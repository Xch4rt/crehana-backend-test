"""TASK-02: one task, and the three ways it has to stay invisible.

The read verb is where an enumerating caller does their work, so the refusals
matter more here than the happy path. A task that is absent, a task filed under
another list (D-14) and a task whose parent list belongs to somebody else (D-04)
must be one answer, not three - and the comparative test below produces two of
them and compares class, code, details and message, because asserting a single
error would pass just as happily against an implementation that leaks existence
through a different code.
"""

import inspect
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from taskmanager.application.dto.commands import GetTaskCommand
from taskmanager.application.use_cases.tasks.get import GetTask
from taskmanager.domain.entities.task import Task
from taskmanager.domain.entities.task_list import TaskList
from taskmanager.domain.exceptions import (
    AuthorizationError,
    DomainError,
    TaskListNotFoundError,
    TaskNotFoundError,
)
from taskmanager.domain.value_objects.task_priority import TaskPriority
from taskmanager.domain.value_objects.task_status import TaskStatus
from tests.unit.application.fakes import FakeUnitOfWork

# Fixed on purpose. A generated identifier or a real clock reading would make
# every assertion below unfalsifiable: the test could no longer state which
# moment, or which actor, it expects.
NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
LATER = NOW + timedelta(hours=3)
DEADLINE = LATER + timedelta(days=7)
ACTOR_ID = UUID("11111111-1111-4111-8111-111111111111")
OTHER_USER_ID = UUID("99999999-9999-4999-8999-999999999999")
ASSIGNEE_ID = UUID("55555555-5555-4555-8555-555555555555")
TASK_ID = UUID("22222222-2222-4222-8222-222222222222")
TASK_LIST_ID = UUID("33333333-3333-4333-8333-333333333333")
OTHER_LIST_ID = UUID("44444444-4444-4444-8444-444444444444")

TITLE = "Read one task"
DESCRIPTION = "Every field of the result has to come from the entity."


def _uow(
    *,
    owner_id: UUID = ACTOR_ID,
    with_task: bool = True,
    stored_under: UUID = TASK_LIST_ID,
) -> FakeUnitOfWork:
    """Assemble a unit of work holding both lists, and optionally the task.

    `stored_under` is D-14's lever: the task is filed under a list the request
    never names, while the addressed list exists and belongs to the actor. The
    task is finished, so `completed_at` carries a value and the result's every
    field can be asserted against something rather than against `None`.
    """
    unit_of_work = FakeUnitOfWork()
    for task_list_id in (TASK_LIST_ID, OTHER_LIST_ID):
        task_list = TaskList.create(
            task_list_id=task_list_id,
            owner_id=owner_id,
            name=f"List {task_list_id}",
            now=NOW,
        )
        unit_of_work.task_list_repository.stored[task_list.id] = task_list
    if with_task:
        task = Task.create(
            task_id=TASK_ID,
            task_list_id=stored_under,
            title=TITLE,
            description=DESCRIPTION,
            priority=TaskPriority.HIGH,
            due_date=DEADLINE,
            assignee_id=ASSIGNEE_ID,
            now=NOW,
        )
        task.change_status(TaskStatus.COMPLETED, now=LATER)
        unit_of_work.task_repository.stored[task.id] = task
    return unit_of_work


def _command(*, actor_id: UUID = ACTOR_ID) -> GetTaskCommand:
    """The single construction site every test below goes through."""
    return GetTaskCommand(
        actor_id=actor_id,
        task_list_id=TASK_LIST_ID,
        task_id=TASK_ID,
    )


async def test_get_task_returns_every_field_of_the_task() -> None:
    """The result is the whole entity, flattened, with nothing dropped."""
    unit_of_work = _uow()
    use_case = GetTask(unit_of_work)

    result = await use_case.execute(_command())

    assert result.id == TASK_ID
    assert result.task_list_id == TASK_LIST_ID
    assert result.title == TITLE
    assert result.description == DESCRIPTION
    assert result.status is TaskStatus.COMPLETED
    assert result.priority is TaskPriority.HIGH
    assert result.created_at == NOW
    assert result.updated_at == LATER
    assert result.due_date == DEADLINE
    assert result.completed_at == LATER
    assert result.assignee_id == ASSIGNEE_ID


