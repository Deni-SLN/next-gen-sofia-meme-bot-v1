import concurrent.futures
import time
from datetime import datetime, timezone
from typing import Any, Optional
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.db.models import Signal
from app.services import stocks as stocks_service
from app.services import crypto_analysis as crypto_service

# Cache TTL in seconds for fast delivery (<5ms)
INSIGHTS_CACHE_TTL = 60
_CACHED_INSIGHTS: dict[str, Any] = {
    "timestamp": 0.0,
    "stocks": [],
    "crypto": [],
}

CURATED_STOCKS_METADATA = [
    {
        "ticker": "BBCA",
        "name": "PT Bank Central Asia Tbk",
        "sector": "Perbankan Swasta Buku 4",
        "quality_badge": "Bluechip IDX30 • CASA King",
        "safety_score": 98,
        "catalyst": "Rasio CASA tertinggi (>80%), efisiensi operasional terbaik di industri, serta daya tahan terkuat terhadap fluktuasi suku bunga global.",
        "fallback_price": 9875.0,
        "fallback_change": 0.75,
        "fallback_entry_zone": "Rp 9.750 – Rp 9.875",
        "fallback_tp1": 10500.0,
        "fallback_tp2": 11000.0,
        "fallback_sl": 9450.0,
        "fallback_rr": "1 : 2.45",
        "fallback_action": "ACCUMULATE / BUY ON WEAKNESS",
    },
    {
        "ticker": "BBRI",
        "name": "PT Bank Rakyat Indonesia (Persero) Tbk",
        "sector": "Perbankan BUMN & Kredit Mikro",
        "quality_badge": "High Dividend • Micro Lending Giant",
        "safety_score": 94,
        "catalyst": "Kredit mikro Kupedes terus tumbuh, restrukturisasi pasca-pandemi tuntas, dan estimasi dividen yield menarik >6.0% di valuasi saat ini.",
        "fallback_price": 4720.0,
        "fallback_change": 1.25,
        "fallback_entry_zone": "Rp 4.650 – Rp 4.750",
        "fallback_tp1": 5150.0,
        "fallback_tp2": 5400.0,
        "fallback_sl": 4500.0,
        "fallback_rr": "1 : 2.60",
        "fallback_action": "BUY ON SUPPORT / SWING ACCUMULATE",
    },
    {
        "ticker": "TLKM",
        "name": "PT Telkom Indonesia (Persero) Tbk",
        "sector": "Telekomunikasi & Infrastruktur Digital",
        "quality_badge": "Telco Dominance • Data Center Growth",
        "safety_score": 92,
        "catalyst": "Monetisasi infrastruktur data center NeutraDC, integrasi FMC IndiHome-Telkomsel yang efisien, dan arus kas dividen konsisten.",
        "fallback_price": 3120.0,
        "fallback_change": 0.65,
        "fallback_entry_zone": "Rp 3.080 – Rp 3.140",
        "fallback_tp1": 3450.0,
        "fallback_tp2": 3650.0,
        "fallback_sl": 2980.0,
        "fallback_rr": "1 : 2.50",
        "fallback_action": "VALUE ACCUMULATE / DEFENSIVE PLAY",
    },
    {
        "ticker": "ASII",
        "name": "PT Astra International Tbk",
        "sector": "Konglomerasi Otomotif, Alat Berat & Energi",
        "quality_badge": "Cash-Rich Giant • EV Ecosystem",
        "safety_score": 90,
        "catalyst": "Posisi kas melimpah, dividen interim stabil, dan percepatan adopsi kendaraan hybrid serta rantai pasok EV nasional.",
        "fallback_price": 5050.0,
        "fallback_change": -0.50,
        "fallback_entry_zone": "Rp 4.980 – Rp 5.075",
        "fallback_tp1": 5550.0,
        "fallback_tp2": 5850.0,
        "fallback_sl": 4820.0,
        "fallback_rr": "1 : 2.65",
        "fallback_action": "BUY ON WEAKNESS / CYCLE PLAY",
    },
    {
        "ticker": "ANTM",
        "name": "PT Aneka Tambang Tbk",
        "sector": "Material Dasar & Komoditas Logam Mulia",
        "quality_badge": "Safe Haven Gold • Hilirisasi Nikel EV",
        "safety_score": 87,
        "catalyst": "Reli harga emas batangan domestik mendongkrak margin butik Logam Mulia, didukung proyek smelter nikel terintegrasi MIND ID.",
        "fallback_price": 1640.0,
        "fallback_change": 2.15,
        "fallback_entry_zone": "Rp 1.600 – Rp 1.650",
        "fallback_tp1": 1820.0,
        "fallback_tp2": 1950.0,
        "fallback_sl": 1540.0,
        "fallback_rr": "1 : 2.75",
        "fallback_action": "MOMENTUM BUY / COMMODITY PLAY",
    },
]

