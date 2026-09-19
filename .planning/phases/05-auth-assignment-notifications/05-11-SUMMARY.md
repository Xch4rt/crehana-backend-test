---
phase: 05-auth-assignment-notifications
plan: 11
subsystem: presentation-auth-routes
tags: [auth, routes, oauth2-password-flow, openapi, security-schemes, composition-root, json-logging, d-09, d-14, d-19, d-23, d-24, adr-051, adr-056, adr-057]

# Dependency graph
requires:
  - phase: 05-auth-assignment-notifications
    provides: "RegisterUser, Login(uow, hasher, tokens, expire_minutes) and GetProfile (05-07)"
  - phase: 05-auth-assignment-notifications
    provides: "RegisterRequest, UserResponse and TokenResponse (05-09)"
  - phase: 05-auth-assignment-notifications
    provides: "CurrentActor over a real token decode, plus the port-typed security providers (05-10)"
  - phase: 05-auth-assignment-notifications
    provides: "configure_logging(), idempotent and I/O-free, called by nothing until now (05-06)"
  - phase: 04-task-lists-tasks
    provides: "The router conventions: four-line handlers, explicit response_model, a responses map naming every leg"
provides:
  - "POST /api/v1/auth/register: 201, the profile, and a Location header resolved from the profile handler's name"
  - "POST /api/v1/auth/login: the OAuth2 form Swagger's Authorize button posts, answered with {access_token, token_type, expires_in}"
  - "GET /api/v1/auth/me: the caller's own profile, and never the stored hash"
  - "register_auth_routes(app), called by create_app before the two authenticated routers"
  - "get_access_token_expire_minutes / AccessTokenExpiryDependency: the token lifetime, from the container that signed with it"
  - "create_app calls configure_logging(), so D-15's INFO notification line is actually written"
  - "An OpenAPI description stating D-14's evaluator path: register, click Authorize, call anything"
  - "tests/unit/presentation/test_security_scheme.py: the partition that fails when a route ships with no token requirement"
affects: [05-12, 05-13, 05-14, 05-15, 05-16]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A handler that takes no caller states the absence in its own docstring, because an absent parameter is invisible and here it is the security property"
    - "A configuration value that two answers must agree on travels in the typed container both are built from, never through two reads of the same setting"
    - "A published-contract assertion shaped as a partition over every operation in the document, so a route nobody remembered fails rather than going unmentioned"
    - "Logging configured in the composition root and never in the lifespan, because the HTTP harness never enters the lifespan (ADR-056)"

key-files:
  created:
    - src/taskmanager/presentation/api/routers/auth.py
    - tests/unit/presentation/test_security_scheme.py
    - .planning/phases/05-auth-assignment-notifications/evidence/05-11-tdd-red.txt
    - .planning/phases/05-auth-assignment-notifications/evidence/05-11-open-route-falsification.txt
  modified:
    - src/taskmanager/main.py
    - src/taskmanager/presentation/api/dependencies.py
    - src/taskmanager/infrastructure/security/resources.py
    - tests/unit/test_app_factory.py
    - tests/architecture/test_routers_raise_no_http_exception.py
    - tests/unit/infrastructure/test_security_resources.py

key-decisions:
  - "The token lifetime joined SecurityResources as a third member rather than being read in the router, because the plan required a provider and none existed. expires_in has to describe the lifetime the token was actually signed with; both now come from one builder call, so they cannot drift. The alternative - the settings accessor in a router - is the exact shape RC-3 forbids, and dependencies.py's 'no configuration read per request' property stays literally true (grep -c get_settings over the module still prints 0)"
  - "GET /auth/me declares a 404 leg the plan's enumeration (200/401/500) omitted. profile.py documents that leg as reachable - an account deleted between the token check and the profile read - and this module's own rule is that every route declares its full refusal set. An undeclared but reachable refusal is the dishonesty the rule exists to prevent, so the leg is published with the race named in its description"
  - "login is the one handler in the project that builds its own command. There is no request schema to put to_command on, because the fields arrive through the web framework's OAuth2 form object (05-09 decided that deliberately), so the rename from the form's username to the command's email happens at the single call site and is commented as the exception it is"
  - "Task 3's red step is a falsification, not a failing-first test. The artifact of that task IS the test, and the implementation it asserts was finished in tasks 1 and 2, so a test written afterwards is green by construction and proves nothing about its own strength. A throwaway route with no caller parameter was planted instead, the partition named it by path, and the route was removed - evidence/05-11-open-route-falsification.txt carries both runs"
  - "The route inventory test lost its 'phase four' name rather than gaining a second list. EXPECTED_API_ENDPOINTS is now fourteen entries and EXPECTED_RESPONSE_MODELS covers all of them; _presentation_models() had to learn about the auth schema module, or the response-model gate would have rejected UserResponse as a name no presentation module defines"
  - "configure_logging() is the first statement of create_app, before the settings are even resolved. Anything later would leave a failure during container construction unlogged, and the call needs nothing from the settings; the lifespan was rejected in a comment naming both reasons (untested under the HTTP harness, and D-06's empty startup half)"
  - "No requirement tick taken. AUTH-01, AUTH-02 and AUTH-05 are in this plan's frontmatter and 05-16 is the last claimant; the behaviour of all three is asserted over HTTP by 05-13, not here. The twelfth consecutive Phase 5 plan to make the same call"

