"""End-to-end: discovery → queue → dry-run post → refresh, on offline sample data,
then live mode against a mocked eBay API."""
import json
import os

import httpx
import pytest

from app import settings_store as st
from app.db import session_scope
from app.ebay import api as ebay
from app.ebay import client
from app.models import ActivityLog, Listing, Order, QueueItem
from app.providers import sample
from app.services import metrics, orders, queue, refresh


@pytest.fixture
def calls():
    """Mock eBay. Records every request; fails the test on any unexpected endpoint."""
    log = []

    def handler(req: httpx.Request):
        path, m = req.url.path, req.method
        body = json.loads(req.content) if req.content and req.headers.get("content-type", "").startswith("application/json") else None
        log.append((m, path, dict(req.url.params), body))
        if path.endswith("/oauth2/token"):
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 7200})
        if path.endswith("get_default_category_tree_id"):
            return httpx.Response(200, json={"categoryTreeId": "0"})
        if path.endswith("get_category_suggestions"):
            return httpx.Response(200, json={"categorySuggestions": [{"category": {"categoryId": "20625", "categoryName": "Garlic Presses"},
                                                                      "categoryTreeNodeAncestors": [{"categoryName": "Kitchen Tools"}]}]})
        if path.endswith("get_item_aspects_for_category"):
            return httpx.Response(200, json={"aspects": [{"localizedAspectName": "Brand", "aspectConstraint": {"aspectRequired": True}}]})
        if "/location/" in path:
            return httpx.Response(404 if m == "GET" else 204, json={} if m == "GET" else None)
        if "/inventory_item/" in path:
            return httpx.Response(204)
        if path.endswith("/offer") and m == "GET":
            return httpx.Response(404, json={"errors": [{"message": "not found"}]})
        if path.endswith("/offer") and m == "POST":
            return httpx.Response(201, json={"offerId": "OFFER1"})
        if path.endswith("/publish"):
            return httpx.Response(200, json={"listingId": "110000000001"})
        if path.endswith("get_campaign_by_name"):
            return httpx.Response(404, json={"errors": [{"message": "none"}]})
        if path.endswith("/ad_campaign"):
            return httpx.Response(201, headers={"Location": "https://api.sandbox.ebay.com/sell/marketing/v1/ad_campaign/CAMP1"})
        if path.endswith("/ad"):
            return httpx.Response(201, headers={"Location": "https://x/ad_campaign/CAMP1/ad/AD1"})
        if path.endswith("bulk_update_price_quantity"):
            return httpx.Response(200, json={"responses": [{"statusCode": 200}]})
        if path.endswith("/withdraw"):
            return httpx.Response(200, json={})
        if path.endswith("/sell/fulfillment/v1/order"):
            return httpx.Response(200, json={"total": 2, "orders": [ORDER("11-1", "AMZ-B0SAMPLE01"), ORDER("11-2", "AMZ-B0SAMPLE01")]})
        if path.endswith("shipping_fulfillment"):
            return httpx.Response(201, headers={"Location": "https://x/shipping_fulfillment/F1"})
        if path.endswith("/sell/finances/v1/transaction"):
            if "NON_SALE_CHARGE" in req.url.params.get("filter", ""):
                return httpx.Response(200, json={"total": 0, "transactions": []})
            return httpx.Response(200, json={"total": 1, "transactions": [{
                "transactionType": "SALE", "bookingEntry": "CREDIT", "amount": {"value": "19.53"},
                "totalFeeAmount": {"value": "4.46"},
                "orderLineItems": [{"marketplaceFees": [{"feeType": "FINAL_VALUE_FEE", "amount": {"value": "2.91"}},
                                                        {"feeType": "FINAL_VALUE_FEE_FIXED_PER_ORDER", "amount": {"value": "0.40"}},
                                                        {"feeType": "AD_FEE", "amount": {"value": "1.15"}}]}]}]})
        raise AssertionError(f"unexpected eBay call {m} {path}")

    saved = dict(client.RATE_PER_SEC)
    client.RATE_PER_SEC.update({k: 10_000 for k in saved})  # no pacing against the mock
    client.set_transport(httpx.MockTransport(handler))
    client._tokens.clear()
    ebay.category_tree_id.cache_clear()
    ebay._aspects_cached.cache_clear()
    yield log
    client.set_transport(None)
    client.RATE_PER_SEC.update(saved)


