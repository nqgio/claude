import { Eye, TrendingDown, TrendingUp, Trophy } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { Card, EmptyState, PageHeader, Table, Thumb, cx, money, useLoad } from "../components/ui";

export default function Best() {
  const nav = useNavigate();
  const [d] = useLoad(() => api.get("/metrics/best"), []);
  const cols = [
    {
      key: "title", label: "Listing", className: "min-w-[220px]",
      render: (r) => (
        <div className="flex items-center gap-3">
          <Thumb src={r.image} size="h-9 w-9" />
          <span className="line-clamp-1 font-medium">{r.title}</span>
        </div>
      ),
    },
    { key: "units", label: "Units", align: "right" },
    { key: "profit", label: "Profit", align: "right", render: (r) => <span className={cx("font-medium", r.profit < 0 ? "text-rose-600 dark:text-rose-400" : r.profit > 0 ? "text-emerald-600 dark:text-emerald-400" : "")}>{money(r.profit)}</span> },
    { key: "views", label: "Views", align: "right" },
    { key: "watchers", label: "Watch", align: "right" },
  ];
  const t = (title, icon, rows, emptyTitle, emptyText) => (
    <Card title={title} icon={icon} padded={false}>
      <Table columns={cols} rows={rows} loading onRowClick={(r) => nav(`/listings/${r.id}`)} empty={<EmptyState icon={icon} title={emptyTitle} text={emptyText} />} />
    </Card>
  );
  return (
    <>
      <PageHeader title="Best & worst" description="What's earning, what's losing, and what gets looked at but doesn't sell." />
      <div className="grid gap-6 xl:grid-cols-2">
        {t("Top by profit", Trophy, d?.top_profit, "No sales yet")}
        {t("Top by units sold", TrendingUp, d?.top_units, "No sales yet")}
        {t("Losing money", TrendingDown, d?.losers, "Nothing is losing money", "Listings whose orders net out negative show up here.")}
        {t("Lots of views, no sales", Eye, d?.views_no_sales, "No view data yet", "Views sync from eBay every 6 hours for live listings.")}
      </div>
    </>
  );
}
