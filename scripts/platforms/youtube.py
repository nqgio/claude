"""YouTube Data API v3: upload Short, post/reply comments, read comments ranked by likes.
Env: YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN  (get the refresh token with scripts/youtube_auth.py)
"""
import json, os
from .common import env, req

API = "https://www.googleapis.com/youtube/v3"
NAME = "youtube"


def configured():
    return env("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN") is not None


def _token():
    e = env("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN")
    r = req("POST", "https://oauth2.googleapis.com/token", data={
        "client_id": e["YT_CLIENT_ID"], "client_secret": e["YT_CLIENT_SECRET"],
        "refresh_token": e["YT_REFRESH_TOKEN"], "grant_type": "refresh_token"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def my_channel_id(h=None):
    h = h or _token()
    return req("GET", f"{API}/channels?part=id&mine=true", headers=h).json()["items"][0]["id"]


def upload(video_path, title, description, tags):
    h = _token()
    meta = {
        "snippet": {"title": title[:100], "description": description, "tags": tags, "categoryId": "23"},  # 23 = Comedy
        "status": {"privacyStatus": os.environ.get("YT_PRIVACY", "public"), "selfDeclaredMadeForKids": False},
    }
    size = os.path.getsize(video_path)
    r = req("POST", "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
            headers={**h, "Content-Type": "application/json; charset=UTF-8", "X-Upload-Content-Type": "video/mp4",
                     "X-Upload-Content-Length": str(size)}, data=json.dumps(meta))
    with open(video_path, "rb") as f:
        r = req("PUT", r.headers["Location"], headers={**h, "Content-Type": "video/mp4"}, data=f, timeout=600)
    vid = r.json()["id"]
    return {"id": vid, "url": f"https://youtube.com/shorts/{vid}"}


def comment(video_id, text):
    h = _token()
    body = {"snippet": {"videoId": video_id, "topLevelComment": {"snippet": {"textOriginal": text}}}}
    return req("POST", f"{API}/commentThreads?part=snippet", headers={**h, "Content-Type": "application/json"}, data=json.dumps(body)).json()["id"]


def reply(comment_id, text):
    h = _token()
    body = {"snippet": {"parentId": comment_id, "textOriginal": text}}
    return req("POST", f"{API}/comments?part=snippet", headers={**h, "Content-Type": "application/json"}, data=json.dumps(body)).json()["id"]


def fetch_comments(video_id, limit=300):
    h = _token()
    me = my_channel_id(h)
    out, page = [], None
    while len(out) < limit:
        url = f"{API}/commentThreads?part=snippet&videoId={video_id}&order=relevance&maxResults=100&textFormat=plainText"
        if page:
            url += f"&pageToken={page}"
        data = req("GET", url, headers=h).json()
        for it in data.get("items", []):
            s = it["snippet"]["topLevelComment"]["snippet"]
            if s.get("authorChannelId", {}).get("value") == me:
                continue
            out.append({"platform": NAME, "comment_id": it["snippet"]["topLevelComment"]["id"],
                        "author": s["authorDisplayName"] if s["authorDisplayName"].startswith("@") else "@" + s["authorDisplayName"],
                        "text": s["textDisplay"], "likes": s.get("likeCount", 0),
                        "replies": it["snippet"].get("totalReplyCount", 0), "published": s["publishedAt"]})
        page = data.get("nextPageToken")
        if not page:
            break
    return out
