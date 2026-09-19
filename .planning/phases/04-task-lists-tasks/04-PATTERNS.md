# Phase 4: Task Lists & Tasks - Pattern Map

**Mapped:** 2026-09-18
**Files analyzed:** 61 (38 new source/test modules, 17 modified files, 6 root artifacts)
**Analogs found:** 56 / 61

> **How to read this.** Every excerpt below is copied verbatim from a file that exists in this
> repository today, with its path and line numbers. The planner should reference the analog by
> path+lines in each plan's action section rather than re-deriving conventions. Where no analog
> exists (the `Unset` sentinel, the Pydantic request schemas, the AST gate, the seed step), the
> "No Analog Found" section says so explicitly and points at `04-RESEARCH.md` instead.
>
> **The one-sentence version of this phase:** everything new is a copy of something that already
> exists, except four things. The four are listed at the bottom.

---

## File Classification

### Domain — modified (2)

| File | Role | Data Flow | What changes | Closest Analog | Match |
|------|------|-----------|--------------|----------------|-------|
| `src/taskmanager/domain/entities/task_list.py` | entity | in-memory mutation | `+ describe(description, *, now)` | its own `rename` L89-96 | **exact** |
| `src/taskmanager/domain/entities/task.py` | entity | in-memory mutation | `+ describe`, `+ reprioritise`, `+ DEFAULT_PRIORITY` ClassVar | its own `rename` L133-144 / `reschedule` L146-159; ClassVars L38-41 | **exact** |

### Application — new (14) and modified (4)

| New/Modified File | Role | Data Flow | Closest Analog | Match |
|-------------------|------|-----------|----------------|-------|
| `application/dto/unset.py` | value/sentinel | — | `domain/value_objects/task_status.py` (module-level enum + `Final`) | partial |
| `application/dto/commands.py` **(M)** | DTO | — | its own `ChangeTaskStatusCommand` L32-38 | **exact** |
| `application/dto/results.py` **(M)** | DTO | pure transform | its own `TaskResult` + `from_entity` L25-62 | **exact** |
| `application/ports/repositories.py` **(M)** | port (Protocol) | query | its own `list_for_task_list` L49-55 / `completion_stats` L57 | **exact** |
| `application/use_cases/access.py` | utility (shared guard) | load + authorize | `use_cases/tasks/change_task_status.py` L54-56 (`_may_change_status`) + L72-85 | **exact** |
| `use_cases/task_lists/create.py` | use case | CRUD write | `change_task_status.py` L59-94 | role-match |
| `use_cases/task_lists/get.py` | use case | CRUD read | `change_task_status.py` L59-94 (minus the commit) | role-match |
| `use_cases/task_lists/list.py` | use case | query + aggregate | `change_task_status.py` L59-94; 04-RESEARCH Code Examples §"task-listing use case" | role-match |
| `use_cases/task_lists/update.py` | use case | CRUD write | `change_task_status.py` L69-94 | **exact** |
| `use_cases/task_lists/delete.py` | use case | CRUD write | `change_task_status.py` L69-94 | role-match |
| `use_cases/tasks/create.py` | use case | CRUD write | `change_task_status.py` L59-94 | role-match |
| `use_cases/tasks/get.py` | use case | CRUD read | `change_task_status.py` L69-94 | role-match |
| `use_cases/tasks/list.py` | use case | query + aggregate | `change_task_status.py` + `tasks.py` adapter L178-194 | role-match |
| `use_cases/tasks/update.py` | use case | CRUD write | `change_task_status.py` L69-94 | **exact** |
| `use_cases/tasks/delete.py` | use case | CRUD write | `change_task_status.py` L69-94 | role-match |
| `use_cases/tasks/change_task_status.py` **(M)** | use case | CRUD write | itself (add `task_list_id` comparison) | — |
| `use_cases/task_lists/__init__.py` | package init | — | `use_cases/tasks/__init__.py` | exact |

### Infrastructure — modified (1)

| File | Role | Data Flow | What changes | Closest Analog | Match |
|------|------|-----------|--------------|----------------|-------|
| `infrastructure/db/repositories/task_lists.py` **(M)** | repository adapter | grouped aggregate | `+ lists_with_stats_statement()` module function, `+ list_for_owner_with_stats()` method | `repositories/tasks.py::completion_statement` L54-75 + `completion_stats` L178-194; `task_lists.py::list_for_owner` L118-143 | **exact** |

### Presentation — new (8) and modified (2)

| New/Modified File | Role | Data Flow | Closest Analog | Match |
|-------------------|------|-----------|----------------|-------|
| `presentation/api/actor.py` | provider (DI seam) | request-scoped identity | `presentation/api/health.py` L45-54 (`Final` constant + `Annotated` alias) | role-match |
| `presentation/api/schemas/__init__.py` | package init | — | `presentation/api/errors/__init__.py` | exact |
| `presentation/api/schemas/common.py` | schema | — | `health.py::HealthResponse` L57-68 | partial |
| `presentation/api/schemas/task_lists.py` | schema | request/response | `health.py::HealthResponse` L57-68 (declaration-order argument) | partial |
| `presentation/api/schemas/tasks.py` | schema | request/response | same | partial |
| `presentation/api/routers/__init__.py` | package init | — | `presentation/api/errors/__init__.py` | exact |
| `presentation/api/routers/task_lists.py` | router | request-response | `presentation/api/health.py` L38, L89-108, L111-119 | role-match |
| `presentation/api/routers/tasks.py` | router | request-response | same | role-match |
| `presentation/api/dependencies.py` **(M)** | provider | request-scoped construction | its own `get_uow` L49-76 and `get_engine` L39-41 | **exact** |
| `main.py` **(M)** | composition root | app construction | its own L69-78 (`register_health_routes(app)`) | **exact** |

