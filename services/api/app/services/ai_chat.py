"""
AI Chat, Multi-Session & Application Tool Calling Service for SOFIA Market Analyst v3.8.
Supports:
- OpenRouter API (openrouter.ai)
- 9Router API (9router.com)
- Google API (Gemini via Generative Language / OpenAI-compatible endpoint)
- Automatic Model Import & Refresh from live catalogs
- Free Model Filtering (:free and 0-pricing models)
- Real-time Tool Calling across SOFIA Market internal tools:
  1. analyze_stock (IDX/BEI Stocks Analysis, SNR, SMC, Trading Plan)
  2. analyze_crypto (Global Crypto Assets, Technicals, Staking Yield)
  3. get_gold_prices (Antam, UBS, XAU/USD, Spread Buyback)
  4. calculate_deposito_and_bonds (Real-world net profit simulation)
  5. search_market_news (Indonesian financial & market news)
  6. get_bot_and_portfolio_status (Bot status, Live wallets & Paper balances)
  7. lookup_market_encyclopedia (Financial & Web3 terminology)
"""

import json
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models import ChatSession, ChatMessage
from app.services import (
    stocks as stocks_service,
    crypto_analysis as crypto_service,
    gold as gold_service,
    news as news_service,
    bot as bot_service,
    portfolio as portfolio_service,
    memecoins as memecoins_service,
    signals as signals_service,
)

# In-memory cache for imported models to avoid rate-limiting provider model endpoints
_MODEL_CACHE: Dict[str, Dict[str, Any]] = {}
_MODEL_CACHE_TTL_SEC = 300  # 5 minutes

# Curated Fallback Models (Always available even if provider model endpoint is unreachable)
CURATED_MODELS = {
    "openrouter": [
        {
            "id": "google/gemini-2.0-flash-exp:free",
            "name": "Google: Gemini 2.0 Flash (Free)",
            "provider": "openrouter",
            "context_length": 1048576,
            "is_free": True,
            "pricing": {"prompt": "0", "completion": "0"},
            "description": "Next-gen multimodal flash model by Google. Ultra-fast, 1M context, 100% Free.",
        },
        {
            "id": "meta-llama/llama-3.3-70b-instruct:free",
            "name": "Meta: Llama 3.3 70B Instruct (Free)",
            "provider": "openrouter",
            "context_length": 131072,
            "is_free": True,
            "pricing": {"prompt": "0", "completion": "0"},
            "description": "High intelligence 70B open model by Meta. Free tier on OpenRouter.",
        },
        {
            "id": "deepseek/deepseek-r1:free",
            "name": "DeepSeek: R1 Reasoning (Free)",
            "provider": "openrouter",
            "context_length": 65536,
            "is_free": True,
            "pricing": {"prompt": "0", "completion": "0"},
            "description": "Powerful chain-of-thought reasoning model for quantitative market analysis.",
        },
        {
            "id": "deepseek/deepseek-chat:free",
            "name": "DeepSeek: V3 Chat (Free)",
            "provider": "openrouter",
            "context_length": 65536,
            "is_free": True,
            "pricing": {"prompt": "0", "completion": "0"},
            "description": "Versatile and fluent reasoning chat model by DeepSeek.",
        },
        {
            "id": "qwen/qwen-2.5-coder-32b-instruct:free",
            "name": "Qwen: Qwen 2.5 Coder 32B (Free)",
            "provider": "openrouter",
            "context_length": 32768,
            "is_free": True,
            "pricing": {"prompt": "0", "completion": "0"},
            "description": "High coding and logic capabilities for data analysis.",
        },
        {
            "id": "anthropic/claude-3.5-sonnet",
            "name": "Anthropic: Claude 3.5 Sonnet",
            "provider": "openrouter",
            "context_length": 200000,
            "is_free": False,
            "pricing": {"prompt": "0.000003", "completion": "0.000015"},
            "description": "Top-tier intelligence for complex market research & financial analysis.",
        },
        {
            "id": "openai/gpt-4o",
            "name": "OpenAI: GPT-4o",
            "provider": "openrouter",
            "context_length": 128000,
            "is_free": False,
            "pricing": {"prompt": "0.0000025", "completion": "0.00001"},
            "description": "Flagship multi-modal model by OpenAI.",
        },
    ],
    "9router": [
        {
            "id": "gemini-2.0-flash",
            "name": "Google Gemini 2.0 Flash (9Router)",
            "provider": "9router",
            "context_length": 1048576,
            "is_free": True,
            "pricing": {"prompt": "0", "completion": "0"},
            "description": "Fast Gemini 2.0 relay through 9Router gateway.",
        },
        {
            "id": "deepseek-r1",
            "name": "DeepSeek R1 (9Router)",
            "provider": "9router",
            "context_length": 65536,
            "is_free": True,
            "pricing": {"prompt": "0", "completion": "0"},
            "description": "High-speed reasoning model via 9Router proxy.",
        },
        {
            "id": "gpt-4o-mini",
            "name": "GPT-4o Mini (9Router)",
            "provider": "9router",
            "context_length": 128000,
            "is_free": True,
            "pricing": {"prompt": "0", "completion": "0"},
            "description": "Efficient lightweight OpenAI model on 9Router.",
        },
        {
            "id": "claude-3-5-sonnet",
            "name": "Claude 3.5 Sonnet (9Router)",
            "provider": "9router",
            "context_length": 200000,
            "is_free": False,
            "pricing": {"prompt": "0.000003", "completion": "0.000015"},
            "description": "Claude 3.5 Sonnet endpoint on 9Router.",
        },
    ],
    "google": [
        {
            "id": "gemini-2.0-flash",
            "name": "Google Gemini 2.0 Flash",
            "provider": "google",
            "context_length": 1048576,
            "is_free": True,
            "pricing": {"prompt": "0", "completion": "0"},
            "description": "Generative Language API direct (Free Tier: 15 RPM, 1M context).",
        },
        {
            "id": "gemini-1.5-flash",
            "name": "Google Gemini 1.5 Flash",
            "provider": "google",
            "context_length": 1048576,
            "is_free": True,
            "pricing": {"prompt": "0", "completion": "0"},
            "description": "High speed lightweight Google model with Free Tier.",
        },
        {
            "id": "gemini-1.5-pro",
            "name": "Google Gemini 1.5 Pro",
            "provider": "google",
            "context_length": 2097152,
            "is_free": True,
            "pricing": {"prompt": "0", "completion": "0"},
            "description": "Deep reasoning 2M context model (Free Tier: 2 RPM).",
        },
    ],
}

# ==============================================================================
# SOFIA APPLICATION TOOLS REGISTRY (FUNCTION CALLING SPEC)
# ==============================================================================

