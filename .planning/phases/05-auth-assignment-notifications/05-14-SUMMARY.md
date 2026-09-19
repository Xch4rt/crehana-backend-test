---
phase: 05-auth-assignment-notifications
plan: 14
subsystem: integration-assignment-http
tags: [integration, http, assignment, notifications, logging, concurrency, statement-counts, d-01, d-02, d-03, d-05, d-06, d-07, d-08, d-11, d-15, d-16, d-18, d-20, t-5-11, t-5-12, t-5-13, t-5-17, notf-03]

# Dependency graph
requires:
  - phase: 05-auth-assignment-notifications
    provides: "AssignTask, UnassignTask and ListAssignedTasks, with the post-commit notification and the D-07 no-ops (05-08)"
  - phase: 05-auth-assignment-notifications
    provides: "routers/assignments.py: the two assignee verbs and the flat discovery route (05-12)"
  - phase: 05-auth-assignment-notifications
    provides: "authenticated_client, bearer_header and the readable assignee/stranger identifiers (05-13)"
  - phase: 05-auth-assignment-notifications
    provides: "LoggingEmailNotifier, LOGGER_NAME and the JsonFormatter that renders a record as one line (05-06)"
  - phase: 05-auth-assignment-notifications
    provides: "owned_task and the assignee short-circuit in visible_task (05-04)"
  - phase: 04-task-lists-tasks
    provides: "The integration harness and the two-connection concurrency module with its timing constants"
provides:
  - "tests/integration/api/test_assignment.py: 25 HTTP tests covering ASGN-01, ASGN-02, NOTF-01, NOTF-02 and NOTF-03"
  - "The measured statement counts on the real authenticated path: 2 for GET /task-lists, 4 for the task collection, both as the owner"
  - "An owner-versus-assignee interleaving in tests/integration/test_concurrent_writes.py"
  - "routers/assignments.py back at 100% statement coverage - the six statements this plan owed"
  - "Four recorded falsifications of the load-bearing assertions, in evidence/05-14-falsification.txt"
affects: [05-15, 05-16]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A falsification file in place of a TDD RED capture, for a plan whose subject already exists: each load-bearing assertion is observed failing against a deliberately broken implementation, then the source is reverted"
    - "Log assertions on a record's `vars()` rather than on attribute access - `record.event` is a mypy-strict error and `getattr(record, 'event')` is flake8-bugbear B009, and `__dict__` is what the formatter itself reads"
    - "caplog.at_level(logging.INFO, logger=LOGGER_NAME) with the name imported from the adapter, and the reason it is load-bearing written in the test"
    - "A dependency-override context manager for the notifier, in the acting_as spirit: the restoring half is what stops a broken double leaking into every later test"
    - "A statement-count constant whose comment names each entry, so an increment reads as a decision rather than a regression"
key-files:
  created:
    - tests/integration/api/test_assignment.py
    - .planning/phases/05-auth-assignment-notifications/evidence/05-14-falsification.txt
  modified:
    - tests/integration/api/test_statements.py
    - tests/integration/test_concurrent_writes.py

