---
phase: 03-persistence-runnable-stack
plan: 09
subsystem: presentation
tags: [health, dependencies, lifespan, composition-root, version, dock-03, arc-08, db-01, d-06, d-08]

# Dependency graph
requires:
  - phase: 02-domain-error-contract
    provides: the UnitOfWork Protocol get_uow yields, and register_exception_handlers as the registration convention create_app follows
  - phase: 03-persistence-runnable-stack
    plan: 03
    provides: Settings and the resolved DSN the engine is built from
  - phase: 03-persistence-runnable-stack
    plan: 05
    provides: the database_url / _require_database / migrated_database fixtures the integration suite takes
  - phase: 03-persistence-runnable-stack
    plan: 08
    provides: create_database_resources, DatabaseResources and SqlAlchemyUnitOfWork - the engine built but never owned, and the boundary never handed out
provides:
  - src/taskmanager/__init__.py::__version__ - the one runtime version string, bound to pyproject.toml by a test
  - src/taskmanager/presentation/api/dependencies.py - get_engine, get_session_factory, get_uow, and the single narrowing of app.state
  - src/taskmanager/presentation/api/health.py - GET /health, the D-08 status document, and EngineDependency as the reusable annotated form
  - src/taskmanager/main.py - the wired composition root: DatabaseResources on app.state, the engine disposed in the lifespan, the health router registered
  - The proof that a yield dependency's teardown keeps nothing, read back from a second connection
affects: [03-10, 03-11, 04-crud-endpoints, 05-auth]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A dependency is injected as `Annotated[T, Depends(f)]`, never as an argument default: flake8-bugbear's B008 whitelist matches the dotted spelling the project never uses, and the annotated alias gives Phase 4 a name to reuse"
    - "The lifespan is a closure over the value create_app just built, not a read of app.state: the composition root has no reason to give up the type of an object it constructed one line earlier"
    - "A provider is tested through a throwaway router that takes it, never through an override - an override replaces the code under test"
    - "Engine disposal is observable without a server: dispose() replaces the pool, so object identity before and after is the assertion"

key-files:
  created:
    - src/taskmanager/presentation/api/dependencies.py
    - src/taskmanager/presentation/api/health.py
    - tests/unit/test_version.py
    - tests/unit/presentation/__init__.py
    - tests/unit/presentation/test_health.py
    - tests/integration/test_health.py
    - tests/integration/test_dependencies.py
    - .planning/phases/03-persistence-runnable-stack/evidence/03-09-teardown-falsification.txt
  modified:
    - src/taskmanager/__init__.py
    - src/taskmanager/main.py
    - tests/unit/test_app_factory.py

key-decisions:
  - "__version__ lives in src/taskmanager/__init__.py, the only non-empty package init in the project, and the docstring says why the exception exists and why importlib.metadata was rejected - it raises PackageNotFoundError in exactly the environment pytest.ini's pythonpath=src creates"
  - "The injection uses Annotated[AsyncEngine, Depends(get_engine)] because B008 fired on the plan's literal default-argument form: .flake8's extend-immutable-calls whitelists `fastapi.Depends`, and this project imports by name"
  - "The lifespan closes over the resources create_app built rather than reading app.state.database, so the disposal path is fully typed with no narrowing outside dependencies.py"
  - "dependencies.py and health.py describe the forbidden shapes in prose and never spell them, keeping the plan's four grep gates real - the phase's prose-not-literal convention, applied for the tenth time"
  - "get_uow is proven by a throwaway router in tests/integration/test_dependencies.py, not by an override, and the no-durable-write claim was falsified: adding one line to the teardown turns the test red (evidence on disk)"
  - "No requirement tick taken: 03-11 is the last claimant of DOCK-03, ARC-08 and DB-01. Ninth consecutive plan in this phase to make the same call"

patterns-established:
  - "presentation/api/dependencies.py is now the composition root's request-scoped half: Phase 4 adds providers there and none of them repeats the app.state narrowing"

requirements-completed: []

# Metrics
duration: 16min
completed: 2026-09-18
---

# Phase 3 Plan 09: The Wired Stack and `GET /health` Summary

