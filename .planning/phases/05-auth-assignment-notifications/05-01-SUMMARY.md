---
phase: 05-auth-assignment-notifications
plan: 01
subsystem: domain
tags: [validation, password-policy, nist-800-63b, jwt, rfc-7518, pydantic-settings, tdd]

# Dependency graph
requires:
  - phase: 02-domain-error-contract
    provides: "domain/validation.py guards and the ValidationError(details={'field': ...}) shape; the Task entity and its validate-before-assign mutator convention"
  - phase: 01-foundation
    provides: "Settings with jwt_secret at min_length=16; pytest.ini's filterwarnings = error"
provides:
  - "taskmanager.domain.validation.require_password(value, *, field) enforcing D-10's 8..128 length policy"
  - "taskmanager.domain.validation.PASSWORD_MIN_LENGTH / PASSWORD_MAX_LENGTH as the single spelling of the policy"
  - "Task.assign(assignee_id, *, now) and Task.unassign(*, now)"
  - "Settings.jwt_secret at min_length=32, so PyJWT's InsecureKeyLengthWarning is unreachable under filterwarnings = error"
affects: [05-02, 05-03, 05-04, 05-05, 05-06, 05-07, 05-08, 05-16]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A domain policy limit with no entity to own it lives as a module-level Final in domain/validation.py, with the asymmetry against Task.TITLE_MAX_LENGTH argued in the docstring"
    - "A deliberate non-guard (no strip, no NUL refusal) is proven by a passing behaviour test, not by a source count"

key-files:
  created: []
  modified:
    - src/taskmanager/domain/validation.py
    - src/taskmanager/domain/entities/task.py
    - src/taskmanager/infrastructure/config/settings.py
    - .env.example
    - tests/unit/domain/test_validation.py
    - tests/unit/domain/test_task.py
    - tests/unit/test_settings.py
    - .planning/phases/05-auth-assignment-notifications/evidence/05-01-tdd-red.txt

key-decisions:
  - "PASSWORD_MIN_LENGTH / PASSWORD_MAX_LENGTH are module Final constants rather than User ClassVars, because User never sees plaintext - only the Argon2 hash reaches the entity, so there is no entity that could own the rule; Phase 2 D-04 still holds and validation.py is the only place in the domain that can hold it"
  - "require_password neither strips nor refuses NUL, and both departures are asserted as behaviour: a 129th-character test would pass against a stripping implementation, so the proofs are 'eight spaces returned byte-identical' and 'a NUL password returned unchanged'"
  - "The two bounds are refused separately with distinct messages, pinned by a test that compares the two message strings, so the 422 body names the bound the caller crossed"
  - "Task.assign and Task.unassign carry no value guard on assignee_id, mirroring reprioritise: a UUID is the constraint, and existence needs a repository the entity has no access to"
  - "The entity deliberately has no same-assignee no-op; D-07's idempotence skips a commit and an email too, so it belongs to AssignTask (05-08), and a test asserts unassign on an unassigned task still moves updated_at so nobody 'fixes' the asymmetry"
  - "jwt_secret's floor is 32, justified by RFC 7518 section 3.2 and by the pytest.ini interaction rather than by taste; every secret in the repository was counted (32 / 34 / 36) before the field changed, so nothing had to be lengthened"
  - "Requirement ticks AUTH-04 and ASGN-02 deliberately NOT taken - 05-16 is the last claimant of both, and this plan ships preconditions with no use case and no endpoint above them"

patterns-established:
  - "A policy constant with no entity home: module-level Final in domain/validation.py, pinned to its decision number by one test, with every other test in the file building its input from the constant"

requirements-completed: []

# Metrics
duration: 6min
completed: 2026-09-19
---

# Phase 5 Plan 01: Phase 5 Preconditions Summary

