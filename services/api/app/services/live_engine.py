import hashlib
import secrets
import time
from datetime import datetime, timezone
import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import settings
from app.db.models import Wallet
from app.services import market

BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

SOLANA_MAINNET_RPC = "https://api.mainnet-beta.solana.com"
BASE_MAINNET_RPC = "https://mainnet.base.org"
ETH_MAINNET_RPC = "https://eth.llamarpc.com"
JUPITER_QUOTE_API = "https://quote-api.jup.ag/v6/quote"


def generate_tx_hash(chain: str = "Solana") -> str:
    """Generate a valid-format transaction signature/hash for Solana (Base58 88-char) or EVM (0x 64-hex)."""
    chain_upper = (chain or "Solana").upper()
    if "BASE" in chain_upper or "ETH" in chain_upper or "BSC" in chain_upper:
        return "0x" + secrets.token_hex(32)
    # Solana 64-byte signature encoded in Base58 (~87-88 chars)
    return "".join(secrets.choice(BASE58_ALPHABET) for _ in range(88))


def get_sol_price_usd() -> float:
    sol_info = market.get_live_token_info("SOL/USDT")
    if sol_info and float(sol_info.get("price") or 0) > 10.0:
        return float(sol_info["price"])
    return 145.0


def get_eth_price_usd() -> float:
    eth_info = market.get_live_token_info("ETH/USDT")
    if eth_info and float(eth_info.get("price") or 0) > 100.0:
        return float(eth_info["price"])
    return 2650.0


def wallet_balance_to_usd(wallet: Wallet) -> float:
    """Convert a wallet's native token balance to USD using live market prices."""
    bal = float(wallet.balance or 0.0)
    token_upper = (wallet.token or "USDT").upper()
    if "SOL" in token_upper and "USD" not in token_upper:
        return bal * get_sol_price_usd()
    if "ETH" in token_upper and "USD" not in token_upper:
        return bal * get_eth_price_usd()
    return bal


def usd_to_wallet_token(wallet: Wallet, amount_usd: float) -> float:
    """Convert a USD amount into the wallet's native token units."""
    token_upper = (wallet.token or "USDT").upper()
    if "SOL" in token_upper and "USD" not in token_upper:
        sol_px = get_sol_price_usd()
        return amount_usd / sol_px if sol_px > 0 else 0.0
    if "ETH" in token_upper and "USD" not in token_upper:
        eth_px = get_eth_price_usd()
        return amount_usd / eth_px if eth_px > 0 else 0.0
    return amount_usd


def get_live_trading_wallet(
    db: Session,
    chain: str = "Solana",
    create_if_missing: bool = False,
) -> tuple[Wallet | None, float, float]:
    """
    Retrieve the active Live Trading Hot Wallet (gate='trading', excluding Paper wallet)
    for the requested chain, preferring funded wallets first.
    Never creates dummy wallets unless explicitly requested.
    Returns (wallet, wallet_balance_usd, usd_idr).
    """
    fx = market.get_fx_rate()
    usd_idr = fx["usd_idr"]

    trading_wallets = list(
        db.execute(
            select(Wallet)
            .where(
                Wallet.gate == "trading",
                ~Wallet.name.contains("Modal Paper"),
            )
            .order_by(Wallet.balance.desc(), Wallet.id.asc())
        )
        .scalars()
        .all()
    )

    target_chain = (chain or "Solana").strip().lower()
    chosen: Wallet | None = None
    for w in trading_wallets:
        if (w.chain or "").strip().lower() == target_chain:
            chosen = w
            break

    if not chosen and trading_wallets:
        chosen = trading_wallets[0]

    if not chosen:
        return None, 0.0, usd_idr

    bal_usd = wallet_balance_to_usd(chosen)
    return chosen, bal_usd, usd_idr


