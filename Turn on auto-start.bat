@echo off
cd /d "%~dp0"
title Listing Automation - auto-start
if not exist "backend\.venv\Scripts\pythonw.exe" (
  echo  Please double-click START.bat first so the app gets set up.
  pause
  exit /b 1
)
rem Stop a copy started with START.bat (if open) so the background copy can take over.
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000 " ^| findstr LISTENING') do taskkill /pid %%p /f >nul 2>&1
powershell -NoProfile -ExecutionPolicy Bypass -File "service\windows\install-autostart.ps1"
if errorlevel 1 (
  echo.
  echo  Could not turn on auto-start. See the message above.
  pause
  exit /b 1
)
echo.
echo  Done. The app now runs in the background and starts whenever you log in.
echo  Open the dashboard any time at http://localhost:8000
echo  (To turn this off, double-click "Turn off auto-start.bat".)
timeout /t 4 >nul
start "" http://localhost:8000
pause
