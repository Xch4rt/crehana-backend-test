---
phase: 03-persistence-runnable-stack
plan: 03
subsystem: infrastructure
tags: [settings, pydantic-settings, database-url, sqlalchemy, clock, d-04, d-15, unit-test]

# Dependency graph
requires:
  - phase: 01-foundation-quality-gates
    provides: Settings with extra="forbid" and no default for any secret, the .env.example/Settings exact-equality parity test, and the five quality gates
  - phase: 02-domain-error-contract
    provides: the Clock Protocol port, FrozenClock as the shape a clock implementation takes, and the conformance-by-annotation test pattern
  - phase: 03-persistence-runnable-stack
    plan: 01
    provides: the infrastructure package layout the two new modules join
provides:
  - Settings.test_database_url - the declared, optional, test-only DSN that keeps cp .env.example .env bootable under extra="forbid"
  - src/taskmanager/infrastructure/config/database_url.py - derive_test_database_url() and resolve_test_database_url(), the single expression of D-04's precedence
  - src/taskmanager/infrastructure/clock.py - SystemClock, the runtime adapter for the one non-async port
  - .env.example documenting the compose host and the localhost host without a second live DATABASE_URL assignment (D-15)
affects: [03-04, 03-05, 03-06, 03-07, 03-08, 03-09, 03-10, 03-11, 04-crud-endpoints, 05-auth]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A test-only setting is declared on the production Settings class rather than read with os.environ: the .env.example parity gate is an exact set equality and extra=forbid makes an undeclared key a boot failure, so the key exists in both places or in neither"
    - "A URL component is changed with make_url(url).set(component=...).render_as_string(hide_password=False), never by substring substitution - the compose credentials put the database name inside the user and the password too"
    - "hide_password=False is confined to the one place a live connection string is produced, with the masking default required for any URL that reaches a message (T-3-10)"
    - "An alternative form that a grep gate forbids is described in prose rather than spelled as a literal - the 01-04 Makefile convention, now applied a fourth time"
    - "A precedence rule (explicit setting over derivation) is proven by monkeypatching the derivation to raise, so the test fails if the fallback is consulted at all"

key-files:
  created:
    - src/taskmanager/infrastructure/config/database_url.py
    - src/taskmanager/infrastructure/clock.py
    - tests/unit/infrastructure/test_database_url.py
    - tests/unit/infrastructure/test_clock.py
  modified:
    - src/taskmanager/infrastructure/config/settings.py
    - .env.example
    - tests/unit/test_settings.py

key-decisions:
  - "RESEARCH Pitfall 6 option (a) taken as recommended: test_database_url: str | None = None on Settings plus TEST_DATABASE_URL in .env.example. The alternative (b) - os.environ in the integration conftest - would have contradicted the CONTEXT canonical-refs note, and (c) - loosening the parity assertion - weakens an existing gate to accommodate a new key"
  - "The compose form of DATABASE_URL is documented as a COMMENTED line, and the comment says why: the parity test collects key names from non-comment lines, so a second live assignment would pass the gate while silently changing which host pydantic reads (it takes the last one)"
  - "The precedence test monkeypatches derive_test_database_url to raise rather than asserting on the returned string alone - a return-value assertion passes even against an implementation that derives first and discards the result"
  - "tests/conftest.py needed no change: the app fixture builds Settings(_env_file=None) with only DATABASE_URL and JWT_SECRET exported, and an optional field defaulting to None is satisfied by that"
  - "No requirement tick taken: 03-11 is the last claimant of DB-01, as it is of DB-02/03/04/05, ARC-08, DOCK-02 and DOCK-03"

patterns-established:
  - "infrastructure/config/ now holds settings.py (what the environment says) beside database_url.py (what one of those values means for tests) - a module whose whole job is keeping one decision in one place, the same shape as constraints.py in infrastructure/db/"

requirements-completed: []

# Metrics
duration: 6min
completed: 2026-09-18
---

# Phase 3 Plan 03: The Test Database URL and the System Clock Summary

**`TEST_DATABASE_URL` is now a declared `Settings` field *and* a documented `.env.example` key - the only combination that keeps `cp .env.example .env && docker compose up` working under `extra="forbid"` while the exact-equality parity gate stays untouched - and the URL it falls back to is derived by `make_url(...).set(database=...)`, with a test that would catch the substring substitution the compose credential pair `taskmanager:taskmanager@` makes lethal rather than theoretical.**

## Performance

- **Duration:** 6 min
- **Started:** 2026-09-18T22:04Z
- **Completed:** 2026-09-18T22:11Z
- **Tasks:** 2
- **Files modified:** 4 created, 3 modified

## Accomplishments

