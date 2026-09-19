"""`get_uow` against a real transaction, in the shape a use case actually has.

The technique needs stating, because the obvious one is wrong. A FastAPI
dependency is normally exercised by overriding it - and an override replaces
precisely the code under test, so the interesting property would be provided by
the test rather than proved by it. This module therefore registers a throwaway
router, in the spirit of `tests/probe.py`: `include_in_schema=False`, declared
here and never anywhere near the production application, whose routes take the
real provider and report what they were handed.

Every handler below opens the block itself - `async with unit:` - and that is
the whole point of the file rather than a detail of it. The provider hands over
a *closed* unit of work, because D-17 and ARC-08 give the `async with` to the
use case; a probe that called `unit.users.get(...)` directly would be testing a
shape no use case will ever have, and it is exactly that gap which let the
Phase 3 review's CR-01 (a provider that entered the block too, so the use case
entered it twice) stay green through a whole phase.

Two claims are made here that could not be made any other way, and both are
read from a second, independent connection opened after the response came back.
A handler that commits leaves its row behind; a handler that returns without
committing leaves nothing, even though the INSERT reached the server. The
second half is the one a teardown-commit would break silently: FastAPI runs the
exit half of a `yield` dependency *after* the response has been sent (research
Anti-Pattern 1), so a provider that finished the transaction there would look
correct from inside every handler and would still be writing rows nobody asked
it to.

One thing about isolation, so no reader assumes what is not true. These tests
deliberately run *outside* the D-01 fixture transaction: the application builds
its own engine from the DSN, exactly as it does in production, and nothing here
is bound to the connection `tests/integration/conftest.py` rolls back. That is
the only way a write could escape and therefore the only way its absence means
anything. The last test asserts the table is empty afterwards, which is both the
cleanliness check and a second reading of the same claim.

There is therefore one deliberate exception to the suite-wide rule that no test
tidies up after itself: `test_a_committed_block_survives_the_response` makes a
write durable on purpose, so it has to remove it, from the same outside
connection, or the emptiness assertion below would be reporting its row rather
than a leak.
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
FULL_NAME = "Dependency Probe"
NOW = datetime(2026, 6, 1, 9, 15, 0, 500000, tzinfo=UTC)

UnitOfWorkDependency = Annotated[UnitOfWork, Depends(get_uow)]

uow_probe_router = APIRouter()


def a_user() -> User:
    """The one account every handler below writes, under a fixed identifier."""
    return User(
        id=USER_ID,
        email=USER_EMAIL,
        full_name=FULL_NAME,
        password_hash=PASSWORD_HASH,
        created_at=NOW,
        updated_at=NOW,
    )


@uow_probe_router.get("/_uow/report", include_in_schema=False)
async def probe_report(unit: UnitOfWorkDependency) -> dict[str, str]:
    """Report what the provider handed over, and prove the session is live.

    The read is the difference between "three attributes exist" and "a usable
    unit of work": it goes to the migrated schema through the session the block
    opened, so a provider handing back something the `async with` cannot open
    fails here rather than passing on the strength of three non-null
    attributes.
    """
    async with unit:
        already_registered = await unit.users.get(USER_ID)
        return {
            "tasks": type(unit.tasks).__name__,
            "task_lists": type(unit.task_lists).__name__,
            "users": type(unit.users).__name__,
            "lookup": "absent" if already_registered is None else "present",
        }


@uow_probe_router.get("/_uow/write-without-finishing", include_in_schema=False)
async def probe_write(unit: UnitOfWorkDependency) -> dict[str, str]:
    """Write a row and leave the block without deciding to keep it.

    A handler that ends like this is the mistake the boundary must survive: a
    use case that forgot the final step, or one that returned early. The row is
    flushed - the database has seen the INSERT - and nothing ever calls
    `commit()`, so leaving the block must undo it.
    """
    async with unit:
        await unit.users.add(a_user())
    return {"wrote": str(USER_ID)}


@uow_probe_router.get("/_uow/write-and-commit", include_in_schema=False)
async def probe_commit(unit: UnitOfWorkDependency) -> dict[str, str]:
    """The full use-case shape: open, write, commit, close - all in the handler.

    This is `ChangeTaskStatus.execute` with the domain removed, and it is what
    makes the pair of tests below a statement about the provider rather than
    about the adapter alone: the unit of work arrives through `Depends`, from
    the application's own engine, exactly as a Phase 4 router will receive it.
    """
    async with unit:
        await unit.users.add(a_user())
        await unit.commit()
    return {"committed": str(USER_ID)}


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


async def _remove_the_committed_user(database_url: str) -> None:
    """Delete the one row this module ever makes durable, from outside.

    The only cleanup in the file, and it is not housekeeping: the test that
    calls it proves a commit *survives*, so the row it leaves behind would
    otherwise be indistinguishable from the leak
    `test_the_users_table_is_left_empty` exists to detect.
    """
    engine = create_async_engine(database_url, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text("DELETE FROM users WHERE id = :id"), {"id": USER_ID}
            )
    finally:
        await engine.dispose()


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


async def test_a_block_that_never_committed_leaves_nothing_behind(
    probe_client: AsyncClient, database_url: str
) -> None:
    """A handler that never asked for durability gets none (ARC-08).

    The request succeeds, the INSERT reached the server, and the row is gone -
    which is only possible if leaving the block rolled back instead of making
    the work permanent. Nothing commits on the way out: not the block, and not
    a provider teardown, because after CR-01 the provider has no teardown at
    all.
    """
    response = await probe_client.get("/_uow/write-without-finishing")

    assert response.status_code == 200
    assert response.json() == {"wrote": str(USER_ID)}
    assert await _rows_in_users(database_url) == 0


async def test_a_committed_block_survives_the_response(
    probe_client: AsyncClient, database_url: str
) -> None:
    """The other half of ARC-08: when the handler asks, the write is kept.

    Without this, every assertion in the module would be satisfied by a
    provider that quietly made `commit()` a no-op - a unit of work that never
    writes anything passes "nothing was written" perfectly. The write is read
    back from a connection the request never touched, which is the only vantage
    point from which "durable" and "still inside an open transaction" differ.
    """
    try:
        response = await probe_client.get("/_uow/write-and-commit")

        assert response.status_code == 200
        assert response.json() == {"committed": str(USER_ID)}
        assert await _rows_in_users(database_url) == 1
    finally:
        await _remove_the_committed_user(database_url)


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
