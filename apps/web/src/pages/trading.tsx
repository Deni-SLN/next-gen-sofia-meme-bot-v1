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

export default function TradingPage() {
  const botQuery = useApiQuery(() => api.getBotStatus(), []);
  const portfolioQuery = useApiQuery(() => api.getPortfolio(), []);
  const walletsQuery = useApiQuery(() => api.getWallets(), []);
  const [selectedMode, setSelectedMode] = useState<'PAPER' | 'LIVE'>('PAPER');
  const [actionError, setActionError] = useState<string>('');
  const [actionSuccess, setActionSuccess] = useState<string>('');
  const [slippage, setSlippage] = useState<number>(1.0);
  const [jitoTip, setJitoTip] = useState<number>(0.005);
  const [autoTpMultiplier, setAutoTpMultiplier] = useState<number>(2.5);

  useEffect(() => {
    setSelectedMode(getTradingMode());
    const handler = (e: any) => {
      setSelectedMode(e.detail);
      walletsQuery.refetch();
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
        setActionSuccess('⏹ Mesin Sniper Bot berhasil dihentikan.');
        if (typeof window !== 'undefined') {
          window.dispatchEvent(new CustomEvent('sofia-bot-status-change', { detail: { running: false } }));
        }
      } else {
        await api.startBot(selectedMode);
        setActionSuccess(
          selectedMode === 'PAPER'
            ? '🟢 Mesin Sniper Bot berjalan dalam Mode PAPER (Data Market 100% Asli + Modal Simulasi Rp 150.000).'
            : '🔴 Mesin Sniper Bot berjalan dalam Mode LIVE.'
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

  return (
    <div className="space-y-3">
      <div className="px-3.5 py-2.5 rounded-xl bg-obsidian-900 border border-obsidian-700/80">
        <h1 className="text-sm font-extrabold text-slate-100 uppercase tracking-wide font-mono">
          🎯 Auto-Sniper Bot Engine
        </h1>
        <p className="text-xs text-slate-400">
          Gunakan <strong>Switch Mode</strong> di bawah atau di Header atas untuk memilih antara{' '}
          <strong>PAPER (Simulasi Rp 150.000)</strong> atau <strong>LIVE (Uang Asli)</strong>.
        </p>
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
                    🔴 <strong>Mode LIVE:</strong> Transaksi on-chain aktif • Saldo Hot Wallets Siap DEX:{' '}
                    <strong className="text-emerald-400">
                      {formatUsd(
                        (walletsQuery.data?.wallets || [])
                          .filter((w: any) => !w.name?.includes('Modal Paper') && w.gate === 'trading')
                          .reduce((acc: number, w: any) => acc + (Number(w.balance_usd) || 0), 0)
                      )}{' '}
                      (≈{' '}
                      {formatIdr(
                        (walletsQuery.data?.wallets || [])
                          .filter((w: any) => !w.name?.includes('Modal Paper') && w.gate === 'trading')
                          .reduce((acc: number, w: any) => acc + (Number(w.balance_idr) || 0), 0)
                      )}
                      )
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

          {/* Sniper Parameters */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 font-mono text-xs">
            <div className="p-3 rounded-lg bg-obsidian-950 border border-obsidian-800 space-y-1.5">
              <label className="text-slate-400 block uppercase text-[10px]">Max Slippage Tolerance (%)</label>
              <input
                type="number"
                step="0.5"
                value={slippage}
                onChange={(e) => setSlippage(Number(e.target.value))}
                className="w-full px-3 py-1.5 rounded bg-obsidian-900 border border-obsidian-700 text-emerald-400 font-bold"
              />
              <span className="text-[10px] text-slate-500 block">Auto-Slippage Turbo aktif</span>
            </div>

            <div className="p-3 rounded-lg bg-obsidian-950 border border-obsidian-800 space-y-1.5">
              <label className="text-slate-400 block uppercase text-[10px]">Jito Priority Bribe (SOL)</label>
              <input
                type="number"
                step="0.001"
                value={jitoTip}
                onChange={(e) => setJitoTip(Number(e.target.value))}
                className="w-full px-3 py-1.5 rounded bg-obsidian-900 border border-obsidian-700 text-cyan-400 font-bold"
              />
              <span className="text-[10px] text-slate-500 block">Memastikan inklusi blok-0 di validator</span>
            </div>

            <div className="p-3 rounded-lg bg-obsidian-950 border border-obsidian-800 space-y-1.5">
              <label className="text-slate-400 block uppercase text-[10px]">Auto Moonbag Take-Profit (x)</label>
              <input
                type="number"
                step="0.5"
                value={autoTpMultiplier}
                onChange={(e) => setAutoTpMultiplier(Number(e.target.value))}
                className="w-full px-3 py-1.5 rounded bg-obsidian-900 border border-obsidian-700 text-emerald-400 font-bold"
              />
              <span className="text-[10px] text-slate-500 block">Jual otomatis saat profit mencapai {autoTpMultiplier}x</span>
            </div>
          </div>
        </div>

        {/* Live Bot Activity Stream Card */}
        <BotActivityCard botStatus={botQuery.data?.status} />
      </QueryState>
    </div>
  );
}
