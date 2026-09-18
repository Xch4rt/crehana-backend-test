# Phase 2: Domain & Error Contract - Research

**Researched:** 2026-09-17
**Domain:** Framework-free Python domain modelling + RFC 9457 error contract in FastAPI 0.141 / Starlette 1.6
**Confidence:** HIGH

> **Method note.** Almost every claim below was produced by *running code against this
> repository's own pinned toolchain* (`.venv`: fastapi 0.141.1, starlette 1.6.0, pydantic 2.13.5,
> httpx 0.28.1, mypy 2.3.1, pytest 9.1.1, pytest-asyncio 1.4.0, flake8 7.3.0 +
> flake8-bugbear 26.9.9, import-linter 2.15, grimp), using this repo's real `.flake8`,
> `pyproject.toml` and `pytest.ini`. Those are tagged `[VERIFIED: executed]`. Nothing important
> here rests on training memory.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Task state machine**
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

**problem+json shape**
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

**Identity and time in the domain**
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

**Use case and DTO shape**
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

### Deferred Ideas (OUT OF SCOPE)
- Multi-value status filters (`?status=a&status=b`) — Phase 4, from FEATURES.md; not a domain
  concern.
- Extra task statuses (`cancelled`, `archived`, `blocked`) — explicitly out of scope; list as
  documented future work in Phase 7.
- A targeted import-linter `forbidden` contract for `HTTPException` outside `presentation` —
  Phase 4, once the presentation modules exist (ADR-005 consequence).
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| **ARC-02** | Domain entities and value objects are stdlib dataclasses/Enums; the domain package imports no third-party library | §Architecture Patterns 1–2 (entity/enum shapes verified under mypy strict + flake8); §Pattern 8 (the grimp/AST stdlib-only test that *actually* proves the claim — see Conflict C-01: the existing `forbidden` contract cannot prove it alone) |
| **ARC-04** | Every use case is a single-purpose class in `application/` depending only on `typing.Protocol` ports (repositories, UnitOfWork, PasswordHasher, TokenService, EmailNotifier, Clock) | §Pattern 3 (all eight Protocols verified mypy-strict-clean, incl. `UnitOfWork` as async CM with `Self`); §Pattern 4 (use-case shape); §Pattern 5 (F841-free conformance idiom); §Pitfall 3 (Protocol + black + E301) |
| **ARC-06** | A `DomainError` hierarchy (not found, conflict, business-rule violation, authentication, authorization) carries a stable `code` and details; no `HTTPException` outside `presentation` | §Pattern 6 (the one exception base shape that is simultaneously B042-clean, mypy-strict-clean and pickle/copy-safe — three obvious alternatives all fail); §Pitfall 1 (B042); §Pitfall 2 (`str(exc)` trap) |
| **ARC-07** | One exception-handling point maps `DomainError`, request-validation errors and unexpected errors to RFC 9457 `application/problem+json` responses with a single shape | §Pattern 7 (four handlers, all verified end-to-end returning problem+json); §Pitfall 4 (`ServerErrorMiddleware` re-raise / `raise_app_exceptions`); §Pitfall 5 (mypy rejects the natural handler signature); §Pitfall 6 (`WWW-Authenticate` header loss) |
</phase_requirements>

---

## Summary

This phase is **declarative code with three sharp edges**, not an integration problem. There are
no new dependencies, no network, no database — everything needed is already installed and pinned
from Phase 1. The intellectual work is (a) getting the `DomainError` base class into the one
shape that passes all three of this repo's gates simultaneously, (b) registering the four
exception handlers in a way that mypy strict accepts, and (c) proving the handlers work before
any router exists.

Each of those three has a *non-obvious* failure mode that the project's own research sketches
(`.planning/research/ARCHITECTURE.md` Pattern 6) would walk straight into:

1. **`flake8-bugbear` B042 rejects `DomainError.__init__(self, message, **details)`** — the exact
   signature in ARCHITECTURE.md Pattern 6. It also rejects keyword-only parameters in *any*
   exception `__init__`. Only one shape survives, and it has a side effect (`str(exc)` stops
   equalling the message) that must be neutralised with an explicit `__str__`.
2. **mypy strict rejects `app.add_exception_handler(DomainError, handler)` when `handler` is
   annotated `(Request, DomainError) -> JSONResponse`** — the natural annotation. Starlette's
   `ExceptionHandler` type is invariant in the exception parameter. Handlers must be annotated
   `exc: Exception` and narrow with `assert isinstance(...)`. (The `@app.exception_handler`
   *decorator* form escapes this, but this project has no module-level `app`, so the imperative
   form is mandatory.)
3. **Starlette's `ServerErrorMiddleware` always re-raises after invoking a handler registered for
   bare `Exception`.** With `httpx.ASGITransport` at its default `raise_app_exceptions=True`, the
   500 test never sees a response — it sees the `RuntimeError`. The 500 test (and *only* the 500
   test) needs `ASGITransport(app=app, raise_app_exceptions=False)`.

Separately, there is a **gap between what the roadmap claims and what import-linter can prove**
(Conflict C-01): a `forbidden` contract can only prove that *enumerated* modules are absent.
`forbidden_modules = *` was tried and forbids `dataclasses`, `datetime` and `enum` too. A
generic "domain imports nothing but stdlib" proof needs one extra ~15-line test built on
`sys.stdlib_module_names` — verified working, catching a planted `import pydantic` while
accepting `dataclasses`/`datetime`/`enum`/`typing`/`uuid`.

**Primary recommendation:** Build bottom-up in four waves — enums + `DomainError` hierarchy →
entities + state machine → ports + DTOs + one reference use case → the four handlers proven by a
probe router — and lift every code shape verbatim from §Code Examples, which are the exact
strings that were observed passing `black --check`, `flake8`, `mypy --strict` and `pytest` in
this repo's venv.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Task state machine (`D-01`–`D-03`) | Domain (`taskmanager.domain`) | — | Invariant of the `Task` aggregate. Lives on the entity so it holds regardless of which adapter drives it. |
| Business validation (blank title, length, past due date) | Domain (entity `__post_init__` / mutators) | — | D-04: one place per limit. Pydantic at the boundary checks *shape*, not *policy*. |
| Error taxonomy + stable `code` + structured `details` | Domain (`domain/exceptions.py`) | — | ARC-06. Zero HTTP knowledge; the domain must be usable by a CLI or worker. |
| `code`/class → HTTP status mapping | Presentation (`presentation/api/errors/mapping.py`) | — | The only tier that knows HTTP exists. CONTEXT explicitly places the `{class: status}` table here. |
| problem+json body construction | Presentation (`presentation/api/errors/problem.py`) | — | RFC 9457 is a wire concern. |
| Exception handler registration | Presentation (`register_exception_handlers`) called from `main.py` | Main (`taskmanager.main`) | `main.create_app()` is the composition root (existing Phase 1 code); the handlers themselves are presentation. |
| Port declarations (8 Protocols) | Application (`application/ports/`) | — | ARCHITECTURE.md §Structure Rationale: "domain imports nothing" is easier to state, enforce and defend than "domain may declare interfaces it doesn't use". Keeps the `layers` contract perfectly linear. |
| Use-case orchestration + transaction boundary | Application (`application/use_cases/`) | — | ARC-04 / ARC-08. Reaches persistence only through the `UnitOfWork` port (D-17). |
| Id generation (`uuid4()`) | Application (inside the use case) | — | D-11/D-12. No ninth port. |
| Current time | Application (`Clock` port, injected) → passed *into* domain as an argument | Domain (receives `now`, never fetches it) | D-13. The domain never imports the `Clock` Protocol — that would be an upward import. |
| Probe router (test-only) | Tests (`tests/…/probe.py`) | — | D-10. Must be unreachable from `create_app()`. |

---

## Standard Stack

### Core — no new dependencies

Phase 2 adds **zero** packages. Everything is already pinned in `requirements.txt` /
`requirements-dev.txt` from Phase 1 and installed in `.venv`.

| Module | Source | Purpose in this phase | Why |
|--------|--------|----------------------|-----|
| `dataclasses` | stdlib | Entities (`slots=True`), DTOs (`frozen=True, slots=True`) | ADR-004 / ARC-02: domain is stdlib-only. |
| `enum.StrEnum` | stdlib (3.11+) | `TaskStatus`, `TaskPriority` | `json.dumps({"s": TaskStatus.PENDING})` → `{"s": "pending"}` with no encoder; `f"{status}"` → `pending`. `[VERIFIED: executed]` |
| `typing.Protocol` / `Self` | stdlib | The eight ports | ARC-04. Structural typing; adapters never import the port. |
| `types.TracebackType` | stdlib | `UnitOfWork.__aexit__` signature | Required for a mypy-strict-clean async context manager Protocol. |
| `uuid.UUID` / `uuid4` | stdlib | Entity ids | D-11/D-12. |
| `datetime` (`UTC`) | stdlib | Aware UTC timestamps | D-14. `datetime.UTC` exists since 3.11 — never `utcnow()` (deprecated 3.12, and `filterwarnings = error` makes it a test failure). |
| `fastapi` 0.141.1 | pinned | `FastAPI.add_exception_handler`, `RequestValidationError`, `JSONResponse` | Already in `main.py`. |
| `starlette` 1.6.0 | transitive, pinned via fastapi | `HTTPException` (register on **Starlette's**, not FastAPI's) | Verified: `fastapi.HTTPException` *is* a subclass of `starlette.exceptions.HTTPException`, so registering on the Starlette class catches both plus Starlette-internal 404/405. `[VERIFIED: executed]` |
| `httpx` 0.28.1 + `ASGITransport` | pinned dev | Probe-router tests | `AsyncClient(app=app)` was removed in httpx 0.28. |
| `pytest-asyncio` 1.4.0, `asyncio_mode = auto` | pinned dev, already configured | async tests + async fixtures with **no** markers and **no** `@pytest_asyncio.fixture` | Verified: a plain `@pytest.fixture` on an `async def` generator works in auto mode. `[VERIFIED: executed]` |
| `grimp` (≥3.17) | **transitive** via import-linter 2.15 | The stdlib-only domain proof (§Pattern 8, Option A) | See Pitfall 8 for the "transitive dependency" caveat and the zero-dependency `ast` alternative. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `enum.StrEnum` | `class TaskStatus(str, Enum)` (the form in `FEATURES.md` §5) | Both serialize to `"pending"` in `json.dumps`. But `f"{TaskStatus.PENDING}"` yields `"TaskStatus.PENDING"` with `(str, Enum)` on 3.11+ and `"pending"` with `StrEnum` — the classic source of a wrong log line or a wrong SQL literal. **Use `StrEnum`.** Requires 3.11+; project is 3.13. |
| Class→status table with MRO walk | `code`→status dict | Class+MRO matches what Starlette itself does and makes a new leaf subclass inherit its parent's status for free. `code`→status needs every new code registered or it silently 500s. **Use class+MRO.** |
| `for … : return / return default` MRO walk | `next((…), default)` generator form | Measured: the `for` loop leaves the trailing `return` as an uncoverable statement **and** a partial branch (89% on the module). The `next(...)` form is 100% coverable. Project rule forbids reaching the gate via `# pragma: no cover`. **Use `next(...)`.** `[VERIFIED: executed]` |
| `assert isinstance(exc, X)` in handlers | `if not isinstance(exc, X): raise exc` | The `if` form adds a branch no test can cover (partial branch, hurts `branch = true` coverage). Measured: `assert` produces **zero** partial branches — coverage.py does not treat `assert` as a branch. No `-O` / `PYTHONOPTIMIZE` anywhere in the Dockerfile or CI, so asserts are never stripped. **Use `assert`.** `[VERIFIED: executed]` |
| `typing.cast(X, exc)` in handlers | — | mypy-clean but silently wrong at runtime if a handler is ever mis-registered. `assert` fails loudly. Prefer `assert`. |
| `@runtime_checkable` on ports | plain `Protocol` | Verified: `isinstance()` works for data protocols but `issubclass()` raises `TypeError: Protocols with non-method members don't support issubclass(). Non-method members: 'tasks'` — exactly the `UnitOfWork` case. Runtime checks are structurally shallow anyway (presence, not signature). **Do not use `runtime_checkable`**; use the mypy-checked conformance assignment (§Pattern 5). `[VERIFIED: executed]` |
| Frozen dataclass entities | `slots=True` mutable entities | D-01/D-03 require mutating methods (`change_status` sets `status`, `updated_at`, `completed_at`). Frozen would force `object.__setattr__` or `replace()` everywhere. **Entities: `@dataclass(slots=True)`. Commands/results: `@dataclass(frozen=True, slots=True)`** per D-16. |

