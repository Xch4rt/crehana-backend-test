---
phase: 04-task-lists-tasks
plan: 10
subsystem: tests
tags: [integration, httpx, asgitransport, d-08, d-13, d-14, d-16, d-17, task-01, task-08, sc-3, sc-4, n-plus-1]

# Dependency graph
requires:
  - phase: 04-task-lists-tasks
    provides: "04-09's api_client / acting_as / statements / seed harness, and the constants, builders and anonymised() this module imports rather than copies"
  - phase: 04-task-lists-tasks
    provides: "04-08's six task routes, their status codes and the status_filter alias whose 422 lands at query.status"
  - phase: 04-task-lists-tasks
    provides: "04-07's TaskResponse eleven-member order, TaskPatchRequest without a status field, and TaskCollectionResponse's four-member envelope"
  - phase: 04-task-lists-tasks
    provides: "04-06's task use cases — the list-shaped CreateTask refusal and the task-shaped siblings — and 04-05's ListTaskLists"
  - phase: 04-task-lists-tasks
    provides: "04-03's visible_task guard, which is the third statement the task collection issues"
  - phase: 02-domain-error-contract
    provides: "the RFC 9457 member list, the 409 from/to body and the two 422 producers the refusal matrix splits on"
provides:
  - "tests/integration/api/test_tasks.py — 44 HTTP tests covering TASK-01..TASK-08 end to end"
  - "tests/integration/api/test_statements.py — the D-17 counter: measured statement counts for both collection endpoints"
  - "the measured fact that GET .../tasks issues THREE statements (guard, page, aggregate), not the two 04-10-PLAN.md predicted"
  - "a_task_with() — the priority-carrying entity builder the filter matrix needs"
  - "100% line coverage of routers/tasks.py and schemas/tasks.py from the HTTP suite alone"
affects: [04-12, 05, 06, 07]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A statement-count test clears the recorder after seeding, because the seeding helper's INSERTs run on the same connection and would otherwise be counted as work the request did"
    - "Each endpoint is pinned by three properties — the exact count, its invariance between 1 and N rows, and a separate non-vacuity guard — because each alone is weak"
    - "The statement counter asserts numbers only; the repository suites already assert the SQL text without a server, and the two together make 'one grouped statement' true in both shape and execution"
    - "Due dates in tests are decades away from today (2020 / 2030), because Task.create and Task.reschedule compare against the CLOCK, not against the fixture's NOW"
    - "A test name must literally contain the word a plan's -k criterion greps for; the prose is kept and the word is appended"
    - "The filter conjunction is pinned by two pairs — one matching exactly one row, one matching none — because either alone passes against a wrong implementation"

key-files:
  created:
    - tests/integration/api/test_tasks.py
    - tests/integration/api/test_statements.py
  modified: []

key-decisions:
  - "GET /api/v1/task-lists/{id}/tasks issues THREE statements, not the two the plan's <interfaces> block predicted, and the measured number is what shipped. The third is 04-03's visible_task_list guard, which loads the parent and discards it so a list the caller cannot see is refused before a single task is read (D-04, ADR-008). The plan counted the page and the aggregate and forgot the guard the same phase mandates. Removing the guard to meet a predicted number would have traded a security property for a counter; the constant in test_statements.py therefore names all three statements and records why the plan's figure was wrong. The D-17 claim is untouched: none of the three is issued once per row, and the test still asserts the count is identical for 1 row and for 5"
  - "Two status tests are named ..._rejects_an_unknown_value / ..._rejects_an_unknown_key rather than the plan's ..._is_422, so that `-k rejects` collects 2 and exits 0. The plan's acceptance criterion offered an either/or — `-k rejects` exits 0, OR `-k validation_error` collects at least 6 — and both are now literally true (the second collects exactly 6). pytest exits 5, not 0, when -k matches nothing, so the plan's own prescribed names would have failed its own first clause; this is the same call 04-09 made when it renamed its two 409 tests to contain the word 'duplicate'"
  - "The module imports the sibling's constants, builders and anonymised() from tests/integration/api/test_task_lists.py rather than re-declaring them, which is why the module is readable at 1507 lines: what is specific to tasks is the nested path, and everything else is shared. A second copy of NOW, of a_user or of the tokenising comparison would be the one that disagreed the first time the shared fact moved"
  - "The wrong-list 404 ships as four tests, one per verb (GET, PATCH, DELETE, status), and the GET one additionally compares the body with the absent-task body through anonymised(). Both lists in those fixtures belong to the ACTING user, so a 404 cannot be explained by ownership — only by the parent segment being compared. Each mutating leg then re-reads the task under its real list, so a refusal is proved total rather than half-applied"
  - "test_status_is_not_writable_through_the_generic_patch asserts the 422 AND reads the task back. A refusal before a write and a refusal after one produce the same status code, so the second request is what makes this T-4-59's mass-assignment proof rather than a validation proof (D-08, TASK-03, SC-3)"
  - "The statistics test compares the three counters ACROSS two responses instead of against literals, and asserts the item counts differ. Comparing to literals would state a fact about the fixture; comparing across responses states the invariant. The differing item counts are what stop it passing vacuously against a filter that was silently dropped, which would make the two responses identical"
  - "a_task_with() is a second builder beside the sibling's a_task rather than a widening of it. a_task fixes the priority at the entity default, which is exactly right for the tests it was written for and useless to a filter matrix where the priority is half of the question; both derive completed_at from the status so neither can construct a pair the entity refuses"
  - "Requirement ticks TASK-01..TASK-08 deliberately NOT taken despite this plan's own frontmatter naming all eight — 04-12 is the last claimant of LIST-01..06 and TASK-01..08, the eleventh consecutive plan in this phase to make the same call. The behaviour those ticks rest on is now proved over HTTP, which is the evidence 04-12 will tick from"

