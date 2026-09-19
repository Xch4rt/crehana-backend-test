# Phase 4: Task Lists & Tasks - Research

**Researched:** 2026-09-18
**Domain:** FastAPI 0.141 / Pydantic 2.13 HTTP boundary over an existing layered async SQLAlchemy 2.0 codebase
**Confidence:** HIGH (almost every claim below was executed against this repository's pinned
`.venv` and its live `taskmanager_test` database, not recalled)

## Summary

This phase writes the *outermost* two layers of a codebase whose inner three are finished and
proven. Phase 2 shipped the entities, the error hierarchy, the ports and one reference use case;
Phase 3 shipped the adapters, the unit of work, the migration, the compose stack and the
integration harness. Nothing about persistence, error translation or the transaction boundary is
an open question. What is missing is: eleven use cases and their DTOs, one new port method,
Pydantic request/response schemas, two routers, an actor seam, a demo-user seed in the
entrypoint, and two new architecture gates.

The three genuinely open technical questions in the phase brief all resolved cleanly against the
pinned stack, and each was verified by execution rather than reasoned about:

1. **PATCH "omitted vs explicit null"** — a single-member `enum.Enum` sentinel on the *application
   command* narrows perfectly under `mypy 2.3.1 --strict` (`str | Unset` → `str` after
   `is not UNSET`, and forgetting the guard is an `arg-type` error). The same sentinel must **not**
   appear in the Pydantic schema: it leaks a `_Unset` enum into `/openapi.json` and produces a
   two-branch union error whose `loc` is `["body","title","str"]`. The schema uses
   `X | None = None` + `model_fields_set`, and a `@field_validator` supplies the clean
   field-level 422 for an explicit null on a non-nullable field.
2. **The grouped list-statistics query (D-10)** — a `LEFT OUTER JOIN` with
   `count(tasks.id) FILTER (WHERE …)` grouped by `task_lists.id`. Executed against PostgreSQL 18.4:
   one statement for 2 lists and one statement for 5 lists, an empty list reports `total=0` →
   `0.0`, and both counters arrive as Python `int`. The trap is `count(*)` instead of
   `count(tasks.id)`: on the null-extended outer-join row it reports `total=1` for an empty list.
3. **The D-17 statement counter** — `event.listen(engine.sync_engine, "before_cursor_execute", …)`
   works on an async engine, and `connection.sync_connection` works for the connection-bound
   fixture. Executed through the full HTTP stack it reports `['SAVEPOINT', 'SELECT', 'ROLLBACK']`,
   so the assertion must filter to data statements rather than count raw callbacks.

The two things most likely to be got wrong by default are not in the brief's discretion list.
First, **`ChangeTaskStatusCommand` has no `task_list_id`**, so the status endpoint of D-11 cannot
satisfy D-14's wrong-list 404 without changing the reference use case, its DTO and its seven unit
tests. Second, **every integration test in this phase needs an HTTP fixture that does not exist
yet**: `tests/conftest.py` builds the app against a fictional DSN, and `tests/integration/conftest.py`
never meets it. The bridge is `app.dependency_overrides[get_uow]` pointing at the connection-bound
`session_factory` — proven working end to end below, including the non-obvious rule that a
seeding session must `commit()` (a savepoint release) or its rows vanish when it closes.

**Primary recommendation:** Wave 0 builds the three seams (the `Unset` sentinel + `CurrentActor`
dependency + the `api_client` integration fixture) and the two new gates; then one plan per
aggregate slice (lists, tasks, status, listing), each closing with its integration tests.

## User Constraints (from CONTEXT.md)

### Locked Decisions

**Carried forward (locked earlier, not re-discussed)**
- The state machine is the one in Phase 2 D-01/D-02/D-03. An invalid move raises
  `InvalidStatusTransitionError`, which becomes a 409 whose `errors` carry `from`/`to`. A
  same-state request is a 200 no-op.
- Business limits live only in the entities (Phase 2 D-04). Pydantic checks shape and type,
  and never repeats a length limit or the past-date rule.
- List-name uniqueness is per owner and **case-sensitive** (03-01, D-12). The use case
  pre-checks with `exists_with_name`, and the repository translates `uq_task_lists_owner_id_name`
  into `DuplicateTaskListNameError`, which becomes a 409 (03 D-13).
- Filters take a single value each (`?status=`, `?priority=`), combined with AND. Multi-value
  filters are API-02 (v2).
- Every command's first field is `actor_id: UUID`. The use case, not the router, decides
  visibility (Phase 2 D-18, ADR-008).
- A use case is one class with `execute(command) -> result`. Commands and results are frozen
  slotted dataclasses (D-15/D-16, ADR-020). `ChangeTaskStatus` is the reference shape.
- Routers inject dependencies as `Annotated[T, Depends(provider)]`, never as an argument
  default (B008, ADR on 03-09). The `get_uow` dependency never commits; the use case commits.
- The completion percentage covers the whole list and ignores the filter, computed by one
  SQL aggregate (ADR-009, `completion_statement()`). An empty list yields `0.0`.

**Actor identity before authentication**
- **D-01:** Every router obtains the caller through a single presentation dependency,
  `get_current_actor() -> UUID`, exposed through an `Annotated` alias (for example
  `CurrentActor`). In Phase 4 it returns a fixed demo user id. Phase 5 replaces **only the body**
  of this dependency with JWT decoding, so no router, schema or use case changes when auth
  arrives. An ADR records this as a deliberate, temporary seam and not as authentication.
- **D-02:** The demo user's row is created by an **idempotent seed step in the container
  entrypoint**, run after `alembic upgrade head`
  (`INSERT ... ON CONFLICT (id) DO NOTHING` with the fixed UUID). No Alembic data migration and
  no get-or-create inside a dependency. Tests never rely on the seed: each test creates its own
  users. Phase 5 deletes the seed step together with the seam.
- **D-03:** The demo UUID is a `Final` constant in `presentation`, next to `get_current_actor`,
  and the seed reads that same constant. It is not a setting, because it is not configuration
  and it disappears in Phase 5. `.env.example` gains no key.
- **D-04:** Ownership is **enforced now**. Every list and task use case checks
  `task_list.owner_id == actor_id`. A list the actor does not own answers exactly like an
  absent one, on every verb: `TaskListNotFoundError` for list routes and `TaskNotFoundError`
  for task routes, as `ChangeTaskStatus` already does. Unit tests with two fake actors prove
  the 404 per verb. Phase 5 only adds the assignee capabilities (view and change status) and
  the 403 leg.

**PATCH semantics (lists and tasks)**
- **D-05:** Omitting a field leaves it unchanged, and an explicit `null` clears a nullable
  field (`description`, `due_date`). These are JSON Merge Patch (RFC 7396) semantics, read from
  Pydantic's `model_fields_set`. An explicit `null` on a non-nullable field (`name`, `title`,
  `priority`) gets a 422 `validation_error`. Tests prove the omitted, null and value legs.
- **D-06:** PATCH schemas use `extra="forbid"` and require at least one known field. An empty
  body `{}`, or a body with only unknown keys, gets a 422 `validation_error`. A typo like
  `titel` is refused, never silently ignored.
- **D-07:** A PATCH that explicitly sets `due_date` to a past moment is refused by
  `Task.reschedule()` (422 `validation_error`, `field: due_date`). The entity rule is unchanged.
  A PATCH that does not include `due_date` never re-checks it, so an overdue task can still be
  renamed, re-prioritised or completed.
- **D-08:** `status` is not a field of the task PATCH schema at all. With `extra="forbid"`,
  sending it gets a 422, which is how TASK-03 / roadmap SC-3's "cannot be changed through the
  generic PATCH" is proven.

**Response shapes**
- **D-09:** `GET /api/v1/task-lists/{list_id}/tasks` returns a flat envelope:
  `{"items": [TaskResponse...], "total_tasks": int, "completed_tasks": int,
  "completion_percentage": float}`. The statistics always cover the whole list, whatever the
  filter. The percentage is a float rounded to 2 decimals and `0.0` when the list is empty.
- **D-10:** One `TaskListResponse` shape everywhere (`GET /task-lists`, and
  `GET`/`POST`/`PATCH /task-lists/{id}`). It always includes `total_tasks`, `completed_tasks`
  and `completion_percentage`. The collection computes the statistics for all of the actor's
  lists in **one grouped SQL query** (LIST-03, no N+1). That needs a new repository capability
  (for example `list_for_owner_with_stats`), expressed in domain types on the port. A single
  list reuses `completion_stats`.
- **D-11:** The status endpoint is `PATCH /api/v1/task-lists/{list_id}/tasks/{task_id}/status`
  with body `{"status": "<pending|in_progress|completed>"}` and `extra="forbid"`. It returns 200
  with the full `TaskResponse`. The same-state request is 200 with an unchanged body (D-02 of
  Phase 2).
- **D-12:** Create endpoints return **201 Created** with a `Location` header naming the new
  resource's URL, plus the full representation in the body. Delete endpoints return **204** with
  no body (LIST-05, TASK-04). Deleting a list cascades to its tasks, and a test asserts it.
- **D-13:** Both collections are ordered by `created_at`, then `id`, a deterministic total
  order (03-07). There are no sort parameters, and the order is documented in the route's
  OpenAPI description.
- **D-14:** A task requested under a list it does not belong to is a 404 `task_not_found`
  (TASK-02). The use case compares `task.task_list_id` with the path's `list_id`, and the answer
  is identical to that for an absent task.

**Proof and quality gates**
- **D-15:** Phase 2's deferred gate lands here. An import-linter `forbidden` contract stops
  `domain`, `application` and `infrastructure` from importing `fastapi` or `starlette`
  exceptions. An AST test asserts that no module under `presentation/api/routers` (or wherever
  the routers live) raises `HTTPException`, so a business failure is always a `DomainError`.
  Both are proven red with a planted violation and the capture is kept in `evidence/`.
  If a new gate is a pytest test, it adds no pre-commit or CI step (the ADR-015 argument used
  in 02-06 and 03-06).
- **D-16:** Every Phase 4 route gets integration tests over HTTP (httpx `ASGITransport` against
  the real `taskmanager_test` database, D-01 rollback isolation from Phase 3). Each route covers
  the success path and its key refusals:
  - 404, including the wrong-list and not-owned cases
  - 409 for a duplicate name, on create **and** rename
  - 409 for an invalid transition, with `from`/`to`
  - 422 for an invalid filter value, a blank title, an over-length field, a past due date, an
    empty PATCH and `status` in the generic PATCH
  - statistics that do not change with the filter

  Every use case gets unit tests against the in-memory fakes. Phase 6 then audits totality
  instead of writing the bulk.