**Installation:** none. `make install` from Phase 1 already covers this phase.

---

## Package Legitimacy Audit

**Not applicable — this phase installs no external packages.** Every module used is either the
Python standard library or a package already pinned, installed and in use from Phase 1
(`requirements.txt` / `requirements-dev.txt`, unchanged by this phase).

The one package *newly imported* by source added in this phase is **`grimp`** (if
§Pattern 8 Option A is chosen), which is already installed as a required transitive dependency of
`import-linter==2.15` (`import-linter` requires `grimp>=3.17`). It is not added to any
requirements file. See Pitfall 8 for why that is a real (if small) risk and what the
zero-dependency alternative is.

| Package | Registry | Status | Disposition |
|---------|----------|--------|-------------|
| *(none added)* | — | — | — |
| `grimp` | PyPI | Already installed, transitive of `import-linter==2.15` | Optional — used only if §Pattern 8 Option A is chosen; see Pitfall 8 |

---

## Project Constraints (from CLAUDE.md)

These are `CLAUDE.md` §"Project Rules" directives that constrain this phase. Each is enforced by
a gate that fails a build.

| # | Directive | Consequence for Phase 2 |
|---|-----------|------------------------|
| PC-1 | Import direction `main > presentation > infrastructure > application > domain`; imports only ever point downward | The `Clock` Protocol lives in `application`, so **the domain must never import it** (D-13 says the same). `presentation/api/errors/mapping.py` importing `taskmanager.domain.exceptions` is downward and legal. |
| PC-2 | `taskmanager.domain` imports **no third-party library at all** — stdlib only, not even Pydantic | ARC-02. See Conflict C-01 on what actually proves this. |
| PC-3 | `taskmanager.application` imports no web framework and no ORM. Pydantic **is** allowed there | D-16 chooses not to use it. The `.importlinter` contract stays permissive (see Conflict C-02). |
| PC-4 | `fastapi.HTTPException` may **never** be raised outside `presentation` | The probe router lives under `tests/`, so raising `StarletteHTTPException` there is fine. No `src/taskmanager/{domain,application}` module may import fastapi. |
| PC-5 | Business failures raise a `DomainError` subclass, translated **once**, at a single exception-handling point, into RFC 9457 `application/problem+json`. No handler builds an error body by hand | One `_problem(...)` builder used by all four handlers. |
| PC-6 | `make lint`, `make typecheck`, `make arch`, `make test` all green before any commit | Every code shape in §Code Examples was verified against all four. |
| PC-7 | Coverage gated at 75% over `src/taskmanager`; **never** reached with `# pragma: no cover` or a coverage `omit` entry. "If the number is short, write the test." | Drives three concrete shape choices: the `next(...)` status mapper, the `assert` narrowing, and a mandatory pickle round-trip test for `DomainError.__reduce__` (see §Validation Architecture). |
| PC-8 | A new gate must be added in **both** `.pre-commit-config.yaml` **and** `.github/workflows/ci.yml` — neither derives from the other | Phase 2 adds **no new gate**: the new stdlib-only test runs inside `pytest`, which both files already invoke. No config change needed — but do not let a plan "helpfully" add a hook to only one file. |
| PC-9 | Everything in English; no Claude/AI co-author or attribution trailer in commits | Applies to code, comments, docstrings, commit messages and `.planning/` artifacts. |

---

## Conflicts with CONTEXT.md / upstream artifacts

> Flagged rather than silently resolved, per the research brief.

### C-01 — ROADMAP success criterion 1 overstates what import-linter can prove · **HIGH confidence, action required**

Roadmap SC-1 says: *"the import-linter contract proves the `domain` package imports no
third-party library."*

**It cannot, as written.** `.importlinter`'s `domain-framework-free` contract is a `forbidden`
contract with an enumerated `forbidden_modules` list (`fastapi`, `starlette`, `sqlalchemy`,
`alembic`, `pydantic`, `pydantic_settings`, `jwt`, `pwdlib`, `httpx`). It proves those nine are
absent. It says nothing about the tenth.

I tried the wildcard escape hatch — `forbidden_modules = *`, which import-linter 2.15 does
support — against a planted test package. Result `[VERIFIED: executed]`:

```
tm.domain is not allowed to import dataclasses:   tm.domain.entities.task -> dataclasses (l.1)
tm.domain is not allowed to import datetime:      tm.domain.entities.task -> datetime (l.2)
tm.domain is not allowed to import enum:          tm.domain.entities.task -> enum (l.3)
tm.domain is not allowed to import pydantic:      tm.domain.bad -> pydantic (l.1)
```

The grimp graph built with `include_external_packages = True` contains stdlib modules as
first-class nodes (verified against this very repo: the graph is
`['fastapi', 'functools', 'pydantic', 'pydantic_settings', 'taskmanager', …]` — note
`functools`). There is no contract type that means "everything except the standard library".

**Resolution:** keep the existing enumerated contract (it gives readable, targeted failures) and
add **one** test in `tests/architecture/` that closes the gap generically. Both implementations
are verified working in §Pattern 8. This is a plan task, not an optional nicety — SC-1 is not
satisfiable without it.

### C-02 — ARC-05 and ADR-004 say "Pydantic types application DTOs"; D-16 says frozen dataclasses · **HIGH confidence, needs a documentation task**

| Source | Says |
|--------|------|
| `REQUIREMENTS.md` **ARC-05** (Phase 4) | "Pydantic v2 models type every boundary: HTTP request/response schemas, **application command/result DTOs**, settings" |
| `DECISION_LOG.md` **ADR-004** (Decision) | "Pydantic lives in `presentation` schemas, **`application` DTOs** and `infrastructure.config.settings`" |
| `.importlinter` comment | "The application layer … may use pydantic (**DTOs are pydantic models**)" |
| `ROADMAP.md` Phase 4 SC-5 | "Pydantic v2 models type every boundary crossed in this slice (HTTP request/response schemas **and application command/result DTOs**)" |
| **CONTEXT.md D-16** (newest, authoritative) | Commands and results are `@dataclass(frozen=True, slots=True)`; "the application layer stays free of Pydantic" |

**D-16 wins** (CONTEXT is authoritative and is the most recent user decision), but three
artifacts now assert the opposite and one of them is a *requirement* whose Phase 4 acceptance
criterion becomes unsatisfiable as literally worded.

**Recommended plan tasks:**
1. Add a new ADR to `DECISION_LOG.md` (it is append-only — do not edit ADR-004) recording:
   "application command/result DTOs are frozen dataclasses, refining ADR-004", with D-16's
   rationale (shape validation happened once at the HTTP boundary; the application layer gains
   nothing from re-validating).
2. Amend **ARC-05**'s wording in `REQUIREMENTS.md` to "HTTP request/response schemas and
   settings" and amend ROADMAP Phase 4 SC-5 to match, or Phase 4 verification will fail against
   its own text.
3. Fix the stale `.importlinter` comment ("DTOs are pydantic models") — a comment that
   contradicts the code is exactly the "AI-code tell" PITFALLS §18 warns about.

**Do not** add `pydantic` to the `application-framework-free` contract's `forbidden_modules`.
CONTEXT lists the current contract shape under "Decisions already locked (do not reopen)", and
Phase 4/5 may still legitimately want a Pydantic DTO. Enforcing D-16 mechanically is out of
scope for this phase.

### C-03 — ARCHITECTURE.md Pattern 6's `DomainError` sketch fails `make lint` · **HIGH confidence**

`.planning/research/ARCHITECTURE.md` Pattern 6 shows
`def __init__(self, message: str, **details: Any)`. Running this repo's real `.flake8` over it:

```
B042 Exception class with `__init__` should pass all args to `super().__init__()` to work in
     edge cases of `pickle` and `copy.copy()`. It should also not take any kwargs.
```

CONTEXT's canonical-refs section points downstream agents at Pattern 6 as "the reference
implementation sketch". It is not usable as-is. §Pattern 6 below supplies the corrected shape.
CONTEXT already establishes the precedent that its decisions override Pattern 6 details (it does
so for the `type` URL scheme and the Pydantic-DTO leaning); this is one more.

### C-04 — `TaskRepository.completion_stats` needs a value object CONTEXT's domain boundary does not list · **MEDIUM confidence, scope note**

CONTEXT §Phase Boundary lists the domain deliverables as `TaskList`, `Task`, `User`,
`TaskStatus`, `TaskPriority` and the `DomainError` hierarchy. But CONTEXT §Canonical References
also names **ADR-009** as "shapes `TaskRepository.completion_stats`", and ARCHITECTURE.md
Pattern 2's `TaskRepository` Protocol has
`async def completion_stats(self, task_list_id: UUID) -> CompletionStats: ...`.

A Protocol cannot reference a return type that does not exist. Either:
- **(recommended)** add `domain/value_objects/completion.py` with a tiny
  `@dataclass(frozen=True, slots=True) CompletionStats(total: int, completed: int)` exposing a
  `percentage` property (empty list → `0.0` per FEATURES.md §6) — ~10 statements, trivially
  unit-testable, and it pre-places ADR-009's semantics where Phase 3's SQL aggregate will land;
- or drop `completion_stats` from the Phase 2 port and let Phase 3/4 add it — but then ARC-04's
  "the ports exist" is partially deferred and Phase 4 edits the port file.

Recommend the first. Flagging because it is an addition to CONTEXT's literal deliverable list.

---

## Architecture Patterns

### System Architecture Diagram

Error-propagation flow — the thing this phase actually builds. Trace an invalid status change
from HTTP in to problem+json out:

```
                          ┌──────────────────────────────────────────────┐
  HTTP request  ─────────▶│ ServerErrorMiddleware                        │
                          │  handler = handle_unexpected_error           │  ◀── registered for
                          │  (ALWAYS re-raises after responding)         │      Exception / 500
                          └───────────────────┬──────────────────────────┘
                                              ▼
                          ┌──────────────────────────────────────────────┐
                          │ ExceptionMiddleware                          │
                          │  handlers = { DomainError,                   │
                          │               RequestValidationError,        │
                          │               StarletteHTTPException }       │
                          │  lookup = walk type(exc).__mro__             │
                          └───────────────────┬──────────────────────────┘
                                              ▼
                          ┌──────────────────────────────────────────────┐
                          │ Router                                       │
                          │  · unknown path  ──▶ StarletteHTTPException 404
                          │  · wrong verb    ──▶ StarletteHTTPException 405 (+ Allow)
                          └───────────────────┬──────────────────────────┘
                                              ▼
                          ┌──────────────────────────────────────────────┐
                          │ Route handler (Phase 4) / probe route (tests)│
                          │  · body/query parse fails ──▶ RequestValidationError
                          └───────────────────┬──────────────────────────┘
                                              ▼  command DTO (frozen dataclass, actor_id)
                          ┌──────────────────────────────────────────────┐
                          │ APPLICATION  UseCase.execute(command)        │
                          │  async with uow:   load ▸ authorize ▸ …      │
                          │   ├─ missing      ──▶ NotFoundError          │
                          │   ├─ not permitted──▶ AuthorizationError     │
                          │   └─ now = clock.now()                       │
                          └───────────────────┬──────────────────────────┘
                                              ▼  entity method + explicit `now`
                          ┌──────────────────────────────────────────────┐
                          │ DOMAIN  task.change_status(new, now=now)     │
                          │   X → X          ──▶ no-op, return (D-02)    │
                          │   forbidden move ──▶ InvalidStatusTransitionError
                          │   enter completed──▶ completed_at = now      │
                          │   leave completed──▶ completed_at = None     │
                          └───────────────────┬──────────────────────────┘
                                              │ raises  (unwinds back up)
                                              ▼
   ┌───────────────────────────────────────────────────────────────────────────────┐
   │ PRESENTATION — the single translation point                                   │
   │                                                                               │
   │   mapping.status_for(exc)   walk __mro__ against {class: status}              │
   │   problem._problem(...)     build the six ordered members + optional errors   │
   │                                                                               │
   │        ▼                                                                      │
   │   JSONResponse(body, status_code=…, media_type="application/problem+json")    │
   └───────────────────────────────────────────────────────────────────────────────┘
                                              ▼
                       {"type":"urn:taskmanager:problem:invalid_status_transition",
                        "title":…, "status":409, "detail":…, "instance":"/…",
                        "code":"invalid_status_transition",
                        "errors":{"from":"completed","to":"pending"}}
```

