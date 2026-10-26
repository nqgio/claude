import { Bot, Cloud, Hand, LogIn, Plus, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api";
import { useToast } from "./toast";
import { ActionButton, Badge, Button, Card, Segmented, Switch, cx, money, useLoad, when } from "./ui";

/** Manual ↔ automatic Amazon ordering switch (saves immediately). */
export function OrderingToggle({ status, reloadStatus, onChanged }) {
  const toast = useToast();
  if (!status) return null;
  const change = async (mode) => {
    if (mode === status.checkout_mode) return;
    if (mode === "auto") {
      const none = !status.amazon.accounts_logged_in;
      const msg = "Turn on AUTOMATIC ordering?\n\nThe app will buy each new eBay order on Amazon with your Amazon accounts "
        + "(using your saved card), as long as it's profitable and within your limits."
        + (none ? "\n\nNote: no Amazon account is logged in yet, so orders will be flagged for you until you log one in." : "")
        + (status.dry_run ? "\n\nDry-run is on, so for now it will only log what it would buy." : "");
      if (!window.confirm(msg)) return;
    }
    try {
      await api.put("/settings", { checkout_mode: mode });
      toast(mode === "auto" ? "Automatic ordering is on" : "Manual ordering is on. You'll buy each order yourself.");
      reloadStatus && reloadStatus();
      onChanged && onChanged(mode);
    } catch (e) {
      toast(e.message, "error");
    }
  };
  return (
    <Segmented value={status.checkout_mode} onChange={change}
      options={[["assisted", "Manual", Hand], ["auto", "Automatic", Bot]]} />
  );
}

function LimitInput({ value, onSave, prefix, placeholder }) {
  const [v, setV] = useState(value ?? "");
  useEffect(() => {
    setV(value ?? "");
  }, [value]);
  return (
    <span className="relative inline-block">
      {prefix && <span className="pointer-events-none absolute top-1/2 left-2.5 -translate-y-1/2 text-xs text-ink-3">{prefix}</span>}
      <input type="number" min="0" step={prefix ? "0.01" : "1"} value={v} placeholder={placeholder}
        onChange={(e) => setV(e.target.value)} onBlur={() => String(v) !== String(value ?? "") && onSave(v)}
        onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()}
        className={cx("!h-8 w-24 text-xs", prefix && "!pl-5")} />
    </span>
  );
}

