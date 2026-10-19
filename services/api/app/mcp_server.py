"""
SOFIA Intelligence MCP (Model Context Protocol) Server.
Enables external AI agents (Hermes Agent, OpenClaw, Claude Desktop, Cursor, Antigravity, etc.)
to query Indonesian financial markets, crypto analysis, physical gold prices,
memecoin rugcheck audits, and investment calculations directly from SOFIA.
"""

import sys
import os
import json
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

from mcp.server.fastmcp import FastMCP

# Ensure the parent app packages can be imported
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from app.services import (
    stocks as stocks_service,
    crypto_analysis as crypto_service,
    gold as gold_service,
    memecoins as memecoins_service,
    news as news_service,
    signals as signals_service,
    portfolio as portfolio_service,
    market as market_service,
)
from app.db.session import SessionLocal

# Initialize FastMCP Server
mcp = FastMCP(
    name="sofia-intelligence",
    instructions=(
        "SOFIA Intelligence MCP Server provides real-time access to Indonesian financial markets (IDX/BEI stocks), "
        "global cryptocurrency analysis with technical indicators and trading plans, Indonesian physical gold prices "
        "(Antam CertiEye, UBS, Galeri 24), Solana meme coin rugcheck security audits, investment calculators "
        "(conventional & syariah deposito vs Indonesian Government Bonds / SBN), active quantitative signals, and financial news."
    ),
)


# ==============================================================================
# MCP TOOLS
# ==============================================================================

@mcp.tool()
def analyze_stock(ticker: str = "BBRI", timeframe: str = "1d") -> Dict[str, Any]:
    """
    Analisa komprehensif saham Bursa Efek Indonesia (BEI / IDX).
    Mengembalikan harga live IDR, rekomendasi Trading Plan (Entry Zone, TP1, TP2, Stop Loss, Risk-to-Reward),
    indikator teknikal (RSI, MACD, MA), serta valuasi fundamental (PBV, PER, Fair Value DCF).

    :param ticker: 4-huruf kode saham BEI (contoh: 'BBRI', 'BBCA', 'BMRI', 'TLKM', 'ASII', 'IHSG').
    :param timeframe: Timeframe analisa ('15m', '1h', '4h', '1d', '1w', '1mo'). Default '1d'.
    """
    code = str(ticker or "BBRI").strip().upper()
    tf = str(timeframe or "1d").strip()
    data = stocks_service.analyze_stock(code, timeframe=tf, force_refresh=False)
    plan = data.get("trading_plan", {})
    val_engine = data.get("valuation_engine", {})
    
    return {
        "status": "success",
        "ticker": data.get("code") or code,
        "company_name": data.get("name") or code,
        "current_price_idr": data.get("current_price"),
        "day_change_idr": data.get("day_change"),
        "day_change_pct": data.get("day_change_pct"),
        "trading_plan": {
            "signal_direction": plan.get("signal_direction"),
            "action_verdict": plan.get("action_verdict"),
            "entry_zone_idr": f"{plan.get('entry_zone_low')} - {plan.get('entry_zone_high')}",
            "target_price_1_idr": plan.get("tp_1"),
            "target_price_2_idr": plan.get("tp_2"),
            "stop_loss_idr": plan.get("stop_loss"),
            "net_risk_reward_ratio": plan.get("net_risk_reward_ratio"),
            "trend_status": plan.get("trend_status"),
            "indicator_summary": plan.get("indicator_summary"),
        },
        "valuation": {
            "verdict": val_engine.get("verdict"),
            "fair_value_base_idr": val_engine.get("scenarios", {}).get("base_case"),
            "dcf_fair_value_idr": val_engine.get("dcf", {}).get("fair_value"),
            "pbv_multiple": val_engine.get("multiples", {}).get("pbv"),
            "per_multiple": val_engine.get("multiples", {}).get("per"),
        },
        "source": "SOFIA Equity Intelligence Engine",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }


