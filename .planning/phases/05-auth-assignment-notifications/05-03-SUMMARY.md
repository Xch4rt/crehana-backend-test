---
phase: 05-auth-assignment-notifications
plan: 03
subsystem: database
tags: [alembic, migration, postgres, sqlalchemy, schema, index, d-25, tdd]

# Dependency graph
requires:
  - phase: 02-domain-error-contract
    provides: "domain/validation.py's require_text, which already trims, refuses blank and refuses NUL (WR-03), so full_name needed no new helper and no second copy of its limit"
  - phase: 03-persistence-runnable-stack
    provides: "0001_baseline.py and its conventions (literal constraint names per ADR-025, a real downgrade, op.f for generated names); constraints.py as the one home of a constraint name; the migrated_database fixture; alembic check"
  - phase: 04-task-lists-tasks
    provides: "docker/entrypoint.sh step 2b, the demo seed whose hand-written column list this plan had to correct"
provides:
  - "User.full_name with FULL_NAME_MAX_LENGTH = 100, trimmed through require_text and deliberately not case-folded"
  - "UserRow.full_name as VARCHAR(100), and full_name in all three user mappers"
  - "migrations/versions/0002_full_name_and_assignee_index.py: the column over populated tables, and ix_tasks_assignee_id"
  - "IX_TASKS_ASSIGNEE_ID in constraints.py as the thirteenth name, asserted against the compiled DDL"
  - "The index behind GET /api/v1/tasks/assigned-to-me and behind every ON DELETE SET NULL on tasks.assignee_id (D-25)"
  - "A migration-chain test replacing the retired one-revision count, and a single-step downgrade/upgrade round trip"
affects: [05-05, 05-07, 05-08, 05-09, 05-10, 05-13, 05-16]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A NOT NULL column arrives in a populated table through a transient server_default dropped in the same upgrade(), with alembic check as the gate proving it did not survive"
    - "A revision chain is asserted through Alembic's own ScriptDirectory (down_revision links and get_current_head) rather than by counting files in a directory"
    - "A single-step downgrade of the newest revision, asserted against the reflected schema, as the proof `downgrade base` cannot give"
    - "A cold-start rehearsal against the live compose database as the only gate that can see a defect in a heredoc the test suite never imports (ADR-037's own argument, paid out)"

key-files:
  created:
    - migrations/versions/0002_full_name_and_assignee_index.py
    - .planning/phases/05-auth-assignment-notifications/evidence/05-03-tdd-red.txt
    - .planning/phases/05-auth-assignment-notifications/evidence/05-03-live-upgrade.txt
  modified:
    - src/taskmanager/domain/entities/user.py
    - src/taskmanager/infrastructure/db/models.py
    - src/taskmanager/infrastructure/db/mappers.py
    - src/taskmanager/infrastructure/db/constraints.py
    - docker/entrypoint.sh
    - tests/unit/domain/test_user.py
    - tests/unit/infrastructure/test_models.py
    - tests/unit/infrastructure/test_mappers.py
    - tests/unit/application/test_fakes.py
    - tests/integration/test_migrations.py
    - tests/integration/test_repositories_users.py
    - tests/integration/test_repositories_task_lists.py
    - tests/integration/test_repositories_tasks.py
    - tests/integration/test_constraints.py
    - tests/integration/test_schema.py
    - tests/integration/test_unit_of_work.py
    - tests/integration/test_dependencies.py
    - tests/integration/test_concurrent_writes.py
    - tests/integration/api/test_task_lists.py

