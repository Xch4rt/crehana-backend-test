# Architecture Research

**Domain:** Layered / hexagonal REST API (FastAPI + PostgreSQL) — Task Manager technical challenge
**Researched:** 2026-09-17
**Confidence:** HIGH (framework mechanics verified against official docs; structural opinions are MEDIUM — they are design judgement, not facts)

---

## Executive Position

The brief asks for "Domain, Application/UseCases, Infrastructure". We build **four** layers
(adding Presentation) in a **src layout**, with a **linear dependency order enforced by
import-linter** and a pytest wrapper so the rule is a *test*, not a folder convention.

Three opinionated calls drive everything below:

1. **Domain = stdlib dataclasses + Enums. Pydantic lives at the application DTO boundary and
   above.** The brief's "strong typing with Pydantic" is satisfied loudly and visibly (request
   schemas, response schemas, command/result DTOs, settings) without making the innermost layer
   depend on a validation framework. Documented in `DECISION_LOG.md`.
2. **Ports are `typing.Protocol`, all of them in `application/ports/`.** Domain has *zero*
   imports outside the standard library — the strongest, easiest-to-prove architectural claim
   available, and it makes the layers contract trivially linear.
3. **Transactions are committed explicitly by the Unit of Work inside the use case**, never by a
   FastAPI dependency's exit code. This is not style — it is correctness (see Anti-Pattern 1).

---

## Standard Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│  main.py — COMPOSITION ROOT (app factory, wiring, handler registration)   │
├──────────────────────────────────────────────────────────────────────────┤
│                           PRESENTATION (driving adapter)                  │
│  ┌──────────┐  ┌───────────┐  ┌──────────────┐  ┌────────────────────┐   │
│  │ routers  │  │ schemas   │  │ auth dep     │  │ error handlers     │   │
│  │ (HTTP)   │  │ (Pydantic)│  │ (Bearer→user)│  │ (→ problem+json)   │   │
│  └────┬─────┘  └─────┬─────┘  └──────┬───────┘  └─────────┬──────────┘   │
│       │              │               │                    │              │
│       └──────────────┴───────────────┴────────────────────┘              │
│                              │ calls use case                            │
├──────────────────────────────┼───────────────────────────────────────────┤
│                       APPLICATION (use cases + ports)                     │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │  one class per use case:  CreateTaskList, ChangeTaskStatus, ...     │  │
│  │  __init__(uow, hasher, tokens, notifier)   async execute(cmd)->DTO  │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │  PORTS (Protocol): TaskListRepository │ TaskRepository │            │  │
│  │  UserRepository │ UnitOfWork │ PasswordHasher │ TokenService │      │  │
│  │  EmailNotifier │ Clock                                              │  │
│  └────────────────────────────────────────────────────────────────────┘  │
├──────────────────────────────────────────────────────────────────────────┤
│                    DOMAIN (pure Python — no imports out)                  │
│  ┌──────────────────┐  ┌────────────────────┐  ┌──────────────────────┐  │
│  │ TaskList (root)  │  │ TaskStatus /       │  │ DomainError          │  │
│  │ Task, User       │  │ TaskPriority /     │  │  hierarchy           │  │
│  │ + invariants     │  │ CompletionStats    │  │                      │  │
│  └──────────────────┘  └────────────────────┘  └──────────────────────┘  │
├──────────────────────────────────────────────────────────────────────────┤
│              INFRASTRUCTURE (driven adapters — implement the ports)       │
│  ┌────────────┐ ┌────────────┐ ┌───────────┐ ┌──────────┐ ┌───────────┐ │
│  │ ORM models │ │ mappers    │ │ SqlAlchemy│ │ JWT /    │ │ Logging   │ │
│  │ + engine   │ │ (ORM↔dom.) │ │ repos+UoW │ │ hasher   │ │ notifier  │ │
│  └─────┬──────┘ └────────────┘ └───────────┘ └──────────┘ └───────────┘ │
│        │                                     ┌────────────────────────┐ │
│        │                                     │ settings (pydantic-    │ │
│        │                                     │ settings)              │ │
└────────┼─────────────────────────────────────┴────────────────────────┴─┘
         ▼
   ┌───────────┐        ┌──────────────────────────────────┐
   │PostgreSQL │◄───────┤ Alembic (migrations/ at repo root)│
   └───────────┘        └──────────────────────────────────┘

Dependency direction: everything points DOWN. Domain points at nothing.
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| **Domain entities** | Business identity + invariants (`Task.change_status` validates the transition; `TaskList.rename` validates the title) | `@dataclass` (mutable for entities, `frozen=True` for value objects), `Enum` for status/priority |
| **Domain exceptions** | HTTP-agnostic vocabulary of business failures | `DomainError` base with `code` + `message` + `details` |
| **Use cases** | Orchestrate one business transaction: load → invoke domain → persist → commit → notify | One class per use case, `async def execute(command) -> Result` |
| **Commands / Results (DTOs)** | Typed contract between presentation and application; decouple HTTP shape from domain shape | Pydantic v2 models, `frozen=True`, `extra="forbid"` |
| **Ports** | Declare what the application needs from the outside world | `typing.Protocol`, async methods, domain types in signatures |
| **Unit of Work** | Transaction boundary + repository access point | Async context manager wrapping one `AsyncSession` |
| **Repositories** | Aggregate persistence; translate ORM rows ↔ domain entities | SQLAlchemy 2.0 `select()` + explicit mapper functions |
| **ORM models** | Table shape, indexes, FKs, cascade | `DeclarativeBase` + `Mapped[...]` / `mapped_column` |
| **Mappers** | `to_domain(row) -> Entity`, `apply_to_row(entity, row)` | Plain module-level functions, pure, 100 % unit-testable |
| **Routers** | HTTP verbs, status codes, OpenAPI docs, schema ↔ DTO translation | `APIRouter`, `Annotated[UseCase, Depends(...)]` |
| **Error handlers** | Single translation point: `DomainError` → RFC 9457 `application/problem+json` | One handler on the base class + a `{ExceptionType: status}` map |
| **Composition root** | Build the object graph; the *only* place that knows concrete classes | `main.py` app factory + `presentation/api/dependencies.py` |

---

## Recommended Project Structure

