# Phase 6: Test Hardening & Coverage - Research

**Researched:** 2026-09-19
**Domain:** Test-suite audit and gate construction over an existing 1019-test suite
**Confidence:** HIGH (every number below was measured in this session against the working tree
at `cfa6f8d`, with a clean tree and a running `db` container)

## Summary

This is an audit phase, and the audit has already been run. Everything in this document is a
measurement, not a projection: the five deliberate breaks of D-08 were actually applied to
`src/` and the whole suite actually executed against each one, the two AST gates of D-05 were
prototyped and run over `tests/integration/api/`, the D-03 recorder was prototyped against the
real application, and the coverage/marker questions of D-13 were answered by running pytest
with the selections in question.

Three findings change the shape of the phase. **First, the suite is in better condition than
D-01..D-15 assume**: endpoint totality is already satisfied (the Phase 5 permission matrix
drives all 19 published operations), use-case totality is already satisfied (all 20 use-case
symbols are imported and constructed by `tests/unit/application/` modules that also import the
fakes), and `pytest -m "not integration"` already reaches **91.43 %** — the D-13 worry that a
unit-only run cannot reach 75 % is factually wrong today. The gates are therefore cheap to
plant green; the work is in the sweep and in two real defects.

**Second, there are two real defects, and both are of exactly the kind SC-4 exists to find.**
Disabling token-expiry enforcement (`break 4`) turns **no HTTP test red at all** — only three
unit tests — because `test_unauthenticated_requests_are_refused_with_the_one_shared_body`
never seeds the caller's `users` row, so six of its seven failure modes collapse into the
seventh (unknown subject) and pass for the wrong reason. Dropping `for_update=True` from
`DeleteTaskList` (`break 5`) turns exactly **one** test red — the fakes-based road pin — because
`tests/integration/test_concurrent_writes.py` has no list-deletion case. Both are D-14 findings
to be fixed inside this phase.

**Third, the D-03 recorder cannot read the published route template from Starlette.** On the
pinned stack (FastAPI 0.141.1 / Starlette 1.6.0) `include_router` leaves `_IncludedRouter`
objects in `app.routes`, so `scope["route"].path_format` returns the *router-local* template
(`/task-lists/{list_id}`) and `scope["root_path"]` stays `""`. The prefix has to be recovered,
and the cheapest sound way is a unique-suffix match against `app.openapi()`.

**Primary recommendation:** plant all four totality gates first (they go green on day one and
immediately expose the two defects above as the only red), then spend the phase's bulk on the
D-05/D-06 sweep — 39 tests, mechanical, concentrated in four files.

## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Totality is proven by **permanent pytest gates**, not by a one-time written audit
  matrix. A use case or a route added without its test must fail a build, consistent with the
  repository's "a gate, not a review" rule. The gates live under `tests/architecture/` (or
  beside the harness where they must observe the run) and, being pytest tests, add **no new
  pre-commit hook and no new CI step** (the ADR-015 argument, as already applied to the two
  Phase 4/5 AST gates).
- **D-02:** Use-case totality: a gate enumerates every use-case module under
  `src/taskmanager/application/use_cases/` (today: `auth/{authenticate,login,profile,register}`,
  `task_lists/{create,delete,get,list,update}`,
  `tasks/{assign,change_task_status,create,delete,get,list,list_assigned,update}`, `users/list`,
  plus `access.py`) and fails if one has no unit test that runs against the in-memory fakes. How
  "has a unit test" is decided (module-name convention vs import scan of `tests/unit/application`)
  is the researcher's call, but it must fail on an emptied or renamed package the way
  `REQUIRED_SCANNED_MODULES` does today — never pass silently.
- **D-03:** Endpoint totality is **observed at runtime**, not declared in a registry. The HTTP
  harness records every `(method, route template)` actually requested during the integration
  run, and a final check compares that set against `app.openapi()`. An operation in the OpenAPI
  document that no integration test requested is a failure. This proves the route was really
  hit through HTTP against real PostgreSQL, and leaves no naming convention to maintain. The
  suite runs single-process (no xdist), which is what makes a run-wide recorder sound;
  the researcher must settle how the check behaves when only a subset of tests is selected
  (`-k`, a single file) so that a focused run is not falsely red.
- **D-04:** Negative-path totality is **derived from the source of truth**, not from a
  hand-written checklist:
  - Invalid status transitions are parametrized over the **complement** of
    `ALLOWED_TRANSITIONS` in `src/taskmanager/domain/value_objects/task_status.py` (every
    status pair minus the allowed ones), at the domain level and through HTTP. Adding a fourth
    status must add its negative cases automatically.
  - Authentication failures are parametrized over a **closed list** of modes: missing header,
    non-bearer scheme, malformed token, wrong signature, expired token, unknown subject. Each
    asserts the RFC 9457 `application/problem+json` body, not only the 401.
  - The cross-user 404/403 matrix is already one parametrized test over the real HTTP harness
    (Phase 5 D-04, `tests/integration/api/test_permission_matrix.py`, ADR-083). Phase 6 audits
    it for completeness against the published permission table; it does not rebuild it.
  - The RFC 9457 error contract is audited the same way: every `DomainError` leaf and the
    validation / unexpected-error legs have a test asserting the full body shape.
- **D-05:** **Sweep now, then gate.** One pass fixes today's offenders; then an AST test under
  `tests/architecture/` fails (a) any HTTP test whose only assertion on a response is its status
  code, and (b) any test issuing POST / PATCH / PUT / DELETE with no follow-up read through the
  API. The scout found about 90 bare `assert response.status_code == N` lines under
  `tests/integration/api/`; many are followed by body assertions and are fine, so the real
  offender count is for the sweep to establish. The gate must report `file:line` per offender,
  like the existing AST gates.
- **D-06:** The re-read rule is **"a GET proves the end state"**, on every leg:
  - successful mutation → a GET whose body equals the mutation's response;
  - DELETE → a GET returning the 404 problem body;
  - **rejected** mutation (403 / 404 / 409 / 422) → a GET showing the resource unchanged.
- **D-07:** A heuristic gate that produces false positives is worse than none. If the re-read
  half (D-05 b) cannot be made reliable by AST alone, the researcher may propose a narrow,
  explicit escape hatch (for example a named marker with a required reason) — but never a blanket
  skip, and the status-only half (D-05 a) has no escape hatch.
- **D-08:** A **hand-picked set of about five breaks**, not only the mandated one and not a
  mutation-testing tool. The set is: 1. invert the completion-percentage formula in
  `src/taskmanager/domain/value_objects/completion.py` (mandated by SC-4); 2. allow a forbidden
  transition in `ALLOWED_TRANSITIONS`; 3. flip a 404-vs-403 visibility decision in
  `application/use_cases/access.py`; 4. disable token-expiry enforcement in
  `infrastructure/security/tokens.py`; 5. drop `for_update=True` from one write path.
  Each break must turn the suite red; the researcher may swap an item for a better one in the
  same risk area, but the first is fixed. No new dependency: **mutmut is not added**.
- **D-09:** The check is **scripted, not gated**. A script under `scripts/` with a Makefile
  target (working name `make break-check`) applies each break, runs the relevant tests, asserts
  red, and restores the file — an evaluator can rerun it. It is **not** part of `make test`,
  pre-commit or CI, so the normal loop stays at about 10 seconds. The script must restore the
  working tree even when interrupted, and must refuse to run on a dirty tree.
