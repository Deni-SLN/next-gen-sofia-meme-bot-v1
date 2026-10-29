import React, { useState, useEffect, useCallback, useMemo } from 'react';
import Head from 'next/head';
import { api } from '@/lib/api';
import { LucideIcon } from '@/components/LucideIcon';
import { TradingChart } from '@/components/TradingChart';
import { TradingViewWidget } from '@/components/TradingViewWidget';
import { TechnicalIndicatorsCard } from '@/components/TechnicalIndicatorsCard';
import { useUltrawide } from '@/lib/useUltrawide';

const QUICK_TICKERS = [
  'IHSG',
  'BBRI',
  'BBCA',
  'BMRI',
  'BBNI',
  'TLKM',
  'ASII',
  'ADRO',
  'PTBA',
  'ITMG',
  'ANTM',
  'PGAS',
  'UNTR',
  'ICBP',
  'BREN',
  'GOTO',
];

const TIMEFRAME_OPTIONS = [
  { id: '15m', label: '15 Menit', short: '15M' },
  { id: '1h', label: '1 Jam', short: '1H' },
  { id: '4h', label: '4 Jam', short: '4H' },
  { id: '1d', label: '1 Hari', short: '1D' },
  { id: '1w', label: '1 Minggu', short: '1W' },
  { id: '1mo', label: '1 Bulan', short: '1M' },
  { id: '1y', label: '1 Tahun', short: '1Y' },
];

const ANALYSIS_TABS = [
  { id: 'overview', label: '1. Overview' },
  { id: 'technical', label: '2. Technical Analysis' },
  { id: 'fundamental', label: '3. Fundamental' },
  { id: 'valuation', label: '4. Valuation' },
  { id: 'dividend', label: '5. Dividend' },
  { id: 'trading_plan', label: '6. Trading Plan' },
  { id: 'risk', label: '7. Risk Calculator' },
  { id: 'news', label: '8. News & Catalysts' },
  { id: 'ai_analyst', label: '9. AI Analysis' },
  { id: 'backtest', label: '10. Backtest & Portfolio' },
  { id: 'sources', label: '11. Data Sources' },
];