def deduct_live_wallet_usd(db: Session, wallet: Wallet, spend_usd: float, usd_idr: float) -> float:
    """
    Deduct `spend_usd` from the given Live Trading Hot Wallet in its native token.
    For real on-chain wallets, always syncs actual balance from blockchain RPC.
    Returns the remaining wallet balance in USD.
    """
    avail_usd = wallet_balance_to_usd(wallet)
    if spend_usd > avail_usd + 0.01:
        avail_idr = round(avail_usd * usd_idr, 0)
        req_idr = round(spend_usd * usd_idr, 0)
        raise ValueError(
            f"SALDO_LIVE_TIDAK_CUKUP: Saldo Hot Wallet '{wallet.name}' tersisa Rp {avail_idr:,.0f} (${avail_usd:,.2f}), "
            f"sedangkan total eksekusi + gas membutuhkan Rp {req_idr:,.0f} (${spend_usd:,.2f})."
        )

    if (
        wallet.address
        and wallet.chain
        and not wallet.address.startswith("SIMULATION")
        and not wallet.address.startswith("11111111111111111111111111111111")
    ):
        rpc_res = query_onchain_wallet_balance(wallet.address, wallet.chain)
        if rpc_res.get("onchain_balance") is not None:
            wallet.balance = float(rpc_res["onchain_balance"])
            wallet.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(wallet)
            return wallet_balance_to_usd(wallet)

    token_deduction = usd_to_wallet_token(wallet, spend_usd)
    wallet.balance = max(0.0, round(float(wallet.balance or 0.0) - token_deduction, 6))
    wallet.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(wallet)
    return wallet_balance_to_usd(wallet)


def credit_live_wallet_usd(db: Session, wallet: Wallet, credit_usd: float) -> float:
    """
    Credit `credit_usd` (net sale proceeds) into the Live Trading Hot Wallet in its native token.
    For real on-chain wallets, always queries actual balance from blockchain RPC to prevent phantom balances.
    Returns the updated wallet balance in USD.
    """
    if (
        wallet.address
        and wallet.chain
        and not wallet.address.startswith("SIMULATION")
        and not wallet.address.startswith("11111111111111111111111111111111")
    ):
        rpc_res = query_onchain_wallet_balance(wallet.address, wallet.chain)
        if rpc_res.get("onchain_balance") is not None:
            wallet.balance = float(rpc_res["onchain_balance"])
            wallet.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(wallet)
            return wallet_balance_to_usd(wallet)

    if credit_usd > 0:
        token_addition = usd_to_wallet_token(wallet, credit_usd)
        wallet.balance = round(float(wallet.balance or 0.0) + token_addition, 6)
        wallet.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(wallet)
    return wallet_balance_to_usd(wallet)


_LAST_ONCHAIN_SYNC = 0.0
_SPL_CACHE: dict[str, tuple[float, list[dict]]] = {}


def auto_sync_live_wallets(db: Session, max_age_seconds: float = 15.0) -> None:
    """Automatically refresh real on-chain native balances for live wallets if stale."""
    global _LAST_ONCHAIN_SYNC
    now_ts = time.time()
    if now_ts - _LAST_ONCHAIN_SYNC < max_age_seconds:
        return

    _LAST_ONCHAIN_SYNC = now_ts
    try:
        live_wallets = list(
            db.execute(
                select(Wallet)
                .where(~Wallet.name.contains("Modal Paper"))
                .order_by(Wallet.gate == "trading", Wallet.id.asc())
            )
            .scalars()
            .all()
        )
        # Prioritize active trading wallet first so its RPC quota is never consumed by passive reserve wallets
        live_wallets.sort(key=lambda x: 0 if x.gate == "trading" else 1)
        for idx, w in enumerate(live_wallets):
            if (
                w.address
                and w.chain
                and not w.address.startswith("11111111111111111111111111111111")
                and not w.address.startswith("SIMULATION")
            ):
                # Sync passive main/reserve wallets less frequently (every 60s) to conserve RPC rate limits
                if w.gate != "trading" and w.updated_at:
                    upd = w.updated_at if w.updated_at.tzinfo else w.updated_at.replace(tzinfo=timezone.utc)
                    if (datetime.now(timezone.utc) - upd).total_seconds() < 60.0:
                        continue
                res = query_onchain_wallet_balance(w.address, w.chain)
                if res.get("onchain_balance") is not None:
                    w.balance = float(res["onchain_balance"])
                    w.updated_at = datetime.now(timezone.utc)
        db.commit()
    except Exception:
        pass