- **D-10:** The episode is recorded in the `AI_WORKFLOW.md` incident log (dated entry, which
  tests went red for each break, and anything a break did **not** turn red). A break that
  survives is a finding handled under D-14.
- **D-11:** Honesty is proven by **three-way agreement plus a configuration pin**. The total is
  recorded from the host (`make test`), Docker (`make docker-test`) and CI, and they must
  agree. A small pytest test reads `pytest.ini` and `pyproject.toml` and fails if the threshold
  drops below 75, an `omit` entry appears, coverage `source` stops being `taskmanager`, or a
  `# pragma: no cover` appears anywhere under `src/`. This turns the existing CLAUDE.md
  coverage rule into a gate.
- **D-12:** Carried forward, not reopened: the threshold stays **75**; 100% is a norm, not a
  requirement (Phase 4 context); the threshold is never reached with pragmas or `omit`; tests
  are outside the denominator because `source = ["taskmanager"]`.
- **D-13:** **Light tidy only.** Move the stray `tests/api/test_error_contract.py` to its right
  home, make sure every test carries the `unit` or `integration` marker so that
  `pytest -m unit` runs with no database, and add a `make test-unit` target. **No deletions and
  no rewrites**: nothing in the brief rewards a smaller suite and a deletion can quietly reduce
  what is proven. Note that `pytest -m unit` alone will not reach 75% by design — the target
  must not trip the coverage gate (researcher to choose how: `--no-cov` or an explicit override).
- **D-14:** When the audit finds a test that passes for the wrong reason, or a real product
  bug, it is **fixed inside Phase 6** and logged in the `AI_WORKFLOW.md` incident log, as
  earlier phases did. Product fixes stay minimal (a bug fix, not a redesign); anything larger is
  written to Deferred Ideas instead of being built.
- **D-15:** **Few, large plans with light ceremony — target 3 to 4 plans for the whole phase.**
  Acceptance criteria are behaviour-based and expressed as test commands, not grep counts over
  prose. No evidence / RED / falsification transcript files, with one exception: the
  deliberate-break episode (D-08..D-10) is itself the evidence SC-4 asks for and belongs in
  `AI_WORKFLOW.md`. The plan checker must not push toward more ceremony. After any `gsd-sdk`
  state handler runs, diff `STATE.md` and repair it by hand (the handlers are known to regress it).

### Claude's Discretion

- How the use-case gate maps a module to "its" unit test (D-02).
- The recording mechanism for D-03 (httpx event hook, ASGI middleware in the test app, or a
  wrapper around `api_client` / `authenticated_client`) and its behaviour under partial runs.
- The exact home of `test_error_contract.py` after the move (D-13).
- Substituting breaks 2–5 within the same risk area (D-08).
- Whether new rules earn ADR entries in `DECISION_LOG.md` (next free number is ADR-085) and a
  CLAUDE.md "Project Rules" bullet; the precedent is that every new gate gets both.

### Deferred Ideas (OUT OF SCOPE)

- **Mutation testing with mutmut** — declined for this phase; a line in Phase 7's "what I'd do next".
- **Running the break check in CI** — declined.
- **Trimming redundant tests** — declined.
- **A written use-case → test / endpoint → test matrix** for the README — belongs to Phase 7.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TEST-01 | Unit tests cover domain rules and every use case using in-memory fakes, no DB/HTTP | §D-02: import-scan gate design; all 20 use-case symbols already covered (measured) |
| TEST-02 | Integration tests exercise every endpoint through HTTP against real PostgreSQL, isolated per test | §D-03: runtime recorder design + `_IncludedRouter` pitfall; all 19 operations already driven by the permission matrix (measured) |
| TEST-03 | Coverage >= 75% enforced by `--cov-fail-under=75` locally and in CI | §D-11/D-13: measured baseline 100 %, three invocation sites identified, 0 pragmas, pin-test design |
| TEST-04 | Negative-path tests for the error contract, 404/403 matrix, invalid transitions, auth failures | §D-04: exact gaps listed with file paths; 4 forbidden transition pairs, 9 raisable error leaves, 7 auth modes |
| TEST-05 | Every test contains meaningful assertions; deliberate-break spot check performed and recorded | §D-05/06/07 sweep sizing (39 tests), §D-08/09 five breaks measured end to end with exact failure lists |

## Project Constraints (from CLAUDE.md)

Directives that bind this phase specifically. Everything here was verified against the working
tree, not assumed.

| Directive | State today | Consequence for Phase 6 |
|-----------|-------------|-------------------------|
| Coverage gated at 75 %, never lowered, never reached with `# pragma: no cover` or an `omit` entry | 100 % line+branch; **0** pragmas under `src/` (verified by grep) | D-11's pin-test can assert `pragmas == 0` as a hard literal, not a ceiling |
| "A new gate goes in two places" (`.pre-commit-config.yaml` **and** `.github/workflows/ci.yml`) — pytest-based gates exempt | pre-commit runs black, isort, flake8, mypy, import-linter. **It does not run pytest.** CI and the Docker `test` stage do | The four new gates are pytest tests → no hook, no CI step (ADR-015). `make break-check` is in neither, by D-09. Note the CLAUDE.md sentence "the hook set … already run [pytest]" is inaccurate; the exemption still holds because CI and Docker do run it |
| `make lint`, `make typecheck`, `make arch`, `make test` green before any commit | All green at `cfa6f8d` | Every new gate file must pass `black`, `isort`, `flake8` (incl. bugbear) and `mypy --strict` over `tests/` too — `mypy src tests` is the invocation |
| `filterwarnings = error` in `pytest.ini` | In force | Any new fixture/hook must emit no warnings. `--no-cov` was verified to produce none (see D-13) |
| Everything in English; no AI attribution trailer in commits | — | Applies to the new gate docstrings and the `AI_WORKFLOW.md` entry |
| Every new gate earns an ADR + a CLAUDE.md "Project Rules" bullet | Last is ADR-084 | Next free number is **ADR-085**; this phase plausibly adds four to six |

## Measured Baseline (2026-09-19, host, `cfa6f8d`)

```
.venv/bin/pytest          -> 1019 passed in 9.57s, TOTAL 1643 stmts / 154 branches, 100%
```

| Slice | Tests | Notes |
|-------|-------|-------|
| `tests/api/` | 17 | the stray directory (D-13) |
| `tests/architecture/` | 13 | 4 gate modules |
| `tests/integration/` | 315 | all carry `pytest.mark.integration` |
| `tests/unit/` | 674 | **none carry a marker** |
| **Total** | **1019** | |

```
.venv/bin/pytest -m unit            -> 1019 deselected in 0.23s   # zero tests carry it
.venv/bin/pytest -m integration     -> 315 collected
.venv/bin/pytest -m "not integration" -> 704 passed in 1.56s, 91.43% coverage
.venv/bin/pytest -m "not integration" --no-cov -> 704 passed in 1.44s, no warnings
```

## D-02 — Use-case totality: use an import scan, not a name convention

**A module-name convention does not exist today and cannot be invented cheaply.** The actual
mapping is disambiguated by domain, not by module name:

