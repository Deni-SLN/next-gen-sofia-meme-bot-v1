# 📋 Product Requirements Document (PRD)
## **Sofia Market 3.9 — Multi-Asset Quantitative Terminal & Autonomous Sniper Platform**

- **Versi Dokumen**: 3.9.0-PRO (Production Ready)
- **Status Sistem**: 100% Aktif, Teruji & Terverifikasi (Mode PAPER & Mode LIVE On-Chain)
- **Database Cloud**: Neon Serverless PostgreSQL (`neondb`, AWS `ap-southeast-1` Singapore)
- **Platform Target**: Desktop Web (termasuk Ultrawide 21:9), Mobile Responsive Web, & Installable Progressive Web App (PWA)
- **Integrasi Web3**: Direct Chrome Extension Wallet Connect (`Phantom`, `Solflare`, `Backpack`, `MetaMask`, `Rabby`)
- **Mesin AI**: Multi-Engine AI Hub (OpenRouter 200+ Models, 9Router, Google Gemini) dengan Application Tool Calling otonom

---

## 1. Ringkasan Eksekutif (Executive Summary)

**Sofia Market 3.9** adalah ekosistem komprehensif *trading*, riset pasar finansial, dan *autonomous sniper bot* multi-aset. Platform ini menggabungkan eksekusi *on-chain* berlatensi rendah pada jaringan Solana & Base dengan analisa kuantitatif lintas instrumen:
1. **Meme Coin Autonomous Sniper**: Mesin sniper terdesentralisasi dengan 3 mode strategi (*Safe*, *Default*, *Agresif*), filter likuiditas instan, relay Jito 0-slot anti-MEV, dan *autonomous background runner* di server yang berjalan 24/7 bahkan saat pengguna telah logout atau menutup browser.
2. **Integritas Data Matematis Murni (Zero Dummy Policy)**: Seluruh metrik performa, *winrate*, keuntungan/kerugian (PnL), dan rekor transaksi dihitung 100% murni dari *database closed trades* riil. Dilarang keras menggunakan angka karangan, estimasi sintetik, atau pembobotan semu.
3. **Analisa Pasar Multi-Aset**:
   - **Saham Bursa Efek Indonesia (BEI / IDX)**: Analisa EOD, teknikal kuantitatif (SNR, SMC, EMA 200, Ichimoku, Fibonacci), valuasi intrinsik DCF 3 skenario, margin of safety (MoS), dividen yield, dan kalkulator risiko dengan fee broker riil BEI.
   - **Kripto Global 24/7**: Pemindai koin populer (dibatasi 10 koin teratas), analisa on-chain, kalkulator risiko modal, dan simulator *staking yield* APR dalam Rupiah.
   - **Portofolio Emas Fisik**: Kurs spot dunia XAU/USD, harga per gram resmi Antam CertiEye, UBS, dan Galeri 24, kalkulator buyback, serta pencatatan portofolio emas fisik.
   - **Kalkulator Deposito & Obligasi SBN**: Simulasi komparasi imbal hasil Deposito Perbankan vs SBN (ORI, SR, FR, Sukuk Ritel) dengan pemotongan pajak riil (PPh Deposito 20% vs Obligasi 10%).
   - **AI Chat & Research Engine**: Asisten analitis multi-model dengan *tool calling* otomatis dan *fallback synthesizer* untuk riset mendalam.
   - **Ensiklopedia Pasar**: Kamus referensi institusional SMC, Price Action, VSA, Wyckoff, dan regulasi bursa BEI.

---

## 2. Arsitektur Sistem & Spesifikasi Fitur Utama

### 2.1. Autonomous Bot Engine 24/7 (Server-Side Persistence)
- **Background Worker Otonom (`_autonomous_bot_engine_worker`)**:
  - Dijalankan langsung pada *lifespan* server FastAPI (`services/api/app/main.py`).
  - Bot terus memindai token dan mengeksekusi *take-profit / stop-loss / auto-snipe* di latar belakang server secara independen.
  - **Aturan Logout & Sesi**: Sesi browser ditutup, tab di-refresh, maupun pengguna melakukan logout **TIDAK MENGHENTIKAN BOT**.
  - **Satu-satunya Cara Menghentikan Bot**: Hanya melalui klik manual tombol **"⏹ HENTIKAN BOT SEKARANG"** (`POST /api/v1/bot/stop`) oleh operator.

