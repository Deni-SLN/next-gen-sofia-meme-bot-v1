import React, { useState, useEffect } from 'react';
import { api, formatIdr } from '@/lib/api';
import { LucideIcon } from '@/components/LucideIcon';
import { TradingChart } from '@/components/TradingChart';
import { TradingViewWidget } from '@/components/TradingViewWidget';
import { TechnicalIndicatorsCard } from '@/components/TechnicalIndicatorsCard';
import { useUltrawide } from '@/lib/useUltrawide';

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
  const [chartMode, setChartMode] = useState<'tradingview' | 'quantitative'>('tradingview');
  const [focusedIndicator, setFocusedIndicator] = useState<'ALL' | 'SNR' | 'SMC' | 'EMA200' | 'ICHIMOKU' | 'FIBONACCI'>('SNR');
  const isUltrawide = useUltrawide();

  const handleSelectIndicator = (ind: 'ALL' | 'SNR' | 'SMC' | 'EMA200' | 'ICHIMOKU' | 'FIBONACCI') => {
    setChartMode('quantitative');
    setFocusedIndicator(ind);
    const el = document.getElementById('chart-container-root');
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  };

  const loadCrypto = async (sym: string, force: boolean = false, tf: string = selectedTimeframe) => {
    const trimmed = (sym || 'BTC').trim();
    const clean = trimmed.length >= 30 ? trimmed : trimmed.toUpperCase();
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
      setError(err?.message || 'Gagal memuat analisis crypto. Periksa koneksi backend.');
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
      loadCrypto(queryInput, false, selectedTimeframe);
    }
  };

  const handleTimeframeChange = (tf: string) => {
    setSelectedTimeframe(tf);
    loadCrypto(activeSymbol, false, tf);
  };

  const calculateCustomRisk = async () => {
    if (!data || !activePlan) return;
    setRiskLoading(true);
    try {
      const res = await api.calculateCryptoRisk({
        capital_idr: riskCapitalIdr,
        entry_price_usd: Number(activePlan.entry_zone_high_usd || data.current_price_usd || 1),
        stop_loss_usd: Number(activePlan.stop_loss_usd || 1),
        target_price_usd: Number(activePlan.tp_1_usd || 1),
        max_risk_pct: riskPct,
      });
      setRiskResult(res);
    } catch (err: any) {
      console.error(err);
    } finally {
      setRiskLoading(false);
    }
  };

  const popularList = [
    { code: 'BTC', name: 'Bitcoin' },
    { code: 'ETH', name: 'Ethereum' },
    { code: 'SOL', name: 'Solana' },
    { code: 'BNB', name: 'BNB' },
    { code: 'XRP', name: 'XRP' },
    { code: 'DOGE', name: 'Dogecoin' },
    { code: 'ADA', name: 'Cardano' },
    { code: 'AVAX', name: 'Avalanche' },
    { code: 'LINK', name: 'Chainlink' },
    { code: 'TON', name: 'Toncoin' },
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
              Mendukung ribuan koin kripto &amp; altcoins global (Binance Vision + DexScreener + Yahoo). Ketik simbol koin apapun (<span className="text-white font-semibold">BTC, APT, TIA, JUP, SEI, TAO, WIF, NEAR, KAS, dll</span>) untuk melihat Analisis Real-Time &amp; Indikator.
            </p>

            {/* LIVE BTC / ETH / SOL PULSE BAR */}
            {pulse?.top_movers && pulse.top_movers.length > 0 && (
              <div className="mt-3 flex items-center gap-2 overflow-x-auto no-scrollbar py-1">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 shrink-0">
                  Denyut Pasar:
                </span>
                {pulse.top_movers.map((m: any) => (
                  <button
                    key={m.code}
                    type="button"
                    onClick={() => {
                      setQueryInput(m.code);
                      loadCrypto(m.code, false, selectedTimeframe);
                    }}
                    className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-900/90 border border-slate-800 hover:border-cyan-500/50 text-xs font-semibold shrink-0 transition"
                  >
                    <span className="text-white font-bold">{m.code}</span>
                    <span className="text-slate-300 font-mono">{formatCryptoUsd(m.price_usd)}</span>
                    <span
                      className={`text-[10px] font-extrabold ${
                        m.change_pct >= 0 ? 'text-emerald-400' : 'text-rose-400'
                      }`}
                    >
                      {m.change_pct >= 0 ? '+' : ''}
                      {m.change_pct}%
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* SEARCH BOX & POPULAR SHORTCUTS */}
          <form onSubmit={handleSearch} className="w-full lg:w-auto flex items-center gap-2 shrink-0">
            <div className="relative flex-1 min-w-0 sm:flex-initial">
              <input
                type="text"
                value={queryInput}
                onChange={(e) => {
                  const val = e.target.value;
                  setQueryInput(val.trim().length >= 30 ? val.trim() : val.toUpperCase());
                }}
                placeholder="Ketik koin atau CA Pump.fun (cth: WIF, POPCAT, ...pump)..."
                className="w-full sm:w-64 bg-slate-950/90 border border-slate-700/80 rounded-xl px-3 py-2 text-xs sm:text-sm font-bold text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500 transition"
              />
            </div>
            <button
              type="submit"
              disabled={loading || refreshing}
              className="px-3.5 sm:px-4 py-2 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 text-xs font-black transition flex items-center gap-1.5 shadow-md shadow-cyan-500/20 disabled:opacity-50 shrink-0"
            >
              <LucideIcon name="zap" className="w-3.5 h-3.5" />
              Analisa
            </button>
            <button
              type="button"
              onClick={() => loadCrypto(activeSymbol, true, selectedTimeframe)}
              disabled={loading || refreshing}
              className="p-2 rounded-xl bg-slate-800/90 hover:bg-slate-700 text-slate-200 border border-slate-700 transition shrink-0"
              title="Refresh Harga Kripto"
            >
              <LucideIcon name="refresh-cw" className={`w-4 h-4 ${refreshing ? 'animate-spin text-cyan-400' : ''}`} />
            </button>
          </form>
        </div>

        {/* POPULAR CRYPTO QUICK BUTTONS (MAX 10 COINS) */}
        <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center gap-1.5 overflow-x-auto no-scrollbar">
          <span className="text-[11px] font-bold text-slate-400 mr-1 shrink-0">Koin Populer:</span>
          {popularList.slice(0, 10).map((item: any) => {
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
          <span className="text-[11px] text-slate-500 ml-2 shrink-0">
            • Koin lainnya ketik manual di kolom pencarian atas
          </span>
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
        <div className="space-y-5">
          {/* ANTI-HONEYPOT & TRADING SAFETY SHIELD BANNER */}
          {data.security_shield && (
            <div
              className={`rounded-2xl p-3.5 border flex flex-wrap items-center justify-between gap-3 ${
                data.security_shield.is_safe_to_trade && !data.security_shield.honeypot
                  ? 'bg-emerald-950/30 border-emerald-500/40 text-emerald-200'
                  : 'bg-rose-950/50 border-rose-500/50 text-rose-200'
              }`}
            >
              <div className="flex items-center gap-3">
                <span className="text-lg">
                  {data.security_shield.is_safe_to_trade && !data.security_shield.honeypot ? '🛡️' : '🚨'}
                </span>
                <div>
                  <div className="text-xs sm:text-sm font-black uppercase tracking-wide">
                    {data.security_shield.is_safe_to_trade && !data.security_shield.honeypot
                      ? `STATUS KEAMANAN TRADING (${data.code}): AMAN UNTUK DI-TRADING • BEBAS HONEYPOT`
                      : `PERINGATAN KERAS (${data.code}): DILARANG TRADING • POTENSI HONEYPOT / RISIKO KONTRAK!`}
                  </div>
                  <div className="text-[11px] opacity-85 mt-0.5 font-mono">
                    {data.security_shield.verdict} • Safety Score: {data.security_shield.safety_score ?? 95}/100
                  </div>
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2 text-[10px] font-mono font-bold">
                <span className="px-2 py-1 rounded bg-slate-900/80 border border-slate-700 text-emerald-300">
                  Mint: {data.security_shield.mint_revoked !== false ? '✅ Dicabut' : '❌ Aktif'}
                </span>
                <span className="px-2 py-1 rounded bg-slate-900/80 border border-slate-700 text-emerald-300">
                  Freeze: {data.security_shield.freeze_revoked !== false ? '✅ Dicabut' : '❌ Aktif'}
                </span>
                <span className="px-2 py-1 rounded bg-slate-900/80 border border-slate-700 text-cyan-300">
                  Honeypot: {data.security_shield.honeypot ? '🚨 TERDETEKSI' : '✅ AMAN (Sellable)'}
                </span>
              </div>
            </div>
          )}

          {/* TOP HERO STATS:
              - Mode Biasa: Menampilkan 3 Card (Harga, Performa 52W, Keputusan Quick).
              - Mode Layar Lebar: Menampilkan 4 Card menyamping (ditambah Ringkasan Futures Perpetual).
          */}
          <div className={isUltrawide ? "grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4" : "grid grid-cols-1 lg:grid-cols-3 gap-4"}>
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

            {/* 4. FUTURES PERPETUAL QUICK HIGHLIGHT (TAMPIL DI MODE LAYAR LEBAR SEHINGGA MENJADI LEBIH DARI 3 CARD) */}
            {isUltrawide && (
              <div className="bg-[#0B0E14] border border-amber-500/40 rounded-2xl p-5 flex flex-col justify-between relative overflow-hidden shadow-lg">
                <div>
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-black uppercase tracking-wider text-amber-300 flex items-center gap-1.5">
                      <LucideIcon name="zap" className="w-3.5 h-3.5 text-amber-400" />
                      FUTURES PERPETUAL
                    </span>
                    <span className={`px-2 py-0.5 rounded text-[10px] font-black border ${
                      selectedFuturesSide === 'LONG'
                        ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                        : 'bg-rose-500/20 text-rose-300 border-rose-500/40'
                    }`}>
                      {selectedFuturesSide} SETUP
                    </span>
                  </div>

                  <div className="mt-2.5 p-3 rounded-xl bg-slate-900/90 border border-slate-800">
                    <div className="flex justify-between items-baseline">
                      <span className="text-[10px] text-slate-400">Bias &amp; Leverage:</span>
                      <span className="text-xs font-black text-white">
                        {activeFuturesPlan?.primary_bias} ({activeFuturesPlan?.recommended_leverage}x Safe)
                      </span>
                    </div>
                    <div className="flex justify-between items-baseline mt-1">
                      <span className="text-[10px] text-slate-400">Funding Rate 8J:</span>
                      <span className={`text-xs font-bold ${Number(futuresContract?.funding_rate_pct || 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                        {Number(futuresContract?.funding_rate_pct || 0) >= 0 ? '+' : ''}{futuresContract?.funding_rate_pct || '0.01'}%
                      </span>
                    </div>
                    <div className="flex justify-between items-baseline mt-1 pt-1 border-t border-slate-800 text-[11px]">
                      <span className="text-slate-400">Target TP1:</span>
                      <span className="font-extrabold text-emerald-400">
                        {formatCryptoUsd(currentFuturesSetup?.tp_1_usd)} (+{currentFuturesSetup?.tp_1_leveraged_roi_pct}% ROE)
                      </span>
                    </div>
                  </div>
                </div>

                <div className="mt-3 pt-2 border-t border-slate-800/80 flex items-center justify-between text-[11px]">
                  <span className="text-slate-400">SL: <strong className="text-rose-400">{formatCryptoUsd(currentFuturesSetup?.stop_loss_usd)}</strong></span>
                  <span className="text-cyan-300 font-bold">R/R {currentFuturesSetup?.risk_reward_ratio || '1:2.5'}</span>
                </div>
              </div>
            )}
          </div>

          {/* MAIN CONTENT AREA:
              - JIKA MODE LAYAR LEBAR (isUltrawide): CARD YANG DARI BAWAH DIPINDAHKAN KE SAMPING SEHINGGA TAMPIL LEBIH DARI 3 CARD SEKALIGUS!
              - JIKA MODE BIASA (DEFAULT): CARD MENAMPILKAN URUTAN VERTIKAL (HARUS SCROLL KE BAWAH)
          */}
          {isUltrawide ? (
            <div className="grid grid-cols-1 xl:grid-cols-12 gap-5 items-start">
              {/* Kolom Kiri Lebar: Chart Interaktif & Analisa Teknikal (7 Kolom) */}
              <div className="xl:col-span-7 space-y-5">
                {/* 1. INTERACTIVE CANDLESTICK CHART & TECHNICAL INDICATORS AUDIT */}
                <div id="chart-container-root" className="space-y-4">
                  <div className="flex flex-wrap items-center justify-between gap-2 bg-obsidian-900/80 p-2.5 rounded-xl border border-obsidian-800">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-slate-300 font-mono flex items-center gap-1.5">
                        <LucideIcon name="bar-chart-2" className="w-4 h-4 text-cyan-400" />
                        Pilihan Mesin Grafik:
                      </span>
                    </div>
                    <div className="flex items-center gap-1.5 font-mono text-xs">
                      <button
                        type="button"
                        onClick={() => setChartMode('tradingview')}
                        className={`px-3 py-1.5 rounded-lg font-bold border transition ${
                          chartMode === 'tradingview'
                            ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/50 shadow-sm'
                            : 'bg-obsidian-950 text-slate-400 border-obsidian-800 hover:text-white'
                        }`}
                      >
                        📈 TradingView Pro (Live Timeframe 1m–1M)
                      </button>
                      <button
                        type="button"
                        onClick={() => setChartMode('quantitative')}
                        className={`px-3 py-1.5 rounded-lg font-bold border transition ${
                          chartMode === 'quantitative'
                            ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/50 shadow-sm'
                            : 'bg-obsidian-950 text-slate-400 border-obsidian-800 hover:text-white'
                        }`}
                      >
                        ⚡ SOFIA Quant (5 Indikator SNR/SMC/EMA/Kumo/Fib)
                      </button>
                    </div>
                  </div>

                  {chartMode === 'tradingview' ? (
                    <TradingViewWidget
                      symbol={data?.code || activeSymbol}
                      timeframe={selectedTimeframe}
                      isCrypto={true}
                      height={520}
                    />
                  ) : (
                    <TradingChart
                      candles={data?.candles || data?.recent_candles || []}
                      symbol={data?.code || activeSymbol}
                      timeframe={selectedTimeframe}
                      currency="USD"
                      technicalAudit={data?.technical_audit}
                      initialFocus={focusedIndicator}
                      onFocusChange={setFocusedIndicator}
                      height={450}
                    />
                  )}

                  {data?.technical_audit && (
                    <TechnicalIndicatorsCard
                      technicalAudit={data.technical_audit}
                      symbol={data?.code || activeSymbol}
                      currency="USD"
                      focusedIndicator={focusedIndicator}
                      onSelectIndicator={handleSelectIndicator}
                    />
                  )}
                </div>

                {/* 2. SIMULASI MODAL SPOT & TOKENOMICS */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  <div className="bg-[#0B0E14] border border-slate-800/80 rounded-2xl p-5">
                    <div className="flex items-center justify-between mb-3">
                      <h3 className="text-sm font-black text-white flex items-center gap-2">
                        <LucideIcon name="calculator" className="w-4 h-4 text-cyan-400" />
                        Simulasi Modal Beli Spot &amp; Estimasi Cuan (Rupiah)
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
                      </div>
                      <div className="bg-emerald-500/10 border border-emerald-500/30 rounded-xl p-3">
                        <span className="text-[10px] text-emerald-300 block">Potensi Profit Bersih TP 1 / TP 2</span>
                        <span className="text-xs sm:text-sm font-black text-emerald-400 mt-0.5 block">
                          +{formatIdr(netTp1ProfitIdr)} s/d +{formatIdr(netTp2ProfitIdr)}
                        </span>
                      </div>
                      <div className="bg-rose-500/10 border border-rose-500/30 rounded-xl p-3">
                        <span className="text-[10px] text-rose-300 block">Risiko Rugi Bersih Stop Loss</span>
                        <span className="text-xs sm:text-sm font-black text-rose-400 mt-0.5 block">
                          {formatIdr(netSlLossIdr)} ({activePlan.net_stop_loss_pct}%)
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Tokenomics info */}
                  <div className="bg-[#0B0E14] border border-slate-800/80 rounded-2xl p-5 flex flex-col justify-between">
                    <div>
                      <div className="flex items-center justify-between mb-3">
                        <h3 className="text-sm font-black text-white flex items-center gap-2">
                          <LucideIcon name="layers" className="w-4 h-4 text-emerald-400" />
                          Tokenomics, Suplai &amp; Risiko Dilusi (FDV)
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
                        </div>
                        <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-3">
                          <span className="text-[10px] text-slate-400 block">FDV / MCap Ratio</span>
                          <span className="text-sm font-black text-cyan-400 mt-0.5 block">
                            {tok?.fdv_usd_b ? `${tok.fdv_to_mcap_ratio}x` : 'N/A'}
                          </span>
                        </div>
                        <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-3">
                          <span className="text-[10px] text-slate-400 block">Suplai Beredar</span>
                          <span className="text-sm font-black text-emerald-400 mt-0.5 block">
                            {tok?.circulating_pct ? `${tok.circulating_pct}%` : '100%'}
                          </span>
                        </div>
                      </div>
                    </div>

                    <div className="mt-3 p-3 rounded-xl bg-slate-900/60 border border-slate-800 text-xs space-y-1">
                      <div>
                        <span className="text-slate-400">Risiko Unlock / Dilusi: </span>
                        <strong className="text-white">{tok?.unlock_dilution_risk}</strong>
                      </div>
                      <div>
                        <span className="text-slate-400">Mekanisme Burn: </span>
                        <span className="text-slate-200">{tok?.burn_mechanism}</span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* 3. INDIKATOR TEKNIKAL & GRAFIK 30 HARI */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  <div className="bg-[#0B0E14] border border-slate-800/80 rounded-2xl p-5">
                    <h3 className="text-sm font-black text-white flex items-center gap-2 mb-3">
                      <LucideIcon name="sliders" className="w-4 h-4 text-purple-400" />
                      Indikator Teknikal (RSI, MACD, Bollinger &amp; ATR)
                    </h3>
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5 text-xs">
                      <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-3">
                        <span className="text-[10px] text-slate-400 block">RSI (14)</span>
                        <span className="text-base font-black text-white mt-0.5 block">{tech?.rsi_14}</span>
                        <span className="text-[10px] text-cyan-400 font-bold">{tech?.rsi_status}</span>
                      </div>
                      <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-3">
                        <span className="text-[10px] text-slate-400 block">SMA-20 &amp; EMA-20</span>
                        <span className="text-sm font-black text-white mt-0.5 block">{formatCryptoUsd(tech?.sma_20)}</span>
                        <span className="text-[10px] text-slate-400">EMA: {formatCryptoUsd(tech?.ema_20)}</span>
                      </div>
                      <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-3">
                        <span className="text-[10px] text-slate-400 block">MACD (12, 26, 9)</span>
                        <span className="text-sm font-black text-white mt-0.5 block">{tech?.macd}</span>
                        <span className={`text-[10px] font-bold ${(tech?.macd_histogram || 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                          Hist: {tech?.macd_histogram}
                        </span>
                      </div>
                      <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-3">
                        <span className="text-[10px] text-slate-400 block">Bollinger Bands</span>
                        <span className="text-xs font-black text-white mt-0.5 block">
                          {formatCryptoUsd(tech?.bollinger?.lower)} – {formatCryptoUsd(tech?.bollinger?.upper)}
                        </span>
                      </div>
                      <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-3">
                        <span className="text-[10px] text-slate-400 block">ATR-14 Volatilitas</span>
                        <span className="text-sm font-black text-white mt-0.5 block">
                          {formatCryptoUsd(tech?.atr_14_usd)} ({tech?.atr_pct}%)
                        </span>
                      </div>
                      <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-3">
                        <span className="text-[10px] text-slate-400 block">Volume Ratio</span>
                        <span className="text-sm font-black text-cyan-400 mt-0.5 block">{tech?.volume_ratio}x MA20</span>
                      </div>
                    </div>
                  </div>

                  <div className="bg-[#0B0E14] border border-slate-800/80 rounded-2xl p-5 flex flex-col justify-between">
                    <div className="flex items-center justify-between mb-3">
                      <h3 className="text-sm font-black text-white flex items-center gap-2">
                        <LucideIcon name="bar-chart-2" className="w-4 h-4 text-cyan-400" />
                        Tren Harga 30 Hari Terakhir ({data.code})
                      </h3>
                      <span className="text-[11px] text-slate-400">Hover batang</span>
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
                          <div className="h-32 flex items-end gap-1 pt-2 px-1">
                            {candles.map((c: any, idx: number) => {
                              const prev = idx > 0 ? Number(candles[idx - 1].close) : Number(c.open);
                              const isUp = Number(c.close) >= prev;
                              const hPct = Math.max(12, Math.round(((Number(c.close) - minC) / span) * 100));
                              return (
                                <div key={c.date + idx} className="flex-1 flex flex-col items-center group relative h-full justify-end">
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
                            <span>Low 30H: <strong className="text-slate-200">{formatCryptoUsd(minC)}</strong></span>
                            <span>High 30H: <strong className="text-slate-200">{formatCryptoUsd(maxC)}</strong></span>
                          </div>
                        </div>
                      );
                    })()}
                  </div>
                </div>

                {/* 4. BERITA KRIPTO */}
                {data.news_articles && data.news_articles.length > 0 && (
                  <div className="bg-[#0B0E14] border border-slate-800/80 rounded-2xl p-5">
                    <h3 className="text-sm font-black text-white flex items-center gap-2 mb-3">
                      <LucideIcon name="newspaper" className="w-4 h-4 text-cyan-400" />
                      Berita &amp; Sentimen Kripto ({data.code})
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
              </div>

              {/* Kolom Kanan Samping: CARD DARI BAWAH DIPINDAHKAN KE SAMPING! (5 Kolom) */}
              <div className="xl:col-span-5 space-y-5">
                {/* 1. CARD KEPUTUSAN TRADING UTAMA */}
                {decision && (
                  <div className="bg-gradient-to-br from-[#0B0E14] via-[#0E1726] to-[#0B0E14] border border-cyan-500/40 rounded-2xl p-5 shadow-2xl relative overflow-hidden">
                    <div className="flex flex-col gap-2 pb-3 mb-3 border-b border-slate-800/80">
                      <div className="flex items-center justify-between">
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider bg-cyan-500/15 text-cyan-300 border border-cyan-500/30">
                          KEPUTUSAN UTAMA ({decision.timeframe_label?.toUpperCase() || '1 HARI'})
                        </span>
                        <span className="text-xs font-bold text-slate-300">
                          Keyakinan: <strong className="text-cyan-400">{decision.confidence_score}%</strong>
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <div className="text-base font-black text-white">
                          Status: <span className="text-cyan-300">{decision.decision}</span>
                        </div>
                        <span className={`px-2.5 py-0.5 rounded text-xs font-black border ${
                          decision.badge_color === 'emerald'
                            ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/50'
                            : decision.badge_color === 'rose'
                            ? 'bg-rose-500/20 text-rose-300 border-rose-500/50'
                            : 'bg-amber-500/20 text-amber-300 border-amber-500/50'
                        }`}>
                          {decision.decision_badge}
                        </span>
                      </div>
                    </div>

                    <div className="p-3.5 rounded-xl bg-slate-900/90 border border-slate-800 space-y-2">
                      <span className="text-[10px] font-extrabold text-amber-300 uppercase block">
                        Target Level / Tunggu Ke Berapa:
                      </span>
                      <div className="text-xl font-black text-white">
                        {decision.target_display}
                      </div>
                      <p className="text-xs text-slate-300 leading-relaxed">
                        {decision.wait_price_display}
                      </p>
                    </div>

                    <div className="mt-3.5 space-y-2 text-xs">
                      <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-3">
                        <span className="text-[10px] text-cyan-400 font-extrabold uppercase block mb-1">
                          Bagi Calon Pembeli:
                        </span>
                        <div className="text-xs font-bold text-white mb-0.5">
                          {decision.prospective_buyers?.action}
                        </div>
                        <p className="text-[11px] text-slate-300">
                          {decision.prospective_buyers?.instruction}
                        </p>
                      </div>

                      <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-3">
                        <span className="text-[10px] text-amber-400 font-extrabold uppercase block mb-1">
                          Bagi Pemilik Koin:
                        </span>
                        <div className="text-xs font-bold text-white mb-0.5">
                          {decision.existing_holders?.action}
                        </div>
                        <p className="text-[11px] text-slate-300">
                          {decision.existing_holders?.instruction}
                        </p>
                      </div>
                    </div>
                  </div>
                )}

                {/* 2. DEDICATED FUTURES TRADING PLAN CARD */}
                <div className="bg-gradient-to-br from-[#0B0E14] via-[#0E1522] to-[#0B0E14] border border-amber-500/35 rounded-2xl p-5 shadow-xl relative overflow-hidden">
                  <div className="flex flex-col gap-2 pb-3 mb-3 border-b border-slate-800/80">
                    <div className="flex items-center justify-between">
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider bg-amber-500/15 text-amber-300 border border-amber-500/30 flex items-center gap-1">
                        <LucideIcon name="zap" className="w-3 h-3 text-amber-400" />
                        FUTURES PERPETUAL
                      </span>
                      {futuresContract?.has_futures && (
                        <div className="bg-slate-900 p-0.5 rounded-lg border border-slate-800 flex items-center gap-1">
                          <button
                            type="button"
                            onClick={() => setFuturesSideOverride('LONG')}
                            className={`px-2 py-0.5 rounded text-[10px] font-black transition ${
                              selectedFuturesSide === 'LONG'
                                ? 'bg-emerald-500 text-slate-950 shadow-sm'
                                : 'text-slate-400 hover:text-white'
                            }`}
                          >
                            LONG
                          </button>
                          <button
                            type="button"
                            onClick={() => setFuturesSideOverride('SHORT')}
                            className={`px-2 py-0.5 rounded text-[10px] font-black transition ${
                              selectedFuturesSide === 'SHORT'
                                ? 'bg-rose-500 text-white shadow-sm'
                                : 'text-slate-400 hover:text-white'
                            }`}
                          >
                            SHORT
                          </button>
                        </div>
                      )}
                    </div>
                    <div className="text-sm font-black text-white">
                      Kontrak {futuresContract?.contract_name || `${data.code}_USDT`} ({selectedFuturesSide} SETUP)
                    </div>
                  </div>

                  {currentFuturesSetup ? (
                    <div className="space-y-2.5 text-xs">
                      <div className="grid grid-cols-2 gap-2">
                        <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-2.5">
                          <span className="text-[10px] text-slate-400 block">Zona Entry {selectedFuturesSide}</span>
                          <span className="text-sm font-black text-white mt-0.5 block">
                            {formatCryptoUsd(currentFuturesSetup.entry_zone_low_usd)} – {formatCryptoUsd(currentFuturesSetup.entry_zone_high_usd)}
                          </span>
                        </div>
                        <div className="bg-slate-900/90 border border-emerald-500/30 rounded-xl p-2.5">
                          <span className="text-[10px] text-emerald-400 block font-bold">Target Profit 1 (TP1)</span>
                          <span className="text-sm font-black text-emerald-400 mt-0.5 block">
                            {formatCryptoUsd(currentFuturesSetup.tp_1_usd)} (+{currentFuturesSetup.tp_1_leveraged_roi_pct}% ROE)
                          </span>
                        </div>
                        <div className="bg-slate-900/90 border border-emerald-500/30 rounded-xl p-2.5">
                          <span className="text-[10px] text-emerald-400 block font-bold">Target Profit 2 (TP2)</span>
                          <span className="text-sm font-black text-emerald-400 mt-0.5 block">
                            {formatCryptoUsd(currentFuturesSetup.tp_2_usd)} (+{currentFuturesSetup.tp_2_leveraged_roi_pct}% ROE)
                          </span>
                        </div>
                        <div className="bg-slate-900/90 border border-rose-500/30 rounded-xl p-2.5">
                          <span className="text-[10px] text-rose-400 block font-bold">Stop Loss (Anti-Liq)</span>
                          <span className="text-sm font-black text-rose-400 mt-0.5 block">
                            {formatCryptoUsd(currentFuturesSetup.stop_loss_usd)} ({currentFuturesSetup.stop_loss_leveraged_risk_pct}% ROE)
                          </span>
                        </div>
                      </div>

                      <div className="p-3 rounded-xl bg-slate-900/80 border border-slate-800 text-[11px] space-y-1">
                        <div className="flex justify-between">
                          <span className="text-slate-400">Leverage Rekomendasi:</span>
                          <strong className="text-cyan-400">{activeFuturesPlan.recommended_leverage}x (Maks aman: {activeFuturesPlan.max_safe_leverage}x)</strong>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-400">Est. Harga Likuidasi:</span>
                          <strong className="text-amber-400">{formatCryptoUsd(currentFuturesSetup.est_liquidation_price_usd)}</strong>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-400">Rasio R/R &amp; ATR:</span>
                          <span className="text-slate-200">{currentFuturesSetup.risk_reward_ratio} • ATR {activeFuturesPlan.atr_volatility_pct}%</span>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="text-xs text-slate-400 text-center py-4">
                      Instrumen futures belum aktif untuk koin ini.
                    </div>
                  )}
                </div>

                {/* 3. SPOT TRADING PLAN CARD */}
                <div className="bg-gradient-to-br from-[#0B0E14] via-[#0F1622] to-[#0B0E14] border border-cyan-500/30 rounded-2xl p-5 shadow-lg">
                  <div className="flex items-center justify-between pb-3 mb-3 border-b border-slate-800/80">
                    <div>
                      <div className="flex items-center gap-1.5">
                        <LucideIcon name="crosshair" className="w-4 h-4 text-cyan-400" />
                        <h2 className="text-sm font-black text-white">
                          Trading Plan Spot ({activePlan.timeframe_label})
                        </h2>
                      </div>
                      <span className="text-[10px] text-slate-400">
                        Horison: {activePlan.horizon} • Berlaku: {activePlan.valid_until}
                      </span>
                    </div>

                    {/* Timeframe switcher pills */}
                    <div className="flex gap-1">
                      {availableTimeframes.slice(0, 4).map((tf: any) => (
                        <button
                          key={tf.id}
                          type="button"
                          onClick={() => handleTimeframeChange(tf.id)}
                          className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            selectedTimeframe === tf.id
                              ? 'bg-cyan-500 text-slate-950'
                              : 'text-slate-400 hover:text-white bg-slate-900'
                          }`}
                        >
                          {tf.id}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="space-y-2 text-xs">
                    <div className="p-3 rounded-xl bg-slate-900/90 border border-cyan-500/30">
                      <div className="flex justify-between text-[11px] text-cyan-400 font-bold mb-1">
                        <span>Zona Beli (Entry Area):</span>
                        <span>{formatCryptoUsd(activePlan.entry_zone_low_usd)} – {formatCryptoUsd(activePlan.entry_zone_high_usd)}</span>
                      </div>
                      <span className="text-[11px] text-slate-300 font-mono">
                        ≈ {formatIdr(activePlan.entry_zone_low_idr)} – {formatIdr(activePlan.entry_zone_high_idr)}
                      </span>
                    </div>

                    <div className="grid grid-cols-2 gap-2">
                      <div className="p-2.5 rounded-xl bg-slate-900/90 border border-emerald-500/30">
                        <span className="text-[10px] text-emerald-400 block font-bold">Target Profit 1 (TP1)</span>
                        <div className="text-sm font-black text-emerald-400 mt-0.5">
                          {formatCryptoUsd(activePlan.tp_1_usd)}
                        </div>
                        <span className="text-[10px] text-slate-400 block">
                          +{activePlan.tp_1_pct}% (Net +{activePlan.net_tp_1_pct}%)
                        </span>
                      </div>
                      <div className="p-2.5 rounded-xl bg-slate-900/90 border border-emerald-500/30">
                        <span className="text-[10px] text-emerald-400 block font-bold">Target Profit 2 (TP2)</span>
                        <div className="text-sm font-black text-emerald-400 mt-0.5">
                          {formatCryptoUsd(activePlan.tp_2_usd)}
                        </div>
                        <span className="text-[10px] text-slate-400 block">
                          +{activePlan.tp_2_pct}% (Net +{activePlan.net_tp_2_pct}%)
                        </span>
                      </div>
                    </div>

                    <div className="p-2.5 rounded-xl bg-slate-900/90 border border-rose-500/30">
                      <div className="flex justify-between items-baseline">
                        <span className="text-[10px] text-rose-400 font-bold">Batas Stop Loss (Cut-Loss Disiplin)</span>
                        <span className="text-sm font-black text-rose-400">
                          {formatCryptoUsd(activePlan.stop_loss_usd)}
                        </span>
                      </div>
                      <div className="text-[10px] text-slate-400 mt-0.5">
                        Risiko: {activePlan.stop_loss_pct}% (Net {activePlan.net_stop_loss_pct}%) • Support: {formatCryptoUsd(activePlan.support_1_usd)}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            /* =========================================================================
               MODE BIASA (DEFAULT): MENAMPILKAN 3 CARD DI ATAS, DAN SCROLL KE BAWAH UNTUK CARD-CARD LAINNYA
               ========================================================================= */
            <div className="space-y-6">
              {/* 1. CARD KEPUTUSAN TRADING UTAMA */}
              {decision && (
                <div className="bg-gradient-to-br from-[#0B0E14] via-[#0E1726] to-[#0B0E14] border border-cyan-500/40 rounded-2xl p-5 shadow-2xl relative overflow-hidden">
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
                    </div>

                    <div className="flex items-center gap-3 shrink-0">
                      <div
                        className={`px-4 py-2 rounded-xl border flex items-center gap-2.5 shadow-lg ${
                          decision.badge_color === 'emerald'
                            ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/50'
                            : decision.badge_color === 'rose'
                            ? 'bg-rose-500/20 text-rose-300 border-rose-500/50'
                            : 'bg-amber-500/20 text-amber-300 border-amber-500/50'
                        }`}
                      >
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

                  <div className="p-4 rounded-xl border mb-4 bg-slate-900/90 border-slate-800">
                    <span className="text-[11px] font-black uppercase tracking-wider text-amber-300 flex items-center gap-1.5">
                      <LucideIcon name="alert-circle" className="w-4 h-4 text-amber-400" />
                      Target Level Masuk / Tunggu Ke Berapa:
                    </span>
                    <div className="text-xl sm:text-2xl font-black text-white mt-1.5">
                      {decision.target_display}
                    </div>
                    <p className="text-xs text-slate-300 mt-1 leading-relaxed">
                      {decision.wait_price_display}
                    </p>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5 mb-4">
                    <div className="bg-slate-900/80 border border-slate-800/90 rounded-xl p-4">
                      <span className="text-[11px] font-black uppercase tracking-wider text-cyan-400 block mb-1">
                        Bagi Calon Pembeli (Belum Punya Koin)
                      </span>
                      <div className="text-sm font-bold text-white mb-1">
                        {decision.prospective_buyers?.action}
                      </div>
                      <p className="text-xs text-slate-300">
                        {decision.prospective_buyers?.instruction}
                      </p>
                    </div>

                    <div className="bg-slate-900/80 border border-slate-800/90 rounded-xl p-4">
                      <span className="text-[11px] font-black uppercase tracking-wider text-amber-400 block mb-1">
                        Bagi Pemilik Koin (Sudah Punya Aset)
                      </span>
                      <div className="text-sm font-bold text-white mb-1">
                        {decision.existing_holders?.action}
                      </div>
                      <p className="text-xs text-slate-300">
                        {decision.existing_holders?.instruction}
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* 2. CHART & 5 INDIKATOR AUDIT */}
              <div id="chart-container-root" className="space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-2 bg-obsidian-900/80 p-2.5 rounded-xl border border-obsidian-800">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-slate-300 font-mono flex items-center gap-1.5">
                      <LucideIcon name="bar-chart-2" className="w-4 h-4 text-cyan-400" />
                      Pilihan Mesin Grafik:
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5 font-mono text-xs">
                    <button
                      type="button"
                      onClick={() => setChartMode('tradingview')}
                      className={`px-3 py-1.5 rounded-lg font-bold border transition ${
                        chartMode === 'tradingview'
                          ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/50 shadow-sm'
                          : 'bg-obsidian-950 text-slate-400 border-obsidian-800 hover:text-white'
                      }`}
                    >
                      📈 TradingView Pro (Live Timeframe 1m–1M)
                    </button>
                    <button
                      type="button"
                      onClick={() => setChartMode('quantitative')}
                      className={`px-3 py-1.5 rounded-lg font-bold border transition ${
                        chartMode === 'quantitative'
                          ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/50 shadow-sm'
                          : 'bg-obsidian-950 text-slate-400 border-obsidian-800 hover:text-white'
                      }`}
                    >
                      ⚡ SOFIA Quant (5 Indikator SNR/SMC/EMA/Kumo/Fib)
                    </button>
                  </div>
                </div>

                {chartMode === 'tradingview' ? (
                  <TradingViewWidget
                    symbol={data?.code || activeSymbol}
                    timeframe={selectedTimeframe}
                    isCrypto={true}
                    height={520}
                  />
                ) : (
                  <TradingChart
                    candles={data?.candles || data?.recent_candles || []}
                    symbol={data?.code || activeSymbol}
                    timeframe={selectedTimeframe}
                    currency="USD"
                    technicalAudit={data?.technical_audit}
                    initialFocus={focusedIndicator}
                    onFocusChange={setFocusedIndicator}
                    height={450}
                  />
                )}

                {data?.technical_audit && (
                  <TechnicalIndicatorsCard
                    technicalAudit={data.technical_audit}
                    symbol={data?.code || activeSymbol}
                    currency="USD"
                    focusedIndicator={focusedIndicator}
                    onSelectIndicator={handleSelectIndicator}
                  />
                )}
              </div>

              {/* 3. SPOT TRADING PLAN */}
              <div className="bg-gradient-to-br from-[#0B0E14] via-[#0F1622] to-[#0B0E14] border border-cyan-500/30 rounded-2xl p-5 shadow-lg">
                <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 mb-4 pb-3 border-b border-slate-800/80">
                  <div>
                    <div className="flex items-center gap-2">
                      <LucideIcon name="crosshair" className="w-5 h-5 text-cyan-400" />
                      <h2 className="text-base sm:text-lg font-black text-white">
                        Rekomendasi Trading Plan Crypto (Entry, TP &amp; Stop Loss)
                      </h2>
                    </div>
                    <p className="text-xs text-slate-400 mt-0.5">
                      Horison: <strong className="text-cyan-300">{activePlan.horizon}</strong> • Berlaku: <strong className="text-slate-300">{activePlan.valid_until}</strong>
                    </p>
                  </div>

                  <div className="flex flex-wrap items-center gap-1.5 bg-slate-900/90 p-1.5 rounded-xl border border-slate-800">
                    <span className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400 px-2">
                      Timeframe:
                    </span>
                    {availableTimeframes.map((tf: any) => (
                      <button
                        key={tf.id}
                        type="button"
                        onClick={() => handleTimeframeChange(tf.id)}
                        className={`px-2.5 py-1 rounded-lg text-xs font-extrabold transition ${
                          selectedTimeframe === tf.id
                            ? 'bg-cyan-500 text-slate-950 shadow-sm'
                            : 'text-slate-300 hover:text-white hover:bg-slate-800'
                        }`}
                      >
                        {tf.label}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
                  <div className="bg-slate-900/90 border border-cyan-500/40 rounded-xl p-4">
                    <span className="text-[11px] font-extrabold uppercase text-cyan-400">1. Zona Beli (Entry Area)</span>
                    <div className="text-lg font-black text-white mt-2">
                      {formatCryptoUsd(activePlan.entry_zone_low_usd)} – {formatCryptoUsd(activePlan.entry_zone_high_usd)}
                    </div>
                    <p className="text-[11px] text-cyan-300 font-semibold mt-0.5">
                      {formatIdr(activePlan.entry_zone_low_idr)} – {formatIdr(activePlan.entry_zone_high_idr)}
                    </p>
                  </div>

                  <div className="bg-slate-900/90 border border-emerald-500/40 rounded-xl p-4">
                    <span className="text-[11px] font-extrabold uppercase text-emerald-400">2. Target Profit 1 (TP 1)</span>
                    <div className="text-xl font-black text-emerald-400 mt-2">
                      {formatCryptoUsd(activePlan.tp_1_usd)}
                    </div>
                    <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 text-[10px] font-black inline-block mt-1">
                      +{activePlan.tp_1_pct}% (Net +{activePlan.net_tp_1_pct}%)
                    </span>
                  </div>

                  <div className="bg-slate-900/90 border border-emerald-500/40 rounded-xl p-4">
                    <span className="text-[11px] font-extrabold uppercase text-emerald-400">3. Target Profit 2 (TP 2)</span>
                    <div className="text-xl font-black text-emerald-400 mt-2">
                      {formatCryptoUsd(activePlan.tp_2_usd)}
                    </div>
                    <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 text-[10px] font-black inline-block mt-1">
                      +{activePlan.tp_2_pct}% (Net +{activePlan.net_tp_2_pct}%)
                    </span>
                  </div>

                  <div className="bg-slate-900/90 border border-rose-500/40 rounded-xl p-4">
                    <span className="text-[11px] font-extrabold uppercase text-rose-400">4. Batas Stop Loss (SL)</span>
                    <div className="text-xl font-black text-rose-400 mt-2">
                      {formatCryptoUsd(activePlan.stop_loss_usd)}
                    </div>
                    <span className="px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 text-[10px] font-black inline-block mt-1">
                      {activePlan.stop_loss_pct}% (Net {activePlan.net_stop_loss_pct}%)
                    </span>
                  </div>
                </div>
              </div>

              {/* 4. DEDICATED FUTURES TRADING PLAN */}
              <div className="bg-gradient-to-br from-[#0B0E14] via-[#0E1522] to-[#0B0E14] border border-amber-500/35 rounded-2xl p-5 shadow-xl relative overflow-hidden">
                <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-4 pb-3.5 border-b border-slate-800/80">
                  <div>
                    <span className="px-2.5 py-0.5 rounded-full text-[10px] font-extrabold uppercase tracking-wider bg-amber-500/15 text-amber-300 border border-amber-500/30 flex items-center gap-1.5 w-max mb-1">
                      <LucideIcon name="zap" className="w-3 h-3 text-amber-400" />
                      KONTRAK FUTURES PERPETUAL (LEVERAGE)
                    </span>
                    <h2 className="text-base sm:text-lg font-black text-white">
                      Trading Plan Futures ({futuresContract?.contract_name || `${data.code}_USDT`})
                    </h2>
                  </div>

                  {futuresContract?.has_futures && (
                    <div className="bg-slate-900/90 p-1 rounded-xl border border-slate-800 flex items-center gap-1">
                      <button
                        type="button"
                        onClick={() => setFuturesSideOverride('LONG')}
                        className={`px-3 py-1.5 rounded-lg text-xs font-black transition ${
                          selectedFuturesSide === 'LONG'
                            ? 'bg-emerald-500 text-slate-950 shadow-md'
                            : 'text-slate-400 hover:text-white'
                        }`}
                      >
                        LONG SETUP {activeFuturesPlan?.primary_bias === 'LONG' && '★'}
                      </button>
                      <button
                        type="button"
                        onClick={() => setFuturesSideOverride('SHORT')}
                        className={`px-3 py-1.5 rounded-lg text-xs font-black transition ${
                          selectedFuturesSide === 'SHORT'
                            ? 'bg-rose-500 text-white shadow-md'
                            : 'text-slate-400 hover:text-white'
                        }`}
                      >
                        SHORT SETUP {activeFuturesPlan?.primary_bias === 'SHORT' && '★'}
                      </button>
                    </div>
                  )}
                </div>

                {currentFuturesSetup && (
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
                    <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-4">
                      <span className="text-[11px] font-black uppercase text-cyan-400">1. Zona Entry ({selectedFuturesSide})</span>
                      <div className="text-lg font-black text-white mt-2">
                        {formatCryptoUsd(currentFuturesSetup.entry_zone_low_usd)} – {formatCryptoUsd(currentFuturesSetup.entry_zone_high_usd)}
                      </div>
                    </div>
                    <div className="bg-slate-900/90 border border-emerald-500/40 rounded-xl p-4">
                      <span className="text-[11px] font-extrabold uppercase text-emerald-400">2. Target Profit 1 (TP 1)</span>
                      <div className="text-xl font-black text-emerald-400 mt-2">
                        {formatCryptoUsd(currentFuturesSetup.tp_1_usd)}
                      </div>
                      <span className="text-[10px] text-emerald-300 font-black block mt-1">
                        +{currentFuturesSetup.tp_1_leveraged_roi_pct}% ROE
                      </span>
                    </div>
                    <div className="bg-slate-900/90 border border-emerald-500/40 rounded-xl p-4">
                      <span className="text-[11px] font-extrabold uppercase text-emerald-400">3. Target Profit 2 (TP 2)</span>
                      <div className="text-xl font-black text-emerald-400 mt-2">
                        {formatCryptoUsd(currentFuturesSetup.tp_2_usd)}
                      </div>
                      <span className="text-[10px] text-emerald-300 font-black block mt-1">
                        +{currentFuturesSetup.tp_2_leveraged_roi_pct}% ROE
                      </span>
                    </div>
                    <div className="bg-slate-900/90 border border-rose-500/40 rounded-xl p-4">
                      <span className="text-[11px] font-extrabold uppercase text-rose-400">4. Stop Loss &amp; Likuidasi</span>
                      <div className="text-xl font-black text-rose-400 mt-2">
                        {formatCryptoUsd(currentFuturesSetup.stop_loss_usd)}
                      </div>
                      <span className="text-[10px] text-rose-300 font-black block mt-1">
                        {currentFuturesSetup.stop_loss_leveraged_risk_pct}% ROE
                      </span>
                      <div className="mt-1 pt-1 border-t border-slate-800 text-[10px] text-amber-400">
                        Est. Liq: {formatCryptoUsd(currentFuturesSetup.est_liquidation_price_usd)}
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* 5. SIMULASI MODAL SPOT & TOKENOMICS */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <div className="bg-[#0B0E14] border border-slate-800/80 rounded-2xl p-5">
                  <h3 className="text-sm font-black text-white flex items-center gap-2 mb-3">
                    <LucideIcon name="calculator" className="w-4 h-4 text-cyan-400" />
                    Simulasi Modal Beli Spot &amp; Estimasi Cuan (Rupiah)
                  </h3>
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
                  </div>
                  <div className="grid grid-cols-2 gap-3 mt-3">
                    <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-3">
                      <span className="text-[10px] text-slate-400 block">Koin Didapat</span>
                      <span className="text-sm font-black text-white mt-0.5 block">
                        {acquiredCoins.toFixed(acquiredCoins >= 1 ? 4 : 6)} {data.code}
                      </span>
                    </div>
                    <div className="bg-emerald-500/10 border border-emerald-500/30 rounded-xl p-3">
                      <span className="text-[10px] text-emerald-300 block">Potensi Profit TP1/TP2</span>
                      <span className="text-xs font-black text-emerald-400 mt-0.5 block">
                        +{formatIdr(netTp1ProfitIdr)} s/d +{formatIdr(netTp2ProfitIdr)}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="bg-[#0B0E14] border border-slate-800/80 rounded-2xl p-5">
                  <h3 className="text-sm font-black text-white flex items-center gap-2 mb-3">
                    <LucideIcon name="layers" className="w-4 h-4 text-emerald-400" />
                    Tokenomics &amp; Suplai Beredar ({data.code})
                  </h3>
                  <div className="grid grid-cols-3 gap-2.5 text-xs">
                    <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-3">
                      <span className="text-[10px] text-slate-400 block">Market Cap</span>
                      <span className="text-sm font-black text-white mt-0.5 block">
                        {tok?.market_cap_usd_b ? `$${tok.market_cap_usd_b} B` : 'N/A'}
                      </span>
                    </div>
                    <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-3">
                      <span className="text-[10px] text-slate-400 block">FDV Ratio</span>
                      <span className="text-sm font-black text-cyan-400 mt-0.5 block">
                        {tok?.fdv_to_mcap_ratio ? `${tok.fdv_to_mcap_ratio}x` : 'N/A'}
                      </span>
                    </div>
                    <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-3">
                      <span className="text-[10px] text-slate-400 block">Beredar</span>
                      <span className="text-sm font-black text-emerald-400 mt-0.5 block">
                        {tok?.circulating_pct ? `${tok.circulating_pct}%` : '100%'}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* 6. INDIKATOR TEKNIKAL & TREN 30 HARI */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <div className="bg-[#0B0E14] border border-slate-800/80 rounded-2xl p-5">
                  <h3 className="text-sm font-black text-white flex items-center gap-2 mb-3">
                    <LucideIcon name="sliders" className="w-4 h-4 text-purple-400" />
                    Indikator Teknikal (RSI, SMA, EMA &amp; ATR)
                  </h3>
                  <div className="grid grid-cols-3 gap-2.5 text-xs">
                    <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-3">
                      <span className="text-[10px] text-slate-400 block">RSI (14)</span>
                      <span className="text-base font-black text-white mt-0.5 block">{tech?.rsi_14}</span>
                      <span className="text-[10px] text-cyan-400 font-bold">{tech?.rsi_status}</span>
                    </div>
                    <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-3">
                      <span className="text-[10px] text-slate-400 block">SMA-20</span>
                      <span className="text-sm font-black text-white mt-0.5 block">{formatCryptoUsd(tech?.sma_20)}</span>
                    </div>
                    <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-3">
                      <span className="text-[10px] text-slate-400 block">ATR-14</span>
                      <span className="text-sm font-black text-white mt-0.5 block">{formatCryptoUsd(tech?.atr_14_usd)}</span>
                    </div>
                  </div>
                </div>

                <div className="bg-[#0B0E14] border border-slate-800/80 rounded-2xl p-5">
                  <h3 className="text-sm font-black text-white flex items-center gap-2 mb-3">
                    <LucideIcon name="bar-chart-2" className="w-4 h-4 text-cyan-400" />
                    Tren Harga 30 Hari Terakhir
                  </h3>
                  {(() => {
                    const candles = data.recent_candles || [];
                    if (!candles.length) return <div className="text-xs text-slate-500">Data candle tidak tersedia</div>;
                    const closes = candles.map((c: any) => Number(c.close));
                    const minC = Math.min(...closes);
                    const maxC = Math.max(...closes);
                    const span = Math.max(1e-9, maxC - minC);
                    return (
                      <div className="h-32 flex items-end gap-1 pt-2 px-1">
                        {candles.map((c: any, idx: number) => {
                          const prev = idx > 0 ? Number(candles[idx - 1].close) : Number(c.open);
                          const isUp = Number(c.close) >= prev;
                          const hPct = Math.max(12, Math.round(((Number(c.close) - minC) / span) * 100));
                          return (
                            <div key={c.date + idx} className="flex-1 flex flex-col items-center group relative h-full justify-end">
                              <div
                                style={{ height: `${hPct}%` }}
                                className={`w-full rounded-t transition-all ${
                                  isUp ? 'bg-emerald-500/80 group-hover:bg-emerald-400' : 'bg-rose-500/80 group-hover:bg-rose-400'
                                }`}
                              />
                            </div>
                          );
                        })}
                      </div>
                    );
                  })()}
                </div>
              </div>

              {/* 7. BERITA KRIPTO */}
              {data.news_articles && data.news_articles.length > 0 && (
                <div className="bg-[#0B0E14] border border-slate-800/80 rounded-2xl p-5">
                  <h3 className="text-sm font-black text-white flex items-center gap-2 mb-3">
                    <LucideIcon name="newspaper" className="w-4 h-4 text-cyan-400" />
                    Berita Terkait ({data.code})
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
                        <h4 className="text-xs font-bold text-white line-clamp-2">{art.title}</h4>
                        <span className="text-[10px] text-cyan-400 font-bold mt-2">Baca →</span>
                      </a>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}
