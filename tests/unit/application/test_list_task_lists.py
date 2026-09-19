"""LIST-03: the whole collection, its counters, and the N+1 that must not happen.

The last test in this module is the one with teeth. Every other assertion here
would be satisfied just as well by an implementation that read the lists and
then asked for one list's statistics per row - the values would be right and the
endpoint would degrade linearly with the size of the collection. So the task
repository this module injects counts the per-list statistics query, and the
collection is required to have called it zero times. Plan 04-10 counts real
statements over HTTP; this is the same claim, one layer down and one millisecond
long, so a regression fails in the layer it was written in.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from taskmanager.application.dto.commands import ListTaskListsCommand
from taskmanager.application.use_cases.task_lists.list import ListTaskLists
from taskmanager.domain.entities.task import Task
from taskmanager.domain.entities.task_list import TaskList
from taskmanager.domain.value_objects.completion import CompletionStats
from taskmanager.domain.value_objects.task_status import TaskStatus
from tests.unit.application.fakes import (
    FakeTaskListRepository,
    FakeTaskRepository,
    FakeUnitOfWork,
)

# Fixed on purpose. A generated identifier or a real clock reading would make
# every assertion below unfalsifiable: the test could no longer state which
# moment, or which actor, it expects.
NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
LATER = NOW + timedelta(hours=3)
ACTOR_ID = UUID("11111111-1111-4111-8111-111111111111")
OTHER_USER_ID = UUID("99999999-9999-4999-8999-999999999999")
# Ordered by their hex so the `(created_at, id)` tie-break has a known answer.
A_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
B_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
C_ID = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
FOREIGN_ID = UUID("ffffffff-ffff-4fff-8fff-ffffffffffff")
TASK_IDS = (
    UUID("22222222-2222-4222-8222-222222222221"),
    UUID("22222222-2222-4222-8222-222222222222"),
)


class _CountingTaskRepository(FakeTaskRepository):
    """The sibling fake, plus a tally of per-list statistics queries.

    Subclassed rather than added to `fakes.py`: the counter is this module's
    instrument, not a property of the port, and a counter on the shared fake
    would invite other tests to assert on a number nothing else maintains.
    """

    def __init__(self) -> None:
        super().__init__()
        self.completion_stats_calls = 0

    async def completion_stats(self, task_list_id: UUID) -> CompletionStats:
        self.completion_stats_calls += 1
        return await super().completion_stats(task_list_id)


def _uow() -> FakeUnitOfWork:
    """An empty unit of work whose task repository counts what it is asked.

    The list repository is given a *second*, uncounted task repository sharing
    the very same `stored` dictionary, so the grouped query still computes real
    statistics from the real tasks while the counter measures only the calls a
    use case made on its own account. Handing it the counted one instead would
    make the tally include the fake's own bookkeeping, and the N+1 assertion
    would measure nothing.
    """
    counting = _CountingTaskRepository()
    grouped = FakeTaskRepository()
    grouped.stored = counting.stored
    return FakeUnitOfWork(tasks=counting, task_lists=FakeTaskListRepository(grouped))


def _add_list(
    unit_of_work: FakeUnitOfWork,
    task_list_id: UUID,
    *,
    owner_id: UUID = ACTOR_ID,
    created_at: datetime = NOW,
    name: str = "A list",
) -> None:
    """Place one list in `stored` directly, so `added` stays the use case's."""
    task_list = TaskList.create(
        task_list_id=task_list_id,
        owner_id=owner_id,
        name=name,
        now=created_at,
    )
    unit_of_work.task_list_repository.stored[task_list.id] = task_list


def _add_task(
    unit_of_work: FakeUnitOfWork,
    task_id: UUID,
    task_list_id: UUID,
    *,
    completed: bool = False,
) -> None:
    """Place one task in `stored`, optionally already finished."""
    task = Task.create(
        task_id=task_id,
        task_list_id=task_list_id,
        title="A task",
        now=NOW,
    )
    if completed:
        task.change_status(TaskStatus.COMPLETED, now=LATER)
    unit_of_work.task_repository.stored[task.id] = task


