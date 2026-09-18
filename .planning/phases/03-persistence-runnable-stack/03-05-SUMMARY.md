---
phase: 03-persistence-runnable-stack
plan: 05
subsystem: testing
tags: [integration-tests, pytest, alembic, postgres, savepoint, constraints, d-01, d-02, d-03, db-04, db-05]

# Dependency graph
requires:
  - phase: 03-persistence-runnable-stack
    plan: 01
    provides: the three ORM rows, the twelve Final constraint names and the declarative Base whose naming convention renders them
  - phase: 03-persistence-runnable-stack
    plan: 02
    provides: alembic.ini with no URL key, the synchronous env.py with its configure_logging and connection attributes, and 0001_baseline
  - phase: 03-persistence-runnable-stack
    plan: 03
    provides: resolve_test_database_url() and TEST_DATABASE_NAME - the single expression of D-04's precedence and the name the destructive fixture checks against
  - phase: 03-persistence-runnable-stack
    plan: 04
    provides: violated_constraint(), whose positive branch had no test that could run without a real server
provides:
  - tests/integration/conftest.py - six fixtures implementing D-01 through D-04, plus alembic_config() as the one place the Config shape is written
  - tests/integration/test_migrations.py - upgrade, alembic check, downgrade base proven without destroying the session, and a one-revision vacuity guard
  - tests/integration/test_schema.py - foreign keys, cascade actions, VARCHAR-not-ENUM, timestamptz everywhere, no server defaults, and an aware-UTC round trip
  - tests/integration/test_constraints.py - twelve insert-and-refuse / delete-and-observe proofs, each asserting the constraint name
  - The empirical settlement of RESEARCH assumptions A2 (psycopg fills diag.constraint_name for foreign-key violations too) and A4 (timestamptz round-trips aware)
affects: [03-06, 03-07, 03-08, 03-09, 03-10, 03-11, 04-crud-endpoints, 05-auth]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Everything session-scoped in the integration harness is synchronous, which is not a compromise: Alembic is synchronous and the reachability probe is one SELECT, so ADR-012's function-scoped event loop costs nothing"
    - "A fail-fast fixture raises its failure AFTER the except block, not inside it, so pytest does not print the driver's exception chain above the one line that says what to do"
    - "A destructive fixture checks the database NAME before it opens a connection, using the constant the URL resolver exports for exactly that purpose"
    - "An expected IntegrityError is wrapped in a savepoint, because a refused statement aborts the transaction the isolation fixture owns"
    - "A constraint test asserts the constraint NAME through the same function the production translation uses, so a rename breaks the test before it breaks the 409"

key-files:
  created:
    - tests/integration/__init__.py
    - tests/integration/conftest.py
    - tests/integration/test_migrations.py
    - tests/integration/test_schema.py
    - tests/integration/test_constraints.py
  modified: []

key-decisions:
  - "migrated_database refuses any database whose name is not taskmanager_test, before connecting. The fixture drops every table it finds; TEST_DATABASE_NAME is exported by 03-03 precisely so the check can be made here (T-3-18). Added beyond the plan's letter, on the prior wave's handoff note"
  - "The D-03 failure is raised outside the except block. Raised inside it, the Failed carries the driver error in __context__ and pytest prints two tracebacks above the instruction - the exact outcome the fixture exists to prevent. Verified both ways"
  - "alembic_config() lives in conftest.py and test_migrations.py imports it, rather than each file building its own Config. The Pitfall 4 argument for configure_logging=False is written once, where it cannot go stale in one copy"
  - "The timestamp round trip asserts utcoffset() == 0 as well as instant equality, and the docstring says plainly that the first assertion pins the server's session timezone rather than the column type. A server not on UTC is a configuration problem this suite should report"
  - "No requirement tick taken: 03-11 is the last claimant of DB-02, DB-04 and DB-05, as it is of DB-01/03, ARC-08, DOCK-02 and DOCK-03. Fifth consecutive plan in this phase to make the same call"

