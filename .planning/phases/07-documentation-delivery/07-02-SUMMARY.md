---
phase: 07-documentation-delivery
plan: 02
subsystem: documentation-decision-log
tags: [doc-03, adr, append-only, ambiguities, claude-md]

# Dependency graph
requires:
  - phase: 07-documentation-delivery
    provides: "07-01 — the published error body, the subclass and the DOC-04 gate these ADRs describe"
  - phase: 02-domain-errors
    provides: "D-01/D-02/D-03 — the transition matrix and the medium default these ADRs transcribe"
provides:
  - "ADR-097 — three statuses, the exhaustive matrix, completed → pending forbidden"
  - "ADR-098 — low|medium|high, and Task.DEFAULT_PRIORITY as the one home of the default"
  - "ADR-099 — the corrections entry superseding ADR-019 and ADR-072 by id"
  - "ADR-100 — the no-model error leg and ProblemAwareFastAPI"
  - "ADR-101 — the DOC-04 totality gate and the GET /health 503 exemption"
  - "DECISION_LOG.md §Start here — the ambiguity→ADR map plan 07-04's gate reads"
  - "CLAUDE.md §The published document — four Project Rules bullets"
affects: [07-03-ai-workflow, 07-04-readme, 07-05-rehearsal]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A factual correction to an append-only log is a new entry naming the old one by id; git diff | grep -c '^-' returning 1 is the proof"
    - "A tag description is prose no gate reads, so it is held to the ADR standard by hand"

key-files:
  created: []
  modified:
    - DECISION_LOG.md
    - CLAUDE.md
    - src/taskmanager/main.py

key-decisions:
  - "The status ADR states the matrix as a table and names the two tests that pin it — test_task_status.py for the table's shape and test_tasks.py's derived FORBIDDEN_TRANSITIONS for its complement. The plan's draft named tests/unit/domain/test_task.py, which does not hold the matrix; an ADR that names the wrong gate is the failure the threat model calls out"
  - "The priority ADR records the second half of the question explicitly: not only low|medium|high, but that the default is applied by Task.create and read by the schema, so it has one home"
  - "One corrections entry for both stale claims, in ADR-041's shape, rather than two entries or an in-place edit"
  - "The tag table did not get a third ADR. It is one consequence bullet of ADR-100 — plus the correction of the one description that shipped false"
  - "The start-here block is two tables and a sentence, 28 lines, inserted into the header region. No 96-row table of contents and no generator (07-RESEARCH Gap 2)"

metrics:
  duration: ~30 min
  completed: 2026-09-19
  tasks: 3
  commits: 3
  tests-added: 0
  suite: 1115 passed, 100% coverage over 1690 statements
---

# Phase 7 Plan 02: The Decision Log Closes DOC-03 Summary

All five of the brief's named ambiguities now resolve to a numbered ADR, the log's two false
sentences are corrected without being edited, and a reader lands on both facts in the first screen.

## What Was Built

**ADR-097 and ADR-098 — the two missing ambiguities.** The status vocabulary, the exhaustive
transition table rendered as a 3×3 matrix, `completed → pending` as the single forbidden move with
its 409 `invalid_status_transition`, and the `KeyError`-on-a-fourth-status property; then
`low | medium | high` ascending, with `Task.DEFAULT_PRIORITY` as the one home of TASK-01's medium
default that the request schema reads rather than restates. Both are transcriptions of docstrings
that already carried the reasoning, plus the options that were rejected: free-text status, a
`done`/`not done` flag, a permissive default table; integer `1..5`, an open string, and the same
enum with the default on the enum.

**ADR-099 — the corrections entry.** One entry in ADR-041's shape carrying both stale claims:
ADR-019's "the workflow has never run on a real runner" (false since CI run `35301518310`) and
ADR-072's `tests/api/test_error_contract.py` (moved to `tests/unit/presentation/` by 06-04). Both
old entries are byte-identical. It states the mechanism once for the next phase and records that
ADR-019's underlying worry gets its real answer in 07-05, since the Phase 7 push is the first time
Phases 2-6 run on a runner.

**ADR-100 and ADR-101 — what 07-01 shipped.** The four measured leg spellings with the three
rejections named, the `FastAPI` subclass versus the `method-assign` assignment, the `deepcopy`,
and the model-bound-by-a-test rule; then the DOC-04 gate as a floor-plus-property totality gate
over `app.openapi()`, the `GET /health` 503 exemption that has to keep earning itself, and the
non-vacuity guard that fails rather than skips.

**`DECISION_LOG.md` §Start here** — 28 lines inserted into the header region: the five ambiguities
→ ADR-009/097/098/069/070, and the five most-questioned decisions → ADR-001, ADR-008, ADR-009,
ADR-062+ADR-063, ADR-010. These are the ids plan 07-04's gate will read.

**`CLAUDE.md` §The published document** — four bullets: `problem_response()` with no `model=` key
and the one `/health` exemption; the subclass and why the registration is not automatic; the gate
and what each of its failures names; and the tag-description rule. Plus `schemas/problem.py`
folded into the existing `REQUIRED_SCANNED_MODULES` bullet.

