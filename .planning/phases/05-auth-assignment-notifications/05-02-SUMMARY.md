---
phase: 05-auth-assignment-notifications
plan: 02
subsystem: application-ports
tags: [ports, protocol, repository, argon2, timing-equalisation, ordering, tdd]

# Dependency graph
requires:
  - phase: 02-domain-error-contract
    provides: "the eight Protocol ports, their in-memory fakes and the mypy-strict port-conformance convention (no ABC, no isinstance)"
  - phase: 03-persistence-migrations
    provides: "SqlAlchemyTaskRepository with its ORDER BY created_at, id idiom and task_to_entity; SqlAlchemyUserRepository.list_all already ordered (WR-03)"
  - phase: 04-task-lists-tasks
    provides: "the fake-versus-adapter ordering precedent fixed in 04-02 and 04-06, and its falsification capture"
provides:
  - "PasswordHasher.dummy_verify(password) -> None, the port method D-12's timing equalisation is implemented through"
  - "FakePasswordHasher.dummy_verifications, a recorder a Login test can assert on without measuring a clock"
  - "TaskRepository.list_for_assignee(assignee_id) -> Sequence[Task], on the port, the SQLAlchemy adapter and the fake, all ordered by (created_at, id)"
  - "FakeUserRepository.list_all ordered by (created_at, id), matching the adapter it stands in for"
affects: [05-05, 05-06, 05-07, 05-08, 05-09, 05-16]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A port method returning None is enforced as unreadable by mypy strict: writing `assert await port.method(...) is None` fails typecheck with func-returns-value, which is a stronger guarantee than the runtime assertion it replaces"
    - "A fake's divergence from its adapter is falsified before it is fixed, and the failing run is committed beside the fix"

key-files:
  created:
    - .planning/phases/05-auth-assignment-notifications/evidence/05-02-tdd-red.txt
    - .planning/phases/05-auth-assignment-notifications/evidence/05-02-fake-user-ordering.txt
  modified:
    - src/taskmanager/application/ports/security.py
    - src/taskmanager/application/ports/repositories.py
    - src/taskmanager/infrastructure/db/repositories/tasks.py
    - tests/unit/application/fakes.py
    - tests/unit/application/test_ports.py
    - tests/unit/application/test_fakes.py
    - tests/integration/test_repositories_tasks.py

key-decisions:
  - "The `assert await hasher.dummy_verify(...) is None` the plan's behaviour block asks for was written, observed to fail `make typecheck` with `Function does not return a value (it only ever returns None)`, and dropped in favour of recording why - mypy strict already forbids every caller from reading the return, which is exactly what the port's comment asks for and more than a runtime assertion can establish; the runtime claim survives in the plan's acceptance snippet, which runs outside mypy"
  - "The dummy_verify test folds the declaration check (`\"dummy_verify\" in PasswordHasher.__dict__`) into the same test as the binding, following the two existing declaration tests in test_ports.py: dropped from the Protocol and the fake together, the typed binding alone would still compile"
  - "list_for_assignee takes no status or priority keyword and the port comment says so as a decision - filtering assigned-to-me is a 05-CONTEXT Deferred Idea, and widening a signature later is additive while a caller depending on filters nobody asked for is not"
  - "The integration suite gained a second owner and a third list rather than widening given_a_list_with_an_owner: the existing helper builds two lists under ONE owner, which cannot prove a cross-owner answer, and changing it would have altered the world every other test in the module runs in"
  - "The adapter's ordering test seeds Water the plants before Buy milk although the two share an instant and Buy milk has the lower id - the reverse of the expected answer, so a statement that dropped the id tie-break fails rather than flakes"
  - "Both assignee empty-case tests ask about OTHER_OWNER_ID, a real account that owns a list containing one of the assignee's tasks, as well as an unknown id: an implementation answering by list membership rather than by assignee_id would hand that caller somebody else's task"
  - "Requirement ticks AUTH-04, ASGN-02 and ASGN-03 deliberately NOT taken - 05-16 is the last claimant, and this plan ships two port methods and a fake fix with no use case and no route above them"

