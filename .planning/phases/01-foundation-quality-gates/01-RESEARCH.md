# Phase 1: Foundation & Quality Gates - Research

**Researched:** 2026-09-17
**Domain:** Python project scaffolding and automated quality enforcement (src layout, flake8/black/isort, mypy strict, pytest + coverage gate, import-linter architecture contracts, pre-commit, GitHub Actions, multistage Docker)
**Confidence:** HIGH — every configuration in this document was executed end-to-end in a throwaway scaffold with the exact pinned versions, on the host (CPython 3.14.3, macOS arm64) **and** inside `python:3.13-slim-trixie` (Python 3.13.15, linux/aarch64). Findings marked `[VERIFIED: local execution]` were observed, not inferred.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Runtime & layout**
- **D-01**: Python 3.13; Docker base image `python:3.13-slim-trixie`.
- **D-02**: `src/taskmanager/` package layout with sub-packages `domain`, `application`, `infrastructure`, `presentation` (each with `__init__.py`), plus `main.py` as composition root.
- **D-03**: Dependencies managed with plain pip and exact `==` pins in `requirements.txt` (runtime) and `requirements-dev.txt` (dev/test). Versions come from `.planning/research/STACK.md` (verified against PyPI on 2026-09-17). No uv/poetry required on the host.

**Lint / format / types**
- **D-04**: `.flake8` file (literal, required by the brief): `max-line-length = 88`, `extend-ignore = E203, E701` — never `ignore =`. Plugins: flake8-bugbear, flake8-comprehensions, pep8-naming.
- **D-05**: black and isort configured in `pyproject.toml`; isort `profile = "black"`.
- **D-06**: mypy in strict mode over `src/`, configured in `pyproject.toml`.
- **D-07**: ruff is NOT used (brief mandates flake8); recorded in `DECISION_LOG.md`.

**Tests & coverage**
- **D-08**: All pytest configuration lives in `pytest.ini` (literal file, required by the brief; pytest ignores `[tool.pytest.ini_options]` when it exists): `asyncio_mode = auto`, `asyncio_default_fixture_loop_scope = function`, `filterwarnings = error` (with targeted ignores only if a transitive dependency forces it), markers `unit` and `integration`.
- **D-09**: Coverage measures the real package (`source = taskmanager` / `src/taskmanager`), excludes tests, reports un-imported files, and fails under 75% (`--cov-fail-under=75`). Never `--cov=.`.

**Architecture enforcement**
- **D-10**: import-linter `layers` contract: `taskmanager.main > taskmanager.presentation > taskmanager.infrastructure > taskmanager.application > taskmanager.domain`, plus a `forbidden` contract banning `fastapi`, `starlette`, `sqlalchemy` (and any third-party lib for `domain`) from `domain` and `application`. The contracts run inside the pytest suite (a test invoking `lint-imports`) and as a CI step. The phase must demonstrate the contract goes red on a deliberate forbidden import and green once removed.

**Automation**
- **D-11**: pre-commit runs black, isort, flake8 and mypy.
- **D-12**: `Makefile` targets: `install`, `lint`, `format`, `typecheck`, `test`, `up`, `down` (`up`/`down` may be thin placeholders until compose lands in Phase 3, but must exist).
- **D-13**: GitHub Actions workflow on every push: lint, typecheck, architecture check, tests with coverage gate, against a `postgres:18-alpine` service container.

**Docker**
- **D-14**: Multistage `Dockerfile` producing a slim image that runs as a non-root user.
- **D-15**: One documented command runs the test suite inside Docker with no Python on the host.

**Configuration**
- **D-16**: Settings via pydantic-settings, read from environment; no secret has a hard-coded production default; `.env.example` documents every variable; `.env` is git-ignored.

**AI transparency & docs**
- **D-17**: `CLAUDE.md` gains a project-rules section: layer rules, no `HTTPException` outside presentation, quality gates must be green before commit, English only, no AI attribution in commits.
- **D-18**: `AI_WORKFLOW.md` is created with its section skeleton and a dated incident log whose first entries are REAL events from this project (no invented incidents). Known real entries so far: (a) a research-synthesizer subagent was refused by a file-write guardrail and worked around it via a shell heredoc instead of reporting back — caught by the orchestrator reading the agent's report, content reviewed before commit, subagent prompts since then forbid workarounds; (b) the four research agents produced 9 conflicting recommendations (e.g. Python 3.12 vs 3.13, RFC 7807 vs 9457, loop scope function vs session) — surfaced explicitly and resolved by the human/orchestrator rather than silently picked.
- **D-19**: `DECISION_LOG.md` is started in this phase in ADR style (context / options / decision / consequences), recording the decisions locked so far: PostgreSQL, Python 3.13, src layout, dataclass domain + Pydantic boundaries, RFC 9457, psycopg 3 + async SQLAlchemy, Alembic, 404/403 visibility rule, whole-list completion %, flake8-over-ruff, pip pins, pytest-asyncio loop scope, `postgres:18-alpine`.
- **D-20**: Everything in English. Git commits carry no Claude/AI co-author or attribution lines.

### Claude's Discretion

- How the 75% coverage gate passes on a near-empty codebase (e.g. a minimal settings module and app factory with real tests) — but it must pass honestly, without `# pragma: no cover` abuse or lowering the threshold.
- Exact Makefile recipe bodies, pre-commit hook revisions, CI job layout/caching.
- Whether the dockerized test command uses a dedicated Dockerfile stage or a compose profile.
- `.gitignore` / `.dockerignore` contents.
- Creating the public GitHub repository is outward-facing: the plan must mark that step as requiring explicit user confirmation (`autonomous: false`); everything else is autonomous.

### Deferred Ideas (OUT OF SCOPE)

- `/health` endpoint and docker-compose API+DB orchestration — Phase 3 (after the error contract).
- README — Phase 7 (a minimal placeholder is acceptable earlier if CI badges need a home).
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FND-01 | Python 3.13 + FastAPI with `src/taskmanager/` layout | §"src-layout mechanics with plain pip" — verified `pyproject.toml` + `pip install -e .`; §"Environment Availability" for the 3.13-vs-3.14 host skew |
| FND-02 | Exact-pinned `requirements.txt` / `requirements-dev.txt`, plain pip | §"Standard Stack" (versions re-verified on PyPI today); §"Package Legitimacy Audit" (28/28 clean) |
| FND-03 | `.flake8` black-compatible, flake8 passes clean | §"Code Examples → `.flake8`" — corrected `extend-exclude`; Pitfall 5 (`exclude` replaces defaults) |
| FND-04 | black + isort (`profile = black`), `--check` passes | §"Code Examples → `pyproject.toml`"; hook order isort → black → flake8 |
| FND-05 | `pytest.ini` holds all pytest config incl. `filterwarnings = error` | §"`filterwarnings = error` interactions" — verified zero warnings with the pinned stack |
| FND-06 | Coverage over the real package, tests excluded, fails under 75% | §"Making 75% pass honestly" — verified 18 statements / 100% / gate fires at 56% |
| FND-07 | mypy strict over `src/`, passes | §"mypy strict + pydantic-settings" — the `pydantic.mypy` plugin is mandatory; verified |
| FND-08 | pre-commit runs black, isort, flake8, mypy | §"pre-commit: mirrors vs local hooks" — recommended split, with the plugin trap |
| FND-09 | `Makefile` one-word targets | §"Makefile on GNU Make 3.81" — `.ONESHELL` unsupported, verified |
| FND-10 | GitHub Actions: lint, typecheck, arch, tests + coverage vs Postgres service | §"GitHub Actions job layout" — action tags and `postgres:18-alpine` verified today |
| FND-11 | pydantic-settings from env, no production default, `.env.example` | §"Code Examples → settings.py" — verified module, 100% covered by 3 tests |
| ARC-01 | Four layer packages under `src/taskmanager/` | §"Recommended Project Structure" |
| ARC-03 | import-linter contracts in pytest and CI | §"import-linter: three ways the gate can silently pass" — **critical**, the recipe in ARCHITECTURE.md is a verified no-op |
| DOCK-01 | Multistage Dockerfile, non-root | §"Code Examples → Dockerfile" — built and run: `whoami` → `app`, 285 MB |
| DOCK-04 | One documented command runs the tests with no host Python | §"Dockerized test command" — `docker build --target test` + `docker run`, verified green |
| AIW-03 | `AI_WORKFLOW.md` incident log opened with real entries | §"Documentation artifacts" — the two real incidents are already known (D-18) |
| AIW-04 | `CLAUDE.md` holds the rules; `.planning/` committed and consistent | §"Documentation artifacts" |
</phase_requirements>

---

## Project Constraints (from CLAUDE.md)

Actionable directives extracted from `./CLAUDE.md` that the plan must honour:

| Directive | Source section | Consequence for Phase 1 |
|-----------|----------------|-------------------------|
| Everything in English — code, docs, commits, planning artifacts | Project → Constraints | Every file this phase creates is English-only |
| No Claude/AI co-author or attribution lines in commits | Project → Constraints | Commit messages carry no trailer; AI usage is documented in `AI_WORKFLOW.md` instead |
| `pytest.ini`, `.flake8`, `Dockerfile`, `docker-compose.yml`, `README.md`, `DECISION_LOG.md` must exist as literal files | Project → Constraints | Phase 1 owns `pytest.ini`, `.flake8`, `Dockerfile`, `DECISION_LOG.md`; compose and README are Phase 3 / Phase 7 |
| Coverage ≥ 75%, enforced automatically | Project → Constraints | `--cov-fail-under=75` lives in `pytest.ini` addopts so *every* invocation is gated |
| Tech stack fixed: Python, FastAPI, pytest, flake8, black, Docker | Project → Constraints | No ruff, no poetry/uv as the source of truth |
| Reviewability: one-command startup and one-command test run | Project → Constraints | Every gate is one word behind `make` |
| Stack section pins exact versions (FastAPI 0.141.1, pytest 9.1.1, …) | Technology Stack | Reuse verbatim; §"Standard Stack" re-confirms them against PyPI today |
| GSD workflow enforcement: file edits happen through a GSD command | GSD Workflow Enforcement | Execution happens via `/gsd:execute-phase`; this research file writes nothing else |
| Conventions / Architecture sections are empty placeholders | Conventions, Architecture | No pre-existing code conventions to inherit — this phase *establishes* them |

---

## Summary

Phase 1 has no product logic, so the only thing that can go wrong is a gate that **looks** enforced but is not. Three such gates were found and proven to be silent no-ops with the exact pinned toolchain, and all three would have shipped if the plan had followed `.planning/research/` verbatim. The most serious is the architecture test: `subprocess.run([sys.executable, "-m", "importlinter.cli", "lint-imports"])` — the recipe written in `.planning/research/ARCHITECTURE.md:792` — **always exits 0**, including with a deliberate `from fastapi import FastAPI` inside `taskmanager/domain/` `[VERIFIED: local execution]`. `importlinter/cli.py` has no `if __name__ == "__main__"` guard and there is no `importlinter/__main__.py`, so `python -m` imports the module and exits cleanly without running anything. Use the documented Python API (`importlinter.application.use_cases.lint_imports() -> bool`) inside pytest and the `lint-imports` console script in the Makefile, CI and pre-commit — both were verified to go red on a violation and green when it is removed. A second silent-pass mode: a config file with zero contracts reports "0 kept, 0 broken" and exits 0, so the test file must also assert that the expected contracts are actually configured. A third: `.flake8`'s `exclude =` replaces flake8's built-in exclude list exactly the way `ignore =` replaces pycodestyle's — use `extend-exclude`.

