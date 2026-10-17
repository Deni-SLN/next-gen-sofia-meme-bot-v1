import time
from datetime import datetime, timezone, timedelta
import httpx

WIB_TZ = timezone(timedelta(hours=7))

# Supported timeframes for Trading Plan (Entry, TP & SL)
SUPPORTED_TIMEFRAMES = {
    "15m": {
        "id": "15m",
        "label": "15 Menit",
        "horizon": "Scalping / Fast Intraday (15 Menit)",
        "hold_duration": "15 – 90 Menit",
        "tp1_mult": 0.45,
        "tp2_mult": 0.85,
        "sl_mult": 0.38,
        "min_tp1_pct": 1.1,
        "min_tp2_pct": 2.2,
        "min_sl_pct": 0.9,
        "lookback_bars": 4,
    },
    "1h": {
        "id": "1h",
        "label": "1 Jam",
        "horizon": "Intraday / Day Trading (1 Jam)",
        "hold_duration": "2 Jam – 2 Hari Bursa",
        "tp1_mult": 0.85,
        "tp2_mult": 1.65,
        "sl_mult": 0.70,
        "min_tp1_pct": 2.0,
        "min_tp2_pct": 4.0,
        "min_sl_pct": 1.5,
        "lookback_bars": 8,
    },
    "1d": {
        "id": "1d",
        "label": "1 Hari",
        "horizon": "Swing Trading Harian (1 Hari)",
        "hold_duration": "3 – 10 Hari Bursa",
        "tp1_mult": 1.80,
        "tp2_mult": 3.40,
        "sl_mult": 1.45,
        "min_tp1_pct": 3.8,
        "min_tp2_pct": 8.0,
        "min_sl_pct": 3.0,
        "lookback_bars": 20,
    },
    "1w": {
        "id": "1w",
        "label": "1 Minggu",
        "horizon": "Swing Mingguan (1 Minggu)",
        "hold_duration": "2 – 6 Minggu",
        "tp1_mult": 3.20,
        "tp2_mult": 6.00,
        "sl_mult": 2.30,
        "min_tp1_pct": 6.8,
        "min_tp2_pct": 13.5,
        "min_sl_pct": 5.0,
        "lookback_bars": 45,
    },
    "1mo": {
        "id": "1mo",
        "label": "1 Bulan",
        "horizon": "Position / Trend Bulanan (1 Bulan)",
        "hold_duration": "1 – 4 Bulan",
        "tp1_mult": 5.20,
        "tp2_mult": 9.80,
        "sl_mult": 3.50,
        "min_tp1_pct": 11.5,
        "min_tp2_pct": 22.0,
        "min_sl_pct": 7.5,
        "lookback_bars": 90,
    },
    "1y": {
        "id": "1y",
        "label": "1 Tahun",
        "horizon": "Investasi & Dividen Tahunan (1 Tahun)",
        "hold_duration": "6 – 12+ Bulan",
        "tp1_mult": 9.00,
        "tp2_mult": 16.50,
        "sl_mult": 5.50,
        "min_tp1_pct": 20.0,
        "min_tp2_pct": 36.0,
        "min_sl_pct": 12.0,
        "lookback_bars": 250,
    },
}