Two load-bearing framework facts, both verified in this repo's `.venv`:

- **`ExceptionMiddleware` resolves handlers by `for cls in type(exc).__mro__`** — verified by
  reading `starlette/_exception_handler.py::_lookup_exception_handler` in the installed
  starlette 1.6.0, and by an end-to-end test where a handler registered on `DomainError` caught
  a grandchild `InvalidStatusTransitionError`. This is what makes "one handler" sufficient
  (D-10 requires a test asserting it).
- **A handler registered for `Exception` (or `500`) is *removed* from `ExceptionMiddleware` and
  installed on `ServerErrorMiddleware` instead** — verified by reading
  `starlette/applications.py::build_middleware_stack`:
  `if key in (500, Exception): error_handler = value`. `ServerErrorMiddleware` sends the
  response and then unconditionally `raise exc`. See Pitfall 4.

### Recommended Project Structure

Follows `.planning/research/ARCHITECTURE.md` §"Recommended Project Structure" (per CONTEXT's
discretion instruction). Only Phase-2 files shown; `(new)` marks what this phase creates.

```
src/taskmanager/
├── main.py                              # existing — gains register_exception_handlers(app)
├── domain/                              # stdlib only
│   ├── exceptions.py            (new)   # the closed DomainError hierarchy
│   ├── value_objects/           (new)
│   │   ├── task_status.py       (new)   # TaskStatus + ALLOWED_TRANSITIONS
│   │   ├── task_priority.py     (new)   # TaskPriority
│   │   └── completion.py        (new)   # CompletionStats  — see Conflict C-04
│   └── entities/                (new)
│       ├── task.py              (new)   # Task + the state machine (D-01..D-04)
│       ├── task_list.py         (new)   # TaskList
│       └── user.py              (new)   # User
├── application/                         # domain only (D-16: no pydantic either)
│   ├── ports/                   (new)
│   │   ├── repositories.py      (new)   # TaskRepository, TaskListRepository, UserRepository
│   │   ├── unit_of_work.py      (new)   # UnitOfWork  (async context manager)
│   │   ├── security.py          (new)   # PasswordHasher, TokenService
│   │   ├── notifications.py     (new)   # EmailNotifier
│   │   └── clock.py             (new)   # Clock
│   ├── dto/                     (new)
│   │   ├── commands.py          (new)   # actor_id convention + ChangeTaskStatusCommand
│   │   └── results.py           (new)   # TaskResult
│   └── use_cases/               (new)
│       └── tasks/
│           └── change_task_status.py (new)   # THE reference use case (see below)
└── presentation/
    └── api/                     (new)
        └── errors/              (new)
            ├── problem.py       (new)   # PROBLEM_JSON + _problem() builder
            ├── mapping.py       (new)   # {DomainError subclass: HTTP status} + status_for()
            └── handlers.py      (new)   # 4 handlers + register_exception_handlers()

tests/
├── conftest.py                  (new)   # app / client / tolerant_client fixtures
├── probe.py                     (new)   # the test-only probe router  (D-10)
├── unit/
│   ├── domain/                  (new)   # test_task_status.py, test_task.py,
│   │                                    # test_task_list.py, test_user.py, test_exceptions.py
│   └── application/             (new)   # fakes.py + test_change_task_status.py
├── api/                         (new)
│   └── test_error_contract.py   (new)   # the probe-router contract tests
└── architecture/
    ├── test_layer_boundaries.py         # existing — update EXPECTED_CONTRACT_NAMES if changed
    └── test_domain_is_stdlib_only.py (new)   # closes Conflict C-01
```

**Recommended reference use case:** ship **one real use case** (`ChangeTaskStatus`) rather than a
skeleton. CONTEXT leaves this to discretion; a real one is better because (a) Phase 4 copies a
file that is known to compile and pass mypy strict, not a docstring; (b) it exercises the
`UnitOfWork` async-context-manager Protocol, the `Clock` port and the `actor_id`/404-vs-403
convention (D-18) in a way a skeleton cannot; (c) it costs ~20 statements and is 100% coverable
with in-memory fakes. `ChangeTaskStatus` specifically, because it is the one use case that
touches the state machine, the `Clock`, and both `NotFoundError` and `AuthorizationError` —
maximum convention coverage per line.

### Pattern 1: Enums as `StrEnum` + a transition table beside them

**What:** `TaskStatus` / `TaskPriority` as `enum.StrEnum`, plus a module-level
`ALLOWED_TRANSITIONS: Final[Mapping[TaskStatus, frozenset[TaskStatus]]]` in the same module.
**When:** always in this project.
**Why not `class TaskStatus(str, Enum)`** (the `FEATURES.md` §5 form): see §Alternatives.

Transition table, from D-01 — note it differs from ARCHITECTURE.md's, which still had
`CANCELLED`:

```python
ALLOWED_TRANSITIONS: Final[Mapping[TaskStatus, frozenset[TaskStatus]]] = {
    TaskStatus.PENDING:     frozenset({TaskStatus.IN_PROGRESS, TaskStatus.COMPLETED}),
    TaskStatus.IN_PROGRESS: frozenset({TaskStatus.PENDING, TaskStatus.COMPLETED}),
    TaskStatus.COMPLETED:   frozenset({TaskStatus.IN_PROGRESS}),
}
```

The only forbidden move is `completed → pending`. Keep the map exhaustive over all three
statuses so a future status addition fails loudly at the `ALLOWED_TRANSITIONS[self.status]`
lookup rather than silently permitting everything.

### Pattern 2: Entities as `@dataclass(slots=True)` with invariants in `__post_init__`

**What:** mutable dataclasses with `slots=True`, invariants in `__post_init__`, state changes
via named methods that take `now` as a keyword argument.
**Why `slots=True`:** verified — it removes `__dict__`, so `task.statsu = X` raises
`AttributeError: 'Task' object has no attribute 'statsu' and no __dict__ for setting new
attributes` instead of silently creating a typo'd attribute. Free correctness. It type-checks
clean under mypy 2.3 strict. `[VERIFIED: executed]`
**Why not `frozen=True`:** D-01/D-03 need in-place mutation (`status`, `updated_at`,
`completed_at`). Frozen would force `object.__setattr__` in every mutator.

**Mutable defaults:** `tags: list[str] = []` in a dataclass is not a lint finding — it is a
`ValueError: mutable default <class 'list'> for field tags is not allowed: use default_factory`
raised at **class-creation time**, i.e. at import. flake8-bugbear's B006 targets *function*
defaults and does not fire here. So this cannot ship undetected; the guard is Python itself.
`[VERIFIED: executed]`

**Timezone rule (D-14):** the canonical aware check is
`dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None`. Comparing naive and aware datetimes
raises `TypeError: can't compare offset-naive and offset-aware datetimes` — verified — which is
exactly the failure PITFALLS §15 says surfaces "in a due-date validation, at the worst moment".
D-14 makes a naive datetime a `ValidationError`; recommend additionally **normalising** aware
non-UTC input with `value.astimezone(UTC)` in `__post_init__` so `completed_at` comparisons and
Phase 3's `timestamptz` round-trip are unambiguous. Note `datetime.now().astimezone()` produces
an aware non-UTC datetime, so "aware" alone does not imply "UTC". `[VERIFIED: executed]`

### Pattern 3: The eight ports as `typing.Protocol`

All eight verified mypy-strict-clean, including `UnitOfWork` as an async context manager
returning `Self`, and a fake satisfying it. See §Code Examples.

| Port | Module | Shape |
|------|--------|-------|
| `TaskRepository` | `ports/repositories.py` | `async` get / add / update / delete / list_for_task_list / completion_stats |
| `TaskListRepository` | `ports/repositories.py` | `async` get / add / update / delete / list_for_owner / exists_with_name |
| `UserRepository` | `ports/repositories.py` | `async` get / get_by_email / add / list_all |
| `UnitOfWork` | `ports/unit_of_work.py` | attributes `tasks` / `task_lists` / `users`; `__aenter__`→`Self`, `__aexit__`, `commit`, `rollback` |
| `PasswordHasher` | `ports/security.py` | `async hash(password) -> str`, `async verify(password, hashed) -> bool` |
| `TokenService` | `ports/security.py` | `issue_access_token(subject) -> str`, `decode(token) -> UUID` |
| `EmailNotifier` | `ports/notifications.py` | `async send_task_assigned(...) -> None` |
| `Clock` | `ports/clock.py` | `def now(self) -> datetime: ...` — **sync** (D-19: it does no I/O) |

**`Clock`: Protocol, not a callable.** D-13 fixes the call site as `clock.now()`, which settles
it. Beyond that, a Protocol with a named method reads better at the injection site
(`ChangeTaskStatus(uow, clock)` vs `ChangeTaskStatus(uow, now_fn)`) and leaves room for a
`FrozenClock` test double with extra affordances.

**Do not use `@runtime_checkable`.** See §Alternatives — `issubclass()` raises `TypeError` on
`UnitOfWork` because it has non-method members.

### Pattern 4: One class per use case, `async def execute(command) -> Result`

Shape fixed by D-15/D-17/D-18. The canonical body, which every Phase 4/5 use case repeats:

```
load ▸ authorize ▸ invoke domain ▸ persist ▸ commit ▸ map to result
```

Dependencies: the `UnitOfWork` first, then non-transactional ports (`Clock`, `PasswordHasher`,
`TokenService`, `EmailNotifier`) as separate constructor arguments (D-17). Every command carries
`actor_id: UUID` (D-18); the **use case** decides 404-vs-403 (ADR-008), never the router.

See §Code Examples for the full verified implementation.

### Pattern 5: Protocol conformance assertions that survive flake8

The idiom in ARCHITECTURE.md Pattern 2 —

```python
def test_adapter_satisfies_port() -> None:
    _: type[TaskRepository] = SqlAlchemyTaskRepository
```

— fails this repo's flake8: `F841 local variable '_repo' is assigned to but never used`.
`[VERIFIED: executed]`

**Two forms that pass flake8 *and* mypy strict** `[VERIFIED: executed]`:

```python
# tests/unit/application/fakes.py — module level (F841 is function-scope only)
_task_repository_conformance: type[TaskRepository] = FakeTaskRepository
_unit_of_work_conformance: type[UnitOfWork] = FakeUnitOfWork
```

```python
# or, as a test with a real runtime assertion (better: it also shows up as a named test)
def test_fake_satisfies_task_repository_port() -> None:
    repo: TaskRepository = FakeTaskRepository()
    assert repo is not None
```

Prefer the second inside `tests/unit/`, because it appears in the pytest output by name — which
is what makes ARC-04 *demonstrable* to an evaluator rather than merely true.

### Pattern 6: The `DomainError` base — the one shape that passes every gate

This is the highest-value finding in this research. Four candidate shapes were run against this
repo's `.flake8`, mypy strict, and a pickle/copy round trip `[VERIFIED: executed]`:

| Shape | B042 | pickle / copy | Verdict |
|-------|------|---------------|---------|
| `__init__(self, message, **details)` — **the ARCHITECTURE.md sketch** | ✗ **fails** | ok (by luck) | blocks `make lint` |
| `__init__(self, message, details=None)` + `super().__init__(message)` | ✗ **fails** | ok | blocks `make lint` |
| `__init__(self, message, *, field=None)` — keyword-only | ✗ **fails** | ok | B042 rejects *any* kwargs |
| `__init__(self, message, details=None)` + `super().__init__(message, details)` | ✓ passes | ✓ | **but** `str(exc)` becomes `"('msg', {...})"` |
| Leaf subclass `__init__(self, current, requested)` forwarding derived values | ✓ passes | ✗ **breaks** | B042's heuristic misses it; see below |

B042's message: *"Exception class with `__init__` should pass all args to `super().__init__()` to
work in edge cases of `pickle` and `copy.copy()`. It should also not take any kwargs."*

**The subtle one.** A leaf subclass such as

```python
class InvalidStatusTransitionError(BusinessRuleViolationError):
    def __init__(self, current: TaskStatus, requested: TaskStatus) -> None:
        super().__init__(f"…", {"from": current.value, "to": requested.value})
```

passes B042 but **genuinely breaks pickle and `copy.copy`**: `Exception.__reduce__` returns
`(cls, self.args)`, and `self.args` is `(message, details)` from the base, so rebuilding calls
`InvalidStatusTransitionError("A task cannot move…", {...})` against a two-`TaskStatus`
signature. Observed:

```
AttributeError: 'str' object has no attribute 'value'
```

B042's heuristic is checking the wrong thing and gives a false pass. This matters because the
ergonomic API we want *is* `raise InvalidStatusTransitionError(current, requested)`.

**Resolution — one `__reduce__` on the base fixes every subclass, forever.** Verified
flake8-clean, mypy-strict-clean, and round-tripping through `pickle`, `copy.copy` and
`copy.deepcopy`. See §Code Examples for the full module. The `__str__` override is not cosmetic:
without it `str(exc)` is `"('A task cannot move…', {'from': …})"`, which would leak the details
dict into any log line or `detail` field built from `str(exc)`.

**Recommended hierarchy** (CONTEXT leaves names and codes to discretion; the seven families from
CONTEXT §Phase Boundary are all present):

```
DomainError                          code                         → HTTP (presentation)
├── ValidationError                  validation_error                 422
├── BusinessRuleViolationError       business_rule_violation          422
│   └── InvalidStatusTransitionError invalid_status_transition        409   (D-01)
├── NotFoundError                    not_found                        404
│   ├── TaskNotFoundError            task_not_found                   404
│   ├── TaskListNotFoundError        task_list_not_found              404
│   └── UserNotFoundError            user_not_found                   404
├── ConflictError                    conflict                         409
│   ├── DuplicateTaskListNameError   duplicate_task_list_name         409   (LIST-06)
│   └── EmailAlreadyRegisteredError  email_already_registered         409   (AUTH-01)
├── AuthenticationError              authentication_failed            401   (AUTH-03)
└── AuthorizationError               authorization_failed             403   (AUTH-06, ADR-008)
```

`code` and `title` are `ClassVar[str]` — required under mypy strict, or they become instance
fields and every subclass override is a type error.

**Closedness:** "closed hierarchy" is a design claim, not an enforced one. If a plan wants it
enforced, the cheap version is a test that asserts the set of `DomainError.__subclasses__()`
(recursively) equals a literal expected set — it doubles as living documentation of the taxonomy
and fails loudly when someone adds an unmapped error. Recommended; ~10 statements.

### Pattern 7: Four handlers, one body builder, registered from `create_app()`

```python
def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, handle_domain_error)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, handle_http_exception)
    app.add_exception_handler(Exception, handle_unexpected_error)
```

Verified end-to-end (5 assertions, all passing) that this yields
`content-type: application/problem+json` for: a nested `DomainError` subclass (409), an unknown
route (404), a wrong verb (405, with the `Allow` header preserved), a `StarletteHTTPException`
(401, with `WWW-Authenticate: Bearer` preserved), a body-validation failure (422) and a raw
`RuntimeError` (500, leaking nothing). `[VERIFIED: executed]`

Points that are easy to get wrong:

- **Register on `starlette.exceptions.HTTPException`, not `fastapi.HTTPException`.** Verified:
  `issubclass(fastapi.HTTPException, starlette.exceptions.HTTPException) is True`, so the
  Starlette registration catches both via the MRO walk **plus** Starlette-internal 404/405 that
  never pass through FastAPI's class. FastAPI's own docs say the same.
  `[CITED: fastapi.tiangolo.com/tutorial/handling-errors]`
- **Registering these four replaces FastAPI's defaults.** A fresh `FastAPI()` ships
  `{HTTPException: http_exception_handler, RequestValidationError:
  request_validation_exception_handler, WebSocketRequestValidationError: …}`. Ours override the
  first two by dict key. The websocket one stays — irrelevant here (no websockets).
  `[VERIFIED: executed]`
- **`ResponseValidationError` is *not* a `RequestValidationError`.** Both subclass
  `fastapi.exceptions.ValidationException`; neither is a parent of the other. A response-model
  mismatch (a Phase 4 risk) therefore falls through to the catch-all `Exception` handler and
  becomes a 500 `internal_error`. That is the correct outcome — a response-model mismatch is a
  server bug, not a client error — but it should be a conscious choice, and worth one sentence
  in the DECISION_LOG entry. `[VERIFIED: executed]`
- **`media_type="application/problem+json"`** on `JSONResponse` produces exactly that
  content-type with no `; charset=utf-8` suffix. `[VERIFIED: executed]`
- **Member order (D-06)** is preserved because Python dicts are insertion-ordered and
  `json.dumps` follows insertion order. Build the dict literally in the D-06 order and append
  `errors` last.

### Pattern 8: Proving "domain imports nothing but stdlib" (closes Conflict C-01)

Both options verified against a planted package containing a legitimate domain module
(`dataclasses`, `datetime`, `enum`, `uuid`, intra-package import) and one violating module
(`import pydantic`). Both reported exactly `[('…domain.bad', 'pydantic')]`. `[VERIFIED: executed]`

**Option A — grimp (reuses the resolver import-linter already uses):**

```python
import sys
import grimp

def test_domain_imports_only_stdlib() -> None:
    graph = grimp.build_graph("taskmanager", include_external_packages=True)
    violations = [
        (module, imported)
        for module in graph.modules
        if module == "taskmanager.domain" or module.startswith("taskmanager.domain.")
        for imported in graph.find_modules_directly_imported_by(module)
        if not imported.startswith("taskmanager.domain")
        and imported.split(".")[0] not in sys.stdlib_module_names
    ]
    assert violations == []
```

Pros: real import resolution, handles `from x import y` correctly, no parsing. Cons: `grimp` is
a *transitive* dependency (see Pitfall 8).

**Option B — `ast` + `sys.stdlib_module_names` (zero new imports beyond stdlib):**

Walks `src/taskmanager/domain/**/*.py`, `ast.parse`s each, collects `ast.Import` /
`ast.ImportFrom` root names (skipping `node.level > 0` relative imports), and asserts each root
is in `sys.stdlib_module_names` or is `taskmanager`. This is exactly what PITFALLS §Pitfall 9
prescribes ("Using `ast` (not string grep) makes the test honest and non-trivial"), and it
depends on nothing. ~15 statements.

**Recommendation: Option B.** It satisfies PITFALLS §9 literally, adds no dependency exposure,
and is more readable to an evaluator who has 90 seconds. Option A is a fine alternative if the
plan prefers not to hand-roll import parsing — say which and why in the DECISION_LOG.

Either way, **also add a red/green observation** the way Phase 1 did for import-linter and
coverage (`evidence/import-linter-red-green.txt`): plant `import pydantic` in a domain module,
capture the test failing, remove it, capture it passing. PITFALLS §"Looks Done But Isn't" lists
exactly this ("verify by temporarily adding it") and Phase 1 set the precedent.

### Anti-Patterns to Avoid

- **`# noqa: B042` on `DomainError`.** It is the path of least resistance and it discards a real
  pickle/copy bug. Use the `__reduce__` shape.
- **Handler annotated `exc: DomainError`.** mypy strict rejects it (Pitfall 5). Do not reach for
  `# type: ignore[arg-type]` — the `exc: Exception` + `assert isinstance` form is clean.
- **`@app.exception_handler(...)` decorator.** It type-checks (the decorator is
  `Callable[[DecoratedCallable], DecoratedCallable]`, i.e. unconstrained) but requires a
  module-level `app`, which Phase 1's ADR and `main.py` docstring explicitly forbid. Verified
  that the decorator form passes mypy strict — do not let that tempt a plan into a module-level
  app. `[VERIFIED: executed]`
- **`raise_app_exceptions=False` on the shared client fixture.** It would swallow real bugs in
  every other test in the suite. Confine it to a second, clearly-named fixture used by the 500
  test only (Pitfall 4).
- **`str(exc)` as the problem `detail`.** Use `exc.message` (Pitfall 2).
- **Branching on `settings.environment` in the 500 handler.** D-08 forbids it explicitly: one
  shape everywhere, one test. This also keeps `presentation` from importing `infrastructure`
  for no reason.
- **`datetime.utcnow()` anywhere.** Deprecated since 3.12 and `filterwarnings = error` turns the
  `DeprecationWarning` into a test failure. Use `datetime.now(UTC)` in the `SystemClock` adapter
  (Phase 3) — the domain never calls either.
- **A `TaskService` with several methods.** D-15 and ARC-04 both forbid it.
- **Putting the `Clock` Protocol in `domain/`.** It is an application port; the domain receives
  `now` as an argument (D-13). A `domain → application` import is an upward import and fails the
  `layers` contract.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Dispatching an exception to its handler | A `try/except` chain in a middleware, or `isinstance` ladders | `app.add_exception_handler(DomainError, …)` + Starlette's MRO walk | Verified: Starlette already walks `type(exc).__mro__`. One registration covers the whole hierarchy. Re-implementing it is the exact thing D-10 asks you to *test*, not to write. |
| Catching unhandled exceptions for a 500 | A bare `except Exception` in every route, or a custom middleware | `app.add_exception_handler(Exception, …)` → `ServerErrorMiddleware` | It is already the outermost middleware and is guaranteed to see everything. A custom middleware placed inside it would miss exceptions raised by other middleware. |
| Enum values that serialize to strings | `TaskStatus.PENDING.value` at every call site, or a custom JSON encoder | `enum.StrEnum` | Verified: `json.dumps` and f-strings both produce `"pending"` with no help. |
| Distinguishing stdlib from third-party | A hard-coded list of stdlib module names | `sys.stdlib_module_names` (3.10+) | 297 names, maintained by CPython, correct for the running interpreter. `[VERIFIED: executed]` |
| Making a dataclass reject unknown attributes | `__setattr__` overrides or `__slots__` written by hand | `@dataclass(slots=True)` | Generates `__slots__` correctly including inheritance, and mypy understands it. |
| Async test/fixture plumbing | A hand-rolled `event_loop` fixture, `asyncio.run` in tests | `pytest-asyncio` `asyncio_mode = auto` (already configured) | Verified: `async def` tests and plain `@pytest.fixture` async generators both work with zero markers. PITFALLS §4 documents the `event_loop`-override trap. |
| ASGI test transport | `TestClient` threads, manual ASGI scope dicts | `httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test")` | Current FastAPI async-testing docs; `AsyncClient(app=…)` was removed in httpx 0.28. |
| Exception pickling/copying | Per-subclass `__reduce__` | One `__reduce__` + `_restore` helper on `DomainError` | ~8 statements, covers every present and future subclass. |

**Key insight:** in this phase almost every "hand-rolled" temptation is re-implementing something
Starlette or the stdlib already does — and the project's value proposition is *knowing* that the
framework does it (and proving it with a test), not writing it again.

---

## Common Pitfalls

### Pitfall 1: `flake8-bugbear` B042 blocks the obvious `DomainError.__init__` · **verified**

