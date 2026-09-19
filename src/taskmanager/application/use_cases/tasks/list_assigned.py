"""The tasks assigned to the caller, across every list there is (D-02, ASGN-02).

An assignee who does not own a list cannot see that list at all (D-01): the
collection endpoint answers 404 and `GET /task-lists` still means "lists I own".
Without this route they would therefore have no way of discovering the tasks
they have been given - they could open one only by being told its nested URL by
somebody else. So discovery is one flat, read-only collection, and each entry
carries its `task_list_id`, which is what lets a client rebuild the nested
address the task is actually worked on through.

**There is no `access.py` guard here, and none is needed, because the query is
the filter.** The repository method this calls selects on the assignee column,
so the only rows it can possibly return are rows already assigned to the caller
- the same answer a per-entry permission check would reach, arrived at by
construction rather than by a guard someone could forget. A load-and-authorize
call has nothing to authorize: there is no single addressed resource, and a
filter written again in Python would run after the rows it was supposed to
exclude had already been read. `task_lists/list.py` makes the identical
argument about ownership scoping.

**What that safety rests on is the argument, not the query.** The identifier
handed to the repository is `command.actor_id`, which presentation fills from
the token's subject and from nothing the client sent - there is no
`assignee_id` field on the command and the port offers no widening parameter,
so this route cannot be pointed at another person's workload by editing a path
or a query string (T-5-11). If a later change ever let a caller name the id,
this module would need a guard; as written, it cannot.

Nothing here is made durable, and nothing is held for update: this is a read,
and a read that waited on a writer would be a regression that no
single-connection test would notice
(`tests/unit/application/test_write_paths_hold_what_they_change.py`).

The answer is a plain `tuple[TaskResult, ...]` rather than the
`TaskCollectionResult` envelope the per-list collection uses. That envelope
carries a list's completion statistics, and a percentage has no meaning across
lists: two thirds of *what*? The bare tuple matches the shape `GET /task-lists`
already answers with.
"""

from taskmanager.application.dto.commands import ListAssignedTasksCommand
from taskmanager.application.dto.results import TaskResult
from taskmanager.application.ports.unit_of_work import UnitOfWork


class ListAssignedTasks:
    """Reads every task assigned to an authenticated actor (D-02)."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(
        self, command: ListAssignedTasksCommand
    ) -> tuple[TaskResult, ...]:
        """Return the actor's assigned tasks in `(created_at, id)` order."""
        async with self._uow:
            # The actor, never an identifier the request supplied - see the
            # module docstring. The ordering is the repository's, for the
            # reason its sibling collections give: a total order belongs in the
            # statement's ORDER BY rather than in a sort over fetched rows.
            tasks = await self._uow.tasks.list_for_assignee(command.actor_id)
        # Mapped outside the block, like every sibling in this package.
        return tuple(TaskResult.from_entity(task) for task in tasks)
