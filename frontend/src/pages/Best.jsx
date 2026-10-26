import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { Card, Table, money, useLoad } from "../components/ui";

export default function Best() {
  const nav = useNavigate();
  const [d] = useLoad(() => api.get("/metrics/best"), []);
  const cols = [
    { key: "image", label: "", render: (r) => (r.image ? <img src={r.image} alt="" className="h-8 w-8 rounded object-cover" /> : null) },
    { key: "title", label: "Title", className: "max-w-xs", render: (r) => <div className="line-clamp-2">{r.title}</div> },
    { key: "price", label: "Price", render: (r) => money(r.price) },
    { key: "units", label: "Units" },
    { key: "profit", label: "Profit", render: (r) => money(r.profit) },
    { key: "views", label: "Views" },
    { key: "watchers", label: "Watchers" },
  ];
  const t = (title, rows, empty) => (
    <Card title={title}><Table columns={cols} rows={rows} onRowClick={(r) => nav(`/listings/${r.id}`)} empty={empty} /></Card>
  );
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {t("Top by profit", d?.top_profit, "No sales yet.")}
      {t("Top by units sold", d?.top_units, "No sales yet.")}
      {t("Losing money", d?.losers, "No money-losing listings.")}
      {t("Lots of views, no sales", d?.views_no_sales, "No view data yet (synced from eBay every 6 hours).")}
    </div>
  );
}