key-decisions:
  - "No TDD RED capture, and a falsification file instead. The routes and use cases this plan tests shipped in 05-08 and 05-12, so every test here was green the moment it was written and a RED step would have been theatre. What a green test over working code does not say is whether it could ever go red, so the four assertions the threat register leans on were each observed failing against a broken implementation: the guard reordered after the user lookup (T-5-12), the D-07 early return deleted, the commit removed (NOTF-03), and the owner's write path not holding the row (T-5-17). Each source edit was reverted with git checkout and the suite re-run green before the commit"
  - "The notification's structured fields are read with vars(record), not with attribute access. Both alternatives were observed failing a gate: `record.event` is a mypy-strict attr-defined error because the fields are not declared members of LogRecord, and `getattr(record, 'event')` is four flake8-bugbear B009 violations. The record's __dict__ is what JsonFormatter iterates, so reading it is the same question the application asks, asked the same way"
  - "The assignee and stranger identifiers, emails and user builder are imported from test_users.py rather than re-declared. They are the same two people plan 05-13 introduced, and the alternative was a second copy of a shared fact in the module most likely to drift from it"
  - "The discovery fixture puts one of the assignee's three tasks in a list the STRANGER owns, so `assigned-to-me` is a view across lists rather than a filter inside one - and the list it spans into is one the assignee cannot see at all (D-01). Two further tasks (one unassigned, one the owner's own) make the three remaining wrong answers - every assigned task, every task in a reachable list, insertion order - fail as well"
  - "The concurrency fixture assigns the task in the fixture rather than inside the new test. Assigning is itself a durable write, and doing it mid-test would put a committed change between the two writers whose interleaving is the subject"
  - "_remove_what_was_committed now names both users explicitly instead of relying on the cascade. tasks.assignee_id is ON DELETE SET NULL, which is right for the column and exactly wrong for a cleanup: deleting the owner clears the assignee out of the task and leaves the assignee's users row standing, which test_dependencies.py would report as a leak"
  - "The new concurrency case asserts `waited` LAST, after the lost-write assertions, which is the ordering `_until_it_waits_or_finishes` asks for in its own docstring. Observed: with the lock removed the test now fails on `'Contended' == 'Renamed by the owner'` - the write that was lost - rather than on 'nobody waited'"
  - "test_statements.py's module docstring states that the property under test has not changed. The numbers moved from 1 and 3 to 2 and 4 because D-11 added a read; the `for_one == for_many` assertions measure invariance, and the absolute number is a measurement to be recorded rather than a target to be defended"
  - "The counts are labelled as the OWNER's, and the per-role difference was measured rather than asserted from the source: the owner's GET of one task issues 3 SELECTs and the assignee's 2; the owner's PATCH .../status issues 4 SELECTs and one UPDATE, the assignee's 3 and one UPDATE. The saving is the assignee short-circuit in visible_task, and the reason for it is the disclosure rather than the statement count"
  - "No requirement tick taken. ASGN-01, ASGN-02, NOTF-01, NOTF-02 and NOTF-03 are in this plan's frontmatter and 05-16 is the last claimant under the project's standing convention; the fifteenth consecutive Phase 5 plan to make the same call"

patterns-established:
  - "For a test-only plan over already-shipped behaviour: falsify each load-bearing assertion against a deliberately broken implementation, capture both the break and the revert, and say in the evidence file why a RED step was not available"
  - "Any statement-count assertion names the role it measures, because the assignee's paths are one SELECT cheaper than the owner's"

requirements-completed: []

# Metrics
duration: 34min
completed: 2026-09-19
---

# Phase 5 Plan 14: Assignment and the Notification over Real HTTP Summary

Twenty-five HTTP tests put the assignment door, the assignee's two capabilities and four
refusals, the discovery route and the simulated invitation on real PostgreSQL; the statement
counts were re-measured through the real actor dependency and are 2 and 4 rather than 1 and 3;
and the concurrency suite now proves the owner and the assignee cannot overwrite each other.

## Performance

- **Duration:** ~34 min
- **Tasks:** 3 of 3
- **Files modified:** 4 (2 created, 2 modified)

## Accomplishments

- **The door, end to end.** `PUT` assigns and `DELETE` unassigns on one URL, both answering 200
  with the full eleven-member `TaskResponse`; a repeat of either is a no-op whose `updated_at`
  does not move; self-assignment is allowed and shows up in the owner's own `assigned-to-me`;
  an `assignee_id` naming nobody is 404 `user_not_found` carrying only the identifier the
  caller supplied.
- **The user-existence oracle is closed, and the proof is a body comparison.** A stranger who
  `PUT`s an invented `assignee_id` and a stranger who `PUT`s a real one get byte-identical
  documents. Reordering the ownership guard and the user lookup in `AssignTask` was observed
  turning that test red with `assert 'user_not_found' == 'task_not_found'` (T-5-12).
