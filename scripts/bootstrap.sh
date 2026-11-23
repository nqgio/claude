#!/usr/bin/env bash
# Idempotent: installs Python deps + downloads the local voice model. Safe to run every session.
set -euo pipefail
cd "$(dirname "$0")/.."
pip install --break-system-packages -q kokoro-onnx soundfile numpy requests 2>/dev/null || pip install -q kokoro-onnx soundfile numpy requests
mkdir -p models
base=https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0
[ -s models/kokoro-v1.0.int8.onnx ] || curl -sSL -o models/kokoro-v1.0.int8.onnx "$base/kokoro-v1.0.int8.onnx"
[ -s models/voices-v1.0.bin ] || curl -sSL -o models/voices-v1.0.bin "$base/voices-v1.0.bin"
node -e "require('playwright')" 2>/dev/null || { npm i -g playwright@1 >/dev/null && npx playwright install --with-deps chromium; }
echo "bootstrap ok"
