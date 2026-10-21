import React, { useState, useMemo } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { formatIdr } from '@/lib/api';
import { LucideIcon } from '@/components/LucideIcon';
import { useUltrawide, toggleUltrawide } from '@/lib/useUltrawide';

// Helper function to convert number to Indonesian words (Terbilang)
function angkaKeTerbilang(nilai: number): string {
  if (nilai === 0) return 'Nol Rupiah';
  if (nilai < 0) return 'Minus ' + angkaKeTerbilang(Math.abs(nilai));

  const satuan = ['', 'Satu', 'Dua', 'Tiga', 'Empat', 'Lima', 'Enam', 'Tujuh', 'Delapan', 'Sembilan', 'Sepuluh', 'Sebelas'];

  function terbilang(n: number): string {
    n = Math.floor(n);
    if (n < 12) return satuan[n];
    if (n < 20) return terbilang(n - 10) + ' Belas';
    if (n < 100) return terbilang(Math.floor(n / 10)) + ' Puluh ' + terbilang(n % 10);
    if (n < 200) return 'Seratus ' + terbilang(n - 100);
    if (n < 1000) return terbilang(Math.floor(n / 100)) + ' Ratus ' + terbilang(n % 100);
    if (n < 2000) return 'Seribu ' + terbilang(n - 1000);
    if (n < 1000000) return terbilang(Math.floor(n / 1000)) + ' Ribu ' + terbilang(n % 1000);
    if (n < 1000000000) return terbilang(Math.floor(n / 1000000)) + ' Juta ' + terbilang(n % 1000000);
    if (n < 1000000000000) return terbilang(Math.floor(n / 1000000000)) + ' Miliar ' + terbilang(n % 1000000000);
    if (n < 1000000000000000) return terbilang(Math.floor(n / 1000000000000)) + ' Triliun ' + terbilang(n % 1000000000000);
    return n.toString();
  }

  const result = terbilang(nilai).replace(/\s+/g, ' ').trim();
  return result + ' Rupiah';
}

const NOMINAL_PRESETS = [
  { label: '5 Juta', value: 5000000 },
  { label: '10 Juta', value: 10000000 },
  { label: '25 Juta', value: 25000000 },
  { label: '50 Juta', value: 50000000 },
  { label: '100 Juta', value: 100000000 },
  { label: '500 Juta', value: 500000000 },
  { label: '1 Miliar', value: 1000000000 },
  { label: '2 Miliar', value: 2000000000 },
];

const DEPOSITO_PRESETS = [
  { id: 'bumn', name: 'Bank BUMN / Buku IV', rate: 3.5, desc: 'Mandiri, BRI, BCA, BNI' },
  { id: 'swasta', name: 'Bank Swasta Nasional', rate: 4.25, desc: 'CIMB, Danamon, Panin' },
  { id: 'syariah', name: 'Deposito Syariah (Mudharabah)', rate: 5.25, desc: 'BSI, Muamalat (Bagi Hasil / Nisbah)' },
  { id: 'digital', name: 'Bank Digital', rate: 5.75, desc: 'Seabank, Krom, Jago, Neobank' },
  { id: 'bpr', name: 'BPR Resmi OJK', rate: 6.75, desc: 'Batas Maks TBP LPS BPR' },
];

const BOND_PRESETS = [
  { id: 'ori', name: 'ORI (Obligasi Negara Ritel)', rate: 6.4, desc: 'Kupon Tetap (Fixed), Bulanan', tenor: 36 },
  { id: 'sr', name: 'SR (Sukuk Ritel Syariah)', rate: 6.35, desc: 'Prinsip Syariah, Kupon Bulanan', tenor: 36 },
  { id: 'sbr', name: 'SBR / ST (Sukuk Tabungan)', rate: 6.65, desc: 'Floating with Floor, Bulanan', tenor: 24 },
  { id: 'fr', name: 'FR (Fixed Rate Pasar Sekunder)', rate: 6.95, desc: 'Benchmark Tenor Panjang', tenor: 60 },
  { id: 'corp', name: 'Obligasi Korporasi IdAAA', rate: 8.25, desc: 'Perusahaan BUMN / Swasta Prima', tenor: 36 },
];

const DEPOSITO_TENOR_PRESETS = [
  { id: '7d', label: '7 Hari', days: 7, displayLabel: '7 Hari' },
  { id: '14d', label: '14 Hari', days: 14, displayLabel: '14 Hari' },
  { id: '1m', label: '1 Bln', days: 30, displayLabel: '1 Bulan' },
  { id: '3m', label: '3 Bln', days: 90, displayLabel: '3 Bulan' },
  { id: '6m', label: '6 Bln', days: 180, displayLabel: '6 Bulan' },
  { id: '12m', label: '1 Thn', days: 365, displayLabel: '12 Bulan (1 Thn)' },
  { id: '24m', label: '2 Thn', days: 730, displayLabel: '24 Bulan (2 Thn)' },
  { id: '36m', label: '3 Thn', days: 1095, displayLabel: '36 Bulan (3 Thn)' },
];

