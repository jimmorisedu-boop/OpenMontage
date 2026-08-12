[CmdletBinding()]
param([switch]$PlanOnly)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$runtime = Join-Path $repoRoot 'runtime'
$downloads = Join-Path $runtime 'downloads'
$artifacts = Get-Content -Raw (Join-Path $repoRoot 'config\runtime\artifacts.json') | ConvertFrom-Json

$paths = [ordered]@{
    python = Join-Path $repoRoot 'runtime\python\python.exe'
    ollama = Join-Path $repoRoot 'runtime\ollama\ollama.exe'
    ffmpeg = Join-Path $repoRoot 'runtime\ffmpeg\ffmpeg.exe'
    ffprobe = Join-Path $repoRoot 'runtime\ffmpeg\ffprobe.exe'
    ytdlp = Join-Path $repoRoot 'runtime\downloader\yt-dlp.exe'
    models = Join-Path $repoRoot 'runtime\models'
    logs = Join-Path $repoRoot 'runtime\logs'
}
$plan = [ordered]@{
    runtime_root = $runtime
    visible_model = 'openmontage-gpt-oss:20b-32k'
    hidden_vision_model = 'qwen3.5:9b'
    downloads = @('Python', 'Ollama', 'FFmpeg', 'yt-dlp', 'gpt-oss:20b', 'qwen3.5:9b')
}
if ($PlanOnly) { $plan | ConvertTo-Json -Compress; exit 0 }

New-Item -ItemType Directory -Force -Path $runtime, $downloads, $paths.models, $paths.logs | Out-Null

function Get-VerifiedArtifact([object]$artifact) {
    $name = if ($artifact.archive) { [string]$artifact.archive } else { Split-Path -Leaf ([string]$artifact.portable_url) }
    $url = if ($artifact.url) { [string]$artifact.url } else { [string]$artifact.portable_url }
    $expected = if ($artifact.sha256) { [string]$artifact.sha256 } else { [string]$artifact.portable_sha256 }
    $target = Join-Path $downloads $name
    $valid = (Test-Path -LiteralPath $target) -and ((Get-FileHash -Algorithm SHA256 -LiteralPath $target).Hash.ToLowerInvariant() -eq $expected.ToLowerInvariant())
    if (-not $valid) {
        Write-Host "Downloading verified artifact: $name"
        & curl.exe --fail --location --retry 3 --continue-at - --output $target $url
        if ($LASTEXITCODE -ne 0) { throw "Download failed: $name" }
    }
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $target).Hash.ToLowerInvariant()
    if ($actual -ne $expected.ToLowerInvariant()) { throw "Checksum mismatch: $name" }
    return $target
}

if (-not (Test-Path -LiteralPath $paths.python)) {
    $pythonDir = Split-Path $paths.python
    New-Item -ItemType Directory -Force -Path $pythonDir | Out-Null
    Expand-Archive -LiteralPath (Get-VerifiedArtifact $artifacts.python) -DestinationPath $pythonDir -Force
    $pth = Get-ChildItem -LiteralPath $pythonDir -Filter 'python*._pth' | Select-Object -First 1
    if (-not $pth) { throw 'Portable Python path configuration was not found.' }
    $content = (Get-Content -Raw $pth.FullName).Replace('#import site', 'import site')
    if ($content -notmatch '(?m)^\.\.\\\.\.$') {
        $content = $content.TrimEnd() + "`r`n..\..`r`n"
    }
    Set-Content -LiteralPath $pth.FullName -Value $content -Encoding ascii
    & $paths.python (Get-VerifiedArtifact $artifacts.get_pip) --disable-pip-version-check --no-warn-script-location
    if ($LASTEXITCODE -ne 0) { throw 'Failed to bootstrap pip in portable Python.' }
}
& $paths.python -m pip install --disable-pip-version-check --no-warn-script-location -r (Join-Path $repoRoot 'config\runtime\requirements-portable.txt')
if ($LASTEXITCODE -ne 0) { throw 'Failed to install the portable local Python dependencies.' }

