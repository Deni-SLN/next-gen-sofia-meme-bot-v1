# SOFIA Trade --- Product Requirements Document (PRD)

**Dokumen:** PRD SOFIA Trade --- Solana Meme Coin Intelligence & Trading
Platform\
**Versi:** 1.1\
**Tanggal:** 13 Oktober 2026\
**Status:** Approved untuk implementasi (delta v1.0 -> v1.1: FR-TB-009)\
**Produk:** Aplikasi web mandiri\
**Pasar awal:** Meme coin pada blockchain Solana\
**Mode rilis awal:** Analysis-only dan paper trading; transaksi wallet on-chain dinonaktifkan sampai feature gate wallet dibuka secara terpisah\
**Prinsip biaya AI:** OpenRouter menggunakan model gratis secara
default; model berbayar hanya melalui pemilihan manual dan persetujuan
eksplisit.

------------------------------------------------------------------------

## 1. Ringkasan Eksekutif

SOFIA Trade adalah platform analisis dan trading meme coin Solana yang
terdiri dari dua mesin utama dalam satu aplikasi:

1.  **Analysis Engine** --- menemukan token, mengumpulkan data pasar dan
    on-chain, menilai risiko, menjalankan analisis teknikal,
    mengorkestrasi AI agent, dan menghasilkan sinyal yang dapat diaudit.
2.  **Trading Bot Engine** --- memvalidasi sinyal, menerapkan batas
    risiko, mengelola siklus order dan posisi, menjalankan paper
    trading, serta menyediakan jalur eksekusi live yang dinonaktifkan
    secara default sampai kriteria kesiapan dipenuhi.

Keduanya berbagi kontrak data dan aturan risiko, tetapi tanggung
jawabnya dipisahkan. AI tidak boleh melewati hard-reject, mengubah
accounting, menaikkan batas risiko, atau mengaktifkan live trading
secara mandiri.

Produk dibuat sebagai aplikasi mandiri dengan satu dashboard. Mesin
analisis dan bot dapat dikembangkan serta diuji terpisah tanpa membuat
dua aplikasi yang tidak terkoordinasi.

### 1.1 Tujuan produk

-   Membantu pengguna menemukan kandidat meme coin Solana secara
    sistematis.
-   Menggabungkan market data, indikator teknikal, data on-chain yang
    tersedia, dan AI-assisted analysis.
-   Menghasilkan sinyal beserta alasan, confidence/coverage, timestamp,
    risiko, invalidasi, dan masa berlaku.
-   Menguji strategi menggunakan paper trading dan evaluasi historis
    sebelum menggunakan modal nyata.
-   Menyediakan bot trading dengan kontrol risiko dan pencatatan yang
    konsisten ketika fase live disetujui.
-   Mendukung 9Router melalui API OpenAI-compatible dan OpenRouter
    melalui API-nya, dengan konfigurasi tanpa perubahan kode.
-   Menekan biaya model: OpenRouter default menggunakan
    `openrouter/free`; model berbayar hanya dapat dipakai setelah
    dipilih manual.

### 1.2 Bukan tujuan V1

-   Menjamin profit atau mengklaim token pasti aman.
-   Menjalankan live trading pada rilis awal.
-   Menyimpan seed phrase atau private key dalam plaintext.
-   Mengandalkan satu model LLM sebagai sumber kebenaran.
-   Menjadikan GMGN atau provider berbayar tertentu sebagai dependensi
    wajib.
-   Melakukan copy trading otomatis atau pengelolaan dana pihak ketiga.

------------------------------------------------------------------------

## 2. Keputusan Produk yang Dikunci

  -----------------------------------------------------------------------
  Area                                Keputusan
  ----------------------------------- -----------------------------------
  Nama kerja                          SOFIA Trade

  Produk                              Aplikasi mandiri, bukan modul yang
                                      bergantung pada aplikasi SOFIA lain

  Pasar awal                          Meme coin Solana

  Mesin utama                         Analysis Engine dan Trading Bot
                                      Engine

  Kontrol keselamatan                 Risk Engine menjadi gerbang
                                      terakhir sebelum keputusan eksekusi

  Mode awal                           Analysis-only dan PAPER

  LIVE                                Nonaktif secara default; aktivasi
                                      memerlukan persetujuan eksplisit
                                      dan kriteria kesiapan

  Frontend                            React + TypeScript + Vite

  UI                                  Tailwind CSS dan shadcn/ui

  Chart                               TradingView Lightweight Charts

  Backend                             Python FastAPI

  Database                            PostgreSQL; Supabase dapat dipakai
                                      sebagai opsi managed

  Worker                              Python worker dan scheduler

  Market discovery                    DEX Screener adapter

  On-chain                            Solana RPC adapter

  AI provider                         9Router (OpenAI-compatible) dan
                                      OpenRouter

  OpenRouter default                  `openrouter/free`

  Model berbayar                      Hanya jika dipilih manual; backend
                                      menolak penggunaan berbayar tanpa
                                      persetujuan

  Notifikasi                          Telegram Bot API, opsional

  Deployment                          Docker Compose untuk lingkungan
                                      awal

  Profit sweep                        50% dari profit terealisasi yang eligible; hanya SOL dan USDC

  Withdrawal                         Otomatis dan manual; hanya ke main wallet yang terdaftar/allowlisted

  Reserve wallet                      Dinamis berdasarkan kewajiban posisi, order pending, dan kebutuhan fee

  Eksekusi awal                       Tidak ada transaksi blockchain;
                                      PAPER memakai simulasi. Wallet transfer LIVE tetap feature-gated
  -----------------------------------------------------------------------

Perubahan terhadap keputusan di atas harus dicatat sebagai perubahan PRD
dan memerlukan persetujuan pemilik produk.

------------------------------------------------------------------------

## 3. Pengguna dan Peran

### 3.1 Primary user --- Operator/Owner

Dapat mengatur provider, model, strategi, risk limits, watchlist, dan
mode operasional. Hanya operator yang berwenang mengaktifkan live
trading setelah kontrol keselamatan terpenuhi.

### 3.2 Read-only observer (opsional setelah V1)

Dapat melihat dashboard, sinyal, dan performa, tetapi tidak mengubah
konfigurasi strategi, provider, atau mode trading.

### 3.3 Prinsip akses

-   V1 dapat dimulai sebagai aplikasi single-user dengan autentikasi
    sederhana.
-   Jangan mengekspos API administratif ke internet tanpa autentikasi.
-   Perubahan konfigurasi sensitif harus dicatat pada audit log.
-   Jika multi-user ditambahkan, setiap objek pengguna harus memiliki
    authorization checks dan isolasi data.

------------------------------------------------------------------------

## 4. Struktur Menu dan Navigasi

Sidebar menampilkan menu utama dan submenu yang dapat diperluas. Dua
mesin utama harus mudah ditemukan.

### 4.1 Overview Dashboard

-   Market Overview
-   Active Signals
-   Engine Status
-   Trading Summary
-   Risk Monitor
-   Provider Health
-   Recent Events

Dashboard wajib memisahkan metrik PAPER dan LIVE. Jika LIVE belum
diaktifkan, UI harus menyatakan status tersebut dengan jelas.

### 4.2 Analysis Engine

-   Market Scanner
-   Token Explorer
-   Technical Analysis
-   On-Chain Intelligence
-   AI Market Research
-   Signal Center
-   Watchlist
-   Analysis History

### 4.3 Trading Bot Engine

-   Bot Control Center
-   Strategy Manager
-   Entry & Exit Rules
-   Position Manager
-   Order & Execution
-   Risk Management
-   Execution Logs
-   Wallet Management (bot wallet dan main wallet)
-   Profit Sweep (50%, SOL/USDC)
-   Withdraw & Transfer (manual dan otomatis)
-   Transfer History & Reconciliation

### 4.4 Portfolio & Accounting

-   Portfolio Overview
-   Balance & Equity
-   Open Positions
-   Realized/Unrealized PnL
-   Transaction History
-   Fees & Slippage
-   External Cash Movements
-   Accounting Audit
-   Wallet Balances (SOL dan USDC)
-   Transfer Ledger (internal transfer dan network fee)
-   Sweepable Profit / Dynamic Reserve

### 4.5 Performance & Research

-   Strategy Backtesting
-   Paper Trading Performance
-   Live Trading Performance (hanya jika tersedia)
-   Signal Performance
-   Equity Curve
-   Expectancy / Profit Factor / Drawdown
-   MAE/MFE Analysis
-   Strategy Comparison
-   Out-of-Sample Testing

### 4.6 AI & Agent Center

-   Agent Overview
-   Agent Management
-   Provider Management
-   Model Registry
-   Routing & Fallback
-   Token & Cost Analytics
-   Decision Trace
-   Prompt/Strategy Versioning
-   Provider Diagnostics

### 4.7 Alerts & Journal

-   Active Alerts
-   Telegram Integration
-   Signal Journal
-   Trade Journal
-   System Event Log
-   Error & Incident History
-   Alert Rules & Cooldown

### 4.8 Settings & System Health

-   General Settings
-   Market Data Providers
-   Solana RPC Settings
-   Wallet & Execution Configuration
-   Risk Parameters
-   Scoring Configuration
-   Database & Backup
-   API & Access Control
-   Worker Health
-   Logs & Diagnostics

------------------------------------------------------------------------

## 5. Arsitektur Sistem

### 5.1 Komponen

