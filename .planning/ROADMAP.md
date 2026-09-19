# Roadmap: Task Manager API — Crehana Backend Technical Challenge

## Overview

The project starts by making quality unavoidable: before a single line of application code
exists, the repository has its layer packages, its literal tooling files (`pytest.ini`,
`.flake8`), formatters, strict mypy, import-linter contracts, a Makefile, GitHub Actions CI and
a multistage Dockerfile. Only then does the code arrive, strictly bottom-up: a framework-free
domain with its `DomainError` hierarchy and the single RFC 9457 exception handler; then the
PostgreSQL persistence layer with Alembic migrations, the UnitOfWork and a working
`docker compose up`; then the first full vertical slice — task lists and tasks with filtering
and the SQL-aggregate completion percentage — which proves the wiring pattern end to end.
With the pattern proven, JWT auth, assignment and the simulated notification are repetition of
a known shape rather than new risk. The last two phases turn a working API into a deliverable:
an assertion audit that makes the ≥75% coverage number mean something, then the documentation
set, a rehearsed clean-clone run and a public repository with a green CI badge. An honest
AI incident log is appended at the end of every phase, so `AI_WORKFLOW.md` is assembled from
evidence rather than reconstructed at the end.

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Foundation & Quality Gates** - Tooling, layer skeleton, enforced boundaries and CI exist before any application code (completed 2026-09-18)
- [x] **Phase 2: Domain & Error Contract** - Framework-free entities, ports and the single RFC 9457 error contract (completed 2026-09-18)
- [x] **Phase 3: Persistence & Runnable Stack** - PostgreSQL, Alembic, UnitOfWork and a one-command `docker compose up`
- [x] **Phase 4: Task Lists & Tasks** - The full brief 1.a vertical slice: CRUD, status changes, filters, completion percentage
- [ ] **Phase 5: Auth, Assignment & Notifications** - JWT login, ownership rules, task assignment and the simulated invitation email
- [ ] **Phase 6: Test Hardening & Coverage** - Tests that actually prove behaviour, with the ≥75% gate genuinely met
- [ ] **Phase 7: Documentation & Delivery** - README, DECISION_LOG, AI_WORKFLOW, clean-clone rehearsal and a public repo

## Phase Details

### Phase 1: Foundation & Quality Gates

**Goal**: Every quality gate the project will be judged by is automated and passing on an empty codebase, so no later code can be written outside the rules.
**Depends on**: Nothing (first phase)
**Requirements**: FND-01, FND-02, FND-03, FND-04, FND-05, FND-06, FND-07, FND-08, FND-09, FND-10, FND-11, ARC-01, ARC-03, DOCK-01, DOCK-04, AIW-03, AIW-04
**Success Criteria** (what must be TRUE):

  1. `make lint`, `make format`, `make typecheck` and `make test` all pass on a clean checkout, driven by the literal files `.flake8`, `pytest.ini` and `pyproject.toml`, with coverage scoped to `src/taskmanager` and failing under 75%.
  2. The four layer packages (`domain`, `application`, `infrastructure`, `presentation`) exist under `src/taskmanager/` and an import-linter contract, run inside the pytest suite, fails when a forbidden import is deliberately added and passes when it is removed.
  3. A push to GitHub triggers a CI run that executes lint, typecheck, architecture check and tests against a Postgres service and reports green.
  4. `docker build` produces an image that runs as a non-root user, and a single documented command runs the test suite with no Python installed on the host.
  5. `CLAUDE.md` states the architecture and quality rules for the AI, and `AI_WORKFLOW.md` exists with its section skeleton and a dated incident log that already has its first real entry.

**Plans**: 8 plans (6 waves)

Plans:
**Wave 1**

- [x] 01-01-PLAN.md — Packaging skeleton, pinned dependencies and every gate configuration file

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 01-02-PLAN.md — Settings module, app factory and the six tests that make 75% honest (+ coverage red/green)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 01-03-PLAN.md — import-linter contracts as a real pytest test (+ architecture red/green)

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 01-04-PLAN.md — pre-commit hooks and the one-word Makefile targets
- [x] 01-05-PLAN.md — Multistage non-root Dockerfile and the GitHub Actions CI workflow

**Wave 5** *(blocked on Wave 4 completion)*

- [x] 01-06-PLAN.md — CLAUDE.md project rules and DECISION_LOG.md in ADR style
- [x] 01-07-PLAN.md — AI_WORKFLOW.md skeleton and incident log opened with real incidents

