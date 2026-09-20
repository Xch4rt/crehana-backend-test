---
phase: 08-web-ui
plan: 03
subsystem: documentation
tags: [readme, ai-workflow, claude-md, rehearsal, documentation-gate, adr-104, adr-105]
requires:
  - 08-01's UI image, `ui` compose service and rehearsal preamble
  - 08-02's four screens and their 66 vitest tests
  - the Phase 7 documentation gate and clean-clone rehearsal (ADR-102, ADR-103)
provides:
  - a README that describes the UI and says the brief asked for none
  - two UI commands the clean-clone rehearsal actually executes
  - a documentation gate that covers eight phases
  - the Phase 8 human/AI account, one dated incident entry, and the frontend Project Rules
  - a clean, green, rehearsed, unpushed tree for 07-05 task 4
affects:
  - README.md, AI_WORKFLOW.md, CLAUDE.md
  - tests/architecture/test_documentation_claims.py
  - .planning/REQUIREMENTS.md, .planning/ROADMAP.md, .planning/STATE.md
tech-stack:
  added: []
  patterns: [executable documentation, append-only log vs editable narrative, gates named beside the rules they enforce]
key-files:
  created:
    - .planning/phases/08-web-ui/08-03-SUMMARY.md
  modified:
    - README.md
    - AI_WORKFLOW.md
    - CLAUDE.md
    - tests/architecture/test_documentation_claims.py
    - .planning/REQUIREMENTS.md
    - .planning/ROADMAP.md
    - .planning/STATE.md
decisions: []
metrics:
  duration: 40min
  tasks: 3
  files: 8
  completed: 2026-09-19
---

# Phase 8 Plan 03: The documents made true again — Summary

The README now describes a web UI and says in its second sentence that the brief asked for none;
`AI_WORKFLOW.md`'s own written objection to a Node toolchain in a Python deliverable is amended in
place rather than left standing false, and names the human who overruled it; and `make rehearse`
exited 0 against the phase's final commit, with two new commands proving from a fresh clone that
the SPA answers on `:8080` and that a bearer-authenticated, query-stringed call through its `/api/`
proxy comes back with the whole-list `"completion_percentage":50.0`.

## What was built

**Task 1 — the README (`45a655b`).** One sentence in "Run it" names
**<http://localhost:8080>**, says the brief asks for no UI, and explains why the first `make up`
is slower than an API-only start. A new section inside the rehearsal markers, "The web UI (beyond
the brief)", describes what the UI does, puts the honesty paragraph **first** among the caveats
(outside the brief, no row in the requirement-to-evidence map, same-origin through
`frontend/nginx.conf`, `src/taskmanager` untouched, ADR-105/106/107), and states how it is gated,
with the real 66-tests-across-10-files figure from 08-02 rather than a prediction. Then the fenced
block the rehearsal executes — `curl -sf` plus `grep -q`, no `make` target, because
`test_the_rehearsal_region_needs_no_virtualenv` allows only the four Docker-path targets in there.
"Pending" gained the UI's deliberate gaps, including the qualifier that matters: the one browser
walkthrough was a manual spot check against a cached chromium binary, not a gate and not
reproducible.

**Task 2 — the account, the gate, the rules (`041ab61`).** `PHASES` in
`tests/architecture/test_documentation_claims.py` now reads `(1, …, 8)` — driven red once,
uncommitted, with the block absent — in the **same commit** as the `AI_WORKFLOW.md` block that
satisfies it. The narrative paragraph above `## Human-Decided vs AI-Delegated` is rewritten in
place: the Node toolchain here now exists, it is the UI's, it carries no Mermaid renderer, and the
earlier judgement was reversed by the human (ADR-105). The Phase 8 block opens on the line that
matters — *the AI recommended keeping the UI out of the delivered repository and the human decided
to include it* — and every hash in it resolves. `CLAUDE.md` gained a `### Frontend` subsection
where each of seven rules names the gate that fails when it is broken. UI-08 is ticked; the roadmap
records Phase 8 complete with a per-criterion verdict and says out loud that it finished out of
order.

**Task 3 — the rehearsal and the hand-over (this commit).** `make rehearse` run twice, STATE.md
hand-edited, and the tree left exactly as 07-05 task 4 expects.

## Verification

| Check | Result |
|-------|--------|
| `make lint` / `make typecheck` / `make arch` | exit 0 on every commit |
| `make test` | **1140 passed, 100.00% over 1690 statements** — unchanged |
| `make docker-test` | **1140 passed, 100.00% over 1844 statements** |
| `make ui-lint` / `make ui-typecheck` | exit 0 |
| `make ui-test` | **66 passed across 10 files** |
| `sh scripts/clean-clone-rehearsal.sh --extract-only` | exit 0; ends with the two new `curl` lines, in order |
| README backticked-path scan | every cited path exists and is tracked, `.env` excepted |
| evidence-map rows | **23 before, 23 after** — no UI row |
| `git diff 1dd5af7 -- src/taskmanager` | **empty** |
| `git diff 06e5453 -- .planning/phases/07-documentation-delivery/` | **empty** |
| `git status --porcelain` | empty |
| pushed | **nothing** |

### `make rehearse`, twice

The first run cloned `041ab61` and exited **0**:

```
    2s  1. stop the developer stack (plain `down`: test_pgdata survives)
    2s  2. clone the committed tree into an empty directory
    0s  4. docker compose down -v in the clone (project: crehana-rehearsal)
    0s  5. every path the README cites, and every [PDF] key it owes
   26s  6. docker compose build --no-cache          (npm ci 5.3s, tsc+vite build 3.0s)
   91s  7. run the README's own commands
    3s  8. docker compose down -v in the clone, and remove the clone
  124s  total
```

