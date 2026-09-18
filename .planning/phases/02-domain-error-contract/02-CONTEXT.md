# Phase 2: Domain & Error Contract - Context

**Gathered:** 2026-09-18
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers the framework-free core every later layer is written against:

- `domain/`: `TaskList`, `Task`, `User` entities and `TaskStatus` / `TaskPriority` enums as
  stdlib dataclasses/Enums, carrying their own invariants and the task state machine.
- `domain/`: a closed `DomainError` hierarchy (validation, business rule, invalid status
  transition, not found, conflict, authentication, authorization) with a stable `code` and
  structured details — no HTTP anywhere in it.
- `application/`: the eight ports as `typing.Protocol` with no implementation —
  `TaskRepository`, `TaskListRepository`, `UserRepository`, `UnitOfWork`, `PasswordHasher`,
  `TokenService`, `EmailNotifier`, `Clock` — plus the fixed, documented use-case shape and the
  base command/result DTO conventions.
- `presentation/`: the single exception-handling point that turns any `DomainError`, any
  request-validation error and any unexpected error into one RFC 9457
  `application/problem+json` shape, registered by `create_app()` and proven by tests against a
  test-only probe router.

Not in this phase: real routers or endpoints (`/health` and compose land in Phase 3, CRUD in
Phase 4), database models, migrations, repository implementations, JWT/auth adapters, the
email adapter. Ports are declared here; adapters arrive in Phases 3–5.

</domain>

<decisions>
## Implementation Decisions

### Task state machine
- **D-01:** Allowed transitions (owned by the `Task` entity, in the domain layer):
  `pending → in_progress | completed`; `in_progress → pending | completed`;
  `completed → in_progress` (reopen). `completed → pending` is forbidden and raises
  `InvalidStatusTransitionError` (maps to 409) carrying `from` and `to` in its details.
  Rationale to document: work resumes before it is un-started, so reopening lands in
  `in_progress`.
- **D-02:** A same-state request (`X → X`) is an idempotent no-op: the entity does not change,
  no timestamp moves, the endpoint (Phase 4) answers 200 with the unchanged task. It is not a
  409.
- **D-03:** Entering `completed` sets `completed_at = now`; leaving `completed` clears it back
  to `None`. This is the observable side effect domain tests assert on.
- **D-04:** Business validations (TASK-08: blank title, over-length fields, `due_date` in the
  past at creation; LIST rules) live in the entities — `__post_init__` and mutating methods
  such as `rename` / `reschedule` — and raise `DomainError` subclasses (`ValidationError`,
  `BusinessRuleViolationError`). Pydantic at the HTTP boundary validates shape and types only;
  a limit is never duplicated in two layers.

### problem+json shape
- **D-05:** `type` is a stable URN per error code: `urn:taskmanager:problem:{code}` (e.g.
  `urn:taskmanager:problem:invalid_status_transition`). No fictional HTTPS domain, no
  `about:blank`. `code` is also carried as an RFC 9457 extension member so clients can switch
  on it without parsing the URN.
- **D-06:** Body members, always in this order and always present: `type`, `title`, `status`,
  `detail`, `instance` (the request path), `code`. Optional extension `errors` carries
  structured details (`from`/`to` for transitions, `field` for validation).
- **D-07:** FastAPI/Pydantic request-validation failures (`RequestValidationError`) are
  translated — not passed through — into `code: validation_error`, status 422, and an `errors`
  list of `{field, message, type}` where `field` is the dotted location (`body.title`,
  `query.status`). Pydantic's `loc` tuples, `ctx` and `input` echo are never exposed.
- **D-08:** Unexpected exceptions produce `code: internal_error`, status 500, a fixed `detail`
  ("An unexpected error occurred") and nothing else — no traceback, no exception message, in
  every environment including `development` and `test`. The full traceback is logged
  server-side. One shape everywhere, one test.
