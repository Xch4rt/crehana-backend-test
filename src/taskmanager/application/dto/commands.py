"""Command DTOs: the inputs use cases accept, and the convention they all follow.

Phase 4 will look for the convention here, so it is stated once rather than
repeated per command. Every command is an immutable
`@dataclass(frozen=True, slots=True)` whose **first field is `actor_id: UUID`** -
the authenticated caller, which presentation fills from the JWT subject in Phase
5 and never from anything the client sent in a body or a path. Everything a use
case is allowed to see or change derives from that one field, which is why it
comes first: a command missing it would fail construction rather than quietly
authorize itself.

The use case, never the router, then decides visibility versus permission per
ADR-008 - 404 for a resource the actor cannot see, 403 for one they can see but
may not change. Putting that in the router would scatter the rule across every
endpoint and make the 404-not-403 leg a thing each one could forget.

The rejected alternative is Pydantic models for commands. Shape validation
already happened once, at the HTTP boundary, where the request schema rejected
a malformed payload before a command object existed; running it again here buys
nothing and makes the application layer depend on the web stack's validation
library (D-16). `frozen=True` means a use case cannot rewrite its own input
halfway through, and `slots=True` means a misspelled field is an `AttributeError`
at the call site rather than an ignored keyword.
"""

from dataclasses import dataclass
from uuid import UUID

from taskmanager.domain.value_objects.task_status import TaskStatus


@dataclass(frozen=True, slots=True)
class ChangeTaskStatusCommand:
    """Ask for a task to move to `new_status`, on behalf of `actor_id`.

    `task_list_id` is the list the task was addressed *under*, which is not the
    same thing as the task's own parent: the use case compares the two and
    refuses a mismatch with the answer an absent task gets (D-14). It is part of
    the request because D-11 nests the endpoint under `{list_id}`, and a nested
    path whose parent segment never reaches the use case is a defect rather than
    a simplification - it would let any list the actor owns stand in for the
    real one, which is an ownership check that passes while checking nothing.
    """

    actor_id: UUID
    task_list_id: UUID
    task_id: UUID
    new_status: TaskStatus
