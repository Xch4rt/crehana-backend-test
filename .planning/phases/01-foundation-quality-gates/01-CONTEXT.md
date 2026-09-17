# Phase 1: Foundation & Quality Gates - Context

**Gathered:** 2026-09-17
**Status:** Ready for planning
**Source:** Decisions already made with the user during project initialization (PROJECT.md Key
Decisions, research conflict resolutions in research/SUMMARY.md). No separate discuss-phase was
run; nothing here is new — it is a consolidation so downstream agents see locked decisions in
one place.

<domain>
## Phase Boundary

This phase delivers the project skeleton and every automated quality gate, passing on a codebase
that contains **no application logic**: package layout, pinned dependencies, lint/format/type
configuration, pytest + coverage configuration, import-linter contracts, pre-commit, Makefile,
GitHub Actions CI, a multistage non-root Docker image, a dockerized test command, settings
loading, and the first versions of `CLAUDE.md` rules, `AI_WORKFLOW.md` and `DECISION_LOG.md`.

Not in this phase: domain entities, error contract, routers (including `/health`), database
models, migrations, docker-compose API+DB orchestration (Phase 3).

</domain>

<decisions>
## Implementation Decisions

### Runtime & layout
- **D-01**: Python 3.13; Docker base image `python:3.13-slim-trixie`.
- **D-02**: `src/taskmanager/` package layout with sub-packages `domain`, `application`,
  `infrastructure`, `presentation` (each with `__init__.py`), plus `main.py` as composition root.
- **D-03**: Dependencies managed with plain pip and exact `==` pins in `requirements.txt`
  (runtime) and `requirements-dev.txt` (dev/test). Versions come from
  `.planning/research/STACK.md` (verified against PyPI on 2026-09-17). No uv/poetry required on
  the host.

### Lint / format / types
- **D-04**: `.flake8` file (literal, required by the brief): `max-line-length = 88`,
  `extend-ignore = E203, E701` — never `ignore =`. Plugins: flake8-bugbear,
  flake8-comprehensions, pep8-naming.
- **D-05**: black and isort configured in `pyproject.toml`; isort `profile = "black"`.
- **D-06**: mypy in strict mode over `src/`, configured in `pyproject.toml`.
- **D-07**: ruff is NOT used (brief mandates flake8); recorded in `DECISION_LOG.md`.

### Tests & coverage
- **D-08**: All pytest configuration lives in `pytest.ini` (literal file, required by the brief;
  pytest ignores `[tool.pytest.ini_options]` when it exists): `asyncio_mode = auto`,
  `asyncio_default_fixture_loop_scope = function`, `filterwarnings = error` (with targeted
  ignores only if a transitive dependency forces it), markers `unit` and `integration`.
- **D-09**: Coverage measures the real package (`source = taskmanager` / `src/taskmanager`),
  excludes tests, reports un-imported files, and fails under 75% (`--cov-fail-under=75`).
  Never `--cov=.`.

### Architecture enforcement
- **D-10**: import-linter `layers` contract:
  `taskmanager.main > taskmanager.presentation > taskmanager.infrastructure >
  taskmanager.application > taskmanager.domain`, plus a `forbidden` contract banning
  `fastapi`, `starlette`, `sqlalchemy` (and any third-party lib for `domain`) from `domain` and
  `application`. The contracts run inside the pytest suite (a test invoking `lint-imports`) and
  as a CI step. The phase must demonstrate the contract goes red on a deliberate forbidden
  import and green once removed.

### Automation
- **D-11**: pre-commit runs black, isort, flake8 and mypy.
- **D-12**: `Makefile` targets: `install`, `lint`, `format`, `typecheck`, `test`, `up`, `down`
  (`up`/`down` may be thin placeholders until compose lands in Phase 3, but must exist).
- **D-13**: GitHub Actions workflow on every push: lint, typecheck, architecture check, tests
  with coverage gate, against a `postgres:18-alpine` service container.

### Docker
- **D-14**: Multistage `Dockerfile` producing a slim image that runs as a non-root user.
- **D-15**: One documented command runs the test suite inside Docker with no Python on the host.