| Use-case module | Its unit test |
|---|---|
| `task_lists/create.py` | `test_create_task_list.py` |
| `tasks/create.py` | `test_create_task.py` |
| `tasks/assign.py` | `test_assign_task.py` **and** `test_unassign_task.py` (two classes in one module) |
| `auth/authenticate.py` | `test_authenticate_actor.py` |
| `auth/register.py` | `test_register_user.py` |
| `access.py` | `test_access.py` (three functions, no class) |

A name-convention gate would need a hand-written `{module: test_module}` map — which is exactly
the hand-maintained registry D-02 and D-03 are written to avoid.

**Recommendation: enumerate the public symbols, then AST-scan the test modules for imports.**
Verified feasible: every one of the 20 symbols is imported by at least one module under
`tests/unit/application/`, and **23 of the 25 test modules there import the fakes** (the two that
do not are `test_dtos.py` and `test_unset.py`, which test no use case).

The 20 symbols, measured from `src/`:

| Package | Symbols |
|---|---|
| `access.py` | `visible_task_list`, `visible_task`, `owned_task` (functions) |
| `auth/` | `AuthenticateActor`, `Login`, `GetProfile`, `RegisterUser` |
| `task_lists/` | `CreateTaskList`, `DeleteTaskList`, `GetTaskList`, `ListTaskLists`, `UpdateTaskList` |
| `tasks/` | `AssignTask`, `UnassignTask`, `ChangeTaskStatus`, `CreateTask`, `DeleteTask`, `GetTask`, `ListTasks`, `ListAssignedTasks`, `UpdateTask` |
| `users/` | `ListUsers` |

Gate shape, following `test_routers_raise_no_http_exception.py` house style:

1. Walk `src/taskmanager/application/use_cases/**/*.py`, collect every module-level `class` or
   `async def` whose name does not start with `_` → the expected symbol set.
2. Walk `tests/unit/application/test_*.py`; for each module collect (a) `ImportFrom` targets
   rooted at `taskmanager.application.use_cases`, (b) whether it also imports `fakes`, (c) the
   set of `ast.Call` func names.
3. A symbol is **covered** iff some module satisfies all three: imports it, imports the fakes,
   and *constructs or calls* it (`ast.Call` on the bound name). Report `symbol -> module:line`
   for every uncovered one.
4. Non-vacuity guard: a `REQUIRED_USE_CASE_SYMBOLS: Final[frozenset[str]]` naming all 20, asserted
   `<= discovered`, so a renamed or emptied package fails rather than passing on an empty set.
   This is the `REQUIRED_SCANNED_MODULES` pattern D-02 asks for, applied to symbols.

**Known and acceptable limit, to be stated in the gate docstring:** an import plus a construction
is not proof of an *exercise*. `test_write_paths_hold_what_they_change.py` imports and constructs
13 of the 20 on its own, so it could in principle carry the whole gate. Requiring two distinct
modules would be arbitrary; requiring an `await instance.execute(...)` is brittle across the
three call shapes in use. The honest framing — write it down rather than hide it — is that this
gate proves *reachability from the fakes-based suite*, and the coverage gate proves execution.

## D-03 — Endpoint totality: record, then resolve the template by unique suffix

### The published surface: 19 operations

`app.openapi()["paths"]` yields exactly 19 `(method, path)` operations (measured):

```
GET    /health
POST   /api/v1/auth/register        POST /api/v1/auth/login        GET /api/v1/auth/me
GET    /api/v1/users                GET  /api/v1/tasks/assigned-to-me
POST   /api/v1/task-lists           GET  /api/v1/task-lists
GET    /api/v1/task-lists/{list_id}          PATCH /api/v1/task-lists/{list_id}
DELETE /api/v1/task-lists/{list_id}
POST   /api/v1/task-lists/{list_id}/tasks    GET /api/v1/task-lists/{list_id}/tasks
GET    /api/v1/task-lists/{list_id}/tasks/{task_id}
PATCH  /api/v1/task-lists/{list_id}/tasks/{task_id}
DELETE /api/v1/task-lists/{list_id}/tasks/{task_id}
PATCH  /api/v1/task-lists/{list_id}/tasks/{task_id}/status
PUT    /api/v1/task-lists/{list_id}/tasks/{task_id}/assignee
DELETE /api/v1/task-lists/{list_id}/tasks/{task_id}/assignee
```

**The gate is already satisfied.** `tests/integration/api/test_permission_matrix.py`'s `MATRIX`
has **19 rows**, one per operation, each driven four times (owner / assignee / stranger /
anonymous) through `matrix_client`, which is built on `authenticated_client`. So a recorder
attached to the two conftest fixtures sees all 19 without any test being added. Plant it green.

### The pitfall: `scope["route"].path_format` is router-local on this stack

Measured on FastAPI 0.141.1 / Starlette 1.6.0:

```
app.routes -> [Route /openapi.json, Route /docs, Route /docs/oauth2-redirect, Route /redoc,
               _IncludedRouter, _IncludedRouter, ... x7]

GET /api/v1/task-lists/<uuid>
  scope["route"].path_format == "/task-lists/{list_id}"     # NOT the published path
  scope["root_path"]         == ""                          # prefix is NOT here either
  scope["path"]              == "/api/v1/task-lists/<uuid>"  # concrete, not a template
```

This is the same fact ADR-057 already records about `app.routes` (an included router stays an
opaque object). An httpx response event hook has the same problem from the other side — it sees
only the concrete path. **Neither mechanism gives the published template directly.**

### Recommended mechanism

A **pure-ASGI wrapper around the app at the transport**, in `tests/integration/conftest.py`,
applied in both `api_client` and `authenticated_client`. It wraps rather than calling
`app.add_middleware(...)`, so the application under test is byte-for-byte the production one:

```python
REQUESTED: Final[set[tuple[str, str]]] = set()   # module-level, session-lived

def _recording(app: FastAPI) -> ASGIApp:
    async def middleware(scope, receive, send):
        await app(scope, receive, send)          # the router mutates `scope` in place
        if scope["type"] == "http":
            route = scope.get("route")           # absent on 404/405 — nothing to record
            if route is not None:
                REQUESTED.add((scope["method"].lower(), route.path_format))
    return middleware
```

Then resolve each recorded router-local template to a published one by **unique suffix match**
against `app.openapi()["paths"]`: `/task-lists/{list_id}` is a suffix of exactly one published
path. Assert uniqueness inside the resolver and fail loudly on a collision, so a future router
whose tail overlaps another's fails rather than being silently miscounted. (The alternative —
compile each published template to a regex with `{param}` → `[^/]+` and match `scope["path"]` —
also works and has no collisions in today's 19; the suffix form is shorter and needs no regex.)

### Behaviour under a partial run

Make the check **two-sided and always-on**, so it is useful on every invocation and total only
on a full one:

- **Always:** every *recorded* operation must exist in the OpenAPI document. This catches a
  route hit through HTTP that the document does not publish, and it is meaningful under `-k`.
- **Only on a full run:** every *published* operation must have been recorded.

Detect a partial run from `config.option` rather than by counting: `keyword` (`-k`), `markexpr`
(`-m`), `deselect`, `last_failed`/`failed_first`/`stepwise`, and `config.args` differing from the
`testpaths` default. When any is set, `pytest.skip("partial selection — totality is asserted on a
full run")` the totality half only. CI runs a bare `pytest` (`.github/workflows/ci.yml`, step
"Tests with coverage gate": `run: pytest`), and the Docker `test` stage's `CMD ["pytest"]` is
likewise bare, so the totality half is exercised in both.

