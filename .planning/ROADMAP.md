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
- [x] **Phase 5: Auth, Assignment & Notifications** - JWT login, ownership rules, task assignment and the simulated invitation email (completed 2026-09-19)
- [x] **Phase 6: Test Hardening & Coverage** - Tests that actually prove behaviour, with the ≥75% gate genuinely met (completed 2026-09-19)
- [ ] **Phase 7: Documentation & Delivery** - README, DECISION_LOG, AI_WORKFLOW, clean-clone rehearsal and a public repo
- [x] **Phase 8: Web UI** - A small React + Vite SPA in the deliverable, gated like the backend; ran before 07-05's delivery tasks resume (completed 2026-09-19)

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

  1. A user can register (duplicate email → 409, hash never returned), log in through the OAuth2 password flow to receive an expiring JWT, and fetch their own profile at `/auth/me`; and the document Swagger builds its "Authorize" button from declares the OAuth2 password scheme with a `tokenUrl` resolving to the published login route, with every operation either requiring that scheme or being one of the three named open ones — asserted from `app.openapi()` by `tests/unit/presentation/test_security_scheme.py`. *(Amended 2026-09-19 by plan 05-16, following the Phase 2 SC-1, Phase 3 SC-4 and Phase 4 SC-5 precedent. The original wording read "use Swagger's 'Authorize' button successfully". Nobody in this project clicks that button: no human ran the browser flow and no test drives one, so the criterion as written credited an observation that was never made. The replacement names the contract the button reads and the gate that fails when it breaks — which is strictly what was verified, including the falsification in `evidence/05-11-open-route-falsification.txt` where a planted route with no caller parameter was caught by name. The end-to-end token path itself was exercised with `curl` against the running container in `evidence/05-15-cold-start.txt`.)*
  2. Every task-list and task endpoint rejects a missing, malformed or expired token with a 401 problem+json body, and a login with a wrong password is indistinguishable from a login with an unknown email.
  3. Resources the caller cannot see return 404 on every verb, while resources they can see but may not act on return 403 — demonstrated by an assignee who can read a task and change its status but cannot edit or delete it.
  4. A list owner can assign a task to an existing user and unassign it, a non-existent assignee is rejected, task responses expose the assignee, and `GET /users` makes assignee ids discoverable.
  5. Assigning a task produces a simulated invitation email through the `EmailNotifier` port after the transaction commits — the runtime adapter only logs a structured message, the in-memory adapter lets tests assert on it without mocks, and a notifier that raises still leaves the assignment succeeding.

**Plans**: 17 plans (12 waves)

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

- [x] 05-09-PLAN.md — The auth, users and assignee schemas, and D-06/D-08 proven by absence
- [x] 05-10-PLAN.md — The real actor seam, the security providers, and the demo user's deletion

**Wave 6** *(blocked on Wave 5 completion)*

- [x] 05-11-PLAN.md — routers/auth.py, configure_logging in the composition root, and the Authorize-button contract

**Wave 7** *(blocked on Wave 6 completion)*

- [x] 05-12-PLAN.md — routers/users.py, routers/assignments.py, and the 401/403 legs every route now owes

**Wave 8** *(blocked on Wave 7 completion)*

- [x] 05-13-PLAN.md — authenticated_client, and the auth and directory routes over real PostgreSQL

**Wave 9** *(blocked on Wave 8 completion)*

- [x] 05-14-PLAN.md — Assignment and the notification over HTTP, the new statement counts, owner vs assignee

**Wave 10** *(blocked on Wave 9 completion)*

- [x] 05-15-PLAN.md — The 19x4 permission matrix and the cold-start rehearsal on an empty volume

**Wave 11** *(blocked on Wave 10 completion)*

- [x] 05-16-PLAN.md — Phase 5 ADRs, the AI_WORKFLOW entries, the twelve requirement ticks and the full phase gate

**Wave 12** *(gap closure, from 05-VERIFICATION.md)*

