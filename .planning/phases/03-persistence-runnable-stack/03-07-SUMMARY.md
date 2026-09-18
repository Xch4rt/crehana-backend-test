---
phase: 03-persistence-runnable-stack
plan: 07
subsystem: infrastructure
tags: [repositories, sqlalchemy-async, task-filters, count-filter-aggregate, adr-009, d-13, arc-08, sc-4, integration-tests]

# Dependency graph
requires:
  - phase: 02-domain-error-contract
    provides: the TaskRepository Protocol with its keyword-only filters, CompletionStats, and FakeTaskRepository as the behaviour the SQL had to reproduce
  - phase: 03-persistence-runnable-stack
    plan: 01
    provides: TaskRow with its two foreign keys and three CHECK constraints, and the Final constraint names the translation keys on
  - phase: 03-persistence-runnable-stack
    plan: 04
    provides: task_to_row / task_to_entity / apply_task_to_row and violated_constraint()
  - phase: 03-persistence-runnable-stack
    plan: 05
    provides: the integration harness, and the empirical settlement of which constraint names PostgreSQL reports
  - phase: 03-persistence-runnable-stack
    plan: 06
    provides: the flush-translate-never-commit shape, the one-_refused()-per-adapter rule, the savepoint finding, and the SC-4 gate this plan widens
provides:
  - src/taskmanager/infrastructure/db/repositories/tasks.py - SqlAlchemyTaskRepository, the third and last adapter 03-08's unit of work needs
  - completion_statement() - the ADR-009 aggregate as an importable, compilable statement rather than four lines inside a method
  - The two query shapes Phase 4 inherits: filters appended to the statement, and the percentage as one COUNT(*) FILTER row
  - tests/architecture/test_no_commit_in_repositories.py now requiring all three adapters by name
affects: [03-08, 03-09, 03-10, 03-11, 04-crud-endpoints, 05-auth]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A filter is appended to the statement under an `if ... is not None`, never applied to the result: the same code answers both the filtered and unfiltered request, and the value reaches SQL as a bound enum `.value`"
    - "An aggregate whose single-statement-ness is a requirement is written as a module-level function, so a test can compile it and assert on the SQL without a server and without counting round trips"
    - "A list query orders by a timestamp AND the primary key, because a timestamp alone is not a total order and the failure it produces is flakiness rather than wrongness"
    - "A constraint the entity already enforces is deliberately NOT translated, and a test asserts the raw IntegrityError escapes - the deliberate gap is pinned, not just left"

key-files:
  created:
    - src/taskmanager/infrastructure/db/repositories/tasks.py
    - tests/integration/test_repositories_tasks.py
  modified:
    - tests/architecture/test_no_commit_in_repositories.py

key-decisions:
  - "completion_statement() is a module-level function rather than inline in the method: it is the only way `test_the_aggregate_is_a_single_statement` can assert on the compiled SQL with no server and no event listener, which is what makes ADR-009 a gate rather than an intention"
  - "The three CHECK constraints are deliberately not translated, and a test asserts the raw IntegrityError escapes with `ck_tasks_status` as its constraint name - a CHECK refusal means the entity was bypassed, which is a process defect and must become the fixed 500"
  - "The assignee branch of _refused() is guarded by `and task.assignee_id is not None` in the same condition: it keeps the raise-site type a UUID with no cast, and adds no branch coverage cannot reach"
  - "Listing orders by created_at THEN id, beyond the plan's wording, and two seeded tasks share an instant so the tie-break is a tested claim"
  - "`type(fetched) is Task` replaces the sibling suite's `not isinstance(fetched, TaskRow)`: mypy's warn_unreachable proves the isinstance form is dead code, because Task and TaskRow have incompatible method signatures"
  - "No requirement tick taken: 03-11 is the last claimant of DB-01, DB-03, DB-04 and ARC-08. Seventh consecutive plan in this phase to make the same call"

patterns-established:
  - "All three adapters now exist and are named in REQUIRED_SCANNED_MODULES; 03-08 constructs them behind SqlAlchemyUnitOfWork and a fourth adapter would add its name in the commit that creates it"

requirements-completed: []

# Metrics
duration: 10min
completed: 2026-09-18
---

# Phase 3 Plan 07: Task Repository Adapter Summary