- **D-17:** "No N+1" is proven, not only claimed. A test attaches a SQLAlchemy
  `before_cursor_execute` listener and asserts that `GET /task-lists` with 1 list and with N
  lists issues the same number of statements, and does the same for the task listing. This
  complements 03-07's compiled-SQL test of the aggregate.

### Claude's Discretion
- How an application command represents "field not provided" versus "set to None" for PATCH
  (a sentinel, a `fields_set: frozenset[str]`, or per-field wrappers). It must pass mypy strict
  and keep the application layer free of Pydantic.
- Whether `updated_at` moves on a PATCH whose values equal the current ones.
- Router module layout (for example `presentation/api/routers/task_lists.py` and `tasks.py`),
  schema module layout, and the names of the `Annotated` aliases.
- The exact seed mechanism inside the entrypoint (a small Python module run by the image, or
  inline SQL through the sync engine). It follows the entrypoint's existing wait-then-migrate
  pattern. If the seed lives under `src/taskmanager`, the coverage rules apply to it.
- The exact shape of the grouped list-statistics query (a LEFT JOIN with
  `COUNT(*) FILTER (...)` grouped by list, or a lateral subquery), provided it is one statement
  and lists with zero tasks yield `0.0`.
- The OpenAPI polish level in this phase: tags, summaries and declared error responses per route.
  DOC-04 is Phase 7, but documenting as the routes are written is welcome.

### Deferred Ideas (OUT OF SCOPE)
- JWT replacing the `get_current_actor` body, deleting the demo seed, and adding the assignee
  403 leg: Phase 5.
- Pagination and sorting (API-01), multi-value filters (API-02): v2, to be documented as
  pending in the README.
- A `PUT` alongside `PATCH`: out of scope per REQUIREMENTS.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ARC-05 | Pydantic v2 models type every HTTP boundary; application DTOs are frozen dataclasses (ADR-020) | "Pydantic schema vs application command" pattern; the sentinel-stays-out-of-the-schema finding; `TaskResponse.from_result` explicit-mapping recommendation |
| LIST-01 | Create a task list (name + optional description) | `TaskList.create` exists; `CreateTaskList` use case + `POST /api/v1/task-lists` + 201/`Location` idiom verified |
| LIST-02 | Get one of their task lists by id | `TaskListRepository.get` exists; ownership check pattern from `ChangeTaskStatus`; `completion_stats` for D-10's stats |
| LIST-03 | List their task lists with counts and completion % in SQL, no N+1 | New port method + the verified grouped `LEFT OUTER JOIN … count(tasks.id) FILTER (…)` statement; D-17 counter technique |
| LIST-04 | PATCH a task list | `Unset` sentinel command shape; `model_fields_set`; `TaskList.rename` exists, `TaskList.describe` is a gap |
| LIST-05 | Delete a task list, 204 | `TaskListRepository.delete` exists; verified `status_code=204, response_class=Response` idiom; DB cascade already tested at the row level |
| LIST-06 | Duplicate list name for the owner → 409 | `exists_with_name` + `DuplicateTaskListNameError` + `uq_task_lists_owner_id_name` translation all exist; only the use-case pre-check and the rename leg are new |
| TASK-01 | Create a task in a list with title/description/priority/due date, starts `pending` | `Task.create` exists with every rule; `DEFAULT_PRIORITY` ClassVar recommendation keeps the default in one place |
| TASK-02 | Get a task in its list; wrong list → 404 | D-14 comparison pattern; `TaskNotFoundError` already maps to 404 by MRO |
| TASK-03 | PATCH a task; `status` not writable | `extra="forbid"` verified to produce 422 `extra_forbidden` at `loc=["body","status"]` |
| TASK-04 | Delete a task, 204 | `TaskRepository.delete` exists; same 204 idiom |
| TASK-05 | Dedicated status endpoint; invalid transitions → 409 with a specific code | `ChangeTaskStatus` exists and is the reference; needs `task_list_id` added for D-14; 409 body already proven by `tests/api/test_error_contract.py` |
| TASK-06 | Filter by `status` and/or `priority`; invalid values → 422 | `list_for_task_list(..., status=, priority=)` exists; verified enum query params produce `loc=["query","status"]` → `field: "query.status"` |
| TASK-07 | Listing carries whole-list `completion_percentage`, `total_tasks`, `completed_tasks`; empty → `0.0` | `completion_stats()` + `CompletionStats.percentage` (a **property**, already rounded to 2 decimals) both exist and are tested |
| TASK-08 | Reject blank titles, over-length fields, past due dates | `require_text` / `optional_text` / `Task.create`'s due-date guard all exist; the work is proving them over HTTP as 422 `validation_error` |

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Request/response shape, `extra="forbid"`, enum filter parsing | Presentation (schemas) | — | ARC-05: Pydantic types the HTTP boundary and *only* the boundary |
| "Which field was provided" (PATCH) | Presentation reads `model_fields_set` | Application carries it as a typed sentinel | Pydantic is the only thing that knows what the client sent; the application must not import Pydantic (ADR-020) |
| Caller identity | Presentation (`get_current_actor`) | — | D-01; Phase 5 swaps the body only |
| Visibility (404 vs 403), ownership | Application (use case) | — | ADR-008 + Phase 2 D-18: the router must never decide it |
| Business rules (length, blank, past due date, transitions) | Domain (entities) | — | Phase 2 D-04: a limit in two layers is a defect |
| Transaction boundary | Application (`uow.commit()`) | — | ARC-08; `get_uow` hands over a *closed* unit of work |
| Filtering, ordering, counting | Infrastructure (SQL) | — | ADR-009, T-3-17/T-3-20: never a Python comprehension over a full read |
| Error → HTTP status | Presentation (`errors/mapping.py`) | — | ARC-06/ARC-07; new leaves resolve by MRO with no edit |
| `Location` URL construction | Presentation (router, `request.url_for`) | — | A URL is a transport concern |
| Demo-user row | Container entrypoint (shell) | — | D-02; ADR-037 precedent keeps it out of `src/` and out of the coverage gate |

## Project Constraints (from CLAUDE.md)

Every line below is enforced by a gate that fails a build. Research recommendations are checked
against them.

| Constraint | Consequence for this phase |
|------------|----------------------------|
| Import direction `main > presentation > infrastructure > application > domain` | Schemas (presentation) may import application DTOs and domain enums. The `Unset` sentinel must live at or below `application`. |
| `domain` imports no third-party library at all | `Task.DEFAULT_PRIORITY` as a ClassVar is fine; a Pydantic default is not a domain concern. |
| `application` imports no web framework and no ORM; DTOs are frozen slotted dataclasses | The PATCH sentinel must be stdlib (`enum.Enum`), not `pydantic.PydanticUndefined`. |
| `fastapi.HTTPException` may never be raised outside `presentation` | D-15's AST gate; a business failure is always a `DomainError`. |
| No transaction-ending call under `infrastructure/db/repositories/` | The new `list_for_owner_with_stats` adapter method must not commit. `tests/architecture/test_no_commit_in_repositories.py` scans the package by text. |
| Repositories take and return domain entities only | The new port method must be `Sequence[tuple[TaskList, CompletionStats]]`, never a `Row`. |
| Migrations run in the entrypoint, never in `create_app()` | The demo seed goes in `docker/entrypoint.sh` after `alembic upgrade head`; `test_creating_the_app_opens_no_connection` still has to pass. |
| Dependencies injected as `Annotated[T, Depends(provider)]` | Every router parameter. flake8-bugbear B008 fails the argument-default form. |
| `make lint`, `make typecheck`, `make arch`, `make test` green before any commit | mypy strict over `src` **and** `tests`; a new port method breaks the fakes until they implement it. |
| Coverage gated at 75%, no `pragma: no cover`, no `omit`; 100% is the standing norm | Routers, schemas and use cases all need tests. A seed module under `src/` would owe one — the shell heredoc does not. |
| A new gate must be added in **both** `.pre-commit-config.yaml` and `.github/workflows/ci.yml` — unless it rides inside pytest | D-15's two gates need **no** new hook or step: `lint-imports` and `pytest` already run in both. |
| English everywhere; no AI attribution trailer in commits | — |

## Standard Stack

No new dependency is introduced by this phase. Everything below is already pinned in
`requirements.txt` / `requirements-dev.txt` and installed in `.venv`.

### Core

| Library | Version | Purpose | Why standard here |
|---------|---------|---------|-------------------|
| fastapi | 0.141.1 | Routers, dependency injection, OpenAPI | Already the app's framework; brief-mandated [VERIFIED: `requirements.txt`, executed in `.venv`] |
| pydantic | 2.13.5 | Request/response schemas (ARC-05) | `model_fields_set`, `extra="forbid"`, `field_validator` all exercised below [VERIFIED: executed] |
| SQLAlchemy[asyncio] | 2.0.54 | The one new grouped query | `func.count(col).filter(...)` compiles to PostgreSQL `FILTER` [VERIFIED: compiled + executed] |
| psycopg[binary] | 3.3.5 | Driver | Returns `bigint` counters as Python `int` [VERIFIED: executed against PG 18.4] |
| pytest / pytest-asyncio / pytest-cov | 9.1.1 / 1.4.0 / 7.1.0 | Tests + the 75% gate | `asyncio_mode = auto`, function-scoped loop (ADR-012) |
| httpx | 0.28.1 | `AsyncClient(transport=ASGITransport(app=app))` | The project's only HTTP client shape; see the `TestClient` pitfall below |
| import-linter | 2.15 | D-15's `forbidden` contract | Proposed contract executed and KEPT against the current graph [VERIFIED: `lint-imports`] |

### Supporting (already present, newly relevant)

| Facility | Where | When to use |
|----------|-------|-------------|
| `fastapi.Query` | schemas/routers | `Annotated[TaskStatus \| None, Query()]` — enum filters, free 422 + Swagger enumeration |
| `fastapi.Response` (injected) | create routes | Set `Location` while still returning a `response_model` |
| `starlette.requests.Request.url_for` | create routes | Builds the absolute `Location` URL including the `/api/v1` prefix [VERIFIED: executed] |
| `sqlalchemy.event.listen(..., "before_cursor_execute", ...)` | D-17 tests | Statement counting on `engine.sync_engine` or `connection.sync_connection` |
| `enum.Enum` single-member sentinel | `application/dto/` | The typed "field not provided" marker |

### Alternatives Considered

