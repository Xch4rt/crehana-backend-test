"""Delete one list, and let the database take its tasks with it (LIST-05).

**The list is loaded before it is deleted, and the load is not wasted work.** A
delete issued straight against the identifier would remove nothing when the list
belongs to someone else - and would then answer 204, telling the caller their
delete succeeded. That is the failure mode ADR-008 and D-04 are written against
from the other direction: an actor must not be able to distinguish a list they
may not touch from one that is not there, and "it worked" is a very loud
distinction. Loading through the shared guard makes both cases the same 404.

**The tasks are not deleted here.** `ON DELETE CASCADE` on `tasks.task_list_id`
has been in the baseline migration since Phase 3, so the rows go with the parent
inside the same statement. Loading the children and removing them one by one
would be a second implementation of a rule the schema already states - and two
implementations of one rule is one of them being wrong eventually, silently, in
whichever copy nobody re-read. The integration suite asserts the cascade against
a real database, which is the only place the claim can honestly be checked.

**No clock, and no result.** Nothing is stamped, and LIST-05's 204 has no body
to build, so `execute` returns `None` rather than a DTO describing something
that no longer exists.
"""

from taskmanager.application.dto.commands import DeleteTaskListCommand
from taskmanager.application.ports.unit_of_work import UnitOfWork
from taskmanager.application.use_cases.access import visible_task_list


class DeleteTaskList:
    """Deletes one task list, with its tasks, on behalf of an actor (LIST-05)."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, command: DeleteTaskListCommand) -> None:
        """Delete the list, or raise the answer an absent list would get."""
        async with self._uow:
            # Loaded to decide whether this actor may see it at all; the return
            # value is deliberately unused, because the guard is the point.
            await visible_task_list(self._uow, command.task_list_id, command.actor_id)
            await self._uow.task_lists.delete(command.task_list_id)
            await self._uow.commit()
