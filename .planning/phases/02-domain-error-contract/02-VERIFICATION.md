---
phase: 02-domain-error-contract
verified: 2026-09-18T18:05:00Z
status: passed
score: 4/4 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: human_needed
  previous_score: 4/4
  gaps_closed:
    - "WR-01: AuthenticationError answered 401 with no WWW-Authenticate header"
    - "WR-02: a bare/unmapped DomainError answered 500 with a non-D-08 body and no logging"
  gaps_remaining: []
  regressions: []
deferred:
  - truth: "WR-05 (server-side clock/rehydration faults misclassified as 422) is not fixed"
    addressed_in: "Phase 3"
    evidence: "02-REVIEW-FIX.md records the fix as skipped because it contradicts locked decision D-14 in 02-CONTEXT.md, and explicitly recommends raising it as a Phase 3 decision point once SystemClock and the SQLAlchemy mappers exist to give the question a concrete answer (candidate ADR superseding part of D-14)."
---

# Phase 2: Domain & Error Contract Verification Report

**Phase Goal:** The business rules and the API's error shape exist as stable, framework-free contracts that every later layer is written against.
**Verified:** 2026-09-18T18:05:00Z
**Status:** passed
**Re-verification:** Yes — after code-review fix commits `cf12361..e9af1aa`

## Method

Re-ran all four gates live from the repo root (`make lint`, `make typecheck`, `make arch`,
`make test`) rather than trusting `02-REVIEW-FIX.md` prose. Read the actual diffs in
`src/taskmanager/presentation/api/errors/handlers.py` and `mapping.py`, and the new/updated
tests in `tests/api/test_error_contract.py` and `tests/probe.py`, to confirm WR-01 and WR-02
are fixed in code and pinned by tests, not just described as fixed. Cross-checked the WR-05
skip against the actual `D-14` text in `02-CONTEXT.md`. Re-checked ARC-02/04/06/07 against
`.planning/REQUIREMENTS.md`. This is a focused re-verification: the previous run's four
roadmap truths, artifacts and key links were already independently confirmed against the
codebase (not SUMMARY.md) and are not re-derived from scratch here — only the two items that
kept the phase at `human_needed` are re-examined in full, plus a live gate re-run to catch
regressions from the fix commits.

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria, Phase 2)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `TaskList`, `Task`, `User` are stdlib dataclasses/Enums; `test_domain_is_stdlib_only.py` proves the domain imports only stdlib via `sys.stdlib_module_names` | ✓ VERIFIED | Unchanged since the previous run; re-confirmed live: `make arch` → "Domain is framework-free KEPT", `make test` includes the AST-based stdlib-only test, still green. |
| 2 | Closed `DomainError` hierarchy (not found, conflict, business-rule, auth, authz) with stable `code`/details; domain unit tests show `InvalidStatusTransitionError` raised specifically | ✓ VERIFIED | Hierarchy unchanged (12 leaf/branch subclasses); `test_hierarchy_is_closed` still passes. `Task.__post_init__` now additionally enforces the `status`/`completed_at` coherence invariant (WR-07 fix, commit `e9af1aa`) via `ValidationError`, strengthening rather than weakening this truth. |
| 3 | All 8 ports exist as `typing.Protocol` with no implementation; use-case shape fixed and documented | ✓ VERIFIED | Unchanged shape. `UnitOfWork.__aexit__` contract made normative (WR-06, commit `bfdda22`): "MUST roll back whatever was not committed" instead of permissive language, with 3 new tests in `test_ports.py` and rollback-counter assertions added to all 8 `test_change_task_status.py` cases. Shape (single class, one `execute`) is intact. `make typecheck` still green under strict mode. |
| 4 | Single exception-handling point converts any `DomainError`, request-validation error and unexpected error into one consistent `application/problem+json` shape, proven against a probe route | ✓ VERIFIED | **Both previously-open gaps in this truth are now closed.** Read `handlers.py` lines 51-83: `handle_domain_error` resolves `status_for(exc)` once; if `status >= 500` it now delegates to `handle_unexpected_error` (WR-02 fix, commit `62ef9eb`) — an unmapped `DomainError` gets the exact D-08 fixed body (`internal_error`, no message, no `errors`) and is logged via `logger.error(..., exc_info=exc)`, proven by `test_unmapped_domain_error_answers_the_fixed_internal_error_body` and `test_unmapped_domain_error_is_logged_like_any_other_server_fault` against `/_probe/unmapped-domain`. If `status == 401`, `response.headers["WWW-Authenticate"] = "Bearer"` is set (WR-01 fix, commit `cf12361`), proven by `test_authentication_error_answers_401_with_the_mandatory_challenge` against a new `/_probe/unauthenticated` route (`tests/probe.py:57-65`) that raises `AuthenticationError`, asserting `response.headers["www-authenticate"] == "Bearer"`. The suite grew from 140 to 151 tests, all passing, with 100% coverage maintained (`presentation/api/errors/handlers.py`: 35 stmts / 6 branches, 100%). |

