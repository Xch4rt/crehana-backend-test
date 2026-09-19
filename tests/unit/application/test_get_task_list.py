"""LIST-02, and the D-04 two-actor proof for the read verb.

The success path asserts `commits == 0` and `rollbacks == 1`, which is the
inverse of the convention every write-path module here follows. That inversion
is the assertion: a read that committed would be indistinguishable from a
correct one by its return value alone, and `rollbacks == 1` is what proves the
transaction was actually closed rather than merely left alone.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from taskmanager.application.dto.commands import GetTaskListCommand
from taskmanager.application.use_cases.task_lists.get import GetTaskList
from taskmanager.domain.entities.task import Task
from taskmanager.domain.entities.task_list import TaskList
from taskmanager.domain.exceptions import (
    AuthorizationError,
    DomainError,
    TaskListNotFoundError,
)
from taskmanager.domain.value_objects.task_status import TaskStatus
from tests.unit.application.fakes import FakeUnitOfWork

pytestmark = pytest.mark.unit

# Fixed on purpose. A generated identifier or a real clock reading would make
# every assertion below unfalsifiable: the test could no longer state which
# moment, or which actor, it expects.
NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
LATER = NOW + timedelta(hours=3)
ACTOR_ID = UUID("11111111-1111-4111-8111-111111111111")
OTHER_USER_ID = UUID("99999999-9999-4999-8999-999999999999")
LIST_ID = UUID("33333333-3333-4333-8333-333333333333")
TASK_IDS = (
    UUID("22222222-2222-4222-8222-222222222221"),
    UUID("22222222-2222-4222-8222-222222222222"),
    UUID("22222222-2222-4222-8222-222222222223"),
)

NAME = "Phase 4"
DESCRIPTION = "Everything the list endpoints owe."


def _uow(
    *,
    owner_id: UUID = ACTOR_ID,
    with_list: bool = True,
    tasks: int = 0,
    completed: int = 0,
) -> FakeUnitOfWork:
    """Assemble a unit of work already holding the list and `tasks` tasks.

    Entities go into the `stored` dicts directly rather than through `add()`,
    so the mutation records stay empty and anything a test finds in them was
    written by the use case.
    """
    unit_of_work = FakeUnitOfWork()
    if with_list:
        task_list = TaskList.create(
            task_list_id=LIST_ID,
            owner_id=owner_id,
            name=NAME,
            description=DESCRIPTION,
            now=NOW,
        )
        unit_of_work.task_list_repository.stored[task_list.id] = task_list
    for index in range(tasks):
        task = Task.create(
            task_id=TASK_IDS[index],
            task_list_id=LIST_ID,
            title=f"Task {index}",
            now=NOW,
        )
        if index < completed:
            task.change_status(TaskStatus.COMPLETED, now=LATER)
        unit_of_work.task_repository.stored[task.id] = task
    return unit_of_work


def _command(*, actor_id: UUID = ACTOR_ID) -> GetTaskListCommand:
    """The single construction site every test below goes through."""
    return GetTaskListCommand(actor_id=actor_id, task_list_id=LIST_ID)


async def test_get_task_list_returns_the_list_without_committing() -> None:
    """LIST-02: the owner's list, its fields, and a transaction that wrote nothing.

    The commit assertion is inverted from the write-path convention on purpose;
    see this module's docstring.
    """
    unit_of_work = _uow()
    use_case = GetTaskList(unit_of_work)

    result = await use_case.execute(_command())

    assert result.id == LIST_ID
    assert result.owner_id == ACTOR_ID
    assert result.name == NAME
    assert result.description == DESCRIPTION
    assert result.created_at == NOW
    assert result.updated_at == NOW
    assert result.total_tasks == 0
    assert result.completed_tasks == 0
    assert result.completion_percentage == 0.0
    assert unit_of_work.commits == 0
    assert unit_of_work.rollbacks == 1


async def test_get_task_list_reports_the_completion_of_the_whole_list() -> None:
    """Two of three done is 66.67, rounded by the value object (ADR-009)."""
    unit_of_work = _uow(tasks=3, completed=2)
    use_case = GetTaskList(unit_of_work)

    result = await use_case.execute(_command())

    assert result.total_tasks == 3
    assert result.completed_tasks == 2
    assert result.completion_percentage == 66.67
    assert unit_of_work.commits == 0


async def test_get_task_list_refuses_an_absent_list() -> None:
    """A list that does not exist is a 404 carrying only the requested id."""
    unit_of_work = _uow(with_list=False)
    use_case = GetTaskList(unit_of_work)

    with pytest.raises(TaskListNotFoundError) as excinfo:
        await use_case.execute(_command())

    assert excinfo.value.details == {"task_list_id": str(LIST_ID)}
    assert unit_of_work.commits == 0
    assert unit_of_work.rollbacks == 1


async def test_get_task_list_hides_a_list_the_actor_does_not_own() -> None:
    """D-04 and ADR-008: an invisible list is a 404, never a 403.

    The broad `DomainError` is caught on purpose. A 403 would satisfy a
    `pytest.raises(AuthorizationError)` written the other way round just as
    happily; catching the base and then asserting *which* leaf came out is what
    makes the information-disclosure claim falsifiable (T-4-22).
    """
    unit_of_work = _uow(owner_id=OTHER_USER_ID)
    use_case = GetTaskList(unit_of_work)

    with pytest.raises(DomainError) as excinfo:
        await use_case.execute(_command())

    error = excinfo.value
    assert isinstance(error, TaskListNotFoundError)
    assert not isinstance(error, AuthorizationError)
    assert error.details == {"task_list_id": str(LIST_ID)}
    assert str(OTHER_USER_ID) not in str(error.details)
    assert unit_of_work.commits == 0
    assert unit_of_work.rollbacks == 1


async def test_the_foreign_list_answer_is_identical_to_the_absent_one() -> None:
    """D-04's second half: the two refusals cannot be told apart.

    Both are produced here and compared - class, `code` and `details` - because
    "answers exactly like an absent one" is a statement about a *pair* of error
    bodies. A foreign-list refusal with a code of its own would satisfy the
    sibling test above and still tell a stranger the list exists.
    """
    absent_uow = _uow(with_list=False)
    with pytest.raises(DomainError) as absent_info:
        await GetTaskList(absent_uow).execute(_command())

    foreign_uow = _uow(owner_id=OTHER_USER_ID)
    with pytest.raises(DomainError) as foreign_info:
        await GetTaskList(foreign_uow).execute(_command())

    absent, foreign = absent_info.value, foreign_info.value
    assert type(foreign) is type(absent)
    assert foreign.code == absent.code
    assert foreign.details == absent.details
    assert str(foreign) == str(absent)
