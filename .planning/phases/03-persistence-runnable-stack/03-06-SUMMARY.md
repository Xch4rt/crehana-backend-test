---
phase: 03-persistence-runnable-stack
plan: 06
subsystem: infrastructure
tags: [repositories, sqlalchemy-async, d-13, arc-08, sc-2, sc-4, integration-tests, architecture-gate]

# Dependency graph
requires:
  - phase: 02-domain-error-contract
    provides: the TaskListRepository and UserRepository Protocols, the closed DomainError hierarchy, and the two in-memory fakes whose behaviour these adapters had to match
  - phase: 03-persistence-runnable-stack
    plan: 01
    provides: TaskListRow / UserRow with lazy="raise" on the tasks relationship, and the Final constraint names the translation keys on
  - phase: 03-persistence-runnable-stack
    plan: 04
    provides: the nine mappers (including the apply_* half that update() needs) and violated_constraint()
  - phase: 03-persistence-runnable-stack
    plan: 05
    provides: the integration harness - migrated schema, outer transaction rolled back, and a session factory that joins it by SAVEPOINT
provides:
  - src/taskmanager/infrastructure/db/repositories/task_lists.py - SqlAlchemyTaskListRepository, the shape the task adapter repeats in 03-07
  - src/taskmanager/infrastructure/db/repositories/users.py - SqlAlchemyUserRepository, with the lower(email) lookup and the address-free conflict
  - tests/architecture/test_no_commit_in_repositories.py - the SC-4 gate with its vacuity guard, proven red on a planted violation
  - The empirical finding that opening a SAVEPOINT flushes whatever is pending, which decides where a deliberately bad row must be added in any repository test
affects: [03-07, 03-08, 03-09, 03-10, 03-11, 04-crud-endpoints, 05-auth]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A repository borrows its session and never ends a transaction; the flush in every write path is what keeps the constraint name where it still means something"
    - "The IntegrityError translation is one private NoReturn helper per adapter, called from both write paths - copied into each, one of its branches would be permanently unreachable in whichever method cannot cause that collision"
    - "A repository returns entities built by the mapper, so every field is materialised before the value leaves and the session's lifetime stops being the caller's problem"
    - "An expected refusal runs inside session.begin_nested(), and anything the refusal needs to be pending goes inside the savepoint too - opening one flushes what is already there"
    - "An architecture gate asserts a property of the source text and records, in its docstring, the runtime check it must never be weakened into"

key-files:
  created:
    - src/taskmanager/infrastructure/db/repositories/__init__.py
    - src/taskmanager/infrastructure/db/repositories/task_lists.py
    - src/taskmanager/infrastructure/db/repositories/users.py
    - tests/integration/test_repositories_task_lists.py
    - tests/integration/test_repositories_users.py
    - tests/architecture/test_no_commit_in_repositories.py
    - .planning/phases/03-persistence-runnable-stack/evidence/03-06-no-commit-gate-red.txt
  modified: []

key-decisions:
  - "The constraint translation lives in one private _refused() helper per adapter rather than being copied into add() and update(). Two copies would be two places for the name comparison to age, and the foreign-key branch is unreachable from update() - a copied block would leave a branch no test could ever cover"
  - "The first version of test_an_unrecognised_integrity_error_is_re_raised was green while add() was never called: opening a SAVEPOINT flushes pending work, so the bad row was refused by the savepoint itself. Caught by reading the per-test coverage row, not by the test result"
  - "Two tests were added beyond the plan's list - update() against a missing row, and the users re-raise path - because both are real branches of the adapters and the project holds 100% coverage with the gate at 75%"
  - "The SC-4 gate is a source-text scan, not an AST walk: the property is about the text, and the project's prose-not-literal convention means a mention in a docstring under that package is a violation too. The docstring records the AST upgrade as legitimate and the runtime check as not"
  - "No requirement tick taken: 03-11 is the last claimant of DB-01, DB-03 and ARC-08. Sixth consecutive plan in this phase to make the same call"

patterns-established:
  - "infrastructure/db/repositories/ is now a package under an automated gate: 03-07 adds tasks.py and one line to REQUIRED_SCANNED_MODULES, and inherits the flush-translate-never-commit shape whole"

requirements-completed: []

# Metrics
duration: 15min
completed: 2026-09-18
---

# Phase 3 Plan 06: Task-List and User Repository Adapters Summary

