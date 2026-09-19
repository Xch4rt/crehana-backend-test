---
phase: 04-task-lists-tasks
plan: 04
subsystem: application
tags: [dto, adr-020, patch-semantics, sentinel, completion-stats, immutability]

# Dependency graph
requires:
  - phase: 04-task-lists-tasks
    provides: "04-01's Unset sentinel (dto/unset.py) and Task.DEFAULT_PRIORITY"
  - phase: 04-task-lists-tasks
    provides: "04-03's ChangeTaskStatusCommand.task_list_id, kept byte-for-byte"
  - phase: 02-domain-error-contract
    provides: "TaskResult, the TaskList/Task entities and CompletionStats"
provides:
  - "The ten Phase 4 commands, frozen, slotted and actor_id-first"
  - "UpdateTaskListCommand / UpdateTaskCommand: omitted vs explicit-null at the type level (D-05)"
  - "TaskListResult.from_entity(task_list, stats) — the one task-list answer shape (D-10)"
  - "TaskCollectionResult.from_parts(tasks, stats) — the tasks envelope (D-09)"
affects: [04-05, 04-06, 04-07, 04-08, 04-09, 04-10, 04-11, 04-12]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Every patchable command field is `X | Unset = UNSET`; plain `X | None` is reserved for filters, where absent and null are the same request"
    - "A result DTO names every field in from_entity; a splat or asdict would publish an entity field by accretion"
    - "Collection DTOs hold a tuple, never a list, because a list stays editable through a frozen wrapper"
    - "Per-command conventions (actor_id first, immutability, no __dict__) asserted by one parametrized test over a table of all ten, so a new command joins the gate by joining the table"

key-files:
  created:
    - tests/unit/application/test_dtos.py
  modified:
    - src/taskmanager/application/dto/commands.py
    - src/taskmanager/application/dto/results.py

key-decisions:
  - "ListTasksCommand's status/priority filters are plain `X | None = None`, NOT the sentinel: an absent filter and a null filter are the same request, so there is only one meaning to express and a second marker would be ceremony the use case has to unwrap"
  - "TaskCollectionResult carries the three statistics FLAT (total_tasks, completed_tasks, completion_percentage) rather than 04-RESEARCH's `stats: CompletionStats` field — the plan's interface block and its acceptance criteria both read `result.completion_percentage`, and a nested value object would make the presentation schema reach through a domain type"
  - "from_parts(tasks, stats) is where the `tuple(TaskResult.from_entity(...))` conversion lives, so the tuple-not-list rule cannot be honoured in one use case and forgotten in the next"
  - "ChangeTaskStatusCommand moved to the end of the tasks banner, its body unchanged, so the file reads task-lists-then-tasks and the status verb sits after the CRUD five it is deliberately not part of (D-08)"
  - "The ten per-command immutability / undeclared-attribute / field-order tests are one parametrized test each with per-class ids rather than thirty hand-written functions — the convention is enforced for every command in the table, including ones a later plan adds"
  - "UpdateTaskCommand's absence test asserts four names, not one: status (D-08) plus owner_id, assignee_id and completed_at, which are the same mass-assignment risk (T-4-17)"

patterns-established:
  - "A table-driven conventions gate: COMMAND_CASES lists every command once and three parametrized tests read the convention off `dataclasses.fields`"
  - "A result's field set is asserted as a whole, so an added entity field fails the DTO test before it can reach a response"

requirements-completed: []

# Metrics
duration: 14min
completed: 2026-09-18
---

# Phase 4 Plan 04: the DTO layer Summary

**The whole Phase 4 DTO surface now exists in two files: eleven frozen, slotted, `actor_id`-first commands in which "omitted" and "set to null" are different types rather than the same `None`, and two results that carry the whole-list completion statistics onto every answer the phase gives.**

## Performance

- **Duration:** ~14 min
- **Tasks:** 2 of 2, one commit each
- **Files:** 1 created, 2 modified

## Accomplishments

