"""Price & stock refresh for every listing that isn't ended."""
from __future__ import annotations

from .. import activity
from .. import settings_store as st
from ..blocklist import Blocklist
from ..db import session_scope
from ..models import Listing, PriceHistory, utcnow
from ..pricing import calculate, profit_for
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

    drop_limit = float(st.get("refresh_max_drop_percent"))
    if b["ebay_price"] < price * (1 - drop_limit / 100):
        # A huge drop is more often a misread page than a real price cut. Keep the current (higher, still
        # profitable) price and let you confirm it.
        ops.flag(lid, f"review: big price drop held — Amazon now ${p.price:.2f} → eBay ${b['ebay_price']:.2f} "
                      f"(currently ${price:.2f}). Check Amazon, then Apply suggested price if it's real.")
        activity.warning("price", f"Held a {100 - b['ebay_price'] / price * 100:.0f}% price drop on '{title[:60]}' "
                                  f"for you to confirm (Amazon ${p.price:.2f})", asin=asin, listing_id=lid)
        return

    if not b["passes_floor"]:
        why = "; ".join(b["floor_reasons"])
        action = st.get("below_floor_action")
        losing = b["profit"] <= 0
        if status == "active":
            stats["below_floor"] += 1
            activity.warning("price", f"{asin} below profit floor at Amazon ${p.price:.2f}: {why}", asin=asin, listing_id=lid)
            if losing and (not apply or action == "flag"):
                # Selling would cost you money: stop sales even in review / "just flag" mode.
                ops.set_quantity(lid, 0, f"below profit floor: {why}", status="qty0")
                ops.flag(lid, f"below profit floor: {why} — quantity set to 0 so it can't sell at a loss")
            elif not apply or action == "flag":
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
    # What one sale earns at the price eBay shows *right now*, with today's Amazon cost.
    profit_now = profit_for(price, b["amazon_cost"], params)["profit"] if status == "active" else None
    with session_scope() as s:
        l = s.get(Listing, lid)
        stale = l.flag_reason.startswith("below profit floor") or (l.flag_reason.startswith("review:") and not price_moved) \
            or l.flag_reason.startswith("review: big price drop")
        if l.flagged and stale:
            l.flagged, l.flag_reason = False, ""
    if price_moved:
        stats["price_changed"] += 1
        if not apply:
            if profit_now is not None and profit_now <= 0:
                _stop_loss(lid, title, asin, price, profit_now)
            review(f"Amazon now ${p.price:.2f} → suggested eBay price ${b['ebay_price']:.2f} (currently ${price:.2f})"
                   + (f"; a sale at ${price:.2f} would lose ${-profit_now:.2f}, so quantity was set to 0"
                      if profit_now is not None and profit_now <= 0 else ""))
            return
        try:
            changed = ops.set_price(lid, b["ebay_price"], f"Amazon price now ${p.price:.2f}")
        except Exception:
            if profit_now is not None and profit_now <= 0:
                _stop_loss(lid, title, asin, price, profit_now)
            raise
        if changed:
            with session_scope() as s:
                s.add(PriceHistory(listing_id=lid, amazon_price=p.price, ebay_price=b["ebay_price"], in_stock=True,
                                   expected_profit=b["profit"], note="eBay price updated"))
        else:
            stats["price_changed"] -= 1


def apply_suggested_price(lid: int) -> dict:
    """You confirmed a held price change: apply the latest refreshed price, if it's still profitable."""
    with session_scope() as s:
        l = s.get(Listing, lid)
        b = l.current_breakdown or {}
        status, in_stock = l.status, l.current_in_stock
    if not b.get("amazon_price"):
        return {"ok": False, "message": "No refreshed price yet — press Refresh first."}
    b = calculate(b["amazon_price"], pricing_params())  # re-check with your settings as they are now
    if not in_stock:
        return {"ok": False, "message": "Amazon showed it out of stock at the last refresh."}
    if not b.get("passes_floor") or b.get("profit", 0) <= 0:
        return {"ok": False, "message": "Not applied: " + "; ".join(b.get("floor_reasons") or ["no profit"])}
    if status == "qty0":
        ok = ops.restore(lid, b["ebay_price"], "price confirmed by you")
    else:
        ok = ops.set_price(lid, b["ebay_price"], f"confirmed by you (Amazon ${b['amazon_price']:.2f})")
    if ok:
        with session_scope() as s:
            l = s.get(Listing, lid)
            l.flagged, l.flag_reason = False, ""
    return {"ok": ok, "message": f"eBay price set to ${b['ebay_price']:.2f}" if ok else "Not changed (dry-run or ended)."}


def _stop_loss(lid: int, title: str, asin: str, price: float, profit_now: float) -> None:
    """The listing's current eBay price no longer covers the Amazon cost: stop it selling."""
    activity.warning("price", f"'{title[:60]}' would lose ${-profit_now:.2f} per sale at ${price:.2f} — quantity set to 0",
                     asin=asin, listing_id=lid)
    ops.set_quantity(lid, 0, f"would lose ${-profit_now:.2f} per sale at ${price:.2f}", status="qty0")


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