**Frontend** - React, TypeScript, Vite. - TanStack Query untuk cache dan
server state. - React Hook Form dan Zod untuk form validation bila
diperlukan. - TradingView Lightweight Charts untuk candlestick. - UI
status harus membedakan loading, empty, stale, unavailable, dan error.

**Backend API** - Python FastAPI. - Pydantic untuk validasi schema. -
SQLAlchemy/SQLModel (pilih satu dan konsisten) untuk akses database. -
Alembic untuk migrasi. - OpenAPI sebagai kontrak API dan sumber generasi
tipe frontend.

**Analysis Engine** - Pipeline discovery dan normalisasi data. -
Deterministic technical indicators. - On-chain checks. - Risk
assessment. - Scoring dan signal generation. - AI orchestration untuk
interpretasi/riset, bukan otoritas eksekusi.

**Trading Bot Engine** - Signal intake dan validation. - Risk gate. -
Position sizing. - Execution adapter interface. - Paper execution
adapter untuk V1. - Live adapter disiapkan terpisah dan tetap disabled
sampai approval. - Position lifecycle, reconciliation, journal, dan
accounting.

**Worker** - Refresh market data. - Menjalankan analisis terjadwal. -
Memproses alert. - Mengevaluasi sinyal pada horizon yang ditentukan. -
Menjalankan job backtest. - Retry dengan batas, exponential backoff, dan
jitter.

**Database** - PostgreSQL. - Snapshot analisis harus dapat
direproduksi. - Data signal, order, fill, dan accounting harus dapat
diaudit.

### 5.2 Diagram arsitektur

``` mermaid
flowchart TD
    UI[React + TypeScript Dashboard] <--> API[FastAPI]
    API <--> DB[(PostgreSQL)]
    WORKER[Python Worker / Scheduler] <--> DB
    WORKER --> MARKET[Market Data Adapters]
    MARKET --> DEX[DEX Screener]
    MARKET --> RPC[Solana RPC]
    WORKER --> ANALYSIS[Analysis Engine]
    ANALYSIS --> RISK[Risk Engine]
    ANALYSIS --> AI[AI Provider Abstraction]
    AI --> R9[9Router OpenAI-Compatible]
    AI --> OR[OpenRouter]
    RISK --> SIGNAL[Signal Store]
    SIGNAL --> BOT[Trading Bot Engine]
    BOT --> PAPER[Paper Execution Adapter]
    BOT -. disabled until approved .-> LIVE[Live Execution Adapter]
    BOT --> ACCOUNTING[Journal & Accounting]
    ACCOUNTING --> DB
    WORKER --> ALERTS[Telegram / Alerts]
```

### 5.3 Batas layanan

-   Frontend tidak memanggil provider AI atau exchange langsung.
-   API key hanya ada pada backend.
-   Analysis Engine tidak mengirim transaksi.
-   Trading Bot Engine tidak mengubah output analisis secara retroaktif.
-   Risk Engine harus berjalan sebelum order intent disetujui.
-   Paper dan Live menggunakan adapter berbeda serta data accounting
    terpisah.
-   Kegagalan satu provider tidak boleh menjatuhkan keseluruhan
    aplikasi.
-   Jangan menambah Redis/message broker sampai kebutuhan antrean
    membenarkannya.

------------------------------------------------------------------------

## 6. Struktur Repository

``` text
sofia-trade/
├── apps/
│   └── web/
│       ├── src/
│       │   ├── app/
│       │   ├── components/
│       │   │   ├── charts/
│       │   │   ├── scanner/
│       │   │   ├── signals/
│       │   │   ├── risk/
│       │   │   └── bot-control/
│       │   ├── features/
│       │   │   ├── dashboard/
│       │   │   ├── analysis/
│       │   │   ├── trading-bot/
│       │   │   ├── portfolio/
│       │   │   ├── performance/
│       │   │   └── ai-agents/
│       │   ├── hooks/
│       │   ├── services/api/
│       │   ├── schemas/
│       │   └── types/
│       ├── tests/
│       └── package.json
├── services/
│   ├── api/
│   │   ├── app/
│   │   │   ├── api/v1/
│   │   │   ├── core/
│   │   │   ├── db/
│   │   │   ├── models/
│   │   │   ├── schemas/
│   │   │   ├── repositories/
│   │   │   ├── services/
│   │   │   ├── providers/
│   │   │   ├── analysis/
│   │   │   ├── risk/
│   │   │   ├── signals/
│   │   │   ├── execution/
│   │   │   └── accounting/
│   │   └── tests/
│   └── worker/
│       ├── jobs/
│       ├── schedulers/
│       └── tests/
├── packages/
│   ├── api-contracts/
│   └── scoring-config/
├── migrations/
├── infra/
│   ├── docker/
│   └── deployment/
├── docs/
│   ├── PRD.md
│   ├── ARCHITECTURE.md
│   ├── API.md
│   ├── DATA_DICTIONARY.md
│   ├── SECURITY.md
│   └── RUNBOOK.md
├── docker-compose.yml
├── .env.example
├── Makefile
└── README.md
```

Gunakan pnpm untuk frontend, uv untuk Python, Pytest untuk backend,
Vitest untuk unit test frontend, Playwright untuk end-to-end test, dan
pre-commit/linting yang konsisten. Hindari duplikasi tipe API; generate
tipe TypeScript dari OpenAPI.

------------------------------------------------------------------------

## 7. Functional Requirements --- Analysis Engine

### FR-AE-001: Market Discovery

Sistem harus menemukan kandidat token Solana melalui provider adapter.

Persyaratan: - Hanya chain Solana yang masuk ke pipeline V1. - Simpan
mint address dan pair address secara terpisah. - Deduplikasi berdasarkan
identitas token/pair, bukan simbol. - Filter umur pool, likuiditas,
volume, transaksi, dan perubahan harga harus dapat dikonfigurasi. -
Setiap record memiliki `observed_at`, sumber data, dan status
freshness. - Provider failure tidak boleh menghasilkan nilai pasar
palsu. - Token dengan data penting tidak lengkap ditandai `INCOMPLETE`.

### FR-AE-002: Token Explorer

Menampilkan: - Token name, symbol, mint, pair, DEX. - Price USD,
liquidity, volume, market cap/FDV bila tersedia. - Umur pool dan
transaksi beli/jual. - Candlestick serta volume untuk timeframe yang
didukung data. - Risk flags, analysis summary, dan signal history. -
Link ke explorer dan sumber pasar eksternal.

Timeframe M1, M5, M15, M30, H1, H4, dan D1 hanya ditampilkan jika data
dasar mencukupi. Jangan membuat candle melalui interpolasi yang
menyesatkan.

### FR-AE-003: Technical Analysis

Komponen awal: - EMA 9/21/50. - RSI 14. - MACD. - ATR 14. - Volume ratio
terhadap baseline. - Swing high/low dan support/resistance zones. -
Market structure: breakout, breakdown, retest, range. - Perubahan
likuiditas dan estimasi price impact bila sumber mendukung.

Seluruh perhitungan deterministik dan memiliki unit tests. Nilai null,
NaN, Infinity, candle incomplete, dan data out-of-order harus ditangani
eksplisit.

### FR-AE-004: On-Chain Intelligence

Pemeriksaan yang dapat diterapkan sesuai data tersedia: - Mint
authority. - Freeze authority. - Metadata dan status token. - Holder
concentration jika holder data tersedia. - Pool/liquidity signals. -
Wallet behavior/labels hanya jika sumber resmi dan akses tersedia. -
Data age, provider, coverage, dan limitations.

Tidak ada klaim "rug-pull-proof" atau "100% aman". `UNKNOWN` tidak sama
dengan `PASS`.

### FR-AE-005: Risk Assessment

Risk result minimal memiliki: - `hard_reject: boolean` -
`risk_flags: string[]` - `coverage: number` -
`status: PASS | WARN | REJECT | UNKNOWN` - `assessed_at` -
`rule_version` - `evidence_refs`

Hard-reject mengalahkan score agregat. Aturan dapat menolak kandidat
jika data harga/likuiditas tidak valid, likuiditas di bawah threshold,
authority tidak memenuhi kebijakan, atau kondisi risiko wajib tidak
dapat diverifikasi. Threshold harus configurable dan berversi.

### FR-AE-006: Scoring

Skor 0--100 adalah ringkasan relatif, bukan probabilitas profit. Bobot
awal yang dapat dikonfigurasi: - Liquidity/market quality: 25%. -
Trend/momentum: 25%. - Volume/activity: 15%. - Price structure: 15%. -
On-chain risk: 20%.

Ketentuan: - Total bobot harus 100%. - Data yang hilang tidak boleh
diberi skor sempurna. - Coverage/confidence dipisahkan dari score. -
Hard-reject tidak dapat diatasi oleh skor tinggi. - Perubahan bobot
menghasilkan versi konfigurasi baru. - Analisis historis tetap terkait
dengan versi yang digunakan saat itu.

### FR-AE-007: Signal Generation

Status: - `LONG_CANDIDATE` - `BEARISH_BIAS` - `WAIT` - `REJECT` -
`EXPIRED` - `INVALIDATED`

Setiap signal memuat: - Signal ID dan token/pair. - Analysis run ID. -
Engine version dan strategy version. - Decision dan reasons. - Entry
reference (jika relevan). - Stop reference dan target references (jika
dihitung). - Risk/reward estimate beserta asumsi fee/slippage. -
Invalidating conditions. - Created time, expiry, data timestamp. -
Coverage, risk flags, dan source references.

