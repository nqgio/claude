import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";
import { Card, Kpi, money, pct, useLoad } from "../components/ui";

const RANGES = [["today", "Today"], ["7d", "7 days"], ["30d", "30 days"], ["90d", "90 days"], ["all", "All time"], ["custom", "Custom"]];

export default function Overview() {
  const [range, setRange] = useState("30d");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const qs = range === "custom" ? `range=custom&start=${start}&end=${end}` : `range=${range}`;
  const [data, , error] = useLoad(() => (range === "custom" && !start ? Promise.resolve(null) : api.get(`/metrics?${qs}`)), [qs], 60000);
  const k = data?.kpis;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        {RANGES.map(([v, l]) => (
          <button
            key={v}
            onClick={() => setRange(v)}
            className={`rounded-md px-3 py-1.5 text-sm ${range === v ? "bg-slate-800 text-white dark:bg-slate-200 dark:text-slate-900" : "border border-slate-300 dark:border-slate-700"}`}
          >
            {l}
          </button>
        ))}
        {range === "custom" && (
          <>
            <input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
            <span>to</span>
            <input type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
          </>
        )}
      </div>
      {error && <p className="text-rose-600">{error}</p>}
      {k && (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
            <Kpi label="Active listings" value={k.active_listings} sub={`${k.qty0_listings} at qty 0`} />
            <Kpi label="Posted today" value={k.listings_posted_today} sub={`${k.listings_posted_period} this period${k.dry_run_previews_today ? ` · ${k.dry_run_previews_today} dry-run today` : ""}`} />
            <Kpi label="Orders" value={k.orders} sub={`${k.units_sold} units`} />
            <Kpi label="Revenue (incl. buyer tax)" value={money(k.revenue)} sub={`buyer tax ${money(k.buyer_tax)}`} />
            <Kpi label="Amazon spend (incl. tax)" value={money(k.amazon_spend)} sub={k.amazon_refunds ? `after ${money(k.amazon_refunds)} Amazon refunds` : null} />
            <Kpi label="eBay fees" value={money(k.ebay_fees)} sub={`promo ${money(k.promo_fees)}`} />
            <Kpi label="Refunds to buyers" value={money(k.refunds)} />
            <Kpi label="Net profit" value={money(k.net_profit)} tone={k.net_profit >= 0 ? "good" : "bad"}
              sub={k.orders_with_estimates ? `${k.orders_with_estimates} order(s) use estimates` : "all actual numbers"} />
            <Kpi label="Profit margin" value={pct(k.profit_margin_pct)} sub="of sales excl. buyer tax" />
            <Kpi label="ROI" value={pct(k.roi_pct)} sub="profit ÷ Amazon spend" />
            <Kpi label="Avg profit / order" value={money(k.avg_profit_per_order)} />
            <Kpi label="Sell-through" value={pct(k.sell_through_pct)} sub="listings sold ÷ active" />
          </div>
          <p className="text-xs text-slate-500">
            Net profit = revenue − buyer tax (eBay remits it) − Amazon spend − eBay fees − promo fees − refunds. Fees are actual
            from eBay's Finances API once available; until then they're formula estimates.
          </p>
          <div className="grid gap-4 lg:grid-cols-2">
            <Card title="Revenue & profit">
              <ResponsiveContainer width="100%" height={240}>
                <LineChart data={data.series}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                  <XAxis dataKey="date" fontSize={11} />
                  <YAxis fontSize={11} />
                  <Tooltip formatter={(v) => money(v)} />
                  <Legend />
                  <Line type="monotone" dataKey="revenue" stroke="#6366f1" dot={false} />
                  <Line type="monotone" dataKey="profit" stroke="#10b981" dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </Card>
            <Card title="Orders per day">
              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={data.series}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                  <XAxis dataKey="date" fontSize={11} />
                  <YAxis allowDecimals={false} fontSize={11} />
                  <Tooltip />
                  <Bar dataKey="orders" fill="#0ea5e9" />
                </BarChart>
              </ResponsiveContainer>
            </Card>
            <Card title="Listings posted per day">
              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={data.series}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                  <XAxis dataKey="date" fontSize={11} />
                  <YAxis allowDecimals={false} fontSize={11} />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="listings" name="live" stackId="a" fill="#6366f1" />
                  <Bar dataKey="dry_run_listings" name="dry-run" stackId="a" fill="#f59e0b" />
                </BarChart>
              </ResponsiveContainer>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
