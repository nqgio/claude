import { Link, useParams } from "react-router-dom";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";
import { ActionButton, Badge, Breakdown, Card, StatusBadge, Table, money, when, day, useLoad } from "../components/ui";

export default function ListingDetail() {
  const { id } = useParams();
  const [l, reload, error] = useLoad(() => api.get(`/listings/${id}`), [id]);
  if (error) return <p className="text-rose-600">{error}</p>;
  if (!l) return <p>Loading…</p>;
  const history = l.history.map((h) => ({ ...h, t: day(h.ts) }));
  return (
    <div className="space-y-4">
      <Link to="/listings" className="text-sm text-indigo-600">← Listings</Link>
      <Card
        title={l.title}
        actions={
          <>
            <a className="rounded-md border px-3 py-1.5 text-sm" href={l.amazon_url} target="_blank" rel="noreferrer">Amazon page</a>
            {l.ebay_url && <a className="rounded-md border px-3 py-1.5 text-sm" href={l.ebay_url} target="_blank" rel="noreferrer">eBay listing</a>}
            <ActionButton action={() => api.post(`/listings/${id}/refresh`)} onDone={() => setTimeout(reload, 4000)}>Refresh now</ActionButton>
            {l.flagged && <ActionButton action={() => api.post(`/listings/${id}/unflag`)} onDone={reload}>Clear flag</ActionButton>}
            {l.status !== "ended" && (
              <ActionButton kind="danger" confirm="End this listing on eBay?" action={() => api.post(`/listings/${id}/end`)} onDone={reload}>
                End listing
              </ActionButton>
            )}
          </>
        }
      >
        <div className="flex flex-wrap gap-2 text-sm">
          <StatusBadge status={l.status} />
          {l.dry_run && <Badge color="yellow">dry-run preview</Badge>}
          <Badge color="blue">{l.environment}</Badge>
          {l.flagged && <Badge color="red">⚑ {l.flag_reason}</Badge>}
          {l.status_reason && <span className="text-slate-500">{l.status_reason}</span>}
        </div>
        <div className="mt-3 grid gap-x-6 gap-y-1 text-sm sm:grid-cols-2 lg:grid-cols-4">
          <div>ASIN: <strong>{l.asin}</strong></div>
          <div>SKU: {l.sku}</div>
          <div>eBay item: {l.ebay_listing_id || "—"}</div>
          <div>Category: {l.ebay_category_name || "—"}</div>
          <div>eBay price: <strong>{money(l.price)}</strong> · qty {l.quantity}</div>
          <div>Amazon at listing: {money(l.amazon_price_at_listing)} (cost {money(l.cost_at_listing)})</div>
          <div>Amazon now: {money(l.current_amazon_price)} {l.current_in_stock === false && <Badge color="red">out of stock</Badge>}</div>
          <div>Views {l.views} · impressions {l.impressions} · watchers {l.watchers}</div>
          <div>Listed: {when(l.created_at)}</div>
          <div>Last refreshed: {when(l.last_refreshed)}</div>
          <div>Promoted: {l.ad_id ? `yes (campaign ${l.campaign_id})` : "no"}</div>
        </div>
      </Card>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Current price breakdown"><Breakdown b={l.current_breakdown || l.breakdown} /></Card>
        <Card title="Price history">
          {history.length < 2 ? (
            <p className="text-sm text-slate-500">History appears after the first refresh.</p>
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={history}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                <XAxis dataKey="t" fontSize={11} />
                <YAxis fontSize={11} />
                <Tooltip formatter={(v) => money(v)} />
                <Legend />
                <Line type="stepAfter" dataKey="amazon_price" name="Amazon" stroke="#f59e0b" dot={false} />
                <Line type="stepAfter" dataKey="ebay_price" name="eBay" stroke="#6366f1" dot={false} />
                <Line type="stepAfter" dataKey="expected_profit" name="Profit" stroke="#10b981" dot={false} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </Card>
      </div>
      <Card title="Price breakdown at listing time"><Breakdown b={l.breakdown} /></Card>
      <Card title="Orders for this listing">
        <Table
          rows={l.orders}
          columns={[
            { key: "created_at", label: "Date", render: (o) => when(o.created_at) },
            { key: "ebay_order_id", label: "eBay order" },
            { key: "quantity", label: "Qty" },
            { key: "revenue_total", label: "Revenue", render: (o) => money(o.revenue_total) },
            { key: "profit", label: "Profit", render: (o) => money(o.financials.profit) },
            { key: "status", label: "Status", render: (o) => <StatusBadge status={o.status} /> },
          ]}
        />
      </Card>
      <Card title="Item specifics & description">
        <div className="mb-3 flex flex-wrap gap-2 text-xs">
          {Object.entries(l.aspects || {}).map(([k, v]) => (
            <Badge key={k}>{k}: {v.join(", ")}</Badge>
          ))}
        </div>
        <iframe title="description" sandbox="" className="h-96 w-full rounded border bg-white" srcDoc={l.description_html} />
      </Card>
    </div>
  );
}