**Wave 6** *(blocked on Wave 5 completion)*

- [x] 01-08-PLAN.md — Full phase gate run and the public GitHub repository checkpoint

Notes: this phase also locks in the decisions the research flagged as conflicts (Python 3.13,
`src/taskmanager` layout, RFC 9457, psycopg 3, Alembic, `postgres:18-alpine`,
`asyncio_default_fixture_loop_scope = function`) so nothing downstream is written against an
unstable choice. The `AI_WORKFLOW.md` incident log opened here is appended to at the end of
every subsequent phase.

### Phase 2: Domain & Error Contract

**Goal**: The business rules and the API's error shape exist as stable, framework-free contracts that every later layer is written against.
**Depends on**: Phase 1
**Requirements**: ARC-02, ARC-04, ARC-06, ARC-07
**Success Criteria** (what must be TRUE):

  1. `TaskList`, `Task` and `User` entities plus `TaskStatus`/`TaskPriority` enums are stdlib dataclasses/Enums, and `tests/architecture/test_domain_is_stdlib_only.py` proves the `domain` package imports no third-party library by checking every import root against `sys.stdlib_module_names` — something the enumerated import-linter contract cannot do (ADR-022).
  2. A closed `DomainError` hierarchy (not found, conflict, business-rule violation, authentication, authorization) carries a stable `code` and details, and domain unit tests show an invalid status transition raising the specific error rather than a generic exception.
  3. Every application port (`TaskRepository`, `TaskListRepository`, `UserRepository`, `UnitOfWork`, `PasswordHasher`, `TokenService`, `EmailNotifier`, `Clock`) exists as a `typing.Protocol` with no implementation, and the use-case class shape is fixed and documented.
  4. A single exception-handling point converts any `DomainError`, any request-validation error and any unexpected error into an `application/problem+json` body with one consistent RFC 9457 shape, proven by tests against a throwaway probe route — before any real router exists.

**Plans**: 7 plans (6 waves)

Plans:
**Wave 1**

- [x] 02-01-PLAN.md — TaskStatus/TaskPriority StrEnums, the D-01 transition table and CompletionStats

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 02-02-PLAN.md — The closed DomainError hierarchy: stable codes, structured details, pickle-safe base

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 02-03-PLAN.md — Task, TaskList and User entities plus the task state machine and the shared validation guards
- [x] 02-04-PLAN.md — The single RFC 9457 exception-handling point, wired into create_app() and proven by a probe router

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 02-05-PLAN.md — The eight typing.Protocol ports, the frozen-dataclass DTO conventions and the ChangeTaskStatus reference use case

**Wave 5** *(blocked on Wave 4 completion)*

- [x] 02-06-PLAN.md — The AST proof that the domain is stdlib-only, its red/green evidence, and ADR-020/021/022

**Wave 6** *(blocked on Wave 5 completion)*

- [x] 02-07-PLAN.md — Reconcile ARC-05, ROADMAP SC-5, .importlinter and CLAUDE.md with ADR-020; append the Phase 2 AI_WORKFLOW record

### Phase 3: Persistence & Runnable Stack

**Goal**: The application talks to a real PostgreSQL through mapped repositories and an explicit transaction boundary, and an evaluator can start the whole stack with one command.
**Depends on**: Phase 2
**Requirements**: DB-01, DB-02, DB-03, DB-04, DB-05, ARC-08, DOCK-02, DOCK-03
**Success Criteria** (what must be TRUE):

  1. `docker compose up` on an empty volume starts PostgreSQL and the API, the API waits for a genuinely ready database, applies Alembic migrations automatically, and `GET /health` returns liveness plus database readiness and backs the container healthcheck.
  2. SQLAlchemy 2.0 async ORM models are separate from the domain entities, relationships use `lazy="raise"`, and repositories return domain objects only — a test that reads an entity outside the session never raises `MissingGreenlet`.
  3. The Alembic baseline migration creates the schema with `task_lists.owner_id`, VARCHAR + CHECK constraints for status and priority, timezone-aware UTC timestamps, and deleting a list removes its tasks.
  4. The use case owns the transaction: a UnitOfWork commits exactly once on success and rolls back on a raised `DomainError`, and no `.commit()` call exists anywhere under `infrastructure/repositories/`.
  5. Integration tests run against real PostgreSQL with per-test isolation, and the full gate (lint, typecheck, architecture, tests) is green.

