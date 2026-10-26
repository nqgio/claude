"""Amazon buying accounts and auto-buy rotation."""
from __future__ import annotations

import shutil
from datetime import datetime, timezone

from .. import activity, config
from .. import settings_store as st
from ..db import session_scope
from ..models import AmazonAccount, Order, utcnow


def _today_start_utc() -> datetime:
    start = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
    return start.astimezone(timezone.utc).replace(tzinfo=None)


def usage_today() -> dict[int, dict]:
    """{account_id: {"orders": n, "spend": $}} for purchases made today (auto or entered manually)."""
    out: dict[int, dict] = {}
    start = _today_start_utc()
    with session_scope() as s:
        rows = s.query(Order).filter(Order.amazon_account_id.isnot(None),
                                     (Order.auto_buy_at >= start) | (Order.purchased_at >= start)).all()
        for o in rows:
            u = out.setdefault(o.amazon_account_id, {"orders": 0, "spend": 0.0})
            u["orders"] += 1
            u["spend"] = round(u["spend"] + (o.amazon_cost or o.amazon_cost_est or 0.0), 2)
    return out


def ensure_legacy_account() -> None:
    """Earlier versions had one login profile; keep it as 'Amazon account 1'."""
    legacy = config.LEGACY_AMAZON_PROFILE_DIR
    with session_scope() as s:
        if s.query(AmazonAccount).count() or not legacy.exists():
            return
        s.add(AmazonAccount(name="Amazon account 1", profile_dir=str(legacy)))
    activity.info("amazon", "Your existing Amazon login was kept as 'Amazon account 1'")


def as_dict(a: AmazonAccount, usage: dict | None = None) -> dict:
    u = (usage or {}).get(a.id, {"orders": 0, "spend": 0.0})
    return {"id": a.id, "name": a.name, "enabled": a.enabled, "buys_orders": a.buys_orders,
            "max_orders_per_day": a.max_orders_per_day, "max_spend_per_day": a.max_spend_per_day,
            "logged_in": a.logged_in, "checked_at": a.checked_at.isoformat() + "Z" if a.checked_at else None,
            "last_used_at": a.last_used_at.isoformat() + "Z" if a.last_used_at else None,
            "orders_today": u["orders"], "spend_today": u["spend"]}


def list_accounts() -> list[dict]:
    usage = usage_today()
    with session_scope() as s:
        return [as_dict(a, usage) for a in s.query(AmazonAccount).order_by(AmazonAccount.id)]


def create(name: str) -> dict:
    name = name.strip() or "Amazon account"
    with session_scope() as s:
        a = AmazonAccount(name=name[:80], profile_dir="")
        s.add(a)
        s.flush()
        a.profile_dir = str(config.AMAZON_ACCOUNTS_DIR / f"account-{a.id}")
        d = as_dict(a)
    activity.info("amazon", f"Added Amazon account '{name}'. Log in to it from Settings.")
    return d


EDITABLE = {"name", "enabled", "buys_orders", "max_orders_per_day", "max_spend_per_day"}


def update(account_id: int, values: dict) -> dict:
    with session_scope() as s:
        a = s.get(AmazonAccount, account_id)
        if a is None:
            raise KeyError(account_id)
        for k, v in values.items():
            if k not in EDITABLE:
                continue
            if k in ("max_orders_per_day", "max_spend_per_day"):
                v = None if v in ("", None) else (int(v) if k == "max_orders_per_day" else float(v))
                if v is not None and v < 0:
                    raise ValueError("limits can't be negative")
            elif k == "name":
                v = str(v).strip()[:80] or a.name
            else:
                v = bool(v)
            setattr(a, k, v)
        return as_dict(a, usage_today())


def delete(account_id: int, remove_login: bool = True) -> None:
    with session_scope() as s:
        a = s.get(AmazonAccount, account_id)
        if a is None:
            return
        name, profile = a.name, a.profile_dir
        s.delete(a)
    if remove_login and profile and str(config.DATA_DIR) in profile:
        shutil.rmtree(profile, ignore_errors=True)
    activity.info("amazon", f"Removed Amazon account '{name}'")


def get(account_id: int | None) -> AmazonAccount | None:
    if account_id is None:
        return None
    with session_scope() as s:
        return s.get(AmazonAccount, account_id)


def default_for_tracking() -> AmazonAccount | None:
    """Fallback for orders bought before accounts existed: the first enabled account."""
    with session_scope() as s:
        return s.query(AmazonAccount).filter_by(enabled=True).order_by(AmazonAccount.id).first()


def pick_next(amount: float | None = None) -> tuple[AmazonAccount | None, str]:
    """Next account to buy with, per the rotation setting and each account's daily limits.
    Returns (account, reason-if-none)."""
    usage = usage_today()
    with session_scope() as s:
        accounts = s.query(AmazonAccount).filter_by(enabled=True, buys_orders=True).order_by(AmazonAccount.id).all()
    if not accounts:
        return None, "no Amazon account is set up to buy orders (Settings → Amazon accounts)"
    eligible, blocked = [], []
    for a in accounts:
        u = usage.get(a.id, {"orders": 0, "spend": 0.0})
        if a.logged_in is False:
            blocked.append(f"{a.name}: not logged in")
        elif a.max_orders_per_day is not None and u["orders"] >= a.max_orders_per_day:
            blocked.append(f"{a.name}: {u['orders']}/{a.max_orders_per_day} orders today")
        elif a.max_spend_per_day is not None and u["spend"] + (amount or 0) > a.max_spend_per_day:
            blocked.append(f"{a.name}: ${u['spend']:.2f} of ${a.max_spend_per_day:.2f} spent today")
        else:
            eligible.append(a)
    if not eligible:
        return None, "every Amazon account is at a limit (" + "; ".join(blocked) + ")"
    oldest = lambda a: a.last_used_at or datetime.min  # noqa: E731
    if st.get("amazon_rotation") == "least_used_today":
        eligible.sort(key=lambda a: (usage.get(a.id, {"orders": 0})["orders"], oldest(a), a.id))
    else:  # take turns
        eligible.sort(key=lambda a: (oldest(a), a.id))
    return eligible[0], ""


def mark_used(account_id: int) -> None:
    with session_scope() as s:
        a = s.get(AmazonAccount, account_id)
        if a:
            a.last_used_at = utcnow()


def set_login_state(account_id: int, logged_in: bool) -> None:
    with session_scope() as s:
        a = s.get(AmazonAccount, account_id)
        if a:
            a.logged_in, a.checked_at = logged_in, utcnow()
