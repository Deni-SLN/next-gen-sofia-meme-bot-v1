import React, { useState, useEffect, useMemo } from 'react';
import Head from 'next/head';
import { api, formatIdr, formatUsd } from '@/lib/api';
import { LucideIcon } from '@/components/LucideIcon';

const QUICK_WEIGHTS = [0.5, 1, 2, 5, 10, 25, 50, 100];
const BRAND_OPTIONS = [
  { id: 'Antam', label: 'Antam CertiEye (Fisik)' },
  { id: 'Hartadinata', label: 'Hartadinata / EmasKita - HRTA (Fisik)' },
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

  // Form state: Add / Edit Manual Gold Portfolio
  const [editingId, setEditingId] = useState<number | null>(null);
  const [brand, setBrand] = useState<string>('Antam');
  const [weightGrams, setWeightGrams] = useState<string>('10');
  const [buyPricePerGram, setBuyPricePerGram] = useState<string>('');
  const [totalCostInput, setTotalCostInput] = useState<string>('');
  const [userEditedPrice, setUserEditedPrice] = useState<boolean>(false);
  const [label, setLabel] = useState<string>('');
  const [purchasedAt, setPurchasedAt] = useState<string>(() => new Date().toISOString().slice(0, 10));
  const [notes, setNotes] = useState<string>('');
  const [submitting, setSubmitting] = useState<boolean>(false);

  // Denomination table brand tab
  const [denomBrand, setDenomBrand] = useState<'antam' | 'hartadinata'>('antam');

  // Card Simulasi Jual Sekarang (Buyback, Spread & Pajak) state
  const [simSource, setSimSource] = useState<'portfolio' | 'custom'>('portfolio');
  const [simWeightGrams, setSimWeightGrams] = useState<number>(10);
  const [simTotalCostIdr, setSimTotalCostIdr] = useState<number>(27000000);
  const [simRetailPricePerGram, setSimRetailPricePerGram] = useState<number>(2620000);
  const [simSpreadPct, setSimSpreadPct] = useState<number>(9.0);
  const [simTaxMode, setSimTaxMode] = useState<'auto_npwp' | 'auto_non_npwp' | 'zero' | 'custom'>('auto_npwp');
  const [simCustomTaxPct, setSimCustomTaxPct] = useState<number>(1.5);
  const [simIncludeStampDuty, setSimIncludeStampDuty] = useState<boolean>(true);

  const getBrandPriceFromMarket = (targetBrand: string, mkt: any): number => {
    if (!mkt) return 2600000;
    const b = (targetBrand || 'Antam').toLowerCase();
    if (b.includes('hartadinata') || b.includes('hrta') || b.includes('emaskita')) {
      return Number(mkt?.hartadinata?.buy_price_idr || mkt?.antam?.buy_price_idr || 2580000);
    }
    if (b.includes('ubs')) {
      return Number(mkt?.ubs?.buy_price_idr || mkt?.antam?.buy_price_idr || 2586000);
    }
    if (b.includes('galeri')) {
      return Number(mkt?.galeri24?.buy_price_idr || mkt?.antam?.buy_price_idr || 2596000);
    }
    if (b.includes('digital')) {
      return Number(mkt?.digital?.buy_price_idr || mkt?.antam?.buy_price_idr || 2458000);
    }
    return Number(mkt?.antam?.buy_price_idr || 2620000);
  };

  const getBrandSpreadFromMarket = (targetBrand: string): number => {
    const b = (targetBrand || 'Antam').toLowerCase();
    if (b.includes('digital')) return 3.0;
    if (b.includes('hartadinata') || b.includes('hrta')) return 8.2;
    if (b.includes('ubs') || b.includes('galeri')) return 8.5;
    return 9.0;
  };

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

      const defaultPrice = getBrandPriceFromMarket(brand, res?.market);
      if (!buyPricePerGram && !userEditedPrice) {
        const w = parseFloat(weightGrams) || 1;
        setBuyPricePerGram(String(defaultPrice));
        setTotalCostInput(String(Math.round(defaultPrice * w)));
      }

      const pWeight = Number(res?.portfolio?.total_weight_grams || 0);
      const pCost = Number(res?.portfolio?.total_cost_idr || 0);
      if (pWeight > 0) {
        setSimSource('portfolio');
        setSimWeightGrams(pWeight);
        setSimTotalCostIdr(pCost);
        const avgRetail =
          Number(res?.portfolio?.total_retail_value_idr || 0) / pWeight;
        setSimRetailPricePerGram(Math.round(avgRetail || defaultPrice));
        if (res?.portfolio?.simulation?.spread_pct) {
          setSimSpreadPct(Number(res.portfolio.simulation.spread_pct));
        }
      } else {
        setSimSource('custom');
        setSimRetailPricePerGram(defaultPrice);
        setSimTotalCostIdr(Math.round(defaultPrice * 10));
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
      if (portfolio?.simulation?.spread_pct) {
        setSimSpreadPct(Number(portfolio.simulation.spread_pct));
      }
    }
  }, [
    simSource,
    portfolio?.total_weight_grams,
    portfolio?.total_cost_idr,
    portfolio?.total_retail_value_idr,
    portfolio?.simulation?.spread_pct,
  ]);

  const handleUseCurrentBrandPrice = (targetBrand: string) => {
    const price = getBrandPriceFromMarket(targetBrand, market);
    setBuyPricePerGram(String(price));
    const w = parseFloat(weightGrams) || 1;
    setTotalCostInput(String(Math.round(price * w)));
    setUserEditedPrice(false);
  };

  const handleStartEditHolding = (h: any) => {
    setEditingId(h.id);
    setBrand(h.brand || 'Antam');
    setWeightGrams(String(h.weight_grams || 1));
    setBuyPricePerGram(String(h.buy_price_per_gram_idr || 0));
    setTotalCostInput(String(h.total_cost_idr || 0));
    setUserEditedPrice(true);
    setLabel(h.label || '');
    setPurchasedAt(h.purchased_at || new Date().toISOString().slice(0, 10));
    setNotes(h.notes || '');
    setNotice(`Mode Edit: Mengubah data "${h.label}". Sesuaikan harga beli/gram lalu klik Simpan Perubahan.`);
  };

  const handleCancelEdit = () => {
    setEditingId(null);
    setLabel('');
    setNotes('');
    setUserEditedPrice(false);
    handleUseCurrentBrandPrice(brand);
  };

  const handleSaveHolding = async (e: React.FormEvent) => {
    e.preventDefault();
    const w = parseFloat(weightGrams);
    if (!w || w <= 0) {
      setError('Masukkan berat emas (gram) lebih dari 0.');
      return;
    }
    const perGram = parseFloat(buyPricePerGram) || 0;
    const totCost = parseFloat(totalCostInput) || Math.round(perGram * w);
    if (perGram <= 0 && totCost <= 0) {
      setError('Masukkan harga beli per gram atau total modal beli.');
      return;
    }

    setSubmitting(true);
    setError('');
    try {
      const payload: any = {
        weight_grams: w,
        brand,
        buy_price_per_gram_idr: perGram > 0 ? perGram : Math.round(totCost / w),
        total_cost_idr: perGram > 0 ? Math.round(perGram * w) : totCost,
        label: label.trim() || `Emas ${brand} ${w}g`,
        purchased_at: purchasedAt,
        notes: notes.trim(),
      };

      let res: any;
      if (editingId !== null) {
        res = await api.updateGoldHolding(editingId, payload);
        setNotice(
          `Perubahan pada "${payload.label}" (${w}g @ ${formatIdr(payload.buy_price_per_gram_idr)}/g) berhasil disimpan.`
        );
        setEditingId(null);
      } else {
        res = await api.addGoldHolding(payload);
        setNotice(
          `Berhasil menambahkan ${w} gram Emas ${brand} (@ ${formatIdr(payload.buy_price_per_gram_idr)}/g • Total ${formatIdr(payload.total_cost_idr)}) ke Portofolio.`
        );
      }

      setData(res);
      setSimSource('portfolio');
      setLabel('');
      setNotes('');
      setTimeout(() => setNotice(''), 4500);
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
      if (editingId === id) {
        setEditingId(null);
      }
      setNotice(`Kepingan "${itemLabel}" berhasil dihapus dari portofolio.`);
      setTimeout(() => setNotice(''), 3500);
    } catch (err: any) {
      setError(err?.message || 'Gagal menghapus data emas.');
    }
  };

  const handleSimulateSingleHolding = (h: any) => {
    setSimSource('custom');
    setSimWeightGrams(Number(h.weight_grams || 1));
    setSimTotalCostIdr(Number(h.total_cost_idr || 0));
    setSimRetailPricePerGram(
      Number(h.current_retail_per_gram_idr || getBrandPriceFromMarket(h.brand, market))
    );
    setSimSpreadPct(getBrandSpreadFromMarket(h.brand));
    setNotice(`Simulasi Jual Sekarang diatur untuk: ${h.label} (${h.weight_grams}g)`);
    setTimeout(() => setNotice(''), 3500);
  };

  // Live preview of form values before saving
  const formPreview = useMemo(() => {
    const w = Math.max(0, parseFloat(weightGrams) || 0);
    const pg = Math.max(0, parseFloat(buyPricePerGram) || 0);
    const tot = Math.max(0, parseFloat(totalCostInput) || Math.round(w * pg));
    const currentBrandRetail = getBrandPriceFromMarket(brand, market);
    const spreadPct = getBrandSpreadFromMarket(brand);
    const currentBrandBuyback = Math.round(currentBrandRetail * (1 - spreadPct / 100));

    const currentRetailTotal = Math.round(w * currentBrandRetail);
    const currentBuybackTotal = Math.round(w * currentBrandBuyback);
    const diffRetailIdr = currentRetailTotal - tot;
    const diffRetailPct = tot > 0 ? ((diffRetailIdr / tot) * 100).toFixed(2) : '0.00';
    const diffBuybackIdr = currentBuybackTotal - tot;
    const diffBuybackPct = tot > 0 ? ((diffBuybackIdr / tot) * 100).toFixed(2) : '0.00';

    return {
      w,
      pg,
      tot,
      currentBrandRetail,
      currentBrandBuyback,
      currentRetailTotal,
      currentBuybackTotal,
      diffRetailIdr,
      diffRetailPct,
      diffBuybackIdr,
      diffBuybackPct,
    };
  }, [weightGrams, buyPricePerGram, totalCostInput, brand, market]);

  // Real-time client-side calculation for Card Simulasi Jual Sekarang
  const simResult = useMemo(() => {
    const w = Math.max(0, Number(simWeightGrams || 0));
    const cost = Math.max(0, Number(simTotalCostIdr || 0));
    const costPerGram = w > 0 ? Math.round(cost / w) : 0;
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
      costPerGram,
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
        <title>Portofolio Emas &amp; Kalkulator Buyback | SOFIA Market</title>
      </Head>

      <div className="space-y-5 pb-12">
        {/* TOP HEADER */}
        <section className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 pb-2 border-b border-obsidian-800">
          <div>
            <div className="flex flex-wrap items-center gap-2 mb-1">
              <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-mono font-medium bg-amber-500/10 text-amber-400 border border-amber-500/25">
                XAU/USD &amp; LOGAM MULIA INDONESIA
              </span>
              <span className="text-[11px] text-slate-400 font-mono">
                {market?.source || 'Yahoo Finance Live'} • Kurs $1 = {formatIdr(market?.usd_idr || 16500)}
              </span>
            </div>
            <h1 className="text-lg sm:text-xl font-semibold tracking-tight text-white">
              Harga Emas Hari Ini, Portofolio Manual &amp; Simulasi Buyback
            </h1>
            <p className="text-xs text-slate-400 mt-0.5">
              Pantau harga emas Antam, <strong>Hartadinata (EmasKita / HRTA)</strong>, UBS, Galeri 24 &amp; Digital, serta hitung otomatis posisi Untung / Rugi terhadap harga etalase dan harga buyback bersih.
            </p>
          </div>

          <div className="flex items-center gap-2 self-start lg:self-center">
            <button
              type="button"
              onClick={() => loadGoldDashboard(true)}
              disabled={refreshing}
              className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-obsidian-900 hover:bg-obsidian-850 text-slate-200 border border-obsidian-700 text-xs font-medium transition"
            >
              <LucideIcon name="rotate-ccw" className={`w-3.5 h-3.5 text-amber-400 ${refreshing ? 'animate-spin' : ''}`} />
              <span>{refreshing ? 'Memperbarui...' : 'Perbarui Harga'}</span>
            </button>
          </div>
        </section>

        {notice && (
          <div className="px-4 py-2.5 rounded-xl bg-emerald-500/10 border border-emerald-500/25 text-emerald-300 text-xs flex items-center justify-between">
            <span>{notice}</span>
            <button type="button" onClick={() => setNotice('')} className="text-slate-400 hover:text-white">
              ✕
            </button>
          </div>
        )}
        {error && (
          <div className="px-4 py-2.5 rounded-xl bg-rose-500/10 border border-rose-500/25 text-rose-300 text-xs flex items-center justify-between">
            <span>{error}</span>
            <button type="button" onClick={() => setError('')} className="text-slate-400 hover:text-white">
              ✕
            </button>
          </div>
        )}

        {/* SECTION 1: HARGA EMAS HARI INI (5 KARTU UTAMA TERMASUK HARTADINATA) */}
        <section className="space-y-2.5">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Harga Emas Hari Ini (Per 1 Gram)
            </h2>
            <span className="text-[11px] font-mono text-slate-500">
              1 Troy Ounce = 31,1035 Gram
            </span>
          </div>

          {loading ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
              {[1, 2, 3, 4, 5].map((n) => (
                <div key={n} className="h-32 rounded-xl bg-obsidian-900 border border-obsidian-800 animate-pulse p-4" />
              ))}
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
              {/* Card 1: Emas Antam CertiEye */}
              <div className="rounded-xl bg-obsidian-900 border border-obsidian-700/80 p-4 flex flex-col justify-between">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-semibold text-amber-400">
                    Antam CertiEye
                  </span>
                  <span className="text-[10px] font-mono text-slate-400 px-1.5 py-0.5 rounded bg-obsidian-850 border border-obsidian-700">
                    Spread -{market?.antam?.spread_pct || 9}%
                  </span>
                </div>
                <div className="my-2">
                  <div className="text-xl font-semibold font-mono text-white">
                    {formatIdr(market?.antam?.buy_price_idr)}
                  </div>
                  <div className="text-[11px] text-slate-400 mt-0.5 font-mono">
                    Buyback: <strong className="text-emerald-400">{formatIdr(market?.antam?.buyback_price_idr)}</strong>
                  </div>
                </div>
                <div className="pt-2 border-t border-obsidian-800 flex items-center justify-between text-[10px] font-mono text-slate-400">
                  <span>Selisih Spread</span>
                  <span>-{formatIdr(market?.antam?.spread_idr)}/g</span>
                </div>
              </div>

              {/* Card 2: Emas Hartadinata (EmasKita / HRTA) */}
              <div className="rounded-xl bg-obsidian-900 border border-amber-500/35 p-4 flex flex-col justify-between">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-semibold text-amber-300 flex items-center gap-1">
                    <span>Hartadinata (HRTA)</span>
                  </span>
                  <span className="text-[10px] font-mono text-amber-300 px-1.5 py-0.5 rounded bg-amber-500/10 border border-amber-500/25">
                    Spread -{market?.hartadinata?.spread_pct || 8.2}%
                  </span>
                </div>
                <div className="my-2">
                  <div className="text-xl font-semibold font-mono text-white">
                    {formatIdr(market?.hartadinata?.buy_price_idr)}
                  </div>
                  <div className="text-[11px] text-slate-400 mt-0.5 font-mono">
                    Buyback: <strong className="text-emerald-400">{formatIdr(market?.hartadinata?.buyback_price_idr)}</strong>
                  </div>
                </div>
                <div className="pt-2 border-t border-obsidian-800 flex items-center justify-between text-[10px] font-mono text-slate-400">
                  <span>EmasKita 99,99%</span>
                  <span>-{formatIdr(market?.hartadinata?.spread_idr)}/g</span>
                </div>
              </div>

              {/* Card 3: UBS Gold & Galeri 24 */}
              <div className="rounded-xl bg-obsidian-900 border border-obsidian-700/80 p-4 flex flex-col justify-between">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-semibold text-cyan-400">
                    UBS &amp; Galeri 24
                  </span>
                  <span className="text-[10px] font-mono text-slate-400 px-1.5 py-0.5 rounded bg-obsidian-850 border border-obsidian-700">
                    Spread -8.5%
                  </span>
                </div>
                <div className="my-2">
                  <div className="text-xl font-semibold font-mono text-white">
                    {formatIdr(market?.galeri24?.buy_price_idr)}
                  </div>
                  <div className="text-[11px] text-slate-400 mt-0.5 font-mono">
                    Buyback G24: <strong className="text-emerald-400">{formatIdr(market?.galeri24?.buyback_price_idr)}</strong>
                  </div>
                </div>
                <div className="pt-2 border-t border-obsidian-800 flex items-center justify-between text-[10px] font-mono text-slate-400">
                  <span>UBS: {formatIdr(market?.ubs?.buy_price_idr)}</span>
                  <span>BB: {formatIdr(market?.ubs?.buyback_price_idr)}</span>
                </div>
              </div>

              {/* Card 4: Emas Digital */}
              <div className="rounded-xl bg-obsidian-900 border border-obsidian-700/80 p-4 flex flex-col justify-between">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-semibold text-purple-400">
                    Emas Digital
                  </span>
                  <span className="text-[10px] font-mono text-emerald-400 px-1.5 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/20">
                    Spread ~{market?.digital?.spread_pct || 3}%
                  </span>
                </div>
                <div className="my-2">
                  <div className="text-xl font-semibold font-mono text-white">
                    {formatIdr(market?.digital?.buy_price_idr)}
                  </div>
                  <div className="text-[11px] text-slate-400 mt-0.5 font-mono">
                    Buyback: <strong className="text-emerald-400">{formatIdr(market?.digital?.buyback_price_idr)}</strong>
                  </div>
                </div>
                <div className="pt-2 border-t border-obsidian-800 flex items-center justify-between text-[10px] font-mono text-slate-400">
                  <span>Selisih Spread</span>
                  <span>-{formatIdr(market?.digital?.spread_idr)}/g</span>
                </div>
              </div>

              {/* Card 5: Spot Emas Dunia (XAU/USD) */}
              <div className="rounded-xl bg-obsidian-900 border border-obsidian-700/80 p-4 flex flex-col justify-between">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-semibold text-slate-300">
                    Spot Dunia (XAU)
                  </span>
                  <span
                    className={`text-[10px] font-mono font-medium px-1.5 py-0.5 rounded ${
                      Number(market?.change_pct || 0) >= 0
                        ? 'bg-emerald-500/10 text-emerald-400'
                        : 'bg-rose-500/10 text-rose-400'
                    }`}
                  >
                    {Number(market?.change_pct || 0) >= 0 ? '+' : ''}
                    {market?.change_pct || 0}%
                  </span>
                </div>
                <div className="my-2">
                  <div className="text-xl font-semibold font-mono text-white">
                    {formatIdr(market?.spot_idr_per_gram)}
                  </div>
                  <div className="text-[11px] text-slate-400 mt-0.5 font-mono">
                    XAU/USD: <strong className="text-amber-300">{formatUsd(market?.xau_usd)}</strong>/oz
                  </div>
                </div>
                <div className="pt-2 border-t border-obsidian-800 flex items-center justify-between text-[10px] font-mono text-slate-400">
                  <span>L: {formatUsd(market?.day_low_usd)}</span>
                  <span>H: {formatUsd(market?.day_high_usd)}</span>
                </div>
              </div>
            </div>
          )}
        </section>

        {/* SECTION 2: PORTOFOLIO EMAS & SIMULASI JUAL SEKARANG */}
        <section className="grid grid-cols-1 xl:grid-cols-12 gap-5">
          {/* LEFT 7 COLS: RINGKASAN PORTOFOLIO & FORM INPUT */}
          <div className="xl:col-span-7 space-y-4">
            <div className="rounded-xl bg-obsidian-900 border border-obsidian-700/80 p-4 sm:p-5 space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-obsidian-800 pb-3">
                <div>
                  <h2 className="text-base font-semibold text-white">
                    Portofolio Emas &amp; Indikator Untung / Rugi
                  </h2>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Membandingkan harga modal beli Anda per gram dengan harga pasar etalase &amp; harga buyback saat ini.
                  </p>
                </div>

                {Number(portfolio?.total_weight_grams || 0) > 0 ? (
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span
                      className={`px-2.5 py-1 rounded-lg font-mono text-xs font-semibold border ${
                        Number(portfolio?.retail_pnl_idr || 0) > 0
                          ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/25'
                          : Number(portfolio?.retail_pnl_idr || 0) < 0
                          ? 'bg-rose-500/15 text-rose-400 border-rose-500/30'
                          : 'bg-obsidian-850 text-slate-300 border-obsidian-700'
                      }`}
                    >
                      vs Etalase: {Number(portfolio?.retail_pnl_idr || 0) > 0 ? 'UNTUNG' : Number(portfolio?.retail_pnl_idr || 0) < 0 ? 'RUGI' : 'IMPAS'} ({portfolio?.retail_pnl_pct || 0}%)
                    </span>
                    <span
                      className={`px-2.5 py-1 rounded-lg font-mono text-xs font-semibold border ${
                        Number(portfolio?.net_pnl_idr || 0) > 0
                          ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
                          : Number(portfolio?.net_pnl_idr || 0) < 0
                          ? 'bg-rose-500/15 text-rose-300 border-rose-500/30'
                          : 'bg-amber-500/15 text-amber-300 border-amber-500/30'
                      }`}
                    >
                      Buyback: {Number(portfolio?.net_pnl_idr || 0) > 0 ? 'UNTUNG' : Number(portfolio?.net_pnl_idr || 0) < 0 ? 'RUGI' : 'IMPAS'} ({portfolio?.net_pnl_pct || 0}%)
                    </span>
                  </div>
                ) : (
                  <span className="px-2.5 py-1 rounded-lg bg-obsidian-850 border border-obsidian-700 text-slate-400 text-xs">
                    Belum Ada Data
                  </span>
                )}
              </div>

              {/* 4 Summary Stat Cards */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="p-3 rounded-xl bg-obsidian-950 border border-obsidian-800">
                  <div className="text-[11px] text-slate-400">Total Berat Emas</div>
                  <div className="text-lg font-semibold font-mono text-amber-400 mt-0.5">
                    {Number(portfolio?.total_weight_grams || 0).toLocaleString('id-ID')} Gram
                  </div>
                  <div className="text-[11px] text-slate-500 font-mono mt-0.5">
                    {portfolio?.holdings_count || 0} keping tercatat
                  </div>
                </div>

                <div className="p-3 rounded-xl bg-obsidian-950 border border-obsidian-800">
                  <div className="text-[11px] text-slate-400">Total Modal Beli</div>
                  <div className="text-lg font-semibold font-mono text-white mt-0.5">
                    {formatIdr(portfolio?.total_cost_idr || 0)}
                  </div>
                  <div className="text-[11px] text-slate-400 font-mono mt-0.5">
                    Beli: {formatIdr(portfolio?.avg_buy_price_per_gram_idr || 0)}/g
                  </div>
                </div>

                <div className="p-3 rounded-xl bg-obsidian-950 border border-obsidian-800">
                  <div className="text-[11px] text-slate-400">Nilai Harga Etalase</div>
                  <div className="text-lg font-semibold font-mono text-white mt-0.5">
                    {formatIdr(portfolio?.total_retail_value_idr || 0)}
                  </div>
                  <div
                    className={`text-[11px] font-mono font-medium mt-0.5 ${
                      Number(portfolio?.retail_pnl_idr || 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'
                    }`}
                  >
                    {Number(portfolio?.retail_pnl_idr || 0) >= 0 ? '+' : ''}
                    {formatIdr(portfolio?.retail_pnl_idr || 0)} ({portfolio?.retail_pnl_pct || 0}%)
                  </div>
                </div>

                <div className="p-3 rounded-xl bg-obsidian-950 border border-obsidian-800">
                  <div className="text-[11px] text-slate-400">Untung/Rugi Buyback</div>
                  <div
                    className={`text-lg font-semibold font-mono mt-0.5 ${
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
                    className={`text-[11px] font-mono mt-0.5 ${
                      Number(portfolio?.net_pnl_idr || 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'
                    }`}
                  >
                    Cair: {formatIdr(portfolio?.net_sell_now_idr || 0)} ({portfolio?.net_pnl_pct || 0}%)
                  </div>
                </div>
              </div>

              {/* Form Tambah / Edit Portofolio Emas Secara Manual */}
              <form
                onSubmit={handleSaveHolding}
                className="p-4 rounded-xl bg-obsidian-950 border border-obsidian-800 space-y-3.5"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h3 className="text-xs font-semibold text-white uppercase tracking-wider flex items-center gap-2">
                    <span>
                      {editingId !== null
                        ? 'Edit Kepingan Emas Portofolio'
                        : 'Tambah Portofolio Emas Manual'}
                    </span>
                  </h3>
                  <div className="flex items-center gap-3">
                    <button
                      type="button"
                      onClick={() => handleUseCurrentBrandPrice(brand)}
                      className="text-[11px] font-mono text-amber-400 hover:text-amber-300 underline"
                    >
                      Gunakan Harga {brand} Hari Ini ({formatIdr(getBrandPriceFromMarket(brand, market))}/g)
                    </button>
                    {editingId !== null && (
                      <button
                        type="button"
                        onClick={handleCancelEdit}
                        className="text-[11px] text-slate-400 hover:text-white underline"
                      >
                        Batal Edit
                      </button>
                    )}
                  </div>
                </div>

                {/* Quick Gram Preset Pills */}
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="text-[11px] text-slate-400 mr-1">Pilih Cepat Berat:</span>
                  {QUICK_WEIGHTS.map((wg) => {
                    const active = parseFloat(weightGrams) === wg;
                    return (
                      <button
                        key={wg}
                        type="button"
                        onClick={() => {
                          setWeightGrams(String(wg));
                          const p = parseFloat(buyPricePerGram) || 0;
                          if (p > 0) {
                            setTotalCostInput(String(Math.round(p * wg)));
                          }
                        }}
                        className={
                          active
                            ? 'px-2.5 py-1 rounded-lg bg-amber-500/15 text-amber-300 border border-amber-500/35 font-mono text-xs font-medium'
                            : 'px-2.5 py-1 rounded-lg bg-obsidian-900 hover:bg-obsidian-850 text-slate-400 border border-obsidian-700 font-mono text-xs'
                        }
                      >
                        {wg}g
                      </button>
                    );
                  })}
                </div>

                {/* 4 Clear Columns: Brand, Berat (g), Harga Beli per Gram (Rp/g), Total Modal (Rp) */}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                  <div>
                    <label className="block text-[11px] text-slate-400 mb-1">
                      Brand / Jenis Emas
                    </label>
                    <select
                      value={brand}
                      onChange={(e) => {
                        const nextBrand = e.target.value;
                        setBrand(nextBrand);
                        if (!userEditedPrice) {
                          handleUseCurrentBrandPrice(nextBrand);
                        }
                      }}
                      className="w-full px-3 py-2 rounded-lg bg-obsidian-900 border border-obsidian-700 text-xs text-white focus:outline-none focus:border-amber-400"
                    >
                      {BRAND_OPTIONS.map((b) => (
                        <option key={b.id} value={b.id}>
                          {b.label}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-[11px] text-slate-400 mb-1">
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
                        const p = parseFloat(buyPricePerGram) || 0;
                        if (p > 0 && w > 0) {
                          setTotalCostInput(String(Math.round(p * w)));
                        }
                      }}
                      placeholder="Contoh: 10"
                      className="w-full px-3 py-2 rounded-lg bg-obsidian-900 border border-obsidian-700 text-xs text-white font-mono focus:outline-none focus:border-amber-400"
                      required
                    />
                  </div>

                  <div>
                    <label className="block text-[11px] text-amber-300 font-medium mb-1">
                      Harga Beli / Gram (Rp)
                    </label>
                    <input
                      type="number"
                      step="500"
                      min="0"
                      value={buyPricePerGram}
                      onChange={(e) => {
                        setUserEditedPrice(true);
                        setBuyPricePerGram(e.target.value);
                        const p = parseFloat(e.target.value) || 0;
                        const w = parseFloat(weightGrams) || 0;
                        setTotalCostInput(String(Math.round(p * w)));
                      }}
                      placeholder="Contoh: 2700000"
                      className="w-full px-3 py-2 rounded-lg bg-obsidian-900 border border-amber-500/40 text-xs text-white font-mono font-semibold focus:outline-none focus:border-amber-400"
                      required
                    />
                  </div>

                  <div>
                    <label className="block text-[11px] text-slate-400 mb-1">
                      Total Modal ({weightGrams || 0}g) (Rp)
                    </label>
                    <input
                      type="number"
                      step="1000"
                      min="0"
                      value={totalCostInput}
                      onChange={(e) => {
                        setUserEditedPrice(true);
                        setTotalCostInput(e.target.value);
                        const tot = parseFloat(e.target.value) || 0;
                        const w = parseFloat(weightGrams) || 1;
                        setBuyPricePerGram(String(Math.round(tot / w)));
                      }}
                      placeholder="Contoh: 27000000"
                      className="w-full px-3 py-2 rounded-lg bg-obsidian-900 border border-obsidian-700 text-xs text-slate-200 font-mono focus:outline-none focus:border-amber-400"
                      required
                    />
                  </div>
                </div>

                {/* Live Calculation Preview Bar so User immediately sees Untung / Rugi before saving */}
                {formPreview.w > 0 && formPreview.pg > 0 && (
                  <div className="p-3 rounded-lg bg-obsidian-900 border border-obsidian-800 flex flex-wrap items-center justify-between gap-2 text-[11px] font-mono">
                    <div className="text-slate-300">
                      Modal: <strong className="text-white">{formPreview.w}g × {formatIdr(formPreview.pg)}/g = {formatIdr(formPreview.tot)}</strong>
                      <span className="text-slate-500 ml-2">
                        (Harga {brand} sekarang: {formatIdr(formPreview.currentBrandRetail)}/g)
                      </span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span
                        className={
                          formPreview.diffRetailIdr >= 0 ? 'text-emerald-400 font-semibold' : 'text-rose-400 font-semibold'
                        }
                      >
                        vs Etalase: {formPreview.diffRetailIdr >= 0 ? 'UNTUNG +' : 'RUGI '}
                        {formatIdr(formPreview.diffRetailIdr)} ({formPreview.diffRetailPct}%)
                      </span>
                      <span
                        className={
                          formPreview.diffBuybackIdr >= 0 ? 'text-emerald-400 font-semibold' : 'text-rose-400 font-semibold'
                        }
                      >
                        vs Buyback: {formPreview.diffBuybackIdr >= 0 ? 'UNTUNG +' : 'RUGI '}
                        {formatIdr(formPreview.diffBuybackIdr)} ({formPreview.diffBuybackPct}%)
                      </span>
                    </div>
                  </div>
                )}

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 items-end">
                  <div>
                    <label className="block text-[11px] text-slate-400 mb-1">
                      Label / Catatan Kepingan
                    </label>
                    <input
                      type="text"
                      value={label}
                      onChange={(e) => setLabel(e.target.value)}
                      placeholder={`Emas ${brand} ${weightGrams || 1}g`}
                      className="w-full px-3 py-2 rounded-lg bg-obsidian-900 border border-obsidian-700 text-xs text-white focus:outline-none focus:border-amber-400"
                    />
                  </div>

                  <div>
                    <label className="block text-[11px] text-slate-400 mb-1">
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
                    className="w-full py-2 px-4 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-obsidian-950 font-semibold text-xs transition"
                  >
                    {submitting
                      ? 'Menyimpan...'
                      : editingId !== null
                      ? 'Simpan Perubahan'
                      : '+ Simpan ke Portofolio'}
                  </button>
                </div>
              </form>

              {/* Daftar Portofolio Emas Manual */}
              <div className="space-y-2.5">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                    Daftar Kepingan Emas Anda ({holdings.length})
                  </h3>
                  {holdings.length > 0 && (
                    <button
                      type="button"
                      onClick={() => setSimSource('portfolio')}
                      className="text-[11px] font-mono text-amber-400 hover:underline"
                    >
                      Simulasikan Jual Semua ({portfolio?.total_weight_grams}g)
                    </button>
                  )}
                </div>

                {holdings.length === 0 ? (
                  <div className="p-6 rounded-xl bg-obsidian-950 border border-obsidian-800 text-center space-y-1">
                    <div className="text-sm font-medium text-slate-300">
                      Portofolio Emas Masih Kosong
                    </div>
                    <p className="text-xs text-slate-400 max-w-md mx-auto">
                      Tambahkan emas yang Anda miliki pada form di atas untuk memantau posisi Untung / Rugi secara real-time.
                    </p>
                  </div>
                ) : (
                  <div className="overflow-x-auto rounded-xl border border-obsidian-800">
                    <table className="w-full text-left border-collapse text-xs font-mono">
                      <thead>
                        <tr className="bg-obsidian-950 text-slate-400 border-b border-obsidian-800 text-[10px] uppercase font-sans">
                          <th className="py-2.5 px-3">Kepingan &amp; Brand</th>
                          <th className="py-2.5 px-3 text-right">Berat</th>
                          <th className="py-2.5 px-3 text-right">Harga Beli vs Sekarang</th>
                          <th className="py-2.5 px-3 text-right">Modal vs Nilai</th>
                          <th className="py-2.5 px-3 text-center">Status Untung / Rugi</th>
                          <th className="py-2.5 px-3 text-right">Aksi</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-obsidian-800/80 bg-obsidian-900/40">
                        {holdings.map((h) => {
                          const buybackPnl = Number(h.buyback_pnl_idr || 0);
                          const retailPnl = Number(h.retail_pnl_idr || 0);
                          const isProfitBuyback = buybackPnl > 0;
                          const isProfitRetail = retailPnl > 0;
                          return (
                            <tr key={h.id} className="hover:bg-obsidian-850/60 transition">
                              <td className="py-2.5 px-3 font-sans">
                                <div className="font-semibold text-white">{h.label}</div>
                                <div className="text-[10px] text-slate-400">
                                  {h.brand} • Beli: {h.purchased_at || '-'}
                                </div>
                              </td>
                              <td className="py-2.5 px-3 text-right font-semibold text-amber-400">
                                {h.weight_grams}g
                              </td>
                              <td className="py-2.5 px-3 text-right">
                                <div className="text-white">
                                  Beli: <strong>{formatIdr(h.buy_price_per_gram_idr)}</strong>/g
                                </div>
                                <div className="text-[10px] text-slate-400">
                                  Skrg: {formatIdr(h.current_retail_per_gram_idr)}/g (BB: {formatIdr(h.current_buyback_per_gram_idr)})
                                </div>
                              </td>
                              <td className="py-2.5 px-3 text-right">
                                <div className="text-white font-medium">
                                  Modal: {formatIdr(h.total_cost_idr)}
                                </div>
                                <div className="text-[10px] text-slate-400">
                                  Etalase: {formatIdr(h.retail_value_idr)} • BB: {formatIdr(h.buyback_value_idr)}
                                </div>
                              </td>
                              <td className="py-2.5 px-3 text-center">
                                <div className="flex flex-col items-center gap-1">
                                  <span
                                    className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold border ${
                                      isProfitRetail
                                        ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/25'
                                        : retailPnl < 0
                                        ? 'bg-rose-500/15 text-rose-400 border-rose-500/30'
                                        : 'bg-obsidian-850 text-slate-300 border-obsidian-700'
                                    }`}
                                  >
                                    Etalase: {isProfitRetail ? 'UNTUNG +' : retailPnl < 0 ? 'RUGI ' : 'IMPAS '}
                                    {formatIdr(retailPnl)} ({h.retail_pnl_pct}%)
                                  </span>
                                  <span
                                    className={`text-[10px] font-medium ${
                                      isProfitBuyback
                                        ? 'text-emerald-400'
                                        : buybackPnl < 0
                                        ? 'text-rose-400'
                                        : 'text-slate-400'
                                    }`}
                                  >
                                    Buyback: {isProfitBuyback ? 'UNTUNG +' : buybackPnl < 0 ? 'RUGI ' : 'IMPAS '}
                                    {formatIdr(buybackPnl)} ({h.buyback_pnl_pct}%)
                                  </span>
                                </div>
                              </td>
                              <td className="py-2.5 px-3 text-right font-sans">
                                <div className="flex items-center justify-end gap-1.5">
                                  <button
                                    type="button"
                                    onClick={() => handleStartEditHolding(h)}
                                    className="px-2 py-1 rounded bg-obsidian-850 hover:bg-obsidian-800 text-slate-300 border border-obsidian-700 text-[10px] font-medium"
                                    title="Edit harga beli atau berat"
                                  >
                                    Edit
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => handleSimulateSingleHolding(h)}
                                    className="px-2 py-1 rounded bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 border border-amber-500/25 text-[10px] font-medium"
                                    title="Simulasikan Jual Sekarang"
                                  >
                                    Simulasi
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => handleDeleteHolding(h.id, h.label)}
                                    className="p-1.5 rounded bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/25"
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
            <div className="rounded-xl bg-obsidian-900 border border-obsidian-700/80 p-4 sm:p-5 space-y-4 sticky top-4">
              <div className="border-b border-obsidian-800 pb-3">
                <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-mono font-medium bg-amber-500/10 text-amber-400 border border-amber-500/25 mb-1">
                  KALKULATOR BUYBACK &amp; PAJAK
                </span>
                <h2 className="text-base font-semibold text-white">
                  Simulasi Jual Sekarang (Spread &amp; Pajak)
                </h2>
                <p className="text-xs text-slate-400 mt-0.5">
                  Perkiraan dana bersih yang diterima setelah potongan spread buyback &amp; PPh 22.
                </p>
              </div>

              {/* Mode Sumber Simulasi */}
              <div className="grid grid-cols-2 gap-1.5 p-1 rounded-xl bg-obsidian-950 border border-obsidian-800 text-xs">
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
                      ? 'py-1.5 px-3 rounded-lg bg-obsidian-800 text-white border border-obsidian-700 font-medium'
                      : 'py-1.5 px-3 rounded-lg text-slate-400 hover:text-slate-200'
                  }
                >
                  Dari Portofolio ({Number(portfolio?.total_weight_grams || 0)}g)
                </button>
                <button
                  type="button"
                  onClick={() => setSimSource('custom')}
                  className={
                    simSource === 'custom'
                      ? 'py-1.5 px-3 rounded-lg bg-obsidian-800 text-white border border-obsidian-700 font-medium'
                      : 'py-1.5 px-3 rounded-lg text-slate-400 hover:text-slate-200'
                  }
                >
                  Simulasi Kustom
                </button>
              </div>

              {/* Input Gram, Modal Beli, & Harga Acuan */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 text-xs">
                <div>
                  <label className="block text-[10px] text-slate-400 mb-1">
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
                    className="w-full px-2.5 py-2 rounded-lg bg-obsidian-950 border border-obsidian-700 text-amber-300 font-mono font-semibold focus:outline-none focus:border-amber-400"
                  />
                </div>

                <div>
                  <label className="block text-[10px] text-slate-400 mb-1">
                    Total Modal Beli (Rp)
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
                    className="w-full px-2.5 py-2 rounded-lg bg-obsidian-950 border border-obsidian-700 text-white font-mono font-semibold focus:outline-none focus:border-amber-400"
                  />
                </div>

                <div>
                  <label className="block text-[10px] text-slate-400 mb-1">
                    Harga Emas Sekarang /g
                  </label>
                  <input
                    type="number"
                    step="500"
                    min="0"
                    value={simRetailPricePerGram}
                    onChange={(e) => setSimRetailPricePerGram(parseFloat(e.target.value) || 0)}
                    className="w-full px-2.5 py-2 rounded-lg bg-obsidian-950 border border-obsidian-700 text-cyan-300 font-mono font-semibold focus:outline-none focus:border-amber-400"
                  />
                </div>
              </div>

              {/* Pengaturan Spread Buyback (%) */}
              <div className="p-3 rounded-xl bg-obsidian-950 border border-obsidian-800 space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-300 font-medium">
                    1. Perkiraan Spread Buyback:
                  </span>
                  <span className="text-amber-400 font-mono font-semibold">{simSpreadPct}%</span>
                </div>

                <div className="grid grid-cols-4 gap-1.5 font-mono text-[10px]">
                  {[
                    { label: 'Digital (3%)', val: 3.0 },
                    { label: 'HRTA (8.2%)', val: 8.2 },
                    { label: 'UBS/G24 (8.5%)', val: 8.5 },
                    { label: 'Antam (9%)', val: 9.0 },
                  ].map((sp) => (
                    <button
                      key={sp.label}
                      type="button"
                      onClick={() => setSimSpreadPct(sp.val)}
                      className={
                        simSpreadPct === sp.val
                          ? 'py-1.5 px-1.5 rounded-lg bg-amber-500/15 text-amber-300 border border-amber-500/35 font-medium'
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
                    step="0.1"
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
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-300 font-medium">
                    2. Pajak Buyback PPh 22 &amp; Materai:
                  </span>
                  <span className="text-rose-400 font-mono font-semibold">{simResult.appliedTaxPct}%</span>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5 font-mono text-[10px]">
                  <button
                    type="button"
                    onClick={() => setSimTaxMode('auto_npwp')}
                    className={
                      simTaxMode === 'auto_npwp'
                        ? 'py-1.5 px-2 rounded-lg bg-emerald-500/15 text-emerald-300 border border-emerald-500/35 font-medium'
                        : 'py-1.5 px-2 rounded-lg bg-obsidian-900 text-slate-400 border border-obsidian-800'
                    }
                  >
                    NPWP (1.5%)
                  </button>
                  <button
                    type="button"
                    onClick={() => setSimTaxMode('auto_non_npwp')}
                    className={
                      simTaxMode === 'auto_non_npwp'
                        ? 'py-1.5 px-2 rounded-lg bg-amber-500/15 text-amber-300 border border-amber-500/35 font-medium'
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
                        ? 'py-1.5 px-2 rounded-lg bg-cyan-500/15 text-cyan-300 border border-cyan-500/35 font-medium'
                        : 'py-1.5 px-2 rounded-lg bg-obsidian-900 text-slate-400 border border-obsidian-800'
                    }
                  >
                    Bebas (0%)
                  </button>
                  <button
                    type="button"
                    onClick={() => setSimTaxMode('custom')}
                    className={
                      simTaxMode === 'custom'
                        ? 'py-1.5 px-2 rounded-lg bg-purple-500/15 text-purple-300 border border-purple-500/35 font-medium'
                        : 'py-1.5 px-2 rounded-lg bg-obsidian-900 text-slate-400 border border-obsidian-800'
                    }
                  >
                    Kustom (%)
                  </button>
                </div>

                {simTaxMode === 'custom' && (
                  <div className="flex items-center gap-2 pt-1 font-mono text-xs">
                    <span className="text-slate-400">Pajak Kustom (%):</span>
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

                <label className="flex items-center gap-2 text-[11px] text-slate-400 pt-1 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={simIncludeStampDuty}
                    onChange={(e) => setSimIncludeStampDuty(e.target.checked)}
                    className="rounded accent-amber-400"
                  />
                  <span>Potongan Bea Materai Rp 10.000 (buyback &gt; Rp 5 Juta)</span>
                </label>
              </div>

              {/* RINCIAN KALKULASI SIMULASI JUAL SEKARANG */}
              <div className="p-4 rounded-xl bg-obsidian-950 border border-obsidian-800 space-y-2 font-mono text-xs">
                <div className="flex items-center justify-between text-slate-400">
                  <span>Modal Beli ({simResult.w}g @ {formatIdr(simResult.costPerGram)}/g):</span>
                  <span className="font-semibold text-white">{formatIdr(simResult.cost)}</span>
                </div>

                <div className="flex items-center justify-between text-slate-300">
                  <span>Nilai Etalase Sekarang ({simResult.w}g @ {formatIdr(simResult.retailPerGram)}/g):</span>
                  <span className="font-semibold text-white">{formatIdr(simResult.grossRetailIdr)}</span>
                </div>

                <div className="flex items-center justify-between text-[11px] pb-1 border-b border-obsidian-800">
                  <span className="text-slate-400">Selisih Harga Etalase vs Modal Beli:</span>
                  <span className={simResult.marketPnlIdr >= 0 ? 'text-emerald-400 font-semibold' : 'text-rose-400 font-semibold'}>
                    {simResult.marketPnlIdr >= 0 ? 'UNTUNG +' : 'RUGI '}
                    {formatIdr(simResult.marketPnlIdr)} ({simResult.marketPnlPct >= 0 ? '+' : ''}{simResult.marketPnlPct}%)
                  </span>
                </div>

                <div className="flex items-center justify-between text-rose-400 pt-1">
                  <span>(-) Spread Buyback ({simResult.spreadPct}%):</span>
                  <span>-{formatIdr(simResult.spreadDeductionIdr)}</span>
                </div>

                <div className="flex items-center justify-between text-slate-200">
                  <span>Nilai Buyback Kotor (@{formatIdr(simResult.effectiveBuybackPerGram)}/g):</span>
                  <span className="font-semibold">{formatIdr(simResult.grossBuybackIdr)}</span>
                </div>

                <div className="flex items-center justify-between text-rose-400">
                  <span>(-) {simResult.taxLabel}:</span>
                  <span>-{formatIdr(simResult.taxDeductionIdr)}</span>
                </div>

                {simResult.stampDutyIdr > 0 && (
                  <div className="flex items-center justify-between text-rose-400">
                    <span>(-) Bea Materai:</span>
                    <span>-{formatIdr(simResult.stampDutyIdr)}</span>
                  </div>
                )}

                <div className="border-t border-obsidian-700 pt-2.5 flex items-center justify-between">
                  <div>
                    <div className="text-[10px] uppercase text-slate-400 font-sans">
                      Dana Bersih Diterima (Net Cash)
                    </div>
                    <div className="text-xl font-semibold text-emerald-400 mt-0.5">
                      {formatIdr(simResult.netPayoutIdr)}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-[10px] uppercase text-slate-400 font-sans">Modal Awal</div>
                    <div className="text-sm font-semibold text-slate-200">{formatIdr(simResult.cost)}</div>
                  </div>
                </div>

                {/* HASIL UNTUNG / RUGI BERSIH JIKA DIJUAL SEKARANG */}
                <div
                  className={`p-3 rounded-xl border mt-2 flex items-center justify-between ${
                    simResult.netPnlIdr > 0
                      ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                      : simResult.netPnlIdr < 0
                      ? 'bg-rose-500/10 border-rose-500/30 text-rose-300'
                      : 'bg-amber-500/10 border-amber-500/30 text-amber-300'
                  }`}
                >
                  <div>
                    <div className="text-[10px] uppercase font-sans font-semibold opacity-80">
                      Status Jika Dijual Sekarang (Setelah Spread &amp; Pajak)
                    </div>
                    <div className="text-sm font-semibold mt-0.5">
                      {simResult.netPnlIdr > 0
                        ? `UNTUNG BERSIH +${formatIdr(simResult.netPnlIdr)} (+${simResult.netPnlPct}%)`
                        : simResult.netPnlIdr < 0
                        ? `RUGI BERSIH ${formatIdr(simResult.netPnlIdr)} (${simResult.netPnlPct}%)`
                        : 'IMPAS / BREAK-EVEN (Rp 0)'}
                    </div>
                  </div>
                </div>

                <div className="text-[11px] text-slate-400 pt-1 flex items-center justify-between">
                  <span>Harga Buyback Minimal Agar Impas:</span>
                  <strong className="text-amber-300">{formatIdr(simResult.breakevenBuybackPerGram)}/gram</strong>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* SECTION 3: TABEL PECAHAN EMAS (ANTAM & HARTADINATA) & GRAFIK 30 HARI */}
        <section className="grid grid-cols-1 lg:grid-cols-12 gap-5">
          <div className="lg:col-span-7 rounded-xl bg-obsidian-900 border border-obsidian-700/80 p-4 sm:p-5 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-obsidian-800 pb-3">
              <div>
                <h3 className="text-sm font-semibold text-white">
                  Daftar Harga Pecahan Emas Batangan (0.5g – 100g)
                </h3>
                <p className="text-xs text-slate-400">
                  Pilih brand untuk melihat harga beli dan estimasi buyback per pecahan.
                </p>
              </div>
              <div className="flex items-center bg-obsidian-950 p-0.5 rounded-lg border border-obsidian-800 text-xs">
                <button
                  type="button"
                  onClick={() => setDenomBrand('antam')}
                  className={
                    denomBrand === 'antam'
                      ? 'px-2.5 py-1 rounded-md bg-obsidian-800 text-amber-300 border border-obsidian-700 font-medium'
                      : 'px-2.5 py-1 rounded-md text-slate-400 hover:text-slate-200'
                  }
                >
                  Antam CertiEye
                </button>
                <button
                  type="button"
                  onClick={() => setDenomBrand('hartadinata')}
                  className={
                    denomBrand === 'hartadinata'
                      ? 'px-2.5 py-1 rounded-md bg-obsidian-800 text-amber-300 border border-obsidian-700 font-medium'
                      : 'px-2.5 py-1 rounded-md text-slate-400 hover:text-slate-200'
                  }
                >
                  Hartadinata (HRTA)
                </button>
              </div>
            </div>

            <div className="overflow-x-auto rounded-xl border border-obsidian-800">
              <table className="w-full text-left border-collapse text-xs font-mono">
                <thead>
                  <tr className="bg-obsidian-950 text-slate-400 border-b border-obsidian-800 text-[10px] uppercase font-sans">
                    <th className="py-2.5 px-3">Pecahan</th>
                    <th className="py-2.5 px-3 text-right">
                      Harga Beli ({denomBrand === 'hartadinata' ? 'Hartadinata' : 'Antam'})
                    </th>
                    <th className="py-2.5 px-3 text-right">Estimasi Buyback</th>
                    <th className="py-2.5 px-3 text-right">Simulasi</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-obsidian-800/80">
                  {(market?.denominations || []).map((d: any) => {
                    const buyIdr =
                      denomBrand === 'hartadinata'
                        ? d.hartadinata_buy_idr || d.antam_buy_idr
                        : d.antam_buy_idr;
                    const buybackIdr =
                      denomBrand === 'hartadinata'
                        ? d.hartadinata_buyback_idr || d.antam_buyback_idr
                        : d.antam_buyback_idr;
                    return (
                      <tr key={d.weight_grams} className="hover:bg-obsidian-850/60 transition">
                        <td className="py-2 px-3 font-semibold text-amber-400">{d.label}</td>
                        <td className="py-2 px-3 text-right text-white">{formatIdr(buyIdr)}</td>
                        <td className="py-2 px-3 text-right text-emerald-400 font-medium">
                          {formatIdr(buybackIdr)}
                        </td>
                        <td className="py-2 px-3 text-right font-sans">
                          <button
                            type="button"
                            onClick={() => {
                              setSimSource('custom');
                              setSimWeightGrams(d.weight_grams);
                              setSimTotalCostIdr(buyIdr);
                              setSimRetailPricePerGram(Math.round(buyIdr / d.weight_grams));
                              setSimSpreadPct(denomBrand === 'hartadinata' ? 8.2 : 9.0);
                            }}
                            className="px-2 py-0.5 rounded bg-obsidian-850 hover:bg-amber-500/15 text-slate-300 hover:text-amber-300 border border-obsidian-700 text-[10px]"
                          >
                            Tes {d.weight_grams}g
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Grafik Tren Harga Emas 30 Hari Terakhir */}
          <div className="lg:col-span-5 rounded-xl bg-obsidian-900 border border-obsidian-700/80 p-4 sm:p-5 flex flex-col justify-between space-y-3">
            <div>
              <div className="border-b border-obsidian-800 pb-3">
                <h3 className="text-sm font-semibold text-white">
                  Tren Harga Emas 30 Hari Terakhir
                </h3>
                <p className="text-xs text-slate-400">
                  Pergerakan harga emas per gram dalam 30 hari perdagangan terakhir.
                </p>
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
                          title={`${pt.date}: Antam ${formatIdr(pt.antam_buy_idr)} | Hartadinata ${formatIdr(pt.hartadinata_buy_idr || pt.antam_buy_idr)} | Buyback ${formatIdr(pt.antam_buyback_idr)}`}
                        >
                          <div
                            style={{ height: `${heightPct}%` }}
                            className="w-full rounded-t bg-amber-500/60 group-hover:bg-amber-400 transition-all"
                          />
                        </div>
                      );
                    })}
                  </div>
                  <div className="flex items-center justify-between text-[10px] font-mono text-slate-400 px-1">
                    <span>{history30d[0]?.date}</span>
                    <span>Min: {formatIdr(minHistPrice)}/g</span>
                    <span>Max: {formatIdr(maxHistPrice)}/g</span>
                    <span>{history30d[history30d.length - 1]?.date}</span>
                  </div>
                </div>
              ) : (
                <div className="h-48 flex items-center justify-center text-xs text-slate-500">
                  Memuat riwayat grafik 30 hari...
                </div>
              )}
            </div>

            <div className="p-3 rounded-xl bg-obsidian-950 border border-obsidian-800 text-xs text-slate-400 leading-relaxed">
              <strong className="text-slate-200">Catatan Perhitungan:</strong> Jika Anda membeli emas seharga{' '}
              <strong className="text-white font-mono">Rp 2.700.000/gram</strong> dan harga emas saat ini sekitar{' '}
              <strong className="text-white font-mono">Rp 2.600.000/gram</strong>, maka posisi Anda otomatis tercatat{' '}
              <strong className="text-rose-400">RUGI</strong> baik terhadap harga etalase maupun harga buyback.
            </div>
          </div>
        </section>
      </div>
    </>
  );
}
