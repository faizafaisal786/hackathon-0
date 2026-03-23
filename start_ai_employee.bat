@echo off
:: AI Employee Gold Tier — Auto-Start Script
:: Double-click OR add to Windows Task Scheduler

title AI Employee Gold Tier - Ralph Loop
echo ============================================
echo  AI Employee Gold Tier Starting...
echo ============================================

:: Go to vault folder
cd /d "C:\Users\HDD BANK\Desktop\Obsidian Vaults"

:: Start ralph_loop (infinite loop)
python ralph_loop.py

:: If it crashes, wait 10s and restart
echo.
echo [RESTARTING in 10 seconds...]
timeout /t 10
call "%~f0"