key-decisions:
  - "full_name is trimmed but NOT lower-cased, the deliberate opposite of email: an address is an identity key that uq_users_email_lower defends, while a display name keys nothing, is never looked up by, and carries capitals that belong to the person who typed them"
  - "No CHECK constraint on the length. This schema enforces a text limit with VARCHAR(n) bound to the entity ClassVar by test_string_lengths_match_the_entity_caps; the three CHECKs that exist guard the two enum columns and the completed_at/status invariant, none of which a width can express (05-RESEARCH Pattern 9)"
  - "test_the_migration_directory_holds_exactly_one_revision is retired out loud, named in the docstring of the chain test that replaces it: a count says nothing about whether the revisions can be walked, and a second head or a wrong down_revision would satisfy it while breaking upgrade head"
  - "The chain test reads through ScriptDirectory against a deliberately unusable DSN, so an edit that made it touch a database would fail loudly rather than quietly connect to whatever the environment points at"
  - "docker/entrypoint.sh step 2b was broken by this change and fixed here: the demo seed's hand-written column list omitted full_name, ON CONFLICT DO NOTHING could not absorb the NotNullViolation because PostgreSQL checks NOT NULL before consulting the arbiter index, and the container aborted under set -eu"
  - "The populated-table claim is proven against the live compose database, not against the suite: migrated_database runs downgrade base first, so taskmanager_test is always empty and the transient server_default is never exercised by a test"
  - "Requirement ticks AUTH-01/ASGN-02/ASGN-03 deliberately NOT taken - 05-16 is the last claimant, and this plan ships a column and an index with no use case and no route above them"

patterns-established:
  - "Splitting one revision file across two commits leaves the developer's test database at a version whose new downgrade() cannot run; the repair is a one-statement fix-up on taskmanager_test, and the shipped chain is unaffected because a real deployment only ever walks 0001 -> 0002 forward"
  - "A live-database rehearsal is scheduled whenever a migration's claim is about rows that already exist, because the suite's empty-database fixture cannot see that case"

requirements-completed: []

# Metrics
duration: 12min
completed: 2026-09-19
---

# Phase 5 Plan 03: users.full_name and revision 0002 Summary

**`full_name` reaches the entity, the row, the three mappers and a second Alembic revision in one
vertical, together with `ix_tasks_assignee_id` — and the live upgrade against the populated compose
database caught a demo-seed `INSERT` that would have broken `docker compose up`.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-09-19T15:08:34Z
- **Completed:** 2026-09-19T15:22Z
- **Tasks:** 3 of 3
- **Files modified:** 22 (3 created, 19 modified)

## Accomplishments

### Task 1 — the vertical (`0ed6501`)

`User` gained `FULL_NAME_MAX_LENGTH: ClassVar[int] = 100` and a `full_name` field validated once,
in `__post_init__`, through the same `require_text` every other string in the domain goes through.
`create()` takes it as a keyword-only parameter in the position the dataclass declares it.
`UserRow.full_name` is `VARCHAR(100)`, `user_to_row` / `user_to_entity` / `apply_user_to_row` all
carry it explicitly, and `0002_full_name_and_assignee_index.py` adds the column `NOT NULL` through a
transient `server_default` dropped in the same `upgrade()`.

The construction blast radius the plan enumerated was fourteen files. It was in fact eighteen — see
Deviations.

`test_the_migration_directory_holds_exactly_one_revision` was replaced by
`test_the_revisions_form_one_unbroken_chain_ending_at_the_head`, which walks Alembic's own
`ScriptDirectory`: `{0001, 0002}` present, `0002.down_revision == "0001"`, `get_current_head() ==
"0002"`. The retirement is named in the replacement's docstring rather than performed quietly.

### Task 2 — the index (`6b0ea5f`)

`IX_TASKS_ASSIGNEE_ID` joined `constraints.py` as the thirteenth name, `index=True` went on
`TaskRow.assignee_id`, and `0002` creates it in `upgrade()` and drops it as the *first* statement of
`downgrade()`, following `0001`'s reverse-order rule. `models.py` refuses two other indexes with
written-out reasons, so the argument for this one is written out beside them in the same voice:
PostgreSQL does not index a foreign key automatically, no unique constraint covers `assignee_id`
(unlike `task_lists.owner_id`), it is the entire `WHERE` clause of `GET /api/v1/tasks/assigned-to-me`
(D-02), and it is the scan performed for every `ON DELETE SET NULL` when a user is removed.

`test_the_naming_convention_produces_every_d12_constraint_name` now asserts thirteen names against
the compiled DDL, still as an exact count rather than a subset check.

### Task 3 — the live proofs (`f702c84`)

Three tests in `test_repositories_users.py`:

- a `full_name` round trip read back through **both** `get` and `get_by_email`, never off the entity
  `add()` was handed — the entity trims in `__post_init__`, so asserting the object that went in
  would pass against a column nobody wrote and a mapper that dropped the field;
- a 101-character name refused by the entity with no statement issued, which is the whole T-5-13
  claim: the `VARCHAR(100)` is the backstop, not the gate;
