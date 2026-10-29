import { CircleCheck, Flag, Package, RefreshCw, Search } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { ActionButton, Badge, Card, EmptyState, PageHeader, Segmented, StatusBadge, Switch, Table, Thumb, ago, cx, money, useLoad } from "../components/ui";

export default function Listings() {
  const nav = useNavigate();
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const [showDry, setShowDry] = useState(true);
  const [rows, reload] = useLoad(
    () => api.get(`/listings?include_dry_run=${showDry}${status ? `&status=${status}` : ""}${q ? `&q=${encodeURIComponent(q)}` : ""}`),
    [status, q, showDry],
    60000
  );
  const profitCls = (v) => (v == null ? "" : v < 0 ? "text-rose-600 dark:text-rose-400" : "text-emerald-600 dark:text-emerald-400");
  const cols = [
    {
      key: "title", label: "Listing", className: "min-w-[320px]",
      render: (r) => (
        <div className="flex items-center gap-3">
          <Thumb src={r.image} />
          <div className="min-w-0">
            <div className="line-clamp-1 font-medium text-ink">{r.title}</div>
            <div className="mt-0.5 flex flex-wrap items-center gap-1.5 text-xs text-ink-3">
              <span className="font-mono">{r.asin}</span>
              {r.dry_run && <Badge color="yellow">Dry run</Badge>}
              {r.environment === "sandbox" && !r.dry_run && <Badge color="blue">Sandbox</Badge>}
              {r.flagged && (
                <span className="inline-flex items-center gap-1 text-rose-600 dark:text-rose-400" title={r.flag_reason}>
                  <Flag className="h-3 w-3" /> flagged
                </span>
              )}
            </div>
          </div>
        </div>
      ),
    },
    { key: "price", label: "eBay", align: "right", render: (r) => <span className="font-medium">{money(r.price)}</span> },
    { key: "current_amazon_price", label: "Amazon", align: "right", render: (r) => money(r.current_amazon_price) },
    { key: "expected_profit", label: "Exp. profit", align: "right", render: (r) => <span className={profitCls(r.expected_profit)}>{money(r.expected_profit)}</span> },
    { key: "status", label: "Status", render: (r) => <StatusBadge status={r.status} /> },
    { key: "views", label: "Views", align: "right" },
    { key: "watchers", label: "Watch", align: "right" },
    { key: "sold_units", label: "Sold", align: "right" },
    { key: "sold_profit", label: "Profit", align: "right", render: (r) => <span className={cx(r.sold_units ? profitCls(r.sold_profit) : "text-ink-3")}>{money(r.sold_profit)}</span> },
    { key: "last_refreshed", label: "Refreshed", render: (r) => <span className="text-xs whitespace-nowrap text-ink-3">{ago(r.last_refreshed)}</span> },
  ];
  return (
    <>
      <PageHeader
        title="Listings"
        description="Everything the app has listed, with live Amazon prices and results."
        actions={
          <>
            <ActionButton icon={CircleCheck} action={() => api.post("/jobs/listing_status/run")} onDone={() => setTimeout(reload, 5000)}
              success="Checking eBay: listings you ended there will show as Ended here. (This also runs every hour.)">
              Check eBay now
            </ActionButton>
            <ActionButton kind="primary" icon={RefreshCw} action={() => api.post("/refresh/run")} success="Refresh started. Prices update as each listing is checked.">
              Refresh now
            </ActionButton>
          </>
        }
      />
      <Card padded={false}>
        <div className="flex flex-wrap items-center gap-3 border-b border-line px-4 py-3">
          <div className="relative w-full max-w-xs">
            <Search className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-ink-3" />
            <input placeholder="Search title or ASIN" value={q} onChange={(e) => setQ(e.target.value)} className="w-full !pl-9" />
          </div>
          <Segmented value={status} onChange={setStatus} options={[["", "All"], ["active", "Active"], ["qty0", "Qty 0"], ["ended", "Ended"]]} />
          <label className="ml-auto flex items-center gap-2 text-[13px] text-ink-2">
            <Switch checked={showDry} onChange={setShowDry} label="Show dry-run previews" /> Show dry-run previews
          </label>
          {rows && <span className="text-xs text-ink-3">{rows.length} listing{rows.length === 1 ? "" : "s"}</span>}
        </div>
        <Table
          columns={cols}
          rows={rows}
          loading
          onRowClick={(r) => nav(`/listings/${r.id}`)}
          initialSort={{ key: "id", dir: "desc" }}
          empty={<EmptyState icon={Package} title="No listings yet" text="Listings appear here once the queue posts them (in dry-run mode they show as previews)." />}
        />
      </Card>
    </>
  );
}
