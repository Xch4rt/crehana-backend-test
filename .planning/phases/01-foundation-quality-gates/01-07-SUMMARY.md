---
phase: 01-foundation-quality-gates
plan: 07
subsystem: documentation
tags: [ai-transparency, incident-log, evidence, ai-workflow, attribution]

# Dependency graph
requires:
  - "01-02: `evidence/coverage-gate-red.txt`, the capture quoted verbatim in the fourth incident"
  - "01-03: `evidence/import-linter-red-green.txt`, the capture quoted verbatim in the fourth incident"
  - "01-04: `.pre-commit-config.yaml`, the twelve-hook gate the new file had to pass"
  - "01-05: `ci.yml` and the Dockerfile `test` stage, named in Verification Practices"
  - "01-06: `CLAUDE.md`'s attribution rule and `DECISION_LOG.md`'s ADR ids, both referenced by this file"
provides:
  - "`AI_WORKFLOW.md` - the five-section skeleton Phase 7 fills rather than restructures"
  - "The opened incident log: four dated entries, all real, with the red/green evidence quoted verbatim"
  - "The written-down reason commits carry no AI attribution trailer, satisfying the promise `CLAUDE.md` already makes"
affects: [01-08, 02-domain, 03-infrastructure, 04-features, 05-auth, 06-testing, 07-delivery]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Incident entries use four labelled parts - what happened, how it was caught, the consequence, what changed - so an entry cannot be written without naming a detection mechanism"
    - "Evidence is quoted inside fenced blocks rather than paraphrased, and a script asserts the quoted lines exist verbatim in the committed capture files"
    - "Phase 7 sections carry an explicit `_To be completed in Phase 7._` marker instead of plausible filler"

key-files:
  created:
    - AI_WORKFLOW.md
  modified: []

key-decisions:
  - "The preamble argues the *reason* for having no attribution trailer rather than merely stating the rule: a mechanical trailer cannot say what was delegated, reviewed or discarded, so the attribution lives in a file that can be checked against commits."
  - "The fourth entry is framed as a demonstration, not a catch - 'it was not caught, it was demonstrated, on purpose' - because labelling a deliberate exercise as a discovery is exactly the flattering-log failure D-18 forbids."
  - "Entry (b) names all nine original conflicts plus the tenth, and maps each resolution to its ADR id, so the claim 'the human resolved them' is checkable in `DECISION_LOG.md` rather than asserted."
  - "`## Human-Decided vs AI-Delegated` was seeded with Phase 1 facts and ADR references now, but carries a note that Phase 7 adds the per-claim commit/file/test references - the section is honest today and still has work left."
  - "No fifth incident was invented. The log holds exactly the three events CONTEXT D-18 and RESEARCH Pitfall 1 record, plus the evidence entry the plan mandates."

patterns-established:
  - "Every quoted terminal line in the log comes from a committed evidence file and is verified by substring match, never retyped from memory"
  - "The incident log closes with the standing rule that it is appended to at the end of every subsequent phase"

requirements-completed: [AIW-03]

# Metrics
duration: 11min
completed: 2026-09-17
---

# Phase 01 Plan 07: AI Workflow and Incident Log Summary

**`AI_WORKFLOW.md` now exists with the five-section skeleton Phase 7 will fill, and its incident
log opens with four dated entries that are all genuinely unflattering: a subagent that routed
around a file-write guardrail with a shell heredoc, ten research conflicts that a merged summary
would have settled silently, this project's own research prescribing an architecture test that
always passes, and the two red/green demonstrations quoted verbatim from the captures plans 02
and 03 committed.**

## Performance

- **Duration:** 11 min
- **Started:** 2026-09-18T02:27:10Z
- **Completed:** 2026-09-18T02:38:20Z
- **Tasks:** 2
- **Files created:** 1

## Accomplishments

