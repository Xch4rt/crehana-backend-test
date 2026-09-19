---
phase: 04-task-lists-tasks
plan: 12
subsystem: documentation
tags: [adr, decision-log, ai-workflow, claude-md, requirements, traceability, phase-gate, coverage, arc-05, list-01, task-01]

# Dependency graph
requires:
  - phase: 04-task-lists-tasks
    provides: "all eleven Phase 4 plan summaries — the decisions and incidents this plan is the last chance to record"
  - phase: 04-task-lists-tasks
    provides: "04-09 and 04-10's 79 HTTP tests, which are what makes the fifteen requirement ticks re-verifiable rather than inherited"
  - phase: 04-task-lists-tasks
    provides: "04-11's evidence/04-11-cold-start.txt — the compose leg of the phase gate, named by path rather than re-run here"
  - phase: 03-persistence-runnable-stack
    provides: "plan 03-11's close: the ADR shape, the scratch-path gate capture, and the last-claimant tick convention"
provides:
  - "DECISION_LOG.md ADR-044..ADR-057 — every Phase 4 decision that outlives the phase, with its rejected alternatives"
  - "AI_WORKFLOW.md: the Phase 4 human-decided/AI-delegated split and eleven dated incident entries"
  - "CLAUDE.md Project Rules: the two gates this phase landed, transcribed from the gates themselves"
  - ".planning/REQUIREMENTS.md: ARC-05, LIST-01..06 and TASK-01..08 ticked, plus a re-verification table naming the command and the test behind each"
  - "evidence/04-12-phase-gate.txt — lint, typecheck, arch, test and docker-test green in one uninterrupted run from a clean tree"
affects: [05, 06, 07]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A requirement tick is earned by running a named command and pasting its output into the phase-gate capture, never inherited from a plan's frontmatter"
    - "A success criterion whose wording credits a gate that does not exist is amended in place and the amendment is recorded beside it, rather than reinterpreted"
    - "Two runs of the same suite that disagree are investigated until the disagreement is explained; the explanation is checked by a labelled one-test probe, not asserted"
    - "An addendum run after an uninterrupted capture is labelled as such, so the capture's own claim stays true"

key-files:
  created:
    - .planning/phases/04-task-lists-tasks/evidence/04-12-phase-gate.txt
    - .planning/phases/04-task-lists-tasks/04-12-SUMMARY.md
  modified:
    - DECISION_LOG.md
    - AI_WORKFLOW.md
    - CLAUDE.md
    - .planning/REQUIREMENTS.md
    - .planning/ROADMAP.md
    - .planning/STATE.md

key-decisions:
  - "DECISION_LOG.md gains FOURTEEN ADRs (044-057), not the plan's enumerated nine. The plan lists nine decisions; the eleven summaries handed forward five more that a reader would otherwise have to reverse-engineer from the code — the shared access.py guard, the HTTP harness design, the app.openapi() route-assertion form, the grouped LIST-03 statement with the three-statement D-17 finding, and the CreateTask list-shaped refusal. Writing only nine would have satisfied the acceptance criterion while pushing the debt into Phase 7, which is the call plan 03-11 refused and the precedent followed here"
  - "The log stayed append-only mechanically rather than by intention: `git diff DECISION_LOG.md | grep -c '^-'` prints 1, the diff header alone, and every entry that refines an earlier one names it by id (ADR-046 refines ADR-020, ADR-049 refines ADR-009, ADR-045 names ADR-037, ADR-051 names ADR-015)"
  - "Roadmap Phase 4 SC-5 was AMENDED, not reinterpreted. Its wording required that 'no router imports SQLAlchemy or raises HTTPException for a business failure'. The SQLAlchemy half is true of both routers by inspection — neither names it — but nothing gates it, and `presentation` as a whole deliberately DOES import SQLAlchemy in health.py and dependencies.py, so the criterion credited a gate that does not exist. The replacement names only what a failing command can prove, and is strictly stronger about HTTPException: the shipped AST gate refuses the import as well as the raise. The Phase 2 SC-1 and Phase 3 SC-4 precedent"
  - "All fifteen ticks taken, each against a command that was run and exited 0 with at least one test collected, and each naming a test in a new re-verification table in REQUIREMENTS.md. Eleven consecutive Phase 4 plans deferred these to the last claimant; this is where the convention pays out. `pytest` exits 5, not 0, on a selector that matches nothing, so a mis-specified command would have blocked its tick rather than passing vacuously"
  - "The two gate runs disagree on coverage — host 100.00% over 1155 statements, container 99.20% over 1267 — and the difference was explained rather than reported. The statement count is PEP 649 (Python 3.14 defers annotations; visible in the Phase 3 capture too at 730 vs 772). The eleven missed lines are the trailing statements of the 04-08 route handlers, and a one-test probe in the container shows `test_create_returns_201_with_a_location_header_and_the_full_representation` PASSING while coverage reports as missed the only lines that set the header it asserts. Measurement artifact, not dead code; nothing was suppressed, and it is handed to Phase 6 with TEST-03"
  - "The phase itself is NOT marked complete here. Plan-level progress and the fifteen requirement ticks are this plan's; the phase checkbox, the Progress-table status and the completion date belong to the orchestrator after verification"

