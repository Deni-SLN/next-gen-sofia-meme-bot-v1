"""Database engine and session wiring.

Schema ownership: Alembic is the single source of truth for migrations
(PRD §11). `create_all` is a development convenience only and is refused
outside development, because it cannot alter an existing table, cannot express
data migrations, and leaves no record of what was applied.
"""

import logging

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.base import Base

log = logging.getLogger("sofia.db")

DEV_ENVS = {"development", "test", "local"}


def _make_engine():
    url = settings.database_url
    kwargs: dict = {"future": True, "pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    engine = create_engine(url, **kwargs)
    if url.startswith("sqlite"):
        _enable_sqlite_foreign_keys(engine)
    return engine


def _enable_sqlite_foreign_keys(engine) -> None:  # noqa: ANN001
    """SQLite disables foreign keys unless asked per connection.

    Without this, declared FKs are inert and orphaned fills/positions can be
    written silently (the real failure mode this project already hit).
    """
    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def _set_pragma(dbapi_connection, _record):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _ensure_sqlite_dir() -> None:
    if not settings.database_url.startswith("sqlite"):
        return
    import os

    db_path = settings.database_url.replace("sqlite:///", "")
    if db_path and db_path != ":memory:":
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)


def current_revision() -> str | None:
    """Return the Alembic revision stamped on the database, if any."""
    try:
        inspector = inspect(engine)
        if "alembic_version" not in inspector.get_table_names():
            return None
        with engine.connect() as conn:
            row = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).scalar()
        return row
    except Exception:  # noqa: BLE001
        log.exception("could not read alembic_version")
        return None


def schema_is_current(head: str = "head") -> bool:
    """True when the database is stamped at the expected revision."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    repo_root = _repo_root()
    cfg = Config(str(repo_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(repo_root / "migrations"))
    script = ScriptDirectory.from_config(cfg)
    target = script.get_revision(head).revision if head != "head" else script.get_current_head()
    return current_revision() == target


def _repo_root():
    """Walk up from this file until the directory holding alembic.ini is found.

    Depth-independent, so moving the package around does not break it.
    """
    from pathlib import Path

    for candidate in Path(__file__).resolve().parents:
        if (candidate / "alembic.ini").exists():
            return candidate
    raise RuntimeError(
        f"could not locate the repository root (no alembic.ini found above {__file__})"
    )


def init_db() -> None:
    """Prepare the database on startup.

    Development: create any missing tables so a fresh checkout runs without
    ceremony. Elsewhere: refuse to serve if the schema is not at the expected
    Alembic revision, and tell the operator to run `alembic upgrade head`.
    """
    from app import models  # noqa: F401  ensure models are registered

    _ensure_sqlite_dir()

    if settings.env in DEV_ENVS:
        Base.metadata.create_all(bind=engine)
        log.info("dev bootstrap: create_all() ran (Alembic is authoritative for real migrations)")
        return

    if current_revision() is None:
        raise RuntimeError(
            "database has no alembic_version table. Run `alembic upgrade head` "
            f"before starting the API in {settings.env}."
        )
    if not schema_is_current():
        raise RuntimeError(
            "database schema is behind (current={}, expected={}). "
            "Run `alembic upgrade head` before starting the API.".format(
                current_revision(), "head"
            )
        )


__all__ = [
    "Base",
    "Session",
    "SessionLocal",
    "current_revision",
    "engine",
    "get_db",
    "init_db",
    "schema_is_current",
]

