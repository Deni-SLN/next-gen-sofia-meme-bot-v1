import React, { useEffect, useState } from 'react';
import { api, getStrategyMode } from '@/lib/api';
import { LucideIcon } from '@/components/LucideIcon';

const PIPELINE_STEPS = [
  {
    idx: 1,
    code: 'SCAN',
    title: '1. Scan DEX Pools',
    desc: 'Mencari likuiditas & pair baru di DexScreener & GMGN',
    idleBadge: 'SELESAI',
  },
  {
    idx: 2,
    code: 'AUDIT',
    title: '2. Rug & Bundle Shield',
    desc: 'Audit kontrak, LP lock & konsentrasi holder',
    idleBadge: 'ACTIVE',
  },
  {
    idx: 3,
    code: 'SIGNAL',
    title: '3. AI Orderflow Scoring',
    desc: 'Analisis buy/sell pressure & bonding curve',
    idleBadge: 'READY',
  },
  {
    idx: 4,
    code: 'MONITOR',
    title: '4. Auto Snipe & Monitor',
    desc: 'Eksekusi beli & pantau TP/SL otomatis',
    idleBadge: 'STANDBY',
  },
];

const BADGE_MAP: Record<string, { label: string; style: string; tokenColor: string }> = {
  SCAN: {
    label: 'SCAN',
    style: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20',
    tokenColor: 'text-emerald-400 font-semibold',
  },
  AUDIT: {
    label: 'SAFETY',
    style: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    tokenColor: 'text-slate-200 font-semibold',
  },
  SIGNAL: {
    label: 'SIGNAL',
    style: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
    tokenColor: 'text-amber-300 font-semibold',
  },
  MONITOR: {
    label: 'MONITOR',
    style: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
    tokenColor: 'text-cyan-300 font-semibold',
  },
  SNIPE: {
    label: 'SNIPE',
    style: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
    tokenColor: 'text-emerald-400 font-bold',
  },
  SYSTEM: {
    label: 'SYSTEM',
    style: 'bg-obsidian-800 text-slate-400 border-obsidian-700',
    tokenColor: 'text-slate-200 font-semibold',
  },
};

