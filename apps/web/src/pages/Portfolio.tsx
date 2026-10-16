import React, { useState, useEffect } from 'react';
import { api, useApiQuery, formatIdr, formatUsd, getTradingMode, setTradingMode } from '@/lib/api';
import { QueryState } from '@/components/QueryState';
import { PnLChart } from '@/components/PnLChart';

export default function PortfolioPage() {
  const portfolioQuery = useApiQuery(() => api.getPortfolio(), []);
  const perfQuery = useApiQuery(() => api.getPerformance(), []);
  const walletsQuery = useApiQuery(() => api.getWallets(), []);
  const [mode, setMode] = useState<'PAPER' | 'LIVE'>('PAPER');
  const [actionMsg, setActionMsg] = useState<string>('');
  const [actionErr, setActionErr] = useState<string>('');

  useEffect(() => {
    if (typeof window !== 'undefined') {
      setMode(getTradingMode());
      const modeHandler = (e: any) => {
        setMode(e.detail);
        portfolioQuery.refetch();
        perfQuery.refetch();
        walletsQuery.refetch();
      };
      const resetHandler = (e: any) => {
        if (e?.detail) {
          portfolioQuery.setData(e.detail);
        } else {
          portfolioQuery.refetch();
        }
        perfQuery.refetch();
        walletsQuery.refetch();
        setActionMsg(
          '🔄 Semua portofolio & posisi meme coin pada mode Paper telah dihapus! Saldo kembali utuh ke Rp 150.000.'
        );
      };
      const tradeHandler = () => {
        portfolioQuery.refetch();
        perfQuery.refetch();
        walletsQuery.refetch();
      };
      window.addEventListener('sofia-mode-change', modeHandler);
      window.addEventListener('sofia-paper-reset', resetHandler);
      window.addEventListener('sofia-bot-trade-executed', tradeHandler);
      return () => {
        window.removeEventListener('sofia-mode-change', modeHandler);
        window.removeEventListener('sofia-paper-reset', resetHandler);
        window.removeEventListener('sofia-bot-trade-executed', tradeHandler);
      };
    }
  }, []);

  const usdIdr = portfolioQuery.data?.usd_idr || perfQuery.data?.usd_idr || 17960;
  const isLive = mode === 'LIVE';

  const allWallets: any[] = walletsQuery.data?.wallets || [];
  const liveWallets = allWallets.filter((w) => !w.name?.includes('Modal Paper'));
  const liveTradingWallets = liveWallets.filter((w) => w.gate === 'trading');

  const liveTotalEquityUsd = liveWallets.reduce((acc, w) => acc + (Number(w.balance_usd) || 0), 0);
  const liveTotalEquityIdr = liveWallets.reduce((acc, w) => acc + (Number(w.balance_idr) || 0), 0);

  const liveCashUsd = liveTradingWallets.reduce((acc, w) => acc + (Number(w.balance_usd) || 0), 0);
  const liveCashIdr = liveTradingWallets.reduce((acc, w) => acc + (Number(w.balance_idr) || 0), 0);

  const d = portfolioQuery.data;
  const activeEquityUsd = isLive ? liveTotalEquityUsd : (d?.total_equity_usd ?? 0);
  const activeEquityIdr = isLive ? liveTotalEquityIdr : (d?.total_equity_idr ?? 0);
  const activeCashUsd = isLive ? liveCashUsd : (d?.paper_cash_usd ?? 0);
  const activeCashIdr = isLive ? liveCashIdr : (d?.paper_cash_idr ?? 0);

  const handleSell = async (symbol: string, pct: number) => {
    setActionMsg('');
    setActionErr('');
    try {
      const res = await api.sellHolding(symbol, pct);
      setActionMsg(
        `✅ Berhasil jual ${pct}% (${res.qty_sold} ${res.symbol}) di harga market asli ${formatUsd(
          res.sell_price_usd
        )} (${formatIdr(res.sell_price_idr)}). Hasil: ${formatIdr(res.proceeds_idr)} (${formatUsd(
          res.proceeds_usd
        )}) | Realized PnL: ${res.realized_pnl_idr >= 0 ? '+' : ''}${formatIdr(res.realized_pnl_idr)}`
      );
      portfolioQuery.refetch();
      perfQuery.refetch();
      walletsQuery.refetch();
    } catch (err: any) {
      setActionErr(err?.message || 'Gagal menjual posisi');
    }
  };

  const handleReset = async () => {
    setActionMsg('');
    setActionErr('');
    try {
      const freshOverview = await api.resetPaperAccount();
      portfolioQuery.setData(freshOverview);
      await perfQuery.refetch();
      await walletsQuery.refetch();
      setActionMsg(
        '🔄 Semua portofolio & posisi meme coin pada mode Paper telah dihapus! Saldo kembali utuh ke Rp 150.000.'
      );
    } catch (err: any) {
      setActionErr(err?.message || 'Gagal mereset akun Paper');
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3 px-3.5 py-2.5 rounded-xl bg-obsidian-900 border border-obsidian-700/80">
        <div>
          <h1 className="text-sm font-extrabold text-slate-100 uppercase tracking-wide font-mono">
            {isLive ? '💼 Live On-Chain Portfolio & Multi-Gate Vaults' : '💼 Meme Portfolio & Paper Account (Rp 150.000)'}
          </h1>
          <p className="text-xs text-slate-400">
            {isLive ? (
              <>
                Valuasi aset on-chain Solana, Base &amp; Ethereum • Saldo Total:{' '}
                <strong className="text-cyan-300 font-mono">{formatUsd(liveTotalEquityUsd)} ({formatIdr(liveTotalEquityIdr)})</strong>
              </>
            ) : (
              <>
                Valuasi harga token di-update otomatis dari <strong>DexScreener Live Market</strong> • Kurs Hari Ini: $1 ={' '}
                <span className="text-emerald-400 font-mono font-bold">{formatIdr(usdIdr)}</span>
              </>
            )}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2 font-mono text-xs">
          <button
            type="button"
            onClick={() => {
              const next = mode === 'PAPER' ? 'LIVE' : 'PAPER';
              setMode(next);
              setTradingMode(next);
            }}
            className={`px-3 py-1.5 rounded-lg border font-bold text-[11px] transition ${
              isLive
                ? 'bg-rose-500/20 text-rose-300 border-rose-500/40 hover:bg-rose-500/30'
                : 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40 hover:bg-emerald-500/30'
            }`}
          >
            {isLive ? '🔴 Mode: LIVE' : '🟢 Mode: PAPER'}
          </button>
          <button
            type="button"
            onClick={() => {
              portfolioQuery.refetch();
              perfQuery.refetch();
              walletsQuery.refetch();
            }}
            className="px-3 py-1.5 rounded-lg bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 hover:bg-cyan-500/30 font-bold text-[11px]"
          >
            🔄 Refresh Harga Live
          </button>
          {!isLive ? (
            <button
              type="button"
              onClick={handleReset}
              className="px-3 py-1.5 rounded-lg bg-obsidian-800 border border-obsidian-600 hover:border-emerald-500/50 text-slate-200 font-bold text-[11px]"
            >
              🔄 Reset Paper (Rp 150.000)
            </button>
          ) : (
            <span className="px-3 py-1.5 rounded-lg bg-cyan-500/10 border border-cyan-500/30 text-cyan-300 font-bold text-[11px]">
              ⚡ On-Chain Live
            </span>
          )}
        </div>
      </div>

      {actionMsg && (
        <div className="p-3 rounded-lg bg-emerald-950/60 border border-emerald-500/40 text-emerald-200 text-xs font-mono">
          {actionMsg}
        </div>
      )}
      {actionErr && (
        <div className="p-3 rounded-lg bg-rose-950/60 border border-rose-500/40 text-rose-200 text-xs font-mono">
          ⚠️ {actionErr}
        </div>
      )}

      <QueryState isLoading={portfolioQuery.isLoading} isError={portfolioQuery.isError} error={portfolioQuery.error}>
        {/* 4 Summary Cards with USD + Small IDR */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-2.5">
          <div className="p-3.5 rounded-xl bg-obsidian-900 border border-obsidian-700/80">
            <div className="text-xs font-mono text-slate-400 uppercase">
              {isLive ? 'Total Ekuitas (Live On-Chain)' : 'Total Ekuitas (Kas + Aset)'}
            </div>
            <div className="text-2xl font-extrabold font-mono text-slate-100 mt-1">
              {formatUsd(activeEquityUsd)}
            </div>
            <div className="text-xs font-mono text-emerald-400 mt-0.5">
              ≈ {formatIdr(activeEquityIdr)}{' '}
              <span className="text-slate-500">
                {isLive ? `(${liveWallets.length} Dompet Vault)` : '(Modal: Rp 150.000)'}
              </span>
            </div>
          </div>

          <div className="p-3.5 rounded-xl bg-obsidian-900 border border-obsidian-700/80">
            <div className="text-xs font-mono text-slate-400 uppercase">
              {isLive ? 'Sisa Kas Live (Hot Wallets)' : 'Sisa Kas Simulasi (Paper)'}
            </div>
            <div className="text-2xl font-extrabold font-mono text-cyan-400 mt-1">
              {formatUsd(activeCashUsd)}
            </div>
            <div className="text-xs font-mono text-slate-300 mt-0.5">
              ≈ {formatIdr(activeCashIdr)}
              {isLive && <span className="text-slate-500 ml-1">(Solana &amp; Base)</span>}
            </div>
          </div>

          <div className="p-3.5 rounded-xl bg-obsidian-900 border border-obsidian-700/80">
            <div className="text-xs font-mono text-slate-400 uppercase">
              {isLive ? 'Nilai Aset Meme (Live DEX)' : 'Nilai Aset Aktif (Live Market)'}
            </div>
            <div className="text-2xl font-extrabold font-mono text-slate-100 mt-1">
              {formatUsd(d?.total_value)}
            </div>
            <div className="text-xs font-mono text-slate-300 mt-0.5">
              ≈ {formatIdr(d?.total_value_idr)} <span className="text-slate-500">(Cost: {formatIdr(d?.total_cost_idr)})</span>
            </div>
          </div>

          <div className="p-3.5 rounded-xl bg-obsidian-900 border border-obsidian-700/80">
            <div className="text-xs font-mono text-slate-400 uppercase">
              {isLive ? 'Unrealized PnL (Live Floating)' : 'Unrealized PnL (Floating)'}
            </div>
            <div
              className={`text-2xl font-extrabold font-mono mt-1 ${
                (d?.unrealized_pnl ?? 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'
              }`}
            >
              {(d?.unrealized_pnl ?? 0) >= 0 ? '+' : ''}
              {formatUsd(d?.unrealized_pnl)} ({d?.unrealized_pnl_pct ?? 0}%)
            </div>
            <div
              className={`text-xs font-mono mt-0.5 ${
                (d?.unrealized_pnl_idr ?? 0) >= 0 ? 'text-emerald-300' : 'text-rose-300'
              }`}
            >
              ≈ {(d?.unrealized_pnl_idr ?? 0) >= 0 ? '+' : ''}
              {formatIdr(d?.unrealized_pnl_idr)}
            </div>
          </div>
        </div>

        {/* Redesigned Equity Curve & PnL Chart */}
        <PnLChart
          points={perfQuery.data?.pnl_chart || []}
          usdIdr={usdIdr}
          totalTrades={perfQuery.data?.total_trades ?? 0}
          realizedIdr={perfQuery.data?.total_pnl_idr ?? 0}
          floatingIdr={d?.unrealized_pnl_idr ?? 0}
          liveEquityUsd={activeEquityUsd}
          liveEquityIdr={activeEquityIdr}
        />

        {/* Holdings Table with 1-Click Sell Buttons */}
        <div className="rounded-xl bg-obsidian-900 border border-obsidian-700/80 overflow-hidden">
          <div className="p-3.5 border-b border-obsidian-800 flex items-center justify-between">
            <div className="font-bold text-xs uppercase tracking-wider text-slate-100">
              Posisi Meme Coin Aktif (Harga Real-Time DexScreener)
            </div>
            <span className="text-[11px] font-mono text-slate-400">
              {isLive
                ? 'Klik tombol Jual untuk eksekusi ke DEX & realisasi dana ke Hot Wallets'
                : 'Klik tombol Jual untuk realisasi PnL ke Kas Paper'}
            </span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-obsidian-950 text-slate-400 border-b border-obsidian-800">
                <tr>
                  <th className="p-3">Symbol</th>
                  <th className="p-3">Quantity</th>
                  <th className="p-3">Avg Entry (USD / Rp)</th>
                  <th className="p-3">Live Market Price</th>
                  <th className="p-3">Total Value</th>
                  <th className="p-3">Floating PnL</th>
                  <th className="p-3 text-right">Eksekusi Jual (Live Price)</th>
                </tr>
              </thead>
              <tbody>
                {(d?.holdings || []).length === 0 ? (
                  <tr>
                    <td colSpan={7} className="p-8 text-center text-slate-400">
                      {isLive ? (
                        <>
                          Belum ada token meme koin aktif di Live Hot Wallets. Saldo kas siap eksekusi di DEX:{' '}
                          <strong className="text-cyan-300">
                            {formatUsd(liveCashUsd)} ({formatIdr(liveCashIdr)})
                          </strong>
                          .
                        </>
                      ) : (
                        <>
                          Belum ada posisi meme coin aktif (0 koin). Saldo kas Paper Anda utuh{' '}
                          <strong className="text-emerald-300">Rp 150.000</strong>.
                        </>
                      )}
                    </td>
                  </tr>
                ) : (
                  d.holdings.map((h: any) => (
                    <tr key={h.symbol} className="border-b border-obsidian-800/60 hover:bg-obsidian-850/60">
                      <td className="p-3 font-extrabold text-slate-100">${h.symbol}</td>
                      <td className="p-3 text-slate-200">{h.quantity.toLocaleString()}</td>
                      <td className="p-3">
                        <div className="text-slate-200">{formatUsd(h.avg_entry_price)}</div>
                        <div className="text-[10px] text-slate-500">≈ {formatIdr(h.avg_entry_price * usdIdr)}</div>
                      </td>
                      <td className="p-3">
                        <div className="text-cyan-400 font-bold">{formatUsd(h.current_price)}</div>
                        <div className="text-[10px] text-slate-400">≈ {formatIdr(h.current_price * usdIdr)}</div>
                      </td>
                      <td className="p-3">
                        <div className="font-bold text-slate-100">{formatUsd(h.value)}</div>
                        <div className="text-[10px] text-emerald-400">≈ {formatIdr(h.value * usdIdr)}</div>
                      </td>
                      <td className="p-3">
                        <div className={`font-bold ${h.pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                          {h.pnl >= 0 ? '+' : ''}
                          {formatUsd(h.pnl)} ({h.pnl_pct}%)
                        </div>
                        <div className="text-[10px] text-slate-400">
                          ≈ {h.pnl >= 0 ? '+' : ''}
                          {formatIdr(h.pnl * usdIdr)}
                        </div>
                      </td>
                      <td className="p-3 text-right">
                        <div className="inline-flex gap-1.5">
                          {[25, 50, 100].map((pct) => (
                            <button
                              key={pct}
                              type="button"
                              onClick={() => handleSell(h.symbol, pct)}
                              className={`px-2.5 py-1 rounded font-bold text-[10px] transition ${
                                pct === 100
                                  ? 'bg-rose-600 hover:bg-rose-500 text-white'
                                  : 'bg-obsidian-800 hover:bg-obsidian-700 text-rose-300 border border-rose-500/30'
                              }`}
                            >
                              Jual {pct}%
                            </button>
                          ))}
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </QueryState>
    </div>
  );
}
