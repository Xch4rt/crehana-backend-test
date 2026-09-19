---
phase: 04-task-lists-tasks
plan: 06
subsystem: application
tags: [use-cases, tasks, adr-008, adr-009, d-14, patch-semantics, filters, transactions]

# Dependency graph
requires:
  - phase: 04-task-lists-tasks
    provides: "04-01's Unset sentinel, Task.describe / Task.reprioritise and Task.DEFAULT_PRIORITY"
  - phase: 04-task-lists-tasks
    provides: "04-03's access.py — visible_task_list and visible_task, the one copy of ADR-008 and D-14"
  - phase: 04-task-lists-tasks
    provides: "04-04's five task commands and TaskResult.from_entity / TaskCollectionResult.from_parts"
  - phase: 03-persistence
    provides: "TaskRepository.list_for_task_list's SQL-side filters and completion_stats"
  - phase: 02-domain-error-contract
    provides: "UnitOfWork / Clock ports, the DomainError hierarchy, FakeUnitOfWork and FrozenClock"
provides:
  - "CreateTask, GetTask, ListTasks, UpdateTask, DeleteTask — the five classes 04-08's task router calls"
  - "The wrong-list 404 (D-14) proved per verb against the absent-task refusal"
  - "TASK-07 as an equality: the filter never moves the three statistics"
  - "TASK-06's conjunction proved by a pair an OR implementation would fail"
  - "D-08 enforced from two directions: no status field on the command, no status mutator in the source"
  - "FakeTaskRepository.list_for_task_list now ordered by (created_at, id), matching the adapter"
affects: [04-07, 04-08, 04-09, 04-10, 04-11, 04-12]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "CreateTask is the single task verb whose refusal is list-shaped, because the caller addressed the list and no task identifier exists yet"
    - "The filter reaches SQL as keyword arguments; completion_stats takes the list id alone, and a regex over the source is an acceptance criterion"
    - "A conjunction is proved by two pairs — one matching no row, one matching exactly one — so OR and last-argument-wins both fail"
    - "A use case returning None is asserted from get_type_hints, never from a bound call: mypy strict refuses to let a value be read off it"

key-files:
  created:
    - src/taskmanager/application/use_cases/tasks/create.py
    - src/taskmanager/application/use_cases/tasks/get.py
    - src/taskmanager/application/use_cases/tasks/list.py
    - src/taskmanager/application/use_cases/tasks/update.py
    - src/taskmanager/application/use_cases/tasks/delete.py
    - tests/unit/application/test_create_task.py
    - tests/unit/application/test_get_task.py
    - tests/unit/application/test_list_tasks.py
    - tests/unit/application/test_update_task.py
    - tests/unit/application/test_delete_task.py
    - .planning/phases/04-task-lists-tasks/evidence/04-06-fake-ordering.txt
  modified:
    - tests/unit/application/fakes.py

key-decisions:
  - "CreateTask refuses with the LIST-shaped error while its four siblings refuse with the task-shaped one, and the module docstring argues the exception at length: the caller addressed the list, no task exists yet, and the identifier the error carries is the one the request already supplied — so there is nothing to disclose and no task id to answer with"
  - "updated_at moves whenever a field is PROVIDED and therefore does not move at all when a command carries none — the plan's task text says 'nothing changes except updated_at' for the all-omitted case, which contradicts the guarded shape the same plan specifies; 04-05 made the identical call and D-06 refuses an empty body at the schema, so the case never reaches the API"
  - "FakeTaskRepository.list_for_task_list gained the (created_at, id) sort the adapter has had since 03-07. 04-PATTERNS section 11 scheduled this for 'both list methods' and 04-02 applied it to the task-list side only, so the task side still returned insertion order — two ordering assertions were observed red against the unsorted fake before the fix"
  - "The list fixture is seeded in an order that is NOT the expected answer (E, B, A, D, C for an answer of C, A, B, D, E), because a fixture seeded in order makes a D-13 assertion pass against a fake that sorts nothing"
  - "The conjunction is pinned by TWO pairs, not one: completed+high matches no row and completed+low matches exactly one. The empty case alone would pass against an implementation that narrowed to nothing whenever two filters arrived; the one-row case alone would pass against an OR"
  - "test_the_filter_never_moves_the_statistics asserts the item counts DIFFER as well as the three counters matching, so the test cannot pass vacuously against a filter that was silently dropped"
  - "D-08 is asserted from the command's dataclass fields AND from a source scan of update.py for the status mutator's name, so 'status is not writable here' is true by shape rather than by convention"
  - "GetTask and DeleteTask take no Clock at all, and a test reads that back off the constructor signature — the 04-05 convention, unchanged"

