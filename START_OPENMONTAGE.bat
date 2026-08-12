@echo off
setlocal
chcp 65001 >nul 2>&1
cd /d "%~dp0"
title OpenMontage

echo Starting OpenMontage local chat window...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start_openmontage.ps1" %*
set "OPENMONTAGE_EXIT_CODE=%ERRORLEVEL%"
if not "%OPENMONTAGE_EXIT_CODE%"=="0" (
    echo.
    echo OpenMontage stopped with error code %OPENMONTAGE_EXIT_CODE%.
    echo Run SETUP_PORTABLE_RUNTIME.bat if a local component is missing.
    pause
)
exit /b %OPENMONTAGE_EXIT_CODE%
