# Phase 5: Auth, Assignment & Notifications - Research

**Researched:** 2026-09-19
**Domain:** OAuth2 password flow + JWT, Argon2 password hashing, ownership/visibility authorization, outbound notification port
**Confidence:** HIGH (every library claim below was executed against the exact pinned version installed in `.venv`, not recalled)

## Summary

This phase adds **no new dependency**. `PyJWT==2.14.0`, `pwdlib[argon2]==0.3.1`, `python-multipart==0.0.32` and
`email-validator==2.3.0` are already pinned in `requirements.txt` and already installed — Phase 1 pinned them
deliberately so "the Docker layer and the CI cache key never change shape". `JWT_SECRET`, `JWT_ALGORITHM` and
`JWT_EXPIRE_MINUTES` already exist in `Settings` and `.env.example`, and CI already exports `JWT_SECRET`. So the
phase is entirely code: adapters for three ports that already exist, one new Alembic revision, a rewritten actor
seam, six new routes, and the 404/403 split.

Three findings change the shape of the plan and are each verified by execution, not by recall:

1. **`OAuth2PasswordBearer(auto_error=False)` is exactly the seam ADR-051 needs.** With `auto_error=False` the
   dependency returns `None` (never raises `HTTPException`) for a missing header *and* for a non-bearer scheme, so
   the actor dependency raises the domain `AuthenticationError` instead. The OpenAPI `securitySchemes` entry and the
   per-route `security` array are still emitted — including through a *nested* dependency — so Swagger's Authorize
   button works and the AST gate stays green. A live probe produced a 401 `application/problem+json` body with
   `WWW-Authenticate: Bearer` through the project's own existing handler, with no change to `handlers.py`.

2. **A structured INFO log line will not appear unless the application configures logging.** uvicorn's
   `LOGGING_CONFIG` configures only the `uvicorn*` loggers; it attaches nothing to root and leaves the root level at
   `WARNING`. `logging.getLogger("taskmanager.notifications").info(...)` is therefore *filtered out entirely* today —
   verified by execution. D-15 needs a handler attached to the `taskmanager` logger at INFO, with `propagate` left
   `True` (setting it `False` would break the existing `caplog` assertions in `tests/api/test_error_contract.py`).

3. **D-11's predicted statement-count change only happens if the HTTP harness authenticates for real.** `api_client`
   today does *not* override `get_current_actor` — it uses the real one, which reads nothing. If Phase 5 makes the
   default harness override it, the counts stay at 1 and 3 and D-11's consequence is never observed. See
   §"Test harness strategy" for the recommended split.

**Primary recommendation:** Build the token/hasher/notifier adapters in `infrastructure/`, make
`get_current_actor` a two-step dependency (`OAuth2PasswordBearer(auto_error=False)` → `AuthenticateActor` use case
over the *cached* `Depends(get_uow)`), extend `access.py` with a second function (`owned_task`) rather than a second
parameter, and switch the statement-count module — and only it plus the 401 legs and the matrix's anonymous column —
to a real-token client.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Carried forward (locked earlier, not re-discussed)**
- Libraries are fixed by the stack research in `CLAUDE.md`: PyJWT (HS256, pinned algorithm, never python-jose),
  `pwdlib[argon2]` (never passlib) with hashing run off the event loop (AUTH-04), `OAuth2PasswordRequestForm` +
  `python-multipart` for login, `email-validator` behind `EmailStr`.
- `JWT_SECRET`, `JWT_ALGORITHM` and `JWT_EXPIRE_MINUTES` already exist in `.env.example` with no default in code.
  Every setting is read through `taskmanager.infrastructure.config.settings`.
- Phase 5 replaces **only the body** of `get_current_actor` (Phase 4 D-01, ADR-044) and deletes the demo seed step
  from `docker/entrypoint.sh` together with the `DEMO_USER_ID` constant (Phase 4 D-02/D-03, ADR-045). No router,
  schema or use-case signature changes because auth arrived: every command already starts with `actor_id: UUID`.
- ADR-008: invisible → 404, visible but forbidden → 403. The rule lives in one module,
  `application/use_cases/access.py` (ADR-055). Phase 4 deliberately inverted the assignee test in
  `test_change_task_status.py` (04-03); Phase 5 flips it back.
- The error contract is already wired: `AuthenticationError` → 401 with `WWW-Authenticate: Bearer`,
  `AuthorizationError` → 403, `EmailAlreadyRegisteredError` → 409, `UserNotFoundError` → 404, all through the single
  RFC 9457 handler. No handler builds an error body by hand and no router raises or imports `HTTPException`
  (ADR-051).
- The ports already exist and keep their shape unless research proves a need: `PasswordHasher.hash/verify`,
  `TokenService.issue_access_token/decode`,
  `EmailNotifier.send_task_assigned(*, recipient_email, task_title, task_id)`,
  `UserRepository.get/get_by_email/add/list_all`. Adapters arrive in this phase.
- A use case is one class with `execute(command) -> result`; commands and results are frozen slotted dataclasses
  (ADR-020); dependencies are `Annotated[T, Depends(provider)]` (ADR-034); the use case commits through the
  `UnitOfWork`, repositories never do.
- Collections are ordered by `created_at`, then `id`, with no pagination (ADR-043).
- **Known gap, not a choice:** `User` has no `full_name` — not in the entity, the ORM model or `0001_baseline`.
  AUTH-01 and ASGN-03 require it, so this phase owns a `0002` Alembic revision (constraint names spelled as literals
  per ADR-025, constants in `constraints.py`) plus the entity, mapper and repository changes.

**Assignee visibility matrix**
- **D-01:** An assignee who does not own the list can see **only the tasks assigned to them**. The parent list stays
  invisible: `GET /task-lists/{id}` and `GET /task-lists/{id}/tasks` answer 404 for them, and `GET /task-lists`
  remains strictly "lists I own" with its one-statement guarantee (ADR-054) untouched. The assignee still addresses
  their task through the nested URL (`/task-lists/{l}/tasks/{t}`), which answers 200 for them even though the list
  itself is 404.
- **D-02:** Discovery is one new flat, read-only route: **`GET /api/v1/tasks/assigned-to-me`**, returning the
  caller's assigned tasks (each item carries `task_list_id` so the nested URLs can be built), ordered by
  `created_at`, `id`. It is the only new collection in this phase besides `GET /users`.
- **D-03:** On a task assigned to them, an assignee gets: `GET` 200, `PATCH .../status` 200, generic `PATCH` **403**,
  `DELETE` **403**, `PUT`/`DELETE .../assignee` **403**. Everything on tasks and lists they cannot see stays 404, and
  `POST` of a new task into the invisible list stays the list-shaped 404 (04-06). An assignee may **not** unassign
  themselves — ASGN-01 says the list owner unassigns.
- **D-04:** The matrix is proven by **one parametrized test over the real HTTP harness**: rows are every route,
  columns are owner / assignee / stranger / anonymous, each cell is the expected status (200/201/204, 403, 404,
  401). A missing cell must be visible in the table. The same table is reused as documentation in Phase 7. Per-role
  unit tests of `access.py` with the fakes are still expected (they are how the rule is developed), but the HTTP
  table is the contract.

**Assignment API shape**
- **D-05:** Assignment has its own door, mirroring ADR-048's status endpoint:
  **`PUT /api/v1/task-lists/{l}/tasks/{t}/assignee`** with body `{"assignee_id": "<uuid>"}` (`extra="forbid"`)
  assigns, **`DELETE`** on the same URL unassigns. Both return 200 with the full `TaskResponse` (which now exposes
  `assignee_id`, ASGN-02). The generic task `PATCH` stays free of side effects and does not accept `assignee_id`.
- **D-06:** A task cannot be created already assigned. `POST .../tasks` keeps its Phase 4 schema, so `assignee_id`
  in the body is a 422 by `extra="forbid"`. One use case notifies, not two.
- **D-07:** `PUT` with the user who is already the assignee is a **200 no-op with no second email** (idempotent,
  like the same-state status request of Phase 2 D-02). Changing to a different user notifies the new assignee only.
  `DELETE` on an unassigned task is likewise a 200 no-op. Unassigning sends nothing.
- **D-08:** Self-assignment is allowed and is emailed like any other — no special case for the owner. A
  non-existent `assignee_id` raises the existing `UserNotFoundError` → **404 `user_not_found`**. Because
  `GET /users` already lists every user, that 404 discloses nothing.

