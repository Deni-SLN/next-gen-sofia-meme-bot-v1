"""Background jobs (FR §8 scheduler, §13 alerting).

Jobs are idempotent and fail-closed: a failing job logs and continues to the
next tick. The worker never performs live execution and never mutates risk
limits or accounting directly (it uses the same services as the API).
"""

import asyncio
from datetime import UTC, datetime

from worker.config import bootstrap, get_logger

log = get_logger("worker.jobs")


def _now() -> datetime:
    return datetime.now(UTC)


# ----------------------------- Discovery -----------------------------


def job_discovery(session_factory) -> dict:
    """Discover + ingest Solana pairs from DEX Screener into the local DB.

    Also refreshes market snapshots for any currently OPEN positions whose
    token was not in the trending slice, so held positions do not turn STALE
    when they rotate out of top trending.
    """
    from app.models.trading import Position
    from app.providers.market.dexscreener import DexScreenerProvider
    from app.services.market_service import ingest_pairs
    from app.services.provider_service import record_provider_health

    dex = DexScreenerProvider()
    db = session_factory()
    try:
        try:
            pairs = asyncio.run(dex.trending(limit=30))
        except Exception as e:  # noqa: BLE001
            record_provider_health("dexscreener", ok=False, error=str(e)[:200])
            log.warning("discovery failed: %s", e)
            return {"ok": False, "error": str(e)[:200]}

        seen_mints = {p.mint_address for p in pairs if p.mint_address}
        open_mints = {
            p.mint_address
            for p in db.query(Position).filter(Position.status == "OPEN").all()
            if p.mint_address and p.mint_address not in seen_mints
        }
        extra_pairs = []
        for mint in open_mints:
            try:
                fetched = asyncio.run(dex.token_pairs(mint))
                if fetched:
                    fetched.sort(key=lambda x: x.liquidity_usd or 0.0, reverse=True)
                    extra_pairs.append(fetched[0])
            except Exception as e:  # noqa: BLE001
                log.warning("open position refresh failed for %s: %s", mint, e)

        result = ingest_pairs(db, pairs)
        if extra_pairs:
            # Ingest open-position snapshots without dropping them on discovery filters
            ingest_pairs(db, extra_pairs, filters={"allow_incomplete": True})
        log.info("discovery ingested: %s (open refreshed: %s)", result, len(extra_pairs))
        return {"ok": True, **result}
    finally:
        db.close()


# ----------------------------- Analysis -----------------------------


def job_analysis(session_factory, use_ai: bool = False) -> dict:
    """Run deterministic analysis over recently-ingested tokens lacking a recent run.

    `use_ai` was previously accepted and never referenced: a scheduler flag that
    did nothing. It now runs the narrative agents, whose output lands in
    `ai_summary` and is read by nobody in the scoring or risk path.
    """
    from app.models.analysis import AnalysisRun
    from app.models.market import Token, TokenPair
    from app.services import onchain_service
    from app.services.agent_service import run_narrative_agents
    from app.services.analysis_service import run_analysis

    db = session_factory()
    analyzed = 0
    narrated = 0
    try:
        pairs = db.query(TokenPair).order_by(TokenPair.created_at.desc()).limit(20).all()
        for pair in pairs:
            token = db.get(Token, pair.token_id)
            if token is None:
                continue
            recent = (
                db.query(AnalysisRun)
                .filter(AnalysisRun.token_id == token.id)
                .order_by(AnalysisRun.created_at.desc())
                .first()
            )
            # Throttle: skip if analyzed in the last 5 minutes.
            if recent and recent.created_at and (_now() - _aware(recent.created_at)).total_seconds() < 300:
                continue
            try:
                facts = onchain_service.get_or_fetch(db, token)
                run = run_analysis(db, token, pair, onchain_facts=facts)
                analyzed += 1
                if use_ai:
                    # Narrative only. Never re-derives the decision or score.
                    payload = run_narrative_agents(
                        db, token, pair, onchain=facts.to_json() if facts else None, run=run
                    )
                    if payload["agents"]:
                        run.ai_summary = {
                            **(run.ai_summary or {}),
                            "agents": payload["agents"],
                            "agent_meta": payload["meta"],
                        }
                        db.commit()
                        narrated += 1
                log.info("analyzed %s -> %s (score=%s)", token.symbol or token.mint_address[:8], run.decision, run.score)
            except Exception as e:  # noqa: BLE001
                log.warning("analysis failed for %s: %s", token.mint_address, e)
        return {"ok": True, "analyzed": analyzed, "narrated": narrated if use_ai else 0}
    finally:
        db.close()


# ----------------------------- Signal lifecycle -----------------------------


