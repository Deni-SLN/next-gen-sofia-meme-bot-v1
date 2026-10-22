# ⚡ Sofia Market 3.9 — Multi-Asset Trading Terminal & Autonomous Sniper

Platform **Sofia Market 3.9** adalah terminal riset pasar finansial & sistem *trading* kuantitatif terintegrasi:
- **Dual-Engine Execution**: Mode `PAPER` (Sandbox Rp 150.000) & Mode `LIVE` (On-Chain Solana Mainnet Hot Wallet).
- **Autonomous Server Worker 24/7**: Bot terus berjalan memindai dan mengeksekusi order di background server bahkan saat pengguna logout atau menutup browser. Satu-satunya penghenti adalah tombol manual.
- **3 Mode Strategi Sniper (Safe, Default, Agresif)**: Disertai kunci pengaman dan perhitungan winrate riil 100% dari database tanpa angka karangan.
- **Quick Exit & Panic Sell**: Likuidasi parsial 25%, 50%, 100% dan Panic Sell All 100% dengan adaptive slippage retry.
- **Multi-Asset Research Hub**: Analisa Saham BEI (IDX), Analisa Kripto Global (10 koin populer), Portofolio Emas Fisik, Kalkulator Deposito & SBN Obligasi, AI Chat Research dengan tool calling otonom, dan Ensiklopedia Pasar.
- **Dual Theme Workspace**: Soft Daylight Workspace (Light Mode) yang teduh di mata & Obsidian Dark Mode.

---

### 📄 Dokumentasi Resmi & Panduan AI Agent:
- [**PRD.md**](./PRD.md) — Product Requirements Document versi Sofia Market 3.9 lengkap.
- [**AGENTS.md**](./AGENTS.md) — Panduan wajib & batasan aturan kritis untuk AI Agent & pengembang masa depan.
- [**MCP_GUIDE.md**](./MCP_GUIDE.md) — Panduan Model Context Protocol (FastMCP).

---

## ✨ Fitur Utama v3.8 PRO

1. **🎯 Dual-Engine 100% Siap Pakai (Mode PAPER & Mode LIVE)**:
   - **Mode PAPER**: Menggunakan 100% harga pasar real-time dari **DexScreener Live API** dengan modal simulasi **Rp 150.000** yang dapat di-*reset* kapan saja.
   - **Mode LIVE**: Terhubung ke **Live Trading Hot Wallet** (`gate = trading`), menghasilkan *Transaction Hash (`tx_hash`)* berformat Solana Base58 / EVM `0x`, memperbarui saldo dompet secara otomatis, dan mencatat seluruh transaksi ke **Jurnal Trading Live** di **Neonbase Cloud**.
2. **⚡ PumpSniper Pro Terminal (`/trading`)**:
   - **1-Click Terminal Snipe Bar**, pilihan relay **Jito 0-Slot Bundle / Helius Staked / bloXroute**, filter **Bonding Curve % & Max Dev Holding %**, **Auto Take-Profit / Stop-Loss / Trailing Stop**, serta tabel posisi aktif dengan tombol **Jual 25% / 50% / 100%** dan **🚨 Panic Sell All**.
3. **🔌 Connect Wallet Langsung ke Ekstensi Chrome**:
   - Hubungkan langsung ke ekstensi **Phantom**, **Solflare**, **Backpack** (`window.solana`) maupun **MetaMask & Rabby** (`window.ethereum` untuk jaringan Base, Ethereum, BSC) dari Header maupun halaman `/wallets` & `/login`.
4. **📒 Jurnal Trading Live & Download Excel (`/journal`)**:
   - Menampilkan **4 Kartu Metrik Utama** (*Modal Awal*, *Keuntungan Sepanjang Masa*, *Kerugian Sepanjang Masa*, dan *Hasil Bersih*) serta **10 transaksi terakhir** yang ringkas dan ringan, dilengkapi tombol **📥 Download Excel (Semua Jurnal)** (`.csv` UTF-8 BOM).
5. **🏦 Auto Top-Up Gas & Bagi Hasil 05:00 WIB (`/wallets`)**:
   - Otomatis isi ulang Gas Reserve jika `< Rp 3.000` dan transfer **40% keuntungan bersih ke Main Wallet** + **60% kembali ke Modal** setiap pukul 05:00 WIB apabila profit bersih `> 40%`.
6. **📱 Desain Mobile-Responsive & Installable PWA**:
   - Dilengkapi `manifest.json`, Service Worker (`sw.js`), **Mobile Slide-Over Drawer**, **Fixed Bottom Navigation Bar** di layar HP, dan halaman login khusus (`/login`).

---

## 🚀 Cara Menjalankan (Quick Start)

### 1. Menjalankan Backend API (FastAPI + Neon PostgreSQL)

```powershell
cd services/api
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

Menjalankan seluruh pengujian otomatis (`pytest`):

```powershell
cd services/api
python -m pytest -v
```

### 2. Menjalankan Frontend Web & PWA (Next.js)

```powershell
cd apps/web
npm install
npm run dev
```

Buka `http://localhost:3000` (atau `http://localhost:3000/login`) di browser Chrome / Mobile. Gunakan password operator default: `changeme` atau klik **⚡ Masuk Cepat / Connect Ekstensi Chrome**.
