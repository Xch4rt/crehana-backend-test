# Phase 3: Persistence & Runnable Stack - Pattern Map

**Mapped:** 2026-09-18
**Files analyzed:** 52 (33 new source/test modules, 8 modified files, 11 new root artifacts)
**Analogs found:** 40 / 52

> **How to read this.** Every excerpt below is copied verbatim from a file that exists in this
> repository today, with its path and line numbers. The planner should reference the analog by
> path+lines in each plan's action section rather than re-deriving conventions. Where no analog
> exists (Alembic, Docker Compose, shell entrypoint), the "No Analog Found" section says so
> explicitly and points at `03-RESEARCH.md` instead.

---

## File Classification

### New source modules

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/taskmanager/infrastructure/db/__init__.py` | package init | — | `src/taskmanager/infrastructure/config/__init__.py` | exact (empty file, no docstring) |
| `src/taskmanager/infrastructure/db/base.py` | config/declarative base | — | `src/taskmanager/domain/value_objects/task_status.py` (module-level `Final` table + docstring) | partial |
| `src/taskmanager/infrastructure/db/constraints.py` | constants | — | `src/taskmanager/presentation/api/errors/problem.py` L17-21 (`Final` constant) + `task_status.py` L30 | role-match |
| `src/taskmanager/infrastructure/db/models.py` | model (ORM rows) | persistence schema | `src/taskmanager/domain/entities/task.py` (field set to mirror) | partial — no ORM model exists yet |
| `src/taskmanager/infrastructure/db/mappers.py` | transform/utility | pure transform | `src/taskmanager/application/dto/results.py::TaskResult.from_entity` (entity → other shape) | role-match |
| `src/taskmanager/infrastructure/db/errors.py` | utility (error translation) | transform | `src/taskmanager/presentation/api/errors/mapping.py` + `problem.py` | role-match |
| `src/taskmanager/infrastructure/db/engine.py` | factory/config | resource construction | `src/taskmanager/infrastructure/config/settings.py::get_settings` | role-match |
| `src/taskmanager/infrastructure/db/unit_of_work.py` | adapter (transaction) | transactional context manager | `tests/unit/application/fakes.py::FakeUnitOfWork` | **exact** |
| `src/taskmanager/infrastructure/db/repositories/tasks.py` | repository adapter | CRUD + aggregate query | `tests/unit/application/fakes.py::FakeTaskRepository` | **exact** |
| `src/taskmanager/infrastructure/db/repositories/task_lists.py` | repository adapter | CRUD | `tests/unit/application/fakes.py::FakeTaskListRepository` | **exact** |
| `src/taskmanager/infrastructure/db/repositories/users.py` | repository adapter | CRUD | `tests/unit/application/fakes.py::FakeUserRepository` | **exact** |
| `src/taskmanager/infrastructure/clock.py` | adapter | in-memory read | `tests/unit/application/fakes.py::FrozenClock` | **exact** |
| `src/taskmanager/presentation/api/dependencies.py` | provider (FastAPI DI) | request-scoped construction | `src/taskmanager/presentation/api/errors/handlers.py::register_exception_handlers` | partial — first `Depends` in the repo |
| `src/taskmanager/presentation/api/health.py` | route/controller | request-response | `tests/probe.py` (router shape) + `errors/problem.py` (response building) | role-match |

### Modified source

| File | Role | Data Flow | What changes | Analog for the change |
|------|------|-----------|--------------|------------------------|
| `src/taskmanager/main.py` | composition root | app construction | engine + session factory on `app.state`, lifespan, `include_router(health_router)` | its own L16-25 + `register_exception_handlers` call |
| `src/taskmanager/infrastructure/config/settings.py` | config | env → typed object | add `test_database_url: str \| None = None` | its own L27-32 field block |
| `src/taskmanager/__init__.py` | package init | — | **gap**: `/health` needs a version; today `main.py` L21 hardcodes `"0.1.0"` and this file is empty | see "Open Gap" below |

### New test modules

| New File | Role | Data Flow | Closest Analog | Match Quality |
|----------|------|-----------|----------------|---------------|
| `tests/integration/__init__.py` | package init | — | `tests/unit/application/__init__.py` | exact (empty) |
| `tests/integration/conftest.py` | fixtures | DB session lifecycle | `tests/conftest.py` | role-match (async fixtures, docstring style) |
| `tests/integration/test_unit_of_work.py` | integration test | transaction | `tests/unit/application/test_ports.py` L94-130 (UoW commit/rollback assertions) | **exact** (behaviour), role-match (mechanism) |
| `tests/integration/test_repositories_*.py` | integration test | CRUD | `tests/unit/application/test_change_task_status.py` | role-match |
| `tests/integration/test_migrations.py` | integration test | schema | — | none |
| `tests/integration/test_constraints.py` | integration test | schema | — | none |
| `tests/integration/test_schema.py` | integration test | schema | — | none |
| `tests/integration/test_health.py` | API test | request-response | `tests/api/test_error_contract.py` | **exact** |
| `tests/unit/infrastructure/__init__.py` | package init | — | `tests/unit/application/__init__.py` | exact |
| `tests/unit/infrastructure/test_mappers.py` | unit test | pure transform | `tests/unit/domain/test_task.py` | role-match |
| `tests/unit/infrastructure/test_clock.py` | unit test | — | `tests/unit/application/test_ports.py` L82-91 | **exact** |
| `tests/unit/infrastructure/test_database_url.py` | unit test | pure transform | `tests/unit/test_settings.py` | role-match |
| `tests/unit/infrastructure/test_errors.py` | unit test | pure transform | `tests/unit/domain/test_exceptions.py` | role-match |
| `tests/unit/infrastructure/test_models.py` | unit test (introspection) | — | `tests/architecture/test_layer_boundaries.py` L26-39 (vacuity guard) | role-match |
| `tests/unit/infrastructure/test_adapter_ports.py` | unit test (conformance) | — | `tests/unit/application/test_ports.py` L47-64 | **exact** |
| `tests/unit/presentation/__init__.py` | package init | — | `tests/unit/application/__init__.py` | exact |
| `tests/unit/presentation/test_health.py` | unit test (API) | request-response | `tests/unit/test_app_factory.py` | role-match |
| `tests/architecture/test_no_commit_in_repositories.py` | architecture test | source-text scan | `tests/architecture/test_domain_is_stdlib_only.py` | **exact** |

### Modified tests & config

| File | Change | Analog |
|------|--------|--------|
| `tests/unit/test_settings.py` | `TEST_DATABASE_URL` in `ENV` dict; parity test unchanged | its own L12-15, L75-83 |
| `tests/unit/test_app_factory.py` | assert engine/session factory on `app.state`; assert `/health` route present | its own L58-67 (route-absence assertion, inverted) |
| `tests/conftest.py` | may need `TEST_DATABASE_URL` monkeypatch if `Settings` gains the field with `extra="forbid"` | its own L28-39 |
| `Dockerfile` | `COPY alembic.ini`, `COPY migrations`, `COPY docker/entrypoint.sh`, `ENTRYPOINT`, `HEALTHCHECK` in `runtime`; `COPY alembic.ini migrations` in `test` | its own L56-65 and L72-85 |
| `Makefile` | real `up` / `down` / `docker-test`; new `run` | its own L55-69 |
| `.env.example` | `TEST_DATABASE_URL` + compose-vs-localhost comment on `DATABASE_URL` | its own L17-19 |
| `.flake8` | **no change** if the directory is named `migrations/` (L7 already excludes it) | its own L7 |
| `.github/workflows/ci.yml` | likely **no change** — the Postgres service on `taskmanager_test` is already there (L29-54) | — |
| `DECISION_LOG.md` | new ADRs (WR-05 resolution, compose/test-stage follow-up to ADR-017/018, published 5432, `test_database_url` on `Settings`) | existing ADR entries |

### New root artifacts

| File | Role | Data Flow | Analog | Match Quality |
|------|------|-----------|--------|---------------|
| `alembic.ini` | config | — | `.flake8` / `pytest.ini` (comment-heavy config style) | partial (style only) |
| `migrations/env.py` | script | migration driver | — | none |
| `migrations/script.py.mako` | template | — | — | none |
| `migrations/versions/0001_baseline.py` | migration | DDL | — | none |
| `docker-compose.yml` | config | orchestration | `.github/workflows/ci.yml` L29-48 (the `db` service + healthcheck) | partial — **copy the healthcheck reasoning verbatim** |
| `docker/entrypoint.sh` | script | startup sequence | — | none |
| `docker/initdb/01-create-test-database.sql` | script (SQL) | — | — | none |

---

## Pattern Assignments

### `src/taskmanager/infrastructure/db/unit_of_work.py` (adapter, transaction)

**Analog:** `tests/unit/application/fakes.py::FakeUnitOfWork` (L162-232) — this is an *exact*
behavioural analog: it was written specifically to model the contract this adapter must honour.

**Port-type annotation pattern** (`tests/unit/application/fakes.py` L173-179, L193-195) — the
single most load-bearing convention in this file:

```python
    Each repository is reachable under two names, and that is not redundancy.
    `UnitOfWork` declares `tasks`, `task_lists` and `users` as mutable attributes,
    and mypy checks a mutable protocol member *invariantly* - so the attribute
    the use case sees has to be annotated with the port type exactly, or this
    class stops satisfying the port at all. ...