Signal bukan order. Signal tidak boleh langsung mengirim transaksi.

### FR-AE-008: Analysis History

-   Menyimpan input snapshot, versi engine, konfigurasi, provider dan
    timestamps.
-   Memungkinkan audit alasan keputusan.
-   Tidak mengubah hasil lama secara diam-diam.
-   Mendukung filter berdasarkan token, tanggal, keputusan, dan engine
    version.

------------------------------------------------------------------------

## 8. Functional Requirements --- Trading Bot Engine

### FR-TB-001: Mode Control

Mode: - `ANALYSIS_ONLY` - `PAPER` - `LIVE` (disabled by default; gated)

UI menampilkan mode aktif secara mencolok. Perubahan mode memerlukan
tindakan eksplisit. Tidak boleh ada perpindahan PAPER ke LIVE akibat
restart, deployment, atau fallback konfigurasi.

### FR-TB-002: Bot Control Center

Kontrol: - Start - Stop - Pause - Resume - Emergency Kill Switch

Semua tindakan dicatat beserta actor, timestamp, mode, alasan, dan
hasil. Stop harus menghentikan pembukaan posisi baru dan menangani
posisi yang ada sesuai kebijakan yang dikonfigurasi. Emergency stop
harus memblokir order intent baru dan tidak bergantung pada respons LLM.

### FR-TB-003: Signal Intake

Sebelum sinyal diterima: - Signature/schema valid. - Signal belum
expired atau invalidated. - Token/pair cocok. - Snapshot data tidak
stale melewati batas konfigurasi. - Signal ID belum diproses. - Risk
flags memenuhi policy. - Strategi dan mode mengizinkan tindakan.

Idempotency key wajib mencegah pemrosesan sinyal yang sama berulang
kali.

### FR-TB-004: Risk Gate

Sebelum order intent: - Maksimum alokasi per posisi. - Maksimum eksposur
total. - Daily loss limit. - Maximum drawdown threshold. - Maksimum
jumlah posisi bersamaan. - Cooldown setelah loss atau error beruntun. -
Slippage ceiling. - Minimum liquidity. - Batas fee dan price impact. -
Kill switch. - Provider/market-data health. - Validitas wallet/balance
jika mode live kelak diaktifkan.

Semua nilai harus finite dan tervalidasi. NaN, Infinity, missing
mandatory metric, atau data stale wajib menghasilkan fail-closed. Tidak
ada AI override untuk hard-reject.

### FR-TB-005: Paper Execution

Paper engine: - Menggunakan data pasar nyata, tetapi saldo dan transaksi
virtual. - Mensimulasikan fee, slippage, latency, partial fill, dan
order rejection sesuai model simulasi. - Tidak menandatangani atau
mengirim transaksi blockchain. - Menyimpan order intent, simulated fill,
fee, posisi, dan accounting event. - Menandai dengan jelas bahwa fill
adalah simulasi, bukan fill nyata.

### FR-TB-006: Live Execution (future gated capability)

Live adapter boleh dibuat sebagai interface, tetapi harus disabled pada
rilis awal. Aktivasi memerlukan: - Persetujuan eksplisit operator. -
Secret/wallet handling yang aman. - Risk limits dan kill switch
teruji. - Reconciliation test lulus. - Idempotency dan duplicate-order
prevention. - Simulasi kegagalan dan recovery. - Verifikasi order/fill
terhadap sumber otoritatif. - Tidak ada blocker keamanan kritis. -
Runbook recovery disetujui.

Live execution tidak menjadi acceptance requirement untuk rilis awal.

### FR-TB-007: Position Management

-   Melacak posisi dan statusnya.
-   Menyimpan entry basis, size, fees, realized/unrealized PnL.
-   Mendukung exit condition yang berversi.
-   Menghindari double-close.
-   Menyediakan posisi stale/unknown state untuk rekonsiliasi.
-   Tidak menganggap stop-loss terjamin pada token dengan likuiditas
    rendah.

### FR-TB-008: Execution Logs

Mencatat: - Signal ID. - Risk decision dan alasan. - Order intent. -
Request/response yang telah disanitasi. - Order status. - Fill(s). - Fee
dan slippage. - Error, retry, reconciliation. - Engine/strategy version.

Secret, private key, dan seed phrase tidak boleh masuk log.

------------------------------------------------------------------------


### FR-TB-009: Wallet Management, Profit Sweep & Withdrawal

**Tujuan:** menyediakan pemindahan dana dari bot wallet ke main/treasury wallet melalui mode otomatis dan manual. Pada rilis V1, fitur dirancang dan dapat diuji di PAPER/sandbox; transaksi on-chain LIVE tetap nonaktif sampai feature gate wallet dibuka melalui persetujuan operator dan security review tersendiri.

**Konfigurasi produk yang dikunci**
- Mode: `AUTO_AND_MANUAL` (otomatis dan manual tersedia bersamaan).
- Default profit sweep: `50%` dari profit terealisasi yang eligible.
- Aset yang boleh disweep/withdraw: `SOL` dan `USDC` saja. Token lain tidak otomatis dikonversi atau dipindahkan oleh fitur ini.
- Reserve: dinamis, dihitung dari eksposur posisi terbuka, order/outflow yang masih pending, dan kebutuhan biaya transaksi.
- Tujuan otomatis: hanya main wallet yang sudah diverifikasi dan di-allowlist. Perubahan alamat tujuan memerlukan konfirmasi eksplisit baru.
- Profit sweep menggunakan profit terealisasi dari posisi yang sudah ditutup; unrealized PnL tidak boleh menjadi dasar sweep.
- Transfer tidak boleh mengurangi dana yang diperlukan untuk mengelola posisi terbuka, memenuhi pending orders, atau membayar biaya jaringan.

**Rumus eligibility**
- `eligible_realized_profit(asset)` adalah profit terealisasi positif yang dapat diatribusikan ke aset SOL atau USDC, setelah fee trading yang relevan dan setelah memperhitungkan sweep sebelumnya agar profit yang sama tidak dapat disweep dua kali.
- `dynamic_reserve(asset)` dihitung dari kebutuhan likuiditas untuk posisi terbuka/eksposur yang masih harus didanai, order dan transfer yang pending, estimasi network fee/priority fee, serta reserve operasional yang diwajibkan jaringan. Untuk SOL, reserve juga harus memperhitungkan biaya yang mungkin diperlukan untuk account creation/rent jika relevan.
- `available_balance(asset)` berasal dari saldo on-chain yang telah dibaca dan divalidasi, bukan hanya dari angka accounting internal.
- `sweepable_amount(asset) = max(0, min(50% × eligible_realized_profit(asset), available_balance(asset) − dynamic_reserve(asset) − pending_outflows(asset) − estimated_transfer_fee(asset)))`.
- Jika salah satu input wajib stale, tidak tersedia, tidak konsisten, atau tidak dapat dihitung dengan aman, jumlah sweep menjadi `0` dan transaksi ditolak/ditunda dengan alasan yang tercatat.
- Untuk SOL, biaya transaksi dipotong dalam SOL. Untuk USDC, biaya jaringan tetap dibayar dari SOL; validasi harus memastikan SOL fee reserve tetap tersedia. Jangan mengasumsikan fee jaringan dibayar dalam USDC.
- Sweep tidak boleh melakukan swap otomatis dari token lain ke SOL/USDC. Konversi, bila ditambahkan di masa depan, harus menjadi workflow terpisah dengan slippage limit dan risk gate tersendiri.

**Mode otomatis**
1. Dipicu setelah close/fill final yang menghasilkan realized PnL, atau melalui scheduler yang memeriksa ledger; tidak boleh dipicu hanya karena unrealized PnL naik.
2. Hitung ulang realized profit eligible, saldo on-chain, dynamic reserve, pending outflows, fee, batas per transaksi, dan batas harian.
3. Buat `withdrawal_intent` unik sebelum penandatanganan transaksi.
4. Transfer hanya ke main wallet allowlisted. Kebijakan awal tidak mengizinkan alamat dinamis dari sinyal, token metadata, LLM, atau input provider eksternal.
5. Jika amount di bawah minimum threshold yang dikonfigurasi atau tidak lolos validasi, catat `SKIPPED` beserta alasan; jangan membuat transaksi on-chain.
6. Kegagalan atau timeout tidak boleh memicu blind retry. Periksa signature/status on-chain terlebih dahulu.
7. Perubahan persentase, reserve policy, threshold, batas transaksi, atau alamat tujuan dicatat dalam audit log. Default 50% tidak dapat diubah oleh AI agent.

**Mode manual**
1. Operator memilih aset SOL/USDC dan nominal atau memilih jumlah maksimum yang aman.
2. UI menampilkan source wallet, destination address lengkap, aset, jumlah, estimasi fee, reserve setelah transfer, saldo tersisa, dan status validasi.
3. Operator mengonfirmasi detail final sebelum transaksi ditandatangani. Alamat tujuan tidak boleh berubah antara validasi dan penandatanganan.
4. Jika saldo, fee estimate, blockhash, reserve, atau status posisi berubah material sebelum signing, intent harus divalidasi ulang dan dapat meminta konfirmasi ulang.
5. Tombol submit yang diklik berulang harus mengembalikan intent yang sama, bukan membuat transfer duplikat.

