# ⚡ NextGenTSofia Trade

AI-powered crypto trading platform with real-time portfolio management, intelligent signal generation, strict schema-validated LLM agent outputs, and multi-gate risk control.

## ✨ Fitur Utama

- **🤖 Bot Management**: Kontrol mode *Paper Trading* dan *Live Trading* dengan proteksi gate keamanan otomatis.
- **💼 Portfolio Tracking**: Pantau kepemilikan aset, harga rata-rata beli, nilai pasar saat ini, dan Unrealized PnL secara *real-time*.
- **📡 Trading Signals**: Manajemen sinyal trading (*long* / *short*) lengkap dengan *confidence score*, *entry price*, *stop loss*, dan *take profit*.
- **🧠 AI Agents & Schema Guard**: Registrasi agen AI (*analyst*, *risk*, *signal*) dengan validasi bentuk JSON ketat (`app/providers/llm/schemas.py`).
- **🛡️ Risk Management**: Konfigurasi batas ukuran posisi maksimum, kerugian harian maksimum, *drawdown*, dan daftar pasangan aset yang diizinkan.
- **📈 Performance Analytics**: Ringkasan metrik performa trading (*win rate*, *total PnL*, *best/worst trade*).
- **🔐 Multi-Gate Wallets & JWT Auth**: Pengelolaan dompet berdasarkan *gate* (`main`, `trading`, `reserve`) dengan autentikasi Bearer JWT.

## 🏗️ Struktur Proyek

```text
nextgentsofia-trade/
├── services/
│   └── api/
│       ├── app/
│       │   ├── core/          # Konfigurasi & JWT Security
│       │   ├── db/            # SQLAlchemy 2.0 Models & Session
│       │   ├── providers/llm/ # JSON Schema Validator untuk output AI
│       │   ├── routers/       # Endpoint FastAPI (/api/v1/*)
│       │   ├── services/      # Business Logic
│       │   └── main.py        # FastAPI Application Entrypoint
│       ├── Dockerfile
│       └── requirements.txt
├── apps/
│   └── web/                   # Frontend Next.js + Tailwind CSS + TypeScript
│       ├── src/
│       │   ├── components/    # Layout, QueryState, Sidebar
│       │   ├── lib/           # API Client & Hooks
│       │   ├── pages/         # Dashboard, Trading, Portfolio, Signals, Agents, Risk, Wallets
│       │   └── styles/        # Global Tailwind CSS
│       ├── Dockerfile
│       └── package.json
├── _smoke.py                  # Script pengujian end-to-end API
├── _fix_indent.py             # Utilitas verifikasi konfigurasi AST
├── _wire_error.py             # Utilitas verifikasi QueryState frontend
├── docker-compose.yml
└── .env.example
```

## 🚀 Cara Menjalankan (Quick Start)

### 1. Menjalankan Backend API (FastAPI)

```powershell
cd services/api
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

Untuk menjalankan *smoke test* dari root proyek atau `services/api`:

```powershell
$env:PYTHONPATH="services/api"
python _smoke.py
```

### 2. Menjalankan Frontend Web (Next.js)

```powershell
cd apps/web
npm install
npm run dev
```

Buka `http://localhost:3000` di browser dan login menggunakan password default: `changeme` (atau sesuai `SOFIA_ADMIN_PASSWORD` di `.env`).

## 🔌 Daftar Endpoint API Utama

| Method | Endpoint | Deskripsi |
|---|---|---|
| `GET` | `/health` | Cek status kesehatan server |
| `POST` | `/api/v1/auth/login` | Login admin & dapatkan Bearer token |
| `GET` | `/api/v1/bot/status` | Status bot saat ini |
| `POST` | `/api/v1/bot/start` | Mulai bot (`PAPER` atau `LIVE`) |
| `POST` | `/api/v1/bot/stop` | Hentikan bot yang sedang berjalan |
| `GET` | `/api/v1/portfolio/overview` | Ringkasan nilai portofolio & PnL |
| `GET` | `/api/v1/signals` | Daftar sinyal trading |
| `GET` | `/api/v1/ai/agents` | Daftar agen AI terdaftar |
| `GET` | `/api/v1/risk/config` | Konfigurasi manajemen risiko |
| `PUT` | `/api/v1/risk/config` | Perbarui parameter risiko |
| `GET` | `/api/v1/performance/summary` | Statistik performa trading |
| `GET` | `/api/v1/wallets` | Daftar dompet & gate alokasi |
