---
phase: 02-domain-error-contract
plan: 03
subsystem: domain
tags: [python, stdlib, dataclass, slots, state-machine, timezone, pytest, mypy]

# Dependency graph
requires:
  - phase: 01-foundation-quality-gates
    provides: src layout, editable install, pytest/mypy/flake8/black/isort gates, import-linter contracts, coverage gate
  - plan: 02-01
    provides: TaskStatus, TaskPriority and ALLOWED_TRANSITIONS, the table change_status looks up
  - plan: 02-02
    provides: ValidationError and InvalidStatusTransitionError, the only errors the entities raise
provides:
  - require_utc / require_text / optional_text, the shared guards every entity delegates to
  - Task entity owning the D-01 state machine, the D-02 no-op and the D-03 completed_at stamp
  - TaskList entity with the 1-120 trimmed name rule and owner_id for the ADR-008 visibility split
  - User entity holding a canonical lowercased email and a password hash, never a plaintext
  - 63 specification tests, every documented -k selector resolving, domain at 100% coverage
affects: [02-05-ports, 02-06-stdlib-proof, 03-persistence, 04-crud-endpoints, 05-auth]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Entities are mutable @dataclass(slots=True); value objects and DTOs are frozen"
    - "Policy limits live in entity ClassVars and reach the guards as a max_length argument, so no limit is ever a literal twice"
    - "now is a keyword-only argument on every classmethod and mutator; the domain reads no clock"
    - "Mutators validate before they assign, so a rejected operation leaves the entity byte-identical"
    - "Negative attribute tests on a mutable slotted class assert AttributeError directly; only the frozen case needs the portable-claim form"

key-files:
  created:
    - src/taskmanager/domain/validation.py
    - src/taskmanager/domain/entities/__init__.py
    - src/taskmanager/domain/entities/task.py
    - src/taskmanager/domain/entities/task_list.py
    - src/taskmanager/domain/entities/user.py
    - tests/unit/domain/test_validation.py
    - tests/unit/domain/test_task.py
    - tests/unit/domain/test_task_list.py
    - tests/unit/domain/test_user.py
    - .planning/phases/02-domain-error-contract/evidence/02-03-tdd-red.txt
    - .planning/phases/02-domain-error-contract/evidence/02-03-mutable-slots-setattr.txt
  modified: []

key-decisions:
  - "The guards live in one module and take max_length as an argument, so TITLE/DESCRIPTION/NAME/EMAIL limits exist exactly once - in the entity ClassVar"
  - "change_status checks ALLOWED_TRANSITIONS before normalising now, so a rejected move cannot half-apply; the same-state no-op returns before both checks"
  - "Task.reschedule is written as an explicit if/else rather than a one-line ternary, because branch = true makes every arm something the 100% gate must see"
  - "User.PASSWORD_HASH_MAX_LENGTH = 512 is a sanity bound, not a credential policy; the entity validates no email format either, because EmailStr owns that at the boundary"
  - "The negative attribute test asserts AttributeError directly - unlike the frozen value objects, a mutable slotted dataclass behaves identically on 3.13 and 3.14.3, and that was probed rather than assumed"

patterns-established:
  - "__post_init__ assigns the guard's return value back to the field: validation and normalisation are the same pass"
  - "A test module builds its subject through a small module-level factory, so each test body stays arrange / act / assert"
  - "Deliberate non-validations get their own named test, so the absence reads as a decision rather than a gap"

requirements-completed: []

# Metrics
duration: 12min
completed: 2026-09-18
---

# Phase 2 Plan 03: Domain Entities and the Task State Machine Summary

**`Task`, `TaskList` and `User` as stdlib `@dataclass(slots=True)` entities that validate and normalise themselves at construction, with the D-01 state machine living in exactly one place - `change_status` - and `now` arriving as an argument because the domain never reads a clock: 63 new tests, every documented `-k` selector resolving, the whole `taskmanager.domain` package at 100% statement and branch coverage on both CPython 3.14.3 and 3.13.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-09-18T06:16:54Z
- **Completed:** 2026-09-18T06:29:00Z
- **Tasks:** 3
- **Files modified:** 11 created, 0 modified

## Accomplishments

