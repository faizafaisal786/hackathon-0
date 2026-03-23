@echo off
:: ============================================================
::  AI Employee — Windows Task Scheduler Setup
::  Silver Tier — Basic Scheduling
:: ============================================================
::
::  This script registers 3 scheduled tasks in Windows:
::
::  1. AI_Employee_Pipeline   — runs ralph_loop.py every 5 minutes
::  2. AI_Employee_Gmail      — runs gmail_watcher.py every 10 minutes
::  3. AI_Employee_FileWatch  — runs watcher.py every 2 minutes
::
::  Usage:
::    Right-click schedule_setup.bat -> Run as Administrator
::    OR open CMD as Admin and run: schedule_setup.bat
::
::  To remove all tasks:
::    schedule_setup.bat --remove
::
::  To check task status:
::    schtasks /query /tn "AI_Employee_Pipeline"
:: ============================================================

:: Detect Python path
for /f "delims=" %%i in ('where python 2^>nul') do set PYTHON_PATH=%%i

if "%PYTHON_PATH%"=="" (
    echo [ERROR] Python not found. Install Python and add to PATH.
    pause
    exit /b 1
)

:: Get current directory (where this .bat file lives)
set SCRIPT_DIR=%~dp0
:: Remove trailing backslash
if "%SCRIPT_DIR:~-1%"=="\" set SCRIPT_DIR=%SCRIPT_DIR:~0,-1%

echo.
echo ============================================================
echo   AI Employee - Task Scheduler Setup
echo ============================================================
echo   Python:     %PYTHON_PATH%
echo   Script dir: %SCRIPT_DIR%
echo ============================================================
echo.

:: ── Handle --remove flag ─────────────────────────────────────
if "%1"=="--remove" goto REMOVE_TASKS

:: ── Create Tasks ─────────────────────────────────────────────

echo [1/3] Registering AI_Employee_Pipeline (every 5 minutes)...
schtasks /create ^
  /tn "AI_Employee_Pipeline" ^
  /tr "\"%PYTHON_PATH%\" \"%SCRIPT_DIR%\ralph_loop.py\" --once" ^
  /sc minute ^
  /mo 5 ^
  /rl HIGHEST ^
  /f
if %errorlevel%==0 (
    echo       [OK] AI_Employee_Pipeline registered.
) else (
    echo       [WARN] Failed - try running as Administrator.
)

echo.
echo [2/3] Registering AI_Employee_Gmail (every 10 minutes)...
schtasks /create ^
  /tn "AI_Employee_Gmail" ^
  /tr "\"%PYTHON_PATH%\" \"%SCRIPT_DIR%\gmail_watcher.py\"" ^
  /sc minute ^
  /mo 10 ^
  /rl HIGHEST ^
  /f
if %errorlevel%==0 (
    echo       [OK] AI_Employee_Gmail registered.
) else (
    echo       [WARN] Failed - try running as Administrator.
)

echo.
echo [3/3] Registering AI_Employee_FileWatch (every 2 minutes)...
schtasks /create ^
  /tn "AI_Employee_FileWatch" ^
  /tr "\"%PYTHON_PATH%\" \"%SCRIPT_DIR%\watcher.py\"" ^
  /sc minute ^
  /mo 2 ^
  /rl HIGHEST ^
  /f
if %errorlevel%==0 (
    echo       [OK] AI_Employee_FileWatch registered.
) else (
    echo       [WARN] Failed - try running as Administrator.
)

echo.
echo ============================================================
echo   SETUP COMPLETE
echo ============================================================
echo.
echo   Tasks registered:
echo     AI_Employee_Pipeline  - every  5 min  (ralph_loop.py)
echo     AI_Employee_Gmail     - every 10 min  (gmail_watcher.py)
echo     AI_Employee_FileWatch - every  2 min  (watcher.py)
echo.
echo   Verify tasks:
echo     schtasks /query /tn "AI_Employee_Pipeline"
echo     schtasks /query /tn "AI_Employee_Gmail"
echo     schtasks /query /tn "AI_Employee_FileWatch"
echo.
echo   Remove tasks:
echo     schedule_setup.bat --remove
echo ============================================================
echo.
pause
exit /b 0


:: ── Remove Tasks ─────────────────────────────────────────────
:REMOVE_TASKS
echo Removing AI Employee scheduled tasks...
echo.

schtasks /delete /tn "AI_Employee_Pipeline"  /f >nul 2>&1
echo   [OK] AI_Employee_Pipeline removed.

schtasks /delete /tn "AI_Employee_Gmail"     /f >nul 2>&1
echo   [OK] AI_Employee_Gmail removed.

schtasks /delete /tn "AI_Employee_FileWatch" /f >nul 2>&1
echo   [OK] AI_Employee_FileWatch removed.

echo.
echo   All AI Employee scheduled tasks removed.
echo.
pause
exit /b 0