### Tests — new (20) and modified (5)

| New/Modified File | Role | Data Flow | Closest Analog | Match |
|-------------------|------|-----------|----------------|-------|
| `tests/unit/application/fakes.py` **(M)** | test double | in-memory | its own `FakeTaskRepository.completion_stats` L82-90 + `FakeTaskListRepository.list_for_owner` L117-122 | **exact** |
| `tests/unit/application/test_ports.py` **(M)** | conformance test | — | its own L47-64 | **exact** |
| `tests/unit/application/test_create_task_list.py` (×11, one per use case) | unit test | orchestration | `tests/unit/application/test_change_task_status.py` (whole file) | **exact** |
| `tests/unit/presentation/test_schemas.py` | unit test | pure validation | `tests/unit/domain/test_validation.py` + `tests/unit/presentation/test_health.py` L111-121 | role-match |
| `tests/unit/presentation/test_actor.py` | unit test | — | `tests/unit/infrastructure/test_clock.py` | role-match |
| `tests/integration/conftest.py` **(M)** | fixtures | HTTP + DB | its own L216-277 (`session_factory`, `uow`) + `tests/conftest.py` L28-47 (`app`, `client`) | **exact** (both halves exist, they have never met) |
| `tests/integration/api/__init__.py` | package init | — | `tests/integration/__init__.py` | exact |
| `tests/integration/api/test_task_lists.py` | API integration test | request-response | `tests/api/test_error_contract.py` (assertion style) + `tests/integration/test_repositories_task_lists.py` L48-118 (fixtures/constants style) | **exact** |
| `tests/integration/api/test_tasks.py` | API integration test | request-response | same | **exact** |
| `tests/integration/api/test_statements.py` | API integration test | instrumentation | `tests/integration/test_repositories_tasks.py::test_the_aggregate_is_a_single_statement` (named in `tasks.py` L66) | role-match |
| `tests/architecture/test_routers_raise_no_http_exception.py` | architecture gate | AST scan | `tests/architecture/test_no_commit_in_repositories.py` (whole file — copy its structure exactly) | **exact** |
| `tests/architecture/test_layer_boundaries.py` **(M)** | architecture gate | — | its own L19-23 (`EXPECTED_CONTRACT_NAMES`) | **exact** |
| `tests/integration/test_repositories_task_lists.py` **(M)** | integration test | grouped query | its own L86-118 builders | **exact** |
| `tests/unit/infrastructure/test_adapter_ports.py` **(M?)** | conformance test | — | its own L67-70 — no edit needed unless the port method is added without the adapter method | **exact** |

### Root artifacts — modified (6)

| File | Role | What changes | Analog | Match |
|------|------|--------------|--------|-------|
| `.importlinter` | config | + one `forbidden` contract | its own L29-50 (`domain-framework-free`) | **exact** |
| `docker/entrypoint.sh` | shell entrypoint | + step 2b, a seed heredoc after L91 | its own L44-84 (step 1 heredoc) | **exact** |
| `DECISION_LOG.md` | docs | + 4 ADRs (actor seam, PATCH sentinel, `updated_at`, status endpoint) | existing ADR entries | exact |
| `AI_WORKFLOW.md` | docs | + phase incidents | existing entries | exact |
| `evidence/` | artifacts | + 2 red captures for D-15 | `evidence/import-linter-red-green.txt` (named in `test_layer_boundaries.py` L13) | exact |
| `README.md` | docs | API section, v2-pending note | existing | exact |

---

## Pattern Assignments

### 1. `application/use_cases/**/*.py` (use case, CRUD / query)

**Analog:** `src/taskmanager/application/use_cases/tasks/change_task_status.py` — the file's own
docstring calls itself "the template Phases 4 and 5 copy". Copy its four structural moves and its
docstring register (state what was rejected and why, not what the code does).

**Imports pattern** (L43-51) — note the order: dto → ports → domain, all absolute, no relative:

```python
from uuid import UUID

from taskmanager.application.dto.commands import ChangeTaskStatusCommand
from taskmanager.application.dto.results import TaskResult
from taskmanager.application.ports.clock import Clock
from taskmanager.application.ports.unit_of_work import UnitOfWork
from taskmanager.domain.entities.task import Task
from taskmanager.domain.entities.task_list import TaskList
from taskmanager.domain.exceptions import TaskNotFoundError
```

**Constructor pattern** (L59-67) — unit of work first, other ports as separate arguments:

```python
class ChangeTaskStatus:
    """Moves one task to a requested status on behalf of an authenticated actor."""

    def __init__(self, uow: UnitOfWork, clock: Clock) -> None:
        # The unit of work first, then the non-transactional ports as separate
        # arguments (D-17). Nothing else is injected, because nothing else is
        # touched - which is the whole point of one class per use case.
        self._uow = uow
        self._clock = clock
```

**Core pattern — load → authorize → domain → persist → commit → map** (L69-94):

```python
    async def execute(self, command: ChangeTaskStatusCommand) -> TaskResult:
        """Run the operation, or raise the domain error that describes its refusal."""
        async with self._uow:
            task = await self._uow.tasks.get(command.task_id)
            if task is None:
                raise TaskNotFoundError(command.task_id)
            task_list = await self._uow.task_lists.get(task.task_list_id)
            if task_list is None or not _may_change_status(
                task, task_list, command.actor_id
            ):
                raise TaskNotFoundError(command.task_id)
            task.change_status(command.new_status, now=self._clock.now())
            await self._uow.tasks.update(task)
            await self._uow.commit()
        # Mapped outside the block: the result describes a transaction that has
        # already been made durable, never one still in flight.
        return TaskResult.from_entity(task)
```

