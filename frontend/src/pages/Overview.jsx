import {
  ArrowRightLeft, BadgeDollarSign, Boxes, CalendarDays, CircleDollarSign, Gauge, Package, PackageCheck, Percent, Receipt,
  RotateCcw, ShoppingCart, TrendingUp, Undo2,
} from "lucide-react";
import { useState } from "react";
import { Area, Bar, BarChart, ComposedChart, Line, ResponsiveContainer } from "recharts";
import { api } from "../api";
import { ChartTooltip, LegendRow, SERIES, axes } from "../components/charts";
import { Card, Kpi, PageHeader, Segmented, Skeleton, money, pct, useLoad } from "../components/ui";

const RANGES = [["today", "Today"], ["7d", "7D"], ["30d", "30D"], ["90d", "90D"], ["all", "All"], ["custom", "Custom"]];

export default function Overview() {
  const [range, setRange] = useState("30d");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const qs = range === "custom" ? `range=custom&start=${start}&end=${end}` : `range=${range}`;
  const [data, , error] = useLoad(() => (range === "custom" && !start ? Promise.resolve(null) : api.get(`/metrics?${qs}`)), [qs], 60000);
  const k = data?.kpis;
  const s = data?.series || [];

  return (
    <>
      <PageHeader
        title="Overview"
        description="How your store is selling, what it costs, and what you keep."
        actions={
          <>
            {range === "custom" && (
              <div className="flex items-center gap-2">
                <input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
                <span className="text-ink-3">–</span>
                <input type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
              </div>
            )}
            <Segmented value={range} onChange={setRange} options={RANGES} />
          </>
        }
      />
      {error && <p className="mb-4 text-rose-600">{error}</p>}

      {!k ? (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-[108px] rounded-xl" />)}
        </div>
      ) : (
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
            <Kpi label="Net profit" icon={TrendingUp} accent={k.net_profit >= 0 ? "emerald" : "rose"} value={money(k.net_profit)}
              tone={k.net_profit > 0 ? "good" : k.net_profit < 0 ? "bad" : undefined}
              sub={k.orders_with_estimates ? `${k.orders_with_estimates} order(s) still estimated` : "All actual numbers"} />
            <Kpi label="Revenue" icon={CircleDollarSign} accent="indigo" value={money(k.revenue)} sub={`Includes ${money(k.buyer_tax)} buyer tax`} />
            <Kpi label="Orders" icon={ShoppingCart} accent="sky" value={k.orders} sub={`${k.units_sold} units sold`} />
            <Kpi label="Active listings" icon={Package} accent="slate" value={k.active_listings} sub={`${k.qty0_listings} at qty 0`} />
          </div>

          <div className="grid gap-4 xl:grid-cols-3">
            <Card title="Revenue & profit" description="Daily, for the selected range" className="xl:col-span-2"
              actions={<LegendRow items={[["Revenue", SERIES[0]], ["Profit", SERIES[1]]]} />}>
              <div className="h-[260px]">
                <ResponsiveContainer>
                  <ComposedChart data={s} margin={{ top: 6, right: 6, left: -6, bottom: 0 }}>
                    <defs>
                      <linearGradient id="revFill" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="var(--series-1)" stopOpacity={0.18} />
                        <stop offset="100%" stopColor="var(--series-1)" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    {axes({ currency: true })}
                    <ChartTooltip currency />
                    <Area type="monotone" dataKey="revenue" name="Revenue" stroke={SERIES[0]} strokeWidth={2} fill="url(#revFill)"
                      activeDot={{ r: 4, strokeWidth: 2, stroke: "var(--c-surface)" }} />
                    <Line type="monotone" dataKey="profit" name="Profit" stroke={SERIES[1]} strokeWidth={2} dot={false}
                      activeDot={{ r: 4, strokeWidth: 2, stroke: "var(--c-surface)" }} />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            </Card>
            <Card title="Profit breakdown" description="Where the money went">
              <Waterfall k={k} />
            </Card>
          </div>

          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <Kpi label="Profit margin" icon={Percent} value={pct(k.profit_margin_pct)} sub="Of sales excl. buyer tax" />
            <Kpi label="ROI" icon={Gauge} value={pct(k.roi_pct)} sub="Profit ÷ Amazon spend" />
            <Kpi label="Avg profit / order" icon={BadgeDollarSign} value={money(k.avg_profit_per_order)} />
            <Kpi label="Sell-through" icon={PackageCheck} value={pct(k.sell_through_pct)} sub="Listings sold ÷ active" />
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card title="Orders per day">
              <div className="h-[220px]">
                <ResponsiveContainer>
                  <BarChart data={s} margin={{ top: 6, right: 6, left: -12, bottom: 0 }} barCategoryGap="30%">
                    {axes()}
                    <ChartTooltip cursor="bar" />
                    <Bar dataKey="orders" name="Orders" fill={SERIES[0]} radius={[4, 4, 0, 0]} maxBarSize={28} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>
            <Card title="Listings posted per day" actions={<LegendRow items={[["Live", SERIES[0]], ["Dry run", SERIES[1]]]} />}>
              <div className="h-[220px]">
                <ResponsiveContainer>
                  <BarChart data={s} margin={{ top: 6, right: 6, left: -12, bottom: 0 }} barCategoryGap="30%">
                    {axes()}
                    <ChartTooltip cursor="bar" />
                    <Bar dataKey="listings" name="Live" stackId="a" fill={SERIES[0]} maxBarSize={28} stroke="var(--c-surface)" strokeWidth={2} />
                    <Bar dataKey="dry_run_listings" name="Dry run" stackId="a" fill={SERIES[1]} radius={[4, 4, 0, 0]} maxBarSize={28}
                      stroke="var(--c-surface)" strokeWidth={2} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>
          </div>

          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <Kpi label="Posted today" icon={CalendarDays} value={k.listings_posted_today}
              sub={`${k.listings_posted_period} this period${k.dry_run_previews_today ? ` · ${k.dry_run_previews_today} dry-run` : ""}`} />
            <Kpi label="Amazon spend" icon={Boxes} value={money(k.amazon_spend)}
              sub={k.amazon_refunds ? `After ${money(k.amazon_refunds)} refunds` : "Incl. sales tax"} />
            <Kpi label="eBay + promo fees" icon={Receipt} value={money(k.ebay_fees + k.promo_fees)} sub={`Promo ${money(k.promo_fees)}`} />
            <Kpi label="Refunds to buyers" icon={Undo2} value={money(k.refunds)} />
          </div>
        </div>
      )}
    </>
  );
}

