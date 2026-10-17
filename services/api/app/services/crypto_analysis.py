"""
Comprehensive Crypto Asset Analysis Engine for SOFIA Trenches v3.8.
Covers:
- Live USD & IDR Pricing + 24/7 Crypto Market Pulse (BTC, ETH, SOL benchmarks)
- Multi-Timeframe Trading Plan (15m, 1h, 4h, 1d, 1w, 1mo) with Entry Zone, TP1, TP2, Stop Loss, Support/Resistance & Net R/R
- Technical Analysis Engine (SMA 20/50/200, EMA 20/50, Wilder's RSI-14, MACD 12/26/9, Bollinger Bands, ATR-14, VWAP, Breakout/Pullback)
- Tokenomics, FDV/MCap Unlock Risk & Staking Yield APR Intelligence
- Crypto Position Sizing & Spot/Futures Risk Calculator (Exchange Fee + Indonesia Crypto Tax PPh/PPN)
- Walk-Forward Backtest (70% In-Sample / 30% Out-of-Sample) & AI Crypto Analyst
"""

import math
import time
import urllib.parse
from datetime import datetime, timezone, timedelta
from typing import Any, Optional
import httpx

from app.services import market, news as news_service
from app.services.stocks import (
    _is_valid_num,
    _compute_sma,
    _compute_ema,
    _compute_rsi,
    _compute_macd,
    _compute_bollinger_bands,
    _compute_true_atr,
    _compute_vwap,
    _sanitize_and_adjust_candles,
)

WIB_TZ = timezone(timedelta(hours=7))

# Standard Crypto Spot Exchange Fee & Indonesia Bappebti/OJK Tax Assumptions
CRYPTO_EXCHANGE_FEE_PCT = 0.10      # Standard 0.10% Maker/Taker fee (Binance/Bybit/Tokocrypto/Indodax)
CRYPTO_INDONESIA_TAX_PCT = 0.21     # PPh Pasal 22 (0.10%) + PPN (0.11%) on registered Bappebti/OJK exchanges
CRYPTO_ROUNDTRIP_FEE_PCT = 0.40     # Total round-trip fee + tax (~0.40%)

CRYPTO_TIMEFRAMES: dict[str, dict[str, Any]] = {
    "15m": {
        "id": "15m",
        "label": "15 Menit",
        "strategy": "Scalping Intraday Cepat",
        "horizon": "Scalping Cepat (15 Menit)",
        "hold_duration": "15 – 180 Menit",
        "yahoo_interval": "15m",
        "yahoo_range": "5d",
        "tp1_mult": 0.65,
        "tp2_mult": 1.25,
        "sl_mult": 0.48,
        "min_tp1_pct": 1.5,
        "min_tp2_pct": 3.0,
        "min_sl_pct": 1.0,
        "min_rr_threshold": 1.35,
        "lookback_bars": 28,
        "validity_hours": 3,
    },
    "1h": {
        "id": "1h",
        "label": "1 Jam",
        "strategy": "Intraday / Day Trading",
        "horizon": "Intraday Crypto (1 Jam)",
        "hold_duration": "4 – 24 Jam",
        "yahoo_interval": "60m",
        "yahoo_range": "1mo",
        "tp1_mult": 1.10,
        "tp2_mult": 2.15,
        "sl_mult": 0.80,
        "min_tp1_pct": 2.8,
        "min_tp2_pct": 5.5,
        "min_sl_pct": 1.9,
        "min_rr_threshold": 1.40,
        "lookback_bars": 36,
        "validity_hours": 12,
    },
    "4h": {
        "id": "4h",
        "label": "4 Jam",
        "strategy": "Crypto Swing 4H",
        "horizon": "Swing Momentum (4 Jam)",
        "hold_duration": "1 – 5 Hari",
        "yahoo_interval": "60m",
        "yahoo_range": "3mo",
        "tp1_mult": 1.55,
        "tp2_mult": 3.00,
        "sl_mult": 1.10,
        "min_tp1_pct": 4.2,
        "min_tp2_pct": 8.5,
        "min_sl_pct": 2.9,
        "min_rr_threshold": 1.45,
        "lookback_bars": 42,
        "validity_hours": 24,
    },
    "1d": {
        "id": "1d",
        "label": "1 Hari",
        "strategy": "Swing Trading Harian",
        "horizon": "Swing Harian (1 Hari)",
        "hold_duration": "3 – 14 Hari",
        "yahoo_interval": "1d",
        "yahoo_range": "2y",
        "tp1_mult": 2.10,
        "tp2_mult": 4.00,
        "sl_mult": 1.45,
        "min_tp1_pct": 6.0,
        "min_tp2_pct": 12.5,
        "min_sl_pct": 4.2,
        "min_rr_threshold": 1.50,
        "lookback_bars": 30,
        "validity_hours": 48,
    },
    "1w": {
        "id": "1w",
        "label": "1 Minggu",
        "strategy": "Macro Swing Mingguan",
        "horizon": "Swing Mingguan (1 Minggu)",
        "hold_duration": "2 – 8 Minggu",
        "yahoo_interval": "1wk",
        "yahoo_range": "5y",
        "tp1_mult": 3.60,
        "tp2_mult": 6.80,
        "sl_mult": 2.30,
        "min_tp1_pct": 11.0,
        "min_tp2_pct": 22.0,
        "min_sl_pct": 7.5,
        "min_rr_threshold": 1.55,
        "lookback_bars": 45,
        "validity_hours": 168,
    },
    "1mo": {
        "id": "1mo",
        "label": "1 Bulan",
        "strategy": "Position / Halving Cycle",
        "horizon": "Investasi Siklus (1 Bulan)",
        "hold_duration": "1 – 6+ Bulan",
        "yahoo_interval": "1mo",
        "yahoo_range": "5y",
        "tp1_mult": 5.80,
        "tp2_mult": 11.50,
        "sl_mult": 3.60,
        "min_tp1_pct": 18.0,
        "min_tp2_pct": 38.0,
        "min_sl_pct": 12.0,
        "min_rr_threshold": 1.60,
        "lookback_bars": 90,
        "validity_hours": 720,
    },
}

POPULAR_CRYPTOS: list[dict[str, str]] = [
    {"code": "BTC", "name": "Bitcoin", "category": "Layer-1 • Store of Value"},
    {"code": "ETH", "name": "Ethereum", "category": "Layer-1 • Smart Contracts"},
    {"code": "SOL", "name": "Solana", "category": "High-Speed Layer-1"},
    {"code": "BNB", "name": "BNB (Build and Build)", "category": "Exchange & BNB Chain"},
    {"code": "XRP", "name": "XRP (Ripple)", "category": "Cross-Border Payments"},
    {"code": "DOGE", "name": "Dogecoin", "category": "PoW Meme Leader"},
    {"code": "SUI", "name": "Sui Network", "category": "Move Layer-1"},
    {"code": "ADA", "name": "Cardano", "category": "Layer-1 PoS"},
    {"code": "AVAX", "name": "Avalanche", "category": "Subnet Layer-1"},
    {"code": "LINK", "name": "Chainlink", "category": "Oracle & RWA"},
    {"code": "TON", "name": "Toncoin", "category": "Telegram Ecosystem L1"},
    {"code": "TRX", "name": "TRON", "category": "Stablecoin Settlement L1"},
    {"code": "PEPE", "name": "Pepe", "category": "Ethereum Meme"},
    {"code": "BONK", "name": "Bonk", "category": "Solana Meme"},
]