def job_signal_lifecycle(session_factory) -> dict:
    """Expire stale signals and process active signals for PAPER trading if the bot is running."""
    from app.models.analysis import Signal
    from app.services.bot_service import get_bot_state
    from app.services.trading_service import process_signal_for_trading

    db = session_factory()
    expired = 0
    processed = 0
    validated = 0
    try:
        now = _now()
        # Expire
        stale = (
            db.query(Signal)
            .filter(Signal.status.in_(["CREATED", "VALIDATED", "ACTIVE", "WAIT"]))
            .all()
        )
        for s in stale:
            if s.expires_at and _aware(s.expires_at) < now:
                s.status = "EXPIRED"
                expired += 1
        db.commit()

        # Trade active signals only if bot running in PAPER
        state = get_bot_state(db)
        if state.get("status") == "RUNNING" and state.get("mode") == "PAPER":
            active = (
                db.query(Signal)
                .filter(Signal.status.in_(["CREATED", "VALIDATED", "ACTIVE"]))
                .all()
            )
            for s in active:
                try:
                    process_signal_for_trading(db, s.id)
                    processed += 1
                except Exception as e:  # noqa: BLE001
                    log.warning("process signal %s failed: %s", s.id, e)

        # signal-validation runs after the decision, never before it: the
        # verdict is context attached to the analysis run, and nothing in the
        # execution path reads it.
        from app.services.agent_service import validate_signal

        for s in (
            db.query(Signal)
            .filter(Signal.status.in_(["ACTIVE", "EVALUATED"]))
            .order_by(Signal.created_at.desc())
            .limit(20)
            .all()
        ):
            try:
                validate_signal(db, s)
                validated += 1
            except Exception as e:  # noqa: BLE001
                log.warning("signal validation for %s failed: %s", s.id, e)

        return {"ok": True, "expired": expired, "processed": processed, "validated": validated}
    finally:
        db.close()


# ----------------------------- Wallet balances -----------------------------


def job_wallet_balances(session_factory) -> dict:
    """Read on-chain SOL/USDC balances and record them as snapshots.

    A read that fails records an UNKNOWN snapshot. It never records zero, and
    it never raises: the sweep layer is the thing that must fail closed on a
    missing balance, and it can only do that if the absence is visible.
    """
    from app.services.wallet_balance_service import refresh_wallet_balances

    db = session_factory()
    try:
        summary = refresh_wallet_balances(db)
        if summary["unknown"]:
            log.warning(
                "wallet balances: %s unknown of %s reads", summary["unknown"],
                summary["ok"] + summary["unknown"],
            )
        return summary
    except Exception as e:  # noqa: BLE001
        log.warning("wallet balance refresh failed: %s", e)
        return {"ok": False, "error": str(e)[:200]}
    finally:
        db.close()


# ----------------------------- Alerts -----------------------------


def job_alerts(session_factory) -> dict:
    """Evaluate alert rules, then flush anything queued for delivery."""
    from app.services.alert_service import evaluate_alert_rules, flush_pending

    db = session_factory()
    try:
        rules = evaluate_alert_rules(db)
        delivery = flush_pending(db)
        return {"ok": True, **rules, **delivery}
    except Exception as e:  # noqa: BLE001
        log.warning("alert evaluation failed: %s", e)
        return {"ok": False, "error": str(e)[:200]}
    finally:
        db.close()


# ----------------------------- Position lifecycle -----------------------------


def job_position_lifecycle(session_factory) -> dict:
    """Close open positions whose take-profit or stop-loss has been hit.

    PAPER only. Positions whose mark is missing or stale are held, not closed -
    the valuation layer decides what is usable, and this job just acts on it.
    """
    from app.services.position_manager import run_position_lifecycle

    db = session_factory()
    try:
        result = run_position_lifecycle(db, mode="PAPER")
        if result.get("closed"):
            log.info("position lifecycle closed %s: %s", len(result["closed"]), result["closed"])
        if result.get("recovered"):
            log.warning("position lifecycle recovered stalled exits: %s", result["recovered"])
        return result
    finally:
        db.close()


# ----------------------------- Signal evaluation -----------------------------


def job_signal_evaluation(session_factory) -> dict:
    """Evaluate realized outcomes for evaluated/expired signals vs latest price (MAE/MFE)."""
    from app.models.analysis import Signal, SignalEvaluation
    from app.services.performance_service import _finite

    db = session_factory()
    try:
        signals = (
            db.query(Signal)
            .filter(Signal.status.in_(["EVALUATED", "INVALIDATED", "EXPIRED"]))
            .order_by(Signal.created_at.desc())
            .limit(50)
            .all()
        )
        # Evaluation is a placeholder reconstruction: recorded for audit & future MAE/MFE.
        for s in signals:
            existing = db.query(SignalEvaluation).filter(SignalEvaluation.signal_id == s.id).first()
            if existing:
                continue
            if s.entry_reference and _finite(s.entry_reference):
                db.add(
                    SignalEvaluation(
                        signal_id=s.id,
                        horizon="H1",
                        evaluation_status="PENDING",
                    )
                )
        db.commit()
        return {"ok": True, "considered": len(signals)}
    finally:
        db.close()


def _aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


__all__ = [
    "job_alerts",
    "job_discovery",
    "job_analysis",
    "job_position_lifecycle",
    "job_signal_lifecycle",
    "job_signal_evaluation",
    "job_wallet_balances",
    "bootstrap",
]