### 2.2. 3 Mode Strategi Bot Trading (`/trading`)
Pengguna dapat memilih salah satu dari 3 mode strategi yang disesuaikan dengan profil risiko:
1. **🛡️ SAFE (Konservatif • Token Lulus & Likuiditas Tinggi)**:
   - Target: Hanya membeli token Solana yang sudah lulus migrasi (*Raydium / PumpSwap Verified Pools*).
   - Parameter: Likuiditas minimum > $20.000, *Safety Score* ≥ 82, Max Dev Holding ≤ 5%, Slippage 0.8%, Target TP +20% / SL -8%, Kecepatan tick 4.0s.
2. **⚖️ DEFAULT (Seimbang • Final Stretch & Migrated)**:
   - Target: Token pada fase *Final Stretch* & pool baru migrasi dengan momentum orderflow 5 menit.
   - Parameter: Likuiditas minimum > $5.000, *Safety Score* ≥ 70, Max Dev Holding ≤ 10%, Slippage 1.2%, Target TP +30% / SL -10%, Kecepatan tick 3.0s.
3. **🔥 AGRESIF (DexScreener Profiles v1 + GMGN.ai Trench Radar)**:
   - Target: Khusus menyergap meme coin **BARU MUNCUL** (umur token < 3 jam, *Market Cap* < $500K) langsung dari feed live DexScreener Token Profiles v1 & GMGN Trench Radar.
   - Proteksi Ketat: **Memblokir 100% koin lama** seperti BONK, PEPE, WIF, POPCAT.
   - Parameter: Likuiditas minimum > $2.000, *Safety Score* ≥ 60, Max Dev Holding ≤ 15%, Slippage 2.0%, Quick Scalp TP +35% / SL -12%, Kecepatan tick 2.0s.

**Kunci Pengaman Mode & Integritas Winrate**:
- **Lock-in saat Aktif**: Selama bot berstatus `running`, mode strategi terkunci otomatis untuk mencegah *order collision*. Bot harus dihentikan manual terlebih dahulu sebelum berganti mode.
- **Transparansi Winrate Riil**: Kartu mode menampilkan persentase *winrate* murni yang dihitung dari tabel `Trade` (*closed sell trades* bertag `[SAFE]`, `[DEFAULT]`, atau `[AGGRESSIVE]`). Apabila belum ada closed trade pada mode tersebut, sistem menampilkan `🎯 Winrate: — (Belum ada trade)`. Tidak diperbolehkan menyuntikkan angka estimasi dummy.

### 2.3. Eksekusi Cepat, Quick Exit & Panic Sell All
- **Quick Exit (Jual Sebagian: 25%, 50%, 100%)**:
  - Tombol aksi cepat pada setiap baris posisi terbuka di terminal.
  - Pencarian posisi menggunakan pencocokan *case-insensitive* (`func.upper(PortfolioHolding.symbol) == symbol.upper()`).
  - Eksekusi jual menggunakan *adaptive slippage retry* (3.5% hingga 8.0%) untuk menjamin transaksi on-chain tidak gagal akibat volatilitas mikro koin meme.
- **🚨 Panic Sell All (100% Likuidasi Sekaligus)**:
  - Tombol darurat global di header posisi aktif (`POST /api/v1/portfolio/sell-all`) untuk melikuidasi seluruh posisi terbuka sekaligus ke saldo kas dalam 1 klik.

### 2.4. Analisa Kripto Global (`/crypto`)
- **Koin Populer (Maksimal 10 Koin)**:
  - Tombol cepat koin populer dibatasi strictly hanya 10 koin teratas (`popularList.slice(0, 10)`).
  - Aset kripto lainnya dapat dicari secara fleksibel melalui kolom pencarian di bar atas.
