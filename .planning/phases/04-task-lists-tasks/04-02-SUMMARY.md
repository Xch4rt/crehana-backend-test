---
phase: 04-task-lists-tasks
plan: 02
subsystem: database
tags: [sqlalchemy, postgres, group-by, filter-aggregate, import-linter, protocol, mypy-strict]

# Dependency graph
requires:
  - phase: 02-domain-error-contract
    provides: "The eight Protocol ports, the in-memory fakes, CompletionStats"
  - phase: 03-persistence-runnable-stack
    provides: "SqlAlchemyTaskListRepository, mappers, completion_statement as the module-level-statement precedent, the .importlinter contract set"
provides:
  - "TaskListRepository.list_for_owner_with_stats(owner_id) -> Sequence[tuple[TaskList, CompletionStats]] on the port, the fake and the SQLAlchemy adapter"
  - "lists_with_stats_statement(owner_id): LIST-03's data in one grouped LEFT OUTER JOIN, compiled-SQL-asserted"
  - "D-13 ordering on both list-returning fake methods, matching the adapter"
  - "The no-http-below-presentation import-linter contract (D-15), with a two-layer red capture"
affects: [04-05, 04-08, 04-09, 04-10, 04-12]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Grouped statistics query: select(Row, count(child.id), count(child.id).filter(...)) + outerjoin + group_by(pk)"
    - "A port method returning tuple[Entity, ValueObject] rather than a new domain value object"

key-files:
  created:
    - .planning/phases/04-task-lists-tasks/evidence/04-02-importlinter-red.txt
    - .planning/phases/04-task-lists-tasks/evidence/04-02-port-change-red.txt
  modified:
    - src/taskmanager/application/ports/repositories.py
    - src/taskmanager/infrastructure/db/repositories/task_lists.py
    - tests/unit/application/fakes.py
    - tests/unit/application/test_ports.py
    - tests/unit/application/test_fakes.py
    - tests/integration/test_repositories_task_lists.py
    - .importlinter
    - tests/architecture/test_layer_boundaries.py

key-decisions:
  - "Tasks 1 and 2 shipped as ONE commit, against the plan's two: adding a method to a Protocol breaks every implementation of it at once, so the tree between them does not type-check, and CLAUDE.md requires `make typecheck` green before every commit with --no-verify forbidden. The red step is captured in evidence/04-02-port-change-red.txt instead - the same compromise 02-01 recorded for its TDD RED step"
  - "The D-15 violation is planted TWICE, against the plan's one. In `application` the import also breaks the pre-existing application-framework-free contract, so it proves the contract fires but not that it earns its place; planted in `infrastructure` - the only layer it adds - exactly ONE contract is reported BROKEN"
  - "`list_for_owner_with_stats` sorts its own pairs rather than delegating to `list_for_owner`, mirroring the adapter where the two ORDER BY clauses are separate; a delegation would leave the ordering test green if the grouped statement lost its ORDER BY entirely"
  - "FakeTaskListRepository takes the sibling FakeTaskRepository through its constructor and FakeUnitOfWork hands over the one it already builds, so the fake counts what a use case actually stored and can disagree with a wrong implementation"
  - "The integration helper derives task ids from the list's LAST four hex digits, never its first eight: every identifier in that module shares the prefix 00000000-0000-4000-8000-, and a prefix-based derivation was observed failing on pk_tasks"
  - "The compiled-SQL test asserts count(*) ABSENT as well as count(tasks.id) present - the two render almost identically and differ only on the null-extended row an empty list produces"
  - "Requirement tick LIST-03 deliberately NOT taken - 04-12 is the last claimant, and this plan ships the repository capability with no endpoint above it"

patterns-established:
  - "Grouped stats statement: a module-level function returning Select[tuple[Row, int, int]], asserted by compiling it against a typed create_engine dialect with no server"
  - "A new import-linter contract is falsified in the layer it UNIQUELY covers, not merely in a layer some older contract already guards"

requirements-completed: []

# Metrics
duration: 18min
completed: 2026-09-18
---

