@echo off
title JARVIS — pip (uses project .venv only)
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: No .venv here. Run run_jarvis_admin.bat once first ^(it creates .venv^).
    pause
    exit /b 1
)

echo Using: "%~dp0.venv\Scripts\python.exe"
".venv\Scripts\python.exe" -m pip %*
if errorlevel 1 pause
