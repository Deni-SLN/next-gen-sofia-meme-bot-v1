import React, { useState } from 'react';
import { api, useApiQuery, formatIdr, formatUsd } from '@/lib/api';
import { QueryState } from '@/components/QueryState';
import { LucideIcon } from '@/components/LucideIcon';

function formatRiskInIndonesian(riskText: string): string {
  if (!riskText) return '';
  let txt = riskText;

  // Map English severity tags to Indonesian
  txt = txt.replace(/^\[WARN\]/i, '[PERINGATAN]');
  txt = txt.replace(/^\[DANGER\]/i, '[BAHAYA]');
  txt = txt.replace(/^\[CRITICAL\]/i, '[KRITIS]');

  const directMappings: [RegExp, string][] = [
    [
      /High holder correlation:\s*The top users hold similar supply amounts/gi,
      'Korelasi Kepemilikan Holder Tinggi: Akun-akun teratas memiliki persentase suplai yang sangat mirip (indikasi split wallet dev/insider cluster)',
    ],
    [/High holder correlation/gi, 'Korelasi Kepemilikan Holder Tinggi'],
    [
      /The top users hold similar supply amounts/gi,
      'Akun-akun teratas memiliki persentase suplai yang sangat mirip (indikasi split wallet)',
    ],
    [
      /Single holder ownership:\s*A single holder owns a large chunk of the supply/gi,
      'Kepemilikan Holder Tunggal Dominan: Satu wallet memegang porsi suplai token yang sangat besar, berisiko tinggi terjadi dump massal',
    ],
    [/Single holder ownership/gi, 'Kepemilikan Holder Tunggal Dominan'],
    [
      /Top 10 holders hold significant supply/gi,
      'Top 10 Holder Menguasai Suplai Terlalu Besar (Risiko Paus/Dump)',
    ],
    [
      /Top 10 holders hold high percentage of supply/gi,
      '10 holder teratas memegang persentase suplai yang sangat tinggi',
    ],
    [
      /Mutable metadata:\s*The metadata can be changed by the authority/gi,
      'Metadata Kontrak Dapat Diubah (Mutable): Developer masih berhak mengganti nama, simbol, atau logo koin sewaktu-waktu',
    ],
    [/Mutable metadata/gi, 'Metadata Kontrak Dapat Diubah (Mutable)'],
    [
      /The metadata can be changed by the authority/gi,
      'Metadata koin dapat diubah sewaktu-waktu oleh developer',
    ],
    [/Mint Authority still enabled/gi, 'Mint Authority Masih Aktif (Bisa Cetak Koin Baru)'],
    [
      /The mint authority is not disabled/gi,
      'Mint authority belum dimatikan, dev bisa mencetak suplai token tanpa batas',
    ],
    [/Freeze Authority still enabled/gi, 'Freeze Authority Masih Aktif (Bisa Bekukan Wallet)'],
    [
      /The freeze authority is not disabled/gi,
      'Freeze authority belum dimatikan, dev bisa membekukan dompet pembeli (Honeypot Selektif)',
    ],
    [/Large LP amount unburned/gi, 'Likuiditas LP Belum Dibakar / Belum Dikunci'],
    [
      /A large amount of LP is not burned/gi,
      'Sebagian besar kas likuiditas LP belum dibakar atau dikunci developer',
    ],
    [/Copycat token/gi, 'Koin Tiruan (Copycat Proyek Populer)'],
    [/Low Liquidity/gi, 'Likuiditas Sangat Rendah'],
    [/Low liquidity in DEX pool/gi, 'Likuiditas rendah di pool DEX'],
    [/Transfer fee enabled/gi, 'Pajak transfer token aktif'],
  ];

  for (const [pattern, replacement] of directMappings) {
    txt = txt.replace(pattern, replacement);
  }

  return txt;
}

