"""Read one list, with the counters every task-list answer carries (LIST-02).

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

The ownership rule is not restated. It is entered, once, through `access.py`,
for the reason that module's docstring gives at length: ten use cases sharing
one copy of ADR-008 cannot forget the second half of the condition in the
eleventh.
"""

from taskmanager.application.dto.commands import GetTaskListCommand
from taskmanager.application.dto.results import TaskListResult
from taskmanager.application.ports.unit_of_work import UnitOfWork
from taskmanager.application.use_cases.access import visible_task_list


class GetTaskList:
    """Reads one task list on behalf of an authenticated actor (LIST-02)."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, command: GetTaskListCommand) -> TaskListResult:
        """Return the list, or raise the answer an absent list would get."""
        async with self._uow:
            # A list this actor does not own is refused exactly as an absent one
            # is - same class, same code, same details (D-04, ADR-008).
            task_list = await visible_task_list(
                self._uow, command.task_list_id, command.actor_id
            )
            # One list, so one aggregate: the grouped statement the collection
            # uses exists to avoid N+1 over many lists, and would be the wrong
            # tool for a single row (D-10).
            stats = await self._uow.tasks.completion_stats(task_list.id)
        # Mapped outside the block, like every sibling: the result is built from
        # values already read, never from an entity a closed session might
        # refresh.
        return TaskListResult.from_entity(task_list, stats)
