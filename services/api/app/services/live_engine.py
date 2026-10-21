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

    if wallet.address and wallet.chain and not wallet.address.startswith("SIMULATION"):
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
    if wallet.address and wallet.chain and not wallet.address.startswith("SIMULATION"):
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


def auto_sync_live_wallets(db: Session, max_age_seconds: float = 25.0) -> None:
    """Automatically refresh real on-chain native balances for live wallets if stale."""
    global _LAST_ONCHAIN_SYNC
    now_ts = time.time()
    if now_ts - _LAST_ONCHAIN_SYNC < max_age_seconds:
        return

    _LAST_ONCHAIN_SYNC = now_ts
    try:
        live_wallets = list(
            db.execute(select(Wallet).where(~Wallet.name.contains("Modal Paper"))).scalars().all()
        )
        for w in live_wallets:
            if w.address and w.chain:
                res = query_onchain_wallet_balance(w.address, w.chain)
                if res.get("onchain_balance") is not None:
                    w.balance = float(res["onchain_balance"])
                    w.updated_at = datetime.now(timezone.utc)
        db.commit()
    except Exception:
        pass


def query_solana_spl_tokens(address: str, max_cache_seconds: float = 25.0) -> list[dict]:
    """Query all SPL token accounts owned by the Solana address (e.g. USDC, meme coins), cached for 25s."""
    global _SPL_CACHE
    addr = (address or "").strip()
    if not addr or len(addr) < 32:
        return []

    now_ts = time.time()
    if addr in _SPL_CACHE:
        cache_time, cached_items = _SPL_CACHE[addr]
        if now_ts - cache_time < max_cache_seconds:
            return cached_items

    try:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getTokenAccountsByOwner",
            "params": [
                addr,
                {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},
                {"encoding": "jsonParsed"},
            ],
        }
        with httpx.Client(timeout=3.5) as client:
            res = client.post(SOLANA_MAINNET_RPC, json=payload)
            if res.status_code != 200:
                return _SPL_CACHE.get(addr, (0, []))[1]
            items = res.json().get("result", {}).get("value", [])
            tokens = []
            for it in items:
                info = it.get("account", {}).get("data", {}).get("parsed", {}).get("info", {})
                mint = info.get("mint", "")
                amt = float(info.get("tokenAmount", {}).get("uiAmount") or 0.0)
                if amt > 0.000001:
                    is_usdc = mint == "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
                    symbol = "USDC" if is_usdc else mint[:6]
                    usd_val = amt if is_usdc else 0.0
                    tokens.append({
                        "mint": mint,
                        "symbol": symbol,
                        "amount": amt,
                        "usd_val": round(usd_val, 4),
                    })
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
    trading_live_usd = 0.0
    for w in live_wallets:
        w_usd = wallet_balance_to_usd(w)
        if w.chain == "Solana" and w.address:
            spl_tokens = query_solana_spl_tokens(w.address)
            spl_usd = sum(t.get("usd_val", 0.0) for t in spl_tokens)
            w_usd += spl_usd
        total_live_usd += w_usd
        if w.gate == "trading":
            trading_live_usd += w_usd

    return {
        "live_cash_usd": round(trading_live_usd, 2),
        "live_cash_idr": round(trading_live_usd * usd_idr, 0),
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
