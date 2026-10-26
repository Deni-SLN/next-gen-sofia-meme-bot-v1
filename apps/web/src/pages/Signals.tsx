import React, { useState } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { api, useApiQuery, formatIdr, formatUsd, StockInsightItem, CryptoInsightItem } from '@/lib/api';
import { QueryState } from '@/components/QueryState';
import { LucideIcon } from '@/components/LucideIcon';

type TabType = 'stocks' | 'crypto' | 'telegram' | 'algorithmic';

export default function SignalsPage() {
  const [activeTab, setActiveTab] = useState<TabType>('stocks');
  const [searchTarget, setSearchTarget] = useState<string>('SOL');
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [radarFilter, setRadarFilter] = useState<'ALL' | 'MEME' | 'CRYPTO_STOCKS'>('ALL');
  const [isRefreshingInsights, setIsRefreshingInsights] = useState<boolean>(false);

  const insightsQuery = useApiQuery(() => api.getSignalInsights(), []);
  const internalSignalsQuery = useApiQuery(() => api.getSignals(), []);
  const telegramSignalsQuery = useApiQuery(() => api.getTelegramSignals(), []);
  const telegramBotsQuery = useApiQuery(() => api.getTelegramBots(), []);
  const botQueryLinks = useApiQuery(
    () => api.getTelegramQueryLinks(searchTarget || 'SOL'),
    [searchTarget]
  );

  const handleManualRefreshInsights = async () => {
    setIsRefreshingInsights(true);
    try {
      await api.getSignalInsights(true);
      await insightsQuery.refetch();
    } catch {
      // ignore
    } finally {
      setIsRefreshingInsights(false);
    }
  };

  const handleCopyCommand = (text: string, key: string) => {
    if (typeof navigator !== 'undefined' && navigator.clipboard) {
      navigator.clipboard.writeText(text);
      setCopiedKey(key);
      setTimeout(() => setCopiedKey(null), 2500);
    }
  };

  const stockInsights: StockInsightItem[] = insightsQuery.data?.stocks || [];
  const cryptoInsights: CryptoInsightItem[] = insightsQuery.data?.crypto || [];
  const tgSignals = telegramSignalsQuery.data?.signals || [];
  const tgBots = telegramBotsQuery.data?.bots || [];
  const quickLinks = botQueryLinks.data?.query_links || [];

  return (
    <>
      <Head>
        <title>Alpha Signals &amp; Market Insights | Sofia Market 3.9</title>
      </Head>

      <div className="space-y-5 pb-10">
        {/* TOP HERO BANNER */}
        <div className="bg-gradient-to-r from-obsidian-900 via-obsidian-900 to-obsidian-850 border border-obsidian-750 rounded-2xl p-5 sm:p-6 shadow-xl flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1.5">
            <div className="flex flex-wrap items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-pulse" />
              <h1 className="text-xl sm:text-2xl font-black text-slate-100 tracking-tight flex items-center gap-2.5">
                <LucideIcon name="radio" className="w-6 h-6 text-cyan-400" />
                Alpha Signals &amp; Market Insights
              </h1>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-cyan-500/15 text-cyan-300 border border-cyan-500/30">
                SOFIA 3.9
              </span>
            </div>
            <p className="text-xs sm:text-sm text-slate-400 max-w-2xl leading-relaxed">
              Pusat inteligensi pasar terintegrasi: 5 Saham IDX &amp; 5 Crypto Terkurasi dengan trading plan presisi, radar komunitas bot Telegram publik, dan sinyal algoritma kuantitatif otonom.
            </p>
          </div>

          {/* TAB SWITCHER */}
          <div className="flex flex-wrap items-center bg-obsidian-950 p-1.5 rounded-xl border border-obsidian-700/80 gap-1 shrink-0">
            <button
              type="button"
              onClick={() => setActiveTab('stocks')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition ${
                activeTab === 'stocks'
                  ? 'bg-emerald-500 text-obsidian-950 shadow-sm font-extrabold'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              <LucideIcon name="trending-up" className="w-3.5 h-3.5" />
              <span>Insight Saham (5)</span>
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('crypto')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition ${
                activeTab === 'crypto'
                  ? 'bg-cyan-500 text-obsidian-950 shadow-sm font-extrabold'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              <LucideIcon name="coins" className="w-3.5 h-3.5" />
              <span>Insight Crypto (5)</span>
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('telegram')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition ${
                activeTab === 'telegram'
                  ? 'bg-purple-500 text-obsidian-950 shadow-sm font-extrabold'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              <LucideIcon name="send" className="w-3.5 h-3.5" />
              <span>Bot Telegram</span>
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('algorithmic')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition ${
                activeTab === 'algorithmic'
                  ? 'bg-amber-400 text-obsidian-950 shadow-sm font-extrabold'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              <LucideIcon name="zap" className="w-3.5 h-3.5" />
              <span>Sinyal Algoritma</span>
            </button>
          </div>
        </div>

        {/* TAB 1: INSIGHT SAHAM IDX (5 SAHAM TERKURASI) */}
        {activeTab === 'stocks' && (
          <div className="space-y-4">
            <div className="p-4 rounded-xl bg-obsidian-900 border border-obsidian-750 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-md">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
                    IDX TOP 5 WATCHLIST
                  </span>
                  <h2 className="text-sm sm:text-base font-bold text-white flex items-center gap-1.5">
                    <LucideIcon name="trending-up" className="w-4 h-4 text-emerald-400" />
                    <span>5 Saham Terkurasi BEI: Fundamental Prima &amp; Peluang Akumulasi</span>
                  </h2>
                </div>
                <p className="text-xs text-slate-400">
                  Daftar saham dengan likuiditas tinggi, neraca kas prima, margin aman, dan setup teknikal terukur (Risk/Reward &gt;= 1:2.0).
                </p>
              </div>

              <div className="flex items-center gap-2 shrink-0">
                <button
                  type="button"
                  onClick={handleManualRefreshInsights}
                  disabled={isRefreshingInsights || insightsQuery.isLoading}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-obsidian-950 hover:bg-obsidian-850 border border-obsidian-700 text-emerald-300 hover:text-white text-xs font-bold transition disabled:opacity-50"
                >
                  <LucideIcon
                    name="refresh-cw"
                    className={`w-3.5 h-3.5 ${isRefreshingInsights || insightsQuery.isLoading ? 'animate-spin' : ''}`}
                  />
                  <span>Perbarui Live Quote</span>
                </button>
              </div>
            </div>

            <QueryState isLoading={insightsQuery.isLoading} isError={insightsQuery.isError} error={insightsQuery.error}>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {stockInsights.map((stock) => {
                  const isUp = stock.change_pct >= 0;
                  return (
                    <div
                      key={stock.ticker}
                      className="rounded-2xl bg-obsidian-900 border border-obsidian-750 hover:border-emerald-500/40 p-4 sm:p-5 flex flex-col justify-between transition-all duration-200 shadow-lg space-y-4"
                    >
                      {/* Top Header */}
                      <div className="space-y-2">
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="text-lg font-black text-white tracking-tight">{stock.ticker}</span>
                              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-obsidian-950 text-slate-300 border border-obsidian-800">
                                {stock.currency}
                              </span>
                            </div>
                            <div className="text-xs text-slate-300 font-medium line-clamp-1">{stock.name}</div>
                            <div className="text-[11px] text-slate-500">{stock.sector}</div>
                          </div>

                          <div className="flex flex-col items-end">
                            <span className="text-sm font-black text-white font-mono">
                              {formatIdr(stock.current_price)}
                            </span>
                            <span
                              className={`text-[10px] font-mono font-bold px-1.5 py-0.5 rounded ${
                                isUp
                                  ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                                  : 'bg-rose-500/15 text-rose-400 border border-rose-500/30'
                              }`}
                            >
                              {isUp ? `+${stock.change_pct}%` : `${stock.change_pct}%`}
                            </span>
                          </div>
                        </div>

                        {/* Badges & Safety Score */}
                        <div className="flex flex-wrap items-center justify-between gap-1.5 pt-1 border-t border-obsidian-800">
                          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 font-bold truncate max-w-[210px]">
                            {stock.quality_badge}
                          </span>
                          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-obsidian-950 text-cyan-300 border border-obsidian-800 font-bold">
                            Safety: {stock.safety_score}/100
                          </span>
                        </div>
                      </div>

                      {/* Action Verdict Callout */}
                      <div className="p-2.5 rounded-xl bg-obsidian-950 border border-obsidian-800 space-y-1">
                        <div className="flex items-center justify-between text-[11px]">
                          <span className="text-slate-400 font-medium">Rekomendasi Taktis:</span>
                          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 uppercase tracking-wide">
                            {stock.action}
                          </span>
                        </div>
                        <div className="text-[11px] text-slate-400 flex items-center justify-between font-mono">
                          <span>Area Beli (Entry):</span>
                          <span className="text-white font-bold">{stock.entry_zone}</span>
                        </div>
                      </div>

                      {/* Trading Plan Matrix */}
                      <div className="grid grid-cols-3 gap-2 p-2.5 rounded-xl bg-obsidian-950/70 border border-obsidian-800/80 text-center font-mono">
                        <div>
                          <div className="text-[9px] uppercase tracking-wider text-slate-500 font-sans">Target 1 (TP1)</div>
                          <div className="text-xs font-bold text-emerald-400">{formatIdr(stock.tp_1)}</div>
                          <div className="text-[10px] text-emerald-500 font-semibold">+{stock.tp_1_pct}%</div>
                        </div>
                        <div>
                          <div className="text-[9px] uppercase tracking-wider text-slate-500 font-sans">Target 2 (TP2)</div>
                          <div className="text-xs font-bold text-cyan-300">{formatIdr(stock.tp_2)}</div>
                          <div className="text-[10px] text-cyan-400 font-semibold">+{stock.tp_2_pct}%</div>
                        </div>
                        <div>
                          <div className="text-[9px] uppercase tracking-wider text-slate-500 font-sans">Stop Loss (SL)</div>
                          <div className="text-xs font-bold text-rose-400">{formatIdr(stock.stop_loss)}</div>
                          <div className="text-[10px] text-rose-500 font-semibold">-{stock.stop_loss_pct}%</div>
                        </div>
                      </div>

                      {/* Risk Reward & Technical Note */}
                      <div className="space-y-1.5 text-xs">
                        <div className="flex items-center justify-between text-[11px] font-mono text-slate-400">
                          <span>Rasio Risk / Reward:</span>
                          <span className="text-amber-400 font-bold">{stock.risk_reward}</span>
                        </div>
                        <div className="text-[11px] text-slate-400 bg-obsidian-950 p-2 rounded-lg border border-obsidian-850 leading-relaxed font-sans">
                          <span className="text-slate-300 font-semibold">💡 Katalis Fundamental: </span>
                          {stock.catalyst}
                        </div>
                        <div className="text-[10px] font-mono text-slate-400 flex items-center gap-1.5 pt-0.5">
                          <LucideIcon name="zap" className="w-3 h-3 text-cyan-400" />
                          <span>{stock.technical_summary}</span>
                        </div>
                      </div>

                      {/* CTA Direct Link */}
                      <div className="pt-2 border-t border-obsidian-800">
                        <Link
                          href={stock.detail_url}
                          className="w-full py-2 px-3 rounded-xl bg-emerald-500/15 hover:bg-emerald-500 text-emerald-300 hover:text-obsidian-950 border border-emerald-500/30 text-xs font-bold transition flex items-center justify-center gap-1.5 shadow-sm"
                        >
                          <span>Buka Analisa Lengkap {stock.ticker}</span>
                          <LucideIcon name="external-link" className="w-3.5 h-3.5" />
                        </Link>
                      </div>
                    </div>
                  );
                })}
              </div>
            </QueryState>
          </div>
        )}

        {/* TAB 2: INSIGHT CRYPTO GLOBAL (5 CRYPTO TERKURASI) */}
        {activeTab === 'crypto' && (
          <div className="space-y-4">
            <div className="p-4 rounded-xl bg-obsidian-900 border border-obsidian-750 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-md">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-cyan-500/15 text-cyan-300 border border-cyan-500/30">
                    GLOBAL TOP 5 CRYPTO
                  </span>
                  <h2 className="text-sm sm:text-base font-bold text-white flex items-center gap-1.5">
                    <LucideIcon name="coins" className="w-4 h-4 text-cyan-400" />
                    <span>5 Koin Crypto Terkurasi: Likuiditas Dalam, On-Chain Solid &amp; Setup Momentum</span>
                  </h2>
                </div>
                <p className="text-xs text-slate-400">
                  Aset crypto bluechip dan high-beta dengan aliran modal institusional, pertumbuhan ekosistem nyata, dan kalkulasi risiko presisi.
                </p>
              </div>

              <div className="flex items-center gap-2 shrink-0">
                <button
                  type="button"
                  onClick={handleManualRefreshInsights}
                  disabled={isRefreshingInsights || insightsQuery.isLoading}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-obsidian-950 hover:bg-obsidian-850 border border-obsidian-700 text-cyan-300 hover:text-white text-xs font-bold transition disabled:opacity-50"
                >
                  <LucideIcon
                    name="refresh-cw"
                    className={`w-3.5 h-3.5 ${isRefreshingInsights || insightsQuery.isLoading ? 'animate-spin' : ''}`}
                  />
                  <span>Perbarui Live Crypto</span>
                </button>
              </div>
            </div>

            <QueryState isLoading={insightsQuery.isLoading} isError={insightsQuery.isError} error={insightsQuery.error}>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {cryptoInsights.map((coin) => {
                  const isUp = coin.change_24h_pct >= 0;
                  return (
                    <div
                      key={coin.symbol}
                      className="rounded-2xl bg-obsidian-900 border border-obsidian-750 hover:border-cyan-500/40 p-4 sm:p-5 flex flex-col justify-between transition-all duration-200 shadow-lg space-y-4"
                    >
                      {/* Top Header */}
                      <div className="space-y-2">
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="text-lg font-black text-white tracking-tight">{coin.symbol}</span>
                              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-obsidian-950 text-slate-300 border border-obsidian-800">
                                USD &amp; IDR
                              </span>
                            </div>
                            <div className="text-xs text-slate-300 font-medium">{coin.name}</div>
                            <div className="text-[11px] text-slate-500">{coin.category}</div>
                          </div>

                          <div className="flex flex-col items-end">
                            <span className="text-sm font-black text-white font-mono">
                              {formatUsd(coin.current_price_usd)}
                            </span>
                            <span className="text-[10px] font-mono text-slate-400">
                              {formatIdr(coin.current_price_idr)}
                            </span>
                            <span
                              className={`text-[10px] font-mono font-bold px-1.5 py-0.5 rounded mt-0.5 ${
                                isUp
                                  ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                                  : 'bg-rose-500/15 text-rose-400 border border-rose-500/30'
                              }`}
                            >
                              {isUp ? `+${coin.change_24h_pct}%` : `${coin.change_24h_pct}%`}
                            </span>
                          </div>
                        </div>

                        {/* Badges & Safety Score */}
                        <div className="flex flex-wrap items-center justify-between gap-1.5 pt-1 border-t border-obsidian-800">
                          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-300 border border-cyan-500/20 font-bold truncate max-w-[210px]">
                            {coin.tier_badge}
                          </span>
                          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-obsidian-950 text-emerald-300 border border-obsidian-800 font-bold">
                            Safety: {coin.safety_score}/100
                          </span>
                        </div>
                      </div>

                      {/* Action Verdict Callout */}
                      <div className="p-2.5 rounded-xl bg-obsidian-950 border border-obsidian-800 space-y-1">
                        <div className="flex items-center justify-between text-[11px]">
                          <span className="text-slate-400 font-medium">Rekomendasi Taktis:</span>
                          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-cyan-500/15 text-cyan-300 border border-cyan-500/30 uppercase tracking-wide">
                            {coin.action}
                          </span>
                        </div>
                        <div className="text-[11px] text-slate-400 flex items-center justify-between font-mono">
                          <span>Area Beli (Entry):</span>
                          <span className="text-white font-bold">{coin.entry_zone_usd}</span>
                        </div>
                      </div>

                      {/* Trading Plan Matrix */}
                      <div className="grid grid-cols-3 gap-2 p-2.5 rounded-xl bg-obsidian-950/70 border border-obsidian-800/80 text-center font-mono">
                        <div>
                          <div className="text-[9px] uppercase tracking-wider text-slate-500 font-sans">Target 1 (TP1)</div>
                          <div className="text-xs font-bold text-emerald-400">{formatUsd(coin.tp_1_usd)}</div>
                          <div className="text-[10px] text-emerald-500 font-semibold">+{coin.tp_1_pct}%</div>
                        </div>
                        <div>
                          <div className="text-[9px] uppercase tracking-wider text-slate-500 font-sans">Target 2 (TP2)</div>
                          <div className="text-xs font-bold text-cyan-300">{formatUsd(coin.tp_2_usd)}</div>
                          <div className="text-[10px] text-cyan-400 font-semibold">+{coin.tp_2_pct}%</div>
                        </div>
                        <div>
                          <div className="text-[9px] uppercase tracking-wider text-slate-500 font-sans">Stop Loss (SL)</div>
                          <div className="text-xs font-bold text-rose-400">{formatUsd(coin.stop_loss_usd)}</div>
                          <div className="text-[10px] text-rose-500 font-semibold">-{coin.stop_loss_pct}%</div>
                        </div>
                      </div>

                      {/* Risk Reward & Catalyst Note */}
                      <div className="space-y-1.5 text-xs">
                        <div className="flex items-center justify-between text-[11px] font-mono text-slate-400">
                          <span>Rasio Risk / Reward:</span>
                          <span className="text-amber-400 font-bold">{coin.risk_reward}</span>
                        </div>
                        <div className="text-[11px] text-slate-400 bg-obsidian-950 p-2 rounded-lg border border-obsidian-850 leading-relaxed font-sans">
                          <span className="text-slate-300 font-semibold">⛓️ Katalis On-Chain: </span>
                          {coin.catalyst}
                        </div>
                        <div className="text-[10px] font-mono text-slate-400 flex items-center gap-1.5 pt-0.5">
                          <LucideIcon name="zap" className="w-3 h-3 text-cyan-400" />
                          <span>{coin.technical_summary}</span>
                        </div>
                      </div>

                      {/* CTA Direct Link */}
                      <div className="pt-2 border-t border-obsidian-800">
                        <Link
                          href={coin.detail_url}
                          className="w-full py-2 px-3 rounded-xl bg-cyan-500/15 hover:bg-cyan-500 text-cyan-300 hover:text-obsidian-950 border border-cyan-500/30 text-xs font-bold transition flex items-center justify-center gap-1.5 shadow-sm"
                        >
                          <span>Buka Analisa Lengkap {coin.symbol}</span>
                          <LucideIcon name="external-link" className="w-3.5 h-3.5" />
                        </Link>
                      </div>
                    </div>
                  );
                })}
              </div>
            </QueryState>
          </div>
        )}

        {/* TAB 3: BOT TELEGRAM PUBLIK */}
        {activeTab === 'telegram' && (
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
            <div className="p-4 sm:p-5 rounded-2xl bg-obsidian-900 border border-obsidian-750 shadow-lg space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="space-y-0.5">
                  <h2 className="text-sm font-bold text-white flex items-center gap-2">
                    <LucideIcon name="radio" className="w-4 h-4 text-emerald-400" />
                    <span>Radar Alpha Komunitas Telegram Publik (Live Feed)</span>
                  </h2>
                  <p className="text-xs text-slate-400">
                    Sinyal terkurasi dari radar Telegram publik (Solana Trench, DexScreener Trending, Rick Burp Scanner, Whale Alert). Dilengkapi fitur 1-klik salin CA dan Wallet Paus.
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => telegramSignalsQuery.refetch()}
                    className="px-2.5 py-1.5 rounded-lg bg-obsidian-950 border border-obsidian-700 text-slate-300 hover:text-white text-xs font-mono transition"
                  >
                    🔄 Refresh Radar
                  </button>
                </div>
              </div>

              {/* FILTER CHIPS (SEMUA / KHUSUS MEME COIN / CRYPTO & STOCKS) */}
              <div className="flex flex-wrap items-center gap-1.5 border-b border-obsidian-800 pb-3">
                <button
                  type="button"
                  onClick={() => setRadarFilter('ALL')}
                  className={`px-3 py-1 rounded-lg text-xs font-bold transition font-mono ${
                    radarFilter === 'ALL'
                      ? 'bg-emerald-500 text-obsidian-950 font-extrabold shadow-sm'
                      : 'bg-obsidian-950 text-slate-400 hover:text-white border border-obsidian-800'
                  }`}
                >
                  Semua Sinyal ({tgSignals.length})
                </button>
                <button
                  type="button"
                  onClick={() => setRadarFilter('MEME')}
                  className={`px-3 py-1 rounded-lg text-xs font-bold transition font-mono flex items-center gap-1.5 ${
                    radarFilter === 'MEME'
                      ? 'bg-amber-400 text-obsidian-950 font-extrabold shadow-sm'
                      : 'bg-obsidian-950 text-amber-300/80 hover:text-amber-200 border border-amber-500/20'
                  }`}
                >
                  <span>🐕 Khusus Meme Coin ({tgSignals.filter((s: any) => s.is_memecoin).length})</span>
                </button>
                <button
                  type="button"
                  onClick={() => setRadarFilter('CRYPTO_STOCKS')}
                  className={`px-3 py-1 rounded-lg text-xs font-bold transition font-mono ${
                    radarFilter === 'CRYPTO_STOCKS'
                      ? 'bg-cyan-500 text-obsidian-950 font-extrabold shadow-sm'
                      : 'bg-obsidian-950 text-slate-400 hover:text-white border border-obsidian-800'
                  }`}
                >
                  🏛️ Bluechip Crypto &amp; Saham ({tgSignals.filter((s: any) => !s.is_memecoin).length})
                </button>
              </div>

              <div className="space-y-3">
                {tgSignals
                  .filter((sig: any) => {
                    if (radarFilter === 'MEME') return sig.is_memecoin;
                    if (radarFilter === 'CRYPTO_STOCKS') return !sig.is_memecoin;
                    return true;
                  })
                  .map((sig: any) => {
                    const isCaCopied = copiedKey === `ca-${sig.id}`;
                    const isWalletCopied = copiedKey === `wallet-${sig.id}`;
                    return (
                      <div
                        key={sig.id}
                        className="p-4 rounded-xl bg-obsidian-950 border border-obsidian-800/80 hover:border-obsidian-700 transition shadow-sm space-y-3"
                      >
                        <div className="flex flex-col md:flex-row md:items-start justify-between gap-3">
                          <div className="space-y-1.5">
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="font-extrabold text-base text-white">{sig.ticker}</span>
                              <span className="text-xs text-slate-400 font-medium">({sig.name})</span>
                              {sig.is_memecoin && (
                                <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-amber-500/15 text-amber-300 border border-amber-500/30">
                                  🐕 MEME COIN
                                </span>
                              )}
                              <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
                                {sig.direction}
                              </span>
                              {sig.chain && (
                                <span className="px-1.5 py-0.5 rounded text-[9px] font-mono bg-obsidian-900 text-cyan-300 border border-obsidian-800">
                                  {sig.chain}
                                </span>
                              )}
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

                        {/* DEDICATED COPY CONTRACT (CA) & WALLET ADDRESS BAR */}
                        {(sig.contract_address || sig.wallet_address) && (
                          <div className="p-2.5 rounded-lg bg-obsidian-900 border border-obsidian-800 flex flex-wrap items-center justify-between gap-2.5 text-xs font-mono">
                            <div className="flex flex-wrap items-center gap-3">
                              {/* 1-CLICK COPY MINT CONTRACT (CA) */}
                              {sig.contract_address && (
                                <div className="flex items-center gap-1.5 bg-obsidian-950 px-2 py-1 rounded border border-obsidian-800">
                                  <span className="text-[10px] text-amber-400 font-bold uppercase tracking-wider">
                                    CA:
                                  </span>
                                  <span className="text-slate-300 text-[11px]" title={sig.contract_address}>
                                    {sig.contract_address.slice(0, 6)}...{sig.contract_address.slice(-4)}
                                  </span>
                                  <button
                                    type="button"
                                    onClick={() => handleCopyCommand(sig.contract_address, `ca-${sig.id}`)}
                                    className={`px-2 py-0.5 rounded text-[10px] font-bold transition flex items-center gap-1 ml-1 ${
                                      isCaCopied
                                        ? 'bg-emerald-500 text-obsidian-950 font-extrabold shadow-sm'
                                        : 'bg-obsidian-900 hover:bg-obsidian-850 text-amber-300 border border-obsidian-750'
                                    }`}
                                    title="Salin Mint Contract Address (CA)"
                                  >
                                    <LucideIcon name={isCaCopied ? 'check' : 'copy'} className="w-3 h-3" />
                                    <span>{isCaCopied ? '✓ CA Tersalin' : '📋 Salin CA'}</span>
                                  </button>
                                </div>
                              )}

                              {/* 1-CLICK COPY WHALE / SMART MONEY WALLET */}
                              {sig.wallet_address && (
                                <div className="flex items-center gap-1.5 bg-obsidian-950 px-2 py-1 rounded border border-obsidian-800">
                                  <span className="text-[10px] text-cyan-400 font-bold uppercase tracking-wider">
                                    {sig.wallet_label ? 'Whale Wallet:' : 'Wallet:'}
                                  </span>
                                  <span className="text-slate-300 text-[11px]" title={sig.wallet_address}>
                                    {sig.wallet_address.slice(0, 6)}...{sig.wallet_address.slice(-4)}
                                  </span>
                                  <button
                                    type="button"
                                    onClick={() => handleCopyCommand(sig.wallet_address, `wallet-${sig.id}`)}
                                    className={`px-2 py-0.5 rounded text-[10px] font-bold transition flex items-center gap-1 ml-1 ${
                                      isWalletCopied
                                        ? 'bg-emerald-500 text-obsidian-950 font-extrabold shadow-sm'
                                        : 'bg-obsidian-900 hover:bg-obsidian-850 text-cyan-300 border border-obsidian-750'
                                    }`}
                                    title="Salin Alamat Dompet Whale / Smart Money"
                                  >
                                    <LucideIcon name={isWalletCopied ? 'check' : 'copy'} className="w-3 h-3" />
                                    <span>{isWalletCopied ? '✓ Wallet Tersalin' : '📋 Salin Wallet'}</span>
                                  </button>
                                </div>
                              )}
                            </div>

                            {/* AUDIT SHORTCUT */}
                            <div className="flex items-center gap-2">
                              {sig.contract_address && (
                                <button
                                  type="button"
                                  onClick={() => {
                                    setSearchTarget(sig.contract_address);
                                    botQueryLinks.refetch();
                                    if (typeof window !== 'undefined') {
                                      window.scrollTo({ top: 180, behavior: 'smooth' });
                                    }
                                  }}
                                  className="text-[10px] px-2.5 py-1 rounded bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 flex items-center gap-1 font-bold transition"
                                  title="Isi alamat CA ke Generator Bot Telegram di atas"
                                >
                                  <LucideIcon name="zap" className="w-3 h-3" />
                                  <span>Audit di Bot</span>
                                </button>
                              )}
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
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
        )}

        {/* TAB 4: ALGORITHMIC INTERNAL SIGNALS TABLE */}
        {activeTab === 'algorithmic' && (
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
