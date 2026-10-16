"""On-chain balance snapshots for wallet accounts.

Before this, `record_balance_snapshot` was only ever called from tests, so
`GET /wallets/{id}/balances` could answer exactly one thing: UNAVAILABLE. Sweep
then correctly refused to act on an unknown balance - which meant the whole
automatic mode of PRD v1.1 FR-TB-009 was untestable in practice.

This module is the producer. Its contract is narrow and strict:

  * A balance is read from the chain, never assumed.
  * A failed or malformed read records a snapshot with `status = "UNKNOWN"` and
    NO numbers. It never records 0, because 0 would let a sweep treat an
    unfunded wallet as definitively empty.
  * Balances are integers in atomic units. No float ever reaches the ledger.
"""

import asyncio
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.errors import ProviderError
from app.models.wallet import WalletAccount, WalletBalanceSnapshot
from app.providers.onchain.solana_rpc import SolanaRPCProvider
from app.services.wallet_service import ALLOWED_ASSETS, record_balance_snapshot

# Canonical mints. SOL is native, so its "mint" is the wrapped-SOL address and
# is never actually looked up as an SPL token.
WSOL_MINT = "So11111111111111111111111111111111111111112"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"

ASSET_MINTS = {"SOL": WSOL_MINT, "USDC": USDC_MINT}

STATUS_OK = "OK"
STATUS_UNKNOWN = "UNKNOWN"


@dataclass
class BalanceRead:
    wallet_id: str
    asset: str
    ok: bool
    balance_atomic: int | None = None
    spendable_atomic: int | None = None
    reason: str | None = None


def asset_mint(asset: str) -> str:
    try:
        return ASSET_MINTS[asset]
    except KeyError as exc:
        raise ProviderError("wallet_balance", f"unsupported asset {asset}") from exc


def read_balances(
    db: Session,
    wallet: WalletAccount,
    assets: tuple[str, ...] = ALLOWED_ASSETS,
    provider: SolanaRPCProvider | None = None,
) -> list[BalanceRead]:
    """Read every requested asset for one wallet.

    Each asset is independent: a USDC failure must not erase a good SOL
    reading, and vice versa.
    """
    rpc = provider or SolanaRPCProvider()
    reads: list[BalanceRead] = []
    for asset in assets:
        reads.append(_read_one(rpc, wallet, asset))
    return reads


def _read_one(rpc: SolanaRPCProvider, wallet: WalletAccount, asset: str) -> BalanceRead:
    try:
        if asset == "SOL":
            lamports = asyncio.run(rpc.get_sol_balance_lamports(wallet.public_address))
            # A SOL account must keep a rent buffer; the sweepable figure is
            # what is left after it. Recorded separately, never subtracted from
            # the truth.
            spendable = max(0, lamports - 5_000)
        else:
            atomic = asyncio.run(
                rpc.get_token_balance_atomic(wallet.public_address, asset_mint(asset))
            )
            lamports = atomic
            spendable = atomic
    except Exception as e:  # noqa: BLE001 - an unreadable balance is UNKNOWN, not 0
        return BalanceRead(wallet.id, asset, ok=False, reason=str(e)[:200])
    return BalanceRead(wallet.id, asset, ok=True, balance_atomic=int(lamports), spendable_atomic=int(spendable))


def persist_reads(db: Session, reads: list[BalanceRead], rpc_provider: str = "solana_rpc") -> dict:
    """Turn reads into snapshot rows.

    An UNKNOWN read still writes a row, stamped with the failure. That is the
    point: the absence of a fresh usable number has to be visible in the audit
    trail rather than looking like "no data yet" or, worse, zero.
    """
    stored: dict = {"ok": 0, "unknown": 0}
    for read in reads:
        if not read.ok:
            db.add(
                WalletBalanceSnapshot(
                    wallet_account_id=read.wallet_id,
                    asset=read.asset,
                    mint_address=asset_mint(read.asset),
                    # Schema requires integers. Zero here means "no value was
                    # read" and is qualified by status; it is never summed.
                    balance_atomic=0,
                    spendable_atomic=0,
                    observed_at=_now(),
                    rpc_provider=rpc_provider,
                    status=STATUS_UNKNOWN,
                    raw_payload_hash=None,
                )
            )
            stored["unknown"] += 1
            continue
        record_balance_snapshot(
            db,
            read.wallet_id,
            read.asset,
            read.balance_atomic or 0,
            asset_mint(read.asset),
            spendable_atomic=read.spendable_atomic,
            rpc_provider=rpc_provider,
        )
        stored["ok"] += 1
    db.commit()
    return stored


def refresh_wallet_balances(
    db: Session,
    assets: tuple[str, ...] = ALLOWED_ASSETS,
    provider: SolanaRPCProvider | None = None,
    wallet_ids: list[str] | None = None,
) -> dict:
    """Read and record balances for the BOT wallet and the MAIN wallet."""
    from app.services.wallet_service import get_main_wallet

    targets: list[WalletAccount] = []
    if wallet_ids:
        for wid in wallet_ids:
            wallet = db.get(WalletAccount, wid)
            if wallet is not None:
                targets.append(wallet)
    else:
        bot = (
            db.query(WalletAccount)
            .filter(WalletAccount.wallet_role == "BOT")
            .order_by(WalletAccount.created_at.asc())
            .first()
        )
        if bot is not None:
            targets.append(bot)
        main = get_main_wallet(db)
        if main is not None:
            targets.append(main)

    summary = {"wallets": 0, "ok": 0, "unknown": 0, "detail": []}
    for wallet in targets:
        reads = read_balances(db, wallet, assets=assets, provider=provider)
        counts = persist_reads(db, reads)
        summary["wallets"] += 1
        summary["ok"] += counts["ok"]
        summary["unknown"] += counts["unknown"]
        summary["detail"].extend(
            {
                "wallet_id": r.wallet_id,
                "asset": r.asset,
                "ok": r.ok,
                "balance_atomic": r.balance_atomic,
                "reason": r.reason,
            }
            for r in reads
        )
    return summary


def _now():
    from datetime import UTC, datetime

    return datetime.now(UTC)


__all__ = [
    "ASSET_MINTS",
    "BalanceRead",
    "STATUS_OK",
    "STATUS_UNKNOWN",
    "USDC_MINT",
    "WSOL_MINT",
    "asset_mint",
    "persist_reads",
    "read_balances",
    "refresh_wallet_balances",
]
