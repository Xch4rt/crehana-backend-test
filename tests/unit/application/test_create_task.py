"""TASK-01 and TASK-08: the write path, and the three refusals it must carry.

The three validation tests here look like duplicates of the entity's own, and
they are not. `tests/unit/domain/test_task.py` proves that `Task.create` refuses
a blank title, an over-long one and a deadline behind the creation moment. What
this module proves is that the refusal *reaches the caller* - that the use case
neither swallows it, nor re-wraps it, nor commits the transaction it was raised
inside. An implementation that caught the error and returned a half-built result
would leave the entity tests green.

The clock is stopped at `LATER` while every pre-existing entity in the fixtures
is stamped `NOW`. The two instants differ on purpose: a single-instant test
cannot tell a use case that reads the clock from one that copied a timestamp off
something it found in the repository.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from taskmanager.application.dto.commands import CreateTaskCommand
from taskmanager.application.use_cases.tasks.create import CreateTask
from taskmanager.domain.entities.task import Task
from taskmanager.domain.entities.task_list import TaskList
from taskmanager.domain.exceptions import (
    AuthorizationError,
    DomainError,
    TaskListNotFoundError,
    ValidationError,
)
from taskmanager.domain.value_objects.task_priority import TaskPriority
from taskmanager.domain.value_objects.task_status import TaskStatus
from tests.unit.application.fakes import FakeUnitOfWork, FrozenClock

# Fixed on purpose. A generated identifier or a real clock reading would make
# every assertion below unfalsifiable: the test could no longer state which
# moment, or which actor, it expects.
NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
LATER = NOW + timedelta(hours=3)
DEADLINE = LATER + timedelta(days=7)
ACTOR_ID = UUID("11111111-1111-4111-8111-111111111111")
OTHER_USER_ID = UUID("99999999-9999-4999-8999-999999999999")
TASK_LIST_ID = UUID("33333333-3333-4333-8333-333333333333")

TITLE = "Write the five task use cases"
DESCRIPTION = "TASK-01 through TASK-08, minus the status endpoint."
# One character past the entity's cap, read off the ClassVar rather than typed
# out: the limit has one home, and a literal here would be a second copy of it.
OVER_LONG_TITLE = "x" * (Task.TITLE_MAX_LENGTH + 1)


def _uow(*, owner_id: UUID = ACTOR_ID, with_list: bool = True) -> FakeUnitOfWork:
    """Assemble a unit of work optionally holding the parent list.

    The list goes into `stored` directly rather than through `add()`, so the
    `added` record stays empty and every entry a test finds in it was written by
    the use case.
    """
    unit_of_work = FakeUnitOfWork()
    if with_list:
        task_list = TaskList.create(
            task_list_id=TASK_LIST_ID,
            owner_id=owner_id,
            name="Phase 4",
            now=NOW,
        )
        unit_of_work.task_list_repository.stored[task_list.id] = task_list
    return unit_of_work


def _command(
    *,
    title: str = TITLE,
    description: str | None = DESCRIPTION,
    priority: TaskPriority = TaskPriority.HIGH,
    due_date: datetime | None = None,
    actor_id: UUID = ACTOR_ID,
) -> CreateTaskCommand:
    """The single construction site every test below goes through."""
    return CreateTaskCommand(
        actor_id=actor_id,
        task_list_id=TASK_LIST_ID,
        title=title,
        description=description,
        priority=priority,
        due_date=due_date,
    )


async def test_create_task_stores_a_pending_task_and_commits() -> None:
    """The happy path, asserted on the answer and on the transaction alike."""
    unit_of_work = _uow()
    use_case = CreateTask(unit_of_work, FrozenClock(LATER))

    result = await use_case.execute(_command(due_date=DEADLINE))

    assert result.title == TITLE
    assert result.description == DESCRIPTION
    assert result.task_list_id == TASK_LIST_ID
    assert result.status is TaskStatus.PENDING
    assert result.priority is TaskPriority.HIGH
    assert result.due_date == DEADLINE
    assert result.completed_at is None
    assert result.assignee_id is None
    # Both stamps come from the stopped clock, never from the parent list, which
    # this fixture deliberately created three hours earlier.
    assert result.created_at == LATER
    assert result.updated_at == LATER
    assert len(unit_of_work.task_repository.added) == 1
    assert unit_of_work.task_repository.stored[result.id].title == TITLE
    assert unit_of_work.commits == 1
    assert unit_of_work.rollbacks == 0


async def test_the_commands_default_priority_is_the_entitys_medium() -> None:
    """TASK-01's `medium`, bound to the one copy that states it.

    The command's `priority` is required and has no default, on purpose: the
    rule lives in `Task.DEFAULT_PRIORITY`, which the request schema reads for
    its own field default. So what this test pins is that the ClassVar really
    is `medium` and really does arrive unchanged - if the entity's default ever
    moved, the schema and this assertion would move with it together.
    """
    unit_of_work = _uow()
    use_case = CreateTask(unit_of_work, FrozenClock(LATER))

    result = await use_case.execute(_command(priority=Task.DEFAULT_PRIORITY))

    assert result.priority is TaskPriority.MEDIUM
    assert unit_of_work.commits == 1


async def test_create_task_refuses_a_blank_title() -> None:
    """TASK-08 rule 3, proved through the use case rather than at the entity."""
    unit_of_work = _uow()
    use_case = CreateTask(unit_of_work, FrozenClock(LATER))

    with pytest.raises(ValidationError) as excinfo:
        await use_case.execute(_command(title="   "))

    assert excinfo.value.details == {"field": "title"}
    assert unit_of_work.task_repository.added == []
    assert unit_of_work.task_repository.stored == {}
    assert unit_of_work.commits == 0
    assert unit_of_work.rollbacks == 1


async def test_create_task_refuses_an_over_long_title() -> None:
    """The other half of TASK-08 rule 3: one character past the entity's cap."""
    unit_of_work = _uow()
    use_case = CreateTask(unit_of_work, FrozenClock(LATER))

    with pytest.raises(ValidationError) as excinfo:
        await use_case.execute(_command(title=OVER_LONG_TITLE))

    assert excinfo.value.details == {"field": "title"}
    assert unit_of_work.task_repository.added == []
    assert unit_of_work.commits == 0
    assert unit_of_work.rollbacks == 1