- **Mode Layar Lebar (Ultrawide Toggle)**:
  - Tombol *toggle* layar lebar ditempatkan secara ergonomis di bagian atas halaman (header bar), menjaga kerapian antarmuka utama.
- **Staking Yield & Risk Calculator**:
  - Simulasi imbal hasil staking APR dalam Rupiah dan kalkulator ukuran posisi (*position sizing*) berdasarkan risiko modal portofolio (1%–5%).

### 2.5. AI Chat & Research Engine (`/chat`)
- **Multi-Provider Hub**: Terhubung ke OpenRouter (200+ model AI), 9Router, dan Google Gemini.
- **Otonom Tool Calling**:
  - `analyze_stock`: Memanggil data kuantitatif saham BEI.
  - `analyze_crypto`: Memanggil data teknikal & on-chain koin kripto.
  - `get_gold_prices`: Memanggil harga emas fisik Antam, UBS, Galeri 24, dan spot XAU/USD.
  - `calculate_deposito_and_bonds`: Menjalankan simulasi komparasi deposito vs obligasi.
  - `analyze_memecoin_rugcheck`: Memindai risiko kontrak pintar koin meme.
  - `get_bot_and_portfolio_status`: Meninjau posisi portofolio dan status bot saat ini.
  - `lookup_market_encyclopedia`: Mencari definisi konsep SMC, VSA, Price Action, dan bursa BEI.
- **Offline / Zero-Key Synthesizer**: Tetap mampu memberikan riset pasar mendalam berbasis data internal sistem meskipun provider AI eksternal kehabisan kuota atau tanpa API key.

### 2.6. Desain Visual & Kenyamanan Pengguna (Dual Theme)
- **Soft Daylight Workspace (Light Mode)**: Menggunakan standar visual *TradingView / Stockbit Pro Daylight* yang teduh di mata dengan latar lembut, teks kontras tajam, dan kartu netral.
- **Obsidian Dark Mode**: Menggunakan palet gelap terkalibrasi untuk pemantauan terminal jangka panjang tanpa kelelahan mata.

### 2.7. Radar Bot Telegram Publik & Sistem Notifikasi Telegram
- **Katalog Bot Telegram Publik Terverifikasi**: Integrasi dengan bot-bot publik terkemuka (Rick Burp `@RickBurpBot`, DexScreener `@DexScreener_Bot`, GMGN Trench Radar `@GMGN_sol_alert_bot`, EtherDrops `@EtherDrops_bot`, Solana Tracker `@SolanaTrackerBot`, dan Saham IDX `@SahamIdxBot`).
- **1-Click Command Generator**: Menghasilkan perintah instan (`/quick <CA>`, `/p <TOKEN>`, `/track <CA>`, `/broker <TICKER>`) yang siap disalin atau langsung membuka aplikasi Telegram dengan parameter koin terisi.
- **Feed Radar Sinyal Komunitas**: Agregasi sinyal momentum, whale accumulation, dan audit keamanan live dari kanal Telegram publik.
- **Sistem Notifikasi Telegram Personal**: Integrasi resmi via Telegram Bot API (`https://api.telegram.org/bot<TOKEN>/sendMessage`) untuk mengirimkan notifikasi instan eksekusi sniper, TP/SL, dan sinyal pasar langsung ke smartphone pengguna.

---

## 3. Matriks Modul & Rute Lengkap