**Two of the three adapters are in, and the three properties that make them honest are now tests rather than intentions: an entity handed back survives the session closing (23 new tests, including the SC-2 read-after-close for both aggregates), a constraint PostgreSQL refuses becomes the business error it means while an unrecognised one escapes untouched, and a repository that ended its own transaction would fail `tests/architecture/test_no_commit_in_repositories.py` — observed red on a planted line naming `users.py:73`, and green again with it removed.**

## Performance

- **Duration:** 15 min
- **Started:** 2026-09-18T23:08Z
- **Completed:** 2026-09-18T23:23Z
- **Tasks:** 3
- **Files modified:** 7 created, 0 modified

## Accomplishments

- **`SqlAlchemyTaskListRepository`, six methods, no base class.** `get` returns `task_list_to_entity(row)` or `None`; `add` inserts and flushes inside a `try`; `update` loads the tracked row, refuses a missing one with `TaskListNotFoundError`, applies the entity in place and flushes the same way; `delete` issues a Core `delete()` and says nothing about a row that was not there; `list_for_owner` is owner-scoped *in SQL* and ordered by `created_at`; `exists_with_name` counts with a case-sensitive comparison. Conformance to the port is structural — mypy checks it where 03-08 assigns the object to a `TaskListRepository`-annotated attribute, exactly as Phase 2's fakes are checked.
- **The translation is written once per adapter and it is a `NoReturn` helper.** `_refused(error, task_list)` compares `violated_constraint(error)` against `UQ_TASK_LISTS_OWNER_ID_NAME` and `FK_TASK_LISTS_OWNER_ID_USERS` and otherwise re-raises the exception unchanged. Both write paths call it. The plan's letter was two copies of the block; the foreign-key branch cannot fire from `update()` (`apply_task_list_to_row` deliberately does not write `owner_id`), so a second copy would have shipped a branch no test could ever reach.
- **SC-2 is a test, twice.** `test_a_returned_entity_is_readable_after_the_session_is_gone` closes the session and then reads `name`, `description`, `owner_id`, `created_at` and `updated_at`; the user suite does the same for its five fields. The docstrings say *why* it cannot raise — the value is a plain dataclass whose fields were copied while the session was open, so there is no instrumented attribute left to load and no SQL to emit outside the greenlet context. An adapter returning the row would fail at the first read.
- **`lazy="raise"` stopped being a setting and became a refusal.** `test_touching_the_tasks_relationship_raises_instead_of_lazy_loading` loads a `TaskListRow` through the session and asserts `InvalidRequestError` on `.tasks`. This is RESEARCH Open Question 4 answered: without it, DB-03's promise is a keyword in `models.py` that nothing exercises.
- **D-13 proven in all three directions, for both aggregates.** A duplicate per-owner name becomes `DuplicateTaskListNameError` whose `details` are exactly `{"field": "name", "name": "Groceries"}` — no constraint name, no SQL. An unknown owner becomes `UserNotFoundError`. A violation the adapter does not recognise (a row with no `name`, added inside the savepoint) escapes as `IntegrityError`, which is the reachable half `tests/unit/infrastructure/test_errors.py` documented it could not reach. The users adapter has the same three: duplicate address, duplicate differing only in case (caught by `uq_users_email_lower`, the deliberate opposite of the task-list index), and a row with no address at all.
- **`get_by_email` folds case on both sides, and there is a test that can tell.** The row it looks up is written with its capitals intact, bypassing `User` the way a seed script or a migration would. An adapter comparing the stored value directly would answer `None` there and let a second account be created for an address that already has one. `func.lower` is also what lets PostgreSQL answer from the expression index rather than scanning.
- **The conflict says nothing, and the test asserts the consequence rather than the intent.** `test_the_conflict_error_does_not_echo_the_address` builds `f"{error} {error.details}"` and asserts the address, the domain `example.test` and the string `uq_users_email_lower` are all absent, and that `details` is exactly `{"field": "email"}`. `EmailAlreadyRegisteredError()` takes no argument, so there is nothing a call site could leak by being helpful (T-3-13).
- **The SC-4 gate, and the proof that it is not decorative.** `test_no_repository_commits_its_own_transaction` reports `file:line` for every offending line; `test_the_repositories_package_is_actually_scanned` fails if the package moves or empties. A line was planted in `users.py`, the test named `users.py:73`, the line was removed and the test went green — both runs in `evidence/03-06-no-commit-gate-red.txt`, with nothing else changed between them.
- **All four gates green before every commit.** `make lint && make typecheck && make arch && make test`: 85 files black/isort clean, flake8 clean, mypy strict clean over 85 source files with no `type: ignore` anywhere in the new package, three import-linter contracts KEPT, **239 passed** under `filterwarnings = error`. **Coverage over `src/taskmanager` is 100.00%** — 560 statements, 0 missed, 58 branches, 0 partial — gate still at 75, no `pragma`, no `omit`.