patterns-established:
  - "The wrong-list pair test: produce the absent-task refusal and the wrong-list refusal in one test and compare class, code, details and rendered message (D-14)"
  - "A query-budget assertion beside the transaction assertion: one listing and one aggregate, counted by a subclass of the task fake declared in the test module"
  - "A falsification capture for a test-double fix — remove the fix, record the red, restore it, record the green (evidence/04-06-fake-ordering.txt)"

requirements-completed: []

# Metrics
duration: 11min
completed: 2026-09-18
---

# Phase 4 Plan 06: the five task use cases Summary

**TASK-01, TASK-02, TASK-03, TASK-04, TASK-06, TASK-07 and TASK-08 now exist as five single-purpose classes over the `UnitOfWork` and `Clock` ports alone — with the wrong-list 404 proved per verb against the absent-task refusal, TASK-06's conjunction proved by a pair an OR implementation would fail, and TASK-07's statistics proved not to follow the filter by an equality between two runs rather than by a comment.**

## Performance

- **Duration:** ~11 min (23:41 → 23:52)
- **Tasks:** 3 of 3, one commit each
- **Files:** 11 created, 1 modified

## Accomplishments

- `application/use_cases/tasks/` now holds six classes — the five this plan adds beside 04-03's `ChangeTaskStatus` — each `execute(command) -> result`, each constructed from the unit of work plus only the ports it actually touches: `CreateTask(uow, clock)`, `GetTask(uow)`, `ListTasks(uow)`, `UpdateTask(uow, clock)`, `DeleteTask(uow)`. The three that stamp nothing ask for no clock, and two tests read that back off `inspect.signature`.
- **Every verb enters the shared guard rather than restating it.** `GetTask`, `UpdateTask` and `DeleteTask` load through `visible_task`, so a task addressed under a list it does not belong to and a task whose parent list is foreign both answer `task_not_found` — with the same class, the same code, the same `details` and the same rendered message as an absent task. Four comparative tests across the three verbs produce *both* refusals and match all four properties; the parent list's identifier and the foreign owner's appear in none of them (T-4-28, T-4-29).
- **`CreateTask` is the deliberate exception, argued in full.** It addresses the *list*, so its refusal is list-shaped — the one asymmetry in the package, and the module docstring says why at length rather than leaving a reader to read it as an inconsistency: no task exists yet, so there is no task identifier to answer with, and the list identifier the error carries is the one the caller supplied themselves.
- **TASK-08's three refusals are proved to reach the caller from the entity, not restated here.** A blank title, a title one character past `Task.TITLE_MAX_LENGTH` and a deadline behind the creation moment each raise from `Task.create` through `CreateTask` with `details` naming the field, nothing in `added` and `commits == 0 / rollbacks == 1`. `grep -c "require_text\|max_length\|ValidationError"` over `create.py` prints `0`: no business limit is spelled twice.
- **TASK-06 reaches SQL.** `ListTasks` hands `status` and `priority` to `list_for_task_list` as keyword arguments and never filters a result in Python. The conjunction is pinned by two pairs — `completed` + `high` matches no row, `completed` + `low` matches exactly one — so an OR implementation and a last-argument-wins implementation each fail while both single-filter tests still pass. That is 03-07's own lesson, repeated one layer up.
- **TASK-07 is an equality between two runs.** `test_the_filter_never_moves_the_statistics` lists the same five-task fixture filtered and unfiltered and requires `total_tasks`, `completed_tasks` and `completion_percentage` to be identical *while the item counts differ*. The `completion_stats` call takes the list identifier alone, and a regex over `list.py` asserting no filter argument appears inside it is an acceptance criterion of the plan (T-4-32).
- **D-07 survives.** `test_a_patch_without_due_date_does_not_recheck_an_overdue_task` stores a task whose deadline is two hours behind the clock and patches only its title and priority. It succeeds — an implementation that re-applied the stored deadline unconditionally would refuse the request naming a field the caller never sent, and the task could never be renamed again (T-4-33).
- **D-08 is true by shape.** `UpdateTaskCommand` declares no `status`, `update.py` calls no status mutator, and `test_update_task_cannot_change_a_status` asserts both — the dataclass fields and a source scan — so the absence is not merely unreachable but unwritten. `grep -c "change_status" update.py` prints `0` (T-4-30).
- **A test-double divergence was found and closed with a falsification capture.** `FakeTaskRepository.list_for_task_list` returned insertion order while the adapter has ordered by `(created_at, id)` since 03-07. Removing the fix turned two ordering assertions red; restoring it turned them green; both captures are in `evidence/04-06-fake-ordering.txt`.

