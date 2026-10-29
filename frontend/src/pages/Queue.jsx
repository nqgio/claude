import { CheckCircle2, CircleStop, ChevronLeft, ChevronRight, Clock, ExternalLink, Eye, ListOrdered, Loader2, Plus, Send, Sparkles, Trash2 } from "lucide-react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useState } from "react";
import { api } from "../api";
import { useToast } from "../components/toast";
import {
  ActionButton, Badge, Breakdown, Button, Card, EmptyState, Modal, PageHeader, StatusBadge, Switch, Table, Thumb, clock, cx, money, useLoad,
} from "../components/ui";

export default function Queue() {
  const [params, setParams] = useSearchParams();
  const day = params.get("day"); // null = today
  const setDay = (d) => setParams(d ? { day: d } : {});
  const [data, reload] = useLoad(() => api.get(`/queue${day ? `?day=${day}` : ""}`), [day], 4000);
  const isToday = !day || (data && data.date === data.today);
  const days = data?.days || [];
  const idx = data ? days.indexOf(data.date) : -1;
  const older = data && (idx >= 0 ? days[idx + 1] : days.find((d) => d < data.date));
  const newer = data && !isToday && (idx > 0 ? days[idx - 1] : null);
  const nice = (d) => new Date(`${d}T00:00:00`).toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" });
  const build = data?.build || {};
  const [asin, setAsin] = useState("");
  const [force, setForce] = useState(false);
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState(null);
  const toast = useToast();
  const nav = useNavigate();
  const posted = data?.posted_today || 0;
  const target = data?.listings_per_day || 0;
  const cols = [
    {
      key: "scheduled_at", label: "Posts at",
      render: (r) => (r.scheduled_at ? <span className="inline-flex items-center gap-1.5 font-medium whitespace-nowrap"><Clock className="h-3.5 w-3.5 text-ink-3" />{clock(r.scheduled_at)}</span> : <span className="text-ink-3">—</span>),
    },
    {
      key: "title", label: "Product", className: "min-w-[300px]",
      render: (r) => (
        <div className="flex items-center gap-3">
          <Thumb src={(r.preview?.images || [])[0]} />
          <div className="min-w-0">
            <div className="line-clamp-1 font-medium">{r.title}</div>
            <div className="mt-0.5 flex items-center gap-1.5 text-xs text-ink-3">
              <span className="font-mono">{r.asin}</span>
              {r.source === "manual" && <Badge color="indigo">Manual</Badge>}
              {r.search_term && <span className="truncate">· {r.search_term}</span>}
            </div>
          </div>
        </div>
      ),
    },
    { key: "amazon_price", label: "Amazon", align: "right", render: (r) => money(r.amazon_price) },
    { key: "ebay_price", label: "eBay", align: "right", render: (r) => <span className="font-medium">{money(r.ebay_price)}</span> },
    { key: "expected_profit", label: "Profit", align: "right", render: (r) => <span className="font-medium text-emerald-600 dark:text-emerald-400">{money(r.expected_profit)}</span> },
    {
      key: "status", label: "Status",
      render: (r) => (
        <div className="max-w-[220px]">
          <StatusBadge status={r.status} />
          {r.message && <div className="mt-1 line-clamp-2 text-xs text-ink-3" title={r.message}>{r.message}</div>}
        </div>
      ),
    },
    {
      key: "act", label: "", sortable: false,
      render: (r) => (
        <div className="flex justify-end gap-1.5" onClick={(e) => e.stopPropagation()}>
          <Button size="sm" kind="ghost" icon={Eye} onClick={() => setPreview(r)}>Preview</Button>
          {r.listing_id && <Button size="sm" kind="ghost" icon={ExternalLink} onClick={() => nav(`/listings/${r.listing_id}`)}>Listing</Button>}
          {["queued", "scheduled"].includes(r.status) && (
            <>
              <ActionButton size="sm" icon={Send} action={() => api.post(`/queue/${r.id}/post-now`)} onDone={() => setTimeout(reload, 3000)} success="Posting now">
                Post
              </ActionButton>
              <ActionButton size="sm" kind="ghost" icon={Trash2} action={() => api.del(`/queue/${r.id}`)} onDone={reload} title="Remove" />
            </>
          )}
        </div>
      ),
    },
  ];
  return (
    <>
      <PageHeader
        title="Queue"
        description={data ? (isToday ? `Today's products, posted at random times between ${data.window[0]} and ${data.window[1]}.`
          : `Queue for ${nice(data.date)}. Posted items are on the Listings page; anything not posted that day moved to the next day's queue.`) : "Today's products."}
        actions={
          <>
          <div className="flex items-center gap-1 rounded-lg border border-line bg-surface p-0.5 shadow-xs">
            <Button size="sm" kind="ghost" icon={ChevronLeft} disabled={!older} onClick={() => setDay(older)} title="Earlier day" />
            <span className="min-w-[96px] px-1 text-center text-[12.5px] font-medium">{data ? (isToday ? "Today" : nice(data.date)) : "…"}</span>
            <Button size="sm" kind="ghost" icon={ChevronRight} disabled={isToday} onClick={() => setDay(newer && newer !== data?.today ? newer : null)} title="Later day" />
          </div>
          {build.running ? (
            <ActionButton kind="danger-soft" icon={CircleStop} action={() => api.post("/queue/stop")} onDone={() => setTimeout(reload, 1000)}>
              Stop search
            </ActionButton>
          ) : (
            <ActionButton kind="primary" icon={Sparkles} action={() => api.post("/queue/build")} onDone={() => setTimeout(reload, 1000)}>
              Build queue now
            </ActionButton>
          )}
          </>
        }
      />
      {isToday && <BuildProgress build={build} onStop={async () => { await api.post("/queue/stop"); setTimeout(reload, 1000); }} />}
      {isToday && (
      <div className="mb-6 grid gap-4 md:grid-cols-3">
        <div className="card p-4 md:col-span-1">
          <div className="text-[12px] font-medium text-ink-2">Posted today</div>
          <div className="tnum mt-1 text-[24px] font-semibold tracking-tight">{posted}<span className="text-base text-ink-3"> / {target}</span></div>
          <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-surface-3">
            <div className="h-full rounded-full bg-accent transition-all" style={{ width: `${target ? Math.min(100, (posted / target) * 100) : 0}%` }} />
          </div>
          {data?.dry_run_posted_today > 0 && (
            <div className="mt-2 text-xs text-ink-3">+ {data.dry_run_posted_today} dry-run preview{data.dry_run_posted_today > 1 ? "s" : ""} (don't count)</div>
          )}
        </div>
        <form
          className="card flex flex-col justify-center gap-3 p-4 md:col-span-2"
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            try {
              const r = await api.post("/queue", { asin, force });
              toast(r.message, "info");
              setAsin("");
              setTimeout(reload, 4000);
            } catch (err) {
              toast(err.message, "error");
            } finally {
              setBusy(false);
            }
          }}
        >
          <div className="text-[12px] font-medium text-ink-2">Add a product by ASIN</div>
          <div className="flex flex-wrap items-center gap-3">
            <input placeholder="B0ABC12345" value={asin} onChange={(e) => setAsin(e.target.value)} className="w-56 font-mono uppercase" />
            <Button kind="primary" type="submit" icon={Plus} busy={busy} disabled={!asin}>Add</Button>
            <label className="flex items-center gap-2 text-[13px] text-ink-2" title="Skips price/rating/review/Prime/shipping filters. Stock, blocklist and profit floor still apply.">
              <Switch checked={force} onChange={setForce} label="Ignore search filters" /> Ignore search filters
            </label>
          </div>
        </form>
      </div>
      )}
      <Card padded={false}>
        <Table columns={cols} rows={data?.items} loading onRowClick={setPreview}
          empty={<EmptyState icon={ListOrdered} title={isToday ? "The queue is empty" : "Nothing was queued that day"}
            text={isToday ? "It's built every day at your queue build time, or press “Build queue now”. While it builds, progress shows above." : "Use the arrows to look at another day."} />} />
      </Card>
      <Modal open={!!preview} onClose={() => setPreview(null)} title="Listing preview" subtitle={preview && `${preview.asin} · written by the ${preview.preview?.writer || "built-in"} writer`} wide>
        {preview && <Preview item={preview} />}
      </Modal>
    </>
  );
}

