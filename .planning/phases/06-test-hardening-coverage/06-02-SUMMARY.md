---
phase: 06-test-hardening-coverage
plan: 02
subsystem: test-gates
tags: [assertion-quality, ast-gate, taint-tracking, re-read, no-reread-marker, d-05, d-06, d-07, sweep]

# Dependency graph
requires:
  - phase: 06-test-hardening-coverage
    provides: "06-RESEARCH.md — both halves prototyped, the 29-vs-1 false positive count, and the 39-offender per-file breakdown"
  - phase: 06-test-hardening-coverage
    provides: "06-01 — the lesson that a gate must not be satisfiable by its own guard, and the planted-snippet self-test pattern"
  - phase: 04-task-lists-tasks
    provides: "tests/integration/api/test_task_lists.py's module docstring, which states the two standards this plan makes enforceable"
provides:
  - "tests/architecture/test_assertion_quality.py — both halves of the assertion-quality gate, 28 tests, of which 20 prove the gate's own rules against planted source"
  - "REQUIRED_NO_REREAD — the ten-entry exemption set, gated four ways"
  - "pytest.ini's no_reread(reason) marker registration"
  - "29 swept HTTP tests that now read their mutation back through the API"
affects: [06-03, 06-04, 07-documentation-delivery]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Taint tracking to a fixed point in an AST gate, so a rule can follow the suite's own indirection instead of demanding a literal"
    - "Per-module helper resolution across ImportFrom, rather than a global name set, so the cross-module hop is load-bearing and falsifiable"
    - "Scope by behaviour, not by signature: an HTTP test is one that issues a request, not one that declares a client fixture"
    - "An exemption that must still be NEEDED, not merely still present — the fourth assertion the repo's existing exemption analog lacks"

key-files:
  created:
    - tests/architecture/test_assertion_quality.py
  modified:
    - pytest.ini
    - tests/integration/api/test_task_lists.py
    - tests/integration/api/test_tasks.py
    - tests/integration/api/test_auth.py
    - tests/integration/api/test_assignment.py
    - tests/integration/api/test_permission_matrix.py

key-decisions:
  - "Half (a)'s scope is tests that ISSUE a request, not tests that declare a client fixture. test_permission_matrix.py's test_the_table_covers_every_operation_the_document_publishes takes authenticated_client only to reach the app half of the two-tuple and drives nothing; under the plan's literal rule it was a false positive the research's prototype had not seen"
  - "Recorder evidence is tracked by taint, not by a direct name: the notification tests do `sent = notifications(caplog)` then `fields = extras(sent[0])` then assert on `fields`, so a rule requiring an assert to NAME caplog reported two false positives. Taint is propagated to a fixed point over three sources (response members, declared recorder fixtures, helper calls)"
  - "The one real status-only offender is fixed but was NOT reported by the shipped gate, and the summary says so: test_the_assignee_cannot_see_the_list_the_task_lives_in also calls assert_not_found on its other response, so a per-TEST rule is satisfied. A per-RESPONSE rule would catch it and was rejected — it is a much larger change with an unmeasured false-positive rate, and this plan's whole argument is that a noisy gate gets deleted"
  - "`REQUIRED_NO_REREAD` is compared as an EQUALITY in both directions, not a subset: a marker on an unlisted test is an exemption granted without editing the gate, and a listed id whose test lost its marker is a stale entry that no subset check catches"
  - "A fourth assertion beyond the plan's three: every exempted test must still be an offender with its marker stripped. So an exemption that stops being needed - because someone added a re-read - fails until it is removed. Implemented with copy.deepcopy rather than a re-parse of ast.unparse, which would renumber every line"
  - "The register legs read POST /auth/register back through GET /api/v1/users with the GET written out in each test rather than hidden in a helper: a re-read inside a helper is one a reader has to go looking for, and the gate reads the test"
  - "Five of the ten exemptions are login tests whose reason is now fuller than 'login mutates nothing': three of them register first, and the register is setup whose persistence is proved by test_register_then_login_then_get_me_reads_back_the_same_profile. Sweeping them with a directory read was considered and rejected as satisfying a tool rather than adding a claim"

patterns-established:
  - "State the rule correctly instead of adding an escape hatch: half (a) has no opt-out because the rule's four accepted shapes reduce 29 offenders to 1"
  - "A gate's detection rules are code and get their own tests: 20 of this module's 28 tests are planted snippets, and every rule the docstring promises has one"