patterns-established:
  - "tests/integration/ is now a package with a conftest that owns the whole database lifecycle: plans 03-06 through 03-09 add test modules and no infrastructure"
  - "From this commit onward `make test` requires a reachable PostgreSQL. That is D-03 working as designed, and the failure message is part of the deliverable"

requirements-completed: []

# Metrics
duration: 11min
completed: 2026-09-18
---

# Phase 3 Plan 05: Integration Harness and Schema Proofs Summary

**The suite now talks to a real PostgreSQL: a session-scoped fixture rebuilds `taskmanager_test` with the actual migration (never a metadata shortcut), every test runs inside an outer transaction that is rolled back so a stray `commit()` is discarded rather than tidied away, and twenty-two tests prove what `alembic check` structurally cannot — that each CHECK refuses the value it names, that each cascade really deletes, and that a timestamp comes back the instant it went in. Total coverage over `src/taskmanager` reached 100%: the last uncovered line in the project, `violated_constraint()`'s positive branch, is now driven by a foreign-key violation from a live server.**

## Performance

- **Duration:** 11 min
- **Started:** 2026-09-18T22:45Z
- **Completed:** 2026-09-18T22:56Z
- **Tasks:** 3
- **Files modified:** 5 created, 0 modified

## Accomplishments

- **Six fixtures, and the order between them is the design.** `database_url` (session, sync) asks `resolve_test_database_url(get_settings())` and nothing else — D-04's precedence is not restated here, because a second copy of a precedence rule is a second thing to keep true. `_require_database` (session, sync) opens one connection and executes one `SELECT 1`. `migrated_database` (session, sync) runs `downgrade base` then `upgrade head` on a connection it owns. `connection` (function, async) opens the outer transaction and rolls it back in a `finally`. `session_factory` (function, sync) closes over that connection with `join_transaction_mode="create_savepoint"`. `session` (function, async) hands out one session and closes it. Nothing session-scoped is a coroutine, so ADR-012's function-scoped loop never gets a fixture that outlives it.
- **The D-03 message is an instruction, and it was tuned until it read like one.** Against an unreachable host the whole suite produces this and nothing else:

  ```
  PostgreSQL is not reachable at postgresql+psycopg://x:***@127.0.0.1:1/x.
  Start it with `make up`, or run the whole suite inside Docker with `make docker-test`.
  Underlying error: OperationalError: (psycopg.OperationalError) connection failed: ...
  ```

  The password is masked by `render_as_string()`'s default — a run with the literal password `secret` greps zero matches — and there is no `Traceback` block anywhere in the output. Getting the second property required raising the failure *after* the `except` block rather than inside it; the first attempt printed two chained driver tracebacks above the instruction, which is precisely the experience this fixture exists to remove. Both versions were run and compared.
