"""The transaction boundary: one session, one explicit commit, one rollback.

This is the adapter behind `application.ports.unit_of_work.UnitOfWork`, and its
whole job is the obligation that port's docstring records as normative (Phase 2
review fix WR-06): `__aexit__` MUST roll back whatever `commit()` did not make
durable, on every exit path, and MUST return `None` so an exception leaving the
block is never swallowed. `tests/unit/application/test_ports.py` already pins
that behaviour against `FakeUnitOfWork`; `tests/integration/test_unit_of_work.py`
pins the same three claims against PostgreSQL, where a rollback that did not
happen is something a second connection can see.

The constructor takes `Callable[[], AsyncSession]` rather than
`async_sessionmaker[AsyncSession]`, and the choice is load-bearing in exactly
one direction. Production wiring is unaffected - an `async_sessionmaker`
already satisfies the callable type, because its `__call__` accepts zero
positional arguments - while the D-01 integration fixture can hand in a plain
closure that returns a session bound to the test connection. Annotating the
parameter with the concrete `async_sessionmaker` would have forced that fixture
through a `cast`, and a cast in the one place the isolation proof lives is a
cast that could hide the proof failing.
"""

from collections.abc import Callable
from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession

from taskmanager.application.ports.repositories import (
    TaskListRepository,
    TaskRepository,
    UserRepository,
)
from taskmanager.infrastructure.db.repositories.task_lists import (
    SqlAlchemyTaskListRepository,
)
from taskmanager.infrastructure.db.repositories.tasks import SqlAlchemyTaskRepository
from taskmanager.infrastructure.db.repositories.users import SqlAlchemyUserRepository


class SqlAlchemyUnitOfWork:
    """`UnitOfWork` (D-17, ARC-08) over one `AsyncSession` per block."""

    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._committed = False

    @property
    def _open_session(self) -> AsyncSession:
        """The session of the block currently open.

        Every method below runs inside `async with`, so this never raises in
        practice; the check exists because the alternative - an attribute
        created in `__aenter__` and annotated nowhere - would make `commit()`
        on an unopened unit of work an `AttributeError` about a private name
        instead of a sentence saying what the caller did wrong.
        """
        if self._session is None:
            raise RuntimeError(
                "This unit of work is not open. Every repository call and every "
                "commit happens inside `async with unit_of_work:` (ARC-08)."
            )
        return self._session

    async def __aenter__(self) -> Self:
        self._session = self._session_factory()
        self._committed = False
        # Annotated with the PORT types, never the concrete adapters. mypy
        # checks a mutable Protocol member invariantly, so `self.tasks:
        # SqlAlchemyTaskRepository` would stop this class from satisfying
        # `UnitOfWork` at all - the same finding `FakeUnitOfWork`'s docstring
        # records, arriving here for the same reason.
        self.tasks: TaskRepository = SqlAlchemyTaskRepository(self._session)
        self.task_lists: TaskListRepository = SqlAlchemyTaskListRepository(
            self._session
        )
        self.users: UserRepository = SqlAlchemyUserRepository(self._session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Roll back anything uncommitted, close the session, swallow nothing.

        Two deliberate non-behaviours, both from the port's normative
        docstring. Nothing commits here: D-17 and ARC-08 put that decision in
        the use case, so an early `return` inside the block must not become a
        silent write. And this returns `None` rather than a true value, so the
        exception that left the block keeps travelling - a unit of work that
        swallowed it would let a failed use case answer 200.

        Closing a session bound to an external `Connection` does not close that
        connection. The D-01 fixture relies on exactly that: it keeps ownership
        of the outer transaction across every block a test opens, and rolls it
        back at teardown.
        """
        session = self._open_session
        try:
            if not self._committed:
                await session.rollback()
        finally:
            await session.close()
            self._session = None
        return None

    async def commit(self) -> None:
        """Make this block's work durable. Only the use case calls this."""
        await self._open_session.commit()
        self._committed = True

    async def rollback(self) -> None:
        """Undo this block's work now, rather than at `__aexit__`."""
        await self._open_session.rollback()
        # Mirrors `FakeUnitOfWork._finished`: the transaction is finished, so
        # `__aexit__` must not roll back a second time. A second rollback on a
        # session whose transaction has already ended is not harmless - it
        # begins and ends a fresh one, which is work no caller asked for.
        self._committed = True
