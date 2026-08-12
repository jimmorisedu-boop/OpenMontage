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

foreach ($path in @($layout.logs_dir, $layout.state_dir, $layout.temp_dir, $layout.jan_data, $layout.models_dir)) {
    New-Item -ItemType Directory -Force -Path $path | Out-Null
}
$processDir = Join-Path $layout.state_dir 'processes'
New-Item -ItemType Directory -Force -Path $processDir | Out-Null
$launcherId = [guid]::NewGuid().ToString('n')
$ledgerPath = Join-Path $processDir "$launcherId.json"
$owned = @()

$env:PATH = "$(Split-Path $layout.ollama_exe);$(Split-Path $layout.ffmpeg_exe);$(Split-Path $layout.ytdlp_exe);$env:PATH"
$env:OPENMONTAGE_ROOT = $repoRoot
$env:OPENMONTAGE_JAN_DATA_ROOT = [string]$layout.jan_data
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
$env:XDG_CACHE_HOME = Join-Path $runtime 'cache'
$env:HF_HOME = Join-Path $runtime 'cache\huggingface'
$env:PIP_CACHE_DIR = Join-Path $runtime 'cache\pip'

function Save-Ledger([string]$status) {
    [ordered]@{ launcher_id = $launcherId; status = $status; root = $repoRoot; processes = $owned } |
        ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $ledgerPath -Encoding utf8
}
function Test-LocalOllama {
    try { Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:11434/api/version' -TimeoutSec 2 | Out-Null; return $true } catch { return $false }
}
function Stop-OwnedProcesses {
    $records = @($owned)
    [array]::Reverse($records)
    foreach ($record in $records) {
        $process = Get-Process -Id $record.pid -ErrorAction SilentlyContinue
        if (-not $process) { continue }
        try {
            $actualPath = $process.Path
            $actualStart = $process.StartTime.ToUniversalTime().ToString('o')
            if ($actualPath -eq $record.executable -and $actualStart -eq $record.start_utc) {
                Stop-Process -Id $record.pid -Force -ErrorAction Stop
            }
        } catch { Write-Warning "Could not stop owned process $($record.pid): $($_.Exception.Message)" }
    }
}

try {
    if (-not (Test-LocalOllama)) {
        $ollama = Start-Process -FilePath $layout.ollama_exe -ArgumentList 'serve' -WorkingDirectory $runtime -WindowStyle Hidden `
            -RedirectStandardOutput (Join-Path $layout.logs_dir 'ollama-server.stdout.log') `
            -RedirectStandardError (Join-Path $layout.logs_dir 'ollama-server.stderr.log') -PassThru
        $owned += [ordered]@{ role = 'ollama'; pid = $ollama.Id; start_utc = $ollama.StartTime.ToUniversalTime().ToString('o'); executable = $ollama.Path }
        Save-Ledger 'starting'
        for ($attempt = 0; $attempt -lt 60 -and -not (Test-LocalOllama); $attempt++) {
            if ($ollama.HasExited) { break }
            Start-Sleep -Milliseconds 500
        }
        if (-not (Test-LocalOllama)) { throw "Portable Ollama did not start. Read $($layout.logs_dir)." }
    }

    & $python -m scripts.openmontage_preflight --root $repoRoot
    if ($LASTEXITCODE -ne 0) { throw 'Portable preflight failed. Run SETUP_PORTABLE_RUNTIME.bat.' }
    Save-Ledger 'running'
    $jan = Start-Process -FilePath $layout.jan_exe -WorkingDirectory $repoRoot -PassThru -Wait
    $exitCode = $jan.ExitCode
    Save-Ledger 'jan-exited'
    exit $exitCode
} finally {
    Stop-OwnedProcesses
    Save-Ledger 'stopped'
}
