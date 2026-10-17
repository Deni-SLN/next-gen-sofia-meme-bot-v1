# ⚡ SOFIA Trenches v3.8 PRO (NextGenTSofia Trade)

Platform **AI-Powered Meme Coin Sniper & On-Chain Trading Command Center** dengan dukungan penuh **Dual-Engine (Mode PAPER Rp 150.000 & Mode LIVE On-Chain)**, **PumpSniper Pro Terminal (Jito 0-Slot Anti-MEV)**, **Direct Chrome Extension Wallet Connect (Phantom / Solflare / MetaMask / Rabby)**, **Jurnal Trading Live di Neon PostgreSQL Cloud + Export Excel**, serta **Mobile-Responsive Progressive Web App (PWA)**.

📄 **Dokumentasi Produk Lengkap**: Lihat [**PRD.md**](./PRD.md) untuk spesifikasi lengkap arsitektur dan fitur v3.8 PRO.

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
