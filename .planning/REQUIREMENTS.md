# Requirements: Task Manager API — Crehana Backend Technical Challenge

**Defined:** 2026-09-17
**Core Value:** Every requirement in the challenge PDF is met to the letter and is provable in
under five minutes by an evaluator: `docker compose up`, run the tests, read the docs.

Each requirement cites its origin: **[PDF x.y]** = literal challenge brief item,
**[NL]** = our "next level" layer, **[R]** = derived from research to make a PDF item correct.
**[U]** = added by user decision after v1 was defined, beyond the brief.

## v1 Requirements

### Foundation & Tooling (FND)

- [x] **FND-01**: Project uses Python 3.13 and FastAPI with a `src/taskmanager/` package layout [PDF Requisitos]
- [x] **FND-02**: Dependencies are exact-pinned in `requirements.txt` / `requirements-dev.txt`, installable with plain pip [R]
- [x] **FND-03**: A `.flake8` file configures flake8 (black-compatible: max-line-length 88, `extend-ignore = E203,E701`) and `flake8` passes with zero errors [PDF 4.a, 4.c]
- [x] **FND-04**: black and isort (`profile = black`) are configured and `black --check` / `isort --check` pass [PDF 4.b, 2.f]
- [x] **FND-05**: A `pytest.ini` file holds all pytest configuration (asyncio mode, markers, coverage options, `filterwarnings = error`) [PDF 3.c]
- [x] **FND-06**: Coverage is measured over the real source package (`source` set, tests excluded) and the run fails under 75% [PDF 3.b]
- [x] **FND-07**: mypy runs in strict mode over `src/` and passes [NL]
- [x] **FND-08**: pre-commit hooks run black, isort, flake8 and mypy [NL]
- [x] **FND-09**: A `Makefile` exposes one-word commands: `install`, `lint`, `format`, `typecheck`, `test`, `up`, `down` [NL]
- [x] **FND-10**: GitHub Actions CI runs lint, typecheck, architecture check and tests with the coverage gate against a Postgres service, on every push [NL]
- [x] **FND-11**: Settings are loaded from environment via pydantic-settings; no secret has a hard-coded production default; `.env.example` documents every variable [R]

### Architecture (ARC)

- [x] **ARC-01**: Code is organized in layers `domain`, `application`, `infrastructure`, `presentation` under `src/taskmanager/` [PDF 2.a]
- [x] **ARC-02**: Domain entities and value objects are stdlib dataclasses/Enums; the domain package imports no third-party library [NL, user decision]
- [x] **ARC-03**: import-linter contracts enforce the layer order and forbid fastapi/starlette/sqlalchemy in `domain` and `application`; the check runs inside the pytest suite and in CI [NL]
- [x] **ARC-04**: Every use case is a single-purpose class in `application/` depending only on `typing.Protocol` ports (repositories, UnitOfWork, PasswordHasher, TokenService, EmailNotifier, Clock) [PDF 2.a]
- [x] **ARC-05**: Pydantic v2 models type every HTTP boundary: request/response schemas and settings; application command/result DTOs are frozen dataclasses (ADR-020) [PDF 2.b]
- [x] **ARC-06**: A `DomainError` hierarchy (not found, conflict, business-rule violation, authentication, authorization) carries a stable `code` and details; no `HTTPException` is raised outside `presentation` [PDF 2.c]
- [x] **ARC-07**: One exception-handling point maps `DomainError`, request-validation errors and unexpected errors to RFC 9457 `application/problem+json` responses with a single shape [NL]
- [x] **ARC-08**: Transactions are owned by a UnitOfWork committed explicitly by the use case (never in a `yield` dependency teardown) [R]

### Persistence (DB)

- [x] **DB-01**: Data is stored in PostgreSQL via SQLAlchemy 2.0 async with psycopg 3 [PDF Requisitos]
- [x] **DB-02**: Schema is created and versioned by Alembic migrations; the container applies them on startup [R]
- [x] **DB-03**: ORM models are separate from domain entities with explicit mappers; relationships use `lazy="raise"` [R]
- [x] **DB-04**: Status and priority persist as VARCHAR + CHECK constraints; all timestamps are timezone-aware UTC [R]
- [x] **DB-05**: `task_lists.owner_id` exists from the first migration; deleting a list deletes its tasks [R]

