---
phase: 06-test-hardening-coverage
verified: 2026-09-19T00:00:00Z
status: gaps_found
score: 4/5 must-haves verified
overrides_applied: 0
gaps:
  - truth: "Every test asserts on response bodies (not just status codes), and every mutating test re-reads through the API to confirm the change persisted (roadmap SC-3)"
    status: partial
    reason: >
      tests/integration/api/test_permission_matrix.py drives every mutating verb
      (POST/PATCH/PUT/DELETE) exclusively through `client.request(cell.row.method, ...)`.
      The assertion-quality gate's `MUTATING_VERBS` set only matches the literal attribute
      names `post`/`put`/`patch`/`delete` (tests/architecture/test_assertion_quality.py:202),
      so every call recorded as verb `"request"` is invisible to half (b) even though it is
      in `REQUEST_VERBS` and counts the test as an HTTP test. For the owner column's
      successful mutating cells (rows 6, 9, 10, 11, 14, 16, 17, 18 — register, PATCH/DELETE a
      list, POST/GET a task, PATCH a task, change status, assign/unassign) the 2xx branch of
      `assert_the_body_the_status_promises` calls only `assert_no_challenge_was_issued`, which
      checks the absence of a `WWW-Authenticate` header and of a `problem+json` content type —
      no body assertion, no re-read. The test carries no `no_reread` marker and is absent from
      `REQUIRED_NO_REREAD`, yet `pytest tests/architecture/test_assertion_quality.py --no-cov`
      passes with zero offenders (verified: 28 passed). This is the live instance of code-review
      finding WR-02, left open in 06-REVIEW.md's "Not fixed, still open" list, and it directly
      contradicts plan 06-02's own must-have truth ("A test that issues POST, PATCH, PUT or
      DELETE and never reads the resource back through the API fails a pytest run unless it
      carries an explicitly registered and justified exemption").
    artifacts:
      - path: "tests/integration/api/test_permission_matrix.py"
        issue: "Owner-success mutating cells (rows 6,9,10,11,14,16,17,18) assert only header absence, never a body, and are never re-read; no no_reread marker"
      - path: "tests/architecture/test_assertion_quality.py"
        issue: "MUTATING_VERBS (post/put/patch/delete) does not include the `request` attribute name, so client.request(method, ...) mutations are invisible to half (b)'s re-read check"
    missing:
      - "Widen MUTATING_VERBS detection (or add a dedicated resolution) to classify client.request(<verb>, ...) calls by their first positional argument when it is a literal HTTP method"
      - "Either give test_the_permission_matrix_answers_what_the_table_promises a registered, justified no_reread exemption, or add body assertions plus a re-read to its 2xx mutating cells"
human_verification: []
---

# Phase 6: Test Hardening & Coverage Verification Report

