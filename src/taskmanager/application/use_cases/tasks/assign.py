"""Hand a task to a user, and tell them - without letting the telling undo it.

`AssignTask` is where four separate decisions meet, and none of them is visible
from the route:

* **The door is owner-only (D-03).** It loads through
  `owned_task(..., for_update=True)`, so the list's owner is answered, the
  task's own assignee is refused with a 403 they can already disprove with a
  `GET`, and everybody else is refused exactly as an absent task is refused.
  `access.py` argues each leg; the point here is that the rule is entered
  rather than restated.
* **The guard runs before the assignee is looked up (T-5-12).** See the comment
  at the call site - reversing the two turns this route into a user-existence
  oracle.
* **A repeat is a no-op (D-07).** Assigning the user who is already there
  changes nothing, makes nothing durable and sends nothing.
* **The notification happens after the write is durable, and cannot undo it
  (D-16, NOTF-01, NOTF-03).** It is attempted outside the transaction block,
  inside a `try`/`except` that records the failure and swallows it.
"""

import logging

from taskmanager.application.dto.commands import AssignTaskCommand
from taskmanager.application.dto.results import TaskResult
from taskmanager.application.ports.clock import Clock
from taskmanager.application.ports.notifications import EmailNotifier
from taskmanager.application.ports.unit_of_work import UnitOfWork
from taskmanager.application.use_cases.access import owned_task
from taskmanager.domain.exceptions import UserNotFoundError

# Stdlib, and therefore legal here: `.importlinter`'s application-framework-free
# contract forbids the web framework, the ORM and the two security libraries,
# none of which this is. `presentation/api/errors/handlers.py` sets the
# precedent for logging from a use-case-shaped module at all.
logger = logging.getLogger(__name__)


class AssignTask:
    """Assigns one task to a user on behalf of the list's owner (ASGN-01)."""

    def __init__(self, uow: UnitOfWork, clock: Clock, notifier: EmailNotifier) -> None:
        # The unit of work first, then the non-transactional ports as separate
        # arguments (D-17) - and here there are two of them.
        #
        # `change_task_status.py` says "nothing else is injected, because
        # nothing else is touched", and that sentence is exactly what justifies
        # the third argument rather than contradicting it: this use case *does*
        # touch something else. The constructor is the honest statement of it,
        # which is the whole point of one class per operation.
        self._uow = uow
        self._clock = clock
        self._notifier = notifier

    async def execute(self, command: AssignTaskCommand) -> TaskResult:
        """Assign the task, then attempt the notification the assignment owes."""
        async with self._uow:
            # **First, always.** Reversing this with the lookup below turns the
            # route into a user-existence oracle for a caller who cannot see
            # the task: they would get `user_not_found` for an invented id and
            # `task_not_found` for a real one, and the difference between the
            # two answers is the disclosure (T-5-12, 05-RESEARCH Pitfall 13).
            # For an *owner* that disclosure is harmless - `GET /users` already
            # lists everyone (D-08) - but it must not be reachable by someone
            # the door has already refused.
            #
            # `for_update=True` because this is read-validate-write, and it
            # holds the task only: a task's writer never holds its list
            # (ADR-058).
            task = await owned_task(
                self._uow,
                command.task_list_id,
                command.task_id,
                command.actor_id,
                for_update=True,
            )
            # Only now, with the caller established as the owner, is the
            # caller-supplied identifier resolved at all.
            assignee = await self._uow.users.get(command.assignee_id)
            if assignee is None:
                raise UserNotFoundError(command.assignee_id)
            # D-07, and it returns *before* the write and before the send. It
            # mirrors `Task.change_status`'s same-state no-op, but it cannot
            # live in `Task.assign`: idempotence here has to skip a durable
            # write and an email as well as a field, and the entity can skip
            # neither - which is why it deliberately carries no such guard.
            if task.assignee_id == command.assignee_id:
                return TaskResult.from_entity(task)
            # The entity owns the timestamps; the clock is read once here and
            # the instant handed down (D-13).
            task.assign(assignee.id, now=self._clock.now())
            await self._uow.tasks.update(task)
            await self._uow.commit()
            # Captured **inside** the block, as plain strings. The unit of work
            # unbinds its repositories on exit and the port documents any use
            # afterwards as a `RuntimeError`, so reaching for `assignee.email`
            # below would be a failure waiting for the first time someone moves
            # a line.
            recipient_email = assignee.email
            task_title = task.title

        # Outside the block, and therefore after the write is durable: a
        # notifier having a bad day cannot take the assignment down with it
        # (D-16, NOTF-01).
        try:
            await self._notifier.send_task_assigned(
                recipient_email=recipient_email,
                task_title=task_title,
                task_id=task.id,
            )
        except Exception:
            # Broad on purpose, and not laziness: NOTF-03 says *no* delivery
            # failure may fail the assignment, so narrowing this to the
            # exceptions today's adapter happens to raise would let tomorrow's
            # adapter break a requirement by raising something else.
            #
            # **No `noqa` here, and that was measured rather than assumed.**
            # 05-RESEARCH expected bugbear to flag this shape and
            # `docker/entrypoint.sh` carries a `# noqa: BLE001` for it - but
            # that file is a shell heredoc flake8 never reads, and the
            # installed plugin set (bugbear + comprehensions + pep8-naming)
            # emits nothing at all here: the line was run without a suppression
            # and flake8 exited 0. BLE001 is a Ruff code. A `noqa` naming a
            # code that cannot fire suppresses nothing and tells a later reader
            # the opposite of the truth; the capture is in
            # `evidence/05-08-broad-except-lint.txt`.
            #
            # The record names the task **id** and carries the traceback. It
            # does not name the title: that is caller-supplied text, and a log
            # line is not where to discover what it does to a parser (T-5-13).
            # `exc_info=True` rather than `handlers.py`'s `exc_info=exc`,
            # because here there genuinely is an ambient exception.
            logger.warning(
                "Assignment notification failed for task %s", task.id, exc_info=True
            )
        # Mapped outside the block: the result describes a transaction that has
        # already been made durable, never one still in flight.
        return TaskResult.from_entity(task)
