import { useState, useEffect, useRef, useMemo, useCallback } from "react";
import { Link } from "react-router-dom";
import { get } from "../lib/api";
import { useTokens } from "../lib/queries";
import { Badge, Card, QueryState, fmtPct, fmtUsd } from "../components/ui";

export interface DiscoveredPair {
  chain: string;
  mint_address: string;
  pair_address: string;
  symbol: string | null;
  name: string | null;
  dex_id: string | null;
  price_usd: number | null;
  liquidity_usd: number | null;
  volume_5m: number | null;
  volume_1h: number | null;
  volume_24h: number | null;
  buys_1h: number | null;
  sells_1h: number | null;
  price_change_5m: number | null;
  price_change_1h: number | null;
  price_change_24h: number | null;
  fdv: number | null;
  market_cap: number | null;
  pair_created_at: string | null;
  observed_at: string | null;
  source: string;
}

export type RadarTab = "micro" | "mid" | "graduate" | "major" | "all";

function fmtPrice(p: number | null | undefined): string {
  if (p === null || p === undefined || Number.isNaN(p)) return "—";
  if (p === 0) return "$0.00";
  if (p < 0.000001) return `$${p.toExponential(3)}`;
  if (p < 0.01) return `$${p.toFixed(6)}`;
  if (p < 1) return `$${p.toFixed(4)}`;
  return `$${p.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function fmtCompact(val: number | null | undefined): string {
  if (val === null || val === undefined || Number.isNaN(val)) return "—";
  if (val >= 1_000_000_000) return `$${(val / 1_000_000_000).toFixed(2)}B`;
  if (val >= 1_000_000) return `$${(val / 1_000_000).toFixed(2)}M`;
  if (val >= 1_000) return `$${(val / 1_000).toFixed(1)}K`;
  return `$${val.toFixed(0)}`;
}

export function getEffectiveCap(p: DiscoveredPair): number {
  return p.market_cap ?? p.fdv ?? (p.liquidity_usd ? p.liquidity_usd * 2 : 0);
}

export function getPairTier(p: DiscoveredPair): "micro" | "mid" | "graduate" | "major" {
  const cap = getEffectiveCap(p);
  const dex = (p.dex_id || "").toLowerCase();
  const isMigratedDex = dex === "raydium" || dex === "orca" || dex === "meteora";

  if (cap >= 1_000_000) {
    return "major";
  }
  // Graduate: migrated to Raydium/Orca/Meteora with cap >= 50K or liquid Raydium pool
  if (isMigratedDex && (cap >= 50_000 || (p.liquidity_usd ?? 0) >= 15_000)) {
    return "graduate";
  }
  if (cap >= 100_000) {
    return "mid";
  }
  return "micro";
}

const PRESET_QUERIES = [
  { label: "🔥 Trending SOL", query: "SOL" },
  { label: "🚀 Trenches / PUMP", query: "PUMP" },
  { label: "🐶 Meme Meta", query: "BONK" },
  { label: "🤖 AI Agents", query: "AI" },
  { label: "💎 Bluechips", query: "JUP" },
];

export default function Scanner() {
  const [q, setQ] = useState("SOL");
  const [result, setResult] = useState<{ items: DiscoveredPair[]; error?: string; source?: string } | null>(null);
  const [loading, setLoading] = useState(false);
  const [autoScan, setAutoScan] = useState(false);
  const [countdown, setCountdown] = useState(5);
  const [scanCount, setScanCount] = useState(0);
  const [lastScanned, setLastScanned] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<RadarTab>("micro");
  const [filterText, setFilterText] = useState("");
  const [sortBy, setSortBy] = useState<"liquidity" | "mcap_desc" | "mcap_asc" | "gain_5m" | "gain_1h" | "vol_24h">("liquidity");
  const [viewMode, setViewMode] = useState<"table" | "cards">("table");
  const [ingestMsg, setIngestMsg] = useState<string | null>(null);
  const [batchIngesting, setBatchIngesting] = useState(false);
  const [ingestStatus, setIngestStatus] = useState<Record<string, "ingesting" | "success" | "error">>({});
  const [copiedMint, setCopiedMint] = useState<string | null>(null);

  const stored = useTokens();

  // Core scan execution
  const executeScan = useCallback(async (searchQuery = q) => {
    setLoading(true);
    try {
      const endpoint = searchQuery.trim()
        ? `/api/v1/discover/search?q=${encodeURIComponent(searchQuery.trim())}`
        : `/api/v1/discover/trending`;
      const r = await get<{ items: DiscoveredPair[]; error?: string; source?: string }>(endpoint);
      setResult(r);
      setLastScanned(new Date().toLocaleTimeString());
      setScanCount((c) => c + 1);
    } catch (e) {
      setResult({ items: [], error: e instanceof Error ? e.message : "Gagal memindai pasar" });
    } finally {
      setLoading(false);
    }
  }, [q]);

  // Initial load
  useEffect(() => {
    void executeScan();
  }, [executeScan]);

  // Auto-scan every 5 seconds handler
  const executeScanRef = useRef(executeScan);
  executeScanRef.current = executeScan;

  useEffect(() => {
    if (!autoScan) {
      setCountdown(5);
      return;
    }

    const timer = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          void executeScanRef.current();
          return 5;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [autoScan]);

  // Copy helper
  const copyAddress = async (mint: string) => {
    try {
      await navigator.clipboard.writeText(mint);
      setCopiedMint(mint);
      setTimeout(() => setCopiedMint(null), 2000);
    } catch {
      // fallback ignore
    }
  };

  // Ingest single token
  const handleIngestSingle = async (mint: string) => {
    setIngestStatus((prev) => ({ ...prev, [mint]: "ingesting" }));
    try {
      const res = await fetch(`/api/v1/discover/ingest?q=${encodeURIComponent(mint)}`, { method: "POST" });
      const body = (await res.json()) as { ingested?: number; tokens?: number; error?: string };
      if (body.error) {
        setIngestStatus((prev) => ({ ...prev, [mint]: "error" }));
      } else {
        setIngestStatus((prev) => ({ ...prev, [mint]: "success" }));
        void stored.refetch();
      }
    } catch {
      setIngestStatus((prev) => ({ ...prev, [mint]: "error" }));
    }
  };

  // Ingest batch
  const handleIngestAll = async () => {
    setBatchIngesting(true);
    setIngestMsg(null);
    try {
      const res = await fetch(`/api/v1/discover/ingest?q=${encodeURIComponent(q.trim() || "SOL")}`, { method: "POST" });
      const body = (await res.json()) as { ingested?: number; tokens?: number; error?: string };
      setIngestMsg(body.error ?? `Berhasil menyimpan ${body.tokens ?? body.ingested ?? 0} token ke DB lokal.`);
      void stored.refetch();
    } catch (e) {
      setIngestMsg(e instanceof Error ? e.message : "Gagal menyimpan ke DB lokal");
    } finally {
      setBatchIngesting(false);
    }
  };

  const rawItems = result?.items ?? [];

  // Group tokens by tier for tab counts
  const tierCounts = useMemo(() => {
    const counts = { micro: 0, mid: 0, graduate: 0, major: 0, all: rawItems.length };
    for (const item of rawItems) {
      const tier = getPairTier(item);
      counts[tier]++;
    }
    return counts;
  }, [rawItems]);

  // Filter items according to active tab and text search
  const filteredItems = useMemo(() => {
    let list = rawItems.filter((item) => {
      if (activeTab !== "all") {
        const tier = getPairTier(item);
        if (activeTab === "micro" && tier !== "micro") return false;
        if (activeTab === "mid" && tier !== "mid") return false;
        if (activeTab === "graduate" && tier !== "graduate") return false;
        if (activeTab === "major" && tier !== "major") return false;
      }

      if (filterText.trim()) {
        const term = filterText.toLowerCase();
        const sym = (item.symbol ?? "").toLowerCase();
        const name = (item.name ?? "").toLowerCase();
        const mint = item.mint_address.toLowerCase();
        if (!sym.includes(term) && !name.includes(term) && !mint.includes(term)) {
          return false;
        }
      }
      return true;
    });

    // Sorting
    list = [...list].sort((a, b) => {
      switch (sortBy) {
        case "liquidity":
          return (b.liquidity_usd ?? 0) - (a.liquidity_usd ?? 0);
        case "mcap_desc":
          return getEffectiveCap(b) - getEffectiveCap(a);
        case "mcap_asc":
          return getEffectiveCap(a) - getEffectiveCap(b);
        case "gain_5m":
          return (b.price_change_5m ?? -999) - (a.price_change_5m ?? -999);
        case "gain_1h":
          return (b.price_change_1h ?? -999) - (a.price_change_1h ?? -999);
        case "vol_24h":
          return (b.volume_24h ?? 0) - (a.volume_24h ?? 0);
        default:
          return 0;
      }
    });

    return list;
  }, [rawItems, activeTab, filterText, sortBy]);

  const renderTierBadge = (item: DiscoveredPair) => {
    const tier = getPairTier(item);
    switch (tier) {
      case "micro":
        return <Badge level="warn">🐣 Micro Cap</Badge>;
      case "mid":
        return <Badge level="info">⚡ Mid Cap</Badge>;
      case "graduate":
        return (
          <span className="inline-flex items-center rounded-full border border-purple-800 bg-purple-950/80 px-2 py-0.5 text-xs font-semibold text-purple-300">
            🎓 Graduate
          </span>
        );
      case "major":
        return <Badge level="ok">💎 Major</Badge>;
    }
  };

  return (
    <div className="space-y-4">
      {/* Header Banner */}
      <div className="flex flex-col justify-between gap-4 rounded-xl border border-emerald-950/60 bg-gradient-to-r from-zinc-950 via-zinc-900 to-emerald-950/30 p-4 sm:flex-row sm:items-center">
        <div>
          <div className="flex items-center gap-2">
            <span className="relative flex h-3 w-3">
              {autoScan && (
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
              )}
              <span className={`relative inline-flex h-3 w-3 rounded-full ${autoScan ? "bg-emerald-500" : "bg-zinc-600"}`} />
            </span>
            <h1 className="text-xl font-bold tracking-tight text-zinc-100">
              Trenches & Pulse Radar
            </h1>
            <Badge level="ok">SOLANA RADAR</Badge>
          </div>
          <p className="mt-1 text-xs text-zinc-400">
            Scanning real-time DEX & trenches: Micro Cap, Mid Cap, Graduate, dan Major pools.
          </p>
        </div>

        {/* Auto Scan Controls */}
        <div className="flex flex-wrap items-center gap-2">
          {/* 5-second Auto Scan Button */}
          <button
            onClick={() => setAutoScan((v) => !v)}
            className={`flex items-center gap-2 rounded-lg px-3.5 py-2 text-xs font-semibold transition-all shadow-sm ${
              autoScan
                ? "border border-emerald-500/70 bg-emerald-950/80 text-emerald-200 ring-2 ring-emerald-500/30 hover:bg-emerald-900"
                : "border border-zinc-700 bg-zinc-900 text-zinc-300 hover:border-emerald-600 hover:bg-zinc-800"
            }`}
          >
            {autoScan ? (
              <>
                <span className="relative flex h-2 w-2">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-300 opacity-80" />
                  <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-400" />
                </span>
                <span>Auto-Scan 5s: <strong className="text-emerald-300">AKTIF</strong> ({countdown}s)</span>
              </>
            ) : (
              <>
                <span>⚡ Jalankan Scan (5 Detik)</span>
              </>
            )}
          </button>

          {/* Manual Refresh Button */}
          <button
            onClick={() => executeScan()}
            disabled={loading}
            className="flex items-center gap-1.5 rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-xs font-medium text-zinc-300 hover:bg-zinc-800 disabled:opacity-50"
            title="Scan sekarang"
          >
            <span className={`text-sm ${loading ? "animate-spin" : ""}`}>↻</span>
            <span>{loading ? "Scanning…" : "Scan Sekarang"}</span>
          </button>
        </div>
      </div>

      {/* Search & Ingest Control Bar */}
      <Card title="Discovery & Filter Target">
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <div className="relative min-w-[240px] flex-1 sm:max-w-md">
              <input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && executeScan()}
                placeholder="Cari simbol, mint, atau meta (cth: SOL, BONK, PUMP)…"
                className="w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-sm text-zinc-100 placeholder:text-zinc-500 focus:border-emerald-500 focus:outline-none"
              />
            </div>
            <button
              onClick={() => executeScan()}
              disabled={loading}
              className="rounded-md bg-emerald-600 px-3.5 py-1.5 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
            >
              {loading ? "Mencari…" : "Cari Pasar"}
            </button>
            <button
              onClick={handleIngestAll}
              disabled={batchIngesting || rawItems.length === 0}
              className="rounded-md border border-zinc-700 px-3 py-1.5 text-sm text-zinc-300 hover:bg-zinc-900 disabled:opacity-50"
            >
              {batchIngesting ? "Menyimpan…" : `Ingest Semua ke DB (${rawItems.length})`}
            </button>
          </div>

          {/* Preset Quick Chips */}
          <div className="flex flex-wrap items-center gap-1.5 pt-1">
            <span className="text-[11px] font-medium text-zinc-500">Preset radar:</span>
            {PRESET_QUERIES.map((preset) => (
              <button
                key={preset.query}
                onClick={() => {
                  setQ(preset.query);
                  void executeScan(preset.query);
                }}
                className={`rounded-full px-2.5 py-0.5 text-xs transition-colors ${
                  q === preset.query
                    ? "border border-emerald-600 bg-emerald-950/80 text-emerald-300"
                    : "border border-zinc-800 bg-zinc-900/80 text-zinc-400 hover:border-zinc-700 hover:text-zinc-200"
                }`}
              >
                {preset.label}
              </button>
            ))}
          </div>

          {/* Status ticker */}
          <div className="flex flex-wrap items-center justify-between gap-2 border-t border-zinc-800/80 pt-2 text-xs text-zinc-400">
            <div className="flex items-center gap-3">
              <span>Sumber: <strong className="text-zinc-300">{result?.source ?? "DEX Screener"}</strong></span>
              <span>Total Pasangan: <strong className="text-zinc-300">{rawItems.length}</strong></span>
              {lastScanned && (
                <span>Terakhir Scan: <strong className="font-mono text-zinc-300">{lastScanned}</strong> (Scan ke-{scanCount})</span>
              )}
            </div>
            {ingestMsg && (
              <span className="text-emerald-400">{ingestMsg}</span>
            )}
          </div>
        </div>
      </Card>

      {/* Main Radar Tabs Navigation: Micro Cap, Mid Cap, Graduate, Major, Semua */}
      <div className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-800 pb-2">
          {/* TABS */}
          <div className="flex flex-wrap gap-1.5" role="tablist">
            {/* MICRO CAP TAB */}
            <button
              role="tab"
              aria-selected={activeTab === "micro"}
              onClick={() => setActiveTab("micro")}
              className={`flex items-center gap-2 rounded-lg px-3.5 py-2 text-xs font-semibold transition-all ${
                activeTab === "micro"
                  ? "border border-amber-500/60 bg-amber-950/40 text-amber-300 shadow-sm"
                  : "border border-transparent text-zinc-400 hover:border-zinc-800 hover:bg-zinc-900 hover:text-zinc-200"
              }`}
            >
              <span>🐣 Micro Cap</span>
              <span className="rounded-full bg-amber-900/60 px-1.5 py-0.5 text-[11px] font-mono text-amber-200">
                {tierCounts.micro}
              </span>
            </button>

            {/* MID CAP (MIDE) TAB */}
            <button
              role="tab"
              aria-selected={activeTab === "mid"}
              onClick={() => setActiveTab("mid")}
              className={`flex items-center gap-2 rounded-lg px-3.5 py-2 text-xs font-semibold transition-all ${
                activeTab === "mid"
                  ? "border border-sky-500/60 bg-sky-950/40 text-sky-300 shadow-sm"
                  : "border border-transparent text-zinc-400 hover:border-zinc-800 hover:bg-zinc-900 hover:text-zinc-200"
              }`}
            >
              <span>⚡ Mid Cap</span>
              <span className="rounded-full bg-sky-900/60 px-1.5 py-0.5 text-[11px] font-mono text-sky-200">
                {tierCounts.mid}
              </span>
            </button>

            {/* GRADUATE TAB */}
            <button
              role="tab"
              aria-selected={activeTab === "graduate"}
              onClick={() => setActiveTab("graduate")}
              className={`flex items-center gap-2 rounded-lg px-3.5 py-2 text-xs font-semibold transition-all ${
                activeTab === "graduate"
                  ? "border border-purple-500/60 bg-purple-950/40 text-purple-300 shadow-sm"
                  : "border border-transparent text-zinc-400 hover:border-zinc-800 hover:bg-zinc-900 hover:text-zinc-200"
              }`}
            >
              <span>🎓 Graduate</span>
              <span className="rounded-full bg-purple-900/60 px-1.5 py-0.5 text-[11px] font-mono text-purple-200">
                {tierCounts.graduate}
              </span>
            </button>

            {/* MAJOR TAB */}
            <button
              role="tab"
              aria-selected={activeTab === "major"}
              onClick={() => setActiveTab("major")}
              className={`flex items-center gap-2 rounded-lg px-3.5 py-2 text-xs font-semibold transition-all ${
                activeTab === "major"
                  ? "border border-emerald-500/60 bg-emerald-950/40 text-emerald-300 shadow-sm"
                  : "border border-transparent text-zinc-400 hover:border-zinc-800 hover:bg-zinc-900 hover:text-zinc-200"
              }`}
            >
              <span>💎 Major</span>
              <span className="rounded-full bg-emerald-900/60 px-1.5 py-0.5 text-[11px] font-mono text-emerald-200">
                {tierCounts.major}
              </span>
            </button>

            {/* ALL TOKENS TAB */}
            <button
              role="tab"
              aria-selected={activeTab === "all"}
              onClick={() => setActiveTab("all")}
              className={`flex items-center gap-2 rounded-lg px-3 py-2 text-xs font-medium transition-all ${
                activeTab === "all"
                  ? "border border-zinc-600 bg-zinc-800 text-zinc-200"
                  : "border border-transparent text-zinc-400 hover:border-zinc-800 hover:bg-zinc-900 hover:text-zinc-200"
              }`}
            >
              <span>Semua</span>
              <span className="rounded-full bg-zinc-800 px-1.5 py-0.5 text-[11px] font-mono text-zinc-300">
                {tierCounts.all}
              </span>
            </button>
          </div>

          {/* Sub-toolbar: Search within tab, sort, view toggle */}
          <div className="flex flex-wrap items-center gap-2">
            <input
              type="text"
              value={filterText}
              onChange={(e) => setFilterText(e.target.value)}
              placeholder="Filter simbol / mint…"
              className="w-36 rounded-md border border-zinc-800 bg-zinc-900/90 px-2 py-1 text-xs text-zinc-200 placeholder:text-zinc-500 focus:border-zinc-600 focus:outline-none sm:w-44"
            />

            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
              className="rounded-md border border-zinc-800 bg-zinc-900 px-2 py-1 text-xs text-zinc-300 focus:outline-none"
            >
              <option value="liquidity">Urutkan: Likuiditas</option>
              <option value="mcap_desc">Urutkan: Market Cap (Tinggi)</option>
              <option value="mcap_asc">Urutkan: Market Cap (Rendah)</option>
              <option value="gain_5m">Urutkan: Gainer 5m</option>
              <option value="gain_1h">Urutkan: Gainer 1h</option>
              <option value="vol_24h">Urutkan: Volume 24h</option>
            </select>

            <div className="flex rounded-md border border-zinc-800 bg-zinc-900 p-0.5 text-xs">
              <button
                onClick={() => setViewMode("table")}
                className={`rounded px-2 py-0.5 ${viewMode === "table" ? "bg-zinc-800 text-zinc-100 font-semibold" : "text-zinc-400 hover:text-zinc-200"}`}
                title="Tampilan Tabel"
              >
                Tabel
              </button>
              <button
                onClick={() => setViewMode("cards")}
                className={`rounded px-2 py-0.5 ${viewMode === "cards" ? "bg-zinc-800 text-zinc-100 font-semibold" : "text-zinc-400 hover:text-zinc-200"}`}
                title="Tampilan Kartu"
              >
                Kartu
              </button>
            </div>
          </div>
        </div>

        {/* Tab Descriptor Bar */}
        <div className="flex items-center justify-between text-xs text-zinc-400">
          <p>
            {activeTab === "micro" && "🐣 Micro Cap (<$100K MC): Token trenches awal, volatilitas tinggi, peluang multiplier awal."}
            {activeTab === "mid" && "⚡ Mid Cap ($100K - $1M MC): Token yang sedang ekspansi likuiditas & volume perdagangan."}
            {activeTab === "graduate" && "🎓 Graduate: Token yang telah lulus bonding curve & migrasi ke Raydium / AMM pool."}
            {activeTab === "major" && "💎 Major (>$1M MC): Token mapan & bluechip Solana dengan likuiditas dalam."}
            {activeTab === "all" && "🌐 Menampilkan semua token aktif yang terdeteksi pada radar."}
          </p>
          <span className="font-mono text-zinc-500">
            {filteredItems.length} dari {rawItems.length} ditampilkan
          </span>
        </div>

        {/* Radar Token Results */}
        {result?.error && (
          <div className="rounded-lg border border-amber-900 bg-amber-950/40 p-3 text-sm text-amber-300">
            Provider Notice: {result.error}
          </div>
        )}

        {filteredItems.length === 0 ? (
          <div className="rounded-xl border border-dashed border-zinc-800 p-8 text-center">
            <p className="text-sm text-zinc-400">
              {loading
                ? "Memindai radar…"
                : `Tidak ada token pada kategori "${activeTab.toUpperCase()}". Coba ubah pencarian atau pilih tab lain.`}
            </p>
          </div>
        ) : viewMode === "table" ? (
          /* Table View */
          <div className="overflow-x-auto rounded-xl border border-zinc-800 bg-zinc-950">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-zinc-800 bg-zinc-900/60 text-[11px] uppercase tracking-wider text-zinc-400">
                <tr>
                  <th className="py-2.5 pl-3 pr-2">Token</th>
                  <th className="px-2 py-2.5">Tier</th>
                  <th className="px-2 py-2.5">DEX</th>
                  <th className="px-2 py-2.5 text-right">Harga</th>
                  <th className="px-2 py-2.5 text-right">Market Cap</th>
                  <th className="px-2 py-2.5 text-right">Likuiditas</th>
                  <th className="px-2 py-2.5 text-right">5m</th>
                  <th className="px-2 py-2.5 text-right">1h</th>
                  <th className="px-2 py-2.5 text-right">Vol 24h</th>
                  <th className="py-2.5 pl-2 pr-3 text-right">Aksi</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/60">
                {filteredItems.map((item) => {
                  const cap = getEffectiveCap(item);
                  const isIngested = ingestStatus[item.mint_address] === "success";
                  const isIngesting = ingestStatus[item.mint_address] === "ingesting";

                  return (
                    <tr
                      key={item.pair_address || item.mint_address}
                      className="group transition-colors hover:bg-zinc-900/40"
                    >
                      {/* Token Info */}
                      <td className="py-2 pl-3 pr-2">
                        <div className="flex flex-col">
                          <div className="flex items-center gap-1.5">
                            <Link
                              to={`/tokens/${item.mint_address}`}
                              className="font-semibold text-emerald-300 hover:underline"
                            >
                              {item.symbol ?? "UNKNOWN"}
                            </Link>
                            {item.name && (
                              <span className="hidden max-w-[120px] truncate text-xs text-zinc-400 sm:inline">
                                {item.name}
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-1">
                            <span className="font-mono text-[11px] text-zinc-500">
                              {item.mint_address.slice(0, 4)}…{item.mint_address.slice(-4)}
                            </span>
                            <button
                              onClick={() => copyAddress(item.mint_address)}
                              className="text-[10px] text-zinc-500 hover:text-zinc-300"
                              title="Salin mint address"
                            >
                              {copiedMint === item.mint_address ? "✓" : "📋"}
                            </button>
                            <a
                              href={`https://solscan.io/token/${item.mint_address}`}
                              target="_blank"
                              rel="noreferrer"
                              className="text-[10px] text-zinc-500 hover:text-emerald-400"
                              title="Buka di Solscan"
                            >
                              ↗
                            </a>
                          </div>
                        </div>
                      </td>

                      {/* Tier Badge */}
                      <td className="px-2 py-2 whitespace-nowrap">
                        {renderTierBadge(item)}
                      </td>

                      {/* DEX */}
                      <td className="px-2 py-2 whitespace-nowrap">
                        <span className="rounded bg-zinc-900 px-1.5 py-0.5 font-mono text-[11px] uppercase text-zinc-400 border border-zinc-800">
                          {item.dex_id ?? "DEX"}
                        </span>
                      </td>

                      {/* Price */}
                      <td className="px-2 py-2 text-right font-mono text-xs text-zinc-200 whitespace-nowrap">
                        {fmtPrice(item.price_usd)}
                      </td>

                      {/* Market Cap */}
                      <td className="px-2 py-2 text-right font-mono text-xs text-zinc-200 whitespace-nowrap">
                        {fmtCompact(cap)}
                      </td>

                      {/* Liquidity */}
                      <td className="px-2 py-2 text-right font-mono text-xs text-zinc-300 whitespace-nowrap">
                        {fmtCompact(item.liquidity_usd)}
                      </td>

                      {/* 5m Change */}
                      <td
                        className={`px-2 py-2 text-right font-mono text-xs whitespace-nowrap ${
                          (item.price_change_5m ?? 0) >= 0 ? "text-emerald-300" : "text-rose-400"
                        }`}
                      >
                        {fmtPct(item.price_change_5m)}
                      </td>

                      {/* 1h Change */}
                      <td
                        className={`px-2 py-2 text-right font-mono text-xs whitespace-nowrap ${
                          (item.price_change_1h ?? 0) >= 0 ? "text-emerald-300" : "text-rose-400"
                        }`}
                      >
                        {fmtPct(item.price_change_1h)}
                      </td>

                      {/* 24h Volume */}
                      <td className="px-2 py-2 text-right font-mono text-xs text-zinc-400 whitespace-nowrap">
                        {fmtCompact(item.volume_24h)}
                      </td>

                      {/* Actions */}
                      <td className="py-2 pl-2 pr-3 text-right whitespace-nowrap">
                        <div className="flex items-center justify-end gap-1.5">
                          <Link
                            to={`/tokens/${item.mint_address}`}
                            className="rounded border border-zinc-700 bg-zinc-900 px-2 py-1 text-xs text-emerald-300 hover:border-emerald-600 hover:bg-emerald-950/40"
                          >
                            Analisis
                          </Link>
                          <button
                            onClick={() => handleIngestSingle(item.mint_address)}
                            disabled={isIngesting || isIngested}
                            className={`rounded border px-2 py-1 text-xs transition-colors ${
                              isIngested
                                ? "border-emerald-800 bg-emerald-950/60 text-emerald-300"
                                : "border-zinc-700 bg-zinc-900 text-zinc-300 hover:bg-zinc-800 disabled:opacity-50"
                            }`}
                          >
                            {isIngesting ? "…" : isIngested ? "✓ Tersimpan" : "+ Ingest"}
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          /* Cards Grid View */
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {filteredItems.map((item) => {
              const cap = getEffectiveCap(item);
              const isIngested = ingestStatus[item.mint_address] === "success";
              const isIngesting = ingestStatus[item.mint_address] === "ingesting";

              return (
                <div
                  key={item.pair_address || item.mint_address}
                  className="flex flex-col justify-between rounded-xl border border-zinc-800 bg-zinc-950 p-3.5 shadow-sm transition-all hover:border-zinc-700"
                >
                  <div className="space-y-2">
                    <div className="flex items-start justify-between gap-1">
                      <div>
                        <div className="flex items-center gap-1.5">
                          <Link
                            to={`/tokens/${item.mint_address}`}
                            className="text-base font-bold text-emerald-300 hover:underline"
                          >
                            {item.symbol ?? "UNKNOWN"}
                          </Link>
                          <span className="rounded bg-zinc-900 px-1 py-0.5 text-[10px] font-mono uppercase text-zinc-400 border border-zinc-800">
                            {item.dex_id ?? "DEX"}
                          </span>
                        </div>
                        <p className="max-w-[180px] truncate text-xs text-zinc-400">
                          {item.name ?? "—"}
                        </p>
                      </div>
                      <div>{renderTierBadge(item)}</div>
                    </div>

                    <div className="flex items-center justify-between font-mono text-xs text-zinc-400">
                      <span>Harga:</span>
                      <span className="text-zinc-100">{fmtPrice(item.price_usd)}</span>
                    </div>

                    <div className="grid grid-cols-2 gap-2 rounded-lg border border-zinc-800/80 bg-zinc-900/50 p-2 text-xs">
                      <div>
                        <p className="text-[10px] uppercase text-zinc-500">Market Cap</p>
                        <p className="font-mono font-semibold text-zinc-200">{fmtCompact(cap)}</p>
                      </div>
                      <div>
                        <p className="text-[10px] uppercase text-zinc-500">Likuiditas</p>
                        <p className="font-mono font-semibold text-zinc-200">{fmtCompact(item.liquidity_usd)}</p>
                      </div>
                      <div>
                        <p className="text-[10px] uppercase text-zinc-500">Change 5m</p>
                        <p
                          className={`font-mono font-semibold ${
                            (item.price_change_5m ?? 0) >= 0 ? "text-emerald-400" : "text-rose-400"
                          }`}
                        >
                          {fmtPct(item.price_change_5m)}
                        </p>
                      </div>
                      <div>
                        <p className="text-[10px] uppercase text-zinc-500">Change 1h</p>
                        <p
                          className={`font-mono font-semibold ${
                            (item.price_change_1h ?? 0) >= 0 ? "text-emerald-400" : "text-rose-400"
                          }`}
                        >
                          {fmtPct(item.price_change_1h)}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center justify-between text-[11px] text-zinc-500">
                      <span className="font-mono">
                        {item.mint_address.slice(0, 6)}…{item.mint_address.slice(-4)}
                      </span>
                      <button
                        onClick={() => copyAddress(item.mint_address)}
                        className="hover:text-zinc-300"
                      >
                        {copiedMint === item.mint_address ? "Disalin ✓" : "Salin mint"}
                      </button>
                    </div>
                  </div>

                  <div className="mt-3 flex items-center gap-1.5 border-t border-zinc-800/80 pt-2.5">
                    <Link
                      to={`/tokens/${item.mint_address}`}
                      className="flex-1 rounded-md border border-zinc-700 bg-zinc-900 py-1 text-center text-xs font-medium text-emerald-300 hover:border-emerald-600 hover:bg-emerald-950/30"
                    >
                      Detail & Analisis
                    </Link>
                    <button
                      onClick={() => handleIngestSingle(item.mint_address)}
                      disabled={isIngesting || isIngested}
                      className={`rounded-md border px-2.5 py-1 text-xs font-medium transition-colors ${
                        isIngested
                          ? "border-emerald-800 bg-emerald-950/60 text-emerald-300"
                          : "border-zinc-700 bg-zinc-900 text-zinc-300 hover:bg-zinc-800 disabled:opacity-50"
                      }`}
                    >
                      {isIngesting ? "…" : isIngested ? "✓" : "+ Ingest"}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Local DB Ingested Tokens Card */}
      <Card
        title="Token Tersimpan di Database Lokal"
        action={
          <button
            onClick={() => stored.refetch()}
            className="text-xs text-zinc-400 hover:text-emerald-300"
          >
            ↻ Refresh DB
          </button>
        }
      >
        <QueryState
          isLoading={stored.isLoading}
          isError={stored.isError}
          error={stored.error}
          isEmpty={(stored.data?.items.length ?? 0) === 0}
          emptyText="Belum ada token tersimpan di DB lokal. Klik '+ Ingest' pada radar di atas untuk menyimpan token ke database bot."
        >
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-800 text-left text-xs text-zinc-500">
                  <th className="py-1.5">Token</th>
                  <th className="text-right">Harga</th>
                  <th className="text-right">Likuiditas</th>
                  <th className="text-right">1h Change</th>
                  <th className="text-right">Status Data</th>
                  <th className="text-right pr-1">Aksi</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/60">
                {(stored.data?.items ?? []).slice(0, 20).map((t) => (
                  <tr key={t.id} className="hover:bg-zinc-900/30">
                    <td className="py-2">
                      <Link
                        to={`/tokens/${t.mint_address}`}
                        className="font-medium text-emerald-300 hover:underline"
                      >
                        {t.symbol ?? t.mint_address.slice(0, 8)}
                      </Link>
                      <span className="ml-2 font-mono text-xs text-zinc-500">
                        {t.mint_address.slice(0, 8)}…
                      </span>
                    </td>
                    <td className="text-right font-mono text-xs">{fmtUsd(t.price_usd, 6)}</td>
                    <td className="text-right font-mono text-xs">{fmtUsd(t.liquidity_usd, 0)}</td>
                    <td
                      className={`text-right font-mono text-xs ${
                        (t.price_change_1h ?? 0) >= 0 ? "text-emerald-300" : "text-rose-400"
                      }`}
                    >
                      {fmtPct(t.price_change_1h)}
                    </td>
                    <td className="text-right text-xs">
                      {t.stale ? <Badge level="warn">STALE</Badge> : <Badge level="ok">FRESH</Badge>}
                    </td>
                    <td className="text-right pr-1">
                      <Link
                        to={`/tokens/${t.mint_address}`}
                        className="text-xs text-emerald-400 hover:underline"
                      >
                        Detail →
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </QueryState>
      </Card>
    </div>
  );
}
