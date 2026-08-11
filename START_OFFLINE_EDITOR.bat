@echo off
setlocal
chcp 65001 >nul 2>&1

cd /d "%~dp0"
title OpenMontage - Offline Editor

if not exist "%~dp0scripts\start_local_agent.ps1" (
    echo [ERROR] OpenMontage launcher was not found:
    echo         %~dp0scripts\start_local_agent.ps1
    echo.
    pause
    exit /b 1
)

echo Starting OpenMontage in strict offline mode...
echo.

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start_local_agent.ps1" %*
set "OPENMONTAGE_EXIT_CODE=%ERRORLEVEL%"

if not "%OPENMONTAGE_EXIT_CODE%"=="0" (
    echo.
    echo OpenMontage stopped with error code %OPENMONTAGE_EXIT_CODE%.
    echo Read the message above, fix the missing local prerequisite, and run this file again.
    echo.
    pause
)

exit /b %OPENMONTAGE_EXIT_CODE%
