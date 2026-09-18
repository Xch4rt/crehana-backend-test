---
phase: 02-domain-error-contract
plan: 04
subsystem: presentation
tags: [python, fastapi, starlette, rfc9457, problem-json, httpx, pytest, mypy]

# Dependency graph
requires:
  - phase: 01-foundation-quality-gates
    provides: create_app() factory with no module-level app, Settings, pytest/mypy/flake8/black/isort gates, import-linter contracts, coverage gate
  - plan: 02-01
    provides: TaskStatus, whose .value the probe route and the 409 body assert on
  - plan: 02-02
    provides: DomainError with code/title/message/details - the exact contract the handler reads
provides:
  - problem(), the only function in the codebase that builds an error body
  - STATUS_BY_EXCEPTION plus status_for(), the only class-to-HTTP-status mapping
  - four handlers and register_exception_handlers(), called by create_app()
  - tests/probe.py and the app/client/tolerant_client fixtures every later API test will reuse
  - 16 new tests pinning D-05 through D-10, presentation and main.py at 100% coverage
affects: [02-05-ports, 03-persistence, 04-crud-endpoints, 05-auth]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Handlers take the base Exception type and narrow with an isinstance assertion - the only signature mypy strict accepts, and the only one that adds no uncoverable branch"
    - "One keyword-only problem() builder; no handler ever assembles a body dict"
    - "The class-to-status table is resolved by MRO walk with next((...), default), mirroring how Starlette resolves the handler itself"
    - "API fixtures live in tests/conftest.py; the tolerant client exists for exactly one test and says so in its docstring"
    - "The probe router lives under tests/, so it is outside coverage, outside import-linter's graph and unreachable from the production app"

key-files:
  created:
    - src/taskmanager/presentation/api/__init__.py
    - src/taskmanager/presentation/api/errors/__init__.py
    - src/taskmanager/presentation/api/errors/problem.py
    - src/taskmanager/presentation/api/errors/mapping.py
    - src/taskmanager/presentation/api/errors/handlers.py
    - tests/api/__init__.py
    - tests/api/test_error_contract.py
    - tests/probe.py
    - tests/conftest.py
    - .planning/phases/02-domain-error-contract/evidence/02-04-tdd-red.txt
  modified:
    - src/taskmanager/main.py
    - tests/unit/test_app_factory.py

key-decisions:
  - "STATUS_BY_EXCEPTION uses plain int literals, not HTTPStatus members: 422's member name changed between Python versions and an int sidesteps the question"
  - "The five leaf errors are deliberately absent from the table and resolve through their parent by MRO; a comment says so, or the omission reads as a bug"
  - "The three docstring paragraphs that explain the forbidden handler shapes describe them instead of spelling them, because the plan's own grep gates count those tokens"
  - "ARC-07 is ticked in REQUIREMENTS.md: unlike ARC-02 and ARC-06, plan 02-04 is its only claimant in the whole phase"

patterns-established:
  - "An error body is built in exactly one place; a new handler calls problem() or it is wrong"
  - "A test-only FastAPI router is packaged under tests/ and included by a fixture, never by create_app()"
  - "A verification command that passes is still checked for what it actually measured - the two-flag coverage --include form silently measured one file"

requirements-completed: [ARC-07]

# Metrics
duration: 18min
completed: 2026-09-18
---

# Phase 2 Plan 04: The Single RFC 9457 Exception-Handling Point Summary

**One `problem()` builder, one class-keyed status table resolved by MRO walk, and four handlers registered by `create_app()` turn every `DomainError`, every request-validation failure, every Starlette `HTTPException` and every unplanned exception into the same `application/problem+json` body - proven end to end by 14 contract tests against a throwaway probe router that the production app cannot even import, with `presentation/` and `main.py` at 100% statement and branch coverage before the first real route exists.**

## Performance

- **Duration:** 18 min
- **Started:** 2026-09-18T06:39:01Z
- **Completed:** 2026-09-18T06:56:41Z
- **Tasks:** 3
- **Files modified:** 10 created, 2 modified

