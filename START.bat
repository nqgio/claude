@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Listing Automation

echo.
echo  ==============================================
echo    Listing Automation  -  Amazon to eBay
echo  ==============================================
echo.

rem --- Already running? Just open the dashboard. ------------------------------
curl -s -o nul http://127.0.0.1:8000/api/status >nul 2>&1
if not errorlevel 1 (
  echo  The app is already running. Opening the dashboard...
  start "" http://localhost:8000
  timeout /t 3 >nul
  exit /b 0
)

rem --- Find Python 3.11 or newer, install it if missing. ----------------------
set "PY="
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if not errorlevel 1 set "PY=py -3"
if not defined PY (
  python -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
  if not errorlevel 1 set "PY=python"
)
if not defined PY (
  echo  Python is not installed yet. Installing it now - this takes a minute...
  echo.
  winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
  if errorlevel 1 (
    echo.
    echo  Could not install Python automatically.
    echo  Please install it from https://www.python.org/downloads/
    echo  and tick "Add python.exe to PATH" in the installer.
    start "" https://www.python.org/downloads/
    pause
    exit /b 1
  )
  echo.
  echo  Python is installed. Please double-click START.bat again.
  pause
  exit /b 0
)

rem --- First-time setup / update dependencies. -------------------------------
if not exist "backend\.venv\Scripts\python.exe" (
  echo  First-time setup - this takes a few minutes, only once...
  echo.
  %PY% -m venv backend\.venv
  if errorlevel 1 goto :fail
)
fc /b "backend\requirements.txt" "backend\.venv\installed-requirements.txt" >nul 2>&1
if errorlevel 1 (
  echo  Installing components...
  "backend\.venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
  "backend\.venv\Scripts\python.exe" -m pip install -r backend\requirements.txt --quiet
  if errorlevel 1 goto :fail
  echo  Installing the browser used to read Amazon...
  "backend\.venv\Scripts\python.exe" -m playwright install chromium
  if errorlevel 1 goto :fail
  copy /y "backend\requirements.txt" "backend\.venv\installed-requirements.txt" >nul
)
if not exist ".env" copy ".env.example" ".env" >nul

rem --- Start. ------------------------------------------------------------------
echo.
echo  Starting... your browser will open at http://localhost:8000
echo.
echo  KEEP THIS WINDOW OPEN while you use the app. Closing it stops the app.
echo  To have it run in the background and start with your PC instead,
echo  double-click "Turn on auto-start.bat".
echo.
"backend\.venv\Scripts\python.exe" backend\run.py --open
echo.
echo  The app stopped.
pause
exit /b 0

:fail
echo.
echo  Something went wrong during setup. Scroll up to see the error,
echo  or copy it and send it for help.
pause
exit /b 1
