---
phase: 04-task-lists-tasks
plan: 05
subsystem: application
tags: [use-cases, task-lists, adr-008, list-06, n-plus-one, patch-semantics, transactions]

# Dependency graph
requires:
  - phase: 04-task-lists-tasks
    provides: "04-01's Unset sentinel and the TaskList.rename / TaskList.describe mutators"
  - phase: 04-task-lists-tasks
    provides: "04-02's TaskListRepository.list_for_owner_with_stats on the port, the adapter and the fake"
  - phase: 04-task-lists-tasks
    provides: "04-03's access.py — visible_task_list, the one copy of ADR-008"
  - phase: 04-task-lists-tasks
    provides: "04-04's five task-list commands and TaskListResult.from_entity(task_list, stats)"
  - phase: 02-domain-error-contract
    provides: "UnitOfWork / Clock ports, the DomainError hierarchy, FakeUnitOfWork and FrozenClock"
provides:
  - "CreateTaskList, GetTaskList, ListTaskLists, UpdateTaskList, DeleteTaskList — the five classes 04-08's routers call"
  - "The 404-not-403 answer proved per verb with two actors (D-04)"
  - "LIST-03 as a count: the collection calls the per-list statistics query zero times"
  - "The decision that updated_at moves whenever a field is provided (ADR owed by 04-12)"
affects: [04-06, 04-07, 04-08, 04-09, 04-10, 04-11, 04-12]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A read-only use case takes the unit of work alone (no Clock), makes nothing durable, and asserts commits == 0 / rollbacks == 1 on its SUCCESS path"
    - "Every verb enters access.visible_task_list rather than restating the ownership condition"
    - "A PATCH guard reads `command.field is not UNSET`, and mypy narrows the sentinel away so the entity mutator receives its declared type"
    - "The N+1 is refused by instrumentation, not by inspection: a counting subclass of the task fake tallies per-list statistics calls and the collection test requires zero"

key-files:
  created:
    - src/taskmanager/application/use_cases/task_lists/__init__.py
    - src/taskmanager/application/use_cases/task_lists/create.py
    - src/taskmanager/application/use_cases/task_lists/get.py
    - src/taskmanager/application/use_cases/task_lists/list.py
    - src/taskmanager/application/use_cases/task_lists/update.py
    - src/taskmanager/application/use_cases/task_lists/delete.py
    - tests/unit/application/test_create_task_list.py
    - tests/unit/application/test_get_task_list.py
    - tests/unit/application/test_list_task_lists.py
    - tests/unit/application/test_update_task_list.py
    - tests/unit/application/test_delete_task_list.py
  modified: []

key-decisions:
  - "A brand-new list's counters are constructed locally as a module-level CompletionStats(total=0, completed=0) rather than read back: nothing else ran inside the transaction, so a statistics query would be a round trip whose answer is already known"
  - "updated_at moves whenever a field is PROVIDED, and therefore does NOT move when a command carries neither field — the plan's task text expected a stamp in that case, but stamping unconditionally would contradict both the discretion decision (04-PATTERNS Pitfall 10) and the verified 04-RESEARCH body; D-06 refuses an empty body at the schema, so the case never reaches the API"
  - "list.py spells list_for_owner_with_stats exactly once, on the call — the docstring names the capability in prose instead, so `grep -c` over the file answers 'how many queries does the collection cost?' rather than counting mentions"
  - "The N+1 counter is a subclass declared in the test module, and the list repository is handed a SECOND, uncounted task repository sharing the very same `stored` dict: counting the fake's own bookkeeping would make the assertion measure nothing"
  - "GetTaskList and DeleteTaskList take no Clock at all, and a test reads that back off the constructor signature — a port accepted and never used would contradict what ARC-04 says a constructor is for"
  - "DeleteTaskList loads through the shared guard and discards the entity: the load is what turns a foreign list's silent 204 into a 404"
  - "Test clocks are stopped at LATER while fixture entities are stamped NOW, so a use case that copied a timestamp off something it read cannot pass the timestamp assertions"

patterns-established:
  - "Read-only use case: no clock, no commit, and the inverted transaction assertion on the success path"
  - "The D-04 pair test: produce BOTH refusals in one test and compare class, code, details and message, because 'answers exactly like an absent one' is a statement about a pair of error bodies"
  - "An N+1 assertion at the fake level, one layer below the statement counter plan 04-10 owns"

requirements-completed: []

# Metrics
duration: 12min
completed: 2026-09-18
---

