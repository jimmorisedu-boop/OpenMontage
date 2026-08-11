[CmdletBinding()]
param([switch]$PlanOnly)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $repoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw 'Repository Python environment is missing. Restore the portable .venv first.'
}

$layoutJson = & $python -m scripts.portable_runtime_layout --root $repoRoot
if ($LASTEXITCODE -ne 0) { throw 'Failed to resolve the portable runtime layout.' }
$layout = $layoutJson | ConvertFrom-Json

$plan = [ordered]@{
    runtime_root = [string]$layout.runtime_root
    models_to_pull = @('gpt-oss:20b', 'qwen3.5:9b')
    profile_to_create = [string]$layout.orchestrator_model
    source_tags_to_remove = @('gpt-oss:20b')
    codex_app_model = [string]$layout.orchestrator_model
    portable_tools = @('ollama', 'ffmpeg', 'ffprobe')
}
if ($PlanOnly) {
    $plan | ConvertTo-Json -Compress
    exit 0
}

$ollamaDir = Split-Path -Parent $layout.ollama_exe
$ffmpegDir = Split-Path -Parent $layout.ffmpeg_exe
$downloadDir = Join-Path $layout.runtime_root 'downloads'
New-Item -ItemType Directory -Path $ollamaDir, $ffmpegDir, $layout.models_dir, $layout.logs_dir, $downloadDir -Force | Out-Null

foreach ($toolName in @('ffmpeg', 'ffprobe')) {
    $target = if ($toolName -eq 'ffmpeg') { [string]$layout.ffmpeg_exe } else { [string]$layout.ffprobe_exe }
    if (-not (Test-Path -LiteralPath $target)) {
        $source = Get-Command $toolName -CommandType Application -ErrorAction SilentlyContinue
        if (-not $source) { throw "$toolName is required once so it can be copied into the portable runtime." }
        Copy-Item -LiteralPath $source.Source -Destination $target
    }
}

if (-not (Test-Path -LiteralPath $layout.ollama_exe)) {
    Write-Host 'Resolving the official standalone Ollama release...'
    $headers = @{ Accept = 'application/vnd.github+json'; 'User-Agent' = 'OpenMontage-Portable-Setup' }
    $release = Invoke-RestMethod -Headers $headers -Uri 'https://api.github.com/repos/ollama/ollama/releases/latest'
    $asset = $release.assets | Where-Object name -eq 'ollama-windows-amd64.zip' | Select-Object -First 1
    if (-not $asset) { throw 'The official standalone Ollama asset was not found.' }

    $archive = Join-Path $downloadDir $asset.name
    if (-not (Test-Path -LiteralPath $archive) -or (Get-Item -LiteralPath $archive).Length -ne $asset.size) {
        Write-Host "Downloading Ollama $($release.tag_name) into the portable runtime..."
        & curl.exe --fail --location --continue-at - --output $archive $asset.browser_download_url
        if ($LASTEXITCODE -ne 0) { throw "Ollama download failed with exit code $LASTEXITCODE." }
    }
    if ((Get-Item -LiteralPath $archive).Length -ne $asset.size) { throw 'Downloaded Ollama archive size does not match the release metadata.' }
    if ($asset.digest -and $asset.digest.StartsWith('sha256:')) {
        $expectedHash = $asset.digest.Substring(7)
        $actualHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $archive).Hash.ToLowerInvariant()
        if ($actualHash -ne $expectedHash.ToLowerInvariant()) { throw 'Downloaded Ollama archive checksum is invalid.' }
    }

    Write-Host 'Extracting portable Ollama...'
    Expand-Archive -LiteralPath $archive -DestinationPath $ollamaDir -Force
    if (-not (Test-Path -LiteralPath $layout.ollama_exe)) { throw 'The Ollama archive did not contain ollama.exe at the expected location.' }
    Remove-Item -LiteralPath $archive -Force
}

$env:PATH = "$ollamaDir;$ffmpegDir;$env:PATH"
$env:OLLAMA_BASE_URL = 'http://127.0.0.1:11434'
$env:OLLAMA_HOST = '127.0.0.1:11434'
$env:OLLAMA_MODELS = [string]$layout.models_dir
$env:OLLAMA_NO_CLOUD = '1'
$env:NO_PROXY = '127.0.0.1,localhost,::1'
$env:OLLAMA_CONTEXT_LENGTH = '32768'
$env:OLLAMA_MAX_LOADED_MODELS = '1'
$env:OLLAMA_NUM_PARALLEL = '1'
$env:OLLAMA_FLASH_ATTENTION = '1'

function Test-LocalOllama {
    try {
        Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:11434/api/version' -TimeoutSec 2 | Out-Null
        return $true
    } catch {
        return $false
    }
}

if (-not (Test-LocalOllama)) {
    $stdoutLog = Join-Path $layout.logs_dir 'ollama-server.stdout.log'
    $stderrLog = Join-Path $layout.logs_dir 'ollama-server.stderr.log'
    $server = Start-Process -FilePath $layout.ollama_exe -ArgumentList 'serve' `
        -WorkingDirectory $layout.runtime_root -WindowStyle Hidden `
        -RedirectStandardOutput $stdoutLog -RedirectStandardError $stderrLog -PassThru
    $ready = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        Start-Sleep -Milliseconds 500
        if (Test-LocalOllama) { $ready = $true; break }
        if ($server.HasExited) { break }
    }
    if (-not $ready) { throw "Portable Ollama did not start. Read $stderrLog" }
}

foreach ($model in $plan.models_to_pull) {
    Write-Host "Downloading fixed local model: $model"
    & $layout.ollama_exe pull $model
    if ($LASTEXITCODE -ne 0) { throw "Model download failed: $model" }
}

$modelFile = Join-Path $repoRoot 'config\ollama\gpt-oss-20b-32k.Modelfile'
& $layout.ollama_exe create $layout.orchestrator_model -f $modelFile
if ($LASTEXITCODE -ne 0) { throw 'Failed to create the fixed 32K orchestration profile.' }

foreach ($sourceTag in $plan.source_tags_to_remove) {
    & $layout.ollama_exe rm $sourceTag
    if ($LASTEXITCODE -ne 0) { throw "Failed to hide the source model tag: $sourceTag" }
}

$env:OPENMONTAGE_OFFLINE = '1'
& $python -m scripts.local_agent_preflight --root $repoRoot
if ($LASTEXITCODE -ne 0) { throw 'Portable runtime preflight failed after setup.' }

& $layout.ollama_exe launch $layout.codex_integration --model $plan.codex_app_model --config --yes
if ($LASTEXITCODE -ne 0) { throw 'Failed to configure Codex Desktop for the fixed local model.' }

Write-Host ''
Write-Host 'Portable OpenMontage runtime is ready.'
Write-Host 'Use START_OFFLINE_EDITOR.bat from now on.'