requirements-completed: []

# Metrics
duration: 30min
completed: 2026-09-19
---

# Phase 6 Plan 02: The Assertion-Quality Gate and the Re-Read Sweep Summary

**A test that asserts only a status code, or mutates without reading the change back, now fails
the build — and the HTTP suite it guards has no such test left except ten that each carry a
registered, still-necessary reason, because 29 mutating tests were swept in the same commits that
planted the gate.**

## Performance

- **Duration:** ~30 min
- **Tasks:** 4 of 4
- **Files modified:** 7 (1 created, 6 modified)
- **Suite:** 1038 → **1066 passed**, coverage **100.00 %** (gate 75 %)

## Task Commits

| Task | Name                                         | Commit    | Files                                                      |
| ---- | -------------------------------------------- | --------- | ---------------------------------------------------------- |
| 1    | Half (a) + the one real offender (D-05a)     | `6bd1480` | test_assertion_quality.py, test_assignment.py              |
| 2    | The re-read sweep, 29 tests (D-06)           | `7610666` | test_task_lists.py, test_tasks.py, test_auth.py             |
| 3    | Half (b), the marker, the exemption set      | `fd0dc9e` | test_assertion_quality.py, pytest.ini, 3 test modules       |
| 4    | Close the plan                               | (this)    | 06-02-SUMMARY.md, STATE.md, ROADMAP.md                      |

## The sweep, measured against the 39

Derived from the tree by the gate itself, not from the research prose — and it agreed with the
research's per-file breakdown exactly, all five files.

| File | Offenders | Swept | Exempt |
| ---- | --------- | ----- | ------ |
| `test_task_lists.py` | 15 | 15 | 0 |
| `test_tasks.py` | 9 | 9 | 0 |
| `test_auth.py` | 9 | 5 (register) | 4 (login) |
| `test_assignment.py` | 5 | 0 | 5 (notification) |
| `test_permission_matrix.py` | 1 | 0 | 1 (login) |
| **Total** | **39** | **29** | **10** |

131 HTTP tests are in scope (the research counted 129; the gate counts what is there).

Legs applied: a successful mutation gets a GET whose body equals the answer, or an explicit
assertion on the field that moved plus equality on the fields that did not; a DELETE or an absent
resource gets a GET returning the 404 problem body through the module's own `assert_not_found` /
`assert_task_not_found` rather than an inlined check; a rejected mutation gets `before` captured
above it and `after == before` below — the bulk of the sweep. No existing assertion was deleted or
rewritten (D-13).

## `REQUIRED_NO_REREAD` — the ten, and the reason each one carries

**`POST /auth/login` × 5.** Login mutates no resource, so there is nothing a GET could read back.

| Node id | Reason |
| ------- | ------ |
| `test_auth.py::test_login_answers_a_bearer_token_and_the_configured_lifetime` | The register above is setup, proved by `test_register_then_login_then_get_me_reads_back_the_same_profile`; the successful login below *is* the re-read, spelled as a POST, which is why the gate cannot see it |
| `test_auth.py::test_login_without_a_password_is_422_and_does_not_echo_the_username` | Refused at the boundary — the use case is never reached, so there is no state for a GET to be about |
| `test_auth.py::test_login_with_an_unknown_address_and_with_a_wrong_password_are_indistinguishable` | Asserts that two refusals are one document, which no GET can show |
| `test_auth.py::test_login_with_an_unstorable_username_is_the_same_401` | The point is that the NUL never reached a statement |
| `test_permission_matrix.py::test_login_refuses_a_bad_credential_from_an_anonymous_caller` | The caller is anonymous and could not read a resource if there were one |

**The five notification tests.** Their subject is a log record no route publishes.

| Node id | Reason |
| ------- | ------ |
| `test_assignment.py::test_assigning_notifies_the_new_assignee_with_one_structured_record` | Persistence is proved by `test_a_notifier_failure_leaves_the_assignment_committed` and by the four assign/unassign tests that do re-read |
| `test_assignment.py::test_the_notification_renders_as_one_parseable_json_line` | Subject is the rendered log line; persistence proved next door |
| `test_assignment.py::test_a_title_carrying_a_newline_still_notifies_on_a_single_line` | Same |
| `test_assignment.py::test_assigning_the_same_user_again_notifies_nobody` | Subject is the *absence* of a record; the row's no-op is proved by `test_assigning_the_same_user_again_is_a_no_op_that_does_not_move_updated_at` |
| `test_assignment.py::test_unassigning_notifies_nobody` | Subject is the *absence* of a record; unassignment is proved by `test_the_owner_unassigns_and_the_assignee_id_goes_back_to_null` |