def ORDER(oid, sku):
    return {"orderId": oid, "creationDate": "2026-10-26T15:00:00.000Z", "lastModifiedDate": "2026-10-26T15:00:00.000Z",
            "orderFulfillmentStatus": "NOT_STARTED", "orderPaymentStatus": "PAID", "buyer": {"username": "buyer1"},
            "pricingSummary": {"priceSubtotal": {"value": "22.99"}, "deliveryCost": {"value": "0.00"}, "total": {"value": "22.99"}},
            "fulfillmentStartInstructions": [{"shippingStep": {"shipTo": {
                "fullName": "Pat Buyer", "contactAddress": {"addressLine1": "1 Main St", "city": "Richmond", "stateOrProvince": "VA",
                                                            "postalCode": "23220", "countryCode": "US"},
                "primaryPhone": {"phoneNumber": "5555550100"}}}}],
            "lineItems": [{"lineItemId": f"L-{oid}", "sku": sku, "legacyItemId": "110000000001", "title": "Garlic Press",
                           "quantity": 1, "lineItemCost": {"value": "22.99"},
                           "ebayCollectAndRemitTaxes": [{"amount": {"value": "1.38"}}]}]}


def _window_all_day():
    st.update({"posting_window_start": "00:00", "posting_window_end": "23:59", "discovery_time": "00:00"})


def _post_all_scheduled():
    with session_scope() as s:
        ids = [q.id for q in s.query(QueueItem).filter(QueueItem.status == "scheduled")]
    return [queue.post_item(i) for i in ids]


def test_dry_run_pipeline(sample_source, calls):
    _window_all_day()
    st.update({"listings_per_day": 3, "queue_backup_factor": 2})
    res = queue.build_queue("test")
    assert res["added"] == 6
    with session_scope() as s:
        items = {q.asin: q for q in s.query(QueueItem).all()}
        skips = " | ".join(a.message for a in s.query(ActivityLog).filter_by(category="skipped"))
    assert set(items) == {"B0SAMPLE01", "B0SAMPLE02", "B0SAMPLE03", "B0SAMPLE10", "B0SAMPLE11", "B0SAMPLE12"}
    assert "blocklisted brand 'Yeti'" in skips           # VeRO
    assert "B0SAMPLE05: price $9.49 outside" in skips     # price filter
    assert "B0SAMPLE09: 45 reviews" in skips              # reviews filter
    assert "not in stock" in skips and "not Prime eligible" in skips
    assert "B0SAMPLE06" in skips and "below the $3.00 minimum" in skips  # profit floor
    assert sum(1 for q in items.values() if q.status == "scheduled") == 3
    assert items["B0SAMPLE01"].ebay_price == 22.99 and items["B0SAMPLE01"].expected_profit == 3.23

    results = _post_all_scheduled()
    assert all(r["ok"] for r in results)
    with session_scope() as s:
        ls = s.query(Listing).all()
        assert len(ls) == 3 and all(l.dry_run for l in ls)
        assert all(len(l.title) <= 80 and l.breakdown["ebay_price"] == l.price for l in ls)
    # Dry run: only read-only eBay calls are allowed (category lookups), never writes.
    assert all(m == "GET" or path.endswith("/oauth2/token") for m, path, *_ in calls)
    # Dry-run previews don't use up the day's listings, so the backups get scheduled next.
    assert queue.posted_today_count() == 0 and queue.dry_run_posted_today_count() == 3
    assert queue.schedule_today() == 3
    _post_all_scheduled()
    assert queue.schedule_today() == 0  # queue used up; Build queue now would refill it
    assert queue.build_queue("test")["added"] == 0  # every sample product was already tried today

    # --- refresh: price change, out of stock, below floor, back in stock
    with session_scope() as s:
        by_asin = {l.asin: l.id for l in s.query(Listing)}
    posted = set(by_asin)
    a, b = sorted(posted)[:2]
    sample.OVERRIDES[a] = {"price": 30.00}
    sample.OVERRIDES[b] = {"in_stock": False}
    stats = refresh.run(force_fetch=True)
    assert stats["price_changed"] >= 1 and stats["out_of_stock"] == 1
    with session_scope() as s:
        la, lb = s.get(Listing, by_asin[a]), s.get(Listing, by_asin[b])
        assert la.price == la.current_breakdown["ebay_price"] and la.current_amazon_price == 30.0
        assert lb.status == "qty0" and lb.quantity == 0
        assert len(la.history) >= 2
    sample.OVERRIDES[b] = {"in_stock": True}
    refresh.run([by_asin[b]], force_fetch=True)
    with session_scope() as s:
        assert s.get(Listing, by_asin[b]).status == "active"
    st.update({"refresh_max_drop_percent": 90})  # this big drop is real, don't hold it
    sample.OVERRIDES[a] = {"price": 7.00}  # cheap → profit under $3
    refresh.run([by_asin[a]], force_fetch=True)
    with session_scope() as s:
        assert s.get(Listing, by_asin[a]).status == "qty0"


