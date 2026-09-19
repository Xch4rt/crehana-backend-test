"""ADR-058 at the application layer: which road each use case takes to its entity.

The Phase 4 review's CR-01 was a lost update: every mutating use case loaded
through `get`, validated against that copy and wrote the whole entity back, so
two overlapping requests persisted a status transition the state machine
forbids. The fix is a second read on the ports, `get_for_update`, and the rule
that a *write* path loads through it while a *read* path never does.

A dictionary has no second writer to keep out, so nothing here proves the
waiting - `tests/integration/test_concurrent_writes.py` does that, on two real
connections. What this module pins is the half a fake *can* see, and both
directions of it:

* a write path that goes back to `get` leaves `held_for_update` empty, and fails;
* a read path that starts taking `get_for_update` fills it, and fails - a GET
  that waits on somebody else's PATCH is a regression too, and it is one no
  single-connection test would ever notice.

The parent list of a task is asserted *not* held on the task write paths, because
that is the lock-ordering rule `access.py` records: a task's writer never holds a
list, so a list deletion can never end up waiting on a writer that waits on it.
"""

from datetime import UTC, datetime
from uuid import UUID

from taskmanager.application.dto.commands import (
    ChangeTaskStatusCommand,
    DeleteTaskCommand,
    DeleteTaskListCommand,
    GetTaskCommand,
    GetTaskListCommand,
    ListTasksCommand,
    UpdateTaskCommand,
    UpdateTaskListCommand,
)
from taskmanager.application.use_cases.access import visible_task, visible_task_list
from taskmanager.application.use_cases.task_lists.delete import DeleteTaskList
from taskmanager.application.use_cases.task_lists.get import GetTaskList
from taskmanager.application.use_cases.task_lists.update import UpdateTaskList
from taskmanager.application.use_cases.tasks.change_task_status import (
    ChangeTaskStatus,
)
from taskmanager.application.use_cases.tasks.delete import DeleteTask
from taskmanager.application.use_cases.tasks.get import GetTask
from taskmanager.application.use_cases.tasks.list import ListTasks
from taskmanager.application.use_cases.tasks.update import UpdateTask
from taskmanager.domain.entities.task import Task
from taskmanager.domain.entities.task_list import TaskList
from taskmanager.domain.value_objects.task_status import TaskStatus
from tests.unit.application.fakes import FakeUnitOfWork, FrozenClock

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
ACTOR_ID = UUID("11111111-1111-4111-8111-111111111111")
ASSIGNEE_ID = UUID("55555555-5555-4555-8555-555555555555")
TASK_ID = UUID("22222222-2222-4222-8222-222222222222")
LIST_ID = UUID("33333333-3333-4333-8333-333333333333")


def _uow(*, assignee_id: UUID | None = None) -> FakeUnitOfWork:
    """One owned list holding one pending task, written straight into `stored`."""
    unit_of_work = FakeUnitOfWork()
    unit_of_work.task_list_repository.stored[LIST_ID] = TaskList.create(
        task_list_id=LIST_ID, owner_id=ACTOR_ID, name="Phase 4", now=NOW
    )
    unit_of_work.task_repository.stored[TASK_ID] = Task.create(
        task_id=TASK_ID,
        task_list_id=LIST_ID,
        title="Hold the row",
        assignee_id=assignee_id,
        now=NOW,
    )
    return unit_of_work


async def test_the_guard_reads_plainly_unless_told_otherwise() -> None:
    """The default is the read path, so a GET can never wait by accident."""
    async with _uow() as unit_of_work:
        await visible_task_list(unit_of_work, LIST_ID, ACTOR_ID)
        await visible_task(unit_of_work, LIST_ID, TASK_ID, ACTOR_ID)

        assert unit_of_work.task_repository.held_for_update == []
        assert unit_of_work.task_list_repository.held_for_update == []


async def test_the_list_guard_holds_the_list_for_a_writer() -> None:
    async with _uow() as unit_of_work:
        task_list = await visible_task_list(
            unit_of_work, LIST_ID, ACTOR_ID, for_update=True
        )

        assert task_list.id == LIST_ID
        assert unit_of_work.task_list_repository.held_for_update == [LIST_ID]


async def test_the_task_guard_holds_the_task_and_never_its_parent_list() -> None:
    """The lock-ordering rule: a task's writer holds the task, and only the task."""
    async with _uow() as unit_of_work:
        task = await visible_task(
            unit_of_work, LIST_ID, TASK_ID, ACTOR_ID, for_update=True
        )

        assert task.id == TASK_ID
        assert unit_of_work.task_repository.held_for_update == [TASK_ID]
        assert unit_of_work.task_list_repository.held_for_update == []