**Phase Goal:** The test suite proves the API behaves correctly rather than merely exercising it, and the coverage number is honest.
**Verified:** 2026-09-19
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth (roadmap SC) | Status | Evidence |
|---|---------|------------|-----------|
| 1 | Every domain rule and every use case has a unit test against in-memory fakes (no DB/HTTP), and every endpoint has an integration test through real PostgreSQL, per-test isolated | ✓ VERIFIED | `tests/architecture/test_use_case_totality.py` (20 use-case symbols, `REQUIRED_USE_CASE_SYMBOLS`), `tests/integration/test_endpoint_totality.py` (19 published operations vs `REQUESTED`). `make test-unit` (`pytest -m unit --no-cov`) runs 773 tests with the database stopped-equivalent slice, no HTTP; `make test` runs the remaining 323 `integration`-marked tests through real Postgres. Marker partition verified total today: 773 + 323 = 1096 = full collected count. |
| 2 | Negative-path tests exist and pass for the RFC 9457 error contract, the full cross-user 404/403 matrix, every invalid status transition, and each auth failure mode | ✓ VERIFIED | `tests/architecture/test_error_contract_totality.py` (9 raised `DomainError` codes, `REQUIRED_RAISED_CODES`); `tests/integration/api/test_permission_matrix.py` (76-cell matrix, `test_the_table_covers_every_operation_the_document_publishes`); `tests/unit/domain/test_task_status.py::test_transition_table_matches_the_documented_matrix` pins the exact transition table independently (not self-referential), plus the derived HTTP complement in `test_tasks.py`; `test_auth.py`'s seven auth-failure cases now seed the caller (fixed in 06-01, re-verified live: `make break-check` break 4 reddens `test_auth.py::test_unauthenticated_requests_are_refused_with_the_one_shared_body[an_expired_token]`). WR-10 (the complement's oracle is derived from the code under test) is a real robustness gap but does not currently falsify this truth, because the independent unit-level pin and the retained hard-coded HTTP test both catch break 2 today (confirmed by `make break-check`). |
| 3 | Every test asserts on response bodies (not just status codes), and every mutating test re-reads through the API to confirm the change persisted | ✗ FAILED | See Gaps. `test_permission_matrix.py`'s owner-success mutating cells assert only header absence and are never re-read, and escape the assertion-quality gate's `client.request(...)` blind spot (WR-02, confirmed live: gate passes 28/28 with zero offenders while the hole is reproducible by reading `MUTATING_VERBS`, `REQUEST_VERBS` and the 2xx branch of `assert_the_body_the_status_promises`). The equivalent operations ARE fully body-asserted and re-read elsewhere (`test_task_lists.py`, `test_tasks.py`, `test_assignment.py`, per the 06-02 sweep), so the underlying endpoints are not unverified — but the literal truth ("every mutating test re-reads") is false for this module today. |
| 4 | A deliberate-break spot check — inverting the completion-percentage formula — turns the suite red, and the episode is recorded in AI_WORKFLOW.md | ✓ VERIFIED | `make break-check` run live: all 5 breaks reported RED (break 1: 7 failed; break 2: 5 failed; break 3 large permission-matrix/access red set; break 4: 5 failed including 2 HTTP tests; break 5: 2 failed including the real concurrency test), exit 0, ~34.5s, `git status --porcelain` clean afterward. `AI_WORKFLOW.md` §"2026-09-19 — Five deliberate defects, and the two this suite could not see" records all five breaks, both original survivals (token-expiry and lock), their fixes, and the verbatim `make break-check` output. |
| 5 | `--cov-fail-under=75` passes locally and in CI with coverage measured over `src/taskmanager` only, tests excluded from the denominator | ✓ VERIFIED (CI leg is config-only, not run) | `make test` run live: 1096 passed, 100.00% over 1659 statements, `Required test coverage of 75% reached`. `pyproject.toml` pins `[tool.coverage.run] source = ["taskmanager"]`, no `omit`; `tests/architecture/test_coverage_configuration.py` gates the threshold floor, source, omit-absence and (post-fix) the exact `exclude_also` list plus a real-statement-exclusion scan (CR-01 fixed in commit `8a0439f`). `.github/workflows/ci.yml`'s final step is a bare `pytest` invocation, so the same `pytest.ini` addopts (`--cov-fail-under=75`) apply — this is the phase's documented one manual verification and cannot be observed running from this session (nothing pushed). |

