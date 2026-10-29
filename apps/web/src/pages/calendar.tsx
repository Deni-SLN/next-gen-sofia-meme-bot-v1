import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { api, useApiQuery, formatIdr, formatUsd, getTradingMode } from '@/lib/api';
import { QueryState } from '@/components/QueryState';
import { LucideIcon } from '@/components/LucideIcon';
import { useUltrawide, toggleUltrawide } from '@/lib/useUltrawide';

const DEFAULT_SOL_WALLET = '8muJ3h4PPLmXhAVpJf8dnp9m17WsSaPNm9dSHcTsMVos';

export default function CalendarPage() {
  const isUltrawide = useUltrawide();
  const [selectedMode, setSelectedMode] = useState<'PAPER' | 'LIVE' | 'WALLET'>('PAPER');
  const [currentYear, setCurrentYear] = useState<number>(new Date().getFullYear());
  const [currentMonth, setCurrentMonth] = useState<number>(new Date().getMonth() + 1);
  const [selectedDayDate, setSelectedDayDate] = useState<string | null>(null);
  const [tradePage, setTradePage] = useState<number>(1);
  const [solanaWallet, setSolanaWallet] = useState<string>(DEFAULT_SOL_WALLET);
  const [copiedWalletKey, setCopiedWalletKey] = useState<string | null>(null);
  const [syncingWallet, setSyncingWallet] = useState<boolean>(false);
  const [syncNotice, setSyncNotice] = useState<string>('');
  const TRADES_PER_PAGE = 20;

  useEffect(() => {
    // Default to the current global trading mode
    const initialMode = getTradingMode();
    setSelectedMode(initialMode === 'LIVE' ? 'LIVE' : 'PAPER');

    if (typeof window !== 'undefined') {
      const savedSol = localStorage.getItem('sofia_sol_addr');
      const resolvedSol =
        !savedSol || savedSol === 'BYyj6C1tykoREhVFQKbmoNc6axT1tUrdMNZZT6XHoYZ8'
          ? DEFAULT_SOL_WALLET
          : savedSol;
      localStorage.setItem('sofia_sol_addr', resolvedSol);
      setSolanaWallet(resolvedSol);
      api.setPrimarySolanaWallet(resolvedSol).catch(() => {});
      api.syncWalletJournal(resolvedSol).then(() => calendarQuery.refetch()).catch(() => {});

      const walletHandler = (e: any) => {
        if (e?.detail) setSolanaWallet(String(e.detail));
      };
      window.addEventListener('sofia-solana-wallet-updated', walletHandler);
      return () => window.removeEventListener('sofia-solana-wallet-updated', walletHandler);
    }
  }, []);

  const calendarQuery = useApiQuery(
    () => api.getDailyCalendar(selectedMode, currentYear, currentMonth, solanaWallet),
    [selectedMode, currentYear, currentMonth, solanaWallet]
  );

  const calData = calendarQuery.data;
  const usdIdr = calData?.usd_idr || 17960;
  const summary = calData?.summary;
  const days: any[] = calData?.days || [];
  const activeSolanaWallet = solanaWallet || calData?.tracked_wallet?.address || DEFAULT_SOL_WALLET;

  const handleSyncOnchainWallet = async () => {
    setSyncingWallet(true);
    setSyncNotice('');
    try {
      const res = await api.syncWalletJournal(activeSolanaWallet);
      await calendarQuery.refetch();
      const totalCount = res?.total_wallet_trades ?? res?.synced ?? 0;
      setSyncNotice(
        `✅ Sinkronisasi Wallet Solana (${activeSolanaWallet.slice(0, 6)}...${activeSolanaWallet.slice(-4)}) selesai! Total ${totalCount} transaksi on-chain tercatat.`
      );
      setTimeout(() => setSyncNotice(''), 4000);
    } catch {
      setSyncNotice('⚠️ Gagal menyinkronkan RPC Solana, menampilkan arsip tersimpan.');
      setTimeout(() => setSyncNotice(''), 4000);
    } finally {
      setSyncingWallet(false);
    }
  };

  const handleCopyWallet = (text: string, key: string) => {
    if (typeof navigator !== 'undefined' && navigator.clipboard) {
      navigator.clipboard.writeText(text);
      setCopiedWalletKey(key);
      setTimeout(() => setCopiedWalletKey(null), 2500);
    }
  };

  useEffect(() => {
    setSelectedDayDate(null);
  }, [selectedMode]);

  // Find selected day or default to today (if it has trades) or latest day with trades
  useEffect(() => {
    if (days.length > 0 && !selectedDayDate) {
      const todayDay = days.find((d: any) => d.is_today);
      if (todayDay && todayDay.trades_count > 0) {
        setSelectedDayDate(todayDay.date);
      } else {
        const lastWithTrades = [...days].reverse().find((d: any) => d.trades_count > 0);
        setSelectedDayDate(lastWithTrades ? lastWithTrades.date : todayDay ? todayDay.date : days[days.length - 1]?.date);
      }
    }
  }, [days, selectedDayDate]);

  const selectedDay = days.find((d: any) => d.date === selectedDayDate) || days[0];

  useEffect(() => {
    setTradePage(1);
  }, [selectedDayDate, selectedMode, currentYear, currentMonth]);

  const handlePrevMonth = () => {
    if (currentMonth === 1) {
      setCurrentMonth(12);
      setCurrentYear((y) => y - 1);
    } else {
      setCurrentMonth((m) => m - 1);
    }
    setSelectedDayDate(null);
  };

  const handleNextMonth = () => {
    if (currentMonth === 12) {
      setCurrentMonth(1);
      setCurrentYear((y) => y + 1);
    } else {
      setCurrentMonth((m) => m + 1);
    }
    setSelectedDayDate(null);
  };

  const handleCurrentMonth = () => {
    const now = new Date();
    setCurrentYear(now.getFullYear());
    setCurrentMonth(now.getMonth() + 1);
    setSelectedDayDate(null);
  };

  // Determine pad empty cells for start of month (Monday = 0, Sunday = 6)
  const firstDayWeekday = days.length > 0 ? days[0].weekday : 0;
  const emptyPads = Array.from({ length: firstDayWeekday }, (_, i) => i);

  return (
    <div className="space-y-4">
      {/* Top Header Card: Title, Mode Separator Switch, and Month Navigator */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3 bg-obsidian-900 border border-obsidian-700 rounded-xl p-4 shadow-lg">
        <div>
          <div className="flex items-center gap-2">
            <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-amber-500/15 border border-amber-500/30 text-amber-400">
              <LucideIcon name="calendar-days" className="w-4 h-4" />
            </div>
            <div>
              <h1 className="text-base font-bold text-slate-100 flex items-center gap-2">
                Kalender PnL Harian
                <span className="text-[10px] px-2 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/30 font-mono">
                  Daily Performance Audit
                </span>
              </h1>
              <p className="text-xs text-slate-400">
                Lacak keuntungan bersih harian (100% net setelah slippage, biaya swap DEX &amp; gas fee Solana).
              </p>
            </div>
          </div>
        </div>

        {/* Center: 3-Mode Separator Switch (PAPER vs LIVE vs WALLET) */}
        <div className="flex items-center gap-2 flex-wrap">
          <div className="flex items-center bg-obsidian-950 p-1 rounded-xl border border-obsidian-700">
            <button
              type="button"
              onClick={() => setSelectedMode('PAPER')}
              className={
                selectedMode === 'PAPER'
                  ? 'flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-500 text-obsidian-950 font-bold text-xs shadow-glow-emerald transition'
                  : 'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-slate-400 hover:text-slate-200 text-xs font-medium transition'
              }
            >
              <LucideIcon name="shield-check" className="w-3.5 h-3.5" />
              <span>PnL Paper (Simulasi)</span>
            </button>
            <button
              type="button"
              onClick={() => setSelectedMode('LIVE')}
              className={
                selectedMode === 'LIVE'
                  ? 'flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-rose-600 text-white font-bold text-xs shadow-glow-rose transition'
                  : 'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-slate-400 hover:text-slate-200 text-xs font-medium transition'
              }
            >
              <span className="w-2 h-2 rounded-full bg-rose-500"></span>
              <span>PnL Live (Bot)</span>
            </button>
            <button
              type="button"
              onClick={() => setSelectedMode('WALLET')}
              className={
                selectedMode === 'WALLET'
                  ? 'flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-purple-500 text-white font-bold text-xs shadow-lg shadow-purple-500/25 transition'
                  : 'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-purple-300 hover:text-white text-xs font-medium transition'
              }
              title={`Kalender PnL khusus Wallet Solana: ${activeSolanaWallet}`}
            >
              <LucideIcon name="wallet" className="w-3.5 h-3.5" />
              <span>
                PnL Wallet ({activeSolanaWallet.slice(0, 4)}...{activeSolanaWallet.slice(-4)})
              </span>
            </button>
          </div>

          {/* Month Navigator Controls */}
          <div className="flex items-center bg-obsidian-950 rounded-xl border border-obsidian-700 p-0.5">
            <button
              type="button"
              onClick={handlePrevMonth}
              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-obsidian-800 transition"
              title="Bulan Sebelumnya"
            >
              <LucideIcon name="chevron-left" className="w-4 h-4" />
            </button>
            <span className="px-3 py-1 text-xs font-mono font-bold text-slate-200 min-w-[120px] text-center">
              {calData?.month_label || `${currentMonth}/${currentYear}`}
            </span>
            <button
              type="button"
              onClick={handleNextMonth}
              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-obsidian-800 transition"
              title="Bulan Berikutnya"
            >
              <LucideIcon name="chevron-right" className="w-4 h-4" />
            </button>
            <button
              type="button"
              onClick={handleCurrentMonth}
              className="ml-1 px-2.5 py-1 text-[11px] font-mono rounded-lg bg-obsidian-800 hover:bg-obsidian-700 text-slate-300 hover:text-white transition"
            >
              Hari Ini
            </button>
          </div>
        </div>
      </div>

      {/* RECORDED SOLANA WALLET BANNER ON PNL CALENDAR (SYNCED WITH SYSTEM SETTINGS) */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 px-4 py-2.5 rounded-xl bg-gradient-to-r from-purple-950/35 via-obsidian-900 to-obsidian-900 border border-purple-500/35 text-xs font-mono">
        <div className="flex flex-wrap items-center gap-2">
          <span className="px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-purple-500/40 text-[10px] font-extrabold">
            🟣 WALLET SOLANA TERCATAT
          </span>
          <span className="text-slate-400 text-[11px]">Dompet PnL On-Chain:</span>
          <code className="px-2 py-0.5 rounded bg-obsidian-950 border border-obsidian-800 text-emerald-300 font-bold select-all text-[11px]">
            {activeSolanaWallet}
          </code>
          <button
            type="button"
            onClick={() => handleCopyWallet(activeSolanaWallet, 'cal-sol-wallet')}
            className="px-2 py-0.5 rounded bg-obsidian-950 hover:bg-obsidian-800 text-cyan-300 border border-obsidian-750 text-[10px] font-bold flex items-center gap-1 transition"
            title="Salin Alamat Wallet Solana"
          >
            <LucideIcon name={copiedWalletKey === 'cal-sol-wallet' ? 'check' : 'copy'} className="w-3 h-3" />
            <span>{copiedWalletKey === 'cal-sol-wallet' ? '✓ Tersalin' : 'Salin Wallet'}</span>
          </button>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-[11px]">
          <button
            type="button"
            onClick={handleSyncOnchainWallet}
            disabled={syncingWallet}
            className="px-2.5 py-1 rounded-lg bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white border border-purple-400/40 font-extrabold flex items-center gap-1 transition shadow-sm"
            title="Sinkronkan riwayat transaksi on-chain Solana langsung dari RPC Mainnet ke mode WALLET"
          >
            <LucideIcon name="refresh-cw" className={`w-3 h-3 ${syncingWallet ? 'animate-spin' : ''}`} />
            <span>{syncingWallet ? 'Syncing On-Chain...' : 'Sync Wallet On-Chain'}</span>
          </button>
          <a
            href={`https://solscan.io/account/${activeSolanaWallet}`}
            target="_blank"
            rel="noreferrer"
            className="px-2.5 py-1 rounded-lg bg-obsidian-950 hover:bg-obsidian-850 text-purple-300 border border-purple-500/30 font-bold flex items-center gap-1 transition"
          >
            <span>Solscan Account</span>
            <span>↗</span>
          </a>
          <Link
            href="/settings?tab=wallet"
            className="px-2.5 py-1 rounded-lg bg-cyan-500/15 hover:bg-cyan-500/25 text-cyan-300 border border-cyan-500/30 font-bold flex items-center gap-1 transition"
            title="Ubah alamat wallet Solana di Pengaturan Sistem & Kredensial"
          >
            <LucideIcon name="sliders" className="w-3 h-3" />
            <span>Pengaturan &amp; Kredensial</span>
          </Link>
        </div>
      </div>

      {syncNotice && (
        <div className="px-3.5 py-2 rounded-lg bg-purple-950/60 border border-purple-500/40 text-purple-200 text-xs font-mono">
          {syncNotice}
        </div>
      )}

      <QueryState
        isLoading={calendarQuery.isLoading}
        isError={calendarQuery.isError}
        error={calendarQuery.error}
      >
        {/* KPI Summary Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {/* Card 1: Total PnL Month */}
          <div className="bg-obsidian-900/90 border border-obsidian-700 rounded-xl p-3.5">
            <div className="text-[10px] font-mono uppercase text-slate-400 flex items-center justify-between">
              <span>Total PnL Bulan Ini</span>
              <span className="text-[9px] px-1.5 py-0.5 rounded bg-obsidian-800 text-slate-300 font-mono">
                {selectedMode}
              </span>
            </div>
            <div
              className={`text-xl font-mono font-extrabold mt-1.5 ${
                (summary?.total_pnl_usd || 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'
              }`}
            >
              {(summary?.total_pnl_usd || 0) >= 0 ? '+' : ''}
              {formatUsd(summary?.total_pnl_usd)}
            </div>
            <div className="text-[11px] text-slate-400 font-mono mt-0.5">
              ≈ {(summary?.total_pnl_idr || 0) >= 0 ? '+' : ''}
              {formatIdr(summary?.total_pnl_idr)}
            </div>
            <div className="text-[10px] text-slate-500 mt-1">
              {summary?.winning_days || 0} Hari Hijau • {summary?.losing_days || 0} Hari Merah
            </div>
          </div>

          {/* Card 2: Day & Trade Win Rate */}
          <div className="bg-obsidian-900/90 border border-obsidian-700 rounded-xl p-3.5">
            <div className="text-[10px] font-mono uppercase text-slate-400 flex items-center justify-between">
              <span>Win Rate Hari / Trade</span>
              <LucideIcon name="badge-percent" className="w-3.5 h-3.5 text-cyan-400" />
            </div>
            <div className="text-xl font-mono font-extrabold text-cyan-400 mt-1.5">
              {summary?.day_win_rate_pct || 0}%{' '}
              <span className="text-xs font-normal text-slate-400">
                ({summary?.trade_win_rate_pct || 0}% trade)
              </span>
            </div>
            <div className="text-[11px] text-slate-400 font-mono mt-0.5">
              {summary?.total_winning_trades || 0} Win / {summary?.total_losing_trades || 0} Loss
            </div>
            <div className="text-[10px] text-slate-500 mt-1">
              Total {summary?.total_trades || 0} Closed Trades
            </div>
          </div>

          {/* Card 3: Total Volume & Net Fees */}
          <div className="bg-obsidian-900/90 border border-obsidian-700 rounded-xl p-3.5">
            <div className="text-[10px] font-mono uppercase text-slate-400 flex items-center justify-between">
              <span>Volume &amp; Biaya Total</span>
              <LucideIcon name="trending-up" className="w-3.5 h-3.5 text-amber-400" />
            </div>
            <div className="text-xl font-mono font-extrabold text-slate-200 mt-1.5">
              {formatUsd(summary?.total_volume_usd)}
            </div>
            <div className="text-[11px] text-slate-400 font-mono mt-0.5">
              ≈ {formatIdr(summary?.total_volume_idr)}
            </div>
            <div className="text-[10px] text-amber-400/90 font-mono mt-1">
              Gas &amp; DEX Fees: {formatIdr(summary?.total_fees_idr)} ({formatUsd(summary?.total_fees_usd)})
            </div>
          </div>

          {/* Card 4: Best Green Day */}
          <div className="bg-obsidian-900/90 border border-obsidian-700 rounded-xl p-3.5">
            <div className="text-[10px] font-mono uppercase text-slate-400 flex items-center justify-between">
              <span>Hari Terbaik (Best Day)</span>
              <LucideIcon name="zap" className="w-3.5 h-3.5 text-emerald-400" />
            </div>
            <div className="text-xl font-mono font-extrabold text-emerald-400 mt-1.5">
              {summary?.best_day ? `+${formatUsd(summary.best_day.pnl_usd)}` : '$0.00'}
            </div>
            <div className="text-[11px] text-slate-400 font-mono mt-0.5">
              {summary?.best_day ? `+${formatIdr(summary.best_day.pnl_idr)}` : 'Rp 0'}
            </div>
            <div className="text-[10px] text-slate-400 font-mono mt-1 truncate">
              {summary?.best_day ? `Tgl ${summary.best_day.date} (${summary.best_day.trades} trades)` : 'Belum ada trade'}
            </div>
          </div>
        </div>

        {(() => {
          const calendarGridBlock = (
            <div className="bg-obsidian-900 border border-obsidian-700 rounded-xl p-4 shadow-lg">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono font-bold text-slate-200 uppercase tracking-wider">
                Kalender Harian: {calData?.month_label}
              </span>
              <span className="text-[10px] font-mono text-slate-400">
                (Klik salah satu tanggal untuk melihat rincian order &amp; biaya)
              </span>
            </div>
            <div className="flex items-center gap-3 text-[10px] font-mono">
              <span className="flex items-center gap-1">
                <span className="w-2.5 h-2.5 rounded bg-emerald-500/30 border border-emerald-500/50"></span>
                <span>Profit (Hijau)</span>
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2.5 h-2.5 rounded bg-rose-500/30 border border-rose-500/50"></span>
                <span>Rugi (Merah)</span>
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2.5 h-2.5 rounded bg-obsidian-800 border border-obsidian-700"></span>
                <span>Netral / Standby</span>
              </span>
            </div>
          </div>

          {/* Weekday Headers */}
          <div className="grid grid-cols-7 gap-1.5 mb-1.5 text-center text-[10px] font-mono font-bold text-slate-400 uppercase">
            <div className="py-1">Sen</div>
            <div className="py-1">Sel</div>
            <div className="py-1">Rab</div>
            <div className="py-1">Kam</div>
            <div className="py-1">Jum</div>
            <div className="py-1 text-cyan-400">Sab</div>
            <div className="py-1 text-rose-400">Min</div>
          </div>

          {/* Calendar Grid Cells */}
          <div className="grid grid-cols-7 gap-1.5">
            {/* Empty Pad Cells */}
            {emptyPads.map((pad) => (
              <div
                key={`pad-${pad}`}
                className="min-h-[88px] rounded-lg bg-obsidian-950/40 border border-obsidian-800/40 opacity-40 pointer-events-none"
              />
            ))}

            {/* Days Cells */}
            {days.map((d: any) => {
              const isSelected = selectedDayDate === d.date;
              const hasTrades = d.trades_count > 0;
              const hasProfit = d.total_pnl_usd > 0.0001;
              const hasLoss = d.total_pnl_usd < -0.0001;

              let cellStyle = 'bg-obsidian-950 border-obsidian-800 hover:border-obsidian-600';
              let badgeColor = 'text-slate-400';
              let pnlColor = 'text-slate-400';

              if (hasProfit) {
                cellStyle = isSelected
                  ? 'bg-emerald-950/50 border-emerald-400 ring-2 ring-emerald-400/40 shadow-glow-emerald'
                  : 'bg-emerald-950/20 border-emerald-500/40 hover:border-emerald-400 hover:bg-emerald-950/30';
                badgeColor = 'text-emerald-400';
                pnlColor = 'text-emerald-400';
              } else if (hasLoss) {
                cellStyle = isSelected
                  ? 'bg-rose-950/50 border-rose-400 ring-2 ring-rose-400/40 shadow-glow-rose'
                  : 'bg-rose-950/20 border-rose-500/40 hover:border-rose-400 hover:bg-rose-950/30';
                badgeColor = 'text-rose-400';
                pnlColor = 'text-rose-400';
              } else if (isSelected) {
                cellStyle = 'bg-obsidian-850 border-cyan-400 ring-2 ring-cyan-400/40';
              }

              return (
                <button
                  key={d.date}
                  type="button"
                  onClick={() => setSelectedDayDate(d.date)}
                  className={`min-h-[92px] p-2 rounded-lg border text-left transition flex flex-col justify-between ${cellStyle}`}
                >
                  {/* Top: Day Number, Winrate Badge & Today indicator */}
                  <div className="flex items-center justify-between w-full gap-1">
                    <span
                      className={`text-xs font-mono font-bold ${
                        d.is_today ? 'text-cyan-400 underline decoration-cyan-400 decoration-2' : 'text-slate-300'
                      }`}
                    >
                      {d.day_number}
                    </span>
                    <div className="flex items-center gap-1">
                      {hasTrades && (
                        <span
                          className={`text-[9px] font-mono font-extrabold px-1.5 py-0.5 rounded border ${
                            (d.win_rate_pct ?? 0) >= 50
                              ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                              : 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                          }`}
                          title={`Win Rate Tanggal ${d.date}: ${d.win_rate_pct ?? 0}% (${d.winning_trades ?? 0} Win / ${d.losing_trades ?? 0} Loss)`}
                        >
                          WR {d.win_rate_pct ?? 0}%
                        </span>
                      )}
                      {d.is_today && (
                        <span className="text-[8px] font-sans font-extrabold uppercase px-1 py-0.2 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
                          Hari Ini
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Middle: Net PnL (USD + IDR) */}
                  <div className="my-1">
                    <div className={`text-xs font-mono font-bold ${pnlColor} truncate`}>
                      {hasProfit ? '+' : ''}
                      {formatUsd(d.total_pnl_usd)}
                    </div>
                    <div className="text-[10px] text-slate-400 font-mono truncate">
                      {hasProfit ? '+' : ''}
                      {formatIdr(d.total_pnl_idr)}
                    </div>
                  </div>

                  {/* Bottom: Posisi (W/L + Trades) & Gas Fee */}
                  <div className="flex flex-col gap-0.5 pt-1 border-t border-obsidian-800/60 w-full text-[9px] font-mono">
                    <div className="flex items-center justify-between w-full">
                      <span className={hasTrades ? badgeColor : 'text-slate-500'}>
                        {d.trades_count} {d.trades_count === 1 ? 'Trade' : 'Trades'}
                      </span>
                      {hasTrades && (
                        <span className="text-[9px] font-bold">
                          <span className="text-emerald-400">{d.winning_trades ?? 0}W</span>
                          <span className="text-slate-600">/</span>
                          <span className="text-rose-400">{d.losing_trades ?? 0}L</span>
                        </span>
                      )}
                    </div>
                    {hasTrades && (
                      <div className="flex items-center justify-between w-full text-[8px] text-slate-400">
                        <span>
                          Posisi: {d.buy_trades ?? 0}B / {d.sell_trades ?? 0}S
                        </span>
                        {d.fees_usd > 0 && (
                          <span title={`Biaya Swap & Gas: ${formatIdr(d.fees_idr)}`}>
                            Gas {formatIdr(d.fees_idr)}
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                </button>
              );
            })}
          </div>
        </div>
        );

        const dayInspectorBlock = (
          <div className="bg-obsidian-900 border border-obsidian-700 rounded-xl p-4 shadow-lg">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-obsidian-800">
            <div className="flex items-center gap-2">
              <div className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-pulse"></div>
              <h2 className="text-sm font-bold text-slate-100 flex items-center gap-2">
                Rincian Transaksi: <span className="font-mono text-cyan-300">{selectedDay?.date || 'Pilih Tanggal'}</span>
                {selectedDay?.is_today && (
                  <span className="text-[9px] font-sans font-semibold px-1.5 py-0.2 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
                    HARI INI
                  </span>
                )}
              </h2>
            </div>
            <div className="flex flex-wrap items-center gap-3 text-xs font-mono">
              <span className="text-slate-400">
                Win Rate Hari:{' '}
                <strong className="text-cyan-300">
                  {selectedDay?.win_rate_pct ?? 0}% ({selectedDay?.winning_trades ?? 0}W / {selectedDay?.losing_trades ?? 0}L)
                </strong>
              </span>
              <span className="text-slate-600">|</span>
              <span className="text-slate-400">
                Net PnL Hari:{' '}
                <strong
                  className={
                    (selectedDay?.total_pnl_usd || 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'
                  }
                >
                  {(selectedDay?.total_pnl_usd || 0) >= 0 ? '+' : ''}
                  {formatUsd(selectedDay?.total_pnl_usd)} ({formatIdr(selectedDay?.total_pnl_idr)})
                </strong>
              </span>
              <span className="text-slate-600">|</span>
              <span className="text-slate-400">
                Volume: <strong>{formatIdr(selectedDay?.volume_idr)}</strong>
              </span>
              <span className="text-slate-600">|</span>
              <span className="text-slate-400">
                Biaya Gas/DEX: <strong className="text-amber-300">{formatIdr(selectedDay?.fees_idr)}</strong>
              </span>
            </div>
          </div>

          {/* Trade Table (Paginated Max 20 Trades Per Page) */}
          {selectedDay?.trades && selectedDay.trades.length > 0 ? (() => {
            const totalDayTrades = selectedDay.trades.length;
            const totalTradePages = Math.max(1, Math.ceil(totalDayTrades / TRADES_PER_PAGE));
            const safeTradePage = Math.min(Math.max(1, tradePage), totalTradePages);
            const startIdx = (safeTradePage - 1) * TRADES_PER_PAGE;
            const endIdx = Math.min(totalDayTrades, startIdx + TRADES_PER_PAGE);
            const paginatedTrades = selectedDay.trades.slice(startIdx, endIdx);

            return (
              <div className="space-y-3 mt-3">
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs font-mono">
                    <thead>
                      <tr className="border-b border-obsidian-800 text-[10px] text-slate-400 uppercase">
                        <th className="py-2 px-2">Waktu</th>
                        <th className="py-2 px-2">Mode</th>
                        <th className="py-2 px-2">Wallet Solana</th>
                        <th className="py-2 px-2">Token / Pair</th>
                        <th className="py-2 px-2">Side</th>
                        <th className="py-2 px-2 text-right">Harga Eksekusi</th>
                        <th className="py-2 px-2 text-right">Qty</th>
                        <th className="py-2 px-2 text-right">Total Nilai</th>
                        <th className="py-2 px-2 text-right">Biaya (Slip/DEX/Gas)</th>
                        <th className="py-2 px-2 text-right">Net PnL (Bersih)</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-obsidian-800/60">
                      {paginatedTrades.map((t: any) => {
                        const isWin = (t.pnl_usd || 0) > 0;
                        const rowWallet = t.wallet_address || activeSolanaWallet;
                        return (
                          <tr key={t.id} className="hover:bg-obsidian-800/40 transition">
                            <td className="py-2.5 px-2 text-slate-400 text-[11px]">{t.time}</td>
                            <td className="py-2.5 px-2">
                              <span
                                className={`text-[9px] px-1.5 py-0.5 rounded font-sans font-bold ${
                                  t.mode === 'LIVE'
                                    ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40'
                                    : t.mode === 'WALLET'
                                    ? 'bg-purple-500/20 text-purple-300 border border-purple-500/40'
                                    : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                                }`}
                              >
                                {t.mode}
                              </span>
                            </td>
                            <td className="py-2.5 px-2">
                              <div className="flex items-center gap-1">
                                <span className="text-[10px] text-purple-300 font-bold" title={rowWallet}>
                                  {rowWallet.slice(0, 5)}...{rowWallet.slice(-4)}
                                </span>
                                <button
                                  type="button"
                                  onClick={() => handleCopyWallet(rowWallet, `cal-row-${t.id}`)}
                                  className="px-1 py-0.2 rounded bg-obsidian-950 hover:bg-obsidian-800 text-cyan-300 border border-obsidian-750 text-[9px]"
                                  title={`Salin Wallet: ${rowWallet}`}
                                >
                                  {copiedWalletKey === `cal-row-${t.id}` ? '✓' : '📋'}
                                </button>
                              </div>
                            </td>
                            <td className="py-2.5 px-2 font-bold text-slate-200">
                              <a
                                href={`https://dexscreener.com/search?q=${encodeURIComponent(t.symbol)}`}
                                target="_blank"
                                rel="noreferrer"
                                className="hover:text-cyan-400 transition underline decoration-dotted"
                              >
                                {t.symbol}
                              </a>
                            </td>
                            <td className="py-2.5 px-2">
                              <span
                                className={`text-[10px] uppercase font-bold px-1.5 py-0.5 rounded ${
                                  t.side === 'buy'
                                    ? 'bg-cyan-500/20 text-cyan-300'
                                    : 'bg-amber-500/20 text-amber-300'
                                }`}
                              >
                                {t.side}
                              </span>
                            </td>
                            <td className="py-2.5 px-2 text-right text-slate-300">
                              <div>{formatUsd(t.price)}</div>
                              <div className="text-[10px] text-slate-500">{formatIdr(t.price_idr)}</div>
                            </td>
                            <td className="py-2.5 px-2 text-right text-slate-300">
                              {Number(t.quantity).toLocaleString()}
                            </td>
                            <td className="py-2.5 px-2 text-right text-slate-300">
                              <div>{formatUsd(t.total_usd)}</div>
                              <div className="text-[10px] text-slate-500">{formatIdr(t.total_idr)}</div>
                            </td>
                            <td className="py-2.5 px-2 text-right text-slate-400 text-[11px]">
                              <div>{formatIdr(t.total_fee_idr)}</div>
                              <div className="text-[9px] text-slate-500">
                                Slip {t.slippage_pct}% • Gas {formatUsd(t.gas_fee_usd)}
                              </div>
                            </td>
                            <td className="py-2.5 px-2 text-right font-bold">
                              <div className={isWin ? 'text-emerald-400' : 'text-rose-400'}>
                                {isWin ? '+' : ''}
                                {formatUsd(t.pnl_usd)} ({t.pnl_pct > 0 ? '+' : ''}
                                {t.pnl_pct}%)
                              </div>
                              <div className="text-[10px] text-slate-400 font-normal">
                                {isWin ? '+' : ''}
                                {formatIdr(t.pnl_idr)}
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                {/* Pagination Controls for Daily Transaction Details (Max 20 trades per page) */}
                <div className="pt-2.5 border-t border-obsidian-800 flex flex-wrap items-center justify-between gap-2 text-xs font-mono">
                  <div className="text-[11px] text-slate-400">
                    Menampilkan <strong className="text-slate-200">{startIdx + 1}–{endIdx}</strong> dari{' '}
                    <strong className="text-cyan-300">{totalDayTrades}</strong> transaksi pada {selectedDay.date} (Maks {TRADES_PER_PAGE} trade/halaman)
                  </div>
                  <div className="flex items-center gap-1.5">
                    <button
                      type="button"
                      disabled={safeTradePage <= 1}
                      onClick={() => setTradePage((p) => Math.max(1, p - 1))}
                      className="px-2.5 py-1 rounded bg-obsidian-950 hover:bg-obsidian-800 text-slate-200 border border-obsidian-700 disabled:opacity-40 disabled:cursor-not-allowed text-[11px] font-bold transition"
                    >
                      ← Sebelumnya
                    </button>
                    <span className="px-2.5 py-1 rounded bg-obsidian-950 border border-cyan-500/30 text-cyan-300 text-[11px] font-extrabold">
                      Hal {safeTradePage} / {totalTradePages}
                    </span>
                    <button
                      type="button"
                      disabled={safeTradePage >= totalTradePages}
                      onClick={() => setTradePage((p) => Math.min(totalTradePages, p + 1))}
                      className="px-2.5 py-1 rounded bg-obsidian-950 hover:bg-obsidian-800 text-slate-200 border border-obsidian-700 disabled:opacity-40 disabled:cursor-not-allowed text-[11px] font-bold transition"
                    >
                      Berikutnya →
                    </button>
                  </div>
                </div>
              </div>
            );
          })() : (
            <div className="text-center py-8 text-xs font-mono text-slate-400">
              <p>Tidak ada riwayat closed trade yang tercatat pada {selectedDay?.date || 'tanggal ini'}.</p>
              {selectedDay?.is_today && (
                <p className="text-[11px] text-slate-500 mt-1">
                  Aktifkan Sniper Bot pada mode {selectedMode} atau lakukan snipe manual untuk mencatat transaksi hari ini.
                </p>
              )}
            </div>
          )}
        </div>
        );

        return isUltrawide ? (
          <div className="grid grid-cols-1 xl:grid-cols-12 gap-4 items-start">
            {/* Kolom Kiri: Kalender Bulanan Interaktif (7 Col) */}
            <div className="xl:col-span-7 space-y-4">
              {calendarGridBlock}
            </div>

            {/* Kolom Kanan: Rincian Transaksi Tanggal Terpilih dipindahkan ke samping! (5 Col) */}
            <div className="xl:col-span-5 space-y-4">
              {dayInspectorBlock}
            </div>
          </div>
        ) : (
          <>
            {calendarGridBlock}
            {dayInspectorBlock}
          </>
        );
      })()}
      </QueryState>
    </div>
  );
}
