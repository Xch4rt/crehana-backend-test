---
phase: 04-task-lists-tasks
plan: 03
subsystem: application
tags: [adr-008, authorization, idor, dto, use-case, tdd, coverage]

# Dependency graph
requires:
  - phase: 02-domain-error-contract
    provides: "ChangeTaskStatus as the reference use case, the DomainError hierarchy, the eight Protocol ports and the in-memory fakes"
  - phase: 04-task-lists-tasks
    provides: "04-02's FakeUnitOfWork wiring (unchanged here, but the fakes these tests drive)"
provides:
  - "taskmanager.application.use_cases.access: visible_task_list and visible_task, the one copy of ADR-008's load-and-authorize rule"
  - "ChangeTaskStatusCommand.task_list_id as the second field, so D-14's comparison can exist at all"
  - "The D-14 refusal on the status use case, proved identical to the absent-task refusal"
affects: [04-04, 04-05, 04-06, 04-07, 04-08, 04-09, 04-10, 04-11, 04-12]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A shared guard as module-level coroutine functions taking an already-entered UnitOfWork, never a base class or mixin"
    - "Indistinguishability asserted by producing BOTH refusals and comparing type, code and details"

key-files:
  created:
    - src/taskmanager/application/use_cases/access.py
    - tests/unit/application/test_access.py
    - .planning/phases/04-task-lists-tasks/evidence/04-03-access-red.txt
  modified:
    - src/taskmanager/application/dto/commands.py
    - src/taskmanager/application/use_cases/tasks/change_task_status.py
    - tests/unit/application/test_change_task_status.py

key-decisions:
  - "The assignee clause of the old `_may_change_status` is DROPPED, and the ASGN-02 test that asserted it is inverted to assert the Phase 4 scope instead - the plan mandates the drop but says nothing about the test it breaks; keeping the clause would have shipped a branch no Phase 4 request can reach, since no endpoint in this phase sets assignee_id, and the coverage gate is met by writing tests rather than by a pragma"
  - "The plan's `grep -c TaskListNotFoundError access.py == 1` is met in substance, not literally: the import line and the single raise are two lines, so the count is 2 and the strict form `grep -c 'raise TaskListNotFoundError'` is 1; the alternative - importing the exceptions module to collapse them onto one line - would have gamed a counter by abandoning the project's import-by-name convention"
  - "`grep -c AuthorizationError access.py == 0` IS met literally, prose included: the module argues the 403 question at length without ever spelling the class, and says so, following the Makefile's own convention of describing a forbidden form without writing it"
  - "The guards are module-level functions, not a GuardedUseCase mixin: an override is invisible at the call site, while a missing `await visible_task(...)` is an absent line in a diff"
  - "`visible_task` compares the task's parent BEFORE loading the addressed list, so a wrong-list request cannot reveal whether that list exists"
  - "A ninth test asserts both guards leave commits and rollbacks at zero from inside the block - the transaction boundary stays with the use case (D-17, ARC-08)"

patterns-established:
  - "Two-refusal comparison: an indistinguishability claim is tested by running both legs and asserting type, code and details match, never by inspecting one error"
  - "A dropped capability is inverted into a test naming the phase that restores it, rather than deleted"

requirements-completed: []

# Metrics
duration: 12min
completed: 2026-09-18
---

# Phase 4 Plan 03: the shared ADR-008 guard and D-14 Summary

**ADR-008's "invisible reads as absent" rule now exists exactly once, as `visible_task_list` and `visible_task`, and the reference use case can finally express D-14: a status change addressed under the wrong list is refused with an error indistinguishable — class, code and `details` — from the one an absent task gets.**

## Performance

- **Duration:** ~12 min
- **Tasks:** 2 of 2, one commit each
- **Files:** 3 created (one of them evidence), 3 modified

## Accomplishments

- `src/taskmanager/application/use_cases/access.py` holds the load-and-authorize block ten sibling use cases were about to repeat. Its docstring argues the three things a reader will question: why a task route raises the task-shaped not-found error even when the *list* is the problem, why nothing in the module can answer 403 in Phase 4, and why this is a module of functions rather than a mixin.
- `visible_task` compares `task.task_list_id` against the addressed list **first**, before the list is loaded at all — so the answer to a wrong-list request cannot depend on whether that list exists.
- `ChangeTaskStatusCommand` gained `task_list_id` as its second field. Before this, D-11's nested route had a parent segment the use case could not see, so the wrong-list request succeeded.
- `ChangeTaskStatus.execute` shrank to a single `visible_task` call plus the entity invocation, the update and the commit. `change_task_status.py` is now 16 statements, all covered.
- Two of the new tests, and one of the D-14 tests on the use case, assert indistinguishability by running **both** refusals and comparing them. A single-error assertion would pass against an implementation that leaked existence through a different code.

## Task Commits

1. **Task 1: the shared guard and its nine two-actor proofs** — `c04d99d` (feat)
2. **Task 2: `task_list_id` on the command, the use case delegating to `visible_task`, three new tests** — `45d0aae` (feat)

**Plan metadata:** see the final `docs(04-03)` commit.

## Files Created/Modified