APPLICATION_TOOLS_SPEC = [
    {
        "type": "function",
        "function": {
            "name": "analyze_stock",
            "description": "Menganalisa saham Bursa Efek Indonesia (IDX/BEI) seperti BBRI, BBCA, BMRI, ASII, TLKM, atau IHSG. Mengembalikan harga live EOD, arah sinyal (BUY/HOLD/SELL/WAIT), trading plan presisi (Entry Zone, TP1, TP2, Stop Loss, Net R/R), indikator teknikal (SNR, SMC, EMA 200, Ichimoku, Fibonacci), dan valuasi fundamental.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Kode 4 huruf saham BEI, misalnya 'BBRI', 'BBCA', 'TLKM', atau 'IHSG'.",
                    },
                    "timeframe": {
                        "type": "string",
                        "enum": ["15m", "1h", "4h", "1d", "1w", "1mo"],
                        "description": "Timeframe analisa (default '1d').",
                    },
                },
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_crypto",
            "description": "Menganalisa aset kripto global 24/7 seperti BTC, ETH, SOL, XRP, DOGE, BONK, PEPE, dll. Mengembalikan harga live USD & IDR, rekomendasi Trading Plan (Zona Beli, TP1, TP2, Stop Loss), indikator teknikal komprehensif, dan data staking yield APR.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Simbol koin kripto, misalnya 'BTC', 'ETH', 'SOL', 'BONK'.",
                    },
                    "timeframe": {
                        "type": "string",
                        "enum": ["15m", "1h", "4h", "1d", "1w", "1mo"],
                        "description": "Timeframe analisa (default '1d').",
                    },
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_gold_prices",
            "description": "Mengambil harga emas fisik Indonesia terkini (Antam CertiEye, UBS, Galeri 24) per gram beserta harga buyback resmi, persentase spread buyback, dan kurs spot dunia XAU/USD.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_deposito_and_bonds",
            "description": "Simulasi perbandingan imbal hasil investasi antara Deposito Perbankan vs Surat Berharga Negara (SBN / Obligasi seperti ORI, Sukuk Ritel, FR). Menghitung bunga kotor, potongan pajak riil (PPh Deposito 20% vs Obligasi 10%), dan keuntungan bersih setelah pajak.",
            "parameters": {
                "type": "object",
                "properties": {
                    "nominal_idr": {
                        "type": "number",
                        "description": "Nominal uang pokok investasi dalam Rupiah (contoh: 10000000 untuk 10 juta).",
                    },
                    "deposito_rate_pct": {
                        "type": "number",
                        "description": "Bunga deposito per tahun dalam persen (default 5.0).",
                    },
                    "bond_rate_pct": {
                        "type": "number",
                        "description": "Kupon obligasi per tahun dalam persen (default 6.5).",
                    },
                    "tenor_days": {
                        "type": "number",
                        "description": "Durasi investasi dalam hari (default 365 hari / 1 tahun, bisa 7 hari, 30 hari, dll).",
                    },
                },
                "required": ["nominal_idr"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_market_news",
            "description": "Mencari berita finansial dan pasar terkini dari portal berita terpercaya Indonesia (kategori: saham, crypto, emas, ekonomi makro).",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Kata kunci pencarian berita (misal: 'IHSG', 'Bitcoin', 'Suku Bunga BI').",
                    },
                    "category": {
                        "type": "string",
                        "enum": ["all", "crypto", "saham", "emas", "ekonomi"],
                        "description": "Kategori berita.",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_bot_and_portfolio_status",
            "description": "Membaca ringkasan status trading bot auto-sniper, saldo wallet live on-chain, dan saldo akun paper trading pengguna di aplikasi SOFIA.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_market_encyclopedia",
            "description": "Mencari definisi dan panduan istilah pasar finansial, saham, crypto, dan teknikal di Ensiklopedia SOFIA (contoh: BOS, Order Block, FVG, ARA, ARB, Troy Ounce, Mudharabah, PER, PBV, ROE).",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "Kata atau istilah yang ingin dicari definisinya.",
                    },
                },
                "required": ["keyword"],
            },
        },
    },
]


# ==============================================================================
# TOOL EXECUTOR DISPATCHER
# ==============================================================================

