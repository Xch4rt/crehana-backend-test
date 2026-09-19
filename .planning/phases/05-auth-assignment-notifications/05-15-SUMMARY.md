---
phase: 05-auth-assignment-notifications
plan: 15
subsystem: integration-permission-matrix
tags: [integration, http, authorization, permission-matrix, openapi, cold-start, docker, notifications, auth-03, auth-06, asgn-02, notf-02, d-01, d-02, d-03, d-04, d-11, d-14, d-15, d-20, d-24, t-5-03, t-5-11, t-5-13, t-5-15, adr-057]

# Dependency graph
requires:
  - phase: 05-auth-assignment-notifications
    provides: "authenticated_client, bearer_header and the seeded assignee/stranger identifiers (05-13)"
  - phase: 05-auth-assignment-notifications
    provides: "tests/integration/api/test_assignment.py: assert_forbidden, a_task_held_by, the_assignee, the_stranger (05-14)"
  - phase: 05-auth-assignment-notifications
    provides: "The nineteen-operation OpenAPI inventory read from app.openapi()['paths'] (05-12)"
  - phase: 05-auth-assignment-notifications
    provides: "The entrypoint with no seed step and the OpenAPI description naming the evaluator path (05-10, 05-11)"
  - phase: 04-task-lists-tasks
    provides: "assert_not_found, assert_task_not_found and the per-route HTTP suites the matrix reuses the shapes of"
provides:
  - "tests/integration/api/test_permission_matrix.py: the 19-row x 4-column contract as one parametrized test, 79 tests"
  - "A coverage assertion binding the table to app.openapi()['paths'], so a route added later without a row fails"
  - "evidence/05-15-cold-start.txt: the empty-volume rehearsal, one attempt, with the logged invitation"
  - "A rebuilt api image carrying plans 05-11 and 05-12, and a compose stack left up and healthy"
affects: [05-16]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A cross-product asserted as one parametrized test over a readable module-level table, so a missing cell is a number absent from a row rather than a test nobody wrote"
    - "The covered route set compared for equality with app.openapi()['paths'], which makes the table self-maintaining (ADR-057)"
    - "One Argon2 hash computed once per session into a module-level dict, so a suite that needs a real credential per test pays the 37 ms once"
    - "A narrow, argued dependency override (get_engine -> the test connection's engine) so /health measures the route rather than the harness's deliberately fictional DSN"
    - "A cold-start capture that records what the wipe destroyed before destroying it, so 'the volume was empty afterwards' is a change rather than a claim about an unknown starting point"
key-files:
  created:
    - tests/integration/api/test_permission_matrix.py
    - .planning/phases/05-auth-assignment-notifications/evidence/05-15-cold-start.txt
  modified: []

