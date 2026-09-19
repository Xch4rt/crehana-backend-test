"""TASK-03: four patchable fields, three D-05 legs each, and one absent field.

The module is laid out like its sibling `test_update_task_list.py`, because the
two verbs share a rule and a reader should be able to tell at a glance that they
implement it the same way. Three legs are pinned separately per field - omitted,
carrying a value, carrying an explicit null - because they are three different
outcomes and only the sentinel can express the difference.

Two tests here have no counterpart in the sibling.
`test_a_patch_without_due_date_does_not_recheck_an_overdue_task` is D-07: it
fails, and nothing else does, if the deadline guard is ever unconditional.
`test_update_task_cannot_change_a_status` is D-08 from two directions at once -
the command declares no such field, and this module's subject calls no mutator
that could write one.
"""

import inspect
from dataclasses import fields
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from taskmanager.application.dto.commands import UpdateTaskCommand
from taskmanager.application.dto.unset import UNSET, Unset
from taskmanager.application.use_cases.tasks import update as update_module
from taskmanager.application.use_cases.tasks.update import UpdateTask
from taskmanager.domain.entities.task import Task
from taskmanager.domain.entities.task_list import TaskList
from taskmanager.domain.exceptions import (
    AuthorizationError,
    DomainError,
    TaskListNotFoundError,
    TaskNotFoundError,
    ValidationError,
)
from taskmanager.domain.value_objects.task_priority import TaskPriority
from taskmanager.domain.value_objects.task_status import TaskStatus
from tests.unit.application.fakes import FakeUnitOfWork, FrozenClock

pytestmark = pytest.mark.unit

# Fixed on purpose. A generated identifier or a real clock reading would make
# every assertion below unfalsifiable: the test could no longer state which
# moment, or which actor, it expects.
NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
LATER = NOW + timedelta(hours=3)
# Set while the task is created at `NOW` and already past by the time the clock
# reads `LATER`: this is the deadline D-07 must not re-check.
OVERDUE_DEADLINE = NOW + timedelta(hours=1)
NEW_DEADLINE = LATER + timedelta(days=7)
ACTOR_ID = UUID("11111111-1111-4111-8111-111111111111")
OTHER_USER_ID = UUID("99999999-9999-4999-8999-999999999999")
TASK_ID = UUID("22222222-2222-4222-8222-222222222222")
TASK_LIST_ID = UUID("33333333-3333-4333-8333-333333333333")
OTHER_LIST_ID = UUID("44444444-4444-4444-8444-444444444444")
# The third role D-03 introduces. `OTHER_USER_ID` is the foreign *owner* in
# these fixtures, so a caller who is neither owner nor assignee needs an
# identifier of their own.
STRANGER_ID = UUID("55555555-5555-4555-8555-555555555555")

TITLE = "Patch one task"
NEW_TITLE = "Patch one task, partially"
DESCRIPTION = "The four fields a client may change."
NEW_DESCRIPTION = "Rewritten in one PATCH."
# One character past the entity's cap, read off the ClassVar rather than typed
# out: the limit has one home, and a literal here would be a second copy of it.
OVER_LONG_TITLE = "x" * (Task.TITLE_MAX_LENGTH + 1)
# The one entity mutator this use case must never reach (D-08). Named here so
# the source scan below has a single spelling to go by.
FORBIDDEN_MUTATOR = "change_status"