**Plans**: 11 plans (9 waves)

Plans:
**Wave 1**

- [x] 03-01-PLAN.md — ORM base, D-12 naming convention, the three row classes, and the case-sensitivity reconciliation

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 03-02-PLAN.md — Alembic wiring, the 0001 baseline migration, the compose db service and the initdb script
- [x] 03-03-PLAN.md — TEST_DATABASE_URL on Settings and .env.example, the URL derivation, and SystemClock
- [x] 03-04-PLAN.md — Explicit ORM/entity mappers and the IntegrityError inspection (WR-05 settled)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 03-05-PLAN.md — The integration fixtures (D-01..D-04) plus the migration, schema and constraint proofs

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 03-06-PLAN.md — The task-list and user adapters and the SC-4 no-commit gate

**Wave 5** *(blocked on Wave 4 completion)*

- [x] 03-07-PLAN.md — The task adapter: CRUD, SQL filters and the COUNT(*) FILTER aggregate

**Wave 6** *(blocked on Wave 5 completion)*

- [x] 03-08-PLAN.md — Engine factory, SqlAlchemyUnitOfWork and the four transaction proofs

**Wave 7** *(blocked on Wave 6 completion)*

- [x] 03-09-PLAN.md — __version__, the FastAPI dependencies, GET /health and the wired composition root

**Wave 8** *(blocked on Wave 7 completion)*

- [x] 03-10-PLAN.md — Container entrypoint, Dockerfile COPY/ENTRYPOINT/HEALTHCHECK, compose api+test, Makefile

**Wave 9** *(blocked on Wave 8 completion)*

- [x] 03-11-PLAN.md — Phase 3 ADRs, the AI_WORKFLOW entry and the full phase gate

### Phase 4: Task Lists & Tasks

**Goal**: Everything the challenge brief lists as a mandatory use case works end to end over HTTP.
**Depends on**: Phase 3
**Requirements**: ARC-05, LIST-01, LIST-02, LIST-03, LIST-04, LIST-05, LIST-06, TASK-01, TASK-02, TASK-03, TASK-04, TASK-05, TASK-06, TASK-07, TASK-08
**Success Criteria** (what must be TRUE):

  1. A caller can create, read, partially update (PATCH) and delete a task list, gets 204 on delete, and gets a 409 problem+json response when reusing a list name they already own.
  2. A caller can create, read, PATCH and delete a task inside a list; a task id requested under the wrong list returns 404; blank titles, over-length fields and past due dates are rejected with a specific error code.
  3. A dedicated status endpoint moves a task through `pending` → `in_progress` → `completed`, and an invalid transition returns a problem+json body naming the transition rather than a generic error; `status` cannot be changed through the generic PATCH.
  4. Listing a list's tasks filtered by `status` and/or `priority` returns only matching tasks, rejects invalid filter values with 422, and always reports `completion_percentage`, `total_tasks` and `completed_tasks` for the whole list — unchanged by the filter, `0.0` when empty, and produced by a single SQL aggregate.
  5. Pydantic v2 models type every HTTP boundary crossed in this slice (request and response schemas), application command/result DTOs are frozen dataclasses per ADR-020, and no router raises **or imports** `HTTPException` — enforced by `tests/architecture/test_routers_raise_no_http_exception.py` — while no layer below `presentation` imports `fastapi` or `starlette` at all, enforced by the `no-http-below-presentation` contract in `.importlinter` (ADR-051). *(Amended 2026-09-19 by plan 04-12, following the Phase 2 SC-1 and Phase 3 SC-4 precedent. The original wording read "no router imports SQLAlchemy or raises `HTTPException` for a business failure". The SQLAlchemy half is true of both routers by inspection — neither names it — but nothing gates it, and `presentation` as a whole deliberately does import SQLAlchemy in `health.py` and `dependencies.py`, so the criterion as written credited a gate that does not exist. The replacement names only what a failing command can prove, and is strictly stronger about `HTTPException`: the shipped gate refuses the **import** as well as the raise.)*

**Plans**: 12 plans (7 waves)

Plans:
**Wave 1**

