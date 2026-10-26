# Registers a Windows Scheduled Task that starts the app when you log in and
# restarts it if it ever stops. Run in PowerShell from the project folder:
#   powershell -ExecutionPolicy Bypass -File service\windows\install-autostart.ps1
# (Runs as YOU, so the Amazon login window can appear on your desktop.)
$ErrorActionPreference = "Stop"
$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$py = Join-Path $root "backend\.venv\Scripts\pythonw.exe"
$run = Join-Path $root "backend\run.py"
if (-not (Test-Path $py)) { throw "Run scripts\setup.ps1 first ($py not found)" }
$action = New-ScheduledTaskAction -Execute $py -Argument "`"$run`"" -WorkingDirectory (Join-Path $root "backend")
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
  -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName "EbayListingAutomation" -Action $action -Trigger $trigger -Settings $settings `
  -Description "Amazon to eBay listing automation (dashboard at http://localhost:8000)" -Force | Out-Null
Start-ScheduledTask -TaskName "EbayListingAutomation"
Write-Host "Installed and started. Dashboard: http://localhost:8000"
Write-Host "Remove later with:  Unregister-ScheduledTask -TaskName EbayListingAutomation -Confirm:`$false"
