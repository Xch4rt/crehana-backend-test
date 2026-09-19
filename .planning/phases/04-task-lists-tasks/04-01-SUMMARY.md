---
phase: 04-task-lists-tasks
plan: 01
subsystem: domain
tags: [dataclasses, enum, mypy-strict, pydantic-settings, pytest, patch-semantics]

# Dependency graph
requires:
  - phase: 02-domain-error-contract
    provides: "Task/TaskList entities, domain/validation.py guards, the frozen slotted DTO convention"
  - phase: 03-persistence-runnable-stack
    provides: "Settings with TEST_DATABASE_URL, the .venv gate set, a reachable taskmanager_test database"
provides:
  - "A hermetic tests/unit/test_settings.py::test_get_settings_is_cached, so `make test` is green on a developer host that has a real .env"
  - "TaskList.describe(description, *, now)"
  - "Task.describe(description, *, now) and Task.reprioritise(priority, *, now)"
  - "Task.DEFAULT_PRIORITY as the single copy of TASK-01's `medium`, read by Task.create"
  - "src/taskmanager/application/dto/unset.py: the stdlib-only, mypy-narrowable PATCH sentinel"
affects: [04-04, 04-05, 04-06, 04-07, 04-08, 04-12]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Single-member enum sentinel for `field not provided`, narrowed by `is not UNSET`"
    - "monkeypatch.chdir(tmp_path) to neutralise a relative pydantic-settings env_file in a unit test"

key-files:
  created:
    - src/taskmanager/application/dto/unset.py
    - tests/unit/application/test_unset.py
  modified:
    - tests/unit/test_settings.py
    - AI_WORKFLOW.md
    - src/taskmanager/domain/entities/task.py
    - src/taskmanager/domain/entities/task_list.py
    - tests/unit/domain/test_task.py
    - tests/unit/domain/test_task_list.py

key-decisions:
  - "The settings test's isolation was fixed, not its assertion: monkeypatch.chdir(tmp_path) before cache_clear(), with all three original assertions untouched"
  - "Task.reprioritise carries no value guard - TaskPriority is a StrEnum and the boundary refuses non-members, so a guard would be an unreachable branch the 100% coverage norm could not cover without a pragma"
  - "Unset is a single-member enum; None, object() and a Patch[T] wrapper are each rejected in the module docstring with the reason"
  - "The sentinel stops at the application boundary: the measured /openapi.json leak and the split error loc are recorded in the docstring so a later plan cannot reintroduce it"
  - "The narrowing claim was falsified before being trusted: deleting the guard made mypy report `Incompatible return value type (got \"str | Unset\", expected \"str\")`"
  - "Requirement ticks LIST-04/TASK-01/TASK-03/TASK-08 deliberately NOT taken - 04-12 is the last claimant of all four and none has an HTTP endpoint yet"

patterns-established:
  - "PATCH sentinel: `class Unset(Enum): TOKEN = \"unset\"` + `UNSET: Final = Unset.TOKEN`, imported by application commands only"
  - "Every new entity mutator is keyword-only on `now`, validates before assigning, and stamps updated_at from the validated moment; its negative test asserts the old value AND the old timestamp"

requirements-completed: []

# Metrics
duration: 10min
completed: 2026-09-18
---

# Phase 4 Plan 01: Phase 4 Preconditions Summary

**The commit gate is honest again, the four PATCH mutators the rest of Phase 4 calls exist with
the project's validate-then-assign shape, and `medium` and "field not provided" each have exactly
one spelling.**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-09-19T04:52Z
- **Completed:** 2026-09-19T05:02Z
- **Tasks:** 3 of 3
- **Files modified:** 8 (2 created, 6 modified)

## Accomplishments

- `tests/unit/test_settings.py::test_get_settings_is_cached` had been red on the developer host
  since plan 03-03 added `TEST_DATABASE_URL` to `.env`. It is now hermetic, and the suite went
  from `1 failed, 292 passed` to `310 passed` at 100.00% coverage. Every Phase 4 commit from here
  is gated by a `make test` whose verdict does not depend on an untracked file.
- `TaskList.describe`, `Task.describe` and `Task.reprioritise` landed, each with a negative test
  that asserts the aggregate is byte-identical after a refused call (both the old value and the
  old `updated_at`), which is the only assertion shape that can observe a half-applied mutation.
