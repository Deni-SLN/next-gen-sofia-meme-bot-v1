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
  const [platformFilter, setPlatformFilter] = useState<'ALL' | 'PUMP_FUN' | 'RAYDIUM' | 'OTHER'>('ALL');
  const [activeColumnTab, setActiveColumnTab] = useState<'MICRO' | 'MID' | 'GRADUATE' | 'MAJOR' | 'ALL'>('MICRO');
  const [sortBy, setSortBy] = useState<'AI_SCORE' | 'BUY_PRESSURE' | 'MOMENTUM_5M' | 'VOLUME_5M' | 'VELOCITY' | 'CURVE_GRAD' | 'NEWEST'>('AI_SCORE');
  const [onlyHighBuyPressure, setOnlyHighBuyPressure] = useState<boolean>(false);
  const [onlySweetSpot, setOnlySweetSpot] = useState<boolean>(false);
  const [onlyCleanSupply, setOnlyCleanSupply] = useState<boolean>(false);
  const [onlyWithSocials, setOnlyWithSocials] = useState<boolean>(false);
  const [autoScan, setAutoScan] = useState<boolean>(false);
  const [countdown, setCountdown] = useState<number>(5);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [executingCardKey, setExecutingCardKey] = useState<string | null>(null);
  const [entryNotice, setEntryNotice] = useState<{ type: 'ok' | 'err'; text: string } | null>(null);
  const [lastScannedTime, setLastScannedTime] = useState<string>('');
  const [lookedUpToken, setLookedUpToken] = useState<any | null>(null);
  const [isLookingUpCa, setIsLookingUpCa] = useState<boolean>(false);
  const [copiedAddresses, setCopiedAddresses] = useState<string[]>([]);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      try {
        const saved = localStorage.getItem('sofia_copied_wallets');
        if (saved) {
          const parsed = JSON.parse(saved);
          if (Array.isArray(parsed)) setCopiedAddresses(parsed);
        }
      } catch {}
      api.getDismissedCas()
        .then((res) => {
          if (res?.dismissed?.length) {
            setCopiedAddresses((prev) => {
              const merged = Array.from(new Set([...prev, ...res.dismissed.map((x) => String(x).toLowerCase())]));
              try {
                localStorage.setItem('sofia_copied_wallets', JSON.stringify(merged));
              } catch {}
              return merged;
            });
          }
        })
        .catch(() => {});
    }
  }, []);

  const copiedSet = useMemo(() => new Set(copiedAddresses.map((a) => a.toLowerCase())), [copiedAddresses]);

  const handleResetCopied = () => {
    setCopiedAddresses([]);
    if (typeof window !== 'undefined') {
      try {
        localStorage.removeItem('sofia_copied_wallets');
      } catch {}
    }
    api.resetDismissedCas()
      .then(() => refetchPulse())
      .catch(() => {});
  };

  // 1-Klik Auto Entry $1.00 USD langsung dari kartu Pulse Radar
  const handleQuickEntry1Dollar = async (t: any) => {
    const key = t.contract || t.symbol;
    if (executingCardKey || !t.contract) return;
    setExecutingCardKey(key);
    try {
      const res = await api.executeTokenEntry({
        contract: t.contract,
        symbol: t.symbol,
        name: t.name,
        amount_usd: 1.0,
      });
      if (res?.success) {
        const spentUsd = Number(res.entry?.amount_usd || 1.0).toFixed(2);
        setEntryNotice({
          type: 'ok',
          text: `⚡ 1-Klik Auto Entry $${spentUsd} (${formatIdr(res.entry?.amount_idr)}) berhasil pada ${t.symbol}! Kuota Posisi: ${res.counter}`,
        });
      } else {
        setEntryNotice({
          type: 'err',
          text: res?.error || `Gagal Auto Entry $1.00 pada ${t.symbol}.`,
        });
      }
    } catch (err: any) {
      setEntryNotice({
        type: 'err',
        text: err?.message || `Gagal mengeksekusi 1-Klik Auto Entry $1.00 pada ${t.symbol}.`,
      });
    } finally {
      setExecutingCardKey(null);
      setTimeout(() => setEntryNotice(null), 5000);
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

  // Handle copy text (salin alamat CA murni Base58 ke clipboard & langsung sembunyikan koin agar tidak ditampilkan lagi)
  const handleCopyText = (text: string, key: string, tokenData?: any) => {
    const cleanCa = String(text || '').trim();
    if (!cleanCa) return;
    if (typeof navigator !== 'undefined' && navigator.clipboard) {
      navigator.clipboard.writeText(cleanCa);
      setCopiedKey(key);
      setTimeout(() => setCopiedKey(null), 2500);
    }

    const toHide: string[] = [cleanCa.toLowerCase()];
    if (tokenData?.contract) toHide.push(String(tokenData.contract).trim().toLowerCase());
    if (tokenData?.symbol) {
      const symL = String(tokenData.symbol).trim().toLowerCase();
      toHide.push(symL);
      toHide.push(symL.split('/')[0].trim());
    }
    if (tokenData?.creator_address) toHide.push(String(tokenData.creator_address).trim().toLowerCase());

    setCopiedAddresses((prev) => {
      const next = Array.from(new Set([...prev.map((x) => x.toLowerCase()), ...toHide.filter(Boolean)]));
      if (typeof window !== 'undefined') {
        try {
          localStorage.setItem('sofia_copied_wallets', JSON.stringify(next));
        } catch {}
      }
      return next;
    });

    api.dismissCopiedCa(tokenData?.contract || cleanCa, tokenData?.symbol || '').catch(() => {});

    setEntryNotice({
      type: 'ok',
      text: `📋 CA ${tokenData?.symbol || cleanCa.slice(0, 8)} berhasil disalin ke clipboard & disembunyikan dari radar!`,
    });
    setTimeout(() => setEntryNotice(null), 3500);
  };

  // Live lookup ketika pengguna mem-paste CA atau URL Pump.fun di kotak pencarian
  useEffect(() => {
    const raw = searchQuery.trim();
    if (!raw || (raw.length < 28 && !raw.toLowerCase().includes('pump.fun'))) {
      setLookedUpToken(null);
      setIsLookingUpCa(false);
      return;
    }
    let cancelled = false;
    setIsLookingUpCa(true);
    const timer = setTimeout(async () => {
      try {
        const res = await api.lookupMemeToken(raw);
        if (!cancelled && res && res.contract) {
          setLookedUpToken(res);
          setActiveColumnTab('ALL');
        }
      } catch {
        if (!cancelled) setLookedUpToken(null);
      } finally {
        if (!cancelled) setIsLookingUpCa(false);
      }
    }, 250);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [searchQuery]);

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

  // Anti-Charity, Donasi, Awareness & Mayhem token detection filter
  const isExcludedTokenClient = (sym?: string, name?: string, websiteUrl?: string, contract?: string): boolean => {
    const s = String(sym || '').toLowerCase();
    const n = String(name || '').toLowerCase();
    const w = String(websiteUrl || '').toLowerCase();
    const c = String(contract || '').toLowerCase();
    const cleanSym = s.split('/')[0].replace(/^\$/, '').trim();

    const blacklistedCas = new Set([
      'cseycgmdcad7voh2cgtpbyq4jyh9sldsekux8g2opump',
      '42njgy25velgphpdw3qhz6tajcrgvvjhfhyvvvfepump',
      '42njgy25velgphpdw3qhz6tajcrgvvjhfhytvvfepump',
      'a5dnsptfybyeugkxw4pgkehzslli1fn9td58oy8wpump',
      'a7bhlacmqnc2lgb7bxt77sttbdbm1tyxbphb58epump',
      'a7bhlacmqnc2lgb7bxt77sttbbdm1tyxvbphb58epump',
      'gfrpypkdkepzmmykudjcztmskqnqmpbn39uewojppump',
      'cpogsmcjprcvza2mfyljmpqkgjmgvzkg4rvwmdrzpump',
      '3krqdkpgqmwwbdgjivpppqvzfsnyg5pdqvrvz1d2pump',
    ]);
    if (c && blacklistedCas.has(c)) return true;

    for (const prefix of [
      'charity', 'donate', 'donation', 'giveback', 'savethe', 'yayasan',
      'nonprofit', 'mayhem', 'donasi', 'movember', 'mobros', 'cancer',
      'autism', 'awareness', 'fundrais', 'bluepepe', 'relief', 'tipr',
    ]) {
      if (cleanSym.includes(prefix)) return true;
    }
    if (/https?:\/\/(?:[a-z0-9-]+\.)*[a-z0-9-]+\.org(?:\/|\b)/i.test(w)) return true;

    const excludedPattern = /\b(charity|charities|donate|donates|donation|donations|donating|giveback|foundation|nonprofit|non-profit|ngo|philanthropy|philanthropic|humanitarian|unicef|redcross|red cross|yayasan|donasi|sedekah|zakat|orphan|orphanage|animalrescue|disaster relief|mayhem|mayhems|movember|mobros|mo bros|noshave|cancer|pancreatic|leukemia|lymphoma|tumor|oncology|chemo|prostate|autism|alzheimer|parkinson|dementia|diabetes|stjude|st jude|makeawish|make a wish|hospice|awareness|fundraiser|fundraising|gofundme|givebutter|justgiving|bluepepe|purple coin|white coin|blue coin|pink coin|black coin|orange coin|silver coin|ribbon coin|tipr)\b/i;
    return excludedPattern.test(s) || excludedPattern.test(n);
  };

  // Filter helper for search query, min safety, exclusion, and hiding copied wallets
  const filterTokens = (list: any[]) => {
    if (!list) return [];
    return list.filter((t) => {
      // 0. VALIDASI KETAT KOIN: Pastikan yang di-scan 100% adalah KOIN / TOKEN MINT murni
      const ca = String(t.contract || '').trim();
      const sym = String(t.symbol || '').toUpperCase();
      const baseSym = String(t.base_symbol || sym.split('/')[0]).toUpperCase();
      const name = String(t.name || '').trim().toLowerCase();

      // Kontrak mint address harus ada dan minimal 32 karakter
      if (!ca || ca.length < 32) return false;

      // Blokir aset induk native dan koin stabil (bukan meme coin)
      const majorCurrencies = ['SOL', 'WSOL', 'USDC', 'USDT', 'USD', 'DAI', 'ETH', 'BTC'];
      if (majorCurrencies.includes(baseSym)) return false;

      // Blokir mint address native SOL / USDC / Token Program
      const systemMints = [
        'so11111111111111111111111111111111111111112',
        'epjfwdd5aufqssqeM2qn1xzybapc8g4weggkzwytde1v'.toLowerCase(),
        'es9vmfrzacermjfrf4h2fyd4kconky11mcce8benwnyb'.toLowerCase(),
      ];
      if (systemMints.includes(ca.toLowerCase())) return false;

      // Nama koin tidak boleh dummy / kosong
      if (!name || name === 'unknown' || name === 'null' || name === 'undefined') return false;

      // Harga harus bernilai positif
      if (Number(t.price || 0) <= 0) return false;

      // 1. Sembunyikan jika kontrak, simbol, atau wallet creator sudah pernah disalin
      const contractLower = ca.toLowerCase();
      const symLower = sym.toLowerCase();
      const baseSymLower = baseSym.toLowerCase();
      const creatorLower = String(t.creator_address || '').trim().toLowerCase();
      if (contractLower && copiedSet.has(contractLower)) return false;
      if (symLower && copiedSet.has(symLower)) return false;
      if (baseSymLower && copiedSet.has(baseSymLower)) return false;
      if (creatorLower && copiedSet.has(creatorLower)) return false;

      // 2. Blokir ketat koin amal, donasi, awareness, dan mayhem
      if (t.is_charity || isExcludedTokenClient(t.symbol, t.name, t.website_url, t.contract)) return false;

      // Jika pengguna sedang mencari spesifik dengan kata kunci / CA / URL Pump.fun, prioritaskan kecocokan langsung
      if (searchQuery.trim()) {
        const q = searchQuery.trim().toLowerCase();
        const caL = ca.toLowerCase();
        return (
          sym.toLowerCase().includes(q) ||
          name.includes(q) ||
          caL.includes(q) ||
          (caL.length >= 32 && q.includes(caL))
        );
      }

      // 3. Filter Platform / Venue DEX (Pump.fun vs Raydium vs Lainnya)
      if (platformFilter !== 'ALL') {
        const lp = String(t.launchpad || '').toLowerCase();
        const dx = String(t.dex || '').toLowerCase();
        const caLower = ca.toLowerCase();

        const isPump =
          Boolean(t.is_pumpfun) ||
          lp.includes('pump') ||
          dx.includes('pump') ||
          caLower.endsWith('pump');

        const isRay =
          lp.includes('raydium') ||
          dx.includes('raydium');

        if (platformFilter === 'PUMP_FUN' && !isPump) return false;
        if (platformFilter === 'RAYDIUM' && !isRay) return false;
        if (platformFilter === 'OTHER' && (isPump || isRay)) return false;
      }

      if (t.safety_score < minSafety) return false;

      // 4a. Anti-Dump Guard: tolak koin yang sudah jatuh / tren turun / seller dominan
      const c5m = Number(t.price_change_5m) || 0;
      const c1h = Number(t.price_change_1h) || 0;
      const c24h = Number(t.price_change_24h) || 0;
      const b5 = Number(t.buys_5m) || 0;
      const s5 = Number(t.sells_5m) || 0;
      const dexL = String(t.dex || '').toLowerCase();
      const isPreGrad = dexL === 'pump.fun' || dexL === 'pumpfun' || dexL === 'moonshot';
      const mcapNow = Number(t.market_cap) || 0;
      if (t.is_dumped === true || t.signal_tag === 'AVOID_DUMP') return false;
      if (c24h <= 0 || c1h < 0) return false;
      if (c5m < 0 && !(c5m >= -2 && c1h >= 15 && c24h >= 20 && b5 > s5)) return false;
      if (s5 >= b5) return false;
      if (!isPreGrad && mcapNow < 42000) return false;

      // 4. Filter Tambahan Profitabilitas Sniper
      const buys = Number(t.buys_5m) || 0;
      const sells = Number(t.sells_5m) || 0;
      const buyPct = t.buy_pressure_5m_pct !== undefined
        ? Number(t.buy_pressure_5m_pct)
        : (buys + sells > 0 ? (buys / (buys + sells)) * 100 : 50);
      const curve = Number(t.bonding_curve_pct) || 0;
      const devPct = Number(t.dev_holding_pct ?? 0);
      const top10Pct = Number(t.top10_pct ?? 15);
      const hasSoc = Boolean(t.has_socials || t.website_url || t.twitter_url || t.telegram_url);

      if (onlyHighBuyPressure && buyPct < 60) return false;
      if (onlySweetSpot && (curve < 25 || curve > 92)) return false;
      if (onlyCleanSupply && (devPct > 3.0 || top10Pct > 25.0)) return false;
      if (onlyWithSocials && !hasSoc) return false;

      return true;
    });
  };

  // ENGINE RECOMMENDATION RANKING FORMULA (Optimized for Meme Coin Trench Profitability)
  // Memprioritaskan: Safety Shield, Smart Money Inflow, Orderflow Buys/Sells Ratio, Bonding Curve Velocity & Low Dev/Top10 Risk
  const getRecommendationScore = (t: any): number => {
    const safety = Number(t.safety_score) || 50;
    const vol = Number(t.volume_5m) || 0;
    const bonding = Number(t.bonding_curve_pct) || 0;
    const smart = (Number(t.gmgn_smart_degens) || 0) * 16;
    const mintSafe = t.mint_revoked ? 25 : 0;
    const lpSafe = t.lp_burned ? 25 : 0;
    const volScore = Math.min(65, Math.log10(Math.max(1, vol)) * 14);

    // 1. Order Flow Buy Pressure: Bonus jika rasio buy 5m > 60%
    const buys = Number(t.buys_5m) || 0;
    const sells = Number(t.sells_5m) || 0;
    let orderflowScore = 0;
    if (buys + sells > 0) {
      const buyRatio = buys / (buys + sells);
      orderflowScore = (buyRatio - 0.5) * 50;
    }

    // 2. Bonding Curve Sweet Spot: 25% - 85% adalah zona akumulasi emas sebelum Raydium migration
    let bondingBonus = bonding * 0.35;
    if (bonding >= 25 && bonding <= 85) {
      bondingBonus += 15;
    }

    // 3. Holder & Dev Risk Penalty
    const top10 = Number(t.top10_pct) || 30;
    const devHold = Number(t.dev_holding_pct) || 0;
    const holderPenalty = top10 > 25 ? -18 : (top10 <= 15 ? 12 : 0);
    const devPenalty = devHold > 5 ? -25 : (devHold <= 1.5 ? 10 : 0);

    // 4. Momentum Multi-Timeframe: bonus jika naik, penalti berat jika turun
    const c5m = Number(t.price_change_5m) || 0;
    const c1h = Number(t.price_change_1h) || 0;
    const c24h = Number(t.price_change_24h) || 0;
    const momentumScore =
      (c5m >= 0 ? Math.min(35, c5m * 1.5) : Math.max(-60, c5m * 6)) +
      (c1h >= 0 ? Math.min(25, c1h * 0.4) : Math.max(-60, c1h * 4)) +
      (c24h >= 0 ? Math.min(15, c24h * 0.08) : Math.max(-60, c24h * 1.5));
    const sellerPenalty = sells >= buys ? -40 : 0;
    const dumpPenalty = (t.is_dumped === true || t.signal_tag === 'AVOID_DUMP') ? -200 : 0;

    return (safety * 1.6) + bondingBonus + volScore + smart + mintSafe + lpSafe + orderflowScore + holderPenalty + devPenalty
      + momentumScore + sellerPenalty + dumpPenalty;
  };

  // Normalisasi Skor Profit AI ke skala 0-99 untuk badge kartu
  const getNormalizedProfitScore = (t: any): number => {
    const raw = getRecommendationScore(t);
    return Math.min(99, Math.max(45, Math.round(raw / 3.4)));
  };

  // Sort sesuai pilihan pengguna & batasi maksimal 10 koin
  const sortAndLimitTokens = (list: any[], limit = 10) => {
    return [...list]
      .sort((a, b) => {
        if (sortBy === 'BUY_PRESSURE') {
          const bpA = a.buy_pressure_5m_pct ?? ((a.buys_5m || 0) / Math.max(1, (a.buys_5m || 0) + (a.sells_5m || 0)) * 100);
          const bpB = b.buy_pressure_5m_pct ?? ((b.buys_5m || 0) / Math.max(1, (b.buys_5m || 0) + (b.sells_5m || 0)) * 100);
          return bpB - bpA;
        }
        if (sortBy === 'MOMENTUM_5M') {
          return (Number(b.price_change_5m) || 0) - (Number(a.price_change_5m) || 0);
        }
        if (sortBy === 'VOLUME_5M') {
          return (Number(b.volume_5m) || 0) - (Number(a.volume_5m) || 0);
        }
        if (sortBy === 'VELOCITY') {
          const vA = (Number(a.volume_5m) || 0) / Math.max(1, Number(a.liquidity) || 1);
          const vB = (Number(b.volume_5m) || 0) / Math.max(1, Number(b.liquidity) || 1);
          return vB - vA;
        }
        if (sortBy === 'CURVE_GRAD') {
          const cA = Number(a.bonding_curve_pct) || 0;
          const cB = Number(b.bonding_curve_pct) || 0;
          // Utamakan yang mendekati 100% (80-99%) terlebih dahulu
          const scoreA = cA < 100 ? cA + 20 : cA;
          const scoreB = cB < 100 ? cB + 20 : cB;
          return scoreB - scoreA;
        }
        if (sortBy === 'NEWEST') {
          return (Number(a.age_hours) || 99) - (Number(b.age_hours) || 99);
        }
        return getRecommendationScore(b) - getRecommendationScore(a);
      })
      .slice(0, limit);
  };

  const allRawTokens = useMemo(() => {
    const base = [
      ...(pulseQuery.data?.new_creations || []),
      ...(pulseQuery.data?.final_stretch || []),
      ...(pulseQuery.data?.migrated || []),
    ];
    if (lookedUpToken && lookedUpToken.contract) {
      const exists = base.some(
        (x) => String(x.contract || '').toLowerCase() === String(lookedUpToken.contract).toLowerCase()
      );
      if (!exists) {
        return [lookedUpToken, ...base];
      }
    }
    return base;
  }, [pulseQuery.data, lookedUpToken]);

  const filterDeps = [
    allRawTokens,
    minSafety,
    searchQuery,
    platformFilter,
    sortBy,
    onlyHighBuyPressure,
    onlySweetSpot,
    onlyCleanSupply,
    onlyWithSocials,
    copiedSet,
  ];

  const microTokens = useMemo(() => {
    const filtered = filterTokens(
      allRawTokens.filter((t) => (t.market_cap || 0) < 100000 || t.is_new_creation)
    );
    return sortAndLimitTokens(filtered, 10);
  }, filterDeps);

  const midTokens = useMemo(() => {
    const filtered = filterTokens(
      allRawTokens.filter((t) => (t.market_cap || 0) >= 100000 && (t.market_cap || 0) < 1000000)
    );
    return sortAndLimitTokens(filtered, 10);
  }, filterDeps);

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
  }, filterDeps);

  const majorTokens = useMemo(() => {
    const filtered = filterTokens(allRawTokens.filter((t) => (t.market_cap || 0) >= 1000000));
    return sortAndLimitTokens(filtered, 10);
  }, filterDeps);

  const allFilteredTokens = useMemo(() => {
    const filtered = filterTokens(allRawTokens);
    return sortAndLimitTokens(filtered, 10);
  }, filterDeps);

  // RINGKASAN TELEMETRI PROFITABILITAS PASAR TRENCH
  const trenchInsights = useMemo(() => {
    if (!allRawTokens.length) {
      return {
        goldenSnipeCount: 0,
        topSnipeSymbol: '—',
        avgBuyPressure: 50,
        totalBuys5m: 0,
        totalSells5m: 0,
        fastestVelocityToken: null as any,
        closestGradToken: null as any,
      };
    }
    let goldenCount = 0;
    let bestSnipe: any = null;
    let bestScore = -999;
    let sumBuyPct = 0;
    let totalBuys = 0;
    let totalSells = 0;
    let fastestVel: any = null;
    let maxVel = -1;
    let closestGrad: any = null;
    let maxCurveUnder100 = -1;

    for (const t of allRawTokens) {
      const buys = Number(t.buys_5m) || 0;
      const sells = Number(t.sells_5m) || 0;
      const bp = t.buy_pressure_5m_pct !== undefined
        ? Number(t.buy_pressure_5m_pct)
        : (buys + sells > 0 ? (buys / (buys + sells)) * 100 : 50);
      const curve = Number(t.bonding_curve_pct) || 0;
      const dev = Number(t.dev_holding_pct ?? 0);
      const safety = Number(t.safety_score) || 0;
      const vel = (Number(t.volume_5m) || 0) / Math.max(1, Number(t.liquidity) || 1) * 100;

      sumBuyPct += bp;
      totalBuys += buys;
      totalSells += sells;

      if ((bp >= 60 && safety >= 75 && dev <= 5) || t.signal_tag === 'GOLDEN_SNIPE' || t.signal_tag === 'HIGH_VELOCITY') {
        goldenCount++;
      }
      const sc = getRecommendationScore(t);
      if (sc > bestScore) {
        bestScore = sc;
        bestSnipe = t;
      }
      if (vel > maxVel) {
        maxVel = vel;
        fastestVel = { ...t, calc_vel_pct: vel.toFixed(1) };
      }
      if (curve < 100 && curve > maxCurveUnder100) {
        maxCurveUnder100 = curve;
        closestGrad = t;
      }
    }

    return {
      goldenSnipeCount: goldenCount,
      topSnipeSymbol: bestSnipe?.symbol?.split('/')[0] || '—',
      avgBuyPressure: Math.round(sumBuyPct / allRawTokens.length),
      totalBuys5m: totalBuys,
      totalSells5m: totalSells,
      fastestVelocityToken: fastestVel,
      closestGradToken: closestGrad,
    };
  }, [allRawTokens]);

  const pumpFunScanCount = useMemo(() => {
    return allRawTokens.filter((t) => {
      const lp = String(t.launchpad || '').toLowerCase();
      const dx = String(t.dex || '').toLowerCase();
      const ca = String(t.contract || '').toLowerCase();
      return lp.includes('pump') || dx.includes('pump') || ca.endsWith('pump');
    }).length;
  }, [allRawTokens]);

  const raydiumScanCount = useMemo(() => {
    return allRawTokens.filter((t) => {
      const lp = String(t.launchpad || '').toLowerCase();
      const dx = String(t.dex || '').toLowerCase();
      return lp.includes('raydium') || dx.includes('raydium');
    }).length;
  }, [allRawTokens]);

  const otherScanCount = useMemo(() => {
    return allRawTokens.filter((t) => {
      const lp = String(t.launchpad || '').toLowerCase();
      const dx = String(t.dex || '').toLowerCase();
      const ca = String(t.contract || '').toLowerCase();
      const isPump = lp.includes('pump') || dx.includes('pump') || ca.endsWith('pump');
      const isRay = lp.includes('raydium') || dx.includes('raydium');
      return !isPump && !isRay;
    }).length;
  }, [allRawTokens]);

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

    // Hitung metrik profitabilitas real-time (dari backend atau kalkulasi fallback langsung)
    const buys5m = Number(t.buys_5m) || 0;
    const sells5m = Number(t.sells_5m) || 0;
    const totalTx5m = buys5m + sells5m;
    const buyPressurePct =
      t.buy_pressure_5m_pct !== undefined
        ? Number(t.buy_pressure_5m_pct)
        : totalTx5m > 0
        ? Math.round((buys5m / totalTx5m) * 1000) / 10
        : 50;
    const sellPressurePct = Math.max(0, Math.round((100 - buyPressurePct) * 10) / 10);
    const netBuys5m = t.net_buys_5m !== undefined ? Number(t.net_buys_5m) : buys5m - sells5m;
    const vol5m = Number(t.volume_5m) || 0;
    const avgTxUsd = t.avg_tx_usd_5m !== undefined ? Number(t.avg_tx_usd_5m) : totalTx5m > 0 ? Math.round(vol5m / totalTx5m) : 0;

    const mcap = Math.max(1, Number(t.market_cap) || 1);
    const liq = Math.max(1, Number(t.liquidity) || 1);
    const liqMcapPct =
      t.liq_mcap_ratio_pct !== undefined
        ? Number(t.liq_mcap_ratio_pct)
        : Math.round((liq / mcap) * 1000) / 10;
    const volLiqPct =
      t.vol_liq_ratio_5m_pct !== undefined
        ? Number(t.vol_liq_ratio_5m_pct)
        : Math.round((vol5m / liq) * 1000) / 10;
    const priceImpact10Usd =
      t.price_impact_10usd_pct !== undefined
        ? Number(t.price_impact_10usd_pct)
        : Math.min(25, Math.round((10 / Math.max(150, liq)) * 10000) / 100);

    const curvePct = Number(t.bonding_curve_pct) || 0;
    const mcapToGrad =
      t.mcap_to_grad_usd !== undefined
        ? Number(t.mcap_to_grad_usd)
        : curvePct < 100 && mcap < 69000
        ? Math.max(0, 69000 - mcap)
        : 0;

    const chg1m = Number(t.price_change_1m ?? ((Number(t.price_change_5m) || 0) / 3.5));
    const chg5m = Number(t.price_change_5m || 0);
    const chg1h = Number(t.price_change_1h ?? (chg5m * 2.2));
    const chg24h = Number(t.price_change_24h ?? (chg1h * 2.5));

    const holdersCount = Number(t.holders) || Math.max(35, Math.round(mcap / 280));
    const top10Pct = Number(t.top10_pct ?? 14.5);
    const devPct = Number(t.dev_holding_pct ?? (curvePct === 100 ? 0 : 1.8));
    const bundlePct = Number(t.bundle_pct ?? 1.2);
    const aiProfitScore = getNormalizedProfitScore(t);

    const signalTag = String(t.signal_tag || (buyPressurePct >= 60 && curvePct >= 25 && curvePct <= 85 ? 'GOLDEN_SNIPE' : 'ACCUMULATION'));
    const signalLabel = String(
      t.signal_label ||
        (signalTag === 'GOLDEN_SNIPE'
          ? '🔥 GOLDEN SNIPE'
          : signalTag === 'PRE_GRADUATE'
          ? '🚀 PRE-GRADUATE'
          : signalTag === 'HIGH_VELOCITY'
          ? '⚡ BREAKOUT VELOCITY'
          : '🛡️ AKUMULASI STABIL')
    );
    const signalDesc = String(t.signal_desc || 'Dominasi buyer positif dengan struktur likuiditas sehat');
    const tpPct = Number(t.suggested_tp_pct || 35);
    const slPct = Number(t.suggested_sl_pct || 10);
    const rrRatio = String(t.rr_ratio || `1:${(tpPct / Math.max(1, slPct)).toFixed(1)}`);

    const signalBannerStyle =
      signalTag === 'GOLDEN_SNIPE'
        ? 'bg-gradient-to-r from-amber-500/20 via-emerald-500/15 to-obsidian-950 border-amber-400/50 text-amber-200'
        : signalTag === 'PRE_GRADUATE'
        ? 'bg-gradient-to-r from-purple-500/20 via-pink-500/15 to-obsidian-950 border-purple-400/50 text-purple-200'
        : signalTag === 'HIGH_VELOCITY'
        ? 'bg-gradient-to-r from-cyan-500/20 via-emerald-500/15 to-obsidian-950 border-cyan-400/50 text-cyan-200'
        : signalTag === 'PULLBACK_ENTRY'
        ? 'bg-gradient-to-r from-sky-500/20 via-indigo-500/15 to-obsidian-950 border-sky-400/50 text-sky-200'
        : signalTag === 'CAUTION_THIN_LIQ'
        ? 'bg-rose-950/50 border-rose-500/40 text-rose-300'
        : 'bg-obsidian-950/90 border-emerald-500/30 text-emerald-200';

    const safetyBadgeStyle = isSafe
      ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
      : isWarning
      ? 'bg-amber-500/15 text-amber-300 border-amber-500/30'
      : 'bg-rose-500/15 text-rose-300 border-rose-500/30';

    return (
      <div
        key={cardKey}
        className="rounded-2xl p-3.5 bg-obsidian-900 border border-obsidian-750 hover:border-cyan-500/40 transition-all duration-200 shadow-md space-y-2.5 flex flex-col justify-between"
      >
        {/* TOP ROW: SYMBOL, RANK, LAUNCHPAD, AGE & SAFETY BADGE */}
        <div className="space-y-2">
          <div className="flex items-start justify-between gap-2">
            <div className="space-y-0.5 min-w-0">
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
                <span className="font-black text-base text-white tracking-tight truncate">{t.symbol}</span>
                {/* PROMINENT DEX / LAUNCHPAD BADGE */}
                {(() => {
                  const lp = String(t.launchpad || '').toLowerCase();
                  const dx = String(t.dex || '').toLowerCase();
                  const ca = String(t.contract || '').toLowerCase();
                  const isPump = Boolean(t.is_pumpfun) || lp.includes('pump') || dx.includes('pump') || ca.endsWith('pump');
                  const isRay = lp.includes('raydium') || dx.includes('raydium');

                  if (isPump) {
                    return (
                      <span
                        className="text-[10px] font-mono font-black px-1.5 py-0.5 rounded bg-pink-500/20 text-pink-300 border border-pink-500/40 shadow-sm flex items-center gap-1"
                        title="Token terverifikasi aktif di Pump.fun (CA dapat langsung di-paste di pump.fun)"
                      >
                        <span>💊 PUMP.FUN READY</span>
                      </span>
                    );
                  }
                  if (isRay) {
                    return (
                      <span
                        className="text-[10px] font-mono font-black px-1.5 py-0.5 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-sm flex items-center gap-1"
                        title="Token pool Raydium AMM murni (Tidak diluncurkan di Pump.fun — trade via Raydium/Jupiter)"
                      >
                        <span>⚡ RAYDIUM ONLY</span>
                      </span>
                    );
                  }
                  return (
                    <span className="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded bg-obsidian-950 text-indigo-300 border border-obsidian-800 flex items-center gap-1">
                      <span>🌐 {t.launchpad || 'DEX'} ONLY</span>
                    </span>
                  );
                })()}
                {t.age && (
                  <span className="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded border border-emerald-500/20" title="Umur pasangan token sejak rilis">
                    ⏱️ {t.age}
                  </span>
                )}
                {Number(t.boosts_active || 0) > 0 && (
                  <span className="text-[10px] font-mono font-bold text-amber-300 bg-amber-500/20 px-1.5 py-0.5 rounded border border-amber-400/40" title="Token sedang di-boost di DexScreener">
                    ⚡ Boost {t.boosts_active}
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
              <span>Shield {t.safety_score}</span>
            </span>
          </div>

          {/* QUANT SNIPER SIGNAL & PROFIT SCORE BANNER */}
          <div className={`px-2.5 py-1.5 rounded-xl border ${signalBannerStyle} flex flex-col gap-0.5`}>
            <div className="flex items-center justify-between gap-1.5">
              <span className="text-[11px] font-mono font-black tracking-wide">{signalLabel}</span>
              <span className="text-[10px] font-mono font-black px-1.5 py-0.2 rounded bg-obsidian-950/90 text-emerald-300 border border-emerald-500/30">
                🎯 Skor Profit: {aiProfitScore}/99
              </span>
            </div>
            <div className="text-[10px] text-slate-300/90 leading-tight line-clamp-1">
              {signalDesc}
            </div>
          </div>

          {/* CONTRACT ADDRESS BAR + SOCIAL PROOF BADGES */}
          {t.contract && (
            <div className="flex items-center justify-between gap-1.5 p-1.5 px-2 rounded-xl bg-obsidian-950 border border-obsidian-800 text-[10px] font-mono">
              <div className="flex items-center gap-1.5 min-w-0">
                <span className="text-slate-400 truncate" title={`Alamat Mint Koin: ${t.contract}`}>
                  🪙 <strong className="text-emerald-300 font-bold">{t.contract.slice(0, 5)}...{t.contract.slice(-4)}</strong>
                </span>
                {/* SOCIAL PROOF ICONS */}
                <div className="flex items-center gap-1 shrink-0 border-l border-obsidian-800 pl-1.5">
                  {t.website_url && (
                    <a
                      href={t.website_url}
                      target="_blank"
                      rel="noreferrer"
                      className="px-1 py-0.2 rounded bg-cyan-500/15 text-cyan-300 hover:bg-cyan-500/30 border border-cyan-500/30 text-[9px] font-bold"
                      title={`Website Resmi: ${t.website_url}`}
                    >
                      🌐 Web
                    </a>
                  )}
                  {t.twitter_url && (
                    <a
                      href={t.twitter_url}
                      target="_blank"
                      rel="noreferrer"
                      className="px-1 py-0.2 rounded bg-sky-500/15 text-sky-300 hover:bg-sky-500/30 border border-sky-500/30 text-[9px] font-bold"
                      title={`Twitter / X: ${t.twitter_url}`}
                    >
                      𝕏
                    </a>
                  )}
                  {t.telegram_url && (
                    <a
                      href={t.telegram_url}
                      target="_blank"
                      rel="noreferrer"
                      className="px-1 py-0.2 rounded bg-indigo-500/15 text-indigo-300 hover:bg-indigo-500/30 border border-indigo-500/30 text-[9px] font-bold"
                      title={`Telegram: ${t.telegram_url}`}
                    >
                      ✈️ TG
                    </a>
                  )}
                  {!t.website_url && !t.twitter_url && !t.telegram_url && (
                    <span
                      className={`px-1 py-0.2 rounded text-[9px] ${
                        t.has_socials
                          ? 'bg-emerald-500/10 text-emerald-300 border border-emerald-500/20'
                          : 'bg-amber-500/10 text-amber-300/80 border border-amber-500/20'
                      }`}
                      title={t.has_socials ? 'Komunitas / Socials Terdeteksi' : 'Belum ada metadata link sosial di DexScreener'}
                    >
                      {t.has_socials ? '🔗 Socials ✓' : '⚠️ No Socials'}
                    </span>
                  )}
                </div>
              </div>
              <button
                type="button"
                onClick={() => handleCopyText(t.contract, `ca-${cardKey}`, t)}
                className={`px-1.5 py-0.5 rounded text-[10px] font-bold font-mono transition flex items-center gap-1 shrink-0 ${
                  isCaCopied
                    ? 'bg-emerald-500 text-obsidian-950'
                    : 'bg-obsidian-900 hover:bg-obsidian-850 text-amber-300 border border-obsidian-750'
                }`}
                title="Salin Alamat Mint Koin (Token CA)"
              >
                <LucideIcon name={isCaCopied ? 'check' : 'copy'} className="w-2.5 h-2.5" />
                <span>{isCaCopied ? '✓' : 'CA'}</span>
              </button>
            </div>
          )}

          {/* PRICE & MULTI-TIMEFRAME MOMENTUM STRIP (1M, 5M, 1H, 24H) */}
          <div className="p-2 rounded-xl bg-obsidian-950/70 border border-obsidian-800 space-y-1.5">
            <div className="flex items-baseline justify-between">
              <div>
                <span className="text-[9px] text-slate-500 block font-mono">HARGA LIVE</span>
                <div className="text-sm font-black font-mono text-white">{formatUsd(t.price)}</div>
              </div>
              <div className="text-right">
                <span className="text-[9px] text-slate-500 block font-mono">ESTIMASI IDR</span>
                <div className="text-xs font-mono font-bold text-emerald-400">≈ {formatIdr(t.price * usdIdr)}</div>
              </div>
            </div>

            {/* 4-TIMEFRAME MOMENTUM CELLS */}
            <div className="grid grid-cols-4 gap-1 pt-1 border-t border-obsidian-800/80 text-[9px] font-mono text-center">
              {[
                { label: '1m', val: chg1m },
                { label: '5m', val: chg5m },
                { label: '1h', val: chg1h },
                { label: '24h', val: chg24h },
              ].map((tf) => {
                const v = Number(tf.val || 0);
                const isPos = v >= 0;
                return (
                  <div
                    key={tf.label}
                    className={`py-0.5 px-1 rounded border ${
                      isPos
                        ? 'bg-emerald-500/10 border-emerald-500/25 text-emerald-300'
                        : 'bg-rose-500/10 border-rose-500/25 text-rose-300'
                    }`}
                  >
                    <span className="text-slate-400 block text-[8px]">{tf.label}</span>
                    <span className="font-bold">
                      {isPos ? '+' : ''}
                      {v.toFixed(1)}%
                    </span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* ORDERFLOW BUY vs SELL PRESSURE VISUAL BAR */}
          <div className="p-2 rounded-xl bg-obsidian-950/80 border border-obsidian-800 space-y-1 font-mono text-[10px]">
            <div className="flex items-center justify-between">
              <span className="text-emerald-400 font-bold">
                🟢 Buy {buyPressurePct.toFixed(0)}% ({buys5m})
              </span>
              <span className="text-[9px] text-slate-300 font-bold">
                {netBuys5m >= 0 ? `Net +${netBuys5m} Beli` : `Net ${netBuys5m} Jual`} · ~${avgTxUsd}/tx
              </span>
              <span className="text-rose-400 font-bold">
                ({sells5m}) {sellPressurePct.toFixed(0)}% Sell 🔴
              </span>
            </div>
            <div className="w-full h-1.5 rounded-full bg-rose-500/40 overflow-hidden flex">
              <div
                className="h-full bg-emerald-400 transition-all duration-300"
                style={{ width: `${Math.min(100, Math.max(5, buyPressurePct))}%` }}
              />
            </div>
          </div>

          {/* BONDING CURVE PROGRESS & DISTANCE TO GRADUATION */}
          <div className="space-y-1 px-0.5">
            <div className="flex justify-between items-center text-[10px] font-mono">
              <span className="text-slate-400">
                {curvePct >= 100 ? '🎓 Pool AMM / Lulus Migrasi' : '💊 Progres Bonding Curve'}
              </span>
              <div className="flex items-center gap-1.5">
                {mcapToGrad > 0 && (
                  <span className="text-[9px] text-amber-300" title="Sisa Market Cap menuju migrasi otomatis Raydium ($69K)">
                    (-${(mcapToGrad / 1000).toFixed(1)}K ke Grad)
                  </span>
                )}
                <span className="text-cyan-300 font-bold">{curvePct}%</span>
              </div>
            </div>
            <div className="w-full h-1.5 rounded-full bg-obsidian-950 border border-obsidian-800 overflow-hidden">
              <div
                className={`h-full transition-all duration-300 ${
                  curvePct >= 85
                    ? 'bg-gradient-to-r from-amber-400 via-pink-500 to-purple-400'
                    : 'bg-gradient-to-r from-cyan-500 to-emerald-400'
                }`}
                style={{ width: `${Math.min(100, Math.max(0, curvePct))}%` }}
              />
            </div>
          </div>

          {/* KEY FINANCIAL & VELOCITY METRICS GRID */}
          <div className="grid grid-cols-3 gap-1.5 p-2 rounded-xl bg-obsidian-950/80 border border-obsidian-800 text-[10px] font-mono">
            <div>
              <span className="text-slate-500 block text-[9px]">MCAP</span>
              <span className="text-white font-bold">${((t.market_cap || 0) / 1000).toFixed(1)}K</span>
              <span className="text-[9px] text-slate-400 block truncate">
                ≈ {formatIdr((t.market_cap || 0) * usdIdr)}
              </span>
            </div>
            <div>
              <span className="text-slate-500 block text-[9px]">LIKUIDITAS</span>
              <span className="text-white font-bold">${((t.liquidity || 0) / 1000).toFixed(1)}K</span>
              <span
                className={`text-[9px] block font-bold ${
                  liqMcapPct >= 10 ? 'text-emerald-400' : liqMcapPct >= 5 ? 'text-amber-300' : 'text-rose-400'
                }`}
                title="Rasio Likuiditas terhadap Market Cap (Sehat: ≥10%)"
              >
                Liq/MC: {liqMcapPct}%
              </span>
            </div>
            <div>
              <span className="text-slate-500 block text-[9px]">5M VOL &amp; TURN</span>
              <span className="text-cyan-300 font-bold">${((t.volume_5m || 0) / 1000).toFixed(1)}K</span>
              <span
                className={`text-[9px] block font-bold ${
                  volLiqPct >= 12 ? 'text-amber-300' : 'text-cyan-400'
                }`}
                title="Perputaran Volume 5m terhadap Likuiditas (Velocity)"
              >
                Turn: {volLiqPct}%
              </span>
            </div>
          </div>

          {/* HOLDER & INSIDER RISK DISTRIBUTION STRIP */}
          <div className="grid grid-cols-4 gap-1 p-1.5 rounded-xl bg-obsidian-950/60 border border-obsidian-850 text-[9px] font-mono text-center">
            <div title="Estimasi jumlah pemegang token aktif">
              <span className="text-slate-500 block text-[8px]">HOLDERS</span>
              <span className="text-white font-bold">👥 {holdersCount}</span>
            </div>
            <div title="Persentase kepemilikan 10 dompet terbesar (Aman ≤20%)">
              <span className="text-slate-500 block text-[8px]">TOP 10</span>
              <span className={`font-bold ${top10Pct <= 20 ? 'text-emerald-400' : 'text-amber-300'}`}>
                {top10Pct}%
              </span>
            </div>
            <div title="Persentase token yang masih dipegang Developer (Aman ≤2%)">
              <span className="text-slate-500 block text-[8px]">DEV HOLD</span>
              <span className={`font-bold ${devPct <= 2 ? 'text-emerald-400' : devPct <= 5 ? 'text-amber-300' : 'text-rose-400'}`}>
                {devPct <= 0.1 ? '0% SAFU' : `${devPct}%`}
              </span>
            </div>
            <div title="Persentase supply yang dibeli oleh bundler saat peluncuran">
              <span className="text-slate-500 block text-[8px]">BUNDLE</span>
              <span className={`font-bold ${bundlePct <= 3 ? 'text-emerald-400' : 'text-amber-300'}`}>
                {bundlePct}%
              </span>
            </div>
          </div>

          {/* SUGGESTED SNIPER TRADING PLAN (TP / SL / R:R / SLIPPAGE) */}
          <div className="flex flex-wrap items-center justify-between gap-1 px-2 py-1 rounded-lg bg-emerald-950/20 border border-emerald-500/25 text-[9px] font-mono">
            <span className="text-emerald-300 font-bold" title="Rekomendasi Target Take Profit">
              🎯 TP: +{tpPct}%
            </span>
            <span className="text-rose-300 font-bold" title="Rekomendasi Batas Stop Loss">
              🛑 SL: -{slPct}%
            </span>
            <span className="text-amber-300 font-bold" title="Rasio Risk : Reward">
              ⚖️ R:R {rrRatio}
            </span>
            <span className="text-cyan-300" title="Estimasi Price Impact untuk entry $10 USD">
              💧 Impact: ~{priceImpact10Usd}%
            </span>
          </div>

          {/* ON-CHAIN SIGNALS & SMART MONEY TAGS */}
          <div className="flex flex-wrap items-center gap-1 text-[9px] font-mono">
            {t.gmgn_smart_degens !== undefined && t.gmgn_smart_degens > 0 && (
              <span className="px-1.5 py-0.5 rounded bg-purple-500/15 text-purple-300 border border-purple-500/30 font-bold">
                🧠 Smart Money: {t.gmgn_smart_degens}W
              </span>
            )}
            {t.mint_revoked && (
              <span className="px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">
                ✓ Mint Revoked
              </span>
            )}
            {t.lp_burned && (
              <span className="px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">
                ✓ LP Lock/Burn
              </span>
            )}
          </div>
        </div>

        {/* BOTTOM ACTION SECTION: SALIN CA, AUDIT SHIELD & LINK AUTO ENTRY */}
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
              title="Salin Mint Contract Address (CA) Base58 asli (Siap di-paste ke Pump.fun / DEX)"
            >
              <LucideIcon name={isCardCaCopied ? 'check' : 'copy'} className="w-3.5 h-3.5" />
              <span>{isCardCaCopied ? '✓ CA Tersalin' : 'Salin CA'}</span>
            </button>

            <Link
              href={`/rugcheck?q=${encodeURIComponent(t.contract || t.symbol)}`}
              className="px-2.5 py-2 rounded-xl bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-mono text-xs font-bold transition flex items-center gap-1 shrink-0"
              title="Audit Keamanan Kontrak & 5 Pilar Pump.fun"
            >
              <LucideIcon name="shield-alert" className="w-3.5 h-3.5 text-emerald-400" />
              <span>Audit</span>
            </Link>

            <button
              type="button"
              disabled={executingCardKey === cardKey || !t.contract}
              onClick={() => handleQuickEntry1Dollar(t)}
              className={`px-2.5 py-2 rounded-xl font-mono text-xs font-extrabold transition flex items-center gap-1 shrink-0 shadow-sm ${
                executingCardKey === cardKey
                  ? 'bg-amber-500/30 text-amber-200 border border-amber-400/50 cursor-wait'
                  : 'bg-amber-400 hover:bg-amber-300 text-obsidian-950 border border-amber-300 shadow-amber-400/20'
              }`}
              title="1-Klik Auto Entry $1.00 USD (1 Dolar) pada koin ini"
            >
              <LucideIcon name="zap" className="w-3.5 h-3.5" />
              <span>{executingCardKey === cardKey ? 'Entry $1...' : '⚡ Entry $1'}</span>
            </button>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-1.5 text-[11px] font-mono pt-0.5">
            <div className="flex flex-wrap items-center gap-1.5">
              {t.dex_url && (
                <a
                  href={t.dex_url}
                  target="_blank"
                  rel="noreferrer"
                  className="px-2 py-1 rounded-lg bg-obsidian-950 hover:bg-obsidian-800 text-cyan-300 border border-obsidian-800 inline-flex items-center gap-1 transition"
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
                  className="px-2 py-1 rounded-lg bg-obsidian-950 hover:bg-obsidian-800 text-emerald-400 border border-obsidian-800 inline-flex items-center gap-1 transition"
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
                className="px-2 py-1 rounded-lg bg-purple-500/15 hover:bg-purple-500/25 text-purple-300 border border-purple-500/30 transition inline-flex items-center gap-1 text-[10px] font-bold"
              >
                <span>💊 Pump.fun</span>
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
        <title>Trenches &amp; Pulse Radar | Sofia Market 4.1.3</title>
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
          <div className="flex flex-wrap items-center gap-1.5 sm:gap-2 text-xs font-mono">
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

            {copiedAddresses.length > 0 && (
              <button
                type="button"
                onClick={handleResetCopied}
                className="sm:hidden px-2 py-1 rounded-lg bg-amber-500/15 hover:bg-amber-500/25 text-amber-300 border border-amber-500/30 text-[10px] font-bold flex items-center gap-1 transition"
                title="Reset wallet/CA yang sudah disalin"
              >
                <span>👁️ Reset ({copiedAddresses.length})</span>
              </button>
            )}

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

            {/* VERIFIED COIN GUARANTEE BADGE */}
            <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 flex items-center gap-1 shadow-sm" title="Semua token yang dipindai dipastikan 100% merupakan Koin / Token Mint (bukan pair pool kosong atau koin stabil)">
              <span>🪙 100% KOIN VERIFIED</span>
            </span>

            {/* LINK KE MENU AUTO ENTRY UNTUK SNIPING */}
            <Link
              href="/auto-entry"
              className="px-2.5 py-1 rounded-lg border border-amber-500/40 bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 font-mono text-xs font-bold transition flex items-center gap-1.5"
              title="Buka menu Auto Entry Bot untuk mengeksekusi sniper token"
            >
              <LucideIcon name="target" className="w-3.5 h-3.5 text-amber-400" />
              <span>Auto Entry ↗</span>
            </Link>
          </div>
        </div>

        {/* 1-CLICK $1 AUTO ENTRY FEEDBACK BANNER */}
        {entryNotice && (
          <div
            className={`px-3.5 py-2.5 rounded-xl text-xs font-mono flex items-center justify-between gap-2 shadow-lg transition-all ${
              entryNotice.type === 'ok'
                ? 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30'
                : 'bg-rose-500/15 text-rose-300 border border-rose-500/30'
            }`}
          >
            <div className="flex items-center gap-2">
              <LucideIcon name={entryNotice.type === 'ok' ? 'check' : 'alert-circle'} className="w-4 h-4 shrink-0" />
              <span>{entryNotice.text}</span>
            </div>
            <Link href="/auto-entry" className="text-[11px] font-bold underline hover:text-white shrink-0">
              Lihat Riwayat Entry →
            </Link>
          </div>
        )}

        {/* DEX / PLATFORM FILTER BUTTONS FOR SCAN ACCURACY */}
        <div className="bg-obsidian-900/95 border border-obsidian-800 p-2.5 rounded-2xl flex flex-col md:flex-row md:items-center justify-between gap-2.5 shadow-md">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-[11px] font-mono text-slate-400 font-bold uppercase mr-1 flex items-center gap-1">
              <span>🎯 Filter Scan DEX:</span>
            </span>

            <button
              type="button"
              onClick={() => setPlatformFilter('ALL')}
              className={`px-3 py-1.5 rounded-xl text-xs font-mono font-bold transition flex items-center gap-1.5 ${
                platformFilter === 'ALL'
                  ? 'bg-amber-400 text-obsidian-950 shadow-md font-black'
                  : 'bg-obsidian-950 text-slate-300 hover:text-white border border-obsidian-800'
              }`}
            >
              <span>Semua DEX</span>
              <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-obsidian-900/70 text-current">
                {totalRawCount}
              </span>
            </button>

            <button
              type="button"
              onClick={() => setPlatformFilter('PUMP_FUN')}
              className={`px-3 py-1.5 rounded-xl text-xs font-mono font-bold transition flex items-center gap-1.5 ${
                platformFilter === 'PUMP_FUN'
                  ? 'bg-gradient-to-r from-pink-500 to-rose-500 text-white shadow-md shadow-pink-500/25 font-black ring-1 ring-pink-300'
                  : 'bg-obsidian-950 text-pink-300 hover:bg-pink-950/30 border border-pink-500/40'
              }`}
            >
              <span>💊 Khusus Pump.fun</span>
              <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-pink-950/80 text-pink-200">
                {pumpFunScanCount}
              </span>
            </button>

            <button
              type="button"
              onClick={() => setPlatformFilter('RAYDIUM')}
              className={`px-3 py-1.5 rounded-xl text-xs font-mono font-bold transition flex items-center gap-1.5 ${
                platformFilter === 'RAYDIUM'
                  ? 'bg-gradient-to-r from-cyan-500 to-blue-500 text-obsidian-950 shadow-md shadow-cyan-500/25 font-black ring-1 ring-cyan-300'
                  : 'bg-obsidian-950 text-cyan-300 hover:bg-cyan-950/30 border border-cyan-500/40'
              }`}
            >
              <span>⚡ Khusus Raydium</span>
              <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-cyan-950/80 text-cyan-200">
                {raydiumScanCount}
              </span>
            </button>

            <button
              type="button"
              onClick={() => setPlatformFilter('OTHER')}
              className={`px-3 py-1.5 rounded-xl text-xs font-mono font-bold transition flex items-center gap-1.5 ${
                platformFilter === 'OTHER'
                  ? 'bg-indigo-500 text-white shadow-md font-black ring-1 ring-indigo-300'
                  : 'bg-obsidian-950 text-indigo-300 hover:bg-indigo-950/30 border border-indigo-500/40'
              }`}
            >
              <span>🌐 DEX Lainnya</span>
              <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-indigo-950/80 text-indigo-200">
                {otherScanCount}
              </span>
            </button>
          </div>

          <div className="text-[11px] font-mono text-slate-400">
            {platformFilter === 'PUMP_FUN' && (
              <span className="text-pink-300 font-bold">💊 Menampilkan hanya koin Pump.fun (Bonding Curve / CA: ...pump)</span>
            )}
            {platformFilter === 'RAYDIUM' && (
              <span className="text-cyan-300 font-bold">⚡ Menampilkan hanya koin yang terdaftar di pool Raydium AMM</span>
            )}
            {platformFilter === 'OTHER' && (
              <span className="text-indigo-300 font-bold">🌐 Menampilkan koin multi-DEX (Moonshot, Orca, Meteora)</span>
            )}
            {platformFilter === 'ALL' && (
              <span>Memindai seluruh DEX Solana &amp; tren pasar secara realtime</span>
            )}
          </div>
        </div>

        {/* TRENCH PROFITABILITY TELEMETRY OVERVIEW STRIP (4 ACTIONABLE CARDS) */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-2.5">
          <div className="bg-obsidian-900/95 border border-amber-500/30 rounded-xl p-2.5 flex items-center justify-between shadow-sm">
            <div>
              <div className="text-[10px] font-mono text-amber-300 font-bold uppercase flex items-center gap-1">
                <span>🔥 Sinyal Golden Snipe</span>
              </div>
              <div className="text-base font-black font-mono text-white mt-0.5">
                {trenchInsights.goldenSnipeCount} Koin Potensial
              </div>
              <div className="text-[10px] font-mono text-slate-400">
                Top Kandidat: <strong className="text-emerald-300">{trenchInsights.topSnipeSymbol}</strong>
              </div>
            </div>
            <div className="w-8 h-8 rounded-lg bg-amber-500/15 border border-amber-500/30 flex items-center justify-center text-amber-300 font-mono text-sm">
              🎯
            </div>
          </div>

          <div className="bg-obsidian-900/95 border border-emerald-500/30 rounded-xl p-2.5 flex items-center justify-between shadow-sm">
            <div>
              <div className="text-[10px] font-mono text-emerald-300 font-bold uppercase flex items-center gap-1">
                <span>🟢 Dominasi Orderflow 5m</span>
              </div>
              <div className="text-base font-black font-mono text-white mt-0.5">
                {trenchInsights.avgBuyPressure}% Buy Pressure
              </div>
              <div className="text-[10px] font-mono text-slate-400">
                Total: <span className="text-emerald-400 font-bold">{trenchInsights.totalBuys5m} Buy</span> vs{' '}
                <span className="text-rose-400 font-bold">{trenchInsights.totalSells5m} Sell</span>
              </div>
            </div>
            <div className="w-8 h-8 rounded-lg bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center text-emerald-300 font-mono text-sm">
              📈
            </div>
          </div>

          <div className="bg-obsidian-900/95 border border-cyan-500/30 rounded-xl p-2.5 flex items-center justify-between shadow-sm">
            <div>
              <div className="text-[10px] font-mono text-cyan-300 font-bold uppercase flex items-center gap-1">
                <span>⚡ Tertinggi Velocity (Vol/Liq)</span>
              </div>
              <div className="text-base font-black font-mono text-white mt-0.5 truncate max-w-[160px]">
                {trenchInsights.fastestVelocityToken
                  ? `${trenchInsights.fastestVelocityToken.symbol.split('/')[0]} (${trenchInsights.fastestVelocityToken.calc_vel_pct}%)`
                  : '—'}
              </div>
              <div className="text-[10px] font-mono text-slate-400">
                Vol 5m: ${((trenchInsights.fastestVelocityToken?.volume_5m || 0) / 1000).toFixed(1)}K
              </div>
            </div>
            <div className="w-8 h-8 rounded-lg bg-cyan-500/15 border border-cyan-500/30 flex items-center justify-center text-cyan-300 font-mono text-sm">
              ⚡
            </div>
          </div>

          <div className="bg-obsidian-900/95 border border-purple-500/30 rounded-xl p-2.5 flex items-center justify-between shadow-sm">
            <div>
              <div className="text-[10px] font-mono text-purple-300 font-bold uppercase flex items-center gap-1">
                <span>🚀 Mendekati Migrasi AMM</span>
              </div>
              <div className="text-base font-black font-mono text-white mt-0.5 truncate max-w-[160px]">
                {trenchInsights.closestGradToken
                  ? `${trenchInsights.closestGradToken.symbol.split('/')[0]} (${trenchInsights.closestGradToken.bonding_curve_pct}%)`
                  : '—'}
              </div>
              <div className="text-[10px] font-mono text-slate-400">
                Target Lulus: $69.0K MCap
              </div>
            </div>
            <div className="w-8 h-8 rounded-lg bg-purple-500/15 border border-purple-500/30 flex items-center justify-center text-purple-300 font-mono text-sm">
              🎓
            </div>
          </div>
        </div>

        {/* COMPACT MINIMALIST TAB BAR & FILTERS */}
        <div className="bg-obsidian-900/90 border border-obsidian-800 rounded-xl p-2 shadow-sm space-y-2">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-2">
            {/* CATEGORY TABS */}
            <div className="flex items-center gap-1 overflow-x-auto no-scrollbar pb-0.5 md:pb-0">
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

            {/* SEARCH, SORT & SHIELD FILTER */}
            <div className="flex flex-wrap items-center gap-2">
              <div className="relative w-full sm:w-44">
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

              {/* SORT SELECTOR */}
              <div className="flex items-center gap-1 text-[11px] font-mono">
                <span className="text-slate-500 hidden sm:inline">Urutkan:</span>
                <select
                  value={sortBy}
                  onChange={(e) => setSortBy(e.target.value as any)}
                  className="px-2 py-1 rounded-lg bg-obsidian-950 border border-obsidian-800 text-cyan-300 font-mono text-[11px] font-bold focus:outline-none focus:border-cyan-400"
                >
                  <option value="AI_SCORE">🎯 Skor Profit AI</option>
                  <option value="BUY_PRESSURE">🟢 Buy Pressure 5m %</option>
                  <option value="VELOCITY">⚡ Velocity (Vol/Liq)</option>
                  <option value="MOMENTUM_5M">🚀 Kenaikan 5m %</option>
                  <option value="VOLUME_5M">💰 Volume 5m ($)</option>
                  <option value="CURVE_GRAD">🎓 Mendekati Graduate</option>
                  <option value="NEWEST">⏱️ Koin Terbaru</option>
                </select>
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

          {/* SNIPER PROFITABILITY QUICK FILTER PILLS */}
          <div className="flex flex-wrap items-center gap-1.5 pt-1.5 border-t border-obsidian-800/80 text-[11px] font-mono">
            <span className="text-slate-400 font-bold mr-1">⚡ Filter Profit Cepat:</span>

            <button
              type="button"
              onClick={() => setOnlyHighBuyPressure((p) => !p)}
              className={`px-2.5 py-1 rounded-lg border transition flex items-center gap-1 ${
                onlyHighBuyPressure
                  ? 'bg-emerald-500/20 text-emerald-300 border-emerald-400 font-bold shadow-sm'
                  : 'bg-obsidian-950 text-slate-400 hover:text-white border-obsidian-800'
              }`}
              title="Hanya tampilkan koin dengan dominasi transaksi beli ≥60% dalam 5 menit terakhir"
            >
              <span>🔥 Buy Pressure ≥60%</span>
            </button>

            <button
              type="button"
              onClick={() => setOnlySweetSpot((p) => !p)}
              className={`px-2.5 py-1 rounded-lg border transition flex items-center gap-1 ${
                onlySweetSpot
                  ? 'bg-amber-500/20 text-amber-300 border-amber-400 font-bold shadow-sm'
                  : 'bg-obsidian-950 text-slate-400 hover:text-white border-obsidian-800'
              }`}
              title="Hanya tampilkan koin di zona akumulasi Bonding Curve 25%–92% sebelum lulus ke Raydium"
            >
              <span>🎯 Zona Sweet Spot (Curve 25–92%)</span>
            </button>

            <button
              type="button"
              onClick={() => setOnlyCleanSupply((p) => !p)}
              className={`px-2.5 py-1 rounded-lg border transition flex items-center gap-1 ${
                onlyCleanSupply
                  ? 'bg-cyan-500/20 text-cyan-300 border-cyan-400 font-bold shadow-sm'
                  : 'bg-obsidian-950 text-slate-400 hover:text-white border-obsidian-800'
              }`}
              title="Hanya tampilkan koin dengan kepemilikan Dev ≤3% dan Top 10 Holder ≤25%"
            >
              <span>🛡️ Clean Supply (Dev ≤3% &amp; Top10 ≤25%)</span>
            </button>

            <button
              type="button"
              onClick={() => setOnlyWithSocials((p) => !p)}
              className={`px-2.5 py-1 rounded-lg border transition flex items-center gap-1 ${
                onlyWithSocials
                  ? 'bg-purple-500/20 text-purple-300 border-purple-400 font-bold shadow-sm'
                  : 'bg-obsidian-950 text-slate-400 hover:text-white border-obsidian-800'
              }`}
              title="Hanya tampilkan koin yang memiliki identitas komunitas / link sosial"
            >
              <span>🔗 Punya Socials</span>
            </button>

            {(onlyHighBuyPressure || onlySweetSpot || onlyCleanSupply || onlyWithSocials || minSafety > 0 || platformFilter !== 'ALL') && (
              <button
                type="button"
                onClick={() => {
                  setOnlyHighBuyPressure(false);
                  setOnlySweetSpot(false);
                  setOnlyCleanSupply(false);
                  setOnlyWithSocials(false);
                  setMinSafety(0);
                  setPlatformFilter('ALL');
                  setSortBy('AI_SCORE');
                }}
                className="px-2 py-1 rounded-lg bg-rose-500/15 hover:bg-rose-500/25 text-rose-300 border border-rose-500/30 text-[10px] font-bold ml-auto"
              >
                ✕ Reset Filter
              </button>
            )}
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
