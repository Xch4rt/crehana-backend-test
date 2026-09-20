---
phase: 07-documentation-delivery
plan: 01
subsystem: presentation-openapi
tags: [doc-04, rfc-9457, openapi, problem-json, totality-gate, tags]

# Dependency graph
requires:
  - phase: 02-domain-errors
    provides: "presentation/api/errors/problem.py — the one body builder and PROBLEM_JSON"
  - phase: 06-test-hardening-coverage
    provides: "tests/problem_details.py MEMBERS — the D-06 member order stated once"
  - phase: 07-documentation-delivery
    provides: "07-RESEARCH.md Gap 3 — the four measured spellings and the subclass fix"
provides:
  - "ProblemResponse — the RFC 9457 document as a published Pydantic model, errors last and optional"
  - "problem_response(description) — one error leg, no model= key, exactly one media type"
  - "PROBLEM_SCHEMA_NAME / PROBLEM_REF / PROBLEM_EXAMPLE"
  - "ProblemAwareFastAPI — registers the Problem component idempotently so 69 $refs resolve"
  - "OPENAPI_TAGS — six described tags in registration order"
  - "tests/architecture/test_openapi_completeness.py — the DOC-04 totality gate, seven tests"
affects: [07-02-decision-log, 07-04-readme, 07-05-rehearsal]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Declare an error leg with content= and no model=: a model publishes application/json, the media type this API never serves for an error"
    - "Subclass FastAPI to inject an OpenAPI component; app.openapi = fn is a mypy --strict method-assign"
    - "Bind a published model to its builder with a test that reads a real response, not with an import"
    - "A totality gate takes a floor plus a per-item property, never an exact census count"

key-files:
  created:
    - src/taskmanager/presentation/api/schemas/problem.py
    - tests/unit/presentation/test_problem_schema.py
    - tests/architecture/test_openapi_completeness.py
  modified:
    - src/taskmanager/main.py
    - src/taskmanager/presentation/api/routers/auth.py
    - src/taskmanager/presentation/api/routers/task_lists.py
    - src/taskmanager/presentation/api/routers/tasks.py
    - src/taskmanager/presentation/api/routers/users.py
    - src/taskmanager/presentation/api/routers/assignments.py
    - tests/architecture/test_routers_raise_no_http_exception.py

key-decisions:
  - "The no-model spelling, and the FastAPI subclass that pays for it. Three of the four obvious ways to declare an error leg publish application/json — one of them alongside problem+json with an empty schema, which is the worst of the four. The correct form registers no component, so ProblemAwareFastAPI.openapi() setdefaults it in. A subclass rather than app.openapi = fn, which mypy --strict rejects as method-assign; buying a one-line convenience with a type: ignore in the composition root is not a trade this project makes"
  - "The model is bound to the builder by a test, not by an import. errors/problem.py builds the body as a dict literal and ProblemResponse describes it — two descriptions of one thing drift silently. test_problem_schema.py calls problem(...) for real, for all three errors shapes, and compares the served member order against the declared one, both read from running code"
  - "deepcopy per leg rather than the plan's dict(PROBLEM_REF). A shallow copy leaves the inner {\"$ref\": ...} object shared by all 69 legs, which is the mutable-object hazard the plan named; the deep copy is what actually removes it, and test_two_legs_share_no_mutable_object proves it"
  - "The gate takes a floor (19 operations, 69 non-exempt legs) plus a per-leg property, never the exact census. The census moves with every route added, so an equality would be a test of the census that gets 'fixed' by editing the number"
  - "The application/json assertion is a separate test from the problem+json one. Two of the three wrong spellings publish both media types, so the per-leg 'exactly one key' check catches them only incidentally; the direct assertion names the warning sign"
  - "PROBLEM_EXAMPLE added beyond the plan: /docs shows a real 409 body beside the schema, copied from what the handlers emit. It carries no credential, identifier or internal path, because a real one does not either"

metrics:
  duration: ~35 min
  completed: 2026-09-19
  tasks: 3
  commits: 4
  tests-added: 14
  suite: 1115 passed, 100% coverage over 1690 statements
