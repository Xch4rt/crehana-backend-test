---
phase: 02-domain-error-contract
plan: 05
subsystem: application
tags: [python, protocol, structural-typing, dataclass, slots, unit-of-work, pytest-asyncio, mypy]

# Dependency graph
requires:
  - phase: 01-foundation-quality-gates
    provides: src layout, editable install, pytest/mypy/flake8/black/isort gates, import-linter contracts, coverage gate
  - plan: 02-01
    provides: TaskStatus, TaskPriority and CompletionStats, the types the port signatures and the result DTO speak in
  - plan: 02-02
    provides: TaskNotFoundError, TaskListNotFoundError, AuthorizationError and InvalidStatusTransitionError, the only errors the use case raises or lets through
  - plan: 02-03
    provides: Task, TaskList and User, and the change_status(new_status, *, now) signature the use case calls
provides:
  - the eight ports as implementation-free typing.Protocol classes (ARC-04)
  - the UnitOfWork async context manager that owns the transaction boundary
  - the command convention - frozen, slotted, actor_id first - that Phase 4 copies
  - TaskResult and its explicit from_entity, the stable field list Phase 4 maps to
  - ChangeTaskStatus, the reference use case shape: one class, constructor injection, one execute
  - tests/unit/application/fakes.py, the in-memory doubles every later application test drives
  - 22 new tests, application/ at 100% statement and branch coverage
affects: [02-06-stdlib-proof, 02-07-phase-close, 03-persistence, 04-crud-endpoints, 05-auth]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Protocols carry `...` bodies only; coverage's exclude_also makes them free coverage, and the def lines are covered by the conformance imports"
    - "A Protocol whose methods are all one-liners stays packed; one wrapping signature means a blank line between every method of that Protocol (E301)"
    - "A fake satisfying a Protocol with mutable attribute members annotates those attributes with the port type exactly, and exposes the concrete object under a second name for assertions"
    - "Conformance is a named test per port - an annotated local binding plus a runtime assertion - so ARC-04 reads off the pytest report, not off mypy's exit code"
    - "A failure test catches the base DomainError and asserts which leaf came out, so a wrong-but-plausible error type fails instead of passing"

key-files:
  created:
    - src/taskmanager/application/ports/__init__.py
    - src/taskmanager/application/ports/repositories.py
    - src/taskmanager/application/ports/unit_of_work.py
    - src/taskmanager/application/ports/security.py
    - src/taskmanager/application/ports/notifications.py
    - src/taskmanager/application/ports/clock.py
    - src/taskmanager/application/dto/__init__.py
    - src/taskmanager/application/dto/commands.py
    - src/taskmanager/application/dto/results.py
    - src/taskmanager/application/use_cases/__init__.py
    - src/taskmanager/application/use_cases/tasks/__init__.py
    - src/taskmanager/application/use_cases/tasks/change_task_status.py
    - tests/unit/application/__init__.py
    - tests/unit/application/fakes.py
    - tests/unit/application/test_ports.py
    - tests/unit/application/test_change_task_status.py
    - .planning/phases/02-domain-error-contract/evidence/02-05-tdd-red.txt
  modified: []

key-decisions:
  - "FakeUnitOfWork exposes each repository twice - `tasks` typed as the port, `task_repository` as the fake - because mypy checks a mutable protocol member invariantly, so the port-typed attribute cannot also be the concrete one"
  - "The invisible-task test catches DomainError and then asserts the leaf type, because catching TaskNotFoundError directly would pass whether or not a 403 leg existed"
  - "The use case has no same-state branch: idempotence is a change_status invariant, and a second copy of that knowledge here would be the two-layer defect D-04 forbids"
  - "TaskResult.from_entity names all eleven fields explicitly rather than splatting the entity, so a future entity field cannot leak into an API response by being declared"
  - "runtime_checkable is rejected in unit_of_work.py's docstring, where the concrete reason lives: issubclass() raises TypeError on a Protocol with non-method members"

patterns-established:
  - "Port modules name their rejected alternative in the docstring's why paragraph, the same voice the domain modules use"
  - "A fake records mutations in `added`/`updated`/`deleted` lists so a use-case test can assert a write happened exactly once, not merely that the final state is right"
  - "A use-case test builder places entities into the fake's `stored` dict directly, so every entry in the mutation records was written by the code under test"