- **The configuration contract has both ends, or it has neither.** `Settings` gains exactly one field, `test_database_url: str | None = None`, immediately after `database_url`, and `.env.example` gains the matching `TEST_DATABASE_URL` key. `test_env_example_documents_every_field` was not touched, and it still asserts set equality rather than a subset. The inline comment on the field records the trade in the terms that matter: the field is never read in production, but declaring it is what stops an undeclared key in a copied `.env` from becoming a boot-time `ValidationError` - a production failure, not a test failure.
- **No secret gained a default.** The only new default is `None`, on the one field that touches the database without being a credential. `database_url` and `jwt_secret` still have no default at all, and `extra="forbid"` still rejects an unknown `.env` key (T-3-12).
- **D-15's two hosts are documented without a second live assignment.** The `DATABASE_URL` block now says that `localhost` is what `make test`, `make run` and host-side `alembic` use, shows the compose form as a **commented** line, and states that the `api` service overrides it inside `docker-compose.yml` so a developer's `.env` never needs editing. The comment also spells out why the line stays commented: the parity test collects key *names* from non-comment lines, so an uncommented second `DATABASE_URL=` would sail through the gate while pydantic quietly read the last assignment instead of the first.
- **The derivation is a library call, and the test proves the failure mode.** `derive_test_database_url` is `make_url(database_url).set(database=TEST_DATABASE_NAME).render_as_string(hide_password=False)`. `test_a_password_containing_taskmanager_is_not_rewritten` starts from the exact compose URL - `postgresql+psycopg://taskmanager:taskmanager@localhost:5432/taskmanager`, three occurrences of the word - and asserts that exactly one of them changes, with `"//taskmanager:taskmanager@" in derived` spelled out beside the full-string equality. `grep -c '\.replace(' src/taskmanager/infrastructure/config/database_url.py` prints `0`.
- **Query parameters survive.** `?sslmode=require` is carried through the swap unchanged, which matters because it is exactly the option a hosted PostgreSQL adds to the URL and exactly what a regex or a substring edit would mangle.
- **T-3-10 is confined to one line, with the rule written beside it.** `hide_password=False` appears once, with a comment saying it is required because the result is a live connection string and that any URL rendered into a message - a log line, an exception, plan 03-05's fail-fast fixture - must use the masking default instead. Both renderings were checked: the default form produces `postgresql+psycopg://taskmanager:***@localhost:5432/taskmanager_test`.
- **D-04's precedence lives in one function, and the test is falsifiable.** `resolve_test_database_url` returns `settings.test_database_url` when set and derives otherwise. `test_an_explicit_test_database_url_wins` monkeypatches `derive_test_database_url` to raise, so the test fails if the fallback runs at all - an assertion on the returned string alone would pass against an implementation that derived first and threw the result away.
- **`SystemClock` conforms structurally and returns an aware instant.** `clock: Clock = SystemClock()` is accepted by mypy strict; `now().tzinfo is not None` and `now().utcoffset() == timedelta(0)`; consecutive readings are non-decreasing. The module docstring names the naive stdlib alternative and the concrete consequence - `domain/validation.py::require_utc` rejects a naive value, so a naive clock would fail at the first `created_at` guard - without spelling the literal the acceptance grep forbids. `grep -c 'utcnow' src/taskmanager/infrastructure/clock.py` prints `0`.
- **All four gates green, coverage still 100%.** `make lint && make typecheck && make arch && make test`: 70 files black/isort clean, flake8 clean, mypy strict clean over 70 source files, three import-linter contracts KEPT, **172 passed, 100.00% total coverage** under `filterwarnings = error`. `clock.py` and `database_url.py` are both at 100% with no `pragma: no cover` and no `omit` entry.

## Task Commits

Each task was committed atomically:

1. **Task 1: declare TEST_DATABASE_URL and document the compose host split** - `c389e41` (feat)
2. **Task 2: derive the test database URL with make_url and add SystemClock** - `4d9833d` (feat)

**Plan metadata:** see the `docs(03-03)` commit that carries this SUMMARY.

## Files Created/Modified

