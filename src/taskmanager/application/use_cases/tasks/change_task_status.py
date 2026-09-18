"""The reference use case: move a task through the lifecycle, or refuse to.

The canonical body every Phase 4 and Phase 5 use case repeats:

    load -> authorize -> invoke domain -> persist -> commit -> map to result

Three alternatives are rejected, and each one is a shape a reader might expect.

A `TaskService` holding create, rename, assign and this operation as four
methods. ARC-04 and D-15 ask for one single-purpose class per use case instead:
a class with one job has one set of dependencies, so its constructor states
exactly what the operation touches, and a test cannot accidentally satisfy it
with ports the operation never uses.

`__call__` in place of a named `execute`. It reads well at one call site and
badly everywhere else - `use_case(command)` gives a reader nothing to grep for,
and D-15 fixes the name so every use case in the project answers to the same one.

Committing in a FastAPI `yield` dependency teardown. That works, and it moves
the transaction boundary into the web framework, so the same use case driven
from a worker or a test would silently lose its atomicity. ARC-08 and D-17 put
`commit()` here, on the success path only, where the code that knows the
operation succeeded is the code that makes it durable.

**On authorization:** this use case has no `AuthorizationError` branch, and that
is a decision rather than an omission. ASGN-02 lets both the list owner and the
assignee change a task's status, so every actor who can see the task may also
change it - there is no visible-but-forbidden case left to answer 403 with. An
actor who cannot see it gets `TaskNotFoundError` instead, per ADR-008: a 403
would confirm the task exists to someone who is not entitled to know that, which
is the IDOR leak AUTH-06 is written against. The 403 leg of ADR-008 belongs to
the owner-only operations - edit, delete, assign - in Phases 4 and 5, and the
mapping from `AuthorizationError` to a 403 problem body is already proven end to
end by `tests/api/test_error_contract.py` (plan 02-04).
"""

from uuid import UUID

from taskmanager.application.dto.commands import ChangeTaskStatusCommand
from taskmanager.application.dto.results import TaskResult
from taskmanager.application.ports.clock import Clock
from taskmanager.application.ports.unit_of_work import UnitOfWork
from taskmanager.domain.entities.task import Task
from taskmanager.domain.entities.task_list import TaskList
from taskmanager.domain.exceptions import TaskListNotFoundError, TaskNotFoundError


def _may_change_status(task: Task, task_list: TaskList, actor_id: UUID) -> bool:
    """Whether this actor may see, and therefore move, this task (ASGN-02)."""
    return task_list.owner_id == actor_id or task.assignee_id == actor_id


class ChangeTaskStatus:
    """Moves one task to a requested status on behalf of an authenticated actor."""

    def __init__(self, uow: UnitOfWork, clock: Clock) -> None:
        # The unit of work first, then the non-transactional ports as separate
        # arguments (D-17). Nothing else is injected, because nothing else is
        # touched - which is the whole point of one class per use case.
        self._uow = uow
        self._clock = clock

    async def execute(self, command: ChangeTaskStatusCommand) -> TaskResult:
        """Run the operation, or raise the domain error that describes its refusal."""
        async with self._uow:
            task = await self._uow.tasks.get(command.task_id)
            if task is None:
                raise TaskNotFoundError(command.task_id)
            task_list = await self._uow.task_lists.get(task.task_list_id)
            if task_list is None:
                raise TaskListNotFoundError(task.task_list_id)
            if not _may_change_status(task, task_list, command.actor_id):
                # ADR-008: the same answer an absent task gets. Anything that
                # distinguished the two would leak the task's existence.
                raise TaskNotFoundError(command.task_id)
            # The entity owns the state machine and the timestamps; this line
            # is the only place the clock is read, and the instant is handed
            # down rather than looked up again (D-13).
            task.change_status(command.new_status, now=self._clock.now())
            await self._uow.tasks.update(task)
            await self._uow.commit()
        # Mapped outside the block: the result describes a transaction that has
        # already been made durable, never one still in flight.
        return TaskResult.from_entity(task)
