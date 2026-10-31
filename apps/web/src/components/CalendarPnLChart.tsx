import React, { useState, useRef, useCallback, useMemo, useEffect } from 'react';
import { formatIdr, formatUsd } from '@/lib/api';
import { LucideIcon } from '@/components/LucideIcon';

export interface CalendarDayData {
  date: string;
  day_number: number;
  weekday: number;
  weekday_name: string;
  is_today: boolean;
  total_pnl_usd: number;
  total_pnl_idr: number;
  realized_pnl_usd?: number;
  realized_pnl_idr?: number;
  floating_pnl_usd?: number;
  floating_included?: boolean;
  trades_count: number;
  winning_trades: number;
  losing_trades: number;
  buy_trades?: number;
  sell_trades?: number;
  win_rate_pct: number;
  volume_usd: number;
  volume_idr: number;
  fees_usd: number;
  fees_idr: number;
  trades?: any[];
}

interface CalendarPnLChartProps {
  days: CalendarDayData[];
  usdIdr: number;
  monthLabel?: string;
  selectedMode?: 'PAPER' | 'LIVE' | 'WALLET';
  selectedDayDate: string | null;
  onSelectDate: (date: string) => void;
}

const GREEN = '#80efad';
const RED = '#ff646e';
const GREEN_BG = '#45ae68';
const RED_BG = '#e11d48';

const CHART_CONFIG = {
  paddingLeft: 20,
  paddingRight: 88,
  paddingTop: 24,
  paddingBottom: 42,
};