**State machine transaksi**
- `DRAFT`: intent dibuat, belum tervalidasi.
- `VALIDATING`: validasi identitas wallet, allowlist tujuan, aset, nominal, saldo, reserve, fee, batas, dan status posisi.
- `REJECTED`: validasi gagal; terminal untuk intent tersebut.
- `AWAITING_CONFIRMATION`: menunggu konfirmasi operator untuk withdrawal manual atau perubahan konfigurasi sensitif.
- `READY_TO_SIGN`: seluruh pemeriksaan lolos dan intent belum kedaluwarsa.
- `SIGNING`: signer terisolasi menandatangani transaksi.
- `SUBMITTED`: transaksi dikirim dan signature disimpan.
- `CONFIRMING`: status signature dipantau melalui RPC yang dikonfigurasi.
- `CONFIRMED`: transaksi final/confirmed sesuai tingkat commitment yang ditetapkan; saldo dan ledger direkonsiliasi.
- `FAILED`: kegagalan definitif telah dipastikan dan dicatat.
- `RECONCILIATION_REQUIRED`: hasil belum pasti, RPC tidak konsisten, atau timeout tanpa status final yang dapat dipastikan. Tidak boleh membuat transfer pengganti sebelum rekonsiliasi selesai.
- `CANCELLED`: intent dibatalkan sebelum signing/submission.
- `SKIPPED`: sweep otomatis tidak dijalankan karena threshold atau eligibility tidak terpenuhi.

Transisi status hanya boleh dilakukan oleh service yang berwenang, dicatat sebagai event append-only, dan dilindungi optimistic locking/versi record. `CONFIRMED`, `FAILED`, `REJECTED`, `CANCELLED`, dan `SKIPPED` adalah terminal kecuali koreksi audit dibuat sebagai event baru; status terminal tidak diubah diam-diam.

**Validasi saldo dan risiko**
- Baca saldo on-chain SOL dan USDC dari wallet yang benar; validasi mint USDC menggunakan mint address resmi yang dikonfigurasi, bukan hanya simbol token.
- Gunakan integer base units/decimal fixed precision untuk amount dan fee; jangan gunakan binary float untuk uang.
- Validasi source wallet, destination allowlist, chain, mint, token decimals, nominal positif, dust/minimum transfer, saldo spendable, fee buffer, daily cap, per-transfer cap, cooldown, serta status signer/RPC.
- Validasi ulang saldo dan reserve tepat sebelum signing. Nilai saldo dari cache tidak cukup untuk mengizinkan transfer.
- Perhitungkan posisi terbuka, exposure, order pending, transfer pending, biaya trading yang belum diselesaikan, SOL untuk fee, dan kebutuhan akun token jika relevan.
- Jika posisi atau order berubah saat intent menunggu konfirmasi, jalankan ulang risk/reserve check. Jika tidak lolos, intent kembali ke validasi atau ditolak; jangan signing.
- Circuit breaker, emergency stop, atau status accounting `RECONCILIATION_REQUIRED` memblokir automatic sweep. Manual withdrawal juga diblokir jika ada ketidakpastian saldo/ledger; emergency stop tidak boleh menghilangkan kemampuan read-only untuk melihat status transaksi.
- Provider/RPC disagreement atau saldo tidak diketahui menghasilkan fail-closed.

**Idempotency dan recovery**
- Setiap intent memiliki `idempotency_key` unik; unique constraint berlaku di database.
- Idempotency scope minimal mencakup wallet, asset, amount, destination, dan logical trigger/event. Request berulang dengan key dan payload sama mengembalikan intent yang sama. Key sama dengan payload berbeda menghasilkan `409 IDEMPOTENCY_CONFLICT`.
- Auto sweep memakai key deterministik dari close-event/ledger-event, asset, dan versi kebijakan agar event yang sama tidak membuat sweep kedua.
- Simpan transaction signature sebelum menandai submission berhasil. Jika RPC timeout setelah submit, cari signature/status transaksi terlebih dahulu.
- Jangan pernah mengirim ulang transaksi secara buta hanya karena HTTP timeout. Jika status belum diketahui, gunakan `RECONCILIATION_REQUIRED` dan worker rekonsiliasi.
- Unique constraints mencegah event accounting untuk signature yang sama dicatat dua kali. Retry RPC/status query boleh dilakukan dengan backoff; retry transfer hanya boleh dilakukan setelah dipastikan transaksi sebelumnya tidak terkirim/valid dan intent baru dibuat secara eksplisit.

**Wallet security**
- Main wallet berfungsi sebagai treasury/destination; bot wallet adalah hot wallet operasional dengan saldo terbatas. Jangan mengaktifkan signing otomatis dari main wallet.
- Private key/seed phrase tidak pernah dikirim ke LLM, browser, log, analytics, atau database biasa. AI agent tidak memiliki tool untuk signing, mengubah destination, atau memanggil withdrawal.
- Utamakan signer terisolasi/hardware signer/KMS yang sesuai untuk Solana. Jika hot-wallet key diperlukan, gunakan secret manager/encrypted storage, pembatasan akses minimum, rotasi/recovery procedure, dan audit akses. Enkripsi saja tidak menggantikan isolasi signer.
- Alamat tujuan harus diverifikasi, ditampilkan penuh saat konfirmasi manual, dan di-allowlist. Perubahan alamat memerlukan autentikasi ulang/konfirmasi eksplisit serta audit event.
- Terapkan authentication, authorization, CSRF protection bila berbasis cookie, rate limit, per-transfer cap, daily cap, cooldown, dan emergency disable switch.
- UI wajib membedakan `SIMULATED/PAPER` dari `ON_CHAIN`; jangan pernah memberi label “berhasil” sebelum status on-chain yang ditetapkan tercapai.
- V1 tidak mengaktifkan transaksi on-chain LIVE. Feature gate withdrawal terpisah dari feature gate live trading; membuka salah satunya tidak otomatis membuka yang lain.

**Accounting dan ledger**
- Transfer bot wallet → main wallet adalah transfer internal jika kedua wallet dimiliki dan dilacak dalam satu portfolio. Transfer mengurangi saldo bot wallet dan menambah saldo main wallet dengan nominal aset yang sama; transfer pokok tidak mengubah combined portfolio equity dan bukan realized trading PnL.
- Network/priority fee dicatat sebagai biaya jaringan terpisah dengan aset, amount, signature, dan timestamp. Fee mengurangi combined equity; jangan mengklasifikasikannya sebagai loss trading pada posisi kecuali kebijakan accounting secara eksplisit mengalokasikannya ke transaksi trading.
- Jika ledger hanya melacak bot wallet, catat transfer sebagai wallet outflow/treasury transfer dan jangan menghitungnya sebagai trading loss. Laporan portfolio harus menyatakan scope wallet yang dilacak.
- Profit sweep hanya mengubah lokasi dana; realized PnL tetap berasal dari trade close events. Jangan mencatat transfer sebagai realized PnL baru atau mengurangi realized PnL karena perpindahan antar-wallet.
- Setiap intent, signature, transfer, fee, balance snapshot, dan accounting event harus saling dapat ditelusuri. Event accounting bersifat append-only secara logis; koreksi dibuat dengan reversal/correction event.
- Gunakan konvensi canonical equity yang sudah ditetapkan pada §11.2. Internal transfers dikecualikan dari external cash movements pada combined portfolio ledger. External deposits/withdrawals ke/dari wallet yang tidak dimiliki tetap dicatat sebagai external cash movement sesuai konvensi tanda yang dipilih.

**Audit dan observability**
- Catat operator/trigger, policy version, asset, amount, destination identifier yang aman, reserve breakdown, balance snapshot time, fee estimate/actual, validation results, idempotency key, signature, RPC provider, state transitions, timestamps, dan failure reason.
- Jangan log private key, seed phrase, authorization token, atau data rahasia signer.
- Dashboard menampilkan realized profit eligible, target sweep 50%, dynamic reserve per aset, amount sweepable, pending transfer, confirmed transfer, fee, dan reconciliation alerts.

## 9. AI & Agent Center

### 9.1 Provider wajib

Dua provider harus didukung sebagai provider kelas utama: 1. **9Router**
melalui API OpenAI-compatible. 2. **OpenRouter** melalui endpoint API
OpenRouter.

Konfigurasi provider harus dapat dilakukan tanpa perubahan kode. Semua
API call dilakukan dari backend.

### 9.2 Konfigurasi 9Router

Field: - Enabled/disabled. - Base URL configurable; default cloud URL
dapat disetel ke `https://9router.com/v1`, atau URL lokal sesuai
instalasi. - API key. - Model ID sesuai model yang disediakan 9Router. -
Timeout. - Retry policy. - Streaming capability. - Connection test.

Jangan mengasumsikan semua model di 9Router mendukung tool calling, JSON
schema, streaming, atau context window yang sama. Kemampuan model harus
diuji/ditandai.

### 9.3 Konfigurasi OpenRouter

Field: - Enabled/disabled. - API key. - Default routing mode. - Model
ID. - Fallback policy. - Timeout. - Usage/cost tracking. - Connection
test.

Base URL default: `https://openrouter.ai/api/v1`.

### 9.4 OpenRouter Free-First --- aturan wajib

Default mode adalah **Automatic Free** dengan model `openrouter/free`.

