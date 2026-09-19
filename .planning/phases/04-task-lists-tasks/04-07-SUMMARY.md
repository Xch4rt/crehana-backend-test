---
phase: 04-task-lists-tasks
plan: 07
subsystem: presentation
tags: [pydantic, schemas, merge-patch, rfc-7396, d-05, d-06, d-08, d-09, actor-seam, fastapi-depends]

# Dependency graph
requires:
  - phase: 04-task-lists-tasks
    provides: "04-01's Unset sentinel and Task.DEFAULT_PRIORITY, the single copy of TASK-01's medium"
  - phase: 04-task-lists-tasks
    provides: "04-04's commands (the two X | Unset update commands) and results (TaskResult, TaskListResult, the flat TaskCollectionResult)"
  - phase: 03-persistence
    provides: "get_uow and the Annotated[T, Depends(...)] alias pattern in dependencies.py; SystemClock as the Clock adapter"
  - phase: 02-domain-error-contract
    provides: "the Clock port, and Phase 2 D-04 — business limits live in the entity only"
provides:
  - "get_current_actor / CurrentActor — the single source of caller identity, and the only body Phase 5 rewrites"
  - "DEMO_USER_ID as a Final v4 UUID the entrypoint seed can import without the database stack"
  - "get_clock, UnitOfWorkDependency and ClockDependency — the three things 04-08's routers inject"
  - "schemas/task_lists.py and schemas/tasks.py: eight Pydantic models typing every HTTP boundary of the phase"
  - "to_command() as the one place model_fields_set becomes the application's not-provided marker"
  - "D-08 as a reproducible 422 at body.status rather than a sentence in a document"
affects: [04-08, 04-09, 04-10, 04-11, 04-12, 05]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A non-nullable PATCH field is mapped with `value is not None`, a nullable one with membership in model_fields_set — the same question for the first, and the only form mypy can narrow to a non-optional command field"
    - "The explicit-null 422 is a field_validator that runs only on a sent value, because Pydantic does not validate defaults"
    - "Absence is the proof: `status` is not declared, so extra=\"forbid\" turns sending it into a 422 naming the key"
    - "A response model copies its result field by field in from_result, never model_validate"
    - "A business limit is refused at the boundary by inspecting a field's constraint metadata in a test, not by remembering a rule"

key-files:
  created:
    - src/taskmanager/presentation/api/actor.py
    - src/taskmanager/presentation/api/schemas/__init__.py
    - src/taskmanager/presentation/api/schemas/task_lists.py
    - src/taskmanager/presentation/api/schemas/tasks.py
    - tests/unit/presentation/test_actor.py
    - tests/unit/presentation/test_schemas.py
  modified:
    - src/taskmanager/presentation/api/dependencies.py

key-decisions:
  - "A non-nullable PATCH field is mapped as `self.name if self.name is not None else UNSET`, NOT the plan's and 04-RESEARCH's `\"name\" in sent` — the membership form leaves the value `str | None` and mypy strict refuses to pass it to a `str | Unset` field. The two questions are identical for those fields because the field validator has already refused an explicit null, so `None` can only mean absent; the nullable fields keep the membership form, where absence genuinely cannot be read off the value"
  - "grep -c \"Unset\" prints 0 on both schema modules, not the plan's 1. The criterion's stated intent is 'the UNSET import used inside to_command only', and importing the sentinel by name gives the uppercase spelling, which the mixed-case pattern does not match. 0 is the stronger reading: the sentinel TYPE is never named at all, in an annotation or anywhere else — grep -c \"UNSET\" prints 3 on task_lists.py and 5 on tasks.py, every one of them the import or a to_command argument"
  - "The forbidden forms are described in prose and never spelled literally — the project's convention since 01-03, and here it is what keeps grep -c \"max_length\" honestly at 0 rather than at 0-except-the-comment"
  - "get_clock takes no Request and stores nothing on app.state: SystemClock is stateless and one allocation per request costs nothing, so the narrowing _resources exists for does not apply. A test asserts two calls return different objects, so the absence of caching is pinned"
  - "CurrentActor is tested by inspecting typing.get_args(CurrentActor) rather than by calling through FastAPI, so a refactor that repointed the alias at a different provider fails here — every router will spell the alias, not the function"
  - "The 'not authentication' phrase is asserted against inspect.getsource, not __doc__, so moving the sentence into a comment beside the function still satisfies D-03's honesty requirement"
  - "The status-change request needs no at-least-one-field validator: its single field is required, so an empty body is already a `missing` error at body.status"
  - "Requirement ticks ARC-05 / TASK-01 / TASK-03 / TASK-06 deliberately NOT taken — 04-12 is the last claimant, the seventh consecutive plan in this phase to make the same call, and this plan ships the boundary with no route above it"

