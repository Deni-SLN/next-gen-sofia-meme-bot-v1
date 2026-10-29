import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { api, useApiQuery, formatIdr, formatUsd } from '@/lib/api';
import { QueryState } from '@/components/QueryState';
import { LucideIcon } from '@/components/LucideIcon';

const DEFAULT_SOL_WALLET = '8muJ3h4PPLmXhAVpJf8dnp9m17WsSaPNm9dSHcTsMVos';

export default function JournalPage() {
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [outcomeFilter, setOutcomeFilter] = useState<string>('');
  const [currentPage, setCurrentPage] = useState<number>(1);
  const PAGE_SIZE = 20;
  const [showAddModal, setShowAddModal] = useState<boolean>(false);
  const [actionMsg, setActionMsg] = useState<string>('');
  const [actionErr, setActionErr] = useState<string>('');
  const [solanaWallet, setSolanaWallet] = useState<string>(DEFAULT_SOL_WALLET);
  const [copiedWalletKey, setCopiedWalletKey] = useState<string | null>(null);

  const [downloading, setDownloading] = useState<boolean>(false);

  // Manual entry modal states
  const [formSymbol, setFormSymbol] = useState<string>('PEPE/USDT');
  const [formChain, setFormChain] = useState<string>('Solana');
  const [formSide, setFormSide] = useState<string>('sell');
  const [formQty, setFormQty] = useState<number>(10000000);
  const [formPrice, setFormPrice] = useState<number>(0.0000125);
  const [formTotal, setFormTotal] = useState<number>(125.0);
  const [formPnl, setFormPnl] = useState<number>(25.0);
  const [formGasFee, setFormGasFee] = useState<number>(0.045);
  const [formDexFee, setFormDexFee] = useState<number>(0.35);
  const [formSlippage, setFormSlippage] = useState<number>(0.85);
  const [formTxHash, setFormTxHash] = useState<string>('');
  const [formNotes, setFormNotes] = useState<string>('Live bot snipe execution');

  // Paginate with max 20 trades per page
  const journalQuery = useApiQuery(
    () => api.getJournal(searchQuery, outcomeFilter, PAGE_SIZE, currentPage),
    [searchQuery, outcomeFilter, currentPage]
  );

  useEffect(() => {
    setCurrentPage(1);
  }, [searchQuery, outcomeFilter]);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const savedSol = localStorage.getItem('sofia_sol_addr');
      const resolvedSol =
        !savedSol || savedSol === 'BYyj6C1tykoREhVFQKbmoNc6axT1tUrdMNZZT6XHoYZ8'
          ? DEFAULT_SOL_WALLET
          : savedSol;
      localStorage.setItem('sofia_sol_addr', resolvedSol);
      setSolanaWallet(resolvedSol);
      api.setPrimarySolanaWallet(resolvedSol).catch(() => {});

      const tradeHandler = () => journalQuery.refetch();
      const walletHandler = (e: any) => {
        if (e?.detail) setSolanaWallet(String(e.detail));
        journalQuery.refetch();
      };
      window.addEventListener('sofia-bot-trade-executed', tradeHandler);
      window.addEventListener('sofia-solana-wallet-updated', walletHandler);
      return () => {
        window.removeEventListener('sofia-bot-trade-executed', tradeHandler);
        window.removeEventListener('sofia-solana-wallet-updated', walletHandler);
      };
    }
  }, []);

  const d = journalQuery.data;
  const usdIdr = d?.usd_idr || 17949;
  const activeSolanaWallet = solanaWallet || d?.wallet_address || DEFAULT_SOL_WALLET;

  const handleCopyWallet = (text: string, key: string) => {
    if (typeof navigator !== 'undefined' && navigator.clipboard) {
      navigator.clipboard.writeText(text);
      setCopiedWalletKey(key);
      setTimeout(() => setCopiedWalletKey(null), 2500);
    }
  };

  const handleDownloadExcel = async () => {
    try {
      setDownloading(true);
      setActionMsg('');
      setActionErr('');
      await api.downloadJournalExcel();
      setActionMsg('📥 Berhasil mengunduh seluruh arsip jurnal trading live (format Excel / CSV).');
    } catch (err: any) {
      setActionErr(err?.message || 'Gagal mengunduh file Excel Jurnal Trading.');
    } finally {
      setDownloading(false);
    }
  };

  const handleRecordTrade = async (e: React.FormEvent) => {
    e.preventDefault();
    setActionMsg('');
    setActionErr('');
    try {
      const res = await api.recordJournalTrade({
        symbol: formSymbol.trim(),
        chain: formChain,
        side: formSide,
        quantity: Number(formQty),
        price: Number(formPrice),
        total: Number(formTotal),
        pnl: Number(formPnl),
        gas_fee_usd: Number(formGasFee),
        dex_fee_usd: Number(formDexFee),
        slippage_pct: Number(formSlippage),
        tx_hash: formTxHash.trim() || `tx_${Date.now()}`,
        notes: formNotes.trim(),
        status: 'closed',
      });
      setActionMsg(`✅ ${res.message || 'Transaksi live berhasil dicatat ke Neonbase!'}`);
      setShowAddModal(false);
      journalQuery.refetch();
    } catch (err: any) {
      setActionErr(err?.message || 'Gagal mencatat transaksi live');
    }
  };

  const handleDeleteTrade = async (tradeId: number, symbol: string) => {
    if (!confirm(`Hapus catatan transaksi ${symbol} dari Neonbase?`)) return;
    setActionMsg('');
    setActionErr('');
    try {
      await api.deleteJournalTrade(tradeId);
      setActionMsg(`🗑️ Catatan transaksi #${tradeId} (${symbol}) berhasil dihapus dari Neonbase.`);
      journalQuery.refetch();
    } catch (err: any) {
      setActionErr(err?.message || 'Gagal menghapus catatan transaksi');
    }
  };

  return (
    <div className="space-y-3 font-mono">
      {/* Header Banner */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-3.5 py-2.5 rounded-xl bg-obsidian-900 border border-obsidian-700/80">
        <div>
          <div className="flex items-center gap-2">
            <LucideIcon name="book-open" className="w-4 h-4 text-emerald-400" />
            <h1 className="text-sm font-extrabold text-slate-100 uppercase tracking-wide">
              📖 Jurnal Trading Live Bot (Neonbase Cloud)
            </h1>
            <span className="text-[10px] px-1.5 py-0.2 rounded bg-rose-500/20 text-rose-300 border border-rose-500/40 font-bold">
              KHUSUS MODE LIVE
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Mencatat setiap token yang dibeli oleh Sniper Bot, volume, harga market, biaya gas &amp; DEX, serta profit/loss bersih • Data tersimpan permanen di Neon PostgreSQL.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-xs">
          {/* Download Excel Button */}
          <button
            type="button"
            onClick={handleDownloadExcel}
            disabled={downloading}
            className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-extrabold text-[11px] shadow-glow-emerald transition flex items-center gap-1.5"
            title="Download seluruh arsip jurnal trading live dalam format Excel/CSV"
          >
            <LucideIcon name="file-spreadsheet" className="w-3.5 h-3.5" />
            <span>{downloading ? 'Mengunduh Excel...' : '📥 Download Excel (Semua Jurnal)'}</span>
          </button>

          <button
            type="button"
            onClick={() => journalQuery.refetch()}
            className="px-3 py-1.5 rounded-lg bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 hover:bg-cyan-500/30 font-bold text-[11px] transition"
          >
            🔄 Refresh
          </button>

          <button
            type="button"
            onClick={() => setShowAddModal(true)}
            className="px-3 py-1.5 rounded-lg bg-obsidian-800 hover:bg-obsidian-700 text-slate-200 border border-obsidian-600 font-bold text-[11px] transition"
          >
            + Catat Manual
          </button>
        </div>
      </div>

      {/* RECORDED SOLANA WALLET BAR (LINKED TO SYSTEM SETTINGS & CREDENTIALS) */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 px-3.5 py-2.5 rounded-xl bg-gradient-to-r from-purple-950/35 via-obsidian-900 to-obsidian-900 border border-purple-500/35 text-xs">
        <div className="flex flex-wrap items-center gap-2">
          <span className="px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-purple-500/40 text-[10px] font-extrabold">
            🟣 WALLET SOLANA TERCATAT
          </span>
          <span className="text-slate-400 text-[11px]">Alamat Dompet:</span>
          <code className="px-2 py-0.5 rounded bg-obsidian-950 border border-obsidian-800 text-emerald-300 font-bold select-all text-[11px]">
            {activeSolanaWallet}
          </code>
          <button
            type="button"
            onClick={() => handleCopyWallet(activeSolanaWallet, 'header-sol')}
            className="px-2 py-0.5 rounded bg-obsidian-950 hover:bg-obsidian-800 text-cyan-300 border border-obsidian-750 text-[10px] font-bold flex items-center gap-1 transition"
            title="Salin Alamat Wallet Solana"
          >
            <LucideIcon name={copiedWalletKey === 'header-sol' ? 'check' : 'copy'} className="w-3 h-3" />
            <span>{copiedWalletKey === 'header-sol' ? '✓ Tersalin' : 'Salin Wallet'}</span>
          </button>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-[11px]">
          <a
            href={`https://solscan.io/account/${activeSolanaWallet}`}
            target="_blank"
            rel="noreferrer"
            className="px-2.5 py-1 rounded-lg bg-obsidian-950 hover:bg-obsidian-850 text-purple-300 border border-purple-500/30 font-bold flex items-center gap-1 transition"
          >
            <span>Solscan Account</span>
            <span>↗</span>
          </a>
          <Link
            href="/settings?tab=wallet"
            className="px-2.5 py-1 rounded-lg bg-cyan-500/15 hover:bg-cyan-500/25 text-cyan-300 border border-cyan-500/30 font-bold flex items-center gap-1 transition"
            title="Ubah alamat wallet Solana di Pengaturan Sistem & Kredensial"
          >
            <LucideIcon name="sliders" className="w-3 h-3" />
            <span>Pengaturan &amp; Kredensial</span>
          </Link>
        </div>
      </div>


      {actionMsg && (
        <div className="p-3 rounded-lg bg-emerald-950/60 border border-emerald-500/40 text-emerald-200 text-xs">
          {actionMsg}
        </div>
      )}
      {actionErr && (
        <div className="p-3 rounded-lg bg-rose-950/60 border border-rose-500/40 text-rose-200 text-xs">
          ⚠️ {actionErr}
        </div>
      )}

      {/* 4 CORE CARDS REQUESTED BY USER */}
      <QueryState isLoading={journalQuery.isLoading} isError={journalQuery.isError} error={journalQuery.error}>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5">
          {/* Card 1: Modal Awal */}
          <div className="p-3.5 rounded-xl bg-obsidian-900 border border-obsidian-700/80 relative overflow-hidden group hover:border-emerald-500/40 transition">
            <div className="flex items-center justify-between text-xs mb-1">
              <span className="text-slate-400 font-medium">MODAL AWAL LIVE</span>
              <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
                BASE MODAL
              </span>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold tracking-tight text-white">
                {formatUsd(d?.initial_capital_usd)}
              </span>
              <span className="text-xs text-slate-400">≈ {formatIdr(d?.initial_capital_idr)}</span>
            </div>
            <div className="mt-2 text-[10px] text-slate-400 flex items-center justify-between border-t border-obsidian-800 pt-1.5">
              <span title={activeSolanaWallet}>
                Solana: <strong className="text-purple-300">{activeSolanaWallet.slice(0, 6)}...{activeSolanaWallet.slice(-4)}</strong>
              </span>
              <span className="text-emerald-400 flex items-center gap-1">
                <LucideIcon name="shield-check" className="w-3 h-3" /> Tercatat
              </span>
            </div>
          </div>

          {/* Card 2: Keuntungan Sepanjang Masa */}
          <div className="p-3.5 rounded-xl bg-obsidian-900 border border-obsidian-700/80 relative overflow-hidden group hover:border-emerald-500/40 transition">
            <div className="flex items-center justify-between text-xs mb-1">
              <span className="text-slate-400 font-medium">KEUNTUNGAN SEPANJANG MASA</span>
              <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                ALL-TIME GAIN
              </span>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold tracking-tight text-emerald-400">
                +{formatUsd(d?.total_profit_usd)}
              </span>
              <span className="text-xs text-emerald-400/80">≈ +{formatIdr(d?.total_profit_idr)}</span>
            </div>
            <div className="mt-2 text-[10px] text-slate-400 flex items-center justify-between border-t border-obsidian-800 pt-1.5">
              <span>{d?.winning_trades ?? 0} Posisi Win (Take-Profit)</span>
              <span className="text-emerald-400 font-bold">🟢 Net Win</span>
            </div>
          </div>

          {/* Card 3: Kerugian Sepanjang Masa */}
          <div className="p-3.5 rounded-xl bg-obsidian-900 border border-obsidian-700/80 relative overflow-hidden group hover:border-rose-500/40 transition">
            <div className="flex items-center justify-between text-xs mb-1">
              <span className="text-slate-400 font-medium">KERUGIAN SEPANJANG MASA</span>
              <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/30">
                ALL-TIME LOSS
              </span>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold tracking-tight text-rose-400">
                -{formatUsd(d?.total_loss_usd)}
              </span>
              <span className="text-xs text-rose-400/80">≈ -{formatIdr(d?.total_loss_idr)}</span>
            </div>
            <div className="mt-2 text-[10px] text-slate-400 flex items-center justify-between border-t border-obsidian-800 pt-1.5">
              <span>{d?.losing_trades ?? 0} Posisi Terkena Stop-Loss</span>
              <span className="text-rose-400 font-bold">🔴 Cut Loss</span>
            </div>
          </div>

          {/* Card 4: Hasil Bersih (Keuntungan dikurang Kerugian) */}
          <div className="p-3.5 rounded-xl bg-obsidian-900 border border-obsidian-700/80 relative overflow-hidden group hover:border-cyan-500/40 transition">
            <div className="flex items-center justify-between text-xs mb-1">
              <span className="text-slate-400 font-medium">HASIL BERSIH (PROFIT - LOSS)</span>
              <span
                className={`text-[9px] font-bold px-1.5 py-0.5 rounded border ${
                  (d?.net_result_usd ?? 0) >= 0
                    ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                    : 'bg-rose-500/20 text-rose-300 border-rose-500/30'
                }`}
              >
                NET HASIL
              </span>
            </div>
            <div className="flex items-baseline gap-2">
              <span
                className={`text-2xl font-bold tracking-tight ${
                  (d?.net_result_usd ?? 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'
                }`}
              >
                {(d?.net_result_usd ?? 0) >= 0 ? '+' : ''}
                {formatUsd(d?.net_result_usd)}
              </span>
              <span
                className={`text-xs ${
                  (d?.net_result_idr ?? 0) >= 0 ? 'text-emerald-400/80' : 'text-rose-400/80'
                }`}
              >
                ≈ {(d?.net_result_idr ?? 0) >= 0 ? '+' : ''}
                {formatIdr(d?.net_result_idr)}
              </span>
            </div>
            <div className="mt-2 text-[10px] text-slate-400 flex items-center justify-between border-t border-obsidian-800 pt-1.5">
              <span>
                Net ROI:{' '}
                <strong
                  className={
                    (d?.net_result_pct ?? 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'
                  }
                >
                  {(d?.net_result_pct ?? 0) >= 0 ? '+' : ''}
                  {d?.net_result_pct}%
                </strong>
              </span>
              <span className="text-slate-300 font-bold">Win Rate: {d?.win_rate}%</span>
            </div>
          </div>
        </div>

        {/* Filter and Search Bar */}
        <div className="flex flex-wrap items-center justify-between gap-2.5 p-3 rounded-xl bg-obsidian-900 border border-obsidian-700/80 text-xs">
          <div className="flex items-center gap-2 w-full sm:w-auto">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Cari Token / Chain (misal PEPE, WIF, Solana)..."
              className="px-3 py-1.5 rounded-lg bg-obsidian-950 border border-obsidian-700 text-slate-100 placeholder-slate-500 text-xs w-full sm:w-64 focus:outline-none focus:border-emerald-500"
            />
          </div>

          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-[11px] text-slate-400 uppercase mr-1">Filter Hasil:</span>
            {[
              { id: '', label: `Semua (${d?.total_trades ?? 0})` },
              { id: 'WIN', label: `🟢 Win (${d?.winning_trades ?? 0})` },
              { id: 'LOSS', label: `🔴 Loss (${d?.losing_trades ?? 0})` },
              { id: 'OPEN', label: `🟡 Terbuka (${d?.open_trades ?? 0})` },
            ].map((btn) => {
              const active = outcomeFilter === btn.id;
              return (
                <button
                  key={btn.id}
                  type="button"
                  onClick={() => setOutcomeFilter(btn.id)}
                  className={`px-2.5 py-1 rounded-md text-[11px] font-bold transition border ${
                    active
                      ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40 shadow-sm'
                      : 'bg-obsidian-950 text-slate-400 hover:text-white border-obsidian-700'
                  }`}
                >
                  {btn.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Compact Notice: Max 20 Transactions per Page */}
        <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-1.5 rounded-lg bg-obsidian-900 border border-emerald-500/20 text-[11px] text-slate-300">
          <div className="flex items-center gap-2">
            <span className="flex h-2 w-2 relative">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
            </span>
            <span>
              Menampilkan maksimal <strong className="text-emerald-400">20 transaksi live per halaman</strong> (Halaman {d?.page || currentPage} dari {d?.total_pages || 1}).
            </span>
          </div>
          <button
            type="button"
            onClick={handleDownloadExcel}
            disabled={downloading}
            className="text-cyan-400 hover:text-cyan-300 font-bold flex items-center gap-1 hover:underline text-[11px] disabled:opacity-50"
          >
            <span>📥 Download Excel (Semua {d?.total_trades ?? 0} Transaksi)</span>
            <span>→</span>
          </button>
        </div>

        {/* Live Bot Trading Journal Table (Paginated Max 20 / Page) */}
        <div className="rounded-xl bg-obsidian-900 border border-obsidian-700/80 overflow-hidden shadow-lg">
          <div className="px-3 py-2 border-b border-obsidian-800 flex flex-wrap items-center justify-between gap-2">
            <div className="font-bold text-xs uppercase tracking-wider text-slate-100 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              <span>Histori Transaksi Live On-Chain (Maks 20 / Halaman)</span>
              <span className="text-[9px] px-1.5 py-0.2 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                PAGINATION 20/PAGE
              </span>
            </div>
            <div className="flex items-center gap-2 text-[10px] text-slate-400">
              <span>
                Halaman <strong className="text-emerald-400">{d?.page || currentPage}</strong> / <strong className="text-white">{d?.total_pages || 1}</strong> • Menampilkan:{' '}
                <strong className="text-white">{d?.trades?.length || 0}</strong> dari{' '}
                <strong className="text-white">{d?.total_matching ?? d?.total_trades ?? 0}</strong> transaksi
              </span>
            </div>
          </div>

          {/* Compact max-height scrolling container */}
          <div className="overflow-x-auto max-h-[440px] overflow-y-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-obsidian-950 text-slate-400 border-b border-obsidian-800 text-[10px] uppercase sticky top-0 z-10 backdrop-blur">
                <tr>
                  <th className="py-2 px-2.5">Waktu &amp; ID</th>
                  <th className="py-2 px-2.5">Koin</th>
                  <th className="py-2 px-2.5">Wallet Solana</th>
                  <th className="py-2 px-2.5">Aksi</th>
                  <th className="py-2 px-2.5">Qty</th>
                  <th className="py-2 px-2.5">Harga</th>
                  <th className="py-2 px-2.5">Total Nilai</th>
                  <th className="py-2 px-2.5">Biaya (Gas/DEX)</th>
                  <th className="py-2 px-2.5">Profit / Loss</th>
                  <th className="py-2 px-2.5">Hasil</th>
                  <th className="py-2 px-2.5">Explorer</th>
                  <th className="py-2 px-2.5 text-right">Aksi</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-obsidian-800/60 font-mono">
                {(d?.trades || []).length === 0 ? (
                  <tr>
                    <td colSpan={12} className="py-6 text-center text-slate-400 text-xs">
                      Belum ada transaksi live bot yang sesuai dengan filter pencarian.
                    </td>
                  </tr>
                ) : (
                  d.trades.map((t: any) => {
                    const isWin = t.result === 'WIN';
                    const isLoss = t.result === 'LOSS';
                    const isSolana = t.chain === 'Solana';
                    const rowWallet = t.wallet_address || activeSolanaWallet;
                    const explorerUrl = isSolana
                      ? `https://solscan.io/tx/${t.tx_hash}`
                      : `https://basescan.org/tx/${t.tx_hash}`;

                    const dateStr = t.closed_at || t.opened_at;
                    const formattedDate = dateStr
                      ? new Date(dateStr).toLocaleString('id-ID', {
                          timeZone: 'Asia/Jakarta',
                          day: '2-digit',
                          month: 'short',
                          hour: '2-digit',
                          minute: '2-digit',
                        }) + ' WIB'
                      : '-';

                    return (
                      <tr key={t.id} className="hover:bg-obsidian-850/60 transition">
                        <td className="py-2 px-2.5">
                          <div className="font-bold text-slate-200 text-xs">#{t.id}</div>
                          <div className="text-[9px] text-slate-500 whitespace-nowrap">{formattedDate}</div>
                        </td>

                        <td className="py-2 px-2.5">
                          <div className="flex items-center gap-1">
                            <span className="font-extrabold text-white text-xs">${t.symbol}</span>
                            <span
                              className={`text-[9px] px-1 py-0.2 rounded font-bold border ${
                                isSolana
                                  ? 'bg-purple-500/10 text-purple-300 border-purple-500/30'
                                  : 'bg-blue-500/10 text-blue-300 border-blue-500/30'
                              }`}
                            >
                              {t.chain}
                            </span>
                          </div>
                          {t.notes && (
                            <div className="text-[9px] text-slate-400 truncate max-w-[160px]" title={t.notes}>
                              {t.notes}
                            </div>
                          )}
                        </td>

                        <td className="py-2 px-2.5">
                          <div className="flex items-center gap-1">
                            <span className="text-[10px] text-purple-300 font-bold" title={rowWallet}>
                              {rowWallet.slice(0, 5)}...{rowWallet.slice(-4)}
                            </span>
                            <button
                              type="button"
                              onClick={() => handleCopyWallet(rowWallet, `row-w-${t.id}`)}
                              className="px-1 py-0.2 rounded bg-obsidian-950 hover:bg-obsidian-800 text-cyan-300 border border-obsidian-750 text-[9px]"
                              title={`Salin Wallet: ${rowWallet}`}
                            >
                              {copiedWalletKey === `row-w-${t.id}` ? '✓' : '📋'}
                            </button>
                          </div>
                        </td>

                        <td className="py-2 px-2.5">
                          <span
                            className={`px-1.5 py-0.5 rounded text-[9px] font-bold border ${
                              t.side === 'buy'
                                ? 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30'
                                : 'bg-orange-500/15 text-orange-300 border-orange-500/30'
                            }`}
                          >
                            {t.side.toUpperCase()}
                          </span>
                        </td>

                        <td className="py-2 px-2.5 text-slate-200 font-bold text-[11px]">
                          {Number(t.quantity).toLocaleString()}
                        </td>

                        <td className="py-2 px-2.5">
                          <div className="text-slate-100 font-bold text-[11px]">{formatUsd(t.price)}</div>
                          <div className="text-[9px] text-slate-400">≈ {formatIdr(t.price_idr)}</div>
                        </td>

                        <td className="py-2 px-2.5">
                          <div className="text-slate-200 font-bold text-[11px]">{formatUsd(t.total_usd)}</div>
                          <div className="text-[9px] text-slate-400">≈ {formatIdr(t.total_idr)}</div>
                        </td>

                        <td className="py-2 px-2.5">
                          <div className="text-rose-300 font-bold text-[11px]">
                            {formatUsd(t.total_fees_usd)}
                          </div>
                          <div className="text-[9px] text-slate-500">
                            ≈ {formatIdr(t.total_fees_idr)}
                          </div>
                        </td>

                        <td className="py-2 px-2.5">
                          <div
                            className={`text-xs font-extrabold ${
                              isWin ? 'text-emerald-400' : isLoss ? 'text-rose-400' : 'text-slate-300'
                            }`}
                          >
                            {t.pnl_usd >= 0 ? '+' : ''}
                            {formatUsd(t.pnl_usd)} ({t.pnl_pct >= 0 ? '+' : ''}
                            {t.pnl_pct}%)
                          </div>
                          <div
                            className={`text-[9px] ${
                              isWin ? 'text-emerald-400/80' : isLoss ? 'text-rose-400/80' : 'text-slate-400'
                            }`}
                          >
                            ≈ {t.pnl_idr >= 0 ? '+' : ''}
                            {formatIdr(t.pnl_idr)}
                          </div>
                        </td>

                        <td className="py-2 px-2.5">
                          <span
                            className={`px-1.5 py-0.5 rounded text-[9px] font-extrabold border ${
                              isWin
                                ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40 shadow-glow-emerald'
                                : isLoss
                                ? 'bg-rose-500/20 text-rose-300 border-rose-500/40'
                                : 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40'
                            }`}
                          >
                            {t.result}
                          </span>
                        </td>

                        <td className="py-2 px-2.5">
                          {t.tx_hash ? (
                            <a
                              href={explorerUrl}
                              target="_blank"
                              rel="noreferrer"
                              className="inline-flex items-center gap-1 text-cyan-400 hover:text-cyan-300 hover:underline text-[10px]"
                              title={`Buka di ${isSolana ? 'Solscan' : 'BaseScan'}`}
                            >
                              <code>{t.tx_hash.slice(0, 5)}...{t.tx_hash.slice(-3)}</code>
                              <span>↗</span>
                            </a>
                          ) : (
                            <span className="text-slate-600">-</span>
                          )}
                        </td>

                        <td className="py-2 px-2.5 text-right">
                          <button
                            type="button"
                            onClick={() => handleDeleteTrade(t.id, t.symbol)}
                            className="p-1 rounded bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/30 transition text-[9px]"
                            title="Hapus entri"
                          >
                            🗑️
                          </button>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination Footer (Max 20 trades per page) */}
          <div className="px-3.5 py-2.5 bg-obsidian-950/80 border-t border-obsidian-800 flex flex-wrap items-center justify-between gap-2 text-xs font-mono">
            <div className="text-[11px] text-slate-400">
              {(() => {
                const totalMatching = Number(d?.total_matching ?? d?.total_trades ?? 0);
                const pageNum = Number(d?.page || currentPage);
                const startRow = totalMatching === 0 ? 0 : (pageNum - 1) * PAGE_SIZE + 1;
                const endRow = Math.min(totalMatching, pageNum * PAGE_SIZE);
                return (
                  <span>
                    Menampilkan <strong className="text-slate-200">{startRow}–{endRow}</strong> dari{' '}
                    <strong className="text-emerald-400">{totalMatching}</strong> transaksi (Maks {PAGE_SIZE} trade/halaman)
                  </span>
                );
              })()}
            </div>
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                disabled={(d?.page || currentPage) <= 1}
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                className="px-2.5 py-1 rounded bg-obsidian-900 hover:bg-obsidian-800 text-slate-200 border border-obsidian-700 disabled:opacity-40 disabled:cursor-not-allowed text-[11px] font-bold transition"
              >
                ← Sebelumnya
              </button>
              <span className="px-2.5 py-1 rounded bg-obsidian-900 border border-emerald-500/30 text-emerald-300 text-[11px] font-extrabold">
                Hal {d?.page || currentPage} / {d?.total_pages || 1}
              </span>
              <button
                type="button"
                disabled={(d?.page || currentPage) >= (d?.total_pages || 1)}
                onClick={() => setCurrentPage((p) => Math.min(d?.total_pages || 1, p + 1))}
                className="px-2.5 py-1 rounded bg-obsidian-900 hover:bg-obsidian-800 text-slate-200 border border-obsidian-700 disabled:opacity-40 disabled:cursor-not-allowed text-[11px] font-bold transition"
              >
                Berikutnya →
              </button>
            </div>
          </div>
        </div>
      </QueryState>

      {/* Manual Entry Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-obsidian-950/80 backdrop-blur-sm">
          <div className="bg-obsidian-900 border border-emerald-500/40 rounded-2xl p-5 w-full max-w-xl space-y-4 shadow-2xl">
            <div className="flex items-center justify-between pb-2 border-b border-obsidian-800">
              <h3 className="font-extrabold text-sm text-slate-100 flex items-center gap-2">
                <LucideIcon name="book-open" className="w-4 h-4 text-emerald-400" />
                Catat Transaksi Live Bot ke Neonbase
              </h3>
              <button
                type="button"
                onClick={() => setShowAddModal(false)}
                className="text-slate-400 hover:text-white font-bold"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleRecordTrade} className="space-y-3 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[10px] text-slate-400 mb-1">SYMBOL TOKEN</label>
                  <input
                    type="text"
                    value={formSymbol}
                    onChange={(e) => setFormSymbol(e.target.value)}
                    placeholder="PEPE/USDT"
                    className="w-full px-2.5 py-1.5 rounded bg-obsidian-950 border border-obsidian-700 text-white"
                    required
                  />
                </div>
                <div>
                  <label className="block text-[10px] text-slate-400 mb-1">CHAIN</label>
                  <select
                    value={formChain}
                    onChange={(e) => setFormChain(e.target.value)}
                    className="w-full px-2.5 py-1.5 rounded bg-obsidian-950 border border-obsidian-700 text-white"
                  >
                    <option value="Solana">Solana</option>
                    <option value="Base">Base</option>
                    <option value="Ethereum">Ethereum</option>
                    <option value="BSC">BSC</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-2.5">
                <div>
                  <label className="block text-[10px] text-slate-400 mb-1">JUMLAH TOKEN</label>
                  <input
                    type="number"
                    step="any"
                    value={formQty}
                    onChange={(e) => setFormQty(Number(e.target.value))}
                    className="w-full px-2.5 py-1.5 rounded bg-obsidian-950 border border-obsidian-700 text-white"
                    required
                  />
                </div>
                <div>
                  <label className="block text-[10px] text-slate-400 mb-1">HARGA (USD)</label>
                  <input
                    type="number"
                    step="any"
                    value={formPrice}
                    onChange={(e) => setFormPrice(Number(e.target.value))}
                    className="w-full px-2.5 py-1.5 rounded bg-obsidian-950 border border-obsidian-700 text-white"
                    required
                  />
                </div>
                <div>
                  <label className="block text-[10px] text-slate-400 mb-1">TOTAL (USD)</label>
                  <input
                    type="number"
                    step="any"
                    value={formTotal}
                    onChange={(e) => setFormTotal(Number(e.target.value))}
                    className="w-full px-2.5 py-1.5 rounded bg-obsidian-950 border border-obsidian-700 text-white"
                    required
                  />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-2.5">
                <div>
                  <label className="block text-[10px] text-slate-400 mb-1">NET PnL (USD)</label>
                  <input
                    type="number"
                    step="any"
                    value={formPnl}
                    onChange={(e) => setFormPnl(Number(e.target.value))}
                    placeholder="+25.0 atau -10.0"
                    className={`w-full px-2.5 py-1.5 rounded bg-obsidian-950 border border-obsidian-700 font-bold ${
                      formPnl >= 0 ? 'text-emerald-400' : 'text-rose-400'
                    }`}
                    required
                  />
                </div>
                <div>
                  <label className="block text-[10px] text-slate-400 mb-1">GAS FEE (USD)</label>
                  <input
                    type="number"
                    step="any"
                    value={formGasFee}
                    onChange={(e) => setFormGasFee(Number(e.target.value))}
                    className="w-full px-2.5 py-1.5 rounded bg-obsidian-950 border border-obsidian-700 text-white"
                  />
                </div>
                <div>
                  <label className="block text-[10px] text-slate-400 mb-1">DEX FEE (USD)</label>
                  <input
                    type="number"
                    step="any"
                    value={formDexFee}
                    onChange={(e) => setFormDexFee(Number(e.target.value))}
                    className="w-full px-2.5 py-1.5 rounded bg-obsidian-950 border border-obsidian-700 text-white"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[10px] text-slate-400 mb-1">TX HASH ON-CHAIN</label>
                <input
                  type="text"
                  value={formTxHash}
                  onChange={(e) => setFormTxHash(e.target.value)}
                  placeholder="5Ux9a7z... (opsional, akan digenerate otomatis)"
                  className="w-full px-2.5 py-1.5 rounded bg-obsidian-950 border border-obsidian-700 text-white font-mono"
                />
              </div>

              <div>
                <label className="block text-[10px] text-slate-400 mb-1">CATATAN BOT / STRATEGI</label>
                <input
                  type="text"
                  value={formNotes}
                  onChange={(e) => setFormNotes(e.target.value)}
                  placeholder="Target TP 2.5x tercapai di Raydium"
                  className="w-full px-2.5 py-1.5 rounded bg-obsidian-950 border border-obsidian-700 text-white"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-obsidian-800">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2 rounded-lg bg-obsidian-800 hover:bg-obsidian-700 text-slate-300 font-bold"
                >
                  Batal
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-obsidian-950 font-extrabold shadow-glow-emerald"
                >
                  Simpan ke Neonbase
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
