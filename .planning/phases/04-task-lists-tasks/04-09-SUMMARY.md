---
phase: 04-task-lists-tasks
plan: 09
subsystem: tests
tags: [integration, httpx, asgitransport, d-16, d-17, d-04, d-05, d-12, rfc-9457, list-01, list-06]

# Dependency graph
requires:
  - phase: 04-task-lists-tasks
    provides: "04-08's five task-list routes on the composed app, and the OpenAPI-not-app.routes finding"
  - phase: 04-task-lists-tasks
    provides: "04-07's get_current_actor seam and the UnitOfWorkDependency / ClockDependency providers this harness overrides"
  - phase: 03-persistence-runnable-stack
    provides: "the D-01 connection fixture, the create_savepoint session factory, migrated_database and the D-03 fail-fast probe"
  - phase: 03-persistence-runnable-stack
    provides: "get_uow, SqlAlchemyUnitOfWork and the IntegrityError translation the 409 legs exercise"
  - phase: 02-domain-error-contract
    provides: "register_exception_handlers, the RFC 9457 member list and the two 422 producers the refusal matrix splits on"
provides:
  - "tests/integration/conftest.py — api_client, acting_as, statements, seed: the harness every module under tests/integration/api/ needs"
  - "tests/integration/api/test_task_lists.py — 31 HTTP tests covering LIST-01..LIST-06 end to end"
  - "the statements recorder 04-11 asserts D-17's no-N+1 claim with"
  - "the seeding helper, the entity builders and the problem-body assertion style 04-10 reuses verbatim"
affects: [04-10, 04-11, 04-12, 05, 06]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "api_client yields a (AsyncClient, FastAPI) pair, because overriding get_current_actor is the only way to reach D-04's not-owned legs over HTTP and a test cannot override a provider on an application it cannot name"
    - "A seeding session must commit(): under join_transaction_mode=create_savepoint, closing without committing rolls the savepoint back and the seeded rows vanish"
    - "Seeds flush per reference level — users, then lists, then tasks — because TaskListRow has a ForeignKey but no relationship, so SQLAlchemy has no edge to order a mixed batch by"
    - "The statement recorder filters to SELECT/INSERT/UPDATE/DELETE: the raw before_cursor_execute stream for one GET is SAVEPOINT, SELECT, ROLLBACK"
    - "acting_as is a restoring context manager, not a one-way setter, so a test cannot silently remain a stranger after proving a 404"
    - "A not-owned body is compared to an absent body with the identifier tokenised out, which compares instance too rather than excusing it"
    - "Every mutating test re-reads through the API, so 'it was written' is a fact about the database rather than the return value of the handler that claimed to write it"

key-files:
  created:
    - tests/integration/api/__init__.py
    - tests/integration/api/test_task_lists.py
  modified:
    - tests/integration/conftest.py

key-decisions:
  - "The not-owned body is compared to the absent body with each response's own identifier replaced by a fixed token, which is STRONGER than the plan's 'identical apart from instance'. The two bodies necessarily mention two different ids — in detail, in errors and in instance, which is the request path — so excusing instance would leave the path uncompared; tokenising compares it modulo the id, and a difference in code, title or the presence of an errors member is caught either way (D-04, T-4-51/T-4-52)"
  - "PROBLEM_JSON and MEMBERS are IMPORTED from tests/api/test_error_contract.py rather than re-declared. The plan's acceptance criterion `grep -c \"application/problem+json\"` therefore prints 0 while `grep -c \"PROBLEM_JSON\"` prints 10 — met in substance, not literally, the call 04-03/04-06/04-07 made for the same kind of counter. Sixteen error responses assert the media type across nine spellings; a tenth copy of a constant that already has a single home would have satisfied a number by abandoning the reason the number exists"
  - "The two 409 tests are named ..._is_a_duplicate_409 rather than the plan's ..._is_409, because pytest's -k matches the test id and the plan's own names contain no 'duplicate' — its criterion `-k duplicate` collects at least 2 would have collected 0 against the names it prescribed. The prose the plan wanted is kept intact and the word is appended"
  - "The 404 legs ship as six tests, three of which issue BOTH requests. The three not-owned tests make the absent-id request too so they can compare the bodies; the three absent-id tests stand alone because a comparison that only ever runs inside the not-owned test would disappear with it"
  - "api_client does NOT enter the lifespan. get_uow is overridden, so the engine create_app built against the fictional DSN is never dialled; tests/integration/test_health.py remains the one place the engine's own lifecycle is proven, against an application deliberately pointed at the live database"
  - "Timestamps off the wire are compared as instants, not as text. Both ISO-8601 strings happen to sort correctly for the pairs asserted here and would stop doing so the first time one landed on a whole second, since Pydantic omits microseconds it does not have — a flake months away rather than a failure today"
  - "Requirement ticks LIST-01..LIST-06 deliberately NOT taken — 04-12 is the last claimant, the ninth consecutive plan in this phase to make the same call. The behaviour is now proved over HTTP, which is the evidence 04-12 will tick from"

