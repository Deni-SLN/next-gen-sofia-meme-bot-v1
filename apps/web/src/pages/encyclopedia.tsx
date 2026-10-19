import React, { useState, useMemo } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { LucideIcon } from '@/components/LucideIcon';
import { useUltrawide, toggleUltrawide } from '@/lib/useUltrawide';

type CategoryType = 'ALL' | 'MENUS' | 'CRYPTO' | 'STOCKS' | 'GOLD' | 'TECHNICAL';

interface EncyclopediaItem {
  id: string;
  category: 'MENUS' | 'CRYPTO' | 'STOCKS' | 'GOLD' | 'TECHNICAL';
  title: string;
  subtitle?: string;
  tag: string;
  badgeTone: 'cyan' | 'emerald' | 'amber' | 'rose' | 'purple';
  routeLink?: string;
  routeLabel?: string;
  summary: string;
  details: string[];
  formulaOrRule?: string;
  tipsOrWarning?: string;
}

const ENCYCLOPEDIA_DATA: EncyclopediaItem[] = [
  // ==========================================
  // 1. PENJELASAN MENU SOFIA MARKET ANALYST
  // ==========================================
  {
    id: 'menu-command-center',
    category: 'MENUS',
    title: 'Command Center (Dashboard Utama)',
    subtitle: 'Rangkuman Alpha & Terminal Eksekusi Cepat',
    tag: 'MENU UTAMA',
    badgeTone: 'cyan',
    routeLink: '/',
    routeLabel: 'Buka Command Center',
    summary: 'Pusat kendali pasar real-time yang memadukan grafik ekuitas PnL harian, terminal beli instan token, radar koin baru, dan status bot trading.',
    details: [
      'Menampilkan ringkasan modal live & simulasi paper trading secara transparan.',
      'Menyediakan form eksekusi instan untuk menembak token Solana/Base dengan modal tetap (Quick Buy Presets: Rp 15rb, Rp 30rb, Rp 50rb, Rp 100rb).',
      'Memantau aktivitas terkini bot auto-sniper beserta status koneksi terminal relai on-chain.',
    ],
    tipsOrWarning: 'Gunakan preset modal kecil saat menguji koin baru yang likuiditasnya belum terkunci permanen.',
  },
  {
    id: 'menu-crypto-analysis',
    category: 'MENUS',
    title: 'Analisa Crypto & Staking Yield',
    subtitle: 'Trading Plan Multi-Timeframe & Tokenomics',
    tag: 'CRYPTO ENGINE',
    badgeTone: 'cyan',
    routeLink: '/crypto',
    routeLabel: 'Buka Analisa Crypto',
    summary: 'Modul komprehensif analisis teknikal aset kripto global 24/7 dengan 6 timeframe (15m, 1h, 4h, 1d, 1w, 1mo), kartu keputusan trading (Buy/Sell/Hold/Wait), dan simulasi staking yield Rupiah.',
    details: [
      'Multi-Tier Free Public Data: Otomatis mengambil data live dari Binance Vision Public Gateway, DexScreener, dan Yahoo Finance.',
      'Trading Plan Otomatis: Menyajikan Zona Beli (Entry Range), Target Profit 1 (Konservatif), Target Profit 2 (Ekspansi), Stop Loss, dan Rasio Reward/Risk bersih setelah potongan fee bursa & pajak kripto Indonesia (PPh 0.10% + PPN 0.11%).',
      'Tokenomics & Dilution Watch: Menghitung rasio FDV terhadap Market Cap untuk mendeteksi risiko dilusi token unlock VC.',
      'Chart Terpadu: Beralih antara Chart Kuantitatif (dengan overlay SNR, SMC, EMA200, Ichimoku, Fibonacci) dan Chart TradingView Interaktif.',
    ],
    tipsOrWarning: 'Sebelum entry, periksa status pasar Bitcoin Pulse. Hindari melawan tren utama saat BTC mengalami breakdown tajam.',
  },
  {
    id: 'menu-stocks-analysis',
    category: 'MENUS',
    title: 'Analisa Saham BEI (IHSG)',
    subtitle: 'Fundamental, Teknikal & Simulasi Lot Bersih',
    tag: 'PASAR MODAL',
    badgeTone: 'emerald',
    routeLink: '/stocks',
    routeLabel: 'Buka Analisa Saham',
    summary: 'Alat screening dan analisis emiten Bursa Efek Indonesia (IDX) lengkap dengan data historis harian, valuasi fundamental (PER, PBV, ROE, DER, Dividend Yield), serta simulasi lot beli bersih setelah fee broker & pajak.',
    details: [
      'Valuasi Saham: Mengkategorikan valuasi emiten (Murah/Undervalued, Wajar/Fair Value, Mahal/Overvalued) terhadap rata-rata historis 5 tahun.',
      'Simulasi Pembelian Lot: Menghitung jumlah lot yang diperoleh berdasarkan anggaran modal Rupiah dengan perhitungan fraksi harga resmi BEI.',
      'Analisis Dividen & Cum-Date: Mengingatkan tanggal Cum Dividen, Ex Date, dan yield dividen tunai per lembar saham.',
    ],
    tipsOrWarning: 'Perhitungkan selalu fee beli broker (~0.15%) dan fee jual + PPh Final (~0.25% + 0.10%) agar target profit Anda realistis di atas biaya transaksi.',
  },
  {
    id: 'menu-gold-portfolio',
    category: 'MENUS',
    title: 'Portofolio & Pasar Emas (XAU & Antam)',
    subtitle: 'Hedging Inflasi, Spread Buyback & Safe Haven',
    tag: 'LOGAM MULIA',
    badgeTone: 'amber',
    routeLink: '/gold',
    routeLabel: 'Buka Portofolio Emas',
    summary: 'Monitoring harga emas fisik Logam Mulia (Antam, UBS, Galeri 24) dan kontrak emas spot dunia (XAU/USD). Dilengkapi kalkulator spread buyback, simulasi laba gramasi, dan hedging inflasi aset.',
    details: [
      'Harga Spot vs Harga Fisik: Mengonversi harga Troy Ounce internasional ($/oz) ke Rupiah per gram live.',
      'Kalkulator Buyback Disiplin: Menghitung selisih harga jual dan harga beli kembali butik (spread rata-rata 8%–13%).',
      'Pajak Emas Batangan PPh 22: Simulasi pemotongan pajak resmi (0.45% untuk pembeli ber-NPWP dan 1.5% untuk buyback di atas Rp 10 juta).',
    ],
    tipsOrWarning: 'Emas fisik adalah instrumen pelindung nilai (safe haven) jangka menengah-panjang. Jangan jadikan instrumen scalping harian karena terbebani spread buyback.',
  },
  {
    id: 'menu-calculator-fixed-income',
    category: 'MENUS',
    title: 'Kalkulator Deposito & Obligasi SBN',
    subtitle: 'Simulasi Bunga Bank vs Kupon SBN dengan 1x Input',
    tag: 'FIXED INCOME',
    badgeTone: 'emerald',
    routeLink: '/calculator',
    routeLabel: 'Buka Kalkulator Deposito & Obligasi',
    summary: 'Alat simulasi dan komparasi instrumen pendapatan tetap perbankan vs Surat Berharga Negara (ORI, SR, SBR, FR). Menghitung estimasi bunga kotor, potongan pajak riil (PPh 20% vs 10%), serta keuntungan bersih bulanan.',
    details: [
      'Input Tunggal Otomatis: Cukup masukkan nominal 1x (misal Rp 10.000.000), kedua kartu instrumen langsung disimulasikan secara simultan.',
      'Pajak Deposito (PP No. 131/2000): Tarif 0% untuk saldo ≤ Rp 7.500.000 dan PPh Final 20% untuk saldo di atas Rp 7.500.000.',
      'Pajak Kupon SBN (PP No. 91/2021): Tarif PPh Final hanya 10% (hemat 50% dibanding deposito) dengan kupon rutin masuk rekening tiap bulan.',
      'Status Keamanan: Penjaminan LPS (maks Rp 2 Miliar) vs Jaminan Negara 100% tanpa batas plafon melalui Undang-Undang APBN.',
    ],
    tipsOrWarning: 'Obligasi negara (SBN) memberikan efisiensi pajak ganda: tarif pajak kupon hanya 10% dan kupon ditransfer otomatis setiap bulan tanpa menunggu jatuh tempo.',
  },
  {
    id: 'menu-pulse-trenches',
    category: 'MENUS',
    title: 'Trenches & Pulse Radar',
    subtitle: 'Screening Koin DEX & Peluncuran Baru Real-Time',
    tag: 'ON-CHAIN RADAR',
    badgeTone: 'cyan',
    routeLink: '/pulse',
    routeLabel: 'Buka Pulse Radar',
    summary: 'Radar live memecoin dan token micro-cap dari jaringan DEX (Solana, Base, Raydium, Uniswap) bersumber dari profil DexScreener dan ranking trench GMGN.ai.',
    details: [
      'Kategori Kolom: Terbagi menjadi Micro-Cap (< $100k MCap), Mid-Cap Momentum ($100k - $1M MCap), dan Graduated/Liquid Pool (> $1M).',
      'Filter Shield Skor: Menyaring koin berdasarkan tingkat keamanan kontrak (Skor Shield 0, 75, hingga 85 ke atas).',
      '1-Click Quick Snipe: Eksekusi pembelian cepat token terpilih dengan relay transaksi prioritas tinggi.',
    ],
  },
  {
    id: 'menu-auto-sniper',
    category: 'MENUS',
    title: 'Auto-Sniper Trading Bot',
    subtitle: 'Bot Eksekusi Otomatis Berkecepatan Tinggi',
    tag: 'BOT EKSEKUSI',
    badgeTone: 'emerald',
    routeLink: '/trading',
    routeLabel: 'Buka Auto-Sniper Bot',
    summary: 'Mesin trading otomatis yang mengeksekusi strategi pembelian token secara otonom berdasarkan filter likuiditas, skor keamanan, dan batasan risiko terprogram.',
    details: [
      '3 Mode Strategi: Conservative (hanya koin likuiditas besar > $50k), Balanced (kombinasi momentum dan keamanan), dan Aggressive Degens (pembelian agresif micro-cap).',
      'Simulasi Paper vs Live On-Chain: Pengguna dapat menguji strategi bot dengan modal virtual Rp 150.000 tanpa risiko kehilangan uang riil sebelum beralih ke dompet on-chain asli.',
      'Jito 0-Slot Relay & Anti-MEV: Mengirim transaksi langsung ke validator block leader untuk menghindari front-running sandwich bots.',
    ],
  },
  {
    id: 'menu-copytrade',
    category: 'MENUS',
    title: 'Smart Money & Copy-Trade',
    subtitle: 'Mirroring Dompet Whale Berkinerja Tinggi',
    tag: 'SMART MONEY',
    badgeTone: 'purple',
    routeLink: '/copytrade',
    routeLabel: 'Buka Smart Money',
    summary: 'Melacak dompet investor besar (whale) dengan win rate tinggi di blockchain Solana dan Base serta menyalin transaksi beli/jual mereka secara otomatis.',
    details: [
      'Metrik Dompet: Menampilkan 7-Day Realized PnL, Win Rate mingguan (%), dan rata-rata durasi hold koin.',
      'Batas Alokasi Maksimal: Menetapkan batas maksimum copy per transaksi (Max Copy USD) untuk melindungi saldo modal Anda dari over-exposure.',
    ],
  },
  {
    id: 'menu-rugcheck',
    category: 'MENUS',
    title: 'Rug, Cluster & Bundle Shield',
    subtitle: 'Audit On-Chain Mendalam & Verifikasi Ekosistem',
    tag: 'KEAMANAN KONTRAK',
    badgeTone: 'rose',
    routeLink: '/rugcheck',
    routeLabel: 'Buka Rug Shield',
    summary: 'Mesin audit on-chain mendalam untuk mendeteksi jebakan kode kontrak token (Honeypot, Mint Authority aktif, Freeze Authority, Permanent Delegate Token-2022) dan memetakan cluster wallet insider.',
    details: [
      'Filter Kontrak Dasar: Verifikasi status pelepasan hak kontrol (Mint Revoked & Freeze Revoked).',
      'Deteksi Ekstensi Token-2022: Menandai program Transfer Hook atau Interest Bearing yang dapat dimanipulasi pemilik token.',
      'Analisis Holder Non-AMM: Menghitung persentase kepemilikan 10 holder teratas di luar pool likuiditas DEX untuk mengantisipasi risiko dump berjamaah.',
      'Deep Links Platform Independen: Tautan verifikasi langsung ke Axiom, Raydium, Birdeye, RugCheck.xyz, Solscan, dan Bubblemaps.',
    ],
  },
  {
    id: 'menu-news',
    category: 'MENUS',
    title: 'News & Riset Pasar Indonesia',
    subtitle: 'Berita Finansial & Tag Sinyal Sentimen Risiko',
    tag: 'INTELIJEN BERITA',
    badgeTone: 'cyan',
    routeLink: '/news',
    routeLabel: 'Buka News & Riset',
    summary: 'Pusat agregasi berita pasar modal, crypto, emas, dan ekonomi makro berbahasa Indonesia terupdate (maksimal 7 hari terakhir) dengan tag sentimen risiko.',
    details: [
      'Tag Risiko Cerdas: Setiap artikel diklasifikasikan dengan tag sentimen: BAHAYA (merah), WASPADA (kuning), NETRAL (abu-abu), POSITIF (hijau toska), atau PELUANG CUAN (hijau emerald).',
      'Filter Multi-Kategori: Tab terpisah untuk Semua Berita, Crypto, Saham BEI, Emas Antam, Ekonomi Makro, dan Perkembangan Teknologi AI.',
    ],
  },
  {
    id: 'menu-portfolio-journal',
    category: 'MENUS',
    title: 'Portofolio, Jurnal & Kalender PnL',
    subtitle: 'Pencatatan Transaksi & Audit Performa Trading',
    tag: 'PORTOFOLIO',
    badgeTone: 'emerald',
    routeLink: '/calendar',
    routeLabel: 'Buka Kalender PnL',
    summary: 'Pusat evaluasi performa trading harian yang mencatat riwayat transaksi, PnL bersih, rasio kemenangan (Win Rate), serta tampilan kalender bulanan interaktif hijau (profit) dan merah (loss).',
    details: [
      'Integrasi Neon Cloud Database: Menyimpan riwayat eksekusi bot secara permanen pada database PostgreSQL cloud.',
      'Settlement 05:00 WIB: Audit otomatis harian untuk merekap keuntungan dan menjaga cadangan gas fee.',
    ],
  },

  // ==========================================
  // 2. ISTILAH-ISTILAH CRYPTO & WEB3
  // ==========================================
  {
    id: 'crypto-blockchain-consensus',
    category: 'CRYPTO',
    title: 'Blockchain, PoW & PoS',
    subtitle: 'Fondasi Jaringan Terdistribusi & Konsensus',
    tag: 'FONDASI WEB3',
    badgeTone: 'cyan',
    summary: 'Blockchain adalah buku besar terdistribusi yang mencatat transaksi secara permanen tanpa otoritas tunggal terpusat.',
    details: [
      'Proof of Work (PoW): Konsensus berbasis komputasi penambangan matematis (contoh: Bitcoin). Sangat aman dan terdesentralisasi, namun membutuhkan konsumsi daya listrik tinggi.',
      'Proof of Stake (PoS): Konsensus berbasis kepemilikan koin yang dipertaruhkan (staking) untuk memvalidasi blok (contoh: Ethereum, Solana). Sangat hemat energi dan berkecepatan tinggi.',
      'Halving Bitcoin: Peristiwa pemotongan reward blok Bitcoin menjadi separuhnya setiap 210.000 blok (~4 tahun sekali), membatasi suplai maksimal BTC tetap 21 Juta koin selamanya.',
    ],
    formulaOrRule: 'Tingkat Inflasi Tahunan BTC Pasca Halving 2024 = ~0.83% per tahun (Lebih langka dari produksi emas baru).',
  },
  {
    id: 'crypto-dex-vs-cex',
    category: 'CRYPTO',
    title: 'DEX vs CEX & AMM',
    subtitle: 'Bursa Desentralisasi vs Bursa Terpusat',
    tag: 'BURSA KRIPTO',
    badgeTone: 'cyan',
    summary: 'DEX memungkinkan pertukaran koin langsung antar pengguna via smart contract tanpa perantara, sedangkan CEX dikelola perusahaan kustodian.',
    details: [
      'CEX (Centralized Exchange): Bursa seperti Binance, Tokocrypto, Indodax. Pengguna wajib KYC dan aset disimpan di dompet bursa (Not your keys, not your coins).',
      'DEX (Decentralized Exchange): Bursa seperti Raydium, Uniswap, Orca. Transaksi non-kustodian langsung dari dompet pengguna (Phantom, MetaMask).',
      'AMM (Automated Market Maker): Algoritma penetapan harga otomatis berbasis kolam likuiditas (Liquidity Pool) menggunakan rumus perkalian konstan x * y = k.',
      'Impermanent Loss: Potensi kerugian sementara penyedia likuiditas (LP provider) akibat perubahan harga drastis salah satu token yang dipasangkan dibandingkan jika hanya menyimpan token secara pasif.',
    ],
    formulaOrRule: 'Rumus Dasar AMM: x (Jumlah Koin A) × y (Jumlah Koin B) = k (Konstanta Likuiditas)',
  },
  {
    id: 'crypto-slippage-mev',
    category: 'CRYPTO',
    title: 'Slippage, MEV & Jito Bribe Relay',
    subtitle: 'Toleransi Pergeseran Harga & Perlindungan Front-Running',
    tag: 'EKSEKUSI ON-CHAIN',
    badgeTone: 'rose',
    summary: 'Slippage adalah deviasi harga antara saat order dikirim dan saat tereksekusi. MEV adalah bot pencuri selisih harga yang dapat dicegah dengan relai Anti-MEV.',
    details: [
      'Slippage Tolerance: Persentase pergeseran harga yang diizinkan trader. Pada koin meme yang volatil, slippage 5%–15% sering dibutuhkan agar transaksi tidak gagal.',
      'MEV (Maximal Extractable Value): Keuntungan yang diambil oleh bot pencari celah di mempool dengan menyisipkan transaksi sebelum dan sesudah transaksi Anda (Sandwich Attack).',
      'Jito Bribe Relay: Pengiriman transaksi langsung ke validator terpercaya Solana melalui bundle tertutup (0-slot), melewati mempool publik sehingga 100% aman dari sandwich bot.',
    ],
    tipsOrWarning: 'Jangan gunakan slippage di atas 20% pada pool DEX tanpa mengaktifkan fitur Anti-MEV, karena transaksi Anda akan menjadi sasaran empuk sandwich bot.',
  },
  {
    id: 'crypto-mcap-vs-fdv',
    category: 'CRYPTO',
    title: 'Market Cap vs FDV & Token Unlock',
    subtitle: 'Kapitalisasi Pasar Beredar vs Valuasi Penuh',
    tag: 'TOKENOMICS',
    badgeTone: 'purple',
    summary: 'Market Cap mencerminkan valuasi koin yang beredar saat ini, sedangkan FDV memperhitungkan seluruh suplai koin di masa depan termasuk jatah vesting investor.',
    details: [
      'Market Cap (Kapitalisasi Pasar): Harga Koin saat ini dikalikan Jumlah Koin yang Sudah Beredar (Circulating Supply).',
      'FDV (Fully Diluted Valuation): Harga Koin saat ini dikalikan Total Suplai Maksimal (Max Supply).',
      'Rasio FDV / Market Cap: Jika nilainya > 2.0x, artinya masih ada suplai token raksasa yang belum dirilis dan akan menimbulkan tekanan jual saat jadwal Token Unlock dibuka.',
    ],
    formulaOrRule: 'Market Cap = Harga × Circulating Supply | FDV = Harga × Max Supply',
    tipsOrWarning: 'Waspadai token dengan Market Cap $100M tetapi FDV $2Milyar (Rasio 20x), karena harga berisiko anjlok terus-menerus akibat emisi token baru setiap bulan.',
  },
  {
    id: 'crypto-contract-safety',
    category: 'CRYPTO',
    title: 'Audit Kontrak: Mint, Freeze & Token-2022',
    subtitle: 'Pemeriksaan Risiko Rugpull, Honeypot & Ekstensi Solana',
    tag: 'KEAMANAN SIBER',
    badgeTone: 'rose',
    summary: 'Kunci keselamatan trading on-chain: memeriksa otoritas pencetakan, pembekuan dompet, dan celah ekstensi kode kontrak.',
    details: [
      'Mint Authority: Hak pemilik kontrak untuk mencetak token baru tanpa batas. Jika statusnya "ACTIVE", pemilik bisa mencetak triliunan koin baru dan mendumpnya ke pool likuiditas (wajib "REVOKED").',
      'Freeze Authority: Hak pemilik kontrak untuk membekukan akun dompet pengguna sehingga koin yang sudah dibeli tidak dapat ditransfer atau dijual (wajib "REVOKED").',
      'Token-2022 Extensions: Standar baru token Solana yang membawa fitur canggih seperti Transfer Hook (pemilik memotong fee setiap transfer) atau Permanent Delegate (pemilik bisa menarik token dari dompet Anda tanpa izin).',
      'Honeypot: Smart contract jahat yang mengatur kode sedemikian rupa sehingga pembeli diizinkan membeli koin, namun gagal total saat mencoba menjual kembali.',
      'Wash Trading: Rekayasa volume transaksi palsu oleh dev token yang memperjualbelikan koin di antara dompet miliknya sendiri untuk memancing indikator trending DEX.',
    ],
  },
  {
    id: 'crypto-staking-yield',
    category: 'CRYPTO',
    title: 'Staking, Liquid Staking & APR vs APY',
    subtitle: 'Pendapatan Pasif On-Chain & Validasi Jaringan',
    tag: 'PASSIVE INCOME',
    badgeTone: 'emerald',
    summary: 'Mendapatkan imbal hasil pasif dengan mengunci koin untuk memvalidasi transaksi di jaringan Proof of Stake.',
    details: [
      'Native PoS Staking: Mengunci koin langsung ke validator jaringan (misal SOL ~6.8% APR, ETH ~3.4% APR).',
      'Liquid Staking (LST): Mengunci koin melalui protokol pihak ketiga (Lido, Jito) dan menerima token representasi (stETH, JitoSOL) yang tetap bisa digunakan untuk trading atau yield farming.',
      'APR (Annual Percentage Rate): Persentase imbal hasil tahunan dengan perhitungan bunga tunggal sederhana tanpa reinvestasi.',
      'APY (Annual Percentage Yield): Persentase imbal hasil tahunan yang memperhitungkan efek bunga berbunga majemuk (compounding interest).',
    ],
  },

  // ==========================================
  // 3. ISTILAH-ISTILAH SAHAM (IHSG & BEI)
  // ==========================================
  {
    id: 'stocks-ihsg-lot',
    category: 'STOCKS',
    title: 'IHSG, Satuan Lot & Papan Pencatatan',
    subtitle: 'Dasar Mekanisme Perdagangan Saham di Indonesia',
    tag: 'BURSA EFEK INDONESIA',
    badgeTone: 'emerald',
    summary: 'Mekanisme perdagangan pasar modal Indonesia yang diatur oleh Otoritas Jasa Keuangan (OJK) dan Bursa Efek Indonesia (BEI).',
    details: [
      'IHSG (Indeks Harga Saham Gabungan): Indeks komposit yang mengukur performa pergerakan seluruh saham yang tercatat di BEI (Kode: COMPOSITE / ^JKSE).',
      'Satuan Lot: Satuan minimum transaksi saham di BEI. 1 Lot = 100 lembar saham.',
      'Papan Utama: Berisi saham perusahaan berkapitalisasi besar, rekam jejak keuangan matang, dan memiliki aset bersih minimal Rp 100 Miliar.',
      'Papan Pengembangan: Berisi saham perusahaan yang sedang bertumbuh dan belum memenuhi kriteria papan utama.',
      'Papan Akselerasi: Dikhususkan bagi perusahaan rintisan (startup) dan UMKM dengan aset bersih di bawah Rp 50 Miliar.',
    ],
    formulaOrRule: 'Modal Pembelian Saham = Harga Saham per Lembar × (Jumlah Lot × 100) + Fee Broker & Pajak',
  },
  {
    id: 'stocks-orderbook-haka-haki',
    category: 'STOCKS',
    title: 'Order Book: Bid, Offer, HAKA & HAKI',
    subtitle: 'Antrean Transaksi & Aksi Agresif Pasar',
    tag: 'ORDER FLOW',
    badgeTone: 'emerald',
    summary: 'Order Book adalah buku antrean transaksi terbuka yang mempertemukan pihak pembeli (Bid) dan penjual (Offer/Ask).',
    details: [
      'Bid (Antrean Beli): Kolom daftar harga dan volume lot yang ditawarkan oleh pihak yang ingin membeli saham di harga bawah.',
      'Offer / Ask (Antrean Jual): Kolom daftar harga dan volume lot yang ditawarkan oleh pihak yang ingin menjual saham di harga atas.',
      'HAKA (Hajar Kanan): Pembelian saham secara agresif dengan langsung memakan antrean jual terendah di kolom Offer agar order langsung match saat itu juga.',
      'HAKI (Hajar Kiri): Penjualan saham secara agresif dengan langsung membuang ke antrean beli tertinggi di kolom Bid untuk mengeksekusi order seketika.',
    ],
  },
  {
    id: 'stocks-ara-arb-fraksi',
    category: 'STOCKS',
    title: 'ARA, ARB & Fraksi Harga Saham BEI',
    subtitle: 'Batas Kenaikan/Penurunan Harian & Tick Harga',
    tag: 'REGULASI PASAR',
    badgeTone: 'amber',
    summary: 'BEI menerapkan batas Auto Rejection untuk mencegah volatilitas harga yang tidak wajar serta fraksi harga teratur.',
    details: [
      'ARA (Auto Rejection Atas): Batas persentase kenaikan harga saham maksimal dalam 1 hari perdagangan. Jika tercapai, sistem menolak order beli di harga yang lebih tinggi.',
      'ARB (Auto Rejection Bawah): Batas persentase penurunan harga saham maksimal dalam 1 hari perdagangan (saat ini sistem simetris 20% - 35% sesuai rentang harga).',
      'Fraksi Harga BEI: Kelipatan kenaikan harga per tick (Rp 1 untuk harga < Rp 200; Rp 2 untuk Rp 200–Rp 500; Rp 5 untuk Rp 500–Rp 2.000; Rp 10 untuk Rp 2.000–Rp 5.000; Rp 25 untuk > Rp 5.000).',
    ],
  },
  {
    id: 'stocks-fundamental-ratios',
    category: 'STOCKS',
    title: 'Rasio Valuasi: PER, PBV, ROE & DER',
    subtitle: 'Analisis Fundamental Kinerja Keuangan Perusahaan',
    tag: 'FUNDAMENTAL EMITEN',
    badgeTone: 'emerald',
    summary: 'Rasio finansial utama yang digunakan investor institusi dan analis untuk menilai kesehatan dan kewajaran harga suatu saham.',
    details: [
      'PER (Price to Earnings Ratio): Mengukur seberapa mahal harga saham dibandingkan laba bersih per lembar (EPS). Semakin rendah PER relatif terhadap industri, semakin murah saham tersebut.',
      'PBV (Price to Book Value): Mengukur rasio harga saham terhadap nilai buku ekuitas perusahaan. PBV < 1.0x menandakan saham dijual di bawah nilai modal bersihnya.',
      'ROE (Return on Equity): Mengukur seberapa efisien manajemen perusahaan menghasilkan laba bersih dari modal investor. Standar emiten unggulan (blue chip) umumnya ROE > 15%.',
      'DER (Debt to Equity Ratio): Membandingkan total hutang terhadap ekuitas. DER di bawah 1.0x (100%) menunjukkan risiko gagal bayar yang aman.',
    ],
    formulaOrRule: 'PER = Harga Saham / Laba per Saham (EPS) | PBV = Harga Saham / Nilai Buku (BVPS)',
  },
  {
    id: 'stocks-corporate-actions',
    category: 'STOCKS',
    title: 'Aksi Korporasi: Dividen, Cum Date & Stock Split',
    subtitle: 'Jadwal Hak Pemegang Saham & Restrukturisasi Modal',
    tag: 'DIVIDEN & HAK',
    badgeTone: 'purple',
    summary: 'Peristiwa korporasi yang berdampak langsung pada jumlah lembar saham, harga teoritis, dan hak pembagian keuntungan.',
    details: [
      'Cum Date (Cumulative Date): Hari perdagangan bursa terakhir di mana investor yang membeli saham masih berhak mendapatkan dividen tunai.',
      'Ex Date (Expired Date): Hari perdagangan bursa pertama di mana pembelian saham sudah tidak lagi berhak mendapatkan dividen (harga saham biasanya terkoreksi sebesar nilai dividen).',
      'Payment Date: Tanggal pencairan dana dividen tunai langsung ke Rekening Dana Nasabah (RDN).',
      'Stock Split: Pemecahan nilai nominal saham (misal rasio 1:5) sehingga harga per lembar menjadi lebih murah dan jumlah lembar bertambah tanpa mengubah nilai total ekuitas pemegang saham.',
      'Right Issue (HMETD): Hak Memesan Efek Terlebih Dahulu yang diberikan kepada investor lama untuk membeli saham baru yang diterbitkan perusahaan.',
    ],
    tipsOrWarning: 'Hati-hati terhadap "Dividend Trap" — membeli saham saat Cum Date hanya demi dividen 5%, namun harga saham anjlok 10% saat Ex Date dibuka.',
  },

  // ==========================================
  // 4. ISTILAH-ISTILAH KEUANGAN & EMAS (XAU)
  // ==========================================
  {
    id: 'gold-xau-troy-ounce',
    category: 'GOLD',
    title: 'Emas Spot Dunia (XAU/USD) & Troy Ounce',
    subtitle: 'Pasar Komoditas Global & Standar Konversi Gram',
    tag: 'LOGAM MULIA',
    badgeTone: 'amber',
    summary: 'Emas internasional diperdagangkan di pasar spot dengan simbol XAU/USD dalam satuan Troy Ounce.',
    details: [
      'XAU/USD: Simbol perdagangan internasional untuk 1 Troy Ounce emas murni terhadap mata uang Dolar AS.',
      'Troy Ounce: Standar ukuran berat logam mulia internasional. 1 Troy Ounce setara dengan tepat 31.1034768 gram (berbeda dengan ounce biasa yang setara 28.35 gram).',
      'Safe Haven Asset: Aset keuangan yang nilainya cenderung bertahan stabil atau bahkan menguat saat pasar saham atau kondisi ekonomi global mengalami krisis geopolitik.',
      'Hubungan Emas & Indeks Dolar (DXY): Hubungan terbalik — saat Dolar AS menguat tajam, harga emas cenderung tertekan, dan sebaliknya saat Dolar melemah, emas menjadi buruan lindung nilai.',
    ],
    formulaOrRule: 'Harga Emas per Gram (IDR) = (Harga XAU/USD × Kurs USD/IDR) / 31.1035',
  },
  {
    id: 'gold-antam-buyback-spread',
    category: 'GOLD',
    title: 'Emas Fisik Antam, Harga Buyback & Spread',
    subtitle: 'Mekanisme Selisih Beli dan Jual Kembali Logam Mulia',
    tag: 'EMAS BATANGAN',
    badgeTone: 'amber',
    summary: 'Emas batangan kemasan CertiCard memiliki harga pembelian dan patokan harga jual kembali (buyback) resmi dari produsen.',
    details: [
      'Harga Beli Logam Mulia: Harga yang dibayarkan investor saat membeli emas fisik dari butik resmi (Antam, UBS, Galeri 24).',
      'Harga Buyback (Pembelian Kembali): Harga resmi yang ditawarkan produsen saat membeli kembali emas dari tangan investor.',
      'Spread Buyback: Selisih persentase antara harga beli dan harga buyback (umumnya berkisar 8% s/d 13%). Keuntungan baru tercipta ketika kenaikan harga emas telah melampaui persentase spread ini.',
      'Kemasan CertiCard: Segel pengaman modern yang menyatukan emas batangan dengan sertifikat keaslian berteknologi barcode/QR micro-text.',
    ],
    formulaOrRule: 'Spread Buyback (%) = ((Harga Beli - Harga Buyback) / Harga Beli) × 100%',
    tipsOrWarning: 'Jangan merusak atau membuka segel kemasan CertiCard, karena akan menurunkan nilai harga buyback saat diverifikasi oleh juru taksir.',
  },
  {
    id: 'gold-tax-regulation',
    category: 'GOLD',
    title: 'Regulasi Pajak Emas Fisik di Indonesia (PPh 22)',
    subtitle: 'Peraturan Menteri Keuangan No. 48/PMK.03/2023',
    tag: 'PAJAK FINANSIAL',
    badgeTone: 'rose',
    summary: 'Ketentuan pemotongan pajak penghasilan resmi pada transaksi jual-beli emas batangan murni di Indonesia.',
    details: [
      'Pajak Pembelian Emas: Dikenakan PPh Pasal 22 sebesar 0.45% untuk pembeli yang mencantumkan NPWP (atau 0.90% untuk yang tidak memiliki NPWP). Bukti potong pajak diterbitkan butik.',
      'Pajak Penjualan Kembali (Buyback): Jika nilai total transaksi buyback melebihi Rp 10.000.000, dikenakan PPh Pasal 22 sebesar 1.5% (ber-NPWP) atau 3.0% (tanpa NPWP). Transaksi buyback di bawah Rp 10 juta dibebaskan dari pemotongan PPh 22.',
      'Kadar Kemurnian 99.99%: Emas batangan investasi dibebaskan dari Pajak Pertambahan Nilai (PPN 0%) karena dikategorikan sebagai instrumen moneter resmi.',
    ],
  },

  // ==========================================
  // 5. ISTILAH ANALISIS TEKNIKAL MODERN
  // ==========================================
  {
    id: 'tech-snr-breakout',
    category: 'TECHNICAL',
    title: 'SNR: Support, Resistance & Retest',
    subtitle: 'Identifikasi Zona Reaksi Penawaran & Permintaan',
    tag: 'PRICE ACTION',
    badgeTone: 'cyan',
    summary: 'Support adalah lantai harga di mana minat beli menahan penurunan, sedangkan Resistance adalah atap harga penahan kenaikan.',
    details: [
      'Swing High & Swing Low: Titik puncak lokal dan dasar lembah lokal yang tervalidasi oleh lilin konfirmasi di kanan dan kirinya.',
      'Breakout: Penembusan level Resistance ke atas dengan volume signifikan, menandakan kelanjutan momentum beli.',
      'Breakdown: Penembusan level Support ke bawah, menandakan dominasi tekanan jual.',
      'Retest: Pergerakan harga yang kembali menguji level yang baru saja ditembus (Resistance yang ditembus berubah fungsi menjadi Support baru / RBS - Resistance Becomes Support).',
    ],
  },
  {
    id: 'tech-smc-bos-choch',
    category: 'TECHNICAL',
    title: 'SMC: BOS, CHoCH, Order Block & FVG',
    subtitle: 'Smart Money Concepts & Jejak Likuiditas Pasar',
    tag: 'SMART MONEY',
    badgeTone: 'purple',
    summary: 'Metode analisis struktur pasar institusional berdasarkan jejak likuiditas, perpindahan karakter tren, dan zona ketidakseimbangan harga.',
    details: [
      'BOS (Break of Structure): Penembusan swing high dalam tren naik atau swing low dalam tren turun yang mengonfirmasi bahwa tren utama masih berlanjut.',
      'CHoCH (Change of Character): Tanda awal pembalikan arah tren ketika struktur swing terakhir tertembus ke arah yang berlawanan.',
      'Order Block (OB): Jejak lilin berlawanan arah terakhir sebelum terjadinya pergerakan impulsif tajam (Demand Zone untuk Bullish OB, Supply Zone untuk Bearish OB).',
      'FVG (Fair Value Gap): Celah ketidakseimbangan antara lilin ke-1 dan lilin ke-3 di mana lilin ke-2 bergerak terlalu cepat sehingga meninggalkan area harga kosong yang berpeluang ditutup kembali.',
      'Liquidity Sweep: Manuver harga yang menusuk swing high/low untuk menyerap stop loss ritel sebelum berbalik arah secara agresif.',
    ],
  },
  {
    id: 'tech-ema200-ichimoku',
    category: 'TECHNICAL',
    title: 'EMA 200 & Ichimoku Kinko Hyo',
    subtitle: 'Filter Tren Makro & Keseimbangan Awan Kumo',
    tag: 'INDIKATOR TREN',
    badgeTone: 'cyan',
    summary: 'Dua instrumen tren teruji untuk memfilter arah pergerakan harga jangka menengah dan jangka panjang.',
    details: [
      'EMA 200 (Exponential Moving Average 200): Garis rata-rata bobot 200 periode. Harga di atas EMA 200 = Bias Tren Bullish; harga di bawah EMA 200 = Bias Tren Bearish.',
      'Golden Cross & Death Cross: Golden Cross terjadi saat moving average jangka pendek (EMA 50) memotong ke atas EMA 200; Death Cross saat memotong ke bawah.',
      'Ichimoku Cloud (Kumo): Sistem analisis komprehensif asal Jepang yang terdiri dari Tenkan-sen (garis konversi 9 periode), Kijun-sen (garis dasar 26 periode), Senkou Span A & B (proyeksi awan Kumo 26 periode ke depan), dan Chikou Span (plot harga penutupan mundur 26 periode).',
      'Sinyal Awan Kumo: Harga di atas awan Kumo menandakan tren bullish kuat; ketebalan awan mencerminkan kekuatan support masa depan.',
    ],
  },
  {
    id: 'tech-fibonacci-risk-reward',
    category: 'TECHNICAL',
    title: 'Fibonacci Retracement & Rasio R/R',
    subtitle: 'Golden Pocket (61.8%) & Manajemen Risiko Posisi',
    tag: 'MANAJEMEN RISIKO',
    badgeTone: 'emerald',
    summary: 'Rasio matematis Fibonacci untuk memprediksi kedalaman koreksi harga dan aturan disiplin rasio imbalan terhadap risiko.',
    details: [
      'Level Retracement: 0%, 23.6%, 38.2%, 50.0%, 61.8%, 78.6%, dan 100.0%.',
      'Golden Pocket (50% – 61.8%): Area retest paling diminati trader kuantitatif untuk mengambil posisi searah impuls tren utama.',
      'Rasio Reward/Risk (R/R): Perbandingan antara potensi keuntungan bersih (Target Profit) terhadap potensi kerugian maksimal (Stop Loss). Sistem SOFIA menetapkan standar minimal R/R 1.50x.',
      'Position Sizing Rule: Tidak mempertaruhkan lebih dari 1%–2% total modal portofolio dalam 1 kali transaksi, terlepas dari seberapa yakin Anda terhadap sinyal tersebut.',
    ],
    formulaOrRule: 'Net R/R = (Harga TP - Harga Entry - Fee Bursa) / (Harga Entry - Harga Stop Loss + Fee Bursa)',
    tipsOrWarning: 'Jika rasio R/R suatu rencana trading di bawah 1.30x, abaikan setup tersebut karena imbalan tidak sebanding dengan risiko yang ditanggung.',
  },
];