def test_dry_run_guard_blocks_writes(calls):
    st.update({"dry_run": True})
    with pytest.raises(client.DryRunBlocked):
        ebay.put_inventory_item("SKU", {})
    assert calls == []


@pytest.fixture
def live(sample_source, calls, monkeypatch):
    for k, v in {"EBAY_SANDBOX_APP_ID": "app", "EBAY_SANDBOX_CERT_ID": "cert", "EBAY_SANDBOX_RUNAME": "ru",
                 "EBAY_SANDBOX_REFRESH_TOKEN": "refresh"}.items():
        monkeypatch.setenv(k, v)
    _window_all_day()
    st.update({"dry_run": False, "listings_per_day": 1, "queue_backup_factor": 1, "fulfillment_policy_id": "F",
               "return_policy_id": "R", "payment_policy_id": "P", "item_location_zip": "23220"})
    return calls


def test_live_listing_and_orders(live):
    queue.build_queue("test")
    [res] = _post_all_scheduled()
    assert res["ok"], res
    with session_scope() as s:
        l = s.query(Listing).one()
        assert not l.dry_run and l.ebay_listing_id == "110000000001" and l.ad_id == "AD1" and l.campaign_id == "CAMP1"
        lid, asin = l.id, l.asin
    offer = next(b for m, p, _, b in live if m == "POST" and p.endswith("/offer"))
    assert offer["pricingSummary"]["price"]["value"] == "22.99"
    assert offer["listingPolicies"] == {"fulfillmentPolicyId": "F", "returnPolicyId": "R", "paymentPolicyId": "P"}
    assert offer["categoryId"] == "20625"
    ad = next(b for m, p, _, b in live if p.endswith("/ad"))
    assert ad == {"listingId": "110000000001", "bidPercentage": "5.0"}

    # orders
    live.clear()
    assert orders.sync_orders() == {"new": 2, "updated": 0}
    with session_scope() as s:
        o1 = s.query(Order).filter_by(ebay_order_id="11-1").one()
        assert o1.listing_id == lid and o1.asin == asin and o1.status == "awaiting_purchase"
        assert o1.revenue_total == 24.37 and o1.buyer_tax == 1.38
        assert o1.ship_name == "Pat Buyer" and o1.ship_postal == "23220"
        o1_id = o1.id
        o2_id = s.query(Order).filter_by(ebay_order_id="11-2").one().id
    # quantity topped back up after each sale
    assert sum(1 for m, p, *_ in live if p.endswith("bulk_update_price_quantity")) == 2

    orders.mark_purchased(o1_id, "112-1234567-7654321", 14.83)
    live.clear()
    r = orders.set_tracking(o1_id, "TBA123456789000")
    assert r == {"carrier": "AMAZON", "uploaded": False}
    assert not any(p.endswith("shipping_fulfillment") for _, p, *_ in live)
    with session_scope() as s:
        assert s.get(Order, o1_id).flag == "tba_manual"

    orders.mark_purchased(o2_id, "112-0000000-0000001", 14.83)
    r = orders.set_tracking(o2_id, "1Z999AA10123456784")
    assert r["uploaded"]
    sf = next(b for m, p, _, b in live if p.endswith("shipping_fulfillment"))
    assert sf["shippingCarrierCode"] == "UPS" and sf["trackingNumber"] == "1Z999AA10123456784"
    with session_scope() as s:
        assert s.get(Order, o2_id).status == "tracking_uploaded"

    # fees: estimate first, then actual from the Finances API
    with session_scope() as s:
        o = s.get(Order, o2_id)
        est = orders.financials(o)
        assert not est["fees_are_actual"] and est["ebay_fees"] == pytest.approx(24.37 * 0.136 + 0.40, abs=0.01)
    orders.sync_fees()
    with session_scope() as s:
        f = orders.financials(s.get(Order, o2_id))
    assert f["fees_are_actual"] and f["ebay_fees"] == 3.31 and f["promo_fee"] == 1.15
    # profit = revenue 24.37 − buyer tax 1.38 − Amazon 14.83 − fees 3.31 − promo 1.15
    assert f["profit"] == 3.70

    k = metrics.overview("all")["kpis"]
    assert k["orders"] == 2 and k["revenue"] == 48.74 and k["buyer_tax"] == 2.76
    assert k["net_profit"] == 7.40 and k["amazon_spend"] == 29.66
    assert k["sell_through_pct"] == 100.0