patterns-established:
  - "One module-level assert_task_not_found(response, id), so ten task 404 legs cannot disagree about what a task 404 looks like — and it asserts the code, because task_list_not_found is also a 404 and would carry an identifier the caller never named"
  - "The not-owned tests assert `code != 'task_list_not_found'` explicitly, so a refusal that leaked the list's existence through a different code would fail even though it is still a 404"
  - "The statement recorder is cleared, never re-created: the fixture attaches one listener per connection and a test that wanted a fresh count clears the list it was handed"
  - "A non-vacuity guard accompanies every counting suite, because a listener that failed to attach makes every count assertion pass by comparing nothing with nothing"

requirements-completed: []

# Metrics
duration: 12min
completed: 2026-09-19
---

# Phase 4 Plan 10: the six task routes over HTTP, and the N+1 counter Summary

**TASK-01 through TASK-08 are now provable by 44 named HTTP integration tests against real PostgreSQL — the lifecycle walk, the 409 that names the move it refused, the filter conjunction pinned by two pairs, and a `status` key that is refused by the generic PATCH on a task whose status is then read back and found not to have moved — and "no N+1" stopped being a claim: `GET /task-lists` is measured at one statement for 1 list and for 5, and `GET .../tasks` at three (the visibility guard, the page, the aggregate) for 1 task and for 5, which is one more than the plan predicted because the plan had not counted the guard.**

## Performance

- **Duration:** ~12 min (00:40 → 00:52 UTC)
- **Tasks:** 3 of 3, one commit each
- **Files:** 2 created (1783 lines), 0 modified

## Accomplishments