Ketentuan: - Saat setup baru, model OpenRouter disetel ke
`openrouter/free`. - Pengguna boleh memilih model gratis spesifik yang
memiliki varian `:free`. - Model berbayar hanya boleh dipilih secara
manual oleh pengguna. - Saat memilih model berbayar, UI harus
menampilkan status paid dan meminta konfirmasi eksplisit. - Persetujuan
tersimpan untuk provider/model yang dipilih, bukan izin global yang
diam-diam berlaku ke semua model berbayar. - Fallback otomatis
OpenRouter hanya boleh mengarah ke model gratis yang disetujui. - Jika
seluruh model gratis gagal, sistem menampilkan error atau memakai
provider lain hanya jika fallback lintas-provider diaktifkan. - Fallback
lintas-provider tidak boleh memilih model berbayar secara diam-diam. -
Jika harga/model status tidak dapat diverifikasi, perlakukan sebagai
tidak diizinkan untuk automatic routing. - Backend harus memvalidasi
model sebelum mengirim request. UI saja tidak cukup. - Catat model yang
benar-benar merespons, karena `openrouter/free` dapat memilih model
berbeda dari satu request ke request lain. - Availability dan rate limit
free models dapat berubah; UI harus menjelaskan kegagalan atau
keterbatasan ini.

### 9.5 Provider abstraction

Buat interface internal seragam, misalnya:

``` python
class LLMProvider:
    async def list_models(self): ...
    async def validate_model(self, model_id: str): ...
    async def chat(self, request): ...
    async def health_check(self): ...
```

Adapter: - `NineRouterProvider` - `OpenRouterProvider`

Model/agent tidak boleh memanggil provider secara langsung. Provider
adapter menormalisasi: - Request/response. - Error categories. - Token
usage. - Latency. - Model sebenarnya yang digunakan. - Capability
metadata. - Cost metadata bila tersedia.

### 9.6 Model Registry dan per-agent selection

Setiap agent memiliki: - Provider. - Model ID. - Mode
automatic/manual. - Required capabilities. - Timeout. - Max retries. -
Fallback list. - Context budget. - Max output tokens. - Cost policy. -
Enabled flag.

Agent tidak boleh meminta capability yang tidak didukung model terpilih
tanpa fallback/penanganan eksplisit.

### 9.7 Agent awal

-   Technical Analysis Agent: menjelaskan hasil indikator deterministik.
-   On-Chain Risk Agent: merangkum evidence dan data yang belum
    diketahui.
-   Market Research Agent: memberi konteks pasar.
-   Signal Validation Agent: memeriksa kelengkapan alasan dan
    konsistensi output, tidak dapat override risk gate.
-   Optional Strategy Research Agent: membantu menyusun hipotesis
    backtest; tidak boleh mengubah strategi live secara otomatis.

Perhitungan indikator, hard-reject, risk sizing, dan accounting tetap
kode deterministik. LLM adalah lapisan interpretasi, bukan sumber
kebenaran angka.

### 9.8 Structured output dan prompt safety

-   Output AI divalidasi dengan schema.
-   Output malformed tidak boleh diteruskan sebagai signal atau order.
-   Input eksternal dianggap data tidak tepercaya, termasuk token
    metadata, URL, dan konten yang berpotensi prompt injection.
-   Prompt injection tidak boleh mengubah policy sistem.
-   AI tidak menerima private key atau secret.
-   Log harus menyimpan metadata keputusan yang diperlukan tanpa
    menyimpan rahasia.
-   Jangan mengandalkan chain-of-thought privat; simpan ringkasan
    alasan, evidence, dan decision trace yang dapat diaudit.

### 9.9 Token usage dan biaya

Catat: - Provider dan model. - Prompt/completion/total tokens jika
disediakan. - Latency. - Request status. - Retry count. - Cost aktual
jika tersedia. - Cost status: `KNOWN`, `ESTIMATED`, atau `UNKNOWN`.

Jika tarif tidak tersedia, tampilkan biaya sebagai unknown, bukan nol.
Konversi ke Rupiah menggunakan kurs yang dapat dikonfigurasi dan diberi
timestamp; tampilkan sebagai estimasi bila kurs tidak real-time.

------------------------------------------------------------------------

## 10. Market Data Providers

### 10.1 DEX Screener

Digunakan sebagai sumber awal untuk token discovery dan market pair
data. Buat adapter yang menangani: - Endpoint discovery/search/token
pairs sesuai dokumentasi provider. - Rate limit per endpoint. - Cache
dan request deduplication. - Retry/backoff untuk 429 dan 5xx. -
Normalisasi data. - Data freshness. - Missing fields.

Jangan hard-code asumsi bahwa semua endpoint memiliki rate limit sama.
Simpan rate limit dalam konfigurasi provider.

### 10.2 Solana RPC

Digunakan untuk pembacaan state on-chain dan pemeriksaan akun yang
dibutuhkan. Dukungan HTTP dan WebSocket dibuat melalui adapter. Public
RPC hanya untuk prototipe dan volume rendah; sistem harus dapat
mengganti endpoint tanpa perubahan kode.

### 10.3 Provider tambahan

GMGN atau provider wallet intelligence lain bersifat opsional.
Implementasi hanya boleh dilakukan jika akses resmi, izin penggunaan,
dan kuota dapat diverifikasi. Jangan menjadikan scraping yang rapuh
sebagai dependensi inti.

### 10.4 Market data integrity

-   Semua angka penting memiliki sumber dan timestamp.
-   Data lama harus ditandai stale.
-   Data yang gagal diambil tidak boleh diam-diam diganti dengan nol.
-   Perubahan provider schema harus terdeteksi.
-   Candle dan snapshot historis yang dipakai dalam signal harus
    disimpan atau direferensikan dengan cara yang dapat direproduksi.

------------------------------------------------------------------------

## 11. Desain Database

PostgreSQL menjadi sumber data utama. Semua timestamp disimpan dalam
UTC. Harga/rasio yang membutuhkan presisi menggunakan `NUMERIC` atau
integer unit yang sesuai, bukan float biner untuk accounting.

### 11.1 Tabel inti

**`tokens`** - `id` UUID primary key - `chain` - `mint_address` unique
per chain - `symbol`, `name`, `decimals` - `first_seen_at` -
`metadata_json` - `created_at`, `updated_at`

**`token_pairs`** - `id` - `token_id` - `pair_address` unique -
`dex_id` - `quote_token_address` - `pair_created_at` - `source` -
`created_at`

**`market_snapshots`** - `id` - `pair_id` - `price_usd` -
`liquidity_usd` - `volume_5m`, `volume_1h`, `volume_24h` - `buys_5m`,
`sells_5m`, `buys_1h`, `sells_1h` - `price_change_5m`,
`price_change_1h`, `price_change_24h` - `fdv`, `market_cap` -
`observed_at` - `source`, `raw_payload_hash`

**`candles`** - `pair_id` - `timeframe` - `open_time` - `open`, `high`,
`low`, `close`, `volume` - `source` - `is_final` - Unique
`(pair_id, timeframe, open_time)`

**`risk_assessments`** - `id` - `token_id` - `status` - `hard_reject` -
`risk_flags` JSONB - `coverage` - `rule_version` - `evidence_refs`
JSONB - `assessed_at`

**`analysis_runs`** - `id` - `token_id` - `pair_id` - `engine_version` -
`scoring_config_version` - `input_snapshot` JSONB atau referensi
snapshot immutable - `score` - `coverage` - `decision` - `reasons`
JSONB - `provider_versions` JSONB - `created_at`

**`signals`** - `id` - `analysis_run_id` - `token_id` - `pair_id` -
`signal_type` - `status` - `entry_reference` - `stop_reference` -
`target_references` JSONB - `fee_assumptions` JSONB -
`slippage_assumption` - `expires_at` - `invalidated_at` - `created_at`

**`signal_evaluations`** - `id` - `signal_id` - `horizon` -
`return_pct` - `net_return_pct` - `mae` - `mfe` - `evaluation_status` -
`evaluated_at`

**`strategies`** - `id` - `name` - `version` - `config` JSONB -
`status` - `created_at`

**`bot_runs`** - `id` - `mode` (`PAPER`/`LIVE`) - `strategy_id` -
`status` - `started_at` - `stopped_at` - `started_by` - `stop_reason`

**`order_intents`** - `id` - `bot_run_id` - `signal_id` -
`idempotency_key` unique - `side` - `requested_size` -
`reference_price` - `risk_decision` - `risk_reasons` JSONB - `status` -
`created_at`

**`orders`** - `id` - `order_intent_id` - `mode` - `provider_order_id`
nullable - `order_type` - `side` - `quantity` - `price` - `status` -
`submitted_at` - `updated_at`

**`fills`** - `id` - `order_id` - `fill_quantity` - `fill_price` -
`fee_amount` - `fee_asset` - `slippage` - `fill_type`
(`SIMULATED`/`ACTUAL`) - `filled_at`

**`positions`** - `id` - `bot_run_id` - `mode` - `token_id` - `status` -
`quantity` - `average_entry_price` - `realized_pnl` - `unrealized_pnl` -
`opened_at` - `closed_at`

**`accounting_events`** - `id` - `mode` - `event_type` -
`reference_type` - `reference_id` - `amount` - `asset` - `metadata`
JSONB - `created_at`

**`wallet_accounts`** - `id` - `wallet_role` (`BOT`/`MAIN`) - `chain` - `public_address` - `is_allowlisted` - `status` - `created_at` - `updated_at`. Public address only; never store private key/seed phrase in this table.

**`wallet_balance_snapshots`** - `id` - `wallet_account_id` - `asset` (`SOL`/`USDC`) - `mint_address` - `balance_atomic` - `spendable_atomic` - `observed_at` - `rpc_provider` - `commitment` - `status` - `raw_payload_hash`.

