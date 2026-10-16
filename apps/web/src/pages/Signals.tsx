import { useState } from "react";
import { useAnalysisRuns, useSignals } from "../lib/queries";
import { Badge, Card, QueryState } from "../components/ui";

export default function Signals() {
  const [status, setStatus] = useState("");
  const signals = useSignals(status || undefined);
  const runs = useAnalysisRuns();

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-xl font-bold">Signal Center</h1>
        <select value={status} onChange={(e) => setStatus(e.target.value)} className="rounded-md border border-zinc-700 bg-zinc-900 px-2 py-1.5 text-sm">
          <option value="">Semua status</option>
          {["CREATED", "VALIDATED", "ACTIVE", "WAIT", "REJECTED", "EXPIRED", "INVALIDATED", "EVALUATED"].map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </div>
      <p className="text-xs text-zinc-500">Sinyal bukan order — eksekusi hanya terjadi bila bot PAPER berjalan dan risk gate menyetujui.</p>
      <Card title="Signals">
        <QueryState isLoading={signals.isLoading} isError={signals.isError} error={signals.error} isEmpty={(signals.data?.items.length ?? 0) === 0} emptyText="Belum ada sinyal.">
          <ul className="space-y-3">
            {(signals.data?.items ?? []).map((s) => (
              <li key={s.id} className="rounded-lg border border-zinc-800 p-3">
                <div className="mb-1 flex flex-wrap items-center gap-2">
                  <span className="font-mono text-xs text-zinc-300">{s.mint_address.slice(0, 16)}…</span>
                  <Badge level={s.decision === "LONG_CANDIDATE" ? "ok" : s.decision === "REJECT" ? "bad" : "mute"}>{s.decision}</Badge>
                  <Badge level="info">{s.status}</Badge>
                  {s.tradable ? <Badge level="ok">TRADABLE</Badge> : <Badge level="mute">NOT TRADABLE</Badge>}
                </div>
                <p className="text-xs text-zinc-500">
                  entry {s.entry_reference ?? "—"} · stop {s.stop_reference ?? "—"} · R/R {s.risk_reward ?? "—"} · coverage {s.coverage ?? "—"}
                </p>
                <ul className="mt-1 list-disc pl-5 text-xs text-zinc-400">
                  {s.reasons.slice(0, 4).map((r, i) => <li key={i}>{r}</li>)}
                </ul>
              </li>
            ))}
          </ul>
        </QueryState>
      </Card>
      <Card title="Analysis History">
        <QueryState isLoading={runs.isLoading} isError={runs.isError} error={runs.error} isEmpty={(runs.data?.items.length ?? 0) === 0} emptyText="Belum ada analysis run.">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-zinc-500">
                <th className="py-1">Run</th>
                <th>Decision</th>
                <th className="text-right">Score</th>
                <th className="text-right">Coverage</th>
              </tr>
            </thead>
            <tbody>
              {(runs.data?.items ?? []).slice(0, 20).map((r) => (
                <tr key={r.id} className="border-t border-zinc-800/60">
                  <td className="py-1.5 font-mono text-xs">{r.id.slice(0, 8)}</td>
                  <td><Badge level={r.decision === "LONG_CANDIDATE" ? "ok" : "mute"}>{r.decision}</Badge></td>
                  <td className="text-right font-mono">{r.score ?? "—"}</td>
                  <td className="text-right font-mono">{r.coverage ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </QueryState>
      </Card>
    </div>
  );
}
