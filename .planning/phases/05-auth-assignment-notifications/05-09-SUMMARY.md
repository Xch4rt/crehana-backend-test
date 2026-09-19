---
phase: 05-auth-assignment-notifications
plan: 09
subsystem: presentation-schemas
tags: [pydantic, boundary, secretstr, mass-assignment, extra-forbid, asgn-03, d-05, d-06, d-08, t-5-09, t-5-10]

# Dependency graph
requires:
  - phase: 05-auth-assignment-notifications
    provides: "RegisterUserCommand, LoginCommand, UserResult and AccessTokenResult (05-07)"
  - phase: 05-auth-assignment-notifications
    provides: "AssignTaskCommand, and the test that keeps it the only command naming an assignee (05-08)"
  - phase: 04-task-lists-tasks
    provides: "schemas/tasks.py and schemas/task_lists.py - the boundary rules, the field-by-field from_result, and the AST gate this plan grows"
provides:
  - "RegisterRequest: the open register boundary, extra-forbidden, with the credential typed as a secret and unwrapped exactly once"
  - "UserResponse and TokenResponse: the profile and the login answer, copied field by field, neither declaring the stored hash"
  - "UserSummaryResponse: ASGN-03's three members in ASGN-03's order, a second model rather than a reuse of the profile"
  - "TaskAssigneeRequest: one required assignee_id beside TaskStatusChangeRequest, with the body-less DELETE noted where a reader would look for it"
  - "REQUIRED_SCANNED_MODULES naming both new modules, each added in the commit that created it"
  - "A parametrized table of the keys an existing task door must refuse by having no field for them, driven red by hand before being trusted"
affects: [05-11, 05-12, 05-13, 05-14, 05-15, 05-16]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A credential typed as SecretStr at the boundary and unwrapped by exactly one call in to_command, with the test asserting the runtime type of the command field rather than its annotation"
    - "Two response models over one result DTO, deliberately not sharing a base, because their member lists are two different contracts"
    - "Proof by absence as a parametrized table of (model, key) rows, falsified by planting the field and observing the rows go red"

key-files:
  created:
    - src/taskmanager/presentation/api/schemas/auth.py
    - src/taskmanager/presentation/api/schemas/users.py
    - .planning/phases/05-auth-assignment-notifications/evidence/05-09-tdd-red.txt
    - .planning/phases/05-auth-assignment-notifications/evidence/05-09-absence-falsification.txt
  modified:
    - src/taskmanager/presentation/api/schemas/tasks.py
    - tests/unit/presentation/test_schemas.py
    - tests/architecture/test_routers_raise_no_http_exception.py

key-decisions:
  - "Each new schema module joined REQUIRED_SCANNED_MODULES in the commit that CREATED it, not in the plan's Task 3. RESEARCH Pitfall 14 states the rule that way and this plan's own must_haves repeat it; the plan's task split would have produced two commits in which a presentation module was scanned by luck rather than by assertion. Every acceptance criterion of Task 3 still passes literally - both names appear exactly once, and no router that does not yet exist appears at all"
  - "The Pitfall 7 test asserts `type(command.password) is str`, not the annotation. RegisterUserCommand is a frozen dataclass with no runtime validation and `.importlinter` deliberately leaves pydantic off the application layer's forbidden list, so forwarding the wrapper would break no contract, no type check and no gate. That one assertion is the entire enforcement, and to_command's docstring says so"
  - "UserSummaryResponse is a second model rather than a reuse of UserResponse, and the member lists differing is the point: ASGN-03 asks for id, name, email in that order and the directory publishes no created_at, so a shared model would move the directory's contract every time the profile's moved"
  - "The three proven-by-absence refusals are one parametrized table rather than three functions, and they were falsified rather than assumed: both task request models were given an `assignee_id` field by hand and the two new rows went red (evidence/05-09-absence-falsification.txt). An absence assertion that has never been driven red is indistinguishable from one asserting nothing"
  - "Response member lists are asserted on the serialised body (`list(model_dump())`) as well as on the class, because the body is what a client reads. A per-key `\"password_hash\" not in body` check would pass against a body that had renamed the field, which is the argument the integration suite already writes out for its own member-order contract (T-5-08)"
  - "The boundary declares no length bound of any kind: `grep -cE 'min_length|max_length'` over schemas/auth.py prints 0, prose included, so the comment arguing the omission had to be worded around both words - the repo's convention of rewording prose to meet a counter rather than changing code to satisfy one (01-03, 04-05, 05-08)"
  - "No requirement tick taken. AUTH-01, AUTH-02, AUTH-05, ASGN-01, ASGN-02 and ASGN-03 are all in this plan's frontmatter and 05-16 is the last claimant; a schema with no route above it proves no requirement. The twelfth consecutive Phase 5 plan to make the same call"