- `commands.py` holds the ten new commands under two banners — task lists, then tasks — each group ordered create / get / list / update / delete. Every one is `@dataclass(frozen=True, slots=True)` and names `actor_id` first, which is now a gate: a parametrized test reads the order off `dataclasses.fields` for all ten.
- The two update commands type every patchable field as `X | Unset = UNSET`. `None` stays available as a *value*, so `description=None` ("clear it") and an omitted `description` ("leave it") are two distinguishable states in one object — D-05's whole distinction, proven at runtime here and by mypy narrowing at every future call site.
- `UpdateTaskCommand` declares no `status`, and the test that says so also refuses `owner_id`, `assignee_id` and `completed_at`. TASK-03 / D-08 is now proven by absence at the application boundary, not only by the PATCH schema's `extra="forbid"` that plan 04-07 will add.
- `CreateTaskCommand.priority` is required with no default, so `Task.DEFAULT_PRIORITY` remains the single copy of TASK-01's `medium` (04-RESEARCH Pitfall 6).
- `TaskListResult.from_entity(task_list, stats)` is the one task-list shape for the collection, the single GET, the POST and the PATCH alike (D-10). It reads `stats.percentage` as the **property** it is — 04-CONTEXT.md spells it `percentage()`, which would be a `TypeError`, and a comment in the method says so.
- `TaskCollectionResult.from_parts(tasks, stats)` pairs the filtered items with the statistics of the whole list (D-09). One test hands in a single item beside statistics covering four tasks, so an implementation that recomputed the counters from `items` fails rather than looking plausible.
- No wrapper DTO for a collection of task lists: `ListTaskLists` will return `tuple[TaskListResult, ...]`, and `results.py`'s module docstring states why (04-RESEARCH Open Question 2, resolved to the tuple).

## Task Commits

1. **Task 1: the ten Phase 4 commands** — `4c5ffa7` (feat)
2. **Task 2: `TaskListResult`, `TaskCollectionResult` and their explicit mappings** — `85fb344` (feat)

**Plan metadata:** see the final `docs(04-04)` commit.

## Files Created/Modified

- `src/taskmanager/application/dto/commands.py` — 205 lines, 36 statements, 100% covered. Eleven commands; the module docstring gained the paragraph naming the two rejected `Unset` alternatives (`fields_set: frozenset[str]`, a per-field `Patch[T]` wrapper) and pointing at `dto/unset.py` rather than restating its argument.
- `src/taskmanager/application/dto/results.py` — 167 lines, 24 statements, 100% covered. `TaskListResult` and `TaskCollectionResult` added; `TaskResult` untouched; the module docstring now carries the no-wrapper-for-a-list-collection decision.
- `tests/unit/application/test_dtos.py` — 47 tests. Thirty of them are the three parametrized conventions gates over all ten commands; the rest are the five sentinel/PATCH-semantics tests and the ten result tests (immutability, undeclared attribute, full field set, `0.0` on empty, `66.67` on 2 of 3, tuple-ness and input order, whole-list-not-filtered statistics).

## Gate Results

| Gate | Result |
|------|--------|
| `make lint` | green (black, isort, flake8) |
| `make typecheck` | green — `Success: no issues found in 104 source files` |
| `make arch` | `Contracts: 4 kept, 0 broken.` |
| `make test` | `380 passed`, **Total coverage: 100.00%** |
| `tests/unit/application/test_dtos.py` | `47 passed` (the plan asks for at least 30) |
| `taskmanager.application.dto` coverage | commands 36, results 24, unset 5 statements — **0 missing lines** |
| eleven commands, `actor_id` first | asserted |
| `grep -c "pydantic" .../dto/commands.py` | `0` |
| `grep -c "pydantic" .../dto/results.py` | `0` |
| `grep -rn "pydantic" src/taskmanager/application/` | no matches |
| `grep -c "percentage()" .../dto/results.py` | `0` |

## Deviations from Plan

### 1. [Judgement recorded] `TaskCollectionResult` carries the statistics flat, against 04-RESEARCH's example

- **Found during:** Task 2.
- **Issue:** 04-RESEARCH's "task-listing use case" example builds `TaskCollectionResult(items=..., stats=stats)` — a nested `CompletionStats` field. The plan's `<interfaces>` block and two of its acceptance criteria instead read `result.completion_percentage` directly.
- **Fix:** The plan's shape was implemented. Flat fields keep the response schema mapping one-to-one with the DTO and stop presentation from reaching through a domain value object to reach a number. `from_parts` is where the unpacking happens, exactly once.
- **Note for 04-06:** build the envelope with `TaskCollectionResult.from_parts(tasks, stats)`, not the RESEARCH constructor call — that spelling will not type-check.
- **Commit:** `85fb344`

