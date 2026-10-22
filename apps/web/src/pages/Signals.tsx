import React, { useState } from 'react';
import Head from 'next/head';
import { api, useApiQuery } from '@/lib/api';
import { QueryState } from '@/components/QueryState';
import { LucideIcon } from '@/components/LucideIcon';

export default function SignalsPage() {
  const [activeTab, setActiveTab] = useState<'telegram' | 'algorithmic'>('telegram');
  const [searchTarget, setSearchTarget] = useState<string>('SOL');
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  const internalSignalsQuery = useApiQuery(() => api.getSignals(), []);
  const telegramSignalsQuery = useApiQuery(() => api.getTelegramSignals(), []);
  const telegramBotsQuery = useApiQuery(() => api.getTelegramBots(), []);
  const botQueryLinks = useApiQuery(
    () => api.getTelegramQueryLinks(searchTarget || 'SOL'),
    [searchTarget]
  );

  const handleCopyCommand = (text: string, key: string) => {
    if (typeof navigator !== 'undefined' && navigator.clipboard) {
      navigator.clipboard.writeText(text);
      setCopiedKey(key);
      setTimeout(() => setCopiedKey(null), 2500);
    }
  };

  const tgSignals = telegramSignalsQuery.data?.signals || [];
  const tgBots = telegramBotsQuery.data?.bots || [];
  const quickLinks = botQueryLinks.data?.query_links || [];

  return (
    <>
      <Head>
        <title>Alpha Signals &amp; Telegram Bot Radar | Sofia Market 3.9</title>
      </Head>

      <div className="space-y-5 pb-10">
        {/* TOP HERO BANNER */}
        <div className="bg-gradient-to-r from-obsidian-900 via-obsidian-900 to-obsidian-850 border border-obsidian-750 rounded-2xl p-5 sm:p-6 shadow-xl flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1.5">
            <div className="flex flex-wrap items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-pulse" />
              <h1 className="text-xl sm:text-2xl font-black text-slate-100 tracking-tight flex items-center gap-2.5">
                <LucideIcon name="radio" className="w-6 h-6 text-cyan-400" />
                Alpha Signals &amp; Radar Bot Telegram
              </h1>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-cyan-500/15 text-cyan-300 border border-cyan-500/30">
                SOFIA 3.9
              </span>
            </div>
            <p className="text-xs sm:text-sm text-slate-400 max-w-2xl leading-relaxed">
              Agregasi sinyal kuantitatif internal dan integrasi bot Telegram publik terverifikasi (RickBurp, DexScreener, GMGN Trench, EtherDrops, Saham IDX) untuk audit kontrak instan dan pelacakan smart money.
            </p>
          </div>

          {/* TAB SWITCHER */}
          <div className="flex items-center bg-obsidian-950 p-1 rounded-xl border border-obsidian-700/80 shrink-0">
            <button
              type="button"
              onClick={() => setActiveTab('telegram')}
              className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-bold transition ${
                activeTab === 'telegram'
                  ? 'bg-cyan-500 text-obsidian-950 shadow-sm'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              <LucideIcon name="send" className="w-3.5 h-3.5" />
              <span>Bot Telegram Publik ({tgBots.length})</span>
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('algorithmic')}
              className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-bold transition ${
                activeTab === 'algorithmic'
                  ? 'bg-cyan-500 text-obsidian-950 shadow-sm'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              <LucideIcon name="cpu" className="w-3.5 h-3.5" />
              <span>Sinyal Algoritma Internal</span>
            </button>
          </div>
        </div>

        {activeTab === 'telegram' ? (
          <div className="space-y-6">
            {/* 1-CLICK BOT QUERY LAUNCHER */}
            <div className="p-4 sm:p-5 rounded-2xl bg-obsidian-900 border border-obsidian-750 shadow-lg space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="space-y-0.5">
                  <h2 className="text-sm font-bold text-white flex items-center gap-2">
                    <LucideIcon name="zap" className="w-4 h-4 text-amber-400" />
                    <span>1-Click Generator Perintah Bot Telegram</span>
                  </h2>
                  <p className="text-xs text-slate-400">
                    Ketik simbol koin (contoh: BONK, SOL, BBRI) atau paste Contract Address (CA) Solana di bawah untuk langsung membuka bot publik dengan perintah siap kirim.
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    value={searchTarget}
                    onChange={(e) => setSearchTarget(e.target.value)}
                    placeholder="Ketik Simbol / Mint CA..."
                    className="px-3 py-1.5 rounded-lg bg-obsidian-950 border border-obsidian-700 text-white font-mono text-xs w-48 sm:w-64 focus:outline-none focus:border-cyan-400 font-bold"
                  />
                  <button
                    type="button"
                    onClick={() => botQueryLinks.refetch()}
                    className="px-3 py-1.5 rounded-lg bg-obsidian-850 hover:bg-obsidian-800 text-cyan-300 border border-obsidian-700 text-xs font-bold"
                  >
                    Generate
                  </button>
                </div>
              </div>

              {/* QUICK LINKS GRID */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {quickLinks.map((q: any) => {
                  const isCopied = copiedKey === q.bot_id;
                  return (
                    <div
                      key={q.bot_id}
                      className="p-3.5 rounded-xl bg-obsidian-950 border border-obsidian-800 hover:border-obsidian-700 transition space-y-2 flex flex-col justify-between"
                    >
                      <div>
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-extrabold text-xs text-white truncate">{q.bot_name}</span>
                          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-cyan-500/10 text-cyan-300 border border-cyan-500/30">
                            {q.badge}
                          </span>
                        </div>
                        <p className="text-[11px] text-slate-400 mt-1 line-clamp-2">{q.description}</p>
                      </div>

                      <div className="pt-2 border-t border-obsidian-850 space-y-2">
                        <div className="flex items-center justify-between text-[11px] font-mono bg-obsidian-900 px-2 py-1 rounded border border-obsidian-800">
                          <span className="text-emerald-300 font-bold truncate">{q.command}</span>
                          <button
                            type="button"
                            onClick={() => handleCopyCommand(q.command, q.bot_id)}
                            className="text-[10px] text-slate-400 hover:text-white shrink-0 ml-2 font-sans"
                            title="Salin Perintah"
                          >
                            {isCopied ? '✓ Disalin' : '📋 Salin'}
                          </button>
                        </div>

                        <a
                          href={q.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="w-full flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg bg-cyan-500/20 hover:bg-cyan-500 text-cyan-300 hover:text-obsidian-950 border border-cyan-500/40 text-xs font-extrabold transition"
                        >
                          <LucideIcon name="external-link" className="w-3.5 h-3.5" />
                          <span>Buka Bot Telegram</span>
                        </a>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* LIVE COMMUNITY TELEGRAM RADAR SIGNALS */}
            <div className="p-4 sm:p-5 rounded-2xl bg-obsidian-900 border border-obsidian-750 shadow-lg space-y-3.5">
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <h2 className="text-sm font-bold text-white flex items-center gap-2">
                    <LucideIcon name="activity" className="w-4 h-4 text-emerald-400" />
                    <span>Radar Alpha Komunitas Telegram Publik (Live Feed)</span>
                  </h2>
                  <p className="text-xs text-slate-400">
                    Sinyal terkurasi dari radar Telegram publik (Solana Trench, DexScreener Trending, Rick Burp Scanner, Whale Alert).
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => telegramSignalsQuery.refetch()}
                  className="px-2.5 py-1 rounded-lg bg-obsidian-950 border border-obsidian-700 text-slate-300 hover:text-white text-xs font-mono"
                >
                  🔄 Refresh Radar
                </button>
              </div>

              <div className="space-y-2.5">
                {tgSignals.map((sig: any) => (
                  <div
                    key={sig.id}
                    className="p-3.5 rounded-xl bg-obsidian-950 border border-obsidian-800/80 hover:border-obsidian-700 flex flex-col md:flex-row md:items-center justify-between gap-3 transition"
                  >
                    <div className="space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-extrabold text-sm text-white">{sig.ticker}</span>
                        <span className="text-xs text-slate-400 font-medium">({sig.name})</span>
                        <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
                          {sig.direction}
                        </span>
                        <span className="text-[10px] font-mono text-slate-500">
                          • {sig.source}
                        </span>
                      </div>
                      <p className="text-xs text-slate-300 leading-relaxed font-sans">{sig.message}</p>
                      <div className="text-[11px] text-cyan-300 font-semibold pt-0.5">
                        💡 Rekomendasi: {sig.suggested_action}
                      </div>
                    </div>

                    <div className="flex items-center md:flex-col md:items-end justify-between gap-1 shrink-0 font-mono text-xs">
                      <div className="flex items-center gap-1.5">
                        <span className="text-slate-500 text-[10px]">Safety:</span>
                        <span className="font-bold text-emerald-400">{sig.safety_score}/100</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <span className="text-slate-500 text-[10px]">Confidence:</span>
                        <span className="font-bold text-cyan-300">{sig.confidence_pct}%</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* DIRECTORY OF VERIFIED PUBLIC TELEGRAM BOTS */}
            <div className="p-4 sm:p-5 rounded-2xl bg-obsidian-900 border border-obsidian-750 shadow-lg space-y-3.5">
              <h2 className="text-sm font-bold text-white flex items-center gap-2">
                <LucideIcon name="book" className="w-4 h-4 text-purple-400" />
                <span>Katalog Bot Analisa Publik Terverifikasi (100% Gratis &amp; Terbuka)</span>
              </h2>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5">
                {tgBots.map((bot: any) => (
                  <div
                    key={bot.id}
                    className="p-4 rounded-xl bg-obsidian-950 border border-obsidian-800 space-y-2.5 flex flex-col justify-between"
                  >
                    <div>
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-bold text-sm text-white">{bot.name}</span>
                        <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-purple-500/15 text-purple-300 border border-purple-500/30">
                          {bot.handle}
                        </span>
                      </div>
                      <div className="text-[11px] font-bold text-emerald-400 mt-0.5">{bot.tag}</div>
                      <p className="text-xs text-slate-400 mt-1.5 leading-relaxed">{bot.description}</p>
                      
                      <div className="mt-2.5 flex flex-wrap gap-1">
                        {(bot.features || []).map((f: string, i: number) => (
                          <span
                            key={i}
                            className="text-[9px] px-1.5 py-0.5 rounded bg-obsidian-900 text-slate-400 border border-obsidian-800 font-mono"
                          >
                            ✓ {f}
                          </span>
                        ))}
                      </div>
                    </div>

                    <div className="pt-2.5 border-t border-obsidian-850 flex items-center justify-between">
                      <span className="text-[11px] font-mono text-slate-400">
                        Cmd: <code className="text-cyan-300 font-bold">{bot.primary_command}</code>
                      </span>
                      <a
                        href={bot.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="px-3 py-1 rounded-lg bg-obsidian-850 hover:bg-cyan-500 hover:text-obsidian-950 text-cyan-300 text-xs font-bold transition flex items-center gap-1"
                      >
                        <span>Mulai Chat</span>
                        <LucideIcon name="external-link" className="w-3 h-3" />
                      </a>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        ) : (
          /* ALGORITHMIC INTERNAL SIGNALS TABLE */
          <QueryState isLoading={internalSignalsQuery.isLoading} isError={internalSignalsQuery.isError} error={internalSignalsQuery.error}>
            <div className="rounded-xl bg-obsidian-900 border border-obsidian-750 overflow-hidden shadow-lg">
              <table className="w-full text-left text-xs font-mono">
                <thead className="bg-obsidian-950 text-slate-400 border-b border-obsidian-800 uppercase text-[10px]">
                  <tr>
                    <th className="p-3.5">Symbol</th>
                    <th className="p-3.5">Arah (Direction)</th>
                    <th className="p-3.5">Confidence</th>
                    <th className="p-3.5">Timeframe</th>
                    <th className="p-3.5">Sumber Analisa</th>
                    <th className="p-3.5">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-obsidian-800/60">
                  {(internalSignalsQuery.data?.signals || []).length === 0 ? (
                    <tr>
                      <td colSpan={6} className="p-6 text-center text-slate-500 font-sans">
                        Belum ada sinyal internal aktif saat ini.
                      </td>
                    </tr>
                  ) : (
                    internalSignalsQuery.data.signals.map((s: any) => (
                      <tr key={s.id} className="hover:bg-obsidian-850/60">
                        <td className="p-3.5 font-bold text-white">${s.symbol}</td>
                        <td className="p-3.5 uppercase font-bold text-cyan-400">{s.direction}</td>
                        <td className="p-3.5">{(s.confidence * 100).toFixed(0)}%</td>
                        <td className="p-3.5 text-slate-400">{s.timeframe}</td>
                        <td className="p-3.5 text-slate-300">{s.source}</td>
                        <td className="p-3.5">
                          <span className="px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 text-[10px] font-bold">
                            {s.status}
                          </span>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </QueryState>
        )}
      </div>
    </>
  );
}