def _uow(
    *,
    owner_id: UUID = ACTOR_ID,
    with_task: bool = True,
    stored_under: UUID = TASK_LIST_ID,
    due_date: datetime | None = None,
    assignee_id: UUID | None = None,
) -> FakeUnitOfWork:
    """Assemble a unit of work holding both lists, and optionally the task.

    `stored_under` is D-14's lever: the task is filed under a list the request
    never names, while the addressed list exists and belongs to the actor.
    Entities go into `stored` directly rather than through `add()`, so the
    `updated` record stays empty and every entry a test finds in it was written
    by the use case.
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
            priority=TaskPriority.LOW,
            due_date=due_date,
            assignee_id=assignee_id,
            now=NOW,
        )
        unit_of_work.task_repository.stored[task.id] = task
    return unit_of_work


def _command(
    *,
    title: str | Unset = UNSET,
    description: str | None | Unset = UNSET,
    priority: TaskPriority | Unset = UNSET,
    due_date: datetime | None | Unset = UNSET,
    actor_id: UUID = ACTOR_ID,
) -> UpdateTaskCommand:
    """The single construction site every test below goes through."""
    return UpdateTaskCommand(
        actor_id=actor_id,
        task_list_id=TASK_LIST_ID,
        task_id=TASK_ID,
        title=title,
        description=description,
        priority=priority,
        due_date=due_date,
    )


async def test_update_task_renames_and_touches_nothing_else() -> None:
    """The omitted leg of D-05: three fields nobody mentioned are left alone."""
    unit_of_work = _uow(due_date=OVERDUE_DEADLINE)
    use_case = UpdateTask(unit_of_work, FrozenClock(LATER))

    result = await use_case.execute(_command(title=NEW_TITLE))

    assert result.title == NEW_TITLE
    assert result.description == DESCRIPTION
    assert result.priority is TaskPriority.LOW
    assert result.due_date == OVERDUE_DEADLINE
    assert result.created_at == NOW
    assert result.updated_at == LATER
    assert len(unit_of_work.task_repository.updated) == 1
    assert unit_of_work.commits == 1
    assert unit_of_work.rollbacks == 0


async def test_update_task_re_describes_and_touches_nothing_else() -> None:
    """The same rule from the second field, so no mutator can be the default."""
    unit_of_work = _uow(due_date=OVERDUE_DEADLINE)
    use_case = UpdateTask(unit_of_work, FrozenClock(LATER))

    result = await use_case.execute(_command(description=NEW_DESCRIPTION))

    assert result.description == NEW_DESCRIPTION
    assert result.title == TITLE
    assert result.priority is TaskPriority.LOW
    assert result.due_date == OVERDUE_DEADLINE
    assert result.updated_at == LATER
    assert unit_of_work.commits == 1
    assert unit_of_work.rollbacks == 0


async def test_update_task_reprioritises_and_touches_nothing_else() -> None:
    """The third field, raised from low to high and nothing beside it."""
    unit_of_work = _uow(due_date=OVERDUE_DEADLINE)
    use_case = UpdateTask(unit_of_work, FrozenClock(LATER))

    result = await use_case.execute(_command(priority=TaskPriority.HIGH))

    assert result.priority is TaskPriority.HIGH
    assert result.title == TITLE
    assert result.description == DESCRIPTION
    assert result.due_date == OVERDUE_DEADLINE
    assert result.updated_at == LATER
    assert unit_of_work.commits == 1
    assert unit_of_work.rollbacks == 0


async def test_update_task_reschedules_and_touches_nothing_else() -> None:
    """The fourth field: a deadline ahead of the clock is accepted."""
    unit_of_work = _uow(due_date=OVERDUE_DEADLINE)
    use_case = UpdateTask(unit_of_work, FrozenClock(LATER))

    result = await use_case.execute(_command(due_date=NEW_DEADLINE))

    assert result.due_date == NEW_DEADLINE
    assert result.title == TITLE
    assert result.description == DESCRIPTION
    assert result.priority is TaskPriority.LOW
    assert result.updated_at == LATER
    assert unit_of_work.commits == 1
    assert unit_of_work.rollbacks == 0


async def test_an_explicit_null_description_clears_it() -> None:
    """D-05's third leg, and the reason `None` cannot also mean "omitted".

    This is the request the sentinel exists for: it and the re-describe test
    send the same field, and a use case with one marker for both meanings has to
    get one of them wrong.
    """
    unit_of_work = _uow()
    use_case = UpdateTask(unit_of_work, FrozenClock(LATER))

    result = await use_case.execute(_command(description=None))

    assert result.description is None
    assert result.title == TITLE
    assert unit_of_work.task_repository.stored[TASK_ID].description is None
    assert unit_of_work.commits == 1


async def test_an_explicit_null_due_date_clears_it() -> None:
    """The same leg on the other nullable field, and on the one D-07 guards.

    Clearing a deadline is not setting one, so the past-moment rule has nothing
    to say about it - an overdue task can always be freed of its deadline.
    """
    unit_of_work = _uow(due_date=OVERDUE_DEADLINE)
    use_case = UpdateTask(unit_of_work, FrozenClock(LATER))

    result = await use_case.execute(_command(due_date=None))

    assert result.due_date is None
    assert unit_of_work.task_repository.stored[TASK_ID].due_date is None
    assert unit_of_work.commits == 1


async def test_a_command_with_no_field_at_all_changes_nothing_and_commits() -> None:
    """The request D-06 never lets through, pinned anyway.

    `updated_at` does **not** move here, and that is the decision stated
    exactly: the stamp follows a field being *provided*, and no field was. The
    schema answers an empty body with a 422 before a command is built, so this
    is the use case's behaviour for a request the API does not deliver - worth a
    test precisely because nothing upstream would reveal a change in it.
    """
    unit_of_work = _uow(due_date=OVERDUE_DEADLINE)
    use_case = UpdateTask(unit_of_work, FrozenClock(LATER))

    result = await use_case.execute(_command())

    assert result.title == TITLE
    assert result.description == DESCRIPTION
    assert result.priority is TaskPriority.LOW
    assert result.due_date == OVERDUE_DEADLINE
    assert result.updated_at == NOW
    assert len(unit_of_work.task_repository.updated) == 1
    assert unit_of_work.commits == 1
    assert unit_of_work.rollbacks == 0


async def test_a_patch_without_due_date_does_not_recheck_an_overdue_task() -> None:
    """D-07, and the one test that fails if the deadline guard goes away.

    The stored deadline is an hour after creation and two hours behind the
    clock, so it is unambiguously in the past for this request. An
    implementation that re-applied it - with the stored value, unconditionally -
    would refuse this PATCH naming a field the caller never sent, and the task
    could never be renamed again.
    """
    unit_of_work = _uow(due_date=OVERDUE_DEADLINE)
    use_case = UpdateTask(unit_of_work, FrozenClock(LATER))

    result = await use_case.execute(
        _command(title=NEW_TITLE, priority=TaskPriority.HIGH)
    )

    assert result.title == NEW_TITLE
    assert result.priority is TaskPriority.HIGH
    assert result.due_date == OVERDUE_DEADLINE
    assert result.updated_at == LATER
    assert unit_of_work.commits == 1
    assert unit_of_work.rollbacks == 0


async def test_setting_due_date_to_a_past_moment_is_refused() -> None:
    """The other side of D-07: a deadline the client *does* send is checked.

    The entity's rule is unchanged and is not restated in the use case, so what
    this proves is that the refusal reaches the caller with nothing written and
    the transaction closed.
    """
    unit_of_work = _uow()
    use_case = UpdateTask(unit_of_work, FrozenClock(LATER))

    with pytest.raises(ValidationError) as excinfo:
        await use_case.execute(_command(due_date=NOW))

    assert excinfo.value.details == {"field": "due_date"}
    assert unit_of_work.task_repository.updated == []
    assert unit_of_work.task_repository.stored[TASK_ID].due_date is None
    assert unit_of_work.commits == 0
    assert unit_of_work.rollbacks == 1


async def test_update_task_refuses_a_blank_title() -> None:
    """TASK-08 rule 3 on the patch verb, and the stored row is untouched."""
    unit_of_work = _uow()
    use_case = UpdateTask(unit_of_work, FrozenClock(LATER))

    with pytest.raises(ValidationError) as excinfo:
        await use_case.execute(_command(title="   "))

    assert excinfo.value.details == {"field": "title"}
    assert unit_of_work.task_repository.updated == []
    assert unit_of_work.task_repository.stored[TASK_ID].title == TITLE
    assert unit_of_work.task_repository.stored[TASK_ID].updated_at == NOW
    assert unit_of_work.commits == 0
    assert unit_of_work.rollbacks == 1


async def test_update_task_refuses_an_over_long_title() -> None:
    """The other half of TASK-08 rule 3: one character past the entity's cap."""
    unit_of_work = _uow()
    use_case = UpdateTask(unit_of_work, FrozenClock(LATER))

    with pytest.raises(ValidationError) as excinfo:
        await use_case.execute(_command(title=OVER_LONG_TITLE))

    assert excinfo.value.details == {"field": "title"}
    assert unit_of_work.task_repository.updated == []
    assert unit_of_work.task_repository.stored[TASK_ID].title == TITLE
    assert unit_of_work.commits == 0
    assert unit_of_work.rollbacks == 1