Four rules to carry into all ten new use cases:
1. `async with self._uow:` wraps everything; `commit()` is the **last** statement inside, on the
   success path only. **Read-only use cases (`Get*`, `List*`) do not commit** — `__aexit__` rolls
   the read transaction back, which is its documented obligation.
2. The clock is read **once** (`now = self._clock.now()`) and handed down as `now=` (D-13). See
   04-RESEARCH Code Examples §"The canonical Phase 4 use case" for the multi-mutator variant.
3. The result is constructed **outside** the `async with` block.
4. `ChangeTaskStatus` has **no** `AuthorizationError` branch (L25-40 of the docstring explains at
   length). D-04 keeps that true for Phase 4: every refusal is a `*NotFoundError`.

**Shared-guard pattern** (L54-56) — the precedent for `access.py`:

```python
def _may_change_status(task: Task, task_list: TaskList, actor_id: UUID) -> bool:
    """Whether this actor may see, and therefore move, this task (ASGN-02)."""
    return task_list.owner_id == actor_id or task.assignee_id == actor_id
```

`access.py` promotes this to a module. Bodies are in 04-RESEARCH Code Examples §"The shared
load-and-authorize helper". Carry the L76-81 comment verbatim in spirit: a task under a foreign or
absent list raises `TaskNotFoundError`, never `TaskListNotFoundError`.

---

### 2. `application/dto/commands.py` (DTO, modified)

**Analog:** the file itself, L32-38.

```python
@dataclass(frozen=True, slots=True)
class ChangeTaskStatusCommand:
    """Ask for a task to move to `new_status`, on behalf of `actor_id`."""

    actor_id: UUID
    task_id: UUID
    new_status: TaskStatus
```

Module docstring L1-24 states the convention the ten new commands inherit: `frozen=True,
slots=True`, **first field `actor_id: UUID`**, never Pydantic. `ChangeTaskStatusCommand` gains
`task_list_id: UUID` as the **second** field (04-RESEARCH Pitfall 1) — blast radius: this file,
`change_task_status.py` L72-85, and `tests/unit/application/test_change_task_status.py` L104-111
(one `_command` helper — the seven call sites all go through it).

The PATCH commands add `X | Unset = UNSET` defaults; shape in 04-RESEARCH Pattern 1.

---

### 3. `application/dto/results.py` (DTO, modified)

**Analog:** `TaskResult` + `from_entity`, L25-62. Copy the explicit field-by-field mapping and the
docstring's reason for it:

```python
@dataclass(frozen=True, slots=True)
class TaskResult:
    """One task, flattened out of the aggregate at a single moment in time."""

    id: UUID
    task_list_id: UUID
    ...

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
            ...
        )
```

`TaskListResult.from_entity(task_list, stats)` takes the second argument because D-10 puts the
counters on every list response. The counters come from
`CompletionStats` (`domain/value_objects/completion.py` L25-33) — `percentage` is a **property**,
already rounded to 2 decimals, so D-09 needs no domain change and `stats.percentage()` would be a
`TypeError`.

---

### 4. `application/ports/repositories.py` (port, modified)

**Analog:** `TaskRepository.list_for_task_list` L49-55 — the keyword-only, domain-typed,
comment-above-the-method shape:

```python
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
```

The new method goes on `TaskListRepository` (L60-72), beside `list_for_owner`:

```python
    async def list_for_owner_with_stats(
        self, owner_id: UUID
    ) -> Sequence[tuple[TaskList, CompletionStats]]: ...
```

`CompletionStats` is already imported at L30. Domain types only — never a `Row` (CLAUDE.md
repositories rule).

**Adding it breaks three things at once, all deliberately:** `FakeTaskListRepository` stops
satisfying the port under `mypy --strict`, `tests/unit/application/test_ports.py::
test_fake_task_list_repository_satisfies_the_task_list_repository_port` fails, and
`tests/unit/infrastructure/test_adapter_ports.py::test_the_sqlalchemy_task_list_repository_
satisfies_its_port` fails. Plan the port, the fake and the adapter in one task.

---

### 5. `infrastructure/db/repositories/task_lists.py` (repository adapter, modified)

**Analog A — the module-level statement function:** `repositories/tasks.py` L54-75:

```python
def completion_statement(task_list_id: UUID) -> Select[tuple[int, int]]:
    """The one statement behind the completion percentage (ADR-009).
    ...
    It is a module-level function rather than a few lines inside the method so
    the SQL it produces can be compiled and asserted on with no server at all:
    `test_the_aggregate_is_a_single_statement` fails if a later refactor turns
    this back into two queries. The filter value is `TaskStatus.COMPLETED.value`
    and travels as a bound parameter, like every other value in this package.
    """
    return select(
        func.count().label("total"),
        func.count()
        .filter(TaskRow.status == TaskStatus.COMPLETED.value)
        .label("completed"),
    ).where(TaskRow.task_list_id == task_list_id)
```

`lists_with_stats_statement(owner_id)` is the same idea one join wider — full verified body,
compiled SQL and the `count(tasks.id)`-not-`count(*)` trap in 04-RESEARCH Pattern 3.
**Note the import cost:** `task_lists.py` does not currently import `TaskRow` or `TaskStatus`; both
come from modules it already neighbours (`.models`, `domain.value_objects.task_status`).

**Analog B — the method that runs it:** `tasks.py` L178-194:

```python
    async def completion_stats(self, task_list_id: UUID) -> CompletionStats:
        """The list's two counters, from the one statement above (ADR-009).
        ...
        """
        row = await self._session.execute(completion_statement(task_list_id))
        total, completed = row.one()
        return CompletionStats(total=total, completed=completed)
```