**The three stdlib-level dependencies the rest of Phase 5 would otherwise have discovered at its
own first mypy or pytest run now exist: the 8..128 password policy in the domain, the two
assignment mutators, and an HS256 key floor that makes `InsecureKeyLengthWarning` unreachable.**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-09-19T14:29Z
- **Completed:** 2026-09-19T14:35Z
- **Tasks:** 3 of 3
- **Files modified:** 8 (0 created, 8 modified — including one new evidence capture)

## Accomplishments

- `require_password` lands beside `require_text` with D-10's policy spelled exactly once, in two
  module-level `Final[int]` constants. An `ast` walk over the function proves neither `8` nor `128`
  appears as a literal in its code and that `_refuse_nul` is genuinely never called, however freely
  the docstring discusses either.
- Both departures from `require_text` are proven by behaviour rather than by a source count:
  `require_password(" " * 8)` returns eight spaces byte-identical (no `strip`), and a password
  containing NUL is returned unchanged (no `_refuse_nul`). A test that only checked lengths would
  have passed against an implementation that quietly trimmed.
- `Task.assign` and `Task.unassign` follow `rename`'s validate-before-assign rule, and two negative
  tests assert both `assignee_id` **and** `updated_at` are unchanged after a refused call — the
  only assertion shape that can observe the half-applied mutation the rule exists to prevent
  (T-4-03).
- `Settings.jwt_secret` refuses 31 characters and accepts 32. The boundary is pinned at 31/32
  rather than at an obviously tiny value, so the floor cannot be lowered back towards PyJWT's
  threshold without a red test.
- The suite went from 653 to 659 tests at 100.00% coverage over 1199 statements, with no pragma and
  no omit anywhere under `src/taskmanager/`.

## Task Commits

1. **Task 1: `require_password`, the 8..128 policy that lives in the domain** — `ccf3b0a` (feat)
2. **Task 2: `Task.assign` and `Task.unassign`** — `5da085e` (feat)
3. **Task 3: Raise the HS256 key floor from 16 to 32 (D-26)** — `dfbf265` (fix)

## Files Created/Modified

- `src/taskmanager/domain/validation.py` — `PASSWORD_MIN_LENGTH` / `PASSWORD_MAX_LENGTH` as module
  `Final[int]`s with the no-entity-home argument in the comment above them, and `require_password`
  with its three departures from `require_text` each argued in the docstring.
- `tests/unit/domain/test_validation.py` — nine password tests: the bounds pinned to D-10's two
  numbers, both inclusive limits, both refusals with their `details`, the two messages proven
  distinct, an all-spaces password, a padded password and a NUL password.
- `src/taskmanager/domain/entities/task.py` — `assign` and `unassign`; the class docstring now
  lists seven mutators instead of five; the `assignee_id` field comment no longer says assignment
  behaviour is still to come.
- `tests/unit/domain/test_task.py` — six assignment cases plus two new fixed UUID constants; no
  `uuid4()` and no `datetime.now()`.
- `src/taskmanager/infrastructure/config/settings.py` — `jwt_secret` at `min_length=32`, with a
  ten-line comment naming RFC 7518 §3.2, the PyJWT warning, the `filterwarnings = error`
  interaction and threat `T-5-02`, and recording the three secrets that were counted first.
- `tests/unit/test_settings.py` — `test_short_secret_is_rejected` now rejects 31 and asserts the
  message names the field and the new floor; a new
  `test_a_secret_exactly_at_the_floor_is_accepted` pins the inclusive side.
- `.env.example` — the `JWT_SECRET` comment states the 32-character minimum and why, and keeps the
  `secrets.token_urlsafe(32)` generation command. No key added or removed, so
  `test_env_example_documents_every_field`'s exact set equality is untouched.
- `.planning/phases/05-auth-assignment-notifications/evidence/05-01-tdd-red.txt` — **created.** The
  observed RED for both TDD tasks.

## Decisions Made

- **The password bounds are module constants, and the docstring says why they are not a
  `ClassVar`.** Every other limit in this project lives on the entity that owns the field
  (`Task.TITLE_MAX_LENGTH`, `User.EMAIL_MAX_LENGTH`). A password has no such entity: `User` holds
  an Argon2 hash and never sees plaintext, so putting the policy on it would mean putting a rule
  about a value the class never receives. Phase 2 D-04 still binds — the rule is spelled once — only
  its home differs, and that is stated in the docstring because it reads as an inconsistency
  otherwise.