### Ordering

The check must run after every HTTP test. Do **not** rely on filename sort. Add a
`pytest_collection_modifyitems` hook in `tests/integration/conftest.py` that moves the totality
item to the end of the collected list. Today's sort order happens to work
(`tests/integration/api/*` → `tests/integration/test_*.py`, and `tests/unit/` last) but nothing
enforces it; the hook does, in three lines.

**One property to state in the docstring:** a route "requested" by a test that only proved a 401
still counts as requested, because the route matched before the dependency refused. That is the
honest reading of D-03 ("an operation that no integration test requested is a failure") and it is
why the assertion-quality gate (D-05) is the one that makes each request *mean* something.

## D-04 — Negative-path totality: what exists, and the four gaps

### Invalid status transitions

`ALLOWED_TRANSITIONS` (`src/taskmanager/domain/value_objects/task_status.py:30-34`) permits 5 of
9 pairs. The **complement is 4 pairs**: `(pending, pending)`, `(in_progress, in_progress)`,
`(completed, pending)`, `(completed, completed)`.

| Level | Today | Gap |
|---|---|---|
| Domain | `test_task.py:136` covers `completed→pending`; `:148/:158/:168` cover the three self-transitions as **idempotent no-ops**, not refusals | The self-pairs are *allowed behaviour* (no-op), so the "complement" is not uniformly a refusal. **The parametrization must distinguish the two legs**, or it will assert a refusal that the domain deliberately does not make |
| Domain (table) | `test_task_status.py:44/49/62/67` pin the table, self-exclusion and the one forbidden pair | No gap |
| HTTP | `test_tasks.py:980 test_an_invalid_transition_is_409_naming_the_transition` — one hard-coded case | **Gap:** not derived from `ALLOWED_TRANSITIONS`; a fourth status adds no case |

**Recommendation:** parametrize over `[(a, b) for a in TaskStatus for b in TaskStatus if b not in
ALLOWED_TRANSITIONS[a]]` and split on `a is b`: self-pairs assert the 200 no-op, cross-pairs
assert the 409 `invalid_status_transition` body. That is 4 cases today and grows automatically.

### Authentication failures

Already **seven** modes, a superset of D-04's six (`tests/integration/api/test_auth.py:494-570`,
`UNAUTHENTICATED_CASES`): `no_header`, `a_basic_scheme`, `an_empty_bearer_parameter`, `garbage`,
`a_foreign_secret_token`, `an_expired_token`, `a_token_for_an_unknown_subject`. Each asserts the
full problem+json body, the `WWW-Authenticate: Bearer` challenge, and that the offered credential
is not echoed. `test_auth.py:620` additionally asserts all seven bodies are byte-identical.

**Gap — and it is the phase's headline defect.** The test takes only `authenticated_client`; it
never seeds a `users` row for `OWNER_ID`. `AuthenticateActor` confirms the subject on every
request, so **six of the seven cases are refused for the unknown-subject reason regardless of
what the credential is**. Proof: with `verify_exp: False` planted in `tokens.py`, all eight tests
in that selection still pass (measured). Fix: seed the caller before driving the cases, so the
expired / foreign-signed / malformed cases are refused by the mechanism they name.

### Cross-user 404/403 matrix

`test_permission_matrix.py` — 19 rows × 4 callers = 76 cells, `MATRIX` at line 188. Audited: the
19 rows are exactly the 19 published operations (§D-03). No gap in coverage.

**Gap:** nothing binds `MATRIX` to the published operation set — a new route would need a row
added by hand. The D-03 recorder closes this incidentally (a new route with no matrix row and no
other test fails the totality half), which is a good reason to plant D-03 first.

### RFC 9457 error contract per `DomainError` leaf

`src/taskmanager/domain/exceptions.py` defines 13 classes. Nine are actually raised in `src/`
(counted): `ValidationError` ×12, `AuthenticationError` ×7, `TaskNotFoundError` ×5,
`UserNotFoundError` ×4, `TaskListNotFoundError` ×3, `DuplicateTaskListNameError` ×3,
`EmailAlreadyRegisteredError` ×2, `InvalidStatusTransitionError` ×1, `AuthorizationError` ×1.
The other four (`DomainError`, `BusinessRuleViolationError`, `ConflictError`, `NotFoundError`) are
abstract parents, never raised.

**All nine raisable codes already have a test asserting the body** (grep for each `code` string
across `tests/`): `validation_error`, `invalid_status_transition`, `task_not_found`,
`task_list_not_found`, `user_not_found`, `duplicate_task_list_name`, `email_already_registered`,
`authentication_failed`, `authorization_failed` — plus `internal_error` in
`tests/api/test_error_contract.py`.

**Gap:** no gate. A tenth leaf added later would ship untested. **Recommendation:** a test that
walks `DomainError.__subclasses__()` recursively, collects every `code` for a class that is
*raised anywhere under `src/`* (AST scan of `raise <Name>` statements, the same walk the existing
gate uses), and asserts each such `code` appears as a literal in at least one module under
`tests/`. Cheap, derived from the source of truth, and it passes today.

## D-05 / D-06 / D-07 — Assertion quality: measured offender counts

Both halves were prototyped and run over `tests/integration/api/` in this session.

### Half (a) — status-only assertions

The scout's "~90 bare `assert response.status_code == N` lines" is a raw line count, not an
offender count. Two facts collapse it:

1. The dominant shape is `assert response.status_code == 201` / `body = response.json()` /
   `assert body[...]`. A naive scan flags it because the later asserts name `body`, not
   `response.json()`. Taint-tracking `body` from `response` removes ~19 of 29.
2. There is an established **named-helper** convention: `assert_forbidden(response)`,
   `assert_not_found(response, id)`, `assert_task_not_found(...)`, `assert_user_not_found(...)`,
   `assert_the_body_the_status_promises(cell, response)`, `assert_unauthenticated(response)`,
   `anonymised(response, *ids)`. These carry the body assertions. Resolving them removes 4 more.

| Scan | Offenders |
|---|---|
| Naive (`.status_code` present, no literal `.json()` in an assert) | 29 |
| + taint-tracking `body = response.json()` | 10 |
| + resolving same-file `Response`-typed helpers | **6** |

The final 6, with the verdict on each:

| Location | Verdict |
|---|---|
| `test_auth.py:620 test_every_unauthenticated_refusal_carries_the_same_body_as_the_others` | **False positive.** It calls `anonymised(response)`, imported *from another module*. The gate must resolve cross-module helper imports, not just same-file defs |
| `test_assignment.py:682 test_the_assignee_cannot_see_the_list_the_task_lives_in` | **Real.** `assert the_task.status_code == 200` with no body check on the visible half. Fix: assert the task body |
| `test_assignment.py:943 / :987 / :1069` (notification tests) | The response is status-only, but each asserts on **`caplog` structured fields** — the behaviour under test. Not a hole |
| `test_statements.py:134 test_the_recorder_sees_statements_at_all` | Same: asserts on the `statements` fixture |