patterns-established:
  - "A `-> None` port method needs no runtime return assertion: mypy strict's func-returns-value error is the gate, and the test docstring records that the omission is the claim"

requirements-completed: []

# Metrics
duration: 10min
completed: 2026-09-19
---

# Phase 5 Plan 02: Port Extensions and Fake Alignment Summary

**The two port changes Phase 5 genuinely needs — `PasswordHasher.dummy_verify` for D-12's timing
equalisation and `TaskRepository.list_for_assignee` for D-02's discovery route — each shipped as
one deliberate commit with every implementation moved at once, plus the last in-memory fake still
answering in insertion order brought into line with its adapter after being observed doing it.**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-09-19T08:37Z
- **Completed:** 2026-09-19T08:47Z
- **Tasks:** 3 of 3
- **Files modified:** 9 (2 created, 7 modified)

## Accomplishments

- `PasswordHasher` gained exactly one method, and the module docstring now argues for it in the
  register the file already used: three named alternatives (the application computing the hash,
  a hard-coded Argon2 string, a per-construction hash in `Login`) are each rejected with the
  reason, the measured 23.6 ms cost is cited, and D-21 is named as the decision that authorised
  the only port extension 05-CONTEXT's "the ports keep their shape" note has taken.
- `FakePasswordHasher` gained `dummy_verifications`, so plan 05-07 can assert the unknown-email
  leg performed the equalising work without reading a clock — the list is the observable, not the
  elapsed time.
- `TaskRepository.list_for_assignee` exists on the port, on `SqlAlchemyTaskRepository` as a single
  `WHERE assignee_id = ... ORDER BY created_at, id`, and on `FakeTaskRepository` with the same
  sort. Six new tests cover it: the fake's filter, empty and order, and the adapter's cross-owner
  span, empty and order.
