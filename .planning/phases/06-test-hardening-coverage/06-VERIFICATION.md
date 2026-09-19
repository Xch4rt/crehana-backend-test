---
phase: 06-test-hardening-coverage
verified: 2026-09-19T23:45:00Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 4/5
  gaps_closed:
    - "Every test asserts on response bodies (not just status codes), and every mutating test re-reads through the API to confirm the change persisted (roadmap SC-3) — the client.request(...) blind spot in the assertion-quality gate is closed, and the permission matrix's 2xx mutating cells now assert a document and re-read the resource."
  gaps_remaining: []
  regressions: []
---

# Phase 6: Test Hardening & Coverage Verification Report

**Phase Goal:** The test suite proves the API behaves correctly rather than merely exercising it, and the coverage number is honest.
**Verified:** 2026-09-19
**Status:** passed
**Re-verification:** Yes — after gap closure plan 06-05 (commits `3cde999`, `9701c13`, `533f21a`)

## Goal Achievement

### Observable Truths

| # | Truth (roadmap SC) | Status | Evidence |
|---|---------|------------|-----------|
| 1 | Every domain rule and every use case has a unit test against in-memory fakes (no DB/HTTP), and every endpoint has an integration test through real PostgreSQL, per-test isolated | ✓ VERIFIED (regression-checked) | `make test-unit` and `make test` re-run live this session: 1101 passed total (1096 → 1101 after 06-05 added 5 self-tests to the gate). No structural change to totality gates in 06-05 (files_modified confirms only `test_permission_matrix.py` and `test_assertion_quality.py` touched among test code). |
| 2 | Negative-path tests exist and pass for the RFC 9457 error contract, the full cross-user 404/403 matrix, every invalid status transition, and each auth failure mode | ✓ VERIFIED (regression-checked) | `make break-check` re-run live: break 2 (invalid transition) red (5 failed), break 3 (403/404 matrix) red (30 failed, including 16 permission-matrix cells), break 4 (auth/token expiry) red (5 failed) — all match the counts the prior verification recorded exactly (5, 30, 5). |
| 3 | Every test asserts on response bodies (not just status codes), and every mutating test re-reads through the API to confirm the change persisted | ✓ VERIFIED (gap closed) | See "Gap Closure Evidence" below — independently falsified twice in this session, not merely re-read from the SUMMARY. |
| 4 | A deliberate-break spot check — inverting the completion-percentage formula — turns the suite red, and the episode is recorded in AI_WORKFLOW.md | ✓ VERIFIED (regression-checked) | `make break-check` re-run live: all 5 breaks RED with counts 7, 5, 30, 5, 2 — identical to the prior verification's live run. `git status --porcelain` clean after. `AI_WORKFLOW.md` retains the original incident entry (`### 2026-09-19 — Five deliberate defects...`) plus a new one from 06-05 documenting this gap closure (`### 2026-09-19 — The gate built to catch unread mutations could not see seventy-six of them`). |
| 5 | `--cov-fail-under=75` passes locally and in CI with coverage measured over `src/taskmanager` only, tests excluded from the denominator | ✓ VERIFIED (CI leg is config-only, not run — same classification as prior verification) | `make test` re-run live: 1101 passed, 100.00% over 1659 statements, "Required test coverage of 75% reached". `.github/workflows/ci.yml` inspected this session: its final step (`pytest`) is unchanged from the prior verification's read — a bare invocation that inherits `pytest.ini`'s `--cov-fail-under=75` addopts. Nothing pushed this session, so the CI leg itself cannot be observed running; this is not reclassified as a new human-verification item because the workflow file is not wrong, only unobserved — the same judgment the prior report made. |

**Score:** 5/5 truths verified

### Gap Closure Evidence (SC-3 / WR-02)

The prior verification's gap was structural (a gate blind spot plus a thin assertion), not cosmetic, so it was verified by reading the gate's own detection logic against the fix and by falsifying it directly in this session — not by trusting 06-05-SUMMARY.md's narrative.

**Falsification 1 — the matrix's per-row confirmation totality guard.** Removed row 9's `confirmation=Confirmation(ONE_LIST, _the_list_carries_its_new_name)` from `MATRIX` and ran `test_every_mutating_row_confirms_its_change_or_says_it_changes_nothing` (no database needed, `pytest.mark.unit`):

```
FAILED tests/integration/api/test_permission_matrix.py::test_every_mutating_row_confirms_its_change_or_says_it_changes_nothing
assert confirmed == ROWS_THAT_CONFIRM   # Extra items in the right set: 9
```

