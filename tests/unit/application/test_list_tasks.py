"""TASK-06 and TASK-07: the filter, the conjunction, and the number that stays put.

Two properties here are worth more than all the others, and both are written
against a plausible wrong implementation rather than against nothing.

**The conjunction.** Two filters sent together must narrow the answer with
*and*, so the module asks for a pair that matches no row at all and for a pair
that matches exactly one. A single pair would be satisfied by an `or`, and by a
last-argument-wins implementation that quietly drops the first filter - 03-07
learned this at the SQL layer, and the same case is repeated here one layer up.

**The statistics.** `test_the_filter_never_moves_the_statistics` runs the same
list twice, filtered and unfiltered, and requires the three counters to be
identical while the item counts differ. Asserting the numbers of one filtered
call alone would pass against a use case that handed the filter to the aggregate
too - which is the single most likely "improvement" anyone will make to
`list.py`.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from taskmanager.application.dto.commands import ListTasksCommand
from taskmanager.application.use_cases.tasks.list import ListTasks
from taskmanager.domain.entities.task import Task
from taskmanager.domain.entities.task_list import TaskList
from taskmanager.domain.exceptions import (
    AuthorizationError,
    DomainError,
    TaskListNotFoundError,
)
from taskmanager.domain.value_objects.completion import CompletionStats
from taskmanager.domain.value_objects.task_priority import TaskPriority
from taskmanager.domain.value_objects.task_status import TaskStatus
from tests.unit.application.fakes import (
    FakeTaskListRepository,
    FakeTaskRepository,
    FakeUnitOfWork,
)

pytestmark = pytest.mark.unit

# Fixed on purpose. A generated identifier or a real clock reading would make
# every assertion below unfalsifiable: the test could no longer state which
# moment, or which actor, it expects.
NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
LATER = NOW + timedelta(hours=3)
LATEST = NOW + timedelta(hours=6)
ACTOR_ID = UUID("11111111-1111-4111-8111-111111111111")
OTHER_USER_ID = UUID("99999999-9999-4999-8999-999999999999")
TASK_LIST_ID = UUID("33333333-3333-4333-8333-333333333333")
EMPTY_LIST_ID = UUID("44444444-4444-4444-8444-444444444444")
# Ordered by their hex so the `(created_at, id)` tie-break has a known answer.
A_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
B_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
C_ID = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
D_ID = UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")
E_ID = UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")

# Five tasks over two statuses and two priorities, **seeded in an order that is
# not the answer**: `C` is created first and stored last, so an implementation
# handing back insertion order fails the first test below rather than passing it
# by coincidence. `A` and `B` share an instant, which is the case a timestamp
# alone cannot order - the clock is read once per request, so two tasks created
# in one call really do collide - and `D` and `E` share the next one. Exactly one
# task is completed, which fixes the percentage at 20.0 whatever the filter says.
FIXTURE: tuple[tuple[UUID, datetime, TaskStatus, TaskPriority], ...] = (
    (E_ID, LATEST, TaskStatus.PENDING, TaskPriority.HIGH),
    (B_ID, LATER, TaskStatus.PENDING, TaskPriority.LOW),
    (D_ID, LATEST, TaskStatus.COMPLETED, TaskPriority.LOW),
    (A_ID, LATER, TaskStatus.PENDING, TaskPriority.HIGH),
    (C_ID, NOW, TaskStatus.IN_PROGRESS, TaskPriority.HIGH),
)
IN_ORDER = (C_ID, A_ID, B_ID, D_ID, E_ID)
TOTAL_TASKS = len(FIXTURE)
COMPLETED_TASKS = 1
COMPLETION_PERCENTAGE = 20.0


class _CountingTaskRepository(FakeTaskRepository):
    """The sibling fake, plus a tally of the two queries this use case makes.

    Subclassed rather than added to `fakes.py`: the counters are this module's
    instrument, not a property of the port, and a counter on the shared fake
    would invite other tests to assert on a number nothing else maintains.
    """

    def __init__(self) -> None:
        super().__init__()
        self.listings = 0
        self.stats_queries = 0

    async def list_for_task_list(
        self,
        task_list_id: UUID,
        *,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
    ) -> list[Task]:
        self.listings += 1
        return list(
            await super().list_for_task_list(
                task_list_id, status=status, priority=priority
            )
        )

    async def completion_stats(self, task_list_id: UUID) -> CompletionStats:
        self.stats_queries += 1
        return await super().completion_stats(task_list_id)


def _uow(*, owner_id: UUID = ACTOR_ID) -> FakeUnitOfWork:
    """Assemble a unit of work holding both lists and the five fixture tasks.

    Entities go into `stored` directly rather than through `add()`, so the
    `added` and `updated` records stay empty - nothing in this module writes
    anything, and the assertions say so.
    """
    counting = _CountingTaskRepository()
    unit_of_work = FakeUnitOfWork(
        tasks=counting, task_lists=FakeTaskListRepository(counting)
    )
    for task_list_id in (TASK_LIST_ID, EMPTY_LIST_ID):
        task_list = TaskList.create(
            task_list_id=task_list_id,
            owner_id=owner_id,
            name=f"List {task_list_id}",
            now=NOW,
        )
        unit_of_work.task_list_repository.stored[task_list.id] = task_list
    for task_id, created_at, status, priority in FIXTURE:
        task = Task.create(
            task_id=task_id,
            task_list_id=TASK_LIST_ID,
            title=f"Task {task_id}",
            priority=priority,
            now=created_at,
        )
        if status is not TaskStatus.PENDING:
            task.change_status(status, now=created_at)
        unit_of_work.task_repository.stored[task.id] = task
    return unit_of_work


def _counter(unit_of_work: FakeUnitOfWork) -> _CountingTaskRepository:
    """Narrow the unit of work's task repository back to the counting fake."""
    counting = unit_of_work.task_repository
    assert isinstance(counting, _CountingTaskRepository)
    return counting