- `src/taskmanager/application/use_cases/access.py` — 18 statements, 6 branches, 100% covered. Two coroutine functions, four refusal legs, one raise of the list-shaped error and none of the authorization one.
- `tests/unit/application/test_access.py` — 9 tests: two success legs, six refusal legs (three of them comparative), and one asserting neither guard ends the transaction it was handed.
- `src/taskmanager/application/dto/commands.py` — `task_list_id: UUID` as the second field, with the D-11/D-14 reason on the class docstring.
- `src/taskmanager/application/use_cases/tasks/change_task_status.py` — `_may_change_status` and the inline guard gone; the module docstring keeps the no-403 argument, records where the block moved and why, and states the assignee clause's removal as a temporary Phase 4 scoping rather than a deletion.
- `tests/unit/application/test_change_task_status.py` — `_command` gained a `task_list_id` keyword (defaulted, so the seven existing call sites still describe the same request); three new tests; the immutability test extended to the new field; a field-order test binding the convention.
- `.planning/phases/04-task-lists-tasks/evidence/04-03-access-red.txt` — the TDD RED capture for Task 1.

## Gate Results

| Gate | Result |
|------|--------|
| `make lint` | green (black, isort, flake8) |
| `make typecheck` | green — `Success: no issues found in 103 source files` |
| `make arch` | `Contracts: 4 kept, 0 broken.` |
| `make test` | `333 passed`, **Total coverage: 100.00%** |
| `access.py` coverage | 18 statements, 6 branches, 0 missed — **100%** |
| `change_task_status.py` coverage | 16 statements, 0 missed — **100%** |
| `grep -c AuthorizationError access.py` | `0` |
| `grep -c "commit()" access.py` | `0` |
| `grep -c "raise TaskListNotFoundError" access.py` | `1` |

## Deviations from Plan

### 1. [Rule 3 — Blocking] The ASGN-02 test had to be inverted, not merely updated

- **Found during:** Task 2.
- **Issue:** The plan instructs that `_may_change_status`'s `task.assignee_id == actor_id` clause be dropped, and lists the test changes as "add `task_list_id` to `_command`" plus two new tests. But `test_change_task_status_allows_the_assignee_who_does_not_own_the_list` asserts exactly the behaviour being dropped, so the tree could not be green either way: keep the clause and `visible_task` is not used; drop it and that test fails.
- **Fix:** The test became `test_change_task_status_hides_the_task_from_its_assignee_for_now`, asserting the Phase 4 answer (`TaskNotFoundError`, `commits == 0`, `rollbacks == 1`) with a docstring that states what it used to assert, why the inversion happened, and that Phase 5 turns it back. The same decision is recorded in `change_task_status.py`'s module docstring, as the plan asked.
- **Commit:** `45d0aae`

### 2. [Rule 4-adjacent — judgement recorded] One acceptance criterion met in substance

- **Found during:** Task 1, running the criteria.
- **Issue:** `grep -c "TaskListNotFoundError" src/taskmanager/application/use_cases/access.py` is required to print `1`. `grep -c` counts *lines*, and the class must appear on the import line as well as the raise line, so the honest minimum under this project's import-by-name convention is `2`.
- **Fix:** The prose mention was removed so the count is exactly the import plus the one raise, and the stricter, meaningful form is asserted instead: `grep -c "raise TaskListNotFoundError"` prints `1`, which is the threat register's actual intent (T-4-13 — "it is the `visible_task_list` leg"). The rejected alternative — `from taskmanager.domain import exceptions` so the import and the raise collapse onto one grep-visible line — would have satisfied the literal count by abandoning the import style every other module in the project uses, which is gaming a counter rather than meeting a requirement.
- **Commit:** `c04d99d`
- **Note:** The companion criterion `grep -c "AuthorizationError" == 0` **is** met literally, including in prose. The module discusses the 403 question at length without naming the class, and says in the docstring that it is doing so deliberately.

### 3. [Minor] A TDD RED capture, not listed in `files_modified`

The plan's tasks are `type="auto"` and not marked `tdd="true"`, but `test_access.py` was written and run before `access.py` existed, and the failing collection was captured to `evidence/04-03-access-red.txt`. Cheap, and it matches the precedent 02-01 and 04-02 set: with a `mypy --strict` pre-commit hook and `--no-verify` forbidden, an evidence file is the only red this project can record.

## Requirements

`TASK-02` and `TASK-05` are **not** ticked. Plan 04-12 is the last claimant of both, and this plan ships the application-layer rule with no endpoint above it — the eleventh consecutive plan to make that call.

## Handoff Notes

- **Every remaining Phase 4 use-case plan** should call `visible_task_list(self._uow, command.task_list_id, command.actor_id)` or `visible_task(...)` as its first statement inside `async with self._uow:`. Do **not** re-implement the check; `grep -rn "visible_task" src/` is the audit an evaluator can run.
- The guards take an **already-entered** unit of work. They neither open the block nor commit, so the calling use case still owns the transaction boundary.
- `visible_task_list` returns the entity, so a use case that needs the list (rename, describe, delete, the single-list GET) has it without a second `get`.
- **04-07 / 04-11** (the status endpoint) must pass the path's `list_id` into `ChangeTaskStatusCommand.task_list_id`. A router that fills it from the task instead would restore exactly the defect this plan closed, and the D-14 unit tests would still pass.
- **Phase 5** restores the assignee leg inside `access.py`, not inside any single use case, and adds the first 403 branch. Two tests name it by phase: `test_change_task_status_hides_the_task_from_its_assignee_for_now`, and the `access.py` docstring paragraph on why nothing here can answer 403.

## Self-Check: PASSED

- `src/taskmanager/application/use_cases/access.py` — FOUND, contains `def visible_task`
- `tests/unit/application/test_access.py` — FOUND
- `.planning/phases/04-task-lists-tasks/evidence/04-03-access-red.txt` — FOUND
- `src/taskmanager/application/dto/commands.py` contains `task_list_id` — FOUND
- `change_task_status.py` contains `visible_task` — FOUND
- commit `c04d99d` — FOUND
- commit `45d0aae` — FOUND
