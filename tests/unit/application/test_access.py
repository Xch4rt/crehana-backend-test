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

Phase 5 adds a third actor to every case below. The assignee of a task may see
it without being able to see the list it lives in (D-01), so `visible_task` now
answers them - and the assertion that matters there is not the returned task but
the *absence* of a read on the list repository, which is why the counting
subclass below exists. Asserting only on the answer would pass against an
implementation that loaded the list and then ignored it, and that statement is
the whole of what the short-circuit saves.
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from taskmanager.application.use_cases.access import (
    owned_task,
    visible_task,
    visible_task_list,
)
from taskmanager.domain.entities.task import Task
from taskmanager.domain.entities.task_list import TaskList
from taskmanager.domain.exceptions import (
    AuthorizationError,
    DomainError,
    TaskListNotFoundError,
    TaskNotFoundError,
)
from taskmanager.domain.value_objects.task_priority import TaskPriority
from tests.unit.application.fakes import FakeTaskListRepository, FakeUnitOfWork

pytestmark = pytest.mark.unit

# Fixed on purpose, exactly as the reference use case's suite fixes them: a
# generated identifier would make every assertion below unfalsifiable, because
# the test could no longer state which actor, or which list, it expects.
NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
ACTOR_ID = UUID("11111111-1111-4111-8111-111111111111")
OTHER_USER_ID = UUID("99999999-9999-4999-8999-999999999999")
TASK_ID = UUID("22222222-2222-4222-8222-222222222222")
TASK_LIST_ID = UUID("33333333-3333-4333-8333-333333333333")
OTHER_LIST_ID = UUID("44444444-4444-4444-8444-444444444444")
# The third role. `OTHER_USER_ID` is the foreign *owner* in these fixtures, so a
# caller who is neither owner nor assignee needs an identifier of their own.
STRANGER_ID = UUID("55555555-5555-4555-8555-555555555555")


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


def _task(
    *,
    task_list_id: UUID = TASK_LIST_ID,
    assignee_id: UUID | None = None,
) -> Task:
    return Task.create(
        task_id=TASK_ID,
        task_list_id=task_list_id,
        title="Share the load-and-authorize rule",
        description="One copy of ADR-008, called by every use case.",
        priority=TaskPriority.HIGH,
        assignee_id=assignee_id,
        now=NOW,
    )


class CountingTaskListRepository(FakeTaskListRepository):
    """A list repository that records every lookup, answered or not.

    D-01's short-circuit is a claim about a statement that is *not* issued: the
    assignee is answered before the parent list is consulted, so their request
    costs one `SELECT` where the owner's costs two. Nothing in the returned task
    can distinguish that from an implementation that read the list, found the
    owner was somebody else, and returned the task anyway on a later branch.

    `held_for_update` alone would not do it either - it records only the locking
    road, and the leg under test is a plain read. So the counter wraps both
    entry points, and the assignee tests assert `reads == []`. The 04-05
    precedent: a counting subclass declared in the test module, rather than a
    field added to the shared fake for one suite's benefit.
    """

    def __init__(self) -> None:
        super().__init__()
        self.reads: list[UUID] = []

    async def get(self, task_list_id: UUID) -> TaskList | None:
        self.reads.append(task_list_id)
        return await super().get(task_list_id)

    async def get_for_update(self, task_list_id: UUID) -> TaskList | None:
        self.reads.append(task_list_id)
        return await super().get_for_update(task_list_id)


def _uow(
    *,
    with_task_list: bool = True,
    owner_id: UUID = ACTOR_ID,
    with_task: bool = True,
    task_belongs_to: UUID = TASK_LIST_ID,
    assignee_id: UUID | None = None,
    task_lists: FakeTaskListRepository | None = None,
) -> FakeUnitOfWork:
    """Assemble a unit of work already holding whatever the case under test needs.

    The entities go into the `stored` dicts directly rather than through
    `add()`, so `added` and `updated` stay empty and any entry a test finds in
    them was written by the code under test - which, for these two guards, must
    be nothing at all.

    `task_lists` is how a test hands in its own `CountingTaskListRepository` and
    keeps a reference to it: `FakeUnitOfWork.task_list_repository` is annotated
    with the base fake, so the counter has to be read off the object the test
    built rather than off the unit of work.
    """
    unit_of_work = FakeUnitOfWork(task_lists=task_lists)
    if with_task_list:
        task_list = _task_list(owner_id=owner_id)
        unit_of_work.task_list_repository.stored[task_list.id] = task_list
    if with_task:
        task = _task(task_list_id=task_belongs_to, assignee_id=assignee_id)
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