patterns-established:
  - "One module-level assert_not_found(response, id) helper, so the six 404 legs cannot disagree about what a 404 looks like"
  - "Entity builders (a_user, a_task_list, a_task) that derive coupled fields — a completed task's completed_at — so a fixture cannot construct a combination the entity refuses"
  - "The 422 tests are named after which of the two producers they hit, so the list-vs-object errors shape is readable from the report rather than from the body"
  - "The ordering test asserts the two created_at values are equal before asserting the id tie-break, so the tie-break cannot go unexercised while the test still passes"

requirements-completed: []

# Metrics
duration: 10min
completed: 2026-09-19
---

# Phase 4 Plan 09: the HTTP integration harness and the five task-list routes Summary

**The two halves of the test suite that had never met — an application built against a fictional DSN, and a PostgreSQL connection nothing escapes — are now joined by a single `dependency_overrides[get_uow]`, and the first thing driven through the join is the whole task-list surface: 31 tests over real HTTP against real PostgreSQL, every success path asserted on the body and re-read through the API, every refusal asserted with its problem+json shape, and a list you do not own answering byte-for-byte like one that does not exist.**

## Performance

- **Duration:** ~10 min (00:19 → 00:29 UTC)
- **Tasks:** 3 of 3, one commit each
- **Files:** 2 created, 1 modified (+1156 lines)

## Accomplishments

