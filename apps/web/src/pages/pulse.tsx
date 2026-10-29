import React, { useState, useEffect, useMemo } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { api, useApiQuery, formatIdr, formatUsd, getTradingMode } from '@/lib/api';
import { QueryState } from '@/components/QueryState';
import { LucideIcon } from '@/components/LucideIcon';
import { useUltrawide } from '@/lib/useUltrawide';

export default function PulsePage() {
  const isUltrawide = useUltrawide();
  const pulseQuery = useApiQuery(() => api.getPulse(), []);
  const [mode, setMode] = useState<'PAPER' | 'LIVE'>('PAPER');
  const [minSafety, setMinSafety] = useState<number>(0);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [activeColumnTab, setActiveColumnTab] = useState<'MICRO' | 'MID' | 'GRADUATE' | 'MAJOR' | 'ALL'>('MICRO');
  const [autoScan, setAutoScan] = useState<boolean>(false);
  const [countdown, setCountdown] = useState<number>(5);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [lastScannedTime, setLastScannedTime] = useState<string>('');
  const [copiedAddresses, setCopiedAddresses] = useState<string[]>(() => {
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

  const copiedSet = useMemo(() => new Set(copiedAddresses.map((a) => a.toLowerCase())), [copiedAddresses]);

  const handleResetCopied = () => {
    setCopiedAddresses([]);
    if (typeof window !== 'undefined') {
      try {
        localStorage.removeItem('sofia_copied_wallets');
      } catch {}
    }
  };

  const refetchPulse = pulseQuery.refetch;

  useEffect(() => {
    if (pulseQuery.data) {
      const now = new Date();
      setLastScannedTime(now.toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit', second: '2-digit' }));
    }
  }, [pulseQuery.data]);

  // Auto-scan timer (5 detik interval sesuai instruksi engine)
  useEffect(() => {
    if (!autoScan) {
      setCountdown(5);
      return;
    }
    const timer = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          refetchPulse();
          return 5;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, [autoScan, refetchPulse]);

  // Handle copy text & sembunyikan wallet/token yang sudah dicopy alamatnya dari scanner
  const handleCopyText = (text: string, key: string, tokenData?: any) => {
    if (typeof navigator !== 'undefined' && navigator.clipboard) {
      navigator.clipboard.writeText(text);
      setCopiedKey(key);
      setTimeout(() => setCopiedKey(null), 2500);

      const toAdd: string[] = [];
      const cleanText = (text || '').trim().toLowerCase();
      if (cleanText.length >= 10) toAdd.push(cleanText);
      if (tokenData?.contract) {
        const c = String(tokenData.contract).trim().toLowerCase();
        if (c.length >= 10) toAdd.push(c);
      }
      if (tokenData?.creator_address) {
        const ca = String(tokenData.creator_address).trim().toLowerCase();
        if (ca.length >= 10) toAdd.push(ca);
      }

      if (toAdd.length > 0) {
        setCopiedAddresses((prev) => {
          const next = Array.from(new Set([...prev, ...toAdd]));
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

  useEffect(() => {
    if (typeof window !== 'undefined') {
      setMode(getTradingMode());
      const modeHandler = (e: any) => setMode(e.detail);
      window.addEventListener('sofia-mode-change', modeHandler);
      return () => {
        window.removeEventListener('sofia-mode-change', modeHandler);
      };
    }
  }, []);

  const usdIdr = pulseQuery.data?.fx?.usd_idr || 16500;

  // Anti-Charity, Donasi & Mayhem token detection filter
  const isExcludedTokenClient = (sym?: string, name?: string): boolean => {
    const s = String(sym || '').toLowerCase();
    const n = String(name || '').toLowerCase();
    const cleanSym = s.split('/')[0].trim();

    for (const prefix of ['charity', 'donate', 'donation', 'giveback', 'savethe', 'yayasan', 'nonprofit', 'mayhem', 'donasi']) {
      if (cleanSym.includes(prefix)) return true;
    }
    const excludedPattern = /\b(charity|charities|donate|donates|donation|donations|donating|giveback|foundation|nonprofit|non-profit|ngo|philanthropy|philanthropic|humanitarian|unicef|yayasan|donasi|sedekah|zakat|orphan|orphanage|animalrescue|disaster relief|mayhem|mayhems)\b/i;
    return excludedPattern.test(s) || excludedPattern.test(n);
  };

  // Filter helper for search query, min safety, exclusion, and hiding copied wallets
  const filterTokens = (list: any[]) => {
    if (!list) return [];
    return list.filter((t) => {
      // 1. Sembunyikan jika kontrak atau wallet creator sudah pernah disalin
      const contractLower = String(t.contract || '').trim().toLowerCase();
      const creatorLower = String(t.creator_address || '').trim().toLowerCase();
      if (contractLower && copiedSet.has(contractLower)) return false;
      if (creatorLower && copiedSet.has(creatorLower)) return false;

      // 2. Blokir ketat koin amal, donasi, dan mayhem
      if (t.is_charity || isExcludedTokenClient(t.symbol, t.name)) return false;

      if (t.safety_score < minSafety) return false;
      if (!searchQuery.trim()) return true;
      const q = searchQuery.toLowerCase();
      const sym = (t.symbol || '').toLowerCase();
      const name = (t.name || '').toLowerCase();
      const ca = (t.contract || '').toLowerCase();
      return sym.includes(q) || name.includes(q) || ca.includes(q);
    });
  };

  // ENGINE RECOMMENDATION RANKING FORMULA
  // Menghitung bobot rekomendasi berdasarkan RugShield safety score, volume 5m, bonding progress, dan smart money
  const getRecommendationScore = (t: any): number => {
    const safety = Number(t.safety_score) || 50;
    const vol = Number(t.volume_5m) || 0;
    const bonding = Number(t.bonding_curve_pct) || 0;
    const smart = (Number(t.gmgn_smart_degens) || 0) * 12;
    const mintSafe = t.mint_revoked ? 20 : 0;
    const lpSafe = t.lp_burned ? 20 : 0;
    const volScore = Math.min(60, Math.log10(Math.max(1, vol)) * 12);
    return (safety * 1.5) + (bonding * 0.35) + volScore + smart + mintSafe + lpSafe;
  };

  // Sort dari yang paling rekomendasi & batasi maksimal 10 koin
  const sortAndLimitTokens = (list: any[], limit = 10) => {
    return [...list]
      .sort((a, b) => getRecommendationScore(b) - getRecommendationScore(a))
      .slice(0, limit);
  };

  const allRawTokens = useMemo(() => {
    return [
      ...(pulseQuery.data?.new_creations || []),
      ...(pulseQuery.data?.final_stretch || []),
      ...(pulseQuery.data?.migrated || []),
    ];
  }, [pulseQuery.data]);

  const microTokens = useMemo(() => {
    const filtered = filterTokens(
      allRawTokens.filter((t) => (t.market_cap || 0) < 100000 || t.is_new_creation)
    );
    return sortAndLimitTokens(filtered, 10);
  }, [allRawTokens, minSafety, searchQuery]);

  const midTokens = useMemo(() => {
    const filtered = filterTokens(
      allRawTokens.filter((t) => (t.market_cap || 0) >= 100000 && (t.market_cap || 0) < 1000000)
    );
    return sortAndLimitTokens(filtered, 10);
  }, [allRawTokens, minSafety, searchQuery]);

  const graduateTokens = useMemo(() => {
    const filtered = filterTokens(
      allRawTokens.filter(
        (t) =>
          ((t.bonding_curve_pct || 0) >= 100 ||
            t.lp_burned ||
            String(t.launchpad || '').toLowerCase().includes('raydium') ||
            String(t.launchpad || '').toLowerCase().includes('pumpswap')) &&
          (t.market_cap || 0) < 1000000
      )
    );
    return sortAndLimitTokens(filtered, 10);
  }, [allRawTokens, minSafety, searchQuery]);

  const majorTokens = useMemo(() => {
    const filtered = filterTokens(allRawTokens.filter((t) => (t.market_cap || 0) >= 1000000));
    return sortAndLimitTokens(filtered, 10);
  }, [allRawTokens, minSafety, searchQuery]);

  const allFilteredTokens = useMemo(() => {
    const filtered = filterTokens(allRawTokens);
    return sortAndLimitTokens(filtered, 10);
  }, [allRawTokens, minSafety, searchQuery]);

  const totalRawCount = allRawTokens.length;

  const totalSafeCount = allRawTokens.filter((t) => (t.safety_score || 0) >= 75).length;

  const renderTokenCard = (t: any, index?: number) => {
    const isSafe = (t.safety_score || 0) >= 75;
    const isWarning = (t.safety_score || 0) >= 55 && (t.safety_score || 0) < 75;
    const cardKey = t.contract || t.symbol;
    const isCaCopied = copiedKey === `ca-${cardKey}`;
    const isCreatorCopied = copiedKey === `creator-${cardKey}`;
    const isCardCaCopied = copiedKey === `card-ca-${cardKey}`;
    const rank = index !== undefined ? index + 1 : undefined;

    const safetyBadgeStyle = isSafe
      ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
      : isWarning
      ? 'bg-amber-500/15 text-amber-300 border-amber-500/30'
      : 'bg-rose-500/15 text-rose-300 border-rose-500/30';

    return (
      <div
        key={cardKey}
        className="rounded-2xl p-4 bg-obsidian-900 border border-obsidian-750 hover:border-obsidian-650 transition-all duration-200 shadow-md space-y-3.5 flex flex-col justify-between"
      >
        {/* TOP ROW: SYMBOL, RANK, LAUNCHPAD, AGE & SAFETY BADGE */}
        <div className="space-y-2.5">
          <div className="flex items-start justify-between gap-2">
            <div className="space-y-0.5">
              <div className="flex flex-wrap items-center gap-1.5">
                {rank !== undefined && (
                  <span
                    className={`text-[10px] font-mono font-black px-1.5 py-0.5 rounded border flex items-center gap-1 ${
                      rank === 1
                        ? 'bg-amber-400 text-obsidian-950 border-amber-400 shadow-sm'
                        : rank <= 3
                        ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40'
                        : 'bg-obsidian-950 text-slate-400 border-obsidian-800'
                    }`}
                    title={`Peringkat #${rank} Rekomendasi Engine Sofia`}
                  >
                    <span>#{rank}</span>
                    {rank === 1 && <span className="text-[9px]">★ TOP</span>}
                  </span>
                )}
                <span className="font-black text-base text-white tracking-tight">{t.symbol}</span>
                {t.launchpad && (
                  <span className="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded bg-obsidian-950 text-cyan-300 border border-obsidian-800">
                    {t.launchpad}
                  </span>
                )}
                {t.age && (
                  <span className="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded border border-emerald-500/20">
                    {t.age}
                  </span>
                )}
              </div>
              <div className="text-xs text-slate-400 line-clamp-1">{t.name}</div>
            </div>

            {/* SAFETY SHIELD BADGE */}
            <span
              className={`text-[10px] px-2 py-0.5 rounded-lg border font-mono font-bold flex items-center gap-1 shrink-0 ${safetyBadgeStyle}`}
              title={`Skor Keselamatan Kontrak: ${t.safety_score}/100`}
            >
              <LucideIcon name="shield-check" className="w-3 h-3" />
              <span>Shield {t.safety_score}/100</span>
            </span>
          </div>

          {/* CONTRACT ADDRESS BAR WITH 1-CLICK COPY */}
          {t.contract && (
            <div className="flex items-center justify-between gap-1.5 p-1.5 px-2 rounded-xl bg-obsidian-950 border border-obsidian-800 text-[11px] font-mono">
              <span className="text-slate-400 truncate max-w-[160px] sm:max-w-[200px]" title={t.contract}>
                CA: <strong className="text-slate-200">{t.contract.slice(0, 6)}...{t.contract.slice(-4)}</strong>
              </span>
              <button
                type="button"
                onClick={() => handleCopyText(t.contract, `ca-${cardKey}`, t)}
                className={`px-2 py-0.5 rounded text-[10px] font-bold font-mono transition flex items-center gap-1 ${
                  isCaCopied
                    ? 'bg-emerald-500 text-obsidian-950'
                    : 'bg-obsidian-900 hover:bg-obsidian-850 text-amber-300 border border-obsidian-750'
                }`}
                title="Salin Mint Contract (CA) & Sembunyikan dari Radar"
              >
                <LucideIcon name={isCaCopied ? 'check' : 'copy'} className="w-2.5 h-2.5" />
                <span>{isCaCopied ? '✓ Tersalin' : 'Salin CA'}</span>
              </button>
            </div>
          )}

          {/* CREATOR / DEV WALLET (IF DETECTED) */}
          {t.creator_address && (
            <div className="flex items-center justify-between gap-1.5 px-2 py-1 rounded-lg bg-obsidian-950/60 border border-obsidian-850 text-[10px] font-mono text-slate-500">
              <span className="truncate max-w-[160px]" title={t.creator_address}>
                Dev: {t.creator_address.slice(0, 4)}...{t.creator_address.slice(-4)}
              </span>
              <button
                type="button"
                onClick={() => handleCopyText(t.creator_address, `creator-${cardKey}`, t)}
                className={`px-1.5 py-0.2 rounded text-[9px] font-bold transition flex items-center gap-0.5 ${
                  isCreatorCopied
                    ? 'bg-cyan-400 text-obsidian-950'
                    : 'bg-obsidian-900 hover:bg-obsidian-800 text-cyan-300 border border-obsidian-750'
                }`}
                title="Salin Alamat Wallet Dev/Creator & Sembunyikan dari Radar"
              >
                <LucideIcon name={isCreatorCopied ? 'check' : 'copy'} className="w-2 h-2" />
                <span>{isCreatorCopied ? '✓' : 'Dev Wallet'}</span>
              </button>
            </div>
          )}

          {/* PRICE BAR */}
          <div className="flex items-baseline justify-between pt-0.5 border-t border-obsidian-800/80">
            <div>
              <span className="text-[10px] text-slate-500 block font-mono">HARGA MARKET</span>
              <div className="text-sm font-black font-mono text-white">
                {formatUsd(t.price)}
              </div>
            </div>
            <div className="text-right">
              <span className="text-[10px] text-slate-500 block font-mono">KURS RUPIAH</span>
              <div className="text-xs font-mono font-bold text-emerald-400">
                ≈ {formatIdr(t.price * usdIdr)}
              </div>
            </div>
          </div>

          {/* BONDING / LIQUIDITY CURVE PROGRESS BAR */}
          <div className="space-y-1">
            <div className="flex justify-between text-[10px] font-mono text-slate-400">
              <span>Bonding / Liquidity Curve</span>
              <span className="text-cyan-300 font-bold">{t.bonding_curve_pct || 0}%</span>
            </div>
            <div className="w-full h-1.5 rounded-full bg-obsidian-950 border border-obsidian-800 overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-cyan-500 to-emerald-400 transition-all duration-300"
                style={{ width: `${Math.min(100, Math.max(0, t.bonding_curve_pct || 0))}%` }}
              />
            </div>
          </div>

          {/* KEY FINANCIAL METRICS GRID */}
          <div className="grid grid-cols-3 gap-1.5 p-2 rounded-xl bg-obsidian-950/80 border border-obsidian-800 text-[10px] font-mono">
            <div>
              <span className="text-slate-500 block">MCAP</span>
              <span className="text-white font-bold">${((t.market_cap || 0) / 1000).toFixed(1)}K</span>
              <span className="text-[9px] text-slate-400 block truncate">
                ≈ {formatIdr((t.market_cap || 0) * usdIdr)}
              </span>
            </div>
            <div>
              <span className="text-slate-500 block">LIKUIDITAS</span>
              <span className="text-white font-bold">${((t.liquidity || 0) / 1000).toFixed(1)}K</span>
              <span className="text-[9px] text-slate-400 block truncate">
                ≈ {formatIdr((t.liquidity || 0) * usdIdr)}
              </span>
            </div>
            <div>
              <span className="text-slate-500 block">5M VOL</span>
              <span className="text-cyan-300 font-bold">${((t.volume_5m || 0) / 1000).toFixed(1)}K</span>
              <span
                className={`text-[9px] block font-bold ${
                  (t.price_change_5m || 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'
                }`}
              >
                5m: {(t.price_change_5m || 0) >= 0 ? '+' : ''}
                {t.price_change_5m ?? 0}%
              </span>
            </div>
          </div>

          {/* ON-CHAIN SIGNALS & SMART MONEY TAGS */}
          <div className="flex flex-wrap items-center gap-1.5 text-[9px] font-mono">
            <span className="px-1.5 py-0.5 rounded bg-obsidian-950 text-slate-300 border border-obsidian-800">
              B/S 5m: <strong className="text-white">{t.buys_5m ?? 0}/{t.sells_5m ?? 0}</strong>
            </span>
            {t.gmgn_smart_degens !== undefined && t.gmgn_smart_degens > 0 && (
              <span className="px-1.5 py-0.5 rounded bg-purple-500/15 text-purple-300 border border-purple-500/30 font-bold">
                🧠 GMGN: {t.gmgn_smart_degens}W
              </span>
            )}
            {t.mint_revoked && (
              <span className="px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">
                ✓ Mint Revoked
              </span>
            )}
            {t.lp_burned && (
              <span className="px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">
                ✓ LP Burned
              </span>
            )}
          </div>
        </div>

        {/* BOTTOM ACTION SECTION: SALIN CA & LINK AUTO ENTRY */}
        <div className="pt-2 border-t border-obsidian-800 space-y-2">
          <div className="flex items-center gap-1.5">
            <button
              type="button"
              onClick={() => handleCopyText(t.contract || '', `card-ca-${cardKey}`, t)}
              className={`flex-1 py-2 px-3 rounded-xl font-mono font-bold text-xs transition flex items-center justify-center gap-1.5 shadow-sm ${
                isCardCaCopied
                  ? 'bg-emerald-500 text-obsidian-950 shadow-emerald-500/20'
                  : 'bg-obsidian-950 hover:bg-obsidian-850 text-cyan-300 border border-obsidian-750 hover:border-cyan-500/40'
              }`}
              title="Salin Mint Contract Address (CA) & Sembunyikan dari Radar"
            >
              <LucideIcon name={isCardCaCopied ? 'check' : 'copy'} className="w-3.5 h-3.5" />
              <span>{isCardCaCopied ? '✓ CA Tersalin' : 'Salin CA'}</span>
            </button>

            <Link
              href="/auto-entry"
              className="px-2.5 py-2 rounded-xl bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 border border-amber-500/30 hover:border-amber-400 font-mono text-xs font-bold transition flex items-center gap-1 shrink-0"
              title="Buka menu Auto Entry Bot untuk snipe & auto buy"
            >
              <LucideIcon name="target" className="w-3.5 h-3.5 text-amber-400" />
              <span className="hidden sm:inline">Auto Entry</span>
            </Link>
          </div>

          <div className="flex items-center justify-between text-[11px] font-mono pt-0.5">
            <div className="flex items-center gap-2">
              {t.dex_url && (
                <a
                  href={t.dex_url}
                  target="_blank"
                  rel="noreferrer"
                  className="px-2 py-0.5 rounded-lg bg-obsidian-950 hover:bg-obsidian-800 text-cyan-300 border border-obsidian-800 inline-flex items-center gap-1 transition"
                >
                  <span>DexScreener</span>
                  <LucideIcon name="external-link" className="w-2.5 h-2.5" />
                </a>
              )}
              {t.gmgn_url && (
                <a
                  href={t.gmgn_url}
                  target="_blank"
                  rel="noreferrer"
                  className="px-2 py-0.5 rounded-lg bg-obsidian-950 hover:bg-obsidian-800 text-emerald-400 border border-obsidian-800 inline-flex items-center gap-1 transition"
                >
                  <span>GMGN.ai</span>
                  <LucideIcon name="external-link" className="w-2.5 h-2.5" />
                </a>
              )}
            </div>

            {t.pumpfun_url && (
              <a
                href={t.pumpfun_url}
                target="_blank"
                rel="noreferrer"
                className="text-purple-400 hover:text-purple-300 transition inline-flex items-center gap-0.5 text-[10px]"
              >
                <span>Pump.fun</span>
                <LucideIcon name="external-link" className="w-2.5 h-2.5" />
              </a>
            )}
          </div>
        </div>
      </div>
    );
  };

  const renderColumn = (title: string, subtitle: string, badgeDot: string, tokens: any[]) => {
    return (
      <div className="space-y-2.5">
        <div className="flex items-center justify-between text-xs font-mono px-0.5 text-slate-400">
          <div className="flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${badgeDot}`} />
            <span className="font-bold text-slate-100">{title}</span>
            <span className="text-slate-500 hidden sm:inline">— {subtitle}</span>
          </div>
          <div className="flex items-center gap-2 font-mono text-[11px]">
            <span className="text-amber-300 font-bold">Top {tokens.length} Rekomendasi</span>
            <span className="text-slate-600">·</span>
            <span className="text-slate-400">Max 10</span>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
          {tokens.length === 0 ? (
            <div className="col-span-full p-8 text-center text-xs text-slate-500 font-mono bg-obsidian-900/40 rounded-xl border border-obsidian-850">
              Tidak ada koin yang sesuai dengan filter di kategori ini.
            </div>
          ) : (
            tokens.map((t, idx) => renderTokenCard(t, idx))
          )}
        </div>
      </div>
    );
  };

  return (
    <>
      <Head>
        <title>Trenches &amp; Pulse Radar | Sofia Market 4.1</title>
      </Head>

      <div className="space-y-3 pb-12">
        {/* COMPACT MINIMALIST HEADER & CONTROLS */}
        <div className="bg-obsidian-900/90 border border-obsidian-800 rounded-xl px-3.5 py-2.5 shadow-sm flex flex-wrap items-center justify-between gap-2.5">
          {/* TITLE & LIVE INLINE STATS */}
          <div className="flex flex-wrap items-center gap-2.5">
            <div className="flex items-center gap-1.5 font-bold text-slate-100 text-sm">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <LucideIcon name="zap" className="w-4 h-4 text-amber-400" />
              <span>Pulse Radar</span>
            </div>

            <div className="hidden sm:flex items-center gap-2 text-[11px] font-mono text-slate-400 border-l border-obsidian-800 pl-2.5">
              <span className="text-amber-300 font-bold">Top 10 Rekomendasi</span>
              <span className="text-slate-600">·</span>
              <span>{totalRawCount} Radar</span>
              <span className="text-slate-600">·</span>
              <span className="text-emerald-400">🛡️ {totalSafeCount} Aman</span>
              <span className="text-slate-600">·</span>
              <span className="text-rose-400 font-bold" title="Koin Amal, Donasi, dan Mayhem otomatis diblokir sistem">
                🚫 Anti-Charity / Mayhem
              </span>
              {copiedAddresses.length > 0 && (
                <>
                  <span className="text-slate-600">·</span>
                  <button
                    type="button"
                    onClick={handleResetCopied}
                    className="px-1.5 py-0.5 rounded bg-amber-500/15 hover:bg-amber-500/25 text-amber-300 border border-amber-500/30 text-[10px] font-bold flex items-center gap-1 transition"
                    title="Klik untuk mereset dan menampilkan kembali token/wallet yang sudah disalin"
                  >
                    <span>👁️ Disalin: {copiedAddresses.length} (Reset)</span>
                  </button>
                </>
              )}
              <span className="text-slate-600">·</span>
              <span className="text-slate-300 font-bold">{formatIdr(usdIdr)}</span>
              {lastScannedTime && (
                <>
                  <span className="text-slate-600">·</span>
                  <span className={pulseQuery.isFetching ? 'text-cyan-400 font-bold animate-pulse' : 'text-slate-400'}>
                    {pulseQuery.isFetching ? '⚡ Memindai...' : `Update: ${lastScannedTime}`}
                  </span>
                </>
              )}
            </div>
          </div>

          {/* RIGHT CONTROLS: 5S AUTO-SCAN / STOP SCAN, REFRESH, MODE & AUTO ENTRY */}
          <div className="flex flex-wrap items-center gap-2 text-xs font-mono">
            {/* 5-DETIK AUTO-SCAN / STOP SCAN BUTTON */}
            {autoScan ? (
              <button
                type="button"
                onClick={() => {
                  setAutoScan(false);
                  setCountdown(5);
                }}
                className="px-2.5 py-1 rounded-lg border border-rose-500/70 bg-rose-950/80 hover:bg-rose-900 text-rose-200 ring-2 ring-rose-500/30 transition flex items-center gap-1.5 shadow-sm font-bold animate-pulse"
                title="Klik untuk menghentikan pemindaian otomatis"
              >
                <span className="w-2 h-2 rounded-sm bg-rose-400" />
                <span>⏹ Stop Scan ({countdown}s)</span>
              </button>
            ) : (
              <button
                type="button"
                onClick={() => {
                  setAutoScan(true);
                  setCountdown(5);
                  pulseQuery.refetch();
                }}
                className="px-2.5 py-1 rounded-lg border border-emerald-500/50 bg-emerald-950/40 hover:bg-emerald-900/60 text-emerald-300 transition flex items-center gap-1.5 shadow-sm font-bold"
                title="Mulai pemindaian otomatis setiap 5 detik"
              >
                <span className="w-2 h-2 rounded-full bg-emerald-400" />
                <span>▶ Jalankan Scan (5s)</span>
              </button>
            )}

            {/* REFRESH BUTTON */}
            <button
              type="button"
              onClick={() => pulseQuery.refetch()}
              className="p-1.5 rounded-lg border border-obsidian-800 bg-obsidian-950 hover:bg-obsidian-850 text-slate-300"
              title="Refresh live data"
            >
              <LucideIcon name="refresh-cw" className={`w-3.5 h-3.5 ${pulseQuery.isFetching ? 'animate-spin' : ''}`} />
            </button>

            {/* TRADING MODE BADGE */}
            <span
              className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                mode === 'LIVE'
                  ? 'bg-rose-500/10 text-rose-300 border-rose-500/30'
                  : 'bg-cyan-500/10 text-cyan-300 border-cyan-500/30'
              }`}
            >
              {mode === 'LIVE' ? 'LIVE' : 'PAPER'}
            </span>

            {/* SCREENING BADGE */}
            <span className="hidden sm:inline-block px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-cyan-500/10 text-cyan-300 border border-cyan-500/30">
              RADAR SCREENING
            </span>

            {/* LINK KE MENU AUTO ENTRY UNTUK SNIPING */}
            <Link
              href="/auto-entry"
              className="px-2.5 py-1 rounded-lg border border-amber-500/40 bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 font-mono text-xs font-bold transition flex items-center gap-1.5"
              title="Buka menu Auto Entry Bot untuk mengeksekusi sniper token"
            >
              <LucideIcon name="target" className="w-3.5 h-3.5 text-amber-400" />
              <span>Menu Auto Entry ↗</span>
            </Link>
          </div>
        </div>

        {/* COMPACT MINIMALIST TAB BAR & FILTERS */}
        <div className="bg-obsidian-900/90 border border-obsidian-800 rounded-xl p-1.5 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-2">
          {/* CATEGORY TABS */}
          <div className="flex items-center gap-1 overflow-x-auto">
            <button
              type="button"
              onClick={() => setActiveColumnTab('MICRO')}
              className={`px-2.5 py-1.5 rounded-lg text-xs font-medium transition flex items-center gap-1.5 shrink-0 ${
                activeColumnTab === 'MICRO'
                  ? 'bg-sky-500/20 text-sky-300 border border-sky-500/30 font-bold'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-obsidian-850'
              }`}
            >
              <span>🌱 Micro Cap</span>
              <span className="px-1.5 py-0.2 rounded-full bg-sky-950/80 text-[10px] font-mono text-sky-300">
                {microTokens.length}
              </span>
            </button>

            <button
              type="button"
              onClick={() => setActiveColumnTab('MID')}
              className={`px-2.5 py-1.5 rounded-lg text-xs font-medium transition flex items-center gap-1.5 shrink-0 ${
                activeColumnTab === 'MID'
                  ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30 font-bold'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-obsidian-850'
              }`}
            >
              <span>⚡ Mid Cap</span>
              <span className="px-1.5 py-0.2 rounded-full bg-amber-950/80 text-[10px] font-mono text-amber-300">
                {midTokens.length}
              </span>
            </button>

            <button
              type="button"
              onClick={() => setActiveColumnTab('GRADUATE')}
              className={`px-2.5 py-1.5 rounded-lg text-xs font-medium transition flex items-center gap-1.5 shrink-0 ${
                activeColumnTab === 'GRADUATE'
                  ? 'bg-purple-500/20 text-purple-300 border border-purple-500/30 font-bold'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-obsidian-850'
              }`}
            >
              <span>🎓 Graduate</span>
              <span className="px-1.5 py-0.2 rounded-full bg-purple-950/80 text-[10px] font-mono text-purple-300">
                {graduateTokens.length}
              </span>
            </button>

            <button
              type="button"
              onClick={() => setActiveColumnTab('MAJOR')}
              className={`px-2.5 py-1.5 rounded-lg text-xs font-medium transition flex items-center gap-1.5 shrink-0 ${
                activeColumnTab === 'MAJOR'
                  ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-bold'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-obsidian-850'
              }`}
            >
              <span>💎 Major</span>
              <span className="px-1.5 py-0.2 rounded-full bg-emerald-950/80 text-[10px] font-mono text-emerald-300">
                {majorTokens.length}
              </span>
            </button>

            <button
              type="button"
              onClick={() => setActiveColumnTab('ALL')}
              className={`px-2.5 py-1.5 rounded-lg text-xs font-medium transition flex items-center gap-1.5 shrink-0 ${
                activeColumnTab === 'ALL'
                  ? 'bg-obsidian-800 text-white border border-obsidian-700 font-bold'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-obsidian-850'
              }`}
            >
              <span>Semua</span>
              <span className="px-1.5 py-0.2 rounded-full bg-obsidian-950 text-[10px] font-mono text-slate-300">
                {allFilteredTokens.length}
              </span>
            </button>
          </div>

          {/* SEARCH & SHIELD FILTER */}
          <div className="flex items-center gap-2">
            <div className="relative w-full sm:w-48">
              <LucideIcon
                name="search"
                className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-1/2 -translate-y-1/2"
              />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Cari simbol / CA..."
                className="w-full pl-7 pr-6 py-1 rounded-lg bg-obsidian-950 border border-obsidian-800 text-white placeholder-slate-500 font-mono text-[11px] focus:outline-none focus:border-cyan-400"
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => setSearchQuery('')}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white text-xs"
                >
                  ✕
                </button>
              )}
            </div>

            <div className="flex items-center gap-1 text-[11px] font-mono shrink-0">
              <span className="text-slate-500 hidden sm:inline">Shield:</span>
              {[0, 75].map((score) => (
                <button
                  key={score}
                  type="button"
                  onClick={() => setMinSafety(score)}
                  className={`px-2 py-0.5 rounded text-[11px] transition font-mono ${
                    minSafety === score
                      ? 'bg-emerald-500 text-obsidian-950 font-bold'
                      : 'bg-obsidian-950 text-slate-400 hover:text-white border border-obsidian-800'
                  }`}
                >
                  {score === 0 ? 'All' : '≥75'}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* RADAR CONTENT PER SELECTED TAB */}
        <QueryState
          isLoading={pulseQuery.isLoading}
          isError={pulseQuery.isError}
          error={pulseQuery.error}
          hasData={Boolean(pulseQuery.data)}
        >
          {activeColumnTab === 'MICRO' &&
            renderColumn(
              '🌱 Micro-Cap (<$100K MCap)',
              'Pasangan meme coin baru rilis & kapitalisasi mikro trenches',
              'bg-sky-400',
              microTokens
            )}

          {activeColumnTab === 'MID' &&
            renderColumn(
              '⚡ Mid-Cap ($100K – $1M MCap)',
              'Token dengan akselerasi volume & likuiditas yang bertumbuh',
              'bg-amber-400',
              midTokens
            )}

          {activeColumnTab === 'GRADUATE' &&
            renderColumn(
              '🎓 Graduate (Raydium / DEX Migrated)',
              'Pool likuiditas yang telah lulus bonding curve & migrasi ke AMM',
              'bg-purple-400',
              graduateTokens
            )}

          {activeColumnTab === 'MAJOR' &&
            renderColumn(
              '💎 Major Liquidity (>$1M MCap)',
              'Token mapan dengan kapitalisasi besar & likuiditas bluechip',
              'bg-emerald-400',
              majorTokens
            )}

          {activeColumnTab === 'ALL' &&
            renderColumn(
              '🌐 Semua Token Radar',
              'Seluruh token aktif yang terdeteksi secara real-time pada radar',
              'bg-cyan-400',
              allFilteredTokens
            )}
        </QueryState>
      </div>
    </>
  );
}
