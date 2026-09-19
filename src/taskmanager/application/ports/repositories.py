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

**`get_for_update` is the write-path read (ADR-058, Phase 4 review CR-01).** Every
mutating use case is read-validate-write: it loads an entity, asks the entity
whether the change is legal, and writes the whole entity back. Between two
overlapping requests that is a lost update, and for a task it is worse - the
second writer validates a status transition against a state the first writer has
already replaced, and persists a transition the state machine forbids. The
contract of `get_for_update` is what closes that window, and it is stated in
domain terms because the application layer has no others:

* the entity it returns is the **latest committed state**, never a cached copy;
* from the moment it returns until the unit of work ends, **no other unit of work
  can obtain the same entity through `get_for_update`** - a second caller waits,
  and then sees whatever the first one committed;
* it is for a caller that is about to `update` or `delete` what it loaded. A read
  path must keep calling `get`, which never waits on a writer.

How an adapter honours that is its own business - the SQLAlchemy one takes a row
lock - and nothing in the signature says so. Phase 5's assignee capabilities and
its assignment use case are further writers of the same task row, and they enter
through this same method.
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

    # The write-path read; see the module docstring for the three guarantees.
    async def get_for_update(self, task_id: UUID) -> Task | None: ...

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

    # D-02: the assigned-tasks collection behind `GET /tasks/assigned-to-me`,
    # and the only query in this project whose answer is not scoped to one list.
    # The argument makes the same point `list_for_task_list` makes above: the
    # filter belongs in the query the adapter issues rather than in a
    # comprehension the use case applies to a full table read - which here would
    # mean reading *every* task in the database to return one caller's few.
    #
    # No `status` or `priority` keyword, and that is a decision rather than an
    # oversight: filtering `assigned-to-me` is a Deferred Idea in 05-CONTEXT,
    # not part of ASGN-02. Widening the signature later is additive; a caller
    # that grew to depend on filters nobody asked for is not.
    async def list_for_assignee(self, assignee_id: UUID) -> Sequence[Task]: ...

    async def completion_stats(self, task_list_id: UUID) -> CompletionStats: ...


class TaskListRepository(Protocol):
    """Persistence for the `TaskList` aggregate root."""

    async def get(self, task_list_id: UUID) -> TaskList | None: ...

    # The write-path read; see the module docstring for the three guarantees.
    async def get_for_update(self, task_list_id: UUID) -> TaskList | None: ...

    async def add(self, task_list: TaskList) -> None: ...
    async def update(self, task_list: TaskList) -> None: ...
    async def delete(self, task_list_id: UUID) -> None: ...
    async def list_for_owner(self, owner_id: UUID) -> Sequence[TaskList]: ...

    # LIST-03 puts the counters on *every* entry of the collection, so asking
    # for them one list at a time - `list_for_owner` followed by a
    # `completion_stats` per row - is the N+1 the requirement exists to forbid.
    # This method is the whole collection and its statistics together, which the
    # adapter answers with one grouped statement.
    #
    # A bare `tuple` rather than a new domain value object, and domain types
    # rather than a row: the naming belongs on the application result DTO, which
    # is the layer that has a word for "a list and how far through it we are",
    # and CLAUDE.md's repositories rule forbids an ORM row crossing into
    # `application` at all.
    async def list_for_owner_with_stats(
        self, owner_id: UUID
    ) -> Sequence[tuple[TaskList, CompletionStats]]: ...

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