function Preview({ item }) {
  const p = item.preview || {};
  return (
    <div className="space-y-5">
      <div>
        <div className="flex items-center justify-between text-xs text-ink-3">
          <span>eBay title</span>
          <span className="tnum">{(p.title || "").length}/80</span>
        </div>
        <div className="mt-1 rounded-lg border border-line bg-surface-2 px-3 py-2 text-[15px] font-semibold">{p.title}</div>
        <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-ink-3">
          Category: <span className="text-ink-2">{p.category_name || p.category_note || "—"}</span>
          {p.missing_required_aspects?.length > 0 && <Badge color="yellow">Missing required specifics: {p.missing_required_aspects.join(", ")}</Badge>}
        </div>
      </div>
      {(p.images || []).length > 0 && (
        <div className="flex gap-2 overflow-x-auto pb-1">
          {p.images.map((u) => <Thumb key={u} src={u} size="h-20 w-20" />)}
        </div>
      )}
      <div className="grid gap-5 md:grid-cols-2">
        <div>
          <h4 className="mb-2 text-[13px] font-semibold">Price breakdown</h4>
          <Breakdown b={item.breakdown} />
        </div>
        <div>
          <h4 className="mb-2 text-[13px] font-semibold">Item specifics</h4>
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(p.aspects || {}).map(([k, v]) => <Badge key={k}><span className="text-ink-3">{k}</span> {v.join(", ")}</Badge>)}
          </div>
          {p.product?.url && <a className="mt-4 inline-block text-[13px] font-medium text-accent-ink hover:underline" href={p.product.url} target="_blank" rel="noreferrer">View on Amazon ↗</a>}
        </div>
      </div>
      <div>
        <h4 className="mb-2 text-[13px] font-semibold">Description</h4>
        <iframe title="description" sandbox="" className="h-80 w-full rounded-lg border border-line bg-white" srcDoc={p.description_html} />
      </div>
    </div>
  );
}


