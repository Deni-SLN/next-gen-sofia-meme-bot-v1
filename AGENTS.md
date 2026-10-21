# 🤖 PANDUAN PENGEMBANGAN UNTUK AI AGENT (AGENTS.md)
## **SOFIA Multi-Asset Intelligence & Autonomous Meme Coin Sniper Platform**

Dokumen ini adalah referensi teknis wajib bagi seluruh **AI Agent**, *autonomous developer*, atau asisten AI yang membaca, memelihara, atau memodifikasi *codebase* **NextGen SOFIA Trading Platform**.

---

## 1. Aturan Mutlak & Pantangan Keras (Critical Invariants)

Setiap AI Agent yang bekerja pada repositori ini **WAJIB** mematuhi 6 aturan di bawah ini:

### ⚠️ Aturan 1: ZERO DUMMY DATA (Dilarang Mengarang Angka)
- **Pantangan**: Dilarang keras menuliskan angka persentase sintetis, estimasi buatan (*hardcoded* winrates seperti `78.5%`, `66.4%`, `54.2%`), rentang estimasi karangan (`74% – 82%`), atau rumus *Bayesian blend* yang mencampur aduk angka karangan dengan data riil.
- **Kewajiban**:
  - Seluruh *winrate*, keuntungan/kerugian (PnL), dan metrik rekor transaksi wajib **100% dihitung dari tabel database `Trade`** dengan filter `status == 'closed'` dan `side == 'sell'`.
  - Jika belum ada data transaksi yang ditutup pada mode tertentu (`trades_count == 0`), kembalikan nilai `None` (di backend) dan tampilkan `🎯 Winrate: — (Belum ada trade)` (di frontend).
  - Pengguna lebih mengutamakan integritas matematis yang jujur daripada angka dekoratif palsu.