patterns-established:
  - "An ADR that supersedes or refines an earlier one names it by id in its title or its first line, so a reader arriving at the old entry is not misled by a log that was never edited"
  - "The gate capture is written to a scratch path and copied in afterwards, so the transcript's own clean-tree check is genuinely blank — carried over from 03-11 and now twice-used"
  - "A null result is reported as a finding: 79 HTTP tests found zero defects under src/, and the log records why that is plausible (the same behaviours were specified against fakes first) and what would have exposed the alternative"

requirements-completed: [ARC-05, LIST-01, LIST-02, LIST-03, LIST-04, LIST-05, LIST-06, TASK-01, TASK-02, TASK-03, TASK-04, TASK-05, TASK-06, TASK-07, TASK-08]

# Metrics
duration: 18min
completed: 2026-09-19
---

# Phase 4 Plan 12: the Phase 4 close — ADRs, incidents and the gate Summary

**Phase 4's decisions are now written down where a reader in six months will find them — fourteen ADRs with their rejected alternatives, from the actor seam that says in its own docstring that it is not authentication, to the D-15 gate pair and the three-statement finding that corrected a plan — alongside eleven dated incident entries, two new CLAUDE.md rules transcribed from the gates that enforce them, fifteen requirement ticks each earned by a command that was run and a test that was named, and one uninterrupted capture of `make lint`, `make typecheck`, `make arch` (4 kept, 0 broken), `make test` (599 passed, 100.00%) and `make docker-test` (599 passed, 99.20%) from a clean tree.**

## Performance

- **Duration:** 18 minutes
- **Tasks:** 3
- **Files changed:** 7 (2 created, 5 modified)
- **Commits:** 3

## What Was Built

### Task 1 — the Phase 4 ADRs (`eae184b`)

`DECISION_LOG.md` gains **ADR-044 through ADR-057**, 637 lines appended and none removed:

| ADR | Decision |
|-----|----------|
| 044 | `get_current_actor` is a seam, and it is not authentication (D-01, D-03) |
| 045 | The demo user is seeded by the container entrypoint, not by a migration (D-02, names ADR-037) |
| 046 | "Field not provided" is a single-member enum in the application layer (D-05, refines ADR-020) |
| 047 | `updated_at` moves whenever a field is provided — and therefore not at all when none is (research A1) |
| 048 | One door into the state machine: a dedicated status endpoint (D-08, D-11) |
| 049 | The two response envelopes (D-09, D-10, refines ADR-009) |
| 050 | `ChangeTaskStatusCommand` gained `task_list_id`, so every task route honours its parent (D-14) |
| 051 | D-15 is two gates, and the import check is the load-bearing half (names ADR-015) |
| 052 | The OpenAPI polish level, and the two corrections it forced (research Open Question 3) |
| 053 | Where the research and the phase context disagreed, the context won |
| 054 | The whole-list statistics come from one grouped statement, and "no N+1" is measured (D-17) |
| 055 | The ADR-008 visibility rule lives in one module, `access.py` |
| 056 | The HTTP harness overrides the unit of work and never enters the lifespan (D-16) |
| 057 | Route assertions read `app.openapi()["paths"]`, never `app.routes` |