patterns-established:
  - "A partition assertion over the OpenAPI document, with the exemption list carrying a per-entry reason and a test of its own that each exemption still exists and is still open"
  - "A falsification capture used where a test-only task cannot have a real red step, recording both the planted failure and the clean re-run"
  - "A container member that is not an adapter, justified at the field rather than in a changelog, because it looks inconsistent beside its two neighbours"

requirements-completed: []

# Metrics
duration: 24min
completed: 2026-09-19
---

# Phase 5 Plan 11: The Auth Routes and the Authorize Button Summary

An account can now be created, exchanged for a token and read back over HTTP through three
handlers that raise nothing, and the document Swagger builds its Authorize button from is
asserted operation by operation rather than clicked and hoped for.

## Performance

- **Duration:** ~24 min
- **Started:** 2026-09-19T16:54Z
- **Completed:** 2026-09-19T17:18Z
- **Tasks:** 3 of 3
- **Files modified:** 10 (4 created, 6 modified)

## Accomplishments

- **Three routes, under `/api/v1/auth`, each four lines long.** `register_user` returns 201
  with the profile and a `Location` header resolved from `read_current_user`'s name;
  `login` reads the OAuth2 form and answers `{access_token, token_type, expires_in}`;
  `read_current_user` returns the caller's own profile and has no identifier in its path to
  aim elsewhere. None of them raises, none of them names the web framework's exception class,
  and `routers/auth.py` joined `REQUIRED_SCANNED_MODULES` in the same commit that created it
  (Pitfall 14).
- **The two open handlers say they are open.** `register_user` and `login` are the only two
  handlers in the project with no caller parameter, and an absent parameter is invisible - so
  each docstring states the absence, why it exists, and that rows 2 and 3 of 05-15's matrix
  are what will prove it anonymously over HTTP.
- **`expires_in` and the signed token now come from one number.** `SecurityResources` gained
  `access_token_expire_minutes`, populated from the same `settings.jwt_expire_minutes`
  expression that builds `JwtTokenService` two lines above it, and
  `get_access_token_expire_minutes` hands it to the login route. 05-07's handover note - "or
  `expires_in` will describe a lifetime the token does not have" - is discharged by
  construction rather than by care.
- **`create_app` configures logging.** The call is the factory's first statement, with a
  comment naming both reasons the lifespan was rejected: the HTTP harness never enters it
  (ADR-056), and D-06 keeps the startup half empty. D-15's INFO notification line is now
  emitted rather than dropped, which is what NOTF-02 needs to be greppable in
  `docker compose logs api`.
- **`/docs` opens with the evaluator's path.** The application description states D-14
  literally: there is no seeded account, so register at `POST /api/v1/auth/register`, click
  **Authorize** with that email in the `username` field, and every other route is callable.
  It names a procedure and never a credential (T-5-03).
- **The Authorize button's contract is asserted from the document.** Five cases over
  `app.openapi()`: the scheme exists and is an OAuth2 password flow, its `tokenUrl` ends with
  a login path that is itself published, every operation is either one of three named open
  ones or carries a `security` array naming the scheme, the three open ones carry no
  `security` key at all, and the secured count is every operation minus those three.
  `grep -c "app.routes"` over the module prints 0 (ADR-057).

