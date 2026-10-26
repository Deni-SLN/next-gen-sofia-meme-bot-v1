import React, { useState, useEffect } from 'react';
import Head from 'next/head';
import { api, useApiQuery, formatIdr, formatUsd, getTradingMode, setTradingMode, AutoEntryState } from '@/lib/api';
import { QueryState } from '@/components/QueryState';
import { LucideIcon } from '@/components/LucideIcon';

export default function AutoEntryPage() {
  const [mode, setMode] = useState<'PAPER' | 'LIVE'>('PAPER');
  const [entryAmountIdr, setEntryAmountIdr] = useState<number>(20000);
  const [maxEntries, setMaxEntries] = useState<number>(5);
  const [slippagePct, setSlippagePct] = useState<number>(1.0);
  const [minSafetyScore, setMinSafetyScore] = useState<number>(70);
  const [targetSource, setTargetSource] = useState<string>('ALL_RADAR');
  const [actionNotice, setActionNotice] = useState<{ type: 'ok' | 'err'; text: string } | null>(null);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  // Poll state every 2.5 seconds for live telemetry
  const autoEntryQuery = useApiQuery(() => api.getAutoEntryStatus(), []);
  const state = autoEntryQuery.data;

  useEffect(() => {
    const timer = setInterval(() => {
      autoEntryQuery.refetch();
    }, 2500);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      setMode(getTradingMode());
      const handleModeChange = (e: any) => setMode(e.detail);
      window.addEventListener('sofia-mode-change', handleModeChange);
      return () => window.removeEventListener('sofia-mode-change', handleModeChange);
    }
  }, []);

  // Sync state into inputs when loaded
  useEffect(() => {
    if (state) {
      if (state.entry_amount_idr) setEntryAmountIdr(state.entry_amount_idr);
      if (state.max_entries) setMaxEntries(state.max_entries);
      if (state.slippage_pct) setSlippagePct(state.slippage_pct);
      if (state.min_safety_score !== undefined) setMinSafetyScore(state.min_safety_score);
      if (state.target_source) setTargetSource(state.target_source);
      if (state.mode) setMode(state.mode);
    }
  }, [state?.status]);

  const handleCopyText = (text: string, key: string) => {
    if (typeof navigator !== 'undefined' && navigator.clipboard) {
      navigator.clipboard.writeText(text);
      setCopiedKey(key);
      setTimeout(() => setCopiedKey(null), 2500);
    }
  };

  const showNotice = (type: 'ok' | 'err', text: string) => {
    setActionNotice({ type, text });
    setTimeout(() => setActionNotice(null), 4000);
  };

  const handleStart = async () => {
    try {
      await api.startAutoEntry({
        entry_amount_idr: entryAmountIdr,
        max_entries: maxEntries,
        slippage_pct: slippagePct,
        min_safety_score: minSafetyScore,
        mode: mode,
        target_source: targetSource,
      });
      await autoEntryQuery.refetch();
      showNotice('ok', `⚡ Bot Auto Entry berhasil dijalankan! Target: ${maxEntries} entry @ ${formatIdr(entryAmountIdr)}.`);
    } catch (err: any) {
      showNotice('err', err?.message || 'Gagal menjalankan bot Auto Entry.');
    }
  };

  const handleStop = async () => {
    try {
      await api.stopAutoEntry();
      await autoEntryQuery.refetch();
      showNotice('ok', '⏹️ Bot Auto Entry telah dihentikan.');
    } catch (err: any) {
      showNotice('err', err?.message || 'Gagal menghentikan bot.');
    }
  };

  const handleResetCounter = async () => {
    try {
      await api.resetAutoEntryCounter();
      await autoEntryQuery.refetch();
      showNotice('ok', '🔄 Counter entry dan riwayat sesi telah di-reset ke 0.');
    } catch (err: any) {
      showNotice('err', err?.message || 'Gagal mereset counter.');
    }
  };

  const handleTriggerScan = async () => {
    try {
      const res = await api.triggerAutoEntryScan();
      await autoEntryQuery.refetch();
      if (res?.action === 'entry_filled') {
        showNotice('ok', `⚡ Berhasil Auto Entry token ${res.entry?.symbol} senilai ${formatIdr(res.entry?.amount_idr)}!`);
      } else if (res?.action === 'quota_reached') {
        showNotice('ok', 'Batas maksimal entry sudah tercapai.');
      } else {
        showNotice('ok', 'Scan selesai. Tidak ada kandidat baru yang memenuhi filter saat ini.');
      }
    } catch (err: any) {
      showNotice('err', err?.message || 'Gagal memindai.');
    }
  };

  const handleModeToggle = (newMode: 'PAPER' | 'LIVE') => {
    setMode(newMode);
    setTradingMode(newMode);
    api.updateAutoEntryConfig({ mode: newMode }).then(() => autoEntryQuery.refetch());
  };

  const isRunning = state?.status === 'RUNNING';
  const isQuotaReached = state?.status === 'QUOTA_REACHED';
  const totalCount = state?.total_entries_count || 0;
  const maxQuota = state?.max_entries || maxEntries;
  const remainingQuota = Math.max(0, maxQuota - totalCount);
  const quotaPercent = Math.min(100, Math.round((totalCount / Math.max(1, maxQuota)) * 100));

  return (
    <>
      <Head>
        <title>Auto Entry Bot — Eksekusi Disiplin | Sofia Market 3.9</title>
      </Head>

      <div className="space-y-6 pb-12">
        {/* HERO BANNER */}
        <div className="bg-gradient-to-r from-obsidian-900 via-obsidian-900 to-obsidian-850 border border-obsidian-750 rounded-2xl p-5 sm:p-6 shadow-xl flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1.5">
            <div className="flex flex-wrap items-center gap-2">
              <span
                className={`w-2.5 h-2.5 rounded-full ${
                  isRunning ? 'bg-emerald-400 animate-pulse' : isQuotaReached ? 'bg-amber-400' : 'bg-slate-500'
                }`}
              />
              <h1 className="text-xl sm:text-2xl font-black text-slate-100 tracking-tight flex items-center gap-2.5">
                <LucideIcon name="crosshair" className="w-6 h-6 text-cyan-400" />
                <span>Auto Entry Bot</span>
              </h1>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-cyan-500/15 text-cyan-300 border border-cyan-500/30">
                ENTRY ONLY
              </span>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-purple-500/15 text-purple-300 border border-purple-500/30">
                SOFIA 3.9
              </span>
            </div>
            <p className="text-xs sm:text-sm text-slate-400 max-w-2xl leading-relaxed">
              Bot khusus akuisisi entry otomatis tanpa intervensi manual. Atur nominal uang per entry, batas maksimal posisi, dan toleransi slippage. Bot akan memindai pool radar dan mengeksekusi order entry disiplin hingga batas maksimal tercapai.
            </p>
          </div>

          {/* MODE TOGGLE SWITCH */}
          <div className="flex items-center gap-2 bg-obsidian-950 p-1.5 rounded-xl border border-obsidian-750 shrink-0">
            <button
              type="button"
              onClick={() => handleModeToggle('PAPER')}
              className={`px-3 py-1.5 rounded-lg text-xs font-mono font-bold transition ${
                mode === 'PAPER'
                  ? 'bg-cyan-500 text-obsidian-950 font-extrabold shadow-sm'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              📄 Paper (Simulasi)
            </button>
            <button
              type="button"
              onClick={() => handleModeToggle('LIVE')}
              className={`px-3 py-1.5 rounded-lg text-xs font-mono font-bold transition ${
                mode === 'LIVE'
                  ? 'bg-emerald-500 text-obsidian-950 font-extrabold shadow-sm'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              ⚡ Live On-Chain
            </button>
          </div>
        </div>

        {/* FEEDBACK NOTICE */}
        {actionNotice && (
          <div
            className={`p-3.5 rounded-xl text-xs font-mono flex items-center gap-2 shadow-lg transition-all ${
              actionNotice.type === 'ok'
                ? 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30'
                : 'bg-rose-500/15 text-rose-300 border border-rose-500/30'
            }`}
          >
            <LucideIcon name={actionNotice.type === 'ok' ? 'check' : 'alert-circle'} className="w-4 h-4 shrink-0" />
            <span>{actionNotice.text}</span>
          </div>
        )}

        {/* 4 TELEMETRY STAT CARDS */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
          {/* Card 1: Bot Status */}
          <div className="p-4 rounded-xl bg-obsidian-900 border border-obsidian-750 shadow-md space-y-2">
            <div className="text-[11px] font-mono text-slate-400 flex items-center justify-between">
              <span>STATUS ENGINE</span>
              <span className={`w-2 h-2 rounded-full ${isRunning ? 'bg-emerald-400 animate-pulse' : isQuotaReached ? 'bg-amber-400' : 'bg-slate-500'}`} />
            </div>
            <div className="text-lg font-black text-white font-mono flex items-center gap-2">
              {isRunning && <span className="text-emerald-400">AKTIF &amp; SCANNING</span>}
              {isQuotaReached && <span className="text-amber-400">KUOTA TERCAPAI</span>}
              {!isRunning && !isQuotaReached && <span className="text-slate-400">STANDBY (OFF)</span>}
            </div>
            <div className="text-[11px] text-slate-400">
              {isRunning
                ? 'Memindai koin baru sesuai kriteria...'
                : isQuotaReached
                ? 'Maksimal entry terpenuhi, pemindaian dijeda'
                : 'Klik Jalankan untuk memulai pemindaian'}
            </div>
          </div>

          {/* Card 2: Entry Counter & Progress */}
          <div className="p-4 rounded-xl bg-obsidian-900 border border-obsidian-750 shadow-md space-y-2">
            <div className="text-[11px] font-mono text-slate-400 flex items-center justify-between">
              <span>KUOTA ENTRY TERCAPAI</span>
              <span className="text-cyan-300 font-bold">{quotaPercent}%</span>
            </div>
            <div className="text-lg font-black text-white font-mono">
              <span className="text-cyan-400">{totalCount}</span>
              <span className="text-slate-500"> / </span>
              <span>{maxQuota} Posisi</span>
            </div>
            <div className="space-y-1">
              <div className="w-full h-1.5 rounded-full bg-obsidian-950 overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-cyan-500 to-emerald-400 transition-all duration-300"
                  style={{ width: `${quotaPercent}%` }}
                />
              </div>
              <div className="text-[10px] text-slate-500 font-mono text-right">
                {remainingQuota} kuota entry tersisa
              </div>
            </div>
          </div>

          {/* Card 3: Total Dana Ter-Entry */}
          <div className="p-4 rounded-xl bg-obsidian-900 border border-obsidian-750 shadow-md space-y-1.5">
            <div className="text-[11px] font-mono text-slate-400 flex items-center justify-between">
              <span>TOTAL DANA TER-ENTRY</span>
              <span className="text-emerald-400 font-bold">{state?.mode || mode}</span>
            </div>
            <div className="text-lg font-black text-emerald-400 font-mono">
              {formatIdr(state?.total_spent_idr || 0)}
            </div>
            <div className="text-xs font-mono text-slate-400">
              ≈ {formatUsd(state?.total_spent_usd || 0)}
            </div>
          </div>

          {/* Card 4: Parameter Aktif */}
          <div className="p-4 rounded-xl bg-obsidian-900 border border-obsidian-750 shadow-md space-y-1.5 font-mono text-xs">
            <div className="text-[11px] text-slate-400 flex items-center justify-between">
              <span>ATURAN AKTIF</span>
              <span className="text-amber-400 font-bold">SLIP: {state?.slippage_pct || slippagePct}%</span>
            </div>
            <div className="flex items-center justify-between text-slate-200 pt-0.5">
              <span className="text-slate-400">Uang/Entry:</span>
              <span className="font-bold text-white">{formatIdr(state?.entry_amount_idr || entryAmountIdr)}</span>
            </div>
            <div className="flex items-center justify-between text-slate-200">
              <span className="text-slate-400">Min Shield:</span>
              <span className="font-bold text-emerald-400">{state?.min_safety_score ?? minSafetyScore}/100</span>
            </div>
          </div>
        </div>

        {/* MAIN CONFIGURATION & CONTROLS */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
          {/* LEFT: PARAMETER CONTROLS (7 Cols) */}
          <div className="lg:col-span-7 rounded-2xl bg-obsidian-900 border border-obsidian-750 p-5 shadow-lg space-y-5">
            <div className="flex items-center justify-between border-b border-obsidian-800 pb-3">
              <div>
                <h2 className="text-sm font-bold text-white flex items-center gap-2">
                  <LucideIcon name="sliders" className="w-4 h-4 text-cyan-400" />
                  <span>Pengaturan Parameter Auto Entry</span>
                </h2>
                <p className="text-xs text-slate-400 mt-0.5">
                  Tentukan jumlah uang, batas maksimal posisi, dan toleransi slippage sebelum memulai.
                </p>
              </div>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-obsidian-950 text-cyan-300 border border-obsidian-800 font-bold">
                SETUP MANDIRI
              </span>
            </div>

            {/* PARAMETER 1: UANG PER ENTRY */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
                  <LucideIcon name="banknote" className="w-3.5 h-3.5 text-emerald-400" />
                  <span>Uang yang akan di-entry per Transaksi (IDR &amp; USD)</span>
                </label>
                <span className="text-xs font-mono font-bold text-emerald-400">
                  {formatIdr(entryAmountIdr)}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  min={1000}
                  step={1000}
                  value={entryAmountIdr}
                  onChange={(e) => setEntryAmountIdr(Math.max(1000, Number(e.target.value)))}
                  className="w-full px-3.5 py-2 rounded-xl bg-obsidian-950 border border-obsidian-700 text-white font-mono text-sm focus:outline-none focus:border-cyan-400 font-bold"
                  placeholder="Nominal Rupiah per trade..."
                />
              </div>

              {/* QUICK CHIPS NOMINAL */}
              <div className="flex flex-wrap gap-1.5 pt-1">
                {[15000, 20000, 25000, 50000, 100000].map((nominal) => (
                  <button
                    key={nominal}
                    type="button"
                    onClick={() => setEntryAmountIdr(nominal)}
                    className={`px-2.5 py-1 rounded-lg text-xs font-mono transition ${
                      entryAmountIdr === nominal
                        ? 'bg-emerald-500 text-obsidian-950 font-bold shadow-sm'
                        : 'bg-obsidian-950 hover:bg-obsidian-800 text-slate-300 border border-obsidian-800'
                    }`}
                  >
                    {formatIdr(nominal)}
                  </button>
                ))}
                <button
                  type="button"
                  onClick={() => setEntryAmountIdr(18087)}
                  className={`px-2.5 py-1 rounded-lg text-xs font-mono transition ${
                    entryAmountIdr === 18087
                      ? 'bg-cyan-500 text-obsidian-950 font-bold'
                      : 'bg-obsidian-950 hover:bg-obsidian-800 text-cyan-300 border border-obsidian-800'
                  }`}
                  title="Tepat $1.00 USD"
                >
                  $1.00 USD
                </button>
              </div>
            </div>

            {/* PARAMETER 2: JUMLAH MAKSIMAL ENTRY */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
                  <LucideIcon name="layers" className="w-3.5 h-3.5 text-cyan-400" />
                  <span>Jumlah Maksimal Entry (Batas Posisi Terbuka)</span>
                </label>
                <span className="text-xs font-mono font-bold text-cyan-300">
                  Maks: {maxEntries} Posisi
                </span>
              </div>
              <input
                type="number"
                min={1}
                max={50}
                value={maxEntries}
                onChange={(e) => setMaxEntries(Math.max(1, Math.min(50, Number(e.target.value))))}
                className="w-full px-3.5 py-2 rounded-xl bg-obsidian-950 border border-obsidian-700 text-white font-mono text-sm focus:outline-none focus:border-cyan-400 font-bold"
                placeholder="Jumlah maksimal entry..."
              />

              {/* QUICK CHIPS MAX ENTRIES */}
              <div className="flex flex-wrap gap-1.5 pt-1">
                {[1, 3, 5, 10, 15].map((cnt) => (
                  <button
                    key={cnt}
                    type="button"
                    onClick={() => setMaxEntries(cnt)}
                    className={`px-3 py-1 rounded-lg text-xs font-mono transition ${
                      maxEntries === cnt
                        ? 'bg-cyan-500 text-obsidian-950 font-bold shadow-sm'
                        : 'bg-obsidian-950 hover:bg-obsidian-800 text-slate-300 border border-obsidian-800'
                    }`}
                  >
                    {cnt} Entry
                  </button>
                ))}
              </div>
              <p className="text-[11px] text-slate-400">
                Bot akan memindai dan melakukan entry secara bertahap. Ketika jumlah entry mencapai {maxEntries}, bot otomatis berhenti tanpa menambah posisi lagi.
              </p>
            </div>

            {/* PARAMETER 3: TOLERANSI SLIPPAGE */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
                  <LucideIcon name="sliders" className="w-3.5 h-3.5 text-amber-400" />
                  <span>Toleransi Slippage Eksekusi (%)</span>
                </label>
                <span className="text-xs font-mono font-bold text-amber-400">
                  {slippagePct}%
                </span>
              </div>

              {/* QUICK CHIPS SLIPPAGE */}
              <div className="grid grid-cols-4 gap-2">
                {[0.5, 1.0, 2.5, 5.0].map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => setSlippagePct(s)}
                    className={`py-2 px-3 rounded-xl text-xs font-mono font-bold transition text-center ${
                      slippagePct === s
                        ? 'bg-amber-400 text-obsidian-950 shadow-sm'
                        : 'bg-obsidian-950 hover:bg-obsidian-800 text-slate-300 border border-obsidian-800'
                    }`}
                  >
                    {s}%
                  </button>
                ))}
              </div>
              <p className="text-[11px] text-slate-400">
                Disarankan 1.0% untuk pool likuid Raydium. 2.5% - 5.0% untuk token yang bergerak sangat cepat.
              </p>
            </div>

            {/* PARAMETER 4: MIN SAFETY SCORE & SOURCE */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
              <div className="space-y-1.5">
                <label className="text-xs font-bold text-slate-200 flex items-center gap-1">
                  <LucideIcon name="shield-check" className="w-3.5 h-3.5 text-emerald-400" />
                  <span>Min Safety Score</span>
                </label>
                <select
                  value={minSafetyScore}
                  onChange={(e) => setMinSafetyScore(Number(e.target.value))}
                  className="w-full px-3 py-2 rounded-xl bg-obsidian-950 border border-obsidian-700 text-white font-mono text-xs focus:outline-none focus:border-cyan-400 font-bold"
                >
                  <option value={60}>Score ≥ 60 (Agresif / Memecoin Baru)</option>
                  <option value={70}>Score ≥ 70 (Seimbang / Direkomendasikan)</option>
                  <option value={82}>Score ≥ 82 (Ketat / Super Safe)</option>
                </select>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-bold text-slate-200 flex items-center gap-1">
                  <LucideIcon name="zap" className="w-3.5 h-3.5 text-cyan-400" />
                  <span>Target Radar Pasar</span>
                </label>
                <select
                  value={targetSource}
                  onChange={(e) => setTargetSource(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-obsidian-950 border border-obsidian-700 text-white font-mono text-xs focus:outline-none focus:border-cyan-400 font-bold"
                >
                  <option value="ALL_RADAR">Semua Radar (New + Final + Migrated)</option>
                  <option value="NEW_CREATIONS">Koin Baru Rilis (&lt; 3 Jam)</option>
                  <option value="MIGRATED">Pool Lulus Migrasi Raydium</option>
                  <option value="FINAL_STRETCH">Final Stretch (Bonding Curve &gt; 80%)</option>
                </select>
              </div>
            </div>

            {/* ACTION BUTTONS */}
            <div className="pt-3 border-t border-obsidian-800 flex flex-wrap items-center gap-2.5">
              {!isRunning ? (
                <button
                  type="button"
                  onClick={handleStart}
                  className="flex-1 py-3 px-4 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-obsidian-950 text-xs font-extrabold transition flex items-center justify-center gap-2 shadow-lg shadow-emerald-500/20"
                >
                  <LucideIcon name="zap" className="w-4 h-4" />
                  <span>JALANKAN AUTO ENTRY</span>
                </button>
              ) : (
                <button
                  type="button"
                  onClick={handleStop}
                  className="flex-1 py-3 px-4 rounded-xl bg-rose-500 hover:bg-rose-400 text-white text-xs font-extrabold transition flex items-center justify-center gap-2 shadow-lg shadow-rose-500/20"
                >
                  <LucideIcon name="octagon-alert" className="w-4 h-4" />
                  <span>HENTIKAN AUTO ENTRY</span>
                </button>
              )}

              <button
                type="button"
                onClick={handleTriggerScan}
                className="py-3 px-4 rounded-xl bg-obsidian-950 hover:bg-obsidian-800 text-cyan-300 border border-obsidian-700 text-xs font-bold transition flex items-center gap-1.5"
                title="Pindai 1 kali sekarang"
              >
                <LucideIcon name="refresh-cw" className="w-3.5 h-3.5" />
                <span>Scan Sekarang</span>
              </button>

              <button
                type="button"
                onClick={handleResetCounter}
                className="py-3 px-4 rounded-xl bg-obsidian-950 hover:bg-obsidian-800 text-amber-300 border border-obsidian-750 text-xs font-bold transition flex items-center gap-1.5"
                title="Mereset hitungan entry kembali ke 0"
              >
                <LucideIcon name="rotate-ccw" className="w-3.5 h-3.5" />
                <span>Reset Kuota</span>
              </button>
            </div>
          </div>

          {/* RIGHT: LIVE SCANNER RADAR & SCAN LOGS (5 Cols) */}
          <div className="lg:col-span-5 space-y-4">
            {/* CURRENT SCAN CANDIDATE CARD */}
            <div className="rounded-2xl bg-obsidian-900 border border-obsidian-750 p-4 sm:p-5 shadow-lg space-y-3">
              <div className="flex items-center justify-between border-b border-obsidian-800 pb-2.5">
                <span className="text-xs font-bold text-white flex items-center gap-1.5">
                  <LucideIcon name="radio" className="w-3.5 h-3.5 text-cyan-400 animate-pulse" />
                  <span>Radar Target Pemindaian Live</span>
                </span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-300 border border-cyan-500/30">
                  REAL-TIME
                </span>
              </div>

              {state?.current_scanning_candidate ? (
                <div className="space-y-2.5 p-3 rounded-xl bg-obsidian-950 border border-obsidian-800 font-mono text-xs">
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="font-extrabold text-white text-sm">
                        {state.current_scanning_candidate.symbol}
                      </div>
                      <div className="text-[11px] text-slate-400 font-sans">
                        {state.current_scanning_candidate.name}
                      </div>
                    </div>
                    <span className="px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 font-bold text-[10px]">
                      Shield {state.current_scanning_candidate.safety_score}/100
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-2 text-[11px] pt-1">
                    <div>
                      <span className="text-slate-500 block text-[9px]">LIKUIDITAS</span>
                      <span className="text-slate-200 font-bold">
                        ${(Number(state.current_scanning_candidate.liquidity || 0) / 1000).toFixed(1)}K
                      </span>
                    </div>
                    <div>
                      <span className="text-slate-500 block text-[9px]">HARGA TOKEN</span>
                      <span className="text-emerald-400 font-bold">
                        {formatUsd(state.current_scanning_candidate.price)}
                      </span>
                    </div>
                  </div>

                  {state.current_scanning_candidate.contract && (
                    <div className="pt-2 border-t border-obsidian-850 flex items-center justify-between">
                      <span className="text-[10px] text-slate-500 truncate max-w-[170px]" title={state.current_scanning_candidate.contract}>
                        CA: {state.current_scanning_candidate.contract.slice(0, 6)}...{state.current_scanning_candidate.contract.slice(-4)}
                      </span>
                      <button
                        type="button"
                        onClick={() => handleCopyText(state.current_scanning_candidate?.contract || '', 'scan-ca')}
                        className="text-[10px] px-2 py-0.5 rounded bg-obsidian-900 hover:bg-obsidian-850 text-cyan-300 border border-obsidian-750 flex items-center gap-1"
                        title="Salin Mint CA"
                      >
                        <LucideIcon name={copiedKey === 'scan-ca' ? 'check' : 'copy'} className="w-2.5 h-2.5" />
                        <span>{copiedKey === 'scan-ca' ? '✓' : 'Salin CA'}</span>
                      </button>
                    </div>
                  )}
                </div>
              ) : (
                <div className="p-6 text-center text-xs text-slate-500 font-mono bg-obsidian-950/50 rounded-xl border border-obsidian-850">
                  {isRunning ? 'Sedang memindai pool DEX...' : 'Bot sedang standby. Klik Jalankan Auto Entry.'}
                </div>
              )}
            </div>

            {/* SCANNING ACTIVITY LOGS */}
            <div className="rounded-2xl bg-obsidian-900 border border-obsidian-750 p-4 shadow-lg space-y-2.5">
              <div className="flex items-center justify-between border-b border-obsidian-800 pb-2">
                <span className="text-xs font-bold text-white flex items-center gap-1.5">
                  <LucideIcon name="terminal" className="w-3.5 h-3.5 text-slate-400" />
                  <span>Log Eksekusi &amp; Scanning</span>
                </span>
                <span className="text-[10px] font-mono text-slate-500">Live Stream</span>
              </div>

              <div className="space-y-1.5 max-h-64 overflow-y-auto pr-1 text-xs font-mono">
                {(state?.scan_logs || []).length === 0 ? (
                  <div className="p-4 text-center text-slate-500">Belum ada aktivitas tercatat.</div>
                ) : (
                  state?.scan_logs.slice(0, 15).map((log: any) => (
                    <div
                      key={log.id}
                      className="p-2 rounded-lg bg-obsidian-950 border border-obsidian-850/80 flex items-start gap-2 leading-relaxed"
                    >
                      <span className="text-[10px] text-slate-500 shrink-0">{log.time}</span>
                      <span
                        className={`text-[9px] px-1.5 py-0.2 rounded font-bold shrink-0 ${
                          log.badge === 'ENTRY'
                            ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                            : log.badge === 'QUOTA'
                            ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                            : 'bg-obsidian-850 text-cyan-300'
                        }`}
                      >
                        {log.badge}
                      </span>
                      <span className="text-[11px] text-slate-300 line-clamp-2">{log.message}</span>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>

        {/* FILLED ENTRIES TABLE */}
        <div className="rounded-2xl bg-obsidian-900 border border-obsidian-750 p-5 shadow-lg space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-obsidian-800 pb-3">
            <div>
              <h2 className="text-sm sm:text-base font-bold text-white flex items-center gap-2">
                <LucideIcon name="check" className="w-4 h-4 text-emerald-400" />
                <span>Daftar Posisi yang Berhasil Di-Entry ({state?.entries_history?.length || 0})</span>
              </h2>
              <p className="text-xs text-slate-400 mt-0.5">
                Riwayat token yang berhasil dibeli oleh bot Auto Entry sesuai kuota dan parameter yang ditentukan.
              </p>
            </div>
            <div className="text-xs font-mono text-slate-400">
              Total Terpakai: <span className="text-emerald-400 font-bold">{formatIdr(state?.total_spent_idr || 0)}</span>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-obsidian-950 text-slate-400 border-b border-obsidian-800 uppercase text-[10px]">
                <tr>
                  <th className="p-3">Waktu</th>
                  <th className="p-3">Token &amp; Nama</th>
                  <th className="p-3">Contract Address (CA) &amp; Wallet</th>
                  <th className="p-3">Harga Entry</th>
                  <th className="p-3">Nominal Terpakai</th>
                  <th className="p-3">Slippage</th>
                  <th className="p-3">Safety Score</th>
                  <th className="p-3 text-right">Aksi</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-obsidian-800/60">
                {(state?.entries_history || []).length === 0 ? (
                  <tr>
                    <td colSpan={8} className="p-8 text-center text-slate-500 font-sans">
                      Belum ada posisi yang di-entry. Jalankan bot Auto Entry di atas untuk memulai eksekusi otomatis.
                    </td>
                  </tr>
                ) : (
                  state?.entries_history.map((entry) => {
                    const isCaCopied = copiedKey === `entry-ca-${entry.id}`;
                    const isWalletCopied = copiedKey === `entry-w-${entry.id}`;
                    return (
                      <tr key={entry.id} className="hover:bg-obsidian-850/60 transition">
                        <td className="p-3 text-slate-400 text-[11px]">
                          {new Date(entry.timestamp).toLocaleTimeString('id-ID')}
                        </td>
                        <td className="p-3">
                          <div className="font-bold text-white text-sm">{entry.symbol}</div>
                          <div className="text-[10px] text-slate-400 font-sans line-clamp-1">{entry.name}</div>
                        </td>
                        <td className="p-3 space-y-1">
                          {/* 1-CLICK COPY CONTRACT (CA) */}
                          {entry.contract && (
                            <div className="flex items-center gap-1.5">
                              <span className="text-[10px] text-slate-400" title={entry.contract}>
                                CA: {entry.contract.slice(0, 6)}...{entry.contract.slice(-4)}
                              </span>
                              <button
                                type="button"
                                onClick={() => handleCopyText(entry.contract, `entry-ca-${entry.id}`)}
                                className="px-1.5 py-0.5 rounded bg-obsidian-950 hover:bg-obsidian-800 text-amber-300 border border-obsidian-800 text-[9px] font-bold flex items-center gap-0.5 transition"
                                title="Salin Mint Contract (CA)"
                              >
                                <LucideIcon name={isCaCopied ? 'check' : 'copy'} className="w-2.5 h-2.5" />
                                <span>{isCaCopied ? '✓' : 'CA'}</span>
                              </button>
                            </div>
                          )}

                          {/* 1-CLICK COPY WALLET */}
                          {entry.wallet_address && (
                            <div className="flex items-center gap-1.5">
                              <span className="text-[10px] text-slate-500" title={entry.wallet_address}>
                                W: {entry.wallet_address.slice(0, 6)}...{entry.wallet_address.slice(-4)}
                              </span>
                              <button
                                type="button"
                                onClick={() => handleCopyText(entry.wallet_address || '', `entry-w-${entry.id}`)}
                                className="px-1.5 py-0.5 rounded bg-obsidian-950 hover:bg-obsidian-800 text-cyan-300 border border-obsidian-800 text-[9px] font-bold flex items-center gap-0.5 transition"
                                title="Salin Alamat Dompet Trading"
                              >
                                <LucideIcon name={isWalletCopied ? 'check' : 'copy'} className="w-2.5 h-2.5" />
                                <span>{isWalletCopied ? '✓' : 'Wallet'}</span>
                              </button>
                            </div>
                          )}
                        </td>
                        <td className="p-3">
                          <div className="text-white font-bold">{formatUsd(entry.entry_price)}</div>
                          <div className="text-[10px] text-slate-500 font-sans">
                            Qty: {Number(entry.quantity).toLocaleString()}
                          </div>
                        </td>
                        <td className="p-3">
                          <div className="text-emerald-400 font-bold">{formatIdr(entry.amount_idr)}</div>
                          <div className="text-[10px] text-slate-400">{formatUsd(entry.amount_usd)}</div>
                        </td>
                        <td className="p-3">
                          <span className="px-2 py-0.5 rounded bg-amber-500/15 text-amber-300 border border-amber-500/30 text-[10px] font-bold">
                            {entry.slippage_pct}%
                          </span>
                        </td>
                        <td className="p-3">
                          <span className="px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 text-[10px] font-bold">
                            {entry.safety_score}/100
                          </span>
                        </td>
                        <td className="p-3 text-right">
                          {entry.contract ? (
                            <a
                              href={`https://dexscreener.com/solana/${entry.contract}`}
                              target="_blank"
                              rel="noreferrer"
                              className="px-2.5 py-1 rounded-lg bg-cyan-500/15 hover:bg-cyan-500 text-cyan-300 hover:text-obsidian-950 text-[11px] font-bold transition inline-flex items-center gap-1"
                            >
                              <span>DEX</span>
                              <LucideIcon name="external-link" className="w-3 h-3" />
                            </a>
                          ) : (
                            <span className="text-slate-500 text-[11px]">-</span>
                          )}
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </>
  );
}
