#!/bin/bash
# Double-click to start the Shorts Bot on macOS.
cd "$(dirname "$0")"
if [ ! -f models/kokoro-v1.0.onnx ]; then python3 bot/bot.py setup || { echo "Setup failed, see above."; read -n1; exit 1; }; fi
python3 bot/bot.py