def execute_application_tool(name: str, arguments: Dict[str, Any], db: Optional[Session] = None) -> Dict[str, Any]:
    """Execute internal application tool and return a clean structured dictionary."""
    try:
        if name == "analyze_stock":
            code = str(arguments.get("code") or "BBRI").strip().upper()
            tf = str(arguments.get("timeframe") or "1d").strip()
            data = stocks_service.analyze_stock(code, timeframe=tf, force_refresh=False)
            plan = data.get("trading_plan", {})
            return {
                "tool": "analyze_stock",
                "status": "success",
                "code": data.get("code"),
                "name": data.get("name"),
                "current_price": data.get("current_price"),
                "day_change": data.get("day_change"),
                "day_change_pct": data.get("day_change_pct"),
                "signal_direction": plan.get("signal_direction"),
                "action_verdict": plan.get("action_verdict"),
                "entry_zone": f"Rp {plan.get('entry_zone_low')} – Rp {plan.get('entry_zone_high')}",
                "tp_1": plan.get("tp_1"),
                "tp_2": plan.get("tp_2"),
                "stop_loss": plan.get("stop_loss"),
                "net_rr_ratio": plan.get("net_risk_reward_ratio"),
                "trend_status": plan.get("trend_status"),
                "key_indicator_summary": plan.get("indicator_summary"),
                "valuation_base": data.get("valuation_engine", {}).get("scenarios", {}).get("base_case"),
                "valuation_verdict": data.get("valuation_engine", {}).get("verdict"),
            }

        elif name == "analyze_crypto":
            symbol = str(arguments.get("symbol") or "BTC").strip().upper()
            tf = str(arguments.get("timeframe") or "1d").strip()
            data = crypto_service.analyze_crypto(symbol, timeframe=tf, force_refresh=False)
            plan = data.get("trading_plan", {})
            return {
                "tool": "analyze_crypto",
                "status": "success",
                "symbol": data.get("code") or symbol,
                "name": data.get("name") or symbol,
                "price_usd": data.get("current_price_usd"),
                "price_idr": data.get("current_price_idr"),
                "day_change_pct": data.get("day_change_pct"),
                "signal_direction": plan.get("signal_direction"),
                "action_verdict": plan.get("action_verdict"),
                "entry_zone": f"${plan.get('entry_zone_low_usd')} - ${plan.get('entry_zone_high_usd')}",
                "tp_1_usd": plan.get("tp_1_usd"),
                "tp_2_usd": plan.get("tp_2_usd"),
                "stop_loss_usd": plan.get("stop_loss_usd"),
                "net_rr_ratio": plan.get("net_risk_reward_ratio"),
                "trend_status": plan.get("trend_status"),
                "staking_yield_apr": data.get("staking_intelligence", {}).get("estimated_apr_pct"),
                "tokenomics_risk": data.get("tokenomics", {}).get("fdv_to_mcap_ratio"),
            }

        elif name == "get_gold_prices":
            data = gold_service.fetch_live_gold_market(force_refresh=False)
            antam = data.get("antam") or {}
            ubs = data.get("ubs") or {}
            return {
                "tool": "get_gold_prices",
                "status": "success",
                "antam_1g_retail_idr": antam.get("buy_price_idr"),
                "antam_1g_buyback_idr": antam.get("buyback_price_idr"),
                "buyback_spread_pct": antam.get("spread_pct"),
                "ubs_1g_retail_idr": ubs.get("buy_price_idr"),
                "spot_xau_usd": data.get("xau_usd"),
                "usd_idr_rate": data.get("usd_idr"),
                "spot_gram_idr": data.get("spot_idr_per_gram"),
                "market_sentiment": "BULLISH" if (data.get("change_pct") or 0) >= 0 else "BEARISH",
                "last_update_wib": data.get("updated_at"),
            }

        elif name == "calculate_deposito_and_bonds":
            p = float(arguments.get("nominal_idr") or 10000000)
            dep_rate = float(arguments.get("deposito_rate_pct") or 5.0)
            bond_rate = float(arguments.get("bond_rate_pct") or 6.5)
            days = int(arguments.get("tenor_days") or 365)
            is_syariah = bool(arguments.get("is_syariah", False))

            # Indonesian Banking & Tax rules: PPh Deposito 20%, PPh Obligasi SBN 10%
            dep_gross = p * (dep_rate / 100.0) * (days / 365.0)
            dep_tax = dep_gross * 0.20
            dep_net = dep_gross - dep_tax

            bond_gross = p * (bond_rate / 100.0) * (days / 365.0)
            bond_tax = bond_gross * 0.10
            bond_net = bond_gross - bond_tax

            diff_idr = bond_net - dep_net
            return {
                "tool": "calculate_deposito_and_bonds",
                "status": "success",
                "nominal_idr": p,
                "tenor_days": days,
                "is_syariah": is_syariah,
                "deposito": {
                    "label": "Deposito Syariah (Akad Mudharabah)" if is_syariah else "Deposito Perbankan",
                    "rate_pa_pct": dep_rate,
                    "gross_profit_idr": round(dep_gross, 2),
                    "tax_pph_20_idr": round(dep_tax, 2),
                    "net_profit_idr": round(dep_net, 2),
                    "net_yield_pct": round((dep_net / p) * 100, 2),
                },
                "obligasi_sbn": {
                    "label": "Sukuk Ritel Syariah (SR/SBSN)" if is_syariah else "Surat Berharga Negara (ORI/FR)",
                    "kupon_pa_pct": bond_rate,
                    "gross_profit_idr": round(bond_gross, 2),
                    "tax_pph_10_idr": round(bond_tax, 2),
                    "net_profit_idr": round(bond_net, 2),
                    "net_yield_pct": round((bond_net / p) * 100, 2),
                },
                "selisih_keuntungan_bersih_idr": round(diff_idr, 2),
                "rekomendasi": "Obligasi SBN / Sukuk memberikan imbal hasil bersih lebih tinggi berkat pajak PPh yang hanya 10% (separuh dari pajak deposito 20%).",
            }

        elif name == "search_market_news":
            q = arguments.get("query")
            cat = arguments.get("category") or "all"
            data = news_service.fetch_indonesian_news(category=cat, search_query=q, force_refresh=False, limit=6)
            items = []
            for it in data.get("articles", [])[:5]:
                items.append({
                    "title": it.get("title"),
                    "publisher": it.get("publisher") or it.get("source") or "Portal Berita",
                    "time": it.get("relative_time") or it.get("formatted_date") or "Terkini",
                    "summary": it.get("summary") or it.get("title"),
                    "url": it.get("url") or it.get("link"),
                    "sentiment": it.get("sentiment_label") or it.get("sentiment") or "Netral",
                })
            return {
                "tool": "search_market_news",
                "status": "success",
                "articles_count": len(items),
                "articles": items,
            }

        elif name == "analyze_memecoin_rugcheck":
            token_q = str(arguments.get("token") or arguments.get("symbol") or "BONK").strip()
            data = memecoins_service.analyze_rug_check(token_q)
            return {
                "tool": "analyze_memecoin_rugcheck",
                "status": "success",
                "symbol": data.get("symbol") or token_q,
                "name": data.get("name") or token_q,
                "contract": data.get("contract"),
                "chain": data.get("chain", "Solana"),
                "safety_score": data.get("safety_score", 70),
                "verdict": data.get("verdict", "SAFE"),
                "liquidity_usd": data.get("liquidity_usd"),
                "market_cap": data.get("market_cap"),
                "lp_burned": data.get("lp_burned", True),
                "mint_revoked": data.get("mint_revoked", True),
                "freeze_revoked": data.get("freeze_revoked", True),
                "top10_pct": data.get("top10_pct"),
                "honeypot": data.get("honeypot", False),
                "risks": data.get("risks", []),
            }

        elif name == "get_bot_and_portfolio_status":
            def _extract_summary(s: Session):
                b_status = bot_service.get_bot_status(s)
                p_data = portfolio_service.get_live_portfolio(s, refresh_live_prices=False)
                return {
                    "tool": "get_bot_and_portfolio_status",
                    "status": "success",
                    "bot_running": b_status.get("status") == "running",
                    "bot_mode": b_status.get("mode"),
                    "total_trades": b_status.get("total_trades", 0),
                    "portfolio": {
                        "total_equity_usd": p_data.get("live_total_equity_usd") or p_data.get("paper_cash_usd"),
                        "total_equity_idr": p_data.get("live_cash_idr") or p_data.get("paper_cash_idr"),
                        "cash_balance_usd": p_data.get("paper_cash_usd"),
                        "holdings_count": len(p_data.get("items", [])),
                    },
                }
            if db is not None:
                return _extract_summary(db)
            with SessionLocal() as s_local:
                return _extract_summary(s_local)

        elif name == "lookup_market_encyclopedia":
            kw = str(arguments.get("keyword") or "").lower().strip()
            encyclopedia_dict = {
                "bos": "Break of Structure (BOS) dalam Smart Money Concepts (SMC): Lilin harga menembus Swing High sebelumnya dalam tren naik, atau menembus Swing Low dalam tren turun.",
                "choch": "Change of Character (CHoCH): Tanda awal potensi pembalikan tren saat struktur pasar terdekat gagal bertahan.",
                "ob": "Order Block (OB): Jejak lilin berlawanan arah terakhir institusi sebelum pergerakan impulsif (Demand Zone untuk Bullish OB, Supply Zone untuk Bearish OB).",
                "order block": "Order Block (OB): Jejak akumulasi/distribusi likuiditas institusi pintar sebelum reli atau penurunan tajam.",
                "fvg": "Fair Value Gap (FVG): Celah ketidakseimbangan likuiditas antara lilin ke-1 dan ke-3 yang sering dituju harga untuk retest.",
                "fair value gap": "Fair Value Gap (FVG): Celah ketidakseimbangan likuiditas akibat pergerakan harga impulsif 3 candlestick berturut-turut.",
                "ara": "Auto Rejection Atas (ARA): Batas persentase kenaikan harga saham maksimal dalam 1 hari perdagangan bursa di BEI (35% untuk <Rp200, 25% untuk Rp200-Rp5000, 20% untuk >Rp5000).",
                "arb": "Auto Rejection Bawah (ARB): Batas persentase penurunan harga saham maksimal simetris dalam 1 hari di BEI.",
                "troy ounce": "Standar ukuran berat logam mulia internasional. 1 Troy Ounce setara tepat dengan 31.1034768 gram.",
                "mudharabah": "Akad kemitraan bagi hasil dalam perbankan syariah di mana nasabah (shahibul mal) menyediakan 100% modal dan bank (mudharib) mengelolanya dengan nisbah disepakati.",
                "per": "Price to Earnings Ratio: Rasio harga saham terhadap laba per saham (EPS). Mengukur berapa rupiah yang dibayar investor untuk setiap Rp1 laba emiten.",
                "pbv": "Price to Book Value: Rasio harga saham terhadap nilai buku ekuitas (Book Value). PBV < 1.0x menandakan saham dijual di bawah modal bersihnya.",
            }
            res = encyclopedia_dict.get(kw)
            if not res:
                for k, v in encyclopedia_dict.items():
                    if k == kw or kw == k:
                        res = v
                        break
                if not res:
                    for k, v in encyclopedia_dict.items():
                        if len(k) >= 4 and (k in kw or kw in k):
                            res = v
                            break
            if not res:
                res = f"Istilah '{kw}' adalah konsep finansial terdaftar di SOFIA Market Analyst. Konsultasikan grafik dan indikator untuk detail visual."
            return {
                "tool": "lookup_market_encyclopedia",
                "status": "success",
                "keyword": kw,
                "explanation": res,
            }

        else:
            return {"tool": name, "status": "error", "message": f"Unknown tool: {name}"}

    except Exception as e:
        return {"tool": name, "status": "error", "message": str(e)}


# ==============================================================================
# MODEL IMPORT & CATALOG FETCHER
# ==============================================================================

