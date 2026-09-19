"""Delete one task, and refuse the ones this caller may not see (TASK-04).

**The task is loaded before it is deleted, and the load is not wasted work.** A
delete issued straight against the identifier removes nothing when the task
belongs to another actor's list, or when it sits under a list the caller did not
address - and would then answer 204, telling the caller their delete succeeded.
"It worked" is the loudest possible distinction between a resource somebody may
not touch and one that is not there, which is precisely the pair D-14 and
ADR-008 require to be indistinguishable. Loading through the shared guard makes
all four legs the same 404.

Those four legs are `visible_task`'s, not this module's: the task is absent; the
task exists under another list (D-14, TASK-02); the parent list is gone; the
parent list belongs to someone else (D-04). `access.py` argues each one, and the
point here is that the rule is entered rather than restated.

**No clock, and no result.** Nothing is stamped, and TASK-04's 204 has no body
to build, so `execute` returns `None` rather than a DTO describing something
that no longer exists.
"""

from taskmanager.application.dto.commands import DeleteTaskCommand
from taskmanager.application.ports.unit_of_work import UnitOfWork
from taskmanager.application.use_cases.access import visible_task


class DeleteTask:
    """Deletes one task on behalf of an authenticated actor (TASK-04)."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, command: DeleteTaskCommand) -> None:
        """Delete the task, or raise the answer an absent task would get."""
        async with self._uow:
            # Loaded to decide whether this actor may see it at all; the return
            # value is deliberately unused, because the guard is the point.
            # `for_update=True`: a write path holds what it is about to remove,
            # so it cannot interleave with a concurrent change (ADR-058).
            await visible_task(
                self._uow,
                command.task_list_id,
                command.task_id,
                command.actor_id,
                for_update=True,
            )
            await self._uow.tasks.delete(command.task_id)
            await self._uow.commit()
