import { ArrowLeft, ExternalLink, Flag, LineChart as LineIcon, RefreshCw, ShoppingBag, Tag, Trash2 } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { Line, LineChart, ResponsiveContainer } from "recharts";
import { api } from "../api";
import { ChartTooltip, LegendRow, SERIES, axes } from "../components/charts";
import {
  ActionButton, Badge, Breakdown, Card, EmptyState, Skeleton, Stat, StatusBadge, Table, Thumb, ago, money, when, useLoad,
} from "../components/ui";

export default function ListingDetail() {
  const { id } = useParams();
  const [l, reload, error] = useLoad(() => api.get(`/listings/${id}`), [id]);
  if (error) return <p className="text-rose-600">{error}</p>;
  if (!l)
    return (
      <div className="space-y-4">
        <Skeleton className="h-36 rounded-xl" />
        <Skeleton className="h-80 rounded-xl" />
      </div>
    );
  const history = l.history.map((h) => ({ ...h, date: h.ts.slice(0, 10) }));
  const linkBtn = "inline-flex h-9 items-center gap-2 rounded-lg border border-line bg-surface px-3.5 text-[13px] font-medium shadow-xs hover:bg-surface-3";
  return (
    <div className="space-y-6">
      <Link to="/listings" className="inline-flex items-center gap-1.5 text-[13px] font-medium text-ink-2 hover:text-ink">
        <ArrowLeft className="h-4 w-4" /> Listings
      </Link>

      <div className="card p-5">
        <div className="flex flex-col gap-5 md:flex-row md:items-start">
          <Thumb src={(l.image_urls || [])[0]} size="h-24 w-24" />
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge status={l.status} />
              {l.dry_run && <Badge color="yellow">Dry-run preview</Badge>}
              <Badge color={l.environment === "sandbox" ? "blue" : "indigo"}>{l.environment}</Badge>
              {l.ad_id && <Badge color="purple">Promoted</Badge>}
            </div>
            <h1 className="mt-2 text-lg font-semibold tracking-tight">{l.title}</h1>
            {l.flagged && (
              <p className="mt-2 inline-flex items-center gap-1.5 rounded-lg bg-rose-50 px-2.5 py-1.5 text-[12.5px] text-rose-700 dark:bg-rose-500/10 dark:text-rose-300">
                <Flag className="h-3.5 w-3.5" /> {l.flag_reason}
              </p>
            )}
            {l.status_reason && <p className="mt-1 text-[12.5px] text-ink-3">{l.status_reason}</p>}
          </div>
          <div className="flex flex-wrap gap-2">
            <a className={linkBtn} href={l.amazon_url} target="_blank" rel="noreferrer"><ExternalLink className="h-4 w-4" /> Amazon</a>
            {l.ebay_url && <a className={linkBtn} href={l.ebay_url} target="_blank" rel="noreferrer"><ExternalLink className="h-4 w-4" /> eBay</a>}
            <ActionButton icon={RefreshCw} action={() => api.post(`/listings/${id}/refresh`)} onDone={() => setTimeout(reload, 4000)} success="Refresh started">
              Refresh
            </ActionButton>
            {l.flagged && <ActionButton action={() => api.post(`/listings/${id}/unflag`)} onDone={reload} success="Flag cleared">Clear flag</ActionButton>}
            {l.status !== "ended" && (
              <ActionButton kind="danger-soft" icon={Trash2} confirm="End this listing on eBay?" action={() => api.post(`/listings/${id}/end`)} onDone={reload}>
                End
              </ActionButton>
            )}
          </div>
        </div>
        <div className="mt-5 grid grid-cols-2 gap-x-6 gap-y-4 border-t border-line pt-5 sm:grid-cols-3 lg:grid-cols-6">
          <Stat label="eBay price"><span className="tnum text-base font-semibold">{money(l.price)}</span> <span className="text-ink-3">× {l.quantity}</span></Stat>
          <Stat label="Amazon now">
            <span className="tnum">{money(l.current_amazon_price)}</span>{" "}
            {l.current_in_stock === false && <Badge color="red">Out of stock</Badge>}
          </Stat>
          <Stat label="Cost at listing"><span className="tnum">{money(l.cost_at_listing)}</span></Stat>
          <Stat label="Expected profit">
            <span className={`tnum font-semibold ${l.expected_profit < 0 ? "text-rose-600" : "text-emerald-600 dark:text-emerald-400"}`}>{money(l.expected_profit)}</span>
          </Stat>
          <Stat label="Traffic">{l.views} views · {l.watchers} watching</Stat>
          <Stat label="Refreshed">{ago(l.last_refreshed)}</Stat>
          <Stat label="ASIN"><span className="font-mono">{l.asin}</span></Stat>
          <Stat label="SKU"><span className="font-mono">{l.sku}</span></Stat>
          <Stat label="eBay item">{l.ebay_listing_id || "—"}</Stat>
          <Stat label="Category"><span title={l.ebay_category_name}>{l.ebay_category_name || "—"}</span></Stat>
          <Stat label="Listed">{when(l.created_at)}</Stat>
          <Stat label="Impressions">{l.impressions}</Stat>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Current price breakdown" icon={Tag}><Breakdown b={l.current_breakdown || l.breakdown} /></Card>
        <Card title="Price history" icon={LineIcon}
          actions={history.length >= 2 && <LegendRow items={[["Amazon", SERIES[2]], ["eBay", SERIES[0]], ["Profit", SERIES[1]]]} />}>
          {history.length < 2 ? (
            <EmptyState icon={LineIcon} title="No history yet" text="A point is added every time the refresh checks this listing." />
          ) : (
            <div className="h-[300px]">
              <ResponsiveContainer>
                <LineChart data={history} margin={{ top: 6, right: 6, left: -6, bottom: 0 }}>
                  {axes({ currency: true })}
                  <ChartTooltip currency />
                  <Line type="stepAfter" dataKey="amazon_price" name="Amazon" stroke={SERIES[2]} strokeWidth={2} dot={false} />
                  <Line type="stepAfter" dataKey="ebay_price" name="eBay" stroke={SERIES[0]} strokeWidth={2} dot={false} />
                  <Line type="stepAfter" dataKey="expected_profit" name="Profit" stroke={SERIES[1]} strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </Card>
      </div>

      <Card title="Orders" icon={ShoppingBag} padded={false}>
        <Table
          rows={l.orders}
          empty={<EmptyState icon={ShoppingBag} title="No orders yet" />}
          columns={[
            { key: "created_at", label: "Date", render: (o) => when(o.created_at) },
            { key: "ebay_order_id", label: "eBay order", render: (o) => <span className="font-mono text-xs">{o.ebay_order_id}</span> },
            { key: "quantity", label: "Qty", align: "right" },
            { key: "revenue_total", label: "Revenue", align: "right", render: (o) => money(o.revenue_total) },
            { key: "profit", label: "Profit", align: "right", render: (o) => money(o.financials.profit) },
            { key: "status", label: "Status", render: (o) => <StatusBadge status={o.status} /> },
          ]}
        />
      </Card>

      <div className="grid gap-6 lg:grid-cols-5">
        <Card title="Price breakdown at listing time" className="lg:col-span-2"><Breakdown b={l.breakdown} /></Card>
        <Card title="Description preview" className="lg:col-span-3">
          <div className="mb-4 flex flex-wrap gap-1.5">
            {Object.entries(l.aspects || {}).map(([k, v]) => (
              <Badge key={k} color="gray"><span className="text-ink-3">{k}</span> {v.join(", ")}</Badge>
            ))}
          </div>
          <iframe title="description" sandbox="" className="h-[420px] w-full rounded-lg border border-line bg-white" srcDoc={l.description_html} />
        </Card>
      </div>
    </div>
  );
}