- **`downgrade base` is proven without wrecking the session.** The test opens its own connection, begins a transaction, hands the connection to Alembic through `config.attributes`, runs the downgrade, asserts inside that same transaction that none of the three tables exist, and then rolls back. PostgreSQL's DDL is transactional, so the schema comes back with the rollback and the twenty-one tests that run afterwards still find it. `docker compose exec db psql -tAc "SELECT count(*) ... IN ('users','task_lists','tasks')"` prints `3` after the run.
- **`alembic check` is clean, and the suite says out loud what it does not prove.** The drift test re-reports `AutogenerateDiffsDetected` with `pytrace=False`, because Alembic's own diff summary is the entire useful message. Both `test_migrations.py` and `test_constraints.py` carry the Pitfall 8 argument in their docstrings: autogenerate does not compare CHECK constraints at all, so a revision dropping `ck_tasks_status` would be reported as no drift, and only an insert PostgreSQL refuses can say otherwise.
- **The schema is asserted against the live catalogue, not against `Base.metadata`.** Reflected foreign keys give `fk_task_lists_owner_id_users` → `users`, `ondelete=CASCADE`, `owner_id` NOT NULL; `fk_tasks_task_list_id_task_lists` CASCADE and NOT NULL beside `fk_tasks_assignee_id_users` SET NULL and nullable. `tasks.status` and `tasks.priority` reflect as `VARCHAR(16)`, and `pg_type` holds no user-defined enum type in `public`. Every `timestamp*` column of the three tables is `timestamp with time zone`, with a vacuity guard so an empty reflection cannot make that true about nothing. No column of the three tables carries a `column_default`, so the `Clock` port stays the only source of time.
- **A4 is settled by a round trip, not by a citation.** An aware UTC value with non-zero microseconds goes in through bound parameters and comes back aware, at zero offset, equal to what went in. That is what makes `NaiveDatetimeFromDatabaseError` a tripwire rather than a live path — plan 03-04 wrote the guard on the strength of an assumption, and this is where the assumption becomes a fact.
- **Twelve constraint proofs, each naming the constraint.** `ck_tasks_status` refuses `archived`; `ck_tasks_priority` refuses `urgent`; `ck_tasks_completed_at_matches_status` refuses a completed task with no timestamp *and* a pending task with one, which is why it is written as an equivalence rather than an implication. `uq_task_lists_owner_id_name` refuses a duplicate, while `Groceries` beside `groceries` is **accepted** for one owner and `Groceries` is accepted for a second owner — the case-sensitivity decision of 03-01 stated empirically. `uq_users_email_lower` refuses `OWNER@EXAMPLE.TEST` after `owner@example.test`, the deliberate opposite. Deleting a list empties its tasks; deleting a user removes their lists and, through them, the tasks; deleting an assignee leaves the task standing with `assignee_id IS NULL`. Every refusal asserts through `violated_constraint()`, so a constraint renamed in the schema but not in `constraints.py` fails here before it silently turns LIST-06's 409 into a 500.
- **A2 is settled too, and it closes the project's last coverage gap.** `test_a_task_in_a_missing_list_is_refused` asserts `violated_constraint(error) == FK_TASKS_TASK_LIST_ID_TASK_LISTS`, which proves psycopg populates `diag.constraint_name` for foreign-key violations and not only for unique and check ones. 03-04 left that branch deliberately uncovered because a populated `Diagnostic` has no public constructor; it now runs against a real server response. **Coverage over `src/taskmanager` is 100.00%** — 474 statements, 0 missed, 50 branches, 0 partial — with the gate still at 75 and no `pragma` and no `omit` anywhere.
- **All four gates green, twice.** `make lint && make typecheck && make arch && make test`: 79 files black/isort clean, flake8 clean, mypy strict clean over 79 source files, three import-linter contracts KEPT, **216 passed** under `filterwarnings = error`. Run back to back, `make test` reports 216 both times and `SELECT count(*) FROM users` on the test database prints `0` afterwards — D-01 isolation holds with nothing escaping and nothing accumulating.

## Task Commits

Each task was committed atomically:

1. **Task 1: the integration fixtures and the migration proofs** — `0ae9b53` (test)
2. **Task 2: schema-shape proofs — owner_id, timestamptz, VARCHAR not ENUM** — `1133224` (test)
3. **Task 3: insert-and-refuse proofs for every D-12 constraint, plus the cascade** — `6a0d743` (test)

**Plan metadata:** see the `docs(03-05)` commit that carries this SUMMARY.

## Files Created/Modified

- `tests/integration/__init__.py` (0 lines) — the package marker that lets `test_migrations.py` import `alembic_config` from the conftest by its real dotted name
- `tests/integration/conftest.py` (259 lines) — six fixtures, `alembic_config()`, and the database-name refusal. The module docstring names four shapes a reader may expect and explains the absence of each: no sweep that empties the tables, no database per test, no metadata create-everything shortcut, no session-scoped async fixture
- `tests/integration/test_migrations.py` (113 lines) — 4 tests: the exact table set, `alembic check`, the rolled-back downgrade, and the one-revision guard
- `tests/integration/test_schema.py` (222 lines) — 6 tests over reflection, `information_schema.columns`, `pg_type` and one async round trip
- `tests/integration/test_constraints.py` (399 lines) — 12 tests, three `INSERT` statement constants, three `*_values()` parameter builders, one `given_a_list_with_an_owner()` setup helper and one `refused()` helper carrying the savepoint argument