key-decisions:
  - "The table's paths are spelled out in the module rather than imported from the five sibling files that own them, which sets aside this package's strongest convention on purpose. A table assembled from fragments defined elsewhere is no longer a table, and D-04 says this one is reused as documentation in Phase 7. Nothing is lost: the coverage test binds every string to the published document, which is a stronger check than agreeing with a helper in a sibling test"
  - "The four expected statuses are positional fields of Row, in the markdown table's own column order, so a row reads across the way the research document does. Naming each would make every entry three lines long and destroy the one property D-04 asks for above all others"
  - "Row 3's second anonymous outcome is a test of its own rather than a value the column had to pick between. Login is the one row whose answer to an anonymous caller depends on the body: good credentials 200, bad ones 401"
  - "The matrix asserts status plus refusal shape, and deliberately does not re-assert the per-route behaviour. 05-14's handover asked for exactly this: the assignee's legs are already proven in test_assignment.py with owner-side re-reads, and the collections' contents in the per-route modules. The matrix's contribution is completeness and the anonymous column"
  - "One provider is overridden beyond the harness's own: get_engine, pointed at the connection the test already owns. /health is the single route in the table that asks the database a question outside the unit of work, and against the harness's fictional DSN it answers 503 - row 1 would then be measuring the fixture rather than the route's openness. Nothing about authentication is replaced"
  - "The owner is seeded with a REAL Argon2 hash so row 3 can log in. The placeholder the sibling modules seed is not an encoded hash, and the adapter answers False for it, so a login against it would be a 401 and the row would assert the opposite of what it says. The hash is computed once per session into a module-level dict rather than per test"
  - "The rehearsal ran `docker compose up -d --build`, not the plan's bare `up -d`. `down -v` removes containers, network and volume but NOT images, and this machine's test-api image predated plans 05-11 and 05-12. An evaluator cloning the repository has no image and their plain `up` builds one, so --build is the faithful equivalent rather than a shortcut; the capture argues it"
  - "The capture records the pre-wipe state, including the one old demo row, against the plan's acceptance criterion 'no reference to a demo account'. The criterion's intent - that no seed is written on the cold path - is met and observed (zero users, no seed line). Recording what `down -v` destroyed is the opposite of claiming a seed exists, and without it 'the volume was empty' would be a statement about an unknown starting point"
  - "The two access tokens in the capture are redacted with a marker and nothing else is. Each was a live bearer credential for thirty minutes signed with the un-committed .env secret, and a transcript in the repository is readable by anyone who can read the repository - the T-3-31 argument the entrypoint already makes about container logs"
  - "No requirement tick taken. AUTH-03, AUTH-06, ASGN-02 and NOTF-02 are in this plan's frontmatter and 05-16 is the last claimant under the project's standing convention; the sixteenth consecutive Phase 5 plan to make the same call"

patterns-established:
  - "For any claim shaped as a cross-product, the table is the artifact and the test is its reader: one parametrized case per cell, ids naming row and role, and an equality against the published route set so the table cannot go stale"
  - "A cold-start capture states its attempt count at the head, records what the wipe removed, and ends by proving the throwaway test database came back"

requirements-completed: []

# Metrics
duration: 20min
completed: 2026-09-19
---

# Phase 5 Plan 15: The Permission Matrix and the Five Minutes an Evaluator Spends Summary

AUTH-06 is now one table a reviewer can read and a test run can fail - nineteen routes by four
callers, seventy-six cells plus login's second anonymous answer, with the covered route set
compared against `app.openapi()["paths"]` so a route shipped without a row is a failure rather
than a gap; and the documented evaluator path was rehearsed on a genuinely empty volume, from
`docker compose down -v` to the `task_assigned_email` line, in one attempt.

## Performance

- **Duration:** ~20 min
- **Tasks:** 2 of 2
- **Files modified:** 2 (2 created, 0 modified)

## Accomplishments

- **The whole cross-product, in one file, as a table.** `MATRIX` carries nineteen `Row`
  entries, each naming the method, the published path template and the four statuses owed to
  the owner, the assignee, a stranger and an anonymous caller, in the research document's own
  column order. 76 cells are driven by one parametrized test whose ids read
  `08-assignee-GET-/api/v1/task-lists/{list_id}`, so a failure names the row of D-04 it came
  from and `-k anonymous` selects exactly that column.
- **Every cell asserts a document.** 401 cells assert the `WWW-Authenticate: Bearer` challenge,
  the six-member body and `AuthenticationError.REFUSAL` read from the class rather than copied;
  403 cells go through `test_assignment.py`'s `assert_forbidden`; 404 cells go through
  `assert_not_found` or `assert_task_not_found` according to which shape the row is owed, so
  the `code` and the `errors` member are checked and not only the number.
- **The anonymous column measures the real dependency.** The module runs on
  `authenticated_client` with three tokens minted by the application's own service for seeded
  rows, and the fourth caller sends no `Authorization` header at all - not an empty one, not an
  invalid one, which is `test_auth.py`'s territory.
- **The three open routes are asserted open.** `/health`, register and login answer an
  anonymous caller, and every 2xx cell additionally asserts that no challenge header came back,
  so "openness" means openness rather than a refusal that happened to carry a 2xx. Which routes
  need no token is now a fact the table states.
