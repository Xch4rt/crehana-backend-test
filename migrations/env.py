"""The migration driver: synchronous, self-sufficient, and four fixes deep.

Synchronous on purpose. The application runs SQLAlchemy's asyncio extension, but
psycopg 3 speaks both protocols behind one `postgresql+psycopg://` URL (ADR-006),
so Alembic can stay on the plain sync engine and this file needs none of the
`asyncio.run` / `run_sync` scaffolding an asyncpg project would be forced into.
One URL, one driver, two execution models.

Four deviations from the stock `generic` template, each fixing a defect that was
reproduced rather than assumed. They are numbered in place below.

It also reads `DATABASE_URL` straight from the environment instead of calling
`taskmanager.infrastructure.config.settings.get_settings()`. `Settings` also
requires `JWT_SECRET`, and a schema migration has no business demanding a token
signing secret; `alembic upgrade head` must run in a context that has a database
and nothing else.
"""

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool
from sqlalchemy.engine import Connection

from taskmanager.infrastructure.db import models  # noqa: F401 - registers tables
from taskmanager.infrastructure.db.base import Base

# `models` is imported for its side effect and for that alone: importing the
# module is what registers UserRow, TaskListRow and TaskRow on Base.metadata.
# Without it `target_metadata` below is an empty MetaData, autogenerate happily
# reports "no changes detected", and `alembic check` becomes a test that passes
# against a schema it never looked at.

config = context.config

# (1) Guarded, and never disabling the loggers that already exist.
#     logging.config.fileConfig() defaults to disable_existing_loggers=True,
#     which switches off every logger created before it runs - including
#     taskmanager's own. That was observed breaking the two caplog assertions in
#     tests/api/test_error_contract.py as soon as a session fixture ran a
#     migration first: the tests pass alone and fail in the full suite, pointing
#     nowhere near Alembic. The `configure_logging` attribute lets a pytest
#     fixture skip the call entirely; disable_existing_loggers=False makes the
#     call harmless even when it does run.
if config.config_file_name is not None and config.attributes.get(
    "configure_logging", True
):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _database_url() -> str:
    """The URL to migrate: caller-supplied first, environment second.

    (2) Read, never written back. The obvious alternative - handing the URL to
    Alembic by setting the ini's main option for it - goes through ConfigParser's
    BasicInterpolation, which raises ValueError on any `%` in the value. A single
    percent-encoded character in a password would take down every migration and
    every integration test at once. The name of that setter is kept out of this
    file so a grep for it stays a meaningful gate. Reading also keeps a live
    credential out of a Config object that Alembic is free to print.
    """
    url = config.attributes.get("sqlalchemy_url")
    if isinstance(url, str):
        return url
    return os.environ["DATABASE_URL"]


def _run_migrations(connection: Connection) -> None:
    """Configure the context against an open connection and run the revisions."""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_offline() -> None:
    """Emit SQL to stdout with no database connection (`alembic upgrade --sql`)."""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run the revisions against a live database."""
    # (3) The documented connection-sharing hook. An integration fixture opens
    #     its own Connection, begins a transaction on it and hands it over here,
    #     so `downgrade base` + `upgrade head` happen inside the one transaction
    #     the fixture controls instead of against a connection Alembic opened and
    #     closed behind its back.
    connection = config.attributes.get("connection")
    if connection is not None:
        _run_migrations(connection)
        return

    # (4) Our own engine, built from the URL above. engine_from_config() is the
    #     template's choice and is unusable here: it reads the URL back out of
    #     the ini section, which is exactly the key alembic.ini does not have.
    #     NullPool because a migration process opens one connection and exits;
    #     a pool would only keep it alive after the work is done.
    engine = create_engine(_database_url(), poolclass=pool.NullPool)
    try:
        with engine.connect() as open_connection:
            _run_migrations(open_connection)
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
