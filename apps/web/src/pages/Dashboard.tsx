import { Link } from "react-router-dom";
import { usePortfolio, useProvidersStatus, useSignals, useSystemStatus, useTokens } from "../lib/queries";
import { Badge, Card, QueryState, fmtPct, fmtUsd } from "../components/ui";

export default function Dashboard() {
  const sys = useSystemStatus();
  const tokens = useTokens();
  const signals = useSignals();
  const portfolio = usePortfolio();
  const providers = useProvidersStatus();

  const top = (tokens.data?.items ?? []).slice(0, 8);
  const activeSignals = (signals.data?.items ?? []).filter((s) => s.tradable).slice(0, 8);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-xl font-bold">Market Overview</h1>
        <Badge level="info">PAPER dipisah dari LIVE · LIVE OFF di V1</Badge>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Card title="Engine Status">
          <QueryState isLoading={sys.isLoading} isError={sys.isError} error={sys.error}>
            <p className="text-2xl font-bold text-emerald-300">{sys.data?.bot.status}</p>
            <p className="text-xs text-zinc-500">mode {sys.data?.bot.mode} · kill-switch {sys.data?.bot.kill_switch_active ? "AKTIF" : "mati"}</p>
          </QueryState>
        </Card>
        <Card title="Trading Summary (PAPER)">
          <QueryState isLoading={portfolio.isLoading} isError={portfolio.isError} error={portfolio.error}>
            <p className="text-2xl font-bold">{fmtUsd(portfolio.data?.modes.PAPER?.equity)}</p>
            <p className="text-xs text-zinc-500">realized {fmtUsd(portfolio.data?.modes.PAPER?.realized_pnl)}</p>
          </QueryState>
        </Card>
        <Card title="Trading Summary (LIVE)">
          <p className="text-2xl font-bold text-zinc-500">{fmtUsd(portfolio.data?.modes.LIVE?.equity)}</p>
          <p className="text-xs text-amber-400">Belum tersedia — live trading dinonaktifkan di V1.</p>
        </Card>
        <Card title="Provider Health">
          <QueryState isLoading={providers.isLoading} isError={providers.isError} error={providers.error} isEmpty={(providers.data?.providers.length ?? 0) === 0} emptyText="Belum ada data health provider.">
            <ul className="space-y-1 text-sm">
              {(providers.data?.providers ?? []).slice(0, 5).map((p) => (
                <li key={p.provider} className="flex items-center justify-between">
                  <span className="text-zinc-300">{p.provider}</span>
                  <Badge level={p.status === "UP" ? "ok" : p.status === "DOWN" ? "bad" : "mute"}>{p.status}</Badge>
                </li>
              ))}
            </ul>
          </QueryState>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card title="Active Signals" action={<Link to="/signals" className="text-xs text-emerald-300 hover:underline">Lihat semua →</Link>}>
          <QueryState isLoading={signals.isLoading} isError={signals.isError} error={signals.error} isEmpty={activeSignals.length === 0} emptyText="Tidak ada sinyal aktif.">
            <ul className="divide-y divide-zinc-800 text-sm">
              {activeSignals.map((s) => (
                <li key={s.id} className="flex items-center justify-between py-2">
                  <span className="font-mono text-xs text-zinc-300">{s.mint_address.slice(0, 10)}…</span>
                  <span className="flex gap-1.5">
                    <Badge level={s.decision === "LONG_CANDIDATE" ? "ok" : "mute"}>{s.decision}</Badge>
                    <Badge level="info">{s.status}</Badge>
                  </span>
                </li>
              ))}
            </ul>
          </QueryState>
        </Card>
        <Card title="Top Tokens" action={<Link to="/tokens" className="text-xs text-emerald-300 hover:underline">Token Explorer →</Link>}>
          <QueryState isLoading={tokens.isLoading} isError={tokens.isError} error={tokens.error} isEmpty={top.length === 0} emptyText="Belum ada token. Jalankan discovery/ingest dulu.">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-zinc-500">
                  <th className="py-1">Token</th>
                  <th className="text-right">Price</th>
                  <th className="text-right">Liq</th>
                  <th className="text-right">1h</th>
                </tr>
              </thead>
              <tbody>
                {top.map((t) => (
                  <tr key={t.id} className="border-t border-zinc-800/60">
                    <td className="py-1.5 font-medium">{t.symbol ?? t.mint_address.slice(0, 8)}</td>
                    <td className="text-right font-mono">{fmtUsd(t.price_usd, 6)}</td>
                    <td className="text-right font-mono">{fmtUsd(t.liquidity_usd, 0)}</td>
                    <td className={`text-right font-mono ${(t.price_change_1h ?? 0) >= 0 ? "text-emerald-300" : "text-red-300"}`}>{fmtPct(t.price_change_1h)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </QueryState>
        </Card>
      </div>

      <Card title="Risk Monitor">
        <QueryState isLoading={sys.isLoading} isError={sys.isError} error={sys.error}>
          <div className="flex flex-wrap gap-2 text-sm">
            <Badge level={sys.data?.bot.kill_switch_active ? "bad" : "ok"}>kill-switch {sys.data?.bot.kill_switch_active ? "AKTIF" : "mati"}</Badge>
            <Badge level="mute">orders {sys.data?.counts.orders}</Badge>
            <Badge level="mute">positions {sys.data?.counts.positions}</Badge>
            <Badge level="mute">signals {sys.data?.counts.signals}</Badge>
          </div>
        </QueryState>
      </Card>
    </div>
  );
}