# Popular IDX tickers for quick-pick chips & sector info
POPULAR_IDX_STOCKS = [
    {"code": "IHSG", "name": "Indeks Harga Saham Gabungan (BEI)", "sector": "Indeks Utama BEI"},
    {"code": "BBRI", "name": "Bank Rakyat Indonesia (Persero) Tbk", "sector": "Perbankan / Big Cap"},
    {"code": "BBCA", "name": "Bank Central Asia Tbk", "sector": "Perbankan / Big Cap"},
    {"code": "BMRI", "name": "Bank Mandiri (Persero) Tbk", "sector": "Perbankan / Big Cap"},
    {"code": "BBNI", "name": "Bank Negara Indonesia (Persero) Tbk", "sector": "Perbankan / Big Cap"},
    {"code": "TLKM", "name": "Telkom Indonesia (Persero) Tbk", "sector": "Telekomunikasi"},
    {"code": "ASII", "name": "Astra International Tbk", "sector": "Konglomerasi / Otomotif"},
    {"code": "ADRO", "name": "Alamtri Resources Indonesia Tbk", "sector": "Energi & Batubara"},
    {"code": "PTBA", "name": "Bukit Asam Tbk", "sector": "Energi & Batubara"},
    {"code": "ITMG", "name": "Indo Tambangraya Megah Tbk", "sector": "Energi & Batubara"},
    {"code": "ANTM", "name": "Aneka Tambang Tbk", "sector": "Emas & Nikel"},
    {"code": "PGAS", "name": "Perusahaan Gas Negara Tbk", "sector": "Energi & Gas"},
    {"code": "UNTR", "name": "United Tractors Tbk", "sector": "Alat Berat & Tambang"},
    {"code": "ICBP", "name": "Indofood CBP Sukses Makmur Tbk", "sector": "Konsumer"},
    {"code": "BREN", "name": "Barito Renewables Energy Tbk", "sector": "Energi Baru Terbarukan"},
    {"code": "GOTO", "name": "GoTo Gojek Tokopedia Tbk", "sector": "Teknologi"},
]

_STOCK_CACHE: dict[str, dict] = {}
_CACHE_TTL_SEC = 120  # 2 minutes


def _round_idx_tick(price: float, is_idx: bool = True, is_index: bool = False) -> float:
    """Round price to official Bursa Efek Indonesia (BEI) tick size (Fraksi Harga Saham)."""
    if not is_idx or is_index or price <= 0:
        return round(price, 2)
    p = round(price)
    if p < 200:
        return float(p)
    if p < 500:
        return float(round(p / 2) * 2)
    if p < 2000:
        return float(round(p / 5) * 5)
    if p < 5000:
        return float(round(p / 10) * 10)
    return float(round(p / 25) * 25)


def _compute_rsi(closes: list[float], period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    gains = []
    losses = []
    for i in range(1, len(closes)):
        delta = closes[i] - closes[i - 1]
        gains.append(max(0.0, delta))
        losses.append(max(0.0, -delta))

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100.0 - (100.0 / (1.0 + rs)), 2)


def _compute_ema(values: list[float], span: int) -> list[float]:
    if not values:
        return []
    k = 2.0 / (span + 1.0)
    ema = [values[0]]
    for v in values[1:]:
        ema.append(v * k + ema[-1] * (1.0 - k))
    return ema


def _compute_macd(closes: list[float]) -> tuple[float, float, float]:
    if len(closes) < 26:
        return 0.0, 0.0, 0.0
    ema12 = _compute_ema(closes, 12)
    ema26 = _compute_ema(closes, 26)
    macd_line = [a - b for a, b in zip(ema12, ema26)]
    signal_line = _compute_ema(macd_line, 9)
    hist = macd_line[-1] - signal_line[-1]
    return round(macd_line[-1], 2), round(signal_line[-1], 2), round(hist, 2)


def _normalize_ticker(raw_query: str) -> tuple[str, str, bool]:
    """
    Return (yahoo_symbol, clean_code, is_idx).
    If user enters 4-letter Indonesian stock code like 'BBRI', converts to 'BBRI.JK'.
    Supports 'IHSG' / '^JKSE' for Jakarta Composite Index.
    """
    q = (raw_query or "BBRI").strip().upper()
    if q in ("IHSG", "JKSE", "^JKSE", "COMPOSITE"):
        return "^JKSE", "IHSG", True
    if q.endswith(".JK"):
        code = q[:-3]
        return q, code, True
    us_common = {"AAPL", "NVDA", "TSLA", "MSFT", "GOOGL", "AMZN", "META", "AMD", "NFLX", "COIN", "MSTR"}
    if "." in q or "-" in q or q in us_common:
        return q, q, False
    if len(q) == 4 and q.isalpha():
        return f"{q}.JK", q, True
    return f"{q}.JK", q, True


