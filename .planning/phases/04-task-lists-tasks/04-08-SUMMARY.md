---
phase: 04-task-lists-tasks
plan: 08
subsystem: presentation
tags: [fastapi, routers, openapi, rfc-9457, d-11, d-12, d-13, d-15, ast-gate, arc-05]

# Dependency graph
requires:
  - phase: 04-task-lists-tasks
    provides: "04-07's CurrentActor, UnitOfWorkDependency, ClockDependency and the eight Pydantic models with their to_command / from_result mappers"
  - phase: 04-task-lists-tasks
    provides: "04-05's five task-list use cases and 04-03/04-06's six task use cases, each one class with execute(command) -> result"
  - phase: 04-task-lists-tasks
    provides: "04-04's frozen command and result DTOs, including the flat TaskCollectionResult"
  - phase: 02-domain-error-contract
    provides: "register_exception_handlers and the MRO status table — every new refusal resolves with zero edits to mapping.py"
  - phase: 03-persistence
    provides: "create_app, register_health_routes as the registration shape to copy, and get_uow's never-commit contract"
provides:
  - "presentation/api/routers/task_lists.py — the five task-list routes"
  - "presentation/api/routers/tasks.py — the six task routes, including PATCH .../status"
  - "eleven routes published under /api/v1, each with a tag, a summary, a response description and a refusal map"
  - "tests/architecture/test_routers_raise_no_http_exception.py — D-15's second gate, in two passes, both shown red"
  - "a route-inventory test and ARC-05's mechanical half, both read off the published OpenAPI document"
  - "the app surface 04-09 and 04-10 write their HTTP integration tests against"
affects: [04-09, 04-10, 04-11, 04-12, 05, 07]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A handler is four lines: build a command from the schema and the actor, run the use case, map the result, set a header — anything longer is a rule that escaped a layer"
    - "`request.url_for(\"get_task\", ...)` builds the Location header, so the handler function name is load-bearing and no prefix is ever concatenated"
    - "A 204 declares a bare response class, because the same handler without it sends content-type: application/json on an empty body"
    - "Every route declares response_model= explicitly AND is annotated with the response schema, so no application dataclass can become the published schema"
    - "A route inventory is read out of app.openapi()['paths'], never off app.routes — this FastAPI leaves one opaque object there with no path and no methods"
    - "An architecture gate reads syntax (ast) when the property is about what the code does, and text when the property is about the text (03-06)"

key-files:
  created:
    - src/taskmanager/presentation/api/routers/__init__.py
    - src/taskmanager/presentation/api/routers/task_lists.py
    - src/taskmanager/presentation/api/routers/tasks.py
    - tests/architecture/test_routers_raise_no_http_exception.py
    - .planning/phases/04-task-lists-tasks/evidence/04-08-ast-gate-red.txt
  modified:
    - src/taskmanager/main.py
    - tests/unit/test_app_factory.py