```

```python
        self.tasks: TaskRepository = self.task_repository
        self.task_lists: TaskListRepository = self.task_list_repository
        self.users: UserRepository = self.user_repository
```

**Rollback-on-every-exit-path pattern** (`tests/unit/application/fakes.py` L204-232) — copy the
`_finished`/`_committed` flag mechanics and the two "deliberate non-behaviours" comment:

```python
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        # The port makes this method responsible for rolling back whatever was
        # not committed, on every exit path, so the fake models exactly that.
        ...
        if not self._finished:
            self.rollbacks += 1
        self._finished = False
        # Two deliberate non-behaviours, both load-bearing. Returning `None`
        # rather than a true value means an exception leaving the block is
        # never swallowed, so a failing use case cannot answer 200. And no
        # automatic commit happens here: D-17 and ARC-08 put the commit in the
        # use case, explicitly, which is what the `commits` counter measures.
        return None

    async def commit(self) -> None:
        self.commits += 1
        self._finished = True

    async def rollback(self) -> None:
        self.rollbacks += 1
        self._finished = True
```

**Contract being implemented** (`src/taskmanager/application/ports/unit_of_work.py` L44-66) —
note `__aenter__ -> Self` and the normative MUST comments:

```python
class UnitOfWork(Protocol):
    """One transaction, the three repositories inside it, and its two verbs."""

    task_lists: TaskListRepository
    tasks: TaskRepository
    users: UserRepository

    async def __aenter__(self) -> Self: ...

    # Two obligations, both part of the contract. An implementation MUST roll
    # back anything `commit()` did not make durable, on every exit path. And it
    # MUST return `None`: returning a true value would swallow the exception
    # that left the block, so a failed use case would answer 200.
```

**Imports pattern** (`tests/unit/application/fakes.py` L18-34): stdlib first, then
`taskmanager.application...`, then `taskmanager.domain...`, isort `profile = "black"` with
`known_first_party = ["taskmanager"]` (`pyproject.toml` L21-24). Multi-name imports use the
parenthesised trailing-comma form:

```python
from types import TracebackType
from typing import Self
from uuid import UUID