requirements-completed: []

# Metrics
duration: 22min
completed: 2026-09-18
---

# Phase 2 Plan 05: Application Ports, DTO Conventions and the Reference Use Case Summary

**The eight ports exist as `typing.Protocol` classes with nothing but `...` in their bodies, every one of them has a conforming in-memory fake under `tests/` proven by mypy strict and named in the pytest report, and one real use case - `ChangeTaskStatus` - demonstrates the shape Phase 4 copies: one class, constructor injection, a single `async def execute(command) -> Result` that loads, authorizes, calls the domain, persists and commits inside the `UnitOfWork` block, answering `TaskNotFoundError` rather than a 403 for a task the actor cannot see. 22 new tests, `application/` at 100% statement and branch coverage, 138 passed on both CPython 3.14.3 and 3.13.**

## Performance

- **Duration:** 22 min
- **Started:** 2026-09-18T07:03:28Z
- **Completed:** 2026-09-18T07:25:22Z
- **Tasks:** 3
- **Files modified:** 17 created, 0 modified

## Accomplishments

- **ARC-04 is satisfied and demonstrable.** All eight ports - `TaskRepository`, `TaskListRepository`, `UserRepository`, `UnitOfWork`, `PasswordHasher`, `TokenService`, `EmailNotifier`, `Clock` - are `Protocol` classes whose every method body is `...`. No default implementation, no `raise NotImplementedError`, no `@runtime_checkable`, and no `IdGenerator`: `grep -rc '(Protocol)'` over `ports/` sums to exactly 8, which is the roadmap's "ports exist with no implementation" taken literally.
- **Conformance is proven twice, statically and visibly.** `mypy src tests` accepts eight annotated bindings such as `repository: TaskRepository = FakeTaskRepository()` - structural matching, method by method, including keyword-only parameters - and eight named `test_fake_*_satisfies_the_*_port` tests put the same claim in the pytest report where an evaluator can see it without running a type checker.
- **The `UnitOfWork` is the transaction boundary, and the counter proves it.** `FakeUnitOfWork.__aexit__` returns `None` and commits nothing; `commits` and `rollbacks` are integers the use-case tests assert on. Every one of the four failure tests asserts `uow.commits == 0`, so "a refused operation writes nothing" (threat T-02-27) is a property of the suite rather than of one test.
- **The ADR-008 leak is closed by a falsifiable test** (threat T-02-25). `test_change_task_status_hides_a_task_the_actor_cannot_see` catches the base `DomainError`, then asserts the escaping error *is* a `TaskNotFoundError` and *is not* an `AuthorizationError`, and that its `details` carry only `{"task_id": ...}`. Catching `TaskNotFoundError` directly would have passed just as happily against an implementation that had never considered the 403 question.
- **Authorization lives in the use case, not in a future router** (threat T-02-26). `_may_change_status(task, task_list, actor_id)` is a named module-level helper reading `task_list.owner_id == actor_id or task.assignee_id == actor_id`, and both of its outcomes plus the ASGN-02 assignee path have their own test. The router will pass `actor_id` and nothing else.
- **The DTO conventions are written where Phase 4 will look.** `commands.py`'s docstring states the convention once - frozen, slotted, `actor_id: UUID` first, filled from the JWT subject and never from the request body - and names the rejected alternative (Pydantic command models, D-16). `results.py` explains why a result is a separate immutable copy rather than the entity: no mutable aggregate and no session-attached relationship crosses the boundary, which is what makes Phase 3's `lazy="raise"` safe.
- **The application layer imports no framework, no ORM and no Pydantic.** The grep over `src/taskmanager/application/` for `fastapi`, `starlette`, `sqlalchemy`, `alembic`, `pydantic`, `jwt` and `pwdlib` returns nothing, `HTTPException` appears nowhere, and `lint-imports` keeps all three contracts with 79 dependencies now in the graph (threat T-02-28).
- **100% statement and branch coverage over `taskmanager.application`** - 70 statements, 6 branches, 0 missed - with no `pragma: no cover` and no coverage `omit`. Whole suite: 138 passed, 100% total, zero warnings under `filterwarnings = error`.
- **Verified on the target runtime.** `make docker-test` (CPython 3.13) reports 138 passed and the same 100%, so nothing here depends on the host's 3.14.3 - including the frozen+slots negative tests, which carry the portable-claim hedge plan 02-01 established.

