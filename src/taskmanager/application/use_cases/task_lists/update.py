"""Partially change one list: the PATCH that can tell omitted from null (LIST-04).

Everything here turns on the sentinel `dto/unset.py` defines. A field the client
did not mention must be left alone, and a field the client explicitly set to
null must be cleared (D-05) - two different outcomes, so `None` cannot stand for
both. The guard below narrows the sentinel away, which is why the entity
mutators receive a value of their declared type and mypy, not a runtime check,
is what proves the guard was not forgotten.

**The rename pre-check is conditional, and the condition is the point.** A PATCH
that resends the list's *current* name is not a conflict: the only row wearing
that name is this list's own, so an unconditional pre-check would refuse the
request on the strength of the very thing it is about to write. Comparing the
incoming name with the stored one first is what keeps a re-send idempotent
instead of fatal. Everything `create.py`'s docstring says about the check being
a convenience rather than the guard applies here unchanged - the unique index is
still the authority, and the adapter already translates its refusal.

**`updated_at` moves whenever a field is provided, even when the value it
carries is the one already stored.** That is a decision (04-PATTERNS Pitfall 10),
and these are its three reasons. D-06 refuses an empty body at the schema with a
422, so there is no genuine no-op request to protect. Comparing old and new
values would put a second "did this actually change?" rule beside the entity
mutators, which already stamp unconditionally - two rules, one of which will
eventually disagree with the other. And a client that sends a field is asking
for a write, so recording one is the honest answer. Plan 04-12 turns this
paragraph into an ADR.

Nothing here re-validates a length, a blank name or an empty description:
`rename` and `describe` apply the same guards construction applied, and Phase 2
D-04 keeps every business limit in the entity exactly once.
"""

from taskmanager.application.dto.commands import UpdateTaskListCommand
from taskmanager.application.dto.results import TaskListResult
from taskmanager.application.dto.unset import UNSET
from taskmanager.application.ports.clock import Clock
from taskmanager.application.ports.unit_of_work import UnitOfWork
from taskmanager.application.use_cases.access import visible_task_list
from taskmanager.domain.exceptions import DuplicateTaskListNameError


class UpdateTaskList:
    """Renames and/or re-describes one list on behalf of an actor (LIST-04)."""

    def __init__(self, uow: UnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    async def execute(self, command: UpdateTaskListCommand) -> TaskListResult:
        """Apply the provided fields, or raise the refusal that stops them."""
        async with self._uow:
            # A list this actor does not own is refused exactly as an absent one
            # is, on this verb as on every other (D-04, ADR-008).
            task_list = await visible_task_list(
                self._uow, command.task_list_id, command.actor_id
            )
            # Read once and handed down, so both mutators stamp the same instant
            # rather than two readings a microsecond apart (D-13).
            now = self._clock.now()
            if command.name is not UNSET:
                # LIST-06 on the rename leg. The comparison comes first: see the
                # module docstring for why a re-sent name must not conflict with
                # the row that already carries it.
                if (
                    command.name != task_list.name
                    and await self._uow.task_lists.exists_with_name(
                        command.actor_id, command.name
                    )
                ):
                    raise DuplicateTaskListNameError(command.name)
                task_list.rename(command.name, now=now)
            if command.description is not UNSET:
                # An explicit null arrives here as `None` and clears the field,
                # which is the whole of D-05; the entity folds "" the same way.
                task_list.describe(command.description, now=now)
            await self._uow.task_lists.update(task_list)
            stats = await self._uow.tasks.completion_stats(task_list.id)
            await self._uow.commit()
        # Mapped outside the block: the result describes a transaction that has
        # already been made durable, never one still in flight.
        return TaskListResult.from_entity(task_list, stats)
