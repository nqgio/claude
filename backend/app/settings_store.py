"""Typed, DB-backed settings. Every behavior knob lives here and is editable
from the dashboard Settings page. The schema doubles as the form definition the
frontend renders."""
from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field
from typing import Any

from .db import session_scope
from .models import Setting


@dataclass
class Spec:
    key: str
    default: Any
    type: str  # bool|float|int|str|time|choice|list|optional_float
    group: str
    label: str
    help: str = ""
    choices: list[tuple[str, str]] = field(default_factory=list)
    min: float | None = None
    max: float | None = None
    hidden: bool = False  # internal state, not shown on the Settings page


SPECS: list[Spec] = [
    # --- General / safety -------------------------------------------------
    Spec("dry_run", True, "bool", "general", "Dry-run mode",
         "When ON the app finds, prices and previews listings but never creates or changes anything on eBay."),
    Spec("ebay_environment", "sandbox", "choice", "general", "eBay environment",
         "Sandbox uses eBay's test site and your sandbox keys. Production is your real store.",
         choices=[("sandbox", "Sandbox (testing)"), ("production", "Production (live store)")]),
    Spec("marketplace_id", "EBAY_US", "str", "general", "eBay marketplace", hidden=True),
    Spec("product_source", "amazon_playwright", "choice", "general", "Product data source",
         "Where product data comes from. 'Offline sample data' uses bundled demo pages and never contacts Amazon.",
         choices=[("amazon_playwright", "Amazon"), ("sample", "Sample data (offline)")]),

    # --- Pricing ------------------------------------------------------------
    Spec("margin_multiplier", 1.20, "float", "pricing", "Margin multiplier", "e.g. 1.20 = 20% markup on Amazon cost.", min=1.0, max=5.0),
    Spec("ebay_fee_percent", 13.6, "float", "pricing", "eBay final value fee %", "Your category's final value fee rate.", min=0, max=50),
    Spec("ebay_fee_fixed_per_order", 0.40, "float", "pricing", "eBay fixed fee per order ($)", min=0, max=10),
    Spec("promo_rate_percent", 5.0, "float", "pricing", "Promoted Listings ad rate %", "Also used as the campaign ad rate.", min=0, max=100),
    Spec("sales_tax_percent", 6.0, "float", "pricing", "Sales tax Amazon charges you %", "Virginia 6.0% by default.", min=0, max=20),
    Spec("buyer_tax_estimate", 6.0, "float", "pricing", "Buyer sales tax estimate %",
         "eBay charges its fee on the order total including the buyer's sales tax.", min=0, max=20),
    Spec("min_profit_dollars", 3.00, "optional_float", "pricing", "Minimum profit per sale ($)", "Leave blank to disable.", min=0),
    Spec("min_profit_percent", None, "optional_float", "pricing", "Minimum profit % (ROI on Amazon cost)",
         "profit ÷ Amazon cost incl. tax. Leave blank to disable.", min=0),
    Spec("rounding_mode", "next_dollar_99", "choice", "pricing", "Price rounding",
         choices=[("next_dollar_99", "Next dollar .99 (13.78 → 14.99)"), ("nearest_99_above", "Nearest .99 above (13.78 → 13.99)")]),

    # --- Finder / auto-lister -----------------------------------------------
    Spec("listings_per_day", 8, "int", "lister", "Listings per day", min=0, max=500),
    Spec("posting_window_start", "08:00", "time", "lister", "Posting window start (local time)"),
    Spec("posting_window_end", "22:00", "time", "lister", "Posting window end (local time)"),
    Spec("discovery_time", "07:30", "time", "lister", "Daily queue build time (local time)"),
    Spec("search_keywords", [], "list", "lister", "Search keywords", "One per line."),
    Spec("search_categories", [], "list", "lister", "Amazon categories",
         "One per line: a search alias (e.g. 'kitchen', 'garden', 'toys-and-games') or a browse node like 'node:284507'."),
    Spec("search_pages_per_term", 2, "int", "lister", "Result pages per keyword/category", min=1, max=10),
    Spec("queue_backup_factor", 2.0, "float", "lister", "Queue size factor",
         "Queue holds listings_per_day × this many products so failures have backups.", min=1, max=5),
    Spec("filter_min_price", 10.0, "float", "filters", "Min Amazon price ($)", min=0),
    Spec("filter_max_price", 80.0, "float", "filters", "Max Amazon price ($)", min=0),
    Spec("filter_min_rating", 4.0, "float", "filters", "Min rating", min=0, max=5),
    Spec("filter_min_reviews", 100, "int", "filters", "Min review count", min=0),
    Spec("filter_prime_only", True, "bool", "filters", "Prime only"),
    Spec("filter_in_stock_only", True, "bool", "filters", "In-stock only"),
    Spec("filter_max_shipping_days", 5, "int", "filters", "Max Amazon shipping days", "0 = don't check.", min=0, max=60),

    # --- Listing defaults ---------------------------------------------------
    Spec("listing_quantity", 1, "int", "listing", "Quantity per listing", min=1, max=100),
    Spec("handling_time_days", 1, "int", "listing", "Handling time (business days)",
         "Handling time comes from the shipping policy; the app warns if the selected policy doesn't match.", min=0, max=30),
    Spec("fulfillment_policy_id", "", "str", "listing", "Shipping policy"),
    Spec("return_policy_id", "", "str", "listing", "Return policy"),
    Spec("payment_policy_id", "", "str", "listing", "Payment policy"),
    Spec("item_location_zip", "", "str", "listing", "Item location ZIP"),
    Spec("item_location_city", "", "str", "listing", "Item location city (optional)"),
    Spec("item_location_state", "", "str", "listing", "Item location state, 2 letters (optional)"),
    Spec("merchant_location_key", "default-location", "str", "listing", "Inventory location key", hidden=True),
    Spec("promoted_listings_enabled", True, "bool", "listing", "Add new listings to Promoted Listings"),
    Spec("promo_campaign_name", "Auto Listings", "str", "listing", "Promoted Listings campaign name"),
    Spec("description_template", "", "text", "listing", "Description template (HTML, optional)",
         "Blank = built-in layout. Placeholders: {{title}} {{overview}} {{highlights}} {{specs}} {{brand}} "
         "{{handling_days}} {{img1}} {{img2}} {{img3}}. Scripts are removed (eBay doesn't allow them)."),
    Spec("ai_content_enabled", False, "bool", "listing", "Write titles/descriptions with Claude",
         "Needs ANTHROPIC_API_KEY in .env. Falls back to the built-in writer on any error."),
    Spec("ai_model", "claude-opus-5-5", "str", "listing", "Claude model for listing content"),

    # --- Amazon scraper -----------------------------------------------------
    Spec("amazon_max_pages_per_hour", 20, "int", "amazon", "Max Amazon pages per hour", min=1, max=600),
    Spec("amazon_min_delay_sec", 15.0, "float", "amazon", "Min delay between pages (sec)", min=1),
    Spec("amazon_max_delay_sec", 45.0, "float", "amazon", "Max delay between pages (sec)", min=1),
    Spec("amazon_cache_hours", 6.0, "float", "amazon", "Reuse cached product data for (hours)", min=0),
    Spec("amazon_cooldown_minutes", 180, "int", "amazon", "Pause after CAPTCHA/block (minutes)", min=5),
    Spec("amazon_headless", True, "bool", "amazon", "Run Amazon browser hidden (headless)"),
    Spec("amazon_paused_until", None, "str", "amazon", "", hidden=True),
    Spec("amazon_pause_reason", "", "str", "amazon", "", hidden=True),
    Spec("amazon_blocked_url", "", "str", "amazon", "", hidden=True),

    # --- Refresh ------------------------------------------------------------
    Spec("refresh_enabled", True, "bool", "refresh", "Auto refresh on",
         "Re-check every listing's Amazon price and stock on the schedule below."),
    Spec("refresh_auto_apply", True, "bool", "refresh", "Apply changes to eBay automatically",
         "Off = only record and flag what changed so you can review it; nothing on eBay is updated by the refresh."),
    Spec("refresh_mode", "daily_at", "choice", "refresh", "Refresh schedule",
         choices=[("daily_at", "Every day at a set time"), ("weekly", "Once a week on a set day and time"),
                  ("every_n_hours", "Every N hours")]),
    Spec("refresh_time", "03:00", "time", "refresh", "Refresh time (local, for daily/weekly)"),
    Spec("refresh_day", "sun", "choice", "refresh", "Day of the week (weekly)",
         choices=[("mon", "Monday"), ("tue", "Tuesday"), ("wed", "Wednesday"), ("thu", "Thursday"), ("fri", "Friday"),
                  ("sat", "Saturday"), ("sun", "Sunday")]),
    Spec("refresh_every_hours", 6, "int", "refresh", "Refresh every N hours", min=1, max=168),
    Spec("oos_action", "zero_quantity", "choice", "refresh", "When Amazon is out of stock",
         choices=[("zero_quantity", "Set eBay quantity to 0"), ("end", "End the listing")]),
    Spec("below_floor_action", "zero_quantity", "choice", "refresh", "When profit drops below the floor",
         choices=[("zero_quantity", "Set eBay quantity to 0"), ("end", "End the listing"), ("flag", "Just flag it")]),

    # --- Orders -------------------------------------------------------------
    Spec("checkout_mode", "assisted", "choice", "orders", "Checkout mode",
         choices=[("assisted", "Assisted (I buy on Amazon, app helps)"), ("auto", "Auto (app places the Amazon order)")]),
    Spec("amazon_rotation", "round_robin", "choice", "accounts", "Amazon account rotation",
         "How auto-buy picks which of your Amazon accounts places each order.",
         choices=[("round_robin", "Take turns"), ("least_used_today", "Least used today")]),
    Spec("auto_buy_kill_switch", False, "bool", "orders", "Auto-buy kill switch (stop all auto orders)"),
    Spec("auto_buy_max_order_dollars", 75.0, "float", "orders", "Max auto-order total ($)", min=0),
    Spec("auto_buy_max_per_day", 5, "int", "orders", "Max auto-orders per day", min=0),
    Spec("auto_buy_max_spend_per_day", None, "optional_float", "orders", "Max auto-buy spending per day ($)",
         "Leave blank for no daily cap.", min=0),
    Spec("auto_buy_require_free_delivery", True, "bool", "orders", "Hold auto-buy if Amazon delivery isn't free",
         "Off = buy anyway as long as the order is still profitable after the delivery charge."),
    Spec("orders_sync_minutes", 10, "int", "orders", "Check eBay for orders every (minutes)", min=2, max=240),
    Spec("tracking_check_hours", 2, "int", "orders", "Check Amazon for tracking every (hours)", min=1, max=48),
    Spec("orders_last_sync", None, "str", "orders", "", hidden=True),

    # --- Blocklist ----------------------------------------------------------
    Spec("blocklist_scan_action", "flag", "choice", "blocklist", "Active-listing scan action",
         choices=[("flag", "Flag matches"), ("end", "End matches")]),

    # --- internal state -----------------------------------------------------
    Spec("last_queue_build_date", None, "str", "internal", "", hidden=True),
    Spec("ebay_refresh_token_expires", {}, "dict", "internal", "", hidden=True),
    Spec("ebay_campaign_ids", {}, "dict", "internal", "", hidden=True),
    Spec("ebay_location_ready", {}, "dict", "internal", "", hidden=True),
]

