"""Shared product qualification: filters, blocklist and the pricing/profit floor."""
from __future__ import annotations

from ..blocklist import Blocklist
from ..pricing import PricingParams, calculate
from ..providers.base import ProductData, SearchResult
from .. import settings_store as st


def pricing_params() -> PricingParams:
    return PricingParams.from_settings(st.all_settings(include_hidden=True))


def search_result_reasons(r: SearchResult) -> list[str]:
    """Cheap pre-filter on the search results page (before opening the product page)."""
    s = st.all_settings()
    out = []
    if r.price is not None and not (s["filter_min_price"] <= r.price <= s["filter_max_price"]):
        out.append(f"price ${r.price:.2f} outside ${s['filter_min_price']:.2f}–${s['filter_max_price']:.2f}")
    if r.rating is not None and r.rating < s["filter_min_rating"]:
        out.append(f"rating {r.rating} below {s['filter_min_rating']}")
    if r.review_count is not None and r.review_count < s["filter_min_reviews"]:
        out.append(f"{r.review_count} reviews below {s['filter_min_reviews']}")
    return out


def product_filter_reasons(p: ProductData) -> list[str]:
    s = st.all_settings()
    out = []
    if p.price is None:
        out.append("no price shown")
    elif not (s["filter_min_price"] <= p.price <= s["filter_max_price"]):
        out.append(f"price ${p.price:.2f} outside ${s['filter_min_price']:.2f}–${s['filter_max_price']:.2f}")
    if s["filter_in_stock_only"] and not p.in_stock:
        out.append(f"not in stock ({p.availability_text or 'no availability shown'})")
    if s["filter_prime_only"] and not p.prime:
        out.append("not Prime eligible")
    if p.rating is None or p.rating < s["filter_min_rating"]:
        out.append(f"rating {p.rating} below {s['filter_min_rating']}")
    if (p.review_count or 0) < s["filter_min_reviews"]:
        out.append(f"{p.review_count or 0} reviews below {s['filter_min_reviews']}")
    max_days = int(s["filter_max_shipping_days"])
    if max_days and p.delivery_days is not None and p.delivery_days > max_days:
        out.append(f"Amazon delivery in {p.delivery_days} days (max {max_days})")
    return out


def evaluate(p: ProductData, apply_filters: bool = True, blocklist: Blocklist | None = None,
             ignore_blocklist: bool = False) -> dict:
    """Always enforces stock, blocklist and profit floor; `apply_filters=False` (manual add with
    'force') skips only the search filters (price range, rating, reviews, Prime, shipping days)."""
    reasons = product_filter_reasons(p) if apply_filters else []
    if not apply_filters and not p.in_stock:
        reasons.append("not in stock")
    match = None
    if not ignore_blocklist:  # you checked this one yourself and chose "Post anyway"
        bl = blocklist or Blocklist.load()
        match = bl.check(p.brand, p.title, " ".join(p.features) + " " + p.description)
    if match:
        reasons.append(match.reason())
    breakdown = None
    if p.price:
        breakdown = calculate(p.price, pricing_params())
        if not breakdown["passes_floor"]:
            reasons.extend(breakdown["floor_reasons"])
    return {"ok": not reasons, "reasons": reasons, "breakdown": breakdown, "blocklisted": bool(match)}