patterns-established:
  - "A new module under presentation/api names itself in the AST gate's frozenset in its own creating commit - never in a later tidy-up task"
  - "An absence assertion ships with the capture of it failing against a planted field"

requirements-completed: []

# Metrics
duration: 21min
completed: 2026-09-19
---

# Phase 5 Plan 09: The Auth, Users and Assignee Schemas Summary

Every HTTP boundary this phase opens is now typed, and the two things those boundaries must
refuse are refused by having no field for them - proven by a table that was driven red before
it was trusted.

## What Was Built

**`schemas/auth.py`** — `RegisterRequest` (`extra="forbid"`, `email: EmailStr`,
`full_name: str`, `password: SecretStr`) with a `to_command()` that takes no `actor_id`,
because this is the operation that creates an identity; `UserResponse` (`id`, `email`,
`full_name`, `created_at`) and `TokenResponse` (`access_token`, `token_type`, `expires_in`),
both copied field by field from their result DTOs. The module carries the two comments the
plan required: no length bound on either string, because the 8-to-128 rule is
`domain/validation.py`'s and the display name's cap is the `User` entity's (Phase 2 D-04,
CONTEXT D-10); and `EmailStr` and `User.__post_init__` are complementary rather than
duplicated, since `EmailStr` normalises the domain half only (`Ana@Example.COM` →
`Ana@example.com`) while the entity lower-cases the whole address, which is the form
`uq_users_email_lower` and `get_by_email` rely on.

**`schemas/users.py`** — `UserSummaryResponse`, exactly `id`, `full_name`, `email`, in
ASGN-03's own order, with `created_at` named in prose as the member the directory was not
asked for.

**`TaskAssigneeRequest`** — one required `assignee_id: UUID`, `extra="forbid"`, living in
`schemas/tasks.py` beside `TaskStatusChangeRequest` because D-05 makes the two the same kind
of door. Its `to_command` binds all four identifiers, and its docstring records that the
`DELETE` on the same URL takes no body and therefore has no model.

**The gate and the refusals** — `REQUIRED_SCANNED_MODULES` now names `schemas/auth.py` and
`schemas/users.py` (and no router that does not exist yet), and one parametrized table
asserts that `assignee_id` on task create (D-06), `assignee_id` on the generic patch (T-5-10)
and `status` on the generic patch (D-08) are each exactly one `extra_forbidden` error at the
key.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 — missing critical functionality] The gate entries moved into the creating commits**

- **Found during:** Task 1
- **Issue:** The plan defers both `REQUIRED_SCANNED_MODULES` entries to Task 3, while
  RESEARCH Pitfall 14 — and this plan's own `must_haves` — require a new presentation module
  to join the frozenset **in the same commit that creates it**. Following the task split
  literally would have produced two commits in which a new module under `presentation/api`
  was scanned incidentally with nothing asserting that it must be.
- **Fix:** `"schemas/auth.py"` was added in Task 1's commit and `"schemas/users.py"` in Task
  2's. Task 3 then shipped the three absence assertions alone.
- **Files modified:** `tests/architecture/test_routers_raise_no_http_exception.py`
- **Commits:** `e61cdb4`, `bf7ddb1`
- **Effect on acceptance:** none. Task 3's four grep criteria still pass literally —
  `schemas/auth.py` 1, `schemas/users.py` 1, router entries 0 — and the architecture suite is
  green.

**2. [Rule 2 — missing critical functionality] The absence assertions were falsified**

- **Found during:** Task 3
- **Issue:** Task 3 is marked `tdd="true"`, but its three assertions are about models that
  already behave correctly, so there is no RED step to observe. An absence assertion nobody
  has ever seen fail is indistinguishable from one that asserts nothing — the argument this
  repo makes for every other gate it ships (02-06, 03-08, 03-09).
- **Fix:** Both task request models were given an `assignee_id` field by hand, the suite was
  re-run, and the two new rows failed with `DID NOT RAISE ValidationError`. The plant was
  reverted with `git checkout --` on that one file.
- **Files modified:** none permanently; capture in
  `.planning/phases/05-auth-assignment-notifications/evidence/05-09-absence-falsification.txt`
- **Commit:** `3dc5494`

### Notes, not deviations

