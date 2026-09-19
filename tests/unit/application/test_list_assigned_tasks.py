"""D-02: the flat collection that makes a received assignment findable.

The claim with teeth is the one about *whose* tasks come back. This use case
has no `access.py` guard and needs none, because the query it issues can only
return rows already assigned to the caller - but that argument holds only while
the argument to the query is the token's subject. So the fixture below seeds a
task assigned to somebody else, under a list the actor does not own, and
requires it to be absent from the answer (T-5-11).

The second claim is that the collection spans lists. An implementation that
reached for `list_for_task_list` and filtered in Python would answer correctly
for a single-list fixture and wrongly for everyone else, so both tasks in the
happy path live under different parents.
"""

import inspect
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from taskmanager.application.dto.commands import ListAssignedTasksCommand
from taskmanager.application.dto.results import TaskResult
from taskmanager.application.use_cases.tasks.list_assigned import ListAssignedTasks
from taskmanager.domain.entities.task import Task
from tests.unit.application.fakes import FakeUnitOfWork

pytestmark = pytest.mark.unit

# Fixed on purpose. A generated identifier or a real clock reading would make
# every assertion below unfalsifiable: the test could no longer state which
# moment, or which actor, it expects.
NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
LATER = NOW + timedelta(hours=3)
ACTOR_ID = UUID("11111111-1111-4111-8111-111111111111")
OTHER_USER_ID = UUID("99999999-9999-4999-8999-999999999999")
FIRST_LIST_ID = UUID("33333333-3333-4333-8333-333333333333")
SECOND_LIST_ID = UUID("44444444-4444-4444-8444-444444444444")
# Ordered by their hex so the `(created_at, id)` tie-break has a known answer.
A_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
B_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
C_ID = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")


def _add_task(
    unit_of_work: FakeUnitOfWork,
    task_id: UUID,
    *,
    task_list_id: UUID = FIRST_LIST_ID,
    assignee_id: UUID | None = ACTOR_ID,
    created_at: datetime = NOW,
    title: str = "A task",
) -> None:
    """Place one task in `stored` directly, so `updated` stays the use case's."""
    task = Task.create(
        task_id=task_id,
        task_list_id=task_list_id,
        title=title,
        assignee_id=assignee_id,
        now=created_at,
    )
    unit_of_work.task_repository.stored[task.id] = task


def _command(*, actor_id: UUID = ACTOR_ID) -> ListAssignedTasksCommand:
    """The single construction site every test below goes through."""
    return ListAssignedTasksCommand(actor_id=actor_id)


async def test_assigned_tasks_span_every_list_the_actor_was_assigned_in() -> None:
    """D-02: the collection is flat, so a second parent list changes nothing.

    Each entry still carries its `task_list_id`, which is what lets a client
    rebuild the nested URL the task is actually addressed through (D-01).
    """
    unit_of_work = FakeUnitOfWork()
    _add_task(unit_of_work, A_ID, task_list_id=FIRST_LIST_ID, title="Here")
    _add_task(unit_of_work, B_ID, task_list_id=SECOND_LIST_ID, title="And there")

    results = await ListAssignedTasks(unit_of_work).execute(_command())

    assert [result.id for result in results] == [A_ID, B_ID]
    assert {result.task_list_id for result in results} == {
        FIRST_LIST_ID,
        SECOND_LIST_ID,
    }
    assert all(isinstance(result, TaskResult) for result in results)


async def test_another_users_assignment_is_never_in_the_answer() -> None:
    """T-5-11: the query is the filter, and its argument is the token's subject.

    The foreign task sits under a list the actor has no relationship with, so an
    implementation that widened the filter - or that took an id from the request
    instead of from the actor - hands back a row the caller may not see at all.
    """
    unit_of_work = FakeUnitOfWork()
    _add_task(unit_of_work, A_ID, title="Mine")
    _add_task(
        unit_of_work,
        B_ID,
        task_list_id=SECOND_LIST_ID,
        assignee_id=OTHER_USER_ID,
        title="Theirs",
    )

    results = await ListAssignedTasks(unit_of_work).execute(_command())

    assert [result.id for result in results] == [A_ID]
    assert all(result.assignee_id == ACTOR_ID for result in results)


async def test_an_unassigned_task_is_not_an_assignment() -> None:
    """The third row a wrong filter would let through: nobody's task at all."""
    unit_of_work = FakeUnitOfWork()
    _add_task(unit_of_work, A_ID, title="Mine")
    _add_task(unit_of_work, B_ID, assignee_id=None, title="Nobody's")

    results = await ListAssignedTasks(unit_of_work).execute(_command())

    assert [result.id for result in results] == [A_ID]


async def test_assigned_tasks_order_by_created_at_then_id() -> None:
    """D-02's order: `created_at` decides, and `id` breaks the tie it leaves.

    `C` is seeded last and created first, so insertion order is not the answer;
    `A` and `B` share an instant, which is the case a timestamp alone cannot
    order - the clock is read once per request, so two tasks made in one call
    really do collide.
    """
    unit_of_work = FakeUnitOfWork()
    _add_task(unit_of_work, A_ID, created_at=LATER, title="Alpha")
    _add_task(unit_of_work, B_ID, created_at=LATER, title="Beta")
    _add_task(unit_of_work, C_ID, created_at=NOW, title="Gamma")

    results = await ListAssignedTasks(unit_of_work).execute(_command())

    assert [result.id for result in results] == [C_ID, A_ID, B_ID]
    assert [result.title for result in results] == ["Gamma", "Alpha", "Beta"]


async def test_a_caller_with_no_assignments_gets_an_empty_tuple() -> None:
    """The empty collection is an empty answer, never `None`.

    This is the ordinary state of a brand new account, so the branch a caller
    would forget is the one every first request takes.
    """
    unit_of_work = FakeUnitOfWork()
    _add_task(unit_of_work, A_ID, assignee_id=OTHER_USER_ID, title="Theirs")

    results = await ListAssignedTasks(unit_of_work).execute(_command())

    assert results == ()
    assert isinstance(results, tuple)


async def test_assigned_tasks_answer_with_a_tuple_and_commit_nothing() -> None:
    """The answer is immutable, and the read transaction was closed unwritten.

    `commits == 0` alone is equally true of a transaction nobody ever closed,
    so the rollback is asserted beside it - the sibling suites' convention.
    """
    unit_of_work = FakeUnitOfWork()
    _add_task(unit_of_work, A_ID)

    results = await ListAssignedTasks(unit_of_work).execute(_command())

    assert isinstance(results, tuple)
    assert unit_of_work.commits == 0
    assert unit_of_work.rollbacks == 1


def test_list_assigned_tasks_asks_for_no_clock() -> None:
    """ARC-04 read back off the constructor: a read stamps nothing."""
    parameters = list(inspect.signature(ListAssignedTasks.__init__).parameters)

    assert parameters[1:] == ["uow"]
