from datetime import datetime, timezone
import time
from typing import Any, Dict, List, Optional
import urllib.parse
import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import GoldHolding
from app.services import market

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
}

TROY_OUNCE_TO_GRAM = 31.1034768

# Default Spread & Tax constants in Indonesia (PMK 48/2023 / PPh Pasal 22)
# Physical Gold (Antam / Hartadinata / UBS / Galeri24) retail minting premium above world spot,
# and buyback spread below retail buy price.
ANTAM_RETAIL_PREMIUM_PCT = 8.2
ANTAM_BUYBACK_SPREAD_PCT = 9.0

HARTADINATA_RETAIL_PREMIUM_PCT = 6.5
HARTADINATA_BUYBACK_SPREAD_PCT = 8.2

UBS_RETAIL_PREMIUM_PCT = 6.8
UBS_BUYBACK_SPREAD_PCT = 8.5

GALERI24_RETAIL_PREMIUM_PCT = 7.2
GALERI24_BUYBACK_SPREAD_PCT = 8.5

DIGITAL_RETAIL_PREMIUM_PCT = 1.5
DIGITAL_BUYBACK_SPREAD_PCT = 3.0

_GOLD_CACHE: Dict[str, Any] = {"ts": 0.0, "data": None}
GOLD_CACHE_TTL_SEC = 180  # 3 minutes


def _round_idr_500(val: float) -> int:
    """Round IDR price to nearest Rp 500 for realistic Logam Mulia pricing."""
    return int(round(val / 500.0) * 500)