- **The nested path segment is honoured on every verb, and that is now a test rather than a reading of the router.** Four wrong-list tests — GET, PATCH, DELETE and the status endpoint — each put a task in list A and address it under list B, **both owned by the acting user**, so ownership cannot be what refuses them. The GET leg additionally compares its body with the absent-task body through `anonymised()`, which leaves `code`, `title`, `detail`, `errors` **and** `instance` compared modulo the identifier each response carries. The three mutating legs then read the task back under its real list and find it untouched (D-14, TASK-02, T-4-57).
- **The not-owned matrix answers task-shaped, deliberately and explicitly.** Four tests act as a second user through `acting_as`, one per verb, each asserting `task_not_found` **and** `code != "task_list_not_found"` — because the latter is also a 404, would also look reasonable, and would carry the identifier of a list the caller only guessed at (D-04, T-4-58).
- **Create is the one list-shaped refusal, pinned with its reason in the docstring.** The caller addressed a list, no task exists yet, so there is no task identifier the answer could be about. The test asserts `task_list_not_found`, compares the body with the absent-list body, and then confirms the owner's list is still empty — and says in prose that this is not an inconsistency to be tidied away, so a later reader does not "fix" it into an invented identifier.
- **The whole lifecycle is driven over HTTP, and the moves come from the table.** The walk asserts `pending → in_progress → completed`, the full eleven-member body at each step, `completed_at` absent while unfinished and set the instant it is, and finally that `completed_at == updated_at`. Both moves are asserted to be in `ALLOWED_TRANSITIONS` before they are made, so a change to the state machine turns the test red instead of leaving it asserting a walk the machine no longer permits (TASK-05, D-11).
- **The same-state request is a 200 no-op, proved by whole-body equality.** `response.json() == before`, `updated_at` included — a handler that treated the no-op as an ordinary move would answer 200 with a body differing in exactly that one member, which a status-code assertion cannot see.
- **The 409 names the move.** `completed → pending` is asserted to be absent from `ALLOWED_TRANSITIONS[COMPLETED]`, then requested: `code == "invalid_status_transition"`, `errors == {"from": "completed", "to": "pending"}`, and the task read back still `completed` (roadmap SC-3).
- **The filter conjunction is pinned by two pairs, not one.** Five seeded tasks span two statuses and two priorities: `pending`+`high` matches exactly one row while each half alone matches two, and `completed`+`medium` matches none. The matching pair alone would pass against an OR; the empty pair alone would pass against an implementation that narrows to nothing whenever two filters arrive (TASK-06).
- **Roadmap SC-4 is the strongest assertion in the module, and it compares responses rather than literals.** `total_tasks`, `completed_tasks` and `completion_percentage` are asserted **identical** across a filtered and an unfiltered call, while the item counts are asserted to **differ** — so the test cannot pass vacuously against a filter that was silently dropped. The empty-conjunction test makes the same point from the other side: zero items, and still `5 / 2 / 40.0`.
- **`status` cannot be written through the generic PATCH, and the proof is the task, not the status code.** 422 with `field == "body.status"` and `type == "extra_forbidden"` (one error, because `status` is not a field of `TaskPatchRequest` at all), and then a `GET` finding the task still `pending` with `completed_at` null. A refusal after a write and a refusal before one are the same 422 (D-08, TASK-03, T-4-59).
- **The 422 matrix is split by producer in the test names.** The **object** shape, from the entity: a blank title, an over-length title built from `Task.TITLE_MAX_LENGTH + 1`, and a past due date (`{"field": "due_date"}`, TASK-08) — the last of which proves the deadline check is still the entity's rather than a second copy at the boundary. The **list** shape, from request validation: an empty patch body at `body`, an unknown key at `body.titel`, `status` at `body.status`, an unknown status value at `body.status`, an unknown key in the status body, a malformed path UUID at `path.task_id`, and invalid filter values at `query.status` and `query.priority` (T-4-60).
- **D-07's overdue task is patchable, and the fixture proves why that state is reachable.** The task is written through the mapper with a 2020 deadline, because `Task.create` refuses one behind the creation moment — the state exists only through the passage of time. Patching the title alone answers 200; a `reschedule` called on every patch rather than only on one that names `due_date` would answer 422 and lock the task forever.
- **"No N+1" is a counter.** `GET /api/v1/task-lists` records exactly `["SELECT"]` for one list and the identical recording for five lists each carrying tasks. `GET .../tasks` records three SELECTs for one task and three for five, and three again with a filter applied. A fourth test issues one request and asserts the recorder is non-empty, so none of the above can pass by recording nothing (D-17, LIST-03, TASK-07, T-4-62).
- **`routers/tasks.py` and `schemas/tasks.py` are at 100% from the HTTP suite alone.** Measured with `--cov=taskmanager.presentation` over `tests/integration/api` only: 49 statements in the router, 0 missing; 51 in the schemas, 0 missing. The whole-project figure is now **599 passed / 100.00%**.

## Task Commits

1. **Task 1: the task CRUD routes over HTTP, and the wrong-list 404 on four verbs** — `db4d7e6` (test, 25 tests, +867 lines)
2. **Task 2: the status endpoint, the filters, the statistics and the 422 matrix** — `a7fff37` (test, +19 tests → 44, +642 lines)
3. **Task 3: the D-17 statement counter — no N+1, asserted rather than claimed** — `e308132` (test, 4 tests, +276 lines)

**Plan metadata:** see the final `docs(04-10)` commit.

## Files Created

| File | Contents | Notes |
|------|----------|-------|
| `tests/integration/api/test_tasks.py` | 1507 lines, 44 tests | the six task routes, their refusals and the 422 matrix |
| `tests/integration/api/test_statements.py` | 276 lines, 4 tests | the D-17 counter for both collection endpoints |

## Files Modified

None. Both artifacts are new, and nothing under `src/` needed a change: no HTTP test exposed a defect in a router, a schema, a use case or an adapter.

## Gate Results