**Analog C — the ordering and the "filter in SQL, not in Python" argument:** `task_lists.py`
L118-143 (`list_for_owner`). Its `.order_by(TaskListRow.created_at, TaskListRow.id)` is D-13's
total order and its docstring L128-135 is the reason `id` is the tie-break. The new grouped
statement carries the same `order_by`.

**Constraint:** no `.commit()` anywhere in this package —
`tests/architecture/test_no_commit_in_repositories.py` L86-99 greps the text. The new method is a
read; it must not flush either.

---

### 6. `presentation/api/routers/*.py` (router, request-response)

**Analog:** `src/taskmanager/presentation/api/health.py` — the only router in the repository.

**Router construction + the `Annotated` alias** (L38, L47-54). The comment is the ADR-034 / B008
argument and should be referenced, not re-litigated, in the new modules:

```python
health_router = APIRouter(tags=["health"])

# The injection is expressed as an annotation rather than as a default value,
# and that is not a style preference. flake8-bugbear's B008 rejects a call in an
# argument default, and `.flake8` whitelists the dotted spelling
# `fastapi.Depends` - which this module does not use, because every other import
# in the project is by name. The annotated form has no default to object to, it
# is the shape FastAPI's own documentation now leads with, and it gives the
# dependency a name Phase 4's routers can reuse instead of repeating the call.
EngineDependency = Annotated[AsyncEngine, Depends(get_engine)]
```

**Route pattern** (L89-108) — explicit `response_model`, declared `responses`, injected `Response`
for header/status manipulation, a docstring that says why the non-200 leg exists:

```python
@health_router.get(
    "/health",
    response_model=HealthResponse,
    responses={503: {"model": HealthResponse}},
)
async def health(response: Response, engine: EngineDependency) -> HealthResponse:
    """Liveness is answering at all; readiness is the database answering too.
    ...
    """
```

**Registration pattern** (L111-119) — imperative, called from the composition root:

```python
def register_health_routes(app: FastAPI) -> None:
    """Install the health router, from create_app().

    Imperative and called from the composition root, mirroring
    `register_exception_handlers`: the router is attached to the application the
    factory built, never to a module-level instance, so importing this module
    creates nothing.
    """
    app.include_router(health_router)
```

The new routers follow this: `register_api_routes(app)` (or one function per router) called from
`create_app`, with `prefix="/api/v1"` on the `include_router` call and `prefix="/task-lists"` on
the `APIRouter` — the combination `request.url_for` needs for D-12's `Location` (verified,
04-RESEARCH Pattern 4).

**201/`Location` and 204 idioms:** 04-RESEARCH Pattern 4, both measured on the pinned stack.
`response_class=Response` on the 204 is the difference between an empty body with and without a
`content-type: application/json` header.

**Hard rule for these two files:** no `HTTPException`, raised or imported. D-15's AST gate scans
this exact package.

---

### 7. `presentation/api/dependencies.py` (provider, modified)

**Analog:** the file itself. `get_uow` L49-76 is the shape; the new `get_clock` is simpler than
`get_engine` L39-41 because `SystemClock` needs no `app.state`:

```python
def get_engine(request: Request) -> AsyncEngine:
    """The application's engine, for callers that need the pool itself."""
    return _resources(request).engine
```

Two rules from `get_uow`'s docstring that the new providers must not break: a plain `def`, never a
`yield` dependency (the teardown runs after the response is sent); and the **port** as the return
annotation, never the concrete class, so a test overrides the provider instead of a signature.
The module docstring L16-17 explicitly anticipates this phase: "Phase 4 will add providers here,
and none of them will have to repeat it."

`UnitOfWorkDependency = Annotated[UnitOfWork, Depends(get_uow)]` and
`ClockDependency = Annotated[Clock, Depends(get_clock)]` follow `EngineDependency`
(`health.py` L54). Where the aliases live is discretionary; `health.py` sets the precedent of
declaring the alias next to the router that uses it, while `dependencies.py` is the natural home
for ones two routers share.

---

### 8. `presentation/api/actor.py` (provider, D-01 seam)

**Analog:** `health.py` L45 for the `Final` module constant with the reasoning comment, and L54 for
the `Annotated` alias. Combined shape (full body in 04-RESEARCH Pattern 5):

```python
DATABASE_PROBE_TIMEOUT_SECONDS: Final[float] = 2.0
...
EngineDependency = Annotated[AsyncEngine, Depends(get_engine)]
```

Separate module rather than an addition to `dependencies.py`, for two reasons 04-RESEARCH gives:
the entrypoint seed imports `DEMO_USER_ID` and must not drag `sqlalchemy` in to do it, and Phase 5
deletes one file rather than editing one. The docstring must say, in those words, that this is
**not authentication** (CONTEXT `<specifics>`).

---

### 9. `presentation/api/schemas/*.py` (Pydantic boundary)

**Nearest analog:** `health.py::HealthResponse` L57-68 — the only Pydantic model in `src/` today.
It carries one transferable argument (field order is contract, not decoration) and nothing else:

```python
class HealthResponse(BaseModel):
    """The D-08 document: three members, always these three, in this order.

    Member order is not decoration. Pydantic serialises fields in declaration
    order, so declaring them here in the order D-08 writes them is what makes
    the contract mechanically true rather than aspirational - the same argument
    `errors/problem.py` makes for building its body as a literal.
    """

    status: Literal["ok", "degraded"]
    checks: dict[str, str]
    version: str
```

