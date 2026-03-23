@echo off
title AI Employee — Platinum Tier Local Agent
color 0D

echo.
echo  =========================================
echo   AI Employee - Platinum Tier
echo   Local Agent + Approval Watcher
echo  =========================================
echo.

:: Check Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo  ERROR: Python not found. Install Python 3.11+
    pause
    exit /b 1
)

:: Change to platinum-tier directory
cd /d "%~dp0"

:: Install dependencies if needed
python -c "import watchdog, dotenv, plyer" >nul 2>&1
if errorlevel 1 (
    echo  Installing dependencies...
    pip install -r requirements.txt
    echo.
)

echo  Vault: %~dp0
echo.
echo  Starting Local Agent and Approval Watcher...
echo  Drop files into Drop\ folder to process.
echo  Move files in Pending_Approval\ to Approved\ to execute.
echo  Press Ctrl+C to stop.
echo.

:: Start approval watcher in background
start "Approval Watcher" python local\local_approval_watcher.py

:: Start local agent in foreground
python local\local_agent.py

pause