- `src/taskmanager/infrastructure/config/database_url.py` (48 lines) - `TEST_DATABASE_NAME` as a `Final`, `derive_test_database_url()` and `resolve_test_database_url()`; the module docstring names the rejected substring substitution and why the compose credentials make it fail by default rather than in an edge case
- `src/taskmanager/infrastructure/clock.py` (26 lines) - `SystemClock` with a single `now()`; the docstring explains why there is no base class (the port is a `Protocol`) and why the instant is aware
- `tests/unit/infrastructure/test_database_url.py` (90 lines) - five tests and one `_settings` helper that controls the whole environment through `monkeypatch`, including `delenv("TEST_DATABASE_URL")`, so no test depends on the developer's shell
- `tests/unit/infrastructure/test_clock.py` (36 lines) - three tests, with the `test_ports.py` docstring rationale for why the conformance proof is static and `make typecheck` is the real gate
- `src/taskmanager/infrastructure/config/settings.py` (+11) - one field and the comment recording the both-ends-or-neither rule
- `.env.example` (+20, -1) - the `TEST_DATABASE_URL` key with its consumer and its fallback named, and the expanded `DATABASE_URL` block carrying the commented compose form
- `tests/unit/test_settings.py` (+21) - `test_test_database_url_defaults_to_none` and `test_test_database_url_is_read_from_the_environment`; `ENV` and the parity test are unchanged

## Decisions Made

- **RESEARCH Pitfall 6 option (a), as recommended, and the smell is documented rather than hidden.** A test-only key on the production settings object is mildly wrong; the alternatives are worse. Option (b) - keeping the key out of both `Settings` and `.env.example` and reading it with `os.environ` in the integration conftest - contradicts the CONTEXT canonical-refs note that `.env.example` gains `TEST_DATABASE_URL`, and leaves the key documented only in a README, which is where configuration goes to be forgotten. Option (c) - loosening the parity assertion to a subset - weakens an existing gate to accommodate a new key, which is the wrong direction for a repository whose whole thesis is that its gates are real. The field comment says all of this in four lines, and the ADR 03-11 owes should repeat the one sentence that matters: the key must exist in both places or in neither.
- **The compose `DATABASE_URL` stays commented, and the comment explains the near miss.** The parity test collects key names from lines that contain `=` and do not start with `#`. A second, uncommented `DATABASE_URL=...@db:5432/...` would therefore contribute the same key name and the set equality would still hold - the gate would say nothing - while `python-dotenv` reads the last assignment and the application would dial `db` from a host that has no such name. That is precisely the class of failure this project keeps trying to make impossible, so the near miss is written down next to the line rather than left for the next reader to rediscover.
- **The precedence test breaks the fallback instead of trusting the return value.** `monkeypatch.setattr(module, "derive_test_database_url", _fail)` makes `test_an_explicit_test_database_url_wins` fail if the derivation is consulted at all. The weaker form - assert the returned string equals the explicit setting - passes against an implementation that computes the derivation and discards it, which is a real shape someone refactoring this could produce.
- **`tests/conftest.py` was checked and deliberately left untouched.** The `app` fixture exports only `DATABASE_URL` and `JWT_SECRET` and builds `Settings(_env_file=None)`. An optional field defaulting to `None` is satisfied by that, which the full suite confirms: 172 tests pass, including all the API-level ones that go through the fixture.
- **No requirement tick taken.** The plan's frontmatter lists `DB-01`, but `03-11-PLAN.md` claims it again, along with DB-02/03/04/05, ARC-08, DOCK-02 and DOCK-03. Under the last-claimant convention this project has followed since 02-01, 03-11 owns the tick; taking it here would make `REQUIREMENTS.md` report a complete requirement while eight plans of the phase are unwritten. This is the third consecutive plan in this phase to make the same call.

## Deviations from Plan

None - the plan executed exactly as written. Both tasks produced every artifact the plan specifies, with the contents it specifies, and every acceptance criterion passed on the first run:

- `test_database_url` is in `Settings.model_fields` with default `None`
- `test_env_example_documents_every_field` passes unchanged
- one live `DATABASE_URL=` line, one live `TEST_DATABASE_URL=` line, one commented compose form
- `tests/unit/test_settings.py` reports 7 tests passing (the plan asks for at least 7)
- `tests/unit/infrastructure/test_database_url.py` reports 5 tests passing (the plan asks for at least 5)
- both `python -c` round-trip checks exit 0; both forbidden-form greps print `0`
- `make test` reports `Required test coverage of 75% reached. Total coverage: 100.00%` with `database_url.py` and `clock.py` both at 100%

Worth noting for the record: the prose-not-literal convention that produced a deviation in each of 03-01 and 03-02 was applied *preemptively* here, in both new module docstrings, so the two forbidden-form greps passed without a correction pass. The convention has now paid for itself three plans running and belongs in the phase's ADRs rather than in a fourth deviation entry.

## Issues Encountered

- Nothing. Both tasks passed their full `<verify>` chain on the host (CPython 3.14.3) on the first attempt, `filterwarnings = error` raised nothing, and no pre-commit hook required a reformat.
- **This plan needed no database, and none was started.** Everything here is pure configuration logic: `make_url` parses and renders strings without resolving a host, and `SystemClock` reads the process clock. The host port 5432 collision with `nuestracasa-postgres` that 03-02 recorded is therefore still open and still untouched - it blocks the *host-side* half of plans 03-05 onward, not this one. See **User Setup Required**.