## Task Commits

Each task was committed atomically:

1. **Task 1: the eight ports as typing.Protocol with no implementation** - `5e9cdaf` (feat)
2. **Task 2: in-memory fakes and one named conformance test per port** - `6561341` (test)
3. **Task 3: the DTO conventions and the ChangeTaskStatus reference use case** - `8f9f98b` (feat)

**Plan metadata:** see the `docs(02-05)` commit that carries this SUMMARY.

## Files Created/Modified

- `src/taskmanager/application/ports/repositories.py` (83 lines) - the three persistence ports; the docstring names ORM rows as the rejected return type and explains that `completion_stats` is a port method because ADR-009 puts the percentage behind one SQL aggregate
- `src/taskmanager/application/ports/unit_of_work.py` (55 lines) - `UnitOfWork` with `__aenter__ -> Self` and a `TracebackType`-typed `__aexit__`; also the single place `runtime_checkable` is argued down, because this is the port with non-method members
- `src/taskmanager/application/ports/security.py` (43 lines) - `PasswordHasher` and `TokenService`, with the paragraph explaining why `TokenService` is async despite signing no I/O (D-19)
- `src/taskmanager/application/ports/notifications.py` (34 lines) - `EmailNotifier` with a keyword-only signature, so two adjacent strings cannot be transposed silently
- `src/taskmanager/application/ports/clock.py` (26 lines) - `Clock`, the one sync port; the docstring rejects both the bare `Callable[[], datetime]` and putting the port in `domain/` (an upward import the `layers` contract fails)
- `src/taskmanager/application/dto/commands.py` (40 lines) - `ChangeTaskStatusCommand` and the command convention paragraph Phase 4 inherits
- `src/taskmanager/application/dto/results.py` (62 lines) - `TaskResult` with all eleven fields and an explicit `from_entity`
- `src/taskmanager/application/use_cases/tasks/change_task_status.py` (86 lines) - the reference use case, `_may_change_status`, and a docstring naming three rejected shapes plus the deliberate absence of an `AuthorizationError` branch
- `tests/unit/application/fakes.py` (241 lines) - the eight in-memory doubles and `FrozenClock`
- `tests/unit/application/test_ports.py` (10 tests) - eight conformance tests plus the frozen-clock and completion-stats behaviour tests
- `tests/unit/application/test_change_task_status.py` (12 tests) - four DTO tests and eight use-case tests
- five empty `__init__.py` package markers (`ports/`, `dto/`, `use_cases/`, `use_cases/tasks/`, `tests/unit/application/`), 0 bytes each
- `.planning/phases/02-domain-error-contract/evidence/02-05-tdd-red.txt` - the two observed RED collection failures, their GREEN counterparts, the application coverage slice and the Docker run

## Decisions Made

- **`FakeUnitOfWork` exposes every repository under two names, and the docstring says why.** `UnitOfWork` declares `tasks`, `task_lists` and `users` as mutable attribute members, and mypy checks those **invariantly** - a `FakeTaskRepository`-typed attribute does not satisfy a `TaskRepository`-typed protocol member. So `self.tasks: TaskRepository` is what the use case sees and what makes the fake conform, while `self.task_repository` is the same object under its concrete type and is what a test reaches for `added`, `updated`, `deleted` and `stored`. The alternative - declaring the port members as read-only properties - would have changed the port's shape away from RESEARCH's verified form and would have invalidated the `runtime_checkable` argument in the same file.
- **The invisible-task test catches the base error on purpose.** `pytest.raises(TaskNotFoundError)` would be satisfied by an implementation that had simply never grown a 403 path; `pytest.raises(DomainError)` followed by `isinstance` assertions fails loudly if the 404-versus-403 decision ever flips. The same reasoning as 02-04's MRO test: assert the mechanism, not the outcome you hope it produces.
- **The use case has no same-state branch.** `change_status` already returns before it assigns when the requested status is the current one (D-02), so the use case runs its linear body and commits a write that is a no-op at the row level. A branch here would put the state machine's knowledge in two layers - exactly the defect D-04 exists to prevent - and would add an arm the 100% branch gate would then have to cover. `test_change_task_status_is_idempotent_for_the_status_already_held` asserts the unchanged timestamps *and* `commits == 1`, so the behaviour is documented rather than implied.
- **`TaskResult.from_entity` names all eleven fields.** `dataclasses.asdict(task)` or a `**vars(task)` splat would be shorter and would carry any future entity field straight into an API response the moment someone declared it. The explicit form makes crossing the boundary a decision.
- **`runtime_checkable` is argued down in `unit_of_work.py`, not in `__init__.py`.** The package marker stays 0 bytes per the project convention, and the argument belongs next to the port that actually breaks `issubclass()` - the one with non-method members.
- **`FakeTaskListRepository.exists_with_name` folds case.** The unique index LIST-06 asks Phase 3 for is on `(owner_id, lower(name))`; a case-sensitive fake would let a Phase 4 use-case test pass against a rule the database will later refuse.
- **ARC-04 is not ticked in `REQUIREMENTS.md`.** Plan 02-07 also claims it (checked against every `requirements:` line in `02-0*-PLAN.md`), and the convention 02-01 set gives the tick to the last claimant. ARC-02 and ARC-06 remain untouched here for the same reason.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] mypy rejected the fake unit of work: mutable Protocol members are invariant**

