"""Create one list for an owner, refusing a name that owner already uses.

Two shapes a reader might expect here are deliberately absent.

The first is validation. There is no length check on the name, no trimming of
the description and no "is this blank?" guard: `TaskList.__post_init__` already
applies all three through `domain/validation.py`, and Phase 2 D-04 puts every
business limit in the entity exactly once. A copy here would be a second place
to update when a limit moves, and the copy that gets forgotten is always the one
nobody re-reads.

The second is a statistics query for the list this use case has just built. A
brand-new list cannot have tasks - nothing else has run inside this transaction -
so the counters are constructed locally rather than read back. The obvious
alternative is a round trip whose answer is already known, on the hottest write
path the phase has.

**On the duplicate-name pre-check.** It is a convenience, not the guard. The
unique index over `(owner_id, name)` is what actually holds under concurrency:
two requests can both pass the check and only one can pass the index, and the
task-list adapter already translates that refusal into the very same error (03
D-13). What the pre-check buys is the clean answer in the ordinary case - a
conflict raised before anything is written, rather than one reconstructed from a
driver error. Both roads lead to the same class, which is why this is belt and
braces rather than a business rule stated twice.

The comparison is case-**sensitive**, and that is a decision D-12 records rather
than an accident: `TaskList` folds no case on its name, unlike `User` on its
email address, so `Alpha` and `alpha` are two lists the domain considers
distinct - and the index agrees.
"""

from uuid import uuid4

from taskmanager.application.dto.commands import CreateTaskListCommand
from taskmanager.application.dto.results import TaskListResult
from taskmanager.application.ports.clock import Clock
from taskmanager.application.ports.unit_of_work import UnitOfWork
from taskmanager.domain.entities.task_list import TaskList
from taskmanager.domain.exceptions import DuplicateTaskListNameError
from taskmanager.domain.value_objects.completion import CompletionStats

# The counters a list has the instant it is created. Named here rather than
# spelled inline so the claim "a new list is empty" is one thing a reader can
# check, and so the zero-task case has the same shape as every other answer.
_NO_TASKS_YET = CompletionStats(total=0, completed=0)


class CreateTaskList:
    """Creates one task list owned by the authenticated actor (LIST-01)."""

    def __init__(self, uow: UnitOfWork, clock: Clock) -> None:
        # The unit of work first, then the non-transactional ports as separate
        # arguments (D-17) - the constructor of `ChangeTaskStatus`, unchanged.
        self._uow = uow
        self._clock = clock

    async def execute(self, command: CreateTaskListCommand) -> TaskListResult:
        """Create the list, or raise the conflict that describes the refusal."""
        async with self._uow:
            # Read once and handed down, so `created_at` and `updated_at` are
            # the same instant by construction rather than by coincidence (D-13).
            now = self._clock.now()
            # LIST-06. See the module docstring for why this is the convenience
            # and the unique index is the authority.
            if await self._uow.task_lists.exists_with_name(
                command.actor_id, command.name
            ):
                raise DuplicateTaskListNameError(command.name)
            # `owner_id` comes from the command's actor and from nothing else:
            # `CreateTaskListCommand` has no owner field at all, so a request
            # cannot nominate a victim to own the list it just made (T-4-27).
            # The identifier is generated here because ids belong to the
            # application layer, never to the entity and never to the database.
            task_list = TaskList.create(
                task_list_id=uuid4(),
                owner_id=command.actor_id,
                name=command.name,
                description=command.description,
                now=now,
            )
            await self._uow.task_lists.add(task_list)
            await self._uow.commit()
        # Mapped outside the block: the result describes a transaction that has
        # already been made durable, never one still in flight.
        return TaskListResult.from_entity(task_list, _NO_TASKS_YET)
