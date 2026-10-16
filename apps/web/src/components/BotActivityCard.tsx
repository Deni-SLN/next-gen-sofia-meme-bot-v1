import React, { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { LucideIcon } from '@/components/LucideIcon';

const PIPELINE_STEPS = [
  {
    idx: 1,
    code: 'SCAN',
    title: '1. Scan DEX Pools',
    desc: 'Mencari likuiditas & pair baru di DexScreener',
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
    desc: 'Analisis buy/sell pressure bot & bonding curve',
    idleBadge: 'READY',
  },
  {
    idx: 4,
    code: 'MONITOR',
    title: '4. Auto Snipe & Monitor',
    desc: 'Eksekusi beli MEV & pantau TP/SL otomatis',
    idleBadge: 'STANDBY',
  },
];

const BADGE_MAP: Record<string, { label: string; style: string; tokenColor: string }> = {
  SCAN: {
    label: 'SCAN',
    style: 'bg-cyan-900/50 text-cyan-300 border-cyan-700/50',
    tokenColor: 'text-emerald-400 font-bold',
  },
  AUDIT: {
    label: 'SAFETY',
    style: 'bg-emerald-900/50 text-emerald-300 border-emerald-700/50',
    tokenColor: 'text-pink-400 font-semibold',
  },
  SIGNAL: {
    label: 'ANALYSIS',
    style: 'bg-purple-900/50 text-purple-300 border-purple-700/50',
    tokenColor: 'text-yellow-300 font-semibold',
  },
  MONITOR: {
    label: 'MONITOR',
    style: 'bg-blue-900/50 text-blue-300 border-blue-700/50',
    tokenColor: 'text-cyan-300 font-semibold',
  },
  SNIPE: {
    label: 'SNIPE',
    style: 'bg-emerald-900/60 text-emerald-300 border-emerald-600/60',
    tokenColor: 'text-emerald-400 font-bold',
  },
  SYSTEM: {
    label: 'SYSTEM',
    style: 'bg-slate-800 text-slate-300 border-slate-700',
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
    fetchTick(true, false);
  }, [botStatus]);

  useEffect(() => {
    const isRunning = (botStatus || activity?.status || 'running') === 'running';
    if (!isRunning) return;
    const timer = setInterval(() => {
      fetchTick(true, false);
    }, 3000);
    return () => clearInterval(timer);
  }, [botStatus, activity?.status]);

  const isRunning = (botStatus || activity?.status || 'running') === 'running';
  const stage = activity?.current_stage || {};
  const activeIdx = isRunning ? stage.stage_index || 2 : 0;
  const logs: any[] = activity?.logs || [];

  return (
    <section
      className="bg-obsidian-900 border border-obsidian-700/80 rounded-xl p-3.5 space-y-3"
      data-purpose="sniper-execution-stream"
    >
      {/* Header & Steps Bar */}
      <div className="flex flex-col xl:flex-row xl:items-center justify-between gap-3 pb-2 border-b border-obsidian-800">
        <div className="flex flex-wrap items-center gap-2">
          <LucideIcon name="terminal" className="w-4 h-4 text-emerald-400" />
          <h2 className="text-xs font-bold text-slate-100 uppercase tracking-wide">
            Live Sniper Bot Activity Stream
          </h2>
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 font-mono">
            {stage.detail ||
              'Memeriksa kontrak: WIF/METH • Mint/Freeze Revoked, LP Lock & Konsentrasi Top 10 Holder (27.5%)'}
          </span>
        </div>
        <div className="flex items-center gap-2 text-xs font-mono">
          {isRunning && (
            <button
              type="button"
              onClick={() => fetchTick(true, true)}
              disabled={loadingTick}
              className="px-2.5 py-0.5 rounded bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 border border-emerald-500/40 text-[10px] font-bold transition"
              title="Langsung eksekusi Auto-Snipe / TP-SL pada tahap 4 sekarang"
            >
              ⚡ Eksekusi Auto-Trade Sekarang
            </button>
          )}
          <button
            type="button"
            onClick={() => fetchTick(true, false)}
            disabled={loadingTick}
            className="px-2 py-0.5 rounded bg-obsidian-850 hover:bg-obsidian-800 text-cyan-300 border border-obsidian-700 text-[10px] transition"
          >
            {loadingTick ? 'Scanning...' : '⚡ Step Scan'}
          </button>
          <span className="text-slate-400 text-[11px]">Pipeline Status:</span>
          <span
            className={
              isRunning
                ? 'px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/25 text-[10px] font-bold'
                : 'px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700 text-[10px] font-bold'
            }
          >
            {isRunning ? 'ONLINE • AUTO-TRADE AKTIF' : 'PAUSED / STANDBY'}
          </span>
        </div>
      </div>

      {/* 4-Step Pipeline Status Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2" data-purpose="pipeline-indicator-cards">
        {PIPELINE_STEPS.map((step) => {
          const isCurrent = isRunning && activeIdx === step.idx;
          const isPassed = isRunning && activeIdx > step.idx;
          const badgeText = isCurrent
            ? 'ACTIVE'
            : isPassed
            ? 'SELESAI'
            : step.idx === 3
            ? 'READY'
            : 'STANDBY';

          return (
            <div
              key={step.idx}
              className={
                isCurrent
                  ? 'p-2.5 rounded-lg bg-emerald-950/30 border border-emerald-500/60 shadow-glow-emerald text-xs relative transition'
                  : 'p-2.5 rounded-lg bg-obsidian-850/80 border border-obsidian-700 text-xs transition'
              }
            >
              <div className="flex items-center justify-between mb-1">
                <span
                  className={
                    isCurrent
                      ? 'font-bold text-emerald-300 flex items-center gap-1.5'
                      : isPassed
                      ? 'font-bold text-slate-200'
                      : 'font-bold text-slate-300'
                  }
                >
                  {isCurrent && <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping"></span>}
                  {step.title}
                </span>
                <span
                  className={
                    isCurrent
                      ? 'text-[9px] font-mono px-1 rounded bg-emerald-500/20 text-emerald-300 font-bold'
                      : isPassed
                      ? 'text-[9px] font-mono px-1 rounded bg-slate-800 text-slate-300'
                      : 'text-[9px] font-mono px-1 rounded bg-slate-800 text-slate-400'
                  }
                >
                  {badgeText}
                </span>
              </div>
              <p
                className={
                  isCurrent
                    ? 'text-[10px] text-emerald-200/80 leading-tight'
                    : 'text-[10px] text-slate-400 leading-tight'
                }
              >
                {step.desc}
              </p>
            </div>
          );
        })}
      </div>

      {/* Terminal Console Execution Log Box */}
      <div
        className="bg-obsidian-950 rounded-lg border border-obsidian-800 p-2.5 font-mono text-[11px] space-y-1.5 max-h-36 overflow-y-auto"
        data-purpose="terminal-feed-box"
      >
        <div className="flex items-center justify-between text-[9px] text-slate-400 border-b border-obsidian-850 pb-1 uppercase font-bold">
          <span>● REAL-TIME EXECUTION LOG STREAM (DEXSCREENER + BLOCKCHAIR)</span>
          <span>{logs.length} events recorded</span>
        </div>

        {logs.length === 0 ? (
          <div className="py-3 text-center text-slate-500 text-[11px]">
            Menunggu stream aktivitas bot... Klik <strong>Step Scan</strong> atau <strong>JALANKAN BOT</strong>.
          </div>
        ) : (
          logs.map((log) => {
            const cfg = BADGE_MAP[log.badge] || BADGE_MAP.SCAN;
            const symDisplay = log.token?.startsWith('$') ? log.token : `$${log.token}`;
            return (
              <div
                key={log.id}
                className="flex items-start justify-between gap-2 text-slate-300 leading-relaxed hover:bg-obsidian-900/60 p-0.5 rounded transition"
              >
                <div className="flex items-start gap-2 min-w-0">
                  <span className="text-slate-400 select-none shrink-0">{log.time}</span>
                  <span className={`px-1 py-0.2 rounded border text-[9px] shrink-0 ${cfg.style}`}>
                    {cfg.label}
                  </span>
                  <span className="text-slate-200 truncate">
                    <span className={cfg.tokenColor}>{symDisplay}</span> {log.message}
                  </span>
                </div>
                {log.detail_idr && (
                  <span className="text-[10px] text-emerald-400 font-semibold shrink-0 hidden sm:inline">
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