**`withdrawal_intents`** - `id` - `idempotency_key` unique - `trigger_type` (`MANUAL`/`AUTO_SWEEP`) - `source_wallet_id` - `destination_wallet_id` - `destination_address_snapshot` - `asset` - `mint_address` - `amount_atomic` - `estimated_fee_atomic` - `actual_fee_atomic` nullable - `reserve_snapshot` JSONB - `policy_version` - `state` - `payload_hash` - `created_by` - `expires_at` - `created_at` - `updated_at`.

**`wallet_transfers`** - `id` - `withdrawal_intent_id` unique - `chain` - `transaction_signature` unique nullable - `submission_attempt` - `rpc_provider` - `commitment_target` - `submitted_at` - `confirmed_at` nullable - `failure_code` nullable - `reconciliation_status` - `created_at`.

**`profit_sweep_events`** - `id` - `close_event_id` - `asset` - `realized_profit_atomic` - `sweep_percent` - `sweep_amount_atomic` - `reserve_snapshot` JSONB - `withdrawal_intent_id` nullable - `status` - unique logical trigger key to prevent the same close event/asset/policy version being swept twice.

**`wallet_policy_versions`** - `id` - `sweep_percent` (default `50`) - `allowed_assets` - `reserve_policy` (`DYNAMIC`) - `min_sweep_atomic` - `per_transfer_cap` - `daily_cap` - `cooldown_seconds` - `destination_wallet_id` - `version` - `enabled` - `created_by` - `created_at`.

**`watchlists`**, **`watchlist_items`** - User/watchlist metadata. -
Token references. - Unique watchlist/token relation.

**`provider_configs`** - Provider name/type. - Enabled state. - Base
URL. - Non-secret settings. - Secret reference, not raw secret in
ordinary table. - Last health status. - Updated timestamp.

**`agent_configs`** - Agent name. - Provider ID. - Model ID. -
Auto/manual mode. - Capabilities. - Timeout/retry/context/output
budgets. - Fallback policy. - Enabled state. - Version.

**`llm_requests`** - Agent, provider, requested model, actual model. -
Status, latency, retry count. - Token usage. - Cost and cost status. -
Request ID and timestamp. - Sanitized error metadata.

**`alert_deliveries`** - Signal/event reference. - Channel. - Delivery
status. - Attempt count. - Sent timestamp.

**`provider_health`** - Provider. - Status. - Last success. - Error
count. - Latency. - Updated timestamp.

**`audit_logs`** - Actor. - Action. - Entity type/id. - Sanitized
metadata. - Timestamp.

### 11.2 Integritas data dan accounting

Canonical equity model:

`equity = initial_capital + realized_pnl + unrealized_pnl - external_cash_movements`

Definisikan tanda cash movement secara konsisten dan dokumentasikan
apakah `external_cash_movements` positif berarti modal keluar atau
masuk. Pilih satu konvensi dan gunakan pada seluruh laporan.

Aturan tambahan wallet/transfer:
- Bot wallet dan main wallet harus memiliki identitas ledger terpisah jika saldo keduanya ditampilkan.
- Transfer internal antardua wallet milik portfolio yang sama tidak mengubah combined equity; network fee tetap mengurangi equity.
- Transfer tidak boleh dianggap sebagai trading PnL. Realized PnL hanya berasal dari event trading yang sah.
- Saldo on-chain, internal ledger, pending outflows, signature, dan fee harus direkonsiliasi; ketidakpastian memblokir sweep.
- Setiap accounting event transfer mengacu pada `withdrawal_intent_id` dan signature bila tersedia.

Aturan: - PAPER dan LIVE dipisahkan pada seluruh order, fill, position,
cash movement, dan accounting. - Semua fill aktual harus dapat
direkonsiliasi ke bukti transaksi. - Simulated fill tidak pernah
disamakan dengan actual fill. - Event accounting bersifat append-only
secara logis; koreksi dibuat sebagai event baru. - Setiap kalkulasi
equity dapat direkonstruksi dari event. - High-water mark dan drawdown
memiliki definisi serta tes eksplisit. - Unique constraint dan
idempotency mencegah double order/double accounting.

------------------------------------------------------------------------

## 12. REST API

Base path: `/api/v1`. Semua endpoint selain health check memerlukan auth
sesuai deployment.

### 12.1 System & providers

-   `GET /health`
-   `GET /system/status`
-   `GET /providers/status`
-   `POST /providers/{provider}/test`
-   `GET /providers/{provider}/models`
-   `GET /ai/agents`
-   `PUT /ai/agents/{agent_id}`
-   `GET /ai/usage`
-   `GET /ai/requests`

### 12.2 Market & analysis

-   `GET /tokens`
-   `GET /tokens/{mint}`
-   `GET /tokens/{mint}/pairs`
-   `GET /tokens/{mint}/candles`
-   `GET /tokens/{mint}/risk`
-   `POST /tokens/{mint}/analyze`
-   `GET /analysis/runs`
-   `GET /analysis/runs/{run_id}`
-   `GET /signals`
-   `GET /signals/{signal_id}`
-   `GET /signals/{signal_id}/evaluations`

### 12.3 Watchlist

-   `GET /watchlists`
-   `POST /watchlists`
-   `POST /watchlists/{id}/items`
-   `DELETE /watchlists/{id}/items/{mint}`

### 12.4 Bot & risk

-   `GET /bot/status`
-   `POST /bot/start`
-   `POST /bot/pause`
-   `POST /bot/resume`
-   `POST /bot/stop`
-   `POST /bot/emergency-stop`
-   `GET /bot/runs`
-   `GET /bot/runs/{id}`
-   `GET /bot/orders`
-   `GET /bot/positions`
-   `GET /risk/config`
-   `PUT /risk/config`

Endpoint LIVE tidak boleh aktif pada rilis awal meskipun route atau
interface disiapkan. Server harus menolak live start ketika feature gate
belum dibuka.

### 12.5 Wallets, transfers & profit sweep

-   `GET /wallets`
-   `GET /wallets/{wallet_id}/balances?assets=SOL,USDC`
-   `GET /wallets/{wallet_id}/reserve`
-   `GET /wallets/{wallet_id}/sweepable`
-   `GET /wallet-policy`
-   `PUT /wallet-policy` (authenticated operator; creates a new policy version and audit event)
-   `POST /wallet-transfers/validate`
-   `POST /wallet-transfers` (manual intent; idempotency key required)
-   `POST /wallet-transfers/{intent_id}/confirm`
-   `POST /wallet-transfers/{intent_id}/cancel`
-   `GET /wallet-transfers`
-   `GET /wallet-transfers/{intent_id}`
-   `POST /wallet-transfers/{intent_id}/reconcile`
-   `POST /profit-sweep/evaluate` (dry-run/evaluation; must not sign or submit)
-   `GET /profit-sweep/events`
-   `POST /profit-sweep/enable` and `POST /profit-sweep/disable` (separate wallet feature gate; operator-only)

Wallet write endpoints must enforce authentication, authorization, idempotency, feature gates, allowlisted destinations, and server-side balance/reserve validation. A frontend-only disable switch is insufficient. On-chain endpoints must return the current transaction state and must not claim success before the configured confirmation commitment is reached.

### 12.6 Portfolio & performance

-   `GET /portfolio/summary`
-   `GET /portfolio/equity-curve`
-   `GET /portfolio/transactions`
-   `GET /accounting/audit`
-   `GET /performance/summary`
-   `GET /performance/strategies`
-   `POST /backtests`
-   `GET /backtests/{id}`

Semua list endpoint mendukung pagination, filter, dan sorting yang
tervalidasi. Gunakan error envelope konsisten: `code`, `message`,
`request_id`, dan sanitized `details`.

------------------------------------------------------------------------

## 13. Signal Lifecycle dan State Machine

Status signal: - `CREATED` - `VALIDATED` - `WAIT` - `REJECTED` -
`ACTIVE` - `EXPIRED` - `INVALIDATED` - `EVALUATED`

Transisi harus eksplisit dan diuji. Signal `REJECTED`, `EXPIRED`, atau
`INVALIDATED` tidak boleh diteruskan untuk order baru. Perubahan harga
setelah signal dibuat harus diperiksa ulang terhadap freshness, expiry,
dan invalidation sebelum digunakan oleh bot.

Order lifecycle: - `INTENT_CREATED` - `RISK_APPROVED` atau
`RISK_REJECTED` - `SUBMITTED` (live future only) -
`OPEN/PARTIALLY_FILLED/FILLED` - `CANCEL_PENDING/CANCELLED` - `FAILED` -
`RECONCILIATION_REQUIRED`

Paper execution menggunakan status simulasi yang dibedakan dari status
order live.

------------------------------------------------------------------------

## 14. Performance Metrics dan Evaluasi Strategi

Metrik minimal: - Win rate. - Average win/loss. - Expectancy per
trade. - Gross profit/loss. - Profit factor. - Maximum drawdown. -
Equity curve. - MAE/MFE. - Signal latency. - Coverage. - False-positive
rate sesuai definisi target. - Fee dan slippage impact.

Formula: -
`expectancy = win_rate * average_win - loss_rate * average_loss`, dengan
average loss ditulis sebagai besaran positif. -
`profit_factor = gross_profit / abs(gross_loss)`; bila gross loss nol,
hasil ditampilkan sebagai undefined/infinite sesuai kebijakan, bukan
angka buatan. - Drawdown dihitung dari puncak equity ke equity
berikutnya.

