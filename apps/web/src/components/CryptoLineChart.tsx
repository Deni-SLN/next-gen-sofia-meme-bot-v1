import React, { useRef, useEffect, useState, useCallback } from 'react';

export interface CryptoLineChartPoint {
  price: number;
  time: string | number;
  label?: string;
  dateStr?: string;
  extra?: Record<string, any>;
}

interface CryptoLineChartProps {
  data: CryptoLineChartPoint[];
  height?: number;
  currency?: string; // 'USD' | 'IDR'
  currentPrice?: number;
  onPointClick?: (point: CryptoLineChartPoint, index: number) => void;
  className?: string;
}

const GREEN = '#80efad';
const RED = '#ff646e';
const GREEN_BG = '#45ae68';
const RED_BG = '#e11d48';

const CONFIG = {
  paddingLeft: 20,
  paddingRight: 88,
  paddingTop: 24,
  paddingBottom: 42,
};

export function CryptoLineChart({
  data = [],
  height = 360,
  currency = 'USD',
  currentPrice,
  onPointClick,
  className = '',
}: CryptoLineChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [pointer, setPointer] = useState<{ x: number; y: number } | null>(null);
  const [activePoint, setActivePoint] = useState<{ point: CryptoLineChartPoint; x: number; y: number } | null>(null);

  const isUsd = currency.toUpperCase() === 'USD' || currency.toUpperCase().includes('USDT');

  const formatPrice = useCallback(
    (val: number | undefined | null) => {
      if (val === undefined || val === null || isNaN(val)) return '-';
      if (isUsd) {
        if (Math.abs(val) >= 1000) return '$' + val.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        if (Math.abs(val) >= 1) return '$' + val.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 4 });
        return '$' + val.toLocaleString('en-US', { minimumFractionDigits: 4, maximumFractionDigits: 6 });
      }
      return 'Rp ' + Math.round(val).toLocaleString('id-ID');
    },
    [isUsd]
  );

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas || !data || data.length === 0) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const width = canvas.clientWidth;
    const h = canvas.clientHeight;
    if (!width || !h) return;

    const dpr = typeof window !== 'undefined' ? window.devicePixelRatio || 1 : 1;
    canvas.width = width * dpr;
    canvas.height = h * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    ctx.clearRect(0, 0, width, h);

    const left = CONFIG.paddingLeft;
    const right = width - CONFIG.paddingRight;
    const top = CONFIG.paddingTop;
    const bottom = h - CONFIG.paddingBottom;

    if (right <= left || bottom <= top) return;

    const prices = data.map((d) => d.price);
    const minVal = Math.min(...prices);
    const maxVal = Math.max(...prices);
    const span = Math.max(0.0001, maxVal - minVal);
    const min = minVal - span * 0.12;
    const max = maxVal + span * 0.12;

    const X = (i: number) => left + (i / Math.max(1, data.length - 1)) * (right - left);
    const Y = (p: number) => bottom - ((p - min) / Math.max(0.0001, max - min)) * (bottom - top);

    // 1. Background Dotted Grid (Matrix of #20262d dots, step 13px, radius 0.8)
    ctx.fillStyle = '#20262d';
    for (let x = left; x < right; x += 13) {
      for (let y = top; y < bottom; y += 13) {
        ctx.beginPath();
        ctx.arc(x, y, 0.8, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    // 2. Horizontal Price Level Gridlines
    ctx.font = '12px Arial, sans-serif';
    ctx.textAlign = 'left';
    ctx.fillStyle = '#777f88';

    for (let i = 0; i <= 4; i++) {
      const priceLvl = max - ((max - min) * i) / 4;
      const y = Y(priceLvl);

      ctx.strokeStyle = '#22282e';
      ctx.lineWidth = 0.7;
      ctx.beginPath();
      ctx.moveTo(left, y);
      ctx.lineTo(right, y);
      ctx.stroke();

      ctx.fillText(formatPrice(priceLvl), right + 10, y + 4);
    }

    // 3. Create Area Gradient
    const gradient = ctx.createLinearGradient(0, top, 0, bottom);
    const lastPrice = currentPrice !== undefined ? currentPrice : data[data.length - 1].price;
    const firstPrice = data[0].price;
    const isOverallBull = lastPrice >= firstPrice;

    if (isOverallBull) {
      gradient.addColorStop(0, 'rgba(67, 230, 160, 0.22)');
      gradient.addColorStop(1, 'rgba(67, 230, 160, 0)');
    } else {
      gradient.addColorStop(0, 'rgba(255, 100, 110, 0.22)');
      gradient.addColorStop(1, 'rgba(255, 100, 110, 0)');
    }

    ctx.beginPath();
    data.forEach((d, i) => {
      const x = X(i);
      const y = Y(d.price);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });

    ctx.lineTo(right, bottom);
    ctx.lineTo(left, bottom);
    ctx.closePath();
    ctx.fillStyle = gradient;
    ctx.fill();

    // 4. Draw Price Line with Two-Tone Green/Red Glowing Segments
    for (let i = 1; i < data.length; i++) {
      const prev = data[i - 1].price;
      const curr = data[i].price;

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

    // 5. Current Price Dashed Horizontal Line
    const activeLastPrice = currentPrice !== undefined ? currentPrice : data[data.length - 1].price;
    const lastY = Y(activeLastPrice);
    const activeColor = isOverallBull ? GREEN : RED;
    const activeBadgeBg = isOverallBull ? GREEN_BG : RED_BG;

    ctx.beginPath();
    ctx.setLineDash([5, 5]);
    ctx.moveTo(left, lastY);
    ctx.lineTo(right, lastY);
    ctx.strokeStyle = activeColor;
    ctx.lineWidth = 1;
    ctx.stroke();
    ctx.setLineDash([]);

    // 6. Current Price Marker Circle on Right Edge
    ctx.beginPath();
    ctx.arc(right, lastY, 4, 0, Math.PI * 2);
    ctx.fillStyle = activeColor;
    ctx.fill();

    // 7. Current Price Rounded Badge Pill
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
    ctx.fillText(formatPrice(activeLastPrice), badgeX + badgeW / 2, lastY + 4);

    // 8. Time Axis Labels (Bottom)
    ctx.fillStyle = '#777f88';
    ctx.font = '12px Arial, sans-serif';
    ctx.textAlign = 'center';

    const numLabels = Math.min(5, data.length);
    for (let k = 0; k < numLabels; k++) {
      const idx = Math.round((k / (numLabels - 1)) * (data.length - 1));
      const pt = data[idx];
      if (pt) {
        const x = X(idx);
        const labelText = pt.label || (typeof pt.time === 'string' ? pt.time : String(pt.time));
        ctx.fillText(labelText, x, h - 12);
      }
    }

    // 9. Interactive Crosshair & Tooltip
    if (pointer && pointer.x >= left && pointer.x <= right) {
      const idx = Math.round(((pointer.x - left) / (right - left)) * (data.length - 1));
      const pt = data[idx];
      if (pt) {
        const px = X(idx);
        const py = Y(pt.price);

        // Dashed Crosshair Lines
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

        // Highlight Point Dot
        ctx.beginPath();
        ctx.arc(px, py, 5, 0, Math.PI * 2);
        ctx.fillStyle = pt.price >= (data[idx - 1]?.price ?? pt.price) ? GREEN : RED;
        ctx.fill();
        ctx.strokeStyle = '#080a0c';
        ctx.lineWidth = 1.5;
        ctx.stroke();
      }
    }
  }, [data, currentPrice, pointer, formatPrice]);

  useEffect(() => {
    draw();
  }, [draw]);

  useEffect(() => {
    const handleResize = () => {
      draw();
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [draw]);

  const handlePointerMove = (e: React.PointerEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas || data.length === 0) return;
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    setPointer({ x, y });

    const left = CONFIG.paddingLeft;
    const right = rect.width - CONFIG.paddingRight;
    if (x >= left && x <= right) {
      const idx = Math.round(((x - left) / (right - left)) * (data.length - 1));
      const pt = data[idx];
      if (pt) {
        setActivePoint({ point: pt, x, y });
      }
    } else {
      setActivePoint(null);
    }
  };

  const handlePointerLeave = () => {
    setPointer(null);
    setActivePoint(null);
  };

  const handleClick = () => {
    if (activePoint && onPointClick) {
      const idx = data.findIndex((d) => d === activePoint.point);
      onPointClick(activePoint.point, idx >= 0 ? idx : 0);
    }
  };

  return (
    <div
      ref={containerRef}
      style={{ height }}
      className={`w-full relative bg-[#080a0c] rounded-xl overflow-hidden select-none border border-slate-800/80 ${className}`}
    >
      <canvas
        ref={canvasRef}
        onPointerMove={handlePointerMove}
        onPointerLeave={handlePointerLeave}
        onClick={handleClick}
        className="w-full h-full block cursor-crosshair touch-pan-y"
      />

      {/* Floating Tooltip matching user CSS */}
      {activePoint && (
        <div
          style={{
            left: Math.min(activePoint.x + 12, (containerRef.current?.clientWidth || 300) - 160),
            top: Math.max(10, activePoint.y - 48),
          }}
          className="pointer-events-none absolute bg-[#171d23] border border-[#303a43] rounded-md px-3 py-2 text-xs text-slate-100 shadow-xl z-20 font-mono transition-all duration-75"
        >
          {activePoint.point.dateStr && (
            <div className="text-[10px] text-slate-400 mb-0.5">{activePoint.point.dateStr}</div>
          )}
          <div>
            Price: <strong className="text-white font-bold">{formatPrice(activePoint.point.price)}</strong>
          </div>
          {activePoint.point.extra?.dayPnl !== undefined && (
            <div className={`text-[11px] font-semibold mt-0.5 ${activePoint.point.extra.dayPnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
              Net: {activePoint.point.extra.dayPnl >= 0 ? '+' : ''}
              {formatPrice(activePoint.point.extra.dayPnl)}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