# Phase 4 Plan 02: LIST-03's grouped query and D-15's contract Summary

**LIST-03's per-list counters now come from one `LEFT OUTER JOIN` with `count(tasks.id) FILTER`, asserted from compiled SQL with no server, and a business layer that imports FastAPI fails a contract proven able to fail in the one layer only it covers.**

## Performance

- **Duration:** ~18 min
- **Tasks:** 3 of 3 (committed as 2 commits, see Deviations)
- **Files modified:** 8 modified, 2 evidence files created

## Accomplishments

- `list_for_owner_with_stats` exists on the port, the in-memory fake and the SQLAlchemy adapter, in domain types only, all three conforming under `mypy --strict`.
- The adapter answers it in **one** statement. The compiled SQL is asserted to contain `FILTER (WHERE`, `LEFT OUTER JOIN`, exactly two `count(tasks.id)` and exactly one `FROM task_lists`, and to contain **no** `count(*)` — the trap that would make an empty list report one phantom task.
- Both list-returning fake methods now order by `(created_at, id)`, closing the divergence 04-PATTERNS §11 named: the adapter has always sorted, the fake never did, so a D-13 assertion would have passed in a unit test and failed over HTTP.
- The `no-http-below-presentation` contract is configured, registered by name, and **falsified in `infrastructure`**, where no other contract covers it and exactly one is reported BROKEN.

## Task Commits

1. **Task 1 + Task 2: the port, the fake, the two conformance tests, the grouped statement and the adapter method** — `c7ae50b` (feat)
2. **Task 3: D-15's contract, its name registration and the red capture** — `1b55626` (feat)

**Plan metadata:** see the final `docs(04-02)` commit.

## Files Created/Modified

- `src/taskmanager/application/ports/repositories.py` — `list_for_owner_with_stats` on `TaskListRepository`, with the N+1 and the domain-types-only arguments above it.
- `src/taskmanager/infrastructure/db/repositories/task_lists.py` — `lists_with_stats_statement()` (module-level, so the SQL can be compiled) and the adapter method that runs it and maps each grouped row into `CompletionStats`.
- `tests/unit/application/fakes.py` — `FakeTaskListRepository(tasks=...)`, the new method counted from the task fake's stored tasks, and `sorted(...)` on both list methods; `FakeUnitOfWork` wires the two repositories together.
- `tests/unit/application/test_ports.py` — the port now asserts the declaration itself, not only the fake's conformance.
- `tests/unit/application/test_fakes.py` — four new tests: per-owner entries with differing mixes, the empty list at 0.0, owner scoping, and the `(created_at, id)` order asserted of **both** methods.
- `tests/integration/test_repositories_task_lists.py` — six new tests against PostgreSQL 18, plus `given_tasks_in` and the `DIALECT` constant.
- `.importlinter` — the D-15 contract with a comment block recording what is deliberately in and out.
- `tests/architecture/test_layer_boundaries.py` — `EXPECTED_CONTRACT_NAMES` gains the fourth name.

## Gate Results

| Gate | Result |
|------|--------|
| `make lint` | green (black, isort, flake8) |
| `make typecheck` | green — `Success: no issues found in 101 source files` |
| `make arch` | `Contracts: 4 kept, 0 broken.` |
| `make test` | `321 passed`, **Total coverage: 100.00%** |
| `lints_with_stats_statement` coverage | `task_lists.py` 58 statements, 0 missed, **100%** |

## Deviations from Plan

### 1. [Rule 3 — Blocking] Tasks 1 and 2 shipped as one commit

