@echo off
setlocal
chcp 65001 >nul 2>&1

cd /d "%~dp0"
title OpenMontage - Portable Runtime Setup

echo This one-time setup downloads only the fixed OpenMontage runtime and models.
echo Runtime location: %~dp0runtime
echo.

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup_portable_runtime.ps1"
set "OPENMONTAGE_EXIT_CODE=%ERRORLEVEL%"

echo.
if "%OPENMONTAGE_EXIT_CODE%"=="0" (
    echo Portable runtime setup completed successfully.
) else (
    echo Portable runtime setup stopped with error code %OPENMONTAGE_EXIT_CODE%.
)
echo.
pause
exit /b %OPENMONTAGE_EXIT_CODE%