SPEC_BY_KEY = {s.key: s for s in SPECS}
_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")
_cache: dict[str, Any] | None = None
_lock = threading.RLock()


class SettingsError(ValueError):
    pass


def coerce(spec: Spec, value: Any) -> Any:
    t = spec.type
    if t == "bool":
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "yes", "on")
        return bool(value)
    if t in ("float", "int", "optional_float"):
        if value is None or (isinstance(value, str) and value.strip() == ""):
            if t == "optional_float":
                return None
            raise SettingsError(f"{spec.label or spec.key} is required")
        try:
            num = float(value)
        except (TypeError, ValueError):
            raise SettingsError(f"{spec.label or spec.key} must be a number")
        if spec.min is not None and num < spec.min:
            raise SettingsError(f"{spec.label or spec.key} must be ≥ {spec.min}")
        if spec.max is not None and num > spec.max:
            raise SettingsError(f"{spec.label or spec.key} must be ≤ {spec.max}")
        return int(num) if t == "int" else num
    if t == "time":
        value = str(value).strip()
        m = _TIME_RE.match(value)
        if not m:
            raise SettingsError(f"{spec.label} must be HH:MM (24h)")
        return f"{int(m.group(1)):02d}:{m.group(2)}"
    if t == "choice":
        if value not in [c[0] for c in spec.choices]:
            raise SettingsError(f"{spec.label}: invalid choice {value!r}")
        return value
    if t == "list":
        if isinstance(value, str):
            value = value.splitlines()
        return [str(v).strip() for v in (value or []) if str(v).strip()]
    if t == "dict":
        return dict(value or {})
    return None if value is None else str(value).strip()


