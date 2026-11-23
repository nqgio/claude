"""Instagram Reels via the Instagram API with Instagram Login (graph.instagram.com).
Env: IG_USER_ID, IG_ACCESS_TOKEN (long-lived, 60 days; refresh with `python3 scripts/refresh_tokens.py`)
"""
import os, time
from .common import env, req

VER = os.environ.get("IG_API_VERSION", "v23.0")
API = f"https://graph.instagram.com/{VER}"
NAME = "instagram"


def configured():
    return env("IG_USER_ID", "IG_ACCESS_TOKEN") is not None


def _e():
    return env("IG_USER_ID", "IG_ACCESS_TOKEN")


def upload(video_path, caption):
    e = _e(); tok = e["IG_ACCESS_TOKEN"]
    c = req("POST", f"{API}/{e['IG_USER_ID']}/media", data={
        "media_type": "REELS", "upload_type": "resumable", "caption": caption[:2200], "share_to_feed": "true", "access_token": tok}).json()["id"]
    size = os.path.getsize(video_path)
    with open(video_path, "rb") as f:
        req("POST", f"https://rupload.facebook.com/ig-api-upload/{VER}/{c}",
            headers={"Authorization": f"OAuth {tok}", "offset": "0", "file_size": str(size)}, data=f, timeout=600)
    for _ in range(60):  # wait for processing (up to ~5 min)
        st = req("GET", f"{API}/{c}?fields=status_code,status&access_token={tok}").json()
        if st.get("status_code") == "FINISHED":
            break
        if st.get("status_code") == "ERROR":
            raise RuntimeError(f"Instagram processing failed: {st}")
        time.sleep(5)
    mid = req("POST", f"{API}/{e['IG_USER_ID']}/media_publish", data={"creation_id": c, "access_token": tok}).json()["id"]
    link = req("GET", f"{API}/{mid}?fields=permalink&access_token={tok}").json().get("permalink")
    return {"id": mid, "url": link}


def comment(media_id, text):
    return req("POST", f"{API}/{media_id}/comments", data={"message": text, "access_token": _e()["IG_ACCESS_TOKEN"]}).json()["id"]


def reply(comment_id, text):
    return req("POST", f"{API}/{comment_id}/replies", data={"message": text, "access_token": _e()["IG_ACCESS_TOKEN"]}).json()["id"]


def fetch_comments(media_id, limit=300):
    e = _e(); tok = e["IG_ACCESS_TOKEN"]
    me = req("GET", f"{API}/me?fields=username&access_token={tok}").json().get("username")
    url = f"{API}/{media_id}/comments?fields=id,text,like_count,username,timestamp,replies{{id}}&limit=50&access_token={tok}"
    out = []
    while url and len(out) < limit:
        data = req("GET", url).json()
        for c in data.get("data", []):
            if c.get("username") == me:
                continue
            out.append({"platform": NAME, "comment_id": c["id"], "author": "@" + c.get("username", "unknown"),
                        "text": c.get("text", ""), "likes": c.get("like_count", 0),
                        "replies": len((c.get("replies") or {}).get("data", [])), "published": c.get("timestamp")})
        url = data.get("paging", {}).get("next")
    return out


def refresh_token():
    tok = _e()["IG_ACCESS_TOKEN"]
    return req("GET", f"https://graph.instagram.com/refresh_access_token?grant_type=ig_refresh_token&access_token={tok}").json()