```
task-manager-api/
├── src/
│   └── taskmanager/
│       ├── __init__.py
│       ├── main.py                       # app factory + lifespan + wiring  (top layer)
│       │
│       ├── domain/                       # LAYER 0 — stdlib only
│       │   ├── entities/
│       │   │   ├── task_list.py          # TaskList (aggregate root)
│       │   │   ├── task.py               # Task
│       │   │   └── user.py               # User
│       │   ├── value_objects/
│       │   │   ├── task_status.py        # TaskStatus + ALLOWED_TRANSITIONS
│       │   │   ├── task_priority.py      # TaskPriority
│       │   │   ├── email_address.py      # EmailAddress (frozen)
│       │   │   └── completion.py         # CompletionStats + percentage()
│       │   └── exceptions.py             # DomainError hierarchy
│       │
│       ├── application/                  # LAYER 1 — domain + pydantic only
│       │   ├── ports/
│       │   │   ├── repositories.py       # *Repository Protocols
│       │   │   ├── unit_of_work.py       # UnitOfWork Protocol
│       │   │   ├── security.py           # PasswordHasher, TokenService
│       │   │   ├── notifications.py      # EmailNotifier
│       │   │   └── clock.py              # Clock  (kills datetime.now() in tests)
│       │   ├── dto/
│       │   │   ├── commands.py           # CreateTaskListCommand, ...
│       │   │   └── results.py            # TaskListResult, TaskListWithStatsResult
│       │   └── use_cases/
│       │       ├── task_lists/           # create / get / update / delete / list_tasks
│       │       ├── tasks/                # create / get / update / delete / change_status / assign
│       │       └── auth/                 # register_user / authenticate_user
│       │
│       ├── infrastructure/               # LAYER 2 — implements the ports
│       │   ├── config/
│       │   │   └── settings.py           # pydantic-settings BaseSettings
│       │   ├── persistence/
│       │   │   ├── engine.py             # create_async_engine + async_sessionmaker
│       │   │   ├── models.py             # SQLAlchemy ORM models
│       │   │   ├── mappers.py            # ORM ↔ domain translation
│       │   │   ├── unit_of_work.py       # SqlAlchemyUnitOfWork
│       │   │   └── repositories/
│       │   │       ├── task_list_repository.py
│       │   │       ├── task_repository.py
│       │   │       └── user_repository.py
│       │   ├── security/
│       │   │   ├── bcrypt_password_hasher.py
│       │   │   └── jwt_token_service.py
│       │   └── notifications/
│       │       └── logging_email_notifier.py   # the "fake" email
│       │
│       └── presentation/                 # LAYER 3 — driving adapter
│           └── api/
│               ├── dependencies.py       # the only module wiring infra → use cases
│               ├── security.py           # HTTPBearer → CurrentUser
│               ├── routers/
│               │   ├── health.py
│               │   ├── auth.py
│               │   ├── task_lists.py
│               │   └── tasks.py
│               ├── schemas/              # Pydantic request/response models
│               │   ├── task_list.py
│               │   ├── task.py
│               │   ├── auth.py
│               │   └── problem.py        # ProblemDetail (documented in OpenAPI)
│               └── errors/
│                   ├── mapping.py        # {DomainError subclass: HTTP status}
│                   └── handlers.py       # the single exception handler
│
├── migrations/                           # Alembic — operational, NOT inside the package
│   ├── env.py                            # async template
│   └── versions/
├── tests/
│   ├── conftest.py
│   ├── architecture/test_layer_boundaries.py
│   ├── unit/            {domain,application}      # fakes, no DB, milliseconds
│   ├── integration/     {repositories,migrations} # real Postgres, rollback per test
│   └── api/                                        # httpx ASGI, full stack
├── docker/entrypoint.sh
├── alembic.ini
├── pyproject.toml        # black, isort, mypy, importlinter contracts, deps
├── pytest.ini            # literal file required by the brief
├── .flake8               # literal file required by the brief
├── Dockerfile            # multistage
├── docker-compose.yml
├── Makefile
├── README.md
└── DECISION_LOG.md
```

### Structure Rationale

- **`src/` layout:** the installed package is what gets tested, so a missing `__init__.py` or a
  bad packaging config fails in CI instead of at `docker build`. It also gives import-linter a
  single unambiguous `root_package`.
- **Layers as top-level packages, features as sub-packages:** the brief is graded on *layers*, so
  the layers must be the first thing an evaluator sees in the tree. Feature grouping (`task_lists/`,
  `tasks/`, `auth/`) lives one level down, which keeps `use_cases/` navigable.
- **`application/ports/` (not `domain/ports/`):** one simple rule — "domain imports nothing" — is
  far easier to state, enforce and defend than "domain may declare interfaces it doesn't use". No
  domain entity in this project needs a port; putting them all in application keeps the layers
  contract perfectly linear.
- **`presentation/api/dependencies.py` is the wiring seam:** routers never import infrastructure;
  a dedicated `forbidden` contract proves it.
- **`migrations/` at repo root:** migrations are an operational artifact, versioned with the repo,
  not importable application code. Keeping them out of `src/` also keeps them out of coverage.
- **`tests/architecture/`:** the brief's "next level" requirement says the boundary must be an
  automated test. It gets its own directory so the evaluator finds it in five seconds.

---

## Architectural Patterns

### Pattern 1: Domain entities as dataclasses, Pydantic at the boundary

**What:** Domain = `@dataclass` + `Enum` + hand-written invariants raising `DomainError`.
Pydantic v2 = request/response schemas, application DTOs, and settings.
**When to use:** any time the domain has real behaviour (state machines, ownership rules) rather
than being a pass-through CRUD shape.
**Trade-offs:**

| | Pydantic entities | Dataclass entities *(recommended)* |
|---|---|---|
| Framework coupling | Domain imports `pydantic` | Domain imports nothing |
| Validation errors | `pydantic.ValidationError` leaks a foreign type into the domain and cannot carry `code`/`details` | Raise your own `DomainError` subclass — exactly what the brief asks for |
| Boilerplate | Lower | Slightly higher (explicit `__post_init__`) |
| Mutation of entities | `model_copy` / `validate_assignment` friction | Natural (`task.status = ...` inside a method) |
| "Strong typing with Pydantic" box ticked? | Yes | Yes — via schemas, DTOs and settings, which is where Pydantic actually earns its keep |

**Escape hatch if literal brief compliance worries you:** `pydantic.dataclasses.dataclass` gives
Pydantic validation with dataclass ergonomics. It still puts `pydantic` in the domain's import
graph, so it weakens the flagship "domain is framework-free" contract. Pick one and *say so* in
`DECISION_LOG.md`; the reasoning is worth more marks than the choice.

```python
# domain/value_objects/task_status.py
from enum import StrEnum

class TaskStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

ALLOWED_TRANSITIONS: dict[TaskStatus, frozenset[TaskStatus]] = {
    TaskStatus.PENDING: frozenset({TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED}),
    TaskStatus.IN_PROGRESS: frozenset({TaskStatus.COMPLETED, TaskStatus.CANCELLED}),
    TaskStatus.COMPLETED: frozenset(),
    TaskStatus.CANCELLED: frozenset({TaskStatus.PENDING}),
}
```

