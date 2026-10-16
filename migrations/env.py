"""Alembic environment for Next Gent Sofia Trade v1.

The database URL always comes from the application settings
(`SOFIA_DATABASE_URL`) so migrations and the running app can never drift apart.
`alembic.ini` intentionally leaves `sqlalchemy.url` empty.

Offline mode (--sql) emits SQL for review; online mode runs against a live
connection.
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

ROOT = Path(__file__).resolve().parents[1]
for candidate in (ROOT / "services" / "api", ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

# Importing the package registers every model on Base.metadata, which is what
# autogenerate compares the database against.
import app.models  # noqa: E402,F401
from app.core.config import settings  # noqa: E402
from app.db.base import Base  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    """Prefer an explicit override, then the app settings, then the env var."""
    return (
        os.environ.get("SOFIA_DATABASE_URL")
        or settings.database_url
        or config.get_main_option("sqlalchemy.url")
    )


def include_object(obj, name, type_, reflected, compare_to):
    """Keep Alembic focused on tables this app owns."""
    if type_ == "table" and name in {"alembic_version", "spatial_ref_sys"}:
        return False
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        include_object=include_object,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            include_object=include_object,
            # SQLite cannot ALTER most things in place; batch mode rebuilds tables.
            render_as_batch=connection.dialect.name == "sqlite",
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()