"""Shared test fixtures.

Tests run with authentication ENABLED so every endpoint is exercised through
the real credential path (PRD §3.3). The `client` fixture logs in with the
configured operator password and attaches the bearer token to every request.
"""

import os

os.environ.setdefault("SOFIA_DATABASE_URL", "sqlite:///./data/test_sofia.db")
os.environ.setdefault("SOFIA_AUTH_DISABLED", "false")
os.environ.setdefault("SOFIA_ADMIN_PASSWORD", "test-password")
os.environ.setdefault("SOFIA_OBSERVER_PASSWORD", "test-observer-password")
os.environ.setdefault("SOFIA_ENV", "test")

import pytest  # noqa: E402
from app.core.config import settings  # noqa: E402,F401
from app.db.base import Base  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

TEST_OPERATOR_PASSWORD = "test-password"
TEST_OBSERVER_PASSWORD = "test-observer-password"


@pytest.fixture()
def db():
    """A fresh in-memory database with all tables created.

    SQLite foreign keys are enforced so that a bogus `fills.order_id` (and any
    other dangling reference) fails loudly instead of being stored silently.
    """
    from app import models  # noqa: F401  ensure models registered
    from sqlalchemy import event

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


def _app_with(db):
    from app.db.session import get_db
    from app.main import create_app

    app = create_app()

    def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    return app


def _login(client, password, role="OPERATOR"):
    r = client.post("/api/v1/auth/login", json={"password": password, "role": role})
    assert r.status_code == 200, f"login failed: {r.text}"
    return r.json()["token"]


@pytest.fixture()
def client(db):
    """Authenticated TestClient using the fresh test session."""
    app = _app_with(db)
    with TestClient(app) as anon:
        token = _login(anon, TEST_OPERATOR_PASSWORD)
    with TestClient(app, headers={"Authorization": "Bearer " + token}) as c:
        yield c


@pytest.fixture()
def anon_client(db):
    """Unauthenticated TestClient, for auth tests."""
    with TestClient(_app_with(db)) as c:
        yield c


@pytest.fixture()
def observer_client(db):
    """TestClient authenticated with the read-only observer role."""
    app = _app_with(db)
    with TestClient(app) as anon:
        token = _login(anon, TEST_OBSERVER_PASSWORD, role="OBSERVER")
    with TestClient(app, headers={"Authorization": "Bearer " + token}) as c:
        yield c


@pytest.fixture()
def operator_token(db):
    from app.core.security import ROLE_OPERATOR, create_session

    return create_session(db, actor="operator", role=ROLE_OPERATOR)