**What goes wrong:** `make lint` fails on `def __init__(self, message: str, **details: Any)` —
the shape in the project's own ARCHITECTURE.md Pattern 6.
**Why:** B042 requires all `__init__` parameters to be forwarded to `super().__init__()` and
forbids `**kwargs` **and keyword-only parameters** in exception constructors, because
`Exception.__reduce__` rebuilds via `cls(*self.args)`.
**How to avoid:** `def __init__(self, message: str, details: dict[str, Any] | None = None) ->
None:` with `super().__init__(message, details)`. Leaf subclasses may take domain-specific
*positional-or-keyword* parameters (B042 does not fire) — but see Pitfall 2.
**Warning signs:** `B042` in `flake8 src tests` output; a plan that reaches for `# noqa: B042`.

### Pitfall 2: The B042-clean base breaks `str(exc)`; the B042-clean *subclass* breaks pickle · **verified**

**What goes wrong:** two separate things, both silent.
1. `super().__init__(message, details)` makes `self.args == (message, details)`, so
   `str(exc)` is `"('Task not found', {'task_id': 'abc'})"`. Any `detail=str(exc)` leaks the
   details dict into the wire body and any log line reads badly.
2. A leaf subclass with its own signature (`__init__(self, current, requested)`) passes B042 but
   fails `pickle.loads(pickle.dumps(exc))` and `copy.copy(exc)` with
   `AttributeError: 'str' object has no attribute 'value'`, because the rebuild calls the leaf
   signature with the base's `args`.
**How to avoid:** define `__str__` returning `self.message`, and define `__reduce__` **once** on
`DomainError` delegating to a module-level `_restore(cls, message, details)` that uses
`cls.__new__(cls)` and never touches a subclass `__init__`. Full verified code in §Code Examples.
**Warning signs:** a problem `detail` containing a `{`; any test that `copy`s or `pickle`s a
domain error failing mysteriously.

### Pitfall 3: `black` formats Protocol stubs into a shape that trips `pycodestyle` E301 · **verified**

**What goes wrong:** `make lint` fails with `E301 expected 1 blank line, found 0` on a Protocol —
after `black` has just formatted it. The classic formatter-vs-linter war PITFALLS §16 warns
about, in a spot the Phase 1 `.flake8` tuning does not cover.
**Why:** pycodestyle 2.14 tolerates *consecutive single-line* stub defs
(`async def get(...) -> Task | None: ...`) but **not** a def that follows another def with no
blank line when the signature wraps across multiple lines. `UnitOfWork.__aexit__` is exactly
that: its signature is 105 characters, so black wraps it. black then leaves no blank line before
it, and E301 fires.
**How to avoid:** **in any Protocol where at least one signature wraps to multiple lines,
separate every method with one blank line.** Verified black-stable (black preserves those blank
lines across repeated runs) and flake8-clean. Protocols whose methods are all one-liners
(`TaskRepository`, `Clock`) need no blank lines and black will keep them packed.
**Warning signs:** `E301` at the line of a multi-line `async def …(…) -> None: ...`; a pre-commit
run that keeps modifying the same file.

### Pitfall 4: the 500 test never sees a response — `ServerErrorMiddleware` always re-raises · **verified**

**What goes wrong:** the test for D-08 fails with `RuntimeError: kaboom` instead of asserting a
500 problem+json body.
**Why:** verified in `starlette/middleware/errors.py` — after invoking the installed 500 handler
and sending its response, `ServerErrorMiddleware` executes `raise exc`, with the comment *"We
always continue to raise the exception. This allows servers to log the error, or allows test
clients to optionally raise the error within the test case."* `httpx.ASGITransport` defaults to
`raise_app_exceptions=True` and therefore propagates it.
**How to avoid:** a **second, separately named** fixture used by the unexpected-error test only:

```python
@pytest.fixture
async def tolerant_client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """Only for the unexpected-error case: ServerErrorMiddleware re-raises by design."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
```

Never apply it to the shared `client` fixture — it would mask genuine 500s in every other test.
(The `TestClient` equivalent is `raise_server_exceptions=False`; this project uses
`httpx.AsyncClient`, so `raise_app_exceptions` is the knob.)
**Warning signs:** the 500 test raising the probe's own exception; or, worse, a green suite where
a route silently 500s because someone made the shared fixture tolerant.

### Pitfall 5: mypy strict rejects the natural exception-handler signature · **verified**

**What goes wrong:** `make typecheck` fails with

```
error: Argument 2 to "add_exception_handler" of "Starlette" has incompatible type
"Callable[[Request[State], DomainError], Coroutine[Any, Any, JSONResponse]]";
expected "Callable[[Request[State], Exception], Response | Awaitable[Response]] | …"  [arg-type]
```

**Why:** `starlette.types.HTTPExceptionHandler` is
`Callable[[Request, Exception], Response | Awaitable[Response]]`. Callable parameters are
contravariant, so a handler that only accepts `DomainError` is not a valid
`Callable[..., Exception, ...]`. This is *correct* variance, not a Starlette bug.
**How to avoid:** annotate every handler `exc: Exception` and narrow on the first line with
`assert isinstance(exc, DomainError)`. Verified: all four handlers in that form pass
`mypy --strict --warn-unreachable` with the pydantic plugin, plus `black --check` and `flake8`.
**Warning signs:** `[arg-type]` on `add_exception_handler`; a plan proposing
`# type: ignore[arg-type]` or a module-level `app` so the decorator form can be used.

### Pitfall 6: translating `HTTPException` silently drops its headers · **verified**

**What goes wrong:** `WWW-Authenticate: Bearer` disappears from 401 responses (AUTH-03, Phase 5)
and `Allow: GET` disappears from 405 responses, because the handler builds a fresh
`JSONResponse` and never looks at `exc.headers`.
**Why:** Starlette's *default* HTTPException handler copies `exc.headers`; a custom one that
replaces it must do the same.
**How to avoid:** in `handle_http_exception`, after building the response,
`for key, value in (exc.headers or {}).items(): response.headers[key] = value`. Verified: with
this line, `response.headers["www-authenticate"] == "Bearer"` and the 405's `Allow: GET` both
survive; without it, both are gone.
**Warning signs:** a 401 with no `WWW-Authenticate`; Swagger's "Authorize" behaving oddly in
Phase 5. Write the assertion **now**, in Phase 2, against the probe router — it is a five-line
test that prevents a Phase 5 debugging session.

### Pitfall 7: the MRO status-mapper leaves an uncoverable line · **verified**

**What goes wrong:** the module sits at 89% with `Missing: 26` and one partial branch, and
someone reaches for `# pragma: no cover` — which CLAUDE.md §Quality gates forbids outright.
**Why:** the `for klass in type(exc).__mro__: … / return DEFAULT` shape has a trailing `return`
that is unreachable once `DomainError` itself is in the table (every `DomainError` subclass's MRO
contains it), plus a loop-exit branch that never happens.
**How to avoid:** use the `next((…generator…), default)` form — measured at 100% with the same
three tests. See §Code Examples.
**Warning signs:** `--cov-report=term-missing` pointing at a `return` statement; any `pragma`
appearing in a diff.

### Pitfall 8: `grimp` is a transitive dependency, not a declared one · **MEDIUM confidence**

**What goes wrong:** `tests/architecture/test_domain_is_stdlib_only.py` does `import grimp`, but
`requirements-dev.txt` never names it — it explicitly says *"coverage and grimp are intentionally
absent: they arrive transitively via pytest-cov and import-linter respectively."* A future
import-linter bump that vendors or renames grimp breaks a test with a confusing
`ModuleNotFoundError`.
**How to avoid:** prefer §Pattern 8 Option B (`ast` + `sys.stdlib_module_names`, zero imports
beyond stdlib). If Option A is chosen anyway, add `grimp==<pinned>` to `requirements-dev.txt`
with a comment explaining why the Phase 1 rule is being carved out — and note that this changes
the Docker layer and CI cache key shape, which `requirements.txt`'s own header says was
deliberately frozen.
**Warning signs:** a plan that imports `grimp` without touching `requirements-dev.txt`.

### Pitfall 9: `DomainError.__reduce__` / `_restore` / `__str__` are dead weight for coverage · **verified**

**What goes wrong:** `domain/exceptions.py` measured at 77% (missing the `_restore` body,
`__reduce__` and `__str__`) because no test ever pickles or stringifies an error, and the phase
adds enough declarative code that nobody notices until the 75% gate bites later.
**How to avoid:** one test, three assertions:

```python
def test_domain_error_survives_pickle_and_copy() -> None:
    error = InvalidStatusTransitionError(TaskStatus.COMPLETED, TaskStatus.PENDING)
    assert str(error) == error.message
    assert pickle.loads(pickle.dumps(error)).details == error.details
    assert copy.copy(error).details == error.details
```

It brings the module to 100% and documents *why* `__reduce__` exists — which is the more valuable
half. **Warning signs:** `exceptions.py` below 100% in `term-missing`.

### Pitfall 10: `include_in_schema` and the probe router leaking into the deliverable · **LOW confidence, MEDIUM impact**

**What goes wrong:** `/_probe/...` shows up in `/openapi.json`, or worse, is reachable in the
running container — directly contradicting D-10 ("the production app never registers it").
**How to avoid:** define the probe router in `tests/probe.py` (not under `src/`), include it only
inside the `app` fixture, and add an explicit assertion that the *production* app does not carry
it:

```python
def test_production_app_has_no_probe_routes() -> None:
    app = create_app(Settings(_env_file=None))
    assert not any(getattr(route, "path", "").startswith("/_probe") for route in app.routes)
```

Keeping it under `tests/` also keeps it out of coverage and out of import-linter's graph
(`root_package = taskmanager`), so it cannot accidentally break a layer contract.
**Warning signs:** a `probe.py` under `src/taskmanager/`; `/_probe` in the committed
`openapi.json` if one is ever snapshotted.

---

## Code Examples

> Every block below was written to a file, formatted with this repo's `black`/`isort`, and run
> through this repo's `flake8`, `mypy --strict --warn-unreachable` (with the pydantic plugin) and
> `pytest`. All green. `[VERIFIED: executed]`

### `domain/exceptions.py` — the base + two representative subclasses

```python
"""The closed domain-error hierarchy. Nothing here knows that HTTP exists.

`__reduce__` is not ceremony. `Exception.__reduce__` rebuilds an instance by calling
`cls(*self.args)`, so a subclass with its own signature -- `InvalidStatusTransitionError(
current, requested)` -- would be rebuilt with the *base* arguments and raise
`AttributeError` during `pickle.loads` or `copy.copy`. Delegating to `_restore` rebuilds
every subclass without ever calling a subclass `__init__`.
"""

from typing import Any, ClassVar


def _restore(
    cls: type["DomainError"], message: str, details: dict[str, Any]
) -> "DomainError":
    """Rebuild a DomainError without calling a subclass-specific ``__init__``."""
    error = cls.__new__(cls)
    Exception.__init__(error, message, details)
    error.message = message
    error.details = details
    return error


class DomainError(Exception):
    """Base of the closed domain-error hierarchy.

    `super().__init__(message, details)` forwards *every* parameter, which is what
    flake8-bugbear's B042 requires; the consequence is that `self.args` is a 2-tuple and
    the inherited `__str__` would render it, hence the explicit `__str__` below.
    """

    code: ClassVar[str] = "domain_error"
    title: ClassVar[str] = "Domain error"

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, details)
        self.message = message
        self.details: dict[str, Any] = details if details is not None else {}

    def __reduce__(self) -> tuple[Any, ...]:
        return (_restore, (type(self), self.message, self.details))

    def __str__(self) -> str:
        return self.message


class BusinessRuleViolationError(DomainError):
    code: ClassVar[str] = "business_rule_violation"
    title: ClassVar[str] = "Business rule violated"


class InvalidStatusTransitionError(BusinessRuleViolationError):
    code: ClassVar[str] = "invalid_status_transition"
    title: ClassVar[str] = "Invalid status transition"

    def __init__(self, current: TaskStatus, requested: TaskStatus) -> None:
        super().__init__(
            f"A task cannot move from {current.value} to {requested.value}.",
            {"from": current.value, "to": requested.value},
        )
```