## Accomplishments

- **ARC-07 is satisfied and demonstrable.** `register_exception_handlers(app)` is called by `create_app()` and is the only place in the repository that produces an error body. `test_create_app_registers_exception_handlers` asserts all four registrations **by identity**, which is what proves our `HTTPException` and `RequestValidationError` handlers replaced FastAPI's own defaults rather than sitting beside them.
- **D-05 and D-06 are mechanically checked, not asserted in prose.** `list(response.json()) == ["type", "title", "status", "detail", "instance", "code", "errors"]` is an exact comparison on the 409 body, and `response.headers["content-type"] == "application/problem+json"` is an equality rather than a `startswith`, so a `; charset=utf-8` suffix would fail the suite. `type` is the URN `urn:taskmanager:problem:{code}` for every code.
- **The MRO claim is tested, not assumed (D-10).** `InvalidStatusTransitionError` is a *grandchild* of `DomainError`; the test asserts its two ancestors, asserts that neither it nor its parent appears in `app.exception_handlers`, and then asserts the 409 problem body comes back anyway. The same walk drives `status_for`, so `TaskNotFoundError` - which has no entry of its own - resolves to 404 through `NotFoundError`.
- **The 422 is a translation, not a pass-through (D-07, threat T-02-02).** One request with a bad query value *and* a bad body yields exactly `{"query.q", "body.title", "body.count"}` as dotted fields, every entry carrying exactly `field`, `message`, `type`. A named test asserts the submitted values (`nope`, `abc`) and the substrings `input`, `ctx` and `url` are all absent from `response.text`.
- **The 500 leaks nothing and logs everything (D-08, threats T-02-01, T-02-24).** The body is the fixed `internal_error` / "An unexpected error occurred" shape with no `errors` member; `hunter2`, `secret internals`, `Traceback` and `RuntimeError` are each asserted absent from the response text, while a `caplog` test asserts exactly one `ERROR` record from the handler's own logger carrying `exc_info` whose exception still contains the canary. `create_app()` passes no `debug=`, so Starlette's HTML traceback page can never render.
- **The header traps are closed before Phase 5 can hit them (D-09, threat T-02-03).** `GET /_probe/http-error` keeps `www-authenticate: Bearer` and `POST /_probe/domain` keeps `Allow`, both through the translated response. An unknown route answers 404 problem+json rather than a bare `{"detail": "Not Found"}`, and a fourteenth test walks seven different failures asserting the media type and the member prefix on every one.
- **The probe cannot reach production (D-10, threat T-02-05).** It lives in `tests/probe.py`, every route is declared `include_in_schema=False`, only the `app` fixture includes it, and `test_production_app_has_no_probe_routes` asserts a freshly built app carries no `/_probe` path.
- **100% statement and branch coverage over `presentation/` and `main.py`** (50 statements, 4 branches, 0 missed) with no `pragma: no cover` and no coverage `omit`. Whole suite: 116 passed, 100% total, zero warnings under `filterwarnings = error`.
- **Verified on the target runtime.** `make docker-test` (CPython 3.13) reports 116 passed and the same 100% for all three error modules, so nothing here depends on the host's 3.14.3.
- **The three layer contracts stay KEPT.** `presentation` imports `domain` and nothing else new; `handlers.py` imports nothing from `infrastructure`, which is also what keeps D-08's "no branch on the environment" structurally true rather than merely observed.

## Task Commits

Each task was committed atomically:

1. **Task 1: the problem+json body builder and the class-to-status table** - `3efd2a6` (feat)
2. **Task 2: the four handlers and the create_app() wiring** - `a6bac6c` (feat)
3. **Task 3: the probe router and the end-to-end contract suite** - `e831039` (test)

**Plan metadata:** see the `docs(02-04)` commit that carries this SUMMARY.

## Files Created/Modified

