---
phase: 06-test-hardening-coverage
plan: 05
subsystem: test-gates
tags: [gap-closure, assertion-quality, verb-resolution, permission-matrix, re-read, wr-02, adr-096]

# Dependency graph
requires:
  - phase: 06-test-hardening-coverage
    provides: "06-02 — the assertion-quality gate, both halves, and the planted-snippet pattern this plan extends"
  - phase: 06-test-hardening-coverage
    provides: "06-VERIFICATION.md — the one gap scored 4/5, and WR-02 from 06-REVIEW.md, which it confirmed live"
  - phase: 05-auth-assignment-notifications
    provides: "tests/integration/api/test_permission_matrix.py — the 76-cell table this plan makes assert its own writes"
provides:
  - "UNRESOLVED_VERB / _verb_of / _mutates — half (b) classifies a request by its verb, not by the attribute name, and an unreadable verb is a mutation"
  - "Four planted self-tests pinning the literal-mutating, literal-GET, non-literal and unrecognised-verb cases"
  - "Confirmation / Row.confirmation — ten named re-reads, one per mutating row of the matrix"
  - "assert_the_success_document_says_what_was_asked_for — a 2xx asserts a document, not an absent header"
  - "ROWS_THAT_CONFIRM / ROWS_THAT_MUTATE_NOTHING and the guard comparing them both ways"
  - "ADR-096, amending ADR-088"
affects: [07-documentation-delivery]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Classify by the resolved verb, not by the spelling: an argument-carried verb is read from the call, and an unreadable one fails safe toward the stricter rule"
    - "A gate whose rule is per test gets a per-row totality guard inside a table-driven test, because the gate cannot see rows"
    - "A success assertion is about a document, never about an absent header — absence is satisfied by a handler that did nothing"

key-files:
  created: []
  modified:
    - tests/integration/api/test_permission_matrix.py
    - tests/architecture/test_assertion_quality.py
    - DECISION_LOG.md
    - CLAUDE.md
    - AI_WORKFLOW.md
    - .planning/ROADMAP.md
    - .planning/STATE.md

key-decisions:
  - "Both halves closed by assertions, not by an exemption. The `no_reread` marker was available for the re-read half and was not taken: the body-assertion half has no exemption mechanism at all by design (D-07), so half the gap was never exemptible, and a re-read keyed on the row cost one field plus one block against three lines for an exemption that would have left the destructive rows proving only that nothing complained"
  - "An unreadable verb is a mutation, not nothing. The asymmetry is the whole rule: a wrongly-mutating classification costs a re-read that was already the standard, a wrongly-reading one is a hole — and the hole is exactly what WR-02 was"
  - "The four written values (`A matrix list`, `Renamed by the matrix`, `A matrix task`, `Retitled by the matrix`) are named module constants read by both the row that sends one and the confirmation that looks for it, rather than read back out of `MATRIX` at run time as the plan suggested: the same no-drift guarantee without a subscript into the table"
  - "A refused cell reads nothing back. The rejected-mutation leg of D-06 stays the per-route modules', where the before/after pair already lives; stated as a limit in the test's own docstring and in ADR-096 rather than smoothed over"
  - "WR-03 deliberately still open and named in ADR-096: a re-read whose result is discarded still satisfies half (b). Closing it is a gate redesign (bind the call's target, accept the inline form only inside an `assert`, re-audit the 29 re-reads the 06-02 sweep added), and no test in today's suite uses the shape"

patterns-established:
  - "A gate's blind spot is defined by the shapes it was tested against: all twenty of 06-02's planted snippets used an attribute-named verb, and the one generic caller three directories away was never planted"

requirements-completed: []

# Metrics
duration: 25min
completed: 2026-09-19
---

# Phase 6 Plan 05: Closing the `client.request` Blind Spot Summary

**The gate that exists to make "every mutating test re-reads" a build failure could not see the
seventy-six mutations of the permission matrix, and the matrix's own successful cells asserted
only that a header was absent — both are now assertions, and removing either turns the build red.**

## Performance

- **Duration:** ~25 min
- **Tasks:** 3 of 3
- **Files modified:** 7 (0 created, 7 modified) plus this SUMMARY
- **Suite:** 1096 → **1101 passed**, coverage **100.00 %** over 1659 statements (gate 75 %)

## Task Commits

| Task | Name                                                   | Commit    | Files                                                     |
| ---- | ------------------------------------------------------ | --------- | --------------------------------------------------------- |
| 1    | The matrix asserts its success documents and re-reads   | `3cde999` | `test_permission_matrix.py`                                |
| 2    | The gate reads the verb it is given                     | `9701c13` | `test_assertion_quality.py`                                |
| 3    | ADR-096, the CLAUDE.md bullet, the incident, the records | (this)   | `DECISION_LOG.md`, `CLAUDE.md`, `AI_WORKFLOW.md`, `ROADMAP.md`, `STATE.md`, this file |

