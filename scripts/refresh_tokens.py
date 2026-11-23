#!/usr/bin/env python3
"""Instagram long-lived tokens last 60 days. Run this (any time after the token is 24h old)
to get a fresh one, then replace IG_ACCESS_TOKEN in your environment's secrets with the printed value."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from platforms import instagram  # noqa: E402

r = instagram.refresh_token()
print(f"New IG_ACCESS_TOKEN (expires in {r['expires_in'] // 86400} days):\n{r['access_token']}")
