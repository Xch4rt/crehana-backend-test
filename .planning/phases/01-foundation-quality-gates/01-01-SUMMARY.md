---
phase: 01-foundation-quality-gates
plan: 01
subsystem: infra
tags: [python, setuptools, src-layout, pip, flake8, black, isort, mypy, pytest, coverage]

# Dependency graph
requires: []
provides:
  - "Installable `taskmanager` package under a src layout (editable install in .venv)"
  - "Four empty layer packages: domain, application, infrastructure, presentation"
  - "Exact-pinned requirements.txt and requirements-dev.txt for the whole project lifetime"
  - "pytest.ini as the single source of pytest and coverage configuration (75% gate)"
  - ".flake8 with black-compatible, extend-only configuration"
  - "black / isort / mypy-strict / coverage configuration in pyproject.toml"
  - ".gitignore and .dockerignore that keep .env out of git and out of any image layer"
affects: [01-02, 01-03, 01-04, 02-domain, 03-infrastructure, docker, ci]

# Tech tracking
tech-stack:
  added:
    - "setuptools>=77 build backend (packaging only)"
    - "pytest 9.1.1, pytest-asyncio 1.4.0, pytest-cov 7.1.0, httpx 0.28.1"
    - "black 26.5.1, isort 9.0.1, flake8 7.3.0 (+ bugbear 26.9.9, comprehensions 3.17.0, pep8-naming 0.15.1)"
    - "mypy 2.3.1, import-linter 2.15, pre-commit 4.6.2"
    - "fastapi 0.141.1, pydantic 2.13.5, pydantic-settings 2.15.0, uvicorn 0.53.0 (pinned, imported later)"
    - "SQLAlchemy 2.0.54, psycopg[binary] 3.3.5, alembic 1.20.0, PyJWT 2.14.0, pwdlib[argon2] 0.3.1 (pinned, imported later)"
  patterns:
    - "src layout + `pip install -e .` as the one mechanism that serves pytest, coverage, mypy and import-linter"
    - "requirements*.txt is the single source of truth for versions; `[project.dependencies]` deliberately absent"
    - "Quality thresholds live in declarative config (pytest.ini addopts), never in a wrapper script"

key-files:
  created:
    - pyproject.toml
    - requirements.txt
    - requirements-dev.txt
    - pytest.ini
    - .flake8
    - .gitignore
    - .dockerignore
    - src/taskmanager/__init__.py
    - src/taskmanager/domain/__init__.py
    - src/taskmanager/application/__init__.py
    - src/taskmanager/infrastructure/__init__.py
    - src/taskmanager/presentation/__init__.py
    - tests/__init__.py
    - tests/unit/__init__.py
    - tests/architecture/__init__.py
  modified: []

key-decisions:
  - "requires-python is `>=3.13` (never `==3.13.*`) so the CPython 3.14.3 host venv installs, while mypy python_version=3.13 and black target-version=py313 keep the analysis target at 3.13"
  - "No `[project.dependencies]` in pyproject.toml: a second version list would drift from requirements*.txt"
  - "`--cov=taskmanager` is the package name, not a path, so un-imported modules land in the coverage denominator"
  - ".flake8 uses only extend-ignore / extend-exclude; the bare forms silently replace pycodestyle and flake8 defaults"
  - "The 75% coverage threshold lives in pytest.ini addopts so local, Docker and CI runs are gated by the same bytes"

patterns-established:
  - "Layer packages exist as empty, zero-statement `__init__.py` files so they neither inflate nor deflate coverage"
  - "Every gate in this phase is a declarative artifact; no imperative wrapper acquires its own bug surface"
  - "Host venv at .venv (CPython 3.14.3) for the fast inner loop; Docker/CI on 3.13 remain authoritative"

requirements-completed: [FND-01, FND-02, FND-03, FND-04, FND-05, FND-06, FND-07, ARC-01]

# Metrics
duration: 13min
completed: 2026-09-17
---

# Phase 01 Plan 01: Packaging Skeleton and Gate Configuration Summary

**Installable `taskmanager` src-layout package with four empty layer packages, 28 exact-pinned dependencies, and black/isort/flake8/mypy-strict/pytest-coverage configuration that all run green on an empty codebase.**

## Performance

- **Duration:** 13 min
- **Started:** 2026-09-17T22:12:00Z
- **Completed:** 2026-09-17T22:25:00Z
- **Tasks:** 3
- **Files created:** 15

## Accomplishments

- `pip install -e .` makes `taskmanager` importable for pytest, coverage, mypy and (from plan 03) import-linter through one mechanism.
- Both requirement files are exact-pinned; `pip install --dry-run -r requirements-dev.txt` resolves with no conflict on CPython 3.14.3 / macOS arm64 with no source builds.
- `pytest.ini` and `.flake8` exist as the literal root files the challenge brief names, with the research-corrected values (`extend-` forms only, `--cov=taskmanager`, `asyncio_default_fixture_loop_scope = function`, `filterwarnings = error`).
- `black --check`, `isort --check-only`, `flake8` and `mypy --strict` all exit 0 over `src tests`; `pytest --collect-only` confirms `configfile: pytest.ini`.
- `.env` is excluded from git and from every Docker build context before any secret file can exist (threats T-01-01 / T-01-02).

