"""Automatic offers to watchers (eBay Negotiation API).

eBay lists which of your listings have interested buyers (watchers) who can be sent an offer. For each of
this app's live listings among them, the app sends your discount (10% by default), lowered as needed so the
offer price still makes your minimum profit (and minimum return, if set); if even eBay's minimum 5% wouldn't,
no offer is sent. Each listing gets at most one offer per "wait between offers" period.
"""
from __future__ import annotations

from datetime import timedelta

from .. import activity
from .. import settings_store as st
from ..db import session_scope
from ..ebay import api as ebay
from ..ebay.client import EbayError, EbayNotConnected
from ..models import Listing, utcnow
from ..pricing import _d, floor_failures, profit_for
from .evaluate import pricing_params

EBAY_MIN_DISCOUNT = 5


def best_discount(price: float, cost: float, wanted: int) -> tuple[int | None, float | None]:
    """Largest whole-percent discount ≤ `wanted` (and ≥ eBay's 5%) that keeps your profit floor.
    Returns (percent, profit at that price) or (None, None)."""
    params = pricing_params()
    for pct in range(int(wanted), EBAY_MIN_DISCOUNT - 1, -1):
        offer = _d(price) * (100 - pct) / 100
        prof = profit_for(offer, cost, params)
        if not floor_failures(prof["_profit_exact"], prof["_roi_exact"], params):
            return pct, prof["profit"]
    return None, None


def send_offers() -> dict:
    if not st.get("auto_offers_enabled"):
        return {"skipped": "auto offers are off"}
    try:
        eligible = set(ebay.offer_eligible_listings())
    except EbayNotConnected as exc:
        return {"skipped": str(exc)}
    except EbayError as exc:
        activity.warning("offers", f"Could not check which listings can get offers: {exc}")
        return {"skipped": str(exc)}
    if not eligible:
        return {"eligible": 0, "sent": 0}
    env = st.get("ebay_environment")
    wait = timedelta(days=int(st.get("auto_offer_repeat_days")))
    with session_scope() as s:
        rows = [(l.id, l.ebay_listing_id, l.title, l.price, (l.current_breakdown or l.breakdown or {}).get("amazon_cost",
                 l.cost_at_listing), l.last_offer_at)
                for l in s.query(Listing).filter(Listing.environment == env, Listing.dry_run.is_(False),
                                                 Listing.status == "active", Listing.ebay_listing_id.in_(eligible))]
    sent = skipped = 0
    wanted = int(st.get("auto_offer_percent"))
    message = st.get("auto_offer_message")
    for lid, item_id, title, price, cost, last in rows:
        if last and utcnow() - last < wait:
            continue
        pct, profit = best_discount(price, cost, wanted)
        if pct is None:
            skipped += 1
            activity.info("offers", f"No offer for '{title[:60]}': even {EBAY_MIN_DISCOUNT}% off would go below your "
                                    f"minimum profit", listing_id=lid)
            with session_scope() as s:  # don't re-check it every few hours; try again after the wait
                s.get(Listing, lid).last_offer_at = utcnow()
            continue
        offer_price = round(price * (100 - pct) / 100, 2)
        if st.get("dry_run"):
            activity.info("offers", f"DRY RUN: would send watchers of '{title[:60]}' a {pct}% offer "
                                    f"(${offer_price:.2f}, profit ${profit:.2f})", listing_id=lid)
        else:
            try:
                ebay.send_offer(item_id, pct, message)
            except EbayError as exc:
                activity.warning("offers", f"Offer for '{title[:60]}' not sent: {exc}", listing_id=lid)
                continue
            activity.info("offers", f"Sent watchers of '{title[:60]}' a {pct}% offer: ${offer_price:.2f} "
                                    f"(profit ${profit:.2f} if they accept)", listing_id=lid)
        with session_scope() as s:
            s.get(Listing, lid).last_offer_at = utcnow()
        sent += 1
    return {"eligible": len(eligible), "sent": sent, "no_room": skipped}