## Task Commits

1. **Task 1: `CreateTask` and `DeleteTask`** — `f43048a` (feat)
2. **Task 2: `GetTask` and `ListTasks` — the filter that must not move the number** — `a9d57cf` (feat)
3. **Task 3: `UpdateTask` — four optional fields, one of which is not there** — `e28f32d` (feat)

**Plan metadata:** see the final `docs(04-06)` commit.

## Files Created

| File | Statements | Coverage | Notes |
|------|-----------:|---------:|-------|
| `use_cases/tasks/create.py` | 19 | 100% | TASK-01, TASK-08; the list-shaped refusal |
| `use_cases/tasks/get.py` | 11 | 100% | TASK-02, no clock, nothing durable |
| `use_cases/tasks/list.py` | 13 | 100% | TASK-06 + TASK-07, two queries |
| `use_cases/tasks/update.py` | 25 | 100% | TASK-03, four sentinel guards |
| `use_cases/tasks/delete.py` | 11 | 100% | TASK-04, load-then-delete |
| `tests/unit/application/test_create_task.py` | — | — | 7 tests |
| `tests/unit/application/test_get_task.py` | — | — | 7 tests |
| `tests/unit/application/test_list_tasks.py` | — | — | 9 tests |
| `tests/unit/application/test_update_task.py` | — | — | 15 tests |
| `tests/unit/application/test_delete_task.py` | — | — | 7 tests |
| `evidence/04-06-fake-ordering.txt` | — | — | Red/green capture for the fake's `ORDER BY` |

45 new tests in all; the plan asks for at least 10 + 13 + 14 = 37.

## Files Modified

| File | Change |
|------|--------|
| `tests/unit/application/fakes.py` | `FakeTaskRepository.list_for_task_list` now returns `sorted(tasks, key=lambda entry: (entry.created_at, entry.id))`, matching the adapter's `ORDER BY` |

## Gate Results