@mcp.tool()
def analyze_crypto(symbol: str = "BTC", timeframe: str = "1d") -> Dict[str, Any]:
    """
    Analisa aset cryptocurrency global 24/7 (BTC, ETH, SOL, altcoins).
    Mengembalikan harga live USD & konversi IDR, Trading Plan (Entry, TP1, TP2, Stop Loss),
    indikator teknikal, staking yield APR, dan rasio risiko tokenomics (FDV/MCap).

    :param symbol: Simbol kripto (contoh: 'BTC', 'ETH', 'SOL', 'BONK', 'DOGE').
    :param timeframe: Timeframe analisa ('15m', '1h', '4h', '1d', '1w', '1mo'). Default '1d'.
    """
    sym = str(symbol or "BTC").strip().upper()
    tf = str(timeframe or "1d").strip()
    data = crypto_service.analyze_crypto(sym, timeframe=tf, force_refresh=False)
    plan = data.get("trading_plan", {})
    
    return {
        "status": "success",
        "symbol": data.get("code") or sym,
        "name": data.get("name") or sym,
        "price_usd": data.get("current_price_usd"),
        "price_idr": data.get("current_price_idr"),
        "day_change_pct": data.get("day_change_pct"),
        "trading_plan": {
            "signal_direction": plan.get("signal_direction"),
            "action_verdict": plan.get("action_verdict"),
            "entry_zone_usd": f"${plan.get('entry_zone_low_usd')} - ${plan.get('entry_zone_high_usd')}",
            "target_price_1_usd": plan.get("tp_1_usd"),
            "target_price_2_usd": plan.get("tp_2_usd"),
            "stop_loss_usd": plan.get("stop_loss_usd"),
            "net_risk_reward_ratio": plan.get("net_risk_reward_ratio"),
            "trend_status": plan.get("trend_status"),
        },
        "staking_yield_apr_pct": data.get("staking_intelligence", {}).get("estimated_apr_pct"),
        "fdv_to_mcap_ratio": data.get("tokenomics", {}).get("fdv_to_mcap_ratio"),
        "source": "SOFIA Crypto Intelligence Engine",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }


@mcp.tool()
def get_gold_market() -> Dict[str, Any]:
    """
    Mengambil data pasar emas fisik Indonesia terkini.
    Meliputi harga retail Antam CertiEye, harga buyback resmi Antam, persentase spread buyback,
    harga emas UBS / Galeri 24, serta kurs spot dunia XAU/USD dan spot IDR/gram.
    """
    data = gold_service.fetch_live_gold_market(force_refresh=False)
    antam = data.get("antam") or {}
    ubs = data.get("ubs") or {}
    return {
        "status": "success",
        "antam_1g_retail_idr": antam.get("buy_price_idr"),
        "antam_1g_buyback_idr": antam.get("buyback_price_idr"),
        "buyback_spread_pct": antam.get("spread_pct"),
        "ubs_1g_retail_idr": ubs.get("buy_price_idr"),
        "spot_xau_usd": data.get("xau_usd"),
        "spot_gram_idr": data.get("spot_idr_per_gram"),
        "usd_idr_rate": data.get("usd_idr"),
        "source": "SOFIA Gold & Precious Metals Engine",
        "updated_at": data.get("updated_at"),
    }


