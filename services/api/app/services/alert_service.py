"""Alert rules and Telegram delivery (PRD §15).

Before this, `AlertDelivery` was a table nobody wrote to, and the Telegram
settings were declared, redacted from logs, documented in `.env.example` - and
then never read. An operator could configure a bot token and receive silence.

Design constraints, in order of importance:

1. **No secrets in an alert.** The bot token is used to make a request and
   never appears in a message, a log line, or an error body.
2. **Deduplicated by key, enforced by the database.** `alert_deliveries.dedup_key`
   is UNIQUE. That constraint is the arbiter - not a time window - so a rule
   that should be able to re-fire after a delay must put a time bucket in its
   key (see `drawdown:20` style keys). An earlier version carried a
   `cooldown_seconds` parameter; it could never take effect, because the second
   insert would violate the unique index before any timer was consulted.
3. **Missing configuration is not a delivery failure.** With no bot token
   configured, rules still evaluate and still record - as `SKIPPED`. A
   misconfigured channel must not take the alerting subsystem down with it.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from app.core.config import settings
from app.models.ops import AlertDelivery

STATUS_PENDING = "PENDING"
STATUS_SENT = "SENT"
STATUS_SKIPPED = "SKIPPED"
STATUS_FAILED = "FAILED"


@dataclass(frozen=True)
class Alert:
    dedup_key: str
    title: str
    body: str
    severity: str = "info"
    reference_type: str | None = None
    reference_id: str | None = None


def _telegram_configured() -> bool:
    return bool(settings.telegram_bot_token and settings.telegram_chat_id)


def record_alert(db, alert: Alert, now: datetime | None = None) -> dict:
    """Record an alert, once per dedup key.

    Returns what happened without raising: an alerting path must not be able
    to take down the job that raised the alert. The UNIQUE index on
    `dedup_key` is the arbiter, so a rule that needs to re-fire must advance
    the bucket in its key rather than relying on a time window here.
    """
    now = now or datetime.now(UTC)
    existing = (
        db.query(AlertDelivery).filter(AlertDelivery.dedup_key == alert.dedup_key).first()
    )
    if existing is not None:
        return {
            "recorded": False,
            "reason": "duplicate dedup_key",
            "dedup_key": alert.dedup_key,
            "id": existing.id,
        }

    row = AlertDelivery(
        reference_type=alert.reference_type,
        reference_id=alert.reference_id,
        channel="TELEGRAM",
        dedup_key=alert.dedup_key,
        title=alert.title[:128],
        body=alert.body[:1024],
        delivery_status=STATUS_PENDING,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"recorded": True, "id": row.id, "dedup_key": alert.dedup_key}


# --------------------------- delivery ---------------------------


def send_telegram(alert: Alert, timeout: float = 10.0) -> dict:
    """Send one message. Never raises; reports what happened instead.

    Returns a dict rather than the response so a token can never leak through
    an exception message or a repr.
    """
    if not _telegram_configured():
        return {"ok": False, "skipped": True, "reason": "telegram is not configured"}

    import httpx

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": settings.telegram_chat_id,
        "text": f"[{alert.severity.upper()}] {alert.title}\n\n{alert.body}"[:4000],
        "disable_web_page_preview": True,
    }
    try:
        response = httpx.post(url, json=payload, timeout=timeout)
        if response.status_code >= 400:
            # Deliberately does not echo the body: it can contain the chat id.
            return {"ok": False, "reason": f"telegram returned HTTP {response.status_code}"}
        return {"ok": True}
    except Exception as e:  # noqa: BLE001 - delivery must never propagate
        return {"ok": False, "reason": f"{type(e).__name__}: {e}"[:200]}


def deliver(db, alert_id: str, alert: Alert) -> dict:
    """Attempt delivery for a recorded alert and stamp the outcome."""
    row = db.query(AlertDelivery).filter(AlertDelivery.id == alert_id).first()
    if row is None:
        return {"ok": False, "reason": "alert not found"}

    result = send_telegram(alert)
    row.attempt_count += 1
    if result.get("ok"):
        row.delivery_status = STATUS_SENT
        row.sent_at = datetime.now(UTC)
    elif result.get("skipped"):
        row.delivery_status = STATUS_SKIPPED
    else:
        row.delivery_status = STATUS_FAILED
    db.commit()
    return {**result, "delivery_status": row.delivery_status, "id": row.id}


def flush_pending(db, limit: int = 50) -> dict:
    """Deliver everything queued but not yet sent."""
    rows = (
        db.query(AlertDelivery)
        .filter(AlertDelivery.delivery_status == STATUS_PENDING)
        .order_by(AlertDelivery.created_at.asc())
        .limit(limit)
        .all()
    )
    sent, skipped, failed = 0, 0, 0
    for row in rows:
        alert = Alert(
            dedup_key=row.dedup_key,
            title=row.title or "",
            body=row.body or "",
            reference_type=row.reference_type,
            reference_id=row.reference_id,
        )
        result = deliver(db, row.id, alert)
        if result.get("ok"):
            sent += 1
        elif result.get("skipped"):
            skipped += 1
        else:
            failed += 1
    return {"considered": len(rows), "sent": sent, "skipped": skipped, "failed": failed}


# --------------------------- rules ---------------------------


def evaluate_alert_rules(db, now: datetime | None = None) -> dict:
    """The standing alert conditions an operator would otherwise poll for."""
    from app.models.trading import Position

    now = now or datetime.now(UTC)
    fired: list[dict] = []

    # A valuation the ledger cannot price blocks new entries (risk gate
    # fail-closed). The operator needs to know that is happening.
    from app.accounting.valuation import value_position

    open_positions = db.query(Position).filter(Position.status == "OPEN").all()
    unvaluable = []
    for position in open_positions:
        valuation = value_position(db, position, now=now)
        if not valuation.is_known:
            unvaluable.append((position, valuation))

    if unvaluable:
        # Bucketed so an operator is reminded rather than told once and never
        # again; the unique index makes the bucket the dedup window.
        bucket = int(now.timestamp() // 3600)
        result = record_alert(
            db,
            Alert(
                dedup_key=f"valuation:unvaluable:{bucket}",
                title="Open positions are not priced",
                severity="warning",
                body=(
                    f"{len(unvaluable)} open position(s) have no usable mark. "
                    "New entries are blocked until they are resolved. "
                    + "; ".join(
                        f"{p.mint_address[:8]}: {v.status}({v.reason})" for p, v in unvaluable[:5]
                    )
                ),
                reference_type="position",
                reference_id=unvaluable[0][0].id,
            ),
            now=now,
        )
        fired.append(result)

    # Drawdown past the risk ceiling.
    from app.accounting.equity import summarize_mode
    from app.services.bot_service import get_initial_capital

    snapshot = summarize_mode(db, "PAPER", float(get_initial_capital(db)))
    if snapshot.current_drawdown_pct is not None and snapshot.current_drawdown_pct > 0:
        from app.risk.gate import DEFAULT_RISK_CONFIG

        ceiling = DEFAULT_RISK_CONFIG["max_drawdown_pct"]
        if snapshot.current_drawdown_pct >= ceiling:
            fired.append(
                record_alert(
                    db,
                    Alert(
                        dedup_key=f"risk:drawdown:{int(snapshot.current_drawdown_pct // 5) * 5}",
                        title="Drawdown past the risk ceiling",
                        severity="critical",
                        body=(
                            f"Current drawdown {snapshot.current_drawdown_pct:.2f}% "
                            f">= ceiling {ceiling}%."
                        ),
                        reference_type="equity",
                        reference_id=None,
                    ),
                    now=now,
                )
            )

    # A withdrawal intent parked outside a terminal state.
    from app.models.wallet import WithdrawalIntent
    from app.services.wallet_service import TERMINAL_STATES

    stuck = (
        db.query(WithdrawalIntent)
        .filter(WithdrawalIntent.state.notin_(list(TERMINAL_STATES)))
        .all()
    )
    if stuck:
        fired.append(
            record_alert(
                db,
                Alert(
                    dedup_key=f"wallet:intent_pending:{int(now.timestamp() // 3600)}",
                    title="Withdrawal intents pending",
                    severity="warning",
                    body=(
                        f"{len(stuck)} withdrawal intent(s) are not in a terminal state: "
                        + ", ".join(sorted({i.state for i in stuck}))
                    ),
                    reference_type="withdrawal_intent",
                    reference_id=stuck[0].id,
                ),
                now=now,
            )
        )

    return {"fired": fired, "recorded": sum(1 for f in fired if f.get("recorded"))}


__all__ = [
    "Alert",
    "STATUS_FAILED",
    "STATUS_PENDING",
    "STATUS_SENT",
    "STATUS_SKIPPED",
    "deliver",
    "evaluate_alert_rules",
    "flush_pending",
    "record_alert",
    "send_telegram",
]