### Task Lists (LIST)

- [x] **LIST-01**: User can create a task list with a name and optional description [PDF 1.a.i]
- [x] **LIST-02**: User can get one of their task lists by id [PDF 1.a.i]
- [x] **LIST-03**: User can list their task lists, each with task counts and completion percentage computed in SQL (no N+1) [PDF 1.a.i]
- [x] **LIST-04**: User can partially update a task list (PATCH) [PDF 1.a.i]
- [x] **LIST-05**: User can delete a task list and gets 204 [PDF 1.a.i]
- [x] **LIST-06**: Creating or renaming a list to a name the same owner already uses is rejected with 409 [PDF 2.d]

### Tasks (TASK)

- [x] **TASK-01**: User can create a task inside a list with title, optional description, priority (`low|medium|high`, default `medium`) and optional due date; new tasks start as `pending` [PDF 1.a.ii]
- [x] **TASK-02**: User can get a task by id within its list; a task id under the wrong list returns 404 [PDF 1.a.ii]
- [x] **TASK-03**: User can partially update a task (PATCH) — title, description, priority, due date; `status` is not writable here [PDF 1.a.ii]
- [x] **TASK-04**: User can delete a task and gets 204 [PDF 1.a.ii]
- [x] **TASK-05**: User can change a task's status through a dedicated endpoint; only valid transitions among `pending`, `in_progress`, `completed` are accepted, invalid ones return 409/422 with a specific error code [PDF 1.a.iii, 2.d]
- [x] **TASK-06**: User can list all tasks of a list filtered by `status` and/or `priority`; invalid filter values return 422 [PDF 1.a.iv]
- [x] **TASK-07**: The task listing response includes `completion_percentage` computed over the whole list (independent of filters) by a single SQL aggregate, plus `total_tasks` and `completed_tasks`; an empty list yields `0.0` [PDF 1.a.iv]
- [x] **TASK-08**: Business validations reject blank titles, over-length fields and a due date in the past at creation [PDF 2.d]

### Authentication (AUTH)

- [x] **AUTH-01**: User can register with email, full name and password; duplicate email returns 409; the password hash is never returned [PDF 1.b.ii]
- [x] **AUTH-02**: User can log in via OAuth2 password flow and receives a JWT access token with expiry; Swagger's "Authorize" button works [PDF 1.b.ii]
- [x] **AUTH-03**: All task-list and task endpoints require a valid token; missing/invalid/expired tokens return 401 in problem+json [PDF 1.b.ii]
- [x] **AUTH-04**: Passwords are hashed with Argon2 (pwdlib) off the event loop; tokens are signed with PyJWT using an env-provided secret and a pinned algorithm; login failures do not reveal whether the email exists [R]
- [x] **AUTH-05**: User can fetch their own profile (`/auth/me`) [R]
- [x] **AUTH-06**: Resources invisible to the caller return 404 for every verb; resources visible but not permitted (assignee attempting owner-only actions) return 403 [PDF 2.d]

### Assignment (ASGN)

- [x] **ASGN-01**: List owner can assign a task to an existing user and unassign it; a non-existent assignee is rejected [PDF 1.b.iii]
- [x] **ASGN-02**: Task responses expose the assignee; an assignee can view the task and change its status but cannot edit or delete it [PDF 1.b.iii]
- [x] **ASGN-03**: User can list users (id, name, email) so an assignee id is discoverable [R]

### Notifications (NOTF)

- [x] **NOTF-01**: Assigning a task sends a simulated invitation email to the assignee through an `EmailNotifier` port, after the transaction commits [PDF 1.b.iv]
- [x] **NOTF-02**: The runtime adapter logs the structured email (to, subject, body) and sends nothing real; an in-memory adapter lets tests assert on sent messages without mocks [PDF 1.b.iv]
- [x] **NOTF-03**: A notifier failure never fails the assignment request [R]

### Testing (TEST)