# Phase 4 Plan 05: the five task-list use cases Summary

**LIST-01 through LIST-06 now exist as five single-purpose classes over the `UnitOfWork` and `Clock` ports alone — with the 404-not-403 answer proved per verb by two actors, the collection's N+1 refused by a counter rather than by a comment, and "a read never commits" asserted on the success path instead of assumed.**

## Performance

- **Duration:** ~12 min (23:29 → 23:41)
- **Tasks:** 3 of 3, one commit each
- **Files:** 11 created, 0 modified

## Accomplishments

- `application/use_cases/task_lists/` holds five classes, each `execute(command) -> result`, each constructed from the unit of work plus only the ports it actually touches: `CreateTaskList(uow, clock)`, `GetTaskList(uow)`, `ListTaskLists(uow)`, `UpdateTaskList(uow, clock)`, `DeleteTaskList(uow)`. The two that stamp nothing ask for no clock, and a test reads that back off `inspect.signature`.
- Every verb loads through `access.visible_task_list`, so ADR-008 is *entered* rather than restated. Four tests across the three addressed verbs produce the absent-list refusal and the foreign-list refusal side by side and compare class, `code`, `details` and rendered message — the foreign owner's identifier appears in neither (T-4-22).
- `ListTaskLists` issues exactly one repository call for the whole collection. The proof is a count: the test module injects a `FakeTaskRepository` subclass that tallies per-list statistics calls, and the collection is required to have made zero of them while still reporting `50.0` for a half-finished list. Plan 04-10's statement counter is the same claim one layer up; a regression now fails in both (T-4-24).
- LIST-06 is served on both legs. The create leg pre-checks before anything is written; the rename leg pre-checks **only when the name actually changes**, so a PATCH that resends the list's own name is not refused by the row it is about to rewrite. Both docstrings record that `uq_task_lists_owner_id_name` remains the authority under concurrency and that the adapter already translates its refusal — the pre-check buys the clean 409, it is not a second copy of the rule (T-4-25).
- D-05's three legs are separate tests: a field omitted is untouched, a field carrying a value is written, and a field carrying an explicit null is cleared. The sentinel guard narrows under mypy strict, so the `None` that means "clear it" reaches `describe()` while the sentinel cannot.
- `DeleteTaskList` loads the list before deleting it, and the foreign-list test asserts the row is *still there* afterwards. An implementation that deleted first and authorized second would raise the right error over a destroyed row; one that skipped the load entirely would answer 204 to a stranger.
- Read-only use cases assert `commits == 0` **and** `rollbacks == 1` on the success path. The second half is what proves the transaction was closed rather than merely left alone — `commits == 0` is equally true of a unit of work nobody ever exited.

## Task Commits

1. **Task 1: `CreateTaskList` with the LIST-06 pre-check** — `be70b98` (feat)
2. **Task 2: `GetTaskList` and `ListTaskLists`, the two reads that never commit** — `12cdf1c` (feat)
3. **Task 3: `UpdateTaskList` (PATCH + rename conflict) and `DeleteTaskList`** — `34fca0d` (feat)

**Plan metadata:** see the final `docs(04-05)` commit.

## Files Created

| File | Statements | Coverage | Notes |
|------|-----------:|---------:|-------|
| `use_cases/task_lists/__init__.py` | 0 | 100% | Empty, mirroring `use_cases/tasks/__init__.py` |
| `use_cases/task_lists/create.py` | 22 | 100% | LIST-01 + the create leg of LIST-06 |
| `use_cases/task_lists/get.py` | 12 | 100% | LIST-02, no clock, nothing durable |
| `use_cases/task_lists/list.py` | 6 | 100% | LIST-03 over the one grouped call |
| `use_cases/task_lists/update.py` | 25 | 100% | LIST-04 + the rename leg of LIST-06 |
| `use_cases/task_lists/delete.py` | 11 | 100% | LIST-05, load-then-delete |
| `tests/unit/application/test_create_task_list.py` | — | — | 7 tests |
| `tests/unit/application/test_get_task_list.py` | — | — | 5 tests |
| `tests/unit/application/test_list_task_lists.py` | — | — | 6 tests |
| `tests/unit/application/test_update_task_list.py` | — | — | 9 tests |
| `tests/unit/application/test_delete_task_list.py` | — | — | 6 tests |

33 new tests in all; the plan asks for at least 5 + 10 + 12 = 27.

## Gate Results

