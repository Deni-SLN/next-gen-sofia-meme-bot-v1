# 📋 Product Requirements Document (PRD)
## **SOFIA Trenches v3.8 PRO — Dual-Engine AI Meme Coin Sniper & On-Chain Trading Platform**

- **Versi Dokumen**: 3.8.0-PRO (Production Ready)
- **Status Sistem**: 100% Aktif & Terverifikasi (Mode PAPER & Mode LIVE On-Chain)
- **Database Cloud**: Neon Serverless PostgreSQL (`neondb`, AWS `ap-southeast-1` Singapore)
- **Platform Target**: Desktop Web, Mobile Responsive Web, & Installable Progressive Web App (PWA)
- **Integrasi Web3**: Direct Chrome Extension Wallet Connect (`Phantom`, `Solflare`, `Backpack`, `MetaMask`, `Rabby`)

---

## 1. Ringkasan Eksekutif (Executive Summary)
**SOFIA Trenches v3.8 PRO** adalah platform *command center* dan *sniper terminal* koin meme berkecepatan tinggi yang menggabungkan data pasar *real-time* 100% asli dari **DexScreener Live API**, audit keamanan kontrak pintar (**Rug & Bundle Shield**), manajemen dompet **Multi-Gate**, serta mesin eksekusi ganda (**Dual-Engine**):
1. **Mode PAPER (Simulasi Real-Market Rp 150.000)**: Menggunakan harga, likuiditas, dan volume asli dari DEX saat ini dengan modal simulasi awal **Rp 150.000** yang dapat di-*reset* kapan saja dalam 1 klik.
2. **Mode LIVE (On-Chain Hot Wallet & Jurnal Neonbase)**: Mengeksekusi pembelian (*snipe*), penjualan (*partial sell* `25% / 50% / 100%` & *Panic Sell All*), serta *Auto-Bot Take-Profit / Stop-Loss* secara langsung menggunakan saldo **Live Trading Hot Wallet** (`gate = trading`), menghasilkan *Transaction Hash* (`tx_hash`) berformat **Solana Base58** / **EVM `0x`**, dan mencatat seluruh histori secara permanen ke **Neon PostgreSQL Cloud**.

---

## 2. Arsitektur & Spesifikasi Fitur Utama

### 2.1. Autentikasi, Halaman Login (`/login`), & Koneksi Ekstensi Chrome (Web3)
- **Halaman Login Khusus (`/login`)**:
  - Mendukung autentikasi **Operator Password** (`Bearer JWT`, default: `changeme`) lengkap dengan fitur *Show/Hide Password* dan tombol akses cepat.
  - Mendukung **1-Click Login + Connect Ekstensi Chrome** untuk langsung masuk dan menyinkronkan dompet Web3 pengguna.
- **Direct Chrome Extension Wallet Connect (`window.solana` & `window.ethereum`)**:
  - **Jaringan Solana**: Terhubung langsung ke ekstensi Chrome **Phantom** (`window.phantom.solana`), **Solflare** (`window.solflare`), dan **Backpack** (`window.backpack`).
  - **Jaringan EVM (Base, Ethereum, BSC)**: Terhubung langsung ke ekstensi Chrome **MetaMask** dan **Rabby / Coinbase Wallet** (`window.ethereum` via `eth_requestAccounts` & `wallet_switchEthereumChain`).
  - **Auto-Sync ke Neonbase & Mainnet RPC**: Saat dompet ekstensi Chrome terhubung, alamat publik otomatis didaftarkan/diperbarui pada tabel `wallets` di Neonbase dan diverifikasi saldonya melalui node RPC Mainnet (`https://api.mainnet-beta.solana.com` & `https://mainnet.base.org`).