**Score:** 4/4 truths verified

### Fixes Confirmed by Direct Code Reading (not SUMMARY.md prose)

| ID | Claim | File(s) read | Verified |
|----|-------|---------------|----------|
| WR-01 | 401 now carries `WWW-Authenticate: Bearer` | `handlers.py:74-83`, `tests/probe.py:57-65`, `tests/api/test_error_contract.py:95-115` | ✓ Confirmed: `if status == 401: response.headers["WWW-Authenticate"] = "Bearer"`; test asserts the header and full D-06 body. |
| WR-02 | Unmapped `DomainError` routes to the fixed 500 body and is logged | `handlers.py:53-62`, `mapping.py:36-58`, `tests/api/test_error_contract.py:150-189` | ✓ Confirmed: `if status >= 500: return await handle_unexpected_error(request, exc)`; two tests assert the fixed `internal_error` body (no leaked message/details) and a single ERROR log record with `exc_info`. |
| WR-05 (skip) | Skip is a deliberate, documented deferral, not a silent drop | `02-CONTEXT.md` line 89 (`D-14`), `02-REVIEW-FIX.md` "Skipped Issues" section | ✓ Confirmed: `D-14` unambiguously states a naive datetime reaching the domain is `ValidationError`; the proposed WR-05 fix would split this into `ValidationError`/`TypeError` by field, directly contradicting the locked decision. Recommended follow-up (a Phase 3 ADR once `SystemClock`/mappers exist) is recorded. Treated as `deferred`, not a gap. |

### Required Artifacts

No changes to the artifact list from the previous run; the fix commits modified existing
artifacts (`handlers.py`, `mapping.py`, `task.py`, `task_list.py`, `change_task_status.py`,
`unit_of_work.py`, `fakes.py`, test files) rather than adding or removing any. All previously
✓ VERIFIED artifacts were re-opened for this run where the diff touched them (see table above)
and remain substantive and wired.

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `handlers.py::handle_domain_error` | `handlers.py::handle_unexpected_error` | direct delegation when `status >= 500` | ✓ WIRED (new) | `handlers.py:61-62`; proven by the two new probe-driven tests. |
| `handlers.py::handle_domain_error` | HTTP response headers | `response.headers["WWW-Authenticate"]` on 401 | ✓ WIRED (new) | `handlers.py:81-82`; proven by `test_authentication_error_answers_401_with_the_mandatory_challenge`. |
| `change_task_status.py` | `application/ports/unit_of_work.py` | `UnitOfWork` async context manager | ✓ WIRED (strengthened) | Rollback obligation is now normative in the port docstring and observed by the fake's `rollbacks` counter across all 8 use-case tests (previously flagged as untested in the prior run's WR-06 caveat — now closed). |

### Data-Flow Trace (Level 4)

Not applicable in the UI-rendering sense — this phase has no rendering components. The
relevant "data flow" is exception → status → response body, traced above: both previously
disconnected paths (unmapped `DomainError`, missing 401 header) now flow through real logic
proven by live tests, not static/hardcoded output.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full gate suite is green at HEAD | `make lint && make typecheck && make arch && make test` | lint: clean; typecheck: "Success: no issues found in 59 source files"; arch: "Contracts: 3 kept, 0 broken"; test: "151 passed", 100.00% coverage, `--cov-fail-under=75` satisfied | ✓ PASS |
| WR-01 fix produces `WWW-Authenticate` on 401 | read `handlers.py:81-82` + ran `make test` (includes the pinning test) | header set conditionally on `status == 401`; test asserts it live | ✓ PASS |
| WR-02 fix routes unmapped `DomainError` to the fixed 500 | read `handlers.py:53-62` + ran `make test` (includes the pinning tests) | delegation confirmed; both new tests pass live | ✓ PASS |

### Probe Execution

