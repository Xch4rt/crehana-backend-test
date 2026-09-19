"""Read one task, addressed under the list it is supposed to belong to (TASK-02).

Two absences are deliberate, and both are the kind of thing a reader assumes is
an oversight unless it is written down.

**No clock.** Nothing here is stamped, so the constructor takes the unit of work
alone. A `Clock` argument accepted and never read would be a dependency the
class does not have, and ARC-04's point is that a use case's constructor states
exactly what the operation touches - a reviewer should be able to tell a read
from a write by the arguments it asks for.

**Nothing is made durable.** This transaction wrote nothing, so there is nothing
to make durable, and `__aexit__` rolling the read back is the obligation the
`UnitOfWork` port places on it in writing - not an oversight, and not a leaked
session. The unit tests assert the inverse of the write-path convention here:
`commits == 0` and `rollbacks == 1` on the *success* path, which is what turns
"a read never writes" from a claim into an assertion.

The wrong-list and the not-owned rules are not restated. They are entered, once,
through `access.py`, which answers all four of its refusal legs with the same
task-shaped error: a read that distinguished "this task is somewhere else" from
"there is no such task" would hand an enumerating caller the one bit of
information D-14 and ADR-008 exist to withhold.
"""

from taskmanager.application.dto.commands import GetTaskCommand
from taskmanager.application.dto.results import TaskResult
from taskmanager.application.ports.unit_of_work import UnitOfWork
from taskmanager.application.use_cases.access import visible_task


class GetTask:
    """Reads one task on behalf of an authenticated actor (TASK-02)."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, command: GetTaskCommand) -> TaskResult:
        """Return the task, or raise the answer an absent task would get."""
        async with self._uow:
            # One call, four refusals, all of them `task_not_found`: absent,
            # under another list (D-14), orphaned, or on a list this actor does
            # not own. `access.py` argues each leg.
            task = await visible_task(
                self._uow, command.task_list_id, command.task_id, command.actor_id
            )
        # Mapped outside the block, like every sibling: the result is built from
        # values already read, never from an entity a closed session might
        # refresh.
        return TaskResult.from_entity(task)