def _command(
    *,
    status: TaskStatus | None = None,
    priority: TaskPriority | None = None,
    task_list_id: UUID = TASK_LIST_ID,
    actor_id: UUID = ACTOR_ID,
) -> ListTasksCommand:
    """The single construction site every test below goes through."""
    return ListTasksCommand(
        actor_id=actor_id,
        task_list_id=task_list_id,
        status=status,
        priority=priority,
    )


async def test_list_tasks_orders_by_created_at_then_id() -> None:
    """D-13: `created_at` decides, and `id` breaks the tie it leaves."""
    unit_of_work = _uow()

    result = await ListTasks(unit_of_work).execute(_command())

    assert [item.id for item in result.items] == list(IN_ORDER)
    assert isinstance(result.items, tuple)


async def test_the_status_filter_narrows_the_items_on_its_own() -> None:
    """TASK-06, one filter at a time: only the pending tasks come back."""
    unit_of_work = _uow()

    result = await ListTasks(unit_of_work).execute(_command(status=TaskStatus.PENDING))

    assert [item.id for item in result.items] == [A_ID, B_ID, E_ID]
    assert all(item.status is TaskStatus.PENDING for item in result.items)


async def test_the_priority_filter_narrows_the_items_on_its_own() -> None:
    """The same claim from the other side, so neither filter can be the default."""
    unit_of_work = _uow()

    result = await ListTasks(unit_of_work).execute(_command(priority=TaskPriority.LOW))

    assert [item.id for item in result.items] == [B_ID, D_ID]
    assert all(item.priority is TaskPriority.LOW for item in result.items)