### 2. [Minor] `ChangeTaskStatusCommand` moved within the file

- **Found during:** Task 1.
- **Issue:** The plan asks for "a comment banner per aggregate", and 04-03's command sat above where the task-lists group belongs.
- **Fix:** The class moved to the end of the tasks banner with its docstring and field list unchanged — a pure reordering, verifiable with `git diff`. Nothing 04-03 decided was reverted.
- **Commit:** `4c5ffa7`

### 3. [Minor] The thirty per-command tests are three parametrized tests, not thirty functions

- **Found during:** Task 1.
- **Issue:** The plan asks for a `FrozenInstanceError` test, an undeclared-attribute test and a field-order check "for each of the ten commands".
- **Fix:** `COMMAND_CASES` lists each command once and three parametrized tests consume it, producing thirty test ids named after the classes (`test_a_command_names_the_actor_first[UpdateTaskCommand]`). Same count, same granularity in the report, and a command added later joins all three gates by joining one table instead of by someone remembering to write three more functions.
- **Commit:** `4c5ffa7`

### 4. [Judgement recorded] `ListTasksCommand` filters stay plain optionals

- **Found during:** Task 1.
- **Issue:** The sentinel could have been used for TASK-06's `status` and `priority` filters for uniformity.
- **Fix:** It is not, and the docstring says why: for a filter, "absent" and "null" are the same request, so there is only one meaning to express. This matches the plan's `<interfaces>` block exactly; it is recorded because the asymmetry with the update commands is the first thing a reader will question.
- **Commit:** `4c5ffa7`

## Requirements

`ARC-05` is **not** ticked. Plans 04-07, 04-08 and 04-12 also claim it, and under this project's last-claimant convention 04-12 takes it: this plan ships the frozen-dataclass half of the requirement, while the Pydantic-at-every-HTTP-boundary half does not exist until the schemas and routers do.

## Handoff Notes

- **04-05 / 04-06 / 04-09 / 04-10 / 04-11 (use cases):** every command is already written; do not add fields to them without a test in `test_dtos.py`. A use case reads a patchable field as `if command.field is not UNSET:` — inside that guard mypy narrows `str | Unset` to `str`, and omitting the guard is an `arg-type` error at the entity call, not a runtime surprise.
- **The `None` legs are live:** `if command.description is not UNSET: task_list.describe(command.description, now=now)` correctly passes `None` through to clear the field. Do not add `and command.description is not None` — that would silently drop D-05's clear-it case.
- **D-07:** `due_date` must only be re-checked when it was sent. The sentinel is what makes that possible; an implementation that called `reschedule` unconditionally would refuse every PATCH on an already-overdue task.
- **04-05 (list use cases):** `TaskListResult.from_entity(task_list, stats)` needs a `CompletionStats` for *every* answer, including the one right after a create — an empty list is `CompletionStats(total=0, completed=0)`, which reports `0.0`, never `None`.
- **04-06 (task listing):** call `completion_stats(task_list_id)` with no filter arguments. The DTO cannot fix a statistic that was computed over the filtered view, and `test_a_task_collection_reports_the_whole_list_never_the_filtered_view` only proves the envelope keeps what it is given.
- **04-07 (schemas):** the sentinel never crosses into Pydantic. The schema declares `X | None = None`, and the router converts `model_fields_set` into `UNSET`; `dto/unset.py`'s docstring records the measured cost of the alternative.
- **04-08 (routers):** `actor_id` is filled from the authenticated caller, never from a body or a path segment. It is the first field of all eleven commands so that this is impossible to forget by accident.

## Self-Check: PASSED

- `src/taskmanager/application/dto/commands.py` — FOUND, contains `class UpdateTaskCommand`
- `src/taskmanager/application/dto/results.py` — FOUND, contains `class TaskListResult` and `class TaskCollectionResult`
- `tests/unit/application/test_dtos.py` — FOUND, 47 tests passing
- commit `4c5ffa7` — FOUND
- commit `85fb344` — FOUND