- [x] 05-17-PLAN.md — The published placeholder refused at boot, `make env` in place of `cp .env.example .env`, and the four review warnings closed

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

**Plans**: 5 plans (5 waves)

Plans:

**Wave 1**

- [x] 06-01-PLAN.md — The four totality gates, the transition complement, and the two tests that passed for the wrong reason

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 06-02-PLAN.md — The assertion-quality gate, the re-read sweep, and the no_reread exemption that has to justify itself

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 06-03-PLAN.md — `scripts/break-check.sh`, `make break-check`, and the incident entry naming what two breaks did not catch

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 06-04-PLAN.md — The coverage configuration pin, the marker partition, `make test-unit`, the ADRs and the five requirement ticks

**Wave 5** *(gap closure, blocked on Wave 4 completion)*

- [x] 06-05-PLAN.md — The `client.request` blind spot in half (b), the matrix's success-cell body assertions and per-row re-reads, ADR-096 (closes the 06-VERIFICATION gap on SC-3)

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

**Plans**: 5 plans (5 waves)

Plans:

**Wave 1**

- [x] 07-01-PLAN.md — The published error body: one `Problem` component, 69 legs on `application/problem+json`, the described tag table and the completeness gate

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 07-02-PLAN.md — The two missing ambiguity ADRs, the superseding entry for two stale claims, 07-01's ADRs and the curated five-ambiguity block

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 07-03-PLAN.md — `AI_WORKFLOW.md`: three Mermaid diagrams, the Phase 5/6/7 human-AI blocks with commit references, and the "What I Did Not Do" body

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 07-04-PLAN.md — `README.md` in ten sections, the documentation-honesty gate and the Dockerfile `COPY` that gate needs in the container

**Wave 5** *(blocking delivery, blocked on Wave 4 completion)*

- [ ] 07-05-PLAN.md — `make rehearse` executing the README's own commands from a fresh clone, the push, the observed-green CI run and the delivery checkpoints

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8, with one
deliberate exception: **Phase 8 ran before Phase 7 finished.** 07-05 is paused at its task 4
push checkpoint, and the user decided the UI had to be part of what gets pushed, so Phase 8
executed in the gap. The complete phases are 1-6 and 8; Phase 7 resumes at 07-05 task 4.

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation & Quality Gates | 8/8 | Complete   | 2026-09-18 |
| 2. Domain & Error Contract | 7/7 | Complete | 2026-09-18 |
| 3. Persistence & Runnable Stack | 11/11 | Complete | 2026-09-19 |
| 4. Task Lists & Tasks | 12/12 | Complete | 2026-09-19 |
| 5. Auth, Assignment & Notifications | 17/17 | Complete    | 2026-09-19 |
| 6. Test Hardening & Coverage | 5/5 | Complete | 2026-09-19 |
| 7. Documentation & Delivery | 4/5 | In progress | - |
| 8. Web UI | 3/3 | Complete | 2026-09-19 |

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

### Phase 8: Web UI