**The application finally holds the database it was configured with: `create_app()` builds `DatabaseResources`, hands them to the first three `Depends` providers in the project, disposes the engine in the lifespan, and serves `GET /health` — 200 with `"database": "ok"` against the real container, 503 with the same three members when nothing answers, and no trace of the driver's refusal either way. `get_uow` yields the transaction boundary and keeps nothing on teardown, proved by a second connection and falsified by a one-line break.**

## Performance

- **Duration:** 16 min
- **Started:** 2026-09-19T00:41Z
- **Completed:** 2026-09-19T00:58Z
- **Tasks:** 3
- **Files modified:** 8 created, 3 modified

## Accomplishments

- **The PATTERNS.md open gap is closed with one literal, not four.** `src/taskmanager/__init__.py` declares `__version__` and is now the single deliberate exception to the project's empty-`__init__` convention — the docstring says so, and says why. `main.py` reads it, `/health` reads it, `tests/unit/test_app_factory.py` asserts against it, and `tests/unit/test_version.py` reads `pyproject.toml` with `tomllib` so the packaging copy can never drift silently. `grep -rn '0\.1\.0' src tests` now matches exactly one source line. The rejected alternative is recorded in the docstring rather than in a review comment: `importlib.metadata.version("taskmanager")` would leave one literal instead of two and would raise `PackageNotFoundError` in exactly the environment `pytest.ini`'s `pythonpath = src` creates.
- **`GET /health` answers the D-08 document on both legs, and the two are asserted to be the same document.** `test_the_healthy_and_unhealthy_bodies_have_the_same_shape` builds two applications differing only in their DSN, collects both bodies in one test, and compares their member lists and their `checks` keys. D-08's "the same body shape" stops being a sentence in a context file; a future change that gave the failing leg a reason or a retry hint fails there.
- **The failing leg leaks nothing, and that is a test rather than a claim.** `_database_is_reachable` returns a `bool`: the exception is caught and discarded, never formatted, never logged. `test_the_unavailable_body_leaks_no_driver_detail` greps the response text for five distinct disclosures a naive implementation makes — the driver name, a traceback, the password, the host and the database name — and asserts the list of hits is empty (T-3-26).
- **The 503 is a status assignment on the injected `Response`, not an exception and not a hand-built body.** The route keeps its declared response model, so both statuses appear in `/openapi.json` with a schema (`test_health_appears_in_the_openapi_document` asserts the response keys are exactly `{"200", "503"}`), which is what DOC-04 will need. `grep -c` prints `0` for the framework's HTTP exception, for the RFC 9457 builder and for a raw JSON response object in that module.
- **The probe is bounded at 2 s (D-08), and the comment says why that matters more than it looks.** An unreachable host refuses in milliseconds; a *hung* one holds the request open until something upstream gives up, and a healthcheck that hangs reports nothing while consuming a connection slot per attempt (T-3-28).
- **The composition root now owns the engine's whole lifetime.** `create_app()` builds `DatabaseResources`, stores it as `app.state.database`, and disposes the engine in the lifespan's shutdown half — closing over the value it just built rather than reading it back untyped. The module docstring gained the D-06 paragraph: no migration and no statement runs here, `docker/entrypoint.sh` owns `alembic upgrade head`, and the two consequences (unit tests build the real app with no server; replicas cannot race) are stated rather than implied.
- **Disposal is asserted, not assumed.** `dispose()` replaces the engine's pool with a fresh one, so `test_the_lifespan_disposes_the_engine` captures the pool object before and after entering the lifespan and asserts identity changed — and asserts it has *not* changed inside the block, which is the empty-startup half of D-06 (T-3-25). A connection-count assertion would have passed vacuously against an engine that never connected.
- **`dependencies.py` narrows `app.state` exactly once.** `grep -c "cast("` prints `1`, in a private helper with no second call site by construction. The module docstring names the rejected alternative — two bare `app.state` attributes read at each site — and the concrete cost: a narrowing is an assertion the type checker accepts without verifying, so the fewer there are, the more each one is worth. Phase 4's providers inherit the container already typed.
- **`get_uow` yields the port and finishes nothing, and the claim was falsified.** The provider enters the block and yields; `grep -c "commit"` over the module prints `0`. `tests/integration/test_dependencies.py` registers a throwaway router — `tests/probe.py`'s technique — whose handler writes a user and returns without asking for durability, and the test reads the `users` table back from a second, independent engine after the response has come home. Adding `await unit.commit()` to the teardown turns that test red with `assert 1 == 0`; the red and the green run are in `evidence/03-09-teardown-falsification.txt` (ARC-08, research Anti-Pattern 1).
- **All four gates green before all three commits.** `make lint && make typecheck && make arch && make test`: 99 files black/isort clean, flake8 clean, mypy strict clean over 99 source files with still **no `type: ignore` anywhere in the project**, three import-linter contracts KEPT, **287 passed** under `filterwarnings = error`. **Coverage over `src/taskmanager` is back to 100.00%** — 730 statements, 0 missed, 74 branches, 0 partial — gate still at 75, no `pragma`, no `omit`. `make test` twice in a row reports 287 both times, and `SELECT count(*) FROM users` on the test database prints `0` afterwards. `docker build --target test` plus `docker run ... pytest tests/unit/test_version.py` passes inside the image, confirming `pyproject.toml` is readable at `/app/pyproject.toml`.

