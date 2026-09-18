---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
stopped_at: Completed 02-05-PLAN.md
last_updated: "2026-09-18T07:29:02.487Z"
last_activity: 2026-09-18 -- Phase 02 plan 05 complete (application ports, DTO conventions, the ChangeTaskStatus reference use case)
progress:
  total_phases: 7
  completed_phases: 1
  total_plans: 15
  completed_plans: 13
  percent: 14
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-09-17)

**Core value:** Every requirement in the challenge PDF is met to the letter and is provable in
under five minutes by an evaluator: `docker compose up`, run the tests, read the docs.
**Current focus:** Phase 02 — domain-error-contract

## Current Position

Phase: 02 (domain-error-contract) — EXECUTING
Plan: 6 of 7
Status: Ready to execute
Last activity: 2026-09-18 -- Phase 02 plan 05 complete (application ports, DTO conventions, the ChangeTaskStatus reference use case)

Progress: [█████████░] 87%

## Performance Metrics

**Velocity:**

- Total plans completed: 8
- Average duration: —
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 8 | - | - |

**Recent Trend:**

- Last 5 plans: —
- Trend: —

*Updated after each plan completion*
| Phase 01 P01 | 13min | 3 tasks | 15 files |
| Phase 01 P02 | 5min | 3 tasks | 7 files |
| Phase 01 P03 | 8min | 3 tasks | 3 files |
| Phase 01 P04 | 14min | 2 tasks | 3 files |
| Phase 01 P05 | 17min | 2 tasks | 3 files |
| Phase 01 P06 | 10min | 2 tasks | 2 files |
| Phase 01 P07 | 11min | 2 tasks | 1 files |
| Phase 01 P08 | 14min | 2 tasks | 2 files |
| Phase 02 P01 | 10min | 2 tasks | 10 files |
| Phase 02 P02 | 14min | 2 tasks | 4 files |
| Phase 02 P03 | 12min | 3 tasks | 11 files |
| Phase 02 P04 | 18min | 3 tasks | 12 files |
| Phase 02 P05 | 22min | 3 tasks | 17 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: Python 3.13, `src/taskmanager/` layout, psycopg 3 + SQLAlchemy 2.0 async, Alembic
- [Roadmap]: Domain entities as stdlib dataclasses; Pydantic at schema/DTO/settings boundaries
- [Roadmap]: RFC 9457 problem+json from a single exception handler, built before any router
- [Roadmap]: 404 for invisible resources, 403 for visible-but-forbidden
- [Roadmap]: Completion % over the whole list via one SQL aggregate; pytest-asyncio loop scope
  `function` by default; `postgres:18-alpine`

- [Phase 01-01]: requires-python >=3.13 with mypy/black analysis target py313 — host venv runs CPython 3.14.3
- [Phase 01-01]: requirements*.txt is the single version source; pyproject.toml has no [project.dependencies]
- [Phase 01-01]: Coverage measured as --cov=taskmanager (package name) with the 75% gate in pytest.ini addopts
- [Phase 01-01]: Host venv at `.venv/` (CPython 3.14.3); invoke tools as `.venv/bin/<tool>`; a bare
  `pytest` fails the 75% gate until plan 01-02 adds real modules and tests