**Score:** 4/5 truths verified (1 FAILED — see Gaps)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `tests/architecture/test_use_case_totality.py` | D-02 use-case totality gate, `REQUIRED_USE_CASE_SYMBOLS` | ✓ VERIFIED | Exists, contains the constant, passes; WR-08 (attribute-call/dead-code blind spot) is a latent robustness gap, not a present false green (checked: no offending shape exists in the current suite). |
| `tests/architecture/test_error_contract_totality.py` | Every raised leaf's code asserted, `REQUIRED_RAISED_CODES` | ✓ VERIFIED | Exists, 9 codes named, passes; WR-07 (alias/variable `raise` blind spot) confirmed a future hole, not present (all 9 codes appear inside real `assert` statements today). |
| `tests/integration/test_endpoint_totality.py` | Two-sided endpoint totality over the run-wide recorder | ✓ VERIFIED | Exists and passes on a full run; WR-06 (silent skip on invocation drift) is real but Makefile/Dockerfile/CI all still invoke bare `pytest`, so the gate is live today. |
| `tests/integration/conftest.py` | ASGI recording wrapper + `pytest_collection_modifyitems` | ✓ VERIFIED | `REQUESTED` set and wrapper present and wired into both client fixtures. |
| `tests/architecture/test_assertion_quality.py` | Both halves + exemption frozenset + companion test | ⚠️ PARTIAL | Exists, both halves implemented, `REQUIRED_NO_REREAD` present and self-justifying for the ~10 registered exemptions — but WR-02's `client.request()` blind spot lets a real, unregistered offender through (see Gaps). WR-03 (bare-helper-call / truthy-headers shapes) is a latent gate weakness with no live exploiting test today. |
| `pytest.ini` | `no_reread` marker registered | ✓ VERIFIED | `markers =` includes `no_reread`; `--strict-markers` did not error on collection. |
| `scripts/break-check.sh` | Five mutations applied, run, asserted red, restored | ✓ VERIFIED | Ran live: all 5 breaks RED, tree clean after. CR-02 (any-non-zero-is-red) fixed in `142d64c` — script now requires an unmutated green baseline and a `FAILED` line. WR-01 (HUP/QUIT untrapped under dash) fixed in `f5b2474`. |
| `tests/unit/test_break_check.py` | Script driven as a program in a throwaway repo | ✓ VERIFIED | Present; WR-09 (verdict paths under-tested) fixed alongside CR-02 per 06-REVIEW.md's "Fixes applied" table. |
| `AI_WORKFLOW.md` | Dated incident entry with both survivals | ✓ VERIFIED | Entry present, matches the live `make break-check` output. |
| `tests/architecture/test_coverage_configuration.py` | Coverage configuration pin, `EXPECTED_EXCLUDE_ALSO` | ✓ VERIFIED (post-fix) | CR-01 fixed in `8a0439f`: `...` removed from `exclude_also`, `test_no_exclusion_removes_a_real_statement` added. WR-04's cheap half (single-config-file pin) fixed in `54cd9cd`; the pragma-spelling half remains open (recorded, low severity — 0 pragmas exist under `src/` today so it is not a present false green). |
| `tests/problem_details.py` | `MEMBERS`/`PROBLEM_JSON`, never collected | ✓ VERIFIED | Exists; `pytest --collect-only -q \| grep -c problem_details` is 0. |
| `tests/unit/presentation/test_error_contract.py` | Error-contract tests moved | ✓ VERIFIED | `tests/api/` removed; module exists under its new home. |
| `tests/conftest.py` | Unmarked-item collection guard | ✓ VERIFIED (present, "at least one" not "exactly one" per WR-05) | `pytest_collection_modifyitems` present; today's suite has no dual-marked test so the gap is latent, not live. |
| `Makefile` | `test-unit` target | ✓ VERIFIED | `make test-unit` run live: 773 passed, 6.28s, no coverage.xml rewrite. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `tests/integration/conftest.py` | `tests/integration/test_endpoint_totality.py` | `REQUESTED` set | ✓ WIRED | Confirmed by a green full-suite run with the totality item passing. |
| `tests/integration/api/test_tasks.py` | `task_status.py::ALLOWED_TRANSITIONS` | derived complement | ✓ WIRED | Confirmed; independently backed by `test_transition_table_matches_the_documented_matrix` (WR-10 noted, not blocking). |
| `tests/integration/api/test_auth.py` | `tests/integration/conftest.py::seed` | caller seeded before unauthenticated cases | ✓ WIRED | Confirmed live via `make break-check` break 4 reddening an HTTP test. |
| `tests/architecture/test_assertion_quality.py` | `tests/integration/api/` | AST scan, cross-module helper resolution | ⚠️ PARTIAL | Wired for `post/put/patch/delete`-named calls; not wired for `client.request(verb, ...)` calls (WR-02). |
| `Makefile` | `scripts/break-check.sh` | `break-check` target | ✓ WIRED | `make break-check` runs the script and reports correctly; absent from `.pre-commit-config.yaml` and `.github/workflows/ci.yml` as required. |

### Data-Flow Trace (Level 4)

Not applicable in the usual sense (no UI/dynamic-rendering artifacts in this phase). The equivalent check — do the gates measure real signal rather than a static/vacuous pass — was performed per-gate above via planted-source review (06-REVIEW.md) and live falsification runs (`make break-check`, `pytest -m unit`/`-m integration` count sums, `make test`).

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Coverage gate enforces 75% over `src/taskmanager` only | `make test` | 1096 passed, 100.00% over 1659 statements, gate reached | ✓ PASS |
| Architecture contracts still hold after phase changes | `make arch` | 4 kept, 0 broken | ✓ PASS |
| Unit slice runs with no database | `make test-unit` | 773 passed, 6.28s, no coverage.xml touch | ✓ PASS |
| Marker partition is total | `pytest -m unit`/`-m integration` collected counts | 773 + 323 = 1096 (matches full collect) | ✓ PASS |
| Assertion-quality gate is green | `pytest tests/architecture/test_assertion_quality.py --no-cov` | 28 passed, 0 offenders | ✓ PASS (but see Gaps — passing does not mean total) |
| Deliberate-break spot check reproduces | `make break-check` | All 5 breaks RED, exit 0, ~34.5s, tree clean | ✓ PASS |

### Probe Execution

