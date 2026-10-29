"""Thin wrappers over the eBay APIs this app uses (official REST APIs plus one
read-only Trading API call for watcher counts)."""
from __future__ import annotations

import functools
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from urllib.parse import quote

from .. import settings_store as st
from .client import EbayError, get_json, request

INV = "/sell/inventory/v1"
ACC = "/sell/account/v1"
MKT = "/sell/marketing/v1"
FUL = "/sell/fulfillment/v1"
FIN = "/sell/finances/v1"
TAX = "/commerce/taxonomy/v1"


def _q(s: str) -> str:
    return quote(s, safe="")


def _id_from_location(resp) -> str:
    loc = resp.headers.get("Location", "")
    return loc.rstrip("/").rsplit("/", 1)[-1] if loc else ""


# ---- Inventory API ------------------------------------------------------------------

def ensure_location(key: str, postal_code: str, city: str = "", state: str = "") -> None:
    try:
        get_json(f"{INV}/location/{_q(key)}")
        return
    except EbayError as exc:
        if exc.status not in (404, 400):
            raise
    address = {"postalCode": postal_code, "country": "US"}
    if city:
        address["city"] = city
    if state:
        address["stateOrProvince"] = state
    request("POST", f"{INV}/location/{_q(key)}", json={
        "location": {"address": address}, "locationTypes": ["WAREHOUSE"], "name": "Default location",
        "merchantLocationStatus": "ENABLED"})


def put_inventory_item(sku: str, item: dict) -> None:
    request("PUT", f"{INV}/inventory_item/{_q(sku)}", json=item)


def get_offers_for_sku(sku: str) -> list[dict]:
    try:
        return get_json(f"{INV}/offer", params={"sku": sku, "marketplace_id": st.get("marketplace_id")}).get("offers", [])
    except EbayError as exc:
        if exc.status == 404:
            return []
        raise


def get_offer(offer_id: str) -> dict | None:
    """The offer, including listing.listingStatus (ACTIVE, OUT_OF_STOCK, ENDED, EBAY_ENDED…); None if it's gone."""
    try:
        return get_json(f"{INV}/offer/{_q(offer_id)}")
    except EbayError as exc:
        if exc.status == 404:
            return None
        raise


def create_offer(offer: dict) -> str:
    return request("POST", f"{INV}/offer", json=offer).json()["offerId"]


def update_offer(offer_id: str, offer: dict) -> None:
    request("PUT", f"{INV}/offer/{_q(offer_id)}", json=offer)


def publish_offer(offer_id: str) -> str:
    return request("POST", f"{INV}/offer/{_q(offer_id)}/publish").json()["listingId"]


def update_price_quantity(sku: str, offer_id: str, quantity: int | None = None, price: float | None = None) -> None:
    offer: dict = {"offerId": offer_id}
    req: dict = {"sku": sku, "offers": [offer]}
    if quantity is not None:
        offer["availableQuantity"] = quantity
        req["shipToLocationAvailability"] = {"quantity": quantity}
    if price is not None:
        offer["price"] = {"value": f"{price:.2f}", "currency": "USD"}
    resp = request("POST", f"{INV}/bulk_update_price_quantity", json={"requests": [req]}).json()
    for r in resp.get("responses", []):
        if r.get("statusCode", 200) >= 400:
            msgs = "; ".join(e.get("message", "") for e in r.get("errors", []))
            raise EbayError(f"price/quantity update failed for {sku}: {msgs}", r.get("statusCode"), r)


def withdraw_offer(offer_id: str) -> None:
    request("POST", f"{INV}/offer/{_q(offer_id)}/withdraw")


# ---- Account API ----------------------------------------------------------------------

def get_policies() -> dict:
    mp = st.get("marketplace_id")
    out = {}
    for kind, key in (("fulfillment", "fulfillmentPolicies"), ("return", "returnPolicies"), ("payment", "paymentPolicies")):
        data = get_json(f"{ACC}/{kind}_policy", params={"marketplace_id": mp})
        rows = []
        for p in data.get(key, []):
            row = {"id": p.get(f"{kind}PolicyId"), "name": p.get("name"), "description": p.get("description", "")}
            if kind == "fulfillment":
                ht = p.get("handlingTime") or {}
                row["handling_time_days"] = ht.get("value")
                opts = []
                for o in p.get("shippingOptions", []):
                    for svc in o.get("shippingServices", []):
                        opts.append({"service": svc.get("shippingServiceCode"), "free": svc.get("freeShipping", False),
                                     "cost": (svc.get("shippingCost") or {}).get("value")})
                row["shipping"] = opts
            if kind == "return":
                row["returns_accepted"] = p.get("returnsAccepted")
                row["period"] = (p.get("returnPeriod") or {}).get("value")
            rows.append(row)
        out[kind] = rows
    return out


