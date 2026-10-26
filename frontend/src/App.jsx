import {
  Activity as ActivityIcon, AlertTriangle, BarChart3, ListOrdered, Menu, Monitor, Moon, Package, Settings as SettingsIcon,
  ShieldAlert, ShoppingBag, Sun, Trophy, X, Zap,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Link, NavLink, Route, Routes, useLocation } from "react-router-dom";
import { api } from "./api";
import { ActionButton, cx, useLoad, when } from "./components/ui";
import Activity from "./pages/Activity";
import Best from "./pages/Best";
import ListingDetail from "./pages/ListingDetail";
import Listings from "./pages/Listings";
import Orders from "./pages/Orders";
import Overview from "./pages/Overview";
import Queue from "./pages/Queue";
import Settings from "./pages/Settings";
import { useTheme } from "./theme.jsx";

const NAV = [
  ["Store", [
    ["/", "Overview", BarChart3],
    ["/listings", "Listings", Package],
    ["/orders", "Orders", ShoppingBag],
    ["/queue", "Queue", ListOrdered],
    ["/best", "Best & worst", Trophy],
  ]],
  ["System", [
    ["/activity", "Activity log", ActivityIcon],
    ["/settings", "Settings", SettingsIcon],
  ]],
];

function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const opts = [["light", Sun, "Light"], ["dark", Moon, "Dark"], ["system", Monitor, "System"]];
  return (
    <div className="grid grid-cols-3 rounded-lg border border-line bg-surface-3 p-0.5" role="radiogroup" aria-label="Theme">
      {opts.map(([v, Icon, label]) => (
        <button
          key={v}
          role="radio"
          aria-checked={theme === v}
          title={label}
          onClick={() => setTheme(v)}
          className={cx(
            "flex h-7 items-center justify-center gap-1.5 rounded-md text-xs font-medium transition",
            theme === v ? "bg-surface text-ink shadow-xs ring-1 ring-line" : "text-ink-3 hover:text-ink"
          )}
        >
          <Icon className="h-3.5 w-3.5" />
          <span className="hidden xl:inline">{label}</span>
        </button>
      ))}
    </div>
  );
}

function StatusRow({ ok, warn, label, value }) {
  const color = ok ? "bg-emerald-500" : warn ? "bg-amber-500" : "bg-rose-500";
  return (
    <div className="flex items-center justify-between gap-2 text-xs">
      <span className="flex items-center gap-2 text-ink-2">
        <span className="relative flex h-2 w-2">
          {ok && <span className={cx("absolute inline-flex h-full w-full animate-ping rounded-full opacity-40", color)} />}
          <span className={cx("relative inline-flex h-2 w-2 rounded-full", color)} />
        </span>
        {label}
      </span>
      <span className="font-medium text-ink">{value}</span>
    </div>
  );
}

function Sidebar({ status, onNavigate }) {
  return (
    <div className="flex h-full flex-col">
      <Link to="/" onClick={onNavigate} className="flex items-center gap-2.5 px-5 pt-5 pb-6">
        <span className="grid h-8 w-8 place-items-center rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 text-white shadow-sm">
          <Zap className="h-4 w-4" fill="currentColor" />
        </span>
        <div className="leading-tight">
          <div className="text-[14px] font-semibold tracking-tight">Listing Automation</div>
          <div className="text-[11px] text-ink-3">Amazon → eBay</div>
        </div>
      </Link>
      <nav className="flex-1 space-y-6 overflow-y-auto px-3">
        {NAV.map(([section, items]) => (
          <div key={section}>
            <div className="px-2 pb-1.5 text-[11px] font-medium tracking-wider text-ink-3 uppercase">{section}</div>
            <div className="space-y-0.5">
              {items.map(([to, label, Icon]) => (
                <NavLink
                  key={to}
                  to={to}
                  end={to === "/"}
                  onClick={onNavigate}
                  className={({ isActive }) =>
                    cx(
                      "group flex h-9 items-center gap-2.5 rounded-lg px-2.5 text-[13px] font-medium transition",
                      isActive ? "bg-surface text-ink shadow-xs ring-1 ring-line" : "text-ink-2 hover:bg-surface-3 hover:text-ink"
                    )
                  }
                >
                  {({ isActive }) => (
                    <>
                      <Icon className={cx("h-4 w-4", isActive ? "text-accent" : "text-ink-3 group-hover:text-ink-2")} />
                      {label}
                    </>
                  )}
                </NavLink>
              ))}
            </div>
          </div>
        ))}
      </nav>
      <div className="space-y-3 p-3">
        {status && (
          <div className="card space-y-2.5 p-3">
            <StatusRow ok={!status.dry_run} warn={status.dry_run} label="Mode" value={status.dry_run ? "Dry run" : "Live"} />
            <StatusRow ok={status.environment === "production"} warn={status.environment === "sandbox"} label="eBay"
              value={status.ebay.connected ? (status.environment === "sandbox" ? "Sandbox" : "Production") : "Not connected"} />
            <StatusRow ok={status.amazon.status === "ok"} label="Amazon" value={status.amazon.status === "ok" ? "Healthy" : "Paused"} />
          </div>
        )}
        <ThemeToggle />
      </div>
    </div>
  );
}