- Tasks 1 and 2 followed the repo's established TDD compromise: the tests were written and
  observed failing (`ModuleNotFoundError`, then `ImportError: cannot import name
  'TaskAssigneeRequest'`) and the run appended to
  `evidence/05-09-tdd-red.txt`, because the `mypy (strict)` pre-commit hook rejects a commit
  whose tests import a name no module exports and `--no-verify` is forbidden (the 02-01
  precedent).
- The pre-commit `trailing-whitespace` hook stripped trailing spaces from the captured pytest
  output in the falsification evidence file. The content is otherwise verbatim and the commit
  message records the edit.
- `.planning/STATE.md` and `.planning/ROADMAP.md` were updated by hand, in their existing
  conventions, rather than through the SDK state handlers — the regressions those handlers
  introduce (a phase-based `percent`, a reset `Status` line, a blanked ROADMAP progress row)
  are recorded in the executor handover for this phase.

## Threat Model Outcomes

| Threat ID | Disposition | Where it is now enforced |
|-----------|-------------|--------------------------|
| T-5-09 | mitigated | `test_the_register_request_refuses_an_unknown_key` — exactly one `extra_forbidden` at the offending key; the command has three fields and no `id`, `created_at` or role |
| T-5-10 | mitigated | `test_an_existing_task_door_refuses_a_key_it_declares_no_field_for[create-assignee_id, patch-assignee_id]`, falsified by planting the field |
| T-5-04 | mitigated | `test_the_register_request_masks_the_password_wherever_pydantic_prints_it` over `repr`, `str()`, `model_dump()` and `model_dump_json()`; unwrapped by one call in `to_command` |
| T-5-08 | mitigated | `UserResponse` and `UserSummaryResponse` member lists asserted in declaration order, on the class and on the serialised body |
| ADR-051 | mitigated | Both new modules in `REQUIRED_SCANNED_MODULES`, each in its creating commit |
| T-5-SC | accepted | No package installed |

## Verification

| Gate | Result |
|------|--------|
| `.venv/bin/pytest tests/unit tests/architecture -q --no-cov` | 656 passed |
| `make lint` (black, isort, flake8) | exit 0 |
| `make typecheck` (`mypy src tests`) | Success, 172 source files |
| `make arch` | `Contracts: 4 kept, 0 broken` |
| `make test` | **858 passed**, total coverage **100.00%** (1524 statements, 146 branches, 0 missed) |
| `grep -rn "pragma: no cover" src/taskmanager/` | no matches |
| `tests/unit/presentation/test_schemas.py` | 49 → 67 tests (+18; Task 1 added 9, the plan asked for at least 7) |

## Commits

| Task | Commit | Subject |
|------|--------|---------|
| 1 | `e61cdb4` | `feat(05-09): the register boundary, typed and masked (AUTH-01, AUTH-02, AUTH-05)` |
| 2 | `bf7ddb1` | `feat(05-09): the assignment body and the ASGN-03 directory entry (ASGN-01, ASGN-03)` |
| 3 | `3dc5494` | `test(05-09): the two keys an existing task door must never accept (D-06, D-08)` |

## What the Next Plans Need

- **05-11 (`routers/auth.py`)** — `RegisterRequest.to_command()` takes **no** arguments; the
  route passes nothing. `UserResponse.from_result` and `TokenResponse.from_result` are the two
  response mappers. Login has no Pydantic request model here by design: it reads the OAuth2
  form. The router's own module must be added to `REQUIRED_SCANNED_MODULES` in the commit that
  creates it.
- **05-12 (`routers/users.py`, `routers/assignments.py`)** — `UserSummaryResponse.from_result`
  is the directory mapper; `TaskAssigneeRequest.to_command(actor_id=, task_list_id=, task_id=)`
  is the assignment body's. The unassign `DELETE` has no body and no model. Same frozenset
  rule for both router modules.
- **05-13/05-14** — the register 422 legs are already unit-asserted here; the HTTP tests owe
  the *status code* and the problem+json shape, not the refusal itself.
- Nothing in this plan changed a use case, a port or a query, so the ADR-054 statement counts
  are untouched by it.

## Self-Check: PASSED

- `src/taskmanager/presentation/api/schemas/auth.py` — FOUND
- `src/taskmanager/presentation/api/schemas/users.py` — FOUND
- `.planning/phases/05-auth-assignment-notifications/evidence/05-09-tdd-red.txt` — FOUND
- `.planning/phases/05-auth-assignment-notifications/evidence/05-09-absence-falsification.txt` — FOUND
- commits `e61cdb4`, `bf7ddb1`, `3dc5494` — all FOUND in `git log`