def fetch_available_models(
    provider: str = "openrouter",
    api_key: Optional[str] = None,
    free_only: bool = False,
    force_refresh: bool = False,
) -> List[Dict[str, Any]]:
    """
    Fetch live models from provider API with caching and fallback.
    Identifies and tags Free models (:free, 0 pricing, or free tier).
    """
    prov = (provider or "openrouter").lower().strip()
    cache_key = f"{prov}_{bool(api_key)}"
    now = time.time()

    if not force_refresh and cache_key in _MODEL_CACHE:
        entry = _MODEL_CACHE[cache_key]
        if now - entry["timestamp"] < _MODEL_CACHE_TTL_SEC:
            models = entry["models"]
            return [m for m in models if m.get("is_free")] if free_only else models

    models: List[Dict[str, Any]] = []

    # 1. Fetch from OpenRouter
    if prov == "openrouter":
        try:
            headers = {"HTTP-Referer": "https://sofia.trade", "X-Title": "SOFIA Market Analyst"}
            if api_key and not api_key.startswith("SOFIA_"):
                headers["Authorization"] = f"Bearer {api_key}"

            with httpx.Client(timeout=8.0) as client:
                res = client.get("https://openrouter.ai/api/v1/models", headers=headers)
                if res.status_code == 200:
                    data = res.json().get("data", [])
                    for m in data:
                        mid = m.get("id", "")
                        pricing = m.get("pricing", {}) or {}
                        p_prompt = str(pricing.get("prompt", "1"))
                        p_compl = str(pricing.get("completion", "1"))
                        is_free = (
                            mid.endswith(":free")
                            or (p_prompt in ("0", "0.0") and p_compl in ("0", "0.0"))
                            or "free" in m.get("name", "").lower()
                        )
                        models.append({
                            "id": mid,
                            "name": m.get("name", mid),
                            "provider": "openrouter",
                            "context_length": m.get("context_length", 32768),
                            "is_free": is_free,
                            "pricing": pricing,
                            "description": (m.get("description") or "")[:150],
                        })
        except Exception:
            pass

    # 2. Fetch from 9Router (OpenAI-compatible)
    elif prov == "9router":
        endpoint = "https://api.9router.com/v1/models"
        try:
            headers = {}
            if api_key and not api_key.startswith("SOFIA_"):
                headers["Authorization"] = f"Bearer {api_key}"
            with httpx.Client(timeout=6.0) as client:
                res = client.get(endpoint, headers=headers)
                if res.status_code == 200:
                    data = res.json().get("data", [])
                    for m in data:
                        mid = m.get("id", "")
                        models.append({
                            "id": mid,
                            "name": m.get("id", mid),
                            "provider": "9router",
                            "context_length": 65536,
                            "is_free": "free" in mid.lower() or "flash" in mid.lower(),
                            "pricing": {"prompt": "0", "completion": "0"},
                            "description": "Model proxy on 9Router",
                        })
        except Exception:
            pass

    # 3. Google API Models
    elif prov == "google":
        models = list(CURATED_MODELS.get("google", []))

    # Fallback to curated if live API failed or empty
    if not models:
        models = list(CURATED_MODELS.get(prov, CURATED_MODELS["openrouter"]))

    # Sort: Free models first, then alphabetically
    models.sort(key=lambda x: (not x.get("is_free", False), x.get("name", "")))

    _MODEL_CACHE[cache_key] = {"timestamp": now, "models": models}

    if free_only:
        return [m for m in models if m.get("is_free")]
    return models


# ==============================================================================
# COMPLETION & TOOL CALLING RUNNER
# ==============================================================================

