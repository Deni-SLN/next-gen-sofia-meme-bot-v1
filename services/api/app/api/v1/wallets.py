"""Wallets, transfers & profit sweep endpoints (FR-TB-009, PRD §12.5).

Safety rules enforced here, not in the frontend (PRD §12.5 note):
- every write requires an authenticated operator;
- idempotency key is mandatory for intent creation;
- feature gates are enforced server-side (wallet on-chain gate and sweep gate
  are separate from the live-trading gate, all default OFF);
- balance/reserve validation is always re-run server-side;
- no endpoint in this module signs or submits an on-chain transaction while the
  wallet gate is OFF — `POST /profit-sweep/evaluate` is a dry run by contract.
"""

from app.api.v1.deps import current_actor, require_operator
from app.core.errors import NotFoundError, ValidationError
from app.db.session import get_db
from app.models.wallet import (
    ProfitSweepEvent,
    WalletAccount,
    WalletBalanceSnapshot,
    WalletTransfer,
    WithdrawalIntent,
)
from app.services import wallet_service as ws
from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

router = APIRouter(tags=["wallets"])


# ------------------------------- Schemas -------------------------------


class PolicyBody(BaseModel):
    sweep_percent: int | None = Field(default=None, ge=0, le=100)
    allowed_assets: list[str] | None = None
    min_sweep_atomic: int | None = Field(default=None, ge=0)
    per_transfer_cap_atomic: int | None = Field(default=None, ge=0)
    daily_cap_atomic: int | None = Field(default=None, ge=0)
    cooldown_seconds: int | None = Field(default=None, ge=0, le=86_400)
    destination_wallet_id: str | None = None


class WalletBody(BaseModel):
    role: str = Field(pattern="^(BOT|MAIN)$")
    address: str = Field(min_length=32, max_length=64)
    allowlisted: bool = False


class TransferBody(BaseModel):
    source_wallet_id: str
    asset: str
    amount_atomic: int = Field(gt=0)
    destination_wallet_id: str | None = None


class TransferIntentBody(TransferBody):
    idempotency_key: str = Field(min_length=1, max_length=128)


class ReconcileBody(BaseModel):
    outcome: str = Field(pattern="^(CONFIRMED|FAILED)$")
    signature: str | None = Field(default=None, max_length=128)


# ------------------------------- Helpers -------------------------------


def _wallet_json(w: WalletAccount) -> dict:
    return {
        "id": w.id,
        "wallet_role": w.wallet_role,
        "chain": w.chain,
        "public_address": w.public_address,
        "is_allowlisted": bool(w.is_allowlisted),
        "status": w.status,
        "created_at": w.created_at.isoformat() if w.created_at else None,
    }


def _snapshot_json(s: WalletBalanceSnapshot) -> dict:
    return {
        "wallet_account_id": s.wallet_account_id,
        "asset": s.asset,
        "mint_address": s.mint_address,
        "balance_atomic": s.balance_atomic,
        "spendable_atomic": s.spendable_atomic,
        "balance_ui": ws.from_atomic(s.balance_atomic, s.asset),
        "observed_at": s.observed_at.isoformat() if s.observed_at else None,
        "rpc_provider": s.rpc_provider,
        "commitment": s.commitment,
        "status": s.status,
    }


def _transfer_json(t: WalletTransfer | None) -> dict | None:
    if t is None:
        return None
    return {
        "id": t.id,
        "withdrawal_intent_id": t.withdrawal_intent_id,
        "chain": t.chain,
        "transaction_signature": t.transaction_signature,
        "submission_attempt": t.submission_attempt,
        "rpc_provider": t.rpc_provider,
        "commitment_target": t.commitment_target,
        "submitted_at": t.submitted_at.isoformat() if t.submitted_at else None,
        "confirmed_at": t.confirmed_at.isoformat() if t.confirmed_at else None,
        "failure_code": t.failure_code,
        "reconciliation_status": t.reconciliation_status,
    }


