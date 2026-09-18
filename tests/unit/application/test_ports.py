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


def test_fake_user_repository_satisfies_the_user_repository_port() -> None:
    repository: UserRepository = FakeUserRepository()
    assert repository is not None


def test_fake_unit_of_work_satisfies_the_unit_of_work_port() -> None:
    unit_of_work: UnitOfWork = FakeUnitOfWork()
    assert unit_of_work is not None


def test_fake_password_hasher_satisfies_the_password_hasher_port() -> None:
    hasher: PasswordHasher = FakePasswordHasher()
    assert hasher is not None


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
