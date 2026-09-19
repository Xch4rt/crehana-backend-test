---
phase: 05-auth-assignment-notifications
plan: 13
subsystem: integration-auth-http
tags: [integration, http, authentication, harness, fixtures, indistinguishability, enumeration, ordering, d-09, d-11, d-12, d-13, d-19, d-20, d-23, t-5-01, t-5-04, t-5-08, t-5-15]

# Dependency graph
requires:
  - phase: 05-auth-assignment-notifications
    provides: "get_current_actor over a real token decode plus D-11's confirmation read, and the security container on app.state (05-07, 05-10)"
  - phase: 05-auth-assignment-notifications
    provides: "POST /auth/register, POST /auth/login and GET /auth/me with their responses maps (05-11)"
  - phase: 05-auth-assignment-notifications
    provides: "GET /api/v1/users and UserSummaryResponse's three members (05-12)"
  - phase: 04-task-lists-tasks
    provides: "The integration harness: api_client, acting_as, statements, seed, and the two standards every HTTP test obeys"
  - phase: 02-domain-application-core
    provides: "The RFC 9457 error contract and tests/api/test_error_contract.py::MEMBERS / PROBLEM_JSON"
provides:
  - "authenticated_client: the harness that overrides get_uow and nothing else, so the real actor dependency runs"
  - "bearer_header(app, user_id): a token minted through the application's own token service"
  - "tests/integration/api/test_auth.py: seventeen tests covering AUTH-01, AUTH-02, AUTH-03, AUTH-04 and AUTH-05 over real HTTP"
  - "tests/integration/api/test_users.py: six tests covering ASGN-03 over real HTTP"
  - "A reusable UNAUTHENTICATED_CASES table of seven Authorization-header builders"
  - "routers/auth.py and routers/users.py back at 100% statement coverage"
affects: [05-14, 05-15, 05-16]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Two HTTP harnesses side by side: one that overrides the actor for speed, one that does not for truth, with the cost of each written in its own docstring"
    - "A token minted through the application's own object on app.state, so a test cannot restate a secret, an algorithm or a lifetime and drift from the app"
    - "A parametrized failure table plus a companion test that drives every row in one function and asserts the set of serialised bodies has exactly one member - the cross-case comparison a parametrized test structurally cannot make"
    - "An expired-token case produced by stopping the ISSUING clock, never by sleeping and never by a clock-rewriting library, because the verifying side reads the real time.time()"
    - "An ordering fixture arranged so that neither insertion order nor an order by id alone produces the expected answer, with a deliberate tie to exercise the second ORDER BY term"

key-files:
  created:
    - tests/integration/api/test_auth.py
    - tests/integration/api/test_users.py
    - .planning/phases/05-auth-assignment-notifications/evidence/05-13-tdd-red.txt
  modified:
    - tests/integration/conftest.py

key-decisions:
  - "The expired and foreign-secret tokens are built from Settings(_env_file=None) constructed inside the test, not from restated literals. authenticated_client monkeypatches the same two variables the application was built from, so an identical construction yields the identical secret, algorithm and lifetime - which is what makes each forgery differ from a valid token in exactly one property and nothing else"
  - "expires_in is asserted against configured_settings().jwt_expire_minutes * 60 rather than against 1800. A literal would assert that somebody typed the same number in two places; the derivation asserts the property SecurityResources exists for, which is that the number the client is told and the number the token was signed with come from one read"
  - "StoppedClock is declared in test_auth.py rather than imported from tests/unit/application/fakes.py. That module is the application layer's whole fake world - a unit of work, three repositories, a recording hasher - and importing it into an HTTP suite to borrow three lines would couple this file to every change made over there. Conformance to the Clock port is structural, so there is nothing to inherit"
  - "The seven-case table is asserted twice: once per case for shape (status, media type, challenge header, member list, code, detail, instance, token absence) and once across all seven for equality of the serialised bodies. The second is not redundant - each parameter runs in its own test, so a leak living in a member neither case names would satisfy every per-case assertion"
  - "The token-absence assertion is skipped for the two cases that carry no credential material (no header, an empty bearer parameter). The empty string is a substring of every document, so the assertion would pass without checking anything; the skip is conditional and commented rather than silently absent"
  - "test_users.py declares its own user builder with a created_at knob instead of widening test_task_lists.py::a_user. The timestamp is the property under test here and is read by nothing over there, so widening the sibling would add a parameter to ~120 tests that none of them uses - and test_task_lists.py is outside this plan's files"
  - "The plan's falsified-sentence rewrite was already done by 05-10: the grep for 'the seam answers with one fixed identifier' printed 0 before this plan touched anything. acting_as's docstring was extended anyway with the half that was still missing - that it impersonates rather than authenticates, and that combining it with authenticated_client is a contradiction rather than a convenience"
  - "No requirement tick taken. AUTH-01..05 and ASGN-03 are in this plan's frontmatter and 05-16 is the last claimant under the project's standing convention; the fourteenth consecutive Phase 5 plan to make the same call"

