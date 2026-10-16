"""Shared fixtures for the worker tests.

The worker is a separate service with its own import root, so it needs its own
conftest. The database fixture mirrors the API's: fresh in-memory schema, SQLite
foreign keys enforced.
"""

import os

os.environ.setdefault("SOFIA_DATABASE_URL", "sqlite:///./data/test_worker.db")
os.environ.setdefault("SOFIA_ENV", "test")
os.environ.setdefault("SOFIA_AUTH_DISABLED", "true")

import pytest  # noqa: E402
from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

# A closed port on loopback: connections are refused immediately, so a job that
# reaches for a provider fails fast and fails closed instead of hanging the
# suite on DNS or a real network call.
UNREACHABLE = "http://127.0.0.1:1"
DEXSCREENER_ENV = "SOFIA_" + "DEXSCREENER_BASE_URL"


@pytest.fixture(autouse=True)
def offline_providers():
    """No worker test may reach the network.

    The worker is the component that runs unattended, so its tests are exactly
    where an accidental live provider call would hide.
    """
    from app.core.config import settings

    before = (settings.dexscreener_base_url, settings.solana_rpc_url)
    settings.dexscreener_base_url = UNREACHABLE
    settings.solana_rpc_url = UNREACHABLE
    try:
        yield
    finally:
        settings.dexscreener_base_url, settings.solana_rpc_url = before


@pytest.fixture()
def db():
    from app import models  # noqa: F401  ensure models registered
    from app.db.base import Base

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