- **The harness exists, and it worked on the first run.** `api_client` builds the real `create_app` output, overrides `get_uow` to hand out a `SqlAlchemyUnitOfWork` over the connection-bound session factory, and yields the client beside the application. A `POST` runs the real use case, which opens its own session on the shared connection and commits; the `GET` that follows opens another and reads the row back; the `connection` fixture discards the lot at teardown. The two smoke tests at the top of the module are the dullest thing in it and the first thing that would fail if any of that were wrong.
- **The savepoint rule the research warned about is now written down where it bites.** `seed()` commits, and its docstring says why: under `join_transaction_mode="create_savepoint"`, closing a session without committing rolls its savepoint back, so the seeded user silently disappears and the first request answers 404 — or a foreign-key translation reports `user_not_found` naming an actor the test plainly created. Committing releases the savepoint into the transaction the `connection` fixture owns, which still rolls the whole thing back. Isolation is exactly as strong as it was; visibility is what the commit buys.
- **The second actor is reachable, and reversible.** `acting_as(app, user_id)` is a context manager that restores the previous override — including none — on exit. A one-way setter would leave a test that proved a 404 and then asserted the owner's own view silently still a stranger, and that second assertion would pass for the wrong reason or fail pointing at the route instead of at the fixture.
- **The D-17 recorder is in place for 04-11.** `statements` listens on `connection.sync_connection` and keeps only `SELECT`/`INSERT`/`UPDATE`/`DELETE`. The filter is the fixture: the measured raw stream for one `GET` through the full stack is `SAVEPOINT`, `SELECT`, `ROLLBACK`, and counting the bracketing would make the number mean "callbacks the engine emitted" rather than "statements the database was asked to run".
- **LIST-01..LIST-05 are provable over HTTP.** Create asserts 201, the nine-member body in declaration order, `total_tasks`/`completed_tasks`/`completion_percentage` at `0`/`0`/`0.0`, a `Location` header that is then **followed** and compared body-to-body. Get asserts 3 tasks, 2 completed, 66.67. The collection asserts two lists with *different* mixes — equal counters would pass against a grouped query that computed one list's statistics and repeated them. Three PATCH legs (name only, description only, explicit `null`) each re-read through `GET` and assert the untouched field unchanged and `updated_at` moved. Delete asserts 204, an empty body, and **no `content-type` header at all**, which is the measured difference `response_class=Response` makes.
- **D-12's cascade is asserted twice, from both sides.** The list and its two tasks are created *through the API*, the list is deleted, the tasks collection answers 404 — and then a `SqlAlchemyTaskRepository` read on the shared session confirms both task ids return `None`. The API half alone could not tell a cascade from an orphaning.
- **A list you do not own is indistinguishable from one that does not exist, and that is a body comparison.** One test per verb acts as a second user against a demo-owned list, issues the absent-id request as well, and compares the two serialised bodies with each response's own identifier replaced by a fixed token — so `code`, `title`, `detail`, `errors` **and** `instance` are all compared. The PATCH and DELETE tests then read the list back as its owner and confirm the refusal was total rather than half-applied.
- **Both 409 legs, and all three non-conflicts.** Duplicate on create and duplicate on rename, each asserting `duplicate_task_list_name` and `errors == {"field": "name", "name": ...}`; plus a name another actor already uses (uniqueness is per owner), a name differing only in case (D-12, case-sensitive), and a rename to the row's own current name — the guard that stops a list conflicting with itself.
- **The 422 matrix is split by producer, in the test names.** The **list** shape: an empty PATCH body (`field: body`, `type: value_error`), an unknown key (`field: body.nmae`, `type: extra_forbidden` — which is also T-4-54's mass-assignment proof), an explicit null `name`, and a malformed path UUID (`field: path.list_id`). The **object** shape: a blank name and an over-length one, both `errors == {"field": "name"}`, with the over-length string built from `TaskList.NAME_MAX_LENGTH + 1` so it cannot drift from the entity.
- **A refusal echoes nothing.** A marker string goes in as an over-length name; the test asserts the marker, `input` and `ctx` are all absent from the response text — the HTTP counterpart of Phase 2's `test_validation_problem_never_echoes_the_client_input` (T-4-53).
- **`routers/task_lists.py` is at 100%, from these tests alone.** Measured with `--cov=taskmanager.presentation.api.routers.task_lists` over `tests/integration/api` only: 39 statements, 0 missing. The remaining gap in the presentation layer is `routers/tasks.py` (84%) and `schemas/tasks.py`, both owed to 04-10.

## Task Commits

1. **Task 1: the `api_client`, actor-override and `statements` fixtures** — `6a0f3be` (test)
2. **Task 2: the five task-list routes over HTTP, success paths** — `0bd8b50` (test)
3. **Task 3: the refusal matrix — 404, 409 twice, and the 422 split** — `3109b18` (test)

**Plan metadata:** see the final `docs(04-09)` commit.

## Files Created

| File | Contents | Notes |
|------|----------|-------|
| `tests/integration/api/__init__.py` | 0 lines | package init, mirroring `tests/integration/__init__.py` |
| `tests/integration/api/test_task_lists.py` | 965 lines, 31 tests | the whole task-list surface |

## Files Modified

| File | Change |
|------|--------|
| `tests/integration/conftest.py` | `+194` lines: `api_client`, `acting_as`, `statements`, `seed` |

## Gate Results

| Gate | Result |
|------|--------|
| `make lint` (black, isort, flake8) | PASS — 137 files unchanged, no findings |
| `make typecheck` (mypy strict) | PASS — no issues in 137 source files |
| `make arch` (import-linter) | PASS — 4 contracts kept, 0 broken |
| `make test` | PASS — **551 passed**, `Required test coverage of 75% reached. Total coverage: 99.36%` |
| `pytest tests/integration -x --no-cov -q` | PASS — 114 passed, the whole Phase 3 integration suite included |
| `grep -rn "TestClient" tests/` | prints nothing |
| `--cov=...routers.task_lists` over `tests/integration/api` | 39 statements, **0 missing**, 100% |

Baseline before this plan was 520 passed / 98.25%; the 31 new tests took it to 551 / 99.36%, and the increase is entirely the task-list router's handler bodies.

## Acceptance Criteria

Every criterion the plan wrote is met, with two exceptions recorded below and one met in substance.

| Criterion | Result |
|-----------|--------|
| `pytest tests/integration/api` ≥ 2 then ≥ 12 then ≥ 30 tests | 31 |
| `-k duplicate` ≥ 2 | 2 (after the rename recorded in Deviations) |
| `-k "not_own or does_not_own"` ≥ 3 | 3 |
| `-k create` ≥ 2, `-k delete` ≥ 2, `-k patch` ≥ 3 | 4, 3, 7 |
| `grep -c "dependency_overrides"` conftest ≥ 1 | 5 |
| `grep -c "get_current_actor"` conftest ≥ 1 | 6 |
| `grep -c "before_cursor_execute"` conftest ≥ 2 | 3 |
| `grep -c "commit()"` conftest ≥ 1 | 2 |
| `grep -rc "TestClient" tests/` = 0 everywhere | 0 |
| `grep -c "response.json()"` ≥ 12 | 23 |
| `grep -c "66.67"` ≥ 1, `"Location"` ≥ 1 | 2, 4 |
| `grep -c "task_list_not_found"` ≥ 3 | 3 |
| `grep -c "NAME_MAX_LENGTH"` ≥ 1 | 4 |
| `grep -c "application/problem+json"` ≥ 10 | **0** — see Deviations; `grep -c "PROBLEM_JSON"` prints 10 |

## Deviations from Plan

### Auto-fixed issues

None. No bug, no missing critical functionality and no blocker was encountered — the harness from `04-RESEARCH` Pattern 7 worked on its first execution, and all three task verifications passed on their first run.

### Judgement calls recorded

**1. [Naming] The two 409 tests carry `duplicate` in their names**

- **Found during:** Task 3
- **Issue:** The plan prescribes `test_creating_a_list_with_a_name_the_actor_already_uses_is_409` and its rename counterpart, *and* an acceptance criterion of `pytest -k duplicate` collecting at least 2. pytest's `-k` matches the test id; neither prescribed name contains the word, so the criterion would have collected 0 against the names the same plan wrote.
- **Fix:** the names end `..._is_a_duplicate_409`. The plan's prose is intact and the counter is met literally.

**2. [Counter met in substance] `grep -c "application/problem+json"` prints 0**

- **Found during:** Task 3
- **Issue:** the criterion expects the media type spelled ≥ 10 times. `PROBLEM_JSON` and `MEMBERS` already have a single home in `tests/api/test_error_contract.py`, which the plan itself names as the source of the assertion style; spelling the literal ten times would have added a tenth copy of a constant.
- **Resolution:** the two names are imported, `grep -c "PROBLEM_JSON"` prints 10, and sixteen error responses assert the media type across nine spellings plus one shared `assert_not_found` helper. The same call 04-03, 04-06 and 04-07 made for counters of this kind. A rename in the source module now breaks this import loudly, which is the failure mode to prefer over silent drift.

**3. [Strengthened assertion] the not-owned comparison includes `instance`**

- **Found during:** Task 3
- **Issue:** the plan asks for the two bodies to be "identical apart from `instance`". The bodies necessarily mention two different identifiers in `detail`, in `errors` **and** in `instance` (which is the request path), so excusing `instance` leaves the path entirely uncompared.
- **Resolution:** `anonymised(response, *identifiers)` replaces each response's own identifier with a fixed token, and the two results are compared whole. Strictly stronger, and documented as such in the helper's docstring.

### Authentication gates

None.

## Known Stubs

None. Every fixture and every test in this plan is wired to the real application and the real database.

## Threat Flags

None. This plan adds no source module, no route and no dependency; it exercises surface 04-07 and 04-08 already shipped.

## Handover to 04-10

Everything 04-10 needs is in `tests/integration/conftest.py` and importable from `tests.integration.conftest`:

- **`api_client`** — yields `tuple[AsyncClient, FastAPI]`. Destructure it: `client, app = api_client`. It does **not** enter the lifespan, and it does not need to.
- **`seed(session_factory, *, users=(), task_lists=(), tasks=())`** — keyword-only, flushes per level, and **commits**. Anything seeded without committing disappears; this is the single most surprising rule in the harness and the docstring says so.
- **`acting_as(app, user_id)`** — a context manager, restoring. Use it for every D-04 / D-14 not-owned leg.
- **`statements`** — a `list[str]` that fills as the test runs; it is 04-11's, not 04-10's, but it is already attached to the same `connection` fixture and takes no extra wiring.
- **`session`** — the pre-existing fixture, on the same connection, for the direct repository reads the cascade test uses.

From `tests/integration/api/test_task_lists.py`, 04-10 should copy rather than re-invent:

- the fixed-identifier series (`...0011` lists, `...0021` tasks, `...00ff` missing) and `NOW`;
- `a_user` / `a_task_list` / `a_task`, the last of which derives `completed_at` from `status` so an incoherent pair cannot be built;
- `moment(value)` for `updated_at` comparisons;
- `anonymised(...)` and the `assert_not_found` shape — D-14's wrong-list leg is the same argument as D-04's not-owned leg and deserves the same body-to-body comparison;
- the `PROBLEM_JSON` / `MEMBERS` import, and the rule that a 422 test is named after which of the two producers it hits.

One measured fact worth carrying over: `GET .../tasks` on a deleted list answers `404` with `code == "task_list_not_found"` — the **list**-shaped error, per 04-06's decision that a caller who addressed a list and has no task identifier to be told about gets the list-shaped refusal. 04-10's wrong-list and not-owned legs need to expect that code on the collection route and the task-shaped one on the `{task_id}` routes.

## Self-Check: PASSED

- `tests/integration/api/__init__.py` — FOUND
- `tests/integration/api/test_task_lists.py` — FOUND
- `tests/integration/conftest.py` — FOUND (modified)
- commit `6a0f3be` — FOUND
- commit `0bd8b50` — FOUND
- commit `3109b18` — FOUND
