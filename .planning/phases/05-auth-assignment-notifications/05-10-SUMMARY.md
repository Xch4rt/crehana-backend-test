---
phase: 05-auth-assignment-notifications
plan: 10
subsystem: presentation-authentication-seam
tags: [auth, bearer-token, oauth2passwordbearer, composition-root, app-state, dependency-injection, d-11, d-14, d-20, d-27, adr-044, adr-045, adr-051]

# Dependency graph
requires:
  - phase: 05-auth-assignment-notifications
    provides: "create_security_resources(settings, clock) and the frozen SecurityResources container, port-annotated (05-05)"
  - phase: 05-auth-assignment-notifications
    provides: "LoggingEmailNotifier, the stateless EmailNotifier adapter (05-06)"
  - phase: 05-auth-assignment-notifications
    provides: "AuthenticateActor and AuthenticationError.REFUSAL, the single 401 message (05-07)"
  - phase: 04-task-lists-tasks
    provides: "The Phase 4 actor seam, CurrentActor, and the HTTP harness with acting_as"
  - phase: 03-persistence-runnable-stack
    provides: "DatabaseResources, the one-narrowing dependencies.py, and docker/entrypoint.sh"
provides:
  - "get_current_actor: a real bearer-token decode plus D-11's per-request row confirmation"
  - "get_password_hasher, get_token_service and get_email_notifier, each returning its port"
  - "PasswordHasherDependency, TokenServiceDependency and EmailNotifierDependency"
  - "app.state.security: the second typed container, built once by create_app"
  - "An entrypoint back to wait -> migrate -> serve, and a stack that ships with zero users"
  - "api_client's default actor override (OWNER_ID), which keeps the ~120 Phase 4 tests about their own subject"
affects: [05-09, 05-11, 05-12, 05-13, 05-14, 05-15, 05-16]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Two private narrowings of app.state, one per typed container, both in dependencies.py - the property counted per container rather than per module"
    - "A security dependency that raises a DomainError and never the web framework's exception class, by configuring the bearer scheme not to refuse anything itself"
    - "A test harness that supplies the caller explicitly, with the cost of the split named in the fixture docstring and a second fixture owed for the legs it cannot reach"
    - "A source-scan gate inverted rather than deleted when the property it pinned became false: the module names no library and no signing scheme, replacing the assertion that it said it was not authentication"

key-files:
  created:
    - .planning/phases/05-auth-assignment-notifications/evidence/05-10-actor-seam.txt
    - .planning/phases/05-auth-assignment-notifications/evidence/05-10-tdd-red.txt
  modified:
    - src/taskmanager/presentation/api/actor.py
    - src/taskmanager/presentation/api/dependencies.py
    - src/taskmanager/main.py
    - docker/entrypoint.sh
    - tests/unit/test_app_factory.py
    - tests/unit/presentation/test_actor.py
    - tests/integration/conftest.py
    - tests/integration/api/test_task_lists.py

key-decisions:
  - "OWNER_ID lives in tests/integration/conftest.py and test_task_lists.py imports it, against the plan's 'module-local' wording. The fixture that installs the override and the row the tests seed have to be one value; two copies in two modules agree only until one is edited, and nothing would notice. The 04-09 precedent (PROBLEM_JSON imported rather than re-declared) applied to an identifier the harness owns"
  - "The deleted honesty test is replaced by a name scan, and the scanned list is implementation names rather than English words. The first draft forbade 'algorithm' and 'secret', which would have made the new docstring unwritable - the plan's own text requires it to say the algorithm is named nowhere. The tuple is now the two credential libraries, the token format and two signing schemes, which is what a hand-rolled decode would actually have to spell"
  - "actor.py never spells the token format, because the gate above scans for it. The seam says 'bearer token' throughout, which is also the more accurate statement: the format is the adapter's business and this layer cannot name it without pinning it"
  - "Three grep counters were met by rewording prose rather than by changing code - auto_error=False printed 3, the deleted step's label printed 1, and both were prose mentions. The 01-03 prose-not-literal convention, applied for the fourth phase running"
  - "The refusal legs are driven over HTTP in a unit test, not by calling the provider with None. Three of the four header shapes differ only in FastAPI's own parse ('no header' and 'Basic zzz' both arrive as None, 'Bearer ' arrives as ''), so calling the function with a value the test invented would prove nothing about the value the code receives - and the lowercase-scheme leg could not be expressed at all"
  - "The four header shapes are asserted to produce one byte-identical body, and the deleted-user leg is compared to the junk-token leg field by field. A 401 per leg would pass against an implementation whose two bodies differ, which is T-5-04's oracle in a different coat"
  - "Nothing was added to the lifespan. The security container owns no pool, no file and no socket, so it has nothing to release; the startup half stays empty (D-06) and the HTTP harness never enters the lifespan at all (ADR-056), so anything placed there would be untested by every test that drives the application over HTTP"
  - "No requirement tick taken. AUTH-03, AUTH-05 and AUTH-06 are in this plan's frontmatter and 05-16 is the last claimant; AUTH-05 has no route until 05-11 and AUTH-06's 403 cannot be produced over HTTP until 05-12. The eleventh consecutive Phase 5 plan to make the same call"

