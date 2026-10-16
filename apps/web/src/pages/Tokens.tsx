import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { createChart, type IChartApi, type ISeriesApi } from "lightweight-charts";
import { useTokenCandles, useTokens } from "../lib/queries";
import { Badge, Card, QueryState, fmtPct, fmtUsd } from "../components/ui";

function CandleChart({ mint, timeframe }: { mint: string; timeframe: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const q = useTokenCandles(mint, timeframe);

  useEffect(() => {
    if (!ref.current) return;
    const chart = createChart(ref.current, {
      layout: { background: { color: "transparent" }, textColor: "#a1a1aa" },
      grid: { vertLines: { color: "#27272a" }, horzLines: { color: "#27272a" } },
      width: ref.current.clientWidth,
      height: 320,
    });
    chartRef.current = chart;
    const onResize = () => chart.applyOptions({ width: ref.current?.clientWidth ?? 600 });
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      chart.remove();
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || !q.data) return;
    const series: ISeriesApi<"Candlestick"> = chart.addSeries(
      { type: "Candlestick", upColor: "#10b981", downColor: "#f43f5e", wickUpColor: "#10b981", wickDownColor: "#f43f5e" } as never,
      {},
    );
    series.setData(
      q.data.items.map((c) => ({
        time: Math.floor(new Date(c.time).getTime() / 1000) as never,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      })),
    );
    chart.timeScale().fitContent();
    return () => chart.removeSeries(series);
  }, [q.data]);

  return (
    <QueryState isLoading={q.isLoading} isError={q.isError} error={q.error} isEmpty={(q.data?.items.length ?? 0) === 0} emptyText="Belum ada candle tersimpan untuk token ini.">
      <div ref={ref} className="w-full" />
    </QueryState>
  );
}

export default function Tokens() {
  const { mint } = useParams();
  const tokens = useTokens();
  // Must be a code the backend accepts (SUPPORTED_TIMEFRAMES). "5m" was
  // rejected on load because the API matches on the stored code, not the
  // lowercase provider spelling.
  const [tf, setTf] = useState("M1");
  const [analysis, setAnalysis] = useState<{ decision: string; score: number | null; reasons: string[] } | null>(null);
  const [analyzing, setAnalyzing] = useState(false);

  if (mint) {
    const runAnalysis = async () => {
      setAnalyzing(true);
      try {
        const res = await fetch(`/api/v1/tokens/${mint}/analyze`, { method: "POST" });
        setAnalysis((await res.json()) as typeof analysis);
      } catch {
        setAnalysis({ decision: "ERROR", score: null, reasons: ["analysis failed"] });
      } finally {
        setAnalyzing(false);
      }
    };
    return (
      <div className="space-y-4">
        <Link to="/tokens" className="text-sm text-emerald-300 hover:underline">← Kembali</Link>
        <h1 className="font-mono text-lg font-bold break-all">{mint}</h1>
        <Card title="Chart" action={
          <select value={tf} onChange={(e) => setTf(e.target.value)} className="rounded-md border border-zinc-700 bg-zinc-900 px-2 py-1 text-sm">
            {["M1", "M5", "M15", "H1"].map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        }>
          <CandleChart mint={mint} timeframe={tf} />
        </Card>
        <Card title="Analysis" action={
          <button onClick={runAnalysis} disabled={analyzing} className="rounded-md bg-emerald-600 px-3 py-1 text-sm font-medium hover:bg-emerald-500 disabled:opacity-50">
            {analyzing ? "Menganalisis…" : "Run Analysis"}
          </button>
        }>
          {analysis ? (
            <div className="space-y-2 text-sm">
              <Badge level={analysis.decision === "LONG_CANDIDATE" ? "ok" : analysis.decision === "REJECT" ? "bad" : "mute"}>{analysis.decision}</Badge>
              <p>Score: <span className="font-mono">{analysis.score ?? "—"}</span></p>
              <ul className="list-disc pl-5 text-zinc-400">{analysis.reasons.map((r, i) => <li key={i}>{r}</li>)}</ul>
            </div>
          ) : (
            <p className="text-sm text-zinc-500">Belum ada hasil analisis.</p>
          )}
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Token Explorer</h1>
      <Card title="Semua token tersimpan">
        <QueryState isLoading={tokens.isLoading} isError={tokens.isError} error={tokens.error} isEmpty={(tokens.data?.items.length ?? 0) === 0}>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-zinc-500">
                <th className="py-1">Token</th>
                <th className="text-right">Price</th>
                <th className="text-right">Liq</th>
                <th className="text-right">24h</th>
              </tr>
            </thead>
            <tbody>
              {(tokens.data?.items ?? []).map((t) => (
                <tr key={t.id} className="border-t border-zinc-800/60">
                  <td className="py-1.5">
                    <Link to={`/tokens/${t.mint_address}`} className="font-medium text-emerald-300 hover:underline">{t.symbol ?? t.mint_address.slice(0, 8)}</Link>
                    <span className="ml-2">{t.stale ? <Badge level="warn">STALE</Badge> : null}</span>
                  </td>
                  <td className="text-right font-mono">{fmtUsd(t.price_usd, 6)}</td>
                  <td className="text-right font-mono">{fmtUsd(t.liquidity_usd, 0)}</td>
                  <td className={`text-right font-mono ${(t.price_change_24h ?? 0) >= 0 ? "text-emerald-300" : "text-red-300"}`}>{fmtPct(t.price_change_24h)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </QueryState>
      </Card>
    </div>
  );
}
