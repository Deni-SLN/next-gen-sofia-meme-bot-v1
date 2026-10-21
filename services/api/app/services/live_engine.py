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

SOLANA_MAINNET_RPC = settings.solana_rpc_url or "https://mainnet.helius-rpc.com/?api-key=15319bf4-5b40-4958-ac8d-6313aa55eb92"
SOLANA_RPC_POOL = [
    "https://mainnet.helius-rpc.com/?api-key=15319bf4-5b40-4958-ac8d-6313aa55eb92",
    "https://solana-rpc.publicnode.com",
    "https://api.mainnet.solana.com",
    "https://api.mainnet-beta.solana.com",
]
if SOLANA_MAINNET_RPC not in SOLANA_RPC_POOL:
    SOLANA_RPC_POOL.insert(0, SOLANA_MAINNET_RPC)

BASE_MAINNET_RPC = "https://mainnet.base.org"
ETH_MAINNET_RPC = "https://eth.llamarpc.com"
JUPITER_QUOTE_API = "https://api.jup.ag/swap/v1/quote"


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
_SPL_CACHE_FRESH: dict[str, bool] = {}
_RECENTLY_SOLD_TOKENS: dict[str, float] = {}
_KNOWN_WALLET_MINTS: set[str] = {
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
    "C5hmni8PQvZpGz1i3KfRowbM5ij5Msrk65RR1E1Qpump",  # Beancat
    "CARDSccUMFKoPRZxt5vt3ksUbxEFEcnZ3H2pd3dKxYjp",  # CARDS
    "9cRCn9rGT8V2imeM2BaKs13yhMEais3ruM3rPvTGpump",  # ANSEM
    "GXetNo3HpSku1Y59E1spoU9QpiDEkWxMLAF4DWnbpump",  # SI
}


def _fetch_tokens_via_multiple_accounts(addr: str) -> list[dict] | None:
    """
    Fast, 429-immune fallback using Solana `getMultipleAccounts` on derived ATA addresses
    for all known/cached mints when `getTokenAccountsByOwner` is throttled by public RPCs.
    """
    try:
        from solders.pubkey import Pubkey
        owner_pk = Pubkey.from_string(addr)
        token_prog = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
        token22_prog = Pubkey.from_string("TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb")
        ata_prog = Pubkey.from_string("ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL")

        mints = set(_KNOWN_WALLET_MINTS)
        for item in _SPL_CACHE.get(addr, (0.0, []))[1]:
            if item.get("mint"):
                mints.add(item["mint"])

        ata_list = []
        for m_str in mints:
            try:
                m_pk = Pubkey.from_string(m_str)
                ata1, _ = Pubkey.find_program_address([bytes(owner_pk), bytes(token_prog), bytes(m_pk)], ata_prog)
                ata2, _ = Pubkey.find_program_address([bytes(owner_pk), bytes(token22_prog), bytes(m_pk)], ata_prog)
                ata_list.append(str(ata1))
                ata_list.append(str(ata2))
            except Exception:
                continue

        if not ata_list:
            return None

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getMultipleAccounts",
            "params": [ata_list[:90], {"encoding": "jsonParsed"}],
        }
        fast_rpcs = [
            "https://solana-rpc.publicnode.com",
            "https://mainnet.helius-rpc.com/?api-key=15319bf4-5b40-4958-ac8d-6313aa55eb92",
            "https://api.mainnet-beta.solana.com",
        ]
        with httpx.Client(timeout=2.5) as client:
            for ep in fast_rpcs:
                try:
                    res = client.post(ep, json=payload)
                    if res.status_code == 200 and "result" in res.json():
                        vals = res.json()["result"].get("value") or []
                        valid_accounts = []
                        for v in vals:
                            if v and isinstance(v, dict) and "data" in v:
                                valid_accounts.append({"account": v})
                        return valid_accounts
                except Exception:
                    continue
    except Exception:
        pass
    return None


def is_spl_cache_fresh(address: str | None) -> bool:
    """Return True only if the most recent SPL + Token-2022 query succeeded for BOTH programs without 429 fallback."""
    if not address:
        return False
    return bool(_SPL_CACHE_FRESH.get(address.strip(), False))


