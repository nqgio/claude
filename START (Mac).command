#!/usr/bin/env bash
# Double-click to start Listing Automation on a Mac (first run sets everything up).
cd "$(dirname "$0")"
echo "Listing Automation - Amazon to eBay"
if curl -s -o /dev/null http://127.0.0.1:8000/api/status; then
  echo "Already running - opening the dashboard."; open http://localhost:8000; exit 0
fi
PY=""
for c in python3.13 python3.12 python3.11 python3; do
  if command -v "$c" >/dev/null && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  echo "Python 3.11+ is needed. Opening the download page - install it, then double-click this file again."
  open https://www.python.org/downloads/; read -r -p "Press Enter to close."; exit 1
fi
set -e
[ -x backend/.venv/bin/python ] || { echo "First-time setup (a few minutes, only once)..."; "$PY" -m venv backend/.venv; }
if ! cmp -s backend/requirements.txt backend/.venv/installed-requirements.txt; then
  backend/.venv/bin/python -m pip install --upgrade pip --quiet
  backend/.venv/bin/python -m pip install -r backend/requirements.txt --quiet
  backend/.venv/bin/python -m playwright install chromium
  cp backend/requirements.txt backend/.venv/installed-requirements.txt
fi
[ -f .env ] || cp .env.example .env
echo; echo "Starting... your browser will open at http://localhost:8000"
echo "KEEP THIS WINDOW OPEN while you use the app. Closing it stops the app."
backend/.venv/bin/python backend/run.py --open
