import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { ActionButton, Badge, Breakdown, Button, Card, useLoad, when } from "../components/ui";

const GROUPS = [
  ["pricing", "Pricing engine"],
  ["lister", "Product finder & auto-lister"],
  ["filters", "Product filters"],
  ["listing", "Listing defaults"],
  ["refresh", "Price & stock refresh"],
  ["orders", "Orders & checkout"],
  ["amazon", "Amazon scraper"],
  ["blocklist", "Blocklist scan"],
];
const POLICY_KEYS = { fulfillment_policy_id: "fulfillment", return_policy_id: "return", payment_policy_id: "payment" };

function Field({ spec, value, onChange, policies }) {
  const id = `f-${spec.key}`;
  let input;
  if (POLICY_KEYS[spec.key] && policies) {
    const list = policies[POLICY_KEYS[spec.key]] || [];
    input = (
      <select id={id} value={value || ""} onChange={(e) => onChange(e.target.value)} className="w-full">
        <option value="">— choose —</option>
        {list.map((p) => (
          <option key={p.id} value={p.id}>
            {p.name}{p.handling_time_days != null ? ` (handling ${p.handling_time_days}d)` : ""}
          </option>
        ))}
      </select>
    );
  } else if (spec.type === "bool") {
    input = <input id={id} type="checkbox" checked={!!value} onChange={(e) => onChange(e.target.checked)} />;
  } else if (spec.type === "choice") {
    input = (
      <select id={id} value={value} onChange={(e) => onChange(e.target.value)} className="w-full">
        {spec.choices.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
      </select>
    );
  } else if (spec.type === "text") {
    input = <textarea id={id} rows={6} className="w-full font-mono text-xs" value={value || ""} onChange={(e) => onChange(e.target.value)} />;
  } else if (spec.type === "list") {
    input = (
      <textarea id={id} rows={4} className="w-full" value={(value || []).join("\n")}
        onChange={(e) => onChange(e.target.value.split("\n"))} />
    );
  } else {
    const numeric = ["float", "int", "optional_float"].includes(spec.type);
    input = (
      <input id={id} className="w-full" type={spec.type === "time" ? "time" : numeric ? "number" : "text"}
        step={spec.type === "int" ? 1 : "any"} value={value ?? ""} onChange={(e) => onChange(e.target.value)} />
    );
  }
  return (
    <div className={spec.type === "text" ? "sm:col-span-2 lg:col-span-3" : spec.type === "list" ? "sm:col-span-2" : ""}>
      <label htmlFor={id} className={`block text-sm font-medium ${spec.type === "bool" ? "flex items-center gap-2" : ""}`}>
        {spec.type === "bool" && input}
        {spec.label}
      </label>
      {spec.type !== "bool" && <div className="mt-1">{input}</div>}
      {spec.help && <p className="mt-0.5 text-xs text-slate-500">{spec.help}</p>}
    </div>
  );
}

function EbayConnection({ status, reloadStatus }) {
  const [paste, setPaste] = useState("");
  if (!status) return null;
  const e = status.ebay;
  return (
    <Card title={`eBay connection (${status.environment})`}>
      <div className="space-y-3 text-sm">
        <div className="flex flex-wrap gap-2">
          <Badge color={e.keys_present ? "green" : "red"}>{e.keys_present ? "App ID / Cert ID found in .env" : "Keys missing in .env"}</Badge>
          <Badge color={e.runame_present ? "green" : "red"}>{e.runame_present ? "RuName set" : "RuName missing"}</Badge>
          <Badge color={e.connected ? "green" : "yellow"}>{e.connected ? "Connected" : "Not connected"}</Badge>
          {e.refresh_token_expires && <span className="text-xs text-slate-500">token valid until {when(e.refresh_token_expires)}</span>}
          <Badge color={status.deletion_endpoint_configured ? "green" : "gray"}>
            Account-deletion endpoint {status.deletion_endpoint_configured ? "configured" : "not configured (needed for production)"}
          </Badge>
        </div>
        <ol className="list-decimal space-y-2 pl-5">
          <li>
            <ActionButton kind="primary" action={async () => { const r = await api.get("/ebay/connect-url"); window.open(r.url, "_blank"); }}>
              Connect eBay
            </ActionButton>{" "}
            — sign in to eBay in the new tab and click <em>Agree</em>.
          </li>
          <li>
            eBay then shows a "you can close this window" page. Copy the <strong>entire address bar URL</strong> of that page and paste it here:
            <div className="mt-1 flex gap-2">
              <input className="flex-1" placeholder="https://signin.ebay.com/…&code=…" value={paste} onChange={(ev) => setPaste(ev.target.value)} />
              <ActionButton kind="primary" action={() => api.post("/ebay/exchange", { value: paste })}
                onDone={() => { setPaste(""); reloadStatus(); }}>Finish connecting</ActionButton>
            </div>
          </li>
        </ol>
        {e.connected && (
          <ActionButton kind="danger" confirm="Disconnect eBay? Jobs will stop talking to eBay." action={() => api.post("/ebay/disconnect")} onDone={reloadStatus}>
            Disconnect
          </ActionButton>
        )}
      </div>
    </Card>
  );
}

function AmazonStatus({ status, reloadStatus }) {
  if (!status) return null;
  const a = status.amazon;
  return (
    <Card title="Amazon scraper">
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <Badge color={a.status === "ok" ? "green" : "red"}>{a.status === "ok" ? "OK" : `Paused until ${when(a.paused_until)}`}</Badge>
        {a.reason && <span>{a.reason}</span>}
        {a.status !== "ok" && <ActionButton action={() => api.post("/amazon/resume")} onDone={reloadStatus}>Resume now</ActionButton>}
        <ActionButton action={() => api.post("/amazon/login-browser").then(() => ({ message: "A browser window opened on this PC — log in to Amazon, then close it." }))}>
          Open Amazon browser (log in once)
        </ActionButton>
        <span className="text-xs text-slate-500">Needed for tracking and auto-buy. Your password/card are never stored by this app.</span>
      </div>
    </Card>
  );
}

function Blocklist() {
  const [rows, reload] = useLoad(() => api.get("/blocklist"), []);
  const [term, setTerm] = useState("");
  const [kind, setKind] = useState("brand");
  const [csv, setCsv] = useState("");
  const [filter, setFilter] = useState("");
  const [scan, setScan] = useState(null);
  const shown = (rows || []).filter((r) => r.term.toLowerCase().includes(filter.toLowerCase()));
  return (
    <Card title={`Brand & keyword blocklist (VeRO)${rows ? ` — ${rows.length}` : ""}`}>
      <div className="space-y-3 text-sm">
        <p className="text-xs text-slate-500">Matched against brand, title and description (whole words). The starter list is a starting point, not a complete VeRO list — review it.</p>
        <div className="flex flex-wrap gap-2">
          <input placeholder="Add brand or keyword" value={term} onChange={(e) => setTerm(e.target.value)} />
          <select value={kind} onChange={(e) => setKind(e.target.value)}><option value="brand">brand</option><option value="keyword">keyword</option></select>
          <ActionButton kind="primary" action={() => api.post("/blocklist", { term, kind })} onDone={() => { setTerm(""); reload(); }}>Add</ActionButton>
          <input placeholder="Filter list" value={filter} onChange={(e) => setFilter(e.target.value)} className="ml-auto" />
        </div>
        <div className="flex max-h-48 flex-wrap gap-1 overflow-y-auto">
          {shown.map((r) => (
            <span key={r.id} className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-xs dark:bg-slate-800">
              {r.term}{r.kind === "keyword" && <em className="text-slate-500">kw</em>}
              <button className="text-slate-500 hover:text-rose-600" onClick={async () => { await api.del(`/blocklist/${r.id}`); reload(); }}>✕</button>
            </span>
          ))}
        </div>
        <div className="flex flex-wrap items-start gap-2">
          <textarea rows={3} className="flex-1" placeholder={"Import CSV: term[,brand|keyword] per line"} value={csv} onChange={(e) => setCsv(e.target.value)} />
          <label className="cursor-pointer rounded-md border px-3 py-1.5 text-sm dark:border-slate-700">
            Choose CSV file
            <input type="file" accept=".csv,.txt" className="hidden" onChange={async (e) => setCsv(await e.target.files[0].text())} />
          </label>
          <ActionButton action={() => api.post("/blocklist/import", { csv }).then((r) => ({ message: `Imported ${r.added}` }))} onDone={() => { setCsv(""); reload(); }}>Import</ActionButton>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <ActionButton action={async () => { const r = await api.post("/blocklist/scan", { action: "flag" }); setScan(r); return { message: `${r.matches.length} match(es) flagged` }; }}>
            Scan active listings (flag)
          </ActionButton>
          <ActionButton kind="danger" confirm="End every active listing that matches the blocklist?"
            action={async () => { const r = await api.post("/blocklist/scan", { action: "end" }); setScan(r); return { message: `${r.matches.length} match(es) ended` }; }}>
            Scan & end matches
          </ActionButton>
        </div>
        {scan && scan.matches.length > 0 && (
          <ul className="list-disc pl-5 text-xs">{scan.matches.map((m) => <li key={m.listing_id}>#{m.listing_id} {m.asin}: {m.reason}</li>)}</ul>
        )}
      </div>
    </Card>
  );
}

function PricePreview({ dirty }) {
  const [price, setPrice] = useState("19.99");
  const [b, setB] = useState(null);
  useEffect(() => {
    const t = setTimeout(() => { if (Number(price) > 0) api.post("/pricing/preview", { amazon_price: Number(price) }).then(setB).catch(() => setB(null)); }, 300);
    return () => clearTimeout(t);
  }, [price, dirty]);
  return (
    <Card title="Price calculator (uses saved settings)">
      <label className="text-sm">Amazon price $ <input type="number" step="0.01" value={price} onChange={(e) => setPrice(e.target.value)} className="w-28" /></label>
      <div className="mt-3"><Breakdown b={b} /></div>
    </Card>
  );
}

export default function Settings({ status, reloadStatus }) {
  const [data, reload] = useLoad(() => api.get("/settings"), []);
  const [form, setForm] = useState(null);
  const [saved, setSaved] = useState(0);
  const [msg, setMsg] = useState(null);
  const [policies, setPolicies] = useState(null);
  const [policyErr, setPolicyErr] = useState(null);
  useEffect(() => { if (data) setForm(data.values); }, [data]);
  const byGroup = useMemo(() => {
    const g = {};
    (data?.schema || []).forEach((s) => { (g[s.group] = g[s.group] || []).push(s); });
    return g;
  }, [data]);
  const dirty = data && form && JSON.stringify(form) !== JSON.stringify(data.values);
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const save = async (patch) => {
    setMsg(null);
    try {
      const r = await api.put("/settings", patch || form);
      setForm(r.values);
      await reload();
      reloadStatus && reloadStatus();
      setSaved((n) => n + 1);
      setMsg({ ok: true, text: r.changed.length ? `Saved: ${r.changed.join(", ")}` : "No changes" });
    } catch (e) {
      setMsg({ ok: false, text: e.message });
    }
  };
  const loadPolicies = async () => {
    setPolicyErr(null);
    try { setPolicies(await api.get("/ebay/policies")); } catch (e) { setPolicyErr(e.message); }
  };
  if (!form) return <p>Loading…</p>;
  const fp = policies?.fulfillment?.find((p) => p.id === form.fulfillment_policy_id);
  const handlingMismatch = fp && fp.handling_time_days != null && Number(fp.handling_time_days) !== Number(form.handling_time_days);

  return (
    <div className="space-y-4 pb-24">
      <Card title="Mode">
        <div className="grid gap-4 sm:grid-cols-3">
          <div>
            <div className="text-sm font-medium">Dry-run mode</div>
            <div className="mt-1 flex items-center gap-2">
              <Badge color={form.dry_run ? "yellow" : "red"}>{form.dry_run ? "ON — nothing changes on eBay" : "OFF — LIVE"}</Badge>
              <Button kind={form.dry_run ? "danger" : "plain"}
                onClick={() => {
                  if (form.dry_run && !window.confirm(`Turn OFF dry-run? The app will create and change real listings on eBay ${form.ebay_environment}.`)) return;
                  save({ dry_run: !form.dry_run });
                }}>
                {form.dry_run ? "Go live" : "Turn dry-run back on"}
              </Button>
            </div>
          </div>
          <div>
            <div className="text-sm font-medium">eBay environment</div>
            <div className="mt-1 flex items-center gap-2">
              <Badge color={form.ebay_environment === "sandbox" ? "blue" : "purple"}>{form.ebay_environment}</Badge>
              <Button onClick={() => {
                const next = form.ebay_environment === "sandbox" ? "production" : "sandbox";
                if (next === "production" && !window.confirm("Switch to PRODUCTION (your real eBay store)?")) return;
                save({ ebay_environment: next });
              }}>Switch to {form.ebay_environment === "sandbox" ? "production" : "sandbox"}</Button>
            </div>
          </div>
          <div>
            <div className="text-sm font-medium">Product data source</div>
            <select className="mt-1" value={form.product_source} onChange={(e) => save({ product_source: e.target.value })}>
              {data.schema.find((s) => s.key === "product_source").choices.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
            </select>
          </div>
        </div>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <EbayConnection status={status} reloadStatus={reloadStatus} />
        <AmazonStatus status={status} reloadStatus={reloadStatus} />
      </div>

      {GROUPS.map(([g, title]) => (
        <Card key={g} title={title}
          actions={g === "listing" && <ActionButton action={loadPolicies}>Load my eBay business policies</ActionButton>}>
          {g === "listing" && policyErr && <p className="mb-2 text-sm text-rose-600">{policyErr}
            {policyErr.includes("SELLING_POLICY") || policyErr.includes("opted") ? (
              <ActionButton action={() => api.post("/ebay/opt-in-policies")} onDone={loadPolicies}>Opt in to business policies</ActionButton>) : null}
          </p>}
          {g === "listing" && handlingMismatch && (
            <p className="mb-2 text-sm text-amber-600">
              The selected shipping policy has a {fp.handling_time_days}-day handling time but your setting is {form.handling_time_days}. eBay uses the policy's value — edit the policy on eBay or change the setting.
            </p>
          )}
          {g === "listing" && fp && fp.shipping?.length > 0 && !fp.shipping.some((s) => s.free) && (
            <p className="mb-2 text-sm text-amber-600">This shipping policy charges the buyer for shipping; the pricing formula assumes free shipping.</p>
          )}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {(byGroup[g] || []).map((spec) => (
              <Field key={spec.key} spec={spec} value={form[spec.key]} onChange={(v) => set(spec.key, v)} policies={policies} />
            ))}
          </div>
          {g === "pricing" && <div className="mt-4"><PricePreview dirty={saved} /></div>}
        </Card>
      ))}

      <Blocklist />

      <div className="fixed inset-x-0 bottom-0 border-t border-slate-200 bg-white/95 p-3 dark:border-slate-800 dark:bg-slate-900/95">
        <div className="mx-auto flex max-w-7xl items-center gap-3">
          <Button kind="primary" disabled={!dirty} onClick={() => save()}>Save settings</Button>
          <Button disabled={!dirty} onClick={() => setForm(data.values)}>Discard changes</Button>
          {dirty && <span className="text-sm text-amber-600">Unsaved changes</span>}
          {msg && <span className={`text-sm ${msg.ok ? "text-emerald-600" : "text-rose-600"}`}>{msg.text}</span>}
        </div>
      </div>
    </div>
  );
}
