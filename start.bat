@echo off
setlocal enabledelayedexpansion
title LLM-Powered RPG Launcher

:: ============================================
::  LLM-Powered RPG - Windows Startup Script
:: ============================================
::  Checks Python 3.10+, creates venv, installs
::  deps, starts Flask server, opens browser.
:: ============================================

echo.
echo ============================================
echo    LLM-Powered RPG - Starting Up
echo ============================================
echo.

:: --------------------------------------------------
:: 1. Check if Python is installed
:: --------------------------------------------------
echo [..] Checking for Python...

where python >nul 2>&1
if errorlevel 1 (
    echo.
    echo [ERROR] Python was not found!
    echo         Please install Python 3.10 or later.
    echo         Download from: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)
echo [OK] Python found.

:: --------------------------------------------------
:: 2. Check Python version (must be 3.10+)
:: --------------------------------------------------
python -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)"
if errorlevel 1 (
    echo.
    echo [ERROR] Python 3.10 or later is required.
    echo         Detected version:
    call python --version
    echo.
    echo         Please upgrade Python from: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PY_VER=%%i
echo [OK] %PY_VER%
echo.

:: --------------------------------------------------
:: 3. Create virtual environment if needed
:: --------------------------------------------------
if not exist ".venv\Scripts\activate.bat" (
    echo [..] Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo.
        echo [ERROR] Failed to create virtual environment.
        echo         Make sure you have the 'venv' module available.
        echo.
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created.
) else (
    echo [OK] Virtual environment already exists.
)
echo.

:: --------------------------------------------------
:: 4. Activate virtual environment
:: --------------------------------------------------
echo [..] Activating virtual environment...
call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo.
    echo [ERROR] Failed to activate virtual environment.
    echo.
    pause
    exit /b 1
)
echo [OK] Virtual environment activated.
echo.

:: --------------------------------------------------
:: 5. Install dependencies
:: --------------------------------------------------
if exist "requirements.txt" (
    echo [..] Installing dependencies from requirements.txt...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo [ERROR] Failed to install dependencies.
        echo         Check your network connection and requirements.txt.
        echo.
        pause
        exit /b 1
    )
    echo [OK] Dependencies installed.
) else (
    echo [WARN] requirements.txt not found, skipping dependency installation.
)
echo.

:: --------------------------------------------------
:: 6. Check Node.js and npm
:: --------------------------------------------------
echo [..] Checking for Node.js and npm...

where node >nul 2>nul
if errorlevel 1 (
    echo.
    echo [ERROR] Node.js is required but not installed.
    echo         Install Node.js from https://nodejs.org/ (v18 or later)
    echo.
    pause
    exit /b 1
)

where npm >nul 2>nul
if errorlevel 1 (
    echo.
    echo [ERROR] npm is required but not installed.
    echo         Install npm alongside Node.js from https://nodejs.org/ (v18 or later)
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('node --version') do set NODE_VER=%%i
for /f "tokens=*" %%i in ('npm --version') do set NPM_VER=%%i
echo [OK] Found Node.js !NODE_VER! with npm !NPM_VER!
echo.

:: --------------------------------------------------
:: 7. Install frontend dependencies and build TypeScript
:: --------------------------------------------------
echo [..] Installing frontend dependencies (npm install^)...
call npm install
if errorlevel 1 (
    echo.
    echo [ERROR] npm install failed. Check your network connection and package.json.
    echo.
    pause
    exit /b 1
)
echo [OK] Frontend dependencies installed.
echo.

echo [..] Compiling TypeScript frontend (npm run build^)...
call npm run build
if errorlevel 1 (
    echo.
    echo [ERROR] TypeScript build failed. Check for errors in app/static/ts/.
    echo.
    pause
    exit /b 1
)
echo [OK] TypeScript compilation complete.
echo.

:: --------------------------------------------------
:: 8. Start Flask server and open browser
:: --------------------------------------------------
echo [..] Starting Flask server on port 5000...
echo.

:: Start the server in a minimized window so it runs in the background
start "RPG Server" /MIN python run.py

:: Wait for server to be ready (up to 30 seconds)
echo [..] Waiting for server to be ready...

>nul 2>&1 where powershell
if errorlevel 1 goto :healthfallback

:: PowerShell is available — do health check loop
>nul 2>&1 powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://localhost:5000/api/health' -TimeoutSec 2; exit 0 } catch { exit 1 }" && (
    echo [OK] Server is ready!
    goto :openbrowser
)

set RETRIES=0
:healthloop
if !RETRIES! GEQ 30 goto :healthtimeout
>nul 2>&1 powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://localhost:5000/api/health' -TimeoutSec 2; exit 0 } catch { exit 1 }" && (
    echo [OK] Server is ready!
    goto :openbrowser
)
set /a RETRIES+=1
timeout /t 1 /nobreak >nul
goto :healthloop
:healthtimeout
echo [WARN] Server may not be fully started yet.
goto :openbrowser

:healthfallback
echo [WARN] PowerShell not available; using fallback delay...
timeout /t 3 /nobreak >nul

:openbrowser

:: Open the browser to the game
echo [OK] Opening browser to http://localhost:5000 ...
start http://localhost:5000

echo.
echo ============================================
echo  Server is running at http://localhost:5000
echo.
echo  Close the "RPG Server" window to stop it.
echo  Or press any key here to shut it down...
echo ============================================
echo.

:: Wait for user to press a key before shutting down
pause >nul

echo [..] Shutting down server...
taskkill /FI "WINDOWTITLE eq RPG Server" >nul 2>&1
if errorlevel 1 (
    echo [WARN] Could not close the RPG Server window automatically.
    echo [WARN] Please close the "RPG Server" window manually.
)
echo [OK] Server stopped. Goodbye!
echo.
