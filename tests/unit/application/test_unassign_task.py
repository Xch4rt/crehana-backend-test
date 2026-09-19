"""The other half of the assignment door: owner-only, idempotent, and silent.

`UnassignTask` is `AssignTask` minus three things - the user lookup, the
captured address and the notification - and each absence is a decision this
module pins rather than a simplification:

* **Silent.** Unassigning sends nothing (D-07), and the use case has no
  notifier to send with. `test_unassigning_sends_nothing` asserts both halves,
  because a recorder that was never injected records nothing whatever the
  implementation does - the load-bearing assertion is the one about the
  constructor.
* **Owner-only, including against the assignee themselves.** ASGN-01 says the
  list owner unassigns; "an assignee declining a task" is a rule nobody asked
  for. So the 403 test here is the mirror image of `test_delete_task.py`'s.
* **Idempotent.** A second `DELETE` writes nothing. `Task.unassign` still
  stamps an already-clear task - the entity deliberately has no no-op (plan
  05-01) - so `updated_at` is asserted unchanged as well as the counters.

Every failure test asserts `commits == 0` and `rollbacks == 1` beside the
exception, the suite convention `test_delete_task.py` describes.
"""

import inspect
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from taskmanager.application.dto.commands import UnassignTaskCommand
from taskmanager.application.use_cases.tasks.assign import UnassignTask
from taskmanager.domain.entities.task import Task
from taskmanager.domain.entities.task_list import TaskList
from taskmanager.domain.exceptions import (
    AuthorizationError,
    DomainError,
    TaskNotFoundError,
)
from taskmanager.domain.value_objects.task_priority import TaskPriority
from tests.unit.application.fakes import (
    FakeEmailNotifier,
    FakeUnitOfWork,
    FrozenClock,
)

# Fixed on purpose. A generated identifier or a real clock reading would make
# every assertion below unfalsifiable: the test could no longer state which
# moment, or which actor, it expects.
NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
LATER = NOW + timedelta(hours=3)
ACTOR_ID = UUID("11111111-1111-4111-8111-111111111111")
TASK_ID = UUID("22222222-2222-4222-8222-222222222222")
TASK_LIST_ID = UUID("33333333-3333-4333-8333-333333333333")
ASSIGNEE_ID = UUID("55555555-5555-4555-8555-555555555555")
STRANGER_ID = UUID("77777777-7777-4777-8777-777777777777")
OTHER_USER_ID = UUID("99999999-9999-4999-8999-999999999999")
TITLE = "Write the assignment use case"


def _uow(
    *,
    owner_id: UUID = ACTOR_ID,
    assignee_id: UUID | None = ASSIGNEE_ID,
) -> FakeUnitOfWork:
    """One list holding one task, written straight into `stored`.

    No users are seeded, and that is the shape of the operation: unassigning
    resolves no caller-supplied identifier, so the users table is never read.
    Entities go in directly rather than through `add()`, so `updated` stays
    empty and every entry a test finds in it was written by the use case.
    """
    unit_of_work = FakeUnitOfWork()
    unit_of_work.task_list_repository.stored[TASK_LIST_ID] = TaskList.create(
        task_list_id=TASK_LIST_ID,
        owner_id=owner_id,
        name="Phase 5",
        now=NOW,
    )
    task = Task.create(
        task_id=TASK_ID,
        task_list_id=TASK_LIST_ID,
        title=TITLE,
        priority=TaskPriority.HIGH,
        assignee_id=assignee_id,
        now=NOW,
    )
    unit_of_work.task_repository.stored[task.id] = task
    return unit_of_work


def _command(*, actor_id: UUID = ACTOR_ID) -> UnassignTaskCommand:
    """The single construction site every test below goes through."""
    return UnassignTaskCommand(
        actor_id=actor_id,
        task_list_id=TASK_LIST_ID,
        task_id=TASK_ID,
    )