patterns-established:
  - "A second HTTP harness whose docstring states what the first one cannot measure, so the choice between them is a decision a reader makes rather than a habit"
  - "A helper that reads a composition-root container off app.state, narrowed once, so tests mint credentials with the application's own configuration"
  - "Per-case shape assertions plus one cross-case body comparison, for any claim of the form 'these N failures are one answer'"

requirements-completed: []

# Metrics
duration: 11min
completed: 2026-09-19
---

# Phase 5 Plan 13: The Auth Surface over Real HTTP Summary

`authenticated_client` is the harness that actually authenticates - it overrides `get_uow` and
nothing else - and twenty-three tests spend it on the five AUTH requirements and the user
directory, proving over real HTTP and real PostgreSQL that seven distinct token failures are
one indistinguishable 401 and that a wrong password answers exactly like an unknown address.

## Performance

- **Duration:** ~11 min
- **Started:** 2026-09-19T17:21Z
- **Completed:** 2026-09-19T17:33Z
- **Tasks:** 3 of 3
- **Files modified:** 4 (3 created, 1 modified)

## Accomplishments

- **A harness that reaches the decode, beside the one that does not.** `authenticated_client`
  is `api_client` verbatim minus one line - the actor override - and its docstring states the
  split, what the other fixture therefore cannot measure (the 401 legs, the anonymous column
  of the D-04 matrix, the statement counts), and what it costs: every test using it must seed
  its own caller, because the real dependency confirms the row on every request. That cost is
  the property under test, not a setup tax.
- **`bearer_header` mints through the application's own token service.**
  `grep -c "JwtTokenService" tests/integration/conftest.py` prints `0`. The helper narrows
  `app.state.security` once - the narrowing `dependencies.py` argues in full - and issues the
  token through the very object the actor dependency will decode with, so the secret and the
  algorithm cannot drift from a second copy written in a test module.
- **The seven ways a token fails are one parametrized test with a named case per row**:
  `no_header`, `a_basic_scheme`, `an_empty_bearer_parameter`, `garbage`,
  `a_foreign_secret_token`, `an_expired_token`, `a_token_for_an_unknown_subject`. A case
  nobody wrote is a missing row in a visible table rather than an absence in a file.
- **And an eighth test drives all seven in one function and asserts the set of serialised
  bodies has exactly one member.** That is the assertion a parametrized test structurally
  cannot make, and it is the one that would catch a leak living in a member no per-case
  assertion happens to name. The failure message carries the per-case bodies, so a regression
  says which two answers diverged.
- **The expired token needed no `freezegun` and no sleeping.**
  `grep -cE "freezegun|sleep\("` prints `0`. PyJWT compares `exp` against the real
  `time.time()`, so only the issuing side is controllable: a real `SecurityResources` built
  from the real settings and a clock stopped two hours ago mints a token that expired ninety
  minutes before the request. Everything about it is the application's own except the instant.
- **D-12 is asserted body to body, not by status.** Both login failures were always going to
  be 401; the comparison is over the serialised documents through `anonymised`, so a
  difference in `code`, in `title`, in `detail` or in the presence of an `errors` member
  fails - and each of those is an account-enumeration oracle a status assertion would let
  through.
- **D-23's bound on the 409 is a test.** Registering `Ana@X.com` and then `ana@x.com` is a
  409 `email_already_registered` carrying `{"field": "email"}` and **neither spelling of the
  address anywhere in the document**. The conflict is the accepted oracle AUTH-01 requires;
  repeating the value back would not be.
- **Every 2xx asserts the member list in declaration order.** `list(body) == ["id", "email",
  "full_name", "created_at"]` on register and on `/auth/me`, and
  `["id", "full_name", "email"]` per directory entry - which a renamed `password_hash` field
  could not pass, where `"password_hash" not in body` would (T-5-08).
- **Register is proven by a re-read, not by its own 201.** One test registers, logs in with
  the new credential, reads `/auth/me` with the returned token and asserts the profile is
  byte-equal to what register answered. A handler that answered a perfect 201 and rolled its
  transaction back passes the shape test and fails this one.
- **ASGN-03's ordering is now pinned at three levels, and the module says so.** The three
  directory rows are arranged so that insertion order is wrong, an order by id alone is wrong,
  and two rows tie on `created_at` so the `id` tie-break is exercised against real PostgreSQL.
  The docstring names the unit test and the repository test that pin the same promise and
  explains why none of the three is redundant - so a reader does not delete one as a
  duplicate.
