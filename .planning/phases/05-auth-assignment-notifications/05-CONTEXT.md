# Phase 5: Auth, Assignment & Notifications - Context

**Gathered:** 2026-09-19
**Status:** Ready for planning

<domain>
## Phase Boundary

The API learns who is calling and enforces what they may do, and it delivers the brief's three
bonus use cases (PDF 1.b): JWT login protecting the endpoints, task assignment, and a simulated
invitation email.

Concretely: register, log in through the OAuth2 password flow, `/auth/me`, a real
`get_current_actor` that replaces the Phase 4 seam, the ADR-008 404/403 split with the assignee
as the first "visible but not permitted" role, owner-only assign/unassign, `GET /users`, and an
`EmailNotifier` call after the transaction commits. Requirements: AUTH-01..06, ASGN-01..03,
NOTF-01..03.

Not in this phase: refresh tokens and revocation (AUTH-07), password reset and email
verification (AUTH-08), roles beyond owner/assignee, real email delivery, pagination.

</domain>

<decisions>
## Implementation Decisions

### Carried forward (locked earlier, not re-discussed)
- Libraries are fixed by the stack research in `CLAUDE.md`: PyJWT (HS256, pinned algorithm, never
  python-jose), `pwdlib[argon2]` (never passlib) with hashing run off the event loop (AUTH-04),
  `OAuth2PasswordRequestForm` + `python-multipart` for login, `email-validator` behind `EmailStr`.
- `JWT_SECRET`, `JWT_ALGORITHM` and `JWT_EXPIRE_MINUTES` already exist in `.env.example` with no
  default in code. Every setting is read through `taskmanager.infrastructure.config.settings`.
- Phase 5 replaces **only the body** of `get_current_actor` (Phase 4 D-01, ADR-044) and deletes
  the demo seed step from `docker/entrypoint.sh` together with the `DEMO_USER_ID` constant
  (Phase 4 D-02/D-03, ADR-045). No router, schema or use-case signature changes because auth
  arrived: every command already starts with `actor_id: UUID`.
- ADR-008: invisible → 404, visible but forbidden → 403. The rule lives in one module,
  `application/use_cases/access.py` (ADR-055). Phase 4 deliberately inverted the assignee test in
  `test_change_task_status.py` (04-03); Phase 5 flips it back.
- The error contract is already wired: `AuthenticationError` → 401 with
  `WWW-Authenticate: Bearer`, `AuthorizationError` → 403, `EmailAlreadyRegisteredError` → 409,
  `UserNotFoundError` → 404, all through the single RFC 9457 handler. No handler builds an error
  body by hand and no router raises or imports `HTTPException` (ADR-051).
- The ports already exist and keep their shape unless research proves a need:
  `PasswordHasher.hash/verify`, `TokenService.issue_access_token/decode`,
  `EmailNotifier.send_task_assigned(*, recipient_email, task_title, task_id)`,
  `UserRepository.get/get_by_email/add/list_all`. Adapters arrive in this phase.
- A use case is one class with `execute(command) -> result`; commands and results are frozen
  slotted dataclasses (ADR-020); dependencies are `Annotated[T, Depends(provider)]` (ADR-034);
  the use case commits through the `UnitOfWork`, repositories never do.
- Collections are ordered by `created_at`, then `id`, with no pagination (ADR-043).
- **Known gap, not a choice:** `User` has no `full_name` — not in the entity, the ORM model or
  `0001_baseline`. AUTH-01 and ASGN-03 require it, so this phase owns a `0002` Alembic revision
  (constraint names spelled as literals per ADR-025, constants in `constraints.py`) plus the
  entity, mapper and repository changes.

### Assignee visibility matrix
- **D-01:** An assignee who does not own the list can see **only the tasks assigned to them**.
  The parent list stays invisible: `GET /task-lists/{id}` and `GET /task-lists/{id}/tasks` answer
  404 for them, and `GET /task-lists` remains strictly "lists I own" with its one-statement
  guarantee (ADR-054) untouched. The assignee still addresses their task through the nested URL
  (`/task-lists/{l}/tasks/{t}`), which answers 200 for them even though the list itself is 404.
- **D-02:** Discovery is one new flat, read-only route: **`GET /api/v1/tasks/assigned-to-me`**,
  returning the caller's assigned tasks (each item carries `task_list_id` so the nested URLs can
  be built), ordered by `created_at`, `id`. It is the only new collection in this phase besides
  `GET /users`.