patterns-established:
  - "Three legs per patchable field, per model: omitted reaches the command as the marker, provided reaches it as the value, explicit null either clears the field or is a field-level 422"
  - "A field-set assertion on the class beside every mapper, because mypy cannot check a string against model_fields (04-RESEARCH Pitfall 7)"
  - "A declaration-order assertion on every response model, because Pydantic serialises in declaration order and the order is the wire contract"
  - "A collection test whose statistics deliberately disagree with its item count, so a mapper that derived the counters from items fails"

requirements-completed: []

# Metrics
duration: 10min
completed: 2026-09-19
---

# Phase 4 Plan 07: the actor seam and the Pydantic boundary Summary

**Every HTTP boundary this phase crosses is now typed by a Pydantic v2 model, D-05/D-06/D-08 are mechanical rather than promised — `{}`, an unknown key, an explicit null on a non-nullable field and `status` in the generic PATCH are each a 422 with a measured `loc` and `type` — and caller identity has exactly one source, which says in its own words that it is not authentication.**

## Performance

- **Duration:** ~10 min (23:53 → 00:03)
- **Tasks:** 3 of 3, one commit each
- **Files:** 6 created, 1 modified

## Accomplishments

- **One place to ask who is calling, and it is honest about what it is.** `presentation/api/actor.py` holds `DEMO_USER_ID` as a `Final` version-4 UUID, a parameterless `get_current_actor() -> UUID`, and the `CurrentActor` alias every Phase 4 router will spell. The module docstring says **"not authentication"** in those words, and `test_the_module_says_it_is_not_authentication` reads the source back so an edit cannot quietly drop the sentence (T-4-37). It is a module of its own for the two reasons D-01/D-03 give: the entrypoint's demo-user seed imports the constant — `grep -c "sqlalchemy" actor.py` prints `0`, so the import stays cheap — and Phase 5 deletes a file rather than editing one.
- **The identifier is a constant, and `.env.example` gained no key.** D-03 holds mechanically: `grep -c "DEMO_USER_ID" .env.example` prints `0` and 01-02's parity test (`test_env_example_documents_every_field`) still passes, so a `cp .env.example .env` is unchanged for an evaluator.
- **`get_clock` joins `get_uow`, annotated with the port.** A plain `def`, no `Request`, no `app.state`, `Clock` as the return type — so a test that wants a frozen instant overrides a provider rather than changing a signature. `UnitOfWorkDependency` and `ClockDependency` sit beside it as the two aliases the routers share; a one-line comment points at `health.py` L47-L54 for the B008 argument rather than re-litigating it.
- **Eight Pydantic models, and ARC-05 is true of the whole slice.** `schemas/task_lists.py` carries `TaskListCreateRequest`, `TaskListPatchRequest` and `TaskListResponse`; `schemas/tasks.py` carries `TaskCreateRequest`, `TaskPatchRequest`, `TaskStatusChangeRequest`, `TaskResponse` and the D-09 envelope `TaskCollectionResponse`. Both modules are at **100% coverage with no pragma and no omit**.
- **D-08 is now a request an evaluator can make.** `status` is not a field of `TaskPatchRequest` at all, and with `extra="forbid"` sending it produces exactly one error, `extra_forbidden` at `("status",)` — asserted with `len(errors) == 1` so a future model that both declared the field and refused it would still fail. The absence is asserted twice: as a membership test by name, and as an exact field set.
- **Every PATCH leg from 04-RESEARCH's measured table is reproduced as a test.** `{}` → `value_error` mentioning *at least one field*; `{"titel": …}` → `extra_forbidden` at `("titel",)`; `{"title": null}` → `value_error` at `("title",)`; `{"description": null}` → the command carries `None` while `name`/`title` carries the marker. Six patchable fields across the two models, three legs each.
- **The marker never reaches the wire.** `to_command` is the only place it is produced; `grep -c "Unset"` prints `0` on both schema modules, so the sentinel type is not named even in an annotation, and `/openapi.json` cannot gain the `_Unset` component 04-RESEARCH measured (T-4-40).
- **TASK-01's `medium` still exists exactly once.** `TaskCreateRequest.priority` defaults to `Task.DEFAULT_PRIORITY`, so OpenAPI documents the default the entity will actually apply, and the test asserts identity against the ClassVar rather than spelling `"medium"` — a test that named the value would become a third copy of the rule it protects.
- **No business limit and no past-date rule crossed into presentation.** `grep -c "max_length"` prints `0` on both modules, and `_declares_no_length_limit` inspects each field's constraint metadata so an equivalent constraint spelled another way is caught too (Phase 2 D-04). `due_date` carries no past-date validator: a second copy would drift from `Task.reschedule` *and* would answer with the request-validation error shape instead of the domain's.
- **Mass assignment has no surface left.** No Phase 4 request model declares `owner_id`, `assignee_id`, `completed_at` or `status`; `actor_id` reaches a command only as a keyword to `to_command`, whose value the router takes from `CurrentActor` (T-4-35, T-4-36). The enum-typed `status` and `priority` fields give the free 422 that stops a value ever reaching SQL as free text, with no membership check written anywhere (T-4-39).
- **Neither response model can leak.** Both `from_result` classmethods name every field explicitly, and declaration-order tests pin D-10's nine members and D-09's four (T-4-41). The collection test gives two items and counters that say four, so a mapper that derived the statistics from `items` rather than copying them fails.

