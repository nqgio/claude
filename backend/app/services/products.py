"""Product fetch with a DB cache in front of the provider."""
from __future__ import annotations

import hashlib
import json
from datetime import timedelta

from ..db import session_scope
from ..models import Product, utcnow
from ..providers import get_provider
from ..providers.base import ProductData
from .. import settings_store as st


def _to_data(p: Product) -> ProductData:
    return ProductData(asin=p.asin, url=p.url, title=p.title, brand=p.brand, price=p.price, in_stock=p.in_stock,
                       availability_text=p.availability_text, prime=p.prime, rating=p.rating,
                       review_count=p.review_count, category=p.category, images=list(p.images or []),
                       features=list(p.features or []), details=dict(p.details or {}), description=p.description,
                       delivery_days=p.delivery_days)


# Bump when the Amazon page reader changes how it reads pages: cached product data from the old
# reader is then fetched again instead of being reused.
PARSER_VERSION = 2


def refresh_cache_if_parser_changed() -> int:
    if (st.get("product_parser_version") or 1) >= PARSER_VERSION:
        return 0
    from datetime import datetime

    with session_scope() as s:
        n = s.query(Product).update({Product.fetched_at: datetime(2000, 1, 1)})
    st.set_internal("product_parser_version", PARSER_VERSION)
    return n


def cached(asin: str) -> ProductData | None:
    with session_scope() as s:
        p = s.get(Product, asin)
        return _to_data(p) if p else None


def fetch(asin: str, max_age_hours: float | None = None) -> tuple[ProductData, bool]:
    """Return (product, changed). Uses the cache if it is fresher than `max_age_hours`
    (defaults to the Settings value). `changed` is False when data is identical to the cache."""
    max_age = float(st.get("amazon_cache_hours") if max_age_hours is None else max_age_hours)
    with session_scope() as s:
        p = s.get(Product, asin)
        if p and max_age > 0 and utcnow() - p.fetched_at < timedelta(hours=max_age):
            return _to_data(p), False
    provider = get_provider()
    data = provider.get_product(asin)
    digest = hashlib.sha256(json.dumps(data.to_dict(), sort_keys=True, default=str).encode()).hexdigest()
    with session_scope() as s:
        p = s.get(Product, asin)
        changed = p is None or p.content_hash != digest
        if p is None:
            p = Product(asin=asin)
            s.add(p)
        for k, v in data.to_dict().items():
            setattr(p, k, v)
        p.source = provider.name
        p.content_hash = digest
        p.fetched_at = utcnow()
    return data, changed
