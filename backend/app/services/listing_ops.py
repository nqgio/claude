"""Changes to existing listings (price, quantity, end). Respects dry-run: live
listings are never touched on eBay while dry-run is on — the intended change is
logged instead."""
from __future__ import annotations

from .. import activity
from .. import settings_store as st
from ..db import session_scope
from ..ebay import api
from ..models import Listing, utcnow


def _live(listing: Listing) -> bool:
    return not listing.dry_run and bool(listing.offer_id)


def _dry_note(listing: Listing, action: str) -> bool:
    """True if we must not call eBay (dry-run on for a live listing)."""
    if _live(listing) and st.get("dry_run"):
        activity.info("price" if "price" in action else "stock", f"DRY RUN: would {action} on '{listing.title}'",
                      asin=listing.asin, listing_id=listing.id)
        return True
    return False


def set_quantity(listing_id: int, qty: int, reason: str, status: str | None = None) -> bool:
    with session_scope() as s:
        l = s.get(Listing, listing_id)
        if _dry_note(l, f"set quantity to {qty} ({reason})"):
            return False
        if _live(l):
            api.update_price_quantity(l.sku, l.offer_id, quantity=qty)
        l.quantity = qty
        if status:
            l.status = status
        l.status_reason = reason
        activity.info("stock", f"Quantity → {qty} on '{l.title}' ({reason})", asin=l.asin, listing_id=l.id)
        return True


def set_price(listing_id: int, price: float, reason: str) -> bool:
    with session_scope() as s:
        l = s.get(Listing, listing_id)
        old = l.price
        if _dry_note(l, f"change price ${old:.2f} → ${price:.2f} ({reason})"):
            return False
        if _live(l):
            api.update_price_quantity(l.sku, l.offer_id, price=price)
        l.price = price
        activity.info("price", f"Price ${old:.2f} → ${price:.2f} on '{l.title}' ({reason})", asin=l.asin, listing_id=l.id)
        return True


def restore(listing_id: int, price: float, reason: str) -> bool:
    qty = int(st.get("listing_quantity"))
    with session_scope() as s:
        l = s.get(Listing, listing_id)
        if _dry_note(l, f"restore quantity {qty} at ${price:.2f} ({reason})"):
            return False
        if _live(l):
            api.update_price_quantity(l.sku, l.offer_id, quantity=qty, price=price)
        l.quantity, l.price = qty, price
        l.status = "active"
        l.status_reason = ""
        activity.info("stock", f"Restored '{l.title}' to quantity {qty} at ${price:.2f} ({reason})",
                      asin=l.asin, listing_id=l.id)
        return True


def end_listing(listing_id: int, reason: str) -> bool:
    with session_scope() as s:
        l = s.get(Listing, listing_id)
        if l.status == "ended":
            return True
        if _dry_note(l, f"end the listing ({reason})"):
            return False
        if _live(l):
            api.withdraw_offer(l.offer_id)
        l.status, l.status_reason, l.ended_at = "ended", reason, utcnow()
        activity.info("ended", f"Ended '{l.title}' ({reason})", asin=l.asin, listing_id=l.id)
        return True


ENDED_STATUSES = {"ENDED": "ended on eBay", "EBAY_ENDED": "ended by eBay (check Seller Hub for why)"}


def sync_status() -> dict:
    """Notice listings you ended yourself on eBay (or eBay ended) and mark them ended here too. Read-only on eBay."""
    from ..ebay.client import EbayError, EbayNotConnected

    env = st.get("ebay_environment")
    with session_scope() as s:
        rows = [(l.id, l.offer_id, l.title) for l in s.query(Listing).filter(
            Listing.environment == env, Listing.dry_run.is_(False), Listing.offer_id.isnot(None), Listing.status != "ended")]
    ended = 0
    for lid, offer_id, title in rows:
        try:
            offer = api.get_offer(offer_id)
        except EbayNotConnected as exc:
            return {"skipped": str(exc)}
        except EbayError as exc:
            activity.warning("ebay", f"Could not check eBay status of '{title[:60]}': {exc}", listing_id=lid)
            continue
        if offer is None:
            reason = "removed on eBay"
        else:
            listing_status = ((offer.get("listing") or {}).get("listingStatus") or "").upper()
            reason = ENDED_STATUSES.get(listing_status)
            if reason is None and offer.get("status") == "UNPUBLISHED":
                reason = "ended on eBay"
        if not reason:
            continue
        with session_scope() as s:
            l = s.get(Listing, lid)
            l.status, l.status_reason, l.ended_at = "ended", reason, utcnow()
            if reason.startswith("ended by eBay"):
                l.flagged, l.flag_reason = True, reason
        ended += 1
        (activity.warning if reason.startswith("ended by eBay") else activity.info)(
            "ended", f"'{title[:60]}' was {reason} — marked ended here too", listing_id=lid)
    return {"checked": len(rows), "ended": ended}


def flag(listing_id: int, reason: str) -> None:
    with session_scope() as s:
        l = s.get(Listing, listing_id)
        l.flagged, l.flag_reason = True, reason
    activity.warning("price", f"Flagged listing #{listing_id}: {reason}", listing_id=listing_id)