## Task Commits

1. **Task 1: the actor seam and the `Clock` provider** — `c161047` (feat)
2. **Task 2: task-list request and response schemas** — `1d40d2d` (feat)
3. **Task 3: task request, response and collection schemas** — `6b63a58` (feat)

**Plan metadata:** see the final `docs(04-07)` commit.

## Files Created

| File | Statements | Coverage | Notes |
|------|-----------:|---------:|-------|
| `presentation/api/actor.py` | 7 | 100% | D-01/D-03; no `sqlalchemy`, no setting |
| `presentation/api/schemas/__init__.py` | 0 | 100% | empty, mirroring `errors/__init__.py` |
| `presentation/api/schemas/task_lists.py` | 36 | 100% | 3 models, D-05/D-06/D-10 |
| `presentation/api/schemas/tasks.py` | 51 | 100% | 5 models, D-05/D-06/D-08/D-09/D-11 |
| `tests/unit/presentation/test_actor.py` | — | — | 7 tests |
| `tests/unit/presentation/test_schemas.py` | — | — | 49 tests |

## Files Modified

| File | Change |
|------|--------|
| `presentation/api/dependencies.py` | `+ get_clock() -> Clock`, `+ UnitOfWorkDependency`, `+ ClockDependency` |

## Gate Results

| Gate | Result |
|------|--------|
| `make lint` | black / isort / flake8 — clean |
| `make typecheck` | `mypy src tests` strict — 131 source files, no issues |
| `make arch` | 4 contracts kept, 0 broken |
| `make test` | **514 passed**, coverage **100.00%** (gate 75%) |
| `pytest tests/unit tests/architecture -q --no-cov` | 414 passed |
| `grep -rn "max_length" src/.../schemas/` | nothing |
| `test_env_example_documents_every_field` | passes — `.env.example` gained no key (D-03) |

## Deviations from Plan

### 1. [Rule 3 — blocking] The non-nullable PATCH mapper uses `is not None`, not `"field" in sent`

