"""Command DTOs: the inputs use cases accept, and the convention they all follow.

Phase 4 will look for the convention here, so it is stated once rather than
repeated per command. Every command is an immutable
`@dataclass(frozen=True, slots=True)` whose **first field is `actor_id: UUID`** -
the authenticated caller, which presentation fills from the JWT subject in Phase
5 and never from anything the client sent in a body or a path. Everything a use
case is allowed to see or change derives from that one field, which is why it
comes first: a command missing it would fail construction rather than quietly
authorize itself.

Phase 5 introduces the only three exceptions, all of them in the auth section
at the bottom of this file: `RegisterUserCommand` and `LoginCommand` run before
an identity exists, and `AuthenticateActorCommand` is the one whose result *is*
the actor. They are exceptions to the field, never to the rule - none of them
lets a caller name an identity they were not given - and each says so in its
own docstring. `test_dtos.py` holds the same three in an exemption set and
derives that set back off the command table, so the convention stays a gate for
the other eleven rather than decaying into a preference.

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


@dataclass(frozen=True, slots=True)
class AssignTaskCommand:
    """Ask for `task_id` to be handed to `assignee_id`, on behalf of `actor_id`.

    It mirrors `ChangeTaskStatusCommand` field for field, with `assignee_id`
    where that one carries `new_status`, and for the same D-11 reason:
    assignment has its own door (D-05) nested under `{list_id}`, so the parent
    segment has to reach the use case or any list the actor owns would stand in
    for the real one.

    **This is the only command in the project with a field naming somebody other
    than the actor**, and that is what makes T-5-10 checkable rather than
    conventional: `UpdateTaskCommand` has no `assignee_id`, so a generic PATCH
    has nothing to write the field through even if a router tried. `test_dtos.py`
    asserts that uniqueness across the whole command table.

    `actor_id` still comes first, and the two identifiers are not
    interchangeable: `actor_id` is the authenticated caller, filled from the
    token's subject, while `assignee_id` is attacker-controlled input that
    `AssignTask` resolves against the users table *after* the ownership guard
    has already run (T-5-12).
    """

    actor_id: UUID
    task_list_id: UUID
    task_id: UUID
    assignee_id: UUID


@dataclass(frozen=True, slots=True)
class UnassignTaskCommand:
    """Ask for one task to lose its assignee, on behalf of `actor_id`.

    Identical in shape to `DeleteTaskCommand`, because the request is: the
    `DELETE` of D-05 carries no body, so there is nothing to name but the task
    and the list it was addressed under. Whose assignment is being cleared is
    never a field - the list owner unassigns whoever is there (ASGN-01), and a
    command that named the current assignee would invite a caller to guess.
    """

    actor_id: UUID
    task_list_id: UUID
    task_id: UUID


@dataclass(frozen=True, slots=True)
class ListAssignedTasksCommand:
    """Ask for every task assigned to `actor_id`, across every list (D-02).

    One field, and it is the actor - deliberately, for the reason
    `GetProfileCommand` gives about `/auth/me`. There is no `assignee_id` here,
    so `GET /tasks/assigned-to-me` cannot be pointed at somebody else's
    workload by editing a query string: the only id the query can filter on is
    the one presentation read off the token (T-5-11).
    """

    actor_id: UUID


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ListUsersCommand:
    """Ask for the user directory, on behalf of any authenticated caller.

    It carries the actor and nothing else, following `ListTaskListsCommand`'s
    argument that a one-field command keeps every `execute` signature uniform.
    The actor is not a filter here - D-13 makes this endpoint the same answer
    for everyone - but it is still required, because the field is what says the
    caller was authenticated at all. `ListUsers`' docstring argues that
    trade-off in full.
    """

    actor_id: UUID


# ---------------------------------------------------------------------------
# Auth
#
# Three of the four commands below carry no `actor_id`, which the module
# docstring above declares as the universal rule. They are the only exceptions
# in the project and each one states its own reason: two of them run before an
# identity exists, and the third is the one whose entire job is to produce the
# identity every other command starts with. `test_dtos.py` names the same three
# in an exemption set and derives that set back off the command table, so a
# fourth cannot join them by being forgotten.
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RegisterUserCommand:
    """Ask for a new account (AUTH-01).

    **No `actor_id`, and no way to add one.** This is the operation that
    *creates* an identity, so there is no authenticated caller to name: the
    endpoint is open by definition and everything here is attacker-controlled.
    The three fields are the whole surface a request gets to influence - there
    is no `id`, no `created_at` and no role - because the identifier comes from
    `uuid4()` in the use case and the timestamps from the `Clock` port (T-5-09).

    `password` is a plain `str` rather than Pydantic's redacting secret-string
    type, and that is worth writing down because nothing would fail if it were
    not: `.importlinter` deliberately leaves `pydantic` off this layer's
    forbidden list, as a convention rather than a gate. The convention is
    ADR-020's - every DTO is a frozen dataclass and the application layer names
    no validation library - so the wrapper stays on the schema side, where
    `to_command()` unwraps it on the way in. The plaintext lives for exactly as long
    as it takes `RegisterUser` to hand it to the `PasswordHasher` port; the
    domain never sees it and no result carries it.
    """

    email: str
    full_name: str
    password: str


@dataclass(frozen=True, slots=True)
class LoginCommand:
    """Ask for an access token in exchange for a credential (AUTH-02).

    **No `actor_id`** for the same reason `RegisterUserCommand` has none: the
    caller has not been identified yet, and this is the operation that
    identifies them. A command that carried an actor here would be a command
    that authenticated itself.

    `email` rather than `username`, deliberately: OAuth2 fixes the *form field*
    name to `username` and this API's usernames are email addresses, so the
    rename happens once, in the schema that reads the form (plan 05-11), and the
    application layer is left saying what it means.

    `password` travels as a plain `str`, for the reason above.
    """

    email: str
    password: str


@dataclass(frozen=True, slots=True)
class AuthenticateActorCommand:
    """Ask who a bearer token belongs to (D-11).

    **No `actor_id`, necessarily**: its single field is the raw token, and this
    is the command whose result *is* the `actor_id` every other command starts
    with. Naming one here would be circular.

    It stays a one-field command rather than a bare `str` argument to
    `execute`, following the argument `ListTaskListsCommand` makes above: a
    uniform signature across every use case means a later field - a token type,
    an audience, a scope - is an addition rather than a change of shape.
    """

    token: str


@dataclass(frozen=True, slots=True)
class GetProfileCommand:
    """Ask for the authenticated caller's own profile (AUTH-05).

    One field, and it is the actor - so unlike its three neighbours this one
    follows the rule. A profile request can only ever be about the caller:
    there is no `user_id` field, so `GET /auth/me` cannot be pointed at somebody
    else's account by editing a path.
    """

    actor_id: UUID