```python
# domain/entities/task.py
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from taskmanager.domain.exceptions import InvalidStatusTransitionError, ValidationError
from taskmanager.domain.value_objects.task_priority import TaskPriority
from taskmanager.domain.value_objects.task_status import ALLOWED_TRANSITIONS, TaskStatus


@dataclass
class Task:
    id: UUID
    task_list_id: UUID
    title: str
    description: str | None
    status: TaskStatus
    priority: TaskPriority
    assignee_id: UUID | None
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValidationError("Task title must not be empty", field="title")

    def change_status(self, new_status: TaskStatus, *, now: datetime) -> None:
        if new_status == self.status:
            return
        if new_status not in ALLOWED_TRANSITIONS[self.status]:
            raise InvalidStatusTransitionError(current=self.status, requested=new_status)
        self.status = new_status
        self.updated_at = now

    def assign_to(self, user_id: UUID, *, now: datetime) -> None:
        if self.status in (TaskStatus.COMPLETED, TaskStatus.CANCELLED):
            raise TaskNotAssignableError(task_id=self.id, status=self.status)
        self.assignee_id = user_id
        self.updated_at = now
```

### Pattern 2: Ports as `typing.Protocol`

**What:** structural interfaces in `application/ports/`. Adapters in `infrastructure/` do **not**
inherit from them; conformance is checked by mypy.
**When to use:** default choice in modern Python; it is the pattern that makes fake repositories
in unit tests free.
**Trade-offs:** no runtime enforcement — a signature drift is only caught by mypy, so mypy in CI
becomes load-bearing rather than decorative (good: the brief already asks for it). Add one
compile-time assertion per adapter so drift also fails the *test* suite, not just the type check.
ABCs are the alternative: runtime enforcement and an explicit `implements` signal for readers, at
the cost of forcing infrastructure to import the port and of `super().__init__` noise. Either is
defensible; Protocol is more idiomatic for hexagonal Python and pairs better with the
"infrastructure knows nothing about who calls it" story.

```python
# application/ports/repositories.py
from typing import Protocol
from uuid import UUID

from taskmanager.domain.entities.task import Task
from taskmanager.domain.value_objects.completion import CompletionStats
from taskmanager.domain.value_objects.task_priority import TaskPriority
from taskmanager.domain.value_objects.task_status import TaskStatus


class TaskRepository(Protocol):
    async def get(self, task_id: UUID) -> Task | None: ...
    async def add(self, task: Task) -> None: ...
    async def update(self, task: Task) -> None: ...
    async def delete(self, task_id: UUID) -> None: ...
    async def list_for_task_list(
        self,
        task_list_id: UUID,
        *,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
    ) -> list[Task]: ...
    async def completion_stats(self, task_list_id: UUID) -> CompletionStats: ...
```

```python
# tests/unit/conftest.py — structural conformance assertion (fails mypy AND documents intent)
from taskmanager.application.ports.repositories import TaskRepository
from taskmanager.infrastructure.persistence.repositories.task_repository import (
    SqlAlchemyTaskRepository,
)

def test_adapter_satisfies_port() -> None:
    _: type[TaskRepository] = SqlAlchemyTaskRepository  # type-checked, no runtime cost
```

### Pattern 3: One class per use case + explicit command/result DTOs

**What:** every entry in the brief's use-case list gets its own class with a single
`async def execute(...)`. No `TaskService` god-object.
**When to use:** whenever the grading rubric contains the words "Application/UseCases" — the
one-to-one mapping between the PDF's bullet list and the files in `use_cases/` is the single
highest-signal structural choice in this project.
**Trade-offs:** more files (≈14 use cases here) and some duplicated "load list, check ownership"
preamble. Absorb the duplication with a small shared helper in `application/use_cases/_guards.py`
rather than with inheritance.

```python
# application/dto/commands.py
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from taskmanager.domain.value_objects.task_status import TaskStatus


class ChangeTaskStatusCommand(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    actor_id: UUID                 # who is acting — set by presentation from the JWT
    task_id: UUID
    new_status: TaskStatus
```

```python
# application/use_cases/tasks/change_task_status.py
class ChangeTaskStatus:
    def __init__(self, uow: UnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    async def execute(self, command: ChangeTaskStatusCommand) -> TaskResult:
        async with self._uow:
            task = await self._uow.tasks.get(command.task_id)
            if task is None:
                raise TaskNotFoundError(task_id=command.task_id)

            task_list = await self._uow.task_lists.get(task.task_list_id)
            if task_list is None or not task_list.is_accessible_by(command.actor_id):
                raise PermissionDeniedError(resource="task_list", actor_id=command.actor_id)

            task.change_status(command.new_status, now=self._clock.now())  # domain invariant
            await self._uow.tasks.update(task)
            await self._uow.commit()                                       # explicit boundary

        return TaskResult.from_entity(task)
```

Note the shape: **load → authorize → invoke domain → persist → commit → map to result.** Every
use case in the project follows it, which makes the code base feel designed rather than accreted.

### Pattern 4: Unit of Work over session-per-request

**What:** one `AsyncSession` per HTTP request, owned by a `SqlAlchemyUnitOfWork` that exposes the
repositories and the `commit()`/`rollback()` verbs. The use case owns the transaction boundary.
**When to use:** any time one request can touch more than one aggregate (here: assigning a task
touches `Task` + reads `User`; registering a user writes `User` and fires a notification).
**Trade-offs:** one more indirection than injecting repositories directly. It buys atomicity that
is *visible in the use case*, and a `FakeUnitOfWork` that makes application unit tests DB-free.

```python
# application/ports/unit_of_work.py
from types import TracebackType
from typing import Protocol, Self


class UnitOfWork(Protocol):
    task_lists: TaskListRepository
    tasks: TaskRepository
    users: UserRepository

    async def __aenter__(self) -> Self: ...
    async def __aexit__(
        self, exc_type: type[BaseException] | None,
        exc: BaseException | None, tb: TracebackType | None,
    ) -> None: ...
    async def commit(self) -> None: ...
    async def rollback(self) -> None: ...
```

```python
# infrastructure/persistence/unit_of_work.py
class SqlAlchemyUnitOfWork:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def __aenter__(self) -> "SqlAlchemyUnitOfWork":
        self._session = self._session_factory()
        self.task_lists = SqlAlchemyTaskListRepository(self._session)
        self.tasks = SqlAlchemyTaskRepository(self._session)
        self.users = SqlAlchemyUserRepository(self._session)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        try:
            if exc_type is not None:
                await self._session.rollback()   # never swallow: no `return True`
        finally:
            await self._session.close()

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()
```