async def test_the_owner_clears_the_assignee_and_the_write_is_durable() -> None:
    """The happy path: the field empties, the timestamp moves, one write lands."""
    unit_of_work = _uow()

    result = await UnassignTask(unit_of_work, FrozenClock(LATER)).execute(_command())

    assert result.assignee_id is None
    assert result.updated_at == LATER
    assert unit_of_work.task_repository.stored[TASK_ID].assignee_id is None
    assert unit_of_work.task_repository.updated == [
        unit_of_work.task_repository.stored[TASK_ID]
    ]
    assert unit_of_work.commits == 1
    assert unit_of_work.rollbacks == 0


async def test_unassigning_sends_nothing() -> None:
    """D-07: taking a task back is not news, so no message is produced.

    The recorder is created and deliberately not injected, which is the point:
    the count it reports is zero whatever the implementation does, so the
    load-bearing assertion is the second one. A use case that *could* send has
    a port to send through, and this one has no argument to accept it in -
    `AssignTask`'s docstring makes the same argument from the other side.
    """
    notifier = FakeEmailNotifier()
    unit_of_work = _uow()

    await UnassignTask(unit_of_work, FrozenClock(LATER)).execute(_command())

    assert notifier.sent == []
    assert "notifier" not in inspect.signature(UnassignTask.__init__).parameters


async def test_unassigning_an_unassigned_task_changes_nothing() -> None:
    """D-07's idempotence, and the reason it cannot live in the entity.

    `Task.unassign` stamps an already-clear task - it has no no-op of its own,
    deliberately (plan 05-01) - so an implementation that simply called it
    would move `updated_at` on every repeated `DELETE` and make something
    durable for a request that changed nothing. `updated_at` is therefore
    asserted unchanged beside the counters.
    """
    unit_of_work = _uow(assignee_id=None)

    result = await UnassignTask(unit_of_work, FrozenClock(LATER)).execute(_command())

    assert result.assignee_id is None
    assert result.updated_at == NOW
    assert unit_of_work.task_repository.updated == []
    assert unit_of_work.commits == 0
    assert unit_of_work.rollbacks == 1


async def test_the_assignee_may_not_unassign_themselves() -> None:
    """D-03 / ASGN-01: the list owner unassigns, and nobody else does.

    An assignee declining their own task is a feature nobody asked for - it
    sits in this phase's deferred ideas - so they are refused with the 403 they
    can already disprove with a `GET`, and the assignment is still there
    afterwards.
    """
    unit_of_work = _uow(owner_id=OTHER_USER_ID, assignee_id=ACTOR_ID)

    with pytest.raises(DomainError) as excinfo:
        await UnassignTask(unit_of_work, FrozenClock(LATER)).execute(_command())

    error = excinfo.value
    assert isinstance(error, AuthorizationError)
    assert not isinstance(error, TaskNotFoundError)
    assert str(OTHER_USER_ID) not in str(error)
    assert unit_of_work.task_repository.stored[TASK_ID].assignee_id == ACTOR_ID
    assert unit_of_work.task_repository.updated == []
    assert unit_of_work.commits == 0
    assert unit_of_work.rollbacks == 1


async def test_unassign_hides_the_task_from_a_stranger() -> None:
    """The 404 leg, and it must not become the assignee's 403 by accident."""
    unit_of_work = _uow(owner_id=OTHER_USER_ID)

    with pytest.raises(DomainError) as excinfo:
        await UnassignTask(unit_of_work, FrozenClock(LATER)).execute(
            _command(actor_id=STRANGER_ID)
        )

    error = excinfo.value
    assert isinstance(error, TaskNotFoundError)
    assert not isinstance(error, AuthorizationError)
    assert error.details == {"task_id": str(TASK_ID)}
    assert unit_of_work.task_repository.stored[TASK_ID].assignee_id == ASSIGNEE_ID
    assert unit_of_work.commits == 0
    assert unit_of_work.rollbacks == 1


def test_unassign_asks_for_the_clock_and_nothing_else() -> None:
    """ARC-04 read back off the constructor: two ports, because two are touched.

    Its sibling takes a third argument and says why. This one must not, and the
    difference between the two constructors is the whole of D-07's "unassigning
    sends nothing" stated as a shape rather than as a promise.
    """
    parameters = list(inspect.signature(UnassignTask.__init__).parameters)

    assert parameters[1:] == ["uow", "clock"]
