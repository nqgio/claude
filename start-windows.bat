@echo off
REM Double-click to start the Shorts Bot on Windows. The first start installs everything it needs.
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
REM Prefer Python 3.12/3.13 (best package support), then any Python 3, then "python".
set "PYEXE="
py -3.12 -c "1" >nul 2>nul && set "PYEXE=py -3.12"
if not defined PYEXE py -3.13 -c "1" >nul 2>nul && set "PYEXE=py -3.13"
if not defined PYEXE py -3 -c "1" >nul 2>nul && set "PYEXE=py -3"
if not defined PYEXE set "PYEXE=python"
echo Using: %PYEXE%
%PYEXE% bot\bot.py
echo.
echo The bot stopped. If you see an error above, send a screenshot of this window.
pause