The remaining open questions the project-level research left unsettled now have executed answers. The src layout works with plain pip through a nine-line `[build-system]`/`[project]` block in `pyproject.toml` plus `pip install -e .`; that single mechanism satisfies pytest, coverage (un-imported modules *do* appear in the denominator), mypy, and import-linter's `root_package` at once, with `pythonpath = src` in `pytest.ini` as a belt-and-braces fallback so a bare `pytest` works on a fresh checkout. `mypy --strict` over a pydantic-settings module **requires** `plugins = ["pydantic.mypy"]`; without it you get six spurious `call-arg` errors, and with it the reflexive `# type: ignore[call-arg]` becomes an `unused-ignore` error. `filterwarnings = error` is completely clean on pytest 9.1.1 + pytest-asyncio 1.4.0 + pytest-cov 7.1.0 + pydantic 2.13.5 + FastAPI 0.141.1 — no targeted ignores are needed — provided `asyncio_default_fixture_loop_scope` is set (locked to `function`). The 75 % gate passes honestly with two real modules and six real tests: `infrastructure/config/settings.py` and `main.py` total 18 statements at 100 %, and the empty layer `__init__.py` files contribute zero statements, so they neither help nor hurt.

The host is CPython 3.14.3 with no 3.13, Docker 29.2.0 and GNU Make 3.81. Every pinned runtime and dev dependency resolves to a prebuilt wheel on macOS arm64 / cp314 — no source builds — and the entire gate runs green on 3.14 `[VERIFIED: local execution]`. The recommendation is therefore a host venv on 3.14 for the sub-second inner loop, with `python:3.13-slim-trixie` as the source of truth for CI and delivery; `requires-python = ">=3.13"` (never `==3.13.*`) keeps both installable, and `mypy python_version = "3.13"` plus `black target-version = ["py313"]` keep the *analysis* target at 3.13 regardless of which interpreter runs the tools. Note GNU Make 3.81 silently ignores `.ONESHELL`, so every recipe line must be self-contained.

**Primary recommendation:** Build the phase in this order — packaging skeleton (`pyproject.toml` + `src/taskmanager/` + `pip install -e .`) → `.flake8` / `pytest.ini` / `pyproject.toml` tool config → the two real modules and their tests (this is what makes 75 % honest) → `.importlinter` + the pytest architecture test using the **Python API** → red/green demonstration → pre-commit → Makefile → Dockerfile (`builder` / `runtime` / `test` stages) → GitHub Actions → `CLAUDE.md` / `AI_WORKFLOW.md` / `DECISION_LOG.md`. Never invoke import-linter as `python -m importlinter.cli`.

---

## Architectural Responsibility Map

Phase 1 delivers no request-serving tiers, so the tiers here are the **enforcement tiers** of the quality pipeline. Assigning each gate to exactly one owner is what stops the same rule from being configured three times and drifting.

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Code formatting (black, isort) | Developer workstation (pre-commit) | CI (`--check` mode) | Formatters must rewrite before commit; CI only verifies, never fixes |
| Style linting (flake8 + plugins) | Developer workstation (pre-commit) | CI | File-scoped, fast, isolated env is safe |
| Static typing (mypy strict) | Project venv (`make typecheck`) | pre-commit `local` hook, CI | Whole-program analysis — must see the *real* installed environment and the pydantic plugin |
| Architecture boundaries (import-linter) | pytest suite (Python API) | `make arch`, pre-commit `local` hook, CI step | The brief's "next level" item demands it be an automated **test**; CI step exists so failures are readable in the job log |
| Coverage threshold | `pytest.ini` addopts | CI (same command) | Encoding it in addopts makes every invocation — local, Docker, CI — gated identically |
| Dependency resolution / pinning | `requirements*.txt` | `pyproject.toml` `[project]` (metadata only, **no** `dependencies` key) | One source of truth for versions; `pyproject.toml` only makes the package importable |
| Package importability (src layout) | `pip install -e .` | `pythonpath = src` in `pytest.ini` | Editable install serves every tool; `pythonpath` keeps a bare `pytest` working on a fresh clone |
| Runtime image contents | `Dockerfile` `runtime` stage | `.dockerignore` | Non-editable install into `/opt/venv`; no `src/`, no tests, no caches |
| Test execution without host Python | `Dockerfile` `test` stage | Phase 3: compose `test` service | A stage needs no compose file, which does not exist until Phase 3 |
| Secret handling | Environment via pydantic-settings | `.env.example` (documentation), `.gitignore` / `.dockerignore` (`.env`) | No default value means the app refuses to boot misconfigured |

---

## Standard Stack

Versions are **reused verbatim from `.planning/research/STACK.md`** per the phase brief (do not re-derive). Every version below was nonetheless re-queried against the PyPI JSON API on 2026-09-17 while writing this file, and all of them are still `info.version` (i.e. current latest). Additionally, every one of them was installed together into a single virtualenv without a resolver conflict `[VERIFIED: local execution]`.

### Core (Phase 1 actually imports these)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | `3.13` (image `python:3.13-slim-trixie`) | Runtime | Locked D-01. Image resolves to Python 3.13.15 `[VERIFIED: local execution]` |
| fastapi | `0.141.1` | App factory in `main.py` | Brief-mandated; `create_app()` is the composition root Phase 3+ extends |
| pydantic | `2.13.5` | Typed boundaries | Brief-mandated "strong typing with Pydantic" |
| pydantic-settings | `2.15.0` | 12-factor settings (FND-11) | `BaseSettings` fails fast at boot on a missing secret |
| setuptools | `>=77` (build backend only) | Makes `src/taskmanager` an installable package | Only build backend that needs no extra host tooling; ships with every venv |

### Development / gating tools

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | `9.1.1` | Test runner (FND-05) | Every gate run |
| pytest-asyncio | `1.4.0` | `asyncio_mode = auto` | Required now so Phase 3+ async tests need no markers |
| pytest-cov | `7.1.0` | `--cov-fail-under=75` (FND-06) | The mechanical coverage gate |
| coverage | `7.16.1` (transitive) | Measurement engine | Pulled by `pytest-cov`; do not pin separately |
| black | `26.5.1` | Formatter (FND-04) | `make format` / `--check` in CI |
| isort | `9.0.1` | Import ordering (FND-04) | Always before black |
| flake8 | `7.3.0` | Linter (FND-03) | `.flake8` is the literal config file |
| flake8-bugbear | `26.9.9` | B0xx real-bug checks | Provides `extend-immutable-calls` for FastAPI `Depends()` |
| flake8-comprehensions | `3.17.0` | C4xx | Zero false positives |
| pep8-naming | `0.15.1` | N8xx | Cheap discipline signal |
| mypy | `2.3.1` | `strict = true` (FND-07) | Requires the pydantic plugin — see Pitfall 4 |
| import-linter | `2.15` | Architecture contracts (ARC-03) | Config in `.importlinter`; pulls `grimp 3.17`, `rich>=14.2.0` |
| pre-commit | `4.6.2` | Local gate (FND-08) | Hook revs verified live today |

### Runtime dependencies pinned now but first imported later

`uvicorn[standard]==0.53.0`, `SQLAlchemy[asyncio]==2.0.54`, `psycopg[binary]==3.3.5`, `alembic==1.20.0`, `PyJWT==2.14.0`, `pwdlib[argon2]==0.3.1`, `python-multipart==0.0.32`, `email-validator==2.3.0`, plus `httpx==0.28.1` in dev. Pinning them in Phase 1 means the Dockerfile and CI cache key never change shape later. All nine resolve to wheels on macOS arm64 / cp314 with **no source builds** `[VERIFIED: local execution]`.

> **Do not** add these to `[project.dependencies]` in `pyproject.toml`. Leave that key absent so `pip install -e .` installs *only* the local package and `requirements*.txt` stays the single source of truth for versions (D-03).

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `pip install -e .` + `[build-system]` | `pythonpath = src` in `pytest.ini` alone | Works for pytest and (with `mypy_path`) mypy, but `lint-imports` then needs `PYTHONPATH=src` exported in every Makefile target, CI step and pre-commit hook `[VERIFIED: local execution]`. More moving parts, more places to forget it |
| `.importlinter` (INI) | `[tool.importlinter]` in `pyproject.toml` | Both fully supported. `.importlinter` is the form in STACK.md and the one an evaluator finds instantly; `pyproject.toml` is the form in ARCHITECTURE.md. **Conflict — see Open Question 1** |
| import-linter Python API in the test | `subprocess.run(["lint-imports"])` | Console script exits 1 correctly `[VERIFIED: local execution]`, but resolving the script path portably inside a venv is fiddlier than a two-line API call, and the API gives a real `bool` |
| Dedicated `test` Dockerfile stage | compose profile | Compose does not exist until Phase 3; a stage works today and Phase 3 can add a `test` service that reuses `target: test` |
| mypy via `pre-commit/mirrors-mypy` | `local` hook, `language: system` | Mirror gives pinned isolation but needs `pydantic`, `pydantic-settings` **and** `pytest` duplicated into `additional_dependencies`, which drifts from `requirements-dev.txt`. See §"pre-commit" |
| Host venv on Python 3.14 | Everything through Docker | Docker-only is purer but turns a 0.3 s test loop into a ~10 s one. Recommendation: both, with Docker authoritative |

**Installation:**

```bash
# Host inner loop (macOS, CPython 3.14.3 — verified)
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -U pip
pip install -r requirements-dev.txt
pip install -e .
pre-commit install
```

**Version verification:** every package above was re-queried on `https://pypi.org/pypi/<name>/json` on 2026-09-17 and is the current `info.version`. `coverage 7.16.1` (2026-09-13) and `grimp 3.17` (2026-09-04) are the transitive versions actually resolved `[VERIFIED: local execution]`.

---

## Package Legitimacy Audit

`slopcheck` was installed and run against every package this phase installs, on the `pypi` ecosystem.

```
slopcheck install pytest pytest-asyncio pytest-cov coverage black isort flake8 \
  flake8-bugbear flake8-comprehensions pep8-naming mypy import-linter pre-commit \
  fastapi pydantic pydantic-settings setuptools
  → scanned 17 packages, 17 OK

slopcheck install uvicorn SQLAlchemy psycopg alembic PyJWT pwdlib \
  python-multipart email-validator httpx greenlet argon2-cffi
  → scanned 11 packages, 11 OK
```

