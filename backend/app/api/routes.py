"""Dashboard JSON API (served on localhost only)."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from .. import activity, blocklist, config
from .. import settings_store as st
from ..db import session_scope
from ..ebay import api as ebay
from ..ebay import client as ebay_client
from ..ebay.client import EbayError
from ..models import ActivityLog, BlocklistEntry, Listing, Order, PriceHistory, Product, QueueItem
from ..pricing import calculate
from ..providers import get_provider
from ..providers.amazon_playwright import paused_until
from ..services import accounts, listing_ops, metrics, orders, queue, refresh, scheduler
from ..services.evaluate import pricing_params

router = APIRouter(prefix="/api")


def ser(v: Any) -> Any:
    if isinstance(v, datetime):
        return v.isoformat() + ("Z" if v.tzinfo is None else "")
    if isinstance(v, date):
        return v.isoformat()
    return v


def row(obj, exclude: tuple = ()) -> dict:
    return {c.name: ser(getattr(obj, c.name)) for c in obj.__table__.columns if c.name not in exclude}


def _err(exc: Exception, code: int = 400):
    raise HTTPException(code, str(exc))


# ---- status / settings --------------------------------------------------------------------

@router.get("/status")
def status():
    env = st.get("ebay_environment")
    k = ebay_client.keys(env)
    until = paused_until()
    from datetime import timezone

    paused = bool(until and until > datetime.now(timezone.utc))
    return {
        "dry_run": st.get("dry_run"), "environment": env, "checkout_mode": st.get("checkout_mode"),
        "kill_switch": st.get("auto_buy_kill_switch"), "product_source": st.get("product_source"),
        "ebay": {"keys_present": bool(k["app_id"] and k["cert_id"]), "runame_present": bool(k["runame"]),
                 "connected": bool(k["refresh_token"]),
                 "refresh_token_expires": (st.get("ebay_refresh_token_expires") or {}).get(env)},
        "amazon": {"status": "paused" if paused else "ok", "paused_until": until.isoformat() if paused else None,
                   "reason": st.get("amazon_pause_reason") if paused else "",
                   "accounts": len(accounts.list_accounts()),
                   "accounts_logged_in": sum(1 for a in accounts.list_accounts() if a["logged_in"])},
        "ai_key_present": bool(config.env("ANTHROPIC_API_KEY")),
        "deletion_endpoint_configured": bool(config.env("EBAY_VERIFICATION_TOKEN") and config.env("EBAY_DELETION_ENDPOINT_URL")),
        "jobs": scheduler.status(),
    }


@router.get("/settings")
def get_settings():
    return {"values": st.all_settings(), "schema": st.schema()}


@router.put("/settings")
def put_settings(values: dict):
    old = st.all_settings()
    try:
        changed = st.update(values)
    except st.SettingsError as exc:
        _err(exc)
    diffs = {k: v for k, v in changed.items() if old.get(k) != v}
    if diffs:
        activity.info("settings", "Settings changed: " + ", ".join(f"{k}={v!r}" for k, v in diffs.items()))
        scheduler.configure()
    return {"values": st.all_settings(), "changed": list(diffs)}


class PricePreview(BaseModel):
    amazon_price: float


@router.post("/pricing/preview")
def pricing_preview(body: PricePreview):
    try:
        return calculate(body.amazon_price, pricing_params())
    except ValueError as exc:
        _err(exc)


# ---- API keys (stored in .env) ---------------------------------------------------------------------

def _mask(name: str, value: str) -> str:
    if not value:
        return ""
    if config.EDITABLE_KEYS[name]:
        return "•" * 8 + value[-4:]
    return value


@router.get("/keys")
def get_keys():
    return {"file": str(config.ENV_FILE), "keys": {k: {"set": bool(config.env(k)), "display": _mask(k, config.env(k)),
                                                     "secret": secret} for k, secret in config.EDITABLE_KEYS.items()}}


@router.put("/keys")
def put_keys(values: dict[str, str]):
    """Save keys into .env. Blank values are ignored (so an empty box never wipes a saved key)."""
    import re

    changed = []
    for name, value in values.items():
        if name not in config.EDITABLE_KEYS:
            raise HTTPException(400, f"unknown key {name}")
        value = (value or "").strip().strip('"').strip("'")
        if not value:
            continue
        if any(c in value for c in "\r\n"):
            raise HTTPException(400, f"{name} can't contain line breaks")
        if name == "EBAY_VERIFICATION_TOKEN" and not re.fullmatch(r"[A-Za-z0-9_-]{32,80}", value):
            raise HTTPException(400, "Verification token must be 32–80 letters, numbers, _ or -")
        if name == "EBAY_DELETION_ENDPOINT_URL" and not value.startswith("https://"):
            raise HTTPException(400, "Deletion endpoint URL must start with https://")
        config.save_env_value(name, value)
        changed.append(name)
    if changed:
        with ebay_client._token_lock:
            ebay_client._tokens.clear()  # new keys → fetch fresh tokens
        activity.info("settings", "API keys updated: " + ", ".join(changed))
    return {**get_keys(), "changed": changed}


# ---- eBay connection ----------------------------------------------------------------------------

@router.get("/ebay/connect-url")
def ebay_connect_url():
    try:
        return {"url": ebay_client.consent_url()}
    except EbayError as exc:
        _err(exc)


class CodeBody(BaseModel):
    value: str


@router.post("/ebay/exchange")
def ebay_exchange(body: CodeBody):
    try:
        code, state = ebay_client.extract_code(body.value)
        return ebay_client.exchange_code(code, state=state)
    except EbayError as exc:
        _err(exc)


@router.get("/ebay/oauth/callback", response_class=HTMLResponse)
def ebay_callback(code: str | None = None, state: str | None = None, error: str | None = None):
    if error or not code:
        return HTMLResponse(f"<h3>eBay connection failed: {error or 'no code'}</h3>", 400)
    try:
        ebay_client.exchange_code(code, state=state)
    except EbayError as exc:
        return HTMLResponse(f"<h3>eBay connection failed</h3><p>{exc}</p>", 400)
    return HTMLResponse("<h3>eBay connected.</h3><p>You can close this tab and return to the dashboard.</p>"
                        "<script>setTimeout(()=>location.href='/settings',1500)</script>")


@router.post("/ebay/disconnect")
def ebay_disconnect():
    ebay_client.disconnect()
    return {"ok": True}


@router.get("/ebay/policies")
def ebay_policies():
    try:
        return ebay.get_policies()
    except EbayError as exc:
        _err(exc)


@router.post("/ebay/opt-in-policies")
def ebay_opt_in():
    try:
        ebay.opt_in_business_policies()
        return {"ok": True}
    except EbayError as exc:
        _err(exc)


# ---- Amazon ------------------------------------------------------------------------------------------

# ---- Amazon accounts -------------------------------------------------------------------------------

@router.get("/amazon/accounts")
def list_amazon_accounts():
    nxt, why = accounts.pick_next()
    return {"accounts": accounts.list_accounts(), "next_account_id": nxt.id if nxt else None, "next_reason": why,
            "rotation": st.get("amazon_rotation")}


class AccountBody(BaseModel):
    name: str = ""


@router.post("/amazon/accounts")
def add_amazon_account(body: AccountBody):
    return accounts.create(body.name)


@router.patch("/amazon/accounts/{aid}")
def edit_amazon_account(aid: int, values: dict):
    try:
        return accounts.update(aid, values)
    except KeyError:
        raise HTTPException(404, "account not found")
    except (TypeError, ValueError) as exc:
        _err(exc)


@router.delete("/amazon/accounts/{aid}")
def remove_amazon_account(aid: int):
    accounts.delete(aid)
    return {"ok": True}


@router.post("/amazon/accounts/{aid}/login")
def login_amazon_account(aid: int):
    a = accounts.get(aid)
    if not a:
        raise HTTPException(404, "account not found")
    get_provider("amazon_playwright").open_login_browser(a.profile_dir, a.name)
    return {"message": f"A browser window opened on this PC for {a.name}. Log in, tick 'Keep me signed in', then close it."}


@router.post("/amazon/accounts/{aid}/check")
def check_amazon_account(aid: int):
    a = accounts.get(aid)
    if not a:
        raise HTTPException(404, "account not found")

    def run():
        ok = get_provider("amazon_playwright").check_login(a.profile_dir)
        accounts.set_login_state(aid, ok)
        (activity.info if ok else activity.warning)("amazon", f"{a.name}: {'logged in' if ok else 'NOT logged in — use Log in'}")

    scheduler.run_task(f"Check login for {a.name}", run)
    return {"message": f"Checking {a.name}… the status updates in a few seconds."}


@router.post("/amazon/resume")
def amazon_resume():
    st.set_internal("amazon_paused_until", None)
    st.set_internal("amazon_pause_reason", "")
    activity.info("amazon", "Amazon jobs resumed manually from the dashboard")
    return {"ok": True}


# ---- metrics -----------------------------------------------------------------------------------------------

@router.get("/metrics")
def get_metrics(range: str = "30d", start: str | None = None, end: str | None = None):
    return metrics.overview(range, start, end)


@router.get("/metrics/best")
def get_best():
    return metrics.best_and_worst()


# ---- listings ------------------------------------------------------------------------------------------------

LIST_EXCLUDE = ("description_html", "breakdown", "current_breakdown", "aspects")


@router.get("/listings")
def list_listings(status: str | None = None, include_dry_run: bool = True, q: str | None = None):
    stats = metrics.listing_stats()
    with session_scope() as s:
        qry = s.query(Listing)
        if status:
            qry = qry.filter(Listing.status == status)
        if not include_dry_run:
            qry = qry.filter(Listing.dry_run.is_(False))
        if q:
            qry = qry.filter(Listing.title.ilike(f"%{q}%") | Listing.asin.ilike(f"%{q}%"))
        out = []
        for l in qry.order_by(Listing.created_at.desc()).limit(2000):
            d = row(l, LIST_EXCLUDE)
            d["image"] = (l.image_urls or [""])[0]
            d.update({f"sold_{k}": v for k, v in stats.get(l.id, {"units": 0, "profit": 0.0, "orders": 0}).items()})
            out.append(d)
        return out


def _ebay_url(l: Listing) -> str | None:
    if not l.ebay_listing_id:
        return None
    host = "sandbox.ebay.com" if l.environment == "sandbox" else "ebay.com"
    return f"https://www.{host}/itm/{l.ebay_listing_id}"


@router.get("/listings/{lid}")
def get_listing(lid: int):
    with session_scope() as s:
        l = s.get(Listing, lid)
        if not l:
            raise HTTPException(404, "listing not found")
        d = row(l)
        d["ebay_url"] = _ebay_url(l)
        d["history"] = [row(h) for h in s.query(PriceHistory).filter_by(listing_id=lid).order_by(PriceHistory.ts)]
        d["orders"] = [{**row(o, ("raw",)), "financials": orders.financials(o)}
                       for o in s.query(Order).filter_by(listing_id=lid).order_by(Order.created_at.desc())]
        p = s.get(Product, l.asin)
        d["product"] = row(p) if p else None
        return d


@router.post("/listings/{lid}/end")
def end_listing(lid: int):
    try:
        done = listing_ops.end_listing(lid, "ended manually from dashboard")
    except EbayError as exc:
        _err(exc)
    return {"ok": done, "message": None if done else "dry-run is on — logged what would happen"}


@router.post("/listings/{lid}/refresh")
def refresh_listing(lid: int):
    scheduler.run_task(f"Refresh listing #{lid}", refresh.run, [lid], True)
    return {"ok": True, "message": "refresh started"}


@router.post("/listings/{lid}/unflag")
def unflag_listing(lid: int):
    with session_scope() as s:
        l = s.get(Listing, lid)
        l.flagged, l.flag_reason = False, ""
    return {"ok": True}


@router.post("/refresh/run")
def refresh_now():
    return {"started": scheduler.run_now("refresh")}


# ---- queue -----------------------------------------------------------------------------------------------------

@router.get("/queue")
def get_queue(day: str | None = None):
    d = date.fromisoformat(day) if day else queue.local_now().date()
    with session_scope() as s:
        items = s.query(QueueItem).filter(QueueItem.queue_date == d).order_by(
            QueueItem.scheduled_at.is_(None), QueueItem.scheduled_at, QueueItem.id).all()
        return {"date": d.isoformat(), "items": [row(i) for i in items],
                "window": [st.get("posting_window_start"), st.get("posting_window_end")],
                "listings_per_day": st.get("listings_per_day"), "posted_today": queue.posted_today_count()}


class AddAsin(BaseModel):
    asin: str
    force: bool = False


@router.post("/queue")
def add_to_queue(body: AddAsin):
    scheduler.run_task(f"Add ASIN {body.asin}", _manual_add, body.asin, body.force)
    return {"ok": True, "message": f"Checking {body.asin.upper()} on Amazon — it will appear in the queue (or the "
                                   "activity log will say why not)."}


def _manual_add(asin, force):
    res = queue.manual_add(asin, force)
    if not res["ok"]:
        activity.warning("queued", f"Could not add {asin.upper()}: {res['message']}", asin=asin.upper())


@router.delete("/queue/{qid}")
def remove_queue_item(qid: int):
    with session_scope() as s:
        item = s.get(QueueItem, qid)
        if not item:
            raise HTTPException(404, "not found")
        if item.status in ("posting", "posted"):
            raise HTTPException(400, f"item is {item.status}")
        item.status, item.message = "removed", "removed from dashboard"
        asin = item.asin
    activity.info("queued", f"Removed {asin} from the queue", asin=asin)
    queue.schedule_today()
    return {"ok": True}


@router.post("/queue/{qid}/post-now")
def post_now(qid: int):
    scheduler.run_task(f"Post queue item #{qid}", queue.post_item, qid)
    return {"ok": True}


@router.post("/queue/build")
def build_queue():
    return {"started": scheduler.run_now("discovery")}


# ---- orders --------------------------------------------------------------------------------------------------------

@router.get("/orders")
def list_orders(status: str | None = None, flag: str | None = None):
    with session_scope() as s:
        q = s.query(Order)
        if status:
            q = q.filter(Order.status == status)
        if flag:
            q = q.filter(Order.flag == flag)
        return [{**row(o, ("raw",)), "financials": orders.financials(o)} for o in q.order_by(Order.created_at.desc()).limit(2000)]


@router.get("/orders/{oid}")
def get_order(oid: int):
    with session_scope() as s:
        o = s.get(Order, oid)
        if not o:
            raise HTTPException(404, "order not found")
        return {**row(o, ("raw",)), "financials": orders.financials(o)}


class PurchaseBody(BaseModel):
    amazon_order_id: str = ""
    amazon_cost: float | None = None
    amazon_account_id: int | None = None


@router.post("/orders/{oid}/purchase")
def order_purchased(oid: int, body: PurchaseBody):
    orders.mark_purchased(oid, body.amazon_order_id, body.amazon_cost, " — entered on dashboard",
                          amazon_account_id=body.amazon_account_id)
    return get_order(oid)


class TrackingBody(BaseModel):
    tracking_number: str
    carrier: str = ""


@router.post("/orders/{oid}/tracking")
def order_tracking(oid: int, body: TrackingBody):
    res = orders.set_tracking(oid, body.tracking_number, body.carrier)
    return {**res, "order": get_order(oid)}


class AmountBody(BaseModel):
    amount: float


@router.post("/orders/{oid}/amazon-refund")
def order_amazon_refund(oid: int, body: AmountBody):
    with session_scope() as s:
        o = s.get(Order, oid)
        o.amazon_refund = round(body.amount, 2)
    activity.info("order", f"Order #{oid}: Amazon refund received ${body.amount:.2f}", order_id=oid)
    return get_order(oid)


class StatusBody(BaseModel):
    status: str
    note: str = ""


@router.post("/orders/{oid}/status")
def order_status(oid: int, body: StatusBody):
    allowed = orders.STATUS_ORDER + sorted(orders.TERMINAL)
    if body.status not in allowed:
        raise HTTPException(400, f"status must be one of {allowed}")
    with session_scope() as s:
        o = s.get(Order, oid)
        o.status = body.status
        if body.note:
            o.notes = (o.notes + "\n" + body.note).strip()
    activity.info("order", f"Order #{oid} status set to {body.status} from dashboard", order_id=oid)
    return get_order(oid)


@router.post("/orders/{oid}/clear-flag")
def order_clear_flag(oid: int):
    with session_scope() as s:
        o = s.get(Order, oid)
        o.flag, o.flag_reason = "", ""
    return get_order(oid)


@router.post("/orders/{oid}/auto-buy")
def order_auto_buy(oid: int):
    scheduler.run_task(f"Auto-buy order #{oid}", orders.auto_buy, oid)
    return {"ok": True, "message": "auto-buy started — watch the activity log"}


@router.post("/orders/sync")
def orders_sync():
    return {"started": scheduler.run_now("orders")}


# ---- activity ----------------------------------------------------------------------------------------------------------

@router.get("/activity")
def get_activity(category: str | None = None, level: str | None = None, q: str | None = None,
                 limit: int = Query(200, le=2000), offset: int = 0):
    with session_scope() as s:
        qry = s.query(ActivityLog)
        if category:
            qry = qry.filter(ActivityLog.category == category)
        if level:
            qry = qry.filter(ActivityLog.level == level)
        if q:
            qry = qry.filter(ActivityLog.message.ilike(f"%{q}%"))
        total = qry.count()
        rows = qry.order_by(ActivityLog.id.desc()).offset(offset).limit(limit).all()
        return {"total": total, "items": [row(r) for r in rows], "categories": activity.CATEGORIES}


# ---- blocklist -----------------------------------------------------------------------------------------------------------

@router.get("/blocklist")
def get_blocklist():
    with session_scope() as s:
        return [row(e) for e in s.query(BlocklistEntry).order_by(BlocklistEntry.kind, BlocklistEntry.term)]


class TermBody(BaseModel):
    term: str
    kind: str = "brand"


@router.post("/blocklist")
def add_block(body: TermBody):
    n = blocklist.add_terms([(body.term, body.kind)])
    if n:
        activity.info("blocklist", f"Added {body.kind} '{body.term}' to blocklist")
    return {"added": n}


@router.delete("/blocklist/{eid}")
def delete_block(eid: int):
    with session_scope() as s:
        e = s.get(BlocklistEntry, eid)
        if e:
            activity.info("blocklist", f"Removed {e.kind} '{e.term}' from blocklist")
            s.delete(e)
    return {"ok": True}


class CsvBody(BaseModel):
    csv: str


@router.post("/blocklist/import")
def import_block(body: CsvBody):
    n = blocklist.add_terms(blocklist.parse_csv(body.csv), source="import")
    activity.info("blocklist", f"Imported {n} blocklist term(s) from CSV")
    return {"added": n}


class ScanBody(BaseModel):
    action: str | None = None


@router.post("/blocklist/scan")
def scan_block(body: ScanBody):
    if body.action not in (None, "flag", "end"):
        raise HTTPException(400, "action must be flag or end")
    try:
        return refresh.scan_blocklist(body.action)
    except EbayError as exc:
        _err(exc)


# ---- jobs ----------------------------------------------------------------------------------------------------------------

@router.post("/jobs/{name}/run")
def run_job(name: str):
    try:
        return {"started": scheduler.run_now(name)}
    except KeyError:
        raise HTTPException(404, "unknown job")
