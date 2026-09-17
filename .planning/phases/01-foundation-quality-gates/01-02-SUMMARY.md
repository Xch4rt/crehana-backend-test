---
phase: 01-foundation-quality-gates
plan: 02
subsystem: config
tags: [pydantic-settings, fastapi, composition-root, coverage, tdd, mypy-strict]

# Dependency graph
requires:
  - "01-01: installable `taskmanager` src-layout package, pytest.ini with the 75% gate, mypy strict + pydantic plugin"
provides:
  - "`taskmanager.infrastructure.config.settings.Settings` - the six-field, environment-backed settings model"
  - "`taskmanager.infrastructure.config.settings.get_settings()` - lru_cache(maxsize=1) process-wide accessor"
  - "`taskmanager.main.create_app(settings=None) -> FastAPI` - the composition root and the DI seam for Phase 3"
  - "`.env.example` documenting every declared field, with a test enforcing the parity"
  - "Six value-asserting unit tests taking the real package to 100% coverage"
  - "Committed evidence that the 75% coverage gate fires below threshold and recovers"
affects: [01-03, 01-04, 01-05, 03-infrastructure, 05-auth, docker, ci]

# Tech tracking
tech-stack:
  added:
    - "pydantic-settings 2.15.0 BaseSettings (first import; pinned in plan 01-01)"
    - "fastapi 0.141.1 (first import; pinned in plan 01-01)"
  patterns:
    - "Secret-bearing settings fields carry NO default, so a misconfigured process dies at boot with one ValidationError instead of at the first request"
    - "`create_app()` factory with an optional `settings` parameter; never a module-level `app = create_app()`"
    - "Every `Settings(...)` construction in tests passes `_env_file=None`, so a developer `.env` cannot silence a negative-path assertion"
    - "`get_settings.cache_clear()` before and after any test that touches the cache"
    - "Quality gates are proven by observation: the coverage gate was watched failing, and the output is committed"

key-files:
  created:
    - src/taskmanager/infrastructure/config/__init__.py
    - src/taskmanager/infrastructure/config/settings.py
    - src/taskmanager/main.py
    - .env.example
    - tests/unit/test_settings.py
    - tests/unit/test_app_factory.py
    - .planning/phases/01-foundation-quality-gates/evidence/coverage-gate-red.txt
  modified: []

key-decisions:
  - "Executed as a real TDD cycle: the six tests were written and observed failing (RED, commit 3d48d02) before settings.py and main.py existed (GREEN, commit 58a0497). The plan assigned the test files to Task 2 and the modules to Task 1; both tasks carried tdd=\"true\", and honouring the RED-before-GREEN ordering required landing the tests in Task 1's RED commit."
  - "`test_get_settings_is_cached` also asserts `get_settings() == Settings(_env_file=None)`, proving the lru_cache holds the current environment rather than a stale object - added to satisfy the plan's `_env_file=None >= 4` criterion with a real assertion instead of padding"
  - "The coverage probe used 16 statements (research predicted 12), giving 40.91% rather than the predicted 56.25% - a deeper red, same conclusion"
  - "`settings.py` keeps `env_file=\".env\"` in production config even though every test bypasses it with `_env_file=None`; the file-based path is a real deployment affordance and Docker/compose will use it in Phase 3"

patterns-established:
  - "18 statements over two modules at 100% is the whole coverage story of Phase 1; every later plan adds statements that must carry their own tests"
  - "Evidence files under `.planning/phases/<phase>/evidence/` capture gate demonstrations verbatim for later embedding into AI_WORKFLOW.md (plan 01-07)"

requirements-completed: [FND-11, FND-06, FND-01, FND-07]

# Metrics
duration: 5min
completed: 2026-09-17
---

# Phase 01 Plan 02: Settings, Composition Root and an Honest 75% Summary

**The two real modules Phase 1 ships - a six-field pydantic-settings model whose secrets have no defaults, and a `create_app()` factory that imports no database - tested to 100% by six value-asserting tests, with the coverage gate observed failing at 40.91% and recovering.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-09-17T22:40:10Z
- **Completed:** 2026-09-17T22:45:11Z
- **Tasks:** 3
- **Files created:** 7

## Accomplishments

