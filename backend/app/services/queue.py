"""Daily product discovery → queue → randomized posting across the window."""
from __future__ import annotations

import math
import random
import time
from datetime import date, datetime, time as dtime, timedelta, timezone

from .. import activity
from .. import settings_store as st
from ..blocklist import Blocklist
from ..db import session_scope
from ..ebay import api as ebay
from ..ebay.client import EbayError, keys as ebay_keys
from ..models import Listing, QueueItem, utcnow
from ..providers import get_provider
from ..providers.base import STOP_EVENT, ProviderError, SourceBlocked, SourcePaused, Stopped, set_wait_listener
from . import products
from .content import build_listing_content
from .evaluate import evaluate, search_result_reasons


def local_now() -> datetime:
    return datetime.now().astimezone()


def to_utc_naive(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _hm(value: str) -> dtime:
    h, m = value.split(":")
    return dtime(int(h), int(m))


def window_today(now: datetime | None = None) -> tuple[datetime, datetime]:
    now = now or local_now()
    start = datetime.combine(now.date(), _hm(st.get("posting_window_start")), tzinfo=now.tzinfo)
    end = datetime.combine(now.date(), _hm(st.get("posting_window_end")), tzinfo=now.tzinfo)
    return start, end


def active_asins() -> set[str]:
    """ASINs that already have a real (non-dry-run) listing that isn't ended."""
    with session_scope() as s:
        rows = s.query(Listing.asin).filter(Listing.dry_run.is_(False), Listing.status != "ended").all()
        return {r[0] for r in rows}


def _search_terms() -> list[tuple[str, str | None]]:
    kws, cats = st.get("search_keywords"), st.get("search_categories")
    if kws and cats:
        return [(k, c) for c in cats for k in kws]
    return [(k, None) for k in kws] + [("", c) for c in cats]


def _preview(p, ev) -> dict:
    content = build_listing_content(p, with_category=_ebay_available())
    return {**content, "product": p.to_dict()}


def _ebay_available() -> bool:
    k = ebay_keys()
    return bool(k["app_id"] and k["cert_id"])


def add_candidate(p, ev, source: str, force: bool = False, today: date | None = None, search_term: str = "") -> int:
    today = today or local_now().date()
    preview = _preview(p, ev)
    preview["force"] = force
    with session_scope() as s:
        item = QueueItem(asin=p.asin, queue_date=today, status="queued", source=source, title=preview["title"],
                         amazon_price=p.price, ebay_price=ev["breakdown"]["ebay_price"],
                         expected_profit=ev["breakdown"]["profit"], breakdown=ev["breakdown"], preview=preview,
                         search_term=search_term)
        s.add(item)
        s.flush()
        return item.id


CARRY_OVER_DAYS = 7  # unposted auto-found products stay in the queue this long


# Live progress of the current/last queue build (shown on the Queue page).
PROGRESS: dict = {"running": False}


def _progress(**kw) -> None:
    PROGRESS.update(kw)


def _on_amazon_wait(message: str | None) -> None:
    """Show long Amazon waits (hourly page limit, another task using the browser) in the progress panel,
    so a waiting build doesn't look frozen."""
    if not PROGRESS.get("running"):
        return
    if message:
        PROGRESS.setdefault("step_before_wait", PROGRESS.get("step", ""))
        PROGRESS.update(step=message, waiting=True)
    elif PROGRESS.get("waiting"):
        PROGRESS.update(step=PROGRESS.pop("step_before_wait", ""), waiting=False)


set_wait_listener(_on_amazon_wait)


def stop_build() -> bool:
    """Ask a running queue build to stop at the next safe point. Products already found are kept."""
    if not PROGRESS.get("running"):
        return False
    STOP_EVENT.set()
    _progress(step="Stopping…")
    return True


def build_queue(trigger: str = "schedule") -> dict:
    STOP_EVENT.clear()
    PROGRESS.clear()
    _progress(running=True, started_at=utcnow().isoformat() + "Z", step="Starting…", examined=0, added=0, target=0,
              have=0, finished_at=None, result="")
    try:
        res = _build_queue(trigger)
        if not PROGRESS.get("result"):  # keep a more specific message (no keywords, Amazon paused…)
            _progress(result=f"Done: checked {res.get('examined', 0)} product(s), added {res.get('added', 0)}.")
        return res
    except Exception as exc:
        _progress(result=f"Stopped by an error: {exc}")
        raise
    finally:
        STOP_EVENT.clear()
        _progress(running=False, finished_at=utcnow().isoformat() + "Z", step="")


def _build_queue(trigger: str) -> dict:
    today = local_now().date()
    terms = _search_terms()
    if not terms:
        activity.warning("queued", "No search keywords or categories set (Settings → Product finder) — queue not built")
        _progress(result="No search keywords set (Settings → Product finder).")
        _mark_built(today)
        return {"added": 0}
    per_day = int(st.get("listings_per_day"))
    target = math.ceil(per_day * float(st.get("queue_backup_factor")))
    listed = active_asins()
    with session_scope() as s:
        # Products found on earlier days but not posted yet carry over (no need to find them on Amazon again);
        # they're re-checked on Amazon right before posting. Auto-found ones expire after a week.
        stale = utcnow() - timedelta(days=CARRY_OVER_DAYS)
        for old in s.query(QueueItem).filter(QueueItem.queue_date < today, QueueItem.status.in_(["queued", "scheduled"])):
            if old.asin in listed:
                old.status, old.message = "removed", "already listed"
            elif old.source == "auto" and old.created_at < stale:
                old.status, old.message = "expired", f"not posted within {CARRY_OVER_DAYS} days"
            else:
                if not old.message.startswith("carried over"):
                    old.message = f"carried over from {old.queue_date:%b %d}"
                old.queue_date, old.status, old.scheduled_at = today, "queued", None
        todays = s.query(QueueItem).filter(QueueItem.queue_date == today).all()
        seen = {q.asin for q in todays}
        dry = _dry_run_listing_ids(s, todays)
        # Dry-run previews don't use up the day: in dry-run you can keep building and testing.
        have = sum(1 for q in todays if q.status in ("queued", "scheduled", "posting")
                   or (q.status == "posted" and q.listing_id not in dry))
    seen |= listed
    activity.info("queued", f"Building today's queue ({trigger}): want {target}, have {have}")
    _progress(target=target, have=have)
    provider, bl = get_provider(), Blocklist.load()
    added, examined = 0, 0
    pages = int(st.get("search_pages_per_term"))
    # Variety: keywords are visited in a random order, one product per keyword per round, so no
    # single keyword fills the queue. Each keyword's results are kept between rounds (no extra searches).
    lanes = [{"term": term, "cat": cat, "label": term or cat, "page": 0, "results": [], "done": False}
             for term, cat in terms]

    def next_result(lane):
        """The next unseen search result for this keyword, searching its next page when needed."""
        while True:
            while lane["results"]:
                r = lane["results"].pop(0)
                if r.asin not in seen:
                    return r
            if lane["page"] >= pages:
                return None
            if STOP_EVENT.is_set():
                raise Stopped("stopped by you")
            lane["page"] += 1
            _progress(step=f"Searching Amazon for “{lane['label']}” (page {lane['page']})")
            try:
                lane["results"] = list(provider.search(lane["term"], lane["cat"], lane["page"]) or [])
            except (SourceBlocked, SourcePaused):
                raise
            except ProviderError as exc:
                activity.error("amazon", f"Search '{lane['label']}' page {lane['page']} failed: {exc}")
                return None
            if not lane["results"]:
                return None

    def take_one(lane) -> bool:
        """Check this keyword's results until one product qualifies (True) or it runs out (False)."""
        nonlocal examined
        while True:
            r = next_result(lane)
            if r is None:
                lane["done"] = True
                return False
            if STOP_EVENT.is_set():
                raise Stopped("stopped by you")
            seen.add(r.asin)
            examined += 1
            _progress(examined=examined, step=f"Checking {r.asin} (“{lane['label']}”): {r.title[:70]}")
            why = search_result_reasons(r)
            m = bl.check("", r.title)
            if m:
                why.append(m.reason())
            if why:
                activity.info("skipped", f"Skipped {r.asin}: {'; '.join(why)}", asin=r.asin)
                continue
            try:
                p, _ = products.fetch(r.asin)
            except (SourceBlocked, SourcePaused):
                raise
            except ProviderError as exc:
                activity.error("amazon", f"Could not load {r.asin}: {exc}", asin=r.asin)
                continue
            ev = evaluate(p, blocklist=bl)
            if not ev["ok"]:
                activity.info("skipped", f"Skipped {p.asin} '{p.title[:60]}': {'; '.join(ev['reasons'])}", asin=p.asin)
                continue
            add_candidate(p, ev, "auto", today=today, search_term=lane["label"])
            b = ev["breakdown"]
            activity.info("found", f"Queued {p.asin} '{p.title[:60]}' from “{lane['label']}” — Amazon "
                                   f"${b['amazon_price']:.2f} → eBay ${b['ebay_price']:.2f}, profit ${b['profit']:.2f}",
                          asin=p.asin)
            return True

    try:
        while have + added < target:
            active = [l for l in lanes if not l["done"]]
            if not active:
                break
            random.shuffle(active)  # a new random keyword order every round
            for lane in active:
                if have + added >= target:
                    break
                if take_one(lane):
                    added += 1
                    _progress(added=added)
    except Stopped:
        activity.info("queued", f"Queue build stopped by you: checked {examined}, added {added} (kept)")
        _progress(result=f"Stopped by you. Checked {examined}, added {added} — those are kept. "
                         "Change settings if you like, then press Build queue now to continue.")
        schedule_today()
        _mark_built(today)
        return {"added": added, "examined": examined, "stopped": "by user"}
    except (SourceBlocked, SourcePaused) as exc:
        activity.warning("queued", f"Queue build stopped early: {exc}")
        _progress(result=f"Stopped early: Amazon is paused ({exc}). Checked {examined}, added {added}. "
                         "It will carry on automatically when the pause ends.")
        schedule_today()  # today isn't marked built, so posting_tick resumes the build after the cooldown
        return {"added": added, "examined": examined, "stopped": str(exc)}
    activity.info("queued", f"Queue build done: examined {examined}, added {added}")
    _progress(step="Scheduling posting times…")
    schedule_today()
    _mark_built(today)
    return {"added": added, "examined": examined}


def _mark_built(day: date) -> None:
    """Today's build finished (or you stopped it). Only then does the catch-up in posting_tick stand down,
    so a build cut short by a CAPTCHA pause, a crash or the PC shutting down is retried the same day."""
    st.set_internal("last_queue_build_date", day.isoformat())


def _dry_run_listing_ids(s, items) -> set[int]:
    ids = [q.listing_id for q in items if q.listing_id]
    if not ids:
        return set()
    return {r[0] for r in s.query(Listing.id).filter(Listing.id.in_(ids), Listing.dry_run.is_(True))}


def _posted_today(dry_run: bool) -> int:
    with session_scope() as s:
        posted = s.query(QueueItem).filter(QueueItem.status == "posted", QueueItem.queue_date == local_now().date()).all()
        dry = _dry_run_listing_ids(s, posted)
        return sum(1 for q in posted if (q.listing_id in dry) == dry_run)


def posted_today_count() -> int:
    """Real listings posted today. Dry-run previews don't count toward listings per day."""
    return _posted_today(dry_run=False)


def dry_run_posted_today_count() -> int:
    return _posted_today(dry_run=True)


def schedule_today() -> int:
    """Assign random posting times (spread across the rest of today's window) to
    as many queued items as are still needed today."""
    now = local_now()
    start, end = window_today(now)
    begin = max(start, now + timedelta(minutes=2))
    if begin >= end:
        return 0
    with session_scope() as s:
        today = now.date()
        scheduled = s.query(QueueItem).filter(QueueItem.queue_date == today,
                                              QueueItem.status.in_(["scheduled", "posting"])).count()
        need = int(st.get("listings_per_day")) - posted_today_count() - scheduled
        if need <= 0:
            return 0
        queued = (s.query(QueueItem).filter(QueueItem.queue_date == today, QueueItem.status == "queued")
                  .order_by((QueueItem.source == "manual").desc(), QueueItem.expected_profit.desc()).all())
        used_today = [q.search_term for q in s.query(QueueItem).filter(
            QueueItem.queue_date == today, QueueItem.status.in_(["scheduled", "posting", "posted"]))]
        items = _mix_keywords(queued, need, used_today)
        if not items:
            return 0
        span = (end - begin).total_seconds()
        slot = span / len(items)
        for i, item in enumerate(items):
            t = begin + timedelta(seconds=slot * i + random.uniform(0.1, 0.9) * slot)
            item.status, item.scheduled_at = "scheduled", to_utc_naive(t)
        n = len(items)
    activity.info("queued", f"Scheduled {n} listing(s) between {begin:%H:%M} and {end:%H:%M}")
    return n


def _mix_keywords(queued: list, need: int, used_today: list[str]) -> list:
    """Pick `need` items, taking turns between keywords so the same kind of product isn't posted back to back.
    Manual adds go first; keywords already posted/scheduled today wait their turn; best profit first within a keyword."""
    manual = [q for q in queued if q.source == "manual"][:need]
    groups: dict[str, list] = {}
    for q in queued:
        if q.source != "manual":
            groups.setdefault(q.search_term, []).append(q)
    order = sorted(groups, key=lambda k: (used_today.count(k), random.random()))
    picked = list(manual)
    while len(picked) < need and any(groups.values()):
        for k in order:
            if groups[k] and len(picked) < need:
                picked.append(groups[k].pop(0))
    return picked


def _amazon_paused() -> bool:
    if st.get("product_source") != "amazon_playwright":
        return False
    from ..providers.amazon_playwright import paused_until

    until = paused_until()
    return until is not None and datetime.now(timezone.utc) < until


STUCK_POSTING_MINUTES = 30


def due_items() -> list[int]:
    """The next item due to post today. Items from earlier days never post late (they expire at the next build)."""
    with session_scope() as s:
        # A post interrupted by the app closing stays "posting"; put it back. Re-posting is safe: the same SKU
        # reuses its eBay offer instead of creating a second listing.
        for q in s.query(QueueItem).filter(QueueItem.status == "posting",
                                           QueueItem.scheduled_at <= utcnow() - timedelta(minutes=STUCK_POSTING_MINUTES)):
            q.status, q.message = "scheduled", "retrying: the earlier attempt was interrupted"
        return [q.id for q in s.query(QueueItem).filter(QueueItem.status == "scheduled", QueueItem.scheduled_at <= utcnow(),
                                                        QueueItem.queue_date == local_now().date())
                .order_by(QueueItem.scheduled_at).limit(1).all()]


CATCHUP_RETRY_SECONDS = 15 * 60
_last_catchup: float | None = None  # monotonic time of the last catch-up attempt (resets when the app restarts)


def posting_tick() -> None:
    global _last_catchup
    now = local_now()
    built = st.get("last_queue_build_date")
    if built != now.date().isoformat() and now.time() >= _hm(st.get("discovery_time")) \
            and not PROGRESS.get("running") \
            and (_last_catchup is None or time.monotonic() - _last_catchup >= CATCHUP_RETRY_SECONDS) \
            and not _amazon_paused():
        # Today's queue hasn't been built yet: the PC was off at build time, or the build was cut short.
        from .scheduler import run_now

        _last_catchup = time.monotonic()
        run_now("discovery")
    for item_id in due_items():
        post_item(item_id)
    schedule_today()  # refill if something failed or was removed


# ---- posting ----------------------------------------------------------------------------

class ListingFailed(Exception):
    pass


def post_item(item_id: int) -> dict:
    with session_scope() as s:
        item = s.get(QueueItem, item_id)
        if item is None or item.status not in ("queued", "scheduled"):
            return {"ok": False, "message": "item is not waiting to be posted"}
        item.status = "posting"
        item.scheduled_at = min(item.scheduled_at or utcnow(), utcnow())  # "Post now" items get a start time too
        asin, force = item.asin, bool((item.preview or {}).get("force"))
    if asin in active_asins():  # last check: never list the same product twice
        _finish(item_id, "skipped", "already listed on eBay")
        activity.info("skipped", f"Not listing {asin}: it's already listed", asin=asin)
        return {"ok": False, "message": "already listed on eBay"}
    try:
        p, _ = products.fetch(asin)
        ev = evaluate(p, apply_filters=not force)
        if not ev["ok"]:
            _finish(item_id, "skipped", "; ".join(ev["reasons"]))
            activity.info("skipped", f"Not listing {asin} at post time: {'; '.join(ev['reasons'])}", asin=asin)
            return {"ok": False, "message": "; ".join(ev["reasons"])}
        content = build_listing_content(p, with_category=_ebay_available())
        listing_id = _create_listing(p, ev["breakdown"], content)
        _finish(item_id, "posted", "", listing_id)
        return {"ok": True, "listing_id": listing_id}
    except (SourceBlocked, SourcePaused) as exc:
        with session_scope() as s:
            item = s.get(QueueItem, item_id)
            item.status, item.message = "scheduled", f"waiting for Amazon cooldown: {exc}"
            item.scheduled_at = utcnow() + timedelta(minutes=30)
        return {"ok": False, "message": str(exc)}
    except Exception as exc:
        _finish(item_id, "failed", str(exc)[:1000])
        activity.error("listed", f"Failed to list {asin}: {exc}", asin=asin)
        return {"ok": False, "message": str(exc)}


def _finish(item_id: int, status: str, message: str, listing_id: int | None = None) -> None:
    with session_scope() as s:
        item = s.get(QueueItem, item_id)
        item.status, item.message = status, message
        if listing_id:
            item.listing_id = listing_id


def _create_listing(p, b: dict, c: dict) -> int:
    s_all = st.all_settings(include_hidden=True)
    dry = bool(s_all["dry_run"])
    env = s_all["ebay_environment"]
    qty = int(s_all["listing_quantity"])
    sku = f"AMZ-{p.asin}"
    row = dict(asin=p.asin, amazon_url=p.url, environment=env, dry_run=dry, sku=sku, title=c["title"],
               description_html=c["description_html"], aspects=c["aspects"], image_urls=c["images"],
               ebay_category_id=c["category_id"], ebay_category_name=c["category_name"], price=b["ebay_price"],
               quantity=qty, status="active", amazon_price_at_listing=b["amazon_price"], cost_at_listing=b["amazon_cost"],
               breakdown=b, current_breakdown=b, current_amazon_price=b["amazon_price"], current_in_stock=p.in_stock,
               expected_profit=b["profit"], last_refreshed=utcnow())
    if dry:
        with session_scope() as s:
            l = Listing(**row)
            s.add(l)
            s.flush()
            lid = l.id
        note = f" (category: {c['category_name']})" if c["category_id"] else f" ({c['category_note']})"
        activity.info("listed", f"DRY RUN: would list '{c['title']}' at ${b['ebay_price']:.2f} "
                                f"(Amazon ${b['amazon_price']:.2f}, profit ${b['profit']:.2f}){note}",
                      asin=p.asin, listing_id=lid)
        return lid

    missing = [k for k in ("fulfillment_policy_id", "return_policy_id", "payment_policy_id", "item_location_zip") if not s_all[k]]
    if missing:
        raise ListingFailed("Settings missing: " + ", ".join(missing) + " (Settings → Listing defaults)")
    if not c["category_id"]:
        raise ListingFailed(f"No eBay category: {c['category_note']}")
    if c["missing_required_aspects"]:
        activity.warning("listed", f"{p.asin}: eBay requires item specifics we couldn't fill: "
                                   f"{', '.join(c['missing_required_aspects'])}", asin=p.asin)
    loc_key = s_all["merchant_location_key"]
    ready = dict(s_all["ebay_location_ready"] or {})
    if ready.get(env) != f"{loc_key}:{s_all['item_location_zip']}":
        ebay.ensure_location(loc_key, s_all["item_location_zip"], s_all["item_location_city"], s_all["item_location_state"])
        ready[env] = f"{loc_key}:{s_all['item_location_zip']}"
        st.set_internal("ebay_location_ready", ready)
    product = {"title": c["title"], "aspects": c["aspects"], "imageUrls": c["images"],
               "description": (p.description or " ".join(p.features))[:3900] or c["title"]}
    if c["aspects"].get("Brand"):
        product["brand"] = c["aspects"]["Brand"][0]
    if c["aspects"].get("MPN"):
        product["mpn"] = c["aspects"]["MPN"][0]
    if p.details.get("UPC"):
        product["upc"] = [p.details["UPC"].split()[0]]
    ebay.put_inventory_item(sku, {"availability": {"shipToLocationAvailability": {"quantity": qty}},
                                  "condition": "NEW", "product": product})
    offer = {"sku": sku, "marketplaceId": s_all["marketplace_id"], "format": "FIXED_PRICE", "availableQuantity": qty,
             "categoryId": c["category_id"], "listingDescription": c["description_html"], "listingDuration": "GTC",
             "merchantLocationKey": loc_key,
             "listingPolicies": {"fulfillmentPolicyId": s_all["fulfillment_policy_id"],
                                 "returnPolicyId": s_all["return_policy_id"],
                                 "paymentPolicyId": s_all["payment_policy_id"]},
             "pricingSummary": {"price": {"value": f"{b['ebay_price']:.2f}", "currency": "USD"}}}
    existing = ebay.get_offers_for_sku(sku)
    if existing:
        offer_id = existing[0]["offerId"]
        ebay.update_offer(offer_id, offer)
    else:
        offer_id = ebay.create_offer(offer)
    listing_id = ebay.publish_offer(offer_id)
    row.update(offer_id=offer_id, ebay_listing_id=listing_id)
    campaign_id = ad_id = None
    if s_all["promoted_listings_enabled"] and s_all["promo_rate_percent"] > 0:
        try:
            camps = dict(s_all["ebay_campaign_ids"] or {})
            key = f"{env}:{s_all['promo_campaign_name']}"
            campaign_id = camps.get(key) or ebay.find_or_create_campaign(s_all["promo_campaign_name"], s_all["promo_rate_percent"])
            if camps.get(key) != campaign_id:
                camps[key] = campaign_id
                st.set_internal("ebay_campaign_ids", camps)
            ad_id = ebay.create_ad(campaign_id, listing_id, s_all["promo_rate_percent"])
        except EbayError as exc:
            activity.warning("listed", f"Listed {p.asin} but could not add it to Promoted Listings: {exc}", asin=p.asin)
    row.update(campaign_id=campaign_id, ad_id=ad_id)
    with session_scope() as s:
        l = Listing(**row)
        s.add(l)
        s.flush()
        lid = l.id
    activity.info("listed", f"Listed '{c['title']}' on eBay ({env}) at ${b['ebay_price']:.2f} — item {listing_id}, "
                            f"expected profit ${b['profit']:.2f}", asin=p.asin, listing_id=lid)
    return lid


def manual_add(asin: str, force: bool = False) -> dict:
    asin = asin.strip().upper()
    if len(asin) != 10 or not asin.isalnum():
        return {"ok": False, "message": "ASIN must be 10 letters/digits"}
    if asin in active_asins():
        return {"ok": False, "message": f"{asin} is already listed"}
    try:
        p, _ = products.fetch(asin, max_age_hours=1)
    except ProviderError as exc:
        return {"ok": False, "message": str(exc)}
    ev = evaluate(p, apply_filters=not force)
    if not ev["ok"]:
        activity.info("skipped", f"Manual add {asin} rejected: {'; '.join(ev['reasons'])}", asin=asin)
        return {"ok": False, "message": "; ".join(ev["reasons"]), "breakdown": ev["breakdown"]}
    qid = add_candidate(p, ev, "manual", force=force)
    activity.info("queued", f"Manually queued {asin} '{p.title[:60]}'", asin=asin)
    schedule_today()
    return {"ok": True, "queue_id": qid, "breakdown": ev["breakdown"]}