def get_ihsg_overview(force_refresh: bool = False) -> dict:
    """Fetch live IHSG (^JKSE - Indeks Harga Saham Gabungan) market overview."""
    now_ts = time.time()
    cache_key = "__IHSG_OVERVIEW__"
    if not force_refresh and cache_key in _STOCK_CACHE:
        cached = _STOCK_CACHE[cache_key]
        if now_ts - cached["fetched_ts"] < _CACHE_TTL_SEC:
            return cached["payload"]

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
    }
    url = "https://query1.finance.yahoo.com/v8/finance/chart/%5EJKSE?range=1mo&interval=1d"
    try:
        with httpx.Client(timeout=8.0, follow_redirects=True, headers=headers) as client:
            resp = client.get(url)
            resp.raise_for_status()
            res = resp.json()["chart"]["result"][0]
            meta = res.get("meta", {})
            quote = (res.get("indicators", {}).get("quote") or [{}])[0]
            closes = [float(c) for c in (quote.get("close") or []) if c is not None]
            highs = [float(h) for h in (quote.get("high") or []) if h is not None]
            lows = [float(l) for l in (quote.get("low") or []) if l is not None]

            price = round(float(meta.get("regularMarketPrice") or (closes[-1] if closes else 7200.0)), 2)
            prev_close = round(float(closes[-2] if len(closes) >= 2 else (meta.get("chartPreviousClose") or price)), 2)
            change = round(price - prev_close, 2)
            change_pct = round((change / prev_close * 100.0), 2) if prev_close > 0 else 0.0
            day_low = round(float(meta.get("regularMarketDayLow") or (lows[-1] if lows else price)), 2)
            day_high = round(float(meta.get("regularMarketDayHigh") or (highs[-1] if highs else price)), 2)
            w52_low = round(float(meta.get("fiftyTwoWeekLow") or min(lows or [price])), 2)
            w52_high = round(float(meta.get("fiftyTwoWeekHigh") or max(highs or [price])), 2)

            ihsg_payload = {
                "code": "IHSG",
                "symbol": "^JKSE",
                "name": "Indeks Harga Saham Gabungan (BEI)",
                "price": price,
                "prev_close": prev_close,
                "change": change,
                "change_pct": change_pct,
                "day_low": day_low,
                "day_high": day_high,
                "w52_low": w52_low,
                "w52_high": w52_high,
                "status": "IHSG MENGUAT" if change >= 0 else "IHSG TERKOREKSI",
            }
            _STOCK_CACHE[cache_key] = {"fetched_ts": now_ts, "payload": ihsg_payload}
            return ihsg_payload
    except Exception:
        return {
            "code": "IHSG",
            "symbol": "^JKSE",
            "name": "Indeks Harga Saham Gabungan (BEI)",
            "price": 7250.0,
            "prev_close": 7220.0,
            "change": 30.0,
            "change_pct": 0.42,
            "day_low": 7205.0,
            "day_high": 7280.0,
            "w52_low": 6500.0,
            "w52_high": 7910.0,
            "status": "IHSG AKTIF",
        }