No `scripts/*/tests/probe-*.sh` shell probes exist in this project; the "probe" referenced by
the phase is `tests/probe.py`, a test-only FastAPI router (not a shell script), already
covered under Behavioral Spot-Checks and the Observable Truths table above via `make test`.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|--------------|--------|----------|
| ARC-02 | 02-01, 02-03, 02-06, 02-07 | Domain entities/value objects stdlib-only | ✓ SATISFIED | REQUIREMENTS.md row `Complete`; unchanged, re-confirmed live via `make arch`. |
| ARC-04 | 02-05, 02-07 | Use cases depend only on Protocol ports | ✓ SATISFIED | REQUIREMENTS.md row `Complete`; unchanged, re-confirmed live via `make typecheck`. |
| ARC-06 | 02-02, 02-03, 02-06 | Closed `DomainError` hierarchy; no `HTTPException` outside `presentation` | ✓ SATISFIED | REQUIREMENTS.md row `Complete`; hierarchy unchanged, `__post_init__` invariant strengthened (WR-07). |
| ARC-07 | 02-04 | Single RFC 9457 exception-handling point | ✓ SATISFIED | REQUIREMENTS.md row `Complete`; the two defects previously found in this mechanism (WR-01, WR-02) are now fixed and tested. |

No orphaned requirements. `.planning/REQUIREMENTS.md` maps only ARC-02/04/06/07 to Phase 2,
and all four are marked `Complete`.

### Anti-Patterns Found

Re-scanned every file touched by the fix commits
(`handlers.py`, `mapping.py`, `task.py`, `task_list.py`, `change_task_status.py`,
`unit_of_work.py`, `tests/unit/application/fakes.py`) for `TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/
`PLACEHOLDER` markers: none found. No stub returns, no empty handlers, no hardcoded-empty
props introduced by the fixes. Coverage remains 100% over all statements/branches in
`src/taskmanager`, with no new `pragma: no cover` and no `omit` entry — the review-fix report's
claim that every new branch is exercised by a new test is confirmed by the live coverage run
(151 passed, 100.00%).

Remaining open items, all correctly classified as non-blocking for this phase's goal:

- **WR-03, WR-04, WR-06, WR-07** were also fixed in this pass (beyond the two that blocked
  the previous verification), further hardening the reference use case and entities that
  Phase 4/5 will copy. Confirmed by reading the diffs and the corresponding new tests.
- **WR-05** was deliberately skipped because the proposed fix contradicts locked decision
  `D-14` in `02-CONTEXT.md`. This is a genuine, well-reasoned deferral to a Phase 3 decision
  point (once `SystemClock` and the SQLAlchemy mappers exist to make the classification
  question concrete), not a silently dropped gap. Filed under `deferred` in the frontmatter
  above, per the explicit instruction to treat it as such.
- **IN-01 through IN-09** (11 info-level findings from `02-REVIEW.md`) remain open; these were
  out of scope for the review-fix pass (`fix_scope: critical_warning`) and do not affect any
  of the four roadmap success criteria.

### Human Verification Required

None. The single item that previously required a human decision — whether to fix WR-01/WR-02
now or defer them — has been resolved: both were fixed in code, proven by new tests, and the
full gate suite is green. WR-05's skip is a self-contained, already-documented engineering
decision (contradicts a locked ADR-backed decision, recommended as a Phase 3 ADR) that does
not require further human input to close out this phase.

## Gaps Summary

No gaps. All four roadmap success criteria for Phase 2 are met and re-verified against the
codebase at HEAD (commits `cf12361..e9af1aa`), not against `02-REVIEW-FIX.md` prose:

- SC1 (stdlib-only domain): unchanged, still mechanically proven.
- SC2 (closed `DomainError` hierarchy): unchanged, strengthened by the WR-07 `__post_init__`
  invariant.
- SC3 (8 Protocol ports, fixed use-case shape): unchanged, strengthened by the WR-06 normative
  rollback contract.
- SC4 (single exception-handling point, RFC 9457 shape): the two real defects previously found
  in this exact mechanism — a spec-violating 401 and an unlogged, non-D-08 500 for unmapped
  `DomainError`s — are now fixed in `handlers.py`/`mapping.py` and pinned by new tests
  (`test_authentication_error_answers_401_with_the_mandatory_challenge`,
  `test_unmapped_domain_error_answers_the_fixed_internal_error_body`,
  `test_unmapped_domain_error_is_logged_like_any_other_server_fault`).

`make lint`, `make typecheck`, `make arch` and `make test` all pass live from the repo root:
151 tests passed, 100.00% coverage (gate is 75%), 3/3 import-linter contracts kept. Requirements
ARC-02, ARC-04, ARC-06, ARC-07 are all satisfied and marked `Complete` in
`.planning/REQUIREMENTS.md`. WR-05 is filed as a deliberate, ADR-backed deferral to Phase 3, not
a gap. Phase 2's goal — stable, framework-free domain and error contracts for every later layer
to build on — is achieved.

---

_Verified: 2026-09-18T18:05:00Z_
_Verifier: Claude (gsd-verifier)_
