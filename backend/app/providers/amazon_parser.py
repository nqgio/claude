"""Pure HTML parsing for Amazon pages (no network). Kept separate so it can be
unit-tested against saved pages and fixed quickly when Amazon changes markup."""
from __future__ import annotations

import json
import re
from datetime import date, datetime

from bs4 import BeautifulSoup

from .base import ProductData, SearchResult, TrackingInfo

_PRICE_RE = re.compile(r"\$\s*([0-9][0-9,]*\.?[0-9]{0,2})")
_INT_RE = re.compile(r"([0-9][0-9,]*)")
_ASIN_RE = re.compile(r"^[A-Z0-9]{10}$")
_MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
     "november", "december"], 1)}
_MONTHS.update({k[:3]: v for k, v in list(_MONTHS.items())})


def is_block_page(html: str, url: str = "") -> bool:
    """CAPTCHA / robot-check / automated-access block pages. We never try to solve these."""
    low = html[:200000].lower()
    signals = [
        "/errors/validatecaptcha",
        "type the characters you see in this image",
        "enter the characters you see below",
        "sorry, we just need to make sure you're not a robot",
        "to discuss automated access to amazon data",
        "api-services-support@amazon.com",
    ]
    return "validatecaptcha" in url.lower() or any(s in low for s in signals)


def parse_price(text: str | None) -> float | None:
    if not text:
        return None
    m = _PRICE_RE.search(text)
    if not m:
        try:
            return float(text.replace(",", "").strip())
        except ValueError:
            return None
    return float(m.group(1).replace(",", ""))


def _int(text: str | None) -> int | None:
    if not text:
        return None
    m = _INT_RE.search(text.replace(" ", " "))
    return int(m.group(1).replace(",", "")) if m else None


def _rating(text: str | None) -> float | None:
    if not text:
        return None
    m = re.search(r"([0-5](?:\.\d)?) out of 5", text)
    return float(m.group(1)) if m else None


def _clean(text: str | None) -> str:
    return re.sub(r"\s+", " ", (text or "").replace("‎", "").replace("‏", "")).strip()


def parse_search(html: str) -> list[SearchResult]:
    soup = BeautifulSoup(html, "lxml")
    results = []
    for card in soup.select('div[data-component-type="s-search-result"][data-asin]'):
        asin = (card.get("data-asin") or "").strip()
        if not _ASIN_RE.match(asin):
            continue
        title_el = card.select_one("h2 span") or card.select_one("h2")
        price_el = card.select_one(".a-price:not(.a-text-price) .a-offscreen") or card.select_one(".a-price .a-offscreen")
        rating_el = card.select_one("span.a-icon-alt")
        reviews_el = (card.select_one('[aria-label$="ratings"]') or card.select_one('a[href*="customerReviews"] span')
                      or card.select_one("span.a-size-base.s-underline-text"))
        reviews_txt = reviews_el.get("aria-label") or reviews_el.get_text() if reviews_el else None
        img = card.select_one("img.s-image")
        text = card.get_text(" ").lower()
        results.append(SearchResult(
            asin=asin,
            title=_clean(title_el.get_text() if title_el else ""),
            price=parse_price(price_el.get_text() if price_el else None),
            rating=_rating(rating_el.get_text() if rating_el else None),
            review_count=_parse_count(reviews_txt),
            prime=bool(card.select_one("i.a-icon-prime, [aria-label='Amazon Prime']")),
            sponsored="sponsored" in text[:400],
            image=img.get("src", "") if img else "",
        ))
    return results


def _parse_count(text: str | None) -> int | None:
    if not text:
        return None
    t = text.strip().lower().replace(",", "")
    m = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*([km])?", t)
    if not m:
        return None
    n = float(m.group(1))
    if m.group(2) == "k":
        n *= 1000
    elif m.group(2) == "m":
        n *= 1_000_000
    return int(n)