**Recommendation for D-07's "no escape hatch" on half (a):** do not add one — instead specify the
rule correctly. The property is *"every HTTP test asserts something beyond the status code"*,
where "something" is any of: a response-body/header/text assertion, a call to a
`Response`-annotated helper (resolved across modules), or an assertion naming a recorded
side-effect fixture (`caplog`, `statements`). All four are AST-decidable, none is a per-test
opt-out, and the rule then has **1 genuine offender** today.

### Half (b) — mutation with no follow-up read

Measured: **87** of 129 HTTP tests under `tests/integration/api/` issue a mutating verb;
**39** have no `client.get(...)` after the last mutation.

| File | Offenders |
|---|---|
| `test_task_lists.py` | 15 |
| `test_tasks.py` | 9 |
| `test_auth.py` | 9 |
| `test_assignment.py` | 5 |
| `test_permission_matrix.py` | 1 |

Composition: most are **rejected** mutations (422 request-validation, 422 domain-validation,
409 duplicate, 404 absent) where D-06 requires "a GET showing the resource unchanged" — a
genuinely missing assertion, and a mechanical two-line fix each. A minority cannot be fixed by
a GET at all:

| Case | Why no GET exists |
|---|---|
| `POST /auth/login` ×5 (`test_auth.py:293/323/349/392`, `test_permission_matrix.py:525`) | Login mutates nothing; there is no resource to re-read |
| `PUT/DELETE .../assignee` notification tests ×5 (`test_assignment.py:943-1102`) | The asserted effect is a log record; the assignment's persistence is already proved by `test_a_notifier_failure_leaves_the_assignment_committed` |
| `POST /auth/register` ×4 (`test_auth.py:161/211/241/266`) | A GET **is** possible via `GET /api/v1/users`. Fix these rather than exempt them |

**Recommendation (D-07 escape hatch, half (b) only):** a registered marker
`@pytest.mark.no_reread("<reason>")`, gated three ways so it cannot become a blanket skip:

1. the reason argument must be a non-empty string literal (asserted by the gate);
2. every marked test's node id must appear in a `REQUIRED_NO_REREAD: Final[frozenset[str]]` in the
   gate module — adding a marker requires editing the gate file in the same commit, exactly as
   `EXPECTED_CONTRACT_NAMES` and `REQUIRED_SCANNED_MODULES` already do;
3. a companion test asserts the frozenset is non-empty **and** that every name in it still exists
   and still carries the marker, so an exemption cannot outlive its reason.

Expected size of the exemption set: **~10**. Expected size of the sweep: **~29 test edits**,
mechanical, in four files. This is the single largest piece of work in the phase and should own
a plan of its own.

Both gates must resolve the `authenticated_client` / `api_client` two-tuple shape
(`client, app = api_client`) to know which name is the client; today every HTTP test uses one of
those two fixture names plus `matrix_client`, `healthy_client`, `probe_client`, `client`,
`tolerant_client`. Discover client names by looking for `AsyncClient`-annotated fixtures rather
than hard-coding the list, and guard non-vacuity with a `REQUIRED_SCANNED_TEST_MODULES` frozenset.

## D-08 / D-09 / D-10 — The five breaks, actually run

Every break below was applied to the working tree, the **whole** suite was run (`pytest -q
--no-cov -p no:cacheprovider`), and the tree restored with `git checkout -- src/`. Baseline for
comparison: 1019 passed.

| # | File / expression | Mutation applied | Result |
|---|---|---|---|
| 1 | `domain/value_objects/completion.py:33` — `return round(self.completed / self.total * 100, 2)` | → `round((self.total - self.completed) / self.total * 100, 2)` | **17 failed, 1002 passed** |
| 2 | `domain/value_objects/task_status.py:33` — `TaskStatus.COMPLETED: frozenset({TaskStatus.IN_PROGRESS}),` | add `, TaskStatus.PENDING` | **6 failed, 1013 passed** |
| 3 | `application/use_cases/access.py:238` — `if task.assignee_id == actor_id:` | → `!=` | **33 failed, 986 passed** |
| 4 | `infrastructure/security/tokens.py:118` — `options={"require": _REQUIRED_CLAIMS},` | add `"verify_exp": False` | **3 failed, 1016 passed** |
| 5 | `application/use_cases/task_lists/delete.py:43` — `..., command.actor_id, for_update=True` | drop `, for_update=True` | **1 failed, 1018 passed** |

### Which tests go red, per break

**1 — completion inverted (the mandated one).** 17 failures across all four layers: three in
`tests/unit/domain/test_completion.py`, four in `tests/unit/application/` (`test_dtos.py` ×3,
`test_fakes.py`, `test_get_task_list.py`, `test_list_tasks.py`, `test_ports.py`), two in
`tests/integration/test_repositories_*`, and five through HTTP
(`test_task_lists.py::test_get_returns_the_list_with_its_statistics` and
`::test_the_collection_returns_every_list_of_the_actor_with_statistics`,
`test_tasks.py::test_the_statistics_cover_the_whole_list_whatever_the_filter` and
`::test_filtering_by_both_applies_the_conjunction`, plus one statement-count test). Confirmed the
percentage is computed **in Python** (`application/dto/results.py:125` and `:167` read
`stats.percentage`; SQL returns only the two counters), which is why the break reaches HTTP.

**2 — forbidden transition allowed.** `test_task_status.py` ×2, `test_task.py` ×1,
`test_change_task_status.py` ×1, `test_tasks.py::test_an_invalid_transition_is_409_naming_the_transition`,
and `test_concurrent_writes.py::test_a_stale_writer_cannot_persist_a_forbidden_transition`.

**3 — 403/404 visibility flipped.** The loudest break: 33 failures, including 8 permission-matrix
cells (rows 14/15/17/18 × assignee and stranger), 5 in `test_assignment.py`, 2 in `test_tasks.py`,
and 18 unit tests across `test_access.py`, `test_assign_task.py`, `test_delete_task.py`,
`test_unassign_task.py`, `test_update_task.py`.

**4 — token expiry disabled. FINDING: no HTTP test goes red.** Only
`tests/unit/infrastructure/test_tokens.py` fails (3 tests). A targeted re-run confirms
`pytest tests/integration/api/test_auth.py -k "unauthenticated or refusal"` → **8 passed** with
the break in place. Root cause as diagnosed in §D-04: the seven auth cases never seed the
caller's `users` row, so every one of them is refused by `AuthenticateActor`'s confirmation read
rather than by the mechanism it names. **This is a D-14 finding.** Fix inside the phase (seed the
caller), then re-run break 4 and record both the before and the after in `AI_WORKFLOW.md` — the
"what a break did *not* turn red" line D-10 asks for.

**5 — `for_update=True` dropped from `DeleteTaskList`. FINDING: one test red, and not a
concurrency one.** Only `test_write_paths_hold_what_they_change.py::test_delete_task_list_holds_the_list_it_removes`
fails. `tests/integration/test_concurrent_writes.py` has four cases
(`:296` stale writer / forbidden transition, `:337` two list patches serialised, `:371` a read
never waits, `:398` owner and assignee on one row) and **none covers list deletion**. The break
is caught, so the suite is not wrong — but the lock on the delete path is proven only against
fakes. Report it; a fifth case in `test_concurrent_writes.py` is a small, in-scope fix under D-14
if the planner wants it, otherwise a Deferred Idea.