Every entry carries the file's four headings — context, options, decision, consequences — and every
rejected option is the one that was really on the table, including the two that this project
executed and measured before rejecting (the sentinel in the Pydantic schema, and the targeted
`ON CONFLICT` clause).

### Task 2 — the incident log, the CLAUDE.md rules and the fifteen ticks (`f4b9e0f`)

**`AI_WORKFLOW.md`** gains a Phase 4 human-decided / AI-delegated block and **ten** dated incident
entries (an eleventh followed in Task 3):

1. A Phase 2 DTO could not express the URL Phase 4 had already chosen — caught by research, cost one field and an inverted test.
2. The sentinel design was chosen by executing the alternative, not by arguing about it — the `_Unset` OpenAPI component and the two-entry error `loc`.
3. Both new gates were planted red, and the first planting proved the wrong thing — `2 kept, 2 broken` where the demonstration needed `3 kept, 1 broken`.
4. The research's PATCH mapper, and the plan that repeated it, do not type-check.
5. A plan predicted two SQL statements; the code issues three, and the plan was wrong.
6. A test double disagreed with the adapter it stands for — `2 failed, 7 passed` on the falsification.
7. A plan reused a route-walking idiom this repository had already found broken in 03-09.
8. The idempotence proof as planned would have passed against the form that breaks the container.
9. Nine mechanical counters were unreachable, and none of them was gamed.
10. What Phase 4's 79 HTTP tests found under `src/`: nothing — reported as a finding, with the reason it is plausible.

Each points at a commit, an evidence file or a named test; every quoted number is verbatim from the
capture it came from.

**`CLAUDE.md` "Project Rules"** gains the two gates, transcribed from the gate files rather than
from a plan, and outside every GSD delimiter block (`git diff CLAUDE.md | grep -c "GSD:"` prints
`0`):

- No module under `src/taskmanager/presentation/api/routers/` raises **or imports**
  `HTTPException` — `tests/architecture/test_routers_raise_no_http_exception.py`, its two passes,
  its `file:line` reporting and its non-vacuity guard.
- No module under `domain`, `application` or `infrastructure` imports `fastapi` or `starlette` —
  the `no-http-below-presentation` contract and `EXPECTED_CONTRACT_NAMES`.
- Plus the note the section makes elsewhere: neither adds a pre-commit hook or a CI step, because
  both ride inside commands those already run.

**`.planning/REQUIREMENTS.md`**: all fifteen boxes ticked, all fifteen Traceability rows moved to
`Complete`, and a new **Phase 4 re-verification** table giving each ID its command, its collected
count and a named test. 44 of 69 v1 requirements are now complete.

**`.planning/ROADMAP.md`**: `04-12-PLAN.md` ticked, and SC-5 amended (see the deviation below).

### Task 3 — the full gate in one uninterrupted run (`7bcbcde`)

`.planning/phases/04-task-lists-tasks/evidence/04-12-phase-gate.txt`, 1026 lines, **attempt 1** —
nothing was fixed and re-run:

| Step | Result |
|------|--------|
| 1. clean tree | no output |
| 2. `make format` | `139 files left unchanged`, tree still clean |
| 3. `make lint` | exit 0 |
| 4. `make typecheck` | `Success: no issues found in 139 source files` |
| 5. `make arch` | `Contracts: 4 kept, 0 broken.` |
| 6. `make test` (db up) | `599 passed`, `Required test coverage of 75% reached. Total coverage: 100.00%` |
| 7. `make docker-test` | `599 passed`, `Required test coverage of 75% reached. Total coverage: 99.20%` |
| 8. fifteen re-verification commands | all exit 0, all collect ≥ 1 test |
| 9. exemption checks | no `pragma: no cover` under `src/taskmanager/`; `grep -c omit pytest.ini` prints `0` |