export default function StockAnalysisPage() {
  const [tickerInput, setTickerInput] = useState<string>('BBRI');
  const [activeTicker, setActiveTicker] = useState<string>('BBRI');
  const [selectedTimeframe, setSelectedTimeframe] = useState<string>('1d');
  const [activeTab, setActiveTab] = useState<string>('overview');
  const [stockData, setStockData] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [chartMode, setChartMode] = useState<'tradingview' | 'quantitative'>('tradingview');
  const [focusedIndicator, setFocusedIndicator] = useState<'ALL' | 'SNR' | 'SMC' | 'EMA200' | 'ICHIMOKU' | 'FIBONACCI'>('SNR');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [noticeMsg, setNoticeMsg] = useState<string | null>(null);
  const isUltrawide = useUltrawide();

  const handleSelectIndicator = (ind: 'ALL' | 'SNR' | 'SMC' | 'EMA200' | 'ICHIMOKU' | 'FIBONACCI') => {
    setChartMode('quantitative');
    setFocusedIndicator(ind);
    const el = document.getElementById('chart-container-root');
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  };

  // Quick lot simulator & Dividend tax toggle
  const [simLots, setSimLots] = useState<number>(10);
  const [divTaxTenPct, setDivTaxTenPct] = useState<boolean>(true);

  // Risk Management Calculator state (Section 4G)
  const [riskCapital, setRiskCapital] = useState<number>(10000000);
  const [riskEntry, setRiskEntry] = useState<number>(0);
  const [riskSl, setRiskSl] = useState<number>(0);
  const [riskTp, setRiskTp] = useState<number>(0);
  const [riskMaxPct, setRiskMaxPct] = useState<number>(2.0);
  const [riskLots, setRiskLots] = useState<number>(10);
  const [riskBuyFeePct, setRiskBuyFeePct] = useState<number>(0.15);
  const [riskSellFeePct, setRiskSellFeePct] = useState<number>(0.25);
  const [riskSlippagePct, setRiskSlippagePct] = useState<number>(0.20);
  const [riskResult, setRiskResult] = useState<any>(null);
  const [riskError, setRiskError] = useState<string | null>(null);

  // Portfolio, Watchlist & Signal Journal state (Section 4J & 4K)
  const [portfolioData, setPortfolioData] = useState<any>(null);
  const [portLotsInput, setPortLotsInput] = useState<string>('10');
  const [portAvgPriceInput, setPortAvgPriceInput] = useState<string>('');
  const [portNotesInput, setPortNotesInput] = useState<string>('');

  // AI Deep Stock Research Prompt Card state
  const [promptHorizon, setPromptHorizon] = useState<string>('SWING / 6–12 BULAN');
  const [promptRiskProfile, setPromptRiskProfile] = useState<string>('MODERAT');
  const [promptGoal, setPromptGoal] = useState<string>('CAPITAL GAIN & DIVIDEN');
  const [promptBuyPrice, setPromptBuyPrice] = useState<string>('');
  const [promptCapital, setPromptCapital] = useState<string>('');
  const [promptBenchmark, setPromptBenchmark] = useState<string>('IHSG / LQ45');
  const [showPromptPreview, setShowPromptPreview] = useState<boolean>(false);
  const [copiedPromptType, setCopiedPromptType] = useState<'filled' | 'raw' | null>(null);

  const fetchAnalysis = useCallback(
    async (code: string, force: boolean = false, tf: string = '1d') => {
      const clean = (code || 'BBRI').trim().toUpperCase();
      if (!clean) return;
      if (force) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }
      setErrorMsg(null);
      try {
        const res = await api.analyzeStock(clean, force, tf);
        setStockData(res);
        const activePlan = res?.timeframes_plan?.[tf] || res?.trading_plan || {};
        setRiskEntry(Number(res?.current_price || 0));
        setRiskSl(Number(activePlan?.stop_loss || 0));
        setRiskTp(Number(activePlan?.tp_2 || 0));
        setRiskResult(res?.risk_calculator_default || null);
        setPortAvgPriceInput(String(res?.current_price || ''));
      } catch (err: any) {
        setErrorMsg(err?.message || `Gagal memuat analisa saham ${clean}. Pastikan kode emiten benar.`);
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    []
  );

  const loadPortfolioData = useCallback(async () => {
    try {
      const pRes = await api.getStockPortfolio();
      setPortfolioData(pRes);
    } catch {
      // ignore if uninitialized
    }
  }, []);

  useEffect(() => {
    fetchAnalysis(activeTicker, false, selectedTimeframe);
    loadPortfolioData();
  }, [activeTicker, fetchAnalysis, loadPortfolioData]);

  const handleTimeframeSelect = (tfId: string) => {
    setSelectedTimeframe(tfId);
    const tfPlan = stockData?.timeframes_plan?.[tfId];
    if (tfPlan && stockData?.current_price) {
      setRiskEntry(Number(stockData.current_price));
      setRiskSl(Number(tfPlan.stop_loss));
      setRiskTp(Number(tfPlan.tp_2));
    }
    fetchAnalysis(activeTicker, false, tfId);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!tickerInput.trim()) return;
    const upper = tickerInput.trim().toUpperCase();
    setTickerInput(upper);
    setActiveTicker(upper);
  };

  const handleRunRiskCalculator = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setRiskError(null);
    try {
      const res = await api.calculateStockRisk({
        capital_idr: Number(riskCapital),
        entry_price: Number(riskEntry),
        stop_loss: Number(riskSl),
        target_price: Number(riskTp),
        max_risk_pct: Number(riskMaxPct),
        lots: Number(riskLots),
        buy_fee_pct: Number(riskBuyFeePct),
        sell_fee_pct: Number(riskSellFeePct),
        slippage_pct: Number(riskSlippagePct),
        existing_portfolio_value_idr: Number(portfolioData?.summary?.total_market_value_idr || 0),
        is_idx: stockData?.is_idx !== false && !stockData?.is_index,
      });
      setRiskResult(res);
    } catch (err: any) {
      setRiskError(err?.message || 'Parameter kalkulator risiko tidak valid.');
    }
  };

  const handleSavePosition = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await api.saveStockPosition({
        code: activeTicker,
        lots: Math.max(1, parseInt(portLotsInput, 10) || 1),
        avg_buy_price: Math.max(1, parseFloat(portAvgPriceInput) || Number(stockData?.current_price || 1000)),
        notes: portNotesInput,
      });
      setPortfolioData(res);
      setNoticeMsg(`✅ Posisi saham ${activeTicker} (${portLotsInput} Lot) berhasil disimpan ke Portofolio BEI.`);
      setTimeout(() => setNoticeMsg(null), 4000);
    } catch (err: any) {
      setErrorMsg(err?.message || 'Gagal menyimpan posisi portofolio saham.');
    }
  };

  const handleAddWatchlist = async () => {
    if (!stockData) return;
    const plan = stockData?.timeframes_plan?.[selectedTimeframe] || stockData?.trading_plan || {};
    try {
      const res = await api.saveStockWatchlist({
        code: stockData.code,
        target_entry_price: Number(plan.entry_zone_high || stockData.current_price),
        target_tp_price: Number(plan.tp_1 || 0),
        stop_loss_price: Number(plan.stop_loss || 0),
        notes: `Watchlist ${plan.timeframe_label || '1D'} (${plan.signal_direction || 'WAIT'})`,
      });
      setPortfolioData(res);
      setNoticeMsg(`🔔 ${stockData.code} berhasil ditambahkan ke Watchlist & Alert Harga!`);
      setTimeout(() => setNoticeMsg(null), 4000);
    } catch (err: any) {
      setErrorMsg(err?.message || 'Gagal menambahkan ke Watchlist.');
    }
  };

  const handleRecordSignalJournal = async () => {
    if (!stockData) return;
    try {
      const res = await api.recordStockSignal({
        code: stockData.code,
        timeframe: selectedTimeframe,
      });
      setPortfolioData(res);
      setNoticeMsg(`📒 Sinyal ${stockData.code} (${selectedTimeframe.toUpperCase()}) berhasil dicatat ke Signal Journal!`);
      setTimeout(() => setNoticeMsg(null), 4000);
    } catch (err: any) {
      setErrorMsg(err?.message || 'Gagal mencatat sinyal ke jurnal.');
    }
  };

  const isIdx = stockData?.is_idx !== false;
  const isIndex = Boolean(stockData?.is_index);

  const fmtPrice = (val: number | undefined | null, idxFlag: boolean = isIdx, indexFlag: boolean = isIndex) => {
    if (val === null || val === undefined || Number.isNaN(Number(val))) return 'UNAVAILABLE';
    const num = Number(val);
    if (indexFlag) {
      return num.toLocaleString('id-ID', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }
    if (idxFlag) {
      return `Rp ${Math.round(num).toLocaleString('id-ID')}`;
    }
    return `$${num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };

  const getTrendBadgeStyle = (badge: string) => {
    const b = (badge || '').toUpperCase();
    if (b.includes('BULLISH') || b === 'BUY') {
      return 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40';
    }
    if (b.includes('REBOUND') || b === 'HOLD') {
      return 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40';
    }
    if (b.includes('BEARISH') || b.includes('SELL')) {
      return 'bg-rose-500/20 text-rose-300 border-rose-500/40';
    }
    return 'bg-amber-500/20 text-amber-300 border-amber-500/40';
  };

  const plan =
    stockData?.timeframes_plan?.[selectedTimeframe] ||
    stockData?.trading_plan ||
    {};
  const overview = stockData?.overview || {};
  const feedStatus = overview?.feed_status || {};
  const tech = stockData?.technicals || {};
  const fund = stockData?.fundamentals || {};
  const fundMetrics = fund?.metrics || {};
  const bankMetrics = fund?.banking_metrics || null;
  const valEngine = stockData?.valuation || {};
  const div = stockData?.dividend || {};
  const perf = stockData?.performance || {};
  const range52 = stockData?.range_52w || {};
  const ihsg = stockData?.ihsg || null;
  const marketIntel = stockData?.market_intelligence || {};
  const aiAnalyst = stockData?.ai_analyst || {};
  const backtest = stockData?.backtest || {};
  const dataQuality = stockData?.data_quality || {};
  const candles: any[] = stockData?.recent_candles || [];

  // Simulator calculations (net of 0.40% IDX round-trip fee & dividend tax option)
  const lotsCount = Math.max(1, Number(simLots) || 1);
  const sharesCount = isIdx && !isIndex ? lotsCount * 100 : lotsCount;
  const totalCapital = sharesCount * Number(stockData?.current_price || 0);
  const feeRoundtripIdr = Math.round(totalCapital * 0.004);
  const grossAnnualDivTotal = sharesCount * Number(div.annual_dividend_per_share || 0);
  const netAnnualDivTotal = divTaxTenPct ? Math.round(grossAnnualDivTotal * 0.9) : Math.round(grossAnnualDivTotal);
  const estProfitTp1Net = Math.round(
    sharesCount * Math.max(0, Number(plan.tp_1 || 0) - Number(stockData?.current_price || 0)) - feeRoundtripIdr
  );
  const estProfitTp2Net = Math.round(
    sharesCount * Math.max(0, Number(plan.tp_2 || 0) - Number(stockData?.current_price || 0)) - feeRoundtripIdr
  );

  // Check if user already holds this stock in their portfolio
  const existingHolding = useMemo(() => {
    const list: any[] = portfolioData?.positions || [];
    return list.find((p) => p.code === activeTicker) || null;
  }, [portfolioData, activeTicker]);

  const buildStockResearchPrompt = useCallback(
    (useRawTemplate: boolean = false) => {
      const companyName = useRawTemplate
        ? '[NAMA PERUSAHAAN]'
        : stockData?.name || activeTicker || '[NAMA PERUSAHAAN]';
      const tickerCode = useRawTemplate ? '[TICKER]' : stockData?.code || activeTicker || '[TICKER]';
      const exchangeName = useRawTemplate ? '[IDX / NASDAQ / NYSE / LAINNYA]' : 'IDX (Bursa Efek Indonesia)';
      const currentPriceStr = useRawTemplate
        ? '[HARGA / AMBIL DATA TERBARU]'
        : stockData?.current_price
          ? `${fmtPrice(stockData.current_price)} (Data Live Terminal, ambil juga data terbaru)`
          : '[HARGA / AMBIL DATA TERBARU]';
      const horizonStr = useRawTemplate
        ? '[INTRADAY / SWING / 6–12 BULAN / 1–5 TAHUN]'
        : promptHorizon || 'SWING / 6–12 BULAN';
      const riskStr = useRawTemplate
        ? '[KONSERVATIF / MODERAT / AGRESIF]'
        : promptRiskProfile || 'MODERAT';
      const goalStr = useRawTemplate
        ? '[CAPITAL GAIN / DIVIDEN / GROWTH / VALUE INVESTING]'
        : promptGoal || 'CAPITAL GAIN & DIVIDEN';
      const buyPriceStr = useRawTemplate
        ? '[HARGA]'
        : promptBuyPrice.trim()
          ? `Rp ${promptBuyPrice.trim()}`
          : existingHolding?.avg_buy_price
            ? fmtPrice(existingHolding.avg_buy_price)
            : 'Belum memiliki posisi (opsional)';
      const capitalStr = useRawTemplate
        ? '[MODAL]'
        : promptCapital.trim()
          ? `Rp ${promptCapital.trim()}`
          : totalCapital > 0
            ? fmtPrice(totalCapital)
            : '[MODAL]';
      const benchmarkStr = useRawTemplate
        ? '[IHSG / LQ45 / S&P 500 / LAINNYA]'
        : promptBenchmark || 'IHSG / LQ45';

      return `# DEEP STOCK RESEARCH & INVESTMENT DECISION

## 1. PERAN AI

Bertindaklah sebagai tim analis investasi profesional yang terdiri dari:
- Equity Research Analyst
- Financial Statement Analyst
- Fundamental & Valuation Analyst
- Quantitative Analyst
- Technical Analyst
- Risk Management Analyst
- Macroeconomic Analyst

Lakukan analisis secara independen, kritis, berbasis data, dan berorientasi pada pengambilan keputusan investasi. Jangan sekadar mengonfirmasi asumsi saya. Identifikasi pula kelemahan tesis investasi, potensi manipulasi laporan keuangan, risiko tersembunyi, dan kemungkinan kerugian permanen modal.

## 2. INPUT ANALISIS

Analisis saham berikut:

- Nama perusahaan: ${companyName}
- Kode saham: ${tickerCode}
- Bursa: ${exchangeName}
- Harga saham saat ini: ${currentPriceStr}
- Horizon investasi: ${horizonStr}
- Profil risiko: ${riskStr}
- Tujuan: ${goalStr}
- Harga beli saya (opsional): ${buyPriceStr}
- Jumlah modal (opsional): ${capitalStr}
- Benchmark: ${benchmarkStr}

Jika ada informasi yang belum tersedia, gunakan asumsi yang wajar, tandai asumsi tersebut, dan jelaskan keterbatasan analisisnya.

## 3. STANDAR PENGUMPULAN DATA

Sebelum membuat kesimpulan:
1. Cari data terbaru yang tersedia dari sumber tepercaya.
2. Prioritaskan laporan tahunan, laporan keuangan kuartalan, keterbukaan informasi bursa, presentasi investor, dan publikasi regulator.
3. Gunakan sumber sekunder seperti penyedia data pasar dan riset industri sebagai pelengkap.
4. Cantumkan tanggal data, periode laporan, mata uang, dan sumber setiap metrik penting.
5. Bandingkan minimal 3–5 tahun data historis apabila tersedia.
6. Bandingkan perusahaan dengan minimal 3 kompetitor relevan apabila tersedia.
7. Bedakan fakta, estimasi, asumsi, dan opini analis.
8. Jangan mengarang data atau menyajikan harga tertunda sebagai harga real-time.
9. Jika data tidak tersedia, nyatakan secara eksplisit dan jangan mengisi kekosongan dengan angka rekaan.

## 4. ANALISIS FUNDAMENTAL

### A. Profil dan model bisnis
- Sumber pendapatan utama dan kontribusi setiap segmen.
- Produk, pelanggan, wilayah operasional, dan keunggulan kompetitif.
- Struktur industri, hambatan masuk, daya tawar pelanggan, dan pemasok.
- Ketergantungan pada pelanggan besar, komoditas, regulasi, atau pihak terkait.
- Kekuatan moat: brand, biaya rendah, jaringan, switching cost, teknologi, atau skala ekonomi.
- Keberlanjutan model bisnis dalam 5–10 tahun mendatang.

### B. Analisis laporan keuangan
Evaluasi tren minimal 3–5 tahun:
- Revenue growth dan pertumbuhan organik.
- Gross profit margin, operating margin, net profit margin.
- ROE, ROA, ROIC.
- EPS dan pertumbuhan EPS.
- Operating cash flow dan free cash flow.
- Total debt, net debt, debt-to-equity, interest coverage.
- Current ratio dan likuiditas.
- Capital expenditure, working capital, serta kualitas laba.
- Perbedaan laba bersih dengan arus kas operasional.

Identifikasi red flags:
- Pendapatan naik tetapi arus kas melemah.
- Piutang atau persediaan tumbuh lebih cepat daripada pendapatan.
- Transaksi pihak berelasi yang material.
- Kapitalisasi biaya yang tidak wajar.
- Dilusi saham, penerbitan saham berulang, atau utang berisiko.
- Perubahan auditor, opini audit, atau restatement laporan keuangan.

Sesuaikan metrik dengan sektor. Untuk bank, gunakan NIM, NPL, CASA, CAR, ROA, cost of credit, dan kualitas pencadangan. Untuk perusahaan komoditas, analisis siklus harga, biaya produksi, cadangan, dan sensitivitas harga komoditas.

### C. Kualitas manajemen dan tata kelola
- Rekam jejak direksi dan komisaris.
- Alokasi modal: ekspansi, akuisisi, dividen, dan buyback.
- Kualitas komunikasi kepada investor.
- Kepemilikan insider dan pemegang saham pengendali.
- Transaksi afiliasi, risiko tata kelola, dan perlindungan pemegang saham minoritas.

## 5. ANALISIS INDUSTRI DAN MAKROEKONOMI

Analisis faktor yang memengaruhi perusahaan:
- Pertumbuhan industri dan pangsa pasar.
- Posisi perusahaan dalam siklus bisnis.
- Suku bunga, inflasi, kurs, daya beli, dan likuiditas pasar.
- Kebijakan pemerintah dan perubahan regulasi.
- Harga komoditas, biaya bahan baku, serta risiko geopolitik jika relevan.
- Tren teknologi dan potensi disrupsi.
- Katalis positif dan negatif dalam 3–12 bulan ke depan.

Jelaskan hubungan sebab-akibat antara faktor makro dan kinerja perusahaan, bukan hanya menyebutkan berita.

## 6. VALUASI INTRINSIK

Gunakan metode yang relevan dengan sektor perusahaan:
- Discounted Cash Flow (DCF).
- Relative valuation: PER, PBV, EV/EBITDA, P/S, atau metrik sektoral.
- Dividend Discount Model apabila relevan.
- Sum-of-the-Parts jika perusahaan memiliki segmen berbeda.
- Historical valuation dibandingkan dengan kompetitor dan rata-rata historisnya.

Untuk DCF:
1. Buat proyeksi pendapatan, margin, arus kas, dan belanja modal.
2. Jelaskan asumsi pertumbuhan, WACC, dan terminal growth.
3. Hitung estimasi nilai wajar per saham.
4. Lakukan sensitivity analysis terhadap WACC dan pertumbuhan.
5. Hindari terminal growth yang tidak realistis.
6. Perhitungkan utang bersih, kas, kepentingan nonpengendali, dan jumlah saham terdilusi secara tepat.

Sajikan tiga skenario:

- Bear case: kondisi bisnis memburuk.
- Base case: kondisi paling masuk akal.
- Bull case: pertumbuhan lebih kuat dari ekspektasi.

Untuk setiap skenario, tampilkan asumsi, nilai wajar, potensi kenaikan/penurunan dari harga saat ini, dan probabilitas jika dapat dipertanggungjawabkan.

Hitung margin of safety pada harga saat ini. Jangan memberikan target harga presisi palsu jika ketidakpastian estimasi tinggi.

## 7. ANALISIS DIVIDEN DAN STRUKTUR MODAL

Jika relevan, evaluasi:
- Dividend yield dan dividend payout ratio.
- Konsistensi serta pertumbuhan dividen.
- Free cash flow dividend coverage.
- Risiko dividend trap.
- Buyback, stock split, rights issue, dan potensi dilusi.
- Kebutuhan pendanaan untuk ekspansi dan pembayaran utang.

## 8. ANALISIS TEKNIKAL DAN PERILAKU PASAR

Gunakan data harga dan volume terbaru yang tersedia:
- Tren harga pada timeframe harian dan mingguan.
- Support, resistance, dan struktur market.
- Moving average 20, 50, 100, dan 200 hari jika tersedia.
- RSI, MACD, serta volume untuk konfirmasi momentum.
- Relative strength terhadap indeks acuan.
- Volatilitas, gap harga, dan potensi false breakout.
- Likuiditas, spread, serta risiko slippage.
- Foreign flow, institutional flow, atau data order book hanya jika datanya tersedia dan valid.

Tentukan:
- Tren utama dan tren jangka pendek.
- Zona entry potensial.
- Level invalidasi tesis teknikal.
- Area stop-loss berbasis struktur harga.
- Target harga berdasarkan risk/reward.

Jangan menyimpulkan sinyal teknikal hanya berdasarkan indikator tanpa mempertimbangkan tren, volume, dan kondisi pasar.

## 9. ANALISIS RISIKO

Buat risk register yang berisi:
- Risiko bisnis.
- Risiko keuangan dan likuiditas.
- Risiko valuasi.
- Risiko tata kelola.
- Risiko makro dan regulasi.
- Risiko likuiditas saham.
- Risiko konsentrasi dan volatilitas.
- Risiko tesis investasi tidak berjalan sesuai rencana.

Untuk setiap risiko, berikan probabilitas kualitatif atau kuantitatif jika tersedia, dampak, indikator peringatan dini, dan mitigasi.

Jelaskan kondisi yang dapat membatalkan tesis investasi dan bukti yang akan membuat Anda mengubah rekomendasi.

## 10. SENTIMEN DAN KATALIS

Analisis berita, keterbukaan informasi, laporan analis, dan sentimen pasar terbaru:
- Berita positif dan negatif yang material.
- Ekspektasi pasar dibandingkan dengan kinerja aktual.
- Potensi earnings surprise.
- Corporate action dan perubahan kebijakan.
- Katalis yang sudah diperhitungkan dalam harga.
- Rumor yang belum terverifikasi.

Bedakan katalis yang memiliki bukti kuat dari spekulasi.

## 11. STRATEGI INVESTASI

Berdasarkan hasil analisis, susun:
- Status: layak dipantau, akumulasi bertahap, hold, reduce, atau hindari.
- Estimasi nilai wajar dan rentang valuasi.
- Zona beli konservatif dan zona beli agresif.
- Target harga berdasarkan horizon investasi.
- Level invalidasi tesis.
- Estimasi upside, downside, dan risk/reward.
- Strategi pembelian bertahap jika sesuai.
- Ukuran posisi berdasarkan toleransi risiko, likuiditas, dan diversifikasi.
- Syarat fundamental atau peristiwa yang perlu dipantau sebelum menambah posisi.

Jangan menetapkan stop-loss trading sebagai pengganti evaluasi fundamental untuk investasi jangka panjang. Pisahkan strategi trading dan strategi investasi.

## 12. OUTPUT AKHIR

Susun laporan dalam urutan berikut:

1. Executive summary.
2. Tabel metrik fundamental utama.
3. Kualitas bisnis dan keunggulan kompetitif.
4. Analisis tren keuangan 3–5 tahun.
5. Perbandingan kompetitor.
6. Analisis manajemen dan tata kelola.
7. Analisis industri dan makro.
8. Valuasi dan sensitivity analysis.
9. Analisis teknikal.
10. Risk register.
11. Katalis positif dan negatif.
12. Skenario bear, base, dan bull.
13. Strategi entry, target, dan invalidasi.
14. Kesimpulan dan rekomendasi.
15. Daftar sumber beserta tanggal data.

Berikan skor 0–100 untuk:
- Kualitas bisnis.
- Kesehatan keuangan.
- Pertumbuhan.
- Kualitas manajemen.
- Valuasi.
- Momentum pasar.
- Risiko.

Jelaskan bobot setiap komponen, alasan pemberian skor, dan jangan membuat skor total seolah-olah objektif jika datanya tidak memadai.

## 13. ATURAN KESIMPULAN

- Jangan merekomendasikan saham hanya karena harganya sedang naik.
- Jangan menyamakan perusahaan bagus dengan saham yang murah.
- Jangan menyamakan saham murah dengan saham yang layak dibeli.
- Jangan menggunakan data usang tanpa memberi peringatan.
- Jangan mengabaikan potensi penurunan modal secara permanen.
- Jika bukti bertentangan, jelaskan kedua sisi secara adil.
- Jika data belum cukup, berikan status “belum dapat disimpulkan”.
- Utamakan kualitas analisis, transparansi asumsi, dan manajemen risiko daripada prediksi yang terdengar meyakinkan.

Mulai analisis dengan memverifikasi ticker, bursa, harga, laporan keuangan terbaru, dan sumber data. Jangan langsung memberikan rekomendasi sebelum proses verifikasi selesai.`;
    },
    [
      stockData,
      activeTicker,
      promptHorizon,
      promptRiskProfile,
      promptGoal,
      promptBuyPrice,
      promptCapital,
      promptBenchmark,
      existingHolding,
      totalCapital,
    ]
  );

  const handleCopyResearchPrompt = useCallback(
    async (useRaw: boolean = false) => {
      const text = buildStockResearchPrompt(useRaw);
      try {
        await navigator.clipboard.writeText(text);
        setCopiedPromptType(useRaw ? 'raw' : 'filled');
        setTimeout(() => setCopiedPromptType(null), 2500);
      } catch {
        const textarea = document.createElement('textarea');
        textarea.value = text;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
        setCopiedPromptType(useRaw ? 'raw' : 'filled');
        setTimeout(() => setCopiedPromptType(null), 2500);
      }
    },
    [buildStockResearchPrompt]
  );

  return (
    <>
      <Head>
        <title>Analisa Saham BEI ({activeTicker}) | Sofia Market 3.9</title>
      </Head>

      <div
        className={`p-4 lg:p-6 space-y-5 pb-24 transition-all duration-300 ${
          isUltrawide ? 'w-full max-w-none px-4 lg:px-8' : 'max-w-[1600px] mx-auto'
        }`}
      >
        {/* Top Search, Truthful Feed Status Badge, IHSG Hari Ini Banner & Quick Ticker Bar */}
        <div className="rounded-2xl border border-slate-800/90 bg-gradient-to-r from-[#0b101d] via-[#0f172a] to-[#0b101d] p-5 shadow-xl space-y-4">
          <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center text-emerald-400 shrink-0">
                <LucideIcon name="trending-up" className="w-5 h-5" />
              </div>
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h1 className="text-lg sm:text-xl font-extrabold tracking-tight text-white">
                    ANALISA CEPAT SAHAM INDONESIA (BEI / IDX)
                  </h1>
                  {/* Truthful Data Latency Badge (DELAYED vs END-OF-DAY) */}
                  <span
                    className={`px-2.5 py-0.5 text-[10px] font-mono font-bold rounded-full border ${
                      feedStatus.feed_badge === 'DELAYED'
                        ? 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                        : 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40'
                    }`}
                    title={feedStatus.feed_description || 'Yahoo Finance IDX Feed'}
                  >
                    {feedStatus.feed_badge || 'END-OF-DAY'} • {feedStatus.session_label || 'BEI / IDX'}
                  </span>
                </div>
                <p className="text-xs text-slate-400 mt-0.5">
                  Multi-Timeframe Technicals, Laporan Keuangan Fundamental, Valuasi Nilai Wajar, Dividen, Kalkulator Risiko ARA/ARB, AI Analyst &amp; Walk-Forward Backtest
                </p>
              </div>
            </div>

            {/* Ticker Search Input */}
            <form onSubmit={handleSubmit} className="flex items-center gap-2">
              <input
                type="text"
                value={tickerInput}
                onChange={(e) => setTickerInput(e.target.value.toUpperCase())}
                placeholder="Ketik kode emiten (cth: BBRI)..."
                className="w-full sm:w-52 bg-slate-950 border border-slate-700 rounded-xl px-3.5 py-2 text-xs font-mono font-bold text-white uppercase placeholder-slate-500 focus:outline-none focus:border-emerald-500"
              />
              <button
                type="submit"
                disabled={loading}
                className="px-4 py-2 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 text-xs font-extrabold transition shrink-0"
              >
                Analisa Saham
              </button>
              <button
                type="button"
                onClick={handleAddWatchlist}
                disabled={loading || !stockData}
                className="px-3 py-2 rounded-xl bg-amber-500/15 hover:bg-amber-500/25 text-amber-300 border border-amber-500/30 text-xs font-bold transition shrink-0"
                title="Simpan ke Watchlist & Alert Harga"
              >
                + Watchlist
              </button>
              <button
                type="button"
                onClick={() => fetchAnalysis(activeTicker, true, selectedTimeframe)}
                disabled={loading || refreshing}
                className="px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-bold transition shrink-0"
                title="Refresh harga & indikator terbaru"
              >
                <LucideIcon name="rotate-ccw" className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
              </button>
            </form>
          </div>

          {noticeMsg && (
            <div className="px-3.5 py-2 rounded-xl bg-emerald-500/15 border border-emerald-500/40 text-emerald-300 text-xs font-mono">
              {noticeMsg}
            </div>
          )}

          {/* IHSG HARI INI (Indeks Harga Saham Gabungan) Live Bar */}
          {ihsg && (
            <div className="p-3.5 rounded-xl bg-slate-950/85 border border-slate-800 flex flex-wrap items-center justify-between gap-3">
              <div className="flex flex-wrap items-center gap-3">
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
                  <span className="text-xs font-extrabold uppercase tracking-wider text-cyan-300">
                    🇮🇩 IHSG HARI INI ({ihsg.symbol}):
                  </span>
                </div>
                <div className="flex items-baseline gap-2 font-mono">
                  <span className="text-base sm:text-lg font-black text-white">
                    {Number(ihsg.price || 0).toLocaleString('id-ID', {
                      minimumFractionDigits: 2,
                      maximumFractionDigits: 2,
                    })}
                  </span>
                  <span
                    className={`text-xs font-extrabold px-2 py-0.5 rounded-md border ${
                      Number(ihsg.change) >= 0
                        ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
                        : 'bg-rose-500/15 text-rose-300 border-rose-500/30'
                    }`}
                  >
                    {Number(ihsg.change) >= 0 ? '▲ +' : '▼ '}
                    {Number(ihsg.change || 0).toLocaleString('id-ID', {
                      minimumFractionDigits: 2,
                      maximumFractionDigits: 2,
                    })}{' '}
                    ({Number(ihsg.change_pct) >= 0 ? '+' : ''}
                    {ihsg.change_pct}%)
                  </span>
                </div>
                <div className="hidden md:flex items-center gap-3 text-[11px] font-mono text-slate-400 border-l border-slate-800 pl-3">
                  <span>
                    Rentang Hari Ini:{' '}
                    <strong className="text-slate-200">
                      {Number(ihsg.day_low || 0).toLocaleString('id-ID', { maximumFractionDigits: 0 })} –{' '}
                      {Number(ihsg.day_high || 0).toLocaleString('id-ID', { maximumFractionDigits: 0 })}
                    </strong>
                  </span>
                  <span>•</span>
                  <span>
                    52 Minggu:{' '}
                    <strong className="text-slate-200">
                      {Number(ihsg.w52_low || 0).toLocaleString('id-ID', { maximumFractionDigits: 0 })} –{' '}
                      {Number(ihsg.w52_high || 0).toLocaleString('id-ID', { maximumFractionDigits: 0 })}
                    </strong>
                  </span>
                </div>
              </div>

              <button
                type="button"
                onClick={() => {
                  setTickerInput('IHSG');
                  setActiveTicker('IHSG');
                }}
                className="px-3 py-1.5 rounded-lg bg-cyan-500/15 hover:bg-cyan-500/25 text-cyan-300 border border-cyan-500/30 text-xs font-bold transition"
              >
                📊 Analisa Detail IHSG
              </button>
            </div>
          )}

          {/* Popular IDX Quick-Select Pills */}
          <div className="pt-2 border-t border-slate-800/80 flex items-center gap-1.5 overflow-x-auto pb-1 no-scrollbar">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 shrink-0 mr-1">
              Saham Populer:
            </span>
            {QUICK_TICKERS.map((code) => {
              const active = activeTicker === code;
              return (
                <button
                  key={code}
                  type="button"
                  onClick={() => {
                    setTickerInput(code);
                    setActiveTicker(code);
                  }}
                  className={`px-2.5 py-1 rounded-lg text-xs font-mono font-bold border transition whitespace-nowrap ${
                    active
                      ? 'bg-emerald-500/25 text-emerald-300 border-emerald-400 shadow-sm'
                      : 'bg-slate-900/90 text-slate-300 border-slate-800 hover:text-white hover:border-slate-700'
                  }`}
                >
                  {code}
                </button>
              );
            })}
          </div>
        </div>

        {/* Error Alert */}
        {errorMsg && (
          <div className="p-4 rounded-xl border border-rose-500/40 bg-rose-500/10 text-rose-300 text-xs flex items-center justify-between">
            <span>⚠️ {errorMsg}</span>
            <button
              type="button"
              onClick={() => {
                setTickerInput('BBRI');
                setActiveTicker('BBRI');
              }}
              className="px-3 py-1 rounded-lg bg-rose-500/20 hover:bg-rose-500/30 text-rose-200 font-bold"
            >
              Kembali ke BBRI
            </button>
          </div>
        )}

        {loading ? (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 animate-pulse">
            <div className="h-64 rounded-2xl bg-[#0b101d] border border-slate-800" />
            <div className="h-64 rounded-2xl bg-[#0b101d] border border-slate-800" />
            <div className="h-64 rounded-2xl bg-[#0b101d] border border-slate-800" />
          </div>
        ) : stockData ? (
          <>
            {/* CARD COPY PROMPT UNTUK AI — DEEP STOCK RESEARCH & INVESTMENT DECISION (Compact Copy-Only Card) */}
            <div className="rounded-2xl border border-indigo-500/30 bg-gradient-to-r from-[#0d1326] via-[#0b101d] to-[#111827] px-5 py-3.5 shadow-xl space-y-3">
              <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3">
                <div className="space-y-0.5">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="px-2.5 py-0.5 rounded-full text-[10px] font-extrabold uppercase tracking-wider bg-indigo-500/20 text-indigo-300 border border-indigo-500/40">
                      Prompt AI • 13 Bagian Riset Institusional
                    </span>
                    <h2 className="text-sm font-extrabold text-white tracking-tight">
                      Deep Stock Research &amp; Investment Decision ({stockData.code})
                    </h2>
                  </div>
                  <p className="text-xs text-slate-400">
                    Salin prompt analisis saham mendalam (<span className="text-slate-300">Peran 7 Analis, Fundamental, DCF, Teknikal, Risk Register &amp; Strategi</span>) untuk{' '}
                    <strong className="text-emerald-300">{stockData.name} ({stockData.code})</strong> tanpa menampilkan teks penuh di layar.
                  </p>
                </div>

                <div className="flex flex-wrap items-center gap-2 shrink-0">
                  <button
                    type="button"
                    onClick={() => handleCopyResearchPrompt(false)}
                    className={`px-4 py-2 rounded-xl text-xs font-extrabold transition flex items-center gap-2 border shadow-md ${
                      copiedPromptType === 'filled'
                        ? 'bg-emerald-500 text-slate-950 border-emerald-400'
                        : 'bg-indigo-600 hover:bg-indigo-500 text-white border-indigo-400/40'
                    }`}
                  >
                    <span>{copiedPromptType === 'filled' ? '✓ Prompt Berhasil Disalin!' : `📋 Copy Prompt AI (${stockData.code})`}</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => handleCopyResearchPrompt(true)}
                    className={`px-3.5 py-2 rounded-xl text-xs font-bold transition flex items-center gap-1.5 border ${
                      copiedPromptType === 'raw'
                        ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                        : 'bg-slate-900 hover:bg-slate-800 text-slate-300 border-slate-700'
                    }`}
                  >
                    <span>{copiedPromptType === 'raw' ? '✓ Template Tersalin!' : '📄 Copy Template Mentah'}</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setShowPromptPreview((prev) => !prev)}
                    className="px-3 py-2 rounded-xl text-xs font-bold bg-slate-950 hover:bg-slate-900 text-slate-300 border border-slate-800 transition"
                  >
                    {showPromptPreview ? 'Tutup Opsi ▲' : '⚙️ Opsi Input'}
                  </button>
                </div>
              </div>

              {showPromptPreview && (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-2.5 pt-2 border-t border-slate-800/80 text-xs">
                  <div className="p-2 rounded-xl bg-slate-950/70 border border-slate-800/90">
                    <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Horizon Investasi</label>
                    <select
                      value={promptHorizon}
                      onChange={(e) => setPromptHorizon(e.target.value)}
                      className="w-full bg-slate-900 text-white rounded-lg px-2 py-1 text-xs border border-slate-700 focus:outline-none focus:border-indigo-500"
                    >
                      <option value="INTRADAY">INTRADAY</option>
                      <option value="SWING">SWING</option>
                      <option value="SWING / 6–12 BULAN">6–12 BULAN (SWING/POSISI)</option>
                      <option value="6–12 BULAN">6–12 BULAN</option>
                      <option value="1–5 TAHUN">1–5 TAHUN (LONG TERM)</option>
                    </select>
                  </div>

                  <div className="p-2 rounded-xl bg-slate-950/70 border border-slate-800/90">
                    <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Profil Risiko</label>
                    <select
                      value={promptRiskProfile}
                      onChange={(e) => setPromptRiskProfile(e.target.value)}
                      className="w-full bg-slate-900 text-white rounded-lg px-2 py-1 text-xs border border-slate-700 focus:outline-none focus:border-indigo-500"
                    >
                      <option value="KONSERVATIF">KONSERVATIF</option>
                      <option value="MODERAT">MODERAT</option>
                      <option value="AGRESIF">AGRESIF</option>
                    </select>
                  </div>

                  <div className="p-2 rounded-xl bg-slate-950/70 border border-slate-800/90">
                    <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Tujuan Investasi</label>
                    <select
                      value={promptGoal}
                      onChange={(e) => setPromptGoal(e.target.value)}
                      className="w-full bg-slate-900 text-white rounded-lg px-2 py-1 text-xs border border-slate-700 focus:outline-none focus:border-indigo-500"
                    >
                      <option value="CAPITAL GAIN">CAPITAL GAIN</option>
                      <option value="DIVIDEN">DIVIDEN</option>
                      <option value="GROWTH">GROWTH</option>
                      <option value="VALUE INVESTING">VALUE INVESTING</option>
                      <option value="CAPITAL GAIN & DIVIDEN">CAPITAL GAIN &amp; DIVIDEN</option>
                    </select>
                  </div>

                  <div className="p-2 rounded-xl bg-slate-950/70 border border-slate-800/90">
                    <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Harga Beli Saya (Opsional)</label>
                    <input
                      type="text"
                      value={promptBuyPrice}
                      onChange={(e) => setPromptBuyPrice(e.target.value)}
                      placeholder={existingHolding?.avg_buy_price ? String(existingHolding.avg_buy_price) : 'Contoh: 4500'}
                      className="w-full bg-slate-900 text-white rounded-lg px-2 py-1 text-xs font-mono border border-slate-700 focus:outline-none focus:border-indigo-500"
                    />
                  </div>

                  <div className="p-2 rounded-xl bg-slate-950/70 border border-slate-800/90">
                    <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Jumlah Modal (Opsional)</label>
                    <input
                      type="text"
                      value={promptCapital}
                      onChange={(e) => setPromptCapital(e.target.value)}
                      placeholder={totalCapital > 0 ? String(totalCapital) : '10.000.000'}
                      className="w-full bg-slate-900 text-white rounded-lg px-2 py-1 text-xs font-mono border border-slate-700 focus:outline-none focus:border-indigo-500"
                    />
                  </div>

                  <div className="p-2 rounded-xl bg-slate-950/70 border border-slate-800/90">
                    <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Benchmark</label>
                    <input
                      type="text"
                      value={promptBenchmark}
                      onChange={(e) => setPromptBenchmark(e.target.value)}
                      placeholder="IHSG / LQ45"
                      className="w-full bg-slate-900 text-white rounded-lg px-2 py-1 text-xs border border-slate-700 focus:outline-none focus:border-indigo-500"
                    />
                  </div>
                </div>
              )}
            </div>

            {/* ROW 1: TOP DECISION SUMMARY (Overview + Multi-Timeframe Trading Plan + Dividend Intelligence) */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
              {/* Card 1: Harga Saat Ini, Sektor & Rentang 52M (4 cols) */}
              <div className="lg:col-span-4 rounded-2xl border border-slate-800/90 bg-[#0b101d] p-5 flex flex-col justify-between space-y-4 shadow-lg">
                <div className="space-y-3">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-2xl font-black font-mono text-white tracking-tight">
                          {stockData.code}
                        </span>
                        <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-slate-800 text-cyan-300 border border-slate-700">
                          {stockData.exchange}
                        </span>
                      </div>
                      <p className="text-xs font-semibold text-slate-300 mt-0.5">{stockData.name}</p>
                      <p className="text-[11px] text-slate-400">
                        {stockData.sector} {stockData.sub_sector && stockData.sub_sector !== stockData.sector ? `• ${stockData.sub_sector}` : ''}
                      </p>
                    </div>
                    <div className="text-right flex flex-col items-end gap-1">
                      <span
                        className={`px-2.5 py-1 rounded-lg text-[11px] font-extrabold border ${getTrendBadgeStyle(
                          plan.signal_direction || plan.trend_badge
                        )}`}
                      >
                        SINYAL: {plan.signal_direction || 'WAIT'}
                      </span>
                      <span className="text-[10px] font-mono text-slate-400">{plan.trend_status}</span>
                    </div>
                  </div>

                  {/* Current Price & Day Change */}
                  <div className="pt-2 border-t border-slate-800/80 flex items-baseline justify-between">
                    <div>
                      <div className="text-[10px] font-bold uppercase text-slate-400">
                        {isIndex ? 'Level Indeks Saat Ini' : 'Harga Terakhir'} ({feedStatus.feed_badge || 'EOD'})
                      </div>
                      <div className="text-3xl font-black font-mono text-white mt-0.5">
                        {fmtPrice(stockData.current_price)}
                      </div>
                      <div className="text-[10px] font-mono text-slate-400 mt-0.5">
                        Update: {feedStatus.last_trade_wib || stockData.updated_at}
                      </div>
                    </div>
                    <div className="text-right">
                      <div
                        className={`text-sm font-extrabold font-mono ${
                          stockData.day_change >= 0 ? 'text-emerald-400' : 'text-rose-400'
                        }`}
                      >
                        {stockData.day_change >= 0 ? '+' : ''}
                        {fmtPrice(stockData.day_change)} ({stockData.day_change_pct >= 0 ? '+' : ''}
                        {stockData.day_change_pct}%)
                      </div>
                      {!isIndex && (
                        <div className="text-[11px] text-slate-400 font-mono mt-0.5">
                          1 Lot (100 lbr):{' '}
                          <strong className="text-slate-200">{fmtPrice(stockData.price_per_lot)}</strong>
                        </div>
                      )}
                      {valEngine?.data_status === 'VALID' && (
                        <div className="text-[10px] font-mono text-amber-300 mt-0.5">
                          Nilai Wajar Base: {fmtPrice(valEngine?.scenarios?.base_case)} ({valEngine.potential_upside_pct >= 0 ? '+' : ''}{valEngine.potential_upside_pct}%)
                        </div>
                      )}
                    </div>
                  </div>

                  {/* 52-Week Range Bar */}
                  <div className="bg-slate-950/80 p-3 rounded-xl border border-slate-800/80 space-y-1.5">
                    <div className="flex justify-between text-[10px] font-mono text-slate-400">
                      <span>Low 52M: {fmtPrice(range52.low)}</span>
                      <span className="text-cyan-300 font-bold">Posisi 52M: {range52.position_pct}%</span>
                      <span>High 52M: {fmtPrice(range52.high)}</span>
                    </div>
                    <div className="w-full h-2 rounded-full bg-slate-800 overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-rose-500 via-amber-400 to-emerald-400 rounded-full"
                        style={{ width: `${Math.min(100, Math.max(4, Number(range52.position_pct || 50)))}%` }}
                      />
                    </div>
                  </div>
                </div>

                {/* Performance Pills (1W, 1M, 3M, 1Y) */}
                <div className="grid grid-cols-4 gap-2 pt-2 border-t border-slate-800/80 font-mono text-center">
                  {[
                    { label: '1 Minggu', val: perf['1w_pct'] },
                    { label: '1 Bulan', val: perf['1m_pct'] },
                    { label: '3 Bulan', val: perf['3m_pct'] },
                    { label: '1 Tahun', val: perf['1y_pct'] },
                  ].map((item) => (
                    <div key={item.label} className="bg-slate-950/70 p-2 rounded-lg border border-slate-800/80">
                      <div className="text-[10px] text-slate-400 font-sans font-medium">{item.label}</div>
                      <div
                        className={`text-xs font-bold mt-0.5 ${
                          Number(item.val) >= 0 ? 'text-emerald-400' : 'text-rose-400'
                        }`}
                      >
                        {Number(item.val) >= 0 ? '+' : ''}
                        {item.val}%
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Card 2: Rekomendasi Trading Plan (Entry, TP & SL) with Multi-Timeframe Selector (5 cols) */}
              <div className="lg:col-span-5 rounded-2xl border border-cyan-500/30 bg-[#0b101d] p-5 flex flex-col justify-between space-y-4 shadow-lg">
                <div className="space-y-3 border-b border-slate-800 pb-3">
                  <div className="flex items-center justify-between gap-2">
                    <div>
                      <h2 className="text-sm font-extrabold uppercase tracking-wide text-cyan-300 flex items-center gap-2">
                        <LucideIcon name="crosshair" className="w-4 h-4 text-cyan-400" />
                        Rekomendasi Trading Plan (Entry, TP &amp; SL)
                      </h2>
                      <p className="text-[11px] text-slate-400 mt-0.5">
                        Strategi: <strong className="text-white">{plan.action_verdict}</strong> • Hold:{' '}
                        <strong className="text-cyan-300">{plan.hold_duration || '3 – 10 Hari'}</strong>
                      </p>
                    </div>
                    <div className="text-right shrink-0">
                      <span className="px-2.5 py-1 rounded-lg bg-cyan-500/15 border border-cyan-500/30 text-cyan-300 font-mono text-xs font-bold block">
                        Net R/R {plan.net_risk_reward_ratio || plan.risk_reward_ratio}
                      </span>
                    </div>
                  </div>

                  {/* Timeframe Selector Buttons (15 Menit, 1 Jam, 1 Hari, 1 Minggu, 1 Bulan, 1 Tahun) */}
                  <div className="flex items-center gap-1.5 overflow-x-auto pb-0.5 no-scrollbar">
                    <span className="text-[10px] font-bold uppercase text-slate-400 shrink-0 mr-1">
                      Time Frame:
                    </span>
                    {TIMEFRAME_OPTIONS.map((tf) => {
                      const active = selectedTimeframe === tf.id;
                      return (
                        <button
                          key={tf.id}
                          type="button"
                          onClick={() => handleTimeframeSelect(tf.id)}
                          className={`px-2.5 py-1 rounded-lg text-[11px] font-bold transition whitespace-nowrap border ${
                            active
                              ? 'bg-cyan-500/25 text-cyan-200 border-cyan-400 shadow-sm'
                              : 'bg-slate-900/90 text-slate-300 border-slate-800 hover:text-white hover:border-slate-700'
                          }`}
                        >
                          {tf.label}
                        </button>
                      );
                    })}
                  </div>
                </div>

                {plan.wait_reason && (
                  <div className="px-3 py-2 rounded-xl bg-amber-500/15 border border-amber-500/30 text-[11px] text-amber-300">
                    <strong>Alasan Sinyal {plan.signal_direction}:</strong> {plan.wait_reason}
                  </div>
                )}

                {/* Grid of Entry, TP1, TP2, Stop Loss */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 font-mono">
                  <div className="p-3.5 rounded-xl bg-cyan-500/10 border border-cyan-500/30">
                    <div className="text-[10px] font-sans font-bold uppercase text-cyan-300">
                      🎯 Area Entry Ideal ({plan.timeframe_label || '1 Hari'})
                    </div>
                    <div className="text-base font-black text-white mt-1">
                      {fmtPrice(plan.entry_zone_low)} – {fmtPrice(plan.entry_zone_high)}
                    </div>
                    <div className="text-[10px] font-sans text-slate-400 mt-0.5">
                      Fee BEI: ~{plan.estimated_fee_roundtrip_pct || 0.4}% pergi-pulang
                    </div>
                  </div>

                  <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-sans font-bold uppercase text-rose-300">
                        🛡️ Stop Loss / Invalidasi
                      </span>
                      <span className="text-xs font-bold text-rose-400">{plan.stop_loss_pct}%</span>
                    </div>
                    <div className="text-base font-black text-white mt-1">
                      {fmtPrice(plan.stop_loss)}
                    </div>
                    <div className="text-[10px] font-sans text-slate-400 mt-0.5">
                      Rugi Bersih (+Fee): {plan.net_stop_loss_pct}%
                    </div>
                  </div>

                  <div className="p-3.5 rounded-xl bg-emerald-500/10 border border-emerald-500/30">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-sans font-bold uppercase text-emerald-300">
                        🚀 Target Profit 1 (TP 1)
                      </span>
                      <span className="text-xs font-bold text-emerald-400">+{plan.tp_1_pct}%</span>
                    </div>
                    <div className="text-base font-black text-white mt-1">
                      {fmtPrice(plan.tp_1)}
                    </div>
                    <div className="text-[10px] font-sans text-slate-400 mt-0.5">
                      Net (+Fee): +{plan.net_tp_1_pct}% • Ambil 50% posisi
                    </div>
                  </div>

                  <div className="p-3.5 rounded-xl bg-teal-500/10 border border-teal-500/30">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-sans font-bold uppercase text-teal-300">
                        💎 Target Profit 2 (TP 2)
                      </span>
                      <span className="text-xs font-bold text-teal-400">+{plan.tp_2_pct}%</span>
                    </div>
                    <div className="text-base font-black text-white mt-1">
                      {fmtPrice(plan.tp_2)}
                    </div>
                    <div className="text-[10px] font-sans text-slate-400 mt-0.5">
                      Net (+Fee): +{plan.net_tp_2_pct}% • Target penuh
                    </div>
                  </div>
                </div>

                {/* Support & Resistance Row */}
                <div className="grid grid-cols-4 gap-2 pt-2 border-t border-slate-800/80 text-center font-mono text-xs">
                  <div className="bg-slate-950/70 p-2 rounded-lg border border-slate-800">
                    <div className="text-[10px] text-slate-400 font-sans">Support 2</div>
                    <div className="font-bold text-amber-300">{fmtPrice(plan.support_2)}</div>
                  </div>
                  <div className="bg-slate-950/70 p-2 rounded-lg border border-slate-800">
                    <div className="text-[10px] text-slate-400 font-sans">Support 1</div>
                    <div className="font-bold text-cyan-300">{fmtPrice(plan.support_1)}</div>
                  </div>
                  <div className="bg-slate-950/70 p-2 rounded-lg border border-slate-800">
                    <div className="text-[10px] text-slate-400 font-sans">Resistance 1</div>
                    <div className="font-bold text-emerald-300">{fmtPrice(plan.resistance_1)}</div>
                  </div>
                  <div className="bg-slate-950/70 p-2 rounded-lg border border-slate-800">
                    <div className="text-[10px] text-slate-400 font-sans">Resistance 2</div>
                    <div className="font-bold text-teal-300">{fmtPrice(plan.resistance_2)}</div>
                  </div>
                </div>
              </div>

              {/* Card 3: Dividend Intelligence Summary (3 cols) */}
              <div className="lg:col-span-3 rounded-2xl border border-amber-500/30 bg-[#0b101d] p-5 flex flex-col justify-between space-y-4 shadow-lg">
                <div className="space-y-3">
                  <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                    <div>
                      <h2 className="text-sm font-extrabold uppercase tracking-wide text-amber-300 flex items-center gap-1.5">
                        <LucideIcon name="banknote" className="w-4 h-4 text-amber-400" />
                        Dividend Intelligence
                      </h2>
                      <p className="text-[11px] text-slate-400">TTM vs Historis 3Th vs Estimasi</p>
                    </div>
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                        div.pays_dividend
                          ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                          : 'bg-slate-800 text-slate-400 border-slate-700'
                      }`}
                    >
                      {div.pays_dividend ? 'RUTIN DIVIDEN' : 'NON-DIVIDEN'}
                    </span>
                  </div>

                  {/* Strictly separated TTM, 3Y Avg, and Forward Estimate */}
                  <div className="grid grid-cols-2 gap-2.5 font-mono">
                    <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/30">
                      <div className="text-[10px] font-sans text-amber-300 font-bold">
                        Dividen TTM (12Bln)
                      </div>
                      <div className="text-base font-black text-white mt-0.5">
                        {div.pays_dividend ? `${fmtPrice(div.ttm_dividend_per_share || div.annual_dividend_per_share)}/lbr` : 'Rp 0'}
                      </div>
                      <div className="text-[10px] font-sans text-slate-400 mt-0.5">
                        Hist 3Th: {fmtPrice(div.avg_3y_dividend_per_share)}
                      </div>
                    </div>

                    <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30">
                      <div className="text-[10px] font-sans text-emerald-300 font-bold">
                        Dividend Yield
                      </div>
                      <div className="text-xl font-black text-emerald-400 mt-0.5">
                        {div.dividend_yield_pct}%
                      </div>
                      <div className="text-[10px] font-sans text-slate-400 mt-0.5">
                        Est. Depan: {fmtPrice(div.forward_estimated_dividend_per_share)}
                      </div>
                    </div>
                  </div>

                  {/* Dividend History List */}
                  <div className="space-y-1.5">
                    <div className="text-[10px] font-bold uppercase text-slate-400">
                      Riwayat Dividen Terkonfirmasi:
                    </div>
                    {div.history && div.history.length > 0 ? (
                      <div className="space-y-1 max-h-32 overflow-y-auto pr-1">
                        {div.history.slice(0, 4).map((item: any, idx: number) => (
                          <div
                            key={idx}
                            className="flex items-center justify-between px-2.5 py-1.5 rounded-lg bg-slate-950/80 border border-slate-800/80 text-xs font-mono"
                          >
                            <span className="text-slate-300">Ex: {item.ex_date || item.date}</span>
                            <span className="text-amber-300 font-bold">
                              {fmtPrice(item.amount)} ({item.yield_at_current_pct}%)
                            </span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="p-3 rounded-lg bg-slate-950/60 border border-slate-800 text-xs text-slate-400">
                        {isIndex
                          ? 'Indeks gabungan tidak membagikan dividen secara langsung.'
                          : 'Emiten ini belum membagikan dividen tunai dalam 3 tahun terakhir.'}
                      </div>
                    )}
                  </div>
                </div>

                <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-xs font-mono">
                  <span className="text-slate-400 font-sans">Dividen Kotor / 1 Lot:</span>
                  <strong className="text-amber-300">{fmtPrice(div.annual_dividend_per_lot)} / thn</strong>
                </div>
              </div>
            </div>

            {/* NAVIGATION TABS FOR ALL 11 MODULES (Section 5 UI Requirement) */}
            <div className="rounded-2xl border border-slate-800 bg-[#0b101d] p-2 flex items-center gap-1.5 overflow-x-auto no-scrollbar">
              {ANALYSIS_TABS.map((t) => {
                const active = activeTab === t.id;
                return (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => setActiveTab(t.id)}
                    className={`px-3 py-2 rounded-xl text-xs font-bold whitespace-nowrap transition border ${
                      active
                        ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40 shadow-sm'
                        : 'bg-slate-950/60 text-slate-400 border-transparent hover:text-white hover:bg-slate-900'
                    }`}
                  >
                    {t.label}
                  </button>
                );
              })}
            </div>

            {/* =====================================================================
                TAB 1: OVERVIEW (Stock Overview + 30D Chart + Quick Lot Simulator)
               ===================================================================== */}
            {activeTab === 'overview' && (
              <div className="space-y-5">
                {/* Complete Stock Overview Microstructure Grid (Section 4A) */}
                <div className="rounded-2xl border border-slate-800/90 bg-[#0b101d] p-5 space-y-4">
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 pb-3">
                    <div>
                      <h3 className="text-sm font-extrabold uppercase text-white">
                        A. Detail Ringkasan Perdagangan Saham ({stockData.code})
                      </h3>
                      <p className="text-xs text-slate-400">
                        Sumber: {feedStatus.source_provider} • Status: {feedStatus.feed_description}
                      </p>
                    </div>
                    {existingHolding && (
                      <span className="px-3 py-1 rounded-xl bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 text-xs font-mono font-bold">
                        📦 Dimiliki di Portofolio: {existingHolding.lots} Lot @ {fmtPrice(existingHolding.avg_buy_price)}
                      </span>
                    )}
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 font-mono text-xs">
                    <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                      <div className="text-[10px] text-slate-400 font-sans">Open / Prev Close</div>
                      <div className="font-bold text-white mt-0.5">
                        {fmtPrice(overview.open)} / {fmtPrice(overview.prev_close)}
                      </div>
                    </div>
                    <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                      <div className="text-[10px] text-slate-400 font-sans">Day Low – Day High</div>
                      <div className="font-bold text-cyan-300 mt-0.5">
                        {fmtPrice(overview.low)} – {fmtPrice(overview.high)}
                      </div>
                    </div>
                    <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                      <div className="text-[10px] text-slate-400 font-sans">Volume &amp; Nilai Transaksi</div>
                      <div className="font-bold text-white mt-0.5">
                        {Number(overview.volume_lots || 0).toLocaleString('id-ID')} Lot
                      </div>
                      <div className="text-[10px] text-slate-400">
                        ≈ Rp {Math.round(Number(overview.transaction_value_idr || 0) / 1e9).toLocaleString('id-ID')} Miliar
                      </div>
                    </div>
                    <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                      <div className="text-[10px] text-slate-400 font-sans">Kapitalisasi Pasar</div>
                      <div className="font-bold text-emerald-400 mt-0.5">
                        {overview.market_cap_idr_t ? `Rp ${overview.market_cap_idr_t} Triliun` : 'UNAVAILABLE'}
                      </div>
                      <div className="text-[10px] text-slate-400">
                        Saham: {overview.shares_outstanding_b ? `${overview.shares_outstanding_b} Miliar lbr` : 'N/A'}
                      </div>
                    </div>
                    <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                      <div className="text-[10px] text-slate-400 font-sans">Fraksi Harga &amp; ARA / ARB</div>
                      <div className="font-bold text-amber-300 mt-0.5">
                        Tick Rp {overview.tick_size_rp || 1} (±{overview.ara_arb_limit_pct || 25}%)
                      </div>
                      <div className="text-[10px] text-slate-400">
                        ARB {fmtPrice(overview.arb_price)} • ARA {fmtPrice(overview.ara_price)}
                      </div>
                    </div>
                    <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                      <div className="text-[10px] text-slate-400 font-sans">Order Book &amp; Frekuensi</div>
                      <div className="font-bold text-slate-400 mt-0.5 text-[11px]">UNAVAILABLE</div>
                      <div className="text-[9px] text-slate-500 font-sans">
                        Butuh lisensi IDX ITCH L2
                      </div>
                    </div>
                  </div>
                </div>

                {/* INTERACTIVE CHART ENGINE & DYNAMIC LAYOUT (NORMAL VS ULTRAWIDE) */}
                {(() => {
                  const chartOnlyBlock = (
                    <div id="chart-container-root" className="space-y-4">
                      <div className="flex flex-wrap items-center justify-between gap-2 bg-obsidian-900/80 p-2.5 rounded-xl border border-obsidian-800">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-bold text-slate-300 font-mono flex items-center gap-1.5">
                            <LucideIcon name="bar-chart-2" className="w-4 h-4 text-cyan-400" />
                            Pilihan Mesin Grafik:
                          </span>
                        </div>
                        <div className="flex items-center gap-1.5 font-mono text-xs">
                          <button
                            type="button"
                            onClick={() => setChartMode('tradingview')}
                            className={`px-3 py-1.5 rounded-lg font-bold border transition ${
                              chartMode === 'tradingview'
                                ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/50 shadow-sm'
                                : 'bg-obsidian-950 text-slate-400 border-obsidian-800 hover:text-white'
                            }`}
                          >
                            📈 TradingView Pro (Live Timeframe)
                          </button>
                          <button
                            type="button"
                            onClick={() => setChartMode('quantitative')}
                            className={`px-3 py-1.5 rounded-lg font-bold border transition ${
                              chartMode === 'quantitative'
                                ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/50 shadow-sm'
                                : 'bg-obsidian-950 text-slate-400 border-obsidian-800 hover:text-white'
                            }`}
                          >
                            ⚡ SOFIA Quant (5 Indikator SNR/SMC/EMA/Kumo/Fib)
                          </button>
                        </div>
                      </div>

                      {chartMode === 'tradingview' ? (
                        <TradingViewWidget
                          symbol={stockData.code}
                          timeframe={selectedTimeframe}
                          isCrypto={false}
                          height={isUltrawide ? 490 : 500}
                        />
                      ) : (
                        <TradingChart
                          candles={stockData?.candles || stockData?.recent_candles || candles}
                          symbol={stockData.code}
                          timeframe={selectedTimeframe}
                          timeframes={TIMEFRAME_OPTIONS}
                          onTimeframeChange={handleTimeframeSelect}
                          currency={stockData.currency}
                          technicalAudit={stockData.technical_audit}
                          initialFocus={focusedIndicator}
                          onFocusChange={setFocusedIndicator}
                          height={isUltrawide ? 480 : 460}
                        />
                      )}
                    </div>
                  );

                  const indicatorsBlock = stockData.technical_audit ? (
                    <TechnicalIndicatorsCard
                      technicalAudit={stockData.technical_audit}
                      symbol={stockData.code}
                      currency={stockData.currency}
                      focusedIndicator={focusedIndicator}
                      onSelectIndicator={handleSelectIndicator}
                    />
                  ) : null;

                  const summaryBlock = (
                    <div className="w-full rounded-2xl border border-slate-800/90 bg-[#0b101d] p-5 space-y-4 shadow-lg">
                    <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                      <h3 className="text-sm font-extrabold uppercase tracking-wide text-white flex items-center gap-2">
                        <LucideIcon name="area-chart" className="w-4 h-4 text-emerald-400" />
                        Ringkasan Sinyal Analisis Saham ({stockData.code})
                      </h3>
                      <span className="text-[11px] font-mono text-slate-400">
                        Satuan: {stockData.currency} • Timeframe: 1D
                      </span>
                    </div>

                    <div className="space-y-2">
                      {(stockData.summary_notes || []).map((note: string, i: number) => (
                        <div
                          key={i}
                          className="flex items-start gap-2.5 p-3 rounded-xl bg-slate-950/70 border border-slate-800/80 text-xs text-slate-200 leading-relaxed"
                        >
                          <span className="text-emerald-400 font-bold mt-0.5">✔</span>
                          <span>{note}</span>
                        </div>
                      ))}
                    </div>

                    {candles.length > 2 && (
                      <div className="pt-2 space-y-2">
                        <div className="flex items-center justify-between text-[11px] text-slate-400">
                          <span>Grafik Penutupan 30 Hari Bursa Terakhir (Hijau = Naik, Merah = Turun)</span>
                          <span className="font-mono text-slate-300">
                            Rentang 30H: {fmtPrice(Math.min(...candles.map((c) => c.low)))} –{' '}
                            {fmtPrice(Math.max(...candles.map((c) => c.high)))}
                          </span>
                        </div>
                        <div className="h-32 w-full bg-slate-950/90 rounded-xl border border-slate-800/80 p-3 flex items-end gap-1">
                          {(() => {
                            const minC = Math.min(...candles.map((c) => c.close));
                            const maxC = Math.max(...candles.map((c) => c.close));
                            const span = Math.max(1, maxC - minC);
                            return candles.map((c, idx) => {
                              const hPct = Math.max(12, Math.round(((c.close - minC) / span) * 100));
                              const isUp = c.close >= c.open;
                              return (
                                <div
                                  key={idx}
                                  title={`${c.date}: Open ${fmtPrice(c.open)} | High ${fmtPrice(c.high)} | Low ${fmtPrice(c.low)} | Close ${fmtPrice(c.close)} | Vol ${Number(c.volume || 0).toLocaleString('id-ID')}`}
                                  className={`flex-1 rounded-t transition-all ${
                                    isUp ? 'bg-emerald-500/70 hover:bg-emerald-400' : 'bg-rose-500/70 hover:bg-rose-400'
                                  }`}
                                  style={{ height: `${hPct}%` }}
                                />
                              );
                            });
                          })()}
                        </div>
                        <div className="flex justify-between text-[10px] font-mono text-slate-400">
                          <span>{candles[0]?.date}</span>
                          <span>Legenda: OHLC Daily Split-Adjusted ({stockData.currency})</span>
                          <span>{candles[candles.length - 1]?.date}</span>
                        </div>
                      </div>
                    )}
                    </div>
                  );

                  // Quick Technicals + Lot Simulator
                  const lotBlock = (
                    <div className="w-full rounded-2xl border border-slate-800/90 bg-[#0b101d] p-5 space-y-4 shadow-lg flex flex-col justify-between">
                    <div className="space-y-3">
                      <h3 className="text-sm font-extrabold uppercase tracking-wide text-white border-b border-slate-800 pb-3">
                        📊 Indikator Inti &amp; Simulasi Lot Bersih
                      </h3>

                      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5 font-mono text-xs">
                        <div className="p-2.5 rounded-xl bg-slate-950/80 border border-slate-800">
                          <div className="text-[10px] text-slate-400 font-sans">RSI (14)</div>
                          <div className="text-sm font-bold text-cyan-300 mt-0.5">{tech.rsi_14}</div>
                          <div className="text-[9px] text-slate-400 font-sans truncate">{tech.rsi_status}</div>
                        </div>
                        <div className="p-2.5 rounded-xl bg-slate-950/80 border border-slate-800">
                          <div className="text-[10px] text-slate-400 font-sans">SMA-20 / EMA-20</div>
                          <div className="text-sm font-bold text-white mt-0.5">{fmtPrice(tech.sma_20)}</div>
                          <div className="text-[9px] text-slate-400 font-sans">EMA20: {fmtPrice(tech.ema_20)}</div>
                        </div>
                        <div className="p-2.5 rounded-xl bg-slate-950/80 border border-slate-800">
                          <div className="text-[10px] text-slate-400 font-sans">SMA-50 / EMA-50</div>
                          <div className="text-sm font-bold text-white mt-0.5">{fmtPrice(tech.sma_50)}</div>
                          <div className="text-[9px] text-slate-400 font-sans">EMA50: {fmtPrice(tech.ema_50)}</div>
                        </div>
                        <div className="p-2.5 rounded-xl bg-slate-950/80 border border-slate-800">
                          <div className="text-[10px] text-slate-400 font-sans">SMA-200 (Major)</div>
                          <div className="text-sm font-bold text-white mt-0.5">{fmtPrice(tech.sma_200)}</div>
                          <div className="text-[9px] text-emerald-400 font-sans">
                            {stockData.current_price >= tech.sma_200 ? 'Major Uptrend' : 'Di bawah SMA200'}
                          </div>
                        </div>
                        <div className="p-2.5 rounded-xl bg-slate-950/80 border border-slate-800">
                          <div className="text-[10px] text-slate-400 font-sans">MACD (12,26,9)</div>
                          <div
                            className={`text-sm font-bold mt-0.5 ${
                              tech.macd_histogram >= 0 ? 'text-emerald-400' : 'text-rose-400'
                            }`}
                          >
                            {tech.macd_histogram >= 0 ? '+' : ''}
                            {tech.macd_histogram}
                          </div>
                          <div className="text-[9px] text-slate-400 font-sans">Sig: {tech.macd_signal}</div>
                        </div>
                        <div className="p-2.5 rounded-xl bg-slate-950/80 border border-slate-800">
                          <div className="text-[10px] text-slate-400 font-sans">ATR-14 &amp; Vol Ratio</div>
                          <div className="text-sm font-bold text-amber-300 mt-0.5">{fmtPrice(tech.atr_14)}</div>
                          <div className="text-[9px] text-slate-400 font-sans">Vol {tech.volume_ratio}x MA20</div>
                        </div>
                      </div>
                    </div>

                    {/* Interactive Lot Simulator with Fee & Tax */}
                    <div className="p-4 rounded-xl bg-slate-950/90 border border-emerald-500/30 space-y-3">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-xs font-bold text-emerald-300">
                          🧮 Simulasi Beli Lot ({stockData.code} • 1 Lot = 100 Lembar)
                        </span>
                        <div className="flex items-center gap-1.5">
                          <span className="text-[11px] text-slate-400">Jumlah Lot:</span>
                          <input
                            type="number"
                            min={1}
                            max={100000}
                            value={simLots}
                            onChange={(e) => setSimLots(Math.max(1, Number(e.target.value) || 1))}
                            className="w-20 bg-slate-900 border border-slate-700 rounded-lg px-2 py-1 text-xs font-mono font-bold text-white text-right"
                          />
                        </div>
                      </div>

                      <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                        <div className="p-2 rounded-lg bg-slate-900/90 border border-slate-800">
                          <div className="text-[10px] text-slate-400 font-sans">
                            Modal ({lotsCount} Lot = {sharesCount.toLocaleString('id-ID')} lbr)
                          </div>
                          <div className="font-bold text-white mt-0.5">{fmtPrice(totalCapital)}</div>
                        </div>
                        <div className="p-2 rounded-lg bg-slate-900/90 border border-slate-800">
                          <div className="text-[10px] text-slate-400 font-sans">
                            Est. Dividen Bersih ({divTaxTenPct ? 'Pajak 10%' : '0% Reinvest'})
                          </div>
                          <div className="font-bold text-amber-300 mt-0.5">{fmtPrice(netAnnualDivTotal)}</div>
                        </div>
                        <div className="p-2 rounded-lg bg-slate-900/90 border border-slate-800">
                          <div className="text-[10px] text-slate-400 font-sans">
                            Net Profit TP 1 (+{plan.net_tp_1_pct || plan.tp_1_pct}%)
                          </div>
                          <div className="font-bold text-emerald-400 mt-0.5">+{fmtPrice(estProfitTp1Net)}</div>
                        </div>
                        <div className="p-2 rounded-lg bg-slate-900/90 border border-slate-800">
                          <div className="text-[10px] text-slate-400 font-sans">
                            Net Profit TP 2 (+{plan.net_tp_2_pct || plan.tp_2_pct}%)
                          </div>
                          <div className="font-bold text-teal-400 mt-0.5">+{fmtPrice(estProfitTp2Net)}</div>
                        </div>
                      </div>
                    </div>
                  </div>
                  );

                  return isUltrawide ? (
                    <div className="grid grid-cols-1 xl:grid-cols-12 gap-5 items-start">
                      {/* Kolom 1 (Kiri - 5 Col): Chart Interaktif (TradingView Pro / SOFIA Quant) */}
                      <div className="xl:col-span-5 space-y-4">
                        {chartOnlyBlock}
                      </div>

                      {/* Kolom 2 (Tengah - 4 Col): Audit 5 Indikator Teknis (SNR, SMC, EMA, Kumo, Fib) Dipindahkan ke Samping Chart! */}
                      <div className="xl:col-span-4 space-y-4">
                        {indicatorsBlock}
                      </div>

                      {/* Kolom 3 (Kanan - 3 Col): Ringkasan Sinyal & Simulasi Pembelian Lot */}
                      <div className="xl:col-span-3 space-y-4">
                        {summaryBlock}
                        {lotBlock}
                      </div>
                    </div>
                  ) : (
                    <>
                      {chartOnlyBlock}
                      {indicatorsBlock}
                      {/* ROW 2: Kesimpulan Analisa Singkat + Detail Indikator + Simulasi Lot */}
                      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
                        <div className="lg:col-span-7">{summaryBlock}</div>
                        <div className="lg:col-span-5">{lotBlock}</div>
                      </div>
                    </>
                  );
                })()}
              </div>
            )}

            {/* =====================================================================
                TAB 2: TECHNICAL ANALYSIS ENGINE (Section 4B)
               ===================================================================== */}
            {activeTab === 'technical' && (() => {
              const chartCol = (
                <div className="space-y-4">
                  <TradingChart
                    candles={stockData?.candles || stockData?.recent_candles || candles}
                    symbol={stockData.code}
                    timeframe={selectedTimeframe}
                    timeframes={TIMEFRAME_OPTIONS}
                    onTimeframeChange={handleTimeframeSelect}
                    currency={stockData.currency}
                    technicalAudit={stockData.technical_audit}
                    initialFocus={focusedIndicator}
                    onFocusChange={setFocusedIndicator}
                    height={isUltrawide ? 490 : 460}
                  />

                  {/* Price Structure: Breakout, Breakdown & Pullback Detection */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                    <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-1">
                      <div className="text-[10px] font-bold uppercase text-cyan-300">
                        Deteksi Breakout / Breakdown (20-Bar Box)
                      </div>
                      <div className="font-mono font-bold text-white">
                        {tech.structure?.breakout_status}
                      </div>
                      <div className="text-[11px] text-slate-400 font-mono">
                        Support Box 20H: {fmtPrice(tech.structure?.box_support_20)} • Resistance Box 20H:{' '}
                        {fmtPrice(tech.structure?.box_resistance_20)}
                      </div>
                    </div>
                    <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-1">
                      <div className="text-[10px] font-bold uppercase text-amber-300">
                        Deteksi Pullback / Retest &amp; Volume MA-20
                      </div>
                      <div className="font-mono font-bold text-white">
                        {tech.structure?.pullback_status}
                      </div>
                      <div className="text-[11px] text-slate-400 font-mono">
                        Volume Saat Ini: {Number(tech.latest_volume || 0).toLocaleString('id-ID')} lbr vs MA20:{' '}
                        {Number(tech.avg_volume_20d || 0).toLocaleString('id-ID')} lbr ({tech.volume_ratio}x)
                      </div>
                    </div>
                  </div>
                </div>
              );

              const metricsCol = (
                <div className="space-y-4">
                  {stockData.technical_audit && (
                    <TechnicalIndicatorsCard
                      technicalAudit={stockData.technical_audit}
                      symbol={stockData.code}
                      currency={stockData.currency}
                      focusedIndicator={focusedIndicator}
                      onSelectIndicator={handleSelectIndicator}
                    />
                  )}

                  <div className="rounded-2xl border border-slate-800/90 bg-[#0b101d] p-5 space-y-4">
                    <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 pb-3">
                      <div>
                        <h3 className="text-sm font-extrabold uppercase text-cyan-300">
                          B. Detail Metrik Indikator — {stockData.code} (Timeframe: {plan.timeframe_label})
                        </h3>
                        <p className="text-xs text-slate-400">
                          Kalkulasi terverifikasi bebas look-ahead bias dari {tech.candles_count} candle historis (Split-Adjusted).
                        </p>
                      </div>
                      <span className="px-3 py-1 rounded-lg bg-slate-900 border border-slate-700 text-xs font-mono text-emerald-300">
                        Data Status: {tech.has_sufficient_data ? 'VALID (Histori Memadai)' : 'INSUFFICIENT_DATA'}
                      </span>
                    </div>

                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono text-xs">
                      <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                        <div className="text-[10px] text-slate-400 font-sans">SMA-20 / SMA-50 / SMA-200</div>
                        <div className="font-bold text-white mt-1">
                          {fmtPrice(tech.sma_20)} / {fmtPrice(tech.sma_50)}
                        </div>
                        <div className="text-[10px] text-slate-400">SMA-200: {fmtPrice(tech.sma_200)}</div>
                      </div>
                      <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                        <div className="text-[10px] text-slate-400 font-sans">EMA-20 &amp; EMA-50</div>
                        <div className="font-bold text-cyan-300 mt-1">
                          {fmtPrice(tech.ema_20)} / {fmtPrice(tech.ema_50)}
                        </div>
                        <div className="text-[10px] text-slate-400">
                          Cross: {tech.ema_20 >= tech.ema_50 ? 'Bullish EMA Alignment' : 'Bearish EMA Alignment'}
                        </div>
                      </div>
                      <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                        <div className="text-[10px] text-slate-400 font-sans">Bollinger Bands (20, 2σ)</div>
                        <div className="font-bold text-white mt-1">
                          {fmtPrice(tech.bollinger?.lower)} – {fmtPrice(tech.bollinger?.upper)}
                        </div>
                        <div className="text-[10px] text-amber-300">
                          %B: {tech.bollinger?.percent_b}% • BW: {tech.bollinger?.bandwidth_pct}%
                        </div>
                      </div>
                      <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                        <div className="text-[10px] text-slate-400 font-sans">VWAP &amp; Wilder&apos;s ATR-14</div>
                        <div className="font-bold text-emerald-300 mt-1">
                          VWAP: {tech.vwap ? fmtPrice(tech.vwap) : 'N/A (EOD)'}
                        </div>
                        <div className="text-[10px] text-slate-400">
                          ATR-14: {fmtPrice(tech.atr_14)} ({tech.atr_pct}%)
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              );

              return isUltrawide ? (
                <div className="grid grid-cols-1 xl:grid-cols-12 gap-5 items-start">
                  <div className="xl:col-span-6 space-y-4">{chartCol}</div>
                  <div className="xl:col-span-6 space-y-4">{metricsCol}</div>
                </div>
              ) : (
                <div className="space-y-5">
                  {chartCol}
                  {metricsCol}
                </div>
              );
            })()}

            {/* =====================================================================
                TAB 3: FUNDAMENTAL ANALYSIS ENGINE (Section 4C)
               ===================================================================== */}
            {activeTab === 'fundamental' && (
              <div className="rounded-2xl border border-slate-800/90 bg-[#0b101d] p-5 space-y-5">
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 pb-3">
                  <div>
                    <h3 className="text-sm font-extrabold uppercase text-emerald-300">
                      C. Fundamental Analysis Engine — {stockData.code} ({fund.reporting_period})
                    </h3>
                    <p className="text-xs text-slate-400">
                      Mata Uang: {fund.currency} • Satuan: {fund.unit} • Status Data: {fund.data_status}
                    </p>
                  </div>
                </div>

                {fund.data_status !== 'VALID' ? (
                  <div className="p-5 rounded-xl bg-amber-500/10 border border-amber-500/30 text-xs text-amber-200">
                    <strong>Status Data: {fund.data_status}</strong> — {fund.reason}
                  </div>
                ) : (
                  <>
                    {/* Core Financial Metrics */}
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono text-xs">
                      <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                        <div className="text-[10px] text-slate-400 font-sans">Pendapatan (Revenue)</div>
                        <div className="text-sm font-bold text-white mt-0.5">
                          Rp {Number(fundMetrics.revenue_idr_b || 0).toLocaleString('id-ID')} Miliar
                        </div>
                        <div className="text-[10px] text-emerald-400">
                          YoY: {fundMetrics.revenue_yoy_pct >= 0 ? '+' : ''}{fundMetrics.revenue_yoy_pct}% • QoQ: +{fundMetrics.revenue_qoq_pct}%
                        </div>
                      </div>
                      <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                        <div className="text-[10px] text-slate-400 font-sans">Laba Bersih (Net Income)</div>
                        <div className="text-sm font-bold text-white mt-0.5">
                          Rp {Number(fundMetrics.net_income_idr_b || 0).toLocaleString('id-ID')} Miliar
                        </div>
                        <div className="text-[10px] text-cyan-300">
                          Net Margin: {fundMetrics.net_margin_pct}% • YoY: {fundMetrics.net_income_yoy_pct >= 0 ? '+' : ''}{fundMetrics.net_income_yoy_pct}%
                        </div>
                      </div>
                      <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                        <div className="text-[10px] text-slate-400 font-sans">EPS (TTM) &amp; BVPS</div>
                        <div className="text-sm font-bold text-amber-300 mt-0.5">
                          EPS: Rp {fundMetrics.eps_ttm} / lbr
                        </div>
                        <div className="text-[10px] text-slate-400">
                           Nilai Buku (BVPS): Rp {Number(fundMetrics.bvps || 0).toLocaleString('id-ID')}
                        </div>
                      </div>
                      <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                        <div className="text-[10px] text-slate-400 font-sans">Profitabilitas (ROE &amp; ROA)</div>
                        <div className="text-sm font-bold text-emerald-400 mt-0.5">
                          ROE: {fundMetrics.roe_pct}% • ROA: {fundMetrics.roa_pct}%
                        </div>
                        <div className="text-[10px] text-slate-400">
                          ROIC: {fundMetrics.roic_pct !== null ? `${fundMetrics.roic_pct}%` : 'N/A (Bank)'}
                        </div>
                      </div>
                    </div>

                    {/* Banking-Specific Metrics (BBRI, BBCA, BMRI, BBNI) */}
                    {bankMetrics && (
                      <div className="p-4 rounded-xl bg-cyan-500/10 border border-cyan-500/30 space-y-2.5">
                        <div className="text-xs font-extrabold uppercase text-cyan-300">
                          🏦 Indikator Khusus Sektor Perbankan (OJK / Bank Indonesia Standard)
                        </div>
                        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2 font-mono text-xs">
                          <div className="p-2 rounded-lg bg-slate-950 border border-slate-800">
                            <div className="text-[9px] text-slate-400">NIM</div>
                            <div className="font-bold text-emerald-400">{bankMetrics.nim_pct}%</div>
                          </div>
                          <div className="p-2 rounded-lg bg-slate-950 border border-slate-800">
                            <div className="text-[9px] text-slate-400">CASA Ratio</div>
                            <div className="font-bold text-cyan-300">{bankMetrics.casa_pct}%</div>
                          </div>
                          <div className="p-2 rounded-lg bg-slate-950 border border-slate-800">
                            <div className="text-[9px] text-slate-400">NPL Gross</div>
                            <div className="font-bold text-amber-300">{bankMetrics.npl_gross_pct}%</div>
                          </div>
                          <div className="p-2 rounded-lg bg-slate-950 border border-slate-800">
                            <div className="text-[9px] text-slate-400">NPL Net</div>
                            <div className="font-bold text-emerald-300">{bankMetrics.npl_net_pct}%</div>
                          </div>
                          <div className="p-2 rounded-lg bg-slate-950 border border-slate-800">
                            <div className="text-[9px] text-slate-400">CAR (Modal)</div>
                            <div className="font-bold text-white">{bankMetrics.car_pct}%</div>
                          </div>
                          <div className="p-2 rounded-lg bg-slate-950 border border-slate-800">
                            <div className="text-[9px] text-slate-400">LDR</div>
                            <div className="font-bold text-white">{bankMetrics.ldr_pct}%</div>
                          </div>
                          <div className="p-2 rounded-lg bg-slate-950 border border-slate-800">
                            <div className="text-[9px] text-slate-400">BOPO (CIR)</div>
                            <div className="font-bold text-white">{bankMetrics.bopo_pct}%</div>
                          </div>
                          <div className="p-2 rounded-lg bg-slate-950 border border-slate-800">
                            <div className="text-[9px] text-slate-400">Cost of Credit</div>
                            <div className="font-bold text-amber-300">{bankMetrics.coc_pct}%</div>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Earnings Quality & Strengths/Weaknesses */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                      <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
                        <div className="font-extrabold text-emerald-400 uppercase">
                          ✔ Kekuatan Fundamental &amp; Kualitas Laba
                        </div>
                        <p className="text-slate-300 font-semibold">{fund.earnings_quality?.status}</p>
                        <p className="text-slate-400">{fund.earnings_quality?.detail}</p>
                        <ul className="list-disc list-inside space-y-1 text-slate-200 pt-1">
                          {(fund.strengths || []).map((s: string, i: number) => (
                            <li key={i}>{s}</li>
                          ))}
                        </ul>
                      </div>
                      <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
                        <div className="font-extrabold text-amber-300 uppercase">
                          ⚠️ Risiko Utang, Arus Kas &amp; Tantangan
                        </div>
                        <p className="text-slate-300 font-semibold">
                          {fund.earnings_quality?.debt_and_cashflow_risk}
                        </p>
                        <ul className="list-disc list-inside space-y-1 text-slate-200 pt-1">
                          {(fund.weaknesses || []).map((w: string, i: number) => (
                            <li key={i}>{w}</li>
                          ))}
                        </ul>
                      </div>
                    </div>

                    {/* Peer Comparison Table */}
                    {fund.peers && fund.peers.length > 0 && (
                      <div className="space-y-2">
                        <h4 className="text-xs font-extrabold uppercase text-slate-300">
                          Perbandingan dengan Emiten Sejenis ({fund.sector})
                        </h4>
                        <div className="overflow-x-auto rounded-xl border border-slate-800">
                          <table className="w-full text-left border-collapse text-xs font-mono">
                            <thead>
                              <tr className="bg-slate-950 text-slate-400 border-b border-slate-800 text-[10px] uppercase">
                                <th className="py-2 px-3">Emiten</th>
                                <th className="py-2 px-3 text-right">PER (x)</th>
                                <th className="py-2 px-3 text-right">PBV (x)</th>
                                <th className="py-2 px-3 text-right">ROE (%)</th>
                                <th className="py-2 px-3 text-right">Net Margin (%)</th>
                                <th className="py-2 px-3 text-right">Payout Ratio</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-800">
                              {fund.peers.map((p: any) => (
                                <tr
                                  key={p.code}
                                  className={p.is_target ? 'bg-emerald-500/10 font-bold' : 'bg-slate-900/40'}
                                >
                                  <td className="py-2 px-3 text-white">
                                    {p.code} {p.is_target && <span className="text-emerald-400">(Aktif)</span>}
                                  </td>
                                  <td className="py-2 px-3 text-right text-slate-200">{p.pe_ratio ?? 'N/A'}x</td>
                                  <td className="py-2 px-3 text-right text-cyan-300">{p.pbv_ratio ?? 'N/A'}x</td>
                                  <td className="py-2 px-3 text-right text-emerald-400">{p.roe_pct}%</td>
                                  <td className="py-2 px-3 text-right text-slate-200">{p.net_margin_pct}%</td>
                                  <td className="py-2 px-3 text-right text-amber-300">{p.payout_ratio_pct}%</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}
                  </>
                )}
              </div>
            )}

            {/* =====================================================================
                TAB 4: VALUATION ENGINE (Section 4D)
               ===================================================================== */}
            {activeTab === 'valuation' && (
              <div className="rounded-2xl border border-slate-800/90 bg-[#0b101d] p-5 space-y-5">
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 pb-3">
                  <div>
                    <h3 className="text-sm font-extrabold uppercase text-amber-300">
                      D. Valuation Engine &amp; Estimasi Nilai Wajar — {stockData.code}
                    </h3>
                    <p className="text-xs text-slate-400">
                      Metode: {valEngine.methodology || 'N/A'} • Tanggal Valuasi: {valEngine.valuation_date}
                    </p>
                  </div>
                  {valEngine.valuation_status && (
                    <span className="px-3 py-1 rounded-xl bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 text-xs font-mono font-bold">
                      {valEngine.valuation_status}
                    </span>
                  )}
                </div>

                {valEngine.data_status !== 'VALID' ? (
                  <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 text-xs text-amber-200">
                    {valEngine.reason}
                  </div>
                ) : (
                  <>
                    {/* Bear, Base, Bull Fair Value Scenarios */}
                    <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 font-mono">
                      <div className="p-4 rounded-xl bg-slate-950 border border-slate-800">
                        <div className="text-[10px] font-sans uppercase text-slate-400">Harga Pasar Aktual</div>
                        <div className="text-xl font-black text-white mt-1">
                          {fmtPrice(valEngine.current_market_price)}
                        </div>
                        <div className="text-[10px] text-slate-400 mt-0.5">Harga perdagangan saat ini</div>
                      </div>
                      <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30">
                        <div className="text-[10px] font-sans uppercase text-rose-300 font-bold">Bear Case (Konservatif)</div>
                        <div className="text-xl font-black text-white mt-1">
                          {fmtPrice(valEngine.scenarios?.bear_case)}
                        </div>
                        <div className="text-[10px] text-slate-400 mt-0.5">Skenario pertumbuhan melambat</div>
                      </div>
                      <div className="p-4 rounded-xl bg-emerald-500/15 border border-emerald-500/40">
                        <div className="text-[10px] font-sans uppercase text-emerald-300 font-bold">
                          Base Case (Estimasi Wajar)
                        </div>
                        <div className="text-xl font-black text-emerald-400 mt-1">
                          {fmtPrice(valEngine.scenarios?.base_case)}
                        </div>
                        <div className="text-[10px] text-slate-200 mt-0.5">
                          Upside/Downside: {valEngine.potential_upside_pct >= 0 ? '+' : ''}{valEngine.potential_upside_pct}% (MoS {valEngine.margin_of_safety_pct}%)
                        </div>
                      </div>
                      <div className="p-4 rounded-xl bg-cyan-500/10 border border-cyan-500/30">
                        <div className="text-[10px] font-sans uppercase text-cyan-300 font-bold">Bull Case (Optimis)</div>
                        <div className="text-xl font-black text-white mt-1">
                          {fmtPrice(valEngine.scenarios?.bull_case)}
                        </div>
                        <div className="text-[10px] text-slate-400 mt-0.5">Ekspansi margin &amp; re-rating</div>
                      </div>
                    </div>

                    {/* Multiples Comparison */}
                    <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 font-mono text-xs">
                      <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                        <div className="text-[10px] text-slate-400 font-sans">PER Saat Ini vs Mean 5Th</div>
                        <div className="font-bold text-white mt-0.5">
                          {valEngine.multiples?.pe_ttm !== null ? `${valEngine.multiples?.pe_ttm}x` : 'N/A (Rugi)'} vs{' '}
                          {valEngine.multiples?.hist_5y_pe_avg ?? 'N/A'}x
                        </div>
                      </div>
                      <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                        <div className="text-[10px] text-slate-400 font-sans">PBV Saat Ini vs Mean 5Th</div>
                        <div className="font-bold text-cyan-300 mt-0.5">
                          {valEngine.multiples?.pbv}x vs {valEngine.multiples?.hist_5y_pbv_avg}x
                        </div>
                      </div>
                      <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                        <div className="text-[10px] text-slate-400 font-sans">PEG Ratio</div>
                        <div className="font-bold text-white mt-0.5">
                          {valEngine.multiples?.peg_ratio ?? 'N/A'}
                        </div>
                      </div>
                      <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                        <div className="text-[10px] text-slate-400 font-sans">EV / EBITDA</div>
                        <div className="font-bold text-white mt-0.5">
                          {valEngine.multiples?.ev_ebitda !== null ? `${valEngine.multiples?.ev_ebitda}x` : 'N/A (Bank)'}
                        </div>
                      </div>
                      <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                        <div className="text-[10px] text-slate-400 font-sans">Asumsi Model (Ke &amp; g)</div>
                        <div className="font-bold text-amber-300 mt-0.5">
                          Ke: {valEngine.assumptions?.cost_of_equity_ke_pct}% • g: {valEngine.assumptions?.terminal_growth_g_pct}%
                        </div>
                      </div>
                    </div>

                    <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-400">
                      ℹ️ <strong>Catatan Penting:</strong> {valEngine.disclaimer}
                    </div>
                  </>
                )}
              </div>
            )}

            {/* =====================================================================
                TAB 5: DIVIDEND INTELLIGENCE (Section 4E)
               ===================================================================== */}
            {activeTab === 'dividend' && (
              <div className="rounded-2xl border border-slate-800/90 bg-[#0b101d] p-5 space-y-5">
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 pb-3">
                  <div>
                    <h3 className="text-sm font-extrabold uppercase text-amber-300">
                      E. Dividend Intelligence &amp; Simulasi Pajak Dividen — {stockData.code}
                    </h3>
                    <p className="text-xs text-slate-400">
                      Pemisahan tegas antara Dividen Historis, Trailing 12 Months (TTM), dan Estimasi Dividen ke Depan.
                    </p>
                  </div>
                  <span className="px-3 py-1 rounded-xl bg-slate-900 border border-slate-700 text-xs font-mono text-emerald-300">
                    Keberlanjutan: {div.sustainability_status}
                  </span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 font-mono">
                  <div className="p-4 rounded-xl bg-slate-950 border border-slate-800">
                    <div className="text-[10px] font-sans uppercase text-slate-400 font-bold">
                      1. Rata-rata Dividen Historis (3 Tahun)
                    </div>
                    <div className="text-xl font-black text-white mt-1">
                      {fmtPrice(div.avg_3y_dividend_per_share)} / lembar
                    </div>
                    <div className="text-[11px] text-slate-400 mt-0.5">
                      CAGR Dividen: {div.dividend_cagr_3y_pct !== null ? `${div.dividend_cagr_3y_pct}%` : 'N/A'}
                    </div>
                  </div>
                  <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30">
                    <div className="text-[10px] font-sans uppercase text-amber-300 font-bold">
                      2. Dividen TTM (12 Bulan Terakhir Aktual)
                    </div>
                    <div className="text-xl font-black text-amber-300 mt-1">
                      {fmtPrice(div.ttm_dividend_per_share)} / lembar
                    </div>
                    <div className="text-[11px] text-slate-300 mt-0.5">
                      TTM Yield: {div.dividend_yield_pct}% ({div.frequency_per_year}x bayar/thn)
                    </div>
                  </div>
                  <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30">
                    <div className="text-[10px] font-sans uppercase text-emerald-300 font-bold">
                      3. Estimasi Dividen ke Depan (Proyeksi)
                    </div>
                    <div className="text-xl font-black text-emerald-400 mt-1">
                      {fmtPrice(div.forward_estimated_dividend_per_share)} / lembar
                    </div>
                    <div className="text-[11px] text-slate-300 mt-0.5">
                      Forward Yield: {div.forward_yield_pct}% • Payout: {div.payout_ratio_pct ?? 'N/A'}%
                    </div>
                  </div>
                </div>

                {/* Tax toggle & Lot Dividend Simulator */}
                <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 flex flex-wrap items-center justify-between gap-4 text-xs">
                  <div className="space-y-1">
                    <div className="font-bold text-white">
                      Simulasi Pendapatan Dividen untuk {lotsCount} Lot ({sharesCount.toLocaleString('id-ID')} Lembar):
                    </div>
                    <div className="text-slate-400">{div.tax_rules_indonesia?.regulation_note}</div>
                  </div>
                  <div className="flex items-center gap-3 font-mono">
                    <label className="flex items-center gap-2 cursor-pointer text-slate-200">
                      <input
                        type="checkbox"
                        checked={divTaxTenPct}
                        onChange={(e) => setDivTaxTenPct(e.target.checked)}
                        className="rounded accent-amber-400"
                      />
                      <span>Potong PPh Final 10%</span>
                    </label>
                    <div className="px-3 py-2 rounded-xl bg-amber-500/15 border border-amber-500/40 text-amber-300 font-bold">
                      Net Cair: {fmtPrice(netAnnualDivTotal)} / thn
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* =====================================================================
                TAB 6: TRADING PLAN GENERATOR (Section 4F)
               ===================================================================== */}
            {activeTab === 'trading_plan' && (
              <div className="rounded-2xl border border-slate-800/90 bg-[#0b101d] p-5 space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 pb-3">
                  <div>
                    <h3 className="text-sm font-extrabold uppercase text-cyan-300">
                      F. Structured Trading Plan Generator — {stockData.code} ({plan.timeframe_label})
                    </h3>
                    <p className="text-xs text-slate-400">
                      Dibuat: {plan.generated_at} • Berlaku s/d: {plan.valid_until}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={handleRecordSignalJournal}
                    className="px-3.5 py-2 rounded-xl bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-300 border border-cyan-500/40 text-xs font-bold"
                  >
                    📒 Catat Sinyal Ini ke Signal Journal
                  </button>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                  <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
                    <div className="font-bold text-cyan-300 uppercase">Syarat Konfirmasi Entry &amp; Keselarasan Tren</div>
                    <p className="text-slate-200">{plan.entry_confirmation}</p>
                    <p className="text-slate-400 font-mono">{plan.higher_tf_alignment}</p>
                  </div>
                  <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
                    <div className="font-bold text-rose-300 uppercase">
                      Level Invalidasi ({fmtPrice(plan.invalidation_level)}) &amp; Kondisi Pembatalan
                    </div>
                    <ul className="list-disc list-inside space-y-1 text-slate-300">
                      {(plan.cancellation_conditions || []).map((c: string, i: number) => (
                        <li key={i}>{c}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>
            )}

            {/* =====================================================================
                TAB 7: RISK MANAGEMENT ENGINE & POSITION SIZING (Section 4G)
               ===================================================================== */}
            {activeTab === 'risk' && (
              <div className="rounded-2xl border border-slate-800/90 bg-[#0b101d] p-5 space-y-5">
                <div className="border-b border-slate-800 pb-3">
                  <h3 className="text-sm font-extrabold uppercase text-emerald-300">
                    G. Risk Management Engine &amp; Position Sizing Calculator ({stockData.code})
                  </h3>
                  <p className="text-xs text-slate-400">
                    Menghitung ukuran lot maksimum berdasarkan batas risiko modal, komisi sekuritas BEI, slippage, dan skenario Stress Test Gap-Down / ARB.
                  </p>
                </div>

                <form onSubmit={handleRunRiskCalculator} className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs font-mono">
                  <div>
                    <label className="block text-[10px] text-slate-400 mb-1">Modal Tersedia (Rp)</label>
                    <input
                      type="number"
                      value={riskCapital}
                      onChange={(e) => setRiskCapital(parseFloat(e.target.value) || 0)}
                      className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-700 text-white"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] text-slate-400 mb-1">Harga Entry (Rp)</label>
                    <input
                      type="number"
                      value={riskEntry}
                      onChange={(e) => setRiskEntry(parseFloat(e.target.value) || 0)}
                      className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-700 text-cyan-300"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] text-slate-400 mb-1">Stop Loss (Rp)</label>
                    <input
                      type="number"
                      value={riskSl}
                      onChange={(e) => setRiskSl(parseFloat(e.target.value) || 0)}
                      className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-700 text-rose-300"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] text-slate-400 mb-1">Target Profit (Rp)</label>
                    <input
                      type="number"
                      value={riskTp}
                      onChange={(e) => setRiskTp(parseFloat(e.target.value) || 0)}
                      className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-700 text-emerald-300"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] text-slate-400 mb-1">Batas Risiko / Trade (%)</label>
                    <input
                      type="number"
                      step="0.25"
                      value={riskMaxPct}
                      onChange={(e) => setRiskMaxPct(parseFloat(e.target.value) || 1)}
                      className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-700 text-amber-300"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] text-slate-400 mb-1">Jumlah Lot Dipilih</label>
                    <input
                      type="number"
                      value={riskLots}
                      onChange={(e) => setRiskLots(parseInt(e.target.value, 10) || 1)}
                      className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-700 text-white"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] text-slate-400 mb-1">Fee Beli / Jual (%)</label>
                    <div className="flex gap-1">
                      <input
                        type="number"
                        step="0.05"
                        value={riskBuyFeePct}
                        onChange={(e) => setRiskBuyFeePct(parseFloat(e.target.value) || 0)}
                        className="w-1/2 px-2 py-2 rounded-lg bg-slate-950 border border-slate-700 text-white"
                      />
                      <input
                        type="number"
                        step="0.05"
                        value={riskSellFeePct}
                        onChange={(e) => setRiskSellFeePct(parseFloat(e.target.value) || 0)}
                        className="w-1/2 px-2 py-2 rounded-lg bg-slate-950 border border-slate-700 text-white"
                      />
                    </div>
                  </div>
                  <div className="flex items-end">
                    <button
                      type="submit"
                      className="w-full py-2 px-4 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-extrabold"
                    >
                      Hitung Risiko &amp; Lot
                    </button>
                  </div>
                </form>

                {riskError && (
                  <div className="p-3 rounded-xl bg-rose-500/15 border border-rose-500/40 text-rose-300 text-xs font-mono">
                    🛑 Validasi Ditolak: {riskError}
                  </div>
                )}

                {riskResult && (
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4 font-mono text-xs">
                    <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-1.5">
                      <div className="text-[10px] uppercase text-cyan-300 font-bold">Ukuran Posisi &amp; Biaya</div>
                      <div>Lot Maksimum Sesuai Risiko: <strong className="text-emerald-400">{riskResult.sizing?.recommended_max_lots} Lot</strong></div>
                      <div>Nilai Pembelian Bruto: <strong>{fmtPrice(riskResult.execution?.gross_buy_value_idr)}</strong></div>
                      <div>Total Fee + Slippage: <strong className="text-amber-300">{fmtPrice(riskResult.execution?.total_estimated_fees_idr)}</strong></div>
                      <div>Total Modal Dibutuhkan: <strong className="text-white">{fmtPrice(riskResult.execution?.total_capital_required_idr)}</strong></div>
                    </div>
                    <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-1.5">
                      <div className="text-[10px] uppercase text-emerald-300 font-bold">Potensi Hasil Bersih</div>
                      <div>Laba Bersih di Target: <strong className="text-emerald-400">+{fmtPrice(riskResult.execution?.net_profit_if_tp_idr)} (+{riskResult.execution?.net_profit_if_tp_pct}%)</strong></div>
                      <div>Rugi Bersih jika Kena SL: <strong className="text-rose-400">-{fmtPrice(riskResult.execution?.net_loss_if_sl_idr)}</strong></div>
                      <div>Persentase Risiko thd Modal: <strong className="text-amber-300">{riskResult.execution?.risk_of_total_capital_pct}%</strong></div>
                      <div>Net Risk/Reward Ratio: <strong className="text-cyan-300">1 : {riskResult.execution?.net_risk_reward_ratio}</strong></div>
                    </div>
                    <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 space-y-1.5">
                      <div className="text-[10px] uppercase text-rose-300 font-bold">⚠️ Skenario Gap-Down &amp; ARB BEI</div>
                      <div>Jika Gap-Down -5% di Bawah SL ({fmtPrice(riskResult.stress_scenarios?.gap_down_5pct_below_sl_price)}): <strong className="text-rose-400">-{fmtPrice(riskResult.stress_scenarios?.gap_down_5pct_net_loss_idr)}</strong></div>
                      <div>Jika Terkunci ARB ({fmtPrice(riskResult.stress_scenarios?.arb_lock_price)}): <strong className="text-rose-400">-{fmtPrice(riskResult.stress_scenarios?.arb_lock_net_loss_idr)}</strong></div>
                      <p className="text-[10px] font-sans text-slate-300 pt-1">{riskResult.stress_scenarios?.warning}</p>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* =====================================================================
                TAB 8: NEWS, CATALYSTS & MARKET INTELLIGENCE (Section 4H)
               ===================================================================== */}
            {activeTab === 'news' && (
              <div className="rounded-2xl border border-slate-800/90 bg-[#0b101d] p-5 space-y-5">
                <div className="border-b border-slate-800 pb-3">
                  <h3 className="text-sm font-extrabold uppercase text-cyan-300">
                    H. Market Intelligence, Sensitivitas Makro &amp; Berita Terverifikasi ({stockData.code})
                  </h3>
                  <p className="text-xs text-slate-400">
                    Memisahkan secara tegas Fakta Data, Interpretasi Analitis, dan Hipotesis Skenario.
                  </p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
                  <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-1">
                    <div className="font-bold text-emerald-400 uppercase">1. Fakta Data Terukur</div>
                    {(marketIntel.epistemic_separation?.facts || []).map((f: string, i: number) => (
                      <p key={i} className="text-slate-200">{f}</p>
                    ))}
                  </div>
                  <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-1">
                    <div className="font-bold text-cyan-300 uppercase">2. Interpretasi Analitis</div>
                    {(marketIntel.epistemic_separation?.interpretations || []).map((f: string, i: number) => (
                      <p key={i} className="text-slate-200">{f}</p>
                    ))}
                  </div>
                  <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-1">
                    <div className="font-bold text-amber-300 uppercase">3. Hipotesis &amp; Status Foreign Flow</div>
                    <p className="text-slate-300">{marketIntel.foreign_flow_status?.note}</p>
                  </div>
                </div>

                {/* News Articles List */}
                <div className="space-y-2">
                  <h4 className="text-xs font-extrabold uppercase text-white">
                    Berita Pasar &amp; Emiten Terkait (Lengkap dengan Sumber &amp; Link)
                  </h4>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {(marketIntel.news_articles || []).map((art: any, idx: number) => (
                      <a
                        key={idx}
                        href={art.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="p-3.5 rounded-xl bg-slate-950 hover:bg-slate-900 border border-slate-800 transition flex flex-col justify-between gap-2"
                      >
                        <div className="text-xs font-bold text-white line-clamp-2">{art.title}</div>
                        <div className="flex items-center justify-between text-[10px] font-mono text-slate-400">
                          <span className="text-cyan-300">{art.source}</span>
                          <span>{art.published_at}</span>
                        </div>
                      </a>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* =====================================================================
                TAB 9: AI STOCK ANALYST (Section 4I - 13 Mandatory Outputs)
               ===================================================================== */}
            {activeTab === 'ai_analyst' && (
              <div className="rounded-2xl border border-slate-800/90 bg-[#0b101d] p-5 space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 pb-3">
                  <div>
                    <h3 className="text-sm font-extrabold uppercase text-emerald-300">
                      I. AI Stock Analyst Synthesis — 13-Point Institutional Report ({stockData.code})
                    </h3>
                    <p className="text-xs text-slate-400">
                      Bebas Halusinasi Angka • Tingkat Keyakinan: {aiAnalyst.confidence_and_scoring_rubric?.confidence_level}
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      onClick={() => handleCopyResearchPrompt(false)}
                      className={`px-3.5 py-1.5 rounded-xl text-xs font-extrabold transition border ${
                        copiedPromptType === 'filled'
                          ? 'bg-emerald-500 text-slate-950 border-emerald-400'
                          : 'bg-indigo-600 hover:bg-indigo-500 text-white border-indigo-400/40'
                      }`}
                    >
                      {copiedPromptType === 'filled' ? '✓ Prompt Disalin!' : `📋 Copy Prompt AI (${stockData.code})`}
                    </button>
                    <button
                      type="button"
                      onClick={() => handleCopyResearchPrompt(true)}
                      className={`px-3 py-1.5 rounded-xl text-xs font-bold transition border ${
                        copiedPromptType === 'raw'
                          ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                          : 'bg-slate-900 hover:bg-slate-800 text-slate-300 border-slate-700'
                      }`}
                    >
                      {copiedPromptType === 'raw' ? '✓ Template Tersalin!' : '📄 Copy Template Mentah'}
                    </button>
                  </div>
                </div>

                {/* Transparent Pillar Scores */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono text-xs">
                  <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                    <div className="text-[10px] text-slate-400 font-sans">Skor Pilar Teknikal (0–100)</div>
                    <div className="text-lg font-black text-cyan-300">
                      {aiAnalyst.confidence_and_scoring_rubric?.pillar_scores?.technical_score_0_100 ?? 'N/A'} / 100
                    </div>
                  </div>
                  <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                    <div className="text-[10px] text-slate-400 font-sans">Skor Pilar Fundamental (0–100)</div>
                    <div className="text-lg font-black text-emerald-400">
                      {aiAnalyst.confidence_and_scoring_rubric?.pillar_scores?.fundamental_score_0_100 ?? 'UNAVAILABLE'}
                    </div>
                  </div>
                  <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                    <div className="text-[10px] text-slate-400 font-sans">Skor Pilar Valuasi (0–100)</div>
                    <div className="text-lg font-black text-amber-300">
                      {aiAnalyst.confidence_and_scoring_rubric?.pillar_scores?.valuation_score_0_100 ?? 'UNAVAILABLE'}
                    </div>
                  </div>
                  <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                    <div className="text-[10px] text-slate-400 font-sans">Win Rate Backtest Historis</div>
                    <div className="text-lg font-black text-white">
                      {aiAnalyst.confidence_and_scoring_rubric?.pillar_scores?.backtest_win_rate_pct ?? 0}%
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                  <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
                    <div className="font-bold text-white uppercase">1. Executive Summary &amp; Alasan Sinyal ({aiAnalyst.signal_rationale?.signal})</div>
                    <p className="text-slate-300 leading-relaxed">{aiAnalyst.executive_summary}</p>
                    <p className="text-emerald-300 font-semibold">{aiAnalyst.signal_rationale?.reason}</p>
                  </div>
                  <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
                    <div className="font-bold text-cyan-300 uppercase">2. Skenario Bullish, Base &amp; Bearish</div>
                    <p className="text-emerald-300"><strong>Bull:</strong> {aiAnalyst.scenarios?.bullish_case}</p>
                    <p className="text-slate-200"><strong>Base:</strong> {aiAnalyst.scenarios?.base_case}</p>
                    <p className="text-rose-300"><strong>Bear:</strong> {aiAnalyst.scenarios?.bearish_case}</p>
                  </div>
                </div>

                <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 text-[11px] text-slate-400">
                  <strong>Dokumentasi Metodologi Skor:</strong> {aiAnalyst.confidence_and_scoring_rubric?.rubric_documentation}
                </div>
              </div>
            )}

            {/* =====================================================================
                TAB 10: WALK-FORWARD BACKTEST, SIGNAL JOURNAL & PORTFOLIO (4J & 4K)
               ===================================================================== */}
            {activeTab === 'backtest' && (() => {
              const backtestCard = (
                <div className="rounded-2xl border border-slate-800/90 bg-[#0b101d] p-5 space-y-4">
                  <div className="border-b border-slate-800 pb-3">
                    <h3 className="text-sm font-extrabold uppercase text-amber-300">
                      J. Walk-Forward Backtest (70% In-Sample Training vs 30% Out-of-Sample Validation) — {stockData.code}
                    </h3>
                    <p className="text-xs text-slate-400">
                      Strategi: {backtest.strategy_name} • Sudah dipotong biaya transaksi BEI 0.40% + slippage.
                    </p>
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 font-mono text-xs">
                    <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                      <div className="text-[10px] text-slate-400">Total Trades</div>
                      <div className="text-sm font-bold text-white">{backtest.overall?.total_trades}</div>
                    </div>
                    <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                      <div className="text-[10px] text-slate-400">Win Rate</div>
                      <div className="text-sm font-bold text-emerald-400">{backtest.overall?.win_rate_pct}%</div>
                    </div>
                    <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                      <div className="text-[10px] text-slate-400">Total Net Return</div>
                      <div className="text-sm font-bold text-cyan-300">{backtest.overall?.total_net_return_pct}%</div>
                    </div>
                    <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                      <div className="text-[10px] text-slate-400">Profit Factor</div>
                      <div className="text-sm font-bold text-amber-300">{backtest.overall?.profit_factor}</div>
                    </div>
                    <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                      <div className="text-[10px] text-slate-400">Expectancy / Trade</div>
                      <div className="text-sm font-bold text-white">{backtest.overall?.expectancy_pct}%</div>
                    </div>
                    <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                      <div className="text-[10px] text-slate-400">Max Drawdown</div>
                      <div className="text-sm font-bold text-rose-400">-{backtest.overall?.max_drawdown_pct}%</div>
                    </div>
                    <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                      <div className="text-[10px] text-slate-400">In-Sample Ret</div>
                      <div className="text-sm font-bold text-slate-200">{backtest.in_sample_70pct?.total_net_return_pct}%</div>
                    </div>
                    <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                      <div className="text-[10px] text-slate-400">Out-of-Sample Ret</div>
                      <div className="text-sm font-bold text-emerald-300">{backtest.out_of_sample_30pct?.total_net_return_pct}%</div>
                    </div>
                  </div>
                </div>
              );

              const portfolioCard = (
                <div className="rounded-2xl border border-slate-800/90 bg-[#0b101d] p-5 space-y-4">
                  <div className="border-b border-slate-800 pb-3">
                    <h3 className="text-sm font-extrabold uppercase text-emerald-300">
                      K. Integrasi Portofolio Saham BEI Manual, Alokasi Sektor &amp; Watchlist
                    </h3>
                    <p className="text-xs text-slate-400">
                      Catat kepemilikan saham Anda untuk memantau Unrealized P/L (bersih fee jual), pendapatan dividen, dan risiko konsentrasi emiten.
                    </p>
                  </div>

                  <form onSubmit={handleSavePosition} className="grid grid-cols-1 sm:grid-cols-4 gap-3 text-xs font-mono">
                    <div>
                      <label className="block text-[10px] text-slate-400 mb-1">Kode Saham</label>
                      <input
                        type="text"
                        value={activeTicker}
                        disabled
                        className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-emerald-300 font-bold"
                      />
                    </div>
                    <div>
                      <label className="block text-[10px] text-slate-400 mb-1">Jumlah Lot (1 Lot = 100 lbr)</label>
                      <input
                        type="number"
                        min="1"
                        value={portLotsInput}
                        onChange={(e) => setPortLotsInput(e.target.value)}
                        className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-700 text-white"
                      />
                    </div>
                    <div>
                      <label className="block text-[10px] text-slate-400 mb-1">Harga Rata-rata Beli (Rp)</label>
                      <input
                        type="number"
                        min="1"
                        value={portAvgPriceInput}
                        onChange={(e) => setPortAvgPriceInput(e.target.value)}
                        className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-700 text-white"
                      />
                    </div>
                    <div className="flex items-end">
                      <button
                        type="submit"
                        className="w-full py-2 px-4 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-extrabold"
                      >
                        + Simpan Posisi {activeTicker}
                      </button>
                    </div>
                  </form>

                  {(portfolioData?.positions || []).length > 0 && (
                    <div className="overflow-x-auto rounded-xl border border-slate-800">
                      <table className="w-full text-left border-collapse text-xs font-mono">
                        <thead>
                          <tr className="bg-slate-950 text-slate-400 border-b border-slate-800 text-[10px] uppercase">
                            <th className="py-2 px-3">Saham &amp; Sektor</th>
                            <th className="py-2 px-3 text-right">Lot</th>
                            <th className="py-2 px-3 text-right">Avg Price</th>
                            <th className="py-2 px-3 text-right">Nilai Pasar</th>
                            <th className="py-2 px-3 text-right">Unrealized P/L</th>
                            <th className="py-2 px-3 text-right">Bobot</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-800">
                          {portfolioData.positions.map((pos: any) => (
                            <tr key={pos.id} className="hover:bg-slate-900/50">
                              <td className="py-2 px-3 text-white font-bold">
                                {pos.code} <span className="text-[10px] text-slate-400 font-normal">({pos.sector})</span>
                              </td>
                              <td className="py-2 px-3 text-right text-amber-300">{pos.lots} Lot</td>
                              <td className="py-2 px-3 text-right text-slate-200">{fmtPrice(pos.avg_buy_price, true, false)}</td>
                              <td className="py-2 px-3 text-right text-white">{fmtPrice(pos.market_value_idr, true, false)}</td>
                              <td className={`py-2 px-3 text-right font-bold ${pos.unrealized_pnl_idr >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                                {pos.unrealized_pnl_idr >= 0 ? '+' : ''}{fmtPrice(pos.unrealized_pnl_idr, true, false)} ({pos.unrealized_pnl_pct}%)
                              </td>
                              <td className="py-2 px-3 text-right text-cyan-300">{pos.portfolio_weight_pct}%</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              );

              return isUltrawide ? (
                <div className="grid grid-cols-1 xl:grid-cols-2 gap-5 items-start">
                  {backtestCard}
                  {portfolioCard}
                </div>
              ) : (
                <div className="space-y-5">
                  {backtestCard}
                  {portfolioCard}
                </div>
              );
            })()}

            {/* =====================================================================
                TAB 11: DATA QUALITY & SOURCE PROVENANCE (Section 4L)
               ===================================================================== */}
            {activeTab === 'sources' && (
              <div className="rounded-2xl border border-slate-800/90 bg-[#0b101d] p-5 space-y-4">
                <div className="border-b border-slate-800 pb-3">
                  <h3 className="text-sm font-extrabold uppercase text-cyan-300">
                    L. Data Quality, Provenance &amp; Source Validation ({stockData.code})
                  </h3>
                  <p className="text-xs text-slate-400">
                    {dataQuality.fail_closed_policy}
                  </p>
                </div>

                <div className="overflow-x-auto rounded-xl border border-slate-800">
                  <table className="w-full text-left border-collapse text-xs font-mono">
                    <thead>
                      <tr className="bg-slate-950 text-slate-400 border-b border-slate-800 text-[10px] uppercase">
                        <th className="py-2.5 px-3">Komponen Data</th>
                        <th className="py-2.5 px-3">Sumber Penyedia</th>
                        <th className="py-2.5 px-3">Periode / Timestamp</th>
                        <th className="py-2.5 px-3">Status Kualitas</th>
                        <th className="py-2.5 px-3">Hasil Validasi</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800">
                      {(dataQuality.fields || []).map((f: any, idx: number) => (
                        <tr key={idx} className="hover:bg-slate-900/50">
                          <td className="py-2.5 px-3 font-bold text-white">{f.field}</td>
                          <td className="py-2.5 px-3 text-slate-300">{f.source}</td>
                          <td className="py-2.5 px-3 text-slate-400">{f.reporting_period}</td>
                          <td className="py-2.5 px-3">
                            <span
                              className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                                f.status === 'VALID'
                                  ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                                  : f.status === 'DELAYED'
                                  ? 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                                  : 'bg-slate-800 text-slate-400 border-slate-700'
                              }`}
                            >
                              {f.status}
                            </span>
                          </td>
                          <td className="py-2.5 px-3 text-slate-300">{f.validation_result}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </>
        ) : null}
      </div>
    </>
  );
}
