import React, { useState, useEffect, useCallback } from 'react';
import Head from 'next/head';
import { api } from '@/lib/api';
import { LucideIcon } from '@/components/LucideIcon';

const QUICK_TICKERS = [
  'IHSG',
  'BBRI',
  'BBCA',
  'BMRI',
  'BBNI',
  'TLKM',
  'ASII',
  'ADRO',
  'PTBA',
  'ITMG',
  'ANTM',
  'PGAS',
  'UNTR',
  'ICBP',
  'BREN',
  'GOTO',
];

const TIMEFRAME_OPTIONS = [
  { id: '15m', label: '15 Menit', short: '15M' },
  { id: '1h', label: '1 Jam', short: '1J' },
  { id: '1d', label: '1 Hari', short: '1H' },
  { id: '1w', label: '1 Minggu', short: '1M' },
  { id: '1mo', label: '1 Bulan', short: '1B' },
  { id: '1y', label: '1 Tahun', short: '1T' },
];

export default function StockAnalysisPage() {
  const [tickerInput, setTickerInput] = useState<string>('BBRI');
  const [activeTicker, setActiveTicker] = useState<string>('BBRI');
  const [selectedTimeframe, setSelectedTimeframe] = useState<string>('1d');
  const [stockData, setStockData] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [simLots, setSimLots] = useState<number>(10);

  const fetchAnalysis = useCallback(
    async (code: string, force: boolean = false, tf: string = '1d') => {
      const clean = (code || 'BBRI').trim().toUpperCase();
      if (!clean) return;
      if (force) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }
      setErrorMsg(null);
      try {
        const res = await api.analyzeStock(clean, force, tf);
        setStockData(res);
      } catch (err: any) {
        setErrorMsg(err?.message || `Gagal memuat analisa saham ${clean}. Pastikan kode emiten benar.`);
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    []
  );

  useEffect(() => {
    fetchAnalysis(activeTicker, false, selectedTimeframe);
  }, [activeTicker, fetchAnalysis]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!tickerInput.trim()) return;
    const upper = tickerInput.trim().toUpperCase();
    setTickerInput(upper);
    setActiveTicker(upper);
  };

  const isIdx = stockData?.is_idx !== false;
  const isIndex = Boolean(stockData?.is_index);

  const fmtPrice = (val: number | undefined | null, idxFlag: boolean = isIdx, indexFlag: boolean = isIndex) => {
    const num = Number(val || 0);
    if (indexFlag) {
      return num.toLocaleString('id-ID', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }
    if (idxFlag) {
      return `Rp ${Math.round(num).toLocaleString('id-ID')}`;
    }
    return `$${num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };

  const getTrendBadgeStyle = (badge: string) => {
    const b = (badge || '').toUpperCase();
    if (b.includes('BULLISH')) {
      return 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40';
    }
    if (b.includes('REBOUND')) {
      return 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40';
    }
    if (b.includes('BEARISH')) {
      return 'bg-rose-500/20 text-rose-300 border-rose-500/40';
    }
    return 'bg-amber-500/20 text-amber-300 border-amber-500/40';
  };

  // Resolve active trading plan from precomputed timeframes_plan or fallback to trading_plan
  const plan =
    stockData?.timeframes_plan?.[selectedTimeframe] ||
    stockData?.trading_plan ||
    {};
  const tech = stockData?.technicals || {};
  const div = stockData?.dividend || {};
  const perf = stockData?.performance || {};
  const range52 = stockData?.range_52w || {};
  const ihsg = stockData?.ihsg || null;
  const candles: any[] = stockData?.recent_candles || [];

  // Simulator calculations (updates dynamically with selectedTimeframe)
  const lotsCount = Math.max(1, Number(simLots) || 1);
  const sharesCount = isIdx && !isIndex ? lotsCount * 100 : lotsCount;
  const totalCapital = sharesCount * Number(stockData?.current_price || 0);
  const estAnnualDivTotal = sharesCount * Number(div.annual_dividend_per_share || 0);
  const estProfitTp1 = sharesCount * Math.max(0, Number(plan.tp_1 || 0) - Number(stockData?.current_price || 0));
  const estProfitTp2 = sharesCount * Math.max(0, Number(plan.tp_2 || 0) - Number(stockData?.current_price || 0));

  return (
    <>
      <Head>
        <title>Analisa Saham BEI ({activeTicker}) | SOFIA Trenches v3.8 PRO</title>
      </Head>

      <div className="p-4 lg:p-6 space-y-5 max-w-[1600px] mx-auto">
        {/* Top Search, IHSG Hari Ini Banner & Quick Ticker Bar */}
        <div className="rounded-2xl border border-slate-800/90 bg-gradient-to-r from-[#0b101d] via-[#0f172a] to-[#0b101d] p-5 shadow-xl space-y-4">
          <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center text-emerald-400 shrink-0">
                <LucideIcon name="trending-up" className="w-5 h-5" />
              </div>
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h1 className="text-lg sm:text-xl font-extrabold tracking-tight text-white">
                    ANALISA CEPAT SAHAM INDONESIA (BEI / IDX)
                  </h1>
                  <span className="px-2.5 py-0.5 text-[10px] font-bold rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                    REAL-TIME BEI
                  </span>
                </div>
                <p className="text-xs text-slate-400 mt-0.5">
                  Masukkan kode saham (misal: BBRI, BBCA, BMRI, ANTM, ADRO) untuk melihat Harga, Area Entry, Target Profit (TP), Stop Loss, Multi-Timeframe, dan Rata-rata Dividen
                </p>
              </div>
            </div>

            {/* Ticker Search Input */}
            <form onSubmit={handleSubmit} className="flex items-center gap-2">
              <input
                type="text"
                value={tickerInput}
                onChange={(e) => setTickerInput(e.target.value.toUpperCase())}
                placeholder="Ketik kode emiten (cth: BBRI)..."
                className="w-full sm:w-56 bg-slate-950 border border-slate-700 rounded-xl px-3.5 py-2 text-xs font-mono font-bold text-white uppercase placeholder-slate-500 focus:outline-none focus:border-emerald-500"
              />
              <button
                type="submit"
                disabled={loading}
                className="px-4 py-2 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 text-xs font-extrabold transition shrink-0"
              >
                Analisa Saham
              </button>
              <button
                type="button"
                onClick={() => fetchAnalysis(activeTicker, true, selectedTimeframe)}
                disabled={loading || refreshing}
                className="px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-bold transition shrink-0"
                title="Refresh harga & indikator terbaru"
              >
                <LucideIcon name="rotate-ccw" className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
              </button>
            </form>
          </div>

          {/* IHSG HARI INI (Indeks Harga Saham Gabungan) Live Bar */}
          {ihsg && (
            <div className="p-3.5 rounded-xl bg-slate-950/85 border border-slate-800 flex flex-wrap items-center justify-between gap-3">
              <div className="flex flex-wrap items-center gap-3">
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
                  <span className="text-xs font-extrabold uppercase tracking-wider text-cyan-300">
                    🇮🇩 IHSG HARI INI ({ihsg.symbol}):
                  </span>
                </div>
                <div className="flex items-baseline gap-2 font-mono">
                  <span className="text-base sm:text-lg font-black text-white">
                    {Number(ihsg.price || 0).toLocaleString('id-ID', {
                      minimumFractionDigits: 2,
                      maximumFractionDigits: 2,
                    })}
                  </span>
                  <span
                    className={`text-xs font-extrabold px-2 py-0.5 rounded-md border ${
                      Number(ihsg.change) >= 0
                        ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
                        : 'bg-rose-500/15 text-rose-300 border-rose-500/30'
                    }`}
                  >
                    {Number(ihsg.change) >= 0 ? '▲ +' : '▼ '}
                    {Number(ihsg.change || 0).toLocaleString('id-ID', {
                      minimumFractionDigits: 2,
                      maximumFractionDigits: 2,
                    })}{' '}
                    ({Number(ihsg.change_pct) >= 0 ? '+' : ''}
                    {ihsg.change_pct}%)
                  </span>
                </div>
                <div className="hidden md:flex items-center gap-3 text-[11px] font-mono text-slate-400 border-l border-slate-800 pl-3">
                  <span>
                    Rentang Hari Ini:{' '}
                    <strong className="text-slate-200">
                      {Number(ihsg.day_low || 0).toLocaleString('id-ID', { maximumFractionDigits: 0 })} –{' '}
                      {Number(ihsg.day_high || 0).toLocaleString('id-ID', { maximumFractionDigits: 0 })}
                    </strong>
                  </span>
                  <span>•</span>
                  <span>
                    52 Minggu:{' '}
                    <strong className="text-slate-200">
                      {Number(ihsg.w52_low || 0).toLocaleString('id-ID', { maximumFractionDigits: 0 })} –{' '}
                      {Number(ihsg.w52_high || 0).toLocaleString('id-ID', { maximumFractionDigits: 0 })}
                    </strong>
                  </span>
                </div>
              </div>

              <button
                type="button"
                onClick={() => {
                  setTickerInput('IHSG');
                  setActiveTicker('IHSG');
                }}
                className="px-3 py-1.5 rounded-lg bg-cyan-500/15 hover:bg-cyan-500/25 text-cyan-300 border border-cyan-500/30 text-xs font-bold transition"
              >
                📊 Analisa Detail IHSG
              </button>
            </div>
          )}

          {/* Popular IDX Quick-Select Pills */}
          <div className="pt-2 border-t border-slate-800/80 flex items-center gap-1.5 overflow-x-auto pb-1 no-scrollbar">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 shrink-0 mr-1">
              Saham Populer:
            </span>
            {QUICK_TICKERS.map((code) => {
              const active = activeTicker === code;
              return (
                <button
                  key={code}
                  type="button"
                  onClick={() => {
                    setTickerInput(code);
                    setActiveTicker(code);
                  }}
                  className={`px-2.5 py-1 rounded-lg text-xs font-mono font-bold border transition whitespace-nowrap ${
                    active
                      ? 'bg-emerald-500/25 text-emerald-300 border-emerald-400 shadow-sm'
                      : 'bg-slate-900/90 text-slate-300 border-slate-800 hover:text-white hover:border-slate-700'
                  }`}
                >
                  {code}
                </button>
              );
            })}
          </div>
        </div>

        {/* Error Alert */}
        {errorMsg && (
          <div className="p-4 rounded-xl border border-rose-500/40 bg-rose-500/10 text-rose-300 text-xs flex items-center justify-between">
            <span>⚠️ {errorMsg}</span>
            <button
              type="button"
              onClick={() => {
                setTickerInput('BBRI');
                setActiveTicker('BBRI');
              }}
              className="px-3 py-1 rounded-lg bg-rose-500/20 hover:bg-rose-500/30 text-rose-200 font-bold"
            >
              Kembali ke BBRI
            </button>
          </div>
        )}

        {loading ? (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 animate-pulse">
            <div className="h-64 rounded-2xl bg-[#0b101d] border border-slate-800" />
            <div className="h-64 rounded-2xl bg-[#0b101d] border border-slate-800" />
            <div className="h-64 rounded-2xl bg-[#0b101d] border border-slate-800" />
          </div>
        ) : stockData ? (
          <>
            {/* ROW 1: Main Stock Overview + Multi-Timeframe Trading Plan + Dividend Summary */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
              {/* Card 1: Harga Saat Ini & Status Bullish/Bearish (4 cols) */}
              <div className="lg:col-span-4 rounded-2xl border border-slate-800/90 bg-[#0b101d] p-5 flex flex-col justify-between space-y-4 shadow-lg">
                <div className="space-y-3">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-2xl font-black font-mono text-white tracking-tight">
                          {stockData.code}
                        </span>
                        <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-slate-800 text-cyan-300 border border-slate-700">
                          {stockData.exchange}
                        </span>
                      </div>
                      <p className="text-xs font-semibold text-slate-300 mt-0.5">{stockData.name}</p>
                      <p className="text-[11px] text-slate-400">{stockData.sector}</p>
                    </div>
                    <span
                      className={`px-2.5 py-1 rounded-lg text-[11px] font-extrabold border ${getTrendBadgeStyle(
                        plan.trend_badge
                      )}`}
                    >
                      {plan.trend_status}
                    </span>
                  </div>

                  {/* Current Price & Day Change */}
                  <div className="pt-2 border-t border-slate-800/80 flex items-baseline justify-between">
                    <div>
                      <div className="text-[10px] font-bold uppercase text-slate-400">
                        {isIndex ? 'Level Indeks Saat Ini' : 'Harga Saat Ini'}
                      </div>
                      <div className="text-3xl font-black font-mono text-white mt-0.5">
                        {fmtPrice(stockData.current_price)}
                      </div>
                    </div>
                    <div className="text-right">
                      <div
                        className={`text-sm font-extrabold font-mono ${
                          stockData.day_change >= 0 ? 'text-emerald-400' : 'text-rose-400'
                        }`}
                      >
                        {stockData.day_change >= 0 ? '+' : ''}
                        {fmtPrice(stockData.day_change)} ({stockData.day_change_pct >= 0 ? '+' : ''}
                        {stockData.day_change_pct}%)
                      </div>
                      {!isIndex && (
                        <div className="text-[11px] text-slate-400 font-mono mt-0.5">
                          1 Lot (100 lbr):{' '}
                          <strong className="text-slate-200">{fmtPrice(stockData.price_per_lot)}</strong>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* 52-Week Range Bar */}
                  <div className="bg-slate-950/80 p-3 rounded-xl border border-slate-800/80 space-y-1.5">
                    <div className="flex justify-between text-[10px] font-mono text-slate-400">
                      <span>Low 52M: {fmtPrice(range52.low)}</span>
                      <span className="text-cyan-300 font-bold">Posisi 52M: {range52.position_pct}%</span>
                      <span>High 52M: {fmtPrice(range52.high)}</span>
                    </div>
                    <div className="w-full h-2 rounded-full bg-slate-800 overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-rose-500 via-amber-400 to-emerald-400 rounded-full"
                        style={{ width: `${Math.min(100, Math.max(4, Number(range52.position_pct || 50)))}%` }}
                      />
                    </div>
                  </div>
                </div>

                {/* Performance Pills (1W, 1M, 3M, 1Y) */}
                <div className="grid grid-cols-4 gap-2 pt-2 border-t border-slate-800/80 font-mono text-center">
                  {[
                    { label: '1 Minggu', val: perf['1w_pct'] },
                    { label: '1 Bulan', val: perf['1m_pct'] },
                    { label: '3 Bulan', val: perf['3m_pct'] },
                    { label: '1 Tahun', val: perf['1y_pct'] },
                  ].map((item) => (
                    <div key={item.label} className="bg-slate-950/70 p-2 rounded-lg border border-slate-800/80">
                      <div className="text-[10px] text-slate-400 font-sans font-medium">{item.label}</div>
                      <div
                        className={`text-xs font-bold mt-0.5 ${
                          Number(item.val) >= 0 ? 'text-emerald-400' : 'text-rose-400'
                        }`}
                      >
                        {Number(item.val) >= 0 ? '+' : ''}
                        {item.val}%
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Card 2: Rekomendasi Trading Plan (Entry, TP & SL) with Multi-Timeframe Selector (5 cols) */}
              <div className="lg:col-span-5 rounded-2xl border border-cyan-500/30 bg-[#0b101d] p-5 flex flex-col justify-between space-y-4 shadow-lg">
                <div className="space-y-3 border-b border-slate-800 pb-3">
                  <div className="flex items-center justify-between gap-2">
                    <div>
                      <h2 className="text-sm font-extrabold uppercase tracking-wide text-cyan-300 flex items-center gap-2">
                        <LucideIcon name="crosshair" className="w-4 h-4 text-cyan-400" />
                        Rekomendasi Trading Plan (Entry, TP &amp; SL)
                      </h2>
                      <p className="text-[11px] text-slate-400 mt-0.5">
                        Strategi: <strong className="text-white">{plan.action_verdict}</strong> • Estimasi Hold:{' '}
                        <strong className="text-cyan-300">{plan.hold_duration || '3 – 10 Hari'}</strong>
                      </p>
                    </div>
                    <span className="px-2.5 py-1 rounded-lg bg-cyan-500/15 border border-cyan-500/30 text-cyan-300 font-mono text-xs font-bold shrink-0">
                      R/R {plan.risk_reward_ratio}
                    </span>
                  </div>

                  {/* Timeframe Selector Buttons (15 Menit, 1 Jam, 1 Hari, 1 Minggu, 1 Bulan, 1 Tahun) */}
                  <div className="flex items-center gap-1.5 overflow-x-auto pb-0.5 no-scrollbar">
                    <span className="text-[10px] font-bold uppercase text-slate-400 shrink-0 mr-1">
                      Time Frame:
                    </span>
                    {TIMEFRAME_OPTIONS.map((tf) => {
                      const active = selectedTimeframe === tf.id;
                      return (
                        <button
                          key={tf.id}
                          type="button"
                          onClick={() => setSelectedTimeframe(tf.id)}
                          className={`px-2.5 py-1 rounded-lg text-[11px] font-bold transition whitespace-nowrap border ${
                            active
                              ? 'bg-cyan-500/25 text-cyan-200 border-cyan-400 shadow-sm'
                              : 'bg-slate-900/90 text-slate-300 border-slate-800 hover:text-white hover:border-slate-700'
                          }`}
                        >
                          {tf.label}
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Grid of Entry, TP1, TP2, Stop Loss */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 font-mono">
                  {/* Area Entry Ideal */}
                  <div className="p-3.5 rounded-xl bg-cyan-500/10 border border-cyan-500/30">
                    <div className="text-[10px] font-sans font-bold uppercase text-cyan-300">
                      🎯 Area Entry Ideal ({plan.timeframe_label || '1 Hari'})
                    </div>
                    <div className="text-base font-black text-white mt-1">
                      {fmtPrice(plan.entry_zone_low)} – {fmtPrice(plan.entry_zone_high)}
                    </div>
                    <div className="text-[10px] font-sans text-slate-400 mt-0.5">
                      Rentang cicil beli sesuai volatilitas {plan.timeframe_label || 'harian'}
                    </div>
                  </div>

                  {/* Stop Loss */}
                  <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-sans font-bold uppercase text-rose-300">
                        🛡️ Stop Loss ({plan.timeframe_label || '1 Hari'})
                      </span>
                      <span className="text-xs font-bold text-rose-400">{plan.stop_loss_pct}%</span>
                    </div>
                    <div className="text-base font-black text-white mt-1">
                      {fmtPrice(plan.stop_loss)}
                    </div>
                    <div className="text-[10px] font-sans text-slate-400 mt-0.5">
                      Batas pengaman risiko time frame {plan.timeframe_label || '1 Hari'}
                    </div>
                  </div>

                  {/* Take Profit 1 */}
                  <div className="p-3.5 rounded-xl bg-emerald-500/10 border border-emerald-500/30">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-sans font-bold uppercase text-emerald-300">
                        🚀 Target Profit 1 (TP 1)
                      </span>
                      <span className="text-xs font-bold text-emerald-400">+{plan.tp_1_pct}%</span>
                    </div>
                    <div className="text-base font-black text-white mt-1">
                      {fmtPrice(plan.tp_1)}
                    </div>
                    <div className="text-[10px] font-sans text-slate-400 mt-0.5">
                      Target resistensi terdekat (Ambil 50% posisi)
                    </div>
                  </div>

                  {/* Take Profit 2 */}
                  <div className="p-3.5 rounded-xl bg-teal-500/10 border border-teal-500/30">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-sans font-bold uppercase text-teal-300">
                        💎 Target Profit 2 (TP 2)
                      </span>
                      <span className="text-xs font-bold text-teal-400">+{plan.tp_2_pct}%</span>
                    </div>
                    <div className="text-base font-black text-white mt-1">
                      {fmtPrice(plan.tp_2)}
                    </div>
                    <div className="text-[10px] font-sans text-slate-400 mt-0.5">
                      Target penuh untuk horizon {plan.timeframe_label || '1 Hari'}
                    </div>
                  </div>
                </div>

                {/* Support & Resistance Row */}
                <div className="grid grid-cols-4 gap-2 pt-2 border-t border-slate-800/80 text-center font-mono text-xs">
                  <div className="bg-slate-950/70 p-2 rounded-lg border border-slate-800">
                    <div className="text-[10px] text-slate-400 font-sans">Support 2</div>
                    <div className="font-bold text-amber-300">{fmtPrice(plan.support_2)}</div>
                  </div>
                  <div className="bg-slate-950/70 p-2 rounded-lg border border-slate-800">
                    <div className="text-[10px] text-slate-400 font-sans">Support 1</div>
                    <div className="font-bold text-cyan-300">{fmtPrice(plan.support_1)}</div>
                  </div>
                  <div className="bg-slate-950/70 p-2 rounded-lg border border-slate-800">
                    <div className="text-[10px] text-slate-400 font-sans">Resistance 1</div>
                    <div className="font-bold text-emerald-300">{fmtPrice(plan.resistance_1)}</div>
                  </div>
                  <div className="bg-slate-950/70 p-2 rounded-lg border border-slate-800">
                    <div className="text-[10px] text-slate-400 font-sans">Resistance 2</div>
                    <div className="font-bold text-teal-300">{fmtPrice(plan.resistance_2)}</div>
                  </div>
                </div>
              </div>

              {/* Card 3: Rata-rata Dividen Tahunan & Yield (3 cols) */}
              <div className="lg:col-span-3 rounded-2xl border border-amber-500/30 bg-[#0b101d] p-5 flex flex-col justify-between space-y-4 shadow-lg">
                <div className="space-y-3">
                  <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                    <div>
                      <h2 className="text-sm font-extrabold uppercase tracking-wide text-amber-300 flex items-center gap-1.5">
                        <LucideIcon name="banknote" className="w-4 h-4 text-amber-400" />
                        Analisa Dividen Tahunan
                      </h2>
                      <p className="text-[11px] text-slate-400">Berdasarkan histori pembagian 3 tahun</p>
                    </div>
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                        div.pays_dividend
                          ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                          : 'bg-slate-800 text-slate-400 border-slate-700'
                      }`}
                    >
                      {div.pays_dividend ? 'RUTIN DIVIDEN' : 'NON-DIVIDEN'}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-2.5 font-mono">
                    <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/30">
                      <div className="text-[10px] font-sans text-amber-300 font-bold">
                        Dividen / Tahun
                      </div>
                      <div className="text-base font-black text-white mt-0.5">
                        {div.pays_dividend ? `${fmtPrice(div.annual_dividend_per_share)}/lbr` : 'Rp 0'}
                      </div>
                      <div className="text-[10px] font-sans text-slate-400 mt-0.5">
                        Rata-rata 3Th: {fmtPrice(div.avg_3y_dividend_per_share)}
                      </div>
                    </div>

                    <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30">
                      <div className="text-[10px] font-sans text-emerald-300 font-bold">
                        Dividend Yield
                      </div>
                      <div className="text-xl font-black text-emerald-400 mt-0.5">
                        {div.dividend_yield_pct}%
                      </div>
                      <div className="text-[10px] font-sans text-slate-400 mt-0.5">
                        {`${div.frequency_per_year}x bagi / tahun`}
                      </div>
                    </div>
                  </div>

                  {/* Dividend History List */}
                  <div className="space-y-1.5">
                    <div className="text-[10px] font-bold uppercase text-slate-400">
                      Riwayat Dividen Terakhir:
                    </div>
                    {div.history && div.history.length > 0 ? (
                      <div className="space-y-1 max-h-36 overflow-y-auto pr-1">
                        {div.history.slice(0, 5).map((item: any, idx: number) => (
                          <div
                            key={idx}
                            className="flex items-center justify-between px-2.5 py-1.5 rounded-lg bg-slate-950/80 border border-slate-800/80 text-xs font-mono"
                          >
                            <span className="text-slate-300">{item.date}</span>
                            <span className="text-amber-300 font-bold">
                              {fmtPrice(item.amount)}/lbr ({item.yield_at_current_pct}%)
                            </span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="p-3 rounded-lg bg-slate-950/60 border border-slate-800 text-xs text-slate-400">
                        {isIndex
                          ? 'Indeks gabungan tidak membagikan dividen secara langsung.'
                          : 'Emiten ini belum membagikan dividen tunai dalam 3 tahun terakhir.'}
                      </div>
                    )}
                  </div>
                </div>

                <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-xs font-mono">
                  <span className="text-slate-400 font-sans">Estimasi Dividen / 1 Lot:</span>
                  <strong className="text-amber-300">{fmtPrice(div.annual_dividend_per_lot)} / thn</strong>
                </div>
              </div>
            </div>

            {/* ROW 2: Ringkasan Analisa Singkat + Indikator Teknikal + Simulasi Modal & Lot */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
              {/* Kesimpulan Analisa Singkat & Grafik 30 Hari (7 cols) */}
              <div className="lg:col-span-7 rounded-2xl border border-slate-800/90 bg-[#0b101d] p-5 space-y-4 shadow-lg">
                <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                  <h3 className="text-sm font-extrabold uppercase tracking-wide text-white flex items-center gap-2">
                    <LucideIcon name="area-chart" className="w-4 h-4 text-emerald-400" />
                    Kesimpulan Analisa Singkat &amp; Pergerakan 30 Hari ({stockData.code})
                  </h3>
                  <span className="text-[11px] font-mono text-slate-400">{stockData.updated_at}</span>
                </div>

                {/* Bullet Summary Notes */}
                <div className="space-y-2">
                  {(stockData.summary_notes || []).map((note: string, i: number) => (
                    <div
                      key={i}
                      className="flex items-start gap-2.5 p-3 rounded-xl bg-slate-950/70 border border-slate-800/80 text-xs text-slate-200 leading-relaxed"
                    >
                      <span className="text-emerald-400 font-bold mt-0.5">✔</span>
                      <span>{note}</span>
                    </div>
                  ))}
                </div>

                {/* Mini 30-Day Price Bar/Spark Chart */}
                {candles.length > 2 && (
                  <div className="pt-2 space-y-2">
                    <div className="flex items-center justify-between text-[11px] text-slate-400">
                      <span>Grafik Penutupan 30 Hari Bursa Terakhir</span>
                      <span className="font-mono text-slate-300">
                        Rentang: {fmtPrice(Math.min(...candles.map((c) => c.low)))} –{' '}
                        {fmtPrice(Math.max(...candles.map((c) => c.high)))}
                      </span>
                    </div>
                    <div className="h-28 w-full bg-slate-950/90 rounded-xl border border-slate-800/80 p-3 flex items-end gap-1">
                      {(() => {
                        const minC = Math.min(...candles.map((c) => c.close));
                        const maxC = Math.max(...candles.map((c) => c.close));
                        const span = Math.max(1, maxC - minC);
                        return candles.map((c, idx) => {
                          const hPct = Math.max(12, Math.round(((c.close - minC) / span) * 100));
                          const isUp = c.close >= c.open;
                          return (
                            <div
                              key={idx}
                              title={`${c.date}: ${fmtPrice(c.close)}`}
                              className={`flex-1 rounded-t transition-all ${
                                isUp ? 'bg-emerald-500/70 hover:bg-emerald-400' : 'bg-rose-500/70 hover:bg-rose-400'
                              }`}
                              style={{ height: `${hPct}%` }}
                            />
                          );
                        });
                      })()}
                    </div>
                  </div>
                )}
              </div>

              {/* Indikator Teknikal & Kalkulator Simulasi Lot BEI (5 cols) */}
              <div className="lg:col-span-5 rounded-2xl border border-slate-800/90 bg-[#0b101d] p-5 space-y-4 shadow-lg flex flex-col justify-between">
                <div className="space-y-3">
                  <h3 className="text-sm font-extrabold uppercase tracking-wide text-white border-b border-slate-800 pb-3">
                    📊 Indikator Teknikal &amp; Kalkulator Lot
                  </h3>

                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5 font-mono text-xs">
                    <div className="p-2.5 rounded-xl bg-slate-950/80 border border-slate-800">
                      <div className="text-[10px] text-slate-400 font-sans">RSI (14 Hari)</div>
                      <div className="text-sm font-bold text-cyan-300 mt-0.5">{tech.rsi_14}</div>
                      <div className="text-[9px] text-slate-400 font-sans truncate">{tech.rsi_status}</div>
                    </div>
                    <div className="p-2.5 rounded-xl bg-slate-950/80 border border-slate-800">
                      <div className="text-[10px] text-slate-400 font-sans">MA-20 (Pendek)</div>
                      <div className="text-sm font-bold text-white mt-0.5">{fmtPrice(tech.ma_20)}</div>
                      <div
                        className={`text-[9px] font-sans font-semibold ${
                          stockData.current_price >= tech.ma_20 ? 'text-emerald-400' : 'text-rose-400'
                        }`}
                      >
                        {stockData.current_price >= tech.ma_20 ? 'Di atas MA-20' : 'Di bawah MA-20'}
                      </div>
                    </div>
                    <div className="p-2.5 rounded-xl bg-slate-950/80 border border-slate-800">
                      <div className="text-[10px] text-slate-400 font-sans">MA-50 (Menengah)</div>
                      <div className="text-sm font-bold text-white mt-0.5">{fmtPrice(tech.ma_50)}</div>
                      <div
                        className={`text-[9px] font-sans font-semibold ${
                          stockData.current_price >= tech.ma_50 ? 'text-emerald-400' : 'text-rose-400'
                        }`}
                      >
                        {stockData.current_price >= tech.ma_50 ? 'Di atas MA-50' : 'Di bawah MA-50'}
                      </div>
                    </div>
                    <div className="p-2.5 rounded-xl bg-slate-950/80 border border-slate-800">
                      <div className="text-[10px] text-slate-400 font-sans">MA-200 (Major)</div>
                      <div className="text-sm font-bold text-white mt-0.5">{fmtPrice(tech.ma_200)}</div>
                      <div
                        className={`text-[9px] font-sans font-semibold ${
                          stockData.current_price >= tech.ma_200 ? 'text-emerald-400' : 'text-amber-400'
                        }`}
                      >
                        {stockData.current_price >= tech.ma_200 ? 'Major Uptrend' : 'Area Diskon'}
                      </div>
                    </div>
                    <div className="p-2.5 rounded-xl bg-slate-950/80 border border-slate-800">
                      <div className="text-[10px] text-slate-400 font-sans">MACD Hist</div>
                      <div
                        className={`text-sm font-bold mt-0.5 ${
                          tech.macd_histogram >= 0 ? 'text-emerald-400' : 'text-rose-400'
                        }`}
                      >
                        {tech.macd_histogram >= 0 ? '+' : ''}
                        {tech.macd_histogram}
                      </div>
                      <div className="text-[9px] text-slate-400 font-sans">Momentum</div>
                    </div>
                    <div className="p-2.5 rounded-xl bg-slate-950/80 border border-slate-800">
                      <div className="text-[10px] text-slate-400 font-sans">Rasio Volume</div>
                      <div className="text-sm font-bold text-amber-300 mt-0.5">{tech.volume_ratio}x</div>
                      <div className="text-[9px] text-slate-400 font-sans">vs Rata2 20H</div>
                    </div>
                  </div>
                </div>

                {/* Interactive Lot Simulator */}
                <div className="p-4 rounded-xl bg-slate-950/90 border border-emerald-500/30 space-y-3">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-bold text-emerald-300">
                      🧮 Simulasi Beli Lot ({stockData.code} • TF {plan.timeframe_label || '1 Hari'})
                    </span>
                    <div className="flex items-center gap-1.5">
                      <span className="text-[11px] text-slate-400">Jumlah Lot:</span>
                      <input
                        type="number"
                        min={1}
                        max={100000}
                        value={simLots}
                        onChange={(e) => setSimLots(Math.max(1, Number(e.target.value) || 1))}
                        className="w-20 bg-slate-900 border border-slate-700 rounded-lg px-2 py-1 text-xs font-mono font-bold text-white text-right"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                    <div className="p-2 rounded-lg bg-slate-900/90 border border-slate-800">
                      <div className="text-[10px] text-slate-400 font-sans">
                        Modal ({lotsCount} Lot = {sharesCount.toLocaleString('id-ID')} lbr)
                      </div>
                      <div className="font-bold text-white mt-0.5">{fmtPrice(totalCapital)}</div>
                    </div>
                    <div className="p-2 rounded-lg bg-slate-900/90 border border-slate-800">
                      <div className="text-[10px] text-slate-400 font-sans">Est. Dividen / Tahun</div>
                      <div className="font-bold text-amber-300 mt-0.5">{fmtPrice(estAnnualDivTotal)}</div>
                    </div>
                    <div className="p-2 rounded-lg bg-slate-900/90 border border-slate-800">
                      <div className="text-[10px] text-slate-400 font-sans">
                        Potensi Cuan TP 1 (+{plan.tp_1_pct}%)
                      </div>
                      <div className="font-bold text-emerald-400 mt-0.5">+{fmtPrice(estProfitTp1)}</div>
                    </div>
                    <div className="p-2 rounded-lg bg-slate-900/90 border border-slate-800">
                      <div className="text-[10px] text-slate-400 font-sans">
                        Potensi Cuan TP 2 (+{plan.tp_2_pct}%)
                      </div>
                      <div className="font-bold text-teal-400 mt-0.5">+{fmtPrice(estProfitTp2)}</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </>
        ) : null}
      </div>
    </>
  );
}
