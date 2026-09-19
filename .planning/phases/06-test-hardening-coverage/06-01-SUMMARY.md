---
phase: 06-test-hardening-coverage
plan: 01
subsystem: test-gates
tags: [totality-gates, ast-gate, asgi-recorder, openapi, parametrization, transition-table, rfc9457, row-locks, d-14, vacuous-tests]

# Dependency graph
requires:
  - phase: 06-test-hardening-coverage
    provides: "06-RESEARCH.md — the four gate designs, the _IncludedRouter pitfall, and both D-14 findings measured end to end"
  - phase: 05-auth-assignment-notifications
    provides: "tests/integration/api/test_permission_matrix.py — 19 rows, one per published operation, which is what makes the endpoint gate green on arrival"
  - phase: 04-task-lists-tasks
    provides: "ADR-058's for_update=True on every write path, and tests/integration/test_concurrent_writes.py's two-connection harness"
provides:
  - "tests/architecture/test_use_case_totality.py — a use case with no fakes-based unit test fails a build"
  - "tests/integration/conftest.py REQUESTED + recording() — every operation the run requested, observed at runtime"
  - "tests/integration/test_endpoint_totality.py — a published operation no test requested fails a full run"
  - "tests/architecture/test_error_contract_totality.py — a raisable DomainError leaf whose code no test asserts fails a build"
  - "test_tasks.py's parametrized complement of ALLOWED_TRANSITIONS over HTTP, four cases derived from the table"
  - "The two D-14 fixes: the auth caller is seeded, and DeleteTaskList's lock is proven against two real connections"
affects: [06-02, 06-03, 06-04, 07-documentation-delivery]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Totality as a gate, not a registry: the expected set is discovered from the source of truth (an AST walk, app.openapi(), ALLOWED_TRANSITIONS, a ClassVar) and never listed by hand"
    - "A non-vacuity guard beside every gate, named rather than counted, asserted as a subset so the gate does not have to be edited to grow"
    - "A pure-ASGI wrapper at the transport to observe the application without changing it"
    - "A two-sided check where one side is always meaningful and the other is total only on a full run"
    - "A gate that excludes itself from its own scan, with a companion test keeping the exemption justified"
    - "Driving each new gate red once, by a temporary edit, before trusting its green"

key-files:
  created:
    - tests/architecture/test_use_case_totality.py
    - tests/architecture/test_error_contract_totality.py
    - tests/integration/test_endpoint_totality.py
  modified:
    - tests/integration/conftest.py
    - tests/integration/api/test_tasks.py
    - tests/integration/api/test_auth.py
    - tests/integration/test_concurrent_writes.py

key-decisions:
  - "The use-case scan collects module-level class, async def AND plain def, and REQUIRED_USE_CASE_SYMBOLS names 22 symbols, not the 20 06-RESEARCH.md counts: the research enumeration itself lists 22 and the count in its prose was wrong (measured against the tree)"
  - "The plan's third falsification for task 1 does not hold and a stronger one was used instead: renaming test_list_users.py leaves the gate green because test_write_paths_hold_what_they_change.py also imports and constructs ListUsers; only 8 of the 22 symbols have a single coverer, and test_login.py was moved aside instead, which reported Login uncovered with its declaration site"
  - "test_error_contract_totality.py excludes itself from the tests/ scan. Written without that exclusion it passed while proving nothing, because its own REQUIRED_RAISED_CODES guard names all nine codes as literals under tests/ — a gate satisfied by its own non-vacuity guard. test_the_self_exclusion_is_load_bearing keeps the exemption honest"
  - "Docstrings are excluded from the string-literal scan: this project's tests explain themselves at length, and a code named in prose is exactly what must not count as coverage"
  - "A second test asserts every DomainError subclass is declared in domain/exceptions.py, which closes the __subclasses__() blind spot the discovery would otherwise have (a leaf declared in an adapter would be raisable and invisible)"
  - "The deletion concurrency case asserts the ANSWER, not the end state: the list ends up gone either way, because a plain read passes the guard on a stale row and the DELETE statement blocks on its own. What the plain read loses is that the second caller is told 204 for a list another caller already removed"
  - "The comparative auth body test is seeded too, not only the parametrized one: unseeded it compared six copies of the unknown-subject answer, so 'all seven bodies are identical' was true by construction rather than by design"
  - "STATE.md and ROADMAP.md were edited by hand, for the reason 05-16 and 05-17 record: the gsd-sdk state handlers reset the percent, inject blank lines between decision bullets and miscount totals"