async def test_both_filters_apply_as_a_conjunction_with_no_matching_row() -> None:
    """The pair that must answer nothing: no task is both completed and high.

    An `or` implementation answers four rows here, and a last-argument-wins one
    answers whichever single filter it kept - so this is the case that fails
    while both single-filter tests above still pass.
    """
    unit_of_work = _uow()

    result = await ListTasks(unit_of_work).execute(
        _command(status=TaskStatus.COMPLETED, priority=TaskPriority.HIGH)
    )

    assert result.items == ()


async def test_both_filters_apply_as_a_conjunction_with_exactly_one_row() -> None:
    """The other half of the conjunction: one task is completed *and* low.

    Asserting the empty answer alone would be satisfied by an implementation
    that narrowed to nothing whenever two filters arrived, so the pair that does
    match is pinned beside it.
    """
    unit_of_work = _uow()

    result = await ListTasks(unit_of_work).execute(
        _command(status=TaskStatus.COMPLETED, priority=TaskPriority.LOW)
    )

    assert [item.id for item in result.items] == [D_ID]


async def test_the_filter_never_moves_the_statistics() -> None:
    """TASK-07 and roadmap SC-4, asserted as the equality it actually is.

    The same list is read twice, and the three counters have to match while the
    item counts do not. A use case that handed the filter to the aggregate as
    well would answer `3 / 0 / 0.0` on the filtered call - right-looking numbers
    describing a list that does not exist.
    """
    unfiltered = await ListTasks(_uow()).execute(_command())
    filtered = await ListTasks(_uow()).execute(_command(status=TaskStatus.PENDING))

    assert len(filtered.items) != len(unfiltered.items)
    assert filtered.total_tasks == unfiltered.total_tasks == TOTAL_TASKS
    assert filtered.completed_tasks == unfiltered.completed_tasks == COMPLETED_TASKS
    assert (
        filtered.completion_percentage
        == unfiltered.completion_percentage
        == COMPLETION_PERCENTAGE
    )


async def test_an_empty_list_reports_zeroes_rather_than_nothing() -> None:
    """A list with no tasks is an ordinary list: an empty tuple and three numbers.

    A use case returning `None` for the counters here would push an `if` into
    every caller, and the first one to forget it would answer 500 to a new
    list's very first read.
    """
    unit_of_work = _uow()

    result = await ListTasks(unit_of_work).execute(_command(task_list_id=EMPTY_LIST_ID))

    assert result.items == ()
    assert result.total_tasks == 0
    assert result.completed_tasks == 0
    assert result.completion_percentage == 0.0


async def test_list_tasks_hides_a_list_not_owned_by_the_actor() -> None:
    """D-04, and the refusal lands before a single task is read.

    The listing counter is what makes the second half of that claim real: an
    implementation that gathered the rows and then authorised would raise the
    very same error, having already read tasks the caller may not see.
    """
    unit_of_work = _uow(owner_id=OTHER_USER_ID)

    with pytest.raises(DomainError) as excinfo:
        await ListTasks(unit_of_work).execute(_command())

    error = excinfo.value
    assert isinstance(error, TaskListNotFoundError)
    assert not isinstance(error, AuthorizationError)
    assert error.details == {"task_list_id": str(TASK_LIST_ID)}
    assert _counter(unit_of_work).listings == 0
    assert _counter(unit_of_work).stats_queries == 0
    assert unit_of_work.commits == 0
    assert unit_of_work.rollbacks == 1


async def test_list_tasks_writes_nothing_and_closes_its_transaction() -> None:
    """The read-path convention, and the query budget beside it.

    One listing and one aggregate, whatever the filter says: D-09's envelope
    costs two statements, and a third would mean the counters had been gathered
    some other way.
    """
    unit_of_work = _uow()

    await ListTasks(unit_of_work).execute(_command(priority=TaskPriority.HIGH))

    assert _counter(unit_of_work).listings == 1
    assert _counter(unit_of_work).stats_queries == 1
    assert unit_of_work.task_repository.updated == []
    assert unit_of_work.commits == 0
    assert unit_of_work.rollbacks == 1