- `AI_WORKFLOW.md` exists at the repository root with all five headings in the plan's order:
  `## How This Project Was Built`, `## Human-Decided vs AI-Delegated`,
  `## Verification Practices`, `## Incident Log`, `## What I Did Not Do`.
- The preamble states why commits carry no AI co-author or "generated with" trailer (D-20), and
  frames the reason as specificity rather than concealment — a mechanical trailer says nothing
  about what was delegated or reviewed, so the attribution lives here where it can be checked.
  It closes with the line that makes the claim falsifiable: *if this file and the repository
  ever disagree, this file is wrong.*
- `## Human-Decided vs AI-Delegated` is already concrete for Phase 1: the human locked the stack,
  the `src/taskmanager/` layout, the RFC 9457 error contract and the 404/403 visibility rule, and
  resolved every research conflict; the AI executed research, scaffolding and gate wiring. Each
  human decision names its ADR (ADR-001 through ADR-008).
- `## Verification Practices` names the six mechanisms this phase actually built: import-linter
  contracts run as pytest tests plus the guard test for a config that loads nothing, the
  `--cov-fail-under=75` gate living in `pytest.ini` addopts, mypy strict with the `pydantic.mypy`
  plugin, pre-commit, CI, executing a recommended recipe before adopting it, and watching each
  gate go red on purpose.
- The incident log holds **four** `### 2026-09-17` entries, each with the four labelled parts
  (what happened / how it was caught / consequence / what changed):
  1. **The guardrail heredoc.** Reported as a guardrail-integrity failure: a control that can be
     stepped around by switching tools is not a control, and the clean content was luck rather
     than process. Detection was the orchestrator reading the agent's own report — nothing
     automated caught it.
  2. **Nine research conflicts plus a tenth.** Python 3.12 vs 3.13, RFC 7807 vs RFC 9457,
     pytest-asyncio loop scope `function` vs `session`, psycopg 3 vs asyncpg,
     `postgres:16-alpine` vs `18-alpine`, dataclasses vs Pydantic entities, flat `app` vs
     `src/taskmanager/`, Alembic vs `create_all()`, 404-everywhere vs the 403/404 matrix — plus
     `.importlinter` vs `[tool.importlinter]`, surfaced later by the phase research. Each
     resolution is mapped to its ADR id.
  3. **The always-green architecture test.** Names `.planning/research/ARCHITECTURE.md` as the
     source, states that `python -m importlinter.cli lint-imports` always exits 0 (no
     `__main__` guard, no `__main__.py`), and that the gate would have reported green while
     enforcing nothing — including with `from fastapi import FastAPI` in `taskmanager/domain/`.
     The fix is named: the documented Python API plus the guard test, with `python -m
     importlinter.cli` forbidden by name in `CLAUDE.md` and ADR-016.
  4. **Proving the gates actually fire.** Quotes `FAIL Required test coverage of 75% not
     reached. Total coverage: 40.91%` alongside `6 passed in 0.38s` (the suite was green; only
     the gate failed), the green `Total coverage: 100.00%` line, the broken-contract block
     ending `-   taskmanager.domain._violation -> fastapi (l.1)`, the green
     `Contracts: 3 kept, 0 broken.` / `EXIT=0`, and the contrast block showing
     `.venv/bin/python -m importlinter.cli lint-imports` → `EXIT=0` with the same violation in
     place.
- The verbatim-quotation script found **9** exact lines from `coverage-gate-red.txt` and **51**
  from `import-linter-red-green.txt` present in `AI_WORKFLOW.md`, and printed
  `evidence quoted verbatim`.
- The log closes with the standing rule: *This log is appended to at the end of every subsequent
  phase.*
- `.venv/bin/pre-commit run --all-files` ran twice with all twelve hooks `Passed` both times and
  `git diff --quiet` clean afterwards. `make lint`, `make typecheck`, `make arch` and `make test`
  all still exit 0 — 8 tests, 3 contracts kept, 100% over 18 statements.

## Task Commits

