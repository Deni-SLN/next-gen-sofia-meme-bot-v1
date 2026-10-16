"""Provider health recording and runtime settings helpers."""

from datetime import UTC, datetime

from app.db.session import SessionLocal
from app.models.market import ProviderHealth
from app.models.ops import SettingEntry


def record_provider_health(provider: str, ok: bool, latency_ms: float | None = None, error: str | None = None) -> None:
    try:
        db = SessionLocal()
        try:
            row = db.query(ProviderHealth).filter(ProviderHealth.provider == provider).first()
            now = datetime.now(UTC)
            if row is None:
                row = ProviderHealth(provider=provider, status="UNKNOWN")
                db.add(row)
            row.status = "UP" if ok else "DOWN"
            row.latency_ms = latency_ms
            row.updated_at = now
            if ok:
                row.last_success_at = now
                row.error_count = 0
                row.last_error_message = None
            else:
                row.last_error_at = now
                row.error_count = (row.error_count or 0) + 1
                row.last_error_message = (error or "")[:500]
            db.commit()
        finally:
            db.close()
    except Exception:  # noqa: BLE001 - never let health tracking break the caller
        pass


def get_setting(key: str, default=None):
    db = SessionLocal()
    try:
        row = db.query(SettingEntry).filter(SettingEntry.key == key).first()
        if row is None:
            return default
        return row.value_json.get("value", default)
    finally:
        db.close()


def set_setting(key: str, value) -> None:
    db = SessionLocal()
    try:
        row = db.query(SettingEntry).filter(SettingEntry.key == key).first()
        if row is None:
            row = SettingEntry(key=key, value_json={"value": value})
            db.add(row)
        else:
            row.value_json = {"value": value}
        db.commit()
    finally:
        db.close()
