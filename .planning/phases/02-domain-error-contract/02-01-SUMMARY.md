---
phase: 02-domain-error-contract
plan: 01
subsystem: domain
tags: [python, stdlib, enum, strenum, dataclass, value-objects, pytest, mypy]

# Dependency graph
requires:
  - phase: 01-foundation-quality-gates
    provides: src layout, editable install, pytest/mypy/flake8/black/isort gates, import-linter contracts, coverage gate
provides:
  - TaskStatus StrEnum (pending, in_progress, completed) serializing to lowercase strings
  - ALLOWED_TRANSITIONS, the exhaustive D-01 transition table
  - TaskPriority StrEnum (low, medium, high)
  - CompletionStats frozen slotted value object with ADR-009 percentage semantics
  - tests/unit/domain package with 21 specification tests at 100% coverage
affects: [02-02-exceptions, 02-03-entities, 02-05-ports, 03-persistence, 04-crud-endpoints]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "enum.StrEnum for every domain vocabulary type, never class X(str, Enum)"
    - "Module-level Final[...] constant as the single source of truth, placed right after the class it describes"
    - "Value objects are @dataclass(frozen=True, slots=True); entities will be the only mutable dataclasses"
    - "Tests assert portable behaviour, not interpreter-specific exception types, when host and target runtime disagree"

key-files:
  created:
    - src/taskmanager/domain/value_objects/__init__.py
    - src/taskmanager/domain/value_objects/task_status.py
    - src/taskmanager/domain/value_objects/task_priority.py
    - src/taskmanager/domain/value_objects/completion.py
    - tests/unit/domain/__init__.py
    - tests/unit/domain/test_task_status.py
    - tests/unit/domain/test_task_priority.py
    - tests/unit/domain/test_completion.py
    - .planning/phases/02-domain-error-contract/evidence/02-01-tdd-red.txt
    - .planning/phases/02-domain-error-contract/evidence/02-01-frozen-slots-setattr.txt
  modified: []

key-decisions:
  - "TDD RED was observed by execution and captured as evidence rather than committed as a separate test() commit: a RED commit cannot pass the mypy hook, and CLAUDE.md forbids --no-verify"
  - "The frozen+slots setattr test asserts the portable claim (assignment refused, no __dict__, exact __slots__) because CPython 3.13 raises FrozenInstanceError and 3.14.3 raises TypeError for a non-field name"
  - "No can_transition() helper beside the enum: the state machine is a Task invariant and belongs to the entity (plan 02-03), a second copy would be the duplicated-limit defect"
  - "CompletionStats carries no __post_init__ validation: the invariant is guaranteed by Phase 3's single COUNT(*) FILTER aggregate, and a guard would couple a value object to the error hierarchy"

patterns-established:
  - "StrEnum vocabulary types: json.dumps and f-strings emit the bare lowercase value with no custom encoder"
  - "Exhaustive lookup tables over every enum member, so a future member fails loudly at the lookup instead of defaulting to permissive"
  - "Docstring voice carried from Phase 1: summary line, then a paragraph naming the rejected alternative and its concrete failure"
  - "setattr with a module-level name constant in negative tests, which keeps mypy strict quiet without a type: ignore and dodges flake8-bugbear B010"

requirements-completed: [ARC-02]

# Metrics
duration: 10min
completed: 2026-09-18
---

# Phase 2 Plan 01: Domain Value Objects Summary

**`TaskStatus` / `TaskPriority` as stdlib `StrEnum`s, the exhaustive `ALLOWED_TRANSITIONS` table that owns D-01, and the frozen `CompletionStats` value object carrying ADR-009's `0.0`-for-empty percentage - 21 tests, 100% coverage, full gate green on both Python 3.14.3 and 3.13.**

## Performance

- **Duration:** 10 min
- **Started:** 2026-09-18T05:37:20Z
- **Completed:** 2026-09-18T05:47:32Z
- **Tasks:** 2
- **Files modified:** 10 created, 0 modified

## Accomplishments

- `taskmanager.domain.value_objects` exists and imports nothing but `collections.abc`, `enum`, `dataclasses` and `typing` - the stdlib-only domain rule (ARC-02, PC-2) holds by construction, and the three import-linter contracts stay KEPT with the new subpackage in the graph.
- `ALLOWED_TRANSITIONS` encodes D-01 exactly and is asserted exhaustive over `set(TaskStatus)`, so adding a fourth status later raises `KeyError` at the entity's lookup rather than silently permitting every move (threat T-02-12).
- `TaskStatus` and `TaskPriority` are proven to serialize as bare lowercase strings through `json.dumps` and f-strings, closing threat T-02-11: no log line or SQL literal can ever ship as `TaskStatus.IN_PROGRESS`.
- `CompletionStats` gives `TaskRepository.completion_stats` a real return type for plan 02-05 (user decision C-04) and pre-places ADR-009's semantics where Phase 3's SQL aggregate will land, with the empty-list `0.0` branch explicitly tested (threat T-02-13).
- The value-object package reports **100% coverage** with no `pragma: no cover` and no coverage `omit`; the whole suite is 29 passed, 100% total.
- The suite was additionally run on the target runtime via `make docker-test` (Python 3.13): 29 passed, coverage gate reached.