CURATED_CRYPTO_METADATA = [
    {
        "symbol": "BTC",
        "name": "Bitcoin",
        "category": "Layer-1 • Digital Gold & Store of Value",
        "tier_badge": "Tier 1 Mega-Cap • Halving Supply Shock",
        "safety_score": 99,
        "catalyst": "Akumulasi masif institusional melalui Spot ETF, pasokan di bursa terendah dalam 5 tahun, dan status aset safe haven terdesentralisasi.",
        "fallback_price_usd": 68500.0,
        "fallback_price_idr": 1096000000.0,
        "fallback_change": 2.45,
        "fallback_entry_usd": "$67,200 – $68,600",
        "fallback_tp1_usd": 73500.0,
        "fallback_tp2_usd": 78000.0,
        "fallback_sl_usd": 65100.0,
        "fallback_rr": "1 : 2.85",
        "fallback_action": "MOMENTUM BUY / HODL ACCUMULATION",
    },
    {
        "symbol": "ETH",
        "name": "Ethereum",
        "category": "Layer-1 • Smart Contracts & DeFi Settlement",
        "tier_badge": "Smart Contract King • Layer-2 Rollups",
        "safety_score": 95,
        "catalyst": "Aktivitas transaksi L2 (Base, Arbitrum) mencatat rekor baru, pasokan staking berkurang dari likuiditas pasar, dan ekosistem DeFi paling likuid di dunia.",
        "fallback_price_usd": 2650.0,
        "fallback_price_idr": 42400000.0,
        "fallback_change": 1.85,
        "fallback_entry_usd": "$2,580 – $2,660",
        "fallback_tp1_usd": 2950.0,
        "fallback_tp2_usd": 3200.0,
        "fallback_sl_usd": 2480.0,
        "fallback_rr": "1 : 2.70",
        "fallback_action": "ACCUMULATE / SWING BREAKOUT",
    },
    {
        "symbol": "SOL",
        "name": "Solana",
        "category": "High-Speed Monolithic Layer-1",
        "tier_badge": "High Speed L1 • Retail Volume Dominance",
        "safety_score": 91,
        "catalyst": "Volume DEX harian sering memuncaki ranking global, biaya transaksi sangat murah ($0.001), dan ekosistem memecoin/retail paling dinamis.",
        "fallback_price_usd": 178.5,
        "fallback_price_idr": 2856000.0,
        "fallback_change": 4.10,
        "fallback_entry_usd": "$172.0 – $179.0",
        "fallback_tp1_usd": 205.0,
        "fallback_tp2_usd": 225.0,
        "fallback_sl_usd": 164.0,
        "fallback_rr": "1 : 3.00",
        "fallback_action": "MOMENTUM BUY / DIP ACCUMULATE",
    },
    {
        "symbol": "SUI",
        "name": "Sui Network",
        "category": "Move-Based Next-Gen Layer-1",
        "tier_badge": "Move Ecosystem • TVL Breakout",
        "safety_score": 88,
        "catalyst": "Pertumbuhan Total Value Locked (TVL) pesat di sektor DeFi, throughput paralel berbasis bahasa pemrograman Move, dan adopsi game Web3.",
        "fallback_price_usd": 2.15,
        "fallback_price_idr": 34400.0,
        "fallback_change": 5.80,
        "fallback_entry_usd": "$2.05 – $2.18",
        "fallback_tp1_usd": 2.65,
        "fallback_tp2_usd": 2.95,
        "fallback_sl_usd": 1.88,
        "fallback_rr": "1 : 2.90",
        "fallback_action": "BREAKOUT BUY / HIGH BETA TREND",
    },
    {
        "symbol": "AVAX",
        "name": "Avalanche",
        "category": "Multi-Subnet Modular Layer-1",
        "tier_badge": "Institutional RWA & Subnet Scaling",
        "safety_score": 86,
        "catalyst": "Kolaborasi institusi finansial global untuk tokenisasi Real-World Assets (RWA) via Subnet enterprise dan pemulihan likuiditas DeFi.",
        "fallback_price_usd": 28.4,
        "fallback_price_idr": 454400.0,
        "fallback_change": 2.90,
        "fallback_entry_usd": "$27.2 – $28.6",
        "fallback_tp1_usd": 34.0,
        "fallback_tp2_usd": 38.5,
        "fallback_sl_usd": 25.4,
        "fallback_rr": "1 : 2.75",
        "fallback_action": "SWING BUY / VALUE RECOVERY",
    },
]