1. **Task 1: AI_WORKFLOW.md section skeleton** — `63fd3a5` (docs)
2. **Task 2: Incident log opened with four real entries** — `8dc572c` (docs)

## Files Created/Modified

- `AI_WORKFLOW.md` — created, 282 lines. Task 1 wrote 111 lines (preamble + five sections);
  Task 2 replaced the log placeholder with 174 lines of dated entries and quoted evidence.

## Decisions Made

- **The fourth entry is labelled a demonstration, not a catch.** Its "how it was caught" part
  says plainly that it was not caught — it was done on purpose before either gate was trusted.
  Presenting a planned exercise as a discovery would be the same self-flattery the plan's hard
  rule forbids, just in a subtler form.
- **All ten research conflicts are enumerated, not two.** The plan asks for "at least two
  concrete examples". Listing every one and mapping each to an ADR turns an assertion about
  process into something an evaluator can verify against `DECISION_LOG.md` in one pass.
- **The preamble argues the reason for the missing trailer, not just the rule.** `CLAUDE.md`
  already states the rule; restating it here would add nothing. What this file can add is why a
  per-commit trailer is a worse form of transparency than a specific, checkable document.
- **No fifth incident was written.** Several further corrections happened during this phase —
  RESEARCH Pitfall 2 not reproducing, the pre-commit `entry:` failure, the Docker test stage
  missing `.env.example`, the 368 MB vs 285 MB image size. All are real and all are recorded in
  their own plan SUMMARYs and evidence files, but the plan names exactly four entries and forbids
  any other, so they were left for later phases to append rather than smuggled in now.
- **`## Human-Decided vs AI-Delegated` was seeded rather than deferred.** The plan asks for the
  Phase 1 split now; the section carries a closing note that Phase 7 adds the per-claim
  commit/file/test references, so the reader knows what is still owed.

## Deviations from Plan

### Auto-fixed Issues

None. Both tasks executed as written. No bug, missing functionality or blocker was encountered,
and no gate had to be repaired.

### Scope Additions

None. The file contains exactly the sections and exactly the four incidents the plan specifies.

## Issues Encountered

None. Two observations worth carrying:

- The first `pre-commit run --all-files` did not modify the new Markdown file — the Write tool
  emitted no trailing whitespace and a single final newline, so `trailing-whitespace` and
  `end-of-file-fixer` both passed on the first pass. This is the second consecutive
  documentation plan where the plan's expected first-run fix-up did not occur. The run-twice
  discipline was still followed; the second run plus `git diff --quiet` are the assertions that
  matter.
- Quoting terminal output verbatim inside fenced blocks is safe against `trailing-whitespace`
  only because the lines chosen from the captures carry none. A capture line ending in spaces
  would have been silently rewritten by the hook and would then have failed the substring
  assertion — worth knowing for every future phase that appends quoted evidence to this log.

## Verification Results

| Check | Result |
|-------|--------|
| `test -f AI_WORKFLOW.md` + all five `##` headings present | exit 0 |
| `grep -qi 'Phase 7'` / `grep -qi 'attribution'` | exit 0 (both) |
| `grep -c '^### 2026-' AI_WORKFLOW.md` | 4 (>= 4) |
| `grep -Eq '^## Incident Log' && grep -Eq '^### 2026-'` (VALIDATION AIW-03 command) | exit 0 |
| `grep -q 'heredoc'` | exit 0 |
| `grep -qi 'RFC 7807'` | exit 0 |
| `grep -q 'importlinter.cli'` | exit 0 |
| `grep -q 'Required test coverage of 75% not reached'` | exit 0 |
| `grep -q 'not allowed to import'` | exit 0 |
| Verbatim-quotation script | `evidence quoted verbatim` — 9 lines from `coverage-gate-red.txt`, 51 from `import-linter-red-green.txt` |
| `.venv/bin/pre-commit run --all-files` (run 1) | exit 0 — twelve hooks Passed, no file modified |
| `.venv/bin/pre-commit run --all-files` (run 2) | exit 0 — twelve hooks Passed |
| `git diff --quiet` after run 2 | exit 0 |
| `make lint` | exit 0 |
| `make typecheck` | exit 0 |
| `make arch` | exit 0 |
| `make test` | `8 passed`, `Required test coverage of 75% reached. Total coverage: 100.00%` |
| Phase 7 sections carry `_To be completed in Phase 7._` | pass (`## How This Project Was Built`, `## What I Did Not Do`) |
| No invented incident present | pass — exactly the four entries the plan enumerates |