def _images(soup: BeautifulSoup, html: str) -> list[str]:
    urls: list[str] = []
    m = re.search(r"'colorImages'\s*:\s*\{\s*'initial'\s*:\s*(\[.*?\])\s*\}", html, re.S)
    if m:
        try:
            for img in json.loads(m.group(1)):
                u = img.get("hiRes") or img.get("large")
                if u and u not in urls:
                    urls.append(u)
        except (ValueError, AttributeError):
            pass
    if not urls:
        land = soup.select_one("#landingImage") or soup.select_one("#imgBlkFront")
        if land:
            if land.get("data-old-hires"):
                urls.append(land["data-old-hires"])
            elif land.get("data-a-dynamic-image"):
                try:
                    dyn = json.loads(land["data-a-dynamic-image"])
                    urls.append(max(dyn.items(), key=lambda kv: kv[1][0] * kv[1][1])[0])
                except (ValueError, KeyError):
                    pass
            elif land.get("src"):
                urls.append(land["src"])
    return urls[:12]


def _details(soup: BeautifulSoup) -> dict[str, str]:
    out: dict[str, str] = {}
    for row in soup.select("#productOverview_feature_div tr, #productDetails_techSpec_section_1 tr, "
                           "#productDetails_detailBullets_sections1 tr, #technicalSpecifications_section_1 tr"):
        k, v = row.select_one("th, td:nth-of-type(1)"), row.select_one("td:nth-of-type(2), td")
        if k and v and k is not v:
            key, val = _clean(k.get_text()).rstrip(":"), _clean(v.get_text())
            if key and val and key not in out:
                out[key] = val
    for li in soup.select("#detailBullets_feature_div li"):
        spans = li.select("span > span")
        if len(spans) >= 2:
            key = _clean(spans[0].get_text()).rstrip(":").strip(" :")
            val = _clean(spans[1].get_text())
            if key and val and key not in out:
                out[key] = val
    out.pop("Customer Reviews", None)
    out.pop("Best Sellers Rank", None)
    return out


def _delivery_days(soup: BeautifulSoup, today: date | None = None) -> int | None:
    today = today or datetime.now().date()
    el = soup.select_one("#mir-layout-DELIVERY_BLOCK [data-csa-c-delivery-time]") or soup.select_one(
        "[data-csa-c-delivery-time]")
    text = el.get("data-csa-c-delivery-time") if el else ""
    if not text:
        block = soup.select_one("#mir-layout-DELIVERY_BLOCK, #deliveryBlockMessage")
        text = block.get_text(" ") if block else ""
    text = _clean(text).lower()
    if not text:
        return None
    if "today" in text or "overnight" in text:
        return 0
    if "tomorrow" in text:
        return 1
    # e.g. "Thursday, October 30" or "Oct 30 - Nov 2" (use the latest date mentioned)
    days = []
    for mon, day in re.findall(r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{1,2})", text):
        month = _MONTHS[mon]
        year = today.year + (1 if month < today.month - 6 else 0)
        try:
            days.append((date(year, month, int(day)) - today).days)
        except ValueError:
            continue
    return max(days) if days else None


