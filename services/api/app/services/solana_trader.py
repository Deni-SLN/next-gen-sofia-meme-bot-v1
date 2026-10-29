import os
import time
import base64
import logging
import httpx
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction

from app.core.config import settings

logger = logging.getLogger("sofia.solana_trader")

NATIVE_SOL_MINT = "So11111111111111111111111111111111111111112"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
SOLANA_SHIELD_RPC = getattr(settings, "solana_shield_rpc_url", None) or "https://eu.shield.fluxrpc.com?key=QrpekiPs1SeekuEwSi_25A"
SOLANA_MAINNET_RPC = settings.solana_rpc_url or "https://eu.fluxrpc.com?key=24252d08-b2ec-4d3f-8baf-9650199b77a9"
SOLANA_RPC_POOL = [
    SOLANA_SHIELD_RPC,
    SOLANA_MAINNET_RPC,
    "https://solana-rpc.publicnode.com",
    "https://mainnet.helius-rpc.com/?api-key=15319bf4-5b40-4958-ac8d-6313aa55eb92",
    "https://api.mainnet.solana.com",
]

JUPITER_QUOTE_ENDPOINTS = [
    "https://lite-api.jup.ag/swap/v1/quote",
    "https://api.jup.ag/swap/v1/quote",
]

JUPITER_SWAP_ENDPOINTS = [
    "https://lite-api.jup.ag/swap/v1/swap",
    "https://api.jup.ag/swap/v1/swap",
]


def get_trading_keypair() -> Keypair | None:
    """Load the user's Solana Trading Keypair from settings or environment variables."""
    priv = (settings.solana_trading_private_key or os.environ.get("SOFIA_SOLANA_TRADING_PRIVATE_KEY") or "").strip()
    if not priv:
        return None
    try:
        return Keypair.from_base58_string(priv)
    except Exception as e:
        logger.error(f"Failed to load Keypair from base58: {e}")
        return None


def get_jupiter_quote(
    input_mint: str,
    output_mint: str,
    amount_raw: int,
    slippage_bps: int = 150,
) -> dict:
    """Fetch best swap routing quote from Jupiter v6 Aggregator with automatic 429 retry."""
    params = {
        "inputMint": input_mint,
        "outputMint": output_mint,
        "amount": str(amount_raw),
        "slippageBps": int(slippage_bps),
    }

    last_err = None
    for attempt in range(3):
        for endpoint in JUPITER_QUOTE_ENDPOINTS:
            try:
                with httpx.Client(timeout=8.0) as client:
                    res = client.get(endpoint, params=params)
                    if res.status_code == 200:
                        return res.json()
                    last_err = f"{endpoint} -> {res.status_code}: {res.text[:160]}"
                    if res.status_code == 429:
                        time.sleep(0.8 * (attempt + 1))
            except Exception as exc:
                last_err = f"{endpoint} -> {exc}"
        time.sleep(0.5)

    raise RuntimeError(f"Gagal mengambil quote dari Jupiter: {last_err}")


def build_and_sign_swap_tx(quote_resp: dict, kp: Keypair) -> tuple[VersionedTransaction, str]:
    """Request serialized swap transaction from Jupiter and cryptographically sign it."""
    user_pubkey = str(kp.pubkey())
    payload = {
        "quoteResponse": quote_resp,
        "userPublicKey": user_pubkey,
        "wrapAndUnwrapSol": True,
        "dynamicComputeUnitLimit": True,
        "prioritizationFeeLamports": "auto",
    }

    swap_tx_b64 = None
    last_err = None
    for attempt in range(3):
        for endpoint in JUPITER_SWAP_ENDPOINTS:
            try:
                with httpx.Client(timeout=10.0) as client:
                    res = client.post(endpoint, json=payload)
                    if res.status_code == 200:
                        swap_tx_b64 = res.json().get("swapTransaction")
                        if swap_tx_b64:
                            break
                    last_err = f"{endpoint} -> {res.status_code}: {res.text[:160]}"
                    if res.status_code == 429:
                        time.sleep(0.8 * (attempt + 1))
            except Exception as exc:
                last_err = f"{endpoint} -> {exc}"
        if swap_tx_b64:
            break
        time.sleep(0.5)

    if not swap_tx_b64:
        raise RuntimeError(f"Gagal membuat transaksi swap Jupiter: {last_err}")

    raw_tx_bytes = base64.b64decode(swap_tx_b64)
    raw_tx = VersionedTransaction.from_bytes(raw_tx_bytes)

    # Sign using the user's trading Keypair
    signed_tx = VersionedTransaction(raw_tx.message, [kp])
    expected_sig = str(signed_tx.signatures[0])
    return signed_tx, expected_sig