## Decisions Made

- **The destructive fixture refuses a database that is not `taskmanager_test`, and the check happens before any connection is opened.** `migrated_database` runs `downgrade base`; against the application database, or against anything shared, that is a schema wipe with no confirmation step. Plan 03-03 exported `TEST_DATABASE_NAME` from the URL resolver for exactly this, and the prior-wave handoff asked for the guard. It sits in `migrated_database` and not in `database_url` on purpose: the reachability probe must still run first, so an unreachable host produces the D-03 instruction rather than a name complaint, and the guard only fires on the path that actually destroys something (T-3-18).
- **The fail-fast failure is raised outside its `except` block.** An exception raised while another is being handled carries the first in `__context__`, and pytest prints the whole chain above the message — for an unreachable database that is two driver tracebacks in front of one line of instruction. The fixture therefore records the caught exception, disposes the engine in a `finally`, and calls `pytest.fail` afterwards. The docstring says why, because the shape looks like needless indirection until you have seen the other output. Both versions were run; the diff in the failure report is the whole justification.
- **`alembic_config()` is a conftest-level function, imported by `test_migrations.py`.** The plan asks the test to "build the same `Config` shape". Building it twice would put the Pitfall 4 argument — `configure_logging: False`, and which `caplog` assertions it protects — in two places, and a comment that exists twice is a comment that will be right once. Importing from the conftest is legal here because `tests/` and `tests/integration/` are both packages, so pytest imports the module under the same dotted name the test does.
- **The timestamp test asserts the offset as well as the instant, and says what each assertion really pins.** `stored == CREATED_AT` is the offset-independent claim and the stronger one. `stored.utcoffset() == timedelta(0)` pins the *session timezone*, which is a property of the server rather than of the column — the compose database and the CI service container both run UTC, and one that did not would be a configuration problem worth failing on. The docstring states the distinction so a future reader who hits it knows which of the two assertions moved.
- **The constraint tests assert names, not exception types.** `pytest.raises(IntegrityError)` alone would pass for a violation of any constraint in the schema, including one a badly written test caused by accident. Reading the name through `violated_constraint()` — the same function D-13's translation will call — means this suite is also a test of that function against a real server, and a rename applied to the schema but not to `constraints.py` fails here rather than in production as an untranslated 500.
- **`refused()` exists to own the savepoint argument once.** A statement PostgreSQL rejects aborts the transaction; every later statement answers `current transaction is aborted` until it is unwound. Since the transaction belongs to the `connection` fixture and must survive to teardown, each expected failure runs inside `connection.begin_nested()`. The explanation is written once, in the helper's docstring, instead of being a comment repeated seven times.
- **No requirement tick taken.** The plan's frontmatter lists `DB-02`, `DB-04` and `DB-05`; `03-11-PLAN.md` claims all three again, along with DB-01/03, ARC-08, DOCK-02 and DOCK-03. Under the last-claimant convention this project has followed since 02-01, 03-11 owns the tick. Fifth consecutive plan in this phase to make the same call.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 — Missing safeguard] `migrated_database` refuses a database that is not `taskmanager_test`**

- **Found during:** Task 1
- **Issue:** The fixture runs `command.downgrade(config, "base")`, which drops every table. Nothing in the plan's fixture list checked *which* database it was about to do that to; an exported `TEST_DATABASE_URL` pointing at the application database — a plausible typo, since the two DSNs differ by one word — would have emptied it silently.
- **Fix:** `_refuse_a_database_that_is_not_the_test_one()` compares `make_url(url).database` against `TEST_DATABASE_NAME` and calls `pytest.fail(..., pytrace=False)` on a mismatch, before any connection is opened. Placed inside `migrated_database` so the D-03 reachability failure still comes first on an unreachable host, which keeps every acceptance criterion of Task 1 intact (verified).
- **Files modified:** `tests/integration/conftest.py`
- **Commit:** `0ae9b53`