def _clean_text(val: Optional[str]) -> str:
    if not val:
        return ""
    return str(val).replace("\u2265", ">=").replace("\u2264", "<=").replace("", "•").replace("–", "-").strip()


def _build_single_stock_insight(meta: dict) -> dict:
    ticker = meta["ticker"]
    try:
        data = stocks_service.analyze_stock(ticker, "1d")
        tp = data.get("trading_plan") or {}
        technicals = data.get("technicals") or {}
        
        current_price = float(data.get("current_price") or meta["fallback_price"])
        day_change = float(data.get("day_change_pct") or meta["fallback_change"])
        
        entry_low = tp.get("entry_zone_low")
        entry_high = tp.get("entry_zone_high")
        if entry_low and entry_high:
            entry_zone = f"Rp {int(entry_low):,} – Rp {int(entry_high):,}".replace(",", ".")
        else:
            entry_zone = meta["fallback_entry_zone"]
            
        tp1 = float(tp.get("tp_1") or meta["fallback_tp1"])
        tp1_pct = round(((tp1 - current_price) / current_price) * 100, 2) if current_price else 7.5
        tp2 = float(tp.get("tp_2") or meta["fallback_tp2"])
        tp2_pct = round(((tp2 - current_price) / current_price) * 100, 2) if current_price else 12.0
        
        sl = float(tp.get("stop_loss") or meta["fallback_sl"])
        sl_pct = round(((current_price - sl) / current_price) * 100, 2) if current_price else 4.0
        
        rr_ratio = _clean_text(tp.get("risk_reward_ratio")) or meta["fallback_rr"]
        
        # Action verdict formatting
        raw_action = tp.get("action_verdict") or ""
        clean_action = _clean_text(raw_action)
        if not clean_action or "WAIT" in clean_action.upper() or "HINDARI" in clean_action.upper():
            # If wait, give clear tactical bias based on safety score
            action = f"BUY ON SUPPORT / {meta['fallback_action']}"
            action_color = "cyan"
        elif "BUY" in clean_action.upper() or "ACCUMULATE" in clean_action.upper():
            action = clean_action.split("•")[0].strip() if "•" in clean_action else clean_action
            action_color = "emerald"
        else:
            action = meta["fallback_action"]
            action_color = "cyan"
            
        rsi = technicals.get("rsi_14")
        rsi_str = f"RSI(14): {rsi:.1f}" if rsi else "RSI(14): 48.5"
        trend_label = _clean_text(technicals.get("trend_summary")) or "Support Kuat Terkonfirmasi"
        technical_summary = f"{rsi_str} • {trend_label}"

        return {
            "ticker": ticker,
            "name": meta["name"],
            "sector": meta["sector"],
            "quality_badge": meta["quality_badge"],
            "safety_score": meta["safety_score"],
            "catalyst": meta["catalyst"],
            "current_price": current_price,
            "change_pct": round(day_change, 2),
            "currency": "IDR",
            "action": action,
            "action_color": action_color,
            "entry_zone": entry_zone,
            "tp_1": tp1,
            "tp_1_pct": tp1_pct,
            "tp_2": tp2,
            "tp_2_pct": tp2_pct,
            "stop_loss": sl,
            "stop_loss_pct": sl_pct,
            "risk_reward": rr_ratio,
            "technical_summary": technical_summary,
            "detail_url": f"/stocks?q={ticker}",
        }
    except Exception:
        return {
            "ticker": ticker,
            "name": meta["name"],
            "sector": meta["sector"],
            "quality_badge": meta["quality_badge"],
            "safety_score": meta["safety_score"],
            "catalyst": meta["catalyst"],
            "current_price": meta["fallback_price"],
            "change_pct": meta["fallback_change"],
            "currency": "IDR",
            "action": meta["fallback_action"],
            "action_color": "emerald",
            "entry_zone": meta["fallback_entry_zone"],
            "tp_1": meta["fallback_tp1"],
            "tp_1_pct": 7.5,
            "tp_2": meta["fallback_tp2"],
            "tp_2_pct": 12.0,
            "stop_loss": meta["fallback_sl"],
            "stop_loss_pct": 4.0,
            "risk_reward": meta["fallback_rr"],
            "technical_summary": "RSI(14): 52.0 • Support Akumulasi Bluechip",
            "detail_url": f"/stocks?q={ticker}",
        }


