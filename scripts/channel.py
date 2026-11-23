"""Channel helpers: resolve a channel from an episode path and load its per-channel credentials."""
import json, os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# per-account secrets MUST be channel-prefixed (e.g. THEO_YT_REFRESH_TOKEN) so one channel can never post to another's account
ACCOUNT_VARS = ["YT_REFRESH_TOKEN", "IG_USER_ID", "IG_ACCESS_TOKEN", "TIKTOK_REFRESH_TOKEN", "YT_PRIVACY", "TIKTOK_MODE"]
# app-level credentials can be shared by all channels (unprefixed) or overridden per channel
APP_VARS = ["YT_CLIENT_ID", "YT_CLIENT_SECRET", "TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET"]


def channel_dir(path):
    p = Path(path).resolve()
    if (p / "channel.json").exists():
        return p
    if (p.parent.parent / "channel.json").exists():
        return p.parent.parent
    if (ROOT / "channels" / str(path) / "channel.json").exists():
        return ROOT / "channels" / str(path)
    raise SystemExit(f"Not a channel or episode path: {path}")


def load(ch):
    return {n: json.loads((ch / f"{n}.json").read_text(encoding="utf-8")) for n in ("channel", "bible", "story")}


def use_credentials(channel_cfg):
    prefix = channel_cfg["env_prefix"]
    for v in ACCOUNT_VARS:
        val = os.environ.get(f"{prefix}_{v}")
        if val:
            os.environ[v] = val
        else:
            os.environ.pop(v, None)
    for v in APP_VARS:
        val = os.environ.get(f"{prefix}_{v}")
        if val:
            os.environ[v] = val


def all_channels():
    return sorted(p.parent for p in (ROOT / "channels").glob("*/channel.json"))
