import React, { useState, useEffect } from 'react';
import {
  api,
  useApiQuery,
  formatIdr,
  formatUsd,
  getTradingMode,
  setTradingMode,
} from '@/lib/api';
import { QueryState } from '@/components/QueryState';
import { PnLChart } from '@/components/PnLChart';
import { BotActivityCard } from '@/components/BotActivityCard';
import { LucideIcon } from '@/components/LucideIcon';

const AVATAR_THEMES = [
  {
    circle: 'bg-emerald-500/20 border-emerald-500/40 text-emerald-300',
    hoverText: 'group-hover:text-emerald-400',
  },
  {
    circle: 'bg-cyan-500/20 border-cyan-500/40 text-cyan-300',
    hoverText: 'group-hover:text-cyan-400',
  },
  {
    circle: 'bg-pink-500/20 border-pink-500/40 text-pink-300',
    hoverText: 'group-hover:text-pink-400',
  },
  {
    circle: 'bg-purple-500/20 border-purple-500/40 text-purple-300',
    hoverText: 'group-hover:text-purple-400',
  },
];

const SNIPE_PCT_PRESETS = [
  { label: '10% (Rp 15k)', value: 15000 },
  { label: '25% (Rp 37.5k)', value: 37500 },
  { label: '50% (Rp 75k)', value: 75000 },
  { label: '100% (Rp 150k)', value: 150000 },
];

