"""Competitor price check: what other eBay sellers charge for the same product (official Browse API, read-only).

Rules (confirmed with you):
- Nobody cheaper than your normal price → keep your normal price.
- Someone cheaper, but you can go just under them (the next .99 below) and still clear your minimum profit
  → use that price.
- Someone cheaper than you can profitably go → skip the product (or, for a live listing, set quantity 0).

Only the *same* product counts: same pack size, the brand in the title (unless the match is very close),
most of the title's words, and not a cheap part or accessory. Your own listings are never compared.
"""
from __future__ import annotations

import re

from .. import activity
from .. import settings_store as st
from ..ebay import api as ebay
from ..ebay.client import EbayError, keys as ebay_keys
from ..pricing import at_price, largest_99_below
from .evaluate import pricing_params

STOP = {"the", "and", "for", "with", "of", "a", "an", "to", "in", "on", "by", "or", "set", "pack", "pcs", "piece",
        "pieces", "new", "inch", "inches", "in", "ft", "x", "black", "white", "home", "use", "kit"}
GENERIC_BRANDS = {"", "generic", "unbranded", "unknown", "na", "n a", "none"}
MIN_WORD_MATCH = 0.6        # share of our title's first 8 key words that must appear in theirs
MIN_WORD_MATCH_NO_BRAND = 0.8
MIN_PRICE_SHARE = 0.5       # cheaper than half the Amazon price → a part/accessory, not the same product


def _words(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(w) > 1 and w not in STOP]


def pack_count(title: str) -> int | None:
    t = (title or "").lower()
    for pat in (r"(\d+)\s*[- ]?\s*(?:pack|pk|pcs|pieces|count|ct)\b", r"(?:pack|set) of (\d+)", r"\b(\d+)\s*-?\s*piece"):
        m = re.search(pat, t)
        if m:
            return int(m.group(1))
    return None


def _total(item: dict) -> float | None:
    try:
        price = float(item["price"]["value"])
    except (KeyError, TypeError, ValueError):
        return None
    ship = 0.0
    opts = item.get("shippingOptions") or []
    if opts:
        try:
            ship = min(float((o.get("shippingCost") or {}).get("value") or 0) for o in opts)
        except (TypeError, ValueError):
            ship = 0.0
    return round(price + ship, 2)


def same_product(ours_title: str, brand: str, amazon_price: float, item: dict, by_gtin: bool = False) -> bool:
    theirs = item.get("title", "")
    a, b = pack_count(ours_title) or 1, pack_count(theirs) or 1
    if a != b:
        return False
    total = _total(item)
    if total is None or total < amazon_price * MIN_PRICE_SHARE:
        return False
    if by_gtin:
        return True
    key = list(dict.fromkeys(_words(ours_title)))[:8]  # Amazon titles lead with the product name
    if not key:
        return False
    theirs_words = set(_words(theirs))
    share = sum(1 for w in key if w in theirs_words) / len(key)
    brand_words = _words(brand)
    if brand_words and " ".join(brand_words) not in GENERIC_BRANDS:
        if all(w in theirs_words for w in brand_words):
            return share >= MIN_WORD_MATCH
        return share >= MIN_WORD_MATCH_NO_BRAND
    return share >= MIN_WORD_MATCH_NO_BRAND


def cheapest_competitor(p, own_item_ids: set[str] | None = None) -> dict | None:
    """Cheapest matching competitor {price, title, url, seller} (price incl. shipping), or None."""
    own = {str(x) for x in (own_item_ids or set()) if x}
    upc = (p.details.get("UPC") or "").split()[0] if p.details.get("UPC") else ""
    batches = []
    if upc.isdigit() and len(upc) in (12, 13, 14):
        batches.append((ebay.search_items(gtin=upc), True))
    batches.append((ebay.search_items(query=" ".join(_words(p.title)[:10])), False))
    best = None
    for items, by_gtin in batches:
        for it in items:
            if str(it.get("legacyItemId") or "") in own or any(str(x) in str(it.get("itemId", "")) for x in own):
                continue
            if not same_product(p.title, p.brand, float(p.price or 0), it, by_gtin):
                continue
            total = _total(it)
            if best is None or total < best["price"]:
                best = {"price": total, "title": it.get("title", "")[:120], "url": it.get("itemWebUrl", ""),
                        "seller": (it.get("seller") or {}).get("username", "")}
    return best


def _own_ids() -> set[str]:
    from ..db import session_scope
    from ..models import Listing

    with session_scope() as s:
        return {r[0] for r in s.query(Listing.ebay_listing_id).filter(Listing.ebay_listing_id.isnot(None))}


def check(p, breakdown: dict) -> dict:
    """Decide the price against competitors. Returns {"action": "keep" | "undercut" | "skip", "breakdown", "reason"}.
    Never blocks on a lookup problem: if eBay can't be asked, your normal price is used."""
    if not st.get("competitor_check_enabled") or not p.price:
        return {"action": "keep", "breakdown": breakdown, "reason": ""}
    k = ebay_keys()
    if not (k["app_id"] and k["cert_id"]):
        return {"action": "keep", "breakdown": breakdown, "reason": "eBay keys not set"}
    try:
        comp = cheapest_competitor(p, _own_ids())
    except EbayError as exc:
        activity.warning("price", f"Competitor check unavailable for {p.asin}: {exc}", asin=p.asin)
        return {"action": "keep", "breakdown": breakdown, "reason": "lookup failed"}
    ours = breakdown["ebay_price"]
    if comp is None:
        return {"action": "keep", "breakdown": {**breakdown, "competitor": None}, "reason": "no competitors found"}
    if comp["price"] > ours:
        return {"action": "keep", "breakdown": {**breakdown, "competitor": comp}, "reason": "you're the cheapest"}
    target = float(largest_99_below(comp["price"]))
    nb = {**at_price(p.price, target, pricing_params()), "competitor": comp} if target > 0 else None
    if nb and nb["passes_floor"]:
        return {"action": "undercut", "breakdown": nb,
                "reason": f"cheapest similar on eBay is ${comp['price']:.2f}; priced at ${target:.2f}"}
    profit = f" (you'd make ${nb['profit']:.2f})" if nb else ""
    return {"action": "skip", "breakdown": {**breakdown, "competitor": comp},
            "reason": f"another eBay seller has it for ${comp['price']:.2f}; you can't go under that and keep your "
                      f"minimum profit{profit}"}