- **`routers/auth.py` and `routers/users.py` are back at 100%.** The fifteen uncovered
  statements this plan inherited are down to six, and all six are
  `routers/assignments.py` 144-147, 201-204 and 249-252 - which belong to 05-14. Total
  coverage **99.66%**, with no `pragma: no cover` and no `omit`.

## Task Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | `authenticated_client` - the harness that really authenticates | `2010592` | `tests/integration/conftest.py`, `evidence/05-13-tdd-red.txt` |
| 2 | `test_auth.py` - register, login, me, and the five ways a token fails | `fea0fc0` | `tests/integration/api/test_auth.py` |
| 3 | `test_users.py` - the directory over HTTP | `bf480a5` | `tests/integration/api/test_users.py` |

## Files Created/Modified

**Created**

- `tests/integration/api/test_auth.py` - seventeen tests: five on register, four touching
  login, two on `/auth/me`, the seven-case unauthenticated table and its cross-case
  comparison. Plus `a_registration`, `a_login_form`, `configured_settings`, `StoppedClock`,
  the seven header builders and `UNAUTHENTICATED_CASES`.
- `tests/integration/api/test_users.py` - six tests: the bare array, the three members in
  declaration order, nothing leaking into the serialised document, the total order, the
  directory being a directory rather than a self-view, and the anonymous 401. Plus a local
  `a_user` with a `created_at` knob and `the_caller`.
- `.planning/phases/05-auth-assignment-notifications/evidence/05-13-tdd-red.txt` - two red
  captures (the helper absent, then the fixture absent) and the green that followed, taken
  through a throwaway probe module that was deleted before the commit.

**Modified**

- `tests/integration/conftest.py` - the `authenticated_client` fixture, the `bearer_header`
  helper, the `SecurityResources` import and the `cast` it needs, and a fourth paragraph on
  `acting_as` recording that it impersonates rather than authenticates.

## Decisions Made

See `key-decisions` in the frontmatter. The two worth reading first are the settings-derived
forgeries (which is what makes each forged token differ from a valid one in exactly one
property) and the doubled assertion over the seven-case table (per-case shape plus cross-case
body equality).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug in the plan's test data] `example.test` is refused by `EmailStr`**

- **Found during:** Task 2
- **Issue:** The integration suite's existing address convention is `demo@example.test`, which
  works everywhere it is used because those addresses reach the `User` entity directly and the
  entity validates no format (Phase 2 D-04). `RegisterRequest.email` is an `EmailStr`, and
  `email-validator` refuses `.test` outright: *"The part after the @-sign is a special-use or
  reserved name that cannot be used with email."* Six tests failed with a 422 where a 201 was
  expected, and - more insidiously - the short-password test failed *green-looking*, because
  the request-validation 422 it got has the same status as the domain 422 it was asserting and
  differs only in the shape of `errors`.
- **Fix:** the registering addresses moved to `example.com`, which `email-validator` accepts
  (verified directly against the validator, along with `.local`, which it also refuses). The
  duplicate-email pair keeps the plan's own `Ana@X.com` / `ana@x.com`. The seeded-entity
  addresses elsewhere in the suite are untouched - they never cross an `EmailStr` boundary.
- **Files modified:** `tests/integration/api/test_auth.py`
- **Commit:** `fea0fc0`

**2. [Rule 3 - Blocking] Two over-long docstring lines failed `make lint`**

- **Found during:** Task 3
- **Issue:** The module docstring named the two sibling tests as
  `path::test_name`, which is 91 and 102 characters - over the 88-column bound.
- **Fix:** each reference split into a file line and a test-name line. No `noqa`, and the
  reference is still exact.
- **Files modified:** `tests/integration/api/test_users.py`
- **Commit:** `bf480a5`

### Deviations Recorded, Not Fixed

**3. The plan's falsified-sentence rewrite was already done.**
`grep -c "the seam answers with one fixed identifier" tests/integration/conftest.py` printed
`0` before this plan touched the file: plan 05-10 had already rewritten that half of
`acting_as`'s docstring when it replaced the seam's body. The acceptance criterion was
therefore met on arrival. The half that was genuinely still missing - that `acting_as`
impersonates rather than authenticates, and that combining it with `authenticated_client` is a
contradiction rather than a convenience - was written in this commit, which is what the plan's
`<action>` was actually asking for.

