import React, { useState, useEffect } from 'react';
import { api, formatIdr } from '@/lib/api';
import { LucideIcon } from '@/components/LucideIcon';

function formatCryptoUsd(val: number | undefined | null): string {
  if (val === undefined || val === null || isNaN(Number(val))) return '$0.00';
  const n = Number(val);
  if (Math.abs(n) >= 100) {
    return '$' + n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  if (Math.abs(n) >= 1) {
    return '$' + n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 4 });
  }
  if (Math.abs(n) >= 0.01) {
    return '$' + n.toLocaleString('en-US', { minimumFractionDigits: 4, maximumFractionDigits: 6 });
  }
  return '$' + n.toLocaleString('en-US', { minimumFractionDigits: 6, maximumFractionDigits: 8 });
}

export default function CryptoAnalysisPage() {
  const [queryInput, setQueryInput] = useState<string>('BTC');
  const [activeSymbol, setActiveSymbol] = useState<string>('BTC');
  const [selectedTimeframe, setSelectedTimeframe] = useState<string>('1d');
  const [data, setData] = useState<any | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Spot Budget & Staking Simulator in IDR
  const [budgetIdr, setBudgetIdr] = useState<number>(5000000);

  // Custom Risk Calculator state
  const [riskCapitalIdr, setRiskCapitalIdr] = useState<number>(20000000);
  const [riskPct, setRiskPct] = useState<number>(2.0);
  const [riskResult, setRiskResult] = useState<any | null>(null);
  const [riskLoading, setRiskLoading] = useState<boolean>(false);

  // Futures Tab Side Selection ('LONG' or 'SHORT' override)
  const [futuresSideOverride, setFuturesSideOverride] = useState<'LONG' | 'SHORT' | null>(null);

  const loadCrypto = async (sym: string, force: boolean = false, tf: string = selectedTimeframe) => {
    const clean = (sym || 'BTC').trim().toUpperCase();
    if (!clean) return;
    if (force) setRefreshing(true);
    else setLoading(true);
    setError(null);
    setFuturesSideOverride(null);
    try {
      const res = await api.analyzeCrypto(clean, force, tf);
      setData(res);
      setActiveSymbol(res.code || clean);
      if (res.selected_timeframe) {
        setSelectedTimeframe(res.selected_timeframe);
      }
      if (res.risk_calculator_default) {
        setRiskResult(res.risk_calculator_default);
      }
    } catch (err: any) {
      setError(err?.message || `Gagal memuat analisis kripto untuk '${clean}'`);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadCrypto('BTC', false, '1d');
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (queryInput.trim()) {
      loadCrypto(queryInput.trim(), false, selectedTimeframe);
    }
  };

  const handleRunRiskCalc = async () => {
    if (!activePlan || !data) return;
    setRiskLoading(true);
    try {
      const res = await api.calculateCryptoRisk({
        capital_idr: riskCapitalIdr,
        entry_price_usd: Number(data.current_price_usd),
        stop_loss_usd: Number(activePlan.stop_loss_usd),
        target_price_usd: Number(activePlan.tp_2_usd),
        max_risk_pct: riskPct,
        investment_idr: budgetIdr,
      });
      setRiskResult(res);
    } catch (err: any) {
      setError(err?.message || 'Gagal menghitung risiko posisi kripto');
    } finally {
      setRiskLoading(false);
    }
  };

  const popularList = data?.popular_cryptos || [
    { code: 'BTC', name: 'Bitcoin' },
    { code: 'ETH', name: 'Ethereum' },
    { code: 'SOL', name: 'Solana' },
    { code: 'BNB', name: 'BNB' },
    { code: 'XRP', name: 'XRP' },
    { code: 'DOGE', name: 'Dogecoin' },
    { code: 'SUI', name: 'Sui' },
    { code: 'ADA', name: 'Cardano' },
    { code: 'AVAX', name: 'Avalanche' },
    { code: 'LINK', name: 'Chainlink' },
    { code: 'TON', name: 'Toncoin' },
    { code: 'PEPE', name: 'Pepe' },
    { code: 'BONK', name: 'Bonk' },
  ];

  const availableTimeframes = data?.available_timeframes || [
    { id: '15m', label: '15 Menit', horizon: 'Scalping Cepat (15 Menit)', hold_duration: '15 – 180 Menit' },
    { id: '1h', label: '1 Jam', horizon: 'Intraday Crypto (1 Jam)', hold_duration: '4 – 24 Jam' },
    { id: '4h', label: '4 Jam', horizon: 'Swing Momentum (4 Jam)', hold_duration: '1 – 5 Hari' },
    { id: '1d', label: '1 Hari', horizon: 'Swing Harian (1 Hari)', hold_duration: '3 – 14 Hari' },
    { id: '1w', label: '1 Minggu', horizon: 'Swing Mingguan (1 Minggu)', hold_duration: '2 – 8 Minggu' },
    { id: '1mo', label: '1 Bulan', horizon: 'Investasi Siklus (1 Bulan)', hold_duration: '1 – 6+ Bulan' },
  ];

  const activePlan = data?.timeframes_plan?.[selectedTimeframe] || data?.trading_plan;
  const futuresContract = data?.futures_contract;
  const activeFuturesPlan = data?.futures_timeframes_plan?.[selectedTimeframe] || data?.futures_plan;
  const selectedFuturesSide: 'LONG' | 'SHORT' =
    futuresSideOverride || (activeFuturesPlan?.primary_bias === 'SHORT' ? 'SHORT' : 'LONG');
  const currentFuturesSetup =
    selectedFuturesSide === 'SHORT' ? activeFuturesPlan?.short_setup : activeFuturesPlan?.long_setup;

  const decision = data?.timeframes_decision?.[selectedTimeframe] || data?.trading_decision;

  const pulse = data?.market_pulse;
  const tok = data?.tokenomics;
  const tech = data?.technicals;

  // Spot Budget Simulator Math
  const safeBudgetIdr = Math.max(100000, Number(budgetIdr) || 1000000);
  const fxRate = Number(data?.usd_idr || 16300);
  const priceUsd = Number(data?.current_price_usd || 1);
  const priceIdr = Number(data?.current_price_idr || priceUsd * fxRate);
  const acquiredCoins = priceIdr > 0 ? safeBudgetIdr / priceIdr : 0;
  const netTp1ProfitIdr = Math.round(safeBudgetIdr * (Number(activePlan?.net_tp_1_pct || 0) / 100));
  const netTp2ProfitIdr = Math.round(safeBudgetIdr * (Number(activePlan?.net_tp_2_pct || 0) / 100));
  const netSlLossIdr = Math.round(safeBudgetIdr * (Number(activePlan?.net_stop_loss_pct || 0) / 100));
  const estAnnualStakingIdr = Math.round(safeBudgetIdr * (Number(tok?.staking_apr_pct || 0) / 100));
  const estAnnualStakingCoins = acquiredCoins * (Number(tok?.staking_apr_pct || 0) / 100);

  const badgeStyle = (badge: string) => {
    if (badge === 'BULLISH' || badge === 'BUY' || badge?.includes('BUY'))
      return 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40';
    if (badge === 'BEARISH' || badge === 'SELL' || badge?.includes('SELL'))
      return 'bg-rose-500/20 text-rose-300 border-rose-500/40';
    if (badge === 'REBOUND WATCH' || badge === 'WAIT' || badge?.includes('TUNGGU'))
      return 'bg-amber-500/20 text-amber-300 border-amber-500/40';
    return 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40';
  };

  return (
    <div className="space-y-5 pb-10">
      {/* HEADER & GLOBAL CRYPTO MARKET PULSE BANNER */}
      <div className="bg-gradient-to-r from-[#0B0E14] via-[#111927] to-[#0B0E14] border border-slate-800/80 rounded-2xl p-5 shadow-xl">
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
          <div>
            <div className="flex flex-wrap items-center gap-2 mb-1.5">
              <span className="px-2.5 py-0.5 rounded-full text-[10px] font-extrabold uppercase tracking-wider bg-cyan-500/15 text-cyan-300 border border-cyan-500/30">
                ANALISA CRYPTO GLOBAL & TOKENOMICS (24/7)
              </span>
              <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
                {pulse?.market_status || 'REAL-TIME • 24/7 CRYPTO FEED'}
              </span>
              {data?.updated_at && (
                <span className="text-[11px] text-slate-400 flex items-center gap-1">
                  <LucideIcon name="clock" className="w-3 h-3 text-slate-500" />
                  Update: {data.updated_at}
                </span>
              )}
            </div>
            <h1 className="text-xl sm:text-2xl font-black text-white tracking-tight flex items-center gap-2.5">
              <LucideIcon name="cpu" className="w-6 h-6 text-cyan-400" />
              Analisa Cepat Kripto, Trading Plan & Staking Yield
            </h1>
            <p className="text-xs sm:text-sm text-slate-400 mt-1">
              Masukkan kode koin (<span className="text-white font-semibold">BTC, ETH, SOL, BNB, XRP, DOGE, SUI, PEPE</span>) untuk melihat Harga Real-Time (USD & Rp), Zona Entry, TP, Stop Loss, Indikator Teknikal, Tokenomics & Staking APR.
            </p>

            {/* LIVE BTC / ETH / SOL PULSE BAR */}
            {pulse && (
              <div className="mt-3 flex flex-wrap items-center gap-2.5 bg-slate-900/90 border border-slate-700/80 rounded-xl px-3.5 py-2.5">
                {(['btc', 'eth', 'sol'] as const).map((k) => {
                  const coin = pulse[k];
                  if (!coin) return null;
                  const up = Number(coin.change_pct) >= 0;
                  return (
                    <button
                      key={coin.code}
                      type="button"
                      onClick={() => {
                        setQueryInput(coin.code);
                        loadCrypto(coin.code, false, selectedTimeframe);
                      }}
                      className="flex items-center gap-2 pr-3 border-r border-slate-800 last:border-none hover:opacity-85 transition text-left"
                    >
                      <span className="px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-300 text-[10px] font-extrabold">
                        {coin.code}
                      </span>
                      <div>
                        <div className="text-xs font-black text-white">
                          {formatCryptoUsd(coin.price_usd)}{' '}
                          <span className={`text-[11px] font-bold ${up ? 'text-emerald-400' : 'text-rose-400'}`}>
                            ({up ? '+' : ''}{coin.change_pct}%)
                          </span>
                        </div>
                        <div className="text-[10px] text-slate-400">{formatIdr(coin.price_idr)}</div>
                      </div>
                    </button>
                  );
                })}
                <div className="text-[11px] text-slate-300 font-semibold">
                  Kurs: <span className="text-white font-bold">{formatIdr(pulse.usd_idr)}/USD</span>
                </div>
                <span className="px-2.5 py-0.5 rounded-md text-[10px] font-extrabold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
                  {pulse.market_regime}
                </span>
              </div>
            )}
          </div>

          {/* SEARCH BAR */}
          <form onSubmit={handleSearch} className="flex items-center gap-2">
            <div className="relative">
              <LucideIcon name="search" className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={queryInput}
                onChange={(e) => setQueryInput(e.target.value.toUpperCase())}
                placeholder="Ketik Koin (mis. BTC, SOL, PEPE)..."
                className="bg-slate-900/90 border border-slate-700/80 focus:border-cyan-500 rounded-xl pl-9 pr-3 py-2 text-xs sm:text-sm text-white font-bold placeholder-slate-500 outline-none w-52 sm:w-64 uppercase"
              />
            </div>
            <button
              type="submit"
              disabled={loading || refreshing}
              className="px-4 py-2 rounded-xl text-xs font-extrabold bg-cyan-500 hover:bg-cyan-400 text-slate-950 transition shadow-lg shadow-cyan-500/20 flex items-center gap-1.5"
            >
              <LucideIcon name="zap" className="w-3.5 h-3.5" />
              Analisa
            </button>
            <button
              type="button"
              onClick={() => loadCrypto(activeSymbol, true, selectedTimeframe)}
              disabled={loading || refreshing}
              className="p-2 rounded-xl bg-slate-800/90 hover:bg-slate-700 text-slate-200 border border-slate-700 transition"
              title="Refresh Harga Kripto"
            >
              <LucideIcon name="refresh-cw" className={`w-4 h-4 ${refreshing ? 'animate-spin text-cyan-400' : ''}`} />
            </button>
          </form>
        </div>

        {/* POPULAR CRYPTO QUICK BUTTONS */}
        <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center gap-1.5 overflow-x-auto no-scrollbar">
          <span className="text-[11px] font-bold text-slate-400 mr-1 shrink-0">Koin Populer:</span>
          {popularList.map((item: any) => {
            const active = activeSymbol === item.code;
            return (
              <button
                key={item.code}
                type="button"
                onClick={() => {
                  setQueryInput(item.code);
                  loadCrypto(item.code, false, selectedTimeframe);
                }}
                className={`px-2.5 py-1 rounded-lg text-xs font-extrabold transition shrink-0 border ${
                  active
                    ? 'bg-cyan-500 text-slate-950 border-cyan-400 shadow-sm'
                    : 'bg-slate-900/80 text-slate-300 border-slate-800 hover:border-slate-700 hover:text-white'
                }`}
              >
                {item.code}
              </button>
            );
          })}
        </div>
      </div>

      {/* ERROR ALERT */}
      {error && (
        <div className="bg-rose-500/10 border border-rose-500/30 rounded-xl p-4 text-rose-300 text-xs sm:text-sm flex items-center justify-between">
          <div className="flex items-center gap-2">
            <LucideIcon name="alert-triangle" className="w-5 h-5 text-rose-400 shrink-0" />
            <span>{error}</span>
          </div>
          <button
            onClick={() => loadCrypto('BTC', true, selectedTimeframe)}
            className="px-3 py-1 rounded-lg bg-rose-500/20 hover:bg-rose-500/30 text-rose-200 text-xs font-bold"
          >
            Reset ke BTC
          </button>
        </div>
      )}

      {/* LOADING SKELETON */}
      {loading && !data ? (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {[1, 2, 3].map((n) => (
            <div key={n} className="bg-[#0B0E14] border border-slate-800/80 rounded-2xl p-5 animate-pulse h-64" />
          ))}
        </div>
      ) : data && activePlan ? (
        <>
          {/* TOP HERO: LIVE PRICE (USD & IDR) + SIGNAL VERDICT + 52-WEEK RANGE */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {/* 1. CURRENT PRICE CARD */}
            <div className="bg-[#0B0E14] border border-slate-800/80 rounded-2xl p-5 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-2xl font-black text-white">{data.code}</span>
                      <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-slate-800 text-cyan-300 border border-slate-700">
                        {data.category}
                      </span>
                    </div>
                    <p className="text-xs text-slate-400 font-medium mt-0.5">{data.name}</p>
                  </div>
                  <span className={`px-3 py-1 rounded-xl text-xs font-black border ${badgeStyle(activePlan.trend_badge)}`}>
                    {activePlan.trend_status}
                  </span>
                </div>

                <div className="mt-4 flex items-baseline gap-3">
                  <span className="text-3xl sm:text-4xl font-black text-white tracking-tight">
                    {formatCryptoUsd(data.current_price_usd)}
                  </span>
                  <span
                    className={`text-sm font-extrabold px-2 py-0.5 rounded-lg ${
                      data.day_change_pct >= 0
                        ? 'bg-emerald-500/15 text-emerald-400'
                        : 'bg-rose-500/15 text-rose-400'
                    }`}
                  >
                    {data.day_change_pct >= 0 ? '+' : ''}
                    {data.day_change_pct}% (24H)
                  </span>
                </div>
                <div className="text-sm font-extrabold text-cyan-400 mt-1">
                  ≈ {formatIdr(data.current_price_idr)} <span className="text-[11px] text-slate-400 font-normal">(Kurs {formatIdr(data.usd_idr)}/USD)</span>
                </div>
              </div>

              <div className="mt-4 pt-3 border-t border-slate-800/80 grid grid-cols-3 gap-2 text-xs">
                <div>
                  <span className="text-slate-500 block text-[10px]">24H Low</span>
                  <span className="text-slate-200 font-bold">{formatCryptoUsd(data.day_low_usd)}</span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[10px]">24H High</span>
                  <span className="text-slate-200 font-bold">{formatCryptoUsd(data.day_high_usd)}</span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[10px]">Staking APR</span>
                  <span className="text-emerald-400 font-bold">
                    {tok?.pays_staking_yield ? `~${tok.staking_apr_pct}% / thn` : 'Non-PoS (0%)'}
                  </span>
                </div>
              </div>
            </div>

            {/* 2. MULTI-PERIOD PERFORMANCE & 52-WEEK RANGE */}
            <div className="bg-[#0B0E14] border border-slate-800/80 rounded-2xl p-5 flex flex-col justify-between">
              <div>
                <h3 className="text-xs font-extrabold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                  <LucideIcon name="activity" className="w-4 h-4 text-cyan-400" />
                  Performa Harga & Rentang 52 Minggu
                </h3>
                <div className="grid grid-cols-4 gap-2 mt-3">
                  {[
                    { label: '7 Hari', val: data.performance?.['7d_pct'] },
                    { label: '30 Hari', val: data.performance?.['30d_pct'] },
                    { label: '90 Hari', val: data.performance?.['90d_pct'] },
                    { label: '1 Tahun', val: data.performance?.['1y_pct'] },
                  ].map((p) => (
                    <div key={p.label} className="bg-slate-900/70 border border-slate-800/80 rounded-xl p-2.5 text-center">
                      <span className="text-[10px] text-slate-400 block">{p.label}</span>
                      <span
                        className={`text-xs font-extrabold mt-0.5 block ${
                          Number(p.val) >= 0 ? 'text-emerald-400' : 'text-rose-400'
                        }`}
                      >
                        {Number(p.val) >= 0 ? '+' : ''}
                        {p.val}%
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="mt-4 pt-3 border-t border-slate-800/80">
                <div className="flex justify-between text-[11px] text-slate-400 mb-1">
                  <span>52W Low: <strong className="text-slate-200">{formatCryptoUsd(data.range_52w?.low_usd)}</strong></span>
                  <span>Posisi: <strong className="text-cyan-400">{data.range_52w?.position_pct}%</strong></span>
                  <span>52W High: <strong className="text-slate-200">{formatCryptoUsd(data.range_52w?.high_usd)}</strong></span>
                </div>
                <div className="w-full h-2.5 bg-slate-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-rose-500 via-amber-400 to-emerald-400 rounded-full"
                    style={{ width: `${Math.min(100, Math.max(3, Number(data.range_52w?.position_pct || 50)))}%` }}
                  />
                </div>
              </div>
            </div>

            {/* 3. KEPUTUSAN TRADING QUICK CARD */}
            <div className="bg-[#0B0E14] border border-slate-800/80 rounded-2xl p-5 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">
                    Keputusan Trading ({decision?.timeframe_label || activePlan.timeframe_label})
                  </span>
                  <span className={`px-2.5 py-0.5 rounded-md text-[10px] font-black border ${badgeStyle(decision?.decision_badge || activePlan.trend_badge)}`}>
                    {decision?.decision || activePlan.signal_direction}
                  </span>
                </div>
                <div className="mt-2.5 p-3 rounded-xl bg-slate-900/90 border border-slate-800">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-black text-white uppercase">
                      {decision?.verdict_headline || activePlan.action_verdict}
                    </span>
                    <span className="text-[10px] font-extrabold text-cyan-400">
                      R/R {activePlan.net_risk_reward_ratio}
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-300 mt-1 leading-relaxed">
                    {decision?.wait_price_display || activePlan.wait_reason || activePlan.entry_confirmation}
                  </p>
                </div>
                <ul className="mt-3 space-y-1.5">
                  {(data.summary_notes || []).slice(0, 3).map((note: string, i: number) => (
                    <li key={i} className="text-[11px] text-slate-300 flex items-start gap-1.5">
                      <span className="text-cyan-400 font-bold">•</span>
                      <span>{note}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>

          {/* SECTION 1.5: CARD KEPUTUSAN TRADING UTAMA (BUY, SELL, HOLD, ATAU TUNGGU DULU KE BERAPA) */}
          {decision && (
            <div className="bg-gradient-to-br from-[#0B0E14] via-[#0E1726] to-[#0B0E14] border border-cyan-500/40 rounded-2xl p-5 shadow-2xl relative overflow-hidden">
              {/* ACCENT GLOW */}
              <div
                className={`absolute top-0 right-0 w-80 h-80 rounded-full blur-3xl pointer-events-none opacity-15 ${
                  decision.badge_color === 'emerald'
                    ? 'bg-emerald-500'
                    : decision.badge_color === 'rose'
                    ? 'bg-rose-500'
                    : decision.badge_color === 'amber'
                    ? 'bg-amber-500'
                    : 'bg-cyan-500'
                }`}
              />

              {/* CARD HEADER */}
              <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 pb-3.5 mb-4 border-b border-slate-800/80 relative z-10">
                <div>
                  <div className="flex flex-wrap items-center gap-2 mb-1.5">
                    <span className="px-2.5 py-0.5 rounded-full text-[10px] font-extrabold uppercase tracking-wider bg-cyan-500/15 text-cyan-300 border border-cyan-500/30 flex items-center gap-1.5">
                      <LucideIcon name="crosshair" className="w-3 h-3 text-cyan-400" />
                      KEPUTUSAN TRADING UTAMA ({decision.timeframe_label?.toUpperCase() || '1 HARI'})
                    </span>
                    <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-slate-800 text-slate-300 border border-slate-700">
                      Skor Keyakinan Teknis: <strong className="text-white">{decision.confidence_score}%</strong>
                    </span>
                    <span className="text-[11px] text-slate-400">
                      Horison: <strong className="text-cyan-300">{activePlan.horizon}</strong>
                    </span>
                  </div>
                  <h2 className="text-base sm:text-xl font-black text-white flex items-center gap-2">
                    <span>Keputusan Trading Kripto: Apakah Buy, Sell, Hold, atau Tunggu Dulu?</span>
                  </h2>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Rekomendasi tindakan terpadu dengan panduan khusus bagi calon pembeli (cash) maupun pemilik koin (holders).
                  </p>
                </div>

                {/* PROMINENT VERDICT PILL */}
                <div className="flex items-center gap-3 shrink-0">
                  <div
                    className={`px-4 py-2 rounded-xl border flex items-center gap-2.5 shadow-lg ${
                      decision.badge_color === 'emerald'
                        ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/50 shadow-emerald-500/10'
                        : decision.badge_color === 'rose'
                        ? 'bg-rose-500/20 text-rose-300 border-rose-500/50 shadow-rose-500/10'
                        : decision.badge_color === 'amber'
                        ? 'bg-amber-500/20 text-amber-300 border-amber-500/50 shadow-amber-500/10'
                        : 'bg-cyan-500/20 text-cyan-300 border-cyan-500/50 shadow-cyan-500/10'
                    }`}
                  >
                    <span
                      className={`w-2.5 h-2.5 rounded-full animate-ping ${
                        decision.badge_color === 'emerald'
                          ? 'bg-emerald-400'
                          : decision.badge_color === 'rose'
                          ? 'bg-rose-400'
                          : decision.badge_color === 'amber'
                          ? 'bg-amber-400'
                          : 'bg-cyan-400'
                      }`}
                    />
                    <div className="text-left">
                      <span className="text-[10px] block font-extrabold uppercase tracking-wider text-slate-400">
                        KEPUTUSAN SISTEM:
                      </span>
                      <span className="text-sm sm:text-base font-black tracking-wide">
                        {decision.decision_badge}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* CENTRAL HIGHLIGHT BOX: TUNGGU DULU KE BERAPA / LEVEL ACUAN TRADING */}
              <div
                className={`p-4 rounded-xl border mb-4 relative z-10 transition ${
                  decision.badge_color === 'emerald'
                    ? 'bg-emerald-500/10 border-emerald-500/30'
                    : decision.badge_color === 'rose'
                    ? 'bg-rose-500/10 border-rose-500/30'
                    : decision.badge_color === 'amber'
                    ? 'bg-amber-500/15 border-amber-500/40 shadow-sm'
                    : 'bg-cyan-500/10 border-cyan-500/30'
                }`}
              >
                <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-[11px] font-black uppercase tracking-wider text-amber-300 flex items-center gap-1.5">
                        <LucideIcon name="alert-circle" className="w-4 h-4 text-amber-400" />
                        {decision.decision === 'TUNGGU DULU'
                          ? 'TUNGGU DULU KE BERAPA? (TARGET LEVEL MASUK)'
                          : decision.decision === 'BUY'
                          ? 'LEVEL ENTRY BELI SEKARANG'
                          : decision.decision === 'SELL'
                          ? 'LEVEL TARGET JUAL / TAKE PROFIT'
                          : 'RENTANG LEVEL PANTAUAN (HOLD)'}
                      </span>
                      {decision.wait_distance_pct !== 0 && (
                        <span className="px-2 py-0.5 rounded text-[10px] font-black bg-slate-900/90 text-amber-300 border border-slate-700">
                          {decision.wait_distance_pct > 0 ? '+' : ''}
                          {decision.wait_distance_pct}% dari harga saat ini
                        </span>
                      )}
                    </div>
                    <div className="text-xl sm:text-2xl font-black text-white mt-1.5">
                      {decision.target_display}
                    </div>
                    <p className="text-xs text-slate-300 mt-1 leading-relaxed">
                      {decision.wait_price_display}
                    </p>
                  </div>

                  <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-3 shrink-0 lg:text-right">
                    <span className="text-[10px] text-slate-400 block font-bold uppercase">Kondisi Konfirmasi</span>
                    <span className="text-xs font-semibold text-slate-200 mt-0.5 block max-w-sm">
                      {decision.trigger_condition}
                    </span>
                  </div>
                </div>
              </div>

              {/* DUAL PERSONA GUIDANCE: CALON PEMBELI vs PEMILIK KOIN */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5 mb-4 relative z-10">
                {/* 1. BAGI CALON PEMBELI (BELUM PUNYA KOIN) */}
                <div className="bg-slate-900/80 border border-slate-800/90 rounded-xl p-4 flex flex-col justify-between">
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-[11px] font-black uppercase tracking-wider text-cyan-400 flex items-center gap-1.5">
                        <LucideIcon name="wallet" className="w-3.5 h-3.5" />
                        Bagi yang Belum Punya Koin (Calon Pembeli)
                      </span>
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-black border ${
                          decision.prospective_buyers?.action === 'BUY SEKARANG'
                            ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                            : 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                        }`}
                      >
                        {decision.prospective_buyers?.action}
                      </span>
                    </div>
                    <p className="text-xs text-slate-300 leading-relaxed mt-1">
                      {decision.prospective_buyers?.guidance}
                    </p>
                  </div>
                  <div className="mt-3 pt-2.5 border-t border-slate-800/80 flex items-center justify-between text-[11px]">
                    <span className="text-slate-400">Patokan Masuk:</span>
                    <span className="text-white font-black">
                      {formatCryptoUsd(decision.prospective_buyers?.entry_ref_usd)}{' '}
                      <span className="text-slate-400 font-normal">
                        ({formatIdr(decision.prospective_buyers?.entry_ref_idr)})
                      </span>
                    </span>
                  </div>
                </div>

                {/* 2. BAGI PEMILIK KOIN (SUDAH PUNYA POSISI) */}
                <div className="bg-slate-900/80 border border-slate-800/90 rounded-xl p-4 flex flex-col justify-between">
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-[11px] font-black uppercase tracking-wider text-purple-400 flex items-center gap-1.5">
                        <LucideIcon name="coins" className="w-3.5 h-3.5" />
                        Bagi Pemilik Koin (Sudah Punya Posisi)
                      </span>
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-black border ${
                          decision.current_holders?.action?.includes('SELL') || decision.current_holders?.action?.includes('REDUCE')
                            ? 'bg-rose-500/20 text-rose-300 border-rose-500/40'
                            : decision.current_holders?.action?.includes('ADD')
                            ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                            : 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40'
                        }`}
                      >
                        {decision.current_holders?.action}
                      </span>
                    </div>
                    <p className="text-xs text-slate-300 leading-relaxed mt-1">
                      {decision.current_holders?.guidance}
                    </p>
                  </div>
                  <div className="mt-3 pt-2.5 border-t border-slate-800/80 flex items-center justify-between text-[11px]">
                    <span className="text-slate-400">Batas Pengaman (SL/Exit):</span>
                    <span className="text-rose-400 font-black">
                      {formatCryptoUsd(decision.current_holders?.exit_ref_usd)}{' '}
                      <span className="text-slate-400 font-normal">
                        ({formatIdr(decision.current_holders?.exit_ref_idr)})
                      </span>
                    </span>
                  </div>
                </div>
              </div>

              {/* 3 LANGKAH TINDAKAN PRIORITAS */}
              <div className="bg-slate-950/70 border border-slate-800/80 rounded-xl p-3.5 relative z-10">
                <span className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400 block mb-2">
                  Langkah Tindakan yang Disarankan Sekarang:
                </span>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                  {(decision.action_steps || []).map((step: string, sIdx: number) => (
                    <div
                      key={sIdx}
                      className="bg-slate-900/70 border border-slate-800 rounded-lg p-2.5 text-xs text-slate-300 flex items-start gap-2"
                    >
                      <span className="text-cyan-400 font-extrabold">•</span>
                      <span>{step.replace(/^\d+\.\s*/, '')}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* SECTION 2: MULTI-TIMEFRAME TRADING PLAN (ENTRY, TP1, TP2, STOP LOSS) */}
          <div className="bg-gradient-to-br from-[#0B0E14] via-[#0F1622] to-[#0B0E14] border border-cyan-500/30 rounded-2xl p-5 shadow-lg">
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 mb-4 pb-3 border-b border-slate-800/80">
              <div>
                <div className="flex items-center gap-2">
                  <LucideIcon name="crosshair" className="w-5 h-5 text-cyan-400" />
                  <h2 className="text-base sm:text-lg font-black text-white">
                    Rekomendasi Trading Plan Crypto (Entry, TP & Stop Loss)
                  </h2>
                </div>
                <p className="text-xs text-slate-400 mt-0.5">
                  Horison: <strong className="text-cyan-300">{activePlan.horizon}</strong> • Estimasi Hold:{' '}
                  <strong className="text-white">{activePlan.hold_duration}</strong> • Berlaku s/d:{' '}
                  <strong className="text-slate-300">{activePlan.valid_until}</strong>
                </p>
              </div>

              {/* TIMEFRAME SELECTOR BUTTONS (15m, 1h, 4h, 1d, 1w, 1mo) */}
              <div className="flex flex-wrap items-center gap-1.5 bg-slate-900/90 p-1.5 rounded-xl border border-slate-800">
                <span className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400 px-2">
                  Timeframe:
                </span>
                {availableTimeframes.map((tf: any) => {
                  const isActive = selectedTimeframe === tf.id;
                  return (
                    <button
                      key={tf.id}
                      type="button"
                      onClick={() => setSelectedTimeframe(tf.id)}
                      className={`px-2.5 py-1 rounded-lg text-xs font-extrabold transition ${
                        isActive
                          ? 'bg-cyan-500 text-slate-950 shadow-sm'
                          : 'text-slate-300 hover:text-white hover:bg-slate-800'
                      }`}
                    >
                      {tf.label}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
              {/* ENTRY ZONE */}
              <div className="bg-slate-900/90 border border-cyan-500/40 rounded-xl p-4">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-extrabold uppercase text-cyan-400">1. Zona Beli (Entry Area)</span>
                  <LucideIcon name="log-in" className="w-4 h-4 text-cyan-400" />
                </div>
                <div className="text-lg font-black text-white mt-2">
                  {formatCryptoUsd(activePlan.entry_zone_low_usd)} – {formatCryptoUsd(activePlan.entry_zone_high_usd)}
                </div>
                <p className="text-[11px] text-cyan-300 font-semibold mt-0.5">
                  {formatIdr(activePlan.entry_zone_low_idr)} – {formatIdr(activePlan.entry_zone_high_idr)}
                </p>
                <p className="text-[11px] text-slate-400 mt-1">
                  Support 1: <strong className="text-slate-200">{formatCryptoUsd(activePlan.support_1_usd)}</strong> | Support 2:{' '}
                  <strong className="text-slate-200">{formatCryptoUsd(activePlan.support_2_usd)}</strong>
                </p>
              </div>

              {/* TAKE PROFIT 1 */}
              <div className="bg-slate-900/90 border border-emerald-500/40 rounded-xl p-4">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-extrabold uppercase text-emerald-400">2. Target Profit 1 (TP 1)</span>
                  <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 text-[10px] font-black">
                    +{activePlan.tp_1_pct}% (Net +{activePlan.net_tp_1_pct}%)
                  </span>
                </div>
                <div className="text-xl font-black text-emerald-400 mt-2">
                  {formatCryptoUsd(activePlan.tp_1_usd)}
                </div>
                <p className="text-[11px] text-slate-300 font-semibold mt-0.5">
                  ≈ {formatIdr(activePlan.tp_1_idr)}
                </p>
                <p className="text-[11px] text-slate-400 mt-1">
                  Target resistensi terdekat untuk amankan 50% profit.
                </p>
              </div>

              {/* TAKE PROFIT 2 */}
              <div className="bg-slate-900/90 border border-emerald-500/40 rounded-xl p-4">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-extrabold uppercase text-emerald-400">3. Target Profit 2 (TP 2)</span>
                  <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 text-[10px] font-black">
                    +{activePlan.tp_2_pct}% (Net +{activePlan.net_tp_2_pct}%)
                  </span>
                </div>
                <div className="text-xl font-black text-emerald-400 mt-2">
                  {formatCryptoUsd(activePlan.tp_2_usd)}
                </div>
                <p className="text-[11px] text-slate-300 font-semibold mt-0.5">
                  ≈ {formatIdr(activePlan.tp_2_idr)}
                </p>
                <p className="text-[11px] text-slate-400 mt-1">
                  Target swing optimal ({activePlan.timeframe_label}) jika breakout berlanjut.
                </p>
              </div>

              {/* STOP LOSS */}
              <div className="bg-slate-900/90 border border-rose-500/40 rounded-xl p-4">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-extrabold uppercase text-rose-400">4. Batas Stop Loss (SL)</span>
                  <span className="px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 text-[10px] font-black">
                    {activePlan.stop_loss_pct}% (Net {activePlan.net_stop_loss_pct}%)
                  </span>
                </div>
                <div className="text-xl font-black text-rose-400 mt-2">
                  {formatCryptoUsd(activePlan.stop_loss_usd)}
                </div>
                <p className="text-[11px] text-slate-300 font-semibold mt-0.5">
                  ≈ {formatIdr(activePlan.stop_loss_idr)}
                </p>
                <p className="text-[11px] text-slate-400 mt-1">
                  Batas disiplin cut-loss untuk melindungi modal dari breakdown.
                </p>
              </div>
            </div>
          </div>

          {/* SECTION 2B: DEDICATED FUTURES TRADING PLAN CARD (LONG / SHORT) */}
          <div className="bg-gradient-to-br from-[#0B0E14] via-[#0E1522] to-[#0B0E14] border border-amber-500/35 rounded-2xl p-5 shadow-xl relative overflow-hidden">
            {/* AMBIENT BACKGROUND GLOW */}
            <div
              className={`absolute top-0 right-0 w-96 h-96 rounded-full blur-3xl pointer-events-none opacity-10 ${
                selectedFuturesSide === 'LONG' ? 'bg-emerald-500' : 'bg-rose-500'
              }`}
            />

            {/* HEADER: TITLE, BADGES, AND LONG/SHORT SWITCHER */}
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-4 pb-3.5 border-b border-slate-800/80 relative z-10">
              <div>
                <div className="flex flex-wrap items-center gap-2 mb-1">
                  <span className="px-2.5 py-0.5 rounded-full text-[10px] font-extrabold uppercase tracking-wider bg-amber-500/15 text-amber-300 border border-amber-500/30 flex items-center gap-1.5">
                    <LucideIcon name="zap" className="w-3 h-3 text-amber-400" />
                    KONTRAK FUTURES PERPETUAL (LEVERAGE)
                  </span>
                  {futuresContract?.has_futures && (
                    <>
                      <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-slate-800 text-slate-300 border border-slate-700">
                        {futuresContract.exchange || 'Gate.io USDT Perpetual'}
                      </span>
                      <span className="px-2.5 py-0.5 rounded-full text-[10px] font-black bg-cyan-500/15 text-cyan-300 border border-cyan-500/30">
                        {activeFuturesPlan?.margin_mode || 'ISOLATED'} MARGIN
                      </span>
                    </>
                  )}
                </div>
                <h2 className="text-base sm:text-lg font-black text-white flex items-center gap-2">
                  <span>Trading Plan Futures ({futuresContract?.contract_name || `${data.code}_USDT`})</span>
                  {futuresContract?.has_futures && (
                    <span className="text-xs font-bold text-slate-400">
                      • Horison: <strong className="text-white">{activeFuturesPlan?.timeframe_label}</strong>
                    </span>
                  )}
                </h2>
                <p className="text-xs text-slate-400 mt-0.5">
                  {futuresContract?.has_futures
                    ? activeFuturesPlan?.bias_description || 'Rekomendasi setup posisi LONG & SHORT dengan batas Stop Loss anti-likuidasi.'
                    : 'Pemeriksaan ketersediaan instrumen derivatif perpetual bursa global.'}
                </p>
              </div>

              {/* ACTION BUTTONS & DIRECTION TOGGLES (IF HAS FUTURES) */}
              {futuresContract?.has_futures && (
                <div className="flex flex-wrap items-center gap-2">
                  {/* SYSTEM BIAS NOTIFICATION */}
                  <div className="hidden sm:flex flex-col text-right pr-2 border-r border-slate-800">
                    <span className="text-[10px] uppercase font-bold text-slate-400">Sinyal Sistem</span>
                    <span className={`text-xs font-black ${
                      activeFuturesPlan?.primary_bias === 'LONG' ? 'text-emerald-400' : 'text-rose-400'
                    }`}>
                      {activeFuturesPlan?.primary_bias} ({activeFuturesPlan?.recommended_leverage}x)
                    </span>
                  </div>

                  {/* LONG / SHORT TAB TOGGLE */}
                  <div className="bg-slate-900/90 p-1 rounded-xl border border-slate-800 flex items-center gap-1">
                    <button
                      type="button"
                      onClick={() => setFuturesSideOverride('LONG')}
                      className={`px-3 py-1.5 rounded-lg text-xs font-black transition flex items-center gap-1.5 ${
                        selectedFuturesSide === 'LONG'
                          ? 'bg-emerald-500 text-slate-950 shadow-md shadow-emerald-500/20'
                          : 'text-slate-400 hover:text-emerald-300 hover:bg-slate-800/80'
                      }`}
                    >
                      <span className="w-2 h-2 rounded-full bg-emerald-400 inline-block animate-pulse" />
                      LONG SETUP {activeFuturesPlan?.primary_bias === 'LONG' && '★'}
                    </button>
                    <button
                      type="button"
                      onClick={() => setFuturesSideOverride('SHORT')}
                      className={`px-3 py-1.5 rounded-lg text-xs font-black transition flex items-center gap-1.5 ${
                        selectedFuturesSide === 'SHORT'
                          ? 'bg-rose-500 text-white shadow-md shadow-rose-500/20'
                          : 'text-slate-400 hover:text-rose-300 hover:bg-slate-800/80'
                      }`}
                    >
                      <span className="w-2 h-2 rounded-full bg-rose-400 inline-block animate-pulse" />
                      SHORT SETUP {activeFuturesPlan?.primary_bias === 'SHORT' && '★'}
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* IF NO FUTURES CONTRACT EXISTS */}
            {!futuresContract?.has_futures ? (
              <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 text-center my-2">
                <div className="w-12 h-12 rounded-2xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center mx-auto mb-3">
                  <LucideIcon name="alert-circle" className="w-6 h-6 text-amber-400" />
                </div>
                <h3 className="text-sm font-black text-white">Kontrak Futures Perpetual Belum Tersedia</h3>
                <p className="text-xs text-slate-400 max-w-lg mx-auto mt-1.5">
                  {futuresContract?.message || `Aset ${data.code} saat ini belum diperdagangkan dalam instrumen kontrak derivatif USDT Perpetual di bursa utama.`}
                </p>
                <div className="mt-3 inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-800/80 text-cyan-300 text-xs font-bold border border-slate-700">
                  <LucideIcon name="info" className="w-3.5 h-3.5" />
                  Gunakan Trading Plan Spot di atas untuk eksekusi beli & jual aset ini.
                </div>
              </div>
            ) : currentFuturesSetup ? (
              <>
                {/* CONTRACT REAL-TIME METRICS BAR: FUNDING RATE, MARK PRICE, SENTIMENT */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 mb-4 text-xs">
                  <div className="bg-slate-900/80 border border-slate-800/90 rounded-xl p-3">
                    <span className="text-[10px] text-slate-400 block font-medium">Mark Price / Index Price</span>
                    <span className="text-sm font-black text-white mt-0.5 block">
                      {formatCryptoUsd(futuresContract.mark_price)}
                    </span>
                    <span className="text-[10px] text-slate-500 block">
                      Index: {formatCryptoUsd(futuresContract.index_price)}
                    </span>
                  </div>

                  <div className="bg-slate-900/80 border border-slate-800/90 rounded-xl p-3">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] text-slate-400 block font-medium">Funding Rate (8 Jam)</span>
                      <span className="text-[10px] text-slate-500">{futuresContract.next_funding_time}</span>
                    </div>
                    <span className={`text-sm font-black mt-0.5 block ${
                      Number(futuresContract.funding_rate_pct) >= 0 ? 'text-emerald-400' : 'text-rose-400'
                    }`}>
                      {Number(futuresContract.funding_rate_pct) >= 0 ? '+' : ''}{futuresContract.funding_rate_pct}%
                    </span>
                    <span className="text-[10px] text-slate-400 block truncate" title={futuresContract.funding_sentiment}>
                      {futuresContract.funding_sentiment}
                    </span>
                  </div>

                  <div className="bg-slate-900/80 border border-slate-800/90 rounded-xl p-3">
                    <span className="text-[10px] text-slate-400 block font-medium">Rekomendasi Leverage</span>
                    <div className="flex items-baseline gap-1 mt-0.5">
                      <span className="text-sm font-black text-cyan-400">
                        {activeFuturesPlan.recommended_leverage}x
                      </span>
                      <span className="text-[10px] text-slate-400">
                        (Aman maks {activeFuturesPlan.max_safe_leverage}x)
                      </span>
                    </div>
                    <span className="text-[10px] text-slate-500 block">
                      Bursa Max: {futuresContract.leverage_max}x
                    </span>
                  </div>

                  <div className="bg-slate-900/80 border border-slate-800/90 rounded-xl p-3">
                    <div className="flex justify-between text-[10px] text-slate-400 mb-1">
                      <span>Rasio Trader:</span>
                      <span className="font-bold text-emerald-400">{futuresContract.long_ratio_pct}% L</span>
                      <span className="font-bold text-rose-400">{futuresContract.short_ratio_pct}% S</span>
                    </div>
                    <div className="w-full h-2 bg-rose-500/40 rounded-full overflow-hidden flex">
                      <div
                        style={{ width: `${futuresContract.long_ratio_pct}%` }}
                        className="bg-emerald-500 h-full transition-all"
                      />
                    </div>
                    <span className="text-[10px] text-slate-500 block mt-1">
                      Sentimen Posisi Akun Terbuka
                    </span>
                  </div>
                </div>

                {/* 4 ACTIONABLE FUTURES CARDS: ENTRY, TP1, TP2, STOP LOSS + LIQ */}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
                  {/* 1. ZONA ENTRY FUTURES */}
                  <div className={`bg-slate-900/90 border rounded-xl p-4 transition ${
                    selectedFuturesSide === 'LONG' ? 'border-emerald-500/50 shadow-sm' : 'border-rose-500/50 shadow-sm'
                  }`}>
                    <div className="flex items-center justify-between">
                      <span className={`text-[11px] font-black uppercase ${
                        selectedFuturesSide === 'LONG' ? 'text-emerald-400' : 'text-rose-400'
                      }`}>
                        1. Zona Entry ({selectedFuturesSide})
                      </span>
                      <span className={`px-2 py-0.5 rounded text-[10px] font-black ${
                        selectedFuturesSide === 'LONG' ? 'bg-emerald-500/20 text-emerald-300' : 'bg-rose-500/20 text-rose-300'
                      }`}>
                        {selectedFuturesSide}
                      </span>
                    </div>
                    <div className="text-lg font-black text-white mt-2">
                      {formatCryptoUsd(currentFuturesSetup.entry_zone_low_usd)} – {formatCryptoUsd(currentFuturesSetup.entry_zone_high_usd)}
                    </div>
                    <p className="text-[11px] text-slate-300 font-semibold mt-0.5">
                      {formatIdr(currentFuturesSetup.entry_zone_low_idr)} – {formatIdr(currentFuturesSetup.entry_zone_high_idr)}
                    </p>
                    <p className="text-[11px] text-slate-400 mt-1.5 leading-relaxed">
                      {currentFuturesSetup.action_desc}
                    </p>
                  </div>

                  {/* 2. TARGET PROFIT 1 */}
                  <div className="bg-slate-900/90 border border-emerald-500/40 rounded-xl p-4">
                    <div className="flex items-center justify-between">
                      <span className="text-[11px] font-extrabold uppercase text-emerald-400">2. Target Profit 1 (TP 1)</span>
                      <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 text-[10px] font-black">
                        +{currentFuturesSetup.tp_1_leveraged_roi_pct}% ROE
                      </span>
                    </div>
                    <div className="text-xl font-black text-emerald-400 mt-2">
                      {formatCryptoUsd(currentFuturesSetup.tp_1_usd)}
                    </div>
                    <p className="text-[11px] text-slate-300 font-semibold mt-0.5">
                      ≈ {formatIdr(currentFuturesSetup.tp_1_idr)}{' '}
                      <span className="text-[10px] text-slate-500 font-normal">
                        (Spot +{currentFuturesSetup.tp_1_pct}%)
                      </span>
                    </p>
                    <p className="text-[11px] text-slate-400 mt-1.5">
                      Amankan 50% profit & geser Stop Loss ke Break-Even (BEP).
                    </p>
                  </div>

                  {/* 3. TARGET PROFIT 2 */}
                  <div className="bg-slate-900/90 border border-emerald-500/40 rounded-xl p-4">
                    <div className="flex items-center justify-between">
                      <span className="text-[11px] font-extrabold uppercase text-emerald-400">3. Target Profit 2 (TP 2)</span>
                      <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 text-[10px] font-black">
                        +{currentFuturesSetup.tp_2_leveraged_roi_pct}% ROE
                      </span>
                    </div>
                    <div className="text-xl font-black text-emerald-400 mt-2">
                      {formatCryptoUsd(currentFuturesSetup.tp_2_usd)}
                    </div>
                    <p className="text-[11px] text-slate-300 font-semibold mt-0.5">
                      ≈ {formatIdr(currentFuturesSetup.tp_2_idr)}{' '}
                      <span className="text-[10px] text-slate-500 font-normal">
                        (Spot +{currentFuturesSetup.tp_2_pct}%)
                      </span>
                    </p>
                    <p className="text-[11px] text-slate-400 mt-1.5">
                      Target swing optimal {activeFuturesPlan.timeframe_label} untuk take profit penuh / runner.
                    </p>
                  </div>

                  {/* 4. STOP LOSS & ESTIMASI LIKUIDASI */}
                  <div className="bg-slate-900/90 border border-rose-500/40 rounded-xl p-4">
                    <div className="flex items-center justify-between">
                      <span className="text-[11px] font-extrabold uppercase text-rose-400">4. Stop Loss & Likuidasi</span>
                      <span className="px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 text-[10px] font-black">
                        {currentFuturesSetup.stop_loss_leveraged_risk_pct}% ROE
                      </span>
                    </div>
                    <div className="text-xl font-black text-rose-400 mt-2">
                      {formatCryptoUsd(currentFuturesSetup.stop_loss_usd)}
                    </div>
                    <p className="text-[11px] text-slate-300 font-semibold mt-0.5">
                      ≈ {formatIdr(currentFuturesSetup.stop_loss_idr)}{' '}
                      <span className="text-[10px] text-slate-500 font-normal">
                        ({currentFuturesSetup.stop_loss_pct}%)
                      </span>
                    </p>
                    <div className="mt-2 pt-2 border-t border-slate-800 text-[11px]">
                      <span className="text-amber-400 font-bold block">
                        Est. Likuidasi ({activeFuturesPlan.recommended_leverage}x): {formatCryptoUsd(currentFuturesSetup.est_liquidation_price_usd)}
                      </span>
                      <span className="text-slate-400 text-[10px] block mt-0.5">
                        Buffer aman: {currentFuturesSetup.liquidation_buffer_pct}% dari SL
                      </span>
                    </div>
                  </div>
                </div>

                {/* SAFETY NOTE & RISK REWARD FOOTER */}
                <div className="mt-3.5 p-3 rounded-xl bg-slate-900/80 border border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs">
                  <div className="flex items-start gap-2">
                    <LucideIcon name="shield-alert" className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                    <span className="text-slate-300 text-[11px]">
                      <strong className="text-white">Proteksi Likuidasi:</strong> {currentFuturesSetup.sl_safety_note}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 shrink-0 text-[11px] font-extrabold text-cyan-300">
                    <span>Net R/R: {currentFuturesSetup.risk_reward_ratio}</span>
                    <span className="text-slate-600">•</span>
                    <span>Volatilitas ATR: {activeFuturesPlan.atr_volatility_pct}%</span>
                  </div>
                </div>
              </>
            ) : null}
          </div>

          {/* SECTION 3: SIMULASI MODAL SPOT (RUPIAH) & TOKENOMICS / STAKING */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* SPOT BUDGET & STAKING SIMULATOR */}
            <div className="bg-[#0B0E14] border border-slate-800/80 rounded-2xl p-5">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-black text-white flex items-center gap-2">
                  <LucideIcon name="calculator" className="w-4 h-4 text-cyan-400" />
                  Simulasi Modal Beli Spot & Estimasi Cuan (Rupiah)
                </h3>
                <span className="text-[11px] text-slate-400 font-bold">
                  Fee Bursa 0.10% + Pajak 0.21%
                </span>
              </div>

              <div className="flex flex-wrap items-center gap-2 bg-slate-900/80 border border-slate-800 rounded-xl p-3">
                <label className="text-xs font-bold text-slate-300">Modal Beli (Rp):</label>
                <input
                  type="number"
                  min={100000}
                  step={500000}
                  value={budgetIdr}
                  onChange={(e) => setBudgetIdr(Math.max(100000, parseInt(e.target.value || '1000000', 10)))}
                  className="w-36 bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-1 text-sm font-black text-white outline-none focus:border-cyan-500"
                />
                <div className="flex gap-1 ml-auto">
                  {[1000000, 5000000, 10000000, 25000000].map((preset) => (
                    <button
                      key={preset}
                      type="button"
                      onClick={() => setBudgetIdr(preset)}
                      className={`px-2 py-1 rounded text-[10px] font-extrabold border ${
                        budgetIdr === preset
                          ? 'bg-cyan-500 text-slate-950 border-cyan-400'
                          : 'bg-slate-800 text-slate-300 border-slate-700 hover:text-white'
                      }`}
                    >
                      {preset / 1000000}Jt
                    </button>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3 mt-3">
                <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-3">
                  <span className="text-[10px] text-slate-400 block">Estimasi Koin Didapat</span>
                  <span className="text-sm sm:text-base font-black text-white mt-0.5 block">
                    {acquiredCoins.toFixed(acquiredCoins >= 1 ? 4 : 6)} {data.code}
                  </span>
                </div>
                <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-3">
                  <span className="text-[10px] text-slate-400 block">Hasil Staking / Tahun ({tok?.staking_apr_pct || 0}% APR)</span>
                  <span className="text-sm sm:text-base font-black text-cyan-400 mt-0.5 block">
                    {estAnnualStakingIdr > 0 ? `+${formatIdr(estAnnualStakingIdr)}` : 'Rp 0 (Non-PoS)'}
                  </span>
                  {estAnnualStakingCoins > 0 && (
                    <span className="text-[10px] text-slate-400 block">
                      ≈ +{estAnnualStakingCoins.toFixed(4)} {data.code}/thn
                    </span>
                  )}
                </div>
                <div className="bg-emerald-500/10 border border-emerald-500/30 rounded-xl p-3">
                  <span className="text-[10px] text-emerald-300 block">Potensi Profit Bersih di TP 1 / TP 2</span>
                  <span className="text-xs sm:text-sm font-black text-emerald-400 mt-0.5 block">
                    +{formatIdr(netTp1ProfitIdr)} s/d +{formatIdr(netTp2ProfitIdr)}
                  </span>
                </div>
                <div className="bg-rose-500/10 border border-rose-500/30 rounded-xl p-3">
                  <span className="text-[10px] text-rose-300 block">Risiko Rugi Bersih di Stop Loss</span>
                  <span className="text-xs sm:text-sm font-black text-rose-400 mt-0.5 block">
                    {formatIdr(netSlLossIdr)} ({activePlan.net_stop_loss_pct}%)
                  </span>
                </div>
              </div>
            </div>

            {/* TOKENOMICS, SUPPLY & STAKING INTELLIGENCE */}
            <div className="bg-[#0B0E14] border border-slate-800/80 rounded-2xl p-5 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-black text-white flex items-center gap-2">
                    <LucideIcon name="layers" className="w-4 h-4 text-emerald-400" />
                    Tokenomics, Suplai & Risiko Dilusi (FDV)
                  </h3>
                  <span className="px-2.5 py-0.5 rounded-full text-[10px] font-extrabold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
                    {tok?.consensus}
                  </span>
                </div>

                <div className="grid grid-cols-3 gap-2.5">
                  <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-3">
                    <span className="text-[10px] text-slate-400 block">Market Cap</span>
                    <span className="text-sm font-black text-white mt-0.5 block">
                      {tok?.market_cap_usd_b ? `$${tok.market_cap_usd_b} B` : 'N/A'}
                    </span>
                    {tok?.market_cap_idr_t && (
                      <span className="text-[10px] text-slate-400 block">Rp {tok.market_cap_idr_t} Triliun</span>
                    )}
                  </div>
                  <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-3">
                    <span className="text-[10px] text-slate-400 block">FDV & Rasio FDV/MCap</span>
                    <span className="text-sm font-black text-cyan-400 mt-0.5 block">
                      {tok?.fdv_usd_b ? `$${tok.fdv_usd_b} B (${tok.fdv_to_mcap_ratio}x)` : 'N/A'}
                    </span>
                  </div>
                  <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-3">
                    <span className="text-[10px] text-slate-400 block">Suplai Beredar</span>
                    <span className="text-sm font-black text-emerald-400 mt-0.5 block">
                      {tok?.circulating_pct ? `${tok.circulating_pct}%` : '100%'}
                    </span>
                    <span className="text-[10px] text-slate-400 block">
                      Inflasi: {tok?.annual_inflation_pct !== null ? `${tok?.annual_inflation_pct}%/thn` : 'N/A'}
                    </span>
                  </div>
                </div>

                <div className="mt-3 p-3 rounded-xl bg-slate-900/60 border border-slate-800 text-xs space-y-1">
                  <div>
                    <span className="text-slate-400">Risiko Unlock / Dilusi: </span>
                    <strong className="text-white">{tok?.unlock_dilution_risk}</strong>
                  </div>
                  <div>
                    <span className="text-slate-400">Mekanisme Burn / Halving: </span>
                    <span className="text-slate-200">{tok?.burn_mechanism}</span>
                  </div>
                  <div>
                    <span className="text-slate-400">Staking / Yield: </span>
                    <span className="text-emerald-300 font-semibold">{tok?.staking_mechanism}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* SECTION 4: INDIKATOR TEKNIKAL & GRAFIK 30 HARI */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* TECHNICAL INDICATORS */}
            <div className="bg-[#0B0E14] border border-slate-800/80 rounded-2xl p-5">
              <h3 className="text-sm font-black text-white flex items-center gap-2 mb-3">
                <LucideIcon name="Sliders" className="w-4 h-4 text-purple-400" />
                Indikator Teknikal Lengkap (SMA, EMA, RSI, MACD, Bollinger & ATR)
              </h3>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5 text-xs">
                <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-3">
                  <span className="text-[10px] text-slate-400 block">RSI (14) Wilder</span>
                  <span className="text-base font-black text-white mt-0.5 block">{tech?.rsi_14}</span>
                  <span className="text-[10px] text-cyan-400 font-bold">{tech?.rsi_status}</span>
                </div>
                <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-3">
                  <span className="text-[10px] text-slate-400 block">SMA-20 & EMA-20</span>
                  <span className="text-sm font-black text-white mt-0.5 block">{formatCryptoUsd(tech?.sma_20)}</span>
                  <span className="text-[10px] text-slate-400">EMA-20: {formatCryptoUsd(tech?.ema_20)}</span>
                </div>
                <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-3">
                  <span className="text-[10px] text-slate-400 block">SMA-50 & SMA-200</span>
                  <span className="text-sm font-black text-white mt-0.5 block">{formatCryptoUsd(tech?.sma_50)}</span>
                  <span className="text-[10px] text-slate-400">SMA-200: {formatCryptoUsd(tech?.sma_200)}</span>
                </div>
                <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-3">
                  <span className="text-[10px] text-slate-400 block">MACD (12, 26, 9)</span>
                  <span className="text-sm font-black text-white mt-0.5 block">{tech?.macd}</span>
                  <span className={`text-[10px] font-bold ${(tech?.macd_histogram || 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                    Hist: {tech?.macd_histogram}
                  </span>
                </div>
                <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-3">
                  <span className="text-[10px] text-slate-400 block">Bollinger Bands (20,2)</span>
                  <span className="text-xs font-black text-white mt-0.5 block">
                    {formatCryptoUsd(tech?.bollinger?.lower)} – {formatCryptoUsd(tech?.bollinger?.upper)}
                  </span>
                  <span className="text-[10px] text-slate-400">Bandwidth: {tech?.bollinger?.bandwidth_pct}%</span>
                </div>
                <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-3">
                  <span className="text-[10px] text-slate-400 block">ATR-14 & Volume Ratio</span>
                  <span className="text-sm font-black text-white mt-0.5 block">
                    {formatCryptoUsd(tech?.atr_14_usd)} ({tech?.atr_pct}%)
                  </span>
                  <span className="text-[10px] text-cyan-400 font-bold">Vol Ratio: {tech?.volume_ratio}x MA20</span>
                </div>
              </div>
            </div>

            {/* 30-DAY PRICE TREND CHART */}
            <div className="bg-[#0B0E14] border border-slate-800/80 rounded-2xl p-5 flex flex-col justify-between">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-black text-white flex items-center gap-2">
                  <LucideIcon name="bar-chart-2" className="w-4 h-4 text-cyan-400" />
                  Grafik Pergerakan Harga 30 Hari Terakhir ({data.code}/USD)
                </h3>
                <span className="text-[11px] text-slate-400">Hover batang untuk detail</span>
              </div>

              {(() => {
                const candles = data.recent_candles || [];
                if (!candles.length) return <div className="text-xs text-slate-500">Data candle tidak tersedia</div>;
                const closes = candles.map((c: any) => Number(c.close));
                const minC = Math.min(...closes);
                const maxC = Math.max(...closes);
                const span = Math.max(1e-9, maxC - minC);
                return (
                  <div>
                    <div className="h-36 flex items-end gap-1 pt-4 px-1">
                      {candles.map((c: any, idx: number) => {
                        const prev = idx > 0 ? Number(candles[idx - 1].close) : Number(c.open);
                        const isUp = Number(c.close) >= prev;
                        const hPct = Math.max(12, Math.round(((Number(c.close) - minC) / span) * 100));
                        return (
                          <div
                            key={c.date + idx}
                            className="flex-1 flex flex-col items-center group relative h-full justify-end"
                          >
                            <div
                              style={{ height: `${hPct}%` }}
                              className={`w-full rounded-t transition-all ${
                                isUp ? 'bg-emerald-500/80 group-hover:bg-emerald-400' : 'bg-rose-500/80 group-hover:bg-rose-400'
                              }`}
                            />
                            <div className="opacity-0 group-hover:opacity-100 pointer-events-none absolute -top-8 left-1/2 -translate-x-1/2 bg-slate-950 border border-slate-700 text-[10px] text-white px-2 py-0.5 rounded whitespace-nowrap z-20 shadow">
                              {c.date}: {formatCryptoUsd(c.close)}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                    <div className="flex justify-between text-[10px] text-slate-400 mt-2 pt-2 border-t border-slate-800/80">
                      <span>Terendah 30H: <strong className="text-slate-200">{formatCryptoUsd(minC)}</strong></span>
                      <span>Tertinggi 30H: <strong className="text-slate-200">{formatCryptoUsd(maxC)}</strong></span>
                    </div>
                  </div>
                );
              })()}
            </div>
          </div>

          {/* SECTION 5: BERITA KRIPTO TERKAIT */}
          {data.news_articles && data.news_articles.length > 0 && (
            <div className="bg-[#0B0E14] border border-slate-800/80 rounded-2xl p-5">
              <h3 className="text-sm font-black text-white flex items-center gap-2 mb-3">
                <LucideIcon name="newspaper" className="w-4 h-4 text-cyan-400" />
                Berita & Sentimen Pasar Kripto Terbaru ({data.code})
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {data.news_articles.slice(0, 3).map((art: any, idx: number) => (
                  <a
                    key={idx}
                    href={art.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="bg-slate-900/70 hover:bg-slate-900 border border-slate-800 hover:border-cyan-500/40 rounded-xl p-3.5 transition flex flex-col justify-between"
                  >
                    <div>
                      <div className="flex items-center justify-between text-[10px] text-slate-400 mb-1">
                        <span className="font-bold text-cyan-400">{art.source}</span>
                        <span>{art.published_at}</span>
                      </div>
                      <h4 className="text-xs font-bold text-white line-clamp-2">{art.title}</h4>
                    </div>
                    <span className="text-[10px] text-cyan-400 font-bold mt-2 inline-flex items-center gap-1">
                      Baca Selengkapnya →
                    </span>
                  </a>
                ))}
              </div>
            </div>
          )}
        </>
      ) : null}
    </div>
  );
}
