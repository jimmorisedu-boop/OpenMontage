[CmdletBinding()]
param([switch]$CreateProfile)
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    throw 'Ollama is missing. Copy it from approved offline installation media; this script never downloads software.'
}

if ($CreateProfile) {
    $modelFile = Join-Path $repoRoot 'config\ollama\gpt-oss-20b-32k.Modelfile'
    & ollama create openmontage-gpt-oss:20b-32k -f $modelFile
    if ($LASTEXITCODE -ne 0) { throw 'Failed to create the local 32K profile.' }
}

$python = Join-Path $repoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw 'Repository Python environment is missing. Restore it from the approved offline wheelhouse or environment archive.'
}

$env:OPENMONTAGE_OFFLINE = '1'
$env:OLLAMA_BASE_URL = 'http://127.0.0.1:11434'
& $python -m scripts.local_agent_preflight --root $repoRoot
exit $LASTEXITCODE