Reverted with `git checkout -- tests/integration/api/test_permission_matrix.py`; `git status --porcelain` confirmed clean immediately after.

**Falsification 2 — the gate's re-read detection against the real tree.** Neutralised the re-read block in `test_the_permission_matrix_answers_what_the_table_promises` (replaced the `confirmation = cell.row.confirmation; if ...; read_back = await client.get(...); confirmation.shows(read_back)` tail with a bare `return`) and ran the real assertion-quality gate — not a planted snippet — against the mutated tree:

```
FAILED tests/architecture/test_assertion_quality.py::test_no_mutating_test_leaves_its_change_unread
Offending tests: ['tests/integration/api/test_permission_matrix.py:704']
```

This is the exact reproduction 06-05-SUMMARY.md claims for its own falsification of Task 2. Reverted with `git checkout -- tests/integration/api/test_permission_matrix.py`; `git status --porcelain` confirmed clean.

**Non-literal-verb closure, read directly from source (not re-derived from the SUMMARY).** `_verb_of` (`tests/architecture/test_assertion_quality.py:369-397`) resolves `client.request(...)`'s verb from a string-literal first positional argument or `method=` keyword; anything else — a name, an attribute access such as the real matrix's `cell.row.method`, an unrecognised spelling — falls through to `UNRESOLVED_VERB`, and `_mutates()` (`:398-404`) treats `UNRESOLVED_VERB` as mutating. This is the asymmetry the docstring calls out by name ("a wrongly-mutating classification costs a re-read that was already the standard, and a wrongly-reading one is a hole (WR-02)") and it is exercised by four planted self-tests that ship in the gate itself and were run live in this session (`pytest tests/architecture/test_assertion_quality.py --no-cov` → 32 passed):

- `test_a_literal_mutating_verb_through_request_is_an_offender` — `client.request('DELETE', ...)` with no read is an offender.
- `test_a_literal_get_through_request_is_not_an_offender` — `client.request('GET', ...)` is a read, and a re-read spelled generically (`client.request('GET', ...)` after a mutation) satisfies the rule — proving the resolution is not merely "treat request as mutating".
- `test_a_non_literal_verb_is_treated_as_mutating` — the literal reduction of the permission matrix's own shape (`client.request(cell.row.method, ...)`): unread is an offender, followed by `client.get(...)` is not.
- `test_a_verb_the_gate_cannot_read_is_never_a_way_out` — an unrecognised literal (`'TRACE'`) and a verb bound to a local name (`verb = 'GET'; client.request(verb, ...)`) are **both** still classified as offenders, confirming a non-literal or unrecognised verb can never read its way out of the gate. The `verb = 'GET'` case is the one that would most tempt a bypass (a real GET, spelled so the gate cannot see it), and it is asserted as still-mutating.

A non-literal verb is therefore never a way out of the gate, checked against the gate's own planted self-tests rather than assumed from the docstring's claim.

**Self-test snippets do not satisfy the gate for the wrong reason.** Each of the four planted tests above asserts a specific `file:line` offender list (`== ["tests/integration/api/planted.py:1"]` or `== []`), not merely "no exception raised" — a vacuous pass (e.g. an empty offenders list from a scan that silently matched nothing) would fail the equality against a non-empty expected list in three of the four cases. `test_the_scan_finds_the_http_tests_it_governs` (`len(found) > 100`) and `test_the_http_suite_is_actually_scanned` additionally guard against the whole module set going vacuous.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `tests/integration/api/test_permission_matrix.py` | `ROWS_THAT_CONFIRM`, `Confirmation`, per-row re-read, totality guard | ✓ VERIFIED | Present and wired: 10 `Confirmation` instances at rows 2, 6, 9, 10, 11, 14, 15, 16, 17, 18; `ROWS_THAT_CONFIRM = {2,6,9,10,11,14,15,16,17,18}`; `ROWS_THAT_MUTATE_NOTHING = {3}`; `test_every_mutating_row_confirms_its_change_or_says_it_changes_nothing` asserts both sets bidirectionally plus that every confirmation path is published and every confirmed row has at least one 2xx cell. |
| `tests/architecture/test_assertion_quality.py` | `UNRESOLVED_VERB`, `_verb_of`, `_mutates` widened detection, planted self-tests | ✓ VERIFIED | `UNRESOLVED_VERB = "request"`; `_verb_of` resolves literal verbs from `client.request(...)`'s first arg or `method=`; `_mutates` treats `MUTATING_VERBS | {UNRESOLVED_VERB}` as mutating. Four new planted self-tests present and passing (`test_a_literal_mutating_verb_through_request_is_an_offender`, `test_a_literal_get_through_request_is_not_an_offender`, `test_a_non_literal_verb_is_treated_as_mutating`, `test_a_verb_the_gate_cannot_read_is_never_a_way_out`). |
| `DECISION_LOG.md` | ADR-096 | ✓ VERIFIED | `## ADR-096: a verb the assertion gate cannot read is a mutation, and the permission matrix confirms its own writes (2026-09-19, amending ADR-088)` present, one occurrence. |
| `AI_WORKFLOW.md` | Dated incident entry for the gap closure | ✓ VERIFIED | `### 2026-09-19 — The gate built to catch unread mutations could not see seventy-six of them` present, in addition to the original break-check incident entry from the initial verification. |