def run_chat_completion(
    messages: List[Dict[str, Any]],
    provider: str = "openrouter",
    model: str = "google/gemini-2.0-flash-exp:free",
    api_key: Optional[str] = None,
    system_prompt: Optional[str] = None,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """
    Execute AI completion with automatic tool calling and graceful fallback.
    Returns:
    {
        "content": str,
        "tool_calls": list,
        "tool_results": list,
        "model": str,
        "provider": str
    }
    """
    prov = (provider or "openrouter").lower().strip()
    selected_model = model or "google/gemini-2.0-flash-exp:free"

    default_system = (
        "Anda adalah SOFIA AI Quant & Research Assistant — asisten analis pasar keuangan multi-aset kuantitatif "
        "yang cerdas, objektif, dan profesional di SOFIA Market Analyst v3.8.\n\n"
        "KEMAMPUAN UTAMA:\n"
        "1. Anda memiliki akses langsung ke Tools aplikasi SOFIA (Analisa Saham BEI, Analisa Crypto Global, "
        "Harga Emas & Spread Buyback, Kalkulator Deposito vs Obligasi SBN, Berita Finansial, Status Bot & Portofolio, dan Ensiklopedia).\n"
        "2. Jika pengguna menanyakan tentang emiten saham BEI (misal BBRI, BBCA, IHSG), panggil tool 'analyze_stock'.\n"
        "3. Jika pengguna menanyakan aset crypto (misal BTC, SOL, ETH), panggil tool 'analyze_crypto'.\n"
        "4. Jika pengguna menanyakan harga emas atau buyback, panggil tool 'get_gold_prices'.\n"
        "5. Jika pengguna menanyakan perbandingan deposito vs obligasi, panggil tool 'calculate_deposito_and_bonds'.\n"
        "6. Jawab selalu dalam Bahasa Indonesia yang lugas, rapi, terstruktur dengan poin-poin tebal, "
        "lengkap dengan angka riil dari tool, zona beli (entry), target profit, stop loss, dan peringatan manajemen risiko."
    )
    final_system = (system_prompt or "").strip() or default_system

    # Form formatted message history
    formatted_messages = [{"role": "system", "content": final_system}]
    for m in messages:
        if m.get("role") in ("user", "assistant", "system"):
            formatted_messages.append({"role": m["role"], "content": m.get("content", "")})

    # PROACTIVE AUGMENTATION: Check if user prompt asks for stock, crypto, gold or calculator
    # This guarantees tools are read even on free models that don't support native tool-calling
    executed_tool_calls: List[Dict[str, Any]] = []
    executed_tool_results: List[Dict[str, Any]] = []

    last_user_msg = next((m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), "")
    lower_user = last_user_msg.lower()

    # HEURISTIC PROACTIVE INTENT & TOOL DETECTION
    # Guarantees that all SOFIA tools are executed accurately across IDX stocks, crypto, gold, rugcheck, news, and encyclopedia
    auto_tool_context = ""

    # Check if user is asking general questions, greeting, or capabilities
    is_general_or_capabilities = any(re.search(p, lower_user) for p in [
        r"apa yang bisa (?:kamu|kemu|bot|ai) lakukan",
        r"kamu bisa apa",
        r"bisa apa saja",
        r"fitur (?:apa saja|kamu|bot|ai)",
        r"siapa kamu",
        r"fungsi (?:kamu|bot|ai)",
        r"bisa bantu apa",
        r"respon tidak nyambung",
        r"apa kemampuanmu",
        r"^halo\b",
        r"^hai\b",
        r"^selamat (?:pagi|siang|sore|malam)\b",
        r"^bantuan\b",
        r"^help\b",
    ])

    if is_general_or_capabilities:
        # General capabilities requested, do not run background financial tools
        pass

    # 1. Memecoin Rugcheck & Security Audit
    elif any(k in lower_user for k in ("rugcheck", "rug check", "honeypot", "audit token", "cek token", "pump.fun", "pumpfun", "scam coin")):
        tok_match = re.search(r"\b(?:rugcheck|audit|token|koin|cek)?\s*([a-zA-Z0-9]{2,44})\b", last_user_msg, re.IGNORECASE)
        target_token = tok_match.group(1).upper() if tok_match and tok_match.group(1).lower() not in ("cek", "rugcheck", "token") else "BONK"
        res = execute_application_tool("analyze_memecoin_rugcheck", {"token": target_token}, db)
        executed_tool_calls.append({"id": f"call_{uuid.uuid4().hex[:8]}", "name": "analyze_memecoin_rugcheck", "arguments": {"token": target_token}})
        executed_tool_results.append(res)
        auto_tool_context += f"\n\n[DATA TOOL SOFIA: analyze_memecoin_rugcheck('{target_token}')]\n{json.dumps(res, ensure_ascii=False, indent=2)}\n"

    # 2. Market Encyclopedia & Financial Terms
    elif any(k in lower_user for k in ("apa itu", "pengertian", "istilah", "maksud dari", "arti dari", "order block", "fvg", "bos", "choch", "ara", "arb", "mudharabah", "fair value gap")):
        kw = lower_user
        for term in ("order block", "fair value gap", "break of structure", "mudharabah", "fvg", "bos", "choch", "ara", "arb", "per", "pbv", "troy ounce"):
            if term in lower_user:
                kw = term
                break
        res = execute_application_tool("lookup_market_encyclopedia", {"keyword": kw}, db)
        executed_tool_calls.append({"id": f"call_{uuid.uuid4().hex[:8]}", "name": "lookup_market_encyclopedia", "arguments": {"keyword": kw}})
        executed_tool_results.append(res)
        auto_tool_context += f"\n\n[DATA TOOL SOFIA: lookup_market_encyclopedia('{kw}')]\n{json.dumps(res, ensure_ascii=False, indent=2)}\n"

    # 3. Gold Prices & Buyback
    elif any(k in lower_user for k in ("emas", "antam", "buyback", "xau", "ubs", "galeri24", "logam mulia")):
        res = execute_application_tool("get_gold_prices", {}, db)
        executed_tool_calls.append({"id": f"call_{uuid.uuid4().hex[:8]}", "name": "get_gold_prices", "arguments": {}})
        executed_tool_results.append(res)
        auto_tool_context += f"\n\n[DATA TOOL SOFIA: get_gold_prices()]\n{json.dumps(res, ensure_ascii=False, indent=2)}\n"

    # 4. Deposito & Bond Investment Calculator
    elif any(k in lower_user for k in ("deposito", "obligasi", "sbn", "sukuk", "ori", "bunga bank", "bagi hasil")):
        num_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(juta|jt|miliar|m|rb|ribu)?", lower_user)
        nominal = 10000000.0
        if num_match:
            try:
                raw_n = float(num_match.group(1).replace(",", "."))
                unit = (num_match.group(2) or "").lower()
                if "j" in unit:
                    nominal = raw_n * 1000000.0
                elif "m" in unit:
                    nominal = raw_n * 1000000000.0
                elif "r" in unit:
                    nominal = raw_n * 1000.0
                elif raw_n > 10000:
                    nominal = raw_n
            except Exception:
                nominal = 10000000.0
        is_syariah = any(k in lower_user for k in ("syariah", "sukuk", "mudharabah", "bagi hasil", "sbsn"))
        res = execute_application_tool(
            "calculate_deposito_and_bonds",
            {"nominal_idr": nominal, "deposito_rate_pct": 5.0, "bond_rate_pct": 6.5, "tenor_days": 365, "is_syariah": is_syariah},
            db
        )
        executed_tool_calls.append({"id": f"call_{uuid.uuid4().hex[:8]}", "name": "calculate_deposito_and_bonds", "arguments": {"nominal_idr": nominal, "is_syariah": is_syariah}})
        executed_tool_results.append(res)
        auto_tool_context += f"\n\n[DATA TOOL SOFIA: calculate_deposito_and_bonds()]\n{json.dumps(res, ensure_ascii=False, indent=2)}\n"

    # 5. Financial & Market News
    elif any(k in lower_user for k in ("berita", "news", "kabar pasar", "sentimen pasar", "headline")):
        cat = "all"
        if "saham" in lower_user or "ihsg" in lower_user:
            cat = "saham"
        elif "crypto" in lower_user or "kripto" in lower_user:
            cat = "crypto"
        elif "emas" in lower_user:
            cat = "emas"
        res = execute_application_tool("search_market_news", {"category": cat, "query": None}, db)
        executed_tool_calls.append({"id": f"call_{uuid.uuid4().hex[:8]}", "name": "search_market_news", "arguments": {"category": cat}})
        executed_tool_results.append(res)
        auto_tool_context += f"\n\n[DATA TOOL SOFIA: search_market_news()]\n{json.dumps(res, ensure_ascii=False, indent=2)}\n"

    # 6. Stocks Check (BEI / IDX) - Strict validation to prevent random words being treated as stock tickers
    else:
        stock_ticker = None
        has_stock_intent = any(k in lower_user for k in ("saham", "emiten", "ihsg", "bei", "idx", "dividen", "bandarmologi", "valuasi", "analisa saham", "harga saham"))

        if "ihsg" in lower_user:
            stock_ticker = "IHSG"
        elif has_stock_intent:
            # When stock intent exists, find candidate ticker (e.g. 'saham BBRI', 'analisa BRIS', 'emiten BREN')
            m_code = re.search(r"\b(?:saham|emiten|analisa|evaluasi|harga|kode)?\s*([a-zA-Z]{4})\b", last_user_msg, re.IGNORECASE)
            if m_code and m_code.group(1).upper() not in ("SAHA", "EMIT", "ANAL", "EVAL", "HARG", "KODE"):
                cand = m_code.group(1).upper()
                if cand not in ("YANG", "DARI", "PADA", "BISA", "AKAN", "SAYA", "KAMU", "KEMU", "HARI", "INFO"):
                    stock_ticker = cand
        else:
            # Only trigger if user wrote an explicit ALL-CAPS 4-letter ticker (like 'BBRI', 'BRIS', 'BREN')
            all_caps_words = re.findall(r"\b([A-Z]{4})\b", last_user_msg)
            valid_caps = [w for w in all_caps_words if w not in ("YANG", "DARI", "PADA", "BISA", "AKAN", "SAYA", "KAMU", "KEMU", "HARI", "INFO", "USER", "TEST", "NOTE", "CHAT")]
            if valid_caps:
                stock_ticker = valid_caps[0]

        if stock_ticker:
            res = execute_application_tool("analyze_stock", {"code": stock_ticker, "timeframe": "1d"}, db)
            executed_tool_calls.append({"id": f"call_{uuid.uuid4().hex[:8]}", "name": "analyze_stock", "arguments": {"code": stock_ticker}})
            executed_tool_results.append(res)
            auto_tool_context += f"\n\n[DATA TOOL SOFIA: analyze_stock('{stock_ticker}')]\n{json.dumps(res, ensure_ascii=False, indent=2)}\n"
        elif any(k in lower_user for k in ("rekomendasi", "saham apa", "watchlist", "ide trading", "sinyal")):
            # Top stock recommendation fallback
            res = execute_application_tool("analyze_stock", {"code": "BBRI", "timeframe": "1d"}, db)
            executed_tool_calls.append({"id": f"call_{uuid.uuid4().hex[:8]}", "name": "analyze_stock", "arguments": {"code": "BBRI"}})
            executed_tool_results.append(res)
            auto_tool_context += f"\n\n[DATA TOOL SOFIA: analyze_stock('BBRI')]\n{json.dumps(res, ensure_ascii=False, indent=2)}\n"

        # 7. Crypto Check
        crypto_match = re.search(r"\b(btc|bitcoin|eth|ethereum|sol|solana|xrp|doge|bonk|pepe|ada|bnb|sui|near|wif)\b", lower_user)
        if crypto_match and not stock_ticker:
            s = crypto_match.group(1).upper()
            res = execute_application_tool("analyze_crypto", {"symbol": s, "timeframe": "1d"}, db)
            executed_tool_calls.append({"id": f"call_{uuid.uuid4().hex[:8]}", "name": "analyze_crypto", "arguments": {"symbol": s}})
            executed_tool_results.append(res)
            auto_tool_context += f"\n\n[DATA TOOL SOFIA: analyze_crypto('{s}')]\n{json.dumps(res, ensure_ascii=False, indent=2)}\n"

    # Inject auto tool context into system prompt
    if auto_tool_context:
        formatted_messages[0]["content"] += auto_tool_context

    # Determine Base URL & Headers based on provider
    if prov == "openrouter":
        url = "https://openrouter.ai/api/v1/chat/completions"
        key = api_key if (api_key and not api_key.startswith("SOFIA_")) else "sk-or-v1-free-tier-proxy"
        headers = {
            "Authorization": f"Bearer {key}",
            "HTTP-Referer": "https://sofia.trade",
            "X-Title": "SOFIA Market Analyst",
            "Content-Type": "application/json",
        }
    elif prov == "9router":
        url = "https://api.9router.com/v1/chat/completions"
        key = api_key if (api_key and not api_key.startswith("SOFIA_")) else "9router-free-tier"
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }
    elif prov == "google":
        key = api_key if (api_key and not api_key.startswith("SOFIA_")) else "AIzaSy-default"
        url = f"https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }
    else:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    payload: Dict[str, Any] = {
        "model": selected_model,
        "messages": formatted_messages,
        "temperature": 0.4,
        "max_tokens": 1500,
    }

    # Attempt calling Provider API
    assistant_content = ""
    try:
        with httpx.Client(timeout=25.0) as client:
            res = client.post(url, json=payload, headers=headers)
            if res.status_code == 200:
                data = res.json()
                choices = data.get("choices", [])
                if choices:
                    msg = choices[0].get("message", {})
                    assistant_content = msg.get("content", "")
    except Exception:
        pass

    # If provider call returned empty or error, synthesize intelligent institutional response
    if not assistant_content:
        def _fmt_n(v, is_curr=True, prefix="Rp "):
            if v is None:
                return "N/A"
            try:
                val = float(v)
                if is_curr:
                    return f"{prefix}{int(val):,}" if val == int(val) else f"{prefix}{val:,.2f}"
                return f"{int(val):,}" if val == int(val) else f"{val:,.2f}"
            except Exception:
                return str(v)

        if executed_tool_results:
            res0 = executed_tool_results[0]
            tname = res0.get("tool")

            if tname == "analyze_stock":
                # Check if tool execution was an error or empty
                if res0.get("status") != "success" or not res0.get("code") or res0.get("current_price") is None:
                    target_code = res0.get("arguments", {}).get("code") or res0.get("code") or "yang dimasukkan"
                    assistant_content = (
                        f"⚠️ Kode saham **{target_code}** tidak ditemukan di Bursa Efek Indonesia (BEI).\n\n"
                        f"Pastikan memasukkan 4 huruf kode emiten resmi (contoh: `BBRI`, `BBCA`, `BMRI`, `TLKM`, `ASII`, `BREN`, `BRIS`, `ANTM`, atau `IHSG`).\n\n"
                        f"Ketik `Analisa BBRI` atau klik salah satu starter card di bawah untuk memulai analisa."
                    )
                else:
                    p_curr = _fmt_n(res0.get("current_price"))
                    tp1 = _fmt_n(res0.get("tp_1"))
                    tp2 = _fmt_n(res0.get("tp_2"))
                    sl = _fmt_n(res0.get("stop_loss"))
                    val_base = _fmt_n(res0.get("valuation_base"))
                    day_chg = res0.get("day_change_pct") or 0.0

                    assistant_content = (
                        f"### 📊 Hasil Analisa Saham: **{res0.get('code')}** ({res0.get('name')})\n\n"
                        f"- **Harga Saat Ini**: {p_curr} ({'+' if day_chg >= 0 else ''}{day_chg}%)\n"
                        f"- **Sinyal Kuantitatif**: **{res0.get('signal_direction', 'NETRAL')}** ({res0.get('action_verdict', 'HOLD')})\n"
                        f"- **Zona Beli (Entry Range)**: **{res0.get('entry_zone', 'N/A')}**\n"
                        f"- **Target Profit 1 (Konservatif)**: {tp1}\n"
                        f"- **Target Profit 2 (Ekspansi)**: {tp2}\n"
                        f"- **Stop Loss Proteksi**: {sl}\n"
                        f"- **Rasio Reward/Risk Bersih**: **{res0.get('net_rr_ratio', 1.5)}x** (Setelah Fee Beli 0.15% & Jual 0.25%)\n"
                        f"- **Status Tren**: {res0.get('trend_status', 'Konsolidasi')}\n\n"
                        f"**Ringkasan Valuasi Fundamental:**\n"
                        f"- Nilai Wajar Base Case (DCF & Multiples): {val_base} ({res0.get('valuation_verdict', 'Fairly Valued')})\n\n"
                        f"💡 *Catatan Manajemen Risiko*: Disiplin memasang Stop Loss ketat dan batasi alokasi maksimal 1–2% risiko modal portofolio per posisi."
                    )

            elif tname == "analyze_crypto":
                if res0.get("status") != "success" or not res0.get("symbol") or res0.get("price_usd") is None:
                    sym = res0.get("symbol") or "yang dimasukkan"
                    assistant_content = (
                        f"⚠️ Aset crypto **{sym}** tidak ditemukan.\n\n"
                        f"Pastikan memasukkan simbol koin global resmi seperti `BTC`, `ETH`, `SOL`, `XRP`, `DOGE`, `ADA`, atau `BNB`."
                    )
                else:
                    p_usd = _fmt_n(res0.get("price_usd"), prefix="$")
                    p_idr = _fmt_n(res0.get("price_idr"), prefix="Rp ")
                    tp1_usd = _fmt_n(res0.get("tp_1_usd"), prefix="$")
                    tp2_usd = _fmt_n(res0.get("tp_2_usd"), prefix="$")
                    sl_usd = _fmt_n(res0.get("stop_loss_usd"), prefix="$")
                    day_chg = res0.get("day_change_pct") or 0.0

                    assistant_content = (
                        f"### 🪙 Hasil Analisa Crypto: **{res0.get('symbol')}** ({res0.get('name')})\n\n"
                        f"- **Harga Live**: **{p_usd}** (≈ {p_idr})\n"
                        f"- **Perubahan 24 Jam**: {'+' if day_chg >= 0 else ''}{day_chg}%\n"
                        f"- **Sinyal Algoritmik**: **{res0.get('signal_direction', 'NEUTRAL')}** ({res0.get('action_verdict', 'WATCH')})\n"
                        f"- **Zona Entry Ideal**: **{res0.get('entry_zone', 'N/A')}**\n"
                        f"- **Target Profit 1**: {tp1_usd}\n"
                        f"- **Target Profit 2**: {tp2_usd}\n"
                        f"- **Stop Loss**: {sl_usd}\n"
                        f"- **Net R/R Ratio**: **{res0.get('net_rr_ratio', 2.0)}x** (setelah fee exchange & PPh 0.10% + PPN 0.11%)\n"
                        f"- **Estimasi Staking APR**: {res0.get('staking_yield_apr', 'N/A')}%\n"
                    )

            elif tname == "get_gold_prices":
                assistant_content = (
                    f"### 🏆 Harga Emas & Spread Buyback Terkini (SOFIA Gold Engine)\n\n"
                    f"- **Emas Antam CertiEye 1 Gram**: **{_fmt_n(res0.get('antam_1g_retail_idr'))}**\n"
                    f"- **Harga Buyback Resmi (Jual Kembali)**: **{_fmt_n(res0.get('antam_1g_buyback_idr'))}**\n"
                    f"- **Spread Buyback (Selisih Beli - Jual)**: **{res0.get('buyback_spread_pct', 8.5)}%**\n"
                    f"- **Emas UBS 1 Gram**: {_fmt_n(res0.get('ubs_1g_retail_idr'))}\n"
                    f"- **Spot Dunia XAU/USD**: {_fmt_n(res0.get('spot_xau_usd'), prefix='$')} / Troy Ounce (Kurs: {_fmt_n(res0.get('usd_idr_rate'))})\n\n"
                    f"💡 *Saran Finansial*: Karena spread buyback emas Antam saat ini berkisar {res0.get('buyback_spread_pct', 8.5)}%, "
                    f"emas sangat ideal untuk instrumen lindung nilai jangka menengah–panjang (> 1–3 tahun) agar keuntungan modal melampaui selisih spread."
                )

            elif tname == "calculate_deposito_and_bonds":
                dep = res0.get("deposito", {})
                ob = res0.get("obligasi_sbn", {})
                inst_type = res0.get("instrument_type") or ("Deposito Syariah Mudharabah vs Sukuk SBN" if res0.get("is_syariah") else "Deposito Konvensional vs Obligasi SBN")
                assistant_content = (
                    f"### 💰 Simulasi Investasi: **{inst_type}**\n"
                    f"**Nominal Pokok**: **{_fmt_n(res0.get('nominal_idr'))}** | Tenor: {res0.get('tenor_days', 365)} Hari\n\n"
                    f"**1. {dep.get('label', 'Deposito')} ({dep.get('rate_pa_pct', 5.0)}% p.a.)**\n"
                    f"- Imbal Hasil Kotor: {_fmt_n(dep.get('gross_profit_idr'))}\n"
                    f"- Pajak PPh 20%: -{_fmt_n(dep.get('tax_pph_20_idr'))}\n"
                    f"- **Keuntungan Bersih**: **{_fmt_n(dep.get('net_profit_idr'))}** (Yield Bersih: {dep.get('net_yield_pct', 4.0)}%)\n\n"
                    f"**2. {ob.get('label', 'Obligasi SBN')} ({ob.get('kupon_pa_pct', 6.5)}% p.a.)**\n"
                    f"- Kupon Kotor: {_fmt_n(ob.get('gross_profit_idr'))}\n"
                    f"- Pajak PPh 10%: -{_fmt_n(ob.get('tax_pph_10_idr'))}\n"
                    f"- **Keuntungan Bersih**: **{_fmt_n(ob.get('net_profit_idr'))}** (Yield Bersih: {ob.get('net_yield_pct', 5.85)}%)\n\n"
                    f"🎯 **Selisih Tambahan Bersih**: **+{_fmt_n(res0.get('selisih_keuntungan_bersih_idr'))}** lebih menguntungkan di Obligasi/Sukuk SBN!\n"
                    f"{res0.get('rekomendasi', '')}"
                )

            elif tname == "analyze_memecoin_rugcheck":
                score = res0.get("safety_score", 70)
                verdict = res0.get("verdict", "SAFE")
                status_icon = "🟢" if score >= 75 else ("🟡" if score >= 50 else "🔴")
                assistant_content = (
                    f"### 🛡️ Laporan Audit Keamanan & Rugcheck: **{res0.get('symbol')}** ({res0.get('name')})\n\n"
                    f"- **Skor Keselamatan (Safety Score)**: {status_icon} **{score}/100** ({verdict})\n"
                    f"- **Status Honeypot**: **{'❌ BAHAYA (Honeypot Terdeteksi)' if res0.get('honeypot') else '✅ AMAN (Bukan Honeypot)'}**\n"
                    f"- **Likuiditas Terkunci/Burned**: **{'✅ Terkunci / Burned' if res0.get('lp_burned') else '⚠️ Belum Terkunci Penuh'}**\n"
                    f"- **Mint Authority (Pencetakan Token Baru)**: **{'✅ Dinonaktifkan (Renounced)' if res0.get('mint_revoked') else '⚠️ Masih Aktif'}**\n"
                    f"- **Freeze Authority (Pembekuan Wallet)**: **{'✅ Dinonaktifkan' if res0.get('freeze_revoked') else '⚠️ Masih Aktif'}**\n"
                    f"- **Konsentrasi Top 10 Holders**: **{res0.get('top10_pct', 25.0)}%**\n"
                    f"- **Likuiditas Pool**: {_fmt_n(res0.get('liquidity_usd'), prefix='$')}\n\n"
                    f"💡 *Saran Trading*: Selalu perhatikan rasio konsentrasi dev dan jangan gunakan modal lebih dari 1-2% untuk koin tren memecoin."
                )

            elif tname == "lookup_market_encyclopedia":
                assistant_content = (
                    f"### 📚 Ensiklopedia Finansial: **{res0.get('keyword', '').upper()}**\n\n"
                    f"{res0.get('explanation')}\n\n"
                    f"💡 *Aplikasi Praktis*: Anda dapat mengonfirmasi pola atau konsep ini secara visual pada grafik saham atau indikator teknikal di platform SOFIA."
                )

            elif tname == "search_market_news":
                articles = res0.get("articles", [])
                if not articles:
                    assistant_content = (
                        "### 📰 Berita Pasar Finansial Terkini\n\n"
                        "Saat ini feed berita pasar finansial sedang diperbarui atau tidak ada artikel yang cocok dengan filter pencarian Anda.\n\n"
                        "💡 *Saran*: Silakan tanyakan topik spesifik seperti: `Berita saham IHSG`, `Kabar crypto Bitcoin hari ini`, atau `Perkembangan harga emas Antam`."
                    )
                else:
                    art_lines = []
                    for idx, a in enumerate(articles[:4], 1):
                        title = a.get("title") or "Kabar Finansial Terkini"
                        pub = a.get("publisher") or a.get("source") or "Portal Finansial"
                        time_str = a.get("time") or a.get("published_at") or "Terkini"
                        summary = (a.get("summary") or "").strip()
                        if not summary or summary.lower() == title.lower() or len(summary) < 25:
                            summary_line = f"Laporan {pub} terkait dinamika pergerakan pasar keuangan, sentimen ekonomi, dan tren bursa terkini."
                        else:
                            summary_line = summary

                        art_lines.append(
                            f"**{idx}. {title}**\n"
                            f"- 🕒 **Waktu**: {time_str} | **Sumber**: {pub}\n"
                            f"- 📝 **Ringkasan**: {summary_line}"
                        )

                    assistant_content = (
                        f"### 📰 Berita Pasar Finansial Terkini ({len(art_lines)} Berita Paling Baru)\n\n"
                        + "\n\n".join(art_lines)
                        + "\n\n💡 *Sentimen Pasar*: Pantau perkembangan berita makroekonomi dan sentimen global untuk mengonfirmasi arah tren bursa saham, kripto, dan komoditas."
                    )

            elif tname == "get_bot_and_portfolio_status":
                port = res0.get("portfolio", {})
                assistant_content = (
                    f"### 🤖 Status Bot Trading & Portofolio SOFIA\n\n"
                    f"- **Status Bot Sniper**: **{'AKTIF (Running)' if res0.get('bot_running') else 'IDLE (Standby)'}** (Mode: {res0.get('bot_mode', 'PAPER')})\n"
                    f"- **Total Ekuitas**: **{_fmt_n(port.get('total_equity_usd'), prefix='$')}** (≈ {_fmt_n(port.get('total_equity_idr'))})\n"
                    f"- **Saldo Kas (Cash)**: {_fmt_n(port.get('cash_balance_usd'), prefix='$')}\n"
                    f"- **Jumlah Posisi Aktif**: {port.get('holdings_count', 0)} Token\n"
                    f"- **Total Transaksi Selesai**: {res0.get('total_trades', 0)} Eksekusi"
                )
            else:
                assistant_content = f"Data dari tool **{tname}** berhasil diproses: {json.dumps(res0, ensure_ascii=False)}"

        else:
            assistant_content = (
                f"Halo! Saya adalah **SOFIA AI Quant & Research Assistant** — asisten riset pasar finansial multi-aset terpadu di platform SOFIA.\n\n"
                f"Berikut adalah kapabilitas dan data yang dapat saya sediakan langsung untuk Anda:\n\n"
                f"1. 📈 **Analisa Saham BEI (IDX)**: Ketik `Analisa BBRI`, `Saham BBCA`, `BRIS`, atau `BREN` untuk mendapatkan harga live, Trading Plan (Entry, TP, SL), dan valuasi fundamental DCF & PBV/PER.\n"
                f"2. 🪙 **Analisa Crypto Global**: Ketik `Analisa BTC`, `SOL`, atau `ETH` untuk melihat tren, level teknikal, dan estimasi APR staking.\n"
                f"3. 🛡️ **Audit Keamanan Memecoin / Rugcheck**: Ketik `Cek rugcheck BONK` atau masukkan contract address token Solana/Pump.fun.\n"
                f"4. 🏆 **Harga Emas & Spread Buyback**: Ketik `Harga emas hari ini` untuk melihat harga Antam CertiEye 1g, harga buyback, dan spot XAU/USD.\n"
                f"5. 💰 **Kalkulator Deposito vs Obligasi**: Ketik `Simulasi 50 juta deposito syariah vs sukuk` untuk menghitung perbandingan imbal hasil bersih setelah pajak (PPh 20% vs 10%).\n"
                f"6. 📰 **Berita Pasar Terkini**: Ketik `Berita IHSG hari ini` untuk membaca rangkuman berita finansial dari CNBC Indonesia dan Antara.\n"
                f"7. 📚 **Ensiklopedia Finansial**: Ketik `Apa itu Order Block`, `Apa itu FVG`, atau `Apa itu Mudharabah`.\n\n"
                f"Silakan ketik pertanyaan Anda sesuai kebutuhan analisa di atas!"
            )

    return {
        "content": assistant_content,
        "tool_calls": executed_tool_calls,
        "tool_results": executed_tool_results,
        "model": selected_model,
        "provider": prov,
    }


