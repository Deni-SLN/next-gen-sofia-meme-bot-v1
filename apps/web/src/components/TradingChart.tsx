import React, { useState, useMemo, useEffect } from 'react';
import { LucideIcon } from '@/components/LucideIcon';

export interface CandleData {
  date?: string;
  time?: string | number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

interface TradingChartProps {
  candles: CandleData[];
  symbol: string;
  timeframe?: string;
  currency?: string;
  technicalAudit?: any;
  height?: number;
  initialFocus?: 'ALL' | 'SNR' | 'SMC' | 'EMA200' | 'ICHIMOKU' | 'FIBONACCI';
  onFocusChange?: (id: 'ALL' | 'SNR' | 'SMC' | 'EMA200' | 'ICHIMOKU' | 'FIBONACCI') => void;
}

export function TradingChart({
  candles = [],
  symbol,
  timeframe = '1d',
  currency = 'IDR',
  technicalAudit,
  height = 460,
  initialFocus = 'SNR',
  onFocusChange,
}: TradingChartProps) {
  // Mode Fokus Indikator yang dipilih pengguna
  const [activeMode, setActiveMode] = useState<'ALL' | 'SNR' | 'SMC' | 'EMA200' | 'ICHIMOKU' | 'FIBONACCI'>(initialFocus);

  useEffect(() => {
    if (initialFocus) {
      setActiveMode(initialFocus);
    }
  }, [initialFocus]);

  const handleModeChange = (mode: 'ALL' | 'SNR' | 'SMC' | 'EMA200' | 'ICHIMOKU' | 'FIBONACCI') => {
    setActiveMode(mode);
    onFocusChange?.(mode);
  };

  // Hover Tooltip Crosshair
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  // Theme Awareness (Stockbit Light Mode synchronization)
  const [isLight, setIsLight] = useState<boolean>(false);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const checkTheme = () => {
        const saved = localStorage.getItem('sofia_theme');
        setIsLight(saved === 'light' || document.documentElement.classList.contains('light-theme'));
      };
      checkTheme();

      const themeHandler = (e: any) => {
        setIsLight(e?.detail === 'light');
      };
      window.addEventListener('sofia-theme-change', themeHandler);
      return () => window.removeEventListener('sofia-theme-change', themeHandler);
    }
  }, []);

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

  // Dimensions
  const padding = { top: 25, right: 85, bottom: 45, left: 20 };
  const svgWidth = 880;
  const svgHeight = height;
  const chartWidth = svgWidth - padding.left - padding.right;
  const chartHeight = svgHeight - padding.top - padding.bottom;
  const volumeHeight = 55;
  const priceChartHeight = chartHeight - volumeHeight - 15;

  const validCandles = useMemo(() => {
    if (!candles || !Array.isArray(candles) || candles.length === 0) return [];
    return candles.filter((c) => c && c.close > 0);
  }, [candles]);

  const n = validCandles.length;

  // Extract indicator data from technicalAudit
  const snrData = technicalAudit?.indicators?.SNR;
  const smcData = technicalAudit?.indicators?.SMC;
  const emaData = technicalAudit?.indicators?.EMA200;
  const ichimokuData = technicalAudit?.indicators?.ICHIMOKU;
  const fiboData = technicalAudit?.indicators?.FIBONACCI;

  // Min and Max prices for scaling
  const { minPrice, maxPrice, maxVol } = useMemo(() => {
    if (n === 0) return { minPrice: 0, maxPrice: 100, maxVol: 100 };
    let minP = Infinity;
    let maxP = -Infinity;
    let maxV = 0;

    validCandles.forEach((c) => {
      if (c.low < minP) minP = c.low;
      if (c.high > maxP) maxP = c.high;
      if (c.volume && c.volume > maxV) maxV = c.volume;
    });

    // Also consider key indicator levels to prevent clipping
    if (snrData?.values?.nearest_support && snrData.values.nearest_support < minP) {
      minP = snrData.values.nearest_support * 0.99;
    }
    if (snrData?.values?.nearest_resistance && snrData.values.nearest_resistance > maxP) {
      maxP = snrData.values.nearest_resistance * 1.01;
    }
    if (fiboData?.levels?.fib_100) {
      minP = Math.min(minP, fiboData.levels.fib_100 * 0.99);
      maxP = Math.max(maxP, fiboData.levels.fib_0 * 1.01);
    }

    const span = Math.max(1e-6, maxP - minP);
    return {
      minPrice: Math.max(0, minP - span * 0.05),
      maxPrice: maxP + span * 0.05,
      maxVol: maxV || 100,
    };
  }, [validCandles, n, snrData, fiboData]);

  // Coordinate mappers
  const getX = (idx: number) => {
    if (n <= 1) return padding.left + chartWidth / 2;
    return padding.left + (idx / (n - 1)) * chartWidth;
  };

  const getY = (price: number) => {
    if (maxPrice === minPrice) return padding.top + priceChartHeight / 2;
    const ratio = (price - minPrice) / (maxPrice - minPrice);
    return padding.top + (1 - ratio) * priceChartHeight;
  };

  const getVolY = (vol: number) => {
    const ratio = maxVol > 0 ? Math.min(1, vol / maxVol) : 0;
    const base = padding.top + priceChartHeight + 15 + volumeHeight;
    return base - ratio * volumeHeight;
  };

  const candleWidth = Math.max(2, Math.min(14, (chartWidth / Math.max(1, n)) * 0.72));

  const hoveredCandle = hoverIndex !== null && validCandles[hoverIndex] ? validCandles[hoverIndex] : validCandles[n - 1];

  if (n === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-64 bg-obsidian-900/60 border border-obsidian-800 rounded-xl text-slate-500 font-mono text-xs">
        <LucideIcon name="bar-chart-2" className="w-8 h-8 mb-2 opacity-50" />
        Data chart tidak tersedia untuk timeframe ini.
      </div>
    );
  }

  // Generate Price Grid Lines
  const priceGridCount = 5;
  const priceGridLevels = Array.from({ length: priceGridCount }).map((_, i) => {
    const p = minPrice + ((maxPrice - minPrice) * i) / (priceGridCount - 1);
    return { price: p, y: getY(p) };
  });

  return (
    <div className={`w-full ${isLight ? 'bg-white border-slate-200 shadow-sm' : 'bg-[#090d16] border-obsidian-800 shadow-2xl'} border rounded-2xl p-4 sm:p-5 space-y-3.5`}>
      {/* Chart Header: Title, Price OHLCV, and Indicator Focus Buttons */}
      <div className={`flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3 pb-3 border-b ${isLight ? 'border-slate-200' : 'border-obsidian-800'}`}>
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <span className={`font-extrabold text-base sm:text-lg font-mono ${isLight ? 'text-slate-900' : 'text-white'}`}>
              {symbol}
            </span>
            <span className="px-2 py-0.5 rounded text-[11px] font-mono font-bold bg-cyan-500/15 text-cyan-500 border border-cyan-500/30">
              {timeframe.toUpperCase()}
            </span>
          </div>

          {hoveredCandle && (
            <div className={`flex items-center gap-2.5 text-[11px] font-mono px-3 py-1 rounded-lg border ${
              isLight ? 'bg-slate-50 border-slate-200 text-slate-600' : 'bg-obsidian-950 border-obsidian-800 text-slate-400'
            }`}>
              <span>O: <strong className={isLight ? 'text-slate-900' : 'text-slate-200'}>{formatPrice(hoveredCandle.open)}</strong></span>
              <span>H: <strong className="text-emerald-500">{formatPrice(hoveredCandle.high)}</strong></span>
              <span>L: <strong className="text-rose-500">{formatPrice(hoveredCandle.low)}</strong></span>
              <span>C: <strong className={hoveredCandle.close >= hoveredCandle.open ? 'text-emerald-500' : 'text-rose-500'}>
                {formatPrice(hoveredCandle.close)}
              </strong></span>
            </div>
          )}
        </div>

        {/* INTERACTIVE INDICATOR FOCUS SELECTOR BUTTONS */}
        <div className="flex items-center gap-1.5 flex-wrap font-mono text-xs">
          <span className={`text-[10px] font-bold uppercase tracking-wider mr-1 ${isLight ? 'text-slate-500' : 'text-slate-400'}`}>
            Sorot di Chart:
          </span>

          <button
            type="button"
            onClick={() => handleModeChange('SNR')}
            className={`px-3 py-1.5 rounded-lg border font-bold transition flex items-center gap-1.5 ${
              activeMode === 'SNR'
                ? 'bg-emerald-500/25 border-emerald-500 text-emerald-600 shadow-sm ring-1 ring-emerald-500'
                : isLight
                ? 'bg-slate-100 border-slate-200 text-slate-600 hover:text-slate-900 hover:bg-slate-200/70'
                : 'bg-obsidian-950 border-obsidian-700 text-slate-400 hover:text-white'
            }`}
          >
            <span>🛡️ SNR (Support &amp; Resistance)</span>
          </button>

          <button
            type="button"
            onClick={() => handleModeChange('SMC')}
            className={`px-3 py-1.5 rounded-lg border font-bold transition flex items-center gap-1.5 ${
              activeMode === 'SMC'
                ? 'bg-cyan-500/25 border-cyan-500 text-cyan-600 shadow-sm ring-1 ring-cyan-500'
                : isLight
                ? 'bg-slate-100 border-slate-200 text-slate-600 hover:text-slate-900 hover:bg-slate-200/70'
                : 'bg-obsidian-950 border-obsidian-700 text-slate-400 hover:text-white'
            }`}
          >
            <span>📦 SMC (Order Blocks &amp; FVG)</span>
          </button>

          <button
            type="button"
            onClick={() => handleModeChange('EMA200')}
            className={`px-3 py-1.5 rounded-lg border font-bold transition flex items-center gap-1.5 ${
              activeMode === 'EMA200'
                ? 'bg-amber-500/25 border-amber-500 text-amber-700 shadow-sm ring-1 ring-amber-500'
                : isLight
                ? 'bg-slate-100 border-slate-200 text-slate-600 hover:text-slate-900 hover:bg-slate-200/70'
                : 'bg-obsidian-950 border-obsidian-700 text-slate-400 hover:text-white'
            }`}
          >
            <span>📈 EMA 200</span>
          </button>

          <button
            type="button"
            onClick={() => handleModeChange('ICHIMOKU')}
            className={`px-3 py-1.5 rounded-lg border font-bold transition flex items-center gap-1.5 ${
              activeMode === 'ICHIMOKU'
                ? 'bg-purple-500/25 border-purple-500 text-purple-700 shadow-sm ring-1 ring-purple-500'
                : isLight
                ? 'bg-slate-100 border-slate-200 text-slate-600 hover:text-slate-900 hover:bg-slate-200/70'
                : 'bg-obsidian-950 border-obsidian-700 text-slate-400 hover:text-white'
            }`}
          >
            <span>☁️ Ichimoku Cloud</span>
          </button>

          <button
            type="button"
            onClick={() => handleModeChange('FIBONACCI')}
            className={`px-3 py-1.5 rounded-lg border font-bold transition flex items-center gap-1.5 ${
              activeMode === 'FIBONACCI'
                ? 'bg-blue-500/25 border-blue-500 text-blue-700 shadow-sm ring-1 ring-blue-500'
                : isLight
                ? 'bg-slate-100 border-slate-200 text-slate-600 hover:text-slate-900 hover:bg-slate-200/70'
                : 'bg-obsidian-950 border-obsidian-700 text-slate-400 hover:text-white'
            }`}
          >
            <span>🎯 Fibonacci</span>
          </button>

          <button
            type="button"
            onClick={() => handleModeChange('ALL')}
            className={`px-2.5 py-1.5 rounded-lg border font-bold transition ${
              activeMode === 'ALL'
                ? 'bg-slate-800 border-slate-600 text-white'
                : isLight
                ? 'bg-slate-100 border-slate-200 text-slate-600 hover:text-slate-900 hover:bg-slate-200/70'
                : 'bg-obsidian-950 border-obsidian-800 text-slate-500 hover:text-slate-300'
            }`}
          >
            Semua
          </button>
        </div>
      </div>

      {/* SVG Candlestick & Overlays Canvas */}
      <div className="relative w-full overflow-hidden select-none">
        <svg
          viewBox={`0 0 ${svgWidth} ${svgHeight}`}
          className="w-full h-auto cursor-crosshair block"
          onMouseLeave={() => setHoverIndex(null)}
          onMouseMove={(e) => {
            const rect = e.currentTarget.getBoundingClientRect();
            const relX = ((e.clientX - rect.left) / rect.width) * svgWidth;
            if (relX >= padding.left && relX <= padding.left + chartWidth) {
              const fraction = (relX - padding.left) / chartWidth;
              const idx = Math.min(n - 1, Math.max(0, Math.round(fraction * (n - 1))));
              setHoverIndex(idx);
            }
          }}
        >
          <defs>
            {/* Gradients */}
            <linearGradient id="cloudGreen" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#10b981" stopOpacity="0.30" />
              <stop offset="100%" stopColor="#10b981" stopOpacity="0.08" />
            </linearGradient>
            <linearGradient id="cloudRed" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#f43f5e" stopOpacity="0.30" />
              <stop offset="100%" stopColor="#f43f5e" stopOpacity="0.08" />
            </linearGradient>
            <linearGradient id="goldenPocketGrad" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#eab308" stopOpacity="0.25" />
              <stop offset="100%" stopColor="#eab308" stopOpacity="0.08" />
            </linearGradient>
          </defs>

          {/* Background Grid Lines */}
          {priceGridLevels.map((lvl, idx) => (
            <g key={idx}>
              <line
                x1={padding.left}
                y1={lvl.y}
                x2={padding.left + chartWidth}
                y2={lvl.y}
                stroke={isLight ? '#e2e8f0' : '#151d2e'}
                strokeDasharray="3 3"
                strokeWidth="1"
              />
              <text
                x={padding.left + chartWidth + 6}
                y={lvl.y + 3.5}
                fill={isLight ? '#64748b' : '#64748b'}
                fontSize="9"
                fontFamily="monospace"
              >
                {formatPrice(lvl.price)}
              </text>
            </g>
          ))}

          {/* Separator for Volume Sub-chart */}
          <line
            x1={padding.left}
            y1={padding.top + priceChartHeight + 10}
            x2={padding.left + chartWidth}
            y2={padding.top + priceChartHeight + 10}
            stroke={isLight ? '#e2e8f0' : '#1e293b'}
            strokeWidth="1"
          />

          {/* =========================================================================
              OVERLAY 1: SNR (SUPPORT & RESISTANCE) — SANGAT JELAS DENGAN GARIS TEBAL & BADGE
             ========================================================================= */}
          {(activeMode === 'SNR' || activeMode === 'ALL') && snrData && (
            <g id="snr-zones-focused">
              {/* Active Supports */}
              {snrData.levels?.supports?.map((sup: any, sIdx: number) => {
                const y = getY(sup.price_level);
                const yLow = getY(sup.zone_low);
                const yHigh = getY(sup.zone_high);
                const zoneH = Math.max(4, Math.abs(yLow - yHigh));

                return (
                  <g key={`sup-${sIdx}`}>
                    {/* Shaded Support Zone Band */}
                    <rect
                      x={padding.left}
                      y={Math.min(yLow, yHigh)}
                      width={chartWidth}
                      height={zoneH}
                      fill="#10b981"
                      fillOpacity={activeMode === 'SNR' ? '0.22' : '0.12'}
                    />
                    {/* Solid Vivid Support Line */}
                    <line
                      x1={padding.left}
                      y1={y}
                      x2={padding.left + chartWidth}
                      y2={y}
                      stroke="#10b981"
                      strokeWidth={activeMode === 'SNR' ? '2.2' : '1.5'}
                      strokeDasharray={activeMode === 'SNR' ? 'none' : '5 3'}
                    />
                    {/* Left Tag Badge */}
                    <rect
                      x={padding.left + 4}
                      y={y - 9}
                      width={110}
                      height={18}
                      rx="3"
                      fill="#064e3b"
                      stroke="#10b981"
                      strokeWidth="1"
                    />
                    <text
                      x={padding.left + 8}
                      y={y + 3.5}
                      fill="#6ee7b7"
                      fontSize="9"
                      fontFamily="monospace"
                      fontWeight="bold"
                    >
                      SUPPORT {sIdx + 1}
                    </text>
                    {/* Right Price Label */}
                    <rect
                      x={padding.left + chartWidth - 85}
                      y={y - 9}
                      width={80}
                      height={18}
                      rx="3"
                      fill="#064e3b"
                      stroke="#10b981"
                      strokeWidth="1"
                    />
                    <text
                      x={padding.left + chartWidth - 45}
                      y={y + 3.5}
                      fill="#a7f3d0"
                      fontSize="9"
                      fontFamily="monospace"
                      fontWeight="bold"
                      textAnchor="middle"
                    >
                      {formatPrice(sup.price_level)}
                    </text>
                  </g>
                );
              })}

              {/* Active Resistances */}
              {snrData.levels?.resistances?.map((res: any, rIdx: number) => {
                const y = getY(res.price_level);
                const yLow = getY(res.zone_low);
                const yHigh = getY(res.zone_high);
                const zoneH = Math.max(4, Math.abs(yLow - yHigh));

                return (
                  <g key={`res-${rIdx}`}>
                    {/* Shaded Resistance Zone Band */}
                    <rect
                      x={padding.left}
                      y={Math.min(yLow, yHigh)}
                      width={chartWidth}
                      height={zoneH}
                      fill="#f43f5e"
                      fillOpacity={activeMode === 'SNR' ? '0.22' : '0.12'}
                    />
                    {/* Solid Vivid Resistance Line */}
                    <line
                      x1={padding.left}
                      y1={y}
                      x2={padding.left + chartWidth}
                      y2={y}
                      stroke="#f43f5e"
                      strokeWidth={activeMode === 'SNR' ? '2.2' : '1.5'}
                      strokeDasharray={activeMode === 'SNR' ? 'none' : '5 3'}
                    />
                    {/* Left Tag Badge */}
                    <rect
                      x={padding.left + 4}
                      y={y - 9}
                      width={125}
                      height={18}
                      rx="3"
                      fill="#881337"
                      stroke="#f43f5e"
                      strokeWidth="1"
                    />
                    <text
                      x={padding.left + 8}
                      y={y + 3.5}
                      fill="#fca5a5"
                      fontSize="9"
                      fontFamily="monospace"
                      fontWeight="bold"
                    >
                      RESISTANCE {rIdx + 1}
                    </text>
                    {/* Right Price Label */}
                    <rect
                      x={padding.left + chartWidth - 85}
                      y={y - 9}
                      width={80}
                      height={18}
                      rx="3"
                      fill="#881337"
                      stroke="#f43f5e"
                      strokeWidth="1"
                    />
                    <text
                      x={padding.left + chartWidth - 45}
                      y={y + 3.5}
                      fill="#fecdd3"
                      fontSize="9"
                      fontFamily="monospace"
                      fontWeight="bold"
                      textAnchor="middle"
                    >
                      {formatPrice(res.price_level)}
                    </text>
                  </g>
                );
              })}
            </g>
          )}

          {/* =========================================================================
              OVERLAY 2: SMC (ORDER BLOCKS, FVGS & LIQUIDITY)
             ========================================================================= */}
          {(activeMode === 'SMC' || activeMode === 'ALL') && smcData && (
            <g id="smc-elements">
              {/* Order Blocks with vivid dashed outlines */}
              {smcData.levels?.order_blocks?.map((ob: any, oIdx: number) => {
                const y1 = getY(ob.top);
                const y2 = getY(ob.bottom);
                const h = Math.max(4, Math.abs(y2 - y1));
                const isBull = ob.type === 'BULLISH_OB';
                const startX = padding.left + chartWidth * 0.35;
                const obWidth = chartWidth * 0.65;

                return (
                  <g key={`ob-${oIdx}`}>
                    <rect
                      x={startX}
                      y={Math.min(y1, y2)}
                      width={obWidth}
                      height={h}
                      fill={isBull ? '#06b6d4' : '#ec4899'}
                      fillOpacity={activeMode === 'SMC' ? '0.22' : '0.12'}
                      stroke={isBull ? '#06b6d4' : '#ec4899'}
                      strokeWidth={activeMode === 'SMC' ? '1.8' : '1'}
                      strokeDasharray="4 2"
                    />
                    <text
                      x={startX + 6}
                      y={Math.min(y1, y2) + 11}
                      fill={isBull ? (isLight ? '#0369a1' : '#22d3ee') : (isLight ? '#be185d' : '#f472b6')}
                      fontSize="8.5"
                      fontFamily="monospace"
                      fontWeight="bold"
                    >
                      {isBull ? 'DEMAND ORDER BLOCK' : 'SUPPLY ORDER BLOCK'} ({ob.status})
                    </text>
                  </g>
                );
              })}

              {/* Fair Value Gaps (FVG) */}
              {smcData.levels?.fair_value_gaps?.map((fvg: any, fIdx: number) => {
                const y1 = getY(fvg.top);
                const y2 = getY(fvg.bottom);
                const h = Math.max(3, Math.abs(y2 - y1));
                return (
                  <g key={`fvg-${fIdx}`}>
                    <rect
                      x={padding.left + chartWidth * 0.55}
                      y={Math.min(y1, y2)}
                      width={chartWidth * 0.45}
                      height={h}
                      fill="#eab308"
                      fillOpacity="0.2"
                      stroke="#eab308"
                      strokeWidth="1.2"
                      strokeDasharray="3 2"
                    />
                    <text
                      x={padding.left + chartWidth * 0.57}
                      y={Math.min(y1, y2) + 9}
                      fill={isLight ? '#b45309' : '#fde047'}
                      fontSize="8"
                      fontFamily="monospace"
                      fontWeight="bold"
                    >
                      FVG GAP
                    </text>
                  </g>
                );
              })}
            </g>
          )}

          {/* =========================================================================
              OVERLAY 3: EMA 200 (EXPONENTIAL MOVING AVERAGE)
             ========================================================================= */}
          {(activeMode === 'EMA200' || activeMode === 'ALL') && emaData?.values?.ema_200 && (
            <g id="ema-200">
              <line
                x1={padding.left}
                y1={getY(emaData.values.ema_200)}
                x2={padding.left + chartWidth}
                y2={getY(emaData.values.ema_200)}
                stroke="#f59e0b"
                strokeWidth={activeMode === 'EMA200' ? '3' : '2'}
              />
              {/* Badge */}
              <rect
                x={padding.left + chartWidth - 90}
                y={getY(emaData.values.ema_200) - 10}
                width={85}
                height={19}
                rx="3"
                fill="#78350f"
                stroke="#f59e0b"
                strokeWidth="1"
              />
              <text
                x={padding.left + chartWidth - 47}
                y={getY(emaData.values.ema_200) + 3.5}
                fill="#fde68a"
                fontSize="9"
                fontFamily="monospace"
                fontWeight="bold"
                textAnchor="middle"
              >
                EMA 200: {formatPrice(emaData.values.ema_200)}
              </text>
            </g>
          )}

          {/* =========================================================================
              OVERLAY 4: ICHIMOKU CLOUD (KINKO HYO)
             ========================================================================= */}
          {(activeMode === 'ICHIMOKU' || activeMode === 'ALL') && ichimokuData?.levels && (
            <g id="ichimoku-kumo">
              {ichimokuData.levels.cloud_top && ichimokuData.levels.cloud_bottom && (
                <rect
                  x={padding.left}
                  y={getY(ichimokuData.levels.cloud_top)}
                  width={chartWidth}
                  height={Math.max(4, Math.abs(getY(ichimokuData.levels.cloud_bottom) - getY(ichimokuData.levels.cloud_top)))}
                  fill="url(#cloudGreen)"
                  stroke="#10b981"
                  strokeWidth="1"
                  strokeDasharray="3 3"
                />
              )}
              {/* Tenkan Line (Biru) */}
              {ichimokuData.levels.tenkan && (
                <line
                  x1={padding.left}
                  y1={getY(ichimokuData.levels.tenkan)}
                  x2={padding.left + chartWidth}
                  y2={getY(ichimokuData.levels.tenkan)}
                  stroke="#38bdf8"
                  strokeWidth="1.8"
                />
              )}
              {/* Kijun Line (Merah) */}
              {ichimokuData.levels.kijun && (
                <line
                  x1={padding.left}
                  y1={getY(ichimokuData.levels.kijun)}
                  x2={padding.left + chartWidth}
                  y2={getY(ichimokuData.levels.kijun)}
                  stroke="#f43f5e"
                  strokeWidth="1.8"
                />
              )}
            </g>
          )}

          {/* =========================================================================
              OVERLAY 5: FIBONACCI RETRACEMENT & GOLDEN POCKET
             ========================================================================= */}
          {(activeMode === 'FIBONACCI' || activeMode === 'ALL') && fiboData?.levels && (
            <g id="fibonacci-levels">
              {/* Golden Pocket Shade (50% - 61.8%) */}
              {fiboData.levels.golden_pocket_min && fiboData.levels.golden_pocket_max && (
                <g>
                  <rect
                    x={padding.left}
                    y={getY(fiboData.levels.golden_pocket_max)}
                    width={chartWidth}
                    height={Math.max(4, getY(fiboData.levels.golden_pocket_min) - getY(fiboData.levels.golden_pocket_max))}
                    fill="url(#goldenPocketGrad)"
                    stroke="#eab308"
                    strokeWidth="1"
                  />
                  <text
                    x={padding.left + 8}
                    y={getY(fiboData.levels.golden_pocket_max) + 12}
                    fill={isLight ? '#92400e' : '#fef08a'}
                    fontSize="9"
                    fontFamily="monospace"
                    fontWeight="bold"
                  >
                    ★ GOLDEN POCKET (50% – 61.8%)
                  </text>
                </g>
              )}

              {[
                { label: '0.0% (High)', val: fiboData.levels.fib_0 },
                { label: '23.6%', val: fiboData.levels.fib_236 },
                { label: '38.2%', val: fiboData.levels.fib_382 },
                { label: '50.0% (Eq)', val: fiboData.levels.fib_500, highlight: true },
                { label: '61.8% (Gold)', val: fiboData.levels.fib_618, highlight: true },
                { label: '78.6%', val: fiboData.levels.fib_786 },
                { label: '100.0% (Low)', val: fiboData.levels.fib_100 },
                { label: '161.8% (Ext)', val: fiboData.levels.fib_1618 },
              ]
                .filter((f) => f.val && f.val >= minPrice && f.val <= maxPrice)
                .map((f, fIdx) => (
                  <g key={`fib-lvl-${fIdx}`}>
                    <line
                      x1={padding.left}
                      y1={getY(f.val)}
                      x2={padding.left + chartWidth}
                      y2={getY(f.val)}
                      stroke={f.highlight ? '#eab308' : '#38bdf8'}
                      strokeWidth={f.highlight ? '1.8' : '1'}
                      strokeDasharray={f.highlight ? 'none' : '4 3'}
                      strokeOpacity={f.highlight ? '0.9' : '0.6'}
                    />
                    <text
                      x={padding.left + chartWidth - 6}
                      y={getY(f.val) - 3}
                      fill={f.highlight ? (isLight ? '#b45309' : '#fde047') : (isLight ? '#0369a1' : '#7dd3fc')}
                      fontSize="8.5"
                      fontFamily="monospace"
                      fontWeight="bold"
                      textAnchor="end"
                    >
                      Fib {f.label}: {formatPrice(f.val)}
                    </text>
                  </g>
                ))}
            </g>
          )}

          {/* Volume Bars */}
          {validCandles.map((c, idx) => {
            if (!c.volume) return null;
            const x = getX(idx);
            const isBull = c.close >= c.open;
            const topY = getVolY(c.volume);
            const base = padding.top + priceChartHeight + 15 + volumeHeight;
            const h = Math.max(1, base - topY);

            return (
              <rect
                key={`vol-${idx}`}
                x={x - candleWidth / 2}
                y={topY}
                width={candleWidth}
                height={h}
                fill={isBull ? '#10b981' : '#f43f5e'}
                fillOpacity="0.35"
              />
            );
          })}

          {/* Candlesticks */}
          {validCandles.map((c, idx) => {
            const x = getX(idx);
            const isBull = c.close >= c.open;
            const color = isBull ? '#10b981' : '#f43f5e';
            const highY = getY(c.high);
            const lowY = getY(c.low);
            const openY = getY(c.open);
            const closeY = getY(c.close);
            const bodyTop = Math.min(openY, closeY);
            const bodyHeight = Math.max(1.5, Math.abs(closeY - openY));

            return (
              <g key={`candle-${idx}`}>
                {/* Wicks */}
                <line
                  x1={x}
                  y1={highY}
                  x2={x}
                  y2={lowY}
                  stroke={color}
                  strokeWidth="1.3"
                />
                {/* Body */}
                <rect
                  x={x - candleWidth / 2}
                  y={bodyTop}
                  width={candleWidth}
                  height={bodyHeight}
                  fill={isBull ? '#10b981' : '#f43f5e'}
                  rx="1"
                />
              </g>
            );
          })}

          {/* Interactive Hover Crosshair */}
          {hoverIndex !== null && validCandles[hoverIndex] && (
            <g id="crosshair">
              {/* Vertical line */}
              <line
                x1={getX(hoverIndex)}
                y1={padding.top}
                x2={getX(hoverIndex)}
                y2={padding.top + priceChartHeight + 15 + volumeHeight}
                stroke={isLight ? '#64748b' : '#cbd5e1'}
                strokeWidth="1"
                strokeDasharray="2 2"
              />
              {/* Horizontal line at candle close */}
              <line
                x1={padding.left}
                y1={getY(validCandles[hoverIndex].close)}
                x2={padding.left + chartWidth}
                y2={getY(validCandles[hoverIndex].close)}
                stroke={isLight ? '#64748b' : '#cbd5e1'}
                strokeWidth="1"
                strokeDasharray="2 2"
              />
              {/* Date text bottom */}
              <text
                x={getX(hoverIndex)}
                y={svgHeight - 10}
                fill={isLight ? '#334155' : '#cbd5e1'}
                fontSize="9"
                fontFamily="monospace"
                textAnchor="middle"
                fontWeight="bold"
              >
                {validCandles[hoverIndex].date || ''}
              </text>
            </g>
          )}
        </svg>
      </div>

      {/* DYNAMIC FOCUSED INDICATOR EXPLANATION PANEL */}
      {activeMode === 'SNR' && snrData && (
        <div className="p-3.5 rounded-xl bg-emerald-950/40 border border-emerald-500/40 text-xs font-mono space-y-2">
          <div className="flex items-center justify-between text-emerald-300 font-bold">
            <span className="flex items-center gap-1.5">
              <LucideIcon name="shield" className="w-4 h-4 text-emerald-400" />
              Detail Level Support &amp; Resistance (SNR) di Chart:
            </span>
            <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/20 border border-emerald-500/30">
              {snrData.display_status}
            </span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-2 text-[11px] pt-1">
            <div className="p-2 rounded-lg bg-obsidian-950 border border-obsidian-800">
              <span className="text-slate-400 block text-[10px]">Support 1 Terdekat</span>
              <strong className="text-emerald-400">{formatPrice(snrData.values?.nearest_support)}</strong>
            </div>
            <div className="p-2 rounded-lg bg-obsidian-950 border border-obsidian-800">
              <span className="text-slate-400 block text-[10px]">Resistance 1 Terdekat</span>
              <strong className="text-rose-400">{formatPrice(snrData.values?.nearest_resistance)}</strong>
            </div>
            <div className="p-2 rounded-lg bg-obsidian-950 border border-obsidian-800">
              <span className="text-slate-400 block text-[10px]">Kekuatan Reaksi</span>
              <span className="text-slate-200 font-bold">{snrData.values?.support_strength}</span>
            </div>
            <div className="p-2 rounded-lg bg-obsidian-950 border border-obsidian-800">
              <span className="text-slate-400 block text-[10px]">Status Sinyal</span>
              <span className="text-cyan-300 font-bold">{snrData.signals?.bias}</span>
            </div>
          </div>
          <p className="text-[11px] text-slate-300 leading-relaxed font-sans pt-1">
            {snrData.signals?.summary}
          </p>
        </div>
      )}

      {activeMode === 'SMC' && smcData && (
        <div className="p-3.5 rounded-xl bg-cyan-950/40 border border-cyan-500/40 text-xs font-mono space-y-2">
          <div className="flex items-center justify-between text-cyan-300 font-bold">
            <span className="flex items-center gap-1.5">
              <LucideIcon name="layers" className="w-4 h-4 text-cyan-400" />
              Detail Smart Money Concepts (SMC) di Chart:
            </span>
            <span className="text-[10px] px-2 py-0.5 rounded bg-cyan-500/20 border border-cyan-500/30">
              {smcData.display_status}
            </span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-[11px] pt-1">
            <div className="p-2 rounded-lg bg-obsidian-950 border border-obsidian-800">
              <span className="text-slate-400 block text-[10px]">Struktur Pasar</span>
              <strong className="text-cyan-400">{smcData.values?.market_structure}</strong>
            </div>
            <div className="p-2 rounded-lg bg-obsidian-950 border border-obsidian-800">
              <span className="text-slate-400 block text-[10px]">Dealing Range</span>
              <strong className="text-emerald-400">{smcData.values?.dealing_zone}</strong>
            </div>
            <div className="p-2 rounded-lg bg-obsidian-950 border border-obsidian-800">
              <span className="text-slate-400 block text-[10px]">Order Blocks Aktif</span>
              <strong className="text-purple-400">{smcData.levels?.order_blocks?.length || 0} Terpetakan</strong>
            </div>
          </div>
          <p className="text-[11px] text-slate-300 leading-relaxed font-sans pt-1">
            {smcData.signals?.summary}
          </p>
        </div>
      )}

      {activeMode === 'EMA200' && emaData && (
        <div className="p-3.5 rounded-xl bg-amber-950/40 border border-amber-500/40 text-xs font-mono space-y-2">
          <div className="flex items-center justify-between text-amber-300 font-bold">
            <span className="flex items-center gap-1.5">
              <LucideIcon name="trending-up" className="w-4 h-4 text-amber-400" />
              Detail Filter Tren Major EMA 200 di Chart:
            </span>
            <span className="text-[10px] px-2 py-0.5 rounded bg-amber-500/20 border border-amber-500/30">
              {emaData.display_status}
            </span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-[11px] pt-1">
            <div className="p-2 rounded-lg bg-obsidian-950 border border-obsidian-800">
              <span className="text-slate-400 block text-[10px]">Level Garis EMA 200</span>
              <strong className="text-amber-400">{formatPrice(emaData.values?.ema_200)}</strong>
            </div>
            <div className="p-2 rounded-lg bg-obsidian-950 border border-obsidian-800">
              <span className="text-slate-400 block text-[10px]">Jarak Harga ke EMA</span>
              <strong className={emaData.values?.distance_pct >= 0 ? 'text-emerald-400' : 'text-rose-400'}>
                {emaData.values?.distance_pct >= 0 ? '+' : ''}{emaData.values?.distance_pct}%
              </strong>
            </div>
            <div className="p-2 rounded-lg bg-obsidian-950 border border-obsidian-800">
              <span className="text-slate-400 block text-[10px]">Arah Tren Utama</span>
              <strong className="text-white">{emaData.values?.trend_alignment}</strong>
            </div>
          </div>
          <p className="text-[11px] text-slate-300 leading-relaxed font-sans pt-1">
            {emaData.signals?.summary}
          </p>
        </div>
      )}

      {activeMode === 'ICHIMOKU' && ichimokuData && (
        <div className="p-3.5 rounded-xl bg-purple-950/40 border border-purple-500/40 text-xs font-mono space-y-2">
          <div className="flex items-center justify-between text-purple-300 font-bold">
            <span className="flex items-center gap-1.5">
              <LucideIcon name="cloud" className="w-4 h-4 text-purple-400" />
              Detail Awan Kumo Ichimoku di Chart:
            </span>
            <span className="text-[10px] px-2 py-0.5 rounded bg-purple-500/20 border border-purple-500/30">
              {ichimokuData.display_status}
            </span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-[11px] pt-1">
            <div className="p-2 rounded-lg bg-obsidian-950 border border-obsidian-800">
              <span className="text-slate-400 block text-[10px]">Tenkan / Kijun Line</span>
              <strong className="text-cyan-300">{formatPrice(ichimokuData.values?.tenkan_sen)} / {formatPrice(ichimokuData.values?.kijun_sen)}</strong>
            </div>
            <div className="p-2 rounded-lg bg-obsidian-950 border border-obsidian-800">
              <span className="text-slate-400 block text-[10px]">Rentang Awan Kumo</span>
              <strong className="text-purple-300">{formatPrice(ichimokuData.values?.kumo_lower)} – {formatPrice(ichimokuData.values?.kumo_upper)}</strong>
            </div>
            <div className="p-2 rounded-lg bg-obsidian-950 border border-obsidian-800">
              <span className="text-slate-400 block text-[10px]">Posisi Harga vs Kumo</span>
              <strong className="text-emerald-400">{ichimokuData.values?.cloud_position}</strong>
            </div>
          </div>
          <p className="text-[11px] text-slate-300 leading-relaxed font-sans pt-1">
            {ichimokuData.signals?.summary}
          </p>
        </div>
      )}

      {activeMode === 'FIBONACCI' && fiboData && (
        <div className="p-3.5 rounded-xl bg-blue-950/40 border border-blue-500/40 text-xs font-mono space-y-2">
          <div className="flex items-center justify-between text-blue-300 font-bold">
            <span className="flex items-center gap-1.5">
              <LucideIcon name="git-commit" className="w-4 h-4 text-blue-400" />
              Detail Level Rasio Fibonacci di Chart:
            </span>
            <span className="text-[10px] px-2 py-0.5 rounded bg-blue-500/20 border border-blue-500/30">
              {fiboData.display_status}
            </span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-[11px] pt-1">
            <div className="p-2 rounded-lg bg-obsidian-950 border border-obsidian-800">
              <span className="text-slate-400 block text-[10px]">Golden Pocket (50%–61.8%)</span>
              <strong className="text-amber-300">
                {formatPrice(fiboData.levels?.fib_500)} – {formatPrice(fiboData.levels?.fib_618)}
              </strong>
            </div>
            <div className="p-2 rounded-lg bg-obsidian-950 border border-obsidian-800">
              <span className="text-slate-400 block text-[10px]">Swing High (0%)</span>
              <strong className="text-white">{formatPrice(fiboData.levels?.fib_0)}</strong>
            </div>
            <div className="p-2 rounded-lg bg-obsidian-950 border border-obsidian-800">
              <span className="text-slate-400 block text-[10px]">Swing Low (100%)</span>
              <strong className="text-white">{formatPrice(fiboData.levels?.fib_100)}</strong>
            </div>
          </div>
          <p className="text-[11px] text-slate-300 leading-relaxed font-sans pt-1">
            {fiboData.signals?.summary}
          </p>
        </div>
      )}
    </div>
  );
}
