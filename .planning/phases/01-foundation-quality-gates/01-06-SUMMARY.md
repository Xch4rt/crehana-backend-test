---
phase: 01-foundation-quality-gates
plan: 06
subsystem: documentation
tags: [claude-md, decision-log, adr, project-rules, ai-transparency]

# Dependency graph
requires:
  - "01-03: `.importlinter` with the three contracts whose layer order the rules must mirror"
  - "01-04: `.pre-commit-config.yaml` and the `Makefile` target names the gate rules reference"
  - "01-05: `Dockerfile` test stage and `ci.yml`, whose direct-invocation split the rules record"
provides:
  - "`CLAUDE.md` `## Project Rules` - the layer, error, gate, configuration, language and attribution rules, placed outside every GSD delimiter block"
  - "`DECISION_LOG.md` - 19 ADRs in Context / Options / Decision / Consequences form, the brief-mandated literal filename"
  - "The standing maintenance rule that a new gate is wired into both `.pre-commit-config.yaml` and `ci.yml`, written in two places"
affects: [01-07, 01-08, 02-domain, 03-infrastructure, 07-delivery]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Hand-maintained CLAUDE.md content lives outside the `<!-- GSD:*-start/-end -->` blocks, with a placement assertion in the plan's own verification"
    - "One ADR per decision, four labelled subsections, at least one concretely rejected alternative in every Options block"
    - "Consequences record accepted costs, not only benefits; four ADRs name a risk that is still open"

key-files:
  created:
    - DECISION_LOG.md
  modified:
    - CLAUDE.md

key-decisions:
  - "`## Project Rules` appended after `<!-- GSD:profile-end -->` rather than inside any generated block; the plan's placement script asserts it and printed `placement OK`."
  - "19 ADRs shipped instead of the 17 the plan floors at: the two extra are the Dockerfile `test` stage over a compose profile and the major-tag action pinning, both handed over explicitly by 01-05 as owed."
  - "The layer order in `CLAUDE.md` was transcribed from `.importlinter` rather than from CONTEXT D-10, so the document and the contract cannot disagree - they are the same five names in the same direction."
  - "`ADR-010` names ruff as the better tool in plain words rather than hedging: the point of the entry is that the brief's flake8 mandate was recognised as a constraint, which only reads as deliberate if the rejected option is not diminished."
  - "The `.venv/bin` hook consequence is written in both `CLAUDE.md` (the rule) and `ADR-015` (the reasoning), because T-01-47 is a drift threat and a rule stated once in a decision log is not a rule a future contributor reads."

patterns-established:
  - "Every ADR that cites a verified observation names the evidence file that holds the capture, so a claim in the log can be checked in one command"
  - "The gate set is documented as a pair (pre-commit + CI), never as a single list, so the duplication is visible rather than accidental"

requirements-completed: [AIW-04, FND-09]

# Metrics
duration: 10min
completed: 2026-09-17
---

# Phase 01 Plan 06: Project Rules and Decision Log Summary

**The rules the tooling already enforces are now written where a human and every future
Claude session read them, in a `CLAUDE.md` section that regeneration cannot delete, and
`DECISION_LOG.md` opens with 19 ADRs whose Consequences name the costs - nine dependencies
pinned before first import, a 3.14 host against 3.13 CI, a gate list duplicated between
pre-commit and CI, and a workflow that has never run on a real runner.**

## Performance

- **Duration:** 10 min
- **Started:** 2026-09-18T01:52:47Z
- **Completed:** 2026-09-18T02:02:50Z
- **Tasks:** 2
- **Files created:** 1 (plus 1 modified)

## Accomplishments

- `CLAUDE.md` gained a hand-maintained `## Project Rules` section in five blocks — layers,
  error handling, quality gates, configuration, language and attribution. It sits after
  `<!-- GSD:profile-end -->`, outside every GSD delimiter pair; the plan's placement script
  parsed the file and printed `placement OK` (T-01-35).
