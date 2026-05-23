@echo off
setlocal EnableExtensions
title JARVIS - Administrator Mode

:: Check if running as admin
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting Administrator privileges...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

cd /d "%~dp0"
set "ROOT=%~dp0"
:: strip trailing backslash duplication if any
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "VENV_PY=%ROOT%\.venv\Scripts\python.exe"

:: ---------------------------------------------------------------------------
:: Admin CMD often has a different PATH. Bare "python" may point at another
:: app's venv (e.g. Hermes) with no pip. Prefer the Windows "py" launcher, then
:: use ONLY the project venv interpreter — never PATH "python" after this.
:: ---------------------------------------------------------------------------

set "HAVE_PY=0"
where py >nul 2>&1 && set "HAVE_PY=1"

if not exist "%VENV_PY%" (
    if "%HAVE_PY%"=="1" (
        echo [JARVIS] Creating .venv with py -3 ^(recommended; avoids wrong "python" on PATH^)...
        py -3 -m venv "%ROOT%\.venv"
    ) else (
        where python >nul 2>&1
        if errorlevel 1 (
            echo [JARVIS] ERROR: Neither "py" nor "python" found on PATH.
            echo Install Python 3.11+ from https://www.python.org/downloads/ ^(enable "py launcher" and "Add to PATH"^).
            pause
            exit /b 1
        )
        echo [JARVIS] Creating .venv with python -m venv ...
        python -m venv "%ROOT%\.venv"
    )
    if errorlevel 1 (
        echo [JARVIS] ERROR: Could not create .venv. If an old .venv is broken, delete the folder .venv and retry.
        pause
        exit /b 1
    )
)

if not exist "%VENV_PY%" (
    echo [JARVIS] ERROR: Missing "%VENV_PY%"
    pause
    exit /b 1
)

:: Ensure pip exists in the venv (venv made from some parent Pythons has no pip)
"%VENV_PY%" -m pip --version >nul 2>&1
if errorlevel 1 (
    echo [JARVIS] Bootstrapping pip in .venv ^(ensurepip^)...
    "%VENV_PY%" -m ensurepip --upgrade
)

"%VENV_PY%" -c "import numpy" 2>nul
if errorlevel 1 (
    echo [JARVIS] Installing dependencies from requirements.txt ^(first run or missing packages^)...
    "%VENV_PY%" -m pip install --upgrade pip
    if errorlevel 1 (
        echo [JARVIS] ERROR: pip is not available in .venv. Delete the .venv folder and run this script again.
        pause
        exit /b 1
    )
    "%VENV_PY%" -m pip install -r "%ROOT%\requirements.txt"
    if errorlevel 1 (
        echo [JARVIS] ERROR: pip install failed. Check internet, then run:
        echo   "%VENV_PY%" -m pip install -r "%ROOT%\requirements.txt"
        pause
        exit /b 1
    )
)

echo [JARVIS] Starting main.py ...
"%VENV_PY%" "%ROOT%\main.py"

pause
endlocal
:: Project: Cifik Intelegents
