# Requirements: Task Manager API — Crehana Backend Technical Challenge

**Defined:** 2026-09-17
**Core Value:** Every requirement in the challenge PDF is met to the letter and is provable in
under five minutes by an evaluator: `docker compose up`, run the tests, read the docs.

Each requirement cites its origin: **[PDF x.y]** = literal challenge brief item,
**[NL]** = our "next level" layer, **[R]** = derived from research to make a PDF item correct.

## v1 Requirements

### Foundation & Tooling (FND)

- [x] **FND-01**: Project uses Python 3.13 and FastAPI with a `src/taskmanager/` package layout [PDF Requisitos]
- [x] **FND-02**: Dependencies are exact-pinned in `requirements.txt` / `requirements-dev.txt`, installable with plain pip [R]
- [x] **FND-03**: A `.flake8` file configures flake8 (black-compatible: max-line-length 88, `extend-ignore = E203,E701`) and `flake8` passes with zero errors [PDF 4.a, 4.c]
- [x] **FND-04**: black and isort (`profile = black`) are configured and `black --check` / `isort --check` pass [PDF 4.b, 2.f]
- [x] **FND-05**: A `pytest.ini` file holds all pytest configuration (asyncio mode, markers, coverage options, `filterwarnings = error`) [PDF 3.c]
- [x] **FND-06**: Coverage is measured over the real source package (`source` set, tests excluded) and the run fails under 75% [PDF 3.b]
- [x] **FND-07**: mypy runs in strict mode over `src/` and passes [NL]
- [ ] **FND-08**: pre-commit hooks run black, isort, flake8 and mypy [NL]
- [ ] **FND-09**: A `Makefile` exposes one-word commands: `install`, `lint`, `format`, `typecheck`, `test`, `up`, `down` [NL]
- [ ] **FND-10**: GitHub Actions CI runs lint, typecheck, architecture check and tests with the coverage gate against a Postgres service, on every push [NL]
- [ ] **FND-11**: Settings are loaded from environment via pydantic-settings; no secret has a hard-coded production default; `.env.example` documents every variable [R]

### Architecture (ARC)

- [x] **ARC-01**: Code is organized in layers `domain`, `application`, `infrastructure`, `presentation` under `src/taskmanager/` [PDF 2.a]
- [ ] **ARC-02**: Domain entities and value objects are stdlib dataclasses/Enums; the domain package imports no third-party library [NL, user decision]
- [ ] **ARC-03**: import-linter contracts enforce the layer order and forbid fastapi/starlette/sqlalchemy in `domain` and `application`; the check runs inside the pytest suite and in CI [NL]
- [ ] **ARC-04**: Every use case is a single-purpose class in `application/` depending only on `typing.Protocol` ports (repositories, UnitOfWork, PasswordHasher, TokenService, EmailNotifier, Clock) [PDF 2.a]
- [ ] **ARC-05**: Pydantic v2 models type every boundary: HTTP request/response schemas, application command/result DTOs, settings [PDF 2.b]
- [ ] **ARC-06**: A `DomainError` hierarchy (not found, conflict, business-rule violation, authentication, authorization) carries a stable `code` and details; no `HTTPException` is raised outside `presentation` [PDF 2.c]
- [ ] **ARC-07**: One exception-handling point maps `DomainError`, request-validation errors and unexpected errors to RFC 9457 `application/problem+json` responses with a single shape [NL]
- [ ] **ARC-08**: Transactions are owned by a UnitOfWork committed explicitly by the use case (never in a `yield` dependency teardown) [R]

### Persistence (DB)

- [ ] **DB-01**: Data is stored in PostgreSQL via SQLAlchemy 2.0 async with psycopg 3 [PDF Requisitos]
- [ ] **DB-02**: Schema is created and versioned by Alembic migrations; the container applies them on startup [R]
- [ ] **DB-03**: ORM models are separate from domain entities with explicit mappers; relationships use `lazy="raise"` [R]
- [ ] **DB-04**: Status and priority persist as VARCHAR + CHECK constraints; all timestamps are timezone-aware UTC [R]
- [ ] **DB-05**: `task_lists.owner_id` exists from the first migration; deleting a list deletes its tasks [R]

### Task Lists (LIST)

