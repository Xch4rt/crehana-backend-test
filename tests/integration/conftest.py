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

from collections.abc import AsyncIterator, Callable, Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any, cast
from uuid import UUID

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from taskmanager.domain.entities.task import Task
from taskmanager.domain.entities.task_list import TaskList
from taskmanager.domain.entities.user import User
from taskmanager.infrastructure.config.database_url import (
    TEST_DATABASE_NAME,
    resolve_test_database_url,
)
from taskmanager.infrastructure.config.settings import Settings, get_settings
from taskmanager.infrastructure.db.mappers import (
    task_list_to_row,
    task_to_row,
    user_to_row,
)
from taskmanager.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from taskmanager.infrastructure.security.resources import SecurityResources
from taskmanager.main import create_app
from taskmanager.presentation.api.actor import get_current_actor
from taskmanager.presentation.api.dependencies import get_uow
from tests.conftest import DATABASE_URL, JWT_SECRET

# tests/integration/conftest.py -> tests/integration -> tests -> repository root.
ROOT = Path(__file__).resolve().parents[2]

# The caller `api_client` runs as, in the readable identifier series every
# integration module already uses. It lives here rather than in one of them
# because the fixture below is what makes it the caller: a second copy in a
# test module would be the one that quietly disagreed the first time this one
# moved, and the modules that seed a matching `users` row import it from here
# (the argument `test_task_lists.py` already makes for `PROBLEM_JSON`).
OWNER_ID = UUID("00000000-0000-4000-8000-000000000001")


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