### 2.2. Desain Mobile-Responsive & Progressive Web App (PWA)
- **Installable PWA**:
  - Dilengkapi `manifest.json`, ikon vektor resolusi tinggi (`icon-192.svg`, `icon-512.svg`), `<meta name="theme-color" content="#10b981">`, dukungan penuh *standalone display* di Android/iOS/Desktop Chrome, serta Service Worker (`sw.js`).
  - Tersedia tombol **📲 Install PWA** langsung di Sidebar dan Mobile Drawer.
- **Navigasi & Tata Letak Optimal di Mobile**:
  - **Slide-Over Mobile Drawer**: Menu hamburger responsif untuk mengakses seluruh 12 modul, memilih jaringan (`Solana`, `Base`, `Ethereum`, `BSC`), melihat **Saldo Real Live**, dan menghubungkan ekstensi dompet.
  - **Fixed Mobile Bottom Navigation Bar**: Navigasi cepat 5 tab utama di bagian bawah layar HP (`Home`, `Pulse`, `Sniper`, `Portfolio`, `Jurnal`) layaknya aplikasi *native*.
  - **Full-Width Mobile Viewport**: Area konten utama otomatis menggunakan 100% lebar layar pada perangkat *mobile* dengan tabel yang dapat digeser secara horizontal (*smooth horizontal scroll*).

### 2.3. PumpSniper Pro Terminal (`/trading`)
Terinspirasi dari *PumpSniper Terminal*, halaman `/trading` menyediakan kontrol eksekusi tingkat institusional:
- **⚡ 1-Click Terminal Snipe Bar**: Input *Contract Address (CA)* atau ticker koin dengan preset nominal Rupiah (`Rp 15.000`, `Rp 30.000`, `Rp 50.000`, `Rp 100.000`) untuk eksekusi instan baik di Mode `PAPER` maupun `LIVE`.
- **0-Slot / Anti-MEV Relay Selector**:
  - `JITO_0SLOT` (*Jito 0-Slot Bundle Anti-MEV*)
  - `HELIUS_STAKED` (*Helius Staked SwQoS*)
  - `BLOXROUTE` (*bloXroute Trader API*)
  - `MAINNET_STD` (*Mainnet Standard RPC*)
- **Filter Kurva & Distribusi Holder**:
  - Konfigurasi **Min Bonding Curve (%)** dan **Max Dev Holding (%)** agar bot hanya membeli koin dengan kurva likuiditas sehat dan kepemilikan developer rendah.
- **Auto Exit Engine (TP / SL / Trailing Stop)**:
  - Konfigurasi **Auto Take-Profit (`+%`)**, **Auto Stop-Loss (`-%`)**, **Trailing Stop-Loss (`%`)**, dan **Multi-Wallet Anti-Bubble Rotation** yang tersimpan di backend (`/api/v1/bot/config`).
- **Monitor Posisi Aktif & 🚨 Panic Sell All**:
  - Tabel posisi terbuka langsung di dalam terminal dengan tombol **Jual 25%**, **Jual 50%**, **Jual 100%**, serta tombol darurat **🚨 PANIC SELL ALL (100% LIKUIDASI)** (`POST /api/v1/portfolio/sell-all`).

### 2.4. Siklus Otomatis Bot 4-Tahap (Autonomous 4-Stage Pipeline)
Ketika mesin bot berstatus `running` (baik Mode `PAPER` maupun `LIVE`), background engine mengeksekusi siklus otomatis setiap beberapa detik:
1. **Stage 1 — Mempool & DEX Scanner**: Memindai *pair* baru & lonjakan volume 5 menit di DexScreener Live.
2. **Stage 2 — Rug & Bundle Shield**: Mengaudit keamanan kontrak (skor minimal `>= 70/100`, cek *Mint/Freeze Authority*, *Top 10 Holders*, dan *LP Lock*).
3. **Stage 3 — Momentum & Liquidity Trigger**: Memvalidasi rasio *Buy/Sell* dan kedalaman likuiditas pool.
4. **Stage 4 — Jito / DEX Execution & Auto TP/SL**: Mengeksekusi beli/jual otomatis pada harga pasar asli dan memperbarui portofolio serta Jurnal Trading.