- [ ] **LIST-01**: User can create a task list with a name and optional description [PDF 1.a.i]
- [ ] **LIST-02**: User can get one of their task lists by id [PDF 1.a.i]
- [ ] **LIST-03**: User can list their task lists, each with task counts and completion percentage computed in SQL (no N+1) [PDF 1.a.i]
- [ ] **LIST-04**: User can partially update a task list (PATCH) [PDF 1.a.i]
- [ ] **LIST-05**: User can delete a task list and gets 204 [PDF 1.a.i]
- [ ] **LIST-06**: Creating or renaming a list to a name the same owner already uses is rejected with 409 [PDF 2.d]

### Tasks (TASK)

- [ ] **TASK-01**: User can create a task inside a list with title, optional description, priority (`low|medium|high`, default `medium`) and optional due date; new tasks start as `pending` [PDF 1.a.ii]
- [ ] **TASK-02**: User can get a task by id within its list; a task id under the wrong list returns 404 [PDF 1.a.ii]
- [ ] **TASK-03**: User can partially update a task (PATCH) — title, description, priority, due date; `status` is not writable here [PDF 1.a.ii]
- [ ] **TASK-04**: User can delete a task and gets 204 [PDF 1.a.ii]
- [ ] **TASK-05**: User can change a task's status through a dedicated endpoint; only valid transitions among `pending`, `in_progress`, `completed` are accepted, invalid ones return 409/422 with a specific error code [PDF 1.a.iii, 2.d]
- [ ] **TASK-06**: User can list all tasks of a list filtered by `status` and/or `priority`; invalid filter values return 422 [PDF 1.a.iv]
- [ ] **TASK-07**: The task listing response includes `completion_percentage` computed over the whole list (independent of filters) by a single SQL aggregate, plus `total_tasks` and `completed_tasks`; an empty list yields `0.0` [PDF 1.a.iv]
- [ ] **TASK-08**: Business validations reject blank titles, over-length fields and a due date in the past at creation [PDF 2.d]

### Authentication (AUTH)

- [ ] **AUTH-01**: User can register with email, full name and password; duplicate email returns 409; the password hash is never returned [PDF 1.b.ii]
- [ ] **AUTH-02**: User can log in via OAuth2 password flow and receives a JWT access token with expiry; Swagger's "Authorize" button works [PDF 1.b.ii]
- [ ] **AUTH-03**: All task-list and task endpoints require a valid token; missing/invalid/expired tokens return 401 in problem+json [PDF 1.b.ii]
- [ ] **AUTH-04**: Passwords are hashed with Argon2 (pwdlib) off the event loop; tokens are signed with PyJWT using an env-provided secret and a pinned algorithm; login failures do not reveal whether the email exists [R]
- [ ] **AUTH-05**: User can fetch their own profile (`/auth/me`) [R]
- [ ] **AUTH-06**: Resources invisible to the caller return 404 for every verb; resources visible but not permitted (assignee attempting owner-only actions) return 403 [PDF 2.d]

### Assignment (ASGN)

- [ ] **ASGN-01**: List owner can assign a task to an existing user and unassign it; a non-existent assignee is rejected [PDF 1.b.iii]
- [ ] **ASGN-02**: Task responses expose the assignee; an assignee can view the task and change its status but cannot edit or delete it [PDF 1.b.iii]
- [ ] **ASGN-03**: User can list users (id, name, email) so an assignee id is discoverable [R]

### Notifications (NOTF)

- [ ] **NOTF-01**: Assigning a task sends a simulated invitation email to the assignee through an `EmailNotifier` port, after the transaction commits [PDF 1.b.iv]
- [ ] **NOTF-02**: The runtime adapter logs the structured email (to, subject, body) and sends nothing real; an in-memory adapter lets tests assert on sent messages without mocks [PDF 1.b.iv]
- [ ] **NOTF-03**: A notifier failure never fails the assignment request [R]

### Testing (TEST)

- [ ] **TEST-01**: Unit tests cover domain rules and every use case using in-memory fakes, with no database or HTTP [PDF 2.e, 3.a]
- [ ] **TEST-02**: Integration tests exercise every endpoint through HTTP against a real PostgreSQL, isolated per test [PDF 2.e, 3.a]
- [ ] **TEST-03**: Total coverage is >= 75% and enforced by `--cov-fail-under=75` locally and in CI [PDF 3.b]
- [ ] **TEST-04**: Negative-path tests exist for the error contract, cross-user access (404/403 matrix), invalid transitions and auth failures [NL]
- [ ] **TEST-05**: Every test contains meaningful assertions; a deliberate-break spot check is performed and recorded [NL]

### Docker (DOCK)

