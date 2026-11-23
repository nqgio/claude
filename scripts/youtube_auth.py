#!/usr/bin/env python3
"""ONE-TIME, run on YOUR computer (needs a browser):
    pip install google-auth-oauthlib
    python3 youtube_auth.py path/to/client_secret.json
Sign in with the Google account that owns the channel. It prints the three values to save as secrets.
"""
import json, sys
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.force-ssl"]
flow = InstalledAppFlow.from_client_secrets_file(sys.argv[1], SCOPES)
creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
cfg = json.load(open(sys.argv[1]))
cfg = cfg.get("installed") or cfg.get("web")
print("\nSave these as secrets:\n")
print("YT_CLIENT_ID=" + cfg["client_id"])
print("YT_CLIENT_SECRET=" + cfg["client_secret"])
print("YT_REFRESH_TOKEN=" + creds.refresh_token)