| Gate | Result |
|------|--------|
| `make lint` | green (black, isort, flake8) |
| `make typecheck` | green — `Success: no issues found in 115 source files` |
| `make arch` | `Contracts: 4 kept, 0 broken.` |
| `make test` | `413 passed`, **Total coverage: 100.00%** (`Required test coverage of 75% reached`) |
| `taskmanager.application.use_cases.task_lists` coverage | 76 statements, **0 missing lines** across all five modules |
| `grep -rn "HTTPException\|fastapi\|sqlalchemy" .../use_cases/task_lists/` | no matches |
| `grep -c "exists_with_name" create.py` | `1` |
| `grep -c "commit()" create.py` | `1` |
| `grep -c "commit()" get.py` / `list.py` | `0` / `0` |
| `grep -c "completion_stats" list.py` | `0` |
| `grep -c "list_for_owner_with_stats" list.py` | `1` |
| `grep -c "is not UNSET" update.py` | `2` |
| `grep -c "command.name != task_list.name" update.py` | `1` |
| `pytest -k "not_owned or other_actor or OTHER_USER"` | `4 passed` (plan asks for at least 4) |
| `pytest -k "updated_at_moves"` | `1 passed` (plan asks for exactly 1) |
| `CreateTaskList.__init__` parameters | `['uow', 'clock']` |

## Deviations from Plan

### 1. [Judgement recorded] A command with neither field provided does **not** move `updated_at`

- **Found during:** Task 3.
- **Issue:** The plan's task text asks for a test asserting that when both fields are `UNSET`, "nothing changes except `updated_at`". That expectation requires an unconditional stamp, which contradicts two things the same plan relies on: the discretion decision it asks to be recorded (04-PATTERNS Pitfall 10 — "`updated_at` moves whenever a field is **provided**") and the verified `UpdateTaskList` body in 04-RESEARCH, where the only stamps are inside the two sentinel guards.
- **Fix:** The verified body was implemented unchanged, and the test asserts `updated_at == NOW` (unmoved) together with `commits == 1`. Its docstring states the reasoning: the stamp follows a field being provided, no field was provided, and D-06 answers an empty body with a 422 before a command is ever built — so this pins the use case's behaviour for a request the API does not deliver, which is exactly why it is worth a test.
- **Files modified:** `use_cases/task_lists/update.py`, `tests/unit/application/test_update_task_list.py`
- **Commit:** `34fca0d`

### 2. [Rule 3 - Blocking] `grep -c "list_for_owner_with_stats" list.py` printed `2`

- **Found during:** Task 2.
- **Issue:** The docstring named the capability in backticks and the call named it again, so the plan's acceptance criterion (`prints 1`) failed on prose rather than on behaviour — the same shape as 04-03's `TaskListNotFoundError` count.
- **Fix:** Rather than record it as "met in substance", the docstring was reworded to describe the capability without spelling it, and it now says *why*: the name appears exactly once, on the call, so a `grep -c` over the file answers "how many queries does this collection cost?". This is the project's existing prose-not-literal convention (`Makefile`, `test_no_commit_in_repositories.py`) applied to a counter the plan wrote.
- **Files modified:** `use_cases/task_lists/list.py`
- **Commit:** `12cdf1c`

### 3. [Rule 1 - Bug] `answer = await use_case.execute(...)` fails mypy strict

- **Found during:** Task 3.
- **Issue:** The plan asks for a test that "`execute` returns `None`". Written as an assignment, mypy strict rejects it: `Function does not return a value (it only ever returns None)` — the gate was red before the commit.
- **Fix:** The claim moved to the contract, where it belongs: `get_type_hints(DeleteTaskList.execute)["return"] is type(None)`. Reading the annotation is also the stronger test — `None` is what an implementation that forgot its `return` hands back too, so a call-site assertion could not tell the two apart. `get_type_hints` rather than `inspect.signature` because it normalises `None` to `NoneType` identically on 3.13 and on the 3.14.3 host.
- **Files modified:** `tests/unit/application/test_delete_task_list.py`
- **Commit:** `34fca0d`

### 4. [Minor] Fixture entities are stamped `NOW` while the clocks read `LATER`

- **Found during:** Task 1.
- **Issue:** The plan describes the create result's timestamps as "`NOW` from the `FrozenClock`", which would make the fixture instant and the clock instant the same value.
- **Fix:** The clock is `FrozenClock(LATER)` and every pre-seeded entity is stamped `NOW`. Both readings satisfy "the timestamps come from the clock", and the split one is falsifiable: with a single instant, a use case that copied a timestamp off something it read from the repository would pass. Each module's docstring says so in one sentence.
- **Commit:** `be70b98`, `12cdf1c`, `34fca0d`