def test_amazon_refund_and_cancel(live):
    queue.build_queue("test")
    _post_all_scheduled()
    orders.sync_orders()
    with session_scope() as s:
        o = s.query(Order).filter_by(ebay_order_id="11-1").one()
        o.amazon_cost, o.amazon_refund, o.refund_to_buyer = 14.83, 14.83, 24.37 - 1.38
        o.ebay_fees_actual, o.promo_fee_actual = 0.40, 0.0
        f = orders.financials(o)
    # Full refund both sides: you lose only the non-refundable fixed fee.
    assert f["profit"] == -0.40


def test_auto_buy_safeguards(live, monkeypatch):
    queue.build_queue("test")
    _post_all_scheduled()
    orders.sync_orders()
    with session_scope() as s:
        oid = s.query(Order).filter_by(ebay_order_id="11-1").one().id
    st.update({"auto_buy_kill_switch": True})
    assert orders.auto_buy(oid)["message"] == "kill switch on"
    st.update({"auto_buy_kill_switch": False, "auto_buy_max_order_dollars": 10})
    assert "over the $10.00 auto-order cap" in orders.auto_buy(oid)["message"]
    st.update({"auto_buy_max_order_dollars": 75})
    sample.OVERRIDES["B0SAMPLE01"] = {"price": 21.00}  # Amazon price jumped → unprofitable
    assert "unprofitable" in orders.auto_buy(oid)["message"]
    sample.OVERRIDES.clear()

    st.update({"auto_buy_max_spend_per_day": 5})
    assert "daily auto-buy spending cap" in orders.auto_buy(oid)["message"]
    st.update({"auto_buy_max_spend_per_day": ""})

    assert "no Amazon account" in orders.auto_buy(oid)["message"]
    from app.services import accounts

    acct = accounts.create("Main")
    placed = {}

    def fake_place(asin, qty, address, guard, profile=None):
        from app.providers.base import PurchaseResult

        assert "free delivery required" in guard(15.10, 5.99)[1]
        ok, why = guard(15.10, 0.0)
        placed.update(asin=asin, address=address, ok=ok, profile=profile)
        return PurchaseResult(True, order_id="113-1111111-2222222", total_paid=15.10)

    from app.providers import get_provider

    monkeypatch.setattr(get_provider(), "place_order", fake_place)
    res = orders.auto_buy(oid)
    assert res["ok"] and placed["ok"] and placed["address"]["postal"] == "23220"
    assert placed["profile"].endswith(f"account-{acct['id']}")
    with session_scope() as s:
        o = s.get(Order, oid)
        assert o.status == "purchased" and o.amazon_cost == 15.10 and o.auto_buy_attempted
        assert o.amazon_account_id == acct["id"]
    # never auto-retried
    assert "already attempted" in orders.auto_buy(oid)["message"] or orders.auto_buy(oid)["message"].startswith("order is")


def test_refresh_review_mode_does_not_touch_listing(sample_source, calls):
    _window_all_day()
    st.update({"listings_per_day": 1, "queue_backup_factor": 1, "refresh_auto_apply": False})
    queue.build_queue("test")
    _post_all_scheduled()
    with session_scope() as s:
        l = s.query(Listing).one()
        lid, asin, price, was = l.id, l.asin, l.price, l.amazon_price_at_listing
    sample.OVERRIDES[asin] = {"price": was + 1}  # still profitable at the current eBay price
    refresh.run(force_fetch=True)
    with session_scope() as s:
        l = s.get(Listing, lid)
        assert l.price == price and l.flagged and "suggested eBay price" in l.flag_reason
    sample.OVERRIDES[asin] = {"in_stock": False}
    refresh.run(force_fetch=True)
    with session_scope() as s:
        l = s.get(Listing, lid)
        assert l.status == "active" and "out of stock" in l.flag_reason



