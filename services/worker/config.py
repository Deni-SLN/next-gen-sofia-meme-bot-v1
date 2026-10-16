"""Worker bootstrap: reuse the API settings and DB session.

Keeps a single source of truth for configuration (SOFIA_* env vars) so the
worker and API never drift apart.
"""

from app.core.config import settings  # noqa: F401
from app.core.logging import get_logger, setup_logging
from app.db.session import SessionLocal, init_db

log = get_logger("worker")


def bootstrap(strict: bool = False) -> None:
    """Prepare logging and the database.

    `strict=True` propagates the failure. `strict=False` logs it and returns so
    the scheduler can retry on its next tick - the worker outliving a database
    restart is better than a worker that exits and relies on `restart: unless-
    stopped`.
    """
    setup_logging()
    try:
        init_db()
    except Exception as exc:  # noqa: BLE001
        if strict:
            raise
        log.exception("init_db failed on worker bootstrap: %s", exc)


__all__ = ["settings", "SessionLocal", "bootstrap", "get_logger", "log"]
