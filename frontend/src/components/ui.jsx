import { useCallback, useEffect, useRef, useState } from "react";

export const money = (v) =>
  v === null || v === undefined || Number.isNaN(v) ? "—" : `${v < 0 ? "-" : ""}$${Math.abs(v).toFixed(2)}`;
export const pct = (v) => (v === null || v === undefined ? "—" : `${v.toFixed(1)}%`);
export const when = (iso) => (iso ? new Date(iso).toLocaleString() : "—");
export const day = (iso) => (iso ? new Date(iso).toLocaleDateString() : "—");
export const clock = (iso) => (iso ? new Date(iso).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) : "—");

export function useLoad(fn, deps = [], intervalMs = 0) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const fnRef = useRef(fn);
  fnRef.current = fn;
  const reload = useCallback(async () => {
    try {
      setData(await fnRef.current());
      setError(null);
    } catch (e) {
      setError(e.message);
    }
  }, []);
  useEffect(() => {
    reload();
    if (!intervalMs) return undefined;
    const t = setInterval(reload, intervalMs);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return [data, reload, error, setData];
}

export function Card({ title, actions, children, className = "" }) {
  return (
    <section className={`rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900 ${className}`}>
      {(title || actions) && (
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          {title && <h2 className="text-base font-semibold">{title}</h2>}
          {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
        </div>
      )}
      {children}
    </section>
  );
}

export function Kpi({ label, value, sub, tone }) {
  const color = tone === "good" ? "text-emerald-600" : tone === "bad" ? "text-rose-600" : "";
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <div className="text-xs text-slate-500">{label}</div>
      <div className={`mt-1 text-xl font-semibold tabular-nums ${color}`}>{value}</div>
      {sub && <div className="mt-0.5 text-xs text-slate-500">{sub}</div>}
    </div>
  );
}

const BTN = {
  primary: "bg-indigo-600 text-white hover:bg-indigo-500",
  danger: "bg-rose-600 text-white hover:bg-rose-500",
  plain: "border border-slate-300 bg-white hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-900 dark:hover:bg-slate-800",
};

export function Button({ kind = "plain", busy, children, className = "", ...rest }) {
  return (
    <button
      className={`inline-flex items-center gap-1 rounded-md px-3 py-1.5 text-sm font-medium disabled:opacity-50 ${BTN[kind]} ${className}`}
      disabled={busy || rest.disabled}
      {...rest}
    >
      {busy ? "…" : children}
    </button>
  );
}

/** Button that runs an async action and shows its result/error. */
export function ActionButton({ action, onDone, confirm: confirmText, children, ...rest }) {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  return (
    <span className="inline-flex items-center gap-2">
      <Button
        busy={busy}
        onClick={async () => {
          if (confirmText && !window.confirm(confirmText)) return;
          setBusy(true);
          setMsg(null);
          try {
            const r = await action();
            if (r && r.message) setMsg({ ok: true, text: r.message });
            onDone && onDone(r);
          } catch (e) {
            setMsg({ ok: false, text: e.message });
          } finally {
            setBusy(false);
          }
        }}
        {...rest}
      >
        {children}
      </Button>
      {msg && <span className={`text-xs ${msg.ok ? "text-slate-500" : "text-rose-600"}`}>{msg.text}</span>}
    </span>
  );
}

const BADGE = {
  green: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300",
  yellow: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  red: "bg-rose-100 text-rose-800 dark:bg-rose-900/40 dark:text-rose-300",
  blue: "bg-sky-100 text-sky-800 dark:bg-sky-900/40 dark:text-sky-300",
  gray: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
  purple: "bg-violet-100 text-violet-800 dark:bg-violet-900/40 dark:text-violet-300",
};

export function Badge({ color = "gray", children }) {
  return <span className={`inline-block whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ${BADGE[color]}`}>{children}</span>;
}

const STATUS_COLORS = {
  active: "green", qty0: "yellow", ended: "gray", queued: "gray", scheduled: "blue", posting: "blue", posted: "green",
  failed: "red", skipped: "yellow", removed: "gray", expired: "gray", awaiting_purchase: "yellow", purchased: "blue",
  shipped: "blue", tracking_uploaded: "purple", delivered: "green", cancelled: "gray", returned: "red", refunded: "red",
};
const STATUS_LABELS = {
  qty0: "qty 0", awaiting_purchase: "Needs purchase", purchased: "Purchased on Amazon", shipped: "Shipped",
  tracking_uploaded: "Tracking uploaded", delivered: "Delivered", cancelled: "Cancelled", returned: "Returned",
  refunded: "Refunded",
};
export function StatusBadge({ status }) {
  return <Badge color={STATUS_COLORS[status] || "gray"}>{STATUS_LABELS[status] || status}</Badge>;
}

export function CopyButton({ text, label = "Copy" }) {
  const [done, setDone] = useState(false);
  return (
    <button
      className="rounded border border-slate-300 px-1.5 py-0.5 text-xs hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text || "");
        } catch {
          const ta = document.createElement("textarea");
          ta.value = text || "";
          document.body.appendChild(ta);
          ta.select();
          document.execCommand("copy");
          ta.remove();
        }
        setDone(true);
        setTimeout(() => setDone(false), 1200);
      }}
    >
      {done ? "Copied" : label}
    </button>
  );
}

