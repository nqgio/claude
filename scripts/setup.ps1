# One-time setup for Windows. In PowerShell, from the project folder:
#   powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
py -3 -c "import sys; assert sys.version_info >= (3, 11), 'Python 3.11+ required'"
py -3 -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install --upgrade pip
backend\.venv\Scripts\pip.exe install -r backend\requirements.txt
backend\.venv\Scripts\python.exe -m playwright install chromium
Push-Location frontend; npm install; npm run build; Pop-Location
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
Write-Host "`nSetup done. Next: fill in .env, then run:  backend\.venv\Scripts\python.exe backend\run.py"
