import { useState } from "react";
import { api } from "../api";
import { ActionButton, Badge, Breakdown, Button, Card, Modal, StatusBadge, Table, clock, money, useLoad } from "../components/ui";

export default function Queue() {
  const [data, reload] = useLoad(() => api.get("/queue"), [], 15000);
  const [asin, setAsin] = useState("");
  const [force, setForce] = useState(false);
  const [preview, setPreview] = useState(null);
  const cols = [
    { key: "scheduled_at", label: "Posts at", render: (r) => (r.scheduled_at ? clock(r.scheduled_at) : "—") },
    { key: "title", label: "Product", className: "max-w-sm", render: (r) => <div><div className="line-clamp-2">{r.title}</div><div className="text-xs text-slate-500">{r.asin} {r.source === "manual" && <Badge>manual</Badge>}</div></div> },
    { key: "amazon_price", label: "Amazon", render: (r) => money(r.amazon_price) },
    { key: "ebay_price", label: "eBay", render: (r) => money(r.ebay_price) },
    { key: "expected_profit", label: "Profit", render: (r) => money(r.expected_profit) },
    { key: "status", label: "Status", render: (r) => <div><StatusBadge status={r.status} />{r.message && <div className="mt-1 max-w-xs text-xs text-slate-500">{r.message}</div>}</div> },
    {
      key: "act", label: "",
      render: (r) => (
        <div className="flex gap-1" onClick={(e) => e.stopPropagation()}>
          <Button onClick={() => setPreview(r)}>Preview</Button>
          {["queued", "scheduled"].includes(r.status) && (
            <>
              <ActionButton action={() => api.post(`/queue/${r.id}/post-now`)} onDone={() => setTimeout(reload, 3000)}>Post now</ActionButton>
              <ActionButton kind="danger" action={() => api.del(`/queue/${r.id}`)} onDone={reload}>Remove</ActionButton>
            </>
          )}
        </div>
      ),
    },
  ];
  return (
    <div className="space-y-4">
      <Card
        title={data ? `Queue for ${data.date} — ${data.posted_today}/${data.listings_per_day} posted, window ${data.window[0]}–${data.window[1]}` : "Queue"}
        actions={
          <ActionButton action={() => api.post("/queue/build").then(() => ({ message: "Building — this takes a while (Amazon pacing)" }))} onDone={() => setTimeout(reload, 5000)}>
            Build queue now
          </ActionButton>
        }
      >
        <form
          className="mb-4 flex flex-wrap items-center gap-2"
          onSubmit={async (e) => {
            e.preventDefault();
            await api.post("/queue", { asin, force });
            setAsin("");
            setTimeout(reload, 4000);
          }}
        >
          <input placeholder="Add an ASIN manually (e.g. B0…)" value={asin} onChange={(e) => setAsin(e.target.value)} className="w-64" />
          <label className="flex items-center gap-1 text-sm" title="Skip price/rating/review/Prime/shipping filters. Stock, blocklist and profit floor still apply.">
            <input type="checkbox" checked={force} onChange={(e) => setForce(e.target.checked)} /> ignore search filters
          </label>
          <Button kind="primary" type="submit" disabled={!asin}>Add</Button>
        </form>
        <Table columns={cols} rows={data?.items} onRowClick={setPreview} empty="Queue is empty. It's built daily at the queue build time (Settings), or press 'Build queue now'." />
      </Card>
      <Modal open={!!preview} onClose={() => setPreview(null)} title="Listing preview" wide>
        {preview && <Preview item={preview} />}
      </Modal>
    </div>
  );
}

function Preview({ item }) {
  const p = item.preview || {};
  return (
    <div className="space-y-4 text-sm">
      <div>
        <div className="text-xs text-slate-500">eBay title ({(p.title || "").length}/80) · written by {p.writer}</div>
        <div className="text-lg font-semibold">{p.title}</div>
        <div className="text-xs text-slate-500">Category: {p.category_name || p.category_note || "—"}</div>
        {p.missing_required_aspects?.length > 0 && (
          <Badge color="yellow">eBay requires specifics we couldn't fill: {p.missing_required_aspects.join(", ")}</Badge>
        )}
      </div>
      <div className="flex gap-2 overflow-x-auto">
        {(p.images || []).map((u) => <img key={u} src={u} alt="" className="h-24 w-24 rounded border object-contain" />)}
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <div><h4 className="mb-1 font-medium">Price breakdown</h4><Breakdown b={item.breakdown} /></div>
        <div>
          <h4 className="mb-1 font-medium">Item specifics</h4>
          <div className="flex flex-wrap gap-1">{Object.entries(p.aspects || {}).map(([k, v]) => <Badge key={k}>{k}: {v.join(", ")}</Badge>)}</div>
          <a className="mt-3 inline-block text-indigo-600" href={p.product?.url} target="_blank" rel="noreferrer">Amazon page ↗</a>
        </div>
      </div>
      <iframe title="description" sandbox="" className="h-80 w-full rounded border bg-white" srcDoc={p.description_html} />
    </div>
  );
}
