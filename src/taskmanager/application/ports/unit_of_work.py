"""The transactional boundary port: three repositories bound to one unit of work.

The rejected alternative is injecting `TaskRepository`, `TaskListRepository` and
`UserRepository` into a use case as three separate constructor arguments and
letting a FastAPI `yield` dependency commit on teardown. That works, and it puts
the transaction boundary in the web framework - so the same use case called from
a CLI, a worker or a test would silently lose its atomicity, and nothing in the
application layer would say where the commit happens. D-17 and ARC-08 put the
boundary in the use case instead: the three repositories arrive already bound to
one transaction through this single async context manager, and the use case
calls `commit()` itself, explicitly, after the last write succeeds.

Nothing here commits on exit. Leaving the block without a `commit()` must leave
the transaction unfinished so the adapter can roll it back; an implementation
that commits in `__aexit__` would turn every early `return` into a silent write.

`__aenter__` returns `typing.Self` rather than `UnitOfWork`, so an adapter that
adds its own affordances keeps them visible to the caller inside the block.

This is also the port that settles `runtime_checkable` for the whole package.
Decorating it would make `issubclass()` raise `TypeError: Protocols with
non-method members don't support issubclass()`, because `tasks`, `task_lists`
and `users` are attributes rather than methods - and even where the check does
run it only proves an attribute exists, never that its signature matches.
Conformance here is proven by mypy strict plus the named tests in
`tests/unit/application/test_ports.py`, which is a stronger claim than any
runtime check could make.
"""

from types import TracebackType
from typing import Protocol, Self

from taskmanager.application.ports.repositories import (
    TaskListRepository,
    TaskRepository,
    UserRepository,
)


class UnitOfWork(Protocol):
    """One transaction, the three repositories inside it, and its two verbs."""

    task_lists: TaskListRepository
    tasks: TaskRepository
    users: UserRepository

    async def __aenter__(self) -> Self: ...

    # Returning `None` is part of the contract: an implementation that returned
    # a true value here would swallow the exception that left the block, and a
    # failed use case would answer 200.
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...
