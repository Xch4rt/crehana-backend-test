"""The runtime `EmailNotifier`: the invitation is composed, logged, and not sent.

Nothing is transmitted from here, and that is the requirement rather than a
shortcut taken under time pressure. FEATURES asks for a *simulated* invitation,
NOTF-02 makes the simulation the deliverable, and
`application/ports/notifications.py` already argues that the port exists so the
choice is visible as an adapter swap instead of being hidden inside the use
case that assigns a task. Replacing this class is the whole change the day real
delivery is wanted; nothing above it moves.

What it writes is D-15's line: one INFO record on `taskmanager.notifications`
carrying `event`, `to`, `subject`, `body` and `task_id` as separate fields, so
`docker compose logs api | grep task_assigned_email` finds it. That record is
only *emitted* because `infrastructure/logging.py` attaches a JSON handler to
the `taskmanager` tree - uvicorn configures its own loggers and nothing else,
so without that call this method would run, return, and produce no output at
all.

**Email header injection (T-5-14) is not applicable yet, and must be re-raised
the day a real SMTP adapter appears.** It is not mitigated here; it simply
cannot occur, because no header is ever constructed and no message is ever
handed to a transport. The recipient address and the task title below are both
caller-supplied text, and both would become header material in a real
implementation - a CR or LF in either is the whole attack. The deferral is
written here, in the file that would be replaced, rather than in a threat
register nobody reads while writing the replacement.

What *is* mitigated here is T-5-13, and it is mitigated by construction rather
than by this module: every field goes through `json.dumps` in the formatter, so
a newline inside a task title is escaped and a title cannot forge a second log
record.
"""

import logging
from uuid import UUID

# The logger is named explicitly rather than taken from `__name__`. `__name__`
# here is `taskmanager.infrastructure.notifications.logging`, which is a
# perfectly good logger and the wrong one: D-15 names
# `taskmanager.notifications` as the handle an operator filters on, and a name
# that tracked this module's path would change the day the file moved.
LOGGER_NAME = "taskmanager.notifications"

# Where the recipient actually finds the task. The port carries `task_id` but
# not `task_list_id` - deliberately, since it is the assignment that is being
# announced and not the list - so a nested `/task-lists/{id}/tasks/{id}` URL
# cannot be constructed from what this method is given. The flat discovery
# route (D-02) can, it is the route an assignee would use anyway, and widening
# the port to carry a second identifier for the sake of a log line is not a
# trade worth making.
ASSIGNED_TASKS_PATH = "/api/v1/tasks/assigned-to-me"

logger = logging.getLogger(LOGGER_NAME)


class LoggingEmailNotifier:
    """Writes the assignment invitation to the log and transmits nothing."""

    async def send_task_assigned(
        self,
        *,
        recipient_email: str,
        task_title: str,
        task_id: UUID,
    ) -> None:
        """Emit exactly one structured record describing the email not sent."""
        subject = f"You have been assigned a task: {task_title}"
        body = (
            f'You have been assigned the task "{task_title}". '
            f"Open {ASSIGNED_TASKS_PATH} to see every task assigned to you."
        )
        logger.info(
            "Task assignment invitation",
            extra={
                "event": "task_assigned_email",
                "to": recipient_email,
                "subject": subject,
                "body": body,
                # Stringified here, not in the formatter: a `UUID` is not
                # JSON-serialisable, so `json.dumps` would raise while
                # rendering the record and a notification would turn into a
                # logging failure.
                "task_id": str(task_id),
            },
        )