- `src/taskmanager/presentation/api/errors/problem.py` (55 lines) - `PROBLEM_JSON` and the keyword-only `problem()`; the comment explains that dict insertion order plus `json.dumps` is what makes D-06's ordering claim mechanical
- `src/taskmanager/presentation/api/errors/mapping.py` (74 lines) - `STATUS_BY_EXCEPTION` (eight entries) and `status_for()`; the header comment names the module's exclusive responsibility and records why the five leaves are absent
- `src/taskmanager/presentation/api/errors/handlers.py` (145 lines) - the four handlers and `register_exception_handlers()`, with a three-paragraph docstring on the variance rule, the imperative registration and the Starlette-vs-FastAPI exception class
- `src/taskmanager/presentation/api/__init__.py`, `.../errors/__init__.py`, `tests/api/__init__.py` - empty package markers, 0 bytes each
- `tests/probe.py` (86 lines) - `probe_router` with six routes, the fixed `PROBE_TASK_ID`, the `hunter2` canary and the comment saying why raising the framework's HTTP exception is legal in a test double
- `tests/conftest.py` (63 lines) - `app`, `client` and `tolerant_client`, with the env injection RESEARCH's snippet elided
- `tests/api/test_error_contract.py` (252 lines) - the 14 contract tests
- `src/taskmanager/main.py` (+4 lines) - the `FastAPI(...)` construction is bound to a local, the handlers are registered, the app is returned; no module-level instance, no `debug=`
- `tests/unit/test_app_factory.py` (+35 lines) - the two new tests
- `.planning/phases/02-domain-error-contract/evidence/02-04-tdd-red.txt` - the three RED captures, their GREEN counterparts, the full host gate and the Docker run

## Selector Proof (02-VALIDATION.md rows)

| Selector | Tests selected | Result |
|----------|----------------|--------|
| `-k domain` (tests/api) | 2 | passed |
| `-k validation` (tests/api) | 2 | passed |
| `-k unexpected` (tests/api) | 4 | passed |
| `-k http` (tests/api) | 3 | passed |
| `-k forbidden` (tests/api) | 1 | passed |
| `-k handlers` (test_app_factory) | 1 | passed |
| `-k probe` (test_app_factory) | 1 | passed |

## Decisions Made

- **Plain integers in the status table, not `HTTPStatus` members.** 422's member name differs across Python versions (the entity/content spelling changed), and the table is more readable as literals anyway. A comment records the reason so the choice does not read as sloppiness.
- **The five leaf errors are absent from the table on purpose.** `TaskNotFoundError` and its four siblings resolve through `NotFoundError` and `ConflictError` by the MRO walk. Listing them would be four future opportunities to disagree with their parent; the comment says so explicitly, because an unexplained omission in a lookup table reads as a bug.
- **Docstrings describe the forbidden shapes instead of spelling them** (see Deviations). This is now the fourth occurrence of the same collision in this project, so it is an established convention rather than an incident.
- **The plan's coverage command was checked for what it actually measures.** Passing two `--include` flags makes coverage.py keep only the last one, so that invocation proves only `main.py`. It exits 0 either way; the comma-separated single-flag form was run as well and is the number quoted above. Both captures are in the evidence file.
- **`problem()` is keyword-only.** Five of its six parameters are strings; a positional call site would be one transposition away from serving the title as the detail with no test noticing.
- **Probe routes are annotated `-> dict[str, str]` even though five of them always raise.** `NoReturn` would make FastAPI build a response field from a type that has no schema; the concrete annotation keeps mypy strict, `warn_unreachable` and the route decorator all satisfied at once.
- **ARC-07 is ticked in `REQUIREMENTS.md`.** Unlike ARC-02 and ARC-06, which several plans in this phase contribute to, ARC-07 has exactly one claimant across the whole phase (checked against every `requirements:` line in `02-0*-PLAN.md`), and every clause of it is now implemented and asserted.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Three docstring phrases in `handlers.py` tripped the plan's own grep gates**