const CATEGORY_TABS: { id: CategoryType; label: string; icon: string; count: number }[] = [
  { id: 'ALL', label: 'Semua Istilah', icon: 'book', count: ENCYCLOPEDIA_DATA.length },
  { id: 'MENUS', label: 'Menu Aplikasi', icon: 'layout-dashboard', count: ENCYCLOPEDIA_DATA.filter((i) => i.category === 'MENUS').length },
  { id: 'CRYPTO', label: 'Crypto & Web3', icon: 'cpu', count: ENCYCLOPEDIA_DATA.filter((i) => i.category === 'CRYPTO').length },
  { id: 'STOCKS', label: 'Saham BEI', icon: 'trending-up', count: ENCYCLOPEDIA_DATA.filter((i) => i.category === 'STOCKS').length },
  { id: 'GOLD', label: 'Keuangan & Emas', icon: 'coins', count: ENCYCLOPEDIA_DATA.filter((i) => i.category === 'GOLD').length },
  { id: 'TECHNICAL', label: 'Indikator Teknikal', icon: 'sliders', count: ENCYCLOPEDIA_DATA.filter((i) => i.category === 'TECHNICAL').length },
];

export default function EncyclopediaPage() {
  const isUltrawide = useUltrawide();
  const [activeCategory, setActiveCategory] = useState<CategoryType>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const filteredItems = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return ENCYCLOPEDIA_DATA.filter((item) => {
      const matchCategory = activeCategory === 'ALL' || item.category === activeCategory;
      if (!matchCategory) return false;
      if (!q) return true;

      const titleMatch = item.title.toLowerCase().includes(q);
      const subtitleMatch = item.subtitle?.toLowerCase().includes(q) || false;
      const summaryMatch = item.summary.toLowerCase().includes(q);
      const tagMatch = item.tag.toLowerCase().includes(q);
      const detailsMatch = item.details.some((d) => d.toLowerCase().includes(q));
      const formulaMatch = item.formulaOrRule?.toLowerCase().includes(q) || false;

      return titleMatch || subtitleMatch || summaryMatch || tagMatch || detailsMatch || formulaMatch;
    });
  }, [activeCategory, searchQuery]);

  const toggleExpand = (id: string) => {
    setExpandedId((prev) => (prev === id ? null : id));
  };

  const getBadgeStyle = (tone: EncyclopediaItem['badgeTone']) => {
    switch (tone) {
      case 'emerald':
        return 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30';
      case 'amber':
        return 'bg-amber-500/15 text-amber-300 border-amber-500/30';
      case 'rose':
        return 'bg-rose-500/15 text-rose-300 border-rose-500/30';
      case 'purple':
        return 'bg-purple-500/15 text-purple-300 border-purple-500/30';
      case 'cyan':
      default:
        return 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30';
    }
  };

  return (
    <>
      <Head>
        <title>Ensiklopedia Pasar &amp; Glosarium — SOFIA Market Analyst</title>
        <meta
          name="description"
          content="Glosarium finansial komprehensif: panduan menu SOFIA, istilah kripto web3, saham BEI IHSG, pasar emas XAU Antam, dan indikator teknikal."
        />
      </Head>

      <div className="space-y-5">
        {/* TOP HERO BANNER */}
        <div className="bg-gradient-to-r from-[#0b101d] via-[#0f172a] to-[#0b101d] border border-slate-800/90 rounded-2xl p-5 sm:p-6 shadow-xl">
          <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
            <div className="space-y-1.5">
              <div className="flex flex-wrap items-center gap-2">
                <span className="px-2.5 py-0.5 rounded-full text-[10px] font-extrabold uppercase tracking-wider bg-cyan-500/15 text-cyan-300 border border-cyan-500/30 flex items-center gap-1.5">
                  <LucideIcon name="book" className="w-3.5 h-3.5" />
                  ENSIKLOPEDIA FINANSIAL TERPADU
                </span>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
                  {filteredItems.length} ISTILAH TERSEDIA
                </span>
              </div>
              <h1 className="text-xl sm:text-2xl font-black text-white tracking-tight flex items-center gap-2.5">
                <LucideIcon name="book-open" className="w-6 h-6 text-cyan-400" />
                Ensiklopedia &amp; Glosarium Pasar SOFIA
              </h1>
              <p className="text-xs sm:text-sm text-slate-400 max-w-3xl leading-relaxed">
                Panduan komprehensif mengenai seluruh <strong>fitur menu aplikasi</strong>, mekanisme pasar <strong>Crypto &amp; Web3</strong>, perdagangan <strong>Saham BEI &amp; Valuasi</strong>, investasi <strong>Emas Batangan &amp; Logam Mulia</strong>, serta indikator <strong>Analisis Teknikal Kuantitatif</strong>.
              </p>
            </div>

            {/* Quick Actions & Ultrawide Toggle */}
            <div className="flex flex-wrap items-center gap-2.5">
              <button
                type="button"
                onClick={() => toggleUltrawide(!isUltrawide)}
                className={`px-3 py-2 rounded-xl text-xs font-mono font-bold border transition flex items-center gap-1.5 ${
                  isUltrawide
                    ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40 shadow-sm'
                    : 'bg-slate-900 text-slate-400 border-slate-800 hover:text-slate-200'
                }`}
                title="Mode Layar Lebar: Menampilkan kartu ensiklopedia 3 kolom horizontal ke samping"
              >
                <LucideIcon name={isUltrawide ? 'Minimize2' : 'Maximize2'} className="w-3.5 h-3.5" />
                <span>{isUltrawide ? 'Layar Biasa' : 'Mode Layar Lebar'}</span>
              </button>
            </div>
          </div>

          {/* SEARCH BAR & CATEGORY TABS */}
          <div className="mt-5 pt-4 border-t border-slate-800/80 space-y-3">
            <div className="flex flex-col sm:flex-row gap-2.5">
              <div className="relative flex-1">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-500">
                  <LucideIcon name="search" className="w-4 h-4" />
                </div>
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Cari istilah atau menu (contoh: BOS, ARA, Spread Buyback, Slippage, Mint Authority, PER, FVG)..."
                  className="w-full pl-10 pr-4 py-2.5 bg-slate-950/90 border border-slate-800 rounded-xl text-xs font-mono text-slate-100 placeholder-slate-500 focus:outline-none focus:border-cyan-500/60 transition"
                />
                {searchQuery && (
                  <button
                    type="button"
                    onClick={() => setSearchQuery('')}
                    className="absolute inset-y-0 right-0 pr-3 flex items-center text-slate-400 hover:text-white text-xs"
                  >
                    ✕
                  </button>
                )}
              </div>
            </div>

            {/* CATEGORY FILTER PILLS */}
            <div className="flex items-center gap-1.5 overflow-x-auto no-scrollbar pb-1 text-xs font-mono">
              {CATEGORY_TABS.map((tab) => {
                const active = activeCategory === tab.id;
                return (
                  <button
                    key={tab.id}
                    type="button"
                    onClick={() => setActiveCategory(tab.id)}
                    className={`px-3 py-1.5 rounded-xl border transition flex items-center gap-1.5 shrink-0 ${
                      active
                        ? 'bg-cyan-500 text-slate-950 border-cyan-400 font-extrabold shadow-sm'
                        : 'bg-slate-900/80 text-slate-400 border-slate-800/90 hover:text-slate-200 hover:border-slate-700'
                    }`}
                  >
                    <LucideIcon name={tab.icon} className="w-3.5 h-3.5" />
                    <span>{tab.label}</span>
                    <span
                      className={`text-[10px] px-1.5 py-0.2 rounded-full ${
                        active ? 'bg-slate-950/30 text-slate-950' : 'bg-slate-800 text-slate-300'
                      }`}
                    >
                      {tab.count}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* EMPTY SEARCH RESULT */}
        {filteredItems.length === 0 ? (
          <div className="p-10 rounded-2xl bg-obsidian-900 border border-obsidian-800 text-center space-y-3">
            <div className="w-12 h-12 rounded-2xl bg-slate-900 border border-slate-800 flex items-center justify-center mx-auto text-slate-400">
              <LucideIcon name="book" className="w-6 h-6" />
            </div>
            <h3 className="text-sm font-bold text-slate-200">Tidak Ada Istilah yang Cocok</h3>
            <p className="text-xs text-slate-400 max-w-md mx-auto">
              Tidak ditemukan istilah atau menu dengan kata kunci &ldquo;{searchQuery}&rdquo;. Coba gunakan kata kunci lain seperti <em>BOS, Buyback, Lot, Mint, Staking</em>.
            </p>
            <button
              type="button"
              onClick={() => {
                setSearchQuery('');
                setActiveCategory('ALL');
              }}
              className="px-4 py-2 rounded-xl bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 text-xs font-bold"
            >
              Reset Pencarian
            </button>
          </div>
        ) : (
          /* ENCYCLOPEDIA CARDS GRID */
          <div
            className={
              isUltrawide
                ? 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-3 2xl:grid-cols-4 gap-4 items-start'
                : 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 items-start'
            }
          >
            {filteredItems.map((item) => {
              const isExpanded = expandedId === item.id;
              return (
                <div
                  key={item.id}
                  className="rounded-2xl border border-slate-800/90 bg-[#0b101d] hover:border-slate-700/80 transition-all duration-200 flex flex-col justify-between overflow-hidden shadow-lg"
                >
                  {/* Card Header */}
                  <div className="p-4 space-y-2 border-b border-slate-800/60 bg-slate-950/40">
                    <div className="flex items-center justify-between gap-2">
                      <span
                        className={`text-[9px] font-mono font-extrabold px-2 py-0.5 rounded-md border ${getBadgeStyle(
                          item.badgeTone
                        )}`}
                      >
                        {item.tag}
                      </span>
                      {item.routeLink && (
                        <Link
                          href={item.routeLink}
                          className="inline-flex items-center gap-1 text-[10px] font-mono text-cyan-400 hover:text-cyan-300 hover:underline transition"
                        >
                          <span>{item.routeLabel || 'Buka Menu'}</span>
                          <LucideIcon name="external-link" className="w-3 h-3" />
                        </Link>
                      )}
                    </div>
                    <div>
                      <h2 className="text-sm font-extrabold text-white tracking-tight leading-snug">
                        {item.title}
                      </h2>
                      {item.subtitle && (
                        <p className="text-[11px] font-mono text-slate-400 mt-0.5">{item.subtitle}</p>
                      )}
                    </div>
                  </div>

                  {/* Card Body */}
                  <div className="p-4 space-y-3 flex-1 flex flex-col justify-between">
                    <p className="text-xs text-slate-300 leading-relaxed">{item.summary}</p>

                    {/* Bullet Points */}
                    <ul className="space-y-1.5 text-[11px] text-slate-400">
                      {item.details.slice(0, isExpanded ? undefined : 2).map((point, idx) => (
                        <li key={idx} className="flex items-start gap-1.5 leading-normal">
                          <span className="text-cyan-400 mt-1 shrink-0">●</span>
                          <span>{point}</span>
                        </li>
                      ))}
                    </ul>

                    {/* Collapsible Section: Formula / Warning Tips */}
                    {isExpanded && (
                      <div className="space-y-2.5 pt-2 border-t border-slate-800/80">
                        {item.formulaOrRule && (
                          <div className="p-2.5 rounded-xl bg-slate-950/80 border border-slate-800 font-mono text-[10px] space-y-1">
                            <span className="text-slate-400 font-bold block uppercase tracking-wider">
                              📐 Rumus / Kaidah:
                            </span>
                            <code className="text-emerald-300 block break-words">{item.formulaOrRule}</code>
                          </div>
                        )}
                        {item.tipsOrWarning && (
                          <div className="p-2.5 rounded-xl bg-amber-950/20 border border-amber-500/30 text-[11px] text-amber-200 leading-relaxed flex items-start gap-1.5">
                            <span className="shrink-0 text-amber-400">💡</span>
                            <span>{item.tipsOrWarning}</span>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Expand / Collapse Button */}
                    <div className="pt-2 border-t border-slate-800/40 flex items-center justify-between text-xs font-mono">
                      <button
                        type="button"
                        onClick={() => toggleExpand(item.id)}
                        className="text-[11px] text-cyan-400 hover:text-cyan-300 font-bold inline-flex items-center gap-1 transition"
                      >
                        <span>{isExpanded ? 'Sembunyikan Rincian' : `Selengkapnya (${item.details.length} poin)`}</span>
                        <LucideIcon
                          name={isExpanded ? 'chevron-left' : 'chevron-right'}
                          className={`w-3.5 h-3.5 transition-transform ${isExpanded ? '-rotate-90' : 'rotate-90'}`}
                        />
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </>
  );
}