@pytest.fixture
async def api_client(
    session_factory: Callable[[], AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[tuple[AsyncClient, FastAPI]]:
    """The real application, over HTTP, over the rolled-back test connection.

    This is where the two halves of the harness finally meet: `tests/conftest.py`
    has always built the application, and this module has always owned the
    transaction nothing escapes, and until now neither knew about the other. The
    join is one line - `get_uow` is overridden to hand out a unit of work over
    the connection-bound factory above - and everything D-16 asks for follows
    from it: a request writes through the production code path, a later request
    reads it back, and the `connection` fixture discards the lot at teardown.

    Three shapes a reader may expect here are deliberately absent.

    The lifespan is never entered. `get_uow` is overridden, so the engine
    `create_app` built against the fictional DSN below is never dialled and has
    no pool to dispose; entering the lifespan would only exercise a teardown for
    a resource no request in this module touches.
    `tests/integration/test_health.py` remains the one place the engine's own
    lifecycle is proven, against an application deliberately pointed at the live
    database.

    There is no truncation, no delete sweep and no reseeding between tests, for
    the reason the module docstring gives in full: the outer transaction
    *discards* whatever a test wrote instead of tidying up after it, which is
    what makes a stray commit inside a repository visible rather than invisible.

    There is no second database and no second connection. Everything a request
    does happens on the connection this fixture inherited, which is what lets a
    test read a row through the API and then inspect it through the shared
    `session` in the same breath.

    The fictional `DATABASE_URL` is still set, and that is not an oversight.
    `Settings` gives `database_url` and `jwt_secret` no default at all, so the
    model refuses to construct without both - and `create_app` builds an engine
    from whatever it is handed. The value below is syntactically valid and
    points nowhere, which is exactly right: it satisfies construction, and the
    override means nothing ever opens a socket with it.

    It yields the application beside the client rather than the client alone.
    Overriding `get_current_actor` is the only way to reach D-04's not-owned
    legs over HTTP, and a test cannot override a provider on an application it
    cannot name.

    **The actor is overridden by default, and that is a cost as well as a
    convenience (D-20).** Until plan 05-10 the seam answered with one fixed
    constant, so every test in this suite ran as the same caller without asking
    to; `get_current_actor` now decodes a real bearer token and confirms the
    row behind it, so the same ~120 tests would each need a login, a token and
    an `Authorization` header to assert anything about a task list. The
    override below supplies the caller explicitly instead, which keeps those
    tests about the behaviour they were written for.

    What it does not do is exercise authentication at all - a request through
    this client never reaches the decode, so no assertion made here says
    anything about tokens. Plan 05-13's `authenticated_client` is the fixture
    that deliberately does *not* override the seam, and it is the one the 401
    legs, the permission matrix's anonymous column and `test_statements.py`
    must use: a statement count taken through this fixture would be missing
    D-11's confirmation read, which is exactly the statement that decision
    added.
    """
    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
    monkeypatch.setenv("JWT_SECRET", JWT_SECRET)

    app = create_app(Settings(_env_file=None))
    app.dependency_overrides[get_uow] = lambda: SqlAlchemyUnitOfWork(session_factory)
    app.dependency_overrides[get_current_actor] = lambda: OWNER_ID

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, app


@pytest.fixture
async def authenticated_client(
    session_factory: Callable[[], AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[tuple[AsyncClient, FastAPI]]:
    """The same application as `api_client`, with authentication left switched on.

    Everything here is `api_client` verbatim - the monkeypatched environment,
    the fictional DSN, the factory call, the `get_uow` override over the
    connection-bound session factory, the `(client, app)` yield - with exactly
    one line removed. The removed line is the actor override, and removing it
    is the entire purpose of this fixture (D-20).

    **Why two fixtures rather than one.** `api_client` supplies the caller
    explicitly, which is what keeps the ~120 Phase 4 tests about task lists and
    tasks rather than about tokens, and what keeps `acting_as` working verbatim
    as a way of impersonating a stranger. The price is that a request through
    it never reaches the decode at all, so no assertion made through it says
    anything about authentication.

    **This is therefore the only harness through which three things may be
    measured**: the 401 legs of every authenticated route, the anonymous column
    of D-04's permission matrix, and the statement counts. A count taken
    through the other fixture would still read D-11's *previous* numbers,
    because the confirmation read that decision added happens inside the very
    dependency that override replaces - a green test asserting the old count
    would hide D-11 entirely, which is the outcome D-20 names as unacceptable.

    **Its price is paid by every test that uses it**: the caller's `users` row
    has to be seeded before the first request, because the real dependency
    confirms the row exists on *every* request. That is not a setup tax to be
    engineered away - it is precisely the property under test (T-5-15), and a
    fixture that pre-seeded a caller would make the unknown-subject case
    unreachable.

    What it does not do is mint a token for you. `bearer_header` below does
    that, and a test that wants an anonymous request simply sends no header.
    """
    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
    monkeypatch.setenv("JWT_SECRET", JWT_SECRET)

    app = create_app(Settings(_env_file=None))
    app.dependency_overrides[get_uow] = lambda: SqlAlchemyUnitOfWork(session_factory)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, app


async def bearer_header(app: FastAPI, user_id: UUID) -> str:
    """An `Authorization` value this very application will accept.

    The token is minted through the application's **own** token service, read
    off the container the composition root put on `app.state`. A second service
    built here would need the secret, the algorithm and the lifetime restated
    in a test module, and the three would agree with the application only until
    one of them was edited - at which point every test in the phase would fail
    with an indistinguishable 401 and nothing to point at. Reading the
    application's object cannot drift, and it exercises the wiring plan 05-10
    added as a side effect.

    The narrowing is the one `dependencies.py` explains in full:
    `State.__getattr__` is annotated to return `Any`, so the container has to be
    named once for the type checker to have anything left to check. It is named
    here rather than per call site, for the same reason that module gives.

    Deliberately not a fixture. A fixture would have to decide *whose* token it
    was, and the tests that matter most here mint one for a subject that was
    never seeded, or for a second user in the same test.
    """
    security = cast(SecurityResources, app.state.security)
    return f"Bearer {await security.token_service.issue_access_token(user_id)}"


@contextmanager
def acting_as(app: FastAPI, user_id: UUID) -> Iterator[None]:
    """Run the block as a different caller, and put the seam back afterwards.

    A context manager rather than a fixture returning a bare `as_actor(app, id)`
    setter, because the restoring half is the part that matters. A test that
    switched actor to prove a 404 and then went on to assert the owner's own
    view would, with a one-way setter, silently still be the stranger - and the
    second assertion would pass for the wrong reason, or fail pointing at the
    route instead of at the fixture. Exiting the block restores whatever
    override was in place before, including none.

    This is how D-04's not-owned legs are reached over HTTP without minting a
    second token: `api_client` installs `OWNER_ID` as the caller, and this
    swaps in a stranger for the length of a block. The restore therefore has
    real work to do now - exiting puts the fixture's own default back, where
    before there was nothing to put back and the `pop` branch was the only one
    a test ever took.

    **It impersonates; it does not authenticate.** That is the right trade for
    a test asking who owns a task list, and the wrong one for a test asking
    whether a credential is accepted: this replaces the very dependency such a
    test exists to exercise. Combining it with `authenticated_client` is
    therefore a contradiction rather than a convenience - a token would be
    minted, sent, and then ignored in favour of the override. Those tests mint
    a second token with `bearer_header` instead, which is what a client does.
    """
    previous = app.dependency_overrides.get(get_current_actor)
    app.dependency_overrides[get_current_actor] = lambda: user_id
    try:
        yield
    finally:
        if previous is None:
            app.dependency_overrides.pop(get_current_actor, None)
        else:
            app.dependency_overrides[get_current_actor] = previous


@pytest.fixture
def statements(connection: AsyncConnection) -> Iterator[list[str]]:
    """Every *data* statement issued on the test connection, in order (D-17).

    The filter is the fixture. Measured through the full HTTP stack, the raw
    callback stream for one `GET` is `SAVEPOINT`, `SELECT`, `ROLLBACK`: the
    session joins the outer transaction by savepoint, so its bracketing is
    reported to the listener exactly like the query between it. Counting those
    would make the recorded number mean "callbacks the engine emitted" rather
    than "statements the database was asked to run", and D-17's claim - that the
    count does not grow with the row count - would be about the wrong quantity.

    Keeping only the four data verbs is therefore not a simplification to be
    tidied away later; it is what gives the list its meaning. The listener is
    attached to the *sync* connection underneath, because `before_cursor_execute`
    is a Core event and the async connection is a facade over the one that
    actually emits it, and it is removed at teardown so a later test on a fresh
    connection never inherits a recorder nobody is reading.
    """
    seen: list[str] = []

    def record(
        conn: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        verb = statement.split(maxsplit=1)[0].upper()
        if verb in {"SELECT", "INSERT", "UPDATE", "DELETE"}:
            seen.append(verb)

    sync_connection = connection.sync_connection
    event.listen(sync_connection, "before_cursor_execute", record)
    try:
        yield seen
    finally:
        event.remove(sync_connection, "before_cursor_execute", record)


async def seed(
    session_factory: Callable[[], AsyncSession],
    *,
    users: Sequence[User] = (),
    task_lists: Sequence[TaskList] = (),
    tasks: Sequence[Task] = (),
) -> None:
    """Write starting rows for an HTTP test, and **commit** them.

    The commit is the single most surprising rule in this harness, and it is not
    optional. The sessions this factory produces join the outer transaction with
    `join_transaction_mode="create_savepoint"`, so closing one without
    committing *rolls its savepoint back*: the seeded rows vanish, and the first
    request answers 404 - or, worse, a foreign-key translation reports a
    `user_not_found` naming an actor the test plainly created. Committing
    releases the savepoint into the transaction the `connection` fixture owns,
    which still rolls the whole thing back at teardown, so isolation is exactly
    as strong as it was before. Committing here buys visibility, not durability.

    Each group is flushed before the next begins, in reference order.
    `TaskListRow` declares a `ForeignKey` to `users` but no `relationship`, so
    SQLAlchemy's unit of work has no dependency edge to sort a mixed batch by
    and will happily send the lists first, which PostgreSQL then refuses
    (04-RESEARCH Pitfall 4). One flush per level is the whole fix.

    Rows are written through the mappers rather than through the repositories: a
    test of the HTTP surface should not go red because an adapter it is not
    exercising broke - the same argument `test_repositories_task_lists.py` makes
    for its own `given_an_owner`.
    """
    session = session_factory()
    try:
        for user in users:
            session.add(user_to_row(user))
        await session.flush()
        for task_list in task_lists:
            session.add(task_list_to_row(task_list))
        await session.flush()
        for task in tasks:
            session.add(task_to_row(task))
        await session.commit()
    finally:
        await session.close()