All artifacts verified in the prior report (use-case totality, error-contract totality, endpoint totality, coverage-configuration gate, `break-check.sh`, etc.) were untouched by 06-05's `files_modified` list and are regression-checked via the live `make test` / `make arch` / `make break-check` runs above rather than re-read line by line.

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `tests/architecture/test_assertion_quality.py` | `tests/integration/api/test_permission_matrix.py` | widened verb resolution (`UNRESOLVED_VERB`) | ✓ WIRED | Falsification 2 above proves this live: removing the matrix's re-read reddens the real gate scanning the real tree, not a planted stand-in. |
| `tests/integration/api/test_permission_matrix.py` | the API under test | `confirmation.shows(read_back)` per mutating row | ✓ WIRED | Falsification 1 above proves this live: a row with no confirmation reddens the module's own totality guard; the per-row confirmation functions (`_the_list_carries_its_new_name`, `_the_list_is_gone`, etc.) each assert against a real re-read response. |

### Data-Flow Trace (Level 4)

Not applicable in the UI-rendering sense. The equivalent check for this phase — do the ten confirmations read real end state rather than a static/vacuous value — was performed by falsification: each confirmation function is a named assertion (`assert response.json()["name"] == RENAMED_LIST_NAME`, etc.) against a response fetched by `client.get(url(confirmation.path), ...)` issued after the mutation, and Falsification 1 demonstrated that dropping the wiring is caught rather than silently accepted.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Coverage gate enforces 75% over `src/taskmanager` only | `make test` | 1101 passed, 100.00% over 1659 statements, gate reached | ✓ PASS |
| Architecture contracts still hold | `make arch` | 4 kept, 0 broken | ✓ PASS |
| Assertion-quality gate is green with the widened detection | `pytest tests/architecture/test_assertion_quality.py --no-cov` | 32 passed, 0 offenders | ✓ PASS |
| Removing a row's confirmation reddens the matrix's own totality guard | falsification 1 (this session) | 1 failed, exact `9` named as the extra item | ✓ PASS (gap genuinely closed) |
| Removing the matrix's re-read reddens the real assertion-quality gate | falsification 2 (this session) | 1 failed, `test_permission_matrix.py:704` named as the offender | ✓ PASS (gap genuinely closed) |
| Deliberate-break spot check still reproduces after the gap closure | `make break-check` | All 5 breaks RED (7, 5, 30, 5, 2 failures — identical to the prior verification), exit 0, tree clean | ✓ PASS |

### Probe Execution

No `scripts/*/tests/probe-*.sh` convention in this project. `make break-check` is this phase's equivalent mutation-testing probe and was executed live above; counts (7, 5, 30, 5, 2) match the prior verification's live run exactly, confirming 06-05 introduced no regression.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| TEST-01 | 06-01 | Unit tests cover domain rules and every use case via fakes, no DB/HTTP | ✓ SATISFIED | Unchanged since prior verification; regression-checked via `make test-unit`/`make test` this session. |
| TEST-02 | 06-01 | Integration tests exercise every endpoint through HTTP against real Postgres, per-test isolated | ✓ SATISFIED | Unchanged since prior verification; regression-checked via `make test` this session (323+ integration tests still run against real Postgres). |
| TEST-03 | 06-04 | Coverage >= 75%, enforced by `--cov-fail-under=75` locally and in CI | ✓ SATISFIED (CI leg config-only) | `make test` 100.00% over 1659 statements this session; CI workflow file inspected, unchanged, still a bare `pytest` step. |
| TEST-04 | 06-01, 06-04 | Negative-path tests for error contract, 404/403 matrix, invalid transitions, auth failures | ✓ SATISFIED | Regression-checked live via `make break-check` (breaks 2, 3, 4 all red at the same counts as before). |
| TEST-05 | 06-02, 06-03, 06-05 | Every test contains meaningful assertions; deliberate-break spot check performed and recorded | ✓ SATISFIED (gap closed) | `test_permission_matrix.py`'s 2xx mutating cells now assert a document (`assert_the_success_document_says_what_was_asked_for`) and re-read the resource (`Confirmation`/`ROWS_THAT_CONFIRM`); the assertion-quality gate's `client.request(...)` blind spot is closed (`UNRESOLVED_VERB`/`_verb_of`/`_mutates`), independently falsified twice in this session. |

