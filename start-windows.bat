@echo off
REM Double-click to start the Shorts Bot on Windows.
cd /d "%~dp0"
if not exist models\kokoro-v1.0.onnx (python bot\bot.py setup || (echo Setup failed, see above. & pause & exit /b 1))
python bot\bot.py
pause