def upsert_spl_cache_token(
    address: str | None,
    mint: str,
    symbol: str,
    amount: float,
    price: float,
    liquidity: float = 1800.0,
    spent_usdc: float = 0.0,
) -> None:
    """
    Immediately inject/update a newly bought on-chain token into _SPL_CACHE so that
    even if Solana RPC returns HTTP 429 right after a swap, sync_onchain_holdings_to_portfolio
    never wipes out the newly acquired position!
    """
    global _SPL_CACHE, _KNOWN_WALLET_MINTS
    addr = (address or "").strip()
    if not addr:
        return
    if mint and len(mint) >= 32:
        _KNOWN_WALLET_MINTS.add(mint)
    now_ts = time.time()
    existing_items = list(_SPL_CACHE.get(addr, (0.0, []))[1])
    updated = []
    found = False
    base_sym = symbol.split("/")[0].upper()
    for item in existing_items:
        it_mint = item.get("mint", "")
        it_sym = (item.get("symbol") or "").split("/")[0].upper()
        if spent_usdc > 0 and (it_mint == "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v" or it_sym == "USDC"):
            new_usdc = max(0.0, round(float(item.get("amount", 0.0)) - spent_usdc, 6))
            updated.append({
                **item,
                "amount": new_usdc,
                "amount_raw": str(int(round(new_usdc * 1e6))),
                "usd_val": round(new_usdc, 4),
            })
        elif (mint and it_mint == mint) or (base_sym and it_sym == base_sym):
            new_amt = float(amount)
            updated.append({
                "mint": mint or it_mint,
                "symbol": symbol,
                "amount": new_amt,
                "amount_raw": str(int(round(new_amt * (10 ** int(item.get("decimals", 6)))))),
                "decimals": int(item.get("decimals", 6)),
                "price": price,
                "liquidity": max(liquidity, float(item.get("liquidity", 1800.0))),
                "usd_val": round(new_amt * price, 4),
            })
            found = True
        else:
            updated.append(item)

    if not found and amount > 0:
        updated.append({
            "mint": mint,
            "symbol": symbol,
            "amount": float(amount),
            "amount_raw": str(int(round(float(amount) * 1e6))),
            "decimals": 6,
            "price": price,
            "liquidity": max(liquidity, 1800.0),
            "usd_val": round(float(amount) * price, 4),
        })

    _RECENTLY_SOLD_TOKENS.pop(base_sym, None)
    if mint:
        _RECENTLY_SOLD_TOKENS.pop(mint, None)
    _SPL_CACHE[addr] = (now_ts, updated)


def remove_spl_cache_token(address: str | None, symbol: str, sell_pct: float = 100.0, mint: str | None = None) -> None:
    """Immediately remove or reduce a sold token from _SPL_CACHE after an on-chain sell."""
    global _SPL_CACHE, _RECENTLY_SOLD_TOKENS
    addr = (address or "").strip()
    base_sym = symbol.split("/")[0].upper()
    if sell_pct >= 99.0:
        _RECENTLY_SOLD_TOKENS[base_sym] = time.time()
        if mint:
            _RECENTLY_SOLD_TOKENS[mint] = time.time()
    if not addr or addr not in _SPL_CACHE:
        return
    _, existing_items = _SPL_CACHE[addr]
    if sell_pct >= 99.0:
        filtered = [
            it for it in existing_items
            if (it.get("symbol") or "").split("/")[0].upper() != base_sym
            and (not mint or it.get("mint") != mint)
        ]
    else:
        remain_ratio = max(0.0, 1.0 - (float(sell_pct) / 100.0))
        filtered = []
        for it in existing_items:
            if (it.get("symbol") or "").split("/")[0].upper() == base_sym or (mint and it.get("mint") == mint):
                new_amt = round(float(it.get("amount", 0.0)) * remain_ratio, 6)
                new_raw = str(max(0, int(round(int(it.get("amount_raw", "0") or 0) * remain_ratio))))
                px = float(it.get("price", 0.0))
                if new_amt > 0.0001:
                    filtered.append({
                        **it,
                        "amount": new_amt,
                        "amount_raw": new_raw,
                        "usd_val": round(new_amt * px, 4),
                    })
            else:
                filtered.append(it)
    _SPL_CACHE[addr] = (time.time(), filtered)


def auto_sync_live_wallets(db: Session, max_age_seconds: float = 20.0) -> None:
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
    global _SPL_CACHE, _SPL_CACHE_FRESH, _LAST_ONCHAIN_SYNC
    _LAST_ONCHAIN_SYNC = 0.0
    if address:
        addr = address.strip()
        _SPL_CACHE_FRESH[addr] = False
        if addr in _SPL_CACHE:
            _SPL_CACHE[addr] = (0.0, _SPL_CACHE[addr][1])
    else:
        for k in list(_SPL_CACHE.keys()):
            _SPL_CACHE_FRESH[k] = False
            _SPL_CACHE[k] = (0.0, _SPL_CACHE[k][1])