def test_update_task_cannot_change_a_status() -> None:
    """D-08 and TASK-03, enforced from two directions rather than by convention.

    The command declares no such field, so a router could not pass one even if
    it wanted to; and the use case's source calls no mutator that could write
    one, so the absence is not merely unreachable but unwritten. The schema's
    `extra="forbid"` adds the third point, one layer up, where an attempt
    becomes a 422.
    """
    declared = {field.name for field in fields(UpdateTaskCommand)}
    source = inspect.getsource(update_module)

    assert "status" not in declared
    assert FORBIDDEN_MUTATOR not in source
    assert TaskStatus.__name__ not in source


async def test_update_task_refuses_a_task_stored_under_a_different_list() -> None:
    """D-14 on the patch verb, with the stored row asserted unchanged.

    Both lists exist and both belong to the actor, so nothing but the mismatch
    can refuse this request - an implementation that patched by identifier alone
    would rewrite a task the caller addressed through the wrong parent.
    """
    unit_of_work = _uow(stored_under=OTHER_LIST_ID)
    use_case = UpdateTask(unit_of_work, FrozenClock(LATER))

    with pytest.raises(TaskNotFoundError) as excinfo:
        await use_case.execute(_command(title=NEW_TITLE))

    assert excinfo.value.details == {"task_id": str(TASK_ID)}
    assert unit_of_work.task_repository.updated == []
    assert unit_of_work.task_repository.stored[TASK_ID].title == TITLE
    assert unit_of_work.commits == 0
    assert unit_of_work.rollbacks == 1


