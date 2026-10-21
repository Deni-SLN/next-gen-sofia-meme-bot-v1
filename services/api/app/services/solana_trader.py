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
SOLANA_MAINNET_RPC = settings.solana_rpc_url or "https://api.mainnet-beta.solana.com"

JUPITER_QUOTE_ENDPOINTS = [
    "https://api.jup.ag/swap/v1/quote",
    "https://lite-api.jup.ag/swap/v1/quote",
]

JUPITER_SWAP_ENDPOINTS = [
    "https://api.jup.ag/swap/v1/swap",
    "https://lite-api.jup.ag/swap/v1/swap",
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
    """Fetch best swap routing quote from Jupiter v6 Aggregator."""
    params = {
        "inputMint": input_mint,
        "outputMint": output_mint,
        "amount": str(amount_raw),
        "slippageBps": int(slippage_bps),
    }

    last_err = None
    for endpoint in JUPITER_QUOTE_ENDPOINTS:
        try:
            with httpx.Client(timeout=8.0) as client:
                res = client.get(endpoint, params=params)
                if res.status_code == 200:
                    return res.json()
                last_err = f"{endpoint} -> {res.status_code}: {res.text}"
        except Exception as exc:
            last_err = f"{endpoint} -> {exc}"

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
    for endpoint in JUPITER_SWAP_ENDPOINTS:
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.post(endpoint, json=payload)
                if res.status_code == 200:
                    swap_tx_b64 = res.json().get("swapTransaction")
                    if swap_tx_b64:
                        break
                last_err = f"{endpoint} -> {res.status_code}: {res.text}"
        except Exception as exc:
            last_err = f"{endpoint} -> {exc}"

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
    """Broadcast signed VersionedTransaction to Solana Mainnet RPC node."""
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

    with httpx.Client(timeout=15.0) as client:
        res = client.post(rpc_url, json=payload)
        data = res.json()
        if "error" in data:
            raise RuntimeError(f"Solana RPC Error: {data['error']}")
        return data["result"]


def wait_for_confirmation(
    signature: str,
    rpc_url: str = SOLANA_MAINNET_RPC,
    max_timeout_secs: int = 25,
) -> dict:
    """Poll Solana RPC until the transaction is confirmed on-chain."""
    t0 = time.time()
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getSignatureStatuses",
        "params": [[signature], {"searchTransactionHistory": True}],
    }

    while time.time() - t0 < max_timeout_secs:
        try:
            with httpx.Client(timeout=5.0) as client:
                res = client.post(rpc_url, json=payload)
                data = res.json()
                vals = data.get("result", {}).get("value", [])
                if vals and vals[0]:
                    status_info = vals[0]
                    conf = status_info.get("confirmationStatus")
                    if conf in ("confirmed", "finalized"):
                        err = status_info.get("err")
                        return {
                            "confirmed": True,
                            "status": conf,
                            "err": err,
                            "slot": status_info.get("slot"),
                            "elapsed_secs": round(time.time() - t0, 1),
                        }
        except Exception:
            pass
        time.sleep(1.5)

    return {
        "confirmed": False,
        "status": "pending_or_timeout",
        "err": None,
        "elapsed_secs": round(time.time() - t0, 1),
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

    return {
        "success": conf.get("confirmed", True),
        "tx_hash": actual_sig,
        "solscan_url": f"https://solscan.io/tx/{actual_sig}",
        "in_amount_sol": amount_sol,
        "out_amount_raw": quote.get("outAmount"),
        "price_impact_pct": quote.get("priceImpactPct"),
        "confirmation": conf,
    }


def execute_onchain_token_to_sol(
    token_mint: str,
    amount_tokens_raw: int,
    slippage_pct: float = 1.5,
) -> dict:
    """
    Execute REAL On-Chain Swap from Target Token -> SOL on Solana Mainnet!
    Returns on-chain signature, solscan link, amounts, and confirmation status.
    """
    kp = get_trading_keypair()
    if not kp:
        raise ValueError("SOFIA_SOLANA_TRADING_PRIVATE_KEY belum disetel di .env.local")

    slippage_bps = int(round(slippage_pct * 100))

    logger.info(f"Mengambil Jupiter quote: {token_mint} -> SOL ({amount_tokens_raw} raw)...")
    quote = get_jupiter_quote(
        input_mint=token_mint,
        output_mint=NATIVE_SOL_MINT,
        amount_raw=amount_tokens_raw,
        slippage_bps=slippage_bps,
    )

    logger.info("Menandatangani transaksi swap sell dengan Keypair Phantom...")
    signed_tx, expected_sig = build_and_sign_swap_tx(quote, kp)

    logger.info(f"Menyiarkan transaksi sell ke Solana Mainnet (Tx: {expected_sig})...")
    actual_sig = broadcast_transaction(signed_tx)

    logger.info(f"Menunggu konfirmasi on-chain (Tx: {actual_sig})...")
    conf = wait_for_confirmation(actual_sig)

    return {
        "success": conf.get("confirmed", True),
        "tx_hash": actual_sig,
        "solscan_url": f"https://solscan.io/tx/{actual_sig}",
        "in_tokens_raw": amount_tokens_raw,
        "out_amount_sol": round(int(quote.get("outAmount", 0)) / 1e9, 6),
        "price_impact_pct": quote.get("priceImpactPct"),
        "confirmation": conf,
    }