| Package | Registry | Age (first release) | Source Repo | slopcheck | Disposition |
|---------|----------|---------------------|-------------|-----------|-------------|
| pytest 9.1.1 | PyPI | 2010-11-25 | github.com/pytest-dev/pytest | [OK] | Approved |
| pytest-asyncio 1.4.0 | PyPI | 2015-04-11 | github.com/pytest-dev/pytest-asyncio | [OK] | Approved |
| pytest-cov 7.1.0 | PyPI | 2010-04-25 | pytest-dev/pytest-cov | [OK] | Approved |
| coverage 7.16.1 | PyPI | 2009-05-16 | github.com/coveragepy/coveragepy | [OK] | Approved (transitive) |
| black 26.5.1 | PyPI | 2018-03-14 | github.com/psf/black | [OK] | Approved |
| isort 9.0.1 | PyPI | 2013-12-07 | github.com/PyCQA/isort | [OK] | Approved |
| flake8 7.3.0 | PyPI | 2010-08-12 | github.com/pycqa/flake8 | [OK] | Approved |
| flake8-bugbear 26.9.9 | PyPI | 2016-04-13 | github.com/PyCQA/flake8-bugbear | [OK] | Approved |
| flake8-comprehensions 3.17.0 | PyPI | 2016-04-05 | github.com/adamchainz/flake8-comprehensions | [OK] | Approved |
| pep8-naming 0.15.1 | PyPI | 2013-02-22 | github.com/PyCQA/pep8-naming | [OK] | Approved |
| mypy 2.3.1 | PyPI | 2009-09-09 | github.com/python/mypy | [OK] | Approved |
| import-linter 2.15 | PyPI | 2019-01-27 | github.com/seddonym/import-linter | [OK] | Approved |
| grimp 3.17 | PyPI | 2018-12-10 | github.com/seddonym/grimp | [OK] | Approved (transitive) |
| pre-commit 4.6.2 | PyPI | 2014-06-17 | github.com/pre-commit/pre-commit | [OK] | Approved |
| fastapi 0.141.1 | PyPI | 2018-12-08 | github.com/fastapi/fastapi | [OK] | Approved |
| pydantic 2.13.5 | PyPI | 2017-05-31 | github.com/pydantic/pydantic | [OK] | Approved |
| pydantic-settings 2.15.0 | PyPI | 2023-06-26 | github.com/pydantic/pydantic-settings | [OK] | Approved |
| setuptools >=77 | PyPI | 2006-05-12 | github.com/pypa/setuptools | [OK] | Approved (build backend) |
| uvicorn, SQLAlchemy, psycopg, alembic, PyJWT, pwdlib, python-multipart, email-validator, httpx, greenlet, argon2-cffi | PyPI | all pre-2024 | all with public repos | [OK] | Approved (pinned now, imported in Phases 3-5) |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

No `postinstall`-equivalent risk applies (PyPI wheels, no setup.py execution for any of the above — all ship built wheels). No `checkpoint:human-verify` task is required before install.

---

## Architecture Patterns

### System Architecture Diagram — the Phase 1 gate pipeline

```
 SOURCE OF CHANGE
 ────────────────
  developer / agent edits a file under src/ or tests/
            │
            ▼
 ┌──────────────────────── LOCAL GATE (pre-commit, on `git commit`) ─────────────────────────┐
 │                                                                                            │
 │  isort ──rewrites──▶ black ──rewrites──▶ flake8 ──reads──▶ (file-scoped, isolated envs)   │
 │                                   │                                                        │
 │                                   ├──▶ mypy  (local hook, language: system, whole tree)    │
 │                                   └──▶ lint-imports (local hook, whole graph)              │
 │                                                                                            │
 │  any hook non-zero ──▶ COMMIT REFUSED                                                      │
 └───────────────────────────────────────────┬────────────────────────────────────────────────┘
                                             │ commit created
                   ┌─────────────────────────┼──────────────────────────┐
                   ▼                         ▼                          ▼
        ┌────────────────────┐   ┌───────────────────────┐   ┌──────────────────────────┐
        │  make lint/format/ │   │  make test            │   │  make docker-test        │
        │  typecheck/arch    │   │  (host venv, py3.14)  │   │  (image, py3.13)         │
        │  (host venv)       │   │      │                │   │      │                   │
        └────────┬───────────┘   └──────┼────────────────┘   └──────┼───────────────────┘
                 │                      │                           │
                 │                      ▼                           ▼
                 │        ┌──────────────────────────────────────────────────────┐
                 │        │  pytest (pytest.ini is the single source of truth)    │
                 │        │   ├─ tests/unit/           settings + app factory     │
                 │        │   ├─ tests/architecture/   importlinter Python API    │
                 │        │   └─ coverage: source=taskmanager, fail-under=75      │
                 │        └───────────────────────┬──────────────────────────────┘
                 │                                │
                 └────────────────┬───────────────┘
                                  │ git push
                                  ▼
 ┌──────────────────────── CI GATE (GitHub Actions, every push) ─────────────────────────────┐
 │  checkout ─▶ setup-python 3.13 (+pip cache) ─▶ pip install -r requirements-dev.txt        │
 │           ─▶ pip install -e .                                                             │
 │           ─▶ black --check ─▶ isort --check-only ─▶ flake8 ─▶ mypy ─▶ lint-imports        │
 │           ─▶ pytest (coverage gate)                                                       │
 │                                    ▲                                                      │
 │                          service: postgres:18-alpine ── pg_isready -h 127.0.0.1 ──┘       │
 │                          (unused by Phase 1 tests; proves the wiring for Phase 3)         │
 │  any step non-zero ──▶ RED BADGE                                                          │
 └───────────────────────────────────────────────────────────────────────────────────────────┘

 IMAGE PIPELINE (Dockerfile)
   builder  ── venv at /opt/venv, requirements.txt, pip install --no-deps .
      │
      ├──▶ runtime  ── COPY /opt/venv only, USER app (non-root), no src/, no tests   [DOCK-01]
      └──▶ test     ── + requirements-dev.txt, pip install -e ., COPY tests + configs [DOCK-04]
                       CMD ["pytest"]
```

Every arrow above was executed end-to-end at least once while writing this document, except the GitHub Actions box (no repository exists yet).

### Recommended Project Structure (end of Phase 1)

```
taskmanager/
├── src/
│   └── taskmanager/
│       ├── __init__.py
│       ├── main.py                      # create_app() — composition root, top layer
│       ├── domain/__init__.py           # empty (Phase 2)
│       ├── application/__init__.py      # empty (Phase 2)
│       ├── infrastructure/
│       │   ├── __init__.py
│       │   └── config/
│       │       ├── __init__.py
│       │       └── settings.py          # pydantic-settings  [FND-11]
│       └── presentation/__init__.py     # empty (Phase 3)
├── tests/
│   ├── __init__.py
│   ├── architecture/
│   │   ├── __init__.py
│   │   └── test_layer_boundaries.py     # import-linter, Python API   [ARC-03]
│   └── unit/
│       ├── __init__.py
│       ├── test_settings.py
│       └── test_app_factory.py
├── .github/workflows/ci.yml             # [FND-10]
├── .flake8                              # literal file  [FND-03]
├── pytest.ini                           # literal file  [FND-05]
├── .importlinter                        # [ARC-03]
├── .pre-commit-config.yaml              # [FND-08]
├── pyproject.toml                       # packaging + black/isort/mypy/coverage  [FND-04/06/07]
├── requirements.txt                     # [FND-02]
├── requirements-dev.txt                 # [FND-02]
├── Makefile                             # [FND-09]
├── Dockerfile                           # multistage, non-root  [DOCK-01/04]
├── .dockerignore
├── .gitignore
├── .env.example                         # [FND-11]
├── CLAUDE.md                            # + project rules section  [AIW-04]
├── AI_WORKFLOW.md                       # skeleton + real incident log  [AIW-03]
└── DECISION_LOG.md                      # ADR-style  [D-19]
```

`README.md` is Phase 7; create an empty placeholder only if the CI badge needs a home (allowed by CONTEXT). `docker-compose.yml`, `migrations/`, `alembic.ini` are Phase 3.

---

### Pattern 1: src layout with plain pip — what actually makes `taskmanager` importable

**What:** a nine-line packaging block in `pyproject.toml`, installed once with `pip install -e .`. That single mechanism serves pytest, coverage, mypy and import-linter simultaneously.

**Why it beats the alternatives:** `lint-imports` resolves `root_package` by *importing* the package. Without an install it prints `Could not find package 'taskmanager' in your Python path.` and exits 1 unless `PYTHONPATH=src` is exported — which would then have to be repeated in the Makefile, in every CI step and in every pre-commit hook `[VERIFIED: local execution]`.

```toml
[build-system]
requires = ["setuptools>=77"]
build-backend = "setuptools.build_meta"

[project]
name = "taskmanager"
version = "0.1.0"
description = "Task Manager API — Crehana Backend Technical Challenge"
requires-python = ">=3.13"      # NOT "==3.13.*" — the host runs 3.14

[tool.setuptools.packages.find]
where = ["src"]
```

**Interaction matrix** (all rows `[VERIFIED: local execution]`):

| Tool | How it finds the package | Config needed |
|------|--------------------------|---------------|
| pytest | editable install; `pythonpath = src` also works standalone | `pythonpath = src` in `pytest.ini` (optional safety net) |
| coverage | `--cov=taskmanager` (package name, not a path) | `[tool.coverage.run] source = ["taskmanager"]` |
| mypy | `mypy_path = "src"` — works even with the package uninstalled | `mypy_path`, `packages = ["taskmanager"]` |
| import-linter | imports `taskmanager` from `sys.path` | `root_package = taskmanager` in `.importlinter` |
| Docker `runtime` | `pip install --no-deps .` → `/opt/venv/lib/.../site-packages/taskmanager` | none |
| Docker `test` | `pip install --no-deps -e .` → paths stay `src/taskmanager/...` | none |

**Hard rule:** any environment that runs the test suite installs the package **editable**. A non-editable install combined with `pythonpath = src` puts two copies of the code on `sys.path` and splits the coverage report between them.

**Side effect to gitignore/dockerignore:** the editable install creates `src/taskmanager.egg-info/` and `.venv/lib/.../__editable__.taskmanager-0.1.0.pth` `[VERIFIED: local execution]`.

---

### Pattern 2: the architecture contract as a real test

**What:** `.importlinter` at repo root, contracts executed inside pytest through import-linter's documented Python API, plus the `lint-imports` console script in Makefile / CI / pre-commit so failures are readable in a job log.

**Contracts** (layer order high → low; `include_external_packages` is required for `forbidden` contracts that name third-party distributions):

```ini
# .importlinter
[importlinter]
root_package = taskmanager
include_external_packages = True

[importlinter:contract:layers]
name = Layered architecture (high to low)
type = layers
layers =
    taskmanager.main
    taskmanager.presentation
    taskmanager.infrastructure
    taskmanager.application
    taskmanager.domain

[importlinter:contract:domain-framework-free]
name = Domain is framework-free
type = forbidden
source_modules =
    taskmanager.domain
forbidden_modules =
    fastapi
    starlette
    sqlalchemy
    alembic
    pydantic
    pydantic_settings
    jwt
    pwdlib
    httpx

[importlinter:contract:application-framework-free]
name = Application knows no web framework or ORM
type = forbidden
source_modules =
    taskmanager.application
forbidden_modules =
    fastapi
    starlette
    sqlalchemy
    alembic
    jwt
    pwdlib
```

