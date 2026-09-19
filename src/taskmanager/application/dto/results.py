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