**Auth surface & account rules**
- **D-09:** `POST /api/v1/auth/register` returns **201 with the profile and no token** —
  `{id, email, full_name, created_at}`, never the hash — plus a `Location` header. Logging in is a separate step
  through `POST /api/v1/auth/login` (the OAuth2 form, which is what Swagger's Authorize button drives, AUTH-02).
  `GET /api/v1/auth/me` returns the same profile shape.
- **D-10:** Password policy is **length only: 8 to 128 characters**, no composition rules (NIST 800-63B; the upper
  bound also bounds Argon2 work). Email is **trimmed and lower-cased** before storing and before lookup, consistent
  with the existing `uq_users_email_lower` index, so `Ana@x.com` and `ana@x.com` are one account. `full_name` is
  trimmed, 1 to 100 characters. Per Phase 2 D-04 these limits live in the entity / use case, not in the Pydantic
  schema.
- **D-11:** `get_current_actor` decodes the token **and confirms the user row exists on every request**. Missing,
  malformed, badly signed, expired and unknown-subject tokens all raise `AuthenticationError` and produce the
  **same generic 401 body**. Consequence to plan for: every authenticated request costs one more indexed `SELECT`,
  so the measured statement counts in `tests/integration/api/test_statements.py` (ADR-054: 1 and 3) move by one and
  that test must be updated deliberately, with the reason recorded — invariance is still the property under test.
- **D-12:** A login with a wrong password is indistinguishable from a login with an unknown email (roadmap SC-2,
  AUTH-04): same status, same body.
- **D-13:** `GET /api/v1/users` is callable by **any authenticated user** and returns `id`, `full_name`, `email` for
  every user (literal ASGN-03), ordered by `created_at`, `id`, no pagination. It is an email directory; that
  trade-off is **written down in an ADR** (a real product would scope it to a team or organisation, which this brief
  does not have).

**Evaluator's first five minutes, and the notification**
- **D-14:** **No seeded account.** The stack ships with zero users and the entrypoint returns to its Phase 3 shape
  (wait → migrate → serve). The documented path is register → click Authorize in Swagger → call anything; the
  OpenAPI description states it and Phase 7's README repeats it. A cold-start evidence capture on an empty volume
  rehearses exactly that path, including an assignment and the logged email.
- **D-15:** The runtime notifier emits **one structured JSON log line** at INFO from a dedicated logger (for example
  `taskmanager.notifications`) with `event=task_assigned_email`, `to`, `subject`, `body` and `task_id` as fields,
  greppable with one command in `docker compose logs api`. The body is a short plain-text sentence naming the task
  title and its URL path. Nothing real is sent. The in-memory adapter records messages so tests assert on them
  without mocks (NOTF-02).
- **D-16:** The send happens **inline in the use case, after the commit and outside the `async with uow` block,
  inside a `try/except`** that logs the failure (WARNING, with the task id) and swallows it (NOTF-01, NOTF-03). No
  FastAPI `BackgroundTasks`: the side effect stays owned by the application layer, and when the response returns the
  email has been attempted, so tests need no sleeps. A test with a notifier that raises proves the assignment still
  succeeds and is persisted.

**Sequencing: Phase 4 review debt**
- **D-17:** (superseded by D-18 — the debt was fixed before planning.)
- **D-18 (D-17 discharged, 2026-09-19):** The debt was fixed before planning — commits `63f6ee4` (CR-01), `0869013`
  (WR-01), `93c4d2c` (WR-02), `5299d7d` (WR-03), `b68686c` (WR-04), `6f30d07` (WR-05); report in
  `.planning/phases/04-task-lists-tasks/04-REVIEW-FIX.md`; suite at 643 passed, 100% coverage. What Phase 5 must
  build on:
  - **Write paths lock.** ADR-058: `TaskRepository.get_for_update(task_id)` and
    `TaskListRepository.get_for_update(task_list_id)` on the ports (adapters use `.with_for_update()` +
    `populate_existing`), reached through `visible_task_list(..., for_update=True)` /
    `visible_task(..., for_update=True)` in `access.py`. Read paths never lock. Lock only the addressed resource: a
    task's writer never holds its list. **Every new Phase 5 write path — the assignee's status change, `AssignTask`,
    `UnassignTask` — loads through the `for_update` door**, and the concurrency suite
    (`tests/integration/test_concurrent_writes.py`) gains a case for owner-vs-assignee writes.
  - **The `HTTPException` AST gate now covers all of `presentation/api`** except the exempt error-handling module,
    including aliased and star imports. The rewritten `actor.py` and the new auth router must raise
    `AuthenticationError`, never `HTTPException` — which also means FastAPI's `OAuth2PasswordBearer(auto_error=True)`
    default (it raises `HTTPException`) has to be dealt with explicitly (for example `auto_error=False` and raising
    the domain error).
  - Text fields refuse NUL and `due_date` refuses values with no UTC form, in `domain/validation.py`; the new
    `full_name` and any other new text field go through the same helpers.
  - `CLAUDE.md` § Project Rules still describes the AST gate as `routers/` only and has no rule for write-path
    locking; this phase's closing plan updates both, each naming its gate.

### Claude's Discretion
- JWT claims beyond `sub` and `exp` (for example `iat`), clock-skew leeway, and the exact token response shape
  (`access_token`, `token_type: "bearer"`, optionally `expires_in`).
- How login equalises the unknown-email and wrong-password paths in time (for example verifying against a dummy
  hash); the observable status and body are locked by D-12.
- Route and module layout (`routers/auth.py`, `routers/users.py`, where `assigned-to-me` lives), schema module
  layout, and the OpenAPI security-scheme wiring (`OAuth2PasswordBearer` with the login URL as `tokenUrl`).
- The shape of the `0002` revision and whether `full_name` is backfilled (the only pre-existing rows are demo-seed
  rows on developer machines).
- How the HTTP harness authenticates: keeping the `acting_as` override for most tests and adding real-token tests
  for the 401 legs, or issuing real tokens everywhere. The 401 legs and the matrix's anonymous column must go
  through the real dependency.
- Names of the domain mutators (`Task.assign` / `Task.unassign`) and of the new use cases.
- Whether `TaskResponse` exposes only `assignee_id` or also an embedded assignee summary; the requirement is
  satisfied by the id.

### Deferred Ideas (OUT OF SCOPE)
- An assignee declining (unassigning themselves) — a new rule not asked for by ASGN-01.
- A `make demo` script that registers two users and walks the assignment story — considered and not chosen; could
  return in Phase 7 if the README walkthrough proves too long.
- Scoping `GET /users` to a team or organisation, or lookup-by-email instead of a directory — needs a tenancy
  concept the brief does not have.
- Login throttling / lockout, refresh tokens, revocation (AUTH-07), password reset and email verification
  (AUTH-08) — v2, to be listed as future work in the README.
- Embedding an assignee summary in `TaskResponse`, and filtering `assigned-to-me` by status or priority — not
  required by ASGN-02.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| AUTH-01 | Register with email, full name and password; duplicate email → 409; hash never returned | §Registration pipeline; §`0002` revision (adds `full_name`); `SqlAlchemyUserRepository.add` already translates `uq_users_email_lower` → `EmailAlreadyRegisteredError` → 409 |
| AUTH-02 | Login via OAuth2 password flow → JWT with expiry; Swagger Authorize works | §Pattern 1 (verified: `securitySchemes.OAuth2PasswordBearer` + per-route `security` emitted through a nested dependency); §Pattern 3 (`TokenService` adapter) |
| AUTH-03 | All task-list/task endpoints require a valid token; missing/invalid/expired → 401 problem+json | §Pattern 1 (verified 401 body with `WWW-Authenticate: Bearer`); §PyJWT exception table |
| AUTH-04 | Argon2 via pwdlib off the event loop; PyJWT with env secret and pinned algorithm; login failures do not reveal whether the email exists | §Pattern 2 (`anyio.to_thread.run_sync`, measured 25–37 ms); §Pattern 4 (dummy-hash equalisation, measured 23.4 ms vs 23.6 ms) |
| AUTH-05 | `/auth/me` returns own profile | §Route inventory; the actor dependency already resolves the `User` row (D-11) |
| AUTH-06 | Invisible → 404 every verb; visible-but-forbidden → 403 | §Pattern 5 (`access.py` split); §The full permission matrix |
| ASGN-01 | Owner assigns/unassigns an existing user; non-existent assignee rejected | §Pattern 6 (`AssignTask` / `UnassignTask` over `owned_task(..., for_update=True)`); `UserNotFoundError` already maps to 404 |
| ASGN-02 | Task responses expose the assignee; assignee can read + change status, not edit/delete | `TaskResponse.assignee_id` **already exists** (`schemas/tasks.py` L193) — no schema change needed; §The full permission matrix |
| ASGN-03 | `GET /users` (id, name, email) | §Route inventory; `UserRepository.list_all` exists and the adapter already orders by `created_at, id`; the **fake** does not (§Pitfall 9) |
| NOTF-01 | Assignment sends a simulated invitation through `EmailNotifier`, after commit | §Pattern 7 (capture the recipient email *inside* the block; send after it) |
| NOTF-02 | Runtime adapter logs the structured email; in-memory adapter lets tests assert without mocks | §Pattern 8 (JSON logging — the application must configure logging or nothing is emitted) |
| NOTF-03 | A notifier failure never fails the assignment | §Pattern 7 (`try/except Exception` after the commit, WARNING + swallow) |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Bearer-token extraction from the request | Presentation (`presentation/api/actor.py`) | — | HTTP header parsing is the web framework's vocabulary; `OAuth2PasswordBearer` also feeds the OpenAPI `securitySchemes` document |
| Token signing / verification | Infrastructure (`infrastructure/security/tokens.py`) | Application (port `TokenService`) | `.importlinter` forbids `jwt` in `domain` and `application`; the algorithm choice must be swappable behind the port |
| Password hashing / verification | Infrastructure (`infrastructure/security/passwords.py`) | Application (port `PasswordHasher`) | Same contract; Argon2's deliberate cost must not be paid by every use-case unit test |
| Password **policy** (8–128 chars) | Domain (`domain/validation.py`) | Application (RegisterUser calls it) | Phase 2 D-04: a limit that exists in two layers is a defect. The entity never sees plaintext, so the helper is called by the use case |
| Email canonical form | Domain (`User.__post_init__`) | Presentation (`EmailStr` validates *format* and lowercases the domain half only — §Pitfall 6) | Already implemented; the two are complementary, not redundant |
| "Who is calling" → `UUID` | Presentation | Application (`AuthenticateActor` use case) | The router signature does not change (ADR-044); the DB lookup belongs behind a use case so presentation never touches `uow.users` directly |
| Visibility (404) and permission (403) | Application (`use_cases/access.py`) | — | ADR-008 + ADR-055: the decision needs ownership knowledge the router does not have |
| Row locking on write paths | Infrastructure (adapters) | Application (`for_update=True` at the call site) | ADR-058; the port states the contract in domain terms |
| Sending the invitation | Infrastructure (`infrastructure/notifications/`) | Application (`EmailNotifier` port, called by `AssignTask`) | NOTF-01/02; the adapter swap is the visible form of "simulated" |
| Structured JSON log formatting | Infrastructure (`infrastructure/logging.py`) | Main (`create_app` calls `configure_logging()`) | uvicorn configures only its own loggers (§Pattern 8); `main` is the composition root |

## Project Constraints (from CLAUDE.md)

Every item below fails a build, not a review. The planner must verify each plan against this list.

| Constraint | Gate | Phase 5 impact |
|---|---|---|
| Import direction main > presentation > infrastructure > application > domain | `.importlinter` `layers`, run by `tests/architecture/test_layer_boundaries.py`, `make arch`, CI | New modules must sit in the right package; `infrastructure/security/*` may import `jwt`/`pwdlib`, `application/*` may not |
| `domain` imports no third-party library at all | `test_domain_is_stdlib_only.py` + `domain-framework-free` contract | `require_password` helper goes in `domain/validation.py` (stdlib only) |
| `application` imports no web framework, no ORM, **no `jwt`, no `pwdlib`** | `application-framework-free` contract | Use cases take the ports, never the libraries |
| `fastapi.HTTPException` never raised **or imported** anywhere under `presentation/api` except `errors/handlers.py` | `tests/architecture/test_routers_raise_no_http_exception.py` (AST, two passes, star-import aware) | `OAuth2PasswordBearer(auto_error=False)`; new modules must be added to `REQUIRED_SCANNED_MODULES` in the same commit |
| No transaction-ending call under `infrastructure/db/repositories/` | `test_no_commit_in_repositories.py` | New repository methods obey it |
| Repositories take and return domain entities only | `application-framework-free` + `test_adapter_ports.py` under `mypy --strict` | `list_for_assignee` returns `Sequence[Task]` |
| Migrations run in `docker/entrypoint.sh`, never in `create_app()` / lifespan | `test_creating_the_app_opens_no_connection`, `test_the_lifespan_disposes_the_engine` | `configure_logging()` in `create_app` must open nothing |
| Constraint names live only in `infrastructure/db/constraints.py`; twelve must appear in the compiled DDL | `tests/unit/infrastructure/test_models.py`, `tests/integration/test_constraints.py` | A new index constant must be added there **and** to that test |
| FastAPI dependencies as `Annotated[T, Depends(...)]`, never argument defaults | flake8-bugbear B008 in `make lint` | Every new provider |
| `make lint` / `typecheck` / `arch` / `test` green before any commit | pre-commit + CI | — |
| Coverage gated at 75%, never reached with `# pragma: no cover` or an `omit` | `pytest.ini --cov-fail-under=75` | Suite currently at 100%; new adapter branches need tests |
| A new gate goes in **both** `.pre-commit-config.yaml` and `.github/workflows/ci.yml` | ADR-015 | Only if a plan adds a *standalone command*; a pytest-based gate needs neither |
| No secret gets a default value in code | `tests/unit/test_settings.py` | `jwt_secret` already has none |
| Every setting is in `.env.example` and in `Settings`, as an exact set equality | `test_env_example_documents_every_field` | Any new setting must be added to both |
| Everything in English; no AI attribution trailer in commits | review | — |

## Standard Stack

### Already installed — no new dependency in this phase

| Library | Pinned version | Verified present | Purpose in Phase 5 |
|---------|----------------|------------------|--------------------|
| `PyJWT` | `2.14.0` | `jwt.__version__ == "2.14.0"` in `.venv` `[VERIFIED: local import]` | HS256 sign/verify the access token |
| `pwdlib[argon2]` | `0.3.1` | `pwdlib.__version__ == "0.3.1"`; `argon2_cffi 25.1.0`, `argon2_cffi_bindings 26.1.0` `[VERIFIED: local import]` | Argon2id hash/verify |
| `python-multipart` | `0.0.32` | in `requirements.txt`; `OAuth2PasswordRequestForm` parsed a form in the live probe `[VERIFIED: executed]` | Form parsing for `POST /auth/login` |
| `email-validator` | `2.3.0` | `EmailStr` validated and normalised in the live probe `[VERIFIED: executed]` | Backs `EmailStr` on the register schema |
| `fastapi` | `0.141.1` | `fastapi.__version__` `[VERIFIED: local import]` | `OAuth2PasswordBearer`, `OAuth2PasswordRequestForm` |
| `pydantic` | `2.13.5` | `pydantic.VERSION` `[VERIFIED: local import]` | `EmailStr`, `SecretStr`, `extra="forbid"` |
| `anyio` | `4.15.1` | `to_thread.run_sync` signature read `[VERIFIED: local import]` | Run Argon2 off the event loop (transitive via Starlette/httpx; already present) |

**Installation:** none. `pip install -r requirements-dev.txt` as today.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `anyio.to_thread.run_sync` | `asyncio.to_thread` | Both work under `asyncio_mode = auto`. anyio's shared `CapacityLimiter` (default 40) is the same pool Starlette uses for sync endpoints, so concurrent logins cannot grow threads unbounded; `asyncio.to_thread` uses the default executor (`min(32, cpu+4)`). anyio is already an installed transitive dependency and adding it to `requirements.txt` is optional. **Recommend anyio**, note the choice in `DECISION_LOG.md`. |
| A new `AuthenticateActor` use case | The actor dependency calling `uow.users.get` directly | Direct call is 5 fewer lines and puts a repository call in `presentation`. The project's whole shape is "routers call use cases"; a use case also keeps the 401 decision testable against the fakes with no HTTP. **Recommend the use case.** |
| `Settings.jwt_secret` floor of 16 | floor of 32 | PyJWT emits `InsecureKeyLengthWarning` below 32 bytes for HS256 (RFC 7518 §3.2) — and `pytest.ini` has `filterwarnings = error`, so a 16-character secret in any future test would *error*. All current secrets are ≥32. **Recommend raising the floor to 32** and updating `test_short_secret_is_rejected` and the `.env.example` comment. This is a change to an existing setting, so the planner should surface it rather than slip it in. |
| Dedicated logging module called from `create_app` | `uvicorn --log-config` file in the entrypoint | A file is untested, lives outside coverage, and does nothing for `pytest`/`caplog`. **Recommend the module.** |

## Package Legitimacy Audit

No package is added by this phase. The four auth-relevant packages already pinned were nevertheless re-checked.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| `PyJWT` | PyPI | 10+ yrs | very high | github.com/jpadilla/pyjwt | `[OK]` | Approved — already pinned `2.14.0` |
| `pwdlib` | PyPI | ~2 yrs | moderate | github.com/frankie567/pwdlib | `[OK]` | Approved — already pinned `0.3.1` |
| `python-multipart` | PyPI | 10+ yrs | very high | github.com/Kludex/python-multipart | `[OK]` | Approved — already pinned `0.0.32` |
| `email-validator` | PyPI | 10+ yrs | very high | github.com/JoshData/python-email-validator | `[OK]` | Approved — already pinned `2.3.0` |

`slopcheck install PyJWT pwdlib python-multipart email-validator` reported **"scanned 4 packages — 4 OK"**
`[VERIFIED: slopcheck]`. (The tool then crashed trying to shell out to `pip`, which is not on this machine's PATH;
the scan itself had already completed and printed its verdict.)

**Packages removed due to slopcheck `[SLOP]`:** none.
**Packages flagged `[SUS]`:** none.

## Architecture Patterns

### System Architecture Diagram

```
                       HTTP request
                            │
                            ▼
        ┌───────────────────────────────────────────────┐
        │  presentation/api                             │
        │                                               │
        │  OAuth2PasswordBearer(auto_error=False)       │
        │      │ returns str | None  (never raises)     │
        │      ▼                                        │
        │  get_current_actor(token, uow, tokens)        │ ◄── Depends(get_uow)  [CACHED per request]
        │      │                                        │        │
        └──────┼────────────────────────────────────────┘        │
               ▼                                                 │
        application: AuthenticateActor.execute(token)            │
               │  ├─ tokens.decode(token) ──► TokenService       │
               │  │        (infrastructure/security/tokens.py)   │
               │  │        PyJWT decode, algorithms=[HS256]      │
               │  └─ async with uow: users.get(uuid)  ───────────┘  (+1 SELECT, D-11)
               │         └─ None or decode failure ──► AuthenticationError
               ▼
          actor_id: UUID  ──►  router handler (signature unchanged, ADR-044)
               │
               ▼
        application use case  (async with uow: …)
               │
               ├─ access.visible_task(...)   ── task | TaskNotFoundError (404)
               ├─ access.owned_task(...)     ── task | AuthorizationError (403) | TaskNotFoundError (404)
               ├─ access.visible_task_list() ── list | TaskListNotFoundError (404)
               │
               ├─ entity mutation (Task.assign / change_status / …)
               ├─ uow.tasks.update(task)
               └─ uow.commit()            ◄── transaction boundary ends here
               │
               │   (OUTSIDE the block — ADR-032: the uow refuses use after exit)
               ▼
        try: await notifier.send_task_assigned(recipient_email=…, task_title=…, task_id=…)
        except Exception: logger.warning(... task_id ...)   ── swallowed (NOTF-03)
               │
               ▼
        infrastructure/notifications/logging.py
               │  logging.getLogger("taskmanager.notifications").info(…, extra=…)
               ▼
        infrastructure/logging.py  JSON formatter on the "taskmanager" logger
               │
               ▼
        stdout → `docker compose logs api`
               │
        any DomainError raised anywhere above
               ▼
        presentation/api/errors/handlers.py  ── the ONE RFC 9457 problem+json response
               (401 also gets WWW-Authenticate: Bearer)
```

### Recommended Project Structure

```
src/taskmanager/
├── domain/
│   ├── entities/user.py             # + full_name, FULL_NAME_MAX_LENGTH
│   ├── entities/task.py             # + assign(assignee_id, now) / unassign(now)
│   └── validation.py                # + require_password(value) -> str  (8..128, stdlib only)
├── application/
│   ├── dto/commands.py              # + RegisterUserCommand, LoginCommand, AssignTaskCommand,
│   │                                #   UnassignTaskCommand, ListAssignedTasksCommand, ListUsersCommand
│   ├── dto/results.py               # + UserResult, AccessTokenResult
│   ├── ports/repositories.py        # + TaskRepository.list_for_assignee(assignee_id)
│   └── use_cases/
│       ├── access.py                # + owned_task(...)  (the 403 leg)
│       ├── auth/register.py         # RegisterUser
│       ├── auth/login.py            # Login
│       ├── auth/authenticate.py     # AuthenticateActor  (token -> User)
│       ├── users/list.py            # ListUsers
│       └── tasks/assign.py          # AssignTask, UnassignTask  (+ list_assigned.py)
├── infrastructure/
│   ├── logging.py                   # configure_logging(): JSON handler on the "taskmanager" logger
│   ├── security/passwords.py        # PwdlibPasswordHasher
│   ├── security/tokens.py           # JwtTokenService(secret, algorithm, expire_minutes, clock)
│   ├── notifications/logging.py     # LoggingEmailNotifier
│   ├── db/constraints.py            # + IX_TASKS_ASSIGNEE_ID
│   ├── db/models.py                 # + UserRow.full_name, TaskRow.assignee_id index=True
│   ├── db/mappers.py                # + full_name in the three user functions
│   └── db/repositories/{users,tasks}.py
├── presentation/api/
│   ├── actor.py                     # rewritten: scheme + AuthenticateActor; DEMO_USER_ID deleted
│   ├── dependencies.py              # + get_password_hasher, get_token_service, get_email_notifier
│   ├── routers/auth.py              # register / login / me
│   ├── routers/users.py             # GET /users
│   ├── routers/assignments.py       # PUT+DELETE .../assignee, GET /tasks/assigned-to-me
│   └── schemas/{auth,users}.py
├── main.py                          # + configure_logging(); + 3 register_*_routes calls
└── migrations/versions/0002_*.py    # users.full_name NOT NULL + ix_tasks_assignee_id
```

### Pattern 1: The bearer scheme that never raises `HTTPException`

**What:** `OAuth2PasswordBearer(auto_error=False)` returns `str | None` and raises nothing. The domain error is
raised by *our* code, so ADR-051's AST gate stays green while Swagger's Authorize button and the OpenAPI
`securitySchemes` entry keep working.

**Verified source of the guarantee** — `fastapi/security/oauth2.py`, `OAuth2PasswordBearer.__call__`:

```python
async def __call__(self, request: Request) -> str | None:
    authorization = request.headers.get("Authorization")
    scheme, param = get_authorization_scheme_param(authorization)
    if not authorization or scheme.lower() != "bearer":
        if self.auto_error:
            raise self.make_not_authenticated_error()   # ← the line we avoid
        else:
            return None
    return param
```

Consequences the dependency must handle, **all measured against a live app**:

| Request | `__call__` returns | Required behaviour |
|---|---|---|
| no `Authorization` header | `None` | `AuthenticationError` → 401 |
| `Authorization: Basic zzz` | `None` | `AuthenticationError` → 401 |
| `Authorization: Bearer ` (empty param) | `""` | falsy — `AuthenticationError` → 401 |
| `Authorization: bearer <tok>` (lowercase) | `<tok>` | accepted; the scheme match is case-insensitive |

**Example (shape proven end to end against this repo's own `register_exception_handlers`):**

```python
# presentation/api/actor.py  — Source: verified probe, /tmp/probe_oauth.py
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from taskmanager.application.use_cases.auth.authenticate import AuthenticateActor
from taskmanager.domain.exceptions import AuthenticationError
from taskmanager.presentation.api.dependencies import (
    TokenServiceDependency,
    UnitOfWorkDependency,
)

# tokenUrl is what Swagger's Authorize button POSTs to.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

BearerToken = Annotated[str | None, Depends(oauth2_scheme)]


async def get_current_actor(
    token: BearerToken,
    uow: UnitOfWorkDependency,
    tokens: TokenServiceDependency,
) -> UUID:
    if not token:                       # covers None and ""
        raise AuthenticationError("Could not validate credentials.")
    return (await AuthenticateActor(uow, tokens).execute(token)).id


CurrentActor = Annotated[UUID, Depends(get_current_actor)]
```

Observed result of `GET` with no header, through the project's real handler stack:

```
401 application/problem+json   WWW-Authenticate: Bearer
{"type":"urn:taskmanager:problem:authentication_failed","title":"Authentication failed","status":401,
 "detail":"Could not validate credentials.","instance":"/api/v1/me","code":"authentication_failed"}
```

`app.openapi()` produced `components.securitySchemes.OAuth2PasswordBearer = {"type":"oauth2","flows":{"password":
{"scopes":{},"tokenUrl":...}}}` and `paths./api/v1/me.get.security = [{"OAuth2PasswordBearer": []}]` — **through the
nested dependency**, so nothing has to be repeated per route. `[VERIFIED: executed against fastapi 0.141.1]`

**`tokenUrl`:** FastAPI's own tutorial uses a *relative* `tokenUrl="token"`. Because this app's OpenAPI document is
served from `/openapi.json` (root), the relative form `api/v1/auth/login` and the absolute form
`/api/v1/auth/login` both resolve to the same URL. **Recommend the absolute `/api/v1/auth/login`** — it is
unambiguous if the document ever moves. `[VERIFIED: spec content]` / `[ASSUMED: Swagger's relative resolution]`

**`OAuth2PasswordRequestForm` failures already land on the existing handler.** A `POST` missing `password` produced,
verified:

```json
{"type":"urn:taskmanager:problem:validation_error","title":"Request validation failed","status":422,
 "detail":"The request payload failed validation.","instance":"/api/v1/auth/login","code":"validation_error",
 "errors":[{"field":"body.password","message":"Field required","type":"missing"}]}
```

A JSON body sent to the form endpoint is also a 422. Crucially, **the submitted value is not echoed** — the existing
`handle_validation_error` keeps only `loc`/`msg`/`type`, so a password can never reach the response body. That is an
existing security property this phase depends on; it needs a test that names it.

### Pattern 2: Argon2 off the event loop

```python
# infrastructure/security/passwords.py
from anyio import to_thread
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError


class PwdlibPasswordHasher:
    """`PasswordHasher` over pwdlib's recommended Argon2id configuration."""

    def __init__(self, password_hash: PasswordHash | None = None) -> None:
        self._hash = password_hash or PasswordHash.recommended()

    async def hash(self, password: str) -> str:
        return await to_thread.run_sync(self._hash.hash, password)

    async def verify(self, password: str, hashed: str) -> bool:
        try:
            return await to_thread.run_sync(self._hash.verify, password, hashed)
        except UnknownHashError:
            # A stored value that is not an Argon2 encoded hash is not a
            # credential; it is a row this application did not write.
            return False
```

Measured on this machine (aarch64 macOS, `.venv` Python 3.14) `[VERIFIED: executed]`:

| Operation | Parameters | Time |
|---|---|---|
| `PasswordHash.recommended().hash(...)` | `m=65536,t=3,p=4` (argon2-cffi defaults) | **37.2 ms** |
| `.verify(...)` correct password | same | **25.7 ms** |
| `.verify(...)` wrong password | same | **23.6 ms** |
| `.verify(...)` against a dummy hash | same | **23.4 ms** |
| `Argon2Hasher(time_cost=1, memory_cost=8, parallelism=1)` hash | cheap | **0.05 ms** |
| same, verify | cheap | **0.03 ms** |
| hash of a 100 000-character password | recommended | **23.8 ms** (Argon2 pre-hashes with Blake2b — length is not the cost driver) |

Encoded hash length is **97 characters**, comfortably inside `User.PASSWORD_HASH_MAX_LENGTH = 512`.

**Test-cost consequence:** the suite is 643 tests in ~4 s. At 25–37 ms per real Argon2 call, ten integration tests
that register and log in add ~0.5 s — acceptable. Unit tests of `RegisterUser`/`Login` must use a **fake hasher**
(alongside the other fakes in `tests/unit/application/fakes.py`), and exactly **one** test should prove the real
adapter round-trips (`hash` then `verify` true, `verify` false, `verify` against a non-Argon2 string returns
`False`). Do not lower the real adapter's cost parameters for tests — inject a different object.

### Pattern 3: The `TokenService` adapter (PyJWT 2.14)

```python
# infrastructure/security/tokens.py
from datetime import timedelta
from uuid import UUID

import jwt
from jwt.exceptions import InvalidTokenError

from taskmanager.application.ports.clock import Clock
from taskmanager.domain.exceptions import AuthenticationError

_REQUIRED_CLAIMS = ["sub", "exp", "iat"]


class JwtTokenService:
    def __init__(
        self, *, secret: str, algorithm: str, expire_minutes: int, clock: Clock
    ) -> None:
        self._secret = secret
        self._algorithm = algorithm
        self._lifetime = timedelta(minutes=expire_minutes)
        self._clock = clock

    async def issue_access_token(self, subject: UUID) -> str:
        issued_at = self._clock.now()
        return jwt.encode(
            # `sub` MUST be a string: PyJWT >= 2.10 raises InvalidSubjectError
            # on decode when it is not.
            {"sub": str(subject), "iat": issued_at, "exp": issued_at + self._lifetime},
            self._secret,
            algorithm=self._algorithm,
        )

    async def decode(self, token: str) -> UUID:
        try:
            payload = jwt.decode(
                token,
                self._secret,
                algorithms=[self._algorithm],          # pinned; never read from the token
                options={"require": _REQUIRED_CLAIMS},
            )
            return UUID(payload["sub"])
        except (InvalidTokenError, ValueError, TypeError) as error:
            raise AuthenticationError("Could not validate credentials.") from error
```

**Behaviour table, every row executed against PyJWT 2.14.0** `[VERIFIED: executed]`:

| Input | Exception raised | Subclass of `InvalidTokenError`? |
|---|---|---|
| valid token | — returns the claims dict | — |
| `alg=none` token, `algorithms=["HS256"]` | `InvalidAlgorithmError: The specified alg value is not allowed` | ✅ |
| token signed with another secret | `InvalidSignatureError` | ✅ (via `DecodeError`) |
| `exp` one second in the past | `ExpiredSignatureError` | ✅ |
| same, with `leeway=5` | **decodes successfully** | — |
| `sub` an int | `InvalidSubjectError: Subject must be a string` | ✅ |
| `sub` absent, `options={"require":["sub"]}` | `MissingRequiredClaimError` | ✅ |
| `"garbage"` / `""` | `DecodeError: Not enough segments` | ✅ |
| HMAC key shorter than 32 bytes | `InsecureKeyLengthWarning` (a `UserWarning`) on **both** encode and decode | n/a — see §Pitfall 1 |
| same, with `PyJWT(options={"enforce_minimum_key_length": True})` | `InvalidKeyError` | ❌ **`InvalidKeyError` is NOT an `InvalidTokenError`** |

Two consequences for the `except` clause:
- Catching `jwt.exceptions.InvalidTokenError` covers every *token* failure above. That is the right net.
- `InvalidKeyError` is deliberately **outside** it — it means the server is misconfigured, not that the caller's
  token is bad, and it should become the fixed 500, not a 401. Do **not** widen the catch to `PyJWTError`.
- `UUID(payload["sub"])` raises `ValueError` for a well-formed token carrying a non-UUID subject (and `TypeError`
  for a non-string, though `InvalidSubjectError` normally gets there first). Both must be caught, and both need a
  test — a token forged with our own secret carrying `sub="not-a-uuid"` is trivial to construct in a test.

**Expiry is validated against the real system clock, not the injected `Clock`.** PyJWT's `_validate_exp` compares
against `time.time()`; there is no hook. The testable design is therefore: the **issuing** side reads the injected
`Clock`, so a fake clock set two hours in the past mints a token whose `exp` is already behind real `time.time()`.
No `freezegun`, no `sleep`. `[VERIFIED: source read + executed]`

**`iat`:** `jwt.encode` converts a `datetime` via `timegm(value.utctimetuple())`, which drops microseconds and
requires the value to be aware (the project's `SystemClock` already returns aware UTC). Including `iat` costs
nothing and makes a token self-describing; `require`-ing it is what makes a hand-forged minimal token fail.

**Leeway:** recommend `leeway=0` for this deliverable and say so in the ADR. One machine, one clock; a non-zero
leeway would make the expired-token test depend on a tolerance rather than on a boundary.

**Token response shape (discretion):** `{"access_token": "<jwt>", "token_type": "bearer"}` is the minimum Swagger's
Authorize button requires. Adding `"expires_in": <seconds>` is free and honest. `token_type` must be the literal
lowercase `"bearer"`.

### Pattern 4: Login that cannot be used to enumerate accounts (D-12)

The official FastAPI tutorial does exactly this, and it is the pattern to copy `[CITED:
fastapi.tiangolo.com/tutorial/security/oauth2-jwt]`:

```python
# application/use_cases/auth/login.py  (sketch)
class Login:
    def __init__(self, uow, hasher, tokens) -> None: ...

    async def execute(self, command: LoginCommand) -> AccessTokenResult:
        async with self._uow:
            user = await self._uow.users.get_by_email(command.email)
        # One refusal for both legs: same class, same message, same body (D-12).
        if user is None:
            # Burn the same Argon2 work an existing account would have cost,
            # so the two paths are indistinguishable in time as well as in body.
            await self._hasher.verify(command.password, self._dummy_hash)
            raise AuthenticationError("Incorrect email or password.")
        if not await self._hasher.verify(command.password, user.password_hash):
            raise AuthenticationError("Incorrect email or password.")
        return AccessTokenResult(
            access_token=await self._tokens.issue_access_token(user.id), ...
        )
```

Measured timings make the equalisation real rather than notional: verify-against-a-real-hash **23.6 ms** vs
verify-against-the-dummy **23.4 ms** `[VERIFIED: executed]`.

**Where the dummy hash comes from.** Hashing a constant at import time costs 37 ms per process — acceptable, but it
happens in *every* test process too. Recommended: compute it lazily and once inside the `PwdlibPasswordHasher`
adapter (`async def dummy_hash(self) -> str` or a cached attribute), or expose it as a constant the provider builds
once. **Do not** hard-code an Argon2 string in source: it reads as a credential. The application layer must not
compute it either (it would need `pwdlib`), so it belongs behind the `PasswordHasher` port — which means
**the port gains one method** (e.g. `async def dummy_verify(self, password: str) -> None`). CONTEXT says the ports
"keep their shape unless research proves a need"; this is the one place research does prove a need, and the planner
should record it as a deliberate port extension rather than smuggle it in. A zero-change alternative is for the
`Login` use case to hold a module-level dummy hash string produced by the injected hasher at construction time —
but construction happens per request, so that re-hashes on every login. **Recommend the port extension.**

**Note on the login "username" field.** OAuth2 fixes the field name to `username`; this API's usernames are email
addresses. Say so in the route description so an evaluator reading `/docs` is not confused.

### Pattern 5: `access.py` — the 404/403 split (AUTH-06, D-01..D-04)

The current `visible_task` refuses on four legs, all `TaskNotFoundError`. Phase 5 needs three outcomes, not two,
and the cheapest correct shape is **a second function beside the existing one**, not a second parameter:

```python
# application/use_cases/access.py  (recommended addition)
async def visible_task(uow, task_list_id, task_id, actor_id, *, for_update=False) -> Task:
    """The task, if this actor may SEE it: its list's owner, or its assignee (D-01)."""
    task = await (uow.tasks.get_for_update if for_update else uow.tasks.get)(task_id)
    if task is None or task.task_list_id != task_list_id:
        raise TaskNotFoundError(task_id)
    # The assignee sees the task without ever seeing its list — which is why the
    # list is not read at all on this leg.
    if task.assignee_id == actor_id:
        return task
    task_list = await uow.task_lists.get(task_list_id)
    if task_list is None or task_list.owner_id != actor_id:
        raise TaskNotFoundError(task_id)
    return task


async def owned_task(uow, task_list_id, task_id, actor_id, *, for_update=False) -> Task:
    """The task, if this actor OWNS its list. Visible-but-not-owned is 403 (ADR-008)."""
    task = await (uow.tasks.get_for_update if for_update else uow.tasks.get)(task_id)
    if task is None or task.task_list_id != task_list_id:
        raise TaskNotFoundError(task_id)
    task_list = await uow.task_lists.get(task_list_id)
    if task_list is None or task_list.owner_id != actor_id:
        if task.assignee_id == actor_id:
            raise AuthorizationError("Only the list owner may change this task.")
        raise TaskNotFoundError(task_id)
    return task
```

Why a second function rather than `visible_task(..., require_owner=True)`: a boolean at the call site reads as
configuration, and the two functions have genuinely different failure *sets*. Why not a tuple return
`(task, is_owner)`: it would change all six existing call sites and push the ADR-008 decision back out into the use
cases, which is what ADR-055 exists to prevent.

**Which use case calls which:**

| Use case | Guard | `for_update` | Assignee outcome |
|---|---|---|---|
| `GetTask` | `visible_task` | `False` | 200 |
| `ChangeTaskStatus` | `visible_task` | **`True`** (ADR-058) | 200 |
| `UpdateTask` | `owned_task` | **`True`** | **403** |
| `DeleteTask` | `owned_task` | **`True`** | **403** |
| `AssignTask` (new) | `owned_task` | **`True`** | **403** |
| `UnassignTask` (new) | `owned_task` | **`True`** | **403** |
| `ListTasks`, `CreateTask` | `visible_task_list` (unchanged) | `False` / `False` | **404** (list-shaped) |
| `GetTaskList`, `UpdateTaskList`, `DeleteTaskList` | `visible_task_list` (unchanged) | `False`/`True`/`True` | **404** |
| `ListAssignedTasks` (new) | none — the query *is* the filter | `False` | own rows only |

**Statement-count side effect, worth naming in the plan:** the assignee's `GET`/`PATCH status` short-circuits before
reading the list, so those requests issue **one** task `SELECT` where the owner's issue two. This is a saving, not a
regression, but it means the count differs by role and any new count assertion must say which role it measures.

**ADR-050 (the wrong-list rule) composes cleanly.** The `task.task_list_id != task_list_id` check still comes
*first*, before either the assignee check or the list read, so a request naming the wrong parent is refused before
anything is learned about that parent — including by an assignee.

**Documentation debt this creates.** `access.py`'s module docstring currently states, as a checkable property, that
`AuthorizationError` "is deliberately not named anywhere in this file, prose included, so 'this module cannot
produce a 403' is something a grep over it settles". Phase 5 falsifies that sentence. It must be rewritten in the
same commit that introduces `owned_task`, and `tests/unit/application/test_access.py` has five
`assert not isinstance(error, AuthorizationError)` assertions that stay valid for the 404 legs and must be joined by
the mirror-image assertions for the 403 leg.

### Pattern 6: The assignment door (D-05..D-08)

Mirror `PATCH .../status` exactly (ADR-048). Two routes, two use cases, one notification:

```
PUT    /api/v1/task-lists/{list_id}/tasks/{task_id}/assignee   body {"assignee_id": uuid}  → 200 TaskResponse
DELETE /api/v1/task-lists/{list_id}/tasks/{task_id}/assignee   no body                     → 200 TaskResponse
```

`AssignTask.execute` in order:
1. `async with uow:`
2. `task = await owned_task(uow, list_id, task_id, actor_id, for_update=True)` — 404 / 403 decided here.
3. `assignee = await uow.users.get(command.assignee_id)`; `None` → `UserNotFoundError(assignee_id)` → 404 (D-08).
   *(Ordering matters: the ownership guard must run before the assignee lookup, or a stranger could probe user ids.)*
4. **D-07 idempotence:** `if task.assignee_id == command.assignee_id:` → commit nothing, send nothing, return the
   task. Matching `Task.change_status`'s same-state no-op.
5. `task.assign(assignee.id, now=clock.now())`; `uow.tasks.update(task)`; `uow.commit()`.
6. **Capture `assignee.email` and `task.title` into locals *inside* the block** (see Pattern 7).
7. Leave the block; attempt the notification.

`UnassignTask` is the same minus steps 3 and 6, with `DELETE` on an already-unassigned task a 200 no-op and no
email (D-07).

`Task.assign` / `Task.unassign` (names at discretion) follow the existing mutator convention exactly: validate
`now` with `require_utc` **before** the first assignment (the rule `rename` documents), set `assignee_id`, set
`updated_at`.

**`GET /api/v1/tasks/assigned-to-me`** needs one new port method:

```python
# ports/repositories.py — TaskRepository
async def list_for_assignee(self, assignee_id: UUID) -> Sequence[Task]: ...
```

Adapter: `select(TaskRow).where(TaskRow.assignee_id == assignee_id).order_by(TaskRow.created_at, TaskRow.id)`.
Return `TaskCollectionResponse`? **No** — that envelope carries the list-level completion statistics, which have no
meaning across lists. Return a bare `list[TaskResponse]`, matching `GET /task-lists`'s bare-array shape.

**There is no index on `tasks.assignee_id` today.** `models.py` declares `assignee_id` with a `ForeignKey` but no
`index=True` (unlike `task_list_id`, which has one). PostgreSQL does not index foreign keys automatically, so this
new query is a sequential scan, and so is every `ON DELETE SET NULL` cascade. The `0002` revision should add
`ix_tasks_assignee_id` with `index=True` on the model and a new `IX_TASKS_ASSIGNEE_ID` constant in `constraints.py`.
Note `models.py` already argues *against* a redundant index on `task_lists.owner_id` because it is the leading
column of a unique constraint — no such cover exists here, so this one is justified rather than speculative.

### Pattern 7: Notifying after the commit, without reaching into a closed unit of work

The trap: `SqlAlchemyUnitOfWork.__aexit__` unbinds the three repositories and sets `_session = None`, and the port
docstring makes any use after the block a `RuntimeError`. The assignee's **email address** therefore has to leave
the block as a plain `str`:

```python
async with self._uow:
    task = await owned_task(self._uow, ..., for_update=True)
    assignee = await self._uow.users.get(command.assignee_id)
    if assignee is None:
        raise UserNotFoundError(command.assignee_id)
    if task.assignee_id == assignee.id:
        return TaskResult.from_entity(task)          # D-07 no-op: no commit, no email
    task.assign(assignee.id, now=self._clock.now())
    await self._uow.tasks.update(task)
    await self._uow.commit()
    recipient_email = assignee.email                  # ← captured INSIDE
    task_title = task.title

# Outside the block: the write is durable. A notifier failure cannot undo it.
try:
    await self._notifier.send_task_assigned(
        recipient_email=recipient_email, task_title=task_title, task_id=task.id
    )
except Exception:                                     # noqa: BLE001 - NOTF-03 is the rule
    logger.warning(
        "Assignment notification failed for task %s", task.id, exc_info=True
    )
return TaskResult.from_entity(task)
```

Three points the planner should make explicit in the plan:

- `logger = logging.getLogger(__name__)` at the top of the use-case module is **legal in the application layer**:
  `logging` is stdlib and `.importlinter` forbids only `fastapi`, `starlette`, `sqlalchemy`, `alembic`, `jwt`,
  `pwdlib` there. `presentation/api/errors/handlers.py` already sets the precedent.
- `except Exception` will trip flake8-bugbear **B902/BLE001** style checks depending on plugin set. The installed
  set is bugbear + comprehensions + pep8-naming; `docker/entrypoint.sh` already carries a
  `# noqa: BLE001` comment for exactly this shape, so the convention exists. Verify with `make lint` rather than
  assuming which code fires.
- `exc_info=True` is safe here (there *is* an ambient exception), unlike the `exc_info=exc` form `handlers.py` uses
  outside an except block.

### Pattern 8: Making one JSON line appear in `docker compose logs api`

**The finding that changes the plan:** uvicorn's `LOGGING_CONFIG` (`uvicorn/config.py` L83–113) declares handlers
only for `uvicorn`, `uvicorn.error` and `uvicorn.access`. It attaches nothing to root and leaves root at `WARNING`.
Executed, with no configuration:

```
logging.getLogger("taskmanager.notifications").info("invisible")   → nothing printed at all
logging.getLogger("taskmanager.notifications").error("visible")    → printed by logging.lastResort, unformatted
```

So D-15's INFO line **is silently dropped** today. `[VERIFIED: executed]`

The fix, also executed:

```python
# infrastructure/logging.py
import json
import logging
import sys
from typing import Any, Final

_MARKER: Final[str] = "_taskmanager_json"
_RESERVED = frozenset(logging.LogRecord("", 0, "", 0, "", None, None).__dict__)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        payload.update(
            {k: v for k, v in record.__dict__.items() if k not in _RESERVED}
        )
        return json.dumps(payload)


def configure_logging(level: int = logging.INFO) -> None:
    """Attach one JSON handler to the `taskmanager` logger. Idempotent."""
    logger = logging.getLogger("taskmanager")
    if any(getattr(h, _MARKER, False) for h in logger.handlers):
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    setattr(handler, _MARKER, True)
    logger.addHandler(handler)
    logger.setLevel(level)
    # propagate stays True on purpose - see below.
```

The runtime notifier then emits exactly D-15's line:

```python
logger.info(
    "Task assignment invitation",
    extra={
        "event": "task_assigned_email",
        "to": recipient_email,
        "subject": subject,
        "body": body,
        "task_id": str(task_id),
    },
)
```

which prints, verified:

```json
{"level":"INFO","logger":"taskmanager.notifications","message":"Task assignment invitation","event":"task_assigned_email","to":"a@b.c","task_id":"..."}
```

grep-able with `docker compose logs api | grep task_assigned_email`.

Four properties that were each checked by execution rather than assumed:

1. **`propagate` must stay `True`.** pytest's `caplog` attaches its handler to the *root* logger; setting
   `propagate=False` on `taskmanager` would stop records reaching it and break the two existing `caplog` assertions
   in `tests/api/test_error_contract.py`. A test with the handler attached and `propagate=True` saw the record
   normally. `[VERIFIED: pytest run]`
2. **No double printing.** `logging.lastResort` fires only when *no* handler was found anywhere on the propagation
   chain. Once our handler exists, root's empty handler list no longer triggers it, and the record is emitted once.
   `[VERIFIED: executed]`
3. **Idempotence is mandatory.** `create_app()` runs hundreds of times across the suite; without the marker check
   each run would add another handler and the line would multiply. The marker version stayed at exactly one handler
   after two calls. `[VERIFIED: pytest run]`
4. **`caplog` defaults to WARNING.** A test asserting on the INFO line must use `caplog.at_level(logging.INFO,
   logger="taskmanager.notifications")`. NOTF-02's "assert without mocks" is better served by the **in-memory
   notifier** recording messages; `caplog` is for the *runtime adapter's* one test.

**Blast radius to decide.** Attaching to the `taskmanager` logger also reformats the existing ERROR record from
`presentation/api/errors/handlers.py` as JSON. That is arguably an improvement and a Phase 7 talking point, but it
is a visible change to existing behaviour. The narrower alternative is to attach to `taskmanager.notifications`
only. **Recommend the package-wide handler** (one place, consistent output, and the 500 log line becomes
machine-readable), with the change named in the plan and in `DECISION_LOG.md`.

**`extra=` collides with reserved `LogRecord` attributes.** Passing `extra={"message": ...}` or `{"name": ...}`
raises `KeyError` at call time. `event`, `to`, `subject`, `body`, `task_id` are all safe.

### Pattern 9: The `0002` Alembic revision

`users.full_name` is `NOT NULL` and developer databases may hold the demo-seed row. The project's conventions
(`0001_baseline.py`) are: constraint names as **literals**, not imports; a real `downgrade()`; `op.f(...)` for names
the naming convention generates.

```python
revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"


def upgrade() -> None:
    # The transient server_default is what lets this run against a database that
    # already holds rows - the demo-seed row every Phase 4 developer machine has.
    # It is dropped immediately: models.py declares no server_default anywhere,
    # and `alembic check` would report a permanent drift if one were left behind.
    op.add_column(
        "users",
        sa.Column("full_name", sa.String(length=100), nullable=False,
                  server_default="Unnamed"),
    )
    op.alter_column("users", "full_name", server_default=None)
    # Foreign keys are not indexed automatically by PostgreSQL. This column is
    # the whole WHERE clause of GET /tasks/assigned-to-me (D-02) and the scan
    # every ON DELETE SET NULL performs.
    op.create_index(op.f("ix_tasks_assignee_id"), "tasks", ["assignee_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_tasks_assignee_id"), table_name="tasks")
    op.drop_column("users", "full_name")
```

**Answering the open question directly: `full_name` needs no `CHECK` constraint.** This project's pattern for text
limits is the `VARCHAR(n)` length, asserted by `test_string_lengths_match_the_entity_caps` against the entity
`ClassVar`. `CHECK` constraints exist only for the two enum columns and the `completed_at`/`status` invariant. A
`ck_users_full_name_length` would be a new pattern with no precedent and a thirteenth constant to keep in sync.

**Tests that must change in the same commit:**

| Test | Why |
|---|---|
| `tests/integration/test_migrations.py::test_the_migration_directory_holds_exactly_one_revision` | There are now two. Rename/rewrite to assert the chain `0001 → 0002` with `head` resolving to `0002`, which is a stronger property than a count. |
| `tests/unit/infrastructure/test_models.py::test_the_naming_convention_produces_every_d12_constraint_name` | Add `IX_TASKS_ASSIGNEE_ID` to `constraints.py` and to this assertion (twelve names become thirteen). |
| `test_string_lengths_match_the_entity_caps` | Add `users.full_name` → `User.FULL_NAME_MAX_LENGTH = 100`. |
| `test_the_models_and_the_migrations_do_not_disagree` (`alembic check`) | Passes only if the `server_default` is dropped. |
| `tests/unit/infrastructure/test_mappers.py` | `user_to_row` / `user_to_entity` / `apply_user_to_row` all gain `full_name`. |

`migrated_database` runs `downgrade base` then `upgrade head`, so a broken `downgrade()` fails the whole
integration suite immediately — which is the right blast radius.

### Pattern 10: Rewriting the actor seam

The `Depends` graph and why it is safe, **verified by execution**:

- `get_current_actor` depends on `Depends(get_uow)`; the route handler also depends on `Depends(get_uow)`.
- FastAPI caches sub-dependencies per request (`use_cache=True` by default), so **both receive the same
  `SqlAlchemyUnitOfWork` object** — one construction per request, confirmed by an instance counter.
- The actor dependency runs *before* the handler, enters the unit of work, reads one row, and exits. `__aexit__`
  sets `_session = None`.
- The use case's later `async with self._uow` is therefore a **re-open, not a re-entry**, which
  `SqlAlchemyUnitOfWork.__aenter__` explicitly allows: *"Entering again after the block has been left is not
  re-entry and stays allowed"*. `tests/unit/infrastructure/test_adapter_ports.py::
  test_a_unit_of_work_can_be_reopened_after_its_block_ended` already pins this.

**Critical:** the actor dependency must reach the unit of work **through `Depends(get_uow)`**, never by calling
`get_uow(request)` directly. The HTTP harness overrides the *dependency*; a direct call would bypass the override
and dial the fictional DSN `postgresql+psycopg://user:pass@localhost:5432/taskmanager`. This single line decides
whether ~120 existing tests pass or hang on a socket.

**Deletions, all of them mechanical:**

| File | Change |
|---|---|
| `src/taskmanager/presentation/api/actor.py` | body replaced; `DEMO_USER_ID` deleted; the `Final`/seed rationale in the docstring replaced; the phrase `"not authentication"` is now *false* and must go (see below) |
| `docker/entrypoint.sh` | step `2b` deleted entirely (lines 97–177); the header's step list returns to 1 / 2 / 3 |
| `tests/unit/presentation/test_actor.py` | four `DEMO_USER_ID` tests and `test_the_module_says_it_is_not_authentication` deleted; replaced by tests of the real decode path |
| `tests/integration/api/test_task_lists.py` | four references (L36, 94, 128, 238, 757) — replace with a test-local `OWNER_ID` constant in the same identifier series |

`grep -rn DEMO_USER_ID` over `src/`, `tests/`, `docker/` returns **exactly those four files** — the blast radius is
small and fully enumerated.

**`test_the_module_says_it_is_not_authentication` is a gate that must be inverted, not deleted quietly.** It asserts
the literal phrase `"not authentication"` appears in `actor.py`'s source. Phase 5 makes the module *be*
authentication. Deleting the test is correct; the plan should say so explicitly so a reviewer does not read it as a
dropped guarantee, and should consider replacing it with a positive assertion (e.g. that the module names the
pinned algorithm nowhere and reaches it only through the port).

### Test harness strategy (the D-11 statement-count question)

`api_client` today overrides **only** `get_uow`. `get_current_actor` runs for real and returns `DEMO_USER_ID` with
zero SQL. `acting_as(app, user_id)` overrides it temporarily and restores afterwards.

| Strategy | ~120 existing tests | 401 legs / anonymous column | Statement counts |
|---|---|---|---|
| **(a)** default-override `get_current_actor` to a fixed `OWNER_ID` in `api_client` | pass unchanged; `acting_as` keeps working verbatim | **impossible** — the override short-circuits the real dependency | stay **1** and **3**; D-11's stated consequence is never observed |
| **(b)** real tokens everywhere | every test must seed a user row before its first request; 404-expecting tests that seed nothing would 401 instead | work | become **2** and **4** |
| **(c) recommended: both, explicitly** | `api_client` keeps the default override (a); a second fixture `authenticated_client` clears the override and sets a real `Authorization` header | work through the second fixture | measured on the second fixture: **2** and **4** |

Under (c), `tests/integration/api/test_statements.py` switches to `authenticated_client` and its two constants
become:

```python
TASK_LISTS_STATEMENTS = ["SELECT", "SELECT"]                       # actor lookup + the grouped LIST-03 statement
TASK_COLLECTION_STATEMENTS = ["SELECT", "SELECT", "SELECT", "SELECT"]  # actor + guard + page + aggregate
```

with a comment naming the new first entry as D-11's cost, exactly as the module already names the three it has.
The property under test is unchanged: **invariance between one row and many**, which is what the
`for_one == for_many` assertions actually check. The non-vacuity test keeps its role.

The D-04 matrix test needs all four columns, so it must use the **unoverridden** client and four real tokens
(owner, assignee, stranger) plus no header (anonymous). That is four `issue_access_token` calls in a fixture and
three seeded user rows.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Extracting `Bearer <tok>` from the header | a manual `request.headers.get("Authorization").split()` | `OAuth2PasswordBearer(auto_error=False)` | it also emits the OpenAPI `securitySchemes` entry that makes Swagger's Authorize button exist (AUTH-02), which a manual parse cannot |
| Parsing the login form | reading `await request.form()` | `Annotated[OAuth2PasswordRequestForm, Depends()]` | gives the documented `application/x-www-form-urlencoded` body in the OpenAPI schema, plus `scope`/`grant_type` handling, plus 422s through the existing handler |
| Password hashing | `hashlib` + a salt, or bcrypt directly | `pwdlib[argon2]` `PasswordHash.recommended()` | Argon2id parameters, encoded-hash format, `check_needs_rehash` and constant-time comparison are all provided; `passlib` is disqualified (CLAUDE.md) |
| JWT encode/decode | building the three base64 segments | PyJWT with `algorithms=[...]` pinned | `alg=none` and algorithm-confusion defences, `exp`/`iat`/`sub` validation and the required-claims option are the whole point |
| Constant-time credential comparison | `==` on hashes | `PasswordHash.verify` (argon2-cffi does it) | a byte-by-byte `==` is a timing oracle |
| Equalising login timing | `asyncio.sleep(random)` | verify against a dummy hash | a sleep adds latency without removing the signal; the dummy hash makes the two paths do identical work — measured 23.4 vs 23.6 ms |
| JSON log lines | `logger.info(json.dumps({...}))` inline | a `logging.Formatter` subclass + `extra=` | a formatter escapes newlines in the task title (log-injection defence) and keeps the message field readable in `caplog` |
| Ownership checks per use case | an `if task_list.owner_id != actor_id` in each of eleven use cases | `access.py`'s two/three functions | ADR-055: eleven chances to forget the second half of the condition, with a silent failure mode |
| Row-level write serialisation | an application-level lock or a version column | `visible_task/owned_task(..., for_update=True)` → `get_for_update` | ADR-058; already built and already proven by `tests/integration/test_concurrent_writes.py` |
| A test clock | `freezegun` | the existing `Clock` port + a fake | PyJWT validates `exp` against `time.time()`, so freezing the clock would not even work for decode — minting a token from a past instant does |

**Key insight:** every "don't hand-roll" item here already has a port declared in `application/ports/`. Phase 5's job
is to write the adapters behind them, not to invent a mechanism.

## Common Pitfalls

### Pitfall 1: `InsecureKeyLengthWarning` + `filterwarnings = error`
**What goes wrong:** PyJWT 2.14 warns on *both* encode and decode when an HMAC key is under 32 bytes. `pytest.ini`
turns every warning into an error, so any test that builds a 16–31 character secret fails with a warning, not an
assertion.
**Why it happens:** `Settings.jwt_secret` has `min_length=16`, which is below PyJWT's 32-byte threshold.
**How to avoid:** every existing test secret is already 32 characters (`"b"*32`, `"a"*32`), CI's is 36 and
`.env.example`'s is 34, so nothing is broken today. Raise `Settings` to `min_length=32` and update
`test_short_secret_is_rejected` + the `.env.example` comment, or explicitly document the 16 floor as a known gap.
**Warning signs:** a test failing with `jwt.warnings.InsecureKeyLengthWarning` and no assertion in the traceback.
`[VERIFIED: executed]`

### Pitfall 2: `pwdlib.verify` argument order — and the stale docstring that gets it wrong
**What goes wrong:** the signature is `verify(password, hash)`. The docstring of `PasswordHash.recommended()` in the
installed 0.3.1 source shows `password_hash.verify(hash, "herminetincture")` — the **reverse** order, left over from
pwdlib < 0.2.
**Why it happens:** the argument order changed and the example was not updated.
**How to avoid:** the project's port already spells it correctly (`verify(self, password, hashed)`). Match it. A
transposed call raises `UnknownHashError` rather than silently returning `False` — but only until someone wraps it
in `except UnknownHashError: return False`, at which point **every login in the system fails**. Catch
`UnknownHashError` narrowly and write a test that a correct password against a correct hash returns `True`.
`[VERIFIED: executed — `verify(hash, password)` raised `pwdlib.exceptions.UnknownHashError`]`

### Pitfall 3: `PasswordHash.verify` raises on an unrecognised hash
**What goes wrong:** verifying against any stored value that is not an Argon2 encoded hash raises
`UnknownHashError`, which is not a `DomainError` and becomes a 500.
**Why it happens:** `PasswordHash.verify` walks its hashers, finds none that `identify()` the string, and raises.
**How to avoid:** the adapter catches `UnknownHashError` and returns `False`. This is not hypothetical — the Phase 4
demo seed wrote `password_hash = "!"`, and a developer database that still holds that row would 500 on a login
attempt against `demo@taskmanager.local`. Verified: `ph.verify("x", "!")` →
`pwdlib.exceptions.UnknownHashError`. `[VERIFIED: executed]`

### Pitfall 4: the actor dependency must go through `Depends(get_uow)`
**What goes wrong:** calling `get_uow(request)` directly inside `get_current_actor` bypasses
`app.dependency_overrides` and opens a connection to the fictional DSN the harness sets.
**Why it happens:** `dependencies.py`'s `get_uow` is a plain callable, so it is *tempting* to call it.
**How to avoid:** declare `uow: UnitOfWorkDependency` as a parameter. FastAPI caches it, so the handler and the
actor share one object and one construction per request.
**Warning signs:** integration tests hanging or failing with a connection error rather than an assertion.
`[VERIFIED: caching behaviour executed]`

### Pitfall 5: the unit of work is single-entry, re-openable
**What goes wrong:** if the actor dependency *held* the block open (e.g. a `yield` dependency), the use case's
`async with` would be a second entry and `__aenter__` would raise `RuntimeError`.
**How to avoid:** the actor dependency enters and exits within itself. `dependencies.py::get_uow`'s docstring
already argues at length why a `yield` dependency is wrong here.

### Pitfall 6: `EmailStr` lowercases the domain only
**What goes wrong:** assuming `EmailStr` gives a canonical address and dropping the entity's `.lower()`.
**Measured:** `Ana@Example.COM` → `Ana@example.com`; `  ana@example.com  ` → `ana@example.com`.
**How to avoid:** keep both. `EmailStr` validates format, trims and normalises the domain half; `User.__post_init__`
lowercases the whole thing, which is the form `uq_users_email_lower` and `get_by_email` both rely on. The two are
complementary and the plan should say so, because it looks like duplication. `[VERIFIED: executed]`

### Pitfall 7: `SecretStr` must not cross into the application layer
**What goes wrong:** putting `SecretStr` on `RegisterUserCommand` would import Pydantic into the application layer.
ADR-020 makes commands frozen slotted dataclasses, and `.importlinter` deliberately leaves `pydantic` off the
application forbidden list *as a convention, not a gate* — so nothing would fail; the convention would just be
silently broken.
**How to avoid:** the schema declares `password: SecretStr`; `to_command()` calls `.get_secret_value()` and passes a
plain `str`. Verified that `SecretStr` masks in `repr`, `str()`, `model_dump()` and `model_dump_json()` — so a
router that accidentally echoed the model would leak `"**********"`, not the password. `[VERIFIED: executed]`

### Pitfall 8: `python-multipart` is an import-time requirement
**What goes wrong:** without it FastAPI raises at *route declaration* time when it sees `OAuth2PasswordRequestForm`,
so the whole application fails to build — not just the login route.
**How to avoid:** it is already pinned and installed. The consequence is that this failure mode, if it ever appears,
looks like "`create_app` is broken" rather than "login is broken".

### Pitfall 9: `FakeUserRepository.list_all` returns insertion order
**What goes wrong:** `tests/unit/application/fakes.py::FakeUserRepository.list_all` is
`return list(self.stored.values())` — **not** sorted. The real adapter orders by `created_at, id`. A D-13 ordering
assertion would pass against the fake and could fail over HTTP.
**Why it matters:** this is exactly the divergence `FakeTaskRepository.list_for_task_list` and
`FakeTaskListRepository.list_for_owner` were both fixed for, with a long comment explaining it. The user fake was
missed.
**How to avoid:** fix it in the same plan that adds `ListUsers`:
`sorted(self.stored.values(), key=lambda u: (u.created_at, u.id))`. Same for the new `list_for_assignee` fake.

### Pitfall 10: `starlette.testclient.TestClient` now warns
**What goes wrong:** importing `starlette.testclient` (or `fastapi.testclient`) emits
`StarletteDeprecationWarning: Using 'httpx' with 'starlette.testclient' is deprecated; install 'httpx2' instead`,
which `filterwarnings = error` turns into a hard import failure.
**How to avoid:** the project already uses `httpx.AsyncClient(transport=ASGITransport(app=app))` everywhere. Do not
reach for `TestClient` for the "quick auth test". `[VERIFIED: executed — the import raised]`

### Pitfall 11: `mypy --strict` over PyJWT and pwdlib
Both ship `py.typed` (`jwt/py.typed`, `pwdlib/py.typed`), so there are no stubs to add. But `jwt.decode` returns
`dict[str, Any]`, so `payload["sub"]` is `Any`. `warn_unreachable = true` is on; write
`UUID(payload["sub"])` inside the `try` and let `ValueError`/`TypeError` be caught rather than adding an
`isinstance` branch no test can reach — `disallow_any_expr` is not part of `strict`, so the `Any` is accepted.

### Pitfall 12: Python 3.13 (container) vs 3.14 (host) coverage divergence
Already recorded in `.planning/STATE.md`: the two runs report different statement totals (PEP 649) and the container
run is ~0.8 pp lower. Phase 6 owns the fix (TEST-03). Phase 5 must not "solve" it with a `pragma` or an `omit`; if
new auth code shows a host/container gap, record it the way Phase 4 did and hand it on.

### Pitfall 13: ordering of the ownership guard and the assignee lookup
**What goes wrong:** looking up `command.assignee_id` before checking that the caller owns the list turns
`PUT .../assignee` into a user-existence oracle for a stranger — they get 404 `user_not_found` for a bad id and
404 `task_not_found` for a good one, distinguishing the two.
**How to avoid:** `owned_task(...)` first, always. (The disclosure is harmless for an *owner*, because `GET /users`
lists everyone — D-08 says so — but it must not be reachable by someone who cannot see the task.)

### Pitfall 14: the AST gate's `REQUIRED_SCANNED_MODULES`
Every new module under `presentation/api` must be added to that frozenset in the same commit that creates it, or
the gate's non-vacuity guard still passes while the new module is scanned only incidentally. The set today names
`actor.py`, `dependencies.py`, `health.py`, `routers/{task_lists,tasks}.py`, `schemas/{task_lists,tasks}.py`.
Phase 5 adds at least `routers/auth.py`, `routers/users.py`, `routers/assignments.py`, `schemas/auth.py`,
`schemas/users.py`.

## The full permission matrix (D-04)

Every route that exists after Phase 5, every role, the expected status. `owner` owns the list; `assignee` is
assigned the addressed task but owns nothing; `stranger` is an authenticated user with no relationship;
`anonymous` sends no `Authorization` header. This table is the one the parametrized HTTP test lifts verbatim.

| # | Method | Path | owner | assignee | stranger | anonymous |
|---|--------|------|-------|----------|----------|-----------|
| 1 | GET | `/health` | 200 | 200 | 200 | **200** (must stay open — the compose healthcheck reads it) |
| 2 | POST | `/api/v1/auth/register` | 201 | 201 | 201 | **201** (open by definition) |
| 3 | POST | `/api/v1/auth/login` | 200 | 200 | 200 | **200 / 401** (open; 401 on bad credentials) |
| 4 | GET | `/api/v1/auth/me` | 200 | 200 | 200 | **401** |
| 5 | GET | `/api/v1/users` | 200 | 200 | 200 | **401** |
| 6 | POST | `/api/v1/task-lists` | 201 | 201 | 201 | **401** |
| 7 | GET | `/api/v1/task-lists` | 200 (own only) | 200 (empty) | 200 (empty) | **401** |
| 8 | GET | `/api/v1/task-lists/{l}` | 200 | **404** | 404 | **401** |
| 9 | PATCH | `/api/v1/task-lists/{l}` | 200 | **404** | 404 | **401** |
| 10 | DELETE | `/api/v1/task-lists/{l}` | 204 | **404** | 404 | **401** |
| 11 | POST | `/api/v1/task-lists/{l}/tasks` | 201 | **404** (list-shaped, 04-06) | 404 | **401** |
| 12 | GET | `/api/v1/task-lists/{l}/tasks` | 200 | **404** (list-shaped) | 404 | **401** |
| 13 | GET | `/api/v1/task-lists/{l}/tasks/{t}` | 200 | **200** | 404 | **401** |
| 14 | PATCH | `/api/v1/task-lists/{l}/tasks/{t}` | 200 | **403** | 404 | **401** |
| 15 | DELETE | `/api/v1/task-lists/{l}/tasks/{t}` | 204 | **403** | 404 | **401** |
| 16 | PATCH | `/api/v1/task-lists/{l}/tasks/{t}/status` | 200 | **200** | 404 | **401** |
| 17 | PUT | `/api/v1/task-lists/{l}/tasks/{t}/assignee` | 200 | **403** | 404 | **401** |
| 18 | DELETE | `/api/v1/task-lists/{l}/tasks/{t}/assignee` | 200 | **403** | 404 | **401** |
| 19 | GET | `/api/v1/tasks/assigned-to-me` | 200 (own assignments) | 200 (the task) | 200 (empty) | **401** |

Rows 1–3 are the three open routes; the matrix test should assert their openness rather than skip them, so "which
routes are unauthenticated" is a fact the table states. Rows 8–12 are D-01's "the list stays invisible"; rows 13–18
are D-03's split. Row 19 is D-02.

Auxiliary error legs, not columns of the matrix but owed by the same phase:

| Case | Status | Code |
|---|---|---|
| malformed / badly-signed / expired token, any authenticated route | 401 | `authentication_failed` (identical body for all three, D-11) |
| token whose `sub` names a deleted user | 401 | `authentication_failed` (same body) |
| register with an already-registered email | 409 | `email_already_registered` |
| register with a password outside 8–128 | 422 | `validation_error` (domain), field `password` |
| register with an unknown body key | 422 | `validation_error` (Pydantic `extra_forbidden`) |
| login with a wrong password **or** an unknown email | 401 | identical status and body (D-12) |
| assign to a non-existent `assignee_id` (as the owner) | 404 | `user_not_found` |
| `assignee_id` in a `POST .../tasks` body | 422 | `validation_error` (`extra_forbidden`, D-06) |

## Runtime State Inventory

This phase deletes a seeded database row and an OS-visible startup step, so the inventory applies.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | **`users` row `00000000-0000-4000-8000-00000000de00`** (`demo@taskmanager.local`, `password_hash = "!"`) exists in every developer's `taskmanager` volume and in any `taskmanager_test` database not rebuilt since Phase 4. It may own `task_lists` rows created during Phase 4 manual testing. | Code edit only — the entrypoint step is deleted so no new row is written. **No data migration**: deleting the row would cascade-delete any lists made under it, and the `0002` revision's transient `server_default` already lets the `NOT NULL` column be added over it. Developers who want a clean slate run `make down` + volume removal; Phase 7's README should say so. Note the row cannot become a live account: `"!"` is not an Argon2 hash, and `PasswordHash.verify` raises `UnknownHashError` on it, which the adapter turns into `False` (Pitfall 3). |
| Live service config | **None** — no external service holds configuration for this project. Verified: `docker-compose.yml` defines only `db`, `api` and a profiled `test` service, all built from this repo. |
| OS-registered state | **None** — no scheduled task, no `launchd` plist, no `pm2` entry. Verified: the only process manager is `docker compose`, whose definitions are in git. |
| Secrets / env vars | `JWT_SECRET`, `JWT_ALGORITHM`, `JWT_EXPIRE_MINUTES` already exist in `Settings`, `.env.example`, the developer's un-committed `.env`, and `.github/workflows/ci.yml` (`JWT_SECRET: ci-only-secret-not-a-real-credential`, 36 chars). **No new key is needed.** If the `min_length` floor is raised to 32 (§Alternatives), every existing value already satisfies it — verified by counting. The Docker `test` service inherits `.env` via `env_file`. |
| Build artifacts | `src/taskmanager.egg-info` / the editable install: no rename occurs, so nothing goes stale. `.mypy_cache`, `.grimp_cache`, `.import_linter_cache` all key on content. **No action.** |

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Docker engine | `make docker-test`, cold-start evidence (D-14) | ✓ | 29.2.0, daemon up | — |
| PostgreSQL (test DB) | every integration test (D-03: no auto-skip) | ✓ | **18.4**, reachable at `localhost:5432/taskmanager_test` | — |
| Python (host) | `make test`, `make lint` | ✓ | 3.14.3 | — |
| Python (container) | CI, `make docker-test` | ✓ (image) | 3.13 per `Dockerfile` | — |
| PyJWT / pwdlib / python-multipart / email-validator | this whole phase | ✓ | pinned + installed in `.venv` | — |
| `psql` CLI | *nothing* — the project never shells out to it | ✗ | — | `docker compose exec db psql` if a human wants it |
| `alembic` on the host PATH | nothing (it is invoked through `.venv/bin/alembic` and inside the container) | ✗ on PATH, ✓ in `.venv` | 1.20.0 | — |
| `slopcheck` | the package audit above | ✓ | scan ran; `pip` shell-out failed harmlessly | — |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** `psql` and a PATH-level `alembic` — neither is used by any gate.

## Validation Architecture

`workflow.nyquist_validation` is not disabled (`.planning/config.json` carries no such key), so this section applies.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 + pytest-asyncio 1.4.0 (`asyncio_mode = auto`) + pytest-cov 7.1.0 |
| Config file | `pytest.ini` (brief-mandated literal file; `[tool.pytest.ini_options]` in `pyproject.toml` would be silently ignored) |
| Quick run command | `.venv/bin/pytest tests/unit -q --no-cov` (no database, sub-second) |
| Full suite command | `make test` (requires a reachable PostgreSQL, D-03) or `make docker-test` |
| Current baseline | 643 passed, 100% coverage (host), gate at `--cov-fail-under=75` |

### Phase Requirements → Test Map

| Req | Behaviour | Test type | Automated command | File exists? |
|-----|-----------|-----------|-------------------|--------------|
| AUTH-01 | register → 201, profile only, no hash in the body | integration HTTP | `pytest tests/integration/api/test_auth.py -k register -x` | ❌ Wave 0 |
| AUTH-01 | duplicate email → 409 `email_already_registered` | integration HTTP | `pytest tests/integration/api/test_auth.py -k duplicate -x` | ❌ Wave 0 |
| AUTH-01 | `full_name` persists and round-trips | integration | `pytest tests/integration/test_repositories_users.py -k full_name -x` | ✅ file exists, case ❌ |
| AUTH-02 | login → token; `token_type == "bearer"` | integration HTTP | `pytest tests/integration/api/test_auth.py -k login_returns -x` | ❌ Wave 0 |
| AUTH-02 | OpenAPI carries `securitySchemes.OAuth2PasswordBearer` and each protected route carries `security` | unit (reads `app.openapi()`, ADR-057) | `pytest tests/unit/presentation/test_security_scheme.py -x` | ❌ Wave 0 |
| AUTH-03 | missing / malformed / expired / wrong-signature / unknown-subject token → the *same* 401 problem+json | integration HTTP, parametrized | `pytest tests/integration/api/test_auth.py -k unauthenticated -x` | ❌ Wave 0 |
| AUTH-03 | 401 carries `WWW-Authenticate: Bearer` | integration HTTP | same module | ❌ Wave 0 |
| AUTH-04 | hashing runs off the event loop | unit (assert the adapter awaits a thread-offloaded call; or assert the loop is not blocked) | `pytest tests/unit/infrastructure/test_passwords.py -x` | ❌ Wave 0 |
| AUTH-04 | real adapter: hash → verify True, wrong → False, non-Argon2 → False | unit (one real Argon2 call, ~60 ms) | same module | ❌ Wave 0 |
| AUTH-04 | decode refuses `alg=none` and a token signed with another secret | unit | `pytest tests/unit/infrastructure/test_tokens.py -x` | ❌ Wave 0 |
| AUTH-04 | **expired token**, driven by a fake `Clock` set in the past — no sleep, no freezegun | unit + integration HTTP | `pytest -k expired -x` | ❌ Wave 0 |
| AUTH-04 | unknown email and wrong password return byte-identical bodies | integration HTTP (compare the two responses) | `pytest tests/integration/api/test_auth.py -k indistinguishable -x` | ❌ Wave 0 |
| AUTH-05 | `/auth/me` returns the caller's profile, never the hash | integration HTTP | `pytest tests/integration/api/test_auth.py -k me -x` | ❌ Wave 0 |
| AUTH-06 | **the whole 19-row × 4-column matrix** | integration HTTP, one parametrized test over the *unoverridden* client | `pytest tests/integration/api/test_permission_matrix.py -x` | ❌ Wave 0 |
| AUTH-06 | `access.py` per-role unit tests: assignee sees, assignee is refused with `AuthorizationError`, stranger gets `TaskNotFoundError` | unit with fakes | `pytest tests/unit/application/test_access.py -x` | ✅ file exists, cases ❌ |
| ASGN-01 | owner assigns; owner unassigns; non-existent assignee → 404 | integration HTTP + unit | `pytest -k assign -x` | ❌ Wave 0 |
| ASGN-01 | **D-18 concurrency:** owner `PATCH` vs assignee `PATCH .../status` on the same task serialise | integration, two connections | `pytest tests/integration/test_concurrent_writes.py -k owner_and_assignee -x` | ✅ file exists, case ❌ |
| ASGN-01 | every new write path loaded through `get_for_update` | unit, asserts `held_for_update` on the fake | `pytest tests/unit/application/test_write_paths_hold_what_they_change.py -x` | ✅ file exists, cases ❌ |
| ASGN-02 | `TaskResponse.assignee_id` present after assign, null after unassign | integration HTTP | `pytest -k assignee_id -x` | ❌ Wave 0 |
| ASGN-02 | assignee: `GET` 200, `PATCH status` 200, `PATCH` 403, `DELETE` 403 | covered by the matrix | — | ❌ Wave 0 |
| ASGN-03 | `GET /users` returns id, full_name, email for every user, ordered `created_at, id` | integration HTTP | `pytest tests/integration/api/test_users.py -x` | ❌ Wave 0 |
| NOTF-01 | assigning calls `EmailNotifier.send_task_assigned` exactly once, **after** the commit | unit with the in-memory notifier + a `FakeUnitOfWork` that records commit order | `pytest tests/unit/application/test_assign_task.py -k notifies -x` | ❌ Wave 0 |
| NOTF-01 | D-07: re-assigning the same user sends **no** second email | unit | same module | ❌ Wave 0 |
| NOTF-02 | the runtime adapter emits one JSON line at INFO carrying `event`, `to`, `subject`, `body`, `task_id` | unit with `caplog.at_level(INFO)` + `json.loads` of the formatted record | `pytest tests/unit/infrastructure/test_notifier.py -x` | ❌ Wave 0 |
| NOTF-02 | the in-memory adapter records messages (no mocks anywhere in the suite) | unit | `pytest tests/unit/application/test_fakes.py -k notifier -x` | ✅ file exists, case ❌ |
| NOTF-03 | **a notifier that raises still leaves the assignment committed and the response 200** | unit + integration HTTP | `pytest -k notifier_failure -x` | ❌ Wave 0 |
| D-11 | statement counts are 2 and 4 under real auth, and invariant between one row and many | integration | `pytest tests/integration/api/test_statements.py -x` | ✅ file exists, must be **updated** |
| D-14 | cold start on an empty volume: register → Authorize → assign → the logged email | evidence capture under `evidence/` | `docker compose down -v && docker compose up -d` + a scripted walk-through | ❌ Wave 0 |
| ADR-051 | no new presentation module raises or imports `HTTPException` | architecture (AST) | `pytest tests/architecture/test_routers_raise_no_http_exception.py -x` | ✅ exists; `REQUIRED_SCANNED_MODULES` must grow |
| layers | `jwt`/`pwdlib` never reach `application` or `domain` | architecture | `make arch` / `pytest tests/architecture/test_layer_boundaries.py -x` | ✅ exists, contract already names them |
| 0002 | migration up/down round-trips; models and migrations agree | integration | `pytest tests/integration/test_migrations.py -x` | ✅ exists, one test must change |

### Sampling Rate

- **Per task commit:** `.venv/bin/pytest tests/unit -q --no-cov` plus the specific integration module the task
  touched.
- **Per wave merge:** `make lint && make typecheck && make arch && make test` (the same four the pre-commit hook
  runs).
- **Phase gate:** full `make test` **and** `make docker-test` green, plus the cold-start evidence capture, before
  `/gsd:verify-work`.

### Wave 0 Gaps

- [ ] `tests/integration/api/test_auth.py` — register / login / me / the 401 legs (AUTH-01..05)
- [ ] `tests/integration/api/test_users.py` — `GET /users` (ASGN-03)
- [ ] `tests/integration/api/test_assignment.py` — assign / unassign / `assigned-to-me` (ASGN-01, D-02)
- [ ] `tests/integration/api/test_permission_matrix.py` — the 19×4 table (AUTH-06, D-04)
- [ ] `tests/unit/infrastructure/test_tokens.py`, `test_passwords.py`, `test_notifier.py` — the three new adapters
- [ ] `tests/unit/application/test_register_user.py`, `test_login.py`, `test_authenticate_actor.py`,
      `test_assign_task.py`, `test_unassign_task.py`, `test_list_users.py`, `test_list_assigned_tasks.py`
- [ ] `tests/unit/presentation/test_security_scheme.py` — the OpenAPI security assertions (ADR-057: read
      `app.openapi()`, never `app.routes`)
- [ ] `tests/unit/application/fakes.py` — `FakePasswordHasher`, `FakeTokenService`, `InMemoryEmailNotifier`,
      `FakeClock`; **and the `list_all` ordering fix** (Pitfall 9)
- [ ] `tests/integration/conftest.py` — `authenticated_client` fixture and a token helper; `acting_as` kept
- [ ] Framework install: **none needed**

## Security Domain

### Applicable ASVS (v5 L1) categories

| ASVS category | Applies | Standard control in this phase |
|---------------|---------|--------------------------------|
| V2 Authentication | **yes** | Argon2id via `pwdlib[argon2]` (`m=65536,t=3,p=4` — at or above the OWASP minimum of 19 MiB/t=2); 8–128 character policy with no composition rules (NIST 800-63B); no default secret; identical refusal for unknown-email and wrong-password |
| V3 Session Management | **yes (partial)** | Stateless bearer JWT with a bounded `exp` (default 30 min). **No revocation and no refresh** — AUTH-07 is explicitly v2. This is a real L1 gap and must be listed as known future work in the README, not glossed over |
| V4 Access Control | **yes** | `access.py` as the single decision point; deny-by-default (every route carries `CurrentActor`); IDOR closed by the 404/403 matrix, tested as a table rather than per route |
| V5 Input Validation | **yes** | Pydantic `extra="forbid"` on every request body (mass-assignment closed); domain `require_text`/`require_utc`/`require_password` for policy; NUL refused; enum-typed path/query values |
| V6 Cryptography | **yes** | PyJWT HS256 with a **pinned** `algorithms=[...]`; secret ≥16 (recommend 32) from the environment; nothing hand-rolled; no key material in source |
| V7 Error Handling & Logging | **yes** | One RFC 9457 body shape; the 500 body is fixed and carries no internals; the validation handler strips the submitted value; the notification line is JSON-encoded so a title cannot inject a log record |
| V8 Data Protection | partial | `password_hash` has no route to a response model — the `User` entity has no plaintext field at all, by construction |
| V13 API | **yes** | OpenAPI declares every refusal leg per route; no verb-tunnelling; the assignment side effect has its own door |

### Threat list for `<threat_model>` blocks

| # | Threat | STRIDE | Mitigation (and the gate that proves it) |
|---|--------|--------|------------------------------------------|
| T-5-01 | **Algorithm confusion / `alg=none`** — attacker forges a token with `"alg":"none"` or swaps HS/RS | Spoofing | `algorithms=[self._algorithm]` pinned from settings, never read from the token. Verified: `alg=none` → `InvalidAlgorithmError`. Test: a hand-built `alg=none` token is a 401 |
| T-5-02 | **Weak signing key** — a 16-character `JWT_SECRET` is brute-forceable offline against any issued token | Spoofing | `Settings` floor (16 today, **recommend 32**); PyJWT warns below 32; `.env.example` tells the operator to generate one with `secrets.token_urlsafe(32)`. Test: `test_short_secret_is_rejected` |
| T-5-03 | **Secret in the image, the logs or CI output** | Information disclosure | No secret has a default in code; `.env` is git-ignored and excluded from the build context (`.dockerignore`); the entrypoint's per-attempt line prints the exception *class name only*; CI's value is a literal marked `ci-only-secret-not-a-real-credential`. Gate: `test_env_example_documents_every_field` + a grep-for-secrets check in review |
| T-5-04 | **Token echoed into a log or an error body** | Information disclosure | `handle_unexpected_error` logs only method and path; `handle_validation_error` keeps only `loc`/`msg`/`type` — verified, the submitted value never reaches the body; the notification line carries no token. Test: a request with a bogus token produces a 401 body that does not contain the token string |
| T-5-05 | **User enumeration via login** | Information disclosure | Identical status, identical body, and equal work: the unknown-email path verifies against a dummy hash (measured 23.4 ms vs 23.6 ms). Test: the two responses are compared byte-for-byte |
| T-5-06 | **User enumeration via register (409)** — *this one is required by AUTH-01 and therefore conceded, not mitigated* | Information disclosure | The brief mandates 409 on a duplicate email, which is by construction an oracle. What is done instead: the error carries **no address** (`EmailAlreadyRegisteredError.__init__` takes no argument, by design) so nothing is echoed into a body or a log; `GET /users` already discloses every address to any authenticated user (D-13), so the residual leak is to *unauthenticated* callers only. **Document this honestly in `DECISION_LOG.md` and in the README's security note** — "we chose the requirement over the property, and here is the bound on the damage" — rather than claiming enumeration is prevented |
| T-5-07 | **Password-length DoS against Argon2** | DoS | The 128-character cap is validated **before** the hash call. Measured: Argon2 pre-hashes with Blake2b so a 100 000-character password still costs 23.8 ms — the real bound is request-body size, but the cap makes the intent explicit. Test: a 129-character password is a 422 and no hash is computed |
| T-5-08 | **Login brute force** — no rate limiting | DoS / Spoofing | **Not mitigated.** Explicitly deferred (CONTEXT: "Login throttling / lockout … v2"). Argon2's 25 ms floor is an incidental throttle (~40 attempts/s/core), not a control. Must appear in the README's future-work list |
| T-5-09 | **Mass assignment on register** — a client sends `id`, `created_at`, `is_admin` | Elevation of privilege | `extra="forbid"` on the register schema (verified: `extra_forbidden`); the id is generated by the use case with `uuid4()`, the timestamps by the `Clock` port |
| T-5-10 | **Mass assignment of `assignee_id` through `PATCH /tasks/{id}`** | Tampering | `TaskPatchRequest` is `extra="forbid"` and has no such field; D-05 gives assignment its own door. Test: `{"assignee_id": ...}` in the patch body is a 422 naming the key |
| T-5-11 | **IDOR across the new routes** — a stranger reads or writes someone else's task via `/tasks/{id}` | Information disclosure / Tampering | `access.py`; the nested path's parent segment always travels into the command (ADR-050); `assigned-to-me` filters on the *token's* subject, never on a client-supplied id. Test: the matrix, all 19 rows |
| T-5-12 | **User-existence oracle via `PUT .../assignee`** | Information disclosure | Ownership is checked before the assignee lookup (Pitfall 13), so only an owner — who can already call `GET /users` — can distinguish the two 404s |
| T-5-13 | **Log injection via the task title or `full_name`** — a title containing `\n{"level":"INFO",...}` forges a log record | Tampering | The JSON formatter runs every field through `json.dumps`, which escapes newlines; the record is one line by construction. NUL is already refused by `domain/validation.py`. Test: a task titled with an embedded newline produces exactly one parseable JSON line |
| T-5-14 | **Email header injection** | Tampering | Not applicable *yet* — nothing is transmitted (NOTF-02: "sends nothing real"). Must be re-raised the day a real SMTP adapter appears; note it in the adapter's docstring so the deferral is visible |
| T-5-15 | **Privilege retention after deletion** — a token outlives its user row | Spoofing | D-11: the user row is confirmed on **every** request, so a deleted user's live token is a 401 from the next call. That is precisely what the extra `SELECT` buys, and the test that proves it is worth naming |
| T-5-16 | **Timing side channel in token comparison** | Information disclosure | HMAC verification is `hmac.compare_digest` inside PyJWT; nothing in this project compares a token by `==` |
| T-5-17 | **Assignment as a write amplifier** — two writers race on one task row | Tampering | ADR-058: every new write path goes through `for_update=True`. Test: the new owner-vs-assignee case in `test_concurrent_writes.py` |

## Open Questions

1. **What does `Location` on `POST /auth/register` point at? (D-09 locks its presence.)**
   - What we know: D-09 says 201 with the profile "plus a `Location` header". `TaskResponse`'s create route uses
     `request.url_for("get_task", ...)`.
   - What's unclear: there is no `GET /users/{id}` route in this phase, so no canonical URL for the created user
     exists. `GET /auth/me` identifies the resource only for the authenticated owner, and the caller is not yet
     authenticated when they read the header.
   - Recommendation: `Location: /api/v1/auth/me`, with one sentence in the route description saying it becomes
     readable after login. The alternative — adding `GET /users/{id}` — is scope the phase boundary does not list.
     **Confirm with the user before planning**, because D-09 is locked and this is the only defensible reading.

2. **Does `Settings.jwt_secret`'s `min_length` move from 16 to 32?**
   - What we know: PyJWT emits `InsecureKeyLengthWarning` below 32 bytes for HS256, and `filterwarnings = error`
     makes that fatal in tests. Every value currently in the repo is ≥32.
   - What's unclear: CONTEXT says the JWT settings "already exist … with no default in code" — it does not lock the
     floor, but changing an existing validated setting is a visible decision.
   - Recommendation: raise to 32 and update `test_short_secret_is_rejected`'s assertion string and `.env.example`'s
     comment. Record as an ADR naming RFC 7518 §3.2.

3. **Does `PasswordHasher` gain a dummy-verify method?**
   - What we know: D-12's timing equalisation needs an Argon2 verify against a throwaway hash, and computing that
     hash requires `pwdlib`, which the application layer may not import.
   - What's unclear: CONTEXT says the ports "keep their shape unless research proves a need". This is that need, but
     it is a port change and the planner should not make it silently.
   - Recommendation: add one method to `PasswordHasher` (e.g. `async def dummy_verify(self, password: str) -> None`)
     and say in the port docstring that it exists to make the two login paths cost the same. Update
     `tests/unit/application/test_ports.py` and `test_adapter_ports.py`.

4. **Which harness strategy, and therefore which statement counts?**
   - What we know: option (c) — default override plus a real-token fixture — keeps ~120 tests untouched and still
     lets D-11's cost be measured. Options (a) and (b) each fail one of CONTEXT's two requirements.
   - Recommendation: (c), with `test_statements.py` moved to the real-token fixture and its two constants updated to
     `["SELECT","SELECT"]` and four `"SELECT"`s, each newly-added entry named in the comment the module already has
     the habit of writing.

5. **Should `ListAssignedTasks` be visible in the OpenAPI `tasks` tag or its own?**
   - Purely cosmetic; no evidence either way. Recommendation: a third tag (`assignments`) so `/docs` groups the
     three assignment-related operations together, matching how `task lists` and `tasks` are already split.

## State of the Art

| Old approach | Current approach | When changed | Impact here |
|---|---|---|---|
| `python-jose` for JWT | **PyJWT** | FastAPI docs switched after CVE-2024-33663/33664; python-jose dormant since 2025-05 | Already the project's choice; do not re-litigate |
| `passlib[bcrypt]` | **`pwdlib[argon2]`** | passlib's last release is 2020-10; it imports the stdlib `crypt` module removed in Python 3.13 | Already the project's choice |
| `jwt.decode(token, key)` with no `algorithms` | `algorithms=[...]` **required** | PyJWT 2.0 | The pinned list is now mandatory, not advisory |
| `sub` may be any JSON value | `sub` **must be a string** | PyJWT ≥ 2.10 raises `InvalidSubjectError` on decode | `str(subject)` on encode is not cosmetic |
| `enforce_minimum_key_length` absent | present, default `False`, warns instead | PyJWT 2.14 (`_get_default_options`) | A short secret warns today and could be made fatal with one option |
| `AsyncClient(app=app)` | `AsyncClient(transport=ASGITransport(app=app))` | httpx 0.28 | Already used throughout |
| `starlette.testclient.TestClient` with httpx | deprecated in favour of `httpx2` | Starlette 1.6 | Under `filterwarnings = error` the import itself fails — stay on `AsyncClient` |

**Deprecated / outdated:**
- `python-jose`, `passlib` — disqualified by CLAUDE.md with verified reasons.
- `fastapi.testclient.TestClient` on this Starlette version — warns, therefore errors.
- The `verify(hash, password)` argument order shown in pwdlib's own `recommended()` docstring — stale since 0.2.

## Assumptions Log

| # | Claim | Section | Risk if wrong |
|---|-------|---------|---------------|
| A1 | Swagger UI resolves a *relative* `tokenUrl` against the OpenAPI document's base URL; the absolute form is therefore equivalent here and safer | Pattern 1 | Low — the recommendation is the absolute form, which is unambiguous. If wrong, Authorize posts to the wrong path and AUTH-02 fails visibly in the cold-start rehearsal |
| A2 | `flake8-bugbear` in the installed configuration flags a bare `except Exception` (the entrypoint already carries a `# noqa: BLE001`) | Pattern 7 | Low — `make lint` settles it in seconds; the plan should run lint rather than pre-commit a `noqa` |
| A3 | Argon2's `m=65536,t=3,p=4` defaults meet current OWASP guidance for Argon2id | Security Domain V2 | Low — they exceed the frequently-cited 19 MiB / t=2 minimum. If a reviewer disagrees, the parameters are one constructor argument away |
| A4 | The demo-seed row is the only pre-existing `users` row on developer machines | Runtime State Inventory | Low — the `server_default` approach in `0002` is correct for *any* number of pre-existing rows, so the assumption does not affect the migration's correctness |
| A5 | No external service (monitoring, tunnel, CI secret store) holds project configuration beyond what is in git + `.env` | Runtime State Inventory | Low — `docker-compose.yml` and `ci.yml` were both read in full |

Everything else in this document is tagged `[VERIFIED: executed]`, `[VERIFIED: source read]` or
`[CITED: <url>]` and was checked in this session against the exact pinned versions.

## Disagreements with CONTEXT.md

Per ADR-053 the context wins; these are reported, not resolved.

1. **D-11's statement-count consequence is conditional, and CONTEXT states it as unconditional.** "Every
   authenticated request costs one more indexed `SELECT`, so the measured statement counts … move by one" is true of
   the *application*, but the existing `test_statements.py` runs against a harness whose actor dependency reads
   nothing. Unless the harness is changed to issue real tokens, the numbers in that file will **not** move and the
   test will keep passing at 1 and 3. The planner must make the harness change deliberately, or D-11's stated
   consequence never materialises.

2. **"The ports … keep their shape unless research proves a need" vs. D-12's timing equalisation.** Research
   proves the need: the dummy hash cannot be produced by the application layer (`pwdlib` is forbidden there) and
   hard-coding an Argon2 string in source is worse. `PasswordHasher` should gain one method. Open Question 3.

3. **D-09's `Location` header has no resource to point at.** There is no user-by-id route in this phase. Open
   Question 1 — needs a user decision, not a research answer.

4. **`access.py`'s module docstring contains a claim Phase 5 falsifies.** It states, as a grep-checkable property,
   that `AuthorizationError` is *"deliberately not named anywhere in this file, prose included"*. CONTEXT's
   carried-forward section cites that same module as the single home of the rule and expects the 403 to live there.
   Both cannot hold; the docstring must be rewritten in the commit that adds the 403 leg, and the rewrite should say
   *why* the old claim was there and why it retired.

5. **CONTEXT says `test_change_task_status.py` "deliberately inverted the assignee test" and Phase 5 "flips it
   back".** Verified present — but note the flip is not a one-line inversion: with the `visible_task` change the
   assignee's status request also drops from two `SELECT`s to one, so any count assertion in that module changes
   with it.

## Sources

### Primary (HIGH confidence — executed or read in this session)
- `.venv/lib/python3.14/site-packages/jwt/api_jwt.py`, `jwt/exceptions.py`, `jwt/warnings.py` (PyJWT 2.14.0) —
  `_get_default_options`, `_validate_sub`, `_validate_exp`, the exception hierarchy
- Live probe against PyJWT 2.14.0 — `alg=none`, wrong signature, expiry, leeway, non-string `sub`, required claims,
  garbage input, short-key warning, `enforce_minimum_key_length`
- `.venv/.../pwdlib/_hash.py`, `pwdlib/hashers/argon2.py` (0.3.1) — `verify(password, hash)` order,
  `UnknownHashError`, `check_needs_rehash`
- Live probe against pwdlib 0.3.1 + argon2-cffi 25.1.0 — timings, hash length, transposed-argument behaviour, the
  `"!"` placeholder case, cheap-hasher cost
- `.venv/.../fastapi/security/oauth2.py` (FastAPI 0.141.1) — `OAuth2PasswordBearer.__call__` with `auto_error=False`
- Live probe: a FastAPI app using this repo's own `register_exception_handlers` — the 401 problem+json body,
  `WWW-Authenticate`, the 422 form body, `securitySchemes`, per-route `security`, dependency caching
- `.venv/.../uvicorn/config.py` L83–113 (uvicorn 0.53.0) — `LOGGING_CONFIG` names only the `uvicorn*` loggers
- Live probe: logging propagation, `lastResort`, handler idempotence, `caplog` under `propagate=True` (run as a
  real pytest session)
- Live probe: Pydantic 2.13.5 `EmailStr` normalisation, `SecretStr` masking, `extra="forbid"`
- This repository, read in full for this phase: `access.py`, `actor.py`, `dependencies.py`, `main.py`,
  `errors/{handlers,mapping,problem}.py`, `ports/*.py`, `domain/{entities,exceptions,validation}`,
  `infrastructure/db/{models,mappers,constraints,unit_of_work,repositories/users}.py`, `config/settings.py`,
  `migrations/versions/0001_baseline.py`, `docker/entrypoint.sh`, `docker-compose.yml`, `.github/workflows/ci.yml`,
  `pytest.ini`, `.flake8`, `.importlinter`, `pyproject.toml`, `.env.example`,
  `tests/{conftest,integration/conftest,integration/api/test_statements,architecture/test_routers_raise_no_http_exception,unit/presentation/test_actor,unit/application/fakes,unit/test_settings}.py`
- `slopcheck install PyJWT pwdlib python-multipart email-validator` — 4 scanned, 4 OK
- Live PostgreSQL probe — 18.4 reachable at `localhost:5432/taskmanager_test`; Docker 29.2.0 daemon up

### Secondary (MEDIUM-HIGH — official documentation, cross-checked against the installed code)
- https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt (via Context7) — the canonical PyJWT + pwdlib pattern,
  the `DUMMY_HASH` timing-equalisation technique, `verify(plain_password, hashed_password)` argument order
- https://fastapi.tiangolo.com/reference/security (via Context7) — `OAuth2PasswordBearer` and
  `OAuth2PasswordRequestForm` signatures, `auto_error` semantics
- https://www.rfc-editor.org/rfc/rfc8725.html §2.1 — quoted in PyJWT's own docstring: never derive `algorithms`
  from the token
- RFC 7518 §3.2 — the HMAC key-length rule PyJWT's warning cites verbatim
- RFC 9110 §15.5.2 — 401 MUST carry a challenge (already implemented in `handlers.py`)
- RFC 9457 — the problem+json shape (already implemented in `problem.py`)

### Tertiary (LOW — training knowledge, flagged in the Assumptions Log)
- Swagger UI's relative-`tokenUrl` resolution (A1)
- Current OWASP Argon2id parameter guidance (A3)

## Metadata

**Confidence breakdown:**
- Standard stack: **HIGH** — nothing new is added; every library was imported and exercised at its pinned version
- Library behaviour (PyJWT, pwdlib, FastAPI security, logging, Pydantic): **HIGH** — every claim is the output of a
  script run in this session, not a recollection
- Architecture / the 404-403 split: **HIGH** for the constraints (read from the code and the gates), **MEDIUM-HIGH**
  for the specific `owned_task` shape, which is a recommendation the planner may refine
- Pitfalls: **HIGH** — each one was reproduced
- The permission matrix: **HIGH** for rows derived from D-01..D-08 and existing code; the three open routes
  (rows 1–3) are a reading of the phase boundary rather than a stated decision
- Open questions 1 and 3: **deliberately unresolved** — they need a user decision, not more research

**Research date:** 2026-09-19
**Valid until:** 2026-10-19 (30 days — every version is exact-pinned, so drift can only arrive with a deliberate
bump; the findings are properties of these exact versions)
