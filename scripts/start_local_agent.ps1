[CmdletBinding()]
param(
    [switch]$InspectRuntime,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$CodexArgs
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $repoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw 'Repository Python environment is missing. Restore the portable .venv first.'
}

$layoutJson = & $python -m scripts.portable_runtime_layout --root $repoRoot
if ($LASTEXITCODE -ne 0) { throw 'Failed to resolve the portable runtime layout.' }
if ($InspectRuntime) {
    Write-Output $layoutJson
    exit 0
}

$layout = $layoutJson | ConvertFrom-Json
$ollamaExe = [string]$layout.ollama_exe
if (-not (Test-Path -LiteralPath $ollamaExe)) {
    throw 'Portable Ollama is missing. Run SETUP_PORTABLE_RUNTIME.bat once while downloads are allowed.'
}
if (-not (Test-Path -LiteralPath $layout.ffmpeg_exe) -or -not (Test-Path -LiteralPath $layout.ffprobe_exe)) {
    throw 'Portable FFmpeg is missing. Run SETUP_PORTABLE_RUNTIME.bat once to copy the local binaries.'
}

New-Item -ItemType Directory -Path $layout.models_dir, $layout.logs_dir -Force | Out-Null
$env:PATH = "$(Split-Path -Parent $ollamaExe);$(Split-Path -Parent $layout.ffmpeg_exe);$env:PATH"
$env:OPENMONTAGE_OFFLINE = '1'
$env:OLLAMA_BASE_URL = 'http://127.0.0.1:11434'
$env:OLLAMA_HOST = '127.0.0.1:11434'
$env:OLLAMA_MODELS = [string]$layout.models_dir
$env:OLLAMA_NO_CLOUD = '1'
$env:NO_PROXY = '127.0.0.1,localhost,::1'
$env:OLLAMA_CONTEXT_LENGTH = '32768'
$env:OLLAMA_MAX_LOADED_MODELS = '1'
$env:OLLAMA_NUM_PARALLEL = '1'
$env:OLLAMA_FLASH_ATTENTION = '1'
$env:OPENMONTAGE_ORCHESTRATOR_MODEL = [string]$layout.orchestrator_model
$env:OPENMONTAGE_VISION_MODEL = [string]$layout.vision_model
$env:OPENMONTAGE_ENFORCE_OLLAMA_GPU_GUARD = '1'

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
    $server = Start-Process -FilePath $ollamaExe -ArgumentList 'serve' `
        -WorkingDirectory $layout.runtime_root -WindowStyle Hidden `
        -RedirectStandardOutput $stdoutLog -RedirectStandardError $stderrLog -PassThru

    $ready = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        Start-Sleep -Milliseconds 500
        if (Test-LocalOllama) {
            $ready = $true
            break
        }
        if ($server.HasExited) { break }
    }
    if (-not $ready) {
        throw "Portable Ollama did not start. Read $stderrLog"
    }
}

& $python -m scripts.local_agent_preflight --root $repoRoot
if ($LASTEXITCODE -ne 0) {
    throw 'Offline preflight failed. Run SETUP_PORTABLE_RUNTIME.bat to restore the fixed local models.'
}

Push-Location $repoRoot
try {
    & $ollamaExe launch $layout.codex_integration --model $layout.orchestrator_model --yes @CodexArgs
    if ($LASTEXITCODE -ne 0) { throw "Codex App launch failed with exit code $LASTEXITCODE." }
} finally {
    Pop-Location
}