- **D-03:** On a task assigned to them, an assignee gets: `GET` 200, `PATCH .../status` 200,
  generic `PATCH` **403**, `DELETE` **403**, `PUT`/`DELETE .../assignee` **403**. Everything on
  tasks and lists they cannot see stays 404, and `POST` of a new task into the invisible list
  stays the list-shaped 404 (04-06). An assignee may **not** unassign themselves — ASGN-01 says
  the list owner unassigns.
- **D-04:** The matrix is proven by **one parametrized test over the real HTTP harness**: rows
  are every route, columns are owner / assignee / stranger / anonymous, each cell is the expected
  status (200/201/204, 403, 404, 401). A missing cell must be visible in the table. The same
  table is reused as documentation in Phase 7. Per-role unit tests of `access.py` with the fakes
  are still expected (they are how the rule is developed), but the HTTP table is the contract.

### Assignment API shape
- **D-05:** Assignment has its own door, mirroring ADR-048's status endpoint:
  **`PUT /api/v1/task-lists/{l}/tasks/{t}/assignee`** with body `{"assignee_id": "<uuid>"}`
  (`extra="forbid"`) assigns, **`DELETE`** on the same URL unassigns. Both return 200 with the
  full `TaskResponse` (which now exposes `assignee_id`, ASGN-02). The generic task `PATCH` stays
  free of side effects and does not accept `assignee_id`.
- **D-06:** A task cannot be created already assigned. `POST .../tasks` keeps its Phase 4 schema,
  so `assignee_id` in the body is a 422 by `extra="forbid"`. One use case notifies, not two.
- **D-07:** `PUT` with the user who is already the assignee is a **200 no-op with no second
  email** (idempotent, like the same-state status request of Phase 2 D-02). Changing to a
  different user notifies the new assignee only. `DELETE` on an unassigned task is likewise a
  200 no-op. Unassigning sends nothing.
- **D-08:** Self-assignment is allowed and is emailed like any other — no special case for the
  owner. A non-existent `assignee_id` raises the existing `UserNotFoundError` → **404
  `user_not_found`**. Because `GET /users` already lists every user, that 404 discloses nothing.

### Auth surface & account rules
- **D-09:** `POST /api/v1/auth/register` returns **201 with the profile and no token** —
  `{id, email, full_name, created_at}`, never the hash — plus a `Location` header. Logging in is
  a separate step through `POST /api/v1/auth/login` (the OAuth2 form, which is what Swagger's
  Authorize button drives, AUTH-02). `GET /api/v1/auth/me` returns the same profile shape.
- **D-10:** Password policy is **length only: 8 to 128 characters**, no composition rules
  (NIST 800-63B; the upper bound also bounds Argon2 work). Email is **trimmed and lower-cased**
  before storing and before lookup, consistent with the existing `uq_users_email_lower` index, so
  `Ana@x.com` and `ana@x.com` are one account. `full_name` is trimmed, 1 to 100 characters.
  Per Phase 2 D-04 these limits live in the entity / use case, not in the Pydantic schema.
- **D-11:** `get_current_actor` decodes the token **and confirms the user row exists on every
  request**. Missing, malformed, badly signed, expired and unknown-subject tokens all raise
  `AuthenticationError` and produce the **same generic 401 body**. Consequence to plan for: every
  authenticated request costs one more indexed `SELECT`, so the measured statement counts in
  `tests/integration/api/test_statements.py` (ADR-054: 1 and 3) move by one and that test must be
  updated deliberately, with the reason recorded — invariance is still the property under test.
- **D-12:** A login with a wrong password is indistinguishable from a login with an unknown email
  (roadmap SC-2, AUTH-04): same status, same body.
- **D-13:** `GET /api/v1/users` is callable by **any authenticated user** and returns
  `id`, `full_name`, `email` for every user (literal ASGN-03), ordered by `created_at`, `id`, no
  pagination. It is an email directory; that trade-off is **written down in an ADR** (a real
  product would scope it to a team or organisation, which this brief does not have).

### Evaluator's first five minutes, and the notification
- **D-14:** **No seeded account.** The stack ships with zero users and the entrypoint returns to
  its Phase 3 shape (wait → migrate → serve). The documented path is register → click Authorize
  in Swagger → call anything; the OpenAPI description states it and Phase 7's README repeats it.
  A cold-start evidence capture on an empty volume rehearses exactly that path, including an
  assignment and the logged email.
- **D-15:** The runtime notifier emits **one structured JSON log line** at INFO from a dedicated
  logger (for example `taskmanager.notifications`) with `event=task_assigned_email`, `to`,
  `subject`, `body` and `task_id` as fields, greppable with one command in
  `docker compose logs api`. The body is a short plain-text sentence naming the task title and
  its URL path. Nothing real is sent. The in-memory adapter records messages so tests assert on
  them without mocks (NOTF-02).