- **D-09:** Starlette `HTTPException` (unknown route 404, method 405, and later the auth
  dependency's 401) is also translated into the same shape, so no response from the app is
  ever a bare `{"detail": ...}`.
- **D-10:** The handler is proven before any real router exists through a probe router
  (`/_probe/...`) that tests include on top of `create_app()`; it raises each error family on
  demand (`DomainError` subclasses, a validation failure, a raw `Exception`,
  `HTTPException`). The production app never registers it. A test also asserts the
  load-bearing framework behaviour that a handler registered on `DomainError` catches every
  subclass (Starlette walks the MRO).

### Identity and time in the domain
- **D-11:** Entity ids are UUIDs generated in the application layer (`uuid4()`) before
  persistence; the database stores them as primary keys and never generates ids. Entities are
  complete from construction and domain tests need no database. Non-enumerable ids reinforce
  ADR-008.
- **D-12:** `uuid4()` is called directly in the use case. There is no `IdGenerator` port; the
  roadmap's eight ports are the full set.
- **D-13:** Current time enters the domain only through the `Clock` port: the use case calls
  `clock.now()` and passes `now` as an explicit argument to entity methods
  (`task.change_status(new_status, now=now)`, `Task.create(..., now=now)`). The domain never
  calls `datetime.now()`; the domain never imports or depends on the `Clock` protocol itself.
- **D-14:** Every temporal value — `created_at`, `updated_at`, `completed_at`, `due_date` — is a
  timezone-aware `datetime` in UTC. A naive `datetime` reaching the domain is a
  `ValidationError` (`DomainError` subclass). Phase 3 maps these to `timestamptz`.

### Use case and DTO shape
- **D-15:** One class per use case, single-purpose (ARC-04). Dependencies arrive through
  `__init__`; the only public method is `async def execute(self, command: XCommand) ->
  XResult`. No `__call__`, no service-per-aggregate classes.
- **D-16:** Commands and results are `@dataclass(frozen=True, slots=True)`. The application
  layer stays free of Pydantic (allowed by ADR-004, not required); shape validation happened
  once at the HTTP boundary and is not repeated.
- **D-17:** Repositories reach the use case only through the `UnitOfWork` port, which is an
  async context manager exposing `tasks`, `task_lists` and `users` bound to one transaction,
  plus `commit()` / `rollback()`. Non-transactional ports (`Clock`, `PasswordHasher`,
  `TokenService`, `EmailNotifier`) are injected as separate constructor arguments.
- **D-18:** Every command carries `actor_id: UUID` — the authenticated caller, filled by
  presentation from the JWT (Phase 5). The use case, not the router, decides visibility
  (404) versus permission (403) per ADR-008. Phase 2 fixes the convention in the base DTO
  documentation; Phase 4 is the first consumer.
- **D-19:** All ports are `async` (`async def get(...) -> Task | None`), matching the async
  SQLAlchemy decision (ADR-006). `Clock.now()` may be sync — it does no I/O.

### Claude's Discretion
- Exact module layout inside `domain/` and `application/` (one module per entity vs
  `entities.py`; `ports/` package vs single module) — follow
  `.planning/research/ARCHITECTURE.md` "Recommended Project Structure" unless a concrete
  reason to deviate appears, and record the deviation.
- Exact `DomainError` class names and the `code` strings, provided the seven families in the
  domain boundary above exist and the `{class: status}` table lives in `presentation`.
- Whether Phase 2 ships one small, real use case as the documented reference shape (it must
  have a test if it lives under `src/`, because coverage is measured over `taskmanager`), or
  documents the shape with a typed skeleton plus a docstring/ADR. Either way the shape must be
  written down where Phase 4 will find it.
- How the probe router is packaged (a `tests/` fixture module vs a `presentation` helper that
  is only imported by tests) — but it must not be reachable in the production app.
- Structural conformance tests for the Protocols (e.g. an in-memory fake asserted against the
  Protocol under mypy) are welcome and count toward "ports exist with no implementation" as
  long as the fakes live under `tests/`.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project
- `.planning/PROJECT.md` — scope, constraints, key decisions
- `.planning/REQUIREMENTS.md` — ARC-02, ARC-04, ARC-06, ARC-07 (this phase); TASK-05,
  TASK-08, LIST-06, AUTH-06, ASGN-02 (rules the domain must be shaped to support)
- `.planning/ROADMAP.md` §"Phase 2" — goal and the four success criteria

### Decisions already locked (do not reopen)
- `DECISION_LOG.md` — ADR-004 (dataclass domain, Pydantic at boundaries), ADR-005 (RFC 9457
  from one handler, no `HTTPException` outside presentation), ADR-006 (async SQLAlchemy —
  why ports are async), ADR-008 (404 invisible / 403 visible-but-forbidden), ADR-009
  (completion % over the whole list — shapes `TaskRepository.completion_stats`)
- `CLAUDE.md` §"Project Rules" — layer rules, error-handling rule, quality-gate rule
- `.importlinter` — the contracts the new packages must keep green (`pydantic` forbidden in
  `domain`, allowed in `application`; `fastapi`/`starlette`/`sqlalchemy` forbidden in both)

### Research
- `.planning/research/ARCHITECTURE.md` §"Pattern 1" (entities), §"Pattern 2" (ports),
  §"Pattern 3" (use case + DTOs), §"Pattern 4" (Unit of Work), §"Pattern 6" (exception
  hierarchy and handler, including the MRO note) — the reference implementation sketches;
  the decisions above override its `type` URL scheme and its Pydantic-DTO leaning
- `.planning/research/FEATURES.md` §5 "Status / Priority Enums and Transition Rules" — the
  transition matrix adopted in D-01..D-03; §"Anti-features" — why `status` is not writable
  via PATCH and why there are exactly three statuses
- `.planning/research/PITFALLS.md` — Phase-2-relevant traps (Pydantic `ValidationError`
  leaking from the domain, handler registration order)
- `.planning/phases/01-foundation-quality-gates/01-CONTEXT.md` — D-09 coverage rule
  (anything under `src/` needs tests), D-10 import-linter contracts

### Standards
- RFC 9457 "Problem Details for HTTP APIs" (obsoletes RFC 7807) — members `type`, `title`,
  `status`, `detail`, `instance`; extension members; guidance on multiple errors

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/taskmanager/main.py::create_app(settings=None)` — the composition root; the exception
  handlers are registered here. It must stay importable with no environment variables set.
- `src/taskmanager/infrastructure/config/settings.py` — `Settings` with `environment`; D-08
  deliberately does not branch on it.
- `tests/unit/test_app_factory.py` — existing pattern for building the app in tests
  (`monkeypatch` env + `create_app()`); the probe-router fixture extends this.
- `tests/architecture/test_layer_boundaries.py` — runs the import-linter contracts inside
  pytest; adding `domain`/`application` modules is automatically covered.

### Established Patterns
- Coverage source is `taskmanager` with no `omit` (18 statements today at 100%). Every new
  module under `src/` needs real tests; the 75% gate is the floor, not the target.
- `filterwarnings = error` in `pytest.ini` — deprecation warnings from new code fail the suite.
- mypy strict with the pydantic plugin over `src` and `tests`; `Protocol` classes and frozen
  dataclasses must type-check without `type: ignore`.
- Every commit runs twelve pre-commit hooks; CI repeats the gates on Python 3.13.

### Integration Points
- `create_app()` gains `register_exception_handlers(app)` (three handlers: `DomainError`,
  `RequestValidationError`, `StarletteHTTPException`, plus the catch-all `Exception`).
- `domain/` and `application/` packages exist but are empty; `presentation/` gains its first
  module (`errors/`).
- Phase 3 implements `UnitOfWork` and the repositories against the Protocols declared here;
  Phase 4 builds routers that call `use_case.execute(command)` and rely on the handler.

</code_context>

<specifics>
## Specific Ideas

- The error contract must be demonstrably in place before the first real route — the roadmap
  success criterion 4 says "before any real router exists"; the probe-router tests are the
  proof.
- The state-machine tests should read as a specification: one test per allowed transition, one
  per forbidden transition, one for the same-state no-op, one for `completed_at` set and one
  for clear.
- `DomainError` details are structured (`dict`), not formatted into the message, so the
  handler can emit them as the `errors` extension without parsing strings.

</specifics>

<deferred>
## Deferred Ideas

- Multi-value status filters (`?status=a&status=b`) — Phase 4, from FEATURES.md; not a domain
  concern.
- Extra task statuses (`cancelled`, `archived`, `blocked`) — explicitly out of scope; list as
  documented future work in Phase 7.
- A targeted import-linter `forbidden` contract for `HTTPException` outside `presentation` —
  Phase 4, once the presentation modules exist (ADR-005 consequence).

</deferred>

---

*Phase: 02-domain-error-contract*
*Context gathered: 2026-09-18*