- The documented layer order is the `.importlinter` `layers` contract verbatim:
  `main > presentation > infrastructure > application > domain`, with the two `forbidden`
  contracts restated as the "domain imports no third-party library" and "application knows no
  web framework or ORM" rules, including the deliberate asymmetry that Pydantic is banned in
  `domain` and allowed in `application` (T-01-32).
- The rules name their own enforcement: `tests/architecture/test_layer_boundaries.py`,
  `make arch`, CI. A violating import fails a test, not a review — stated in those words.
- The gate rule records the **split**: pre-commit is the developer-host gate and needs `.venv`;
  CI and the Docker `test` stage run the same tools directly; a new gate goes in **both**
  `.pre-commit-config.yaml` and `.github/workflows/ci.yml` (T-01-47).
- The 75% floor is stated together with the two ways of cheating it that are forbidden —
  lowering the threshold, and reaching it with `# pragma: no cover` or a coverage `omit`.
- `DECISION_LOG.md` ships with **19 ADRs**, each with all four labelled subsections and each
  Options block naming a concretely rejected alternative: PostgreSQL over SQLite; Python 3.13
  over 3.12 and 3.14; the `src/` layout; dataclass domain entities with Pydantic at the
  boundaries; RFC 9457 `problem+json`; psycopg 3 with async SQLAlchemy over asyncpg; Alembic
  over `create_all()`; the 404/403 visibility rule; whole-list completion percentage;
  flake8 over ruff; pip exact pins; pytest-asyncio with
  `asyncio_default_fixture_loop_scope = function`; `postgres:18-alpine`; plus the six settled
  by this phase — the `.importlinter` INI file, the venv-qualified repo-local hooks, the
  import-linter Python API, the `up`/`down` placeholders, the Dockerfile `test` stage, and
  major-tag action pinning.
- ADR-015 carries the full `.venv/bin` consequence chain the plan demanded: the literal entries
  `.venv/bin/mypy` and `.venv/bin/lint-imports`, the reason (pre-commit activates no
  virtualenv and this host has no project tools on `PATH` outside `.venv`), the observed
  failure quoted from `evidence/pre-commit-venv-entry.txt`, the accepted cost (host-only
  config), the consequence (CI and the container never invoke `pre-commit`) and the
  maintenance rule (both files, always).
- Accepted costs appear in nine Consequences blocks, four of them describing a risk that is
  still open: the 3.14-host / 3.13-CI skew under `filterwarnings = error` (ADR-002), nine
  dependencies pinned before Phase 1 imports any of them (ADR-011), the duplicated gate list
  (ADR-015), and a `ci.yml` that has never executed on a runner (ADR-019). ADR-018 records
  368 MB as observed rather than repeating the research's 285 MB (T-01-34).
- `.venv/bin/pre-commit run --all-files` ran twice with all twelve hooks `Passed` both times
  and `git diff --quiet` clean afterwards — the new Markdown file tripped neither
  `end-of-file-fixer` nor `trailing-whitespace` on the first run.
- `make lint`, `make typecheck`, `make arch` and `make test` all still exit 0: black/isort/
  flake8 silent, mypy clean over 14 files, 3 contracts kept, 8 tests, 100% over 18 statements.

## Task Commits

1. **Task 1: Project rules section in CLAUDE.md** — `0456070` (docs)
2. **Task 2: DECISION_LOG.md in ADR style** — `127b00b` (docs)

## Files Created/Modified

- `CLAUDE.md` — +57 lines, one new `## Project Rules` section after the profile block. No
  generated block was touched: Project, Technology Stack, Conventions, Architecture, Project
  Skills, GSD Workflow Enforcement and Developer Profile are byte-identical.
- `DECISION_LOG.md` — 614 lines, a preamble naming the format and the opening date
  (2026-09-17) plus ADR-001 through ADR-019.