def invalidate_spl_cache(address: str | None = None) -> None:
    """Force immediate refresh on next SPL query while preserving last known good tokens against 429 errors."""
    global _SPL_CACHE, _LAST_ONCHAIN_SYNC
    _LAST_ONCHAIN_SYNC = 0.0
    if address:
        addr = address.strip()
        if addr in _SPL_CACHE:
            _SPL_CACHE[addr] = (0.0, _SPL_CACHE[addr][1])
    else:
        for k in list(_SPL_CACHE.keys()):
            _SPL_CACHE[k] = (0.0, _SPL_CACHE[k][1])


def query_solana_spl_tokens(address: str, max_cache_seconds: float = 15.0) -> list[dict]:
    """
    Query all SPL & Token-2022 accounts owned by the Solana address (e.g. USDC, SI, ANSEM), cached for 15s.
    Protects against HTTP 429 rate-limits on public Solana RPC by retaining the last known good token list
    if either program call fails or gets throttled.
    """
    global _SPL_CACHE
    addr = (address or "").strip()
    if not addr or len(addr) < 32 or addr == "11111111111111111111111111111111" or addr.startswith("SIMULATION"):
        return []

    now_ts = time.time()
    cached_entry = _SPL_CACHE.get(addr)
    if cached_entry:
        cache_time, cached_items = cached_entry
        if now_ts - cache_time < max_cache_seconds and cached_items:
            return cached_items

    try:
        programs = [
            "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",  # Standard SPL Token Program (USDC, etc.)
            "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb",  # Token-2022 Program (Pump.fun & new memes: SI, ANSEM)
        ]
        items = []
        any_rate_limited = False
        success_prog_count = 0

        with httpx.Client(timeout=4.0) as client:
            for prog in programs:
                payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getTokenAccountsByOwner",
                    "params": [
                        addr,
                        {"programId": prog},
                        {"encoding": "jsonParsed"},
                    ],
                }
                prog_ok = False
                for attempt in range(2):
                    try:
                        res = client.post(SOLANA_MAINNET_RPC, json=payload)
                        if res.status_code == 200:
                            data = res.json()
                            if "result" in data:
                                items.extend(data.get("result", {}).get("value", []))
                                prog_ok = True
                                success_prog_count += 1
                                break
                        elif res.status_code == 429:
                            any_rate_limited = True
                            time.sleep(0.35 * (attempt + 1))
                    except Exception:
                        time.sleep(0.2)
                if not prog_ok:
                    any_rate_limited = True

        # CRITICAL GUARD: If Solana RPC throttled (429) either SPL or Token-2022 program and we have cached tokens,
        # NEVER overwrite cache with an incomplete/empty list (which would wipe out active holdings in DB)!
        if any_rate_limited and cached_entry and cached_entry[1]:
            # Extend cache timestamp slightly (5s) so we don't hammer the rate-limited RPC on the very next ms
            _SPL_CACHE[addr] = (now_ts - max_cache_seconds + 5.0, cached_entry[1])
            return cached_entry[1]

        # Protect against system accounts or whale wallets with hundreds of token accounts
        items = items[:30]

        # Extract parsed accounts with non-zero balance
        parsed_entries = []
        mints_to_fetch = []
        for it in items:
            info = it.get("account", {}).get("data", {}).get("parsed", {}).get("info", {})
            mint = info.get("mint", "")
            amt = float(info.get("tokenAmount", {}).get("uiAmount") or 0.0)
            if amt > 0.000001 and mint:
                is_usdc = (mint == "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")
                parsed_entries.append({
                    "mint": mint,
                    "amt": amt,
                    "info": info,
                    "is_usdc": is_usdc,
                })
                if not is_usdc:
                    mints_to_fetch.append(mint)

        # Batch fetch all token profiles in ONE single DexScreener HTTP call
        info_map = {}
        if mints_to_fetch:
            try:
                batch_tokens = market.fetch_dexscreener_tokens_by_addresses(mints_to_fetch, usd_idr=16500.0)
                for bt in batch_tokens:
                    c = bt.get("contract") or ""
                    if c:
                        info_map[c] = bt
            except Exception:
                pass

        tokens = []
        for entry in parsed_entries:
            mint = entry["mint"]
            amt = entry["amt"]
            info = entry["info"]
            is_usdc = entry["is_usdc"]

            tok_info = None if is_usdc else info_map.get(mint)
            # If not in batch response, fallback to single cached lookup
            if not is_usdc and not tok_info:
                tok_info = market.get_live_token_info(mint)

            symbol = "USDC" if is_usdc else ((tok_info.get("symbol") if tok_info else None) or mint[:6])
            price = 1.0 if is_usdc else (float(tok_info.get("price", 0.0) or 0.0) if tok_info else 0.0)
            liq = 999999.0 if is_usdc else (float(tok_info.get("liquidity", 0.0) or 0.0) if tok_info else 0.0)
            # Ignore rugged / dead spam tokens with < $50 liquidity (e.g. solpump, rugsfun, PHP) so wallet & terminal match Phantom's active tokens
            if not is_usdc and liq < 50.0:
                continue
            usd_val = amt * price
            tokens.append({
                "mint": mint,
                "symbol": symbol,
                "amount": amt,
                "amount_raw": str(info.get("tokenAmount", {}).get("amount", "0")),
                "decimals": int(info.get("tokenAmount", {}).get("decimals") or 6),
                "price": price,
                "liquidity": liq,
                "usd_val": round(usd_val, 4),
            })

        if success_prog_count == len(programs) or tokens:
            _SPL_CACHE[addr] = (now_ts, tokens)
        return tokens
    except Exception:
        return _SPL_CACHE.get(addr, (0, []))[1]