`pydantic` is forbidden in `domain` (D-02/ARC-02: stdlib dataclasses only) but **allowed** in `application` (DTOs are Pydantic — ARC-05). A fourth contract restricting `presentation.api.routers` / `.schemas` from importing `infrastructure` is proposed in ARCHITECTURE.md; it references modules that do not exist until Phase 3, so add it in Phase 3, not now — import-linter errors on unresolvable `source_modules`.

**The test** (verified red on a violation, green when removed):

```python
# tests/architecture/test_layer_boundaries.py
"""The architecture contract, executed as part of the normal test suite."""

from importlinter import api
from importlinter.application import use_cases

EXPECTED_CONTRACT_NAMES = {
    "Layered architecture (high to low)",
    "Domain is framework-free",
    "Application knows no web framework or ORM",
}


def test_every_contract_is_configured() -> None:
    config = api.read_configuration()
    assert config["session_options"]["root_packages"] == ["taskmanager"]
    assert {c["name"] for c in config["contracts_options"]} == EXPECTED_CONTRACT_NAMES


def test_import_contracts_hold() -> None:
    assert use_cases.lint_imports(no_logo=True) is True
```

`test_every_contract_is_configured` is not ceremony: a `.importlinter` containing only the `[importlinter]` header reports "Contracts: 0 kept, 0 broken" and exits **0** `[VERIFIED: local execution]`.

**The red/green demonstration** (success criterion 2 of the phase):

```bash
printf 'from fastapi import FastAPI\n\n__all__ = ["FastAPI"]\n' > src/taskmanager/domain/_violation.py
pytest tests/architecture -q            # -> 1 failed: "taskmanager.domain is not allowed to import fastapi"
lint-imports;  echo $?                  # -> 1
rm src/taskmanager/domain/_violation.py
pytest tests/architecture -q            # -> 2 passed
lint-imports;  echo $?                  # -> 0
```

Record the actual terminal output of this sequence in `AI_WORKFLOW.md` / `DECISION_LOG.md` — it is the evidence that the gate is real, and it costs thirty seconds.

---

### Pattern 3: an honest 75 % on a codebase with no features

**What:** ship exactly two real modules and test both to 100 %. The empty layer `__init__.py` files contain zero statements, and coverage reports zero-statement files at 100 % — they neither inflate nor deflate the number `[VERIFIED: local execution]`.

Measured result of the verified scaffold:

```
Name                                                Stmts   Miss Branch BrPart  Cover
src/taskmanager/__init__.py                             0      0      0      0   100%
src/taskmanager/application/__init__.py                 0      0      0      0   100%
src/taskmanager/domain/__init__.py                      0      0      0      0   100%
src/taskmanager/infrastructure/__init__.py              0      0      0      0   100%
src/taskmanager/infrastructure/config/__init__.py       0      0      0      0   100%
src/taskmanager/infrastructure/config/settings.py      13      0      0      0   100%
src/taskmanager/main.py                                 5      0      0      0   100%
src/taskmanager/presentation/__init__.py                0      0      0      0   100%
TOTAL                                                  18      0      0      0   100%
Required test coverage of 75% reached. Total coverage: 100.00%
```

The gate was then proven to *fire*: adding a 12-statement module that no test imports dropped the total to **56.25 %** and pytest exited non-zero with `FAIL Required test coverage of 75% not reached` `[VERIFIED: local execution]`. That un-imported module appearing in the denominator at all is the direct payoff of `source = ["taskmanager"]` (PITFALLS Pitfall 6).

**Rules that keep it honest:**
- No `# pragma: no cover` anywhere in this phase.
- No `omit` entries beyond `*/migrations/*` (added in Phase 3; migrations are not application code).
- No `if __name__ == "__main__":` block in `main.py` — it would be a permanently uncovered statement. The container runs `uvicorn --factory taskmanager.main:create_app`.
- No `/health` route (Phase 3, per CONTEXT deferred list).
- Six tests is the right order of magnitude: three for settings (happy path, missing secret, too-short secret), one for the `lru_cache`, one for the app factory, one architecture pair. Each asserts on a **value**, never just "it didn't raise".

---

### Pattern 4: the composition root that does not need a database

```python
# src/taskmanager/main.py
"""Composition root: builds the FastAPI application."""

from fastapi import FastAPI

from taskmanager.infrastructure.config.settings import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()
    return FastAPI(
        title=resolved.app_name,
        version="0.1.0",
        openapi_url="/openapi.json",
    )
```

The optional `settings` parameter is what lets tests build an app without touching the process environment, and it is the seam Phase 3 uses to inject a test engine. `create_app` is a factory, not a module-level `app = create_app()` — a module-level instance would evaluate settings at import time and make `import taskmanager.main` crash in any environment without `JWT_SECRET`, including mypy's and import-linter's.

`create_app()` satisfies the `taskmanager.main` layer of the import-linter contract from day one: it imports `infrastructure` (allowed, downward) and nothing imports it.

---

### Anti-Patterns to Avoid

- **`python -m importlinter.cli lint-imports` in a test.** Always exits 0. See Pitfall 1 — this is the single most damaging thing that could ship in this phase.
- **`ignore =` in `.flake8`.** Replaces pycodestyle's `DEFAULT_IGNORE = E121,E123,E126,E226,E24,E704,W503,W504` `[VERIFIED: local execution]`, silently re-enabling checks black's output violates.
- **`exclude =` in `.flake8`.** Same trap, one level up: replaces flake8's `('.svn','CVS','.bzr','.hg','.git','__pycache__','.tox','.nox','.eggs','*.egg')` `[VERIFIED: local execution]`. Use `extend-exclude`.
- **`[tool.pytest.ini_options]` in `pyproject.toml`.** Silently ignored while `pytest.ini` exists.
- **`# type: ignore[call-arg]` on `Settings()`.** With the pydantic mypy plugin loaded this becomes an `unused-ignore` error under `strict = true` `[VERIFIED: local execution]`.
- **`dependencies = [...]` in `[project]`.** Duplicates `requirements*.txt` and creates two version sources.
- **`.ONESHELL:` in the Makefile.** GNU Make 3.81 (the macOS default, and this host) silently ignores it: `cd /tmp` followed by `pwd` printed the *original* directory `[VERIFIED: local execution]`.
- **`--cov=.` or bare `--cov`.** Counts `tests/` toward the number.
- **Lowering `--cov-fail-under` or adding `omit` to reach 75 %.** The visible, unrecoverable version of the mistake (PITFALLS Pitfall 6).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Layer-boundary enforcement | An `ast`-walking test that collects `Import`/`ImportFrom` nodes per file (PITFALLS Pitfall 9 sketches one) | `import-linter` 2.15 with `layers` + `forbidden` contracts | A hand-rolled AST walker sees only *direct* imports in the files it visits; grimp builds the full transitive graph, catches `taskmanager.domain → x → sqlalchemy`, understands packages vs modules, and handles `if TYPE_CHECKING` via `exclude_type_checking_imports`. The hand-rolled version is ~60 lines that quietly under-report |
| Settings loading / validation | `os.environ.get("JWT_SECRET", "changeme")` + manual casting | `pydantic-settings` `BaseSettings` with no default on secrets | A default *is* the vulnerability (PITFALLS Security Mistakes row 1). BaseSettings also gives type coercion, `min_length`, `extra="forbid"` and a single readable `ValidationError` listing every missing variable |
| Coverage threshold checking | Parsing `coverage report` output in the Makefile | `--cov-fail-under=75` in `pytest.ini` addopts | Encoding it in addopts means local, Docker and CI runs are gated by the same bytes; a Makefile-only check is bypassed by anyone typing `pytest` |
| "Is the package importable?" plumbing | `sys.path.insert(0, "src")` in `conftest.py` | `pip install -e .` (+ optional `pythonpath = src`) | A `conftest.py` hack fixes pytest and nothing else — mypy, import-linter and Docker all still break |
| Waiting for Postgres in CI | A bash `until pg_isready` loop | GitHub Actions `services.postgres.options` health flags | The runner blocks on the health check before the first step runs, with no script to maintain |
| Deprecation policing | A grep-based check for `utcnow`, `orm_mode`, `.dict()` | `filterwarnings = error` in `pytest.ini` | Catches every deprecation in every dependency, including ones not yet on any grep list (PITFALLS Pitfall 15) |
| Non-root container user | `RUN chmod 777` on the app directory | `useradd --system --create-home` + `USER app` | Verified: `docker run --rm <image> whoami` → `app` |

**Key insight:** every gate in this phase is a *declarative* artifact. The moment a gate becomes imperative code, it acquires its own bug surface — and a buggy gate is strictly worse than no gate, because it reports green.

---

## Common Pitfalls

### Pitfall 1: The architecture test that always passes — `python -m importlinter.cli`

**What goes wrong:** `tests/architecture/test_layer_boundaries.py` asserts `subprocess.run([sys.executable, "-m", "importlinter.cli", "lint-imports"]).returncode == 0` and passes forever, including with `from fastapi import FastAPI` sitting inside `taskmanager/domain/`.

**Why it happens:** it is the recipe published in this project's own `.planning/research/ARCHITECTURE.md:786-796`. `importlinter/cli.py` has no `if __name__ == "__main__":` guard, and the package has no `__main__.py`, so `python -m importlinter.cli` imports the module (defining the click commands) and exits 0 without invoking anything. `python -m importlinter` fails differently — `No module named importlinter.__main__` — which at least fails loudly, but for the wrong reason.

**Verified evidence:**

```
with a deliberate fastapi import inside taskmanager/domain/:
  lint-imports                                   -> exit 1  (Domain is framework-free BROKEN)
  python -m importlinter.cli lint-imports        -> exit 0  (prints nothing)
  python -m importlinter lint-imports            -> exit 1  ("cannot be directly executed")
```

**How to avoid:** use `importlinter.application.use_cases.lint_imports(no_logo=True) -> bool` in the test (returns `False` on a violation `[VERIFIED: local execution]`) and the `lint-imports` console script everywhere else.

**Warning signs:** the architecture test has never been seen to fail. **The plan must include an explicit red-phase task** that adds a violation, observes the failure, and removes it.

---

### Pitfall 2: The contract file that configures nothing

**What goes wrong:** a typo in a section header (`[importlinter:contracts:layers]` instead of `[importlinter:contract:layers]`) yields a config with zero contracts. import-linter prints `Contracts: 0 kept, 0 broken` and exits **0** `[VERIFIED: local execution]`.

**Why it happens:** import-linter's success condition is "no broken contracts", and vacuously true is true.

**How to avoid:** the guard test in Pattern 2 — assert `read_configuration()` returns exactly the expected contract names and `root_packages == ["taskmanager"]`.

**Warning signs:** `lint-imports` output that never mentions the contract names. Note the contrasting, *loud* failure modes that do work correctly: no config file at all → `Could not read any configuration.` exit 1; package not importable → `Could not find package 'taskmanager' in your Python path.` exit 1.

---

### Pitfall 3: `exclude` and `ignore` in `.flake8` both replace built-in defaults

**What goes wrong:** the `.flake8` sample in `.planning/research/STACK.md:300-310` uses `exclude = .git,__pycache__,.venv,build,dist,migrations/versions`, which drops `.tox`, `.nox`, `.eggs`, `*.egg`, `.svn`, `CVS`, `.bzr`, `.hg` from flake8's defaults.