**Goal**: An evaluator who runs `docker compose up` can also open a browser and drive every brief use case — lists, tasks, status, filters with the completion percentage, login, assignment — through a small web UI, without the UI weakening a single claim the repository makes about itself.
**Depends on**: Phase 7 plans 07-01..07-04 and 07-05 tasks 1-3. **Executes before 07-05 resumes**: 07-05 is paused at its task 4 push checkpoint, and its delivery tasks 4-7 (push, CI run, badge/diagram check, email) run after this phase, so the UI is part of what is delivered.
**Origin**: User decision on 2026-09-19, reversing the "Frontend / UI" Out of Scope row. The brief asks for no UI; this phase is beyond the brief and the documents must say so.
**Requirements**: UI-01, UI-02, UI-03, UI-04, UI-05, UI-06, UI-07, UI-08
**Success Criteria** (what must be TRUE):

  1. `docker compose up` still starts everything with one command, and the UI is reachable in a browser on a documented port. The UI reaches the API **same-origin through the UI container's reverse proxy** (and the Vite dev proxy in development), so the backend gains no CORS surface; if planning finds that unworkable, settings-driven CORS with no wildcard and an ADR is the fallback.
  2. Through the UI a user can register, log in and log out; create, rename and delete task lists; create, edit and delete tasks; change a task's status; filter by status and by priority while the completion percentage keeps describing the whole list; assign and unassign a task from the user directory; and see the tasks assigned to them.
  3. Every refusal the API answers is shown from its RFC 9457 body (`title`/`detail`, keyed on `code`), and a 401 returns the user to the login screen. The UI builds no error text of its own for an API failure.
  4. The frontend has the backend's kind of gates: TypeScript strict, eslint and vitest component/unit tests, each behind a `make` target, each run by CI in a Node job — and added in both places the two-places rule names if it introduces a new command. `src/taskmanager` is not modified unless criterion 1's fallback is taken.
  5. `README.md`, `make rehearse` and `tests/architecture/test_documentation_claims.py` stay true and green: the README says what the UI is, how to open it and that it is beyond the brief; the rehearsal proves the UI answers in the fresh clone; pinned counts are updated in the commit that changes them.
  6. `DECISION_LOG.md` records the stack choice (React + Vite, not Next.js), the same-origin proxy (or CORS), and the reversal of two earlier positions by id — "Frontend / UI" out of scope, and `AI_WORKFLOW.md`'s rejection of a Node toolchain in a Python deliverable. `AI_WORKFLOW.md` gains the Phase 8 human/AI split and a dated incident entry.

**Plans**: 3 plans (3 waves, sequential)

Plans:

**Wave 1**

- [x] 08-01-PLAN.md — The `frontend/` scaffold, the pinned toolchain, the one fetch boundary, the auth screen, the nginx reverse proxy and the `ui` compose service, gated in both places

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 08-02-PLAN.md — The four screens: lists with their completion bars, one list with tasks, status moves and filters, assignment and assigned-to-me

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 08-03-PLAN.md — The documents made true again: the README's UI section, the rehearsal's UI check, the Phase 8 human/AI block and incident entry, the frontend Project Rules, and a tree 07-05 can resume against

**Outcome (2026-09-19): all six criteria met.**

  1. Met. `docker compose up` builds and starts db, api and ui; the UI answers on `http://localhost:8080` and reaches the API same-origin through `frontend/nginx.conf`'s `/api/` proxy. The CORS fallback was **not** taken: `git diff 1dd5af7 -- src/taskmanager` is empty (ADR-107).
  2. Met. All four screens shipped in 08-02 and were driven both by the vitest suite and, once, by hand in a browser: register, log in, log out; create, rename, delete lists; create, edit, delete tasks; the dedicated `/status` endpoint offering only legal moves; both filters with the bar still reading the whole list (ADR-009); assign and unassign from the directory; and assigned-to-me.
  3. Met. Every refusal renders the RFC 9457 body's `detail`, and the global 401 handler clears the session and returns to the login screen — asserted in the suite and observed in the browser with a forged token.
  4. Met. TypeScript strict, eslint and vitest behind `make ui-lint` / `make ui-typecheck` / `make ui-test`, a CI `frontend` job, a pre-commit hook and `tests/architecture/test_frontend_gates.py` (ADR-108). `src/taskmanager` is unmodified.
  5. Met. The README has the UI section, says the brief asks for no UI and gains **no** evidence-map row; `make rehearse` executes two UI commands against the clone's own container; the documentation gate's `PHASES` covers eight phases; the `108 ADRs` count moved in 08-01, the commit that added ADR-105..108.
  6. Met. ADR-105 (inside the deliverable, and the reversal of both positions by id), ADR-106 (React + Vite, not Next.js, no component/state/routing library), ADR-107 (the proxy, not CORS) and ADR-108 (the gates). `AI_WORKFLOW.md` gained the Phase 8 human/AI block and one dated incident entry, and its own Node-toolchain sentence is amended in place.