- `list_all` over three users written out of order with two sharing an instant to the microsecond —
  the adapter-side counterpart of 05-02's fake fix, and the only shape that pins the composite
  `(created_at, id)` rather than one axis of it.

And one in `test_migrations.py`: a single-step `downgrade` to `0001` and back to `head`, asserting
`users.full_name` and `ix_tasks_assignee_id` absent then present in the **reflected** schema. The
whole thing runs inside a rolled-back transaction, so the session's schema survives.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Four more construction sites than the plan enumerated**

- **Found during:** Task 1
- **Issue:** The plan's `<interfaces>` block listed ten files holding `User(` or `User.create(`
  calls. `mypy src tests` found three more in `tests/unit/application/test_fakes.py` (the three-user
  ordering test 05-02 added, written after the plan's grep was taken), and `make test` then found a
  second class of site the plan did not consider at all: code that builds a `users` row **without**
  the entity. Those are `UserRow(...)` literals in `test_repositories_users.py` (three) and raw
  `INSERT INTO users` statements in `test_constraints.py` and `test_schema.py` — all deliberate, all
  bypassing `User` the way a seed script or a migration would, and therefore all obliged to name the
  new `NOT NULL` column themselves. Fifteen failures.
- **Fix:** Every site updated in the same commit as the field. The `UserRow` literal in
  `test_an_unrecognised_integrity_error_is_re_raised` was given a `full_name` on purpose: that test
  wants a row with *no address*, and leaving `full_name` out too would have changed which violation
  it was actually observing.
- **Files modified:** `tests/unit/application/test_fakes.py`, `tests/integration/test_constraints.py`,
  `tests/integration/test_schema.py`, `tests/integration/test_repositories_users.py`
- **Commit:** `0ed6501`

**2. [Rule 1 - Bug] `docker/entrypoint.sh` step 2b broke `docker compose up`**

- **Found during:** Task 3, in the live upgrade against the compose database
- **Issue:** The Phase 4 demo seed writes its row with a hand-written column list, and `full_name`
  was not in it. The `INSERT` became a `NotNullViolation`, and `ON CONFLICT DO NOTHING` did not
  absorb it and could not have: PostgreSQL checks `NOT NULL` while building the candidate row,
  before the arbiter index is consulted, so the clause never runs. Under `set -eu` the container
  aborted before serving. This is the project's core value — "provable in under five minutes by an
  evaluator: `docker compose up`" — broken by one column.
- **Fix:** `full_name` added to the column list and the parameter dict, with the reason and the
  observed error recorded in the comment block above the heredoc. Rebuilt, restarted, `healthy`,
  `/health` returns `ok`, and a second restart is still healthy (the seed stays idempotent).
- **Why no test caught it:** the suite migrates `taskmanager_test` and never runs the entrypoint,
  and the entrypoint is a heredoc rather than a module under `src/taskmanager/` (ADR-037), so
  nothing imports that `INSERT`. ADR-037 argues that the cold-start rehearsal is the stronger proof
  in exchange; this is that argument paying out.
- **Files modified:** `docker/entrypoint.sh`
- **Commit:** `f702c84`

### Criteria met in substance rather than literally

**`grep -cE 'op\.create_index\(op\.f\("ix_tasks_assignee_id"\)' prints 1`** — it prints `0`. That
call is 89 characters on one line and `black`, a mandated gate, wraps it, exactly as it already
wraps the identical `ix_tasks_task_list_id` call in `0001` (L138-140). `grep -c 'op\.f("ix_tasks_assignee_id")'`
prints `2` instead, one per operation, and `grep -cE 'op\.drop_index\(op\.f\("ix_tasks_assignee_id"\)'`
prints `1` literally. The plan's own text calls the load-bearing proofs the thirteen-name DDL
assertion and Task 3's round trip; both are green. This is the 01-03 prose-not-literal precedent
applied to a counter the plan itself wrote.

### Deliberate additions

**The live upgrade against the populated compose database.** The plan's `must_haves` claim that
`0002` "adds `users.full_name` NOT NULL over existing rows". No test in this repository can prove
that: `migrated_database` runs `downgrade base` before `upgrade head`, so `taskmanager_test` is
always empty when `0002` runs and the transient `server_default` is never exercised. The compose
`taskmanager` database was at `0001` with the Phase 4 demo-seed row in it — the exact case — so the
`api` image was rebuilt and the container restarted, which runs `alembic upgrade head` through its
own entrypoint. The full capture, including the failure it exposed, is in
`evidence/05-03-live-upgrade.txt`. Afterwards: `alembic version_num = 0002`, the existing row
survived carrying the default's filler, `\d users` shows `full_name | character varying(100) | not
null` with an **empty Default column**, `\d tasks` shows `ix_tasks_assignee_id`, and
`docker compose exec api alembic check` reports `No new upgrade operations detected`.

## What the live database was actually asked to do

- `taskmanager_test` (the throwaway test database): migrated as usual by `migrated_database`, which
  drops and rebuilds it every session. One hand-issued repair, described below.
- `taskmanager` (the compose application database, holding the evaluator-facing demo row): upgraded
  `0001 -> 0002` **only**, through the container's own entrypoint. Nothing dropped, no volume
  removed, no `downgrade` run against it. The demo row is intact.

## Known Stubs

None.

## Threat Flags

None. The plan's register anticipated every surface this change touches; no new endpoint, auth path,
file access or trust-boundary schema element was introduced. `requirements*.txt` is unchanged.

## Issues Encountered

**A revision file amended across two commits leaves the developer's test database unreversible.**
The plan splits `0002` over Task 1 (the column) and Task 2 (the index). After Task 1, `taskmanager_test`
was stamped `0002` by a version of `upgrade()` that never created the index; Task 2's `downgrade()`
then tried to drop it, and every integration test that depends on `migrated_database` errored with
`index "ix_tasks_assignee_id" does not exist`. Repaired with a single
`CREATE INDEX IF NOT EXISTS` against `taskmanager_test` — never against `taskmanager` — after which
the suite was green. This is a development artifact of the commit split, not a defect in the shipped
chain: a real deployment only ever walks `0001 -> 0002` forward from a database that never saw the
intermediate state, which is precisely what the live upgrade then demonstrated.

## Verification

| Gate | Result |
|------|--------|
| `make lint` | pass — black, isort, flake8 all clean over 141 files |
| `make typecheck` | pass — `mypy --strict`, no issues in 141 source files |
| `make arch` | pass — `Contracts: 4 kept, 0 broken` |
| `make test` | pass — **695 passed**, coverage **100.00%** over 1221 statements, `Required test coverage of 75% reached` |
| `grep -rn "pragma: no cover" src/taskmanager/` | 0 matches |
| `alembic check` (live `taskmanager`) | `No new upgrade operations detected` |
| `docker compose up` | `api Up (healthy)`, `/health` → `{"status":"ok","checks":{"database":"ok"}}` |

## Handoff Notes

- **05-05 onward:** every `User(...)` or `User.create(...)` now requires `full_name`. It is
  keyword-only on `create`.
- **05-07 (RegisterUser) and 05-09 (schemas):** the entity trims and validates `full_name` itself,
  so the Pydantic schema owns only the boundary shape. The cap is `User.FULL_NAME_MAX_LENGTH`; do
  not repeat `100` as a literal (D-04).
- **05-10 (the demo user's deletion):** `docker/entrypoint.sh` step 2b now names `full_name`. When
  the seam and the seed block go, that goes with them.
- **05-13 (`GET /users`):** `list_for_assignee` and `list_all` both have their index now;
  `ix_tasks_assignee_id` exists on the model, in the revision and in the live database.
- **Requirement ticks AUTH-01, ASGN-02, ASGN-03 deliberately not taken.** 05-16 is the last
  claimant, the sixth consecutive plan in this phase to make that call. This plan ships a column and
  an index with no use case and no route above them.
- **A note for any future migration:** if its claim is about rows that already exist, the suite
  cannot prove it. Schedule a run against the populated compose database, as this plan did.

## Self-Check: PASSED

- `migrations/versions/0002_full_name_and_assignee_index.py` — FOUND
- `.planning/phases/05-auth-assignment-notifications/evidence/05-03-tdd-red.txt` — FOUND
- `.planning/phases/05-auth-assignment-notifications/evidence/05-03-live-upgrade.txt` — FOUND
- commit `0ed6501` — FOUND
- commit `6b0ea5f` — FOUND
- commit `f702c84` — FOUND