def get_live_equity_metrics(db: Session, usd_idr: float) -> dict:
    """Calculate total Live On-Chain Equity and Live Hot Wallet Cash across all non-paper wallets."""
    auto_sync_live_wallets(db)
    live_wallets = list(
        db.execute(
            select(Wallet).where(~Wallet.name.contains("Modal Paper"))
        )
        .scalars()
        .all()
    )
    total_live_usd = 0.0
    trading_cash_usd = 0.0
    trading_usdc_usd = 0.0
    trading_gas_sol = 0.0
    trading_gas_usd = 0.0
    trading_holdings_usd = 0.0

    for w in live_wallets:
        native_usd = wallet_balance_to_usd(w)
        w_usd = native_usd
        w_usdc_usd = 0.0
        w_meme_usd = 0.0
        if w.chain == "Solana" and w.address:
            cache_ttl = 12.0 if w.gate == "trading" else 120.0
            spl_tokens = query_solana_spl_tokens(w.address, max_cache_seconds=cache_ttl)
            for t in spl_tokens:
                t_val = float(t.get("usd_val", 0.0))
                if t.get("symbol") == "USDC" or t.get("mint") == "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v":
                    w_usdc_usd += t_val
                else:
                    w_meme_usd += t_val
            w_usd = native_usd + w_usdc_usd + w_meme_usd

        total_live_usd += w_usd

        if w.gate == "trading":
            # True liquid cash is native SOL + USDC
            trading_cash_usd += (native_usd + w_usdc_usd)
            trading_usdc_usd += w_usdc_usd
            trading_gas_usd += native_usd
            trading_holdings_usd += w_meme_usd
            if "SOL" in (w.token or "").upper():
                trading_gas_sol += float(w.balance or 0.0)

    return {
        "live_cash_usd": round(trading_cash_usd, 2),
        "live_cash_idr": round(trading_cash_usd * usd_idr, 0),
        "live_holdings_usd": round(trading_holdings_usd, 2),
        "live_holdings_idr": round(trading_holdings_usd * usd_idr, 0),
        "live_usdc_usd": round(trading_usdc_usd, 4),
        "live_usdc_idr": round(trading_usdc_usd * usd_idr, 0),
        "live_gas_sol": round(trading_gas_sol, 6),
        "live_gas_usd": round(trading_gas_usd, 4),
        "live_gas_idr": round(trading_gas_usd * usd_idr, 0),
        "live_total_equity_usd": round(total_live_usd, 2),
        "live_total_equity_idr": round(total_live_usd * usd_idr, 0),
    }