async def test_visible_task_list_takes_the_locking_road_when_told_to() -> None:
    """ADR-058 on the list guard, closing this module's last uncovered branch.

    `test_write_paths_hold_what_they_change.py` proves the same thing from the
    use cases that pass the flag; asserted here as well because the guards'
    own specification should exercise every road its subject can take - and
    until plan 05-04 this file measured `visible_task_list` with the flag never
    set, so the branch was covered only by a sibling module.
    """
    async with _uow() as unit_of_work:
        task_list = await visible_task_list(
            unit_of_work, TASK_LIST_ID, ACTOR_ID, for_update=True
        )

        assert task_list.id == TASK_LIST_ID
        assert unit_of_work.task_list_repository.held_for_update == [TASK_LIST_ID]
        assert unit_of_work.task_repository.held_for_update == []


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


async def test_visible_task_answers_its_assignee_without_reading_the_parent_list() -> (
    None
):
    """D-01: the assignee sees the task, and learns nothing about its list.

    The list here belongs to somebody else, so an implementation that consulted
    it would have to refuse - the only way this request can succeed is the
    short-circuit. `reads == []` is the assertion that makes the *cost* claim
    falsifiable as well: a leg that loaded the list and then returned the task
    anyway would satisfy every assertion above this one.
    """
    task_lists = CountingTaskListRepository()
    async with _uow(
        owner_id=OTHER_USER_ID, assignee_id=ACTOR_ID, task_lists=task_lists
    ) as unit_of_work:
        task = await visible_task(unit_of_work, TASK_LIST_ID, TASK_ID, ACTOR_ID)

        assert task.id == TASK_ID
        assert task.assignee_id == ACTOR_ID
        assert task is unit_of_work.task_repository.stored[TASK_ID]
        assert task_lists.reads == []


async def test_the_assignee_leg_holds_the_task_and_still_reads_no_list() -> None:
    """ADR-058 and D-01 together, on the road `ChangeTaskStatus` takes.

    An assignee may advance the state machine (D-03), so their read is a write
    path and passes `for_update=True`. The two properties have to hold at once:
    the task is held, and the list is neither held nor read.
    """
    task_lists = CountingTaskListRepository()
    async with _uow(
        owner_id=OTHER_USER_ID, assignee_id=ACTOR_ID, task_lists=task_lists
    ) as unit_of_work:
        task = await visible_task(
            unit_of_work, TASK_LIST_ID, TASK_ID, ACTOR_ID, for_update=True
        )

        assert task.id == TASK_ID
        assert unit_of_work.task_repository.held_for_update == [TASK_ID]
        assert task_lists.reads == []
        assert task_lists.held_for_update == []


async def test_visible_task_hides_a_task_from_a_stranger_who_is_not_its_assignee() -> (
    None
):
    """The third role: neither owner nor assignee, and therefore nothing at all.

    Somebody *is* assigned here, which is what separates this from the
    pre-existing foreign-list case: the short-circuit exists and this caller
    still does not get through it.
    """
    async with _uow(owner_id=OTHER_USER_ID, assignee_id=OTHER_USER_ID) as unit_of_work:
        with pytest.raises(DomainError) as excinfo:
            await visible_task(unit_of_work, TASK_LIST_ID, TASK_ID, ACTOR_ID)

        error = excinfo.value
        assert isinstance(error, TaskNotFoundError)
        assert not isinstance(error, AuthorizationError)
        assert error.details == {"task_id": str(TASK_ID)}
        assert str(OTHER_USER_ID) not in str(error.details)


