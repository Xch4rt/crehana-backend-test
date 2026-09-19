"""Builders for the engine and the session factory - never an engine itself.

`.planning/research/STACK.md` sketches a module-level `create_async_engine(...)`
and `.planning/research/ARCHITECTURE.md` Anti-Pattern 10 forbids exactly that.
The contradiction is resolved here in favour of Anti-Pattern 10, and the reason
is concrete rather than stylistic: a module-level engine would have to read
`Settings` at import time, so `import taskmanager.infrastructure.db.engine`
would raise in every environment without `DATABASE_URL` and `JWT_SECRET` -
mypy's, import-linter's, and a plain `docker build`. That is the same argument
`main.py`'s docstring already makes for the application object, and the same
answer: this module exports *builders*, and the composition root calls them.

Nothing below opens a connection. `create_async_engine` only configures a pool,
and the pool is lazy, which is what keeps `create_app()` constructible in unit
tests against a syntactically valid but entirely fictional DSN with no database
running anywhere (`tests/conftest.py`, `tests/unit/test_app_factory.py`).
`tests/unit/infrastructure/test_engine.py` asserts that property rather than
trusting it.
"""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from taskmanager.infrastructure.config.settings import Settings


@dataclass(frozen=True, slots=True)
class DatabaseResources:
    """The engine and its session factory, as one typed value.

    This exists so `app.state` carries a single object instead of two loose
    attributes. `starlette.datastructures.State.__getattr__` returns `Any`,
    which mypy strict treats as an implicit-`Any` source, so every read of
    `app.state.engine` would need its own `cast` to stay clean. One container
    means the composition root's dependency module casts once, in one place,
    and everything downstream is typed by this class instead.

    Frozen because neither half may be swapped after the application is built:
    a session factory bound to a disposed engine is the kind of fault that only
    shows up under load.
    """

    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]


def create_engine(settings: Settings) -> AsyncEngine:
    """The async engine for `settings.database_url`, connected to nothing yet.

    Building an engine opens no connection - SQLAlchemy's pool fills on first
    use - which is the property that lets `create_app()` run in unit tests with
    a fake DSN and no server. The pre-ping option below makes the pool validate
    a connection before handing it out, so a database restart or an idle
    connection reaped by the server costs one retry instead of one failed
    request. It is named once, in the call, following the project's
    prose-not-literal convention so a grep for the setting finds the code
    rather than the commentary.

    Only `create_async_engine` is imported into this module: importing
    `sqlalchemy.create_engine` beside it would shadow this function's name and
    make every call site ambiguous to a reader.
    """
    return create_async_engine(settings.database_url, pool_pre_ping=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """The session factory the unit of work calls once per transaction."""
    return async_sessionmaker(
        engine,
        # Mandatory, not a preference. The default expires every attribute on
        # commit, so the first attribute read afterwards emits a refresh SELECT
        # - and under asyncio a lazy SELECT from outside the greenlet context
        # is a `MissingGreenlet` raised in front of a user rather than a slow
        # query (PITFALLS Pitfall 2).
        expire_on_commit=False,
        # The repositories' explicit `flush()` is the only flush point. With
        # autoflush on, a later `select()` could trigger the pending flush at
        # an unpredictable moment outside the `try` that owns D-13's
        # `IntegrityError` translation, and the refusal would surface as a 500
        # from wherever the read happened to be.
        autoflush=False,
    )


def create_database_resources(settings: Settings) -> DatabaseResources:
    """Both halves at once, for the composition root to store on `app.state`."""
    engine = create_engine(settings)
    return DatabaseResources(
        engine=engine,
        session_factory=create_session_factory(engine),
    )