---

# Phase 7 Plan 01: The Published Error Body Summary

Every refusal the API documents now publishes the body a client has to parse — one `Problem`
component, 69 legs on `application/problem+json`, six described tags, and a gate that makes a bare
leg a red test.

## What Was Built

**`src/taskmanager/presentation/api/schemas/problem.py`** — `ProblemResponse`, the RFC 9457
document as published: the six D-06 members in contract order, then `errors` last and optional,
typed as the union of the two shapes the server really emits (a flat domain `details` object, or
the 422 list of `{field, message, type}` entries). Plus `PROBLEM_SCHEMA_NAME`, `PROBLEM_REF`,
`PROBLEM_EXAMPLE` and `problem_response(description)`, the one-leg helper. No `model=` key, and the
module docstring records the three rejected spellings as measurements rather than opinions.

**`src/taskmanager/main.py`** — `ProblemAwareFastAPI`, a `FastAPI` subclass whose `openapi()`
`setdefault`s the component into `components.schemas`, so the 69 `$ref`s resolve; and
`OPENAPI_TAGS`, six entries with a one-sentence description each, in registration order. The
factory's return annotation stays `FastAPI` and `isinstance(app, FastAPI)` is still true, so every
existing document test passes untouched.

**The five routers** — 69 legs rewritten from `{code: {"description": D}}` to
`{code: problem_response(D)}`. No description text changed, no 2xx leg, `response_model`,
`status_code` or summary touched, and `health.py` left alone entirely.

**`tests/architecture/test_openapi_completeness.py`** — the DOC-04 gate, seven tests reading
`create_app(...).openapi()`: the per-leg problem+json property, a direct no-`application/json`
assertion, the `$ref` resolving to a component whose `properties` are `ProblemResponse`'s fields,
tag and summary presence, tag set equality in both directions, and a non-vacuity guard that fails
rather than skips.

**`tests/unit/presentation/test_problem_schema.py`** — seven tests binding the model to the
builder, the leg helper to its media type, and the component registration to its idempotence.

## The Census, Measured After the Change

Read from `create_app(Settings(_env_file=None)).openapi()`:

| Property | Before | After |
|----------|--------|-------|
| Operations | 19 | 19 |
| Non-2xx legs | 70 | 70 |
| Legs publishing a schema | 1 | 70 |
| Legs on `application/problem+json` with a resolving `$ref` | 0 | **69** |
| Legs on `application/json` | 1 (`get /health 503`) | 1 (`get /health 503`) |
| Top-level `tags` array | absent (`None`) | 6 entries, each described |

Leg census unchanged: `401`x17, `403`x4, `404`x12, `409`x4, `422`x14, `500`x18, `503`x1.

## Gates Driven Red

Every new gate was falsified before it was trusted, and `git status --porcelain -- src/` was empty
after each revert. No `git stash`, no `git checkout -- src/`, no `git reset --hard` was used.

| Plant | Observed |
|-------|----------|
| Two `ProblemResponse` fields swapped | `test_problem_schema.py` red, 4 of 7 tests, naming the index |
| `schemas/problem.py` renamed | import fails at collection — a rename cannot pass silently |
| A name in `REQUIRED_SCANNED_MODULES` with no module | `test_the_presentation_api_package_is_actually_scanned` red |
| One `users.py` leg back to `{"description": ...}` | gate red: `Bare legs: ['get /api/v1/users 401']` |
| `"model": ProblemResponse` beside the `content` block | both the problem+json and the `application/json` tests red, naming the leg |
| One `OPENAPI_TAGS` entry dropped | `{'used but undescribed': ['users']}` |
| `EXEMPT_LEGS` emptied | `get /health 503` becomes an offender — the exemption is load bearing |
| `EXEMPT_LEGS` pointed at `/nope` | exemption test red: "is exempt from DOC-04 and does not exist" |

## Deviations from Plan

**1. [Rule 2 — correctness] `deepcopy(PROBLEM_REF)` instead of `dict(PROBLEM_REF)`**
- **Found during:** Task 1
- **Issue:** The plan specified `dict(PROBLEM_REF)` to give each leg a fresh object. `dict()` is a
  shallow copy, so the inner `{"$ref": ...}` dict would still have been shared by all 69 legs —
  the exact hazard the instruction was written to remove.
