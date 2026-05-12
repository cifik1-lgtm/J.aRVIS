@echo off
title JARVIS - Administrator Mode

:: Check if running as admin
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting Administrator privileges...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

:: Run JARVIS with admin rights
cd /d "%~dp0"
python main.py

pause:: Project: Cifik Intelegents
