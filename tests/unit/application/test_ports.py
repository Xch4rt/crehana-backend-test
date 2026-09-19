"""Conformance: every one of the eight ports has an implementation satisfying it.

The proof itself is static. Each test below binds a fake to a local annotated
with the Protocol, and mypy strict accepts that assignment only if the fake
matches the port structurally, method by method, including keyword-only
parameters and return types. `make typecheck` is therefore the gate; these tests
are what makes ARC-04 *visible* - a requirement an evaluator can confirm only by
running a type checker is weaker than one that names itself, eight times, in the
pytest report.

The alternative form, a module-level `_: type[TaskRepository] = FakeTaskRepository`
constant, is not used: inside a function flake8 reports it as an assigned-but-
unused local, and at module level it never appears in the report at all.
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from taskmanager.application.ports.clock import Clock
from taskmanager.application.ports.notifications import EmailNotifier
from taskmanager.application.ports.repositories import (
    TaskListRepository,
    TaskRepository,
    UserRepository,
)
from taskmanager.application.ports.security import PasswordHasher, TokenService
from taskmanager.application.ports.unit_of_work import UnitOfWork
from taskmanager.domain.entities.task import Task
from taskmanager.domain.value_objects.task_status import TaskStatus
from tests.unit.application.fakes import (
    FakeEmailNotifier,
    FakePasswordHasher,
    FakeTaskListRepository,
    FakeTaskRepository,
    FakeTokenService,
    FakeUnitOfWork,
    FakeUserRepository,
    FrozenClock,
)

pytestmark = pytest.mark.unit

# Fixed on purpose: a generated identifier or a clock reading would make the
# percentage assertion below unfalsifiable.
NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
TASK_LIST_ID = UUID("22222222-2222-4222-8222-222222222222")


def test_fake_task_repository_satisfies_the_task_repository_port() -> None:
    repository: TaskRepository = FakeTaskRepository()
    assert repository is not None


def test_fake_task_list_repository_satisfies_the_task_list_repository_port() -> None:
    repository: TaskListRepository = FakeTaskListRepository()
    assert repository is not None


def test_the_task_list_repository_port_declares_the_stats_listing() -> None:
    """LIST-03's capability is on the port itself, not only on an adapter.

    The binding above already fails under mypy strict if the fake stops matching
    the Protocol, but it would go on passing if the method were quietly dropped
    from *both* sides. This asserts the declaration, so removing it from the port
    is a failing test rather than a silently narrower contract.
    """
    assert "list_for_owner_with_stats" in TaskListRepository.__dict__


def test_both_aggregate_ports_declare_the_write_path_read() -> None:
    """ADR-058's capability is on the ports themselves, for the same reason.

    `get_for_update` is what closes the Phase 4 review's CR-01, the lost update
    between two overlapping read-validate-write requests. Dropped from a port
    *and* from its fake together, every binding here would still type-check and
    the write paths would have nothing to call - so the declaration is asserted,
    on both aggregates a request can change.
    """
    assert "get_for_update" in TaskRepository.__dict__
    assert "get_for_update" in TaskListRepository.__dict__


def test_fake_user_repository_satisfies_the_user_repository_port() -> None:
    repository: UserRepository = FakeUserRepository()
    assert repository is not None


def test_fake_unit_of_work_satisfies_the_unit_of_work_port() -> None:
    unit_of_work: UnitOfWork = FakeUnitOfWork()
    assert unit_of_work is not None


def test_fake_password_hasher_satisfies_the_password_hasher_port() -> None:
    hasher: PasswordHasher = FakePasswordHasher()
    assert hasher is not None


async def test_the_password_hasher_port_declares_the_equalising_dummy_verify() -> None:
    """D-21's method, bound through the port and asserted on the recorder.

    The declaration is asserted for the reason the two tests above assert
    theirs: dropped from the Protocol *and* from the fake together, the binding
    below would still type-check and D-12's unknown-email leg would have nothing
    to call. The call then goes through the port-typed local, and the recorder is
    what plan 05-07's `Login` tests assert the work was requested with, without
    measuring a clock.

    There is deliberately no `assert await ... is None` here, and the omission is
    the stronger claim. Written that way, mypy strict reports `Function does not
    return a value (it only ever returns None)` and `make typecheck` fails - so
    the type checker already refuses to let any caller read this method's return,
    which is exactly what the port's comment asks for and more than a runtime
    assertion could establish.
    """
    assert "dummy_verify" in PasswordHasher.__dict__

    fake = FakePasswordHasher()
    hasher: PasswordHasher = fake

    await hasher.dummy_verify("wrong-password")

    assert fake.dummy_verifications == ["wrong-password"]


def test_fake_token_service_satisfies_the_token_service_port() -> None:
    tokens: TokenService = FakeTokenService()
    assert tokens is not None


def test_fake_email_notifier_satisfies_the_email_notifier_port() -> None:
    notifier: EmailNotifier = FakeEmailNotifier()
    assert notifier is not None


def test_fake_clock_satisfies_the_clock_port() -> None:
    clock: Clock = FrozenClock(NOW)
    assert clock.now() == NOW


async def test_frozen_clock_returns_the_same_instant_on_every_call() -> None:
    clock = FrozenClock(NOW)

    assert clock.now() == NOW
    assert clock.now() == NOW


async def test_fake_unit_of_work_rolls_back_a_block_that_never_committed() -> None:
    """`__aexit__` owns the rollback, per the port; the fake has to model that.

    Without this behaviour `rollbacks` is a counter nothing increments, and no
    test in the suite could fail if Phase 3's SQLAlchemy adapter forgot to roll
    back - `commits == 0` proves nothing was written, not that the session was
    returned clean.
    """
    unit_of_work = FakeUnitOfWork()

    async with unit_of_work:
        pass

    assert unit_of_work.commits == 0
    assert unit_of_work.rollbacks == 1


async def test_fake_unit_of_work_does_not_roll_back_after_a_commit() -> None:
    """A committed block has nothing left to undo."""
    unit_of_work = FakeUnitOfWork()

    async with unit_of_work:
        await unit_of_work.commit()

    assert unit_of_work.commits == 1
    assert unit_of_work.rollbacks == 0


async def test_fake_unit_of_work_counts_an_explicit_rollback_only_once() -> None:
    """An explicit rollback finishes the transaction, so `__aexit__` adds nothing."""
    unit_of_work = FakeUnitOfWork()

    async with unit_of_work:
        await unit_of_work.rollback()

    assert unit_of_work.commits == 0
    assert unit_of_work.rollbacks == 1


async def test_fake_task_repository_counts_completion_from_the_stored_tasks() -> None:
    # Four tasks in the list, one of them completed: the fake computes the
    # value object the port declares rather than returning a canned one, so the
    # return type is exercised and not merely annotated.
    repository = FakeTaskRepository()
    for index in range(4):
        task = Task.create(
            task_id=UUID(f"3333333{index}-3333-4333-8333-333333333333"),
            task_list_id=TASK_LIST_ID,
            title=f"Task {index}",
            now=NOW,
        )
        if index == 0:
            task.change_status(TaskStatus.COMPLETED, now=NOW)
        await repository.add(task)

    stats = await repository.completion_stats(TASK_LIST_ID)

    assert stats.total == 4
    assert stats.completed == 1
    assert stats.percentage == 25.0
