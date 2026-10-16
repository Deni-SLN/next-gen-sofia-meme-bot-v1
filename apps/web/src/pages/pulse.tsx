import React, { useState, useEffect } from 'react';
import { api, useApiQuery, formatIdr, formatUsd, getTradingMode } from '@/lib/api';
import { QueryState } from '@/components/QueryState';

export default function PulsePage() {
  const pulseQuery = useApiQuery(() => api.getPulse(), []);
  const [presetIdr, setPresetIdr] = useState<number>(30000);
  const [mode, setMode] = useState<'PAPER' | 'LIVE'>('PAPER');
  const [snipeFeedback, setSnipeFeedback] = useState<string>('');
  const [snipeError, setSnipeError] = useState<string>('');
  const [minSafety, setMinSafety] = useState<number>(0);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      setMode(getTradingMode());
      const saved = localStorage.getItem('sofia_quickbuy_idr');
      if (saved) setPresetIdr(Number(saved));
      const handler = (e: any) => setPresetIdr(Number(e.detail));
      const modeHandler = (e: any) => setMode(e.detail);
      window.addEventListener('sofia-preset-idr-change', handler);
      window.addEventListener('sofia-mode-change', modeHandler);
      return () => {
        window.removeEventListener('sofia-preset-idr-change', handler);
        window.removeEventListener('sofia-mode-change', modeHandler);
      };
    }
  }, []);

  const usdIdr = pulseQuery.data?.fx?.usd_idr || 16500;

  const handleQuickSnipe = async (token: any) => {
    setSnipeFeedback('');
    setSnipeError('');
    try {
      const res = await api.snipeToken({
        symbol: token.base_symbol || token.symbol,
        amount_idr: presetIdr,
        price: token.price,
        slippage_pct: 15,
        priority_fee_sol: 0.005,
        anti_mev: true,
        mode: mode,
      });
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('sofia-bot-trade-executed', { detail: res }));
      }
      setSnipeFeedback(
        res.mode === 'LIVE'
          ? `⚡ [LIVE ON-CHAIN] Berhasil beli ${res.quantity.toLocaleString()} ${res.symbol} @ ${formatUsd(
              res.entry_price
            )} (${formatIdr(res.entry_price_idr)}) senilai ${formatIdr(res.amount_idr)} (${formatUsd(
              res.amount_usd
            )}) • Tx: ${String(res.tx_hash || '').slice(0, 16)}... • Sisa Kas Live: ${formatIdr(res.live_cash_remaining_idr)}`
          : `⚡ [PAPER SIMULASI] Berhasil beli ${res.quantity.toLocaleString()} ${res.symbol} pada harga market asli ${formatUsd(
              res.entry_price
            )} (${formatIdr(res.entry_price_idr)}) senilai ${formatIdr(res.amount_idr)} (${formatUsd(
              res.amount_usd
            )}). Sisa Kas Paper: ${formatIdr(res.paper_cash_remaining_idr)}.`
      );
    } catch (err: any) {
      setSnipeError(err?.message || 'Gagal melakukan snipe');
    }
  };

  const renderColumn = (title: string, subtitle: string, badgeColor: string, tokens: any[]) => {
    const filtered = (tokens || []).filter((t) => t.safety_score >= minSafety);
    return (
      <div className="bg-[#0b0f17] border border-slate-800/90 rounded-2xl flex flex-col overflow-hidden">
        <div className="p-4 border-b border-slate-800 flex items-center justify-between bg-slate-900/50">
          <div>
            <div className="font-bold text-sm text-slate-100 flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${badgeColor}`} />
              {title}
            </div>
            <div className="text-[11px] text-slate-400 mt-0.5">{subtitle}</div>
          </div>
          <span className="px-2 py-0.5 rounded-md bg-slate-800 text-xs font-mono text-slate-300">
            {filtered.length}
          </span>
        </div>

        <div className="p-3 space-y-3 divide-y divide-slate-800/40">
          {filtered.map((t) => {
            const isSafe = t.safety_score >= 75;
            return (
              <div
                key={t.contract || t.symbol}
                className="pt-3 first:pt-0 rounded-xl p-3 bg-slate-900/60 hover:bg-slate-900 border border-slate-800/80 transition space-y-2.5"
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-extrabold text-slate-100">{t.symbol}</span>
                      <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-sky-300">
                        {t.launchpad}
                      </span>
                      <span className="text-[10px] font-mono text-emerald-400">{t.age}</span>
                    </div>
                    <div className="text-xs text-slate-400">{t.name}</div>
                    <div className="text-xs font-mono font-bold text-slate-100 mt-1">
                      {formatUsd(t.price)}{' '}
                      <span className="text-[11px] font-normal text-emerald-400">
                        (≈ {formatIdr(t.price * usdIdr)})
                      </span>
                    </div>
                  </div>

                  <button
                    onClick={() => handleQuickSnipe(t)}
                    className="px-3 py-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-mono font-bold text-xs transition shadow-sm shadow-emerald-500/20 shrink-0 text-right"
                  >
                    <div>⚡ Snipe {formatIdr(presetIdr)}</div>
                    <div className="text-[9px] opacity-80">({formatUsd(presetIdr / usdIdr)})</div>
                  </button>
                </div>

                {/* Bonding Curve Progress Bar */}
                <div>
                  <div className="flex justify-between text-[11px] font-mono text-slate-400 mb-1">
                    <span>Bonding / Liquidity Curve</span>
                    <span className="text-emerald-400">{t.bonding_curve_pct}%</span>
                  </div>
                  <div className="w-full h-1.5 rounded-full bg-slate-800 overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-emerald-500 to-sky-400"
                      style={{ width: `${t.bonding_curve_pct}%` }}
                    />
                  </div>
                </div>

                {/* Key Metrics Grid with USD + small IDR */}
                <div className="grid grid-cols-3 gap-2 text-[11px] font-mono bg-slate-950/70 p-2 rounded-lg border border-slate-800/60">
                  <div>
                    <span className="text-slate-500 block">MCAP</span>
                    <span className="text-slate-200 font-semibold">${(t.market_cap / 1000).toFixed(1)}K</span>
                    <span className="text-[9px] text-slate-400 block">≈ {formatIdr(t.market_cap * usdIdr)}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 block">LIQUIDITY</span>
                    <span className="text-slate-200 font-semibold">${(t.liquidity / 1000).toFixed(1)}K</span>
                    <span className="text-[9px] text-slate-400 block">≈ {formatIdr(t.liquidity * usdIdr)}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 block">5M VOL</span>
                    <span className="text-sky-400 font-semibold">${(t.volume_5m / 1000).toFixed(1)}K</span>
                    <span
                      className={`text-[9px] block ${
                        (t.price_change_5m || 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'
                      }`}
                    >
                      5m: {(t.price_change_5m || 0) >= 0 ? '+' : ''}
                      {t.price_change_5m ?? 0}%
                    </span>
                  </div>
                </div>

                {/* Security Badges */}
                <div className="flex flex-wrap items-center justify-between gap-1.5 text-[10px] font-mono">
                  <div className="flex flex-wrap gap-1.5">
                    <span
                      className={`px-1.5 py-0.5 rounded border ${
                        isSafe
                          ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30'
                          : 'bg-rose-500/15 text-rose-300 border-rose-500/40'
                      }`}
                    >
                      Shield {t.safety_score}/100
                    </span>
                    <span className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-300">
                      B/S 5m: {t.buys_5m ?? 0}/{t.sells_5m ?? 0}
                    </span>
                  </div>
                  {t.dex_url && (
                    <a
                      href={t.dex_url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-sky-400 hover:underline"
                    >
                      DexScreener ↗
                    </a>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-100 flex items-center gap-2">
            🔥 Trenches & Pulse Radar (100% Real-Time DexScreener)
          </h1>
          <p className="text-sm text-slate-400">
            Data harga, volume, dan likuiditas asli dari jaringan DEX saat ini • Kurs: $1 = {formatIdr(usdIdr)}
          </p>
        </div>

        <div className="flex items-center gap-3 bg-[#0b0f17] border border-slate-800 px-4 py-2 rounded-xl text-xs font-mono">
          <button
            type="button"
            onClick={() => pulseQuery.refetch()}
            className="px-2.5 py-1 rounded-lg bg-sky-500/20 text-sky-300 border border-sky-500/30 hover:bg-sky-500/30"
          >
            🔄 Refresh Live Market
          </button>
          <span className="text-slate-400">Filter Shield:</span>
          {[0, 75, 85].map((score) => (
            <button
              key={score}
              onClick={() => setMinSafety(score)}
              className={`px-2.5 py-1 rounded-lg transition ${
                minSafety === score
                  ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                  : 'bg-slate-900 text-slate-400 hover:text-slate-200'
              }`}
            >
              {score === 0 ? 'All' : `≥ ${score}`}
            </button>
          ))}
        </div>
      </div>

      {snipeFeedback && (
        <div className="p-4 rounded-xl bg-emerald-950/60 border border-emerald-500/40 text-emerald-200 text-sm font-mono">
          {snipeFeedback}
        </div>
      )}
      {snipeError && (
        <div className="p-4 rounded-xl bg-rose-950/60 border border-rose-500/40 text-rose-200 text-sm font-mono">
          🛡️ {snipeError}
        </div>
      )}

      <QueryState isLoading={pulseQuery.isLoading} isError={pulseQuery.isError} error={pulseQuery.error}>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
          {renderColumn(
            '🌱 Micro-Cap & New Pairs',
            'Pasangan meme coin baru & kapitalisasi mikro',
            'bg-sky-400',
            pulseQuery.data?.new_creations || []
          )}
          {renderColumn(
            '⚡ Mid-Cap Momentum (Pumpswap / DEX)',
            'Token dengan akselerasi volume & likuiditas aktif',
            'bg-amber-400',
            pulseQuery.data?.final_stretch || []
          )}
          {renderColumn(
            '🚀 Graduated & Major Meme Liquidity',
            'Pool DEX likuiditas besar & terverifikasi',
            'bg-emerald-400',
            pulseQuery.data?.migrated || []
          )}
        </div>
      </QueryState>
    </div>
  );
}
