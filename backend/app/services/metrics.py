"""Dashboard KPIs and chart series."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone

from ..db import session_scope
from ..models import Listing, Order
from .orders import financials


def resolve_range(rng: str, start: str | None = None, end: str | None = None) -> tuple[datetime | None, datetime]:
    """Return (start_utc_naive | None, end_utc_naive) for today/7d/30d/90d/all/custom (local-day boundaries)."""
    tz = datetime.now().astimezone().tzinfo
    today = datetime.now(tz).date()

    def utc(d: date, t: time = time(0)) -> datetime:
        return datetime.combine(d, t, tzinfo=tz).astimezone(timezone.utc).replace(tzinfo=None)

    end_dt = utc(today + timedelta(days=1))
    if rng == "today":
        return utc(today), end_dt
    if rng in ("7d", "30d", "90d"):
        return utc(today - timedelta(days=int(rng[:-1]) - 1)), end_dt
    if rng == "custom" and start:
        s = date.fromisoformat(start)
        e = date.fromisoformat(end) if end else today
        return utc(s), utc(e + timedelta(days=1))
    return None, end_dt


def _local_day(dt: datetime) -> str:
    return dt.replace(tzinfo=timezone.utc).astimezone().date().isoformat()


def overview(rng: str = "30d", start: str | None = None, end: str | None = None) -> dict:
    s_dt, e_dt = resolve_range(rng, start, end)
    with session_scope() as s:
        oq = s.query(Order).filter(Order.created_at < e_dt, Order.managed.is_(True))
        lq = s.query(Listing).filter(Listing.created_at < e_dt)
        if s_dt:
            oq, lq = oq.filter(Order.created_at >= s_dt), lq.filter(Listing.created_at >= s_dt)
        orders = oq.all()
        new_listings = lq.all()
        all_listings = s.query(Listing).all()
        tot = defaultdict(float)
        series = defaultdict(lambda: defaultdict(float))
        sold_listing_ids = set()
        n_orders = units = n_est = 0
        for o in orders:
            f = financials(o)
            day = _local_day(o.created_at)
            if o.status != "cancelled":
                n_orders += 1
                units += o.quantity
                if o.listing_id:
                    sold_listing_ids.add(o.listing_id)
            for k in ("revenue", "buyer_tax", "amazon_cost", "amazon_refund", "ebay_fees", "promo_fee", "refund_to_buyer", "profit"):
                tot[k] += f[k]
            if not (f["fees_are_actual"] and f["amazon_cost_is_actual"]) and o.status != "cancelled":
                n_est += 1
            series[day]["revenue"] += f["revenue"]
            series[day]["profit"] += f["profit"]
            series[day]["orders"] += 0 if o.status == "cancelled" else 1
        for l in new_listings:
            series[_local_day(l.created_at)]["listings_live" if not l.dry_run else "listings_dry_run"] += 1
        active = [l for l in all_listings if l.status == "active" and not l.dry_run]
        qty0 = [l for l in all_listings if l.status == "qty0" and not l.dry_run]
        today_start = resolve_range("today")[0]
        posted_today = sum(1 for l in all_listings if l.created_at >= today_start and not l.dry_run)
        dry_today = sum(1 for l in all_listings if l.created_at >= today_start and l.dry_run)
    amazon_spend = tot["amazon_cost"] - tot["amazon_refund"]
    sales_ex_tax = tot["revenue"] - tot["buyer_tax"]
    net = tot["profit"]
    days = sorted(series)
    if s_dt and days:
        d, last = date.fromisoformat(_local_day(s_dt)), date.fromisoformat(days[-1])
        while d <= last:
            series[d.isoformat()]
            d += timedelta(days=1)
        days = sorted(series)
    return {
        "range": rng,
        "kpis": {
            "active_listings": len(active), "qty0_listings": len(qty0),
            "listings_posted_today": posted_today, "dry_run_previews_today": dry_today,
            "listings_posted_period": sum(1 for l in new_listings if not l.dry_run),
            "orders": n_orders, "units_sold": units,
            "revenue": round(tot["revenue"], 2), "buyer_tax": round(tot["buyer_tax"], 2),
            "amazon_spend": round(amazon_spend, 2), "amazon_refunds": round(tot["amazon_refund"], 2),
            "ebay_fees": round(tot["ebay_fees"], 2), "promo_fees": round(tot["promo_fee"], 2),
            "refunds": round(tot["refund_to_buyer"], 2),
            "net_profit": round(net, 2),
            "profit_margin_pct": round(net / sales_ex_tax * 100, 1) if sales_ex_tax else None,
            "roi_pct": round(net / amazon_spend * 100, 1) if amazon_spend else None,
            "avg_profit_per_order": round(net / n_orders, 2) if n_orders else None,
            "sell_through_pct": round(len(sold_listing_ids) / len(active) * 100, 1) if active else None,
            "orders_with_estimates": n_est,
        },
        "series": [{"date": d, "revenue": round(series[d]["revenue"], 2), "profit": round(series[d]["profit"], 2),
                    "orders": int(series[d]["orders"]), "listings": int(series[d]["listings_live"]),
                    "dry_run_listings": int(series[d]["listings_dry_run"])} for d in days],
    }


def listing_stats() -> dict[int, dict]:
    """{listing_id: {"units": n, "profit": $, "orders": n}}"""
    out: dict[int, dict] = defaultdict(lambda: {"units": 0, "profit": 0.0, "orders": 0})
    with session_scope() as s:
        for o in s.query(Order).filter(Order.listing_id.isnot(None), Order.status != "cancelled"):
            f = financials(o)
            st = out[o.listing_id]
            st["units"] += o.quantity
            st["orders"] += 1
            st["profit"] = round(st["profit"] + f["profit"], 2)
    return dict(out)


def best_and_worst(limit: int = 10) -> dict:
    stats = listing_stats()
    with session_scope() as s:
        listings = {l.id: l for l in s.query(Listing).filter(Listing.dry_run.is_(False)).all()}

    def row(lid):
        l = listings[lid]
        return {"id": lid, "title": l.title, "image": (l.image_urls or [""])[0], "price": l.price, "status": l.status,
                "views": l.views, "watchers": l.watchers, **stats.get(lid, {"units": 0, "profit": 0.0, "orders": 0})}

    sold = [lid for lid in stats if lid in listings]
    by_profit = sorted(sold, key=lambda i: stats[i]["profit"], reverse=True)
    return {
        "top_profit": [row(i) for i in by_profit[:limit]],
        "top_units": [row(i) for i in sorted(sold, key=lambda i: stats[i]["units"], reverse=True)[:limit]],
        "losers": [row(i) for i in sorted(sold, key=lambda i: stats[i]["profit"])[:limit] if stats[i]["profit"] < 0],
        "views_no_sales": [row(i) for i in sorted((i for i, l in listings.items() if i not in stats and l.status != "ended"),
                                                  key=lambda i: listings[i].views, reverse=True)[:limit]
                           if listings[i].views > 0],
    }