## Known Stubs

None. Both new source modules are complete and fully exercised: `database_url.py` is covered by five tests across both of its functions and its `Final` constant, `clock.py` by three, and the two new `Settings` tests cover the field in both of its states. Coverage over `src/taskmanager` is 100% with no `pragma: no cover` and no `omit` entry.

## Threat Flags

None new. This plan opens no network endpoint, adds no auth path, installs nothing (`requirements.txt` untouched, so T-3-SC stays `accept`) and reads no user input. The register's three `mitigate` rows are implemented:

- **T-3-10** (information disclosure through a rendered URL) - *mitigated*: `hide_password=False` appears exactly once, at the one call that must produce a live connection string, with an inline comment forbidding it anywhere a URL reaches a message. The masking default was checked and does mask: `postgresql+psycopg://taskmanager:***@localhost:5432/taskmanager_test`. Plan 03-05's fail-fast fixture is the next place this rule applies, and it is named in the comment.
- **T-3-11** (a real credential in the tracked example file) - *mitigated*: the added `TEST_DATABASE_URL` uses the same obviously-fake `taskmanager:taskmanager` pair the compose file and CI already publish; `.env` remains in `.gitignore` and `.dockerignore`, and pre-commit's `detect-private-key` hook is unchanged and passed on both commits.
- **T-3-12** (a default that weakens configuration) - *mitigated*: the one new default is `None` on a field that is never read in production; no secret gained a default, and `extra="forbid"` is untouched.

One item to hand forward rather than file as a threat: `resolve_test_database_url` will happily return a URL pointing at the *application* database if someone sets `TEST_DATABASE_URL` to it, and the D-01 fixture rolls back rather than truncating, so the damage would be bounded but not zero. Plan 03-05's fixture is the right place to refuse a resolved test URL whose database name is not `taskmanager_test` - the constant is already exported for exactly that comparison.

## User Setup Required

None for this plan - it touches no database and no container.

Still open from 03-02, and still blocking the host-side half of the plans that follow: host port 5432 is held by `nuestracasa-postgres`, an unrelated container belonging to another project. Until it is stopped or republished, a host-side `DATABASE_URL=...@localhost:5432/...` resolves to *that* server rather than this project's, and the failure presents as an authentication error rather than a wrong-database one.

```
docker stop nuestracasa-postgres      # or republish it on another host port
cd <this repo> && docker compose up -d db
```

Also still true: this repository has no `.env`. Nothing so far has needed one, but `cp .env.example .env` becomes the evaluator's first step the moment plan 03-10's `api` and `test` services land - and it is that copy, against `extra="forbid"`, that this plan's single field exists to keep working.

## Next Phase Readiness

- **Plan 03-05's integration conftest has its URL source.** `resolve_test_database_url(get_settings())` is the whole of it; no fixture needs to know about the precedence rule or the derivation, and neither should be re-expressed there.
- **Plans 03-04 onward have their clock.** `SystemClock()` is the production counterpart of `FrozenClock` and satisfies the same annotation, so a use case constructed with either type-checks identically. It is not yet wired into any composition root - plan 03-09 owns that, alongside the engine and session factory.
- **`TEST_DATABASE_NAME` is exported for reuse, not just for the derivation.** Plan 03-05's fail-fast fixture should compare the resolved URL's database name against it before connecting, which turns the hand-forward threat note above into a gate.
- **The ADR debt for this phase grows by one.** 03-11 already owes ADRs for the PostgreSQL 18 volume path, the literal-constraint-names-in-revisions rule and the case-sensitivity contrast. Add: why a test-only key lives on the production `Settings` class. It is the kind of thing an evaluator reads as sloppiness unless the reasoning is one click away.
- No blockers, one pre-existing environment action (see above).

## Self-Check: PASSED

All four created files exist on disk (`src/taskmanager/infrastructure/config/database_url.py`, `src/taskmanager/infrastructure/clock.py`, `tests/unit/infrastructure/test_database_url.py`, `tests/unit/infrastructure/test_clock.py`), the three modified files carry the intended diffs, and both task commits (`c389e41`, `4d9833d`) are present in `git log`. Neither commit deleted a tracked file (`git diff --diff-filter=D` is empty for both). `make lint && make typecheck && make arch && make test` was run green after each: 172 passed, 100.00% coverage, three contracts KEPT.

---
*Phase: 03-persistence-runnable-stack*
*Completed: 2026-09-18*