- [x] **TEST-01**: Unit tests cover domain rules and every use case using in-memory fakes, with no database or HTTP [PDF 2.e, 3.a]
- [x] **TEST-02**: Integration tests exercise every endpoint through HTTP against a real PostgreSQL, isolated per test [PDF 2.e, 3.a]
- [x] **TEST-03**: Total coverage is >= 75% and enforced by `--cov-fail-under=75` locally and in CI [PDF 3.b]
- [x] **TEST-04**: Negative-path tests exist for the error contract, cross-user access (404/403 matrix), invalid transitions and auth failures [NL]
- [x] **TEST-05**: Every test contains meaningful assertions; a deliberate-break spot check is performed and recorded [NL]

### Docker (DOCK)

- [x] **DOCK-01**: A multistage `Dockerfile` builds a slim image that runs the app as a non-root user [PDF 5.a, 2.g]
- [x] **DOCK-02**: `docker-compose.yml` starts API + PostgreSQL with one command; the API waits for a healthy database (`pg_isready -h 127.0.0.1`) and applies migrations [PDF 5.a, 2.g]
- [x] **DOCK-03**: `/health` reports liveness and database readiness and backs the container healthcheck [R]
- [x] **DOCK-04**: The test suite can be run with one documented command without a local Python setup [R]
- [x] **DOCK-05**: A clean-clone rehearsal (fresh clone, `down -v`, `--no-cache` build, follow README verbatim) passes before delivery [NL]

### Documentation (DOC)

- [x] **DOC-01**: `README.md` includes project description, local environment setup, running in Docker, and running the tests [PDF 6]
- [x] **DOC-02**: README also includes an endpoint overview, a 2-minute quickstart walkthrough, a requirement-to-evidence map for the PDF, and a "pending / what I'd do next" section [PDF intro, NL]
- [x] **DOC-03**: `DECISION_LOG.md` records each technical decision as context / options / decision / consequences, including every brief ambiguity resolved [PDF 2.h]
- [x] **DOC-04**: OpenAPI docs are complete: tags, summaries, response models and documented error responses for every route [NL]

### AI Workflow Transparency (AIW)

- [x] **AIW-01**: `AI_WORKFLOW.md` shows, with Mermaid diagrams, the real workflow: brief analysis -> research -> requirements -> roadmap -> per-phase plan/execute/verify -> quality gates [NL]
- [x] **AIW-02**: It states what the human decided versus what was delegated to AI, with every claim traceable to a commit, file or test [NL]
- [x] **AIW-03**: It keeps an honest incident log of AI mistakes and how each was caught, written incrementally during the work, plus a "what I did not do" section [NL]
- [x] **AIW-04**: `CLAUDE.md` holds the architecture and quality rules imposed on the AI; `.planning/` artifacts are committed and consistent with what shipped [NL]
- [ ] **AIW-05**: The project is delivered as a public GitHub repository with atomic, phase-scoped commits and a green CI badge [NL]

### Web UI (UI) — beyond the brief, user decision 2026-09-19

