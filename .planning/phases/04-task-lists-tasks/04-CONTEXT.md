# Phase 4: Task Lists & Tasks - Context

**Gathered:** 2026-09-18
**Status:** Ready for planning

<domain>
## Phase Boundary

The brief's mandatory use case 1.a, end to end over HTTP under `/api/v1`: CRUD for task lists,
CRUD for tasks nested inside a list, a dedicated status-change endpoint, and the filtered task
listing that carries the list's completion statistics. Pydantic v2 schemas type every HTTP
boundary in the slice (ARC-05). Requirements: ARC-05, LIST-01..06, TASK-01..08.

Not in this phase: JWT, registration, login, assignment, notifications, the assignee 403 leg
(all Phase 5); pagination, sorting, multi-value filters (v2); the totality audit of tests and
coverage (Phase 6).

</domain>

<decisions>
## Implementation Decisions

### Carried forward (locked earlier, not re-discussed)
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

### Actor identity before authentication
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

### PATCH semantics (lists and tasks)
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

### Response shapes
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

### Proof and quality gates
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

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Scope and requirements
- `.planning/ROADMAP.md` §"Phase 4: Task Lists & Tasks": goal and the five success criteria
- `.planning/REQUIREMENTS.md`: ARC-05, LIST-01..06, TASK-01..08, and the Out of Scope table
  (no PUT, status not writable via PATCH, no `cancelled` status)
- `CLAUDE.md` §"Project Rules": layer order, no `HTTPException` outside presentation, no
  commit in repositories, the `Annotated[T, Depends(...)]` rule, quality gates

### API design research
- `.planning/research/FEATURES.md`: endpoint tree (`/api/v1/task-lists/...`), HTTP status
  table, the completion-percentage envelope and rounding, the 403/404 matrix
- `.planning/research/ARCHITECTURE.md`: layer responsibilities, composition root, router →
  use case → UoW flow
- `.planning/research/PITFALLS.md`: Pitfall 11 (N+1 completion percentage) and the async
  session pitfalls

### Decisions already recorded
- `DECISION_LOG.md`: ADR-008 (404 vs 403), ADR-009 (single SQL aggregate), ADR-020 (DTOs are
  frozen dataclasses), ADR-021/ADR-028 (ValidationError → 422 and its scope), the 03-09
  `Annotated` dependency ADR, ADR-043 (no pagination)
- `.planning/phases/02-domain-error-contract/02-CONTEXT.md`: D-01..D-19 (state machine,
  problem+json shape, identity and time, use-case and DTO shape)
- `.planning/phases/03-persistence-runnable-stack/03-CONTEXT.md`: D-01..D-16 (test isolation,
  entrypoint, constraints, compose layout)

### Code to copy or extend
- `src/taskmanager/application/use_cases/tasks/change_task_status.py`: the reference use case
- `src/taskmanager/application/dto/commands.py`, `src/taskmanager/application/dto/results.py`:
  DTO conventions and `TaskResult.from_entity`
- `src/taskmanager/application/ports/repositories.py`: the port surface. D-10 extends it.
- `src/taskmanager/presentation/api/dependencies.py`: `get_uow` and the `Annotated` alias pattern
- `src/taskmanager/presentation/api/errors/mapping.py`: status table. New leaves resolve by MRO.
- `src/taskmanager/main.py`: `create_app()` composition root, where the routers are included
- `docker/entrypoint.sh`: wait → migrate → exec. D-02's seed step goes after migrate.
- `.importlinter`: existing contracts. D-15 adds one.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ChangeTaskStatus` already implements TASK-05's use case, including the ownership check that
  hides a non-visible task behind `TaskNotFoundError`. Phase 4 mostly needs its router and a
  wrong-list check.
- `TaskRepository.list_for_task_list(task_list_id, *, status, priority)` and
  `completion_stats()` already exist with the AND-filter and aggregate tests from 03-07.
- `TaskListRepository.exists_with_name`, `list_for_owner` and the IntegrityError → 409
  translation (03-06) already exist.
- `Task.create`, `Task.rename`, `Task.reschedule`, `Task.change_status`, `TaskList.create` and
  `TaskList.rename` carry every TASK-08 and LIST rule.
- `CompletionStats.percentage()` is the domain-side percentage. Check that its rounding matches
  D-09's 2 decimals.
- In-memory fakes for every port live under `tests/`, so use-case unit tests need no database.
- `SqlAlchemyUnitOfWork`, `get_uow`, the D-01 rollback fixtures and `migrated_database`
  already exist.

### Established Patterns
- TDD red is captured as an `evidence/` file, never as a separate commit. The mypy pre-commit
  hook refuses imports of modules that don't exist yet (02-01).
- Falsification over assertion: every new gate is shown red with a planted violation (02-06,
  03-06, 03-09).
- Requirement ticks go to the last plan that claims them, each re-verified against a named test.
- `AI_WORKFLOW.md` gains the phase's incident entries, and `DECISION_LOG.md` is append-only.
- The 100% coverage level held so far is a norm, not a requirement. The requirement is 75%, with no
  pragma and no omit.

### Integration Points
- `create_app()` includes the new routers under the `/api/v1` prefix.
- `register_exception_handlers()` already turns every `DomainError` into problem+json. No
  router builds an error body.
- The entrypoint gains the demo-user seed step (D-02). The compose cold-start rehearsal must
  still reach `api healthy`.
- `.importlinter` gains the D-15 contract.

</code_context>

<specifics>
## Specific Ideas

- The actor seam must read honestly in the docs: "Phase 4 runs as a single demo user and
  Phase 5 replaces `get_current_actor` with JWT", not something dressed up as authentication.
- Evaluators probe with curl or Swagger right after `docker compose up`. The seeded demo user
  exists so that `POST /api/v1/task-lists` works on a fresh stack with no setup.

</specifics>

<deferred>
## Deferred Ideas

- JWT replacing the `get_current_actor` body, deleting the demo seed, and adding the assignee
  403 leg: Phase 5.
- Pagination and sorting (API-01), multi-value filters (API-02): v2, to be documented as
  pending in the README.
- A `PUT` alongside `PATCH`: out of scope per REQUIREMENTS.

</deferred>

---

*Phase: 04-task-lists-tasks*
*Context gathered: 2026-09-18*
