"""The reference use case: move a task through the lifecycle, or refuse to.

The canonical body every Phase 4 and Phase 5 use case repeats:

    load -> authorize -> invoke domain -> persist -> commit -> map to result

Three alternatives are rejected, and each one is a shape a reader might expect.

A `TaskService` holding create, rename, assign and this operation as four
methods. ARC-04 and D-15 ask for one single-purpose class per use case instead:
a class with one job has one set of dependencies, so its constructor states
exactly what the operation touches, and a test cannot accidentally satisfy it
with ports the operation never uses.

`__call__` in place of a named `execute`. It reads well at one call site and
badly everywhere else - `use_case(command)` gives a reader nothing to grep for,
and D-15 fixes the name so every use case in the project answers to the same one.

Committing in a FastAPI `yield` dependency teardown. That works, and it moves
the transaction boundary into the web framework, so the same use case driven
from a worker or a test would silently lose its atomicity. ARC-08 and D-17 put
`commit()` here, on the success path only, where the code that knows the
operation succeeded is the code that makes it durable.

**On authorization:** this use case has no `AuthorizationError` branch, and that
is a decision rather than an omission. An actor who cannot see the task gets
`TaskNotFoundError` instead, per ADR-008: a 403 would confirm the task exists to
someone who is not entitled to know that, which is the IDOR leak AUTH-06 is
written against. A task whose list has vanished, and a task addressed under a
list it does not belong to (D-14), answer the same way and for the same reason:
`task_list_not_found` would carry a different code *and* a foreign identifier,
so it would distinguish exactly the cases ADR-008 requires to be
indistinguishable. The 403 leg of ADR-008 arrives in Phase 5 with the first
resource an actor can see but may not change, and the mapping from
`AuthorizationError` to a 403 problem body is already proven end to end by
`tests/api/test_error_contract.py` (plan 02-04).

That argument used to be implemented here, as a `get` plus an
`is None or not permitted` guard. It now lives in
`taskmanager.application.use_cases.access`, called as `visible_task`, because
ten sibling use cases in this phase were about to repeat the same block - and a
rule copied eleven times is a rule that gets forgotten once, silently, in
whichever copy nobody re-read. The load-and-authorize step is still visible at
this call site; only its body moved.

**On the assignee.** The old guard admitted `task.assignee_id == actor_id`
beside the list's owner, for ASGN-02. That clause is gone, deliberately and
temporarily, and is worth saying out loud rather than deleting in silence: D-04
scopes Phase 4 to the owner, and assignment does not exist yet - no endpoint in
this phase sets `assignee_id`, so nothing a request can do would reach the
clause. It would be an unreachable branch, and this project's coverage gate is
met by writing the test, never by a pragma or an omit. Phase 5 restores it in
`access.py`, where every use case picks it up at once, together with the 403 leg
the assignee capabilities finally create.
"""

from taskmanager.application.dto.commands import ChangeTaskStatusCommand
from taskmanager.application.dto.results import TaskResult
from taskmanager.application.ports.clock import Clock
from taskmanager.application.ports.unit_of_work import UnitOfWork
from taskmanager.application.use_cases.access import visible_task


class ChangeTaskStatus:
    """Moves one task to a requested status on behalf of an authenticated actor."""

    def __init__(self, uow: UnitOfWork, clock: Clock) -> None:
        # The unit of work first, then the non-transactional ports as separate
        # arguments (D-17). Nothing else is injected, because nothing else is
        # touched - which is the whole point of one class per use case.
        self._uow = uow
        self._clock = clock

    async def execute(self, command: ChangeTaskStatusCommand) -> TaskResult:
        """Run the operation, or raise the domain error that describes its refusal."""
        async with self._uow:
            # One call, four refusals, all of them `task_not_found`: absent,
            # under another list (D-14), orphaned, or on a list this actor does
            # not own. `access.py` argues each leg; the point here is that the
            # rule is entered rather than restated.
            task = await visible_task(
                self._uow, command.task_list_id, command.task_id, command.actor_id
            )
            # The entity owns the state machine and the timestamps; this line
            # is the only place the clock is read, and the instant is handed
            # down rather than looked up again (D-13).
            task.change_status(command.new_status, now=self._clock.now())
            await self._uow.tasks.update(task)
            await self._uow.commit()
        # Mapped outside the block: the result describes a transaction that has
        # already been made durable, never one still in flight.
        return TaskResult.from_entity(task)
