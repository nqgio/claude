import { AlertTriangle, EyeOff, ExternalLink, MapPin, RefreshCw, ShoppingBag, ShoppingCart, Truck, Users, Wallet } from "lucide-react";
import { useState } from "react";
import { api } from "../api";
import AmazonAccounts, { OrderingToggle } from "../components/AmazonAccounts";
import {
  ActionButton, Badge, Button, Card, CopyButton, Drawer, EmptyState, Modal, PageHeader, Segmented, StatusBadge, Table, cx, money, statusLabel,
  when, useLoad,
} from "../components/ui";

const STATUSES = ["awaiting_purchase", "purchased", "shipped", "tracking_uploaded", "delivered", "cancelled", "returned", "refunded"];

const addressBlock = (o) =>
  [o.ship_name, o.ship_line1, o.ship_line2, `${o.ship_city}, ${o.ship_state} ${o.ship_postal}`, o.ship_country].filter(Boolean).join("\n");

function Section({ step, title, icon: Icon, children }) {
  return (
    <section className="rounded-xl border border-line">
      <div className="flex items-center gap-2.5 border-b border-line bg-surface-2 px-4 py-2.5">
        {step && <span className="grid h-5 w-5 place-items-center rounded-full bg-accent text-[11px] font-semibold text-white">{step}</span>}
        {Icon && !step && <Icon className="h-4 w-4 text-ink-3" />}
        <h4 className="text-[13px] font-semibold">{title}</h4>
      </div>
      <div className="p-4">{children}</div>
    </section>
  );
}

function Money({ label, value, est, strong, negative }) {
  return (
    <div className="flex items-center justify-between py-1 text-[13px]">
      <span className={strong ? "font-semibold" : "text-ink-2"}>
        {label} {est && <Badge color="yellow" className="ml-1">est.</Badge>}
      </span>
      <span className={cx("tnum", strong && "text-[15px] font-semibold", strong && (value < 0 ? "text-rose-600 dark:text-rose-400" : "text-emerald-600 dark:text-emerald-400"))}>
        {negative && value ? "−" : ""}{money(Math.abs(value))}
      </span>
    </div>
  );
}