- [x] **UI-01**: A React + Vite + TypeScript SPA lives in `frontend/` and lets a user register, log in and log out against the existing API [U]
- [ ] **UI-02**: User can create, rename and delete task lists and sees each list's completion percentage [U]
- [ ] **UI-03**: User can create, edit and delete tasks, change a task's status, and filter by status and priority while the completion percentage keeps describing the whole list [U]
- [ ] **UI-04**: User can assign and unassign a task from the user directory and see the tasks assigned to them [U]
- [ ] **UI-05**: Every API refusal is rendered from its RFC 9457 body, and a 401 returns the user to the login screen [U]
- [x] **UI-06**: `docker compose up` serves the UI with no second command; the UI reaches the API same-origin through a reverse proxy, so the backend gains no CORS surface (fallback: settings-driven CORS, no wildcard, with an ADR) [U]
- [x] **UI-07**: The frontend is gated by TypeScript strict, eslint and vitest, each behind a `make` target and a CI Node job [U]
- [ ] **UI-08**: README, the clean-clone rehearsal, the documentation gate, DECISION_LOG and AI_WORKFLOW are extended and stay true, including the two reversed positions named by id [U]

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
| ~~Frontend / UI~~ | ~~Backend-only challenge~~ — reversed by user decision 2026-09-19; see UI-01..UI-08 (Phase 8). The brief still asks for none |
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
| FND-08 | Phase 1 | Complete |
| FND-09 | Phase 1 | Complete |
| FND-10 | Phase 1 | Complete |
| FND-11 | Phase 1 | Complete |
| ARC-01 | Phase 1 | Complete |
| ARC-02 | Phase 2 | Complete |
| ARC-03 | Phase 1 | Complete |
| ARC-04 | Phase 2 | Complete |
| ARC-05 | Phase 4 | Complete |
| ARC-06 | Phase 2 | Complete |
| ARC-07 | Phase 2 | Complete |
| ARC-08 | Phase 3 | Complete |
| DB-01 | Phase 3 | Complete |
| DB-02 | Phase 3 | Complete |
| DB-03 | Phase 3 | Complete |
| DB-04 | Phase 3 | Complete |
| DB-05 | Phase 3 | Complete |
| LIST-01 | Phase 4 | Complete |
| LIST-02 | Phase 4 | Complete |
| LIST-03 | Phase 4 | Complete |
| LIST-04 | Phase 4 | Complete |
| LIST-05 | Phase 4 | Complete |
| LIST-06 | Phase 4 | Complete |
| TASK-01 | Phase 4 | Complete |
| TASK-02 | Phase 4 | Complete |
| TASK-03 | Phase 4 | Complete |
| TASK-04 | Phase 4 | Complete |
| TASK-05 | Phase 4 | Complete |
| TASK-06 | Phase 4 | Complete |
| TASK-07 | Phase 4 | Complete |
| TASK-08 | Phase 4 | Complete |
| AUTH-01 | Phase 5 | Complete |
| AUTH-02 | Phase 5 | Complete |
| AUTH-03 | Phase 5 | Complete |
| AUTH-04 | Phase 5 | Complete |
| AUTH-05 | Phase 5 | Complete |
| AUTH-06 | Phase 5 | Complete |
| ASGN-01 | Phase 5 | Complete |
| ASGN-02 | Phase 5 | Complete |
| ASGN-03 | Phase 5 | Complete |
| NOTF-01 | Phase 5 | Complete |
| NOTF-02 | Phase 5 | Complete |
| NOTF-03 | Phase 5 | Complete |
| TEST-01 | Phase 6 | Complete |
| TEST-02 | Phase 6 | Complete |
| TEST-03 | Phase 6 | Complete |
| TEST-04 | Phase 6 | Complete |
| TEST-05 | Phase 6 | Complete |
| DOCK-01 | Phase 1 | Complete |
| DOCK-02 | Phase 3 | Complete |
| DOCK-03 | Phase 3 | Complete |
| DOCK-04 | Phase 1 | Complete |
| DOCK-05 | Phase 7 | Complete (07-05) — `make rehearse` green twice, 161s then 115s, README executed from the clone |
| DOC-01 | Phase 7 | Complete (07-04) — `tests/architecture/test_documentation_claims.py`; `make rehearse` |
| DOC-02 | Phase 7 | Complete (07-04) — `tests/architecture/test_documentation_claims.py`; `make rehearse` |
| DOC-03 | Phase 7 | Complete (07-02) — ADR-009/097/098/069/070, pinned by `AMBIGUITY_ADRS` |
| DOC-04 | Phase 7 | Complete (07-01) — `tests/architecture/test_openapi_completeness.py` |
| AIW-01 | Phase 7 | Complete (07-03) — the mermaid-block floor in `test_documentation_claims.py` |
| AIW-02 | Phase 7 | Complete (07-03) — the phase-coverage check in `test_documentation_claims.py` |
| AIW-03 | Phase 1 | Complete — 52 dated entries; the "What I Did Not Do" body written in 07-03 |
| AIW-04 | Phase 1 | Complete |
| AIW-05 | Phase 7 | Pending |
| UI-01 | Phase 8 | Complete (08-01) — `frontend/src/auth/LoginScreen.tsx`; register, log in and log out, 20 vitest tests |
| UI-02 | Phase 8 | Pending |
| UI-03 | Phase 8 | Pending |
| UI-04 | Phase 8 | Pending |
| UI-05 | Phase 8 | Partial (08-01) — the mechanism exists (`problem.ts`, `ErrorBanner`, the global 401 handler) and is exercised on the auth screen; completed by 08-02's screens |
| UI-06 | Phase 8 | Complete (08-01) — `frontend/nginx.conf` proxies `/api/` to `api:8000`; `docker compose up` serves the SPA on :8080; no CORS header anywhere, `src/taskmanager` unmodified (ADR-107) |
| UI-07 | Phase 8 | Complete (08-01) — `make ui-lint` / `ui-typecheck` / `ui-test`, the CI `frontend` job, and `tests/architecture/test_frontend_gates.py` (ADR-108) |
| UI-08 | Phase 8 | Pending |

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
- **TEST-01..05 were ticked once, in plan 06-04**, each against a named passing test rather than
  against a plan header:
  - **TEST-01** — `tests/architecture/test_use_case_totality.py` (every use case reachable from
    the fakes-based suite, AST-derived) plus the 755-test `make test-unit` slice, which runs with
    no database and no live engine.
  - **TEST-02** — `tests/integration/test_endpoint_totality.py`, which compares the operations
    the run actually requested (recorded by the ASGI wrapper in `tests/integration/conftest.py`)
    with `app.openapi()["paths"]`.
  - **TEST-03** — `tests/architecture/test_coverage_configuration.py` for the configuration, and
    the measured number: `make test` → 1078 passed, 100.00%; `make docker-test` → 1078 passed,
    100.00%. The CI leg is the phase's one manual verification (`06-VALIDATION.md`).
  - **TEST-04** — the transition complement in `tests/integration/api/test_tasks.py` (derived from
    `ALLOWED_TRANSITIONS`), the seeded auth failure modes in
    `tests/integration/api/test_auth.py`, `tests/architecture/test_error_contract_totality.py`,
    and the 19-row `tests/integration/api/test_permission_matrix.py` for the 404/403 matrix.
  - **TEST-05** — `tests/architecture/test_assertion_quality.py` (both halves, with the
    `no_reread` exemption that must keep earning itself) plus `make break-check`, whose five
    deliberate breaks all turn the suite red, recorded in `AI_WORKFLOW.md`.
