import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { ActionButton, Badge, Card, StatusBadge, Table, money, when, useLoad } from "../components/ui";

export default function Listings() {
  const nav = useNavigate();
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const [showDry, setShowDry] = useState(true);
  const [rows] = useLoad(
    () => api.get(`/listings?include_dry_run=${showDry}${status ? `&status=${status}` : ""}${q ? `&q=${encodeURIComponent(q)}` : ""}`),
    [status, q, showDry],
    60000
  );
  const cols = [
    { key: "image", label: "", render: (r) => (r.image ? <img src={r.image} alt="" className="h-10 w-10 rounded object-cover" /> : null) },
    {
      key: "title", label: "Title", className: "max-w-sm",
      render: (r) => (
        <div>
          <div className="line-clamp-2">{r.title}</div>
          <div className="text-xs text-slate-500">{r.asin}{r.flagged && <span className="ml-1 text-rose-600">⚑ {r.flag_reason}</span>}</div>
        </div>
      ),
    },
    { key: "price", label: "eBay price", render: (r) => money(r.price), className: "tabular-nums" },
    { key: "current_amazon_price", label: "Amazon now", render: (r) => money(r.current_amazon_price), className: "tabular-nums" },
    { key: "expected_profit", label: "Exp. profit", render: (r) => money(r.expected_profit), className: "tabular-nums" },
    {
      key: "status", label: "Status",
      render: (r) => (
        <div className="space-x-1">
          <StatusBadge status={r.status} />
          {r.dry_run && <Badge color="yellow">dry run</Badge>}
          {r.environment === "sandbox" && !r.dry_run && <Badge color="blue">sandbox</Badge>}
        </div>
      ),
    },
    { key: "views", label: "Views" },
    { key: "watchers", label: "Watchers" },
    { key: "sold_units", label: "Sold" },
    { key: "sold_profit", label: "Total profit", render: (r) => money(r.sold_profit), className: "tabular-nums" },
    { key: "last_refreshed", label: "Refreshed", render: (r) => <span className="text-xs">{when(r.last_refreshed)}</span> },
  ];
  return (
    <Card
      title={`Listings${rows ? ` (${rows.length})` : ""}`}
      actions={
        <>
          <input placeholder="Search title / ASIN" value={q} onChange={(e) => setQ(e.target.value)} />
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">All statuses</option>
            <option value="active">Active</option>
            <option value="qty0">Qty 0</option>
            <option value="ended">Ended</option>
          </select>
          <label className="flex items-center gap-1 text-sm">
            <input type="checkbox" checked={showDry} onChange={(e) => setShowDry(e.target.checked)} /> show dry-run
          </label>
          <ActionButton action={() => api.post("/refresh/run").then(() => ({ message: "Refresh started" }))}>Refresh now</ActionButton>
        </>
      }
    >
      <Table columns={cols} rows={rows} onRowClick={(r) => nav(`/listings/${r.id}`)} initialSort={{ key: "id", dir: "desc" }} />
    </Card>
  );
}
