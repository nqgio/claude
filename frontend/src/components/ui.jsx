import { Check, ChevronDown, ChevronUp, Copy, Image as ImageIcon, Inbox, Loader2, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useToast } from "./toast.jsx";

// ---- formatting ---------------------------------------------------------------------------------
export const money = (v) =>
  v === null || v === undefined || Number.isNaN(v)
    ? "—"
    : `${v < 0 ? "−" : ""}$${Math.abs(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
export const pct = (v) => (v === null || v === undefined ? "—" : `${v.toFixed(1)}%`);
export const when = (iso) =>
  iso ? new Date(iso).toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }) : "—";
export const day = (iso) => (iso ? new Date(iso).toLocaleDateString([], { month: "short", day: "numeric" }) : "—");
export const clock = (iso) => (iso ? new Date(iso).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) : "—");
export function ago(iso) {
  if (!iso) return "never";
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}
export const cx = (...c) => c.filter(Boolean).join(" ");

// ---- data loading ------------------------------------------------------------------------------
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

// ---- layout ------------------------------------------------------------------------------------------
export function PageHeader({ title, description, actions, children }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <h1 className="text-[22px] font-semibold tracking-tight text-ink">{title}</h1>
        {description && <p className="mt-1 text-[13px] text-ink-2">{description}</p>}
        {children}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Card({ title, description, actions, children, className = "", padded = true, icon: Icon }) {
  return (
    <section className={cx("card", className)}>
      {(title || actions) && (
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-3.5">
          <div className="flex min-w-0 items-center gap-2.5">
            {Icon && <Icon className="h-4 w-4 text-ink-3" />}
            <div className="min-w-0">
              {title && <h2 className="truncate text-[14px] font-semibold text-ink">{title}</h2>}
              {description && <p className="mt-0.5 text-xs text-ink-3">{description}</p>}
            </div>
          </div>
          {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
        </div>
      )}
      <div className={padded ? "p-5" : ""}>{children}</div>
    </section>
  );
}

export function Kpi({ label, value, sub, tone, icon: Icon, accent = "slate" }) {
  const toneCls = tone === "good" ? "text-emerald-600 dark:text-emerald-400" : tone === "bad" ? "text-rose-600 dark:text-rose-400" : "text-ink";
  const chip = {
    slate: "bg-surface-3 text-ink-2",
    indigo: "bg-indigo-50 text-indigo-600 dark:bg-indigo-500/10 dark:text-indigo-300",
    emerald: "bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-300",
    amber: "bg-amber-50 text-amber-600 dark:bg-amber-500/10 dark:text-amber-300",
    rose: "bg-rose-50 text-rose-600 dark:bg-rose-500/10 dark:text-rose-300",
    sky: "bg-sky-50 text-sky-600 dark:bg-sky-500/10 dark:text-sky-300",
  }[accent];
  return (
    <div className="card p-4">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[12px] font-medium text-ink-2">{label}</span>
        {Icon && (
          <span className={cx("grid h-7 w-7 place-items-center rounded-lg", chip)}>
            <Icon className="h-3.5 w-3.5" />
          </span>
        )}
      </div>
      <div className={cx("tnum mt-2 text-[24px] leading-8 font-semibold tracking-tight", toneCls)}>{value}</div>
      {sub && <div className="mt-0.5 truncate text-[12px] text-ink-3">{sub}</div>}
    </div>
  );
}

// ---- controls --------------------------------------------------------------------------------------------
const BTN = {
  primary: "bg-accent text-white shadow-xs hover:bg-accent-hover",
  secondary: "border border-line bg-surface text-ink shadow-xs hover:bg-surface-3",
  ghost: "text-ink-2 hover:bg-surface-3 hover:text-ink",
  danger: "bg-rose-600 text-white shadow-xs hover:bg-rose-500",
  "danger-soft": "border border-rose-200 bg-surface text-rose-600 hover:bg-rose-50 dark:border-rose-500/30 dark:text-rose-400 dark:hover:bg-rose-500/10",
};
const SIZE = { sm: "h-8 px-2.5 text-[12.5px] gap-1.5", md: "h-9 px-3.5 text-[13px] gap-2", lg: "h-10 px-4 text-sm gap-2" };

export function Button({ kind = "secondary", size = "md", busy, icon: Icon, children, className = "", ...rest }) {
  return (
    <button
      className={cx("inline-flex shrink-0 items-center justify-center rounded-lg font-medium whitespace-nowrap transition disabled:pointer-events-none disabled:opacity-50", BTN[kind], SIZE[size], className)}
      disabled={busy || rest.disabled}
      {...rest}
    >
      {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : Icon && <Icon className="h-4 w-4" />}
      {children}
    </button>
  );
}

/** Runs an async action; result message / error goes to a toast. */
export function ActionButton({ action, onDone, confirm: confirmText, success, children, ...rest }) {
  const [busy, setBusy] = useState(false);
  const toast = useToast();
  return (
    <Button
      busy={busy}
      onClick={async (e) => {
        e.stopPropagation();
        if (confirmText && !window.confirm(confirmText)) return;
        setBusy(true);
        try {
          const r = await action();
          const msg = (r && r.message) || success;
          if (msg) toast(msg, "success");
          onDone && onDone(r);
        } catch (err) {
          toast(err.message, "error");
        } finally {
          setBusy(false);
        }
      }}
      {...rest}
    >
      {children}
    </Button>
  );
}

export function Segmented({ value, onChange, options, size = "md" }) {
  return (
    <div className="inline-flex rounded-lg border border-line bg-surface-3 p-0.5">
      {options.map(([v, label, Icon]) => (
        <button
          key={v}
          onClick={() => onChange(v)}
          className={cx(
            "inline-flex items-center gap-1.5 rounded-md font-medium transition",
            size === "sm" ? "h-7 px-2 text-xs" : "h-8 px-3 text-[13px]",
            value === v ? "bg-surface text-ink shadow-xs ring-1 ring-line" : "text-ink-2 hover:text-ink"
          )}
          title={typeof label === "string" ? label : undefined}
        >
          {Icon && <Icon className="h-3.5 w-3.5" />}
          {label}
        </button>
      ))}
    </div>
  );
}

export function Switch({ checked, onChange, label, id }) {
  return (
    <button
      id={id}
      type="button"
      role="switch"
      aria-checked={!!checked}
      aria-label={label}
      onClick={() => onChange(!checked)}
      className={cx("relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition", checked ? "bg-accent" : "bg-line-strong")}
    >
      <span className={cx("inline-block h-4 w-4 rounded-full bg-white shadow transition", checked ? "translate-x-4.5" : "translate-x-0.5")} />
    </button>
  );
}

// ---- badges ------------------------------------------------------------------------------------------------
const BADGE = {
  green: "bg-emerald-50 text-emerald-700 ring-emerald-600/15 dark:bg-emerald-500/10 dark:text-emerald-300 dark:ring-emerald-400/20",
  yellow: "bg-amber-50 text-amber-800 ring-amber-600/20 dark:bg-amber-500/10 dark:text-amber-300 dark:ring-amber-400/20",
  red: "bg-rose-50 text-rose-700 ring-rose-600/15 dark:bg-rose-500/10 dark:text-rose-300 dark:ring-rose-400/20",
  blue: "bg-sky-50 text-sky-700 ring-sky-600/15 dark:bg-sky-500/10 dark:text-sky-300 dark:ring-sky-400/20",
  gray: "bg-surface-3 text-ink-2 ring-line-strong/60",
  purple: "bg-violet-50 text-violet-700 ring-violet-600/15 dark:bg-violet-500/10 dark:text-violet-300 dark:ring-violet-400/20",
  indigo: "bg-accent-soft text-accent-ink ring-accent/20",
};
const DOT = { green: "bg-emerald-500", yellow: "bg-amber-500", red: "bg-rose-500", blue: "bg-sky-500", gray: "bg-ink-3", purple: "bg-violet-500", indigo: "bg-accent" };

export function Badge({ color = "gray", dot, children, className = "" }) {
  return (
    <span className={cx("inline-flex items-center gap-1.5 rounded-md px-1.5 py-0.5 text-[11.5px] font-medium whitespace-nowrap ring-1 ring-inset", BADGE[color], className)}>
      {dot && <span className={cx("h-1.5 w-1.5 rounded-full", DOT[color])} />}
      {children}
    </span>
  );
}

const STATUS = {
  active: ["green", "Active"], qty0: ["yellow", "Qty 0"], ended: ["gray", "Ended"], queued: ["gray", "Queued"],
  scheduled: ["blue", "Scheduled"], posting: ["blue", "Posting"], posted: ["green", "Posted"], failed: ["red", "Failed"],
  skipped: ["yellow", "Skipped"], removed: ["gray", "Removed"], expired: ["gray", "Expired"],
  awaiting_purchase: ["yellow", "Needs purchase"], purchased: ["blue", "Purchased"], shipped: ["blue", "Shipped"],
  tracking_uploaded: ["purple", "Tracking uploaded"], delivered: ["green", "Delivered"], cancelled: ["gray", "Cancelled"],
  returned: ["red", "Returned"], refunded: ["red", "Refunded"],
};
export const statusLabel = (s) => (STATUS[s] || [null, s])[1];
export function StatusBadge({ status }) {
  const [c, l] = STATUS[status] || ["gray", status];
  return <Badge color={c} dot>{l}</Badge>;
}

export function CopyButton({ text, label }) {
  const [done, setDone] = useState(false);
  return (
    <button
      className="inline-flex h-7 items-center gap-1 rounded-md border border-line bg-surface px-2 text-xs font-medium text-ink-2 transition hover:bg-surface-3 hover:text-ink"
      onClick={async (e) => {
        e.stopPropagation();
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
      title="Copy"
    >
      {done ? <Check className="h-3.5 w-3.5 text-emerald-500" /> : <Copy className="h-3.5 w-3.5" />}
      {label && (done ? "Copied" : label)}
    </button>
  );
}

// ---- overlays ----------------------------------------------------------------------------------------------
export function Modal({ open, onClose, title, subtitle, children, wide }) {
  useEffect(() => {
    if (!open) return undefined;
    const k = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="anim-fade fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-4 backdrop-blur-[2px]" onClick={onClose}>
      <div className={cx("card anim-pop mt-10 w-full shadow-2xl", wide ? "max-w-4xl" : "max-w-xl")} onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between gap-4 border-b border-line px-5 py-4">
          <div className="min-w-0">
            <h3 className="text-[15px] font-semibold">{title}</h3>
            {subtitle && <p className="mt-0.5 text-xs text-ink-3">{subtitle}</p>}
          </div>
          <button className="rounded-md p-1 text-ink-3 hover:bg-surface-3 hover:text-ink" onClick={onClose} aria-label="Close">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  );
}

export function Drawer({ open, onClose, title, subtitle, children, footer }) {
  useEffect(() => {
    if (!open) return undefined;
    const k = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="anim-fade fixed inset-0 z-50 bg-black/40 backdrop-blur-[2px]" onClick={onClose}>
      <aside
        className="anim-slide absolute inset-y-0 right-0 flex w-full max-w-2xl flex-col border-l border-line bg-surface shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4 border-b border-line px-6 py-4">
          <div className="min-w-0">
            <h3 className="truncate text-[15px] font-semibold">{title}</h3>
            {subtitle && <div className="mt-1 text-xs text-ink-3">{subtitle}</div>}
          </div>
          <button className="rounded-md p-1 text-ink-3 hover:bg-surface-3 hover:text-ink" onClick={onClose} aria-label="Close">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-6 py-5">{children}</div>
        {footer && <div className="border-t border-line px-6 py-3">{footer}</div>}
      </aside>
    </div>
  );
}

// ---- table ---------------------------------------------------------------------------------------------------
export function EmptyState({ icon: Icon = Inbox, title = "Nothing here yet", text }) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-14 text-center">
      <span className="grid h-11 w-11 place-items-center rounded-xl bg-surface-3 text-ink-3">
        <Icon className="h-5 w-5" />
      </span>
      <p className="mt-3 text-[13px] font-medium text-ink">{title}</p>
      {text && <p className="mt-1 max-w-sm text-xs text-ink-3">{text}</p>}
    </div>
  );
}

export function Skeleton({ className = "" }) {
  return <div className={cx("animate-pulse rounded-md bg-surface-3", className)} />;
}

/** Sortable table. columns: [{key, label, render?, sort?, className?, align?}] */
export function Table({ columns, rows, onRowClick, empty, initialSort, loading }) {
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
      <table className="w-full text-[13px]">
        <thead>
          <tr className="border-b border-line bg-surface-2">
            {columns.map((c) => (
              <th
                key={c.key}
                className={cx(
                  "px-4 py-2.5 text-[11.5px] font-medium tracking-wide whitespace-nowrap text-ink-3 uppercase select-none",
                  c.label && c.sortable !== false ? "cursor-pointer hover:text-ink-2" : "",
                  c.align === "right" ? "text-right" : "text-left",
                  c.className
                )}
                onClick={() => c.label && c.sortable !== false && setSort((s) => ({ key: c.key, dir: s?.key === c.key && s.dir === "desc" ? "asc" : "desc" }))}
              >
                <span className="inline-flex items-center gap-1">
                  {c.label}
                  {sort?.key === c.key && (sort.dir === "asc" ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />)}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {loading &&
            !rows &&
            [0, 1, 2, 3].map((i) => (
              <tr key={i}>
                {columns.map((c) => (
                  <td key={c.key} className="px-4 py-3.5"><Skeleton className="h-4 w-full max-w-[140px]" /></td>
                ))}
              </tr>
            ))}
          {rows && sorted.length === 0 && (
            <tr>
              <td colSpan={columns.length}>{empty || <EmptyState />}</td>
            </tr>
          )}
          {sorted.map((r, i) => (
            <tr
              key={r.id ?? i}
              className={cx("group transition-colors", onRowClick && "cursor-pointer hover:bg-surface-2")}
              onClick={onRowClick ? () => onRowClick(r) : undefined}
            >
              {columns.map((c) => (
                <td key={c.key} className={cx("px-4 py-3 align-middle", c.align === "right" && "tnum text-right", c.className)}>
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

export function Thumb({ src, size = "h-10 w-10" }) {
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    setFailed(false);
  }, [src]);
  if (!src || failed)
    return (
      <div className={cx(size, "grid shrink-0 place-items-center rounded-lg border border-line bg-surface-3 text-ink-3")}>
        <ImageIcon className="h-1/3 w-1/3" />
      </div>
    );
  return <img src={src} alt="" onError={() => setFailed(true)} className={cx(size, "shrink-0 rounded-lg border border-line bg-white object-contain p-0.5")} />;
}

export function Stat({ label, children }) {
  return (
    <div className="min-w-0">
      <div className="text-[11.5px] font-medium tracking-wide text-ink-3 uppercase">{label}</div>
      <div className="mt-1 truncate text-[13px] text-ink">{children}</div>
    </div>
  );
}

// ---- price breakdown --------------------------------------------------------------------------------------------
export function Breakdown({ b }) {
  if (!b) return <p className="text-[13px] text-ink-3">No price breakdown available.</p>;
  const line = (label, value, opts = {}) => ({ label, value, ...opts });
  const groups = [
    [
      line("Amazon price", money(b.amazon_price)),
      line(`Sales tax Amazon charges (${b.sales_tax_percent}%)`, `+${money(b.amazon_sales_tax)}`),
      line("Amazon cost", money(b.amazon_cost), { total: true }),
    ],
    [
      line(`× Margin multiplier`, `${b.margin_multiplier}×`, { hint: money(b.after_margin) }),
      line(`× (1 + eBay fee ${b.ebay_fee_percent}%)`, money(b.after_ebay_fee_gross_up)),
      line(`× (1 + promo ${b.promo_rate_percent}%)`, money(b.after_promo_gross_up)),
      line("+ Fixed fee per order", money(b.ebay_fee_fixed_per_order)),
      line("Raw price", `$${b.raw_price.toFixed(4)}`),
      line(`Rounding · ${b.rounding_mode === "next_dollar_99" ? "next dollar .99" : "nearest .99 above"}`, `+${money(b.rounding_added)}`),
      line("eBay price", money(b.ebay_price), { total: true, accent: true }),
    ],
    [
      line(`eBay fees · ${b.ebay_fee_percent}% of price + ${b.buyer_tax_estimate}% buyer tax, + fixed`, `−${money(b.ebay_fees)}`),
      line(`Promoted Listings · ${b.promo_rate_percent}% of price + buyer tax`, `−${money(b.promo_fee)}`),
      line("Amazon cost", `−${money(b.amazon_cost)}`),
    ],
  ];
  return (
    <div>
      <div className="divide-y divide-line overflow-hidden rounded-lg border border-line">
        {groups.map((g, gi) => (
          <div key={gi} className="px-4 py-2">
            {g.map((l, i) => (
              <div key={i} className={cx("flex items-baseline justify-between gap-4 py-1", l.total && "font-semibold")}>
                <span className={cx("text-[13px]", l.total ? "text-ink" : "text-ink-2")}>
                  {l.label}
                  {l.hint && <span className="ml-1.5 text-ink-3">({l.hint})</span>}
                </span>
                <span className={cx("tnum text-[13px]", l.accent ? "text-accent-ink" : "text-ink")}>{l.value}</span>
              </div>
            ))}
          </div>
        ))}
        <div className="flex items-center justify-between gap-4 bg-surface-2 px-4 py-3">
          <span className="text-[13px] font-semibold">Expected profit</span>
          <span className="tnum text-right">
            <span className={cx("text-[15px] font-semibold", b.profit < 0 ? "text-rose-600 dark:text-rose-400" : "text-emerald-600 dark:text-emerald-400")}>
              {money(b.profit)}
            </span>
            <span className="ml-2 text-xs text-ink-3">{pct(b.profit_percent)} of cost</span>
          </span>
        </div>
      </div>
      <div className="mt-3">
        {b.passes_floor ? (
          <Badge color="green" dot>Passes profit floor</Badge>
        ) : (
          <Badge color="red" dot>Below floor · {b.floor_reasons.join("; ")}</Badge>
        )}
      </div>
    </div>
  );
}
