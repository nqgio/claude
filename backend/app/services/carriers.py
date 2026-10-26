"""Carrier detection for tracking numbers. Only UPS, USPS and FedEx are uploaded
to eBay; Amazon Logistics (TBA…) numbers are never uploaded or substituted."""
from __future__ import annotations

import re

EBAY_CODES = {"UPS": "UPS", "USPS": "USPS", "FEDEX": "FedEx"}

_PATTERNS = [
    ("AMAZON", re.compile(r"^TBA\d{9,14}$")),
    ("UPS", re.compile(r"^1Z[0-9A-Z]{16}$")),
    ("USPS", re.compile(r"^(?:9[1-5]\d{18,24}|[A-Z]{2}\d{9}US|420\d{5}(?:\d{4})?9[1-5]\d{18,24})$")),
    ("FEDEX", re.compile(r"^(?:\d{12}|\d{15}|\d{20}|\d{22})$")),
]


def detect(tracking: str, carrier_text: str = "") -> str:
    """Return AMAZON | UPS | USPS | FEDEX | OTHER."""
    t = re.sub(r"\s+", "", tracking or "").upper()
    if t.startswith("TBA"):
        return "AMAZON"
    c = (carrier_text or "").strip().upper().replace(" ", "")
    if "AMAZON" in c:
        return "AMAZON"
    if c in ("UPS", "USPS", "FEDEX"):
        return c
    for name, pat in _PATTERNS:
        if pat.match(t):
            return name
    return "OTHER"


def ebay_code(carrier: str) -> str | None:
    return EBAY_CODES.get(carrier.upper())