- **Found during:** Task 1, at the commit step.
- **Issue:** The plan schedules Task 1 (port + fake) and Task 2 (adapter) as separate commits, and explicitly says `tests/unit/infrastructure/test_adapter_ports.py` "is expected to be red between Task 1 and Task 2, and that is the guard working". It was — mypy reported `SqlAlchemyTaskListRepository is missing following TaskListRepository protocol member: list_for_owner_with_stats` in two files. But CLAUDE.md requires `make typecheck` green before **every** commit, pre-commit enforces it, and `--no-verify` is forbidden. The red tree is uncommittable.
- **Fix:** The red state was observed and captured verbatim to `.planning/phases/04-task-lists-tasks/evidence/04-02-port-change-red.txt`, and the two tasks were committed together with the reason in the commit body. This is the identical compromise plan 02-01 recorded for its TDD RED step (`evidence/02-01-tdd-red.txt`), so it is a precedent rather than a new decision.
- **Commit:** `c7ae50b`

### 2. [Rule 2 — Missing critical verification] The D-15 violation is planted twice

- **Found during:** Task 3, reading the first capture.
- **Issue:** The plan asks for one planted `from fastapi import HTTPException` inside `src/taskmanager/application/`. The capture showed **two** contracts BROKEN, because `application-framework-free` already forbade `fastapi` there. That capture proves the new contract fires; it does not prove it is worth having, since the build would have gone red without it.
- **Fix:** A second planting in `src/taskmanager/infrastructure/db/engine.py` — the only layer `no-http-below-presentation` adds — where exactly **one** contract is reported BROKEN and it is the new one. Both runs are in the evidence file, and the header states why the first is insufficient. Same reasoning as 02-06's demonstrated gap.
- **Commit:** `1b55626`

### 3. [Rule 1 — Bug] Task ids in the integration helper collided on `pk_tasks`

- **Found during:** Task 2, first integration run.
- **Issue:** `given_tasks_in` derived task ids from `task_list_id.hex[:8]`. Every identifier in `test_repositories_task_lists.py` shares the prefix `00000000-0000-4000-8000-`, so two different lists produced identical task ids and PostgreSQL refused the second batch with a `pk_tasks` unique violation.
- **Fix:** Derive from the list's last four hex digits instead, with the reason in a comment so the next helper in that module does not repeat it.
- **Commit:** `c7ae50b`

### 4. [Rule 1 — Bug] The bound-parameter assertion matched its own label

- **Found during:** Task 2.
- **Issue:** `assert TaskStatus.COMPLETED.value not in compiled` fails because the statement labels its counter `AS completed`.
- **Fix:** Elide the label first, exactly as `test_the_aggregate_is_a_single_statement` in the sibling module already does.
- **Commit:** `c7ae50b`

### 5. [Minor] A second evidence file, not in `files_modified`

`evidence/04-02-port-change-red.txt` is the artifact deviation 1 produces. The plan's `files_modified` lists only the import-linter capture.

## Requirements

`LIST-03` is **not** ticked. Plan 04-12 is its last claimant, and this plan ships the repository capability with no endpoint above it — the same call Phase 3 made ten consecutive times.

## Handoff Notes

- **04-05** (the task-list use cases) consumes `uow.task_lists.list_for_owner_with_stats(owner_id)` and gets ordering for free in both the fake and the adapter. It owns naming the pair on the result DTO — the port deliberately returns a bare `tuple`, per 04-RESEARCH Open Question 2.
- **04-08**'s AST gate is the symbol-level half of D-15. The `.importlinter` comment already points at it by path; the contract answers the module-level question and cannot answer the other.
- **04-10**'s runtime statement counter now has something meaningful to count: the query it will assert `== 1` over was written as one grouped statement, and `test_listing_with_stats_is_a_single_statement` fails independently if that stops being true.
- `EXPECTED_CONTRACT_NAMES` now holds four names. Any later plan adding a contract must edit both files in one change.

## Self-Check: PASSED

- `.planning/phases/04-task-lists-tasks/evidence/04-02-importlinter-red.txt` — FOUND
- `.planning/phases/04-task-lists-tasks/evidence/04-02-port-change-red.txt` — FOUND
- `src/taskmanager/infrastructure/db/repositories/task_lists.py` contains `lists_with_stats_statement` — FOUND
- `.importlinter` contains `no-http-below-presentation` — FOUND
- commit `c7ae50b` — FOUND
- commit `1b55626` — FOUND
