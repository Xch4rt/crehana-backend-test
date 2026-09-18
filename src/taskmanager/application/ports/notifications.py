"""The outbound notification port: telling an assignee a task is theirs.

The rejected alternative is sending the message inline from the use case that
assigns a task. That makes the use case untestable without a mail server, and -
worse - it makes a notifier outage indistinguishable from a failed assignment,
because the exception the client sees comes from the same call stack as the
write. Behind this port, whether a delivery failure aborts the operation or is
merely recorded becomes a decision a use case states explicitly, instead of an
accident of where the call happened to sit.

FEATURES calls for a simulated invitation rather than real delivery, so Phase
5's adapter logs the message. The port exists so that choice is visible as an
adapter swap rather than hidden inside a use case.

Every parameter is keyword-only: `recipient_email` and `task_title` are both
strings, and a positional call site would be one transposition away from mailing
a title to an address-shaped nothing with no test noticing.
"""

from typing import Protocol
from uuid import UUID


class EmailNotifier(Protocol):
    """Sends the one message this product has: a task assignment notice."""

    async def send_task_assigned(
        self,
        *,
        recipient_email: str,
        task_title: str,
        task_id: UUID,
    ) -> None: ...