patterns-established:
  - "One narrowing per typed container, not one per module: the docstring argues why fusing the containers would couple every unit test of one half to the other"
  - "A dependency that must be overridable takes its collaborators as Depends parameters, with the consequence of the direct call written where the temptation is"
  - "An evidence file that records a blast radius before and after, the before reproduced from the commit the plan started at rather than remembered"

requirements-completed: []

# Metrics
duration: 14min
completed: 2026-09-19
---

# Phase 5 Plan 10: The Real Actor Seam Summary

Every endpoint in the project now costs a valid bearer token and a live user row; the demo
identity is gone from the code, the tests and the container, and the module that used to
insist it was not authentication now is.

## Performance

- **Duration:** ~14 min
- **Started:** 2026-09-19T16:28Z
- **Completed:** 2026-09-19T16:42Z
- **Tasks:** 3 of 3
- **Files modified:** 10 (2 created, 8 modified)

## Accomplishments

- **`get_current_actor` decodes and then confirms, and every failure mode is one 401.** No
  header, a `Basic` scheme, a bearer scheme with an empty parameter, a junk token and a
  perfectly valid token whose subject has no row all produce the same status, the same
  `application/problem+json` body, the same `WWW-Authenticate: Bearer` challenge and the same
  `detail`. Four of those five are captured live in
  `evidence/05-10-actor-seam.txt`, through `create_app`'s real application and the project's
  own handler stack; the fifth is compared field by field against the junk-token body in
  `tests/unit/presentation/test_actor.py`.
- **The AST gate stayed green without losing Swagger's Authorize button.** The bearer scheme is
  configured not to raise the web framework's own exception class, so `presentation/api`
  still neither raises nor imports it (ADR-051, WR-05) — and because the scheme is still a
  `Depends`, `components.securitySchemes.OAuth2PasswordBearer` and a per-route
  `security: [{"OAuth2PasswordBearer": []}]` are emitted *through the nested dependency*, with
  nothing repeated per route. A hand-rolled header parse would have satisfied the gate and lost
  the second half.
- **`CurrentActor` kept its name, its `UUID` type and its target function.** Not one router,
  request schema, command or use-case signature moved because authentication arrived — ADR-044
  paying out. The clearest evidence is that
  `test_current_actor_depends_on_this_module_s_provider` survived the rewrite verbatim.
- **The demo identity is gone from four files and from the container.** `DEMO_USER_ID`, the
  entrypoint's seed step and the four tests that asserted on the constant are deleted together;
  `grep -rn DEMO_USER_ID src/ tests/ docker/` now exits 1. The entrypoint is back to three
  steps — wait, migrate, serve — and a fresh volume ships **zero** users, so no account and no
  password exists anywhere in the repository (T-5-03, D-14, ADR-045).
- **The security adapters reach a request through the same typed path the database already
  used.** `create_app` builds `SecurityResources` once and stores it beside `DatabaseResources`;
  `dependencies.py` narrows it in one private helper and hands out three port-annotated
  providers. `grep -c "get_settings"` on that module prints `0`, so no provider reads
  configuration per request (RC-3), and the hasher's ~37 ms cached dummy hash is paid once per
  application rather than once per login (D-27).
- **The harness supplies its caller explicitly, and says what that costs.** `api_client` now
  installs a default `get_current_actor` override, so the ~120 Phase 4 tests keep testing task
  lists rather than tokens — and the fixture docstring states plainly that a request through it
  never reaches the decode, which is why 05-13's `authenticated_client` must own the 401 legs,
  the matrix's anonymous column and `test_statements.py`.

## Task Commits