- **DOCK-01/04** (image + dockerized test command) land in Phase 1; **DOCK-02/03** (full
  startup contract with migrations and `/health` DB readiness) need Alembic and an engine, so
  they land in Phase 3.
- **ARC-04** (ports as Protocols, use-case class shape) is owned by Phase 2 where the ports are
  defined; Phases 4-5 add use cases conforming to it, enforced automatically by ARC-03.

**Coverage:**
- v1 requirements: 69 total, plus 8 [U] requirements added for Phase 8 (77)
- Mapped to phases: 77
- Unmapped: 0 ✓
- Duplicates: 0 ✓

### Phase 4 re-verification (plan 04-12)

The fifteen Phase 4 boxes above were ticked by **plan 04-12 only**, after running the command in
each row and seeing it pass — not inherited from the plan frontmatter that claimed them. Eleven
consecutive Phase 4 plans deferred these ticks to the last claimant, which is the convention
established in plans 02-07 and 03-11. The full output of every command below is in
`.planning/phases/04-task-lists-tasks/evidence/04-12-phase-gate.txt`.

| ID | Command | Collected | A named test that proves it |
|----|---------|-----------|------------------------------|
| ARC-05 | `pytest tests/unit/presentation/test_schemas.py tests/unit/test_app_factory.py` | 55 | `test_every_api_route_declares_a_response_model_or_returns_no_content` |
| LIST-01 | `pytest tests/integration/api/test_task_lists.py -k create` | 4 | `test_create_returns_201_with_a_location_header_and_the_full_representation` |
| LIST-02 | `pytest tests/integration/api/test_task_lists.py -k get` | 3 | `test_get_returns_the_list_with_its_statistics` |
| LIST-03 | `pytest tests/integration/api/test_statements.py -k lists` | 1 | `test_the_task_lists_collection_issues_the_same_statements_for_one_list_and_for_many` |
| LIST-03 | `pytest tests/integration/test_repositories_task_lists.py -k single_statement` | 1 | `test_listing_with_stats_is_a_single_statement` |
| LIST-04 | `pytest tests/integration/api/test_task_lists.py -k patch` | 7 | `test_patch_with_an_explicit_null_description_clears_the_field` |
| LIST-05 | `pytest tests/integration/api/test_task_lists.py -k delete` | 3 | `test_delete_returns_204_with_an_empty_body` |
| LIST-06 | `pytest tests/integration/api/test_task_lists.py -k duplicate` | 2 | `test_renaming_a_list_to_a_name_the_actor_already_uses_is_a_duplicate_409` |
| TASK-01 | `pytest tests/integration/api/test_tasks.py -k create` | 4 | `test_create_returns_201_with_a_location_header` |
| TASK-02 | `pytest tests/integration/api/test_tasks.py -k wrong_list` | 4 | `test_a_get_under_the_wrong_list_is_404_exactly_like_an_absent_task` |
| TASK-03 | `pytest tests/integration/api/test_tasks.py -k status_is_not_writable` | 1 | `test_status_is_not_writable_through_the_generic_patch` |
| TASK-04 | `pytest tests/integration/api/test_tasks.py -k delete` | 2 | `test_delete_returns_204_with_an_empty_body` |
| TASK-05 | `pytest tests/integration/api/test_tasks.py -k status` | 8 | `test_the_status_endpoint_walks_pending_to_in_progress_to_completed` |
| TASK-05 | `pytest tests/unit/application/test_change_task_status.py` | 15 | `test_change_task_status_propagates_a_forbidden_transition` |
| TASK-06 | `pytest tests/integration/api/test_tasks.py -k filter` | 6 | `test_filtering_by_both_applies_the_conjunction` |
| TASK-07 | `pytest tests/integration/api/test_tasks.py -k statistics` | 2 | `test_the_statistics_cover_the_whole_list_whatever_the_filter` |
| TASK-08 | `pytest tests/integration/api/test_tasks.py -k validation_error` | 6 | `test_a_past_due_date_is_a_domain_validation_error` |
| TASK-08 | `pytest tests/unit/domain/test_task.py` | 42 | `test_task_validation_rejects_a_blank_title` |