function OrderPanel({ order, onChange, checkoutMode, accts }) {
  const [o, setO] = useState(order);
  const accountList = accts?.accounts || [];
  const [acctId, setAcctId] = useState(order.amazon_account_id ?? accts?.next_account_id ?? "");
  const nextAcct = accountList.find((a) => a.id === accts?.next_account_id);
  const boughtWith = accountList.find((a) => a.id === o.amazon_account_id);
  const [amzId, setAmzId] = useState(order.amazon_order_id || "");
  const [cost, setCost] = useState(order.amazon_cost ?? "");
  const [tracking, setTracking] = useState(order.tracking_number || "");
  const [carrier, setCarrier] = useState("");
  const [refund, setRefund] = useState(order.amazon_refund || "");
  const f = o.financials;
  const update = (x) => {
    setO(x.order || x);
    onChange();
  };
  const fields = [
    ["Name", o.ship_name], ["Address 1", o.ship_line1], ["Address 2", o.ship_line2], ["City", o.ship_city],
    ["State", o.ship_state], ["ZIP", o.ship_postal], ["Phone", o.ship_phone],
  ];
  return (
    <div className="space-y-5">
      {o.flag && (
        <div className="flex gap-3 rounded-xl border border-rose-200 bg-rose-50 p-3.5 text-[13px] text-rose-800 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-200">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <div className="flex-1">
            <div className="font-semibold">{o.flag === "tba_manual" ? "TBA – manual action" : "Needs attention"}</div>
            <div className="mt-0.5">{o.flag_reason}</div>
          </div>
          <ActionButton size="sm" action={() => api.post(`/orders/${o.id}/clear-flag`)} onDone={update}>Clear</ActionButton>
        </div>
      )}

      {!o.managed && (
        <div className="flex gap-3 rounded-xl border border-line bg-surface-2 p-3.5 text-[13px] text-ink-2">
          <EyeOff className="mt-0.5 h-4 w-4 shrink-0 text-ink-3" />
          <div className="flex-1">
            <div className="font-semibold text-ink">Not managed by this app</div>
            <div className="mt-0.5">This item wasn't listed by the app, so it's one of your own. It's never bought on Amazon and isn't counted in the dashboard's revenue or profit.</div>
          </div>
          <ActionButton size="sm" confirm="Count this order as one of the app's? It will show in profit numbers. It still won't be auto-bought."
            action={() => api.post(`/orders/${o.id}/managed`, { managed: true })} onDone={update} success="Now managed by this app">Manage it</ActionButton>
        </div>
      )}

      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="text-[13px] font-semibold">{o.quantity}× {o.title}</div>
          <div className="mt-1 flex flex-wrap items-center gap-2 font-mono text-xs text-ink-3">
            {o.asin || "no linked listing"}
            {o.managed && !o.asin && (
              <ActionButton size="sm" icon={EyeOff} action={() => api.post(`/orders/${o.id}/managed`, { managed: false })} onDone={update}
                success="Moved to Other eBay sales">Not from this app — leave it alone</ActionButton>
            )}
          </div>
        </div>
        {o.amazon_url && (
          <a href={o.amazon_url} target="_blank" rel="noreferrer"
            className="inline-flex h-9 shrink-0 items-center gap-2 rounded-lg bg-[#ff9900] px-3.5 text-[13px] font-semibold text-black shadow-xs hover:brightness-105">
            Buy on Amazon <ExternalLink className="h-3.5 w-3.5" />
          </a>
        )}
      </div>

      <div className={cx("grid gap-5", o.managed && "md:grid-cols-2")}>
        <Section title="Ship to" icon={MapPin}>
          <div className="space-y-1.5">
            {fields.map(([k, v]) => (
              <div key={k} className="flex items-center justify-between gap-2 text-[13px]">
                <span className="w-20 shrink-0 text-ink-3">{k}</span>
                <span className="flex-1 truncate">{v || "—"}</span>
                {v && <CopyButton text={v} />}
              </div>
            ))}
          </div>
          <div className="mt-3"><CopyButton text={addressBlock(o)} label="Copy full address" /></div>
        </Section>
        {o.managed && <Section title="Profit" icon={Wallet}>
          <Money label="Revenue" value={f.revenue} />
          <Money label="Buyer tax (eBay remits)" value={f.buyer_tax} negative />
          <Money label="Amazon cost" value={f.amazon_cost} est={!f.amazon_cost_is_actual} negative />
          <Money label="eBay fees" value={f.ebay_fees} est={!f.fees_are_actual} negative />
          <Money label="Promoted Listings" value={f.promo_fee} est={!f.fees_are_actual} negative />
          {f.refund_to_buyer > 0 && <Money label="Refund to buyer" value={f.refund_to_buyer} negative />}
          {f.amazon_refund > 0 && <Money label="Amazon refund" value={f.amazon_refund} />}
          <div className="mt-1 border-t border-line pt-1.5"><Money label="Profit" value={f.profit} strong /></div>
        </Section>}
      </div>

      {o.managed && <Section step="1" title="Amazon purchase">
        {o.status === "awaiting_purchase" && nextAcct && (
          <p className="mb-3 text-[12.5px] text-ink-2">
            Buy with <strong className="font-semibold text-ink">{nextAcct.name}</strong> (next in your account rotation).
          </p>
        )}
        {boughtWith && o.status !== "awaiting_purchase" && (
          <p className="mb-3 text-[12.5px] text-ink-2">Bought with <strong className="font-semibold text-ink">{boughtWith.name}</strong>.</p>
        )}
        <div className="flex flex-wrap gap-2">
          {accountList.length > 0 && (
            <select value={acctId} onChange={(e) => setAcctId(e.target.value)} className="w-40" aria-label="Amazon account used">
              <option value="">Which account?</option>
              {accountList.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
            </select>
          )}
          <input placeholder="Amazon order # (112-…)" value={amzId} onChange={(e) => setAmzId(e.target.value)} className="min-w-[150px] flex-1" />
          <input placeholder="Total paid (incl. tax)" type="number" step="0.01" value={cost} onChange={(e) => setCost(e.target.value)} className="w-32" />
          <ActionButton kind="primary"
            action={() => api.post(`/orders/${o.id}/purchase`, {
              amazon_order_id: amzId, amazon_cost: cost === "" ? null : Number(cost), amazon_account_id: acctId === "" ? null : Number(acctId),
            })}
            onDone={update} success="Purchase saved">Save</ActionButton>
        </div>
        <p className="mt-2 text-xs text-ink-3">Leave the total blank if unsure. The estimate is used until you fill it in.</p>
        {checkoutMode === "auto" && o.status === "awaiting_purchase" && (
          <div className="mt-3">
            <ActionButton icon={ShoppingCart} confirm="Place this order on Amazon now? All safeguards still apply."
              action={() => api.post(`/orders/${o.id}/auto-buy`)}>Auto-buy now</ActionButton>
          </div>
        )}
      </Section>}

      <Section step={o.managed ? "2" : null} icon={Truck} title="Tracking">
        <div className="flex flex-wrap gap-2">
          <input placeholder="Tracking number" value={tracking} onChange={(e) => setTracking(e.target.value)} className="min-w-[200px] flex-1" />
          <select value={carrier} onChange={(e) => setCarrier(e.target.value)} className="w-44">
            <option value="">Detect carrier</option>
            <option>UPS</option><option>USPS</option><option>FedEx</option><option value="Amazon">Amazon Logistics</option>
          </select>
          <ActionButton kind="primary"
            action={async () => {
              const r = await api.post(`/orders/${o.id}/tracking`, { tracking_number: tracking, carrier });
              return {
                ...r,
                message: r.carrier === "AMAZON" ? "Amazon Logistics number: not uploaded. Order flagged 'TBA – manual action'."
                  : r.uploaded ? `Uploaded to eBay as ${r.carrier}.` : `Saved (${r.carrier}), not uploaded. See the activity log.`,
              };
            }}
            onDone={update}>Save</ActionButton>
        </div>
        {o.tracking_number && (
          <p className="mt-2 flex items-center gap-2 text-xs text-ink-2">
            <Truck className="h-3.5 w-3.5" /> {o.carrier} {o.tracking_number}
            {o.tracking_uploaded_at ? <Badge color="green">Uploaded {when(o.tracking_uploaded_at)}</Badge> : <Badge>Not uploaded</Badge>}
          </p>
        )}
      </Section>

      <Section step={o.managed ? "3" : null} icon={Wallet} title="Adjustments">
        <div className="flex flex-wrap items-center gap-2">
          <input placeholder="Amazon refund ($)" type="number" step="0.01" value={refund} onChange={(e) => setRefund(e.target.value)} className="w-44" />
          <ActionButton action={() => api.post(`/orders/${o.id}/amazon-refund`, { amount: Number(refund || 0) })} onDone={update} success="Refund saved">
            Save refund
          </ActionButton>
          <div className="ml-auto flex items-center gap-2 text-[13px] text-ink-2">
            Status
            <select value={o.status} onChange={async (e) => update(await api.post(`/orders/${o.id}/status`, { status: e.target.value }))}>
              {STATUSES.map((s) => <option key={s} value={s}>{statusLabel(s)}</option>)}
            </select>
          </div>
        </div>
        {o.notes && <pre className="mt-3 whitespace-pre-wrap text-xs text-ink-3">{o.notes}</pre>}
      </Section>
    </div>
  );
}

export default function Orders({ status: appStatus, reloadStatus }) {
  const [status, setStatus] = useState("");
  const [view, setView] = useState("app"); // app = orders for this app's listings, other = your own items
  const [showAccounts, setShowAccounts] = useState(false);
  const [rows, reload] = useLoad(() => api.get(`/orders?managed=${view === "app"}${status ? `&status=${status}` : ""}`), [status, view], 30000);
  const [accts, reloadAccts] = useLoad(() => api.get("/amazon/accounts"), [], 60000);
  const [open, setOpen] = useState(null);
  const needs = (rows || []).filter((o) => o.status === "awaiting_purchase").length;
  const cols = [
    { key: "created_at", label: "Date", render: (o) => <span className="whitespace-nowrap text-ink-2">{when(o.created_at)}</span> },
    {
      key: "title", label: "Item", className: "min-w-[240px]",
      render: (o) => (
        <div>
          <div className="line-clamp-1 font-medium">{o.quantity > 1 && <span className="text-ink-3">{o.quantity}× </span>}{o.title}</div>
          <div className="mt-0.5 font-mono text-xs text-ink-3">{o.ebay_order_id}</div>
        </div>
      ),
    },
    { key: "ship_name", label: "Buyer", render: (o) => <div className="whitespace-nowrap">{o.ship_name}<div className="text-xs text-ink-3">{o.ship_city}, {o.ship_state}</div></div> },
    { key: "revenue_total", label: "Revenue", align: "right", render: (o) => money(o.revenue_total) },
    ...(view === "other" ? [] : [{ key: "cost", label: "Cost", align: "right", sort: (o) => o.financials.amazon_cost, render: (o) => <span className={o.financials.amazon_cost_is_actual ? "" : "text-ink-3"}>{money(o.financials.amazon_cost)}</span> },
    { key: "fees", label: "Fees", align: "right", sort: (o) => o.financials.ebay_fees + o.financials.promo_fee, render: (o) => <span className={o.financials.fees_are_actual ? "" : "text-ink-3"}>{money(o.financials.ebay_fees + o.financials.promo_fee)}</span> },
    { key: "profit", label: "Profit", align: "right", sort: (o) => o.financials.profit, render: (o) => <span className={cx("font-medium", o.financials.profit < 0 ? "text-rose-600 dark:text-rose-400" : "text-emerald-600 dark:text-emerald-400")}>{money(o.financials.profit)}</span> }]),
    {
      key: "status", label: "Status",
      render: (o) => (
        <div className="flex flex-col items-start gap-1">
          {o.managed ? <StatusBadge status={o.status} /> : <Badge>{o.status === "awaiting_purchase" ? "Not managed" : statusLabel(o.status)}</Badge>}
          {o.flag === "tba_manual" && <Badge color="red">TBA – manual</Badge>}
          {o.flag && o.flag !== "tba_manual" && <Badge color="red">Needs attention</Badge>}
        </div>
      ),
    },
    { key: "tracking_number", label: "Tracking", render: (o) => (o.tracking_number ? <span className="text-xs whitespace-nowrap">{o.carrier} · {o.tracking_number.slice(-6)}</span> : <span className="text-ink-3">—</span>) },
  ];
  return (
    <>
      <PageHeader
        title="Orders"
        description={view === "other" ? "eBay sales of items this app didn't list. Never bought on Amazon, not counted in profit."
          : needs ? `${needs} order${needs > 1 ? "s" : ""} waiting to be purchased on Amazon.` : "Every eBay order, its costs and fulfillment."}
        actions={
          <>
            <div className="flex items-center gap-2 text-[13px] text-ink-2">
              Ordering <OrderingToggle status={appStatus} reloadStatus={reloadStatus} />
            </div>
            <Button icon={Users} onClick={() => setShowAccounts(true)}>
              Amazon accounts
              {appStatus && <Badge color={appStatus.amazon.accounts_logged_in ? "green" : "yellow"}>{appStatus.amazon.accounts_logged_in}/{appStatus.amazon.accounts}</Badge>}
            </Button>
            <ActionButton icon={RefreshCw} action={() => api.post("/orders/sync")} onDone={() => setTimeout(reload, 5000)} success="Syncing orders from eBay">Sync from eBay</ActionButton>
          </>
        }
      />
      <Card padded={false}>
        <div className="flex flex-wrap items-center gap-3 border-b border-line px-4 py-3">
          <Segmented value={view} onChange={(v) => { setView(v); setOpen(null); }}
            options={[["app", "This app's orders"], ["other", "Other eBay sales"]]} />
          <Segmented value={status} onChange={setStatus}
            options={[["", "All"], ["awaiting_purchase", "Needs purchase"], ["purchased", "Purchased"], ["shipped", "Shipped"], ["tracking_uploaded", "Tracked"], ["delivered", "Delivered"]]} />
          <select value={STATUSES.slice(5).includes(status) ? status : ""} onChange={(e) => setStatus(e.target.value)} className="w-40">
            <option value="">More statuses…</option>
            {STATUSES.slice(5).map((x) => <option key={x} value={x}>{statusLabel(x)}</option>)}
          </select>
        </div>
        <Table columns={cols} rows={rows} loading onRowClick={setOpen} initialSort={{ key: "created_at", dir: "desc" }}
          empty={view === "other"
            ? <EmptyState icon={EyeOff} title="No other sales" text="Sales of items you listed yourself (not through this app) show up here and are left alone." />
            : <EmptyState icon={ShoppingBag} title="No orders yet" text="Orders sync from eBay every few minutes once eBay is connected." />} />
      </Card>
      <Modal open={showAccounts} onClose={() => { setShowAccounts(false); reloadAccts(); }} title="Amazon accounts" wide
        subtitle="Add the accounts you buy with. Each logs in once in its own browser window; passwords and cards are never stored.">
        <AmazonAccounts status={appStatus} reloadStatus={reloadStatus} bare />
      </Modal>
      <Drawer open={!!open} onClose={() => setOpen(null)} title={open ? `Order ${open.ebay_order_id}` : ""}
        subtitle={open && <span className="flex flex-wrap items-center gap-2">{open.managed ? <StatusBadge status={open.status} /> : <Badge>Not managed</Badge>} {when(open.created_at)} · buyer {open.buyer_username}</span>}>
        {open && <OrderPanel key={open.id} order={open} onChange={() => { reload(); reloadAccts(); }} checkoutMode={appStatus?.checkout_mode} accts={accts} />}
      </Drawer>
    </>
  );
}