## Deviations from Plan

**1. [Rule 1 — bug] The `users` tag description shipped false, and was corrected**
- **Found during:** Task 2, reading `OPENAPI_TAGS` to write ADR-100.
- **Issue:** 07-01's description read "Summaries only - no email address of another account is
  published here". `UserSummaryResponse` publishes `id`, `full_name` and **`email`**, and ADR-068
  decided that on purpose — `GET /api/v1/users` is an email directory readable by every
  authenticated caller. ADR-068 goes further and names describing it as restricted as "the one
  available wording that would actively mislead", which is the wording that shipped.
- **Fix:** `src/taskmanager/main.py` — the description now states the three published fields, who
  may read them, and that no client should treat the route as restricted. No gate reads tag prose,
  so the rule that catches the next one is a CLAUDE.md bullet and ADR-100's consequence.
- **Commit:** d45c0d2

**2. [Accuracy] ADR-097 names the tests that actually pin the matrix**
- The plan's draft consequence credited `tests/unit/domain/test_task.py`. The matrix is pinned by
  `tests/unit/domain/test_task_status.py` (exhaustive over `TaskStatus`, each row exact, no
  self-transition) and by `tests/integration/api/test_tasks.py`, whose `FORBIDDEN_TRANSITIONS` is
  *derived* as the complement and drives all four pairs over HTTP — the three self-pairs expecting
  the 200 no-op and `completed → pending` expecting the 409. Both were read before the entry was
  written, per the threat model's "an ADR that describes a rule the code does not implement".

**3. [Scope] The tag table got no ADR of its own**
- Taken as the plan permits: 07-01's SUMMARY records no separate decision for it beyond the
  registration order, so it is a consequence bullet of ADR-100 rather than an invented third entry.

## Verification

| Check | Result |
|-------|--------|
| `make lint`, `make typecheck`, `make arch`, `make test` | green; 1115 passed, 100% over 1690 statements, 4 contracts kept |
| `git diff 3a3e5fd HEAD -- DECISION_LOG.md \| grep -c '^-'` | **1** — the diff's own header, across all three tasks |
| Diff hunks in `DECISION_LOG.md` | two: the header insert and the tail append. Neither touches ADR-019 or ADR-072 |
| `grep -c '^## ADR-0'` | 96 → **101**, contiguous, no duplicate |
| The five ambiguity headings resolve | 5/5 |
| Every ADR id the start-here block cites | all 13 resolve to a `## ADR-NNN:` heading |
| Four-part shape in each new entry | 4/4 in all five |
| `<!-- GSD: -->` delimiters in `CLAUDE.md` | untouched; 0 deleted delimiter lines |
| Commit trailers | no `Co-Authored-By`, no `Generated with` |

## For the Next Plans

**07-03 (`AI_WORKFLOW.md`)** — nothing here constrains it. Worth one line: this plan is a clean
example of the workflow's own thesis, in that reading the source to write the ADR is what caught a
false sentence in the published OpenAPI document that review had passed.

**07-04 (`README.md` + `tests/architecture/test_documentation_claims.py`)**
- The ambiguity→ADR mapping the gate must pin is now fixed and live in `DECISION_LOG.md`
  §Start here: **ADR-009, ADR-097, ADR-098, ADR-069, ADR-070**. The block also cites ADR-049,
  ADR-054, ADR-068, ADR-001, ADR-008, ADR-062, ADR-063 and ADR-010 — a gate that checks "every id
  cited resolves to a heading" should read all thirteen.
- The log is now **4,560 lines**, ADR-001..**ADR-101**; the next free number is **ADR-102**.
- 07-04 still owns the `Dockerfile` `COPY` line that gate needs. Nothing in `tests/`, `scripts/`,
  `.pre-commit-config.yaml` or `.github/` reads `DECISION_LOG.md` yet, so 07-04 adds the first
  reader — and with it the host/container divergence risk 07-RESEARCH Pitfall 1 describes.
- The README's endpoint overview should use the six tag names in registration order: health, auth,
  task lists, tasks, users, assignments. The `users` line should match the corrected description —
  the directory publishes email to any authenticated caller — because ADR-068 says the trade-off
  belongs where a client reads it, and the README is now the second place that is true of.
- The "errors are RFC 9457 from every route" sentence still owes the `GET /health` 503 caveat
  (ADR-101 names the exemption), or the README and `/docs` disagree by one leg.

**07-05 (rehearsal)** — no new command, hook or CI step was added here either. ADR-099 records that
the Phase 7 push is the first run of Phases 2-6 on a real runner and that ADR-019's one budgeted
fix-up commit is spent there if anywhere.

## Self-Check: PASSED

- `DECISION_LOG.md` §Start here, ADR-097..ADR-101 — FOUND (`grep -n '^## ADR-101:'` matches)
- `CLAUDE.md` §The published document — FOUND (`grep -n 'test_openapi_completeness' CLAUDE.md`)
- Commits `e53033e`, `d45c0d2`, `1682ede` — FOUND in `git log`