- **The assignee's whole row of D-03.** `GET` 200 (the same document the owner sees),
  `PATCH .../status` 200, and 403 on the generic `PATCH`, the `DELETE`, the `PUT .../assignee`
  and the `DELETE .../assignee` - each 403 followed by a re-read as the owner, so a refusal
  that had already written fails. Their parent list still answers 404 on both list routes
  (D-01), which is why the discovery route exists.
- **`GET /tasks/assigned-to-me` spans lists and carries the address.** Three tasks over two
  lists - one of them owned by a third party - in `(created_at, id)` order, with the fixture
  arranged so that insertion order, identifier order and `created_at` alone are each the wrong
  answer. The test does not assert that `task_list_id` is present; it **builds the nested URL
  from it and follows it**, for a task in a list the caller cannot see.
- **The invitation is observable from an HTTP request.** One `taskmanager.notifications` INFO
  record per real assignment, asserted on its structured fields (`event`, `to`, `task_id`,
  `body`) and on `json.loads(JsonFormatter().format(record))`, never on a substring of the
  message. No record for a D-07 repeat and none for an unassignment.
- **A title carrying an embedded newline still produces exactly one line** (T-5-13): the forged
  JSON object survives as a string *value* inside `body` rather than becoming a record of its
  own, because every field goes through `json.dumps` in the formatter.
- **NOTF-03 is proven by a re-read, not by a status code.** With `get_email_notifier` overridden
  by a notifier that raises, the request is still 200, the assignment is still there on a fresh
  `GET`, and one WARNING naming the task id was logged with its traceback. Removing
  `AssignTask`'s `commit()` was observed turning exactly that re-read red while the 200 and the
  response body still passed - which is the whole argument for the second request.
- **The statement counts now include what D-11 costs.** `test_statements.py` runs on
  `authenticated_client`, so every request carries a real bearer token and reaches the
  confirmation read: `GET /api/v1/task-lists` issues **2** and the task collection **4**, each
  entry named in the constant's comment, with the actor lookup first. The invariance property -
  `for_one == for_many` - is untouched, and the module now says so explicitly so that a later
  reader does not mistake a measurement for a target.
- **Counts differ by role, and the difference was measured.** Owner `GET` of one task: 3
  `SELECT`s. Assignee: 2. Owner `PATCH .../status`: 4 `SELECT`s and one `UPDATE`. Assignee: 3
  and one `UPDATE`. The module docstring records the rule that any future count assertion must
  say which role it measures.
- **Two writers, two people, one row.** The owner renames the task by hand on one connection
  while the assignee completes it through the real use case on another. The assignee waits,
  then answers with the owner's new title - which is what proves it read the committed state -
  and the row ends with both writes. With the owner's `for_update` removed the test fails on
  the lost rename (T-5-17).
- **The six statements this plan owed are covered.** `routers/assignments.py` is back at 32/32,
  and the suite's total coverage is **100.00%** with no `pragma: no cover` anywhere in
  `src/taskmanager`.

## Deviations from Plan

### Auto-fixed issues

**1. [Rule 3 - Blocking] `getattr(record, "event")` is a flake8-bugbear B009 violation**

- **Found during:** Task 2
- **Issue:** The notification's fields are passed through `extra=`, so they are not declared
  members of `logging.LogRecord`. `record.event` fails `mypy --strict` with `attr-defined`, and
  the `getattr` form that satisfies mypy produced four B009 violations in `make lint`.
- **Fix:** A one-line `extras(record)` helper returning `vars(record)`, with the two failed
  alternatives and the reason recorded in its docstring. `vars()` is also what `JsonFormatter`
  itself iterates, so the test asks the same question the application does.
- **Files modified:** `tests/integration/api/test_assignment.py`
- **Commit:** f020c33