## Task Commits

Each task was committed atomically:

1. **Task 1: one runtime source for the application version** — `4299993` (feat)
2. **Task 2: the dependencies, the /health route and the wired composition root** — `b56e5d6` (feat)
3. **Task 3: the /health and get_uow proofs against real PostgreSQL** — `f81cc8e` (test)

**Plan metadata:** see the `docs(03-09)` commit that carries this SUMMARY.

## Files Created/Modified

- `src/taskmanager/__init__.py` (25 lines) — `__version__` and the docstring that justifies the project's only non-empty package init
- `src/taskmanager/main.py` (65 lines, +40) — resources built and stored, the lifespan closure, the health registration, and the D-06 paragraph
- `src/taskmanager/presentation/api/dependencies.py` (69 lines) — three providers and the one narrowing
- `src/taskmanager/presentation/api/health.py` (119 lines) — the router, the response model, the bounded probe, `EngineDependency` and `register_health_routes`
- `tests/unit/test_version.py` (48 lines) — 2 tests: the parity gate and the OpenAPI reading
- `tests/unit/presentation/test_health.py` (152 lines) — 6 tests, none of which needs a database
- `tests/integration/test_health.py` (129 lines) — 3 tests against the running container
- `tests/integration/test_dependencies.py` (202 lines) — 4 tests, two throwaway routes, and the second-connection reader
- `tests/unit/test_app_factory.py` (+1/−1) — the literal replaced by the constant
- `.planning/phases/03-persistence-runnable-stack/evidence/03-09-teardown-falsification.txt` (51 lines) — the red/green pair for the no-durable-teardown claim

## Decisions Made