def _load() -> dict[str, Any]:
    global _cache
    with _lock:
        if _cache is None:
            data = {s.key: s.default for s in SPECS}
            with session_scope() as s:
                for row in s.query(Setting).all():
                    if row.key in data:
                        data[row.key] = row.value
            _cache = data
        return _cache


def get(key: str) -> Any:
    return _load()[key]


def all_settings(include_hidden: bool = False) -> dict[str, Any]:
    data = dict(_load())
    if not include_hidden:
        data = {k: v for k, v in data.items() if not SPEC_BY_KEY[k].hidden}
    return data


def update(values: dict[str, Any], allow_hidden: bool = False) -> dict[str, Any]:
    """Validate + save. Raises SettingsError without saving anything if any value is invalid."""
    clean: dict[str, Any] = {}
    for key, value in values.items():
        spec = SPEC_BY_KEY.get(key)
        if spec is None or (spec.hidden and not allow_hidden):
            continue
        clean[key] = coerce(spec, value)
    merged = {**_load(), **clean}
    if merged["amazon_min_delay_sec"] > merged["amazon_max_delay_sec"]:
        raise SettingsError("Min delay between pages can't be larger than max delay")
    if merged["filter_min_price"] > merged["filter_max_price"]:
        raise SettingsError("Min Amazon price can't be larger than max price")
    if merged["posting_window_start"] >= merged["posting_window_end"]:
        raise SettingsError("Posting window start must be before its end")
    with _lock:
        with session_scope() as s:
            for key, value in clean.items():
                row = s.get(Setting, key)
                if row is None:
                    s.add(Setting(key=key, value=value))
                else:
                    row.value = value
        _cache.update(clean)
    return clean


def set_internal(key: str, value: Any) -> None:
    update({key: value}, allow_hidden=True)


def reset_cache() -> None:
    global _cache
    with _lock:
        _cache = None


def schema() -> list[dict]:
    return [
        {"key": s.key, "type": s.type, "group": s.group, "label": s.label, "help": s.help,
         "choices": [{"value": v, "label": l} for v, l in s.choices], "min": s.min, "max": s.max, "default": s.default}
        for s in SPECS if not s.hidden
    ]