export function Modal({ open, onClose, title, children, wide }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-4" onClick={onClose}>
      <div
        className={`mt-8 w-full ${wide ? "max-w-4xl" : "max-w-xl"} rounded-xl bg-white p-5 shadow-xl dark:bg-slate-900`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-lg font-semibold">{title}</h3>
          <button className="text-slate-500 hover:text-slate-800" onClick={onClose}>✕</button>
        </div>
        {children}
      </div>
    </div>
  );
}

/** Sortable table. columns: [{key, label, render?, sort? (value fn), className?}] */
export function Table({ columns, rows, onRowClick, empty = "Nothing here yet.", initialSort }) {
  const [sort, setSort] = useState(initialSort || null);
  const sorted = [...(rows || [])];
  if (sort) {
    const col = columns.find((c) => c.key === sort.key);
    const val = col?.sort || ((r) => r[sort.key]);
    sorted.sort((a, b) => {
      const x = val(a), y = val(b);
      if (x === y) return 0;
      if (x === null || x === undefined) return 1;
      if (y === null || y === undefined) return -1;
      return (x > y ? 1 : -1) * (sort.dir === "asc" ? 1 : -1);
    });
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="border-b border-slate-200 text-xs text-slate-500 dark:border-slate-800">
          <tr>
            {columns.map((c) => (
              <th
                key={c.key}
                className={`cursor-pointer select-none px-2 py-2 ${c.className || ""}`}
                onClick={() => setSort((s) => ({ key: c.key, dir: s?.key === c.key && s.dir === "desc" ? "asc" : "desc" }))}
              >
                {c.label}
                {sort?.key === c.key ? (sort.dir === "asc" ? " ▲" : " ▼") : ""}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.length === 0 && (
            <tr>
              <td colSpan={columns.length} className="px-2 py-6 text-center text-slate-500">{empty}</td>
            </tr>
          )}
          {sorted.map((r, i) => (
            <tr
              key={r.id ?? i}
              className={`border-b border-slate-100 dark:border-slate-800/60 ${onRowClick ? "cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/40" : ""}`}
              onClick={onRowClick ? () => onRowClick(r) : undefined}
            >
              {columns.map((c) => (
                <td key={c.key} className={`px-2 py-2 align-top ${c.className || ""}`}>
                  {c.render ? c.render(r) : r[c.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Breakdown({ b }) {
  if (!b) return <p className="text-sm text-slate-500">No price breakdown.</p>;
  const rows = [
    ["Amazon price", money(b.amazon_price)],
    [`+ Amazon sales tax (${b.sales_tax_percent}%)`, money(b.amazon_sales_tax)],
    ["= Amazon cost", money(b.amazon_cost), true],
    [`× margin multiplier (${b.margin_multiplier})`, money(b.after_margin)],
    [`× (1 + eBay fee ${b.ebay_fee_percent}%)`, money(b.after_ebay_fee_gross_up)],
    [`× (1 + promo ${b.promo_rate_percent}%)`, money(b.after_promo_gross_up)],
    [`+ fixed fee per order`, money(b.ebay_fee_fixed_per_order)],
    ["= raw price", `$${b.raw_price.toFixed(4)}`],
    [`rounding (${b.rounding_mode === "next_dollar_99" ? "next dollar .99" : "nearest .99 above"})`, `+${money(b.rounding_added)}`],
    ["= eBay price", money(b.ebay_price), true],
    [`eBay fees: (${money(b.ebay_price)} × (1 + ${b.buyer_tax_estimate}% buyer tax)) × ${b.ebay_fee_percent}% + fixed`, `-${money(b.ebay_fees)}`],
    [`Promoted Listings fee (${b.promo_rate_percent}%)`, `-${money(b.promo_fee)}`],
    ["Amazon cost", `-${money(b.amazon_cost)}`],
    ["= Expected profit", `${money(b.profit)} (${pct(b.profit_percent)} of cost)`, true],
  ];
  return (
    <div>
      <table className="w-full text-sm">
        <tbody>
          {rows.map(([k, v, bold], i) => (
            <tr key={i} className={bold ? "font-semibold" : ""}>
              <td className="py-0.5 pr-4 text-slate-600 dark:text-slate-400">{k}</td>
              <td className="py-0.5 text-right tabular-nums">{v}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="mt-2">
        {b.passes_floor ? (
          <Badge color="green">Passes profit floor</Badge>
        ) : (
          <Badge color="red">Below floor: {b.floor_reasons.join("; ")}</Badge>
        )}
      </div>
    </div>
  );
}
