@echo off
title AI Employee — Gold Tier Orchestrator
color 0B

echo.
echo  =========================================
echo   AI Employee - Gold Tier
echo   Full Automation Orchestrator
echo  =========================================
echo.

:: Check Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo  ERROR: Python not found. Install Python 3.11+
    pause
    exit /b 1
)

:: Change to gold-tier directory
cd /d "%~dp0"

:: Install dependencies if needed
python -c "import watchdog, schedule, dotenv, playwright" >nul 2>&1
if errorlevel 1 (
    echo  Installing dependencies...
    pip install -r requirements.txt
    echo.
)

echo  Vault: %~dp0
echo  Starting orchestrator with all watchers...
echo.
echo  Drop files into the Drop\ folder to trigger processing.
echo  Approved actions go in Approved\ folder.
echo  Press Ctrl+C to stop.
echo.

python orchestrator.py

pause