async def test_create_task_refuses_a_deadline_behind_the_creation_moment() -> None:
    """TASK-08 rule 6, measured against the clock this use case just read.

    `NOW` is three hours behind the stopped clock, so the deadline is in the
    past for this request and for no other reason - a use case that stamped the
    task from something it found in the repository would accept it.
    """
    unit_of_work = _uow()
    use_case = CreateTask(unit_of_work, FrozenClock(LATER))

    with pytest.raises(ValidationError) as excinfo:
        await use_case.execute(_command(due_date=NOW))

    assert excinfo.value.details == {"field": "due_date"}
    assert unit_of_work.task_repository.added == []
    assert unit_of_work.commits == 0
    assert unit_of_work.rollbacks == 1


async def test_create_task_hides_a_list_not_owned_by_the_actor() -> None:
    """D-04 on the create verb: a 404, never a 403, and nothing written.

    The broad `DomainError` is caught on purpose - catching the leaf directly
    would pass against an implementation that never considered the 403 question
    (T-4-29).
    """
    unit_of_work = _uow(owner_id=OTHER_USER_ID)
    use_case = CreateTask(unit_of_work, FrozenClock(LATER))

    with pytest.raises(DomainError) as excinfo:
        await use_case.execute(_command())

    error = excinfo.value
    assert isinstance(error, TaskListNotFoundError)
    assert not isinstance(error, AuthorizationError)
    assert error.details == {"task_list_id": str(TASK_LIST_ID)}
    assert unit_of_work.task_repository.added == []
    assert unit_of_work.task_repository.stored == {}
    assert unit_of_work.commits == 0
    assert unit_of_work.rollbacks == 1


async def test_creating_in_a_foreign_list_answers_exactly_like_an_absent_one() -> None:
    """Both refusals are produced and compared, because D-04 is about a pair.

    This is the one task verb whose refusal is list-shaped, and the reason is
    that the caller addressed the list: no task exists yet, so there is no task
    identifier to answer with and nothing the list-shaped error can disclose
    that the request did not already contain.
    """
    absent_uow = _uow(with_list=False)
    with pytest.raises(DomainError) as absent_info:
        await CreateTask(absent_uow, FrozenClock(LATER)).execute(_command())

    foreign_uow = _uow(owner_id=OTHER_USER_ID)
    with pytest.raises(DomainError) as foreign_info:
        await CreateTask(foreign_uow, FrozenClock(LATER)).execute(_command())

    absent, foreign = absent_info.value, foreign_info.value
    assert type(foreign) is type(absent)
    assert foreign.code == absent.code
    assert foreign.details == absent.details
    assert str(foreign) == str(absent)
    assert str(OTHER_USER_ID) not in str(foreign.details)
    assert absent_uow.commits == 0
    assert foreign_uow.commits == 0
