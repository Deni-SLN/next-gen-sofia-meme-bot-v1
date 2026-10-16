"""Trading bot engine service (FR-TB-001..008).

Signal intake (idempotent) -> risk gate -> paper execution -> positions ->
accounting events. LIVE start is always rejected in V1.
"""

import math
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import ConflictError, ValidationError
from app.models.ops import SettingEntry
from app.models.trading import BotRun

BOT_STATE_KEY = "bot_state"


def default_bot_state() -> dict:
    return {
        "mode": "PAPER",
        "status": "STOPPED",
        "kill_switch_active": False,
        "active_run_id": None,
        "last_loss_at": None,
    }


def get_bot_state(db: Session) -> dict:
    row = db.query(SettingEntry).filter(SettingEntry.key == BOT_STATE_KEY).first()
    if row is None:
        return default_bot_state()
    state = default_bot_state()
    state.update(row.value_json or {})
    return state


def save_bot_state(db: Session, state: dict) -> None:
    row = db.query(SettingEntry).filter(SettingEntry.key == BOT_STATE_KEY).first()
    if row is None:
        db.add(SettingEntry(key=BOT_STATE_KEY, value_json=state))
    else:
        row.value_json = state
    db.commit()


def get_risk_config(db: Session) -> dict:
    from app.risk.gate import DEFAULT_RISK_CONFIG

    row = db.query(SettingEntry).filter(SettingEntry.key == "bot_risk_config").first()
    cfg = dict(DEFAULT_RISK_CONFIG)
    if row and isinstance(row.value_json, dict):
        cfg.update(row.value_json)
    return cfg


def set_risk_config(db: Session, cfg: dict) -> None:
    for k, v in cfg.items():
        if isinstance(v, float) and not math.isfinite(v):
            raise ValidationError(f"risk config {k} must be finite")
    row = db.query(SettingEntry).filter(SettingEntry.key == "bot_risk_config").first()
    if row is None:
        db.add(SettingEntry(key="bot_risk_config", value_json=cfg))
    else:
        row.value_json = cfg
    db.commit()


def get_initial_capital(db: Session) -> float:
    row = db.query(SettingEntry).filter(SettingEntry.key == "initial_capital").first()
    if row is None:
        return settings.initial_paper_capital
    val = row.value_json.get("value")
    return float(val) if isinstance(val, (int, float)) else settings.initial_paper_capital


def set_mode(db: Session, mode: str, actor: str) -> dict:
    if mode not in ("ANALYSIS_ONLY", "PAPER", "LIVE"):
        raise ValidationError(f"invalid mode {mode}")
    if mode == "LIVE":
        from app.execution.live_stub import assert_live_allowed

        assert_live_allowed()
    state = get_bot_state(db)
    state["mode"] = mode
    save_bot_state(db, state)
    from app.services.audit_service import write_audit

    write_audit(actor, "set_mode", "bot", None, {"mode": mode}, db)
    return state


def start_bot(db: Session, actor: str, mode: str | None = None) -> dict:
    from app.execution.live_stub import LiveExecutionDisabledError

    state = get_bot_state(db)
    effective_mode = mode or state["mode"]
    if effective_mode == "LIVE":
        raise LiveExecutionDisabledError()
    if state["status"] == "RUNNING":
        raise ConflictError("bot already running")
    state["mode"] = effective_mode
    state["status"] = "RUNNING"
    state["kill_switch_active"] = False
    run = BotRun(
        mode=effective_mode if effective_mode != "ANALYSIS_ONLY" else "PAPER",
        started_by=actor,
        status="RUNNING",
    )
    db.add(run)
    db.flush()
    state["active_run_id"] = run.id
    save_bot_state(db, state)
    from app.services.audit_service import write_audit

    write_audit(actor, "bot_start", "bot_run", run.id, {"mode": effective_mode}, db)
    return state


def _finish_run(db: Session, actor: str, reason: str, status: str) -> dict:
    state = get_bot_state(db)
    state["status"] = status
    run_id = state.get("active_run_id")
    if run_id:
        run = db.get(BotRun, run_id)
        if run and run.status == "RUNNING":
            run.status = status
            run.stopped_at = datetime.now(UTC)
            run.stop_reason = reason
    if status == "STOPPED":
        state["active_run_id"] = None
    save_bot_state(db, state)
    from app.services.audit_service import write_audit

    write_audit(actor, f"bot_{status.lower()}", "bot_run", run_id, {"reason": reason}, db)
    return state


def pause_bot(db: Session, actor: str) -> dict:
    state = get_bot_state(db)
    if state["status"] != "RUNNING":
        raise ConflictError("bot is not running")
    return _finish_run(db, actor, "operator pause", "PAUSED")


def resume_bot(db: Session, actor: str) -> dict:
    state = get_bot_state(db)
    if state["status"] != "PAUSED":
        raise ConflictError("bot is not paused")
    state["status"] = "RUNNING"
    run_id = state.get("active_run_id")
    if run_id:
        run = db.get(BotRun, run_id)
        if run:
            run.status = "RUNNING"
    save_bot_state(db, state)
    from app.services.audit_service import write_audit

    write_audit(actor, "bot_resume", "bot_run", run_id, {}, db)
    return state


def stop_bot(db: Session, actor: str, reason: str = "operator stop") -> dict:
    state = get_bot_state(db)
    if state["status"] == "STOPPED":
        raise ConflictError("bot already stopped")
    return _finish_run(db, actor, reason, "STOPPED")


def emergency_stop(db: Session, actor: str) -> dict:
    state = get_bot_state(db)
    state["kill_switch_active"] = True
    state["status"] = "STOPPED"
    run_id = state.get("active_run_id")
    if run_id:
        run = db.get(BotRun, run_id)
        if run:
            run.status = "STOPPED"
            run.stopped_at = datetime.now(UTC)
            run.stop_reason = "EMERGENCY_STOP"
    state["active_run_id"] = None
    save_bot_state(db, state)
    from app.services.audit_service import write_audit

    write_audit(actor, "emergency_stop", "bot", None, {"run_id": run_id}, db)
    return state


def clear_kill_switch(db: Session, actor: str) -> dict:
    state = get_bot_state(db)
    state["kill_switch_active"] = False
    save_bot_state(db, state)
    from app.services.audit_service import write_audit

    write_audit(actor, "clear_kill_switch", "bot", None, {}, db)
    return state

