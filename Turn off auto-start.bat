@echo off
title Listing Automation - auto-start off
powershell -NoProfile -Command "Stop-ScheduledTask -TaskName EbayListingAutomation -ErrorAction SilentlyContinue; Unregister-ScheduledTask -TaskName EbayListingAutomation -Confirm:$false -ErrorAction SilentlyContinue"
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000 " ^| findstr LISTENING') do taskkill /pid %%p /f >nul 2>&1
echo  Auto-start is off and the background app was stopped.
echo  Use START.bat whenever you want to run it.
pause