def _command(*, actor_id: UUID = ACTOR_ID) -> ListTaskListsCommand:
    """The single construction site every test below goes through."""
    return ListTaskListsCommand(actor_id=actor_id)


async def test_list_task_lists_orders_by_created_at_then_id() -> None:
    """D-13: `created_at` decides, and `id` breaks the tie it leaves.

    `C` is seeded last and created first, so insertion order is not the answer;
    `A` and `B` share an instant, which is the case a timestamp alone cannot
    order - and the clock is read once per request, so two lists made in one
    call really do collide.
    """
    unit_of_work = _uow()
    _add_list(unit_of_work, A_ID, created_at=LATER, name="Alpha")
    _add_list(unit_of_work, B_ID, created_at=LATER, name="Beta")
    _add_list(unit_of_work, C_ID, created_at=NOW, name="Gamma")

    results = await ListTaskLists(unit_of_work).execute(_command())

    assert [result.id for result in results] == [C_ID, A_ID, B_ID]
    assert [result.name for result in results] == ["Gamma", "Alpha", "Beta"]


async def test_list_task_lists_never_shows_another_owners_list() -> None:
    """T-4-23: the query is scoped by owner, so a foreign list is simply absent."""
    unit_of_work = _uow()
    _add_list(unit_of_work, A_ID, name="Mine")
    _add_list(unit_of_work, FOREIGN_ID, owner_id=OTHER_USER_ID, name="Theirs")

    results = await ListTaskLists(unit_of_work).execute(_command())

    assert [result.id for result in results] == [A_ID]
    assert all(result.owner_id == ACTOR_ID for result in results)


async def test_a_list_with_no_tasks_reports_zero_rather_than_nothing() -> None:
    """An empty list is an ordinary list: three numbers, none of them missing."""
    unit_of_work = _uow()
    _add_list(unit_of_work, A_ID)

    results = await ListTaskLists(unit_of_work).execute(_command())

    assert len(results) == 1
    assert results[0].total_tasks == 0
    assert results[0].completed_tasks == 0
    assert results[0].completion_percentage == 0.0


async def test_an_actor_with_no_lists_gets_an_empty_tuple() -> None:
    """The empty collection is an empty answer, never `None`.

    A use case returning `None` here would push an `if results is None` branch
    into every caller, and the first one to forget it would answer 500 to a new
    user's very first request.
    """
    results = await ListTaskLists(_uow()).execute(_command())

    assert results == ()
    assert isinstance(results, tuple)


async def test_list_task_lists_answers_with_a_tuple_and_commits_nothing() -> None:
    """The answer is immutable, and the read transaction was closed unwritten."""
    unit_of_work = _uow()
    _add_list(unit_of_work, A_ID)

    results = await ListTaskLists(unit_of_work).execute(_command())

    assert isinstance(results, tuple)
    assert unit_of_work.commits == 0
    assert unit_of_work.rollbacks == 1


async def test_the_collection_never_asks_for_one_lists_statistics() -> None:
    """LIST-03 as a count, not as a claim (T-4-24).

    Two lists, one of them half done, and the counters still have to be right -
    an implementation that simply never gathered them would pass a bare
    "called zero times" assertion while answering zeroes to every client.
    """
    unit_of_work = _uow()
    _add_list(unit_of_work, A_ID, name="Alpha")
    _add_list(unit_of_work, B_ID, name="Beta")
    _add_task(unit_of_work, TASK_IDS[0], A_ID, completed=True)
    _add_task(unit_of_work, TASK_IDS[1], A_ID)

    results = await ListTaskLists(unit_of_work).execute(_command())

    assert len(results) == 2
    assert (results[0].total_tasks, results[0].completed_tasks) == (2, 1)
    assert results[0].completion_percentage == 50.0
    assert results[1].completion_percentage == 0.0
    counted = unit_of_work.task_repository
    assert isinstance(counted, _CountingTaskRepository)
    assert counted.completion_stats_calls == 0
