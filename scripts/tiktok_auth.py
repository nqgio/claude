#!/usr/bin/env python3
"""ONE-TIME TikTok sign-in (run anywhere with a browser):
    python3 tiktok_auth.py <client_key> <client_secret> <redirect_uri>
1. Open the printed URL, approve.
2. You get redirected to <redirect_uri>?code=...  (the page itself can 404, that's fine)
3. Paste the whole redirected URL back here. It prints TIKTOK_REFRESH_TOKEN (valid 1 year).
"""
import secrets, sys, urllib.parse
import requests

key, secret, redirect = sys.argv[1:4]
state = secrets.token_urlsafe(8)
url = "https://www.tiktok.com/v2/auth/authorize/?" + urllib.parse.urlencode({
    "client_key": key, "scope": "user.info.basic,video.upload,video.publish", "response_type": "code",
    "redirect_uri": redirect, "state": state})
print("Open this URL and approve:\n\n" + url + "\n")
back = input("Paste the full URL you were redirected to: ").strip()
code = urllib.parse.parse_qs(urllib.parse.urlparse(back).query)["code"][0]
r = requests.post("https://open.tiktokapis.com/v2/oauth/token/", headers={"Content-Type": "application/x-www-form-urlencoded"},
                  data={"client_key": key, "client_secret": secret, "code": code, "grant_type": "authorization_code", "redirect_uri": redirect}).json()
if "refresh_token" not in r:
    sys.exit(f"Failed: {r}")
print("\nSave these as secrets:\n")
print("TIKTOK_CLIENT_KEY=" + key)
print("TIKTOK_CLIENT_SECRET=" + secret)
print("TIKTOK_REFRESH_TOKEN=" + r["refresh_token"])
