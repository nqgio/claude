@echo off
REM Double-click to start the Shorts Bot on Windows.
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
REM Prefer the official "py" launcher (python.exe can be a Microsoft Store shortcut)
where py >nul 2>nul && (set "PYEXE=py -3") || (set "PYEXE=python")
if not exist models\kokoro-v1.0.onnx (
  %PYEXE% bot\bot.py setup
  if errorlevel 1 (echo. & echo Setup failed - see the messages above. & pause & exit /b 1)
)
%PYEXE% bot\bot.py
pause
