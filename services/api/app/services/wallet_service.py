"""Wallet service: profit sweep & withdrawal (FR-TB-009, PRD v1.1).

Safety architecture:
- All amounts in integer ATOMIC units; money never in binary float.
- Sweep only from REALIZED profit of closed positions (never unrealized).
- sweepable = max(0, min(50% * eligible_realized, available - reserve - pending - fee)).
- Missing/stale inputs -> sweepable 0, intent REJECTED (fail closed).
- On-chain submission is feature-gated OFF in V1 (gate, not UI toggle).
  Simulated PAPER transfers are recorded with fill_type SIMULATED semantics.
- WithdrawalIntent state machine: DRAFT -> VALIDATING -> AWAITING_CONFIRMATION
  -> READY_TO_SIGN -> SIGNING -> SUBMITTED -> CONFIRMING -> CONFIRMED, with
  FAILED / REJECTED / CANCELLED / SKIPPED / RECONCILIATION_REQUIRED terminals.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.models.trading import AccountingEvent, Position
from app.models.wallet import (
    ProfitSweepEvent,
    WalletAccount,
    WalletBalanceSnapshot,
    WalletPolicyVersion,
    WalletTransfer,
    WithdrawalIntent,
)

# ---- Asset registry (PRD locks SOL + USDC only; USDC mint configurable) ----

SOL_DECIMALS = 9
USDC_DECIMALS = 6
USDC_MAINNET_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
ALLOWED_ASSETS = ("SOL", "USDC")
TERMINAL_STATES = ("CONFIRMED", "FAILED", "REJECTED", "CANCELLED", "SKIPPED")

# Separate feature gate for wallet on-chain activity (default OFF, independent
# from the live-trading gate). Stored in settings so tests can flip it without
# code changes.
WALLET_GATE_KEY = "wallet_feature_enabled"
SWEEP_GATE_KEY = "profit_sweep_enabled"


# ---- Atomic <-> UI conversion (integer math, no floats) ----


def _decimals(asset: str) -> int:
    return SOL_DECIMALS if asset == "SOL" else USDC_DECIMALS


def asset_decimals(asset: str) -> int:
    return _decimals(asset)


def from_atomic(amount_atomic: int, asset: str) -> float:
    return amount_atomic / (10 ** _decimals(asset))


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _now() -> datetime:
    return datetime.now(UTC)


# ---- Feature gates ----


def is_wallet_enabled(db: Session) -> bool:
    from app.models.ops import SettingEntry

    row = db.query(SettingEntry).filter(SettingEntry.key == WALLET_GATE_KEY).first()
    return bool(row and row.value_json.get("value") is True)


def set_wallet_enabled(db: Session, enabled: bool, actor: str) -> bool:
    from app.models.ops import SettingEntry
    from app.services.audit_service import write_audit

    row = db.query(SettingEntry).filter(SettingEntry.key == WALLET_GATE_KEY).first()
    if row is None:
        db.add(SettingEntry(key=WALLET_GATE_KEY, value_json={"value": enabled}))
    else:
        row.value_json = {"value": enabled}
    db.commit()
    write_audit(actor, "wallet_gate_set", "wallet_gate", None, {"enabled": enabled}, db)
    return enabled


def is_sweep_enabled(db: Session) -> bool:
    from app.models.ops import SettingEntry

    row = db.query(SettingEntry).filter(SettingEntry.key == SWEEP_GATE_KEY).first()
    return bool(row and row.value_json.get("value") is True)


def set_sweep_enabled(db: Session, enabled: bool, actor: str) -> bool:
    from app.models.ops import SettingEntry
    from app.services.audit_service import write_audit

    row = db.query(SettingEntry).filter(SettingEntry.key == SWEEP_GATE_KEY).first()
    if row is None:
        db.add(SettingEntry(key=SWEEP_GATE_KEY, value_json={"value": enabled}))
    else:
        row.value_json = {"value": enabled}
    db.commit()
    write_audit(actor, "sweep_gate_set", "sweep_gate", None, {"enabled": enabled}, db)
    return enabled


# ---- Policy ----


def get_policy(db: Session) -> WalletPolicyVersion | None:
    return (
        db.query(WalletPolicyVersion)
        .filter(WalletPolicyVersion.enabled == 1)
        .order_by(WalletPolicyVersion.version.desc())
        .first()
    )


def default_policy(db: Session, actor: str = "system") -> WalletPolicyVersion:
    p = get_policy(db)
    if p is not None:
        return p
    p = WalletPolicyVersion(
        sweep_percent=50,
        allowed_assets=list(ALLOWED_ASSETS),
        reserve_policy="DYNAMIC",
        min_sweep_atomic=0,
        per_transfer_cap_atomic=None,
        daily_cap_atomic=None,
        cooldown_seconds=0,
        version=1,
        enabled=1,
        created_by=actor,
    )
    db.add(p)
    db.commit()
    return p


# Bounds enforced on every policy write (PRD §8 "dibatasi dan berversi").
POLICY_LIMITS = {
    "sweep_percent": (0, 100),
    "min_sweep_atomic": (0, None),
    "per_transfer_cap_atomic": (0, None),
    "daily_cap_atomic": (0, None),
    "cooldown_seconds": (0, 86_400),
}


def set_policy(db: Session, actor: str, payload: dict) -> WalletPolicyVersion:
    """Create a NEW policy version. Previous versions are never mutated.

    Every change is audited (PRD §8 mode otomatis step 7). The 50% default is
    policy data, never an AI-modifiable value.
    """
    from app.services.audit_service import write_audit

    allowed = set(POLICY_LIMITS) | {"allowed_assets", "reserve_policy", "destination_wallet_id"}
    unknown = set(payload) - allowed
    if unknown:
        raise ValidationError(f"unknown policy fields: {sorted(unknown)}", details={"allowed": sorted(allowed)})

    current = get_policy(db)
    if current is None:
        current = default_policy(db, actor)

    values: dict = {
        "sweep_percent": current.sweep_percent,
        "allowed_assets": list(current.allowed_assets or list(ALLOWED_ASSETS)),
        "reserve_policy": current.reserve_policy or "DYNAMIC",
        "min_sweep_atomic": current.min_sweep_atomic,
        "per_transfer_cap_atomic": current.per_transfer_cap_atomic,
        "daily_cap_atomic": current.daily_cap_atomic,
        "cooldown_seconds": current.cooldown_seconds,
        "destination_wallet_id": current.destination_wallet_id,
    }
    changed_keys: list[str] = []
    for field, (lo, hi) in POLICY_LIMITS.items():
        if field not in payload:
            continue
        raw = payload[field]
        if not isinstance(raw, int) or isinstance(raw, bool):
            raise ValidationError(f"{field} must be an integer (atomic units for *_atomic)")
        if raw < lo or (hi is not None and raw > hi):
            raise ValidationError(f"{field} out of range [{lo}, {hi}]")
        values[field] = raw
        changed_keys.append(field)

    if "allowed_assets" in payload:
        assets = payload["allowed_assets"]
        if not isinstance(assets, list) or not assets:
            raise ValidationError("allowed_assets must be a non-empty list")
        bad = [a for a in assets if a not in ALLOWED_ASSETS]
        if bad:
            raise ValidationError(f"assets outside the locked allowlist {ALLOWED_ASSETS}: {bad}")
        values["allowed_assets"] = list(assets)
        changed_keys.append("allowed_assets")

    if "reserve_policy" in payload:
        if payload["reserve_policy"] != "DYNAMIC":
            raise ValidationError("reserve_policy is locked to DYNAMIC in V1")
        values["reserve_policy"] = "DYNAMIC"
        changed_keys.append("reserve_policy")

    if "destination_wallet_id" in payload:
        dest = db.get(WalletAccount, payload["destination_wallet_id"])
        if dest is None:
            raise NotFoundError("wallet", payload["destination_wallet_id"])
        if dest.wallet_role != "MAIN" or not dest.is_allowlisted:
            raise ValidationError("destination must be an allowlisted MAIN wallet")
        values["destination_wallet_id"] = dest.id
        changed_keys.append("destination_wallet_id")

    current.enabled = 0  # policy versions are immutable once superseded
    new_version = WalletPolicyVersion(
        **values,
        version=current.version + 1,
        enabled=1,
        created_by=actor,
    )
    db.add(new_version)
    db.commit()
    write_audit(actor, "update_wallet_policy", "wallet_policy_version", new_version.id, {"changed": sorted(changed_keys), "version": new_version.version}, db)
    return new_version


def policy_json(p: WalletPolicyVersion) -> dict:
    return {
        "id": p.id,
        "version": p.version,
        "enabled": bool(p.enabled),
        "sweep_percent": p.sweep_percent,
        "allowed_assets": p.allowed_assets,
        "reserve_policy": p.reserve_policy,
        "min_sweep_atomic": p.min_sweep_atomic,
        "per_transfer_cap_atomic": p.per_transfer_cap_atomic,
        "daily_cap_atomic": p.daily_cap_atomic,
        "cooldown_seconds": p.cooldown_seconds,
        "destination_wallet_id": p.destination_wallet_id,
        "created_by": p.created_by,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


# ---- Wallets ----


def register_wallet(db: Session, role: str, address: str, actor: str, allowlisted: bool = False) -> WalletAccount:
    from app.services.audit_service import write_audit

    role = role.upper()
    if role not in ("BOT", "MAIN"):
        raise ValidationError("role must be BOT or MAIN")
    if not address or len(address) < 32:
        raise ValidationError("invalid public address")
    existing = db.query(WalletAccount).filter(WalletAccount.public_address == address).first()
    if existing:
        return existing
    # First MAIN wallet becomes the allowlisted treasury destination.
    if role == "MAIN" and db.query(WalletAccount).filter(WalletAccount.wallet_role == "MAIN").count() == 0:
        allowlisted = True
    w = WalletAccount(
        wallet_role=role, chain="solana", public_address=address,
        is_allowlisted=1 if allowlisted else 0, status="ACTIVE",
    )
    db.add(w)
    db.commit()
    write_audit(actor, "register_wallet", "wallet_account", w.id, {"role": role, "allowlisted": allowlisted}, db)
    return w


def get_main_wallet(db: Session) -> WalletAccount | None:
    return (
        db.query(WalletAccount)
        .filter(WalletAccount.wallet_role == "MAIN", WalletAccount.is_allowlisted == 1)
        .order_by(WalletAccount.created_at.asc())
        .first()
    )


def get_bot_wallet(db: Session) -> WalletAccount | None:
    return (
        db.query(WalletAccount)
        .filter(WalletAccount.wallet_role == "BOT", WalletAccount.status == "ACTIVE")
        .order_by(WalletAccount.created_at.asc())
        .first()
    )


# ---- Balance snapshots (validated on-chain reads; cache alone never authorizes) ----


def record_balance_snapshot(
    db: Session,
    wallet_id: str,
    asset: str,
    balance_atomic: int,
    mint_address: str,
    spendable_atomic: int | None = None,
    rpc_provider: str | None = None,
    observed_at: datetime | None = None,
) -> WalletBalanceSnapshot:
    if asset not in ALLOWED_ASSETS:
        raise ValidationError(f"asset must be one of {ALLOWED_ASSETS}")
    if balance_atomic < 0:
        raise ValidationError("balance cannot be negative")
    snap = WalletBalanceSnapshot(
        wallet_account_id=wallet_id,
        asset=asset,
        mint_address=mint_address,
        balance_atomic=balance_atomic,
        spendable_atomic=spendable_atomic if spendable_atomic is not None else balance_atomic,
        observed_at=observed_at or _now(),
        rpc_provider=rpc_provider,
        status="OK",
    )
    db.add(snap)
    db.commit()
    return snap


def latest_snapshot(
    db: Session,
    wallet_id: str,
    asset: str,
    max_age_seconds: int = 300,
    require_ok: bool = True,
) -> WalletBalanceSnapshot | None:
    """Freshest usable balance snapshot, or None.

    None means "no number you may act on", for three different reasons that all
    fail the same way: never read, read too long ago, or read by a call that
    failed (status UNKNOWN). An UNKNOWN row still holds an integer zero because
    the column is non-nullable - that zero is the absence of a measurement, so
    by default it is not returned as if it were a measurement.

    `require_ok=False` is for display paths that want to show the distinction
    between "never read" and "read and failed".
    """
    snap = (
        db.query(WalletBalanceSnapshot)
        .filter(WalletBalanceSnapshot.wallet_account_id == wallet_id, WalletBalanceSnapshot.asset == asset)
        .order_by(WalletBalanceSnapshot.observed_at.desc())
        .first()
    )
    if snap is None:
        return None
    age = (_now() - _aware(snap.observed_at)).total_seconds()
    if age > max_age_seconds:
        return None  # stale -> treated as unavailable (fail closed)
    if require_ok and (snap.status or "OK") != "OK":
        return None  # the read failed -> the stored zero is not a balance
    return snap


# ---- Dynamic reserve & sweepable calculation (integer atomic math) ----


@dataclass
class ReserveBreakdown:
    open_position_exposure_atomic: int
    pending_outflows_atomic: int
    estimated_fees_atomic: int
    operational_buffer_atomic: int
    total_atomic: int


def _usd_to_atomic(usd: float, asset: str) -> int:
    """Convert a USD notional into integer atomic units for `asset`.

    SOL uses the conservative 100 USD/SOL marker; USDC is 1 USD/USDC.
    """
    if usd <= 0:
        return 0
    divisor = 100.0 if asset == "SOL" else 1.0
    return int(round(usd * (10 ** asset_decimals(asset)) / divisor))


def compute_dynamic_reserve(db: Session, wallet_id: str, asset: str, fee_atomic: int = 0) -> ReserveBreakdown:
    """Reserve = open exposure + pending outflows + fees + op buffer.

    In PAPER the ledger tracks USD notionals; per-asset atomic reserve is
    derived conservatively from open positions so sweep can never strand them.
    """
    open_positions = db.query(Position).filter(Position.status == "OPEN").all()
    exposure_usd = sum(abs(p.quantity * (p.average_entry_price or 0.0)) for p in open_positions)
    # Conservative USD->atomic mapping uses a configured notional rate marker.
    # The reserve is intentionally approximate-up: it only ever REDUCES sweepable.
    exposure_atomic = _usd_to_atomic(exposure_usd, asset) if exposure_usd else 0
    pending = (
        db.query(WithdrawalIntent)
        .filter(
            WithdrawalIntent.source_wallet_id == wallet_id,
            WithdrawalIntent.asset == asset,
            WithdrawalIntent.state.notin_(list(TERMINAL_STATES)),
        )
        .all()
    )
    pending_atomic = sum(i.amount_atomic + (i.estimated_fee_atomic or 0) for i in pending)
    op_buffer = 5_000 if asset == "SOL" else 0  # ~rent-exempt dust guard (lamports)
    total = exposure_atomic + pending_atomic + fee_atomic + op_buffer
    return ReserveBreakdown(exposure_atomic, pending_atomic, fee_atomic, op_buffer, total)


@dataclass
class SweepEvaluation:
    asset: str
    eligible_realized_atomic: int
    sweep_target_atomic: int
    available_atomic: int
    reserve_atomic: int
    pending_outflows_atomic: int
    fee_atomic: int
    sweepable_atomic: int
    reasons: list
    reserve_breakdown: dict


def eligible_realized_profit_atomic(db: Session, asset: str) -> int:
    """Realized profit attributable to asset from CLOSED positions + ledger.

    Only positive realized profit counts; profit already swept (recorded in
    ProfitSweepEvent) is subtracted so the same profit is never swept twice.
    """
    closed = db.query(Position).filter(Position.status == "CLOSED").all()
    realized_usd = sum(p.realized_pnl or 0.0 for p in closed)
    ledger_pnl = sum(
        e.amount for e in
        db.query(AccountingEvent).filter(AccountingEvent.event_type == "REALIZED_PNL").all()
    )
    total_usd = max(realized_usd, 0.0) + max(ledger_pnl, 0.0)
    gross_atomic = _usd_to_atomic(total_usd, asset)
    swept = sum(
        s.sweep_amount_atomic for s in
        db.query(ProfitSweepEvent).filter(ProfitSweepEvent.asset == asset).all()
    )
    return max(0, gross_atomic - swept)


def evaluate_sweep(db: Session, wallet_id: str, asset: str) -> SweepEvaluation:
    """Dry-run sweep evaluation. NEVER signs or submits. Fail-closed."""
    # require_ok=False so a failed read reports *why* it is unusable. The
    # default would collapse "read and failed" into "never read", which is the
    # distinction an operator needs when the sweep silently does nothing.
    snap = latest_snapshot(db, wallet_id, asset, require_ok=False)
    if snap is None:
        return _blocked_sweep(asset, "balance snapshot missing or stale -> fail closed")

    # A snapshot written by a failed chain read carries status UNKNOWN and an
    # integer zero only because the column is non-nullable. Spending against it
    # would be spending against a number nobody measured, so refuse outright.
    if (snap.status or "OK") != "OK":
        return _blocked_sweep(asset, f"balance snapshot status is {snap.status} -> fail closed")

    eligible = eligible_realized_profit_atomic(db, asset)
    reserve = compute_dynamic_reserve(db, wallet_id, asset)
    fee = 5_000
    available = snap.spendable_atomic
    # reserve.total_atomic ALREADY includes pending outflows and the operational
    # buffer, so subtracting pending again would double-count it and zero out a
    # sweep that is genuinely affordable.
    cushion = available - reserve.total_atomic - fee
    policy = get_policy(db)
    sweep_pct = (policy.sweep_percent if policy and policy.sweep_percent is not None else 50)
    sweep_target = min(int(eligible * sweep_pct // 100), cushion) if cushion > 0 else 0

    reasons: list[str] = []
    if eligible <= 0:
        reasons.append("no realized profit available to sweep")
    if cushion <= 0:
        reasons.append(
            f"dynamic reserve {reserve.total_atomic} + fee {fee} "
            f"exceeds available {available}"
        )
    if policy:
        if policy.min_sweep_atomic and sweep_target and sweep_target < policy.min_sweep_atomic:
            reasons.append(
                f"sweepable {sweep_target} is below the policy minimum {policy.min_sweep_atomic}"
            )

    return SweepEvaluation(
        asset=asset,
        eligible_realized_atomic=eligible,
        sweep_target_atomic=sweep_target,
        available_atomic=available,
        reserve_atomic=reserve.total_atomic,
        pending_outflows_atomic=reserve.pending_outflows_atomic,
        fee_atomic=fee,
        sweepable_atomic=max(0, sweep_target),
        reasons=reasons,
        reserve_breakdown={
            "open_position_exposure_atomic": reserve.open_position_exposure_atomic,
            "pending_outflows_atomic": reserve.pending_outflows_atomic,
            "estimated_fees_atomic": fee,
            "operational_buffer_atomic": reserve.operational_buffer_atomic,
            "total_atomic": reserve.total_atomic,
        },
    )


def _blocked_sweep(asset: str, reason: str) -> SweepEvaluation:
    """A sweep that refuses to evaluate, with the reason attached."""
    return SweepEvaluation(
        asset=asset,
        eligible_realized_atomic=0,
        sweep_target_atomic=0,
        available_atomic=0,
        reserve_atomic=0,
        pending_outflows_atomic=0,
        fee_atomic=5_000,
        sweepable_atomic=0,
        reasons=[reason],
        reserve_breakdown={
            "total_atomic": 0,
            "open_position_exposure_atomic": 0,
            "pending_outflows_atomic": 0,
        },
    )



def _payload_hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:32]


# USD dust floor: anything below this is not worth a transfer and is treated as
# dust (PRD §8 "dust/minimum transfer").
DUST_THRESHOLD_ATOMIC = {"SOL": 1_000_000, "USDC": 100_000}  # 0.001 SOL / 0.10 USDC
SOL_FEE_LAMPORTS = 5_000  # network fee estimate, always paid in SOL


def validate_transfer(
    db: Session,
    source_wallet_id: str,
    asset: str,
    amount_atomic: int,
    destination_wallet_id: str | None = None,
) -> dict:
    """Full dry validation for a withdrawal. NEVER creates an intent or signs.

    Returns a report the UI can render before operator confirmation (PRD §8
    mode manual step 2). Every mandatory input that is missing, stale or
    inconsistent makes the whole validation fail closed.
    """
    policy = get_policy(db) or default_policy(db)
    checks: list[dict] = []

    def check(name: str, ok: bool, detail: str = "", value=None) -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail, "value": value})

    # --- identity ---
    source = db.get(WalletAccount, source_wallet_id)
    check("source_wallet_exists", source is not None, "bot wallet must be registered and active")
    if source is None:
        return {"valid": False, "checks": checks, "asset": asset, "amount_atomic": amount_atomic}
    check("source_wallet_active", source.status == "ACTIVE", f"status={source.status}")
    check("source_is_bot_wallet", source.wallet_role == "BOT", f"role={source.wallet_role}")

    dest = db.get(WalletAccount, destination_wallet_id) if destination_wallet_id else get_main_wallet(db)
    check("destination_allowlisted", dest is not None and bool(dest.is_allowlisted) and dest.wallet_role == "MAIN",
          "destination must be the allowlisted MAIN (treasury) wallet")
    if dest is not None and source is not None:
        check("destination_differs_from_source", dest.id != source.id, "source and destination must differ")

    # --- asset / amount ---
    check("asset_allowed", asset in ALLOWED_ASSETS, f"allowlist={list(ALLOWED_ASSETS)}")
    check("asset_in_policy", asset in (policy.allowed_assets or list(ALLOWED_ASSETS)), f"policy assets={policy.allowed_assets}")
    check("amount_positive", isinstance(amount_atomic, int) and amount_atomic > 0, "amount must be a positive integer")
    if isinstance(amount_atomic, int) and amount_atomic > 0:
        dust = DUST_THRESHOLD_ATOMIC.get(asset, 0)
        check("not_dust", amount_atomic >= dust, f"minimum {dust} atomic units ({asset})", amount_atomic)
        check("meets_min_sweep", amount_atomic >= (policy.min_sweep_atomic or 0), f"policy min_sweep_atomic={policy.min_sweep_atomic}")
    if isinstance(amount_atomic, int) and amount_atomic > 0:
        check("within_per_transfer_cap",
              not policy.per_transfer_cap_atomic or amount_atomic <= policy.per_transfer_cap_atomic,
              f"cap={policy.per_transfer_cap_atomic}")

    # --- balance: must be a fresh on-chain read, cache alone never authorizes ---
    snap = latest_snapshot(db, source.id, asset) if isinstance(asset, str) else None
    check("balance_snapshot_fresh", snap is not None, "on-chain balance snapshot missing or stale -> fail closed")
    reserve = compute_dynamic_reserve(db, source.id, asset, fee_atomic=SOL_FEE_LAMPORTS)
    if snap is not None:
        need = amount_atomic + reserve.total_atomic if isinstance(amount_atomic, int) and amount_atomic > 0 else 0
        check("spendable_covers_amount_plus_reserve", snap.spendable_atomic >= need,
              f"spendable={snap.spendable_atomic} need={need}", snap.spendable_atomic)
        check("reserve_preserved",
              snap.spendable_atomic - (amount_atomic if isinstance(amount_atomic, int) else 0) >= reserve.total_atomic,
              f"reserve={reserve.total_atomic}")

    # --- network fee is always paid in SOL, never assumed to be paid in USDC ---
    if asset == "USDC":
        sol_snap = latest_snapshot(db, source.id, "SOL")
        check("sol_fee_reserve_available",
              sol_snap is not None and sol_snap.spendable_atomic >= SOL_FEE_LAMPORTS,
              "USDC transfers still pay network fee in SOL")

    # --- caps & cooldown ---
    if policy.daily_cap_atomic:
        day_start = _now() - timedelta(hours=24)
        day_total = sum(
            i.amount_atomic for i in db.query(WithdrawalIntent).filter(
                WithdrawalIntent.source_wallet_id == source.id,
                WithdrawalIntent.asset == asset,
                WithdrawalIntent.created_at >= day_start,
                WithdrawalIntent.state.notin_(("REJECTED", "CANCELLED")),
            ).all()
        )
        check("within_daily_cap", day_total + max(0, amount_atomic) <= policy.daily_cap_atomic,
              f"used_today={day_total} cap={policy.daily_cap_atomic}")
    if policy.cooldown_seconds:
        recent = (
            db.query(WithdrawalIntent)
            .filter(
                WithdrawalIntent.source_wallet_id == source.id,
                WithdrawalIntent.asset == asset,
                WithdrawalIntent.created_at >= _now() - timedelta(seconds=policy.cooldown_seconds),
                WithdrawalIntent.state.notin_(("REJECTED", "CANCELLED", "FAILED", "SKIPPED")),
            )
            .order_by(WithdrawalIntent.created_at.desc())
            .first()
        )
        check("cooldown_elapsed", recent is None,
              f"cooldown {policy.cooldown_seconds}s since last intent for {asset}")

    valid = all(c["ok"] for c in checks)
    return {
        "valid": valid,
        "asset": asset,
        "amount_atomic": amount_atomic,
        "amount_ui": from_atomic(amount_atomic, asset) if isinstance(amount_atomic, int) else None,
        "source_wallet_id": source.id,
        "source_address": source.public_address,
        "destination_wallet_id": dest.id if dest else None,
        "destination_address": dest.public_address if dest else None,
        "estimated_fee_atomic": SOL_FEE_LAMPORTS,
        "estimated_fee_asset": "SOL",
        "reserve_atomic": reserve.total_atomic,
        "reserve_breakdown": {
            "open_position_exposure_atomic": reserve.open_position_exposure_atomic,
            "pending_outflows_atomic": reserve.pending_outflows_atomic,
            "estimated_fees_atomic": reserve.estimated_fees_atomic,
            "operational_buffer_atomic": reserve.operational_buffer_atomic,
            "total_atomic": reserve.total_atomic,
        },
        "balance_after_atomic": (snap.spendable_atomic - amount_atomic) if snap is not None and isinstance(amount_atomic, int) else None,
        "policy_version": policy.version,
        "wallet_onchain_gate_enabled": is_wallet_enabled(db),
        "checks": checks,
        "failed_checks": [c["name"] for c in checks if not c["ok"]],
    }


def _intent_json(i: WithdrawalIntent) -> dict:
    return {
        "id": i.id,
        "idempotency_key": i.idempotency_key,
        "trigger_type": i.trigger_type,
        "asset": i.asset,
        "amount_atomic": i.amount_atomic,
        "amount_ui": from_atomic(i.amount_atomic, i.asset),
        "estimated_fee_atomic": i.estimated_fee_atomic,
        "state": i.state,
        "destination_address_snapshot": i.destination_address_snapshot,
        "policy_version": i.policy_version,
        "version": i.version,
        "failure_reason": i.failure_reason,
        "created_at": i.created_at.isoformat() if i.created_at else None,
    }


def create_withdrawal_intent(
    db: Session,
    actor: str,
    source_wallet_id: str,
    asset: str,
    amount_atomic: int,
    idempotency_key: str,
    trigger_type: str = "MANUAL",
    destination_wallet_id: str | None = None,
) -> dict:
    """Create (or return existing) withdrawal intent. Idempotent + fail-closed."""

    if trigger_type not in ("MANUAL", "AUTO_SWEEP"):
        raise ValidationError("trigger_type must be MANUAL or AUTO_SWEEP")
    if asset not in ALLOWED_ASSETS:
        raise ValidationError(f"asset must be one of {ALLOWED_ASSETS}")
    if amount_atomic <= 0:
        raise ValidationError("amount must be positive (atomic units)")
    if not idempotency_key:
        raise ValidationError("idempotency_key required")

    source = db.get(WalletAccount, source_wallet_id)
    if source is None:
        raise NotFoundError("wallet", source_wallet_id)
    dest = db.get(WalletAccount, destination_wallet_id) if destination_wallet_id else get_main_wallet(db)
    if dest is None or not dest.is_allowlisted or dest.wallet_role != "MAIN":
        raise ValidationError("destination must be the allowlisted MAIN wallet")
    if dest.id == source.id:
        raise ValidationError("source and destination must differ")

    payload = {
        "source": source_wallet_id, "dest": dest.id, "asset": asset,
        "amount": amount_atomic, "trigger": trigger_type,
    }
    existing = db.query(WithdrawalIntent).filter(WithdrawalIntent.idempotency_key == idempotency_key).first()
    if existing:
        if existing.payload_hash != _payload_hash(payload):
            raise ConflictError("idempotency key reused with different payload", details={"code": "IDEMPOTENCY_CONFLICT"})
        return {"intent": _intent_json(existing), "deduplicated": True}
    return _persist_intent(db, actor, source, dest, asset, amount_atomic, idempotency_key, trigger_type, payload, latest_snapshot(db, source.id, asset))



def _persist_intent(db, actor, source, dest, asset, amount_atomic, idempotency_key, trigger_type, payload, snap) -> dict:
    from app.services.audit_service import write_audit

    if snap is None:
        raise ValidationError(
            "on-chain balance snapshot missing or stale -> fail closed",
            details={"wallet_id": source.id, "asset": asset},
        )
    fee = 5_000  # lamports estimate; USDC fee still paid from SOL
    reserve = compute_dynamic_reserve(db, source.id, asset, fee_atomic=fee)
    if snap.spendable_atomic < amount_atomic + reserve.total_atomic:
        raise ValidationError(
            f"insufficient spendable after reserve: have {snap.spendable_atomic}, need {amount_atomic + reserve.total_atomic}",
            details={"reserve": reserve.total_atomic, "spendable": snap.spendable_atomic},
        )
    policy = get_policy(db) or default_policy(db)
    if policy.per_transfer_cap_atomic and amount_atomic > policy.per_transfer_cap_atomic:
        raise ValidationError("amount exceeds per-transfer cap")
    if policy.daily_cap_atomic:
        day_start = _now() - timedelta(hours=24)
        day_total = sum(
            i.amount_atomic for i in db.query(WithdrawalIntent).filter(
                WithdrawalIntent.source_wallet_id == source.id,
                WithdrawalIntent.asset == asset,
                WithdrawalIntent.created_at >= day_start,
                WithdrawalIntent.state.notin_(("REJECTED", "CANCELLED")),
            ).all()
        )
        if day_total + amount_atomic > policy.daily_cap_atomic:
            raise ValidationError("amount exceeds daily cap")
    intent = WithdrawalIntent(
        idempotency_key=idempotency_key,
        trigger_type=trigger_type,
        source_wallet_id=source.id,
        destination_wallet_id=dest.id,
        destination_address_snapshot=dest.public_address,
        asset=asset,
        mint_address=USDC_MAINNET_MINT if asset == "USDC" else "So11111111111111111111111111111111111111112",
        amount_atomic=amount_atomic,
        estimated_fee_atomic=fee,
        reserve_snapshot={
            "total_atomic": reserve.total_atomic,
            "open_position_exposure_atomic": reserve.open_position_exposure_atomic,
            "pending_outflows_atomic": reserve.pending_outflows_atomic,
            "balance_at_validation": snap.spendable_atomic,
        },
        policy_version=policy.version,
        state="VALIDATING",
        payload_hash=_payload_hash(payload),
        created_by=actor,
        expires_at=_now() + timedelta(minutes=15),
    )
    db.add(intent)
    db.commit()
    write_audit(actor, "create_withdrawal_intent", "withdrawal_intent", intent.id, {"asset": asset, "amount_atomic": amount_atomic}, db)
    return {"intent": _intent_json(intent), "deduplicated": False}


def transition_intent(db: Session, intent_id: str, actor: str, to_state: str, reason: str | None = None) -> dict:
    """Explicit, audited state transitions with optimistic locking."""
    from app.services.audit_service import write_audit

    allowed = {
        "DRAFT": ("VALIDATING", "CANCELLED"),
        "VALIDATING": ("AWAITING_CONFIRMATION", "READY_TO_SIGN", "REJECTED"),
        "AWAITING_CONFIRMATION": ("READY_TO_SIGN", "CANCELLED", "REJECTED"),
        "READY_TO_SIGN": ("SIGNING", "CANCELLED", "REJECTED"),
        "SIGNING": ("SUBMITTED", "FAILED"),
        "SUBMITTED": ("CONFIRMING", "FAILED"),
        "CONFIRMING": ("CONFIRMED", "FAILED", "RECONCILIATION_REQUIRED"),
        "RECONCILIATION_REQUIRED": ("CONFIRMED", "FAILED"),
        "SKIPPED": (),
        "REJECTED": (),
        "CONFIRMED": (),
        "FAILED": (),
        "CANCELLED": (),
    }
    intent = db.get(WithdrawalIntent, intent_id)
    if intent is None:
        raise NotFoundError("withdrawal_intent", intent_id)
    if intent.state in TERMINAL_STATES:
        raise ConflictError(f"intent is terminal ({intent.state}); corrections need a new intent")
    if to_state not in allowed.get(intent.state, ()):
        raise ValidationError(f"illegal transition {intent.state} -> {to_state}")
    if to_state in ("READY_TO_SIGN", "SIGNING", "SUBMITTED") and not is_wallet_enabled(db):
        raise ForbiddenError("wallet on-chain activity is disabled (feature gate OFF)")
    if to_state == "READY_TO_SIGN":
        snap = latest_snapshot(db, intent.source_wallet_id, intent.asset)
        if snap is None:
            intent.state = "REJECTED"
            intent.failure_reason = "balance stale at signing gate -> revalidation failed"
            db.commit()
            raise ValidationError(intent.failure_reason)
        if snap.spendable_atomic < intent.amount_atomic + (intent.estimated_fee_atomic or 0):
            intent.state = "REJECTED"
            intent.failure_reason = "spendable dropped below reserve before signing"
            db.commit()
            raise ValidationError(intent.failure_reason)
    intent.state = to_state
    intent.version = (intent.version or 1) + 1
    if reason and to_state in ("REJECTED", "FAILED", "CANCELLED"):
        intent.failure_reason = reason[:500]
    db.commit()
    write_audit(actor, f"withdrawal_{to_state.lower()}", "withdrawal_intent", intent.id, {"to": to_state}, db)
    return _intent_json(intent)


def evaluate_and_record_sweep(db: Session, actor: str, close_event_id: str, wallet_id: str, asset: str) -> dict:
    """Evaluate sweep for one close event; record ProfitSweepEvent once.

    Unique (close_event_id, asset, policy_version) prevents double sweep.
    Creates a VALIDATING AUTO_SWEEP intent only when sweepable > 0 and the
    sweep gate is on; otherwise records SKIPPED with reasons. Never signs.
    """
    from app.services.audit_service import write_audit

    policy = get_policy(db) or default_policy(db)
    existing = (
        db.query(ProfitSweepEvent)
        .filter(
            ProfitSweepEvent.close_event_id == close_event_id,
            ProfitSweepEvent.asset == asset,
            ProfitSweepEvent.policy_version == policy.version,
        )
        .first()
    )
    if existing:
        return {"status": existing.status, "deduplicated": True, "event_id": existing.id}

    ev = evaluate_sweep(db, wallet_id, asset)
    sweep_event = ProfitSweepEvent(
        close_event_id=close_event_id,
        asset=asset,
        realized_profit_atomic=ev.eligible_realized_atomic,
        sweep_percent=policy.sweep_percent,
        sweep_amount_atomic=ev.sweepable_atomic,
        reserve_snapshot=ev.reserve_breakdown,
        status="SKIPPED" if ev.sweepable_atomic <= 0 else "EVALUATED",
    )
    db.add(sweep_event)
    db.flush()

    if ev.sweepable_atomic <= 0 or not is_sweep_enabled(db):
        # Nothing will actually be swept: record it as SKIPPED so the ledger
        # never implies an action that the gate prevented.
        gate_off = ev.sweepable_atomic > 0 and not is_sweep_enabled(db)
        sweep_event.status = "SKIPPED"
        sweep_event.sweep_amount_atomic = 0
        reasons = (
            ["sweep feature gate is off"]
            if gate_off
            else (ev.reasons or ["no sweepable balance after reserve"])
        )
        db.commit()
        return {"status": "SKIPPED", "sweepable_atomic": 0, "reasons": reasons, "event_id": sweep_event.id}

    key = f"sweep:{close_event_id}:{asset}:v{policy.version}"
    try:
        created = create_withdrawal_intent(
            db, actor, wallet_id, asset, ev.sweepable_atomic, key, trigger_type="AUTO_SWEEP",
        )
        sweep_event.withdrawal_intent_id = created["intent"]["id"]
        sweep_event.status = "INTENT_CREATED"
        db.commit()
        write_audit(actor, "auto_sweep_intent", "profit_sweep_event", sweep_event.id, {"asset": asset}, db)
        return {"status": "INTENT_CREATED", "sweepable_atomic": ev.sweepable_atomic, "event_id": sweep_event.id, "intent": created["intent"]}
    except (ValidationError, ConflictError, ForbiddenError) as e:
        sweep_event.status = "SKIPPED"
        db.commit()
        return {"status": "SKIPPED", "sweepable_atomic": 0, "reasons": [str(e)][:3], "event_id": sweep_event.id}


# ---- Reconciliation ----


def reconcile_intent(db: Session, intent_id: str, actor: str, outcome: str, signature: str | None = None) -> dict:
    """Resolve RECONCILIATION_REQUIRED (or CONFIRMING) to a final known state.

    No blind retry: the caller must supply the observed on-chain outcome
    (signature found -> CONFIRMED with stored signature; proven absent ->
    FAILED). A replacement transfer always needs a NEW intent.
    """
    from app.services.audit_service import write_audit

    intent = db.get(WithdrawalIntent, intent_id)
    if intent is None:
        raise NotFoundError("withdrawal_intent", intent_id)
    if intent.state not in ("CONFIRMING", "RECONCILIATION_REQUIRED", "SUBMITTED"):
        raise ValidationError(f"intent {intent.state} does not need reconciliation")
    transfer = db.query(WalletTransfer).filter(WalletTransfer.withdrawal_intent_id == intent.id).first()
    if outcome == "CONFIRMED":
        if not signature:
            raise ValidationError("signature required to mark CONFIRMED")
        dupe = db.query(WalletTransfer).filter(WalletTransfer.transaction_signature == signature).first()
        if dupe and dupe.withdrawal_intent_id != intent.id:
            raise ConflictError("signature already attributed to another intent")
        if transfer is None:
            transfer = WalletTransfer(withdrawal_intent_id=intent.id, transaction_signature=signature)
            db.add(transfer)
        else:
            transfer.transaction_signature = signature
        transfer.reconciliation_status = "CONFIRMED"
        transfer.confirmed_at = _now()
        intent.state = "CONFIRMED"
    elif outcome == "FAILED":
        if transfer:
            transfer.reconciliation_status = "FAILED"
        intent.state = "FAILED"
        intent.failure_reason = "reconciliation proved no valid transaction"
    else:
        raise ValidationError("outcome must be CONFIRMED or FAILED")
    intent.version = (intent.version or 1) + 1
    db.commit()
    write_audit(actor, "withdrawal_reconciled", "withdrawal_intent", intent.id, {"outcome": outcome}, db)
    return _intent_json(intent)