**The third adapter is in, and with it the two query shapes Phase 4 no longer has to invent: a listing whose TASK-06 filters are appended to the SQL statement rather than applied to a full table read, and a completion percentage that is one `COUNT(*) FILTER (WHERE ...)` row mapped straight into `CompletionStats` — proven by 17 integration tests against PostgreSQL plus a compiled-SQL assertion that fails if anyone ever splits it into two queries.**

## Performance

- **Duration:** 10 min
- **Started:** 2026-09-18T23:37Z
- **Completed:** 2026-09-18T23:47Z
- **Tasks:** 2
- **Files modified:** 2 created, 1 modified

## Accomplishments

- **`SqlAlchemyTaskRepository`, six methods, the same five moves as its siblings.** `get` returns `task_to_entity(row)` or `None`; `add` inserts and flushes inside a `try`; `update` loads the tracked row, refuses a missing one with `TaskNotFoundError`, applies the entity in place and flushes the same way; `delete` issues a Core `delete()` and says nothing about a row that was not there. No base class, no `.commit()`, no `HTTPException`, entities in and entities out.
- **D-13 told apart, not just implemented.** `fk_tasks_task_list_id_task_lists` becomes `TaskListNotFoundError(task.task_list_id)` and `fk_tasks_assignee_id_users` becomes `UserNotFoundError(task.assignee_id)`, each asserted through its `details` payload. The distinction is the point: a caller who posted to a list that does not exist must not be told their assignee is missing, and only a real foreign key can tell the two apart.
- **The deliberate gap is a test, not a comment.** `test_a_check_constraint_violation_is_not_translated` puts a row with `status="archived"` into the session *inside* the savepoint and lets the flush in `add()` carry it, then asserts both that `IntegrityError` escaped and that `violated_constraint()` names `ck_tasks_status`. A status outside the enumeration cannot come from a `Task`, so the refusal means something bypassed the entity — a defect in this process, not a decision a caller made, and it must reach Phase 2's catch-all as the fixed 500 rather than becoming a business error naming a field no request contained (T-3-14).
- **The filters run in PostgreSQL, and a single test can tell.** `list_for_task_list` appends `.where(TaskRow.status == status.value)` and `.where(TaskRow.priority == priority.value)` only when the argument is not `None`. Four tasks are seeded so that `pending` matches two and `high` matches two *different* ones: the conjunction test asks for `pending` + `low` (one row) and then for `pending` + `high` (none), so an implementation combining the predicates with `OR`, or honouring only the last argument, returns rows where zero are asserted while still passing both single-filter tests.
- **Nothing crosses a list boundary.** `Sweep the floor` belongs to the second list and is the oldest row in the database, so an unscoped statement would return it *first* — the loudest possible failure for the quietest possible bug (T-3-20). Filtered and unfiltered listings both assert its absence, and a list that does not exist answers `[]`.
- **The order is total.** `created_at` then `id`, with two seeded tasks sharing an instant, so a statement ordering by the timestamp alone would have to be lucky to produce the asserted order. That is the difference between a Phase 4 assertion being wrong and being flaky.
- **ADR-009 is a compiled-SQL gate.** `completion_statement(task_list_id)` is a module-level function, so `test_the_aggregate_is_a_single_statement` renders it against the PostgreSQL dialect with no server and asserts `FILTER (WHERE`, exactly one `FROM tasks`, exactly two `count(*)` calls, and that the filter value never appears as an inlined literal. Counting round trips would have needed an event listener and would still only have described one call path.
- **The counters behave at both ends.** Four tasks with one completed gives `total=4, completed=1, percentage=25.0`; an empty list gives `0, 0, 0.0` with no division; a list that does not exist gives the same zeros, because the adapter cannot tell "empty" from "absent" and must not guess (ADR-008). And `test_completion_stats_is_unaffected_by_a_filter` pins roadmap Phase 4 SC-4: a caller reading the two pending tasks is still told the list is 25% done.
- **`bigint` is an `int`, observed rather than assumed.** The plan asked for this to be confirmed instead of cast blindly. `type(stats.total) is int` and `type(stats.completed) is int` are asserted against psycopg's real decoding, so no `int(...)` hides the day that stops being true, and `CompletionStats` stays free of a persistence concern.
- **The SC-4 gate now names all three adapters.** `REQUIRED_SCANNED_MODULES` is `{"task_lists.py", "tasks.py", "users.py"}`, and the comment that used to say "`tasks.py` arrives in 03-07" now says a fourth adapter adds its name in the commit that creates it.
- **All four gates green before both commits.** `make lint && make typecheck && make arch && make test`: 87 files black/isort clean, flake8 clean, mypy strict clean with no `type: ignore` in the new module, three import-linter contracts KEPT, **256 passed** under `filterwarnings = error`. **Coverage over `src/taskmanager` is 100.00%** — 620 statements, 0 missed, 68 branches, 0 partial — gate still at 75, no `pragma`, no `omit`.