function Alerts({ status, reload }) {
  if (!status) return null;
  const items = [];
  if (status.amazon.status === "paused")
    items.push(
      <div key="amz" className="flex flex-wrap items-center gap-3 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-[13px] text-rose-800 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-200">
        <ShieldAlert className="h-4.5 w-4.5 shrink-0" />
        <span className="flex-1">
          <strong className="font-semibold">Amazon jobs paused.</strong> Amazon showed a CAPTCHA or block ({status.amazon.reason}). The app
          never bypasses it, and resumes automatically {when(status.amazon.paused_until)}.
        </span>
        <ActionButton size="sm" action={() => api.post("/amazon/resume")} onDone={reload} success="Amazon jobs resumed">Resume now</ActionButton>
      </div>
    );
  if (status.dry_run)
    items.push(
      <div key="dry" className="flex flex-wrap items-center gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-2.5 text-[13px] text-amber-900 dark:border-amber-500/25 dark:bg-amber-500/10 dark:text-amber-200">
        <AlertTriangle className="h-4 w-4 shrink-0" />
        <span className="flex-1">
          <strong className="font-semibold">Dry-run mode is on</strong>, so nothing is posted or changed on eBay.
          {status.environment === "sandbox" && " You're on the eBay sandbox."}
        </span>
        <Link to="/settings" className="text-[12.5px] font-semibold underline-offset-2 hover:underline">Settings →</Link>
      </div>
    );
  if (status.checkout_mode === "auto" && status.kill_switch)
    items.push(
      <div key="ks" className="rounded-xl border border-line bg-surface-3 px-4 py-2.5 text-[13px] text-ink-2">
        Auto-buy kill switch is on, so no Amazon orders will be placed.
      </div>
    );
  return items.length ? <div className="mb-6 space-y-2">{items}</div> : null;
}

export default function App() {
  const [status, reload] = useLoad(() => api.get("/status"), [], 15000);
  const [open, setOpen] = useState(false);
  const loc = useLocation();
  useEffect(() => window.scrollTo(0, 0), [loc.pathname]);
  return (
    <div className="min-h-screen">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 border-r border-line bg-surface-2 lg:block">
        <Sidebar status={status} />
      </aside>
      {open && (
        <div className="anim-fade fixed inset-0 z-40 bg-black/40 lg:hidden" onClick={() => setOpen(false)}>
          <aside className="anim-slide h-full w-64 border-r border-line bg-surface-2" onClick={(e) => e.stopPropagation()}>
            <Sidebar status={status} onNavigate={() => setOpen(false)} />
          </aside>
        </div>
      )}
      <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-line bg-surface/80 px-4 backdrop-blur lg:hidden">
        <button onClick={() => setOpen(!open)} className="rounded-md p-1.5 text-ink-2 hover:bg-surface-3" aria-label="Menu">
          {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
        <span className="font-semibold">Listing Automation</span>
      </header>
      <main className="lg:pl-60">
        <div className="mx-auto max-w-[1280px] px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <Alerts status={status} reload={reload} />
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/listings" element={<Listings />} />
            <Route path="/listings/:id" element={<ListingDetail />} />
            <Route path="/orders" element={<Orders status={status} />} />
            <Route path="/queue" element={<Queue />} />
            <Route path="/best" element={<Best />} />
            <Route path="/activity" element={<Activity />} />
            <Route path="/settings" element={<Settings status={status} reloadStatus={reload} />} />
          </Routes>
        </div>
      </main>
    </div>
  );
}