- **`__version__` is a module constant, not distribution metadata.** Two copies remain — the runtime one here and the packaging one in `pyproject.toml` — because a build backend cannot import the package it is about to build. The parity test is what makes two copies acceptable, and it is written in the same spirit as `test_env_example_documents_every_field`: two artifacts that must agree, one assertion, drift becomes a red run. `src/taskmanager/__init__.py` is now the only non-empty `__init__.py` in the project, and it says so in its first paragraph, because an unexplained exception to a stated convention reads as an oversight.
- **The dependency is injected as an annotation, not as an argument default.** PATTERNS.md predicted B008 would not fire because `.flake8` whitelists `fastapi.Depends`; flake8-bugbear matches the call name *as written*, and this project imports by name everywhere, so `Depends(get_engine)` in a default was rejected. The two ways out were adding a bare `Depends` to the whitelist, which loosens a linter rule for the whole repository, and `Annotated[AsyncEngine, Depends(get_engine)]`, which needs no configuration change at all, is the shape FastAPI's own documentation now leads with, and names the dependency so Phase 4's routers reuse `EngineDependency` rather than repeating the call. The second was taken.
- **The lifespan is a closure, not a read of `app.state`.** The plan's literal wording disposes `app.state.database.engine`. That type-checks — the attribute arrives as `Any`, and mypy has nothing to object to — which is exactly the problem: it discards the type of an object the same function constructed three lines earlier, in the one place where no narrowing is needed. Closing over `resources` keeps the shutdown path fully typed and keeps `dependencies.py` the only module in the project that reads application state back.
- **Four grep gates were kept real by describing the forbidden shapes without naming them.** `dependencies.py` must contain no occurrence of the word the acceptance criterion greps for, while the plan's action text asks the docstring to state the rule explicitly. Both are satisfied by prose — "making the block's work durable is the use case's decision and only the use case's (ARC-08)" — which states the rule more precisely than the forbidden token would have. `health.py` does the same for the framework's HTTP exception, the RFC 9457 builder and the raw JSON response. This is the phase's prose-not-literal convention, applied for the tenth time.
- **The `get_uow` proof is a throwaway router, and the module docstring explains why an override would have been worthless.** Overriding the provider replaces the code under test, so the interesting property would be supplied by the test rather than proved by it. The router carries two routes — one that reads through the yielded unit of work, proving the session is live against the migrated schema, and one that writes without finishing — and both are `include_in_schema=False`, declared in the test module, never anywhere near the production application.
- **`test_the_dependency_yields_a_usable_unit_of_work` asserts adapter class names, not non-nullness.** `unit.tasks is not None` is true of anything; the three names prove the provider handed over the SQLAlchemy adapters, and the extra `await unit.users.get(...)` proves the block was actually entered, since an unopened unit of work raises the `RuntimeError` 03-08 added.
- **This module runs outside the D-01 fixture transaction, deliberately, and says so.** The application builds its own engine from the DSN, exactly as in production, and nothing is bound to the connection `tests/integration/conftest.py` rolls back — which is the only arrangement in which an escaping write *could* be seen, and therefore the only one in which its absence means anything. `test_the_users_table_is_left_empty` closes the module, and its docstring records that the right response to a failure there is not to add a cleanup step.
- **No requirement tick taken.** The plan's frontmatter lists `DOCK-03`, `ARC-08` and `DB-01`; `03-11-PLAN.md` claims all three again. Under the last-claimant convention, 03-11 owns the ticks. Ninth consecutive plan in this phase to make the same call.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] B008 fired on the plan's `engine: AsyncEngine = Depends(get_engine)`**

- **Found during:** Task 2
- **Issue:** `make lint` failed with `health.py:86:47: B008 Do not perform function calls in argument defaults`. `.flake8` L8 carries `extend-immutable-calls = fastapi.Depends,...` and PATTERNS.md concluded from it that B008 could not fire — but flake8-bugbear matches the call name as it appears in the source, and this project imports by name (`from fastapi import Depends`), so the whitelist entry never applied.
- **Fix:** A module-level `EngineDependency = Annotated[AsyncEngine, Depends(get_engine)]` and `async def health(response: Response, engine: EngineDependency)`. No `.flake8` change, so no linter rule was loosened for the rest of the repository, and the comment above the alias records both the rule and the alternative.
- **Files modified:** `src/taskmanager/presentation/api/health.py`
- **Commit:** `b56e5d6`

**2. [Rule 2 — Missing coverage of a new branch] the lifespan had no test**

- **Found during:** Task 2
- **Issue:** The plan lists five unit tests, none of which enters the lifespan — `ASGITransport` does not run it. The disposal added in the same task would therefore have been the first untested line in `src/taskmanager` since 03-05, and the project's own rule is that every new branch gets a test.
- **Fix:** `test_the_lifespan_disposes_the_engine` enters `app.router.lifespan_context(app)` and asserts the engine's pool object is unchanged inside the block and replaced after it. Six unit tests against the plan's floor of five, and coverage stayed at 100%.
- **Files modified:** `tests/unit/presentation/test_health.py`
- **Commit:** `b56e5d6`

**3. [Rule 3 — Blocking] a `type: ignore` was avoided in the shared-shape test**