Observed round trip:

```
str(e)      : A task cannot move from completed to pending.
details     : {'from': 'completed', 'to': 'pending'}
code/title  : invalid_status_transition / Invalid status transition
pickle ok   : InvalidStatusTransitionError …
copy ok / deepcopy ok
isinstance(e, DomainError) -> True     # what makes one handler enough
```

### `presentation/api/errors/mapping.py` — MRO walk, 100% coverable

```python
from http import HTTPStatus
from typing import Final

from taskmanager.domain.exceptions import (
    AuthenticationError,
    AuthorizationError,
    BusinessRuleViolationError,
    ConflictError,
    DomainError,
    InvalidStatusTransitionError,
    NotFoundError,
    ValidationError,
)

# The ONLY place in the codebase that maps a business failure to an HTTP status.
STATUS_BY_EXCEPTION: Final[dict[type[DomainError], int]] = {
    DomainError: HTTPStatus.INTERNAL_SERVER_ERROR,
    ValidationError: HTTPStatus.UNPROCESSABLE_CONTENT,
    BusinessRuleViolationError: HTTPStatus.UNPROCESSABLE_CONTENT,
    InvalidStatusTransitionError: HTTPStatus.CONFLICT,
    NotFoundError: HTTPStatus.NOT_FOUND,
    ConflictError: HTTPStatus.CONFLICT,
    AuthenticationError: HTTPStatus.UNAUTHORIZED,
    AuthorizationError: HTTPStatus.FORBIDDEN,
}


def status_for(exc: DomainError) -> int:
    """Resolve the HTTP status by walking the MRO, exactly as Starlette resolves handlers.

    The generator form is deliberate: the equivalent `for`/`return` loop leaves a trailing
    `return` that no test can reach (every DomainError subclass's MRO contains DomainError,
    which is mapped), costing one uncovered statement and one partial branch.
    """
    return next(
        (
            STATUS_BY_EXCEPTION[klass]
            for klass in type(exc).__mro__
            if klass in STATUS_BY_EXCEPTION
        ),
        HTTPStatus.INTERNAL_SERVER_ERROR,
    )
```

> Note `HTTPStatus.UNPROCESSABLE_CONTENT` — `UNPROCESSABLE_ENTITY` is the older alias for 422.
> Confirm the spelling available on 3.13 when writing the code; a plain `422` int literal is also
> fine and avoids the question entirely.

### `presentation/api/errors/problem.py` + `handlers.py` — the four handlers

```python
from typing import Any, Final

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from taskmanager.domain.exceptions import DomainError
from taskmanager.presentation.api.errors.mapping import status_for

PROBLEM_JSON: Final[str] = "application/problem+json"


def problem(
    *,
    code: str,
    title: str,
    status: int,
    detail: str,
    instance: str,
    errors: Any = None,
) -> JSONResponse:
    """Build the one RFC 9457 body shape. Members in D-06 order; `errors` last."""
    body: dict[str, Any] = {
        "type": f"urn:taskmanager:problem:{code}",
        "title": title,
        "status": status,
        "detail": detail,
        "instance": instance,
        "code": code,
    }
    if errors:
        body["errors"] = errors
    return JSONResponse(body, status_code=status, media_type=PROBLEM_JSON)


# `exc: Exception`, not `exc: DomainError`: starlette's ExceptionHandler type is
# Callable[[Request, Exception], ...] and callable parameters are contravariant, so the
# narrower annotation is rejected by mypy strict. `assert` narrows without adding an
# uncoverable branch (coverage.py does not treat `assert` as a branch).
async def handle_domain_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, DomainError)
    return problem(
        code=exc.code,
        title=exc.title,
        status=status_for(exc),
        detail=exc.message,
        instance=request.url.path,
        errors=exc.details or None,
    )


async def handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    return problem(
        code="validation_error",
        title="Request validation failed",
        status=422,
        detail="The request payload failed validation.",
        instance=request.url.path,
        errors=[
            {
                "field": ".".join(str(part) for part in error["loc"]),
                "message": error["msg"],
                "type": error["type"],
            }
            for error in exc.errors()
        ],
    )


async def handle_http_exception(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    response = problem(
        code="http_error",
        title="HTTP error",
        status=exc.status_code,
        detail=str(exc.detail),
        instance=request.url.path,
    )
    # Starlette's own handler forwards these; a replacement must too, or 401 loses
    # WWW-Authenticate and 405 loses Allow.
    for key, value in (exc.headers or {}).items():
        response.headers[key] = value
    return response


async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    # D-08: identical in every environment. No traceback, no str(exc), no branch on
    # settings.environment. The traceback is logged server-side instead.
    return problem(
        code="internal_error",
        title="Internal server error",
        status=500,
        detail="An unexpected error occurred",
        instance=request.url.path,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """The single exception-handling point (ARC-07). Called by create_app()."""
    app.add_exception_handler(DomainError, handle_domain_error)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, handle_http_exception)
    app.add_exception_handler(Exception, handle_unexpected_error)
```

`RequestValidationError.errors()` shape as emitted by pydantic 2.13.5 through fastapi 0.141.1,
for a request with a bad query param and a bad/missing body field `[VERIFIED: executed]`:

```json
[
  {"type": "int_parsing", "loc": ["query", "q"],
   "msg": "Input should be a valid integer, unable to parse string as an integer",
   "input": "nope"},
  {"type": "missing", "loc": ["body", "title"], "msg": "Field required",
   "input": {"count": "abc"}},
  {"type": "int_parsing", "loc": ["body", "count"], "msg": "…", "input": "abc"}
]
```

Note `input` echoes the raw client value and some error types also carry `ctx` and `url`. D-07
forbids exposing any of them — the comprehension above selects only `loc`/`msg`/`type`, which is
why it is a translation and not a pass-through. Produced output:

```json
{"code": "validation_error",
 "errors": [{"field": "query.q",    "message": "…", "type": "int_parsing"},
            {"field": "body.title", "message": "Field required", "type": "missing"},
            {"field": "body.count", "message": "…", "type": "int_parsing"}]}
```

### Ports — all eight shapes, mypy strict clean

```python
# application/ports/repositories.py  -- all one-liners, black keeps them packed, no E301
class TaskRepository(Protocol):
    async def get(self, task_id: UUID) -> Task | None: ...
    async def add(self, task: Task) -> None: ...
    async def update(self, task: Task) -> None: ...
    async def delete(self, task_id: UUID) -> None: ...
    async def completion_stats(self, task_list_id: UUID) -> CompletionStats: ...


# application/ports/clock.py
class Clock(Protocol):
    def now(self) -> datetime: ...


# application/ports/unit_of_work.py
# __aexit__'s signature wraps, so EVERY method here is separated by a blank line (Pitfall 3).
class UnitOfWork(Protocol):
    task_lists: TaskListRepository
    tasks: TaskRepository
    users: UserRepository

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...
```

### Use case + command DTO

```python
# application/dto/commands.py
@dataclass(frozen=True, slots=True)
class ChangeTaskStatusCommand:
    """Every command carries actor_id: the authenticated caller (D-18).

    Presentation fills it from the JWT (Phase 5); the use case -- never the router --
    decides 404 (invisible) versus 403 (visible but not permitted), per ADR-008.
    """

    actor_id: UUID
    task_id: UUID
    new_status: TaskStatus


# application/use_cases/tasks/change_task_status.py
class ChangeTaskStatus:
    """load -> authorize -> invoke domain -> persist -> commit -> map to result."""

    def __init__(self, uow: UnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    async def execute(self, command: ChangeTaskStatusCommand) -> TaskResult:
        async with self._uow:
            task = await self._uow.tasks.get(command.task_id)
            if task is None:
                raise TaskNotFoundError(...)
            ...
            task.change_status(command.new_status, now=self._clock.now())
            await self._uow.tasks.update(task)
            await self._uow.commit()
        return TaskResult.from_entity(task)
```

### `tests/conftest.py` — the three fixtures (verified under `asyncio_mode = auto`)

```python
@pytest.fixture
def app() -> FastAPI:
    application = create_app(Settings(_env_file=None))
    application.include_router(probe_router)  # tests only -- never in production
    return application


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client


@pytest.fixture
async def tolerant_client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """Only for the unexpected-error case: ServerErrorMiddleware re-raises by design."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client
```