def test_amazon_account_rotation(sample_source):
    from datetime import timedelta

    from app.models import AmazonAccount, utcnow
    from app.services import accounts

    a = accounts.create("Alpha")
    b = accounts.create("Bravo")
    c = accounts.create("Charlie")
    accounts.update(c["id"], {"buys_orders": False})  # excluded from rotation
    # take turns: never-used first (lowest id), then whoever was used longest ago
    st.update({"amazon_rotation": "round_robin"})
    first, _ = accounts.pick_next()
    assert first.id == a["id"]
    accounts.mark_used(a["id"])
    assert accounts.pick_next()[0].id == b["id"]
    accounts.mark_used(b["id"])
    assert accounts.pick_next()[0].id == a["id"]

    # least used today: count today's purchases per account
    def buy(acct_id, cost):
        with session_scope() as s:
            s.add(Order(ebay_order_id=f"X{acct_id}{cost}", created_at=utcnow(), amazon_account_id=acct_id,
                        auto_buy_at=utcnow(), amazon_cost=cost))

    buy(a["id"], 10)
    buy(a["id"], 12)
    buy(b["id"], 30)
    st.update({"amazon_rotation": "least_used_today"})
    assert accounts.pick_next()[0].id == b["id"]

    # per-account limits
    accounts.update(b["id"], {"max_orders_per_day": 1})
    assert accounts.pick_next()[0].id == a["id"]
    accounts.update(a["id"], {"max_spend_per_day": 25})
    nxt, why = accounts.pick_next(amount=5)
    assert nxt is None and "at a limit" in why and "Alpha" in why and "Bravo" in why
    accounts.update(a["id"], {"max_spend_per_day": ""})  # blank = no limit
    assert accounts.pick_next(amount=5)[0].id == a["id"]
    # an account known to be logged out is skipped
    accounts.set_login_state(a["id"], False)
    nxt, why = accounts.pick_next()
    assert nxt is None and "not logged in" in why
    usage = {x["name"]: x for x in accounts.list_accounts()}
    assert usage["Alpha"]["orders_today"] == 2 and usage["Alpha"]["spend_today"] == 22.0


def test_legacy_login_becomes_first_account(tmp_path, monkeypatch):
    from app import config
    from app.services import accounts

    legacy = tmp_path / "amazon_profile"
    legacy.mkdir()
    monkeypatch.setattr(config, "LEGACY_AMAZON_PROFILE_DIR", legacy)
    accounts.ensure_legacy_account()
    accounts.ensure_legacy_account()  # idempotent
    rows = accounts.list_accounts()
    assert len(rows) == 1 and rows[0]["name"] == "Amazon account 1"
    assert accounts.get(rows[0]["id"]).profile_dir == str(legacy)


def test_db_upgrade_adds_new_columns():
    from sqlalchemy import inspect, text

    from app.db import engine, init_db

    with engine.begin() as conn:
        conn.execute(text("DROP INDEX ix_orders_amazon_account_id"))
        conn.execute(text("ALTER TABLE orders DROP COLUMN amazon_account_id"))
    assert "amazon_account_id" not in {c["name"] for c in inspect(engine).get_columns("orders")}
    init_db()
    assert "amazon_account_id" in {c["name"] for c in inspect(engine).get_columns("orders")}
    assert "ix_orders_amazon_account_id" in {i["name"] for i in inspect(engine).get_indexes("orders")}