- **Found during:** Task 2, at the plan's `<verify>` step
- **Issue:** the plan's action text asks the module docstring to name the rejected alternatives, and its acceptance criteria then *count* those very tokens: `grep -c 'app.add_exception_handler'` must be exactly 4, `grep -c 'exc: Exception'` exactly 4, and `grep -c '@app.exception_handler'` exactly 0. Writing the explanations as dictated produced 5, 5 and 1 - the prose about the forms failed the gates that exist to constrain the forms. (Note also that `grep`'s `.` is a wildcard, so even "app add_exception_handler" would have matched.)
- **Fix:** the three paragraphs now describe each shape without spelling it: "annotates its exception parameter with the bare `Exception` type", "`register_exception_handlers` below calls `add_exception_handler` on the application object it is given", and "the decorator form FastAPI also offers is deliberately absent". Same convention as 01-04's Makefile, 02-02's docstring and 02-03's `validation.py`.
- **Files modified:** `src/taskmanager/presentation/api/errors/handlers.py`
- **Verification:** the three counts are now 4, 4 and 0, and the whole `<verify>` chain exits 0.
- **Committed in:** `a6bac6c` (Task 2 commit)

**2. [Rule 3 - Blocking] The same collision in `tests/conftest.py`**

- **Found during:** Task 3 verification
- **Issue:** the docstring paragraph stating that no asyncio fixture decorator, no asyncio marker and no loop override appear in the file spelled all three tokens, and the plan's criterion is `grep -c 'pytest_asyncio.fixture\|mark.asyncio\|def event_loop' tests/conftest.py` returns 0.
- **Fix:** the paragraph now names them as "the asyncio-specific fixture decorator, the per-test asyncio marker, and a hand-rolled replacement for pytest-asyncio's own loop fixture", and explains that `asyncio_mode = auto` is why none is needed.
- **Files modified:** `tests/conftest.py`
- **Verification:** the grep returns 0; all 14 contract tests still pass.
- **Committed in:** `e831039` (Task 3 commit)

**3. [Rule 3 - Blocking] mypy rejected an intermediate variable for `exc.headers`**

- **Found during:** Task 2, at `make typecheck`
- **Issue:** the header-forwarding loop was written with an explicit `headers: dict[str, Any] = exc.headers or {}` binding for readability. `HTTPException.headers` is typed `Mapping[str, str] | None`, so mypy strict reported `Incompatible types in assignment (expression has type "Mapping[str, str]", variable has type "dict[str, Any]")` - a `Mapping` is not a `dict`.
- **Fix:** reverted to RESEARCH's verified inline form, `for key, value in (exc.headers or {}).items():`, which needs no annotation at all. The unused `typing.Any` import was removed with it.
- **Files modified:** `src/taskmanager/presentation/api/errors/handlers.py`
- **Verification:** `.venv/bin/mypy src tests` exits 0; both header-preservation tests pass.
- **Committed in:** `a6bac6c` (Task 2 commit)

---

**Total deviations:** 3 auto-fixed (3 blocking, 0 bugs)
**Impact on plan:** No scope change, no interface change. Every signature in the plan's `<interfaces>` block shipped exactly as written, so plans 02-05, Phase 4 and Phase 5 are unaffected.

## Issues Encountered

- **The plan's presentation-coverage command is weaker than it looks.** `coverage report --include=A --include=B` keeps only `B`, so the documented invocation measured `main.py` alone (8 statements) and would have exited 0 even with `handlers.py` uncovered. The comma-separated form was run as well - 50 statements, 4 branches, 0 missed - and both outputs are in the evidence file. Worth fixing in 02-VALIDATION.md rather than rediscovering in Phase 4.
- **TDD gate commits still not separable** - the same wall plans 02-01, 02-02 and 02-03 hit. See TDD Gate Compliance below.
- Nothing else. All three tasks passed their full `<verify>` chain, on the host (CPython 3.14.3) and in Docker (CPython 3.13), with zero warnings.

## Known Stubs