**2. [Rule 1 — Output defect] The D-03 message was printed under two driver tracebacks**

- **Found during:** Task 1
- **Issue:** The research snippet calls `pytest.fail` from inside the `except` block. Run that way, pytest printed the psycopg `OperationalError`, then `The above exception was the direct cause of the following exception:`, then the SQLAlchemy wrapper, then `During handling of the above exception, another exception occurred:`, and only then the instruction. D-03's whole promise is "an instruction rather than a traceback", and the plan's acceptance criterion forbids a traceback block from the fixture.
- **Fix:** The caught exception is stored, the engine is disposed in a `finally`, and `pytest.fail` is called after the block. Output is now the three-line message and nothing else; `grep -c Traceback` on the run prints `0`.
- **Files modified:** `tests/integration/conftest.py`
- **Commit:** `0ae9b53`

**3. [Rule 3 — Blocking] Two docstring first lines exceeded 88 characters**

- **Found during:** Task 3
- **Issue:** `flake8` E501 on two one-line summaries that black cannot rewrap.
- **Fix:** One was expanded into a short multi-line docstring that says more than the line it replaced (the `=`-not-implication argument for `ck_tasks_completed_at_matches_status`); the other was shortened.
- **Files modified:** `tests/integration/test_constraints.py`
- **Commit:** `6a0d743`