def opt_in_business_policies() -> None:
    progs = get_json(f"{ACC}/program/get_opted_in_programs").get("programs", [])
    if not any(p.get("programType") == "SELLING_POLICY_MANAGEMENT" for p in progs):
        request("POST", f"{ACC}/program/opt_in", json={"programType": "SELLING_POLICY_MANAGEMENT"})


# ---- Marketing API (Promoted Listings, general / cost-per-sale) --------------------------

def find_or_create_campaign(name: str, bid_percent: float) -> str:
    try:
        c = get_json(f"{MKT}/ad_campaign/get_campaign_by_name", params={"campaign_name": name})
        if c.get("campaignId"):
            return c["campaignId"]
    except EbayError as exc:
        if exc.status not in (404, 400):
            raise
    resp = request("POST", f"{MKT}/ad_campaign", json={
        "campaignName": name, "marketplaceId": st.get("marketplace_id"),
        "startDate": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "fundingStrategy": {"fundingModel": "COST_PER_SALE", "bidPercentage": f"{bid_percent:.1f}"}})
    return _id_from_location(resp)


def create_ad(campaign_id: str, listing_id: str, bid_percent: float) -> str:
    resp = request("POST", f"{MKT}/ad_campaign/{_q(campaign_id)}/ad",
                   json={"listingId": listing_id, "bidPercentage": f"{bid_percent:.1f}"})
    return _id_from_location(resp)


# ---- Fulfillment API ------------------------------------------------------------------------

def get_orders_modified_since(since: datetime) -> list[dict]:
    flt = f"lastmodifieddate:[{since.strftime('%Y-%m-%dT%H:%M:%S.000Z')}..]"
    orders, offset = [], 0
    while True:
        data = get_json(f"{FUL}/order", params={"filter": flt, "limit": 200, "offset": offset})
        batch = data.get("orders", [])
        orders.extend(batch)
        offset += len(batch)
        if not batch or offset >= int(data.get("total", 0)):
            return orders


def create_shipping_fulfillment(order_id: str, line_items: list[dict], carrier: str, tracking: str) -> str:
    resp = request("POST", f"{FUL}/order/{_q(order_id)}/shipping_fulfillment", json={
        "lineItems": line_items, "shippedDate": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "shippingCarrierCode": carrier, "trackingNumber": tracking})
    return _id_from_location(resp)


def search_returns(since: datetime) -> list[dict]:
    """Post-Order API return search (best effort — not every account/environment supports it)."""
    data = get_json("/post-order/v2/return/search", params={
        "creation_date_range_from": since.strftime("%Y-%m-%dT%H:%M:%S.000Z"), "limit": 200},
        headers={"Authorization": f"IAF {_bearer()}"})
    return data.get("members", [])


def _bearer() -> str:
    from .client import user_token

    return user_token()


# ---- Finances API ---------------------------------------------------------------------------

def get_order_transactions(order_id: str) -> list[dict]:
    out, offset = [], 0
    while True:
        data = get_json(f"{FIN}/transaction", host="apiz", family="finances",
                        params={"filter": f"orderId:{{{order_id}}}", "limit": 200, "offset": offset})
        batch = data.get("transactions", [])
        out.extend(batch)
        offset += len(batch)
        if not batch or offset >= int(data.get("total", 0)):
            return out


def get_ad_fee_transactions(start: datetime, end: datetime) -> list[dict]:
    out, offset = [], 0
    rng = f"transactionDate:[{start.strftime('%Y-%m-%dT%H:%M:%S.000Z')}..{end.strftime('%Y-%m-%dT%H:%M:%S.000Z')}]"
    while True:
        data = get_json(f"{FIN}/transaction", host="apiz", family="finances",
                        params={"filter": f"{rng},transactionType:{{NON_SALE_CHARGE}}", "limit": 200, "offset": offset})
        batch = data.get("transactions", [])
        out.extend(batch)
        offset += len(batch)
        if not batch or offset >= int(data.get("total", 0)):
            return out


# ---- Analytics API ----------------------------------------------------------------------------

