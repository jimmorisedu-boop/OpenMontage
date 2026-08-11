[CmdletBinding()]
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$CodexArgs)
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $repoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw 'Repository Python environment is missing. Run scripts\setup_local_agent.ps1 first.'
}

$env:OPENMONTAGE_OFFLINE = '1'
$env:OLLAMA_BASE_URL = 'http://127.0.0.1:11434'
$env:OPENMONTAGE_ORCHESTRATOR_MODEL = 'openmontage-gpt-oss:20b-32k'
$env:OPENMONTAGE_VISION_MODEL = 'qwen3.5:9b'
$env:OPENMONTAGE_ENFORCE_OLLAMA_GPU_GUARD = '1'

& $python -m scripts.local_agent_preflight --root $repoRoot
if ($LASTEXITCODE -ne 0) { throw 'Offline preflight failed. Resolve the listed local prerequisites and retry.' }

Push-Location $repoRoot
try {
    & codex --oss -m openmontage-gpt-oss:20b-32k @CodexArgs
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