The trace shows both new lines executing against the clone's own `ui` container:

```
+ UI=http://localhost:8080
+ curl -sf http://localhost:8080
+ grep -q 'id="root"'
+ curl -sf 'http://localhost:8080/api/v1/task-lists/10b78d64-.../tasks?priority=high' -H 'Authorization: Bearer eyJ...'
+ grep -q '"completion_percentage":50.0'
```

The second proves three things at once that a bare `curl` would not: the proxy forwarded the
`Authorization` header, it forwarded the query string, and the body that came back reports the
**whole list** (`total_tasks: 2`, `completion_percentage: 50.0`) while returning one item.

The second run cloned the phase's **final** commit — this one — and its result is in the execution
report. It differs from `041ab61` only by `.planning/STATE.md` and this file, prose the rehearsal
reads only for its `[PDF x.y]` keys.

## Deviations from Plan

**1. [Rule 1 - Bug] The documentation gate's own docstring still called the Node toolchain "the wrong trade"**
- **Found during:** Task 2, while bumping `PHASES`.
- **Issue:** the plan says to change nothing else in
  `tests/architecture/test_documentation_claims.py`. But
  `test_the_ai_workflow_still_draws_the_diagrams_aiw_01_asks_for`'s docstring carried the same
  now-false sentence the plan exists to amend in `AI_WORKFLOW.md` — "adding a Node toolchain to a
  Python deliverable is the wrong trade" — in the very module that gates the document's honesty.
- **Fix:** amended to say what is true: there is still no local Mermaid renderer, Phase 8 put a
  Node toolchain here after all (ADR-105), and it is the UI's, carrying no renderer. Two comment
  lines saying "seven phases" beside `PHASES` were updated to "eight" in the same edit.
- **Commit:** `041ab61`

**2. [Scope] `.planning/REQUIREMENTS.md`'s per-phase totals line gained `Phase 8 = 8`**
- Not in the plan's list. The line enumerated Phases 1-7 and would have been quietly wrong about a
  phase whose requirements it lists twenty lines above. One clause, no rule changed.
- **Commit:** `041ab61`

**3. [Scope] STATE.md also gained the `[Phase 08-02]` findings and metrics row that 08-02 never added**
- 08-02 updated the frontmatter and Current Position but added no `## Accumulated Context` bullets,
  left `## Session Continuity` pointing at 08-01, and added no `Phase 08 P02` metrics row. Rather
  than record only 08-03's findings on top of a gap, the five 08-02 findings were written from its
  SUMMARY and the metrics row added.
- **Commit:** this one

**4. [Honest limit] No commit can contain the sha of the rehearsal that cloned it**
- The plan asks STATE.md to name the sha `make rehearse` was green on, *and* for the final commit
  to be the rehearsed one. Both cannot hold for the same commit. STATE.md names `041ab61` for the
  first run with its full timings, states precisely how the final commit differs from it, and says
  the final run's sha is in the execution report. No rehearsal claim is made before it was run.

**Not a deviation:** no ADR was appended. `DECISION_LOG.md` stays at **108** entries and the README
still says `108 ADRs`; nothing in this plan decided anything ADR-105 through ADR-108 had not
already decided. The next free id is **ADR-109**.

## Threat Flags

None. The plan's register is unchanged and each item is now asserted rather than intended: T-08-11
(the README implying the UI satisfies a brief requirement) — the section says the opposite and the
evidence map still has 23 rows; T-08-12 — `rehearsal_assert_the_ui_is_ours` compared the container
publishing `:8080` with `docker compose ps -q ui` before either UI assertion ran; T-08-13 — the
developer's `test_pgdata` survived both runs; T-08-14 — nothing was pushed; T-08-15 — every
`commit <sha>` in `AI_WORKFLOW.md` resolves under `git cat-file -e`.

## Known Stubs

None.

## For 07-05, resuming at task 4

- **The tree is ready:** clean, every gate green, `make rehearse` green on the final commit,
  nothing pushed, and `07-05-PLAN.md` byte-identical to how Phase 8 found it.
- **Its "289+ commits" is stale by more than the "+".** Measured at `041ab61`:
  `git rev-list --count origin/main..HEAD` = **328**, `git ls-files .planning | wc -l` = **245**;
  this commit makes them **329** and **246**. `origin/main` is still the 43-commit Phase 1 push, so
  all of it is unpublished. Run both commands; do not copy the number, and do not edit that plan.
- **What becomes public that was not in 07-05's original scope:** the whole `frontend/` package
  including its 132 kB `package-lock.json`, the `ui` service in `docker-compose.yml`, the
  `frontend` job in CI, and the UI section of the README.
- **CI now has two jobs, not one.** The `frontend` job runs `npm ci`, eslint, `tsc --noEmit` and
  vitest on Node 24. It has never run on a runner — Phases 2-8 were never pushed — so task 5's
  observed-green CI run is the first time either job executes there.
- **First-run cost for an evaluator.** `docker compose up` now builds three images; in the
  rehearsal's `--no-cache` run the UI stage cost `npm ci` 5.3 s plus `tsc --noEmit && vite build`
  3.0 s, inside a 26 s total build. On a cold machine pulling `node:24-alpine`,
  `nginx:1.30-alpine`, `python:3.13-slim-trixie` and `postgres:18-alpine` it is longer; the README
  says so in the "Run it" section rather than leaving it a surprise.

## Self-Check: PASSED

`08-03-SUMMARY.md` exists; `45a655b` and `041ab61` resolve in `git log`; the working tree is clean
after this commit; `make rehearse` exited 0 on it.