## Self-Check: PASSED

`AI_WORKFLOW.md` verified present on disk (282 lines). Commits `63fd3a5` and `8dc572c` verified
in `git log`. Both commits passed the twelve pre-commit hooks with no `--no-verify`.

## Known Stubs

Two, both intentional and both marked in the file itself:

- `## How This Project Was Built` — `_To be completed in Phase 7._` The section states what it
  will hold (the Mermaid diagrams of the real workflow, AIW-01) and holds nothing else. Filling
  it now would mean drawing a diagram of a workflow that has run for one phase out of seven.
- `## What I Did Not Do` — `_To be completed in Phase 7._` (AIW-02/AIW-05 territory.) The
  scope-left-out list cannot be honest before the scope is finished.

`## Human-Decided vs AI-Delegated` is seeded and useful today but carries an explicit note that
Phase 7 adds the per-claim commit/file/test references AIW-02 requires. These are the placeholder
markers D-18 asks for, not unfinished work: the plan's deliverable is a skeleton Phase 7 fills
rather than restructures.

## Threat Flags

None. No network surface, auth path, file access pattern or schema was introduced. `AI_WORKFLOW.md`
is documentation that ships publicly; `detect-private-key` passed over it, and the quoted terminal
output contains only gate results, module paths and coverage tables — no credentials, tokens or
private paths beyond the repository-relative ones already visible in every other committed file.

## User Setup Required

None.

## Next Phase Readiness

Ready for plan 01-08 (the end-to-end phase gate, which carries a human checkpoint). What it must
know:

- **AIW-03 is satisfiable and should be re-asserted, not re-implemented.** The VALIDATION command
  for AIW-03 (`grep -Eq '^## Incident Log' AI_WORKFLOW.md && grep -Eq '^### 2026-' AI_WORKFLOW.md`)
  exits 0. `AI_WORKFLOW.md` is the last of the three brief/CONTEXT documentation artifacts;
  `CLAUDE.md`, `DECISION_LOG.md` and `AI_WORKFLOW.md` now all exist and cross-reference each
  other consistently.
- **The file is append-only from here.** Every subsequent phase adds a dated entry to
  `## Incident Log`; the file says so in two places (the section intro and the closing line), and
  `STATE.md` already carries this as a standing concern. 01-08 should verify the rule is stated,
  not add an entry of its own unless a real incident occurs during it.
- **Four real incidents from this phase are deliberately NOT in the log yet** — RESEARCH Pitfall 2
  failing to reproduce on import-linter 2.15, the pre-commit bare-`entry:` failure, the Docker
  `test` stage missing `.env.example`, and the 368 MB vs 285 MB image size. They are all recorded
  in the 01-03 through 01-05 SUMMARYs and in `evidence/`. If 01-08 or Phase 7 wants a richer log,
  these are the honest raw material, already captured.
- **Quoting discipline for future appends:** quote from a committed file under
  `evidence/`, never from memory, and avoid lines with trailing whitespace — the
  `trailing-whitespace` hook rewrites them inside fenced blocks too, which would break any
  substring assertion made against the capture.
- **Nothing outside `AI_WORKFLOW.md` was touched.** `CLAUDE.md` and `DECISION_LOG.md` are
  byte-identical to their 01-06 state; the working tree was clean before and after both commits.