patterns-established:
  - "Observed totality: record what the run did, compare it against what the application publishes, and skip the total half on a partial selection"
  - "Falsify before trusting: a gate's green is worth what its red proved, so each one was driven red by a named temporary edit and the edit reverted"

requirements-completed: [TEST-01, TEST-02, TEST-04]

# Metrics
duration: 15min
completed: 2026-09-19
---

# Phase 6 Plan 01: Totality Gates and the Two D-14 Findings Summary

**Adding a use case, a route, a status or a `DomainError` leaf without its test is now a build
failure rather than a claim: four gates derive their expectations from the source of truth and
each was driven red once before being trusted — and the two tests the research proved were green
for the wrong reason now fail for the reason they name, one of which had been reporting that
token expiry was enforced while nothing checked it.**

## Performance

- **Duration:** ~15 min
- **Tasks:** 5 of 5
- **Files modified:** 7 (3 created, 4 modified)
- **Suite:** 1019 → **1038 passed**, coverage **100.00 %** (gate 75 %)

## Task Commits

| Task | Name                                        | Commit    | Files                                                       |
| ---- | ------------------------------------------- | --------- | ----------------------------------------------------------- |
| 1    | Use-case totality gate (D-02, TEST-01)      | `590b5bf` | tests/architecture/test_use_case_totality.py                |
| 2    | Endpoint totality: recorder + check (D-03)  | `f921e4b` | tests/integration/conftest.py, test_endpoint_totality.py    |
| 3    | Negative-path totality (D-04, TEST-04)      | `ade4868` | test_tasks.py, test_error_contract_totality.py              |
| 4    | The two D-14 findings                       | `0b9463d` | test_auth.py, test_concurrent_writes.py                     |
| 5    | Close the plan                              | (this)    | 06-01-SUMMARY.md, STATE.md, ROADMAP.md                      |

## The four gates, and the red that earned each green

None of these is trusted on the strength of passing. Each was driven red once by a temporary edit,
the edit reverted, and `git status --porcelain -- src/` confirmed empty afterwards. The transcripts
are not kept (D-15); the edit that produced each red is named here instead.

1. **Use-case totality** — `tests/architecture/test_use_case_totality.py`. 22 symbols discovered,
   all 22 covered. Red by moving `tests/unit/application/test_login.py` aside, which reported
   `Login -> src/taskmanager/application/use_cases/auth/login.py:77` as uncovered. Also red on a
   fictitious name added to `REQUIRED_USE_CASE_SYMBOLS`, and correctly *not* red on a name removed
   from it — the guard is a subset check, deliberately.
2. **Endpoint totality** — `tests/integration/test_endpoint_totality.py`. All 19 published
   operations recorded on a full run. Red twice: a planted `GET /api/v1/ping` in the app factory was
   named as never requested, and unwiring the ASGI wrapper from the two fixtures tripped the
   `REQUESTED` non-vacuity assertion instead of leaving the comparison trivially satisfied.
3. **Transition complement** — `tests/integration/api/test_tasks.py`. 4 cases derived from
   `ALLOWED_TRANSITIONS` (`pending->pending`, `in_progress->in_progress`, `completed->pending`,
   `completed->completed`). Red by adding `TaskStatus.PENDING` to
   `ALLOWED_TRANSITIONS[TaskStatus.COMPLETED]`, which dropped the parametrization to three cases and
   turned the older hard-coded 409 test red — which is the derivation working.
4. **Error-leaf totality** — `tests/architecture/test_error_contract_totality.py`. 9 raisable
   leaves, all asserted. Red by renaming the `task_not_found` code literal, which reported
   `task_gone_missing -> TaskNotFoundError`.

## The two D-14 findings, before and after

Both are handed to **plan 03** for one dated `AI_WORKFLOW.md` incident entry; nothing was written
to that file here.

