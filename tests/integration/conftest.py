"""The integration harness: a migrated schema, and a transaction nothing escapes.

Four shapes a reader may expect here are deliberately absent, and the reasons are
not stylistic.

There is no sweep that empties the tables between tests. Deleting the rows
afterwards would let a repository that opened and committed its own transaction
pass unnoticed - the residue it left behind would simply be tidied away - and
ARC-08 rests on that never happening. The outer transaction below *discards* a
stray commit instead of cleaning up after it, which is the difference between
isolation and housekeeping (D-01).

There is no database per test. A fresh one costs a connection, a `CREATE
DATABASE` and a full migration run every time; the rollback costs a single
statement and proves more, because it is the same transactional behaviour the
application itself will depend on.

There is no call to the declarative metadata's create-every-table shortcut, not
even as a convenience (ADR-007, D-02). The schema under test is the one
`migrations/versions/` produces, so a migration that is wrong fails this suite
instead of being quietly bypassed by it. The name of that shortcut is kept out of
this file so the plan's grep gate stays a real gate rather than a formality - the
same prose-not-literal convention `migrations/env.py` already follows.

There is no session-scoped *async* fixture. ADR-012 pins
`asyncio_default_fixture_loop_scope = function`, so a coroutine fixture held for
the whole session would outlive the loop it was created on and fail on the second
test with a message about a different loop. Everything session-scoped here is
therefore synchronous, which costs nothing: Alembic is synchronous, and the
reachability probe is one `SELECT 1`.

One consequence is deliberate and worth stating plainly: from this module onward
`make test` requires a reachable PostgreSQL. That is D-03, not an accident - the
suite fails once, fast, with an instruction, and never skips itself into a green
run that proved nothing.
"""

from collections.abc import AsyncIterator, Callable, Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from taskmanager.infrastructure.config.database_url import (
    TEST_DATABASE_NAME,
    resolve_test_database_url,
)
from taskmanager.infrastructure.config.settings import get_settings
from taskmanager.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork

# tests/integration/conftest.py -> tests/integration -> tests -> repository root.
ROOT = Path(__file__).resolve().parents[2]


def alembic_config(database_url: str) -> Config:
    """An Alembic `Config` aimed at `database_url`, with logging left alone.

    The URL travels in `attributes` rather than being written into the ini. The
    setter that would write it goes through ConfigParser's interpolation, which
    raises on any `%` a percent-encoded password may carry; `migrations/env.py`
    records the same reasoning, and neither file spells that setter's name so a
    grep for it stays meaningful.

    `configure_logging: False` is not decoration. Alembic's stock `env.py` calls
    `logging.config.fileConfig()`, which defaults to switching off every logger
    that already exists - including the one
    `presentation/api/errors/handlers.py` emits its single ERROR record on. The
    two `caplog` assertions in `tests/api/test_error_contract.py` then see zero
    records the moment a migration has run earlier in the same session, and fail
    pointing nowhere near Alembic. `env.py` carries the other belt
    (`disable_existing_loggers=False`); this attribute is the one that skips the
    call outright.
    """
    return Config(
        str(ROOT / "alembic.ini"),
        attributes={"sqlalchemy_url": database_url, "configure_logging": False},
    )


@pytest.fixture(scope="session")
def database_url() -> str:
    """The test DSN, resolved by the one module that owns D-04's precedence.

    `resolve_test_database_url` is the whole rule - explicit `TEST_DATABASE_URL`
    first, otherwise `DATABASE_URL` with only its database component replaced.
    Restating that precedence here would give it a second home, and the two would
    disagree the first time one of them is edited.

    The cache is cleared first because `get_settings` is `lru_cache`d for the
    process: a unit test that built its settings under `monkeypatch` may already
    have populated it with a DSN naming a database this suite must never open.
    """
    get_settings.cache_clear()
    return resolve_test_database_url(get_settings())


@pytest.fixture(scope="session")
def _require_database(database_url: str) -> None:
    """D-03: one instruction, once - never a connection traceback per test.

    Without this probe an unreachable database produces a failure for every
    integration test in the suite, each one a driver traceback that says
    `connection refused` and nothing about what to do next. The reader of a test
    run should be told to start the database, not handed the same stack trace
    forty times.

    The URL is rendered with the *masking* default on purpose: this message is
    the most likely place a live DSN reaches a public CI log (T-3-10), and
    `derive_test_database_url` is the only caller in the project that legitimately
    asks for the password back.

    The failure is raised *after* the `except` block rather than inside it. That
    is not tidiness: an exception raised while another is being handled carries
    the first one in `__context__`, and pytest prints the whole chain above the
    message - two driver tracebacks in front of the one line that says what to
    do, which is the outcome this fixture exists to prevent.
    """
    unreachable: Exception | None = None
    engine = create_engine(database_url, poolclass=NullPool)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as error:
        unreachable = error
    finally:
        engine.dispose()

    if unreachable is not None:
        pytest.fail(
            "PostgreSQL is not reachable at "
            f"{make_url(database_url).render_as_string()}.\n"
            "Start it with `make up`, or run the whole suite inside Docker with "
            "`make docker-test`.\n"
            f"Underlying error: {type(unreachable).__name__}: {unreachable}",
            pytrace=False,
        )