key-decisions:
  - "The plan's acceptance one-liners walk app.routes looking for .path and .methods; on FastAPI 0.141.1 with Starlette 1.6.0, include_router leaves a single opaque fastapi.routing._IncludedRouter with neither attribute, so those commands report zero routes against a correctly wired app. Every route assertion — the acceptance checks and the new inventory test — reads app.openapi()['paths'] instead, which is both the working form and the honest one: it is the document a client actually reads"
  - "Every route declares a 500 leg beside its 404/409/422. Phase 2's catch-all answers an unexpected failure with a fixed problem+json body, so 500 is a documented outcome rather than an accident — and it is what lets GET /api/v1/task-lists, the one route with no 404, no 409 and no 422, still publish a non-empty and truthful refusal map instead of an invented one"
  - "Declaring 422 explicitly REPLACES FastAPI's auto-generated 422, which referenced the HTTPValidationError schema. That is a correction, not a loss: this API answers 422 through handle_validation_error with an RFC 9457 body, so the generated entry documented a shape no endpoint has ever returned"
  - "The tasks router takes the plan's conditional branch: the Python parameter is status_filter with Query(alias=\"status\"), because the plain name would shadow the status module the file imports for its status-code constants. The public contract is unchanged and was measured — an unknown filter value answers 422 with field \"query.status\""
  - "The import half of the D-15 gate flags the forbidden name bound from ANY module, not only from fastapi and starlette.exceptions as the research recommends. Naming the two modules would tie the gate to a fact about a dependency rather than to the property, and a local re-export would walk straight through it"
  - "The red capture's first plant adds the import as well as the raise. A raise of a name the module never bound is not a state the codebase could reach, and both assertions have to be shown failing — the import is what makes the plant realistic and the second run (import only, raise removed) is what proves the two assertions are not redundant"
  - "Requirement ticks ARC-05 / LIST-01..06 / TASK-01..08 deliberately NOT taken — 04-12 is the last claimant, the eighth consecutive plan in this phase to make the same call. These routes have no HTTP test above them until 04-09 and 04-10, and a requirement ticked from a route's existence rather than from its behaviour is a tick that proves nothing"

patterns-established:
  - "One shared description constant per refusal leg per router module, so the same leg reads identically on every verb in /openapi.json"
  - "A route-inventory test that writes the expected set down rather than deriving it, because a derived expectation agrees with whatever the app happens to expose"
  - "A documentation test (tag, summary, success description, at least one refusal leg) so the twelfth route cannot arrive bare"
  - "An architecture gate whose two passes are deliberately overlapping, with the capture proving the weaker one can pass while the stronger one fails"

requirements-completed: []

# Metrics
duration: 11min
completed: 2026-09-19
---

# Phase 4 Plan 08: the HTTP surface and D-15's second gate Summary

**Eleven routes now answer under `/api/v1` — five for task lists, six for tasks including the dedicated `PATCH .../status` — every handler is four lines that build a command, run a use case and map a result, every route publishes a Pydantic model or a bodiless 204, and a router that reached for the web framework's own exception class would fail an AST gate that has been shown able to fail twice, in two different ways.**

## Performance

- **Duration:** ~11 min (06:08 → 06:19 UTC)
- **Tasks:** 3 of 3, one commit each
- **Files:** 5 created, 2 modified

## Accomplishments