## Task Commits

Each task was committed atomically:

1. **Task 1: the task-list adapter and its integration proofs** — `81e9afb` (feat)
2. **Task 2: the user adapter and its integration proofs** — `5de7e50` (feat)
3. **Task 3: the SC-4 architecture gate, with red/green evidence** — `4227a93` (test)

**Plan metadata:** see the `docs(03-06)` commit that carries this SUMMARY.

## Files Created/Modified

- `src/taskmanager/infrastructure/db/repositories/__init__.py` (0 bytes) — the package marker; the gate scans the directory, so the package is the unit the rule applies to
- `src/taskmanager/infrastructure/db/repositories/task_lists.py` (178 lines) — the adapter and the `_refused` translator. The docstring names both rejected shapes (a repository that ends its own transaction, a repository that returns rows) and states the flush argument once for the whole package
- `src/taskmanager/infrastructure/db/repositories/users.py` (98 lines) — the sibling, plus the paragraph on why the conflict carries no address
- `tests/integration/test_repositories_task_lists.py` (400 lines) — 12 tests, a `refused()` savepoint helper, an `a_task_list()` builder and a `given_an_owner()` setup that writes through the mapper rather than through the other adapter
- `tests/integration/test_repositories_users.py` (255 lines) — 9 tests, including the two that write a row without the entity so the lookup and the index are tested against something `User` did not canonicalise
- `tests/architecture/test_no_commit_in_repositories.py` (98 lines) — 2 tests, structurally matching `test_domain_is_stdlib_only.py`: the same hop-count comment, the same vacuity guard, the same violation-list assertion
- `.planning/phases/03-persistence-runnable-stack/evidence/03-06-no-commit-gate-red.txt` — the planted-violation run and the clean one

## Decisions Made

- **One `_refused()` helper per adapter, called from every write path.** The plan describes the `try`/`except` block twice — once in `add`, once in `update` — and that is the shape research sketched. Two copies would be two places for the constraint-name comparison to fall out of date, and, more concretely, the `FK_TASK_LISTS_OWNER_ID_USERS` branch cannot fire from `update()`: `apply_task_list_to_row` deliberately does not write `owner_id`, because ownership is fixed at creation. A copied block would therefore have contained a branch that no test could ever cover, which on a project holding 100% coverage means either a `pragma` (forbidden) or a permanently red number. The helper is annotated `NoReturn`, so mypy knows the call does not fall through, and it is not syntactically inside an `except` clause, so flake8-bugbear's B904 has nothing to say about the bare re-raise.
- **A savepoint flushes what is already pending, and that decides where a bad row goes.** The first version of `test_an_unrecognised_integrity_error_is_re_raised` added the malformed row to the session and *then* opened the savepoint around the repository call. It passed. It also never called `add()` — the per-test coverage row showed the whole method uncovered — because entering `begin_nested()` flushed the pending row and PostgreSQL refused it there. The row is now added inside the savepoint, the comment says what was observed, and the users suite was written the same way from the start. This is the sort of green test that is worse than no test, and the only thing that caught it was reading the coverage row rather than the exit status.
- **Two tests were added beyond the plan's list.** `test_updating_a_list_that_is_gone_raises_not_found` covers the one write path that can fail before it reaches the database, and states the reason the adapter does not insert instead: treating a missing row as an insert turns "modify what I fetched" into "create whatever I was handed". `test_an_unrecognised_integrity_error_is_re_raised` in the users suite mirrors its task-list twin; the plan lists it only for task lists, but `users.py` has the same re-raise branch and leaving it untested would have dropped the project's first uncovered line since 03-05.
- **`exists_with_name` returns `count is not None and count > 0`, not `count > 0`.** `AsyncSession.scalar` is typed `int | None`, so the plan's literal comparison does not type-check under mypy strict. Written as a single `return` expression rather than an `if`, it also adds no branch coverage.py would want a second test for — a `SELECT count(*)` cannot answer `None`.
- **The SC-4 gate scans text and says so.** The property is *"this call does not appear in this directory"*, which is a property of the source, not of one execution. The docstring records all three alternatives: the code-review habit (enforces nothing), the runtime assertion (tests one path and calls it a rule), and the AST walk (a legitimate upgrade that must assert the same thing). The text scan also happens to agree with the project's prose-not-literal convention — a docstring under that package that spelled the call out would be a violation of the convention as well as of the gate, which is why this module's own explanations are written in prose.
- **No hook added to `.pre-commit-config.yaml`, no step added to `.github/workflows/ci.yml`.** CLAUDE.md's two-places rule exists for a gate that needs its own invocation. This one rides inside `pytest`, which the hook set, the Docker test stage and CI all already run — the same argument plan 02-06 made for the stdlib check, and `git diff --name-only` lists neither file.
- **No requirement tick taken.** The plan's frontmatter lists `DB-01`, `DB-03` and `ARC-08`; `03-11-PLAN.md` claims all three again. Under the last-claimant convention, 03-11 owns the tick. Sixth consecutive plan in this phase to make the same call.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] A green test that proved nothing: the savepoint refused the row before the repository ran**

