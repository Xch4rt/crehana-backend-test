"""The tasks of one list, filtered - and the number that must not follow the
filter (TASK-06, TASK-07).

This module holds the phase's most easily-got-wrong rule, so it is stated here
in full rather than left to a comment. **The filter describes the view; the
statistics describe the list.** A client asking to see only the pending tasks is
asking about a subset of rows, not about a different list, and a completion
percentage that moved when they changed a query parameter would be a different
number wearing the same name - one a dashboard could not compare against
yesterday's. ADR-009 and roadmap SC-4 fix that asymmetry, and `D-09` puts both
halves in one envelope so a client never has to make a second call to learn how
far along the list is.

The line below that reads the counters therefore takes the list's identifier and
nothing else. It is the single line in this phase most likely to be "improved"
by passing the filter through - the call sits three lines under one that does
take the filter, and the two look like they should match. They must not. A
regex acceptance criterion in 04-06-PLAN.md asserts that no filter argument
appears in that call, and `test_the_filter_never_moves_the_statistics` asserts
the behaviour from the other side.

**The filters reach SQL, never a comprehension.** `list_for_task_list` takes
`status` and `priority` as keyword arguments and appends them to the statement,
so PostgreSQL returns exactly the rows the caller asked for. Reading the whole
list and narrowing it in Python would answer the same thing today, and would
become the slow path the first time a list holds a thousand tasks - while also
reading rows the caller never asked for. Plan 03-07 already proved the adapter
applies the two together as a conjunction; the unit test beside this module
proves the use case hands them over as a pair rather than picking one.

**Nothing is made durable**, for the reason `get.py` states: the transaction
wrote nothing, and `__aexit__` closing it is the port's documented obligation.
"""

from taskmanager.application.dto.commands import ListTasksCommand
from taskmanager.application.dto.results import TaskCollectionResult
from taskmanager.application.ports.unit_of_work import UnitOfWork
from taskmanager.application.use_cases.access import visible_task_list


class ListTasks:
    """Reads the tasks of one list, optionally filtered (TASK-06, TASK-07)."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, command: ListTasksCommand) -> TaskCollectionResult:
        """Return the filtered tasks, with the whole list's counters beside them."""
        async with self._uow:
            # The parent is authorised first, so a list this actor cannot see is
            # refused before a single task is read - and the entity is discarded,
            # because the guard is the point (D-04, ADR-008).
            await visible_task_list(self._uow, command.task_list_id, command.actor_id)
            # Keyword arguments, so the narrowing happens in the statement. The
            # port's signature is keyword-only and must not be widened: a
            # positional call would rely on an order the Protocol never promised.
            tasks = await self._uow.tasks.list_for_task_list(
                command.task_list_id,
                status=command.status,
                priority=command.priority,
            )
            # ADR-009: no filter argument here, on purpose. See the module
            # docstring - the counters describe the whole list, and passing the
            # filter through would silently answer a different question.
            stats = await self._uow.tasks.completion_stats(command.task_list_id)
        # Mapped outside the block, like every sibling: `from_parts` is the one
        # place the tuple conversion and the unpacking of the counters happen.
        return TaskCollectionResult.from_parts(tasks, stats)
