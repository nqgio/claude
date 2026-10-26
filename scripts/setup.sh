#!/usr/bin/env bash
# One-time setup for macOS / Linux. Run from the project folder:  bash scripts/setup.sh
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${PYTHON:-python3}
"$PY" -c 'import sys; assert sys.version_info >= (3, 11), "Python 3.11+ required"'
"$PY" -m venv backend/.venv
backend/.venv/bin/pip install --upgrade pip
backend/.venv/bin/pip install -r backend/requirements.txt
backend/.venv/bin/python -m playwright install chromium
(cd frontend && npm install && npm run build)
[ -f .env ] || cp .env.example .env
echo
echo "Setup done. Next: fill in .env, then run:  backend/.venv/bin/python backend/run.py"
