"""The three persistence ports, expressed entirely in domain entities.

The rejected alternative is a repository that hands back ORM rows, or a
SQLAlchemy `Result` the use case has to unpack. That shape would drag the
persistence library's vocabulary - and its lazy-loading behaviour - straight
into the application layer, and every use-case test would then need a database
to produce a single object. These signatures speak only `Task`, `TaskList`,
`User` and `CompletionStats`, which is exactly what lets the use cases be
exercised against in-memory fakes with no I/O at all. That is also where this
project's coverage comes from: the application layer is pure orchestration, so
ten fast unit tests move the number further than twenty integration tests.

`completion_stats` is a port method rather than something a use case computes by
listing tasks and counting them in Python, because ADR-009 puts the percentage
behind a single `COUNT(*) FILTER (...)` aggregate. The adapter that runs that
query is Phase 3's; the contract it has to satisfy is here.

Every method is `async` (D-19): each one is a database round trip in the real
adapter, and a uniform surface means a Phase 4 use case never has to remember
which call needs `await`.
"""

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from taskmanager.domain.entities.task import Task
from taskmanager.domain.entities.task_list import TaskList
from taskmanager.domain.entities.user import User
from taskmanager.domain.value_objects.completion import CompletionStats
from taskmanager.domain.value_objects.task_priority import TaskPriority
from taskmanager.domain.value_objects.task_status import TaskStatus


class TaskRepository(Protocol):
    """Persistence for the `Task` aggregate, plus the list-level counters."""

    async def get(self, task_id: UUID) -> Task | None: ...

    async def add(self, task: Task) -> None: ...

    async def update(self, task: Task) -> None: ...

    async def delete(self, task_id: UUID) -> None: ...

    # TASK-06: filtering by status and by priority is a requirement of the
    # listing endpoint, so it belongs in the query the adapter issues rather
    # than in a comprehension the use case applies to a full table read.
    async def list_for_task_list(
        self,
        task_list_id: UUID,
        *,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
    ) -> Sequence[Task]: ...

    async def completion_stats(self, task_list_id: UUID) -> CompletionStats: ...


class TaskListRepository(Protocol):
    """Persistence for the `TaskList` aggregate root."""

    async def get(self, task_list_id: UUID) -> TaskList | None: ...
    async def add(self, task_list: TaskList) -> None: ...
    async def update(self, task_list: TaskList) -> None: ...
    async def delete(self, task_list_id: UUID) -> None: ...
    async def list_for_owner(self, owner_id: UUID) -> Sequence[TaskList]: ...

    # LIST-06: the entity cannot see its siblings, so the per-owner name
    # uniqueness pre-check lives in a use case and asks the repository here.
    # The unique index is still the authority; this only buys a clean 409.
    async def exists_with_name(self, owner_id: UUID, name: str) -> bool: ...


class UserRepository(Protocol):
    """Persistence for the `User` entity and the login lookup."""

    async def get(self, user_id: UUID) -> User | None: ...

    # Lookup by address, not by a search predicate: `User` already stores the
    # canonical lowercased form, so the adapter compares what it was given.
    async def get_by_email(self, email: str) -> User | None: ...
    async def add(self, user: User) -> None: ...
    async def list_all(self) -> Sequence[User]: ...