## Decisions Made

- **Two extra ADRs beyond the plan's floor.** The plan names 13 + 4 = 17. 01-05's handover
  named three it considered owed, two of which (the `test` stage, the action pinning) were not
  in the plan's enumeration. Dropping them would have left the two most recent decisions of the
  phase undocumented while the log claimed to cover everything locked so far, so they were
  added as ADR-018 and ADR-019.
- **The layer rules were copied from the contract, not from CONTEXT.** D-10 and `.importlinter`
  agree today, but only one of them is executed. Transcribing from the executed artifact makes
  T-01-32 (documentation drifting from enforcement) structurally harder, not just checked.
- **`ADR-010` states plainly that ruff is the better tool.** A decision log that only ever
  praises what was chosen is the "rationalises rather than records" failure T-01-34 names. The
  entry's value to an evaluator is that the constraint was seen as a constraint.
- **The duplicated gate list is written twice on purpose.** It is a rule in `CLAUDE.md` (where
  someone about to add a gate looks) and a consequence in ADR-015 (where someone asking *why*
  looks). Duplication is the right call when the failure mode is silent divergence.
- **No `AI_WORKFLOW.md` content was written**, though both new files reference it. Plan 01-07
  owns that file; `CLAUDE.md` only names it as where AI involvement is documented.

## Deviations from Plan

### Auto-fixed Issues

None. Both tasks executed as written; no bug, missing functionality or blocker was
encountered, and no gate had to be repaired.

### Scope Additions

**1. Two ADRs added beyond the enumerated set**

- **Found during:** Task 2
- **Reason:** 01-05's SUMMARY explicitly hands over three ADRs; the plan's enumeration includes
  only the CI-direct-invocation one (folded into ADR-015). The Dockerfile `test` stage and the
  action-pinning decision would otherwise have been the only phase decisions absent from a log
  that claims completeness.
- **Impact:** 19 ADRs instead of 17; the plan's `-ge 17` gate is satisfied with margin.
- **Commit:** `127b00b`

## Issues Encountered

None. Two observations worth carrying:

- The first `pre-commit run --all-files` did not modify the new Markdown file, contrary to the
  plan's expectation. The Write tool emitted a single trailing newline and no trailing
  whitespace, so `end-of-file-fixer` and `trailing-whitespace` both passed on the first pass.
  The run-twice discipline was still followed; the second run and `git diff --quiet` are the
  assertions that matter.
- `pre-commit run --all-files` only sees files git knows about, so `DECISION_LOG.md` had to be
  `git add`-ed before the first run or every file-scoped hook would have reported
  `(no files to check) Skipped` against it — the same trap 01-04 recorded for `check-yaml`.

## Verification Results

| Check | Result |
|-------|--------|
| `grep -q '^## Project Rules' CLAUDE.md` | exit 0 |
| `grep -q 'HTTPException' CLAUDE.md` | exit 0 |
| `grep -q 'problem+json'` / `'make arch'` / `'75'` / English / no-attribution in `CLAUDE.md` | exit 0 (all) |
| Placement script (section outside every GSD block) | `placement OK` |
| Documented layer order equals `.importlinter` `layers` contract | pass (5 names, same order) |
| `grep -c '^## ADR-' DECISION_LOG.md` | 19 (>= 17) |
| `**Context**` / `**Options**` / `**Decision**` / `**Consequences**` line counts | 19 / 19 / 19 / 19 |
| `grep -qi 'ruff'` | exit 0 (ADR-010, named as the unconstrained choice) |
| `grep -q 'RFC 9457'` / `'psycopg'` / `'postgres:18-alpine'` | exit 0 (all) |
| `grep -q 'asyncio_default_fixture_loop_scope'` / `'importlinter'` / `'3.14'` | exit 0 (all) |
| `grep -q '\.venv/bin/lint-imports'` / `'pre-commit'` | exit 0 (both, ADR-015) |
| `.venv/bin/pre-commit run --all-files` (run 1) | exit 0 — twelve hooks Passed, no file modified |
| `.venv/bin/pre-commit run --all-files` (run 2) | exit 0 — twelve hooks Passed |
| `git diff --quiet` after run 2 | exit 0 |
| `make lint` | exit 0 — 14 files unchanged, flake8 silent |
| `make typecheck` | `Success: no issues found in 14 source files` |
| `make arch` | `Contracts: 3 kept, 0 broken.` |
| `make test` | `8 passed`, `Required test coverage of 75% reached. Total coverage: 100.00%` |
| Every GSD-delimited block in `CLAUDE.md` unmodified | pass (diff is a pure 57-line append) |
| `AI_WORKFLOW.md` not created (plan 01-07 owns it) | pass |