None. Every symbol this plan created is fully implemented and exercised at 100% statement and branch coverage. `tests/probe.py` is a deliberate test double rather than a stub: it is not shipped, not imported by `src/`, not measured by coverage, and a named test asserts it cannot reach the production app.

## TDD Gate Compliance

All three tasks are `tdd="true"` and the cycle was executed in order. The gate commits remain **not** separable in this repository - the convention plan 02-01 established applies unchanged, because the `mypy (strict)` pre-commit hook rejects a test (or a probe script) importing a module that does not exist and `--no-verify` is forbidden by CLAUDE.md:

- **RED:** Task 1's behaviour script was run against a tree with no `presentation.api` package (`ModuleNotFoundError: No module named 'taskmanager.presentation.api'`). Task 2's two app-factory tests were written first and run against a tree with no `handlers.py` (collection `ImportError`). Task 3's 14 contract tests were written first and run against a tree with no `tests/probe.py` and no fixtures (collection `ImportError`). All three failures, and the GREEN run of the identical command, are captured verbatim in `evidence/02-04-tdd-red.txt`.
- **GREEN:** `3efd2a6` (the builder and the table), `a6bac6c` (the handlers, the wiring and the two app-factory tests), `e831039` (the probe router, the fixtures and the contract suite).
- **REFACTOR:** not needed. The three fixes above all happened before green was reached, not after it.

One honest caveat recorded in the evidence file as well: the handler bodies the Task 3 suite exercises were written in Task 2, so those 14 tests passed on their first run. Their RED is genuine for the fixtures and the probe router - the subjects Task 3 actually creates - and the suite is a specification of the handlers rather than a driver of them. The plan ordered the tasks that way; the ordering is reported rather than disguised.

## Threat Flags

None. The plan's register is fully implemented and asserted: T-02-01 (fixed 500 body, three leak assertions), T-02-02 (only `loc`/`msg`/`type` survive, echo test), T-02-03 (`exc.headers` forwarded, two header tests), T-02-04 (`errors=exc.details or None` passes only the statically constrained `Details` dict from 02-02), T-02-05 (probe outside `src/`, `include_in_schema=False`, production-app test), T-02-06 (Starlette's own 404/405 translated; media type asserted on seven different failures), T-02-24 (no `debug=`, grep-gated). T-02-09 stays `accept` and is now documented in the module docstring: the `isinstance` assertions are load-bearing, and no `-O` or `PYTHONOPTIMIZE` appears in the `Dockerfile`, the `Makefile` or `ci.yml`. T-02-SC stays not-applicable - nothing was installed.

This plan does introduce the app's first error-response surface, but it introduces no route, no auth path, no file access and no schema; the six probe routes exist only inside a test fixture.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 02-05 (ports and the reference use case) is unblocked and untouched by this plan: nothing here imports `application`, and the layer contracts stay KEPT.
- Phase 4's routers inherit a finished contract: raise a `DomainError` subclass and the response shape, status, URN and `errors` member follow automatically. No endpoint should ever build an error body, and CLAUDE.md already forbids it.
- Phase 4 and Phase 5 also inherit the fixtures: `app`, `client` and `tolerant_client` are in `tests/conftest.py` and ready for real routers. `tolerant_client` is for the 500 case only - its docstring says why, and `test_unexpected_error_still_reaches_an_intolerant_client` fails loudly if anyone makes the shared client tolerant.
- Phase 5's auth dependency can raise the framework's 401 with `WWW-Authenticate` and the header will survive translation; that is asserted today rather than discovered later.
- A new `DomainError` subclass added in a later phase needs a `STATUS_BY_EXCEPTION` entry **only** if its status differs from its parent's - 02-02's `test_hierarchy_is_closed` is what will force the question.
- No blockers.

## Self-Check: PASSED

All ten created files and both modified files exist on disk, and all three task commits (`3efd2a6`, `a6bac6c`, `e831039`) are present in `git log`.

---
*Phase: 02-domain-error-contract*
*Completed: 2026-09-18*