- **Found during:** Task 3
- **Issue:** Annotating the decoded body as `dict[str, object]` makes `set(body["checks"])` a mypy `arg-type` error, and the obvious fix is a suppression comment. This repository has none, and 03-08 kept that count at zero on the same argument.
- **Fix:** The helper returns `tuple[int, dict[str, Any]]`, with a docstring recording that a decoded payload is read loosely on purpose — narrowing it in the test would describe the contract instead of checking it.
- **Files modified:** `tests/integration/test_health.py`
- **Commit:** `f81cc8e`

### Deviations from the plan's letter

**4. The lifespan disposes through a closure rather than through `app.state`**

- **Found during:** Task 2
- **Reason:** Recorded in full under "Decisions Made". The plan's form type-checks; the closure keeps the shutdown path typed and keeps the single narrowing in `dependencies.py` genuinely single.
- **Files modified:** `src/taskmanager/main.py`
- **Commit:** `b56e5d6`

**5. A fourth test in `test_dependencies.py`, and falsification evidence the plan did not ask for**

- **Found during:** Task 3
- **Reason:** The plan's action text ends with "assert the `users` table is empty at the end, since this module deliberately runs outside the D-01 fixture transaction" — which is a fourth property, so it became a fourth named test rather than a trailing assertion on an unrelated one. The evidence file follows 03-08's precedent: a green test asserting that something did *not* happen is worth what its red run proves, and the teardown-commit break is the only way to produce that run.
- **Files modified:** `tests/integration/test_dependencies.py`, `evidence/03-09-teardown-falsification.txt`
- **Commit:** `f81cc8e`

Everything else executed as written. Every acceptance criterion passed: `import taskmanager; taskmanager.__version__ == '0.1.0'` exits 0; `grep -c '"0.1.0"' src/taskmanager/main.py` prints `0` and `grep -rn '"0.1.0"' src tests` outside the package init prints nothing; `tests/unit/test_version.py` passes 2 tests on the host and inside the `test` image; `tests/unit/presentation/test_health.py` passes 6 against a floor of 5 with no database; `grep -c` prints `0` for the HTTP exception and the problem builder, `0` for the raw JSON response, `1` for the narrowing and `0` for the durability verb; the OpenAPI one-liner exits 0; `make arch` keeps three contracts; `.venv/bin/mypy src tests` is clean with no suppression anywhere; the integration health suite reports 3 against a floor of 3 and the dependency suite 4 against a floor of 3; `grep -c "def test_health_reports_ok_against_a_reachable_database"` prints `1`; `SELECT count(*) FROM users` prints `0` after the run; and `make test` twice in a row reports 287 both times with `Required test coverage of 75% reached. Total coverage: 100.00%`.

## Issues Encountered

- **The falsification run committed one row that had to be removed by hand.** With `await unit.commit()` in the teardown the write became durable in `taskmanager_test`, and this module deliberately runs outside the D-01 rollback, so nothing cleaned it up. `DELETE FROM users` was run once and the count verified at `0` before the suite was re-run. Worth knowing for any future plan that falsifies a persistence claim from outside the isolation fixture: the red run leaves real rows.
- **No `.env` exists in this repository by design**, so `DATABASE_URL`, `TEST_DATABASE_URL` and `JWT_SECRET` were exported in the shell for every test run, exactly as in 03-05 through 03-08. `pre-commit` runs no pytest, so the commits themselves needed no database.
- Nothing else. `filterwarnings = error` raised nothing new: entering `app.router.lifespan_context(app)` from an async test emits no warning, and neither does disposing the second engine in the row-count helper.

## Known Stubs

None. Both new source modules are complete, and every public function in them is driven by at least one test — including `get_session_factory`, which no production caller has yet: Phase 4 is its first consumer, and it is exercised today through `get_uow`, which is built on it. The `/health` `checks` dictionary carries exactly one key because exactly one dependency exists; it is a dictionary rather than a boolean precisely so a second check can be added without changing the document's shape.

## Threat Flags

None new. This plan opens one endpoint, and it is the one the threat register already covers; it installs nothing (`requirements.txt` untouched, so T-3-SC stays `accept`) and reads no user input at all — `/health` takes no parameter, no header and no body. The register's five `mitigate` rows are implemented:

- **T-3-26** (a driver message describing the database to an anonymous caller) — *mitigated*: `_database_is_reachable` returns a `bool`, the exception is caught and discarded, and `test_the_unavailable_body_leaks_no_driver_detail` asserts the response text contains none of `psycopg`, `Traceback`, the password, `127.0.0.1` or the database name.
- **T-3-28** (a hung database piling up request-scoped connections) — *mitigated*: every probe runs inside `asyncio.timeout(DATABASE_PROBE_TIMEOUT_SECONDS)` at 2.0 s, and the engine was built with pre-ping in 03-08, so a dead pooled connection costs one retry rather than one failed healthcheck.
- **T-3-21** (a write escaping the use case's decision) — *mitigated*: `get_uow` opens the block and nothing else, and `test_the_dependency_does_not_commit_on_teardown` proves it with a second connection. The falsification evidence shows the same test failing the moment the teardown finishes the transaction.
- **T-3-29** (a side effect at application construction) — *mitigated*: no migration and no statement runs in `create_app()` or in the lifespan's startup half. `test_creating_the_app_opens_no_connection` builds the real application on a dead DSN and asserts zero connections checked out; `test_the_lifespan_disposes_the_engine` asserts the pool is untouched *inside* the block.
- **T-3-25** (pooled connections carrying credentials left open after shutdown) — *mitigated*: the lifespan disposes the engine, and the disposal is asserted by pool identity rather than assumed.

**T-3-27** stays `accept` as the register records: `/health` is unauthenticated by D-08, and `test_health_requires_no_authentication` pins it so Phase 5 cannot quietly protect it.

## User Setup Required

None new. `docker compose up -d db` (or `make up`) must be running before `make test`, and until `.env` exists on a given machine `DATABASE_URL`, `TEST_DATABASE_URL` and `JWT_SECRET` must be in the shell — `cp .env.example .env` covers all three.

## Next Phase Readiness

- **03-10 has the endpoint its Dockerfile `HEALTHCHECK` and compose `api` service depend on.** `GET /health` answers 200 only when the database answers, 503 otherwise, and the 503 is what makes the container report unhealthy — so `depends_on: condition: service_healthy` becomes meaningful rather than decorative. The `--start-period` argument in RESEARCH Pattern 8 still matters: the API is not listening until the entrypoint's migration finishes.
- **Phase 4's routers need no new wiring.** `Annotated[UnitOfWork, Depends(get_uow)]` is the whole signature; the boundary arrives open and finishes nothing, and `dependencies.py` is where any further provider belongs. The annotated-alias form is established by `EngineDependency` and by the probe router's `UnitOfWorkDependency`, so a Phase 4 handler copies a shape that already passes B008.
- **Phase 5 has one standing obligation, and it is now a test.** `test_health_requires_no_authentication` fails if an authentication dependency is applied application-wide rather than router-by-router.
- **ADR debt for 03-11 grows by one entry**: the `Annotated[...]` injection form and the reason it replaced the default-argument form — a linter whitelist that matches the dotted spelling this project does not use. It joins the existing debt (the PostgreSQL 18 volume path, literal constraint names in revisions, the case-sensitivity contrast, the test-only key on `Settings`, the WR-05 resolution, `make test` requiring PostgreSQL, the deliberate non-translation of the three CHECK constraints, and 03-08's engine-lifetime resolution).
- **Coverage is at 100% with the gate at 75%**, unchanged since 03-05 across 59 further statements.
- No blockers.

## Self-Check: PASSED

All eight created files exist on disk and the three modified files carry their changes; all three task commits (`4299993`, `b56e5d6`, `f81cc8e`) are present in `git log`. No commit deleted a tracked file (`git diff --diff-filter=D --name-only HEAD~3 HEAD` is empty) and `git status --short` was clean after each. `make lint && make typecheck && make arch && make test` was run green before every commit: 287 passed, 100.00% coverage over `src/taskmanager` with the gate at 75%, three contracts KEPT.

---
*Phase: 03-persistence-runnable-stack*
*Completed: 2026-09-18*
