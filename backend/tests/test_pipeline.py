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
    assert items["B0SAMPLE01"].ebay_price == 22.99 and items["B0SAMPLE01"].expected_profit == 3.30

    results = _post_all_scheduled()
    assert all(r["ok"] for r in results)
    with session_scope() as s:
        ls = s.query(Listing).all()
        assert len(ls) == 3 and all(l.dry_run for l in ls)
        assert all(len(l.title) <= 80 and l.breakdown["ebay_price"] == l.price for l in ls)
    # Dry run: only read-only eBay calls are allowed (category lookups), never writes.
    assert all(m == "GET" or path.endswith("/oauth2/token") for m, path, *_ in calls)
    assert queue.schedule_today() == 0  # daily target reached

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
        lid, asin, price = l.id, l.asin, l.price
    sample.OVERRIDES[asin] = {"price": 30.00}
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