Ketentuan evaluasi: - Masukkan fee, slippage, latency, partial fill, dan
exit yang realistis. - Hindari look-ahead bias. - Hindari survivorship
bias sejauh data tersedia. - Pisahkan in-sample dan out-of-sample. -
Jangan menghitung signal yang belum mencapai horizon sebagai hasil
final. - Semua metrik harus berasal dari transaksi/event dataset yang
sama. - Jangan mengoptimasi strategi hanya pada satu periode pasar.

------------------------------------------------------------------------

## 15. Alerts & Telegram

Fitur opsional: - Signal candidate. - Risk flag baru. - Signal
invalidated/expired. - Bot stopped atau circuit breaker. - Provider
down/recovered. - Daily performance summary.

Setiap alert memiliki deduplication key dan cooldown. Jangan mengirim
alert berulang pada setiap polling. Kegagalan Telegram tidak boleh
menghentikan analysis atau bot engine. Token bot disimpan sebagai secret
backend.

------------------------------------------------------------------------

## 16. Security Requirements

-   Semua secret hanya di backend/secret manager.
-   Jangan menggunakan prefix frontend yang mengekspos API key.
-   HTTPS pada deployment publik.
-   CORS allowlist.
-   Authentication dan authorization untuk endpoint sensitif.
-   Rate limiting dan request validation.
-   Sanitasi log.
-   Dependency scanning dan lockfile.
-   Database least privilege dan backup.
-   Tidak ada private key/seed phrase dalam database biasa, logs, prompt
    AI, atau frontend.
-   Jika live wallet diperlukan pada fase mendatang, gunakan signer
    terisolasi dan kebijakan secret yang direview secara terpisah.
-   AI provider tidak diberi akses langsung ke execution tools.
-   Untrusted token metadata tidak boleh dianggap sebagai instruksi.
-   Emergency stop dan risk gate berjalan tanpa memerlukan LLM.
-   Semua perubahan risk settings, model berbayar, dan mode live masuk
    audit log.
-   Wallet withdrawal memakai feature gate terpisah dari live trading; keduanya default OFF.
-   Main wallet hanya menjadi tujuan treasury; automatic signer tidak boleh mengirim dana dari main wallet.
-   Withdrawal hanya boleh menuju alamat main wallet yang allowlisted. Perubahan destination wajib dikonfirmasi dan diaudit.
-   Signing dilakukan melalui signer terisolasi; AI agent tidak memiliki akses ke key material atau tool signing.
-   Semua transfer memerlukan idempotency key, unique transaction signature, balance/reserve revalidation, serta reconciliation workflow.
-   Jika signature/status tidak pasti, fail closed ke `RECONCILIATION_REQUIRED`; jangan retry transaksi secara buta.

------------------------------------------------------------------------

## 17. Non-Functional Requirements

  -----------------------------------------------------------------------
  Area                                Target
  ----------------------------------- -----------------------------------
  API read latency                    P95 \< 500 ms untuk endpoint
                                      cache/database pada beban uji yang
                                      ditetapkan

  Scanner refresh                     Target 15--60 detik sesuai provider
                                      quota

  Data freshness                      Timestamp dan stale status terlihat

  Reliability                         Provider failure terisolasi

  Reproducibility                     Analysis run menyimpan
                                      snapshot/versi yang cukup

  Security                            Tidak ada secret di frontend/log

  Observability                       Structured logs, health, latency,
                                      error rate

  Responsive UI                       Desktop dan mobile

  Cost controls                       Cache, rate limit, usage logging

  Numeric safety                      Null/NaN/Infinity tidak
                                      menghasilkan keputusan valid

  Data integrity                      Tidak ada duplikasi
                                      order/accounting dari retry
  -----------------------------------------------------------------------

Target latency bukan jaminan untuk seluruh provider/free-tier hosting;
acceptance diuji pada lingkungan yang ditentukan.

------------------------------------------------------------------------

## 18. Acceptance Criteria / Definition of Done

### A. Data pipeline

-   [ ] Token yang ditampilkan memiliki chain/mint/pair identity yang
    tervalidasi.
-   [ ] HTTP 429, timeout, 5xx, malformed JSON, dan provider schema
    changes ditangani.
-   [ ] Snapshot menampilkan observed timestamp dan freshness.
-   [ ] Request deduplication dan cache mengurangi request berulang.
-   [ ] Data hilang tidak disamakan dengan nol.

### B. Analysis Engine

-   [ ] Indikator deterministik memiliki unit tests.
-   [ ] Risk assessment menyimpan evidence, coverage, timestamp, dan
    rule version.
-   [ ] Hard-reject selalu mengalahkan skor agregat.
-   [ ] Unknown mandatory safety checks tidak dapat dianggap aman.
-   [ ] Signal menyimpan alasan, expiry, invalidation, input snapshot,
    dan engine version.
-   [ ] Output untuk input dan versi konfigurasi yang sama
    deterministik, kecuali komponen AI yang ditandai terpisah.

### C. AI providers

-   [ ] 9Router dapat dikonfigurasi melalui OpenAI-compatible base URL,
    key, dan model ID.
-   [ ] OpenRouter dapat dikonfigurasi dengan key dan model ID.
-   [ ] Provider connection test menampilkan hasil yang dapat
    ditindaklanjuti.
-   [ ] Default OpenRouter adalah `openrouter/free`.
-   [ ] Model paid ditolak oleh backend kecuali dipilih manual dan
    dikonfirmasi.
-   [ ] Fallback otomatis OpenRouter tidak keluar dari kebijakan
    free-only.
-   [ ] Cross-provider fallback disabled secara default dan, jika
    diaktifkan, tetap menghormati free-only policy.
-   [ ] Actual model ID, token usage, latency, retry, status, dan cost
    status tercatat.
-   [ ] Capability mismatch dan malformed structured output ditangani.
-   [ ] API key tidak terlihat pada frontend, response API, atau logs.

### D. Trading Bot Engine

-   [ ] PAPER tidak mengirim transaksi blockchain.
-   [ ] Mode tidak berpindah otomatis ke LIVE.
-   [ ] Signal expired/invalidated tidak dapat membuka posisi.
-   [ ] Duplicate signal tidak membuat duplicate order intent.
-   [ ] Risk gate menolak NaN/Infinity/missing mandatory metrics.
-   [ ] Daily loss, max exposure, max positions, slippage, dan circuit
    breaker memiliki tests.
-   [ ] Stop dan emergency stop memblokir order baru.
-   [ ] Simulated fill ditandai berbeda dari actual fill.
-   [ ] Live start ditolak selama feature gate belum dibuka.

### E. Accounting & performance

-   [ ] PAPER dan LIVE ledger terpisah.
-   [ ] Equity dihitung dari definisi canonical yang terdokumentasi.
-   [ ] Fee, slippage, realized/unrealized PnL dihitung konsisten.
-   [ ] Retry tidak membuat double accounting.
-   [ ] Semua metrik dashboard dapat direkonsiliasi ke sumber event.
-   [ ] High-water mark dan drawdown memiliki unit/regression tests.
-   [ ] Signal yang belum selesai tidak masuk sebagai hasil final.

### F. Profit Sweep & Wallet Withdrawal

-   [ ] Mode otomatis dan manual tersedia dalam konfigurasi, dengan default sweep 50%.
-   [ ] Hanya SOL dan USDC yang dapat dipilih; USDC diverifikasi berdasarkan mint address yang dikonfigurasi.
-   [ ] Dynamic reserve memasukkan kebutuhan posisi terbuka, order/outflow pending, network/priority fee, dan kebutuhan akun/rent yang relevan.
-   [ ] Unrealized PnL tidak pernah menjadi dasar profit sweep.
-   [ ] Formula sweepable amount dibatasi oleh 50% realized profit eligible, saldo on-chain spendable, dynamic reserve, pending outflows, dan fee.
-   [ ] Saldo/fee/reserve divalidasi ulang tepat sebelum signing; input stale/unknown menyebabkan fail-closed.
-   [ ] Tujuan otomatis hanya main wallet allowlisted; perubahan destination memerlukan konfirmasi dan audit log.
-   [ ] Manual confirmation menampilkan source, destination lengkap, asset, amount, fee estimate, reserve setelah transfer, dan saldo tersisa.
-   [ ] State machine transaksi dan transisi ilegal diuji, termasuk `RECONCILIATION_REQUIRED`.
-   [ ] Duplicate request dengan idempotency key/payload sama menghasilkan intent yang sama; payload berbeda dengan key sama menghasilkan conflict.
-   [ ] Timeout setelah submit tidak membuat transaksi duplikat; signature/status diperiksa sebelum retry.
-   [ ] Satu signature tidak dapat menghasilkan accounting event ganda.
-   [ ] Internal transfer tidak mengubah combined portfolio equity dan tidak dicatat sebagai realized trading PnL; network fee mengurangi equity secara tepat satu kali.
-   [ ] Sweep failure tidak menghentikan engine trading dan tidak merusak ledger; accounting uncertainty memblokir sweep berikutnya.
-   [ ] Key/seed phrase tidak muncul pada database biasa, log, frontend, API response, atau prompt AI.
-   [ ] Wallet feature gate dan live-trading feature gate terpisah dan default OFF.
-   [ ] PAPER/sandbox withdrawal tidak mengirim transaksi blockchain dan ditandai jelas sebagai simulasi.