CRYPTO_TOKENOMICS_REGISTRY: dict[str, dict[str, Any]] = {
    "BTC": {
        "name": "Bitcoin",
        "category": "Layer-1 • Digital Gold & Store of Value",
        "consensus": "Proof-of-Work (SHA-256)",
        "circulating_supply_m": 19.82,
        "max_supply_m": 21.00,
        "supply_unit": "Juta BTC",
        "annual_inflation_pct": 0.83,
        "staking_apr_pct": 0.0,
        "staking_mechanism": "Non-PoS (Yield hanya melalui Babylon BTC Staking / Wrapped DeFi ~0.5–2%)",
        "burn_mechanism": "Hard-Cap 21 Juta BTC & Siklus Halving setiap 210.000 blok (~4 Tahun)",
        "strengths": [
            "Kelangkaan absolut dengan batas suplai maksimum 21 juta BTC dan inflasi pasca-Halving 2024 hanya ~0.83%/tahun.",
            "Adopsi institusional global melalui Spot Bitcoin ETF (BlackRock IBIT, Fidelity FBTC) dan cadangan korporasi.",
            "Desentralisasi dan keamanan jaringan Proof-of-Work tertinggi di industri aset digital.",
        ],
        "risks": [
            "Sensitif terhadap kebijakan suku bunga The Fed (likuiditas makro global & indeks DXY).",
            "Tidak menghasilkan native staking yield secara langsung pada protokol dasar.",
        ],
    },
    "ETH": {
        "name": "Ethereum",
        "category": "Layer-1 • Smart Contracts, DeFi & RWA Leader",
        "consensus": "Proof-of-Stake (Gasper) + EIP-1559 Fee Burn",
        "circulating_supply_m": 120.52,
        "max_supply_m": None,
        "supply_unit": "Juta ETH",
        "annual_inflation_pct": 0.15,
        "staking_apr_pct": 3.40,
        "staking_mechanism": "Native Beacon Chain PoS & Liquid Staking (Lido stETH / RocketPool ~3.4% APR)",
        "burn_mechanism": "EIP-1559 membakar Base Fee transaksi secara otomatis (deflasioner saat aktivitas jaringan tinggi)",
        "strengths": [
            "Ekosistem DeFi, Stablecoin, dan Tokenisasi Real-World Assets (RWA) terbesar dengan TVL dominan.",
            "Menghasilkan imbal hasil staking (Native Yield ~3.4% APR) sekaligus mekanisme pembakaran biaya EIP-1559.",
            "Dukungan ekosistem Layer-2 (Arbitrum, Base, Optimism) dan Spot Ethereum ETF.",
        ],
        "risks": [
            "Kompetisi biaya transaksi dan aktivitas ritel dari Layer-1 berkecepatan tinggi seperti Solana dan Sui.",
            "Fragmentasi likuiditas antar jaringan Layer-2.",
        ],
    },
    "SOL": {
        "name": "Solana",
        "category": "High-Throughput Layer-1 • Consumer, DePIN & DEX Leader",
        "consensus": "Proof-of-History (PoH) + Proof-of-Stake",
        "circulating_supply_m": 488.50,
        "max_supply_m": 594.00,
        "supply_unit": "Juta SOL",
        "annual_inflation_pct": 4.60,
        "staking_apr_pct": 6.80,
        "staking_mechanism": "Native Delegated PoS + MEV Jito Staking (JitoSOL / mSOL ~6.8% – 7.5% APR)",
        "burn_mechanism": "50% dari biaya transaksi dasar dibakar (sisanya untuk validator)",
        "strengths": [
            "Volume transaksi DEX harian, ekosistem DePIN, dan peluncuran token ritel tertinggi dengan biaya < $0.005.",
            "Imbal hasil staking sangat kompetitif (~6.8% APR ditambah MEV reward Jito).",
            "Peningkatan performa klien validator Firedancer memperkuat stabilitas dan throughput.",
        ],
        "risks": [
            "Tingkat inflasi emisi validator (~4.6%/tahun) lebih tinggi dibandingkan BTC dan ETH.",
            "Volatilitas tinggi akibat siklus spekulasi memecoin pada jaringan Solana.",
        ],
    },
    "BNB": {
        "name": "BNB (Build and Build)",
        "category": "Layer-1 Ecosystem & Exchange Utility",
        "consensus": "Proof-of-Staked-Authority (PoSA)",
        "circulating_supply_m": 142.48,
        "max_supply_m": 142.48,
        "supply_unit": "Juta BNB",
        "annual_inflation_pct": -2.50,
        "staking_apr_pct": 2.80,
        "staking_mechanism": "BNB Chain Staking + Launchpool / Megadrop Yield (~2.8% – 6% APR)",
        "burn_mechanism": "Quarterly Auto-Burn + BEP-95 Real-Time Gas Burn menuju target 100 Juta BNB",
        "strengths": [
            "Tokenomics deflasioner kuat melalui kuartalan Auto-Burn dan utilitas diskon biaya trading.",
            "Permintaan konsisten dari partisipasi Launchpool, Megadrop, dan ekosistem BNB Smart Chain.",
        ],
        "risks": [
            "Tingkat sentralisasi validator yang lebih tinggi dibanding Ethereum.",
            "Sensitif terhadap perkembangan regulasi bursa kripto global.",
        ],
    },
    "XRP": {
        "name": "XRP (Ripple)",
        "category": "Layer-1 • Cross-Border Settlement & RLUSD Ecosystem",
        "consensus": "XRP Ledger Consensus Protocol (Federated)",
        "circulating_supply_m": 57_800.0,
        "max_supply_m": 100_000.0,
        "supply_unit": "Juta XRP",
        "annual_inflation_pct": 3.20,
        "staking_apr_pct": 0.0,
        "staking_mechanism": "Tidak ada PoS Staking (AMM Liquidity Pool XRPL tersedia)",
        "burn_mechanism": "Biaya mikro setiap transaksi XRPL dihancurkan secara permanen",
        "strengths": [
            "Penyelesaian transaksi lintas negara dalam 3–5 detik dengan biaya mendekati nol.",
            "Ekspansi stablecoin institusional RLUSD dan kejelasan regulasi yang membaik.",
        ],
        "risks": [
            "Rasio FDV terhadap Market Cap cukup besar karena jadwal pelepasan escrow bulanan.",
        ],
    },
    "DOGE": {
        "name": "Dogecoin",
        "category": "Proof-of-Work Meme Coin & Payment Currency",
        "consensus": "Proof-of-Work (Scrypt • AuxPoW)",
        "circulating_supply_m": 148_100.0,
        "max_supply_m": None,
        "supply_unit": "Juta DOGE",
        "annual_inflation_pct": 3.38,
        "staking_apr_pct": 0.0,
        "staking_mechanism": "Proof-of-Work (Tidak ada native staking)",
        "burn_mechanism": "Emisi tetap 5 Miliar DOGE per tahun (persentase inflasi menurun setiap tahun)",
        "strengths": [
            "Likuiditas pasar dan komunitas global terbesar di kategori memecoin dengan distribusi 100% beredar.",
            "Tidak ada risiko unlock token VC karena seluruh suplai telah beredar di pasar.",
        ],
        "risks": [
            "Pergerakan harga sangat dipengaruhi sentimen media sosial dan siklus minat ritel.",
        ],
    },
    "SUI": {
        "name": "Sui Network",
        "category": "Next-Gen Move Layer-1",
        "consensus": "Mysticeti DAG Consensus + Delegated PoS",
        "circulating_supply_m": 3_090.0,
        "max_supply_m": 10_000.0,
        "supply_unit": "Juta SUI",
        "annual_inflation_pct": 8.50,
        "staking_apr_pct": 3.50,
        "staking_mechanism": "Native SUI Staking & Liquid Staking (afSUI / haSUI ~3.5% APR)",
        "burn_mechanism": "Mekanisme Storage Fund mengunci sebagian SUI seiring pertumbuhan data on-chain",
        "strengths": [
            "Arsitektur berorientasi objek dengan bahasa Move memberikan finalitas sub-detik (<400ms).",
            "Pertumbuhan TVL DeFi dan adopsi gaming/konsumen yang sangat pesat.",
        ],
        "risks": [
            "Sekitar ~69% dari total suplai maksimum 10 miliar SUI masih dalam jadwal vesting/unlock bertahap.",
        ],
    },
    "ADA": {
        "name": "Cardano",
        "category": "Layer-1 • Peer-Reviewed Proof-of-Stake",
        "consensus": "Ouroboros Proof-of-Stake",
        "circulating_supply_m": 35_900.0,
        "max_supply_m": 45_000.0,
        "supply_unit": "Juta ADA",
        "annual_inflation_pct": 1.80,
        "staking_apr_pct": 3.20,
        "staking_mechanism": "Non-Custodial Liquid Staking tanpa periode penguncian (~3.2% APR)",
        "burn_mechanism": "Batas suplai maksimum 45 Miliar ADA",
        "strengths": [
            "Staking likuid langsung dari dompet tanpa risiko slashing dan hampir 80% suplai sudah beredar.",
        ],
        "risks": [
            "Adopsi TVL DeFi dan volume stablecoin relatif lebih lambat dibanding Solana dan Ethereum.",
        ],
    },
    "AVAX": {
        "name": "Avalanche",
        "category": "Layer-1 • Institutional Subnets & Gaming",
        "consensus": "Avalanche Snowman Proof-of-Stake",
        "circulating_supply_m": 412.0,
        "max_supply_m": 720.0,
        "supply_unit": "Juta AVAX",
        "annual_inflation_pct": 4.20,
        "staking_apr_pct": 7.20,
        "staking_mechanism": "Primary Network Validator & Delegator Staking (~7.2% APR)",
        "burn_mechanism": "100% dari seluruh biaya transaksi jaringan Avalanche dibakar secara permanen",
        "strengths": [
            "Arsitektur Subnet memudahkan institusi dan pengembang game meluncurkan blockchain khusus.",
            "Imbal hasil staking tinggi (~7.2% APR) dengan pembakaran 100% biaya transaksi.",
        ],
        "risks": [
            "Jadwal emisi dan unlock menuju batas maksimum 720 juta AVAX.",
        ],
    },
    "LINK": {
        "name": "Chainlink",
        "category": "Decentralized Oracle Network & CCIP Interoperability",
        "consensus": "DON (Decentralized Oracle Networks)",
        "circulating_supply_m": 638.10,
        "max_supply_m": 1_000.0,
        "supply_unit": "Juta LINK",
        "annual_inflation_pct": 3.50,
        "staking_apr_pct": 4.30,
        "staking_mechanism": "Chainlink Staking v0.2 (~4.3% APR)",
        "burn_mechanism": "Chainlink Economics 2.0 (pembayaran biaya protokol dikonversi ke LINK)",
        "strengths": [
            "Infrastruktur oracle standar industri untuk DeFi dan interoperabilitas perbankan global (SWIFT / CCIP).",
        ],
        "risks": [
            "Sekitar ~36% suplai masih berada di cadangan pengembangan ekosistem.",
        ],
    },
    "TON": {
        "name": "Toncoin",
        "category": "Layer-1 • Telegram SuperApp Ecosystem",
        "consensus": "Catchain Proof-of-Stake",
        "circulating_supply_m": 2_495.0,
        "max_supply_m": 5_120.0,
        "supply_unit": "Juta TON",
        "annual_inflation_pct": 0.60,
        "staking_apr_pct": 3.80,
        "staking_mechanism": "TON Nominator Pools & Liquid Staking (tsTON ~3.8% APR)",
        "burn_mechanism": "50% dari seluruh biaya transaksi jaringan TON dibakar",
        "strengths": [
            "Integrasi eksklusif dengan lebih dari 950 juta pengguna aktif bulanan aplikasi Telegram.",
        ],
        "risks": [
            "Konsentrasi kepemilikan koin pada dompet penambang awal dan ketergantungan pada ekosistem Telegram.",
        ],
    },
    "TRX": {
        "name": "TRON",
        "category": "Layer-1 • Global USDT Stablecoin Settlement",
        "consensus": "Delegated Proof-of-Stake (DPoS)",
        "circulating_supply_m": 86_100.0,
        "max_supply_m": 86_100.0,
        "supply_unit": "Juta TRX",
        "annual_inflation_pct": -1.80,
        "staking_apr_pct": 4.50,
        "staking_mechanism": "TRON Stake 2.0 (Energy/Bandwidth + Voting Reward ~4.5% APR)",
        "burn_mechanism": "Deflasioner bersih — pembakaran TRX untuk biaya Energy transfer USDT melampaui emisi blok",
        "strengths": [
            "Jaringan penyelesaian transfer USDT terbesar di pasar negara berkembang dengan suplai deflasioner bersih.",
        ],
        "risks": [
            "Risiko regulasi terkait penggunaan stablecoin lintas yurisdiksi.",
        ],
    },
    "PEPE": {
        "name": "Pepe",
        "category": "Ethereum ERC-20 Meme Asset",
        "consensus": "ERC-20 Token (Ethereum)",
        "circulating_supply_m": 420_690_000.0,
        "max_supply_m": 420_690_000.0,
        "supply_unit": "Juta PEPE",
        "annual_inflation_pct": 0.0,
        "staking_apr_pct": 0.0,
        "staking_mechanism": "Tidak ada staking protokol (100% suplai beredar)",
        "burn_mechanism": "100% Circulating Supply (Zero Tax, LP Burned)",
        "strengths": [
            "100% suplai sudah beredar tanpa risiko unlock tim/VC dan likuiditas bursa Tier-1 sangat dalam.",
        ],
        "risks": [
            "Aset murni berbasis komunitas/atensi dengan volatilitas harian sangat tinggi.",
        ],
    },
    "BONK": {
        "name": "Bonk",
        "category": "Solana Community Meme Coin",
        "consensus": "SPL Token (Solana)",
        "circulating_supply_m": 77_300_000.0,
        "max_supply_m": 88_800_000.0,
        "supply_unit": "Juta BONK",
        "annual_inflation_pct": 0.0,
        "staking_apr_pct": 0.0,
        "staking_mechanism": "BONK Rewards Locking (ekosistem BONKbot)",
        "burn_mechanism": "Pembakaran rutin dari pendapatan biaya transaksi BONKbot & acara BURNmas",
        "strengths": [
            "Terintegrasi luas di ekosistem DeFi Solana dengan mekanisme beli-dan-bakar nyata dari BONKbot.",
        ],
        "risks": [
            "Beta tinggi terhadap fluktuasi harga SOL dan siklus memecoin.",
        ],
    },
}