## The two halves, and the red that earned each green

Neither half is trusted on the strength of passing. Nine temporary edits were made, observed red,
and reverted; `git status --porcelain -- src/ tests/` confirmed clean each time. No transcript is
kept (D-15); the edit is named instead.

**Half (a) — status-only.** Four falsifications.
1. Deleting `assert response.json() == []` from
   `test_the_collection_is_empty_for_an_actor_who_owns_nothing` reported
   `tests/integration/api/test_task_lists.py:180`. (The test was chosen deliberately: its body
   assertion is its *only* evidence. A test that also calls a named helper stays green under the
   same edit, which is the per-test granularity stated as a limit below.)
2. Turning the cross-module helper hop off reported
   `test_auth.py::test_every_unauthenticated_refusal_carries_the_same_body_as_the_others` — the
   exact false positive 06-RESEARCH.md measured. This is asserted on a planted snippet too, so it
   is checked on every run and not only today.
3. Removing a name from `REQUIRED_SCANNED_TEST_MODULES` left the gate green (a subset check,
   deliberately) while `git mv test_users.py test_people.py` turned
   `test_the_http_suite_is_actually_scanned` red.

**Half (b) — no re-read.** Five falsifications.
1. Deleting the trailing GET from a swept test reported `test_task_lists.py:1015`.
2. `@pytest.mark.no_reread("because")` on an unregistered test failed
   `test_every_exemption_marker_is_registered_in_this_module`.
3. An emptied reason string failed `test_every_exemption_marker_carries_a_non_empty_reason`,
   naming `test_auth.py:390`.
4. Renaming an exempted test named both the stale id and the new one.
5. Adding a re-read to an exempted test failed `test_every_registered_exemption_still_needs_it`
   with "reads its mutation back and no longer needs its `no_reread` marker; remove both" — the
   fourth gate, and the one the repo's existing exemption analog does not have.

**And the sweep itself.** With `await self._uow.task_lists.update(task_list)` removed from
`UpdateTaskList`, the swept `test_renaming_a_list_to_its_own_current_name_succeeds` fails on its
**re-read** assertion (`moment(after["updated_at"]) > moment(before["updated_at"])`) while both of
its response assertions stay green. That is the sweep doing what it was for.
`git status --porcelain -- src/` empty afterwards; this plan needed no `src/` change.

## Deviations from Plan