def traffic_report(listing_ids: list[str], start: datetime, end: datetime) -> dict[str, dict]:
    """{listing_id: {"views": n, "impressions": n}} over the date range."""
    out: dict[str, dict] = {}
    for i in range(0, len(listing_ids), 200):
        chunk = listing_ids[i:i + 200]
        flt = (f"marketplace_ids:{{{st.get('marketplace_id')}}},date_range:[{start:%Y%m%d}..{end:%Y%m%d}],"
               f"listing_ids:{{{'|'.join(chunk)}}}")
        data = get_json("/sell/analytics/v1/traffic_report", family="analytics", params={
            "dimension": "LISTING", "metric": "LISTING_VIEWS_TOTAL,LISTING_IMPRESSION_TOTAL", "filter": flt})
        metrics = [m.get("key") for m in (data.get("header") or {}).get("metrics", [])]
        for rec in data.get("records", []):
            lid = (rec.get("dimensionValues") or [{}])[0].get("value")
            vals = {metrics[j]: (mv.get("value") or 0) for j, mv in enumerate(rec.get("metricValues", [])) if j < len(metrics)}
            out[lid] = {"views": int(vals.get("LISTING_VIEWS_TOTAL", 0)),
                        "impressions": int(vals.get("LISTING_IMPRESSION_TOTAL", 0))}
    return out


# ---- Trading API (read-only): watcher counts -----------------------------------------------------

_NS = {"e": "urn:ebay:apis:eBLBaseComponents"}


def watch_counts() -> dict[str, int]:
    out: dict[str, int] = {}
    page = 1
    while True:
        body = f"""<?xml version="1.0" encoding="utf-8"?>
<GetMyeBaySellingRequest xmlns="urn:ebay:apis:eBLBaseComponents">
  <ActiveList><Include>true</Include><IncludeWatchCount>true</IncludeWatchCount>
    <Pagination><EntriesPerPage>200</EntriesPerPage><PageNumber>{page}</PageNumber></Pagination></ActiveList>
  <DetailLevel>ReturnAll</DetailLevel>
</GetMyeBaySellingRequest>"""
        r = request("POST", "/ws/api.dll", content=body, write=False, family="trading", headers={
            "Content-Type": "text/xml", "X-EBAY-API-CALL-NAME": "GetMyeBaySelling", "X-EBAY-API-SITEID": "0",
            "X-EBAY-API-COMPATIBILITY-LEVEL": "1193", "X-EBAY-API-IAF-TOKEN": _bearer()})
        root = ET.fromstring(r.content)
        for item in root.iterfind(".//e:ActiveList/e:ItemArray/e:Item", _NS):
            iid = item.findtext("e:ItemID", default="", namespaces=_NS)
            out[iid] = int(item.findtext("e:WatchCount", default="0", namespaces=_NS) or 0)
        pages = int(root.findtext(".//e:ActiveList/e:PaginationResult/e:TotalNumberOfPages", default="1", namespaces=_NS) or 1)
        if page >= pages:
            return out
        page += 1


# ---- Taxonomy API ----------------------------------------------------------------------------------

@functools.lru_cache(maxsize=4)
def category_tree_id(environment: str) -> str:
    return get_json(f"{TAX}/get_default_category_tree_id", token="app", environment=environment,
                    params={"marketplace_id": st.get("marketplace_id")})["categoryTreeId"]


def category_suggestions(query: str) -> list[dict]:
    env = st.get("ebay_environment")
    data = get_json(f"{TAX}/category_tree/{category_tree_id(env)}/get_category_suggestions", token="app",
                    params={"q": query[:350]})
    return [{"id": s["category"]["categoryId"], "name": s["category"]["categoryName"],
             "path": " > ".join(a["categoryName"] for a in reversed(s.get("categoryTreeNodeAncestors", [])))}
            for s in data.get("categorySuggestions", [])]


@functools.lru_cache(maxsize=512)
def _aspects_cached(environment: str, category_id: str) -> tuple:
    data = get_json(f"{TAX}/category_tree/{category_tree_id(environment)}/get_item_aspects_for_category", token="app",
                    environment=environment, params={"category_id": category_id})
    out = []
    for a in data.get("aspects", []):
        c = a.get("aspectConstraint", {})
        out.append({"name": a.get("localizedAspectName"), "required": bool(c.get("aspectRequired")),
                    "mode": c.get("aspectMode", "FREE_TEXT"),
                    "values": tuple(v.get("localizedValue") for v in a.get("aspectValues", [])[:500])})
    return tuple(out)


def item_aspects(category_id: str) -> list[dict]:
    return list(_aspects_cached(st.get("ebay_environment"), category_id))