async def test_the_wrong_parent_refuses_even_the_tasks_own_assignee() -> None:
    """ADR-050 outranks D-01, and this is where that ordering is pinned.

    The caller is the assignee, so the short-circuit would answer them - but the
    task is filed under another list, and the comparison that refuses a
    wrong-list request comes first. Placed the other way round, an assignee
    could discover that their task lives somewhere other than the list they
    addressed, which is exactly the bit ADR-050 withholds.
    """
    async with _uow(
        task_belongs_to=OTHER_LIST_ID, assignee_id=ACTOR_ID
    ) as unit_of_work:
        with pytest.raises(DomainError) as excinfo:
            await visible_task(unit_of_work, TASK_LIST_ID, TASK_ID, ACTOR_ID)

        error = excinfo.value
        assert isinstance(error, TaskNotFoundError)
        assert not isinstance(error, AuthorizationError)
        assert error.details == {"task_id": str(TASK_ID)}
        assert str(OTHER_LIST_ID) not in str(error.details)


async def test_owned_task_returns_the_task_to_the_owner_of_its_list() -> None:
    """The success leg, identical to `visible_task`'s: only the refusals differ."""
    async with _uow(assignee_id=OTHER_USER_ID) as unit_of_work:
        task = await owned_task(unit_of_work, TASK_LIST_ID, TASK_ID, ACTOR_ID)

        assert task.id == TASK_ID
        assert task is unit_of_work.task_repository.stored[TASK_ID]


async def test_owned_task_refuses_the_assignee_with_the_projects_first_403() -> None:
    """D-03: the assignee can see this task and may not change it.

    The base `DomainError` is caught and the leaf asserted afterwards, the same
    way round as every 404 test here - a `pytest.raises(AuthorizationError)`
    would be satisfied by an implementation that had never considered the 404
    alternative, and the pair is the whole point.

    The message is asserted not to name the owner. A 403 tells a caller that
    they may not; who may is a different question, and answering it would hand
    an enumerating caller a user identifier the request never contained.
    """
    async with _uow(owner_id=OTHER_USER_ID, assignee_id=ACTOR_ID) as unit_of_work:
        with pytest.raises(DomainError) as excinfo:
            await owned_task(unit_of_work, TASK_LIST_ID, TASK_ID, ACTOR_ID)

        error = excinfo.value
        assert isinstance(error, AuthorizationError)
        assert not isinstance(error, TaskNotFoundError)
        assert error.code == "authorization_failed"
        assert error.details == {}
        assert str(OTHER_USER_ID) not in str(error)
        assert str(OTHER_USER_ID) not in str(error.details)


async def test_owned_task_hides_the_task_from_a_stranger() -> None:
    """The third role gets the answer an absent task gets, never the 403."""
    async with _uow(owner_id=OTHER_USER_ID, assignee_id=OTHER_USER_ID) as unit_of_work:
        with pytest.raises(DomainError) as excinfo:
            await owned_task(unit_of_work, TASK_LIST_ID, TASK_ID, ACTOR_ID)

        error = excinfo.value
        assert isinstance(error, TaskNotFoundError)
        assert not isinstance(error, AuthorizationError)
        assert error.details == {"task_id": str(TASK_ID)}


async def test_owned_task_hides_an_absent_task() -> None:
    """Nothing was loaded, so there is no assignee to be forbidden."""
    async with _uow(with_task=False) as unit_of_work:
        with pytest.raises(DomainError) as excinfo:
            await owned_task(unit_of_work, TASK_LIST_ID, TASK_ID, ACTOR_ID)

        error = excinfo.value
        assert isinstance(error, TaskNotFoundError)
        assert not isinstance(error, AuthorizationError)
        assert error.details == {"task_id": str(TASK_ID)}


async def test_owned_task_refuses_a_wrong_parent_before_it_reads_anything() -> None:
    """ADR-050 on the owner-only door, with the same ordering as its sibling.

    The caller owns the list they addressed and is also the task's assignee, so
    both of the ways through this function are open to them - and the wrong
    parent still refuses first, with the task-shaped 404 rather than the 403.
    An implementation that compared the parent later would answer this request
    403, which tells the caller their task exists somewhere.
    """
    task_lists = CountingTaskListRepository()
    async with _uow(
        task_belongs_to=OTHER_LIST_ID, assignee_id=ACTOR_ID, task_lists=task_lists
    ) as unit_of_work:
        with pytest.raises(DomainError) as excinfo:
            await owned_task(unit_of_work, TASK_LIST_ID, TASK_ID, ACTOR_ID)

        error = excinfo.value
        assert isinstance(error, TaskNotFoundError)
        assert not isinstance(error, AuthorizationError)
        assert error.details == {"task_id": str(TASK_ID)}
        assert str(OTHER_LIST_ID) not in str(error.details)
        assert task_lists.reads == []


