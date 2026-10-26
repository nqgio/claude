"""Activity log: every action the app takes is written here (and to the console)."""
from __future__ import annotations

import logging

from .db import session_scope
from .models import ActivityLog

log = logging.getLogger("app")

# Categories used across the app (shown as filters in the dashboard).
CATEGORIES = ["found", "skipped", "queued", "listed", "price", "stock", "ended", "order", "tracking",
              "fees", "amazon", "ebay", "blocklist", "settings", "system", "error"]


def record(category: str, message: str, level: str = "info", *, asin: str | None = None,
           listing_id: int | None = None, order_id: int | None = None, details: dict | None = None) -> None:
    """Write one activity row in its own transaction so it survives callers' rollbacks."""
    getattr(log, "warning" if level == "warning" else "error" if level == "error" else "info")(
        "[%s] %s", category, message)
    try:
        with session_scope() as s:
            s.add(ActivityLog(category=category, message=message[:4000], level=level, asin=asin,
                              listing_id=listing_id, order_id=order_id, details=details))
    except Exception:  # logging must never break a job
        log.exception("failed to write activity log")


def info(category: str, message: str, **kw) -> None:
    record(category, message, "info", **kw)


def warning(category: str, message: str, **kw) -> None:
    record(category, message, "warning", **kw)


def error(category: str, message: str, **kw) -> None:
    record(category, message, "error", **kw)