- **Found during:** Task 1
- **Issue:** `test_an_unrecognised_integrity_error_is_re_raised` added a `TaskListRow` with no `name` to the session, then ran `repository.add()` inside `session.begin_nested()`. It passed — and the per-test coverage row for `task_lists.py` showed `add()` entirely uncovered. Opening a SAVEPOINT flushes pending work, so the malformed row was refused by the savepoint's own flush and the `IntegrityError` `pytest.raises` caught had never been near the adapter.
- **Fix:** The bad row is now added *inside* the savepoint, immediately before the repository call, with a comment recording what was observed. Per-test coverage of the module went from 39% to 100%.
- **Files modified:** `tests/integration/test_repositories_task_lists.py`
- **Commit:** `81e9afb`

**2. [Rule 2 — Missing coverage of a real branch] `update()` against a row that is gone had no test**

- **Found during:** Task 1
- **Issue:** The plan's test list covers `update` only through rename and collision, both of which find their row. `TaskListNotFoundError` is a reachable branch of the adapter and the decision behind it (not inserting instead) is worth stating.
- **Fix:** Added `test_updating_a_list_that_is_gone_raises_not_found`, asserting the error and its `details`.
- **Files modified:** `tests/integration/test_repositories_task_lists.py`
- **Commit:** `81e9afb`

**3. [Rule 2 — Missing coverage of a real branch] the users adapter's re-raise path**

- **Found during:** Task 2
- **Issue:** The plan lists the unrecognised-`IntegrityError` test only for task lists, but `users.py` has the same bare re-raise, and it is the D-13 property that matters most for a registration endpoint: what is not recognised must become the fixed 500 rather than a guess.
- **Fix:** Added `test_an_unrecognised_integrity_error_is_re_raised` to the users suite, written with the row inside the savepoint from the start.
- **Files modified:** `tests/integration/test_repositories_users.py`
- **Commit:** `5de7e50`

**4. [Rule 3 — Blocking] `exists_with_name` cannot compare a `scalar()` result to zero directly**

- **Found during:** Task 1
- **Issue:** The plan specifies `count > 0`; `AsyncSession.scalar` returns `int | None`, which mypy strict refuses to order against an `int`.
- **Fix:** `return count is not None and count > 0`, as one expression so no uncoverable branch is introduced.
- **Files modified:** `src/taskmanager/infrastructure/db/repositories/task_lists.py`
- **Commit:** `81e9afb`

Everything else executed as written. Every acceptance criterion passed: `grep -c "\.commit()"` prints `0` for both adapters and `grep -rn` under the package prints nothing; `flush()` appears on 4 lines in `task_lists.py` against a floor of 3; `func.lower` appears twice in `users.py`; `grep -rn "TaskListRow" src/taskmanager/application src/taskmanager/domain` is empty; the `inspect.getsource` check for the two forbidden forms exits 0; `__init__.py` is 0 bytes; `.venv/bin/mypy src tests` is clean with no `type: ignore` in the new package; the two integration suites report 12 and 9 tests against floors of 10 and 8; the gate reports 2; and `git diff --name-only` never listed `.pre-commit-config.yaml` or `.github/workflows/ci.yml`.

## Issues Encountered

- **The `trailing-whitespace` pre-commit hook rewrote the evidence file** on the first attempt at the Task 3 commit: pytest's traceback output contains trailing spaces. The hook fixed it, the file was re-staged and committed; the captured text is otherwise byte-identical, and both runs still read as they did on the terminal.
- **No `.env` exists in this repository by design**, so `DATABASE_URL`, `TEST_DATABASE_URL` and `JWT_SECRET` were exported in the shell for every test run. A run with `JWT_SECRET=x` failed at settings validation (`min_length=16`) before any test executed — which is 01-02's fail-fast working, noted here because it looks like a database problem for about ten seconds.
- Nothing else. `filterwarnings = error` raised nothing: neither the Core `delete()` with the default synchronisation strategy nor the savepoint-per-refusal pattern produced a `SAWarning`.