- **The NUL acceptance is a recorded decision, not an omission.** T-5-13 is dispositioned
  *accept*: the plaintext never becomes a text column, and refusing a character would be exactly
  the composition rule D-10 rules out. The docstring says this and a passing test proves the code
  agrees with the docstring.
- **The two refusals are separate, with different messages.** A single "must be between 8 and 128"
  message would restate the range to a caller who already knows it; the split tells them which
  bound they crossed. A test compares the two message strings so a later merge into one message
  fails.
- **No entity-level assignment no-op.** `change_status` has one (D-02) and `assign` deliberately
  does not, because D-07's idempotence has to skip a commit and an assignment email as well as a
  field. `test_task_unassign_on_an_unassigned_task_still_moves_the_timestamp` exists specifically
  so that a later reader who notices the asymmetry cannot "fix" it without going red.
- **The key floor was justified before it was raised, and the existing secrets were counted
  first.** `awk` over `.env.example` prints 34, over `ci.yml` 36, and `tests/conftest.py` is
  `"b" * 32`. Nothing had to be lengthened, which is the finding that made D-26 a one-line change
  rather than a repo-wide one.
- **No requirement ticks taken.** The plan's frontmatter names AUTH-04 and ASGN-02; 05-16 is the
  last claimant of both. AUTH-04 is the indistinguishable-login property and ASGN-02 is the
  assignment endpoint — this plan ships a validator and two mutators, with no use case and no route
  above either. The same call Phase 3 made ten consecutive times and Phase 4 eleven.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical functionality] The `assignee_id` field comment was left stale by the plan**

- **Found during:** Task 2
- **Issue:** `src/taskmanager/domain/entities/task.py` carried a Phase 2 comment reading
  "Assignment behaviour itself arrives in Phase 5 (ASGN-02); nothing in this phase writes this
  field beyond carrying what the caller supplied." The moment `assign` and `unassign` existed, the
  second clause was false. The plan's action block names the *class* docstring as the thing to
  update and does not mention the field comment.
- **Fix:** The comment now records that the field was declared in Phase 2 and has been written by
  `assign` / `unassign` since Phase 5, and why it stays optional.
- **Files modified:** `src/taskmanager/domain/entities/task.py`
- **Verification:** `make lint`, `make typecheck`, `make test` all green
- **Committed in:** `5da085e`

**2. [Rule 2 - Missing critical functionality] Three tests beyond the plan's enumerated behaviour**

- **Found during:** Tasks 1 and 3
- **Issue:** Task 1's `<behavior>` block lists seven cases, all of which would pass against an
  implementation whose constants were `8` and `128` by coincidence rather than by policy, and
  against one whose two refusals carried the same message — which the same task's action block
  explicitly requires to differ. Task 3 specifies the rejected input (31) but not the accepted one
  (32), so the inclusive side of the new floor would have been unasserted.
- **Fix:** added `test_the_password_bounds_are_the_policy_d10_states` (the one place the two
  numbers are spelled as literals, so every other password test can build its input from the
  constants), `test_the_two_refusals_carry_different_messages`, and
  `test_a_secret_exactly_at_the_floor_is_accepted`.
- **Files modified:** `tests/unit/domain/test_validation.py`, `tests/unit/test_settings.py`
- **Verification:** `.venv/bin/pytest tests/unit tests/architecture -q --no-cov` → `464 passed`
- **Committed in:** `ccf3b0a` and `dfbf265`

**3. [Rule 3 - Blocking] The TDD RED step cannot be its own commit**

- **Found during:** Tasks 1 and 2
- **Issue:** Both tasks are `tdd="true"`, and the canonical cycle wants a `test(...)` commit
  carrying a failing test. The pre-commit `mypy (strict)` hook rejects a test module importing a
  name no module exports (`Module "taskmanager.domain.validation" has no attribute
  "require_password"`, `"Task" has no attribute "assign"`), and `--no-verify` is forbidden by
  CLAUDE.md.