- `Task.DEFAULT_PRIORITY` is the one copy of TASK-01's `medium`; `grep -c "TaskPriority.MEDIUM"`
  over the entity module prints `1`, and a test binds `Task.create`'s default to the ClassVar so
  the schema default plan 04-07 imports cannot drift from the entity's.
- `application/dto/unset.py` gives the PATCH commands a marker that mypy narrows, imports only
  `enum` and `typing.Final`, and records in prose why it is neither `None`, nor `object()`, nor a
  Pydantic field.

## Task Commits

1. **Task 1: Make the settings cache test hermetic and record the incident** - `5bf365d` (fix)
2. **Task 2: The four domain mutators the PATCH endpoints require** - `bc48745` (feat)
3. **Task 3: The typed Unset sentinel for PATCH commands** - `47f53e8` (feat)

## Files Created/Modified

- `tests/unit/test_settings.py` - `test_get_settings_is_cached` gains `tmp_path` and
  `monkeypatch.chdir(tmp_path)`; the comment block now names the relative `env_file` as the reason.
- `AI_WORKFLOW.md` - one dated incident entry: the gate was red for two phases, found by the
  Phase 4 research baseline rather than by CI, and fixed by changing isolation not assertion.
- `src/taskmanager/domain/entities/task_list.py` - `describe`; the class docstring now names its
  two mutators instead of announcing that Phase 4 will add them.
- `src/taskmanager/domain/entities/task.py` - `DEFAULT_PRIORITY`, `describe`, `reprioritise`;
  `create`'s `priority` default reads the ClassVar; the class docstring lists the five mutators and
  says why `status` has no setter beyond `change_status`.
- `tests/unit/domain/test_task_list.py` - five `describe` cases (set, null, blank, over-length,
  naive `now`).
- `tests/unit/domain/test_task.py` - the same five, plus two `reprioritise` cases and the
  `DEFAULT_PRIORITY`-is-what-`create`-applies test.
- `src/taskmanager/application/dto/unset.py` - **created.** The sentinel plus the rejected-shapes
  docstring.
- `tests/unit/application/test_unset.py` - **created.** Four tests, including a module-level helper
  typed `str | Unset -> str` whose body type-checks only because of the guard.

## Decisions Made

- **The settings test's isolation moved, its assertions did not.** Each of the easy alternatives
  destroys the claim the test exists to make: `_env_file=None` on the `get_settings()` path stops
  testing the function as production calls it, `skipif` hides the failure on the only machine that
  reproduces it, and deleting the test drops the "the cached instance carries the current
  environment" guarantee.
- **`Task.reprioritise` has no value guard.** `TaskPriority` is a `StrEnum`, the parameter's own
  type is the constraint, and the enum-typed body field at the boundary (04-07) refuses anything
  else before a command exists. A defensive check would be a branch no test could reach, and this
  project's coverage rules forbid excusing it with a pragma.
- **The sentinel is confined to `application/dto/`.** 04-RESEARCH measured the alternative: it
  publishes a `_Unset` component into `/openapi.json` and splits the explicit-null refusal into
  `body.title.str` and `body.title.enum[_Unset]`. That measurement is now in the module docstring,
  where a later plan will read it.
- **The narrowing was falsified, not asserted.** The guard was deleted and `mypy src tests`
  reported `tests/unit/application/test_unset.py:16: error: Incompatible return value type (got
  "str | Unset", expected "str") [return-value]`, then the guard was restored and the run returned
  to `Success: no issues found in 101 source files`. That is the evidence behind the docstring's
  claim that a forgotten guard is a type error rather than a runtime surprise.
- **No requirement ticks taken.** 04-12 is the last claimant of LIST-04, TASK-01, TASK-03 and
  TASK-08, and none of the four has an HTTP endpoint yet — the same call Phase 3 made ten times in
  a row.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] The plan's acceptance criterion miscounts the settings tests**

- **Found during:** Task 1
- **Issue:** The plan asserts `.venv/bin/pytest tests/unit/test_settings.py -q --no-cov` "exits 0
  with 8 tests passing", and describes "the other seven". The module contains seven tests in total,
  so the baseline was `1 failed, 6 passed` and the fixed run is `7 passed`. Reaching 8 would have
  required inventing a test the plan never specified, purely to satisfy a number.
