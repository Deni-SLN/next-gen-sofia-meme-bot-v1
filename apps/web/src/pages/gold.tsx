import React, { useState, useEffect, useMemo } from 'react';
import Head from 'next/head';
import { api, formatIdr, formatUsd } from '@/lib/api';
import { LucideIcon } from '@/components/LucideIcon';

const QUICK_WEIGHTS = [0.5, 1, 2, 5, 10, 25, 50, 100];
const BRAND_OPTIONS = [
  { id: 'Antam', label: 'Antam CertiEye (Fisik)' },
  { id: 'UBS', label: 'UBS Gold (Fisik)' },
  { id: 'Galeri24', label: 'Galeri 24 Pegadaian (Fisik)' },
  { id: 'Digital', label: 'Emas Digital (Pegadaian/Pluang/Treasury)' },
];

export default function GoldPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [error, setError] = useState<string>('');
  const [notice, setNotice] = useState<string>('');

  // Form state: Add Manual Gold Portfolio
  const [brand, setBrand] = useState<string>('Antam');
  const [weightGrams, setWeightGrams] = useState<string>('5');
  const [costMode, setCostMode] = useState<'per_gram' | 'total'>('per_gram');
  const [buyPricePerGram, setBuyPricePerGram] = useState<string>('');
  const [totalCostInput, setTotalCostInput] = useState<string>('');
  const [label, setLabel] = useState<string>('');
  const [purchasedAt, setPurchasedAt] = useState<string>(() => new Date().toISOString().slice(0, 10));
  const [notes, setNotes] = useState<string>('');
  const [submitting, setSubmitting] = useState<boolean>(false);

  // Card Simulasi Jual Sekarang (Buyback, Spread & Pajak) state
  const [simSource, setSimSource] = useState<'portfolio' | 'custom'>('portfolio');
  const [simWeightGrams, setSimWeightGrams] = useState<number>(5);
  const [simTotalCostIdr, setSimTotalCostIdr] = useState<number>(7500000);
  const [simRetailPricePerGram, setSimRetailPricePerGram] = useState<number>(1700000);
  const [simSpreadPct, setSimSpreadPct] = useState<number>(9.0);
  const [simTaxMode, setSimTaxMode] = useState<'auto_npwp' | 'auto_non_npwp' | 'zero' | 'custom'>('auto_npwp');
  const [simCustomTaxPct, setSimCustomTaxPct] = useState<number>(1.5);
  const [simIncludeStampDuty, setSimIncludeStampDuty] = useState<boolean>(true);

  const loadGoldDashboard = async (forceRefresh: boolean = false) => {
    if (forceRefresh) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    setError('');
    try {
      const res = await api.getGoldDashboard(forceRefresh);
      setData(res);

      const antamBuy = Number(res?.market?.antam?.buy_price_idr || 1700000);
      if (!buyPricePerGram) {
        setBuyPricePerGram(String(antamBuy));
        setTotalCostInput(String(Math.round(antamBuy * ( parseFloat(weightGrams) || 1 ))));
      }

      const pWeight = Number(res?.portfolio?.total_weight_grams || 0);
      const pCost = Number(res?.portfolio?.total_cost_idr || 0);
      if (pWeight > 0) {
        setSimSource('portfolio');
        setSimWeightGrams(pWeight);
        setSimTotalCostIdr(pCost);
        setSimRetailPricePerGram(antamBuy);
      } else {
        setSimSource('custom');
        setSimRetailPricePerGram(antamBuy);
        setSimTotalCostIdr(Math.round(antamBuy * 5 * 0.92)); // default contoh beli 8% lebih murah dulu
      }
    } catch (err: any) {
      setError(err?.message || 'Gagal memuat harga emas dan portofolio.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadGoldDashboard(false);
  }, []);

  const market = data?.market || {};
  const portfolio = data?.portfolio || {};
  const holdings: any[] = data?.holdings || [];

  // Keep portfolio simulation synced when simSource === 'portfolio'
  useEffect(() => {
    if (simSource === 'portfolio' && Number(portfolio?.total_weight_grams || 0) > 0) {
      setSimWeightGrams(Number(portfolio.total_weight_grams));
      setSimTotalCostIdr(Number(portfolio.total_cost_idr));
      const avgRetail =
        Number(portfolio.total_retail_value_idr || 0) / Number(portfolio.total_weight_grams || 1);
      if (avgRetail > 0) {
        setSimRetailPricePerGram(Math.round(avgRetail));
      }
    }
  }, [simSource, portfolio?.total_weight_grams, portfolio?.total_cost_idr, portfolio?.total_retail_value_idr]);

  const handleUseCurrentBrandPrice = (targetBrand: string) => {
    if (!market?.antam) return;
    const b = targetBrand.toLowerCase();
    let price = Number(market.antam.buy_price_idr || 0);
    if (b.includes('ubs')) price = Number(market.ubs?.buy_price_idr || price);
    else if (b.includes('galeri')) price = Number(market.galeri24?.buy_price_idr || price);
    else if (b.includes('digital')) price = Number(market.digital?.buy_price_idr || price);

    setBuyPricePerGram(String(price));
    const w = parseFloat(weightGrams) || 1;
    setTotalCostInput(String(Math.round(price * w)));
  };

  const handleAddHolding = async (e: React.FormEvent) => {
    e.preventDefault();
    const w = parseFloat(weightGrams);
    if (!w || w <= 0) {
      setError('Masukkan berat emas (gram) lebih dari 0.');
      return;
    }
    setSubmitting(true);
    setError('');
    try {
      const payload: any = {
        weight_grams: w,
        brand,
        label: label.trim() || `Emas ${brand} ${w}g`,
        purchased_at: purchasedAt,
        notes: notes.trim(),
      };
      if (costMode === 'per_gram') {
        payload.buy_price_per_gram_idr = parseFloat(buyPricePerGram) || 0;
      } else {
        payload.total_cost_idr = parseFloat(totalCostInput) || 0;
      }
      const res = await api.addGoldHolding(payload);
      setData(res);
      setSimSource('portfolio');
      setLabel('');
      setNotes('');
      setNotice(`✅ Berhasil menambahkan ${w} gram Emas ${brand} ke Portofolio Anda!`);
      setTimeout(() => setNotice(''), 4000);
    } catch (err: any) {
      setError(err?.message || 'Gagal menyimpan portofolio emas.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteHolding = async (id: number, itemLabel: string) => {
    try {
      const res = await api.deleteGoldHolding(id);
      setData(res);
      setNotice(`🗑️ Kepingan "${itemLabel}" berhasil dihapus dari portofolio.`);
      setTimeout(() => setNotice(''), 3500);
    } catch (err: any) {
      setError(err?.message || 'Gagal menghapus data emas.');
    }
  };

  const handleSimulateSingleHolding = (h: any) => {
    setSimSource('custom');
    setSimWeightGrams(Number(h.weight_grams || 1));
    setSimTotalCostIdr(Number(h.total_cost_idr || 0));
    setSimRetailPricePerGram(Number(h.current_retail_per_gram_idr || market?.antam?.buy_price_idr || 1700000));
    const b = String(h.brand || '').toLowerCase();
    if (b.includes('digital')) setSimSpreadPct(3.0);
    else if (b.includes('ubs') || b.includes('galeri')) setSimSpreadPct(8.5);
    else setSimSpreadPct(9.0);
    setNotice(`🧮 Simulasi Jual Sekarang diatur untuk kepingan: ${h.label} (${h.weight_grams}g)`);
    setTimeout(() => setNotice(''), 3500);
  };

  // Real-time client-side calculation for Card Simulasi Jual Sekarang
  const simResult = useMemo(() => {
    const w = Math.max(0, Number(simWeightGrams || 0));
    const cost = Math.max(0, Number(simTotalCostIdr || 0));
    const retailPerGram = Math.max(0, Number(simRetailPricePerGram || 0));
    const spreadPct = Math.max(0, Math.min(50, Number(simSpreadPct || 0)));

    const grossRetailIdr = Math.round(w * retailPerGram);
    const spreadDeductionIdr = Math.round(grossRetailIdr * (spreadPct / 100));
    const effectiveBuybackPerGram = Math.round(retailPerGram * (1 - spreadPct / 100));
    const grossBuybackIdr = Math.max(0, grossRetailIdr - spreadDeductionIdr);

    let appliedTaxPct = 0;
    let taxLabel = '';
    if (simTaxMode === 'zero') {
      appliedTaxPct = 0;
      taxLabel = 'Tanpa Potongan Pajak (0%)';
    } else if (simTaxMode === 'custom') {
      appliedTaxPct = Math.max(0, Number(simCustomTaxPct || 0));
      taxLabel = `Pajak Kustom (${appliedTaxPct.toFixed(2)}%)`;
    } else {
      const hasNpwp = simTaxMode === 'auto_npwp';
      if (grossBuybackIdr > 10_000_000) {
        appliedTaxPct = hasNpwp ? 1.5 : 3.0;
        taxLabel = `PPh 22 Buyback > Rp 10 Juta (${appliedTaxPct}% ${hasNpwp ? 'NPWP' : 'Non-NPWP'})`;
      } else {
        appliedTaxPct = 0;
        taxLabel = 'Bebas PPh 22 (Buyback ≤ Rp 10 Juta)';
      }
    }

    const taxDeductionIdr = Math.round(grossBuybackIdr * (appliedTaxPct / 100));
    const stampDutyIdr = simIncludeStampDuty && grossBuybackIdr > 5_000_000 ? 10_000 : 0;
    const totalDeductionsIdr = spreadDeductionIdr + taxDeductionIdr + stampDutyIdr;
    const netPayoutIdr = Math.max(0, grossBuybackIdr - taxDeductionIdr - stampDutyIdr);

    const netPnlIdr = Math.round(netPayoutIdr - cost);
    const netPnlPct = cost > 0 ? Number(((netPnlIdr / cost) * 100).toFixed(2)) : 0;

    const marketPnlIdr = Math.round(grossRetailIdr - cost);
    const marketPnlPct = cost > 0 ? Number(((marketPnlIdr / cost) * 100).toFixed(2)) : 0;

    const taxFactor = 1 - appliedTaxPct / 100;
    const requiredGrossBuyback = taxFactor > 0 ? (cost + stampDutyIdr) / taxFactor : cost;
    const breakevenBuybackPerGram = w > 0 ? Math.round(requiredGrossBuyback / w) : 0;
    const breakevenRetailPerGram =
      w > 0 && 1 - spreadPct / 100 > 0
        ? Math.round(breakevenBuybackPerGram / (1 - spreadPct / 100))
        : 0;

    const status = netPnlIdr > 0 ? 'UNTUNG' : netPnlIdr < 0 ? 'RUGI' : 'IMPAS';

    return {
      w,
      cost,
      retailPerGram,
      effectiveBuybackPerGram,
      grossRetailIdr,
      spreadPct,
      spreadDeductionIdr,
      grossBuybackIdr,
      appliedTaxPct,
      taxLabel,
      taxDeductionIdr,
      stampDutyIdr,
      totalDeductionsIdr,
      netPayoutIdr,
      netPnlIdr,
      netPnlPct,
      marketPnlIdr,
      marketPnlPct,
      breakevenBuybackPerGram,
      breakevenRetailPerGram,
      status,
    };
  }, [
    simWeightGrams,
    simTotalCostIdr,
    simRetailPricePerGram,
    simSpreadPct,
    simTaxMode,
    simCustomTaxPct,
    simIncludeStampDuty,
  ]);

  const history30d: any[] = market?.history_30d || [];
  const maxHistPrice = useMemo(() => {
    if (!history30d.length) return 1;
    return Math.max(...history30d.map((p) => Number(p.antam_buy_idr || 0)));
  }, [history30d]);
  const minHistPrice = useMemo(() => {
    if (!history30d.length) return 0;
    return Math.min(...history30d.map((p) => Number(p.antam_buyback_idr || p.antam_buy_idr || 0)));
  }, [history30d]);

  return (
    <>
      <Head>
        <title>Harga Emas Hari Ini &amp; Simulasi Buyback | SOFIA TRENCHES</title>
      </Head>

      <main className="flex-1 overflow-y-auto p-3 sm:p-5 space-y-5 pb-24 md:pb-8">
        {/* TOP HEADER BANNER */}
        <section className="rounded-2xl bg-gradient-to-r from-obsidian-900 via-obsidian-900 to-amber-950/20 border border-obsidian-700 p-4 sm:p-5 shadow-lg">
          <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
            <div className="space-y-1">
              <div className="flex flex-wrap items-center gap-2">
                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-mono font-bold bg-amber-500/20 text-amber-300 border border-amber-500/40">
                  <LucideIcon name="coins" className="w-3.5 h-3.5" />
                  GOLD &amp; LOGAM MULIA TRACKER
                </span>
                <span className="text-[11px] font-mono text-slate-400">
                  Sumber: {market?.source || 'Yahoo Finance Live XAU/USD'} • Kurs $1 = {formatIdr(market?.usd_idr || 16500)}
                </span>
              </div>
              <h1 className="text-lg sm:text-2xl font-extrabold tracking-tight text-white">
                Harga Emas Hari Ini, Portofolio Manual &amp; Kalkulator Buyback
              </h1>
              <p className="text-xs sm:text-sm text-slate-300 max-w-3xl">
                Pantau harga emas dunia (<code className="font-mono text-amber-400">XAU/USD</code>) &amp; estimasi Logam Mulia (Antam, UBS, Galeri 24, Digital), catat kepemilikan emas Anda secara manual, dan hitung simulasi pencairan bersih setelah potongan <strong>Spread</strong> &amp; <strong>Pajak PPh 22</strong>.
              </p>
            </div>

            <div className="flex items-center gap-2 self-start lg:self-center">
              <button
                type="button"
                onClick={() => loadGoldDashboard(true)}
                disabled={refreshing}
                className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border border-amber-500/40 font-mono text-xs font-bold transition"
              >
                <LucideIcon name="rotate-ccw" className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
                <span>{refreshing ? 'Memperbarui Harga...' : 'Refresh Harga Emas'}</span>
              </button>
            </div>
          </div>

          {notice && (
            <div className="mt-3 px-3.5 py-2 rounded-xl bg-emerald-500/15 border border-emerald-500/40 text-emerald-300 text-xs font-mono">
              {notice}
            </div>
          )}
          {error && (
            <div className="mt-3 px-3.5 py-2 rounded-xl bg-rose-500/15 border border-rose-500/40 text-rose-300 text-xs font-mono">
              ⚠️ {error}
            </div>
          )}
        </section>

        {/* SECTION 1: HARGA EMAS HARI INI (4 KARTU UTAMA) */}
        <section className="space-y-2.5">
          <div className="flex items-center justify-between">
            <h2 className="text-xs sm:text-sm font-mono font-extrabold uppercase tracking-wider text-amber-400 flex items-center gap-2">
              <LucideIcon name="coins" className="w-4 h-4" />
              <span>Harga Emas Hari Ini (Live Spot &amp; Logam Mulia Indonesia)</span>
            </h2>
            <span className="text-[11px] font-mono text-slate-400">
              1 Troy Ounce = 31,1035 Gram
            </span>
          </div>

          {loading ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3">
              {[1, 2, 3, 4].map((n) => (
                <div key={n} className="h-32 rounded-2xl bg-obsidian-900 border border-obsidian-800 animate-pulse p-4" />
              ))}
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3">
              {/* Card 1: Harga Beli Emas Antam */}
              <div className="rounded-2xl bg-obsidian-900 border border-amber-500/40 p-4 flex flex-col justify-between shadow-md">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-mono font-bold uppercase text-amber-300 px-2 py-0.5 rounded bg-amber-500/15 border border-amber-500/30">
                    🏅 HARGA BELI ANTAM (1 GRAM)
                  </span>
                  <span
                    className={`text-xs font-mono font-bold px-2 py-0.5 rounded ${
                      Number(market?.antam?.change_idr || 0) >= 0
                        ? 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30'
                        : 'bg-rose-500/15 text-rose-300 border border-rose-500/30'
                    }`}
                  >
                    {Number(market?.antam?.change_idr || 0) >= 0 ? '▲ +' : '▼ '}
                    {formatIdr(market?.antam?.change_idr || 0)}
                  </span>
                </div>
                <div className="my-2">
                  <div className="text-2xl sm:text-3xl font-extrabold font-mono text-white">
                    {formatIdr(market?.antam?.buy_price_idr)}
                  </div>
                  <div className="text-[11px] text-slate-400 mt-0.5">
                    Harga etalase Emas Batangan CertiEye 1g
                  </div>
                </div>
                <div className="pt-2 border-t border-obsidian-800 flex items-center justify-between text-[11px] font-mono">
                  <span className="text-slate-400">UBS 1g: {formatIdr(market?.ubs?.buy_price_idr)}</span>
                  <span className="text-cyan-400">Galeri24: {formatIdr(market?.galeri24?.buy_price_idr)}</span>
                </div>
              </div>

              {/* Card 2: Harga Buyback (Jual Kembali) Antam */}
              <div className="rounded-2xl bg-obsidian-900 border border-emerald-500/30 p-4 flex flex-col justify-between shadow-md">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-mono font-bold uppercase text-emerald-300 px-2 py-0.5 rounded bg-emerald-500/15 border border-emerald-500/30">
                    💵 HARGA BUYBACK ANTAM (1G)
                  </span>
                  <span className="text-[11px] font-mono text-amber-300 px-2 py-0.5 rounded bg-amber-500/15 border border-amber-500/30">
                    Spread -{market?.antam?.spread_pct || 9}%
                  </span>
                </div>
                <div className="my-2">
                  <div className="text-2xl sm:text-3xl font-extrabold font-mono text-emerald-400">
                    {formatIdr(market?.antam?.buyback_price_idr)}
                  </div>
                  <div className="text-[11px] text-slate-400 mt-0.5">
                    Selisih beli vs jual: -{formatIdr(market?.antam?.spread_idr)} / gram
                  </div>
                </div>
                <div className="pt-2 border-t border-obsidian-800 flex items-center justify-between text-[11px] font-mono">
                  <span className="text-slate-400">Buyback UBS:</span>
                  <span className="text-emerald-300 font-semibold">{formatIdr(market?.ubs?.buyback_price_idr)}/g</span>
                </div>
              </div>

              {/* Card 3: Harga Emas Spot Dunia (XAU/USD & IDR/gram) */}
              <div className="rounded-2xl bg-obsidian-900 border border-obsidian-700 p-4 flex flex-col justify-between shadow-md">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-mono font-bold uppercase text-cyan-300 px-2 py-0.5 rounded bg-cyan-500/15 border border-cyan-500/30">
                    🌍 SPOT EMAS DUNIA (XAU)
                  </span>
                  <span
                    className={`text-xs font-mono font-bold px-2 py-0.5 rounded ${
                      Number(market?.change_pct || 0) >= 0
                        ? 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30'
                        : 'bg-rose-500/15 text-rose-300 border border-rose-500/30'
                    }`}
                  >
                    {Number(market?.change_pct || 0) >= 0 ? '+' : ''}
                    {market?.change_pct || 0}%
                  </span>
                </div>
                <div className="my-2">
                  <div className="text-2xl sm:text-3xl font-extrabold font-mono text-white">
                    {formatIdr(market?.spot_idr_per_gram)}
                    <span className="text-xs font-normal text-slate-400"> /gram</span>
                  </div>
                  <div className="text-[11px] text-slate-400 mt-0.5 font-mono">
                    XAU/USD: <strong className="text-amber-300">{formatUsd(market?.xau_usd)}</strong> / oz (
                    {Number(market?.change_usd || 0) >= 0 ? '+' : ''}
                    {formatUsd(market?.change_usd)})
                  </div>
                </div>
                <div className="pt-2 border-t border-obsidian-800 flex items-center justify-between text-[11px] font-mono text-slate-400">
                  <span>Low: {formatUsd(market?.day_low_usd)}</span>
                  <span>High: {formatUsd(market?.day_high_usd)}</span>
                </div>
              </div>

              {/* Card 4: Harga Emas Digital (Spread Rendah) */}
              <div className="rounded-2xl bg-obsidian-900 border border-obsidian-700 p-4 flex flex-col justify-between shadow-md">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-mono font-bold uppercase text-purple-300 px-2 py-0.5 rounded bg-purple-500/15 border border-purple-500/30">
                    📱 EMAS DIGITAL (1 GRAM)
                  </span>
                  <span className="text-[11px] font-mono text-emerald-300 px-2 py-0.5 rounded bg-emerald-500/15 border border-emerald-500/30">
                    Spread ~{market?.digital?.spread_pct || 3}%
                  </span>
                </div>
                <div className="my-2">
                  <div className="text-2xl sm:text-3xl font-extrabold font-mono text-white">
                    {formatIdr(market?.digital?.buy_price_idr)}
                  </div>
                  <div className="text-[11px] text-slate-400 mt-0.5">
                    Buyback Digital: <strong className="text-emerald-400">{formatIdr(market?.digital?.buyback_price_idr)}</strong>/g
                  </div>
                </div>
                <div className="pt-2 border-t border-obsidian-800 flex items-center justify-between text-[11px] font-mono text-slate-400">
                  <span>Selisih Spread:</span>
                  <span className="text-amber-300">-{formatIdr(market?.digital?.spread_idr)}/g</span>
                </div>
              </div>
            </div>
          )}
        </section>

        {/* SECTION 2: INDIKATOR PORTOFOLIO UNTUNG/RUGI + CARD SIMULASI JUAL SEKARANG */}
        <section className="grid grid-cols-1 xl:grid-cols-12 gap-5">
          {/* LEFT 7 COLS: RINGKASAN PORTOFOLIO & TAMBAH MANUAL */}
          <div className="xl:col-span-7 space-y-4">
            {/* Indikator Status Untung / Rugi Portofolio Emas */}
            <div className="rounded-2xl bg-obsidian-900 border border-obsidian-700 p-4 sm:p-5 space-y-4 shadow-lg">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-obsidian-800 pb-3">
                <div>
                  <h2 className="text-sm sm:text-base font-extrabold text-white flex items-center gap-2">
                    <LucideIcon name="wallet" className="w-4 h-4 text-amber-400" />
                    <span>Ringkasan Portofolio Emas &amp; Indikator Untung / Rugi</span>
                  </h2>
                  <p className="text-xs text-slate-400">
                    Perhitungan otomatis nilai emas Anda terhadap harga beli baru (etalase) maupun harga jual kembali (buyback).
                  </p>
                </div>

                {/* Main Profit/Loss Status Badge */}
                {Number(portfolio?.total_weight_grams || 0) > 0 ? (
                  <div
                    className={`px-3 py-1.5 rounded-xl font-mono text-xs font-extrabold border flex items-center gap-2 ${
                      Number(portfolio?.net_pnl_idr || 0) > 0
                        ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                        : Number(portfolio?.net_pnl_idr || 0) < 0
                        ? 'bg-rose-500/20 text-rose-300 border-rose-500/40'
                        : 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                    }`}
                  >
                    <span>
                      {Number(portfolio?.net_pnl_idr || 0) > 0
                        ? '🟢 POSISI UNTUNG BERSIH (BUYBACK)'
                        : Number(portfolio?.net_pnl_idr || 0) < 0
                        ? '🔴 POSISI RUGI JIKA DIJUAL SEKARANG'
                        : '⚖️ POSISI IMPAS (BREAK-EVEN)'}
                    </span>
                  </div>
                ) : (
                  <span className="px-3 py-1 rounded-xl bg-obsidian-850 border border-obsidian-700 text-slate-400 font-mono text-xs">
                    Belum Ada Emas Tercatat
                  </span>
                )}
              </div>

              {/* 4 Stat Boxes for Portfolio */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="p-3 rounded-xl bg-obsidian-950 border border-obsidian-800">
                  <div className="text-[10px] font-mono uppercase text-slate-400">Total Berat Emas</div>
                  <div className="text-lg sm:text-xl font-extrabold font-mono text-amber-400 mt-0.5">
                    {Number(portfolio?.total_weight_grams || 0).toLocaleString('id-ID')} Gram
                  </div>
                  <div className="text-[11px] text-slate-400 font-mono mt-0.5">
                    {portfolio?.holdings_count || 0} keping / catatan
                  </div>
                </div>

                <div className="p-3 rounded-xl bg-obsidian-950 border border-obsidian-800">
                  <div className="text-[10px] font-mono uppercase text-slate-400">Total Modal Beli</div>
                  <div className="text-lg sm:text-xl font-extrabold font-mono text-white mt-0.5">
                    {formatIdr(portfolio?.total_cost_idr || 0)}
                  </div>
                  <div className="text-[11px] text-slate-400 font-mono mt-0.5">
                    Rata-rata: {formatIdr(portfolio?.avg_buy_price_per_gram_idr || 0)}/g
                  </div>
                </div>

                <div className="p-3 rounded-xl bg-obsidian-950 border border-obsidian-800">
                  <div className="text-[10px] font-mono uppercase text-slate-400">Nilai Etalase (Harga Beli)</div>
                  <div className="text-lg sm:text-xl font-extrabold font-mono text-cyan-400 mt-0.5">
                    {formatIdr(portfolio?.total_retail_value_idr || 0)}
                  </div>
                  <div
                    className={`text-[11px] font-mono font-bold mt-0.5 ${
                      Number(portfolio?.retail_pnl_idr || 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'
                    }`}
                  >
                    {Number(portfolio?.retail_pnl_idr || 0) >= 0 ? '+' : ''}
                    {formatIdr(portfolio?.retail_pnl_idr || 0)} ({portfolio?.retail_pnl_pct || 0}%)
                  </div>
                </div>

                <div className="p-3 rounded-xl bg-obsidian-950 border border-obsidian-800">
                  <div className="text-[10px] font-mono uppercase text-slate-400">Untung/Rugi Jual Bersih</div>
                  <div
                    className={`text-lg sm:text-xl font-extrabold font-mono mt-0.5 ${
                      Number(portfolio?.net_pnl_idr || 0) > 0
                        ? 'text-emerald-400'
                        : Number(portfolio?.net_pnl_idr || 0) < 0
                        ? 'text-rose-400'
                        : 'text-slate-200'
                    }`}
                  >
                    {Number(portfolio?.net_pnl_idr || 0) > 0 ? '+' : ''}
                    {formatIdr(portfolio?.net_pnl_idr || 0)}
                  </div>
                  <div
                    className={`text-[11px] font-mono font-bold mt-0.5 ${
                      Number(portfolio?.net_pnl_idr || 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'
                    }`}
                  >
                    Net Cair: {formatIdr(portfolio?.net_sell_now_idr || 0)} ({portfolio?.net_pnl_pct || 0}%)
                  </div>
                </div>
              </div>

              {/* Form Tambah Portofolio Emas Secara Manual */}
              <form
                onSubmit={handleAddHolding}
                className="p-4 rounded-xl bg-obsidian-950/90 border border-obsidian-800 space-y-3"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h3 className="text-xs sm:text-sm font-mono font-bold text-amber-300 uppercase flex items-center gap-1.5">
                    <span>➕ Tambah Portofolio Emas Manual</span>
                  </h3>
                  <button
                    type="button"
                    onClick={() => handleUseCurrentBrandPrice(brand)}
                    className="text-[11px] font-mono text-cyan-400 hover:text-cyan-300 underline"
                  >
                    Isi dengan Harga {brand} Hari Ini
                  </button>
                </div>

                {/* Quick Gram Preset Pills */}
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="text-[11px] font-mono text-slate-400 mr-1">Pilih Cepat Gram:</span>
                  {QUICK_WEIGHTS.map((wg) => {
                    const active = parseFloat(weightGrams) === wg;
                    return (
                      <button
                        key={wg}
                        type="button"
                        onClick={() => {
                          setWeightGrams(String(wg));
                          if (buyPricePerGram) {
                            setTotalCostInput(String(Math.round((parseFloat(buyPricePerGram) || 0) * wg)));
                          }
                        }}
                        className={
                          active
                            ? 'px-2 py-0.5 rounded-md bg-amber-500/25 text-amber-300 border border-amber-500/50 font-mono text-xs font-bold'
                            : 'px-2 py-0.5 rounded-md bg-obsidian-850 hover:bg-obsidian-800 text-slate-300 border border-obsidian-700 font-mono text-xs'
                        }
                      >
                        {wg}g
                      </button>
                    );
                  })}
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <div>
                    <label className="block text-[11px] font-mono text-slate-300 mb-1">
                      Brand / Jenis Emas
                    </label>
                    <select
                      value={brand}
                      onChange={(e) => {
                        setBrand(e.target.value);
                        handleUseCurrentBrandPrice(e.target.value);
                      }}
                      className="w-full px-3 py-2 rounded-lg bg-obsidian-900 border border-obsidian-700 text-xs text-white font-mono focus:outline-none focus:border-amber-400"
                    >
                      {BRAND_OPTIONS.map((b) => (
                        <option key={b.id} value={b.id}>
                          {b.label}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-[11px] font-mono text-slate-300 mb-1">
                      Berat Emas (Gram)
                    </label>
                    <input
                      type="number"
                      step="0.01"
                      min="0.01"
                      value={weightGrams}
                      onChange={(e) => {
                        setWeightGrams(e.target.value);
                        const w = parseFloat(e.target.value) || 0;
                        if (costMode === 'per_gram' && buyPricePerGram) {
                          setTotalCostInput(String(Math.round((parseFloat(buyPricePerGram) || 0) * w)));
                        }
                      }}
                      placeholder="Contoh: 5"
                      className="w-full px-3 py-2 rounded-lg bg-obsidian-900 border border-obsidian-700 text-xs text-white font-mono focus:outline-none focus:border-amber-400"
                      required
                    />
                  </div>

                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <label className="text-[11px] font-mono text-slate-300">
                        {costMode === 'per_gram' ? 'Harga Beli / Gram (Rp)' : 'Total Modal Beli (Rp)'}
                      </label>
                      <button
                        type="button"
                        onClick={() => setCostMode(costMode === 'per_gram' ? 'total' : 'per_gram')}
                        className="text-[10px] font-mono text-amber-400 hover:underline"
                      >
                        Ubah ke {costMode === 'per_gram' ? 'Total Rp' : 'Rp/Gram'}
                      </button>
                    </div>
                    {costMode === 'per_gram' ? (
                      <input
                        type="number"
                        step="500"
                        min="0"
                        value={buyPricePerGram}
                        onChange={(e) => {
                          setBuyPricePerGram(e.target.value);
                          const p = parseFloat(e.target.value) || 0;
                          const w = parseFloat(weightGrams) || 0;
                          setTotalCostInput(String(Math.round(p * w)));
                        }}
                        placeholder="Contoh: 1550000"
                        className="w-full px-3 py-2 rounded-lg bg-obsidian-900 border border-obsidian-700 text-xs text-white font-mono focus:outline-none focus:border-amber-400"
                        required
                      />
                    ) : (
                      <input
                        type="number"
                        step="1000"
                        min="0"
                        value={totalCostInput}
                        onChange={(e) => {
                          setTotalCostInput(e.target.value);
                          const tot = parseFloat(e.target.value) || 0;
                          const w = parseFloat(weightGrams) || 1;
                          setBuyPricePerGram(String(Math.round(tot / w)));
                        }}
                        placeholder="Contoh: 7750000"
                        className="w-full px-3 py-2 rounded-lg bg-obsidian-900 border border-obsidian-700 text-xs text-white font-mono focus:outline-none focus:border-amber-400"
                        required
                      />
                    )}
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 items-end">
                  <div>
                    <label className="block text-[11px] font-mono text-slate-300 mb-1">
                      Label / Nama Kepingan (Opsional)
                    </label>
                    <input
                      type="text"
                      value={label}
                      onChange={(e) => setLabel(e.target.value)}
                      placeholder={`Emas ${brand} ${weightGrams || 1}g`}
                      className="w-full px-3 py-2 rounded-lg bg-obsidian-900 border border-obsidian-700 text-xs text-white font-mono focus:outline-none focus:border-amber-400"
                    />
                  </div>

                  <div>
                    <label className="block text-[11px] font-mono text-slate-300 mb-1">
                      Tanggal Beli
                    </label>
                    <input
                      type="date"
                      value={purchasedAt}
                      onChange={(e) => setPurchasedAt(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg bg-obsidian-900 border border-obsidian-700 text-xs text-white font-mono focus:outline-none focus:border-amber-400"
                    />
                  </div>

                  <button
                    type="submit"
                    disabled={submitting}
                    className="w-full py-2 px-4 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-obsidian-950 font-mono font-extrabold text-xs shadow-glow-emerald transition"
                  >
                    {submitting ? 'Menyimpan...' : '+ Simpan ke Portofolio'}
                  </button>
                </div>
              </form>

              {/* Daftar Portofolio Emas Manual */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-mono font-bold uppercase text-slate-300">
                    Daftar Kepingan Emas Anda ({holdings.length})
                  </h3>
                  {holdings.length > 0 && (
                    <button
                      type="button"
                      onClick={() => setSimSource('portfolio')}
                      className="text-[11px] font-mono text-amber-400 hover:underline"
                    >
                      🧮 Simulasikan Jual Semua Portofolio ({portfolio?.total_weight_grams}g)
                    </button>
                  )}
                </div>

                {holdings.length === 0 ? (
                  <div className="p-6 rounded-xl bg-obsidian-950 border border-obsidian-800 text-center space-y-1">
                    <div className="text-sm font-bold text-slate-300">
                      Portofolio Emas Anda Masih Kosong
                    </div>
                    <p className="text-xs text-slate-400 max-w-md mx-auto">
                      Tambahkan emas yang Anda miliki pada form di atas (misal: 5 gram Antam dengan harga beli lama Anda) untuk melihat indikator Untung / Rugi secara real-time.
                    </p>
                  </div>
                ) : (
                  <div className="overflow-x-auto rounded-xl border border-obsidian-800">
                    <table className="w-full text-left border-collapse text-xs font-mono">
                      <thead>
                        <tr className="bg-obsidian-950 text-slate-400 border-b border-obsidian-800 text-[10px] uppercase">
                          <th className="py-2.5 px-3">Kepingan &amp; Brand</th>
                          <th className="py-2.5 px-3 text-right">Berat</th>
                          <th className="py-2.5 px-3 text-right">Modal Beli</th>
                          <th className="py-2.5 px-3 text-right">Nilai Buyback</th>
                          <th className="py-2.5 px-3 text-center">Indikator Untung / Rugi</th>
                          <th className="py-2.5 px-3 text-right">Aksi</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-obsidian-800/80 bg-obsidian-900/60">
                        {holdings.map((h) => {
                          const isProfitBuyback = Number(h.buyback_pnl_idr || 0) > 0;
                          const isProfitRetail = Number(h.retail_pnl_idr || 0) > 0;
                          return (
                            <tr key={h.id} className="hover:bg-obsidian-850/70 transition">
                              <td className="py-2.5 px-3">
                                <div className="font-bold text-white">{h.label}</div>
                                <div className="text-[10px] text-slate-400">
                                  {h.brand} • Beli: {h.purchased_at || '-'}
                                </div>
                              </td>
                              <td className="py-2.5 px-3 text-right font-bold text-amber-400">
                                {h.weight_grams}g
                              </td>
                              <td className="py-2.5 px-3 text-right">
                                <div className="text-white font-semibold">{formatIdr(h.total_cost_idr)}</div>
                                <div className="text-[10px] text-slate-400">
                                  @{formatIdr(h.buy_price_per_gram_idr)}/g
                                </div>
                              </td>
                              <td className="py-2.5 px-3 text-right">
                                <div className="text-emerald-300 font-semibold">
                                  {formatIdr(h.buyback_value_idr)}
                                </div>
                                <div className="text-[10px] text-slate-400">
                                  Etalase: {formatIdr(h.retail_value_idr)}
                                </div>
                              </td>
                              <td className="py-2.5 px-3 text-center">
                                <div className="flex flex-col items-center gap-1">
                                  <span
                                    className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold border ${
                                      isProfitBuyback
                                        ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                                        : Number(h.buyback_pnl_idr || 0) < 0
                                        ? 'bg-rose-500/20 text-rose-300 border-rose-500/40'
                                        : 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                                    }`}
                                  >
                                    {isProfitBuyback ? '🟢 UNTUNG ' : Number(h.buyback_pnl_idr || 0) < 0 ? '🔴 RUGI ' : '⚖️ IMPAS '}
                                    {isProfitBuyback ? '+' : ''}
                                    {formatIdr(h.buyback_pnl_idr)} ({h.buyback_pnl_pct}%)
                                  </span>
                                  <span className="text-[10px] text-slate-400">
                                    vs Etalase:{' '}
                                    <strong className={isProfitRetail ? 'text-emerald-400' : 'text-rose-400'}>
                                      {isProfitRetail ? '+' : ''}
                                      {formatIdr(h.retail_pnl_idr)} ({h.retail_pnl_pct}%)
                                    </strong>
                                  </span>
                                </div>
                              </td>
                              <td className="py-2.5 px-3 text-right">
                                <div className="flex items-center justify-end gap-1.5">
                                  <button
                                    type="button"
                                    onClick={() => handleSimulateSingleHolding(h)}
                                    className="px-2 py-1 rounded bg-amber-500/15 hover:bg-amber-500/25 text-amber-300 border border-amber-500/30 text-[10px] font-bold"
                                    title="Masukkan kepingan ini ke Card Simulasi Jual Sekarang"
                                  >
                                    Simulasi Jual
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => handleDeleteHolding(h.id, h.label)}
                                    className="p-1.5 rounded bg-rose-500/15 hover:bg-rose-500/30 text-rose-300 border border-rose-500/30"
                                    title="Hapus dari portofolio"
                                  >
                                    <LucideIcon name="trash-2" className="w-3.5 h-3.5" />
                                  </button>
                                </div>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* RIGHT 5 COLS: CARD SIMULASI JUAL SEKARANG (SPREAD & PAJAK PPH 22) */}
          <div className="xl:col-span-5">
            <div className="rounded-2xl bg-obsidian-900 border-2 border-amber-500/40 p-4 sm:p-5 space-y-4 shadow-xl sticky top-4">
              <div className="flex items-start justify-between gap-2 border-b border-obsidian-800 pb-3">
                <div>
                  <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-amber-500/20 text-amber-300 border border-amber-500/40 mb-1">
                    <LucideIcon name="calculator" className="w-3.5 h-3.5" />
                    KALKULATOR BUYBACK REALISTIS
                  </span>
                  <h2 className="text-base sm:text-lg font-extrabold text-white">
                    Card Simulasi Jual Sekarang (Spread &amp; Pajak)
                  </h2>
                  <p className="text-xs text-slate-400">
                    Estimasi uang tunai bersih yang masuk ke rekening Anda jika emas dijual hari ini.
                  </p>
                </div>
              </div>

              {/* Mode Sumber Simulasi: Portofolio vs Kustom */}
              <div className="grid grid-cols-2 gap-1.5 p-1 rounded-xl bg-obsidian-950 border border-obsidian-800 font-mono text-xs">
                <button
                  type="button"
                  onClick={() => {
                    setSimSource('portfolio');
                    if (Number(portfolio?.total_weight_grams || 0) > 0) {
                      setSimWeightGrams(Number(portfolio.total_weight_grams));
                      setSimTotalCostIdr(Number(portfolio.total_cost_idr));
                    }
                  }}
                  className={
                    simSource === 'portfolio'
                      ? 'py-2 px-3 rounded-lg bg-amber-500/20 text-amber-300 border border-amber-500/40 font-bold'
                      : 'py-2 px-3 rounded-lg text-slate-400 hover:text-slate-200'
                  }
                >
                  📦 Dari Portofolio ({Number(portfolio?.total_weight_grams || 0)}g)
                </button>
                <button
                  type="button"
                  onClick={() => setSimSource('custom')}
                  className={
                    simSource === 'custom'
                      ? 'py-2 px-3 rounded-lg bg-amber-500/20 text-amber-300 border border-amber-500/40 font-bold'
                      : 'py-2 px-3 rounded-lg text-slate-400 hover:text-slate-200'
                  }
                >
                  ✏️ Simulasi Gram Kustom
                </button>
              </div>

              {/* Input Gram, Modal Beli, & Harga Acuan */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 font-mono text-xs">
                <div>
                  <label className="block text-[10px] uppercase text-slate-400 mb-1">
                    Berat Dijual (Gram)
                  </label>
                  <input
                    type="number"
                    step="0.1"
                    min="0.1"
                    value={simWeightGrams}
                    onChange={(e) => {
                      setSimSource('custom');
                      setSimWeightGrams(parseFloat(e.target.value) || 0);
                    }}
                    className="w-full px-2.5 py-2 rounded-lg bg-obsidian-950 border border-obsidian-700 text-amber-300 font-bold focus:outline-none focus:border-amber-400"
                  />
                </div>

                <div>
                  <label className="block text-[10px] uppercase text-slate-400 mb-1">
                    Total Modal Beli Dulu (Rp)
                  </label>
                  <input
                    type="number"
                    step="10000"
                    min="0"
                    value={simTotalCostIdr}
                    onChange={(e) => {
                      setSimSource('custom');
                      setSimTotalCostIdr(parseFloat(e.target.value) || 0);
                    }}
                    className="w-full px-2.5 py-2 rounded-lg bg-obsidian-950 border border-obsidian-700 text-white font-bold focus:outline-none focus:border-amber-400"
                  />
                </div>

                <div>
                  <label className="block text-[10px] uppercase text-slate-400 mb-1">
                    Harga Beli Baru /g (Rp)
                  </label>
                  <input
                    type="number"
                    step="500"
                    min="0"
                    value={simRetailPricePerGram}
                    onChange={(e) => setSimRetailPricePerGram(parseFloat(e.target.value) || 0)}
                    className="w-full px-2.5 py-2 rounded-lg bg-obsidian-950 border border-obsidian-700 text-cyan-300 font-bold focus:outline-none focus:border-amber-400"
                  />
                </div>
              </div>

              {/* Pengaturan Spread Buyback (%) */}
              <div className="p-3 rounded-xl bg-obsidian-950 border border-obsidian-800 space-y-2">
                <div className="flex items-center justify-between text-xs font-mono">
                  <span className="text-slate-300 font-bold">
                    1. Perkiraan Spread Buyback (Selisih Beli vs Jual):
                  </span>
                  <span className="text-amber-400 font-extrabold">{simSpreadPct}%</span>
                </div>

                <div className="grid grid-cols-4 gap-1.5 font-mono text-[10px]">
                  {[
                    { label: 'Digital (3%)', val: 3.0 },
                    { label: 'UBS (8.5%)', val: 8.5 },
                    { label: 'Antam (9%)', val: 9.0 },
                    { label: 'Toko (10.5%)', val: 10.5 },
                  ].map((sp) => (
                    <button
                      key={sp.label}
                      type="button"
                      onClick={() => setSimSpreadPct(sp.val)}
                      className={
                        simSpreadPct === sp.val
                          ? 'py-1.5 px-1.5 rounded-lg bg-amber-500/20 text-amber-300 border border-amber-500/40 font-bold'
                          : 'py-1.5 px-1.5 rounded-lg bg-obsidian-900 text-slate-400 hover:text-slate-200 border border-obsidian-800'
                      }
                    >
                      {sp.label}
                    </button>
                  ))}
                </div>

                <div className="flex items-center gap-2 pt-1">
                  <input
                    type="range"
                    min="0"
                    max="20"
                    step="0.25"
                    value={simSpreadPct}
                    onChange={(e) => setSimSpreadPct(parseFloat(e.target.value))}
                    className="flex-1 accent-amber-400"
                  />
                  <span className="text-[11px] font-mono text-slate-400">
                    Buyback: <strong className="text-emerald-400">{formatIdr(simResult.effectiveBuybackPerGram)}/g</strong>
                  </span>
                </div>
              </div>

              {/* Pengaturan Pajak PPh 22 & Bea Materai */}
              <div className="p-3 rounded-xl bg-obsidian-950 border border-obsidian-800 space-y-2">
                <div className="flex items-center justify-between text-xs font-mono">
                  <span className="text-slate-300 font-bold">
                    2. Pajak Buyback PPh 22 (PMK 48/2023) &amp; Materai:
                  </span>
                  <span className="text-rose-400 font-extrabold">{simResult.appliedTaxPct}%</span>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5 font-mono text-[10px]">
                  <button
                    type="button"
                    onClick={() => setSimTaxMode('auto_npwp')}
                    className={
                      simTaxMode === 'auto_npwp'
                        ? 'py-1.5 px-2 rounded-lg bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 font-bold'
                        : 'py-1.5 px-2 rounded-lg bg-obsidian-900 text-slate-400 border border-obsidian-800'
                    }
                  >
                    NPWP (1.5% &gt;10Jt)
                  </button>
                  <button
                    type="button"
                    onClick={() => setSimTaxMode('auto_non_npwp')}
                    className={
                      simTaxMode === 'auto_non_npwp'
                        ? 'py-1.5 px-2 rounded-lg bg-amber-500/20 text-amber-300 border border-amber-500/40 font-bold'
                        : 'py-1.5 px-2 rounded-lg bg-obsidian-900 text-slate-400 border border-obsidian-800'
                    }
                  >
                    Non-NPWP (3%)
                  </button>
                  <button
                    type="button"
                    onClick={() => setSimTaxMode('zero')}
                    className={
                      simTaxMode === 'zero'
                        ? 'py-1.5 px-2 rounded-lg bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 font-bold'
                        : 'py-1.5 px-2 rounded-lg bg-obsidian-900 text-slate-400 border border-obsidian-800'
                    }
                  >
                    Bebas Pajak (0%)
                  </button>
                  <button
                    type="button"
                    onClick={() => setSimTaxMode('custom')}
                    className={
                      simTaxMode === 'custom'
                        ? 'py-1.5 px-2 rounded-lg bg-purple-500/20 text-purple-300 border border-purple-500/40 font-bold'
                        : 'py-1.5 px-2 rounded-lg bg-obsidian-900 text-slate-400 border border-obsidian-800'
                    }
                  >
                    Kustom (%)
                  </button>
                </div>

                {simTaxMode === 'custom' && (
                  <div className="flex items-center gap-2 pt-1 font-mono text-xs">
                    <span className="text-slate-400">Persentase Pajak Kustom (%):</span>
                    <input
                      type="number"
                      step="0.1"
                      min="0"
                      max="25"
                      value={simCustomTaxPct}
                      onChange={(e) => setSimCustomTaxPct(parseFloat(e.target.value) || 0)}
                      className="w-24 px-2 py-1 rounded bg-obsidian-900 border border-obsidian-700 text-white"
                    />
                  </div>
                )}

                <label className="flex items-center gap-2 text-[11px] font-mono text-slate-300 pt-1 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={simIncludeStampDuty}
                    onChange={(e) => setSimIncludeStampDuty(e.target.checked)}
                    className="rounded accent-amber-400"
                  />
                  <span>Sertakan potongan Bea Materai Rp 10.000 (jika nilai buyback &gt; Rp 5 Juta)</span>
                </label>
              </div>

              {/* RINCIAN KALKULASI SIMULASI JUAL SEKARANG */}
              <div className="p-4 rounded-xl bg-obsidian-950 border border-obsidian-800 space-y-2.5 font-mono text-xs">
                <div className="flex items-center justify-between text-slate-300">
                  <span>Nilai Harga Etalase ({simResult.w}g × {formatIdr(simResult.retailPerGram)}):</span>
                  <span className="font-bold text-white">{formatIdr(simResult.grossRetailIdr)}</span>
                </div>

                <div className="flex items-center justify-between text-rose-400">
                  <span>(-) Potongan Spread Buyback ({simResult.spreadPct}%):</span>
                  <span className="font-bold">-{formatIdr(simResult.spreadDeductionIdr)}</span>
                </div>

                <div className="flex items-center justify-between text-slate-200 border-t border-obsidian-800 pt-2">
                  <span>Nilai Buyback Kotor (@{formatIdr(simResult.effectiveBuybackPerGram)}/g):</span>
                  <span className="font-bold">{formatIdr(simResult.grossBuybackIdr)}</span>
                </div>

                <div className="flex items-center justify-between text-rose-400">
                  <span>(-) {simResult.taxLabel}:</span>
                  <span className="font-bold">-{formatIdr(simResult.taxDeductionIdr)}</span>
                </div>

                {simResult.stampDutyIdr > 0 && (
                  <div className="flex items-center justify-between text-rose-400">
                    <span>(-) Bea Materai Transaksi (&gt; Rp 5 Juta):</span>
                    <span className="font-bold">-{formatIdr(simResult.stampDutyIdr)}</span>
                  </div>
                )}

                <div className="border-t-2 border-obsidian-700 pt-3 flex items-center justify-between">
                  <div>
                    <div className="text-[10px] uppercase text-amber-400 font-bold">
                      DANA BERSIH DITERIMA (NET CASH OUT)
                    </div>
                    <div className="text-xl sm:text-2xl font-extrabold text-emerald-400 mt-0.5">
                      {formatIdr(simResult.netPayoutIdr)}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-[10px] uppercase text-slate-400">Modal Awal Anda</div>
                    <div className="text-sm font-bold text-slate-200">{formatIdr(simResult.cost)}</div>
                  </div>
                </div>

                {/* HASIL UNTUNG / RUGI BERSIH JIKA DIJUAL SEKARANG */}
                <div
                  className={`p-3 rounded-xl border mt-2 flex items-center justify-between ${
                    simResult.netPnlIdr > 0
                      ? 'bg-emerald-500/15 border-emerald-500/40 text-emerald-300'
                      : simResult.netPnlIdr < 0
                      ? 'bg-rose-500/15 border-rose-500/40 text-rose-300'
                      : 'bg-amber-500/15 border-amber-500/40 text-amber-300'
                  }`}
                >
                  <div>
                    <div className="text-[10px] uppercase font-bold">
                      STATUS JIKA DIJUAL SEKARANG (SETELAH SPREAD &amp; PAJAK)
                    </div>
                    <div className="text-sm sm:text-base font-extrabold mt-0.5">
                      {simResult.netPnlIdr > 0
                        ? `🟢 UNTUNG BERSIH +${formatIdr(simResult.netPnlIdr)} (+${simResult.netPnlPct}%)`
                        : simResult.netPnlIdr < 0
                        ? `🔴 RUGI BERSIH ${formatIdr(simResult.netPnlIdr)} (${simResult.netPnlPct}%)`
                        : '⚖️ IMPAS / BREAK-EVEN (Rp 0)'}
                    </div>
                  </div>
                </div>

                {/* Info Break-Even */}
                <div className="text-[11px] text-slate-400 pt-1 flex items-center justify-between">
                  <span>Harga Buyback Minimal Agar Impas (Break-Even):</span>
                  <strong className="text-amber-300">{formatIdr(simResult.breakevenBuybackPerGram)} / gram</strong>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* SECTION 3: TABEL PECAHAN EMAS ANTAM & GRAFIK TREN 30 HARI */}
        <section className="grid grid-cols-1 lg:grid-cols-12 gap-5">
          {/* Tabel Harga Emas per Pecahan (0.5g - 100g) */}
          <div className="lg:col-span-7 rounded-2xl bg-obsidian-900 border border-obsidian-700 p-4 sm:p-5 space-y-3">
            <div className="flex items-center justify-between border-b border-obsidian-800 pb-2.5">
              <div>
                <h3 className="text-sm font-extrabold text-white font-mono uppercase">
                  📊 Daftar Harga Pecahan Emas Batangan Hari Ini (0.5g – 100g)
                </h3>
                <p className="text-xs text-slate-400">
                  Estimasi harga beli butik (+PPh 22 0,25% NPWP) dan estimasi nilai buyback per pecahan.
                </p>
              </div>
            </div>

            <div className="overflow-x-auto rounded-xl border border-obsidian-800">
              <table className="w-full text-left border-collapse text-xs font-mono">
                <thead>
                  <tr className="bg-obsidian-950 text-slate-400 border-b border-obsidian-800 text-[10px] uppercase">
                    <th className="py-2 px-3">Pecahan Emas</th>
                    <th className="py-2 px-3 text-right">Harga Dasar</th>
                    <th className="py-2 px-3 text-right">+Pajak Beli (0.25%)</th>
                    <th className="py-2 px-3 text-right">Estimasi Buyback</th>
                    <th className="py-2 px-3 text-right">Pilih Simulasi</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-obsidian-800/80">
                  {(market?.denominations || []).map((d: any) => (
                    <tr key={d.weight_grams} className="hover:bg-obsidian-850/60 transition">
                      <td className="py-2 px-3 font-bold text-amber-400">{d.label}</td>
                      <td className="py-2 px-3 text-right text-white">{formatIdr(d.antam_buy_idr)}</td>
                      <td className="py-2 px-3 text-right text-cyan-300">{formatIdr(d.antam_buy_with_tax_idr)}</td>
                      <td className="py-2 px-3 text-right text-emerald-400 font-semibold">
                        {formatIdr(d.antam_buyback_idr)}
                      </td>
                      <td className="py-2 px-3 text-right">
                        <button
                          type="button"
                          onClick={() => {
                            setSimSource('custom');
                            setSimWeightGrams(d.weight_grams);
                            setSimTotalCostIdr(d.antam_buy_idr);
                            setSimRetailPricePerGram(Math.round(d.antam_buy_idr / d.weight_grams));
                          }}
                          className="px-2 py-0.5 rounded bg-obsidian-800 hover:bg-amber-500/20 text-slate-300 hover:text-amber-300 border border-obsidian-700 text-[10px]"
                        >
                          Tes {d.weight_grams}g
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Grafik Tren Harga Emas 30 Hari Terakhir */}
          <div className="lg:col-span-5 rounded-2xl bg-obsidian-900 border border-obsidian-700 p-4 sm:p-5 flex flex-col justify-between space-y-3">
            <div>
              <div className="flex items-center justify-between border-b border-obsidian-800 pb-2.5">
                <div>
                  <h3 className="text-sm font-extrabold text-white font-mono uppercase">
                    📈 Tren Harga Emas 30 Hari Terakhir
                  </h3>
                  <p className="text-xs text-slate-400">
                    Pergerakan harga beli (kuning) vs buyback (hijau) per gram dalam 1 bulan terakhir.
                  </p>
                </div>
              </div>

              {history30d.length > 0 ? (
                <div className="mt-4 space-y-2">
                  <div className="h-48 flex items-end gap-1 pt-4 pb-2 px-2 rounded-xl bg-obsidian-950 border border-obsidian-800">
                    {history30d.map((pt, idx) => {
                      const span = Math.max(10000, maxHistPrice - minHistPrice);
                      const heightPct = Math.max(
                        18,
                        Math.min(100, Math.round(((pt.antam_buy_idr - minHistPrice) / span) * 80 + 18))
                      );
                      return (
                        <div
                          key={idx}
                          className="flex-1 flex flex-col items-center justify-end h-full group relative"
                          title={`${pt.date}: Beli ${formatIdr(pt.antam_buy_idr)} | Buyback ${formatIdr(pt.antam_buyback_idr)} (${formatUsd(pt.xau_usd)}/oz)`}
                        >
                          <div
                            style={{ height: `${heightPct}%` }}
                            className="w-full rounded-t bg-gradient-to-t from-emerald-500/60 via-amber-500/70 to-amber-400 group-hover:from-emerald-400 group-hover:to-amber-300 transition-all"
                          />
                        </div>
                      );
                    })}
                  </div>
                  <div className="flex items-center justify-between text-[10px] font-mono text-slate-400 px-1">
                    <span>{history30d[0]?.date}</span>
                    <span>Terendah: {formatIdr(minHistPrice)}/g</span>
                    <span>Tertinggi: {formatIdr(maxHistPrice)}/g</span>
                    <span>{history30d[history30d.length - 1]?.date}</span>
                  </div>
                </div>
              ) : (
                <div className="h-48 flex items-center justify-center text-xs font-mono text-slate-400">
                  Memuat riwayat grafik 30 hari...
                </div>
              )}
            </div>

            <div className="p-3 rounded-xl bg-obsidian-950 border border-obsidian-800 text-[11px] text-slate-300 space-y-1 font-mono">
              <div className="font-bold text-amber-400">💡 Tips Cuan Investasi Emas Fisik &amp; Digital:</div>
              <p className="text-slate-400 leading-relaxed">
                Karena emas batangan fisik memiliki spread sekitar <strong>8,5% – 9,5%</strong>, emas fisik paling optimal untuk investasi jangka menengah-panjang. Gunakan <strong>Card Simulasi Jual Sekarang</strong> di atas untuk memastikan harga buyback sudah melewati harga modal beli Anda.
              </p>
            </div>
          </div>
        </section>
      </main>
    </>
  );
}
