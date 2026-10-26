import { NavLink, Route, Routes } from "react-router-dom";
import { api } from "./api";
import { ActionButton, useLoad, when } from "./components/ui";
import Activity from "./pages/Activity";
import Best from "./pages/Best";
import ListingDetail from "./pages/ListingDetail";
import Listings from "./pages/Listings";
import Orders from "./pages/Orders";
import Overview from "./pages/Overview";
import Queue from "./pages/Queue";
import Settings from "./pages/Settings";

const NAV = [
  ["/", "Overview"],
  ["/listings", "Listings"],
  ["/orders", "Orders"],
  ["/queue", "Queue"],
  ["/best", "Best & worst"],
  ["/activity", "Activity log"],
  ["/settings", "Settings"],
];

function Banners({ status, reload }) {
  if (!status) return null;
  const b = [];
  if (status.amazon.status === "paused")
    b.push(
      <div key="amz" className="flex flex-wrap items-center gap-3 bg-rose-600 px-4 py-2 text-sm text-white">
        <strong>Amazon jobs paused</strong> — Amazon showed a CAPTCHA/block ({status.amazon.reason}). Resumes automatically at{" "}
        {when(status.amazon.paused_until)}.
        <ActionButton action={() => api.post("/amazon/resume")} onDone={reload}>Resume now</ActionButton>
      </div>
    );
  if (status.dry_run)
    b.push(
      <div key="dry" className="bg-amber-400 px-4 py-1.5 text-sm text-amber-950">
        <strong>Dry-run mode is ON</strong> — nothing is posted or changed on eBay. Turn it off in Settings when you're ready.
      </div>
    );
  if (status.environment === "sandbox")
    b.push(
      <div key="sb" className="bg-sky-600 px-4 py-1 text-xs text-white">Using the eBay <strong>Sandbox</strong> (test site).</div>
    );
  if (status.checkout_mode === "auto" && status.kill_switch)
    b.push(<div key="ks" className="bg-slate-800 px-4 py-1 text-xs text-white">Auto-buy kill switch is ON — no Amazon orders will be placed.</div>);
  return <>{b}</>;
}

export default function App() {
  const [status, reload] = useLoad(() => api.get("/status"), [], 15000);
  return (
    <div className="min-h-screen">
      <Banners status={status} reload={reload} />
      <header className="border-b border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
          <div className="font-semibold">Amazon → eBay</div>
          <nav className="flex flex-wrap gap-1">
            {NAV.map(([to, label]) => (
              <NavLink
                key={to}
                to={to}
                end={to === "/"}
                className={({ isActive }) =>
                  `rounded-md px-3 py-1.5 text-sm ${isActive ? "bg-indigo-600 text-white" : "hover:bg-slate-100 dark:hover:bg-slate-800"}`
                }
              >
                {label}
              </NavLink>
            ))}
          </nav>
          {status && (
            <div className="ml-auto flex gap-3 text-xs text-slate-500">
              <span>eBay: {status.ebay.connected ? "connected" : "not connected"}</span>
              <span>Amazon: {status.amazon.status}</span>
            </div>
          )}
        </div>
      </header>
      <main className="mx-auto max-w-7xl p-4">
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/listings" element={<Listings />} />
          <Route path="/listings/:id" element={<ListingDetail />} />
          <Route path="/orders" element={<Orders />} />
          <Route path="/queue" element={<Queue />} />
          <Route path="/best" element={<Best />} />
          <Route path="/activity" element={<Activity />} />
          <Route path="/settings" element={<Settings status={status} reloadStatus={reload} />} />
        </Routes>
      </main>
    </div>
  );
}