function Waterfall({ k }) {
  const rows = [
    ["Revenue", k.revenue, ArrowRightLeft],
    ["Buyer tax (eBay remits)", -k.buyer_tax, Receipt],
    ["Amazon spend", -k.amazon_spend, Boxes],
    ["eBay fees", -k.ebay_fees, Receipt],
    ["Promoted Listings", -k.promo_fees, Receipt],
    ["Refunds", -k.refunds, RotateCcw],
  ];
  const max = Math.max(1, Math.abs(k.revenue));
  return (
    <div className="space-y-3">
      {rows.map(([label, v]) => (
        <div key={label}>
          <div className="mb-1 flex items-baseline justify-between text-[12.5px]">
            <span className="text-ink-2">{label}</span>
            <span className="tnum font-medium">{money(v)}</span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-surface-3">
            <div className="h-full rounded-full" style={{ width: `${Math.min(100, (Math.abs(v) / max) * 100)}%`, background: v >= 0 ? "var(--series-1)" : "var(--chart-axis)" }} />
          </div>
        </div>
      ))}
      <div className="flex items-baseline justify-between border-t border-line pt-3">
        <span className="text-[13px] font-semibold">Net profit</span>
        <span className={`tnum text-[15px] font-semibold ${k.net_profit < 0 ? "text-rose-600 dark:text-rose-400" : "text-emerald-600 dark:text-emerald-400"}`}>
          {money(k.net_profit)}
        </span>
      </div>
    </div>
  );
}