def _build_timeframe_trading_plan(
    tf_key: str,
    current_price: float,
    closes: list[float],
    highs: list[float],
    lows: list[float],
    atr_pct: float,
    w52_low: float,
    w52_high: float,
    is_idx: bool,
    is_index: bool,
) -> dict:
    """Compute Entry Zone, TP 1, TP 2, Stop Loss, Support/Resistance, and Trend Status for a specific timeframe."""
    tf_cfg = SUPPORTED_TIMEFRAMES.get(tf_key, SUPPORTED_TIMEFRAMES["1d"])
    lb = min(len(closes), tf_cfg["lookback_bars"])
    sub_closes = closes[-max(15, lb):]
    sub_highs = highs[-max(5, lb):]
    sub_lows = lows[-max(5, lb):]

    ma_fast = sum(closes[-min(10 if tf_key in ("15m", "1h") else 20, len(closes)):]) / min(
        10 if tf_key in ("15m", "1h") else 20, len(closes)
    )
    ma_mid = sum(closes[-min(25 if tf_key in ("15m", "1h") else 50, len(closes)):]) / min(
        25 if tf_key in ("15m", "1h") else 50, len(closes)
    )
    rsi_tf = _compute_rsi(sub_closes, min(14, max(5, len(sub_closes) - 2)))

    # Determine Bullish/Bearish status for this timeframe
    bull_pts = 0
    bear_pts = 0
    if current_price >= ma_fast:
        bull_pts += 2
    else:
        bear_pts += 2
    if current_price >= ma_mid:
        bull_pts += 2
    else:
        bear_pts += 2

    if rsi_tf < 34:
        bull_pts += 2
    elif rsi_tf > 70:
        bear_pts += 1
    elif rsi_tf >= 52:
        bull_pts += 1
    else:
        bear_pts += 1

    if bull_pts >= bear_pts + 2:
        trend_status = "BULLISH KUAT"
        trend_badge = "BULLISH"
        action_verdict = f"AKUMULASI / TREND FOLLOWING ({tf_cfg['label'].upper()})"
    elif bull_pts > bear_pts:
        trend_status = "BULLISH MODERAT"
        trend_badge = "BULLISH"
        action_verdict = f"BUY ON WEAKNESS ({tf_cfg['label'].upper()})"
    elif rsi_tf < 35:
        trend_status = "BEARISH • OVERSOLD REBOUND"
        trend_badge = "REBOUND WATCH"
        action_verdict = f"SPECULATIVE BUY DI SUPPORT ({tf_cfg['label'].upper()})"
    elif bear_pts >= bull_pts + 2:
        trend_status = "BEARISH / DISTRIBUSI"
        trend_badge = "BEARISH"
        action_verdict = f"WAIT & SEE DI SUPPORT ({tf_cfg['label'].upper()})"
    else:
        trend_status = "SIDEWAYS / NETRAL"
        trend_badge = "NETRAL"
        action_verdict = f"TRADING RANGE ({tf_cfg['label'].upper()})"

    # Calculate timeframe-specific percentage distances
    tp1_target_pct = max(tf_cfg["min_tp1_pct"] / 100.0, atr_pct * tf_cfg["tp1_mult"])
    tp2_target_pct = max(tf_cfg["min_tp2_pct"] / 100.0, atr_pct * tf_cfg["tp2_mult"])
    sl_target_pct = max(tf_cfg["min_sl_pct"] / 100.0, atr_pct * tf_cfg["sl_mult"])

    low_window = min(sub_lows) if sub_lows else current_price * (1.0 - sl_target_pct)
    high_window = max(sub_highs) if sub_highs else current_price * (1.0 + tp2_target_pct)

    support_1 = _round_idx_tick(
        max(w52_low * 0.95, min(low_window, current_price * (1.0 - sl_target_pct * 0.85))),
        is_idx,
        is_index,
    )
    support_2 = _round_idx_tick(
        max(w52_low * 0.90, support_1 * (1.0 - sl_target_pct * 0.9)),
        is_idx,
        is_index,
    )

    entry_ideal_low = _round_idx_tick(
        max(support_1, current_price * (1.0 - sl_target_pct * 0.45)),
        is_idx,
        is_index,
    )
    entry_ideal_high = _round_idx_tick(current_price, is_idx, is_index)
    if entry_ideal_low >= entry_ideal_high:
        entry_ideal_low = _round_idx_tick(current_price * (1.0 - max(0.005, sl_target_pct * 0.35)), is_idx, is_index)

    raw_tp1 = current_price * (1.0 + tp1_target_pct)
    tp_1 = _round_idx_tick(raw_tp1, is_idx, is_index)
    if tp_1 <= current_price:
        tp_1 = _round_idx_tick(current_price * 1.015 + (5 if is_idx else 0.5), is_idx, is_index)

    raw_tp2 = max(tp_1 * 1.02, current_price * (1.0 + tp2_target_pct))
    tp_2 = _round_idx_tick(raw_tp2, is_idx, is_index)
    if tp_2 <= tp_1:
        tp_2 = _round_idx_tick(tp_1 * 1.03 + (10 if is_idx else 1.0), is_idx, is_index)

    raw_sl = min(entry_ideal_low * 0.99, current_price * (1.0 - sl_target_pct))
    stop_loss = _round_idx_tick(raw_sl, is_idx, is_index)
    if stop_loss >= entry_ideal_low:
        stop_loss = _round_idx_tick(entry_ideal_low * 0.985 - (5 if is_idx else 0.5), is_idx, is_index)

    tp1_pct = round((tp_1 - current_price) / current_price * 100.0, 2) if current_price > 0 else 0.0
    tp2_pct = round((tp_2 - current_price) / current_price * 100.0, 2) if current_price > 0 else 0.0
    sl_pct = round((stop_loss - current_price) / current_price * 100.0, 2) if current_price > 0 else 0.0

    risk_amt = max(0.01, current_price - stop_loss)
    reward_amt = max(0.01, tp_2 - current_price)
    rr_ratio = round(reward_amt / risk_amt, 2)

    return {
        "timeframe": tf_key,
        "timeframe_label": tf_cfg["label"],
        "horizon": tf_cfg["horizon"],
        "hold_duration": tf_cfg["hold_duration"],
        "trend_status": trend_status,
        "trend_badge": trend_badge,
        "action_verdict": action_verdict,
        "entry_zone_low": entry_ideal_low,
        "entry_zone_high": entry_ideal_high,
        "support_1": support_1,
        "support_2": support_2,
        "resistance_1": tp_1,
        "resistance_2": tp_2,
        "tp_1": tp_1,
        "tp_1_pct": tp1_pct,
        "tp_2": tp_2,
        "tp_2_pct": tp2_pct,
        "stop_loss": stop_loss,
        "stop_loss_pct": sl_pct,
        "risk_reward_ratio": f"1 : {rr_ratio}",
    }