| No | Modul | Rute Web | Endpoint Backend Utama | Deskripsi Fungsional |
|---|---|---|---|---|
| 1 | **Command Center** | `/` | `GET /api/v1/portfolio/overview` | Dashboard eksekutif ringkasan aset multi-instrumen |
| 2 | **Trenches & Pulse** | `/pulse` | `GET /api/v1/memecoins/pulse` | Radar koin baru DexScreener & GMGN.ai |
| 3 | **Auto-Sniper Bot** | `/trading` | `GET/POST /api/v1/bot/*` | Terminal sniper, 3 mode strategi, quick exit, 24/7 worker |
| 4 | **Rug & Bundle Shield** | `/rugcheck` | `GET /api/v1/memecoins/rugcheck` | Audit mint/freeze authority, LP burned, & holder bubble |
| 5 | **Smart Money Copy** | `/copytrade` | `GET /api/v1/memecoins/smart-money` | Pelacak dompet whale & sinyal copy trade Solana |
| 6 | **AI Chat & Research** | `/chat` | `POST /api/v1/chat/completions` | Asisten AI kuantitatif dengan tool calling multi-aset |
| 7 | **Analisa Saham BEI** | `/stocks` | `GET /api/v1/stocks/analyze` | Chart EOD, SMC/SNR, DCF 3 skenario, watchlist & journal |
| 8 | **Analisa Crypto** | `/crypto` | `GET /api/v1/crypto/analyze` | 10 koin populer, analisis teknikal, staking IDR simulator |
| 9 | **Portofolio Emas** | `/gold` | `GET /api/v1/gold` | Harga Antam/UBS/Galeri 24, kalkulator buyback, aset fisik |
| 10 | **Kalkulator Investasi** | `/calculator` | N/A (Client Math + AI Tool) | Komparasi Deposito vs SBN Obligasi dengan pajak riil |
| 11 | **News & Riset** | `/news` | `GET /api/v1/news` | Agregasi berita ekonomi & pasar finansial terkurasi |
| 12 | **Alpha Signals & Telegram Radar** | `/signals` | `GET /api/v1/telegram/*`, `GET /api/v1/signals` | Feed sinyal Telegram publik, 1-click bot launcher & internal signals |
| 13 | **Ensiklopedia Pasar** | `/encyclopedia` | `GET /api/v1/chat/tools` | Kamus SMC, Wyckoff, VSA, Indikator, dan Regulasi BEI |
| 14 | **Portofolio Meme** | `/portfolio` | `GET/POST /api/v1/portfolio/*` | Monitoring kepemilikan koin meme & tombol reset Rp 150K |
| 15 | **Jurnal Trading** | `/journal` | `GET/POST /api/v1/journal/*` | Rekapitulasi transaksi closed, fee breakdown, ekspor Excel |
| 16 | **Kalender PnL** | `/calendar` | `GET /api/v1/performance/daily-calendar` | Kalender keuntungan/kerugian harian bulanan |
| 17 | **AI Degen Agents** | `/agents` | `GET /api/v1/ai/agents` | Pengelolaan sub-agen riset autonomous |
| 18 | **Risk & Slippage** | `/risk` | `GET/PUT /api/v1/risk/config` | Proteksi drawdown, batas slippage, dan alokasi modal |
| 19 | **Multi-Gate Wallets** | `/wallets` | `GET/POST /api/v1/wallets/*` | Manajemen 3 gate wallet, topup gas, settlement 05:00 WIB |
| 20 | **Pengaturan Sistem** | `/settings` | `GET/PUT /api/v1/settings/*`, `POST /api/v1/telegram/test-alert` | Konfigurasi API keys, RPC nodes, notifikasi Telegram, sesi operator |

---

## 4. Standar Kualitas & Kriteria Integritas Data

1. **Prinsip Zero Dummy**: Dilarang menampilkan data simulasi atau persentase karangan pada halaman produksi. Jika data riil belum mencukupi, sistem wajib menampilkan tanda *dash* (`—`) atau status informatif seperti `Belum ada trade`.
2. **Keberlangsungan Bot Otonom**: Server backend adalah pemilik mutlak siklus eksekusi bot. Status bot dipertahankan di database dan tidak boleh terikat pada status login frontend.
3. **Pemisahan Mode Transaksi**: Mode `PAPER` (Sandbox Rp 150.000) dan Mode `LIVE` (On-Chain Mainnet Hot Wallet) harus selalu terisolasi secara tegas pada level portofolio, database, dan transaksi.