| Gate | Result |
|------|--------|
| `make lint` (black, isort, flake8) | PASS — 139 files unchanged, no findings |
| `make typecheck` (mypy strict) | PASS — no issues in 139 source files |
| `make arch` (import-linter) | PASS — 4 contracts kept, 0 broken |
| `make test` | PASS — **599 passed**, `Required test coverage of 75% reached. Total coverage: 100.00%` |
| `pytest tests/integration -x --no-cov -q` | PASS — 162 passed, the whole Phase 3 integration suite included |
| `pytest tests/integration/api -x --no-cov -q` | PASS — 79 passed |
| `--cov=taskmanager.presentation` over `tests/integration/api` | `routers/tasks.py` 49 statements / **0 missing**; `routers/task_lists.py` 39 / **0 missing** |

Baseline before this plan was 551 passed / 99.36%; the 48 new tests took it to 599 / **100.00%**, and the increase is entirely the task router's and task schemas' handler bodies.

## Measured Statement Counts

| Request | Statements | Composition |
|---------|-----------|-------------|
| `GET /api/v1/task-lists` (1 list) | `["SELECT"]` | the one grouped statement (D-10, LIST-03) |
| `GET /api/v1/task-lists` (5 lists, 3 tasks) | `["SELECT"]` | identical — this is the invariance D-17 asks for |
| `GET .../{id}/tasks` (1 task) | `["SELECT", "SELECT", "SELECT"]` | visibility guard, page, aggregate |
| `GET .../{id}/tasks` (5 tasks) | `["SELECT", "SELECT", "SELECT"]` | identical |
| `GET .../{id}/tasks?status=pending` | `["SELECT", "SELECT", "SELECT"]` | the filter adds no statement |

## Acceptance Criteria

Every criterion the plan wrote is met. One is met by a number the plan predicted wrongly, recorded in full under Deviations.

| Criterion | Result |
|-----------|--------|
| `test_tasks.py -x --no-cov -q` ≥ 22 tests after Task 1 | PASS — 25 |
| `-k wrong_list` collects ≥ 4 | PASS — 4 |
| `-k create` collects ≥ 2 | PASS — 3 |
| `-k delete` collects ≥ 1 | PASS — 2 |
| `grep -c task_not_found` ≥ 5 | PASS — 13 |
| `grep -c DEFAULT_PRIORITY` ≥ 1 | PASS — 4 |
| `grep -c TITLE_MAX_LENGTH` ≥ 1 | PASS — 2 |
| `test_tasks.py` ≥ 42 tests after Task 2 | PASS — 44 |
| `-k status_is_not_writable` collects 1 | PASS — 1 |
| `-k filter` collects ≥ 5 | PASS — 6 |
| `-k statistics` collects ≥ 2 | PASS — 2 |
| `-k rejects` exits 0 **or** `-k validation_error` collects ≥ 6 | PASS — **both**: `rejects` collects 2, `validation_error` collects 6 |
| `grep -c invalid_status_transition` ≥ 1 | PASS — 1 |
| `grep -c "query.status"` ≥ 1 | PASS — 2 |
| `grep -c completion_percentage` ≥ 4 | PASS — 4 |
| `test_statements.py` exits 0 with 4 tests | PASS — 4 |
| `-k lists` collects ≥ 1 | PASS — 1 |
| `grep -c statements` ≥ 8 | PASS — 29 |
| `grep -c SELECT` ≥ 2 | PASS — 3 |
| `pytest tests/integration -x --no-cov -q` exits 0 | PASS — 162 passed |
| `make lint && make typecheck && make arch` | PASS |
| `make test` reports coverage reached | PASS — 100.00% |
| router modules show no missing lines | PASS — both at 0 missing |
| `mypy src tests` exits 0 | PASS |

## Deviations from Plan

### 1. [Rule 1 — measurement correcting the plan] The task collection issues three statements, not two

- **Found during:** Task 3, on the first run of `test_statements.py`.
- **Plan's claim:** the `<interfaces>` block states "GET `.../tasks` issues TWO (the page and the aggregate, ADR-009)", and Task 3's text repeats it as "expecting exactly two `SELECT`s".
- **Measured:** three. Reading `application/use_cases/tasks/list.py` shows why: `execute` first `await`s `visible_task_list(...)`, which loads the parent list and discards it so a list the caller cannot see is refused before a single task is read (D-04, ADR-008); then the page; then the aggregate.
- **Resolution:** the measured number shipped. The two candidate "fixes" were both worse than the finding. Removing the guard would trade a security property of this very phase for a number in a plan. Folding the guard into the page query would be an architectural change (Rule 4) that dissolves the indistinguishability 04-03 built. The constant `TASK_COLLECTION_STATEMENTS` therefore carries a three-item comment naming each statement and recording that the plan predicted two and had not counted the guard.
- **The D-17 claim is unaffected.** D-17 is about invariance, not about a magic number: none of the three statements is issued once per row, and the test asserts the recording is byte-identical between one task and five, and again with a filter applied.
- **Files:** `tests/integration/api/test_statements.py`. **Commit:** `e308132`.