1. **Task 1: The three security providers and the second `app.state` container** — `41a2533` (feat)
2. **Task 2: Move the HTTP harness onto an explicit actor override** — `1c2b0d6` (test)
3. **Task 3: The real actor seam, and the demo user's deletion** — `4d6e128` (feat)

TDD RED for tasks 1 and 3 is captured in
`evidence/05-10-tdd-red.txt` rather than committed: the pre-commit `mypy (strict)` hook rejects
a test module importing a name no module exports yet, and `--no-verify` is forbidden. The same
compromise 02-01, 04-02 and every earlier Phase 5 plan recorded.

## Files Created/Modified

- `src/taskmanager/presentation/api/actor.py` — the seam rewritten: the bearer scheme, the
  falsy-token guard covering both `None` and `""`, and the delegation to `AuthenticateActor`.
  `DEMO_USER_ID` and all four now-false docstring passages are gone.
- `src/taskmanager/presentation/api/dependencies.py` — `_security`, the three providers, the
  three aliases, and a docstring that argues two narrowings instead of claiming one.
- `src/taskmanager/main.py` — `create_security_resources(resolved, SystemClock())` and
  `app.state.security`, beside the database container and before the `register_*` block.
- `docker/entrypoint.sh` — the seed step deleted in full (94 lines); the header's step list is
  1 / 2 / 3 again and records the deletion as the contract the old numbering promised.
- `tests/unit/presentation/test_actor.py` — rewritten: four `DEMO_USER_ID` tests and the
  "not authentication" assertion deleted, seven tests of the decode path added, the alias
  introspection test and the two `get_clock` tests kept.
- `tests/unit/test_app_factory.py` — six new cases covering the container, the three providers,
  their port annotations and the no-connection promise.
- `tests/integration/conftest.py` — `OWNER_ID`, the default actor override, and the fixture and
  `acting_as` docstrings rewritten around D-20.
- `tests/integration/api/test_task_lists.py` — `DEMO_USER_ID` replaced by the imported
  `OWNER_ID`; `a_user`'s docstring no longer points at a seed that does not exist.
- `.planning/.../evidence/05-10-actor-seam.txt` — the blast radius before and after, the four
  live 401s, the published security scheme, and the script that produced them.
- `.planning/.../evidence/05-10-tdd-red.txt` — both RED runs.

## Decisions Made

See `key-decisions` in the frontmatter. The two worth repeating here:

- **`OWNER_ID` has one home.** The plan asked for a module-local constant in
  `test_task_lists.py`; it is defined in the harness instead and imported, because the override
  and the seeded row must be the same value and a second copy would be the one that quietly
  disagreed.
- **The replacement source scan forbids implementation names, not English.** A first draft
  forbade the words "algorithm" and "secret" and immediately collided with the docstring the
  same plan requires. The shipped tuple is `jwt`, `pwdlib`, `argon2`, `hs256`, `rs256` — the
  things a decode written here would have to spell — and `actor.py` therefore says "bearer
  token" throughout rather than naming the format.

## Deviations from Plan

### 1. `OWNER_ID` is imported from the harness, not declared module-locally

- **Found during:** Task 2
- **Plan text:** "Replace every `DEMO_USER_ID` reference … with a module-local `OWNER_ID`".
- **What shipped:** `OWNER_ID` is defined once in `tests/integration/conftest.py`, beside the
  fixture that installs it as the caller, and `test_task_lists.py` imports it.
- **Why:** the override and the `users` row the tests seed are the same identity. Two
  declarations would satisfy the plan's own `grep -c "OWNER_ID" >= 5` criterion (it prints 6
  either way) while creating exactly the drift the 04-09 `PROBLEM_JSON` argument rejects.
- **Impact:** none on behaviour; the criterion is met literally.

### 2. Task 2's `DEMO_USER_ID` criterion could not hold at Task 2