**Verified:** `flake8.defaults.EXCLUDE == ('.svn','CVS','.bzr','.hg','.git','__pycache__','.tox','.nox','.eggs','*.egg')`; `pycodestyle.DEFAULT_IGNORE == 'E121,E123,E126,E226,E24,E704,W503,W504'`.

**How to avoid:** `extend-exclude` and `extend-ignore`, never the bare forms. Two further corrections to that same sample:
- `extend-select = B950` contradicts `max-line-length = 88`; black's guide pairs B950 with `max-line-length = 80` + ignoring E501. STACK.md itself says "pick one, do not mix" — pick plain `max-line-length = 88` and drop B950.
- `per-file-ignores = tests/*:S101` references a flake8-bandit code; bandit is not in the stack, so the line is dead configuration an evaluator may read as copy-paste.

---

### Pitfall 4: `mypy --strict` over pydantic-settings without the plugin

**What goes wrong:** `mypy src tests` reports, on a perfectly correct settings module:

```
settings.py:27: error: Missing named argument "database_url" for "Settings"  [call-arg]
settings.py:27: error: Missing named argument "jwt_secret" for "Settings"    [call-arg]
test_settings.py:16: error: Unexpected keyword argument "_env_file" for "Settings"  [call-arg]
```

The reflex fix is `# type: ignore[call-arg]` — which, once the plugin **is** enabled, becomes `error: Unused "type: ignore" comment [unused-ignore]` because `strict = true` implies `warn_unused_ignores`. Both states are verified `[VERIFIED: local execution]`.

**How to avoid:** `plugins = ["pydantic.mypy"]` in `[tool.mypy]`, and **no** `type: ignore` on `Settings()`. With the plugin, `mypy src tests` is `Success: no issues found in 13 source files`.

**Warning signs:** a `# type: ignore` in the settings module. A missing plugin is an unmissable hard failure — `mypy` exits **2** with `Error importing plugin ... [misc]` `[VERIFIED: local execution]` — so it cannot be silently absent, but it *can* be silently absent from a pre-commit hook's isolated environment (see Pitfall 6).

---

### Pitfall 5: `filterwarnings = error` does not police coverage misconfiguration

**What goes wrong:** the team assumes `filterwarnings = error` turns every warning into a failure. Coverage's own warnings are emitted at session teardown, outside pytest's warning-capture scope, and do **not** fail the run:

```
CoverageWarning: Module totally_absent_pkg was never imported. (module-not-imported)
CoverageWarning: No data was collected. (no-data-collected)
CovReportWarning: Failed to generate report: No data to report.
  -> 2 passed
```

`[VERIFIED: local execution]`. The `--cov-fail-under` gate still catches this case (0 % < 75 %), but a *partially* wrong `source` would pass quietly.

**How to avoid:** read the coverage table once, manually, when the gate is first wired, and confirm the file list matches `find src -name '*.py'`. Any `Coverage.py warning:` line in the pytest output is a defect even though the suite is green.

**The good news:** `filterwarnings = error` is otherwise completely clean with the pinned stack. A full run of pytest 9.1.1 + pytest-asyncio 1.4.0 (auto mode) + pytest-cov 7.1.0 + pydantic 2.13.5 + pydantic-settings 2.15.0 + FastAPI 0.141.1 + Starlette 1.6.0 produced **zero** warnings on both Python 3.14.3 and 3.13.15 `[VERIFIED: local execution]`. No targeted `ignore::` entries are needed in Phase 1. Two prerequisites: `asyncio_default_fixture_loop_scope` must be set (unset → deprecation warning → error), and `--strict-config` is safe to add (verified).

---

### Pitfall 6: pre-commit's isolated environments do not contain your dependencies

**What goes wrong:** `pre-commit/mirrors-mypy` installs mypy into its own virtualenv. That env has no `pydantic`, so `plugins = ["pydantic.mypy"]` aborts with exit 2; and no `pytest`, so every `import pytest` in `tests/` becomes `Cannot find implementation or library stub`. The hook then either fails permanently or gets "fixed" by dropping `tests/` from the hook — which quietly stops type-checking half the repo.

**How to avoid (recommended split):**
- **black, isort, flake8** → pinned mirror repos. They are file-scoped, and an isolated environment is exactly what you want for reproducible formatting.
- **mypy, lint-imports** → `repo: local` hooks with `language: system`, `pass_filenames: false`. Both are whole-program tools that must see the real installed environment. This also guarantees the pre-commit run and `make typecheck` / `make arch` execute the *same* command with the *same* versions — no `additional_dependencies` list to drift from `requirements-dev.txt`.

The alternative (mirrors-mypy with `additional_dependencies: [pydantic==2.13.5, pydantic-settings==2.15.0, pytest==9.1.1]`) works but creates a fourth place where versions are pinned; note it in `DECISION_LOG.md` if chosen.

**Warning signs:** a mypy `additional_dependencies` list that has stopped matching `requirements-dev.txt`. A pre-commit mypy hook whose `files:` pattern excludes `tests/`.

---

### Pitfall 7: hook ordering oscillation

**What goes wrong:** pre-commit modifies files on a second consecutive run; `make lint` fails on code `make format` just produced.

**How to avoid:** hook order is **isort → black → flake8 → mypy → lint-imports**, and isort must carry `profile = "black"`. CI runs `--check` / `--check-only` modes only, so CI fails instead of silently rewriting.

**Verification:** `pre-commit run --all-files` twice in a row; the second run must report every hook `Passed` with no file modifications.

---

### Pitfall 8: Makefile assumptions that break on GNU Make 3.81

**What goes wrong:** recipes written as multi-line shell blocks relying on `.ONESHELL:` execute each line in a separate shell. Verified on this host: `.ONESHELL:` + `cd /tmp` + `pwd` printed the *original* working directory, not `/tmp` `[VERIFIED: local execution]`. GNU Make 3.81 (2006) is what ships with macOS; `.ONESHELL` arrived in 3.82.

**How to avoid:** one self-contained command per recipe line, or join with `&&` / `;` on a single line. Declare `.PHONY` for every target. Do not use `$(shell ...)` for anything that must run at recipe time.

Also relevant: the `up` / `down` targets must exist now (D-12) but compose does not arrive until Phase 3. Make them print an explicit, honest message rather than failing obscurely — e.g. `@echo "docker compose lands in Phase 3 — use 'make docker-test' to run the suite in Docker"` — and convert them in Phase 3.

---

### Pitfall 9: host Python 3.13 does not exist on this machine

**What goes wrong:** a plan task says `python3.13 -m venv .venv` and fails immediately: the host has CPython **3.14.3** and no 3.13 `[VERIFIED: local execution]`.

**How to avoid:** `python3 -m venv .venv` (whatever the host has) for the inner loop; `requires-python = ">=3.13"` in `pyproject.toml` so 3.14 satisfies it; `mypy python_version = "3.13"` and `black target-version = ["py313"]` so the *analysis* target stays 3.13; CI and Docker pin 3.13. All of it verified green on 3.14.3.

**Residual risk:** a 3.14-only DeprecationWarning could turn `filterwarnings = error` red locally while CI (3.13) is green, or vice versa. None occurred in the verified run, and CI on 3.13 is authoritative. Record the skew in `DECISION_LOG.md` in one line — it is exactly the kind of small, owned decision the deliverable is graded on.

---

### Pitfall 10: the runtime image is a "multistage" that isn't

**What goes wrong:** a single `FROM` with a `AS builder` label, or a `COPY . .` before `pip install` that invalidates the dependency layer on every code edit, or `.env`/`.git` baked into a layer.

**How to avoid:** three real stages (`builder` → `runtime`, `builder` → `test`), `COPY requirements.txt` before `COPY src`, a `.dockerignore` listing `.git`, `.venv`, `.env`, `__pycache__`, `*.pyc`, `.pytest_cache`, `.mypy_cache`, `.import_linter_cache`, `.coverage`, `coverage.xml`, `htmlcov`, `src/*.egg-info`, `.planning`.

**Verification commands** (all run successfully while writing this):

```bash
docker build --target runtime -t taskmanager .
docker run --rm taskmanager whoami          # -> app        (non-root)
docker run --rm taskmanager python --version # -> Python 3.13.15
docker image ls taskmanager --format '{{.Size}}'  # -> 285MB
docker history taskmanager | grep -i secret       # -> empty
```

285 MB is comfortably under the 500 MB threshold PITFALLS names.

---

### Pitfall 11: `.import_linter_cache` and `src/*.egg-info` polluting the repo and the image

**What goes wrong:** `lint-imports` writes `.import_linter_cache/`, and `pip install -e .` writes `src/taskmanager.egg-info/` `[VERIFIED: local execution]`. Both are easy to miss in `.gitignore` because neither existed before this phase, and both then show up in the evaluator's `git status`.

**How to avoid:** add them to `.gitignore` and `.dockerignore` in the same task that introduces the tool that creates them.

---

## Code Examples

All files below are the exact contents that were executed. Adapt only where noted.

### `pyproject.toml` (packaging + every tool except flake8 and pytest)

```toml
[build-system]
requires = ["setuptools>=77"]
build-backend = "setuptools.build_meta"

[project]
name = "taskmanager"
version = "0.1.0"
description = "Task Manager API — Crehana Backend Technical Challenge"
requires-python = ">=3.13"
# NOTE: no [project.dependencies] — requirements*.txt is the single source of truth (D-03)

[tool.setuptools.packages.find]
where = ["src"]

[tool.black]
line-length = 88
target-version = ["py313"]

[tool.isort]
profile = "black"
line_length = 88
known_first_party = ["taskmanager"]

[tool.mypy]
python_version = "3.13"
strict = true
plugins = ["pydantic.mypy"]
warn_unreachable = true
mypy_path = "src"
packages = ["taskmanager"]

[tool.coverage.run]
source = ["taskmanager"]
branch = true

[tool.coverage.report]
exclude_also = [
    "if TYPE_CHECKING:",
    "raise NotImplementedError",
    "@abstractmethod",
    "\\.\\.\\.",
]
```

`packages = ["taskmanager"]` makes a bare `mypy` check the whole package; passing explicit paths (`mypy src tests`, or pre-commit passing filenames) overrides it without conflict `[VERIFIED: local execution]`. `make typecheck` should be `mypy src tests` so tests are type-checked too.

### `pytest.ini` (brief-mandated literal file)

```ini
[pytest]
testpaths = tests
pythonpath = src
asyncio_mode = auto
asyncio_default_fixture_loop_scope = function
addopts =
    -ra
    --strict-markers
    --strict-config
    --cov=taskmanager
    --cov-report=term-missing
    --cov-report=xml
    --cov-fail-under=75
markers =
    unit: pure domain/application tests, no I/O
    integration: tests that touch PostgreSQL
filterwarnings =
    error
```

`asyncio_default_fixture_loop_scope = function` resolves SUMMARY.md conflict #2 in favour of PITFALLS. `--cov=taskmanager` is the **package name**, not a path — that is what makes un-imported modules appear in the denominator.

