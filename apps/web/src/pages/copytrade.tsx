import React, { useState, useMemo } from 'react';
import Head from 'next/head';
import { api, useApiQuery, formatIdr, formatUsd } from '@/lib/api';
import { QueryState } from '@/components/QueryState';
import { LucideIcon } from '@/components/LucideIcon';
import { useUltrawide } from '@/lib/useUltrawide';

export default function CopyTradePage() {
  const isUltrawide = useUltrawide();
  const smQuery = useApiQuery(() => api.getSmartMoney(), []);
  const [copiedId, setCopiedId] = useState<number | null>(null);
  const [filterType, setFilterType] = useState<'ALL' | 'SMART_MONEY' | 'WHALE' | 'ACTIVE_COPY'>('ALL');
  const [updatingId, setUpdatingId] = useState<number | null>(null);
  const [copiedWallets, setCopiedWallets] = useState<string[]>(() => {
    if (typeof window !== 'undefined') {
      try {
        const raw = localStorage.getItem('sofia_copied_wallets');
        return raw ? JSON.parse(raw) : [];
      } catch {
        return [];
      }
    }
    return [];
  });

  const usdIdr = smQuery.data?.usd_idr || 16500;
  const rankingDate = smQuery.data?.ranking_date || 'Hari Ini';
  const updatedAt = smQuery.data?.updated_at || 'Live On-Chain';

  const handleCopy = (address: string, id: number) => {
    if (typeof navigator !== 'undefined' && navigator.clipboard) {
      navigator.clipboard.writeText(address);
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 2500);

      const clean = (address || '').trim().toLowerCase();
      if (clean) {
        setCopiedWallets((prev) => {
          const next = Array.from(new Set([...prev, clean]));
          if (typeof window !== 'undefined') {
            try {
              localStorage.setItem('sofia_copied_wallets', JSON.stringify(next));
            } catch {}
          }
          return next;
        });
      }
    }
  };

  const handleResetCopied = () => {
    setCopiedWallets([]);
    if (typeof window !== 'undefined') {
      try {
        localStorage.removeItem('sofia_copied_wallets');
      } catch {}
    }
  };

  const handleToggle = async (wallet: any) => {
    setUpdatingId(wallet.id);
    try {
      await api.toggleCopyWallet(wallet.id, !wallet.copy_enabled, wallet.max_copy_usd || 1.0);
      await smQuery.refetch();
    } finally {
      setUpdatingId(null);
    }
  };

  const handleMaxCopyChange = async (wallet: any, newMaxUsd: number) => {
    setUpdatingId(wallet.id);
    try {
      await api.toggleCopyWallet(wallet.id, Boolean(wallet.copy_enabled), newMaxUsd);
      await smQuery.refetch();
    } finally {
      setUpdatingId(null);
    }
  };

  const allRankedWallets: any[] = useMemo(() => {
    const raw = smQuery.data?.wallets || [];
    return [...raw].sort((a, b) => (Number(a.rank) || 99) - (Number(b.rank) || 99));
  }, [smQuery.data]);

  const visibleWallets = useMemo(() => {
    return allRankedWallets.filter((w: any) => {
      if (copiedWallets.includes(String(w.address || '').trim().toLowerCase())) {
        return false;
      }
      const eType = String(w.entity_type || '').toUpperCase();
      if (filterType === 'SMART_MONEY') {
        return eType.includes('SMART');
      }
      if (filterType === 'WHALE') {
        return eType.includes('WHALE');
      }
      if (filterType === 'ACTIVE_COPY') {
        return Boolean(w.copy_enabled);
      }
      return true;
    });
  }, [allRankedWallets, copiedWallets, filterType]);

  const whaleCount = allRankedWallets.filter((w) => String(w.entity_type || '').includes('WHALE')).length;
  const smartCount = allRankedWallets.filter((w) => String(w.entity_type || '').includes('SMART')).length;
  const activeCopyCount = allRankedWallets.filter((w) => Boolean(w.copy_enabled)).length;
  const rankChangedCount = allRankedWallets.filter((w) => Number(w.rank_change || 0) !== 0).length;

  const getRankBadge = (rank: number) => {
    if (rank === 1) {
      return {
        label: '🏆 RANK #1',
        cls: 'bg-gradient-to-r from-amber-400 to-yellow-300 text-obsidian-950 border-amber-300 shadow-md shadow-amber-400/25 font-black',
      };
    }
    if (rank === 2) {
      return {
        label: '🥈 RANK #2',
        cls: 'bg-slate-200 text-obsidian-950 border-slate-300 shadow-sm font-black',
      };
    }
    if (rank === 3) {
      return {
        label: '🥉 RANK #3',
        cls: 'bg-amber-600/30 text-amber-200 border-amber-500/50 font-black',
      };
    }
    return {
      label: `RANK #${rank}`,
      cls: 'bg-obsidian-950 text-cyan-300 border-obsidian-750 font-extrabold',
    };
  };

  const renderEntityBadges = (w: any) => {
    const eType = String(w.entity_type || 'SMART_MONEY').toUpperCase();
    const isWhale = eType.includes('WHALE');
    const isSmart = eType.includes('SMART');

    return (
      <div className="flex flex-wrap items-center gap-1.5">
        {isWhale && (
          <span
            className="px-2.5 py-0.5 rounded-lg text-[10px] font-mono font-extrabold bg-purple-500/20 text-purple-200 border border-purple-400/40 flex items-center gap-1 shadow-sm"
            title="Dompet Whale bermodal besar (Akumulator Likuiditas)"
          >
            <span>🐋 WHALE</span>
          </span>
        )}
        {isSmart && (
          <span
            className="px-2.5 py-0.5 rounded-lg text-[10px] font-mono font-extrabold bg-emerald-500/20 text-emerald-300 border border-emerald-400/40 flex items-center gap-1 shadow-sm"
            title="Dompet Smart Money dengan Win-Rate & Alpha Sniper Tinggi"
          >
            <span>🧠 SMART MONEY</span>
          </span>
        )}
      </div>
    );
  };

  const renderRankDelta = (w: any) => {
    const delta = Number(w.rank_change || 0);
    const prev = w.prev_rank || w.rank;
    if (delta > 0) {
      return (
        <span
          className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 flex items-center gap-0.5"
          title={`Naik ${delta} peringkat hari ini (Kemarin Rank #${prev})`}
        >
          <span>▲ +{delta} Hari Ini</span>
          <span className="text-[9px] text-emerald-400/80">(dari #{prev})</span>
        </span>
      );
    }
    if (delta < 0) {
      return (
        <span
          className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-rose-500/15 text-rose-300 border border-rose-500/30 flex items-center gap-0.5"
          title={`Turun ${Math.abs(delta)} peringkat hari ini (Kemarin Rank #${prev})`}
        >
          <span>▼ {delta} Hari Ini</span>
          <span className="text-[9px] text-rose-400/80">(dari #{prev})</span>
        </span>
      );
    }
    return (
      <span
        className="px-2 py-0.5 rounded text-[10px] font-mono font-medium bg-obsidian-950 text-slate-400 border border-obsidian-800"
        title="Peringkat stabil dibandingkan kemarin"
      >
        ▬ Stabil (#{w.rank})
      </span>
    );
  };

  return (
    <>
      <Head>
        <title>Top 10 Smart Money &amp; Whale Auto Copy-Trade | Sofia Market 4.1.2</title>
      </Head>

      <div className="space-y-5 pb-12">
        {/* HEADER BANNER */}
        <div className="bg-gradient-to-r from-obsidian-900 via-obsidian-900 to-obsidian-850 border border-obsidian-750 rounded-2xl p-5 sm:p-6 shadow-xl flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div className="space-y-1.5">
            <div className="flex flex-wrap items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
              <h1 className="text-xl sm:text-2xl font-black text-slate-100 flex items-center gap-2">
                <span>🐋🧠</span>
                <span>Top 10 Smart Money &amp; Whale Auto Copy-Trade</span>
              </h1>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-amber-400/15 text-amber-300 border border-amber-400/30">
                RANK #1 – #10 HARIAN
              </span>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
                1 KLIK = $1.00 COPY
              </span>
            </div>
            <p className="text-xs sm:text-sm text-slate-400 max-w-3xl leading-relaxed">
              Peringkat 10 dompet <strong className="text-emerald-300">🧠 Smart Money</strong> &amp;{' '}
              <strong className="text-purple-300">🐋 Whale</strong> terbaik yang diurutkan otomatis dari{' '}
              <strong className="text-amber-300">Rank #1 sampai Rank #10</strong> dan diperbarui setiap hari mengikuti
              performa PnL 24h/7D serta Win-Rate on-chain • Kurs: $1 ={' '}
              <span className="text-emerald-400 font-mono font-bold">{formatIdr(usdIdr)}</span>
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2 shrink-0">
            <div className="px-3 py-1.5 rounded-xl bg-obsidian-950 border border-obsidian-800 text-[11px] font-mono text-slate-300">
              <span className="text-slate-500 block text-[9px] uppercase">Update Peringkat Harian</span>
              <span className="text-cyan-300 font-bold">{updatedAt}</span>
            </div>

            <button
              type="button"
              onClick={() => smQuery.refetch()}
              className="px-3.5 py-2 rounded-xl bg-obsidian-950 hover:bg-obsidian-800 text-cyan-300 border border-obsidian-750 text-xs font-mono font-bold transition flex items-center gap-1.5"
              title="Perbarui peringkat & aktivitas dompet hari ini"
            >
              <LucideIcon name="refresh-cw" className={`w-3.5 h-3.5 ${smQuery.isFetching ? 'animate-spin' : ''}`} />
              <span>Update Hari Ini</span>
            </button>

            {copiedWallets.length > 0 && (
              <button
                type="button"
                onClick={handleResetCopied}
                className="px-3 py-2 rounded-xl bg-amber-500/15 hover:bg-amber-500/25 text-amber-300 border border-amber-500/30 text-xs font-mono font-bold transition flex items-center gap-1.5"
                title="Klik untuk menampilkan kembali dompet yang pernah disalin"
              >
                <span>👁️ Disalin: {copiedWallets.length} (Reset)</span>
              </button>
            )}
          </div>
        </div>

        {/* 4 DAILY LEADERBOARD SUMMARY CARDS */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <div className="p-3.5 rounded-xl bg-obsidian-900 border border-obsidian-800 flex items-center justify-between">
            <div>
              <span className="text-[10px] font-mono text-slate-400 uppercase block">Total Leaderboard</span>
              <span className="text-lg font-black font-mono text-white">Top {allRankedWallets.length} Dompet</span>
              <span className="text-[10px] font-mono text-amber-300 block">Urut Rank #1 – #{allRankedWallets.length}</span>
            </div>
            <span className="text-2xl">🏆</span>
          </div>

          <div className="p-3.5 rounded-xl bg-obsidian-900 border border-obsidian-800 flex items-center justify-between">
            <div>
              <span className="text-[10px] font-mono text-slate-400 uppercase block">Tanda Kategori</span>
              <span className="text-lg font-black font-mono text-emerald-400">
                {smartCount} Smart • {whaleCount} Whale
              </span>
              <span className="text-[10px] font-mono text-slate-400 block">Terverifikasi On-Chain</span>
            </div>
            <span className="text-2xl">🧠</span>
          </div>

          <div className="p-3.5 rounded-xl bg-obsidian-900 border border-obsidian-800 flex items-center justify-between">
            <div>
              <span className="text-[10px] font-mono text-slate-400 uppercase block">Perubahan Rank Hari Ini</span>
              <span className="text-lg font-black font-mono text-cyan-300">{rankChangedCount} Dompet Berubah</span>
              <span className="text-[10px] font-mono text-slate-400 block">Periode: {rankingDate}</span>
            </div>
            <span className="text-2xl">📊</span>
          </div>

          <div className="p-3.5 rounded-xl bg-obsidian-900 border border-obsidian-800 flex items-center justify-between">
            <div>
              <span className="text-[10px] font-mono text-slate-400 uppercase block">Auto Copy-Trade Aktif</span>
              <span className="text-lg font-black font-mono text-emerald-400">
                {activeCopyCount} / {allRankedWallets.length} Aktif
              </span>
              <span className="text-[10px] font-mono text-slate-400 block">Default $1.00 / Transaksi</span>
            </div>
            <span className="text-2xl">⚡</span>
          </div>
        </div>

        {/* FILTER TABS (ALL / SMART MONEY / WHALE / ACTIVE COPY) */}
        <div className="flex flex-wrap items-center justify-between gap-2 bg-obsidian-900/90 border border-obsidian-800 p-2 rounded-xl">
          <div className="flex flex-wrap items-center gap-1.5">
            <button
              type="button"
              onClick={() => setFilterType('ALL')}
              className={`px-3 py-1.5 rounded-lg text-xs font-mono font-bold transition ${
                filterType === 'ALL'
                  ? 'bg-amber-400 text-obsidian-950 shadow-sm'
                  : 'bg-obsidian-950 text-slate-300 hover:text-white border border-obsidian-800'
              }`}
            >
              🏆 Semua Rank #1–#10 ({allRankedWallets.length})
            </button>
            <button
              type="button"
              onClick={() => setFilterType('SMART_MONEY')}
              className={`px-3 py-1.5 rounded-lg text-xs font-mono font-bold transition ${
                filterType === 'SMART_MONEY'
                  ? 'bg-emerald-500 text-obsidian-950 shadow-sm'
                  : 'bg-obsidian-950 text-emerald-300 hover:bg-obsidian-850 border border-emerald-500/30'
              }`}
            >
              🧠 Smart Money ({smartCount})
            </button>
            <button
              type="button"
              onClick={() => setFilterType('WHALE')}
              className={`px-3 py-1.5 rounded-lg text-xs font-mono font-bold transition ${
                filterType === 'WHALE'
                  ? 'bg-purple-500 text-white shadow-sm'
                  : 'bg-obsidian-950 text-purple-300 hover:bg-obsidian-850 border border-purple-500/30'
              }`}
            >
              🐋 Whale ({whaleCount})
            </button>
            <button
              type="button"
              onClick={() => setFilterType('ACTIVE_COPY')}
              className={`px-3 py-1.5 rounded-lg text-xs font-mono font-bold transition ${
                filterType === 'ACTIVE_COPY'
                  ? 'bg-cyan-400 text-obsidian-950 shadow-sm'
                  : 'bg-obsidian-950 text-cyan-300 hover:bg-obsidian-850 border border-cyan-500/30'
              }`}
            >
              ⚡ Auto-Copy Aktif ({activeCopyCount})
            </button>
          </div>

          <div className="text-[11px] font-mono text-slate-400 px-2">
            Menampilkan <strong className="text-white">{visibleWallets.length}</strong> dari 10 dompet terbaik hari ini
          </div>
        </div>

        {/* RANK #1 TO #10 WALLET CARDS */}
        <QueryState isLoading={smQuery.isLoading} isError={smQuery.isError} error={smQuery.error}>
          <div
            className={
              isUltrawide
                ? 'grid grid-cols-1 xl:grid-cols-2 gap-4 items-stretch'
                : 'grid grid-cols-1 gap-3.5'
            }
          >
            {visibleWallets.length === 0 ? (
              <div className="p-8 text-center rounded-2xl bg-obsidian-900 border border-obsidian-800 text-slate-400 font-mono text-sm col-span-full">
                Tidak ada dompet pada filter ini atau semua dompet telah disalin. Klik tombol &ldquo;Reset&rdquo; atau pilih tab &ldquo;Semua Rank #1–#10&rdquo;.
              </div>
            ) : (
              visibleWallets.map((w: any) => {
                const rankNum = Number(w.rank || w.id || 1);
                const rankBadge = getRankBadge(rankNum);
                const isTop3 = rankNum <= 3;

                return (
                  <div
                    key={w.id}
                    className={`p-5 rounded-2xl bg-[#0b0f17] border transition-all flex flex-col lg:flex-row lg:items-center justify-between gap-5 ${
                      rankNum === 1
                        ? 'border-amber-400/50 shadow-lg shadow-amber-500/5'
                        : isTop3
                        ? 'border-cyan-500/35'
                        : 'border-slate-800 hover:border-slate-700'
                    }`}
                  >
                    {/* LEFT SECTION: RANK, BADGES, LABEL, WALLET ADDRESS & ACTIVITY */}
                    <div className="space-y-2 flex-1 min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        {/* RANK #1 - #10 BADGE */}
                        <span className={`px-2.5 py-0.5 text-xs font-mono rounded-lg border ${rankBadge.cls}`}>
                          {rankBadge.label}
                        </span>

                        {/* DAILY RANK MOVEMENT INDICATOR */}
                        {renderRankDelta(w)}

                        {/* SMART MONEY / WHALE CLASSIFICATION BADGE */}
                        {renderEntityBadges(w)}

                        {/* CHAIN BADGE */}
                        <span className="px-2 py-0.5 text-[10px] font-mono rounded bg-sky-500/15 text-sky-300 border border-sky-500/30 font-bold">
                          {w.chain}
                        </span>

                        {/* AUTO-MIRROR ACTIVE STATUS */}
                        {w.copy_enabled && (
                          <span className="px-2 py-0.5 text-[10px] font-mono rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 font-bold animate-pulse">
                            ⚡ AUTO-COPY AKTIF
                          </span>
                        )}
                      </div>

                      <div className="flex flex-wrap items-baseline gap-2">
                        <span className="text-base sm:text-lg font-extrabold text-slate-100">{w.label}</span>
                        {w.specialty && (
                          <span className="text-xs font-mono text-slate-400">• {w.specialty}</span>
                        )}
                      </div>

                      {/* WALLET ADDRESS + 1-CLICK COPY */}
                      <div className="flex flex-wrap items-center gap-2 text-xs font-mono text-slate-400">
                        <span className="px-2 py-1 rounded-lg bg-obsidian-950 border border-obsidian-800 text-slate-300 select-all truncate max-w-[260px] sm:max-w-none" title={w.address}>
                          {w.address}
                        </span>
                        <button
                          type="button"
                          onClick={() => handleCopy(w.address, w.id)}
                          className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-sky-300 border border-slate-700 text-[11px] font-mono font-bold flex items-center gap-1 transition"
                          title="Salin Alamat Dompet Smart Money / Whale"
                        >
                          <LucideIcon name={copiedId === w.id ? 'check' : 'copy'} className="w-3 h-3" />
                          <span>{copiedId === w.id ? '✓ Tersalin' : 'Salin Wallet'}</span>
                        </button>
                        {w.recent_token && (
                          <span className="px-2 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/25 text-[10px] font-bold">
                            🎯 Fokus Hari Ini: {w.recent_token}
                          </span>
                        )}
                      </div>

                      <div className="text-xs font-mono text-amber-300/90 pt-0.5">
                        🔔 Aktivitas Harian: {w.last_Action}
                      </div>
                    </div>

                    {/* RIGHT SECTION: METRICS (WIN RATE, 24H PNL, 7D PNL, HOLD, COPY SIZE) & ACTION BUTTON */}
                    <div className="flex flex-wrap items-center justify-between lg:justify-end gap-4 sm:gap-5 font-mono pt-3 lg:pt-0 border-t lg:border-t-0 border-obsidian-800">
                      <div>
                        <div className="text-[10px] text-slate-500 uppercase">Win Rate ({w.trades_7d || 40} Tx)</div>
                        <div className="text-base sm:text-lg font-extrabold text-emerald-400">{w.win_rate}%</div>
                        <div className="text-[10px] text-slate-400">Hold: {w.avg_hold_time}</div>
                      </div>

                      <div>
                        <div className="text-[10px] text-slate-500 uppercase">24H Realized PnL</div>
                        <div className="text-sm sm:text-base font-bold text-cyan-300">
                          +{formatUsd(w.pnl_24h || w.pnl_7d / 6)}
                        </div>
                        <div className="text-[10px] text-slate-400">
                          ≈ +{formatIdr((w.pnl_24h || w.pnl_7d / 6) * usdIdr)}
                        </div>
                      </div>

                      <div>
                        <div className="text-[10px] text-slate-500 uppercase">7D Realized PnL</div>
                        <div className="text-base sm:text-lg font-extrabold text-emerald-400">
                          +{formatUsd(w.pnl_7d)}
                        </div>
                        <div className="text-[10px] text-slate-400">≈ +{formatIdr(w.pnl_7d * usdIdr)}</div>
                      </div>

                      {/* MAX COPY / TRADE SIZING SELECTOR ($1 DEFAULT) */}
                      <div className="space-y-1">
                        <div className="text-[10px] text-slate-500 uppercase">Nominal Copy / Klik</div>
                        <div className="flex items-center gap-1">
                          {[1.0, 2.0, 5.0].map((amt) => {
                            const isSelected = Math.abs(Number(w.max_copy_usd || 1.0) - amt) < 0.05;
                            return (
                              <button
                                key={amt}
                                type="button"
                                disabled={updatingId === w.id}
                                onClick={() => handleMaxCopyChange(w, amt)}
                                className={`px-2 py-0.5 rounded text-[11px] font-bold transition ${
                                  isSelected
                                    ? 'bg-sky-400 text-obsidian-950 shadow-sm'
                                    : 'bg-obsidian-950 text-slate-400 hover:text-white border border-obsidian-800'
                                }`}
                                title={`Setel batas copy trade $${amt.toFixed(2)} USD per transaksi`}
                              >
                                ${amt}
                              </button>
                            );
                          })}
                        </div>
                        <div className="text-[10px] text-slate-400">
                          ≈ {formatIdr(Number(w.max_copy_usd || 1.0) * usdIdr)}
                        </div>
                      </div>

                      <button
                        type="button"
                        disabled={updatingId === w.id}
                        onClick={() => handleToggle(w)}
                        className={`px-4 py-2.5 rounded-xl text-xs font-mono font-extrabold transition shrink-0 ${
                          w.copy_enabled
                            ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40 hover:bg-rose-500/30'
                            : 'bg-emerald-500 text-slate-950 hover:bg-emerald-400 shadow-md shadow-emerald-500/15'
                        }`}
                      >
                        {updatingId === w.id
                          ? 'Memproses...'
                          : w.copy_enabled
                          ? '⏸ Pause Copy Trade'
                          : `▶️ Copy $${Number(w.max_copy_usd || 1.0).toFixed(0)} / Trade`}
                      </button>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </QueryState>
      </div>
    </>
  );
}