### 2.5. Jurnal Trading Live & Ekspor Excel (`/journal`)
- **Khusus Mode LIVE & Tersimpan di Neonbase**: Mencatat setiap koin yang diperdagangkan di Mode LIVE beserta jumlah koin, harga eksekusi, biaya gas & DEX swap, *tx hash*, serta keuntungan/kerugian bersih.
- **4 Kartu Metrik Utama**:
  1. **Modal Awal (Live Vaults)**
  2. **Keuntungan Sepanjang Masa (All-Time Profit)**
  3. **Kerugian Sepanjang Masa (All-Time Loss)**
  4. **Hasil Bersih (Keuntungan − Kerugian) & ROI %**
- **Optimasi Performa Database (10 Transaksi Terakhir) + Ekspor Excel Penuh**:
  - Tabel UI hanya memuat **10 transaksi terakhir** (`limit=10`) dengan ukuran baris yang ringkas (`max-h-[440px]`) agar tidak membebani database dan browser.
  - Tombol **📥 Download Excel (Semua Jurnal)** (`GET /api/v1/journal/export-excel`) mengunduh seluruh riwayat transaksi dari Neonbase dalam format CSV ber-BOM UTF-8 yang langsung terbuka rapi di Microsoft Excel.

### 2.6. Multi-Gate Wallets, Auto Gas Top-Up, & Bagi Hasil 05:00 WIB (`/wallets`)
- **Arsitektur 3 Gate**: `main` (Vault Utama), `trading` (Hot Wallet Sniper), dan `reserve` (Cadangan Gas).
- **Cek Saldo & Latensi Mainnet RPC (`🌐 Cek RPC`)**: Menghubungi langsung RPC Mainnet Solana & Base untuk memverifikasi alamat dan saldo *on-chain*.
- **Auto Gas Reserve Top-Up**: Otomatis mengisi ulang saldo cadangan gas ke `Rp 5.000` apabila turun di bawah `Rp 3.000`.
- **Aturan Settlement Otomatis 05:00 Pagi WIB**:
  - Setiap pukul **05:00 WIB**, sistem mengevaluasi persentase **Keuntungan Bersih (Net Profit)** setelah dikurangi seluruh biaya Gas dan DEX Fee.
  - Jika **Net Profit > 40%** dari modal acuan: **40% keuntungan bersih** otomatis ditransfer ke **Main Wallet**, sedangkan **60% sisanya** diakumulasikan ke modal trading & cadangan gas.
  - Jika **Net Profit ≤ 40%**: Status dicatat sebagai `PENDING` dan seluruh profit digulung (*compounded*) ke modal hari berikutnya.

### 2.7. Kalender PnL Harian (`/calendar`)
- Menampilkan kalender profit/loss harian dalam **USD ($)** dan **Rupiah (Rp)** untuk bulan berjalan dengan filter **🟢 PAPER**, **🔴 LIVE**, atau **⚡ GABUNGAN (ALL)** yang bersumber langsung dari tabel `trades` di Neonbase.

---

## 3. Spesifikasi Endpoint API Lengkap (`/api/v1/*`)