## Self-Check: PASSED

`DECISION_LOG.md` verified present on disk; `CLAUDE.md` verified modified. Commits `0456070`
and `127b00b` verified in `git log`. Both commits passed the twelve pre-commit hooks.

## Known Stubs

None. Both files are complete for Phase 1 as specified. `DECISION_LOG.md` is explicitly an
append-only document — Phases 2 through 7 add ADRs as decisions are made, and the preamble says
so; that is the designed lifecycle, not an unfinished artifact.

## Threat Flags

None. No network surface, auth path, file access pattern or schema was introduced. Both files
are documentation and ship publicly; the only value resembling a credential anywhere near them
is the `JWT_SECRET=replace-me-with-a-generated-secret` placeholder in `.env.example`, which
neither file reproduces. `detect-private-key` passed over both.

## User Setup Required

None.

## Next Phase Readiness

Ready for plans 01-07 and 01-08. What they must know:

- **Plan 01-07 (`AI_WORKFLOW.md`): the file does not exist yet and nothing here created it.**
  Both new files reference it by name — `CLAUDE.md`'s attribution rule says AI involvement is
  documented there, and it is the project's stated alternative to commit trailers. That
  promise is now in the shipped repository, so 01-07 is load-bearing rather than optional.
- **Plan 01-07:** the four evidence files in
  `.planning/phases/01-foundation-quality-gates/evidence/` are each cited by at least one ADR
  (`pre-commit-venv-entry.txt` → ADR-015, `import-linter-red-green.txt` → ADR-016,
  `docker-test-stage.txt` → ADR-018, `coverage-gate-red.txt` → the 75% rule in `CLAUDE.md`).
  The incident log can point at the ADR and the capture together rather than re-narrating.
- **Plan 01-08 (phase gate):** `CLAUDE.md` now claims, in the repository itself, that
  `make lint typecheck arch test` are all green before any commit and that coverage is gated at
  75%. The combined run is what makes that claim true; a red gate at 01-08 would make the
  shipped documentation false, not merely the phase incomplete. All four were green at the end
  of this plan.
- **Plan 01-08:** if the GitHub repository checkpoint is declined, ADR-019's "the workflow has
  never run on a real runner" stays accurate and needs no edit; if it is accepted and CI needs a
  fix-up commit, that fix-up is itself worth a line in `AI_WORKFLOW.md` and does **not** require
  a new ADR unless the fix changes a decision.
- **Phase 2 onwards:** `DECISION_LOG.md` is appended to, never rewritten. A reversal gets a new
  ADR that supersedes the old id. Phase 2 owes at least the `DomainError` hierarchy shape and
  the status-code mapping table promised by ADR-005; Phase 3 owes the session-scope call
  ADR-012 defers and the `expire_on_commit=False` consequence ADR-006 names.
- **Phase 7:** ADR-019 names SHA-pinning the GitHub Actions as the delivery-hardening option,
  and ADR-010's ruff line is the one a reviewer is most likely to look for.

---
*Phase: 01-foundation-quality-gates*
*Completed: 2026-09-17*
