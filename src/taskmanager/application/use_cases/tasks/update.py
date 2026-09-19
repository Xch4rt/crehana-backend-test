"""Partially change one task: four fields, and a fifth that is not here (TASK-03).

Everything here turns on the sentinel `dto/unset.py` defines. A field the client
did not mention must be left alone, and a field the client explicitly set to
null must be cleared (D-05) - two different outcomes, so `None` cannot stand for
both. Each guard below narrows the sentinel away, which is why the entity
mutators receive a value of their declared type and mypy, not a runtime check,
is what proves the guard was not forgotten.

**D-07: the deadline is re-checked only when the client sent one.** `reschedule`
refuses a deadline behind the current moment, and that rule is about the moment
a deadline is *set* - never about the continued existence of a row whose
deadline has simply passed. Calling it unconditionally, with the stored value,
would make an overdue task permanently unpatchable: its title could not be
corrected, its priority could not be raised, and the refusal would name a field
the request never contained. `test_a_patch_without_due_date_does_not_recheck_an_
overdue_task` is what fails if anybody moves that call out of its guard.

**D-08: there is no branch for the status, and there is no mutator call for it
either.** The dedicated endpoint is the only door onto the state machine
(TASK-03), and `UpdateTaskCommand` does not declare the field at all - so this
is enforced by the type rather than by an `if` somebody could add back. The
request schema's `extra="forbid"` turns an attempt into a 422 one layer up, and
a grep over this module for the mutator's name is an acceptance criterion of the
plan that wrote it. Three enforcement points, none of which is a convention.

**`updated_at` moves whenever a field is provided - and therefore does not move
at all when the command carries none.** That is the decision the sibling
`task_lists/update.py` records, kept identical here: the mutators stamp
unconditionally, comparing old and new values first would put a second "did this
actually change?" rule beside them, and D-06 refuses an empty body at the schema
with a 422, so the no-field request never arrives over HTTP in the first place.

Nothing here re-validates a blank title, a length or a deadline: `rename`,
`describe`, `reprioritise` and `reschedule` apply the same guards construction
applied, and Phase 2 D-04 keeps every business limit in the entity exactly once.
"""

from taskmanager.application.dto.commands import UpdateTaskCommand
from taskmanager.application.dto.results import TaskResult
from taskmanager.application.dto.unset import UNSET
from taskmanager.application.ports.clock import Clock
from taskmanager.application.ports.unit_of_work import UnitOfWork
from taskmanager.application.use_cases.access import visible_task


class UpdateTask:
    """Applies a partial change to one task on behalf of an actor (TASK-03)."""

    def __init__(self, uow: UnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    async def execute(self, command: UpdateTaskCommand) -> TaskResult:
        """Apply the provided fields, or raise the refusal that stops them."""
        async with self._uow:
            # One call, four refusals, all of them `task_not_found`: absent,
            # under another list (D-14), orphaned, or on a list this actor does
            # not own. `access.py` argues each leg.
            task = await visible_task(
                self._uow, command.task_list_id, command.task_id, command.actor_id
            )
            # Read once and handed down, so every mutator this request reaches
            # stamps the same instant rather than four readings a microsecond
            # apart (D-13).
            now = self._clock.now()
            # Four independent guards in field order. Each one is also what
            # narrows the sentinel away for mypy, so a mutator called outside
            # its guard is a type error rather than a runtime surprise.
            if command.title is not UNSET:
                task.rename(command.title, now=now)
            if command.description is not UNSET:
                # An explicit null arrives here as `None` and clears the field,
                # which is the whole of D-05; the entity folds "" the same way.
                task.describe(command.description, now=now)
            if command.priority is not UNSET:
                task.reprioritise(command.priority, now=now)
            if command.due_date is not UNSET:
                # D-07 lives in this guard. See the module docstring: moving
                # this call out of it is what makes an overdue task
                # unpatchable, and no other line in the file would change.
                task.reschedule(command.due_date, now=now)
            await self._uow.tasks.update(task)
            await self._uow.commit()
        # Mapped outside the block: the result describes a transaction that has
        # already been made durable, never one still in flight.
        return TaskResult.from_entity(task)