## What the gap actually was

Two halves, both real, and neither hypothetical.

**The gate was blind.** `MUTATING_VERBS` was matched against the *attribute name*, so
`client.request(cell.row.method, ...)` — the only way the matrix issues a request — was recorded as
the verb `"request"`: in `REQUEST_VERBS`, so the test counted as an in-scope HTTP test, and in
nothing half (b) looked at. The test carried no exemption marker and was not in
`REQUIRED_NO_REREAD`. It was outside the rule's field of view, and the gate reported zero
offenders.

**The test was thin where it succeeded.** For the ten mutating rows the 2xx branch of
`assert_the_body_the_status_promises` called only `assert_no_challenge_was_issued`, which asserts a
`WWW-Authenticate` header and a `problem+json` content type are **absent**. A `DELETE` that
answered 204 and deleted nothing satisfied it exactly as well as one that worked. The refusal cells
(401/403/404) were already fully body-asserted; only success was thin.

## The choice: assertions, not an exemption

`no_reread` was available for the re-read half and was not taken.

- Half (a) — the body assertion — has **no exemption mechanism at all**, by design (D-07, ADR-088),
  and roadmap SC-3's wording has no opt-out. So half the gap could not have been exempted however
  the argument went.
- The matrix is parametrized over a table, so a re-read keyed on the row is one field on `Row` plus
  one block in the test. An exemption would have bought three lines and left the destructive rows —
  `DELETE` a list, `DELETE` a task, unassign — proving only that nothing complained.

The module docstring's claim that per-route persistence is proved next door stays true and is not
the point: the gate's rule is per test, and this test mutates.

## The red that earned each green

Four temporary edits, each observed red and reverted immediately; no transcript file (D-15), the
edit is named instead.

**Task 1 — the matrix.** Three.

1. Row 9's `body` value changed to the literal `"Renamed"` while the confirmation kept looking for
   `RENAMED_LIST_NAME` → exactly `[09-owner-PATCH-/api/v1/task-lists/{list_id}]` red. The echo
   assertion stayed green (the request did get back what it sent), which is precisely why the
   re-read is a second, independent claim.
2. `confirmation=` deleted from row 10 → the guard test red, reporting `10` as an extra item in
   `ROWS_THAT_CONFIRM`.
3. `_the_list_is_gone` changed to assert a 200 → `[10-owner-DELETE-...]` red.

**Task 2 — the gate, against the real tree.** With the matrix's re-read block removed:

```
FAILED tests/architecture/test_assertion_quality.py::test_no_mutating_test_leaves_its_change_unread
Offending tests: ['tests/integration/api/test_permission_matrix.py:704']
```

That is the gap, reproduced by the fixed gate on the same tree that was green before it. Restored
with `git checkout -- tests/integration/api/test_permission_matrix.py` (one exact committed path);
`git status --porcelain` then listed only the gate module.

## What is in place now

| Claim | Where it lives | What fails if it is removed |
| ----- | -------------- | --------------------------- |
| A `request(...)` mutation is inside half (b), literal verb or not | `_verb_of`, `_mutates` | `test_no_mutating_test_leaves_its_change_unread` on the matrix |
| `request("GET", ...)` is still a read | `_verb_of` | `test_a_literal_get_through_request_is_not_an_offender` |
| An unreadable verb is a mutation | `_mutates` | `test_a_non_literal_verb_is_treated_as_mutating`, `test_a_verb_the_gate_cannot_read_is_never_a_way_out` |
| A 204 carries no body; a sent field comes back; a credential does not | `assert_the_success_document_says_what_was_asked_for` | the cell whose row sends that field |
| Ten mutating rows re-read their change | `Confirmation`, `Row.confirmation` | the owner (or assignee) cell of that row |
| A mutating row added without a re-read | `ROWS_THAT_CONFIRM`, `ROWS_THAT_MUTATE_NOTHING` | `test_every_mutating_row_confirms_its_change_or_says_it_changes_nothing` |

The reader of a confirmation is the caller that mutated — a stranger's own list is read with the
stranger's token — with the owner standing in for row 2 alone, whose caller may be anonymous while
`GET /api/v1/users` needs a credential.

## Deviations from Plan

