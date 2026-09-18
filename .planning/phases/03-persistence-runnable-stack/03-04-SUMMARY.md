---
phase: 03-persistence-runnable-stack
plan: 04
subsystem: infrastructure
tags: [mappers, orm, entities, error-translation, integrityerror, wr-05, d-13, unit-test]

# Dependency graph
requires:
  - phase: 02-domain-error-contract
    provides: the three entities with their __post_init__ guards, the closed DomainError hierarchy, the Details alias that forbids a constraint name in an error body, and the deferred WR-05 question
  - phase: 03-persistence-runnable-stack
    plan: 01
    provides: UserRow / TaskListRow / TaskRow, the twelve Final constraint names, and the declarative Base
provides:
  - src/taskmanager/infrastructure/db/mappers.py - nine functions translating all three aggregates in both directions, plus the _aware() guard that is WR-05's answer
  - src/taskmanager/infrastructure/db/errors.py - NaiveDatetimeFromDatabaseError (the WR-05 infrastructure fault) and violated_constraint() (the key D-13's translation turns on)
  - The decision that a naive datetime read from the database is an infrastructure fault outside the DomainError hierarchy, written into two module docstrings and pinned by four tests
affects: [03-05, 03-06, 03-07, 03-08, 03-09, 03-11, 04-crud-endpoints, 05-auth]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A pair of @overload stubs is what lets one guard serve both a mandatory and a nullable column: passing created_at through returns datetime, passing due_date through returns datetime | None, so no call site needs a cast and none can silently widen a required field"
    - "An exception forwards its *distinguishing value* to super().__init__(), never its rendered message, and assembles the message in __str__ - the shape B042 asks for and the one that survives copy.copy(), matching domain.exceptions.DomainError"
    - "A driver exception is inspected with a real `if isinstance(...)` where the negative branch is reachable, and with an assertion only where it is not - the difference between this module and presentation/api/errors/handlers.py, recorded in both"
    - "A branch that only a real server can produce is left uncovered and named in the docstring, rather than covered by a hand-built stand-in that would pass against a broken implementation too"
    - "An alternative form a grep gate forbids is described in prose rather than spelled as a literal - the 01-04 Makefile convention, now applied a fifth time"

key-files:
  created:
    - src/taskmanager/infrastructure/db/mappers.py
    - src/taskmanager/infrastructure/db/errors.py
    - tests/unit/infrastructure/test_mappers.py
    - tests/unit/infrastructure/test_errors.py
  modified: []

key-decisions:
  - "WR-05 resolved as RESEARCH Open Question 5 recommends: D-14 is refined by scope, not by error type. A naive datetime reaching the domain is still a ValidationError; the mapper additionally refuses one at the infrastructure boundary with NaiveDatetimeFromDatabaseError, a RuntimeError deliberately outside the DomainError hierarchy, so a schema regression becomes the fixed 500 and never a 422 naming a column no request contains"
  - "errors.py was created in Task 1 rather than Task 2, because mappers.py imports NaiveDatetimeFromDatabaseError from it and the plan ordered the two the other way round; Task 2 added violated_constraint() to the same module (Rule 3)"
  - "NaiveDatetimeFromDatabaseError takes `column` positionally, not keyword-only: flake8-bugbear B042 refuses a keyword-only exception parameter outright, and forwarding the rendered message instead of the column would rebuild the error with its own message as the column name under copy.copy()"
  - "violated_constraint's positive branch is left to the integration suites of 03-06/03-07. A populated psycopg Diagnostic has no public constructor, and a hand-built stand-in would prove only that this module can read an attribute off an object the test wrote - true of a broken implementation too"
  - "A bare psycopg.Error is a real, not a faked, second None path: its Diagnostic carries no constraint name, which is what a driver-level failure looks like, so the isinstance-true branch is covered without PostgreSQL"
  - "No requirement tick taken: 03-11 is the last claimant of DB-03 and DB-04, as it is of DB-01/02/05, ARC-08, DOCK-02 and DOCK-03"

patterns-established:
  - "infrastructure/db/ now holds the two pure modules every repository is built from - mappers.py (what a row means) beside errors.py (what a failure means) - both unit-testable with no database, which is where this phase's cheap coverage comes from"

requirements-completed: []

# Metrics
duration: 16min
completed: 2026-09-18
---

# Phase 3 Plan 04: ORM Mappers and IntegrityError Inspection Summary

**All three aggregates now round-trip entity → row → entity with no field lost and both enums surviving as enums, and the two questions this phase inherited are answered in code rather than in a comment: a naive timestamp read from the database raises `NaiveDatetimeFromDatabaseError` — provably *not* a `DomainError`, so a schema regression cannot be reported to a client as their validation problem — and `violated_constraint()` hands D-13's translation the constraint name or an honest `None` that means "re-raise", with both of its reachable branches tested and no `type: ignore` anywhere.**

## Performance

- **Duration:** 16 min
- **Started:** 2026-09-18T22:15Z
- **Completed:** 2026-09-18T22:31Z
- **Tasks:** 2
- **Files modified:** 4 created, 0 modified

## Accomplishments

- **Nine functions, and the ninth is the one that matters.** `user_to_row` / `user_to_entity`, `task_list_to_row` / `task_list_to_entity`, `task_to_row` / `task_to_entity`, plus `apply_user_to_row`, `apply_task_list_to_row` and `apply_task_to_row`. The `apply_*` half exists because a repository's `update()` loads the row the session is already tracking and writes the entity's current values onto it; replacing that row with a freshly constructed one would either detach the original or insert a duplicate. Each of the three carries a comment saying the primary key is deliberately not reassigned — and, where it is not obvious, which *other* field is also held fixed: `task_lists.owner_id` (ownership is set at creation, no use case transfers a list) is, `tasks.task_list_id` is not (moving a task between lists is an ordinary update).
- **Round-trip is proven field by field, not by a single `==`.** `User` and `TaskList` compare with dataclass equality, but `Task` goes through `_assert_tasks_match`, which asserts all eleven fields separately so a failure names the one that was lost rather than printing two long reprs. `test_a_task_with_every_optional_field_set_round_trips` populates `description`, `due_date`, `completed_at` and `assignee_id` together, because four optional fields tested one at a time can still be dropped in combination.
- **Both enums make the trip through a plain string and back.** `to_row` writes `status.value` / `priority.value`; `to_entity` rebuilds with `TaskStatus(...)` / `TaskPriority(...)`. The storage test pins the *type* as well as the value — `type(row.status) is str` — because `StrEnum` members compare equal to their own value, so `row.status == "in_progress"` would also pass for a row that had stored the enum object itself and left the `VARCHAR` column to coerce it. `test_a_status_the_check_constraint_would_refuse_fails_at_the_boundary` sets `"almost_done"` on a row and asserts the `ValueError`: T-3-15 is mitigated by re-validation, not by trust in `ck_tasks_status`.
- **WR-05 is decided, and the decision is visible in three places.** The mapper module docstring carries the reasoning paragraph, `NaiveDatetimeFromDatabaseError`'s own docstring carries the classification, and four tests pin it — one per aggregate plus one for a nullable column, each asserting the column name appears in the message and (for the task case) `not isinstance(raised.value, DomainError)`. Every datetime read from a row passes through `_aware()`, including the nullable ones.
- **One guard serves both column kinds without a cast.** `_aware` is written once with two `@overload` stubs: `datetime → datetime`, `None → None`. Passing `row.due_date` (typed `datetime | None`) resolves through mypy's union math to `datetime | None`, and passing `row.created_at` resolves to `datetime`, so `Task(...)` type-checks strictly with no `cast` and no widening of a required field. The awareness test is `utcoffset() is None`, matching `domain/validation.py::require_utc` rather than the shallower `tzinfo is not None` a reader might expect — a `tzinfo` object is permitted to return `None` for a given instant, and such a value is naive in every way that matters.
- **`violated_constraint()` reads the name and nothing else.** `error.orig` is narrowed with a real `if isinstance(original, psycopg.Error)` — not the assertion idiom `handlers.py` uses — because the `None` result is a documented outcome that a test must reach. Three tests cover the two reachable `None` paths: a non-psycopg original, an `orig` of `None`, and a bare `psycopg.Error` whose `Diagnostic` carries no constraint name. A fourth passes a statement containing an address and a bound parameter dict and asserts nothing but `None` comes back (T-3-13).
- **The exception survives a copy, and there is a test for it.** `NaiveDatetimeFromDatabaseError` forwards the *column* to `super().__init__()` and renders its message in `__str__`. `test_the_naive_datetime_error_survives_a_copy` runs it through `copy.copy()` and asserts the column is still the column — the exact defect flake8-bugbear's B042 points at, and the same trade `domain/exceptions.py` makes for the same reason.
- **All four gates green.** `make lint && make typecheck && make arch && make test`: 74 files black/isort clean, flake8 clean (including bugbear B042, which had to be satisfied rather than suppressed), mypy strict clean over 74 source files, three import-linter contracts KEPT, **194 passed** under `filterwarnings = error`. Coverage 99.62%, gate satisfied; `mappers.py` is at 100% statement *and* branch, `errors.py` at 87% with exactly one uncovered line — the positive branch the plan hands to 03-06/03-07.

## Task Commits

Each task was committed atomically:

1. **Task 1: the explicit ORM ↔ entity mappers and the WR-05 awareness guard** — `827a272` (feat)
2. **Task 2: IntegrityError inspection and the two infrastructure error types** — `d2d2f18` (feat)

**Plan metadata:** see the `docs(03-04)` commit that carries this SUMMARY.

## Files Created/Modified

- `src/taskmanager/infrastructure/db/mappers.py` (194 lines) — nine public functions, one private overloaded guard; the docstring names `registry.map_imperatively` as the rejected alternative and states the concrete cost (every entity would carry SQLAlchemy instrumentation and `tests/architecture/test_domain_is_stdlib_only.py` would go red), then gives WR-05 its paragraph
- `src/taskmanager/infrastructure/db/errors.py` (83 lines) — `NaiveDatetimeFromDatabaseError` and `violated_constraint()`; the docstring names the rejected grab-bag mapping table in the `UnitOfWork` and why per-repository `flush()` plus this inspector replaces it
- `tests/unit/infrastructure/test_mappers.py` (15 tests) — fixed UUID and datetime literals with a comment saying why a generated one would make an equality assertion pass for the wrong reason
- `tests/unit/infrastructure/test_errors.py` (7 tests) — the module docstring states, up front, which branch is deliberately not asserted here and where it *is* proven

## Decisions Made

- **WR-05: refined by scope, exactly as RESEARCH Open Question 5 recommends.** D-14 says a naive datetime reaching the domain is a `ValidationError`, and that stays true and untouched — no domain test changed, no observable HTTP contract moved. What this plan adds is a second, earlier check at a different boundary: a naive datetime arriving *from the database* means the schema stopped promising `TIMESTAMP WITH TIME ZONE`, which is this process's own fault and not a caller's malformed input. Reporting it as a 422 would name a column no request contains and send a client hunting for a mistake they did not make. As a plain `RuntimeError` it reaches Phase 2's catch-all and becomes the fixed 500 body with no message, which is the correct outcome for a schema regression. Per Assumption A4 the branch is unreachable from a correct schema — which is the point: it is a tripwire, not a routine path. **This is the ADR 03-11 owes.**
- **`errors.py` landed in Task 1, not Task 2 (deviation, Rule 3).** The plan puts the module in Task 2 but has Task 1's mapper import `NaiveDatetimeFromDatabaseError` from it, so Task 1 could not pass its own `<verify>` without it. Splitting the module by *symbol* rather than by task — the error type in the first commit, `violated_constraint()` in the second — keeps both commits atomic and green, and keeps every acceptance criterion of both tasks intact. The alternative, reordering the tasks, would have inverted the plan's narrative for no gain.
- **`column` is a positional parameter, against the plan's `*, column: str`.** flake8-bugbear B042 rejects a keyword-only parameter on an exception outright ("It should also not take any kwargs"), and `make lint` is a gate, not advice. The deeper reason to prefer the positional form is the one B042 exists for: `Exception.__reduce__` rebuilds by calling `cls(*self.args)`, so forwarding the rendered message — the obvious shape — would rebuild the error with its own message as the column name after a `copy.copy()`. Forwarding the column and rendering in `__str__` makes that round-trip correct, and `test_the_naive_datetime_error_survives_a_copy` proves it. Call sites still read `NaiveDatetimeFromDatabaseError(column=...)`, which B042 does not object to.
- **The positive branch of `violated_constraint()` is left uncovered on purpose, and said so out loud.** `psycopg.errors.Diagnostic` is populated by libpq from a server response and has no public constructor. A stand-in object carrying a `constraint_name` attribute would assert that this function can read an attribute off an object the test itself wrote — which is equally true of an implementation that ignores the isinstance check, or one that returns the wrong field. The integration suites of 03-06 and 03-07 prove it where it is real, by inserting a duplicate and asserting the `DomainError` that comes back. The module docstring of `test_errors.py` states this in its first paragraph so the gap reads as a decision rather than an omission.
- **A bare `psycopg.Error` gives the isinstance-true path a real test.** Its `Diagnostic` exists but carries `None` for every field — which is what a driver-level failure such as a connection dropped mid-statement actually looks like. That covers the `and original.diag.constraint_name` half of the condition without PostgreSQL and without fabricating anything, and it pins the behaviour that matters: right exception type, still unknowable, still re-raise.
- **`TaskListRow.tasks` is not read by `task_list_to_entity`, and the docstring says why.** The relationship is `lazy="raise"`, and the aggregate this project persists is the list itself; its tasks are loaded by their own repository when a use case asks for them. A mapper that touched the collection would turn every list read into an `InvalidRequestError`.
- **No requirement tick taken.** The plan's frontmatter lists `DB-03` and `DB-04`; `03-11-PLAN.md` claims both again, along with DB-01/02/05, ARC-08, DOCK-02 and DOCK-03. Under the last-claimant convention this project has followed since 02-01, 03-11 owns the tick. This is the fourth consecutive plan in this phase to make the same call.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] `errors.py` created in Task 1 instead of Task 2**

- **Found during:** Task 1
- **Issue:** The plan defines `NaiveDatetimeFromDatabaseError` in `errors.py` under Task 2, but Task 1's `mappers.py` imports it and Task 1's `<verify>` runs `pytest`, `mypy` and `flake8`. Task 1 could not be committed green as written.
- **Fix:** `errors.py` was created in Task 1 containing only `NaiveDatetimeFromDatabaseError`; Task 2 added `violated_constraint()` and its imports to the same file. Both tasks' acceptance criteria were run and passed in their own commits.
- **Files modified:** `src/taskmanager/infrastructure/db/errors.py`
- **Commit:** `827a272` (Task 1), `d2d2f18` (Task 2)

**2. [Rule 3 — Blocking] `NaiveDatetimeFromDatabaseError.__init__` is positional, not keyword-only**

- **Found during:** Task 1
- **Issue:** The plan specifies `__init__(self, *, column: str)`. flake8-bugbear B042 fires on it — "Exception class with `__init__` should pass all args to `super().__init__()` … It should also not take any kwargs" — and `make lint` is a commit gate.
- **Fix:** Signature changed to `__init__(self, column: str)`, with `super().__init__(column)` and the message rendered in `__str__`. This also fixes the `copy.copy()` defect B042 is actually about, and it matches the shape `domain/exceptions.py` already uses. Call sites are unchanged (`column=` is still passed by name). Added `test_the_naive_datetime_error_survives_a_copy` to pin the round trip.
- **Files modified:** `src/taskmanager/infrastructure/db/errors.py`, `tests/unit/infrastructure/test_errors.py`
- **Commit:** `827a272`, `d2d2f18`

**3. [Rule 3 — Blocking] A forbidden literal appeared in a comment**

- **Found during:** Task 2
- **Issue:** The acceptance criterion `grep -c "assert isinstance" src/taskmanager/infrastructure/db/errors.py` must print `0`, but the comment explaining *why this file uses an `if` instead* spelled the forbidden form out.
- **Fix:** Reworded to "the assertion-based narrowing idiom `handlers.py` uses", with a clause noting the gate is why it is described rather than spelled. The project's prose-not-literal convention, now applied a fifth time.
- **Files modified:** `src/taskmanager/infrastructure/db/errors.py`
- **Commit:** `d2d2f18`

Everything else executed exactly as written. Every other acceptance criterion passed on its first run: the nine-function `hasattr` check, the two upward-import greps (both empty), `grep -c "NaiveDatetimeFromDatabaseError"` printing 3, `grep -rn "type: ignore" src/taskmanager/infrastructure/db/` printing nothing, `grep -rn "sqlalchemy\|psycopg" src/taskmanager/application src/taskmanager/domain` printing nothing, `make arch` KEPT × 3, and both `python -c` one-liners exiting 0.

One acceptance criterion could not be run **verbatim** and was verified in a stronger form instead: `pytest … --cov=taskmanager.infrastructure.db.mappers --cov-fail-under=100` fails because `pytest.ini`'s `addopts` already carries `--cov=taskmanager`, and coverage.py unions the two sources rather than replacing one — so the threshold is applied to the whole package, which this one test file naturally does not cover. The per-file number the criterion is asking about was read from the `term-missing` table instead: `mappers.py` **48 statements, 0 missed, 4 branches, 0 partial, 100%** from `test_mappers.py` alone.

## Issues Encountered

- Nothing beyond the three deviations above, all of which were caught by the gates rather than by inspection — which is the point of running them before each commit. `filterwarnings = error` raised nothing, and no pre-commit hook required a reformat on either commit.
- **This plan needed no database, and none was started.** Both modules are pure functions over in-memory objects; a `TaskRow` can be constructed and read without a session. The host port 5432 collision with `nuestracasa-postgres` recorded by 03-02 and 03-03 is therefore still open and still untouched — it blocks the host-side half of plans 03-05 onward, not this one.

## Known Stubs

None. Both modules are complete. `mappers.py` is at 100% statement and branch coverage; `errors.py` has exactly one uncovered line, the `return original.diag.constraint_name` of the positive branch, which is a deliberate and documented hand-off to the integration suites of 03-06 and 03-07 rather than a stub — the code is written, exercised by the negative path, and simply cannot be driven to that line without a real server response. No `pragma: no cover` and no coverage `omit` entry was added.

## Threat Flags

None new. This plan opens no network endpoint, adds no auth path, installs nothing (`requirements.txt` untouched, so T-3-SC stays `accept`) and reads no user input. The register's four `mitigate` rows are implemented:

- **T-3-13** (information disclosure through an error) — *mitigated*: `violated_constraint()` reads `diag.constraint_name` and nothing else; the statement and the bound parameters carried by `IntegrityError` are never touched. `test_no_statement_or_parameter_text_is_returned` passes a statement containing an address and a parameter dict holding the same address, and asserts `None` comes back.
- **T-3-14** (an unrecognised failure leaking detail) — *mitigated*: the `None` result is documented as meaning "re-raise, never no-conflict", in the function docstring and in `test_errors.py`'s own docstring, and `test_an_unknown_constraint_is_not_swallowed` asserts the comparison against `UQ_TASK_LISTS_OWNER_ID_NAME` fails so the caller falls through to its bare `raise`. From there Phase 2's catch-all emits the fixed 500 body, already proven by `tests/api/test_error_contract.py`.
- **T-3-15** (a tampered enum value becoming a live entity state) — *mitigated*: `TaskStatus(row.status)` and `TaskPriority(row.priority)` re-validate at the boundary; `test_a_status_the_check_constraint_would_refuse_fails_at_the_boundary` proves a value that got past `ck_tasks_status` raises instead of rehydrating.
- **T-3-16** (an ordering or expiry decision made on an ambiguous instant) — *mitigated*: `_aware()` refuses every naive datetime, on all three aggregates and on the nullable columns too; four tests, one per aggregate plus one nullable.

## User Setup Required

None for this plan — it touches no database and no container.

Still open from 03-02, and still blocking the host-side half of the plans that follow: host port 5432 is held by `nuestracasa-postgres`, an unrelated container belonging to another project. Until it is stopped or republished, a host-side `DATABASE_URL=...@localhost:5432/...` resolves to *that* server, and the failure presents as an authentication error rather than a wrong-database one.

```
docker stop nuestracasa-postgres      # or republish it on another host port
cd <this repo> && docker compose up -d db
```

## Next Phase Readiness

- **Plans 03-06 and 03-07 have everything they need to be thin.** A repository's `add()` is `session.add(task_to_row(entity))` plus a `flush()` in a `try`, and its `update()` is a `get()` plus `apply_task_to_row(entity, row)`. Neither has to know what a column is called.
- **The D-13 translation has its key, and one obligation attached.** `violated_constraint(error) == UQ_TASK_LISTS_OWNER_ID_NAME` is the whole comparison; the `else` is a bare `raise`. The obligation those plans inherit is coverage: the positive branch of `violated_constraint` is the one uncovered line in `src/taskmanager`, and the duplicate-insert test that closes it is also the test that proves the translation works end to end.
- **Every write path must `flush()`.** Without it the `IntegrityError` surfaces at the use case's `commit()`, where the `UnitOfWork` — not the repository — is holding it, and D-13's "translate in the repository" becomes impossible. `autoflush=False` on the session factory (03-RESEARCH Pattern 1) is what keeps this explicit rather than accidental.
- **The ADR debt for this phase grows by one, and this one is the most load-bearing.** 03-11 already owes ADRs for the PostgreSQL 18 volume path, the literal-constraint-names-in-revisions rule, the case-sensitivity contrast and the test-only key on the production `Settings` class. Add: **the WR-05 resolution** — D-14 refined by scope, with the classification argument and the note that Phase 2's review explicitly deferred it. That is a reviewer-facing decision, not an implementation note.
- No blockers, one pre-existing environment action (see above).

## Self-Check: PASSED

All four created files exist on disk (`src/taskmanager/infrastructure/db/mappers.py`, `src/taskmanager/infrastructure/db/errors.py`, `tests/unit/infrastructure/test_mappers.py`, `tests/unit/infrastructure/test_errors.py`), and both task commits (`827a272`, `d2d2f18`) are present in `git log`. Neither commit deleted a tracked file (`git diff --diff-filter=D HEAD~2 HEAD` is empty) and `git status --short` is clean with no untracked leftovers. `make lint && make typecheck && make arch && make test` was run green before each commit: 194 passed, 99.62% coverage over `src/taskmanager` with the gate at 75%, three contracts KEPT.

---
*Phase: 03-persistence-runnable-stack*
*Completed: 2026-09-18*