def test_own_ebay_items_are_never_bought_or_counted(live, monkeypatch):
    """Sales of items you listed yourself (not through this app) are left alone, even with auto ordering on."""
    from app.providers import get_provider
    from app.services import accounts

    queue.build_queue("test")
    _post_all_scheduled()
    accounts.create("Main")
    own = ORDER("22-1", "MY-OWN-SKU")
    own["lineItems"][0].update(legacyItemId="229999999999", title="Vintage lamp I already own")
    monkeypatch.setattr(ebay, "get_orders_modified_since", lambda since: [ORDER("11-1", "AMZ-B0SAMPLE01"), own])

    bought = []

    def fake_place(asin, qty, address, guard, profile=None):
        from app.providers.base import PurchaseResult

        bought.append(asin)
        return PurchaseResult(True, order_id="113-1111111-2222222", total_paid=15.10)

    monkeypatch.setattr(get_provider(), "place_order", fake_place)
    st.update({"checkout_mode": "auto", "auto_buy_max_order_dollars": 75})
    orders.sync_orders()
    assert bought == ["B0SAMPLE01"]  # only the app's own listing was bought
    with session_scope() as s:
        mine = s.query(Order).filter_by(ebay_order_id="22-1").one()
        assert not mine.managed and mine.flag == "" and not mine.auto_buy_attempted and mine.status == "awaiting_purchase"
        assert s.query(Order).filter_by(ebay_order_id="11-1").one().managed
        mine_id = mine.id
    assert "never bought" in orders.auto_buy(mine_id)["message"] and bought == ["B0SAMPLE01"]
    k = metrics.overview("all")["kpis"]
    assert k["orders"] == 1 and k["revenue"] == 24.37  # only the app's sale
    orders.set_managed(mine_id, True)
    assert metrics.overview("all")["kpis"]["orders"] == 2


def test_upgrade_marks_old_unlinked_orders_unmanaged():
    from sqlalchemy import text

    from app.db import engine, init_db
    from app.models import utcnow

    with session_scope() as s:
        s.add(Order(ebay_order_id="OLD-1", environment="production", created_at=utcnow()))
    with engine.begin() as conn:
        conn.execute(text("DROP INDEX ix_orders_managed"))
        conn.execute(text("ALTER TABLE orders DROP COLUMN managed"))
    init_db()
    with session_scope() as s:
        assert s.query(Order).filter_by(ebay_order_id="OLD-1").one().managed is False


def _one_listing(**settings):
    _window_all_day()
    st.update({"listings_per_day": 1, "queue_backup_factor": 1, **settings})
    queue.build_queue("test")
    _post_all_scheduled()
    with session_scope() as s:
        l = s.query(Listing).one()
        return l.id, l.asin, l.price


def test_losing_price_is_never_listed_even_with_floors_off():
    from decimal import Decimal

    from app.pricing import PricingParams, floor_failures

    off = PricingParams(min_profit_dollars=None, min_profit_percent=None)
    assert "would lose money" in floor_failures(Decimal("-0.50"), Decimal("-3"), off)[0]
    assert not floor_failures(Decimal("0.01"), Decimal("0.1"), off)


def test_review_mode_stops_sales_that_would_lose_money(sample_source, calls, monkeypatch):
    from app.services import listing_ops

    lid, asin, price = _one_listing(refresh_auto_apply=False)
    qty = []
    monkeypatch.setattr(listing_ops, "set_quantity", lambda i, q, r, status=None: qty.append((i, q)) or True)
    sample.OVERRIDES[asin] = {"price": price}  # Amazon now costs about what eBay sells it for
    refresh.run(force_fetch=True)
    assert qty == [(lid, 0)]
    with session_scope() as s:
        l = s.get(Listing, lid)
        assert l.price == price and "would lose" in l.flag_reason and "suggested eBay price" in l.flag_reason
    # a small rise that stays profitable is only flagged
    qty.clear()
    with session_scope() as s:
        s.get(Listing, lid).flagged = False
    sample.OVERRIDES[asin] = {"price": round(price / 1.8, 2)}
    refresh.run(force_fetch=True)
    assert qty == []


def test_failed_price_update_stops_a_losing_listing(sample_source, calls, monkeypatch):
    from app.services import listing_ops

    lid, asin, price = _one_listing()
    qty = []
    monkeypatch.setattr(listing_ops, "set_quantity", lambda i, q, r, status=None: qty.append((i, q)) or True)

    def boom(*a, **k):
        raise RuntimeError("eBay said no")

    monkeypatch.setattr(listing_ops, "set_price", boom)
    sample.OVERRIDES[asin] = {"price": price}
    stats = refresh.run(force_fetch=True)
    assert stats["errors"] == 1 and qty == [(lid, 0)]