- **The state machine exists once.** `change_status` is the only code in the repository that decides whether a status move is legal; it looks the answer up in `ALLOWED_TRANSITIONS[self.status]` and raises `InvalidStatusTransitionError(self.status, new_status)` for the single forbidden move. Phase 4's endpoint will call this method and translate nothing (TASK-05, roadmap SC-2).
- **A rejected transition cannot half-apply** (threat T-02-18). The membership check runs before any assignment, and the forbidden-transition test asserts the full `(status, updated_at, completed_at)` tuple is identical after the raise - not just that an exception came out.
- **D-02 and D-03 are observable, not implied.** Three same-state tests (one per status) assert nothing moves; two more assert `completed_at` becomes exactly the supplied `now` on entering `completed` and `None` on leaving it.
- **Every temporal field is aware UTC** (D-14, threat T-02-19). `require_utc` refuses a naive value with `ValidationError` and normalises an aware non-UTC one with `astimezone(UTC)`, so `due_date < now` can never raise `TypeError: can't compare offset-naive and offset-aware datetimes` inside a request. Four `naive` tests and one normalisation test pin it.
- **No limit exists twice** (D-04, threat T-02-20). `TITLE_MAX_LENGTH`, `DESCRIPTION_MAX_LENGTH`, `NAME_MAX_LENGTH` and `EMAIL_MAX_LENGTH` are entity `ClassVar`s passed into the guards as `max_length`; the over-length messages interpolate that argument, and the tests build their over-length inputs from the same `ClassVar` (`"a" * (Task.TITLE_MAX_LENGTH + 1)`). There is no `201` and no `2001` anywhere.
- **Rejected values are never echoed** (threat T-02-21). Every `ValidationError` message names the field and, where relevant, the numeric limit; not one quotes the input back, so a caller's payload cannot reach a log line or a problem body through an error path.
- **The domain still reads no clock and imports nothing upward** (D-13). `grep -rc 'datetime.now(\|utcnow(' src/taskmanager/domain` returns 0 for all eleven files, and so does the grep for `from taskmanager.application|infrastructure|presentation`. The three import-linter contracts stay KEPT with the new `entities` subpackage in the graph.
- **No plaintext credential enters the domain** (threat T-02-22). `User` declares `password_hash` only; a test asserts the identifier `password` is absent from `User.__slots__` and that assigning it raises `AttributeError`.
- **100% statement and branch coverage over `taskmanager.domain`** with no `pragma: no cover` and no coverage `omit`: `coverage report --include='*/taskmanager/domain/*' --fail-under=100` exits 0. The whole suite is 100 passed, 100% total.
- **Verified on the target runtime.** `make docker-test` (CPython 3.13) reports 100 passed, coverage gate reached - so nothing here depends on the host's 3.14.3.

## Task Commits

Each task was committed atomically:

1. **Task 1: shared validation guards and the Task entity with the D-01 state machine** - `4a0d53e` (feat)
2. **Task 2: the state machine and the guards read as a specification** - `7dee684` (test)
3. **Task 3: TaskList and User entities with their tests, then the full gate** - `3cad63a` (feat)

**Plan metadata:** see the `docs(02-03)` commit that carries this SUMMARY.

## Files Created/Modified

- `src/taskmanager/domain/validation.py` (66 lines) - `require_utc`, `require_text`, `optional_text`; the only place a policy limit is applied
- `src/taskmanager/domain/entities/__init__.py` - empty package marker (0 bytes, no re-export barrel)
- `src/taskmanager/domain/entities/task.py` (156 lines) - the `Task` aggregate, its two `ClassVar` limits, `__post_init__`, `create`, `rename`, `reschedule` and `change_status`
- `src/taskmanager/domain/entities/task_list.py` (85 lines) - `TaskList` with the 1-120 trimmed name rule, `owner_id`, and the docstring explaining why uniqueness is not enforced here
- `src/taskmanager/domain/entities/user.py` (78 lines) - `User` with the canonical lowercased email, the stored hash, and the two deliberate non-validations named in the docstring
- `tests/unit/domain/test_validation.py` - 13 tests, one per branch of the three guards
- `tests/unit/domain/test_task.py` - 30 tests: three construction, six transition, three same-state, two `completed_at`, five validation, four naive/normalisation, five mutator, one slots
- `tests/unit/domain/test_task_list.py` - 11 tests mirroring the sibling shape
- `tests/unit/domain/test_user.py` - 9 tests, including the explicit `test_user_does_not_validate_the_email_format`
- `.planning/phases/02-domain-error-contract/evidence/02-03-tdd-red.txt` - the observed RED runs for both waves of this plan, plus the GREEN run of the same command
- `.planning/phases/02-domain-error-contract/evidence/02-03-mutable-slots-setattr.txt` - the 3.13 probe showing why the mutable slotted case needs no portable-claim hedge

## Selector Proof (02-VALIDATION.md rows)

Every `-k` selector the validation plan documents resolves and passes against `tests/unit/domain/test_task.py`:

