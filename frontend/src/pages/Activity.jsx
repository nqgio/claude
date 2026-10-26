import { AlertCircle, AlertTriangle, ChevronLeft, ChevronRight, Info, ScrollText, Search } from "lucide-react";
import { useState } from "react";
import { api } from "../api";
import { Badge, Button, Card, EmptyState, PageHeader, Skeleton, cx, useLoad } from "../components/ui";

const LEVEL = {
  info: { icon: Info, cls: "text-ink-3" },
  warning: { icon: AlertTriangle, cls: "text-amber-500" },
  error: { icon: AlertCircle, cls: "text-rose-500" },
};
const PAGE = 100;

function stamp(iso) {
  const d = new Date(iso);
  return {
    date: d.toLocaleDateString([], { month: "short", day: "numeric" }),
    time: d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit", second: "2-digit" }),
  };
}

export default function Activity() {
  const [category, setCategory] = useState("");
  const [level, setLevel] = useState("");
  const [q, setQ] = useState("");
  const [offset, setOffset] = useState(0);
  const qs = new URLSearchParams({ limit: PAGE, offset, ...(category && { category }), ...(level && { level }), ...(q && { q }) });
  const [d] = useLoad(() => api.get(`/activity?${qs}`), [qs.toString()], 10000);
  const reset = (fn) => (e) => {
    fn(e.target.value);
    setOffset(0);
  };
  return (
    <>
      <PageHeader title="Activity log" description="Everything the app does: products found and skipped (with reasons), listings, price changes, orders and errors." />
      <Card padded={false}>
        <div className="flex flex-wrap items-center gap-3 border-b border-line px-4 py-3">
          <div className="relative w-full max-w-xs">
            <Search className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-ink-3" />
            <input placeholder="Search messages" value={q} onChange={reset(setQ)} className="w-full !pl-9" />
          </div>
          <select value={category} onChange={reset(setCategory)} className="w-44">
            <option value="">All categories</option>
            {(d?.categories || []).map((c) => <option key={c} value={c}>{c[0].toUpperCase() + c.slice(1)}</option>)}
          </select>
          <select value={level} onChange={reset(setLevel)} className="w-36">
            <option value="">All levels</option><option value="info">Info</option><option value="warning">Warnings</option><option value="error">Errors</option>
          </select>
          {d && <span className="ml-auto text-xs text-ink-3">{d.total.toLocaleString()} entries</span>}
        </div>
        {!d ? (
          <div className="space-y-3 p-4">{[0, 1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-5" />)}</div>
        ) : d.items.length === 0 ? (
          <EmptyState icon={ScrollText} title="No matching activity" />
        ) : (
          <ul className="divide-y divide-line">
            {d.items.map((r) => {
              const L = LEVEL[r.level] || LEVEL.info;
              const t = stamp(r.ts);
              return (
                <li key={r.id} className={cx("flex gap-3 px-4 py-3 hover:bg-surface-2", r.level === "error" && "bg-rose-50/40 dark:bg-rose-500/[0.04]")}>
                  <L.icon className={cx("mt-0.5 h-4 w-4 shrink-0", L.cls)} />
                  <div className="min-w-0 flex-1">
                    <p className="text-[13px] leading-5 break-words text-ink">{r.message}</p>
                    {r.details?.traceback && (
                      <details className="mt-1 text-xs text-ink-3">
                        <summary className="cursor-pointer hover:text-ink-2">Technical details</summary>
                        <pre className="mt-2 overflow-x-auto rounded-lg bg-surface-3 p-3 font-mono text-[11px] whitespace-pre-wrap">{r.details.traceback}</pre>
                      </details>
                    )}
                  </div>
                  <div className="flex shrink-0 flex-col items-end gap-1">
                    <Badge>{r.category}</Badge>
                    <span className="tnum text-[11px] whitespace-nowrap text-ink-3">{t.date} · {t.time}</span>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
        <div className="flex items-center justify-between border-t border-line px-4 py-3">
          <span className="text-xs text-ink-3">{d && d.total ? `${offset + 1}–${Math.min(offset + PAGE, d.total)} of ${d.total.toLocaleString()}` : ""}</span>
          <div className="flex gap-2">
            <Button size="sm" icon={ChevronLeft} disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>Newer</Button>
            <Button size="sm" disabled={!d || offset + PAGE >= d.total} onClick={() => setOffset(offset + PAGE)}>
              Older <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </Card>
    </>
  );
}
