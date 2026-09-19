"""Every list the actor owns, and its counters, in one repository call (LIST-03).

The shape this module exists to refuse is the obvious one: read the collection,
then ask for one list's statistics per entry. That is an N+1 - one statement,
then one more for every row - and it is the pitfall the whole of LIST-03 is
written against. It is also invisible in a unit test that checks values only,
which is why the test module instruments the task repository and asserts the
per-list counter was never called at all, and why plan 04-10 counts statements
over HTTP. A future implementation that loops per entry therefore fails twice,
in two layers, rather than passing both.

So the counters arrive *with* the rows, from the one grouped statement plan
04-02 added to the task-list port - the single call below - and this module's
job is to map pairs rather than to gather them. The name is spelled exactly
once in this file, on that call, so "how many queries does the collection cost?"
is a question a grep answers.

**There is no ownership check here, and that is not the omission it looks
like.** The query is scoped by `owner_id` - a list the actor does not own is
simply not among the rows, which is the same answer ADR-008 requires and reached
by construction rather than by a guard someone could forget. A load-and-
authorize call has nothing to authorize: there is no single addressed resource,
and a per-entry filter in Python would be a second copy of a rule the SQL
already states, running after the rows it was supposed to exclude had already
been read.

Nothing here is made durable, for the reason `get.py` states: the transaction
wrote nothing, and `__aexit__` closing it is the port's documented obligation.

The answer is a plain `tuple`, never a wrapper class: D-10 puts the statistics
on each entry, so a collection envelope would be a name the API shape never
asks for (`results.py` makes the same argument from the DTO side). `tuple` and
not `list`, because a caller must not be able to edit an answer the transaction
has already finished producing.
"""

from taskmanager.application.dto.commands import ListTaskListsCommand
from taskmanager.application.dto.results import TaskListResult
from taskmanager.application.ports.unit_of_work import UnitOfWork


class ListTaskLists:
    """Reads every task list an authenticated actor owns (LIST-03)."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(
        self, command: ListTaskListsCommand
    ) -> tuple[TaskListResult, ...]:
        """Return the actor's lists in `(created_at, id)` order, with counters."""
        async with self._uow:
            # The one call, for the whole collection, whatever its size. The
            # ordering is the repository's (D-13): a total order belongs in the
            # statement's ORDER BY, where PostgreSQL can serve it from the
            # index, rather than in a sort applied to rows already fetched.
            entries = await self._uow.task_lists.list_for_owner_with_stats(
                command.actor_id
            )
        # Mapped outside the block, like every sibling in this package.
        return tuple(
            TaskListResult.from_entity(task_list, stats) for task_list, stats in entries
        )