if (-not (Test-Path -LiteralPath $paths.ollama)) {
    New-Item -ItemType Directory -Force -Path (Split-Path $paths.ollama) | Out-Null
    Expand-Archive -LiteralPath (Get-VerifiedArtifact $artifacts.ollama) -DestinationPath (Split-Path $paths.ollama) -Force
}
if (-not (Test-Path -LiteralPath $paths.ffmpeg) -or -not (Test-Path -LiteralPath $paths.ffprobe)) {
    $stage = Join-Path $runtime 'ffmpeg-stage'
    New-Item -ItemType Directory -Force -Path $stage, (Split-Path $paths.ffmpeg) | Out-Null
    Expand-Archive -LiteralPath (Get-VerifiedArtifact $artifacts.ffmpeg) -DestinationPath $stage -Force
    foreach ($name in @('ffmpeg.exe', 'ffprobe.exe')) {
        $source = Get-ChildItem -LiteralPath $stage -Recurse -Filter $name | Select-Object -First 1
        if (-not $source) { throw "$name was not found in the verified FFmpeg archive." }
        Copy-Item -LiteralPath $source.FullName -Destination (Join-Path (Split-Path $paths.ffmpeg) $name)
    }
    Remove-Item -LiteralPath $stage -Recurse -Force
}
if (-not (Test-Path -LiteralPath $paths.ytdlp)) {
    New-Item -ItemType Directory -Force -Path (Split-Path $paths.ytdlp) | Out-Null
    Copy-Item -LiteralPath (Get-VerifiedArtifact $artifacts.yt_dlp) -Destination $paths.ytdlp
}

$env:PATH = "$(Split-Path $paths.ollama);$(Split-Path $paths.ffmpeg);$env:PATH"
$env:OLLAMA_HOST = '127.0.0.1:11434'
$env:OLLAMA_BASE_URL = 'http://127.0.0.1:11434'
$env:OLLAMA_MODELS = $paths.models
$env:OLLAMA_NO_CLOUD = '1'
$env:NO_PROXY = '127.0.0.1,localhost,::1'
$env:OLLAMA_CONTEXT_LENGTH = '32768'
$env:OLLAMA_MAX_LOADED_MODELS = '1'
$env:OLLAMA_NUM_PARALLEL = '1'
$env:OLLAMA_FLASH_ATTENTION = '1'
$env:OLLAMA_LOAD_TIMEOUT = '15m'

function Test-LocalOllama {
    try { Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:11434/api/version' -TimeoutSec 2 | Out-Null; return $true } catch { return $false }
}
if (-not (Test-LocalOllama)) {
    $server = Start-Process -FilePath $paths.ollama -ArgumentList 'serve' -WorkingDirectory $runtime -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $paths.logs 'ollama-server.stdout.log') `
        -RedirectStandardError (Join-Path $paths.logs 'ollama-server.stderr.log') -PassThru
    for ($attempt = 0; $attempt -lt 120 -and -not (Test-LocalOllama); $attempt++) {
        if ($server.HasExited) { break }
        Start-Sleep -Milliseconds 500
    }
    if (-not (Test-LocalOllama)) { throw "Portable Ollama did not start. Read $($paths.logs)" }
}

foreach ($model in @('gpt-oss:20b', 'qwen3.5:9b')) {
    Write-Host "Downloading fixed local model: $model"
    & $paths.ollama pull $model
    if ($LASTEXITCODE -ne 0) { throw "Model download failed: $model" }
}
& $paths.ollama create 'openmontage-gpt-oss:20b-32k' -f (Join-Path $repoRoot 'config\ollama\gpt-oss-20b-32k.Modelfile')
if ($LASTEXITCODE -ne 0) { throw 'Failed to create the fixed 32K orchestration profile.' }
& $paths.ollama rm 'gpt-oss:20b' | Out-Null

$env:OPENMONTAGE_NETWORK_MODE = 'url-import-only'
& $paths.python -m scripts.openmontage_preflight --root $repoRoot
if ($LASTEXITCODE -ne 0) { throw 'Portable runtime preflight failed after setup.' }

Write-Host ''
Write-Host 'Portable OpenMontage is ready. Double-click START_OPENMONTAGE.bat.'