def _refuse_a_database_that_is_not_the_test_one(database_url: str) -> None:
    """Refuse to migrate anything but `taskmanager_test`.

    The fixture below drops every table it finds before rebuilding the schema.
    `TEST_DATABASE_NAME` is exported by `infrastructure.config.database_url`
    precisely so that intent can be checked here, before a connection is opened:
    an operator who exports `TEST_DATABASE_URL` pointing at the application
    database - or at anything shared - gets a refusal instead of an empty schema
    (T-3-18).
    """
    database = make_url(database_url).database
    if database != TEST_DATABASE_NAME:
        pytest.fail(
            f"Refusing to migrate `{database}`: this fixture drops every table "
            f"it finds, so it only ever runs against `{TEST_DATABASE_NAME}`. "
            "Check TEST_DATABASE_URL.",
            pytrace=False,
        )


@pytest.fixture(scope="session")
def migrated_database(_require_database: None, database_url: str) -> Iterator[None]:
    """D-02: the real migration builds the schema, and it goes down first.

    Down before up so a test database left behind by an earlier revision cannot
    mask a migration change. Without that step a table the current revision no
    longer creates would still be standing, and every assertion about the schema
    would be reading yesterday's answer while reporting today's.

    Alembic runs on the connection this fixture opens, handed over through
    `config.attributes`, so the downgrade and the upgrade share one transaction
    instead of each getting a connection Alembic opened and closed behind our
    back.
    """
    _refuse_a_database_that_is_not_the_test_one(database_url)

    config = alembic_config(database_url)
    engine = create_engine(database_url, poolclass=NullPool)
    try:
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.downgrade(config, "base")
            command.upgrade(config, "head")
    finally:
        engine.dispose()

    yield


@pytest.fixture
async def connection(
    migrated_database: None, database_url: str
) -> AsyncIterator[AsyncConnection]:
    """The outer transaction: nothing written inside a test reaches disk.

    The rollback in the `finally` is the whole isolation contract (D-01). It runs
    whether the test passed, failed or raised, so a test that leaves rows behind
    cannot exist - which is what lets the next test assume an empty database
    without a single cleanup statement.
    """
    engine = create_async_engine(database_url, poolclass=NullPool)
    try:
        async with engine.connect() as open_connection:
            transaction = await open_connection.begin()
            try:
                yield open_connection
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()


@pytest.fixture
def session_factory(connection: AsyncConnection) -> Callable[[], AsyncSession]:
    """Sessions bound to the test connection, joining it by SAVEPOINT.

    `join_transaction_mode` is passed explicitly and must stay that way. The
    default, `conditional_savepoint`, degrades to `rollback_only` when the given
    connection is already inside a transaction that is not itself a SAVEPOINT -
    which is exactly the shape the `connection` fixture above produces. Under
    that degradation the unit of work's `commit()` becomes a silent no-op: every
    later read in the same test still sees the data, because it is the same
    connection, so the test passes while proving nothing about committing at all.

    `expire_on_commit=False` and `autoflush=False` match the production session
    factory, so what these tests exercise is the configuration the application
    actually runs.
    """

    def factory() -> AsyncSession:
        return AsyncSession(
            bind=connection,
            expire_on_commit=False,
            autoflush=False,
            join_transaction_mode="create_savepoint",
        )

    return factory


@pytest.fixture
async def session(
    session_factory: Callable[[], AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """One session from the factory, closed at teardown.

    Closing a session bound to a connection somebody else owns does not close
    that connection - which is the property the `connection` fixture relies on to
    keep control of the outer transaction. Tests that want the transaction
    boundary itself rather than a bare session take `uow` below.
    """
    open_session = session_factory()
    try:
        yield open_session
    finally:
        await open_session.close()


@pytest.fixture
def uow(session_factory: Callable[[], AsyncSession]) -> SqlAlchemyUnitOfWork:
    """The real unit of work, over the connection-bound factory above.

    Synchronous and function-scoped: the constructor stores the factory and
    opens nothing, so there is no coroutine here for ADR-012's function-scoped
    event loop to outlive.

    The factory it receives is the D-01 closure, not an `async_sessionmaker`.
    That is the whole reason `SqlAlchemyUnitOfWork.__init__` is annotated
    `Callable[[], AsyncSession]`: production hands it a sessionmaker, which
    satisfies the same type, while this fixture hands it a plain function
    returning a session bound to the test connection - and neither end needs a
    `cast`.
    """
    return SqlAlchemyUnitOfWork(session_factory)
