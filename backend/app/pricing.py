"""Pricing engine — implements the spec formula exactly.

    amazon_cost = amazon_price × (1 + sales_tax_percent/100)
    raw_price   = amazon_cost × margin_multiplier × (1 + ebay_fee_percent/100)
                  × (1 + promo_rate_percent/100) + ebay_fee_fixed_per_order
    ebay_price  = round_to_99(raw_price)

    ebay_fees   = (ebay_price × (1 + buyer_tax_estimate/100)) × ebay_fee_percent/100 + ebay_fee_fixed_per_order
    promo_fee   = ebay_price × promo_rate_percent/100
    profit      = ebay_price − amazon_cost − ebay_fees − promo_fee

Profit % (min_profit_percent) is ROI: profit ÷ amazon_cost × 100.
All arithmetic uses Decimal; values are only rounded to cents for output.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal
from typing import Any

D = Decimal
CENT = D("0.01")
HUNDRED = D(100)
NINETY_NINE = D("0.99")


def _d(x: Any) -> Decimal:
    return x if isinstance(x, Decimal) else D(str(x))


def money(x: Decimal) -> float:
    return float(_d(x).quantize(CENT, rounding=ROUND_HALF_UP))


@dataclass(frozen=True)
class PricingParams:
    margin_multiplier: float = 1.20
    ebay_fee_percent: float = 13.6
    ebay_fee_fixed_per_order: float = 0.40
    promo_rate_percent: float = 5.0
    sales_tax_percent: float = 6.0
    buyer_tax_estimate: float = 6.0
    min_profit_dollars: float | None = None
    min_profit_percent: float | None = None
    rounding_mode: str = "next_dollar_99"

    @classmethod
    def from_settings(cls, settings: dict) -> "PricingParams":
        return cls(**{k: settings[k] for k in cls.__dataclass_fields__ if k in settings})


def round_to_99(raw_price: Any, mode: str = "next_dollar_99") -> Decimal:
    """next_dollar_99: whole-dollar part + 1, ending in .99   (13.78 → 14.99, 9.05 → 10.99)
    nearest_99_above: smallest X.99 that is ≥ raw_price      (13.78 → 13.99)"""
    raw = _d(raw_price)
    whole = raw.to_integral_value(rounding=ROUND_FLOOR)
    if mode == "next_dollar_99":
        return whole + 1 + NINETY_NINE
    if mode == "nearest_99_above":
        candidate = whole + NINETY_NINE
        return candidate if candidate >= raw else candidate + 1
    raise ValueError(f"unknown rounding mode {mode!r}")


def amazon_cost(amazon_price: Any, p: PricingParams) -> Decimal:
    return _d(amazon_price) * (1 + _d(p.sales_tax_percent) / HUNDRED)


def profit_for(ebay_price: Any, cost: Any, p: PricingParams, buyer_tax_percent: Any | None = None) -> dict:
    """True profit check for a given eBay price and Amazon cost (cost already includes Amazon tax)."""
    price, cost = _d(ebay_price), _d(cost)
    bt = _d(p.buyer_tax_estimate if buyer_tax_percent is None else buyer_tax_percent)
    fee_basis = price * (1 + bt / HUNDRED)
    fvf = fee_basis * _d(p.ebay_fee_percent) / HUNDRED
    ebay_fees = fvf + _d(p.ebay_fee_fixed_per_order)
    promo_fee = price * _d(p.promo_rate_percent) / HUNDRED
    profit = price - cost - ebay_fees - promo_fee
    roi = (profit / cost * HUNDRED) if cost > 0 else D(0)
    return {
        "fee_basis_incl_buyer_tax": money(fee_basis),
        "ebay_fee_variable": money(fvf),
        "ebay_fee_fixed": money(_d(p.ebay_fee_fixed_per_order)),
        "ebay_fees": money(ebay_fees),
        "promo_fee": money(promo_fee),
        "profit": money(profit),
        "profit_percent": float(roi.quantize(D("0.1"), rounding=ROUND_HALF_UP)),
        "_profit_exact": profit,
        "_roi_exact": roi,
    }


def floor_failures(profit: Decimal, roi: Decimal, p: PricingParams) -> list[str]:
    reasons = []
    if p.min_profit_dollars is not None and profit < _d(p.min_profit_dollars):
        reasons.append(f"profit ${money(profit):.2f} is below the ${float(p.min_profit_dollars):.2f} minimum")
    if p.min_profit_percent is not None and roi < _d(p.min_profit_percent):
        reasons.append(f"profit {float(roi):.1f}% of cost is below the {float(p.min_profit_percent):.1f}% minimum")
    return reasons


def calculate(amazon_price: Any, p: PricingParams) -> dict:
    """Full price breakdown for one Amazon price, including the profit-floor verdict."""
    if amazon_price is None or _d(amazon_price) <= 0:
        raise ValueError("Amazon price must be a positive number")
    price = _d(amazon_price)
    tax = price * _d(p.sales_tax_percent) / HUNDRED
    cost = price + tax
    after_margin = cost * _d(p.margin_multiplier)
    after_fee = after_margin * (1 + _d(p.ebay_fee_percent) / HUNDRED)
    after_promo = after_fee * (1 + _d(p.promo_rate_percent) / HUNDRED)
    raw = after_promo + _d(p.ebay_fee_fixed_per_order)
    final = round_to_99(raw, p.rounding_mode)
    prof = profit_for(final, cost, p)
    reasons = floor_failures(prof.pop("_profit_exact"), prof.pop("_roi_exact"), p)
    return {
        "amazon_price": money(price),
        "sales_tax_percent": float(p.sales_tax_percent),
        "amazon_sales_tax": money(tax),
        "amazon_cost": money(cost),
        "margin_multiplier": float(p.margin_multiplier),
        "after_margin": money(after_margin),
        "ebay_fee_percent": float(p.ebay_fee_percent),
        "after_ebay_fee_gross_up": money(after_fee),
        "promo_rate_percent": float(p.promo_rate_percent),
        "after_promo_gross_up": money(after_promo),
        "ebay_fee_fixed_per_order": float(p.ebay_fee_fixed_per_order),
        "raw_price": float(raw.quantize(D("0.0001"), rounding=ROUND_HALF_UP)),
        "rounding_mode": p.rounding_mode,
        "rounding_added": money(final - raw),
        "ebay_price": money(final),
        "buyer_tax_estimate": float(p.buyer_tax_estimate),
        **prof,
        "min_profit_dollars": p.min_profit_dollars,
        "min_profit_percent": p.min_profit_percent,
        "passes_floor": not reasons,
        "floor_reasons": reasons,
        "params": asdict(p),
    }
