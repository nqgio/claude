"""APScheduler wiring. Every job is wrapped so one failure is logged and never
stops the scheduler; jobs never overlap with themselves."""
from __future__ import annotations

import threading
import traceback
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from .. import activity
from .. import settings_store as st
from ..ebay.client import EbayNotConnected
from ..providers.base import SourceBlocked, SourcePaused

_scheduler: BackgroundScheduler | None = None
_running: set[str] = set()
_running_lock = threading.Lock()
JOB_LABELS = {
    "discovery": "Build today's queue", "posting_tick": "Post due listings", "refresh": "Price & stock refresh",
    "orders": "Sync eBay orders", "fees": "Sync actual fees (Finances API)", "traffic": "Sync views & watchers",
    "tracking": "Check Amazon tracking", "returns": "Sync returns", "maintenance": "Housekeeping",
}


def _job_fn(name: str):
    from . import orders, queue, refresh

    return {
        "discovery": lambda: queue.build_queue("schedule"),
        "posting_tick": queue.posting_tick,
        "refresh": refresh.run,
        "orders": orders.sync_orders,
        "fees": orders.sync_fees,
        "traffic": orders.sync_traffic,
        "tracking": orders.check_tracking,
        "returns": orders.sync_returns,
        "maintenance": _maintenance,
    }[name]


def safe(name: str):
    def run():
        with _running_lock:
            if name in _running:
                return
            _running.add(name)
        try:
            _job_fn(name)()
        except EbayNotConnected:
            pass  # expected until eBay is connected; status shows on the dashboard
        except (SourceBlocked, SourcePaused) as exc:
            activity.warning("amazon", f"{JOB_LABELS[name]} skipped: {exc}")
        except Exception as exc:
            activity.error("system", f"Job '{JOB_LABELS[name]}' failed: {exc}",
                           details={"traceback": traceback.format_exc()[-4000:]})
        finally:
            with _running_lock:
                _running.discard(name)
    return run


def _maintenance():
    from ..db import session_scope
    from ..models import ActivityLog, utcnow

    with session_scope() as s:
        n = s.query(ActivityLog).filter(ActivityLog.ts < utcnow() - timedelta(days=180)).delete()
    if n:
        activity.info("system", f"Pruned {n} activity rows older than 180 days")


def _hm(v: str) -> tuple[int, int]:
    h, m = v.split(":")
    return int(h), int(m)


def configure() -> None:
    """(Re)create all jobs from current settings."""
    sch = _scheduler
    if sch is None:
        return
    s = st.all_settings()
    dh, dm = _hm(s["discovery_time"])
    jobs = {
        "discovery": CronTrigger(hour=dh, minute=dm),
        "posting_tick": IntervalTrigger(minutes=1),
        "orders": IntervalTrigger(minutes=int(s["orders_sync_minutes"])),
        "fees": IntervalTrigger(hours=1),
        "traffic": IntervalTrigger(hours=6),
        "tracking": IntervalTrigger(hours=int(s["tracking_check_hours"])),
        "returns": IntervalTrigger(hours=3),
        "maintenance": CronTrigger(hour=4, minute=17),
    }
    rh, rm = _hm(s["refresh_time"])
    if not s["refresh_enabled"]:
        if sch.get_job("refresh"):
            sch.remove_job("refresh")
    elif s["refresh_mode"] == "every_n_hours":
        jobs["refresh"] = IntervalTrigger(hours=int(s["refresh_every_hours"]))
    elif s["refresh_mode"] == "weekly":
        jobs["refresh"] = CronTrigger(day_of_week=s["refresh_day"], hour=rh, minute=rm)
    else:
        jobs["refresh"] = CronTrigger(hour=rh, minute=rm)
    for name, trig in jobs.items():
        sch.add_job(safe(name), trig, id=name, name=JOB_LABELS[name], replace_existing=True,
                    max_instances=1, coalesce=True, misfire_grace_time=3600)


def start() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = BackgroundScheduler(job_defaults={"coalesce": True, "max_instances": 1})
    _scheduler.start()
    configure()
    activity.info("system", "Scheduler started")


def shutdown() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None


def run_now(name: str) -> bool:
    """Run a job immediately in the background (no-op if it's already running)."""
    if name not in JOB_LABELS:
        raise KeyError(name)
    with _running_lock:
        if name in _running:
            return False
    if _scheduler is None:
        threading.Thread(target=safe(name), daemon=True).start()
    else:
        _scheduler.add_job(safe(name), id=f"{name}_now_{datetime.now().timestamp()}", name=JOB_LABELS[name] + " (manual)")
    return True


def run_task(label: str, fn, *args) -> None:
    """Run an ad-hoc function in the background with the same error protection."""
    def wrapped():
        try:
            fn(*args)
        except (SourceBlocked, SourcePaused) as exc:
            activity.warning("amazon", f"{label}: {exc}")
        except Exception as exc:
            activity.error("system", f"{label} failed: {exc}", details={"traceback": traceback.format_exc()[-4000:]})

    if _scheduler is None:
        threading.Thread(target=wrapped, daemon=True).start()
    else:
        _scheduler.add_job(wrapped, id=f"task_{datetime.now().timestamp()}", name=label)


def status() -> list[dict]:
    if _scheduler is None:
        return []
    out = []
    for name, label in JOB_LABELS.items():
        job = _scheduler.get_job(name)
        if name == "refresh" and job is None:
            label += " (auto refresh off)"
        out.append({"name": name, "label": label, "running": name in _running,
                    "next_run": job.next_run_time.isoformat() if job and job.next_run_time else None})
    return out