def _intent_detail(db: Session, i: WithdrawalIntent) -> dict:
    payload = ws._intent_json(i)
    transfer = db.query(WalletTransfer).filter(WalletTransfer.withdrawal_intent_id == i.id).first()
    payload["transfer"] = _transfer_json(transfer)
    payload["source_wallet_id"] = i.source_wallet_id
    payload["destination_wallet_id"] = i.destination_wallet_id
    payload["mint_address"] = i.mint_address
    payload["actual_fee_atomic"] = i.actual_fee_atomic
    payload["reserve_snapshot"] = i.reserve_snapshot
    payload["created_by"] = i.created_by
    payload["expires_at"] = i.expires_at.isoformat() if i.expires_at else None
    return payload


def _parse_assets(raw: str | None) -> list[str]:
    if not raw:
        return list(ws.ALLOWED_ASSETS)
    assets = [a.strip().upper() for a in raw.split(",") if a.strip()]
    bad = [a for a in assets if a not in ws.ALLOWED_ASSETS]
    if bad:
        raise ValidationError(f"assets outside the locked allowlist {list(ws.ALLOWED_ASSETS)}: {bad}")
    return assets


# ------------------------------- Wallets -------------------------------


@router.get("/wallets")
def list_wallets(db: Session = Depends(get_db), actor: str = Depends(current_actor)):
    rows = db.query(WalletAccount).order_by(WalletAccount.wallet_role, WalletAccount.created_at).all()
    return {
        "items": [_wallet_json(w) for w in rows],
        "main_wallet_allowlisted_id": (ws.get_main_wallet(db).id if ws.get_main_wallet(db) else None),
        "gates": {
            "wallet_onchain_enabled": ws.is_wallet_enabled(db),
            "profit_sweep_enabled": ws.is_sweep_enabled(db),
        },
        "allowed_assets": list(ws.ALLOWED_ASSETS),
    }


@router.post("/wallets", status_code=201)
def create_wallet(payload: WalletBody, db: Session = Depends(get_db), actor: str = Depends(require_operator)):
    """Register a public address. Private keys are never accepted or stored."""
    if " " in payload.address.strip():
        raise ValidationError("address must not contain whitespace")
    w = ws.register_wallet(db, payload.role, payload.address.strip(), actor, allowlisted=payload.allowlisted)
    return _wallet_json(w)


@router.get("/wallets/{wallet_id}/balances")
def wallet_balances(
    wallet_id: str,
    assets: str | None = Query(default=None, description="Comma-separated, SOL and USDC only"),
    db: Session = Depends(get_db),
    actor: str = Depends(current_actor),
):
    w = db.get(WalletAccount, wallet_id)
    if w is None:
        raise NotFoundError("wallet", wallet_id)
    wanted = _parse_assets(assets)
    items = []
    for asset in wanted:
        # Display path: pass require_ok=False so "never read" (UNAVAILABLE) stays
        # distinguishable from "read and failed" (UNKNOWN). Every spending path
        # uses the default and sees None for both.
        snap = ws.latest_snapshot(db, wallet_id, asset, require_ok=False)
        entry = {"asset": asset, "decimals": ws.asset_decimals(asset)}
        if snap is None:
            # Missing/stale is reported explicitly, never coerced to zero.
            entry["status"] = "UNAVAILABLE"
            entry["balance_atomic"] = None
            entry["spendable_atomic"] = None
        else:
            entry.update(_snapshot_json(snap))
            # Deliberately NOT hardcoded to "OK". A snapshot written by a failed
            # chain read is `UNKNOWN`, and reporting it as OK would show the UI
            # a balance of zero as if it had been measured - the exact failure
            # this subsystem exists to avoid.
            entry["status"] = snap.status
            entry["age_seconds"] = round((ws._now() - ws._aware(snap.observed_at)).total_seconds(), 3)
        items.append(entry)
    return {"wallet": _wallet_json(w), "items": items}


