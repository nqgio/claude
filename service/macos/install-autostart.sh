#!/usr/bin/env bash
# Starts the app at login and keeps it running (launchd). Run: bash service/macos/install-autostart.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PLIST="$HOME/Library/LaunchAgents/com.listing-automation.plist"
mkdir -p "$HOME/Library/LaunchAgents" "$ROOT/data"
cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.listing-automation</string>
  <key>ProgramArguments</key><array><string>$ROOT/backend/.venv/bin/python</string><string>$ROOT/backend/run.py</string></array>
  <key>WorkingDirectory</key><string>$ROOT/backend</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$ROOT/data/app.log</string>
  <key>StandardErrorPath</key><string>$ROOT/data/app.log</string>
</dict></plist>
PL
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
echo "Installed. Dashboard: http://localhost:8000   (remove: launchctl unload $PLIST && rm $PLIST)"
