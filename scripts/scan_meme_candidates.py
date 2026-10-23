"""
Read-Only Meme Candidates Scanner for Sofia Market 3.9
Scans DexScreener and GMGN.ai Trench for verified meme coin candidates.
Safe, read-only script: no trade execution or private key access.
"""
import sys
import os
from pathlib import Path

# Add services/api to python path
current_dir = Path(__file__).resolve().parent
repo_root = current_dir.parent if current_dir.name == "scripts" else current_dir
api_dir = repo_root / "services" / "api"
if str(api_dir) not in sys.path:
    sys.path.insert(0, str(api_dir))

from app.services import market


def scan(min_safety: int = 60, min_liquidity: float = 1000.0, max_age_hours: float = 24.0):
    print("=" * 80)
    print("SOFIA MARKET 3.9 - MEME COIN CANDIDATE RADAR (READ-ONLY)")
    print("=" * 80)
    fx = market.get_fx_rate()
    usd_idr = fx.get("usd_idr", 16300.0)
    print(f"Kurs USD/IDR: Rp {usd_idr:,.0f}\n")

    pulse = market.get_live_pulse_feed()
    all_tokens = pulse.get("tokens", [])
    if not all_tokens:
        print("Tidak ada kandidat koin meme yang ditemukan pada tick saat ini.")
        return

    qualified = []
    for tok in all_tokens:
        score = int(tok.get("safety_score", 0))
        liq = float(tok.get("liquidity", 0))
        age_h = float(tok.get("age_hours", 999))
        if score >= min_safety and liq >= min_liquidity and age_h <= max_age_hours:
            qualified.append(tok)

    print(f"Total Ditemukan: {len(all_tokens)} | Lolos Kriteria: {len(qualified)}\n")
    print(f"{'Simbol':<12} {'Harga (USD)':<14} {'Likuiditas':<14} {'Skor':<6} {'Umur':<10} {'Launchpad':<12}")
    print("-" * 80)
    for tok in qualified:
        sym = tok.get("symbol", "-")[:10]
        px = tok.get("price", 0.0)
        px_str = f"${px:.6f}" if px < 1 else f"${px:.2f}"
        liq_str = f"${tok.get('liquidity', 0):,.0f}"
        score = tok.get("safety_score", 0)
        age = tok.get("age", "-")
        lp = tok.get("launchpad", "Pump.fun")[:10]
        print(f"{sym:<12} {px_str:<14} {liq_str:<14} {score:<6} {age:<10} {lp:<12}")

    print("=" * 80)


if __name__ == "__main__":
    scan()