| Selector | Tests selected | Result |
|----------|----------------|--------|
| `-k transition` | 6 | passed |
| `-k same_state` | 3 | passed |
| `-k completed_at` | 3 | passed |
| `-k validation` | 5 | passed |
| `-k naive` | 4 | passed |

## Decisions Made

- **One guard module, limits passed in as arguments.** `require_text(value, field=..., max_length=...)` never knows which entity called it, and its over-length message interpolates the argument. That is what makes the entity `ClassVar` the single source of the limit instead of one of two copies - the concrete shape D-04 asks for, applied to the code rather than only to the layer boundary.
- **`change_status` orders its three steps deliberately.** Same-state returns first (D-02: repeating a request that already succeeded is not a conflict, so no timestamp moves and Phase 4 answers 200). The transition check comes next, before `now` is even normalised, so the entity is provably untouched when the move is refused. Only then does assignment happen. A naive `now` on an *allowed* move still raises `ValidationError`, and a test asserts it.
- **`Task.reschedule` is an explicit `if`/`else`, not a ternary.** `branch = true` in the coverage config means every arm is something the 100% gate must observe; a one-line conditional expression hides one of them from the report rather than proving it. Three tests cover clear / accept / reject.
- **`User.PASSWORD_HASH_MAX_LENGTH = 512` is a sanity bound, and the comment says so.** The real credential policy is a minimum *password* length, which applies to a plaintext that never reaches the domain. An Argon2id encoded hash is around a hundred characters, so the cap can only be hit by something that is not a hash.
- **Two deliberate non-validations have their own tests.** `test_user_does_not_validate_the_email_format` asserts `User.create(email="not-an-email")` succeeds, because duplicating `EmailStr` here would be the two-layer defect D-04 forbids. `TaskList` raises no `DuplicateTaskListNameError`, because an entity cannot see its siblings; the docstring says where that check lives instead (use-case pre-check plus the unique index, LIST-06).
- **The negative attribute test asserts `AttributeError` directly.** Plan 02-01 had to hedge the same claim for `CompletionStats` because a *frozen* slotted dataclass diverges between CPython 3.13 and 3.14.3. That divergence comes from the `__setattr__` `dataclasses` generates for frozen classes; a mutable dataclass installs none, so the refusal comes from the type machinery and is identical everywhere. Probed on `python:3.13-slim-trixie` before the assertion was written, not assumed - capture in `evidence/02-03-mutable-slots-setattr.txt`.
- **`assignee_id` is declared but inert.** It carries whatever the caller supplies and nothing else; a comment records that assignment behaviour is Phase 5 (ASGN-02), so no later phase has to reopen the entity to add a column.
- **ARC-02 and ARC-06 are still not ticked in `REQUIREMENTS.md`.** This plan delivers the entity half of ARC-02 and the entity half of ARC-06's "specific errors", but both are also claimed by 02-04, 02-06 and 02-07. Plan 02-07, the last claimant, owns the tick - the convention 02-01 set.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] The prescribed comment in `validation.py` tripped the plan's own grep gate**

- **Found during:** Task 1, at the plan's `<verify>` step
- **Issue:** The plan's action text asks for a comment above the normalisation saying that a local clock reading with `.astimezone()` applied "is aware but not UTC", quoting the call form verbatim. The plan's own acceptance criterion is `grep -c 'datetime.now(\|utcnow(' src/taskmanager/domain/validation.py` returns 0, so writing the explanation as dictated would have failed the gate that exists to ban the call itself.
- **Fix:** The comment now says "reading a local clock and applying astimezone() with no argument yields an offset-carrying value" - the same warning, without the banned token. This is the third instance of the same collision in this project (01-04's Makefile comments, 02-02's docstring), so it is now an established convention rather than an incident.
- **Files modified:** `src/taskmanager/domain/validation.py`
- **Verification:** `grep -c 'datetime.now(\|utcnow(' src/taskmanager/domain/validation.py` returns 0; the full grep chain in `<verify>` exits 0.
- **Committed in:** `4a0d53e` (Task 1 commit)

**2. [Rule 2 - Missing critical] Four tests the plan's behaviour list does not name, required by branch coverage**