**Why the UoW opens its own session instead of receiving one from a FastAPI dependency:**
FastAPI's official docs state that *"normally the exit code of dependencies with `yield` is
executed **after the response** is sent to the client"* (a `scope="function"` option exists in
recent versions to change this). If the commit lived in a dependency's exit code, a
`ForeignKeyViolation` at COMMIT time would happen **after** the client already received `201
Created`. Owning the session inside the UoW sidesteps the whole class of problem. If you prefer
the dependency-owned session (it makes the test override trivially easy), then inject the session
with `Depends(get_session, scope="function")` and still commit inside the use case, never in the
dependency.

### Pattern 5: Explicit ORM ↔ domain mappers

**What:** separate SQLAlchemy `DeclarativeBase` models in `infrastructure/persistence/models.py`,
plus pure functions translating to and from domain entities.
**When to use:** whenever the domain must stay import-free of the ORM. The alternative —
SQLAlchemy **imperative mapping** (`registry.map_imperatively`) onto the domain dataclasses —
gives you a dirty-tracked domain with no mapper code, but it silently instruments your "pure"
objects, fights mypy, and makes `__post_init__` invariants run at load time. Not worth it for a
4–6 hour deliverable; mention it in `DECISION_LOG.md` as the considered alternative.
**Trade-offs:** you write ~15 lines per aggregate, and updates need a load-then-copy step rather
than free dirty tracking.

```python
# infrastructure/persistence/mappers.py
def task_to_domain(row: TaskModel) -> Task:
    return Task(
        id=row.id, task_list_id=row.task_list_id, title=row.title,
        description=row.description, status=TaskStatus(row.status),
        priority=TaskPriority(row.priority), assignee_id=row.assignee_id,
        created_at=row.created_at, updated_at=row.updated_at,
    )

def apply_task_to_row(task: Task, row: TaskModel) -> None:
    row.title = task.title
    row.description = task.description
    row.status = task.status.value
    row.priority = task.priority.value
    row.assignee_id = task.assignee_id
    row.updated_at = task.updated_at
```

```python
# infrastructure/persistence/repositories/task_repository.py  (update path)
async def update(self, task: Task) -> None:
    row = await self._session.get(TaskModel, task.id)
    if row is None:
        raise TaskNotFoundError(task_id=task.id)
    apply_task_to_row(task, row)          # flushed on commit by the UoW
```

### Pattern 6: Domain exceptions → one handler → RFC 9457 Problem Details

**What:** a closed hierarchy under `DomainError`, a `{exception type: HTTP status}` table in
presentation, and **one** `@app.exception_handler(DomainError)`.
**Why one handler is enough:** Starlette's `ExceptionMiddleware` resolves handlers by walking
`type(exc).__mro__`, so a handler registered on the base class catches every subclass. Add a test
asserting it — it is a load-bearing framework behaviour, not an obvious one.

**Standards note:** the brief says RFC 7807. **RFC 9457 (July 2023) obsoletes RFC 7807** with no
breaking changes — same `application/problem+json` media type, same core members, plus explicit
guidance to carry multiple errors in a custom extension member rather than at the root. Implement
9457 and cite both in `DECISION_LOG.md`; noticing the supersession is exactly the kind of detail
that reads as senior.

```
DomainError                      code            → HTTP
├── ValidationError              validation_error    422
├── BusinessRuleViolationError   business_rule       422
│   └── InvalidStatusTransitionError  invalid_status_transition  409
├── NotFoundError                not_found           404
│   ├── TaskListNotFoundError
│   ├── TaskNotFoundError
│   └── UserNotFoundError
├── ConflictError                conflict            409
│   └── EmailAlreadyRegisteredError
├── AuthenticationError          authentication      401
└── PermissionDeniedError        permission_denied   403
```

```python
# domain/exceptions.py  — no HTTP anywhere in this file
from typing import Any


class DomainError(Exception):
    code: str = "domain_error"
    title: str = "Domain error"

    def __init__(self, message: str, **details: Any) -> None:
        super().__init__(message)
        self.message = message
        self.details = details
```

```python
# presentation/api/errors/handlers.py
STATUS_BY_EXCEPTION: dict[type[DomainError], int] = {
    ValidationError: 422,
    BusinessRuleViolationError: 422,
    InvalidStatusTransitionError: 409,
    NotFoundError: 404,
    ConflictError: 409,
    AuthenticationError: 401,
    PermissionDeniedError: 403,
}

def _status_for(exc: DomainError) -> int:
    for klass in type(exc).__mro__:                 # same MRO walk Starlette does
        if klass in STATUS_BY_EXCEPTION:
            return STATUS_BY_EXCEPTION[klass]
    return 500


async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    status = _status_for(exc)
    body = {
        "type": f"https://taskmanager.example/problems/{exc.code}",
        "title": exc.title,
        "status": status,
        "detail": exc.message,
        "instance": str(request.url.path),
        "code": exc.code,          # RFC 9457 extension member
        **({"errors": exc.details} if exc.details else {}),
    }
    return JSONResponse(body, status_code=status, media_type="application/problem+json")
```

Register three handlers in the composition root so **every** error path produces the same shape:
`DomainError`, `RequestValidationError` (422, failures under the `errors` extension),
`StarletteHTTPException` (covers 404 on unknown routes and the 401 from the auth dependency).
Declare `ProblemDetail` in `responses={...}` on the routers so the contract appears in OpenAPI.

### Pattern 7: FastAPI `Depends` as the composition root

**What:** a chain of small provider functions in `presentation/api/dependencies.py`, exported as
`Annotated` aliases so the routers read cleanly and contain no wiring.
**Trade-offs:** no third-party DI container needed (`dependency-injector` and friends are pure
overhead here); the cost is that dependency wiring is expressed as function signatures rather than
as a declarative graph. `app.dependency_overrides` makes every node swappable in tests, for free.

```python
# presentation/api/dependencies.py
def get_settings() -> Settings:                  # cached in main via lru_cache
    ...

def get_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    return request.app.state.session_factory     # created once in lifespan

def get_uow(
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> UnitOfWork:
    return SqlAlchemyUnitOfWork(factory)

def get_change_task_status(
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> ChangeTaskStatus:
    return ChangeTaskStatus(uow, clock)

ChangeTaskStatusUC = Annotated[ChangeTaskStatus, Depends(get_change_task_status)]
```

```python
# presentation/api/routers/tasks.py
@router.patch("/{task_id}/status", response_model=TaskResponse,
              responses={404: {"model": ProblemDetail}, 409: {"model": ProblemDetail}})
async def change_task_status(
    task_id: UUID,
    payload: ChangeTaskStatusRequest,
    use_case: ChangeTaskStatusUC,
    current_user: CurrentUser,
) -> TaskResponse:
    result = await use_case.execute(
        ChangeTaskStatusCommand(
            actor_id=current_user.id, task_id=task_id, new_status=payload.status,
        )
    )
    return TaskResponse.from_result(result)
```