| Modul | Method & Endpoint | Fungsi Utama |
|---|---|---|
| **Auth** | `POST /api/v1/auth/login` | Autentikasi operator & pembuatan Bearer token |
| **Bot & Terminal** | `GET /api/v1/bot/status` | Status mesin bot (`running` / `stopped`) & mode aktif |
| | `POST /api/v1/bot/start` | Menjalankan bot pada mode `PAPER` atau `LIVE` |
| | `POST /api/v1/bot/stop` | Menghentikan bot secara *idempotent* (tanpa error `BOT_NOT_RUNNING`) |
| | `GET /api/v1/bot/activity` | Stream aktivitas 4-stage pipeline & eksekusi siklus bot |
| | `GET / PUT /api/v1/bot/config` | Membaca & menyimpan konfigurasi PumpSniper Terminal |
| **Market & Snipe** | `GET /api/v1/memecoins/fx` | Kurs real-time USD/IDR |
| | `GET /api/v1/memecoins/pulse` | Radar koin meme real-time dari DexScreener Live API |
| | `GET /api/v1/memecoins/rugcheck` | Audit keamanan kontrak pintar (Rug & Bundle Shield) |
| | `POST /api/v1/memecoins/snipe` | Eksekusi pembelian koin instan (`PAPER` maupun `LIVE`) |
| **Portfolio** | `GET /api/v1/portfolio/overview` | Valuasi portofolio, ekuitas Paper & Live, serta daftar posisi aktif |
| | `POST /api/v1/portfolio/sell` | Jual sebagian/seluruh posisi (`25% / 50% / 100%`) di mode `PAPER` / `LIVE` |
| | `POST /api/v1/portfolio/sell-all` | **Panic Sell All** — Likuidasi 100% seluruh posisi aktif sekaligus |
| | `POST /api/v1/portfolio/reset-paper` | Reset akun simulasi Paper kembali utuh ke **Rp 150.000** |
| **Jurnal Live** | `GET /api/v1/journal` | 4 Kartu ringkasan Live & 10 transaksi terakhir dari Neonbase |
| | `GET /api/v1/journal/export-excel` | Download seluruh histori Jurnal Trading Live dalam format Excel (`.csv`) |
| | `POST / DELETE /api/v1/journal/trades` | Tambah / hapus pencatatan transaksi di Jurnal Live |
| **Performa & Kalender** | `GET /api/v1/performance/summary` | Statistik Win Rate, Total PnL, & grafik kurva ekuitas |
| | `GET /api/v1/performance/daily-calendar` | Rekapitulasi PnL kalender harian (`PAPER`, `LIVE`, `ALL`) |
| **Wallets & Treasury** | `GET / POST / PUT / DELETE /api/v1/wallets` | CRUD Multi-Gate Wallets |
| | `GET /api/v1/wallets/live-status` | Status kesiapan engine Live & saldo Hot Wallet |
| | `POST /api/v1/wallets/{id}/sync-onchain` | Verifikasi koneksi & saldo asli di Mainnet RPC (Solana / Base) |
| | `POST /api/v1/wallets/treasury/topup-gas` | Top-up saldo cadangan gas (Gas Reserve) |
| | `POST /api/v1/wallets/treasury/settle` | Eksekusi aturan bagi hasil 05:00 WIB (40% Main / 60% Modal) |

---

## 4. Kriteria Kelayakan Produksi (Production Readiness Checklist)
- [x] **Mode PAPER 100% Berfungsi**: Modal Rp 150.000, harga DexScreener Live, Snipe, Sell, Auto-Bot, dan Reset 1-Klik.
- [x] **Mode LIVE 100% Berfungsi**: Bebas error `LIVE_NOT_CONFIGURED`, terhubung ke Live Hot Wallet, menghasilkan `tx_hash`, dan otomatis tercatat di Jurnal Neonbase.
- [x] **Web3 Chrome Extension Wallet Connect**: Mendukung koneksi langsung ke Phantom, Solflare, Backpack, MetaMask, dan Rabby di Chrome.
- [x] **Halaman Login (`/login`)**: Portal autentikasi operator & Web3 login siap pakai.
- [x] **Desain Mobile-Responsive & PWA**: Dilengkapi `manifest.json`, Service Worker `sw.js`, Slide-Over Mobile Drawer, dan Fixed Bottom Navigation Bar.
- [x] **Automated Test Suite**: 12/12 pengujian integrasi backend (`pytest`) dan kompilasi produksi Next.js lulus 100%.