@router.post("/wallets/balances/refresh")
def refresh_balances(
    assets: str | None = Query(default=None, description="Comma-separated, SOL and USDC only"),
    db: Session = Depends(get_db),
    actor: str = Depends(require_operator),
):
    """Read on-chain balances now and record them as snapshots.

    The worker does this on a schedule; this endpoint exists so an operator
    does not have to wait for it. A read that fails records an UNKNOWN
    snapshot and reports `unknown` in the summary - it is never reported as a
    balance of zero.
    """
    from app.services.wallet_balance_service import refresh_wallet_balances

    summary = refresh_wallet_balances(db, assets=tuple(_parse_assets(assets)))
    return summary


@router.get("/wallets/{wallet_id}/reserve")
def wallet_reserve(
    wallet_id: str,
    asset: str = Query(default="SOL"),
    db: Session = Depends(get_db),
    actor: str = Depends(current_actor),
):
    if db.get(WalletAccount, wallet_id) is None:
        raise NotFoundError("wallet", wallet_id)
    asset = asset.upper()
    if asset not in ws.ALLOWED_ASSETS:
        raise ValidationError(f"asset must be one of {list(ws.ALLOWED_ASSETS)}")
    r = ws.compute_dynamic_reserve(db, wallet_id, asset, fee_atomic=ws.SOL_FEE_LAMPORTS)
    return {
        "wallet_id": wallet_id,
        "asset": asset,
        "reserve_policy": "DYNAMIC",
        "open_position_exposure_atomic": r.open_position_exposure_atomic,
        "pending_outflows_atomic": r.pending_outflows_atomic,
        "estimated_fees_atomic": r.estimated_fees_atomic,
        "operational_buffer_atomic": r.operational_buffer_atomic,
        "total_atomic": r.total_atomic,
        "total_ui": ws.from_atomic(r.total_atomic, asset),
    }


@router.get("/wallets/{wallet_id}/sweepable")
def wallet_sweepable(
    wallet_id: str,
    asset: str = Query(default="SOL"),
    db: Session = Depends(get_db),
    actor: str = Depends(current_actor),
):
    """Dry evaluation only. Never signs or submits."""
    if db.get(WalletAccount, wallet_id) is None:
        raise NotFoundError("wallet", wallet_id)
    asset = asset.upper()
    if asset not in ws.ALLOWED_ASSETS:
        raise ValidationError(f"asset must be one of {list(ws.ALLOWED_ASSETS)}")
    ev = ws.evaluate_sweep(db, wallet_id, asset)
    return {
        "wallet_id": wallet_id,
        "asset": ev.asset,
        "eligible_realized_profit_atomic": ev.eligible_realized_atomic,
        "sweep_target_atomic": ev.sweep_target_atomic,
        "available_atomic": ev.available_atomic,
        "reserve_atomic": ev.reserve_atomic,
        "pending_outflows_atomic": ev.pending_outflows_atomic,
        "estimated_fee_atomic": ev.fee_atomic,
        "sweepable_atomic": ev.sweepable_atomic,
        "sweepable_ui": ws.from_atomic(ev.sweepable_atomic, ev.asset),
        "reasons": ev.reasons,
        "reserve_breakdown": ev.reserve_breakdown,
        "onchain_submission": "DISABLED" if not ws.is_wallet_enabled(db) else "GATE_OPEN_REQUIRES_SIGNER",
    }


# ------------------------------- Policy -------------------------------


@router.get("/wallet-policy")
def get_wallet_policy(db: Session = Depends(get_db), actor: str = Depends(current_actor)):
    p = ws.get_policy(db) or ws.default_policy(db)
    return {"policy": ws.policy_json(p), "gates": {
        "wallet_onchain_enabled": ws.is_wallet_enabled(db),
        "profit_sweep_enabled": ws.is_sweep_enabled(db),
    }}


@router.put("/wallet-policy")
def update_wallet_policy(payload: PolicyBody, db: Session = Depends(get_db), actor: str = Depends(require_operator)):
    """Creates a NEW policy version + audit event; previous versions are immutable."""
    changes = payload.model_dump(exclude_none=True)
    if not changes:
        raise ValidationError("no policy fields supplied")
    p = ws.set_policy(db, actor, changes)
    return {"policy": ws.policy_json(p)}


