"""Provider registry. To add a new product source, implement
`base.ProductProvider` and add it to `_FACTORIES` (plus a Settings choice)."""
from __future__ import annotations

import threading

from .base import ProductProvider

_instances: dict[str, ProductProvider] = {}
_lock = threading.Lock()


def _factories():
    from .amazon_playwright import AmazonPlaywrightProvider
    from .sample import SampleProvider

    return {"amazon_playwright": AmazonPlaywrightProvider, "sample": SampleProvider}


def get_provider(name: str | None = None) -> ProductProvider:
    from .. import settings_store as st

    name = name or st.get("product_source")
    with _lock:
        if name not in _instances:
            _instances[name] = _factories()[name]()
        return _instances[name]


def shutdown() -> None:
    with _lock:
        for p in _instances.values():
            p.close()
        _instances.clear()