- **Fix:** The criterion is read as "exits 0 with every test in the file passing", which it does.
  No test was added or removed. The count is recorded here rather than silently reinterpreted.
- **Files modified:** none beyond the task's own
- **Verification:** `.venv/bin/pytest tests/unit/test_settings.py -q --no-cov` → `7 passed`
- **Committed in:** `5bf365d` (behaviour), documented here

**2. [Rule 2 - Missing critical functionality] The requirement ticks the frontmatter claims were not taken**

- **Found during:** state update
- **Issue:** The plan's frontmatter lists `requirements: [LIST-04, TASK-01, TASK-03, TASK-08]`.
  Marking them complete here would be false: LIST-04 and TASK-03 are PATCH *endpoints*, TASK-01 is
  a create endpoint, and TASK-08 is the set of business validations proven over HTTP. This plan
  ships only the domain-side preconditions for them.
- **Fix:** `requirements-completed: []`. 04-12 is the last claimant of all four and will tick them
  against named tests, per the convention Phase 3 applied ten consecutive times.
- **Files modified:** `.planning/REQUIREMENTS.md` deliberately left unchanged
- **Verification:** `grep -m1 '^requirements:' .planning/phases/04-task-lists-tasks/04-12-PLAN.md`
  lists all four
- **Committed in:** n/a (an omission, recorded here)

---

**Total deviations:** 2 auto-fixed (1 × Rule 1, 1 × Rule 2)
**Impact on plan:** None on scope. Both are corrections to planning arithmetic and to a premature
completion claim; every artifact and behaviour the plan specified was delivered.

## Issues Encountered

- The first draft of a test docstring opened with `""""" and null ...`, which the tokenizer accepts
  (the two extra quotes become content) but which reads as a syntax error to anything human. It was
  rewritten before the gates ran.

## Verification

| Gate | Command | Result |
|------|---------|--------|
| Lint | `make lint` | black 101 files unchanged, isort clean, flake8 clean |
| Types | `make typecheck` | `Success: no issues found in 101 source files` |
| Architecture | `make arch` | `Contracts: 3 kept, 0 broken.` |
| Tests | `make test` | `310 passed`, `Required test coverage of 75% reached. Total coverage: 100.00%` |
| No pragma | `grep -rn "pragma: no cover" src/taskmanager/` | 0 matches |
| Entity coverage | `pytest tests/unit/domain --cov=taskmanager.domain.entities` | `task.py` 100%, `task_list.py` 100%, no missing lines |
| Sentinel coverage | `pytest tests/unit/application/test_unset.py --cov=...dto.unset` | 100%, no missing lines |
| Single `medium` | `grep -c "TaskPriority.MEDIUM" src/taskmanager/domain/entities/task.py` | `1` |
| Sentinel imports | `grep -cE "^(import\|from) " .../dto/unset.py` | `2`, both stdlib |

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Wave 1's sibling (04-02) and every downstream Phase 4 plan can now proceed:

- `make test` is a meaningful gate on the developer host. A red run from here is a real regression.
- The PATCH use cases (04-04/04-05/04-06) have `Task.describe`, `Task.reprioritise`,
  `TaskList.describe` and `Task.reschedule` to call, and `UNSET` to build their commands from.
- 04-07's Pydantic schema imports `Task.DEFAULT_PRIORITY` for its `priority` field default rather
  than spelling `medium` again.
- 04-12 owns the requirement ticks for LIST-04, TASK-01, TASK-03 and TASK-08, and the
  `AI_WORKFLOW.md` entry added here is one of the phase's incident entries it will build on.

**Concern for 04-02:** `make arch` currently reports `3 kept`. 04-02 raises that to 4, so any later
plan asserting the kept count rather than `0 broken` will be asserting an order-dependent number.

## Self-Check: PASSED

- `src/taskmanager/application/dto/unset.py` — FOUND
- `tests/unit/application/test_unset.py` — FOUND
- `src/taskmanager/domain/entities/task.py` — FOUND (`DEFAULT_PRIORITY`, `describe`, `reprioritise`)
- `src/taskmanager/domain/entities/task_list.py` — FOUND (`describe`)
- commit `5bf365d` — FOUND
- commit `bc48745` — FOUND
- commit `47f53e8` — FOUND

---
*Phase: 04-task-lists-tasks*
*Completed: 2026-09-18*