No `@pytest_asyncio.fixture`, no `@pytest.mark.asyncio`, no `event_loop` override — `auto` mode
handles async tests and async generator fixtures. Note `Settings(_env_file=None)` mirrors the
existing `tests/unit/test_app_factory.py` pattern; those two env vars must be set via
`monkeypatch` or the fixture must accept them, exactly as Phase 1 does today.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact here |
|--------------|------------------|--------------|-------------|
| RFC 7807 (the brief's wording) | **RFC 9457**, which obsoletes it | July 2023 | Same media type and core members. ADR-005 already chose 9457. Cite both in DECISION_LOG — noticing the supersession is the point. |
| `about:blank` or a fictional `https://` domain for `type` | A stable URN (D-05) | — | RFC 9457 permits non-dereferenceable URIs; it gives `tag:` URIs as an explicit example, and *encourages* (SHOULD, not MUST) dereferenceable ones. A URN is compliant. `[CITED: rfc-editor.org/rfc/rfc9457.html]` |
| `AsyncClient(app=app)` | `AsyncClient(transport=ASGITransport(app=app), base_url=…)` | httpx 0.28 | The old form raises `TypeError`. |
| `class TaskStatus(str, Enum)` | `enum.StrEnum` | Python 3.11 | `f"{status}"` differs between the two on 3.11+. |
| `datetime.utcnow()` | `datetime.now(UTC)` | deprecated in 3.12 | `filterwarnings = error` makes the old form a test failure. |
| `typing.Protocol` from `typing_extensions` | `typing.Protocol`, `typing.Self` | 3.8 / 3.11 | No `typing_extensions` needed on 3.13. |
| A hard-coded stdlib module list | `sys.stdlib_module_names` | Python 3.10 | Makes the ARC-02 test honest. |

**Deprecated / not applicable:**
- `@app.on_event("startup")` — irrelevant here (Phase 2 adds no lifespan), but PITFALLS §15
  flags it for Phase 3.
- `sqlalchemy2-stubs` — not a Phase 2 concern.
- ARCHITECTURE.md's `TaskStatus.CANCELLED` and its transition map — superseded by D-01 and by
  REQUIREMENTS "Out of Scope" (`cancelled` status excluded). Do not copy Pattern 1's enum
  verbatim.

---

## Runtime State Inventory

*(Not a rename/refactor/migration phase — but Phase 2 does touch one existing file, so the
categories are answered explicitly rather than omitted.)*

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | None — no database exists until Phase 3; no datastore holds any string this phase introduces. | none |
| Live service config | None — no external service is configured; the CI Postgres service container is unused by Phase 2 tests. | none |
| OS-registered state | None — no scheduled task, daemon or service registration exists in this project. | none |
| Secrets / env vars | None added. `DATABASE_URL` and `JWT_SECRET` (the only two without defaults) are unchanged; D-08 deliberately does **not** branch on `settings.environment`, so no new setting is introduced. | none |
| Build artifacts / installed packages | `src/taskmanager.egg-info/` exists from the Phase 1 editable install. New sub-packages under `src/taskmanager/` are picked up automatically by the editable install (`[tool.setuptools.packages.find] where = ["src"]`) — **no reinstall needed**, but every new directory needs an `__init__.py` or it will not be importable and `lint-imports` will not see it. | add `__init__.py` to every new package directory |

**Existing files this phase modifies:** exactly one — `src/taskmanager/main.py`, which gains a
`register_exception_handlers(app)` call inside `create_app()`. `tests/unit/test_app_factory.py`
should gain an assertion that the four handlers are registered, so the wiring is covered rather
than merely present.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python (host venv) | all gates | ✓ | 3.14.3 (`.venv`) | — |
| Python 3.13 | CI + Docker (authoritative target) | ✓ (CI/Docker) | 3.13 | — |
| `pytest` + `pytest-asyncio` + `pytest-cov` | all tests | ✓ | 9.1.1 / 1.4.0 / 7.1.0 | — |
| `mypy` (+ pydantic plugin) | `make typecheck` | ✓ | 2.3.1 | — |
| `flake8` + bugbear/comprehensions/pep8-naming | `make lint` | ✓ | 7.3.0 / 26.9.9 / 3.17.0 / 0.15.1 | — |
| `black` / `isort` | `make format` / `make lint` | ✓ | 26.5.1 / 9.0.1 | — |
| `import-linter` (+ `grimp`) | `make arch`, architecture tests | ✓ | 2.15 | — |
| `fastapi` / `starlette` / `httpx` | error-contract tests | ✓ | 0.141.1 / 1.6.0 / 0.28.1 | — |
| Docker | `make docker-test` (optional here) | ✓ | 29.2.0 | run gates on the host venv |
| GNU Make | `make <target>` | ✓ | 3.81 | invoke `.venv/bin/<tool>` directly |
| PostgreSQL | **not needed** — Phase 2 has zero integration tests | n/a | — | — |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** none.

Phase 2 is fully executable offline with the current `.venv`. `git status` was clean before and
after this research; no repository file was modified.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 + pytest-asyncio 1.4.0 (`asyncio_mode = auto`, `asyncio_default_fixture_loop_scope = function`) |
| Config file | `pytest.ini` (brief-mandated literal file; `[tool.pytest.ini_options]` in `pyproject.toml` would be silently ignored) |
| Coverage config | `[tool.coverage.run] source = ["taskmanager"], branch = true`; threshold `--cov-fail-under=75` in `pytest.ini` addopts; no `omit`, no `pragma` |
| Quick run command | `.venv/bin/pytest tests/unit -q --no-cov` — verified: `--no-cov` suppresses the 75% gate so a subset run does not fail spuriously |
| Targeted run | `.venv/bin/pytest tests/unit/domain/test_task.py -q --no-cov -x` |
| Full suite command | `make test` (= `.venv/bin/pytest`, gate included) |
| Full gate | `make lint && make typecheck && make arch && make test` |
| Baseline before this phase | 8 tests, 18 statements, 100% coverage, 0 warnings (`filterwarnings = error`) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| ARC-02 | `TaskStatus`/`TaskPriority` are `StrEnum`, serialize to lowercase strings | unit | `pytest tests/unit/domain/test_task_status.py -q --no-cov` | ❌ Wave 0 |
| ARC-02 | `Task`/`TaskList`/`User` are stdlib dataclasses with `slots=True`; construction enforces invariants | unit | `pytest tests/unit/domain/test_task.py tests/unit/domain/test_task_list.py tests/unit/domain/test_user.py -q --no-cov` | ❌ Wave 0 |
| ARC-02 | **`taskmanager.domain` imports nothing outside the stdlib** (closes Conflict C-01) | architecture | `pytest tests/architecture/test_domain_is_stdlib_only.py -q --no-cov` | ❌ Wave 0 |
| ARC-02 | Existing enumerated contracts still hold with the new packages present | architecture | `pytest tests/architecture/test_layer_boundaries.py -q --no-cov` **and** `make arch` | ✅ exists |
| ARC-06 | Each of the seven families exists with a stable `code` + structured `details` dict | unit | `pytest tests/unit/domain/test_exceptions.py -q --no-cov` | ❌ Wave 0 |
| ARC-06 | The hierarchy is **closed** — recursive `__subclasses__()` equals the expected set | unit | `pytest tests/unit/domain/test_exceptions.py::test_hierarchy_is_closed -q --no-cov` | ❌ Wave 0 |
| ARC-06 | `str(exc) == exc.message`; pickle and `copy.copy` round-trip preserve `details` (Pitfall 9) | unit | `pytest tests/unit/domain/test_exceptions.py::test_domain_error_survives_pickle_and_copy -q --no-cov` | ❌ Wave 0 |
| ARC-06 / D-01 | One test per **allowed** transition (4), one per **forbidden** (`completed→pending`), raising `InvalidStatusTransitionError` specifically — not a generic exception | unit | `pytest tests/unit/domain/test_task.py -k transition -q --no-cov` | ❌ Wave 0 |
| ARC-06 / D-02 | Same-state `X→X` is a no-op: no field changes, no timestamp moves | unit | `pytest tests/unit/domain/test_task.py -k same_state -q --no-cov` | ❌ Wave 0 |
| ARC-06 / D-03 | Entering `completed` sets `completed_at = now`; leaving clears it to `None` | unit | `pytest tests/unit/domain/test_task.py -k completed_at -q --no-cov` | ❌ Wave 0 |
| ARC-06 / D-04 | Blank title, over-length fields, past `due_date` raise `ValidationError`/`BusinessRuleViolationError` | unit | `pytest tests/unit/domain/test_task.py -k validation -q --no-cov` | ❌ Wave 0 |
| ARC-06 / D-14 | A naive `datetime` reaching an entity raises `ValidationError` | unit | `pytest tests/unit/domain/test_task.py -k naive -q --no-cov` | ❌ Wave 0 |
| ARC-04 | Each of the eight ports exists as a `Protocol` and an in-memory fake satisfies it (mypy-checked + named test) | unit | `pytest tests/unit/application/test_ports.py -q --no-cov` **and** `make typecheck` | ❌ Wave 0 |
| ARC-04 | The reference use case runs against fakes: happy path, `NotFoundError`, `AuthorizationError`, commit called exactly once | unit | `pytest tests/unit/application/test_change_task_status.py -q --no-cov` | ❌ Wave 0 |
| ARC-04 | `HTTPException` appears nowhere under `domain`/`application` | architecture | covered by `make arch` (`fastapi`/`starlette` already in both `forbidden_modules` lists) | ✅ exists |
| ARC-07 | A `DomainError` grandchild raised in a route produces 409 problem+json with the full D-06 member set and `errors: {from,to}` — **and** proves the MRO walk (D-10) | api | `pytest tests/api/test_error_contract.py -k domain -q --no-cov` | ❌ Wave 0 |
| ARC-07 / D-07 | A body/query validation failure yields 422 with `errors: [{field, message, type}]` and **no** `loc`/`ctx`/`input` | api | `pytest tests/api/test_error_contract.py -k validation -q --no-cov` | ❌ Wave 0 |
| ARC-07 / D-08 | An unexpected `RuntimeError` yields 500 with the fixed detail and leaks no message/traceback (uses `tolerant_client`) | api | `pytest tests/api/test_error_contract.py -k unexpected -q --no-cov` | ❌ Wave 0 |
| ARC-07 / D-09 | Unknown route → 404 problem+json; wrong verb → 405 with `Allow` preserved; `HTTPException(401)` → 401 with `WWW-Authenticate` preserved (Pitfall 6) | api | `pytest tests/api/test_error_contract.py -k http -q --no-cov` | ❌ Wave 0 |
| ARC-07 | Every error response carries `content-type: application/problem+json` — no bare `{"detail": …}` anywhere | api | `pytest tests/api/test_error_contract.py -q --no-cov` | ❌ Wave 0 |
| ARC-07 / D-10 | The **production** app registers no `/_probe` route | unit | `pytest tests/unit/test_app_factory.py -k probe -q --no-cov` | ✅ file exists, test ❌ |
| ARC-07 | `create_app()` registers all four handlers | unit | `pytest tests/unit/test_app_factory.py -k handlers -q --no-cov` | ✅ file exists, test ❌ |

### Sampling Rate

- **Per task commit:** `.venv/bin/pytest tests/unit -q --no-cov` (sub-second; no I/O in this phase)
- **Per wave merge:** `make lint && make typecheck && make arch && make test`
- **Phase gate:** full suite green, coverage ≥ 75% (target: 100%, matching the Phase 1 baseline),
  **zero warnings**, before `/gsd:verify-work`

### Coverage Strategy

Phase 2 adds roughly 200–250 statements, essentially all of it pure logic reachable without a
database or a network. The 75% floor is not the risk; specific *uncoverable shapes* are. Three
measured facts drive the design:

1. **Protocol modules cost nothing.** Measured: a module with two classes and three `async def …:
   ...` stubs reports **100%** — the `def` lines execute at import, and the `...` bodies are
   removed by the existing `exclude_also = ["\\.\\.\\."]` in `pyproject.toml`. All eight ports
   are free coverage. `[VERIFIED: executed]`
2. **`assert isinstance` adds no partial branches.** Measured: the four-handler module reported
   **100%, 4 branches, 0 partial**. coverage.py does not treat `assert` as a branch. The
   `if not isinstance(...): raise` alternative *would* add four uncoverable partial branches.
   `[VERIFIED: executed]`
3. **Two shapes silently leak uncovered lines** and must be handled at write time, not at the
   gate: the `for`/`return` MRO mapper (→ use `next(...)`, Pitfall 7) and
   `__reduce__`/`_restore`/`__str__` on `DomainError` (measured 77% until a pickle test exists,
   Pitfall 9).

Following those three, 100% is achievable with no `pragma` and no `omit`, which is what
CLAUDE.md §Quality gates demands. As ARCHITECTURE.md notes, coverage here is dominated by the
application layer — pure logic, trivially unit-tested against in-memory fakes implementing the
same Protocols. That is the direct payoff of the layered architecture the brief mandates; say so
in the README (Phase 7).

### Wave 0 Gaps

- [ ] `tests/conftest.py` — `app`, `client`, `tolerant_client` fixtures (does not exist yet; the
      repo currently has **no** conftest.py at all)
- [ ] `tests/probe.py` — the test-only probe router (D-10)
- [ ] `tests/unit/domain/__init__.py`, `tests/unit/application/__init__.py`,
      `tests/api/__init__.py` — the existing `tests/unit/` and `tests/architecture/` both carry
      `__init__.py`; keep the convention
- [ ] `tests/unit/application/fakes.py` — `FakeTaskRepository`, `FakeTaskListRepository`,
      `FakeUserRepository`, `FakeUnitOfWork`, `FrozenClock`
- [ ] `tests/architecture/test_domain_is_stdlib_only.py` — closes Conflict C-01
- [ ] Framework install: **none** — pytest, pytest-asyncio, pytest-cov and httpx are installed
      and configured

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | **declared only** | `AuthenticationError` + `TokenService`/`PasswordHasher` Protocols. No implementation in this phase (Phase 5: PyJWT + pwdlib[argon2]). The 401 *shape* is proven here via the `StarletteHTTPException` handler. |
| V3 Session Management | no | Stateless JWT, Phase 5. |
| V4 Access Control | **declared only** | `AuthorizationError` (403) and the `actor_id` command convention (D-18). ADR-008's 404-invisible / 403-visible rule is a use-case decision; Phase 2 fixes the convention and the status mapping, Phase 4/5 exercise it. |
| V5 Input Validation | **yes** | Two-tier and non-duplicated (D-04): Pydantic at the HTTP boundary for shape/type; entity `__post_init__` + mutators for policy, raising `DomainError`. The `RequestValidationError` translation (D-07) is the 422 half. |
| V6 Cryptography | no | Phase 5. Nothing here hashes or signs. |
| **V7 Error Handling & Logging** | **yes — this is the phase's core security surface** | D-08: a fixed 500 body in every environment, traceback logged server-side only. Verified end-to-end that a `RuntimeError("secret internals: hunter2")` produces a body in which `"hunter2"` does not appear. |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation | Phase 2 status |
|---------|--------|---------------------|----------------|
| Stack trace / exception message leaked in a 500 body | Information Disclosure | Fixed generic detail, no `str(exc)`, no env branch (D-08) | **Mitigated + tested here** — assert the secret substring is absent, not merely that status == 500 |
| Debug-mode traceback HTML from `ServerErrorMiddleware` | Information Disclosure | `FastAPI(debug=...)` defaults to `False`; never set it from an env var | Verify `create_app()` never passes `debug=True`; consider one assertion |
| Client-supplied input echoed back in a validation error | Information Disclosure | D-07 strips Pydantic's `input`, `ctx`, `url`; only `loc`/`msg`/`type` survive | **Mitigated + tested here** — verified the raw `errors()` carries `input` with the client's value |
| Ownership leak via 403-where-404-is-correct (IDOR) | Information Disclosure | ADR-008 / AUTH-06; the **use case** decides, never the router (D-18) | Convention fixed here; enforced in Phase 4/5 |
| Enumerable integer ids | Information Disclosure | UUIDv4 primary keys generated in the application layer (D-11) | Fixed here |
| Inconsistent error shapes revealing internal routing (`{"detail": …}` vs problem+json) | Information Disclosure | D-09: `StarletteHTTPException` also translated | **Mitigated + tested here** |
| `WWW-Authenticate` stripped → broken auth challenge | Spoofing (weakened) | Forward `exc.headers` (Pitfall 6) | **Mitigated + tested here** |
| Assertion stripped under `python -O`, handler crashes | Denial of Service | Verified: no `-O` / `PYTHONOPTIMIZE` in `Dockerfile`, `ci.yml` or `Makefile`; `CMD ["uvicorn", "--factory", …]` | Safe; note it in a comment so nobody adds `-O` later |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The recommended `DomainError` class names and `code` strings (`validation_error`, `business_rule_violation`, `invalid_status_transition`, `not_found`, `conflict`, `authentication_failed`, `authorization_failed`, …) are acceptable. | §Pattern 6 | Low — CONTEXT explicitly leaves names and codes to discretion, requiring only that the seven families exist. Renaming is a find/replace before Phase 4 depends on them. |
| A2 | The class→status mapping (`ValidationError`/`BusinessRuleViolationError` → 422, `InvalidStatusTransitionError` → 409, `NotFoundError` → 404, `ConflictError` → 409, `AuthenticationError` → 401, `AuthorizationError` → 403) matches intent. | §Pattern 6 | Low-medium — 409 for the invalid transition is explicitly locked by D-01; TASK-05 says "409/422" for invalid transitions, so 409 satisfies it. The 422-vs-400 choice for `ValidationError` is a judgement call worth one line in DECISION_LOG. |
| A3 | Shipping `ChangeTaskStatus` as a **real** reference use case (rather than a typed skeleton) is the better reading of CONTEXT's discretion. | §Recommended Project Structure | Low — both are explicitly permitted. If the planner prefers a skeleton, the coverage argument in CONTEXT still applies (anything under `src/` needs a test). |
| A4 | `CompletionStats` belongs in Phase 2 because `TaskRepository.completion_stats` references it. | Conflict C-04 | Medium — it is an addition to CONTEXT's literal deliverable list. The alternative (defer the method to Phase 3) weakens ARC-04's "every port exists". **Worth a one-line user confirmation.** |
| A5 | `presentation/api/errors/` (following ARCHITECTURE.md) rather than a flatter `presentation/errors/`. | §Recommended Project Structure | Very low — CONTEXT says follow ARCHITECTURE.md unless there is a concrete reason to deviate; there isn't one. |
| A6 | Phase 2 should **not** add `pydantic` to the `application-framework-free` contract's `forbidden_modules` despite D-16. | Conflict C-02 | Low-medium — mechanically enforcing D-16 would be stronger, but CONTEXT lists the current contract shape as locked and Phase 4/5 might legitimately want a Pydantic DTO. **Worth a one-line user confirmation.** |
| A7 | Fixing the stale `.importlinter` comment and adding a refining ADR for C-02 is in scope for Phase 2 (rather than deferred to Phase 7). | Conflict C-02 | Low — either is defensible; doing it now keeps documentation from contradicting shipped code, which is the project's whole thesis. |
| A8 | The 405 `Allow` header and the 401 `WWW-Authenticate` header are worth asserting in Phase 2 even though no auth exists yet. | Pitfall 6 | Very low — a five-line test that prevents a Phase 5 debugging session. |

---

## Open Questions

1. **Does `TaskList` need a `CompletionStats` value object in Phase 2?** (Conflict C-04)
   - What we know: `TaskRepository.completion_stats` appears in ARCHITECTURE.md Pattern 2 and
     CONTEXT names ADR-009 as shaping it; a Protocol cannot reference a non-existent type.
   - What's unclear: CONTEXT §Phase Boundary does not list it among the domain deliverables.
   - Recommendation: add it (~10 statements, fully unit-testable, pre-places ADR-009's
     empty-list-→-`0.0` rule). Flag to the user during planning; it is a one-line confirmation.

2. **Should `ValidationError` map to 422 or 400?**
   - What we know: TASK-05 says invalid transitions return "409/422"; D-01 fixes the transition
     at 409. TASK-06 says invalid filter values return 422 — but those are `RequestValidationError`
     (enum parse failure), already 422 by D-07.
   - What's unclear: a domain `ValidationError` (blank title after trimming, over-length) is
     semantically "well-formed but unprocessable" → 422 matches, and matches the 422 an
     evaluator will already have seen from Pydantic. 400 would be defensible.
   - Recommendation: **422**, one sentence in DECISION_LOG explaining the "well-formed but
     semantically invalid" reading. Low risk either way.

3. **Should the closed hierarchy be enforced by a test or only documented?**
   - What we know: "closed" is asserted in ROADMAP SC-2 and CONTEXT but is not mechanically
     checkable by any existing gate.
   - Recommendation: add the `__subclasses__()` set test (~10 statements). It is cheap, it is
     the kind of test that reads as deliberate, and it fails loudly when someone adds an error
     that `STATUS_BY_EXCEPTION` does not map (which would otherwise silently 500).

4. **`grimp` vs `ast` for the stdlib-only test.** (Pitfall 8)
   - What we know: both verified working and equally accurate on the planted test case.
   - Recommendation: `ast` — PITFALLS §9 prescribes it by name, it adds no dependency exposure,
     and it does not carve an exception into Phase 1's explicit "grimp is intentionally absent
     from requirements-dev.txt" rule.

5. **Should `DomainError.details` values be constrained?**
   - What we know: `dict[str, Any]` is what makes the handler able to emit `errors` without
     parsing strings (CONTEXT §Specific Ideas). But `Any` values mean a non-JSON-serialisable
     value (e.g. a raw `TaskStatus` or `UUID`) would raise inside `JSONResponse`, producing a
     500 *from the error handler itself* — the worst possible failure mode.
   - Recommendation: normalise at construction — leaf subclasses store `current.value` and
     `str(task_id)`, never the enum/UUID object (the §Code Examples do this). Optionally add one
     test that `json.dumps(exc.details)` succeeds for every leaf error class. Consider typing it
     `dict[str, str | int | float | bool | None]` to make the rule mechanical; flag to the user.

---

## Sources

### Primary (HIGH confidence — executed in this repository's `.venv`)
- `starlette/_exception_handler.py::_lookup_exception_handler` (starlette 1.6.0, installed) —
  the `for cls in type(exc).__mro__` handler resolution
- `starlette/middleware/errors.py::ServerErrorMiddleware.__call__` (installed) — the
  unconditional `raise exc` after responding
- `starlette/applications.py::build_middleware_stack` (installed) —
  `if key in (500, Exception): error_handler = value`
- `starlette/types.py` (installed) — `HTTPExceptionHandler = Callable[[Request, Exception], …]`,
  the source of the mypy variance error
- Executed end-to-end probe app (fastapi 0.141.1 / starlette 1.6.0 / pydantic 2.13.5 /
  httpx 0.28.1): six error paths, content-types, headers, and the
  `raise_app_exceptions` behaviour
- Executed `mypy 2.3.1 --strict --warn-unreachable` + pydantic plugin over handler, port,
  entity, DTO and use-case probes
- Executed `flake8 7.3.0 --config .flake8` (bugbear 26.9.9, comprehensions 3.17.0,
  pep8-naming 0.15.1) over five candidate `DomainError` shapes and over black-formatted Protocols
- Executed `black 26.5.1` / `isort 9.0.1` with this repo's `pyproject.toml` settings
- Executed `pytest 9.1.1` + `pytest-asyncio 1.4.0` (auto mode) + `pytest-cov 7.1.0` with
  `--cov-branch`: the five-test error-contract suite, the Protocol-coverage probe, and the
  status-mapper coverage comparison
- Executed `grimp` graph builds against this repo (`taskmanager`) and a planted test package
- Executed `lint-imports` (import-linter 2.15) with a `forbidden_modules = *` wildcard contract
- `importlinter/contracts/{forbidden,protected,layers,independence,acyclic_siblings}.py`
  (installed) — available contract types and their options

### Primary (HIGH confidence — official documentation)
- https://www.rfc-editor.org/rfc/rfc9457.html — `type`/`title`/`status`/`detail`/`instance`
  semantics, non-dereferenceable URIs permitted, extension members, `application/problem+json`,
  guidance on multiple problems
- https://fastapi.tiangolo.com/tutorial/handling-errors (via Context7 `/websites/fastapi_tiangolo`)
  — `@app.exception_handler`, overriding `RequestValidationError` /
  `StarletteHTTPException`, and the explicit instruction to register on **Starlette's**
  `HTTPException`

### Secondary (MEDIUM confidence — project artifacts, cross-checked against the codebase)
- `.planning/research/ARCHITECTURE.md` §§Patterns 1–6, §Recommended Project Structure — the
  reference sketches; Pattern 6's `DomainError.__init__` corrected here (Conflict C-03), Pattern
  1's enum superseded by D-01
- `.planning/research/PITFALLS.md` §9, §10, §15, §16, §"Looks Done But Isn't",
  §Pitfall-to-Phase Mapping
- `.planning/research/FEATURES.md` §5 (transition matrix), §6 (completion-% semantics)
- `DECISION_LOG.md` ADR-004, ADR-005, ADR-008, ADR-009
- `CLAUDE.md` §Project Rules
- Phase 1 shipped code: `src/taskmanager/main.py`, `settings.py`,
  `tests/unit/test_app_factory.py`, `tests/architecture/test_layer_boundaries.py`,
  `.importlinter`, `pytest.ini`, `pyproject.toml`, `.flake8`, `Makefile`,
  `.pre-commit-config.yaml`, `.github/workflows/ci.yml`, `Dockerfile`

### Tertiary (LOW confidence — none)
- No claim in this document rests on a single unverified web search.

---

## Metadata

**Confidence breakdown:**

| Area | Level | Reason |
|------|-------|--------|
| Standard stack | HIGH | No new dependencies; every version read from the installed `.venv`, not from memory |
| Architecture / handler wiring | HIGH | End-to-end executed: five passing tests covering six error paths, plus Starlette source read for the two load-bearing behaviours |
| `DomainError` shape | HIGH | Five candidate shapes run through flake8 + mypy + pickle/copy; the winner verified on all three |
| Protocol / port shapes | HIGH | All eight verified mypy-strict-clean, with a conforming fake, plus black/flake8 interactions measured |
| Pitfalls | HIGH | Nine of ten reproduced and fixed in this session; Pitfall 8 (transitive `grimp`) is reasoned from `requirements-dev.txt`'s stated policy, and Pitfall 10 is preventive |
| ARC-02 proof mechanism | HIGH | Both candidate tests executed against a planted violation; the wildcard alternative executed and ruled out |
| Conflicts C-01 – C-04 | HIGH (C-01, C-02, C-03) / MEDIUM (C-04) | C-01–C-03 demonstrated by execution or direct textual contradiction; C-04 is an inference from a Protocol return type |
| Coverage strategy | HIGH | Three shapes measured with `--cov-branch` against the project's own `exclude_also` |

**Research date:** 2026-09-17
**Valid until:** 2026-10-17 (30 days). Everything rests on exact pins that this project freezes
deliberately; the only re-verification trigger is a dependency bump — particularly
`flake8-bugbear` (B042's heuristic), `starlette` (the `ExceptionHandler` type and
`ServerErrorMiddleware`) or `pycodestyle` (E301 on stub defs).