| Gate | Result |
|------|--------|
| `make lint` | green (black, isort, flake8 — 125 files unchanged) |
| `make typecheck` | green — `Success: no issues found in 125 source files` |
| `make arch` | `Contracts: 4 kept, 0 broken.` |
| `make test` | `458 passed`, **Total coverage: 100.00%** (`Required test coverage of 75% reached`) |
| `taskmanager.application.use_cases.tasks` coverage | 95 statements over six modules, **0 missing lines and 0 partial branches** |
| `grep -rn "fastapi\|sqlalchemy\|HTTPException" .../use_cases/tasks/` | no matches |
| `grep -c "visible_task(" delete.py` | `1` |
| `grep -c "require_text\|max_length\|ValidationError" create.py` | `0` |
| `grep -c "commit()" get.py` / `list.py` | `0` / `0` |
| regex over `completion_stats(...)` in `list.py` | `completion_stats(command.task_list_id)` — no `status`, no `priority` |
| `grep -c "is not UNSET" update.py` | `4` |
| `grep -c "change_status" update.py` | `0` |
| `grep -c "reprioritise" update.py` | `2` (the call and the docstring's field list) |
| `UpdateTaskCommand` fields | `status` absent |
| `pytest -k "wrong_list or different_list"` | `8 passed` (plan asks for at least 2) |
| `pytest -k "filter_never_moves"` | `1 passed` (plan asks for exactly 1) |
| `pytest -k "conjunction"` | `2 passed` (plan asks for at least 1) |
| `pytest -k "overdue"` | `1 passed` (plan asks for at least 1) |

## Deviations from Plan

### 1. [Judgement recorded] A command with no field at all does **not** move `updated_at`

- **Found during:** Task 3
- **Issue:** the plan's task text asks for "all four omitted: nothing changes except `updated_at`, and the use case still commits". That is unreachable from the shape the same task specifies: four guards, each calling one mutator, and every stamp inside a guard. A command carrying no field reaches no mutator, so nothing stamps.
- **Decision:** kept the guarded shape and asserted `updated_at == NOW` for that case, exactly as 04-05 did for `UpdateTaskList`. Stamping outside the guards would contradict 04-PATTERNS Pitfall 10 and the verified 04-RESEARCH body, and would put a second "did this change?" rule beside mutators that already stamp unconditionally. D-06 refuses an empty body at the schema with a 422, so the request never arrives over HTTP; the test exists because nothing upstream would reveal a change in it.
- **Files:** `src/taskmanager/application/use_cases/tasks/update.py`, `tests/unit/application/test_update_task.py`
- **Commit:** `e28f32d`

### 2. [Rule 1 — Bug] `FakeTaskRepository.list_for_task_list` returned insertion order

- **Found during:** Task 2
- **Issue:** the SQLAlchemy adapter has ordered by `(created_at, id)` since 03-07, and 04-PATTERNS section 11 scheduled the matching `sorted(...)` for "both list methods" of the fakes. 04-02 applied it to `FakeTaskListRepository.list_for_owner` and `list_for_owner_with_stats`; the task side was left unsorted. A D-13 assertion written against it would have passed here and been free to fail over HTTP, where PostgreSQL answers in whatever order the plan produced.
- **Fix:** added the `(created_at, id)` sort with the comment its sibling already carries, and made the fixture seed order deliberately different from the expected answer so the assertion is not satisfied by coincidence.
- **Falsified, not asserted:** the sort was removed and the suite re-run — `test_list_tasks_orders_by_created_at_then_id` and `test_the_status_filter_narrows_the_items_on_its_own` both failed; restored, both pass. Captured in `evidence/04-06-fake-ordering.txt`.
- **Files:** `tests/unit/application/fakes.py`, `tests/unit/application/test_list_tasks.py`
- **Commit:** `a9d57cf`

### 3. [Acceptance criterion met in substance] `grep -c "visible_task_list" create.py` prints `2`, not `1`

- **Found during:** Task 1
- **Issue:** the name appears on the import line and on the call line, so `2` is the floor for any module that imports it by name. `grep -c "await visible_task_list"` prints `1`, and `grep -c "visible_task(" delete.py` — whose import line carries no parenthesis — prints `1` literally.
- **Decision:** kept the import-by-name convention every module in this package follows. Collapsing the two lines by importing the `access` module instead would satisfy a counter by abandoning a convention, which is the exact call 04-03 made for the same criterion on `access.py` itself.
- **Files:** `src/taskmanager/application/use_cases/tasks/create.py`

### 4. [Blocked by mypy strict] The delete happy path binds no value from `execute`

- **Found during:** Task 1
- **Issue:** `answer = await use_case.execute(...)` is `error: Function does not return a value (it only ever returns None) [func-returns-value]` under `mypy --strict`.
- **Fix:** the call is made without binding, and the "no result at all" claim is asserted from `get_type_hints(DeleteTask.execute)["return"]` instead — which is the stronger form anyway, since `None` is also what an implementation that forgot its `return` would hand back. Same resolution 04-05 reached for `DeleteTaskList`.
- **Files:** `tests/unit/application/test_delete_task.py`
- **Commit:** `f43048a`

## Threat Flags

None. No new network endpoint, auth path, file access pattern or schema change: this plan adds application-layer orchestration over ports that already existed, and every threat in the register (T-4-28 through T-4-34) is mitigated by a named test listed under Gate Results.

## Known Stubs

None. All five use cases are complete and wired to real ports; nothing returns a placeholder value.

## Handoff Notes

- **04-08 (routers):** construct these with the unit of work from `get_uow` and — for `CreateTask` and `UpdateTask` only — the `Clock` adapter. `GetTask`, `ListTasks` and `DeleteTask` take **one** argument; passing a clock is a type error, not a harmless extra.
- **04-08, again:** the router converts Pydantic's `model_fields_set` into `UNSET`. Do not pass `None` for an omitted field — `UpdateTask` would read that as D-05's explicit null and clear the description, or clear the deadline.
- **04-08:** `CreateTask` answers `TaskListNotFoundError` for an invisible parent (404 `task_list_not_found`), while the other four answer `TaskNotFoundError` (404 `task_not_found`). Both already resolve through the MRO table in `presentation/api/errors/`; nothing there needs a change.
- **04-07 (schemas):** `TaskCollectionResult` is flat — `items`, `total_tasks`, `completed_tasks`, `completion_percentage` — and `items` is a `tuple`. The response schema maps those four names directly; there is no nested `stats` object.
- **04-07, again:** the PATCH schema must not declare `status`, and `extra="forbid"` is what turns an attempt into a 422. `test_update_task_cannot_change_a_status` covers the two layers below it; the schema is the third.
- **04-09 (integration):** the filter-does-not-move-the-statistics claim is asserted here against fakes. The honest counterpart is an HTTP call against a real list with a real `COUNT(*) FILTER` aggregate behind it.
- **04-10 (statement counter):** `ListTasks` costs exactly two statements whatever the filter says, and `test_list_tasks_writes_nothing_and_closes_its_transaction` counts them at the fake level. A third statement means the counters were gathered some other way.
- **04-12 (ADRs):** two decisions are owed an entry — `CreateTask`'s list-shaped refusal as the argued exception to `access.py`'s asymmetry, and (jointly with 04-05) `updated_at` moving whenever a field is provided.

## Self-Check: PASSED

- `src/taskmanager/application/use_cases/tasks/create.py` — FOUND, contains `class CreateTask`
- `src/taskmanager/application/use_cases/tasks/get.py` — FOUND, contains `class GetTask`
- `src/taskmanager/application/use_cases/tasks/list.py` — FOUND, contains `class ListTasks`
- `src/taskmanager/application/use_cases/tasks/update.py` — FOUND, contains `class UpdateTask`
- `src/taskmanager/application/use_cases/tasks/delete.py` — FOUND, contains `class DeleteTask`
- `tests/unit/application/test_create_task.py` — FOUND, 7 tests passing
- `tests/unit/application/test_get_task.py` — FOUND, 7 tests passing
- `tests/unit/application/test_list_tasks.py` — FOUND, 9 tests passing
- `tests/unit/application/test_update_task.py` — FOUND, 15 tests passing
- `tests/unit/application/test_delete_task.py` — FOUND, 7 tests passing
- `.planning/phases/04-task-lists-tasks/evidence/04-06-fake-ordering.txt` — FOUND
- commit `f43048a` — FOUND
- commit `a9d57cf` — FOUND
- commit `e28f32d` — FOUND
