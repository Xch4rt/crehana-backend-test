"""Specification for the single copy of ADR-008's visibility rule.

Eleven use cases will call `visible_task_list` or `visible_task`, so what is
pinned here is not one endpoint's behaviour but the rule itself: an actor who
may not see a resource gets the answer an absent resource gets, and a task
addressed under the wrong list is one of those cases (D-14).

Two properties are asserted by comparing *two* refusals rather than by
inspecting one. "A foreign list answers exactly like an absent one" and "a
wrong-list task answers exactly like an absent one" are claims about a pair of
error bodies, so each is tested by producing both and asserting the type, the
`code` and the `details` all match. A single-error assertion would still pass
against an implementation that leaked existence through a different code.

Every failure test catches the base `DomainError` and then asserts which leaf
came out, the shape `test_change_task_status.py` established: catching
`TaskNotFoundError` directly would pass just as happily against an
implementation that never considered the 403 question, which is the one thing
these tests exist to make falsifiable.
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from taskmanager.application.use_cases.access import visible_task, visible_task_list
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

# Fixed on purpose, exactly as the reference use case's suite fixes them: a
# generated identifier would make every assertion below unfalsifiable, because
# the test could no longer state which actor, or which list, it expects.
NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
ACTOR_ID = UUID("11111111-1111-4111-8111-111111111111")
OTHER_USER_ID = UUID("99999999-9999-4999-8999-999999999999")
TASK_ID = UUID("22222222-2222-4222-8222-222222222222")
TASK_LIST_ID = UUID("33333333-3333-4333-8333-333333333333")
OTHER_LIST_ID = UUID("44444444-4444-4444-8444-444444444444")


def _task_list(
    *,
    owner_id: UUID = ACTOR_ID,
    task_list_id: UUID = TASK_LIST_ID,
) -> TaskList:
    return TaskList.create(
        task_list_id=task_list_id,
        owner_id=owner_id,
        name="Phase 4",
        now=NOW,
    )


def _task(*, task_list_id: UUID = TASK_LIST_ID) -> Task:
    return Task.create(
        task_id=TASK_ID,
        task_list_id=task_list_id,
        title="Share the load-and-authorize rule",
        description="One copy of ADR-008, called by every use case.",
        priority=TaskPriority.HIGH,
        now=NOW,
    )


def _uow(
    *,
    with_task_list: bool = True,
    owner_id: UUID = ACTOR_ID,
    with_task: bool = True,
    task_belongs_to: UUID = TASK_LIST_ID,
) -> FakeUnitOfWork:
    """Assemble a unit of work already holding whatever the case under test needs.

    The entities go into the `stored` dicts directly rather than through
    `add()`, so `added` and `updated` stay empty and any entry a test finds in
    them was written by the code under test - which, for these two guards, must
    be nothing at all.
    """
    unit_of_work = FakeUnitOfWork()
    if with_task_list:
        task_list = _task_list(owner_id=owner_id)
        unit_of_work.task_list_repository.stored[task_list.id] = task_list
    if with_task:
        task = _task(task_list_id=task_belongs_to)
        unit_of_work.task_repository.stored[task.id] = task
    return unit_of_work


async def test_visible_task_list_returns_the_list_to_its_owner() -> None:
    """The success leg: the owner gets the entity itself, not a copy of it."""
    async with _uow() as unit_of_work:
        task_list = await visible_task_list(unit_of_work, TASK_LIST_ID, ACTOR_ID)

        assert task_list.id == TASK_LIST_ID
        assert task_list.owner_id == ACTOR_ID
        assert task_list is unit_of_work.task_list_repository.stored[TASK_LIST_ID]


async def test_visible_task_list_hides_an_absent_list() -> None:
    """An absent list is a 404 carrying only the id the caller supplied."""
    async with _uow(with_task_list=False) as unit_of_work:
        with pytest.raises(DomainError) as excinfo:
            await visible_task_list(unit_of_work, TASK_LIST_ID, ACTOR_ID)

        error = excinfo.value
        assert isinstance(error, TaskListNotFoundError)
        assert not isinstance(error, AuthorizationError)
        assert error.details == {"task_list_id": str(TASK_LIST_ID)}


async def test_a_foreign_list_answers_exactly_as_an_absent_one() -> None:
    """D-04 and ADR-008: the two refusals are indistinguishable to the caller.

    Both are produced here and compared - type, `code` and `details` - because
    "answers exactly like an absent one" is a claim about a pair of error
    bodies. Asserting only on the foreign case would pass against an
    implementation that answered it with a different code.
    """
    async with _uow(with_task_list=False) as absent_uow:
        with pytest.raises(DomainError) as absent_info:
            await visible_task_list(absent_uow, TASK_LIST_ID, ACTOR_ID)

    async with _uow(owner_id=OTHER_USER_ID) as foreign_uow:
        with pytest.raises(DomainError) as foreign_info:
            await visible_task_list(foreign_uow, TASK_LIST_ID, ACTOR_ID)

    absent, foreign = absent_info.value, foreign_info.value
    assert type(foreign) is type(absent)
    assert foreign.code == absent.code
    assert foreign.details == absent.details
    assert str(OTHER_USER_ID) not in str(foreign.details)


async def test_visible_task_returns_the_task_to_the_owner_of_its_list() -> None:
    """The success leg: the task is in the addressed list, and the list is owned."""
    async with _uow() as unit_of_work:
        task = await visible_task(unit_of_work, TASK_LIST_ID, TASK_ID, ACTOR_ID)

        assert task.id == TASK_ID
        assert task.task_list_id == TASK_LIST_ID
        assert task is unit_of_work.task_repository.stored[TASK_ID]


async def test_visible_task_hides_an_absent_task() -> None:
    """An absent task is a 404 carrying only the task id."""
    async with _uow(with_task=False) as unit_of_work:
        with pytest.raises(DomainError) as excinfo:
            await visible_task(unit_of_work, TASK_LIST_ID, TASK_ID, ACTOR_ID)

        error = excinfo.value
        assert isinstance(error, TaskNotFoundError)
        assert not isinstance(error, AuthorizationError)
        assert error.details == {"task_id": str(TASK_ID)}


async def test_a_task_under_the_wrong_list_answers_exactly_as_an_absent_one() -> None:
    """D-14: the task exists, but not here - and the caller cannot tell it exists.

    The list in the request is the actor's own, so the refusal cannot be
    explained away as an ownership failure; the only thing wrong is that the
    task lives somewhere else. Both refusals are produced and compared, for the
    reason the sibling list test gives.
    """
    async with _uow(with_task=False) as absent_uow:
        with pytest.raises(DomainError) as absent_info:
            await visible_task(absent_uow, TASK_LIST_ID, TASK_ID, ACTOR_ID)

    async with _uow(task_belongs_to=OTHER_LIST_ID) as wrong_list_uow:
        with pytest.raises(DomainError) as wrong_list_info:
            await visible_task(wrong_list_uow, TASK_LIST_ID, TASK_ID, ACTOR_ID)

    absent, wrong_list = absent_info.value, wrong_list_info.value
    assert isinstance(wrong_list, TaskNotFoundError)
    assert type(wrong_list) is type(absent)
    assert wrong_list.code == absent.code
    assert wrong_list.details == absent.details
    assert str(OTHER_LIST_ID) not in str(wrong_list.details)


async def test_visible_task_hides_a_task_whose_parent_list_is_absent() -> None:
    """An orphaned task is `task_not_found`, never `task_list_not_found`.

    The asymmetry is the point: `task_list_not_found` differs in code *and*
    carries an identifier for a resource the caller may not be entitled to know
    anything about, so it would distinguish precisely the two cases ADR-008
    requires to be indistinguishable.
    """
    async with _uow(with_task_list=False) as unit_of_work:
        with pytest.raises(DomainError) as excinfo:
            await visible_task(unit_of_work, TASK_LIST_ID, TASK_ID, ACTOR_ID)

        error = excinfo.value
        assert isinstance(error, TaskNotFoundError)
        assert not isinstance(error, TaskListNotFoundError)
        assert not isinstance(error, AuthorizationError)
        assert error.details == {"task_id": str(TASK_ID)}
        assert str(TASK_LIST_ID) not in str(error.details)


async def test_visible_task_hides_a_task_on_a_list_the_actor_does_not_own() -> None:
    """The foreign-parent leg answers as the absent-task leg does, not as a 403."""
    async with _uow(owner_id=OTHER_USER_ID) as unit_of_work:
        with pytest.raises(DomainError) as excinfo:
            await visible_task(unit_of_work, TASK_LIST_ID, TASK_ID, ACTOR_ID)

        error = excinfo.value
        assert isinstance(error, TaskNotFoundError)
        assert not isinstance(error, TaskListNotFoundError)
        assert not isinstance(error, AuthorizationError)
        assert error.details == {"task_id": str(TASK_ID)}


async def test_the_guards_never_end_the_transaction_they_were_handed() -> None:
    """Both helpers read inside a block someone else owns, on every leg.

    A guard that committed, rolled back or opened its own block would take the
    transaction boundary away from the use case, which is exactly what D-17 and
    ARC-08 put there. The counters are read *inside* the block, because
    `FakeUnitOfWork.__aexit__` rolls an uncommitted block back on the way out -
    that is the unit of work's obligation, not the guard's doing.
    """
    async with _uow() as unit_of_work:
        await visible_task_list(unit_of_work, TASK_LIST_ID, ACTOR_ID)
        await visible_task(unit_of_work, TASK_LIST_ID, TASK_ID, ACTOR_ID)

        with pytest.raises(DomainError):
            await visible_task(unit_of_work, OTHER_LIST_ID, TASK_ID, ACTOR_ID)

        assert unit_of_work.commits == 0
        assert unit_of_work.rollbacks == 0
        assert unit_of_work.task_repository.updated == []
        assert unit_of_work.task_list_repository.updated == []