async def test_update_task_hides_a_task_whose_list_the_actor_does_not_own() -> None:
    """D-04: the refusal is task-shaped, never list-shaped and never a 403.

    The broad `DomainError` is caught on purpose - catching the leaf directly
    would pass against an implementation that never considered the 403 question
    (T-4-29).
    """
    unit_of_work = _uow(owner_id=OTHER_USER_ID)
    use_case = UpdateTask(unit_of_work, FrozenClock(LATER))

    with pytest.raises(DomainError) as excinfo:
        await use_case.execute(_command(title=NEW_TITLE))

    error = excinfo.value
    assert isinstance(error, TaskNotFoundError)
    assert not isinstance(error, TaskListNotFoundError)
    assert not isinstance(error, AuthorizationError)
    assert error.details == {"task_id": str(TASK_ID)}
    assert unit_of_work.task_repository.updated == []
    assert unit_of_work.task_repository.stored[TASK_ID].title == TITLE
    assert unit_of_work.commits == 0
    assert unit_of_work.rollbacks == 1


async def test_update_task_refuses_the_assignee_with_a_403() -> None:
    """D-03: the assignee may advance the status and may not rewrite the task.

    They can see this task - a `GET` and a `PATCH .../status` both answer 200 -
    so the generic patch is the first request in this project that has to be
    refused as forbidden rather than as absent.

    `commits == 0` is asserted beside the exception because an authorization
    refusal must make nothing durable, and the stored title is read back for the
    same reason: "refused" and "wrote nothing" are two claims, and a use case
    can satisfy one while failing the other.
    """
    unit_of_work = _uow(owner_id=OTHER_USER_ID, assignee_id=ACTOR_ID)
    use_case = UpdateTask(unit_of_work, FrozenClock(LATER))

    with pytest.raises(DomainError) as excinfo:
        await use_case.execute(_command(title=NEW_TITLE))

    error = excinfo.value
    assert isinstance(error, AuthorizationError)
    assert not isinstance(error, TaskNotFoundError)
    assert str(OTHER_USER_ID) not in str(error)
    assert unit_of_work.task_repository.updated == []
    assert unit_of_work.task_repository.stored[TASK_ID].title == TITLE
    assert unit_of_work.commits == 0
    assert unit_of_work.rollbacks == 1


