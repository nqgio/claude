import {
  Ban, Calculator, CheckCircle2, Circle, Cloud, Filter, Globe, LogIn, Monitor, Moon, Palette, Plug, RefreshCcw, Search, ShieldCheck,
  ShoppingCart, SlidersHorizontal, Store, Sun, Tag, Upload,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { useToast } from "../components/toast";
import { ActionButton, Badge, Breakdown, Button, Card, PageHeader, Segmented, Switch, cx, useLoad, when } from "../components/ui";
import { useTheme } from "../theme.jsx";

const GROUPS = [
  ["pricing", "Pricing engine", Calculator, "Exactly how eBay prices and the profit floor are calculated."],
  ["lister", "Product finder", Search, "What to search for and how many listings to post each day."],
  ["filters", "Product filters", Filter, "Products must pass these to be queued."],
  ["listing", "Listing defaults", Tag, "Quantity, business policies, location, promotion and listing content."],
  ["refresh", "Price & stock refresh", RefreshCcw, "Re-checks Amazon on a schedule and updates eBay."],
  ["orders", "Orders & checkout", ShoppingCart, "Assisted or automatic Amazon purchasing and its safeguards."],
  ["amazon", "Amazon scraper", Globe, "How politely the app reads Amazon pages."],
];
const NAV = [
  ["mode", "Mode", SlidersHorizontal], ["connections", "Connections", Plug], ...GROUPS.map(([k, l, i]) => [k, l, i]),
  ["blocklist", "Blocklist", Ban], ["appearance", "Appearance", Palette],
];
const POLICY_KEYS = { fulfillment_policy_id: "fulfillment", return_policy_id: "return", payment_policy_id: "payment" };

function Field({ spec, value, onChange, policies }) {
  const id = `f-${spec.key}`;
  if (spec.type === "bool") {
    return (
      <div className="flex items-start justify-between gap-4 rounded-lg border border-line bg-surface-2 px-3.5 py-3 sm:col-span-2 lg:col-span-1">
        <label htmlFor={id} className="min-w-0 cursor-pointer">
          <div className="text-[13px] font-medium text-ink">{spec.label}</div>
          {spec.help && <p className="mt-0.5 text-xs text-ink-3">{spec.help}</p>}
        </label>
        <Switch id={id} checked={!!value} onChange={onChange} label={spec.label} />
      </div>
    );
  }
  let input;
  if (POLICY_KEYS[spec.key] && policies) {
    const list = policies[POLICY_KEYS[spec.key]] || [];
    input = (
      <select id={id} value={value || ""} onChange={(e) => onChange(e.target.value)} className="w-full">
        <option value="">Choose a policy…</option>
        {list.map((p) => (
          <option key={p.id} value={p.id}>{p.name}{p.handling_time_days != null ? ` · ${p.handling_time_days}-day handling` : ""}</option>
        ))}
      </select>
    );
  } else if (spec.type === "choice") {
    input = (
      <select id={id} value={value} onChange={(e) => onChange(e.target.value)} className="w-full">
        {spec.choices.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
      </select>
    );
  } else if (spec.type === "text") {
    input = <textarea id={id} rows={7} className="w-full font-mono text-xs" value={value || ""} onChange={(e) => onChange(e.target.value)} placeholder="Leave blank to use the built-in layout" />;
  } else if (spec.type === "list") {
    input = <textarea id={id} rows={4} className="w-full" value={(value || []).join("\n")} onChange={(e) => onChange(e.target.value.split("\n"))} placeholder="One per line" />;
  } else {
    const numeric = ["float", "int", "optional_float"].includes(spec.type);
    input = (
      <input id={id} className="w-full" type={spec.type === "time" ? "time" : numeric ? "number" : "text"} step={spec.type === "int" ? 1 : "any"}
        value={value ?? ""} onChange={(e) => onChange(e.target.value)} placeholder={spec.type === "optional_float" ? "Off" : undefined} />
    );
  }
  const wide = spec.type === "text" ? "sm:col-span-2 lg:col-span-3" : spec.type === "list" ? "sm:col-span-2 lg:col-span-1" : "";
  return (
    <div className={wide}>
      <label htmlFor={id} className="mb-1.5 block text-[12.5px] font-medium text-ink">{spec.label}</label>
      {input}
      {spec.help && <p className="mt-1.5 text-xs leading-4 text-ink-3">{spec.help}</p>}
    </div>
  );
}

function Step({ done, children }) {
  return (
    <li className="flex gap-3">
      {done ? <CheckCircle2 className="mt-0.5 h-4.5 w-4.5 shrink-0 text-emerald-500" /> : <Circle className="mt-0.5 h-4.5 w-4.5 shrink-0 text-ink-3" />}
      <div className="min-w-0 flex-1 text-[13px]">{children}</div>
    </li>
  );
}

function Connections({ status, reloadStatus }) {
  const [paste, setPaste] = useState("");
  if (!status) return null;
  const e = status.ebay;
  const a = status.amazon;
  return (
    <div className="grid gap-6 xl:grid-cols-2">
      <Card title={`eBay · ${status.environment}`} icon={Store} actions={<Badge color={e.connected ? "green" : "yellow"} dot>{e.connected ? "Connected" : "Not connected"}</Badge>}>
        <ol className="space-y-4">
          <Step done={e.keys_present && e.runame_present}>
            <div className="font-medium">Keys in <code className="rounded bg-surface-3 px-1 text-xs">.env</code></div>
            <div className="mt-1 flex flex-wrap gap-1.5">
              <Badge color={e.keys_present ? "green" : "red"}>App ID / Cert ID</Badge>
              <Badge color={e.runame_present ? "green" : "red"}>RuName</Badge>
            </div>
          </Step>
          <Step done={e.connected}>
            <div className="font-medium">Sign in to eBay</div>
            <p className="mt-0.5 text-xs text-ink-3">Opens eBay in a new tab. Sign in and click Agree.</p>
            <div className="mt-2">
              <ActionButton kind="primary" icon={LogIn} action={async () => { const r = await api.get("/ebay/connect-url"); window.open(r.url, "_blank"); }}>
                Connect eBay
              </ActionButton>
            </div>
          </Step>
          <Step done={e.connected}>
            <div className="font-medium">Paste the page address</div>
            <p className="mt-0.5 text-xs text-ink-3">After agreeing, copy the whole address bar of eBay's "you can close this window" page.</p>
            <div className="mt-2 flex gap-2">
              <input className="min-w-0 flex-1" placeholder="https://signin.ebay.com/…&code=…" value={paste} onChange={(ev) => setPaste(ev.target.value)} />
              <ActionButton action={() => api.post("/ebay/exchange", { value: paste })} onDone={() => { setPaste(""); reloadStatus(); }} success="eBay connected">
                Finish
              </ActionButton>
            </div>
          </Step>
        </ol>
        <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4 text-xs text-ink-3">
          <span>
            {e.refresh_token_expires ? `Token valid until ${when(e.refresh_token_expires)}` : "No token yet"} ·{" "}
            Account-deletion endpoint {status.deletion_endpoint_configured ? "configured" : "not configured (needed for production)"}
          </span>
          {e.connected && (
            <ActionButton size="sm" kind="danger-soft" confirm="Disconnect eBay? Jobs will stop talking to eBay." action={() => api.post("/ebay/disconnect")} onDone={reloadStatus}>
              Disconnect
            </ActionButton>
          )}
        </div>
      </Card>
      <Card title="Amazon" icon={Cloud} actions={<Badge color={a.status === "ok" ? "green" : "red"} dot>{a.status === "ok" ? "Healthy" : "Paused"}</Badge>}>
        {a.status !== "ok" && (
          <div className="mb-4 rounded-lg border border-rose-200 bg-rose-50 p-3 text-[13px] text-rose-800 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-200">
            Paused until {when(a.paused_until)}: {a.reason}
            <div className="mt-2"><ActionButton size="sm" action={() => api.post("/amazon/resume")} onDone={reloadStatus} success="Resumed">Resume now</ActionButton></div>
          </div>
        )}
        <ol className="space-y-4">
          <Step done={a.profile_exists}>
            <div className="font-medium">Log in once</div>
            <p className="mt-0.5 text-xs text-ink-3">
              Needed for tracking and auto-buy. A browser window opens on this PC. Log in, tick "Keep me signed in", then close it.
              Your password and card are never stored by this app.
            </p>
            <div className="mt-2">
              <ActionButton icon={LogIn} action={() => api.post("/amazon/login-browser")} success="A browser window opened on this PC">Open Amazon browser</ActionButton>
            </div>
          </Step>
          <Step done={a.status === "ok"}>
            <div className="font-medium">CAPTCHA protection</div>
            <p className="mt-0.5 text-xs text-ink-3">If Amazon shows a robot check, Amazon jobs pause for the cooldown below. The app never tries to get past it.</p>
          </Step>
        </ol>
      </Card>
    </div>
  );
}

function Blocklist() {
  const [rows, reload] = useLoad(() => api.get("/blocklist"), []);
  const [term, setTerm] = useState("");
  const [kind, setKind] = useState("brand");
  const [csv, setCsv] = useState("");
  const [filter, setFilter] = useState("");
  const [scan, setScan] = useState(null);
  const toast = useToast();
  const shown = (rows || []).filter((r) => r.term.toLowerCase().includes(filter.toLowerCase()));
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap gap-2">
        <input placeholder="Brand or keyword" value={term} onChange={(e) => setTerm(e.target.value)} className="w-56" />
        <Segmented value={kind} onChange={setKind} options={[["brand", "Brand"], ["keyword", "Keyword"]]} />
        <ActionButton kind="primary" action={() => api.post("/blocklist", { term, kind })} onDone={() => { setTerm(""); reload(); }} success="Added">Add</ActionButton>
        <input placeholder="Filter…" value={filter} onChange={(e) => setFilter(e.target.value)} className="ml-auto w-44" />
      </div>
      <div className="flex max-h-52 flex-wrap gap-1.5 overflow-y-auto rounded-lg border border-line bg-surface-2 p-3">
        {shown.map((r) => (
          <span key={r.id} className="inline-flex items-center gap-1 rounded-md bg-surface py-0.5 pr-1 pl-2 text-xs ring-1 ring-line">
            {r.term}
            {r.kind === "keyword" && <span className="text-[10px] text-ink-3 uppercase">kw</span>}
            <button className="rounded px-1 text-ink-3 hover:bg-rose-50 hover:text-rose-600 dark:hover:bg-rose-500/10" aria-label={`Remove ${r.term}`}
              onClick={async () => { await api.del(`/blocklist/${r.id}`); reload(); }}>×</button>
          </span>
        ))}
        {rows && shown.length === 0 && <span className="text-xs text-ink-3">No matches.</span>}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-lg border border-line p-3.5">
          <div className="mb-2 text-[12.5px] font-medium">Import CSV</div>
          <textarea rows={3} className="w-full" placeholder={"Nike\nreplica,keyword"} value={csv} onChange={(e) => setCsv(e.target.value)} />
          <div className="mt-2 flex gap-2">
            <label className="inline-flex h-9 cursor-pointer items-center gap-2 rounded-lg border border-line bg-surface px-3 text-[13px] font-medium hover:bg-surface-3">
              <Upload className="h-4 w-4" /> Choose file
              <input type="file" accept=".csv,.txt" className="hidden" onChange={async (e) => setCsv(await e.target.files[0].text())} />
            </label>
            <ActionButton action={async () => { const r = await api.post("/blocklist/import", { csv }); return { message: `Imported ${r.added} term(s)` }; }}
              onDone={() => { setCsv(""); reload(); }} disabled={!csv}>Import</ActionButton>
          </div>
        </div>
        <div className="rounded-lg border border-line p-3.5">
          <div className="mb-1 text-[12.5px] font-medium">Scan active listings</div>
          <p className="mb-3 text-xs text-ink-3">Checks every live listing's brand, title and description against the list.</p>
          <div className="flex flex-wrap gap-2">
            <ActionButton icon={ShieldCheck} action={async () => { const r = await api.post("/blocklist/scan", { action: "flag" }); setScan(r); return { message: `${r.matches.length} match(es) flagged` }; }}>
              Scan & flag
            </ActionButton>
            <ActionButton kind="danger-soft" confirm="End every active listing that matches the blocklist?"
              action={async () => { const r = await api.post("/blocklist/scan", { action: "end" }); setScan(r); toast(`${r.matches.length} match(es) ended`); }}>
              Scan & end
            </ActionButton>
          </div>
          {scan && scan.matches.length > 0 && (
            <ul className="mt-3 space-y-1 text-xs text-ink-2">{scan.matches.map((m) => <li key={m.listing_id}>#{m.listing_id} {m.asin}: {m.reason}</li>)}</ul>
          )}
        </div>
      </div>
      <p className="text-xs text-ink-3">The starter list is a starting point, not a complete VeRO list. Matching is whole-word and case-insensitive.</p>
    </div>
  );
}

function PricePreview({ saved }) {
  const [price, setPrice] = useState("19.99");
  const [b, setB] = useState(null);
  useEffect(() => {
    const t = setTimeout(() => {
      if (Number(price) > 0) api.post("/pricing/preview", { amazon_price: Number(price) }).then(setB).catch(() => setB(null));
    }, 250);
    return () => clearTimeout(t);
  }, [price, saved]);
  return (
    <div className="rounded-xl border border-line bg-surface-2 p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-[13px] font-semibold">Price calculator</div>
          <div className="text-xs text-ink-3">Uses your saved settings</div>
        </div>
        <label className="flex items-center gap-2 text-[13px] text-ink-2">
          Amazon price
          <span className="relative">
            <span className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-ink-3">$</span>
            <input type="number" step="0.01" value={price} onChange={(e) => setPrice(e.target.value)} className="w-28 !pl-6" />
          </span>
        </label>
      </div>
      <Breakdown b={b} />
    </div>
  );
}

function Appearance() {
  const { theme, setTheme } = useTheme();
  const opts = [["light", "Light", Sun], ["dark", "Dark", Moon], ["system", "Match system", Monitor]];
  return (
    <div className="grid gap-3 sm:grid-cols-3">
      {opts.map(([v, label, Icon]) => (
        <button key={v} onClick={() => setTheme(v)}
          className={cx("flex items-center gap-3 rounded-xl border p-4 text-left transition",
            theme === v ? "border-accent bg-accent-soft ring-4 ring-accent/10" : "border-line hover:bg-surface-2")}>
          <span className={cx("grid h-9 w-9 place-items-center rounded-lg", theme === v ? "bg-accent text-white" : "bg-surface-3 text-ink-2")}>
            <Icon className="h-4.5 w-4.5" />
          </span>
          <span className="text-[13px] font-medium">{label}</span>
        </button>
      ))}
    </div>
  );
}

export default function Settings({ status, reloadStatus }) {
  const [data, reload] = useLoad(() => api.get("/settings"), []);
  const [form, setForm] = useState(null);
  const [saved, setSaved] = useState(0);
  const [policies, setPolicies] = useState(null);
  const toast = useToast();
  useEffect(() => {
    if (data) setForm(data.values);
  }, [data]);
  const byGroup = useMemo(() => {
    const g = {};
    (data?.schema || []).forEach((s) => (g[s.group] = g[s.group] || []).push(s));
    return g;
  }, [data]);
  const dirty = data && form && JSON.stringify(form) !== JSON.stringify(data.values);
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const save = async (patch) => {
    try {
      const r = await api.put("/settings", patch || form);
      setForm(r.values);
      await reload();
      reloadStatus && reloadStatus();
      setSaved((n) => n + 1);
      toast(r.changed.length ? `Saved ${r.changed.length} setting${r.changed.length > 1 ? "s" : ""}` : "No changes to save");
    } catch (e) {
      toast(e.message, "error");
    }
  };
  const loadPolicies = async () => {
    try {
      setPolicies(await api.get("/ebay/policies"));
      return { message: "Policies loaded from eBay" };
    } catch (e) {
      if (/SELLING_POLICY|opted|business polic/i.test(e.message)) throw new Error(`${e.message}. Use “Opt in to business policies”, then try again.`);
      throw e;
    }
  };
  if (!form) return <PageHeader title="Settings" description="Loading…" />;
  const fp = policies?.fulfillment?.find((p) => p.id === form.fulfillment_policy_id);
  const handlingMismatch = fp && fp.handling_time_days != null && Number(fp.handling_time_days) !== Number(form.handling_time_days);
  const sourceSpec = data.schema.find((s) => s.key === "product_source");

  return (
    <div className="pb-24">
      <PageHeader title="Settings" description="Everything the app does is controlled here. Changes apply as soon as you save." />
      <div className="grid gap-8 lg:grid-cols-[190px_1fr]">
        <nav className="hidden lg:block">
          <div className="sticky top-8 space-y-0.5">
            {NAV.map(([id, label, Icon]) => (
              <a key={id} href={`#${id}`} className="flex h-8 items-center gap-2.5 rounded-lg px-2.5 text-[13px] text-ink-2 hover:bg-surface-3 hover:text-ink">
                <Icon className="h-3.5 w-3.5 text-ink-3" /> {label}
              </a>
            ))}
          </div>
        </nav>
        <div className="min-w-0 space-y-6">
          <section id="mode" className="scroll-mt-6">
            <div className="grid gap-4 md:grid-cols-3">
              <div className={cx("card p-4", form.dry_run ? "" : "ring-2 ring-rose-500/40")}>
                <div className="flex items-center justify-between">
                  <span className="text-[12.5px] font-medium text-ink-2">Dry-run mode</span>
                  <Switch checked={form.dry_run} label="Dry-run mode"
                    onChange={(v) => {
                      if (!v && !window.confirm(`Turn OFF dry-run? The app will create and change real listings on eBay ${form.ebay_environment}.`)) return;
                      save({ dry_run: v });
                    }} />
                </div>
                <div className="mt-2 text-[17px] font-semibold">{form.dry_run ? "On, safe" : "Off, live"}</div>
                <p className="mt-1 text-xs text-ink-3">{form.dry_run ? "Finds, prices and previews. Nothing changes on eBay." : "The app is creating and updating real listings."}</p>
              </div>
              <div className="card p-4">
                <span className="text-[12.5px] font-medium text-ink-2">eBay environment</span>
                <div className="mt-2.5">
                  <Segmented value={form.ebay_environment} options={[["sandbox", "Sandbox"], ["production", "Production"]]}
                    onChange={(v) => {
                      if (v === form.ebay_environment) return;
                      if (v === "production" && !window.confirm("Switch to PRODUCTION (your real eBay store)?")) return;
                      save({ ebay_environment: v });
                    }} />
                </div>
                <p className="mt-2 text-xs text-ink-3">Test on the sandbox first, then switch with one click.</p>
              </div>
              <div className="card p-4">
                <span className="text-[12.5px] font-medium text-ink-2">Product data source</span>
                <select className="mt-2.5 w-full" value={form.product_source} onChange={(e) => save({ product_source: e.target.value })}>
                  {sourceSpec.choices.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
                </select>
                <p className="mt-2 text-xs text-ink-3">Sample data never contacts Amazon.</p>
              </div>
            </div>
          </section>

          <section id="connections" className="scroll-mt-6"><Connections status={status} reloadStatus={reloadStatus} /></section>

          {GROUPS.map(([g, title, Icon, desc]) => (
            <section key={g} id={g} className="scroll-mt-6">
              <Card title={title} description={desc} icon={Icon}
                actions={g === "listing" && (
                  <>
                    <ActionButton size="sm" action={() => api.post("/ebay/opt-in-policies")} success="Opted in to business policies">Opt in to business policies</ActionButton>
                    <ActionButton size="sm" kind="primary" action={loadPolicies}>Load my policies</ActionButton>
                  </>
                )}>
                {g === "listing" && handlingMismatch && (
                  <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-[12.5px] text-amber-900 dark:border-amber-500/25 dark:bg-amber-500/10 dark:text-amber-200">
                    The selected shipping policy has a {fp.handling_time_days}-day handling time, but your setting is {form.handling_time_days}. eBay uses the policy's value.
                  </div>
                )}
                {g === "listing" && fp && fp.shipping?.length > 0 && !fp.shipping.some((s) => s.free) && (
                  <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-[12.5px] text-amber-900 dark:border-amber-500/25 dark:bg-amber-500/10 dark:text-amber-200">
                    This shipping policy charges the buyer for shipping, but the pricing formula assumes free shipping.
                  </div>
                )}
                <div className="grid gap-x-5 gap-y-5 sm:grid-cols-2 lg:grid-cols-3">
                  {(byGroup[g] || []).map((spec) => (
                    <Field key={spec.key} spec={spec} value={form[spec.key]} onChange={(v) => set(spec.key, v)} policies={policies} />
                  ))}
                </div>
                {g === "pricing" && <div className="mt-6"><PricePreview saved={saved} /></div>}
              </Card>
            </section>
          ))}

          <section id="blocklist" className="scroll-mt-6">
            <Card title="Brand & keyword blocklist" description="VeRO protection: matching products are skipped with a logged reason." icon={Ban}>
              <div className="mb-5 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
                {(byGroup.blocklist || []).map((spec) => <Field key={spec.key} spec={spec} value={form[spec.key]} onChange={(v) => set(spec.key, v)} />)}
              </div>
              <Blocklist />
            </Card>
          </section>

          <section id="appearance" className="scroll-mt-6">
            <Card title="Appearance" description="Saved in this browser." icon={Palette}><Appearance /></Card>
          </section>
        </div>
      </div>

      {dirty && (
        <div className="anim-pop fixed inset-x-0 bottom-4 z-40 flex justify-center px-4 lg:pl-60">
          <div className="card flex items-center gap-3 py-2.5 pr-2.5 pl-4 shadow-xl">
            <span className="h-2 w-2 rounded-full bg-amber-500" />
            <span className="text-[13px] font-medium">You have unsaved changes</span>
            <Button size="sm" kind="ghost" onClick={() => setForm(data.values)}>Discard</Button>
            <Button size="sm" kind="primary" onClick={() => save()}>Save changes</Button>
          </div>
        </div>
      )}
    </div>
  );
}
