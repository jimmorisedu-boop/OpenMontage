@echo off
setlocal
cd /d "%~dp0"
echo START_OFFLINE_EDITOR.bat has been replaced by START_OPENMONTAGE.bat.
call "%~dp0START_OPENMONTAGE.bat" %*
exit /b %ERRORLEVEL%
