"""Conformance: every infrastructure adapter satisfies the port it implements.

The proof is static, exactly as in `tests/unit/application/test_ports.py`: each
test binds an adapter to a local annotated with the Protocol, and mypy strict
accepts that assignment only if the adapter matches the port structurally -
method by method, including keyword-only parameters and return types.
`make typecheck` is therefore the gate; these tests are what make it *visible*,
because a requirement an evaluator can confirm only by running a type checker
is weaker than one that names itself, four times, in the pytest report.

The `Clock` port is deliberately absent from this module. Its adapter
conformance already has a single home in
`tests/unit/infrastructure/test_clock.py::test_system_clock_satisfies_the_clock_port`
(plan 03-03), and asserting the same thing twice would mean a future change to
the port produces two identical failures in two files - which reads as two
problems.

Nothing here opens a connection. The session the three repositories borrow comes
from a factory over an engine whose DSN points at a port with no listener, which
is safe precisely because constructing an adapter - like constructing an engine -
performs no I/O. That is what keeps these unit tests rather than integration
ones; `tests/integration/` drives the same classes against a real server.
"""

from collections.abc import Callable

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from taskmanager.application.ports.repositories import (
    TaskListRepository,
    TaskRepository,
    UserRepository,
)
from taskmanager.application.ports.unit_of_work import UnitOfWork
from taskmanager.infrastructure.config.settings import Settings
from taskmanager.infrastructure.db.engine import create_database_resources
from taskmanager.infrastructure.db.repositories.task_lists import (
    SqlAlchemyTaskListRepository,
)
from taskmanager.infrastructure.db.repositories.tasks import SqlAlchemyTaskRepository
from taskmanager.infrastructure.db.repositories.users import SqlAlchemyUserRepository
from taskmanager.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork

# The same unreachable DSN `test_engine.py` uses, and for the same reason: an
# accidental connection attempt must fail loudly instead of silently reaching
# whatever PostgreSQL the developer has running.
UNREACHABLE_DATABASE_URL = "postgresql+psycopg://user:pass@127.0.0.1:1/nothing"
JWT_SECRET = "b" * 32


def a_session_factory() -> Callable[[], AsyncSession]:
    """A real session factory over an engine that will never be connected."""
    settings = Settings(
        _env_file=None,
        database_url=UNREACHABLE_DATABASE_URL,
        jwt_secret=JWT_SECRET,
    )
    return create_database_resources(settings).session_factory


def test_the_sqlalchemy_task_repository_satisfies_the_task_repository_port() -> None:
    repository: TaskRepository = SqlAlchemyTaskRepository(a_session_factory()())
    assert repository is not None


def test_the_sqlalchemy_task_list_repository_satisfies_its_port() -> None:
    repository: TaskListRepository = SqlAlchemyTaskListRepository(a_session_factory()())
    assert repository is not None


def test_the_sqlalchemy_user_repository_satisfies_the_user_repository_port() -> None:
    repository: UserRepository = SqlAlchemyUserRepository(a_session_factory()())
    assert repository is not None


def test_the_sqlalchemy_unit_of_work_satisfies_the_unit_of_work_port() -> None:
    """The one that would break first if the port annotations were tightened.

    `UnitOfWork` declares `tasks`, `task_lists` and `users` as *mutable*
    attributes, and mypy checks a mutable Protocol member invariantly. Changing
    `self.tasks: TaskRepository` to `self.tasks: SqlAlchemyTaskRepository` in
    the adapter makes this binding fail to type-check even though every method
    still matches - verified by editing the annotation, observing
    `Following member(s) of "SqlAlchemyUnitOfWork" have conflicts`, and
    reverting.
    """
    unit_of_work: UnitOfWork = SqlAlchemyUnitOfWork(a_session_factory())
    assert unit_of_work is not None


async def test_using_a_unit_of_work_outside_a_block_says_so() -> None:
    """A commit before `__aenter__` is a programming error with a sentence.

    Without the guard this is an `AttributeError` naming a private attribute,
    which tells the reader nothing about the rule they broke: the transaction
    boundary is the `async with`, and every repository call and every commit
    lives inside it.
    """
    unit_of_work = SqlAlchemyUnitOfWork(a_session_factory())

    with pytest.raises(RuntimeError) as excinfo:
        await unit_of_work.commit()

    assert "not open" in str(excinfo.value)


async def test_entering_a_unit_of_work_twice_is_refused() -> None:
    """The Phase 3 review's CR-01, pinned: this object is not re-entrant.

    A second `__aenter__` used to be silent. It replaced the open session with
    a fresh one and rebound the three repositories to it, so the first session
    was abandoned - never committed, never rolled back, never returned to the
    pool - and the outer `__aexit__` then raised about a unit of work that was
    no longer open, after the response had already been sent. That is the exact
    combination a `Depends` provider entering the block produced for every use
    case that entered it too, which is why the refusal belongs in the adapter
    and not only in the provider's docstring.

    No connection is opened here. `__aenter__` calls the session factory, which
    performs no I/O, and the block is left without a statement ever having been
    emitted - so this stays a unit test against an unreachable DSN.
    """
    unit_of_work = SqlAlchemyUnitOfWork(a_session_factory())

    async with unit_of_work:
        with pytest.raises(RuntimeError) as excinfo:
            await unit_of_work.__aenter__()

    assert "already open" in str(excinfo.value)


async def test_a_unit_of_work_can_be_reopened_after_its_block_ended() -> None:
    """Sequential blocks are not re-entry, and the guard must not confuse them.

    The distinction matters to real callers: `tests/integration/conftest.py`
    hands one `uow` fixture to a test that opens several blocks in a row, and a
    guard that latched on the first entry would fail all of them. What is
    forbidden is a *second owner while the first is still inside*, not reuse.
    """
    unit_of_work = SqlAlchemyUnitOfWork(a_session_factory())

    async with unit_of_work:
        pass
    async with unit_of_work:
        pass