def fetch_live_gold_market(force_refresh: bool = False) -> Dict[str, Any]:
    """Fetch live XAU/USD (GC=F) from Yahoo Finance and convert to IDR/gram + Antam/Hartadinata/UBS/Galeri24/Digital prices."""
    now = time.time()
    if not force_refresh and _GOLD_CACHE["data"] and (now - _GOLD_CACHE["ts"] < GOLD_CACHE_TTL_SEC):
        return _GOLD_CACHE["data"]

    fx_info = market.get_fx_rate()
    usd_idr = float(fx_info.get("usd_idr") or 16500.0)

    xau_usd = 2745.0
    prev_xau_usd = 2728.0
    day_high_usd = 2758.0
    day_low_usd = 2720.0
    history_points: List[Dict[str, Any]] = []
    source = "Yahoo Finance Live (XAU/USD • GC=F)"

    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{urllib.parse.quote('GC=F')}?range=1mo&interval=1d&includePrePost=false"
    )
    try:
        with httpx.Client(timeout=8.0, headers=HEADERS, follow_redirects=True) as client:
            resp = client.get(url)
            if resp.status_code == 200:
                payload = resp.json()
                results = payload.get("chart", {}).get("result") or []
                if results:
                    res0 = results[0]
                    meta = res0.get("meta") or {}
                    timestamps = res0.get("timestamp") or []
                    quote = (res0.get("indicators", {}).get("quote") or [{}])[0]
                    closes = quote.get("close") or []
                    highs = quote.get("high") or []
                    lows = quote.get("low") or []

                    valid_bars = []
                    for i, ts in enumerate(timestamps):
                        c = closes[i] if i < len(closes) else None
                        if c is None:
                            continue
                        h = highs[i] if i < len(highs) and highs[i] is not None else c
                        l = lows[i] if i < len(lows) and lows[i] is not None else c
                        valid_bars.append((ts, float(c), float(h), float(l)))

                    if valid_bars:
                        last_ts, last_c, last_h, last_l = valid_bars[-1]
                        xau_usd = float(meta.get("regularMarketPrice") or last_c)
                        prev_xau_usd = float(
                            valid_bars[-2][1]
                            if len(valid_bars) >= 2
                            else (meta.get("chartPreviousClose") or xau_usd)
                        )
                        day_high_usd = float(meta.get("regularMarketDayHigh") or last_h)
                        day_low_usd = float(meta.get("regularMarketDayLow") or last_l)

                        for ts, c, h, l in valid_bars[-30:]:
                            dt_str = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%d %b")
                            spot_gram = (c / TROY_OUNCE_TO_GRAM) * usd_idr
                            antam_gram = _round_idr_500(spot_gram * (1.0 + ANTAM_RETAIL_PREMIUM_PCT / 100.0))
                            buyback_gram = _round_idr_500(antam_gram * (1.0 - ANTAM_BUYBACK_SPREAD_PCT / 100.0))
                            hrta_gram = _round_idr_500(spot_gram * (1.0 + HARTADINATA_RETAIL_PREMIUM_PCT / 100.0))
                            history_points.append(
                                {
                                    "date": dt_str,
                                    "xau_usd": round(c, 2),
                                    "spot_idr_gram": round(spot_gram),
                                    "antam_buy_idr": antam_gram,
                                    "antam_buyback_idr": buyback_gram,
                                    "hartadinata_buy_idr": hrta_gram,
                                }
                            )
    except Exception:
        source = "Estimasi Pasar Global (XAU/USD Fallback)"

    change_usd = round(xau_usd - prev_xau_usd, 2)
    change_pct = round(((xau_usd - prev_xau_usd) / prev_xau_usd) * 100.0, 2) if prev_xau_usd > 0 else 0.0

    spot_idr_per_gram = (xau_usd / TROY_OUNCE_TO_GRAM) * usd_idr
    prev_spot_idr_per_gram = (prev_xau_usd / TROY_OUNCE_TO_GRAM) * usd_idr
    change_idr_per_gram = round(spot_idr_per_gram - prev_spot_idr_per_gram)

    antam_buy_idr = _round_idr_500(spot_idr_per_gram * (1.0 + ANTAM_RETAIL_PREMIUM_PCT / 100.0))
    antam_buyback_idr = _round_idr_500(antam_buy_idr * (1.0 - ANTAM_BUYBACK_SPREAD_PCT / 100.0))
    antam_change_idr = _round_idr_500(change_idr_per_gram * (1.0 + ANTAM_RETAIL_PREMIUM_PCT / 100.0))

    hartadinata_buy_idr = _round_idr_500(spot_idr_per_gram * (1.0 + HARTADINATA_RETAIL_PREMIUM_PCT / 100.0))
    hartadinata_buyback_idr = _round_idr_500(
        hartadinata_buy_idr * (1.0 - HARTADINATA_BUYBACK_SPREAD_PCT / 100.0)
    )
    hartadinata_change_idr = _round_idr_500(
        change_idr_per_gram * (1.0 + HARTADINATA_RETAIL_PREMIUM_PCT / 100.0)
    )

    ubs_buy_idr = _round_idr_500(spot_idr_per_gram * (1.0 + UBS_RETAIL_PREMIUM_PCT / 100.0))
    ubs_buyback_idr = _round_idr_500(ubs_buy_idr * (1.0 - UBS_BUYBACK_SPREAD_PCT / 100.0))

    galeri24_buy_idr = _round_idr_500(spot_idr_per_gram * (1.0 + GALERI24_RETAIL_PREMIUM_PCT / 100.0))
    galeri24_buyback_idr = _round_idr_500(galeri24_buy_idr * (1.0 - GALERI24_BUYBACK_SPREAD_PCT / 100.0))

    digital_buy_idr = _round_idr_500(spot_idr_per_gram * (1.0 + DIGITAL_RETAIL_PREMIUM_PCT / 100.0))
    digital_buyback_idr = _round_idr_500(digital_buy_idr * (1.0 - DIGITAL_BUYBACK_SPREAD_PCT / 100.0))

    # Denominations table (0.5g to 100g) with realistic smaller-bar minting regressive discount
    denominations_spec = [
        (0.5, 1.055),
        (1.0, 1.000),
        (2.0, 0.985),
        (3.0, 0.980),
        (5.0, 0.972),
        (10.0, 0.964),
        (25.0, 0.958),
        (50.0, 0.954),
        (100.0, 0.951),
    ]
    denominations = []
    for weight, mult in denominations_spec:
        buy_total = _round_idr_500(antam_buy_idr * weight * mult)
        buy_pph22_npwp = _round_idr_500(buy_total * 1.0025)  # PPh 22 pembelian 0.25%
        buyback_total = _round_idr_500(antam_buyback_idr * weight)
        hrta_buy_total = _round_idr_500(hartadinata_buy_idr * weight * mult)
        hrta_buyback_total = _round_idr_500(hartadinata_buyback_idr * weight)
        denominations.append(
            {
                "weight_grams": weight,
                "label": f"{weight:g} Gram",
                "antam_buy_idr": buy_total,
                "antam_buy_with_tax_idr": buy_pph22_npwp,
                "antam_buyback_idr": buyback_total,
                "hartadinata_buy_idr": hrta_buy_total,
                "hartadinata_buyback_idr": hrta_buyback_total,
            }
        )

    market_data = {
        "xau_usd": round(xau_usd, 2),
        "prev_xau_usd": round(prev_xau_usd, 2),
        "change_usd": change_usd,
        "change_pct": change_pct,
        "day_high_usd": round(day_high_usd, 2),
        "day_low_usd": round(day_low_usd, 2),
        "usd_idr": round(usd_idr, 2),
        "spot_idr_per_gram": round(spot_idr_per_gram),
        "change_idr_per_gram": change_idr_per_gram,
        "antam": {
            "brand": "Antam CertiEye",
            "buy_price_idr": antam_buy_idr,
            "buyback_price_idr": antam_buyback_idr,
            "spread_idr": antam_buy_idr - antam_buyback_idr,
            "spread_pct": ANTAM_BUYBACK_SPREAD_PCT,
            "change_idr": antam_change_idr,
        },
        "hartadinata": {
            "brand": "Hartadinata (EmasKita / HRTA)",
            "buy_price_idr": hartadinata_buy_idr,
            "buyback_price_idr": hartadinata_buyback_idr,
            "spread_idr": hartadinata_buy_idr - hartadinata_buyback_idr,
            "spread_pct": HARTADINATA_BUYBACK_SPREAD_PCT,
            "change_idr": hartadinata_change_idr,
        },
        "ubs": {
            "brand": "UBS Gold",
            "buy_price_idr": ubs_buy_idr,
            "buyback_price_idr": ubs_buyback_idr,
            "spread_idr": ubs_buy_idr - ubs_buyback_idr,
            "spread_pct": UBS_BUYBACK_SPREAD_PCT,
        },
        "galeri24": {
            "brand": "Galeri 24 (Pegadaian)",
            "buy_price_idr": galeri24_buy_idr,
            "buyback_price_idr": galeri24_buyback_idr,
            "spread_idr": galeri24_buy_idr - galeri24_buyback_idr,
            "spread_pct": GALERI24_BUYBACK_SPREAD_PCT,
        },
        "digital": {
            "brand": "Emas Digital (Pegadaian/Pluang/Treasury)",
            "buy_price_idr": digital_buy_idr,
            "buyback_price_idr": digital_buyback_idr,
            "spread_idr": digital_buy_idr - digital_buyback_idr,
            "spread_pct": DIGITAL_BUYBACK_SPREAD_PCT,
        },
        "denominations": denominations,
        "history_30d": history_points,
        "tax_rules": {
            "regulation": "PMK No. 48 Tahun 2023 (PPh Pasal 22 Emas Batangan)",
            "buyback_tax_threshold_idr": 10_000_000,
            "buyback_tax_npwp_pct": 1.5,
            "buyback_tax_non_npwp_pct": 3.0,
            "stamp_duty_threshold_idr": 5_000_000,
            "stamp_duty_idr": 10_000,
        },
        "source": source,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    _GOLD_CACHE["ts"] = now
    _GOLD_CACHE["data"] = market_data
    return market_data


def _brand_reference_prices(brand: str, market_data: Dict[str, Any]) -> Dict[str, float]:
    b = (brand or "Antam").strip().lower()
    if "hartadinata" in b or "hrta" in b or "emaskita" in b or "ardore" in b:
        ref = market_data["hartadinata"]
    elif "ubs" in b:
        ref = market_data["ubs"]
    elif "galeri" in b or "pegadaian" in b:
        ref = market_data["galeri24"]
    elif "digital" in b or "pluang" in b or "treasury" in b:
        ref = market_data["digital"]
    else:
        ref = market_data["antam"]
    return {
        "buy_price_idr": float(ref["buy_price_idr"]),
        "buyback_price_idr": float(ref["buyback_price_idr"]),
        "spread_pct": float(ref["spread_pct"]),
    }


def _normalize_cost_and_price_per_gram(
    weight_grams: float,
    buy_price_per_gram_idr: Optional[float],
    total_cost_idr: Optional[float],
    spot_idr_per_gram: float,
) -> tuple[float, float]:
    """
    Ensure per-gram price and total cost are never inverted when a user enters a per-gram price
    (e.g. Rp 2.700.000/g or Rp 2.790.000/g) while weight > 1g.
    """
    w = max(0.01, float(weight_grams or 1.0))
    raw_per_gram = float(buy_price_per_gram_idr or 0.0)
    raw_total = float(total_cost_idr or 0.0)

    # Minimum plausible per-gram price in modern IDR (around 45% of current spot, e.g. ~Rp 1.000.000/g)
    min_plausible_per_gram = max(900_000.0, spot_idr_per_gram * 0.42)
    max_plausible_per_gram = max(4_500_000.0, spot_idr_per_gram * 2.2)

    if raw_per_gram > 0 and raw_total > 0:
        # Check if raw_total was actually entered as a per-gram price and divided by w
        if (
            w > 1.0
            and raw_per_gram < min_plausible_per_gram
            and min_plausible_per_gram <= raw_total <= max_plausible_per_gram
        ):
            price_per_gram = raw_total
            cost = w * price_per_gram
        else:
            # Check if raw_per_gram is plausible
            if raw_per_gram >= min_plausible_per_gram and abs(raw_total - w * raw_per_gram) > 1000:
                price_per_gram = raw_per_gram
                cost = w * price_per_gram
            else:
                cost = raw_total
                price_per_gram = cost / w
    elif raw_per_gram > 0:
        price_per_gram = raw_per_gram
        cost = w * price_per_gram
    elif raw_total > 0:
        # If user sent only total_cost_idr (e.g. 2.700.000 for 10g), detect if it's actually a per-gram price!
        implied_per_gram = raw_total / w
        if (
            w > 1.0
            and implied_per_gram < min_plausible_per_gram
            and min_plausible_per_gram <= raw_total <= max_plausible_per_gram
        ):
            price_per_gram = raw_total
            cost = w * price_per_gram
        else:
            cost = raw_total
            price_per_gram = cost / w
    else:
        price_per_gram = spot_idr_per_gram
        cost = w * price_per_gram

    return round(price_per_gram), round(cost)


def simulate_sell_now(
    weight_grams: float,
    total_cost_idr: float,
    retail_buy_price_per_gram_idr: float,
    spread_pct: float = 9.0,
    tax_pct: Optional[float] = None,
    has_npwp: bool = True,
    include_stamp_duty: bool = True,
) -> Dict[str, Any]:
    """
    Calculate realistic 'Simulasi Jual Sekarang' (Buyback Simulation) with:
    - Gross Retail Value (Harga Etalase / Beli Baru)
    - Potongan Spread Buyback (Rp & %)
    - Nilai Buyback Kotor (Sebelum Pajak)
    - Potongan Pajak PPh 22 (Otomatis 1.5% NPWP / 3.0% Non-NPWP jika > Rp 10 juta, atau kustom)
    - Bea Materai (Rp 10.000 jika > Rp 5 juta)
    - Dana Bersih Diterima (Net Cash Received)
    - Untung / Rugi Bersih (Net Profit / Loss vs Modal Beli)
    """
    w = max(0.0, float(weight_grams or 0.0))
    cost = max(0.0, float(total_cost_idr or 0.0))
    retail_price = max(0.0, float(retail_buy_price_per_gram_idr or 0.0))
    sp_pct = max(0.0, min(50.0, float(spread_pct if spread_pct is not None else 9.0)))

    gross_retail_value_idr = round(w * retail_price)
    spread_deduction_idr = round(gross_retail_value_idr * (sp_pct / 100.0))
    effective_buyback_per_gram_idr = round(retail_price * (1.0 - sp_pct / 100.0))
    gross_buyback_value_idr = max(0, gross_retail_value_idr - spread_deduction_idr)

    # Determine PPh 22 Tax Rate
    if tax_pct is not None:
        applied_tax_pct = max(0.0, float(tax_pct))
        tax_note = f"Pajak Kustom ({applied_tax_pct:.2f}%)"
    else:
        if gross_buyback_value_idr > 10_000_000:
            applied_tax_pct = 1.5 if has_npwp else 3.0
            tax_note = (
                f"PPh 22 Buyback > Rp 10 Juta ({applied_tax_pct:.1f}% {'dengan NPWP' if has_npwp else 'tanpa NPWP'})"
            )
        else:
            applied_tax_pct = 0.0
            tax_note = "Bebas PPh 22 (Transaksi Buyback ≤ Rp 10 Juta)"

    tax_deduction_idr = round(gross_buyback_value_idr * (applied_tax_pct / 100.0))
    stamp_duty_idr = 10_000 if (include_stamp_duty and gross_buyback_value_idr > 5_000_000) else 0

    net_payout_idr = max(0, gross_buyback_value_idr - tax_deduction_idr - stamp_duty_idr)
    net_pnl_idr = round(net_payout_idr - cost)
    net_pnl_pct = round((net_pnl_idr / cost) * 100.0, 2) if cost > 0 else 0.0

    # Valuation vs Retail Price (before spread, e.g., nilai pasar etalase)
    market_pnl_idr = round(gross_retail_value_idr - cost)
    market_pnl_pct = round((market_pnl_idr / cost) * 100.0, 2) if cost > 0 else 0.0

    # Break-even buyback price per gram needed to recover modal + tax
    breakeven_buyback_per_gram_idr = round(cost / w) if w > 0 else 0

    status = "UNTUNG" if net_pnl_idr > 0 else "RUGI" if net_pnl_idr < 0 else "IMPAS"

    return {
        "weight_grams": round(w, 4),
        "total_cost_idr": round(cost),
        "retail_price_per_gram_idr": round(retail_price),
        "effective_buyback_per_gram_idr": effective_buyback_per_gram_idr,
        "gross_retail_value_idr": gross_retail_value_idr,
        "spread_pct": round(sp_pct, 2),
        "spread_deduction_idr": spread_deduction_idr,
        "gross_buyback_value_idr": gross_buyback_value_idr,
        "tax_pct": round(applied_tax_pct, 2),
        "tax_note": tax_note,
        "tax_deduction_idr": tax_deduction_idr,
        "stamp_duty_idr": stamp_duty_idr,
        "total_deductions_idr": spread_deduction_idr + tax_deduction_idr + stamp_duty_idr,
        "net_payout_idr": net_payout_idr,
        "net_pnl_idr": net_pnl_idr,
        "net_pnl_pct": net_pnl_pct,
        "market_pnl_idr": market_pnl_idr,
        "market_pnl_pct": market_pnl_pct,
        "breakeven_buyback_per_gram_idr": breakeven_buyback_per_gram_idr,
        "status": status,
    }


def get_gold_dashboard(db: Session, force_refresh: bool = False) -> Dict[str, Any]:
    """Return live gold market prices, user's manual gold portfolio, P/L status, and default simulation."""
    market_data = fetch_live_gold_market(force_refresh=force_refresh)
    spot_idr_per_gram = float(market_data.get("spot_idr_per_gram") or 2400000.0)
    rows = db.execute(select(GoldHolding).order_by(GoldHolding.id.desc())).scalars().all()

    holdings_list: List[Dict[str, Any]] = []
    total_weight_grams = 0.0
    total_cost_idr = 0.0
    total_retail_value_idr = 0.0
    total_gross_buyback_idr = 0.0
    dirty = False

    for h in rows:
        w = float(h.weight_grams or 0.0)
        buy_per_gram, cost = _normalize_cost_and_price_per_gram(
            weight_grams=w,
            buy_price_per_gram_idr=h.buy_price_per_gram_idr,
            total_cost_idr=h.total_cost_idr,
            spot_idr_per_gram=spot_idr_per_gram,
        )
        # Auto-heal DB record if it had inverted per-gram vs total cost
        if round(float(h.buy_price_per_gram_idr or 0)) != buy_per_gram or round(float(h.total_cost_idr or 0)) != cost:
            h.buy_price_per_gram_idr = buy_per_gram
            h.total_cost_idr = cost
            dirty = True

        ref = _brand_reference_prices(h.brand, market_data)
        current_retail_per_gram = ref["buy_price_idr"]
        current_buyback_per_gram = ref["buyback_price_idr"]

        retail_val = round(w * current_retail_per_gram)
        buyback_val = round(w * current_buyback_per_gram)

        # Item-level simulation
        item_sim = simulate_sell_now(
            weight_grams=w,
            total_cost_idr=cost,
            retail_buy_price_per_gram_idr=current_retail_per_gram,
            spread_pct=ref["spread_pct"],
            has_npwp=True,
            include_stamp_duty=False,
        )

        retail_pnl_idr = round(retail_val - cost)
        retail_pnl_pct = round((retail_pnl_idr / cost) * 100.0, 2) if cost > 0 else 0.0

        buyback_pnl_idr = round(buyback_val - cost)
        buyback_pnl_pct = round((buyback_pnl_idr / cost) * 100.0, 2) if cost > 0 else 0.0

        total_weight_grams += w
        total_cost_idr += cost
        total_retail_value_idr += retail_val
        total_gross_buyback_idr += buyback_val

        holdings_list.append(
            {
                "id": h.id,
                "label": h.label,
                "brand": h.brand,
                "weight_grams": round(w, 4),
                "buy_price_per_gram_idr": round(buy_per_gram),
                "total_cost_idr": round(cost),
                "current_retail_per_gram_idr": round(current_retail_per_gram),
                "current_buyback_per_gram_idr": round(current_buyback_per_gram),
                "retail_value_idr": retail_val,
                "buyback_value_idr": buyback_val,
                "retail_pnl_idr": retail_pnl_idr,
                "retail_pnl_pct": retail_pnl_pct,
                "buyback_pnl_idr": buyback_pnl_idr,
                "buyback_pnl_pct": buyback_pnl_pct,
                "net_sell_now_idr": item_sim["net_payout_idr"],
                "net_pnl_idr": item_sim["net_pnl_idr"],
                "net_pnl_pct": item_sim["net_pnl_pct"],
                "status": "UNTUNG" if buyback_pnl_idr > 0 else "RUGI" if buyback_pnl_idr < 0 else "IMPAS",
                "retail_status": "UNTUNG" if retail_pnl_idr > 0 else "RUGI" if retail_pnl_idr < 0 else "IMPAS",
                "purchased_at": h.purchased_at or "",
                "notes": h.notes or "",
                "created_at": h.created_at.isoformat() if h.created_at else "",
            }
        )

    if dirty:
        db.commit()

    avg_buy_per_gram_idr = round(total_cost_idr / total_weight_grams) if total_weight_grams > 0 else 0
    avg_retail_per_gram_idr = (
        round(total_retail_value_idr / total_weight_grams)
        if total_weight_grams > 0
        else market_data["antam"]["buy_price_idr"]
    )
    avg_spread_pct = (
        round((1.0 - (total_gross_buyback_idr / total_retail_value_idr)) * 100.0, 2)
        if total_retail_value_idr > 0
        else ANTAM_BUYBACK_SPREAD_PCT
    )

    portfolio_simulation = simulate_sell_now(
        weight_grams=total_weight_grams,
        total_cost_idr=total_cost_idr,
        retail_buy_price_per_gram_idr=avg_retail_per_gram_idr,
        spread_pct=avg_spread_pct,
        has_npwp=True,
        include_stamp_duty=True,
    )

    retail_total_pnl_idr = round(total_retail_value_idr - total_cost_idr)
    retail_total_pnl_pct = round((retail_total_pnl_idr / total_cost_idr) * 100.0, 2) if total_cost_idr > 0 else 0.0

    buyback_total_pnl_idr = round(total_gross_buyback_idr - total_cost_idr)
    buyback_total_pnl_pct = round((buyback_total_pnl_idr / total_cost_idr) * 100.0, 2) if total_cost_idr > 0 else 0.0

    portfolio_summary = {
        "holdings_count": len(holdings_list),
        "total_weight_grams": round(total_weight_grams, 4),
        "avg_buy_price_per_gram_idr": avg_buy_per_gram_idr,
        "total_cost_idr": round(total_cost_idr),
        "total_retail_value_idr": round(total_retail_value_idr),
        "total_gross_buyback_idr": round(total_gross_buyback_idr),
        "retail_pnl_idr": retail_total_pnl_idr,
        "retail_pnl_pct": retail_total_pnl_pct,
        "buyback_pnl_idr": buyback_total_pnl_idr,
        "buyback_pnl_pct": buyback_total_pnl_pct,
        "net_sell_now_idr": portfolio_simulation["net_payout_idr"],
        "net_pnl_idr": portfolio_simulation["net_pnl_idr"],
        "net_pnl_pct": portfolio_simulation["net_pnl_pct"],
        "status": portfolio_simulation["status"],
        "retail_status": "UNTUNG" if retail_total_pnl_idr > 0 else "RUGI" if retail_total_pnl_idr < 0 else "IMPAS",
        "simulation": portfolio_simulation,
    }

    return {
        "market": market_data,
        "portfolio": portfolio_summary,
        "holdings": holdings_list,
    }


def add_gold_holding(
    db: Session,
    weight_grams: float,
    buy_price_per_gram_idr: Optional[float] = None,
    total_cost_idr: Optional[float] = None,
    brand: str = "Antam",
    label: str = "",
    purchased_at: str = "",
    notes: str = "",
) -> GoldHolding:
    w = max(0.01, float(weight_grams or 0.0))
    market_data = fetch_live_gold_market(force_refresh=False)
    spot_idr_per_gram = float(market_data.get("spot_idr_per_gram") or 2400000.0)

    if (not buy_price_per_gram_idr or float(buy_price_per_gram_idr) <= 0) and (
        not total_cost_idr or float(total_cost_idr) <= 0
    ):
        ref = _brand_reference_prices(brand, market_data)
        price_per_gram = round(ref["buy_price_idr"])
        cost = round(w * price_per_gram)
    else:
        price_per_gram, cost = _normalize_cost_and_price_per_gram(
            weight_grams=w,
            buy_price_per_gram_idr=buy_price_per_gram_idr,
            total_cost_idr=total_cost_idr,
            spot_idr_per_gram=spot_idr_per_gram,
        )

    clean_brand = (brand or "Antam").strip()
    clean_label = (label or f"Emas {clean_brand} {w:g}g").strip()
    clean_date = (purchased_at or datetime.now(timezone.utc).strftime("%Y-%m-%d")).strip()

    item = GoldHolding(
        label=clean_label,
        brand=clean_brand,
        weight_grams=round(w, 4),
        buy_price_per_gram_idr=round(price_per_gram),
        total_cost_idr=round(cost),
        purchased_at=clean_date,
        notes=(notes or "").strip(),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_gold_holding(
    db: Session,
    holding_id: int,
    weight_grams: Optional[float] = None,
    buy_price_per_gram_idr: Optional[float] = None,
    total_cost_idr: Optional[float] = None,
    brand: Optional[str] = None,
    label: Optional[str] = None,
    purchased_at: Optional[str] = None,
    notes: Optional[str] = None,
) -> Optional[GoldHolding]:
    item = db.execute(select(GoldHolding).where(GoldHolding.id == holding_id)).scalar_one_or_none()
    if not item:
        return None

    market_data = fetch_live_gold_market(force_refresh=False)
    spot_idr_per_gram = float(market_data.get("spot_idr_per_gram") or 2400000.0)

    w = max(0.01, float(weight_grams if weight_grams is not None else item.weight_grams))
    if buy_price_per_gram_idr is not None or total_cost_idr is not None:
        price_per_gram, cost = _normalize_cost_and_price_per_gram(
            weight_grams=w,
            buy_price_per_gram_idr=buy_price_per_gram_idr,
            total_cost_idr=total_cost_idr,
            spot_idr_per_gram=spot_idr_per_gram,
        )
    else:
        price_per_gram = float(item.buy_price_per_gram_idr or 0.0)
        cost = round(w * price_per_gram)

    item.weight_grams = round(w, 4)
    item.buy_price_per_gram_idr = round(price_per_gram)
    item.total_cost_idr = round(cost)
    if brand is not None:
        item.brand = brand.strip() or item.brand
    if label is not None:
        item.label = label.strip() or f"Emas {item.brand} {w:g}g"
    if purchased_at is not None:
        item.purchased_at = purchased_at.strip()
    if notes is not None:
        item.notes = notes.strip()

    db.commit()
    db.refresh(item)
    return item


def delete_gold_holding(db: Session, holding_id: int) -> bool:
    item = db.execute(select(GoldHolding).where(GoldHolding.id == holding_id)).scalar_one_or_none()
    if not item:
        return False
    db.delete(item)
    db.commit()
    return True