- The adapter's cross-list claim is proven against a genuinely foreign list: a third user owning a
  third list, with one of the assignee's tasks inside it, so a statement scoped by owner — or by
  the parent of the first row it found — fails. Two decoys older than everything else (a task
  assigned to the list's owner, a task assigned to nobody) mean a lost `WHERE` puts a wrong row
  *first* rather than merely returning too much.
- `FakeUserRepository.list_all` is sorted, and the divergence was falsified rather than asserted:
  the failing run and the passing run are both in
  `evidence/05-02-fake-user-ordering.txt`. It was the last of the three fakes still answering in
  insertion order — 04-02 fixed `list_for_owner`, 04-06 fixed `list_for_task_list`, and
  05-RESEARCH Pitfall 9 found this one.
- The suite went from 659 to 667 passing at 100.00% coverage over 1202 statements, with no
  `pragma: no cover` and no `omit` anywhere under `src/taskmanager/`. `tests/unit` plus
  `tests/architecture` went from 464 to 469.

## Task Commits

1. **Task 1: The D-21 `PasswordHasher` port extension** — `5f1d25f` (feat)
2. **Task 2: `TaskRepository.list_for_assignee`, its adapter and its fake** — `ab6bb39` (feat)
3. **Task 3: Sort `FakeUserRepository.list_all`, after observing it unsorted** — `2d267e5` (fix)

## Files Created/Modified

- `src/taskmanager/application/ports/security.py` — `dummy_verify` on the Protocol with a comment
  saying the `None` return is deliberate and unbranchable; a docstring section arguing D-21 by
  name, naming `pwdlib` and the `application-framework-free` contract, and listing the three
  rejected ways of producing the throwaway hash.
- `src/taskmanager/application/ports/repositories.py` — `list_for_assignee` on `TaskRepository`,
  with the "the filter belongs in the SQL" argument restated for a query that would otherwise read
  every task in the database, and the absent `status` / `priority` keywords recorded as a Deferred
  Idea rather than an oversight.
- `src/taskmanager/infrastructure/db/repositories/tasks.py` — the adapter method: one statement,
  `task_to_entity` mapping, no transaction-ending call. Its docstring states that *who may ask for
  this `assignee_id`* is the use case's decision (T-5-11), so the question never reaches SQL.
- `tests/unit/application/fakes.py` — `FakePasswordHasher.__init__` plus `dummy_verify` and its
  recorder; `FakeTaskRepository.list_for_assignee`; `FakeUserRepository.list_all` sorted, with the
  comment naming D-25 and recording that this fake was missed when the two siblings were fixed.
- `tests/unit/application/test_ports.py` — one new test binding the fake to the port, asserting
  the declaration and the recorder; its docstring records why there is no `is None` assertion.
- `tests/unit/application/test_fakes.py` — three `list_for_assignee` cases over a shared
  `_given_assignments` seeding, one `list_all` ordering case, and a module docstring that now
  covers all three fakes rather than two methods of one.
- `tests/integration/test_repositories_tasks.py` — `given_a_second_owner_with_a_list` and
  `given_assignments_across_two_owners` helpers, three assignee tests, and five new fixed
  identifiers. No existing test's world changed.
- `.planning/phases/05-auth-assignment-notifications/evidence/05-02-tdd-red.txt` — **created.**
  The observed RED for Tasks 1 and 2, including the mypy finding below.
- `.planning/phases/05-auth-assignment-notifications/evidence/05-02-fake-user-ordering.txt` —
  **created.** The unsorted user fake failing, then passing.

## Decisions Made

- **The `is None` assertion the plan asks for cannot be written, and its absence is the stronger
  claim.** Task 1's behaviour block says "`FakePasswordHasher().dummy_verify("anything")` awaits
  and returns `None`". Written literally as `assert await hasher.dummy_verify("pw") is None`, mypy
  strict answers `Function does not return a value (it only ever returns None)
  [func-returns-value]` and `make typecheck` fails. That is the port comment's rule — "a caller has
  nothing to branch on" — being enforced by the type checker rather than by convention: *no* caller
  can read this return, which a passing runtime assertion could never establish. The assertion was
  dropped, the reason written into the test's docstring, and the runtime claim kept in the plan's
  acceptance snippet, which runs outside mypy and passes.
- **The port-declaration check rides in the same test as the binding.** `test_ports.py` already has
  two tests asserting a capability is declared on the Protocol, for the case where a method is
  dropped from the port *and* its fake together — the typed binding alone stays green. `dummy_verify`
  is exactly that shape, so the assertion joins the new test rather than becoming a third
  near-identical one.
- **`list_for_assignee` takes one argument and will not be widened here.** The signature is pinned
  by the plan's acceptance snippet against both implementations. Filtering `assigned-to-me` by
  status or priority is in 05-CONTEXT's Deferred Ideas, and the port comment says so, because a
  reader comparing it to `list_for_task_list`'s two keywords would otherwise read the asymmetry as
  an oversight.
- **A second owner was added rather than the base helper widened.** `given_a_list_with_an_owner`
  builds two lists owned by one user, which cannot distinguish "every task assigned to me" from
  "every task in my owner's lists". Widening it would have put a third user and a third list into
  the world of all twenty existing tests in the module for the benefit of three; a separate helper
  costs eight lines and changes nothing else.
- **Both assignee empty-case assertions use a real account, not only a missing id.**
  `OTHER_OWNER_ID` owns the list holding `Fix the shelf`, so an adapter that answered by list
  membership would return that task here. The unknown id is asked too, and answers the same, because
  an adapter must not distinguish "no assignments" from "no such user" — who may learn a user exists
  is ADR-008's question and belongs to a use case.
- **No requirement ticks taken.** The plan's frontmatter names AUTH-04, ASGN-02 and ASGN-03. 05-16
  is the last claimant of all three under this project's convention, and this plan ships two port
  methods, one adapter method and a fake fix, with no use case and no route above any of them. The
  same call Phase 3 made ten consecutive times, Phase 4 eleven, and 05-01 once.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] The plan's prescribed `is None` assertion fails `make typecheck`**