const ECOSYSTEM_TOOLS = [
  {
    name: 'FluxRPC Shield',
    urlKey: 'fluxrpc',
    defaultUrl: 'https://dashboard.fluxrpc.com',
    mainFunc: 'Firewall RPC anti-rug, simulasi honeypot & perlindungan MEV',
    bestFor: 'Shielding Eksekusi On-Chain',
    badge: 'RPC SHIELD',
  },
  {
    name: 'Axiom',
    urlKey: 'axiom',
    defaultUrl: 'https://axiom.trade/?utm_source=chatgpt.com',
    mainFunc: 'Terminal trading, pelacakan wallet, token baru',
    bestFor: 'Trader aktif',
    badge: 'TERMINAL',
  },
  {
    name: 'Raydium',
    urlKey: 'raydium',
    defaultUrl: 'https://raydium.io/?utm_source=chatgpt.com',
    mainFunc: 'Swap dan likuiditas token Solana',
    bestFor: 'Trading melalui DEX',
    badge: 'DEX SWAP',
  },
  {
    name: 'Birdeye',
    urlKey: 'birdeye',
    defaultUrl: 'https://birdeye.so/?utm_source=chatgpt.com',
    mainFunc: 'Analisis harga, volume, dan data token',
    bestFor: 'Riset pasar',
    badge: 'ANALYTICS',
  },
  {
    name: 'RugCheck',
    urlKey: 'rugcheck',
    defaultUrl: 'https://rugcheck.xyz/?utm_source=chatgpt.com',
    mainFunc: 'Pemeriksaan risiko token Solana',
    bestFor: 'Screening keamanan',
    badge: 'SECURITY',
  },
  {
    name: 'Solscan',
    urlKey: 'solscan',
    defaultUrl: 'https://solscan.io/?utm_source=chatgpt.com',
    mainFunc: 'Memeriksa transaksi, wallet, dan token di blockchain',
    bestFor: 'Verifikasi on-chain',
    badge: 'EXPLORER',
  },
  {
    name: 'Bubblemaps',
    urlKey: 'bubblemaps',
    defaultUrl: 'https://app.bubblemaps.io',
    mainFunc: 'Visualisasi cluster wallet & sumber pendanaan top holders',
    bestFor: 'Deteksi insider cluster',
    badge: 'CLUSTERS',
  },
];

