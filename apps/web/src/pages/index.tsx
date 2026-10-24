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
import { StartBotModal, StartBotParams } from '@/components/StartBotModal';
import { useUltrawide, toggleUltrawide } from '@/lib/useUltrawide';
const AVATAR_THEMES = [
  {
    circle: 'bg-emerald-500/10 border-emerald-500/25 text-emerald-400',
    hoverText: 'group-hover:text-emerald-400',
  },
  {
    circle: 'bg-cyan-500/10 border-cyan-500/25 text-cyan-400',
    hoverText: 'group-hover:text-cyan-400',
  },
  {
    circle: 'bg-amber-500/10 border-amber-500/25 text-amber-400',
    hoverText: 'group-hover:text-amber-400',
  },
  {
    circle: 'bg-purple-500/10 border-purple-500/25 text-purple-400',
    hoverText: 'group-hover:text-purple-400',
  },
];

const SNIPE_PCT_PRESETS = [
  { label: '10% (15rb)', value: 15000 },
  { label: '25% (37.5rb)', value: 37500 },
  { label: '50% (75rb)', value: 75000 },
  { label: '100% (150rb)', value: 150000 },
];

export default function DashboardPage() {
  const isUltrawide = useUltrawide();
  const botQuery = useApiQuery(() => api.getBotStatus(), []);
  const portfolioQuery = useApiQuery(() => api.getPortfolio(), []);
  const perfQuery = useApiQuery(() => api.getPerformance(), []);
  const pulseQuery = useApiQuery(() => api.getPulse(), []);
  const walletsQuery = useApiQuery(() => api.getWallets(), []);

  const [quickTicker, setQuickTicker] = useState<string>('PEPE');
  const [quickAmountIdr, setQuickAmountIdr] = useState<number | string>(15000);
  const [snipeMode, setSnipeMode] = useState<'PAPER' | 'LIVE'>('PAPER');
  const [snipeMsg, setSnipeMsg] = useState<string>('');
  const [snipeErr, setSnipeErr] = useState<string>('');
  const [activeTarget, setActiveTarget] = useState<string>('SOL/USDC');
  const [showStartBotModal, setShowStartBotModal] = useState<boolean>(false);
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
          'Portofolio Paper telah direset kembali ke saldo awal Rp 150.000.'
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
              `[Auto-Bot Sell] Menjual ${act.symbol} @ ${formatUsd(act.sell_price_usd)} • Realized PnL: ${formatIdr(act.realized_pnl_idr)}`
            );
          } else {
            setSnipeMsg(
              `[Auto-Bot Buy] Membeli ${Number(act.quantity || 0).toLocaleString()} ${act.symbol} senilai ${formatIdr(act.amount_idr)} @ ${formatUsd(act.entry_price)}`
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
    if (botQuery.data?.status === 'running') {
      try {
        await api.stopBot();
        setSnipeMsg('Auto-Sniper Bot dihentikan.');
        if (typeof window !== 'undefined') {
          window.dispatchEvent(new CustomEvent('sofia-bot-status-change', { detail: { running: false } }));
        }
        botQuery.refetch();
      } catch (err: unknown) {
        if (err instanceof Error) {
          setSnipeErr(err.message);
        } else {
          setSnipeErr('Gagal menghentikan bot.');
        }
      }
    } else {
      setShowStartBotModal(true);
    }
  };

  const handleConfirmStartBot = async (params: StartBotParams) => {
    setSnipeMsg('');
    setSnipeErr('');
    await api.startBot(snipeMode, botQuery.data?.strategy_mode || 'DEFAULT', {
      buy_amount_usd: params.buy_amount_usd,
      max_open_positions: params.max_open_positions,
      slippage_pct: params.slippage_pct,
    });
    setSnipeMsg(
      `🟢 Auto-Sniper Bot diaktifkan (${snipeMode} Mode • $${params.buy_amount_usd.toFixed(2)}/trade • Maks ${params.max_open_positions} posisi • Slip ${params.slippage_pct}%).`
    );
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('sofia-bot-status-change', { detail: { running: true } }));
    }
    botQuery.refetch();
  };

  const handleInstantSnipe = async (e: React.FormEvent) => {
    e.preventDefault();
    setSnipeMsg('');
    setSnipeErr('');
    try {
      const res = await api.snipeToken({
        symbol: quickTicker,
        amount_idr: Number(quickAmountIdr) || 15000,
        slippage_pct: 1.0,
        priority_fee_sol: 0.005,
        anti_mev: true,
        mode: snipeMode,
      });
      setSnipeMsg(
        `[${res.mode}] Berhasil membeli ${res.quantity.toLocaleString()} ${res.symbol} @ ${formatUsd(
          res.entry_price
        )} (${formatIdr(res.entry_price_idr)}) senilai ${formatIdr(res.amount_idr)}`
      );
      portfolioQuery.refetch();
      perfQuery.refetch();
      walletsQuery.refetch();
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

  const d = portfolioQuery.data;
  const paperInitialIdr = Number(d?.paper_initial_idr) || 150000;
  const paperInitialUsd = Number(d?.paper_initial_usd) || (paperInitialIdr / usdIdr);
  const paperCashUsd = d?.paper_cash_usd ?? paperInitialUsd;
  const paperCashIdr = d?.paper_cash_idr ?? paperInitialIdr;
  const totalEquityUsd = d?.total_equity_usd ?? paperCashUsd;
  const totalEquityIdr = d?.total_equity_idr ?? paperCashIdr;
  const holdingsValUsd = d?.total_value ?? 0;
  const holdingsValIdr = d?.total_value_idr ?? 0;
  const holdingsCount = (d?.holdings || []).length;
  const realizedPnlUsd = perfQuery.data?.total_pnl ?? 0;
  const realizedPnlIdr = perfQuery.data?.total_pnl_idr ?? 0;
  const unrealizedPnlUsd = d?.unrealized_pnl ?? 0;
  const unrealizedPnlIdr = d?.unrealized_pnl_idr ?? 0;
  const netPnlUsd = realizedPnlUsd + unrealizedPnlUsd;
  const netPnlIdr = realizedPnlIdr + unrealizedPnlIdr;
  const netPnlPct = paperInitialIdr > 0 ? ((totalEquityIdr - paperInitialIdr) / paperInitialIdr) * 100 : 0;
  const isBotRunning = botQuery.data?.status === 'running';

  const isLive = snipeMode === 'LIVE';

  const allWallets: any[] = walletsQuery.data?.wallets || [];
  const liveWallets = allWallets.filter((w) => !w.name?.includes('Modal Paper'));
  const liveTradingWallets = liveWallets.filter((w) => w.gate === 'trading');

  const liveTotalEquityUsd = liveWallets.reduce((acc, w) => acc + (Number(w.balance_usd) || 0), 0);
  const liveTotalEquityIdr = liveWallets.reduce((acc, w) => acc + (Number(w.balance_idr) || 0), 0);

  const liveCashUsd = liveTradingWallets.reduce((acc, w) => acc + (Number(w.balance_usd) || 0), 0);
  const liveCashIdr = liveTradingWallets.reduce((acc, w) => acc + (Number(w.balance_idr) || 0), 0);

  // Separate USDC (Kas Trading) & Gas Fee (SOL on-chain)
  const primaryLiveTradingWallet = liveTradingWallets[0];
  const liveUsdcBal = primaryLiveTradingWallet?.usdc_balance ?? (
    (primaryLiveTradingWallet?.spl_tokens || []).find((t: { symbol?: string; mint?: string; amount?: number }) => t.symbol === 'USDC' || t.mint === 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v')?.amount || 0
  );
  const liveUsdcUsd = primaryLiveTradingWallet?.usdc_usd ?? liveUsdcBal;
  const liveUsdcIdr = primaryLiveTradingWallet?.usdc_idr ?? (liveUsdcUsd * usdIdr);

  const liveGasBal = primaryLiveTradingWallet?.gas_fee_balance ?? (Number(primaryLiveTradingWallet?.balance) || 0);
  const liveGasToken = primaryLiveTradingWallet?.gas_fee_token || primaryLiveTradingWallet?.token || 'SOL';
  const liveGasUsd = primaryLiveTradingWallet?.gas_fee_usd ?? Math.max(0, (Number(primaryLiveTradingWallet?.balance_usd) || 0) - liveUsdcUsd);
  const liveGasIdr = primaryLiveTradingWallet?.gas_fee_idr ?? (liveGasUsd * usdIdr);

  const activeEquityUsd = isLive ? (liveTotalEquityUsd + holdingsValUsd) : totalEquityUsd;
  const activeEquityIdr = isLive ? (liveTotalEquityIdr + holdingsValIdr) : totalEquityIdr;
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
    <div className="space-y-4">
      {/* Clean AnalisMarket-Style Page Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-1">
        <div>
          <h1 className="text-lg font-semibold text-white tracking-tight">
            Command Center
          </h1>
          <p className="text-xs text-slate-400 mt-0.5">
            Ringkasan ekuitas portofolio, kurva performa, dan terminal eksekusi real-time DexScreener.
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span className="px-2.5 py-1 rounded-lg bg-obsidian-900 border border-obsidian-700/80 text-slate-300 font-mono text-[11px]">
            Target: <strong className="text-white">{activeTarget}</strong>
          </span>
          <button
            type="button"
            onClick={handleBotPower}
            className="px-3 py-1 rounded-lg bg-obsidian-900 hover:bg-obsidian-850 text-slate-200 border border-obsidian-700/80 font-medium text-[11px] flex items-center gap-1.5 transition"
          >
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                isBotRunning ? 'bg-emerald-400 animate-pulse' : 'bg-slate-500'
              }`}
            />
            <span>{isBotRunning ? 'Hentikan Scan' : 'Mulai Scan'}</span>
          </button>
        </div>
      </div>

      {snipeMsg && (
        <div className="px-3.5 py-2.5 rounded-xl bg-emerald-500/10 border border-emerald-500/25 text-xs text-emerald-300">
          {snipeMsg}
        </div>
      )}
      {snipeErr && (
        <div className="px-3.5 py-2.5 rounded-xl bg-rose-500/10 border border-rose-500/25 text-xs text-rose-300">
          {snipeErr}
        </div>
      )}

      <QueryState
        isLoading={botQuery.isLoading}
        isError={botQuery.isError}
        error={botQuery.error}
        hasData={!!botQuery.data}
      >
        {/* BEGIN: Clean 4-Metric KPI Cards */}
        <section
          className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3"
          data-purpose="stat-counter-grid"
        >
          {/* Card 1: Total Ekuitas */}
          <div className="bg-obsidian-900 border border-obsidian-700/70 rounded-xl p-4 transition hover:border-obsidian-600">
            <div className="flex items-center justify-between text-xs mb-2">
              <span className="text-slate-400 font-medium">
                {isLive ? 'Total Ekuitas (Live)' : 'Total Ekuitas (Paper)'}
              </span>
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-obsidian-850 text-slate-300 border border-obsidian-700">
                {isLive ? 'On-Chain' : 'Simulasi'}
              </span>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-semibold font-mono tracking-tight text-white">
                {formatUsd(activeEquityUsd)}
              </span>
              <span className="text-xs text-slate-400 font-mono">≈ {formatIdr(activeEquityIdr)}</span>
            </div>
            <div className="mt-3 text-[11px] text-slate-400 flex items-center justify-between border-t border-obsidian-800/80 pt-2">
              <span>
                {isLive
                  ? `${liveWallets.length} dompet terhubung`
                  : `Modal awal ${formatIdr(paperInitialIdr)}`}
              </span>
              <span
                className={`font-mono font-medium ${
                  activePnlPct >= 0 ? 'text-emerald-400' : 'text-rose-400'
                }`}
              >
                {activePnlPct >= 0 ? '+' : ''}
                {activePnlPct.toFixed(2)}%
              </span>
            </div>
          </div>

          {/* Card 2: Saldo Kas Tersedia */}
          <div className="bg-obsidian-900 border border-obsidian-700/70 rounded-xl p-4 transition hover:border-obsidian-600">
            <div className="flex items-center justify-between text-xs mb-2">
              <span className="text-slate-400 font-medium">
                Saldo Kas Tersedia
              </span>
              <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded font-bold border ${
                isLive ? 'bg-cyan-500/15 text-cyan-400 border-cyan-500/30' : 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
              }`}>
                {isLive ? 'USDC & GAS FEE' : 'Siap Beli'}
              </span>
            </div>
            {isLive ? (
              <div className="space-y-2 mt-1">
                <div>
                  <div className="text-[10px] font-mono uppercase text-slate-400 flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-cyan-400"></span>
                    <span>Kas Belanja (USDC)</span>
                  </div>
                  <div className="flex items-baseline gap-1.5 mt-0.5">
                    <span className="text-xl font-bold font-mono text-cyan-300">
                      {liveUsdcBal.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 })} USDC
                    </span>
                    <span className="text-[11px] text-slate-400 font-mono">
                      ≈ {formatIdr(liveUsdcIdr)}
                    </span>
                  </div>
                </div>
                <div className="border-t border-obsidian-800/80 pt-1.5">
                  <div className="text-[10px] font-mono uppercase text-slate-400 flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-amber-400"></span>
                    <span>Gas Fee Tersedia ({liveGasToken})</span>
                  </div>
                  <div className="flex items-baseline gap-1.5 mt-0.5">
                    <span className="text-sm font-bold font-mono text-amber-300">
                      {Number(liveGasBal).toFixed(6)} {liveGasToken}
                    </span>
                    <span className="text-[10px] text-slate-400 font-mono">
                      ≈ {formatUsd(liveGasUsd)} ({formatIdr(liveGasIdr)})
                    </span>
                  </div>
                </div>
              </div>
            ) : (
              <>
                <div className="flex items-baseline gap-2">
                  <span className="text-2xl font-semibold font-mono tracking-tight text-white">
                    {formatUsd(activeCashUsd)}
                  </span>
                  <span className="text-xs text-emerald-400 font-medium">
                    Siap Beli
                  </span>
                </div>
                <div className="mt-3 text-[11px] text-slate-400 flex items-center justify-between border-t border-obsidian-800/80 pt-2 font-mono">
                  <span>{formatIdr(activeCashIdr)}</span>
                  <span className="text-slate-500 font-sans">
                    Likuiditas Paper
                  </span>
                </div>
              </>
            )}
          </div>

          {/* Card 3: Nilai Posisi Aktif */}
          <div className="bg-obsidian-900 border border-obsidian-700/70 rounded-xl p-4 transition hover:border-obsidian-600">
            <div className="flex items-center justify-between text-xs mb-2">
              <span className="text-slate-400 font-medium">
                Nilai Posisi Aktif
              </span>
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-obsidian-850 text-slate-400 border border-obsidian-700">
                {holdingsCount} Posisi
              </span>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-semibold font-mono tracking-tight text-white">
                {formatUsd(holdingsValUsd)}
              </span>
              <span className="text-xs text-slate-400 font-mono">≈ {formatIdr(holdingsValIdr)}</span>
            </div>
            <div className="mt-3 text-[11px] text-slate-400 flex items-center justify-between border-t border-obsidian-800/80 pt-2">
              <span>Portofolio Terbuka</span>
              <span className="text-slate-400">
                {holdingsCount > 0 ? 'Dipantau TP/SL' : 'Menunggu Sinyal'}
              </span>
            </div>
          </div>

          {/* Card 4: Total Profit / Loss */}
          <div className="bg-obsidian-900 border border-obsidian-700/70 rounded-xl p-4 transition hover:border-obsidian-600">
            <div className="flex items-center justify-between text-xs mb-2">
              <span className="text-slate-400 font-medium">
                Total Profit / Loss (PnL)
              </span>
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-obsidian-850 text-slate-400 border border-obsidian-700">
                Kumulatif
              </span>
            </div>
            <div className="flex items-baseline gap-2">
              <span
                className={`text-2xl font-semibold font-mono tracking-tight ${
                  netPnlUsd >= 0 ? 'text-emerald-400' : 'text-rose-400'
                }`}
              >
                {netPnlUsd >= 0 ? '+' : ''}
                {formatUsd(netPnlUsd)}
              </span>
              <span
                className={`text-xs font-mono ${
                  activePnlPct >= 0 ? 'text-emerald-400' : 'text-rose-400'
                }`}
              >
                {activePnlPct >= 0 ? '+' : ''}
                {activePnlPct.toFixed(2)}%
              </span>
            </div>
            <div className="mt-3 text-[11px] text-slate-400 flex items-center justify-between border-t border-obsidian-800/80 pt-2 font-mono">
              <span className={netPnlIdr >= 0 ? 'text-emerald-400' : 'text-rose-400'}>
                {netPnlIdr >= 0 ? '+' : ''}
                {formatIdr(netPnlIdr)}
              </span>
              <span className="text-slate-500 font-sans">Realized + Floating</span>
            </div>
            <div className="mt-2 pt-1.5 border-t border-obsidian-800/80 grid grid-cols-2 gap-2 text-[10px] font-mono">
              <div className="flex items-center justify-between bg-obsidian-950/70 px-2 py-1 rounded border border-obsidian-800/70">
                <span className="text-emerald-300 font-bold">🟢 WR PAPER</span>
                <span className="text-white font-extrabold">
                  {Number(d?.paper_winrate_pct ?? 0).toFixed(1)}% ({Number(d?.paper_wins ?? 0)}W/{Number(d?.paper_losses ?? 0)}L)
                </span>
              </div>
              <div className="flex items-center justify-between bg-obsidian-950/70 px-2 py-1 rounded border border-obsidian-800/70">
                <span className="text-rose-300 font-bold">🔴 WR LIVE</span>
                <span className="text-white font-extrabold">
                  {Number(d?.live_winrate_pct ?? 0).toFixed(1)}% ({Number(d?.live_wins ?? 0)}W/{Number(d?.live_losses ?? 0)}L)
                </span>
              </div>
            </div>
          </div>
        </section>
        {/* END: Clean 4-Metric KPI Cards */}

        {(() => {
          const terminalAndChartBlock = (
            <div className="space-y-4">
              <BotActivityCard
                botStatus={botQuery.data?.status}
                onTargetChange={(t) => setActiveTarget(t)}
              />
              <PnLChart
                points={perfQuery.data?.pnl_chart || []}
                usdIdr={usdIdr}
                totalTrades={perfQuery.data?.total_trades ?? 0}
                realizedIdr={realizedPnlIdr}
                floatingIdr={unrealizedPnlIdr}
                liveEquityUsd={activeEquityUsd}
                liveEquityIdr={activeEquityIdr}
              />
            </div>
          );

          const sniperCard = (
            <form
              onSubmit={handleInstantSnipe}
              className="w-full bg-obsidian-900 border border-obsidian-700/70 rounded-xl p-4 flex flex-col justify-between space-y-4 shadow-lg"
            >
            <div className="space-y-3.5">
              <div className="flex items-center justify-between pb-2.5 border-b border-obsidian-800">
                <div className="flex items-center gap-2">
                  <LucideIcon name="zap" className="w-4 h-4 text-emerald-400" />
                  <h3 className="text-sm font-semibold text-white">
                    Eksekusi Cepat (Instant Snipe)
                  </h3>
                </div>
                <button
                  type="button"
                  onClick={handleToggleModeSwitch}
                  className={
                    snipeMode === 'PAPER'
                      ? 'text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/25'
                      : 'text-[10px] font-mono px-2 py-0.5 rounded bg-rose-500/15 text-rose-400 border border-rose-500/30'
                  }
                >
                  Mode {snipeMode}
                </button>
              </div>

              <p className="text-xs text-slate-400 leading-relaxed">
                Masukkan ticker atau Contract Address (CA) token dari DexScreener / GMGN untuk
                mengeksekusi pembelian instan.
              </p>

              {/* Input: Contract Address / Ticker */}
              <div className="space-y-1.5">
                <label className="text-[11px] text-slate-400 font-medium flex items-center justify-between">
                  <span>Ticker / Contract Address</span>
                  <span className="text-slate-500 font-mono text-[10px]">Auto-Detect CA</span>
                </label>
                <div className="relative">
                  <input
                    className="w-full bg-obsidian-950 border border-obsidian-700 rounded-lg px-3 py-2 text-xs font-mono text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500/60"
                    placeholder="Contoh: BONK atau Mint CA..."
                    type="text"
                    value={quickTicker}
                    onChange={(e) => setQuickTicker(e.target.value)}
                    required
                  />
                  <button
                    type="button"
                    onClick={handlePasteClipboard}
                    className="absolute right-2 top-1.5 px-2 py-0.5 rounded bg-obsidian-850 text-[10px] font-mono text-slate-400 hover:text-white border border-obsidian-700 transition"
                  >
                    Paste
                  </button>
                </div>
              </div>

              {/* Input: Nominal Snipe (Rupiah) */}
              <div className="space-y-1.5">
                <div className="flex justify-between items-center text-[11px]">
                  <span className="text-slate-400 font-medium">Nominal Pembelian (IDR)</span>
                  <span className="text-slate-400 font-mono text-[10px]">
                    Maks: {formatIdr(activeCashIdr)}
                  </span>
                </div>
                <div className="relative">
                  <span className="absolute left-3 top-2 text-xs font-mono text-slate-400">
                    Rp
                  </span>
                  <input
                    className="w-full bg-obsidian-950 border border-obsidian-700 rounded-lg pl-9 pr-3 py-2 text-xs font-mono text-white font-semibold focus:outline-none focus:border-emerald-500/60"
                    type="number"
                    step="1000"
                    value={quickAmountIdr}
                    onChange={(e) => setQuickAmountIdr(e.target.value === '' ? '' : Number(e.target.value))}
                    placeholder="15000"
                    required
                  />
                </div>
              </div>

              {/* Preset Amount Percent Buttons */}
              <div className="grid grid-cols-4 gap-1.5 text-xs">
                {SNIPE_PCT_PRESETS.map((p) => {
                  const active = quickAmountIdr === p.value;
                  return (
                    <button
                      key={p.label}
                      type="button"
                      onClick={() => setQuickAmountIdr(p.value)}
                      className={
                        active
                          ? 'py-1.5 rounded-lg bg-emerald-500/15 border border-emerald-500/35 text-emerald-300 font-medium text-center text-[11px] transition'
                          : 'py-1.5 rounded-lg bg-obsidian-950 hover:bg-obsidian-850 border border-obsidian-800 text-slate-400 hover:text-slate-200 transition text-center text-[11px]'
                      }
                    >
                      {p.label}
                    </button>
                  );
                })}
              </div>

              {/* Snipe Configurations */}
              <div className="flex items-center justify-between p-2.5 rounded-lg bg-obsidian-950 border border-obsidian-800 text-[11px]">
                <span className="text-slate-400">
                  Proteksi MEV: <strong className="text-emerald-400 font-medium">Aktif</strong>
                </span>
                <span className="text-slate-400 font-mono">
                  Slippage: <strong className="text-slate-200">1.0% Auto</strong>
                </span>
              </div>
            </div>

            <div className="pt-2">
              <button
                type="submit"
                className="w-full py-2.5 px-4 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-obsidian-950 font-semibold text-xs flex items-center justify-center gap-2 transition"
              >
                <LucideIcon name="zap" className="w-4 h-4" />
                <span>
                  Beli Sekarang ({snipeMode}) • {formatIdr(Number(quickAmountIdr) || 0)}
                </span>
              </button>
            </div>
          </form>
        );

        const trenchesCard = (
          <div className="w-full bg-obsidian-900 border border-obsidian-700/70 rounded-xl p-4 space-y-3 flex flex-col justify-between shadow-lg">
            <div className="space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2 pb-2.5 border-b border-obsidian-800">
                <div className="flex items-center gap-2">
                  <h3 className="text-sm font-semibold text-white">
                    Live DexScreener Feed
                  </h3>
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
                </div>
                <span className="text-[11px] text-slate-400">
                  Klik token untuk mengisi ke panel eksekusi
                </span>
              </div>

              <div className="overflow-x-auto" data-purpose="dex-screener-table">
                <table className="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr className="border-b border-obsidian-800 text-[11px] text-slate-400">
                      <th className="py-2 px-2 font-medium">Token</th>
                      <th className="py-2 px-2 font-medium">Harga</th>
                      <th className="py-2 px-2 font-medium">5m %</th>
                      <th className="py-2 px-2 font-medium">Likuiditas / MCap</th>
                      <th className="py-2 px-2 font-medium text-right">Aksi</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-obsidian-800/60 text-xs font-mono">
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
                          className="hover:bg-obsidian-850/70 transition group"
                        >
                          <td className="py-2.5 px-2 font-sans">
                            <div className="flex items-center gap-2.5">
                              <div
                                className={`w-7 h-7 rounded-lg border flex items-center justify-center text-[10px] font-semibold font-mono ${theme.circle}`}
                              >
                                {initials}
                              </div>
                              <div>
                                <div className={`font-semibold text-white transition ${theme.hoverText}`}>
                                  {dispSymbol}
                                </div>
                                <div className="text-[10px] text-slate-500">
                                  {t.chain} • {t.launchpad}
                                </div>
                              </div>
                            </div>
                          </td>
                          <td className="py-2.5 px-2">
                            <div className="text-white font-medium">{formatUsd(t.price)}</div>
                            <div className="text-[10px] text-slate-500">
                              {formatIdr(t.price * usdIdr)}
                            </div>
                          </td>
                          <td className="py-2.5 px-2">
                            <span
                              className={
                                isUp
                                  ? 'text-emerald-400 font-medium bg-emerald-500/10 px-1.5 py-0.5 rounded text-[11px]'
                                  : 'text-rose-400 font-medium bg-rose-500/10 px-1.5 py-0.5 rounded text-[11px]'
                              }
                            >
                              {isUp ? '+' : ''}
                              {chg5m.toFixed(1)}%
                            </span>
                          </td>
                          <td className="py-2.5 px-2 text-slate-300">
                            <div>${((t.liquidity || 0) / 1000).toFixed(1)}K</div>
                            <div className="text-[10px] text-slate-500">
                              MCap ${((t.market_cap || 0) / 1000).toFixed(1)}K
                            </div>
                          </td>
                          <td className="py-2.5 px-2 text-right font-sans">
                            <button
                              type="button"
                              onClick={() => setQuickTicker(t.base_symbol || t.symbol)}
                              className="px-2.5 py-1 rounded-lg bg-obsidian-850 hover:bg-emerald-500/15 text-slate-300 hover:text-emerald-300 font-medium text-[11px] border border-obsidian-700 hover:border-emerald-500/30 transition"
                            >
                              Pilih
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="flex items-center justify-between text-[11px] text-slate-500 pt-2.5 border-t border-obsidian-800">
              <span>Sumber: DexScreener &amp; GMGN.ai</span>
              <span>Filter: Anti-Rug Verified</span>
            </div>
            </div>
          );

          return isUltrawide ? (
            <div className="grid grid-cols-1 xl:grid-cols-12 gap-4 items-start">
              {/* Kolom Kiri: Terminal Bot & Kurva Equity PnL (7 Cols) */}
              <div className="xl:col-span-7 space-y-4">
                {terminalAndChartBlock}
              </div>

              {/* Kolom Kanan: Instant Sniper & Trenches Feed dipindahkan ke samping! (5 Cols) */}
              <div className="xl:col-span-5 space-y-4">
                {sniperCard}
                {trenchesCard}
              </div>
            </div>
          ) : (
            <>
              {terminalAndChartBlock}
              <section
                className="grid grid-cols-1 lg:grid-cols-12 gap-4"
                data-purpose="sniper-and-market-dual-panel"
              >
                <div className="lg:col-span-5">{sniperCard}</div>
                <div className="lg:col-span-7">{trenchesCard}</div>
              </section>
            </>
          );
        })()}
      </QueryState>

      <StartBotModal
        isOpen={showStartBotModal}
        onClose={() => setShowStartBotModal(false)}
        onConfirm={handleConfirmStartBot}
        mode={snipeMode}
        strategyMode={botQuery.data?.strategy_mode || 'DEFAULT'}
        initialBuyAmountUsd={1.0}
        initialMaxPositions={3}
        initialSlippagePct={1.5}
        usdIdr={usdIdr}
        solPrice={liveGasBal > 0.0001 ? Math.round(liveGasUsd / liveGasBal) : 145}
        liveUsdcBal={liveUsdcBal}
        liveGasBal={liveGasBal}
        liveGasToken={liveGasToken}
      />
    </div>
  );
}