export default function AmazonAccounts({ status, reloadStatus, bare = false }) {
  const [data, reload] = useLoad(() => api.get("/amazon/accounts"), [], 15000);
  const [name, setName] = useState("");
  const toast = useToast();
  const a = status?.amazon;
  const patch = async (id, values) => {
    try {
      await api.patch(`/amazon/accounts/${id}`, values);
      reload();
    } catch (e) {
      toast(e.message, "error");
    }
  };
  const loginBadge = (acc) =>
    acc.logged_in === true ? <Badge color="green" dot>Logged in</Badge>
      : acc.logged_in === false ? <Badge color="red" dot>Not logged in</Badge>
      : <Badge color="gray" dot>Not checked</Badge>;
  const body = (
    <>
      {a && a.status !== "ok" && (
        <div className="mb-4 flex flex-wrap items-center gap-3 rounded-lg border border-rose-200 bg-rose-50 p-3 text-[13px] text-rose-800 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-200">
          <span className="flex-1">Amazon jobs paused until {when(a.paused_until)}: {a.reason}</span>
          <ActionButton size="sm" action={() => api.post("/amazon/resume")} onDone={reloadStatus} success="Resumed">Resume now</ActionButton>
        </div>
      )}
      <div className="space-y-3">
        {(data?.accounts || []).map((acc) => (
          <div key={acc.id} className={cx("rounded-xl border p-3.5", data.next_account_id === acc.id ? "border-accent/50 bg-accent-soft/40" : "border-line")}>
            <div className="flex flex-wrap items-center gap-2">
              <input defaultValue={acc.name} onBlur={(e) => e.target.value !== acc.name && patch(acc.id, { name: e.target.value })}
                className="!h-8 w-44 font-medium" aria-label="Account name" />
              {loginBadge(acc)}
              {data.next_account_id === acc.id && <Badge color="indigo">Next in rotation</Badge>}
              <span className="ml-auto text-xs text-ink-3">{acc.orders_today} order{acc.orders_today === 1 ? "" : "s"} · {money(acc.spend_today)} today</span>
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2.5 text-[12.5px] text-ink-2">
              <label className="flex items-center gap-2"><Switch checked={acc.enabled} onChange={(v) => patch(acc.id, { enabled: v })} label="Enabled" /> Enabled</label>
              <label className="flex items-center gap-2"><Switch checked={acc.buys_orders} onChange={(v) => patch(acc.id, { buys_orders: v })} label="Buys orders" /> Buys orders</label>
              <span className="flex items-center gap-2">Max orders/day <LimitInput value={acc.max_orders_per_day} placeholder="No limit" onSave={(v) => patch(acc.id, { max_orders_per_day: v })} /></span>
              <span className="flex items-center gap-2">Max spend/day <LimitInput value={acc.max_spend_per_day} prefix="$" placeholder="No limit" onSave={(v) => patch(acc.id, { max_spend_per_day: v })} /></span>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              <ActionButton size="sm" kind="primary" icon={LogIn} action={() => api.post(`/amazon/accounts/${acc.id}/login`)}>Log in</ActionButton>
              <ActionButton size="sm" icon={ShieldCheck} action={() => api.post(`/amazon/accounts/${acc.id}/check`)} onDone={() => setTimeout(reload, 8000)}>Check login</ActionButton>
              <ActionButton size="sm" kind="ghost" confirm={`Remove ${acc.name}? Its saved login on this PC is deleted too.`}
                action={() => api.del(`/amazon/accounts/${acc.id}`)} onDone={() => { reload(); reloadStatus(); }} success="Account removed">Remove</ActionButton>
            </div>
          </div>
        ))}
        {data && data.accounts.length === 0 && (
          <p className="rounded-lg border border-dashed border-line-strong p-4 text-center text-[13px] text-ink-3">
            No Amazon accounts yet. Add one to use auto-buy and automatic tracking.
          </p>
        )}
        <form className="flex flex-wrap gap-2" onSubmit={async (e) => {
          e.preventDefault();
          try {
            await api.post("/amazon/accounts", { name: name || `Amazon account ${(data?.accounts.length || 0) + 1}` });
            setName("");
            reload();
            reloadStatus();
            toast("Account added. Click “Log in” on it to sign in.");
          } catch (err) {
            toast(err.message, "error");
          }
        }}>
          <input placeholder="Account name (e.g. Main, Backup)" value={name} onChange={(e) => setName(e.target.value)} className="min-w-0 flex-1" />
          <Button kind="secondary" type="submit" icon={Plus}>Add account</Button>
        </form>
        {data && data.accounts.length > 0 && (
          <div className="flex flex-wrap items-center gap-3 border-t border-line pt-4">
            <span className="text-[13px] font-medium">Rotation</span>
            <Segmented size="sm" value={data.rotation}
              options={[["round_robin", "Take turns"], ["least_used_today", "Least used today"]]}
              onChange={async (v) => {
                try {
                  await api.put("/settings", { amazon_rotation: v });
                  reload();
                } catch (e) {
                  toast(e.message, "error");
                }
              }} />
            <span className="text-xs text-ink-3">
              {data.next_reason ? data.next_reason : "Orders go to the account marked “Next in rotation”, skipping any at their daily limits."}
            </span>
          </div>
        )}
      </div>
    </>
  );
  if (bare) return body;
  return (
    <Card title="Amazon accounts" icon={Cloud}
      description="Buying accounts for automatic ordering and tracking. Each logs in once in its own browser window; passwords and cards are never stored."
      actions={a && <Badge color={a.status === "ok" ? "green" : "red"} dot>{a.status === "ok" ? "Amazon healthy" : "Amazon paused"}</Badge>}>
      {body}
    </Card>
  );
}