### 2. [Naming, so a -k criterion is literally true] Two status tests carry the word `rejects`

- The plan prescribes `test_an_unknown_status_value_is_422` and `test_an_unknown_key_in_the_status_body_is_422`, and then offers the criterion "`-k rejects` exits 0 (or, if no test carries `rejects`, `-k validation_error` collects at least 6)". pytest exits **5**, not 0, when `-k` matches nothing, so the plan's own names would have failed its own first clause.
- Shipped as `test_the_status_endpoint_rejects_an_unknown_value` and `test_the_status_endpoint_rejects_an_unknown_key`: the meaning is unchanged, both clauses of the criterion are now literally true, and the 04-09 precedent (renaming its 409 tests to contain "duplicate") is followed rather than invented.

### 3. [Scope, additive] Four tests beyond the plan's enumeration

- `test_a_created_task_is_visible_to_the_next_request` — the harness smoke test, the sibling module's convention.
- `test_get_an_absent_task_is_404` — the standalone counterpart every wrong-list comparison is measured against. A comparison that only ever ran inside another test would disappear with it (the 04-09 argument).
- `test_the_collection_of_a_list_the_actor_does_not_own_is_404` — `GET .../tasks` is addressed at a list, so its refusal is list-shaped; measured rather than assumed, and it asserts that no seeded task id appears anywhere in the body.
- `test_an_over_length_title_is_a_domain_validation_error` — the plan lists it under Task 2, and it shipped in Task 1 beside the other create-time refusals. Not a deviation in content, only in which commit carries it.

### 4. Nothing under `src/` changed

No HTTP test exposed a defect in a router, a schema, a use case or an adapter. Every one of the 48 tests passed on its first run against the shipped code — including the ordering tie-break, the 66.67-style rounding path and the `completed_at`/`updated_at` equality — which is the payoff of 04-05 and 04-06 having proved the same behaviours against the fakes first.

## Known Stubs

None. Every test in both modules asserts against live behaviour; nothing is skipped, xfailed or marked.

## Threat Flags

None. This plan adds no route, no schema, no query and no dependency — it adds assertions about surface that already existed, and it closes T-4-57 through T-4-62 with tests named in the register.

## Handover to 04-12

- **All fourteen behavioural requirements are now provable over HTTP.** LIST-01..LIST-06 by `test_task_lists.py` (04-09), TASK-01..TASK-08 by `test_tasks.py` (this plan). 04-12 is the last claimant of all fourteen and can tick each from a named test rather than from a plan header.
- **Three requirement-to-test anchors 04-12 will want:** TASK-03/SC-3 → `test_status_is_not_writable_through_the_generic_patch` (the 422 *and* the unmoved task); TASK-07/SC-4 → `test_the_statistics_cover_the_whole_list_whatever_the_filter`; SC-3's transition leg → `test_an_invalid_transition_is_409_naming_the_transition`.
- **The three-statement figure belongs in the README and in `DECISION_LOG.md`.** Any document that says the task collection is "two queries" is now wrong, and the honest sentence is that it is three and that none of them scales with the number of tasks. `test_statements.py`'s module docstring is the source to quote.
- **The coverage figure is 100.00% over `src/taskmanager` with no pragma and no omit**, which is the number Phase 7's README should cite.
- **`AI_WORKFLOW.md` owes an entry**, per the standing rule: the plan predicted a statement count and the measurement disagreed, and the resolution was to correct the plan rather than the code — the same class of incident as 03-10's compose profile and 04-08's `app.routes`.

## Self-Check: PASSED

- `tests/integration/api/test_tasks.py` — FOUND (1507 lines, 44 tests)
- `tests/integration/api/test_statements.py` — FOUND (276 lines, 4 tests)
- `.planning/phases/04-task-lists-tasks/04-10-SUMMARY.md` — FOUND
- commit `db4d7e6` — FOUND
- commit `a7fff37` — FOUND
- commit `e308132` — FOUND