- [x] 04-01-PLAN.md — Hermetic settings test, the four domain mutators and the typed Unset sentinel
- [x] 04-02-PLAN.md — list_for_owner_with_stats across port/fake/adapter, the grouped LIST-03 statement, and D-15's import-linter contract
- [x] 04-03-PLAN.md — ChangeTaskStatusCommand gains task_list_id (D-14) and the shared access.py guard

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 04-04-PLAN.md — The ten Phase 4 commands and the TaskListResult / TaskCollectionResult DTOs

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 04-05-PLAN.md — The five task-list use cases and their two-actor unit proofs
- [x] 04-06-PLAN.md — The five task use cases, the filter conjunction and the D-07 overdue rule
- [x] 04-07-PLAN.md — The actor seam, the Clock provider and every Pydantic request/response schema

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 04-08-PLAN.md — The two routers, the composition-root wiring and D-15's AST gate

**Wave 5** *(blocked on Wave 4 completion)*

- [x] 04-09-PLAN.md — The HTTP integration harness and the task-list routes over real PostgreSQL
- [x] 04-11-PLAN.md — The idempotent demo-user seed and the cold-start rehearsal

**Wave 6** *(blocked on Wave 5 completion)*

- [x] 04-10-PLAN.md — The task routes over HTTP and the D-17 no-N+1 statement counter

**Wave 7** *(blocked on Wave 6 completion)*

- [x] 04-12-PLAN.md — Phase 4 ADRs, the AI_WORKFLOW entries, the fifteen requirement ticks and the full phase gate

### Phase 5: Auth, Assignment & Notifications

**Goal**: The API knows who is calling, enforces what they may do, and delivers all three bonus use cases from the brief.
**Depends on**: Phase 4
**Requirements**: AUTH-01, AUTH-02, AUTH-03, AUTH-04, AUTH-05, AUTH-06, ASGN-01, ASGN-02, ASGN-03, NOTF-01, NOTF-02, NOTF-03
**Success Criteria** (what must be TRUE):

  1. A user can register (duplicate email → 409, hash never returned), log in through the OAuth2 password flow to receive an expiring JWT, use Swagger's "Authorize" button successfully, and fetch their own profile at `/auth/me`.
  2. Every task-list and task endpoint rejects a missing, malformed or expired token with a 401 problem+json body, and a login with a wrong password is indistinguishable from a login with an unknown email.
  3. Resources the caller cannot see return 404 on every verb, while resources they can see but may not act on return 403 — demonstrated by an assignee who can read a task and change its status but cannot edit or delete it.
  4. A list owner can assign a task to an existing user and unassign it, a non-existent assignee is rejected, task responses expose the assignee, and `GET /users` makes assignee ids discoverable.
  5. Assigning a task produces a simulated invitation email through the `EmailNotifier` port after the transaction commits — the runtime adapter only logs a structured message, the in-memory adapter lets tests assert on it without mocks, and a notifier that raises still leaves the assignment succeeding.

**Plans**: 16 plans (11 waves)

Plans:
**Wave 1**

- [x] 05-01-PLAN.md — require_password, Task.assign/unassign and the HS256 key floor at 32
- [x] 05-02-PLAN.md — The two port extensions, the assignee query, and the fakes brought back into line
- [x] 05-04-PLAN.md — access.py gains owned_task and the assignee short-circuit; the 04-03 test flips back

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 05-03-PLAN.md — users.full_name end to end and the 0002 revision with ix_tasks_assignee_id
- [x] 05-05-PLAN.md — PwdlibPasswordHasher, JwtTokenService and the typed SecurityResources container

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 05-06-PLAN.md — JSON logging that is actually emitted, and the LoggingEmailNotifier
- [x] 05-07-PLAN.md — RegisterUser, AuthenticateActor, GetProfile and the login that says nothing

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 05-08-PLAN.md — AssignTask, UnassignTask, ListUsers, ListAssignedTasks and the post-commit notification

**Wave 5** *(blocked on Wave 4 completion)*

- [ ] 05-09-PLAN.md — The auth, users and assignee schemas, and D-06/D-08 proven by absence
- [x] 05-10-PLAN.md — The real actor seam, the security providers, and the demo user's deletion

**Wave 6** *(blocked on Wave 5 completion)*

- [ ] 05-11-PLAN.md — routers/auth.py, configure_logging in the composition root, and the Authorize-button contract

**Wave 7** *(blocked on Wave 6 completion)*

- [ ] 05-12-PLAN.md — routers/users.py, routers/assignments.py, and the 401/403 legs every route now owes

**Wave 8** *(blocked on Wave 7 completion)*

- [ ] 05-13-PLAN.md — authenticated_client, and the auth and directory routes over real PostgreSQL