## Task Commits

Each task was committed atomically:

1. **Task 1: TaskStatus, TaskPriority and the D-01 transition table** - `59324e6` (feat)
2. **Task 2: CompletionStats value object (user decision C-04)** - `03bb438` (feat)

**Plan metadata:** see the `docs(02-01)` commit that carries this SUMMARY.

## Files Created/Modified

- `src/taskmanager/domain/value_objects/__init__.py` - empty package marker (0 bytes, no re-export barrel)
- `src/taskmanager/domain/value_objects/task_status.py` - `TaskStatus` StrEnum plus `ALLOWED_TRANSITIONS: Final[Mapping[TaskStatus, frozenset[TaskStatus]]]`
- `src/taskmanager/domain/value_objects/task_priority.py` - `TaskPriority` StrEnum (low/medium/high), with the note that `medium` as creation default is the entity's job
- `src/taskmanager/domain/value_objects/completion.py` - `CompletionStats(total, completed)` with the `percentage` property
- `tests/unit/domain/__init__.py` - empty package marker (0 bytes)
- `tests/unit/domain/test_task_status.py` - 9 tests: serialization, f-string form, rebuild-from-value, unknown-value rejection, member count, table exhaustiveness, the exact matrix, the forbidden `completed -> pending`, no self-transitions
- `tests/unit/domain/test_task_priority.py` - 5 tests: declaration order, serialization, f-string form, rebuild-from-value, unknown-value rejection
- `tests/unit/domain/test_completion.py` - 7 tests: empty list, rounding, full list, untouched list, float type, immutability, slots
- `.planning/phases/02-domain-error-contract/evidence/02-01-tdd-red.txt` - the observed RED runs for both tasks
- `.planning/phases/02-domain-error-contract/evidence/02-01-frozen-slots-setattr.txt` - the 3.13-vs-3.14.3 `frozen+slots` divergence, probe and both outputs

## Decisions Made

- **RED captured as evidence, not as a commit.** The plan marks both tasks `tdd="true"`. A separate `test(...)` RED commit is impossible here: the pre-commit `mypy (strict)` hook fails on a test importing a module that does not exist yet (`import-untyped` / `import-not-found`), and both CLAUDE.md and the execution brief forbid `--no-verify`. Phase 1 could commit RED at plan 01-02 only because the hooks did not exist until plan 01-04. The cycle was therefore run for real - tests written, `pytest` run, failure observed - and the failing output committed as `evidence/02-01-tdd-red.txt` alongside the green code. Honesty preserved, gate preserved.
- **No `can_transition()` helper in the enum module.** D-01 belongs to the `Task` entity (plan 02-03); a second implementation next to the table would be the duplicated-limit defect D-04 forbids.
- **`CompletionStats` performs no validation.** A `__post_init__` rejecting `completed > total` would make a value object depend on the error hierarchy to describe a state only a broken SQL aggregate could produce. The reason is written into the module docstring so the absence reads as a decision.
- **Both enum modules name their rejected alternative in the docstring** (`class X(str, Enum)` and its `TaskStatus.PENDING` formatting leak), per the Phase 1 docstring voice.
- **ARC-02 is not yet checked off in `REQUIREMENTS.md`.** This plan delivers its value-object half, but the requirement reads "domain entities *and* value objects are stdlib dataclasses/Enums; the domain package imports no third-party library" and is also claimed by plans 02-03 (entities), 02-06 (the AST proof that the domain is stdlib-only) and 02-07. Ticking it here would assert something that is not yet true; plan 02-07, the last claimant, owns the tick.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] The `slots=True` test asserted an exception type that differs between the two runtimes of this project**

