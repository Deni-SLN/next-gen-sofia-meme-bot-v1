import React, { useState, useRef, useCallback, useMemo } from 'react';
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

export function CalendarPnLChart({
  days = [],
  usdIdr = 17960,
  monthLabel = 'Bulan Ini',
  selectedMode = 'PAPER',
  selectedDayDate,
  onSelectDate,
}: CalendarPnLChartProps) {
  const [chartType, setChartType] = useState<'cumulative' | 'daily'>('cumulative');
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);
  const [isCollapsed, setIsCollapsed] = useState<boolean>(false);
  const chartRef = useRef<HTMLDivElement>(null);

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

  // Overall performance stats for the chart header
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
        avgDailyPnlUsd: 0,
        avgDailyPnlIdr: 0,
      };
    }

    const last = timelineData[timelineData.length - 1];
    const totalPnlUsd = last?.cumPnlUsd || 0;
    const totalPnlIdr = last?.cumPnlIdr || 0;

    let peakPnlUsd = 0;
    let maxDrawdownUsd = 0;
    let activeDays = 0;
    let sumActiveDailyPnl = 0;

    timelineData.forEach((pt) => {
      if (pt.cumPnlUsd > peakPnlUsd) peakPnlUsd = pt.cumPnlUsd;
      const dd = peakPnlUsd - pt.cumPnlUsd;
      if (dd > maxDrawdownUsd) maxDrawdownUsd = dd;

      if (pt.tradesCount > 0) {
        activeDays++;
        sumActiveDailyPnl += pt.dayPnlUsd;
      }
    });

    const avgDailyPnlUsd = activeDays > 0 ? sumActiveDailyPnl / activeDays : 0;

    return {
      totalPnlUsd,
      totalPnlIdr,
      peakPnlUsd,
      peakPnlIdr: peakPnlUsd * rate,
      maxDrawdownUsd,
      maxDrawdownIdr: maxDrawdownUsd * rate,
      activeDays,
      avgDailyPnlUsd,
      avgDailyPnlIdr: avgDailyPnlUsd * rate,
    };
  }, [timelineData, rate]);

  // SVG Geometry Dimensions
  const SVG_WIDTH = 1000;
  const SVG_HEIGHT = 200;
  const PADDING_TOP = 28;
  const PADDING_BOTTOM = 32;
  const PLOT_HEIGHT = SVG_HEIGHT - PADDING_TOP - PADDING_BOTTOM;

  // Build Cumulative Spline Geometry
  const cumulativeGeometry = useMemo(() => {
    if (timelineData.length === 0) return null;

    const values = timelineData.map((d) => d.cumPnlUsd);
    const minVal = Math.min(0, ...values);
    const maxVal = Math.max(0, ...values);
    const range = Math.max(0.01, maxVal - minVal);

    const getY = (val: number) => {
      const normalized = (val - minVal) / range;
      return PADDING_TOP + PLOT_HEIGHT * (1 - normalized);
    };

    const zeroY = getY(0);

    const points = timelineData.map((d, i) => {
      const x = (i / Math.max(1, timelineData.length - 1)) * (SVG_WIDTH - 40) + 20;
      const y = getY(d.cumPnlUsd);
      return { x, y, data: d };
    });

    // Spline curve path
    let linePath = `M ${points[0].x.toFixed(1)} ${points[0].y.toFixed(1)}`;
    for (let i = 0; i < points.length - 1; i++) {
      const p0 = points[i];
      const p1 = points[i + 1];
      const cx1 = p0.x + (p1.x - p0.x) * 0.45;
      const cy1 = p0.y;
      const cx2 = p0.x + (p1.x - p0.x) * 0.55;
      const cy2 = p1.y;
      linePath += ` C ${cx1.toFixed(1)} ${cy1.toFixed(1)}, ${cx2.toFixed(1)} ${cy2.toFixed(1)}, ${p1.x.toFixed(1)} ${p1.y.toFixed(1)}`;
    }

    const lastX = points[points.length - 1].x;
    const firstX = points[0].x;
    const areaPath = `${linePath} L ${lastX.toFixed(1)} ${SVG_HEIGHT - PADDING_BOTTOM} L ${firstX.toFixed(1)} ${SVG_HEIGHT - PADDING_BOTTOM} Z`;

    return {
      points,
      linePath,
      areaPath,
      zeroY,
      minVal,
      maxVal,
    };
  }, [timelineData, PLOT_HEIGHT, PADDING_TOP, PADDING_BOTTOM, SVG_HEIGHT]);

  // Build Daily Bar Geometry
  const dailyBarGeometry = useMemo(() => {
    if (timelineData.length === 0) return null;

    const values = timelineData.map((d) => d.dayPnlUsd);
    const minVal = Math.min(0, ...values);
    const maxVal = Math.max(0, ...values);
    const absMax = Math.max(0.01, Math.abs(minVal), Math.abs(maxVal));

    const zeroY = PADDING_TOP + PLOT_HEIGHT / 2;
    const barWidth = Math.max(6, Math.min(22, (SVG_WIDTH - 60) / timelineData.length - 4));

    const bars = timelineData.map((d, i) => {
      const x = (i / Math.max(1, timelineData.length - 1)) * (SVG_WIDTH - 60) + 30;
      const heightFrac = Math.abs(d.dayPnlUsd) / absMax;
      const barHeight = Math.max(d.dayPnlUsd !== 0 ? 3 : 1, heightFrac * (PLOT_HEIGHT / 2 - 4));

      const isPositive = d.dayPnlUsd >= 0;
      const y = isPositive ? zeroY - barHeight : zeroY;

      return {
        x,
        y,
        width: barWidth,
        height: barHeight,
        isPositive,
        data: d,
      };
    });

    return {
      bars,
      zeroY,
      absMax,
    };
  }, [timelineData, PLOT_HEIGHT, PADDING_TOP]);

  // Mouse handler for hover inspection
  const handleMouseMove = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (!chartRef.current || timelineData.length === 0) return;
      const rect = chartRef.current.getBoundingClientRect();
      const clickX = e.clientX - rect.left;
      const ratio = Math.max(0, Math.min(1, clickX / rect.width));
      const targetIdx = Math.round(ratio * (timelineData.length - 1));
      setHoveredIdx(targetIdx);
    },
    [timelineData.length]
  );

  const handleMouseLeave = useCallback(() => {
    setHoveredIdx(null);
  }, []);

  const activeHoverData = hoveredIdx !== null ? timelineData[hoveredIdx] : null;
  const isNetPositive = chartStats.totalPnlUsd >= 0;

  return (
    <div className="bg-obsidian-900 border border-obsidian-700 rounded-xl p-4 shadow-lg space-y-3">
      {/* Header: Title, Quick KPI, View Switchers, and Collapse Button */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 pb-3 border-b border-obsidian-800">
        <div className="flex items-center gap-2.5">
          <div
            className={`flex items-center justify-center w-8 h-8 rounded-lg border ${
              isNetPositive
                ? 'bg-emerald-500/15 border-emerald-500/30 text-emerald-400'
                : 'bg-rose-500/15 border-rose-500/30 text-rose-400'
            }`}
          >
            <LucideIcon name={chartType === 'cumulative' ? 'trending-up' : 'bar-chart-2'} className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-bold text-slate-100 flex items-center gap-1.5">
                <span>Grafik Performa PnL</span>
                <span className="text-cyan-400 font-mono text-xs font-semibold">({monthLabel})</span>
              </h2>
              <span
                className={`text-[9px] font-mono px-1.5 py-0.5 rounded border font-bold uppercase ${
                  selectedMode === 'LIVE'
                    ? 'bg-rose-500/15 text-rose-300 border-rose-500/30'
                    : selectedMode === 'WALLET'
                    ? 'bg-purple-500/15 text-purple-300 border-purple-500/30'
                    : 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
                }`}
              >
                {selectedMode}
              </span>
            </div>
            <p className="text-[11px] text-slate-400 font-sans">
              Visualisasi tren kumulatif &amp; PnL bersih harian kalender trading.
            </p>
          </div>
        </div>

        {/* Action Controls & KPI Pills */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Quick Stats: Peak & Max Drawdown */}
          <div className="hidden lg:flex items-center gap-2 text-[11px] font-mono bg-obsidian-950 px-2.5 py-1 rounded-lg border border-obsidian-800">
            <span className="text-slate-400">
              Puncak:{' '}
              <strong className="text-emerald-400">
                +{formatUsd(chartStats.peakPnlUsd)} ({formatIdr(chartStats.peakPnlIdr)})
              </strong>
            </span>
            <span className="text-slate-700">|</span>
            <span className="text-slate-400">
              Max DD:{' '}
              <strong className={chartStats.maxDrawdownUsd > 0 ? 'text-rose-400' : 'text-slate-400'}>
                -{formatUsd(chartStats.maxDrawdownUsd)}
              </strong>
            </span>
          </div>

          {/* Toggle Type: Cumulative Curve vs Daily Bars */}
          <div className="flex items-center bg-obsidian-950 p-0.5 rounded-lg border border-obsidian-800 text-xs font-mono">
            <button
              type="button"
              onClick={() => setChartType('cumulative')}
              className={`flex items-center gap-1 px-2.5 py-1 rounded-md transition ${
                chartType === 'cumulative'
                  ? 'bg-emerald-500 text-obsidian-950 font-bold shadow-glow-emerald'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
              title="Grafik Garis Pertumbuhan Kumulatif PnL"
            >
              <LucideIcon name="trending-up" className="w-3.5 h-3.5" />
              <span>Kumulatif</span>
            </button>
            <button
              type="button"
              onClick={() => setChartType('daily')}
              className={`flex items-center gap-1 px-2.5 py-1 rounded-md transition ${
                chartType === 'daily'
                  ? 'bg-cyan-500 text-obsidian-950 font-bold shadow-glow-cyan'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
              title="Grafik Batang Net PnL Per Hari (Hijau Profit / Merah Rugi)"
            >
              <LucideIcon name="bar-chart-2" className="w-3.5 h-3.5" />
              <span>Batang Harian</span>
            </button>
          </div>

          {/* Collapse/Expand Button */}
          <button
            type="button"
            onClick={() => setIsCollapsed(!isCollapsed)}
            className="p-1.5 rounded-lg bg-obsidian-950 hover:bg-obsidian-800 text-slate-400 hover:text-slate-200 border border-obsidian-800 transition"
            title={isCollapsed ? 'Perluas Grafik' : 'Perkecil Grafik'}
          >
            <LucideIcon name={isCollapsed ? 'chevron-down' : 'chevron-up'} className="w-4 h-4" />
          </button>
        </div>
      </div>

      {!isCollapsed && (
        <>
          {/* Active Inspection HUD Banner (Floating or Hovered Day) */}
          <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-1.5 rounded-lg bg-obsidian-950 border border-obsidian-800 text-xs font-mono">
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-cyan-400 font-bold uppercase tracking-wider bg-cyan-500/10 px-2 py-0.5 rounded border border-cyan-500/30">
                {activeHoverData
                  ? `Titik Inspeksi: Tgl ${activeHoverData.dayNumber} (${activeHoverData.date})`
                  : selectedDayDate
                  ? `Tanggal Terpilih: ${selectedDayDate}`
                  : `Ringkasan Akhir ${monthLabel}`}
              </span>
              {activeHoverData?.isToday && (
                <span className="text-[9px] px-1.5 py-0.2 rounded bg-cyan-500/20 text-cyan-300 font-bold">
                  HARI INI
                </span>
              )}
            </div>

            {/* Metric Displays for Hovered or Selected Day */}
            {activeHoverData ? (
              <div className="flex flex-wrap items-center gap-3 text-[11px]">
                <span className="text-slate-400">
                  PnL Hari Ini:{' '}
                  <strong
                    className={
                      activeHoverData.dayPnlUsd > 0
                        ? 'text-emerald-400'
                        : activeHoverData.dayPnlUsd < 0
                        ? 'text-rose-400'
                        : 'text-slate-300'
                    }
                  >
                    {activeHoverData.dayPnlUsd >= 0 ? '+' : ''}
                    {formatUsd(activeHoverData.dayPnlUsd)} ({activeHoverData.dayPnlIdr >= 0 ? '+' : ''}
                    {formatIdr(activeHoverData.dayPnlIdr)})
                  </strong>
                </span>
                <span className="text-slate-700">|</span>
                <span className="text-slate-400">
                  Kumulatif s/d Tgl ini:{' '}
                  <strong
                    className={
                      activeHoverData.cumPnlUsd >= 0 ? 'text-emerald-400' : 'text-rose-400'
                    }
                  >
                    {activeHoverData.cumPnlUsd >= 0 ? '+' : ''}
                    {formatUsd(activeHoverData.cumPnlUsd)}
                  </strong>
                </span>
                <span className="text-slate-700">|</span>
                <span className="text-slate-400">
                  Aktivitas:{' '}
                  <strong className="text-slate-200">
                    {activeHoverData.tradesCount} Trade ({activeHoverData.winTrades}W/{activeHoverData.lossTrades}L) • WR {activeHoverData.winRate}%
                  </strong>
                </span>
              </div>
            ) : (
              <div className="flex flex-wrap items-center gap-3 text-[11px]">
                <span className="text-slate-400">
                  Total PnL Bulan Ini:{' '}
                  <strong className={isNetPositive ? 'text-emerald-400' : 'text-rose-400'}>
                    {isNetPositive ? '+' : ''}
                    {formatUsd(chartStats.totalPnlUsd)} ({isNetPositive ? '+' : ''}
                    {formatIdr(chartStats.totalPnlIdr)})
                  </strong>
                </span>
                <span className="text-slate-700">|</span>
                <span className="text-slate-400">
                  Hari Aktif Trade: <strong className="text-cyan-300">{chartStats.activeDays} Hari</strong>
                </span>
                <span className="text-slate-700">|</span>
                <span className="text-slate-400">
                  Rata-rata/Hari: <strong className="text-slate-200">{formatUsd(chartStats.avgDailyPnlUsd)}</strong>
                </span>
              </div>
            )}
          </div>

          {/* SVG Interactive Canvas */}
          <div
            ref={chartRef}
            onMouseMove={handleMouseMove}
            onMouseLeave={handleMouseLeave}
            className="relative w-full h-48 bg-obsidian-950/80 rounded-xl border border-obsidian-800 overflow-hidden cursor-crosshair select-none"
          >
            {timelineData.length === 0 ? (
              <div className="w-full h-full flex items-center justify-center text-xs text-slate-500 font-mono">
                Belum ada data transaksi untuk bulan ini.
              </div>
            ) : (
              <svg
                viewBox={`0 0 ${SVG_WIDTH} ${SVG_HEIGHT}`}
                preserveAspectRatio="none"
                className="w-full h-full"
              >
                <defs>
                  {/* Linear Gradient for Cumulative Area */}
                  <linearGradient id="calPnlEmeraldGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#10b981" stopOpacity="0.35" />
                    <stop offset="65%" stopColor="#10b981" stopOpacity="0.08" />
                    <stop offset="100%" stopColor="#10b981" stopOpacity="0.0" />
                  </linearGradient>

                  <linearGradient id="calPnlRoseGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#f43f5e" stopOpacity="0.35" />
                    <stop offset="65%" stopColor="#f43f5e" stopOpacity="0.08" />
                    <stop offset="100%" stopColor="#f43f5e" stopOpacity="0.0" />
                  </linearGradient>

                  {/* Bar Gradients */}
                  <linearGradient id="barGreenGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#34d399" stopOpacity="0.9" />
                    <stop offset="100%" stopColor="#059669" stopOpacity="0.4" />
                  </linearGradient>

                  <linearGradient id="barRedGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#e11d48" stopOpacity="0.4" />
                    <stop offset="100%" stopColor="#f43f5e" stopOpacity="0.9" />
                  </linearGradient>
                </defs>

                {/* Horizontal Gridlines */}
                <line
                  x1="0"
                  y1={PADDING_TOP}
                  x2={SVG_WIDTH}
                  y2={PADDING_TOP}
                  stroke="#334155"
                  strokeWidth="0.8"
                  strokeDasharray="4 4"
                  opacity="0.25"
                />
                <line
                  x1="0"
                  y1={SVG_HEIGHT / 2}
                  x2={SVG_WIDTH}
                  y2={SVG_HEIGHT / 2}
                  stroke="#334155"
                  strokeWidth="0.8"
                  strokeDasharray="4 4"
                  opacity="0.25"
                />
                <line
                  x1="0"
                  y1={SVG_HEIGHT - PADDING_BOTTOM}
                  x2={SVG_WIDTH}
                  y2={SVG_HEIGHT - PADDING_BOTTOM}
                  stroke="#334155"
                  strokeWidth="0.8"
                  strokeDasharray="4 4"
                  opacity="0.25"
                />

                {/* MODE 1: CUMULATIVE CURVE */}
                {chartType === 'cumulative' && cumulativeGeometry && (
                  <>
                    {/* Zero Level Baseline */}
                    <line
                      x1="0"
                      y1={cumulativeGeometry.zeroY}
                      x2={SVG_WIDTH}
                      y2={cumulativeGeometry.zeroY}
                      stroke="#64748b"
                      strokeWidth="1.2"
                      strokeDasharray="3 3"
                      opacity="0.4"
                    />

                    {/* Gradient Area Fill */}
                    <path
                      d={cumulativeGeometry.areaPath}
                      fill={isNetPositive ? 'url(#calPnlEmeraldGrad)' : 'url(#calPnlRoseGrad)'}
                    />

                    {/* Glowing Spline Stroke Line */}
                    <path
                      d={cumulativeGeometry.linePath}
                      fill="none"
                      stroke={isNetPositive ? '#10b981' : '#f43f5e'}
                      strokeWidth="2.8"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      className="drop-shadow-[0_0_8px_rgba(16,185,129,0.5)]"
                    />

                    {/* Data Points on Days With Trades or Selected Day */}
                    {cumulativeGeometry.points.map((pt, i) => {
                      const hasTrades = pt.data.tradesCount > 0;
                      const isSelected = selectedDayDate === pt.data.date;
                      const isHovered = hoveredIdx === i;

                      if (!hasTrades && !isSelected && !isHovered && !pt.data.isToday) return null;

                      return (
                        <g
                          key={pt.data.date}
                          onClick={() => onSelectDate(pt.data.date)}
                          className="cursor-pointer"
                        >
                          {/* Outer pulse for selected or hovered */}
                          {(isSelected || isHovered) && (
                            <circle
                              cx={pt.x}
                              cy={pt.y}
                              r={isSelected ? 9 : 7}
                              fill="none"
                              stroke={isSelected ? '#38bdf8' : isNetPositive ? '#10b981' : '#f43f5e'}
                              strokeWidth="1.5"
                              className="animate-ping opacity-60"
                            />
                          )}

                          {/* Main node dot */}
                          <circle
                            cx={pt.x}
                            cy={pt.y}
                            r={isSelected ? 6 : hasTrades ? 4.5 : 3}
                            fill={
                              isSelected
                                ? '#38bdf8'
                                : pt.data.dayPnlUsd > 0
                                ? '#10b981'
                                : pt.data.dayPnlUsd < 0
                                ? '#f43f5e'
                                : '#94a3b8'
                            }
                            stroke="#0b0f17"
                            strokeWidth="2"
                          />
                        </g>
                      );
                    })}
                  </>
                )}

                {/* MODE 2: DAILY NET PNL BARS */}
                {chartType === 'daily' && dailyBarGeometry && (
                  <>
                    {/* Zero Level Baseline */}
                    <line
                      x1="0"
                      y1={dailyBarGeometry.zeroY}
                      x2={SVG_WIDTH}
                      y2={dailyBarGeometry.zeroY}
                      stroke="#94a3b8"
                      strokeWidth="1.2"
                      opacity="0.5"
                    />

                    {/* Day Net PnL Bars */}
                    {dailyBarGeometry.bars.map((bar, i) => {
                      const isSelected = selectedDayDate === bar.data.date;
                      const isHovered = hoveredIdx === i;

                      return (
                        <g
                          key={bar.data.date}
                          onClick={() => onSelectDate(bar.data.date)}
                          className="cursor-pointer group"
                        >
                          <rect
                            x={bar.x - bar.width / 2}
                            y={bar.y}
                            width={bar.width}
                            height={bar.height}
                            rx="2"
                            fill={bar.isPositive ? 'url(#barGreenGrad)' : 'url(#barRedGrad)'}
                            stroke={
                              isSelected
                                ? '#38bdf8'
                                : isHovered
                                ? '#f8fafc'
                                : bar.isPositive
                                ? '#10b981'
                                : '#f43f5e'
                            }
                            strokeWidth={isSelected ? '2' : isHovered ? '1.5' : '0.5'}
                            className="transition-all duration-150"
                          />
                        </g>
                      );
                    })}
                  </>
                )}

                {/* Vertical Cursor Crosshair on Hover */}
                {hoveredIdx !== null && (
                  <line
                    x1={
                      chartType === 'cumulative'
                        ? cumulativeGeometry?.points[hoveredIdx]?.x ?? 0
                        : dailyBarGeometry?.bars[hoveredIdx]?.x ?? 0
                    }
                    y1={PADDING_TOP}
                    x2={
                      chartType === 'cumulative'
                        ? cumulativeGeometry?.points[hoveredIdx]?.x ?? 0
                        : dailyBarGeometry?.bars[hoveredIdx]?.x ?? 0
                    }
                    y2={SVG_HEIGHT - PADDING_BOTTOM}
                    stroke="#38bdf8"
                    strokeWidth="1.2"
                    strokeDasharray="2 2"
                    opacity="0.8"
                  />
                )}

                {/* X-Axis Date Labels along bottom */}
                {timelineData.map((d, i) => {
                  // Show label every 3 to 5 days, or on first, last, today
                  const isFirst = i === 0;
                  const isLast = i === timelineData.length - 1;
                  const isStep = d.dayNumber % 5 === 0 || d.dayNumber === 1;

                  if (!isFirst && !isLast && !isStep && !d.isToday) return null;

                  const xPos =
                    chartType === 'cumulative'
                      ? cumulativeGeometry?.points[i]?.x ?? 0
                      : dailyBarGeometry?.bars[i]?.x ?? 0;

                  return (
                    <text
                      key={`lbl-${d.date}`}
                      x={xPos}
                      y={SVG_HEIGHT - 10}
                      textAnchor="middle"
                      fill={d.isToday ? '#38bdf8' : '#64748b'}
                      fontSize="9"
                      fontFamily="monospace"
                      fontWeight={d.isToday ? 'bold' : 'normal'}
                    >
                      {d.dayNumber}
                    </text>
                  );
                })}
              </svg>
            )}

            {/* Quick Interactive Tooltip Card on Hover */}
            {activeHoverData && (
              <div
                className="pointer-events-none absolute bottom-3 right-3 bg-obsidian-950/95 border border-cyan-500/40 rounded-lg p-2.5 shadow-2xl backdrop-blur-md text-xs font-mono z-20 space-y-1"
              >
                <div className="flex items-center justify-between gap-3 text-[11px] pb-1 border-b border-obsidian-800">
                  <span className="font-bold text-slate-200">
                    {activeHoverData.date} ({activeHoverData.dayNumber})
                  </span>
                  <span className="text-cyan-400 font-extrabold">
                    {activeHoverData.tradesCount} Trade
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 text-[10px]">
                  <span className="text-slate-400">Net Hari Ini:</span>
                  <span
                    className={`text-right font-bold ${
                      activeHoverData.dayPnlUsd >= 0 ? 'text-emerald-400' : 'text-rose-400'
                    }`}
                  >
                    {activeHoverData.dayPnlUsd >= 0 ? '+' : ''}
                    {formatUsd(activeHoverData.dayPnlUsd)}
                  </span>
                  <span className="text-slate-400">Kumulatif:</span>
                  <span
                    className={`text-right font-bold ${
                      activeHoverData.cumPnlUsd >= 0 ? 'text-emerald-400' : 'text-rose-400'
                    }`}
                  >
                    {activeHoverData.cumPnlUsd >= 0 ? '+' : ''}
                    {formatUsd(activeHoverData.cumPnlUsd)}
                  </span>
                  <span className="text-slate-400">Win Rate:</span>
                  <span className="text-right text-slate-300 font-semibold">
                    {activeHoverData.winRate}% ({activeHoverData.winTrades}W/{activeHoverData.lossTrades}L)
                  </span>
                  {activeHoverData.feesIdr > 0 && (
                    <>
                      <span className="text-slate-400">Biaya Gas:</span>
                      <span className="text-right text-amber-300">
                        {formatIdr(activeHoverData.feesIdr)}
                      </span>
                    </>
                  )}
                </div>
                <div className="text-[9px] text-cyan-300/80 pt-0.5 border-t border-obsidian-800/60 text-center">
                  💡 Klik titik ini untuk membuka rincian trade
                </div>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