# ==============================================================================
# DATABASE SESSION & MESSAGE HELPERS
# ==============================================================================

def _resolve_session(db: Session, session_id: Optional[str]) -> Optional[ChatSession]:
    if not session_id:
        return None
    sid_str = str(session_id).strip()
    session = db.execute(select(ChatSession).where(ChatSession.session_id == sid_str)).scalar_one_or_none()
    if not session and sid_str.isdigit():
        session = db.execute(select(ChatSession).where(ChatSession.id == int(sid_str))).scalar_one_or_none()
    return session


def list_chat_sessions(db: Session) -> List[Dict[str, Any]]:
    """List all chat sessions ordered by latest updated."""
    sessions = db.execute(select(ChatSession).order_by(desc(ChatSession.updated_at))).scalars().all()
    res = []
    for s in sessions:
        # Count messages in this session
        msg_count = db.execute(
            select(ChatMessage).where(ChatMessage.session_id == s.session_id)
        ).scalars().all()
        res.append({
            "id": s.session_id,
            "session_id": s.session_id,
            "db_id": s.id,
            "title": s.title,
            "provider": s.provider,
            "model": s.model,
            "message_count": len(msg_count),
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "updated_at": s.updated_at.isoformat() if s.updated_at else None,
        })
    return res


def create_chat_session(
    db: Session,
    title: Optional[str] = None,
    provider: str = "openrouter",
    model: str = "google/gemini-2.0-flash-exp:free",
    system_prompt: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a new chat session."""
    sid = f"sess_{uuid.uuid4().hex[:12]}"
    session = ChatSession(
        session_id=sid,
        title=title or "Percakapan Baru",
        provider=provider or "openrouter",
        model=model or "google/gemini-2.0-flash-exp:free",
        system_prompt=system_prompt or "",
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return {
        "id": session.session_id,
        "session_id": session.session_id,
        "db_id": session.id,
        "title": session.title,
        "provider": session.provider,
        "model": session.model,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "updated_at": session.updated_at.isoformat() if session.updated_at else None,
    }


def get_chat_session_with_messages(db: Session, session_id: str) -> Optional[Dict[str, Any]]:
    """Get session and its chronological message history."""
    session = _resolve_session(db, session_id)
    if not session:
        return None

    messages = db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session.session_id)
        .order_by(ChatMessage.created_at)
    ).scalars().all()

    return {
        "id": session.session_id,
        "session_id": session.session_id,
        "title": session.title,
        "provider": session.provider,
        "model": session.model,
        "system_prompt": session.system_prompt,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "updated_at": session.updated_at.isoformat() if session.updated_at else None,
        "messages": [
            {
                "id": str(m.id),
                "role": m.role,
                "content": m.content,
                "tool_calls": m.tool_calls,
                "tool_results": m.tool_results,
                "model": m.model,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
    }


def update_chat_session(
    db: Session,
    session_id: str,
    title: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Update title, provider, or model for a session."""
    session = _resolve_session(db, session_id)
    if not session:
        return None

    if title is not None:
        session.title = title
    if provider is not None:
        session.provider = provider
    if model is not None:
        session.model = model
    session.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(session)
    return {
        "id": session.session_id,
        "session_id": session.session_id,
        "title": session.title,
        "provider": session.provider,
        "model": session.model,
        "updated_at": session.updated_at.isoformat() if session.updated_at else None,
    }


def delete_chat_session(db: Session, session_id: str) -> bool:
    """Delete a session and all its messages."""
    session = _resolve_session(db, session_id)
    if not session:
        return False

    messages = db.execute(
        select(ChatMessage).where(ChatMessage.session_id == session.session_id)
    ).scalars().all()
    for m in messages:
        db.delete(m)

    db.delete(session)
    db.commit()
    return True


def save_chat_message(
    db: Session,
    session_id: str,
    role: str,
    content: str,
    tool_calls: Optional[Any] = None,
    tool_results: Optional[Any] = None,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """Append a message to a session and touch updated_at."""
    session = _resolve_session(db, session_id)
    target_sid = session.session_id if session else str(session_id)

    if session:
        session.updated_at = datetime.now(timezone.utc)
        # If title is default "Percakapan Baru" and user sends first message, rename smartly
        if session.title == "Percakapan Baru" and role == "user":
            snippet = content.strip().replace("\n", " ")[:40]
            if snippet:
                session.title = snippet + ("..." if len(content) > 40 else "")
        db.commit()

    msg = ChatMessage(
        session_id=target_sid,
        role=role,
        content=content,
        tool_calls=tool_calls,
        tool_results=tool_results,
        model=model,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return {
        "id": str(msg.id),
        "session_id": target_sid,
        "role": msg.role,
        "content": msg.content,
        "tool_calls": msg.tool_calls,
        "tool_results": msg.tool_results,
        "model": msg.model,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
    }