- **The phase became visible.** `create_app` gained two calls, and `/openapi.json` gained eleven operations: `POST`/`GET` on `/api/v1/task-lists`, `GET`/`PATCH`/`DELETE` on `/api/v1/task-lists/{list_id}`, `POST`/`GET` on `.../tasks`, `GET`/`PATCH`/`DELETE` on `.../tasks/{task_id}`, and `PATCH .../tasks/{task_id}/status`. The task-list router and the task router share the `/task-lists` prefix so the URLs stay nested, and carry different tags so `/docs` shows two groups rather than eleven flat entries.
- **Every handler is four lines or fewer, and that is the point.** The longest body in either module is the create route's three statements plus a `return`. There is no `try`, no `except`, no branch, no transaction, no validation and no ownership check anywhere in the two files — every one of those was proved by a unit test in waves 1-3, and a handler that had grown one would have been a rule that escaped its layer.
- **201 and 204 are both correct rather than approximately correct.** The two create routes set `Location` from `request.url_for(...)`, which honours both prefixes — `grep` finds no `/api/v1` string anywhere in either router. The two delete routes declare a bare response class, because the same handler without it sends `content-type: application/json` on an empty body (04-RESEARCH's measurement, reproduced).
- **ARC-05's boundary claim is now mechanical.** Every route passes `response_model=` **and** is annotated with the response schema, and `test_every_api_route_declares_a_response_model_or_returns_no_content` reads the published schema back: a handler annotated with a result dataclass would answer a `curl` perfectly and fail here.
- **The route inventory is an inventory, not a count.** `test_create_app_publishes_exactly_the_phase_four_routes` compares the whole `(method, path)` set against eleven written-down pairs, so a route re-pathed, a verb changed, or one deleted while another was added fails with the offending pair named.
- **D-15's second gate landed, in two passes, both falsified.** `test_no_router_raises_an_http_exception` walks every `raise` and resolves the name; `test_no_router_imports_an_http_exception` refuses the name anywhere it is bound or reached, which is the load-bearing half because it makes the bind-then-raise form the first pass provably misses impossible in the first place. A third test, `test_the_routers_package_is_actually_scanned`, requires both router modules by name so a moved package fails the guard instead of asserting that nothing is nothing.
- **The capture proves the pair is not redundant.** `evidence/04-08-ast-gate-red.txt` shows plant 1 (an import and a raise) turning **both** red at `tasks.py:208` and `tasks.py:27`, then plant 2 (the import alone) leaving the raise check **green** and turning only the import check red, then the green run on the restored tree. That second run is the whole argument for keeping two assertions instead of one.
- **`mapping.py` needed no edit, exactly as the plan predicted.** `TaskListNotFoundError`, `TaskNotFoundError`, `DuplicateTaskListNameError` and `InvalidStatusTransitionError` all resolve through the MRO walk, so the eleven routes added four refusal legs and zero lines to the status table.
- **The filters cannot reach SQL as free text.** Both query parameters are typed by the domain enumerations. Measured against the composed app: `?status=bogus` answers `422` with `application/problem+json` and `errors[0].field == "query.status"`, before any use case runs.
- **Routing was smoke-tested without a database.** Five requests against the real `create_app` output — a malformed path UUID, an empty patch body, `status` sent to the generic task patch, an invalid filter value, and `status` on a patch — each returned `422 application/problem+json` from the single error handler, which proves both routers dispatch and that no route answers an error itself.

## Task Commits

1. **Task 1: the task-list router** — `55392c3` (feat)
2. **Task 2: the task router, including the dedicated status endpoint** — `f362847` (feat)
3. **Task 3: composition-root registration and D-15's AST gate with its red capture** — `f96076e` (feat)

**Plan metadata:** see the final `docs(04-08)` commit.

## Files Created

| File | Statements | Coverage | Notes |
|------|-----------:|---------:|-------|
| `presentation/api/routers/__init__.py` | 0 | 100% | empty, mirroring `errors/__init__.py` |
| `presentation/api/routers/task_lists.py` | 39 | 74% | 5 routes; the 10 uncovered lines are handler bodies, owed to 04-09 |
| `presentation/api/routers/tasks.py` | 49 | 76% | 6 routes; the 12 uncovered lines are handler bodies, owed to 04-10 |
| `tests/architecture/test_routers_raise_no_http_exception.py` | — | — | 3 tests |
| `evidence/04-08-ast-gate-red.txt` | — | — | 185 lines, three runs |

## Files Modified

| File | Change |
|------|--------|
| `src/taskmanager/main.py` | `+2` imports, `+2` calls in `create_app` — nothing else |
| `tests/unit/test_app_factory.py` | `+_api_operations`, `+EXPECTED_API_ENDPOINTS`, `+3` tests |

## Gate Results

| Gate | Result |
|------|--------|
| `make lint` | black / isort / flake8 (incl. bugbear B008) — clean, 135 files |
| `make typecheck` | `mypy src tests` strict — 135 source files, no issues |
| `make arch` | 4 contracts kept, 0 broken |
| `make test` | **520 passed**, coverage **98.25%** (gate 75%) |
| `pytest tests/unit tests/architecture -q --no-cov` | 420 passed |
| `grep -rc "HTTPException" src/.../routers/` | `0` on all three files |
| `grep -c "Depends("` per router | `0` and `0` — every injection is an imported alias |
| `grep -c "task_list_id" routers/tasks.py` | `7` (floor was 6) — D-14 travels on every task route |
| `git diff --stat .pre-commit-config.yaml .github/workflows/ci.yml` | empty — the gate rides inside pytest |

The 22 uncovered statements in `src/taskmanager` are all router handler bodies. They are not stubs and carry no pragma and no omit: 04-09 and 04-10 exercise every one of them over HTTP, which is D-16's whole purpose. Coverage is expected to return to 100% at the end of 04-10.

## Deviations from Plan

### 1. [Rule 3 — blocking] `app.routes` cannot be walked on this FastAPI; every route assertion reads the OpenAPI document

- **Found during:** Task 1's acceptance check, and again in Task 3.
- **Issue:** the plan's three route-counting one-liners all iterate `app.routes` filtering on `hasattr(r, 'methods')` and reading `r.path`. On the pinned stack (FastAPI 0.141.1, Starlette 1.6.0) `include_router` leaves a single `fastapi.routing._IncludedRouter` object in `app.routes` with **no `path` and no `methods` at all**. Run verbatim against a correctly wired application, the first command asserted `0 == 5` and failed.
- **Fix:** every route assertion — the three acceptance checks and the new inventory test — derives its operations from `app.openapi()["paths"]`. `_api_operations()` in `test_app_factory.py` carries the reason in its docstring.
- **Why this is the better form anyway:** the schema is what a client reads, so asserting on it is asserting the published contract rather than an internal representation that has already changed once. This module's own probe guard hit the same opacity in 03-09 and reached the same conclusion, in its own words: *"FastAPI wraps an included router in a single opaque object with no `path` attribute at all"*.
- **Files:** `tests/unit/test_app_factory.py`
- **Commit:** `f96076e`

### 2. [Rule 2 — missing critical functionality] Every route declares a `500` leg, which the plan does not list

- **Found during:** Task 1.
- **Issue:** the plan asks for a `responses` map on every route "naming the legs that route can produce — 404 …, 409 …, 422 …". `GET /api/v1/task-lists` can produce none of the three: it has no path parameter, no body and no query parameter, and a caller who owns nothing gets `200` with `[]`. Taken literally the route would have had an **empty** map, and the plan's own must-have ("every route carries … a `responses` map") would have been false.
- **Fix:** every route also declares `500`, described as the fixed problem+json body Phase 2's catch-all handler produces. It is a genuine, documented outcome of every route in this API, so the collection route's map is non-empty and truthful rather than padded with a leg that cannot happen.
- **Files:** `routers/task_lists.py`, `routers/tasks.py`
- **Commits:** `55392c3`, `f362847`

### 3. [Rule 1 — bug] Declaring `422` replaces FastAPI's generated `HTTPValidationError` entry, and that is the correct outcome

- **Found during:** Task 1, reading the generated schema back.
- **Issue:** FastAPI auto-generates a `422` response referencing its `HTTPValidationError` component for any route with a body or a typed parameter. This API does not return that shape: `handle_validation_error` answers with an RFC 9457 `application/problem+json` document. The generated entry documented a body no endpoint has ever produced.
- **Resolution:** the explicit `422: {"description": ...}` supersedes it, leaving a description and no misleading `content`. Publishing the real problem+json schema instead is DOC-04's budget in Phase 7 (04-RESEARCH Open Question 3), and the plan explicitly forbids adding a `ProblemDetail` model here.
- **Files:** `routers/task_lists.py`, `routers/tasks.py`

### 4. The `status` filter is `status_filter` + `Query(alias="status")` — the plan's conditional branch, taken

- **Found during:** Task 2.
- **Issue:** the plan makes this conditional on whether the Python name would shadow the imported `status` module. It would: `tasks.py` imports `status` from `fastapi` for `HTTP_201_CREATED` and `HTTP_204_NO_CONTENT`.
- **Fix:** the parameter is `status_filter`, aliased to `status`. The public contract is unchanged and was **measured**, not assumed: `?status=bogus` answers `422` with `errors[0].field == "query.status"`, so TASK-06's URL and the 422's `loc` are both exactly as specified.
- **Files:** `routers/tasks.py`
- **Commit:** `f362847`

### 5. [Rule 2] A third app-factory test the plan does not ask for: every route is documented

- **Found during:** Task 3.
- **Issue:** the plan's must-haves require a tag, a summary, a response description and a refusal map on every route, and the plan schedules a gate for none of it. A documented contract with no gate is the one that drifts first.
- **Fix:** `test_every_api_route_is_documented` asserts all four members on every `/api/v1` operation, so the twelfth route cannot arrive bare.
- **Files:** `tests/unit/test_app_factory.py`
- **Commit:** `f96076e`

### 6. The import half of the gate is wider than the research recommends

- **Found during:** Task 3.
- **Issue:** 04-RESEARCH Pattern 9 recommends flagging an `ImportFrom` whose module is `fastapi` or `starlette.exceptions`. That ties the gate to a fact about a dependency's layout rather than to the property being defended, and a local re-export — a module that forwarded the name — would pass it.
- **Fix:** the name is refused wherever it is bound, from any module, plus any attribute access carrying it. Strictly stronger, with the reasoning in the module docstring.
- **Files:** `tests/architecture/test_routers_raise_no_http_exception.py`

### 7. The first plant adds the import as well as the raise

- **Found during:** Task 3's falsification.
- **Issue:** the plan describes plant 1 as "the planted `raise HTTPException(status_code=404)`". A raise of a name the module never bound is not a state this codebase could reach, and it would leave the import assertion green — but the plan requires **both** tests failing on plant 1.
- **Fix:** plant 1 is the import *and* the raise, which is what a real mistake looks like; plant 2 is then the import alone, which is the run that proves the two assertions are not redundant. The diff of each plant is included verbatim in the capture.
- **Files:** `evidence/04-08-ast-gate-red.txt`

### 8. Two grep criteria were met by rewording prose, not by weakening the code

- **Found during:** Task 1's acceptance check.
- **Issue:** `grep -c "commit()"` printed `1` and `grep -c "response_class=Response"` printed `2`, both from docstrings that named the forms they were explaining.
- **Fix:** both passages were reworded to describe the form rather than spell it — the project's prose-not-literal convention since 01-03, which exists precisely so these counters stay strict. The module docstring now says so explicitly and names `test_no_commit_in_repositories.py` as the source of the convention.
- **Files:** `routers/task_lists.py`

### 9. The evidence capture had trailing whitespace stripped by a pre-commit hook

- **Found during:** Task 3's commit.
- **Issue:** pytest pads its assertion-diff lines with trailing spaces; the repository's `trailing-whitespace` hook rewrote the file and failed the commit.
- **Resolution:** the edit was accepted and **declared in the capture's header**, following the Phase 1 precedent that names the one edit applied to its captures. No line was added, removed or reworded and no exit code changed.
- **Files:** `evidence/04-08-ast-gate-red.txt`

### 10. `create_app` gains four lines, of which two are in the function

- The success criterion reads "create_app gains exactly two lines". The **function body** gains exactly two — `register_task_list_routes(app)` and `register_task_routes(app)` — plus the two import lines they need at module level. `git diff --stat src/taskmanager/main.py` reports `1 file changed, 4 insertions(+)`, and there are no deletions.

## Authentication Gates

None. Phase 4 runs as the fixed demo actor through 04-07's seam; no credential, token or external login was needed.

## Threat Flags

None new. Eleven HTTP endpoints were added, and all eleven are inside the plan's own `<threat_model>` — no file access pattern, no schema change and no trust boundary beyond the ones the register already names. Each mitigation has a gate:

| Threat | Mitigated by |
|--------|--------------|
| T-4-43 actor from the body or the path | `actor_id` arrives only as `CurrentActor`; no request schema declares the field, and `grep -c "Depends("` is `0` on both routers because the injection is an imported alias |
| T-4-44 a router deciding visibility | no `try`, no `except` and no framework exception in either module; both AST assertions green, both shown red |
| T-4-45 a second error-body shape | no router constructs a response body; `mapping.py` unchanged, every new leaf resolving by MRO |
| T-4-46 the nested `{list_id}` ignored | `grep -c "task_list_id" routers/tasks.py` prints `7`; every one of the six task routes passes the parent segment into its command |
| T-4-47 a filter reaching SQL as free text | enum-typed query parameters; measured `422` at `query.status` before any use case runs |
| T-4-48 a result dataclass as the response model | explicit `response_model=` on all eleven routes, plus `test_every_api_route_declares_a_response_model_or_returns_no_content` on the published schema |
| T-4-49 a gate that scanned nothing | `REQUIRED_SCANNED_MODULES` naming both routers, plus `test_the_routers_package_is_actually_scanned`; the capture proves both real assertions can fail |
| T-4-50 the app opening a connection at import | `create_app` gained only the two register calls; `test_creating_the_app_opens_no_connection` and `test_the_lifespan_disposes_the_engine` both still green in the 520-test run |
| T-4-SC package installs | none; this plan installed nothing |

## Known Stubs

None. The 22 uncovered statements are fully implemented handler bodies with no test above them yet — 04-09 and 04-10 own that, per D-16. No route returns a hardcoded value, a placeholder or an empty collection it did not get from a use case.

## Handoff Notes

- **04-09 / 04-10 (HTTP integration):** the harness must reach a second actor with `app.dependency_overrides[get_current_actor] = lambda: other_id`; that is the only route to D-04's not-owned 404 legs over HTTP.
- **04-09 / 04-10:** assert the `Location` header on both create routes. It is built by `url_for`, so a renamed handler function — `get_task_list` or `get_task` — breaks the header while every import still resolves. Nothing else in the codebase would notice.
- **04-09 / 04-10:** the 204 routes must be asserted for **no** `content-type` header, not merely for an empty body. That is the measured difference the bare response class buys, and an assertion on the body alone would pass without it.
- **04-10:** `?status=bogus` was measured here as `422` with `errors[0].field == "query.status"` — the alias is what preserves that, so the integration test is the thing that would catch its removal.
- **04-11 (N+1):** the statement counter attaches to `GET /api/v1/task-lists` and `GET /api/v1/task-lists/{list_id}/tasks`; both handlers make exactly one use-case call, so any growth in the statement count is the repository's, not the router's.
- **04-12 (ADRs):** three entries owed — the `_IncludedRouter` opacity and the decision to assert routes through the OpenAPI document (Deviation 1); the `500`-on-every-route choice and the replacement of FastAPI's generated 422 (Deviations 2 and 3); and D-15's two-pass gate with the honest statement of what the raise pass misses (Deviation 6).
- **Phase 7 (DOC-04):** the `422` and `500` entries currently carry a description and no schema. Publishing the real problem+json component is that phase's budget, and the descriptions are written so they stay correct when it lands.
- **Phase 5:** nothing in either router changes when JWT arrives. Every handler takes the caller from `CurrentActor`, so only `get_current_actor`'s body moves.

## Self-Check: PASSED

- `src/taskmanager/presentation/api/routers/__init__.py` — FOUND
- `src/taskmanager/presentation/api/routers/task_lists.py` — FOUND, contains `HTTP_201_CREATED`
- `src/taskmanager/presentation/api/routers/tasks.py` — FOUND, contains `/status`
- `tests/architecture/test_routers_raise_no_http_exception.py` — FOUND, contains `REQUIRED_SCANNED_MODULES`
- `.planning/phases/04-task-lists-tasks/evidence/04-08-ast-gate-red.txt` — FOUND, contains a red run and a green run
- `55392c3` — FOUND in `git log`
- `f362847` — FOUND in `git log`
- `f96076e` — FOUND in `git log`
