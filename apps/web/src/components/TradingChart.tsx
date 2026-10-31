import React, { useState, useMemo, useEffect } from 'react';
import { LucideIcon } from '@/components/LucideIcon';
import { CryptoLineChart } from './CryptoLineChart';

export interface CandleData {
  date?: string;
  time?: string | number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

export interface TimeframeOption {
  id: string;
  label: string;
  short?: string;
}

const DEFAULT_TIMEFRAMES: TimeframeOption[] = [
  { id: '15m', label: '15 Menit', short: '15M' },
  { id: '1h', label: '1 Jam', short: '1H' },
  { id: '4h', label: '4 Jam', short: '4H' },
  { id: '1d', label: '1 Hari', short: '1D' },
  { id: '1w', label: '1 Minggu', short: '1W' },
  { id: '1mo', label: '1 Bulan', short: '1M' },
];

interface TradingChartProps {
  candles: CandleData[];
  symbol: string;
  timeframe?: string;
  timeframes?: TimeframeOption[];
  onTimeframeChange?: (tf: string) => void;
  currency?: string;
  technicalAudit?: any;
  height?: number;
  initialFocus?: 'ALL' | 'SNR' | 'SMC' | 'EMA200' | 'ICHIMOKU' | 'FIBONACCI';
  onFocusChange?: (id: 'ALL' | 'SNR' | 'SMC' | 'EMA200' | 'ICHIMOKU' | 'FIBONACCI') => void;
}

interface RightAxisTag {
  id: string;
  rawY: number;
  y: number;
  text: string;
  bg: string;
  border: string;
  color: string;
}

function resolveVerticalCollisions<T extends { rawY: number; y: number }>(
  items: T[],
  minY: number,
  maxY: number,
  minGap: number = 16
): T[] {
  if (items.length <= 1) return items;
  const sorted = [...items].sort((a, b) => a.rawY - b.rawY);
  sorted[0].y = Math.max(minY, Math.min(maxY, sorted[0].rawY));
  for (let i = 1; i < sorted.length; i++) {
    sorted[i].y = Math.max(sorted[i].rawY, sorted[i - 1].y + minGap);
  }
  if (sorted[sorted.length - 1].y > maxY) {
    sorted[sorted.length - 1].y = maxY;
    for (let i = sorted.length - 2; i >= 0; i--) {
      sorted[i].y = Math.min(sorted[i].y, sorted[i + 1].y - minGap);
      sorted[i].y = Math.max(minY, sorted[i].y);
    }
  }
  return sorted;
}

export function TradingChart({
  candles = [],
  symbol,
  timeframe = '1d',
  timeframes = DEFAULT_TIMEFRAMES,
  onTimeframeChange,
  currency = 'IDR',
  technicalAudit,
  height = 480,
  initialFocus = 'SNR',
  onFocusChange,
}: TradingChartProps) {
  const [activeMode, setActiveMode] = useState<'ALL' | 'SNR' | 'SMC' | 'EMA200' | 'ICHIMOKU' | 'FIBONACCI'>(initialFocus);
  const [localTimeframe, setLocalTimeframe] = useState<string>(timeframe.toLowerCase());
  const [chartStyle, setChartStyle] = useState<'candles' | 'line'>('candles');

  useEffect(() => {
    if (initialFocus) {
      setActiveMode(initialFocus);
    }
  }, [initialFocus]);

  useEffect(() => {
    if (timeframe) {
      setLocalTimeframe(timeframe.toLowerCase());
    }
  }, [timeframe]);

  const handleModeChange = (mode: 'ALL' | 'SNR' | 'SMC' | 'EMA200' | 'ICHIMOKU' | 'FIBONACCI') => {
    setActiveMode(mode);
    onFocusChange?.(mode);
  };

  const handleTfClick = (tfId: string) => {
    const cleanTf = tfId.toLowerCase();
    setLocalTimeframe(cleanTf);
    onTimeframeChange?.(cleanTf);
  };

  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const [isLight, setIsLight] = useState<boolean>(false);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const checkTheme = () => {
        const saved = localStorage.getItem('sofia_theme');
        setIsLight(saved === 'light' || document.documentElement.classList.contains('light-theme'));
      };
      checkTheme();
      const themeHandler = (e: any) => setIsLight(e?.detail === 'light');
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

  // Dedicated Right Gutter (130px) so price badges NEVER overlap candlesticks
  const padding = { top: 22, right: 132, bottom: 42, left: 16 };
  const svgWidth = 920;
  const svgHeight = height;
  const chartWidth = svgWidth - padding.left - padding.right;
  const chartHeight = svgHeight - padding.top - padding.bottom;
  const volumeHeight = 52;
  const priceChartHeight = chartHeight - volumeHeight - 14;
  const plotLeft = padding.left + 38; // Leave 38px on left for compact S1/R1 tags
  const plotRight = padding.left + chartWidth - 10;
  const plotWidth = plotRight - plotLeft;

  const validCandles = useMemo(() => {
    if (!candles || !Array.isArray(candles) || candles.length === 0) return [];
    return candles.filter((c) => c && c.close > 0);
  }, [candles]);

  const n = validCandles.length;

  const snrData = technicalAudit?.indicators?.SNR;
  const smcData = technicalAudit?.indicators?.SMC;
  const emaData = technicalAudit?.indicators?.EMA200;
  const ichimokuData = technicalAudit?.indicators?.ICHIMOKU;
  const fiboData = technicalAudit?.indicators?.FIBONACCI;

  // Compute dynamic per-candle Ichimoku (Tenkan 9, Kijun 26, Senkou Span A & B) and EMA curves
  const dynamicSeries = useMemo(() => {
    if (n === 0) return { tenkan: [], kijun: [], spanA: [], spanB: [], emaCurve: [] };
    const tenkan: number[] = [];
    const kijun: number[] = [];
    const spanA: number[] = [];
    const spanB: number[] = [];
    const emaCurve: number[] = [];

    const alpha = 2 / (Math.min(50, Math.max(14, n)) + 1);
    let runningEma = validCandles[0].close;
    const targetEma200 = Number(emaData?.values?.ema_200 || 0);

    for (let i = 0; i < n; i++) {
      // Tenkan-sen (9)
      const start9 = Math.max(0, i - 8);
      let h9 = -Infinity;
      let l9 = Infinity;
      for (let j = start9; j <= i; j++) {
        if (validCandles[j].high > h9) h9 = validCandles[j].high;
        if (validCandles[j].low < l9) l9 = validCandles[j].low;
      }
      const tVal = (h9 + l9) / 2;
      tenkan.push(tVal);

      // Kijun-sen (26)
      const start26 = Math.max(0, i - 25);
      let h26 = -Infinity;
      let l26 = Infinity;
      for (let j = start26; j <= i; j++) {
        if (validCandles[j].high > h26) h26 = validCandles[j].high;
        if (validCandles[j].low < l26) l26 = validCandles[j].low;
      }
      const kVal = (h26 + l26) / 2;
      kijun.push(kVal);

      // Senkou Span A & B (shifted lookback for realistic Kumo wave)
      const lagIdx = Math.max(0, i - 12);
      const sA = (tenkan[lagIdx] + kijun[lagIdx]) / 2;
      const start52 = Math.max(0, lagIdx - 51);
      let h52 = -Infinity;
      let l52 = Infinity;
      for (let j = start52; j <= lagIdx; j++) {
        if (validCandles[j].high > h52) h52 = validCandles[j].high;
        if (validCandles[j].low < l52) l52 = validCandles[j].low;
      }
      const sB = (h52 + l52) / 2;
      spanA.push(sA);
      spanB.push(sB);

      // Smooth EMA curve anchored to backend EMA200 level at the latest bar
      runningEma = validCandles[i].close * alpha + runningEma * (1 - alpha);
      emaCurve.push(runningEma);
    }

    if (targetEma200 > 0 && emaCurve.length > 0) {
      const lastRaw = emaCurve[emaCurve.length - 1];
      const offset = targetEma200 - lastRaw;
      for (let i = 0; i < emaCurve.length; i++) {
        const weight = 0.65 + 0.35 * (i / Math.max(1, emaCurve.length - 1));
        emaCurve[i] = emaCurve[i] + offset * weight;
      }
    }

    return { tenkan, kijun, spanA, spanB, emaCurve };
  }, [validCandles, n, emaData]);

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

    if ((activeMode === 'SNR' || activeMode === 'ALL') && snrData?.levels) {
      (snrData.levels.supports || []).forEach((s: any) => {
        if (s.price_level > 0) minP = Math.min(minP, s.price_level);
      });
      (snrData.levels.resistances || []).forEach((r: any) => {
        if (r.price_level > 0) maxP = Math.max(maxP, r.price_level);
      });
    }

    if ((activeMode === 'EMA200' || activeMode === 'ALL') && emaData?.values?.ema_200) {
      const e200 = Number(emaData.values.ema_200);
      if (e200 > 0) {
        minP = Math.min(minP, e200);
        maxP = Math.max(maxP, e200);
      }
    }

    if ((activeMode === 'FIBONACCI' || activeMode === 'ALL') && fiboData?.levels) {
      const f0 = Number(fiboData.levels.fib_0 || 0);
      const f100 = Number(fiboData.levels.fib_100 || 0);
      if (f0 > 0 && f100 > 0) {
        minP = Math.min(minP, f0, f100);
        maxP = Math.max(maxP, f0, f100);
      }
    }

    const span = Math.max(1e-6, maxP - minP);
    return {
      minPrice: Math.max(0, minP - span * 0.06),
      maxPrice: maxP + span * 0.06,
      maxVol: maxV || 100,
    };
  }, [validCandles, n, activeMode, snrData, emaData, fiboData]);

  const getX = (idx: number) => {
    if (n <= 1) return plotLeft + plotWidth / 2;
    return plotLeft + (idx / (n - 1)) * plotWidth;
  };

  const getY = (price: number) => {
    if (maxPrice === minPrice) return padding.top + priceChartHeight / 2;
    const ratio = (price - minPrice) / (maxPrice - minPrice);
    const rawY = padding.top + (1 - ratio) * priceChartHeight;
    return Math.max(padding.top + 4, Math.min(padding.top + priceChartHeight - 4, rawY));
  };

  const getVolY = (vol: number) => {
    const ratio = maxVol > 0 ? Math.min(1, vol / maxVol) : 0;
    const base = padding.top + priceChartHeight + 14 + volumeHeight;
    return base - ratio * volumeHeight;
  };

  const candleWidth = Math.max(2.5, Math.min(11, (plotWidth / Math.max(1, n)) * 0.68));
  const hoveredCandle = hoverIndex !== null && validCandles[hoverIndex] ? validCandles[hoverIndex] : validCandles[n - 1];

  // Build de-overlapped right-axis price tags for active overlays
  const rightAxisTags = useMemo(() => {
    const tags: RightAxisTag[] = [];
    const axisTop = padding.top + 8;
    const axisBot = padding.top + priceChartHeight - 8;

    if ((activeMode === 'SNR' || activeMode === 'ALL') && snrData?.levels) {
      (snrData.levels.resistances || []).forEach((res: any, idx: number) => {
        const y = getY(res.price_level);
        tags.push({
          id: `res-${idx}`,
          rawY: y,
          y,
          text: `R${idx + 1} ${formatPrice(res.price_level)}`,
          bg: '#881337',
          border: '#f43f5e',
          color: '#fecdd3',
        });
      });
      (snrData.levels.supports || []).forEach((sup: any, idx: number) => {
        const y = getY(sup.price_level);
        tags.push({
          id: `sup-${idx}`,
          rawY: y,
          y,
          text: `S${idx + 1} ${formatPrice(sup.price_level)}`,
          bg: '#064e3b',
          border: '#10b981',
          color: '#a7f3d0',
        });
      });
    }

    if ((activeMode === 'EMA200' || activeMode === 'ALL') && emaData?.values?.ema_200) {
      const y = getY(emaData.values.ema_200);
      tags.push({
        id: 'ema200',
        rawY: y,
        y,
        text: `EMA ${formatPrice(emaData.values.ema_200)}`,
        bg: '#78350f',
        border: '#f59e0b',
        color: '#fde68a',
      });
    }

    if (activeMode === 'ICHIMOKU' && dynamicSeries.tenkan.length > 0) {
      const lastTenkan = dynamicSeries.tenkan[dynamicSeries.tenkan.length - 1];
      const lastKijun = dynamicSeries.kijun[dynamicSeries.kijun.length - 1];
      const lastSpanA = dynamicSeries.spanA[dynamicSeries.spanA.length - 1];
      const lastSpanB = dynamicSeries.spanB[dynamicSeries.spanB.length - 1];

      tags.push({
        id: 'tenkan',
        rawY: getY(lastTenkan),
        y: getY(lastTenkan),
        text: `Tenkan ${formatPrice(lastTenkan)}`,
        bg: '#0c4a6e',
        border: '#38bdf8',
        color: '#bae6fd',
      });
      tags.push({
        id: 'kijun',
        rawY: getY(lastKijun),
        y: getY(lastKijun),
        text: `Kijun ${formatPrice(lastKijun)}`,
        bg: '#881337',
        border: '#f43f5e',
        color: '#fecdd3',
      });
      tags.push({
        id: 'spanA',
        rawY: getY(lastSpanA),
        y: getY(lastSpanA),
        text: `Span A ${formatPrice(lastSpanA)}`,
        bg: '#064e3b',
        border: '#10b981',
        color: '#a7f3d0',
      });
      tags.push({
        id: 'spanB',
        rawY: getY(lastSpanB),
        y: getY(lastSpanB),
        text: `Span B ${formatPrice(lastSpanB)}`,
        bg: '#3b0764',
        border: '#a855f7',
        color: '#e9d5ff',
      });
    }

    if (activeMode === 'FIBONACCI' && fiboData?.levels) {
      const f0 = Number(fiboData.levels.fib_0 || 0);
      const f100 = Number(fiboData.levels.fib_100 || 0);
      const isF0High = f0 >= f100;

      const fibItems = [
        { pct: '0.0%', tag: isF0High ? '0% High' : '0% Low', val: f0, gold: false },
        { pct: '23.6%', tag: '23.6%', val: Number(fiboData.levels.fib_236 || 0), gold: false },
        { pct: '38.2%', tag: '38.2%', val: Number(fiboData.levels.fib_382 || 0), gold: false },
        { pct: '50.0%', tag: '50.0%', val: Number(fiboData.levels.fib_500 || 0), gold: true },
        { pct: '61.8%', tag: '61.8%★', val: Number(fiboData.levels.fib_618 || 0), gold: true },
        { pct: '78.6%', tag: '78.6%', val: Number(fiboData.levels.fib_786 || 0), gold: false },
        { pct: '100.0%', tag: isF0High ? '100% Low' : '100% High', val: f100, gold: false },
      ];

      fibItems.forEach((f, idx) => {
        if (f.val >= minPrice && f.val <= maxPrice) {
          const y = getY(f.val);
          tags.push({
            id: `fib-${idx}`,
            rawY: y,
            y,
            text: `${f.tag} ${formatPrice(f.val)}`,
            bg: f.gold ? '#713f12' : '#0c4a6e',
            border: f.gold ? '#eab308' : '#38bdf8',
            color: f.gold ? '#fef08a' : '#bae6fd',
          });
        }
      });
    }

    return resolveVerticalCollisions(tags, axisTop, axisBot, 17);
  }, [activeMode, snrData, emaData, dynamicSeries, fiboData, minPrice, maxPrice, priceChartHeight]);

  // Build de-overlapped left-side compact SNR tags
  const leftSnrTags = useMemo(() => {
    if (activeMode !== 'SNR' && activeMode !== 'ALL') return [];
    if (!snrData?.levels) return [];
    const items: { id: string; rawY: number; y: number; label: string; isSup: boolean }[] = [];
    (snrData.levels.resistances || []).forEach((res: any, idx: number) => {
      const y = getY(res.price_level);
      items.push({ id: `l-res-${idx}`, rawY: y, y, label: `R${idx + 1}`, isSup: false });
    });
    (snrData.levels.supports || []).forEach((sup: any, idx: number) => {
      const y = getY(sup.price_level);
      items.push({ id: `l-sup-${idx}`, rawY: y, y, label: `S${idx + 1}`, isSup: true });
    });
    return resolveVerticalCollisions(items, padding.top + 8, padding.top + priceChartHeight - 8, 16);
  }, [activeMode, snrData, minPrice, maxPrice, priceChartHeight]);

  // Build de-overlapped SMC boxes & labels so FVG and OB texts never collide
  const smcVisuals = useMemo(() => {
    if ((activeMode !== 'SMC' && activeMode !== 'ALL') || !smcData?.levels) {
      return { boxes: [], labels: [] };
    }
    const boxes: {
      key: string;
      x: number;
      y: number;
      w: number;
      h: number;
      fill: string;
      stroke: string;
      dash: string;
    }[] = [];
    const rawLabels: {
      key: string;
      x: number;
      rawY: number;
      y: number;
      text: string;
      bg: string;
      border: string;
      color: string;
    }[] = [];

    (smcData.levels.order_blocks || []).slice(-3).forEach((ob: any, idx: number) => {
      const y1 = getY(ob.top);
      const y2 = getY(ob.bottom);
      const topY = Math.min(y1, y2);
      const h = Math.min(priceChartHeight * 0.22, Math.max(8, Math.abs(y2 - y1)));
      const isBull = ob.type === 'BULLISH_OB';
      const barRatio = typeof ob.bar_index === 'number' && n > 1 ? Math.min(0.75, Math.max(0.18, ob.bar_index / n)) : 0.28 + idx * 0.12;
      const startX = plotLeft + plotWidth * barRatio;
      const w = Math.max(60, plotRight - startX);

      boxes.push({
        key: `ob-box-${idx}`,
        x: startX,
        y: topY,
        w,
        h,
        fill: isBull ? '#06b6d4' : '#f43f5e',
        stroke: isBull ? '#22d3ee' : '#fb7185',
        dash: '4 2',
      });
      rawLabels.push({
        key: `ob-lbl-${idx}`,
        x: startX + 6,
        rawY: topY + 9,
        y: topY + 9,
        text: `${isBull ? 'DEMAND OB' : 'SUPPLY OB'} (${formatPrice(isBull ? ob.bottom : ob.top)})`,
        bg: isBull ? '#083344' : '#4c0519',
        border: isBull ? '#06b6d4' : '#f43f5e',
        color: isBull ? '#67e8f9' : '#fda4af',
      });
    });

    (smcData.levels.fair_value_gaps || []).slice(-3).forEach((fvg: any, idx: number) => {
      const y1 = getY(fvg.top);
      const y2 = getY(fvg.bottom);
      const topY = Math.min(y1, y2);
      const h = Math.min(priceChartHeight * 0.18, Math.max(7, Math.abs(y2 - y1)));
      const isBull = fvg.type === 'BULLISH_FVG';
      const startX = plotLeft + plotWidth * (0.48 + idx * 0.08);
      const w = Math.max(50, plotRight - startX);

      boxes.push({
        key: `fvg-box-${idx}`,
        x: startX,
        y: topY,
        w,
        h,
        fill: isBull ? '#10b981' : '#eab308',
        stroke: isBull ? '#34d399' : '#facc15',
        dash: '3 2',
      });
      rawLabels.push({
        key: `fvg-lbl-${idx}`,
        x: startX + 6,
        rawY: topY + 9,
        y: topY + 9,
        text: `${isBull ? 'FVG BULL' : 'FVG BEAR'} (${formatPrice(fvg.bottom)}–${formatPrice(fvg.top)})`,
        bg: isBull ? '#064e3b' : '#713f12',
        border: isBull ? '#10b981' : '#eab308',
        color: isBull ? '#a7f3d0' : '#fef08a',
      });
    });

    const decollided = resolveVerticalCollisions(
      rawLabels,
      padding.top + 12,
      padding.top + priceChartHeight - 12,
      18
    );
    return { boxes, labels: decollided };
  }, [activeMode, smcData, n, minPrice, maxPrice, priceChartHeight, plotLeft, plotRight, plotWidth]);

  // Build SVG path for Ichimoku Kumo Cloud & Lines
  const kumoCloudPath = useMemo(() => {
    if (dynamicSeries.spanA.length < 2) return '';
    const upperPts = dynamicSeries.spanA.map((val, idx) => `${getX(idx).toFixed(1)},${getY(val).toFixed(1)}`);
    const lowerPts = [...dynamicSeries.spanB]
      .map((val, idx) => `${getX(idx).toFixed(1)},${getY(val).toFixed(1)}`)
      .reverse();
    return `M ${upperPts.join(' L ')} L ${lowerPts.join(' L ')} Z`;
  }, [dynamicSeries, minPrice, maxPrice]);

  const tenkanPoints = useMemo(
    () => dynamicSeries.tenkan.map((val, idx) => `${getX(idx).toFixed(1)},${getY(val).toFixed(1)}`).join(' '),
    [dynamicSeries, minPrice, maxPrice]
  );

  const kijunPoints = useMemo(
    () => dynamicSeries.kijun.map((val, idx) => `${getX(idx).toFixed(1)},${getY(val).toFixed(1)}`).join(' '),
    [dynamicSeries, minPrice, maxPrice]
  );

  const emaCurvePoints = useMemo(
    () => dynamicSeries.emaCurve.map((val, idx) => `${getX(idx).toFixed(1)},${getY(val).toFixed(1)}`).join(' '),
    [dynamicSeries, minPrice, maxPrice]
  );

  if (n === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-64 bg-obsidian-900/60 border border-obsidian-800 rounded-xl text-slate-500 font-mono text-xs">
        <LucideIcon name="bar-chart-2" className="w-8 h-8 mb-2 opacity-50" />
        Data chart tidak tersedia untuk timeframe ini.
      </div>
    );
  }

  const priceGridCount = 5;
  const priceGridLevels = Array.from({ length: priceGridCount }).map((_, i) => {
    const p = minPrice + ((maxPrice - minPrice) * i) / (priceGridCount - 1);
    return { price: p, y: getY(p) };
  });

  return (
    <div
      className={`w-full ${
        isLight ? 'bg-white border-slate-200 shadow-sm' : 'bg-[#090d16] border-obsidian-800 shadow-2xl'
      } border rounded-2xl p-3.5 sm:p-4 space-y-3`}
    >
      {/* ROW 1: Symbol + Interactive Timeframe Selector + Live OHLCV */}
      <div
        className={`flex flex-wrap items-center justify-between gap-2.5 pb-2.5 border-b ${
          isLight ? 'border-slate-200' : 'border-obsidian-800/90'
        }`}
      >
        <div className="flex flex-wrap items-center gap-2.5">
          {/* Symbol Name */}
          <div className="flex items-center gap-2">
            <span className={`font-extrabold text-base sm:text-lg font-mono tracking-tight ${isLight ? 'text-slate-900' : 'text-white'}`}>
              {symbol}
            </span>
          </div>

          {/* Interactive Chart Style & Timeframe Selector Bar */}
          <div
            className={`inline-flex items-center gap-1 p-1 rounded-xl border ${
              isLight ? 'bg-slate-100 border-slate-200' : 'bg-obsidian-950/90 border-obsidian-800'
            }`}
          >
            {/* Style Selector: Candles vs Line Chart */}
            <div className="flex items-center gap-0.5 border-r border-obsidian-800/80 pr-1 mr-0.5">
              <button
                type="button"
                onClick={() => setChartStyle('candles')}
                title="Tampilan Candlestick Tradisional"
                className={`px-2 py-1 rounded-lg text-[10.5px] font-mono font-bold transition-all ${
                  chartStyle === 'candles'
                    ? 'bg-cyan-500 text-slate-950 shadow-sm'
                    : isLight
                    ? 'text-slate-600 hover:text-slate-900'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                Candles
              </button>
              <button
                type="button"
                onClick={() => setChartStyle('line')}
                title="Tampilan Gaya Line Chart Modern (Matrix Dotted Grid)"
                className={`px-2 py-1 rounded-lg text-[10.5px] font-mono font-bold transition-all ${
                  chartStyle === 'line'
                    ? 'bg-[#45ae68] text-white shadow-sm'
                    : isLight
                    ? 'text-slate-600 hover:text-slate-900'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                Line Chart
              </button>
            </div>

            <span className="text-[10px] font-mono font-bold text-slate-400 px-1 hidden sm:inline">TF:</span>
            {timeframes.map((tf) => {
              const isSelected = localTimeframe === tf.id.toLowerCase();
              const shortLabel = tf.short || tf.id.toUpperCase();
              return (
                <button
                  key={tf.id}
                  type="button"
                  onClick={() => handleTfClick(tf.id)}
                  title={`Pilih Timeframe ${tf.label}`}
                  className={`px-2.5 py-1 rounded-lg text-[11px] font-mono font-extrabold transition-all ${
                    isSelected
                      ? 'bg-cyan-500 text-slate-950 shadow-sm ring-1 ring-cyan-400'
                      : isLight
                      ? 'text-slate-600 hover:text-slate-900 hover:bg-white'
                      : 'text-slate-400 hover:text-white hover:bg-obsidian-800/80'
                  }`}
                >
                  {shortLabel}
                </button>
              );
            })}
          </div>
        </div>

        {/* Live OHLCV Bar */}
        {hoveredCandle && (
          <div
            className={`flex flex-wrap items-center gap-2.5 text-[11px] font-mono px-3 py-1 rounded-lg border ${
              isLight ? 'bg-slate-50 border-slate-200 text-slate-600' : 'bg-obsidian-950 border-obsidian-800 text-slate-400'
            }`}
          >
            {hoveredCandle.date && (
              <span className="text-cyan-400 font-bold">{hoveredCandle.date}</span>
            )}
            <span>
              O: <strong className={isLight ? 'text-slate-900' : 'text-slate-200'}>{formatPrice(hoveredCandle.open)}</strong>
            </span>
            <span>
              H: <strong className="text-emerald-400">{formatPrice(hoveredCandle.high)}</strong>
            </span>
            <span>
              L: <strong className="text-rose-400">{formatPrice(hoveredCandle.low)}</strong>
            </span>
            <span>
              C:{' '}
              <strong className={hoveredCandle.close >= hoveredCandle.open ? 'text-emerald-400' : 'text-rose-400'}>
                {formatPrice(hoveredCandle.close)}
              </strong>
            </span>
          </div>
        )}
      </div>

      {/* ROW 2: Single-Line Compact Indicator Focus Toolbar */}
      <div className="flex items-center justify-between gap-2 overflow-x-auto no-scrollbar pb-0.5">
        <div className="flex items-center gap-1.5 font-mono text-[11px] whitespace-nowrap">
          <span className={`text-[10px] font-bold uppercase tracking-wider mr-1 ${isLight ? 'text-slate-500' : 'text-slate-400'}`}>
            Sorot di Chart:
          </span>

          <button
            type="button"
            onClick={() => handleModeChange('SNR')}
            className={`px-2.5 py-1 rounded-lg border font-bold transition flex items-center gap-1 ${
              activeMode === 'SNR'
                ? 'bg-emerald-500/20 border-emerald-500 text-emerald-400 shadow-sm ring-1 ring-emerald-500/60'
                : isLight
                ? 'bg-slate-100 border-slate-200 text-slate-600 hover:text-slate-900'
                : 'bg-obsidian-950 border-obsidian-800 text-slate-400 hover:text-white'
            }`}
          >
            <span>🛡️ SNR (Support &amp; Resistance)</span>
          </button>

          <button
            type="button"
            onClick={() => handleModeChange('SMC')}
            className={`px-2.5 py-1 rounded-lg border font-bold transition flex items-center gap-1 ${
              activeMode === 'SMC'
                ? 'bg-cyan-500/20 border-cyan-500 text-cyan-300 shadow-sm ring-1 ring-cyan-500/60'
                : isLight
                ? 'bg-slate-100 border-slate-200 text-slate-600 hover:text-slate-900'
                : 'bg-obsidian-950 border-obsidian-800 text-slate-400 hover:text-white'
            }`}
          >
            <span>📦 SMC (Order Blocks &amp; FVG)</span>
          </button>

          <button
            type="button"
            onClick={() => handleModeChange('EMA200')}
            className={`px-2.5 py-1 rounded-lg border font-bold transition flex items-center gap-1 ${
              activeMode === 'EMA200'
                ? 'bg-amber-500/20 border-amber-500 text-amber-300 shadow-sm ring-1 ring-amber-500/60'
                : isLight
                ? 'bg-slate-100 border-slate-200 text-slate-600 hover:text-slate-900'
                : 'bg-obsidian-950 border-obsidian-800 text-slate-400 hover:text-white'
            }`}
          >
            <span>📈 EMA 200</span>
          </button>

          <button
            type="button"
            onClick={() => handleModeChange('ICHIMOKU')}
            className={`px-2.5 py-1 rounded-lg border font-bold transition flex items-center gap-1 ${
              activeMode === 'ICHIMOKU'
                ? 'bg-purple-500/20 border-purple-500 text-purple-300 shadow-sm ring-1 ring-purple-500/60'
                : isLight
                ? 'bg-slate-100 border-slate-200 text-slate-600 hover:text-slate-900'
                : 'bg-obsidian-950 border-obsidian-800 text-slate-400 hover:text-white'
            }`}
          >
            <span>☁️ Ichimoku Cloud</span>
          </button>

          <button
            type="button"
            onClick={() => handleModeChange('FIBONACCI')}
            className={`px-2.5 py-1 rounded-lg border font-bold transition flex items-center gap-1 ${
              activeMode === 'FIBONACCI'
                ? 'bg-blue-500/20 border-blue-500 text-blue-300 shadow-sm ring-1 ring-blue-500/60'
                : isLight
                ? 'bg-slate-100 border-slate-200 text-slate-600 hover:text-slate-900'
                : 'bg-obsidian-950 border-obsidian-800 text-slate-400 hover:text-white'
            }`}
          >
            <span>🎯 Fibonacci</span>
          </button>

          <button
            type="button"
            onClick={() => handleModeChange('ALL')}
            className={`px-2.5 py-1 rounded-lg border font-bold transition ${
              activeMode === 'ALL'
                ? 'bg-slate-800 border-slate-500 text-white ring-1 ring-slate-500/50'
                : isLight
                ? 'bg-slate-100 border-slate-200 text-slate-600 hover:text-slate-900'
                : 'bg-obsidian-950 border-obsidian-800 text-slate-500 hover:text-slate-300'
            }`}
          >
            Semua
          </button>
        </div>
      </div>

      {/* SVG Candlestick & Overlays Canvas OR Crypto Line Chart Canvas */}
      {chartStyle === 'line' ? (
        <CryptoLineChart
          data={validCandles.map((c) => ({
            price: c.close,
            time: c.date || (typeof c.time === 'string' ? c.time : String(c.time || '')),
            label: typeof c.date === 'string' ? (c.date.includes('-') ? c.date.split('-').slice(1).join('/') : c.date) : undefined,
            dateStr: c.date,
          }))}
          height={height}
          currency={currency}
          currentPrice={validCandles[validCandles.length - 1]?.close}
        />
      ) : (
        <div className="relative w-full overflow-hidden select-none rounded-xl border border-obsidian-800/60 bg-[#070b12]">
        <svg
          viewBox={`0 0 ${svgWidth} ${svgHeight}`}
          className="w-full h-auto cursor-crosshair block"
          onMouseLeave={() => setHoverIndex(null)}
          onMouseMove={(e) => {
            const rect = e.currentTarget.getBoundingClientRect();
            const relX = ((e.clientX - rect.left) / rect.width) * svgWidth;
            if (relX >= plotLeft && relX <= plotRight) {
              const fraction = (relX - plotLeft) / Math.max(1, plotWidth);
              const idx = Math.min(n - 1, Math.max(0, Math.round(fraction * (n - 1))));
              setHoverIndex(idx);
            }
          }}
        >
          <defs>
            <linearGradient id="cloudGreen" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#10b981" stopOpacity="0.24" />
              <stop offset="100%" stopColor="#06b6d4" stopOpacity="0.06" />
            </linearGradient>
            <linearGradient id="goldenPocketGrad" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#eab308" stopOpacity="0.22" />
              <stop offset="100%" stopColor="#eab308" stopOpacity="0.06" />
            </linearGradient>
            <clipPath id="pricePlotClip">
              <rect x={padding.left} y={padding.top} width={chartWidth} height={priceChartHeight} />
            </clipPath>
          </defs>

          {/* =========================================================================
              LAYER 1: BACKGROUND GRID & RIGHT PRICE AXIS SEPARATOR
             ========================================================================= */}
          {priceGridLevels.map((lvl, idx) => (
            <g key={`grid-${idx}`}>
              <line
                x1={padding.left}
                y1={lvl.y}
                x2={padding.left + chartWidth}
                y2={lvl.y}
                stroke={isLight ? '#e2e8f0' : '#131c2e'}
                strokeDasharray="3 3"
                strokeWidth="1"
              />
              {rightAxisTags.length === 0 && (
                <text
                  x={padding.left + chartWidth + 8}
                  y={lvl.y + 3}
                  fill="#64748b"
                  fontSize="9"
                  fontFamily="monospace"
                >
                  {formatPrice(lvl.price)}
                </text>
              )}
            </g>
          ))}

          {/* Right Axis Vertical Divider */}
          <line
            x1={padding.left + chartWidth}
            y1={padding.top}
            x2={padding.left + chartWidth}
            y2={padding.top + priceChartHeight + 14 + volumeHeight}
            stroke={isLight ? '#cbd5e1' : '#1e293b'}
            strokeWidth="1"
          />

          {/* Volume Sub-chart Top Border */}
          <line
            x1={padding.left}
            y1={padding.top + priceChartHeight + 10}
            x2={padding.left + chartWidth}
            y2={padding.top + priceChartHeight + 10}
            stroke={isLight ? '#e2e8f0' : '#1e293b'}
            strokeWidth="1"
          />

          {/* =========================================================================
              LAYER 2: SHADED BACKGROUND ZONES (Clipped to Price Plot Area)
             ========================================================================= */}
          <g clipPath="url(#pricePlotClip)">
            {/* SNR Shaded Bands */}
            {(activeMode === 'SNR' || activeMode === 'ALL') && snrData?.levels && (
              <g id="snr-bands">
                {(snrData.levels.supports || []).map((sup: any, sIdx: number) => {
                  const yLow = getY(sup.zone_low);
                  const yHigh = getY(sup.zone_high);
                  const zoneH = Math.min(18, Math.max(4, Math.abs(yLow - yHigh)));
                  return (
                    <rect
                      key={`sup-band-${sIdx}`}
                      x={plotLeft}
                      y={getY(sup.price_level) - zoneH / 2}
                      width={plotWidth}
                      height={zoneH}
                      fill="#10b981"
                      fillOpacity={activeMode === 'SNR' ? '0.14' : '0.08'}
                    />
                  );
                })}
                {(snrData.levels.resistances || []).map((res: any, rIdx: number) => {
                  const yLow = getY(res.zone_low);
                  const yHigh = getY(res.zone_high);
                  const zoneH = Math.min(18, Math.max(4, Math.abs(yLow - yHigh)));
                  return (
                    <rect
                      key={`res-band-${rIdx}`}
                      x={plotLeft}
                      y={getY(res.price_level) - zoneH / 2}
                      width={plotWidth}
                      height={zoneH}
                      fill="#f43f5e"
                      fillOpacity={activeMode === 'SNR' ? '0.14' : '0.08'}
                    />
                  );
                })}
              </g>
            )}

            {/* SMC Shaded Boxes (OB & FVG) */}
            {(activeMode === 'SMC' || activeMode === 'ALL') && (
              <g id="smc-boxes">
                {smcVisuals.boxes.map((b) => (
                  <rect
                    key={b.key}
                    x={b.x}
                    y={b.y}
                    width={b.w}
                    height={b.h}
                    fill={b.fill}
                    fillOpacity={activeMode === 'SMC' ? '0.18' : '0.10'}
                    stroke={b.stroke}
                    strokeWidth="1.2"
                    strokeDasharray={b.dash}
                    rx="2"
                  />
                ))}
                {/* Equilibrium 50% Dealing Range Line */}
                {activeMode === 'SMC' && smcData?.values?.dealing_range_eq && (
                  <line
                    x1={plotLeft}
                    y1={getY(smcData.values.dealing_range_eq)}
                    x2={padding.left + chartWidth}
                    y2={getY(smcData.values.dealing_range_eq)}
                    stroke="#94a3b8"
                    strokeWidth="1"
                    strokeDasharray="6 4"
                    strokeOpacity="0.6"
                  />
                )}
              </g>
            )}

            {/* Ichimoku Dynamic Kumo Cloud Polygon */}
            {(activeMode === 'ICHIMOKU' || activeMode === 'ALL') && kumoCloudPath && (
              <path
                d={kumoCloudPath}
                fill="url(#cloudGreen)"
                stroke="#10b981"
                strokeWidth="1"
                strokeOpacity="0.45"
              />
            )}

            {/* Fibonacci Golden Pocket Shaded Band */}
            {(activeMode === 'FIBONACCI' || activeMode === 'ALL') &&
              fiboData?.levels?.golden_pocket_min &&
              fiboData?.levels?.golden_pocket_max && (
                <rect
                  x={plotLeft}
                  y={getY(fiboData.levels.golden_pocket_max)}
                  width={plotWidth}
                  height={Math.max(6, Math.abs(getY(fiboData.levels.golden_pocket_min) - getY(fiboData.levels.golden_pocket_max)))}
                  fill="url(#goldenPocketGrad)"
                  stroke="#eab308"
                  strokeWidth="1"
                  strokeOpacity="0.7"
                />
              )}
          </g>

          {/* =========================================================================
              LAYER 3: VOLUME BARS & CANDLESTICKS
             ========================================================================= */}
          {validCandles.map((c, idx) => {
            if (!c.volume) return null;
            const x = getX(idx);
            const isBull = c.close >= c.open;
            const topY = getVolY(c.volume);
            const base = padding.top + priceChartHeight + 14 + volumeHeight;
            const h = Math.max(1, base - topY);
            return (
              <rect
                key={`vol-${idx}`}
                x={x - candleWidth / 2}
                y={topY}
                width={candleWidth}
                height={h}
                fill={isBull ? '#10b981' : '#f43f5e'}
                fillOpacity="0.32"
              />
            );
          })}

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
                <line x1={x} y1={highY} x2={x} y2={lowY} stroke={color} strokeWidth="1.25" />
                <rect
                  x={x - candleWidth / 2}
                  y={bodyTop}
                  width={candleWidth}
                  height={bodyHeight}
                  fill={color}
                  rx="0.8"
                />
              </g>
            );
          })}

          {/* =========================================================================
              LAYER 4: CRISP INDICATOR LINES & CURVES (Above Candles)
             ========================================================================= */}
          <g clipPath="url(#pricePlotClip)">
            {/* SNR Lines */}
            {(activeMode === 'SNR' || activeMode === 'ALL') && snrData?.levels && (
              <g id="snr-lines">
                {(snrData.levels.supports || []).map((sup: any, sIdx: number) => {
                  const y = getY(sup.price_level);
                  return (
                    <line
                      key={`sup-line-${sIdx}`}
                      x1={padding.left + 36}
                      y1={y}
                      x2={padding.left + chartWidth}
                      y2={y}
                      stroke="#10b981"
                      strokeWidth={activeMode === 'SNR' ? '1.8' : '1.2'}
                      strokeDasharray={activeMode === 'SNR' ? 'none' : '5 3'}
                    />
                  );
                })}
                {(snrData.levels.resistances || []).map((res: any, rIdx: number) => {
                  const y = getY(res.price_level);
                  return (
                    <line
                      key={`res-line-${rIdx}`}
                      x1={padding.left + 36}
                      y1={y}
                      x2={padding.left + chartWidth}
                      y2={y}
                      stroke="#f43f5e"
                      strokeWidth={activeMode === 'SNR' ? '1.8' : '1.2'}
                      strokeDasharray={activeMode === 'SNR' ? 'none' : '5 3'}
                    />
                  );
                })}
              </g>
            )}

            {/* Dynamic EMA 200 Curve */}
            {(activeMode === 'EMA200' || activeMode === 'ALL') && emaCurvePoints && (
              <polyline
                fill="none"
                stroke="#f59e0b"
                strokeWidth={activeMode === 'EMA200' ? '2.5' : '1.8'}
                points={emaCurvePoints}
              />
            )}

            {/* Dynamic Ichimoku Tenkan-sen & Kijun-sen Curves */}
            {(activeMode === 'ICHIMOKU' || activeMode === 'ALL') && (
              <g id="ichimoku-curves">
                {tenkanPoints && (
                  <polyline fill="none" stroke="#38bdf8" strokeWidth="1.8" points={tenkanPoints} />
                )}
                {kijunPoints && (
                  <polyline fill="none" stroke="#f43f5e" strokeWidth="1.8" points={kijunPoints} />
                )}
              </g>
            )}

            {/* Fibonacci Horizontal Retracement Lines */}
            {(activeMode === 'FIBONACCI' || activeMode === 'ALL') && fiboData?.levels && (
              <g id="fib-lines">
                {[
                  { val: fiboData.levels.fib_0, gold: false },
                  { val: fiboData.levels.fib_236, gold: false },
                  { val: fiboData.levels.fib_382, gold: false },
                  { val: fiboData.levels.fib_500, gold: true },
                  { val: fiboData.levels.fib_618, gold: true },
                  { val: fiboData.levels.fib_786, gold: false },
                  { val: fiboData.levels.fib_100, gold: false },
                ]
                  .filter((f) => f.val && f.val >= minPrice && f.val <= maxPrice)
                  .map((f, idx) => (
                    <line
                      key={`fib-l-${idx}`}
                      x1={plotLeft}
                      y1={getY(f.val)}
                      x2={padding.left + chartWidth}
                      y2={getY(f.val)}
                      stroke={f.gold ? '#eab308' : '#38bdf8'}
                      strokeWidth={f.gold ? '1.6' : '1'}
                      strokeDasharray={f.gold ? 'none' : '4 3'}
                      strokeOpacity={f.gold ? '0.9' : '0.55'}
                    />
                  ))}
              </g>
            )}
          </g>

          {/* =========================================================================
              LAYER 5: TOPMOST NON-OVERLAPPING PILL BADGES & RIGHT-AXIS GUTTER TAGS
             ========================================================================= */}

          {/* Left Compact SNR Badges (S1/S2/S3, R1/R2/R3) */}
          {leftSnrTags.map((tag) => (
            <g key={tag.id}>
              <rect
                x={padding.left + 2}
                y={tag.y - 7.5}
                width={30}
                height={15}
                rx="3"
                fill={tag.isSup ? '#064e3b' : '#881337'}
                stroke={tag.isSup ? '#10b981' : '#f43f5e'}
                strokeWidth="1"
              />
              <text
                x={padding.left + 17}
                y={tag.y + 3}
                fill={tag.isSup ? '#a7f3d0' : '#fecdd3'}
                fontSize="8.5"
                fontFamily="monospace"
                fontWeight="bold"
                textAnchor="middle"
              >
                {tag.label}
              </text>
            </g>
          ))}

          {/* De-collided SMC Order Block & FVG Pill Labels */}
          {(activeMode === 'SMC' || activeMode === 'ALL') &&
            smcVisuals.labels.map((lbl) => {
              const pillW = Math.min(205, Math.max(95, lbl.text.length * 5.4 + 12));
              const safeX = Math.min(padding.left + chartWidth - pillW - 6, lbl.x);
              return (
                <g key={lbl.key}>
                  <rect
                    x={safeX}
                    y={lbl.y - 8}
                    width={pillW}
                    height={15}
                    rx="3"
                    fill={lbl.bg}
                    fillOpacity="0.92"
                    stroke={lbl.border}
                    strokeWidth="0.9"
                  />
                  <text
                    x={safeX + 6}
                    y={lbl.y + 2.5}
                    fill={lbl.color}
                    fontSize="8"
                    fontFamily="monospace"
                    fontWeight="bold"
                  >
                    {lbl.text}
                  </text>
                </g>
              );
            })}

          {/* Golden Pocket Floating Pill Badge */}
          {activeMode === 'FIBONACCI' &&
            fiboData?.levels?.golden_pocket_min &&
            fiboData?.levels?.golden_pocket_max && (() => {
              const gpY =
                (getY(fiboData.levels.golden_pocket_max) + getY(fiboData.levels.golden_pocket_min)) / 2;
              return (
                <g>
                  <rect
                    x={plotLeft + 6}
                    y={gpY - 8.5}
                    width={176}
                    height={17}
                    rx="4"
                    fill="#090d16"
                    fillOpacity="0.92"
                    stroke="#eab308"
                    strokeWidth="1"
                  />
                  <text
                    x={plotLeft + 12}
                    y={gpY + 3}
                    fill="#fef08a"
                    fontSize="8.5"
                    fontFamily="monospace"
                    fontWeight="bold"
                  >
                    ★ GOLDEN POCKET (50%–61.8%)
                  </text>
                </g>
              );
            })()}

          {/* Right-Axis Gutter Price Badges (Zero Overlap with Candlesticks!) */}
          {rightAxisTags.map((tag) => (
            <g key={tag.id}>
              {/* Connector tick from exact price line to de-collided tag */}
              <line
                x1={padding.left + chartWidth}
                y1={tag.rawY}
                x2={padding.left + chartWidth + 6}
                y2={tag.y}
                stroke={tag.border}
                strokeWidth="1"
              />
              <rect
                x={padding.left + chartWidth + 6}
                y={tag.y - 8}
                width={padding.right - 10}
                height={16}
                rx="3"
                fill={tag.bg}
                stroke={tag.border}
                strokeWidth="1"
              />
              <text
                x={padding.left + chartWidth + 11}
                y={tag.y + 3}
                fill={tag.color}
                fontSize="8.2"
                fontFamily="monospace"
                fontWeight="bold"
              >
                {tag.text}
              </text>
            </g>
          ))}

          {/* Interactive Hover Crosshair */}
          {hoverIndex !== null && validCandles[hoverIndex] && (
            <g id="crosshair">
              <line
                x1={getX(hoverIndex)}
                y1={padding.top}
                x2={getX(hoverIndex)}
                y2={padding.top + priceChartHeight + 14 + volumeHeight}
                stroke="#94a3b8"
                strokeWidth="1"
                strokeDasharray="2 2"
              />
              <line
                x1={padding.left}
                y1={getY(validCandles[hoverIndex].close)}
                x2={padding.left + chartWidth}
                y2={getY(validCandles[hoverIndex].close)}
                stroke="#94a3b8"
                strokeWidth="1"
                strokeDasharray="2 2"
              />
              {/* Hover Price Tag on Right Axis */}
              <rect
                x={padding.left + chartWidth + 4}
                y={getY(validCandles[hoverIndex].close) - 9}
                width={padding.right - 8}
                height={18}
                rx="3"
                fill="#0f172a"
                stroke="#38bdf8"
                strokeWidth="1.2"
              />
              <text
                x={padding.left + chartWidth + 10}
                y={getY(validCandles[hoverIndex].close) + 3}
                fill="#38bdf8"
                fontSize="8.5"
                fontFamily="monospace"
                fontWeight="bold"
              >
                ► {formatPrice(validCandles[hoverIndex].close)}
              </text>
              {/* Hover Date Pill at Bottom */}
              <rect
                x={Math.max(padding.left, Math.min(padding.left + chartWidth - 90, getX(hoverIndex) - 45))}
                y={svgHeight - 20}
                width={90}
                height={16}
                rx="3"
                fill="#0f172a"
                stroke="#475569"
                strokeWidth="1"
              />
              <text
                x={Math.max(padding.left + 45, Math.min(padding.left + chartWidth - 45, getX(hoverIndex)))}
                y={svgHeight - 9}
                fill="#e2e8f0"
                fontSize="8.5"
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
      )}

      {/* DYNAMIC FOCUSED INDICATOR EXPLANATION PANEL */}
      {activeMode === 'SNR' && snrData && (
        <div className="p-3.5 rounded-xl bg-emerald-950/40 border border-emerald-500/40 text-xs font-mono space-y-2">
          <div className="flex items-center justify-between text-emerald-300 font-bold">
            <span className="flex items-center gap-1.5">
              <LucideIcon name="shield" className="w-4 h-4 text-emerald-400" />
              Detail Level Support &amp; Resistance (SNR) • TF {localTimeframe.toUpperCase()}:
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
              Detail Smart Money Concepts (SMC) • TF {localTimeframe.toUpperCase()}:
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
              <span className="text-slate-400 block text-[10px]">Order Blocks &amp; FVG Aktif</span>
              <strong className="text-purple-400">
                {smcData.levels?.order_blocks?.length || 0} OB • {smcData.levels?.fair_value_gaps?.length || 0} FVG
              </strong>
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
              Detail Filter Tren Major EMA 200 • TF {localTimeframe.toUpperCase()}:
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
                {emaData.values?.distance_pct >= 0 ? '+' : ''}
                {emaData.values?.distance_pct}%
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
              Detail Awan Kumo Ichimoku • TF {localTimeframe.toUpperCase()}:
            </span>
            <span className="text-[10px] px-2 py-0.5 rounded bg-purple-500/20 border border-purple-500/30">
              {ichimokuData.display_status}
            </span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-[11px] pt-1">
            <div className="p-2 rounded-lg bg-obsidian-950 border border-obsidian-800">
              <span className="text-slate-400 block text-[10px]">Tenkan (Biru) / Kijun (Merah)</span>
              <strong className="text-cyan-300">
                {formatPrice(ichimokuData.values?.tenkan_sen)} / {formatPrice(ichimokuData.values?.kijun_sen)}
              </strong>
            </div>
            <div className="p-2 rounded-lg bg-obsidian-950 border border-obsidian-800">
              <span className="text-slate-400 block text-[10px]">Rentang Awan Kumo</span>
              <strong className="text-purple-300">
                {formatPrice(ichimokuData.values?.kumo_lower)} – {formatPrice(ichimokuData.values?.kumo_upper)}
              </strong>
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
              Detail Level Rasio Fibonacci • TF {localTimeframe.toUpperCase()}:
            </span>
            <span className="text-[10px] px-2 py-0.5 rounded bg-blue-500/20 border border-blue-500/30">
              {fiboData.display_status}
            </span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-[11px] pt-1">
            <div className="p-2 rounded-lg bg-obsidian-950 border border-obsidian-800">
              <span className="text-slate-400 block text-[10px]">Golden Pocket (50%–61.8%)</span>
              <strong className="text-amber-300">
                {formatPrice(fiboData.levels?.golden_pocket_min)} – {formatPrice(fiboData.levels?.golden_pocket_max)}
              </strong>
            </div>
            <div className="p-2 rounded-lg bg-obsidian-950 border border-obsidian-800">
              <span className="text-slate-400 block text-[10px]">Swing High</span>
              <strong className="text-white">{formatPrice(fiboData.values?.swing_high)}</strong>
            </div>
            <div className="p-2 rounded-lg bg-obsidian-950 border border-obsidian-800">
              <span className="text-slate-400 block text-[10px]">Swing Low</span>
              <strong className="text-white">{formatPrice(fiboData.values?.swing_low)}</strong>
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