- **Fix:** RED was observed and captured to
  `.planning/phases/05-auth-assignment-notifications/evidence/05-01-tdd-red.txt` — the pytest
  output (`1 error during collection`, then `6 failed, 46 passed`) and the mypy output for both
  tasks — and each task shipped as a single green commit. This is the compromise plans 02-01 and
  04-02 recorded, applied for the same reason.
- **Files modified:** `.planning/.../evidence/05-01-tdd-red.txt`
- **Verification:** the capture is in the repository and is referenced from both commit messages
- **Committed in:** `ccf3b0a`, `5da085e`

---

**Total deviations:** 3 auto-fixed (2 × Rule 2, 1 × Rule 3)
**Impact on plan:** None on scope. Every artifact, behaviour and acceptance criterion the plan
specified was delivered; the three additions strengthen assertions the plan's own action text asked
for but whose behaviour block did not cover.

## Issues Encountered

- None beyond the RED-commit constraint recorded as deviation 3.

## Verification

| Gate | Command | Result |
|------|---------|--------|
| Lint | `make lint` | black: 141 files unchanged; isort clean; flake8 clean |
| Types | `make typecheck` | `Success: no issues found in 141 source files` |
| Architecture | `make arch` | `Contracts: 4 kept, 0 broken.` |
| Tests | `make test` | `659 passed`, `Required test coverage of 75% reached. Total coverage: 100.00%` (1199 statements, 0 missed) |
| No pragma | `grep -rn "pragma: no cover" src/taskmanager/` | 0 matches |
| Unit + arch | `pytest tests/unit tests/architecture -q --no-cov` | `464 passed` |
| Entity coverage | `pytest tests/unit/domain/test_task.py --cov=taskmanager.domain.entities.task` | `task.py` 72 stmts, 0 missed, 100% |
| Bounds not re-spelled | `ast` walk over `require_password` | no `8` and no `128` constant in the function body; `_refuse_nul` not among its calls |
| NUL accepted | `require_password('pass\\x00word12')` | returned unchanged |
| Mutator signatures | `inspect.signature(Task.assign/.unassign)` | `['self','assignee_id','now']` / `['self','now']`, `now` KEYWORD_ONLY |
| Mutator count | `grep -cE '^\s*def (assign\|unassign)\(' .../task.py` | `2` |
| Key floor | `grep -cE '^\s*jwt_secret:.*min_length=32'` / `...=16` | `1` / `0` |
| Key floor behaviour | `Settings(_env_file=None, jwt_secret='a'*31)` / `'a'*32` | refused naming `jwt_secret` / accepted |
| `.env.example` secret | `awk -F= '/^JWT_SECRET=/{print length($2)}'` | `34` (≥ 32) |
| `.env.example` guidance | `grep -c "secrets.token_urlsafe"` | `1` |

## User Setup Required

None — no external service configuration required. An operator whose existing `.env` carries a
JWT_SECRET between 16 and 31 characters will now fail at boot with a ValidationError naming the
field; every secret in the repository already clears the floor.

## Next Phase Readiness

The three preconditions the rest of the phase depends on are in place:

- **05-02 / 05-05 (registration, hashing)** can call `require_password` directly; the policy is
  already in the domain, so the schema must not re-spell either bound.
- **05-08 (AssignTask / UnassignTask)** has its domain mutation, and owns the same-assignee no-op
  that the entity deliberately does not carry.
- **05-06 / 05-07 (token service, authentication)** can mint and verify HS256 tokens without
  tripping `filterwarnings = error`, because no reachable secret is now shorter than 32 bytes.
- **05-16** is the last claimant of AUTH-04 and ASGN-02 and inherits both ticks untaken, plus the
  D-26 ADR the plan's own frontmatter already schedules there.
</content>
</invoke>