The compose leg is named by path rather than repeated:
`.planning/phases/04-task-lists-tasks/evidence/04-11-cold-start.txt`.

## Deviations from Plan

### 1. [Judgement recorded] Fourteen ADRs, not the plan's nine

- **Found during:** Task 1, reading the eleven summaries.
- **Issue:** the plan enumerates nine decisions "at minimum" and says to prefer writing one too
  many. Five more were handed forward by summaries: `access.py` and the dropped assignee clause
  (04-03), `CreateTask`'s list-shaped refusal (04-06), the `app.routes` opacity (04-08), the HTTP
  harness design (04-09), and the grouped LIST-03 statement with the three-statement D-17 finding
  (04-02, 04-10).
- **Resolution:** all fourteen written. The 03-11 precedent — twenty-one where the plan enumerated
  twelve — is the call this follows.
- **Commit:** `eae184b`

### 2. [Rule 1 — a criterion that credits a gate that does not exist] Roadmap SC-5 amended

- **Found during:** Task 2, re-reading the five success criteria against what shipped.
- **Issue:** SC-5 required that "no router imports SQLAlchemy or raises `HTTPException` for a
  business failure". Both halves are *true*, but only one is *gated*: nothing in the repository
  forbids a router from importing SQLAlchemy, and `presentation` as a whole deliberately imports it
  in `health.py` (the readiness probe) and `dependencies.py` (the session factory). A criterion
  that reads as a guarantee and is only an observation is the Phase 2 SC-1 defect again.
- **Fix:** the wording now names the two gates that exist —
  `tests/architecture/test_routers_raise_no_http_exception.py` and the
  `no-http-below-presentation` contract — and is strictly stronger about `HTTPException`, since the
  shipped gate refuses the **import** as well as the raise. The amendment is recorded in a
  parenthesis beside the criterion with the original wording quoted, following Phase 2 SC-1 and
  Phase 3 SC-4.
- **Commit:** `f4b9e0f`

### 3. [Rule 2 — missing critical documentation] The two gate runs disagree on coverage, and the plan asked for the difference to be read

- **Found during:** Task 3, reading both coverage tables.
- **Issue:** host `1155` statements / `0` missed / `100.00%`; container `1267` / `11` / `99.20%`;
  `599 passed` in both. Eleven uncovered lines in the newest code reads like eleven untested lines.
- **Fix:** checked rather than assumed. The statement-count difference is PEP 649 and is visible in
  the Phase 3 capture too (730 vs 772). The eleven missed lines are the trailing statements of the
  04-08 route handlers, and a **labelled addendum** runs one test in the container:
  `test_create_returns_201_with_a_location_header_and_the_full_representation` passes while
  coverage reports as missed the only lines in the project that set the header it asserts and then
  follows. Measurement artifact, not dead code.
- **What was not done:** nothing was suppressed. A `# pragma: no cover` is forbidden by CLAUDE.md
  and would convert an artifact into a permanent exemption. The finding is handed to Phase 6, which
  owns TEST-03.
- **Files:** `evidence/04-12-phase-gate.txt` (the addendum), `AI_WORKFLOW.md` (the eleventh entry)
- **Commit:** `7bcbcde`

### 4. [Acceptance criterion unreachable as written] The ROADMAP `TBD` count could not drop

- **Issue:** the criterion requires `grep -c "TBD" .planning/ROADMAP.md` to be *lower* than at
  `HEAD`, on the premise that Phase 4 still carried a `**Plans:** TBD` placeholder. It does not —
  the placeholder was filled during phase planning, and Phase 4 has listed twelve plans and seven
  waves since. The six remaining matches all belong to Phases 5, 6 and 7, and lowering the count
  would mean inventing plan counts for phases that have not been planned.