async def test_owned_task_hides_a_task_whose_parent_list_is_absent() -> None:
    """An orphan is `task_not_found`, exactly as it is through the other door."""
    async with _uow(with_task_list=False) as unit_of_work:
        with pytest.raises(DomainError) as excinfo:
            await owned_task(unit_of_work, TASK_LIST_ID, TASK_ID, ACTOR_ID)

        error = excinfo.value
        assert isinstance(error, TaskNotFoundError)
        assert not isinstance(error, TaskListNotFoundError)
        assert not isinstance(error, AuthorizationError)
        assert error.details == {"task_id": str(TASK_ID)}
        assert str(TASK_LIST_ID) not in str(error.details)


async def test_the_owned_task_403_and_404_are_two_different_answers() -> None:
    """The mirror image of this module's indistinguishability tests.

    Every other comparative test here produces two refusals and asserts they
    match. This one produces two refusals and asserts they *differ* - same
    fixture, same request, one actor who is the assignee and one who is not -
    because "visible but forbidden is a 403 and invisible is a 404" is a claim
    about a pair too. A single-error assertion would pass just as happily
    against an implementation that answered 404 for the assignee as well, which
    is what the project did for the whole of Phase 4.
    """
    async with _uow(owner_id=OTHER_USER_ID, assignee_id=ACTOR_ID) as assignee_uow:
        with pytest.raises(DomainError) as assignee_info:
            await owned_task(assignee_uow, TASK_LIST_ID, TASK_ID, ACTOR_ID)

    async with _uow(owner_id=OTHER_USER_ID, assignee_id=ACTOR_ID) as stranger_uow:
        with pytest.raises(DomainError) as stranger_info:
            await owned_task(stranger_uow, TASK_LIST_ID, TASK_ID, STRANGER_ID)

    forbidden, hidden = assignee_info.value, stranger_info.value
    assert type(forbidden) is not type(hidden)
    assert forbidden.code != hidden.code
    assert isinstance(forbidden, AuthorizationError)
    assert isinstance(hidden, TaskNotFoundError)


async def test_owned_task_holds_the_task_and_never_its_parent_list() -> None:
    """ADR-058 and the lock-ordering rule on the door both write paths now use."""
    task_lists = CountingTaskListRepository()
    async with _uow(task_lists=task_lists) as unit_of_work:
        task = await owned_task(
            unit_of_work, TASK_LIST_ID, TASK_ID, ACTOR_ID, for_update=True
        )

        assert task.id == TASK_ID
        assert unit_of_work.task_repository.held_for_update == [TASK_ID]
        assert task_lists.held_for_update == []
        assert task_lists.reads == [TASK_LIST_ID]


async def test_the_guards_never_end_the_transaction_they_were_handed() -> None:
    """All three helpers read inside a block someone else owns, on every leg.

    A guard that committed, rolled back or opened its own block would take the
    transaction boundary away from the use case, which is exactly what D-17 and
    ARC-08 put there. The counters are read *inside* the block, because
    `FakeUnitOfWork.__aexit__` rolls an uncommitted block back on the way out -
    that is the unit of work's obligation, not the guard's doing.
    """
    async with _uow(assignee_id=OTHER_USER_ID) as unit_of_work:
        await visible_task_list(unit_of_work, TASK_LIST_ID, ACTOR_ID)
        await visible_task(unit_of_work, TASK_LIST_ID, TASK_ID, ACTOR_ID)
        await owned_task(unit_of_work, TASK_LIST_ID, TASK_ID, ACTOR_ID)

        with pytest.raises(DomainError):
            await visible_task(unit_of_work, OTHER_LIST_ID, TASK_ID, ACTOR_ID)
        # The 403 leg closes nothing either: an authorization refusal must leave
        # the transaction exactly as it found it, for the use case to end.
        with pytest.raises(DomainError):
            await owned_task(unit_of_work, TASK_LIST_ID, TASK_ID, OTHER_USER_ID)

        assert unit_of_work.commits == 0
        assert unit_of_work.rollbacks == 0
        assert unit_of_work.task_repository.updated == []
        assert unit_of_work.task_list_repository.updated == []