async def test_change_task_status_holds_the_task_it_validates() -> None:
    """The use case CR-01 was reproduced against.

    Validating `change_status` against a copy loaded through `get` is what let a
    second writer persist `completed -> pending`. Held exactly once: a second
    hold would be a second statement on the hottest write path in the phase.
    """
    unit_of_work = _uow()

    await ChangeTaskStatus(unit_of_work, FrozenClock(NOW)).execute(
        ChangeTaskStatusCommand(
            actor_id=ACTOR_ID,
            task_list_id=LIST_ID,
            task_id=TASK_ID,
            new_status=TaskStatus.IN_PROGRESS,
        )
    )

    assert unit_of_work.task_repository.held_for_update == [TASK_ID]
    assert unit_of_work.task_list_repository.held_for_update == []


async def test_the_assignees_status_change_holds_the_task_and_no_list() -> None:
    """The second actor who can now reach a write path (D-03, plan 05-04).

    The assignee is not the owner of this list, so their request is answered by
    the short-circuit in `access.py` and never reads the list at all - which
    makes "holds no task list" true here for a second, stronger reason than it
    is on the owner's path. Both halves are asserted anyway, because the claim
    being kept is the lock-ordering rule, and it must survive a future change
    that makes the assignee's leg consult the list again.

    Plan 05-08 adds the `AssignTask` and `UnassignTask` cases beside this one.
    """
    unit_of_work = _uow(assignee_id=ASSIGNEE_ID)

    await ChangeTaskStatus(unit_of_work, FrozenClock(NOW)).execute(
        ChangeTaskStatusCommand(
            actor_id=ASSIGNEE_ID,
            task_list_id=LIST_ID,
            task_id=TASK_ID,
            new_status=TaskStatus.IN_PROGRESS,
        )
    )

    assert unit_of_work.task_repository.held_for_update == [TASK_ID]
    assert unit_of_work.task_list_repository.held_for_update == []


async def test_update_task_holds_the_task_it_writes_back() -> None:
    """A PATCH writes `status` and `completed_at` back beside the new title."""
    unit_of_work = _uow()

    await UpdateTask(unit_of_work, FrozenClock(NOW)).execute(
        UpdateTaskCommand(
            actor_id=ACTOR_ID, task_list_id=LIST_ID, task_id=TASK_ID, title="Renamed"
        )
    )

    assert unit_of_work.task_repository.held_for_update == [TASK_ID]
    assert unit_of_work.task_list_repository.held_for_update == []


async def test_delete_task_holds_the_task_it_removes() -> None:
    unit_of_work = _uow()

    await DeleteTask(unit_of_work).execute(
        DeleteTaskCommand(actor_id=ACTOR_ID, task_list_id=LIST_ID, task_id=TASK_ID)
    )

    assert unit_of_work.task_repository.held_for_update == [TASK_ID]
    assert unit_of_work.task_list_repository.held_for_update == []


async def test_update_task_list_holds_the_list_it_writes_back() -> None:
    unit_of_work = _uow()

    await UpdateTaskList(unit_of_work, FrozenClock(NOW)).execute(
        UpdateTaskListCommand(
            actor_id=ACTOR_ID, task_list_id=LIST_ID, description="Rewritten."
        )
    )

    assert unit_of_work.task_list_repository.held_for_update == [LIST_ID]
    assert unit_of_work.task_repository.held_for_update == []


async def test_delete_task_list_holds_the_list_it_removes() -> None:
    unit_of_work = _uow()

    await DeleteTaskList(unit_of_work).execute(
        DeleteTaskListCommand(actor_id=ACTOR_ID, task_list_id=LIST_ID)
    )

    assert unit_of_work.task_list_repository.held_for_update == [LIST_ID]
    assert unit_of_work.task_repository.held_for_update == []


async def test_no_read_use_case_ever_holds_anything() -> None:
    """The other direction: a GET that waited on a PATCH would be a regression.

    All three addressed-resource reads in one test, because the claim is about
    the set - "reads do not hold" - and a fourth read added later belongs here.
    """
    unit_of_work = _uow()

    await GetTask(unit_of_work).execute(
        GetTaskCommand(actor_id=ACTOR_ID, task_list_id=LIST_ID, task_id=TASK_ID)
    )
    await GetTaskList(unit_of_work).execute(
        GetTaskListCommand(actor_id=ACTOR_ID, task_list_id=LIST_ID)
    )
    await ListTasks(unit_of_work).execute(
        ListTasksCommand(actor_id=ACTOR_ID, task_list_id=LIST_ID)
    )

    assert unit_of_work.task_repository.held_for_update == []
    assert unit_of_work.task_list_repository.held_for_update == []
