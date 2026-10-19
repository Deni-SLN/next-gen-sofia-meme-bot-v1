# 🌐 Panduan Integrasi SOFIA Model Context Protocol (MCP) Server

Server **SOFIA Model Context Protocol (MCP)** memungkinkan agen kecerdasan buatan eksternal seperti **Hermes Agent** (Nous Research), **OpenClaw**, **Claude Desktop**, **Cursor**, **Cline**, dan **Antigravity** untuk mengambil data finansial dan menjalankan tools analisis secara langsung dari platform SOFIA.

---

## 🚀 Pilihan Protokol Koneksi

SOFIA MCP mendukung 3 mode protokol:

| Mode | Protokol | Cocok Untuk | Endpoint / Perintah |
| :--- | :--- | :--- | :--- |
| **1. STDIO (Rekomendasi)** | Standard Input/Output | Hermes Agent, OpenClaw CLI, Claude Desktop, Cursor | `python "D:\nextgentsofia trade\run_mcp.py"` |
| **2. SSE (Server-Sent Events)** | Networked HTTP / SSE | Agen remote, Webhook, Container Docker | `http://127.0.0.1:8000/mcp/sse` |
| **3. REST JSON-RPC** | HTTP POST / GET | OpenClaw crawlers, cURL, script otomatisasi Python/Node.js | `http://127.0.0.1:8000/api/v1/mcp/call` |

---

## 🤖 1. Cara Menghubungkan Hermes Agent

Hermes Agent (berbasis model Nous Research Hermes 2 / Hermes 3 / Llama-3-Hermes) mendukung tool calling dan protokol MCP secara native.

### Konfigurasi STDIO
Tambahkan konfigurasi berikut ke file konfigurasi Hermes Agent Anda (misal `hermes_config.json` atau konfigurasi CLI):

```json
{
  "mcpServers": {
    "sofia-intelligence": {
      "command": "python",
      "args": [
        "D:\\nextgentsofia trade\\run_mcp.py"
      ],
      "env": {
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

### Konfigurasi SSE (Bila Backend FastAPI sedang berjalan)
```json
{
  "mcpServers": {
    "sofia-intelligence": {
      "url": "http://127.0.0.1:8000/mcp/sse"
    }
  }
}
```

File template konfigurasi siap pakai telah disediakan di:
`D:\nextgentsofia trade\hermes_mcp_config.json`

---

## 🦅 2. Cara Menghubungkan OpenClaw

OpenClaw dapat bertindak sebagai data collector dan task runner otomatis yang memanggil tools SOFIA secara terjadwal.

### Konfigurasi `openclaw_config.json`
Gunakan file `openclaw_config.json` yang ada di root direktori proyek:

```json
{
  "name": "openclaw-sofia-collector",
  "connections": {
    "mcp": {
      "type": "stdio",
      "command": "python",
      "args": ["D:\\nextgentsofia trade\\run_mcp.py"]
    },
    "http_fallback": {
      "type": "rest_jsonrpc",
      "base_url": "http://127.0.0.1:8000/api/v1/mcp",
      "tools_endpoint": "/tools",
      "call_endpoint": "/call"
    }
  }
}
```

### Eksekusi via OpenClaw CLI / Script HTTP:
```bash
# Contoh pemanggilan tool via HTTP POST oleh OpenClaw:
curl -X POST http://127.0.0.1:8000/api/v1/mcp/call \
  -H "Content-Type: application/json" \
  -d '{"tool": "get_gold_market", "arguments": {}}'
