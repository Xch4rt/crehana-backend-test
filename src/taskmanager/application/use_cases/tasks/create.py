"""Create one task inside a list the actor owns (TASK-01, TASK-08).

**This is the one task verb whose refusal is list-shaped, and that is the
deliberate exception to `access.py`'s asymmetry rule rather than an
inconsistency with its four siblings.** Every other verb in this package
addresses a *task* and therefore answers `task_not_found` on every leg,
including a parent list that is absent or foreign - because telling the caller
which of those two things went wrong would distinguish exactly the cases
ADR-008 requires to be indistinguishable. Here there is no task yet. The caller
addressed the list, the list is the only resource named in the request, and the
identifier the error carries is the one they supplied themselves. So the
list-shaped refusal reveals nothing, and inventing a task-shaped one would mean
answering with an identifier that does not exist for a resource nobody asked
for. The load below is the shared guard, entered exactly as the siblings enter
it; only the class it raises differs, and this paragraph is why.

**Nothing is re-checked here.** The blank title, the two-hundred-character cap
and the deadline that may not sit behind the creation moment are TASK-08's three
rules, and all three belong to the entity: `Task.create` applies them, and Phase
2 D-04 puts every business limit there exactly once. A copy in this module would
be a second place to update when a limit moves - and the copy that gets
forgotten is always the one nobody re-reads. The unit tests drive all three
refusals through this use case anyway, because "the entity's rule reaches the
caller" is a property of the orchestration, not of the entity.

**The priority is required on the command and has no default here.** TASK-01's
`medium` lives in `Task.DEFAULT_PRIORITY`, which the request schema reads for
its own field default, so a default on this path would be the same rule spelled
a second time. The command therefore always carries a value, and this use case
always passes one on.

**The status is not an argument.** A new task is pending, `Task.create` says so,
and the only door onto the state machine afterwards is the dedicated endpoint
(D-08). Accepting a starting status here would open a second one before the
first was even built.
"""

from uuid import uuid4

from taskmanager.application.dto.commands import CreateTaskCommand
from taskmanager.application.dto.results import TaskResult
from taskmanager.application.ports.clock import Clock
from taskmanager.application.ports.unit_of_work import UnitOfWork
from taskmanager.application.use_cases.access import visible_task_list
from taskmanager.domain.entities.task import Task


class CreateTask:
    """Creates one task inside a list the authenticated actor owns (TASK-01)."""

    def __init__(self, uow: UnitOfWork, clock: Clock) -> None:
        # The unit of work first, then the non-transactional ports as separate
        # arguments (D-17) - the constructor of `ChangeTaskStatus`, unchanged.
        self._uow = uow
        self._clock = clock

    async def execute(self, command: CreateTaskCommand) -> TaskResult:
        """Create the task, or raise the refusal that stops it."""
        async with self._uow:
            # The parent is loaded to decide whether this actor may put anything
            # in it at all, and the entity is deliberately discarded: the guard
            # is the point. A list this actor does not own is refused exactly as
            # an absent one is - see the module docstring for why that refusal is
            # list-shaped here and task-shaped in every sibling.
            await visible_task_list(self._uow, command.task_list_id, command.actor_id)
            # Read once and handed down, so `created_at` and `updated_at` are the
            # same instant by construction rather than by coincidence (D-13), and
            # so the deadline is compared against the moment this task was made.
            now = self._clock.now()
            # The identifier is generated here because ids belong to the
            # application layer, never to the entity and never to the database.
            # `task_list_id` comes from the path the guard above just authorised,
            # so a request cannot file a task under a list it was not addressed
            # to.
            task = Task.create(
                task_id=uuid4(),
                task_list_id=command.task_list_id,
                title=command.title,
                description=command.description,
                priority=command.priority,
                due_date=command.due_date,
                now=now,
            )
            await self._uow.tasks.add(task)
            await self._uow.commit()
        # Mapped outside the block: the result describes a transaction that has
        # already been made durable, never one still in flight.
        return TaskResult.from_entity(task)