_CRYPTO_CACHE: dict[str, dict[str, Any]] = {}
_CRYPTO_TTL_SEC = 90


def _format_crypto_price_usd(price: float) -> float:
    if not _is_valid_num(price) or price <= 0:
        return 0.0
    if price >= 100:
        return round(float(price), 2)
    if price >= 1:
        return round(float(price), 4)
    if price >= 0.01:
        return round(float(price), 6)
    return round(float(price), 8)


def _normalize_crypto_symbol(raw_query: str) -> tuple[str, str]:
    """Return (yahoo_symbol, clean_code)."""
    q = (raw_query or "BTC").strip().upper()
    for suffix in ("-USD", "/USD", "USDT", "/USDT", "-IDR", "/IDR"):
        if q.endswith(suffix) and len(q) > len(suffix):
            q = q[: -len(suffix)]
            break
    q = "".join(ch for ch in q if ch.isalnum()) or "BTC"
    # Note: PEPE and BONK on Yahoo Finance can be PEPE24478-USD or PEPE-USD; we handle fallback automatically
    return f"{q}-USD", q


def get_crypto_market_pulse(usd_idr: float, force_refresh: bool = False) -> dict[str, Any]:
    """Fetch live BTC, ETH, and SOL prices & 24h changes for the top Crypto Market Pulse banner."""
    now_ts = time.time()
    cache_key = "__CRYPTO_MARKET_PULSE__"
    if not force_refresh and cache_key in _CRYPTO_CACHE:
        cached = _CRYPTO_CACHE[cache_key]
        if now_ts - cached["ts"] < _CRYPTO_TTL_SEC:
            return cached["data"]

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
    }

    benchmarks = {}
    defaults = {
        "BTC": {"price_usd": 88500.0, "change_pct": 1.25},
        "ETH": {"price_usd": 2450.0, "change_pct": 0.85},
        "SOL": {"price_usd": 175.0, "change_pct": 2.40},
    }

    with httpx.Client(timeout=6.0, follow_redirects=True, headers=headers) as client:
        for code in ("BTC", "ETH", "SOL"):
            try:
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{code}-USD?range=5d&interval=1d"
                resp = client.get(url)
                if resp.status_code == 200:
                    res = resp.json()["chart"]["result"][0]
                    meta = res.get("meta", {})
                    quote = (res.get("indicators", {}).get("quote") or [{}])[0]
                    closes = [float(c) for c in (quote.get("close") or []) if _is_valid_num(c)]
                    px = float(meta.get("regularMarketPrice") or (closes[-1] if closes else defaults[code]["price_usd"]))
                    prev = float(closes[-2] if len(closes) >= 2 else (meta.get("chartPreviousClose") or px))
                    chg_pct = round(((px - prev) / prev) * 100.0, 2) if prev > 0 else 0.0
                    benchmarks[code] = {
                        "code": code,
                        "price_usd": _format_crypto_price_usd(px),
                        "price_idr": round(px * usd_idr),
                        "change_pct": chg_pct,
                    }
                    continue
            except Exception:
                pass
            d = defaults[code]
            benchmarks[code] = {
                "code": code,
                "price_usd": d["price_usd"],
                "price_idr": round(d["price_usd"] * usd_idr),
                "change_pct": d["change_pct"],
            }

    btc_chg = benchmarks["BTC"]["change_pct"]
    sol_chg = benchmarks["SOL"]["change_pct"]
    if btc_chg >= 1.5 and sol_chg >= 2.0:
        regime = "BULLISH RISK-ON (Momentum Pasar Kripto Kuat)"
    elif btc_chg < -2.0:
        regime = "RISK-OFF / KOREKSI (Waspadai Likuidasi Leverage)"
    elif sol_chg > btc_chg + 1.5:
        regime = "ROTASI ALTCOIN AKTIF (Altcoin Outperforming BTC)"
    else:
        regime = "KONSOLIDASI SEHAT (Pasar Kripto 24/7 Stabil)"

    pulse = {
        "btc": benchmarks["BTC"],
        "eth": benchmarks["ETH"],
        "sol": benchmarks["SOL"],
        "usd_idr": round(usd_idr, 2),
        "market_regime": regime,
        "market_status": "REAL-TIME • 24/7 GLOBAL CRYPTO FEED",
    }
    _CRYPTO_CACHE[cache_key] = {"ts": now_ts, "data": pulse}
    return pulse