export default function DashboardPage() {
  const botQuery = useApiQuery(() => api.getBotStatus(), []);
  const portfolioQuery = useApiQuery(() => api.getPortfolio(), []);
  const perfQuery = useApiQuery(() => api.getPerformance(), []);
  const pulseQuery = useApiQuery(() => api.getPulse(), []);
  const walletsQuery = useApiQuery(() => api.getWallets(), []);

  const [quickTicker, setQuickTicker] = useState<string>('PEPE');
  const [quickAmountIdr, setQuickAmountIdr] = useState<number>(15000);
  const [snipeMode, setSnipeMode] = useState<'PAPER' | 'LIVE'>('PAPER');
  const [snipeMsg, setSnipeMsg] = useState<string>('');
  const [snipeErr, setSnipeErr] = useState<string>('');
  const [activeTarget, setActiveTarget] = useState<string>('WIF/METH');

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('sofia_quickbuy_idr');
      if (saved) setQuickAmountIdr(Number(saved));
      setSnipeMode(getTradingMode());

      const presetHandler = (e: any) => setQuickAmountIdr(Number(e.detail));
      const modeHandler = (e: any) => {
        setSnipeMode(e.detail);
        walletsQuery.refetch();
        portfolioQuery.refetch();
        perfQuery.refetch();
      };
      const resetHandler = (e: any) => {
        if (e?.detail) {
          portfolioQuery.setData(e.detail);
        } else {
          portfolioQuery.refetch();
        }
        perfQuery.refetch();
        walletsQuery.refetch();
        setSnipeMsg(
          '🔄 Semua portofolio & posisi meme coin pada mode Paper telah dihapus! Saldo kembali utuh ke Rp 150.000.'
        );
      };
      const botHandler = () => {
        botQuery.refetch();
      };
      const tradeExecHandler = (e: any) => {
        portfolioQuery.refetch();
        perfQuery.refetch();
        botQuery.refetch();
        walletsQuery.refetch();
        const act = e?.detail;
        if (act && act.symbol) {
          if (act.status === 'sold') {
            setSnipeMsg(
              `🤖 [AUTO-BOT SELL] Menjual ${act.symbol} @ ${formatUsd(act.sell_price_usd)} • Realized PnL: ${formatIdr(act.realized_pnl_idr)}`
            );
          } else {
            setSnipeMsg(
              `🤖 [AUTO-BOT SNIPE] Membeli ${Number(act.quantity || 0).toLocaleString()} ${act.symbol} senilai ${formatIdr(act.amount_idr)} @ harga live ${formatUsd(act.entry_price)}!`
            );
          }
        }
      };

      window.addEventListener('sofia-preset-idr-change', presetHandler);
      window.addEventListener('sofia-mode-change', modeHandler);
      window.addEventListener('sofia-paper-reset', resetHandler);
      window.addEventListener('sofia-bot-status-change', botHandler);
      window.addEventListener('sofia-bot-trade-executed', tradeExecHandler);
      return () => {
        window.removeEventListener('sofia-preset-idr-change', presetHandler);
        window.removeEventListener('sofia-mode-change', modeHandler);
        window.removeEventListener('sofia-paper-reset', resetHandler);
        window.removeEventListener('sofia-bot-status-change', botHandler);
        window.removeEventListener('sofia-bot-trade-executed', tradeExecHandler);
      };
    }
  }, []);

  const usdIdr =
    portfolioQuery.data?.usd_idr ||
    perfQuery.data?.usd_idr ||
    pulseQuery.data?.fx?.usd_idr ||
    17960;

  const handleToggleModeSwitch = () => {
    const next = snipeMode === 'PAPER' ? 'LIVE' : 'PAPER';
    setSnipeMode(next);
    setTradingMode(next);
  };

  const handleBotPower = async () => {
    setSnipeMsg('');
    setSnipeErr('');
    try {
      if (botQuery.data?.status === 'running') {
        await api.stopBot();
        setSnipeMsg('⏹ Mesin Sniper Bot dihentikan.');
        if (typeof window !== 'undefined') {
          window.dispatchEvent(new CustomEvent('sofia-bot-status-change', { detail: { running: false } }));
        }
      } else {
        await api.startBot(snipeMode);
        setSnipeMsg(`🟢 Mesin Sniper Bot diaktifkan dalam mode ${snipeMode}!`);
        if (typeof window !== 'undefined') {
          window.dispatchEvent(new CustomEvent('sofia-bot-status-change', { detail: { running: true } }));
        }
      }
      botQuery.refetch();
    } catch (err: any) {
      setSnipeErr(`${err?.code || 'ERROR'}: ${err?.message || 'Gagal mengubah status bot'}`);
    }
  };

  const handleInstantSnipe = async (e: React.FormEvent) => {
    e.preventDefault();
    setSnipeMsg('');
    setSnipeErr('');
    try {
      const res = await api.snipeToken({
        symbol: quickTicker,
        amount_idr: quickAmountIdr,
        slippage_pct: 1.0,
        priority_fee_sol: 0.005,
        anti_mev: true,
        mode: snipeMode,
      });
      setSnipeMsg(
        `⚡ [${res.mode}] Berhasil snipe ${res.quantity.toLocaleString()} ${res.symbol} pada harga market asli ${formatUsd(
          res.entry_price
        )} (${formatIdr(res.entry_price_idr)}) senilai ${formatIdr(res.amount_idr)} (${formatUsd(res.amount_usd)}).`
      );
      portfolioQuery.refetch();
      perfQuery.refetch();
    } catch (err: any) {
      setSnipeErr(err?.message || 'Eksekusi snipe gagal');
    }
  };

  const handlePasteClipboard = async () => {
    try {
      if (typeof navigator !== 'undefined' && navigator.clipboard?.readText) {
        const text = await navigator.clipboard.readText();
        if (text && text.trim()) {
          setQuickTicker(text.trim());
        }
      }
    } catch {
      // ignore clipboard permission denied
    }
  };

  const paperCashUsd = portfolioQuery.data?.paper_cash_usd ?? 150000 / usdIdr;
  const paperCashIdr = portfolioQuery.data?.paper_cash_idr ?? 150000;
  const totalEquityUsd = portfolioQuery.data?.total_equity_usd ?? paperCashUsd;
  const totalEquityIdr = portfolioQuery.data?.total_equity_idr ?? paperCashIdr;
  const holdingsValUsd = portfolioQuery.data?.total_value ?? 0;
  const holdingsValIdr = portfolioQuery.data?.total_value_idr ?? 0;
  const holdingsCount = (portfolioQuery.data?.holdings || []).length;
  const realizedPnlUsd = perfQuery.data?.total_pnl ?? 0;
  const realizedPnlIdr = perfQuery.data?.total_pnl_idr ?? 0;
  const unrealizedPnlUsd = portfolioQuery.data?.unrealized_pnl ?? 0;
  const unrealizedPnlIdr = portfolioQuery.data?.unrealized_pnl_idr ?? 0;
  const netPnlUsd = realizedPnlUsd + unrealizedPnlUsd;
  const netPnlIdr = realizedPnlIdr + unrealizedPnlIdr;
  const netPnlPct = ((totalEquityIdr - 150000) / 150000) * 100;
  const isBotRunning = botQuery.data?.status === 'running';

  const isLive = snipeMode === 'LIVE';

  // Live multi-gate on-chain wallets calculations
  const allWallets: any[] = walletsQuery.data?.wallets || [];
  const liveWallets = allWallets.filter((w) => !w.name?.includes('Modal Paper'));
  const liveTradingWallets = liveWallets.filter((w) => w.gate === 'trading');

  const liveTotalEquityUsd = liveWallets.reduce((acc, w) => acc + (Number(w.balance_usd) || 0), 0);
  const liveTotalEquityIdr = liveWallets.reduce((acc, w) => acc + (Number(w.balance_idr) || 0), 0);

  const liveCashUsd = liveTradingWallets.reduce((acc, w) => acc + (Number(w.balance_usd) || 0), 0);
  const liveCashIdr = liveTradingWallets.reduce((acc, w) => acc + (Number(w.balance_idr) || 0), 0);

  // Dynamic values based on selected mode (PAPER vs LIVE)
  const activeEquityUsd = isLive ? liveTotalEquityUsd : totalEquityUsd;
  const activeEquityIdr = isLive ? liveTotalEquityIdr : totalEquityIdr;
  const activeCashUsd = isLive ? liveCashUsd : paperCashUsd;
  const activeCashIdr = isLive ? liveCashIdr : paperCashIdr;
  const activePnlPct = isLive
    ? liveTotalEquityIdr > 0
      ? (netPnlIdr / liveTotalEquityIdr) * 100
      : 0
    : netPnlPct;

  const liveTokens: any[] = [
    ...(pulseQuery.data?.new_creations || []),
    ...(pulseQuery.data?.final_stretch || []),
    ...(pulseQuery.data?.migrated || []),
  ].slice(0, 6);

  return (
    <div className="space-y-3">
      {/* Sub-Header Alert Banner */}
      <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 rounded-lg bg-emerald-500/10 border border-emerald-500/25">
        <div className="flex items-center gap-2 text-xs text-slate-200">
          <span className="flex h-2 w-2 rounded-full bg-emerald-400 animate-pulse"></span>
          <span className="font-bold text-emerald-400 font-mono">⚡ Meme Sniper Command Center:</span>
          <span className="text-slate-300 text-[11px]">
            100% Real-Time Market Data (DexScreener Live) • {isLive ? (
              <>Saldo On-Chain Live: <strong className="text-cyan-300 font-mono">{formatUsd(liveTotalEquityUsd)} ({formatIdr(liveTotalEquityIdr)})</strong></>
            ) : (
              <>Modal Paper: <strong className="text-emerald-300 font-mono">Rp 150.000</strong></>
            )} • Kurs Hari Ini: <strong className="text-cyan-300 font-mono">$1 = {formatIdr(usdIdr)}</strong>
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] bg-emerald-950 text-emerald-300 border border-emerald-600/50 px-2 py-0.5 rounded font-mono">
            TARGET: {activeTarget}
          </span>
          <button
            type="button"
            onClick={handleBotPower}
            className="text-[10px] bg-cyan-500/20 text-cyan-300 hover:bg-cyan-500/30 border border-cyan-500/40 px-2 py-0.5 rounded font-mono flex items-center gap-1 transition"
          >
            <LucideIcon name="radio" className="w-3 h-3" />{' '}
            {isBotRunning ? 'Stop Scan' : 'Start Scan'}
          </button>
        </div>
      </div>

      {snipeMsg && (
        <div className="px-3 py-2 rounded-lg bg-emerald-950/70 border border-emerald-500/40 text-xs font-mono text-emerald-200">
          {snipeMsg}
        </div>
      )}
      {snipeErr && (
        <div className="px-3 py-2 rounded-lg bg-rose-950/70 border border-rose-500/40 text-xs font-mono text-rose-200">
          ⚠️ {snipeErr}
        </div>
      )}

      <QueryState isLoading={botQuery.isLoading} isError={botQuery.isError} error={botQuery.error}>
        {/* BEGIN: StatCardsSection */}
        <section
          className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5"
          data-purpose="stat-counter-grid"
        >
          {/* Card 1: Total Ekuitas */}
          <div className="bg-obsidian-900 border border-obsidian-700/80 rounded-xl p-3.5 relative overflow-hidden group hover:border-emerald-500/40 transition">
            <div className="flex items-center justify-between text-xs mb-1">
              <span className="text-slate-400 font-medium">
                {isLive ? 'TOTAL EKUITAS (LIVE)' : 'TOTAL EKUITAS (PAPER)'}
              </span>
              <span
                className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded border ${
                  isLive
                    ? 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30'
                    : 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
                }`}
              >
                {isLive ? 'LIVE ON-CHAIN' : 'MODAL AWAL'}
              </span>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold font-mono tracking-tight text-white">
                {formatUsd(activeEquityUsd)}
              </span>
              <span className="text-xs text-slate-400 font-mono">≈ {formatIdr(activeEquityIdr)}</span>
            </div>
            <div className="mt-2 text-[10px] text-slate-400 flex items-center justify-between border-t border-obsidian-800 pt-1.5 font-mono">
              <span>
                {isLive
                  ? `${liveWallets.length} Dompet Multi-Chain On-Chain`
                  : `${formatIdr(totalEquityIdr)} (kurs hari ini)`}
              </span>
              <span
                className={`flex items-center gap-0.5 ${
                  activePnlPct >= 0 ? 'text-emerald-400' : 'text-rose-400'
                }`}
              >
                <LucideIcon name={isLive ? 'shield-check' : 'trending-up'} className="w-3 h-3" />{' '}
                {isLive ? 'Verified On-Chain' : `${activePnlPct >= 0 ? '+' : ''}${activePnlPct.toFixed(2)}%`}
              </span>
            </div>
          </div>

          {/* Card 2: Sisa Saldo Kas */}
          <div className="bg-obsidian-900 border border-obsidian-700/80 rounded-xl p-3.5 relative overflow-hidden group hover:border-cyan-500/40 transition">
            <div className="flex items-center justify-between text-xs mb-1">
              <span className="text-slate-400 font-medium">
                {isLive ? 'SISA SALDO KAS LIVE' : 'SISA SALDO KAS PAPER'}
              </span>
              <LucideIcon name="banknote" className="w-3.5 h-3.5 text-cyan-400" />
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold font-mono tracking-tight text-white">
                {formatUsd(activeCashUsd)}
              </span>
              <span className="text-xs text-cyan-400 font-mono">
                {isLive ? 'Hot Wallets' : 'Siap Beli'}
              </span>
            </div>
            <div className="mt-2 text-[10px] text-slate-400 flex items-center justify-between border-t border-obsidian-800 pt-1.5 font-mono">
              <span>= {formatIdr(activeCashIdr)}</span>
              <span className="text-slate-300">
                {isLive ? 'Solana & Base DEX' : 'dari Rp 150.000'}
              </span>
            </div>
          </div>

          {/* Card 3: Nilai Posisi Meme Cuan */}
          <div className="bg-obsidian-900 border border-obsidian-700/80 rounded-xl p-3.5 relative overflow-hidden group hover:border-slate-500 transition">
            <div className="flex items-center justify-between text-xs mb-1">
              <span className="text-slate-400 font-medium">
                {isLive ? 'NILAI POSISI MEME (LIVE)' : 'NILAI POSISI MEME CUAN'}
              </span>
              <span
                className={`text-[9px] font-mono px-1.5 py-0.5 rounded border ${
                  isLive
                    ? 'bg-cyan-500/10 text-cyan-300 border-cyan-500/30'
                    : 'bg-obsidian-800 text-slate-400 border border-obsidian-700'
                }`}
              >
                {isLive ? 'LIVE DEX' : `${holdingsCount} POSISI`}
              </span>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold font-mono tracking-tight text-slate-300">
                {formatUsd(holdingsValUsd)}
              </span>
              <span className="text-xs text-slate-400 font-mono">{formatIdr(holdingsValIdr)}</span>
            </div>
            <div className="mt-2 text-[10px] text-slate-400 flex items-center justify-between border-t border-obsidian-800 pt-1.5 font-mono">
              <span>
                ≈ {formatIdr(holdingsValIdr)} ({holdingsCount} posisi)
              </span>
              <span className="text-slate-400">
                {holdingsCount > 0 ? (isLive ? 'Aktif di Raydium / Base' : 'Aktif di DEX') : (isLive ? 'Standby Sniper' : 'Menunggu Trigger')}
              </span>
            </div>
          </div>

          {/* Card 4: Total Profit / Loss */}
          <div className="bg-obsidian-900 border border-obsidian-700/80 rounded-xl p-3.5 relative overflow-hidden group hover:border-emerald-500/40 transition">
            <div className="flex items-center justify-between text-xs mb-1">
              <span className="text-slate-400 font-medium">
                {isLive ? 'TOTAL PROFIT / LOSS (LIVE)' : 'TOTAL PROFIT / LOSS (PnL)'}
              </span>
              <span
                className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded border ${
                  isLive
                    ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/30'
                    : 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                }`}
              >
                {isLive ? 'SETTLEMENT 05:00 WIB' : 'HARI INI'}
              </span>
            </div>
            <div className="flex items-baseline gap-2">
              <span
                className={`text-2xl font-bold font-mono tracking-tight ${
                  netPnlUsd >= 0 ? 'text-emerald-400' : 'text-rose-400'
                }`}
              >
                {netPnlUsd >= 0 ? '+' : ''}
                {formatUsd(netPnlUsd)}
              </span>
              <span
                className={`text-xs font-mono ${
                  activePnlPct >= 0 ? 'text-emerald-400/80' : 'text-rose-400/80'
                }`}
              >
                {activePnlPct >= 0 ? '+' : ''}
                {activePnlPct.toFixed(2)}%
              </span>
            </div>
            <div className="mt-2 text-[10px] text-slate-400 flex items-center justify-between border-t border-obsidian-800 pt-1.5 font-mono">
              <span
                className={`font-medium ${
                  netPnlIdr >= 0 ? 'text-emerald-400/90' : 'text-rose-400/90'
                }`}
              >
                {netPnlIdr >= 0 ? '+' : ''} {formatIdr(netPnlIdr)} ({isLive ? 'Net Settlement PnL' : 'Realized + Floating'})
              </span>
              <LucideIcon name="badge-percent" className="w-3.5 h-3.5 text-emerald-400" />
            </div>
          </div>
        </section>
        {/* END: StatCardsSection */}

        {/* BEGIN: LiveBotActivityAndTerminal */}
        <BotActivityCard
          botStatus={botQuery.data?.status}
          onTargetChange={(t) => setActiveTarget(t)}
        />
        {/* END: LiveBotActivityAndTerminal */}

        {/* BEGIN: EquityCurveSection */}
        <PnLChart
          points={perfQuery.data?.pnl_chart || []}
          usdIdr={usdIdr}
          totalTrades={perfQuery.data?.total_trades ?? 0}
          realizedIdr={realizedPnlIdr}
          floatingIdr={unrealizedPnlIdr}
          liveEquityUsd={activeEquityUsd}
          liveEquityIdr={activeEquityIdr}
        />
        {/* END: EquityCurveSection */}

        {/* BEGIN: BottomDualPanelsSection */}
        <section
          className="grid grid-cols-1 lg:grid-cols-12 gap-3"
          data-purpose="sniper-and-market-dual-panel"
        >
          {/* ================= LEFT PANEL: Instant Token Sniper ================= */}
          <form
            onSubmit={handleInstantSnipe}
            className="lg:col-span-5 bg-obsidian-900 border border-obsidian-700/80 rounded-xl p-3.5 flex flex-col justify-between space-y-3.5"
          >
            <div className="space-y-3">
              {/* Header with Title and Mode Indicator */}
              <div className="flex items-center justify-between pb-2 border-b border-obsidian-800">
                <div className="flex items-center gap-2">
                  <LucideIcon name="zap" className="w-4 h-4 text-emerald-400" />
                  <h3 className="text-xs font-bold text-slate-100 uppercase tracking-wide">
                    Instant Token Sniper
                  </h3>
                </div>
                <button
                  type="button"
                  onClick={handleToggleModeSwitch}
                  className={
                    snipeMode === 'PAPER'
                      ? 'text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-300 border border-emerald-500/30'
                      : 'text-[10px] font-mono px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/40'
                  }
                >
                  {snipeMode} ACTIVE
                </button>
              </div>

              {/* Description / Help */}
              <p className="text-[11px] text-slate-400 leading-snug">
                Salin &amp; Tempel Contract Address (CA) token dari DexScreener atau PumpFun untuk
                langsung mengeksekusi order {snipeMode === 'PAPER' ? 'simulasi paper' : 'live on-chain'}.
              </p>

              {/* Input: Contract Address / Ticker */}
              <div className="space-y-1">
                <label className="text-[10px] font-mono text-slate-400 uppercase font-semibold flex items-center justify-between">
                  <span>TOKEN TICKER / CONTRACT ADDRESS (DEXSCREENER LINK)</span>
                  <span className="text-cyan-400">Auto-Detect CA</span>
                </label>
                <div className="relative">
                  <input
                    className="w-full bg-obsidian-950 border border-obsidian-700 rounded-lg px-3 py-2 text-xs font-mono text-white placeholder-slate-600 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
                    placeholder="Paste Mint CA or DexScreener URL..."
                    type="text"
                    value={quickTicker}
                    onChange={(e) => setQuickTicker(e.target.value)}
                    required
                  />
                  <button
                    type="button"
                    onClick={handlePasteClipboard}
                    className="absolute right-2 top-1.5 px-1.5 py-0.5 rounded bg-obsidian-800 text-[10px] font-mono text-slate-400 hover:text-white transition"
                  >
                    PASTE
                  </button>
                </div>
              </div>

              {/* Input: Nominal Snipe (Rupiah) */}
              <div className="space-y-1">
                <div className="flex justify-between items-center text-[10px] font-mono">
                  <span className="text-slate-400 uppercase font-semibold">
                    NOMINAL SNIPE (RUPIAH)
                  </span>
                  <span className="text-emerald-400 font-medium">
                    Maks: {formatIdr(paperCashIdr)} ({formatUsd(paperCashUsd)})
                  </span>
                </div>
                <div className="relative">
                  <span className="absolute left-3 top-2 text-xs font-mono text-slate-400 font-bold">
                    Rp
                  </span>
                  <input
                    className="w-full bg-obsidian-950 border border-obsidian-700 rounded-lg pl-9 pr-3 py-2 text-xs font-mono text-emerald-400 font-bold focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
                    type="number"
                    step="1000"
                    value={quickAmountIdr}
                    onChange={(e) => setQuickAmountIdr(Number(e.target.value))}
                    required
                  />
                </div>
              </div>

              {/* Preset Amount Percent Buttons */}
              <div className="grid grid-cols-4 gap-1.5 font-mono text-xs">
                {SNIPE_PCT_PRESETS.map((p) => {
                  const active = quickAmountIdr === p.value;
                  return (
                    <button
                      key={p.label}
                      type="button"
                      onClick={() => setQuickAmountIdr(p.value)}
                      className={
                        active
                          ? 'py-1.5 rounded-lg bg-emerald-500/15 border border-emerald-500/40 text-emerald-300 font-semibold text-center text-[11px] transition'
                          : 'py-1.5 rounded-lg bg-obsidian-950 hover:bg-obsidian-800 border border-obsidian-700/80 text-slate-300 hover:text-white transition text-center text-[11px]'
                      }
                    >
                      {p.label}
                    </button>
                  );
                })}
              </div>

              {/* Snipe Configurations (Slippage & MEV) */}
              <div className="flex items-center justify-between p-2 rounded-lg bg-obsidian-950/70 border border-obsidian-800 text-[10px] font-mono">
                <div className="flex items-center gap-1.5 text-slate-400">
                  <LucideIcon name="shield" className="w-3.5 h-3.5 text-emerald-400" />
                  <span>
                    Anti-MEV Turbo: <strong className="text-emerald-400">AKTIF</strong>
                  </span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="text-slate-400">Slippage:</span>
                  <span className="px-1.5 py-0.5 rounded bg-obsidian-800 text-slate-200">1.0%</span>
                  <span className="px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300">
                    Auto
                  </span>
                </div>
              </div>
            </div>

            {/* Primary Call to Action Button: SNIPE PAPER */}
            <div className="pt-2">
              <button
                type="submit"
                className="w-full py-3 px-4 rounded-xl bg-gradient-to-r from-emerald-400 via-teal-400 to-cyan-400 hover:from-emerald-300 hover:to-cyan-300 text-obsidian-950 font-extrabold text-xs uppercase tracking-wider flex items-center justify-center gap-2 shadow-glow-emerald-lg transition transform active:scale-[0.99]"
              >
                <LucideIcon name="zap" className="w-4 h-4 fill-obsidian-950" />
                <span>
                  ⚡ SNIPE [{snipeMode}] - {formatIdr(quickAmountIdr)}
                </span>
              </button>
              <p className="text-center text-[10px] text-slate-400 font-mono mt-1.5">
                {isLive
                  ? '⚡ Eksekusi On-Chain Asli • Gas Fee & Slippage Terproteksi'
                  : 'Simulasi Eksekusi Cepat • Biaya Gas $0.00 (Solana Dev Simulated)'}
              </p>
            </div>
          </form>

          {/* ================= RIGHT PANEL: Live DexScreener Meme Feed ================= */}
          <div className="lg:col-span-7 bg-obsidian-900 border border-obsidian-700/80 rounded-xl p-3.5 space-y-3 flex flex-col justify-between">
            <div className="space-y-2.5">
              {/* Feed Title & Live Ping */}
              <div className="flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-obsidian-800">
                <div className="flex items-center gap-2">
                  <LucideIcon name="flame" className="w-4 h-4 text-orange-400" />
                  <h3 className="text-xs font-bold text-slate-100 uppercase tracking-wide">
                    Live DexScreener Meme Feed (100% Data Market Asli)
                  </h3>
                  <span className="flex h-2 w-2 rounded-full bg-emerald-400"></span>
                </div>
                <span className="text-[10px] text-slate-400 font-mono">
                  Klik salah satu token untuk langsung mengisi formulir Snipe
                </span>
              </div>

              {/* Table Container */}
              <div className="overflow-x-auto" data-purpose="dex-screener-table">
                <table className="w-full text-left border-collapse text-xs font-mono">
                  <thead>
                    <tr className="border-b border-obsidian-800 text-[10px] text-slate-400 uppercase tracking-wider">
                      <th className="py-1.5 px-2 font-semibold">Token</th>
                      <th className="py-1.5 px-2 font-semibold">Harga Live (USD / Rp)</th>
                      <th className="py-1.5 px-2 font-semibold">5m Change</th>
                      <th className="py-1.5 px-2 font-semibold">Liquidity / Vol</th>
                      <th className="py-1.5 px-2 font-semibold text-right">Aksi Cepat</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-obsidian-800/60 text-[11px]">
                    {liveTokens.map((t: any, idx: number) => {
                      const theme = AVATAR_THEMES[idx % AVATAR_THEMES.length];
                      const cleanSym = (t.base_symbol || t.symbol || 'TK').replace(/[^A-Za-z0-9]/g, '');
                      const initials = cleanSym.slice(0, 2).toUpperCase() || 'TK';
                      const dispSymbol = t.symbol?.startsWith('$') ? t.symbol : `$${t.symbol}`;
                      const chg5m = Number(t.price_change_5m ?? 0);
                      const isUp = chg5m >= 0;

                      return (
                        <tr
                          key={t.contract || t.symbol || idx}
                          className="hover:bg-obsidian-850/80 transition group"
                        >
                          <td className="py-2.5 px-2">
                            <div className="flex items-center gap-2">
                              <div
                                className={`w-6 h-6 rounded-full border flex items-center justify-center text-[10px] font-bold ${theme.circle}`}
                              >
                                {initials}
                              </div>
                              <div>
                                <div className={`font-bold text-white transition ${theme.hoverText}`}>
                                  {dispSymbol}
                                </div>
                                <div className="text-[9px] text-slate-400">
                                  {t.chain} • {t.launchpad}
                                </div>
                              </div>
                            </div>
                          </td>
                          <td className="py-2.5 px-2">
                            <div className="text-white font-medium">{formatUsd(t.price)}</div>
                            <div className="text-[9px] text-slate-400">
                              ≈ {formatIdr(t.price * usdIdr)}
                            </div>
                          </td>
                          <td className="py-2.5 px-2">
                            <span
                              className={
                                isUp
                                  ? 'text-emerald-400 font-bold bg-emerald-500/10 px-1.5 py-0.5 rounded border border-emerald-500/20 text-[10px]'
                                  : 'text-rose-400 font-bold bg-rose-500/10 px-1.5 py-0.5 rounded border border-rose-500/20 text-[10px]'
                              }
                            >
                              {isUp ? '+' : ''}
                              {chg5m.toFixed(1)}%
                            </span>
                          </td>
                          <td className="py-2.5 px-2 text-slate-300">
                            <div>${((t.liquidity || 0) / 1000).toFixed(1)}K</div>
                            <div className="text-[9px] text-slate-400">
                              MCap ${((t.market_cap || 0) / 1000).toFixed(1)}K
                            </div>
                          </td>
                          <td className="py-2.5 px-2 text-right">
                            <button
                              type="button"
                              onClick={() => setQuickTicker(t.base_symbol || t.symbol)}
                              className="px-2.5 py-1 rounded bg-emerald-500/15 hover:bg-emerald-500 text-emerald-300 hover:text-obsidian-950 font-bold text-[10px] border border-emerald-500/30 transition"
                            >
                              PILIH TOKEN
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Feed Pagination / Filter Bar */}
            <div className="flex items-center justify-between text-[10px] font-mono text-slate-400 pt-2 border-t border-obsidian-800">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
                <span>Memindai 12 pool baru per detik</span>
              </div>
              <div className="flex items-center gap-1">
                <span className="px-2 py-0.5 rounded bg-obsidian-950 text-slate-300 border border-obsidian-800">
                  Filter: Liq &gt; $5K
                </span>
                <span className="px-2 py-0.5 rounded bg-obsidian-950 text-emerald-400 border border-obsidian-800">
                  No Mint Revoke
                </span>
              </div>
            </div>
          </div>
        </section>
        {/* END: BottomDualPanelsSection */}
      </QueryState>
    </div>
  );
}
