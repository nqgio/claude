"""Orders: sync from eBay, Amazon purchase (assisted or auto), tracking, fees, returns."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .. import activity
from .. import settings_store as st
from ..db import session_scope
from ..ebay import api as ebay
from ..ebay.client import EbayError, EbayNotConnected
from ..models import Listing, Order, utcnow
from ..pricing import _d
from ..providers import get_provider
from ..providers.base import ProviderError, SourceBlocked, SourcePaused
from . import carriers, products
from .evaluate import pricing_params

STATUS_ORDER = ["awaiting_purchase", "purchased", "shipped", "tracking_uploaded", "delivered"]
TERMINAL = {"cancelled", "returned", "refunded"}


def _amt(x) -> float:
    try:
        return float((x or {}).get("value") or 0)
    except (TypeError, ValueError, AttributeError):
        return 0.0


def _parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc).replace(tzinfo=None)


def _advance(order: Order, new: str) -> None:
    """Move status forward only (never backwards); terminal states always win."""
    if new in TERMINAL:
        order.status = new
    elif order.status not in TERMINAL and STATUS_ORDER.index(new) > STATUS_ORDER.index(order.status):
        order.status = new


def estimate_fees(order: Order, listing: Listing | None) -> None:
    p = pricing_params()
    fee_basis = _d(order.revenue_total)
    order.ebay_fees_est = float(fee_basis * _d(p.ebay_fee_percent) / 100 + _d(p.ebay_fee_fixed_per_order))
    promoted = listing is not None and (listing.ad_id or listing.dry_run) and p.promo_rate_percent > 0
    sale = _d(order.item_subtotal + order.shipping_charged)
    order.promo_fee_est = float(sale * _d(p.promo_rate_percent) / 100) if promoted else 0.0


def financials(o: Order) -> dict:
    """Per-order money. Uses actual fees/cost when known, estimates otherwise.
    profit = revenue (incl. buyer tax) − buyer tax − Amazon cost + Amazon refund − eBay fees − promo − refund to buyer"""
    fees_actual = o.ebay_fees_actual is not None
    fees = o.ebay_fees_actual if fees_actual else o.ebay_fees_est
    promo = o.promo_fee_actual if o.promo_fee_actual is not None else o.promo_fee_est
    cost_actual = o.amazon_cost is not None
    cost = o.amazon_cost if cost_actual else o.amazon_cost_est
    if o.status == "cancelled" and not cost_actual:
        cost, fees, promo = 0.0, (o.ebay_fees_actual or 0.0), (o.promo_fee_actual or 0.0)
    revenue = 0.0 if o.status == "cancelled" else o.revenue_total
    tax = 0.0 if o.status == "cancelled" else o.buyer_tax
    profit = revenue - tax - cost + o.amazon_refund - fees - promo - o.refund_to_buyer
    return {"revenue": round(revenue, 2), "buyer_tax": round(tax, 2), "amazon_cost": round(cost, 2),
            "amazon_cost_is_actual": cost_actual, "amazon_refund": round(o.amazon_refund, 2),
            "ebay_fees": round(fees, 2), "promo_fee": round(promo, 2), "fees_are_actual": fees_actual,
            "refund_to_buyer": round(o.refund_to_buyer, 2), "profit": round(profit, 2)}


# ---- sync ----------------------------------------------------------------------------------

def sync_orders() -> dict:
    env = st.get("ebay_environment")
    last = st.get("orders_last_sync")
    since = (datetime.fromisoformat(last) - timedelta(minutes=30)) if last else datetime.now(timezone.utc) - timedelta(days=30)
    started = datetime.now(timezone.utc)
    try:
        raw_orders = ebay.get_orders_modified_since(since)
    except EbayNotConnected as exc:
        return {"skipped": str(exc)}
    new_ids, n_updated = [], 0
    for ro in raw_orders:
        try:
            oid, is_new = _upsert(ro, env)
            (new_ids.append(oid) if is_new else None)
            n_updated += 0 if is_new else 1
        except Exception as exc:
            activity.error("order", f"Could not process eBay order {ro.get('orderId')}: {exc}")
    st.set_internal("orders_last_sync", started.isoformat())
    for oid in new_ids:
        _after_new_order(oid)
    if new_ids or n_updated:
        activity.info("order", f"Order sync: {len(new_ids)} new, {n_updated} updated")
    return {"new": len(new_ids), "updated": n_updated}


def _upsert(ro: dict, env: str) -> tuple[int, bool]:
    lines = []
    for li in ro.get("lineItems", []):
        lines.append({"line_item_id": li.get("lineItemId"), "sku": li.get("sku", ""), "item_id": li.get("legacyItemId", ""),
                      "title": li.get("title", ""), "quantity": int(li.get("quantity", 1)),
                      "line_cost": _amt(li.get("lineItemCost")),
                      "tax": sum(_amt(t.get("amount")) for t in li.get("ebayCollectAndRemitTaxes", []))})
    ps = ro.get("pricingSummary", {})
    subtotal = _amt(ps.get("priceSubtotal")) - abs(_amt(ps.get("priceDiscount")))
    shipping = _amt(ps.get("deliveryCost"))
    tax = round(sum(l["tax"] for l in lines), 2)
    ship = (((ro.get("fulfillmentStartInstructions") or [{}])[0].get("shippingStep") or {}).get("shipTo") or {})
    addr = ship.get("contactAddress") or {}
    refunds = sum(_amt(r.get("amount")) for r in (ro.get("paymentSummary") or {}).get("refunds", [])
                  if r.get("refundStatus") in ("REFUNDED", None))
    with session_scope() as s:
        o = s.query(Order).filter_by(ebay_order_id=ro["orderId"], environment=env).one_or_none()
        is_new = o is None
        if is_new:
            o = Order(ebay_order_id=ro["orderId"], environment=env, created_at=_parse_dt(ro.get("creationDate")) or utcnow())
            s.add(o)
        o.last_modified = _parse_dt(ro.get("lastModifiedDate"))
        o.ebay_fulfillment_status = ro.get("orderFulfillmentStatus", "")
        o.ebay_payment_status = ro.get("orderPaymentStatus", "")
        o.buyer_username = (ro.get("buyer") or {}).get("username", "") if o.buyer_username != "[deleted]" else o.buyer_username
        if o.ship_name != "[deleted]":
            o.ship_name = ship.get("fullName", "")
            o.ship_line1, o.ship_line2 = addr.get("addressLine1", ""), addr.get("addressLine2", "")
            o.ship_city, o.ship_state = addr.get("city", ""), addr.get("stateOrProvince", "")
            o.ship_postal, o.ship_country = addr.get("postalCode", ""), addr.get("countryCode", "US")
            o.ship_phone = (ship.get("primaryPhone") or {}).get("phoneNumber", "")
            o.raw = ro
        o.lines = lines
        o.quantity = sum(l["quantity"] for l in lines) or 1
        o.title = lines[0]["title"] if lines else ""
        o.item_subtotal, o.shipping_charged, o.buyer_tax = round(subtotal, 2), round(shipping, 2), tax
        o.revenue_total = round(subtotal + shipping + tax, 2)
        listing = None
        if lines:
            listing = (s.query(Listing).filter(Listing.environment == env, Listing.dry_run.is_(False))
                       .filter((Listing.sku == lines[0]["sku"]) | (Listing.ebay_listing_id == lines[0]["item_id"]))
                       .order_by(Listing.id.desc()).first())
        if listing:
            o.listing_id, o.asin, o.amazon_url = listing.id, listing.asin, listing.amazon_url
            cost_each = (listing.current_breakdown or listing.breakdown or {}).get("amazon_cost", listing.cost_at_listing)
            if o.amazon_cost is None:
                o.amazon_cost_est = round(cost_each * o.quantity, 2)
        estimate_fees(o, listing)
        if not o.refund_is_actual and refunds:
            o.refund_to_buyer = round(refunds, 2)
        if (ro.get("cancelStatus") or {}).get("cancelState") == "CANCELED":
            _advance(o, "cancelled")
        elif refunds and refunds >= o.revenue_total - 0.01 and o.status != "returned":
            _advance(o, "refunded")
        elif o.ebay_fulfillment_status == "FULFILLED" and o.status in ("awaiting_purchase", "purchased", "shipped"):
            _advance(o, "tracking_uploaded")
        s.flush()
        return o.id, is_new


def _after_new_order(order_id: int) -> None:
    with session_scope() as s:
        o = s.get(Order, order_id)
        l = s.get(Listing, o.listing_id) if o.listing_id else None
        summary = f"New order {o.ebay_order_id}: {o.quantity}× '{o.title[:60]}' for ${o.revenue_total:.2f}"
        if not l:
            summary += " (no matching listing in this app)"
        status, listing_id = o.status, o.listing_id
    activity.info("order", summary, order_id=order_id, listing_id=listing_id)
    if status != "awaiting_purchase":
        return
    if l and l.status == "active" and not st.get("dry_run"):  # eBay lowered quantity — top it back up
        try:
            ebay.update_price_quantity(l.sku, l.offer_id, quantity=int(st.get("listing_quantity")))
        except EbayError as exc:
            activity.warning("stock", f"Could not restore quantity after sale on '{l.title}': {exc}", listing_id=l.id)
    if st.get("checkout_mode") == "auto":
        auto_buy(order_id)


# ---- purchase ------------------------------------------------------------------------------------

def _flag(order_id: int, flag: str, reason: str) -> None:
    with session_scope() as s:
        o = s.get(Order, order_id)
        o.flag, o.flag_reason = flag, reason
    activity.warning("order", f"Order #{order_id} flagged ({flag}): {reason}", order_id=order_id)


def mark_purchased(order_id: int, amazon_order_id: str, amazon_cost: float | None, note: str = "") -> None:
    with session_scope() as s:
        o = s.get(Order, order_id)
        o.amazon_order_id = amazon_order_id.strip()
        if amazon_cost is not None:
            o.amazon_cost = round(float(amazon_cost), 2)
        o.purchased_at = o.purchased_at or utcnow()
        _advance(o, "purchased")
        if o.flag == "needs_attention":
            o.flag, o.flag_reason = "", ""
    activity.info("order", f"Order #{order_id} purchased on Amazon ({amazon_order_id or 'no order #'}"
                           f"{f', paid ${amazon_cost:.2f}' if amazon_cost is not None else ''}){note}", order_id=order_id)


def auto_buy_count_today() -> int:
    start = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
    with session_scope() as s:
        return s.query(Order).filter(Order.auto_buy_at >= start.astimezone(timezone.utc).replace(tzinfo=None)).count()


def auto_buy_spent_today() -> float:
    start = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
    with session_scope() as s:
        rows = s.query(Order).filter(Order.auto_buy_at >= start.astimezone(timezone.utc).replace(tzinfo=None)).all()
        return round(sum(o.amazon_cost or 0.0 for o in rows), 2)


def auto_buy(order_id: int) -> dict:
    """Place the Amazon order for an eBay order, with every safeguard checked first."""
    sset = st.all_settings()
    with session_scope() as s:
        o = s.get(Order, order_id)
        if o.status != "awaiting_purchase":
            return {"ok": False, "message": f"order is {o.status}"}
        if o.auto_buy_attempted:
            return {"ok": False, "message": "auto-buy was already attempted for this order — buy manually"}
        if not o.asin:
            _flag(order_id, "needs_attention", "auto-buy: order isn't linked to a listing/ASIN")
            return {"ok": False, "message": "no ASIN"}
        asin, qty = o.asin, o.quantity
        address = {"name": o.ship_name, "line1": o.ship_line1, "line2": o.ship_line2, "city": o.ship_city,
                   "state": o.ship_state, "postal": o.ship_postal, "phone": o.ship_phone}
        net_sale = o.revenue_total - o.buyer_tax
        fees = o.ebay_fees_actual if o.ebay_fees_actual is not None else o.ebay_fees_est
        promo = o.promo_fee_actual if o.promo_fee_actual is not None else o.promo_fee_est
    if sset["auto_buy_kill_switch"]:
        _flag(order_id, "needs_attention", "auto-buy kill switch is ON — buy manually")
        return {"ok": False, "message": "kill switch on"}
    if auto_buy_count_today() >= int(sset["auto_buy_max_per_day"]):
        _flag(order_id, "needs_attention", f"auto-buy daily limit ({sset['auto_buy_max_per_day']}) reached")
        return {"ok": False, "message": "daily limit reached"}
    try:
        p, _ = products.fetch(asin, max_age_hours=0)
    except ProviderError as exc:
        _flag(order_id, "needs_attention", f"auto-buy: could not load Amazon page: {exc}")
        return {"ok": False, "message": str(exc)}
    if not p.in_stock or not p.price:
        _flag(order_id, "needs_attention", "auto-buy: Amazon item is out of stock")
        return {"ok": False, "message": "out of stock"}
    params = pricing_params()
    est_cost = float(_d(p.price) * qty * (1 + _d(params.sales_tax_percent) / 100))
    cap = float(sset["auto_buy_max_order_dollars"])

    day_cap = sset["auto_buy_max_spend_per_day"]
    spent_today = auto_buy_spent_today()

    def check(total: float, shipping: float | None = None) -> tuple[bool, str]:
        profit = net_sale - total - fees - promo
        if profit <= 0:
            return False, f"unprofitable at Amazon total ${total:.2f} (profit ${profit:.2f})"
        if total > cap:
            return False, f"Amazon total ${total:.2f} is over the ${cap:.2f} auto-order cap"
        if day_cap is not None and spent_today + total > float(day_cap):
            return False, f"would exceed the ${float(day_cap):.2f} daily auto-buy spending cap (${spent_today:.2f} spent today)"
        if shipping and shipping > 0 and sset["auto_buy_require_free_delivery"]:
            return False, f"Amazon charges ${shipping:.2f} delivery (free delivery required)"
        return True, f"profit ${profit:.2f}"

    ok, why = check(est_cost)
    if not ok:
        _flag(order_id, "needs_attention", f"auto-buy blocked: {why}")
        return {"ok": False, "message": why}
    if sset["dry_run"]:
        activity.info("order", f"DRY RUN: would auto-buy {qty}× {asin} on Amazon for about ${est_cost:.2f} ({why})",
                      order_id=order_id)
        return {"ok": True, "dry_run": True, "message": why}
    with session_scope() as s:  # record the attempt BEFORE touching checkout so we never double-buy
        o = s.get(Order, order_id)
        o.auto_buy_attempted, o.auto_buy_at = True, utcnow()
    try:
        res = get_provider().place_order(asin, qty, address, check)
    except Exception as exc:
        _flag(order_id, "needs_attention", f"auto-buy error — check Amazon before buying manually: {exc}")
        return {"ok": False, "message": str(exc)}
    if not res.ok:
        _flag(order_id, "needs_attention", f"auto-buy did not complete: {res.message}"
                                           + (f" (screenshot: {res.screenshot})" if res.screenshot else ""))
        return {"ok": False, "message": res.message}
    mark_purchased(order_id, res.order_id, res.total_paid, " — auto-buy")
    if not res.order_id:
        _flag(order_id, "needs_attention", res.message)
    return {"ok": True, "amazon_order_id": res.order_id, "total": res.total_paid}


# ---- tracking ----------------------------------------------------------------------------------------

def set_tracking(order_id: int, tracking: str, carrier_text: str = "") -> dict:
    tracking = tracking.strip().replace(" ", "").upper()
    carrier = carriers.detect(tracking, carrier_text)
    with session_scope() as s:
        o = s.get(Order, order_id)
        o.tracking_number, o.carrier = tracking, carrier
        _advance(o, "shipped")
        if carrier == "AMAZON":
            o.flag, o.flag_reason = "tba_manual", "Amazon Logistics (TBA) tracking — not uploaded. Decide what to do manually."
        elif carrier == "OTHER":
            o.flag, o.flag_reason = "needs_attention", f"Unrecognized carrier for tracking {tracking}; not uploaded"
    activity.info("tracking", f"Order #{order_id}: tracking {tracking} ({carrier})", order_id=order_id)
    if carrier == "AMAZON":
        activity.warning("tracking", f"Order #{order_id}: TBA tracking — manual action needed", order_id=order_id)
        return {"carrier": carrier, "uploaded": False}
    if carriers.ebay_code(carrier):
        return {"carrier": carrier, "uploaded": upload_tracking(order_id)}
    return {"carrier": carrier, "uploaded": False}


def upload_tracking(order_id: int) -> bool:
    with session_scope() as s:
        o = s.get(Order, order_id)
        code = carriers.ebay_code(o.carrier)
        if not code or o.tracking_uploaded_at:
            return False
        ebay_id, tracking = o.ebay_order_id, o.tracking_number
        lines = [{"lineItemId": l["line_item_id"], "quantity": l["quantity"]} for l in o.lines]
    if st.get("dry_run"):
        activity.info("tracking", f"DRY RUN: would upload {code} {tracking} to eBay order {ebay_id}", order_id=order_id)
        return False
    try:
        ebay.create_shipping_fulfillment(ebay_id, lines, code, tracking)
    except EbayError as exc:
        activity.error("tracking", f"Tracking upload failed for order {ebay_id}: {exc}", order_id=order_id)
        return False
    with session_scope() as s:
        o = s.get(Order, order_id)
        o.tracking_uploaded_at = utcnow()
        _advance(o, "tracking_uploaded")
    activity.info("tracking", f"Uploaded {code} tracking {tracking} to eBay order {ebay_id}", order_id=order_id)
    return True


def check_tracking() -> dict:
    with session_scope() as s:
        rows = [(o.id, o.amazon_order_id) for o in s.query(Order).filter(
            Order.status.in_(["purchased", "shipped", "tracking_uploaded"]), Order.amazon_order_id != "",
            Order.delivered_at.is_(None))]
    provider = get_provider()
    found = 0
    for oid, amz in rows:
        try:
            info = provider.get_tracking(amz)
        except (SourceBlocked, SourcePaused) as exc:
            activity.warning("tracking", f"Tracking check stopped: {exc}")
            break
        except ProviderError as exc:
            activity.warning("tracking", f"Could not read Amazon order {amz}: {exc}", order_id=oid)
            continue
        if not info:
            continue
        with session_scope() as s:
            o = s.get(Order, oid)
            had = o.tracking_number
        if info.tracking_number and info.tracking_number != had:
            set_tracking(oid, info.tracking_number, info.carrier)
            found += 1
        if info.delivered:
            with session_scope() as s:
                o = s.get(Order, oid)
                o.delivered_at = utcnow()
                _advance(o, "delivered")
            activity.info("tracking", f"Order #{oid} delivered", order_id=oid)
    # retry uploads that failed earlier
    with session_scope() as s:
        pending = [o.id for o in s.query(Order).filter(Order.tracking_number != "", Order.tracking_uploaded_at.is_(None),
                                                       Order.carrier.in_(["UPS", "USPS", "FEDEX"]),
                                                       Order.status.notin_(list(TERMINAL)))]
    for oid in pending:
        upload_tracking(oid)
    return {"checked": len(rows), "new_tracking": found}


# ---- fees (Finances API) -----------------------------------------------------------------------------

def _sign(t: dict) -> int:
    return -1 if t.get("bookingEntry") == "CREDIT" else 1


def sync_fees() -> dict:
    env = st.get("ebay_environment")
    cutoff = utcnow() - timedelta(days=60)
    stale = utcnow() - timedelta(hours=20)
    with session_scope() as s:
        rows = [(o.id, o.ebay_order_id, o.created_at) for o in s.query(Order).filter(
            Order.environment == env, Order.created_at >= cutoff,
            (Order.fees_synced_at.is_(None)) | (Order.fees_synced_at < stale))]
    if not rows:
        return {"orders": 0}
    ad_by_order: dict[str, float] = {}
    try:
        start = min(r[2] for r in rows).replace(tzinfo=timezone.utc)
        for t in ebay.get_ad_fee_transactions(start, datetime.now(timezone.utc)):
            if t.get("feeType") != "AD_FEE":
                continue
            for ref in t.get("references", []) or []:
                if ref.get("referenceType") == "ORDER_ID":
                    ad_by_order[ref["referenceId"]] = ad_by_order.get(ref["referenceId"], 0.0) + _sign(t) * _amt(t.get("amount"))
    except EbayNotConnected as exc:
        return {"skipped": str(exc)}
    except EbayError as exc:
        activity.warning("fees", f"Could not load ad-fee transactions: {exc}")
    updated = 0
    for oid, ebay_id, _ in rows:
        try:
            txs = ebay.get_order_transactions(ebay_id)
        except EbayError as exc:
            activity.warning("fees", f"Finances lookup failed for {ebay_id}: {exc}", order_id=oid)
            continue
        fees = promo = refund = 0.0
        sale_seen = False
        seen_ad_ids = set()
        for t in txs:
            typ = t.get("transactionType")
            if typ == "SALE":
                sale_seen = True
                line_fees = [f for li in t.get("orderLineItems", []) for f in li.get("marketplaceFees", [])]
                if line_fees:
                    for f in line_fees:
                        if f.get("feeType") == "AD_FEE":
                            promo += _amt(f.get("amount"))
                        else:
                            fees += _amt(f.get("amount"))
                else:
                    fees += _amt(t.get("totalFeeAmount"))
            elif typ == "REFUND":
                refund += _amt(t.get("amount"))
                fees -= _amt(t.get("totalFeeAmount"))
            elif typ in ("NON_SALE_CHARGE", "CREDIT") and t.get("feeType"):
                if t.get("feeType") == "AD_FEE":
                    promo += _sign(t) * _amt(t.get("amount"))
                    seen_ad_ids.add(t.get("transactionId"))
                else:
                    fees += _sign(t) * _amt(t.get("amount"))
        if not seen_ad_ids:
            promo += ad_by_order.get(ebay_id, 0.0)
        with session_scope() as s:
            o = s.get(Order, oid)
            o.fees_synced_at = utcnow()
            if sale_seen:
                changed = (o.ebay_fees_actual, o.promo_fee_actual) != (round(fees, 2), round(promo, 2))
                o.ebay_fees_actual, o.promo_fee_actual = round(fees, 2), round(promo, 2)
                if refund:
                    o.refund_to_buyer, o.refund_is_actual = round(refund, 2), True
                if changed:
                    updated += 1
                    activity.info("fees", f"Order {ebay_id}: actual eBay fees ${fees:.2f}, promo ${promo:.2f}"
                                          + (f", refund ${refund:.2f}" if refund else ""), order_id=oid)
    return {"orders": len(rows), "updated": updated}


def sync_returns() -> dict:
    env = st.get("ebay_environment")
    try:
        members = ebay.search_returns(datetime.now(timezone.utc) - timedelta(days=90))
    except EbayNotConnected as exc:
        return {"skipped": str(exc)}
    except EbayError as exc:
        return {"skipped": f"returns lookup unavailable: {exc}"}
    n = 0
    for m in members:
        oid = m.get("orderId")
        if not oid:
            continue
        with session_scope() as s:
            o = s.query(Order).filter_by(ebay_order_id=oid, environment=env).one_or_none()
            if o and o.status not in ("returned", "refunded", "cancelled"):
                o.status = "returned"
                o.notes = (o.notes + f"\nReturn {m.get('returnId', '')}: {m.get('state') or m.get('status', '')}").strip()
                n += 1
                activity.info("order", f"Order {oid} has a return ({m.get('state') or m.get('status', '')})", order_id=o.id)
    return {"returns": n}


# ---- traffic -------------------------------------------------------------------------------------

def sync_traffic() -> dict:
    env = st.get("ebay_environment")
    with session_scope() as s:
        rows = [(l.id, l.ebay_listing_id, l.created_at) for l in s.query(Listing).filter(
            Listing.environment == env, Listing.dry_run.is_(False), Listing.ebay_listing_id.isnot(None),
            Listing.status != "ended")]
    if not rows:
        return {"listings": 0}
    end = datetime.now(timezone.utc)
    start = max(min(r[2] for r in rows).replace(tzinfo=timezone.utc), end - timedelta(days=89))
    try:
        traffic = ebay.traffic_report([r[1] for r in rows], start, end)
    except EbayNotConnected as exc:
        return {"skipped": str(exc)}
    except EbayError as exc:
        activity.warning("ebay", f"Traffic report unavailable: {exc}")
        traffic = {}
    try:
        watchers = ebay.watch_counts()
    except EbayError as exc:
        activity.warning("ebay", f"Watcher counts unavailable: {exc}")
        watchers = {}
    with session_scope() as s:
        for lid, ebay_id, _ in rows:
            l = s.get(Listing, lid)
            if ebay_id in traffic:
                l.views, l.impressions = traffic[ebay_id]["views"], traffic[ebay_id]["impressions"]
            if ebay_id in watchers:
                l.watchers = watchers[ebay_id]
    return {"listings": len(rows), "with_traffic": len(traffic), "with_watchers": len(watchers)}
