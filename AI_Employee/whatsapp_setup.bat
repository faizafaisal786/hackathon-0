@echo off
:: ============================================================
:: WhatsApp Watcher Setup — Windows
:: ============================================================
:: Run this file ONCE to set up WhatsApp Web session.
:: After setup, PM2 handles everything automatically.
::
:: Steps this script does:
::   1. Install playwright
::   2. Install chromium browser (free)
::   3. Open WhatsApp Web for QR code scan
::   4. Save session (never need to scan again)
:: ============================================================

echo.
echo ============================================================
echo   WhatsApp Watcher Setup
echo ============================================================
echo.

cd /d "%~dp0"

echo [1/3] Installing playwright...
pip install playwright
if %errorlevel% neq 0 (
    echo ERROR: pip failed. Make sure Python is installed.
    pause
    exit /b 1
)

echo.
echo [2/3] Installing Chromium browser (free, one-time)...
playwright install chromium
if %errorlevel% neq 0 (
    echo ERROR: playwright install failed.
    pause
    exit /b 1
)

echo.
echo [3/3] Opening WhatsApp Web for QR scan...
echo.
echo  ^>^> A browser window will open.
echo  ^>^> Scan the QR code with your WhatsApp phone app.
echo  ^>^> (WhatsApp ^> Three dots ^> Linked Devices ^> Link a device)
echo  ^>^> After scanning, press ENTER in this window.
echo.
pause

python whatsapp_watcher.py --login

echo.
echo ============================================================
echo   Setup COMPLETE!
echo   WhatsApp session saved. Now run:
echo     pm2 start ecosystem.config.js
echo   OR:
echo     python whatsapp_watcher.py --loop
echo ============================================================
echo.
pause
