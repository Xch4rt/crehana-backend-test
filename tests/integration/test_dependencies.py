"""`get_uow` against a real transaction, including the write it must not keep.

The technique needs stating, because the obvious one is wrong. A FastAPI
dependency is normally exercised by overriding it - and an override replaces
precisely the code under test, so the interesting property would be provided by
the test rather than proved by it. This module therefore registers a throwaway
router, in the spirit of `tests/probe.py`: `include_in_schema=False`, declared
here and never anywhere near the production application, whose routes take the
real provider and report what they were handed.

`test_the_dependency_does_not_commit_on_teardown` is why the router exists, and
it is the one assertion that could not be made any other way. FastAPI runs the
exit half of a `yield` dependency *after* the response has been sent (research
Anti-Pattern 1), so a provider that made the transaction durable there would
look correct from inside every handler and would still be writing rows nobody
asked it to. The proof is a second, independent connection opened after the
response has come back, asking whether the row is there.

One thing about isolation, so no reader assumes what is not true. These tests
deliberately run *outside* the D-01 fixture transaction: the application builds
its own engine from the DSN, exactly as it does in production, and nothing here
is bound to the connection `tests/integration/conftest.py` rolls back. That is
the only way a write could escape and therefore the only way its absence means
anything. The last test asserts the table is empty afterwards, which is both the
cleanliness check and a second reading of the same claim.
"""

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated

import pytest
from fastapi import APIRouter, Depends, FastAPI, Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from taskmanager.application.ports.unit_of_work import UnitOfWork
from taskmanager.domain.entities.user import User
from taskmanager.infrastructure.config.settings import Settings
from taskmanager.main import create_app
from taskmanager.presentation.api.dependencies import get_engine, get_uow

pytestmark = pytest.mark.integration

JWT_SECRET = "b" * 32

# Fixed, never generated: "the row is absent" has to be a statement about this
# exact row, not about whatever happened not to be in the table.
USER_ID = uuid.UUID("00000000-0000-4000-8000-0000000000d1")
USER_EMAIL = "dependency@example.test"
PASSWORD_HASH = "argon2-placeholder-hash-value"
NOW = datetime(2026, 6, 1, 9, 15, 0, 500000, tzinfo=UTC)

UnitOfWorkDependency = Annotated[UnitOfWork, Depends(get_uow)]

uow_probe_router = APIRouter()


@uow_probe_router.get("/_uow/report", include_in_schema=False)
async def probe_report(unit: UnitOfWorkDependency) -> dict[str, str]:
    """Report what the provider handed over, and prove the session is live.

    The read is the difference between "three attributes exist" and "a usable
    unit of work": it goes to the migrated schema through the session the
    provider opened, so a block that was never entered fails here rather than
    passing on the strength of three non-null attributes.
    """
    already_registered = await unit.users.get(USER_ID)
    return {
        "tasks": type(unit.tasks).__name__,
        "task_lists": type(unit.task_lists).__name__,
        "users": type(unit.users).__name__,
        "lookup": "absent" if already_registered is None else "present",
    }


@uow_probe_router.get("/_uow/write-without-finishing", include_in_schema=False)
async def probe_write(unit: UnitOfWorkDependency) -> dict[str, str]:
    """Write a row and return, leaving the decision to keep it unmade.

    A handler that ends like this is the mistake the provider must survive: a
    use case that forgot the final step, or one that returned early. The row is
    flushed - the database has seen the INSERT - and the transaction is still
    open when the response is handed back.
    """
    await unit.users.add(
        User(
            id=USER_ID,
            email=USER_EMAIL,
            password_hash=PASSWORD_HASH,
            created_at=NOW,
            updated_at=NOW,
        )
    )
    return {"wrote": str(USER_ID)}


def _app_for(database_url: str) -> FastAPI:
    """The production application plus the probe router, which only tests see."""
    app = create_app(
        Settings(_env_file=None, database_url=database_url, jwt_secret=JWT_SECRET)
    )
    app.include_router(uow_probe_router)  # tests only - never production
    return app


async def _rows_in_users(database_url: str) -> int:
    """Count the `users` rows from a connection this module opened itself.

    A second connection is the whole instrument. Reading through the session
    the request used would see its own uncommitted work and answer `1` whether
    or not anything was made durable, which is the failure mode this test
    exists to detect.
    """
    engine = create_async_engine(database_url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            count = await connection.scalar(text("SELECT count(*) FROM users"))
    finally:
        await engine.dispose()
    # An aggregate arriving as anything but an integer would compare unequal to
    # zero and turn the assertions below into silent passes.
    assert isinstance(count, int)
    return count


@pytest.fixture
async def probe_client(
    migrated_database: None, database_url: str
) -> AsyncIterator[AsyncClient]:
    """A client over the real application, schema present, nothing overridden."""
    app = _app_for(database_url)
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


async def test_the_dependency_yields_a_usable_unit_of_work(
    probe_client: AsyncClient,
) -> None:
    """All three repositories arrive as the SQLAlchemy adapters, and they work."""
    response = await probe_client.get("/_uow/report")

    assert response.status_code == 200
    assert response.json() == {
        "tasks": "SqlAlchemyTaskRepository",
        "task_lists": "SqlAlchemyTaskListRepository",
        "users": "SqlAlchemyUserRepository",
        "lookup": "absent",
    }


async def test_the_dependency_does_not_commit_on_teardown(
    probe_client: AsyncClient, database_url: str
) -> None:
    """A handler that never asked for durability gets none (ARC-08).

    The request succeeds, the INSERT reached the server, and the row is gone -
    which is only possible if the provider's teardown rolled back instead of
    making the work permanent.
    """
    response = await probe_client.get("/_uow/write-without-finishing")

    assert response.status_code == 200
    assert response.json() == {"wrote": str(USER_ID)}
    assert await _rows_in_users(database_url) == 0


async def test_get_engine_returns_the_engine_built_by_create_app(
    migrated_database: None, database_url: str
) -> None:
    """The provider hands back the one engine, never a second pool.

    Identity, not equivalence. Two engines over the same DSN would both answer
    every query and would quietly double the connection pool, which is the kind
    of fault that only shows up under load - the same reason `DatabaseResources`
    is frozen.
    """
    app = _app_for(database_url)
    async with app.router.lifespan_context(app):
        request = Request({"type": "http", "app": app, "headers": []})

        assert get_engine(request) is app.state.database.engine


async def test_the_users_table_is_left_empty(
    probe_client: AsyncClient, database_url: str
) -> None:
    """Nothing this module ran leaves a row behind, and it is not tidied away.

    There is no cleanup step anywhere above. If this assertion ever fails, the
    right answer is not to add one: it would mean something in the request path
    is making writes durable on its own, which is exactly what the suite is
    here to forbid.
    """
    await probe_client.get("/_uow/report")

    assert await _rows_in_users(database_url) == 0