### G. UI & operasi

-   [ ] Semua menu P0 berfungsi.
-   [ ] Loading, empty, stale, error, dan unavailable memiliki state
    yang berbeda.
-   [ ] PAPER/LIVE status selalu terlihat.
-   [ ] Bot Start/Stop/Pause/Resume menunjukkan status aktual dari
    backend.
-   [ ] Docker Compose dapat menjalankan stack lokal dari dokumentasi.
-   [ ] Migrasi database dan `.env.example` tersedia.
-   [ ] Tidak ada blocker keamanan kritis.
-   [ ] Unit, integration, dan end-to-end tests wajib lulus.

------------------------------------------------------------------------

## 19. Roadmap Implementasi

### Phase 1 --- Foundation

-   Monorepo, Docker, config, database, migrations, FastAPI, React.
-   Auth dan health checks.
-   OpenAPI contract.
-   Logging dasar.

**Exit gate:** aplikasi lokal berjalan, migrasi dan health checks lulus.

### Phase 2 --- Market Data

-   DEX Screener adapter.
-   Solana RPC adapter.
-   Token/pair normalization.
-   Snapshots, candle storage, cache, provider health.

**Exit gate:** data nyata tampil dengan freshness dan error handling.

### Phase 3 --- Analysis Engine

-   Technical indicators.
-   On-chain checks.
-   Risk scoring dan hard-reject.
-   Signal lifecycle.
-   Analysis history.

**Exit gate:** deterministic tests dan risk tests lulus.

### Phase 4 --- AI Agent Center

-   Provider abstraction.
-   9Router adapter.
-   OpenRouter adapter.
-   OpenRouter free-only enforcement.
-   Model registry, per-agent configuration, diagnostics, usage logs.

**Exit gate:** provider tests lulus dan tidak ada jalur otomatis ke paid
model.

### Phase 5 --- Terminal UI

-   Overview.
-   Scanner, token detail/chart.
-   Signal center.
-   Watchlist dan history.
-   Agent center.

**Exit gate:** UI terhubung ke API nyata dan semua error/stale states
berfungsi.

### Phase 6 --- Paper Trading & Accounting

-   Bot control.
-   Paper execution.
-   Risk gate.
-   Positions, orders, fills, accounting.
-   Performance summary.
-   Wallet ledger, Profit Sweep 50% (SOL/USDC), dynamic reserve calculation, manual withdrawal simulation, transaction state machine, idempotency, dan reconciliation.

**Exit gate:** reconciliation, idempotency, accounting regression, simulated execution tests, dan wallet transfer simulations lulus.

### Phase 7 --- Hardening & Deployment

-   Security review.
-   Load tests.
-   Backup/restore.
-   Observability.
-   Runbooks.
-   Acceptance test final.

**Exit gate:** seluruh P0 criteria lulus; live tetap disabled.

### Phase 8 --- Future Live Readiness

Fase terpisah setelah rilis V1: - Live signer/adapter. - Small-capital
controlled rollout. - Transaction reconciliation. - Recovery drills. -
Approval gate dan kill-switch validation.

Fase ini bukan bagian dari definisi selesai V1. Wallet on-chain withdrawal/sweep memerlukan gate terpisah, signer review, allowlist destination, caps/cooldown, recovery drill, dan persetujuan eksplisit; kesiapan live trading tidak otomatis mengaktifkan wallet transfer.

------------------------------------------------------------------------

## 20. Estimasi Waktu

Estimasi untuk satu developer yang fokus dan menggunakan coding agents
sebagai alat bantu:

  Phase                         Estimasi
  -------------------------- -----------
  Foundation                   3--5 hari
  Market data                  3--5 hari
  Analysis engine              5--8 hari
  AI Agent Center              3--5 hari
  Terminal UI                  5--8 hari
  Paper trading/accounting     5--8 hari
  Hardening/deployment         3--5 hari

Perkiraan total: sekitar 4--6 minggu dengan asumsi scope terkendali,
provider tersedia, dan tidak ada hambatan besar. Angka ini bukan
jaminan; kualitas market data dan accounting membutuhkan pengujian yang
tidak boleh dipangkas demi mengejar tanggal.

------------------------------------------------------------------------

## 21. Risiko dan Mitigasi

  -----------------------------------------------------------------------
  Risiko                              Mitigasi
  ----------------------------------- -----------------------------------
  Free model tidak tersedia/terkena   Fallback free yang terbatas, error
  rate limit                          eksplisit, optional 9Router
                                      fallback

  Provider mengganti model yang       Simpan actual model ID per request
  dipilih                             

  Data pasar stale                    Freshness threshold dan fail-closed
                                      untuk tindakan berisiko

  Token rug pull/manipulasi           Hard-reject, risk flags, no safety
                                      guarantees

  LLM output tidak valid              Schema validation; jangan teruskan
                                      ke signal/order

  Biaya model tak terduga             Paid-model allowlist, backend
                                      enforcement, usage monitoring

  Duplicate orders                    Idempotency key dan state machine

  Accounting mismatch                 Append-only events, reconciliation,
                                      regression tests

  Public RPC throttling               Cache, backoff, configurable
                                      endpoint

  Model tidak mendukung tool/schema   Capability validation dan safe
                                      fallback

  Live trading rugi akibat slippage   Live disabled by default,
                                      paper/shadow tests, risk limits

  Prompt injection dari token         Treat external content as untrusted
  metadata                            data
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 22. Definition of Done untuk V1

V1 dapat dinyatakan selesai ketika:

1.  Scanner menggunakan data pasar nyata dan menampilkan status
    freshness.
2.  Analysis Engine menghasilkan risk assessment dan signal yang dapat
    diaudit.
3.  9Router dan OpenRouter dapat dikonfigurasi dari AI Agent Center.
4.  OpenRouter memakai `openrouter/free` secara default dan paid models
    diblokir kecuali dipilih manual serta dikonfirmasi.
5.  Paper Bot dapat mengonsumsi signal, menjalankan simulasi, dan
    mencatat order/fill/position/accounting.
6.  Performance metrics berasal dari ledger/event yang sama dan dapat
    direkonsiliasi.
7.  Start/Stop/Pause/Resume dan emergency stop diuji.
8.  Profit Sweep & Wallet Withdrawal tersedia untuk simulasi/PAPER, dengan state machine, idempotency, dynamic reserve, dan accounting tests yang lulus.
9.  Tidak ada jalur transaksi blockchain nyata aktif pada rilis V1; wallet withdrawal dan live trading memakai feature gate terpisah yang default OFF.
10. Semua P0 acceptance criteria lulus dan tidak ada blocker keamanan kritis.
11. Dokumentasi setup, konfigurasi, migrasi, backup, diagnosa, dan recovery tersedia.

------------------------------------------------------------------------

## 23. Referensi Teknis

-   DEX Screener API Reference:
    https://docs.dexscreener.com/api/reference
-   Solana RPC Documentation: https://solana.com/docs/rpc
-   Solana WebSocket RPC: https://solana.com/docs/rpc/websocket
-   9Router Documentation: https://docs.9router.com/
-   9Router OpenAI-compatible integration:
    https://github.com/decolua/9router
-   OpenRouter Documentation: https://openrouter.ai/docs
-   OpenRouter Free Models Router:
    https://openrouter.ai/docs/guides/routing/routers/free-router
-   OpenRouter Model Fallbacks:
    https://openrouter.ai/docs/guides/routing/model-fallbacks
-   TradingView Lightweight Charts:
    https://github.com/tradingview/lightweight-charts
-   FastAPI: https://fastapi.tiangolo.com/
-   Supabase: https://supabase.com/docs

Dokumentasi provider dapat berubah. Verifikasi endpoint, model ID,
capability, rate limit, dan pricing pada saat implementasi.

------------------------------------------------------------------------

## 24. Instruksi untuk Coding Agent

Implementasikan PRD ini secara bertahap. Jangan membuat seluruh fitur
sekaligus dalam satu perubahan besar.

Urutan wajib: 1. Baca PRD dan buat implementation plan dengan dependency
graph. 2. Buat repository, Docker, database migrations, health check,
dan API contract. 3. Implementasikan market data adapter dan tests. 4.
Implementasikan deterministic analysis/risk/signal engine. 5.
Implementasikan 9Router/OpenRouter provider abstraction dengan
OpenRouter free-only enforcement. 6. Implementasikan UI Analysis Engine.
7. Implementasikan Paper Bot, risk gate, ledger, dan reconciliation. 8.
Implementasikan performance metrics dan hardening. 9. Jalankan seluruh
test suite dan laporkan hasil aktual.

Setiap fase harus menghasilkan: - File yang berubah. - Tes yang
dijalankan dan hasil aktual. - Acceptance criteria yang terpenuhi/belum
terpenuhi. - Known limitations. - Risiko yang belum diselesaikan.

Jangan mengklaim test lulus jika tidak dijalankan. Jangan menggunakan
mock data sebagai bukti bahwa integrasi provider atau market data sudah
berhasil. Jangan mengaktifkan live trading atau wallet on-chain withdrawal, memilih model berbayar, atau melewati hard-reject tanpa persetujuan eksplisit. Untuk wallet, implementasikan dahulu simulasi/PAPER dan test state machine, idempotency, reserve, ledger, serta reconciliation sebelum ada integrasi signer live. Jika ada konflik
antara kenyamanan implementasi dan aturan keselamatan/akuntansi, aturan
keselamatan dan integritas data menang.