### Deliberate departures

**1. A falsification file instead of a TDD RED capture.** The plan marks all three tasks
`tdd="true"`, and a RED step was not available: 05-08 and 05-12 shipped the behaviour, so every
test here passed the moment it was written. Four falsifications were recorded instead, each
breaking the one decision the assertion exists to pin. This is the same compromise 02-01 and
05-13 recorded, arrived at from the other direction.

**2. `MISSING_TASK_ID` and `INJECTED_TITLE` were planned imports/constants that changed shape.**
`MISSING_TASK_ID` is not imported - no test in this module needs an absent task, because the
stranger's refusal is about a task that plainly exists. `INJECTED_TITLE` is declared in Task 2's
section rather than at the top, beside the two tests that use it.

**3. The concurrency fixture, not just the new test, gained the assignee.** The plan allowed
either extending `_remove_what_was_committed` or making the assignee reachable by the existing
cascade. The cascade cannot reach them - `ON DELETE SET NULL` - so the cleanup names both rows,
and its docstring now argues the change rather than merely surviving it.

## Verification

| Gate | Result |
|---|---|
| `make lint` | pass - black, isort and flake8 over 179 files |
| `make typecheck` | pass - `Success: no issues found in 179 source files` |
| `make arch` | pass - `Contracts: 4 kept, 0 broken.` |
| `make test` | pass - **919 passed in 6.90s**, `Required test coverage of 75% reached. Total coverage: 100.00%` |
| `grep -rn "pragma: no cover" src/taskmanager/` | 0 hits |

Every acceptance criterion in the plan was checked literally:

- `test_assignment.py` collects **25** tests (16 asked); `-k assign` **25** (8 asked);
  `-k assignee_id` **3** (2); `-k assigned_to_me` **3** (3); `-k notifies` **4** (1);
  `-k notifier_failure` **1** (1).
- `grep -c`: `user_not_found` 7 (2 asked), `PROBLEM_JSON` 4 (4), `updated_at` 6 (1),
  `at_level` 8 (3), `task_assigned_email` 3 (1), `get_email_notifier` 6 (2).
- `test_statements.py`: `authenticated_client` 9 (2 asked), `D-11` 4 (1), and the plan's
  constant-length script exits 0 with 2 and 4.
- `test_concurrent_writes.py` collects 4, one more than before, and `-k owner_and_assignee`
  collects 1.

## Known Stubs

None.

## Threat Flags

None. This plan adds no route, no schema and no network surface; it only measures the ones
Phase 5 already shipped.

## Notes for Later Plans

- **05-15's permission matrix must not re-litigate D-03 per cell.** Every leg of the assignee's
  row is already asserted here with a re-read; the matrix's value is completeness across all
  nineteen routes and four callers, including the anonymous column.
- **Any new statement-count assertion must name its role.** The assignee's `GET` and
  `PATCH .../status` are one `SELECT` cheaper than the owner's, and a count written without
  saying whose it is will look like a regression to the next reader.
- **The compose stack was not touched.** No container was rebuilt, restarted or stopped, and
  neither the `taskmanager` volume nor its one old demo-seed row was altered. This plan's
  notification assertions are made through `caplog` on the host suite, not through
  `docker compose logs api`, so the stale `api` image was never in the way.
- **`tests/integration/api/test_assignment.py` now exports reusable pieces** for 05-15:
  `assignee_url`, `headers_for`, `a_task_held_by`, `the_assignee`, `the_stranger`,
  `assert_forbidden`, `ASSIGNED_TO_ME` and the three `given_*` fixtures.

## Self-Check: PASSED

- `tests/integration/api/test_assignment.py` - FOUND
- `.planning/phases/05-auth-assignment-notifications/evidence/05-14-falsification.txt` - FOUND
- Commits `d1203c3`, `f020c33`, `32f0523` - all FOUND in `git log`