**Finding 1 — the expired-token case was not testing expiry.**
*Before:* `test_unauthenticated_requests_are_refused_with_the_one_shared_body` never seeded a
`users` row for `OWNER_ID`, and `AuthenticateActor` confirms the subject on every request, so six
of its seven cases were refused for the unknown-subject reason whatever credential they carried.
Measured in research: with `"verify_exp": False` planted in
`src/taskmanager/infrastructure/security/tokens.py`, the whole selection stayed green — a suite
reporting that token expiry is enforced while nothing checked it.
*After:* the test takes `session_factory` and seeds `a_user()` before driving the cases. The same
plant now turns `an_expired_token` red (and the comparative body test with it), verified this plan.
`a_token_for_an_unknown_subject` still signs for a fresh `uuid.uuid4()`, which is now the only case
that relies on an unseeded subject, and its docstring says so.

**Finding 2 — `DeleteTaskList`'s lock had no proof behind it.**
*Before:* dropping `for_update=True` from `use_cases/task_lists/delete.py` turned exactly one test
red, the fakes-based road pin in `test_write_paths_hold_what_they_change.py`, which proves which
method the use case calls and can say nothing about whether a database made anyone wait.
*After:* a fifth case in `tests/integration/test_concurrent_writes.py` queues a real
`DeleteTaskList` behind a hand-held lock on two real connections and asserts it is refused with
`TaskListNotFoundError` — plus the mandatory `assert waited`. With `for_update=True` dropped it is
now the **only** failure in that module, answering `None` (a 204, "your delete succeeded") for a
list another caller had already removed.

## Deviations from Plan

**1. [Rule 1 — wrong measurement in the plan] `REQUIRED_USE_CASE_SYMBOLS` names 22 symbols, not 20**
- **Found during:** Task 1
- **Issue:** the plan and `06-RESEARCH.md` both say "the 20 use-case symbols", while the enumeration
  they give lists 22 and an AST scan of the tree finds 22.
- **Fix:** all 22 are named, the comment records that the prose count was wrong and the enumeration
  right, and the guard stays a subset check.
- **Commit:** `590b5bf`

**2. [Rule 1 — a falsification in the plan does not falsify] task 1's third acceptance check**
- **Found during:** Task 1
- **Issue:** "renaming `test_list_users.py` makes the gate red naming `ListUsers`" is false —
  `test_write_paths_hold_what_they_change.py` also imports and constructs `ListUsers`, so the gate
  stays green. Only 8 of the 22 symbols have a single coverer.
- **Fix:** the equivalent check was run against one of those eight: moving `test_login.py` aside
  turned the gate red naming `Login` with its declaration site. The spirit of the criterion is met;
  its literal form could not be.
- **Commit:** `590b5bf`

**3. [Rule 2 — a gate that satisfied itself] `test_error_contract_totality.py` excludes itself**
- **Found during:** Task 3
- **Issue:** written as the plan specifies, the gate passed while proving nothing: its own
  `REQUIRED_RAISED_CODES` non-vacuity guard names all nine codes as string literals in a file under
  `tests/`, which the `tests/` scan counted as coverage.
- **Fix:** `SELF` is excluded from the scan, `test_the_self_exclusion_is_load_bearing` fails if the
  exemption ever outlives its reason, and the module docstring records that it was written the wrong
  way first. The `task_not_found` falsification was then run against the corrected gate.
- **Commit:** `ade4868`

**4. [Rule 2 — the discovery had a blind spot] the error contract lives in one module**
- **Found during:** Task 3
- **Issue:** `DomainError.__subclasses__()` sees only classes whose module has been imported, so a
  leaf declared in an adapter would be raisable and invisible to the gate.
- **Fix:** a second test asserts no `DomainError` subclass is declared outside
  `domain/exceptions.py` — which is a rule worth having on its own.
- **Commit:** `ade4868`