## Task Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | routers/auth.py - register, login and me | `5fcd1bd` | `routers/auth.py`, `dependencies.py`, `security/resources.py`, `test_routers_raise_no_http_exception.py`, `test_security_resources.py`, `evidence/05-11-tdd-red.txt` |
| 2 | The composition root configures logging and registers the auth router | `9a20356` | `main.py`, `test_app_factory.py`, `evidence/05-11-tdd-red.txt` |
| 3 | The Authorize button's contract, asserted from the document | `b6cef10` | `test_security_scheme.py`, `evidence/05-11-open-route-falsification.txt` |

## Files Created/Modified

**Created**

- `src/taskmanager/presentation/api/routers/auth.py` - the three handlers, the six refusal
  descriptions declared locally, and `register_auth_routes`.
- `tests/unit/presentation/test_security_scheme.py` - five cases, all reading
  `app.openapi()`.
- `.planning/phases/05-auth-assignment-notifications/evidence/05-11-tdd-red.txt` - the two red
  runs: the architecture guard before `routers/auth.py` existed, and the five app-factory
  failures before `create_app` changed.
- `.planning/phases/05-auth-assignment-notifications/evidence/05-11-open-route-falsification.txt`
  - the planted open route, the partition naming it, and the clean re-run.

**Modified**

- `src/taskmanager/main.py` - `configure_logging()`, `register_auth_routes(app)`, and the
  `DESCRIPTION` constant.
- `src/taskmanager/presentation/api/dependencies.py` - `get_access_token_expire_minutes` and
  `AccessTokenExpiryDependency`.
- `src/taskmanager/infrastructure/security/resources.py` - the third container member and the
  docstring that argues for it.
- `tests/unit/test_app_factory.py` - the inventory grew to fourteen, the response-model table
  and `_presentation_models()` learned about the auth schemas, and four cases were added
  (logging idempotence, logging before the lifespan, the description, the lifetime provider).
- `tests/architecture/test_routers_raise_no_http_exception.py` - `routers/auth.py` in
  `REQUIRED_SCANNED_MODULES`.
- `tests/unit/infrastructure/test_security_resources.py` - the field list, the type hints and
  the lifetime the builder copies.

## Decisions Made

See `key-decisions` in the frontmatter. The two worth reading first are the token-lifetime
container member (it is the only place this plan touched a file outside its own list) and the
404 published on `/auth/me` (the only place it published more than the plan enumerated).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] The provider the plan required did not exist**

- **Found during:** Task 1
- **Issue:** The plan says `expires_in` "comes from the same `jwt_expire_minutes` the token
  service was built with - reach it through the injected dependency rather than calling
  `get_settings()` in a router". There was no such dependency: `SecurityResources` held the
  two adapters only, the `TokenService` port exposes no lifetime, and `Login` needs the
  number as a plain `int`.
- **Fix:** `SecurityResources` gained `access_token_expire_minutes: int`, populated by
  `create_security_resources` from the same settings expression the token service is built
  from; `dependencies.py` gained `get_access_token_expire_minutes` and
  `AccessTokenExpiryDependency`, reading it through the existing private narrowing.
- **Files modified outside the plan's list:**
  `src/taskmanager/infrastructure/security/resources.py`,
  `src/taskmanager/presentation/api/dependencies.py`,
  `tests/unit/infrastructure/test_security_resources.py` (its field-list assertion is
  deliberately exhaustive, so it had to move with the dataclass).
- **Commit:** `5fcd1bd`

**2. [Rule 2 - Honest documentation] `/auth/me` declares a 404 the plan did not enumerate**

- **Found during:** Task 1
- **Issue:** The plan enumerates me's legs as 200/401/500. `GetProfile` raises
  `UserNotFoundError` when the account is gone, and `profile.py`'s docstring names that leg
  explicitly as reachable by a deletion landing between the token check and the read. The
  module's stated rule - and `task_lists.py`'s - is that every route declares its full refusal
  set.
- **Fix:** the 404 is declared, with a description naming the race and why it is an ordinary
  not-found rather than the generic 401.
- **Commit:** `5fcd1bd`

**3. [Rule 3 - Blocking] The route inventory and the response-model gate had to move**