- **Found during:** Task 2, at the plan's `<verify>` step (`mypy src tests`)
- **Issue:** `FakeUnitOfWork` was written the obvious way, with `self.tasks` inferred as `FakeTaskRepository` so the use-case tests could reach `uow.tasks.updated` as the plan's behaviour list describes. mypy strict refused the conformance binding: `Incompatible types in assignment (expression has type "FakeUnitOfWork", variable has type "UnitOfWork") ... tasks: expected "TaskRepository", got "FakeTaskRepository"`. A protocol *variable* member is checked invariantly, because the protocol permits assignment to it; only method members and read-only properties are covariant. RESEARCH's Pattern 3 states that a fake satisfying `UnitOfWork` was verified, but does not record this constraint on how its attributes must be annotated.
- **Fix:** each repository is now bound twice in `__init__` - `self.task_repository` (concrete, for assertions) and `self.tasks: TaskRepository` (port-typed, for conformance) - pointing at the same object. The class docstring explains the invariance rule so the duplication does not read as an accident. The use-case tests assert on `unit_of_work.task_repository.updated`.
- **Files modified:** `tests/unit/application/fakes.py`, `tests/unit/application/test_change_task_status.py`
- **Verification:** `.venv/bin/mypy src tests` exits 0 over 58 files; `test_fake_unit_of_work_satisfies_the_unit_of_work_port` passes.
- **Committed in:** `6561341` (Task 2 commit)

**2. [Rule 3 - Blocking] flake8-bugbear B010 on a literal attribute name in `setattr`**

- **Found during:** Task 3, at `make lint`
- **Issue:** `test_task_result_is_immutable` was written as `setattr(result, "title", "edited")`, which bugbear rejects: *"Do not call setattr with a constant attribute value, it is not any safer than normal property access."* The plain assignment the check suggests is not available here - mypy would reject writing to a frozen dataclass field, which is the very refusal the test exists to observe at runtime.
- **Fix:** the attribute name moved into a module-level `DECLARED_RESULT_FIELD` constant, matching the convention plans 02-01 and 02-03 already use for exactly this collision, and the test now also asserts the field name appears in the `FrozenInstanceError` message.
- **Files modified:** `tests/unit/application/test_change_task_status.py`
- **Verification:** `.venv/bin/flake8 src tests` exits 0; the test still fails if the dataclass stops being frozen.
- **Committed in:** `8f9f98b` (Task 3 commit)

---

**Total deviations:** 2 auto-fixed (2 blocking, 0 bugs)
**Impact on plan:** No scope change and no interface change. Every signature in the plan's `<interfaces>` block shipped exactly as written - the deviation is entirely on the test-double side - so plan 02-06, plan 02-07, Phase 3's adapters and Phase 4's use cases are unaffected. The one consequence worth carrying forward: Phase 3's real `SqlAlchemyUnitOfWork` will hit the same invariance rule, and the fix is the same one line of annotation.

## Issues Encountered