export function CalendarPnLChart({
  days = [],
  usdIdr = 17960,
  monthLabel = 'Bulan Ini',
  selectedMode = 'PAPER',
  selectedDayDate,
  onSelectDate,
}: CalendarPnLChartProps) {
  const [chartType, setChartType] = useState<'cumulative' | 'daily'>('cumulative');
  const [isCollapsed, setIsCollapsed] = useState<boolean>(false);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [pointer, setPointer] = useState<{ x: number; y: number } | null>(null);
  const [activeHoverIdx, setActiveHoverIdx] = useState<number | null>(null);

  const rate = usdIdr || 17960;

  // Process timeline data across days in the month
  const timelineData = useMemo(() => {
    let runningCumUsd = 0;
    let runningCumIdr = 0;
    let peakUsd = 0;
    let maxDrawdownUsd = 0;

    return days.map((d, idx) => {
      const pnlUsd = Number(d.total_pnl_usd || 0);
      const pnlIdr = Number(d.total_pnl_idr || pnlUsd * rate);

      runningCumUsd += pnlUsd;
      runningCumIdr += pnlIdr;

      if (runningCumUsd > peakUsd) {
        peakUsd = runningCumUsd;
      }
      const dd = peakUsd - runningCumUsd;
      if (dd > maxDrawdownUsd) {
        maxDrawdownUsd = dd;
      }

      return {
        index: idx,
        date: d.date,
        dayNumber: d.day_number,
        weekdayName: d.weekday_name || '',
        isToday: d.is_today,
        dayPnlUsd: pnlUsd,
        dayPnlIdr: pnlIdr,
        cumPnlUsd: runningCumUsd,
        cumPnlIdr: runningCumIdr,
        tradesCount: d.trades_count || 0,
        winRate: d.win_rate_pct || 0,
        winTrades: d.winning_trades || 0,
        lossTrades: d.losing_trades || 0,
        feesIdr: d.fees_idr || 0,
        feesUsd: d.fees_usd || 0,
        volumeUsd: d.volume_usd || 0,
        volumeIdr: d.volume_idr || 0,
      };
    });
  }, [days, rate]);

  // Overall performance stats
  const chartStats = useMemo(() => {
    if (timelineData.length === 0) {
      return {
        totalPnlUsd: 0,
        totalPnlIdr: 0,
        peakPnlUsd: 0,
        peakPnlIdr: 0,
        maxDrawdownUsd: 0,
        maxDrawdownIdr: 0,
        activeDays: 0,
        totalTrades: 0,
        winTrades: 0,
        avgDailyPnlUsd: 0,
        avgDailyPnlIdr: 0,
        winRatePct: 0,
      };
    }

    const last = timelineData[timelineData.length - 1];
    const totalPnlUsd = last.cumPnlUsd;
    const totalPnlIdr = last.cumPnlIdr;

    let peakPnlUsd = 0;
    let maxDrawdownUsd = 0;
    let activeDays = 0;
    let totalTrades = 0;
    let winTrades = 0;

    timelineData.forEach((d) => {
      if (d.cumPnlUsd > peakPnlUsd) peakPnlUsd = d.cumPnlUsd;
      const dd = peakPnlUsd - d.cumPnlUsd;
      if (dd > maxDrawdownUsd) maxDrawdownUsd = dd;
      if (d.tradesCount > 0) {
        activeDays += 1;
        totalTrades += d.tradesCount;
        winTrades += d.winTrades;
      }
    });

    const avgDailyPnlUsd = activeDays > 0 ? totalPnlUsd / activeDays : 0;
    const winRatePct = totalTrades > 0 ? (winTrades / totalTrades) * 100 : 0;

    return {
      totalPnlUsd,
      totalPnlIdr,
      peakPnlUsd,
      peakPnlIdr: peakPnlUsd * rate,
      maxDrawdownUsd,
      maxDrawdownIdr: maxDrawdownUsd * rate,
      activeDays,
      totalTrades,
      winTrades,
      avgDailyPnlUsd,
      avgDailyPnlIdr: avgDailyPnlUsd * rate,
      winRatePct,
    };
  }, [timelineData, rate]);

  // Canvas drawing function matching the user's Crypto Line Chart style
  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas || timelineData.length === 0) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const width = canvas.clientWidth;
    const height = canvas.clientHeight;
    if (!width || !height) return;

    const dpr = typeof window !== 'undefined' ? window.devicePixelRatio || 1 : 1;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    ctx.clearRect(0, 0, width, height);

    const left = CHART_CONFIG.paddingLeft;
    const right = width - CHART_CONFIG.paddingRight;
    const top = CHART_CONFIG.paddingTop;
    const bottom = height - CHART_CONFIG.paddingBottom;

    if (right <= left || bottom <= top) return;

    // 1. Background Dotted Grid (Matrix of #20262d dots, step 13px, radius 0.8)
    ctx.fillStyle = '#20262d';
    for (let x = left; x < right; x += 13) {
      for (let y = top; y < bottom; y += 13) {
        ctx.beginPath();
        ctx.arc(x, y, 0.8, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    if (chartType === 'cumulative') {
      const values = timelineData.map((d) => d.cumPnlUsd);
      const minVal = Math.min(...values);
      const maxVal = Math.max(...values);
      const span = Math.max(0.1, maxVal - minVal);
      const min = minVal - span * 0.12;
      const max = maxVal + span * 0.12;

      const X = (i: number) => left + (i / Math.max(1, timelineData.length - 1)) * (right - left);
      const Y = (val: number) => bottom - ((val - min) / Math.max(0.01, max - min)) * (bottom - top);

      // Horizontal reference levels
      ctx.font = '12px Arial, sans-serif';
      ctx.textAlign = 'left';
      ctx.fillStyle = '#777f88';

      for (let i = 0; i <= 4; i++) {
        const p = max - ((max - min) * i) / 4;
        const y = Y(p);

        ctx.strokeStyle = '#22282e';
        ctx.lineWidth = 0.7;
        ctx.beginPath();
        ctx.moveTo(left, y);
        ctx.lineTo(right, y);
        ctx.stroke();

        ctx.fillText(formatUsd(p), right + 10, y + 4);
      }

      // Area gradient
      const isOverallBull = timelineData[timelineData.length - 1].cumPnlUsd >= 0;
      const gradient = ctx.createLinearGradient(0, top, 0, bottom);
      if (isOverallBull) {
        gradient.addColorStop(0, 'rgba(67, 230, 160, 0.22)');
        gradient.addColorStop(1, 'rgba(67, 230, 160, 0)');
      } else {
        gradient.addColorStop(0, 'rgba(255, 100, 110, 0.22)');
        gradient.addColorStop(1, 'rgba(255, 100, 110, 0)');
      }

      ctx.beginPath();
      timelineData.forEach((d, i) => {
        const x = X(i);
        const y = Y(d.cumPnlUsd);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.lineTo(right, bottom);
      ctx.lineTo(left, bottom);
      ctx.closePath();
      ctx.fillStyle = gradient;
      ctx.fill();

      // Glowing two-tone line segments (Green on uptick, Red on downtick)
      for (let i = 1; i < timelineData.length; i++) {
        const prev = timelineData[i - 1].cumPnlUsd;
        const curr = timelineData[i].cumPnlUsd;

        ctx.beginPath();
        ctx.moveTo(X(i - 1), Y(prev));
        ctx.lineTo(X(i), Y(curr));

        const color = curr >= prev ? GREEN : RED;

        ctx.strokeStyle = color;
        ctx.lineWidth = 2.5;
        ctx.lineJoin = 'round';
        ctx.lineCap = 'round';

        ctx.shadowColor = color;
        ctx.shadowBlur = 7;
        ctx.stroke();
      }
      ctx.shadowBlur = 0;

      // Current Price / Latest PnL Horizontal Dashed Line
      const last = timelineData[timelineData.length - 1];
      const lastY = Y(last.cumPnlUsd);
      const isLastBull = last.cumPnlUsd >= 0;
      const activeColor = isLastBull ? GREEN : RED;
      const activeBadgeBg = isLastBull ? GREEN_BG : RED_BG;

      ctx.beginPath();
      ctx.setLineDash([5, 5]);
      ctx.moveTo(left, lastY);
      ctx.lineTo(right, lastY);
      ctx.strokeStyle = activeColor;
      ctx.lineWidth = 1;
      ctx.stroke();
      ctx.setLineDash([]);

      // Current Price Marker Circle on Right Edge
      ctx.beginPath();
      ctx.arc(right, lastY, 4, 0, Math.PI * 2);
      ctx.fillStyle = activeColor;
      ctx.fill();

      // Current Price Rounded Badge Pill
      const badgeW = 78;
      const badgeH = 28;
      const badgeX = right + 6;
      const badgeY = lastY - badgeH / 2;
      const radius = 14;

      ctx.fillStyle = activeBadgeBg;
      ctx.beginPath();
      if (typeof (ctx as any).roundRect === 'function') {
        (ctx as any).roundRect(badgeX, badgeY, badgeW, badgeH, radius);
      } else {
        ctx.rect(badgeX, badgeY, badgeW, badgeH);
      }
      ctx.fill();

      ctx.fillStyle = '#ffffff';
      ctx.font = 'bold 12px Arial, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(formatUsd(last.cumPnlUsd), badgeX + badgeW / 2, lastY + 4);

      // Selected Day Highlight Ring
      if (selectedDayDate) {
        const selIdx = timelineData.findIndex((d) => d.date === selectedDayDate);
        if (selIdx >= 0) {
          const selX = X(selIdx);
          const selY = Y(timelineData[selIdx].cumPnlUsd);

          ctx.beginPath();
          ctx.arc(selX, selY, 7, 0, Math.PI * 2);
          ctx.strokeStyle = '#38bdf8';
          ctx.lineWidth = 2;
          ctx.stroke();

          ctx.beginPath();
          ctx.arc(selX, selY, 4, 0, Math.PI * 2);
          ctx.fillStyle = '#38bdf8';
          ctx.fill();
        }
      }

      // Crosshair & Tooltip Anchor
      if (pointer && pointer.x >= left && pointer.x <= right) {
        const idx = Math.round(((pointer.x - left) / (right - left)) * (timelineData.length - 1));
        const pt = timelineData[idx];
        if (pt) {
          const px = X(idx);
          const py = Y(pt.cumPnlUsd);

          ctx.strokeStyle = '#a0aab4';
          ctx.setLineDash([3, 4]);

          ctx.beginPath();
          ctx.moveTo(px, top);
          ctx.lineTo(px, bottom);
          ctx.stroke();

          ctx.beginPath();
          ctx.moveTo(left, py);
          ctx.lineTo(right, py);
          ctx.stroke();

          ctx.setLineDash([]);

          ctx.beginPath();
          ctx.arc(px, py, 5, 0, Math.PI * 2);
          ctx.fillStyle = pt.cumPnlUsd >= (timelineData[idx - 1]?.cumPnlUsd ?? pt.cumPnlUsd) ? GREEN : RED;
          ctx.fill();
          ctx.strokeStyle = '#080a0c';
          ctx.lineWidth = 1.5;
          ctx.stroke();
        }
      }
    } else {
      // Daily Bar View
      const values = timelineData.map((d) => d.dayPnlUsd);
      const minVal = Math.min(0, ...values);
      const maxVal = Math.max(0, ...values);
      const absMax = Math.max(0.1, Math.abs(minVal), Math.abs(maxVal)) * 1.15;

      const zeroY = top + (bottom - top) / 2;
      const barWidth = Math.max(6, Math.min(22, ((right - left) / timelineData.length) * 0.65));

      // Zero Baseline
      ctx.strokeStyle = '#475569';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(left, zeroY);
      ctx.lineTo(right, zeroY);
      ctx.stroke();

      // Right Levels
      ctx.font = '12px Arial, sans-serif';
      ctx.textAlign = 'left';
      ctx.fillStyle = '#777f88';
      ctx.fillText(formatUsd(absMax * 0.8), right + 10, zeroY - (bottom - top) * 0.4 + 4);
      ctx.fillText('$0.00', right + 10, zeroY + 4);
      ctx.fillText(formatUsd(-absMax * 0.8), right + 10, zeroY + (bottom - top) * 0.4 + 4);

      // Bars
      timelineData.forEach((d, i) => {
        const x = left + (i / Math.max(1, timelineData.length - 1)) * (right - left);
        const frac = Math.abs(d.dayPnlUsd) / absMax;
        const bH = Math.max(d.dayPnlUsd !== 0 ? 3 : 1, frac * ((bottom - top) / 2 - 8));
        const isPos = d.dayPnlUsd >= 0;
        const y = isPos ? zeroY - bH : zeroY;

        ctx.fillStyle = isPos ? GREEN : RED;
        ctx.beginPath();
        if (typeof (ctx as any).roundRect === 'function') {
          (ctx as any).roundRect(x - barWidth / 2, y, barWidth, bH, 2);
        } else {
          ctx.rect(x - barWidth / 2, y, barWidth, bH);
        }
        ctx.fill();

        if (d.date === selectedDayDate) {
          ctx.strokeStyle = '#38bdf8';
          ctx.lineWidth = 2;
          ctx.stroke();
        }
      });
    }

    // Time Axis Labels (Bottom)
    ctx.fillStyle = '#777f88';
    ctx.font = '12px Arial, sans-serif';
    ctx.textAlign = 'center';

    const numLabels = Math.min(6, timelineData.length);
    for (let k = 0; k < numLabels; k++) {
      const idx = Math.round((k / (numLabels - 1)) * (timelineData.length - 1));
      const pt = timelineData[idx];
      if (pt) {
        const x = left + (idx / Math.max(1, timelineData.length - 1)) * (right - left);
        ctx.fillText(String(pt.dayNumber), x, height - 12);
      }
    }
  }, [timelineData, chartType, selectedDayDate, pointer]);

  useEffect(() => {
    draw();
  }, [draw]);

  useEffect(() => {
    const handleResize = () => draw();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [draw]);

  const handlePointerMove = (e: React.PointerEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas || timelineData.length === 0) return;
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    setPointer({ x, y });

    const left = CHART_CONFIG.paddingLeft;
    const right = rect.width - CHART_CONFIG.paddingRight;
    if (x >= left && x <= right) {
      const idx = Math.round(((x - left) / (right - left)) * (timelineData.length - 1));
      setActiveHoverIdx(idx);
    } else {
      setActiveHoverIdx(null);
    }
  };

  const handlePointerLeave = () => {
    setPointer(null);
    setActiveHoverIdx(null);
  };

  const handleCanvasClick = () => {
    if (activeHoverIdx !== null && timelineData[activeHoverIdx]) {
      onSelectDate(timelineData[activeHoverIdx].date);
    }
  };

  const activeHoverData = activeHoverIdx !== null ? timelineData[activeHoverIdx] : null;
  const isNetPositive = chartStats.totalPnlUsd >= 0;

  return (
    <div className="bg-[#080a0c] border border-slate-800/80 rounded-2xl p-4 sm:p-5 shadow-2xl backdrop-blur-md space-y-4">
      {/* Top Header: Clean Metric & Segmented Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-800/60">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-mono tracking-wider text-slate-400 uppercase font-medium">
              Performa PnL {monthLabel}
            </span>
            <span
              className={`text-[10px] font-mono px-2 py-0.5 rounded-full font-bold uppercase ${
                selectedMode === 'LIVE'
                  ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                  : selectedMode === 'WALLET'
                  ? 'bg-purple-500/10 text-purple-400 border border-purple-500/20'
                  : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
              }`}
            >
              {selectedMode}
            </span>
          </div>

          {/* Large Hero Metric */}
          <div className="flex items-baseline gap-2.5 mt-1">
            <span
              className={`text-2xl sm:text-3xl font-extrabold font-mono tracking-tight tabular-nums ${
                isNetPositive ? 'text-[#80efad]' : 'text-[#ff646e]'
              }`}
            >
              {isNetPositive ? '+' : ''}
              {formatUsd(chartStats.totalPnlUsd)}
            </span>
            <span className="text-xs sm:text-sm text-slate-400 font-mono">
              ≈ {isNetPositive ? '+' : ''}
              {formatIdr(chartStats.totalPnlIdr)}
            </span>
            {chartStats.totalTrades > 0 && (
              <span
                className={`text-[11px] font-mono font-semibold px-2 py-0.5 rounded-md ${
                  isNetPositive
                    ? 'bg-emerald-500/15 text-emerald-300'
                    : 'bg-rose-500/15 text-rose-300'
                }`}
              >
                {chartStats.winRatePct.toFixed(1)}% WR
              </span>
            )}
          </div>
        </div>

        {/* Right Controls: Segmented Button & Collapse */}
        <div className="flex items-center gap-2 self-start sm:self-center">
          <div className="flex items-center bg-[#171d23] p-1 rounded-xl border border-[#303a43] text-xs font-mono">
            <button
              type="button"
              onClick={() => setChartType('cumulative')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all duration-150 font-medium ${
                chartType === 'cumulative'
                  ? 'bg-[#45ae68] text-white font-bold shadow-md shadow-emerald-500/20'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
              title="Kurva Pertumbuhan Akumulasi PnL (Gaya Neon)"
            >
              <LucideIcon name="trending-up" className="w-3.5 h-3.5" />
              <span>Gaya Line Chart</span>
            </button>
            <button
              type="button"
              onClick={() => setChartType('daily')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all duration-150 font-medium ${
                chartType === 'daily'
                  ? 'bg-cyan-600 text-white font-bold shadow-md shadow-cyan-500/20'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
              title="Grafik Batang Net PnL Harian"
            >
              <LucideIcon name="bar-chart-2" className="w-3.5 h-3.5" />
              <span>Batang Harian</span>
            </button>
          </div>

          <button
            type="button"
            onClick={() => setIsCollapsed(!isCollapsed)}
            className="p-2 rounded-xl bg-[#171d23] hover:bg-slate-800 text-slate-400 hover:text-slate-200 border border-[#303a43] transition"
            title={isCollapsed ? 'Tampilkan Grafik' : 'Sembunyikan Grafik'}
          >
            <LucideIcon name={isCollapsed ? 'chevron-down' : 'chevron-up'} className="w-4 h-4" />
          </button>
        </div>
      </div>

      {!isCollapsed && (
        <>
          {/* Chart Canvas Area */}
          <div
            ref={containerRef}
            className="relative w-full h-64 bg-[#080a0c] rounded-xl border border-slate-800/80 overflow-hidden cursor-crosshair select-none"
          >
            {timelineData.length === 0 ? (
              <div className="w-full h-full flex items-center justify-center text-xs text-slate-500 font-mono">
                Belum ada data transaksi yang tercatat pada bulan ini.
              </div>
            ) : (
              <canvas
                ref={canvasRef}
                onPointerMove={handlePointerMove}
                onPointerLeave={handlePointerLeave}
                onClick={handleCanvasClick}
                className="w-full h-full block touch-pan-y"
              />
            )}

            {/* Floating Tooltip matching user CSS */}
            {activeHoverData && (
              <div
                style={{
                  left: Math.min(
                    (pointer?.x ?? 50) + 12,
                    (containerRef.current?.clientWidth || 300) - 220
                  ),
                  top: Math.max(10, (pointer?.y ?? 50) - 55),
                }}
                className="pointer-events-none absolute bg-[#171d23] border border-[#303a43] rounded-md px-3 py-2 text-xs text-slate-100 shadow-2xl z-20 font-mono transition-all duration-75 space-y-1"
              >
                <div className="flex items-center justify-between pb-1 border-b border-[#303a43] gap-2">
                  <span className="font-bold text-white">
                    {activeHoverData.weekdayName}, {activeHoverData.dayNumber} {monthLabel}
                  </span>
                  {activeHoverData.isToday && (
                    <span className="text-[9px] px-1.5 py-0.2 rounded bg-cyan-500/20 text-cyan-300 font-bold">
                      HARI INI
                    </span>
                  )}
                </div>

                <div>
                  Kumulatif: <strong className={activeHoverData.cumPnlUsd >= 0 ? 'text-[#80efad]' : 'text-[#ff646e]'}>{activeHoverData.cumPnlUsd >= 0 ? '+' : ''}{formatUsd(activeHoverData.cumPnlUsd)}</strong>
                </div>
                <div>
                  Hari Ini: <span className={activeHoverData.dayPnlUsd >= 0 ? 'text-[#80efad]' : 'text-[#ff646e]'}>{activeHoverData.dayPnlUsd >= 0 ? '+' : ''}{formatUsd(activeHoverData.dayPnlUsd)}</span>
                </div>
                {activeHoverData.tradesCount > 0 && (
                  <div className="text-[10px] text-slate-400">
                    {activeHoverData.tradesCount} Trade ({activeHoverData.winTrades}W/{activeHoverData.lossTrades}L)
                  </div>
                )}
                <div className="text-[9px] text-cyan-400/90 pt-0.5 border-t border-[#303a43] text-center">
                  Klik untuk pilih tanggal ↗
                </div>
              </div>
            )}
          </div>

          {/* Minimal 4-Metric Footer Bar */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 pt-1 text-xs font-mono">
            <div className="bg-[#171d23] border border-[#303a43] rounded-xl p-2.5">
              <span className="text-[10px] text-slate-400 uppercase tracking-wider block">
                Puncak Profit (Peak)
              </span>
              <span className="text-sm font-bold text-[#80efad] mt-0.5 block tabular-nums">
                +{formatUsd(chartStats.peakPnlUsd)}
              </span>
              <span className="text-[10px] text-slate-400 block truncate">
                ≈ +{formatIdr(chartStats.peakPnlIdr)}
              </span>
            </div>

            <div className="bg-[#171d23] border border-[#303a43] rounded-xl p-2.5">
              <span className="text-[10px] text-slate-400 uppercase tracking-wider block">
                Max Drawdown
              </span>
              <span
                className={`text-sm font-bold mt-0.5 block tabular-nums ${
                  chartStats.maxDrawdownUsd > 0 ? 'text-[#ff646e]' : 'text-slate-400'
                }`}
              >
                -{formatUsd(chartStats.maxDrawdownUsd)}
              </span>
              <span className="text-[10px] text-slate-400 block truncate">
                ≈ -{formatIdr(chartStats.maxDrawdownIdr)}
              </span>
            </div>

            <div className="bg-[#171d23] border border-[#303a43] rounded-xl p-2.5">
              <span className="text-[10px] text-slate-400 uppercase tracking-wider block">
                Rata-Rata / Hari Aktif
              </span>
              <span
                className={`text-sm font-bold mt-0.5 block tabular-nums ${
                  chartStats.avgDailyPnlUsd >= 0 ? 'text-[#80efad]' : 'text-[#ff646e]'
                }`}
              >
                {chartStats.avgDailyPnlUsd >= 0 ? '+' : ''}
                {formatUsd(chartStats.avgDailyPnlUsd)}
              </span>
              <span className="text-[10px] text-slate-400 block truncate">
                ≈ {chartStats.avgDailyPnlUsd >= 0 ? '+' : ''}
                {formatIdr(chartStats.avgDailyPnlIdr)}
              </span>
            </div>

            <div className="bg-[#171d23] border border-[#303a43] rounded-xl p-2.5">
              <span className="text-[10px] text-slate-400 uppercase tracking-wider block">
                Hari Aktif Trading
              </span>
              <span className="text-sm font-bold text-cyan-400 mt-0.5 block tabular-nums">
                {chartStats.activeDays} Hari
              </span>
              <span className="text-[10px] text-slate-400 block truncate">
                {chartStats.totalTrades} Total Closed Trades
              </span>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