async def test_get_task_writes_nothing_and_closes_its_transaction() -> None:
    """The read-path convention, inverted from the write path's.

    `commits == 0` alone would be equally true of a transaction nobody ever
    closed, which is why the rollback is asserted beside it.
    """
    unit_of_work = _uow()

    await GetTask(unit_of_work).execute(_command())

    assert unit_of_work.task_repository.updated == []
    assert unit_of_work.commits == 0
    assert unit_of_work.rollbacks == 1


async def test_get_task_refuses_an_absent_task() -> None:
    """A task that does not exist is a 404 carrying only the requested id."""
    unit_of_work = _uow(with_task=False)

    with pytest.raises(TaskNotFoundError) as excinfo:
        await GetTask(unit_of_work).execute(_command())

    assert excinfo.value.details == {"task_id": str(TASK_ID)}
    assert unit_of_work.commits == 0
    assert unit_of_work.rollbacks == 1


async def test_get_task_refuses_a_task_stored_under_a_different_list() -> None:
    """D-14 and TASK-02: the pair of identifiers is itself the rule.

    Both lists exist and both belong to the actor, so nothing but the mismatch
    can refuse this request - an implementation that read by identifier alone
    would hand over a task the caller addressed through the wrong parent.
    """
    unit_of_work = _uow(stored_under=OTHER_LIST_ID)

    with pytest.raises(TaskNotFoundError) as excinfo:
        await GetTask(unit_of_work).execute(_command())

    assert excinfo.value.details == {"task_id": str(TASK_ID)}
    assert str(OTHER_LIST_ID) not in str(excinfo.value.details)


async def test_the_wrong_list_read_answers_exactly_like_an_absent_task() -> None:
    """D-14 is about a pair, so both refusals are produced and compared."""
    absent_uow = _uow(with_task=False)
    with pytest.raises(DomainError) as absent_info:
        await GetTask(absent_uow).execute(_command())

    wrong_list_uow = _uow(stored_under=OTHER_LIST_ID)
    with pytest.raises(DomainError) as wrong_list_info:
        await GetTask(wrong_list_uow).execute(_command())

    absent, wrong_list = absent_info.value, wrong_list_info.value
    assert type(wrong_list) is type(absent)
    assert wrong_list.code == absent.code
    assert wrong_list.details == absent.details
    assert str(wrong_list) == str(absent)


async def test_get_task_hides_a_task_whose_list_the_actor_does_not_own() -> None:
    """D-04: the refusal is task-shaped, never list-shaped and never a 403.

    The broad `DomainError` is caught on purpose - catching the leaf directly
    would pass against an implementation that never considered the 403 question
    (T-4-29). `TaskListNotFoundError` is ruled out explicitly as well, because
    it would carry a different code *and* the parent's identifier: two things
    the caller is not entitled to learn from a task they may not see.
    """
    unit_of_work = _uow(owner_id=OTHER_USER_ID)

    with pytest.raises(DomainError) as excinfo:
        await GetTask(unit_of_work).execute(_command())

    error = excinfo.value
    assert isinstance(error, TaskNotFoundError)
    assert not isinstance(error, TaskListNotFoundError)
    assert not isinstance(error, AuthorizationError)
    assert error.details == {"task_id": str(TASK_ID)}
    assert unit_of_work.commits == 0
    assert unit_of_work.rollbacks == 1


def test_get_task_asks_for_no_clock() -> None:
    """ARC-04 read back off the constructor: this operation stamps nothing.

    A `Clock` accepted and never read would be a dependency this use case does
    not have, and the whole point of one class per operation is that its
    constructor states exactly what the operation touches.
    """
    parameters = list(inspect.signature(GetTask.__init__).parameters)

    assert parameters[1:] == ["uow"]