## Task Commits

1. **Task 1: Packaging skeleton, layer packages and pinned requirements** - `34071eb` (chore)
2. **Task 2: Literal gate configuration files (pytest.ini, .flake8, pyproject tool sections)** - `57a0845` (chore)
3. **Task 3: Ignore files, venv bootstrap and first green gate subset** - `d48bff1` (chore)

## Files Created/Modified

- `pyproject.toml` - setuptools packaging block (src layout, `requires-python = ">=3.13"`, no `dependencies` key) plus black / isort / mypy / coverage configuration
- `requirements.txt` - 11 exact-pinned runtime dependencies, grouped with English section comments
- `requirements-dev.txt` - `-r requirements.txt` plus 13 exact-pinned dev and gating tools
- `pytest.ini` - testpaths, `pythonpath = src`, asyncio auto mode, `--cov=taskmanager --cov-fail-under=75`, `unit`/`integration` markers, `filterwarnings = error`
- `.flake8` - `max-line-length = 88`, `extend-ignore = E203,E701`, `extend-exclude`, `extend-immutable-calls` for FastAPI `Depends()`, `max-complexity = 10`
- `.gitignore` - `.venv/`, `.env`, caches, `.import_linter_cache/`, `src/*.egg-info/`, coverage artifacts
- `.dockerignore` - `.git`, `.env`, `.planning`, `.github`, caches and build artifacts
- `src/taskmanager/{,domain/,application/,infrastructure/,presentation/}__init__.py` - the four layer packages (zero-byte)
- `tests/{,unit/,architecture/}__init__.py` - mirror test tree so `flake8 src tests` and friends are valid invocations from wave 1

## Decisions Made

None beyond the plan - every value came from the plan and from `01-RESEARCH.md`. The one judgement call worth recording: the em dash in the `pyproject.toml` `description` was written as a plain hyphen to keep the file pure ASCII, which avoids any encoding ambiguity in build metadata.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. The host has no CPython 3.13 (3.14.3 only), which the plan already anticipated: `python3 -m venv .venv` plus `requires-python = ">=3.13"` installed and ran every pinned tool without a single source build.

## Verification Results

| Check | Result |
|-------|--------|
| `python3 -c "tomllib ... requires-python == '>=3.13'"` | pass |
| `pyproject.toml` has no `project.dependencies` | pass |
| all `requirements*.txt` lines use `==` | pass |
| no `conftest.py` anywhere in the repo | pass (0 files) |
| `.flake8` matches neither `^\s*ignore\s*=` nor `^\s*exclude\s*=` | pass |
| `.flake8` contains no `B950` and no `S101` | pass |
| `tool.coverage.run` has no `omit`; `pyproject.toml` has no `[tool.pytest.ini_options]` | pass |
| `import taskmanager.{domain,application,infrastructure,presentation}` | pass |
| `black --check src tests` | pass (8 files unchanged) |
| `isort --check-only src tests` | pass |
| `flake8 src tests` | pass (no output) |
| `mypy src tests` | `Success: no issues found in 8 source files` |
| `pytest --collect-only` reports `configfile: pytest.ini` | pass |
| `pip install --dry-run -r requirements-dev.txt` | pass |
| `git status --porcelain` free of `.venv`, `__pycache__`, `.coverage`, `*.egg-info` | pass |

## Self-Check: PASSED

All 15 created files verified present on disk; commits `34071eb`, `57a0845`, `d48bff1` verified in `git log`.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for plan 01-02. Notes for the next executor:

- The host virtualenv lives at `.venv/` in the repository root and runs **CPython 3.14.3**. Invoke every tool through it: `.venv/bin/pytest`, `.venv/bin/black`, `.venv/bin/isort`, `.venv/bin/flake8`, `.venv/bin/mypy`, `.venv/bin/lint-imports`. `taskmanager 0.1.0` is already installed editable, so no re-install is needed unless `pyproject.toml` changes.
- Do **not** run a bare `.venv/bin/pytest` until plan 02 lands real tests: there are zero tests and zero statements, so `--cov-fail-under=75` legitimately fails. Plan 02 (`settings.py` + `main.py` + six tests) is what turns the full suite green.
- `infrastructure/config/` does not exist yet - plan 02 owns it. No `conftest.py` exists, and research confirms Phase 1 needs none.
- `.importlinter` and `pre-commit install` are deliberately not done: plans 03 and 04 own them. `.import_linter_cache/` is already gitignored for when they arrive.
- `mypy` is configured with `packages = ["taskmanager"]`, so a bare `mypy` checks the package; use `mypy src tests` to include the test tree.

---
*Phase: 01-foundation-quality-gates*
*Completed: 2026-09-17*