- **Fix:** `copy.deepcopy`, plus `test_two_legs_share_no_mutable_object`, which mutates one leg's
  `$ref` and asserts the next leg is unaffected.
- **Commit:** 5853aa9

**2. [Scope note] The `grep -rc "application/json"` acceptance criterion was already unsatisfiable**
- **Found during:** Task 2
- **Issue:** The criterion asks for 0 in all five routers. `routers/task_lists.py:289` contains the
  string inside a `response_description` paragraph explaining why a 204 carries no
  `Content-Type` — prose, present before this plan, and unrelated to any error leg.
- **Resolution:** Not touched. The property the criterion is a proxy for is asserted directly
  against the published document by `test_no_error_leg_advertises_plain_json`, which is stronger:
  it would catch a leg that acquired the media type through a `model=` key without the literal
  ever appearing in a router.

**3. [Addition] `PROBLEM_EXAMPLE`**
- A `json_schema_extra` example on `ProblemResponse`, so `/docs` shows a real 409 body beside the
  schema. Beyond the plan's letter, squarely inside DOC-04's intent. It affects no `properties`
  key, so the gate's schema assertion is unchanged.

## Verification

- `make lint`, `make typecheck`, `make arch`, `make test` — all green.
- `make test`: **1115 passed**, 100% coverage over 1690 statements (was 1101 / 1659). No
  `# pragma: no cover`, no coverage `omit`, threshold untouched at 75.
- `make arch`: 4 contracts kept, 0 broken.
- The one-off `app.openapi()` census above was executed in-session against the real factory.

## For the Next Plans

**07-02 (DECISION_LOG)** needs ADRs for two decisions this plan took, both already argued in
docstrings that can be transcribed:
1. **The error-leg spelling and the `FastAPI` subclass.** Context: 69 legs published no schema.
   Options: the four measured spellings in `07-RESEARCH.md` Gap 3, plus `app.openapi = fn` vs a
   subclass. Decision: the no-`model` form with `ProblemAwareFastAPI`. Consequences: the component
   is registered outside FastAPI's own machinery, so a future leg that *does* want a different
   model must not assume the registration is automatic. Rejected: `{"model": ProblemResponse}`,
   which publishes `application/json` — a media type this API never emits for an error.
2. **The `/health` 503 exemption, restated as a gate.** D-08 already decided that `/health` is a
   status document; what is new is `EXEMPT_LEGS` and the test keeping the exemption tied to the
   leg. Worth an ADR because it is the single documented hole in a totality rule.

Also note for 07-02's curated ambiguity block: nothing here changes any of the five brief
ambiguities. The two missing ADRs (statuses/transitions, priorities) are untouched by this plan.

**07-04 (README)** can now state, and gate against, three facts that are mechanically true:
- Every route's refusals are documented with a parseable body; the endpoint table can cite
  `/openapi.json` as its source, per `07-RESEARCH.md` §Don't Hand-Roll.
- `/docs` groups the six tags in a deliberate order with descriptions — the README's endpoint
  overview should use the same six names and the same order: health, auth, task lists, tasks,
  users, assignments.
- The one honest exception to "errors are RFC 9457 problem+json from every route" is `GET /health`,
  whose 503 is a `HealthResponse`. The OpenAPI `DESCRIPTION` in `main.py` says "from every route";
  if the README repeats that sentence it should carry the `/health` caveat, or the two documents
  disagree by one leg.

**07-05 (rehearsal)** — no new command, no new hook, no new CI step was added. The gate rides
inside `pytest`, so `make test`, the Docker `test` stage and CI already run it.

## Self-Check: PASSED

- `src/taskmanager/presentation/api/schemas/problem.py` — FOUND
- `tests/unit/presentation/test_problem_schema.py` — FOUND
- `tests/architecture/test_openapi_completeness.py` — FOUND
- Commits 5853aa9, 4963218, e008afe — FOUND in `git log`