- **Found during:** Task 1
- **Issue:** The task's behaviour block and its acceptance criteria both express the `None` return
  as something the test asserts. Inside the test suite, which `mypy --strict` checks, reading the
  return of a `-> None` function is `func-returns-value` and the pre-commit `mypy (strict)` hook
  refuses the commit.
- **Fix:** the call is awaited without binding; the test docstring records that mypy already
  forbids every caller from reading the return, which is what the port comment asks for. The
  runtime `is None` claim is still made by the plan's acceptance snippet (`.venv/bin/python -c`),
  which runs outside mypy and exits 0.
- **Files modified:** `tests/unit/application/test_ports.py`
- **Verification:** `.venv/bin/mypy src tests` → `Success: no issues found in 141 source files`;
  the acceptance snippet printed `acceptance snippet ok`
- **Committed in:** `5f1d25f`, and both the red and the reasoning are in `05-02-tdd-red.txt`

**2. [Rule 2 - Missing critical functionality] A second evidence file the plan did not enumerate**

- **Found during:** Tasks 1 and 2
- **Issue:** both tasks are `tdd="true"` and the plan names only Task 3's capture as an artifact.
  A TDD task whose red step is neither committed nor captured leaves the cycle unevidenced, which
  is the gap 05-01 closed by writing `05-01-tdd-red.txt` under the same conditions.
- **Fix:** `evidence/05-02-tdd-red.txt` carries the red runs for both port extensions — pytest and
  mypy, before and after — and the mypy finding above.
- **Files modified:** `.planning/phases/05-auth-assignment-notifications/evidence/05-02-tdd-red.txt`
- **Verification:** committed with the tasks it documents
- **Committed in:** `5f1d25f` and `ab6bb39`

**3. [Rule 3 - Blocking] The TDD RED step still cannot be its own commit**

- **Found during:** Tasks 1 and 2
- **Issue:** the canonical cycle wants a `test(...)` commit carrying a failing test. Adding a
  method to a Protocol breaks every implementation at once, and the pre-commit `mypy (strict)` hook
  rejects a test naming a member no module exports (`"PasswordHasher" has no attribute
  "dummy_verify"`, `"SqlAlchemyTaskRepository" has no attribute "list_for_assignee"`).
  `--no-verify` is forbidden by CLAUDE.md.
- **Fix:** RED was observed and captured; the port, the adapter, the fake and the tests ship
  together as one green commit per task. The 02-01 / 04-02 / 05-01 compromise, applied for the same
  reason.
- **Verification:** `05-02-tdd-red.txt` shows `1 failed, 15 passed` and `3 failed, 6 passed`
  before, `Success: no issues found` after
- **Committed in:** `5f1d25f` and `ab6bb39`

### Notes, not deviations

- `-k assignee` collects **4** tests in `tests/integration/test_repositories_tasks.py`, not the
  three this plan added: the pre-existing
  `test_a_task_for_a_missing_assignee_raises_user_not_found` matches the same substring. The
  criterion asks for at least 3.
- `grep -c "sorted(" tests/unit/application/fakes.py` prints **5**, not the plan's expected
  floor of 4 — the two sibling fakes, `list_all`, `list_for_assignee`, and
  `list_for_owner_with_stats`, which the plan's enumeration omitted. The criterion is "at least 4".
- The `trailing-whitespace` pre-commit hook rewrote `05-02-fake-user-ordering.txt` on the first
  commit attempt: pytest's assertion diff emits lines consisting of `E` and a trailing space. The
  capture is otherwise verbatim, and the same hook has processed every prior evidence file.

## Threat Flags

None. Every file touched is either a Protocol declaration, one SQL `SELECT` with a `WHERE` and an
`ORDER BY`, or test material. The one new query is dispositioned in the plan's register as T-5-11
and is mitigated as written: it takes exactly one argument, filters in SQL, and has no `owner_id`
widening for a caller to reach through.

## Self-Check: PASSED

All nine files named above exist on disk, and all four commits
(`5f1d25f`, `ab6bb39`, `2d267e5`, `ae279f0`) are reachable from `main`.