**1. [Rule 1 — the plan's no-drift mechanism, done a better way] shared constants, not a subscript into `MATRIX`**
- **Found during:** Task 1
- **Issue:** the plan asks for the four written values to be read out of the rows' own `body`
  mappings "if that reads better", and says to prefer reading them from `MATRIX`. The ten
  confirmation functions must be defined *above* `MATRIX` (the table references them), so reading
  them back would mean `MATRIX[5].body["name"]` inside a function — a subscript into a table by
  index, which drifts the moment a row is inserted.
- **Fix:** `LIST_NAME`, `RENAMED_LIST_NAME`, `TASK_TITLE`, `RETITLED_TASK_TITLE` as module
  constants, read by both the row that sends one and the confirmation that looks for it. The same
  guarantee the plan wanted — the two cannot drift because there is only one — and falsification 1
  above proves it is load-bearing.
- **Commit:** `3cde999`

**2. [Rule 3 — a name black would have wrapped badly] guard test renamed by four words**
- **Found during:** Task 1
- **Issue:** the plan's `test_every_mutating_row_confirms_its_change_or_is_named_as_changing_nothing`
  is 89 characters with `def ` and `() -> None:`, one over `max-line-length = 88`, which black
  reformats into a `-> (\n    None\n):` signature.
- **Fix:** `test_every_mutating_row_confirms_its_change_or_says_it_changes_nothing`, same claim,
  85 characters.
- **Commit:** `3cde999`

**3. [Rule 2 — internal consistency the plan's diff list did not cover] three more STATE.md lines**
- **Found during:** Task 3
- **Issue:** the plan lists the two counters, the timestamps and the position prose. Leaving
  `- Total plans completed: 59` and the `| 06 | 4 |` velocity row would have put a stale 59 four
  lines below a frontmatter saying 60, in the one file whose regressions this project keeps
  logging.
- **Fix:** both updated, and a `| Phase 06 P05 |` metrics row added, matching what the four
  preceding plans of this phase did. `git diff .planning/STATE.md` is 26 insertions / 21 deletions,
  every one intended: no `percent` change, no blank-line churn.
- **Commit:** (this)

## Still open, by design

Named rather than left for the next reader to rediscover.

- **WR-03** — a re-read whose result is discarded still satisfies half (b); the gate sees the
  `client.get(...)` call, not whether its value reaches an `assert`. Recorded in ADR-096's
  consequences and in `06-REVIEW.md`; no test in today's suite uses the shape.
- **WR-04's other half** — `FORBIDDEN_PRAGMA` matches one spelling of `# pragma: no cover` while
  coverage honours several (ADR-095's own consequence).
- **WR-05, WR-06, WR-07, WR-08, WR-10, WR-11** and every **IN-\*** — checked latent by the
  verifier, untouched here.
- **The rejected-mutation leg of D-06 in the matrix** — a refused cell reads nothing back; the
  "unchanged" pair stays in `test_task_lists.py`, `test_tasks.py` and `test_assignment.py`.

## Verification Results

```
make lint       -> black 187 files unchanged, isort clean, flake8 clean
make typecheck  -> Success: no issues found in 187 source files
make arch       -> Contracts: 4 kept, 0 broken.
make test       -> 1101 passed, TOTAL 1659 stmts / 154 branches, 100.00%
make break-check-> all 5 breaks RED (7, 5, 30, 5, 2 failures), exit 0, src/ clean after
```

- `.venv/bin/pytest tests/integration/api/test_permission_matrix.py --no-cov` → **80 passed**
  (76 cells + the login refusal + the coverage test + the two non-parametrized guards).
- `.venv/bin/pytest tests/architecture/test_assertion_quality.py --no-cov` → **32 passed**
  (28 + the four new self-tests), zero offenders in both halves across the real suite.
- Break 3 still reports **30** failures, the same verdict `06-VERIFICATION.md` recorded — the
  permission-matrix changes did not move it.
- `git status --porcelain -- src/` empty throughout, including after `make break-check`. This plan
  needed no `src/` change: every one of the ten confirmations passed against the real API first
  time, so the gap was in what the suite proved, not in what the product did.

## Ceremony

Minimal, per D-15: one SUMMARY, no evidence file, no transcript, no RED artifact. `TEST-05` is
**not** re-ticked — it is already ticked in `REQUIREMENTS.md` from 06-04, and its "meaningful
assertions" half is what this plan makes true rather than newly claims. Phase 6's ROADMAP checkbox,
its progress-table status cell and its completion date are deliberately untouched: they belong to
the orchestrator after **re**-verification, which this plan does not perform.

## Self-Check: PASSED

- `tests/integration/api/test_permission_matrix.py` carries `ROWS_THAT_CONFIRM` — FOUND
- `tests/architecture/test_assertion_quality.py` carries `UNRESOLVED_VERB` — FOUND
- `DECISION_LOG.md` carries exactly one `^## ADR-096` — FOUND (append only: 77 insertions, 0 deletions)
- `CLAUDE.md`'s Assertion quality bullet carries `client.request` and `ROWS_THAT_MUTATE_NOTHING`,
  no `GSD:*` block touched — FOUND
- `AI_WORKFLOW.md` has one new dated entry — FOUND
- commits `3cde999`, `9701c13` — both FOUND in `git log`
