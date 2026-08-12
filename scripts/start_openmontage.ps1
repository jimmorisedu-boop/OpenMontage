[CmdletBinding()]
param([switch]$InspectRuntime)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$runtime = Join-Path $repoRoot 'runtime'
$python = Join-Path $runtime 'python\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Portable Python is missing. Run SETUP_PORTABLE_RUNTIME.bat.' }
$layout = (& $python -m scripts.portable_runtime_layout --root $repoRoot) | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) { throw 'Could not resolve the portable runtime layout.' }
if ($InspectRuntime) { $layout | ConvertTo-Json -Compress; exit 0 }

New-Item -ItemType Directory -Force -Path $layout.logs_dir, $layout.state_dir, $layout.temp_dir | Out-Null
$env:PATH = "$(Split-Path $layout.ollama_exe);$(Split-Path $layout.ffmpeg_exe);$(Split-Path $layout.ytdlp_exe);$env:PATH"
$env:OPENMONTAGE_ROOT = $repoRoot
$env:OPENMONTAGE_NETWORK_MODE = 'url-import-only'
$env:OPENMONTAGE_ORCHESTRATOR_MODEL = [string]$layout.orchestrator_model
$env:OPENMONTAGE_VISION_MODEL = [string]$layout.vision_model
$env:OLLAMA_HOST = '127.0.0.1:11434'
$env:OLLAMA_BASE_URL = 'http://127.0.0.1:11434'
$env:OLLAMA_MODELS = [string]$layout.models_dir
$env:OLLAMA_NO_CLOUD = '1'
$env:OLLAMA_CONTEXT_LENGTH = '32768'
$env:OLLAMA_MAX_LOADED_MODELS = '1'
$env:OLLAMA_NUM_PARALLEL = '1'
$env:OLLAMA_FLASH_ATTENTION = '1'
$env:OLLAMA_LOAD_TIMEOUT = '15m'
$env:NO_PROXY = '127.0.0.1,localhost,::1'
$env:TEMP = [string]$layout.temp_dir
$env:TMP = [string]$layout.temp_dir

function Test-LocalOllama {
    try { Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:11434/api/version' -TimeoutSec 2 | Out-Null; return $true } catch { return $false }
}
function Test-ChatServer([int]$port) {
    try { Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$port/" -TimeoutSec 2 | Out-Null; return $true } catch { return $false }
}

$owned = @()
try {
    if (-not (Test-LocalOllama)) {
        $ollama = Start-Process -FilePath $layout.ollama_exe -ArgumentList 'serve' -WorkingDirectory $runtime -WindowStyle Hidden `
            -RedirectStandardOutput (Join-Path $layout.logs_dir 'ollama-server.stdout.log') `
            -RedirectStandardError (Join-Path $layout.logs_dir 'ollama-server.stderr.log') -PassThru
        $owned += $ollama
        for ($i = 0; $i -lt 120 -and -not (Test-LocalOllama); $i++) { Start-Sleep -Milliseconds 500 }
        if (-not (Test-LocalOllama)) { throw 'Portable Ollama did not start.' }
    }

    & $python -m scripts.openmontage_preflight --root $repoRoot
    if ($LASTEXITCODE -ne 0) { throw 'Portable preflight failed.' }

    $port = 17861
    while (Test-NetConnection -ComputerName 127.0.0.1 -Port $port -InformationLevel Quiet -WarningAction SilentlyContinue) { $port++ }
    $server = Start-Process -FilePath $python -ArgumentList @('-m','scripts.openmontage_chat.app','--root',$repoRoot,'--port',"$port") `
        -WorkingDirectory $repoRoot -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $layout.logs_dir 'chat-server.stdout.log') `
        -RedirectStandardError (Join-Path $layout.logs_dir 'chat-server.stderr.log') -PassThru
    $owned += $server
    for ($i = 0; $i -lt 60 -and -not (Test-ChatServer $port); $i++) { Start-Sleep -Milliseconds 250 }
    if (-not (Test-ChatServer $port)) { throw 'OpenMontage chat server did not start.' }

    $edge = 'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
    if (-not (Test-Path -LiteralPath $edge)) { throw 'Microsoft Edge WebView runtime is missing.' }
    $profile = Join-Path $runtime 'chat-data\edge-profile'
    New-Item -ItemType Directory -Force -Path $profile | Out-Null
    # scripts.openmontage_chat.app owns the backend; --app creates a dedicated window without browser chrome.
    $window = Start-Process -FilePath $edge -ArgumentList @(
        "--app=http://127.0.0.1:$port/",
        "--user-data-dir=$profile",
        '--no-first-run',
        '--disable-sync',
        '--disable-background-networking',
        '--disable-component-update'
    ) -PassThru -Wait
    exit $window.ExitCode
} finally {
    [array]::Reverse($owned)
    foreach ($process in $owned) {
        if (-not $process.HasExited) { Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue }
    }
}