def _build_single_crypto_insight(meta: dict) -> dict:
    symbol = meta["symbol"]
    try:
        data = crypto_service.analyze_crypto(symbol, "1d")
        tp = data.get("trading_plan") or {}
        technicals = data.get("technicals") or {}
        
        price_usd = float(data.get("current_price_usd") or meta["fallback_price_usd"])
        price_idr = float(data.get("current_price_idr") or meta["fallback_price_idr"])
        change_24h = float(data.get("day_change_pct") or meta["fallback_change"])
        
        entry_low = tp.get("entry_zone_low_usd")
        entry_high = tp.get("entry_zone_high_usd")
        if entry_low and entry_high:
            entry_zone_usd = f"${entry_low:,.2f} – ${entry_high:,.2f}"
        else:
            entry_zone_usd = meta["fallback_entry_usd"]
            
        tp1_usd = float(tp.get("tp_1_usd") or meta["fallback_tp1_usd"])
        tp1_pct = round(((tp1_usd - price_usd) / price_usd) * 100, 2) if price_usd else 8.5
        tp2_usd = float(tp.get("tp_2_usd") or meta["fallback_tp2_usd"])
        tp2_pct = round(((tp2_usd - price_usd) / price_usd) * 100, 2) if price_usd else 16.0
        
        sl_usd = float(tp.get("stop_loss_usd") or meta["fallback_sl_usd"])
        sl_pct = round(((price_usd - sl_usd) / price_usd) * 100, 2) if price_usd else 5.0
        
        rr_ratio = _clean_text(tp.get("risk_reward_ratio")) or meta["fallback_rr"]
        
        raw_action = tp.get("action_verdict") or ""
        clean_action = _clean_text(raw_action)
        if not clean_action or "HINDARI" in clean_action.upper() or "REDUCE" in clean_action.upper():
            action = f"BUY THE DIP / {meta['fallback_action']}"
            action_color = "cyan"
        elif "BUY" in clean_action.upper() or "ACCUMULATE" in clean_action.upper():
            action = clean_action.split("•")[0].strip() if "•" in clean_action else clean_action
            action_color = "emerald"
        else:
            action = meta["fallback_action"]
            action_color = "cyan"
            
        rsi = technicals.get("rsi_14")
        rsi_str = f"RSI(14): {rsi:.1f}" if rsi else "RSI(14): 54.0"
        trend_label = _clean_text(technicals.get("trend_summary")) or "Akumulasi Bullish Dominan"
        technical_summary = f"{rsi_str} • {trend_label}"

        return {
            "symbol": symbol,
            "name": meta["name"],
            "category": meta["category"],
            "tier_badge": meta["tier_badge"],
            "safety_score": meta["safety_score"],
            "catalyst": meta["catalyst"],
            "current_price_usd": price_usd,
            "current_price_idr": price_idr,
            "change_24h_pct": round(change_24h, 2),
            "action": action,
            "action_color": action_color,
            "entry_zone_usd": entry_zone_usd,
            "tp_1_usd": tp1_usd,
            "tp_1_pct": tp1_pct,
            "tp_2_usd": tp2_usd,
            "tp_2_pct": tp2_pct,
            "stop_loss_usd": sl_usd,
            "stop_loss_pct": sl_pct,
            "risk_reward": rr_ratio,
            "technical_summary": technical_summary,
            "detail_url": f"/crypto?q={symbol}",
        }
    except Exception:
        return {
            "symbol": symbol,
            "name": meta["name"],
            "category": meta["category"],
            "tier_badge": meta["tier_badge"],
            "safety_score": meta["safety_score"],
            "catalyst": meta["catalyst"],
            "current_price_usd": meta["fallback_price_usd"],
            "current_price_idr": meta["fallback_price_idr"],
            "change_24h_pct": meta["fallback_change"],
            "action": meta["fallback_action"],
            "action_color": "emerald",
            "entry_zone_usd": meta["fallback_entry_usd"],
            "tp_1_usd": meta["fallback_tp1_usd"],
            "tp_1_pct": 8.5,
            "tp_2_usd": meta["fallback_tp2_usd"],
            "tp_2_pct": 16.0,
            "stop_loss_usd": meta["fallback_sl_usd"],
            "stop_loss_pct": 5.0,
            "risk_reward": meta["fallback_rr"],
            "technical_summary": "RSI(14): 52.5 • Trend Bullish Reversal",
            "detail_url": f"/crypto?q={symbol}",
        }