export default function CalculatorPage() {
  const isUltrawide = useUltrawide();

  // 1. Unified Single Principal Input
  const [principal, setPrincipal] = useState<number>(10000000); // 10 juta default
  const [principalInputStr, setPrincipalInputStr] = useState<string>('10.000.000');

  // 2. Deposito Configuration
  const [depositoRate, setDepositoRate] = useState<number>(5.0); // 5.0% p.a.
  const [depositoTenorId, setDepositoTenorId] = useState<string>('12m'); // default 12 bulan
  const [depositoActivePreset, setDepositoActivePreset] = useState<string>('digital');

  // 3. Obligasi Configuration
  const [bondRate, setBondRate] = useState<number>(6.65); // 6.65% p.a.
  const [bondTenorMonths, setBondTenorMonths] = useState<number>(36); // 36 bulan (3 tahun)
  const [bondActivePreset, setBondActivePreset] = useState<string>('sbr');
  const [bondFrequency, setBondFrequency] = useState<'monthly' | 'semi-annual'>('monthly');

  // 4. View & Simulation Tabs
  const [showSchedule, setShowSchedule] = useState<boolean>(false);
  const [copiedNotice, setCopiedNotice] = useState<boolean>(false);

  // Sync Input String with Number
  const handlePrincipalChange = (valStr: string) => {
    const rawDigits = valStr.replace(/\D/g, '');
    const num = Number(rawDigits || 0);
    setPrincipal(num);
    setPrincipalInputStr(num > 0 ? num.toLocaleString('id-ID') : '');
  };

  const handleSelectPresetPrincipal = (val: number) => {
    setPrincipal(val);
    setPrincipalInputStr(val.toLocaleString('id-ID'));
  };

  const handleSelectDepositoPreset = (preset: typeof DEPOSITO_PRESETS[0]) => {
    setDepositoActivePreset(preset.id);
    setDepositoRate(preset.rate);
  };

  const handleSelectBondPreset = (preset: typeof BOND_PRESETS[0]) => {
    setBondActivePreset(preset.id);
    setBondRate(preset.rate);
    setBondTenorMonths(preset.tenor);
  };

  const activeTenorPreset = useMemo(() => {
    return DEPOSITO_TENOR_PRESETS.find((t) => t.id === depositoTenorId) || DEPOSITO_TENOR_PRESETS[5];
  }, [depositoTenorId]);

  // --- CALCULATIONS: DEPOSITO ---
  const depositoCalc = useMemo(() => {
    const P = principal;
    const rateAnnual = depositoRate / 100;
    const days = activeTenorPreset.days;

    // Perhitungan Bunga Kotor Standar BI: P * (r / 365) * hari
    const grossInterest = P * (rateAnnual / 365) * days;

    // Pajak Deposito Indonesia:
    // PP No. 131/2000: Nominal > Rp 7.500.000 dikenakan PPh Final 20%. Di bawah 7.5jt tarif 0%.
    const isTaxExempt = P <= 7500000;
    const taxRate = isTaxExempt ? 0 : 0.2;
    const taxAmount = grossInterest * taxRate;
    const netInterest = grossInterest - taxAmount;

    // Payout dan per bulan / per periode
    const totalPayout = P + netInterest;
    const monthlyGross = (grossInterest / days) * 30.4167;
    const monthlyNet = (netInterest / days) * 30.4167;
    const effectiveNetRateAnnual = depositoRate * (1 - taxRate);

    // LPS Guarantee Check: TBP Bank Umum 4.25%, Max Simpanan Rp 2 Miliar
    const isUnderLpsCeiling = P <= 2000000000;
    const isLpsRateEligible = depositoRate <= 4.25;
    const lpsGuaranteed = isUnderLpsCeiling && isLpsRateEligible;

    return {
      grossInterest,
      taxRate,
      taxAmount,
      netInterest,
      totalPayout,
      monthlyGross,
      monthlyNet,
      effectiveNetRateAnnual,
      isTaxExempt,
      lpsGuaranteed,
      isUnderLpsCeiling,
      isLpsRateEligible,
      days,
      displayLabel: activeTenorPreset.displayLabel,
    };
  }, [principal, depositoRate, activeTenorPreset]);

  // --- CALCULATIONS: OBLIGASI / SBN ---
  const bondCalc = useMemo(() => {
    const P = principal;
    const rateAnnual = bondRate / 100;
    const months = bondTenorMonths;

    // Kupon Kotor Tahunan & Total Tenor
    const annualGross = P * rateAnnual;
    const monthlyGross = annualGross / 12;
    const totalGross = annualGross * (months / 12);

    // Pajak Obligasi Indonesia:
    // PP No. 91 Tahun 2021: PPh Final Kupon Obligasi untuk WPDN dipangkas menjadi 10%
    const taxRate = 0.1;
    const monthlyTax = monthlyGross * taxRate;
    const totalTax = totalGross * taxRate;

    // Kupon Bersih
    const monthlyNet = monthlyGross - monthlyTax;
    const annualNet = annualGross * (1 - taxRate);
    const totalNet = totalGross - totalTax;

    const totalPayout = P + totalNet;
    const effectiveNetRateAnnual = bondRate * (1 - taxRate);

    return {
      annualGross,
      monthlyGross,
      totalGross,
      taxRate,
      monthlyTax,
      totalTax,
      monthlyNet,
      annualNet,
      totalNet,
      totalPayout,
      effectiveNetRateAnnual,
    };
  }, [principal, bondRate, bondTenorMonths]);

  // --- COMPARISON CALCULATIONS (Normalized 12 Months / 1 Year) ---
  const comparison = useMemo(() => {
    const P = principal;

    // 1 Tahun (12 Bulan) Deposito
    const depGross1Y = P * (depositoRate / 100);
    const depTaxRate = P <= 7500000 ? 0 : 0.2;
    const depTax1Y = depGross1Y * depTaxRate;
    const depNet1Y = depGross1Y - depTax1Y;

    // 1 Tahun (12 Bulan) Obligasi
    const bondGross1Y = P * (bondRate / 100);
    const bondTax1Y = bondGross1Y * 0.1;
    const bondNet1Y = bondGross1Y - bondTax1Y;

    // Selisih Net Profit 1 Tahun
    const netDifference1Y = bondNet1Y - depNet1Y;
    const pctDifference1Y = depNet1Y > 0 ? ((bondNet1Y - depNet1Y) / depNet1Y) * 100 : 0;

    // Penghematan Pajak (Tax Advantage Obligasi)
    const taxSavings1Y = depTax1Y - bondTax1Y;

    // Perbandingan Total Tenor Aktual
    const totalNetDiff = bondCalc.totalNet - depositoCalc.netInterest;

    return {
      depNet1Y,
      bondNet1Y,
      netDifference1Y,
      pctDifference1Y,
      depTax1Y,
      bondTax1Y,
      taxSavings1Y,
      totalNetDiff,
    };
  }, [principal, depositoRate, bondRate, depositoCalc, bondCalc]);

  // Copy Summary to Clipboard
  const handleCopySummary = () => {
    const summaryText = `SIMULASI FINANSIAL SOFIA: DEPOSITO VS OBLIGASI
Pokok Investasi: ${formatIdr(principal)} (${angkaKeTerbilang(principal)})

1. DEPOSITO BERJANGKA:
- Suku Bunga / Imbal Hasil: ${depositoRate.toFixed(2)}% p.a. | Tenor: ${depositoCalc.displayLabel}
- Keuntungan Kotor: ${formatIdr(depositoCalc.grossInterest)}
- Pajak PPh (20%): -${formatIdr(depositoCalc.taxAmount)}
- Keuntungan Bersih: ${formatIdr(depositoCalc.netInterest)}
- Total Akhir: ${formatIdr(depositoCalc.totalPayout)}
- Estimasi Hasil: ${depositoCalc.days < 30 ? formatIdr(depositoCalc.netInterest) : formatIdr(depositoCalc.monthlyNet) + ' / bulan'}

2. OBLIGASI / SBN NEGARA:
- Kupon: ${bondRate.toFixed(2)}% p.a. | Tenor: ${bondTenorMonths} Bulan (${(bondTenorMonths / 12).toFixed(1)} Tahun)
- Kupon Kotor Tenor: ${formatIdr(bondCalc.totalGross)}
- Pajak PPh (10%): -${formatIdr(bondCalc.totalTax)}
- Kupon Bersih Tenor: ${formatIdr(bondCalc.totalNet)}
- Kupon Bersih per Bulan: ${formatIdr(bondCalc.monthlyNet)}
- Total Akhir: ${formatIdr(bondCalc.totalPayout)}

3. KOMPARASI (1 TAHUN):
- Selisih Bersih: ${comparison.netDifference1Y >= 0 ? '+' : ''}${formatIdr(comparison.netDifference1Y)} (Obligasi vs Deposito)
- Efisiensi Pajak: Kupon obligasi hemat pajak PPh 10% vs Deposito 20%
Generated by SOFIA Trading & Financial Terminal`;

    navigator.clipboard.writeText(summaryText);
    setCopiedNotice(true);
    setTimeout(() => setCopiedNotice(false), 3000);
  };

  return (
    <>
      <Head>
        <title>Kalkulator Deposito & Obligasi SBN | SOFIA Financial Terminal</title>
        <meta
          name="description"
          content="Simulasi perbandingan imbal hasil bunga deposito bank dan kupon obligasi SBN dengan 1x input nominal dan perhitungan pajak riil."
        />
      </Head>

      <div className="space-y-6 pb-12">
        {/* HEADER SECTION */}
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 border-b border-obsidian-800 pb-5">
          <div>
            <div className="flex items-center gap-2 mb-1.5">
              <span className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                <LucideIcon name="calculator" className="w-5 h-5" />
              </span>
              <h1 className="text-xl sm:text-2xl font-bold text-white tracking-tight">
                Kalkulator Deposito & Obligasi SBN
              </h1>
              <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
                Fixed Income
              </span>
            </div>
            <p className="text-xs sm:text-sm text-slate-400 max-w-3xl leading-relaxed">
              Bandingkan imbal hasil instrumen pendapatan tetap perbankan vs Surat Berharga Negara (SBN) secara
              head-to-head. Cukup masukkan nominal <strong>1 kali</strong>, sistem akan menghitung estimasi keuntungan
              kotor, potongan pajak riil (PPh 20% vs 10%), dan keuntungan bersih kedua instrumen.
            </p>
          </div>

          {/* Quick Actions & Ultrawide Toggle */}
          <div className="flex items-center gap-2 shrink-0">
            <button
              type="button"
              onClick={handleCopySummary}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-obsidian-800 hover:bg-obsidian-750 text-slate-200 border border-obsidian-700 text-xs font-medium transition active:scale-95"
            >
              <LucideIcon name="copy" className="w-4 h-4 text-emerald-400" />
              <span>{copiedNotice ? 'Tersalin!' : 'Salin Ringkasan'}</span>
            </button>
          </div>
        </div>

        {/* 1. MASTER UNIFIED INPUT CARD (NOMINAL 1X SAJA) */}
        <div className="bg-gradient-to-r from-obsidian-900 via-obsidian-900 to-obsidian-850 p-5 rounded-2xl border border-obsidian-750 shadow-xl relative overflow-hidden">
          <div className="absolute top-0 right-0 w-80 h-32 bg-emerald-500/5 blur-3xl pointer-events-none rounded-full" />
          <div className="relative z-10 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-300">
                  Nominal Investasi Pokok (Principal)
                </span>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-medium">
                  1x Input untuk Semua Kartu
                </span>
              </div>
              <span className="text-xs font-mono text-emerald-400/90 italic truncate max-w-md">
                {angkaKeTerbilang(principal)}
              </span>
            </div>

            {/* Input Nominal Field with clean Rp prefix */}
            <div className="flex flex-col md:flex-row items-stretch gap-3">
              <div className="flex-1 flex rounded-xl overflow-hidden border border-obsidian-700 bg-obsidian-950/90 focus-within:border-emerald-500 focus-within:ring-1 focus-within:ring-emerald-500 transition shadow-inner">
                <div className="flex items-center px-4.5 bg-obsidian-850/90 border-r border-obsidian-750 text-emerald-400 font-bold text-lg sm:text-xl font-mono select-none">
                  Rp
                </div>
                <input
                  type="text"
                  value={principalInputStr}
                  onChange={(e) => handlePrincipalChange(e.target.value)}
                  placeholder="10.000.000"
                  className="w-full px-4 py-3 bg-transparent text-white font-mono text-xl sm:text-2xl font-bold focus:outline-none placeholder:text-slate-600"
                />
              </div>

              {/* Slider for quick nominal tweaking */}
              <div className="flex items-center gap-3 bg-obsidian-950/60 px-4 py-2 rounded-xl border border-obsidian-800/80 min-w-[240px]">
                <div className="text-[11px] text-slate-400 shrink-0">Geser Nominal:</div>
                <input
                  type="range"
                  min={1000000}
                  max={200000000}
                  step={1000000}
                  value={Math.min(principal, 200000000)}
                  onChange={(e) => handleSelectPresetPrincipal(Number(e.target.value))}
                  className="w-full accent-emerald-500 cursor-pointer h-1.5 bg-obsidian-700 rounded-lg"
                />
              </div>
            </div>

            {/* Quick Nominal Presets */}
            <div className="flex flex-wrap items-center gap-1.5 pt-1">
              <span className="text-[11px] text-slate-400 mr-1 flex items-center gap-1">
                <LucideIcon name="zap" className="w-3 h-3 text-amber-400" />
                Preset Cepat:
              </span>
              {NOMINAL_PRESETS.map((preset) => {
                const isSelected = principal === preset.value;
                return (
                  <button
                    key={preset.value}
                    type="button"
                    onClick={() => handleSelectPresetPrincipal(preset.value)}
                    className={`text-xs px-2.5 py-1 rounded-lg border font-mono transition ${
                      isSelected
                        ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40 font-semibold shadow-xs'
                        : 'bg-obsidian-950 text-slate-400 border-obsidian-800 hover:border-obsidian-700 hover:text-slate-200'
                    }`}
                  >
                    {preset.label}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* 2. CARDS SECTION (GRID RESPONSIVE / ULTRAWIDE SIDE-BY-SIDE) */}
        <div
          className={`grid gap-6 ${
            isUltrawide ? 'grid-cols-1 xl:grid-cols-3' : 'grid-cols-1 lg:grid-cols-2'
          }`}
        >
          {/* ========================================================= */}
          {/* CARD A: DEPOSITO BERJANGKA BANK */}
          {/* ========================================================= */}
          <div className="bg-obsidian-900/90 rounded-2xl border border-obsidian-750 p-5 flex flex-col justify-between shadow-xl relative overflow-hidden">
            <div className="absolute top-0 right-0 w-48 h-48 bg-cyan-500/5 blur-3xl pointer-events-none rounded-full" />
            <div className="space-y-5">
              {/* Card Header */}
              <div className="flex items-start justify-between gap-3 border-b border-obsidian-800 pb-4">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="p-1.5 rounded-lg bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
                      <LucideIcon name="banknote" className="w-4 h-4" />
                    </span>
                    <h2 className="text-base sm:text-lg font-bold text-white tracking-tight">
                      Deposito Berjangka Bank
                    </h2>
                  </div>
                  <p className="text-xs text-slate-400 mt-1">
                    Simpanan bank konvensional & digital dengan bunga tetap per tahun (p.a.).
                  </p>
                </div>
                <span className="text-[10px] px-2 py-0.5 rounded font-mono font-bold bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
                  PPh 20%
                </span>
              </div>

              {/* Deposito Presets Bank & Syariah */}
              <div>
                <label className="block text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-2">
                  Preset Suku Bunga / Imbal Hasil Deposito
                </label>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5">
                  {DEPOSITO_PRESETS.map((p) => {
                    const active = depositoActivePreset === p.id && depositoRate === p.rate;
                    return (
                      <button
                        key={p.id}
                        type="button"
                        onClick={() => handleSelectDepositoPreset(p)}
                        className={`p-2 rounded-xl border text-left transition ${
                          active
                            ? p.id === 'syariah'
                              ? 'bg-emerald-500/15 border-emerald-500/40 text-emerald-300'
                              : 'bg-cyan-500/15 border-cyan-500/40 text-cyan-300'
                            : 'bg-obsidian-950/70 border-obsidian-800 text-slate-400 hover:border-obsidian-700'
                        } ${p.id === 'syariah' ? 'col-span-2 sm:col-span-1' : ''}`}
                      >
                        <div className="flex items-center justify-between text-xs font-semibold">
                          <span className="truncate">{p.name}</span>
                          <span className={`font-mono ${p.id === 'syariah' ? 'text-emerald-400' : 'text-cyan-400'}`}>{p.rate}%</span>
                        </div>
                        <div className="text-[10px] text-slate-500 truncate mt-0.5">{p.desc}</div>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Deposito Margin Input & Slider (Maks 20%) */}
              <div className="space-y-2 bg-obsidian-950/60 p-3.5 rounded-xl border border-obsidian-800">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-300 font-medium">Margin Bunga / Bagi Hasil (% p.a.)</span>
                  <div className="flex items-center gap-1.5">
                    <input
                      type="number"
                      step="0.05"
                      min="0.5"
                      max="20"
                      value={depositoRate}
                      onChange={(e) => {
                        const val = Math.min(20, Math.max(0, Number(e.target.value)));
                        setDepositoRate(val);
                        setDepositoActivePreset('custom');
                      }}
                      className="w-18 px-2 py-1 bg-obsidian-900 border border-obsidian-700 rounded-lg text-white font-mono text-right font-bold text-xs focus:outline-none focus:border-cyan-500"
                    />
                    <span className="text-slate-400 font-mono text-xs">%</span>
                  </div>
                </div>
                <input
                  type="range"
                  min="1"
                  max="20"
                  step="0.1"
                  value={depositoRate}
                  onChange={(e) => {
                    setDepositoRate(Number(e.target.value));
                    setDepositoActivePreset('custom');
                  }}
                  className="w-full accent-cyan-500 cursor-pointer h-1.5 bg-obsidian-700 rounded-lg"
                />
                <div className="flex justify-between text-[10px] font-mono text-slate-500">
                  <span>1.0%</span>
                  <span>LPS: 4.25%</span>
                  <span>10.0%</span>
                  <span>Maks: 20.0%</span>
                </div>
              </div>

              {/* Deposito Periode / Tenor (Termasuk 7 Hari & 14 Hari) */}
              <div>
                <label className="block text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-2">
                  Periode / Tenor Deposito
                </label>
                <div className="grid grid-cols-4 sm:grid-cols-4 md:grid-cols-8 gap-1.5">
                  {DEPOSITO_TENOR_PRESETS.map((t) => {
                    const active = depositoTenorId === t.id;
                    return (
                      <button
                        key={t.id}
                        type="button"
                        onClick={() => setDepositoTenorId(t.id)}
                        className={`py-2 px-1 rounded-xl text-center border font-mono text-xs transition ${
                          active
                            ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/50 font-bold shadow-xs'
                            : 'bg-obsidian-950/70 text-slate-400 border-obsidian-800 hover:border-obsidian-700'
                        }`}
                      >
                        {t.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Deposito Calculation Breakdown Results */}
              <div className="space-y-2.5 pt-2 border-t border-obsidian-800">
                {/* Keuntungan Kotor */}
                <div className="flex items-center justify-between text-xs py-1">
                  <span className="text-slate-400">Estimasi Keuntungan Kotor:</span>
                  <span className="font-mono font-medium text-slate-200">
                    {formatIdr(depositoCalc.grossInterest)}
                  </span>
                </div>

                {/* Potongan Pajak PPh */}
                <div className="flex items-center justify-between text-xs py-1">
                  <div className="flex items-center gap-1.5">
                    <span className="text-slate-400">Pajak PPh Final Deposito:</span>
                    <span
                      className={`text-[9px] px-1.5 py-0.2 rounded font-mono ${
                        depositoCalc.isTaxExempt
                          ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                          : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                      }`}
                    >
                      {depositoCalc.isTaxExempt ? 'Bebas Pajak (≤7.5jt)' : '20% PP 131/2000'}
                    </span>
                  </div>
                  <span className="font-mono text-rose-400">
                    {depositoCalc.taxAmount > 0 ? `-${formatIdr(depositoCalc.taxAmount)}` : 'Rp 0'}
                  </span>
                </div>

                {/* Keuntungan Bersih (HIGHLIGHT) */}
                <div className="p-3 rounded-xl bg-cyan-950/30 border border-cyan-800/40 flex items-center justify-between">
                  <div>
                    <div className="text-[11px] text-cyan-300 font-semibold uppercase tracking-wider">
                      Keuntungan Bersih (Net Profit)
                    </div>
                    <div className="text-[10px] text-slate-400">
                      Setelah potong pajak selama {depositoCalc.displayLabel}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-base sm:text-lg font-bold font-mono text-cyan-400">
                      +{formatIdr(depositoCalc.netInterest)}
                    </div>
                    <div className="text-[10px] text-slate-400 font-mono">
                      {depositoCalc.days < 30
                        ? `(cair dalam ${depositoCalc.displayLabel})`
                        : `~${formatIdr(depositoCalc.monthlyNet)} / bulan`}
                    </div>
                  </div>
                </div>

                {/* Total Dana Akhir */}
                <div className="flex items-center justify-between text-xs py-1 border-t border-obsidian-800/80 pt-2">
                  <span className="text-slate-300 font-medium">Total Dana di Jatuh Tempo:</span>
                  <span className="font-mono font-bold text-white text-sm">
                    {formatIdr(depositoCalc.totalPayout)}
                  </span>
                </div>

                {/* Effective Net Rate */}
                <div className="flex items-center justify-between text-[11px] text-slate-400 pt-1">
                  <span>Margin Bersih Efektif (Net p.a.):</span>
                  <span className="font-mono text-cyan-300 font-semibold">
                    {depositoCalc.effectiveNetRateAnnual.toFixed(2)}% p.a.
                  </span>
                </div>
              </div>
            </div>

            {/* Deposito Footer Note: Status LPS */}
            <div className="mt-5 pt-3 border-t border-obsidian-800/80">
              <div className="flex items-start gap-2 text-[11px] text-slate-400">
                <LucideIcon
                  name={depositoCalc.lpsGuaranteed ? 'shield-check' : 'alert-circle'}
                  className={`w-4 h-4 shrink-0 mt-0.5 ${
                    depositoCalc.lpsGuaranteed ? 'text-emerald-400' : 'text-amber-400'
                  }`}
                />
                <div>
                  <span className="font-semibold text-slate-300">Penjaminan LPS (Maks Rp 2 Miliar): </span>
                  {depositoCalc.lpsGuaranteed ? (
                    <span className="text-emerald-400">
                      Bunga {depositoRate}% memenuhi syarat Tingkat Bunga Penjaminan LPS (Maks 4.25%). Simpanan dijamin penuh.
                    </span>
                  ) : depositoRate > 4.25 ? (
                    <span className="text-amber-400">
                      Bunga {depositoRate}% di atas batas TBP LPS (4.25%). Simpanan tidak dijamin oleh LPS sesuai ketentuan undang-undang.
                    </span>
                  ) : (
                    <span className="text-rose-400">Nominal melebihi pagu penjaminan LPS (Maks Rp 2 Miliar).</span>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* ========================================================= */}
          {/* CARD B: OBLIGASI & SURAT BERHARGA NEGARA (SBN) */}
          {/* ========================================================= */}
          <div className="bg-obsidian-900/90 rounded-2xl border border-obsidian-750 p-5 flex flex-col justify-between shadow-xl relative overflow-hidden">
            <div className="absolute top-0 right-0 w-48 h-48 bg-emerald-500/5 blur-3xl pointer-events-none rounded-full" />
            <div className="space-y-5">
              {/* Card Header */}
              <div className="flex items-start justify-between gap-3 border-b border-obsidian-800 pb-4">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                      <LucideIcon name="trending-up" className="w-4 h-4" />
                    </span>
                    <h2 className="text-base sm:text-lg font-bold text-white tracking-tight">
                      Obligasi & SBN Negara
                    </h2>
                  </div>
                  <p className="text-xs text-slate-400 mt-1">
                    ORI, Sukuk Ritel (SR), SBR, FR & Obligasi Korporasi dengan kupon bulanan.
                  </p>
                </div>
                <span className="text-[10px] px-2 py-0.5 rounded font-mono font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  PPh 10% (Hemat Pajak)
                </span>
              </div>

              {/* Obligasi Presets */}
              <div>
                <label className="block text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-2">
                  Preset Kupon Instrumen SBN & Obligasi
                </label>
                <div className="grid grid-cols-2 gap-1.5">
                  {BOND_PRESETS.map((p) => {
                    const active = bondActivePreset === p.id && bondRate === p.rate;
                    return (
                      <button
                        key={p.id}
                        type="button"
                        onClick={() => handleSelectBondPreset(p)}
                        className={`p-2 rounded-xl border text-left transition ${
                          active
                            ? 'bg-emerald-500/15 border-emerald-500/40 text-emerald-300'
                            : 'bg-obsidian-950/70 border-obsidian-800 text-slate-400 hover:border-obsidian-700'
                        }`}
                      >
                        <div className="flex items-center justify-between text-xs font-semibold">
                          <span className="truncate">{p.name}</span>
                          <span className="font-mono text-emerald-400">{p.rate}%</span>
                        </div>
                        <div className="text-[10px] text-slate-500 truncate mt-0.5">{p.desc}</div>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Obligasi Margin/Kupon Input & Slider (Maks 20%) */}
              <div className="space-y-2 bg-obsidian-950/60 p-3.5 rounded-xl border border-obsidian-800">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-300 font-medium">Margin Kupon per Tahun (% p.a.)</span>
                  <div className="flex items-center gap-1.5">
                    <input
                      type="number"
                      step="0.05"
                      min="0.5"
                      max="20"
                      value={bondRate}
                      onChange={(e) => {
                        const val = Math.min(20, Math.max(0, Number(e.target.value)));
                        setBondRate(val);
                        setBondActivePreset('custom');
                      }}
                      className="w-18 px-2 py-1 bg-obsidian-900 border border-obsidian-700 rounded-lg text-white font-mono text-right font-bold text-xs focus:outline-none focus:border-emerald-500"
                    />
                    <span className="text-slate-400 font-mono text-xs">%</span>
                  </div>
                </div>
                <input
                  type="range"
                  min="1"
                  max="20"
                  step="0.05"
                  value={bondRate}
                  onChange={(e) => {
                    setBondRate(Number(e.target.value));
                    setBondActivePreset('custom');
                  }}
                  className="w-full accent-emerald-500 cursor-pointer h-1.5 bg-obsidian-700 rounded-lg"
                />
                <div className="flex justify-between text-[10px] font-mono text-slate-500">
                  <span>1.0%</span>
                  <span>Rata-rata SBN: 6.4% - 6.8%</span>
                  <span>12.0%</span>
                  <span>Maks: 20.0%</span>
                </div>
              </div>

              {/* Obligasi Periode / Tenor */}
              <div>
                <label className="block text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-2">
                  Periode / Tenor Obligasi
                </label>
                <div className="grid grid-cols-4 gap-1.5">
                  {[
                    { m: 12, label: '1 Thn' },
                    { m: 24, label: '2 Thn (SBR/ST)' },
                    { m: 36, label: '3 Thn (ORI/SR)' },
                    { m: 60, label: '5 Thn (ORI-T5)' },
                  ].map((item) => {
                    const active = bondTenorMonths === item.m;
                    return (
                      <button
                        key={item.m}
                        type="button"
                        onClick={() => setBondTenorMonths(item.m)}
                        className={`py-2 px-1 rounded-xl text-center border font-mono text-xs transition ${
                          active
                            ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/50 font-bold'
                            : 'bg-obsidian-950/70 text-slate-400 border-obsidian-800 hover:border-obsidian-700'
                        }`}
                      >
                        {item.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Obligasi Calculation Breakdown Results */}
              <div className="space-y-2.5 pt-2 border-t border-obsidian-800">
                {/* Kupon Kotor */}
                <div className="flex items-center justify-between text-xs py-1">
                  <span className="text-slate-400">Total Kupon Kotor Tenor:</span>
                  <span className="font-mono font-medium text-slate-200">
                    {formatIdr(bondCalc.totalGross)}
                  </span>
                </div>

                {/* Potongan Pajak PPh (HANYA 10%) */}
                <div className="flex items-center justify-between text-xs py-1">
                  <div className="flex items-center gap-1.5">
                    <span className="text-slate-400">Pajak Kupon Obligasi:</span>
                    <span className="text-[9px] px-1.5 py-0.2 rounded font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                      10% PP No. 91/2021
                    </span>
                  </div>
                  <span className="font-mono text-emerald-400">
                    -{formatIdr(bondCalc.totalTax)}
                  </span>
                </div>

                {/* Keuntungan Bersih (HIGHLIGHT) */}
                <div className="p-3 rounded-xl bg-emerald-950/30 border border-emerald-800/40 flex items-center justify-between">
                  <div>
                    <div className="text-[11px] text-emerald-300 font-semibold uppercase tracking-wider">
                      Keuntungan Bersih (Total Kupon Bersih)
                    </div>
                    <div className="text-[10px] text-slate-400">
                      Cair otomatis tiap bulan selama {bondTenorMonths} bulan
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-base sm:text-lg font-bold font-mono text-emerald-400">
                      +{formatIdr(bondCalc.totalNet)}
                    </div>
                    <div className="text-[10px] text-emerald-300/90 font-mono font-medium">
                      {formatIdr(bondCalc.monthlyNet)} / bulan
                    </div>
                  </div>
                </div>

                {/* Total Pengembalian Akhir */}
                <div className="flex items-center justify-between text-xs py-1 border-t border-obsidian-800/80 pt-2">
                  <span className="text-slate-300 font-medium">Total Dana (Pokok + Seluruh Kupon):</span>
                  <span className="font-mono font-bold text-white text-sm">
                    {formatIdr(bondCalc.totalPayout)}
                  </span>
                </div>

                {/* Effective Net Rate */}
                <div className="flex items-center justify-between text-[11px] text-slate-400 pt-1">
                  <span>Margin Kupon Bersih Efektif (Net p.a.):</span>
                  <span className="font-mono text-emerald-300 font-semibold">
                    {bondCalc.effectiveNetRateAnnual.toFixed(2)}% p.a.
                  </span>
                </div>
              </div>
            </div>

            {/* Obligasi Footer Note: Jaminan Negara */}
            <div className="mt-5 pt-3 border-t border-obsidian-800/80">
              <div className="flex items-start gap-2 text-[11px] text-slate-400">
                <LucideIcon name="shield-check" className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                <div>
                  <span className="font-semibold text-slate-300">100% Dijamin Negara RI: </span>
                  Kupon dan pokok SBN dijamin penuh oleh Undang-Undang No. 24/2002 dan UU APBN tanpa batas plafon nominal (Zero Default Risk).
                </div>
              </div>
            </div>
          </div>

          {/* ========================================================= */}
          {/* CARD C: HEAD-TO-HEAD COMPARISON & TAX EFFICIENCY */}
          {/* ========================================================= */}
          <div
            className={`bg-obsidian-900/90 rounded-2xl border border-obsidian-750 p-5 flex flex-col justify-between shadow-xl ${
              isUltrawide ? 'col-span-1' : 'col-span-1 lg:col-span-2'
            }`}
          >
            <div className="space-y-5">
              {/* Card Header */}
              <div className="flex items-center justify-between border-b border-obsidian-800 pb-4">
                <div className="flex items-center gap-2">
                  <span className="p-1.5 rounded-lg bg-amber-500/10 text-amber-400 border border-amber-500/20">
                    <LucideIcon name="zap" className="w-4 h-4" />
                  </span>
                  <div>
                    <h2 className="text-base sm:text-lg font-bold text-white tracking-tight">
                      Komparasi Head-to-Head & Efisiensi Pajak
                    </h2>
                    <p className="text-xs text-slate-400">
                      Perbandingan langsung keuntungan bersih dan penghematan pajak atas nominal {formatIdr(principal)}.
                    </p>
                  </div>
                </div>
              </div>

              {/* Highlight Selisih 1 Tahun */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                {/* 1. Net Profit 1 Tahun Deposito */}
                <div className="bg-obsidian-950 p-3.5 rounded-xl border border-obsidian-800">
                  <div className="text-[11px] text-slate-400 mb-1">Net Deposito (1 Tahun)</div>
                  <div className="text-base sm:text-lg font-mono font-bold text-cyan-400">
                    {formatIdr(comparison.depNet1Y)}
                  </div>
                  <div className="text-[10px] text-slate-500 mt-1">
                    Pajak PPh 20%: -{formatIdr(comparison.depTax1Y)}
                  </div>
                </div>

                {/* 2. Net Profit 1 Tahun Obligasi */}
                <div className="bg-obsidian-950 p-3.5 rounded-xl border border-obsidian-800">
                  <div className="text-[11px] text-slate-400 mb-1">Net Obligasi / SBN (1 Tahun)</div>
                  <div className="text-base sm:text-lg font-mono font-bold text-emerald-400">
                    {formatIdr(comparison.bondNet1Y)}
                  </div>
                  <div className="text-[10px] text-slate-500 mt-1">
                    Pajak PPh 10%: -{formatIdr(comparison.bondTax1Y)}
                  </div>
                </div>

                {/* 3. Selisih Keuntungan Bersih (Alpha) */}
                <div
                  className={`p-3.5 rounded-xl border ${
                    comparison.netDifference1Y >= 0
                      ? 'bg-emerald-950/20 border-emerald-800/40'
                      : 'bg-cyan-950/20 border-cyan-800/40'
                  }`}
                >
                  <div className="text-[11px] text-slate-400 mb-1">
                    {comparison.netDifference1Y >= 0 ? 'Keunggulan Bersih Obligasi' : 'Keunggulan Bersih Deposito'}
                  </div>
                  <div
                    className={`text-base sm:text-lg font-mono font-bold ${
                      comparison.netDifference1Y >= 0 ? 'text-emerald-400' : 'text-cyan-400'
                    }`}
                  >
                    {comparison.netDifference1Y >= 0 ? '+' : ''}
                    {formatIdr(comparison.netDifference1Y)}
                  </div>
                  <div className="text-[10px] text-slate-400 mt-1">
                    {comparison.pctDifference1Y >= 0
                      ? `+${comparison.pctDifference1Y.toFixed(1)}% lebih tinggi per tahun`
                      : `${comparison.pctDifference1Y.toFixed(1)}%`}
                  </div>
                </div>
              </div>

              {/* Visual Profit Comparison Bar */}
              <div className="bg-obsidian-950/80 p-4 rounded-xl border border-obsidian-800 space-y-3">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-slate-300">Visualisasi Hasil Bersih (1 Tahun)</span>
                  <span className="text-[11px] text-slate-400">
                    Efisiensi Pajak: Hemat{' '}
                    <strong className="text-emerald-400 font-mono">
                      {formatIdr(comparison.taxSavings1Y)}
                    </strong>{' '}
                    berkat PPh 10%
                  </span>
                </div>

                {/* Bar Deposito */}
                <div className="space-y-1">
                  <div className="flex items-center justify-between text-[11px] text-slate-400">
                    <span className="flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-cyan-400" />
                      Deposito ({depositoRate}%)
                    </span>
                    <span className="font-mono text-cyan-300">{formatIdr(comparison.depNet1Y)}</span>
                  </div>
                  <div className="w-full h-2.5 bg-obsidian-800 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-cyan-500 rounded-full transition-all duration-500"
                      style={{
                        width: `${Math.min(
                          100,
                          (comparison.depNet1Y / Math.max(comparison.bondNet1Y, comparison.depNet1Y, 1)) * 100
                        )}%`,
                      }}
                    />
                  </div>
                </div>

                {/* Bar Obligasi */}
                <div className="space-y-1">
                  <div className="flex items-center justify-between text-[11px] text-slate-400">
                    <span className="flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-emerald-400" />
                      Obligasi / SBN ({bondRate}%)
                    </span>
                    <span className="font-mono text-emerald-300">{formatIdr(comparison.bondNet1Y)}</span>
                  </div>
                  <div className="w-full h-2.5 bg-obsidian-800 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-emerald-500 rounded-full transition-all duration-500"
                      style={{
                        width: `${Math.min(
                          100,
                          (comparison.bondNet1Y / Math.max(comparison.bondNet1Y, comparison.depNet1Y, 1)) * 100
                        )}%`,
                      }}
                    />
                  </div>
                </div>
              </div>

              {/* Table of Differences */}
              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left">
                  <thead>
                    <tr className="border-b border-obsidian-800 text-[10px] uppercase font-bold text-slate-400">
                      <th className="py-2 pr-3">Aspek Perbandingan</th>
                      <th className="py-2 px-3 text-cyan-400">Deposito Perbankan</th>
                      <th className="py-2 pl-3 text-emerald-400">Obligasi / SBN Negara</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-obsidian-800/60 text-slate-300">
                    <tr>
                      <td className="py-2.5 pr-3 text-slate-400 font-medium">Pajak Penghasilan (PPh)</td>
                      <td className="py-2.5 px-3 font-mono">
                        {principal <= 7500000 ? '0% (Nominal ≤ 7.5jt)' : '20% Final (PP 131/2000)'}
                      </td>
                      <td className="py-2.5 pl-3 font-mono text-emerald-400 font-semibold">
                        10% Final (PP 91/2021)
                      </td>
                    </tr>
                    <tr>
                      <td className="py-2.5 pr-3 text-slate-400 font-medium">Pencairan Hasil</td>
                      <td className="py-2.5 px-3">Saat jatuh tempo / bulanan</td>
                      <td className="py-2.5 pl-3 text-emerald-400 font-semibold">
                        Tiap bulan otomatis (tgl 10 / 15)
                      </td>
                    </tr>
                    <tr>
                      <td className="py-2.5 pr-3 text-slate-400 font-medium">Jaminan Keamanan</td>
                      <td className="py-2.5 px-3">LPS (Maks Rp 2 Miliar, bunga ≤ 4.25%)</td>
                      <td className="py-2.5 pl-3 text-emerald-400 font-semibold">
                        Pemerintah RI 100% via UU APBN
                      </td>
                    </tr>
                    <tr>
                      <td className="py-2.5 pr-3 text-slate-400 font-medium">Pencairan Sebelum Jatuh Tempo</td>
                      <td className="py-2.5 px-3 text-rose-400">Kena penalti / bunga hangus</td>
                      <td className="py-2.5 pl-3">Bisa dijual di pasar sekunder / Early Redemption</td>
                    </tr>
                  </tbody>
                </table>
              </div>

              {/* Schedule Toggle Button */}
              <div className="pt-2">
                <button
                  type="button"
                  onClick={() => setShowSchedule(!showSchedule)}
                  className="flex items-center gap-2 text-xs text-slate-400 hover:text-slate-200 transition font-medium"
                >
                  <LucideIcon
                    name={showSchedule ? 'chevron-up' : 'chevron-down'}
                    className="w-4 h-4 text-emerald-400"
                  />
                  <span>
                    {showSchedule
                      ? 'Sembunyikan Proyeksi Aliran Kas Bulanan'
                      : 'Tampilkan Proyeksi Aliran Kas Bulanan (Cash Flow Schedule)'}
                  </span>
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* 3. CASH FLOW SCHEDULE (COLLAPSIBLE DETAIL TABLE) */}
        {showSchedule && (
          <div className="bg-obsidian-900/90 rounded-2xl border border-obsidian-750 p-5 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-obsidian-800 pb-3">
              <div>
                <h3 className="text-sm sm:text-base font-bold text-white">
                  Jadwal Aliran Kas Bulanan (12 Bulan Pertama)
                </h3>
                <p className="text-xs text-slate-400">
                  Simulasi arus kas yang masuk ke rekening Anda setiap bulan untuk nominal {formatIdr(principal)}.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setShowSchedule(false)}
                className="text-xs px-2.5 py-1 rounded-lg bg-obsidian-800 text-slate-400 hover:text-white"
              >
                Tutup
              </button>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left">
                <thead>
                  <tr className="border-b border-obsidian-800 text-[10px] uppercase font-bold text-slate-400">
                    <th className="py-2 px-3">Bulan Ke</th>
                    <th className="py-2 px-3 text-cyan-400">Kas Masuk Deposito</th>
                    <th className="py-2 px-3 text-emerald-400">Kupon Masuk Obligasi (Net)</th>
                    <th className="py-2 px-3 text-slate-300">Akumulasi Kupon Obligasi</th>
                    <th className="py-2 px-3 text-amber-400">Status Deposito</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-obsidian-800/60 font-mono text-slate-300">
                  {Array.from({ length: 12 }, (_, i) => i + 1).map((month) => {
                    const isMaturity =
                      depositoCalc.days <= 30
                        ? month === 1
                        : month === Math.round(depositoCalc.days / 30.4167);
                    const depCashThisMonth = isMaturity ? depositoCalc.totalPayout : 0;
                    const bondCashThisMonth = bondCalc.monthlyNet;
                    const bondCumThisMonth = bondCalc.monthlyNet * month;

                    return (
                      <tr key={month} className={isMaturity ? 'bg-cyan-950/20' : ''}>
                        <td className="py-2 px-3 font-semibold text-slate-400">Bulan {month}</td>
                        <td className="py-2 px-3 text-cyan-300 font-bold">
                          {isMaturity ? formatIdr(depCashThisMonth) : 'Rp 0 (Terkunci)'}
                        </td>
                        <td className="py-2 px-3 text-emerald-400 font-bold">
                          +{formatIdr(bondCashThisMonth)}
                        </td>
                        <td className="py-2 px-3 text-slate-200">{formatIdr(bondCumThisMonth)}</td>
                        <td className="py-2 px-3 text-[11px] font-sans">
                          {isMaturity ? (
                            <span className="px-1.5 py-0.5 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 font-medium">
                              Jatuh Tempo (Pokok + Bunga Cair)
                            </span>
                          ) : (
                            <span className="text-slate-500">Dana Terkunci</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* 4. FINANCIAL TIPS & REGULATORY BASIS */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
          <div className="bg-obsidian-900/60 p-4 rounded-xl border border-obsidian-800 space-y-1.5">
            <div className="flex items-center gap-1.5 font-bold text-slate-200">
              <LucideIcon name="book" className="w-4 h-4 text-cyan-400" />
              <span>Dasar Hukum Pajak Deposito (PP No. 131/2000)</span>
            </div>
            <p className="text-slate-400 leading-relaxed text-[11px]">
              Berdasarkan Peraturan Pemerintah RI No. 131 Tahun 2000 jo. KMK No. 51/KMK.04/2001, bunga deposito hingga
              Rp 7.500.000 tidak dikenakan pemotongan pajak (0%). Sementara simpanan deposito di atas Rp 7.500.000
              dikenakan Pajak Penghasilan (PPh) Final sebesar <strong>20%</strong> yang dipotong langsung oleh pihak bank.
            </p>
          </div>

          <div className="bg-obsidian-900/60 p-4 rounded-xl border border-obsidian-800 space-y-1.5">
            <div className="flex items-center gap-1.5 font-bold text-slate-200">
              <LucideIcon name="book" className="w-4 h-4 text-emerald-400" />
              <span>Dasar Hukum Pajak Kupon Obligasi (PP No. 91/2021)</span>
            </div>
            <p className="text-slate-400 leading-relaxed text-[11px]">
              Berdasarkan Peraturan Pemerintah RI No. 91 Tahun 2021, tarif PPh Final atas bunga/kupon obligasi bagi
              Wajib Pajak Dalam Negeri (WPDN) ditetapkan sebesar <strong>10%</strong> (turun dari sebelumnya 15%). Hal ini
              menjadikan obligasi negara (ORI/SR/SBR) jauh lebih hemat pajak dibanding deposito.
            </p>
          </div>
        </div>
      </div>
    </>
  );
}
