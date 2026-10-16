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
import { BotActivityCard } from '@/components/BotActivityCard';
import { LucideIcon } from '@/components/LucideIcon';

const RELAY_OPTIONS = [
  { id: 'JITO_0SLOT', label: '⚡ Jito 0-Slot Bundle (Anti-MEV)', desc: 'Inklusi blok-0 langsung ke validator Jito' },
  { id: 'HELIUS_STAKED', label: '🚀 Helius Staked SwQoS', desc: 'Jalur RPC staked prioritas tinggi' },
  { id: 'BLOXROUTE', label: '🛡️ bloXroute Trader API', desc: 'Proteksi frontrun & sandwich optimal' },
  { id: 'MAINNET_STD', label: '🌐 Mainnet Standard RPC', desc: 'Tanpa biaya bribe tambahan' },
];

const QUICK_SNIPE_PRESETS = [15000, 30000, 50000, 100000];

export default function TradingPage() {
  const botQuery = useApiQuery(() => api.getBotStatus(), []);
  const portfolioQuery = useApiQuery(() => api.getPortfolio(), []);
  const walletsQuery = useApiQuery(() => api.getWallets(), []);
  const configQuery = useApiQuery(() => api.getSniperConfig(), []);

  const [selectedMode, setSelectedMode] = useState<'PAPER' | 'LIVE'>('PAPER');
  const [actionError, setActionError] = useState<string>('');
  const [actionSuccess, setActionSuccess] = useState<string>('');

  // PumpSniper Terminal Config State
  const [relayMode, setRelayMode] = useState<string>('JITO_0SLOT');
  const [jitoTip, setJitoTip] = useState<number>(0.005);
  const [slippage, setSlippage] = useState<number>(1.5);
  const [minBondingPct, setMinBondingPct] = useState<number>(15);
  const [maxDevHoldPct, setMaxDevHoldPct] = useState<number>(5);
  const [autoTpPct, setAutoTpPct] = useState<number>(35);
  const [autoSlPct, setAutoSlPct] = useState<number>(15);
  const [trailingStop, setTrailingStop] = useState<boolean>(true);
  const [trailingPct, setTrailingPct] = useState<number>(8);
  const [multiWalletRot, setMultiWalletRot] = useState<boolean>(true);
  const [snipeAmountIdr, setSnipeAmountIdr] = useState<number>(25000);

  // 1-Click Terminal Snipe Bar State
  const [terminalSymbol, setTerminalSymbol] = useState<string>('BONK');
  const [terminalAmountIdr, setTerminalAmountIdr] = useState<number>(25000);
  const [isSniping, setIsSniping] = useState<boolean>(false);

  useEffect(() => {
    if (configQuery.data) {
      const c = configQuery.data;
      if (c.relay_mode) setRelayMode(c.relay_mode);
      if (c.jito_bribe_sol !== undefined) setJitoTip(Number(c.jito_bribe_sol));
      if (c.max_slippage_pct !== undefined) setSlippage(Number(c.max_slippage_pct));
      if (c.min_bonding_curve_pct !== undefined) setMinBondingPct(Number(c.min_bonding_curve_pct));
      if (c.max_dev_holding_pct !== undefined) setMaxDevHoldPct(Number(c.max_dev_holding_pct));
      if (c.auto_tp_pct !== undefined) setAutoTpPct(Number(c.auto_tp_pct));
      if (c.auto_sl_pct !== undefined) setAutoSlPct(Number(c.auto_sl_pct));
      if (c.trailing_stop_enabled !== undefined) setTrailingStop(Boolean(c.trailing_stop_enabled));
      if (c.trailing_stop_pct !== undefined) setTrailingPct(Number(c.trailing_stop_pct));
      if (c.multi_wallet_rotation !== undefined) setMultiWalletRot(Boolean(c.multi_wallet_rotation));
      if (c.snipe_amount_idr !== undefined) setSnipeAmountIdr(Number(c.snipe_amount_idr));
    }
  }, [configQuery.data]);

  useEffect(() => {
    setSelectedMode(getTradingMode());
    const handler = (e: any) => {
      setSelectedMode(e.detail);
      walletsQuery.refetch();
      portfolioQuery.refetch();
    };
    const botHandler = () => botQuery.refetch();
    const resetHandler = (e: any) => {
      if (e?.detail) portfolioQuery.setData(e.detail);
      else portfolioQuery.refetch();
      walletsQuery.refetch();
    };
    const tradeHandler = () => {
      botQuery.refetch();
      portfolioQuery.refetch();
      walletsQuery.refetch();
    };
    window.addEventListener('sofia-mode-change', handler);
    window.addEventListener('sofia-bot-status-change', botHandler);
    window.addEventListener('sofia-paper-reset', resetHandler);
    window.addEventListener('sofia-bot-trade-executed', tradeHandler);
    return () => {
      window.removeEventListener('sofia-mode-change', handler);
      window.removeEventListener('sofia-bot-status-change', botHandler);
      window.removeEventListener('sofia-paper-reset', resetHandler);
      window.removeEventListener('sofia-bot-trade-executed', tradeHandler);
    };
  }, []);

  const isRunning = botQuery.data?.status === 'running';
  const isLive = selectedMode === 'LIVE';
  const usdIdr = portfolioQuery.data?.usd_idr || 16500;

  const liveTradingWallets = (walletsQuery.data?.wallets || []).filter(
    (w: any) => !w.name?.includes('Modal Paper') && w.gate === 'trading'
  );
  const liveCashUsd = liveTradingWallets.reduce((acc: number, w: any) => acc + (Number(w.balance_usd) || 0), 0);
  const liveCashIdr = liveTradingWallets.reduce((acc: number, w: any) => acc + (Number(w.balance_idr) || 0), 0);

  const handleToggleSwitch = () => {
    const next = selectedMode === 'PAPER' ? 'LIVE' : 'PAPER';
    setSelectedMode(next);
    setTradingMode(next);
    setActionError('');
    setActionSuccess('');
  };

  const handlePowerButton = async () => {
    setActionError('');
    setActionSuccess('');
    try {
      if (isRunning) {
        await api.stopBot();
        setActionSuccess('⏹ Mesin PumpSniper Bot berhasil dihentikan.');
        if (typeof window !== 'undefined') {
          window.dispatchEvent(new CustomEvent('sofia-bot-status-change', { detail: { running: false } }));
        }
      } else {
        await api.startBot(selectedMode);
        setActionSuccess(
          selectedMode === 'PAPER'
            ? '🟢 Mesin PumpSniper Bot berjalan dalam Mode PAPER (Data Market 100% Asli + Modal Simulasi Rp 150.000).'
            : `🔴 Mesin PumpSniper Bot berjalan dalam Mode LIVE ON-CHAIN (${relayMode})! Seluruh transaksi terekam di Jurnal Trading.`
        );
        if (typeof window !== 'undefined') {
          window.dispatchEvent(new CustomEvent('sofia-bot-status-change', { detail: { running: true } }));
        }
      }
      botQuery.refetch();
    } catch (err: any) {
      setActionError(`${err.code || 'ERROR'}: ${err.message}`);
    }
  };

  const handleSaveConfig = async () => {
    setActionError('');
    setActionSuccess('');
    try {
      await api.updateSniperConfig({
        relay_mode: relayMode,
        jito_bribe_sol: jitoTip,
        max_slippage_pct: slippage,
        min_bonding_curve_pct: minBondingPct,
        max_dev_holding_pct: maxDevHoldPct,
        auto_tp_pct: autoTpPct,
        auto_sl_pct: autoSlPct,
        trailing_stop_enabled: trailingStop,
        trailing_stop_pct: trailingPct,
        multi_wallet_rotation: multiWalletRot,
        snipe_amount_idr: snipeAmountIdr,
      });
      setActionSuccess(
        `✅ Konfigurasi PumpSniper Terminal tersimpan! Relay: ${relayMode} • Auto TP: +${autoTpPct}% • SL: -${autoSlPct}% • Trailing Stop: ${
          trailingStop ? `AKTIF (${trailingPct}%)` : 'OFF'
        }`
      );
      configQuery.refetch();
    } catch (err: any) {
      setActionError(err?.message || 'Gagal menyimpan konfigurasi');
    }
  };

  const handleTerminalSnipe = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!terminalSymbol.trim()) return;
    setActionError('');
    setActionSuccess('');
    setIsSniping(true);
    try {
      const res = await api.snipeToken({
        symbol: terminalSymbol.trim(),
        amount_idr: terminalAmountIdr,
        slippage_pct: slippage,
        priority_fee_sol: jitoTip,
        anti_mev: relayMode !== 'MAINNET_STD',
        mode: selectedMode,
      });
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('sofia-bot-trade-executed', { detail: res }));
      }
      setActionSuccess(
        `⚡ [${res.mode}] 1-Click Snipe sukses! Beli ${Number(res.quantity || 0).toLocaleString()} ${res.symbol} @ ${formatUsd(
          res.entry_price
        )} (${formatIdr(res.entry_price_idr)}) senilai ${formatIdr(res.amount_idr)}${
          res.tx_hash ? ` • Tx: ${String(res.tx_hash).slice(0, 16)}...` : ''
        }`
      );
      portfolioQuery.refetch();
      walletsQuery.refetch();
    } catch (err: any) {
      setActionError(err?.message || 'Gagal mengeksekusi 1-Click Snipe');
    } finally {
      setIsSniping(false);
    }
  };

  const handleQuickSell = async (symbol: string, pct: number) => {
    setActionError('');
    setActionSuccess('');
    try {
      const res = await api.sellHolding(symbol, pct, selectedMode);
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('sofia-bot-trade-executed', { detail: res }));
      }
      setActionSuccess(
        `✅ [${res.mode || selectedMode}] Jual ${pct}% ${res.symbol} berhasil @ ${formatUsd(
          res.sell_price_usd
        )} • Realized PnL: ${res.realized_pnl_idr >= 0 ? '+' : ''}${formatIdr(res.realized_pnl_idr)}${
          res.tx_hash ? ` • Tx: ${String(res.tx_hash).slice(0, 14)}...` : ''
        }`
      );
      portfolioQuery.refetch();
      walletsQuery.refetch();
    } catch (err: any) {
      setActionError(err?.message || 'Gagal menjual posisi');
    }
  };

  const handlePanicSellAll = async () => {
    setActionError('');
    setActionSuccess('');
    try {
      const res = await api.panicSellAll(selectedMode);
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('sofia-bot-trade-executed', { detail: res }));
      }
      setActionSuccess(
        `🚨 [${res.mode || selectedMode}] PANIC SELL ALL selesai! ${res.positions_closed} posisi ditutup • Total Realized PnL: ${
          res.total_realized_pnl_idr >= 0 ? '+' : ''
        }${formatIdr(res.total_realized_pnl_idr)} (${formatUsd(res.total_realized_pnl_usd)})`
      );
      portfolioQuery.refetch();
      walletsQuery.refetch();
    } catch (err: any) {
      setActionError(err?.message || 'Gagal mengeksekusi Panic Sell All');
    }
  };

  const holdings: any[] = portfolioQuery.data?.holdings || [];

  return (
    <div className="space-y-3">
      {/* Top Banner */}
      <div className="px-3.5 py-2.5 rounded-xl bg-obsidian-900 border border-obsidian-700/80 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-sm font-extrabold text-slate-100 uppercase tracking-wide font-mono flex items-center gap-2">
            <span>🎯 PumpSniper Pro Terminal &amp; Auto-Sniper Engine</span>
            <span className="px-2 py-0.5 text-[10px] rounded bg-cyan-500/15 text-cyan-300 border border-cyan-500/30">
              {relayMode}
            </span>
          </h1>
          <p className="text-xs text-slate-400">
            Mendukung 100% <strong>Mode PAPER (Simulasi Rp 150.000)</strong> &amp;{' '}
            <strong>Mode LIVE (On-Chain Hot Wallet + Jurnal Neonbase)</strong> dengan Jito 0-Slot Anti-MEV.
          </p>
        </div>
        <div className="flex items-center gap-2 text-[11px] font-mono">
          <span className="px-2.5 py-1 rounded-lg bg-obsidian-950 border border-obsidian-800 text-slate-300">
            Auto TP: <strong className="text-emerald-400">+{autoTpPct}%</strong> • SL:{' '}
            <strong className="text-rose-400">-{autoSlPct}%</strong>
          </span>
        </div>
      </div>

      {actionSuccess && (
        <div className="p-3 rounded-lg bg-emerald-950/60 border border-emerald-500/40 text-emerald-200 text-xs font-mono">
          {actionSuccess}
        </div>
      )}
      {actionError && (
        <div className="p-3 rounded-lg bg-rose-950/60 border border-rose-800 text-rose-200 text-xs font-mono">
          ⚠️ {actionError}
        </div>
      )}

      <QueryState isLoading={botQuery.isLoading} isError={botQuery.isError} error={botQuery.error}>
        {/* Main Switch & Power Control Card */}
        <div className="p-4 rounded-xl bg-obsidian-900 border border-obsidian-700/80 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-4 border-b border-obsidian-800 pb-4">
            {/* Left: Current Engine Status */}
            <div className="space-y-1">
              <div className="text-[10px] font-mono uppercase text-slate-400">Status Mesin Sniper</div>
              <div className="flex items-center gap-2.5">
                <span
                  className={`w-3 h-3 rounded-full ${
                    isRunning ? 'bg-emerald-400 animate-ping' : 'bg-slate-600'
                  }`}
                />
                <span className="text-xl font-extrabold uppercase text-slate-100 font-mono">
                  {botQuery.data?.status || 'idle'}
                </span>
                <span
                  className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold border ${
                    selectedMode === 'PAPER'
                      ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
                      : 'bg-rose-500/20 text-rose-300 border-rose-500/40'
                  }`}
                >
                  MODE {selectedMode}
                </span>
              </div>
              <div className="text-xs font-mono text-slate-400 pt-0.5">
                {selectedMode === 'PAPER' ? (
                  <span>
                    🟢 <strong>Mode PAPER:</strong> Harga market 100% asli (DexScreener Live) • Sisa Kas Simulasi:{' '}
                    <strong className="text-emerald-400">
                      {formatUsd(portfolioQuery.data?.paper_cash_usd)} (≈ {formatIdr(portfolioQuery.data?.paper_cash_idr)})
                    </strong>
                  </span>
                ) : (
                  <span className="text-cyan-300">
                    🔴 <strong>Mode LIVE ON-CHAIN:</strong> Transaksi memotong/menambah Hot Wallet &amp; masuk Jurnal Neonbase • Saldo Siap DEX:{' '}
                    <strong className="text-emerald-400">
                      {formatUsd(liveCashUsd)} (≈ {formatIdr(liveCashIdr)})
                    </strong>
                  </span>
                )}
              </div>
            </div>

            {/* Right: Sliding Mode Switch + Single Power Button */}
            <div className="flex flex-wrap items-center gap-3">
              <div className="flex items-center gap-2.5 bg-obsidian-950 border border-obsidian-700 px-3 py-2 rounded-lg font-mono text-xs">
                <span
                  className={`font-bold ${
                    selectedMode === 'PAPER' ? 'text-emerald-400' : 'text-slate-500'
                  }`}
                >
                  PAPER (Rp 150rb)
                </span>
                <button
                  type="button"
                  role="switch"
                  aria-checked={selectedMode === 'LIVE'}
                  onClick={handleToggleSwitch}
                  className={`relative inline-flex h-6 w-12 items-center rounded-full transition-colors ${
                    selectedMode === 'LIVE' ? 'bg-rose-600' : 'bg-emerald-500'
                  }`}
                >
                  <span
                    className={`inline-block h-4 w-4 transform rounded-full bg-obsidian-950 transition-transform ${
                      selectedMode === 'LIVE' ? 'translate-x-7' : 'translate-x-1'
                    }`}
                  />
                </button>
                <span
                  className={`font-bold ${
                    selectedMode === 'LIVE' ? 'text-rose-400' : 'text-slate-500'
                  }`}
                >
                  LIVE (Uang Asli)
                </span>
              </div>

              <button
                type="button"
                onClick={handlePowerButton}
                className={`px-4 py-2 rounded-lg font-mono font-extrabold text-xs transition ${
                  isRunning
                    ? 'bg-rose-600/20 hover:bg-rose-600/30 text-rose-300 border border-rose-500/40 shadow-glow-rose'
                    : 'bg-emerald-500 hover:bg-emerald-400 text-obsidian-950 shadow-glow-emerald'
                }`}
              >
                {isRunning
                  ? '⏹ HENTIKAN BOT SEKARANG'
                  : `▶️ JALANKAN BOT (${selectedMode})`}
              </button>
            </div>
          </div>

          {/* 1-Click Terminal Snipe Bar (Inspired by PumpSniper Terminal) */}
          <form
            onSubmit={handleTerminalSnipe}
            className="p-3 rounded-xl bg-obsidian-950 border border-emerald-500/30 flex flex-wrap items-center justify-between gap-3 font-mono text-xs"
          >
            <div className="flex items-center gap-2">
              <span className="px-2 py-1 rounded bg-emerald-500/20 text-emerald-300 font-extrabold text-[10px]">
                ⚡ 1-CLICK TERMINAL SNIPE
              </span>
              <input
                type="text"
                value={terminalSymbol}
                onChange={(e) => setTerminalSymbol(e.target.value)}
                placeholder="Paste Mint CA / Simbol (PEPE, WIF, BONK)..."
                className="w-52 sm:w-64 px-3 py-1.5 rounded-lg bg-obsidian-900 border border-obsidian-700 text-white font-bold focus:outline-none focus:border-emerald-500"
              />
            </div>

            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-[10px] text-slate-400">Nominal:</span>
              {QUICK_SNIPE_PRESETS.map((amt) => (
                <button
                  key={amt}
                  type="button"
                  onClick={() => setTerminalAmountIdr(amt)}
                  className={`px-2 py-1 rounded text-[10px] font-bold transition ${
                    terminalAmountIdr === amt
                      ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                      : 'bg-obsidian-900 text-slate-400 border border-obsidian-800 hover:text-white'
                  }`}
                >
                  {formatIdr(amt)}
                </button>
              ))}
              <input
                type="number"
                step="5000"
                value={terminalAmountIdr}
                onChange={(e) => setTerminalAmountIdr(Number(e.target.value))}
                className="w-28 px-2.5 py-1 rounded-lg bg-obsidian-900 border border-obsidian-700 text-emerald-400 font-bold"
              />
            </div>

            <button
              type="submit"
              disabled={isSniping}
              className={`px-4 py-1.5 rounded-lg font-extrabold text-xs transition ${
                isLive
                  ? 'bg-rose-600 hover:bg-rose-500 text-white shadow-glow-rose'
                  : 'bg-emerald-500 hover:bg-emerald-400 text-obsidian-950 shadow-glow-emerald'
              }`}
            >
              {isSniping ? '⏳ Mengeksekusi...' : `⚡ SNIPE SEKARANG [${selectedMode}]`}
            </button>
          </form>

          {/* PumpSniper Pro Parameters Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 font-mono text-xs">
            {/* Relay Selector */}
            <div className="p-3 rounded-lg bg-obsidian-950 border border-obsidian-800 space-y-1.5">
              <label className="text-slate-400 block uppercase text-[10px]">
                0-Slot / Anti-MEV Relay Node
              </label>
              <select
                value={relayMode}
                onChange={(e) => setRelayMode(e.target.value)}
                className="w-full px-2.5 py-1.5 rounded bg-obsidian-900 border border-obsidian-700 text-cyan-300 font-bold"
              >
                {RELAY_OPTIONS.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.label}
                  </option>
                ))}
              </select>
              <span className="text-[10px] text-slate-500 block">
                {RELAY_OPTIONS.find((r) => r.id === relayMode)?.desc}
              </span>
            </div>

            {/* Jito Tip & Slippage */}
            <div className="p-3 rounded-lg bg-obsidian-950 border border-obsidian-800 space-y-1.5">
              <label className="text-slate-400 block uppercase text-[10px]">
                Jito Bribe (SOL) &amp; Max Slippage (%)
              </label>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <input
                    type="number"
                    step="0.001"
                    value={jitoTip}
                    onChange={(e) => setJitoTip(Number(e.target.value))}
                    className="w-full px-2.5 py-1.5 rounded bg-obsidian-900 border border-obsidian-700 text-cyan-400 font-bold"
                  />
                  <span className="text-[9px] text-slate-500">Bribe (SOL)</span>
                </div>
                <div>
                  <input
                    type="number"
                    step="0.5"
                    value={slippage}
                    onChange={(e) => setSlippage(Number(e.target.value))}
                    className="w-full px-2.5 py-1.5 rounded bg-obsidian-900 border border-obsidian-700 text-emerald-400 font-bold"
                  />
                  <span className="text-[9px] text-slate-500">Slippage (%)</span>
                </div>
              </div>
            </div>

            {/* Bonding Curve & Dev Holding Filter */}
            <div className="p-3 rounded-lg bg-obsidian-950 border border-obsidian-800 space-y-1.5">
              <label className="text-slate-400 block uppercase text-[10px]">
                Filter Bonding Curve &amp; Max Dev Hold
              </label>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <input
                    type="number"
                    step="5"
                    value={minBondingPct}
                    onChange={(e) => setMinBondingPct(Number(e.target.value))}
                    className="w-full px-2.5 py-1.5 rounded bg-obsidian-900 border border-obsidian-700 text-amber-300 font-bold"
                  />
                  <span className="text-[9px] text-slate-500">Min Curve (%)</span>
                </div>
                <div>
                  <input
                    type="number"
                    step="1"
                    value={maxDevHoldPct}
                    onChange={(e) => setMaxDevHoldPct(Number(e.target.value))}
                    className="w-full px-2.5 py-1.5 rounded bg-obsidian-900 border border-obsidian-700 text-emerald-300 font-bold"
                  />
                  <span className="text-[9px] text-slate-500">Max Dev (%)</span>
                </div>
              </div>
            </div>

            {/* Auto Take Profit & Stop Loss */}
            <div className="p-3 rounded-lg bg-obsidian-950 border border-obsidian-800 space-y-1.5">
              <label className="text-slate-400 block uppercase text-[10px]">
                Auto Take-Profit (+%) &amp; Stop-Loss (-%)
              </label>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <input
                    type="number"
                    step="5"
                    value={autoTpPct}
                    onChange={(e) => setAutoTpPct(Number(e.target.value))}
                    className="w-full px-2.5 py-1.5 rounded bg-obsidian-900 border border-obsidian-700 text-emerald-400 font-bold"
                  />
                  <span className="text-[9px] text-emerald-400/80">Take Profit +%</span>
                </div>
                <div>
                  <input
                    type="number"
                    step="1"
                    value={autoSlPct}
                    onChange={(e) => setAutoSlPct(Number(e.target.value))}
                    className="w-full px-2.5 py-1.5 rounded bg-obsidian-900 border border-obsidian-700 text-rose-400 font-bold"
                  />
                  <span className="text-[9px] text-rose-400/80">Stop Loss -%</span>
                </div>
              </div>
            </div>
          </div>

          {/* Bottom Row: Trailing Stop, Multi-Wallet Rotation, and Save Config Button */}
          <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-obsidian-800 font-mono text-xs">
            <div className="flex flex-wrap items-center gap-4">
              <label className="flex items-center gap-2 cursor-pointer text-slate-300">
                <input
                  type="checkbox"
                  checked={trailingStop}
                  onChange={(e) => setTrailingStop(e.target.checked)}
                  className="rounded border-obsidian-700 bg-obsidian-950 text-emerald-500"
                />
                <span>
                  📈 Trailing Stop-Loss ({trailingPct}%)
                </span>
              </label>

              <label className="flex items-center gap-2 cursor-pointer text-slate-300">
                <input
                  type="checkbox"
                  checked={multiWalletRot}
                  onChange={(e) => setMultiWalletRot(e.target.checked)}
                  className="rounded border-obsidian-700 bg-obsidian-950 text-cyan-500"
                />
                <span>
                  🔄 Multi-Wallet Anti-Bubble Rotation
                </span>
              </label>

              <div className="flex items-center gap-1.5 text-slate-400">
                <span>Ukuran Auto-Snipe Bot:</span>
                <input
                  type="number"
                  step="5000"
                  value={snipeAmountIdr}
                  onChange={(e) => setSnipeAmountIdr(Number(e.target.value))}
                  className="w-24 px-2 py-1 rounded bg-obsidian-950 border border-obsidian-700 text-emerald-300 font-bold"
                />
                <span className="text-[10px]">({formatIdr(snipeAmountIdr)})</span>
              </div>
            </div>

            <button
              type="button"
              onClick={handleSaveConfig}
              className="px-3.5 py-1.5 rounded-lg bg-cyan-500/20 hover:bg-cyan-500 text-cyan-300 hover:text-obsidian-950 border border-cyan-500/40 font-extrabold text-xs transition"
            >
              💾 Simpan Konfigurasi Terminal
            </button>
          </div>
        </div>

        {/* Active Open Positions Monitor (With 25%/50%/100% Quick Sell & Panic Sell All) */}
        <div className="p-4 rounded-xl bg-obsidian-900 border border-obsidian-700/80 space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-obsidian-800 pb-2.5">
            <div className="flex items-center gap-2">
              <LucideIcon name="activity" className="w-4 h-4 text-emerald-400" />
              <h2 className="text-xs font-extrabold uppercase tracking-wider text-slate-100 font-mono">
                Posisi Aktif di Terminal ({holdings.length} Koin)
              </h2>
            </div>
            <div className="flex items-center gap-2">
              {holdings.length > 0 && (
                <button
                  type="button"
                  onClick={handlePanicSellAll}
                  className="px-3 py-1 rounded-lg bg-rose-600 hover:bg-rose-500 text-white font-mono font-extrabold text-[11px] shadow-glow-rose transition"
                >
                  🚨 PANIC SELL ALL (100% LIKUIDASI)
                </button>
              )}
            </div>
          </div>

          {holdings.length === 0 ? (
            <div className="py-4 text-center text-xs font-mono text-slate-400">
              Belum ada posisi terbuka. Gunakan <strong>⚡ 1-Click Terminal Snipe</strong> di atas atau nyalakan <strong>Auto-Sniper Bot</strong> untuk mulai membeli koin potensial secara otomatis.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead className="bg-obsidian-950 text-slate-400 border-b border-obsidian-800 text-[10px] uppercase">
                  <tr>
                    <th className="p-2.5">Token</th>
                    <th className="p-2.5">Qty</th>
                    <th className="p-2.5">Entry</th>
                    <th className="p-2.5">Harga Live</th>
                    <th className="p-2.5">Nilai Posisi</th>
                    <th className="p-2.5">Floating PnL</th>
                    <th className="p-2.5 text-right">Quick Exit ({selectedMode})</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-obsidian-800/60">
                  {holdings.map((h: any) => (
                    <tr key={h.symbol} className="hover:bg-obsidian-850/60">
                      <td className="p-2.5 font-extrabold text-white">${h.symbol}</td>
                      <td className="p-2.5 text-slate-300">{Number(h.quantity).toLocaleString()}</td>
                      <td className="p-2.5 text-slate-300">{formatUsd(h.avg_entry_price)}</td>
                      <td className="p-2.5 text-cyan-300 font-bold">{formatUsd(h.current_price)}</td>
                      <td className="p-2.5">
                        <div className="font-bold text-white">{formatUsd(h.value)}</div>
                        <div className="text-[10px] text-slate-400">≈ {formatIdr(h.value * usdIdr)}</div>
                      </td>
                      <td className="p-2.5">
                        <span className={`font-bold ${h.pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                          {h.pnl >= 0 ? '+' : ''}
                          {formatUsd(h.pnl)} ({h.pnl_pct}%)
                        </span>
                      </td>
                      <td className="p-2.5 text-right">
                        <div className="inline-flex gap-1">
                          {[25, 50, 100].map((pct) => (
                            <button
                              key={pct}
                              type="button"
                              onClick={() => handleQuickSell(h.symbol, pct)}
                              className={`px-2 py-1 rounded font-bold text-[10px] transition ${
                                pct === 100
                                  ? 'bg-rose-600 hover:bg-rose-500 text-white'
                                  : 'bg-obsidian-800 hover:bg-obsidian-700 text-rose-300 border border-rose-500/30'
                              }`}
                            >
                              Jual {pct}%
                            </button>
                          ))}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Live Bot Activity Stream Card */}
        <BotActivityCard botStatus={botQuery.data?.status} />
      </QueryState>
    </div>
  );
}