@mcp.tool()
def calculate_deposito_vs_bonds(
    nominal_idr: float = 10000000.0,
    tenor_days: int = 365,
    deposito_rate_pct: float = 5.0,
    bond_rate_pct: float = 6.5,
    is_syariah: bool = False,
) -> Dict[str, Any]:
    """
    Kalkulator simulasi perbandingan imbal hasil investasi antara Deposito Perbankan
    (Konvensional atau Deposito Syariah Mudharabah) versus Surat Berharga Negara (SBN / Obligasi seperti ORI, Sukuk Ritel, FR).
    Menerapkan regulasi pajak resmi Indonesia: PPh Deposito 20% vs PPh SBN 10%.

    :param nominal_idr: Nilai pokok investasi dalam Rupiah (contoh: 10000000 untuk 10 juta).
    :param tenor_days: Durasi tenor dalam hari (contoh: 7, 30, 90, 180, 365).
    :param deposito_rate_pct: Margin bagi hasil / bunga deposito p.a. (maks 20%).
    :param bond_rate_pct: Kupon obligasi SBN p.a. (maks 20%).
    :param is_syariah: Set True untuk Deposito Syariah (Nisbah Mudharabah) & Sukuk Ritel Syariah.
    """
    p = max(100000.0, float(nominal_idr))
    days = max(1, int(tenor_days))
    dep_rate = min(20.0, max(0.1, float(deposito_rate_pct)))
    bond_rate = min(20.0, max(0.1, float(bond_rate_pct)))

    # Deposito: PPh 20%
    dep_gross = p * (dep_rate / 100.0) * (days / 365.0)
    dep_tax = dep_gross * 0.20
    dep_net = dep_gross - dep_tax

    # SBN: PPh 10%
    bond_gross = p * (bond_rate / 100.0) * (days / 365.0)
    bond_tax = bond_gross * 0.10
    bond_net = bond_gross - bond_tax

    diff_idr = bond_net - dep_net
    mode_label = "Deposito Syariah (Akad Mudharabah) vs Sukuk SBN" if is_syariah else "Deposito Konvensional vs Obligasi SBN"

    return {
        "status": "success",
        "instrument_type": mode_label,
        "nominal_idr": p,
        "tenor_days": days,
        "deposito": {
            "label": "Deposito Syariah Mudharabah" if is_syariah else "Deposito Perbankan",
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
        "net_difference_idr": round(diff_idr, 2),
        "tax_advantage": "SBN memiliki keunggulan pajak PPh hanya 10% (separuh dari pajak deposito 20%).",
    }


@mcp.tool()
def analyze_memecoin_rugcheck(token_query: str) -> Dict[str, Any]:
    """
    Audit keamanan dan analisis risiko Rugcheck untuk koin meme Solana / Pump.fun / Base.
    Memeriksa likuiditas terkunci (LP lock), mint authority status, freeze authority status,
    konsentrasi kepemilikan top 10 holders, serta skor keselamatan koin (0-100).

    :param token_query: Simbol koin (misal 'BONK', 'WIF', 'POPCAT') atau Contract Address token.
    """
    data = memecoins_service.analyze_rug_check(token_query)
    return {
        "status": "success",
        "token_name": data.get("name"),
        "symbol": data.get("symbol"),
        "contract_address": data.get("contract"),
        "chain": data.get("chain"),
        "safety_score": data.get("safety_score"),
        "risk_verdict": data.get("verdict"),
        "liquidity_usd": data.get("liquidity_usd"),
        "market_cap_usd": data.get("market_cap"),
        "lp_burned_or_locked": data.get("lp_burned", True),
        "mint_authority_disabled": data.get("mint_revoked", True),
        "freeze_authority_disabled": data.get("freeze_revoked", True),
        "top_10_holders_pct": data.get("top10_pct"),
        "is_honeypot": data.get("honeypot", False),
        "risks": data.get("risks", []),
        "source": "SOFIA Rugcheck & Security Intelligence",
    }


@mcp.tool()
def search_market_news(query: str = "", category: str = "all", limit: int = 5) -> Dict[str, Any]:
    """
    Mencari berita finansial dan pasar Indonesia terkini dari media terverifikasi (CNBC Indonesia, Antara, dsb).

    :param query: Kata kunci pencarian (contoh: 'IHSG', 'BI Rate', 'Bitcoin', 'Antam'). Kosongkan untuk headline umum.
    :param category: Kategori berita ('all', 'saham', 'crypto', 'emas', 'ekonomi').
    :param limit: Jumlah maksimal artikel yang dikembalikan (default 5, maks 10).
    """
    lim = min(10, max(1, int(limit)))
    data = news_service.fetch_indonesian_news(
        category=category or "all",
        query=query or None,
        refresh=False,
        limit=lim,
    )
    articles = []
    for it in data.get("articles", [])[:lim]:
        articles.append({
            "title": it.get("title"),
            "source": it.get("source"),
            "category": it.get("category"),
            "published_at_wib": it.get("published_at_wib"),
            "summary": it.get("summary"),
            "link": it.get("link"),
        })
    return {
        "status": "success",
        "total_articles": len(articles),
        "query": query,
        "category": category,
        "articles": articles,
    }


@mcp.tool()
def get_trading_signals(status: str = "pending", limit: int = 10) -> Dict[str, Any]:
    """
    Membaca sinyal trading kuantitatif aktif (Buy/Sell, Entry, TP, Stop Loss) yang dihasilkan oleh engine SOFIA.

    :param status: Filter status sinyal ('pending', 'active', 'closed', atau kosong untuk semua).
    :param limit: Jumlah sinyal (default 10).
    """
    with SessionLocal() as db:
        items, total = signals_service.list_signals(db, status=status or None, limit=min(25, int(limit)))
        results = []
        for s in items:
            results.append({
                "id": s.id,
                "symbol": s.symbol,
                "direction": s.direction,
                "confidence_pct": s.confidence,
                "entry_price": s.entry_price,
                "take_profit": s.take_profit,
                "stop_loss": s.stop_loss,
                "timeframe": s.timeframe,
                "source": s.source,
                "status": s.status,
                "created_at_utc": s.created_at.isoformat() if s.created_at else None,
            })
    return {
        "status": "success",
        "total_active_signals": total,
        "signals": results,
    }


@mcp.tool()
def get_portfolio_status() -> Dict[str, Any]:
    """
    Membaca ringkasan ekuitas portofolio trading live, saldo tunai IDR & USD,
    posisi aset yang sedang di-hold, dan kurs valuta asing live (USD/IDR).
    """
    with SessionLocal() as db:
        port = portfolio_service.get_live_portfolio(db, refresh_live_prices=False)
        return {
            "status": "success",
            "usd_idr_rate": port.get("usd_idr"),
            "total_equity_usd": port.get("live_total_equity_usd") or port.get("paper_cash_usd"),
            "total_equity_idr": port.get("live_cash_idr") or port.get("paper_cash_idr"),
            "cash_balance_usd": port.get("paper_cash_usd"),
            "holdings_count": len(port.get("items", [])),
            "holdings": port.get("items", []),
        }


@mcp.tool()
def lookup_market_encyclopedia(keyword: str) -> Dict[str, Any]:
    """
    Kamus dan ensiklopedia finansial untuk memahami istilah trading, saham BEI, Smart Money Concepts (SMC), dan Web3.

    :param keyword: Istilah yang dicari (contoh: 'BOS', 'CHoCH', 'Order Block', 'FVG', 'ARA', 'ARB', 'Mudharabah', 'PER', 'PBV', 'Troy Ounce').
    """
    kw = str(keyword or "").lower().strip()
    encyclopedia_dict = {
        "bos": "Break of Structure (BOS) dalam Smart Money Concepts (SMC): Lilin harga menembus Swing High sebelumnya dalam tren naik, atau menembus Swing Low dalam tren turun.",
        "choch": "Change of Character (CHoCH): Tanda awal potensi pembalikan tren saat struktur pasar terdekat gagal bertahan.",
        "ob": "Order Block (OB): Jejak lilin berlawanan arah terakhir institusi sebelum pergerakan impulsif (Demand Zone untuk Bullish OB, Supply Zone untuk Bearish OB).",
        "order block": "Order Block (OB): Jejak likuiditas institusi pintar sebelum reli atau penurunan tajam.",
        "fvg": "Fair Value Gap (FVG): Celah ketidakseimbangan likuiditas antara lilin ke-1 dan ke-3 yang sering dituju harga untuk retest.",
        "ara": "Auto Rejection Atas (ARA): Batas persentase kenaikan harga saham maksimal dalam 1 hari perdagangan bursa di BEI (misal 35% untuk fraksi harga <Rp200, 25% untuk Rp200-Rp5000, 20% untuk >Rp5000).",
        "arb": "Auto Rejection Bawah (ARB): Batas persentase penurunan harga saham maksimal simetris dalam 1 hari di BEI.",
        "troy ounce": "Standar ukuran berat logam mulia internasional. 1 Troy Ounce setara tepat dengan 31.1034768 gram.",
        "mudharabah": "Akad kemitraan bagi hasil dalam perbankan syariah di mana deposan (shahibul mal) menyediakan dana dan bank (mudharib) mengelolanya dengan nisbah disepakati.",
        "per": "Price to Earnings Ratio: Rasio harga saham terhadap laba per saham (EPS). Mengukur berapa rupiah yang bersedia dibayar investor untuk setiap Rp1 laba emiten.",
        "pbv": "Price to Book Value: Rasio harga saham terhadap nilai buku ekuitas (Book Value). PBV < 1.0x mengindikasikan saham diperdagangkan di bawah nilai aset bersihnya.",
    }
    # Exact match first
    match = encyclopedia_dict.get(kw)
    if not match:
        for k, v in encyclopedia_dict.items():
            if k == kw or kw == k:
                match = v
                break
        if not match:
            for k, v in encyclopedia_dict.items():
                if len(k) >= 4 and (k in kw or kw in k):
                    match = v
                    break
    if not match:
        match = f"Istilah '{keyword}' adalah konsep keuangan terdaftar di SOFIA Market Intelligence."

    return {
        "status": "success",
        "keyword": keyword,
        "explanation": match,
    }


@mcp.tool()
def get_market_pulse() -> Dict[str, Any]:
    """
    Snapshot live denyut pasar (Market Pulse): token Solana trending, volume lonjakan DexScreener, dan kurs FX USD/IDR.
    """
    pulse = market_service.get_live_pulse_feed()
    fx = market_service.get_fx_rate()
    return {
        "status": "success",
        "usd_idr": fx.get("usd_idr"),
        "trending_tokens_count": len(pulse.get("trending", [])),
        "trending_tokens": pulse.get("trending", [])[:6],
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }


# ==============================================================================
# MCP RESOURCES
# ==============================================================================

@mcp.resource("sofia://market/pulse")
def resource_market_pulse() -> str:
    """Live snapshot of market pulse and USD/IDR rate."""
    data = get_market_pulse()
    return json.dumps(data, indent=2)


@mcp.resource("sofia://gold/prices")
def resource_gold_prices() -> str:
    """Current live Indonesian physical gold prices (Antam, UBS, Spot)."""
    data = get_gold_market()
    return json.dumps(data, indent=2)


@mcp.resource("sofia://portfolio/summary")
def resource_portfolio_summary() -> str:
    """Current live trading equity and balance overview."""
    data = get_portfolio_status()
    return json.dumps(data, indent=2)


# ==============================================================================
# MCP PROMPTS
# ==============================================================================

@mcp.prompt()
def morning_market_briefing() -> str:
    """Prompt template for morning Indonesian financial and crypto market briefing."""
    return (
        "Buatkan rangkuman pagi komprehensif untuk investor Indonesia:\n"
        "1. Cek harga emas Antam dan buyback spread hari ini menggunakan tool get_gold_market.\n"
        "2. Cek saham penggerak IHSG (misal BBCA, BBRI, BMRI, TLKM) menggunakan tool analyze_stock.\n"
        "3. Cek kondisi pasar kripto global (BTC dan SOL) menggunakan tool analyze_crypto.\n"
        "4. Cek berita finansial terkini dengan search_market_news.\n"
        "Sajikan dalam format ringkas, padat aksi, dan profesional."
    )


@mcp.prompt()
def stock_investment_thesis(ticker: str) -> str:
    """Prompt template for deep institutional stock analysis on IDX."""
    return (
        f"Lakukan evaluasi menyeluruh untuk emiten BEI: {ticker}.\n"
        f"Gunakan tool analyze_stock(ticker='{ticker}') untuk mendapatkan data teknikal dan valuasi.\n"
        "Analisa: \n"
        "- Trend dan momentum teknikal saat ini\n"
        "- Zona beli ideal, target take profit, dan rasio batas risiko (R/R)\n"
        "- Status valuasi (Undervalued / Fair / Overvalued) berdasarkan DCF dan PBV\n"
        "- Kesimpulan rekomendasi akhir (BUY / HOLD / SELL)."
    )


@mcp.prompt()
def token_risk_audit(symbol: str) -> str:
    """Prompt template to conduct security due diligence on a token or memecoin."""
    return (
        f"Lakukan audit keamanan mendalam untuk token: {symbol}.\n"
        f"1. Panggil analyze_memecoin_rugcheck(token_query='{symbol}') untuk mengecek skor risiko dan likuiditas.\n"
        f"2. Panggil analyze_crypto(symbol='{symbol}') untuk mengecek pergerakan harga dan indikator.\n"
        "Berikan laporan bahaya/keamanan (Green Flag vs Red Flag) untuk trader."
    )


# ==============================================================================
# ENTRY POINT
# ==============================================================================

def main():
    """Run FastMCP server over standard STDIO or SSE depending on CLI arguments."""
    if "--sse" in sys.argv:
        port = 8001
        for i, arg in enumerate(sys.argv):
            if arg == "--port" and i + 1 < len(sys.argv):
                port = int(sys.argv[i + 1])
        print(f"Starting SOFIA MCP Server via SSE on port {port}...", file=sys.stderr)
        mcp.run(transport="sse")
    else:
        # Standard STDIO transport for Hermes Agent, OpenClaw, Claude Desktop, Cursor, etc.
        mcp.run()


if __name__ == "__main__":
    main()
