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

The two update commands are why `dto/unset.py` exists. A PATCH has three cases
per field - omitted, set to a value, set to null - and D-05 gives the last two
different outcomes, so `None` cannot also stand for the first. The rejected
alternatives were a `fields_set: frozenset[str]` beside plain optional fields,
which mypy cannot narrow because the set is stringly typed and the field stays
`str | None` whatever it contains, and a per-field `Patch[T]` wrapper, which
narrows correctly but adds a second DTO vocabulary beside ADR-020's frozen
dataclasses. `dto/unset.py` carries that argument in full; it is not repeated
here.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from taskmanager.application.dto.unset import UNSET, Unset
from taskmanager.domain.value_objects.task_priority import TaskPriority
from taskmanager.domain.value_objects.task_status import TaskStatus

# ---------------------------------------------------------------------------
# Task lists
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CreateTaskListCommand:
    """Ask for a new list named `name`, owned by `actor_id`."""

    actor_id: UUID
    name: str
    description: str | None


@dataclass(frozen=True, slots=True)
class GetTaskListCommand:
    """Ask for one list, on behalf of `actor_id`."""

    actor_id: UUID
    task_list_id: UUID


@dataclass(frozen=True, slots=True)
class ListTaskListsCommand:
    """Ask for every list `actor_id` owns.

    It carries nothing but the actor, and that is the point: there are no
    filter, sort or pagination fields because D-13 fixes the order and the
    phase declares no such parameters. A command with one field is still worth
    having - it keeps the use case's signature identical to its nine siblings,
    so a later filter is a field rather than a change of shape.
    """

    actor_id: UUID


@dataclass(frozen=True, slots=True)
class UpdateTaskListCommand:
    """Ask for a partial change to one list, on behalf of `actor_id`.

    Every patchable field is `X | Unset = UNSET`. `None` cannot serve as the
    "omitted" marker because it is a legal *value* for `description` - an
    explicit JSON null is how a client clears it (D-05) - so the two meanings
    need two markers. The router converts Pydantic's `model_fields_set` into
    this sentinel on the way in; the sentinel itself never appears in a request
    schema or in `/openapi.json` (04-RESEARCH Pattern 2).
    """

    actor_id: UUID
    task_list_id: UUID
    name: str | Unset = UNSET
    description: str | None | Unset = UNSET


@dataclass(frozen=True, slots=True)
class DeleteTaskListCommand:
    """Ask for one list to be deleted, with its tasks, on behalf of `actor_id`."""

    actor_id: UUID
    task_list_id: UUID


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CreateTaskCommand:
    """Ask for a new task inside `task_list_id`, on behalf of `actor_id`.

    `priority` is required and has no default here. `Task.DEFAULT_PRIORITY` is
    the single copy of TASK-01's `medium`, and the request schema's field
    default reads that ClassVar, so a default on this field would be a second
    copy of the same rule - two places that can drift apart, which is exactly
    the defect the ClassVar exists to prevent (04-RESEARCH Pitfall 6).
    """

    actor_id: UUID
    task_list_id: UUID
    title: str
    description: str | None
    priority: TaskPriority
    due_date: datetime | None


@dataclass(frozen=True, slots=True)
class GetTaskCommand:
    """Ask for one task addressed under `task_list_id`, on behalf of `actor_id`."""

    actor_id: UUID
    task_list_id: UUID
    task_id: UUID


@dataclass(frozen=True, slots=True)
class ListTasksCommand:
    """Ask for the tasks of one list, optionally filtered (TASK-06).

    `status` and `priority` use plain `None` rather than the sentinel, and that
    is not an inconsistency with the update commands: an absent filter and a
    "null filter" are the same request, so there is only ever one meaning to
    express. The statistics the answer carries describe the whole list whatever
    these two say (D-09).
    """

    actor_id: UUID
    task_list_id: UUID
    status: TaskStatus | None = None
    priority: TaskPriority | None = None


@dataclass(frozen=True, slots=True)
class UpdateTaskCommand:
    """Ask for a partial change to one task, on behalf of `actor_id`.

    There is deliberately **no `status` field**. D-08 makes the dedicated
    endpoint the only door onto the state machine, and declaring it here would
    be the first step back toward a generic PATCH that writes it - the command
    would exist before the route did, and the route would then look like an
    omission rather than a decision. TASK-03 is proven by its absence.

    The same `X | Unset = UNSET` rule as `UpdateTaskListCommand` applies to
    every field that is here, for the same D-05 reason: `description` and
    `due_date` both accept an explicit null as a value.
    """

    actor_id: UUID
    task_list_id: UUID
    task_id: UUID
    title: str | Unset = UNSET
    description: str | None | Unset = UNSET
    priority: TaskPriority | Unset = UNSET
    due_date: datetime | None | Unset = UNSET


@dataclass(frozen=True, slots=True)
class DeleteTaskCommand:
    """Ask for one task to be deleted, on behalf of `actor_id`."""

    actor_id: UUID
    task_list_id: UUID
    task_id: UUID


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
