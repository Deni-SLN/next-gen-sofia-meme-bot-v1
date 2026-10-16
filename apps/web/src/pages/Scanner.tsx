import { useState } from "react";
import { Link } from "react-router-dom";
import { get } from "../lib/api";
import { useTokens } from "../lib/queries";
import { Badge, Card, QueryState, fmtPct, fmtUsd } from "../components/ui";

export default function Scanner() {
  const [q, setQ] = useState("SOL");
  const [result, setResult] = useState<{ items: { mint_address: string; symbol: string | null; price_usd: number | null; liquidity_usd: number | null }[]; error?: string } | null>(null);
  const [loading, setLoading] = useState(false);
  const [ingestMsg, setIngestMsg] = useState<string | null>(null);
  const stored = useTokens();

  const search = async () => {
    setLoading(true);
    setResult(null);
    try {
      const r = await get<{ items: { mint_address: string; symbol: string | null; price_usd: number | null; liquidity_usd: number | null }[]; error?: string }>(`/api/v1/discover/search?q=${encodeURIComponent(q)}`);
      setResult(r);
    } catch (e) {
      setResult({ items: [], error: e instanceof Error ? e.message : "search failed" });
    } finally {
      setLoading(false);
    }
  };

  const ingest = async () => {
    setIngestMsg(null);
    try {
      const res = await fetch(`/api/v1/discover/ingest?q=${encodeURIComponent(q)}`, { method: "POST" });
      const body = (await res.json()) as { ingested?: number; tokens?: number; error?: string };
      setIngestMsg(body.error ?? `Ingested ${body.tokens ?? body.ingested ?? 0} token.`);
      stored.refetch();
    } catch (e) {
      setIngestMsg(e instanceof Error ? e.message : "ingest failed");
    }
  };

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Market Scanner</h1>
      <Card title="Discovery via DEX Screener">
        <div className="flex flex-wrap gap-2">
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="cth: SOL, BONK, WIF" className="w-64 rounded-md border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-sm" />
          <button onClick={search} disabled={loading} className="rounded-md bg-emerald-600 px-3 py-1.5 text-sm font-medium hover:bg-emerald-500 disabled:opacity-50">
            {loading ? "Mencari…" : "Search"}
          </button>
          <button onClick={ingest} className="rounded-md border border-zinc-700 px-3 py-1.5 text-sm hover:bg-zinc-900">
            Ingest ke DB lokal
          </button>
        </div>
        {ingestMsg && <p className="mt-2 text-xs text-zinc-400">{ingestMsg}</p>}
        {result && (
          <div className="mt-3">
            {result.error && <p className="mb-2 text-sm text-amber-300">Provider: {result.error}</p>}
            {result.items.length === 0 ? (
              <p className="text-sm text-zinc-500">Tidak ada hasil.</p>
            ) : (
              <ul className="divide-y divide-zinc-800 text-sm">
                {result.items.slice(0, 20).map((p) => (
                  <li key={p.mint_address} className="flex items-center justify-between py-1.5">
                    <span>
                      <Link to={`/tokens/${p.mint_address}`} className="font-medium text-emerald-300 hover:underline">{p.symbol ?? p.mint_address.slice(0, 8)}</Link>{" "}
                      <span className="font-mono text-xs text-zinc-500">{p.mint_address.slice(0, 12)}…</span>
                    </span>
                    <span className="font-mono text-xs">{fmtUsd(p.price_usd, 6)} · {fmtUsd(p.liquidity_usd, 0)}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </Card>
      <Card title="Token tersimpan (DB lokal)">
        <QueryState isLoading={stored.isLoading} isError={stored.isError} error={stored.error} isEmpty={(stored.data?.items.length ?? 0) === 0} emptyText="Belum ada token tersimpan — lakukan ingest.">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-zinc-500">
                <th className="py-1">Token</th>
                <th className="text-right">Price</th>
                <th className="text-right">Liq</th>
                <th className="text-right">1h</th>
                <th className="text-right">State</th>
              </tr>
            </thead>
            <tbody>
              {(stored.data?.items ?? []).slice(0, 20).map((t) => (
                <tr key={t.id} className="border-t border-zinc-800/60">
                  <td className="py-1.5">
                    <Link to={`/tokens/${t.mint_address}`} className="font-medium text-emerald-300 hover:underline">{t.symbol ?? t.mint_address.slice(0, 8)}</Link>
                  </td>
                  <td className="text-right font-mono">{fmtUsd(t.price_usd, 6)}</td>
                  <td className="text-right font-mono">{fmtUsd(t.liquidity_usd, 0)}</td>
                  <td className={`text-right font-mono ${(t.price_change_1h ?? 0) >= 0 ? "text-emerald-300" : "text-red-300"}`}>{fmtPct(t.price_change_1h)}</td>
                  <td className="text-right">{t.stale ? <Badge level="warn">STALE</Badge> : <Badge level="ok">FRESH</Badge>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </QueryState>
      </Card>
    </div>
  );
}