## Task Commits

Each task was committed atomically:

1. **Task 1: the task adapter's CRUD half and its D-13 proofs** — `4a5aa88` (feat)
2. **Task 2: filtered listing, the aggregate, and the widened SC-4 gate** — `8dcaf63` (feat)

**Plan metadata:** see the `docs(03-07)` commit that carries this SUMMARY.

## Files Created/Modified

- `src/taskmanager/infrastructure/db/repositories/tasks.py` (218 lines) — the adapter, the `_refused` translator and `completion_statement()`. The module docstring states the one thing specific to this aggregate: which constraints are translated and, at length, why the other three are not
- `tests/integration/test_repositories_tasks.py` (666 lines) — 17 tests, the `refused()` savepoint helper, an `a_task()` builder, a `given_a_list_with_an_owner()` world and a `given_a_mixed_list()` fixture whose asymmetry is what makes the filter assertions meaningful
- `tests/architecture/test_no_commit_in_repositories.py` (99 lines, +1/−1 in the constant and a rewritten comment) — the vacuity guard now requires all three adapters

## Decisions Made

- **`completion_statement()` is a module-level function, not four lines inside `completion_stats`.** ADR-009's requirement is about the *shape of the SQL*, and the only way to assert that without a server is to hand the statement to a test. The alternatives were both worse: an event listener counting queries describes one call path and needs a live connection, and asserting nothing at all would leave "one aggregate, not two queries" as a sentence in a docstring that no gate defends. The function is public rather than underscore-prefixed because a test importing a private name is a smell that outlives the reason for it.
- **The three CHECK constraints are deliberately absent from the translation, and the absence is tested.** `ck_tasks_status`, `ck_tasks_priority` and `ck_tasks_completed_at_matches_status` duplicate invariants `Task.__post_init__` already enforces. A refusal from one of them therefore means a row reached the database without passing through the entity — a bug in this process, not a request a client can fix. Translating it would produce a 422 pointing at a field the request never contained; leaving it raw produces Phase 2's fixed 500, which is the honest answer. The test asserts the constraint *name* as well as the exception type, for `test_constraints.py`'s reason: `IntegrityError` alone would also pass for a violation the test never intended to cause.
- **The assignee branch carries its `None` guard in the same condition.** `if refused_by == FK_TASKS_ASSIGNEE_ID_USERS and task.assignee_id is not None:` keeps `UserNotFoundError(task.assignee_id)` typed without a cast or an assertion, and coverage.py measures arcs out of the `if` rather than sub-conditions, so both outcomes are already exercised — no uncoverable branch was introduced. An unassigned task writes `NULL`, which no foreign key can refuse, so the guarded pairing cannot happen in practice and the comment says so.
- **Listing orders by `created_at` *and* `id`.** The plan asked for the tie-break and the seed data makes it testable: `Buy milk` and `Water the plants` share an instant, so PostgreSQL is free to return them either way round. A missing tie-break would not produce a failing test — it would produce one that fails occasionally, months later, in Phase 4.
- **`type(fetched) is Task` instead of `not isinstance(fetched, TaskRow)`.** The sibling suite's form does not compile here: mypy with `warn_unreachable = true` proves `Task` and `TaskRow` can have no common subclass (their method signatures are incompatible), so the comparison is dead code and `make typecheck` fails. The exact-type check makes the same claim and mypy cannot resolve it away. The comment in the test records why the two suites differ.
- **The world is seeded through the mappers, not through the sibling adapters.** The plan's wording says "through the sibling adapters"; `test_repositories_task_lists.py` establishes the opposite convention and gives the reason — this module tests one adapter, and a fault in `task_lists.py` or `users.py` should not be able to turn this file red while pointing at the wrong one. Consistency with the established pattern won.
- **No requirement tick taken.** The plan's frontmatter lists `DB-01`, `DB-03`, `DB-04` and `ARC-08`; `03-11-PLAN.md` claims all four again. Under the last-claimant convention, 03-11 owns the tick. Seventh consecutive plan in this phase to make the same call.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 — Missing coverage of a real branch] `update()`'s `IntegrityError` path had no test**