### `.flake8` (brief-mandated literal file — corrected)

```ini
[flake8]
max-line-length = 88
extend-ignore = E203,E701
extend-exclude = .venv,build,dist,migrations
extend-immutable-calls = fastapi.Depends,fastapi.Query,fastapi.Path,fastapi.Body,fastapi.Header
max-complexity = 10
```

Verified clean against the scaffold. `extend-immutable-calls` is a flake8-bugbear option (suppresses B008 on FastAPI's `Depends()`); harmless now, essential from Phase 3.

### `src/taskmanager/infrastructure/config/settings.py` (FND-11)

```python
"""Application settings loaded from the environment."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="forbid",
        frozen=True,
    )

    app_name: str = "Task Manager API"
    environment: str = "local"
    database_url: str
    jwt_secret: str = Field(min_length=16)
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = Field(default=30, gt=0)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
```

`database_url` and `jwt_secret` have **no defaults** — a misconfigured process fails at boot, not at first request (D-16). `frozen=True` and `extra="forbid"` are cheap, visible rigour. Do **not** add `# type: ignore[call-arg]` to the `Settings()` call (Pitfall 4).

### `tests/unit/test_settings.py` (the six tests that make 75 % honest)

```python
import pytest
from pydantic import ValidationError

from taskmanager.infrastructure.config.settings import Settings, get_settings
from taskmanager.main import create_app

ENV = {
    "DATABASE_URL": "postgresql+psycopg://u:p@localhost/db",
    "JWT_SECRET": "a" * 32,
}


def test_settings_read_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)
    settings = Settings(_env_file=None)
    assert settings.database_url == ENV["DATABASE_URL"]
    assert settings.jwt_expire_minutes == 30


def test_missing_secret_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", ENV["DATABASE_URL"])
    monkeypatch.delenv("JWT_SECRET", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_short_secret_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", ENV["DATABASE_URL"])
    monkeypatch.setenv("JWT_SECRET", "short")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_get_settings_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    assert get_settings() is get_settings()
    get_settings.cache_clear()


def test_create_app_uses_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)
    app = create_app(Settings(_env_file=None))
    assert app.title == "Task Manager API"
    assert app.openapi()["info"]["version"] == "0.1.0"
```

`_env_file=None` is essential: without it a developer's real `.env` leaks into the test and the "missing secret" cases stop failing. Mypy accepts `_env_file` only because the pydantic plugin is loaded (Pitfall 4). `get_settings.cache_clear()` in both directions prevents the cache leaking into later tests.

### `Dockerfile` (multistage, non-root, plus a test stage) — DOCK-01 / DOCK-04

```dockerfile
# syntax=docker/dockerfile:1

# ---------- Stage 1: builder ----------
FROM python:3.13-slim-trixie AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-deps .

# ---------- Stage 2: runtime ----------
FROM python:3.13-slim-trixie AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

RUN useradd --system --create-home --shell /usr/sbin/nologin app
COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
USER app

EXPOSE 8000
CMD ["uvicorn", "--factory", "taskmanager.main:create_app", \
     "--host", "0.0.0.0", "--port", "8000"]

# ---------- Stage 3: test ----------
FROM builder AS test

COPY requirements-dev.txt ./
RUN pip install -r requirements-dev.txt && pip install --no-deps -e .

COPY pytest.ini .flake8 .importlinter ./
COPY tests ./tests

RUN useradd --system --create-home --shell /usr/sbin/nologin app \
    && chown -R app:app /app /opt/venv
USER app

CMD ["pytest"]
```

Built and run successfully: runtime image 285 MB, `whoami` → `app`, Python 3.13.15; test stage ran the suite to 100 % coverage with the gate satisfied `[VERIFIED: local execution]`.

Two notes for the planner: (a) `pip install --no-deps -e .` in the test stage replaces the non-editable copy the builder installed, so `src/` remains the single source of truth and coverage paths stay `src/taskmanager/...`; (b) `pip install --no-deps .` requires `[project]` in `pyproject.toml` — that is the only reason the packaging block is mandatory in the image.

### Dockerized test command — DOCK-04

```bash
docker build --target test -t taskmanager-test .
docker run --rm taskmanager-test
```

Wrapped as `make docker-test`. Keep this target name stable: Phase 3 replaces the body with `docker compose run --rm test` (a compose service using `target: test` plus `depends_on: db: condition: service_healthy`) without touching any documentation.

### `.github/workflows/ci.yml` — FND-10

```yaml
name: CI

on:
  push:
  pull_request:

jobs:
  quality-gates:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:18-alpine
        env:
          POSTGRES_USER: taskmanager
          POSTGRES_PASSWORD: taskmanager
          POSTGRES_DB: taskmanager_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd "pg_isready -h 127.0.0.1 -U taskmanager -d taskmanager_test"
          --health-interval 5s
          --health-timeout 5s
          --health-retries 10
          --health-start-period 10s

    env:
      DATABASE_URL: postgresql+psycopg://taskmanager:taskmanager@localhost:5432/taskmanager_test
      JWT_SECRET: ci-only-secret-not-a-real-credential

    steps:
      - uses: actions/checkout@v7

      - uses: actions/setup-python@v7
        with:
          python-version: '3.13'
          cache: pip
          cache-dependency-path: |
            requirements.txt
            requirements-dev.txt

      - name: Install dependencies
        run: |
          python -m pip install -U pip
          pip install -r requirements-dev.txt
          pip install -e .

      - name: Format check (black)
        run: black --check src tests

      - name: Import order check (isort)
        run: isort --check-only src tests

      - name: Lint (flake8)
        run: flake8 src tests

      - name: Type check (mypy strict)
        run: mypy src tests

      - name: Architecture contracts (import-linter)
        run: lint-imports

      - name: Tests with coverage gate
        run: pytest
```

Verified today: `actions/checkout@v7.0.1`, `actions/setup-python@v7.0.0` are the current releases; `cache: pip` + multi-line `cache-dependency-path` is the documented pattern in `actions/setup-python/docs/advanced-usage.md`; `postgres:18-alpine` exists on Docker Hub (`docker manifest inspect` succeeded).

The Postgres service is **unused by Phase 1 tests** — FND-10 requires it, and having it green now means Phase 3's integration tests only add a `pytest` marker, not new CI infrastructure. The `-h 127.0.0.1` in the health command is the PITFALLS Pitfall 7 fix (the official image's init-time server listens only on a Unix socket).

`lint-imports` gets its own step so a boundary failure is a named red step in the job log, in addition to being a failing test inside `pytest`.

### `.pre-commit-config.yaml` — FND-08

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v6.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-toml
      - id: check-added-large-files
      - id: check-merge-conflict
      - id: detect-private-key

  - repo: https://github.com/PyCQA/isort
    rev: 9.0.1
    hooks:
      - id: isort

  - repo: https://github.com/psf/black-pre-commit-mirror
    rev: 26.5.1
    hooks:
      - id: black

  - repo: https://github.com/PyCQA/flake8
    rev: 7.3.0
    hooks:
      - id: flake8
        additional_dependencies:
          - flake8-bugbear==26.9.9
          - flake8-comprehensions==3.17.0
          - pep8-naming==0.15.1

  - repo: local
    hooks:
      - id: mypy
        name: mypy (strict)
        entry: mypy
        language: system
        types: [python]
        pass_filenames: false
        args: [src, tests]
      - id: import-linter
        name: import-linter contracts
        entry: lint-imports
        language: system
        pass_filenames: false
        always_run: true
```

All five mirror revs verified against the GitHub tags API today: `pre-commit-hooks v6.0.0`, `isort 9.0.1`, `black-pre-commit-mirror 26.5.1`, `flake8 7.3.0`. (`mirrors-mypy v2.3.1` also exists and is current, if the planner prefers the mirror over the local hook — see Pitfall 6 for the tradeoff.)

### `Makefile` — FND-09

```make
.PHONY: install lint format typecheck arch test docker-test up down

VENV := .venv
PY := $(VENV)/bin/python

install:
	python3 -m venv $(VENV)
	$(PY) -m pip install -U pip
	$(PY) -m pip install -r requirements-dev.txt
	$(PY) -m pip install -e .
	$(VENV)/bin/pre-commit install

format:
	$(VENV)/bin/isort src tests
	$(VENV)/bin/black src tests

lint:
	$(VENV)/bin/black --check src tests
	$(VENV)/bin/isort --check-only src tests
	$(VENV)/bin/flake8 src tests

typecheck:
	$(VENV)/bin/mypy src tests

arch:
	$(VENV)/bin/lint-imports

test:
	$(VENV)/bin/pytest

docker-test:
	docker build --target test -t taskmanager-test .
	docker run --rm taskmanager-test

up:
	@echo "docker compose arrives in Phase 3. For now: make docker-test"

down:
	@echo "docker compose arrives in Phase 3."
