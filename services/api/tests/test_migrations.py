"""Alembic migration tests (PRD §11, §18.G).

These run the real migration chain against a throwaway SQLite file and assert
the resulting schema matches the SQLAlchemy metadata. Without this, a migration
can be generated successfully and still fail at apply time (a named constraint
is required for SQLite batch mode), or silently skip columns.
"""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
ALEMBIC_INI = ROOT / "alembic.ini"
MIGRATIONS = ROOT / "migrations"


def _run(args, db_path, expect_ok=True):
    env = {**os.environ, "SOFIA_DATABASE_URL": f"sqlite:///{db_path}"}
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    if expect_ok and proc.returncode != 0:
        raise AssertionError(
            "alembic {} failed ({}):\n{}\n{}".format(
                " ".join(args), proc.returncode, proc.stdout[-3000:], proc.stderr[-3000:]
            )
        )
    return proc


def _tables(db_path):
    con = sqlite3.connect(db_path)
    try:
        return {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        con.close()


def _columns(db_path, table):
    con = sqlite3.connect(db_path)
    try:
        return {r[1] for r in con.execute(f'PRAGMA table_info("{table}")')}
    finally:
        con.close()


@pytest.fixture()
def migrated_db(tmp_path):
    db_path = tmp_path / "migrations_test.db"
    _run(["upgrade", "head"], db_path)
    yield str(db_path)
    if os.path.exists(db_path):
        os.remove(db_path)


# ----------------------------- Configuration -----------------------------


def test_alembic_ini_points_at_migrations_dir():
    assert ALEMBIC_INI.exists(), "alembic.ini missing"
    assert MIGRATIONS.exists()
    assert (MIGRATIONS / "env.py").exists()
    assert (MIGRATIONS / "script.py.mako").exists()


def test_alembic_ini_has_no_hardcoded_url():
    """The URL must come from settings so app and migrations cannot drift."""
    text = ALEMBIC_INI.read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.strip().startswith("sqlalchemy.url"):
            assert not line.split("=", 1)[1].strip(), "alembic.ini must not hardcode a URL"
            break
    else:
        raise AssertionError("sqlalchemy.url key missing from alembic.ini")


def test_env_py_reads_the_app_url():
    text = (MIGRATIONS / "env.py").read_text(encoding="utf-8")
    assert "SOFIA_DATABASE_URL" in text
    assert "settings.database_url" in text


# ----------------------------- Applying migrations -----------------------------


def test_upgrade_head_creates_every_table(migrated_db):
    from app import models  # noqa: F401
    from app.db.base import Base

    actual = _tables(migrated_db) - {"alembic_version", "sqlite_sequence"}
    expected = set(Base.metadata.tables)
    assert expected - actual == set(), f"tables missing after upgrade head: {sorted(expected - actual)}"


def test_upgrade_head_creates_every_column(migrated_db):
    from app import models  # noqa: F401
    from app.db.base import Base

    missing = []
    for table, metadata_table in Base.metadata.tables.items():
        if table not in _tables(migrated_db):
            continue
        cols = _columns(migrated_db, table)
        for column in metadata_table.columns:
            if column.name not in cols:
                missing.append(f"{table}.{column.name}")
    assert missing == [], f"columns missing after upgrade head: {missing}"


def test_head_is_stamped(migrated_db):
    con = sqlite3.connect(migrated_db)
    try:
        version = con.execute("SELECT version_num FROM alembic_version").fetchone()[0]
    finally:
        con.close()
    proc = _run(["heads"], migrated_db)
    assert version in proc.stdout


def test_downgrade_to_base_drops_all_tables(tmp_path):
    db_path = str(tmp_path / "downgrade_test.db")
    _run(["upgrade", "head"], db_path)
    _run(["downgrade", "base"], db_path)
    remaining = _tables(db_path) - {"alembic_version", "sqlite_sequence"}
    assert remaining == set(), f"tables left after downgrade: {sorted(remaining)}"


def test_upgrade_downgrade_upgrade_is_stable(tmp_path):
    db_path = str(tmp_path / "roundtrip_test.db")
    _run(["upgrade", "head"], db_path)
    after_first = _columns(db_path, "positions")
    _run(["downgrade", "base"], db_path)
    _run(["upgrade", "head"], db_path)
    assert _columns(db_path, "positions") == after_first


# ----------------------------- The specific fix -----------------------------


def test_exit_order_intent_columns_exist(migrated_db):
    """Exit fills must be traceable to a real order intent (FR-TB-008)."""
    cols = _columns(migrated_db, "positions")
    assert {"open_order_intent_id", "open_signal_id", "exit_order_intent_id"} <= cols


def test_fill_side_column_exists(migrated_db):
    assert "side" in _columns(migrated_db, "fills")


# ----------------------------- Dialect coverage -----------------------------


def test_postgres_ddl_generates_without_errors():
    """Production target. Offline mode compiles the whole chain to SQL."""
    env = {
        **os.environ,
        "SOFIA_DATABASE_URL": "postgresql+psycopg://sofia:sofia@localhost:5432/sofia_trade",
    }
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head", "--sql"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr[-3000:]
    assert "CREATE TABLE positions" in proc.stdout
    assert "fk_positions_exit_order_intent_id" in proc.stdout


# ----------------------------- Runtime schema guard -----------------------------


def test_schema_is_current_reports_true_after_upgrade(migrated_db):
    """`init_db` refuses to serve when this is False outside development."""
    import app.db.session as session_module

    original = session_module.engine
    from sqlalchemy import create_engine

    session_module.engine = create_engine(f"sqlite:///{migrated_db}")
    try:
        assert session_module.schema_is_current() is True
    finally:
        session_module.engine.dispose()
        session_module.engine = original


def test_schema_is_current_reports_false_for_fresh_db(tmp_path):
    import app.db.session as session_module

    original = session_module.engine
    from sqlalchemy import create_engine

    fresh = create_engine("sqlite:///{}".format(tmp_path / "fresh.db"))
    session_module.engine = fresh
    try:
        assert session_module.schema_is_current() is False
    finally:
        fresh.dispose()
        session_module.engine = original