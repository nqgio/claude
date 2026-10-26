import { useState } from "react";
import { api } from "../api";
import { ActionButton, Badge, Button, Card, CopyButton, Modal, StatusBadge, Table, money, when, useLoad } from "../components/ui";

const STATUSES = ["awaiting_purchase", "purchased", "shipped", "tracking_uploaded", "delivered", "cancelled", "returned", "refunded"];

function addressBlock(o) {
  return [o.ship_name, o.ship_line1, o.ship_line2, `${o.ship_city}, ${o.ship_state} ${o.ship_postal}`, o.ship_country]
    .filter(Boolean)
    .join("\n");
}

function OrderPanel({ order, onChange, checkoutMode }) {
  const [o, setO] = useState(order);
  const [amzId, setAmzId] = useState(order.amazon_order_id || "");
  const [cost, setCost] = useState(order.amazon_cost ?? "");
  const [tracking, setTracking] = useState(order.tracking_number || "");
  const [carrier, setCarrier] = useState("");
  const [refund, setRefund] = useState(order.amazon_refund || "");
  const [msg, setMsg] = useState(null);
  const f = o.financials;
  const update = (x) => {
    setO(x.order || x);
    onChange();
  };
  const fields = [
    ["Full name", o.ship_name], ["Address line 1", o.ship_line1], ["Address line 2", o.ship_line2], ["City", o.ship_city],
    ["State", o.ship_state], ["ZIP", o.ship_postal], ["Phone", o.ship_phone],
  ];
  return (
    <div className="space-y-4 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <StatusBadge status={o.status} />
        {o.flag === "tba_manual" && <Badge color="red">TBA – manual action</Badge>}
        {o.flag && o.flag !== "tba_manual" && <Badge color="red">⚑ {o.flag}</Badge>}
        <span className="text-slate-500">eBay order {o.ebay_order_id} · {when(o.created_at)} · buyer {o.buyer_username}</span>
      </div>
      {o.flag_reason && <p className="rounded bg-rose-50 p-2 text-rose-800 dark:bg-rose-950 dark:text-rose-200">{o.flag_reason}</p>}
      <div>
        <div className="font-medium">{o.quantity}× {o.title}</div>
        {o.amazon_url && (
          <a href={o.amazon_url} target="_blank" rel="noreferrer"
             className="mt-2 inline-block rounded-md bg-amber-500 px-3 py-1.5 font-medium text-white hover:bg-amber-400">
            Open Amazon product page ↗
          </a>
        )}
      </div>
      <div className="rounded-lg border p-3 dark:border-slate-700">
        <div className="mb-2 flex items-center justify-between">
          <strong>Ship to</strong>
          <CopyButton text={addressBlock(o)} label="Copy full address" />
        </div>
        <table className="w-full">
          <tbody>
            {fields.map(([k, v]) => (
              <tr key={k}>
                <td className="w-32 py-0.5 text-slate-500">{k}</td>
                <td className="py-0.5">{v || "—"}</td>
                <td className="py-0.5 text-right">{v && <CopyButton text={v} />}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="grid grid-cols-2 gap-x-4 gap-y-1 rounded-lg border p-3 dark:border-slate-700 sm:grid-cols-3">
        <div>Revenue: {money(f.revenue)}</div>
        <div>Buyer tax (eBay remits): −{money(f.buyer_tax)}</div>
        <div>Amazon cost: −{money(f.amazon_cost)} {!f.amazon_cost_is_actual && <Badge color="yellow">est.</Badge>}</div>
        <div>eBay fees: −{money(f.ebay_fees)} {!f.fees_are_actual && <Badge color="yellow">est.</Badge>}</div>
        <div>Promo fee: −{money(f.promo_fee)} {!f.fees_are_actual && <Badge color="yellow">est.</Badge>}</div>
        <div>Refund to buyer: −{money(f.refund_to_buyer)}</div>
        <div>Amazon refund: +{money(f.amazon_refund)}</div>
        <div className="font-semibold">Profit: {money(f.profit)}</div>
      </div>

      <div className="space-y-2 rounded-lg border p-3 dark:border-slate-700">
        <strong>1. Amazon purchase</strong>
        <div className="flex flex-wrap items-center gap-2">
          <input placeholder="Amazon order # (112-…)" value={amzId} onChange={(e) => setAmzId(e.target.value)} />
          <input placeholder="Total paid incl. tax" type="number" step="0.01" value={cost} onChange={(e) => setCost(e.target.value)} className="w-40" />
          <ActionButton kind="primary"
            action={() => api.post(`/orders/${o.id}/purchase`, { amazon_order_id: amzId, amazon_cost: cost === "" ? null : Number(cost) })}
            onDone={update}>Save purchase</ActionButton>
          {checkoutMode === "auto" && o.status === "awaiting_purchase" && (
            <ActionButton confirm="Place this order on Amazon now (all safeguards still apply)?"
              action={() => api.post(`/orders/${o.id}/auto-buy`)}>Auto-buy now</ActionButton>
          )}
        </div>
        <p className="text-xs text-slate-500">Leave "total paid" blank if unsure — the estimate is used until you fill it in.</p>
      </div>

      <div className="space-y-2 rounded-lg border p-3 dark:border-slate-700">
        <strong>2. Tracking</strong>
        <div className="flex flex-wrap items-center gap-2">
          <input placeholder="Tracking number" value={tracking} onChange={(e) => setTracking(e.target.value)} />
          <select value={carrier} onChange={(e) => setCarrier(e.target.value)}>
            <option value="">Detect carrier</option>
            <option>UPS</option><option>USPS</option><option>FedEx</option><option value="Amazon">Amazon Logistics</option>
          </select>
          <ActionButton kind="primary"
            action={async () => {
              const r = await api.post(`/orders/${o.id}/tracking`, { tracking_number: tracking, carrier });
              setMsg(r.carrier === "AMAZON" ? "Amazon Logistics number — NOT uploaded. Order flagged 'TBA – manual action'."
                : r.uploaded ? `Uploaded to eBay as ${r.carrier}.` : `Saved (${r.carrier}); not uploaded — see activity log.`);
              return r;
            }}
            onDone={update}>Save tracking</ActionButton>
        </div>
        {o.tracking_number && <p className="text-xs">Current: {o.tracking_number} ({o.carrier}) {o.tracking_uploaded_at ? `· uploaded ${when(o.tracking_uploaded_at)}` : "· not uploaded"}</p>}
        {msg && <p className="text-xs text-slate-600">{msg}</p>}
      </div>

      <div className="flex flex-wrap items-center gap-2 rounded-lg border p-3 dark:border-slate-700">
        <strong className="mr-2">3. Adjustments</strong>
        <input placeholder="Amazon refund received" type="number" step="0.01" value={refund} onChange={(e) => setRefund(e.target.value)} className="w-44" />
        <ActionButton action={() => api.post(`/orders/${o.id}/amazon-refund`, { amount: Number(refund || 0) })} onDone={update}>Save refund</ActionButton>
        <select value={o.status} onChange={async (e) => update(await api.post(`/orders/${o.id}/status`, { status: e.target.value }))}>
          {STATUSES.map((s) => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}
        </select>
        {o.flag && <ActionButton action={() => api.post(`/orders/${o.id}/clear-flag`)} onDone={update}>Clear flag</ActionButton>}
      </div>
      {o.notes && <pre className="whitespace-pre-wrap text-xs text-slate-500">{o.notes}</pre>}
    </div>
  );
}

export default function Orders() {
  const [status, setStatus] = useState("");
  const [rows, reload] = useLoad(() => api.get(`/orders${status ? `?status=${status}` : ""}`), [status], 30000);
  const [s] = useLoad(() => api.get("/status"), []);
  const [open, setOpen] = useState(null);
  const cols = [
    { key: "created_at", label: "Date", render: (o) => <span className="text-xs">{when(o.created_at)}</span> },
    { key: "title", label: "Item", className: "max-w-xs", render: (o) => <div className="line-clamp-2">{o.quantity}× {o.title}</div> },
    { key: "ship_name", label: "Buyer", render: (o) => <div>{o.ship_name}<div className="text-xs text-slate-500">{o.ship_city}, {o.ship_state}</div></div> },
    { key: "revenue_total", label: "Revenue", render: (o) => money(o.revenue_total) },
    { key: "cost", label: "Amazon cost", sort: (o) => o.financials.amazon_cost, render: (o) => <>{money(o.financials.amazon_cost)}{!o.financials.amazon_cost_is_actual && <sup> est</sup>}</> },
    { key: "fees", label: "Fees", sort: (o) => o.financials.ebay_fees + o.financials.promo_fee, render: (o) => <>{money(o.financials.ebay_fees + o.financials.promo_fee)}{!o.financials.fees_are_actual && <sup> est</sup>}</> },
    { key: "profit", label: "Profit", sort: (o) => o.financials.profit, render: (o) => <span className={o.financials.profit < 0 ? "text-rose-600" : ""}>{money(o.financials.profit)}</span> },
    {
      key: "status", label: "Status",
      render: (o) => (
        <div className="space-y-1">
          <StatusBadge status={o.status} />
          {o.flag === "tba_manual" && <div><Badge color="red">TBA – manual action</Badge></div>}
          {o.flag && o.flag !== "tba_manual" && <div><Badge color="red">⚑ needs attention</Badge></div>}
        </div>
      ),
    },
    { key: "tracking_number", label: "Tracking", render: (o) => <span className="text-xs">{o.tracking_number ? `${o.carrier} ${o.tracking_number}` : "—"}</span> },
    { key: "act", label: "", render: (o) => <Button onClick={(e) => { e.stopPropagation(); setOpen(o); }}>{o.status === "awaiting_purchase" ? "Buy / details" : "Details"}</Button> },
  ];
  return (
    <>
      <Card
        title="Orders"
        actions={
          <>
            <select value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="">All statuses</option>
              {STATUSES.map((x) => <option key={x} value={x}>{x.replace(/_/g, " ")}</option>)}
            </select>
            <ActionButton action={() => api.post("/orders/sync").then(() => ({ message: "Sync started" }))} onDone={() => setTimeout(reload, 5000)}>
              Sync from eBay
            </ActionButton>
          </>
        }
      >
        <Table columns={cols} rows={rows} onRowClick={setOpen} initialSort={{ key: "created_at", dir: "desc" }} />
      </Card>
      <Modal open={!!open} onClose={() => setOpen(null)} title="Order" wide>
        {open && <OrderPanel key={open.id} order={open} onChange={reload} checkoutMode={s?.checkout_mode} />}
      </Modal>
    </>
  );
}
