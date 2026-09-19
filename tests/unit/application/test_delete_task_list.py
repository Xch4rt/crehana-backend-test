"""LIST-05: the verb whose refusal is easiest to get wrong quietly.

A delete issued straight against the identifier removes nothing when the list
belongs to someone else - and then answers 204. Every failure test here
therefore asserts *both* that the error came out and that `deleted` is empty:
"nothing was removed" and "the caller was told so" are two different claims, and
an implementation can satisfy one while failing the other.
"""

import inspect
from datetime import UTC, datetime
from typing import get_type_hints
from uuid import UUID

import pytest

from taskmanager.application.dto.commands import DeleteTaskListCommand
from taskmanager.application.use_cases.task_lists.delete import DeleteTaskList
from taskmanager.domain.entities.task_list import TaskList
from taskmanager.domain.exceptions import (
    AuthorizationError,
    DomainError,
    TaskListNotFoundError,
)
from tests.unit.application.fakes import FakeUnitOfWork

pytestmark = pytest.mark.unit

# Fixed on purpose. A generated identifier or a real clock reading would make
# every assertion below unfalsifiable: the test could no longer state which
# moment, or which actor, it expects.
NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
ACTOR_ID = UUID("11111111-1111-4111-8111-111111111111")
OTHER_USER_ID = UUID("99999999-9999-4999-8999-999999999999")
LIST_ID = UUID("33333333-3333-4333-8333-333333333333")

NAME = "Phase 4"


def _uow(*, owner_id: UUID = ACTOR_ID, with_list: bool = True) -> FakeUnitOfWork:
    """Assemble a unit of work optionally holding the list under test."""
    unit_of_work = FakeUnitOfWork()
    if with_list:
        task_list = TaskList.create(
            task_list_id=LIST_ID,
            owner_id=owner_id,
            name=NAME,
            now=NOW,
        )
        unit_of_work.task_list_repository.stored[task_list.id] = task_list
    return unit_of_work


def _command(*, actor_id: UUID = ACTOR_ID) -> DeleteTaskListCommand:
    """The single construction site every test below goes through."""
    return DeleteTaskListCommand(actor_id=actor_id, task_list_id=LIST_ID)


async def test_delete_task_list_removes_the_list_and_commits() -> None:
    """The happy path: the row is gone and the transaction made it durable."""
    unit_of_work = _uow()
    use_case = DeleteTaskList(unit_of_work)

    await use_case.execute(_command())

    assert unit_of_work.task_list_repository.deleted == [LIST_ID]
    assert LIST_ID not in unit_of_work.task_list_repository.stored
    assert unit_of_work.commits == 1
    assert unit_of_work.rollbacks == 0


async def test_delete_task_list_refuses_an_absent_list() -> None:
    """A list that does not exist is a 404 carrying only the requested id."""
    unit_of_work = _uow(with_list=False)
    use_case = DeleteTaskList(unit_of_work)

    with pytest.raises(TaskListNotFoundError) as excinfo:
        await use_case.execute(_command())

    assert excinfo.value.details == {"task_list_id": str(LIST_ID)}
    assert unit_of_work.task_list_repository.deleted == []
    assert unit_of_work.commits == 0
    assert unit_of_work.rollbacks == 1


async def test_delete_task_list_hides_a_list_not_owned_by_the_actor() -> None:
    """D-04 on the destructive verb: refused, untouched, and a 404 not a 403.

    The stored list is asserted to still be there. An implementation that
    deleted first and authorized afterwards would raise the right error and
    have already destroyed the row.
    """
    unit_of_work = _uow(owner_id=OTHER_USER_ID)
    use_case = DeleteTaskList(unit_of_work)

    with pytest.raises(DomainError) as excinfo:
        await use_case.execute(_command())

    error = excinfo.value
    assert isinstance(error, TaskListNotFoundError)
    assert not isinstance(error, AuthorizationError)
    assert error.details == {"task_list_id": str(LIST_ID)}
    assert unit_of_work.task_list_repository.deleted == []
    assert LIST_ID in unit_of_work.task_list_repository.stored
    assert unit_of_work.commits == 0
    assert unit_of_work.rollbacks == 1


async def test_the_not_owned_delete_answers_exactly_like_an_absent_list() -> None:
    """Both refusals are produced and compared, because D-04 is about a pair.

    The 204 a silent no-op would return is the loudest possible distinction
    between the two cases, so the comparison covers the message as well as the
    class, the code and the details.
    """
    absent_uow = _uow(with_list=False)
    with pytest.raises(DomainError) as absent_info:
        await DeleteTaskList(absent_uow).execute(_command())

    foreign_uow = _uow(owner_id=OTHER_USER_ID)
    with pytest.raises(DomainError) as foreign_info:
        await DeleteTaskList(foreign_uow).execute(_command())

    absent, foreign = absent_info.value, foreign_info.value
    assert type(foreign) is type(absent)
    assert foreign.code == absent.code
    assert foreign.details == absent.details
    assert str(foreign) == str(absent)
    assert str(OTHER_USER_ID) not in str(foreign.details)


def test_delete_task_list_declares_no_result_at_all() -> None:
    """LIST-05's 204 has no body, so `execute` has nothing to return.

    Read off the annotation rather than off a call, because `None` is also what
    an implementation that forgot its `return` would hand back - the claim is
    about the contract, not about one invocation of it.
    """
    assert get_type_hints(DeleteTaskList.execute)["return"] is type(None)


def test_delete_task_list_asks_for_no_clock() -> None:
    """ARC-04 read back off the constructor: this operation stamps nothing.

    A `Clock` accepted and never read would be a dependency this use case does
    not have, and the whole point of one class per operation is that its
    constructor states exactly what the operation touches.
    """
    parameters = list(inspect.signature(DeleteTaskList.__init__).parameters)

    assert parameters[1:] == ["uow"]