Everything else — `extra="forbid"`, `model_fields_set`, `field_validator` for the explicit-null
leg, `model_validator` for the empty body, `to_command()` — has **no analog in this repository**
and comes from 04-RESEARCH Pattern 2, where every row of the behaviour table was executed on the
pinned stack.

**Two constraints from the existing code, not from research:**
- Do not repeat a business limit. `Task.TITLE_MAX_LENGTH` (task.py L39) and
  `TaskList.NAME_MAX_LENGTH` (task_list.py L39) are the only copies; no `Field(max_length=...)`.
- `TaskResponse.from_result(...)` names every field explicitly, mirroring
  `TaskResult.from_entity` (results.py L41-62) and for the identical reason. `model_validate`
  works but re-opens the automatic-leak hole that class exists to close.

---

### 10. `tests/unit/application/test_*.py` (use-case unit tests)

**Analog:** `tests/unit/application/test_change_task_status.py` — copy the whole file's structure.

**Fixed constants, never generated** (L41-52):

```python
# Fixed on purpose. A generated identifier or a real clock reading would make
# every assertion below unfalsifiable: the test could no longer state which
# moment, or which actor, it expects.
NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
LATER = NOW + timedelta(hours=3)
ACTOR_ID = UUID("11111111-1111-4111-8111-111111111111")
OTHER_USER_ID = UUID("99999999-9999-4999-8999-999999999999")
TASK_ID = UUID("22222222-2222-4222-8222-222222222222")
TASK_LIST_ID = UUID("33333333-3333-4333-8333-333333333333")
```

**Three private builders** — `_task()`, `_uow()`, `_command()` (L55-111). Note L83-88: entities go
into `stored` **directly**, not through `add()`, so `added`/`updated` stay empty and every entry a
test finds was written by the use case.

**Every success test asserts the transaction, not only the value** (L170-182):

```python
    assert result.status is TaskStatus.IN_PROGRESS
    assert result.updated_at == LATER
    assert len(unit_of_work.task_repository.updated) == 1
    assert unit_of_work.commits == 1
    assert unit_of_work.rollbacks == 0
```

**Every failure test asserts the mirror image, and catches the base class** (L237-257) — this is
the D-04 two-actor test the planner needs per verb:

```python
async def test_change_task_status_hides_a_task_the_actor_cannot_see() -> None:
    """ADR-008: an invisible task is a 404 for every verb, never a 403.

    The broad `DomainError` is caught on purpose. A 403 would satisfy a
    `pytest.raises(AuthorizationError)` written the other way round just as
    happily; catching the base and then asserting *which* leaf came out is what
    makes the information-disclosure claim falsifiable (threat T-02-25).
    """
    unit_of_work = _uow(owner_id=OTHER_USER_ID)
    use_case = ChangeTaskStatus(unit_of_work, FrozenClock(LATER))

    with pytest.raises(DomainError) as excinfo:
        await use_case.execute(_command(TaskStatus.IN_PROGRESS))

    error = excinfo.value
    assert isinstance(error, TaskNotFoundError)
    assert not isinstance(error, AuthorizationError)
    assert error.details == {"task_id": str(TASK_ID)}
    assert unit_of_work.task_repository.updated == []
    assert unit_of_work.commits == 0
    assert unit_of_work.rollbacks == 1
```

Read-only use cases invert the commit assertion: `commits == 0`, `rollbacks == 1` on the **success**
path, which is what makes "a read never commits" an assertion rather than a claim.

The DTO immutability tests (L114-148) are per-DTO boilerplate: one `FrozenInstanceError` test and
one `slots` test per new command, using the `DECLARED_COMMAND_FIELD` / `UNDECLARED_FIELD` string
constants (L48-52) so mypy does not reject the very assignment the test observes failing.

---

### 11. `tests/unit/application/fakes.py` (modified)

**Analog for `list_for_owner_with_stats`:** the two methods it composes, already in the file.
`FakeTaskRepository.completion_stats` L82-90:

```python
    async def completion_stats(self, task_list_id: UUID) -> CompletionStats:
        # Counted from what is stored, not canned: the aggregate Phase 3 will
        # write in SQL has to agree with this, so the fake must be able to
        # disagree with a wrong use case.
        tasks = [
            task for task in self.stored.values() if task.task_list_id == task_list_id
        ]
        completed = [task for task in tasks if task.status is TaskStatus.COMPLETED]
        return CompletionStats(total=len(tasks), completed=len(completed))
```

and `FakeTaskListRepository.list_for_owner` L117-122:

```python
    async def list_for_owner(self, owner_id: UUID) -> Sequence[TaskList]:
        return [
            task_list
            for task_list in self.stored.values()
            if task_list.owner_id == owner_id
        ]
```

Two things the planner must schedule here:
1. `list_for_owner` has **no ordering** while the adapter sorts by `(created_at, id)`. 04-RESEARCH
   flags this: a D-13 assertion would pass in unit tests and fail over HTTP. Add
   `sorted(..., key=lambda tl: (tl.created_at, tl.id))` to both list methods.
2. The fake `TaskList` repository has no access to tasks, so `list_for_owner_with_stats` needs the
   task repository. `FakeUnitOfWork.__init__` L184-197 already constructs both and can hand one to
   the other — or the test's `_uow()` builder wires them. Either is fine; pick one and state it.

---

### 12. `tests/integration/conftest.py` (modified — the missing bridge)

**Both halves exist and have never met.** `tests/integration/conftest.py` L216-241 gives a
connection-bound `session_factory`:

```python
@pytest.fixture
def session_factory(connection: AsyncConnection) -> Callable[[], AsyncSession]:
    """Sessions bound to the test connection, joining it by SAVEPOINT.
    ...
    """

    def factory() -> AsyncSession:
        return AsyncSession(
            bind=connection,
            expire_on_commit=False,
            autoflush=False,
            join_transaction_mode="create_savepoint",
        )

    return factory
```

