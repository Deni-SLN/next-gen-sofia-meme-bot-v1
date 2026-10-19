import React, { useEffect, useRef, useState } from 'react';
import { LucideIcon } from '@/components/LucideIcon';

interface TradingViewWidgetProps {
  symbol: string;
  timeframe?: string; // '1', '5', '15', '60', '240', 'D', 'W', 'M'
  isCrypto?: boolean;
  height?: number;
  autosize?: boolean;
}

export function TradingViewWidget({
  symbol,
  timeframe = 'D',
  isCrypto = false,
  height = 520,
  autosize = true,
}: TradingViewWidgetProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [activeInterval, setActiveInterval] = useState<string>(timeframe);

  // Normalize symbol for TradingView
  const tvSymbol = (() => {
    const s = (symbol || 'BTC').trim().toUpperCase();
    if (s === 'IHSG' || s === '^JKSE' || s === 'COMPOSITE') {
      return 'IDX:COMPOSITE';
    }
    if (isCrypto || ['BTC', 'ETH', 'SOL', 'BONK', 'DOGE', 'PEPE', 'BNB', 'XRP', 'APT', 'TIA', 'JUP', 'SEI', 'TAO', 'FET', 'PENDLE', 'ONDO', 'NEAR', 'RENDER', 'SHIB', 'WIF', 'INJ', 'KAS'].includes(s)) {
      if (s.includes(':')) {
        return s;
      }
      if (s === 'KAS' || s === 'KASPA') {
        return 'BYBIT:KASUSDT';
      }
      if (s.endsWith('USDT') || s.endsWith('USD')) {
        return `BINANCE:${s}`;
      }
      return `BINANCE:${s}USDT`;
    }
    // Indonesian Stock default prefix
    if (!s.includes(':')) {
      return `IDX:${s}`;
    }
    return s;
  })();

  const intervalMap: Record<string, string> = {
    '1m': '1',
    '5m': '5',
    '15m': '15',
    '30m': '30',
    '1h': '60',
    '4h': '240',
    '1d': 'D',
    '1w': 'W',
    '1mo': 'M',
  };

  const selectedTvInterval = intervalMap[activeInterval] || activeInterval || 'D';
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

  useEffect(() => {
    if (!containerRef.current) return;
    containerRef.current.innerHTML = '';

    const widgetContainer = document.createElement('div');
    widgetContainer.className = 'tradingview-widget-container__widget';
    widgetContainer.style.height = '100%';
    widgetContainer.style.width = '100%';
    containerRef.current.appendChild(widgetContainer);

    const script = document.createElement('script');
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js';
    script.type = 'text/javascript';
    script.async = true;
    script.innerHTML = JSON.stringify({
      autosize: autosize,
      height: height,
      symbol: tvSymbol,
      interval: selectedTvInterval,
      timezone: 'Asia/Jakarta',
      theme: isLight ? 'light' : 'dark',
      style: '1', // 1 = Candlesticks
      locale: 'id',
      enable_publishing: false,
      allow_symbol_change: true,
      hide_top_toolbar: false,
      hide_legend: false,
      save_image: true,
      calendar: false,
      hide_volume: false,
      support_host: 'https://www.tradingview.com',
      backgroundColor: isLight ? '#ffffff' : '#0a0d14',
      gridColor: isLight ? '#f1f5f9' : '#161e2e',
      studies: [
        'MASimple@tv-basicstudies',
        'EMA@tv-basicstudies',
        'RSI@tv-basicstudies',
        'MACD@tv-basicstudies',
      ],
    });

    containerRef.current.appendChild(script);

    return () => {
      if (containerRef.current) {
        containerRef.current.innerHTML = '';
      }
    };
  }, [tvSymbol, selectedTvInterval, height, autosize, isLight]);

  return (
    <div
      className={`w-full rounded-2xl p-3 sm:p-4 shadow-xl space-y-3 transition border ${
        isLight ? 'bg-white border-slate-200' : 'bg-[#0a0d14] border-obsidian-800'
      }`}
    >
      {/* Timeframe Quick Switcher Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-2.5 border-b border-obsidian-800/80">
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-obsidian-900 border border-obsidian-700 text-xs font-mono font-bold text-cyan-400">
            <LucideIcon name="bar-chart-2" className="w-4 h-4 text-cyan-400" />
            <span>TradingView Pro Live:</span>
            <span className="text-white">{tvSymbol}</span>
          </div>
          <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 font-mono font-bold">
            Real-Time Feed
          </span>
        </div>

        {/* Quick Timeframe Buttons */}
        <div className="flex items-center gap-1 overflow-x-auto no-scrollbar font-mono text-xs">
          <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider mr-1">
            Timeframe:
          </span>
          {[
            { id: '1m', label: '1m' },
            { id: '5m', label: '5m' },
            { id: '15m', label: '15m' },
            { id: '1h', label: '1J' },
            { id: '4h', label: '4J' },
            { id: '1d', label: '1H' },
            { id: '1w', label: '1M' },
            { id: '1mo', label: '1B' },
          ].map((tf) => {
            const active = activeInterval === tf.id;
            return (
              <button
                key={tf.id}
                type="button"
                onClick={() => setActiveInterval(tf.id)}
                className={`px-2.5 py-1 rounded-lg font-bold border transition ${
                  active
                    ? 'bg-cyan-500/20 text-cyan-300 border-cyan-400 shadow-sm'
                    : 'bg-obsidian-950 text-slate-400 border-obsidian-800 hover:text-white hover:border-obsidian-700'
                }`}
              >
                {tf.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Embedded Advanced TradingView Widget Container */}
      <div
        ref={containerRef}
        style={{ height: `${height}px`, width: '100%' }}
        className="tradingview-widget-container rounded-xl overflow-hidden"
      />
    </div>
  );
}