def _build_crypto_timeframe_plan(
    tf_key: str,
    current_price_usd: float,
    usd_idr: float,
    closes: list[float],
    highs: list[float],
    lows: list[float],
    atr_pct: float,
    w52_low: float,
    w52_high: float,
    daily_major_bullish: bool = True,
) -> dict[str, Any]:
    tf_cfg = CRYPTO_TIMEFRAMES.get(tf_key, CRYPTO_TIMEFRAMES["1d"])
    lb = min(len(closes), tf_cfg["lookback_bars"])
    closed_series = closes[:-1] if len(closes) > 15 else closes
    sub_closes = closed_series[-max(15, lb):]
    sub_lows = lows[-max(5, lb):]

    fast_len = min(10 if tf_key in ("15m", "1h", "4h") else 20, len(sub_closes))
    mid_len = min(25 if tf_key in ("15m", "1h", "4h") else 50, len(sub_closes))
    ma_fast = sum(sub_closes[-fast_len:]) / max(1, fast_len)
    ma_mid = sum(sub_closes[-mid_len:]) / max(1, mid_len)
    rsi_tf = _compute_rsi(sub_closes, min(14, max(5, len(sub_closes) - 2)))
    _, _, macd_h = _compute_macd(closed_series[-90:])

    bull_pts = 0
    bear_pts = 0
    if current_price_usd >= ma_fast:
        bull_pts += 2
    else:
        bear_pts += 2
    if current_price_usd >= ma_mid:
        bull_pts += 2
    else:
        bear_pts += 2
    if macd_h >= 0:
        bull_pts += 1
    else:
        bear_pts += 1

    if 48 <= rsi_tf <= 70:
        bull_pts += 1
    elif rsi_tf > 76:
        bear_pts += 1
    elif rsi_tf < 33 and current_price_usd < ma_mid:
        bear_pts += 1

    tp1_target_pct = max(tf_cfg["min_tp1_pct"] / 100.0, atr_pct * tf_cfg["tp1_mult"])
    tp2_target_pct = max(tf_cfg["min_tp2_pct"] / 100.0, atr_pct * tf_cfg["tp2_mult"])
    sl_target_pct = max(tf_cfg["min_sl_pct"] / 100.0, atr_pct * tf_cfg["sl_mult"])

    low_window = min(sub_lows) if sub_lows else current_price_usd * (1.0 - sl_target_pct)
    support_1 = _format_crypto_price_usd(max(w52_low * 0.90, min(low_window, current_price_usd * (1.0 - sl_target_pct * 0.85))))
    support_2 = _format_crypto_price_usd(max(w52_low * 0.82, support_1 * (1.0 - sl_target_pct * 0.90)))

    entry_low = _format_crypto_price_usd(max(support_1, current_price_usd * (1.0 - sl_target_pct * 0.45)))
    entry_high = _format_crypto_price_usd(current_price_usd)
    if entry_low >= entry_high:
        entry_low = _format_crypto_price_usd(current_price_usd * 0.99)

    tp_1 = _format_crypto_price_usd(current_price_usd * (1.0 + tp1_target_pct))
    tp_2 = _format_crypto_price_usd(max(tp_1 * 1.02, current_price_usd * (1.0 + tp2_target_pct)))
    stop_loss = _format_crypto_price_usd(min(entry_low * 0.988, current_price_usd * (1.0 - sl_target_pct)))

    tp1_pct = round(((tp_1 - current_price_usd) / current_price_usd) * 100.0, 2) if current_price_usd > 0 else 0.0
    tp2_pct = round(((tp_2 - current_price_usd) / current_price_usd) * 100.0, 2) if current_price_usd > 0 else 0.0
    sl_pct = round(((stop_loss - current_price_usd) / current_price_usd) * 100.0, 2) if current_price_usd > 0 else 0.0

    net_tp1_pct = round(tp1_pct - CRYPTO_ROUNDTRIP_FEE_PCT, 2)
    net_tp2_pct = round(tp2_pct - CRYPTO_ROUNDTRIP_FEE_PCT, 2)
    net_sl_pct = round(abs(sl_pct) + CRYPTO_ROUNDTRIP_FEE_PCT, 2)

    risk_amt = max(1e-9, current_price_usd - stop_loss)
    reward_amt = max(1e-9, tp_2 - current_price_usd)
    rr_ratio = round(reward_amt / risk_amt, 2)
    net_rr_ratio = round(max(0.01, net_tp2_pct) / max(0.01, net_sl_pct), 2)

    htf_conflict = tf_key in ("15m", "1h", "4h") and (bull_pts > bear_pts) and (not daily_major_bullish)
    min_rr_req = float(tf_cfg.get("min_rr_threshold", 1.35))
    wait_reason: Optional[str] = None

    if net_rr_ratio < min_rr_req:
        signal_direction = "WAIT"
        trend_status = "R/R BELUM IDEAL"
        trend_badge = "WAIT"
        action_verdict = f"WAIT — TUNGGU PULLBACK KE SUPPORT ({tf_cfg['label'].upper()})"
        wait_reason = f"Rasio Reward/Risk bersih (1 : {net_rr_ratio}) di bawah batas minimum 1 : {min_rr_req}. Tunggu area beli dekat ${support_1:,.4f}."
    elif bull_pts >= bear_pts + 2 and rsi_tf <= 74:
        signal_direction = "LONG / BUY"
        trend_status = "BULLISH MOMENTUM"
        trend_badge = "BULLISH"
        action_verdict = f"LONG / BUY ON BREAKOUT & RETEST ({tf_cfg['label'].upper()})"
    elif bull_pts > bear_pts:
        signal_direction = "LONG / BUY" if not htf_conflict else "HOLD"
        trend_status = "BULLISH MODERAT"
        trend_badge = "BULLISH"
        action_verdict = f"ACCUMULATE / BUY ON DIP ({tf_cfg['label'].upper()})"
    elif bear_pts >= bull_pts + 2 and rsi_tf < 34:
        signal_direction = "WAIT"
        trend_status = "BEARISH • OVERSOLD"
        trend_badge = "REBOUND WATCH"
        action_verdict = f"WAIT — TUNGGU REVERSAL CANDLE ({tf_cfg['label'].upper()})"
        wait_reason = f"RSI-14 jenuh jual ({rsi_tf}) namun tren masih turun. Hindari menangkap pisau jatuh sebelum harga kembali di atas ${entry_high:,.4f}."
    elif bear_pts >= bull_pts + 2:
        signal_direction = "SHORT / REDUCE"
        trend_status = "BEARISH / DISTRIBUSI"
        trend_badge = "BEARISH"
        action_verdict = f"REDUCE SPOT / HINDARI LEVERAGE LONG ({tf_cfg['label'].upper()})"
        wait_reason = f"Harga bergerak di bawah MA-20 & MA-50 pada timeframe {tf_cfg['label']}."
    else:
        signal_direction = "HOLD"
        trend_status = "SIDEWAYS / RANGE"
        trend_badge = "NETRAL"
        action_verdict = f"HOLD / TRADING RANGE ({tf_cfg['label'].upper()})"

    now_wib = datetime.now(WIB_TZ)
    valid_until_wib = (now_wib + timedelta(hours=int(tf_cfg.get("validity_hours", 24)))).strftime("%d %b %Y, %H:%M WIB")

    return {
        "timeframe": tf_key,
        "timeframe_label": tf_cfg["label"],
        "strategy": tf_cfg["strategy"],
        "horizon": tf_cfg["horizon"],
        "hold_duration": tf_cfg["hold_duration"],
        "signal_direction": signal_direction,
        "trend_status": trend_status,
        "trend_badge": trend_badge,
        "action_verdict": action_verdict,
        "wait_reason": wait_reason,
        "entry_zone_low_usd": entry_low,
        "entry_zone_high_usd": entry_high,
        "entry_zone_low_idr": round(entry_low * usd_idr),
        "entry_zone_high_idr": round(entry_high * usd_idr),
        "support_1_usd": support_1,
        "support_2_usd": support_2,
        "support_1_idr": round(support_1 * usd_idr),
        "support_2_idr": round(support_2 * usd_idr),
        "tp_1_usd": tp_1,
        "tp_2_usd": tp_2,
        "tp_1_idr": round(tp_1 * usd_idr),
        "tp_2_idr": round(tp_2 * usd_idr),
        "tp_1_pct": tp1_pct,
        "tp_2_pct": tp2_pct,
        "net_tp_1_pct": net_tp1_pct,
        "net_tp_2_pct": net_tp2_pct,
        "stop_loss_usd": stop_loss,
        "stop_loss_idr": round(stop_loss * usd_idr),
        "stop_loss_pct": sl_pct,
        "net_stop_loss_pct": -net_sl_pct,
        "risk_reward_ratio": f"1 : {rr_ratio}",
        "net_risk_reward_ratio": f"1 : {net_rr_ratio}",
        "numeric_rr_ratio": rr_ratio,
        "entry_confirmation": (
            f"Candle {tf_cfg['label']} ditutup bertahan di atas ${entry_low:,.4f} dengan volume ≥ rata-rata 20 bar "
            "dan tidak ada lonjakan funding rate ekstrem."
        ),
        "higher_tf_alignment": (
            "⚠️ Counter-Trend terhadap grafik Harian (1D di bawah MA-50) — kurangi ukuran posisi."
            if htf_conflict
            else "✅ Searah dengan struktur tren utama."
        ),
        "valid_until": valid_until_wib,
    }