- [ ] **DOCK-01**: A multistage `Dockerfile` builds a slim image that runs the app as a non-root user [PDF 5.a, 2.g]
- [ ] **DOCK-02**: `docker-compose.yml` starts API + PostgreSQL with one command; the API waits for a healthy database (`pg_isready -h 127.0.0.1`) and applies migrations [PDF 5.a, 2.g]
- [ ] **DOCK-03**: `/health` reports liveness and database readiness and backs the container healthcheck [R]
- [ ] **DOCK-04**: The test suite can be run with one documented command without a local Python setup [R]
- [ ] **DOCK-05**: A clean-clone rehearsal (fresh clone, `down -v`, `--no-cache` build, follow README verbatim) passes before delivery [NL]

### Documentation (DOC)

- [ ] **DOC-01**: `README.md` includes project description, local environment setup, running in Docker, and running the tests [PDF 6]
- [ ] **DOC-02**: README also includes an endpoint overview, a 2-minute quickstart walkthrough, a requirement-to-evidence map for the PDF, and a "pending / what I'd do next" section [PDF intro, NL]
- [ ] **DOC-03**: `DECISION_LOG.md` records each technical decision as context / options / decision / consequences, including every brief ambiguity resolved [PDF 2.h]
- [ ] **DOC-04**: OpenAPI docs are complete: tags, summaries, response models and documented error responses for every route [NL]

### AI Workflow Transparency (AIW)

- [ ] **AIW-01**: `AI_WORKFLOW.md` shows, with Mermaid diagrams, the real workflow: brief analysis -> research -> requirements -> roadmap -> per-phase plan/execute/verify -> quality gates [NL]
- [ ] **AIW-02**: It states what the human decided versus what was delegated to AI, with every claim traceable to a commit, file or test [NL]
- [ ] **AIW-03**: It keeps an honest incident log of AI mistakes and how each was caught, written incrementally during the work, plus a "what I did not do" section [NL]
- [ ] **AIW-04**: `CLAUDE.md` holds the architecture and quality rules imposed on the AI; `.planning/` artifacts are committed and consistent with what shipped [NL]
- [ ] **AIW-05**: The project is delivered as a public GitHub repository with atomic, phase-scoped commits and a green CI badge [NL]

## v2 Requirements

Acknowledged, documented as "pending" in the README, not built.

### API polish

- **API-01**: Pagination and sorting on list endpoints
- **API-02**: Multi-value filters (`?status=pending&status=in_progress`)
- **API-03**: Explicit invitation endpoint independent of assignment

### Auth

- **AUTH-07**: Refresh tokens and token revocation
- **AUTH-08**: Password reset and email verification

## Out of Scope

| Feature | Reason |
|---------|--------|
| Frontend / UI | Backend-only challenge |
| Real email delivery (SMTP/provider) | Brief explicitly asks for a simulation |
| PUT alongside PATCH | Doubles the test surface for no points; documented in DECISION_LOG |
| Status writable through generic PATCH | Would bypass the state machine; the dedicated endpoint is the only door |
| `cancelled` status, integer priorities | Re-open the completion-% definition / known client-bug source |
| List membership / sharing model | "Invitation" is a stateless simulated message that grants nothing |
| Roles and permissions beyond owner/assignee | Not requested |
| Celery / message queues | Over-engineering for a simulated email |
| Soft delete, audit trail | Not requested |
| SQLModel | Fuses ORM and API schema, collapsing the boundary the brief evaluates |
| ruff | Brief mandates flake8; noted in DECISION_LOG as the choice absent that constraint |
| Production deployment, metrics, tracing | Not requested; keeps the project reviewable in minutes |
| HTML page for the AI workflow | User decision: Markdown + Mermaid is enough |

## Traceability