- **Found during:** Task 1
- **Issue:** The plan's test list drives `update()` only through a successful write and a missing row, so lines 96–97 — the `except IntegrityError` that calls `_refused` — were the only uncovered lines in the module (96%). Both foreign keys are writable through `apply_task_to_row`, so this is a reachable branch, and a rewrite that dropped it would let a raw `IntegrityError` travel up from every PATCH in Phase 4 while every test exercising only `add()` stayed green.
- **Fix:** Added `test_moving_a_task_into_a_missing_list_is_refused_the_same_way`, which loads a stored task, points it at a list that does not exist and updates it inside the savepoint. Module coverage went to 100%.
- **Files modified:** `tests/integration/test_repositories_tasks.py`
- **Commit:** `4a5aa88`

**2. [Rule 3 — Blocking] the seed helper's single flush emitted `task_lists` before `users`**

- **Found during:** Task 1
- **Issue:** `given_a_list_with_an_owner` added two users and two lists and flushed once. SQLAlchemy orders a flush by the dependencies it knows about, and it knows about `relationship()` declarations — there is none between `UserRow` and `TaskListRow`, only a plain foreign key — so it emitted the list inserts first and PostgreSQL refused them with `fk_task_lists_owner_id_users`. Every test in the module failed at setup.
- **Fix:** Two flushes, in the order the references point: users, flush, lists, flush. The docstring records the cause, because the next suite that seeds across two tables without a relationship will meet it again.
- **Files modified:** `tests/integration/test_repositories_tasks.py`
- **Commit:** `4a5aa88`

**3. [Rule 3 — Blocking] `assert not isinstance(fetched, TaskRow)` is dead code under `warn_unreachable`**

- **Found during:** Task 1
- **Issue:** Copied from the task-list suite, where it type-checks. Here mypy reports `Subclass of "Task" and "TaskRow" cannot exist: would have incompatible method signatures [unreachable]`, and `make typecheck` fails — a gate CLAUDE.md requires green before the commit.
- **Fix:** `assert type(fetched) is Task`, with a comment explaining why this suite differs from its sibling.
- **Files modified:** `tests/integration/test_repositories_tasks.py`
- **Commit:** `4a5aa88`

### Deviations from the plan's letter

**4. The CHECK-violation test writes its bad row through the ORM inside the savepoint, not "through raw SQL on the same session"**

- **Found during:** Task 1
- **Reason:** Raw SQL executed on the session would prove that PostgreSQL refuses the row — which `test_constraints.py` already proves — without the adapter ever running, so it could not show that *the adapter* does not translate it. The row is therefore added to the session inside `begin_nested()` and `repository.add()` is called immediately after, so the flush inside `add()` is what carries the violation. This is 03-06's savepoint finding applied rather than rediscovered: anything a refusal depends on must be created inside the savepoint, or the savepoint's own flush produces a green test that never reached the code under test.
- **Files modified:** `tests/integration/test_repositories_tasks.py`
- **Commit:** `4a5aa88`

**5. The compiled-SQL test resolves its dialect with `create_engine`, not `postgresql.dialect()`**

- **Found during:** Task 2
- **Reason:** The plan spells `.compile(dialect=postgresql.dialect())`; that call is unannotated and mypy strict rejects it as `no-untyped-call`, which plan 03-01 already settled. `create_engine("postgresql+psycopg://").dialect` is the typed equivalent and connects lazily, so the test needs no server. The comment points at `tests/unit/infrastructure/test_models.py`, where the same constant lives for the same reason.
- **Files modified:** `tests/integration/test_repositories_tasks.py`
- **Commit:** `8dcaf63`

Everything else executed as written. Every acceptance criterion passed: the tasks suite reports **17 tests** against floors of 7 and 16; `grep -c "\.commit()"` prints `0` for the new module and `grep -rn` under the package prints nothing; `flush()` appears on 4 lines against a floor of 3; `grep -c "tasks.py"` in the gate prints `1`; the `FILTER (WHERE` one-liner exits 0; `.venv/bin/mypy src tests` is clean with no `type: ignore`; the `TaskRepository` import-and-instantiate one-liner exits 0; `make test` reports `Required test coverage of 75% reached. Total coverage: 100.00%`; and the per-file coverage row for `tasks.py` shows 60 statements, 0 missed, 10 branches, 0 partial.

## Issues Encountered

