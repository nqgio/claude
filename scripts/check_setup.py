#!/usr/bin/env python3
"""Checks that everything needed for a daily run is in place. Read-only (doesn't post anything)."""
import shutil, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from platforms import youtube, instagram, tiktok  # noqa: E402
from platforms.common import req  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ok = True


def check(name, cond, hint=""):
    global ok
    print(("  ✅ " if cond else "  ❌ ") + name + ("" if cond else f"  → {hint}"))
    ok &= bool(cond)


print("Rendering")
check("ffmpeg", shutil.which("ffmpeg"), "apt-get install -y ffmpeg")
check("node", shutil.which("node"), "install Node 18+")
check("playwright", subprocess.run(["node", "-e", "require('playwright')"], capture_output=True).returncode == 0, "npm i -g playwright && npx playwright install chromium")
check("voice model", (ROOT / "models/kokoro-v1.0.int8.onnx").exists() and (ROOT / "models/voices-v1.0.bin").exists(), "bash scripts/bootstrap.sh")
try:
    import kokoro_onnx, soundfile, numpy, requests  # noqa: F401
    check("python packages", True)
except ImportError as e:
    check("python packages", False, f"bash scripts/bootstrap.sh ({e})")

print("Platforms (optional, any subset works)")
for mod, test in [(youtube, lambda: youtube.my_channel_id()),
                  (instagram, lambda: req("GET", f"{instagram.API}/me?fields=username&access_token={instagram._e()['IG_ACCESS_TOKEN']}").json()["username"]),
                  (tiktok, lambda: tiktok._token() and "token ok")]:
    if not mod.configured():
        print(f"  ⚪ {mod.NAME}: not configured")
        continue
    try:
        print(f"  ✅ {mod.NAME}: {test()}")
    except Exception as e:
        print(f"  ❌ {mod.NAME}: {e}"); ok = False

sys.exit(0 if ok else 1)