- **Found during:** Task 2 (CompletionStats)
- **Issue:** The plan prescribes `pytest.raises(AttributeError)` for assigning an undeclared attribute. Written that way, the test failed on the developer host with `TypeError: super(type, obj): obj (instance of CompletionStats) is not an instance or subtype of type (CompletionStats)`. Cause: the `__setattr__` that `dataclasses` generates for a frozen class tests `type(self) is cls` before falling through to `super(cls, self).__setattr__`; `slots=True` rebuilds the class, and on CPython 3.14.3 the closure cell still holds the pre-slots class, so a non-field name reaches a `super()` call that raises. A probe on `python:3.13-slim-trixie` - the Docker and CI runtime - showed the opposite: `FrozenInstanceError` (an `AttributeError` subclass) for **both** field and non-field names. The plan's assertion would have been green in Docker/CI and red on the host; the inverse of the usual trap, and equally fatal.
- **Fix:** The test now asserts the portable claim - the assignment is refused (`pytest.raises((AttributeError, TypeError))`), the attribute still does not exist, the instance has no `__dict__`, and `CompletionStats.__slots__ == ("total", "completed")`. A comment names both interpreters and both exception types so the tuple does not read as hedging.
- **Files modified:** `tests/unit/domain/test_completion.py`
- **Verification:** `.venv/bin/pytest -q` green on CPython 3.14.3 (29 passed) and `make docker-test` green on CPython 3.13 (29 passed).
- **Committed in:** `03bb438` (Task 2 commit), with the probe output captured in `evidence/02-01-frozen-slots-setattr.txt`

**2. [Rule 3 - Blocking] `flake8-comprehensions` C416 on the priority serialization test**

- **Found during:** Task 1 (TaskPriority tests)
- **Issue:** `json.dumps([member for member in TaskPriority])` is an unnecessary comprehension; `make lint` would have failed the commit.
- **Fix:** Rewritten as `json.dumps(list(TaskPriority))`.
- **Files modified:** `tests/unit/domain/test_task_priority.py`
- **Verification:** `.venv/bin/flake8 src tests` exits 0.
- **Committed in:** `59324e6` (Task 1 commit)

**3. [Rule 3 - Blocking] E501 on a test docstring**

- **Found during:** Task 1 (TaskStatus tests)
- **Issue:** The member-count test's docstring ran to 90 characters, over the 88-character limit black does not reflow inside a string.
- **Fix:** Shortened to `"""Exactly three statuses; cancelled, archived and blocked stay out of scope."""`.
- **Files modified:** `tests/unit/domain/test_task_status.py`
- **Verification:** `.venv/bin/flake8 src tests` exits 0.
- **Committed in:** `59324e6` (Task 1 commit)

---

**Total deviations:** 3 auto-fixed (1 bug, 2 blocking)
**Impact on plan:** No scope change. Deviation 1 is the only substantive one and it strengthens the test: the phase now carries executed proof of a CPython behaviour that plan 02-03's slotted entities will meet again.

## Issues Encountered

- **TDD gate commits could not be separated** (see Decisions Made). The RED phase was executed and captured, but the RED state itself is not committable under this repository's hooks. Every later `tdd="true"` plan in this phase will hit the same wall; the evidence-file convention established here is the answer.
- Nothing else. Both tasks passed their `<verify>` chains on the first full run after the fixes above.

## Known Stubs

None. Every symbol this plan created is fully implemented and exercised by tests; `domain/value_objects/` is at 100% statement and branch coverage.

## TDD Gate Compliance

The plan's tasks are `tdd="true"` and the cycle was executed in order, but the gate commits are **not** separable in this repository:

- **RED:** performed and observed for both tasks (`ModuleNotFoundError` collection failures), captured verbatim in `evidence/02-01-tdd-red.txt`. Not committed on its own, because the `mypy (strict)` pre-commit hook rejects a test importing a module that does not exist and `--no-verify` is forbidden by CLAUDE.md.
- **GREEN:** `59324e6` and `03bb438`, each carrying its task's tests and implementation together.
- **REFACTOR:** not needed; no structural change was made after green.

## Threat Flags

None. This plan introduces no network endpoint, no auth path, no file access and no schema; every import is stdlib and nothing was installed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 02-02 (`domain/exceptions.py`) can start immediately; it has no dependency on this plan beyond the package layout and the docstring/testing conventions now fixed by two committed examples.
- Plan 02-03 (entities) has `TaskStatus`, `TaskPriority` and `ALLOWED_TRANSITIONS` to import, and should read `evidence/02-01-frozen-slots-setattr.txt` before writing negative attribute tests against `@dataclass(slots=True)` entities.
- Plan 02-05 (ports) has `CompletionStats` as the real return type for `TaskRepository.completion_stats`, so no Protocol will reference a non-existent name.
- No blockers.

## Self-Check: PASSED

All ten created files exist on disk and both task commits are present in `git log`.

---
*Phase: 02-domain-error-contract*
*Completed: 2026-09-18*