def test_big_price_drop_is_held_for_review(sample_source, calls, monkeypatch):
    from app.services import listing_ops

    lid, asin, price = _one_listing()
    changed = []
    monkeypatch.setattr(listing_ops, "set_price", lambda i, p, r: changed.append(p) or True)
    sample.OVERRIDES[asin] = {"price": 2.00}  # e.g. a misread coupon price
    refresh.run(force_fetch=True)
    with session_scope() as s:
        l = s.get(Listing, lid)
        assert changed == [] and l.price == price and "big price drop held" in l.flag_reason
        suggested = l.current_breakdown["ebay_price"]
    st.update({"min_profit_dollars": None})  # $2 items can't make $3, so allow the confirm in this test
    r = refresh.apply_suggested_price(lid)
    assert r["ok"], r
    assert changed == [suggested]
    with session_scope() as s:
        assert not s.get(Listing, lid).flagged


def test_queue_takes_turns_between_keywords(sample_source, monkeypatch):
    """One product per keyword per round, in a random keyword order, so one keyword can't fill the queue."""
    from app.providers import amazon_parser, get_provider

    _window_all_day()
    st.update({"search_keywords": ["garlic", "lamps"], "listings_per_day": 4, "queue_backup_factor": 1})
    by_term = {"garlic": {"B0SAMPLE01", "B0SAMPLE02", "B0SAMPLE03"}, "lamps": {"B0SAMPLE10", "B0SAMPLE11", "B0SAMPLE12"}}
    searches = []

    def search(term, cat, page):
        searches.append((term, page))
        rs = amazon_parser.parse_search(sample.search_html(term)) if page == 1 else []
        return [r for r in rs if r.asin in by_term[term]]

    monkeypatch.setattr(get_provider(), "search", search)
    assert queue.build_queue("test")["added"] == 4
    with session_scope() as s:
        items = s.query(QueueItem).all()
        terms = [q.search_term for q in items]
        assert terms.count("garlic") == 2 and terms.count("lamps") == 2
        scheduled = [q.search_term for q in sorted(items, key=lambda q: q.scheduled_at)]
    assert scheduled[0] != scheduled[1] and scheduled[1] != scheduled[2]  # posts alternate keywords
    assert sorted(searches) == [("garlic", 1), ("lamps", 1)]  # each keyword searched once, results reused


def _tick_at(monkeypatch, hhmm: str):
    """Run one posting_tick as if the local time were hh:mm today; returns the jobs it started."""
    from datetime import datetime

    from app.services import scheduler

    started = []
    h, m = map(int, hhmm.split(":"))
    fake_now = datetime.now().astimezone().replace(hour=h, minute=m)
    monkeypatch.setattr(queue, "local_now", lambda: fake_now)
    monkeypatch.setattr(scheduler, "run_now", lambda name: started.append(name) or True)
    queue.posting_tick()
    return started


def test_morning_queue_catch_up(sample_source, monkeypatch):
    from app.providers import amazon_playwright as ap
    from app.providers.base import SourcePaused

    st.update({"discovery_time": "07:30", "posting_window_start": "08:00", "posting_window_end": "22:00"})
    queue._last_catchup = None
    assert _tick_at(monkeypatch, "07:00") == []                 # before build time: nothing
    assert _tick_at(monkeypatch, "09:15") == ["discovery"]      # PC was off at 07:30 → builds on next tick
    assert _tick_at(monkeypatch, "09:16") == []                 # no retry storm while it runs / just ran
    queue._last_catchup = None

    # A CAPTCHA cuts the build short: today is NOT marked built, and it carries on after the cooldown.
    def blocked(*a, **k):
        ap.pause_for_block("test robot check")
        raise SourcePaused("paused")

    st.update({"product_source": "amazon_playwright"})
    monkeypatch.setattr(queue, "get_provider", lambda: type("P", (), {"search": staticmethod(blocked)})())
    res = queue.build_queue("schedule")
    assert res["stopped"] and st.get("last_queue_build_date") is None
    assert "carry on automatically" in queue.PROGRESS["result"]
    assert _tick_at(monkeypatch, "09:30") == []                 # still paused: waits, no hammering Amazon
    ap.resume("test")
    assert _tick_at(monkeypatch, "12:45") == ["discovery"]      # cooldown over → build resumes
    queue._last_catchup = None

    # A crash mid-build (or the PC shutting down) also leaves today unbuilt.
    st.update({"product_source": "sample"})
    monkeypatch.setattr(queue, "get_provider", lambda: type("P", (), {"search": staticmethod(
        lambda *a: (_ for _ in ()).throw(RuntimeError("network down")))})())
    with pytest.raises(RuntimeError):
        queue.build_queue("schedule")
    assert st.get("last_queue_build_date") is None
    monkeypatch.undo()

    # A normal build marks the day done, so no more catch-ups today.
    queue.build_queue("schedule")
    assert st.get("last_queue_build_date") == queue.local_now().date().isoformat()
    queue._last_catchup = None
    assert _tick_at(monkeypatch, "15:00") == []


