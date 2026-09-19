"""TASK-04, and the two refusals a delete gets wrong most quietly.

A delete issued straight against the identifier removes nothing when the task
belongs to somebody else - and then answers 204. Every failure test here
therefore asserts *both* that the error came out and that `deleted` is empty:
"nothing was removed" and "the caller was told so" are two different claims, and
an implementation can satisfy one while failing the other.

The second refusal is D-14's. A task addressed under a list it does not belong
to must answer exactly as an absent task does, so the comparative test below
produces both errors and compares them rather than asserting one of them alone.
"""

import inspect
from datetime import UTC, datetime
from typing import get_type_hints
from uuid import UUID

import pytest

from taskmanager.application.dto.commands import DeleteTaskCommand
from taskmanager.application.use_cases.tasks.delete import DeleteTask
from taskmanager.domain.entities.task import Task
from taskmanager.domain.entities.task_list import TaskList
from taskmanager.domain.exceptions import (
    AuthorizationError,
    DomainError,
    TaskListNotFoundError,
    TaskNotFoundError,
)
from taskmanager.domain.value_objects.task_priority import TaskPriority
from tests.unit.application.fakes import FakeUnitOfWork

pytestmark = pytest.mark.unit

# Fixed on purpose. A generated identifier or a real clock reading would make
# every assertion below unfalsifiable: the test could no longer state which
# moment, or which actor, it expects.
NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
ACTOR_ID = UUID("11111111-1111-4111-8111-111111111111")
OTHER_USER_ID = UUID("99999999-9999-4999-8999-999999999999")
TASK_ID = UUID("22222222-2222-4222-8222-222222222222")
TASK_LIST_ID = UUID("33333333-3333-4333-8333-333333333333")
OTHER_LIST_ID = UUID("44444444-4444-4444-8444-444444444444")
# The third role D-03 introduces. `OTHER_USER_ID` is the foreign *owner* in
# these fixtures, so a caller who is neither owner nor assignee needs an
# identifier of their own.
STRANGER_ID = UUID("55555555-5555-4555-8555-555555555555")


