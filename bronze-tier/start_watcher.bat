@echo off
title AI Employee — Bronze Tier File Watcher
color 0A


echo.
echo  =========================================
echo   AI Employee - Bronze Tier
echo   File System Watcher
echo  =========================================
echo.

:: Check Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo  ERROR: Python not found. Install Python 3.13+
    pause
    exit /b 1
)

:: Check watchdog is installed
python -c "import watchdog" >nul 2>&1
if errorlevel 1 (
    echo  Installing watchdog...
    pip install watchdog
    echo.
)

:: Change to bronze-tier directory
cd /d "%~dp0"

echo  Vault: %~dp0
echo  Watching: Inbox folder
echo  Drop any file into the Inbox folder to trigger an action item.
echo.
echo  Press Ctrl+C to stop.
echo.

python filesystem_watcher.py

pause