```

One self-contained command per line (GNU Make 3.81 — no `.ONESHELL`). Explicit `$(VENV)/bin/...` paths mean the targets work without an activated venv, which is what an evaluator will do.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `setup.py` / `setup.cfg` for packaging | `pyproject.toml` `[build-system]` + `[project]` (PEP 517/621) | PEP 621 final 2020; setuptools support stable since 61 (2022) | Nine lines replace a `setup.py`; no `setup.py develop` deprecation warnings |
| `sys.path` hacks in `conftest.py` | `pip install -e .` (PEP 660 editable) or `pythonpath =` in `pytest.ini` | `pythonpath` ini option added in pytest 7 (2022); PEP 660 in pip 21.3 | Every tool sees the same package, not just pytest |
| `ignore =` in `.flake8` | `extend-ignore =` / `extend-exclude =` | flake8 3.8 (2020) | Preserves built-in defaults instead of silently replacing them |
| `@pytest.fixture(scope="session") def event_loop()` | `asyncio_default_fixture_loop_scope` in config; `@pytest_asyncio.fixture(loop_scope=..., scope=...)` | pytest-asyncio 0.23 (2023) | The old recipe is removed; training data still reproduces it |
| `python -m importlinter.cli` | `lint-imports` console script, or `use_cases.lint_imports()` | n/a — the `-m` form never worked | See Pitfall 1 |
| Hand-rolled AST import checks | `import-linter` contracts | import-linter 1.0 (2019) | Transitive graph analysis instead of direct-import grep |
| `actions/checkout@v4`, `setup-python@v5` | `@v7` for both | 2026-07-20 | Node runtime and cache backend updates |
| mypy default `--no-local-partial-types`, loose bytes | mypy 2.0 defaults: `--local-partial-types`, `--strict-bytes` | mypy 2.0 | Module-level `x = None` must be annotated; `bytearray`/`memoryview` no longer assignable to `bytes` |

**Deprecated / outdated in this project's context:**
- `[tool.pytest.ini_options]` in `pyproject.toml` — silently ignored while `pytest.ini` exists (brief mandates `pytest.ini`).
- `psf/black` as a pre-commit repo — use `psf/black-pre-commit-mirror`.
- `extend-select = B950` alongside `max-line-length = 88` — contradictory; see Pitfall 3.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `pre-commit/mirrors-mypy` in an isolated env cannot resolve `import pytest` in `tests/`, so `pytest` would need to be in `additional_dependencies` | Pitfall 6 | LOW — this is the stated reason to prefer the `local`/`language: system` hook, which sidesteps the question entirely. If the mirror is chosen instead and the assumption is wrong, the only cost is one unnecessary entry in `additional_dependencies` |
| A2 | The CI workflow as written runs green on GitHub Actions | `ci.yml` | MEDIUM — no repository exists yet, so the workflow was never executed. Every *component* is verified (action tags, `postgres:18-alpine`, `cache: pip` syntax from official docs, and every shell command run locally), but the assembled YAML has not run. The first push is the test; budget one fix-up commit |
| A3 | A Python 3.14 host and a 3.13 CI/image will not diverge under `filterwarnings = error` | Pitfall 9 | LOW-MEDIUM — zero warnings were observed on both interpreters with the current (tiny) codebase. Divergence becomes more likely as Phases 3-5 add SQLAlchemy/psycopg. Mitigation: CI on 3.13 is authoritative, and `make docker-test` reproduces 3.13 locally |
| A4 | 285 MB runtime image size will hold once psycopg/SQLAlchemy/uvicorn[standard] are actually imported | Pitfall 10 | LOW — those wheels are already installed in the measured image (`requirements.txt` was complete); the number is real, not projected |
| A5 | The two AI incidents listed in D-18 are the complete set of real incidents so far | Documentation artifacts | LOW — sourced from CONTEXT.md, which the user authored. The plan should append the Pitfall 1 discovery (a research-provided recipe that would have shipped a fake architecture test, caught by executing it) as a third, genuinely unflattering entry |

Everything else in this document is either `[VERIFIED: local execution]` or `[CITED: …]` against an official source.

---

## Open Questions (RESOLVED)

1. **`.importlinter` file vs `[tool.importlinter]` in `pyproject.toml`**
   - What we know: both are fully supported and behave identically. `.planning/research/STACK.md` and CONTEXT's canonical-refs list say `.importlinter`; `.planning/research/ARCHITECTURE.md:736` says `pyproject.toml`. This is conflict #10, not enumerated in SUMMARY.md's table of nine.
   - What's unclear: nothing technical — it is a taste/discoverability call.
   - Recommendation: **`.importlinter`**, because the phase's whole thesis is that an evaluator can find the enforced boundary in five seconds, and a dedicated root-level file named after the tool does that better than the fifth section of `pyproject.toml`. Record the choice (and that the alternative is equivalent) in `DECISION_LOG.md`. The verified test code uses `api.read_configuration()` with no filename, which finds either.
   - **RESOLVED:** adopt the root-level `.importlinter` INI file. Implemented by plan `01-03` (which creates `.importlinter` and the architecture test); recorded as an ADR by plan `01-06`.

2. **Does `up` / `down` need to do anything in Phase 1?**
   - What we know: D-12 requires the targets to exist; CONTEXT explicitly permits "thin placeholders"; compose is Phase 3.
   - What's unclear: whether a placeholder that only prints a message reads as unfinished to an evaluator who runs it.
   - Recommendation: placeholders that print an accurate one-line explanation and exit 0. An evaluator running `make up` in Phase 1 is not a scenario that happens — only the final delivery is graded, and by then Phase 3 has replaced them.
   - **RESOLVED:** `up` and `down` ship as single `@echo` placeholders that exit 0 and name Phase 3 honestly. Implemented by plan `01-04` Task 2; recorded as an ADR by plan `01-06`.

3. **Should Phase 1 create the public GitHub repository, or only the workflow file?**
   - What we know: FND-10's success criterion is "a push to GitHub triggers CI … green", which requires a remote. CONTEXT marks repo creation as outward-facing and requiring explicit user confirmation (`autonomous: false`). AIW-05 (public repo, green badge) is owned by Phase 7.
   - What's unclear: whether the user wants the repo created now or at delivery.
   - Recommendation: the plan includes one `autonomous: false` checkpoint task — "create the GitHub repository and push" — placed last in the phase, with everything before it fully autonomous. If the user declines, the phase still completes with `ci.yml` committed and `make lint typecheck arch test` green locally, and the "green CI" criterion carries to Phase 7. The plan should state that fallback explicitly so it is not a surprise.
   - **RESOLVED:** repository creation is the last task of the phase, a blocking human checkpoint, with the documented fallback of committing `ci.yml` and carrying the green-CI evidence to Phase 7. Implemented by plan `01-08` Task 2.

4. **Which `.env.example` variables exist in Phase 1?**
   - What we know: FND-11 says "`.env.example` documents every variable". The settings module above declares five, but `DATABASE_URL` is not consumed by anything until Phase 3.
   - Recommendation: document all five now (`APP_NAME`, `ENVIRONMENT`, `DATABASE_URL`, `JWT_SECRET`, `JWT_ALGORITHM`, `JWT_EXPIRE_MINUTES`) with non-secret placeholder values. Declaring `DATABASE_URL` in Phase 1 is what lets the CI job export it and lets Phase 3 add a repository without touching settings. Phase 3/5 extend the file; Phase 7 verifies it against the README.
   - **RESOLVED:** `.env.example` documents every field the `Settings` model declares — the full list named above — with non-secret placeholders. Implemented by plan `01-02`.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.13 (host) | FND-01 inner loop | ✗ | — | **Python 3.14.3 host venv** — every pinned dep resolves to a wheel and the whole gate runs green; 3.13 is provided by Docker and CI |
| Python 3 (any) | host venv | ✓ | 3.14.3 (macOS arm64) | — |
| Docker Engine | DOCK-01, DOCK-04 | ✓ | 29.2.0 (linux/aarch64 backend) | — |
| Docker Compose | Phase 3 only | ✓ | v5.0.2 | — |
| `python:3.13-slim-trixie` | DOCK-01 | ✓ | pulls Python 3.13.15 | — |
| `postgres:18-alpine` | FND-10 | ✓ | manifest verified | `postgres:17-alpine` |
| GNU Make | FND-09 | ✓ | **3.81** (no `.ONESHELL`) | — |
| git | version control | ✓ | 2.50.1 | — |
| PyPI network access | FND-02 | ✓ | — | — |
| GitHub remote | FND-10 | ✗ (repo not created) | — | Commit `ci.yml`; gate the push behind an `autonomous: false` task (Open Question 3) |
| PostgreSQL (local) | not needed in Phase 1 | n/a | — | CI service container covers FND-10; Phase 3 adds compose |

**Missing dependencies with no fallback:** none.

**Missing dependencies with fallback:**
- Host Python 3.13 → use the 3.14 host venv for speed, Docker/CI for the authoritative 3.13 run. Verified equivalent for every gate in this phase.
- GitHub remote → Open Question 3.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 + pytest-asyncio 1.4.0 + pytest-cov 7.1.0 |
| Config file | `pytest.ini` (created by this phase — Wave 0) |
| Quick run command | `pytest tests/unit -q --no-cov` (≈0.2 s) |
| Full suite command | `pytest` (coverage gate included via addopts; ≈0.3 s) |
| Dockerized full suite | `make docker-test` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FND-01 | `taskmanager` is importable from `src/` and the four layer packages exist | unit | `python -c "import taskmanager.domain, taskmanager.application, taskmanager.infrastructure, taskmanager.presentation, taskmanager.main"` | ❌ Wave 0 |
| FND-02 | Dev + runtime requirements install with plain pip, exact pins | smoke | `pip install --dry-run -r requirements-dev.txt` | ❌ Wave 0 |
| FND-03 | flake8 passes with zero errors, driven by `.flake8` | smoke | `flake8 src tests` | ❌ Wave 0 |
| FND-03 | `.flake8` uses `extend-ignore`, never `ignore` | smoke | `! grep -Eq '^[[:space:]]*ignore[[:space:]]*=' .flake8` | ❌ Wave 0 |
| FND-04 | black and isort are satisfied | smoke | `black --check src tests && isort --check-only src tests` | ❌ Wave 0 |
| FND-05 | pytest config is read from `pytest.ini`, not pyproject | smoke | `pytest --collect-only -q 2>&1 \| grep -q "configfile: pytest.ini"` | ❌ Wave 0 |
| FND-05 | `filterwarnings = error` is active and the suite is warning-free | smoke | `pytest` (any warning becomes a failure) | ❌ Wave 0 |
| FND-06 | Coverage over `taskmanager` only, un-imported files counted, gate at 75 | smoke | `pytest` (addopts carry `--cov=taskmanager --cov-fail-under=75`) | ❌ Wave 0 |
| FND-06 | The gate actually fires below threshold | manual-once | Add a temporary uncovered module, run `pytest`, observe `FAIL Required test coverage of 75% not reached`, remove it | ❌ Wave 0 |
| FND-07 | mypy strict passes over src and tests | smoke | `mypy src tests` | ❌ Wave 0 |
| FND-08 | pre-commit runs all hooks and is stable on a second run | smoke | `pre-commit run --all-files && pre-commit run --all-files` | ❌ Wave 0 |
| FND-09 | Every Makefile target exists and succeeds | smoke | `make lint && make typecheck && make arch && make test` | ❌ Wave 0 |
| FND-10 | CI workflow is valid YAML and names every gate | smoke | `python -c "import yaml,sys; d=yaml.safe_load(open('.github/workflows/ci.yml')); s=[x.get('name','') for x in d['jobs']['quality-gates']['steps']]; assert any('mypy' in n for n in s)"` | ❌ Wave 0 |
| FND-10 | CI is green on a real push | manual (outward-facing) | GitHub Actions run — Open Question 3 | n/a |
| FND-11 | Settings load from env; missing/short secret rejected; nothing defaulted | unit | `pytest tests/unit/test_settings.py -q --no-cov` | ❌ Wave 0 |
| FND-11 | `.env.example` documents every declared field | unit | A test comparing `Settings.model_fields` keys (upper-cased) against the keys parsed from `.env.example` | ❌ Wave 0 |
| ARC-01 | Four layer packages under `src/taskmanager/` each with `__init__.py` | unit | `pytest tests/architecture -q --no-cov` (the `read_configuration` guard names them) | ❌ Wave 0 |
| ARC-03 | Contracts are configured **and** hold | unit | `pytest tests/architecture -q --no-cov` | ❌ Wave 0 |
| ARC-03 | Contracts go red on a violation | manual-once | The red/green sequence in Pattern 2; capture the output into `AI_WORKFLOW.md` | ❌ Wave 0 |
| ARC-03 | Contracts also run as a standalone CI step | smoke | `lint-imports; echo $?` → 0 | ❌ Wave 0 |
| DOCK-01 | Image builds, runs as non-root, is slim | smoke | `docker build --target runtime -t taskmanager . && [ "$(docker run --rm taskmanager whoami)" = app ]` | ❌ Wave 0 |
| DOCK-01 | Image contains no `.env` and no `.git` | smoke | `docker run --rm taskmanager ls -a /app` → no `.env`; `docker history taskmanager` → no secrets | ❌ Wave 0 |
| DOCK-04 | Suite runs in Docker with no host Python | smoke | `make docker-test` | ❌ Wave 0 |
| AIW-03 | `AI_WORKFLOW.md` exists with the skeleton and ≥1 dated real incident | smoke | `test -f AI_WORKFLOW.md && grep -Eq '^## Incident Log' AI_WORKFLOW.md && grep -Eq '^### 2026-' AI_WORKFLOW.md` | ❌ Wave 0 |
| AIW-04 | `CLAUDE.md` carries the project rules section | smoke | `grep -q 'HTTPException' CLAUDE.md && grep -q 'domain' CLAUDE.md` | ❌ Wave 0 |

`manual-once` items are one-time demonstrations whose *output* is committed as evidence (in `AI_WORKFLOW.md` / `DECISION_LOG.md`); they are not recurring gates.

### Sampling Rate

- **Per task commit:** `pytest tests/unit -q --no-cov` — sub-second, catches the common break.
- **Per wave merge:** `make lint && make typecheck && make arch && make test` — the full host gate, ≈5 s.
- **Phase gate (before `/gsd:verify-work`):** `make lint typecheck arch test` **and** `make docker-test` green, plus `pre-commit run --all-files` twice with no modifications on the second run.

### Wave 0 Gaps

Everything is a gap — the repository contains no code. Wave 0 must create, in this order:

- [ ] `pyproject.toml` (packaging block first — nothing else works without an importable package)
- [ ] `src/taskmanager/` with the four layer packages and `__init__.py` files — covers ARC-01
- [ ] `requirements.txt` / `requirements-dev.txt` — covers FND-02
- [ ] `pytest.ini`, `.flake8` — the two literal files, FND-03/FND-05
- [ ] `src/taskmanager/infrastructure/config/settings.py` + `src/taskmanager/main.py` — the real code the coverage gate measures
- [ ] `tests/__init__.py`, `tests/unit/__init__.py`, `tests/architecture/__init__.py`
- [ ] `tests/unit/test_settings.py`, `tests/unit/test_app_factory.py` — FND-06/FND-11
- [ ] `.importlinter` + `tests/architecture/test_layer_boundaries.py` — ARC-03
- [ ] `.env.example`, `.gitignore`, `.dockerignore`
- [ ] `.pre-commit-config.yaml` — FND-08
- [ ] `Makefile` — FND-09
- [ ] `Dockerfile` — DOCK-01/DOCK-04
- [ ] `.github/workflows/ci.yml` — FND-10
- [ ] `CLAUDE.md` project-rules section, `AI_WORKFLOW.md`, `DECISION_LOG.md` — AIW-03/AIW-04, D-17/D-18/D-19
- [ ] Framework install: `make install` (creates `.venv`, installs `requirements-dev.txt`, `pip install -e .`, `pre-commit install`)

No `conftest.py` is required in Phase 1 — `pythonpath = src` plus the editable install make it unnecessary, and an empty `conftest.py` is dead weight an evaluator notices. Phase 3 introduces one for the database fixtures.

---

## Security Domain

`security_enforcement` is absent from `.planning/config.json`, therefore enabled.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V1 Encoding & Sanitization | no (Phase 1) | No user input is processed yet |
| V2 Validation & Business Logic | partially | `pydantic-settings` validates configuration at boot (`min_length`, `gt=0`, `extra="forbid"`) |
| V3 Web Frontend Security | no | No routes exist until Phase 3 |
| V6 Authentication | no (Phase 5) | Phase 1 only guarantees `JWT_SECRET` has **no default** and is ≥16 chars |
| V7 Session Management | no (Phase 5) | — |
| V8 Authorization | no (Phase 5) | — |
| V10 OAuth / OIDC | no (Phase 5) | — |
| V11 Cryptography | partially | Secret *handling* only: env-sourced, never defaulted, never committed, never baked into an image layer. No cryptographic code in this phase |
| V12 Secure Communication | no | — |
| V13 Configuration | **yes — this phase's core security responsibility** | pydantic-settings with no production defaults; `.env` in `.gitignore` **and** `.dockerignore`; `.env.example` with placeholders; non-root container user; pinned base image (never `:latest`); exact `==` dependency pins |
| V14 Data Protection | no | — |
| V50 Supply Chain | **yes** | Exact `==` pins in `requirements*.txt`; `slopcheck` audit (28/28 OK); pinned pre-commit `rev`s; pinned GitHub Action major tags; pinned `python:3.13-slim-trixie` / `postgres:18-alpine` |

### Known Threat Patterns for this phase's surface

| Pattern | STRIDE | Standard Mitigation | Verified? |
|---------|--------|---------------------|-----------|
| Secret with a hard-coded default (`SECRET_KEY = "secret"`) | Spoofing / Elevation of Privilege | `jwt_secret: str = Field(min_length=16)` — no default; boot fails with `ValidationError` | ✓ two tests assert the rejection |
| `.env` committed or baked into an image layer | Information Disclosure | `.env` in both `.gitignore` and `.dockerignore`; verify with `git log --all -- .env` and `docker history` | Dockerignore written; `git log` check is a phase-gate task |
| Container running as root | Elevation of Privilege | `useradd --system` + `USER app` in the final stage | ✓ `docker run --rm taskmanager whoami` → `app` |
| Unpinned base image (`postgres:latest`, `python:3.13`) | Tampering | Pin the tag; `python:3.13-slim-trixie`, `postgres:18-alpine` | ✓ both verified to exist |
| Dependency confusion / hallucinated package | Tampering | `slopcheck install` on every package before it enters `requirements*.txt`; exact `==` pins | ✓ 28/28 OK |
| Compromised GitHub Action | Tampering | Pin action tags (`@v7`); consider SHA pinning at delivery | Tags verified today |
| Secret injected via `ENV`/`ARG` in the Dockerfile | Information Disclosure | Never; inject at runtime via compose `environment:` / `env_file:` | ✓ Dockerfile contains no secret |
| `detect-private-key` bypass | Information Disclosure | `pre-commit-hooks` `detect-private-key` + `check-added-large-files` | Included in the hook list |
| Architecture gate that reports green while broken | Repudiation | The red/green demonstration, plus the `read_configuration` guard test | ✓ both verified |

Phases 3-5 carry V2/V6/V7/V8/V11 in full (JWT, Argon2, ownership scoping, RFC 9457 error bodies). Nothing in Phase 1 should anticipate them beyond the secret-handling rules above.

---

## Sources

### Primary (HIGH confidence)

- **Local execution** in a throwaway scaffold with the exact pinned toolchain — host CPython 3.14.3 / macOS arm64 and `python:3.13-slim-trixie` (Python 3.13.15, linux/aarch64). Source of every `[VERIFIED: local execution]` claim: import-linter exit codes and the `python -m importlinter.cli` no-op, the zero-contract silent pass, the coverage numbers and gate firing at 56 %, `filterwarnings = error` producing zero warnings, the mypy plugin behaviour in both directions, `flake8.defaults.EXCLUDE` and `pycodestyle.DEFAULT_IGNORE`, GNU Make 3.81 ignoring `.ONESHELL`, wheel-only resolution of all pinned deps on cp314/arm64, and the three-stage Docker build with `whoami` → `app` at 285 MB.
- **Context7 `/seddonym/import-linter`** — `.importlinter` INI vs `[tool.importlinter]` TOML equivalence, `root_package`/`root_packages`, `include_external_packages`, `api.read_configuration()` return shape, `use_cases.lint_imports() -> bool`, and the documented "zero contracts → SUCCESS" behaviour in `application/use_cases.py`.
- **PyPI JSON API**, queried 2026-09-17 — current version, release date, `requires_python` and `requires_dist` for import-linter 2.15, grimp 3.17, pytest 9.1.1, pytest-asyncio 1.4.0, pytest-cov 7.1.0, coverage 7.16.1, mypy 2.3.1, black 26.5.1, isort 9.0.1, flake8 7.3.0, flake8-bugbear 26.9.9, flake8-comprehensions 3.17.0, pep8-naming 0.15.1, pre-commit 4.6.2, setuptools 84.0.0.
- **GitHub Tags API**, queried 2026-09-17 — `pre-commit/mirrors-mypy` v2.3.1, `psf/black-pre-commit-mirror` 26.5.1, `PyCQA/flake8` 7.3.0, `PyCQA/isort` 9.0.1, `pre-commit/pre-commit-hooks` v6.0.0; releases API — `actions/checkout` v7.0.1, `actions/setup-python` v7.0.0, `actions/cache` v6.1.0.
- **`actions/setup-python` `docs/advanced-usage.md`** (raw, fetched today) — `cache: pip` + `cache-dependency-path` exact YAML.
- **Docker Hub** — `docker manifest inspect postgres:18-alpine` succeeded; `python:3.13-slim-trixie` pulled and run.
- **`slopcheck` 0.x** run against 28 packages across two invocations — 28 OK, 0 SUS, 0 SLOP.

### Secondary (MEDIUM confidence)

- `.planning/research/STACK.md`, `PITFALLS.md`, `ARCHITECTURE.md`, `SUMMARY.md` — reused for versions, pitfall taxonomy and layer design per the phase brief. Three concrete corrections to them are raised above (the `python -m importlinter.cli` recipe, `exclude` vs `extend-exclude`, and `extend-select = B950`), each backed by local execution.
- Black's "Using Black with other tools" guide (via STACK.md) — `max-line-length = 88`, `extend-ignore = E203,E701`.

### Tertiary (LOW confidence)

- A1 in the Assumptions Log (`pytest` needed in a mirrors-mypy `additional_dependencies` list) — reasoned from pre-commit's isolation model, not executed. The recommended `local` hook makes it moot.

---

## Metadata

**Confidence breakdown:**

- Standard stack: **HIGH** — every version re-queried on PyPI today and installed together without a resolver conflict.
- src-layout mechanics: **HIGH** — the full matrix (pytest / coverage / mypy / import-linter / Docker runtime / Docker test) was executed, including the negative cases (package uninstalled, non-editable install).
- import-linter configuration and invocation: **HIGH** — all four invocation forms and all three silent-pass modes tested explicitly; red/green demonstrated twice.
- Coverage strategy: **HIGH** — measured, and the gate observed firing.
- `filterwarnings = error`: **HIGH** for Phase 1's dependency set on both 3.13 and 3.14; **MEDIUM** as a forward-looking claim for Phases 3-5 (SQLAlchemy/psycopg/httpx not yet exercised under it).
- Docker: **HIGH** — image built and run; size, user and Python version measured.
- GitHub Actions: **MEDIUM-HIGH** — every ingredient verified against official sources, but the assembled workflow has never executed (Assumption A2).
- pre-commit: **MEDIUM-HIGH** — all five mirror revs verified live; hook *behaviour* in the isolated envs was reasoned, not run (Assumption A1).
- Pitfalls: **HIGH** — nine of eleven were reproduced on this machine.

**Research date:** 2026-09-17
**Valid until:** 2026-10-17 (30 days — the toolchain is stable; re-verify pinned versions if the phase slips past this date, since `pytest`, `mypy` and `black` all released within the last four months)

---
*Phase research for: 01-foundation-quality-gates*
*Verification scaffold: `/private/tmp/claude-501/-Users-xch4rt-work-myself-crehana-test/bcbdb14e-b987-4aa8-87b1-0c43dba682b7/scratchpad/proj1` (throwaway; not part of the repository)*