```

---

## 🖥️ 3. Konfigurasi Claude Desktop & Cursor

Untuk pengguna **Claude Desktop** di Windows (`%APPDATA%\Claude\claude_desktop_config.json`) atau **Cursor** (`.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "sofia": {
      "command": "python",
      "args": [
        "D:\\nextgentsofia trade\\run_mcp.py"
      ]
    }
  }
}
```

---

## 🛠️ Daftar 10 Tools MCP yang Tersedia

### 1. `analyze_stock`
Analisa mendalam saham Bursa Efek Indonesia (IDX / BEI).
- **Argumen**:
  - `ticker` (string, contoh: `"BBRI"`, `"BBCA"`, `"TLKM"`, `"IHSG"`)
  - `timeframe` (string: `"15m"`, `"1h"`, `"4h"`, `"1d"`, `"1w"`, `"1mo"`, default `"1d"`)
- **Data yang dikembalikan**: Harga live IDR, Trading Plan (Entry Zone, TP1, TP2, Stop Loss, Risk-to-Reward Ratio), indikator teknikal (RSI, MACD, MA), serta Fair Value DCF & Valuasi PBV/PER.

### 2. `analyze_crypto`
Analisa aset cryptocurrency global 24/7.
- **Argumen**:
  - `symbol` (string, contoh: `"BTC"`, `"ETH"`, `"SOL"`, `"BONK"`, `"DOGE"`)
  - `timeframe` (string, default `"1d"`)
- **Data yang dikembalikan**: Harga live USD & IDR, rekomendasi Trading Plan, tren, estimasi Staking Yield APR %, dan rasio risiko tokenomics (FDV/MCap).

### 3. `get_gold_market`
Harga emas fisik Indonesia dan kurs spot internasional terkini.
- **Argumen**: Tidak ada.
- **Data yang dikembalikan**: Harga retail Antam CertiEye 1g, harga buyback resmi Antam 1g, persentase spread buyback, harga retail UBS 1g, kurs spot dunia XAU/USD, dan spot IDR/gram.

### 4. `calculate_deposito_vs_bonds`
Kalkulator simulasi perbandingan imbal hasil investasi Deposito (Konvensional / Syariah Mudharabah) vs Surat Berharga Negara (SBN: ORI, Sukuk Ritel, FR).
- **Argumen**:
  - `nominal_idr` (number, contoh: `10000000`)
  - `tenor_days` (integer: `7`, `30`, `90`, `180`, `365`)
  - `deposito_rate_pct` (number, default `5.0`)
  - `bond_rate_pct` (number, default `6.5`)
  - `is_syariah` (boolean, default `false`)
- **Data yang dikembalikan**: Keuntungan kotor, potongan pajak PPh riil (20% Deposito vs 10% SBN), keuntungan bersih setelah pajak, dan selisih yield bersih.

### 5. `analyze_memecoin_rugcheck`
Audit keselamatan dan deteksi honeypot untuk koin meme Solana / Pump.fun / Base.
- **Argumen**:
  - `token_query` (string simbol atau Contract Address token)
- **Data yang dikembalikan**: Safety score (0-100), status LP locked/burned, mint authority disabled, freeze authority disabled, persentase top 10 holders, serta daftar red flags.

### 6. `search_market_news`
Berita finansial dan pasar Indonesia dari sumber terverifikasi (CNBC Indonesia, Antara, dll).
- **Argumen**:
  - `query` (string, opsional, contoh: `"IHSG"`, `"BI Rate"`, `"Bitcoin"`)
  - `category` (string: `"all"`, `"saham"`, `"crypto"`, `"emas"`, `"ekonomi"`)
  - `limit` (integer, default `5`, maks `10`)

### 7. `get_trading_signals`
Sinyal trading kuantitatif aktif yang dihasilkan engine SOFIA.
- **Argumen**:
  - `status` (string: `"pending"`, `"active"`, `"closed"`)
  - `limit` (integer, default `10`)

### 8. `get_portfolio_status`
Ringkasan portofolio live & simulasi, saldo cash, dan kurs USD/IDR.
- **Argumen**: Tidak ada.

### 9. `lookup_market_encyclopedia`
Kamus ensiklopedia finansial, istilah teknikal (SMC, Order Block, FVG, ARA/ARB), dan perbankan syariah (Mudharabah).
- **Argumen**:
  - `keyword` (string, contoh: `"mudharabah"`, `"order block"`, `"ara"`)

### 10. `get_market_pulse`
Snapshot denyut pasar: token trending DexScreener dan kurs FX USD/IDR live.
- **Argumen**: Tidak ada.

---

## 📦 MCP Resources yang Disediakan

Agen dapat membaca resource langsung melalui URI berikut:
- `sofia://market/pulse` : Snapshot live denyut pasar dan token Solana terpopuler.
- `sofia://gold/prices` : Papan harga emas live (Antam, UBS, Spot).
- `sofia://portfolio/summary` : Status ekuitas dan saldo live portofolio.

---

## 📝 MCP Prompts yang Disediakan

- `morning_market_briefing` : Template prompt untuk rangkuman pasar pagi investor Indonesia.
- `stock_investment_thesis` : Template prompt riset mendalam saham emiten BEI.
- `token_risk_audit` : Template prompt due diligence keamanan token kripto.

---

## 🧪 Cara Uji Coba (Testing)

### 1. Test via Command Line:
```bash
python -c "import asyncio, app.mcp_server as s; print(asyncio.run(s.mcp.call_tool('get_gold_market', {})))"
```

### 2. Test via REST HTTP Endpoint:
```bash
# Menampilkan katalog tool:
curl http://127.0.0.1:8000/api/v1/mcp/tools

# Eksekusi analisa saham BBRI:
curl -X POST http://127.0.0.1:8000/api/v1/mcp/call \
  -H "Content-Type: application/json" \
  -d '{"tool": "analyze_stock", "arguments": {"ticker": "BBRI", "timeframe": "1d"}}'
```
