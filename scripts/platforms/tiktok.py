"""TikTok Content Posting API.
Env: TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET, TIKTOK_REFRESH_TOKEN
     TIKTOK_MODE = draft (default: lands in your TikTok inbox, you tap Post)
                 | direct (needs an audited app; unaudited apps can only post privately)
TikTok has no comment API for normal developers, so votes come from YouTube + Instagram.
"""
import json, math, os
from .common import env, req

API = "https://open.tiktokapis.com/v2"
NAME = "tiktok"


def configured():
    return env("TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET", "TIKTOK_REFRESH_TOKEN") is not None


def _token():
    e = env("TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET", "TIKTOK_REFRESH_TOKEN")
    r = req("POST", f"{API}/oauth/token/", headers={"Content-Type": "application/x-www-form-urlencoded"}, data={
        "client_key": e["TIKTOK_CLIENT_KEY"], "client_secret": e["TIKTOK_CLIENT_SECRET"],
        "grant_type": "refresh_token", "refresh_token": e["TIKTOK_REFRESH_TOKEN"]}).json()
    if "access_token" not in r:
        raise RuntimeError(f"TikTok token refresh failed: {r}")
    return r["access_token"]


def upload(video_path, caption):
    tok = _token()
    size = os.path.getsize(video_path)
    chunk = size if size <= 64 * 1024 * 1024 else 10 * 1024 * 1024
    n = math.ceil(size / chunk)
    src = {"source": "FILE_UPLOAD", "video_size": size, "chunk_size": chunk, "total_chunk_count": n}
    mode = os.environ.get("TIKTOK_MODE", "draft")
    h = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json; charset=UTF-8"}
    if mode == "direct":
        body = {"post_info": {"title": caption[:2200], "privacy_level": os.environ.get("TIKTOK_PRIVACY", "PUBLIC_TO_EVERYONE"),
                              "disable_comment": False, "is_aigc": True}, "source_info": src}
        data = req("POST", f"{API}/post/publish/video/init/", headers=h, data=json.dumps(body)).json()["data"]
    else:
        data = req("POST", f"{API}/post/publish/inbox/video/init/", headers=h, data=json.dumps({"source_info": src})).json()["data"]
    with open(video_path, "rb") as f:
        for i in range(n):
            part = f.read(chunk if i < n - 1 else size - chunk * (n - 1))
            start = i * chunk
            req("PUT", data["upload_url"], headers={"Content-Type": "video/mp4", "Content-Length": str(len(part)),
                                                    "Content-Range": f"bytes {start}-{start + len(part) - 1}/{size}"}, data=part, timeout=600)
    return {"id": data["publish_id"], "url": None, "mode": mode}