## Requirements

`LIST-01` … `LIST-06` are **not** ticked. Plans 04-08, 04-09 and 04-12 also claim them and 04-12 is the last claimant, which is the convention every plan in Phases 3 and 4 has followed. This plan ships the orchestration; no HTTP endpoint exists above it yet, so none of the six is demonstrable end to end.

## Threat Flags

None. Every entry of the plan's STRIDE register is mitigated by a named test:

| Threat | Where it is refused |
|--------|---------------------|
| T-4-22 cross-tenant read/update/delete | `test_get_task_list_hides_a_list_the_actor_does_not_own`, `test_update_task_list_hides_a_list_not_owned_by_the_actor`, `test_delete_task_list_hides_a_list_not_owned_by_the_actor`, plus the three pair-comparison tests |
| T-4-23 a foreign list in the collection | `test_list_task_lists_never_shows_another_owners_list` |
| T-4-24 N+1 on the index | `test_the_collection_never_asks_for_one_lists_statistics` |
| T-4-25 duplicate name under concurrency | `test_create_task_list_refuses_a_name_the_owner_already_uses`, `test_update_task_list_refuses_a_rename_onto_a_name_the_owner_uses`, and both docstrings naming the index as the authority |
| T-4-26 a refused write that still commits | every failure test asserts `commits == 0` and `rollbacks == 1` |
| T-4-27 `owner_id` taken from the request | `test_create_task_list_returns_the_owner_the_instant_and_zero_statistics` asserts `result.owner_id == ACTOR_ID`; the command has no owner field to take instead |

## Known Stubs

None. All five use cases are complete and wired to real ports; nothing returns a placeholder value.

## Handoff Notes

- **04-08 (routers):** construct these with the unit of work from `get_uow` and — for `CreateTaskList` and `UpdateTaskList` only — the `Clock` adapter. `GetTaskList`, `ListTaskLists` and `DeleteTaskList` take **one** argument; passing a clock is a type error, not a harmless extra.
- **04-08, again:** the router converts Pydantic's `model_fields_set` into `UNSET`. Do not pass `None` for an omitted field — `UpdateTaskList` would read that as D-05's explicit null and clear the description.
- **04-08 / 04-09:** `DeleteTaskList.execute` returns `None`, which is what LIST-05's 204 needs; do not wrap it in a result.
- **04-09 (integration):** the cascade is asserted there, not here. This plan deliberately deletes only the parent and leans on `ON DELETE CASCADE`, so an integration test that creates tasks, deletes the list and counts rows is the only honest proof.
- **04-10 (statement counter):** `ListTaskLists` is already instrumented at the fake level. The HTTP counter should find the same number of statements for 1 list and for N.
- **04-12 (ADRs):** two decisions are owed an entry — `updated_at` moves whenever a field is provided (with the "and therefore not at all when none is" consequence recorded above), and the pre-check-plus-unique-index division of labour for LIST-06.
- **Nothing in `presentation/api/errors/` needs a change.** `DuplicateTaskListNameError` resolves to 409 and `TaskListNotFoundError` to 404 through the MRO table already in place.

## Self-Check: PASSED

- `src/taskmanager/application/use_cases/task_lists/__init__.py` — FOUND
- `src/taskmanager/application/use_cases/task_lists/create.py` — FOUND, contains `class CreateTaskList`
- `src/taskmanager/application/use_cases/task_lists/get.py` — FOUND, contains `class GetTaskList`
- `src/taskmanager/application/use_cases/task_lists/list.py` — FOUND, contains `class ListTaskLists`
- `src/taskmanager/application/use_cases/task_lists/update.py` — FOUND, contains `class UpdateTaskList`
- `src/taskmanager/application/use_cases/task_lists/delete.py` — FOUND, contains `class DeleteTaskList`
- `tests/unit/application/test_create_task_list.py` — FOUND, 7 tests passing
- `tests/unit/application/test_get_task_list.py` — FOUND, 5 tests passing
- `tests/unit/application/test_list_task_lists.py` — FOUND, 6 tests passing
- `tests/unit/application/test_update_task_list.py` — FOUND, 9 tests passing
- `tests/unit/application/test_delete_task_list.py` — FOUND, 6 tests passing
- commit `be70b98` — FOUND
- commit `12cdf1c` — FOUND
- commit `34fca0d` — FOUND