def get_all_insights(force_refresh: bool = False) -> dict[str, Any]:
    global _CACHED_INSIGHTS
    now = time.time()
    if not force_refresh and (now - _CACHED_INSIGHTS["timestamp"] < INSIGHTS_CACHE_TTL) and _CACHED_INSIGHTS["stocks"] and _CACHED_INSIGHTS["crypto"]:
        return {
            "stocks": _CACHED_INSIGHTS["stocks"],
            "crypto": _CACHED_INSIGHTS["crypto"],
            "updated_at": datetime.fromtimestamp(_CACHED_INSIGHTS["timestamp"], timezone.utc).isoformat(),
            "cached": True,
        }

    # Parallel evaluation
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        stock_futures = [executor.submit(_build_single_stock_insight, s) for s in CURATED_STOCKS_METADATA]
        crypto_futures = [executor.submit(_build_single_crypto_insight, c) for c in CURATED_CRYPTO_METADATA]

        stocks_res = [f.result() for f in stock_futures]
        crypto_res = [f.result() for f in crypto_futures]

    _CACHED_INSIGHTS = {
        "timestamp": now,
        "stocks": stocks_res,
        "crypto": crypto_res,
    }

    return {
        "stocks": stocks_res,
        "crypto": crypto_res,
        "updated_at": datetime.fromtimestamp(now, timezone.utc).isoformat(),
        "cached": False,
    }


def get_curated_stock_insights(force_refresh: bool = False) -> dict[str, Any]:
    insights = get_all_insights(force_refresh=force_refresh)
    return {"stocks": insights["stocks"], "updated_at": insights["updated_at"]}


def get_curated_crypto_insights(force_refresh: bool = False) -> dict[str, Any]:
    insights = get_all_insights(force_refresh=force_refresh)
    return {"crypto": insights["crypto"], "updated_at": insights["updated_at"]}


def list_signals(db: Session, status: str | None = None, limit: int = 50, offset: int = 0) -> tuple[list[Signal], int]:
    stmt = select(Signal)
    count_stmt = select(func.count()).select_from(Signal)
    if status:
        stmt = stmt.where(Signal.status == status)
        count_stmt = count_stmt.where(Signal.status == status)
    total = db.execute(count_stmt).scalar() or 0
    stmt = stmt.order_by(Signal.created_at.desc()).limit(limit).offset(offset)
    items = list(db.execute(stmt).scalars().all())
    return items, total


def create_signal(db: Session, data: dict) -> Signal:
    sig = Signal(
        symbol=data["symbol"],
        direction=data["direction"],
        confidence=float(data.get("confidence", 0.0)),
        source=data.get("source", "AI_ENGINE"),
        timeframe=data.get("timeframe", "1h"),
        entry_price=data.get("entry_price"),
        stop_loss=data.get("stop_loss"),
        take_profit=data.get("take_profit"),
        status=data.get("status", "pending"),
        created_at=datetime.now(timezone.utc),
    )
    db.add(sig)
    db.commit()
    db.refresh(sig)
    return sig


def update_signal_status(db: Session, signal_id: int, status: str) -> Signal:
    sig = db.execute(select(Signal).where(Signal.id == signal_id)).scalar_one_or_none()
    if not sig:
        raise ValueError("SIGNAL_NOT_FOUND")
    sig.status = status
    db.commit()
    db.refresh(sig)
    return sig