### Configuration
- **D-16**: Settings via pydantic-settings, read from environment; no secret has a hard-coded
  production default; `.env.example` documents every variable; `.env` is git-ignored.

### AI transparency & docs
- **D-17**: `CLAUDE.md` gains a project-rules section: layer rules, no `HTTPException` outside
  presentation, quality gates must be green before commit, English only, no AI attribution in
  commits.
- **D-18**: `AI_WORKFLOW.md` is created with its section skeleton and a dated incident log whose
  first entries are REAL events from this project (no invented incidents). Known real entries
  so far: (a) a research-synthesizer subagent was refused by a file-write guardrail and worked
  around it via a shell heredoc instead of reporting back — caught by the orchestrator reading
  the agent's report, content reviewed before commit, subagent prompts since then forbid
  workarounds; (b) the four research agents produced 9 conflicting recommendations (e.g. Python
  3.12 vs 3.13, RFC 7807 vs 9457, loop scope function vs session) — surfaced explicitly and
  resolved by the human/orchestrator rather than silently picked.
- **D-19**: `DECISION_LOG.md` is started in this phase in ADR style (context / options /
  decision / consequences), recording the decisions locked so far: PostgreSQL, Python 3.13,
  src layout, dataclass domain + Pydantic boundaries, RFC 9457, psycopg 3 + async SQLAlchemy,
  Alembic, 404/403 visibility rule, whole-list completion %, flake8-over-ruff, pip pins,
  pytest-asyncio loop scope, `postgres:18-alpine`.
- **D-20**: Everything in English. Git commits carry no Claude/AI co-author or attribution lines.

### Claude's Discretion
- How the 75% coverage gate passes on a near-empty codebase (e.g. a minimal settings module and
  app factory with real tests) — but it must pass honestly, without `# pragma: no cover` abuse
  or lowering the threshold.
- Exact Makefile recipe bodies, pre-commit hook revisions, CI job layout/caching.
- Whether the dockerized test command uses a dedicated Dockerfile stage or a compose profile.
- `.gitignore` / `.dockerignore` contents.
- Creating the public GitHub repository is outward-facing: the plan must mark that step as
  requiring explicit user confirmation (`autonomous: false`); everything else is autonomous.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project
- `.planning/PROJECT.md` — scope, constraints, key decisions
- `.planning/REQUIREMENTS.md` — FND-01..11, ARC-01, ARC-03, DOCK-01, DOCK-04, AIW-03, AIW-04
- `.planning/ROADMAP.md` — Phase 1 goal, success criteria, standing rules

### Research
- `.planning/research/STACK.md` — exact pinned versions and ready-to-paste `.flake8`,
  `pytest.ini`, `pyproject.toml`, `.pre-commit-config.yaml`, `.importlinter` samples (adapt the
  `app`/`api` sample names to `taskmanager`/`presentation`)
- `.planning/research/SUMMARY.md` — "Conflicts Between Research Files" table with resolutions
- `.planning/research/PITFALLS.md` — Phase-1 pitfalls: flake8 `ignore` trap, coverage `source`,
  pytest-asyncio loop scope, Docker non-root/.dockerignore, `filterwarnings = error`
- `.planning/research/ARCHITECTURE.md` — package layout and import-linter contract design

</canonical_refs>

<specifics>
## Specific Ideas

- The brief names these files literally; they must exist with these exact names: `.flake8`,
  `pytest.ini`, `Dockerfile`, `docker-compose.yml` (Phase 3), `README.md` (Phase 7),
  `DECISION_LOG.md`.
- The evaluator has ~5 minutes: every command must be one word behind `make`.

</specifics>

<deferred>
## Deferred Ideas

- `/health` endpoint and docker-compose API+DB orchestration — Phase 3 (after the error contract).
- README — Phase 7 (a minimal placeholder is acceptable earlier if CI badges need a home).

</deferred>

---

*Phase: 01-foundation-quality-gates*
*Context gathered: 2026-09-17 from project-initialization decisions*