def _uow(
    *,
    owner_id: UUID = ACTOR_ID,
    with_task: bool = True,
    stored_under: UUID = TASK_LIST_ID,
    assignee_id: UUID | None = None,
) -> FakeUnitOfWork:
    """Assemble a unit of work holding the list, and optionally the task.

    `stored_under` is D-14's lever: the task is filed under a list the request
    never names, while the addressed list exists and belongs to the actor.
    Entities go into `stored` directly rather than through `add()`, so the
    `deleted` record stays empty and every entry a test finds in it was written
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
            title="Delete me",
            priority=TaskPriority.HIGH,
            assignee_id=assignee_id,
            now=NOW,
        )
        unit_of_work.task_repository.stored[task.id] = task
    return unit_of_work


def _command(*, actor_id: UUID = ACTOR_ID) -> DeleteTaskCommand:
    """The single construction site every test below goes through."""
    return DeleteTaskCommand(
        actor_id=actor_id,
        task_list_id=TASK_LIST_ID,
        task_id=TASK_ID,
    )


async def test_delete_task_removes_the_task_and_commits() -> None:
    """The happy path: the row is gone and the transaction made it durable.

    Nothing is bound from the call. `execute` is annotated to return `None`, and
    mypy refuses to let a value be read off it at all - which is why the
    contract is asserted from the annotation further down rather than from an
    answer this test could have held.
    """
    unit_of_work = _uow()
    use_case = DeleteTask(unit_of_work)

    await use_case.execute(_command())

    assert unit_of_work.task_repository.deleted == [TASK_ID]
    assert TASK_ID not in unit_of_work.task_repository.stored
    assert unit_of_work.commits == 1
    assert unit_of_work.rollbacks == 0


async def test_delete_task_refuses_an_absent_task() -> None:
    """A task that does not exist is a 404 carrying only the requested id."""
    unit_of_work = _uow(with_task=False)
    use_case = DeleteTask(unit_of_work)

    with pytest.raises(TaskNotFoundError) as excinfo:
        await use_case.execute(_command())

    assert excinfo.value.details == {"task_id": str(TASK_ID)}
    assert unit_of_work.task_repository.deleted == []
    assert unit_of_work.commits == 0
    assert unit_of_work.rollbacks == 1


async def test_delete_task_refuses_a_task_stored_under_a_different_list() -> None:
    """D-14 on the destructive verb, and the row is still there afterwards.

    Both lists exist and both belong to the actor, so nothing but the mismatch
    can refuse this request - an implementation that deleted by identifier alone
    would destroy a task the caller addressed through the wrong parent, and
    report success.
    """
    unit_of_work = _uow(stored_under=OTHER_LIST_ID)
    use_case = DeleteTask(unit_of_work)

    with pytest.raises(TaskNotFoundError) as excinfo:
        await use_case.execute(_command())

    assert excinfo.value.details == {"task_id": str(TASK_ID)}
    assert str(OTHER_LIST_ID) not in str(excinfo.value.details)
    assert unit_of_work.task_repository.deleted == []
    assert TASK_ID in unit_of_work.task_repository.stored
    assert unit_of_work.commits == 0
    assert unit_of_work.rollbacks == 1


async def test_the_wrong_list_delete_answers_exactly_like_an_absent_task() -> None:
    """D-14 is about a pair, so both refusals are produced and compared.

    The comparison covers the message as well as the class, the code and the
    details: a message naming the parent list would distinguish the two cases
    just as loudly as a different code.
    """
    absent_uow = _uow(with_task=False)
    with pytest.raises(DomainError) as absent_info:
        await DeleteTask(absent_uow).execute(_command())

    wrong_list_uow = _uow(stored_under=OTHER_LIST_ID)
    with pytest.raises(DomainError) as wrong_list_info:
        await DeleteTask(wrong_list_uow).execute(_command())

    absent, wrong_list = absent_info.value, wrong_list_info.value
    assert type(wrong_list) is type(absent)
    assert wrong_list.code == absent.code
    assert wrong_list.details == absent.details
    assert str(wrong_list) == str(absent)


async def test_delete_task_hides_a_task_whose_list_the_actor_does_not_own() -> None:
    """D-04: the refusal is task-shaped, never list-shaped and never a 403.

    The broad `DomainError` is caught on purpose - catching the leaf directly
    would pass against an implementation that never considered the 403 question
    (T-4-29). `TaskListNotFoundError` is ruled out explicitly as well, because
    it would carry a different code *and* the parent's identifier: two things
    the caller is not entitled to learn from a task they may not see.
    """
    unit_of_work = _uow(owner_id=OTHER_USER_ID)
    use_case = DeleteTask(unit_of_work)

    with pytest.raises(DomainError) as excinfo:
        await use_case.execute(_command())

    error = excinfo.value
    assert isinstance(error, TaskNotFoundError)
    assert not isinstance(error, TaskListNotFoundError)
    assert not isinstance(error, AuthorizationError)
    assert error.details == {"task_id": str(TASK_ID)}
    assert unit_of_work.task_repository.deleted == []
    assert TASK_ID in unit_of_work.task_repository.stored
    assert unit_of_work.commits == 0
    assert unit_of_work.rollbacks == 1


async def test_delete_task_refuses_the_assignee_with_a_403() -> None:
    """D-03: an assignee may work on a task, never destroy it.

    This is the loudest of the four verbs to get wrong. An implementation that
    kept the old visibility door would let a user who cannot even see the list
    delete a row out of it, and would answer 204 - so the assertion that the
    task is still stored matters as much as the exception.
    """
    unit_of_work = _uow(owner_id=OTHER_USER_ID, assignee_id=ACTOR_ID)
    use_case = DeleteTask(unit_of_work)

    with pytest.raises(DomainError) as excinfo:
        await use_case.execute(_command())

    error = excinfo.value
    assert isinstance(error, AuthorizationError)
    assert not isinstance(error, TaskNotFoundError)
    assert str(OTHER_USER_ID) not in str(error)
    assert unit_of_work.task_repository.deleted == []
    assert TASK_ID in unit_of_work.task_repository.stored
    assert unit_of_work.commits == 0
    assert unit_of_work.rollbacks == 1


async def test_delete_task_still_hides_the_task_from_a_stranger() -> None:
    """The forbidden leg exists in this fixture and this caller misses it."""
    unit_of_work = _uow(owner_id=OTHER_USER_ID, assignee_id=ACTOR_ID)
    use_case = DeleteTask(unit_of_work)

    with pytest.raises(DomainError) as excinfo:
        await use_case.execute(_command(actor_id=STRANGER_ID))

    error = excinfo.value
    assert isinstance(error, TaskNotFoundError)
    assert not isinstance(error, AuthorizationError)
    assert error.details == {"task_id": str(TASK_ID)}
    assert unit_of_work.task_repository.deleted == []
    assert unit_of_work.commits == 0
    assert unit_of_work.rollbacks == 1


async def test_the_assignees_403_and_a_strangers_404_are_different_answers() -> None:
    """The one comparison in this module that must find a difference.

    Its siblings above produce two refusals and assert they match. This one
    produces two from the identical fixture and asserts they do not, because a
    use case that answered the assignee 404 would pass every other test here
    while quietly dropping D-03.
    """
    assignee_uow = _uow(owner_id=OTHER_USER_ID, assignee_id=ACTOR_ID)
    with pytest.raises(DomainError) as assignee_info:
        await DeleteTask(assignee_uow).execute(_command())

    stranger_uow = _uow(owner_id=OTHER_USER_ID, assignee_id=ACTOR_ID)
    with pytest.raises(DomainError) as stranger_info:
        await DeleteTask(stranger_uow).execute(_command(actor_id=STRANGER_ID))

    forbidden, hidden = assignee_info.value, stranger_info.value
    assert type(forbidden) is not type(hidden)
    assert forbidden.code != hidden.code
    assert isinstance(forbidden, AuthorizationError)
    assert isinstance(hidden, TaskNotFoundError)
    assert assignee_uow.task_repository.deleted == []
    assert stranger_uow.task_repository.deleted == []


def test_delete_task_declares_no_result_at_all() -> None:
    """TASK-04's 204 has no body, so `execute` has nothing to return.

    Read off the annotation rather than off a call, because `None` is also what
    an implementation that forgot its `return` would hand back - the claim is
    about the contract, not about one invocation of it.
    """
    assert get_type_hints(DeleteTask.execute)["return"] is type(None)


def test_delete_task_asks_for_no_clock() -> None:
    """ARC-04 read back off the constructor: this operation stamps nothing.

    A `Clock` accepted and never read would be a dependency this use case does
    not have, and the whole point of one class per operation is that its
    constructor states exactly what the operation touches.
    """
    parameters = list(inspect.signature(DeleteTask.__init__).parameters)

    assert parameters[1:] == ["uow"]