| Instead of | Could use | Tradeoff |
|------------|-----------|----------|
| Enum sentinel on the command | `fields_set: frozenset[str]` on the command | Stringly typed: mypy cannot narrow, a typo silently means "omitted", and the use case needs a guard *and* a cast per field. Rejected. |
| Enum sentinel on the command | Per-field wrapper (`Patch[T]` dataclass) | Works and narrows, but every read becomes `command.title.value` behind `command.title.provided`, and the frozen-dataclass DTO convention gains a second vocabulary for no gain. Rejected. |
| Sentinel in the Pydantic schema too | — | Measured cost: `_Unset` becomes a public enum in `/openapi.json`, the explicit-null error `loc` becomes `["body","title","str"]` and `["body","title","enum[_Unset]"]` (two entries, both unreadable). Rejected on evidence. |
| Grouped `LEFT JOIN` | Correlated scalar subqueries per counter | Also one statement, but two subqueries per row and a harder `EXPLAIN`. The join is the shape PITFALLS Pitfall 11 names. |
| Grouped `LEFT JOIN` | `LATERAL` subquery | Equivalent; more SQL to read for no measured benefit. |
| Seed as a shell heredoc | Seed as `src/taskmanager/seed.py` | A module under `src/` owes a unit test under the no-omit coverage rule (CLAUDE.md), and adds a node to the import graph that would have to import `presentation`. ADR-037 already set the precedent for the readiness probe. |
| `response_class=Response` on 204 | Bare `status_code=204` | Measured: the bare form still emits `content-type: application/json` on an empty 204 body. Cosmetic but visible in `curl -i`. |

**Installation:** none. `pip install -r requirements-dev.txt` is unchanged.

## Package Legitimacy Audit

**Not applicable — this phase installs no external package.** Every library it uses is already
pinned by exact `==` in `requirements.txt` / `requirements-dev.txt` (shipped in Phase 1, ADR-011)
and already present in `.venv`. The slopcheck gate is therefore vacuous here; no package name in
this document was newly discovered from a search engine or from training recall.

If the planner nonetheless adds a dependency, the gate applies in full and the addition must also
update `requirements*.txt`, the Docker layer and the CI cache key.

## Architecture Patterns

### System Architecture Diagram

```
                    HTTP request (curl / Swagger / httpx AsyncClient)
                                     │
                                     ▼
                    ┌──────────────────────────────────┐
                    │  FastAPI routing + Pydantic       │
                    │  path params, query params,       │
                    │  request body, extra="forbid"     │
                    └───────────┬──────────────┬────────┘
                                │              │ invalid shape
                                │              ▼
                                │   RequestValidationError
                                │              │
                                │              ▼
                                │   handle_validation_error
                                │   → 422 problem+json
                                │     errors = [ {field,message,type}, … ]
                                ▼
                 ┌──────────────────────────────────────┐
                 │  Router handler (presentation)        │
                 │  CurrentActor = Depends(              │
                 │      get_current_actor)  ── D-01 seam │
                 │  UnitOfWorkDep = Depends(get_uow)     │
                 │  schema ──► Command (frozen dataclass)│
                 │        (model_fields_set → UNSET)     │
                 └───────────────┬──────────────────────┘
                                 ▼
                 ┌──────────────────────────────────────┐
                 │  Use case (application)               │
                 │  async with uow:                      │
                 │    load ──► authorize ──► domain call │
                 │       ──► persist ──► commit          │
                 └───┬─────────────┬──────────────┬─────┘
                     │             │              │
                     ▼             ▼              ▼
              TaskList /      DomainError    UnitOfWork
              Task entity     (not found,    (SqlAlchemy)
              invariants       conflict,          │
              + state machine  validation)        ▼
                     │             │      ┌──────────────────┐
                     │             │      │ Repositories      │
                     │             │      │ SELECT / INSERT   │
                     │             │      │ UPDATE / DELETE   │
                     │             │      │ grouped aggregate │
                     │             │      └────────┬─────────┘
                     │             │               ▼
                     │             │         PostgreSQL 18
                     │             │      (UNIQUE, FK CASCADE,
                     │             │       CHECK constraints)
                     │             │               │ IntegrityError
                     │             │               ▼
                     │             │      constraint-name translation
                     │             │      → DuplicateTaskListNameError
                     │             ▼
                     │     handle_domain_error
                     │     status_for(exc) by MRO
                     │     → 404 / 409 / 422 problem+json
                     ▼
              Result DTO (frozen)
                     │
                     ▼
              Response schema (Pydantic)
              + Location header (201) / empty body (204)
                     │
                     ▼
                HTTP response
```

### Recommended Project Structure

```
src/taskmanager/
├── domain/
│   ├── entities/task.py              # + describe(), reprioritise(), DEFAULT_PRIORITY
│   └── entities/task_list.py         # + describe()
├── application/
│   ├── dto/unset.py                  # NEW: the Unset sentinel
│   ├── dto/commands.py               # + 10 commands; ChangeTaskStatusCommand gains task_list_id
│   ├── dto/results.py                # + TaskListResult, TaskCollectionResult
│   ├── ports/repositories.py         # + list_for_owner_with_stats
│   └── use_cases/
│       ├── access.py                 # NEW (optional): the one copy of the ADR-008 load+authorize
│       ├── task_lists/{create,get,list,update,delete}.py
│       └── tasks/{create,get,list,update,delete,change_task_status}.py
├── infrastructure/db/repositories/task_lists.py   # + the grouped statement
└── presentation/api/
    ├── actor.py                      # NEW: DEMO_USER_ID, get_current_actor, CurrentActor
    ├── schemas/{common,task_lists,tasks}.py       # NEW
    └── routers/{task_lists,tasks}.py              # NEW
docker/entrypoint.sh                  # + step 2b: idempotent demo-user seed
.importlinter                         # + the D-15 forbidden contract
tests/
├── architecture/test_routers_raise_no_http_exception.py   # NEW (AST gate)
├── architecture/test_layer_boundaries.py                  # EXPECTED_CONTRACT_NAMES += 1
├── integration/conftest.py           # + api_client / actor-override fixtures
├── integration/api/test_task_lists.py, test_tasks.py, test_statements.py   # NEW
└── unit/application/...              # one module per new use case; fakes.py extended
```

### Pattern 1: The typed PATCH sentinel (Claude's-discretion item #1)

**What:** A single-member `enum.Enum` marks "the client did not send this field". It lives in the
application layer, is stdlib-only, and narrows under `mypy --strict`.

**Why an Enum and not `object()` or `None`:** `None` is a legal *value* for the nullable fields, so
it cannot also mean "absent". A bare `_UNSET = object()` gives mypy nothing to narrow on. A
single-member Enum is the form the typing ecosystem settled on, and mypy treats
`x is not UNSET` as a literal narrowing.

```python
# src/taskmanager/application/dto/unset.py
from enum import Enum
from typing import Final


class Unset(Enum):
    """The typed marker for "this PATCH field was not provided".

    A single-member enum rather than `object()`: mypy narrows an `is not` test
    against an enum member, so `str | Unset` becomes `str` inside the guard and
    forgetting the guard is a type error rather than a runtime surprise.
    `None` cannot serve, because it is a legal value for every nullable field.
    """

    TOKEN = "unset"


UNSET: Final = Unset.TOKEN
```

```python
# src/taskmanager/application/dto/commands.py  (excerpt)
@dataclass(frozen=True, slots=True)
class UpdateTaskCommand:
    actor_id: UUID
    task_list_id: UUID
    task_id: UUID
    title: str | Unset = UNSET
    description: str | None | Unset = UNSET
    priority: TaskPriority | Unset = UNSET
    due_date: datetime | None | Unset = UNSET
```

Verified under this repository's `mypy 2.3.1 --strict`:

```
sentinel.py:29: note: Revealed type is "str"                       # inside `is not UNSET`
sentinel.py:32: note: Revealed type is "str | None"
sentinel.py:35: note: Revealed type is "datetime.datetime | None"
sentinel.py:43: error: Argument 1 to "takes_str" has incompatible type
                      "str | Unset"; expected "str"  [arg-type]     # guard omitted
```

[VERIFIED: `.venv/bin/mypy --strict` executed 2026-09-18]

**The use case then reads it:**

```python
if command.title is not UNSET:
    task.rename(command.title, now=now)          # narrowed to str
if command.description is not UNSET:
    task.describe(command.description, now=now)  # narrowed to str | None
if command.due_date is not UNSET:
    task.reschedule(command.due_date, now=now)   # D-07: only re-checked when sent
```

### Pattern 2: The Pydantic PATCH schema — and why the sentinel stays out of it

**What:** the schema declares `X | None = None` and the *router* converts `model_fields_set` into
the sentinel. `extra="forbid"` + one model validator gives D-06; one field validator per
non-nullable field gives D-05's explicit-null 422 with a clean field-level `loc`.

```python
# src/taskmanager/presentation/api/schemas/tasks.py  (excerpt)
class TaskPatchRequest(BaseModel):
    """PATCH body: omitted leaves unchanged, explicit null clears a nullable field.

    `status` is deliberately absent: with extra="forbid" a client that sends it
    gets a 422, which is how "status is not writable here" (TASK-03, D-08) is
    proven rather than promised.
    """

    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    description: str | None = None
    priority: TaskPriority | None = None
    due_date: datetime | None = None

    @field_validator("title", "priority")
    @classmethod
    def _not_explicitly_null(cls, value: object, info: ValidationInfo) -> object:
        # Runs only for a value the client actually sent: pydantic skips field
        # validators for defaults unless validate_default is set. So this is the
        # explicit-null leg of D-05 and nothing else.
        if value is None:
            raise ValueError("this field may not be null")
        return value

    @model_validator(mode="after")
    def _at_least_one_field(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("at least one field must be provided")
        return self

    def to_command(self, *, actor_id: UUID, task_list_id: UUID, task_id: UUID)
            -> UpdateTaskCommand:
        sent = self.model_fields_set        # never `self.model_fields` - see pitfalls
        return UpdateTaskCommand(
            actor_id=actor_id,
            task_list_id=task_list_id,
            task_id=task_id,
            title=self.title if "title" in sent else UNSET,      # type: ignore-free:
            description=self.description if "description" in sent else UNSET,
            priority=self.priority if "priority" in sent else UNSET,
            due_date=self.due_date if "due_date" in sent else UNSET,
        )
```

Measured behaviour on the pinned stack (`fastapi 0.141.1`, `pydantic 2.13.5`)
[VERIFIED: executed 2026-09-18]:

| Request body | Status | `errors` entry `field` / `type` |
|--------------|--------|---------------------------------|
| `{}` | 422 | `body` / `value_error` — "at least one field must be provided" |
| `{"titel": "x"}` | 422 | `body.titel` / `extra_forbidden` |
| `{"status": "completed"}` | 422 | `body.status` / `extra_forbidden` |
| `{"title": null}` | 422 | `body.title` / `value_error` |
| `{"description": null}` | 200 | `model_fields_set == {"description"}`, value `None` |
| `{"title": "x"}` | 200 | `model_fields_set == {"title"}`, description untouched |

For contrast, the *rejected* sentinel-in-the-schema variant produced, for `{"title": null}`, two
error entries at `body.title.str` and `body.title.enum[_Unset]`, and leaked this into
`/openapi.json`:

```json
"title": {"anyOf": [{"type": "string"}, {"$ref": "#/components/schemas/_Unset"}],
          "default": "UNSET"}
```

[VERIFIED: executed 2026-09-18 — this is the decisive evidence for keeping the sentinel out of
the boundary schema]

### Pattern 3: The grouped list-statistics query (D-10)

```python
# src/taskmanager/infrastructure/db/repositories/task_lists.py
def lists_with_stats_statement(owner_id: UUID) -> Select[tuple[TaskListRow, int, int]]:
    """LIST-03 in one statement: every list of one owner, with its two counters.

    A module-level function for the reason `completion_statement` is one: the SQL
    can be compiled and asserted on with no server at all, so a later refactor
    back into 1+N queries fails a test rather than a code review.

    `count(tasks.id)`, never `count(*)`: on the null-extended row a LEFT OUTER
    JOIN produces for a list with no tasks, `count(*)` returns 1 and the list
    reports 100%/0% over a phantom task. `count(tasks.id)` returns 0, which is
    what makes the empty list yield 0.0.
    """
    return (
        select(
            TaskListRow,
            func.count(TaskRow.id).label("total"),
            func.count(TaskRow.id)
            .filter(TaskRow.status == TaskStatus.COMPLETED.value)
            .label("completed"),
        )
        .outerjoin(TaskRow, TaskRow.task_list_id == TaskListRow.id)
        .where(TaskListRow.owner_id == owner_id)
        .group_by(TaskListRow.id)
        .order_by(TaskListRow.created_at, TaskListRow.id)   # D-13 total order
    )
```

Compiles to (psycopg dialect):

```sql
SELECT task_lists.id, task_lists.owner_id, task_lists.name, task_lists.description,
       task_lists.created_at, task_lists.updated_at,
       count(tasks.id) AS total,
       count(tasks.id) FILTER (WHERE tasks.status = %(status_1)s) AS completed
FROM task_lists LEFT OUTER JOIN tasks ON tasks.task_list_id = task_lists.id
WHERE task_lists.owner_id = %(owner_id_1)s::UUID
GROUP BY task_lists.id
ORDER BY task_lists.created_at, task_lists.id
```

Executed against the live `taskmanager_test` (PostgreSQL 18.4):

```
statements issued by the grouped query: 1 ['SELECT']
  empty: total=0 completed=0 pct=0.0 types=int
  full:  total=3 completed=2 pct=66.67 types=int
with 5 lists -> statements: 1
```

[VERIFIED: executed 2026-09-18 against PostgreSQL 18.4]