### The script (D-09)

Follow the `scripts/init-env.sh` precedent: POSIX `sh`, `set -eu`, no `sed -i` (its `-i` argument
differs between GNU and BSD — the reason that script uses `awk` + `mv`), resolved against the
working directory so a test can run it in a temp dir, a Makefile target, and a unit test that
executes it.

Required behaviours, all learned from the runs above:

| Requirement | Mechanism |
|---|---|
| Refuse a dirty tree | `git status --porcelain -- src/` must be empty, else exit 1 with the remedy |
| Restore on interrupt | `trap 'git checkout -- src/' EXIT INT TERM` — installed **before** the first mutation |
| Apply a break | A here-doc Python one-liner doing an exact literal `str.replace` with an `assert old in s` precondition, so a drifted line fails loudly instead of silently mutating nothing. (This is exactly how each break above was applied.) |
| Run the relevant tests | Target the named files per break, not the whole suite, so the script finishes in seconds. Use `--no-cov -p no:cacheprovider` so it never rewrites `coverage.xml` or `.pytest_cache` |
| Assert red | Invert the exit status: a **passing** run is the script's failure. Print which tests failed |
| Restore | `git checkout -- src/`, then re-assert `git status --porcelain -- src/` is empty |

Do not put it in `make test`, pre-commit or CI (D-09). Name it `make break-check`.

## D-11 / D-13 — Coverage honesty and suite shape

### The three invocation sites (for the three-way agreement)

| Site | Command | Notes |
|---|---|---|
| Host | `make test` → `.venv/bin/pytest` | Python 3.14.3 venv; needs `make up` for PostgreSQL |
| Docker | `make docker-test` → `docker compose run --rm --build test` | Dockerfile stage `test`, `CMD ["pytest"]`, Python 3.13, `TEST_DATABASE_URL` → `taskmanager_test` on `db` |
| CI | `.github/workflows/ci.yml` step "Tests with coverage gate": `run: pytest` | Python 3.13, `postgres:18-alpine` service |

All three are a **bare `pytest`**, so the `pytest.ini` addopts (`--cov=taskmanager
--cov-fail-under=75 --cov-report=xml`) are identical bytes in all three. That is what makes the
three-way agreement meaningful, and it is what the D-03 partial-run detection relies on.

### The configuration pin (D-11)

Facts to assert, all verified true today:

| Assertion | Verified value |
|---|---|
| `pytest.ini` addopts contain `--cov-fail-under=N` with `N >= 75` | 75 |
| `pytest.ini` addopts contain `--cov=taskmanager` | present |
| `[tool.coverage.run] source == ["taskmanager"]` | true |
| `[tool.coverage.run] branch is true` | true |
| `[tool.coverage.run]` has **no** `omit` key | true |
| `[tool.coverage.report]` has **no** `fail_under` key (the threshold has exactly one home) | true |
| `[tool.coverage.report] exclude_also` is exactly the four known entries | `if TYPE_CHECKING:`, `raise NotImplementedError`, `@abstractmethod`, `\.\.\.` |
| No `# pragma: no cover` anywhere under `src/` | **0 occurrences** |

Parse `pytest.ini` with `configparser` and `pyproject.toml` with `tomllib` (stdlib, Python 3.11+).
Put it in `tests/architecture/test_coverage_configuration.py`; it needs no database, so it must
carry the `unit` marker per D-13. Pin `exclude_also` by exact list, not by length — a fifth entry
is how a real exclusion would be smuggled in.

### Markers (D-13) — the real state

**Zero tests carry `unit`.** `pytest -m unit` deselects all 1019 (measured). 315 carry
`integration` via a module-level `pytestmark`; 704 are unmarked: all of `tests/unit/` (674),
all of `tests/architecture/` (13), and all of `tests/api/` (17).

Recommendation: add `pytestmark = pytest.mark.unit` at module level in each of the 704's modules
(same one-line convention as the integration side — 41 files). Then add a
`pytest_collection_modifyitems` guard in `tests/conftest.py` that **fails** if any collected item
carries neither marker, so D-13's rule survives the next new file. That guard is itself the gate;
no CI step is needed.

`tests/architecture/` is I/O-free (it reads source files and parses TOML/INI) so `unit` is the
right marker for it; D-13 offers only the two.

### `make test-unit` and the coverage gate — the D-13 premise is wrong

```
.venv/bin/pytest -m "not integration"          -> 704 passed, 91.43% coverage, 1.56s
```

**The unit-only slice already clears 75 %.** The premise "pytest -m unit alone will not reach 75%
by design" does not hold at this suite size. Use `--no-cov` anyway, for two reasons that survive
the correction:

1. `pytest.ini` also sets `--cov-report=xml`, so a unit-only run **overwrites `coverage.xml`**
   with a partial number. That file is the three-way agreement's artifact; a fast-loop command
   must not clobber it.
2. 91.43 % is incidental, not designed. A `make test-unit` whose green depends on a number nobody
   is defending is a gate that will one day fail for a reason nobody intended.

`--no-cov` was verified to emit no warnings under `filterwarnings = error` (704 passed, 1.44 s).

```makefile
# The fast host loop: no database, no coverage artifact.
# --no-cov, not a threshold override: pytest.ini also writes coverage.xml, and a
# partial run must not overwrite the artifact `make test` and CI produce.
test-unit:
	$(VENV)/bin/pytest -m unit --no-cov
```

### The stray `tests/api/` (D-13)

`tests/api/test_error_contract.py` holds 17 tests driven through `tests/probe.py`'s throwaway
router and `tests/conftest.py`'s `client` / `tolerant_client`. It touches no database (it is
inside the 1.44 s no-DB slice), so it is a unit test in the wrong place.

It also exports two constants imported by **six** integration modules:

```
tests/integration/api/{test_task_lists,test_assignment,test_auth,
                       test_permission_matrix,test_tasks,test_users}.py
  -> from tests.api.test_error_contract import MEMBERS, PROBLEM_JSON
```

**Recommendation, two steps:**

1. Move `MEMBERS` and `PROBLEM_JSON` into a new non-test module `tests/problem_details.py`
   (importable, never collected, beside `tests/probe.py` which sets that precedent). Update the
   six import sites plus the moved module. A test module importing constants from another *test*
   module is the smell that makes this file look stray in the first place.
2. Move the file to `tests/unit/presentation/test_error_contract.py` and delete `tests/api/`
   (and its `__init__.py`). The root `tests/conftest.py` fixtures it uses are visible from there.
   `tests/unit/presentation/` already holds `test_actor.py`, `test_health.py`, `test_schemas.py`
   and `test_security_scheme.py` — the error handler is presentation, and this is its home.

Note for the planner: `tests/integration/conftest.py`'s `alembic_config` docstring names
`tests/api/test_error_contract.py` by path. Update it in the same commit or the prose goes stale.

## Runtime State Inventory

Not applicable in the usual sense — this phase changes no runtime identifier — but two
non-source artifacts are affected and must be handled:

| Category | Item | Action |
|---|---|---|
| Build artifacts | `coverage.xml` at the repo root, rewritten by every `pytest` | `make test-unit` uses `--no-cov`; the break script uses `--no-cov -p no:cacheprovider`. Verify it is `.gitignore`d |
| Build artifacts | `.pytest_cache/`, `tests/**/__pycache__/` | `-p no:cacheprovider` in the break script so `--lf` state is not poisoned by a deliberately-red run |
| Live service config | None — no external service holds a name this phase changes | Verified: no rename in scope |
| Stored data | None — `taskmanager_test` is rebuilt by `migrated_database` on every session | Verified |
| Secrets / env vars | None changed. `.env` exists and is untracked | Verified |

## Common Pitfalls

### Pitfall 1: taking `scope["route"].path_format` as the published path

**What goes wrong:** the D-03 gate reports all 19 operations as never-requested, or (worse) a
prefix change silently stops being proven.
**Why:** FastAPI 0.141.1 / Starlette 1.6.0 keep included routers as `_IncludedRouter` objects;
the route's own `path_format` is router-local and `root_path` is `""`. Measured, not assumed.
**How to avoid:** resolve via unique-suffix (or regex) match against `app.openapi()`, and assert
the match is unique.

### Pitfall 2: an AST gate that does not resolve assertion helpers

**What goes wrong:** 29 false positives instead of 1 real offender; the gate gets weakened or
deleted.
**Why:** this suite's house style pushes body assertions into `assert_*(response, ...)` helpers,
some of them imported across modules (`anonymised` lives in `test_task_lists.py` and is used in
`test_auth.py`).
**How to avoid:** taint-track `body = response.json()`, and resolve `Response`-annotated helpers
both same-file and via `ImportFrom` within `tests/`.

### Pitfall 3: an auth-failure test that never seeds its subject

**What goes wrong:** six of seven failure modes pass for the unknown-subject reason. Proven: with
expiry verification disabled the whole selection stays green.
**Why:** `AuthenticateActor` performs a confirmation read (D-11 of Phase 5) on every request, and
`authenticated_client` deliberately seeds nobody.
**Warning sign:** an auth test that takes `authenticated_client` and no `session_factory`.

### Pitfall 4: a totality gate that passes vacuously on a partial run

**What goes wrong:** CI skips the totality half and nobody notices.
**How to avoid:** the two-sided rule (§D-03) — the "recorded ⊆ published" half never skips — plus
the knowledge that all three invocation sites run a bare `pytest`.

### Pitfall 5: the break script leaving a mutated tree behind

**What goes wrong:** an interrupted run leaves `src/` modified; the next `make test` is red for a
reason nobody can see.
**How to avoid:** `trap ... EXIT INT TERM` installed before the first mutation, a dirty-tree
refusal at the top, and a post-restore `git status --porcelain -- src/` assertion.

### Pitfall 6: a new gate that fails `mypy --stcrit` / `flake8` rather than its own assertion

`make typecheck` runs `mypy src tests` under `strict = true`, and `.flake8` carries bugbear.
Every new gate module, conftest hook and helper is inside that scope. Annotate the
`pytest_collection_modifyitems` hooks (`config: pytest.Config`, `items: list[pytest.Item]`) and
the ASGI middleware (`Scope`, `Receive`, `Send` from `starlette.types`) explicitly.

## Suggested plan shape (D-15: 3–4 plans)

Offered as input, not as a constraint on the planner.

| Plan | Contents | Why grouped |
|---|---|---|
| **A — Totality gates** | D-02 use-case import-scan gate; D-03 recorder + two-sided endpoint gate + ordering hook; D-04 transition complement, error-leaf gate, auth-mode seeding fix | All four are "plant a gate that is already green", except the one D-14 fix they expose. Doing D-03 first makes the matrix self-defending |
| **B — Assertion sweep + gates** | D-05a rule + gate (1 real offender); D-05b/D-06 sweep of ~29 tests; `no_reread` marker + exemption frozenset + companion test | The largest single body of work; the gate must land in the same plan as the sweep or the gate is red on arrival |
| **C — Break check** | `scripts/break-check.sh`, `make break-check`, its unit test, the `AI_WORKFLOW.md` incident entry including the two survivals | Self-contained; depends on A's auth fix so break 4's "after" can be recorded |
| **D — Coverage pin + tidy + ticks** | D-11 configuration pin test; markers on 704 tests + the unmarked-item guard; `make test-unit`; `tests/problem_details.py` + the move; three-way agreement record; TEST-01..05 ticks; ADR-085.. entries and CLAUDE.md bullets | Mechanical and low-risk; the closing plan takes the requirement ticks |

## Validation Architecture

### Test Framework

| Property | Value |
|---|---|
| Framework | pytest 9.x + pytest-asyncio (`asyncio_mode = auto`) + pytest-cov |
| Config file | `pytest.ini` (authoritative; `[tool.pytest.ini_options]` in `pyproject.toml` would be ignored) |
| Quick run command | `.venv/bin/pytest -m unit --no-cov` (704 tests, 1.4 s, no database) |
| Full suite command | `.venv/bin/pytest` (1019 tests, 9.6 s, requires `make up`) |

### Phase Requirements → Test Map

| Req | Behaviour | Type | Automated command | Exists? |
|---|---|---|---|---|
| TEST-01 | Every use-case symbol has a fakes-based unit test | unit | `pytest tests/architecture/test_use_case_totality.py -x --no-cov` | ❌ new |
| TEST-02 | Every published operation was requested over HTTP | integration | `pytest tests/integration -x` (gate item runs last) | ❌ new |
| TEST-03 | Coverage configuration is pinned and the gate passes | unit + full | `pytest tests/architecture/test_coverage_configuration.py --no-cov` and `pytest` | ❌ new / ✅ gate |
| TEST-04 | Transition complement, auth modes, error leaves, matrix | unit + integration | `pytest tests/unit/domain/test_task_status.py tests/integration/api/test_tasks.py tests/integration/api/test_auth.py tests/integration/api/test_permission_matrix.py` | ⚠️ partial — see §D-04 gaps |
| TEST-05 | Assertion-quality gates; break check red on all five | unit + script | `pytest tests/architecture/test_assertion_quality.py --no-cov` ; `make break-check` | ❌ new |

### Sampling Rate

- **Per task commit:** `.venv/bin/pytest -m unit --no-cov` (1.4 s)
- **Per wave merge:** `.venv/bin/pytest` (9.6 s, full suite + coverage gate)
- **Phase gate:** `make lint && make typecheck && make arch && make test` green, plus
  `make docker-test` and CI agreeing on the coverage total, plus `make break-check` green

### Wave 0 Gaps

- [ ] `tests/architecture/test_use_case_totality.py` — TEST-01
- [ ] `tests/architecture/test_assertion_quality.py` — TEST-05
- [ ] `tests/architecture/test_coverage_configuration.py` — TEST-03
- [ ] `tests/integration/test_endpoint_totality.py` + recorder in `tests/integration/conftest.py` — TEST-02
- [ ] `tests/problem_details.py` — shared `MEMBERS` / `PROBLEM_JSON`, six import sites
- [ ] `scripts/break-check.sh` + `tests/unit/test_break_check.py` — TEST-05
- [ ] Framework install: none — the stack is complete and no dependency is added

## Security Domain

Applicable, and this phase touches it directly through two of the five breaks.