**4. Task 1's red was captured through a throwaway module rather than a committed test.**
Task 1's `<files>` list is `tests/integration/conftest.py` alone, and the fixture's behaviour
(`a minted header reaches a handler`, `no header is refused`) belongs to Tasks 2 and 3. A
temporary `tests/integration/api/test_harness_probe.py` was written, observed red twice - once
for the absent helper, once for the absent fixture, with the fixture list pytest prints -
observed green after the fixture existed, and then deleted. Both captures and the green are in
`evidence/05-13-tdd-red.txt`, which states that the module is not in the commit and why. This
is the same compromise 02-01 recorded for a different reason.

**5. Seventeen tests in `test_auth.py`, not fifteen.**
The floor the plan sets is "at least 15 collected". The extra two are the eighth
unauthenticated test (the cross-case body comparison, argued above) and the separate register
round-trip test, which the plan's `<action>` asks for as a property of the register tests
rather than as a test of its own; splitting it keeps the shape assertions and the durability
assertion from failing as one.

## Threat Flags

None. This plan adds no production code, no route, no dependency and no package install; it
adds only tests over surface plans 05-11 and 05-12 already published. `T-5-SC` is satisfied
literally - no `pip install` ran, and `grep -cE "freezegun|sleep\("` prints `0`.

## Verification

All four gates green, in one pass, with the `db` container running.

| Gate | Result |
|------|--------|
| `make lint` | pass - black 178 files unchanged, isort clean, flake8 silent |
| `make typecheck` | pass - `Success: no issues found in 178 source files` |
| `make arch` | pass - `Contracts: 4 kept, 0 broken.` |
| `make test` | pass - **893 passed in 6.10s**, `Required test coverage of 75% reached. Total coverage: 99.66%` |

- `grep -rn "pragma: no cover" src/taskmanager/` prints nothing.
- Uncovered statements: **6**, all in `src/taskmanager/presentation/api/routers/assignments.py`
  (144-147, 201-204, 249-252). Plan 05-14 owns them. `routers/auth.py` (32 statements) and
  `routers/users.py` (16 statements) are both at 100%, down from the 15 uncovered statements
  this plan inherited.
- `-k` selectors, all exiting 0: `register` 5, `duplicate` 1, `login` 4, `indistinguishable`
  1, `unauthenticated` 8, `expired` 1, `_me` 2, and `order` 2 in `test_users.py`.
- Grep gates: `authenticated_client` 3, `get_current_actor` 8, `JwtTokenService` 0, the
  falsified sentence 0, `application/problem+json` literal 0, `PROBLEM_JSON` 7 in
  `test_auth.py` and 2 in `test_users.py`, `freezegun|sleep(` 0, `WWW-Authenticate` 3,
  `password_hash` 2 in `test_users.py`.

## What the Next Plans Need to Know

- **`test_statements.py` is still measured through `api_client`, and is therefore still
  reading the override path.** That is 05-14's to re-measure: D-20 records that ADR-054's
  counts of 1 and 3 become 2 and 4 once the real actor runs, and `authenticated_client` plus
  `bearer_header` are now available for exactly that. A test that switches fixture must seed
  the caller's `users` row and clear the `statements` recorder *after* seeding, because `seed`
  commits on the same connection.
- **`UNAUTHENTICATED_CASES` and the seven header builders are importable** from
  `tests/integration/api/test_auth.py`, as are `PROFILE_MEMBERS`, `ME`, `LOGIN`, `REGISTER`
  and `configured_settings`. 05-15's permission matrix needs an anonymous column; reusing the
  table is cheaper than re-deriving it, and `test_statements.py` already sets the precedent of
  importing from a sibling HTTP module.
- **`ASSIGNEE_ID` (...0003) and `STRANGER_ID` (...0004) are taken**, in
  `tests/integration/api/test_users.py`. The next Phase 5 module that needs a new person
  continues from ...0005 and must not reuse a Phase 4 number.
- **Addresses that cross an `EmailStr` boundary must use a real TLD.** `example.test` and
  anything `.local` are refused by `email-validator` before any handler runs. The existing
  `demo@example.test` constants are safe only because they are seeded as entities.
- **The 409 on register is the one accepted enumeration oracle in this API**, bounded by a
  test that its body names no address. 05-16's ADR owes the record; it must be written as
  *accepted*, never as mitigated (D-23, T-5-06).
- **Coverage stands at 99.66% with 6 uncovered statements.** The threshold is untouched at
  75%, and nothing was excused with a pragma or an omit.

## Self-Check: PASSED

- `tests/integration/conftest.py` - FOUND
- `tests/integration/api/test_auth.py` - FOUND
- `tests/integration/api/test_users.py` - FOUND
- `.planning/phases/05-auth-assignment-notifications/evidence/05-13-tdd-red.txt` - FOUND
- `2010592` - FOUND
- `fea0fc0` - FOUND
- `bf480a5` - FOUND