- **Found during:** Task 2, checking the plan's own `--fail-under=100` criterion before committing
- **Issue:** `[tool.coverage.run] branch = true` means the 100% gate over the domain is a *branch* gate. Three code paths had no test in the plan's enumeration: the `if self.completed_at is not None` arm of `Task.__post_init__` (reachable only by constructing a `Task` directly, since `create` always passes `None`), and the accept and reject arms of `reschedule` (the plan lists only the clearing case). `rename`'s failure path was likewise unlisted.
- **Fix:** Added `test_task_rejects_a_naive_completed_at` (constructs the entity directly, as Phase 3's repository will when rehydrating a finished task), `test_task_reschedule_accepts_a_future_due_date`, `test_task_reschedule_rejects_a_due_date_in_the_past` and `test_task_rename_rejects_a_blank_title`. Each is a real behaviour claim, not a coverage filler - the first one in particular specifies what happens on the rehydration path Phase 3 depends on.
- **Files modified:** `tests/unit/domain/test_task.py`
- **Verification:** `.venv/bin/coverage report --include='*/taskmanager/domain/*' --fail-under=100` exits 0 with 0 missed statements and 0 partial branches.
- **Committed in:** `7dee684` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 missing critical)
**Impact on plan:** No scope change, no interface change. Every signature in the plan's `<interfaces>` block shipped exactly as written, so plans 02-05 and Phase 4 are unaffected.

## Issues Encountered

- **TDD gate commits again not separable** - the same wall plans 02-01 and 02-02 hit. See TDD Gate Compliance below.
- The `roadmap update-plan-progress` handler wrote a malformed progress row (`In Progress|  |` instead of `| In Progress | - |`), exactly as observed in plan 02-02. Repaired by hand in the same commit as this SUMMARY; worth reporting upstream rather than fixing repeatedly.
- Nothing else. All three tasks passed their full `<verify>` chain, on the host (CPython 3.14.3) and in Docker (CPython 3.13).

## Known Stubs

None. Every symbol this plan created is fully implemented and exercised. `assignee_id` is declared without assignment *behaviour*, but that is a documented Phase 5 boundary rather than a stub: the field is validated, stored and round-tripped, and its comment names the requirement that will use it (ASGN-02).

## TDD Gate Compliance

All three tasks are `tdd="true"` and the cycle was executed in order. The gate commits remain **not** separable in this repository - the convention plan 02-01 established applies unchanged:

- **RED:** `test_validation.py` and `test_task.py` were written first and run against a tree with no `validation.py` and no `entities/` package; `test_task_list.py` and `test_user.py` were run against a tree with no `task_list.py` and no `user.py`. Both `ModuleNotFoundError` collection failures were observed and captured verbatim in `evidence/02-03-tdd-red.txt`, together with the GREEN run of the same command. Neither is a commit of its own, because the `mypy (strict)` pre-commit hook rejects a test importing a module that does not exist and `--no-verify` is forbidden by CLAUDE.md.
- **GREEN:** `4a0d53e` (guards and `Task`, with the RED capture alongside), `7dee684` (the two test modules), `3cad63a` (`TaskList`, `User` and their tests together).
- **REFACTOR:** not needed; no structural change was made after green.

Commit-type note: `4a0d53e` is a `feat` and `7dee684` a `test`, so tasks 1 and 2 read as GREEN-then-specification in `git log`. The honest ordering is recorded here and in the evidence file rather than faked by a commit sequence the hooks would reject.

## Threat Flags

None. This plan introduces no network endpoint, no auth path, no file access and no schema. Every `mitigate` row of the plan's register is implemented and asserted: T-02-18 (transition check before assignment, entity unchanged after the raise), T-02-19 (`require_utc`), T-02-20 (the four `ClassVar` caps), T-02-21 (messages name the field and the limit, never the value), T-02-22 (`password_hash` only, asserted absent from `__slots__` under its plaintext name), T-02-23 (`slots=True` on all three entities, probed on both runtimes). T-02-SC stays not-applicable: nothing was installed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 02-04 (the RFC 9457 handler) is unblocked and unaffected: the entities raise only `ValidationError` and `InvalidStatusTransitionError`, both already in 02-02's twelve-name set.
- Plan 02-05 (ports, DTOs, the `ChangeTaskStatus` use case) has every signature it was written against: `Task.create`, `task.change_status(new_status, now=now)`, `TaskList.create`, `User.create`. The `Clock` port it declares is what supplies `now`; the domain still does not import it.
- Plan 02-06 (the AST proof that the domain is stdlib-only) now has eleven domain modules to walk, and all of them import only `dataclasses`, `datetime`, `typing`, `uuid`, `enum`, `collections.abc` and `taskmanager.domain`.
- Phase 3 rehydrates entities directly from rows rather than through `create`; `test_task_rejects_a_naive_completed_at` already specifies what `__post_init__` does on that path.
- No blockers.

## Self-Check: PASSED

All eleven created files exist on disk, and all three task commits (`4a0d53e`, `7dee684`, `3cad63a`) are present in `git log`.

---
*Phase: 02-domain-error-contract*
*Completed: 2026-09-18*