def broadcast_transaction(
    signed_tx: VersionedTransaction,
    rpc_url: str = SOLANA_MAINNET_RPC,
    skip_preflight: bool = False,
) -> str:
    """Broadcast signed VersionedTransaction to Solana Mainnet RPC node (with multi-node failover for Alpenglow v4.3+)."""
    b64_tx = base64.b64encode(bytes(signed_tx)).decode("utf-8")
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "sendTransaction",
        "params": [
            b64_tx,
            {
                "encoding": "base64",
                "skipPreflight": skip_preflight,
                "preflightCommitment": "confirmed",
                "maxRetries": 3,
            },
        ],
    }

    endpoints = [rpc_url] + [ep for ep in SOLANA_RPC_POOL if ep != rpc_url]
    last_err = None
    with httpx.Client(timeout=15.0) as client:
        for ep in endpoints:
            try:
                res = client.post(ep, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    if "error" not in data and "result" in data:
                        return data["result"]
                    last_err = data.get("error")
                else:
                    last_err = f"HTTP {res.status_code}: {res.text[:120]}"
            except Exception as exc:
                last_err = str(exc)
    raise RuntimeError(f"Solana RPC Error across pool: {last_err}")


def wait_for_confirmation(
    signature: str,
    rpc_url: str = SOLANA_MAINNET_RPC,
    max_timeout_secs: int = 20,
) -> dict:
    """
    Poll Solana RPC until the transaction is confirmed on-chain.
    Adapted for Solana Alpenglow (Votor/Rotor consensus) where sub-second finality (100-200ms) is standard.
    """
    t0 = time.time()
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getSignatureStatuses",
        "params": [[signature], {"searchTransactionHistory": True}],
    }

    endpoints = [rpc_url] + [ep for ep in SOLANA_RPC_POOL if ep != rpc_url]
    poll_idx = 0
    while time.time() - t0 < max_timeout_secs:
        ep = endpoints[poll_idx % len(endpoints)]
        poll_idx += 1
        try:
            with httpx.Client(timeout=4.0) as client:
                res = client.post(ep, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    vals = data.get("result", {}).get("value", [])
                    if vals and vals[0]:
                        status_info = vals[0]
                        conf = status_info.get("confirmationStatus")
                        if conf in ("confirmed", "finalized", "processed"):
                            err = status_info.get("err")
                            if conf in ("confirmed", "finalized") or err is not None:
                                return {
                                    "confirmed": err is None,
                                    "status": conf,
                                    "err": err,
                                    "slot": status_info.get("slot"),
                                    "elapsed_secs": round(time.time() - t0, 2),
                                }
        except Exception:
            pass
        # Faster polling (0.5s) for Solana Alpenglow sub-second finality
        time.sleep(0.5)

    return {
        "confirmed": False,
        "status": "pending_or_timeout",
        "err": None,
        "elapsed_secs": round(time.time() - t0, 2),
    }


def execute_onchain_sol_to_token(
    target_token_mint: str,
    amount_sol: float,
    slippage_pct: float = 1.5,
) -> dict:
    """
    Execute REAL On-Chain Swap from SOL -> Target Token Mint on Solana Mainnet!
    Returns on-chain signature, solscan link, amounts, and confirmation status.
    """
    kp = get_trading_keypair()
    if not kp:
        raise ValueError("SOFIA_SOLANA_TRADING_PRIVATE_KEY belum disetel di .env.local")

    amount_lamports = int(round(amount_sol * 1e9))
    if amount_lamports <= 5000:
        raise ValueError("Nominal swap terlalu kecil (minimal > 0.0001 SOL)")

    slippage_bps = int(round(slippage_pct * 100))

    logger.info(f"Mengambil Jupiter quote: SOL -> {target_token_mint} ({amount_sol} SOL)...")
    quote = get_jupiter_quote(
        input_mint=NATIVE_SOL_MINT,
        output_mint=target_token_mint,
        amount_raw=amount_lamports,
        slippage_bps=slippage_bps,
    )

    logger.info("Menandatangani transaksi swap dengan Keypair Phantom...")
    signed_tx, expected_sig = build_and_sign_swap_tx(quote, kp)

    logger.info(f"Menyiarkan transaksi ke Solana Mainnet (Tx: {expected_sig})...")
    actual_sig = broadcast_transaction(signed_tx)

    logger.info(f"Menunggu konfirmasi on-chain (Tx: {actual_sig})...")
    conf = wait_for_confirmation(actual_sig)
    if not conf.get("confirmed") or conf.get("err") is not None:
        raise RuntimeError(f"Swap on-chain SOL -> Token gagal atau revert: {conf.get('err') or 'Konfirmasi timeout'}")

    return {
        "success": True,
        "tx_hash": actual_sig,
        "solscan_url": f"https://solscan.io/tx/{actual_sig}",
        "in_amount_sol": amount_sol,
        "out_amount_raw": quote.get("outAmount"),
        "price_impact_pct": quote.get("priceImpactPct"),
        "confirmation": conf,
    }


def execute_onchain_usdc_to_token(
    target_token_mint: str,
    amount_usdc: float,
    slippage_pct: float = 1.5,
) -> dict:
    """
    Execute REAL On-Chain Swap from USDC -> Target Token Mint on Solana Mainnet!
    Returns on-chain signature, solscan link, amounts, and confirmation status.
    """
    kp = get_trading_keypair()
    if not kp:
        raise ValueError("SOFIA_SOLANA_TRADING_PRIVATE_KEY belum disetel di .env.local")

    # USDC on Solana has 6 decimals
    amount_raw = int(round(amount_usdc * 1e6))
    if amount_raw <= 10000:
        raise ValueError("Nominal swap USDC terlalu kecil (minimal > $0.05 USDC)")

    slippage_bps = int(round(slippage_pct * 100))

    logger.info(f"Mengambil Jupiter quote: USDC -> {target_token_mint} ({amount_usdc:.4f} USDC)...")
    quote = get_jupiter_quote(
        input_mint=USDC_MINT,
        output_mint=target_token_mint,
        amount_raw=amount_raw,
        slippage_bps=slippage_bps,
    )

    logger.info("Menandatangani transaksi swap USDC -> Token dengan Keypair Phantom...")
    signed_tx, expected_sig = build_and_sign_swap_tx(quote, kp)

    logger.info(f"Menyiarkan transaksi USDC swap ke Solana Mainnet (Tx: {expected_sig})...")
    actual_sig = broadcast_transaction(signed_tx)

    logger.info(f"Menunggu konfirmasi on-chain (Tx: {actual_sig})...")
    conf = wait_for_confirmation(actual_sig)
    if not conf.get("confirmed") or conf.get("err") is not None:
        raise RuntimeError(f"Swap on-chain USDC -> Token gagal atau revert: {conf.get('err') or 'Konfirmasi timeout'}")

    return {
        "success": True,
        "tx_hash": actual_sig,
        "solscan_url": f"https://solscan.io/tx/{actual_sig}",
        "in_amount_usdc": amount_usdc,
        "out_amount_raw": quote.get("outAmount"),
        "price_impact_pct": quote.get("priceImpactPct"),
        "confirmation": conf,
    }


def execute_onchain_token_to_sol(
    token_mint: str,
    amount_tokens_raw: int,
    slippage_pct: float = 3.5,
) -> dict:
    """
    Execute REAL On-Chain Swap from Target Token -> SOL on Solana Mainnet!
    Uses adaptive slippage (3.5% -> 8.0% retry if SlippageToleranceExceeded 6001)
    so Quick Exit & Panic Sell never fail due to micro-volatility on meme coins.
    """
    kp = get_trading_keypair()
    if not kp:
        raise ValueError("SOFIA_SOLANA_TRADING_PRIVATE_KEY belum disetel di .env.local")

    # Adaptive slippage tiers: start at max(slippage_pct, 3.5%), escalate to 8.0% if needed
    slip_candidates = [max(float(slippage_pct or 3.5), 3.5), 8.0]
    last_error_msg = None

    for attempt_idx, slip_val in enumerate(slip_candidates):
        slippage_bps = int(round(slip_val * 100))
        try:
            logger.info(f"Mengambil Jupiter quote: {token_mint} -> SOL ({amount_tokens_raw} raw, slippage {slippage_bps} bps)...")
            quote = get_jupiter_quote(
                input_mint=token_mint,
                output_mint=NATIVE_SOL_MINT,
                amount_raw=amount_tokens_raw,
                slippage_bps=slippage_bps,
            )

            logger.info("Menandatangani transaksi swap sell dengan Keypair Phantom...")
            signed_tx, expected_sig = build_and_sign_swap_tx(quote, kp)

            logger.info(f"Menyiarkan transaksi sell ke Solana Mainnet (Tx: {expected_sig})...")
            actual_sig = broadcast_transaction(signed_tx, skip_preflight=(attempt_idx > 0))

            logger.info(f"Menunggu konfirmasi on-chain (Tx: {actual_sig})...")
            conf = wait_for_confirmation(actual_sig)

            if conf.get("err") is not None or not conf.get("confirmed"):
                last_error_msg = f"On-chain error: {conf.get('err') or 'Konfirmasi timeout'}"
                logger.warning(f"Attempt {attempt_idx + 1} sell failed on-chain ({last_error_msg}), retrying with higher slippage...")
                continue

            return {
                "success": True,
                "tx_hash": actual_sig,
                "solscan_url": f"https://solscan.io/tx/{actual_sig}",
                "in_tokens_raw": amount_tokens_raw,
                "out_amount_sol": round(int(quote.get("outAmount", 0)) / 1e9, 6),
                "price_impact_pct": quote.get("priceImpactPct"),
                "confirmation": conf,
            }
        except Exception as exc:
            last_error_msg = str(exc)
            logger.warning(f"Attempt {attempt_idx + 1} sell exception ({last_error_msg})")
            time.sleep(0.6)

    raise RuntimeError(f"Transaksi Quick Exit on-chain gagal dieksekusi: {last_error_msg}")