**1. [Rule 1 — the plan's scope rule produced a false positive] an HTTP test is one that requests**
- **Found during:** Task 1
- **Issue:** the plan scopes half (a) to "test functions ... that take a client fixture parameter".
  `test_permission_matrix.py::test_the_table_covers_every_operation_the_document_publishes` takes
  `authenticated_client` solely to reach the `app` half of the two-tuple, compares `app.openapi()`
  against the matrix table, and issues no request at all. Under the plan's rule it is a status-only
  offender with no response to assert on.
- **Fix:** the scope is tests that issue at least one request through a client local name. Stated in
  `http_tests`' docstring with that test named.
- **Commit:** `6bd1480`

**2. [Rule 1 — the recorder rule as specified missed two real tests] taint, not naming**
- **Found during:** Task 1
- **Issue:** the plan accepts "an assertion naming a recorded side-effect fixture the test
  declares". Two notification tests never name `caplog` in an assert — they do
  `sent = notifications(caplog)`, then `fields = extras(sent[0])`, then
  `assert fields["event"] == ...`. Both were reported as offenders.
- **Fix:** one taint mechanism, propagated to a fixed point, over three sources: a response member,
  a declared recorder fixture, and a call to a resolvable `Response`-taking helper. A helper call
  anywhere in the function also satisfies the rule directly, which is what
  `bodies[name] = anonymised(response)` needs.
- **Commit:** `6bd1480`

**3. [Rule 3 — the plan's "one real offender" is not reportable by a per-test rule]**
- **Found during:** Task 1
- **Issue:** the plan names `test_the_assignee_cannot_see_the_list_the_task_lives_in` as the one
  genuine half (a) offender, and it is one — its visible half asserted only
  `the_task.status_code == 200`. But the same test calls `assert_not_found(the_list, LIST_ID)` on
  its *other* response, so a rule about the test satisfies. The research's count of "6, of which 1
  is real" came from a prototype reading responses, and the rule the plan specifies reads tests.
- **Fix:** the offender is fixed anyway — it now asserts the task body its own name implies — and
  the limitation is recorded here rather than papered over. A per-response rule was considered and
  rejected: it is a much larger change with an unmeasured false-positive rate, and the whole
  argument of this module's docstring is that a noisy gate gets deleted.
- **Commit:** `6bd1480`

**4. [Rule 2 — one more gate on the escape hatch than the plan asks for]**
- **Found during:** Task 3
- **Issue:** the plan's three gates (non-empty literal reason; node id in the frozenset; the id
  still exists and still carries the marker) all pass for an exemption that has quietly stopped
  being necessary — someone adds a re-read to an exempted test and the marker lives on as a hole.
- **Fix:** a fourth assertion: every exempted test must still be an offender with its marker
  stripped. Falsified directly (see above). The strip is a `copy.deepcopy` and not a re-parse of
  `ast.unparse(tree)`, which renumbers every line and would break the `file:line` comparison.
- **Commit:** `fd0dc9e`

**5. [Rule 1 — the exemption count is the plan's ten, but one reason is different]**
- **Found during:** Task 3
- **Issue:** the research names `test_login_with_an_unstorable_username_is_the_same_401` and two
  siblings as "login mutates nothing", but all three `POST /auth/register` first — a successful
  mutation a `GET /api/v1/users` could observe. Strictly they are sweepable.
- **Fix:** exempted, with the fuller reason recorded per test: the register is setup whose
  persistence is proved by the dedicated re-read test, and in two of the three the successful login
  *is* the read, invisible to the gate only because a login is spelled as a POST. Adding a
  directory read there would satisfy a tool rather than add a claim. Recorded so the next reader
  does not have to re-derive it.
- **Commit:** `fd0dc9e`

## For plan 04: the ADR-worthy rule this plan introduced

Next free ADR number is **085**; 06-01 handed over three candidates, so this is the fourth, and it
earns one `CLAUDE.md` "Project Rules" bullet under a new **Test quality** heading:

**Assertion quality.** Every test under `tests/integration/api/` that issues a request through a
client fixture must assert on something the API said — a body member, a name tainted from one, a
named `Response`-taking helper, or a recorded side-effect fixture it declares — and every test that
mutates must read the resource back with a `GET` after its last mutation. The only exemption from
the second half is `@pytest.mark.no_reread("<reason>")`, whose node id must appear in
`REQUIRED_NO_REREAD` in the gate module and which fails the build the moment it stops being
necessary. Enforced by `tests/architecture/test_assertion_quality.py`. Worth recording with its
honest limit: the rule is per **test**, not per **response**, so a test that asserts one body and
only a status code on a second response satisfies it.

Also worth writing up alongside it, because this plan is the second live example in two plans:
**a gate's detection rules are code and get their own tests.** 20 of this module's 28 tests are
planted snippets. Two of the plan's own rule statements were wrong in a way that only the tree
could reveal (deviations 1 and 2), and both were caught within minutes because the rules were
executable rather than prose.

## Verification Results

```
make lint       -> black 185 files unchanged, isort clean, flake8 clean
make typecheck  -> Success: no issues found in 185 source files
make arch       -> Contracts: 4 kept, 0 broken.
make test       -> 1066 passed, TOTAL 1643 stmts / 154 branches, 100%
```

- `.venv/bin/pytest tests/architecture/test_assertion_quality.py --no-cov` → 28 passed, zero
  offenders in both halves.
- `.venv/bin/pytest tests/integration/api --no-cov` → 220 passed; no collection error under
  `--strict-markers`, so the marker registration is live.
- `git status --porcelain -- src/` empty after every falsification.

## Ceremony

Minimal, per D-15: one SUMMARY, no evidence file, no transcript, no RED artifact. Nothing was
written to `AI_WORKFLOW.md` or `DECISION_LOG.md` — plans 03 and 04 own those. `TEST-05` is **not**
ticked: 06-03 owns the deliberate-break half of that requirement and is its last claimant.

## Self-Check: PASSED

- `tests/architecture/test_assertion_quality.py` — FOUND
- `pytest.ini` carries `no_reread` — FOUND
- commits `6bd1480`, `7610666`, `fd0dc9e` — all FOUND in `git log`
