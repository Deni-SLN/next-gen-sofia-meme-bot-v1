import React, { useState, useMemo } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { LucideIcon } from '@/components/LucideIcon';
import { useUltrawide, toggleUltrawide } from '@/lib/useUltrawide';

type CategoryType = 'ALL' | 'MEME_TIPS' | 'MENUS' | 'CRYPTO' | 'STOCKS' | 'GOLD' | 'TECHNICAL';

interface EncyclopediaItem {
  id: string;
  category: 'MEME_TIPS' | 'MENUS' | 'CRYPTO' | 'STOCKS' | 'GOLD' | 'TECHNICAL';
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
  // 0. TIPS & STRATEGI TRADING MEME COIN ON-CHAIN
  // ==========================================
  {
    id: 'meme-marketcap-tiers',
    category: 'MEME_TIPS',
    title: 'Analisis Siklus Market Cap Meme Coin (Micro-Cap vs Graduation vs Mid-Cap)',
    subtitle: 'Menakar Valuasi, Kapasitas Likuiditas & Ekspektasi Kelipatan Cuan',
    tag: 'VALUASI MCAP',
    badgeTone: 'amber',
    routeLink: '/pulse',
    routeLabel: 'Buka Radar Trenches & Pulse',
    summary: 'Panduan wajib membaca valuasi Market Cap (MCap) sebelum entry di DEX Solana (Pump.fun, Raydium, DEXScreener) agar tidak menjadi exit liquidity bagi insider atau whale awal.',
    details: [
      'Tier 1: Micro-Cap / Bonding Curve (< $30K - $60K MCap): Fase paling awal di launchpad (Pump.fun/Moonshot). Potensi gain 10x-50x sangat cepat, namun secara statistik lebih dari 95% koin di tier ini gagal bertahan. Wajib gunakan alokasi mikro ("Lottery Ticket Sizing" misal Rp 15.000 s/d Rp 30.000 per posisi) dan jangan pernah menaruh porsi modal besar.',
      'Tier 2: Graduation Threshold ($60K - $100K MCap): Fase transisi migrasi bonding curve ke Raydium AMM. Sering terjadi dump sesaat karena early buyer take profit dan developer membakar sisa bonding curve. Trader profesional sering menunggu retest support dan konfirmasi likuiditas terkunci sebelum masuk gelombang kedua.',
      'Tier 3: Early Breakout ($100K - $500K MCap): Koin sudah memiliki volume organik stabil, trending di DexScreener, dan likuiditas pool mencapai $20K-$60K. Sangat ideal untuk swing trade 2x-5x dengan risk-reward yang jauh lebih terukur dibanding micro-cap.',
      'Tier 4: Cult / Mid-Cap ($1M - $10M+ MCap): Koin dengan narasi kultus viral di Twitter/X dan TikTok, volume harian jutaan dolar, dan distribusi holder di atas 3.000-5.000 wallet. Risiko rug pull kontraktual sangat rendah, pergerakan lebih stabil layaknya altcoin.',
    ],
    formulaOrRule: 'Aturan Valuasi: Ekspektasi Profit = (Target MCap / Current MCap) - 1. Semakin kecil MCap saat entry, semakin ketat batasan alokasi modal (Maksimal 1-2% portofolio).',
    tipsOrWarning: 'Jangan pernah membeli koin ber-MCap $10K dengan order besar ($1.000+) karena order Anda sendiri akan memicu slippage masif 25%+ dan seketika di-dump oleh holder lama.',
  },
  {
    id: 'meme-liquidity-ratio',
    category: 'MEME_TIPS',
    title: 'Rasio Likuiditas terhadap Market Cap (Liq / MCap Ratio & Anti-Slippage)',
    subtitle: 'Mendeteksi Kolam Tipis, Jebakan Harga Semu & Slippage Ekstrem',
    tag: 'LIKUIDITAS ON-CHAIN',
    badgeTone: 'cyan',
    routeLink: '/auto-entry',
    routeLabel: 'Buka Auto Entry Bot & Scanner',
    summary: 'Likuiditas adalah uang kas riil (SOL/USDC) di smart contract yang siap membayar penjualan token Anda. Market Cap tinggi tanpa likuiditas memadai hanyalah ilusi angka di atas kertas.',
    details: [
      'Rasio Sehat (15% - 30% dari MCap): Menunjukkan kolam likuiditas solid yang mampu menampung aksi jual ribuan dolar tanpa memicu flash crash tajam pada grafik.',
      'Jebakan Kolam Kering (< 10% dari MCap): Jika MCap $500K namun likuiditas pool hanya $8K (rasio < 2%), satu order jual $1.000 saja dapat merontokkan harga hingga 40-60%. Token seperti ini sangat berbahaya untuk dimasuki.',
      'Volume to Liquidity Turnover: Jika Volume 5 menit mencapai 10x-30x lipat dari likuiditas yang tersedia tanpa ada kenaikan harga seimbang, waspadai indikasi bot wash trading otomatis yang sengaja dibuat dev untuk memanipulasi algoritma trending DexScreener.',
    ],
    formulaOrRule: 'Batas Minimum Aman: Likuiditas Pool DEX ≥ $15,000 USD dan Rasio (Likuiditas / Market Cap) ≥ 15%.',
    tipsOrWarning: 'Selalu cek kolom Likuiditas di Sofia Market 4.0 sebelum klik snipe. Jangan tergiur persentase gain +1,000% jika likuiditas kas pool-nya hanya $300.',
  },
  {
    id: 'meme-rugcheck-checklist',
    category: 'MEME_TIPS',
    title: 'Prosedur 30 Detik Audit Kontrak Anti-Rug (RugCheck & Shield)',
    subtitle: 'Verifikasi Mint Authority, Freeze Authority & Ekstensi Token-2022',
    tag: 'KEAMANAN KONTRAK',
    badgeTone: 'emerald',
    routeLink: '/rugcheck',
    routeLabel: 'Buka Rug & Bundle Shield',
    summary: 'Standar operasional 30 detik untuk memastikan smart contract koin tidak memiliki celah tersembunyi yang memungkinkan developer mencuri likuiditas atau membekukan saldo jual Anda.',
    details: [
      'Mint Authority (Wajib Revoked / Dimatikan): Jika mint authority masih aktif (Enabled), developer dapat mencetak triliunan token baru kapan saja secara gratis dan langsung membuangnya (dump) ke pool DEX hingga harga menjadi nol.',
      'Freeze Authority (Wajib Revoked / Dimatikan): Jika freeze authority aktif, developer memiliki hak membekukan wallet pembeli sehingga Anda tidak bisa menjual token saat harga meroket (honeypot selektif).',
      'LP Burn / Lock 100%: Likuiditas di Raydium harus dikirim ke alamat burn (Dead address) atau terkunci di smart contract resmi. Jika LP tidak di-burn, dev bisa mencabut pool (pull liquidity) sewaktu-waktu.',
      'Bahaya Ekstensi Token-2022: Waspadai token Solana dengan ekstensi Token-2022 seperti TransferHook atau PermanentDelegate yang mengenakan potongan pajak jual dinamis 99% (Hidden Tax).',
    ],
    formulaOrRule: 'Kriteria Kontrak Lolos Audit: Mint Revoked = YES • Freeze Revoked = YES • LP Burned/Locked = 100% • Safety Score ≥ 75/100.',
    tipsOrWarning: 'Sofia 4.0 otomatis memblokir token dengan celah honeypot ini melalui modul Rug & Bundle Shield dan Auto Entry Bot.',
  },
  {
    id: 'meme-holder-clustering',
    category: 'MEME_TIPS',
    title: 'Analisis Distribusi Holder & Deteksi Sniper Cluster (BubbleMaps)',
    subtitle: 'Membongkar Manipulasi Suplai Dev yang Dipecah ke Puluhan Wallet',
    tag: 'INSIDER & CLUSTER',
    badgeTone: 'rose',
    routeLink: '/rugcheck',
    routeLabel: 'Deteksi Cluster di RugCheck',
    summary: 'Developer scammer zaman sekarang jarang memegang suplai koin dalam 1 wallet besar. Mereka menggunakan bot sniper untuk memecah 30-60% suplai ke 15-30 wallet baru saat peluncuran awal.',
    details: [
      'Top 10 Holder Threshold (< 20-25%): Di luar AMM liquidity pool, 10 wallet pemegang terbesar tidak boleh menguasai lebih dari 20-25% total suplai token.',
      'Cluster Funding Source (Satu Induk Dana): Buka BubbleMaps atau Solscan untuk melacak dari mana SOL biaya gas wallet-wallet top holder berasal. Jika 15 wallet didanai oleh satu wallet induk yang sama sesaat sebelum rilis, itu adalah cluster sniper insider yang bersiap melakukan dump terkoordinasi.',
      'Dev Holding (< 2-5%): Developer yang transparan idealnya membeli suplai di open market seperti trader lain atau memegang kurang dari 5% suplai untuk alokasi operasional/marketing bertahap.',
    ],
    formulaOrRule: 'Aturan Distribusi: Maksimal Top 10 Holder = 20% (eksklusif Pool DEX) • Cluster Terhubung = 0% • Dev Wallet ≤ 5%.',
    tipsOrWarning: 'Jika melihat koin dengan Top 10 menguasai 50%+ suplai, setiap kenaikan harga akan dijadikan ajang likuidasi keluar (dumping) oleh segelintir insider.',
  },
  {
    id: 'meme-freeroll-money-mgmt',
    category: 'MEME_TIPS',
    title: 'Strategi "Free Roll" & Money Management Koin Meme',
    subtitle: 'Mengamankan Modal Pokok 100% dan Membiarkan Moonbag Berlari Tanpa Beban Mental',
    tag: 'MONEY MANAGEMENT',
    badgeTone: 'purple',
    routeLink: '/auto-entry',
    routeLabel: 'Buka Auto Entry Bot',
    summary: 'Perbedaan mendasar antara trader meme yang konsisten profit vs degen yang selalu boncos terletak pada manajemen modal dan disiplin take profit saat mencapai kelipatan 2x.',
    details: [
      'Prinsip The Free Roll (Modal Keluar Saat 2x): Ketika koin yang Anda beli naik +100% (2x dari harga beli), segera jual 50% porsi token untuk menarik kembali 100% modal awal Anda. Sisa 50% token (disebut "Moonbag") kini adalah uang gratis murni dari pasar yang bisa dibiarkan berlari hingga 5x-10x tanpa beban risiko kehilangan uang pokok.',
      'Ukuran Posisi Kecil Bertahap (Position Sizing 1-3%): Jangan pernah mempertaruhkan lebih dari 1% s/d 3% total portofolio Anda pada satu meme coin tunggal. Mengalokasikan seluruh saldo ke 1 koin baru sama saja dengan bunuh diri finansial.',
      'Disiplin Cut Loss Cepat (-20% s/d -35%): Di pasar koin meme, jika narasi memudar atau dev berhenti memposting, harga tidak akan kembali ke atas. Potong kerugian dengan cepat sebelum drawdown mencapai -90%.',
      'Gunakan Burner Wallet: Selalu pisahkan dompet trading degen dari dompet aset utama Anda untuk mencegah terkurasnya tabungan utama akibat menandatangani smart contract berbahaya.',
    ],
    formulaOrRule: 'Formula Free Roll: Jual 50% Qty saat Harga = 2x Entry Price. Modal Pokok = 100% Selamat di Kas Dompet.',
    tipsOrWarning: 'Keserakahan menunggu 100x tanpa pernah take profit adalah penyebab utama trader memegang tas kosong (bagholders) hingga koin bernilai nol.',
  },
  {
    id: 'meme-narrative-catalysts',
    category: 'MEME_TIPS',
    title: 'Katalis Narasi & Pelacak Smart Money (GMGN / Twitter CT / Inflow)',
    subtitle: 'Menunggangi Gelombang Atensi & Viralitas Sebelum Retail Masuk',
    tag: 'NARASI & MOMENTUM',
    badgeTone: 'cyan',
    routeLink: '/signals',
    routeLabel: 'Buka Alpha Signals & Insights',
    summary: 'Meme coin murni digerakkan oleh atensi sosial, humor internet, dan momentum aliran modal. Belajar mengenali narasi yang memiliki daya tahan vs sekadar koin tiruan (copycat) yang berumur 5 menit.',
    details: [
      'Kekuatan Narasi Orisinal: Koin pemenang selalu memiliki kaitan erat dengan tren internet global terkini, tokoh populer, peristiwa politik riil, atau meme kultus yang memiliki komunitas pembuat konten (meme makers) aktif.',
      'Hindari Koin Copycat: Begitu ada 1 koin viral, akan bermunculan puluhan koin tiruan dengan nama mirip. Koin tiruan hampir 99% berakhir rug pull karena dev hanya ingin memanen sisa atensi.',
      'Inflow Smart Money & GMGN Tracking: Gunakan radar Sofia 4.0 untuk memantau apakah ada wallet dengan rekam jejak profit tinggi (GMGN Smart Degens) yang sedang mengakumulasi koin tersebut secara diam-diam.',
      'Rasio Pembeli vs Penjual (Buy/Sell Ratio > 60%): Periksa rasio transaksi 5 menit. Koin yang sedang dalam fase akumulasi sehat memiliki frekuensi buy order yang konsisten lebih banyak dibanding sell order.',
    ],
    formulaOrRule: 'Hukum Atensi Meme: Harga Bergerak Mengikuti Viralitas Media Sosial (Twitter/X, TikTok, Telegram) + Inflow Smart Money.',
    tipsOrWarning: 'Jangan pernah membeli koin meme yang media sosialnya (Twitter/X & Telegram) mati, akunnya bot, atau kolom komentarnya dimatikan oleh admin.',
  },
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
      'Filter Multi-Kategori: Tab terpisah untuk Semua Berita, Crypto, Saham BEI, Emas Antam, Ekonomi Makro, Geopolitik & Militer, dan Perkembangan Teknologi AI.',
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
  {
    id: 'menu-ai-chat',
    category: 'MENUS',
    title: 'AI Chat & Quant Research Assistant',
    subtitle: 'Model Multimodal, Tool Calling Kuantitatif & Typografi Bersih',
    tag: 'AI ASSISTANT',
    badgeTone: 'cyan',
    routeLink: '/chat',
    routeLabel: 'Buka AI Chat Assistant',
    summary: 'Asisten AI berbasis model multi-engine (OpenRouter, 9Router, Google Gemini) yang dilengkapi tool-calling otonom untuk menganalisis saham BEI, koin kripto, emas, rugcheck, dan berita secara instan.',
    details: [
      'Multi-Provider & Model Selector: Akses ke 200+ model AI termasuk Gemini 2.0 Flash, Llama 3.3 70B, DeepSeek-R1 Reasoning, dan Claude 3.5 Sonnet.',
      'Pemanggilan Tool Otomatis: AI otomatis menjalankan fungsi aplikasi (analyze_stock, analyze_crypto, get_gold_prices, calculate_deposito_and_bonds, search_market_news) tanpa perlu input manual pengguna.',
      'Typografi Bersih Zero-Asterisk: Sistem memproses teks markdown agar simbol bold (**), heading, dan bullet points terformat bersih dan elegan di layar pengguna.',
      'Sinkronisasi Jam Lokal Depok/WIB: AI selalu mengetahui waktu aktual dan status sesi perdagangan bursa BEI secara real-time.',
    ],
    tipsOrWarning: 'Gunakan starter prompt cepat di bagian bawah chat untuk langsung memicu analisis saham atau perbandingan obligasi dalam 1 klik.',
  },
  {
    id: 'menu-economic-calendar',
    category: 'MENUS',
    title: 'Kalender Ekonomi Makro & Dividen BEI',
    subtitle: 'Jadwal Kebijakan Suku Bunga & Hak Pembagian Laba Emiten',
    tag: 'KALENDER PASAR',
    badgeTone: 'emerald',
    routeLink: '/calendar',
    routeLabel: 'Buka Kalender Ekonomi',
    summary: 'Pusat pemantauan jadwal rilis indikator ekonomi makro berdampak tinggi (High Impact News) dan jadwal dividen tunai emiten bursa saham Indonesia.',
    details: [
      'Jadwal Makroekonomi: Menampilkan tanggal rapat Dewan Gubernur BI (BI-Rate), pengumuman inflasi BPS, keputusan FOMC The Fed, serta data tenaga kerja NFP AS.',
      'Jadwal Dividen Tunai: Melacak tanggal Cum Date, Ex Date, Recording Date, dan Payment Date dividen emiten BEI lengkap dengan estimasi yield per lembar.',
    ],
    tipsOrWarning: 'Perhatikan rilis BI-Rate dan FOMC karena sering kali memicu volatilitas tajam pada pergerakan IHSG dan nilai tukar Rupiah.',
  },
  {
    id: 'menu-risk-calculator',
    category: 'MENUS',
    title: 'Kalkulator Manajemen Risiko & Position Sizing',
    subtitle: 'Kelly Criterion, Batas Drawdown & Pengukuran Modal',
    tag: 'RISK ENGINE',
    badgeTone: 'rose',
    routeLink: '/risk',
    routeLabel: 'Buka Manajemen Risiko',
    summary: 'Alat ukur risiko kuantitatif untuk menghitung ukuran lot atau token optimal berdasarkan toleransi kerugian modal (Max Risk 1–2%) dan rasio probabilitas keuntungan.',
    details: [
      'Formula Kelly Criterion: Menghitung fraksi modal ideal untuk menghindari risiko kebangkrutan (risk of ruin).',
      'Max Drawdown Guard: Membatasi akumulasi kerugian harian agar psikologi trading tetap stabil.',
      'Risk/Reward Normalizer: Memastikan setiap trade memiliki rasio potensi imbalan minimal 1.5x di atas risiko setelah memperhitungkan fee broker dan bursa.',
    ],
    tipsOrWarning: 'Jangan pernah menambah posisi (averaging down) pada posisi rugi jika melanggar batas risiko portofolio yang telah ditetapkan.',
  },
  {
    id: 'menu-mcp-server',
    category: 'MENUS',
    title: 'Interoperabilitas Server MCP (Model Context Protocol)',
    subtitle: 'Jembatan Data untuk Agent Hermes, OpenClaw & AI Eksternal',
    tag: 'INTEGRASI AGENT',
    badgeTone: 'purple',
    summary: 'Server protokol terbuka standar industri (JSON-RPC) yang memungkinkan agent otonom eksternal (seperti Hermes Agent dan OpenClaw) mengakses seluruh pipeline data SOFIA secara terprogram.',
    details: [
      'Tools Siap Pakai: Menyediakan endpoint tool get_stock_analysis, get_crypto_analysis, get_gold_prices, calculate_deposito_vs_bonds, dan search_market_news.',
      'Kompatibilitas Standar MCP: Mendukung format JSON Schema standar sehingga dapat di-load langsung oleh ekosistem agentic coding dan LLM multi-tools.',
    ],
    tipsOrWarning: 'Jalankan perintah "python -m app.mcp_server" untuk mengaktifkan konektor transport stdio atau SSE ke agent eksternal Anda.',
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
  {
    id: 'crypto-pumpfun-bonding-curve',
    category: 'CRYPTO',
    title: 'Pump.fun Bonding Curve & Raydium Migration',
    subtitle: 'Mekanisme Peluncuran Token Solana & Risiko Dev Dump',
    tag: 'MEMECOIN ON-CHAIN',
    badgeTone: 'rose',
    summary: 'Mekanisme pencetakan dan perdagangan koin di Solana yang menggunakan formula matematis kurva ikatan harga tanpa order book atau kolam likuiditas awal.',
    details: [
      'Target Kelulusan (Graduation): Ketika bonding curve mengumpulkan total pembelian 85 SOL (ekuivalen Market Cap ~$69.000–$85.000), token dinyatakan lulus (100% curve complete).',
      'Migrasi Raydium / PumpSwap: Seluruh sisa pasokan token dan cadangan SOL yang terkumpul dipindahkan secara otomatis ke DEX untuk membentuk kolam likuiditas permanen (LP Burned).',
      'Fenomena Dev Dump: Momen paling berisiko di mana developer atau insider pembeli awal yang memegang porsi suplai besar sering mendump koinnya begitu pool DEX terbentuk untuk mengambil keuntungan dari pembeli retail.',
    ],
    tipsOrWarning: 'Periksa persentase kepemilikan Dev di menu Rug Shield. Hindari membeli koin pasca migrasi jika dev masih memegang lebih dari 5% total pasokan.',
  },
  {
    id: 'crypto-layer2-rollups',
    category: 'CRYPTO',
    title: 'Layer 2, Rollups & Ekosistem Base',
    subtitle: 'Skalabilitas Ethereum, Optimistic vs ZK & Bridging',
    tag: 'SKALABILITAS L2',
    badgeTone: 'cyan',
    summary: 'Jaringan sekunder (Layer 2) yang memproses transaksi di luar rantai utama Ethereum untuk memangkas biaya gas fee dan meningkatkan kecepatan throughput transaksi.',
    details: [
      'Optimistic Rollups (Base, Arbitrum, Optimism): Memproses bundel transaksi dengan asumsi valid, dilengkapi periode sanggahan (Fraud Proof) 7 hari saat penarikan ke L1.',
      'ZK-Rollups (zkSync, Starknet): Menggunakan pembuktian kriptografi matematika Zero-Knowledge (Validity Proofs) yang tervalidasi seketika tanpa jeda waktu sanggahan.',
      'Base Network: Jaringan L2 yang diinkubasi oleh Coinbase menggunakan OP Stack, menawarkan biaya transaksi kurang dari $0.01 dengan keamanan terikat ke Ethereum L1.',
    ],
    formulaOrRule: 'Throughput L2: Mencapai 2.000–4.000 TPS dengan efisiensi gas fee hingga 99% lebih hemat dibanding Ethereum Mainnet.',
  },
  {
    id: 'crypto-gas-priority-fee',
    category: 'CRYPTO',
    title: 'Gas Fee, Gwei & Solana Compute Units',
    subtitle: 'Biaya Bahan Bakar Transaksi & Jalur Prioritas Validasi',
    tag: 'EKSEKUSI BLOK',
    badgeTone: 'amber',
    summary: 'Mekanisme kompensasi jaringan yang dibayarkan pengguna kepada validator untuk memproses dan mencatat transaksi ke dalam buku besar blockchain.',
    details: [
      'Ethereum EIP-1559: Biaya gas terbagi menjadi Base Fee (dibakar/burn otomatis oleh jaringan) dan Priority Tip (diberikan kepada validator agar transaksi diproses lebih cepat). 1 Gwei = 0.000000001 ETH.',
      'Solana Compute Units (CU): Setiap instruksi smart contract mengonsumsi unit komputasi (default limit 200.000 CU). Trader dapat membayar Micro-Lamports per CU sebagai Priority Fee untuk menembus antrean blok saat jaringan padat.',
    ],
    tipsOrWarning: 'Pada saat peluncuran memecoin hype tinggi, naikkan Priority Fee ke tingkat agresif (misal 0.005–0.01 SOL) agar order Anda tidak drop oleh validator.',
  },
  {
    id: 'crypto-perpetuals-funding-rate',
    category: 'CRYPTO',
    title: 'Perpetual Futures & Funding Rate',
    subtitle: 'Kontrak Derivatif Tanpa Kedaluwarsa & Mekanisme Keseimbangan',
    tag: 'DERIVATIF KRIPTO',
    badgeTone: 'purple',
    summary: 'Kontrak berjangka (futures) aset kripto yang dapat dipegang tanpa batas waktu kedaluwarsa, menggunakan mekanisme Funding Rate periodik untuk menyelaraskan harga kontrak dengan harga pasar spot.',
    details: [
      'Funding Rate Positif: Terjadi saat harga kontrak perpetual lebih tinggi dari harga spot (pasar dominan Bullish/Long). Trader posisi Long wajib membayar biaya fee kepada trader posisi Short setiap interval waktu (umumnya per 8 jam).',
      'Funding Rate Negatif: Terjadi saat harga perpetual lebih rendah dari spot (pasar dominan Bearish/Short). Trader posisi Short wajib membayar kepada posisi Long.',
      'Sinyal Kontrarian Sentimen: Funding Rate yang sangat tinggi (>0.05% per 8 jam) mengindikasikan pasar sudah terlalu overleveraged dan rentan terhadap Long Squeeze (penurunan tajam pemburu likuidasi).',
    ],
    formulaOrRule: 'Funding Payment = Posisi Notional (USD) × Funding Rate (%)',
  },
  {
    id: 'crypto-defi-lending-liquidation',
    category: 'CRYPTO',
    title: 'DeFi Lending, LTV & Health Factor',
    subtitle: 'Protokol Pinjaman Kripto & Perlindungan Likuidasi Otomatis',
    tag: 'DEFI PROTOCOL',
    badgeTone: 'emerald',
    summary: 'Sistem perbankan desentralisasi (Aave, Compound, MakerDAO) yang memungkinkan pengguna meminjam aset kripto dengan menyetorkan jaminan (collateral) secara over-collateralized.',
    details: [
      'LTV (Loan to Value): Persentase maksimal pinjaman yang dapat diambil terhadap nilai aset jaminan (contoh: LTV 75% artinya jaminan $1.000 SOL hanya bisa meminjam maksimal $750 USDC).',
      'Health Factor (HF): Skor kesehatan pinjaman. Jika HF > 1.0 posisi aman; jika HF jatuh ke angka ≤ 1.0, protokol otomatis mengeksekusi likuidasi sebagian jaminan kepada bot likuidator.',
      'Liquidation Penalty: Denda tambahan (umumnya 5%–10%) yang dipotong dari jaminan Anda dan diberikan kepada likuidator saat Health Factor jebol.',
    ],
    tipsOrWarning: 'Pertahankan selalu Health Factor di atas 1.50x untuk mengantisipasi penurunan mendadak harga aset jaminan saat volatilitas pasar tinggi.',
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
  {
    id: 'stocks-bandarmologi-broker-summary',
    category: 'STOCKS',
    title: 'Bandarmologi & Broker Summary (Broksum)',
    subtitle: 'Deteksi Akumulasi, Distribusi & Klasifikasi Broker BEI',
    tag: 'BANDARMOLOGI',
    badgeTone: 'emerald',
    summary: 'Metode analisis aliran dana untuk melacak transaksi pelaku pasar bermodal besar (institusi/bandar) melalui rangkuman perdagangan sekuritas (Broker Summary).',
    details: [
      'Fase Akumulasi: Pembelian bersih (Net Buy) terfokus oleh sekuritas tertentu saat harga saham konsolidasi menyamping (sideways) tanpa menarik perhatian ritel.',
      'Fase Distribusi: Penjualan bersih (Net Sell) besar-besaran oleh broker utama saat harga saham melambung tinggi dan dipenuhi sentimen berita positif di media massa.',
      'Broker Asing (Foreign): Sekuritas institusi global seperti BK (UBS), AK (Mirae Asing), ZP (Maybank), RX (Macquarie). Sering menjadi motor penggerak saham Big Caps LQ45.',
      'Broker BUMN & Swasta: CC (Mandiri Sekuritas), YP (BRI Danareksa), NI (BNI Sekuritas), serta sekuritas ritel lokal seperti PD (Indo Premier), XC (Ajaib), MG (Semesta Indovest).',
      'Average Buy/Sell Price: Membandingkan harga rata-rata beli (B.Avg) top buyer terhadap harga pasar saat ini untuk mengetahui batas aman modal institusi.',
    ],
    tipsOrWarning: 'Hindari menganalisis Broker Summary hanya dari data 1 hari. Gunakan timeframe akumulasi 3–10 hari bursa untuk menyaring manipulasi semu.',
  },
  {
    id: 'stocks-ppk-fca',
    category: 'STOCKS',
    title: 'Papan Pemantauan Khusus (PPK) & Full Call Auction (FCA)',
    subtitle: 'Regulasi Peraturan Bursa I-X, 11 Kriteria & Lelang Periodik',
    tag: 'REGULASI BEI',
    badgeTone: 'rose',
    summary: 'Papan pencatatan khusus di Bursa Efek Indonesia untuk emiten yang memenuhi kriteria fundamental atau likuiditas tertentu, diperdagangkan dengan sistem lelang berkala (Full Call Auction).',
    details: [
      'Mekanisme FCA (Full Call Auction): Perdagangan tidak menggunakan antrean Bid-Offer real-time, melainkan mempertemukan seluruh order beli dan jual secara serentak pada jam-jam lelang tertentu (Indicative Equilibrium Price / IEP dan Indicative Equilibrium Volume / IEV).',
      'Kriteria Utama PPK: Kriteria 2 (Opini Disclaimer), Kriteria 3 (Tidak ada pendapatan usaha), Kriteria 4 (Minerba belum operasi komersial), Kriteria 5 (Ekuitas negatif), Kriteria 8 (PKPU/Pailit), Kriteria 9 (Anak usaha pailit), Kriteria 11 (Kondisi lain ketetapan OJK).',
      'Tujuan Regulasi: Memberikan perlindungan transparansi risiko bagi investor ritel agar lebih berhati-hati terhadap saham dengan catatan kondisi khusus.',
    ],
    tipsOrWarning: 'Saham yang masuk PPK FCA memiliki likuiditas terbatas dan rentan mengalami pergerakan harga tanpa antrean visual reguler. Batasi alokasi modal spekulatif.',
  },
  {
    id: 'stocks-notasi-khusus',
    category: 'STOCKS',
    title: 'Daftar Notasi Khusus BEI ("Tato" Saham)',
    subtitle: 'Arti Huruf Peringatan Emiten (A, B, E, L, X, S, C, Y)',
    tag: 'NOTASI KHUSUS',
    badgeTone: 'amber',
    summary: 'Kode alfabetis yang disematkan BEI di belakang kode saham untuk memberikan peringatan cepat kepada publik mengenai kendala finansial, hukum, atau kepatuhan emiten.',
    details: [
      'Notasi E: Laporan keuangan terakhir menunjukkan Ekuitas Negatif (jumlah utang melebihi total aset bersih).',
      'Notasi L: Emiten Terlambat menyampaikan laporan keuangan melewati batas waktu resmi bursa.',
      'Notasi S: Laporan keuangan terakhir membukukan Tidak Ada Pendapatan Usaha sama sekali.',
      'Notasi B: Terdapat permohonan Pernyataan Pailit atau pembatalan perdamaian di Pengadilan Niaga.',
      'Notasi A: Laporan keuangan mendapatkan Opini Tidak Wajar (Adverse) dari Akuntan Publik independen.',
      'Notasi D: Laporan keuangan mendapatkan Opini Tidak Menyatakan Pendapat (Disclaimer).',
      'Notasi X: Efek tercatat dalam Papan Pemantauan Khusus (PPK).',
      'Notasi C: Sedang menghadapi Perkara Hukum material yang berpotensi mengganggu kelangsungan usaha.',
    ],
    tipsOrWarning: 'Notasi khusus bersifat dinamis. BEI akan mencabut tanda tato tersebut setelah emiten menyelesaikan kewajiban audit dan laporan keuangannya.',
  },
  {
    id: 'stocks-waran-terstruktur',
    category: 'STOCKS',
    title: 'Waran Terstruktur (Structured Warrants) & HMETD (Right)',
    subtitle: 'Instrumen Derivatif Modal Berpengungkit & Hak Beli Saham Baru',
    tag: 'DERIVATIF PASAR MODAL',
    badgeTone: 'purple',
    summary: 'Instrumen efek turunan yang memberikan hak (bukan kewajiban) untuk membeli atau menjual saham induk pada harga dan tanggal yang telah ditentukan.',
    details: [
      'Waran Terstruktur (Call Warrant): Diterbitkan oleh perusahaan sekuritas anggota bursa (contoh kode: BBRIZCW5A), memungkinkan investor menikmati kenaikan harga saham induk dengan modal pembelian jauh lebih kecil (leverage effect).',
      'Rasio Konversi & Exercise Price: Jumlah waran yang dibutuhkan untuk menebus 1 lembar saham induk pada harga pelaksanaan tertentu.',
      'HMETD / Right Issue (Kode berakhiran -R): Hak Memesan Efek Terlebih Dahulu yang diterbitkan emiten saat menambah modal. Jika investor lama tidak menebus atau menjual hak right-nya di pasar, persentase kepemilikan sahamnya akan terdilusi.',
    ],
    formulaOrRule: 'Intrinsic Value Call Warrant = Max(0, Harga Saham Induk - Exercise Price) / Rasio Konversi',
  },
  {
    id: 'stocks-valuasi-dcf-graham',
    category: 'STOCKS',
    title: 'Valuasi Intrinsik DCF & Formula Benjamin Graham',
    subtitle: 'Menghitung Harga Wajar Saham Berbasis Arus Kas & Nilai Buku',
    tag: 'VALUASI INTRINSIK',
    badgeTone: 'emerald',
    summary: 'Dua kerangka kerja fundamental paling dihormati di dunia pasar modal untuk menentukan apakah harga saham di bursa sedang diskon (undervalued) atau kemahalan (overvalued).',
    details: [
      'Discounted Cash Flow (DCF): Memproyeksikan arus kas bebas masa depan (Free Cash Flow to Firm) perusahaan dan mendiskontokannya ke nilai saat ini (Present Value) menggunakan tingkat diskonto WACC (Weighted Average Cost of Capital).',
      'Formula Nilai Intrinsik Graham: Formula klasik Benjamin Graham (guru Warren Buffett) untuk mengukur batas harga wajar konservatif emiten berfundamental sehat: Nilai Wajar = √(22.5 × EPS × BVPS). Angka 22.5 berasal dari standar batas wajar PER 15x dikali PBV 1.5x.',
      'Margin of Safety (MoS): Selisih diskon persentase antara harga pasar saham saat ini terhadap nilai wajar intrinsiknya. Investor nilai umumnya mencari MoS minimal 20%–30%.',
    ],
    formulaOrRule: 'Nilai Intrinsik Graham = √(22.5 × Laba per Saham EPS × Nilai Buku BVPS) | Margin of Safety (%) = ((Nilai Wajar - Harga Saat Ini) / Nilai Wajar) × 100%',
  },
  {
    id: 'stocks-indeks-lq45-idx30',
    category: 'STOCKS',
    title: 'Indeks Acuan BEI: LQ45, IDX30 & IDXHIDIV20',
    subtitle: 'Saham Berkapitalisasi Besar, Likuiditas Tinggi & Pembagi Dividen Jumbo',
    tag: 'INDEKS ACUAN',
    badgeTone: 'cyan',
    summary: 'Indeks tematik resmi Bursa Efek Indonesia yang menyaring saham-saham pilihan berdasarkan likuiditas, kapitalisasi pasar free-float, kepatuhan finansial, dan konsistensi dividen.',
    details: [
      'Indeks LQ45: 45 emiten dengan likuiditas transaksi tertinggi di pasar reguler, kapitalisasi pasar besar, serta prospek pertumbuhan keuangan yang solid.',
      'Indeks IDX30: 30 saham paling likuid dan berkapitalisasi pasar terbesar yang dipilih dari konstituen indeks LQ45 (sering disebut saham inti Blue Chip).',
      'Indeks IDX High Dividend 20 (IDXHIDIV20): 20 saham emiten yang konsisten membagikan dividen tunai selama 3 tahun terakhir dan memiliki Dividend Yield tertinggi.',
      'Evaluasi Mayor & Minor: BEI mengevaluasi konstituen indeks secara berkala setiap 6 bulan (evaluasi mayor pada Januari dan Juli) untuk mendepak saham yang surut likuiditasnya dan memasukkan emiten baru yang memenuhi kriteria.',
    ],
    tipsOrWarning: 'Bagi investor pemula, membatasi pilihan saham pada konstituen LQ45 atau IDX30 memberikan perlindungan likuiditas tinggi sehingga transaksi beli-jual mudah tereksekusi kapan saja.',
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
  {
    id: 'gold-bi-rate-inflasi',
    category: 'GOLD',
    title: 'BI-Rate (Suku Bunga Acuan BI) & Inflasi BPS',
    subtitle: 'Transmisi Kebijakan Moneter ke Deposito, Kredit & IHSG',
    tag: 'MAKROEKONOMI INDONESIA',
    badgeTone: 'cyan',
    summary: 'Suku bunga kebijakan Bank Indonesia yang menjadi jangkar penetapan bunga perbankan, pengendalian laju inflasi Badan Pusat Statistik (BPS), dan stabilitas nilai tukar Rupiah.',
    details: [
      'Dampak Kenaikan BI-Rate (Moneter Ketat): Bunga deposito bank dan kupon SBN baru cenderung naik. Biaya bunga pinjaman korporasi bertambah, yang umumnya menekan pertumbuhan laba emiten saham dan menahan laju inflasi.',
      'Dampak Penurunan BI-Rate (Moneter Longgar): Menstimulasi penyaluran kredit konsumsi dan investasi usaha. Valuasi saham di bursa (IHSG) cenderung terdongkrak naik karena biaya modal lebih murah.',
      'Sasaran Inflasi Nasional: Bank Indonesia menetapkan target inflasi tahunan di rentang 2.5% ± 1% sebagai batas stabilitas daya beli masyarakat.',
    ],
    formulaOrRule: 'Suku Bunga Riil (Real Interest Rate) = Suku Bunga Nominal - Tingkat Laju Inflasi',
  },
  {
    id: 'gold-the-fed-fomc-dxy',
    category: 'GOLD',
    title: 'The Fed, FOMC, Suku Bunga AS & Indeks DXY',
    subtitle: 'Gravitasi Keuangan Global, Yield US Treasury & Arus Modal Keluar',
    tag: 'KEUANGAN GLOBAL',
    badgeTone: 'amber',
    summary: 'Kebijakan suku bunga bank sentral Amerika Serikat (Federal Reserve / The Fed) melalui pertemuan komite FOMC yang mendikte aliran modal investasi di seluruh dunia.',
    details: [
      'FOMC (Federal Open Market Committee): Rapat 8 kali setahun para gubernur The Fed untuk menentukan Fed Funds Rate (FFR) berdasarkan data ketenagakerjaan dan inflasi AS (CPI/PCE).',
      'Indeks Dolar AS (DXY): Indeks yang mengukur kekuatan mata uang Dolar AS terhadap 6 mata uang utama dunia (Euro, Yen, Poundsterling, Dolar Kanada, Krona Swedia, Franc Swiss).',
      'Pengaruh terhadap Emas: Hubungan terbalik kuat — kenaikan suku bunga The Fed mengangkat imbal hasil US Treasury (obligasi AS) dan menguatkan indeks DXY, yang membuat emas spot dunia (XAU/USD) cenderung tertekan karena emas tidak memberikan kupon bunga (zero yield).',
      'Pengaruh terhadap Rupiah: Kenaikan suku bunga The Fed mempersempit selisih suku bunga AS-Indonesia (Yield Spread), memicu penarikan dana asing (capital outflow) dari pasar obligasi dan saham lokal.',
    ],
    tipsOrWarning: 'Setiap rilis data inflasi AS (CPI) dan pidato Ketua The Fed adalah momen volatilitas tertinggi bagi pasar komoditas emas dan bursa kripto global.',
  },
  {
    id: 'gold-emas-digital-bappebti',
    category: 'GOLD',
    title: 'Emas Digital vs Emas Fisik Batangan',
    subtitle: 'Regulasi Pasar Fisik Emas Digital Bappebti & Biaya Cetak',
    tag: 'INVESTASI EMAS',
    badgeTone: 'amber',
    summary: 'Komparasi antara menabung emas secara digital melalui pedagang fisik emas yang diawasi Bappebti versus menyimpan emas batangan fisik di brankas pribadi.',
    details: [
      'Emas Digital Bappebti: Transaksi emas pecahan mikro (mulai dari 0.01 gram atau Rp 10.000) yang tercatat secara digital di bursa berjangka. Wajib memiliki underlying fisik emas 100% di lembaga kliring berizin (ICDX/KBI).',
      'Spread Transaksi Lebih Ramping: Selisih harga jual-beli emas digital umumnya lebih kompetitif (~3%–5%) dibanding spread butik emas fisik (~8%–13%).',
      'Biaya Cetak Fisik: Jika pengguna ingin mengubah saldo gramasi digital menjadi kepingan batangan CertiCard (Antam/Lotus Archi), dikenakan biaya cetak per keping sesuai ukuran gram.',
      'Keunggulan Emas Fisik: Bebas risiko counterparty platform digital, tidak bergantung pada koneksi internet atau sistem aplikasi, dan diakui secara universal sebagai alat transaksi fisik.',
    ],
    tipsOrWarning: 'Pastikan platform emas digital Anda terdaftar resmi di Bappebti (Badan Pengawas Perdagangan Berjangka Komoditi) untuk menjamin keberadaan fisik emas di brankas kliring.',
  },
  {
    id: 'gold-sbn-ritel-komparasi',
    category: 'GOLD',
    title: 'SBN Ritel Indonesia: ORI, SR, SBR, dan ST',
    subtitle: 'Obligasi Tradable vs Non-Tradable & Floating with Floor',
    tag: 'SURAT BERHARGA NEGARA',
    badgeTone: 'emerald',
    summary: 'Instrumen investasi resmi yang diterbitkan oleh Pemerintah Republik Indonesia khusus untuk investor individu WNI melalui Kementerian Keuangan.',
    details: [
      'ORI (Obligasi Negara Ritel - Konvensional): Kupon bersifat tetap (Fixed Rate), dapat diperjualbelikan antar investor di pasar sekunder sebelum jatuh tempo (Tradable), berpeluang mencetak Capital Gain.',
      'SR (Sukuk Ritel - Syariah): Instrumen syariah berakad Ijarah Asset to be Leased dengan kupon tetap bulanan dan bersifat Tradable di pasar sekunder.',
      'SBR (Savings Bond Ritel - Konvensional): Kupon mengambang dengan batas minimal (Floating with Floor) yang naik jika BI-Rate naik namun tidak bisa turun di bawah kupon awal. Bersifat Non-Tradable (tidak bisa dijual di pasar sekunder, hanya ada fasilitas Early Redemption maksimal 50% setelah 1 tahun).',
      'ST (Sukuk Tabungan - Syariah): Versi syariah dari SBR dengan kupon mengambang (Floating with Floor) berakad Wakalah, tidak dapat diperjualbelikan di pasar sekunder.',
      'Efisiensi Pajak: Pajak penghasilan atas kupon SBN hanya 10% (PPh Final sesuai PP 91/2021), jauh lebih hemat dibanding pajak deposito perbankan sebesar 20%.',
    ],
    formulaOrRule: 'Kupon Bersih SBN Bulanan = (Nominal Investasi × Kupon Tahunan × 90% (setelah PPh 10%)) / 12 Bulan',
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
  {
    id: 'tech-rsi-divergence',
    category: 'TECHNICAL',
    title: 'RSI (Relative Strength Index) & Hidden Divergence',
    subtitle: 'Momentum 14 Periode, Reversal & Konfirmasi Kelanjutan Tren',
    tag: 'OSILATOR MOMENTUM',
    badgeTone: 'cyan',
    summary: 'Indikator osilator momentum terpopuler ciptaan J. Welles Wilder yang mengukur kecepatan dan besaran perubahan harga dalam skala 0 hingga 100.',
    details: [
      'Zona Ekstrem: Nilai RSI di atas 70 menunjukkan kondisi Jenuh Beli (Overbought), sedangkan di bawah 30 menunjukkan Jenuh Jual (Oversold).',
      'Regular Bullish Divergence (Pembalikan Tren): Harga membuat lembah lebih rendah (Lower Low), namun grafik RSI membentuk lembah lebih tinggi (Higher Low). Menandakan tekanan jual melemah dan sinyal pembalikan arah naik.',
      'Regular Bearish Divergence: Harga mencetak puncak lebih tinggi (Higher High), namun RSI membentuk puncak lebih rendah (Lower High). Sinyal peringatan potensi koreksi turun.',
      'Hidden Divergence (Kelanjutan Tren): Terjadi saat harga mencetak Higher Low dalam tren naik, namun RSI mencetak Lower Low. Mengindikasikan dorongan koreksi sementara telah tuntas dan tren naik siap melanjutkan reli.',
    ],
    formulaOrRule: 'RSI = 100 - (100 / (1 + RS)) | RS = Rata-rata Kenaikan (14 Periode) / Rata-rata Penurunan (14 Periode)',
  },
  {
    id: 'tech-macd-histogram',
    category: 'TECHNICAL',
    title: 'MACD (Moving Average Convergence Divergence)',
    subtitle: 'Momentum Dua Garis Rata-Rata, Histogram & Zero Crossover',
    tag: 'INDIKATOR MOMENTUM',
    badgeTone: 'purple',
    summary: 'Indikator teknikal serbaguna ciptaan Gerald Appel yang menggabungkan karakteristik pengikut tren (trend-following) dan osilator momentum harga.',
    details: [
      'Garis MACD: Selisih antara Exponential Moving Average (EMA) 12 periode dan EMA 26 periode.',
      'Garis Sinyal (Signal Line): Rata-rata pergerakan eksponensial (EMA) 9 periode dari Garis MACD.',
      'MACD Histogram: Selisih visual antara Garis MACD dan Garis Sinyal. Batang histogram di atas garis nol (positif) menandakan dominasi momentum bullish; di bawah garis nol (negatif) menandakan momentum bearish.',
      'Bullish Crossover: Garis MACD memotong ke atas Garis Sinyal dari bawah (sinyal beli momentum).',
      'Zero Line Cross: Ketika Garis MACD menembus garis 0 ke atas, mengonfirmasi bahwa rata-rata harga jangka pendek telah melampaui rata-rata harga jangka panjang.',
    ],
    formulaOrRule: 'MACD Line = EMA(12) - EMA(26) | Signal Line = EMA(9) dari MACD Line | Histogram = MACD Line - Signal Line',
  },
  {
    id: 'tech-bollinger-squeeze',
    category: 'TECHNICAL',
    title: 'Bollinger Bands & Volatility Squeeze',
    subtitle: 'Pita Deviasi Standar, Siklus Volatilitas & Ledakan Tren',
    tag: 'INDIKATOR VOLATILITAS',
    badgeTone: 'cyan',
    summary: 'Indikator pita volatilitas ciptaan John Bollinger yang memetakan rentang pergerakan harga relatif menggunakan teori distribusi normal statistik.',
    details: [
      '3 Komponen Garis: Garis Tengah (Middle Band berupa SMA 20 periode), Pita Atas (Upper Band = SMA 20 + 2 Standar Deviasi), dan Pita Bawah (Lower Band = SMA 20 - 2 Standar Deviasi).',
      'Karakteristik 95%: Secara statistik, sekitar 95% pergerakan harga berada di dalam batas pita Upper dan Lower Band.',
      'The Squeeze (Penyempitan Pita): Kondisi saat pita Upper dan Lower merapat sangat sempit, mencerminkan volatilitas pasar yang mengering. Pasar selalu bergerak dari periode volatilitas rendah ke volatilitas tinggi — penyempitan pita sering kali mendahului ledakan tren (breakout) besar.',
      'Walking the Bands: Kondisi dalam tren kuat di mana lilin harga terus menempel atau berjalan di sepanjang Pita Atas (Strong Bullish) atau Pita Bawah (Strong Bearish) tanpa langsung berbalik ke tengah.',
    ],
    tipsOrWarning: 'Jangan langsung menjual aset hanya karena harga menyentuh Upper Band. Dalam tren trending kuat, menyentuh Upper Band adalah konfirmasi momentum beli yang kuat, bukan sinyal pembalikan otomatis.',
  },
  {
    id: 'tech-vsa-wyckoff',
    category: 'TECHNICAL',
    title: 'Volume Spread Analysis (VSA) & Metode Wyckoff',
    subtitle: 'Membaca Niat Smart Money dari Rentang Lilin & Volume Transaksi',
    tag: 'VOLUME & PRICE ACTION',
    badgeTone: 'emerald',
    summary: 'Metodologi analisis pergerakan pasar ciptaan Richard Wyckoff dan Tom Williams yang mengungkap hubungan sebab-akibat antara volume transaksi bursa dengan rentang (spread) tubuh candlestick.',
    details: [
      '4 Siklus Pasar Wyckoff: 1) Akumulasi (institusi menyerap pasokan di harga bawah), 2) Markup (fase reli tren naik), 3) Distribusi (institusi melepas barang di harga pucuk), 4) Markdown (fase kejatuhan harga).`',
      'Selling Climax & Spring: Momen di fase akhir akumulasi di mana harga dijatuhkan di bawah level support dengan volume raksasa untuk memicu panik jual ritel (shakeout), sebelum ditutup kembali di atas support.',
      'Upthrust (UTAD): Momen di fase akhir distribusi di mana harga didorong menembus resistance ke atas untuk memancing FOMO ritel, lalu dibanting turun secara agresif.',
      'No Demand Bar: Lilin naik dengan rentang sempit dan volume jauh di bawah rata-rata, menandakan institusi tidak berminat mengangkat harga lebih lanjut (peluang pembalikan turun).',
      'Stopping Volume: Lilin turun bertubuh lebar dengan volume sangat tinggi yang berhasil ditahan pembeli sehingga harga berikutnya gagal membuat new low (sinyal serapan bandar).',
    ],
    tipsOrWarning: 'Volume adalah bahan bakar harga. Pergerakan harga naik tanpa dukungan peningkatan volume adalah tanda reli semu yang rentan ambruk.',
  },
  {
    id: 'tech-atr-volatility',
    category: 'TECHNICAL',
    title: 'ATR (Average True Range) & Chandelier Stop',
    subtitle: 'Pengukuran Volatilitas Sejati & Penempatan Stop Loss Dinamis',
    tag: 'PENGUKUR VOLATILITAS',
    badgeTone: 'amber',
    summary: 'Indikator teknikal ciptaan J. Welles Wilder yang menghitung tingkat volatilitas harga pasar murni tanpa dipengaruhi oleh arah tren naik atau turun.',
    details: [
      'True Range (TR): Nilai terbesar dari: 1) Selisih High hari ini dan Low hari ini, 2) Selisih mutlak High hari ini dan Close kemarin, 3) Selisih mutlak Low hari ini dan Close kemarin (memperhitungkan gap pembukaan bursa).',
      'ATR 14 Periode: Rata-rata pergerakan eksponensial dari nilai True Range selama 14 lilin terakhir.',
      'Stop Loss Dinamis Berbasis ATR: Menghindari penetapan Stop Loss dengan persentase kaku (misal fix -2%). Pada aset dengan volatilitas tinggi, Stop Loss ditempatkan sejauh 1.5x hingga 2.0x nilai ATR di bawah harga beli agar tidak terkena goyangan normal pasar (whipsaw).',
      'Chandelier Exit: Sistem trailing stop yang menghitung batas trailing sejauh kelipatan n × ATR dari titik tertinggi (Highest High) sejak posisi dibuka.',
    ],
    formulaOrRule: 'Batas Stop Loss Dinamis = Harga Entry - (Multiplier ATR × Nilai ATR 14) | Nilai Multiplier Umum = 1.5x s/d 2.0x',
  },
  {
    id: 'tech-kelly-criterion',
    category: 'TECHNICAL',
    title: 'Kelly Criterion & Dynamic Position Sizing',
    subtitle: 'Formula Fraksi Modal Optimal untuk Pertumbuhan Portofolio Maksimal',
    tag: 'KUANTITATIF FINANSIAL',
    badgeTone: 'emerald',
    summary: 'Formula matematis ciptaan John Larry Kelly Jr. (ilmuwan Bell Labs) yang digunakan investor legendaris seperti Ed Thorp dan Jim Simons untuk menentukan persentase modal optimal yang dipertaruhkan dalam setiap perdagangan.',
    details: [
      'Formula Kelly: Menghitung persentase modal ideal berdasarkan rasio kemenangan historis (Win Rate) dan rasio keuntungan terhadap kerugian (Win/Loss Ratio).',
      'Full Kelly vs Half Kelly: Menjalankan Full Kelly sering kali menghasilkan volatilitas drawdown yang terlalu ekstrem bagi psikologi trader. Manajer investasi kuantitatif umumnya menerapkan "Half Kelly" (50% dari hasil formula) untuk meredam ayunan ekuitas tanpa mengurangi laju pertumbuhan majemuk.',
      'Perlindungan Terhadap Over-Betting: Formula secara otomatis melarang transaksi (nilai fraksi f* negatif) jika kombinasi Win Rate dan rasio R/R tidak menghasilkan nilai ekspektasi matematis positif (Negative Expectancy).',
    ],
    formulaOrRule: 'Fraksi Modal Kelly f* = (p × b - q) / b | p = Win Rate (desimal), q = Peluang Loss (1 - p), b = Rasio Win/Loss (R/R)',
    tipsOrWarning: 'Bagi pemula, kombinasikan formula Kelly dengan aturan disiplin plafon: jangan pernah merisikokan lebih dari 1% s/d 2% total ekuitas dalam satu instrumen tunggal.',
  },
];

const CATEGORY_TABS: { id: CategoryType; label: string; icon: string; count: number }[] = [
  { id: 'ALL', label: 'Semua Istilah', icon: 'book', count: ENCYCLOPEDIA_DATA.length },
  { id: 'MEME_TIPS', label: '🔥 Tips Trading Meme Coin', icon: 'zap', count: ENCYCLOPEDIA_DATA.filter((i) => i.category === 'MEME_TIPS').length },
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
        <title>Ensiklopedia Pasar &amp; Glosarium — Sofia Market 4.0 (SFIA 4.0)</title>
        <meta
          name="description"
          content="Glosarium finansial komprehensif: tips trading meme coin Solana on-chain, panduan menu SOFIA 4.0, istilah kripto web3, saham BEI IHSG, pasar emas XAU Antam, dan indikator teknikal."
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
                <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-amber-500/15 text-amber-300 border border-amber-500/30">
                  🔥 TIPS MEME COIN ON-CHAIN
                </span>
              </div>
              <h1 className="text-xl sm:text-2xl font-black text-white tracking-tight flex items-center gap-2.5">
                <LucideIcon name="book-open" className="w-6 h-6 text-cyan-400" />
                Ensiklopedia &amp; Glosarium Pasar SOFIA 4.0
              </h1>
              <p className="text-xs sm:text-sm text-slate-400 max-w-3xl leading-relaxed">
                Panduan komprehensif mengenai strategi <strong>Tips Trading Meme Coin &amp; Valuasi MCap</strong>, fitur menu <strong>Sofia 4.0</strong>, mekanisme pasar <strong>Crypto &amp; Web3</strong>, perdagangan <strong>Saham BEI &amp; Valuasi</strong>, investasi <strong>Emas Batangan &amp; Logam Mulia</strong>, serta indikator <strong>Analisis Teknikal Kuantitatif</strong>.
              </p>
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