**Wave 9** *(blocked on Wave 8 completion)*

- [ ] 05-14-PLAN.md — Assignment and the notification over HTTP, the new statement counts, owner vs assignee

**Wave 10** *(blocked on Wave 9 completion)*

- [ ] 05-15-PLAN.md — The 19x4 permission matrix and the cold-start rehearsal on an empty volume

**Wave 11** *(blocked on Wave 10 completion)*

- [ ] 05-16-PLAN.md — Phase 5 ADRs, the AI_WORKFLOW entries, the twelve requirement ticks and the full phase gate

### Phase 6: Test Hardening & Coverage

**Goal**: The test suite proves the API behaves correctly rather than merely exercising it, and the coverage number is honest.
**Depends on**: Phase 5
**Requirements**: TEST-01, TEST-02, TEST-03, TEST-04, TEST-05
**Success Criteria** (what must be TRUE):

  1. Every domain rule and every use case has a unit test that runs against in-memory fakes with no database and no HTTP, and every endpoint has an integration test that goes through HTTP against real PostgreSQL with per-test isolation.
  2. Negative-path tests exist and pass for the RFC 9457 error contract, the full cross-user 404/403 matrix, every invalid status transition, and each authentication failure mode.
  3. Every test asserts on response bodies (not just status codes), and every mutating test re-reads through the API to confirm the change persisted.
  4. A deliberate-break spot check — inverting the completion-percentage formula — turns the suite red, and the episode is recorded in `AI_WORKFLOW.md`.
  5. `--cov-fail-under=75` passes locally and in CI with coverage measured over `src/taskmanager` only, with tests excluded from the denominator.

**Plans**: TBD

### Phase 7: Documentation & Delivery

**Goal**: An evaluator who has never seen the project can clone it, run it, and verify every brief requirement in under five minutes.
**Depends on**: Phase 6
**Requirements**: DOC-01, DOC-02, DOC-03, DOC-04, DOCK-05, AIW-01, AIW-02, AIW-05
**Success Criteria** (what must be TRUE):

  1. `README.md` covers project description, local setup, running in Docker and running the tests, plus an endpoint overview, a 2-minute quickstart walkthrough, a requirement-to-evidence map for the PDF, and a "pending / what I'd do next" section.
  2. `DECISION_LOG.md` records every technical decision and every brief ambiguity (completion-percentage scope, allowed statuses and transitions, priority values, who may be assigned, what triggers the invitation) as context / options / decision / consequences.
  3. `/docs` shows tags, summaries, response models and documented error responses for every route.
  4. A clean-clone rehearsal — fresh clone into an empty directory, `docker compose down -v`, `--no-cache` build, README followed verbatim — reaches a working API and a green test run with no undocumented step. This is blocking: delivery does not happen until it passes.
  5. `AI_WORKFLOW.md` is finalized with Mermaid diagrams of the real workflow, an explicit human-decided vs AI-delegated split where every claim points at a commit, file or test, the incident log accumulated since Phase 1 with at least three real mistakes, and a "what I did not do" section.
  6. The project is public on GitHub with atomic, phase-scoped commits and a green CI badge in the README.

**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation & Quality Gates | 8/8 | Complete   | 2026-09-18 |
| 2. Domain & Error Contract | 7/7 | Complete | 2026-09-18 |
| 3. Persistence & Runnable Stack | 11/11 | Complete | 2026-09-19 |
| 4. Task Lists & Tasks | 12/12 | Complete | 2026-09-19 |
| 5. Auth, Assignment & Notifications | 9/16 | In Progress | - |
| 6. Test Hardening & Coverage | 0/TBD | Not started | - |
| 7. Documentation & Delivery | 0/TBD | Not started | - |

## Standing Rules

These apply to every phase and are not repeated in each phase's criteria:

- A phase is not complete until `make lint`, `make typecheck` and `make test` (including the
  architecture contract and the coverage gate) all run green.

- Every phase ends by appending a dated entry to the `AI_WORKFLOW.md` incident log — what the
  human decided, what was delegated, and any AI mistake caught and how.

- Commits are atomic and phase-scoped, in English, with no AI co-author attribution lines.
- Research flags: Phase 3 (async session lifecycle, transactional fixtures, Alembic `env.py`)
  and Phase 5 (JWT/hashing libraries, the 403-vs-404 matrix) warrant
  `/gsd:plan-phase --research-phase`.