**Port shape** (domain types only, per CLAUDE.md's repositories rule):

```python
async def list_for_owner_with_stats(
    self, owner_id: UUID
) -> Sequence[tuple[TaskList, CompletionStats]]: ...
```

**Adapter body:** `rows = await self._session.execute(statement)`, then
`[(task_list_to_entity(row), CompletionStats(total=total, completed=completed))
  for row, total, completed in rows]`. `GROUP BY task_lists.id` is sufficient because `id` is the
primary key (PostgreSQL functional-dependency rule), so every other selected column is legal
without being listed.

### Pattern 4: 201 + `Location`, and 204 with no body

```python
@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=TaskListResponse,
    summary="Create a task list",
)
async def create_task_list(
    payload: TaskListCreateRequest,
    actor_id: CurrentActor,
    uow: UnitOfWorkDependency,
    clock: ClockDependency,
    request: Request,
    response: Response,
) -> TaskListResponse:
    result = await CreateTaskList(uow, clock).execute(payload.to_command(actor_id=actor_id))
    response.headers["Location"] = str(
        request.url_for("get_task_list", list_id=result.id)
    )
    return TaskListResponse.from_result(result)
```

```python
@router.delete(
    "/{list_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,        # keeps the empty 204 free of a content-type header
    summary="Delete a task list",
)
async def delete_task_list(list_id: UUID, actor_id: CurrentActor,
                           uow: UnitOfWorkDependency) -> None:
    await DeleteTaskList(uow).execute(DeleteTaskListCommand(actor_id=actor_id,
                                                            task_list_id=list_id))
```

Measured [VERIFIED: executed 2026-09-18]:

- `request.url_for("get_task_list", list_id=…)` with `include_router(router, prefix="/api/v1")`
  and `APIRouter(prefix="/task-lists")` yields
  `http://testserver/api/v1/task-lists/7781375c-…` — the prefix is honoured, so no string
  concatenation is needed.
- `status_code=204` + `return None` **without** `response_class=Response`: body is `b""`, but
  the response still carries `content-type: application/json`. With `response_class=Response`
  there is no content-type at all. OpenAPI is identical (`{"description": "Successful Response"}`,
  no `content`) in both cases.

### Pattern 5: The actor seam (D-01/D-03)

```python
# src/taskmanager/presentation/api/actor.py
DEMO_USER_ID: Final[UUID] = UUID("00000000-0000-4000-8000-00000000de00")


def get_current_actor() -> UUID:
    """The caller's identity. Phase 4 runs as one demo user; Phase 5 replaces
    this body with JWT decoding and nothing else in the project moves."""
    return DEMO_USER_ID


CurrentActor = Annotated[UUID, Depends(get_current_actor)]
```

A separate module rather than an addition to `dependencies.py`, for two reasons: the entrypoint's
seed imports `DEMO_USER_ID` and should not drag `sqlalchemy` in to do it, and Phase 5 deletes one
file instead of editing one.

Integration tests that need a second actor override the provider:
`app.dependency_overrides[get_current_actor] = lambda: other_user_id`. This is the *only* way to
get the D-04 "not owned → 404" legs over HTTP, so the fixture must expose it.

### Pattern 6: The demo-user seed in the entrypoint (D-02)

Recommended placement: a second heredoc in `docker/entrypoint.sh`, between `alembic upgrade head`
and `exec uvicorn`. This is exactly the ADR-037 argument the existing readiness probe already
won: a module under `src/taskmanager/` owes a unit test under the no-`omit`/no-`pragma` coverage
rule, and this code disappears in Phase 5.

```sh
# --- 2b. Seed the demo user -------------------------------------------------
python - <<'PY'
import os
from datetime import UTC, datetime

from sqlalchemy import create_engine, text

from taskmanager.presentation.api.actor import DEMO_USER_ID

SEED = text(
    """
    INSERT INTO users (id, email, password_hash, created_at, updated_at)
    VALUES (:id, :email, :password_hash, :now, :now)
    ON CONFLICT DO NOTHING
    """
)
engine = create_engine(os.environ["DATABASE_URL"])
with engine.begin() as connection:
    connection.execute(SEED, {
        "id": DEMO_USER_ID,
        "email": "demo@taskmanager.local",
        # Not a credential and not a secret: "!" is not a valid Argon2 encoded
        # hash, so pwdlib's verify can never succeed against it. Phase 5 deletes
        # this row together with the seam.
        "password_hash": "!",
        "now": datetime.now(UTC),
    })
engine.dispose()
PY
```

What the `users` table actually requires [VERIFIED: `migrations/versions/0001_baseline.py`]:
`id UUID PK`, `email VARCHAR(320) NOT NULL`, `password_hash VARCHAR(512) NOT NULL`,
`created_at`/`updated_at TIMESTAMPTZ NOT NULL`, plus the unique index `uq_users_email_lower`
over `lower(email)`.

`ON CONFLICT DO NOTHING` **without a conflict target** was executed three times against the live
database: insert (rowcount 1), same id (rowcount 0, primary-key conflict absorbed), different id
with the same email (rowcount 0, `uq_users_email_lower` conflict absorbed). A targeted
`ON CONFLICT (id) DO NOTHING` would **not** absorb the second case and would abort the
entrypoint. [VERIFIED: executed 2026-09-18]

Layer safety: the heredoc is not a module under `src/`, so it adds no node to import-linter's
graph and cannot break a contract. It does import from `presentation`, which is legal for a
`main`-level consumer anyway.

Constraint to re-check in the plan: `taskmanager` is installed into `/opt/venv` in the runtime
image, so `from taskmanager.presentation.api.actor import DEMO_USER_ID` resolves; the `test` stage
deliberately does not carry `entrypoint.sh`, so nothing seeds the test database (correct — D-02
says tests never rely on the seed).

### Pattern 7: The HTTP integration harness (D-16) — the missing fixture

`tests/conftest.py` builds the app against a **fictional DSN**
(`postgresql+psycopg://user:pass@localhost:5432/taskmanager`) and never meets
`tests/integration/conftest.py`. Phase 4 needs a fixture that joins them:

```python
# tests/integration/conftest.py (addition)
@pytest.fixture
async def api_client(
    session_factory: Callable[[], AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[tuple[AsyncClient, FastAPI]]:
    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)   # never dialled: get_uow is overridden
    monkeypatch.setenv("JWT_SECRET", JWT_SECRET)
    app = create_app(Settings(_env_file=None))
    app.dependency_overrides[get_uow] = lambda: SqlAlchemyUnitOfWork(session_factory)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, app
```

This exact shape was executed end to end: a `POST` handler that opened `async with uow:` and
called `uow.commit()` wrote a row, a later `GET` on a second session read it back, and the outer
transaction rollback removed everything. Domain errors already came back as problem+json without
any extra wiring. [VERIFIED: executed 2026-09-18]

**The non-obvious rule this experiment surfaced:** a fixture that seeds a user must `commit()` the
seeding session. Under `join_transaction_mode="create_savepoint"`, closing a session without
committing **rolls its savepoint back**, so the seeded row silently disappears and every
subsequent request 404s (observed: the first run returned
`user_not_found` from the FK translation). `commit()` releases the savepoint into the outer
transaction, which the `connection` fixture still rolls back at teardown, so isolation is
preserved.

### Pattern 8: The D-17 statement counter

```python
@pytest.fixture
def statements(connection: AsyncConnection) -> Iterator[list[str]]:
    """Every data statement issued on the test connection, in order."""
    seen: list[str] = []

    def record(conn, cursor, statement, parameters, context, executemany):  # noqa
        verb = statement.split(maxsplit=1)[0].upper()
        if verb in {"SELECT", "INSERT", "UPDATE", "DELETE"}:
            seen.append(verb)

    event.listen(connection.sync_connection, "before_cursor_execute", record)
    try:
        yield seen
    finally:
        event.remove(connection.sync_connection, "before_cursor_execute", record)
```

Measured through the full HTTP stack, the raw callback stream for one `GET` is
`['SAVEPOINT', 'SELECT', 'ROLLBACK']` — the session's savepoint bracketing is counted too, which
is why the filter above is not optional. [VERIFIED: executed 2026-09-18]

The assertion D-17 asks for: `GET /api/v1/task-lists` with 1 list and with N lists yields the
*same* `statements` list (one `SELECT`), and `GET …/tasks` likewise yields two (the page and the
aggregate — ADR-009 says two on purpose, and the point is that the number does not grow with the
row count).

### Pattern 9: D-15's two gates

**The import-linter contract.** Executed against the current graph and reported KEPT:

```ini
[importlinter:contract:no-http-below-presentation]
name = No web framework below presentation
type = forbidden
source_modules =
    taskmanager.domain
    taskmanager.application
    taskmanager.infrastructure
forbidden_modules =
    fastapi
    starlette
```

```
Analyzed 68 files, 165 dependencies.
Layered architecture (high to low) KEPT
Domain is framework-free KEPT
Application knows no web framework or ORM KEPT
No web framework below presentation KEPT
Contracts: 4 kept, 0 broken.
```

[VERIFIED: `.venv/bin/lint-imports --config … --no-cache` executed 2026-09-18]

`infrastructure` is clean today: its only occurrence of `starlette` is a prose mention inside
`db/engine.py`'s docstring, which import-linter does not see.

**Two consequences the planner must schedule:**
1. `tests/architecture/test_layer_boundaries.py::test_every_contract_is_configured` asserts the
   exact set `EXPECTED_CONTRACT_NAMES`. Adding a contract without updating that set fails the
   suite — which is the guard working, not a bug.
2. No `.pre-commit-config.yaml` hook and no `ci.yml` step is needed: `lint-imports` already runs
   in both (`pre-commit` hook id `import-linter`, CI step "Architecture contracts").

**The AST gate.** A prototype was executed against a planted-violation source:

```python
def _raised_name(node: ast.Raise) -> str | None:
    exc = node.exc
    if exc is None:
        return None
    if isinstance(exc, ast.Call):
        exc = exc.func
    if isinstance(exc, ast.Name):
        return exc.id
    if isinstance(exc, ast.Attribute):
        return exc.attr        # catches `fastapi.HTTPException(...)`
    return None
```

It caught `raise HTTPException(...)`, `raise fastapi.HTTPException(...)` and
`raise StarletteHTTPException(...)`. It **misses** `exc = HTTPException(...); raise exc`.
[VERIFIED: executed 2026-09-18]

Recommendation: pair it with a second, strictly stronger assertion that closes that hole —
*no router module imports `HTTPException` at all*, checked from the same AST
(`ast.ImportFrom` with `module in {"fastapi", "starlette.exceptions"}` and a name of
`HTTPException`, plus `import fastapi` + any `Attribute` access named `HTTPException`). Follow
`test_no_commit_in_repositories.py`'s structure exactly: a `REQUIRED_SCANNED_MODULES` frozenset
and a non-vacuity test, so a moved or renamed routers package fails the guard instead of
asserting that an empty list is empty.

### Pattern 10: Response schema built from the result DTO

`TaskResult` is a `@dataclass(frozen=True, slots=True)`, and
`TaskResponse.model_validate(result)` with `from_attributes=True` works —
`status`/`priority` serialise as `"pending"`/`"high"` (they are `StrEnum`) and datetimes as
`"2026-09-18T12:00:00Z"`. [VERIFIED: executed 2026-09-18]

**Recommended anyway: an explicit `from_result` classmethod naming every field**, mirroring
`TaskResult.from_entity`'s own docstring reasoning. `model_validate` silently ignores a result
field the response forgot and silently accepts a new result field, which is precisely the
automatic leak into the public API that the result DTO exists to prevent.

Also: **pass `response_model=` explicitly, or annotate the handler `-> TaskResponse`.** If the
handler is annotated `-> TaskResult` with no `response_model`, FastAPI infers the response model
from the *dataclass* and the boundary claim of ARC-05 quietly stops being true.

### Anti-Patterns to Avoid

- **`fastapi.testclient.TestClient` anywhere in this phase.** On the pinned stack, importing
  `starlette.testclient` emits `StarletteDeprecationWarning: Using httpx with
  starlette.testclient is deprecated; install httpx2 instead`, and `pytest.ini` sets
  `filterwarnings = error`. The test would fail at import. Use
  `AsyncClient(transport=ASGITransport(app=app), base_url="http://test")`, as every existing test
  already does. [VERIFIED: observed while running the probes]
- **`payload.model_fields`** (instance attribute). Deprecated since Pydantic 2.11; under
  `filterwarnings = error` it *raises* `PydanticDeprecatedSince211`. Use
  `type(payload).model_fields` or the class directly. `model_fields_set` on the instance is fine.
  [VERIFIED: executed 2026-09-18]
- **Repeating a business limit in Pydantic** (`Field(max_length=200)`, a past-date validator).
  Phase 2 D-04 forbids it and the entity already enforces it. Pydantic checks shape and type only.
- **A `for` loop over a list's tasks to compute a percentage** (PITFALLS Pitfall 11). Also:
  `selectinload(TaskListRow.tasks)` — the relationship is `lazy="raise"` and touching it raises.
- **`count(*)` in the grouped statistics query.** Reports `total=1` for a list with no tasks.
- **Committing anywhere but the use case.** `tests/architecture/test_no_commit_in_repositories.py`
  greps the adapter package for the literal call.
- **Raising `HTTPException` for "not found" in a router.** ADR-008 makes visibility a use-case
  decision, and D-15's new gate fails the build.
- **A second `errors` shape.** Every error body comes from `problem()`. No router builds one.

## Don't Hand-Roll

| Problem | Don't build | Use instead | Why |
|---------|-------------|-------------|-----|
| "Was this PATCH field provided?" | A `dict` of `Any` from `model_dump(exclude_unset=True)` | `model_fields_set` + the typed `Unset` sentinel on the command | `dict[str, Any]` defeats `mypy --strict` at the exact boundary where the phase's correctness lives |
| Empty-PATCH / unknown-key rejection | Manual key inspection in the router | `extra="forbid"` + a `model_validator` | Both already render through the project's 422 translator with correct `loc`s |
| Enum filter validation | `if status not in ("pending", …)` | `Annotated[TaskStatus \| None, Query()]` | Free 422 at `query.status`, free Swagger enumeration, and the value arrives as a bound parameter |
| Per-list completion counting | 1 + N queries, or counting in Python | The grouped `LEFT JOIN … FILTER` statement | PITFALLS Pitfall 11 — the one place an evaluator can see SQL thinking |
| Duplicate-name detection | `SELECT … ; if rows: 409` only | The existing `exists_with_name` pre-check **plus** the `IntegrityError` translation already in the adapter | The pre-check gives the clean 409; the constraint is the authority under concurrency |
| Cascade delete of tasks | Loading and deleting children in the use case | The `ON DELETE CASCADE` FK already in the baseline migration | Already tested at the row level (`test_deleting_a_task_list_cascades_to_its_tasks`) |
| Problem+json bodies | A dict literal per handler | `problem()` + the MRO status table | New error leaves resolve with **zero** edits to `mapping.py` |
| `Location` URL | f-string concatenation of `/api/v1/...` | `request.url_for("get_task_list", list_id=…)` | Honours the router prefix; a renamed prefix cannot silently produce a broken header |
| Test isolation | Truncating tables between tests | The existing `connection` fixture's outer rollback | D-01; a sweep would hide a repository that committed on its own |

**Key insight:** roughly 70% of this phase is *wiring already-proven components*. The genuinely
new code is eleven small use cases, one SQL statement, two Pydantic modules and two routers.
Any task that proposes re-solving persistence, error translation or transaction management is a
task that should be deleted.

## Common Pitfalls

### Pitfall 1: `ChangeTaskStatusCommand` cannot express D-14

**What goes wrong:** D-11 puts the status endpoint at
`/task-lists/{list_id}/tasks/{task_id}/status`, and D-14 requires a task addressed under the wrong
list to answer 404. `ChangeTaskStatusCommand` is `(actor_id, task_id, new_status)` — the use case
has no `list_id` to compare against, so the wrong-list request succeeds.

**Why it happens:** the command was written in Phase 2 before the URL shape was decided, and it is
labelled "the reference use case", which makes it read as finished.

**How to avoid:** add `task_list_id: UUID` to the command (second field, after `actor_id`) and one
comparison to the use case, next to the existing ownership check. Budget the blast radius: the DTO,
`change_task_status.py`, the seven constructor call sites in
`tests/unit/application/test_change_task_status.py`, and the "commands are frozen, first field is
`actor_id`" docstring.

**Warning signs:** a status-endpoint router that ignores `list_id`; a `# noqa`-free
`ARG001`-shaped unused path parameter.

### Pitfall 2: entity mutators that do not exist yet

**What goes wrong:** the PATCH use cases need `TaskList.describe`, `Task.describe` and
`Task.reprioritise`. `Task` has only `rename`, `reschedule` and `change_status`; `TaskList` has
only `rename`. Both docstrings say so explicitly ("Phase 4 adds the ones its PATCH endpoints
require"). A plan that assumes they exist fails at the first mypy run.

**How to avoid:** put the entity additions in an early wave, following the established convention
exactly — validate everything before assigning anything, take `now` as a keyword argument, and
stamp `updated_at` from the validated moment. `describe` delegates to `optional_text`, which
already turns `""` into `None`.

### Pitfall 3: the seeded fixture row that vanishes

**What goes wrong:** an integration fixture creates a user with a session from `session_factory`,
closes it, and every subsequent request 404s or raises `UserNotFoundError` from the FK
translation.

**Why it happens:** `join_transaction_mode="create_savepoint"` means closing an uncommitted session
rolls its SAVEPOINT back. Observed exactly this way while validating the harness.

**How to avoid:** the seeding session calls `commit()` (it releases the savepoint into the outer
transaction, which is still rolled back at teardown), or the fixture writes through the shared
`session` fixture.

**Warning signs:** `user_not_found` / `task_list_not_found` on the first request of a test that
"obviously" created the row.

### Pitfall 4: insert order without a relationship

**What goes wrong:** adding a `UserRow` and a `TaskListRow` to the same session and flushing once
raises `ForeignKeyViolation: … fk_task_lists_owner_id_users`. Observed.

**Why it happens:** `TaskListRow` declares a `ForeignKey` but no `relationship` back to `UserRow`,
so SQLAlchemy's unit of work has no dependency edge to sort the INSERTs by.

**How to avoid:** fixtures flush the user before adding lists (or add them in separate flushes).
Not an application-code problem — every production write path creates one aggregate at a time —
but it will bite the first integration fixture that batches.

### Pitfall 5: two different `errors` shapes under one `validation_error` code

**What goes wrong:** a test asserts `body["errors"][0]["field"] == "title"` and gets a `TypeError`,
or asserts a dict and gets a list.

**Why it happens:** the project has two 422 producers, and they already disagree by design:

| Source | `title` | `errors` |
|--------|---------|----------|
| `RequestValidationError` (schema/shape) | `"Request validation failed"` | **list** of `{field, message, type}` |
| domain `ValidationError` (entity rule) | `"Validation error"` | **object** — the error's `details`, e.g. `{"field": "due_date"}` |

Both carry `"code": "validation_error"`. This is pre-existing (Phase 2 D-07 + ADR-021) and not
something this phase should "fix" — but D-16's 422 cases split across both producers: an invalid
filter value, an empty PATCH and `status`-in-PATCH are the *list* shape, while a blank title, an
over-length field and a past due date are the *object* shape. Write the assertions accordingly and
say which is which in the test names.

### Pitfall 6: the `priority` default in two places

**What goes wrong:** the schema declares `priority: TaskPriority = TaskPriority.MEDIUM` and
`Task.create` also defaults to `MEDIUM`. Two copies of a business default — the defect Phase 2
D-04 exists to prevent.

**How to avoid:** promote the default to a domain ClassVar
(`Task.DEFAULT_PRIORITY: ClassVar[TaskPriority] = TaskPriority.MEDIUM`), use it as `Task.create`'s
default *and* as the Pydantic field default. Presentation may import from `domain` (the layer order
allows it), OpenAPI then documents the real default, and there is one copy.

### Pitfall 7: `str` field names in the schema→command mapper

**What goes wrong:** `self.title if "titel" in sent else UNSET` — the field is silently never
updated, and no gate catches it. mypy cannot check a string against `model_fields`.

**How to avoid:** one unit test per schema asserting
`set(TaskPatchRequest.model_fields) == {"title", "description", "priority", "due_date"}` *and* a
test per field proving the omitted/provided/null legs (D-05 already requires those three legs, so
the coverage is owed anyway). Mapper correctness is only ever provable by the tests, never by the
type checker — plan for it rather than hoping.

### Pitfall 8: `filterwarnings = error` turns deprecations into failures

Already bitten twice in the probes above (`TestClient`, `instance.model_fields`). Any new Pydantic
or Starlette idiom lifted from a tutorial should be run once before it is committed.

### Pitfall 9: the `test_every_contract_is_configured` guard

Adding the D-15 contract fails `tests/architecture/test_layer_boundaries.py` until
`EXPECTED_CONTRACT_NAMES` is updated in the same change. Expected, and worth noting in the plan so
it is not mistaken for a real violation during the red step.

### Pitfall 10: `updated_at` on an equal-value PATCH (discretion item #2)

**Recommendation: `updated_at` moves whenever a field is provided, regardless of whether the value
differs.** Reasons: D-06 already makes the empty body a 422, so there is no genuine no-op request;
comparing old and new values would put a second "did this change?" rule in the entity, next to
the mutators that already unconditionally stamp; and a client that sends a field is asking for a
write. Record it as one line in `DECISION_LOG.md` and assert it in a test named after the
decision, so a reviewer reads a choice rather than an accident.

## Code Examples

### The canonical Phase 4 use case (copy `ChangeTaskStatus`'s body)

```python
class UpdateTaskList:
    """Rename and/or re-describe one list on behalf of an authenticated actor."""

    def __init__(self, uow: UnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    async def execute(self, command: UpdateTaskListCommand) -> TaskListResult:
        async with self._uow:
            task_list = await self._uow.task_lists.get(command.task_list_id)
            # ADR-008 / D-04: a list the actor does not own answers exactly like
            # an absent one, on every verb.
            if task_list is None or task_list.owner_id != command.actor_id:
                raise TaskListNotFoundError(command.task_list_id)
            now = self._clock.now()                     # read once, handed down (D-13)
            if command.name is not UNSET:
                # LIST-06 on the rename leg too: the pre-check buys the clean 409,
                # and uq_task_lists_owner_id_name is still the authority.
                if command.name != task_list.name and await self._uow.task_lists.exists_with_name(
                    command.actor_id, command.name
                ):
                    raise DuplicateTaskListNameError(command.name)
                task_list.rename(command.name, now=now)
            if command.description is not UNSET:
                task_list.describe(command.description, now=now)
            await self._uow.task_lists.update(task_list)
            stats = await self._uow.tasks.completion_stats(task_list.id)
            await self._uow.commit()
        return TaskListResult.from_entity(task_list, stats)
```

### The shared load-and-authorize helper (recommended)

Ten use cases repeat `get` → `None or not owner` → raise. `ChangeTaskStatus` already sets the
precedent of a module-level private function. A shared module keeps ADR-008 in one place:

```python
# src/taskmanager/application/use_cases/access.py
async def visible_task_list(uow: UnitOfWork, task_list_id: UUID, actor_id: UUID) -> TaskList:
    """The list, if this actor may see it; otherwise the answer an absent list gets.

    One copy of ADR-008's "invisible reads as absent" rule. Ten use cases share it
    so the 404-not-403 leg cannot be forgotten in the eleventh.
    """
    task_list = await uow.task_lists.get(task_list_id)
    if task_list is None or task_list.owner_id != actor_id:
        raise TaskListNotFoundError(task_list_id)
    return task_list


async def visible_task(uow: UnitOfWork, task_list_id: UUID, task_id: UUID,
                       actor_id: UUID) -> Task:
    """The task, if it is in this list and this actor may see it (D-14, ADR-008)."""
    task = await uow.tasks.get(task_id)
    if task is None or task.task_list_id != task_list_id:
        raise TaskNotFoundError(task_id)
    task_list = await uow.task_lists.get(task_list_id)
    if task_list is None or task_list.owner_id != actor_id:
        raise TaskNotFoundError(task_id)
    return task
```

Note the deliberate asymmetry: task routes raise `TaskNotFoundError` on *every* leg, including a
missing or foreign parent list, because `task_list_not_found` would carry a different code and a
foreign identifier — the pre-authorization disclosure `change_task_status.py`'s docstring already
argues against at length.

### The task-listing use case (D-09 + TASK-07)

```python
    async def execute(self, command: ListTasksCommand) -> TaskCollectionResult:
        async with self._uow:
            await visible_task_list(self._uow, command.task_list_id, command.actor_id)
            tasks = await self._uow.tasks.list_for_task_list(
                command.task_list_id,
                status=command.status,
                priority=command.priority,
            )
            # ADR-009: no filter argument here, on purpose. The number describes
            # the list, the filter describes the view.
            stats = await self._uow.tasks.completion_stats(command.task_list_id)
        return TaskCollectionResult(
            items=tuple(TaskResult.from_entity(task) for task in tasks),
            stats=stats,
        )
```

No `commit()` — nothing was written. The unit of work's `__aexit__` rolls the read transaction
back, which is its documented obligation.

### `CompletionStats.percentage` — already correct for D-09

```python
    @property
    def percentage(self) -> float:
        if self.total == 0:
            return 0.0
        return round(self.completed / self.total * 100, 2)
```

**Two facts the planner should carry:** it is a **property**, not a method — CONTEXT.md's
`CompletionStats.percentage()` would be a `TypeError` at the call site — and its rounding is
already two decimals, so D-09 needs no change to the domain. Verified against the live data:
2 of 3 completed → `66.67`; empty list → `0.0`. [VERIFIED: source read + executed]

## State of the Art

| Old approach | Current approach | When changed | Impact here |
|--------------|------------------|--------------|-------------|
| `AsyncClient(app=app)` | `AsyncClient(transport=ASGITransport(app=app))` | httpx 0.28 | Already the project's shape; do not regress |
| `fastapi.testclient.TestClient` for API tests | httpx `AsyncClient` + `ASGITransport` | Starlette deprecation on the pinned version | Under `filterwarnings = error` the old form now **fails at import** |
| `instance.model_fields` | `type(instance).model_fields` | Pydantic 2.11 | Raises under `filterwarnings = error` |
| `@validator` / `@root_validator` | `@field_validator` / `@model_validator(mode="after")` | Pydantic v2 | Use the v2 spellings only |
| `.dict()` / `.json()` | `.model_dump()` / `.model_dump_json()` | Pydantic v2 | — |
| `class TaskStatus(str, Enum)` | `enum.StrEnum` | Python 3.11 | Already done; `str(member)` renders the value |
| Percentage counted in Python | `count(col) FILTER (WHERE …)` grouped in SQL | — | PITFALLS Pitfall 11; the phase's one visible SQL judgement |

**Deprecated / outdated for this phase:**
- `Depends()` as an argument default — flake8-bugbear B008 fails it, ADR-034 forbids it.
- `response_model` inferred from a dataclass return annotation — silently bypasses ARC-05.
- JSON Patch / JSON Merge Patch content types — CONTEXT D-05 specifies merge-patch *semantics*
  over a plain `application/json` partial object, which is what the FastAPI docs' `exclude_unset`
  pattern describes [CITED: fastapi.tiangolo.com/tutorial/body-updates].

## What Already Exists vs What Is Missing

### Exists and is reusable as-is

| Asset | Location |
|-------|----------|
| `Task.create / rename / reschedule / change_status`, `TaskList.create / rename` | `domain/entities/` |
| `require_text` / `optional_text` / `require_utc` (all TASK-08 limits) | `domain/validation.py` |
| `TaskStatus`, `TaskPriority`, `ALLOWED_TRANSITIONS`, `CompletionStats.percentage` | `domain/value_objects/` |
| Full `DomainError` hierarchy incl. `DuplicateTaskListNameError`, `TaskNotFoundError`, `TaskListNotFoundError`, `InvalidStatusTransitionError` | `domain/exceptions.py` |
| `ChangeTaskStatus` use case (the template) | `application/use_cases/tasks/change_task_status.py` |
| `ChangeTaskStatusCommand`, `TaskResult` + `from_entity` | `application/dto/` |
| `TaskRepository` (get/add/update/delete/`list_for_task_list`/`completion_stats`), `TaskListRepository` (get/add/update/delete/`list_for_owner`/`exists_with_name`), `UnitOfWork`, `Clock` | `application/ports/` |
| All three SQLAlchemy adapters incl. `completion_statement()` and the `IntegrityError` → domain translation | `infrastructure/db/repositories/` |
| `SqlAlchemyUnitOfWork` (refuses double entry, rolls back on every exit path) | `infrastructure/db/unit_of_work.py` |
| `get_uow`, `get_engine`, `get_session_factory`, the `Annotated` alias convention | `presentation/api/dependencies.py` |
| `register_exception_handlers`, `problem()`, `status_for()` MRO table | `presentation/api/errors/` |
| `create_app()` composition root | `main.py` |
| `migrated_database`, `connection`, `session_factory`, `session`, `uow` fixtures; `client` / `tolerant_client` | `tests/conftest.py`, `tests/integration/conftest.py` |
| Fakes for all eight ports, `FrozenClock` | `tests/unit/application/fakes.py` |

### Missing — the concrete gap list

**Domain (4 additions)**
- `TaskList.describe(description: str | None, *, now)`
- `Task.describe(description: str | None, *, now)`
- `Task.reprioritise(priority: TaskPriority, *, now)`
- `Task.DEFAULT_PRIORITY` ClassVar (and `Task.create`'s default reads it)

**Application**
- `dto/unset.py`: `Unset` + `UNSET`
- 10 new commands; `ChangeTaskStatusCommand` gains `task_list_id`
- `TaskListResult` (+ `from_entity(task_list, stats)`), `TaskCollectionResult`, and a result for
  the list collection (a `tuple[TaskListResult, ...]` is enough)
- Port: `TaskListRepository.list_for_owner_with_stats`
- 10 use cases: `CreateTaskList`, `GetTaskList`, `ListTaskLists`, `UpdateTaskList`,
  `DeleteTaskList`, `CreateTask`, `GetTask`, `ListTasks`, `UpdateTask`, `DeleteTask`
- Optional shared `access.py` helper

**Infrastructure**
- `lists_with_stats_statement()` + the adapter method

**Presentation**
- `actor.py` (`DEMO_USER_ID`, `get_current_actor`, `CurrentActor`)
- `schemas/`: `TaskListCreateRequest`, `TaskListPatchRequest`, `TaskListResponse`,
  `TaskCreateRequest`, `TaskPatchRequest`, `TaskStatusChangeRequest`, `TaskResponse`,
  `TaskCollectionResponse`
- `routers/task_lists.py` (5 routes), `routers/tasks.py` (6 routes)
- A `ClockDependency` provider (`SystemClock` exists in `infrastructure/clock.py`; there is no
  `get_clock` provider yet — check `dependencies.py`, it has only engine/session/uow)
- `create_app()` includes both routers under `/api/v1`

**Tests**
- `fakes.py`: implement `list_for_owner_with_stats`; also give
  `FakeTaskListRepository.list_for_owner` the `created_at, id` ordering the adapter has, or a
  D-13 assertion will pass in unit tests and fail over HTTP
- `tests/unit/application/test_ports.py`: the new port method must be reflected
- 11 use-case unit test modules; schema unit tests (the three PATCH legs per field)
- `tests/integration/api/`: one module per router + the D-17 statement tests
- `tests/architecture/`: the AST gate; `EXPECTED_CONTRACT_NAMES` update

**Root artifacts**
- `.importlinter`: one contract
- `docker/entrypoint.sh`: the seed step
- `DECISION_LOG.md`: ADRs for the actor seam, the PATCH sentinel, the `updated_at` choice, the
  status-endpoint-vs-action-verb choice (FEATURES flags Todoist as the defensible alternative)
- `AI_WORKFLOW.md`: the phase's incident entries
- `evidence/`: the two D-15 red captures

## Divergences Between Older Research and the Locked Decisions

`.planning/research/FEATURES.md` predates the CONTEXT decisions and contradicts them in three
places. CONTEXT wins; flagged so a plan does not "fix" the code back to the research.

| FEATURES.md says | CONTEXT.md decides | Authority |
|------------------|--------------------|-----------|
| Empty PATCH `{}` → 200 idempotent no-op | 422 `validation_error` | D-06 |
| Multi-value filters `?status=a&status=b`, OR within a field | Single value per filter, AND across | Carried-forward decision; multi-value is API-02 (v2) |
| Envelope carries `list_id`, `returned_count`, `filters` | Exactly `items`, `total_tasks`, `completed_tasks`, `completion_percentage` | D-09 |

## Runtime State Inventory

Not applicable — this is a greenfield feature phase, not a rename, refactor or migration. The one
piece of runtime state it *introduces* is the demo-user row, covered under Pattern 6 (idempotent,
entrypoint-owned, deleted in Phase 5, never relied on by tests).

## Environment Availability

| Dependency | Required by | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Python venv with the pinned stack | everything | ✓ | `.venv`, CPython 3.14.3 | — |
| PostgreSQL (test database) | integration tests | ✓ | 18.4, `taskmanager_test` reachable on `localhost:5432` | `make docker-test` |
| Docker + compose stack | cold-start rehearsal, seed verification | ✓ | `test-db-1` and `test-api-1` both healthy | — |
| `lint-imports`, `mypy`, `flake8`, `black`, `isort`, `pytest` | gates | ✓ | as pinned | — |

**Missing with no fallback:** none.

**Pre-existing red to be aware of:** `.venv/bin/pytest` on this host reports
`1 failed, 292 passed` — `tests/unit/test_settings.py::test_get_settings_is_cached`. Cause:
`get_settings()` reads the developer's `.env` (which sets `TEST_DATABASE_URL`), while the test
compares against `Settings(_env_file=None)` built from only the two monkeypatched variables. The
Docker `test` stage and CI have no `.env`, so it passes there. This is **pre-existing and
host-specific**, not caused by Phase 4 — but `make test` is a phase gate, so the plan should
either fix it (pass `_env_file=None` to the cached comparison, or clear the offending variable)
or record explicitly that the authoritative run is `make docker-test`. Coverage is 100% over 731
statements today. [VERIFIED: executed 2026-09-18]

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 + pytest-asyncio 1.4.0 (`asyncio_mode = auto`, function-scoped loop) + pytest-cov 7.1.0 |
| Config file | `pytest.ini` (authoritative; `[tool.pytest.ini_options]` in `pyproject.toml` would be silently ignored) |
| Quick run command | `.venv/bin/pytest tests/unit tests/architecture -q --no-cov` (no database, < 2 s) |
| Full suite command | `.venv/bin/pytest` (requires a reachable PostgreSQL — ADR-029) or `make docker-test` |

`--no-cov` is required for any subset run: `--cov-fail-under=75` rides in `addopts`, so a partial
run would otherwise fail the gate. [VERIFIED: executed]

### Phase Requirements → Test Map

| Req | Behavior | Type | Automated command | File exists? |
|-----|----------|------|-------------------|--------------|
| ARC-05 | Every route declares a Pydantic request/response model; no router returns a dataclass | unit | `pytest tests/unit/presentation/test_schemas.py -q --no-cov` | ❌ Wave 0 |
| ARC-05 | Commands/results stay frozen slotted dataclasses | unit | `pytest tests/unit/application -k "immutable or undeclared" -q --no-cov` | ✅ pattern exists (`test_change_task_status.py`) |
| LIST-01 | `POST /api/v1/task-lists` → 201 + `Location` + body | integration | `pytest tests/integration/api/test_task_lists.py -k create -x` | ❌ Wave 0 |
| LIST-02 | `GET /api/v1/task-lists/{id}` → 200; not-owned → 404 | integration | `pytest tests/integration/api/test_task_lists.py -k get -x` | ❌ Wave 0 |
| LIST-03 | `GET /api/v1/task-lists` → stats per list, ordered, **one statement** | integration | `pytest tests/integration/api/test_statements.py -k lists -x` | ❌ Wave 0 |
| LIST-04 | PATCH: omitted / explicit-null / value legs, 422 on `{}` and unknown keys | integration + unit | `pytest tests/integration/api/test_task_lists.py -k patch -x` | ❌ Wave 0 |
| LIST-05 | `DELETE` → 204, empty body, tasks cascade away | integration | `pytest tests/integration/api/test_task_lists.py -k delete -x` | ❌ Wave 0 |
| LIST-06 | 409 `duplicate_task_list_name` on create **and** rename | integration | `pytest tests/integration/api/test_task_lists.py -k duplicate -x` | ❌ Wave 0 |
| TASK-01 | `POST …/tasks` → 201, `status == "pending"`, default priority `medium` | integration | `pytest tests/integration/api/test_tasks.py -k create -x` | ❌ Wave 0 |
| TASK-02 | Task under the wrong list → 404 `task_not_found` | integration | `pytest tests/integration/api/test_tasks.py -k wrong_list -x` | ❌ Wave 0 |
| TASK-03 | PATCH excludes `status`; sending it → 422 `extra_forbidden` | integration | `pytest tests/integration/api/test_tasks.py -k status_is_not_writable -x` | ❌ Wave 0 |
| TASK-04 | `DELETE` task → 204, empty body | integration | `pytest tests/integration/api/test_tasks.py -k delete -x` | ❌ Wave 0 |
| TASK-05 | Status endpoint walks pending→in_progress→completed; `completed→pending` → 409 with `from`/`to`; same-state → 200 | integration + unit | `pytest tests/integration/api/test_tasks.py -k status -x` | ⚠️ unit exists (`test_change_task_status.py`), HTTP leg ❌ |
| TASK-06 | `?status=` / `?priority=` filter; invalid value → 422 at `query.status` | integration | `pytest tests/integration/api/test_tasks.py -k filter -x` | ❌ Wave 0 |
| TASK-07 | Envelope stats cover the whole list, unchanged by the filter, `0.0` when empty | integration | `pytest tests/integration/api/test_tasks.py -k statistics -x` | ⚠️ repository leg exists (`test_completion_stats_*`), HTTP leg ❌ |
| TASK-08 | Blank title / over-length / past due date → 422 `validation_error` with `field` | integration | `pytest tests/integration/api/test_tasks.py -k rejects -x` | ⚠️ entity leg exists (`tests/unit/domain/test_task.py`), HTTP leg ❌ |
| D-15 gate | No module under `presentation/api/routers` raises or imports `HTTPException` | architecture | `pytest tests/architecture/test_routers_raise_no_http_exception.py -q --no-cov` | ❌ Wave 0 |
| D-15 gate | `domain`/`application`/`infrastructure` import no fastapi/starlette | architecture | `pytest tests/architecture/test_layer_boundaries.py -q --no-cov` | ✅ (needs the new contract + name update) |
| D-17 | `GET /task-lists` issues the same statement count for 1 and N lists | integration | `pytest tests/integration/api/test_statements.py -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `.venv/bin/pytest tests/unit tests/architecture -q --no-cov` plus
  `make lint && make typecheck && make arch`
- **Per wave merge:** `.venv/bin/pytest` (full suite, coverage gate on)
- **Phase gate:** full suite green, `make docker-test` green (the no-host-setup path, and the run
  that is free of the `.env` artifact above), plus a compose cold-start rehearsal reaching
  `api healthy` with the new seed step in place

### Wave 0 Gaps

- [ ] `tests/integration/conftest.py` — `api_client` fixture (app + `dependency_overrides[get_uow]`
      over the connection-bound `session_factory`) and an actor-override helper
- [ ] `tests/integration/conftest.py` — `statements` fixture (the `before_cursor_execute` recorder)
- [ ] `tests/integration/api/__init__.py` + the three test modules
- [ ] `tests/unit/presentation/test_schemas.py`
- [ ] `tests/architecture/test_routers_raise_no_http_exception.py`
- [ ] `tests/unit/application/fakes.py` — `list_for_owner_with_stats` and the D-13 ordering
- [ ] Framework install: none needed

## Security Domain

`security_enforcement` is not set to `false` in `.planning/config.json`, so this section applies.

### Applicable ASVS Categories

| ASVS category | Applies | Standard control in this phase |
|---------------|---------|-------------------------------|
| V2 Authentication | **no (deferred)** | Phase 5. The D-01 seam is explicitly *not* authentication and the docs must say so in those words (CONTEXT `<specifics>`). |
| V3 Session Management | no | No sessions; stateless JWT arrives in Phase 5 |
| V4 Access Control | **yes** | ADR-008 enforced in the use case, never the router: `visible_task_list` / `visible_task` raise the *not-found* error for an invisible resource. Every verb gets a two-actor test (D-04). |
| V5 Input Validation | **yes** | Pydantic for shape/type at the boundary; domain `require_text` / `require_utc` for policy. `extra="forbid"` on every PATCH and on the status body. Enum-typed query params, so a filter value can never reach SQL as free text. |
| V6 Cryptography | no | No hashing or signing in this phase. The seeded `password_hash` is a deliberately unverifiable placeholder, not a credential. |
| V7 Error Handling & Logging | **yes** | Already built: one translation point, fixed 500 body, no client input echoed back (`test_validation_problem_never_echoes_the_client_input`). New routes must not add a second error shape. |
| V13 API | **yes** | Correct status semantics (201/204/404/409/422), `Location` on create, problem+json everywhere |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard mitigation | Status |
|---------|--------|---------------------|--------|
| IDOR / cross-tenant read via a guessed UUID | Information disclosure | 404 (not 403) for anything the actor cannot see, identical code and body to a genuinely absent resource | Enforced in the use case; D-04 requires a test per verb |
| Existence disclosure through a *different* error code | Information disclosure | A task under a foreign list raises `TaskNotFoundError`, never `TaskListNotFoundError` — the latter would both differ in code and leak a foreign id | The `change_task_status.py` docstring already argues this; the new helpers must copy it |
| SQL injection via a filter value | Tampering | Enum-typed query params + bound parameters; the adapter passes `status.value`, never a string from the URL | Existing adapter behaviour |
| Mass assignment (client sets `status`, `owner_id`, `assignee_id`, `completed_at`) | Elevation of privilege | `extra="forbid"` on every request schema; `status` absent from the task PATCH; `owner_id` and `assignee_id` never appear in a Phase 4 request schema | D-06/D-08 |
| Unbounded listing (`T-3-22`) | Denial of service | Accepted, recorded in ADR-043: work is bounded by the per-list scope and `ix_tasks_task_list_id` | Documented, not re-opened |
| N+1 amplification on the index endpoint | Denial of service | One grouped statement, asserted by the D-17 counter | New |
| The demo seed becoming a live account | Elevation of privilege | `password_hash = "!"` can never verify under Argon2; Phase 5 deletes the row and the seam. Note this explicitly in the ADR. | New — worth a line in `DECISION_LOG.md` |
| Sensitive data in a problem body | Information disclosure | `problem()` emits only translated members; `handle_validation_error` strips `input`, `ctx` and `url` | Existing, already tested |

## Assumptions Log

| # | Claim | Section | Risk if wrong |
|---|-------|---------|---------------|
| A1 | `updated_at` should move on a PATCH whose values equal the current ones | Pitfall 10 | Low — a discretion item; the opposite choice costs a value comparison per field and an extra test |
| A2 | The shared `access.py` helper is preferable to repeating the load-and-authorize block in ten use cases | Code Examples | Low — the alternative (a private function per module, as `change_task_status.py` does today) is equally defensible and arguably more consistent with the existing file |
| A3 | `"demo@taskmanager.local"` and `"!"` are acceptable seed values | Pattern 6 | Low — any non-verifiable hash works; `.local` avoids colliding with a real address in Phase 5's registration tests |
| A4 | `Task.DEFAULT_PRIORITY` as a domain ClassVar imported by the schema is the right single source for the `medium` default | Pitfall 6 | Low — the alternative keeps the default only in the entity and leaves it undocumented in OpenAPI |
| A5 | The `test_get_settings_is_cached` failure is caused solely by the developer's local `.env` and does not reproduce in CI | Environment Availability | Medium — if it also fails in CI the phase gate is blocked and a plan must fix it first. Verifiable in one CI run. |
| A6 | `request.url_for` producing an absolute URL satisfies D-12's "`Location` header naming the new resource's URL" | Pattern 4 | Low — RFC 9110 permits both absolute and relative; a relative path is a one-line change |
| A7 | Two routers (`task_lists.py`, `tasks.py`) rather than one per resource-plus-subresource | Project Structure | Low — a discretion item |

## Open Questions

1. **Does the status endpoint need `task_list_id` in the command?**
   - What we know: D-11 nests it under `{list_id}` and D-14 requires a wrong-list 404 for task
     routes; `ChangeTaskStatusCommand` has no `task_list_id` today.
   - What's unclear: whether the CONTEXT author intended D-14 to cover the status route or only
     TASK-02's GET.
   - Recommendation: apply it to *every* task route including status. A nested path whose parent
     segment is ignored is a real defect, an evaluator can find it in one curl, and the
     consistency argument is stronger than the cost (one DTO field, one comparison, seven test
     call sites).

2. **Should `ListTaskLists` return `CompletionStats` through a tuple or a new value object?**
   - What we know: the port must speak domain types; `Sequence[tuple[TaskList, CompletionStats]]`
     satisfies that and compiles.
   - What's unclear: whether the project's taste prefers a named `TaskListWithStats` frozen
     dataclass in `domain/value_objects/`.
   - Recommendation: the tuple. It introduces no domain concept that only one query needs, and
     the application result DTO (`TaskListResult`) is where the naming belongs.

3. **How much OpenAPI polish belongs in this phase?** (discretion item #6)
   - Recommendation: tags + `summary` + `response_description` on every route, plus a
     `responses={404: …, 409: …, 422: …}` map. Declaring the problem body as a model means adding
     a `ProblemDetail` Pydantic model used *only* for documentation — worthwhile and cheap, but it
     is DOC-04's budget. Do the tags and summaries now; leave the documented error models to
     Phase 7 unless a plan has slack.

4. **Is the pre-existing `test_get_settings_is_cached` failure in scope?**
   - Recommendation: check one CI run first. If CI is green, record it in `AI_WORKFLOW.md` as a
     host-environment artifact and use `make docker-test` for the phase gate. If CI is red, it
     blocks the gate and needs a one-line fix in a Wave 0 task.

## Sources

### Primary (HIGH confidence — executed in this repository on 2026-09-18)

- `.venv/bin/mypy 2.3.1 --strict` — enum-sentinel narrowing (`str | Unset` → `str`) and the
  `arg-type` error when the guard is omitted
- `.venv/bin/python` + `fastapi 0.141.1` / `pydantic 2.13.5` — every PATCH semantics row,
  `extra="forbid"` locs, the sentinel-in-schema OpenAPI leak, 201/`Location`, 204 with and
  without `response_class=Response`, enum query-param 422, `request.url_for` with a router prefix,
  `TaskResponse.model_validate` over a frozen dataclass
- `.venv/bin/python` + `SQLAlchemy 2.0.54` + psycopg 3.3.5 against **PostgreSQL 18.4**
  (`taskmanager_test`) — the grouped statistics query (compiled SQL, one statement for 2 and for 5
  lists, `total=0` for an empty list, `int` counters), `before_cursor_execute` on
  `engine.sync_engine` and `connection.sync_connection`, the full app + `dependency_overrides`
  harness, the savepoint-rollback-on-close finding, the FK ordering finding, and the
  `ON CONFLICT DO NOTHING` seed (3 executions, rowcounts 1/0/0)
- `.venv/bin/lint-imports 2.15` — the proposed D-15 contract reported KEPT against the current
  graph (4 kept, 0 broken)
- `.venv/bin/pytest 9.1.1` — full-suite baseline (`1 failed, 292 passed`, 100% coverage over 731
  statements) and the `--no-cov` subset behaviour
- Source read: `src/taskmanager/**` (all 30 modules), `tests/**` conftests and fakes,
  `migrations/versions/0001_baseline.py`, `docker/entrypoint.sh`, `docker-compose.yml`,
  `Dockerfile`, `.importlinter`, `pytest.ini`, `.flake8`, `Makefile`,
  `.pre-commit-config.yaml`, `.github/workflows/ci.yml`

### Primary (HIGH confidence — project documents)

- `.planning/phases/04-task-lists-tasks/04-CONTEXT.md` — D-01..D-17
- `.planning/REQUIREMENTS.md` — ARC-05, LIST-01..06, TASK-01..08, Out of Scope
- `.planning/ROADMAP.md` §"Phase 4" — the five success criteria
- `DECISION_LOG.md` — ADR-008, ADR-009, ADR-020, ADR-021, ADR-029, ADR-034, ADR-037, ADR-043
- `CLAUDE.md` §"Project Rules"
- `.planning/research/FEATURES.md` §§2–7, `.planning/research/PITFALLS.md` Pitfalls 10–11

### Secondary (MEDIUM-HIGH confidence)

- [CITED: https://fastapi.tiangolo.com/tutorial/body-updates] — `model_dump(exclude_unset=True)` as
  the official partial-update pattern (via Context7 `/websites/fastapi_tiangolo`). This research
  departs from it deliberately: the untyped dict it produces cannot cross into a
  `mypy --strict` application layer, so `model_fields_set` + the typed sentinel is used instead.
- [CITED: https://fastapi.tiangolo.com/advanced/custom-response] — `response_class` documents the
  response in OpenAPI while changing what is returned

### Tertiary (LOW confidence — none)

No claim in this document rests on an unverified web search.

## Metadata

**Confidence breakdown:**

- Existing-code inventory: **HIGH** — every module was read, not inferred
- PATCH sentinel + Pydantic schema design: **HIGH** — both the recommendation and the rejected
  alternative were executed, including the mypy narrowing and the OpenAPI leak
- Grouped statistics query: **HIGH** — compiled and executed against PostgreSQL 18.4
- Integration harness + statement counting: **HIGH** — executed end to end through the real app
- D-15 gates: **HIGH** for the import-linter contract (executed), **MEDIUM-HIGH** for the AST gate
  (prototype executed against a planted violation; the `raise exc` gap is stated rather than hidden)
- Demo-user seed: **HIGH** for the SQL and the table's requirements (executed / migration read),
  **MEDIUM** for the placement argument (a reasoned extension of ADR-037, not an executed proof)
- Discretion recommendations (`updated_at`, module layout, shared access helper, OpenAPI polish):
  **MEDIUM** — judgement calls, flagged in the Assumptions Log

**Research date:** 2026-09-18
**Valid until:** 2026-10-18 — every version is exact-pinned, so nothing here can drift except by a
deliberate dependency bump. Re-verify the `pytest` baseline after any change to `.env`.