The router has **no** `try/except`, **no** SQLAlchemy import and **no** business logic. That is the
whole point, and it is what the import-linter `forbidden` contract locks in.

### Pattern 8: Authentication in presentation, authorization in the use case

**What:** the `HTTPBearer` dependency decodes the JWT via the `TokenService` **port** and yields a
`CurrentUser`; it raises `AuthenticationError` (→ 401) and nothing else. Ownership rules
("only the list owner may delete it") live in `TaskList.is_accessible_by()` / the use case and
raise `PermissionDeniedError` (→ 403).
**Why it matters here:** it is what turns the optional JWT bonus into the brief's mandatory
"business validations" — and those rules are then unit-testable with no HTTP at all.
**Port placement:**

| Concern | Port (application/ports) | Adapter (infrastructure) | Used by |
|---|---|---|---|
| Password hashing | `PasswordHasher.hash / verify` | `BcryptPasswordHasher` (bcrypt or argon2) | `RegisterUser`, `AuthenticateUser` |
| Token issuing | `TokenService.issue(subject, expires_in)` | `JwtTokenService` (PyJWT, HS256) | `AuthenticateUser` |
| Token decoding | `TokenService.decode(token) -> TokenPayload` | same adapter | presentation auth dependency |
| Fake email | `EmailNotifier.send_task_assigned(...)` | `LoggingEmailNotifier` + `InMemoryEmailNotifier` (tests) | `AssignTask`, `RegisterUser` |
| Time | `Clock.now() -> datetime` | `SystemClock`, `FrozenClock` (tests) | every use case that timestamps |

The `Clock` port looks like ceremony until the first `updated_at` assertion; then it pays for
itself. Keep it.

### Pattern 9: Settings via pydantic-settings, resolved once at startup

**What:** a single `Settings(BaseSettings)` in `infrastructure/config/settings.py`, built once and
stashed on `app.state` during `lifespan`; nothing else calls `os.environ`.
**Trade-offs:** module-level `settings = Settings()` is tempting and wrong — it makes import order
significant and breaks tests that need a different DB URL. Use an `lru_cache`d factory + a
`dependency_overrides` swap in tests.

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_nested_delimiter="__", extra="ignore")

    database_url: PostgresDsn
    jwt_secret_key: SecretStr
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 60
    environment: Literal["local", "test", "production"] = "local"
```

Nested groups (`DatabaseConfig`, `JwtConfig`) via `env_nested_delimiter="__"` are supported and
read nicely, but flat is fine at this size. **Never** default `jwt_secret_key` — an absent secret
must crash at startup, not silently sign tokens with `"changeme"`.

### Pattern 10: Alembic at the root, migrations at container start

**What:** `alembic.ini` + `migrations/` at repo root, `alembic init -t async`, and `env.py`
importing `Base.metadata` from `infrastructure.persistence.models` with the URL taken from
`Settings` (not hardcoded in the ini). An entrypoint script runs `alembic upgrade head` before
`exec uvicorn`.

```bash
# docker/entrypoint.sh
set -euo pipefail
alembic upgrade head
exec uvicorn taskmanager.main:app --host 0.0.0.0 --port 8000
```

```yaml
# docker-compose.yml (excerpt)
services:
  db:
    image: postgres:16-alpine
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d taskmanager"]
      interval: 3s
      timeout: 3s
      retries: 20
  api:
    build: .
    depends_on:
      db: { condition: service_healthy }   # plain depends_on is NOT enough
    entrypoint: ["/app/docker/entrypoint.sh"]
```

**Trade-offs, stated honestly in `DECISION_LOG.md`:** coupling migrations to container start is a
known production anti-pattern (with N replicas, N containers race to migrate; a failed migration
becomes a crash-loop; rollback gets hard). For a reviewable challenge where `docker compose up`
must Just Work, it is the right call — and *saying* you know why it is wrong in production is
worth more than silently doing the "correct" thing.

**Never** call `Base.metadata.create_all()` in the app or in tests. Integration tests must run
`alembic upgrade head`, which means the migrations themselves are covered by the test suite.

---

## Enforcing the Boundaries

### import-linter contracts

Configured in `pyproject.toml` under `[tool.importlinter]`. Verified syntax (Context7,
import-linter docs): layer lists are ordered high → low; `|` separates *independent* siblings,
`:` separates siblings allowed to import each other; `include_external_packages = true` enables
`forbidden` contracts that name third-party packages.

```toml
[tool.importlinter]
root_package = "taskmanager"
include_external_packages = true

[[tool.importlinter.contracts]]
name = "Layered architecture (high to low)"
type = "layers"
layers = [
    "taskmanager.main",
    "taskmanager.presentation",
    "taskmanager.infrastructure",
    "taskmanager.application",
    "taskmanager.domain",
]

[[tool.importlinter.contracts]]
name = "Domain is framework-free"
type = "forbidden"
source_modules = ["taskmanager.domain"]
forbidden_modules = [
    "fastapi", "starlette", "sqlalchemy", "alembic",
    "pydantic", "pydantic_settings", "jwt", "passlib", "bcrypt", "httpx",
]

[[tool.importlinter.contracts]]
name = "Application knows no framework except Pydantic"
type = "forbidden"
source_modules = ["taskmanager.application"]
forbidden_modules = ["fastapi", "starlette", "sqlalchemy", "alembic", "jwt", "passlib", "bcrypt"]

[[tool.importlinter.contracts]]
name = "Routers and schemas reach infrastructure only via the composition root"
type = "forbidden"
source_modules = [
    "taskmanager.presentation.api.routers",
    "taskmanager.presentation.api.schemas",
]
forbidden_modules = ["taskmanager.infrastructure"]
```

**Why presentation sits above infrastructure** rather than as an independent sibling: something
has to know both concrete adapters and HTTP routes, and a strict hexagon would force that wiring
into a fifth top package with stub-provider indirection (`dependency_overrides` for production
wiring). Ranking presentation highest keeps the graph linear and readable; contract #4 restores
the missing guarantee by restricting infrastructure imports to `dependencies.py`. If you prefer
the purist version, use `"taskmanager.presentation | taskmanager.infrastructure"` as a single
sibling layer under `taskmanager.main` and move `dependencies.py` into `main`.

### The automated test

```python
# tests/architecture/test_layer_boundaries.py
import subprocess, sys

def test_import_contracts_hold() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "importlinter.cli", "lint-imports"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
```

Run `lint-imports` **also** as its own CI step so the failure message is visible in the job log
rather than buried in pytest output, and add it to the `Makefile` (`make arch`). Wire it into
pre-commit so a boundary violation cannot even be committed.

---

## Data Flow

### Request flow (write path — `PATCH /task-lists/{id}/tasks/{task_id}/status`)

```
HTTP request
   │
   ▼