and `tests/conftest.py` L28-47 gives the app and the httpx client:

```python
@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    """The production app plus the probe router, which only tests ever see."""
    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
    monkeypatch.setenv("JWT_SECRET", JWT_SECRET)

    application = create_app(Settings(_env_file=None))
    application.include_router(probe_router)  # tests only - never production

    return application


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """The default client: an exception escaping the app fails the test."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client
```

The `api_client` fixture is those two joined by `app.dependency_overrides[get_uow]` — verified end
to end in 04-RESEARCH Pattern 7, including the savepoint rule (a fixture that seeds a user **must**
`commit()`, or the row vanishes when the session closes). The `statements` counter fixture is
04-RESEARCH Pattern 8.

`tests/integration/test_health.py` L67-76 is the precedent for an integration fixture that builds
its own app rather than reusing the fictional-DSN one, and L59-64 for entering
`app.router.lifespan_context(app)` when the engine's lifecycle matters. The `api_client` fixture
does **not** need the lifespan: `get_uow` is overridden, so the app's own engine is never dialled.

Also copy L32 (`pytestmark = pytest.mark.integration`) into every new module under
`tests/integration/api/`.

---

### 13. `tests/integration/api/test_*.py` (API integration tests)

**Analog A — assertion style:** `tests/api/test_error_contract.py`. The problem+json member list is
already a module constant (L18-20) and every error assertion in the phase should reuse the shape:

```python
PROBLEM_JSON = "application/problem+json"
# The full D-06 member list, in the order the contract promises.
MEMBERS = ["type", "title", "status", "detail", "instance", "code"]
```

The 409 body assertion (L29-41) is exactly D-16's invalid-transition case:

```python
    assert response.status_code == 409
    assert response.headers["content-type"] == PROBLEM_JSON
    body = response.json()
    assert list(body) == [*MEMBERS, "errors"]
    assert body["code"] == "invalid_status_transition"
    assert body["errors"] == {"from": "completed", "to": "pending"}
```

The 422 **list** shape (L118-134) — the one a filter value, an empty PATCH and `status`-in-PATCH
produce:

```python
    assert body["code"] == "validation_error"
    assert body["title"] == "Request validation failed"
    assert all(set(entry) == {"field", "message", "type"} for entry in body["errors"])
    fields = {entry["field"] for entry in body["errors"]}
    assert fields == {"query.q", "body.title", "body.count"}
```

The 422 **object** shape (a blank title, a past due date) comes from the domain `ValidationError`
and is `body["errors"] == {"field": "due_date"}`. 04-RESEARCH Pitfall 5 tabulates which producer
each D-16 case hits; name it in the test name.

**Analog B — fixtures and constants:** `tests/integration/test_repositories_task_lists.py` L50-118.
Fixed UUIDs in a readable series, fixed instants, and a `given_an_owner` helper because
`task_lists.owner_id` is a foreign key:

```python
OWNER_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")
OTHER_OWNER_ID = uuid.UUID("00000000-0000-4000-8000-000000000002")
LIST_ID = uuid.UUID("00000000-0000-4000-8000-000000000011")
...
async def given_an_owner(
    session: AsyncSession,
    *,
    user_id: uuid.UUID = OWNER_ID,
    email: str = OWNER_EMAIL,
) -> None:
    """One user row, because `task_lists.owner_id` is a foreign key.
    ...
    """
```

04-RESEARCH Pitfall 4: flush the user **before** adding lists — `TaskListRow` has a `ForeignKey`
but no `relationship`, so SQLAlchemy has no dependency edge to sort the INSERTs by.

The not-owned 404 legs need a **second actor over HTTP**, which means
`app.dependency_overrides[get_current_actor] = lambda: other_user_id`. That is the only way to
reach them, so the `api_client` fixture must yield the `FastAPI` object too, not just the client.

---

### 14. `tests/architecture/test_routers_raise_no_http_exception.py` (AST gate)

**Analog:** `tests/architecture/test_no_commit_in_repositories.py` — copy its structure line for
line. Constants (L40-63):

```python
# tests/architecture/test_no_commit_in_repositories.py -> tests/architecture ->
# tests -> repository root.
REPOSITORIES: Final[Path] = (
    Path(__file__).resolve().parents[2]
    / "src" / "taskmanager" / "infrastructure" / "db" / "repositories"
)

FORBIDDEN_CALL: Final[str] = ".commit()"

# All three adapters, named rather than counted. Requiring them by name is what
# makes the scan non-vacuous - a renamed or emptied package, or a newest adapter
# that quietly stopped being scanned, fails the guard below instead of leaving
# the real test asserting that nothing is nothing.
REQUIRED_SCANNED_MODULES: Final[frozenset[str]] = frozenset(
    {"task_lists.py", "tasks.py", "users.py"}
)
```

Non-vacuity guard + the real test (L71-99):

```python
def test_the_repositories_package_is_actually_scanned() -> None:
    """A glob that matches nothing passes vacuously; assert it matched the tree."""
    scanned = {
        path.relative_to(REPOSITORIES).as_posix() for path in _repository_modules()
    }

    assert scanned
    assert REQUIRED_SCANNED_MODULES <= scanned


def test_no_repository_commits_its_own_transaction() -> None:
    """No line under the repositories package ends a transaction."""
    offenders = [
        f"{path.relative_to(REPOSITORIES).as_posix()}:{number}"
        for path in _repository_modules()
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if FORBIDDEN_CALL in line
    ]

    assert offenders == [], (
        "A repository must never end its own transaction: ..."
        f"{FORBIDDEN_CALL} at: {offenders}"
    )
```