export function BotActivityCard({
  botStatus,
  onTargetChange,
}: {
  botStatus?: string;
  onTargetChange?: (target: string) => void;
}) {
  const [activity, setActivity] = useState<any>(null);
  const [loadingTick, setLoadingTick] = useState<boolean>(false);

  const fetchTick = async (doTick: boolean = true, forceTrade: boolean = false) => {
    try {
      setLoadingTick(true);
      const res = await api.getBotActivity(doTick, forceTrade);
      setActivity(res);
      if (res?.current_stage?.target_token && onTargetChange) {
        onTargetChange(res.current_stage.target_token);
      }
      if (res?.trade_executed && typeof window !== 'undefined') {
        window.dispatchEvent(
          new CustomEvent('sofia-bot-trade-executed', { detail: res.trade_action })
        );
      }
    } catch {
      // ignore transient network errors
    } finally {
      setLoadingTick(false);
    }
  };

  useEffect(() => {
    fetchTick(false, false);
  }, [botStatus]);

  useEffect(() => {
    const isRunning = (botStatus || activity?.status || 'running') === 'running';
    if (!isRunning) return;
    const intervalMs = Number(activity?.sniper_config?.tick_interval_ms || 3000);
    const timer = setInterval(() => {
      // Read live state from the 24/7 server daemon without blocking browser HTTP connections
      fetchTick(false, false);
    }, Math.max(2000, intervalMs));
    return () => clearInterval(timer);
  }, [botStatus, activity?.status, activity?.sniper_config?.tick_interval_ms]);

  const isRunning = (botStatus || activity?.status || 'running') === 'running';
  const stage = activity?.current_stage || {};
  const activeIdx = isRunning ? stage.stage_index || 2 : 0;
  const logs: any[] = activity?.logs || [];
  const activeStrat = activity?.strategy_mode || activity?.sniper_config?.strategy_mode || getStrategyMode();

  return (
    <section
      className="bg-obsidian-900 border border-obsidian-700/70 rounded-xl p-4 space-y-3.5"
      data-purpose="sniper-execution-stream"
    >
      {/* Header & Steps Bar */}
      <div className="flex flex-col xl:flex-row xl:items-center justify-between gap-3 pb-3 border-b border-obsidian-800">
        <div className="flex flex-wrap items-center gap-2.5">
          <LucideIcon name="terminal" className="w-4 h-4 text-emerald-400" />
          <h2 className="text-sm font-semibold text-white tracking-tight">
            Aktivitas Mesin Auto-Sniper
          </h2>
          <span
            className={`text-[10px] px-2 py-0.5 rounded-md font-mono font-medium border ${
              activeStrat === 'AGGRESSIVE'
                ? 'bg-amber-500/10 text-amber-400 border-amber-500/25'
                : activeStrat === 'SAFE'
                ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/25'
                : 'bg-cyan-500/10 text-cyan-400 border-cyan-500/25'
            }`}
          >
            {activeStrat === 'AGGRESSIVE'
              ? 'Mode Agresif • Koin Baru 1.2s'
              : activeStrat === 'SAFE'
              ? 'Mode Safe • Token Lulus'
              : 'Mode Default'}
          </span>
          <span className="text-[11px] text-slate-400 truncate max-w-md">
            {stage.detail || 'Memeriksa kontrak & likuiditas token secara berkala'}
          </span>
        </div>
        <div className="flex items-center gap-2 text-xs">
          {isRunning && (
            <button
              type="button"
              onClick={() => fetchTick(true, true)}
              disabled={loadingTick}
              className="px-2.5 py-1 rounded-lg bg-emerald-500/15 hover:bg-emerald-500/25 text-emerald-300 border border-emerald-500/30 text-[11px] font-medium transition"
              title="Langsung eksekusi Auto-Snipe / TP-SL pada tahap 4 sekarang"
            >
              Eksekusi Sekarang
            </button>
          )}
          <button
            type="button"
            onClick={() => fetchTick(true, false)}
            disabled={loadingTick}
            className="px-2.5 py-1 rounded-lg bg-obsidian-850 hover:bg-obsidian-800 text-slate-300 border border-obsidian-700 text-[11px] transition"
          >
            {loadingTick ? 'Memindai...' : 'Step Scan'}
          </button>
          <span
            className={
              isRunning
                ? 'px-2.5 py-1 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-[11px] font-medium'
                : 'px-2.5 py-1 rounded-lg bg-obsidian-850 text-slate-400 border border-obsidian-700 text-[11px] font-medium'
            }
            title={
              isRunning
                ? 'Bot berjalan 24/7 di server. Menutup browser atau logout tidak akan menghentikan bot; bot hanya berhenti jika tombol Hentikan Bot ditekan.'
                : 'Bot sedang berhenti / standby.'
            }
          >
            {isRunning ? 'Online • 24/7 Daemon' : 'Standby'}
          </span>
        </div>
      </div>

      {/* 4-Step Pipeline Status Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5" data-purpose="pipeline-indicator-cards">
        {PIPELINE_STEPS.map((step) => {
          const isCurrent = isRunning && activeIdx === step.idx;
          const isPassed = isRunning && activeIdx > step.idx;
          const badgeText = isCurrent
            ? 'ACTIVE'
            : isPassed
            ? 'DONE'
            : step.idx === 3
            ? 'READY'
            : 'STANDBY';

          return (
            <div
              key={step.idx}
              className={
                isCurrent
                  ? 'p-3 rounded-xl bg-obsidian-850 border border-emerald-500/40 text-xs relative transition'
                  : 'p-3 rounded-xl bg-obsidian-950/60 border border-obsidian-800 text-xs transition'
              }
            >
              <div className="flex items-center justify-between mb-1">
                <span
                  className={
                    isCurrent
                      ? 'font-semibold text-white flex items-center gap-1.5'
                      : 'font-medium text-slate-300'
                  }
                >
                  {isCurrent && <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>}
                  {step.title}
                </span>
                <span
                  className={
                    isCurrent
                      ? 'text-[9px] font-mono px-1.5 py-0.2 rounded bg-emerald-500/15 text-emerald-400 border border-emerald-500/25'
                      : 'text-[9px] font-mono px-1.5 py-0.2 rounded bg-obsidian-850 text-slate-500'
                  }
                >
                  {badgeText}
                </span>
              </div>
              <p className="text-[11px] text-slate-400 leading-snug">
                {step.desc}
              </p>
            </div>
          );
        })}
      </div>

      {/* Terminal Console Execution Log Box */}
      <div
        className="bg-obsidian-950 rounded-xl border border-obsidian-800 p-3 font-mono text-[11px] space-y-1.5 max-h-36 overflow-y-auto"
        data-purpose="terminal-feed-box"
      >
        <div className="flex items-center justify-between text-[10px] text-slate-500 border-b border-obsidian-850 pb-1.5 font-sans font-medium">
          <span>Log Eksekusi Real-Time (DexScreener &amp; GMGN.ai)</span>
          <span className="font-mono">{logs.length} aktivitas</span>
        </div>

        {logs.length === 0 ? (
          <div className="py-3 text-center text-slate-500 text-[11px] font-sans">
            Menunggu aktivitas bot. Klik <strong>Step Scan</strong> atau <strong>Jalankan Bot</strong>.
          </div>
        ) : (
          logs.map((log) => {
            const cfg = BADGE_MAP[log.badge] || BADGE_MAP.SCAN;
            const symDisplay = log.token?.startsWith('$') ? log.token : `$${log.token}`;
            return (
              <div
                key={log.id}
                className="flex items-start justify-between gap-2 text-slate-300 leading-relaxed hover:bg-obsidian-900/60 px-1 py-0.5 rounded transition"
              >
                <div className="flex items-start gap-2 min-w-0">
                  <span className="text-slate-500 select-none shrink-0">{log.time}</span>
                  <span className={`px-1.5 py-0.2 rounded border text-[9px] shrink-0 ${cfg.style}`}>
                    {cfg.label}
                  </span>
                  <span className="text-slate-300 truncate">
                    <span className={cfg.tokenColor}>{symDisplay}</span> {log.message}
                  </span>
                </div>
                {log.detail_idr && (
                  <span className="text-[10px] text-emerald-400 font-medium shrink-0 hidden sm:inline">
                    {log.detail_idr}
                  </span>
                )}
              </div>
            );
          })
        )}
      </div>
    </section>
  );
}
