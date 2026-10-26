#!/usr/bin/env bash
# systemd user service that starts at boot and restarts on failure. Run: bash service/linux/install-autostart.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
UNIT="$HOME/.config/systemd/user/listing-automation.service"
mkdir -p "$(dirname "$UNIT")"
cat > "$UNIT" <<U
[Unit]
Description=Amazon to eBay listing automation
After=network-online.target

[Service]
WorkingDirectory=$ROOT/backend
ExecStart=$ROOT/backend/.venv/bin/python $ROOT/backend/run.py
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
U
systemctl --user daemon-reload
systemctl --user enable --now listing-automation.service
loginctl enable-linger "$USER" || true   # start at boot even before you log in
echo "Installed. Dashboard: http://localhost:8000   (logs: journalctl --user -u listing-automation -f)"