- [Phase 01-02]: Executed plan 01-02 as a real TDD cycle: tests written and observed failing (3d48d02) before settings.py and main.py existed (58a0497)
- [Phase 01-02]: Settings secrets (database_url, jwt_secret) carry no default at all; jwt_secret enforces min_length=16, extra=forbid and frozen=True
- [Phase 01-02]: create_app(settings=None) is a factory with no module-level app instance, so taskmanager.main imports with zero environment configuration
- [Phase 01-02]: Coverage is 100% over 18 real statements with no pragma, no omit and no threshold change; the gate was observed firing at 40.91% and the output committed as evidence
- [Phase 01-03]: Root-level .importlinter (not [tool.importlinter] in pyproject.toml): equivalent, but an evaluator finds a file named after the tool in five seconds
- [Phase 01-03]: The architecture contract runs inside pytest via importlinter.application.use_cases.lint_imports; python -m importlinter.cli is forbidden - it exits 0 with a real violation in place
- [Phase 01-03]: RESEARCH Pitfall 2 corrected by execution: the [importlinter:contracts:] plural typo is harmless on 2.15; the real zero-contract trap is the hyphenated [import-linter:] prefix, and the guard test was observed catching it
- [Phase 01-04]: pre-commit repo-local hooks use .venv/bin-qualified entries; RESEARCH's bare entries were executed and both whole-program gates died with 'Executable not found' under a minimal PATH (evidence/pre-commit-venv-entry.txt)
- [Phase 01-04]: consequence accepted - .pre-commit-config.yaml is developer-host-only, so CI and the Docker image must never call pre-commit run; CI runs black/isort/flake8/mypy/lint-imports/pytest as named steps
- [Phase 01-04]: Makefile comments describe forbidden forms (ONESHELL, a version-suffixed python3, the python -m import-linter module) without spelling them, so the plan's grep gates stay strict - same convention as 01-03's docstring
- [Phase 01-05]: The research Dockerfile's test stage was observed red before shipping: it never copied .env.example, so 01-02's parity test failed while the run still printed 'Total coverage: 100.00%'; fix and both captures in evidence/docker-test-stage.txt
- [Phase 01-05]: Image size recorded as observed (368MB on linux/arm64 with a BuildKit attestation manifest), not RESEARCH's 285MB; both far under the 500MB ceiling
- [Phase 01-05]: ci.yml runs six gates as named direct steps with permissions contents:read and lint-imports --no-logo; the local hook framework is never invoked, since a runner has no .venv
- [Phase 01-06]: CLAUDE.md gains a hand-maintained ## Project Rules section placed outside every GSD delimiter block, transcribing the layer order from .importlinter rather than from CONTEXT so documentation cannot drift from enforcement
- [Phase 01-06]: DECISION_LOG.md opens with 19 ADRs (17 required): the two extra are 01-05's Dockerfile test stage and major-tag action pinning, both handed over as owed
- [Phase 01-06]: the duplicated gate list is documented twice on purpose - as a rule in CLAUDE.md and as a consequence in ADR-015 - because silent divergence between pre-commit and ci.yml is threat T-01-47
- [Phase 01-07]: AI_WORKFLOW.md opens with the five-section skeleton plus four dated incidents; Phase 7 sections carry explicit to-be-completed markers instead of filler
- [Phase 01-07]: The incident log quotes the coverage and import-linter captures verbatim (9 and 51 exact lines matched by script) rather than paraphrasing any number
- [Phase 01-07]: Four further real Phase 1 incidents (RESEARCH Pitfall 2 non-reproduction, pre-commit bare entry, Docker .env.example, 368MB image) were deliberately left out - the plan enumerates exactly four entries
- [Phase 01-08]: The whole Phase 1 gate was captured green in one uninterrupted run (format first, proven a no-op) rather than stitched from per-plan runs
- [Phase 01-08]: FND-10 satisfied by observation, not the fallback: CI run 35301518310 on Xch4rt/crehana-backend-test concluded success on the FIRST attempt, so RESEARCH A2's budgeted fix-up commit went unused
- [Phase 01-08]: 01-RESEARCH.md assumption A2 and DECISION_LOG.md ADR-019 ('the workflow has never run on a real runner') are now stale; Phase 7 owns the refresh since DECISION_LOG.md is append-only
- [Phase 01-08]: The user supplied an already-created empty public repo, so gh repo create was never run and GitHub's quick-setup README/first-commit snippet was ignored: the real eight-commit main was pushed unchanged, no force
- [Phase 01-08]: The attribution audit publishes both counts (raw=1, refined=0); the single raw match is the filename CLAUDE.md in commit 0456070's subject, not a trailer
- [Phase 02-01]: TDD RED is observed and captured as evidence/02-01-tdd-red.txt, never as a separate test() commit - the mypy (strict) pre-commit hook rejects a test importing a module that does not exist yet, and --no-verify is forbidden
- [Phase 02-01]: frozen+slots dataclass setattr on a NON-field raises FrozenInstanceError on CPython 3.13 (Docker/CI) but TypeError on 3.14.3 (host); negative attribute tests assert the portable claim (refused, no __dict__, exact __slots__) - evidence/02-01-frozen-slots-setattr.txt
- [Phase 02-01]: No can_transition() helper beside ALLOWED_TRANSITIONS - the state machine is a Task invariant owned by the entity (02-03); CompletionStats carries no __post_init__ guard because Phase 3's COUNT(*) FILTER aggregate owns that invariant
- [Phase 02-02]: DomainError.details is typed dict[str, str | int | float | bool | None], not dict[str, Any] - an unserialisable value is now a mypy error at the raise site instead of a server fault raised inside the error handler
- [Phase 02-02]: flake8-bugbear B042 counts POSITIONAL arguments against declared parameters, so every single-argument exception leaf forwards details as a keyword; 02-RESEARCH.md Pattern 6 only verified the two-parameter case - evidence/02-02-b042-leaf-arity.txt
- [Phase 02-02]: One __reduce__ on DomainError delegating to a module-level _restore covers pickle and copy for every subclass; no leaf defines a pickle dunder, and the explicit __str__ keeps the details dict out of log lines
- [Phase 02-03]: Entities are mutable @dataclass(slots=True) and their negative attribute tests assert AttributeError directly - a non-frozen slotted class installs no __setattr__, so 02-01's frozen 3.13-vs-3.14.3 divergence does not apply (evidence/02-03-mutable-slots-setattr.txt)
- [Phase 02-03]: domain/validation.py owns require_utc/require_text/optional_text and every entity delegates to them, so each limit exists exactly once - in the entity ClassVar passed as max_length, never as a literal in a guard, a message or a test
- [Phase 02-03]: change_status checks ALLOWED_TRANSITIONS before normalising now, so a rejected move leaves the entity byte-identical; the same-state no-op returns before either check (D-02)
- [Phase 02-03]: User.PASSWORD_HASH_MAX_LENGTH = 512 is a sanity bound, not a policy - the minimum-password-length rule applies to the plaintext, which never reaches the domain; the entity validates no email format either, because EmailStr owns that at the boundary (D-04)
- [Phase 02-04]: ARC-07 is satisfied: register_exception_handlers(app), called by create_app(), is the only place an error body is produced - four handlers, one problem() builder, one class-keyed status table resolved by MRO walk
- [Phase 02-04]: Exception handlers annotate the base Exception type and narrow with an isinstance assertion: mypy strict rejects the narrower annotation (callable parameters are contravariant) and the if/raise form adds partial branches the 100% gate cannot cover
- [Phase 02-04]: STATUS_BY_EXCEPTION holds eight entries and no leaf class: TaskNotFoundError and its four siblings resolve through their parent by MRO, and the table uses int literals because 422's HTTPStatus member name changed across Python versions
- [Phase 02-04]: coverage report --include A --include B keeps only B, so the plan's presentation coverage command measured main.py alone; the comma-separated single-flag form is the honest one and is captured in evidence/02-04-tdd-red.txt
- [Phase 02-05]: ARC-04 satisfied: the eight ports are typing.Protocol classes with ... bodies only, and each has a conforming in-memory fake under tests/ named in eight test_fake_*_satisfies_the_*_port tests
- [Phase 02-05]: mypy checks a MUTABLE protocol member invariantly, so FakeUnitOfWork.tasks must be annotated TaskRepository exactly; the fake exposes the same object twice (tasks + task_repository) and Phase 3's SqlAlchemyUnitOfWork will need the same annotation
- [Phase 02-05]: The invisible-task test catches the base DomainError and then asserts the leaf is TaskNotFoundError and not AuthorizationError - catching the leaf directly would pass against an implementation that never considered the 403 question (ADR-008)
- [Phase 02-05]: ChangeTaskStatus has no same-state branch and no AuthorizationError branch, both deliberate: idempotence is a change_status invariant (D-02) and ASGN-02 leaves no visible-but-forbidden case for this verb

### Pending Todos

[From .planning/todos/pending/ — ideas captured during sessions]

None yet.

### Blockers/Concerns

[Issues that affect future work]

- Phase 3 (async session lifecycle, transactional test fixtures, Alembic `env.py`) and Phase 5
  (JWT/hashing libraries, 403-vs-404 matrix) are flagged by research as needing
  `/gsd:plan-phase --research-phase`.

- `AI_WORKFLOW.md` must be appended to at the end of every phase; reconstructing it in Phase 7
  would undermine the project's own thesis.

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| *(none)* | | | |

## Session Continuity

Last session: 2026-09-18T07:29:02.479Z
Stopped at: Completed 02-05-PLAN.md
Resume file: None