- `Settings` declares six fields; `database_url` and `jwt_secret` have no default at all, so a process missing either refuses to start (D-16 / T-01-06). `jwt_secret` additionally enforces `min_length=16`, and both negative paths are asserted by tests.
- `extra="forbid"` turns an unknown key in `.env` into a boot-time `ValidationError` rather than a silent no-op (T-01-08); `frozen=True` makes settings read-only after load (T-01-09).
- `create_app(settings=None)` is a factory with no module-level instance, no `__main__` block, no router and no database import. `import taskmanager.main` succeeds with `JWT_SECRET` and `DATABASE_URL` both unset - verified explicitly with `env -u` (T-01-11, FND-01).
- `.env.example` documents all six fields with obviously fake placeholders, and `test_env_example_documents_every_field` asserts set equality in both directions, so adding a field without documenting it fails the suite (FND-11).
- Total coverage is **100.00% over 18 statements** with no `# pragma: no cover`, no `omit` entry and no change to `--cov-fail-under=75`.
- The gate was proven real: a 16-statement module that no test imports dropped the total to **40.91%** and pytest exited 1 with `FAIL Required test coverage of 75% not reached` - while all six tests still passed, which is exactly the point. Both runs are committed verbatim (T-01-10, FND-06).
- `mypy src tests` is clean over 13 source files with **zero** `type: ignore` comments, confirming the `plugins = ["pydantic.mypy"]` line from plan 01-01 is doing its job on both `Settings()` and `_env_file=None` (FND-07, RESEARCH Pitfall 4).

## Task Commits

1. **Task 1 (RED): failing tests for settings and the app factory** - `3d48d02` (test)
2. **Task 1 (GREEN): settings module, composition root and .env.example** - `58a0497` (feat)
3. **Task 2: cached-settings assertion + full host gate green** - `60074c7` (test)
4. **Task 3: coverage gate red/green evidence** - `b1408c0` (docs)

## Files Created/Modified

- `src/taskmanager/infrastructure/config/settings.py` - `Settings(BaseSettings)` (13 statements) and `get_settings()` under `lru_cache(maxsize=1)`
- `src/taskmanager/main.py` - `create_app(settings: Settings | None = None) -> FastAPI` (5 statements), title from settings, `version="0.1.0"`, `openapi_url="/openapi.json"`
- `src/taskmanager/infrastructure/config/__init__.py` - empty, zero statements
- `.env.example` - six documented keys with non-secret placeholders and an English comment each
- `tests/unit/test_settings.py` - five tests: environment read, missing secret, short secret, cache identity, `.env.example` parity
- `tests/unit/test_app_factory.py` - `test_create_app_uses_settings`
- `.planning/phases/01-foundation-quality-gates/evidence/coverage-gate-red.txt` - both pytest runs verbatim, with the date, the exact command and the `source = ["taskmanager"]` rationale

## Decisions Made

- **TDD ordering over task-file assignment.** Both tasks were marked `tdd="true"`, but the plan put the modules in Task 1 and the tests in Task 2 - a literal reading would have written implementation first, which is not TDD. The tests were written first and observed failing with `ModuleNotFoundError` (commit `3d48d02`), then the modules made them pass (commit `58a0497`). Every file the plan named exists; only the commit-to-task mapping shifted.
- **The fourth `_env_file=None`.** The plan required at least four occurrences in `test_settings.py`, but the research original reached four only because the app-factory test lived in the same file; this plan split it into `test_app_factory.py`. Rather than pad, `test_get_settings_is_cached` gained a real assertion - `get_settings() == Settings(_env_file=None)` - which proves the cached instance reflects the current environment.
- **Assertion strings over bare `pytest.raises`.** The two negative-path tests assert on the `ValidationError` content (`"jwt_secret"`, `"at least 16 characters"`), so they cannot pass for the wrong reason - a `ValidationError` raised by an unrelated field would no longer satisfy them.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical functionality] `_env_file=None` occurrence count below the plan's own acceptance criterion**

- **Found during:** Task 2
- **Issue:** The plan required `grep -c '_env_file=None' tests/unit/test_settings.py` to be at least 4, but the plan's own task split (app-factory test moved to a separate module) made 3 the natural count. Reaching 4 by duplication would have been padding.
- **Fix:** Added `assert first == Settings(_env_file=None)` to `test_get_settings_is_cached`, strengthening the test with a real claim - the `lru_cache` returns settings equal to a fresh read of the current environment - while satisfying the criterion honestly.
- **Files modified:** `tests/unit/test_settings.py`
- **Commit:** `60074c7`

### Process Deviations

**2. Task 1 executed as two commits (RED then GREEN) rather than one**

- **Found during:** Task 1
- **Reason:** `tdd="true"` mandates writing and observing failing tests before implementation. The plan's `<files>` block assigned the test modules to Task 2, so the RED commit necessarily contains Task 2's files.
- **Impact:** Four task commits instead of three. No file was skipped, added or renamed; the RED run is recorded in the commit message of `3d48d02`.

## Issues Encountered

None blocking. Two observations worth carrying forward:

- The probe module produced 16 statements rather than the 12 the research predicted, so the red total was 40.91% instead of 56.25%. The demonstration is strictly stronger; nothing else changed.
- `get_settings()` internally constructs `Settings()` with `env_file=".env"`. No `.env` exists in the repository (it is git-ignored and was never created), so this is currently inert. If a developer later creates a `.env` containing a key outside the six declared fields, `extra="forbid"` will make `test_get_settings_is_cached` fail loudly. That is the correct failure mode - loud, not a silent pass - and it does not weaken any negative-path assertion, since those all use `_env_file=None`.

## Verification Results

| Check | Result |
|-------|--------|
| `.venv/bin/pytest` | pass - 6 passed, exit 0 |
| Total coverage | **100.00%**, `Required test coverage of 75% reached` |
| Coverage table matches `find src -name '*.py'` | pass - `diff` of the two sorted lists is empty (8 files) |
| No `Coverage.py warning` / `CoverageWarning` in output | pass (RESEARCH Pitfall 5 manual read) |
| No warnings summary (`filterwarnings = error` active) | pass |
| `.venv/bin/mypy src tests` | `Success: no issues found in 13 source files` |
| `.venv/bin/flake8 src tests` | pass (no output) |
| `.venv/bin/black --check src tests` | pass (13 files unchanged) |
| `.venv/bin/isort --check-only src tests` | pass |
| `import taskmanager.main` with `JWT_SECRET`/`DATABASE_URL` unset | pass |
| `grep -rn 'pragma: no cover\|type: ignore' src tests` | no matches |
| `grep -cE 'APIRouter\|include_router\|/health' src/taskmanager/main.py` | 0 |
| `grep -c '__main__' src/taskmanager/main.py` | 0 |
| `Settings.model_fields['database_url'\|'jwt_secret'].is_required()` | both `True` |
| `.env.example` keys == upper-cased `Settings.model_fields` | pass (6 == 6) |
| Evidence file contains both the red and the green gate lines | pass |
| `_coverage_probe.py` absent from disk and from `git status` | pass |
| `--cov-fail-under=75` in `pytest.ini` unchanged | pass |
| `AI_WORKFLOW.md` not created or modified | pass (does not exist) |

## Self-Check: PASSED

All 7 created files verified present on disk; commits `3d48d02`, `58a0497`, `60074c7`, `b1408c0` verified in `git log`.

## Known Stubs

None. Both modules are complete for their Phase 1 responsibility. `DATABASE_URL` is declared and validated but not yet consumed by any code - that is intentional and stated in `.env.example`: declaring it now lets the CI job export it and lets Phase 3 add repositories without touching settings.

## User Setup Required

None - no external service configuration required. Developers who want a local `.env` can `cp .env.example .env`; the test suite does not need one.

## Next Phase Readiness

Ready for plan 01-03 (import-linter contracts and the architecture test). Notes for the next executor:

- **The import graph now has real edges to enforce.** `taskmanager.main` imports `taskmanager.infrastructure.config.settings`, which is downward and legal under the D-10 layers contract (`main > presentation > infrastructure > application > domain`). `presentation`, `application` and `domain` are still empty packages with zero statements.
- **import-linter needs every layer module to be importable.** All eight modules import cleanly with no environment variables set - verified. `create_app` being a factory rather than a module-level `app` is exactly what makes this true; do not let a later plan add `app = create_app()`.
- **The red/green demonstration pattern is established.** Plan 01-03 owes the same for its contract (CONTEXT D-10: "demonstrate the contract goes red on a deliberate forbidden import and green once removed"). Put the capture in `.planning/phases/01-foundation-quality-gates/evidence/`, alongside `coverage-gate-red.txt`, so plan 01-07 can embed both. Suggested name: `architecture-contract-red.txt`.
- **Do not use `python -m importlinter.cli` in the test** (RESEARCH Pitfall 1: it always exits 0). The verified approach is the `importlinter.api.read_configuration()` + `create_report()` route sketched at RESEARCH line 452.
- **Adding an architecture test adds no statements to the coverage denominator** (tests are not in `source = ["taskmanager"]`), so the 100% figure survives. But if plan 01-03 adds any module under `src/`, it must be tested - the margin above 75% is 18 statements wide and a single untested 7-statement module would drop the total to 72%.
- **`tests/architecture/__init__.py` already exists** (created by plan 01-01) and is empty.
- **Tooling reminders:** `.venv/bin/lint-imports` is installed; `.import_linter_cache/` is already git-ignored; `mypy` is configured with `packages = ["taskmanager"]`, so use `mypy src tests` to cover the test tree.

---
*Phase: 01-foundation-quality-gates*
*Completed: 2026-09-17*
