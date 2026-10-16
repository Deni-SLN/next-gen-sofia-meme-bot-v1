import { useState } from "react";
import { useEquityCurve, usePortfolio, usePositions } from "../lib/queries";
import { Badge, Card, QueryState, fmtPct, fmtUsd, sumKnown } from "../components/ui";

export default function Portfolio() {
  const pf = usePortfolio();
  const pos = usePositions();
  const curve = useEquityCurve();
  const [amount, setAmount] = useState("500");
  const [kind, setKind] = useState<"DEPOSIT" | "WITHDRAWAL">("DEPOSIT");
  const [msg, setMsg] = useState<string | null>(null);

  const cash = async () => {
    setMsg(null);
    try {
      const res = await fetch("/api/v1/portfolio/cash-movement", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ kind, amount: Number(amount), mode: "PAPER" }),
      });
      const body = (await res.json()) as { recorded: boolean; reason?: string; error?: { message: string } };
      if (!res.ok) throw new Error(body.error?.message ?? "gagal");
      setMsg(body.recorded ? "Cash movement tercatat." : (body.reason ?? "duplikat — diabaikan (idempotency)."));
      pf.refetch();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "gagal");
    }
  };

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Portfolio Overview</h1>
      <div className="grid gap-4 md:grid-cols-2">
        {(["PAPER", "LIVE"] as const).map((m) => {
          const acc = pf.data?.modes[m];
          const incomplete = acc?.valuation_status === "INCOMPLETE";
          return (
            <Card key={m} title={`${m} Account`}>
              <QueryState isLoading={pf.isLoading} isError={pf.isError} error={pf.error}>
                <p className="text-2xl font-bold">{fmtUsd(acc?.equity)}</p>
                <p className="text-xs text-zinc-500">
                  realized {fmtUsd(acc?.realized_pnl)} · unrealized {fmtUsd(acc?.unrealized_pnl)} · DD{" "}
                  {fmtPct(acc?.current_drawdown_pct)}
                </p>
                {incomplete && (
                  <p className="mt-2 rounded-lg border border-amber-900/70 bg-amber-950/30 px-2 py-1 text-xs text-amber-300">
                    ◍ {acc?.unmarked_positions} posisi terbuka belum punya harga valid. Equity dan drawdown
                    tidak dihitung — bukan nol. Known equity saat ini {fmtUsd(acc?.known_equity)}.
                  </p>
                )}
                {m === "LIVE" && <p className="mt-1 text-xs text-amber-400">Belum tersedia — live trading dinonaktifkan di V1.</p>}
              </QueryState>
            </Card>
          );
        })}
      </div>
      <Card title="Equity curve (PAPER)">
        <QueryState isLoading={curve.isLoading} isError={curve.isError} error={curve.error} isEmpty={(curve.data?.curve.length ?? 0) === 0} emptyText="Belum ada pergerakan ekuitas.">
          <ul className="max-h-48 space-y-1 overflow-y-auto font-mono text-xs text-zinc-400">
            {(curve.data?.curve ?? []).slice(-30).map((p, i) => (
              <li key={i}>{p.timestamp ?? "start"} → {fmtUsd(p.equity)}</li>
            ))}
          </ul>
        </QueryState>
      </Card>
      <Card title="External cash movement (PAPER)">
        <div className="flex flex-wrap gap-2">
          <select value={kind} onChange={(e) => setKind(e.target.value as typeof kind)} className="rounded-md border border-zinc-700 bg-zinc-900 px-2 py-1.5 text-sm">
            <option value="DEPOSIT">DEPOSIT</option>
            <option value="WITHDRAWAL">WITHDRAWAL</option>
          </select>
          <input value={amount} onChange={(e) => setAmount(e.target.value)} inputMode="decimal" className="w-32 rounded-md border border-zinc-700 bg-zinc-900 px-2 py-1.5 text-sm" />
          <button onClick={cash} className="rounded-md bg-emerald-600 px-3 py-1.5 text-sm font-medium hover:bg-emerald-500">Catat</button>
        </div>
        {msg && <p className="mt-2 text-xs text-zinc-400">{msg}</p>}
      </Card>
      <Card title="Open Positions (PAPER)">
        <QueryState isLoading={pos.isLoading} isError={pos.isError} error={pos.error} isEmpty={(pos.data?.items.length ?? 0) === 0} emptyText="Tidak ada posisi.">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-zinc-500">
                <th className="py-1">Mint</th>
                <th>Status</th>
                <th className="text-right">Qty</th>
                <th className="text-right">Entry</th>
                <th className="text-right">PnL</th>
              </tr>
            </thead>
            <tbody>
              {(pos.data?.items ?? []).map((p) => (
                <tr key={p.id} className="border-t border-zinc-800/60">
                  <td className="py-1.5 font-mono text-xs">{p.mint_address.slice(0, 12)}…</td>
                  <td><Badge level={p.status === "OPEN" ? "ok" : "mute"}>{p.status}</Badge></td>
                  <td className="text-right font-mono">{p.quantity}</td>
                  <td className="text-right font-mono">{fmtUsd(p.average_entry_price, 6)}</td>
                  <td className="text-right font-mono">{fmtUsd(sumKnown(p.realized_pnl, p.unrealized_pnl))}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </QueryState>
      </Card>
    </div>
  );
}