function BuildProgress({ build, onStop }) {
  if (!build.running && !build.result) return null;
  const pct = build.target ? Math.min(100, ((build.have + build.added) / build.target) * 100) : 0;
  if (!build.running) {
    return (
      <div className="card mb-6 flex flex-wrap items-center gap-3 px-4 py-3 text-[13px]">
        <CheckCircle2 className="h-4.5 w-4.5 shrink-0 text-emerald-500" />
        <span className="flex-1"><strong className="font-semibold">Last queue build:</strong> {build.result}</span>
        <Link to="/activity" className="text-[12.5px] font-medium text-accent-ink hover:underline">See details in the Activity log →</Link>
      </div>
    );
  }
  return (
    <div className="card mb-6 border-accent/40 p-4">
      <div className="flex flex-wrap items-center gap-3">
        <Loader2 className="h-4.5 w-4.5 shrink-0 animate-spin text-accent" />
        <div className="min-w-0 flex-1">
          <div className="text-[13px] font-semibold">Building the queue…</div>
          <div className={cx("mt-0.5 text-xs", build.waiting ? "font-medium text-amber-700 dark:text-amber-300" : "truncate text-ink-2")}>
            {build.step || "Starting…"}
          </div>
        </div>
        <Button size="sm" kind="danger-soft" icon={CircleStop} onClick={onStop} disabled={build.step === "Stopping…"}>
          {build.step === "Stopping…" ? "Stopping…" : "Stop"}
        </Button>
        <div className="text-right text-[12.5px] text-ink-2">
          <div><strong className="tnum text-ink">{build.added}</strong>{build.target ? ` of ${build.target - build.have}` : ""} added</div>
          <div className="tnum text-xs text-ink-3">{build.examined} product{build.examined === 1 ? "" : "s"} checked</div>
        </div>
      </div>
      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-surface-3">
        <div className="h-full rounded-full bg-accent transition-all" style={{ width: `${Math.max(pct, 3)}%` }} />
      </div>
      <p className="mt-2 text-xs text-ink-3">
        Amazon pages are read slowly on purpose, so this can take an hour or more. You can leave this page; it keeps going.
        Want to change settings first? Press Stop (products found so far are kept), change Settings, then Build queue now again.
        Each product found or skipped (and why) is listed in the <Link to="/activity" className="text-accent-ink hover:underline">Activity log</Link>.
      </p>
    </div>
  );
}