[Router]  ── validates body ──►  ChangeTaskStatusRequest (Pydantic)
   │       ── CurrentUser dep ─►  TokenService.decode(jwt)   ── invalid ──► 401 problem+json
   │
   ├── builds ──►  ChangeTaskStatusCommand(actor_id, task_id, new_status)
   ▼
[Use case]  async with uow:
   │           ├─► TaskRepository.get()        ──► SELECT ──► TaskModel ──► mapper ──► Task
   │           ├─► ownership check             ──► PermissionDeniedError ─┐
   │           ├─► task.change_status()        ──► InvalidStatusTransition┤ (domain)
   │           ├─► TaskRepository.update()     ──► mapper ──► TaskModel   │
   │           └─► uow.commit()                ──► COMMIT                 │
   ▼                                                                      │
TaskResult (DTO)                                                          │
   │                                                                      ▼
   ▼                                                        [Single exception handler]
[Router] ──► TaskResponse ──► 200 application/json          ──► RFC 9457 problem+json
```

On any exception the UoW's `__aexit__` rolls back and closes; the exception keeps propagating to
the handler, which is invoked by Starlette **before** the response is sent. Dependency exit code
(if any) runs after. Never swallow in `__aexit__`.

### Read flow with the completion percentage (`GET /task-lists/{id}/tasks?status=&priority=`)

```
Router(query params) ──► ListTasksCommand(list_id, status?, priority?, actor_id)
        │
        ▼
ListTasksOfList.execute()
        ├─► task_lists.get(id)              → 404 / 403 guards
        ├─► tasks.list_for_task_list(...)   → filtered Task[]        (SQL WHERE)
        ├─► tasks.completion_stats(id)      → CompletionStats(total, completed)
        │                                      (SQL COUNT — the WHOLE list, unfiltered)
        └─► completion_percentage(stats)    → pure domain function, 0.0 when total == 0
        ▼
TaskListWithStatsResult { tasks: [...], completion_percentage: 42.9, total: 7, completed: 3 }
```

Two deliberate decisions to record in `DECISION_LOG.md`:
1. **The percentage is computed over the whole list, not the filtered subset** — a "completion
   percentage" that changes when you filter by priority is meaningless. Expose `total_tasks` and
   `completed_tasks` alongside it so the client can compute the filtered view if it wants.
2. **The count is a SQL aggregate, not `len([t for t in tasks if ...])`** — the percentage must be
   correct even when the query is filtered or paginated, and it avoids loading the whole list.
   The *arithmetic* still lives in a pure domain function so it is unit-tested without a DB.

```python
# domain/value_objects/completion.py
from dataclasses import dataclass

@dataclass(frozen=True)
class CompletionStats:
    total: int
    completed: int

    def percentage(self) -> float:
        if self.total == 0:
            return 0.0
        return round(self.completed / self.total * 100, 2)
```

### Notification flow (fake email)

```
AssignTask.execute()
   ├─► ... domain mutation ...
   ├─► uow.commit()                       ◄── transaction ends HERE
   └─► notifier.send_task_assigned(...)   ◄── side effect AFTER commit
```

Dispatching the notification *before* the commit means a rollback leaves the user with an email
about a change that never happened. With a fake notifier nobody will notice — but the evaluator
reads the order of those two lines. Put the notifier call after `commit()` and keep it out of the
`async with` block.

### Test data flow

```
tests/unit/          Use case ──► FakeUnitOfWork(dict-backed fakes) ──► in-memory
                     Domain   ──► no dependencies at all
tests/integration/   Repository ──► AsyncSession bound to an outer connection
                                    (join_transaction_mode="create_savepoint")
                                 ──► real Postgres ──► rolled back at teardown
tests/api/           httpx ASGITransport ──► app with dependency_overrides
                                          ──► same transactional session
```

---

## Test Architecture

| Layer | Location | Dependencies | Speed | What it proves |
|---|---|---|---|---|
| Domain unit | `tests/unit/domain/` | none | ~ms | Invariants, transitions, percentage maths |
| Use case unit | `tests/unit/application/` | fakes only | ~ms | Orchestration, guards, error raising, notifier called once, after commit |
| Mapper unit | `tests/unit/infrastructure/` | none | ~ms | ORM ↔ domain round-trip |
| Repository integration | `tests/integration/` | real Postgres | ~100ms | SQL, constraints, filters, COUNT aggregates, migrations apply |
| API | `tests/api/` | real Postgres + full app | ~100ms | Status codes, problem+json shape, auth, OpenAPI contract |
| Architecture | `tests/architecture/` | import-linter | ~1s | Boundaries hold |

**Fake repositories** are the payoff of Protocol ports — roughly 20 lines each, dict-backed, no
mocking library, and they make `--cov-fail-under=75` easy to clear without a DB in the fast loop.

```python
class FakeTaskRepository:
    def __init__(self) -> None:
        self._items: dict[UUID, Task] = {}

    async def get(self, task_id: UUID) -> Task | None:
        return self._items.get(task_id)

    async def add(self, task: Task) -> None:
        self._items[task.id] = task
    ...

class FakeUnitOfWork:
    def __init__(self) -> None:
        self.tasks = FakeTaskRepository()
        self.task_lists = FakeTaskListRepository()
        self.users = FakeUserRepository()
        self.committed = False

    async def __aenter__(self): return self
    async def __aexit__(self, *_): return None
    async def commit(self) -> None: self.committed = True
    async def rollback(self) -> None: ...