| ASVS Category | Applies | Standard control in this repo |
|---|---|---|
| V2 Authentication | yes | PyJWT HS256, `pwdlib[argon2]`; **finding:** the HTTP-level failure-mode suite is vacuous for six of seven modes (§D-04) and must be fixed in this phase |
| V3 Session Management | yes | Stateless bearer tokens, `exp` required and verified with zero leeway (`tokens.py:48,118`); break 4 proves the unit tests defend it |
| V4 Access Control | yes | `application/use_cases/access.py` — the 404/403 decision; break 3 turns 33 tests red, so it is well defended |
| V5 Input Validation | yes | Pydantic v2 at the boundary (`extra="forbid"`), domain `ValidationError` inside |
| V6 Cryptography | yes | PyJWT + argon2 only; nothing hand-rolled |

| Threat pattern | STRIDE | Mitigation / state |
|---|---|---|
| Expired-token replay | Spoofing | `verify_exp` on by default, zero leeway. **Only unit-tested end to end today** — fix per §D-04 |
| IDOR / horizontal privilege escalation | Elevation of privilege | 76-cell permission matrix; break 3 confirms it bites |
| Lost update on concurrent writes | Tampering | `for_update=True` on write paths. **List deletion is pinned only against fakes** (break 5) |
| Credential echo in an error body | Information disclosure | `test_a_refusal_never_echoes_the_clients_input`, and the per-case `credential not in response.text` assertion |

## Environment Availability

| Dependency | Required by | Available | Version | Fallback |
|---|---|---|---|---|
| Python venv | host test loop | ✓ | 3.14.3 at `.venv/bin/python` | Docker `test` stage |
| PostgreSQL | integration suite | ✓ | `postgres:18-alpine`, `db` container running | `make up` |
| Docker | `make docker-test`, three-way agreement | ✓ | daemon reachable | none needed |
| `git` | break script restore | ✓ | clean tree at `cfa6f8d` | none — the script requires it |
| pytest / pytest-cov / pytest-asyncio | everything | ✓ | installed, suite green | — |
| **New packages** | — | n/a | **none added** (mutmut declined, D-08) | — |

No missing dependency. No package is installed by this phase, so the Package Legitimacy Audit is
not applicable.

## Assumptions Log

| # | Claim | Section | Risk if wrong |
|---|---|---|---|
| A1 | `pytest_collection_modifyitems` reordering is stable enough to guarantee the totality item runs last | D-03 | Gate reports a false negative for `/health` and the last-collected routes. Mitigation: the "recorded ⊆ published" half still holds, and a companion assertion can pin the item's index |
| A2 | Unique-suffix resolution of router-local templates stays unambiguous as the API grows | D-03 | A future overlapping tail. Mitigated by asserting uniqueness inside the resolver |
| A3 | `config.option.{keyword,markexpr,deselect,last_failed,...}` is the complete set of selection flags to detect | D-03 | A selection mechanism not covered produces a false red on a focused run. Low impact, easy to extend |
| A4 | The ~29-test sweep is mechanical (add a GET and a body assertion) | D-05/06 | Plan sizing. Sampled four of them by hand; all were two-line additions |
| A5 | A fifth concurrency case for list deletion is in scope under D-14 rather than a Deferred Idea | D-08 break 5 | Planner's call; the finding itself is measured and must be reported either way |

## Open Questions

1. **Does the self-transition leg belong in D-04's "complement"?**
   - Known: `(pending,pending)`, `(in_progress,in_progress)`, `(completed,completed)` are outside
     `ALLOWED_TRANSITIONS` but are deliberately **200 no-ops**, tested at `test_task.py:148-168`.
   - Unclear: D-04 says "every status pair minus the allowed ones", which would assert a refusal
     for them and be wrong.
   - Recommendation: parametrize over the complement but branch on `a is b` — self-pairs assert
     the no-op, cross-pairs assert the 409. State it in the test docstring so the split reads as
     a decision, not an oversight.

2. **Fix break 5's blind spot, or defer it?**
   - Known: dropping the lock on `DeleteTaskList` reddens exactly one fakes-based test;
     `test_concurrent_writes.py` has no list-deletion case.
   - Recommendation: the finding is mandatory to report (D-10). Adding a fifth case is ~40 lines
     following `test_two_list_patches_are_serialised_and_neither_edit_is_lost`. Worth it —
     ADR-058's deadlock-ordering argument is otherwise unproven on the delete path.

3. **Does `tests/probe.py` need the `unit` marker treatment?**
   - It is not collected (no `test_` prefix), so it needs no marker; but the unmarked-item guard
     must not mistake it for one. Verified it is not in any collection count.

## Sources

### Primary (HIGH confidence — measured in this session)

- Full suite run: `.venv/bin/pytest` → 1019 passed, 100 %, 9.57 s
- Five break runs, each followed by `git checkout -- src/` and a clean `git status --porcelain`
- AST prototypes over `tests/integration/api/` (three refinement passes: 29 → 10 → 6 offenders)
- ASGI recorder prototype against `create_app(...)`, printing `scope["route"].path_format`,
  `scope["root_path"]` and `app.routes` types
- `app.openapi()` enumeration → 19 operations
- Marker and coverage selections: `-m unit`, `-m integration`, `-m "not integration"`, `--no-cov`
- Repository files read in full: `pytest.ini`, `pyproject.toml`, `Makefile`,
  `.github/workflows/ci.yml`, `docker-compose.yml` (test service), `Dockerfile` (test stage),
  `.pre-commit-config.yaml`, `tests/conftest.py`, `tests/integration/conftest.py`,
  `tests/architecture/test_routers_raise_no_http_exception.py`,
  `tests/unit/presentation/test_security_scheme.py`,
  `tests/integration/api/test_permission_matrix.py`, `tests/integration/api/test_auth.py`,
  `src/taskmanager/domain/value_objects/{completion,task_status}.py`,
  `src/taskmanager/domain/exceptions.py`,
  `src/taskmanager/application/use_cases/access.py`,
  `src/taskmanager/infrastructure/security/tokens.py`,
  `src/taskmanager/presentation/api/errors/mapping.py`, `scripts/init-env.sh`
- Installed versions reported by the interpreter: FastAPI 0.141.1, Starlette 1.6.0

### Secondary (MEDIUM confidence)

- `CLAUDE.md` §"Project Rules", `.planning/REQUIREMENTS.md` TEST-01..05,
  `.planning/phases/06-test-hardening-coverage/06-CONTEXT.md` — the constraints above
- `DECISION_LOG.md` — ADR-084 is the last entry; ADR-085 is next free

### Tertiary (LOW confidence)

- None. No claim in this document rests on training data or on an unverified web source.

## Metadata

**Confidence breakdown:**
- Offender counts and break outcomes: **HIGH** — executed, not estimated
- `_IncludedRouter` / `path_format` behaviour: **HIGH** — printed from the running application
- Gate designs (D-02 scan, D-03 resolver, D-05 rules, D-11 pin): **MEDIUM-HIGH** — prototyped in
  part, not yet written as passing pytest modules under `mypy --strict`
- Sweep sizing (~29 edits): **MEDIUM** — four samples inspected by hand out of 39
- Plan shape: **MEDIUM** — a suggestion, and the planner's call

**Research date:** 2026-09-19
**Valid until:** 2026-10-19 (30 days — the stack is pinned and no dependency changes; the
measured counts are valid only against tree `cfa6f8d`, and any test added before planning
invalidates the offender numbers, not the method)