- **The table cannot go stale.** `test_the_table_covers_every_operation_the_document_publishes`
  reads `app.openapi()["paths"]` and asserts set equality in both directions - an unmeasured
  route and a stale row both fail - with `len(published) == 19` as the non-vacuity guard. A
  fourth test pins the row numbers to 1..19, the `(method, path)` pairs to unique, and the cell
  count to `4 x 19`, because a set swallows a duplicate the coverage test would not see.
- **Every destructive cell is isolated rather than ordered.** The fixture is function-scoped:
  rows 10 and 15 delete the subject rows 8-18 address and row 9 renames it, so each cell gets
  its own list and task on the rolled-back connection. A matrix whose later rows depend on its
  earlier ones passes for the wrong reason.
- **All 76 cells were right on the first run.** The table lifted from `05-RESEARCH.md` matched
  the running application exactly - no cell surprised, no production bug exposed. Given that
  this is the first time the cross-product has been driven as a cross-product, that is the
  result worth recording.
- **The cold start, in one attempt.** An empty volume to `api healthy` in 7 seconds, three
  startup steps and no fourth, `SELECT count(*) FROM users` returning **0**, then the
  documented path exactly as `/openapi.json` states it: register, register a teammate, log in,
  read the profile, create a list, create a task, `GET /api/v1/users`, `PUT .../assignee`.
- **One grep finds the invitation.** `docker compose logs api | grep task_assigned_email`
  prints exactly one line; it parses through `python3 -m json.tool` as a single JSON object
  and carries `to`, `subject`, `body` and `task_id`, checked by membership (NOTF-02, D-15,
  D-24).
- **D-01 and D-02 observed in the running container.** The teammate's `assigned-to-me` returns
  the task, their `GET /api/v1/task-lists` returns `[]`, and the list the task lives in answers
  404 - the asymmetry the discovery route exists for, outside the test suite for the first
  time.
- **The stack was left up and healthy with `taskmanager_test` reachable**, and `make test` ran
  green inside the capture itself: 998 passed, 100.00% coverage. The next plan's gate is not
  the thing that discovers the volume was wiped.

## Deviations from Plan

### Auto-fixed issues

**1. [Rule 1 - Bug in the test as first written] The API has two 401 wordings, not one**

- **Found during:** Task 1
- **Issue:** The first draft asserted `AuthenticationError.REFUSAL` on every 401 in the table,
  including login's bad-credential leg. That leg was observed failing with
  `'Incorrect email or password.' != 'Could not validate credentials.'`.
- **Fix:** Not a defect in the application - `AuthenticationError`'s own docstring argues it:
  login asks a different question at a different endpoint and passes a message with a single
  home in `use_cases/auth/login.py`, while the token refusals share the class default so they
  cannot be told apart. `assert_unauthenticated` was split into
  `assert_a_bearer_challenge` (status, media type, challenge header, six members, `code`) plus
  the D-11 wording, and the login test asserts the challenge half plus the property that
  matters at that door: neither the address nor the password comes back.
- **Files modified:** `tests/integration/api/test_permission_matrix.py`
- **Commit:** b548622

### Deliberate departures

**1. `docker compose up -d --build`, not the plan's bare `up -d`.** `down -v` removes
containers, network and volume but not images, and this machine's `test-api` image predated
05-11 and 05-12 - it had no `configure_logging()` in `create_app()` and none of the four new
routes, so a rehearsal on it would have proved the wrong thing. An evaluator cloning the
repository has no image at all and their plain `up` builds one. The capture argues this where
it happens.

**2. The capture records the pre-wipe state, including the old demo row.** The plan's
acceptance criterion asks for "no reference to a demo account". The criterion's intent is met
literally on the cold path - no `INSERT INTO users` anywhere, no seed line in the startup log,
zero users on the fresh volume - and the only mention is STEP 0 recording what
`docker compose down -v` was about to destroy, which the orchestrator asked for explicitly and
which is what turns "the volume was empty afterwards" into an observed change.

**3. Two access tokens are redacted.** Marked in place, explained at the head, and the length
of each redacted value is recorded by the command that follows it. Nothing else in the capture
is elided, including the full build output.