- **Resolution:** met in substance and recorded. The companion clause — *"the Phase 4 section
  contains no `TBD`"* — is satisfied literally: `sed -n '/### Phase 4/,/### Phase 5/p' | grep -c
  TBD` prints `0`. The tenth counter in this phase met in substance rather than manufactured, and
  the same call every plan since 04-03 has made.

### 5. [Instructed by the orchestrator, against the plan text] The phase is not marked complete here

- **Issue:** Task 2's text asks to "mark the phase complete with its date in both the phase heading
  and the Progress table". The execution brief for this plan instructs the opposite: plan-level
  progress and the requirement ticks are this plan's, while the phase checkbox, the Progress-table
  status and the completion date belong to the orchestrator after verification.
- **Resolution:** the orchestrator's instruction was followed. `04-12-PLAN.md` is ticked, the
  Progress row reads `12/12`, and the phase's own checkbox in the Phases list, its status and its
  date are untouched. Recorded so the omission reads as a decision rather than as a missed step.

### Authentication gates

None. This plan is documentation, verification and a gate run; no credential, token or external
login was involved.

## Verification

Every acceptance criterion in the plan, checked:

**Task 1**

- `git diff DECISION_LOG.md | grep -c '^-'` → `1` ✓ (the diff header alone; append-only)
- `grep -c "ADR-" DECISION_LOG.md` → `98`, against `61` at `HEAD` — `+37`, against a floor of `+9` ✓
- `grep -c "^## ADR-"` → `57`, was `43` — fourteen new entries ✓
- `grep -ci "not authentication"` → `2` ✓
- `grep -c "ADR-037"` → `2` ✓ · `grep -c "ADR-015"` → `4` ✓ · `grep -c "ON CONFLICT"` → `1` ✓
- Every new entry carries context / options / decision / consequences ✓ (read back)

**Task 2**

- `grep -c "^- \[ \] \*\*\(ARC-05\|LIST-0[1-6]\|TASK-0[1-8]\)\*\*" .planning/REQUIREMENTS.md` → `0` ✓
- `grep -c "| Phase 4 | Pending |" .planning/REQUIREMENTS.md` → `0` ✓
- `grep -c "04-12-PLAN.md" .planning/ROADMAP.md` → `1` ✓
- Phase 4 section of the roadmap contains no `TBD` ✓ (the whole-file count is deviation 4)
- `grep -c "test_routers_raise_no_http_exception" CLAUDE.md` → `1` ✓
- `grep -c "no-http-below-presentation" CLAUDE.md` → `1` ✓
- `git diff CLAUDE.md | grep -c "GSD:"` → `0` ✓
- `grep -ci "phase 4" AI_WORKFLOW.md` → `14`, entries dated ✓
- All fifteen re-verification commands run, all exit 0, output pasted into the gate capture ✓

**Task 3**

- `make lint`, `make typecheck`, `make arch`, `make test`, `make docker-test` — all exit 0 ✓
- `make arch` output contains `Contracts: 4 kept, 0 broken.` ✓
- `make test` output contains `Required test coverage of 75% reached` ✓
- The capture contains `make lint`, `make typecheck`, `make arch`, `make test`, `make docker-test`,
  `4 kept, 0 broken` and `Required test coverage of 75% reached` ✓
- The capture's clean-tree check is followed by no output ✓
- `grep -c "04-11-cold-start.txt"` in the capture → `1` ✓
- `grep -rn "pragma: no cover" src/taskmanager/` → nothing; `grep -c "omit" pytest.ini` → `0` ✓

## Known Stubs

None. This plan adds no code. The one open item it hands forward is the container/host coverage
discrepancy described in deviation 3, which is a measurement question rather than a stub: the lines
in question are executed and asserted, and the finding is recorded in `AI_WORKFLOW.md` and in
`.planning/STATE.md` for Phase 6.

## Threat Flags

None. No network endpoint, auth path, file access pattern or schema change was introduced — the
plan touches documentation, planning artifacts and one evidence file.

## Self-Check: PASSED