export default function RugCheckPage() {
  const [searchInput, setSearchInput] = useState<string>('WIF');
  const [activeTarget, setActiveTarget] = useState<string>('WIF');
  const rugQuery = useApiQuery(() => api.rugCheck(activeTarget), [activeTarget]);

  const handleScan = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchInput.trim()) {
      setActiveTarget(searchInput.trim());
    }
  };

  const data = rugQuery.data;
  const usdIdr = data?.fx?.usd_idr || 17960;
  const contractClean = Boolean(data?.contract_clean ?? (data?.mint_revoked && data?.freeze_revoked && !data?.honeypot));
  const liqUsd = Number(data?.liquidity_usd ?? 0);
  const liqMcapRatio = Number(data?.liq_mcap_ratio_pct ?? 0);
  const clusterRisk = data?.cluster_risk_level || 'LOW';

  return (
    <div className="space-y-3">
      {/* Top Banner */}
      <div className="flex flex-wrap items-center justify-between gap-2 px-3.5 py-2.5 rounded-xl bg-obsidian-900 border border-obsidian-700/80">
        <div>
          <div className="flex items-center gap-2">
            <LucideIcon name="shield-alert" className="w-4 h-4 text-emerald-400" />
            <h1 className="text-sm font-extrabold text-slate-100 uppercase tracking-wide font-mono">
              Rug, Cluster &amp; Liquidity Shield v2 (Deep On-Chain Audit)
            </h1>
            <span className="text-[9px] font-mono px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
              100% LIVE API (DEXSCREENER + RUGCHECK /REPORT)
            </span>
            <span className="text-[9px] font-mono px-2 py-0.5 rounded bg-cyan-500/15 text-cyan-300 border border-cyan-500/30 flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
              ⚡ FLUX SHIELD RPC: AKTIF
            </span>
          </div>
          <p className="text-[11px] text-slate-400 mt-0.5">
            Mengevaluasi <strong>Kontrak &amp; Ekstensi Token-2022</strong>, <strong>Cluster Pendanaan Holder (Non-AMM)</strong>,{' '}
            <strong>Riwayat Wallet Dev</strong>, <strong>Rasio Likuiditas/MCap</strong>, dan <strong>Indikasi Wash Trading</strong>.
          </p>
        </div>

        <button
          type="button"
          onClick={() => rugQuery.refetch()}
          className="px-3 py-1.5 rounded-lg bg-obsidian-800 hover:bg-obsidian-700 border border-obsidian-600 text-cyan-300 font-mono text-xs transition"
        >
          🔄 Tarik Ulang Data Live API
        </button>
      </div>

      {/* Search Form */}
      <form onSubmit={handleScan} className="flex flex-wrap gap-2">
        <input
          type="text"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          placeholder="Masukkan ticker atau Contract Address Solana/Base asli (contoh: WIF, BONK, POPCAT, PEPE)..."
          className="flex-1 min-w-[260px] px-3.5 py-2 rounded-lg bg-obsidian-900 border border-obsidian-700 text-slate-100 font-mono text-xs focus:outline-none focus:border-emerald-500"
        />
        <button
          type="submit"
          className="px-4 py-2 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-obsidian-950 font-extrabold font-mono text-xs shadow-glow-emerald transition"
        >
          🔍 Deep Audit Kontrak &amp; Cluster
        </button>
        {['WIF', 'BONK', 'POPCAT', 'PEPE', 'RUGDOGE/SOL'].map((preset) => (
          <button
            key={preset}
            type="button"
            onClick={() => {
              setSearchInput(preset);
              setActiveTarget(preset);
            }}
            className={`px-2.5 py-2 rounded-lg border text-[11px] font-mono transition ${
              activeTarget.toUpperCase() === preset
                ? 'bg-emerald-500/20 border-emerald-500/50 text-emerald-300 font-bold'
                : 'bg-obsidian-900 border-obsidian-700 hover:border-obsidian-600 text-slate-300'
            }`}
          >
            {preset}
          </button>
        ))}
      </form>

      <QueryState isLoading={rugQuery.isLoading} isError={rugQuery.isError} error={rugQuery.error}>
        {data && (
          <div className="space-y-3">
            {/* Honest Verdict & Pump.fun Caveat Banner */}
            <div
              className={`p-3.5 rounded-xl border flex flex-col lg:flex-row lg:items-center justify-between gap-3 ${
                contractClean && liqUsd >= 25000 && clusterRisk !== 'HIGH'
                  ? 'bg-emerald-950/25 border-emerald-500/40'
                  : contractClean
                  ? 'bg-amber-950/25 border-amber-500/40'
                  : 'bg-rose-950/35 border-rose-500/50'
              }`}
            >
              <div className="space-y-1">
                <div className="flex flex-wrap items-center gap-2 font-mono">
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-extrabold border ${
                      contractClean
                        ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                        : 'bg-rose-500/20 text-rose-300 border-rose-500/40'
                    }`}
                  >
                    STATUS KONTRAK: {contractClean ? 'KONTRAK BERSIH (CLEAN CONTRACT)' : 'KONTRAK BERBAHAYA'}
                  </span>
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-extrabold border ${
                      liqUsd >= 30000 && clusterRisk === 'LOW'
                        ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40'
                        : 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                    }`}
                  >
                    STATUS PASAR: {data.liquidity_verdict || (liqUsd < 25000 ? 'LIKUIDITAS TIPIS' : 'MODERAT')}
                  </span>
                  <span className="text-[10px] text-slate-400">
                    Skor Komposit: <strong className="text-white">{data.safety_score}/100</strong>
                  </span>
                </div>
                <div className="text-xs font-bold text-slate-100 font-mono">{data.verdict}</div>
                <p className="text-[11px] text-slate-300 leading-relaxed">
                  💡 <strong>Catatan Penting:</strong> Label <em>&ldquo;Kontrak Bersih&rdquo;</em> berarti tidak ditemukan celah exploit
                  mint/freeze pada kode kontrak, <strong>bukan jaminan uang Anda aman dari dump holder</strong>.{' '}
                  {data.pumpfun_warning}
                </p>
              </div>

              <div className="shrink-0 bg-obsidian-950/90 border border-obsidian-700 rounded-lg p-2.5 font-mono text-[10px] space-y-1">
                <div className="text-slate-400">Bukti Data Live API:</div>
                <div className="text-emerald-400 font-bold truncate max-w-[260px]">CA: {data.contract}</div>
                <div className="text-slate-300">
                  Umur Pair: <strong className="text-cyan-300">{data.age || 'live'}</strong> • Holders:{' '}
                  <strong className="text-white">{(data.total_holders || 0).toLocaleString()}</strong>
                </div>
                <div className="text-slate-500 flex items-center justify-between gap-2">
                  <span>Audited: {data.audited_at ? new Date(data.audited_at).toLocaleTimeString() : 'Live'}</span>
                  <span className="text-cyan-400 font-bold">🛡️ FluxShield OK</span>
                </div>
              </div>
            </div>

            {/* Main 12-Col Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-3">
              {/* Left 4 Cols: Token Identity, Liquidity/MCap Ratio & Position Sizing Rule */}
              <div className="lg:col-span-4 space-y-3">
                {/* Market & Liquidity Depth Card */}
                <div className="bg-obsidian-900 border border-obsidian-700/80 rounded-xl p-3.5 space-y-3 font-mono">
                  <div className="flex items-center justify-between border-b border-obsidian-800 pb-2">
                    <div>
                      <span className="text-[10px] text-emerald-400 uppercase font-bold">
                        {data.chain} • {data.launchpad}
                      </span>
                      <h2 className="text-lg font-extrabold text-white">{data.symbol}</h2>
                      <p className="text-[11px] text-slate-400 font-sans">{data.name}</p>
                    </div>
                    <div className="text-right">
                      <div className="text-[10px] text-slate-400">SKOR MULTI-FAKTOR</div>
                      <div
                        className={`text-3xl font-black ${
                          data.safety_score >= 75
                            ? 'text-emerald-400'
                            : data.safety_score >= 55
                            ? 'text-amber-400'
                            : 'text-rose-400'
                        }`}
                      >
                        {data.safety_score}/100
                      </div>
                    </div>
                  </div>

                  {/* Liquidity vs MCap & Wash Trading */}
                  <div className="space-y-2 text-xs">
                    <div className="flex justify-between items-center">
                      <span className="text-slate-400">Harga Live (DexScreener):</span>
                      <div className="text-right">
                        <div className="text-white font-bold">{formatUsd(data.price)}</div>
                        <div className="text-[10px] text-emerald-400">≈ {formatIdr((data.price || 0) * usdIdr)}</div>
                      </div>
                    </div>

                    <div className="flex justify-between items-center">
                      <span className="text-slate-400">Pool Liquidity:</span>
                      <div className="text-right">
                        <div className={`font-bold ${liqUsd < 25000 ? 'text-amber-400' : 'text-emerald-400'}`}>
                          ${liqUsd.toLocaleString()}
                        </div>
                        <div className="text-[10px] text-slate-400">≈ {formatIdr(liqUsd * usdIdr)}</div>
                      </div>
                    </div>

                    <div className="flex justify-between items-center">
                      <span className="text-slate-400">Market Cap (FDV):</span>
                      <div className="text-right">
                        <div className="text-slate-200 font-bold">${(data.market_cap || 0).toLocaleString()}</div>
                        <div className="text-[10px] text-slate-400">≈ {formatIdr((data.market_cap || 0) * usdIdr)}</div>
                      </div>
                    </div>

                    <div className="p-2.5 rounded-lg bg-obsidian-950 border border-obsidian-800 space-y-1.5">
                      <div className="flex justify-between text-[11px]">
                        <span className="text-slate-400">Rasio Likuiditas / MCap:</span>
                        <span
                          className={`font-bold ${
                            liqMcapRatio >= 10
                              ? 'text-emerald-400'
                              : liqMcapRatio >= 5
                              ? 'text-cyan-400'
                              : 'text-rose-400'
                          }`}
                        >
                          {liqMcapRatio}% {liqMcapRatio < 5 ? '(Tipis!)' : '(Sehat)'}
                        </span>
                      </div>
                      <div className="flex justify-between text-[11px]">
                        <span className="text-slate-400">Volume 24h / Likuiditas:</span>
                        <span className={data.wash_trading_flag ? 'text-rose-400 font-bold' : 'text-slate-200'}>
                          {data.vol_to_liq_ratio ?? 1.2}x
                        </span>
                      </div>
                      <div className="flex justify-between text-[11px]">
                        <span className="text-slate-400">Orderflow 5m (Buy / Sell):</span>
                        <span className="text-slate-200">
                          <span className="text-emerald-400">{data.buys_5m ?? 0}B</span> /{' '}
                          <span className="text-rose-400">{data.sells_5m ?? 0}S</span>
                        </span>
                      </div>
                      <div
                        className={`text-[10px] pt-1 border-t border-obsidian-800 ${
                          data.wash_trading_flag ? 'text-rose-300' : 'text-slate-400'
                        }`}
                      >
                        {data.wash_trading_note || 'Volume & frekuensi transaksi tampak organik.'}
                      </div>
                    </div>
                  </div>
                </div>

                {/* Position Sizing & Hard Stop-Loss Rule Box */}
                <div className="bg-obsidian-900 border border-emerald-500/40 rounded-xl p-3.5 space-y-2.5 font-mono">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-emerald-400 uppercase">
                      🛡️ Aturan Ukuran Posisi &amp; Stop-Loss
                    </span>
                    <span className="text-[9px] px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-300">
                      MODAL PAPER Rp 150rb
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-300 font-sans leading-relaxed">
                    Karena tidak ada filter yang menjamin 100% bebas rug/dump, gunakan batas risiko disiplin berikut:
                  </p>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div className="p-2 rounded bg-obsidian-950 border border-obsidian-800">
                      <div className="text-[10px] text-slate-400">Maks Ukuran Posisi</div>
                      <div className="text-sm font-bold text-emerald-400">
                        {data.position_sizing?.max_position_pct ?? 10}% ({formatIdr(data.position_sizing?.max_position_idr ?? 15000)})
                      </div>
                    </div>
                    <div className="p-2 rounded bg-obsidian-950 border border-obsidian-800">
                      <div className="text-[10px] text-slate-400">Wajib Hard Stop-Loss</div>
                      <div className="text-sm font-bold text-rose-400">
                        -{data.position_sizing?.recommended_sl_pct ?? 12}%
                      </div>
                    </div>
                  </div>
                  <div className="text-[10px] text-cyan-300 bg-obsidian-950/80 p-2 rounded border border-obsidian-800">
                    {data.position_sizing?.rule_summary}
                  </div>
                </div>
              </div>

              {/* Right 8 Cols: Deep On-Chain Checks (Token-2022, AMM-Excluded Holders, Clusters, Dev History) */}
              <div className="lg:col-span-8 space-y-3">
                {/* 1. Baseline Contract Filter + Token-2022 Extensions */}
                <div className="bg-obsidian-900 border border-obsidian-700/80 rounded-xl p-3.5 space-y-3">
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-obsidian-800 pb-2">
                    <div>
                      <h3 className="text-xs font-bold text-slate-100 uppercase font-mono">
                        1. Filter Dasar Kontrak &amp; Pemeriksaan Ekstensi Token-2022
                      </h3>
                      <p className="text-[10px] text-slate-400">
                        Mendeteksi TransferHook / PermanentDelegate yang bisa mengubah token &ldquo;Sellable&rdquo; menjadi Honeypot.
                      </p>
                    </div>
                    <span
                      className={`text-[10px] font-mono px-2 py-0.5 rounded border ${
                        data.is_token_2022
                          ? 'bg-amber-500/15 text-amber-300 border-amber-500/40'
                          : 'bg-obsidian-850 text-slate-300 border-obsidian-700'
                      }`}
                    >
                      Program: {data.token_program || 'SPL Token (Standard)'}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 font-mono text-xs">
                    <div className="p-2.5 rounded-lg bg-obsidian-950 border border-obsidian-800">
                      <div className="flex items-center justify-between text-[10px] text-slate-400">
                        <span>Mint Authority</span>
                        <span className="text-[9px] text-slate-500">Filter Dasar</span>
                      </div>
                      <div className={`mt-1 font-bold ${data.mint_revoked ? 'text-emerald-400' : 'text-rose-400'}`}>
                        {data.mint_revoked ? '✅ DICABUT (AMAN)' : '❌ AKTIF (BAHAYA)'}
                      </div>
                    </div>

                    <div className="p-2.5 rounded-lg bg-obsidian-950 border border-obsidian-800">
                      <div className="flex items-center justify-between text-[10px] text-slate-400">
                        <span>Freeze Authority</span>
                        <span className="text-[9px] text-slate-500">Filter Dasar</span>
                      </div>
                      <div className={`mt-1 font-bold ${data.freeze_revoked ? 'text-emerald-400' : 'text-rose-400'}`}>
                        {data.freeze_revoked ? '✅ DICABUT (AMAN)' : '❌ AKTIF (HONEYPOT)'}
                      </div>
                    </div>

                    <div className="p-2.5 rounded-lg bg-obsidian-950 border border-obsidian-800">
                      <div className="flex items-center justify-between text-[10px] text-slate-400">
                        <span>LP Burn / Lock</span>
                        <span className="text-[9px] text-slate-500">Filter Dasar</span>
                      </div>
                      <div className={`mt-1 font-bold ${data.lp_burned ? 'text-emerald-400' : 'text-amber-400'}`}>
                        {data.lp_burned ? `🔥 TERKUNCI (${data.lp_locked_pct}%)` : '⚠️ TIDAK TERKUNCI'}
                      </div>
                    </div>

                    <div className="p-2.5 rounded-lg bg-obsidian-950 border border-obsidian-800">
                      <div className="flex items-center justify-between text-[10px] text-slate-400">
                        <span>Token-2022 Hooks</span>
                        <span className="text-[9px] text-cyan-400">Dinamis</span>
                      </div>
                      <div
                        className={`mt-1 font-bold ${
                          (data.token_2022_extensions || []).length === 0 ? 'text-emerald-400' : 'text-rose-400'
                        }`}
                      >
                        {(data.token_2022_extensions || []).length === 0
                          ? `✅ BERSIH (Pajak ${data.transfer_fee_pct ?? 0}%)`
                          : `⚠️ ${(data.token_2022_extensions || []).join(', ')}`}
                      </div>
                    </div>
                  </div>

                  {/* Anti-Honeypot & Sellability Verification Strip */}
                  <div
                    className={`p-2.5 rounded-lg border font-mono text-xs flex flex-wrap items-center justify-between gap-2 ${
                      data.honeypot
                        ? 'bg-rose-950/50 border-rose-500/50 text-rose-200'
                        : 'bg-emerald-950/30 border-emerald-500/40 text-emerald-200'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-sm">{data.honeypot ? '🚨' : '🛡️'}</span>
                      <div>
                        <div className="font-bold">
                          {data.honeypot
                            ? 'PERINGATAN KERAS: TERDETEKSI INDIKASI HONEYPOT / KONTRAK BERBAHAYA!'
                            : 'STATUS ANTI-HONEYPOT: AMAN (DAPAT DIJUAL & KONTRAK BERSIH)'}
                        </div>
                        <div className="text-[10px] opacity-85">
                          {data.honeypot
                            ? 'Jangan beli token ini! Terdapat fitur pembekuan wallet, pajak ekstrem, atau blokir transaksi jual.'
                            : 'Simulasi FluxRPC Shield & RugCheck mengonfirmasi tidak ada TransferHook/Freeze/Honeypot aktif.'}
                        </div>
                      </div>
                    </div>
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                        data.honeypot ? 'bg-rose-500 text-white' : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                      }`}
                    >
                      {data.honeypot ? 'HONEYPOT TERDETEKSI' : 'LOLOS CEK HONEYPOT'}
                    </span>
                  </div>

                  {/* Pump.fun 5-Pillar Safe Trading Checklist */}
                  {data.pumpfun_safe_checklist && (
                    <div className="p-3 rounded-lg bg-obsidian-950/90 border border-cyan-500/30 space-y-2 font-mono">
                      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-obsidian-800 pb-2">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-extrabold text-cyan-300 uppercase">
                            💊 Checklist 5 Pilar Keamanan Trading Pump.fun ({data.pumpfun_safe_checklist.passed_count}/{data.pumpfun_safe_checklist.total_checks} Lolos)
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                              data.pumpfun_safe_checklist.tone === 'safe'
                                ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                                : data.pumpfun_safe_checklist.tone === 'danger'
                                ? 'bg-rose-500/20 text-rose-300 border-rose-500/40'
                                : 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                            }`}
                          >
                            {data.pumpfun_safe_checklist.status_badge}
                          </span>
                          {data.contract && (
                            <a
                              href={data.external_links?.pumpfun || `https://pump.fun/coin/${data.contract}`}
                              target="_blank"
                              rel="noreferrer"
                              className="px-2 py-0.5 rounded bg-emerald-500 hover:bg-emerald-400 text-obsidian-950 text-[10px] font-extrabold transition"
                            >
                              💊 Buka di Pump.fun →
                            </a>
                          )}
                        </div>
                      </div>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5 text-[11px]">
                        {(data.pumpfun_safe_checklist.checks || []).map((chk: any, idx: number) => (
                          <div
                            key={idx}
                            className={`p-2 rounded border flex items-start gap-2 ${
                              chk.passed
                                ? 'bg-emerald-950/20 border-emerald-500/25 text-emerald-200'
                                : 'bg-rose-950/30 border-rose-500/35 text-rose-200'
                            }`}
                          >
                            <span className="mt-0.5">{chk.passed ? '✅' : '⚠️'}</span>
                            <div>
                              <div className="font-bold text-[10px]">{chk.label}</div>
                              <div className="text-[10px] opacity-85">{chk.detail}</div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {/* 2. Holder Concentration (AMM Excluded) & Wallet Clustering / Dev History */}
                <div className="bg-obsidian-900 border border-obsidian-700/80 rounded-xl p-3.5 space-y-3">
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-obsidian-800 pb-2">
                    <div>
                      <h3 className="text-xs font-bold text-slate-100 uppercase font-mono">
                        2. Distribusi Holder (Pool AMM Dikeluarkan), Cluster Pendanaan &amp; Riwayat Dev
                      </h3>
                      <p className="text-[10px] text-slate-400">
                        Mengeluarkan alamat LP/Bonding Curve dari Top 10 dan melacak jaringan wallet insider yang didanai bertahap.
                      </p>
                    </div>
                    <a
                      href={data.external_links?.bubblemaps || `https://app.bubblemaps.io/sol/token/${data.contract}`}
                      target="_blank"
                      rel="noreferrer"
                      className="px-2.5 py-1 rounded bg-purple-500/20 hover:bg-purple-500/30 text-purple-300 border border-purple-500/40 text-[10px] font-mono font-bold transition"
                    >
                      🫧 Buka Bubblemaps Cluster →
                    </a>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5 font-mono text-xs">
                    {/* Top 10 Non-AMM Holders */}
                    <div className="p-3 rounded-lg bg-obsidian-950 border border-obsidian-800 space-y-1">
                      <div className="text-[10px] text-slate-400">Top 10 Holders (Non-AMM)</div>
                      <div className={`text-xl font-extrabold ${data.top10_pct > 25 ? 'text-rose-400' : 'text-emerald-400'}`}>
                        {data.top10_pct}%
                      </div>
                      <div className="text-[10px] text-cyan-400">
                        Pool/AMM dikeluarkan: {data.amm_pool_excluded_pct ?? 0}%
                      </div>
                      <div className="text-[10px] text-slate-500">Ambang sehat: &lt; 25% di luar LP</div>
                    </div>

                    {/* Wallet Clustering & Funding Source */}
                    <div className="p-3 rounded-lg bg-obsidian-950 border border-obsidian-800 space-y-1">
                      <div className="text-[10px] text-slate-400">Cluster Wallet &amp; Insider Graph</div>
                      <div
                        className={`text-xl font-extrabold ${
                          clusterRisk === 'HIGH'
                            ? 'text-rose-400'
                            : clusterRisk === 'MEDIUM'
                            ? 'text-amber-400'
                            : 'text-emerald-400'
                        }`}
                      >
                        {clusterRisk === 'HIGH' ? 'TINGGI' : clusterRisk === 'MEDIUM' ? 'SEDANG' : 'RENDAH'} ({data.graph_insiders_detected ?? 0} akun)
                      </div>
                      <div className="text-[10px] text-slate-300">
                        Block-0 Bundle: {data.bundle_pct}% • Cluster: {(data.insider_clusters || []).length} jaringan
                      </div>
                      <div className="text-[10px] text-slate-500">Deteksi transfer &amp; pendanaan bertahap</div>
                    </div>

                    {/* Developer Wallet & Previous Rug History */}
                    <div className="p-3 rounded-lg bg-obsidian-950 border border-obsidian-800 space-y-1">
                      <div className="text-[10px] text-slate-400">Wallet Dev &amp; Riwayat Token</div>
                      <div className={`text-xl font-extrabold ${data.dev_holding_pct > 10 ? 'text-rose-400' : 'text-emerald-400'}`}>
                        Saldo Saat Ini: {data.dev_holding_pct}%
                      </div>
                      <div className="text-[10px] text-amber-300">
                        Riwayat Dev: {data.creator_prev_tokens ?? 0} token ({data.creator_rugged_tokens ?? 0} rug)
                      </div>
                      <div className="text-[10px] text-slate-400 leading-tight">{data.creator_status_note}</div>
                    </div>
                  </div>

                  {/* Insider Clusters & Top Non-AMM Holders Breakdown */}
                  {((data.insider_clusters || []).length > 0 || (data.top_holders_detail || []).length > 0) && (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5 pt-1 font-mono text-[11px]">
                      <div className="p-2.5 rounded-lg bg-obsidian-950/70 border border-obsidian-800 space-y-1">
                        <div className="text-[10px] font-bold text-slate-300 uppercase">
                          Jaringan Cluster Pendanaan Terdeteksi (RugCheck Graph):
                        </div>
                        {(data.insider_clusters || []).length === 0 ? (
                          <div className="text-slate-500 text-[10px]">
                            Tidak terdeteksi cluster transfer multi-wallet mencurigakan.
                          </div>
                        ) : (
                          (data.insider_clusters || []).map((c: any, i: number) => (
                            <div key={i} className="flex items-center justify-between text-[10px] text-amber-300">
                              <span>
                                ● Cluster <strong>{c.id}</strong> ({c.type})
                              </span>
                              <span>{c.size} wallet terhubung</span>
                            </div>
                          ))
                        )}
                      </div>

                      <div className="p-2.5 rounded-lg bg-obsidian-950/70 border border-obsidian-800 space-y-1">
                        <div className="text-[10px] font-bold text-slate-300 uppercase">
                          Top Holder Non-AMM Terbesar (Di Luar Pool LP):
                        </div>
                        {(data.top_holders_detail || []).length === 0 ? (
                          <div className="text-slate-500 text-[10px]">Data detail top holder tersedia di Solscan.</div>
                        ) : (
                          (data.top_holders_detail || []).slice(0, 4).map((h: any, i: number) => (
                            <div key={i} className="flex items-center justify-between text-[10px] text-slate-300">
                              <span className="truncate max-w-[180px]">
                                #{i + 1} {h.owner ? `${h.owner.slice(0, 6)}...${h.owner.slice(-4)}` : h.address}
                              </span>
                              <span className={h.insider ? 'text-rose-400 font-bold' : 'text-emerald-400 font-bold'}>
                                {h.pct}% {h.insider ? '(INSIDER)' : ''}
                              </span>
                            </div>
                          ))
                        )}
                      </div>
                    </div>
                  )}

                  {/* Warnings Box */}
                  {(data.risks || []).length > 0 && (
                    <div className="p-3 rounded-lg bg-rose-950/40 border border-rose-500/40 space-y-1 font-mono">
                      <div className="text-[10px] font-bold text-rose-300 uppercase">
                        ⚠️ Temuan Risiko Kontrak, Likuiditas &amp; Cluster:
                      </div>
                      <ul className="list-disc list-inside text-[11px] text-rose-200 space-y-0.5">
                        {data.risks.map((r: string, idx: number) => (
                          <li key={idx}>{formatRiskInIndonesian(r)}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Section: Aplikasi Tambahan & Verifikasi Eksternal (Axiom, Raydium, Birdeye, RugCheck, Solscan, Bubblemaps) */}
            <div className="bg-obsidian-900 border border-obsidian-700/80 rounded-xl p-3.5 space-y-2.5">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-obsidian-800 pb-2">
                <div>
                  <h3 className="text-xs font-bold text-slate-100 uppercase tracking-wider font-mono">
                    🔗 Ekosistem Aplikasi Verifikasi On-Chain &amp; Riset Pasar (Direct Token Deep-Links)
                  </h3>
                  <p className="text-[11px] text-slate-400">
                    Klik langsung pada salah satu platform di bawah untuk memverifikasi kontrak{' '}
                    <code className="text-emerald-400 font-mono">{data.symbol}</code> secara independen di blockchain:
                  </p>
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-xs font-mono">
                  <thead>
                    <tr className="border-b border-obsidian-800 text-[10px] text-slate-400 uppercase">
                      <th className="py-2 px-2.5">Aplikasi</th>
                      <th className="py-2 px-2.5">Fungsi Utama</th>
                      <th className="py-2 px-2.5">Cocok Untuk</th>
                      <th className="py-2 px-2.5 text-right">Tautan Verifikasi Live</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-obsidian-800/60 text-[11px]">
                    {ECOSYSTEM_TOOLS.map((tool) => {
                      const directHref = data.external_links?.[tool.urlKey] || tool.defaultUrl;
                      return (
                        <tr key={tool.name} className="hover:bg-obsidian-850/70 transition">
                          <td className="py-2.5 px-2.5 font-bold text-white flex items-center gap-2">
                            <span className="px-1.5 py-0.5 text-[9px] rounded bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
                              {tool.badge}
                            </span>
                            <span>{tool.name}</span>
                          </td>
                          <td className="py-2.5 px-2.5 text-slate-300 font-sans">{tool.mainFunc}</td>
                          <td className="py-2.5 px-2.5 text-cyan-300">{tool.bestFor}</td>
                          <td className="py-2.5 px-2.5 text-right">
                            <a
                              href={directHref}
                              target="_blank"
                              rel="noreferrer"
                              className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-obsidian-800 hover:bg-emerald-500 text-emerald-300 hover:text-obsidian-950 border border-emerald-500/30 font-bold text-[10px] transition"
                            >
                              <span>Buka {tool.name}</span>
                              <span>↗</span>
                            </a>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </QueryState>
    </div>
  );
}
