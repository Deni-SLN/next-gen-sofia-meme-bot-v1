import React, { useState, useEffect, useMemo } from 'react';
import Head from 'next/head';
import { api, useApiQuery, formatIdr, formatUsd, getTradingMode } from '@/lib/api';
import { QueryState } from '@/components/QueryState';
import { LucideIcon } from '@/components/LucideIcon';
import { useUltrawide } from '@/lib/useUltrawide';

export default function PulsePage() {
  const isUltrawide = useUltrawide();
  const pulseQuery = useApiQuery(() => api.getPulse(), []);
  const [presetIdr, setPresetIdr] = useState<number>(30000);
  const [mode, setMode] = useState<'PAPER' | 'LIVE'>('PAPER');
  const [snipeFeedback, setSnipeFeedback] = useState<string>('');
  const [snipeError, setSnipeError] = useState<string>('');
  const [minSafety, setMinSafety] = useState<number>(0);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [activeColumnTab, setActiveColumnTab] = useState<'ALL' | 'NEW' | 'MID' | 'MIGRATED'>('ALL');
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [isSnipingKey, setIsSnipingKey] = useState<string | null>(null);

  const handleCopyText = (text: string, key: string) => {
    if (typeof navigator !== 'undefined' && navigator.clipboard) {
      navigator.clipboard.writeText(text);
      setCopiedKey(key);
      setTimeout(() => setCopiedKey(null), 2500);
    }
  };

  useEffect(() => {
    if (typeof window !== 'undefined') {
      setMode(getTradingMode());
      const saved = localStorage.getItem('sofia_quickbuy_idr');
      if (saved) setPresetIdr(Number(saved));
      const handler = (e: any) => setPresetIdr(Number(e.detail));
      const modeHandler = (e: any) => setMode(e.detail);
      window.addEventListener('sofia-preset-idr-change', handler);
      window.addEventListener('sofia-mode-change', modeHandler);
      return () => {
        window.removeEventListener('sofia-preset-idr-change', handler);
        window.removeEventListener('sofia-mode-change', modeHandler);
      };
    }
  }, []);

  const handleSelectPreset = (val: number) => {
    setPresetIdr(val);
    if (typeof window !== 'undefined') {
      localStorage.setItem('sofia_quickbuy_idr', String(val));
    }
  };

  const usdIdr = pulseQuery.data?.fx?.usd_idr || 16500;

  const handleQuickSnipe = async (token: any) => {
    const tokenKey = token.contract || token.symbol;
    setIsSnipingKey(tokenKey);
    setSnipeFeedback('');
    setSnipeError('');
    try {
      const res = await api.snipeToken({
        symbol: token.base_symbol || token.symbol,
        contract: token.contract || undefined,
        amount_idr: presetIdr,
        price: token.price,
        slippage_pct: 15,
        priority_fee_sol: 0.005,
        anti_mev: true,
        mode: mode,
      });
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('sofia-bot-trade-executed', { detail: res }));
      }
      setSnipeFeedback(
        res.mode === 'LIVE'
          ? `⚡ [LIVE ON-CHAIN] Berhasil beli ${Number(res.quantity).toLocaleString()} ${res.symbol} @ ${formatUsd(
              res.entry_price
            )} (${formatIdr(res.entry_price_idr)}) senilai ${formatIdr(res.amount_idr)} (${formatUsd(
              res.amount_usd
            )}) • Tx: ${String(res.tx_hash || '').slice(0, 16)}... • Sisa Kas Live: ${formatIdr(
              res.live_cash_remaining_idr
            )}`
          : `⚡ [PAPER SIMULASI] Berhasil beli ${Number(res.quantity).toLocaleString()} ${res.symbol} pada harga market asli ${formatUsd(
              res.entry_price
            )} (${formatIdr(res.entry_price_idr)}) senilai ${formatIdr(res.amount_idr)} (${formatUsd(
              res.amount_usd
            )}). Sisa Kas Paper: ${formatIdr(res.paper_cash_remaining_idr)}.`
      );
      setTimeout(() => setSnipeFeedback(''), 8000);
    } catch (err: any) {
      setSnipeError(err?.message || 'Gagal melakukan snipe');
      setTimeout(() => setSnipeError(''), 6000);
    } finally {
      setIsSnipingKey(null);
    }
  };

  // Filter helper for search query & min safety
  const filterTokens = (list: any[]) => {
    if (!list) return [];
    return list.filter((t) => {
      if (t.safety_score < minSafety) return false;
      if (!searchQuery.trim()) return true;
      const q = searchQuery.toLowerCase();
      const sym = (t.symbol || '').toLowerCase();
      const name = (t.name || '').toLowerCase();
      const ca = (t.contract || '').toLowerCase();
      return sym.includes(q) || name.includes(q) || ca.includes(q);
    });
  };

  const newTokens = useMemo(() => filterTokens(pulseQuery.data?.new_creations || []), [pulseQuery.data?.new_creations, minSafety, searchQuery]);
  const midTokens = useMemo(() => filterTokens(pulseQuery.data?.final_stretch || []), [pulseQuery.data?.final_stretch, minSafety, searchQuery]);
  const migratedTokens = useMemo(() => filterTokens(pulseQuery.data?.migrated || []), [pulseQuery.data?.migrated, minSafety, searchQuery]);

  const totalRawCount =
    (pulseQuery.data?.new_creations?.length || 0) +
    (pulseQuery.data?.final_stretch?.length || 0) +
    (pulseQuery.data?.migrated?.length || 0);

  const totalSafeCount = [
    ...(pulseQuery.data?.new_creations || []),
    ...(pulseQuery.data?.final_stretch || []),
    ...(pulseQuery.data?.migrated || []),
  ].filter((t) => (t.safety_score || 0) >= 75).length;

  const renderTokenCard = (t: any) => {
    const isSafe = (t.safety_score || 0) >= 75;
    const isWarning = (t.safety_score || 0) >= 55 && (t.safety_score || 0) < 75;
    const cardKey = t.contract || t.symbol;
    const isCaCopied = copiedKey === `ca-${cardKey}`;
    const isCreatorCopied = copiedKey === `creator-${cardKey}`;
    const isSnipingThis = isSnipingKey === cardKey;

    const safetyBadgeStyle = isSafe
      ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
      : isWarning
      ? 'bg-amber-500/15 text-amber-300 border-amber-500/30'
      : 'bg-rose-500/15 text-rose-300 border-rose-500/30';

    return (
      <div
        key={cardKey}
        className="rounded-2xl p-4 bg-obsidian-900 border border-obsidian-750 hover:border-obsidian-650 transition-all duration-200 shadow-md space-y-3.5 flex flex-col justify-between"
      >
        {/* TOP ROW: SYMBOL, LAUNCHPAD, AGE & SAFETY BADGE */}
        <div className="space-y-2.5">
          <div className="flex items-start justify-between gap-2">
            <div className="space-y-0.5">
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="font-black text-base text-white tracking-tight">{t.symbol}</span>
                {t.launchpad && (
                  <span className="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded bg-obsidian-950 text-cyan-300 border border-obsidian-800">
                    {t.launchpad}
                  </span>
                )}
                {t.age && (
                  <span className="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded border border-emerald-500/20">
                    {t.age}
                  </span>
                )}
              </div>
              <div className="text-xs text-slate-400 line-clamp-1">{t.name}</div>
            </div>

            {/* SAFETY SHIELD BADGE */}
            <span
              className={`text-[10px] px-2 py-0.5 rounded-lg border font-mono font-bold flex items-center gap-1 shrink-0 ${safetyBadgeStyle}`}
              title={`Skor Keselamatan Kontrak: ${t.safety_score}/100`}
            >
              <LucideIcon name="shield-check" className="w-3 h-3" />
              <span>Shield {t.safety_score}/100</span>
            </span>
          </div>

          {/* CONTRACT ADDRESS BAR WITH 1-CLICK COPY */}
          {t.contract && (
            <div className="flex items-center justify-between gap-1.5 p-1.5 px-2 rounded-xl bg-obsidian-950 border border-obsidian-800 text-[11px] font-mono">
              <span className="text-slate-400 truncate max-w-[160px] sm:max-w-[200px]" title={t.contract}>
                CA: <strong className="text-slate-200">{t.contract.slice(0, 6)}...{t.contract.slice(-4)}</strong>
              </span>
              <button
                type="button"
                onClick={() => handleCopyText(t.contract, `ca-${cardKey}`)}
                className={`px-2 py-0.5 rounded text-[10px] font-bold font-mono transition flex items-center gap-1 ${
                  isCaCopied
                    ? 'bg-emerald-500 text-obsidian-950'
                    : 'bg-obsidian-900 hover:bg-obsidian-850 text-amber-300 border border-obsidian-750'
                }`}
                title="Salin Mint Contract (CA)"
              >
                <LucideIcon name={isCaCopied ? 'check' : 'copy'} className="w-2.5 h-2.5" />
                <span>{isCaCopied ? '✓ Tersalin' : 'Salin CA'}</span>
              </button>
            </div>
          )}

          {/* CREATOR / DEV WALLET (IF DETECTED) */}
          {t.creator_address && (
            <div className="flex items-center justify-between gap-1.5 px-2 py-1 rounded-lg bg-obsidian-950/60 border border-obsidian-850 text-[10px] font-mono text-slate-500">
              <span className="truncate max-w-[160px]" title={t.creator_address}>
                Dev: {t.creator_address.slice(0, 4)}...{t.creator_address.slice(-4)}
              </span>
              <button
                type="button"
                onClick={() => handleCopyText(t.creator_address, `creator-${cardKey}`)}
                className={`px-1.5 py-0.2 rounded text-[9px] font-bold transition flex items-center gap-0.5 ${
                  isCreatorCopied
                    ? 'bg-cyan-400 text-obsidian-950'
                    : 'bg-obsidian-900 hover:bg-obsidian-800 text-cyan-300 border border-obsidian-750'
                }`}
                title="Salin Alamat Wallet Dev/Creator"
              >
                <LucideIcon name={isCreatorCopied ? 'check' : 'copy'} className="w-2 h-2" />
                <span>{isCreatorCopied ? '✓' : 'Dev Wallet'}</span>
              </button>
            </div>
          )}

          {/* PRICE BAR */}
          <div className="flex items-baseline justify-between pt-0.5 border-t border-obsidian-800/80">
            <div>
              <span className="text-[10px] text-slate-500 block font-mono">HARGA MARKET</span>
              <div className="text-sm font-black font-mono text-white">
                {formatUsd(t.price)}
              </div>
            </div>
            <div className="text-right">
              <span className="text-[10px] text-slate-500 block font-mono">KURS RUPIAH</span>
              <div className="text-xs font-mono font-bold text-emerald-400">
                ≈ {formatIdr(t.price * usdIdr)}
              </div>
            </div>
          </div>

          {/* BONDING / LIQUIDITY CURVE PROGRESS BAR */}
          <div className="space-y-1">
            <div className="flex justify-between text-[10px] font-mono text-slate-400">
              <span>Bonding / Liquidity Curve</span>
              <span className="text-cyan-300 font-bold">{t.bonding_curve_pct || 0}%</span>
            </div>
            <div className="w-full h-1.5 rounded-full bg-obsidian-950 border border-obsidian-800 overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-cyan-500 to-emerald-400 transition-all duration-300"
                style={{ width: `${Math.min(100, Math.max(0, t.bonding_curve_pct || 0))}%` }}
              />
            </div>
          </div>

          {/* KEY FINANCIAL METRICS GRID */}
          <div className="grid grid-cols-3 gap-1.5 p-2 rounded-xl bg-obsidian-950/80 border border-obsidian-800 text-[10px] font-mono">
            <div>
              <span className="text-slate-500 block">MCAP</span>
              <span className="text-white font-bold">${((t.market_cap || 0) / 1000).toFixed(1)}K</span>
              <span className="text-[9px] text-slate-400 block truncate">
                ≈ {formatIdr((t.market_cap || 0) * usdIdr)}
              </span>
            </div>
            <div>
              <span className="text-slate-500 block">LIKUIDITAS</span>
              <span className="text-white font-bold">${((t.liquidity || 0) / 1000).toFixed(1)}K</span>
              <span className="text-[9px] text-slate-400 block truncate">
                ≈ {formatIdr((t.liquidity || 0) * usdIdr)}
              </span>
            </div>
            <div>
              <span className="text-slate-500 block">5M VOL</span>
              <span className="text-cyan-300 font-bold">${((t.volume_5m || 0) / 1000).toFixed(1)}K</span>
              <span
                className={`text-[9px] block font-bold ${
                  (t.price_change_5m || 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'
                }`}
              >
                5m: {(t.price_change_5m || 0) >= 0 ? '+' : ''}
                {t.price_change_5m ?? 0}%
              </span>
            </div>
          </div>

          {/* ON-CHAIN SIGNALS & SMART MONEY TAGS */}
          <div className="flex flex-wrap items-center gap-1.5 text-[9px] font-mono">
            <span className="px-1.5 py-0.5 rounded bg-obsidian-950 text-slate-300 border border-obsidian-800">
              B/S 5m: <strong className="text-white">{t.buys_5m ?? 0}/{t.sells_5m ?? 0}</strong>
            </span>
            {t.gmgn_smart_degens !== undefined && t.gmgn_smart_degens > 0 && (
              <span className="px-1.5 py-0.5 rounded bg-purple-500/15 text-purple-300 border border-purple-500/30 font-bold">
                🧠 GMGN: {t.gmgn_smart_degens}W
              </span>
            )}
            {t.mint_revoked && (
              <span className="px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">
                ✓ Mint Revoked
              </span>
            )}
            {t.lp_burned && (
              <span className="px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">
                ✓ LP Burned
              </span>
            )}
          </div>
        </div>

        {/* BOTTOM ACTION SECTION: 1-CLICK SNIPE & DEX LINKS */}
        <div className="pt-2 border-t border-obsidian-800 space-y-2">
          <button
            type="button"
            disabled={isSnipingThis}
            onClick={() => handleQuickSnipe(t)}
            className="w-full py-2.5 px-3 rounded-xl bg-emerald-500 hover:bg-emerald-400 disabled:bg-obsidian-800 text-obsidian-950 font-mono font-black text-xs transition shadow-md shadow-emerald-500/20 flex items-center justify-center gap-2"
          >
            <LucideIcon name="zap" className="w-3.5 h-3.5 text-obsidian-950" />
            <span>
              {isSnipingThis
                ? 'Mengeksekusi Snipe...'
                : `⚡ 1-Klik Snipe ${formatIdr(presetIdr)} (${formatUsd(presetIdr / usdIdr)})`}
            </span>
          </button>

          <div className="flex items-center justify-between text-[11px] font-mono pt-0.5">
            <div className="flex items-center gap-2">
              {t.dex_url && (
                <a
                  href={t.dex_url}
                  target="_blank"
                  rel="noreferrer"
                  className="px-2 py-0.5 rounded-lg bg-obsidian-950 hover:bg-obsidian-800 text-cyan-300 border border-obsidian-800 inline-flex items-center gap-1 transition"
                >
                  <span>DexScreener</span>
                  <LucideIcon name="external-link" className="w-2.5 h-2.5" />
                </a>
              )}
              {t.gmgn_url && (
                <a
                  href={t.gmgn_url}
                  target="_blank"
                  rel="noreferrer"
                  className="px-2 py-0.5 rounded-lg bg-obsidian-950 hover:bg-obsidian-800 text-emerald-400 border border-obsidian-800 inline-flex items-center gap-1 transition"
                >
                  <span>GMGN.ai</span>
                  <LucideIcon name="external-link" className="w-2.5 h-2.5" />
                </a>
              )}
            </div>

            {t.pumpfun_url && (
              <a
                href={t.pumpfun_url}
                target="_blank"
                rel="noreferrer"
                className="text-purple-400 hover:text-purple-300 transition inline-flex items-center gap-0.5 text-[10px]"
              >
                <span>Pump.fun</span>
                <LucideIcon name="external-link" className="w-2.5 h-2.5" />
              </a>
            )}
          </div>
        </div>
      </div>
    );
  };

  const renderColumn = (title: string, subtitle: string, badgeDot: string, tokens: any[]) => {
    return (
      <div className="bg-obsidian-950 border border-obsidian-800 rounded-2xl flex flex-col overflow-hidden shadow-lg">
        {/* COLUMN HEADER */}
        <div className="p-3.5 sm:p-4 border-b border-obsidian-800 flex items-center justify-between bg-obsidian-900/70">
          <div className="space-y-0.5">
            <div className="font-bold text-sm text-white flex items-center gap-2">
              <span className={`w-2.5 h-2.5 rounded-full ${badgeDot}`} />
              <span>{title}</span>
            </div>
            <div className="text-[11px] text-slate-400">{subtitle}</div>
          </div>
          <span className="px-2.5 py-0.5 rounded-lg bg-obsidian-950 border border-obsidian-750 text-xs font-mono font-bold text-cyan-300">
            {tokens.length} Koin
          </span>
        </div>

        {/* COLUMN CONTENT */}
        <div
          className={
            isUltrawide
              ? 'p-3.5 grid grid-cols-1 xl:grid-cols-2 gap-3.5 overflow-y-auto max-h-[78vh]'
              : 'p-3.5 space-y-3.5 overflow-y-auto max-h-[78vh]'
          }
        >
          {tokens.length === 0 ? (
            <div className="p-8 text-center text-xs text-slate-500 font-mono bg-obsidian-900/30 rounded-xl border border-obsidian-850">
              Tidak ada koin yang sesuai dengan filter di kategori ini.
            </div>
          ) : (
            tokens.map((t) => renderTokenCard(t))
          )}
        </div>
      </div>
    );
  };

  return (
    <>
      <Head>
        <title>Trenches &amp; Pulse Radar | Sofia Market 3.9</title>
      </Head>

      <div className="space-y-5 pb-12">
        {/* HERO HEADER */}
        <div className="bg-gradient-to-r from-obsidian-900 via-obsidian-900 to-obsidian-850 border border-obsidian-750 rounded-2xl p-5 sm:p-6 shadow-xl flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1.5">
            <div className="flex flex-wrap items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
              <h1 className="text-xl sm:text-2xl font-black text-slate-100 tracking-tight flex items-center gap-2">
                <LucideIcon name="zap" className="w-6 h-6 text-amber-400" />
                <span>Trenches &amp; Pulse Radar</span>
              </h1>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-cyan-500/15 text-cyan-300 border border-cyan-500/30">
                DEXSCREENER V1
              </span>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-purple-500/15 text-purple-300 border border-purple-500/30">
                GMGN.AI TRENCH
              </span>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
                100% REAL MARKET
              </span>
            </div>
            <p className="text-xs sm:text-sm text-slate-400 max-w-3xl leading-relaxed">
              Pemantauan harga on-chain, umur token baru rilis di DEX, likuiditas Raydium/PumpSwap, dan audit keselamatan RugShield secara live. Eksekusi 1-klik snipe langsung menggunakan modal Paper atau Live wallet.
            </p>
          </div>

          {/* TELEMETRY MINI STATUS */}
          <div className="flex flex-wrap items-center gap-2 text-xs font-mono shrink-0">
            <div className="bg-obsidian-950 px-3 py-2 rounded-xl border border-obsidian-800">
              <span className="text-[10px] text-slate-500 block">KURS USD/IDR</span>
              <span className="font-bold text-white font-mono">{formatIdr(usdIdr)}</span>
            </div>
            <div className="bg-obsidian-950 px-3 py-2 rounded-xl border border-obsidian-800">
              <span className="text-[10px] text-slate-500 block">MODE TRADING</span>
              <span
                className={`font-bold font-mono ${
                  mode === 'LIVE' ? 'text-rose-400' : 'text-cyan-300'
                }`}
              >
                {mode === 'LIVE' ? '⚡ LIVE SOLANA' : '📄 PAPER SIMULASI'}
              </span>
            </div>
          </div>
        </div>

        {/* FEEDBACK TOASTS */}
        {snipeFeedback && (
          <div className="p-4 rounded-xl bg-emerald-500/15 border border-emerald-500/30 text-emerald-200 text-xs sm:text-sm font-mono flex items-center gap-2 shadow-lg">
            <LucideIcon name="check" className="w-4 h-4 shrink-0 text-emerald-400" />
            <span>{snipeFeedback}</span>
          </div>
        )}
        {snipeError && (
          <div className="p-4 rounded-xl bg-rose-500/15 border border-rose-500/30 text-rose-200 text-xs sm:text-sm font-mono flex items-center gap-2 shadow-lg">
            <LucideIcon name="alert-circle" className="w-4 h-4 shrink-0 text-rose-400" />
            <span>🛡️ {snipeError}</span>
          </div>
        )}

        {/* 4 SUMMARY STAT CARDS */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3.5">
          <div className="p-3.5 sm:p-4 rounded-xl bg-obsidian-900 border border-obsidian-750 shadow-md space-y-1">
            <div className="text-[10px] sm:text-[11px] font-mono text-slate-400 flex items-center justify-between">
              <span>TOTAL TOKEN RADAR</span>
              <span className="w-2 h-2 rounded-full bg-cyan-400" />
            </div>
            <div className="text-xl sm:text-2xl font-black text-white font-mono">
              {totalRawCount} Koin
            </div>
            <div className="text-[10px] text-slate-500">Live feed dari Solana DEX</div>
          </div>

          <div className="p-3.5 sm:p-4 rounded-xl bg-obsidian-900 border border-obsidian-750 shadow-md space-y-1">
            <div className="text-[10px] sm:text-[11px] font-mono text-slate-400 flex items-center justify-between">
              <span>PASANGAN BARU RILIS</span>
              <span className="w-2 h-2 rounded-full bg-sky-400" />
            </div>
            <div className="text-xl sm:text-2xl font-black text-sky-400 font-mono">
              {pulseQuery.data?.new_creations?.length || 0} Pool
            </div>
            <div className="text-[10px] text-slate-500">Koin menit &amp; jam pertama</div>
          </div>

          <div className="p-3.5 sm:p-4 rounded-xl bg-obsidian-900 border border-obsidian-750 shadow-md space-y-1">
            <div className="text-[10px] sm:text-[11px] font-mono text-slate-400 flex items-center justify-between">
              <span>MID-CAP &amp; BONDING</span>
              <span className="w-2 h-2 rounded-full bg-amber-400" />
            </div>
            <div className="text-xl sm:text-2xl font-black text-amber-400 font-mono">
              {pulseQuery.data?.final_stretch?.length || 0} Pool
            </div>
            <div className="text-[10px] text-slate-500">Akselerasi volume aktif</div>
          </div>

          <div className="p-3.5 sm:p-4 rounded-xl bg-obsidian-900 border border-obsidian-750 shadow-md space-y-1">
            <div className="text-[10px] sm:text-[11px] font-mono text-slate-400 flex items-center justify-between">
              <span>LOLOS SHIELD (≥ 75)</span>
              <span className="w-2 h-2 rounded-full bg-emerald-400" />
            </div>
            <div className="text-xl sm:text-2xl font-black text-emerald-400 font-mono">
              {totalSafeCount} Koin
            </div>
            <div className="text-[10px] text-slate-500">
              {totalRawCount > 0 ? `${Math.round((totalSafeCount / totalRawCount) * 100)}% aman di-snipe` : 'Audit otomatis'}
            </div>
          </div>
        </div>

        {/* INTERACTIVE CONTROLS TOOLBAR */}
        <div className="rounded-2xl bg-obsidian-900 border border-obsidian-750 p-4 shadow-lg space-y-3.5">
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
            {/* SEARCH INPUT */}
            <div className="relative flex-1 max-w-md">
              <LucideIcon
                name="search"
                className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2"
              />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Cari simbol, nama koin, atau paste CA..."
                className="w-full pl-9 pr-8 py-2 rounded-xl bg-obsidian-950 border border-obsidian-750 text-white placeholder-slate-500 font-mono text-xs focus:outline-none focus:border-cyan-400"
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => setSearchQuery('')}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white text-xs"
                >
                  ✕
                </button>
              )}
            </div>

            {/* CONTROLS: SHIELD FILTER + REFRESH */}
            <div className="flex flex-wrap items-center gap-2 text-xs font-mono">
              <span className="text-slate-400 flex items-center gap-1 font-bold">
                <LucideIcon name="shield-check" className="w-3.5 h-3.5 text-emerald-400" />
                <span>Filter Shield:</span>
              </span>
              {[0, 60, 75, 85].map((score) => (
                <button
                  key={score}
                  type="button"
                  onClick={() => setMinSafety(score)}
                  className={`px-2.5 py-1.5 rounded-lg transition font-bold ${
                    minSafety === score
                      ? 'bg-emerald-500 text-obsidian-950 shadow-sm'
                      : 'bg-obsidian-950 text-slate-400 hover:text-white border border-obsidian-800'
                  }`}
                >
                  {score === 0 ? 'Semua' : `≥ ${score}`}
                </button>
              ))}

              <button
                type="button"
                onClick={() => pulseQuery.refetch()}
                className="ml-auto lg:ml-2 px-3 py-1.5 rounded-lg bg-cyan-500/15 hover:bg-cyan-500/25 text-cyan-300 border border-cyan-500/30 flex items-center gap-1.5 transition font-bold"
                title="Pembaruan manual data pool DEX"
              >
                <LucideIcon name="refresh-cw" className="w-3.5 h-3.5" />
                <span>Refresh Live</span>
              </button>
            </div>
          </div>

          {/* NOMINAL SNIPE CHIPS ROW */}
          <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-obsidian-800 text-xs font-mono">
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-slate-400 flex items-center gap-1 font-bold">
                <LucideIcon name="banknote" className="w-3.5 h-3.5 text-amber-400" />
                <span>Nominal 1-Klik Snipe:</span>
              </span>
              {[15000, 25000, 30000, 50000, 100000].map((nominal) => (
                <button
                  key={nominal}
                  type="button"
                  onClick={() => handleSelectPreset(nominal)}
                  className={`px-2.5 py-1 rounded-lg transition font-bold ${
                    presetIdr === nominal
                      ? 'bg-amber-400 text-obsidian-950 shadow-sm'
                      : 'bg-obsidian-950 hover:bg-obsidian-850 text-slate-300 border border-obsidian-800'
                  }`}
                >
                  {formatIdr(nominal)}
                </button>
              ))}
              <span className="text-[11px] text-slate-500 ml-1">
                (≈ {formatUsd(presetIdr / usdIdr)})
              </span>
            </div>

            {/* MOBILE COLUMN TAB SWITCHER */}
            <div className="lg:hidden flex items-center gap-1 bg-obsidian-950 p-1 rounded-xl border border-obsidian-800 w-full sm:w-auto">
              <button
                type="button"
                onClick={() => setActiveColumnTab('ALL')}
                className={`flex-1 sm:flex-initial px-2.5 py-1 rounded-lg text-[11px] font-bold ${
                  activeColumnTab === 'ALL' ? 'bg-obsidian-800 text-white' : 'text-slate-400'
                }`}
              >
                Semua
              </button>
              <button
                type="button"
                onClick={() => setActiveColumnTab('NEW')}
                className={`flex-1 sm:flex-initial px-2.5 py-1 rounded-lg text-[11px] font-bold ${
                  activeColumnTab === 'NEW' ? 'bg-sky-500/20 text-sky-300' : 'text-slate-400'
                }`}
              >
                🌱 Baru ({newTokens.length})
              </button>
              <button
                type="button"
                onClick={() => setActiveColumnTab('MID')}
                className={`flex-1 sm:flex-initial px-2.5 py-1 rounded-lg text-[11px] font-bold ${
                  activeColumnTab === 'MID' ? 'bg-amber-500/20 text-amber-300' : 'text-slate-400'
                }`}
              >
                ⚡ Mid-Cap ({midTokens.length})
              </button>
              <button
                type="button"
                onClick={() => setActiveColumnTab('MIGRATED')}
                className={`flex-1 sm:flex-initial px-2.5 py-1 rounded-lg text-[11px] font-bold ${
                  activeColumnTab === 'MIGRATED' ? 'bg-emerald-500/20 text-emerald-300' : 'text-slate-400'
                }`}
              >
                🚀 Graduated ({migratedTokens.length})
              </button>
            </div>
          </div>
        </div>

        {/* 3-COLUMN RADAR GRIDS */}
        <QueryState
          isLoading={pulseQuery.isLoading}
          isError={pulseQuery.isError}
          error={pulseQuery.error}
          hasData={Boolean(pulseQuery.data)}
        >
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
            {/* COLUMN 1: MICRO-CAP & NEW CREATIONS */}
            {(activeColumnTab === 'ALL' || activeColumnTab === 'NEW') &&
              renderColumn(
                '🌱 Micro-Cap & New Pairs',
                'Pasangan meme coin baru rilis & kapitalisasi mikro',
                'bg-sky-400',
                newTokens
              )}

            {/* COLUMN 2: MID-CAP MOMENTUM & BONDING CURVE */}
            {(activeColumnTab === 'ALL' || activeColumnTab === 'MID') &&
              renderColumn(
                '⚡ Mid-Cap Momentum (PumpSwap / DEX)',
                'Token dengan akselerasi volume & likuiditas aktif',
                'bg-amber-400',
                midTokens
              )}

            {/* COLUMN 3: GRADUATED & MAJOR RAYDIUM LIQUIDITY */}
            {(activeColumnTab === 'ALL' || activeColumnTab === 'MIGRATED') &&
              renderColumn(
                '🚀 Graduated & Major Liquidity',
                'Pool DEX likuiditas besar & lulus bonding curve',
                'bg-emerald-400',
                migratedTokens
              )}
          </div>
        </QueryState>
      </div>
    </>
  );
}