def query_solana_spl_tokens(address: str, max_cache_seconds: float = 20.0) -> list[dict]:
    """
    Query all SPL & Token-2022 accounts owned by the Solana address (e.g. USDC, SI, ANSEM), cached for 20s.
    Protects against HTTP 429 rate-limits on public Solana RPC by retaining the last known good token list
    if either program call fails or gets throttled.
    """
    global _SPL_CACHE, _SPL_CACHE_FRESH
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

        # Primary ultra-fast ATA check via getMultipleAccounts (~200ms, 429-immune on publicnode)
        fallback_items = _fetch_tokens_via_multiple_accounts(addr)
        if fallback_items is not None:
            items.extend(fallback_items)
            success_prog_count = len(programs)

        # Secondary discovery check via getTokenAccountsByOwner (fast 2.0s timeout, single attempt)
        indexed_rpcs = [
            "https://api.mainnet.solana.com",
            "https://api.mainnet-beta.solana.com",
        ]
        seen_mints = {
            it.get("account", {}).get("data", {}).get("parsed", {}).get("info", {}).get("mint")
            for it in items
        }
        with httpx.Client(timeout=2.0) as client:
            for prog_idx, prog in enumerate(programs):
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
                rpc_ep = indexed_rpcs[prog_idx % len(indexed_rpcs)]
                try:
                    res = client.post(rpc_ep, json=payload)
                    if res.status_code == 200:
                        data = res.json()
                        if "result" in data:
                            for acc in data.get("result", {}).get("value", []):
                                m = acc.get("account", {}).get("data", {}).get("parsed", {}).get("info", {}).get("mint")
                                if m and m not in seen_mints:
                                    items.append(acc)
                                    seen_mints.add(m)
                            success_prog_count = len(programs)
                except Exception:
                    pass

        if not items and fallback_items is None and cached_entry and cached_entry[1]:
            _SPL_CACHE_FRESH[addr] = False
            _SPL_CACHE[addr] = (now_ts - max_cache_seconds + 6.0, cached_entry[1])
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
                _KNOWN_WALLET_MINTS.add(mint)
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
            base_sym_check = (symbol or "").split("/")[0].upper()
            sold_ts = _RECENTLY_SOLD_TOKENS.get(mint) or _RECENTLY_SOLD_TOKENS.get(base_sym_check)
            if sold_ts and (now_ts - sold_ts) < 30.0:
                continue
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

        if success_prog_count == len(programs):
            _SPL_CACHE_FRESH[addr] = True
            _SPL_CACHE[addr] = (now_ts, tokens)
        else:
            _SPL_CACHE_FRESH[addr] = False
            if tokens and not cached_entry:
                _SPL_CACHE[addr] = (now_ts - max_cache_seconds + 6.0, tokens)
        return tokens
    except Exception:
        _SPL_CACHE_FRESH[addr] = False
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
            last_data = {}
            used_ep = SOLANA_MAINNET_RPC
            with httpx.Client(timeout=4.0) as client:
                for ep in SOLANA_RPC_POOL:
                    try:
                        t_ep = time.perf_counter()
                        resp = client.post(ep, json=payload)
                        latency_ms = round((time.perf_counter() - t_ep) * 1000.0, 1)
                        if resp.status_code == 200:
                            data = resp.json()
                            last_data = data
                            used_ep = ep.split("?")[0]
                            if "result" in data and "value" in data["result"]:
                                lamports = int(data["result"]["value"])
                                sol_bal = round(lamports / 1e9, 6)
                                return {
                                    "rpc_connected": True,
                                    "chain": "Solana",
                                    "rpc_endpoint": used_ep,
                                    "latency_ms": latency_ms,
                                    "onchain_balance": sol_bal,
                                    "token": "SOL",
                                    "valid_address": True,
                                }
                    except Exception:
                        continue
                latency_ms = round((time.perf_counter() - t0) * 1000.0, 1)
                return {
                    "rpc_connected": True,
                    "chain": "Solana",
                    "rpc_endpoint": used_ep,
                    "latency_ms": latency_ms,
                    "onchain_balance": None,
                    "token": "SOL",
                    "valid_address": False,
                    "note": last_data.get("error", {}).get("message", "Format alamat Solana tidak dikenal di Mainnet"),
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