async def test_update_task_still_hides_the_task_from_a_stranger() -> None:
    """The 403 is for the assignee alone; everybody else still sees nothing.

    Somebody *is* assigned here, so the forbidden leg exists and this caller
    still does not reach it - which is what separates this from the
    foreign-list case above, written when no task could have an assignee.
    """
    unit_of_work = _uow(owner_id=OTHER_USER_ID, assignee_id=ACTOR_ID)
    use_case = UpdateTask(unit_of_work, FrozenClock(LATER))

    with pytest.raises(DomainError) as excinfo:
        await use_case.execute(_command(title=NEW_TITLE, actor_id=STRANGER_ID))

    error = excinfo.value
    assert isinstance(error, TaskNotFoundError)
    assert not isinstance(error, AuthorizationError)
    assert error.details == {"task_id": str(TASK_ID)}
    assert unit_of_work.task_repository.updated == []
    assert unit_of_work.commits == 0
    assert unit_of_work.rollbacks == 1


async def test_the_assignees_403_and_a_strangers_404_are_different_answers() -> None:
    """AUTH-06 is about a pair too, and this pair must *not* match.

    Every other comparative test in this module produces two refusals and
    asserts they are indistinguishable. This one produces two refusals from the
    identical fixture - one actor assigned, one not - and asserts they differ in
    class and in code, because a use case that answered the assignee 404 would
    satisfy the sibling test above and silently drop D-03.
    """
    assignee_uow = _uow(owner_id=OTHER_USER_ID, assignee_id=ACTOR_ID)
    with pytest.raises(DomainError) as assignee_info:
        await UpdateTask(assignee_uow, FrozenClock(LATER)).execute(
            _command(title=NEW_TITLE)
        )

    stranger_uow = _uow(owner_id=OTHER_USER_ID, assignee_id=ACTOR_ID)
    with pytest.raises(DomainError) as stranger_info:
        await UpdateTask(stranger_uow, FrozenClock(LATER)).execute(
            _command(title=NEW_TITLE, actor_id=STRANGER_ID)
        )

    forbidden, hidden = assignee_info.value, stranger_info.value
    assert type(forbidden) is not type(hidden)
    assert forbidden.code != hidden.code
    assert isinstance(forbidden, AuthorizationError)
    assert isinstance(hidden, TaskNotFoundError)
    assert assignee_uow.commits == stranger_uow.commits == 0


async def test_the_refused_patches_answer_exactly_like_an_absent_task() -> None:
    """D-14 and D-04 are each about a pair, so all three refusals are compared.

    The wrong-list case and the foreign-list case are produced beside the
    absent-task case and matched on class, code, details and message - a
    distinction in any one of the four would hand an enumerating caller the bit
    both decisions exist to withhold.
    """
    absent_uow = _uow(with_task=False)
    with pytest.raises(DomainError) as absent_info:
        await UpdateTask(absent_uow, FrozenClock(LATER)).execute(
            _command(title=NEW_TITLE)
        )

    wrong_list_uow = _uow(stored_under=OTHER_LIST_ID)
    with pytest.raises(DomainError) as wrong_list_info:
        await UpdateTask(wrong_list_uow, FrozenClock(LATER)).execute(
            _command(title=NEW_TITLE)
        )

    foreign_uow = _uow(owner_id=OTHER_USER_ID)
    with pytest.raises(DomainError) as foreign_info:
        await UpdateTask(foreign_uow, FrozenClock(LATER)).execute(
            _command(title=NEW_TITLE)
        )

    absent = absent_info.value
    for refusal in (wrong_list_info.value, foreign_info.value):
        assert type(refusal) is type(absent)
        assert refusal.code == absent.code
        assert refusal.details == absent.details
        assert str(refusal) == str(absent)
    assert str(OTHER_USER_ID) not in str(foreign_info.value.details)
    assert str(OTHER_LIST_ID) not in str(wrong_list_info.value.details)