```

Assert `uow.committed is True` in the happy path and `is False` in every error path — a cheap,
high-signal test that the transaction boundary is actually respected.

**Transaction rollback per integration test** (SQLAlchemy's documented "join a Session into an
external transaction" recipe, asyncio variant): open a connection, `begin()` an outer transaction,
bind the session with `join_transaction_mode="create_savepoint"`, and roll the outer transaction
back at teardown. `create_savepoint` means the code under test can call `commit()` for real and
still be undone.

```python
@pytest_asyncio.fixture
async def session(engine) -> AsyncIterator[AsyncSession]:
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, join_transaction_mode="create_savepoint")
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()
```

Then override the session factory in API tests so requests share that transaction:

```python
app.dependency_overrides[get_uow] = lambda: SqlAlchemyUnitOfWork(lambda: session)
```

Schema setup: run `alembic upgrade head` once per test session against a dedicated test database
(a second `docker-compose` service, or `testcontainers` if you want the suite to be
self-contained). Configure `pytest.ini` with `asyncio_mode = auto`, a `markers = integration`
entry so `-m "not integration"` gives a sub-second inner loop, and `addopts` carrying
`--cov=src/taskmanager --cov-fail-under=75` so the brief's threshold is enforced by the file the
brief names.

---

## Suggested Build Order

Build the **layers bottom-up inside one thin vertical slice first**, then widen. The slice proves
the wiring, the error contract and the test harness before there are fourteen use cases to
retrofit.

| # | Step | Depends on | Delivers |
|---|---|---|---|
| 0 | **Skeleton + gates.** src layout, `pyproject.toml`, `pytest.ini`, `.flake8`, black/isort, mypy, pre-commit, Makefile, CI, **import-linter contracts against empty packages**, Dockerfile + compose, `GET /health` | — | Green CI on an empty app. Writing the contract *before* the code is the whole trick: boundaries can never be violated because they were never unenforced. |
| 1 | **Domain core.** `TaskList`, `Task`, `TaskStatus`/`TaskPriority`, transitions, `CompletionStats`, `DomainError` hierarchy | 0 | Pure unit tests, zero infrastructure. Biggest coverage win per minute. |
| 2 | **Ports + DTOs + first use cases** (task-list CRUD) against fakes | 1 | Application layer proven with no DB in sight. |
| 3 | **Persistence.** ORM models, Alembic baseline migration, mappers, `TaskListRepository`, `SqlAlchemyUnitOfWork`; integration fixtures | 2 | First real Postgres test; migration applies. |
| 4 | **Presentation slice.** Router + schemas for task lists, composition root, **error handlers + RFC 9457**, OpenAPI `responses` | 3 | End-to-end vertical slice. Everything after this is repetition of a proven shape. |
| 5 | **Tasks.** Task CRUD, `ChangeTaskStatus`, filtered listing + completion percentage | 4 | The remaining mandatory use cases (PDF 1.a complete). |
| 6 | **Auth.** `User`, `PasswordHasher`/`TokenService` ports + adapters, register/login use cases, `CurrentUser` dependency, ownership rules → 401/403 | 4 | Bonus 1 + the business validations the brief demands. |
| 7 | **Assignment + fake notifier.** `AssignTask`, `EmailNotifier` port, `LoggingEmailNotifier`, post-commit dispatch | 6 | Bonus 2 + 3. |
| 8 | **Hardening + docs.** entrypoint migrations, multistage Dockerfile polish, coverage to ≥ 75 %, `README.md`, `DECISION_LOG.md`, `AI_WORKFLOW.md` | all | Submittable. |

**Critical orderings:** 0 before everything (gates first, always). 1 before 2 (ports reference
domain types). 3 before 4 (the router needs something real to call). 4 before 5/6/7 (never repeat
an unproven pattern fourteen times). 6 before 7 (assignment needs users to assign to).

**Natural phase seams for the roadmap:** {0}, {1,2}, {3,4}, {5}, {6,7}, {8} — six phases, each
ending on a green test suite and a demonstrable capability.

**Where deeper research will be needed:** step 3 (async session + transactional test fixtures is
the single most error-prone area in this stack) and step 6 (JWT library choice and password
hashing backend have moving parts — `passlib` vs direct `bcrypt`/`argon2-cffi`, `python-jose` vs
`PyJWT`; defer to `STACK.md`). Steps 1, 2, 4, 5 are standard patterns.

---

## Anti-Patterns

### Anti-Pattern 1: Committing in a FastAPI dependency's exit code

**What people do:** `def get_session(): ... yield s; await s.commit()`.
**Why it's wrong:** FastAPI documents that the exit code of a `yield` dependency runs **after the
response is sent** (unless `scope="function"` is used). A constraint violation at COMMIT time then
happens when the client already holds a `201`. It also hides the transaction boundary from the
code that owns the business transaction.
**Do this instead:** commit explicitly inside the use case via the UoW. Dependencies only build
objects and clean up.

### Anti-Pattern 2: Returning ORM models from repositories

**What people do:** `async def get(...) -> TaskModel`.
**Why it's wrong:** SQLAlchemy leaks into the application and presentation layers; lazy-load
`MissingGreenlet` errors surface inside the router; the import-linter contract must be weakened to
allow it; and the domain's invariants are bypassed entirely.
**Do this instead:** repositories accept and return domain entities. The mapper is the only place
that knows both shapes.

### Anti-Pattern 3: Anemic domain + fat use cases

**What people do:** entities are field bags; `use_case.execute()` contains
`if task.status == "completed": raise ...`.
**Why it's wrong:** the brief is explicitly graded on "business validations", and this puts them
all in the orchestration layer where they get duplicated across use cases and drift.
**Do this instead:** rules that depend only on one aggregate's state go on the entity
(`task.change_status`, `task_list.is_accessible_by`). Use cases orchestrate; they do not decide.

### Anti-Pattern 4: Pydantic validators as the business rule layer

**What people do:** `@field_validator("status")` enforcing the state machine on the request schema.
**Why it's wrong:** the rule then exists only on the HTTP path, produces a
`pydantic.ValidationError` instead of your `DomainError`, is invisible to unit tests of the
domain, and vanishes the moment a second entry point (a CLI, a worker) appears.
**Do this instead:** Pydantic validates **shape** (types, lengths, formats, enum membership). The
domain validates **rules** (allowed transitions, ownership, assignability).

### Anti-Pattern 5: `try/except` in routers

**What people do:** `except TaskNotFound: raise HTTPException(404)` in every endpoint.
**Why it's wrong:** duplicates the mapping N times, guarantees inconsistent error bodies, and
defeats the "single exception-handling point" the brief's next-level layer asks for.
**Do this instead:** one handler on `DomainError` + a mapping table. Starlette's MRO walk covers
every subclass automatically — assert that with a test.

### Anti-Pattern 6: Layers that are only folders

**What people do:** `domain/`, `application/`, `infrastructure/` with `from sqlalchemy import ...`
inside `domain/entities/task.py`.
**Why it's wrong:** it is the single most common failure mode in "clean architecture" repos, and
an evaluator finds it with one `grep`.
**Do this instead:** import-linter contracts in `pyproject.toml`, run in pre-commit, in CI, and
from a pytest test. Ship the contract before the code.

### Anti-Pattern 7: A service layer that is a CRUD pass-through

**What people do:** `TaskService.create(dto)` that does nothing but call
`repository.create(dto)`.
**Why it's wrong:** pure ceremony — it adds a file per entity and zero behaviour, and it makes
reviewers suspect the whole architecture is cargo cult.
**Do this instead:** every use case must contain at least one decision (a guard, an invariant, a
mapping choice). If `GetTaskList` truly has none beyond the 404/403 guards, keep it — those *are*
decisions — but do not add a second indirection layer on top.

### Anti-Pattern 8: Computing the completion percentage in Python over loaded rows

**What people do:** `len([t for t in tasks if t.status == COMPLETED]) / len(tasks)`.
**Why it's wrong:** wrong answer as soon as the list is filtered or paginated, and it loads every
row to produce two integers.
**Do this instead:** a `COUNT(*) FILTER (WHERE status = 'completed')` aggregate in the repository
returning `CompletionStats`; the arithmetic stays in a pure domain function.

### Anti-Pattern 9: `Base.metadata.create_all()` for tests, Alembic for production

**What people do:** tests build the schema from the models; production runs migrations.
**Why it's wrong:** the migrations are then never tested, and the two schemas silently diverge.
**Do this instead:** tests run `alembic upgrade head` once per session. Broken migrations fail CI.

### Anti-Pattern 10: A module-level global `Settings()` or `engine`

**What people do:** `settings = Settings()` at import time in `config.py`.
**Why it's wrong:** import order becomes significant, the engine is created before the event loop
exists, and tests cannot point at a different database without monkeypatching.
**Do this instead:** build settings and the engine in `lifespan`, store on `app.state`, inject via
`Depends`. Dispose the engine on shutdown.

---

## Scaling Considerations

| Scale | Architecture adjustments |
|-------|--------------------------|
| 0–1k users (this project) | Single container + single Postgres. Nothing else. The layering is for *changeability*, not throughput. |
| 1k–100k | Add `LIMIT/OFFSET` (or keyset) pagination — the current design returns whole lists; index `(task_list_id, status)` and `(task_list_id, priority)`; tune the async pool (`pool_size`, `max_overflow`); move migrations out of the app entrypoint into a release job. |
| 100k+ | Read replicas behind a second engine (the repository port already hides this); replace the synchronous fake notifier with a real outbox + worker (the `EmailNotifier` port means the use cases do not change); consider caching completion stats. |

### Scaling priorities

1. **First bottleneck: unbounded list endpoints.** `GET /task-lists/{id}/tasks` returns every
   task. Pagination is explicitly out of scope for the challenge — list it in the README's
   "pending work" section, which turns a gap into evidence of judgement.
2. **Second bottleneck: connection pool exhaustion.** A UoW that opens a session per request is
   fine until slow queries pile up. `pool_pre_ping=True` plus a `statement_timeout` on the
   Postgres side is the cheap first mitigation.
3. **Third: the N+1 hiding in `completion_stats`.** Listing many lists with their percentages
   would fire one COUNT per list. Solve with a single grouped aggregate if that endpoint is ever
   added.

---

## Integration Points

### External services

| Service | Integration pattern | Notes |
|---------|---------------------|-------|
| PostgreSQL | SQLAlchemy 2.0 async engine + `async_sessionmaker`, one session per request via the UoW | `pool_pre_ping=True`; `expire_on_commit=False` avoids surprise lazy loads after commit; never share a session across tasks |
| Alembic | Root-level `migrations/`, async `env.py` reading the URL from `Settings` | Run via entrypoint in compose; also run in CI before integration tests |
| JWT | `TokenService` port, HS256, secret from settings | Presentation decodes, application issues. No refresh tokens (out of scope, document as pending) |
| "Email" | `EmailNotifier` port, logging adapter | Fires after commit; `InMemoryEmailNotifier` in tests makes it assertable |

### Internal boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Presentation ↔ Application | Pydantic command/result DTOs | Presentation never sees domain entities; the router maps `Result` → response schema |
| Application ↔ Domain | Direct calls on entities | Only layer allowed to import domain freely |
| Application ↔ Infrastructure | Protocol ports, dependency-inverted | Application never imports infrastructure; the composition root injects |
| Infrastructure ↔ Domain | Mapper functions only | ORM models are a separate shape; the mapper is the single translation point |
| Composition root ↔ everything | `Depends` providers in `dependencies.py` | The only module in presentation permitted to import infrastructure |

---

## Confidence Notes

| Claim | Confidence | Basis |
|---|---|---|
| Yield-dependency exit code runs after the response (`scope="function"` changes it) | HIGH | FastAPI official docs |
| Exceptions from a path operation propagate into yield dependencies; re-raise if caught | HIGH | FastAPI official docs |
| Starlette resolves exception handlers by walking `type(exc).__mro__` | MEDIUM-HIGH | Starlette source/docs via search; add a test to pin it |
| `join_transaction_mode="create_savepoint"` recipe for transactional tests | HIGH | SQLAlchemy 2.0 official docs (sync example; async variant widely used and discussed upstream) |
| import-linter `layers` / `forbidden` / `include_external_packages` syntax | HIGH | import-linter official docs via Context7 |
| RFC 9457 obsoletes RFC 7807, same media type, no breaking changes | HIGH | RFC Editor / IETF datatracker |
| pydantic-settings `env_nested_delimiter`, `SettingsConfigDict` | HIGH | pydantic-settings official docs via Context7 |
| Layer decomposition, port placement, dataclass-vs-Pydantic call, build order | MEDIUM | Design judgement informed by the ecosystem; defensible, not factual |
| Exact package versions | NOT ASSERTED | PyPI unreachable from this sandbox; defer to `STACK.md` |

## Sources

- FastAPI — Dependencies with yield: https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/
- FastAPI — Handling errors: https://fastapi.tiangolo.com/tutorial/handling-errors/
- FastAPI — `Depends` reference (`scope`, `use_cache`): https://fastapi.tiangolo.com/reference/dependencies/
- SQLAlchemy 2.0 — Session transaction / joining an external transaction: https://docs.sqlalchemy.org/en/20/orm/session_transaction.html
- SQLAlchemy 2.0 — asyncio extension (`async_sessionmaker`): https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
- Import Linter — contract types (layers, forbidden, independence): https://import-linter.readthedocs.io/en/stable/contract_types/index.html
- Starlette — exceptions / ExceptionMiddleware: https://www.starlette.io/exceptions/
- RFC 9457 — Problem Details for HTTP APIs (obsoletes RFC 7807): https://www.rfc-editor.org/info/rfc9457/
- pydantic-settings — settings management: https://docs.pydantic.dev/latest/concepts/pydantic_settings/
- Cosmic Python — Unit of Work pattern: https://www.cosmicpython.com/book/chapter_06_uow.html
- Patterns and practices for SQLAlchemy 2.0 with FastAPI: https://chaoticengineer.hashnode.dev/fastapi-sqlalchemy
- Decoupling database migrations from server startup: https://pythonspeed.com/articles/schema-migrations-server-startup/
- SQLAlchemy discussion — external transaction with asyncio: https://github.com/sqlalchemy/sqlalchemy/discussions/10857

---
*Architecture research for: layered/hexagonal FastAPI + PostgreSQL REST API*
*Researched: 2026-09-17*