- **The FK ordering failure above cost one run**, and it is worth stating plainly for 03-08: SQLAlchemy's flush ordering follows `relationship()` declarations, not raw `ForeignKey` columns. The unit of work will hit the same thing the first time a use case creates a user and a list in one block without flushing between them.
- **No `.env` exists in this repository by design**, so `DATABASE_URL`, `TEST_DATABASE_URL` and `JWT_SECRET` were exported in the shell for every test run, exactly as in 03-06.
- Nothing else. `filterwarnings = error` raised nothing new: neither the Core `delete()` with the default synchronisation strategy nor the `FunctionFilter` construct produced a `SAWarning`.

## Known Stubs

None. Every method of the `TaskRepository` port is implemented and every one of them is driven against PostgreSQL by at least one test. All three adapters now exist, so `infrastructure/db/repositories/` is complete for this phase and `REQUIRED_SCANNED_MODULES` names the whole package rather than a subset with a promissory note.

## Threat Flags

None new. This plan opens no endpoint, adds no auth path, installs nothing (`requirements.txt` untouched, so T-3-SC stays `accept`) and reads no user input directly. The register's four `mitigate` rows are implemented:

- **T-3-17** (a filter value reaching SQL as text) — *mitigated*: both filters are `.where(Column == enum_member.value)` with bound parameters, and `test_the_aggregate_is_a_single_statement` asserts that even the aggregate's `completed` literal never appears inlined in the compiled SQL. No f-string SQL exists anywhere in the package.
- **T-3-20** (a cross-list read) — *mitigated*: every statement is scoped by `task_list_id` in SQL, and the foreign task seeded into the second list is the oldest row in the database, so an unscoped listing would surface it first.
- **T-3-14** (a driver message reaching a client) — *mitigated*: the CHECK constraints are untranslated by design and the unrecognised path re-raises, so both reach Phase 2's catch-all and become the fixed 500 with no message. The two translated errors carry only an id in `details`, never a constraint name or SQL.
- **T-3-21** (a write made durable outside the use case's boundary) — *mitigated*: the SC-4 gate now requires `tasks.py` to be among the scanned modules, so the newest adapter cannot silently drop out of the scan.

**T-3-22** (unbounded listing) remains `accept` as the register records: pagination is out of scope for this phase, the per-list scope plus `ix_tasks_task_list_id` bounds the work per request, and the ADR in plan 03-11 records the omission honestly.

## User Setup Required

None new. `docker compose up -d db` (or `make up`) must be running before `make test`, and until `.env` exists on a given machine `DATABASE_URL`, `TEST_DATABASE_URL` and `JWT_SECRET` must be in the shell — `cp .env.example .env` covers all three.

## Next Phase Readiness

- **03-08 has all three adapters to construct.** `SqlAlchemyUnitOfWork.__aenter__` assigns them to port-annotated attributes; mypy checks a mutable Protocol member invariantly, which is why those annotations must be the port types — Phase 2's `FakeUnitOfWork` already recorded it, and nothing in this plan changes it.
- **Phase 4 inherits two query shapes it does not have to invent.** The listing endpoint's TASK-06 filters are already keyword-only, already in SQL and already list-scoped; the completion percentage is already one statement whose result is a `CompletionStats`, and SC-4's "the percentage covers the whole list" is already a test rather than a note.
- **The flush-ordering finding is a hand-off.** Two tables related only by a `ForeignKey` are not ordered by the unit of work; if a 03-08 or Phase 4 test creates a user and a list in one flush, it will see `fk_task_lists_owner_id_users`.
- **Coverage is at 100% with the gate at 75%**, unchanged since 03-05 despite 60 further statements.
- **ADR debt for 03-11 grows by one small entry in kind**: the deliberate non-translation of the three CHECK constraints is a D-13 refinement worth one sentence, alongside the existing debt (the PostgreSQL 18 volume path, literal constraint names in revisions, the case-sensitivity contrast, the test-only key on `Settings`, the WR-05 resolution, and `make test` requiring PostgreSQL).
- No blockers.

## Self-Check: PASSED

Both created files exist on disk and the modified gate carries `tasks.py`; both task commits (`4a5aa88`, `8dcaf63`) are present in `git log`. No commit deleted a tracked file (`git diff --diff-filter=D --name-only HEAD~2 HEAD` is empty) and `git status --short` was clean after each. `make lint && make typecheck && make arch && make test` was run green before every commit: 256 passed, 100.00% coverage over `src/taskmanager` with the gate at 75%, three contracts KEPT.

---
*Phase: 03-persistence-runnable-stack*
*Completed: 2026-09-18*