**4. Row 3's anonymous 401 is a separate test rather than a fifth column.** The parametrized
walk stays a clean 4-column cross-product; the extra cell is named
`test_login_refuses_a_bad_credential_from_an_anonymous_caller` and sits immediately after it,
with the table commenting that this row is the one whose anonymous answer depends on the body.

**5. `get_engine` is overridden in this module's fixture.** Argued in full in the fixture
docstring: the shared harness aims its application at a deliberately fictional DSN, and
`/health` is the one route in the table that dials the database itself, so row 1 would have
measured 503 against the fixture rather than 200 against the route.

**6. No TDD RED step.** The plan marks Task 1 `tdd="true"`, and the deliverable is a test over
an application that already exists - every cell was green when written. Rather than stage
theatre, the honest RED is recorded above: the one assertion that did fail on first run, and
what it turned out to mean. This is the compromise 02-01, 05-13 and 05-14 each recorded.

## Verification

| Gate | Result |
|---|---|
| `make lint` | pass - black, isort and flake8 over 180 files |
| `make typecheck` | pass - `Success: no issues found in 180 source files` |
| `make arch` | pass - `Contracts: 4 kept, 0 broken.` |
| `make test` | pass - **998 passed in 9.33s**, `Required test coverage of 75% reached. Total coverage: 100.00%` |
| `docker compose ps` | `api healthy`, `db healthy` |
| `grep -rn "pragma: no cover" src/taskmanager/` | 0 hits |

Every acceptance criterion was checked literally:

- `test_permission_matrix.py` collects **79** (76 asked); `-k anonymous` **20** (19);
  `-k assignee` **25** (19); `-k covers` **1** (1).
- `grep -c`: `app.routes` **0** (0 asked), `api_client` **0** (0), `WWW-Authenticate` **4**
  (>= 1).
- The capture contains `docker compose down -v` (3), `healthy` (13), `auth/register` (3),
  `auth/login` (2), `assignee` (8), `task_assigned_email` (7), `assigned-to-me` (6),
  `application/problem+json` (3), `www-authenticate: Bearer` (2), and `INSERT INTO users` **0**.
- `docker compose logs api | grep -c task_assigned_email` prints **1**.
- The attempt count is the third line of the capture: **ATTEMPTS: ONE**.

## Known Stubs

None.

## Threat Flags

None. This plan adds no route, no schema and no network surface. It measures the ones Phase 5
shipped and rehearses the container that serves them.

## Notes for Later Plans

- **The matrix is where a new route's permissions must be declared.** Adding an operation
  without a `Row` fails `test_the_table_covers_every_operation_the_document_publishes`, and the
  failure message names the unmeasured `(method, path)`. The same table is the one Phase 7's
  README should reproduce (D-04).
- **This API has two 401 wordings, both with `code: authentication_failed` and both carrying
  the challenge.** `AuthenticationError.REFUSAL` for anything to do with a token, and
  `use_cases/auth/login.py`'s own constant for a rejected credential. Any future assertion on a
  401 `detail` must say which door it is at.
- **The running stack is now the current code.** The `api` image was rebuilt during the
  rehearsal, so `docker compose logs api`, `/docs` and the four Phase 5 routes are live on
  `localhost:8000`. The volume holds two accounts created by the rehearsal
  (`evaluator@example.com`, `teammate@example.com`), one list and one assigned task; their
  passwords exist only in the capture and nothing in the repository depends on them.
- **`make test` was run inside the capture and again after it**, both green against the
  recreated `taskmanager_test`. 05-16 does not need to re-establish the database.
- **05-16 is the last claimant of AUTH-03, AUTH-06, ASGN-02 and NOTF-02.** Both artifacts this
  plan produced are the evidence those ticks should be re-verified against: the matrix for
  AUTH-03 and AUTH-06, the capture for NOTF-02.

## Self-Check: PASSED

- `tests/integration/api/test_permission_matrix.py` - FOUND
- `.planning/phases/05-auth-assignment-notifications/evidence/05-15-cold-start.txt` - FOUND
- Commits `b548622`, `36729f2` - both FOUND in `git log`