- **Found during:** Task 2, repeated in Task 3.
- **Issue:** the plan's `<interfaces>` block and 04-RESEARCH Pattern 2 both write every mapper leg as `self.title if "title" in sent else UNSET`. Under `mypy --strict` that expression has type `str | None | Unset`, and `UpdateTaskCommand.title` is `str | Unset` — the membership test is a runtime question the type checker cannot use to narrow, so the form does not type-check at all.
- **Fix:** the two **non-nullable** fields per model (`name`; `title` and `priority`) are mapped with `self.name if self.name is not None else UNSET`, which narrows cleanly. The equivalence is exact rather than convenient: the field validator has already refused an explicit null for precisely those fields, so a `None` at `to_command` time can only mean the key was absent. The **nullable** fields (`description`, `due_date`) keep the membership form, because there `None` is a legitimate value and absence genuinely cannot be read off it.
- **Why not a cast or an assert:** a `cast` asserts something the type checker then stops checking, and an `assert` adds a branch the no-`pragma` coverage rule would need an unreachable test for.
- **Proof it is not D-05's failure mode in disguise:** `test_an_explicitly_null_name_is_refused`, `test_an_explicitly_null_task_title_is_refused` and `test_an_explicitly_null_priority_is_refused` each assert a `value_error` at the field — so the case where the two questions could diverge never reaches the mapper.
- **Files:** `schemas/task_lists.py`, `schemas/tasks.py`
- **Commits:** `1d40d2d`, `6b63a58`

### 2. `grep -c "Unset"` prints `0` per schema module, not the plan's `1`

- **Found during:** Task 2 acceptance check.
- **Issue:** the criterion reads *"prints `1` — the `UNSET` import used inside `to_command` only"*. `grep` is case-sensitive, and importing the sentinel by name gives `from taskmanager.application.dto.unset import UNSET` — no mixed-case `Unset` anywhere. The literal count is therefore `0`.
- **Resolution:** recorded rather than manufactured. Adding a prose mention of the type to reach `1` would satisfy a counter by weakening the property; `0` is the stronger statement — the sentinel **type** is never named at all, so it cannot appear in a field annotation or a default by any route. The criterion's actual subject, the sentinel value, is counted honestly: `grep -c "UNSET"` prints `3` on `task_lists.py` and `5` on `tasks.py`, every match being the import line or a `to_command` argument. The 04-03 and 04-06 precedent for a grep criterion met in substance rather than literally.
- **Files:** `schemas/task_lists.py`, `schemas/tasks.py`

### 3. Both schema modules declare their refusal messages as constants

- **Found during:** Task 2.
- **Issue:** not a plan requirement either way. The tests assert the message a client receives; a literal repeated between module and test can drift silently.
- **Fix:** `NULL_REJECTED_MESSAGE` and `EMPTY_PATCH_MESSAGE` are module constants. They are **re-declared** in `tasks.py` rather than imported from `task_lists.py` — deliberately, so that changing one endpoint's wording cannot silently change the other's.
- **Files:** `schemas/task_lists.py`, `schemas/tasks.py`
- **Commits:** `1d40d2d`, `6b63a58`

### 4. Test count exceeds the plan's floors

- Task 1 asked for at least 5 tests in `test_actor.py`; it has **7** (the `Clock` provider's two are separate from the seam's five).
- Task 2 asked for at least 12 in `test_schemas.py`; it had **16** at that commit.
- Task 3 asked for at least 28; the file has **49**. The excess is the three legs × six patchable fields, written out rather than parametrized so that a failure names the field and the leg in the pytest report.

## Authentication Gates

None. This plan builds the seam that *stands in* for authentication; no credential, token or external login was needed to execute it.

## Threat Flags

None. No new network endpoint, file access pattern or schema change: this plan adds boundary types and a provider, with no route above them yet. Every threat in the plan's register is mitigated by a named test:

| Threat | Mitigated by |
|--------|--------------|
| T-4-35 mass assignment | `extra="forbid"` on all five request models; `test_status_is_not_a_field_of_the_task_patch_schema`, `test_sending_a_status_to_the_generic_patch_is_refused_at_that_key`, `test_the_create_request_refuses_an_unknown_key` (which sends `owner_id`) |
| T-4-36 client-supplied actor | no request model declares `actor_id`; `test_the_create_command_binds_the_body_to_the_caller`, `test_the_patch_command_carries_the_identifiers_it_was_handed` |
| T-4-37 the seam mistaken for auth | `test_the_module_says_it_is_not_authentication` |
| T-4-38 the demo identity as an account | the seed's unverifiable `password_hash` is named in `actor.py`'s docstring; the row itself arrives with 04-08's entrypoint step |
| T-4-39 free-text filter or status | enum-typed fields; `test_an_unknown_priority_is_refused_by_the_enum`, `test_an_unknown_status_is_refused_by_the_enum` |
| T-4-40 the marker in `/openapi.json` | `grep -c "Unset"` prints `0` on both modules |
| T-4-41 auto-published result field | explicit `from_result` per response model + `test_the_list_response_declares_d_10_s_members_in_order`, `test_the_task_response_declares_its_eleven_members_in_order`, `test_the_collection_declares_d_09_s_four_members_in_order` |
| T-4-42 a typo in the mapper | `test_the_patch_schema_declares_exactly_the_two_patchable_fields`, `test_the_task_patch_schema_declares_exactly_the_four_patchable_fields`, plus every three-leg test |

## Known Stubs

None in the sense the check means. `get_current_actor` returns a fixed value, but it is a **deliberate, documented, dated seam** (D-01), not an unwired placeholder: it is the production implementation for Phase 4's scope, its honesty is asserted by a test, and 04-12 owes it an ADR.

## Handoff Notes

- **04-08 (routers):** inject `CurrentActor`, `UnitOfWorkDependency` and `ClockDependency` as annotations, never as argument defaults — B008 in `make lint` is the gate, and it matches the call name as written.
- **04-08:** call `to_command(...)` on the request model and pass the result to the use case. Do **not** build a command in the router: the marker conversion lives in one place, and a router that passed `None` for an omitted field would clear a description or a deadline (04-06's handoff note, now enforceable).
- **04-08:** annotate every handler `-> TaskResponse` / `-> TaskListResponse` / `-> TaskCollectionResponse`, or pass `response_model=` explicitly. A handler annotated with a *result DTO* makes FastAPI infer the schema from the dataclass, and ARC-05's boundary claim quietly stops being true (04-RESEARCH Pattern 10).
- **04-08 (entrypoint seed):** import `DEMO_USER_ID` from `taskmanager.presentation.api.actor`. The module imports only `typing`, `uuid` and `fastapi`, so the seed stays a small script.
- **04-09 (integration):** a second actor is obtained with `app.dependency_overrides[get_current_actor] = lambda: other_id` — the only way to reach D-04's "not owned → 404" legs over HTTP, so the fixture must expose it.
- **04-09:** the measured `loc` values are `("status",)`, `("titel",)`, `("title",)` at the model level; over HTTP they arrive prefixed with `body`, i.e. `body.status`. The unit tests here assert the model-level tuples; the integration tests own the `body`-prefixed form.
- **04-12 (ADRs):** two entries owed — the seam as a deliberate temporary placeholder that is not authentication (D-01/D-03), and the non-nullable PATCH mapper's `is not None` form with the mypy reason (Deviation 1 above).

## Self-Check: PASSED

- `src/taskmanager/presentation/api/actor.py` — FOUND, contains `DEMO_USER_ID`, `get_current_actor`, `CurrentActor`
- `src/taskmanager/presentation/api/schemas/__init__.py` — FOUND (empty)
- `src/taskmanager/presentation/api/schemas/task_lists.py` — FOUND, contains `extra="forbid"`
- `src/taskmanager/presentation/api/schemas/tasks.py` — FOUND, contains `extra="forbid"`, `model_fields_set`, `DEFAULT_PRIORITY`
- `tests/unit/presentation/test_actor.py` — FOUND, 7 tests passing
- `tests/unit/presentation/test_schemas.py` — FOUND, 49 tests passing
- `src/taskmanager/presentation/api/dependencies.py` — FOUND, contains `get_clock`, `UnitOfWorkDependency`, `ClockDependency`
- commit `c161047` — FOUND
- commit `1d40d2d` — FOUND
- commit `6b63a58` — FOUND
