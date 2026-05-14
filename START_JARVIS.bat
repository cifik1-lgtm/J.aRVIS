@echo off
echo ==============================================
echo       JARVIS - Initializing System...
echo ==============================================

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH!
    echo Please install Python 3.10+ and check "Add Python to PATH".
    pause
    exit /b
)

:: Check if .venv exists
if not exist ".venv" (
    echo [JARVIS] Creating virtual environment...
    python -m venv .venv
)

:: Activate venv
call .venv\Scripts\activate

:: Check if requirements need installing
if exist "requirements.txt" (
    echo [JARVIS] Checking dependencies...
    pip install -r requirements.txt >nul 2>&1
)

:: Run JARVIS
echo [JARVIS] Launching Main System...
python main.py
pause