- **The plan's behaviour text says `uow.tasks.updated`; the code says `uow.task_repository.updated`.** That is deviation 1 above and it is a naming consequence, not a behaviour change - the assertion, the object and the count are identical.
- **TDD gate commits still not separable** - the same wall plans 02-01 through 02-04 hit. See TDD Gate Compliance below.
- Nothing else. All three tasks passed their full `<verify>` chain, on the host (CPython 3.14.3) and in Docker (CPython 3.13), with zero warnings.

## Known Stubs

None. Every symbol this plan created under `src/` is either a declared port - whose emptiness is the requirement, not a gap - or fully implemented and exercised at 100% statement and branch coverage. The seven ports without a production adapter are Phase 3 and Phase 5 boundaries named in their own docstrings, and each one already has a conforming implementation under `tests/`.

## TDD Gate Compliance

Tasks 2 and 3 are `tdd="true"` and both cycles were executed in order. The gate commits remain **not** separable in this repository - the convention plan 02-01 established applies unchanged, because the `mypy (strict)` pre-commit hook rejects a test importing a module that does not exist and `--no-verify` is forbidden by CLAUDE.md:

- **RED:** `test_ports.py` was written first and run against a tree with no `fakes.py` (`ModuleNotFoundError: No module named 'tests.unit.application.fakes'`). `test_change_task_status.py` was written first and run against a tree with no `dto/` and no `use_cases/` (`ModuleNotFoundError: No module named 'taskmanager.application.dto'`). Both failures, and the GREEN run of the identical command, are captured verbatim in `evidence/02-05-tdd-red.txt`.
- **GREEN:** `6561341` (the fakes, committed with the conformance tests and the RED capture) and `8f9f98b` (the DTOs, the use case and its tests).
- **REFACTOR:** not needed. Both fixes above happened before green was reached, not after it.

Task 1 is not a TDD task and did not claim to be: a `Protocol` with `...` bodies has no behaviour to drive a test from, and its verification is `mypy` plus the conformance tests Task 2 then wrote.

## Threat Flags

None. This plan introduces no network endpoint, no auth path, no file access and no schema; it introduces the *decision points* those will later route through. Every `mitigate` row of the plan's register is implemented and asserted: T-02-25 (the invisible task raises `TaskNotFoundError`, asserted by catching the base and checking the leaf), T-02-26 (`_may_change_status` inside the use case, both outcomes tested, plus the assignee path), T-02-08 (every identifier in both DTOs is a `UUID`; no integer id exists in the model), T-02-27 (`commit()` only after the domain call and the update succeed, `commits == 0` in all four failure tests, `FakeUnitOfWork.__aexit__` returns `None`), T-02-28 (`lint-imports` KEPT plus the grep gate over `src/taskmanager/application/`, `HTTPException` absent), T-02-22 (`PasswordHasher` and `TokenService` are implementation-free, so no hashing or signing code exists yet to get wrong). T-02-SC stays not-applicable: nothing was installed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 02-06 (the AST proof that the domain is stdlib-only, plus the ADRs) now has the application layer in place as the counterexample: `domain/` imports nothing outside the standard library, while `application/` imports `taskmanager.domain` and nothing else. The ADR recording D-16 has a concrete file to point at.
- Plan 02-07 is the last claimant of ARC-04 and owns the tick; every clause of the requirement is now implemented and asserted, so that plan's job is verification rather than construction.
- Phase 3 writes `SqlAlchemyTaskRepository`, `SqlAlchemyTaskListRepository`, `SqlAlchemyUserRepository` and `SqlAlchemyUnitOfWork` against these Protocols. Two things it inherits: the mutable-member invariance rule (deviation 1 - annotate the unit of work's three attributes with the port types), and the fact that nothing may commit in `__aexit__`.
- Phase 4 copies `change_task_status.py`. The shape is one class, `__init__(uow, *other_ports)`, one `execute(command) -> Result`, and the body order `load -> authorize -> invoke domain -> persist -> commit -> map to result`. The 403 leg of ADR-008 belongs to its owner-only operations; this use case documents why it has none.
- Phase 5 fills `PasswordHasher`, `TokenService` and `EmailNotifier`. Their fakes already exist, so an auth use case can be unit-tested before a library is chosen.
- No blockers.

## Self-Check: PASSED

All seventeen created files exist on disk, and all three task commits (`5e9cdaf`, `6561341`, `8f9f98b`) are present in `git log`.

---
*Phase: 02-domain-error-contract*
*Completed: 2026-09-18*