No `scripts/*/tests/probe-*.sh` convention in this project; `make break-check` is this phase's equivalent mutation-testing probe and was executed directly above (not a `probe-*.sh` file, so not double-counted here).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| TEST-01 | 06-01 | Unit tests cover domain rules and every use case via fakes, no DB/HTTP | ✓ SATISFIED | `test_use_case_totality.py`, `make test-unit` (773 tests, no DB) |
| TEST-02 | 06-01 | Integration tests exercise every endpoint through HTTP against real Postgres, per-test isolated | ✓ SATISFIED | `test_endpoint_totality.py`, 323 `integration`-marked tests against real Postgres |
| TEST-03 | 06-04 | Coverage >= 75%, enforced by `--cov-fail-under=75` locally and in CI | ✓ SATISFIED (CI leg config-only) | `make test` 100.00% over 1659 statements; `test_coverage_configuration.py`; CI's `pytest` step inherits the same addopts |
| TEST-04 | 06-01, 06-04 | Negative-path tests for error contract, 404/403 matrix, invalid transitions, auth failures | ✓ SATISFIED | `test_error_contract_totality.py`, `test_permission_matrix.py` (76 cells), transition complement, seeded auth-failure cases |
| TEST-05 | 06-02, 06-03 | Every test contains meaningful assertions; deliberate-break spot check performed and recorded | ⚠️ PARTIAL | `make break-check` and `AI_WORKFLOW.md` entry fully satisfy the break-check half; the "meaningful assertions" half has a live, unregistered exception in `test_permission_matrix.py` (WR-02) |

No orphaned requirement IDs: REQUIREMENTS.md maps exactly TEST-01..05 to Phase 6, and all five are declared across the four plans' frontmatter.

### Anti-Patterns Found

No `TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/`PLACEHOLDER` markers found in any file this phase modified (scanned all 19 files listed in 06-REVIEW.md's `files_reviewed_list` plus `tests/problem_details.py`, `tests/conftest.py`, `Makefile`, `pyproject.toml`, `pytest.ini`).

The phase's own code review (`06-REVIEW.md`) found 2 criticals and 11 warnings. Both criticals were fixed (commits `8a0439f`, `142d64c`) and reproduced as fixed in this verification (`make break-check` no longer accepts a false RED; the `...` coverage exclusion no longer hides real statements). One warning (WR-01) and half of another (WR-04) were also fixed (`f5b2474`, `54cd9cd`). Of the remaining open warnings, WR-02 was independently re-verified in this session to be a live, material gap against roadmap SC-3 (see Gaps). WR-03, WR-05, WR-06, WR-07, WR-08, WR-10, WR-11 and the pragma-spelling half of WR-04 were checked against the current suite and confirmed to be **latent** robustness gaps in the gates (a future regression could sneak through undetected) rather than **present** false-greens — i.e., no test in today's suite currently exploits them to hide a real hole, except WR-02.

### Human Verification Required

None. Every truth in this phase is either checkable by running a command/gate or by reading gate source against the AST rules it claims to enforce, which was done directly.

### Gaps Summary

Four of five roadmap success criteria hold under direct, reproduced verification (fresh `make test`, `make test-unit`, `make arch`, `make break-check` runs, plus reading the gates' own detection logic against the claims their docstrings make). The phase's own code review already caught and disclosed the two most serious problems (the `...` coverage exclusion and the always-green break script), and both were fixed with new counter-gates before this verification, which was independently re-confirmed live rather than taken on the SUMMARY's word.

One gap remains open and is material enough to block: `tests/integration/api/test_permission_matrix.py`'s owner-success mutating cells (list/task creation, rename, delete, status change, assign/unassign) are asserted only by header absence and are never re-read through the API, and the assertion-quality gate that exists specifically to make "every mutating test re-reads" a build failure cannot see them because it recognizes mutating calls only by the literal attribute names `post`/`put`/`patch`/`delete`, not `request(method, ...)`. This is not a hypothetical: the test module exists today, mutates real resources, and is not in `REQUIRED_NO_REREAD`. It was flagged by the phase's own reviewer (WR-02) and left open. The underlying endpoint behaviors are separately and adequately re-read-tested in the per-route modules, so this is a test-suite-completeness gap rather than an unverified endpoint — but it directly contradicts both the roadmap's literal SC-3 wording and plan 06-02's own must-have truth, so it is reported as a gap rather than smoothed over.

Recommended fix (two options, either closes the gap): (a) extend `MUTATING_VERBS`/`requests_made` to resolve `client.request(<literal verb>, ...)` the same way `post`/`patch`/etc. are resolved, then either add a re-read to the matrix's 2xx mutating cells or give the test a registered, justified `no_reread` exemption; or (b) if the matrix's role is deliberately "who may reach this route", not "did the mutation persist" — since persistence is proved elsewhere — register the exemption now with that reasoning, rather than leaving the test outside the gate's field of view entirely.

---

_Verified: 2026-09-19_
_Verifier: Claude (gsd-verifier)_
