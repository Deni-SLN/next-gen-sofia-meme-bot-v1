import React, { useState, useRef, useCallback } from 'react';
import { formatIdr, formatUsd } from '@/lib/api';
import { LucideIcon } from '@/components/LucideIcon';

export interface PnLPoint {
  step: number;
  label: string;
  symbol: string;
  side: string;
  trade_pnl_usd: number;
  trade_pnl_idr: number;
  cumulative_pnl_usd: number;
  cumulative_pnl_idr: number;
  equity_usd: number;
  equity_idr: number;
  timestamp: string;
}

interface PnLChartProps {
  points: PnLPoint[];
  usdIdr: number;
  initialCapitalIdr?: number;
  initialCapitalUsd?: number;
  totalTrades?: number;
  realizedIdr?: number;
  floatingIdr?: number;
  liveEquityUsd?: number;
  liveEquityIdr?: number;
}
interface InspectionState {
  index: number;
  svgX: number;
  svgY: number;
  xPercent: number; // 0..100
  yPercent: number; // 0..100
  point: PnLPoint;
  equityIdr: number;
  equityUsd: number;
  diffIdr: number;
  diffPct: number;
}

export function PnLChart({
  points,
  usdIdr,
  initialCapitalIdr,
  initialCapitalUsd,
  totalTrades = 0,
  realizedIdr = 0,
  floatingIdr = 0,
  liveEquityUsd,
  liveEquityIdr,
}: PnLChartProps) {
  const [viewMode, setViewMode] = useState<'equity' | 'pnl'>('equity');
  const [inspected, setInspected] = useState<InspectionState | null>(null);
  const chartWrapperRef = useRef<HTMLDivElement>(null);

  const rate = usdIdr || 17960;
  const initialIdr = initialCapitalIdr ?? 150000;
  const initialUsd = initialCapitalUsd ?? (initialIdr / rate);
  const basePoint: PnLPoint = {
    step: 0,
    label: 'Modal Awal',
    symbol: 'INIT',
    side: 'init',
    trade_pnl_usd: 0,
    trade_pnl_idr: 0,
    cumulative_pnl_usd: 0,
    cumulative_pnl_idr: 0,
    equity_usd: initialUsd,
    equity_idr: initialIdr,
    timestamp: new Date().toISOString(),
  };

  const safePoints: PnLPoint[] = points && points.length > 0 ? points : [basePoint];
  const lastPt = safePoints[safePoints.length - 1];

  const currentEquityIdr = liveEquityIdr ?? lastPt.equity_idr ?? initialIdr;
  const currentEquityUsd = liveEquityUsd ?? lastPt.equity_usd ?? initialUsd;
  const netDiffIdr = currentEquityIdr - initialIdr;
  const netPct = initialIdr > 0 ? (netDiffIdr / initialIdr) * 100 : 0;

  // Build coordinate geometry for 1000 x 150 SVG canvas
  const buildTrajectory = () => {
    const values = safePoints.map((p) =>
      viewMode === 'equity' ? p.equity_idr : ((p.equity_idr - initialIdr) / initialIdr) * 100
    );
    const baseline = viewMode === 'equity' ? initialIdr : 0;
    const minV = Math.min(...values, baseline);
    const maxV = Math.max(...values, baseline * (viewMode === 'equity' ? 1.15 : 1) + 1);
    const span = Math.max(1, maxV - minV);

    const calculatedPoints = safePoints.map((p, idx) => {
      const x = (idx / Math.max(1, safePoints.length - 1)) * 1000;
      const v =
        viewMode === 'equity' ? p.equity_idr : ((p.equity_idr - initialIdr) / initialIdr) * 100;
      const y = 125 - ((v - minV) / span) * 88;
      return {
        index: idx,
        point: p,
        x,
        y: Math.max(22, Math.min(136, y)),
      };
    });

    if (calculatedPoints.length === 1) {
      calculatedPoints.push({
        index: 1,
        point: calculatedPoints[0].point,
        x: 1000,
        y: calculatedPoints[0].y,
      });
    }

    let d = `M ${calculatedPoints[0].x.toFixed(0)} ${calculatedPoints[0].y.toFixed(0)}`;
    for (let i = 0; i < calculatedPoints.length - 1; i++) {
      const c = calculatedPoints[i];
      const n = calculatedPoints[i + 1];
      const cx1 = c.x + (n.x - c.x) * 0.45;
      const cy1 = c.y;
      const cx2 = c.x + (n.x - c.x) * 0.55;
      const cy2 = n.y;
      d += ` C ${cx1.toFixed(0)} ${cy1.toFixed(0)}, ${cx2.toFixed(0)} ${cy2.toFixed(0)}, ${n.x.toFixed(0)} ${n.y.toFixed(0)}`;
    }
    const endY = calculatedPoints[calculatedPoints.length - 1].y;

    return {
      linePath: d,
      areaPath: `${d} L 1000 150 L 0 150 Z`,
      endY,
      calculatedPoints,
    };
  };

  const { linePath, areaPath, endY, calculatedPoints } = buildTrajectory();

  // Resolve closest data point from mouse / touch click
  const resolvePointFromEvent = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (!chartWrapperRef.current) return;
      const rect = chartWrapperRef.current.getBoundingClientRect();
      const clickX = e.clientX - rect.left;
      const ratio = Math.max(0, Math.min(1, clickX / rect.width));
      const targetSvgX = ratio * 1000;

      let closest = calculatedPoints[0];
      let minDistance = Math.abs(closest.x - targetSvgX);

      for (let i = 1; i < calculatedPoints.length; i++) {
        const dist = Math.abs(calculatedPoints[i].x - targetSvgX);
        if (dist < minDistance) {
          minDistance = dist;
          closest = calculatedPoints[i];
        }
      }

      const eqIdr = closest.point.equity_idr;
      const eqUsd = closest.point.equity_usd || eqIdr / rate;
      const diffIdr = eqIdr - initialIdr;
      const diffPct = initialIdr > 0 ? (diffIdr / initialIdr) * 100 : 0;

      setInspected({
        index: closest.index,
        svgX: closest.x,
        svgY: closest.y,
        xPercent: (closest.x / 1000) * 100,
        yPercent: (closest.y / 150) * 100,
        point: closest.point,
        equityIdr: eqIdr,
        equityUsd: eqUsd,
        diffIdr,
        diffPct,
      });
    },
    [calculatedPoints, rate, initialIdr]
  );

  const isPositive = netDiffIdr >= -1;

  // Smart placement for floating pop-up so it is NEVER clipped or covered (FOMO app style)
  const getPopupPlacementStyles = () => {
    if (!inspected) return {};
    const isNearTop = inspected.yPercent < 55;
    const isNearRight = inspected.xPercent > 70;
    const isNearLeft = inspected.xPercent < 30;

    let transform = '';
    let left = `${inspected.xPercent}%`;
    let top = `${inspected.yPercent}%`;

    if (isNearRight) {
      // Anchor to the left of the point
      transform = isNearTop ? 'translate(-100%, 12px)' : 'translate(-100%, -100%) translateY(-12px)';
    } else if (isNearLeft) {
      // Anchor to the right of the point
      transform = isNearTop ? 'translate(0%, 12px)' : 'translate(0%, -100%) translateY(-12px)';
    } else {
      // Center horizontally
      transform = isNearTop ? 'translate(-50%, 14px)' : 'translate(-50%, -100%) translateY(-14px)';
    }

    return {
      left,
      top,
      transform,
    };
  };

  return (
    <section
      className="bg-obsidian-900 border border-obsidian-700/80 rounded-xl p-3.5 space-y-3 shadow-lg"
      data-purpose="equity-curve-card"
    >
      {/* FOMO-Style Inspection HUD / Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 pb-2 border-b border-obsidian-800">
        <div>
          {inspected ? (
            /* ACTIVE INSPECTION MODE HUD */
            <div className="flex items-center gap-2.5 animate-fadeIn">
              <div className="flex items-center justify-center w-7 h-7 rounded-lg bg-cyan-500/20 border border-cyan-400 text-cyan-300 font-mono text-xs font-bold shadow-glow-cyan">
                #{inspected.point.step}
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-mono uppercase tracking-wider text-cyan-300 font-bold bg-cyan-500/10 px-1.5 py-0.2 rounded border border-cyan-500/30">
                    Posisi Dipilih: {inspected.point.label}
                  </span>
                  <button
                    type="button"
                    onClick={() => setInspected(null)}
                    className="text-[10px] text-slate-400 hover:text-white underline font-mono flex items-center gap-1"
                  >
                    <span>✕ Kembali ke Live</span>
                  </button>
                </div>
                <div className="flex items-center gap-2 mt-0.5 font-mono">
                  <span className="text-base font-extrabold text-emerald-400">
                    {formatIdr(inspected.equityIdr)}
                  </span>
                  <span className="text-xs text-slate-300">
                    ({formatUsd(inspected.equityUsd)})
                  </span>
                  <span
                    className={`text-xs font-bold ${
                      inspected.diffIdr >= 0 ? 'text-emerald-400' : 'text-rose-400'
                    }`}
                  >
                    {inspected.diffIdr >= 0 ? '+' : ''}
                    {formatIdr(inspected.diffIdr)} ({inspected.diffPct >= 0 ? '+' : ''}
                    {inspected.diffPct.toFixed(2)}%)
                  </span>
                </div>
              </div>
            </div>
          ) : (
            /* STANDARD LIVE HUD */
            <div>
              <div className="flex items-center gap-2">
                <LucideIcon name="area-chart" className="w-4 h-4 text-emerald-400" />
                <h2 className="text-xs font-bold text-slate-100 uppercase tracking-wider">
                  Kurva Pertumbuhan Modal (Equity Curve)
                </h2>
                <span className="text-[9px] bg-emerald-500/10 text-emerald-300 px-1.5 py-0.5 rounded border border-emerald-500/20 font-mono">
                  FOMO DYNAMIC HUD
                </span>
              </div>
              <p className="text-[11px] text-slate-400 mt-0.5 font-mono">
                Modal Awal:{' '}
                <strong className="text-slate-200 font-semibold">
                  Rp 150.000 ({formatUsd(initialUsd)})
                </strong>{' '}
                • Kurs Live: <span className="text-cyan-300">$1 = {formatIdr(rate)}</span>
              </p>
            </div>
          )}
        </div>

        {/* View Mode Switcher */}
        <div className="flex items-center gap-1.5 bg-obsidian-850 p-1 rounded-lg border border-obsidian-700 font-mono text-xs self-start sm:self-auto">
          <button
            type="button"
            onClick={() => setViewMode('equity')}
            className={
              viewMode === 'equity'
                ? 'px-2.5 py-1 rounded-md bg-emerald-500 text-obsidian-950 font-bold text-[11px] shadow-sm flex items-center gap-1 transition'
                : 'px-2.5 py-1 rounded-md text-slate-400 hover:text-slate-200 text-[11px] transition flex items-center gap-1'
            }
          >
            <LucideIcon name="trending-up" className="w-3 h-3" /> Saldo Modal (Rp 150rb)
          </button>
          <button
            type="button"
            onClick={() => setViewMode('pnl')}
            className={
              viewMode === 'pnl'
                ? 'px-2.5 py-1 rounded-md bg-emerald-500 text-obsidian-950 font-bold text-[11px] shadow-sm transition'
                : 'px-2.5 py-1 rounded-md text-slate-400 hover:text-slate-200 text-[11px] transition'
            }
          >
            PnL %
          </button>
        </div>
      </div>

      {/* Interactive Chart Container: Notice overflow-visible & relative so popup is NEVER clipped */}
      <div className="relative pt-2 pb-1">
        <div
          ref={chartWrapperRef}
          onClick={resolvePointFromEvent}
          className="relative w-full h-52 bg-obsidian-950/90 rounded-xl border border-obsidian-800 p-3 flex flex-col justify-end cursor-crosshair select-none"
          title="Klik titik atau geser di sepanjang grafik untuk memeriksa saldo uang"
        >
          {/* Subtle Background Target Grid */}
          <div className="absolute inset-0 flex flex-col justify-between p-4 pointer-events-none opacity-15">
            <div className="border-b border-dashed border-slate-500 w-full"></div>
            <div className="border-b border-dashed border-slate-500 w-full"></div>
            <div className="border-b border-dashed border-slate-500 w-full"></div>
            <div className="border-b border-dashed border-slate-500 w-full"></div>
          </div>

          {/* Target Reference Badges (Top-Right) */}
          <div className="absolute right-3 top-3 text-right font-mono text-[10px] space-y-0.5 text-slate-400 pointer-events-none z-10">
            <div>
              Target 2x: <span className="text-slate-300 font-semibold">Rp 300.000</span>
            </div>
            <div>
              Baseline: <span className="text-emerald-400 font-semibold">Rp 150.000</span>
            </div>
          </div>

          {/* SVG Vector Canvas */}
          <div className="relative w-full h-36">
            <svg
              className="w-full h-full overflow-visible"
              preserveAspectRatio="none"
              viewBox="0 0 1000 150"
            >
              <defs>
                <linearGradient id="fomoEquityGrad" x1="0%" x2="0%" y1="0%" y2="100%">
                  <stop offset="0%" stopColor="#10b981" stopOpacity="0.5"></stop>
                  <stop offset="50%" stopColor="#06b6d4" stopOpacity="0.2"></stop>
                  <stop offset="100%" stopColor="#0a0d14" stopOpacity="0.0"></stop>
                </linearGradient>
                <linearGradient id="fomoStrokeGrad" x1="0%" x2="100%" y1="0%" y2="0%">
                  <stop offset="0%" stopColor="#10b981"></stop>
                  <stop offset="60%" stopColor="#34d399"></stop>
                  <stop offset="100%" stopColor="#00ff88"></stop>
                </linearGradient>
              </defs>

              {/* Area Shading */}
              <path d={areaPath} fill="url(#fomoEquityGrad)"></path>

              {/* Baseline Reference Line */}
              <line
                stroke="#334155"
                strokeDasharray="4 4"
                strokeWidth="1.5"
                x1="0"
                x2="1000"
                y1="120"
                y2="120"
              ></line>

              {/* Main Line Trajectory */}
              <path
                d={linePath}
                fill="none"
                stroke="url(#fomoStrokeGrad)"
                strokeLinecap="round"
                strokeWidth="3.2"
              ></path>

              {/* Laser Crosshair Line at Inspected Position */}
              {inspected && (
                <line
                  x1={inspected.svgX}
                  x2={inspected.svgX}
                  y1="5"
                  y2="145"
                  stroke="#00e5ff"
                  strokeDasharray="3 3"
                  strokeWidth="2"
                  opacity="0.9"
                />
              )}

              {/* Interactive Anchor Circles along the curve */}
              {calculatedPoints.map((cp) => {
                const isSelected = inspected?.index === cp.index;
                return (
                  <g key={`anchor-${cp.index}`}>
                    {/* Outer glow ring when selected */}
                    {isSelected && (
                      <circle
                        cx={cp.x}
                        cy={cp.y}
                        r="10"
                        fill="none"
                        stroke="#00e5ff"
                        strokeWidth="2"
                        className="animate-ping opacity-75"
                      />
                    )}
                    {/* Visual dot */}
                    <circle
                      cx={cp.x}
                      cy={cp.y}
                      r={isSelected ? '6.5' : '4'}
                      fill={isSelected ? '#00e5ff' : '#00ff88'}
                      stroke="#06080d"
                      strokeWidth="2"
                      className="cursor-pointer transition hover:scale-125"
                    />
                    {/* Large Invisible Hitbox (32px radius) for effortless click on any screen */}
                    <circle
                      cx={cp.x}
                      cy={cp.y}
                      r="20"
                      fill="transparent"
                      className="cursor-pointer"
                    />
                  </g>
                );
              })}

              {/* Live Head Pulse Dot */}
              <circle className="animate-pulse" cx="1000" cy={endY} fill="#00ff88" r="5.5"></circle>
            </svg>

            {/* FOMO NON-CLIPPING FLOATING CALLOUT POPUP */}
            {inspected && (
              <div
                className="absolute z-40 bg-obsidian-900/95 backdrop-blur-md border border-cyan-400 rounded-xl p-3 shadow-glow-cyan text-xs font-mono min-w-[220px] pointer-events-auto transition-all duration-150"
                style={getPopupPlacementStyles()}
                onClick={(e) => e.stopPropagation()}
              >
                {/* Header */}
                <div className="flex items-center justify-between gap-2 border-b border-obsidian-750 pb-1.5 mb-1.5">
                  <div className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping"></span>
                    <span className="text-[10px] text-cyan-300 font-bold uppercase">
                      {inspected.point.label}
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={() => setInspected(null)}
                    className="text-[10px] text-slate-400 hover:text-white px-1.5 py-0.5 rounded hover:bg-obsidian-800 transition"
                    title="Tutup Pop-up"
                  >
                    ✕
                  </button>
                </div>

                {/* Saldo / Money Position Display */}
                <div className="space-y-0.5">
                  <div className="text-slate-400 text-[10px] uppercase font-sans font-bold">
                    Saldo Posisi:
                  </div>
                  <div className="text-base font-extrabold text-emerald-400 tracking-tight">
                    {formatIdr(inspected.equityIdr)}
                  </div>
                  <div className="text-[10px] text-slate-300 font-mono">
                    ≈ {formatUsd(inspected.equityUsd)}
                  </div>
                </div>

                {/* Delta / PnL from Rp 150.000 */}
                <div className="mt-1.5 pt-1.5 border-t border-obsidian-800 flex items-center justify-between gap-2 text-[10px]">
                  <span className="text-slate-400 font-sans">Δ dari Rp 150rb:</span>
                  <span
                    className={`font-bold ${
                      inspected.diffIdr >= 0 ? 'text-emerald-400' : 'text-rose-400'
                    }`}
                  >
                    {inspected.diffIdr >= 0 ? '+' : ''}
                    {formatIdr(inspected.diffIdr)} ({inspected.diffPct >= 0 ? '+' : ''}
                    {inspected.diffPct.toFixed(2)}%)
                  </span>
                </div>

                {/* Trade event info */}
                {inspected.point.symbol && inspected.point.symbol !== 'INIT' && (
                  <div className="mt-1 pt-1 border-t border-obsidian-800/60 flex items-center justify-between text-[9px] text-slate-400">
                    <span className="text-slate-200 font-bold">{inspected.point.symbol}</span>
                    <span
                      className={`font-bold uppercase px-1.5 py-0.2 rounded text-[9px] ${
                        inspected.point.side === 'buy'
                          ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40'
                          : inspected.point.side === 'sell'
                          ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                          : 'bg-obsidian-800 text-slate-300'
                      }`}
                    >
                      {inspected.point.side}
                    </span>
                  </div>
                )}
              </div>
            )}

            {/* Static Live Badge — moved to the LEFT SIDE so it never collides with Baseline/Target on the right */}
            {!inspected && (
              <div className="absolute left-3 top-3 flex items-center gap-2 bg-obsidian-900/95 backdrop-blur-md border border-emerald-500/60 px-2.5 py-1 rounded-lg shadow-glow-emerald pointer-events-none z-10">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                </span>
                <span className="text-xs font-mono font-bold text-emerald-300">
                  {viewMode === 'equity'
                    ? `Live: ${formatIdr(currentEquityIdr)} (${formatUsd(currentEquityUsd)})`
                    : `Kumulatif: ${netPct >= 0 ? '+' : ''}${netPct.toFixed(2)}% (${formatIdr(netDiffIdr)})`}
                </span>
                {netDiffIdr !== 0 && (
                  <span
                    className={`text-[10px] font-mono font-semibold ${
                      netDiffIdr >= 0 ? 'text-emerald-400' : 'text-rose-400'
                    }`}
                  >
                    ({netDiffIdr >= 0 ? '+' : ''}
                    {formatIdr(netDiffIdr)})
                  </span>
                )}
              </div>
            )}
          </div>

          {/* Time axis labels */}
          <div className="flex justify-between items-center text-[10px] text-slate-400 font-mono pt-1.5 border-t border-obsidian-850 pointer-events-none">
            <span>Modal Awal (Rp 150rb)</span>
            <span className="text-cyan-400/90 italic font-medium">
              💡 {inspected ? 'Geser kursor atau klik titik lain' : 'Klik titik atau garis grafik untuk melihat saldo'}
            </span>
            <span className="text-emerald-400 font-bold">Sekarang (Real-Time)</span>
          </div>
        </div>
      </div>

      {/* Metric Footers Under Chart */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-[11px] font-mono pt-1 text-slate-400">
        <div className="bg-obsidian-950/60 px-2.5 py-1.5 rounded border border-obsidian-800">
          <span className="text-slate-400 text-[10px]">Titik Modal Awal:</span>
          <div className="text-slate-200 font-medium">Rp 150.000 ({formatUsd(initialUsd)})</div>
        </div>
        <div className="bg-obsidian-950/60 px-2.5 py-1.5 rounded border border-obsidian-800">
          <span className="text-slate-400 text-[10px]">Live Real-Time:</span>
          <div className="text-emerald-400 font-semibold">
            {formatIdr(currentEquityIdr)} ({formatUsd(currentEquityUsd)})
          </div>
        </div>
        <div className="bg-obsidian-950/60 px-2.5 py-1.5 rounded border border-obsidian-800">
          <span className="text-slate-400 text-[10px]">Floating PnL:</span>
          <div className={isPositive ? 'text-cyan-400 font-medium' : 'text-rose-400 font-medium'}>
            {floatingIdr >= 0 ? '+' : ''}
            {formatIdr(floatingIdr)} ({netPct >= 0 ? '+' : ''}
            {netPct.toFixed(2)}%)
          </div>
        </div>
        <div className="bg-obsidian-950/60 px-2.5 py-1.5 rounded border border-obsidian-800">
          <span className="text-slate-400 text-[10px]">Total Closed Trades:</span>
          <div className="text-slate-200 font-medium">
            {totalTrades} Transaksi • Realized: {formatIdr(realizedIdr)}
          </div>
        </div>
      </div>
    </section>
  );
}
