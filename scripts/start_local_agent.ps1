# Compatibility wrapper. START_OPENMONTAGE.bat is the normal entry point.
& (Join-Path $PSScriptRoot 'start_openmontage.ps1') @args
exit $LASTEXITCODE