- **Found during:** Task 2
- **Issue:** `test_create_app_publishes_exactly_the_phase_four_routes` compares the whole set
  of published operations, and `test_every_api_route_declares_a_response_model_or_returns_no_content`
  requires every name in its table to be a model defined under `presentation/api/schemas/` -
  and `_presentation_models()` read only two of the three schema modules.
- **Fix:** three entries added to both tables, the auth schema module added to
  `_presentation_models()`, and the test renamed to
  `test_create_app_publishes_exactly_the_expected_routes` because the set is no longer one
  phase's.
- **Commit:** `9a20356`

### Deliberate departures

**4. Task 3's red step is a falsification.** The task's only artifact is a test, and
everything it asserts was already built by tasks 1 and 2, so writing it and watching it pass
proves nothing about whether it can fail. A throwaway `GET /api/v1/auth/_falsification` with
no caller parameter was appended to the auth router; the partition test failed naming it by
path (`AssertionError: [('get', '/api/v1/auth/_falsification')]`) and the count test failed
with `assert 12 == (16 - 3)`. The route was removed and both runs are in
`evidence/05-11-open-route-falsification.txt`. This is the 03-08 / 03-09 precedent applied to
a test-only task.

**5. `login` builds its own command.** Every other handler in the project calls
`payload.to_command(...)`. There is no payload here - 05-09 deliberately declared no login
schema, because the fields arrive through the OAuth2 form object - so the handler constructs
`LoginCommand` at one call site, commented as the exception it is.

## Issues Encountered

- **Coverage fell from 100.00% to 99.59%.** The seven uncovered statements are the bodies of
  the three handlers: nothing drives them over HTTP yet, and plan 05-13 owns exactly that.
  The 75% gate is met with a wide margin, no `# pragma: no cover` was added and no coverage
  `omit` entry exists (`grep -rn "pragma: no cover" src/taskmanager/` prints nothing). This is
  an intra-phase state with a named owner, not a lowered bar - **05-13 must return the number
  to 100%.**
- **The behaviour was smoke-tested out of band rather than shipped unexercised.** A scratch
  script (not committed, in the session scratchpad) drove the real application with the
  in-memory fakes and dependency overrides: register → 201 with
  `Location: http://test/api/v1/auth/me` and the four-member body; login → 200 with
  `token_type: bearer` and `expires_in: 1800` for a 30-minute setting; `/auth/me` with the
  token → 200; without one → the 401 problem+json; a duplicate address in different case →
  409 `email_already_registered` carrying no address; a form missing `password` → 422 naming
  `body.password` and echoing no value. No database was touched - the application was built
  against the dead DSN the unit suite uses.
- **The `trailing-whitespace` hook rewrites evidence captures.** pytest's output carries
  trailing spaces on its source-echo lines, so the first commit attempt failed and the hook
  stripped them. The captured text is otherwise verbatim; every line was observed.

## User Setup Required

None. Nothing was installed, no container was rebuilt or restarted, and no live database was
written to.

## Next Phase Readiness

- **05-12** adds `GET /users` and the two assignee routes. `test_security_scheme.py` is built
  to accept them without being edited - each must carry `CurrentActor`, and one that does not
  will fail the partition. Each new operation must also be added to `EXPECTED_API_ENDPOINTS`
  **and** `EXPECTED_RESPONSE_MODELS` in `tests/unit/test_app_factory.py`; the two are asserted
  equal as sets, so adding one and forgetting the other fails.
- **05-13** owns the HTTP behaviour of these three routes and, with it, the seven uncovered
  statements. The properties worth asserting over the wire, already verified out of band
  above: the `Location` header's value, the four-member body in declaration order, the 409 on
  a differently-cased duplicate, and the 422 that does not echo the submitted password
  (T-5-04).
- **05-14 / D-14's cold-start rehearsal** now has something to show: the container's
  `taskmanager` logger writes JSON to stdout, so the assignment line will appear in
  `docker compose logs api`. The `api` container in the current compose stack predates this
  commit and must be rebuilt before that evidence is captured.
- **05-16** takes the AUTH-01 / AUTH-02 / AUTH-05 ticks. It should also note that
  `SecurityResources` is no longer two adapters, and that the `Location` divergence on
  register (D-19) is argued in `register_user`'s docstring, which is the copy an ADR can
  point at.

## Self-Check: PASSED
