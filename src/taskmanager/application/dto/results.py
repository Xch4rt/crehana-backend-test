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
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from taskmanager.domain.entities.task import Task
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