**5. [Rule 2 — the finding was wider than the plan's half of it] the comparative auth test is seeded too**
- **Found during:** Task 4
- **Issue:** the plan seeds the caller in the parametrized test only. Unseeded,
  `test_every_unauthenticated_refusal_carries_the_same_body_as_the_others` was comparing six copies
  of the unknown-subject answer, so "all seven bodies are byte-identical" was true by construction.
- **Fix:** seeded there too. The bodies still come out byte-identical, which is now a claim about the
  handler rather than about the fixture.
- **Commit:** `0b9463d`

**6. [Rule 3 — the plan's chosen direction could not falsify] the deletion case asserts the answer**
- **Found during:** Task 4
- **Issue:** the plan leaves the direction open. The obvious end-state assertion cannot pin
  `DeleteTaskList`'s locking read at all: without it the plain read passes the guard on a stale row
  and the `DELETE` statement blocks on the same lock by itself, so the row ends up gone and someone
  still waits either way.
- **Fix:** the case asserts the *answer* — the queued deletion must be refused with the guard's 404
  rather than told 204 — which is the one thing the two versions disagree about. Confirmed by the
  falsification: with `for_update=True` dropped it is the only failing test in the module.
- **Commit:** `0b9463d`

## For plan 04: the ADR-worthy rules this plan introduced

Next free ADR number is **085**. Three rules earn one each, with a `CLAUDE.md` "Project Rules"
bullet apiece:

1. **Use-case totality.** Every public module-level symbol under `application/use_cases/` must be
   imported, alongside the in-memory fakes, and constructed or called by some module under
   `tests/unit/application/`. Enforced by `tests/architecture/test_use_case_totality.py`. Worth
   recording with its honest limit: this proves reachability from the fakes-based suite, and the
   coverage gate proves execution.
2. **Endpoint totality, observed.** Every operation in `app.openapi()` must be requested through
   HTTP during a full run, recorded by the ASGI wrapper in `tests/integration/conftest.py` and
   checked by `tests/integration/test_endpoint_totality.py`; the total half skips on a partial
   selection, and the recorded-subset half is always on. Worth recording alongside ADR-057, whose
   `_IncludedRouter` fact is why the suffix resolver exists.
3. **Error-leaf totality.** Every `DomainError` leaf actually raised under `src/` must have its
   RFC 9457 `code` asserted as a non-docstring string literal somewhere under `tests/`, and every
   leaf must be declared in `domain/exceptions.py`. Enforced by
   `tests/architecture/test_error_contract_totality.py`, which excludes itself from its own scan.

A fourth candidate, if plan 04 wants it: **a gate is not trusted until it has been driven red**, and
**a gate must never be satisfiable by its own non-vacuity guard** — this plan produced a live
example of the second, which is the strongest argument for writing it down.

## Verification Results

```
make lint       -> black 184 files unchanged, isort clean, flake8 clean
make typecheck  -> Success: no issues found in 184 source files
make arch       -> Contracts: 4 kept, 0 broken.
make test       -> 1038 passed, TOTAL 1643 stmts / 154 branches, 100%
```

- `.venv/bin/pytest tests/integration --no-cov` → 317 passed, 1 skipped (the totality half, on a
  partial selection), with the totality module collected last.
- `.venv/bin/pytest tests/integration/api/test_users.py --no-cov` → 6 passed; a focused run is not
  falsely red.
- `.venv/bin/pytest -k task_lists --no-cov` → 65 passed, 964 deselected.
- `.venv/bin/pytest tests/integration/api/test_tasks.py -k complement --no-cov` → 4 cases, ids
  `pending->pending`, `in_progress->in_progress`, `completed->pending`, `completed->completed`.
- `git status --porcelain -- src/` empty after every falsification. No `src/` change was needed by
  this plan; all four fixes are test-side.

## Ceremony

Minimal, per D-15: one SUMMARY, no evidence file, no transcript, no RED artifact. Nothing was
written to `AI_WORKFLOW.md` or `DECISION_LOG.md` — plans 03 and 04 own those.

## Self-Check: PASSED

- `tests/architecture/test_use_case_totality.py` — FOUND
- `tests/architecture/test_error_contract_totality.py` — FOUND
- `tests/integration/test_endpoint_totality.py` — FOUND
- commits `590b5bf`, `f921e4b`, `ade4868`, `0b9463d` — all FOUND in `git log`