def test_sweep_fixes(sample_source, calls, monkeypatch):
    from datetime import timedelta

    from app.models import utcnow
    from app.services import refresh as rf

    _window_all_day()
    st.update({"listings_per_day": 2, "queue_backup_factor": 1})
    queue.build_queue("test")
    with session_scope() as s:
        a, b = [q.id for q in s.query(QueueItem).filter_by(status="scheduled")]
        qa, qb = s.get(QueueItem, a), s.get(QueueItem, b)
        qa.scheduled_at = utcnow() - timedelta(hours=1)
        qa.status = "posting"                          # app closed mid-post an hour ago
        qb.scheduled_at = utcnow() - timedelta(minutes=5)
        qb.queue_date = qb.queue_date - timedelta(days=1)  # yesterday's leftover
    assert queue.due_items() == [a]                    # stuck one retried; yesterday's never posts late
    with session_scope() as s:
        assert s.get(QueueItem, a).status == "scheduled" and "interrupted" in s.get(QueueItem, a).message

    # refresh: dry-run previews are skipped once you're live; product data is never older than 1 hour
    queue.post_item(a)
    seen_ages = []
    monkeypatch.setattr(rf.products, "fetch", lambda asin, max_age_hours=None: seen_ages.append(max_age_hours) or
                        (_ for _ in ()).throw(rf.ProviderError("stop here")))
    st.update({"amazon_cache_hours": 6})
    rf.run()
    assert seen_ages == [1.0]
    seen_ages.clear()
    st.update({"dry_run": False})
    rf.run()
    assert seen_ages == []                              # the only listing is a dry-run preview

    # settings: a build time after the posting window would mean nothing ever posts
    with pytest.raises(st.SettingsError):
        st.update({"discovery_time": "23:00", "posting_window_start": "08:00", "posting_window_end": "22:00"})


def test_one_bad_new_order_does_not_block_the_others(live, monkeypatch):
    queue.build_queue("test")
    _post_all_scheduled()
    handled = []

    def after(oid):
        handled.append(oid)
        if len(handled) == 1:
            raise RuntimeError("boom")

    monkeypatch.setattr(orders, "_after_new_order", after)
    assert orders.sync_orders()["new"] == 2
    assert len(handled) == 2
    with session_scope() as s:
        assert "could not finish processing" in s.get(Order, handled[0]).flag_reason


def test_unposted_items_carry_over_to_the_next_day(sample_source, monkeypatch):
    from datetime import timedelta

    from app.models import utcnow
    from app.providers import get_provider

    _window_all_day()
    st.update({"listings_per_day": 2, "queue_backup_factor": 3})
    assert queue.build_queue("test")["added"] == 6
    with session_scope() as s:
        items = s.query(QueueItem).order_by(QueueItem.id).all()
        for q in items:  # pretend all of this was found yesterday
            q.queue_date = q.queue_date - timedelta(days=1)
        items[0].created_at = utcnow() - timedelta(days=8)  # found over a week ago
        ids = [q.id for q in items]
    searches = []
    real = get_provider().search
    monkeypatch.setattr(get_provider(), "search", lambda *a: searches.append(a) or real(*a))
    res = queue.build_queue("test")
    assert res["added"] == 1 and len(searches) == 1      # only the one expired item had to be replaced
    with session_scope() as s:
        old = {q.id: q for q in s.query(QueueItem).filter(QueueItem.id.in_(ids))}
        assert old[ids[0]].status == "expired"
        carried = [old[i] for i in ids[1:]]
        assert all(q.queue_date == queue.local_now().date() and q.message.startswith("carried over") for q in carried)
        assert sum(1 for q in carried if q.status == "scheduled") >= 1
