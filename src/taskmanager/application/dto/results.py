"""Result DTOs: the flat, immutable answers use cases return.

A use case returns one of these rather than the entity it just changed, and the
difference matters twice. It means a response can never carry a mutable
aggregate across the layer boundary, where a router or a serialiser could edit
it after the transaction closed. And it means nothing reaches presentation that
might still be attached to a session: Phase 3 configures its relationships with
`lazy="raise"` precisely so an accidental lazy load fails loudly, and a frozen
copy taken inside the transaction cannot trigger one at all.

The second payoff is for Phase 4: a response schema needs a stable field list to
map from, and `TaskResult` is that list. When the entity gains a field, adding it
here is a deliberate step rather than an automatic leak into the public API.

There is deliberately no wrapper around a collection of task lists: `ListTaskLists`
returns a plain `tuple[TaskListResult, ...]`. A class carrying nothing but a tuple
would be a name the API shape never asks for, because D-10 puts the counters on
each entry rather than on the collection. `TaskCollectionResult` exists for the
opposite reason - D-09 gives the *tasks* envelope statistics of its own, which a
bare tuple has nowhere to keep.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from taskmanager.domain.entities.task import Task
from taskmanager.domain.entities.task_list import TaskList
from taskmanager.domain.entities.user import User
from taskmanager.domain.value_objects.completion import CompletionStats
from taskmanager.domain.value_objects.task_priority import TaskPriority
from taskmanager.domain.value_objects.task_status import TaskStatus


@dataclass(frozen=True, slots=True)
class TaskResult:
    """One task, flattened out of the aggregate at a single moment in time."""

    id: UUID
    task_list_id: UUID
    title: str
    description: str | None
    status: TaskStatus
    priority: TaskPriority
    created_at: datetime
    updated_at: datetime
    due_date: datetime | None
    completed_at: datetime | None
    assignee_id: UUID | None

    @classmethod
    def from_entity(cls, task: Task) -> "TaskResult":
        """Copy every field of the entity, naming each one explicitly.

        Written out rather than derived from `dataclasses.asdict` or a
        `**vars(task)` splat: those forms would carry a newly added entity
        field into an API response the moment someone declared it, which is the
        opposite of the boundary this class exists to be.
        """
        return cls(
            id=task.id,
            task_list_id=task.task_list_id,
            title=task.title,
            description=task.description,
            status=task.status,
            priority=task.priority,
            created_at=task.created_at,
            updated_at=task.updated_at,
            due_date=task.due_date,
            completed_at=task.completed_at,
            assignee_id=task.assignee_id,
        )


@dataclass(frozen=True, slots=True)
class TaskListResult:
    """One task list, flattened, with the completion counters D-10 requires.

    The three statistics are part of *every* task-list answer - the collection,
    the single GET, the POST and the PATCH all return this one shape - so a
    client never has to make a second call to learn how far along a list is, and
    the API never has two list shapes that could drift apart.

    They always describe the **whole list**. Nothing here is ever computed over
    a filtered view: a filter describes what the caller is looking at, while the
    number describes the list (ADR-009).
    """

    id: UUID
    owner_id: UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime
    total_tasks: int
    completed_tasks: int
    completion_percentage: float

    @classmethod
    def from_entity(
        cls, task_list: TaskList, stats: CompletionStats
    ) -> "TaskListResult":
        """Copy every field of the entity, naming each one explicitly.

        Written out for the reason `TaskResult.from_entity` gives: an `asdict`
        or a `**vars()` splat would publish a newly added entity field the
        moment someone declared it.

        `stats.percentage` is read as a **property**, without parentheses -
        04-CONTEXT.md writes it as a call, and following that spelling would
        raise `TypeError` here. It already rounds to two decimals and already
        answers `0.0` for an empty list, so no arithmetic and no division guard
        belongs in this method.
        """
        return cls(
            id=task_list.id,
            owner_id=task_list.owner_id,
            name=task_list.name,
            description=task_list.description,
            created_at=task_list.created_at,
            updated_at=task_list.updated_at,
            total_tasks=stats.total,
            completed_tasks=stats.completed,
            completion_percentage=stats.percentage,
        )


@dataclass(frozen=True, slots=True)
class TaskCollectionResult:
    """The tasks of one list, plus that list's whole-list statistics (D-09).

    `items` carries what the caller asked to see - TASK-06's status and priority
    filters apply to it - while the three counters describe the entire list
    whatever the filter said. That asymmetry is the decision, not an oversight:
    a percentage that moved when a client changed a filter would be a different
    number wearing the same name.

    `items` is a `tuple` rather than a `list` because the dataclass is frozen: a
    list field would leave the contents editable straight through the frozen
    wrapper, which is the one thing freezing is here to prevent.
    """

    items: tuple[TaskResult, ...]
    total_tasks: int
    completed_tasks: int
    completion_percentage: float

    @classmethod
    def from_parts(
        cls, tasks: Sequence[Task], stats: CompletionStats
    ) -> "TaskCollectionResult":
        """Build the envelope from the two things the use case just read.

        The `tuple(TaskResult.from_entity(...))` conversion has one home here
        rather than one copy per call site, so the tuple-not-list rule above
        cannot be honoured in one use case and forgotten in the next.

        `stats` arrives from a query that never sees the filter arguments, which
        is what makes the counters whole-list by construction rather than by
        convention.
        """
        return cls(
            items=tuple(TaskResult.from_entity(task) for task in tasks),
            total_tasks=stats.total,
            completed_tasks=stats.completed,
            completion_percentage=stats.percentage,
        )


@dataclass(frozen=True, slots=True)
class UserResult:
    """One account, as every profile answer in the API shows it (D-09).

    Four fields, and the interesting thing about this class is the fifth one it
    does not have. `User` holds a `password_hash`, and it is deliberately not
    copied below - which is the field-by-field rule of `TaskResult.from_entity`
    earning its keep rather than a style preference. A `**vars(user)` splat or
    a `dataclasses.asdict` would carry the stored Argon2 hash into an API
    response the moment anybody wrote one, and nothing between here and the
    wire would object: a response schema built from this type would simply have
    a field to fill. `test_dtos.py` asserts the absence against
    `dataclasses.fields`, so a rename cannot smuggle it back (T-5-04).

    `updated_at` is absent for a duller reason: AUTH-05 and AUTH-01 both
    describe the profile as `{id, email, full_name, created_at}`, and a field
    published once is a field that has to keep being published.
    """

    id: UUID
    email: str
    full_name: str
    created_at: datetime

    @classmethod
    def from_entity(cls, user: User) -> "UserResult":
        """Copy the four public fields, naming each one explicitly.

        The one field of `User` that is missing here is `password_hash`, and
        its omission is the whole design of this class - see the docstring
        above. `updated_at` is omitted too, because the published profile shape
        has never carried it.
        """
        return cls(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            created_at=user.created_at,
        )


@dataclass(frozen=True, slots=True)
class AccessTokenResult:
    """The answer to a successful login (AUTH-02).

    There is no `from_entity` because there is no entity: a token is minted by
    the `TokenService` port and assembled by `Login`, so nothing was read that
    this could map from.

    Both of the fields beside the token are wire-format obligations rather than
    internal choices, which is why they are spelled out here:

    * `token_type` carries the literal lowercase `bearer`. OAuth2 says the value
      is case-insensitive, but Swagger UI's Authorize button and a good many
      clients build the header by concatenation, so `Bearer` and `bearer` are
      not interchangeable in practice - and the header this produces is what
      `OAuth2PasswordBearer` parses on the way back in.
    * `expires_in` is a number of **seconds**, not minutes: the setting is
      `jwt_expire_minutes`, so the use case multiplies, and the name of this
      field is the only place that says which unit crossed the boundary.
    """

    access_token: str
    token_type: str
    expires_in: int
