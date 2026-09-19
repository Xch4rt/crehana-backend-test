"""The project's first `Depends` providers, and the one place `app.state` is read.

`starlette.datastructures.State.__getattr__` is annotated to return `Any`, so
every attribute read off `app.state` is an implicit-`Any` source: the value
arrives untyped and mypy has nothing left to check downstream of it. The
resolution chosen here is the one `DatabaseResources` was built for. The
composition root stores a single typed container, and this module narrows it
back exactly once, in the private helper below; every other provider reads a
field off that container and is typed by the dataclass instead.

The rejected alternative is two bare attributes - `app.state.engine` and
`app.state.session_factory` - read directly wherever they are needed. It costs
one narrowing per read site rather than one per application, and each of those
is a separate opportunity to name the wrong type: a narrowing is an assertion
the type checker accepts without verifying, so the fewer of them there are, the
more one is worth. Phase 4 will add providers here, and none of them will have
to repeat it.
"""

from collections.abc import AsyncIterator
from typing import cast

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from taskmanager.application.ports.unit_of_work import UnitOfWork
from taskmanager.infrastructure.db.engine import DatabaseResources
from taskmanager.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork


def _resources(request: Request) -> DatabaseResources:
    """The database container the composition root put on `app.state`.

    The single narrowing of this module, deliberately private so it cannot
    acquire a second call site outside this file.
    """
    return cast(DatabaseResources, request.app.state.database)


def get_engine(request: Request) -> AsyncEngine:
    """The application's engine, for callers that need the pool itself."""
    return _resources(request).engine


def get_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    """The application's session factory, bound to the engine above."""
    return _resources(request).session_factory


async def get_uow(request: Request) -> AsyncIterator[UnitOfWork]:
    """Open one transaction for this request and hand it to the use case.

    This provider constructs the unit of work, enters its block, and does
    nothing else. Making the block's work durable is the use case's decision
    and only the use case's (ARC-08), and doing it here instead would be
    research Anti-Pattern 1: FastAPI runs the exit half of a `yield` dependency
    *after* the response has already been sent, so the write would land at a
    moment no handler can observe, no test can assert on, and no failure can
    still influence the status code the client received. A use case that
    refused the request would have its work made permanent anyway, and the
    boundary the whole phase is about would exist only on paper.

    The yield type is the port, never `SqlAlchemyUnitOfWork`. Phase 4's routers
    are meant to depend on the contract Phase 2 wrote, so that substituting the
    in-memory double in a test is a matter of overriding this provider rather
    than of changing a signature.
    """
    async with SqlAlchemyUnitOfWork(get_session_factory(request)) as unit:
        yield unit