Everything else executed as written. Every acceptance criterion of all three tasks passed: `join_transaction_mode="create_savepoint"` appears once, `"configure_logging": False` once, `create_all` and `TRUNCATE` appear nowhere under `tests/integration/` (both described in prose instead — the project's prose-not-literal convention, now applied a sixth and seventh time), `set_main_option` prints `0` for both files, `violated_constraint` appears on 10 lines against a floor of 8, `begin_nested` once, f-string SQL zero times in both new test modules, the three tables still stand after the downgrade test, `tests/api/test_error_contract.py` passes in the same session as a migration run, and `make test` twice in a row reports 216 both times with an empty `users` table afterwards.

## Issues Encountered

- **`black` reformatted the two new test modules once each** (a dict comprehension and a list comprehension it wanted broken differently). `make format` then `make lint`; no behavioural change.
- **No `.env` file exists in this repository by design**, so `DATABASE_URL`, `TEST_DATABASE_URL` and `JWT_SECRET` were exported in the shell for every test run. `pre-commit` does not run `pytest` — its twelve hooks are the formatters, the linters, mypy and import-linter — so the commits themselves needed no database.
- The port 5432 collision recorded by 03-02, 03-03 and 03-04 is **resolved**: `test-db-1` is up and healthy on `0.0.0.0:5432`, both databases exist, and the whole plan ran against it.

## Known Stubs

None. All five files are complete. The `session` fixture is used by no test in this plan — the repository tests that consume it arrive in 03-06 and 03-07 — but it is a finished, typed, documented fixture rather than a placeholder, and pytest does not execute an unrequested fixture, so it costs no coverage and hides no gap. The `uow` fixture it will sit beside is deliberately absent until the unit-of-work adapter exists in 03-08; adding it now would mean importing a class that has not been written.

## Threat Flags

None new. This plan opens no endpoint, adds no auth path, installs nothing (`requirements.txt` untouched, so T-3-SC stays `accept`) and reads no user input. The register's five `mitigate` rows are implemented:

- **T-3-10** (a live DSN in a CI log) — *mitigated*: `_require_database` renders the URL with `render_as_string()`'s masking default. A run with the password `secret` and `grep -c secret` over the full output prints `0`.
- **T-3-17** (SQL construction habits) — *mitigated*: every statement in all three modules is `text()` with bound parameters. `grep -cE 'f"(INSERT|SELECT|UPDATE|DELETE)'` prints `0` for `test_schema.py` and for `test_constraints.py`.
- **T-3-18** (a downgrade destroying real data) — *mitigated twice*: the downgrade test runs inside a transaction it rolls back, and `migrated_database` refuses outright any database not named `taskmanager_test` before opening a connection. The three tables are re-counted after the suite and print `3`.
- **T-3-19** (residue between runs) — *mitigated*: `make test` back to back reports 216 both times, and `SELECT count(*) FROM users` on the test database prints `0` afterwards.
- **T-3-02** and **T-3-03** (a CHECK or a cascade quietly not being enforced) — *mitigated*: six insert-and-refuse tests and three delete-and-observe tests, each asserting the constraint name or the surviving row state.

## User Setup Required

None new. `docker compose up -d db` (or `make up`) must be running before `make test`, which is D-03 working as designed rather than a setup step to remove. Until `.env` exists on a given machine, `DATABASE_URL` and `JWT_SECRET` must be present in the shell — `cp .env.example .env` is the evaluator's one-time action and it covers both, plus `TEST_DATABASE_URL`.

**`.github/workflows/ci.yml` needs no change, confirmed by reading it rather than by assuming.** Its `env:` block sets `DATABASE_URL=postgresql+psycopg://taskmanager:taskmanager@localhost:5432/taskmanager_test` and `JWT_SECRET`, and sets no `TEST_DATABASE_URL`. `resolve_test_database_url` therefore takes the derivation branch and replaces the database component with `taskmanager_test` — the value it already holds — so CI resolves to the identical URL. The service container's `POSTGRES_DB` is `taskmanager_test`, so the name guard passes and the migration fixture owns a database nothing else in the job uses. The workflow's comment from Phase 1 ("integration tests add a pytest marker rather than new CI infrastructure") turns out to have been accurate.

## Next Phase Readiness

- **Plans 03-06 through 03-09 add test modules and no infrastructure.** `connection`, `session_factory` and `session` are in place; 03-08 adds a `uow` fixture that is three lines over `session_factory`, and nothing else in this conftest has to move.
- **The savepoint decision is now load-bearing rather than theoretical.** `join_transaction_mode="create_savepoint"` is what will let 03-08's isolation proof mean something: the unit of work really commits, the fixture's rollback really discards it, and a second connection really sees nothing. With the default the commit would be a silent no-op and that test would pass for the wrong reason.
- **`violated_constraint()` has a working positive branch and a live example of how to assert on it.** 03-06 and 03-07 can now write "insert a duplicate, expect the domain error" knowing the name lookup works against a real server for unique, check *and* foreign-key violations.
- **Coverage is at 100% with the gate at 75%.** Every line added from here needs its own test to hold that, which is the position this phase wanted to be in before the repositories land.
- **ADR debt for 03-11 grows by one, a small one.** Add the note that `make test` requires PostgreSQL from this phase onward, with the D-03 reasoning: an auto-skip would let a run report green having exercised none of the persistence layer, which is the opposite of what a graded deliverable wants. The existing debt — the PostgreSQL 18 volume path, the literal constraint names in revisions, the case-sensitivity contrast, the test-only key on `Settings`, and the WR-05 resolution — is unchanged.
- No blockers.

## Self-Check: PASSED

All five created files exist on disk (`tests/integration/__init__.py`, `conftest.py`, `test_migrations.py`, `test_schema.py`, `test_constraints.py`), and all three task commits (`0ae9b53`, `1133224`, `6a0d743`) are present in `git log`. No commit deleted a tracked file, and `git status --short` was clean after each. `make lint && make typecheck && make arch && make test` was run green before every commit: 216 passed, 100.00% coverage over `src/taskmanager` with the gate at 75%, three contracts KEPT.

---
*Phase: 03-persistence-runnable-stack*
*Completed: 2026-09-18*