- **Found during:** Task 2
- **Plan text:** Task 2's acceptance criteria require `grep -rc "DEMO_USER_ID" tests/ | grep -v
  ":0" | wc -l` to print `0`.
- **What shipped:** after Task 2 it printed `1` — `tests/unit/presentation/test_actor.py`, the
  module whose whole subject was the constant, which Task 2 is forbidden to touch (it changes
  no production code and the constant still exists). Task 3's identical criterion over
  `src/ tests/ docker/` prints `0`, and does so because Task 3 deletes the constant and rewrites
  that module, exactly as its own `<action>` says.
- **Why not "fixed" at Task 2:** deleting those tests before the constant existed nowhere would
  have been Task 3's work done early, and the plan's ordering — harness first, production
  second — is the reason each commit leaves the tree green.
- **Impact:** none. The property holds at the end of the plan; only its position in the plan
  was wrong.

### 3. `auto_error=False` and the deleted step's label printed more than the criterion allowed

- **Found during:** Task 3
- **Issue:** the first draft of `actor.py` mentioned the scheme's argument twice in prose
  (counter printed 3, criterion 1), and the first draft of the entrypoint header named the
  deleted step by its old label (counter printed 1, criterion 0).
- **Fix:** both prose mentions reworded to describe the form rather than spell it, each with a
  one-line note pointing at the convention. Code unchanged.
- **Verification:** `grep -c "auto_error=False" src/taskmanager/presentation/api/actor.py`
  prints `1`; `grep -cE "^#.*2b|step 2b" docker/entrypoint.sh` prints `0`.
- **Impact:** none — this is the 01-03 prose-not-literal convention doing its job.

### 4. One evidence file beyond the plan's `files_modified`

- **Found during:** Tasks 1 and 3
- **Issue:** the frontmatter lists only `evidence/05-10-actor-seam.txt`, but both TDD tasks
  produced a RED run that cannot be committed as a red test.
- **Fix:** captured in `evidence/05-10-tdd-red.txt`, the filename every Phase 5 plan has used.
- **Impact:** one extra file, appended to after each run, containing only observed output.

---

**Total deviations:** 4 (1 design choice with a named precedent, 1 unsatisfiable-at-that-point
plan criterion, 1 prose rewording, 1 extra evidence file). **No production behaviour deviates
from the plan.**

## Issues Encountered

- **`make test` is unaffected by the seam becoming real**, which was the risk the task ordering
  existed to manage: 840 tests pass, 100.00% coverage over 1496 statements, no pragma and no
  omit. Nothing hung on a socket, which is the observable difference between taking the unit of
  work as a parameter and calling its provider (Pitfall 4).
- **The live compose stack was rebuilt and restarted** to prove the entrypoint is not broken:
  `docker compose build api` succeeded, `docker compose up -d` reached `api healthy`, and
  `curl http://localhost:8000/api/v1/task-lists` answers 401 problem+json with the challenge
  header. The database volume was not touched and no `downgrade` was run.
- **The already-seeded demo row on the compose database still exists** (`select count(*) from
  users` returns 1) and was deliberately left alone. It cannot become a live account: its
  stored `password_hash` is `"!"`, which is not an Argon2 encoded hash, and 05-05's adapter
  turns an unrecognised hash into `False`. A developer who wants it gone runs
  `docker compose down -v`. A fresh volume never gets it.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- **05-09 is still outstanding** and runs after this plan in the same phase; it owns the auth,
  users and assignee schemas.
- **05-11 owns** `routers/auth.py`, the `configure_logging()` call in `create_app` (still
  uncalled by anything), and the `AuthenticateActor` providers' first real consumers. The three
  aliases it needs — `PasswordHasherDependency`, `TokenServiceDependency`,
  `EmailNotifierDependency` — exist and are tested. `python-multipart` is already pinned, so
  `OAuth2PasswordRequestForm` will import.
- **05-12 owns** `routers/users.py` and `routers/assignments.py`; `AssignTask` takes three
  arguments and `UnassignTask` two, and the notifier provider is ready for the first.
- **05-13 owns `authenticated_client`**, the fixture that deliberately does *not* override
  `get_current_actor` — and it now has a named cost to discharge: `api_client` proves nothing
  about authentication, and `test_statements.py` currently runs through it, so its statement
  counts are missing D-11's confirmation read. Re-measuring those counts is 05-13's.
- **05-15 owns the cold-start capture.** The entrypoint was rehearsed here only far enough to
  prove it is not broken; the fresh-volume, zero-users, register → Authorize → call walkthrough
  is still owed.
- **05-16 owes an ADR** for `auto_error=False` as the way ADR-051 and AUTH-02 are satisfied
  together, and is the last claimant of AUTH-03, AUTH-05 and AUTH-06.

---
*Phase: 05-auth-assignment-notifications*
*Completed: 2026-09-19*

## Self-Check: PASSED

Every file named above exists on disk, and all three task commits (`41a2533`, `1c2b0d6`,
`4d6e128`) are reachable from `git log`.
