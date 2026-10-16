"""Signal center & analysis history endpoints (FR §12.2, §13)."""

from app.api.v1.deps import current_actor
from app.core.errors import NotFoundError
from app.db.session import get_db
from app.models.analysis import AnalysisRun, Signal, SignalEvaluation
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

router = APIRouter(tags=["signals"])


def _signal_json(s: Signal) -> dict:
    return {
        "id": s.id,
        "mint_address": s.mint_address,
        "signal_type": s.signal_type,
        "status": s.status,
        "decision": s.decision,
        "reasons": s.reasons,
        "entry_reference": s.entry_reference,
        "stop_reference": s.stop_reference,
        "target_references": s.target_references,
        "risk_reward": s.risk_reward,
        "coverage": s.coverage,
        "risk_flags": s.risk_flags,
        "invalidation_conditions": s.invalidation_conditions,
        "engine_version": s.engine_version,
        "strategy_version": s.strategy_version,
        "data_timestamp": s.data_timestamp.isoformat() if s.data_timestamp else None,
        "expires_at": s.expires_at.isoformat() if s.expires_at else None,
        "invalidated_at": s.invalidated_at.isoformat() if s.invalidated_at else None,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "tradable": s.status not in ("REJECTED", "EXPIRED", "INVALIDATED"),
    }


@router.get("/signals")
def list_signals(
    db: Session = Depends(get_db),
    status: str | None = None,
    decision: str | None = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    actor: str = Depends(current_actor),
):
    q = db.query(Signal)
    if status:
        q = q.filter(Signal.status == status)
    if decision:
        q = q.filter(Signal.decision == decision)
    total = q.count()
    rows = q.order_by(Signal.created_at.desc()).offset(offset).limit(limit).all()
    return {"items": [_signal_json(s) for s in rows], "total": total, "limit": limit, "offset": offset}


@router.get("/signals/{signal_id}")
def get_signal(signal_id: str, db: Session = Depends(get_db), actor: str = Depends(current_actor)):
    s = db.get(Signal, signal_id)
    if s is None:
        raise NotFoundError("signal", signal_id)
    return _signal_json(s)


@router.get("/signals/{signal_id}/evaluations")
def get_signal_evaluations(signal_id: str, db: Session = Depends(get_db), actor: str = Depends(current_actor)):
    s = db.get(Signal, signal_id)
    if s is None:
        raise NotFoundError("signal", signal_id)
    rows = (
        db.query(SignalEvaluation)
        .filter(SignalEvaluation.signal_id == signal_id)
        .order_by(SignalEvaluation.evaluated_at.desc())
        .all()
    )
    return {
        "signal_id": signal_id,
        "items": [
            {
                "id": e.id,
                "horizon": e.horizon,
                "return_pct": e.return_pct,
                "net_return_pct": e.net_return_pct,
                "mae": e.mae,
                "mfe": e.mfe,
                "evaluation_status": e.evaluation_status,
                "evaluated_at": e.evaluated_at.isoformat() if e.evaluated_at else None,
            }
            for e in rows
        ],
    }


def _run_json(r: AnalysisRun) -> dict:
    return {
        "id": r.id,
        "token_id": r.token_id,
        "pair_id": r.pair_id,
        "engine_version": r.engine_version,
        "scoring_config_version": r.scoring_config_version,
        "score": r.score,
        "coverage": r.coverage,
        "decision": r.decision,
        "reasons": r.reasons,
        "indicators": r.indicators,
        "input_snapshot": r.input_snapshot,
        "provider_versions": r.provider_versions,
        "ai_summary_present": r.ai_summary is not None,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


@router.get("/analysis/runs")
def list_analysis_runs(
    db: Session = Depends(get_db),
    token_id: str | None = None,
    decision: str | None = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    actor: str = Depends(current_actor),
):
    q = db.query(AnalysisRun)
    if token_id:
        q = q.filter(AnalysisRun.token_id == token_id)
    if decision:
        q = q.filter(AnalysisRun.decision == decision)
    total = q.count()
    rows = q.order_by(AnalysisRun.created_at.desc()).offset(offset).limit(limit).all()
    return {"items": [_run_json(r) for r in rows], "total": total, "limit": limit, "offset": offset}


@router.get("/analysis/runs/{run_id}")
def get_analysis_run(run_id: str, db: Session = Depends(get_db), actor: str = Depends(current_actor)):
    r = db.get(AnalysisRun, run_id)
    if r is None:
        raise NotFoundError("analysis_run", run_id)
    out = _run_json(r)
    out["ai_summary"] = r.ai_summary
    return out