## Known Stubs

None. Both adapters implement every method of their port, and every method has at least one integration test that drives it against PostgreSQL. `tasks.py` is absent because it is plan 03-07's, and the SC-4 gate's `REQUIRED_SCANNED_MODULES` carries a comment saying so rather than listing a file that does not exist.

## Threat Flags

None new. This plan opens no endpoint, adds no auth path, installs nothing (`requirements.txt` untouched, so T-3-SC stays `accept`) and reads no user input. The register's five `mitigate` rows are implemented:

- **T-3-17** (SQL construction) — *mitigated*: every statement in both adapters is built with `select()`, `delete()` or `session.get()` and bound parameters. The `inspect.getsource` check proves the legacy query API and `HTTPException` appear in neither file, and no f-string SQL exists in the package.
- **T-3-13** (a conflict error leaking the address) — *mitigated*: `test_the_conflict_error_does_not_echo_the_address` asserts the address, its domain and the constraint name are absent from both the message and the `details`, and that `details` is exactly `{"field": "email"}`. The task-list conflict is checked the same way for the constraint name and for SQL.
- **T-3-14** (an unmapped `IntegrityError` leaking driver detail) — *mitigated*: both adapters re-raise untranslated, proven by one test each, and Phase 2's catch-all turns that into the fixed 500 body with no message (already proven by `tests/api/test_error_contract.py`).
- **T-3-20** (an unscoped read) — *mitigated*: `list_for_owner` and `exists_with_name` filter in SQL, and `test_list_for_owner_returns_only_that_owners_lists_in_creation_order` plants a third list belonging to somebody else that must not appear.
- **T-3-21** (a write made durable outside the use case's boundary) — *mitigated*: the SC-4 gate, observed red on a planted violation.

## User Setup Required

None new. `docker compose up -d db` (or `make up`) must be running before `make test`, and until `.env` exists on a given machine `DATABASE_URL`, `TEST_DATABASE_URL` and `JWT_SECRET` must be in the shell — `cp .env.example .env` covers all three.

## Next Phase Readiness

- **03-07 repeats a shape that is now written down.** `tasks.py` is the same five moves: borrow the session, map in, flush inside a `try`, translate through a private `NoReturn` helper, map out. It adds `CK_TASKS_STATUS`, `CK_TASKS_PRIORITY`, `CK_TASKS_COMPLETED_AT_MATCHES_STATUS` and the two foreign keys to the translation, and `"tasks.py"` to `REQUIRED_SCANNED_MODULES` in the gate — one line, and the comment there says so.
- **03-08 has both adapters to construct.** `SqlAlchemyUnitOfWork.__aenter__` assigns them to port-annotated attributes; mypy checking a mutable Protocol member invariantly is the reason those annotations must be the port types, which Phase 2's `FakeUnitOfWork` already recorded.
- **The savepoint finding is a hand-off, not a footnote.** Any test in 03-07 or 03-08 that expects a refusal must put the *cause* of the refusal inside `begin_nested()`, or the savepoint's own flush will produce a passing test that never reached the code under test. It cost one debugging cycle here; it is written into both suites' comments so it costs zero there.
- **Coverage is at 100% with the gate at 75%**, unchanged from 03-05 despite 133 new statements.
- **ADR debt for 03-11 is unchanged in kind and grows by nothing.** The SC-4 gate is an implementation of ARC-08, not a new decision; the existing debt (the PostgreSQL 18 volume path, literal constraint names in revisions, the case-sensitivity contrast, the test-only key on `Settings`, the WR-05 resolution, and `make test` requiring PostgreSQL) stands as recorded.
- No blockers.

## Self-Check: PASSED

All seven created files exist on disk, and all three task commits (`81e9afb`, `5de7e50`, `4227a93`) are present in `git log`. No commit deleted a tracked file (`git diff --diff-filter=D --name-only HEAD~3 HEAD` is empty) and `git status --short` was clean after each. `make lint && make typecheck && make arch && make test` was run green before every commit: 239 passed, 100.00% coverage over `src/taskmanager` with the gate at 75%, three contracts KEPT.

---
*Phase: 03-persistence-runnable-stack*
*Completed: 2026-09-18*
