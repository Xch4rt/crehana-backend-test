"""The project's `Depends` providers, and the only place `app.state` is read.

`starlette.datastructures.State.__getattr__` is annotated to return `Any`, so
every attribute read off `app.state` is an implicit-`Any` source: the value
arrives untyped and mypy has nothing left to check downstream of it. The
resolution chosen here is the one `DatabaseResources` was built for. The
composition root stores typed containers, and this module narrows each of them
back exactly once, in a private helper; every provider reads a field off a
container and is typed by the dataclass instead.

The rejected alternative is bare attributes - `app.state.engine`,
`app.state.session_factory`, `app.state.token_service` - read directly wherever
they are needed. It costs one narrowing per read site rather than one per
container, and each of those is a separate opportunity to name the wrong type:
a narrowing is an assertion the type checker accepts without verifying, so the
fewer of them there are, the more one is worth.

**There are two narrowings now, and the earlier wording here claimed one.**
That is not the property weakening; it is the property counted per container
rather than per module, which is what it was always defending. The two are not
fused into a single container because they have nothing in common: the database
half is built from one URL and owns a connection pool that must be disposed,
while the security half is built from three JWT settings and owns two stateless
adapters that own nothing. Merging them would mean every unit test that wants a
token service also builds an engine, and every test that wants an engine also
reads a signing secret - so a change to either half would break tests of the
other. Two narrowings, both private, both in this file, is the shape being
kept.

One divergence between the providers below is deliberate and looks
inconsistent, so it is stated rather than left to be inferred (D-27, RC-3).
`SystemClock` and `LoggingEmailNotifier` are rebuilt for every caller: they
hold no state, open nothing and cost a single allocation each, so a shared
instance would buy nothing and add a place a test could forget to override.
`PwdlibPasswordHasher` is the opposite - it caches a throwaway Argon2 hash that
costs a measured 37 ms to produce, so a fresh instance per request would pay
that on every login, which is precisely the cost `dummy_verify` exists to
control. It therefore lives in the container and is handed out, not built here.
"""

from typing import Annotated, cast

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from taskmanager.application.ports.clock import Clock
from taskmanager.application.ports.notifications import EmailNotifier
from taskmanager.application.ports.security import PasswordHasher, TokenService
from taskmanager.application.ports.unit_of_work import UnitOfWork
from taskmanager.infrastructure.clock import SystemClock
from taskmanager.infrastructure.db.engine import DatabaseResources
from taskmanager.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from taskmanager.infrastructure.notifications.logging import LoggingEmailNotifier
from taskmanager.infrastructure.security.resources import SecurityResources


def _resources(request: Request) -> DatabaseResources:
    """The database container the composition root put on `app.state`.

    One of this module's two narrowings, deliberately private so it cannot
    acquire a call site outside this file.
    """
    return cast(DatabaseResources, request.app.state.database)


def _security(request: Request) -> SecurityResources:
    """The security container the composition root put on `app.state`.

    The second narrowing, private for the same reason as the first and living
    beside it so the count is visible in one screen rather than discovered.
    """
    return cast(SecurityResources, request.app.state.security)


def get_engine(request: Request) -> AsyncEngine:
    """The application's engine, for callers that need the pool itself."""
    return _resources(request).engine


def get_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    """The application's session factory, bound to the engine above."""
    return _resources(request).session_factory


def get_uow(request: Request) -> UnitOfWork:
    """Build this request's unit of work and hand it over *closed*.

    The provider constructs, and does nothing else. The `async with` belongs to
    the use case (D-17, ARC-08), which is what the port's docstring says and
    what `ChangeTaskStatus.execute` does, so entering the block here would give
    the same object two owners: the use case's `__aenter__` would open a second
    session over the first, the first would never be closed, and the teardown
    running after the response would find a unit of work the use case had
    already finished (review fix CR-01). `SqlAlchemyUnitOfWork.__aenter__` now
    refuses that second entry outright, so the shape cannot come back quietly.

    This is a plain `def` rather than a `yield` dependency for the same reason
    it must not commit. FastAPI runs the exit half of a `yield` dependency
    *after* the response has already been sent (research Anti-Pattern 1), so
    anything a teardown did - a commit, a rollback, a close - would land at a
    moment no handler can observe, no test can assert on, and no failure can
    still influence the status code the client received. There is nothing left
    to do there anyway: the use case's block rolls back whatever it did not
    commit and closes the session on every exit path, before the handler
    returns.

    The return type is the port, never `SqlAlchemyUnitOfWork`. Phase 4's routers
    are meant to depend on the contract Phase 2 wrote, so that substituting the
    in-memory double in a test is a matter of overriding this provider rather
    than of changing a signature.
    """
    return SqlAlchemyUnitOfWork(get_session_factory(request))


def get_clock() -> Clock:
    """The system clock, built fresh for whoever asks (D-14).

    It takes no `Request` because it reads nothing off the application, and it
    is not stored on `app.state` for the same reason: `SystemClock` holds no
    state, opens nothing and costs a single object allocation, so the narrowing
    `_resources` exists to avoid would buy nothing here. A shared instance would
    only add a second place a test could forget to override.

    The annotation is the **port**, never the concrete adapter, exactly as
    `get_uow`'s is. A use case that wants a frozen instant in a test gets it by
    overriding this provider, which is a line in a fixture rather than a change
    to a signature.
    """
    return SystemClock()


def get_password_hasher(request: Request) -> PasswordHasher:
    """The one hasher this application built, never a fresh one.

    Handed out rather than constructed, which is the divergence from
    `get_clock` the module docstring argues: the cached dummy hash behind
    `dummy_verify` is bought once per application here, and once per request in
    the rejected shape.

    The annotation is the port. A test that wants a hasher which answers
    instantly overrides this provider, and no signature anywhere moves.
    """
    return _security(request).password_hasher


def get_token_service(request: Request) -> TokenService:
    """The one token service this application built, never a fresh one.

    It is in the container for a second reason beyond the hasher's: it carries
    the signing secret, the algorithm and the expiry, all read from `Settings`
    exactly once, by the composition root. A provider that rebuilt it per
    request would have to read configuration per request - which is the shape
    this module has none of.
    """
    return _security(request).token_service


def get_email_notifier() -> EmailNotifier:
    """The invitation notifier, built fresh for whoever asks.

    The `get_clock` shape rather than the container one, and for the same
    reason: `LoggingEmailNotifier` holds nothing at all beyond a module-level
    logger it looks up by name, so there is no cached work for a shared
    instance to preserve. It takes no `Request` because it reads nothing off
    the application.
    """
    return LoggingEmailNotifier()


# The aliases every router shares, declared once here rather than re-spelled
# per router. They are annotations and not argument defaults, for the B008
# reason `health.py` L47-L54 sets out in full; that argument is not repeated
# here.
UnitOfWorkDependency = Annotated[UnitOfWork, Depends(get_uow)]
ClockDependency = Annotated[Clock, Depends(get_clock)]
PasswordHasherDependency = Annotated[PasswordHasher, Depends(get_password_hasher)]
TokenServiceDependency = Annotated[TokenService, Depends(get_token_service)]
EmailNotifierDependency = Annotated[EmailNotifier, Depends(get_email_notifier)]