The new gate keeps `REQUIRED_SCANNED_MODULES = frozenset({"task_lists.py", "tasks.py"})` over
`presentation/api/routers/`, the non-vacuity test, and offenders reported as `file:line`. It
substitutes an `ast` walk for the text scan (prototype and its one known gap in 04-RESEARCH
Pattern 9); note that `test_no_commit_in_repositories.py` L24-31 explicitly blesses the AST upgrade
while forbidding a weakening into a runtime check. Pair the raise-check with the strictly stronger
import-check, per 04-RESEARCH.

The L33-37 paragraph is the reason this gate adds **no** pre-commit hook and **no** CI step; copy
that argument into the new module's docstring.

---

### 15. `tests/architecture/test_layer_boundaries.py` (modified) and `.importlinter`

**`.importlinter` analog:** the `domain-framework-free` contract, L29-50 — a comment block stating
what is deliberately in or out of the list, then the contract:

```ini
[importlinter:contract:domain-framework-free]
name = Domain is framework-free
type = forbidden
source_modules =
    taskmanager.domain
forbidden_modules =
    fastapi
    starlette
    ...
```

The new contract's exact text (executed and reported KEPT) is in 04-RESEARCH Pattern 9.
`include_external_packages = True` is already set at L14 and is required for it.

**`test_layer_boundaries.py` analog:** its own L19-23. The set is asserted exactly, so adding a
contract without adding its name here fails the suite — expected, in the same change:

```python
EXPECTED_CONTRACT_NAMES = {
    "Layered architecture (high to low)",
    "Domain is framework-free",
    "Application knows no web framework or ORM",
}
```

---

### 16. `docker/entrypoint.sh` (modified)

**Analog:** step 1 of the same file, L44-84 — a `python - <<'PY' ... PY` heredoc that builds a
sync SQLAlchemy engine from `os.environ["DATABASE_URL"]` and disposes it:

```sh
python - <<'PY'
import os
import sys
import time

from sqlalchemy import create_engine, text
...
engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
...
engine.dispose()
PY
```

The seed goes **after** L91 (`alembic upgrade head`) and **before** L103 (`exec uvicorn`), as its
own `# --- 2b.` block matching the existing comment banners. Full body, the `ON CONFLICT DO
NOTHING`-without-a-target finding (3 executions, rowcounts 1/0/0) and the `users` column list are
in 04-RESEARCH Pattern 6.

The L13-23 paragraph is the standing argument for why this is a heredoc and not a module under
`src/taskmanager/` (coverage would owe it a test; ADR-037). Reference it rather than restating it.

`set -eu` at L26 means a failing seed aborts the container — which is correct, and why the
untargeted `ON CONFLICT` matters.

---

### 17. Domain entity additions

**Analog:** `Task.rename` L133-144 and `Task.reschedule` L146-159:

```python
    def rename(self, title: str, *, now: datetime) -> None:
        """Replace the title, applying the same guard construction applied."""
        # Every guard runs before the first assignment, as in `reschedule` and
        # `change_status`. Assigning the title first and validating `now`
        # afterwards left a refused call with the new title and the old
        # `updated_at`: a half-applied mutation the unit of work cannot undo,
        # because the corrupted copy is the in-memory aggregate, not the row.
        moment = require_utc(now, field="now")
        self.title = require_text(
            title, field="title", max_length=self.TITLE_MAX_LENGTH
        )
        self.updated_at = moment
```

Three rules, all visible above: `now` is keyword-only; **validate everything before assigning
anything**; `updated_at` is stamped from the validated moment, not from `now` directly.

`describe` delegates to `optional_text` (already imported in both entities), which turns `""` into
`None` — see `__post_init__` task.py L63-67 / task_list.py L56-60 for the call shape.

`DEFAULT_PRIORITY` follows the ClassVar block at task.py L38-41:

```python
    # TASK-08 / FEATURES section 8 rule 3: a title is 1-200 characters trimmed.
    TITLE_MAX_LENGTH: ClassVar[int] = 200
```

and `Task.create`'s signature L97 (`priority: TaskPriority = TaskPriority.MEDIUM`) changes to read
it, so the schema default and the entity default are one copy (04-RESEARCH Pitfall 6).

Both entity docstrings already announce this change — task.py L33-36 and task_list.py L34-36 say
"Phase 4 adds the ones its PATCH endpoints require". Update that sentence when the mutators land.

---

## Shared Patterns

### Error handling — never build a body, never raise HTTPException

**Source:** `src/taskmanager/presentation/api/errors/mapping.py` L49-58
**Apply to:** every new use case, router and integration test

```python
STATUS_BY_EXCEPTION: Final[dict[type[DomainError], int]] = {
    DomainError: 500,
    ValidationError: 422,
    BusinessRuleViolationError: 422,
    InvalidStatusTransitionError: 409,
    NotFoundError: 404,
    ConflictError: 409,
    AuthenticationError: 401,
    AuthorizationError: 403,
}
```

L38-43 of that file is the load-bearing part for Phase 4: `TaskNotFoundError`,
`TaskListNotFoundError` and `DuplicateTaskListNameError` are **deliberately absent** and resolve
through their parents by the MRO walk. **This file needs no edit in Phase 4.** A plan that proposes
one has misread it.

`register_exception_handlers(app)` is already called from `main.py` L76, so every new router is
covered the moment it is included.

### Authorization — one shape, no 403 in this phase

**Source:** `application/use_cases/tasks/change_task_status.py` L76-85 + its docstring L25-40
**Apply to:** all ten new use cases, via `access.py`