### ⚠️ Aturan 2: Bot Berjalan Otonom di Server 24/7 (Survives Logout)
- **Pantangan**: Jangan pernah mengaitkan siklus eksekusi bot dengan status login frontend, session storage, browser tab, atau websocket browser.
- **Kewajiban**:
  - Mesin bot dikendalikan oleh background worker server FastAPI `_autonomous_bot_engine_worker` di [services/api/app/main.py](file:///D:/nextgentsofia%20trade/services/api/app/main.py).
  - Bot harus terus berjalan memindai pasar dan mengeksekusi order walaupun pengguna menutup browser, berganti perangkat, atau melakukan logout.
  - **Satu-satunya pemicu yang menghentikan bot** adalah klik manual tombol **"⏹ HENTIKAN BOT SEKARANG"** (`POST /api/v1/bot/stop`).

### ⚠️ Aturan 3: Kunci Pengaman Mode Strategi saat Bot Aktif
- **Kewajiban**:
  - Selama bot berstatus `running`, mode strategi (`SAFE`, `DEFAULT`, `AGGRESSIVE`) **wajib terkunci**.
  - Tombol mode lain di-disable untuk mencegah *race condition* dan benturan eksekusi sniper.
  - Pengguna harus menghentikan bot terlebih dahulu sebelum berpindah mode strategi.

### ⚠️ Aturan 4: Quick Exit & Panic Sell Wajib Handal (Case-Insensitive & Adaptive Slippage)
- **Kewajiban**:
  - Pencarian posisi di database pada fungsi `sell_holding` wajib menggunakan pencocokan *case-insensitive* (`or_(PortfolioHolding.symbol == sym, func.upper(PortfolioHolding.symbol) == sym.upper())`).
  - Eksekusi jual di on-chain Solana menggunakan *adaptive slippage retry* (3.5% hingga 8.0%) agar tidak gagal akibat fluktuasi likuiditas koin meme.
  - Sediakan opsi likuidasi parsial (`25%`, `50%`, `100%`) dan likuidasi total 1-klik (**Panic Sell All**).

### ⚠️ Aturan 5: Menu Crypto (Koin Populer Maksimal 10 & Bar Layar Lebar di Atas)
- **Kewajiban**:
  - Bar tombol cepat koin populer di [apps/web/src/pages/crypto.tsx](file:///D:/nextgentsofia%20trade/apps/web/src/pages/crypto.tsx) dibatasi strictly **maksimal 10 koin** (`popularList.slice(0, 10)`). Koin lainnya wajib dicari melalui input pencarian manual.
  - Tombol *toggle* mode layar lebar (*Ultrawide*) hanya ditempatkan di bagian atas halaman (header bar).

### ⚠️ Aturan 6: Desain Visual Daylight / Light Mode Teduh di Mata
- **Kewajiban**:
  - Jika mengubah CSS tema, pastikan Light Mode menggunakan palet *Soft Daylight Workspace* (terinspirasi dari TradingView & Stockbit Pro).
  - Hindari latar belakang putih menyilaukan (`#ffffff` mentah); gunakan abu-abu netral lembut (`#f1f5f9` / `#e2e8f0`), kartu putih bertepi teduh, dan kontras teks gelap (`#0f172a`) yang nyaman dibaca berjam-jam.

---

## 2. Struktur Proyek & Arsitektur Direktori

```
D:\nextgentsofia trade\
├── apps\
│   └── web\                     # Frontend Next.js (Port 3000)
│       ├── src\
│       │   ├── components\      # Komponen UI Reusable (Layout, BotActivityCard, TradingChart, LucideIcon, dll.)
│       │   ├── lib\             # api.ts (Klien Axios/Fetch), web3.ts (Koneksi Ekstensi Chrome Phantom/MetaMask)
│       │   ├── pages\           # Seluruh 20+ Rute Halaman (index, trading, stocks, crypto, gold, chat, dll.)
│       │   └── styles\          # globals.css (Tailwind CSS, Tema Dark Obsidian & Soft Daylight)
│       └── package.json
│
├── services\
│   └── api\                     # Backend FastAPI Python (Port 8000)
│       ├── app\
│       │   ├── core\            # config.py, security.py (JWT Bearer Token)
│       │   ├── db\              # models.py (SQLAlchemy ORM), session.py (Neon Serverless PostgreSQL)
│       │   ├── routers\         # bot.py, portfolio.py, stocks.py, crypto.py, gold.py, chat.py, news.py, dll.
│       │   └── services\        # bot.py (Sniper Engine), live_engine.py, ai_chat.py, market.py, treasury.py
│       ├── sniper_config.json   # Konfigurasi aktif bot & parameter preset yang dipersistensikan
│       └── requirements.txt
│
├── PRD.md                       # Product Requirements Document resmi
└── AGENTS.md                    # File ini (Panduan Operasional AI Agent)
```

---

## 3. Komponen Utama & Alur Data

### 3.1. Preset Mode Strategi Sniper ([`bot.py`](file:///D:/nextgentsofia%20trade/services/api/app/services/bot.py))
- **`SAFE`**: Likuiditas > $20K, Min Score 82, Max Dev 5%, target Raydium/PumpSwap migrated pools.
- **`DEFAULT`**: Likuiditas > $5K, Min Score 70, Max Dev 10%, target Final Stretch & migrated pools.
- **`AGGRESSIVE`**: Likuiditas > $2K, Min Score 60, Max Dev 15%, Max Age 180m, Max MCap $500K. Memblokir token lama (BONK, PEPE, WIF, POPCAT) agar 100% fokus pada koin baru DexScreener v1 & GMGN.ai.

### 3.2. Perhitungan Winrate Riil
```python
# Format penghitungan di get_strategy_winrate_stats()
stats[m_key]["trades_count"] += 1
if float(t.pnl or 0.0) >= 0:
    stats[m_key]["wins"] += 1
else:
    stats[m_key]["losses"] += 1

if stats[m_key]["trades_count"] > 0:
    stats[m_key]["winrate_pct"] = round((stats[m_key]["wins"] / stats[m_key]["trades_count"]) * 100.0, 1)
```

### 3.3. Dual Execution: Mode PAPER vs Mode LIVE
- **Mode PAPER**: Menggunakan saldo virtual awal **Rp 150.000** di tabel `wallets` dengan nama `Modal Paper Simulasi (Rp 150.000)`. Dapat di-reset ke modal awal kapan saja melalui `POST /api/v1/portfolio/reset-paper`.
- **Mode LIVE**: Menggunakan kunci privat Solana on-chain (`SOFIA_SOLANA_TRADING_PRIVATE_KEY`), memotong gas fee SOL asli, dan menyinkronkan saldo langsung dengan node RPC Mainnet.

---

## 4. Prosedur Verifikasi Sebelum Menyerahkan Tugas

Sebelum menyelesaikan pekerjaan atau merespons pengguna, setiap AI Agent **wajib** menjalankan verifikasi:

1. **Verifikasi TypeScript (Frontend)**:
   ```powershell
   cd "D:\nextgentsofia trade\apps\web"
   ./node_modules/.bin/tsc --noEmit
   ```
   *Wajib keluar dengan code 0 tanpa error tipe.*

2. **Verifikasi Build Next.js**:
   ```powershell
   cd "D:\nextgentsofia trade\apps\web"
   npm run build
   ```
   *Wajib sukses mengompilasi seluruh 23 halaman.*

3. **Verifikasi Sintaks Python (Backend)**:
   ```powershell
   cd "D:\nextgentsofia trade"
   python -m py_compile services/api/app/services/bot.py
   python -m py_compile services/api/app/services/portfolio.py
   python -m py_compile services/api/app/routers/*.py
   ```

4. **Verifikasi Endpoint API**:
   Jalankan pengujian via `TestClient` FastAPI untuk memastikan tidak ada rute yang menghasilkan error 500.