def parse_product(html: str, asin: str, url: str = "", today: date | None = None) -> ProductData:
    soup = BeautifulSoup(html, "lxml")
    title_el = soup.select_one("#productTitle")
    if not title_el:
        raise ValueError("product title not found (not a product page?)")
    price = None
    for sel in ["#corePrice_feature_div .a-price .a-offscreen", "#corePriceDisplay_desktop_feature_div .a-price .a-offscreen",
                "#apex_desktop .a-price .a-offscreen", "#priceblock_ourprice", "#priceblock_dealprice",
                "#price_inside_buybox", "#newBuyBoxPrice", ".a-price .a-offscreen"]:
        el = soup.select_one(sel)
        if el and parse_price(el.get_text()):
            price = parse_price(el.get_text())
            break
    if price is None:
        whole = soup.select_one("#corePrice_feature_div .a-price-whole, .a-price .a-price-whole")
        frac = soup.select_one("#corePrice_feature_div .a-price-fraction, .a-price .a-price-fraction")
        if whole:
            price = parse_price(_clean(whole.get_text()).rstrip(".") + "." + (_clean(frac.get_text()) if frac else "00"))

    avail_el = soup.select_one("#availability")
    avail = _clean(avail_el.get_text() if avail_el else "")
    low = avail.lower()
    has_buy = bool(soup.select_one("#add-to-cart-button, #buy-now-button"))
    out_words = ("currently unavailable", "out of stock", "temporarily out of stock", "unavailable")
    in_stock = (has_buy and not any(w in low for w in out_words)) if (avail or has_buy) else False
    if "in stock" in low or re.search(r"only \d+ left in stock", low):
        in_stock = True

    brand = ""
    po = soup.select_one("#productOverview_feature_div tr.po-brand td.po-break-word")
    if po:
        brand = _clean(po.get_text())
    if not brand:
        byline = soup.select_one("#bylineInfo")
        if byline:
            t = _clean(byline.get_text())
            m = re.match(r"(?:Visit the\s+(.+?)\s+Store|Brand:\s*(.+))$", t)
            brand = (m.group(1) or m.group(2)) if m else t
    details = _details(soup)
    brand = brand or details.get("Brand", "") or details.get("Manufacturer", "")

    rating_el = soup.select_one("#acrPopover")
    rating = _rating(rating_el.get("title") if rating_el and rating_el.get("title") else
                     (soup.select_one("#acrPopover span.a-icon-alt") or soup.select_one("span.a-icon-alt") or BeautifulSoup("", "lxml")).get_text())
    reviews_el = soup.select_one("#acrCustomerReviewText")

    prime = bool(soup.select_one("#prime-badge, i.a-icon-prime, #primeBadge, [data-csa-c-delivery-benefit-program-id='prime'], "
                                 "#deliveryBlockMessage i.a-icon-prime"))

    crumbs = [_clean(a.get_text()) for a in soup.select("#wayfinding-breadcrumbs_feature_div ul li a")]
    features = [_clean(li.get_text()) for li in soup.select("#feature-bullets ul li span.a-list-item")]
    features = [f for f in features if f and not f.lower().startswith("make sure this fits")]
    desc_el = soup.select_one("#productDescription")

    return ProductData(
        asin=asin,
        url=url or f"https://www.amazon.com/dp/{asin}",
        title=_clean(title_el.get_text()),
        brand=brand,
        price=price,
        in_stock=bool(in_stock and price),
        availability_text=avail[:200],
        prime=prime,
        rating=rating,
        review_count=_int(reviews_el.get_text() if reviews_el else None),
        category=" > ".join(c for c in crumbs if c),
        images=_images(soup, html),
        features=features[:10],
        details=details,
        description=_clean(desc_el.get_text() if desc_el else "")[:3000],
        delivery_days=_delivery_days(soup, today),
    )


# ---- Order-side pages (logged-in account) ----------------------------------------

ORDER_ID_RE = re.compile(r"\b(\d{3}-\d{7}-\d{7})\b")


def parse_order_total(html: str) -> float | None:
    """Final 'Order total' on the checkout review page."""
    soup = BeautifulSoup(html, "lxml")
    for row in soup.select("#subtotals-marketplace-table tr, .order-summary-line-definition, #subtotals tr, li, tr"):
        txt = _clean(row.get_text(" "))
        if re.search(r"order total", txt, re.I):
            p = parse_price(txt)
            if p is not None:
                return p
    m = re.search(r"Order total:?\s*\$\s*([0-9,]+\.\d{2})", soup.get_text(" "), re.I)
    return float(m.group(1).replace(",", "")) if m else None


def parse_shipping_cost(html: str) -> float | None:
    """'Shipping & handling' charge on the checkout review page (0.0 when free, None if not shown)."""
    text = re.sub(r"\s+", " ", BeautifulSoup(html, "lxml").get_text(" "))
    m = re.search(r"Shipping\s*(?:&|and)\s*handling:?\s*(FREE|\$\s*[0-9,]+\.\d{2})", text, re.I)
    if not m:
        return None
    return 0.0 if m.group(1).upper() == "FREE" else parse_price(m.group(1))


def parse_order_id(html: str) -> str:
    m = ORDER_ID_RE.search(BeautifulSoup(html, "lxml").get_text(" "))
    return m.group(1) if m else ""


def parse_tracking(html: str) -> TrackingInfo:
    text = _clean(BeautifulSoup(html, "lxml").get_text(" "))
    info = TrackingInfo(status_text=text[:200])
    m = re.search(r"Tracking ID:?\s*([A-Z0-9]{8,40})", text, re.I)
    if m:
        info.tracking_number = m.group(1).upper()
    c = re.search(r"(?:Shipped with|Delivery by|Carrier:?)\s*(UPS|USPS|FedEx|Amazon(?: Logistics)?|DHL|OnTrac|LaserShip)", text, re.I)
    if c:
        info.carrier = c.group(1)
    info.delivered = bool(re.search(r"\bDelivered\b", text))
    return info
