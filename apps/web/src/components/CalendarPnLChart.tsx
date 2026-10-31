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

  // Overall performance stats for the chart header & footer
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
    const totalPnlUsd = last?.cumPnlUsd || 0;
    const totalPnlIdr = last?.cumPnlIdr || 0;

    let peakPnlUsd = 0;
    let maxDrawdownUsd = 0;
    let activeDays = 0;
    let sumActiveDailyPnl = 0;
    let totalTrades = 0;
    let winTrades = 0;

    timelineData.forEach((pt) => {
      if (pt.cumPnlUsd > peakPnlUsd) peakPnlUsd = pt.cumPnlUsd;
      const dd = peakPnlUsd - pt.cumPnlUsd;
      if (dd > maxDrawdownUsd) maxDrawdownUsd = dd;

      if (pt.tradesCount > 0) {
        activeDays++;
        sumActiveDailyPnl += pt.dayPnlUsd;
        totalTrades += pt.tradesCount;
        winTrades += pt.winTrades;
      }
    });

    const avgDailyPnlUsd = activeDays > 0 ? sumActiveDailyPnl / activeDays : 0;
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

  // SVG Geometry Constants
  const SVG_WIDTH = 1000;
  const SVG_HEIGHT = 220;
  const PADDING_TOP = 24;
  const PADDING_BOTTOM = 34;
  const PADDING_LEFT = 24;
  const PADDING_RIGHT = 68; // Space for right Y-axis values
  const PLOT_WIDTH = SVG_WIDTH - PADDING_LEFT - PADDING_RIGHT;
  const PLOT_HEIGHT = SVG_HEIGHT - PADDING_TOP - PADDING_BOTTOM;

  // Build Cumulative Spline Geometry (Clean Linear/Stripe style)
  const cumulativeGeometry = useMemo(() => {
    if (timelineData.length === 0) return null;

    const values = timelineData.map((d) => d.cumPnlUsd);
    let minVal = Math.min(0, ...values);
    let maxVal = Math.max(0, ...values);

    // Give 10% breathing room top and bottom
    const span = maxVal - minVal;
    const padding = span > 0 ? span * 0.12 : 1;
    minVal -= padding;
    maxVal += padding;
    const range = Math.max(0.01, maxVal - minVal);

    const getY = (val: number) => {
      const normalized = (val - minVal) / range;
      return PADDING_TOP + PLOT_HEIGHT * (1 - normalized);
    };

    const zeroY = getY(0);

    const points = timelineData.map((d, i) => {
      const x = PADDING_LEFT + (i / Math.max(1, timelineData.length - 1)) * PLOT_WIDTH;
      const y = getY(d.cumPnlUsd);
      return { x, y, data: d };
    });

    // Spline curve path with smooth Bézier control points
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
    const baselineY = SVG_HEIGHT - PADDING_BOTTOM;
    const areaPath = `${linePath} L ${lastX.toFixed(1)} ${baselineY} L ${firstX.toFixed(1)} ${baselineY} Z`;

    // Reference levels for Y-axis
    const levels = [
      { val: maxVal - padding, y: getY(maxVal - padding) },
      { val: 0, y: zeroY },
      { val: minVal + padding, y: getY(minVal + padding) },
    ];

    return {
      points,
      linePath,
      areaPath,
      zeroY,
      levels,
      minVal,
      maxVal,
    };
  }, [timelineData, PLOT_WIDTH, PLOT_HEIGHT, PADDING_TOP, PADDING_BOTTOM, PADDING_LEFT, SVG_HEIGHT]);

  // Build Daily Bar Geometry
  const dailyBarGeometry = useMemo(() => {
    if (timelineData.length === 0) return null;

    const values = timelineData.map((d) => d.dayPnlUsd);
    const minVal = Math.min(0, ...values);
    const maxVal = Math.max(0, ...values);
    const absMax = Math.max(0.01, Math.abs(minVal), Math.abs(maxVal)) * 1.15;

    const zeroY = PADDING_TOP + PLOT_HEIGHT / 2;
    const barWidth = Math.max(6, Math.min(20, (PLOT_WIDTH / timelineData.length) * 0.65));

    const bars = timelineData.map((d, i) => {
      const x = PADDING_LEFT + (i / Math.max(1, timelineData.length - 1)) * PLOT_WIDTH;
      const heightFrac = Math.abs(d.dayPnlUsd) / absMax;
      const barHeight = Math.max(d.dayPnlUsd !== 0 ? 3 : 1, heightFrac * (PLOT_HEIGHT / 2 - 6));

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

    const levels = [
      { val: absMax * 0.8, y: zeroY - (PLOT_HEIGHT / 2 - 8) * 0.8 },
      { val: 0, y: zeroY },
      { val: -absMax * 0.8, y: zeroY + (PLOT_HEIGHT / 2 - 8) * 0.8 },
    ];

    return {
      bars,
      zeroY,
      absMax,
      levels,
    };
  }, [timelineData, PLOT_WIDTH, PLOT_HEIGHT, PADDING_TOP, PADDING_LEFT]);

  // Mouse move handler for crosshair inspection
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
    <div className="bg-[#0e121b] border border-slate-800/80 rounded-2xl p-4 sm:p-5 shadow-2xl backdrop-blur-md space-y-4">
      {/* Top Header: Clean Typographic Metric & Segmented Controls */}
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
                isNetPositive ? 'text-emerald-400' : 'text-rose-400'
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

        {/* Right Controls: Minimalist Linear-Style Segmented Pill Toggle & Collapse */}
        <div className="flex items-center gap-2 self-start sm:self-center">
          <div className="flex items-center bg-[#141824] p-1 rounded-xl border border-slate-800 text-xs font-mono">
            <button
              type="button"
              onClick={() => setChartType('cumulative')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all duration-150 font-medium ${
                chartType === 'cumulative'
                  ? 'bg-emerald-500 text-slate-950 font-bold shadow-md shadow-emerald-500/20'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
              title="Kurva Pertumbuhan Akumulasi PnL"
            >
              <LucideIcon name="trending-up" className="w-3.5 h-3.5" />
              <span>Kurva Kumulatif</span>
            </button>
            <button
              type="button"
              onClick={() => setChartType('daily')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all duration-150 font-medium ${
                chartType === 'daily'
                  ? 'bg-cyan-500 text-slate-950 font-bold shadow-md shadow-cyan-500/20'
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
            className="p-2 rounded-xl bg-[#141824] hover:bg-slate-800 text-slate-400 hover:text-slate-200 border border-slate-800 transition"
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
            ref={chartRef}
            onMouseMove={handleMouseMove}
            onMouseLeave={handleMouseLeave}
            className="relative w-full h-56 bg-[#090c13] rounded-xl border border-slate-800/80 overflow-hidden cursor-crosshair select-none"
          >
            {timelineData.length === 0 ? (
              <div className="w-full h-full flex items-center justify-center text-xs text-slate-500 font-mono">
                Belum ada data transaksi yang tercatat pada bulan ini.
              </div>
            ) : (
              <svg
                viewBox={`0 0 ${SVG_WIDTH} ${SVG_HEIGHT}`}
                preserveAspectRatio="none"
                className="w-full h-full"
              >
                <defs>
                  {/* Subtle, Linear-grade Area Gradients */}
                  <linearGradient id="pnlEmeraldArea" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#10b981" stopOpacity="0.22" />
                    <stop offset="60%" stopColor="#10b981" stopOpacity="0.04" />
                    <stop offset="100%" stopColor="#10b981" stopOpacity="0.0" />
                  </linearGradient>

                  <linearGradient id="pnlRoseArea" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#f43f5e" stopOpacity="0.22" />
                    <stop offset="60%" stopColor="#f43f5e" stopOpacity="0.04" />
                    <stop offset="100%" stopColor="#f43f5e" stopOpacity="0.0" />
                  </linearGradient>

                  {/* Clean Bar Gradients */}
                  <linearGradient id="cleanBarGreen" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#34d399" stopOpacity="0.95" />
                    <stop offset="100%" stopColor="#059669" stopOpacity="0.6" />
                  </linearGradient>

                  <linearGradient id="cleanBarRed" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#e11d48" stopOpacity="0.6" />
                    <stop offset="100%" stopColor="#f43f5e" stopOpacity="0.95" />
                  </linearGradient>
                </defs>

                {/* Faint Horizontal Reference Gridlines */}
                {chartType === 'cumulative' && cumulativeGeometry && (
                  <>
                    {cumulativeGeometry.levels.map((lvl, idx) => (
                      <g key={`lvl-${idx}`}>
                        <line
                          x1={PADDING_LEFT}
                          y1={lvl.y}
                          x2={SVG_WIDTH - PADDING_RIGHT}
                          y2={lvl.y}
                          stroke="#1e293b"
                          strokeWidth="1"
                          strokeDasharray={lvl.val === 0 ? '4 4' : '2 4'}
                          opacity={lvl.val === 0 ? 0.8 : 0.4}
                        />
                        <text
                          x={SVG_WIDTH - PADDING_RIGHT + 8}
                          y={lvl.y + 3.5}
                          fill={lvl.val === 0 ? '#64748b' : '#475569'}
                          fontSize="9.5"
                          fontFamily="monospace"
                        >
                          {lvl.val >= 0 ? '+' : ''}
                          {formatUsd(lvl.val)}
                        </text>
                      </g>
                    ))}
                  </>
                )}

                {chartType === 'daily' && dailyBarGeometry && (
                  <>
                    {dailyBarGeometry.levels.map((lvl, idx) => (
                      <g key={`lvl-bar-${idx}`}>
                        <line
                          x1={PADDING_LEFT}
                          y1={lvl.y}
                          x2={SVG_WIDTH - PADDING_RIGHT}
                          y2={lvl.y}
                          stroke="#1e293b"
                          strokeWidth="1"
                          strokeDasharray={lvl.val === 0 ? '4 4' : '2 4'}
                          opacity={lvl.val === 0 ? 0.8 : 0.4}
                        />
                        <text
                          x={SVG_WIDTH - PADDING_RIGHT + 8}
                          y={lvl.y + 3.5}
                          fill={lvl.val === 0 ? '#64748b' : '#475569'}
                          fontSize="9.5"
                          fontFamily="monospace"
                        >
                          {lvl.val >= 0 ? '+' : ''}
                          {formatUsd(lvl.val)}
                        </text>
                      </g>
                    ))}
                  </>
                )}

                {/* MODE 1: CUMULATIVE CURVE */}
                {chartType === 'cumulative' && cumulativeGeometry && (
                  <>
                    {/* Area fill */}
                    <path
                      d={cumulativeGeometry.areaPath}
                      fill={isNetPositive ? 'url(#pnlEmeraldArea)' : 'url(#pnlRoseArea)'}
                    />

                    {/* Smooth glowing stroke */}
                    <path
                      d={cumulativeGeometry.linePath}
                      fill="none"
                      stroke={isNetPositive ? '#10b981' : '#f43f5e'}
                      strokeWidth="2.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      style={{
                        filter: `drop-shadow(0 4px 10px ${
                          isNetPositive ? 'rgba(16,185,129,0.3)' : 'rgba(244,63,94,0.3)'
                        })`,
                      }}
                    />

                    {/* Nodes on days with trades */}
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
                          {/* Pulsing ring for selected / hovered */}
                          {(isSelected || isHovered) && (
                            <circle
                              cx={pt.x}
                              cy={pt.y}
                              r={isSelected ? 8.5 : 6.5}
                              fill="none"
                              stroke={isSelected ? '#38bdf8' : isNetPositive ? '#10b981' : '#f43f5e'}
                              strokeWidth="1.5"
                              className="animate-ping opacity-60"
                            />
                          )}

                          {/* Node circle */}
                          <circle
                            cx={pt.x}
                            cy={pt.y}
                            r={isSelected ? 5.5 : hasTrades ? 4 : 2.5}
                            fill={
                              isSelected
                                ? '#38bdf8'
                                : pt.data.dayPnlUsd > 0
                                ? '#10b981'
                                : pt.data.dayPnlUsd < 0
                                ? '#f43f5e'
                                : '#64748b'
                            }
                            stroke="#090c13"
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
                    {/* Zero baseline */}
                    <line
                      x1={PADDING_LEFT}
                      y1={dailyBarGeometry.zeroY}
                      x2={SVG_WIDTH - PADDING_RIGHT}
                      y2={dailyBarGeometry.zeroY}
                      stroke="#475569"
                      strokeWidth="1.2"
                      opacity="0.6"
                    />

                    {/* Bars */}
                    {dailyBarGeometry.bars.map((bar, i) => {
                      const isSelected = selectedDayDate === bar.data.date;
                      const isHovered = hoveredIdx === i;
                      const hasTrades = bar.data.tradesCount > 0;

                      return (
                        <g
                          key={bar.data.date}
                          onClick={() => onSelectDate(bar.data.date)}
                          className="cursor-pointer"
                        >
                          {hasTrades ? (
                            <rect
                              x={bar.x - bar.width / 2}
                              y={bar.y}
                              width={bar.width}
                              height={bar.height}
                              rx="3"
                              fill={bar.isPositive ? 'url(#cleanBarGreen)' : 'url(#cleanBarRed)'}
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
                          ) : (
                            <circle
                              cx={bar.x}
                              cy={dailyBarGeometry.zeroY}
                              r={1.5}
                              fill="#334155"
                            />
                          )}
                        </g>
                      );
                    })}
                  </>
                )}

                {/* Interactive Crosshair Tracking Line */}
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
                    strokeWidth="1"
                    strokeDasharray="3 3"
                    opacity="0.75"
                  />
                )}

                {/* X-Axis Date Numbers Along Bottom */}
                {timelineData.map((d, i) => {
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
                      key={`axis-lbl-${d.date}`}
                      x={xPos}
                      y={SVG_HEIGHT - 12}
                      textAnchor="middle"
                      fill={d.isToday ? '#38bdf8' : '#64748b'}
                      fontSize="9.5"
                      fontFamily="monospace"
                      fontWeight={d.isToday ? 'bold' : 'normal'}
                    >
                      {d.dayNumber}
                    </text>
                  );
                })}
              </svg>
            )}

            {/* Floating Inspection Tooltip HUD (Stripe/Linear style) */}
            {activeHoverData && (
              <div className="pointer-events-none absolute top-3 right-3 sm:right-5 bg-[#0e121b]/95 border border-slate-700/80 rounded-xl p-3 shadow-2xl backdrop-blur-md text-xs font-mono z-20 space-y-1.5 min-w-[220px]">
                <div className="flex items-center justify-between pb-1 border-b border-slate-800">
                  <span className="font-bold text-slate-200">
                    {activeHoverData.weekdayName}, {activeHoverData.dayNumber} {monthLabel}
                  </span>
                  {activeHoverData.isToday && (
                    <span className="text-[9px] px-1.5 py-0.2 rounded bg-cyan-500/20 text-cyan-300 font-bold">
                      HARI INI
                    </span>
                  )}
                </div>

                <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-[11px]">
                  <span className="text-slate-400">Net Hari Ini:</span>
                  <span
                    className={`text-right font-bold tabular-nums ${
                      activeHoverData.dayPnlUsd > 0
                        ? 'text-emerald-400'
                        : activeHoverData.dayPnlUsd < 0
                        ? 'text-rose-400'
                        : 'text-slate-400'
                    }`}
                  >
                    {activeHoverData.dayPnlUsd >= 0 ? '+' : ''}
                    {formatUsd(activeHoverData.dayPnlUsd)}
                  </span>

                  <span className="text-slate-400">Kumulatif:</span>
                  <span
                    className={`text-right font-bold tabular-nums ${
                      activeHoverData.cumPnlUsd >= 0 ? 'text-emerald-400' : 'text-rose-400'
                    }`}
                  >
                    {activeHoverData.cumPnlUsd >= 0 ? '+' : ''}
                    {formatUsd(activeHoverData.cumPnlUsd)}
                  </span>

                  <span className="text-slate-400">Transaksi:</span>
                  <span className="text-right text-slate-300">
                    {activeHoverData.tradesCount} Trade{' '}
                    {activeHoverData.tradesCount > 0 &&
                      `(${activeHoverData.winTrades}W/${activeHoverData.lossTrades}L)`}
                  </span>

                  {activeHoverData.feesIdr > 0 && (
                    <>
                      <span className="text-slate-400">Biaya Gas:</span>
                      <span className="text-right text-amber-300 tabular-nums">
                        {formatIdr(activeHoverData.feesIdr)}
                      </span>
                    </>
                  )}
                </div>

                <div className="text-[9px] text-cyan-400/90 pt-1 border-t border-slate-800/80 text-center flex items-center justify-center gap-1">
                  <span>Klik untuk melihat tabel transaksi</span>
                  <span>↗</span>
                </div>
              </div>
            )}
          </div>

          {/* Minimal 4-Metric Footer Bar (Stripe / TradeZella Style) */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 pt-1 text-xs font-mono">
            <div className="bg-[#141824] border border-slate-800/80 rounded-xl p-2.5">
              <span className="text-[10px] text-slate-400 uppercase tracking-wider block">
                Puncak Profit (Peak)
              </span>
              <span className="text-sm font-bold text-emerald-400 mt-0.5 block tabular-nums">
                +{formatUsd(chartStats.peakPnlUsd)}
              </span>
              <span className="text-[10px] text-slate-400 block truncate">
                ≈ +{formatIdr(chartStats.peakPnlIdr)}
              </span>
            </div>

            <div className="bg-[#141824] border border-slate-800/80 rounded-xl p-2.5">
              <span className="text-[10px] text-slate-400 uppercase tracking-wider block">
                Max Drawdown
              </span>
              <span
                className={`text-sm font-bold mt-0.5 block tabular-nums ${
                  chartStats.maxDrawdownUsd > 0 ? 'text-rose-400' : 'text-slate-400'
                }`}
              >
                -{formatUsd(chartStats.maxDrawdownUsd)}
              </span>
              <span className="text-[10px] text-slate-400 block truncate">
                ≈ -{formatIdr(chartStats.maxDrawdownIdr)}
              </span>
            </div>

            <div className="bg-[#141824] border border-slate-800/80 rounded-xl p-2.5">
              <span className="text-[10px] text-slate-400 uppercase tracking-wider block">
                Rata-Rata / Hari Aktif
              </span>
              <span
                className={`text-sm font-bold mt-0.5 block tabular-nums ${
                  chartStats.avgDailyPnlUsd >= 0 ? 'text-emerald-400' : 'text-rose-400'
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

            <div className="bg-[#141824] border border-slate-800/80 rounded-xl p-2.5">
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