Which phases cover which requirements. Filled in during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| FND-01 | Phase 1 | Complete |
| FND-02 | Phase 1 | Complete |
| FND-03 | Phase 1 | Complete |
| FND-04 | Phase 1 | Complete |
| FND-05 | Phase 1 | Complete |
| FND-06 | Phase 1 | Complete |
| FND-07 | Phase 1 | Complete |
| FND-08 | Phase 1 | Pending |
| FND-09 | Phase 1 | Pending |
| FND-10 | Phase 1 | Pending |
| FND-11 | Phase 1 | Pending |
| ARC-01 | Phase 1 | Complete |
| ARC-02 | Phase 2 | Pending |
| ARC-03 | Phase 1 | Pending |
| ARC-04 | Phase 2 | Pending |
| ARC-05 | Phase 4 | Pending |
| ARC-06 | Phase 2 | Pending |
| ARC-07 | Phase 2 | Pending |
| ARC-08 | Phase 3 | Pending |
| DB-01 | Phase 3 | Pending |
| DB-02 | Phase 3 | Pending |
| DB-03 | Phase 3 | Pending |
| DB-04 | Phase 3 | Pending |
| DB-05 | Phase 3 | Pending |
| LIST-01 | Phase 4 | Pending |
| LIST-02 | Phase 4 | Pending |
| LIST-03 | Phase 4 | Pending |
| LIST-04 | Phase 4 | Pending |
| LIST-05 | Phase 4 | Pending |
| LIST-06 | Phase 4 | Pending |
| TASK-01 | Phase 4 | Pending |
| TASK-02 | Phase 4 | Pending |
| TASK-03 | Phase 4 | Pending |
| TASK-04 | Phase 4 | Pending |
| TASK-05 | Phase 4 | Pending |
| TASK-06 | Phase 4 | Pending |
| TASK-07 | Phase 4 | Pending |
| TASK-08 | Phase 4 | Pending |
| AUTH-01 | Phase 5 | Pending |
| AUTH-02 | Phase 5 | Pending |
| AUTH-03 | Phase 5 | Pending |
| AUTH-04 | Phase 5 | Pending |
| AUTH-05 | Phase 5 | Pending |
| AUTH-06 | Phase 5 | Pending |
| ASGN-01 | Phase 5 | Pending |
| ASGN-02 | Phase 5 | Pending |
| ASGN-03 | Phase 5 | Pending |
| NOTF-01 | Phase 5 | Pending |
| NOTF-02 | Phase 5 | Pending |
| NOTF-03 | Phase 5 | Pending |
| TEST-01 | Phase 6 | Pending |
| TEST-02 | Phase 6 | Pending |
| TEST-03 | Phase 6 | Pending |
| TEST-04 | Phase 6 | Pending |
| TEST-05 | Phase 6 | Pending |
| DOCK-01 | Phase 1 | Pending |
| DOCK-02 | Phase 3 | Pending |
| DOCK-03 | Phase 3 | Pending |
| DOCK-04 | Phase 1 | Pending |
| DOCK-05 | Phase 7 | Pending |
| DOC-01 | Phase 7 | Pending |
| DOC-02 | Phase 7 | Pending |
| DOC-03 | Phase 7 | Pending |
| DOC-04 | Phase 7 | Pending |
| AIW-01 | Phase 7 | Pending |
| AIW-02 | Phase 7 | Pending |
| AIW-03 | Phase 1 | Pending |
| AIW-04 | Phase 1 | Pending |
| AIW-05 | Phase 7 | Pending |

**Per-phase totals:** Phase 1 = 17, Phase 2 = 4, Phase 3 = 8, Phase 4 = 15, Phase 5 = 12,
Phase 6 = 5, Phase 7 = 8.

**Notes on cross-phase requirements:**
- **AIW-03** (incident log) is owned by Phase 1 because the log must open before any code is
  written; every later phase appends a dated entry to it. **AIW-01/02** finalize the document
  in Phase 7.
- **AIW-04** (`CLAUDE.md` + committed `.planning/`) is owned by Phase 1; the "consistent with
  what shipped" check is re-verified during the Phase 7 delivery rehearsal.
- **TEST-01..05** are owned by Phase 6 because they assert *totality* ("every use case",
  "every endpoint", the achieved coverage number). Tests are still written alongside the code
  in Phases 2-5; Phase 6 is where completeness and assertion quality are audited.
- **FND-06** is the coverage *configuration* (Phase 1); **TEST-03** is the coverage *number*
  being met (Phase 6).
- **DOCK-01/04** (image + dockerized test command) land in Phase 1; **DOCK-02/03** (full
  startup contract with migrations and `/health` DB readiness) need Alembic and an engine, so
  they land in Phase 3.
- **ARC-04** (ports as Protocols, use-case class shape) is owned by Phase 2 where the ports are
  defined; Phases 4-5 add use cases conforming to it, enforced automatically by ARC-03.

**Coverage:**
- v1 requirements: 69 total
- Mapped to phases: 69
- Unmapped: 0 ✓
- Duplicates: 0 ✓

---
*Requirements defined: 2026-09-17*
*Last updated: 2026-09-17 after roadmap creation (7 phases, 69/69 mapped)*
