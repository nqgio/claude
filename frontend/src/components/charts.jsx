import { CartesianGrid, Tooltip, XAxis, YAxis } from "recharts";
import { money } from "./ui.jsx";

// Series colors come from CSS variables, so light/dark each use their own validated steps.
export const SERIES = ["var(--series-1)", "var(--series-2)", "var(--series-3)"];

const shortDate = (d) => {
  const dt = new Date(`${d}T00:00:00`);
  return Number.isNaN(dt.getTime()) ? d : dt.toLocaleDateString([], { month: "short", day: "numeric" });
};

export function axes({ currency = false, xKey = "date", dateAxis = true } = {}) {
  const tick = { fill: "var(--chart-axis)", fontSize: 11 };
  return [
    <CartesianGrid key="g" vertical={false} stroke="var(--chart-grid)" />,
    <XAxis key="x" dataKey={xKey} tick={tick} tickLine={false} axisLine={false} tickMargin={8} minTickGap={24}
      tickFormatter={dateAxis ? shortDate : undefined} />,
    <YAxis key="y" tick={tick} tickLine={false} axisLine={false} width={currency ? 56 : 32} allowDecimals={!currency ? false : true}
      tickFormatter={currency ? (v) => `$${Math.round(v).toLocaleString()}` : undefined} />,
  ];
}

export function ChartTooltip({ currency = false, dateAxis = true, cursor = true }) {
  return (
    <Tooltip
      cursor={cursor === "bar" ? { fill: "var(--c-surface-3)" } : { stroke: "var(--c-line-strong)", strokeWidth: 1 }}
      content={({ active, payload, label }) => {
        if (!active || !payload?.length) return null;
        return (
          <div className="card min-w-[150px] px-3 py-2 shadow-lg">
            <div className="mb-1.5 text-[11.5px] font-medium text-ink-3">{dateAxis ? shortDate(label) : label}</div>
            {payload.map((p) => (
              <div key={p.dataKey} className="flex items-center justify-between gap-4 py-0.5 text-[12.5px]">
                <span className="flex items-center gap-2 text-ink-2">
                  <span className="h-2 w-2 rounded-full" style={{ background: p.color }} />
                  {p.name}
                </span>
                <span className="tnum font-medium text-ink">{currency ? money(p.value) : p.value}</span>
              </div>
            ))}
          </div>
        );
      }}
    />
  );
}

export function LegendRow({ items }) {
  return (
    <div className="flex flex-wrap items-center gap-4 text-xs text-ink-2">
      {items.map(([label, color]) => (
        <span key={label} className="inline-flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full" style={{ background: color }} />
          {label}
        </span>
      ))}
    </div>
  );
}
