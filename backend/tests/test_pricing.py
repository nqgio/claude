from decimal import Decimal

import pytest

from app.pricing import PricingParams, calculate, profit_for, round_to_99


@pytest.mark.parametrize("raw,expected", [("13.78", "14.99"), ("9.05", "10.99"), ("22.50", "23.99"),
                                          ("13.00", "14.99"), ("13.99", "14.99"), ("0.10", "1.99")])
def test_next_dollar_99_examples(raw, expected):
    assert round_to_99(Decimal(raw), "next_dollar_99") == Decimal(expected)


@pytest.mark.parametrize("raw,expected", [("13.78", "13.99"), ("13.99", "13.99"), ("13.991", "14.99"),
                                          ("14.00", "14.99"), ("9.05", "9.99")])
def test_nearest_99_above(raw, expected):
    assert round_to_99(Decimal(raw), "nearest_99_above") == Decimal(expected)


def test_unknown_rounding_mode():
    with pytest.raises(ValueError):
        round_to_99("1.00", "bogus")


def P(**kw):
    base = dict(margin_multiplier=1.20, ebay_fee_percent=13.6, ebay_fee_fixed_per_order=0.40, promo_rate_percent=5.0,
                sales_tax_percent=6.0, buyer_tax_estimate=6.0, min_profit_dollars=None, min_profit_percent=None)
    base.update(kw)
    return PricingParams(**base)


def test_formula_matches_spec_step_by_step():
    b = calculate(13.99, P())
    cost = Decimal("13.99") * Decimal("1.06")
    raw = cost * Decimal("1.20") * Decimal("1.136") * Decimal("1.05") + Decimal("0.40")
    assert b["amazon_cost"] == float(cost.quantize(Decimal("0.01")))
    assert b["raw_price"] == pytest.approx(float(raw), abs=1e-4)
    assert b["ebay_price"] == 22.99  # raw 21.6262 → next dollar .99
    fees = Decimal("22.99") * Decimal("1.06") * Decimal("0.136") + Decimal("0.40")
    promo = Decimal("22.99") * Decimal("1.06") * Decimal("0.05")  # ad fee also on the tax-inclusive total
    profit = Decimal("22.99") - cost - fees - promo
    assert b["ebay_fees"] == float(fees.quantize(Decimal("0.01")))
    assert b["promo_fee"] == float(promo.quantize(Decimal("0.01")))
    assert b["profit"] == float(profit.quantize(Decimal("0.01")))  # 3.23
    assert b["profit"] == 3.23
    assert b["profit_percent"] == pytest.approx(float(profit / cost * 100), abs=0.05)  # ROI on cost


def test_nearest_mode_changes_final_price():
    assert calculate(13.99, P(rounding_mode="nearest_99_above"))["ebay_price"] == 21.99


def test_fee_charged_on_total_including_buyer_tax():
    no_tax = profit_for(20, 10, P(buyer_tax_estimate=0))
    with_tax = profit_for(20, 10, P(buyer_tax_estimate=6))
    assert with_tax["ebay_fees"] == pytest.approx(no_tax["ebay_fees"] + 20 * 0.06 * 0.136, abs=0.01)


def test_profit_floor_dollars():
    ok = calculate(13.99, P(min_profit_dollars=3.00))
    bad = calculate(13.99, P(min_profit_dollars=3.50))
    assert ok["passes_floor"] and not ok["floor_reasons"]
    assert not bad["passes_floor"] and "below the $3.50 minimum" in bad["floor_reasons"][0]


def test_profit_floor_percent_is_roi_on_amazon_cost():
    b = calculate(13.99, P())  # ROI ≈ 21.8%
    assert calculate(13.99, P(min_profit_percent=21.5))["passes_floor"]
    bad = calculate(13.99, P(min_profit_percent=25))
    assert not bad["passes_floor"] and "% of cost" in bad["floor_reasons"][0]
    assert 21.5 < b["profit_percent"] < 22


def test_profit_floor_both_and_neither():
    assert calculate(13.99, P())["passes_floor"]
    both = calculate(13.99, P(min_profit_dollars=5, min_profit_percent=50))
    assert len(both["floor_reasons"]) == 2


def test_zero_floor_is_a_real_floor():
    # a $0 floor still rejects a money-losing price; blank (None) disables the check
    from app.pricing import floor_failures

    assert floor_failures(Decimal("-0.01"), Decimal("-1"), P(min_profit_dollars=0))
    assert not floor_failures(Decimal("0"), Decimal("0"), P(min_profit_dollars=0))
    assert floor_failures(Decimal("-5"), Decimal("-50"), P()) == ["would lose money (profit $-5.00)"]  # even with floors off


def test_invalid_price():
    with pytest.raises(ValueError):
        calculate(0, P())