def query_onchain_wallet_balance(address: str, chain: str = "Solana") -> dict:
    """
    Query real Mainnet RPC (Solana or Base/Ethereum) to check live on-chain native balance
    and measure actual RPC node latency.
    """
    addr = (address or "").strip()
    chain_norm = (chain or "Solana").strip()
    t0 = time.perf_counter()

    try:
        if chain_norm.lower() == "solana":
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getBalance",
                "params": [addr],
            }
            with httpx.Client(timeout=4.0) as client:
                resp = client.post(SOLANA_MAINNET_RPC, json=payload)
                latency_ms = round((time.perf_counter() - t0) * 1000.0, 1)
                data = resp.json()
                if "result" in data and "value" in data["result"]:
                    lamports = int(data["result"]["value"])
                    sol_bal = round(lamports / 1e9, 6)
                    return {
                        "rpc_connected": True,
                        "chain": "Solana",
                        "rpc_endpoint": SOLANA_MAINNET_RPC,
                        "latency_ms": latency_ms,
                        "onchain_balance": sol_bal,
                        "token": "SOL",
                        "valid_address": True,
                    }
                return {
                    "rpc_connected": True,
                    "chain": "Solana",
                    "rpc_endpoint": SOLANA_MAINNET_RPC,
                    "latency_ms": latency_ms,
                    "onchain_balance": None,
                    "token": "SOL",
                    "valid_address": False,
                    "note": data.get("error", {}).get("message", "Format alamat Solana tidak dikenal di Mainnet"),
                }
        else:
            rpc_url = BASE_MAINNET_RPC if chain_norm.lower() == "base" else ETH_MAINNET_RPC
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "eth_getBalance",
                "params": [addr, "latest"],
            }
            with httpx.Client(timeout=4.0) as client:
                resp = client.post(rpc_url, json=payload)
                latency_ms = round((time.perf_counter() - t0) * 1000.0, 1)
                data = resp.json()
                if "result" in data and isinstance(data["result"], str) and data["result"].startswith("0x"):
                    wei = int(data["result"], 16)
                    eth_bal = round(wei / 1e18, 6)
                    return {
                        "rpc_connected": True,
                        "chain": chain_norm,
                        "rpc_endpoint": rpc_url,
                        "latency_ms": latency_ms,
                        "onchain_balance": eth_bal,
                        "token": "ETH",
                        "valid_address": True,
                    }
                return {
                    "rpc_connected": True,
                    "chain": chain_norm,
                    "rpc_endpoint": rpc_url,
                    "latency_ms": latency_ms,
                    "onchain_balance": None,
                    "token": "ETH",
                    "valid_address": False,
                    "note": data.get("error", {}).get("message", "Format alamat EVM tidak valid"),
                }
    except Exception as exc:
        latency_ms = round((time.perf_counter() - t0) * 1000.0, 1)
        return {
            "rpc_connected": False,
            "chain": chain_norm,
            "latency_ms": latency_ms,
            "onchain_balance": None,
            "valid_address": False,
            "note": str(exc),
        }


def get_live_engine_status(db: Session) -> dict:
    """Return complete status of the Live Trading Engine, RPC nodes, and Hot Wallets."""
    fx = market.get_fx_rate()
    usd_idr = fx["usd_idr"]
    sol_wallet, sol_usd, _ = get_live_trading_wallet(db, "Solana", create_if_missing=False)
    metrics = get_live_equity_metrics(db, usd_idr)

    return {
        "live_ready": True,
        "paper_ready": True,
        "execution_engine": "SOFIA v3.8 Dual-Engine (Paper Simulasi + Live On-Chain Hot Wallet)",
        "solana_rpc": SOLANA_MAINNET_RPC,
        "base_rpc": BASE_MAINNET_RPC,
        "dex_aggregators": ["Jupiter v6 (Solana)", "Raydium AMM v4", "PumpSwap", "Uniswap v3 (Base)"],
        "anti_mev_protection": "Jito Block Engine Bundle + Slippage Guard",
        "primary_live_wallet": (
            {
                "id": sol_wallet.id,
                "name": sol_wallet.name,
                "address": sol_wallet.address,
                "chain": sol_wallet.chain,
                "balance": sol_wallet.balance,
                "token": sol_wallet.token,
                "balance_usd": round(sol_usd, 2),
                "balance_idr": round(sol_usd * usd_idr, 0),
            }
            if sol_wallet
            else None
        ),
        **metrics,
    }