A resource the actor cannot see answers exactly as an absent one, with the **same error class** and
the **same details**, on every verb. Task routes raise `TaskNotFoundError` even when the parent
list is missing or foreign, because `task_list_not_found` differs in code **and** carries a foreign
identifier.

### Transaction boundary

**Source:** `presentation/api/dependencies.py` L49-76, `infrastructure/db/repositories/task_lists.py`
L1-29, `tests/architecture/test_no_commit_in_repositories.py`
**Apply to:** every use case (owns `commit()`), every router (never commits), every adapter (never
commits, flushes instead)

The provider hands over a **closed** unit of work; `SqlAlchemyUnitOfWork.__aenter__` refuses a
second entry (`tests/unit/infrastructure/test_adapter_ports.py` L108-130), so a router that entered
the block would fail loudly rather than quietly.

### Docstring register

**Source:** every module in `src/taskmanager/`
**Apply to:** every new module

The project's convention is a module docstring that names the **rejected alternatives** and why,
not one that paraphrases the code. `change_task_status.py` L1-41, `dependencies.py` L1-18 and
`tests/integration/conftest.py` L1-36 ("Four shapes a reader may expect here are deliberately
absent") are the three clearest specimens. Forbidden forms are described in **prose, never spelled
literally**, so text-scanning gates stay real gates — stated at
`test_no_commit_in_repositories.py` L27-31 and honoured by `Makefile`, `migrations/env.py`,
`errors.py` and `tests/integration/conftest.py` L20-23.

### Fixed identifiers and instants in tests

**Source:** `tests/unit/application/test_change_task_status.py` L38-46,
`tests/integration/test_repositories_task_lists.py` L50-64
**Apply to:** every new test module

No `uuid4()`, no `datetime.now()`. A generated value makes an assertion unfalsifiable.

### The 100%-coverage norm

**Source:** CLAUDE.md; `pytest.ini` gates at 75%
**Apply to:** every new module under `src/taskmanager/`

No `# pragma: no cover`, no coverage `omit`. This is the operative reason the demo seed is a shell
heredoc and the fakes live under `tests/` (`fakes.py` L3-8). `mapping.py::status_for` L61-70 shows
how the project reshapes code to avoid an unreachable branch rather than suppressing it.

---

## No Analog Found

Five things in this phase have no close match in the codebase. The planner should take these from
`04-RESEARCH.md`, where each was executed against the pinned stack rather than recalled.

| File / artifact | Role | Data Flow | Reason | Take it from |
|-----------------|------|-----------|--------|--------------|
| `application/dto/unset.py` | sentinel | — | No sentinel of any kind exists; `None` is used as a real value throughout | 04-RESEARCH Pattern 1 (mypy narrowing verified) |
| `presentation/api/schemas/{task_lists,tasks}.py` — the PATCH half | schema | request validation | `HealthResponse` is the only Pydantic model and it is a plain response with no validators, no `extra="forbid"`, no `model_fields_set` | 04-RESEARCH Pattern 2 (behaviour table executed) |
| The 201/`Location` and 204 route decorators | router | request-response | `/health` is the only route and it is a 200/503 GET | 04-RESEARCH Pattern 4 (both measured, incl. the `content-type` on a bare 204) |
| `tests/integration/api/test_statements.py` | test instrumentation | event listener | No test in the repository attaches a SQLAlchemy event listener | 04-RESEARCH Pattern 8 (`['SAVEPOINT','SELECT','ROLLBACK']` — the filter is not optional) |
| The demo-user seed SQL | shell | one-shot write | The entrypoint's existing heredoc is a *read* probe; nothing in the project writes a row from the shell | 04-RESEARCH Pattern 6 (3 executions, rowcounts 1/0/0) |

Partial-analog warning: `tests/integration/api/*` has a strong analog for *assertions*
(`tests/api/test_error_contract.py`) and a strong analog for *database fixtures*
(`tests/integration/test_repositories_task_lists.py`), but **no analog for the two joined** — the
`api_client` fixture is genuinely new. It is the single highest-risk Wave 0 item and 04-RESEARCH
Pattern 7 is the only place its verified shape exists.

---

## Cross-Cutting Notes for the Planner

1. **The port change is a three-file atomic edit.** `list_for_owner_with_stats` added to
   `ports/repositories.py` breaks `fakes.py`, `test_ports.py` and `test_adapter_ports.py`
   simultaneously under `mypy --strict`. One task.
2. **The `ChangeTaskStatusCommand` change is a three-file atomic edit.** `commands.py`,
   `change_task_status.py`, `test_change_task_status.py` (the `_command` helper at L104-111 is the
   single call site). One task.
3. **The `.importlinter` contract is a two-file atomic edit.** `.importlinter` plus
   `EXPECTED_CONTRACT_NAMES` in `test_layer_boundaries.py` L19-23. One task.
4. **Nothing in `presentation/api/errors/` changes.** The MRO table already covers every error this
   phase raises.
5. **`main.py` L76-77 is the only line that changes in the composition root** — one more
   `register_*_routes(app)` call, following `register_health_routes`.

---

## Metadata

**Analog search scope:** `src/taskmanager/**` (all 30 modules), `tests/**` (all 33 modules and both
conftests), `docker/entrypoint.sh`, `.importlinter`
**Files read in full:** 24
**Files sampled by grep:** 6 (`models.py`, `mappers.py`, `validation.py`, `ports/clock.py`,
`ports/unit_of_work.py`, `infrastructure/clock.py`)
**Pattern extraction date:** 2026-09-18
**Previous phase map for format:** `.planning/phases/03-persistence-runnable-stack/03-PATTERNS.md`
