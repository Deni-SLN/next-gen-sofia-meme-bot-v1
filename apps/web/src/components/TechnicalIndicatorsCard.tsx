import React, { useState } from 'react';
import { LucideIcon } from '@/components/LucideIcon';

interface TechnicalIndicatorsCardProps {
  technicalAudit: any;
  symbol: string;
  currency?: string;
  onSelectIndicator?: (id: 'ALL' | 'SNR' | 'SMC' | 'EMA200' | 'ICHIMOKU' | 'FIBONACCI') => void;
  focusedIndicator?: string;
}

export function TechnicalIndicatorsCard({
  technicalAudit,
  symbol,
  currency = 'IDR',
  onSelectIndicator,
  focusedIndicator = 'ALL',
}: TechnicalIndicatorsCardProps) {
  const [activeTab, setActiveTab] = useState<'all' | 'SNR' | 'SMC' | 'EMA200' | 'ICHIMOKU' | 'FIBONACCI'>('all');

  if (!technicalAudit || !technicalAudit.indicators) {
    return null;
  }

  const isUsd = currency.toUpperCase() === 'USD' || symbol.includes('USDT');

  const formatPrice = (val: number | undefined | null) => {
    if (val === undefined || val === null || isNaN(val)) return '-';
    if (isUsd) {
      if (Math.abs(val) >= 100) return '$' + val.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
      if (Math.abs(val) >= 1) return '$' + val.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 4 });
      return '$' + val.toLocaleString('en-US', { minimumFractionDigits: 4, maximumFractionDigits: 6 });
    }
    return 'Rp ' + Math.round(val).toLocaleString('id-ID');
  };

  const indicators = technicalAudit.indicators;
  const snr = indicators.SNR;
  const smc = indicators.SMC;
  const ema = indicators.EMA200;
  const ichimoku = indicators.ICHIMOKU;
  const fibo = indicators.FIBONACCI;

  const getBiasBadge = (bias: string) => {
    const b = (bias || '').toUpperCase();
    if (b === 'BULLISH') {
      return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40';
    }
    if (b === 'BEARISH') {
      return 'bg-rose-500/20 text-rose-400 border-rose-500/40';
    }
    return 'bg-amber-500/20 text-amber-300 border-amber-500/40';
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'READY':
        return 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30';
      case 'WARMING_UP':
        return 'bg-amber-500/15 text-amber-300 border-amber-500/30';
      case 'NO_SIGNAL':
        return 'bg-slate-800 text-slate-300 border-slate-700';
      default:
        return 'bg-slate-800 text-slate-400 border-slate-700';
    }
  };

  const items = [
    { id: 'SNR', data: snr, icon: 'shield', label: '1. Support & Resistance (SNR)' },
    { id: 'SMC', data: smc, icon: 'layers', label: '2. Smart Money Concepts (SMC)' },
    { id: 'EMA200', data: ema, icon: 'trending-up', label: '3. Trend Filter EMA 200' },
    { id: 'ICHIMOKU', data: ichimoku, icon: 'cloud', label: '4. Ichimoku Cloud (Kumo)' },
    { id: 'FIBONACCI', data: fibo, icon: 'git-commit', label: '5. Fibonacci Retracement' },
  ];

  const visibleItems = activeTab === 'all' ? items : items.filter((it) => it.id === activeTab);

  return (
    <div className="bg-obsidian-900/90 border border-obsidian-800 rounded-2xl p-5 sm:p-6 shadow-xl space-y-5">
      {/* Header & Synthesis Decision */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 pb-4 border-b border-obsidian-800">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-pulse" />
            <h3 className="text-base sm:text-lg font-black text-white tracking-tight flex items-center gap-2">
              <LucideIcon name="check-circle" className="w-5 h-5 text-cyan-400" />
              Audit &amp; Sintesis 5 Indikator Analisis Teknikal
            </h3>
          </div>
          <p className="text-xs text-slate-400">
            Perhitungan objektif multi-indikator tanpa look-ahead bias untuk <strong>{symbol}</strong> ({technicalAudit.timeframe?.toUpperCase()}).
          </p>
        </div>

        {/* Global Technical Decision Badge */}
        <div className="flex items-center gap-3">
          <div className="text-right">
            <div className="text-[10px] font-mono uppercase text-slate-400">Skor Konsensus</div>
            <div className="text-xl font-black font-mono text-cyan-400">
              {technicalAudit.overall_score_0_100}<span className="text-xs text-slate-500">/100</span>
            </div>
          </div>
          <div
            className={`px-3.5 py-2 rounded-xl border font-mono font-extrabold text-xs sm:text-sm text-center shadow-lg ${
              technicalAudit.decision === 'BUY'
                ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/50 shadow-emerald-500/10'
                : technicalAudit.decision === 'SELL'
                ? 'bg-rose-500/20 text-rose-300 border-rose-500/50 shadow-rose-500/10'
                : 'bg-amber-500/20 text-amber-300 border-amber-500/50 shadow-amber-500/10'
            }`}
          >
            {technicalAudit.decision_label}
          </div>
        </div>
      </div>

      {/* Decision Summary Text Box */}
      <div className="p-3.5 rounded-xl bg-obsidian-950 border border-obsidian-800 flex items-start gap-3">
        <span className="text-cyan-400 font-bold text-base mt-0.5">💡</span>
        <div className="text-xs font-mono text-slate-300 space-y-1">
          <p className="font-semibold text-slate-200">{technicalAudit.decision_desc}</p>
          <div className="flex flex-wrap items-center gap-4 text-[11px] text-slate-400 pt-1">
            <span>
              Suara Indikator:{' '}
              <strong className="text-emerald-400">Bullish: {technicalAudit.votes?.bullish}</strong> •{' '}
              <strong className="text-rose-400">Bearish: {technicalAudit.votes?.bearish}</strong> •{' '}
              <strong className="text-amber-400">Netral: {technicalAudit.votes?.neutral}</strong>
            </span>
            {technicalAudit.wait_target_price && (
              <span>
                Target Tunggu Pantulan:{' '}
                <strong className="text-amber-300 font-bold">
                  {formatPrice(technicalAudit.wait_target_price)}
                </strong>
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Tabs Filter */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1 no-scrollbar text-xs font-mono">
        <button
          type="button"
          onClick={() => setActiveTab('all')}
          className={`px-3 py-1.5 rounded-xl border transition whitespace-nowrap ${
            activeTab === 'all'
              ? 'bg-cyan-500/20 border-cyan-500/50 text-cyan-300 font-bold'
              : 'bg-obsidian-950 border-obsidian-800 text-slate-400 hover:text-white'
          }`}
        >
          Semua Indikator (5)
        </button>
        {items.map((it) => (
          <button
            key={it.id}
            type="button"
            onClick={() => setActiveTab(it.id as any)}
            className={`px-3 py-1.5 rounded-xl border transition whitespace-nowrap ${
              activeTab === it.id
                ? 'bg-cyan-500/20 border-cyan-500/50 text-cyan-300 font-bold'
                : 'bg-obsidian-950 border-obsidian-800 text-slate-400 hover:text-white'
            }`}
          >
            {it.id}
          </button>
        ))}
      </div>

      {/* 5 Indicators Details Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {visibleItems.map(({ id, data, icon, label }) => {
          if (!data) return null;
          const sig = data.signals || {};
          const vals = data.values || {};
          const isWarming = data.status === 'WARMING_UP';

          const isFocused = focusedIndicator === id;

          return (
            <div
              key={id}
              className={`rounded-xl p-4 flex flex-col justify-between space-y-3 transition duration-200 ${
                isFocused
                  ? 'bg-obsidian-900 border-2 border-cyan-400 shadow-glow-cyan'
                  : 'bg-obsidian-950/70 border border-obsidian-800 hover:border-obsidian-700'
              }`}
            >
              {/* Header Card */}
              <div>
                <div className="flex items-center justify-between gap-2 mb-2">
                  <span className="text-xs font-bold text-slate-200 flex items-center gap-1.5 font-mono">
                    <LucideIcon name={icon as any} className="w-4 h-4 text-cyan-400" />
                    {label}
                  </span>
                  <div className="flex items-center gap-1.5">
                    {onSelectIndicator && (
                      <button
                        type="button"
                        onClick={() => {
                          onSelectIndicator(id as any);
                          const chartEl = document.getElementById('chart-container-root');
                          if (chartEl) chartEl.scrollIntoView({ behavior: 'smooth' });
                        }}
                        className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold border transition ${
                          isFocused
                            ? 'bg-cyan-500 text-obsidian-950 border-cyan-400'
                            : 'bg-obsidian-900 text-cyan-300 border-cyan-500/30 hover:bg-cyan-500/20'
                        }`}
                        title={`Sorot ${id} secara jelas di dalam chart`}
                      >
                        👁️ {isFocused ? 'Aktif di Chart' : 'Sorot di Chart'}
                      </button>
                    )}
                    <span className={`px-2 py-0.5 rounded text-[10px] font-mono border font-bold ${getStatusBadge(data.status)}`}>
                      {data.status}
                    </span>
                  </div>
                </div>

                {/* Sub status pill */}
                <div className="flex items-center justify-between text-[11px] font-mono py-1 border-b border-obsidian-800/80">
                  <span className="text-slate-400">{data.display_status}</span>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-extrabold border ${getBiasBadge(sig.bias)}`}>
                    {sig.bias || 'NEUTRAL'}
                  </span>
                </div>

                {/* Signal Summary */}
                <p className="text-xs text-slate-300 mt-2.5 leading-relaxed font-sans">
                  {sig.summary}
                </p>
              </div>

              {/* Specific Details per Indicator */}
              <div className="pt-2 border-t border-obsidian-800/80 text-[11px] font-mono space-y-1 text-slate-400">
                {id === 'SNR' && (
                  <>
                    <div className="flex justify-between">
                      <span>Support Terdekat:</span>
                      <strong className="text-emerald-400">{formatPrice(vals.nearest_support)}</strong>
                    </div>
                    <div className="flex justify-between">
                      <span>Resistensi Terdekat:</span>
                      <strong className="text-rose-400">{formatPrice(vals.nearest_resistance)}</strong>
                    </div>
                    <div className="flex justify-between">
                      <span>Kekuatan Reaksi:</span>
                      <span className="text-slate-200">{vals.support_strength || 'Moderat'}</span>
                    </div>
                  </>
                )}

                {id === 'SMC' && (
                  <>
                    <div className="flex justify-between">
                      <span>Struktur Swing:</span>
                      <strong className="text-cyan-400">{vals.market_structure || 'Netral'}</strong>
                    </div>
                    <div className="flex justify-between">
                      <span>Dealing Range:</span>
                      <span className="text-slate-200">{vals.dealing_zone || 'Equilibrium'}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Order Block Aktif:</span>
                      <span className="text-emerald-400 font-bold">
                        {data.levels?.order_blocks?.length || 0} Terpetakan
                      </span>
                    </div>
                  </>
                )}

                {id === 'EMA200' && (
                  <>
                    <div className="flex justify-between">
                      <span>Nilai EMA 200:</span>
                      <strong className="text-amber-400">{formatPrice(vals.ema_200)}</strong>
                    </div>
                    <div className="flex justify-between">
                      <span>Jarak dari Harga:</span>
                      <span className={vals.distance_pct >= 0 ? 'text-emerald-400' : 'text-rose-400'}>
                        {vals.distance_pct >= 0 ? '+' : ''}{vals.distance_pct}%
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span>Arah Major Trend:</span>
                      <span className="text-slate-200">{vals.trend_alignment}</span>
                    </div>
                  </>
                )}

                {id === 'ICHIMOKU' && (
                  <>
                    <div className="flex justify-between">
                      <span>Tenkan / Kijun:</span>
                      <span className="text-cyan-300">
                        {formatPrice(vals.tenkan_sen)} / {formatPrice(vals.kijun_sen)}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span>Awan Kumo (Rentang):</span>
                      <span className="text-purple-300">
                        {formatPrice(vals.kumo_lower)} – {formatPrice(vals.kumo_upper)}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span>Posisi Kumo:</span>
                      <span className="text-emerald-400 font-bold">{vals.cloud_position}</span>
                    </div>
                  </>
                )}

                {id === 'FIBONACCI' && (
                  <>
                    <div className="flex justify-between">
                      <span>Impuls Dominan:</span>
                      <span className="text-cyan-300">{vals.impulse_direction}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Golden Pocket 50-61.8%:</span>
                      <strong className="text-amber-300">
                        {formatPrice(data.levels?.fib_500)} – {formatPrice(data.levels?.fib_618)}
                      </strong>
                    </div>
                    <div className="flex justify-between">
                      <span>Ekstensi 161.8%:</span>
                      <span className="text-slate-200">{formatPrice(data.levels?.fib_1618)}</span>
                    </div>
                  </>
                )}

                {isWarming && data.warnings?.[0] && (
                  <div className="p-2 rounded bg-amber-500/10 text-amber-300 text-[10px] mt-1">
                    ⚠️ {data.warnings[0]}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
