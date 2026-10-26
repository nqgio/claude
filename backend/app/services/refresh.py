"""Price & stock refresh for every listing that isn't ended."""
from __future__ import annotations

from .. import activity
from .. import settings_store as st
from ..blocklist import Blocklist
from ..db import session_scope
from ..models import Listing, PriceHistory, utcnow
from ..pricing import calculate
from ..providers.base import ProviderError, SourceBlocked, SourcePaused
from . import listing_ops as ops
from . import products
from .evaluate import pricing_params


def _ids(listing_ids: list[int] | None) -> list[int]:
    with session_scope() as s:
        q = s.query(Listing.id).filter(Listing.status != "ended")
        if listing_ids:
            q = q.filter(Listing.id.in_(listing_ids))
        return [r[0] for r in q.order_by(Listing.last_refreshed.is_(None).desc(), Listing.last_refreshed).all()]


def run(listing_ids: list[int] | None = None, force_fetch: bool = False) -> dict:
    ids = _ids(listing_ids)
    stats = {"checked": 0, "price_changed": 0, "out_of_stock": 0, "restored": 0, "below_floor": 0, "errors": 0}
    if not ids:
        return stats
    activity.info("price", f"Refreshing {len(ids)} listing(s)")
    # When refreshing on a schedule, don't re-fetch anything fetched within the cache window.
    max_age = 0 if force_fetch else None
    for lid in ids:
        try:
            refresh_one(lid, stats, max_age)
        except (SourceBlocked, SourcePaused) as exc:
            activity.warning("price", f"Refresh stopped: {exc}")
            break
        except Exception as exc:
            stats["errors"] += 1
            activity.error("price", f"Refresh failed for listing #{lid}: {exc}", listing_id=lid)
    activity.info("price", "Refresh done: " + ", ".join(f"{k} {v}" for k, v in stats.items()))
    return stats


def refresh_one(lid: int, stats: dict, max_age: float | None = None) -> None:
    with session_scope() as s:
        l = s.get(Listing, lid)
        asin, status, reason, price, title = l.asin, l.status, l.status_reason, l.price, l.title
    try:
        p, _changed = products.fetch(asin, max_age_hours=max_age)
    except (SourceBlocked, SourcePaused):
        raise
    except ProviderError as exc:
        stats["errors"] += 1
        activity.error("price", f"Could not re-check {asin}: {exc}", asin=asin, listing_id=lid)
        return
    stats["checked"] += 1
    params = pricing_params()
    b = calculate(p.price, params) if p.price else None
    with session_scope() as s:
        l = s.get(Listing, lid)
        l.current_amazon_price, l.current_in_stock, l.last_refreshed = p.price, p.in_stock, utcnow()
        if b:
            l.current_breakdown = b
            l.expected_profit = b["profit"]
        s.add(PriceHistory(listing_id=lid, amazon_price=p.price, ebay_price=l.price, in_stock=p.in_stock,
                           expected_profit=b["profit"] if b else None))

    apply = bool(st.get("refresh_auto_apply"))

    def review(msg: str) -> None:
        """Auto-apply is off: record the suggested change for you instead of touching eBay."""
        ops.flag(lid, f"review: {msg}")

    if not p.in_stock or not p.price:
        if status == "active":
            stats["out_of_stock"] += 1
            activity.info("stock", f"Amazon out of stock: {asin} '{title[:60]}'", asin=asin, listing_id=lid)
            if not apply:
                review("Amazon is out of stock")
            elif st.get("oos_action") == "end":
                ops.end_listing(lid, "Amazon out of stock")
            else:
                ops.set_quantity(lid, 0, "Amazon out of stock", status="qty0")
        return

    if not b["passes_floor"]:
        why = "; ".join(b["floor_reasons"])
        action = st.get("below_floor_action")
        if status == "active":
            stats["below_floor"] += 1
            activity.warning("price", f"{asin} below profit floor at Amazon ${p.price:.2f}: {why}", asin=asin, listing_id=lid)
            if not apply or action == "flag":
                ops.flag(lid, f"{'review: ' if not apply else ''}below profit floor: {why}")
            elif action == "end":
                ops.end_listing(lid, f"below profit floor: {why}")
            else:
                ops.set_quantity(lid, 0, f"below profit floor: {why}", status="qty0")
        return

    if status == "qty0":
        if not apply:
            review(f"can be restored at ${b['ebay_price']:.2f}")
            return
        ops.restore(lid, b["ebay_price"], "Amazon back in stock" if "stock" in reason else "profit back above floor")
        stats["restored"] += 1
        return
    price_moved = abs(b["ebay_price"] - price) >= 0.005
    with session_scope() as s:
        l = s.get(Listing, lid)
        stale = l.flag_reason.startswith("below profit floor") or (l.flag_reason.startswith("review:") and not price_moved)
        if l.flagged and stale:
            l.flagged, l.flag_reason = False, ""
    if price_moved:
        stats["price_changed"] += 1
        if not apply:
            review(f"Amazon now ${p.price:.2f} → suggested eBay price ${b['ebay_price']:.2f} (currently ${price:.2f})")
            return
        if ops.set_price(lid, b["ebay_price"], f"Amazon price now ${p.price:.2f}"):
            with session_scope() as s:
                s.add(PriceHistory(listing_id=lid, amazon_price=p.price, ebay_price=b["ebay_price"], in_stock=True,
                                   expected_profit=b["profit"], note="eBay price updated"))
        else:
            stats["price_changed"] -= 1


def scan_blocklist(action: str | None = None) -> dict:
    """Check every non-ended listing against the current blocklist; flag or end matches."""
    action = action or st.get("blocklist_scan_action")
    bl = Blocklist.load()
    hits = []
    with session_scope() as s:
        rows = [(l.id, l.asin, l.title, l.description_html) for l in s.query(Listing).filter(Listing.status != "ended")]
    for lid, asin, title, desc in rows:
        cached = products.cached(asin)
        brand = cached.brand if cached else ""
        m = bl.check(brand, title + " " + (cached.title if cached else ""), desc)
        if not m:
            continue
        hits.append({"listing_id": lid, "asin": asin, "reason": m.reason()})
        activity.warning("blocklist", f"Listing #{lid} '{title[:60]}' matches blocklist: {m.reason()}", asin=asin, listing_id=lid)
        if action == "end":
            ops.end_listing(lid, f"blocklist: {m.reason()}")
        else:
            ops.flag(lid, f"blocklist: {m.reason()}")
    return {"matches": hits, "action": action}
