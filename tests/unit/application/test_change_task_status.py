"""Specification for the reference use case and the DTO conventions it carries.

Phase 4 copies `ChangeTaskStatus`, so what is pinned here is not one endpoint's
behaviour but a shape: constructor injection, a single `execute`, the commit
inside the transaction block, and - the part that is easiest to get wrong once
routers exist - the ADR-008 answer for a task the caller cannot see.

Every failure test asserts `uow.commits == 0` as well as the exception, so "a
refused operation writes nothing" is a property of the whole suite rather than
of whichever test happened to remember it.
"""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from taskmanager.application.dto.commands import ChangeTaskStatusCommand
from taskmanager.application.dto.results import TaskResult
from taskmanager.application.use_cases.tasks.change_task_status import ChangeTaskStatus
from taskmanager.domain.entities.task import Task
from taskmanager.domain.entities.task_list import TaskList
from taskmanager.domain.exceptions import (
    AuthorizationError,
    DomainError,
    InvalidStatusTransitionError,
    TaskListNotFoundError,
    TaskNotFoundError,
)
from taskmanager.domain.value_objects.task_priority import TaskPriority
from taskmanager.domain.value_objects.task_status import TaskStatus
from tests.unit.application.fakes import FakeUnitOfWork, FrozenClock

# Fixed on purpose. A generated identifier or a real clock reading would make
# every assertion below unfalsifiable: the test could no longer state which
# moment, or which actor, it expects.
NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
LATER = NOW + timedelta(hours=3)
ACTOR_ID = UUID("11111111-1111-4111-8111-111111111111")
OTHER_USER_ID = UUID("99999999-9999-4999-8999-999999999999")
TASK_ID = UUID("22222222-2222-4222-8222-222222222222")
TASK_LIST_ID = UUID("33333333-3333-4333-8333-333333333333")

# Attribute names live in constants so mypy does not reject the very assignment
# the immutability tests exist to observe failing at runtime.
DECLARED_COMMAND_FIELD = "new_status"
DECLARED_RESULT_FIELD = "title"
UNDECLARED_FIELD = "actor"


def _task(
    *,
    status: TaskStatus = TaskStatus.PENDING,
    assignee_id: UUID | None = None,
) -> Task:
    """Build the task under test, moved into `status` by the entity itself."""
    task = Task.create(
        task_id=TASK_ID,
        task_list_id=TASK_LIST_ID,
        title="Declare the eight ports",
        description="The reference use case has to change something real.",
        priority=TaskPriority.HIGH,
        assignee_id=assignee_id,
        now=NOW,
    )
    if status is not TaskStatus.PENDING:
        task.change_status(status, now=NOW)
    return task


def _uow(
    *,
    status: TaskStatus = TaskStatus.PENDING,
    owner_id: UUID = ACTOR_ID,
    assignee_id: UUID | None = None,
    with_task: bool = True,
    with_task_list: bool = True,
) -> FakeUnitOfWork:
    """Assemble a unit of work already holding the task and its list.

    The entities are placed in the `stored` dicts directly rather than through
    `add()`, so the `added` and `updated` records stay empty and every entry a
    test finds in them was written by the use case.
    """
    unit_of_work = FakeUnitOfWork()
    if with_task_list:
        task_list = TaskList.create(
            task_list_id=TASK_LIST_ID,
            owner_id=owner_id,
            name="Phase 2",
            now=NOW,
        )
        unit_of_work.task_list_repository.stored[task_list.id] = task_list
    if with_task:
        task = _task(status=status, assignee_id=assignee_id)
        unit_of_work.task_repository.stored[task.id] = task
    return unit_of_work


def _command(
    new_status: TaskStatus, *, actor_id: UUID = ACTOR_ID
) -> ChangeTaskStatusCommand:
    return ChangeTaskStatusCommand(
        actor_id=actor_id,
        task_id=TASK_ID,
        new_status=new_status,
    )


def test_change_task_status_command_is_immutable() -> None:
    """A command cannot be edited after presentation built it (D-16)."""
    command = _command(TaskStatus.IN_PROGRESS)

    with pytest.raises(FrozenInstanceError) as excinfo:
        setattr(command, DECLARED_COMMAND_FIELD, TaskStatus.COMPLETED)

    assert DECLARED_COMMAND_FIELD in str(excinfo.value)


def test_change_task_status_command_rejects_an_undeclared_attribute() -> None:
    """slots=True leaves no __dict__, so a typo'd field cannot be created."""
    command = _command(TaskStatus.IN_PROGRESS)

    # The exception type for a name that is not a field differs between this
    # project's two runtimes on a frozen+slots dataclass - CPython 3.13 raises
    # FrozenInstanceError, 3.14.3 raises TypeError - so the assertion is the
    # portable claim: refused, and nowhere to keep it either way. The same
    # hedge, and the same reason, as the value-object tests in plan 02-01.
    with pytest.raises((AttributeError, TypeError)):
        setattr(command, UNDECLARED_FIELD, ACTOR_ID)

    assert not hasattr(command, UNDECLARED_FIELD)
    assert not hasattr(command, "__dict__")


def test_task_result_is_immutable() -> None:
    """A result cannot be edited on its way out to the response model."""
    result = TaskResult.from_entity(_task())

    with pytest.raises(FrozenInstanceError) as excinfo:
        setattr(result, DECLARED_RESULT_FIELD, "edited")

    assert DECLARED_RESULT_FIELD in str(excinfo.value)
    assert not hasattr(result, "__dict__")