def calculate_crypto_position_risk(
    capital_idr: float,
    entry_price_usd: float,
    stop_loss_usd: float,
    target_price_usd: float,
    max_risk_pct: float = 2.0,
    investment_idr: Optional[float] = None,
    exchange_fee_pct: float = CRYPTO_EXCHANGE_FEE_PCT,
    tax_pct: float = CRYPTO_INDONESIA_TAX_PCT,
    usd_idr: Optional[float] = None,
) -> dict[str, Any]:
    """Calculate Crypto Spot/Position Sizing, Coin Quantity, Exchange Fees + Bappebti Tax, and Net P/L in IDR & USD."""
    for name, val in [
        ("Modal tersedia (capital_idr)", capital_idr),
        ("Harga Entry USD (entry_price_usd)", entry_price_usd),
        ("Stop Loss USD (stop_loss_usd)", stop_loss_usd),
        ("Target Profit USD (target_price_usd)", target_price_usd),
        ("Batas Risiko % (max_risk_pct)", max_risk_pct),
    ]:
        if not _is_valid_num(val) or float(val) <= 0:
            raise ValueError(f"{name} harus lebih besar dari 0.")

    if stop_loss_usd >= entry_price_usd:
        raise ValueError("Stop Loss harus berada di bawah Harga Entry untuk posisi Beli / Long.")
    if target_price_usd <= entry_price_usd:
        raise ValueError("Target Profit harus berada di atas Harga Entry.")

    fx = float(usd_idr) if (usd_idr and usd_idr > 0) else float(market.get_fx_rate().get("usd_idr") or 16300.0)
    fee_roundtrip_dec = ((float(exchange_fee_pct) * 2.0) + float(tax_pct)) / 100.0
    sl_drop_dec = (entry_price_usd - stop_loss_usd) / entry_price_usd
    total_loss_dec_per_unit = sl_drop_dec + fee_roundtrip_dec

    max_risk_budget_idr = capital_idr * (float(max_risk_pct) / 100.0)
    recommended_position_idr = min(capital_idr, max_risk_budget_idr / max(0.005, total_loss_dec_per_unit))

    allocated_idr = float(investment_idr) if (investment_idr and investment_idr > 0) else recommended_position_idr
    allocated_usd = allocated_idr / fx

    buy_fee_idr = round(allocated_idr * (float(exchange_fee_pct) / 100.0))
    net_invested_idr = allocated_idr - buy_fee_idr
    coin_quantity = (net_invested_idr / fx) / entry_price_usd

    gross_tp_idr = coin_quantity * target_price_usd * fx
    sell_fee_tax_tp_idr = round(gross_tp_idr * ((float(exchange_fee_pct) + float(tax_pct)) / 100.0))
    net_tp_proceeds_idr = gross_tp_idr - sell_fee_tax_tp_idr
    net_profit_tp_idr = round(net_tp_proceeds_idr - allocated_idr)
    net_profit_tp_pct = round((net_profit_tp_idr / allocated_idr) * 100.0, 2) if allocated_idr > 0 else 0.0

    gross_sl_idr = coin_quantity * stop_loss_usd * fx
    sell_fee_tax_sl_idr = round(gross_sl_idr * ((float(exchange_fee_pct) + float(tax_pct)) / 100.0))
    net_sl_proceeds_idr = gross_sl_idr - sell_fee_tax_sl_idr
    net_loss_sl_idr = round(allocated_idr - net_sl_proceeds_idr)
    risk_of_capital_pct = round((net_loss_sl_idr / capital_idr) * 100.0, 2) if capital_idr > 0 else 0.0

    net_rr = round(net_profit_tp_idr / max(1.0, net_loss_sl_idr), 2)

    return {
        "valid": True,
        "usd_idr": round(fx, 2),
        "inputs": {
            "capital_idr": round(capital_idr),
            "allocated_position_idr": round(allocated_idr),
            "allocated_position_usd": round(allocated_usd, 2),
            "entry_price_usd": entry_price_usd,
            "stop_loss_usd": stop_loss_usd,
            "target_price_usd": target_price_usd,
            "max_risk_pct": max_risk_pct,
        },
        "sizing": {
            "recommended_max_position_idr": round(recommended_position_idr),
            "recommended_max_position_usd": round(recommended_position_idr / fx, 2),
            "max_risk_budget_idr": round(max_risk_budget_idr),
            "coin_quantity": round(coin_quantity, 6),
            "exceeds_risk_budget": net_loss_sl_idr > (max_risk_budget_idr * 1.05),
        },
        "execution": {
            "estimated_buy_fee_idr": buy_fee_idr,
            "estimated_sell_fee_and_tax_idr": sell_fee_tax_tp_idr,
            "total_fee_and_tax_idr": buy_fee_idr + sell_fee_tax_tp_idr,
            "net_profit_tp_idr": net_profit_tp_idr,
            "net_profit_tp_usd": round(net_profit_tp_idr / fx, 2),
            "net_profit_tp_pct": net_profit_tp_pct,
            "net_loss_sl_idr": net_loss_sl_idr,
            "net_loss_sl_usd": round(net_loss_sl_idr / fx, 2),
            "risk_of_total_capital_pct": risk_of_capital_pct,
            "net_risk_reward_ratio": net_rr,
        },
    }