- **D-16:** The send happens **inline in the use case, after the commit and outside the
  `async with uow` block, inside a `try/except`** that logs the failure (WARNING, with the task
  id) and swallows it (NOTF-01, NOTF-03). No FastAPI `BackgroundTasks`: the side effect stays
  owned by the application layer, and when the response returns the email has been attempted, so
  tests need no sleeps. A test with a notifier that raises proves the assignment still succeeds
  and is persisted.

### Sequencing: Phase 4 review debt
- **D-17:** The open findings of `04-REVIEW.md` are fixed **before Phase 5 is planned**, as
  Phase 4 debt, through `/gsd-code-review 4 --fix`: CR-01 (write paths read-validate-write with
  no row lock or version column — a forbidden `completed → pending` transition and a lost update
  were reproduced), WR-01 (false 409 on a whitespace-padded re-send of a list's own name),
  WR-02 (`due_date` timezone overflow → 500) and WR-03 (NUL character → 500). Phase 5 adds a
  second writer role and a new write path (`AssignTask`), so its plans must be written against
  write paths that already serialise concurrent writers. If the planner finds CR-01 still open,
  it stops and says so rather than planning around it. WR-05 (the `HTTPException` AST gate scans
  only `routers/`) is relevant here because `actor.py` is rewritten in this phase: the gate's
  scope should cover it.

### Claude's Discretion
- JWT claims beyond `sub` and `exp` (for example `iat`), clock-skew leeway, and the exact token
  response shape (`access_token`, `token_type: "bearer"`, optionally `expires_in`).
- How login equalises the unknown-email and wrong-password paths in time (for example verifying
  against a dummy hash); the observable status and body are locked by D-12.
- Route and module layout (`routers/auth.py`, `routers/users.py`, where `assigned-to-me` lives),
  schema module layout, and the OpenAPI security-scheme wiring (`OAuth2PasswordBearer` with the
  login URL as `tokenUrl`).
- The shape of the `0002` revision and whether `full_name` is backfilled (the only pre-existing
  rows are demo-seed rows on developer machines).
- How the HTTP harness authenticates: keeping the `acting_as` override for most tests and adding
  real-token tests for the 401 legs, or issuing real tokens everywhere. The 401 legs and the
  matrix's anonymous column must go through the real dependency.
- Names of the domain mutators (`Task.assign` / `Task.unassign`) and of the new use cases.
- Whether `TaskResponse` exposes only `assignee_id` or also an embedded assignee summary; the
  requirement is satisfied by the id.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Scope and requirements
- `.planning/ROADMAP.md` § "Phase 5: Auth, Assignment & Notifications" — goal and the five
  success criteria
- `.planning/REQUIREMENTS.md` — AUTH-01..06, ASGN-01..03, NOTF-01..03; AUTH-07/AUTH-08 are v2
- `.planning/PROJECT.md` — core value, constraints, bonus use cases (PDF 1.b)
- `CLAUDE.md` § "Project Rules" and § "Technology Stack" (decisions 6 and 7: PyJWT, pwdlib;
  "What NOT to Use": python-jose, passlib)

### Decisions this phase builds on
- `DECISION_LOG.md` ADR-008 — 404 invisible / 403 visible-but-forbidden; each endpoint owes both
- `DECISION_LOG.md` ADR-044 — `get_current_actor` is a seam, not authentication
- `DECISION_LOG.md` ADR-045 — the entrypoint demo seed, to be deleted here
- `DECISION_LOG.md` ADR-048 — one door into the state machine (model for the assignee route)
- `DECISION_LOG.md` ADR-051 — no `HTTPException` in routers; no web framework below presentation
- `DECISION_LOG.md` ADR-054 — measured statement counts that D-11 changes
- `DECISION_LOG.md` ADR-055 — the visibility rule lives in `access.py`
- `DECISION_LOG.md` ADR-056 — the HTTP harness overrides `get_uow` and never enters the lifespan
- `DECISION_LOG.md` ADR-005, ADR-021 — the RFC 9457 contract and the `DomainError` base shape
- `DECISION_LOG.md` ADR-020, ADR-034, ADR-025, ADR-030, ADR-043 — DTO shape, `Annotated`
  dependencies, literal constraint names in revisions, `IntegrityError` translation, no pagination
- `.planning/phases/04-task-lists-tasks/04-CONTEXT.md` — D-01..D-04 (actor seam and ownership),
  D-16/D-17 (test and statement-count conventions)
- `.planning/phases/02-domain-error-contract/02-CONTEXT.md` — error taxonomy, port declarations,
  D-18 (visibility is decided by the use case)

### Open debt that gates this phase
- `.planning/phases/04-task-lists-tasks/04-REVIEW.md` — CR-01, WR-01..WR-05 (see D-17)
- `.planning/STATE.md` § "Blockers/Concerns" — CR-01 entry, the Phase 5 research flag, the
  host/container coverage note

### External
- https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/ — the PyJWT + pwdlib pattern
- RFC 9110 §15.5.2 (401 requires a challenge), RFC 9457 (problem+json)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/taskmanager/application/ports/security.py` — `PasswordHasher`, `TokenService` protocols,
  already async; only adapters are missing (`infrastructure/security/` does not exist yet).
- `src/taskmanager/application/ports/notifications.py` — `EmailNotifier.send_task_assigned`.
- `src/taskmanager/application/ports/repositories.py` + `infrastructure/db/repositories/users.py`
  — `UserRepository` with `get`, `get_by_email`, `add`, `list_all`; `add` already translates the
  unique-email `IntegrityError` into `EmailAlreadyRegisteredError`.
- `src/taskmanager/domain/entities/user.py` — `User` (no `full_name` yet);
  `src/taskmanager/domain/entities/task.py` — `assignee_id` field exists, no mutator yet.
- `src/taskmanager/domain/exceptions.py` — `AuthenticationError`, `AuthorizationError`,
  `EmailAlreadyRegisteredError`, `UserNotFoundError` already defined and mapped in
  `presentation/api/errors/mapping.py`; `handlers.py` already adds `WWW-Authenticate` on 401.
- `src/taskmanager/application/use_cases/access.py` — `visible_task_list`, `visible_task`; the
  module docstring already anticipates the assignee capabilities and the 403 leg.
- `tests/integration/conftest.py` — `api_client`, `seed` (must commit), `acting_as`,
  `statements`; `tests/integration/api/test_task_lists.py` — builders, `anonymised()`,
  `assert_not_found`.
- `tests/unit/application/fakes.py` — in-memory repositories; an in-memory notifier, hasher and
  token service belong beside them.

### Established Patterns
- Dedicated sub-resource routes for side-effecting verbs (`PATCH .../status`), with
  `extra="forbid"` bodies and the full `TaskResponse` returned.
- Every route declares its refusal legs (401/403/404/409/422/500) as problem+json in OpenAPI;
  route assertions read `app.openapi()["paths"]`, never `app.routes` (ADR-057).
- TDD RED steps cannot be committed red: capture the red run under `evidence/` and commit
  RED+GREEN together.
- New architecture gates written as pytest tests need no new pre-commit or CI step (ADR-015
  argument); a new standalone command needs both.
- Requirement ticks are taken once, by the phase's closing plan, against a named passing test.

### Integration Points
- `presentation/api/actor.py` — body replaced with token decoding + user lookup; the
  `DEMO_USER_ID` constant and its tests go.
- `presentation/api/dependencies.py` — providers for the hasher, token service, notifier and the
  new use cases; `main.py` — composition root registers the new routers and adapters.
- `docker/entrypoint.sh` — step `2b` (the seed) is removed.
- `migrations/versions/` — `0002` adds `users.full_name`.
- `tests/integration/api/test_statements.py` — counts change by D-11.

</code_context>

<specifics>
## Specific Ideas

- The assignee route should feel like the status route: one door, one use case, one place where
  the side effect happens.
- The roadmap's SC-3 demonstration is the story to make visible: an assignee reads a task and
  changes its status, then gets 403 on edit and delete, while a stranger gets 404 on all of it.
- The logged email must be findable with a single `grep` in `docker compose logs api`.
- The evaluator path is register → Authorize → call, with nothing pre-seeded and no known
  password anywhere in the repository.

</specifics>

<deferred>
## Deferred Ideas

- An assignee declining (unassigning themselves) — a new rule not asked for by ASGN-01.
- A `make demo` script that registers two users and walks the assignment story — considered and
  not chosen; could return in Phase 7 if the README walkthrough proves too long.
- Scoping `GET /users` to a team or organisation, or lookup-by-email instead of a directory —
  needs a tenancy concept the brief does not have.
- Login throttling / lockout, refresh tokens, revocation (AUTH-07), password reset and email
  verification (AUTH-08) — v2, to be listed as future work in the README.
- Embedding an assignee summary in `TaskResponse`, and filtering `assigned-to-me` by status or
  priority — not required by ASGN-02.

</deferred>

---

*Phase: 5-Auth, Assignment & Notifications*
*Context gathered: 2026-09-19*