def test_task_result_from_entity_copies_every_field() -> None:
    """All eleven fields cross, including the two that are usually None."""
    task = _task(status=TaskStatus.COMPLETED, assignee_id=OTHER_USER_ID)

    result = TaskResult.from_entity(task)

    assert result.id == task.id
    assert result.task_list_id == task.task_list_id
    assert result.title == task.title
    assert result.description == task.description
    assert result.status is task.status
    assert result.priority is task.priority
    assert result.created_at == task.created_at
    assert result.updated_at == task.updated_at
    assert result.due_date == task.due_date
    assert result.completed_at == task.completed_at == NOW
    assert result.assignee_id == task.assignee_id == OTHER_USER_ID


async def test_change_task_status_moves_a_pending_task_to_in_progress() -> None:
    """The happy path: the owner advances the task and the write is committed."""
    unit_of_work = _uow()
    use_case = ChangeTaskStatus(unit_of_work, FrozenClock(LATER))

    result = await use_case.execute(_command(TaskStatus.IN_PROGRESS))

    assert result.status is TaskStatus.IN_PROGRESS
    assert result.updated_at == LATER
    assert result.completed_at is None
    assert len(unit_of_work.task_repository.updated) == 1
    assert unit_of_work.commits == 1


async def test_change_task_status_stamps_completed_at_when_entering_completed() -> None:
    """D-03 observed through the use case: the stamp is the clock's instant."""
    unit_of_work = _uow(status=TaskStatus.IN_PROGRESS)
    use_case = ChangeTaskStatus(unit_of_work, FrozenClock(LATER))

    result = await use_case.execute(_command(TaskStatus.COMPLETED))

    assert result.status is TaskStatus.COMPLETED
    assert result.completed_at == LATER
    assert unit_of_work.commits == 1


async def test_change_task_status_raises_task_not_found_for_an_unknown_task() -> None:
    """A task that does not exist is a 404 carrying only the requested id."""
    unit_of_work = _uow(with_task=False)
    use_case = ChangeTaskStatus(unit_of_work, FrozenClock(LATER))

    with pytest.raises(TaskNotFoundError) as excinfo:
        await use_case.execute(_command(TaskStatus.IN_PROGRESS))

    assert excinfo.value.details == {"task_id": str(TASK_ID)}
    assert unit_of_work.commits == 0


async def test_change_task_status_raises_task_list_not_found_for_an_orphan() -> None:
    """A task whose list is gone cannot be authorized, so it is a 404 too."""
    unit_of_work = _uow(with_task_list=False)
    use_case = ChangeTaskStatus(unit_of_work, FrozenClock(LATER))

    with pytest.raises(TaskListNotFoundError) as excinfo:
        await use_case.execute(_command(TaskStatus.IN_PROGRESS))

    assert excinfo.value.details == {"task_list_id": str(TASK_LIST_ID)}
    assert unit_of_work.commits == 0


async def test_change_task_status_hides_a_task_the_actor_cannot_see() -> None:
    """ADR-008: an invisible task is a 404 for every verb, never a 403.

    The broad `DomainError` is caught on purpose. A 403 would satisfy a
    `pytest.raises(AuthorizationError)` written the other way round just as
    happily; catching the base and then asserting *which* leaf came out is what
    makes the information-disclosure claim falsifiable (threat T-02-25).
    """
    unit_of_work = _uow(owner_id=OTHER_USER_ID)
    use_case = ChangeTaskStatus(unit_of_work, FrozenClock(LATER))

    with pytest.raises(DomainError) as excinfo:
        await use_case.execute(_command(TaskStatus.IN_PROGRESS))

    error = excinfo.value
    assert isinstance(error, TaskNotFoundError)
    assert not isinstance(error, AuthorizationError)
    assert error.details == {"task_id": str(TASK_ID)}
    assert unit_of_work.task_repository.updated == []
    assert unit_of_work.commits == 0


async def test_change_task_status_allows_the_assignee_who_does_not_own_the_list() -> (
    None
):
    """ASGN-02: the assignee may move the task even on someone else's list."""
    unit_of_work = _uow(owner_id=OTHER_USER_ID, assignee_id=ACTOR_ID)
    use_case = ChangeTaskStatus(unit_of_work, FrozenClock(LATER))

    result = await use_case.execute(_command(TaskStatus.IN_PROGRESS))

    assert result.status is TaskStatus.IN_PROGRESS
    assert result.assignee_id == ACTOR_ID
    assert unit_of_work.commits == 1


async def test_change_task_status_propagates_a_forbidden_transition() -> None:
    """The one move D-01 forbids reaches the caller untranslated, uncommitted."""
    unit_of_work = _uow(status=TaskStatus.COMPLETED)
    use_case = ChangeTaskStatus(unit_of_work, FrozenClock(LATER))

    with pytest.raises(InvalidStatusTransitionError) as excinfo:
        await use_case.execute(_command(TaskStatus.PENDING))

    assert excinfo.value.details == {"from": "completed", "to": "pending"}
    assert unit_of_work.task_repository.updated == []
    assert unit_of_work.commits == 0


async def test_change_task_status_is_idempotent_for_the_status_already_held() -> None:
    """D-02 through the use case: nothing moves, and it is not a conflict.

    The commit still happens. There is deliberately no same-state branch in the
    use case: idempotence is a `change_status` invariant (the entity returns
    before it assigns), and a second copy of that knowledge here would be the
    two-layer defect D-04 exists to prevent. The write is a no-op at the row
    level, so the transaction has nothing to make durable.
    """
    unit_of_work = _uow()
    use_case = ChangeTaskStatus(unit_of_work, FrozenClock(LATER))

    result = await use_case.execute(_command(TaskStatus.PENDING))

    assert result.status is TaskStatus.PENDING
    assert result.updated_at == NOW
    assert result.completed_at is None
    assert unit_of_work.task_repository.stored[TASK_ID].updated_at == NOW
    assert unit_of_work.commits == 1
