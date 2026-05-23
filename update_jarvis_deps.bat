@echo off
title JARVIS — update dependencies (.venv)
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: No .venv. Run run_jarvis_admin.bat once first.
    pause
    exit /b 1
)

echo [JARVIS] Updating packages from requirements.txt ...
".venv\Scripts\python.exe" -m pip install -U pip
".venv\Scripts\python.exe" -m pip install -r "%~dp0requirements.txt"
echo.
echo Done. Press a key to close.
pause >nul