# ------------------------------- Transfers -------------------------------


@router.post("/wallet-transfers/validate")
def validate_transfer_endpoint(payload: TransferBody, db: Session = Depends(get_db), actor: str = Depends(current_actor)):
    """Full dry validation for the manual confirmation screen. Creates nothing."""
    return ws.validate_transfer(
        db,
        source_wallet_id=payload.source_wallet_id,
        asset=payload.asset.upper(),
        amount_atomic=payload.amount_atomic,
        destination_wallet_id=payload.destination_wallet_id,
    )


@router.post("/wallet-transfers", status_code=201)
def create_transfer(
    payload: TransferIntentBody,
    db: Session = Depends(get_db),
    actor: str = Depends(require_operator),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    """Create a manual withdrawal intent. Idempotency key required (header or body)."""
    key = idempotency_key or payload.idempotency_key
    if not key:
        raise ValidationError("idempotency_key required (header Idempotency-Key or body field)")
    result = ws.create_withdrawal_intent(
        db,
        actor,
        source_wallet_id=payload.source_wallet_id,
        asset=payload.asset.upper(),
        amount_atomic=payload.amount_atomic,
        idempotency_key=key,
        trigger_type="MANUAL",
        destination_wallet_id=payload.destination_wallet_id,
    )
    intent_id = result["intent"]["id"]
    return {**result, "detail": _intent_detail(db, db.get(WithdrawalIntent, intent_id))}


@router.post("/wallet-transfers/{intent_id}/confirm")
def confirm_transfer(intent_id: str, db: Session = Depends(get_db), actor: str = Depends(require_operator)):
    """Operator confirms the intent. Balance and reserve are re-validated here,
    immediately before the signing gate. If the wallet gate is OFF (V1 default)
    the transition is refused with 403 rather than silently succeeding."""
    intent = db.get(WithdrawalIntent, intent_id)
    if intent is None:
        raise NotFoundError("withdrawal_intent", intent_id)
    if intent.state == "AWAITING_CONFIRMATION":
        ws.transition_intent(db, intent_id, actor, "READY_TO_SIGN", reason="operator confirmed")
    elif intent.state == "VALIDATING":
        ws.transition_intent(db, intent_id, actor, "AWAITING_CONFIRMATION", reason="awaiting operator")
        ws.transition_intent(db, intent_id, actor, "READY_TO_SIGN", reason="operator confirmed")
    else:
        raise ValidationError(f"intent in state {intent.state} cannot be confirmed")
    return _intent_detail(db, db.get(WithdrawalIntent, intent_id))


@router.post("/wallet-transfers/{intent_id}/cancel")
def cancel_transfer(intent_id: str, payload: dict | None = None, db: Session = Depends(get_db), actor: str = Depends(require_operator)):
    reason = (payload or {}).get("reason", "operator cancelled")
    ws.transition_intent(db, intent_id, actor, "CANCELLED", reason=reason)
    return _intent_detail(db, db.get(WithdrawalIntent, intent_id))


@router.get("/wallet-transfers")
def list_transfers(
    state: str | None = None,
    asset: str | None = None,
    trigger_type: str | None = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db),
    actor: str = Depends(current_actor),
):
    q = db.query(WithdrawalIntent)
    if state:
        q = q.filter(WithdrawalIntent.state == state)
    if asset:
        q = q.filter(WithdrawalIntent.asset == asset.upper())
    if trigger_type:
        q = q.filter(WithdrawalIntent.trigger_type == trigger_type)
    total = q.count()
    rows = q.order_by(WithdrawalIntent.created_at.desc()).offset(offset).limit(limit).all()
    return {
        "items": [_intent_detail(db, r) for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/wallet-transfers/{intent_id}")
def get_transfer(intent_id: str, db: Session = Depends(get_db), actor: str = Depends(current_actor)):
    intent = db.get(WithdrawalIntent, intent_id)
    if intent is None:
        raise NotFoundError("withdrawal_intent", intent_id)
    return _intent_detail(db, intent)


@router.post("/wallet-transfers/{intent_id}/reconcile")
def reconcile_transfer(intent_id: str, payload: ReconcileBody, db: Session = Depends(get_db), actor: str = Depends(require_operator)):
    """Resolve RECONCILIATION_REQUIRED with an observed on-chain outcome.
    Never blind-retries; a replacement transfer always requires a NEW intent."""
    result = ws.reconcile_intent(db, intent_id, actor, outcome=payload.outcome, signature=payload.signature)
    return {**result, "detail": _intent_detail(db, db.get(WithdrawalIntent, intent_id))}


# ------------------------------- Profit sweep -------------------------------


@router.post("/profit-sweep/evaluate")
def evaluate_sweep_endpoint(payload: dict | None = None, db: Session = Depends(get_db), actor: str = Depends(require_operator)):
    """Dry-run evaluation across both assets. MUST NOT sign or submit."""
    wallet_id = (payload or {}).get("wallet_id")
    assets = _parse_assets((payload or {}).get("assets"))
    if wallet_id is None:
        bot = db.query(WalletAccount).filter(WalletAccount.wallet_role == "BOT").order_by(WalletAccount.created_at).first()
        if bot is None:
            raise NotFoundError("wallet", "BOT wallet not registered")
        wallet_id = bot.id
    items = []
    for asset in assets:
        ev = ws.evaluate_sweep(db, wallet_id, asset)
        items.append({
            "asset": ev.asset,
            "eligible_realized_profit_atomic": ev.eligible_realized_atomic,
            "sweep_target_atomic": ev.sweep_target_atomic,
            "available_atomic": ev.available_atomic,
            "reserve_atomic": ev.reserve_atomic,
            "pending_outflows_atomic": ev.pending_outflows_atomic,
            "estimated_fee_atomic": ev.fee_atomic,
            "sweepable_atomic": ev.sweepable_atomic,
            "sweepable_ui": ws.from_atomic(ev.sweepable_atomic, ev.asset),
            "reasons": ev.reasons,
            "reserve_breakdown": ev.reserve_breakdown,
        })
    return {
        "wallet_id": wallet_id,
        "sweep_percent": (ws.get_policy(db) or ws.default_policy(db)).sweep_percent,
        "items": items,
        "sweep_gate_enabled": ws.is_sweep_enabled(db),
        "onchain_submission": "DISABLED" if not ws.is_wallet_enabled(db) else "GATE_OPEN_REQUIRES_SIGNER",
        "note": "dry run: no transaction was signed or submitted",
    }


@router.get("/profit-sweep/events")
def list_sweep_events(
    status: str | None = None,
    asset: str | None = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db),
    actor: str = Depends(current_actor),
):
    q = db.query(ProfitSweepEvent)
    if status:
        q = q.filter(ProfitSweepEvent.status == status)
    if asset:
        q = q.filter(ProfitSweepEvent.asset == asset.upper())
    total = q.count()
    rows = q.order_by(ProfitSweepEvent.created_at.desc()).offset(offset).limit(limit).all()
    return {
        "items": [
            {
                "id": e.id,
                "close_event_id": e.close_event_id,
                "asset": e.asset,
                "realized_profit_atomic": e.realized_profit_atomic,
                "sweep_percent": e.sweep_percent,
                "sweep_amount_atomic": e.sweep_amount_atomic,
                "sweep_amount_ui": ws.from_atomic(e.sweep_amount_atomic, e.asset),
                "policy_version": e.policy_version,
                "reserve_snapshot": e.reserve_snapshot,
                "withdrawal_intent_id": e.withdrawal_intent_id,
                "status": e.status,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("/profit-sweep/enable")
def enable_sweep(db: Session = Depends(get_db), actor: str = Depends(require_operator)):
    return {"profit_sweep_enabled": ws.set_sweep_enabled(db, True, actor)}


@router.post("/profit-sweep/disable")
def disable_sweep(db: Session = Depends(get_db), actor: str = Depends(require_operator)):
    return {"profit_sweep_enabled": ws.set_sweep_enabled(db, False, actor)}