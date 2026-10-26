"""Start the app: the dashboard/API on 127.0.0.1:APP_PORT (default 8000) and the
eBay account-deletion webhook on APP_NOTIFY_PORT (default 8001).

    python run.py            (add --open to open the dashboard in your browser once it's up)
"""
from __future__ import annotations

import sys
import threading
import webbrowser

import uvicorn

from app import config
from app.ebay.notifications import build_app


def main() -> None:
    notify = uvicorn.Server(uvicorn.Config(build_app(), host="127.0.0.1", port=config.NOTIFY_PORT, log_level="warning"))
    threading.Thread(target=notify.run, daemon=True, name="notify-server").start()
    if "--open" in sys.argv:
        threading.Timer(3.0, webbrowser.open, [f"http://localhost:{config.PORT}"]).start()
    uvicorn.run("app.main:app", host=config.HOST, port=config.PORT, log_level="info")


if __name__ == "__main__":
    main()
