import { useState } from "react";

import { Badge, Card, QueryState, fmtPct, fmtUsd } from "../components/ui";
import { useBacktest, usePerformance } from "../lib/queries";
import { PERFORMANCE_METRICS } from "../lib/types";
import type { BacktestResult, PerformanceMetric } from "../lib/types";

/** Render a metric by its declared kind.
 *
 * A null here means "not measured" - the backend returns null for an unknown
 * value, and for metrics it declares in `unavailable_metrics`. Both render as
 * a dash rather than a zero.
 */
function renderMetric(metric: PerformanceMetric, value: number | null | undefined) {
  if (metric.kind === "pct") {
    // win_rate and drawdown percentages are already 0-100 fractions from the
    // API, so format without the signed-percent helper's extra scaling.
    if (value === null || value === undefined || Number.isNaN(value)) return "—";
    return `${value.toFixed(2)}%`;
  }
  if (metric.kind === "usd") return fmtUsd(value);
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return String(value);
}

export default function Performance() {
  const perf = usePerformance();
  const backtest = useBacktest();
  const [btMsg, setBtMsg] = useState<string | null>(null);
  const [pairId, setPairId] = useState("");
  const [timeframe, setTimeframe] = useState("M1");

  const runBacktest = async () => {
    setBtMsg(null);
    try {
      await backtest.mutateAsync({ pair_id: pairId, timeframe });
      setBtMsg(null);
    } catch (e) {
      setBtMsg(e instanceof Error ? e.message : "gagal menjalankan backtest");
    }
  };

  const bt: BacktestResult | undefined = backtest.data;

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Performance &amp; Research</h1>
      <div className="grid gap-4 md:grid-cols-2">
        {(["paper", "live"] as const).map((m) => {
          const acc = perf.data?.[m];
          const incomplete = acc?.valuation_status === "INCOMPLETE";
          return (
            <Card key={m} title={`${m.toUpperCase()} metrics`}>
              <QueryState isLoading={perf.isLoading} isError={perf.isError} error={perf.error}>
                {incomplete && (
                  <p className="mb-2 rounded-lg border border-amber-900/70 bg-amber-950/30 px-2 py-1 text-xs text-amber-300">
                    ◍ {acc?.unmarked_positions} posisi terbuka belum punya harga valid. Metrik yang
                    bergantung pada equity tidak dihitung — bukan nol.
                  </p>
                )}
                <dl className="grid grid-cols-2 gap-2 text-sm">
                  {PERFORMANCE_METRICS.map((metric) => {
                    const value = acc?.[metric.key];
                    const declared = acc?.unavailable_metrics?.includes(metric.key);
                    return (
                      <div key={metric.key} className="rounded-lg border border-zinc-800 p-2">
                        <dt className="text-xs text-zinc-500" title={declared ? "Belum diimplementasikan (PRD §14)" : metric.key}>
                          {metric.label}
                        </dt>
                        <dd className="font-mono">
                          {renderMetric(metric, value as number | null | undefined)}
                        </dd>
                      </div>
                    );
                  })}
                </dl>
                {m === "live" && (
                  <p className="mt-2 text-xs text-amber-400">
                    LIVE belum tersedia di V1 — metrik kosong secara eksplisit, bukan nol yang menyesatkan.
                  </p>
                )}
              </QueryState>
            </Card>
          );
        })}
      </div>

      <Card title="Backtest (deterministik, di atas candle tersimpan)">
        <QueryState
          isLoading={backtest.isPending}
          isError={backtest.isError}
          error={backtest.error}
          isEmpty={!bt && !btMsg}
          emptyText="Belum ada hasil backtest sesi ini."
        >
          <div className="mb-3 flex flex-wrap items-end gap-2">
            <label className="text-xs text-zinc-500">
              pair_id
              <input
                value={pairId}
                onChange={(e) => setPairId(e.target.value)}
                placeholder="uuid pair"
                className="mt-1 block w-64 rounded-md border border-zinc-700 bg-zinc-900 px-2 py-1.5 font-mono text-sm"
              />
            </label>
            <label className="text-xs text-zinc-500">
              timeframe
              <select
                value={timeframe}
                onChange={(e) => setTimeframe(e.target.value)}
                className="mt-1 block rounded-md border border-zinc-700 bg-zinc-900 px-2 py-1.5 text-sm"
              >
                {["M1", "M5", "M15", "M30", "H1", "H4", "D1"].map((tf) => (
                  <option key={tf} value={tf}>
                    {tf}
                  </option>
                ))}
              </select>
            </label>
            <button
              onClick={runBacktest}
              disabled={!pairId || backtest.isPending}
              className="rounded-md bg-emerald-600 px-3 py-1.5 text-sm font-medium hover:bg-emerald-500 disabled:opacity-50"
            >
              Jalankan
            </button>
          </div>
          {btMsg && <p className="mb-2 text-xs text-red-400">{btMsg}</p>}
          {bt && (
            <div className="flex flex-wrap gap-2 text-sm">
              <Badge level="info">timeframe {bt.timeframe}</Badge>
              <Badge level="info">candles {bt.candles}</Badge>
              <Badge level="info">trades {bt.trades}</Badge>
              <Badge level="info">win rate {bt.win_rate === null ? "—" : `${(bt.win_rate * 100).toFixed(1)}%`}</Badge>
              <Badge level={bt.net_pnl >= 0 ? "ok" : "bad"}>
                net {fmtUsd(bt.net_pnl)} ({fmtPct(bt.net_pnl_pct)})
              </Badge>
              <Badge level="mute">fees {fmtUsd(bt.total_fees)}</Badge>
              <Badge level="mute">max DD {bt.max_drawdown_pct.toFixed(2)}%</Badge>
            </div>
          )}
        </QueryState>
      </Card>
    </div>
  );
}