Every command exited `0` and collected at least one test. A command collecting zero would have
blocked its tick: `pytest` exits `5`, not `0`, when `-k` matches nothing, which is how a
mis-specified selector announces itself rather than passing vacuously.

### Phase 5 re-verification (plan 05-16)

The twelve Phase 5 boxes — AUTH-01..06, ASGN-01..03, NOTF-01..03 — were ticked by **plan 05-16
only**, after running the command in each row and seeing it exit `0` with at least one test
collected. Fifteen consecutive Phase 5 plans deferred these ticks to the last claimant, which is
the convention plans 02-07, 03-11 and 04-12 established. The full output of every command below
is in `.planning/phases/05-auth-assignment-notifications/evidence/05-16-phase-gate.txt`.

| ID | Command | Collected | A named test that proves it |
|----|---------|-----------|------------------------------|
| AUTH-01 | `pytest tests/integration/api/test_auth.py -k register` | 5 | `test_register_answers_201_with_the_profile_and_a_location_header` |
| AUTH-01 | `pytest tests/integration/api/test_auth.py -k duplicate` | 1 | `test_register_with_the_same_address_in_another_case_is_a_duplicate_409` |
| AUTH-02 | `pytest tests/integration/api/test_auth.py -k login` | 4 | `test_login_answers_a_bearer_token_and_the_configured_lifetime` |
| AUTH-02 | `pytest tests/unit/presentation/test_security_scheme.py` | 5 | `test_the_document_declares_the_oauth2_password_scheme` |
| AUTH-03 | `pytest tests/integration/api/test_auth.py -k unauthenticated` | 8 | `test_unauthenticated_requests_are_refused_with_the_one_shared_body[an_expired_token]` |
| AUTH-03 | `pytest tests/integration/api/test_permission_matrix.py -k anonymous` | 20 | `test_the_permission_matrix_answers_what_the_table_promises[08-anonymous-GET-/api/v1/task-lists/{list_id}]` |
| AUTH-04 | `pytest tests/unit/infrastructure/test_tokens.py` | 13 | `test_a_token_that_cannot_be_trusted_is_refused[alg_none]` |
| AUTH-04 | `pytest tests/unit/infrastructure/test_passwords.py` | 10 | `test_hashing_and_verifying_leave_the_event_loop_in_that_order` |
| AUTH-04 | `pytest tests/integration/api/test_auth.py -k indistinguishable` | 1 | `test_login_with_an_unknown_address_and_with_a_wrong_password_are_indistinguishable` |
| AUTH-05 | `pytest tests/integration/api/test_auth.py -k _me` | 2 | `test_get_me_answers_the_callers_own_profile_and_no_stored_hash` |
| AUTH-06 | `pytest tests/integration/api/test_permission_matrix.py` | 79 | `test_the_table_covers_every_operation_the_document_publishes` |
| AUTH-06 | `pytest tests/unit/application/test_access.py` | 22 | `test_owned_task_refuses_the_assignee_with_the_projects_first_403` |
| ASGN-01 | `pytest tests/integration/api/test_assignment.py -k assign` | 25 | `test_the_owner_assigns_a_task_and_the_assignee_id_persists` |
| ASGN-01 | `pytest tests/unit/application/test_unassign_task.py` | 6 | `test_the_owner_clears_the_assignee_and_the_write_is_durable` |
| ASGN-02 | `pytest tests/integration/api/test_assignment.py -k assignee_id` | 3 | `test_the_owner_assigns_a_task_and_the_assignee_id_persists` |
| ASGN-02 | `pytest tests/integration/api/test_permission_matrix.py -k assignee` | 25 | `test_the_permission_matrix_answers_what_the_table_promises[14-assignee-PATCH-/api/v1/task-lists/{list_id}/tasks/{task_id}]` |
| ASGN-03 | `pytest tests/integration/api/test_users.py` | 6 | `test_every_entry_publishes_exactly_the_three_members_in_declaration_order` |
| NOTF-01 | `pytest tests/unit/application/test_assign_task.py -k notifies` | 2 | `test_the_owner_assigns_an_existing_user_and_notifies_them` |
| NOTF-01 | `pytest tests/integration/api/test_assignment.py -k notifies` | 4 | `test_assigning_notifies_the_new_assignee_with_one_structured_record` |
| NOTF-02 | `pytest tests/unit/infrastructure/test_notifier.py` | 7 | `test_the_module_imports_no_mail_library` |
| NOTF-02 | `evidence/05-15-cold-start.txt` | — | `docker compose logs api \| grep -c task_assigned_email` prints `1`, and the line parses through `python3 -m json.tool` carrying `to`, `subject`, `body` and `task_id` |
| NOTF-03 | `pytest tests/unit/application/test_assign_task.py -k notifier_failure` | 1 | `test_a_notifier_failure_leaves_the_assignment_durable` |
| NOTF-03 | `pytest tests/integration/api/test_assignment.py -k notifier_failure` | 1 | `test_a_notifier_failure_leaves_the_assignment_committed` |

Every command exited `0` and collected at least one test. A command collecting zero would have
blocked its tick: `pytest` exits `5`, not `0`, when `-k` matches nothing.

NOTF-02 is the one requirement whose second half is not a test. "The runtime adapter logs the
structured email and sends nothing real" is a claim about a running container, and the evidence
is the cold-start capture: on a volume wiped with `docker compose down -v`, one `grep` over
`docker compose logs api` finds exactly one `task_assigned_email` record. The suite half —
"an in-memory adapter lets tests assert on sent messages without mocks" — is
`FakeEmailNotifier`, used by every assignment unit test, plus `test_notifier.py`'s source scan
proving the runtime adapter imports no mail library at all.

---
*Requirements defined: 2026-09-17*
*Last updated: 2026-09-19 after plan 07-05 task 3: DOCK-05 ticked — `make rehearse` clones the
committed tree, builds with `--no-cache` and executes the README's own fenced blocks in the clone,
green twice (ADR-103). 68/69 complete; the one open is AIW-05, which needs the push and an observed
green CI run*
