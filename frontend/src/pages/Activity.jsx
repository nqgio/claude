import { useState } from "react";
import { api } from "../api";
import { Badge, Button, Card, useLoad, when } from "../components/ui";

const LEVEL = { info: "gray", warning: "yellow", error: "red" };
const PAGE = 200;

export default function Activity() {
  const [category, setCategory] = useState("");
  const [level, setLevel] = useState("");
  const [q, setQ] = useState("");
  const [offset, setOffset] = useState(0);
  const qs = new URLSearchParams({ limit: PAGE, offset, ...(category && { category }), ...(level && { level }), ...(q && { q }) });
  const [d] = useLoad(() => api.get(`/activity?${qs}`), [qs.toString()], 10000);
  return (
    <Card
      title={`Activity log${d ? ` (${d.total})` : ""}`}
      actions={
        <>
          <input placeholder="Search" value={q} onChange={(e) => { setQ(e.target.value); setOffset(0); }} />
          <select value={category} onChange={(e) => { setCategory(e.target.value); setOffset(0); }}>
            <option value="">All categories</option>
            {(d?.categories || []).map((c) => <option key={c}>{c}</option>)}
          </select>
          <select value={level} onChange={(e) => { setLevel(e.target.value); setOffset(0); }}>
            <option value="">All levels</option><option>info</option><option>warning</option><option>error</option>
          </select>
        </>
      }
    >
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <tbody>
            {(d?.items || []).map((r) => (
              <tr key={r.id} className="border-b border-slate-100 dark:border-slate-800/60">
                <td className="whitespace-nowrap px-2 py-1.5 text-xs text-slate-500">{when(r.ts)}</td>
                <td className="px-2 py-1.5"><Badge color={LEVEL[r.level]}>{r.category}</Badge></td>
                <td className="px-2 py-1.5">
                  {r.message}
                  {r.details?.traceback && (
                    <details className="text-xs text-slate-500"><summary>details</summary><pre className="whitespace-pre-wrap">{r.details.traceback}</pre></details>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mt-3 flex gap-2">
        <Button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>Newer</Button>
        <Button disabled={!d || offset + PAGE >= d.total} onClick={() => setOffset(offset + PAGE)}>Older</Button>
      </div>
    </Card>
  );
}
