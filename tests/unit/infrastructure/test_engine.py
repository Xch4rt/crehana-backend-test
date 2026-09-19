"""The engine builders, proven without a database and without a network.

Every test in this module builds resources from a DSN pointing at port 1 of the
loopback address, where nothing listens. That is the point: if any of these
tests could connect, the whole suite would inherit a dependency on a running
server for building the application object, and `tests/conftest.py` and
`tests/unit/test_app_factory.py` - which build the app with an equally
fictional DSN - would stop being unit tests.
"""

from dataclasses import FrozenInstanceError

import pytest
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from sqlalchemy.pool import QueuePool

from taskmanager.infrastructure.config.settings import Settings
from taskmanager.infrastructure.db.engine import (
    DatabaseResources,
    create_database_resources,
    create_engine,
    create_session_factory,
)

# Syntactically valid, deliberately unreachable: port 1 on the loopback has no
# listener, so any accidental connection attempt fails loudly instead of
# silently reaching the developer's local PostgreSQL.
UNREACHABLE_DATABASE_URL = "postgresql+psycopg://user:pass@127.0.0.1:1/nothing"
JWT_SECRET = "b" * 32

# A real field of DatabaseResources, named once so the immutability test below
# cannot quietly start asserting about an attribute that does not exist.
DECLARED_FIELD = "engine"

# A fixed identifier rather than a generated one: nothing here depends on it
# being unique, and a reader can see the value that is being hidden.
USER_ID = "11111111-1111-4111-8111-111111111111"


def a_settings() -> Settings:
    """Settings with the unreachable DSN, built without reading any `.env`.

    `_env_file=None` keeps a developer's real `.env` - or its absence - out of
    these tests entirely, the same way `tests/unit/test_app_factory.py` does it.
    """
    return Settings(
        _env_file=None,
        database_url=UNREACHABLE_DATABASE_URL,
        jwt_secret=JWT_SECRET,
    )


def test_building_the_engine_opens_no_connection() -> None:
    """The pool is lazy, and `create_app()` in unit tests depends on it.

    Nothing listens on the DSN above. If `create_async_engine` connected
    eagerly this call would raise, and with it every test that builds the
    application object without a database.
    """
    resources = create_database_resources(a_settings())

    assert isinstance(resources.engine, AsyncEngine)
    # `checkedout()` lives on QueuePool, not on the `Pool` base that
    # `AsyncEngine.pool` is annotated with, so the narrowing is what mypy
    # strict requires - and it doubles as the claim that an async engine really
    # does get a queue pool rather than a NullPool that could never hold one.
    pool = resources.engine.pool
    assert isinstance(pool, QueuePool)
    assert pool.checkedout() == 0
    assert pool.checkedin() == 0


def test_the_session_factory_does_not_expire_on_commit() -> None:
    """`expire_on_commit=False` and `autoflush=False`, read off the factory.

    Asserted through the factory's configured keyword arguments rather than by
    grepping the source: this is the value `AsyncSession` will actually be
    constructed with, so a later refactor that stops passing it fails here.
    """
    factory = create_session_factory(create_engine(a_settings()))

    assert isinstance(factory, async_sessionmaker)
    assert factory.kw["expire_on_commit"] is False
    assert factory.kw["autoflush"] is False


def test_the_engine_pre_pings() -> None:
    """`pool_pre_ping=True` reaches the pool.

    The pool records the setting under a private name - confirmed by
    introspecting a built engine, not guessed - because SQLAlchemy exposes no
    public reader for it. Asserting on the private attribute is still worth
    more than asserting nothing: the alternative is a constructor argument no
    test would notice the loss of.
    """
    engine = create_engine(a_settings())

    assert engine.pool._pre_ping is True


def test_the_engine_hides_bound_parameters() -> None:
    """WR-02: a statement error renders without the values it was bound to.

    The flag is read off the real engine - it lives on the sync engine, not on
    the dialect - and then passed to the error being rendered, so removing
    `hide_parameters=True` from the builder fails this test rather than leaving
    it asserting about a hardcoded `True`. The parameters are a register INSERT's:
    an Argon2 hash and an address, the two values the log must not carry.
    """
    hide_parameters = create_engine(a_settings()).sync_engine.hide_parameters

    assert hide_parameters is True

    hashed = "$argon2id$v=19$m=65536,t=3,p=4$c29tZXNhbHQ$0123456789abcdef"
    address = "ana@example.com"
    error = DBAPIError(
        "INSERT INTO users (id, email, full_name, password_hash) "
        "VALUES (%s, %s, %s, %s)",
        (USER_ID, address, "Ana Torres", hashed),
        # Any driver-level cause will do: what is under test is how the values
        # bound to the statement are rendered, not which failure produced it.
        Exception("server closed the connection unexpectedly"),
        hide_parameters=hide_parameters,
    )

    rendered = str(error)

    assert hashed not in rendered
    assert address not in rendered


def test_database_resources_is_frozen() -> None:
    """Neither half may be swapped after the application is built.

    Written through `setattr` with a name held in a constant, the convention
    the frozen-dataclass tests in `tests/unit/application/` established: a
    direct assignment is a mypy error that would have to be silenced with a
    `type: ignore`, and this project has none.
    """
    resources = create_database_resources(a_settings())

    with pytest.raises(FrozenInstanceError) as excinfo:
        setattr(resources, DECLARED_FIELD, create_engine(a_settings()))

    assert DECLARED_FIELD in str(excinfo.value)
    assert not hasattr(resources, "__dict__")


def test_create_database_resources_binds_the_factory_to_the_same_engine() -> None:
    """One engine, one factory over it - not two independent pools."""
    resources = create_database_resources(a_settings())

    assert isinstance(resources, DatabaseResources)
    assert resources.session_factory.kw["bind"] is resources.engine