from taskmanager.application.ports.repositories import (
    TaskListRepository,
    TaskRepository,
    UserRepository,
)
```

---

### `src/taskmanager/infrastructure/db/repositories/*.py` (repository adapter, CRUD)

**Analog:** `tests/unit/application/fakes.py::FakeTaskRepository` (L37-90),
`FakeTaskListRepository` (L93-132), `FakeUserRepository` (L135-159).
**Contract:** `src/taskmanager/application/ports/repositories.py` L35-84.

**Method signature set to implement verbatim** (`application/ports/repositories.py` L35-57) —
keyword-only `status`/`priority`, `Sequence[Task]` return, `CompletionStats`:

```python
class TaskRepository(Protocol):
    """Persistence for the `Task` aggregate, plus the list-level counters."""

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
    ) -> Sequence[Task]: ...

    async def completion_stats(self, task_list_id: UUID) -> CompletionStats: ...
```

**Case-folding semantics the SQL adapter must reproduce** (`fakes.py` L124-132 and L145-152).
The fake documents the exact rule the unique index and the `get_by_email` query must match:

```python
    async def exists_with_name(self, owner_id: UUID, name: str) -> bool:
        # Case-insensitive, matching the `(owner_id, lower(name))` unique index
        # LIST-06 asks Phase 3 for; a fake that compared case-sensitively would
        # let a use-case test pass against a rule the database will refuse.
        return any(
            task_list.owner_id == owner_id
            and task_list.name.casefold() == name.strip().casefold()
            for task_list in self.stored.values()
        )
```

> **Planner note — a real inconsistency to resolve, not to paper over.** `fakes.py` L125-126
> says the index is on `(owner_id, lower(name))`, `task_list.py` L13 says the same, but CONTEXT
> D-12 specifies `uq_task_lists_owner_id_name` as a plain `UNIQUE (owner_id, name)`
> (case-*sensitive*). One of the two must move. Decide explicitly in the plan and, if the
> database stays case-sensitive, fix the fake's comment and its `casefold()` in the same task —
> otherwise a Phase 4 use-case test passes against a rule PostgreSQL will not enforce.

**Error-translation call shape** (D-13) — the `DomainError` leaves to raise already exist,
with their exact constructor signatures (`src/taskmanager/domain/exceptions.py` L157-186):

```python
class DuplicateTaskListNameError(ConflictError):
    """Raised when an owner already has a task list under the same name."""
    def __init__(self, name: str) -> None: ...


class EmailAlreadyRegisteredError(ConflictError):
    """Raised when a registration reuses an address that already has an account."""
    def __init__(self) -> None: ...          # takes NO argument - the address is deliberately absent
```

And the not-found leaves for FK violations (`domain/exceptions.py` L111-147):
`TaskNotFoundError(task_id: UUID)`, `TaskListNotFoundError(task_list_id: UUID)`,
`UserNotFoundError(user_id: UUID)`.

**Security constraint on `details`** (`domain/exceptions.py` L31-40) — the repository must not
put a constraint name or SQL into `details`; the alias only permits scalars:

```python
DetailValue = str | int | float | bool | None
Details = dict[str, DetailValue]
```

**No `.commit()` anywhere in this directory** — enforced by the new architecture test below.

---

### `src/taskmanager/infrastructure/db/models.py` (ORM model, persistence schema)

**Analog for the field set:** the three domain entities. The ORM rows must round-trip exactly
these fields and nothing else.

`src/taskmanager/domain/entities/task.py` L43-56:

```python
    id: UUID
    task_list_id: UUID
    title: str
    status: TaskStatus
    priority: TaskPriority
    created_at: datetime
    updated_at: datetime
    description: str | None = None
    due_date: datetime | None = None
    completed_at: datetime | None = None
    assignee_id: UUID | None = None
```

`src/taskmanager/domain/entities/task_list.py` L39-44:

```python
    id: UUID
    owner_id: UUID
    name: str
    created_at: datetime
    updated_at: datetime
    description: str | None = None
```

`src/taskmanager/domain/entities/user.py` L38-42:

```python
    id: UUID
    email: str
    password_hash: str
    created_at: datetime
    updated_at: datetime
```

> **Two schema deltas the planner must reconcile with CONTEXT D-10.** D-10 lists `users` as
> `(id, email, password_hash, created_at)` — the entity also has `updated_at` (L42). D-10 omits
> `task_lists.description` — the entity has it (L44). Both columns must exist in the baseline
> migration or the mapper cannot round-trip; flag them as a corrected reading of D-10 rather
> than adding a second revision later.

**Column length caps come from the entities' `ClassVar`s** — a `String(n)` that disagrees would
be caught by `alembic check` (`compare_type=True`):

| Column | `String(n)` | Source |
|--------|-------------|--------|
| `tasks.title` | 200 | `task.py` L39 `TITLE_MAX_LENGTH: ClassVar[int] = 200` |
| `tasks.description` | 2000 | `task.py` L41 `DESCRIPTION_MAX_LENGTH` |
| `task_lists.name` | 120 | `task_list.py` L34 `NAME_MAX_LENGTH: ClassVar[int] = 120` |
| `task_lists.description` | 2000 | `task_list.py` L37 |
| `users.email` | 320 | `user.py` L31 `EMAIL_MAX_LENGTH` |
| `users.password_hash` | 512 | `user.py` L36 `PASSWORD_HASH_MAX_LENGTH` |

**CHECK constraint value lists come from the enums** (`domain/value_objects/task_status.py`
L20-26). `StrEnum`, so `TaskStatus.COMPLETED.value == "completed"`:

```python
class TaskStatus(StrEnum):
    """The three states a task can be in, in lifecycle order."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
```

The `ck_tasks_completed_at_matches_status` constraint is the database copy of the entity
invariant at `domain/entities/task.py` L83-87:

```python
        if (self.status is TaskStatus.COMPLETED) != (self.completed_at is not None):
            raise ValidationError(
                "completed_at must be set exactly when status is completed.",
                details={"field": "completed_at"},
            )
```

**Model/DDL shapes:** see `03-RESEARCH.md` Pattern 2 (verified `NAMING_CONVENTION`, `Uuid()`,
`DateTime(timezone=True)`, `CheckConstraint(..., name="status")` → `ck_tasks_status`).

---

### `src/taskmanager/infrastructure/db/constraints.py` (constants)

**Analog:** `src/taskmanager/presentation/api/errors/problem.py` L17-21 and
`src/taskmanager/domain/value_objects/task_status.py` L17, L30 — module-level `Final` with a
docstring explaining *why the constant exists in one place*:

```python
from typing import Any, Final

from fastapi.responses import JSONResponse

PROBLEM_JSON: Final[str] = "application/problem+json"
```

```python
ALLOWED_TRANSITIONS: Final[Mapping[TaskStatus, frozenset[TaskStatus]]] = {
```

The "one source, two readers" rationale to reproduce is in `problem.py` L9-14:

```python
The other rejected alternative is each handler assembling its own dict. The
CLAUDE.md error-handling rule forbids it, and for a concrete reason: two
handlers written a week apart drift in member order, in spelling and in which
members they bother to include, and the "one shape" claim of ARC-07 quietly
stops being true.
```

---

### `src/taskmanager/infrastructure/db/errors.py` (utility, transform)

**Analog:** `src/taskmanager/presentation/api/errors/problem.py` (single translation function,
keyword-only, `Final` media type) and `handlers.py` L51-83 (narrow-then-translate shape).

**The `isinstance`-narrowing idiom under mypy strict** — `handlers.py` L6-18 already explains
why the narrow annotation is illegal and the narrowing is mandatory. `errors.py` faces the same
problem with `IntegrityError.orig: BaseException | None`:

```python
Every handler annotates its exception parameter with the bare `Exception` type
and narrows on its first line with an `isinstance` assertion. ... The rejected
fixes were a type-ignore comment, which would hide a real variance rule, and
`if not isinstance(...): raise`, which adds four partial branches no test can
reach while the 100% presentation coverage gate forbids a suppression comment.
```

Note the difference: `handlers.py` uses `assert isinstance(...)` because coverage does not count
an assert as a branch; `errors.py` needs a real `if isinstance(...)` because the `None` case is
reachable and must be tested (D-13 "unrecognised constraint re-raises").

**Keyword-only signature convention** (`problem.py` L24-38):

```python
def problem(
    *,
    code: str,
    title: str,
    status: int,
    detail: str,
    instance: str,
    errors: Any = None,
) -> JSONResponse:
    """Build the one RFC 9457 body shape: D-06 members in order, `errors` last.

    Arguments are keyword-only because five of the six are strings: a
    positional call site would be one transposition away from serving the
    title as the detail, and no test would notice.
    """
```

---

### `src/taskmanager/infrastructure/db/engine.py` (factory)

**Analog:** `src/taskmanager/infrastructure/config/settings.py` L1-38 — the factory-function
convention (`get_settings()`), and the module docstring that states what a default would cost:

```python
"""Application settings loaded from the process environment.

`database_url` and `jwt_secret` deliberately carry no default: a misconfigured
process must fail at boot with a single readable ValidationError listing every
missing variable, rather than starting up on a placeholder secret and failing
at the first authenticated request.
"""
```

**No module-level instantiation** (`src/taskmanager/main.py` L1-8) — the same argument applies
verbatim to the engine (Anti-Pattern 10):

```python
"""Composition root: builds the FastAPI application.

`create_app` is a factory rather than a module-level `app = create_app()`.
A module-level instance would evaluate the settings at import time, which makes
`import taskmanager.main` crash in any environment without JWT_SECRET -
including mypy's, import-linter's and a plain `docker build`. The container
runs `uvicorn --factory taskmanager.main:create_app`.
"""
```

Engine/session-factory shapes: `03-RESEARCH.md` Pattern 1 (`pool_pre_ping=True`,
`async_sessionmaker(expire_on_commit=False, autoflush=False)`).

---

### `src/taskmanager/infrastructure/clock.py` (adapter)

**Analog:** `tests/unit/application/fakes.py::FrozenClock` L235-248 and the port at
`src/taskmanager/application/ports/clock.py` L22-25:

```python
class Clock(Protocol):
    """Reads the current moment, as an aware UTC `datetime` (D-14)."""

    def now(self) -> datetime: ...
```

Note: `Clock` is the **one port that is not `async`** (`clock.py` L12-16). `SystemClock.now()`
is a plain `def` returning `datetime.now(UTC)`.

---

### `src/taskmanager/main.py` (composition root — modified)

**Analog:** itself, L16-25. Extend in place; do not restructure.

```python
def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the application, optionally with explicitly injected settings."""
    resolved = settings or get_settings()
    app = FastAPI(
        title=resolved.app_name,
        version="0.1.0",
        openapi_url="/openapi.json",
    )
    register_exception_handlers(app)
    return app
```

**Hard constraint this must keep**: `tests/conftest.py` L36 and `tests/unit/test_app_factory.py`
L27 both call `create_app(Settings(_env_file=None))` with a fake DSN and **no database running**.
`create_async_engine` opens no connection, so this stays true — but a `SELECT 1` at startup or a
migration in the lifespan would break every existing API test.

**Existing registration convention to mirror for the router** (`presentation/api/errors/handlers.py`
L152-164) — imperative, called from `create_app`, never a decorator on a module-level app:

```python
def register_exception_handlers(app: FastAPI) -> None:
    """Install the single exception-handling point of ARC-07, from create_app()."""
    app.add_exception_handler(DomainError, handle_domain_error)
    ...
```

---

### `src/taskmanager/presentation/api/health.py` (route, request-response)

**Analog for router construction:** `tests/probe.py` L35, L45-48 — module-level `APIRouter()`
named for its purpose, `async def` handlers with a docstring per route:

```python
probe_router = APIRouter()


@probe_router.get("/_probe/domain", include_in_schema=False)
async def probe_domain() -> dict[str, str]:
    """Raise a grandchild of `DomainError`, to prove the MRO walk reaches it."""
```

`/health` differs in two ways: it **is** in the schema (no `include_in_schema=False`), and it
returns a Pydantic `response_model` rather than a dict (see `03-RESEARCH.md` Pattern 8).

**Response-shape discipline** (`presentation/api/errors/problem.py` L43-55) — build the body as a
dict literal in contract order; the same insertion-order reasoning applies to the D-08 document:

```python
    # Member order is not decoration. Python dicts are insertion-ordered and
    # `json.dumps` writes keys in insertion order, so building the body as a
    # literal in this order is what makes D-06's "always in this order"
    # mechanically true rather than aspirational.
```

**C-4 reminder:** `/health` must NOT emit problem+json (D-08). Do not route it through
`problem()`. Use `response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE` on the injected
`Response` so both legs share one body shape.

---

### `src/taskmanager/presentation/api/dependencies.py` (provider)

No `Depends` exists in the repository yet — this is the first. Two existing facts constrain it:

1. `.flake8` L8 already whitelists the call in a default argument, so `Depends(...)` will not
   trip flake8-bugbear B008:
   ```ini
   extend-immutable-calls = fastapi.Depends,fastapi.Query,fastapi.Path,fastapi.Body,fastapi.Header
   ```
2. `app.state` is untyped (`State.__getattr__ -> Any`), which mypy strict flags as an implicit
   `Any`. Decide the read-back shape once here — see `03-RESEARCH.md` Pattern 1's note.

---

### `src/taskmanager/infrastructure/config/settings.py` (modified)

**Analog:** its own field block, L27-32. Add one field in the same style:

```python
    app_name: str = "Task Manager API"
    environment: str = "local"
    database_url: str
    jwt_secret: str = Field(min_length=16)
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = Field(default=30, gt=0)
```

**The gate this trips** (`tests/unit/test_settings.py` L75-83) — exact set equality, and
`extra="forbid"` (`settings.py` L22-23) means an undeclared key in a developer's `.env` is a boot
failure. `TEST_DATABASE_URL` therefore goes in **both** `Settings` and `.env.example`, or neither:

```python
def test_env_example_documents_every_field() -> None:
    """.env.example documents every declared field and nothing else."""
    documented = {
        line.split("=", 1)[0].strip()
        for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines()
        if "=" in line and not line.strip().startswith("#")
    }

    assert documented == {name.upper() for name in Settings.model_fields}
```

**`.env.example` entry style to copy** (`.env.example` L17-19) — a comment naming the consumer,
then the key:

```
# PostgreSQL DSN used by SQLAlchemy through the psycopg 3 driver.
# Declared from the start so CI can export it; first consumed in Phase 3.
DATABASE_URL=postgresql+psycopg://taskmanager:taskmanager@localhost:5432/taskmanager
```

---

### `tests/integration/conftest.py` (fixtures)

**Analog:** `tests/conftest.py` L1-47 — docstring that names the three shapes deliberately
absent, no `@pytest_asyncio.fixture` decorator, no `asyncio` marker, plain `@pytest.fixture` on
async generators:

```python
"""Fixtures shared by the API-level tests: the app and its two HTTP clients.

Three shapes that a reader may expect here are deliberately absent: the
asyncio-specific fixture decorator, the per-test asyncio marker, and a
hand-rolled replacement for pytest-asyncio's own loop fixture. `pytest.ini`
sets `asyncio_mode = auto` and `asyncio_default_fixture_loop_scope = function`,
which already covers both async tests and async-generator fixtures, and the
loop override in particular has been removed from pytest-asyncio itself.
"""
```

```python
@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """The default client: an exception escaping the app fails the test."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client
```

**Root-path derivation idiom** (`tests/unit/test_settings.py` L17-18 — comment spelling out the
`parents[n]` hop count, which is the convention, not just `Path(...).parents[2]`):

```python
# tests/unit/test_settings.py -> tests/unit -> tests -> repository root.
ENV_EXAMPLE = Path(__file__).resolve().parents[2] / ".env.example"
```

Fixture bodies (`database_url`, `_require_database`, `migrated_database`, `connection`,
`session_factory`, `uow`) are given in full in `03-RESEARCH.md` §"Integration-test fixtures".

---

### `tests/architecture/test_no_commit_in_repositories.py` (architecture test)

**Analog:** `tests/architecture/test_domain_is_stdlib_only.py` — an *exact* structural match: a
source-tree scan with a module docstring justifying the technique, a path constant, a vacuity
guard test, and the assertion test.

**Path constant + vacuity guard** (L34-50, L69-79) — the guard is the part most likely to be
skipped and must not be:

```python
DOMAIN_ROOT = Path(__file__).resolve().parents[2] / "src" / "taskmanager" / "domain"

MINIMUM_DOMAIN_MODULES = 10

REQUIRED_SCANNED_MODULES = frozenset(
    {
        "exceptions.py",
        "validation.py",
        "value_objects/task_status.py",
        "entities/task.py",
    }
)


def _domain_modules() -> list[Path]:
    """Every `.py` file under the domain package, in a stable order."""
    return sorted(DOMAIN_ROOT.rglob("*.py"))
```

```python
def test_the_domain_package_is_actually_scanned() -> None:
    """A glob that matches nothing passes vacuously; assert it matched the real tree.

    Without this guard a renamed directory, a moved `src/` layout or a typo in
    `DOMAIN_ROOT` would leave `test_domain_imports_only_stdlib` asserting that an empty
    list is empty - green forever, checking nothing, which is worse than no test at all.
    """
```

**Violation-list assertion form** (L82-91) — build a list of offenders, assert it equals `[]`:

```python
def test_domain_imports_only_stdlib() -> None:
    """Every import root under `taskmanager.domain` is stdlib or `taskmanager`."""
    violations = [
        (path.relative_to(DOMAIN_ROOT).as_posix(), root)
        for path in _domain_modules()
        for root in sorted(_imported_roots(path))
        if root != "taskmanager" and root not in sys.stdlib_module_names
    ]

    assert violations == []
```

The same file's L9-27 also shows the "Deliberately NOT used: ..." convention for recording the
rejected implementation (AST walk vs text scan — see `03-RESEARCH.md` L1486-1490).

**The other architecture-test analog** (`tests/architecture/test_layer_boundaries.py` L26-39)
shows the same vacuity concern applied to configuration rather than a glob.

---

### `tests/unit/infrastructure/test_adapter_ports.py` (conformance test)

**Analog:** `tests/unit/application/test_ports.py` L1-14 (docstring explaining that the proof is
static) and L47-64 (the binding pattern). Copy both exactly:

```python
"""Conformance: every one of the eight ports has an implementation satisfying it.

The proof itself is static. Each test below binds a fake to a local annotated
with the Protocol, and mypy strict accepts that assignment only if the fake
matches the port structurally, method by method, including keyword-only
parameters and return types. `make typecheck` is therefore the gate; these tests
are what makes ARC-04 *visible* ...

The alternative form, a module-level `_: type[TaskRepository] = FakeTaskRepository`
constant, is not used: inside a function flake8 reports it as an assigned-but-
unused local, and at module level it never appears in the report at all.
"""
```

```python
def test_fake_task_repository_satisfies_the_task_repository_port() -> None:
    repository: TaskRepository = FakeTaskRepository()
    assert repository is not None


def test_fake_unit_of_work_satisfies_the_unit_of_work_port() -> None:
    unit_of_work: UnitOfWork = FakeUnitOfWork()
    assert unit_of_work is not None
```

---

### `tests/integration/test_unit_of_work.py` (integration test, transaction)

**Analog for the behaviours to assert:** `tests/unit/application/test_ports.py` L94-130. The
three fake-UoW tests are the exact three properties the SQLAlchemy adapter must now demonstrate
against a real transaction:

```python
async def test_fake_unit_of_work_rolls_back_a_block_that_never_committed() -> None:
    """`__aexit__` owns the rollback, per the port; the fake has to model that.

    Without this behaviour `rollbacks` is a counter nothing increments, and no
    test in the suite could fail if Phase 3's SQLAlchemy adapter forgot to roll
    back - `commits == 0` proves nothing was written, not that the session was
    returned clean.
    """
```

Test-naming convention: full sentences, `test_<subject>_<verb>_<object>`, docstring stating the
*property*, not the mechanics. Fixed literals over generated ones (`test_ports.py` L41-44):

```python
# Fixed on purpose: a generated identifier or a clock reading would make the
# percentage assertion below unfalsifiable.
NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
TASK_LIST_ID = UUID("22222222-2222-4222-8222-222222222222")
```

---

### `tests/integration/test_health.py` and `tests/unit/presentation/test_health.py`

**Analog:** `tests/api/test_error_contract.py` L1-41 — module docstring naming the success
criterion, module-level contract constants, one assertion block per response property:

```python
"""The RFC 9457 error contract, asserted end to end against the probe router.

This suite is the proof required by roadmap success criterion 4: the single
exception-handling point behaves correctly *before* the first real router
exists. ...
"""

PROBLEM_JSON = "application/problem+json"
# The full D-06 member list, in the order the contract promises.
MEMBERS = ["type", "title", "status", "detail", "instance", "code"]


async def test_domain_error_subclass_becomes_problem_json_409(
    client: AsyncClient,
) -> None:
    """A refused status transition answers 409 with the complete D-06 body."""
    response = await client.get("/_probe/domain")

    assert response.status_code == 409
    # Exactly, not `startswith`: the point is that there is no charset suffix.
    assert response.headers["content-type"] == PROBLEM_JSON

    body = response.json()

    assert list(body) == [*MEMBERS, "errors"]
```

`assert list(body) == [...]` (key order, not just membership) is the convention to reuse for the
D-08 `{"status", "checks", "version"}` document.

**Caution (Pitfall 4):** this file's `caplog` assertions break if Alembic's `fileConfig` runs
with `disable_existing_loggers=True`. The `migrations/env.py` guard is not optional.

---

### `Dockerfile` (modified)

**Analog:** itself. The `runtime` stage today (L46-65) copies **no application files**:

```dockerfile
FROM python:3.13-slim-trixie AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# A dedicated system account with no login shell, rather than loosening
# permissions on the application directory.
RUN useradd --system --create-home --shell /usr/sbin/nologin app

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
USER app

# No configuration value is baked in here. Every setting - including the two with
# no default - is injected at run time by the environment (compose, Phase 3).
EXPOSE 8000
CMD ["uvicorn", "--factory", "taskmanager.main:create_app", \
     "--host", "0.0.0.0", "--port", "8000"]
```

`USER app` is set at L59, **before** any new `COPY` would land — so the new lines need
`--chown=app:app` or must sit above L59. The `test` stage's existing copy line (L78) is the
pattern for the new one:

```dockerfile
COPY pytest.ini .flake8 .importlinter .env.example ./
COPY tests ./tests
```

Note `.dockerignore` does **not** exclude `alembic.ini`, `migrations/` or `docker/` — they are
simply never copied today.

---

### `docker-compose.yml` (new)

**Analog:** `.github/workflows/ci.yml` L29-48. Copy the healthcheck *and its comment* — the
`-h 127.0.0.1` reasoning is already written down here and must not be re-derived:

```yaml
    services:
      postgres:
        image: postgres:18-alpine
        env:
          POSTGRES_USER: taskmanager
          POSTGRES_PASSWORD: taskmanager
          POSTGRES_DB: taskmanager_test
        ports:
          - 5432:5432
        # `-h 127.0.0.1` is load-bearing: the official image's init-time server listens
        # only on a Unix socket, so a health command without it reports ready too early.
        # The runner blocks on this declared check before the first step, which is why
        # there is no hand-rolled `until pg_isready` loop anywhere in this file.
        options: >-
          --health-cmd "pg_isready -h 127.0.0.1 -U taskmanager -d taskmanager_test"
          --health-interval 5s
          --health-timeout 5s
          --health-retries 10
          --health-start-period 10s
```

Credential convention (`ci.yml` L49-54): obviously-fake `taskmanager/taskmanager`, with a comment
saying so. Compose service shapes: `03-RESEARCH.md` Pattern 6.

---

### `Makefile` (modified)

**Analog:** itself, L55-69. The placeholders already name Phase 3 as their replacement:

```make
test:
	$(VENV)/bin/pytest

# Runs the suite on Python 3.13 with no host Python involved. Phase 3 replaces
# the body with a compose invocation; the target name stays, so no documentation
# has to change.
docker-test:
	docker build --target test -t taskmanager-test .
	docker run --rm taskmanager-test

up:
	@echo "docker compose arrives in Phase 3. For now: make docker-test"

down:
	@echo "docker compose arrives in Phase 3; there is nothing to stop yet."
```

Two file-level constraints (`Makefile` L3-11): GNU Make 3.81 — **every recipe line runs in its
own shell**, so anything needing shared state is joined with `&&` on one line; and every tool is
invoked through an explicit `$(VENV)/bin/` path. The new `run` target must therefore be
`$(VENV)/bin/uvicorn ...`, not bare `uvicorn`. Add `run` to `.PHONY` (L13).

---

## Shared Patterns

### Module docstring: state the rejected alternative and why

**Source:** every module in `src/`. Clearest examples:
`src/taskmanager/application/ports/repositories.py` L1-21,
`src/taskmanager/application/ports/unit_of_work.py` L1-32,
`src/taskmanager/presentation/api/errors/problem.py` L1-15,
`tests/probe.py` L1-14.
**Apply to:** every new module in this phase, source and test.

```python
"""The three persistence ports, expressed entirely in domain entities.

The rejected alternative is a repository that hands back ORM rows, or a
SQLAlchemy `Result` the use case has to unpack. That shape would drag the
persistence library's vocabulary - and its lazy-loading behaviour - straight
into the application layer, and every use-case test would then need a database
to produce a single object. ...
"""
```

The form is consistent: one-line summary, blank line, then the alternative(s) that a reader
might expect and the concrete failure each would cause. Requirement/decision IDs (D-13, ARC-08,
LIST-06) are cited inline. This is the project's dominant signal of deliberate design — a new
module without it will read as generated.

### Inline comments explain *why*, at the line that would otherwise look wrong

**Source:** `src/taskmanager/application/use_cases/tasks/change_task_status.py` L86-94,
`tests/unit/application/fakes.py` L83-85, `src/taskmanager/presentation/api/errors/problem.py`
L51-52.
**Apply to:** every non-obvious line in this phase — `join_transaction_mode="create_savepoint"`,
`flush()`-not-`commit()`, `expire_on_commit=False`, `-h 127.0.0.1`, `--chown=app:app`.

```python
            # The entity owns the state machine and the timestamps; this line
            # is the only place the clock is read, and the instant is handed
            # down rather than looked up again (D-13).
            task.change_status(command.new_status, now=self._clock.now())
            await self._uow.tasks.update(task)
            await self._uow.commit()
        # Mapped outside the block: the result describes a transaction that has
        # already been made durable, never one still in flight.
        return TaskResult.from_entity(task)
```

### Package `__init__.py` files are empty

**Source:** `src/taskmanager/__init__.py`, `src/taskmanager/infrastructure/__init__.py`,
`src/taskmanager/infrastructure/config/__init__.py`, `tests/unit/application/__init__.py` — all
zero bytes.
**Apply to:** `infrastructure/db/__init__.py`, `infrastructure/db/repositories/__init__.py`,
`tests/integration/__init__.py`, `tests/unit/infrastructure/__init__.py`,
`tests/unit/presentation/__init__.py`. No re-export barrels; import from the defining module.

### Typing conventions

**Source:** `pyproject.toml` L26-34 (`strict = true`, `warn_unreachable = true`),
`domain/exceptions.py` L26-40, `domain/value_objects/task_status.py` L17.
**Apply to:** all new source.

- PEP 604 unions (`str | None`), never `Optional[...]` / `Union[...]` — consistent across every
  file read.
- `from collections.abc import Sequence, Callable, Mapping, AsyncIterator`, never `typing.*`
  equivalents.
- `Final` for module constants; `ClassVar` for class-level constants
  (`domain/entities/task.py` L39-41 explains why: without it they become dataclass fields).
- `Self` from `typing` for `__aenter__` (`ports/unit_of_work.py` L35, L51).
- No `# type: ignore` anywhere in `src/` or `tests/` today. Do not introduce the first one.

### Test conventions

**Source:** `pytest.ini`, `tests/unit/application/test_ports.py`, `tests/api/test_error_contract.py`.
**Apply to:** every new test.

```ini
asyncio_mode = auto
asyncio_default_fixture_loop_scope = function
addopts =
    -ra
    --strict-markers
    --strict-config
    --cov=taskmanager
    --cov-fail-under=75
markers =
    unit: pure domain/application tests, no I/O
    integration: tests that touch PostgreSQL
filterwarnings =
    error
```

- `async def test_...` with **no** `@pytest.mark.asyncio` (auto mode).
- `--strict-markers`: `pytestmark = pytest.mark.integration` is legal only because `integration`
  is declared above.
- `filterwarnings = error`: any SQLAlchemy/Alembic deprecation fails the suite.
- Every test has a docstring stating the property under test.
- Fixed UUID/datetime literals, never `uuid4()`/`now()` in an assertion path.

### Layer and gate constraints that apply to every file

**Source:** `.importlinter` L16-64, `CLAUDE.md` §"Project Rules".

```ini
[importlinter:contract:application-framework-free]
name = Application knows no web framework or ORM
source_modules =
    taskmanager.application
forbidden_modules =
    fastapi
    starlette
    sqlalchemy
    alembic
    jwt
    pwdlib
```

- `sqlalchemy` may appear **only** under `taskmanager.infrastructure` and
  `taskmanager.presentation` (and `migrations/`, which is outside the root package).
- `tests/architecture/test_layer_boundaries.py` (L42-44) picks up the new modules automatically —
  no change needed there.
- Coverage source is `taskmanager` with **no `omit`** (`pyproject.toml` L36-38) and no
  `pragma: no cover`. Anything placed under `src/taskmanager/` must be tested — this is the
  argument for keeping the entrypoint retry loop in `docker/entrypoint.sh` rather than in a
  module (RESEARCH Open Question 1).
- A new gate must be added to **both** `.pre-commit-config.yaml` and `.github/workflows/ci.yml`
  (CLAUDE.md); neither derives from the other. The `.commit()` gate is a pytest test, so it rides
  along in both through `pytest` — no new hook needed.

---

## No Analog Found

Files with no close match in the codebase. The planner should use `03-RESEARCH.md` (which
contains verified, executed code for each) rather than inventing a shape.

| File | Role | Data Flow | Reason | Use instead |
|------|------|-----------|--------|-------------|
| `alembic.ini` | config | — | No migration tooling exists yet | RESEARCH Pattern 5 + Pitfall 9 (`path_separator = os`, `prepend_sys_path = src`) |
| `migrations/env.py` | script | migration driver | First Alembic wiring | RESEARCH Pattern 5 (full verified module, four deviations from the stock template) |
| `migrations/script.py.mako` | template | — | First Alembic wiring | RESEARCH Pattern 5 (rewrite the stock `Union[...]` to PEP 604) |
| `migrations/versions/0001_baseline.py` | migration | DDL | First migration | RESEARCH Pattern 2 (verified rendered DDL with the D-12 constraint names) + CONTEXT D-10/D-11/D-12 |
| `docker-compose.yml` | config | orchestration | No compose file exists | RESEARCH Pattern 6 + `ci.yml` L29-48 for the healthcheck |
| `docker/entrypoint.sh` | script | startup sequence | No shell script exists anywhere in the repo | RESEARCH Pattern 7 + Pitfall 2 (`psycopg.connect()` rejects the project's URL) |
| `docker/initdb/01-create-test-database.sql` | script (SQL) | — | No SQL file exists | RESEARCH Pitfall 7 (`\gexec` guard; only runs on an empty volume) |
| `tests/integration/test_migrations.py` | integration test | schema | No migration test exists | RESEARCH §"The `alembic check` drift test" |
| `tests/integration/test_constraints.py` | integration test | schema | No DB test exists | RESEARCH Pitfall 8 (`alembic check` cannot prove CHECKs — insert-and-refuse tests are the only proof) |
| `tests/integration/test_schema.py` | integration test | schema | No DB test exists | RESEARCH Validation Architecture SC-3 rows |
| `src/taskmanager/presentation/api/dependencies.py` | provider | request-scoped | First `Depends` in the project | RESEARCH Pattern 1 note (`app.state` typing) + Pattern 7 |

---

## Open Gap the Planner Must Close

**`/health` needs a version string and there is no `__version__`.** RESEARCH Pattern 8 writes
`version=__version__`, but `src/taskmanager/__init__.py` is empty (0 bytes) and
`src/taskmanager/main.py` L21 hardcodes `version="0.1.0"`, while `pyproject.toml` L7 declares
`version = "0.1.0"` a third time. `tests/unit/test_app_factory.py` L31 asserts
`app.openapi()["info"]["version"] == "0.1.0"`.

Pick one source in this phase and note it in the plan: either add `__version__` to
`src/taskmanager/__init__.py` and have `main.py` and `/health` read it, or read
`importlib.metadata.version("taskmanager")`. Do not add a fourth literal.

---

## Metadata

**Analog search scope:** `src/taskmanager/**` (all 31 modules), `tests/**` (all 26 modules),
repository root config (`Dockerfile`, `Makefile`, `pytest.ini`, `.flake8`, `.importlinter`,
`.env.example`, `.dockerignore`, `pyproject.toml`, `.pre-commit-config.yaml`,
`.github/workflows/ci.yml`).
**Files scanned:** 57 Python modules + 10 configuration files; 24 read in full for excerpts.
**Pattern extraction date:** 2026-09-18