def analyze_stock(
    query: str = "BBRI",
    timeframe: str = "1d",
    force_refresh: bool = False,
) -> dict:
    yahoo_sym, clean_code, is_idx = _normalize_ticker(query)
    is_index = yahoo_sym.startswith("^")
    tf_norm = (timeframe or "1d").strip().lower()
    if tf_norm not in SUPPORTED_TIMEFRAMES:
        tf_norm = "1d"

    now_ts = time.time()

    if not force_refresh and yahoo_sym in _STOCK_CACHE:
        cached = _STOCK_CACHE[yahoo_sym]
        if now_ts - cached["fetched_ts"] < _CACHE_TTL_SEC:
            base_payload = dict(cached["payload"])
            tf_plans = base_payload.get("timeframes_plan", {})
            if tf_norm in tf_plans:
                base_payload["selected_timeframe"] = tf_norm
                base_payload["trading_plan"] = tf_plans[tf_norm]
            return base_payload

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
    }

    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(yahoo_sym) if 'urllib' in globals() else yahoo_sym.replace('^', '%5E')}?range=3y&interval=1d&events=div"
    with httpx.Client(timeout=10.0, follow_redirects=True, headers=headers) as client:
        resp = client.get(url)
        if resp.status_code != 200 and is_idx and not is_index:
            alt_url = f"https://query1.finance.yahoo.com/v8/finance/chart/{clean_code}?range=3y&interval=1d&events=div"
            resp = client.get(alt_url)
            if resp.status_code == 200:
                yahoo_sym = clean_code
                is_idx = False

        if resp.status_code != 200:
            raise ValueError(f"Kode saham '{clean_code}' tidak ditemukan di Bursa Efek Indonesia (BEI) maupun bursa global.")

        raw = resp.json()

    results = raw.get("chart", {}).get("result")
    if not results:
        raise ValueError(f"Data pasar untuk '{clean_code}' tidak tersedia.")

    data = results[0]
    meta = data.get("meta", {})
    timestamps = data.get("timestamp", []) or []
    quote = (data.get("indicators", {}).get("quote") or [{}])[0]

    raw_closes = quote.get("close", []) or []
    raw_highs = quote.get("high", []) or []
    raw_lows = quote.get("low", []) or []
    raw_opens = quote.get("open", []) or []
    raw_vols = quote.get("volume", []) or []

    candles = []
    closes: list[float] = []
    highs: list[float] = []
    lows: list[float] = []
    volumes: list[int] = []

    for ts, o, h, l, c, v in zip(timestamps, raw_opens, raw_highs, raw_lows, raw_closes, raw_vols):
        if c is None or h is None or l is None:
            continue
        cf = float(c)
        hf = float(h)
        lf = float(l)
        of = float(o) if o is not None else cf
        vf = int(v or 0)
        closes.append(cf)
        highs.append(hf)
        lows.append(lf)
        volumes.append(vf)
        dt_str = datetime.fromtimestamp(ts, tz=WIB_TZ).strftime("%d %b %Y")
        candles.append({
            "date": dt_str,
            "timestamp": ts,
            "open": round(of, 2),
            "high": round(hf, 2),
            "low": round(lf, 2),
            "close": round(cf, 2),
            "volume": vf,
        })

    if not closes:
        raise ValueError(f"Data riwayat harga saham '{clean_code}' kosong.")

    current_price = float(meta.get("regularMarketPrice") or closes[-1])
    prev_close = float(closes[-2]) if len(closes) >= 2 else float(meta.get("chartPreviousClose") or current_price)
    day_change = current_price - prev_close
    day_change_pct = round((day_change / prev_close * 100.0), 2) if prev_close > 0 else 0.0

    def _pct_since(days_back: int) -> float:
        if len(closes) > days_back and closes[-1 - days_back] > 0:
            base = closes[-1 - days_back]
            return round((current_price - base) / base * 100.0, 2)
        return 0.0

    perf_1w = _pct_since(5)
    perf_1m = _pct_since(21)
    perf_3m = _pct_since(63)
    perf_1y = _pct_since(min(250, len(closes) - 1))

    # Moving Averages
    ma20 = round(sum(closes[-20:]) / min(20, len(closes)), 2)
    ma50 = round(sum(closes[-50:]) / min(50, len(closes)), 2)
    ma200 = round(sum(closes[-200:]) / min(200, len(closes)), 2)

    # RSI (14) & MACD
    rsi14 = _compute_rsi(closes[-60:], 14)
    macd_val, macd_sig, macd_hist = _compute_macd(closes[-90:])

    # ATR / Daily volatility (last 14 candles)
    recent_ranges = [max(0.0, h - l) for h, l in zip(highs[-14:], lows[-14:])]
    atr14 = sum(recent_ranges) / len(recent_ranges) if recent_ranges else current_price * 0.02
    atr_pct = max(0.015, min(0.08, atr14 / current_price if current_price > 0 else 0.025))

    w52_high = float(meta.get("fiftyTwoWeekHigh") or max(highs[-250:]))
    w52_low = float(meta.get("fiftyTwoWeekLow") or min(lows[-250:]))

    avg_vol_20d = int(sum(volumes[-20:]) / min(20, len(volumes))) if volumes else 0
    latest_vol = volumes[-1] if volumes else 0
    vol_ratio = round(latest_vol / avg_vol_20d, 2) if avg_vol_20d > 0 else 1.0

    signals_notes = []
    if current_price >= ma20:
        signals_notes.append(f"Harga berada di atas MA-20 ({ma20:,.0f}), menandakan momentum jangka pendek positif.")
    else:
        signals_notes.append(f"Harga bergerak di bawah MA-20 ({ma20:,.0f}), menunjukkan tekanan jual jangka pendek.")

    if current_price >= ma50:
        signals_notes.append(f"Tren menengah di atas MA-50 ({ma50:,.0f}).")
    else:
        signals_notes.append(f"Tren menengah masih tertahan di bawah MA-50 ({ma50:,.0f}).")

    if current_price >= ma200:
        signals_notes.append(f"Tren jangka panjang (Major Trend) di atas MA-200 ({ma200:,.0f}).")
    else:
        signals_notes.append(f"Harga di bawah MA-200 ({ma200:,.0f}) — area diskon valuasi / fase konsolidasi bawah.")

    if rsi14 < 33:
        rsi_status = "OVERSOLD (Jenuh Jual • Potensi Rebound)"
        signals_notes.append(f"RSI-14 di level {rsi14} (Oversold), peluang pantulan teknikal (Buy on Weakness) terbuka.")
    elif rsi14 > 70:
        rsi_status = "OVERBOUGHT (Jenuh Beli • Rawan Profit Taking)"
        signals_notes.append(f"RSI-14 di level {rsi14} (Overbought), waspadai aksi ambil untung jangka pendek.")
    elif rsi14 >= 52:
        rsi_status = "BULLISH MOMENTUM (Akumulasi Sehat)"
    else:
        rsi_status = "WEAK / KONSOLIDASI"

    # Build Trading Plans for all 6 timeframes (15m, 1h, 1d, 1w, 1mo, 1y)
    timeframes_plan: dict[str, dict] = {}
    for tf_k in SUPPORTED_TIMEFRAMES:
        timeframes_plan[tf_k] = _build_timeframe_trading_plan(
            tf_key=tf_k,
            current_price=current_price,
            closes=closes,
            highs=highs,
            lows=lows,
            atr_pct=atr_pct,
            w52_low=w52_low,
            w52_high=w52_high,
            is_idx=is_idx,
            is_index=is_index,
        )

    active_plan = timeframes_plan.get(tf_norm, timeframes_plan["1d"])

    # Dividend Analysis (from 3-year dividend events in Yahoo Finance)
    div_events = data.get("events", {}).get("dividends", {}) or {}
    div_list = []
    by_year: dict[int, float] = {}
    cutoff_1y_ts = now_ts - (380 * 86400)
    ttm_dividend = 0.0

    for _, d_obj in div_events.items():
        amt = float(d_obj.get("amount") or 0.0)
        d_ts = int(d_obj.get("date") or 0)
        if amt <= 0 or d_ts <= 0:
            continue
        dt_d = datetime.fromtimestamp(d_ts, tz=WIB_TZ)
        yr = dt_d.year
        by_year[yr] = by_year.get(yr, 0.0) + amt
        if d_ts >= cutoff_1y_ts:
            ttm_dividend += amt
        div_list.append({
            "date": dt_d.strftime("%d %b %Y"),
            "year": yr,
            "timestamp": d_ts,
            "amount": round(amt, 2),
            "yield_at_current_pct": round((amt / current_price) * 100.0, 2) if current_price > 0 else 0.0,
        })

    div_list.sort(key=lambda x: x["timestamp"], reverse=True)

    annual_totals = list(by_year.values())
    avg_annual_dividend = round(sum(annual_totals) / len(annual_totals), 2) if annual_totals else 0.0
    effective_annual_div = round(ttm_dividend if ttm_dividend > 0 else avg_annual_dividend, 2)
    dividend_yield_pct = round((effective_annual_div / current_price) * 100.0, 2) if current_price > 0 else 0.0

    company_name = meta.get("longName") or meta.get("shortName") or clean_code
    popular_match = next((p for p in POPULAR_IDX_STOCKS if p["code"] == clean_code), None)
    if popular_match and (not company_name or company_name == yahoo_sym):
        company_name = popular_match["name"]
    sector_label = popular_match["sector"] if popular_match else ("Emiten Bursa Efek Indonesia (BEI)" if is_idx else "Global Equity")

    lot_price = round(current_price * 100, 0) if (is_idx and not is_index) else round(current_price, 2)
    div_per_lot = round(effective_annual_div * 100, 0) if (is_idx and not is_index) else round(effective_annual_div, 2)

    if effective_annual_div > 0:
        signals_notes.append(
            f"Rutin membagikan dividen dengan estimasi ~Rp {effective_annual_div:,.0f}/lembar per tahun "
            f"(Dividend Yield ~{dividend_yield_pct:.2f}% • Setara Rp {div_per_lot:,.0f} per 1 Lot)."
        )
    elif is_index:
        signals_notes.append("Indeks Harga Saham Gabungan (IHSG) mencerminkan kinerja rata-rata seluruh saham di Bursa Efek Indonesia.")
    else:
        signals_notes.append("Emiten ini tidak memiliki riwayat pembagian dividen tunai dalam 3 tahun terakhir (fokus pertumbuhan/growth).")

    payload = {
        "code": clean_code,
        "yahoo_symbol": yahoo_sym,
        "name": company_name,
        "sector": sector_label,
        "exchange": "Bursa Efek Indonesia (IDX / BEI)" if is_idx else (meta.get("exchangeName") or "Global Exchange"),
        "currency": "IDR" if is_idx else (meta.get("currency") or "USD"),
        "is_idx": is_idx,
        "is_index": is_index,
        "current_price": current_price,
        "prev_close": prev_close,
        "day_change": round(day_change, 2),
        "day_change_pct": day_change_pct,
        "price_per_lot": lot_price,
        "performance": {
            "1w_pct": perf_1w,
            "1m_pct": perf_1m,
            "3m_pct": perf_3m,
            "1y_pct": perf_1y,
        },
        "range_52w": {
            "low": w52_low,
            "high": w52_high,
            "position_pct": round(
                ((current_price - w52_low) / max(1.0, (w52_high - w52_low))) * 100.0, 1
            ),
        },
        "selected_timeframe": tf_norm,
        "available_timeframes": [
            {"id": k, "label": v["label"], "horizon": v["horizon"], "hold_duration": v["hold_duration"]}
            for k, v in SUPPORTED_TIMEFRAMES.items()
        ],
        "trading_plan": active_plan,
        "timeframes_plan": timeframes_plan,
        "technicals": {
            "rsi_14": rsi14,
            "rsi_status": rsi_status,
            "ma_20": ma20,
            "ma_50": ma50,
            "ma_200": ma200,
            "macd": macd_val,
            "macd_signal": macd_sig,
            "macd_histogram": macd_hist,
            "atr_14": round(atr14, 2),
            "latest_volume": latest_vol,
            "avg_volume_20d": avg_vol_20d,
            "volume_ratio": vol_ratio,
        },
        "dividend": {
            "pays_dividend": effective_annual_div > 0,
            "annual_dividend_per_share": effective_annual_div,
            "avg_3y_dividend_per_share": avg_annual_dividend,
            "dividend_yield_pct": dividend_yield_pct,
            "annual_dividend_per_lot": div_per_lot,
            "frequency_per_year": len([d for d in div_list if d["timestamp"] >= cutoff_1y_ts]) or (1 if effective_annual_div > 0 else 0),
            "history": div_list[:8],
        },
        "summary_notes": signals_notes,
        "recent_candles": candles[-30:],
        "popular_stocks": POPULAR_IDX_STOCKS,
        "ihsg": get_ihsg_overview(force_refresh),
        "updated_at": datetime.now(WIB_TZ).strftime("%d %b %Y, %H:%M:%S WIB"),
    }

    _STOCK_CACHE[yahoo_sym] = {
        "fetched_ts": now_ts,
        "payload": payload,
    }
    return payload