def analyze_crypto(
    query: str = "BTC",
    timeframe: str = "1d",
    force_refresh: bool = False,
) -> dict[str, Any]:
    yahoo_sym, clean_code = _normalize_crypto_symbol(query)
    tf_norm = (timeframe or "1d").strip().lower()
    if tf_norm not in CRYPTO_TIMEFRAMES:
        tf_norm = "1d"

    now_ts = time.time()
    usd_idr = float(market.get_fx_rate().get("usd_idr") or 16300.0)
    market_pulse = get_crypto_market_pulse(usd_idr, force_refresh=force_refresh)

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
    }

    # Candidate Yahoo symbols (some newer meme coins use specific tickers on Yahoo)
    candidate_symbols = [yahoo_sym]
    if clean_code == "PEPE":
        candidate_symbols = ["PEPE24478-USD", "PEPE-USD"]
    elif clean_code == "SUI":
        candidate_symbols = ["SUI20947-USD", "SUI-USD"]
    elif clean_code == "TON":
        candidate_symbols = ["TON11419-USD", "TON-USD"]

    raw = None
    raw_cache_key = f"__CRYPTO_RAW__{clean_code}"
    if not force_refresh and raw_cache_key in _CRYPTO_CACHE:
        if now_ts - _CRYPTO_CACHE[raw_cache_key]["ts"] < _CRYPTO_TTL_SEC:
            raw = _CRYPTO_CACHE[raw_cache_key]["raw"]
            yahoo_sym = _CRYPTO_CACHE[raw_cache_key]["yahoo_sym"]

    if raw is None:
        for cand_sym in candidate_symbols:
            for host in ("query1.finance.yahoo.com", "query2.finance.yahoo.com"):
                url = f"https://{host}/v8/finance/chart/{urllib.parse.quote(cand_sym)}?range=2y&interval=1d"
                try:
                    with httpx.Client(timeout=8.0, follow_redirects=True, headers=headers) as client:
                        resp = client.get(url)
                        if resp.status_code == 200:
                            res_list = resp.json().get("chart", {}).get("result")
                            if res_list and (res_list[0].get("timestamp") or []):
                                raw = resp.json()
                                yahoo_sym = cand_sym
                                _CRYPTO_CACHE[raw_cache_key] = {"ts": now_ts, "raw": raw, "yahoo_sym": yahoo_sym}
                                break
                except Exception:
                    continue
            if raw is not None:
                break

    if raw is None:
        raise ValueError(f"Aset kripto '{clean_code}' tidak ditemukan. Coba kode populer seperti BTC, ETH, SOL, BNB, XRP, DOGE, SUI, ADA, AVAX, LINK.")

    data = raw["chart"]["result"][0]
    meta = data.get("meta", {})
    timestamps = data.get("timestamp", []) or []
    quote = (data.get("indicators", {}).get("quote") or [{}])[0]

    candles, _ = _sanitize_and_adjust_candles(
        timestamps=timestamps,
        opens=quote.get("open", []) or [],
        highs=quote.get("high", []) or [],
        lows=quote.get("low", []) or [],
        closes=quote.get("close", []) or [],
        volumes=quote.get("volume", []) or [],
        splits_events={},
        interval="1d",
    )

    if not candles:
        raise ValueError(f"Data riwayat harga untuk '{clean_code}' kosong.")

    closes = [float(c["close"]) for c in candles]
    highs = [float(c["high"]) for c in candles]
    lows = [float(c["low"]) for c in candles]
    opens = [float(c["open"]) for c in candles]
    volumes = [int(c["volume"]) for c in candles]

    current_price_usd = _format_crypto_price_usd(float(meta.get("regularMarketPrice") or closes[-1]))
    prev_close_usd = _format_crypto_price_usd(float(closes[-2]) if len(closes) >= 2 else float(meta.get("chartPreviousClose") or current_price_usd))
    day_high_usd = _format_crypto_price_usd(float(meta.get("regularMarketDayHigh") or highs[-1]))
    day_low_usd = _format_crypto_price_usd(float(meta.get("regularMarketDayLow") or lows[-1]))
    day_change_usd = _format_crypto_price_usd(current_price_usd - prev_close_usd)
    day_change_pct = round(((current_price_usd - prev_close_usd) / prev_close_usd) * 100.0, 2) if prev_close_usd > 0 else 0.0

    current_price_idr = round(current_price_usd * usd_idr)

    def _pct_since(days_back: int) -> float:
        if len(closes) > days_back and closes[-1 - days_back] > 0:
            base = closes[-1 - days_back]
            return round(((current_price_usd - base) / base) * 100.0, 2)
        return 0.0

    perf_7d = _pct_since(7)
    perf_30d = _pct_since(30)
    perf_90d = _pct_since(90)
    perf_1y = _pct_since(min(365, len(closes) - 1))

    sma20 = _format_crypto_price_usd(_compute_sma(closes, 20) or (sum(closes[-min(20, len(closes)):]) / min(20, len(closes))))
    sma50 = _format_crypto_price_usd(_compute_sma(closes, 50) or (sum(closes[-min(50, len(closes)):]) / min(50, len(closes))))
    sma200 = _format_crypto_price_usd(_compute_sma(closes, 200) or (sum(closes[-min(200, len(closes)):]) / min(200, len(closes))))
    ema20 = _format_crypto_price_usd(_compute_ema(closes, 20) or sma20)
    ema50 = _format_crypto_price_usd(_compute_ema(closes, 50) or sma50)

    rsi14 = _compute_rsi(closes[-80:], 14)
    macd_val, macd_sig, macd_hist = _compute_macd(closes[-100:])
    bb = _compute_bollinger_bands(closes, 20, 2.0)
    atr14 = _format_crypto_price_usd(_compute_true_atr(highs[-30:], lows[-30:], closes[-30:], 14))
    atr_pct = max(0.02, min(0.12, (atr14 / current_price_usd) if current_price_usd > 0 else 0.04))

    w52_high_usd = _format_crypto_price_usd(float(meta.get("fiftyTwoWeekHigh") or max(highs[-365:])))
    w52_low_usd = _format_crypto_price_usd(float(meta.get("fiftyTwoWeekLow") or min(lows[-365:])))

    avg_vol_20d = int(sum(volumes[-20:]) / min(20, len(volumes))) if volumes else 0
    latest_vol_usd = volumes[-1] if volumes else 0
    vol_ratio = round(latest_vol_usd / avg_vol_20d, 2) if avg_vol_20d > 0 else 1.0
    vwap_val = _compute_vwap(candles[-24:], is_intraday=True)

    daily_major_bullish = current_price_usd >= sma50

    if rsi14 < 32:
        rsi_status = "OVERSOLD (Jenuh Jual • Pantau Pantulan Support)"
    elif rsi14 > 72:
        rsi_status = "OVERBOUGHT (Jenuh Beli • Waspada Long Squeeze / Koreksi)"
    elif rsi14 >= 52:
        rsi_status = "BULLISH MOMENTUM (Akumulasi Kuat)"
    else:
        rsi_status = "NETRAL / KONSOLIDASI"

    # Build Trading Plans for all 6 Crypto timeframes
    timeframes_plan: dict[str, dict[str, Any]] = {}
    for tf_k in CRYPTO_TIMEFRAMES:
        timeframes_plan[tf_k] = _build_crypto_timeframe_plan(
            tf_key=tf_k,
            current_price_usd=current_price_usd,
            usd_idr=usd_idr,
            closes=closes,
            highs=highs,
            lows=lows,
            atr_pct=atr_pct,
            w52_low=w52_low_usd,
            w52_high=w52_high_usd,
            daily_major_bullish=daily_major_bullish,
        )

    active_plan = timeframes_plan.get(tf_norm, timeframes_plan["1d"])

    # Tokenomics & Staking Intelligence
    tok_base = CRYPTO_TOKENOMICS_REGISTRY.get(clean_code)
    pop_match = next((p for p in POPULAR_CRYPTOS if p["code"] == clean_code), None)
    coin_name = (tok_base["name"] if tok_base else None) or (pop_match["name"] if pop_match else None) or meta.get("shortName") or clean_code
    category_label = (tok_base["category"] if tok_base else None) or (pop_match["category"] if pop_match else "Digital Crypto Asset")

    if tok_base:
        circ_m = float(tok_base["circulating_supply_m"])
        max_m = float(tok_base["max_supply_m"]) if tok_base.get("max_supply_m") else None
        mcap_usd_b = round((circ_m * current_price_usd) / 1000.0, 2)
        fdv_usd_b = round((max_m * current_price_usd) / 1000.0, 2) if max_m else mcap_usd_b
        fdv_mcap_ratio = round(fdv_usd_b / max(0.01, mcap_usd_b), 2)
        unlock_risk = (
            "RENDAH (Mayoritas Suplai Sudah Beredar)"
            if fdv_mcap_ratio <= 1.25
            else ("MODERAT (Pantau Jadwal Vesting Tahunan)" if fdv_mcap_ratio <= 2.0 else "TINGGI (Waspadai Dilusi Token Unlock VC/Ekosistem)")
        )
        tokenomics = {
            "status": "VALID",
            "consensus": tok_base["consensus"],
            "circulating_supply_m": circ_m,
            "max_supply_m": max_m,
            "supply_unit": tok_base["supply_unit"],
            "circulating_pct": round((circ_m / max_m) * 100.0, 2) if max_m else 100.0,
            "market_cap_usd_b": mcap_usd_b,
            "market_cap_idr_t": round((mcap_usd_b * usd_idr) / 1000.0, 2),
            "fdv_usd_b": fdv_usd_b,
            "fdv_to_mcap_ratio": fdv_mcap_ratio,
            "unlock_dilution_risk": unlock_risk,
            "annual_inflation_pct": tok_base["annual_inflation_pct"],
            "pays_staking_yield": float(tok_base["staking_apr_pct"]) > 0,
            "staking_apr_pct": float(tok_base["staking_apr_pct"]),
            "staking_mechanism": tok_base["staking_mechanism"],
            "burn_mechanism": tok_base["burn_mechanism"],
            "strengths": tok_base["strengths"],
            "risks": tok_base["risks"],
        }
    else:
        tokenomics = {
            "status": "PARTIAL",
            "consensus": "Public Blockchain / Smart Contract Token",
            "circulating_supply_m": None,
            "max_supply_m": None,
            "supply_unit": clean_code,
            "circulating_pct": None,
            "market_cap_usd_b": None,
            "market_cap_idr_t": None,
            "fdv_usd_b": None,
            "fdv_to_mcap_ratio": None,
            "unlock_dilution_risk": "UNAVAILABLE (Periksa jadwal unlock token sebelum investasi jangka panjang)",
            "annual_inflation_pct": None,
            "pays_staking_yield": False,
            "staking_apr_pct": 0.0,
            "staking_mechanism": "UNAVAILABLE",
            "burn_mechanism": "UNAVAILABLE",
            "strengths": ["Diperdagangkan secara global 24/7 dengan likuiditas pasar terbuka."],
            "risks": ["Perhatikan risiko volatilitas harga dan likuiditas pada pasangan perdagangan."],
        }

    # Default Risk Calculator (Rp 10.000.000 modal default)
    default_risk = calculate_crypto_position_risk(
        capital_idr=10_000_000.0,
        entry_price_usd=current_price_usd,
        stop_loss_usd=float(active_plan["stop_loss_usd"]),
        target_price_usd=float(active_plan["tp_2_usd"]),
        max_risk_pct=2.0,
        investment_idr=2_000_000.0,
        usd_idr=usd_idr,
    )

    # Fetch Indonesian Crypto News
    crypto_news = []
    try:
        feed = news_service.get_indonesian_news(category="crypto", query=clean_code, limit=6, force_refresh=False)
        crypto_news = feed.get("articles", []) or []
        if len(crypto_news) < 3:
            gen = news_service.get_indonesian_news(category="crypto", limit=6, force_refresh=False)
            seen = {a.get("url") for a in crypto_news}
            for item in gen.get("articles", []) or []:
                if item.get("url") not in seen:
                    crypto_news.append(item)
                if len(crypto_news) >= 6:
                    break
    except Exception:
        crypto_news = []

    summary_notes = [
        f"Harga {clean_code} saat ini ${current_price_usd:,.4f} (Rp {current_price_idr:,.0f}) berada {'di atas' if current_price_usd >= sma20 else 'di bawah'} SMA-20 (${sma20:,.4f}) dan {'di atas' if current_price_usd >= sma50 else 'di bawah'} SMA-50 (${sma50:,.4f}).",
        f"RSI-14 berada di level {rsi14} ({rsi_status}) dengan volatilitas harian ATR-14 sebesar {round(atr_pct * 100.0, 2)}%.",
        f"Sinyal Trading Plan ({active_plan['timeframe_label']}): {active_plan['signal_direction']} dengan Rasio Reward/Risk bersih {active_plan['net_risk_reward_ratio']} setelah biaya bursa & pajak kripto.",
    ]
    if tokenomics["pays_staking_yield"]:
        summary_notes.append(
            f"Aset ini menghasilkan imbal hasil Staking / Native Yield sekitar ~{tokenomics['staking_apr_pct']}% APR ({tokenomics['staking_mechanism']})."
        )

    return {
        "code": clean_code,
        "yahoo_symbol": yahoo_sym,
        "name": coin_name,
        "category": category_label,
        "usd_idr": round(usd_idr, 2),
        "current_price_usd": current_price_usd,
        "current_price_idr": current_price_idr,
        "prev_close_usd": prev_close_usd,
        "day_high_usd": day_high_usd,
        "day_low_usd": day_low_usd,
        "day_change_usd": day_change_usd,
        "day_change_pct": day_change_pct,
        "performance": {
            "7d_pct": perf_7d,
            "30d_pct": perf_30d,
            "90d_pct": perf_90d,
            "1y_pct": perf_1y,
        },
        "range_52w": {
            "low_usd": w52_low_usd,
            "high_usd": w52_high_usd,
            "low_idr": round(w52_low_usd * usd_idr),
            "high_idr": round(w52_high_usd * usd_idr),
            "position_pct": round(((current_price_usd - w52_low_usd) / max(1e-9, (w52_high_usd - w52_low_usd))) * 100.0, 1),
        },
        "selected_timeframe": tf_norm,
        "available_timeframes": [
            {
                "id": k,
                "label": v["label"],
                "strategy": v["strategy"],
                "horizon": v["horizon"],
                "hold_duration": v["hold_duration"],
            }
            for k, v in CRYPTO_TIMEFRAMES.items()
        ],
        "trading_plan": active_plan,
        "timeframes_plan": timeframes_plan,
        "technicals": {
            "rsi_14": rsi14,
            "rsi_status": rsi_status,
            "sma_20": sma20,
            "sma_50": sma50,
            "sma_200": sma200,
            "ema_20": ema20,
            "ema_50": ema50,
            "macd": macd_val,
            "macd_signal": macd_sig,
            "macd_histogram": macd_hist,
            "bollinger": bb,
            "atr_14_usd": atr14,
            "atr_pct": round(atr_pct * 100.0, 2),
            "vwap_usd": _format_crypto_price_usd(vwap_val) if vwap_val else current_price_usd,
            "volume_24h_usd": latest_vol_usd,
            "avg_volume_20d_usd": avg_vol_20d,
            "volume_ratio": vol_ratio,
        },
        "tokenomics": tokenomics,
        "risk_calculator_default": default_risk,
        "market_pulse": market_pulse,
        "news_articles": crypto_news,
        "summary_notes": summary_notes,
        "recent_candles": candles[-30:],
        "popular_cryptos": POPULAR_CRYPTOS,
        "updated_at": datetime.now(WIB_TZ).strftime("%d %b %Y, %H:%M:%S WIB"),
    }