REQUIREMENTS.md maps exactly TEST-01..05 to Phase 6 (lines 88-92, 206-210), all five declared across the phase's plans' frontmatter (06-01 through 06-05), all five checked `[x]`. No orphaned requirement IDs.

### Anti-Patterns Found

No `TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/`PLACEHOLDER` markers in the two files 06-05 modified (`test_permission_matrix.py`, `test_assertion_quality.py`), checked directly this session.

### Open Warnings from 06-REVIEW.md — Judged, Not Re-litigated

Per the verification brief, WR-03, WR-05, WR-06, WR-07, WR-08, WR-10 and WR-11 are known, recorded follow-ups (each is named individually in 06-REVIEW.md's "Not fixed, still open" line and WR-03 is additionally named in ADR-096's "Still open, by design" consequences). None of them was touched by 06-05, and none makes a roadmap success criterion false **today**:

- **WR-03** (a re-read whose result is discarded still satisfies half (b)) — a latent gate weakness, not exploited by any test in the current suite; the ten confirmations added by 06-05 all assert directly on the re-read response (`confirmation.shows(read_back)` calls a function whose body is an `assert`), so WR-03's blind spot is not what makes SC-3 true here.
- **WR-05** (marker guard enforces "at least one" not "exactly one") — latent; today's suite has no dual-marked test.
- **WR-06** (endpoint-totality gate skips rather than fails on invocation drift) — latent; `Makefile`, `Dockerfile` and `ci.yml` all still invoke bare `pytest`, confirmed by direct inspection this session.
- **WR-07** (error-contract gate resolves `raise` by spelled name only) — latent; all 9 required codes appear inside real `assert` statements today (unchanged by 06-05).
- **WR-08** (use-case totality gate's attribute-call blind spot) — latent; no offending shape exists in the current suite (unchanged by 06-05).
- **WR-10** (the transition complement's oracle is derived from the code under test) — a real robustness gap, but the independent unit-level pin (`test_transition_table_matches_the_documented_matrix`) and the retained hard-coded HTTP test both still catch break 2, confirmed live this session (break 2: 5 failed, unchanged count).
- **WR-11** (two assertions on `\x00` that can never fail) — cosmetic; the load-bearing assertion beside each (`after == before`) is what actually proves the negative in those tests, and neither test is part of the permission-matrix module this phase's gap closure touched.

These are recorded here as non-blocking notes per the verification brief's instruction, not as gaps.

### Human Verification Required

None. The one item that cannot be observed running from this session — the CI leg of TEST-03/SC-5 — was inspected as configuration (the workflow file's final step is unchanged, still a bare `pytest` inheriting `pytest.ini`'s coverage gate) and is not reclassified as a human-verification item, consistent with the prior verification's treatment of the same fact.

### Gaps Summary

None remaining. The single gap the prior verification (4/5) found — the `client.request(...)` blind spot in the assertion-quality gate, and the permission matrix's thin 2xx success assertions — was independently falsified twice in this session (not merely re-read from 06-05-SUMMARY.md's narrative): removing a row's confirmation reddens the matrix's own totality guard, and removing the matrix's re-read block reddens the real assertion-quality gate scanning the real tree. Both edits were reverted exactly and `git status --porcelain` confirmed clean after each. The gate's non-literal-verb handling was checked against its own planted self-tests, which prove an unrecognised or name-bound verb can never read its way out of the rule. All four previously-passing success criteria (SC-1, SC-2, SC-4, SC-5) were regression-checked with fresh, live runs of `make test`, `make arch` and `make break-check`, producing counts identical to the prior verification's (7, 5, 30, 5, 2 failures across the five deliberate breaks; 100.00% coverage over 1659 statements; 4 architecture contracts kept). Requirements TEST-01 through TEST-05 are all satisfied and none is orphaned. The seven open code-review warnings named in the verification brief were checked individually and confirmed to be latent gate-robustness gaps rather than present false-greens, and are recorded as non-blocking notes.

---

_Verified: 2026-09-19_
_Verifier: Claude (gsd-verifier)_
