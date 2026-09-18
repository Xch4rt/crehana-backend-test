---
phase: 01-foundation-quality-gates
plan: 08
subsystem: verification
tags: [phase-gate, evidence, ci, github, secret-audit, attribution, fnd-09, fnd-10, dock-04]

# Dependency graph
requires:
  - "01-01: `pyproject.toml`, `requirements*.txt`, `.flake8`, `pytest.ini` — the FND-02/FND-03/FND-05 spot checks"
  - "01-02: `settings.py`, `main.py` and the six tests carrying the 100% coverage the gate measures"
  - "01-03: `.importlinter` and the contract tests — `make arch` and the `lint-imports` step"
  - "01-04: `.pre-commit-config.yaml` — the twelve hooks run twice, plus once under a stripped environment"
  - "01-05: `Dockerfile` (`test` stage) and `.github/workflows/ci.yml` — `make docker-test` and the real CI run"
  - "01-06: `CLAUDE.md` and `DECISION_LOG.md` — the AIW-04 spot check and the attribution rule audited here"
  - "01-07: `AI_WORKFLOW.md` — the AIW-03 spot check"
provides:
  - "`evidence/phase-gate.txt` — the whole Phase 1 gate observed green in one uninterrupted run, plus the first real CI run"
  - "FND-10 satisfied by observation: a public GitHub repository with a `success` CI run, not the documented fallback"
  - "A published, immutable history proven to contain no `.env`, no credential and no AI attribution trailer"
  - "`origin` → git@github.com:Xch4rt/crehana-backend-test.git, `main` tracking it"
affects: [02-domain, 03-infrastructure, 04-features, 05-auth, 06-testing, 07-delivery]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Phase completion is evidenced by one uninterrupted capture of every gate, not by per-plan green runs stitched together after the fact"
    - "Before a first push to a remote, assert `isEmpty: true` — a populated remote means someone else's history and the correct response is to stop, never to force"
    - "The attribution audit is reported as a raw count plus a refined count, with the single raw match explained, rather than as a bare pass"

key-files:
  created:
    - .planning/phases/01-foundation-quality-gates/01-08-SUMMARY.md
  modified:
    - .planning/phases/01-foundation-quality-gates/evidence/phase-gate.txt

key-decisions:
  - "The user supplied an already-created empty public repository, so `gh repo create` was never run and no README or 'first commit' was fabricated — GitHub's generic quick-setup snippet was deliberately ignored in favour of pushing this repository's real `main` unchanged."
  - "`gh repo view --json isEmpty` was re-checked read-only immediately before the push, with a documented stop-and-report response if it had come back populated. No force push was available as a fallback at any point."
  - "RESEARCH assumption A2's budgeted fix-up commit went unused — CI passed on the first attempt — so A2 and ADR-019's 'never run on a real runner' caveat are now stale. Flagged for Phase 7 rather than patched here: `DECISION_LOG.md` is append-only and a superseding note is a Phase 7 concern."
  - "The raw attribution grep returns 1, not 0. The single match is the filename `CLAUDE.md` in commit 0456070's subject — a file being referenced, not a trailer. Both counts are reported in the evidence rather than silently filtering to the flattering one."
  - "Three interpreters have now run the suite green (host 3.14.3 / image 3.13.15 / runner 3.13.15). The image and the runner agree exactly at 19 statements, which is the pair that matters — the image is what `docker compose up` gives an evaluator."

patterns-established:
  - "`make format` is run FIRST in the phase gate and `git diff --quiet` asserted immediately after, so the ROADMAP-named target is proven a no-op rather than a target nobody runs"
  - "Evidence files are appended to across tasks within a plan, so a single file tells the whole verification story in order"

requirements-completed: [FND-09, FND-10, DOCK-04]

# Metrics
duration: 14min
completed: 2026-09-18
---

# Phase 01 Plan 08: Phase Gate and First Real CI Run Summary

**The entire Phase 1 gate — `format`, `lint`, `typecheck`, `arch`, `test`, `docker-test`, two
`pre-commit` passes and one under a stripped environment — was observed green in a single
uninterrupted run with a clean secret and attribution audit; then the real history was pushed to
the user-supplied public repository `Xch4rt/crehana-backend-test`, where CI run 35301518310
concluded `success` on the first attempt with 3 contracts kept, 8 tests passed and 100% coverage
on Python 3.13.15, leaving the budgeted fix-up commit unused.**

## Performance

- **Duration:** 14 min
- **Started:** 2026-09-18T02:49:20Z
- **Completed:** 2026-09-18T03:04:00Z
- **Tasks:** 2 (Task 2 was a blocking human checkpoint)
- **Files modified:** 1 (`evidence/phase-gate.txt`, 394 → 512 lines)

## Accomplishments

### Task 1 — the whole gate, one sitting

- `make format` ran **first** and `git diff --quiet` exited 0 immediately afterwards: the
  ROADMAP's named target is exercised and is a proven no-op on the finished tree, not a target
  nobody runs.
- `make lint`, `make typecheck`, `make arch` and `make test` each exited 0 in the same
  uninterrupted pass. `make test`: 8 passed, 3 contracts kept, `Required test coverage of 75%
  reached. Total coverage: 100.00%` over 18 statements on the host's CPython 3.14.3.
- `make docker-test` exited 0 and reached the same gate on Python 3.13 **inside the image** —
  19 statements, 100%. This is DOCK-04 in its documented one-command form; a host with no Python
  at all produces the same result.
- `.venv/bin/pre-commit run --all-files` twice with `git diff --quiet` clean afterwards, then once
  more under `env -i HOME=… PATH=/usr/bin:/bin:/usr/local/bin`, re-confirming plan 04's
  `.venv/bin/`-qualified local hook entries resolve with no activated virtualenv — the condition a
  real `git commit` runs under.
- Spot checks no earlier plan owned end to end: `pip install --dry-run -r requirements-dev.txt`
  (FND-02), `.flake8` carrying neither a bare `ignore =` nor `exclude =` (FND-03),
  `configfile: pytest.ini` in `pytest --collect-only` (FND-05), `lint-imports` exit 0 (ARC-03),
  `## Incident Log` + a `### 2026-` entry in `AI_WORKFLOW.md` (AIW-03), `HTTPException` and
  `domain` both in `CLAUDE.md` (AIW-04), and `pre-commit` appearing in neither `ci.yml` nor the
  `Dockerfile`.
- Secret and hygiene audit all clean: no `.env` in `git ls-files` or `git log --all --name-only`,
  no case-insensitive `secret` in `docker history taskmanager`, and the attribution grep raw=1 /
  refined=0 (the one raw match is the *filename* `CLAUDE.md` in a commit subject).

### Task 2 — the first real CI run

- The checkpoint was answered with an **already-created** repository:
  `git@github.com:Xch4rt/crehana-backend-test.git`. `gh auth status` reported logged in as
  `Xch4rt` over SSH; `gh repo view --json name,visibility,isEmpty` reported
  `crehana-backend-test`, `PUBLIC`, `isEmpty: true` with no default branch.
- No `gh repo create`, no README, no fabricated "first commit". `origin` was added and the real
  `main` pushed as-is, ending at `6d73281`. `* [new branch] main -> main`, no force.
- CI run **35301518310** (<https://github.com/Xch4rt/crehana-backend-test/actions/runs/35301518310>)
  concluded **`success`** in 53s, head sha `6d73281`. All six gate steps ran as individually named
  steps — black, isort, flake8, mypy strict, import-linter, pytest — none skipped, none no-opped
  (threat T-01-43). The Postgres service container came up and health-checked even though no
  Phase 1 test touches it.
- Runner-side output, quoted verbatim into the evidence file: `Contracts: 3 kept, 0 broken.`,
  `platform linux -- Python 3.13.15, pytest-9.1.1`, `configfile: pytest.ini`,
  `TOTAL 19 0 0 0 100%`, `Required test coverage of 75% reached. Total coverage: 100.00%`,
  `8 passed in 0.71s`.
- The refined attribution grep was re-run after the push and after the evidence commit: still 0.
  That history is now public and immutable.

## Task Commits

1. **Task 1: Full phase gate run and secret audit** — `6d73281` (docs) — evidence file created,
   394 lines
2. **Task 2: Public repository push and first CI run** — `c809d70` (docs) — evidence appended,
   +118 lines
3. **Plan completion** — this SUMMARY plus the STATE/ROADMAP/REQUIREMENTS updates

No fix-up commit exists: the workflow passed on its first execution on a real runner.

## Files Created/Modified

- `.planning/phases/01-foundation-quality-gates/evidence/phase-gate.txt` — 394 → 512 lines. Task 2
  appended a `Task 2 - first real CI run` section with the preflight checks, the push output, the
  run id/URL/conclusion, the `gh run watch` step list, the runner's coverage and contract lines,
  the unused fix-up budget, and the post-push D-20 re-check.
- `.planning/phases/01-foundation-quality-gates/01-08-SUMMARY.md` — this file.

No source file, config file or workflow file was touched by this plan. Phase 1's deliverables are
byte-identical to their state at `9f1e256`.

## Decisions Made

- **The already-created repository was treated as "create-now with the creation already done."**
  The user pasted GitHub's generic quick-setup snippet (`echo "# repo" >> README.md`,
  `git init`, `git commit -m "first commit"`). Following it literally would have produced a
  one-commit history and destroyed the eight-commit trail that is this project's whole thesis. The
  snippet was ignored; `git remote add origin` + `git push -u origin main` was the entire action.
- **`isEmpty: true` was re-asserted immediately before the push.** A remote that had become
  populated between the orchestrator's check and the executor's would have meant a different
  history, and the documented response was to stop and report — never to force. The guard cost one
  read-only API call.
- **A2's fix-up budget went unused, and that is recorded rather than quietly enjoyed.** The
  research assumed the workflow would fail once on a real runner because it had never executed on
  one. It did not. `01-RESEARCH.md` assumption A2 and `DECISION_LOG.md` ADR-019 both still say the
  workflow has never run on a real runner; **that text is now stale.** Phase 7 should refresh it —
  `DECISION_LOG.md` is append-only, so a superseding note there is a Phase 7 concern and was not
  written by this plan.
- **Both attribution counts are published.** Reporting only the refined 0 would be the exact
  self-flattering evidence D-18 forbids. The evidence file states raw=1, names the commit
  (`0456070`) and explains why a filename in a subject line is not a trailer.

## Deviations from Plan

### Auto-fixed Issues

None. No bug, missing functionality or blocker was encountered in either task, and no gate needed
repair.

### Scope Adjustments

- **`gh repo create` was not run** (plan step: "create the repository with the `gh` CLI under the
  confirmed name and visibility"). The user had already created it. Creating it again was
  impossible and unnecessary; every downstream acceptance criterion — name, `PUBLIC` visibility,
  `origin` remote, successful push, green run — was still met and verified. This is a narrowing of
  the action, not of the acceptance.
- **The fallback branch of the plan (defer to Phase 7) was not taken**, so no Deferred Items row
  was added to `STATE.md`. FND-10 is satisfied by observation.

## Issues Encountered

None blocking. Two observations worth carrying:

- **The `ubuntu-latest` annotation.** The run carries one non-fatal annotation: *"The
  ubuntu-latest label will migrate to Ubuntu 26 beginning October 19, 2026."* Nothing in this
  workflow depends on the runner's OS minor version — Python comes from `setup-python@v7` and
  Postgres from a pinned `postgres:18-alpine` service — so the migration is expected to be a
  no-op. Worth a glance in Phase 7 rather than an action now.
- **`DATABASE_URL` is masked in the job log** (`***localhost:5432/taskmanager_test`). GitHub
  redacted it because the value contains the string `taskmanager:taskmanager`, which it treats as
  credential-shaped. The value is the obviously-fake CI-only one committed in `ci.yml`; nothing
  real leaked, and nothing is hidden that a reader cannot find in the workflow file. It does mean
  a future debugging session cannot read the URL back out of the log.

## Verification Results

| Check | Result |
|-------|--------|
| `gh auth status` | logged in as `Xch4rt`, protocol ssh |
| `gh repo view … --json isEmpty` (preflight) | `true` — safe to push |
| `git remote -v` | `origin` → `git@github.com:Xch4rt/crehana-backend-test.git` (fetch + push) |
| `git push -u origin main` | `* [new branch] main -> main`, no force |
| `gh repo view --json name,visibility` | `crehana-backend-test`, `PUBLIC` |
| `gh run list --limit 1` | `completed success … 35301518310 53s` |
| `gh run watch 35301518310 --exit-status` | exit 0 — 15/15 steps green |
| CI: Architecture contracts | `Contracts: 3 kept, 0 broken.` |
| CI: Tests with coverage gate | `8 passed`, `Required test coverage of 75% reached. Total coverage: 100.00%` on Python 3.13.15 |
| `git log --all --format='%B' \| grep -ciE 'co-authored-by\|claude\|generated with\|anthropic'` | 1 raw (filename `CLAUDE.md` in `0456070`'s subject) |
| …piped through `grep -v 'CLAUDE\.md'` first | **0** refined — no trailer on any branch |
| Evidence file appended and committed | `c809d70`, 512 lines |
| pre-commit on the evidence commit | twelve hooks, all Passed/Skipped, no `--no-verify` |

Task 1's full gate table (`format`/`lint`/`typecheck`/`arch`/`test`/`docker-test`/pre-commit ×3)
is captured verbatim in `evidence/phase-gate.txt` rather than restated here.

## Self-Check: PASSED

- `.planning/phases/01-foundation-quality-gates/evidence/phase-gate.txt` — present, 512 lines.
- `.planning/phases/01-foundation-quality-gates/01-08-SUMMARY.md` — present.
- Commits `6d73281` and `c809d70` — both verified in `git log`, both on `origin/main`.
- CI run 35301518310 — verified `completed` / `success` via `gh run view --json`.

## Known Stubs

None. This plan added no code and no placeholder.

## Threat Flags

None new. Every threat in the plan's register was exercised and cleared:

- **T-01-40 (secret published)** — the `.env` and `docker history` audits ran in Task 1, *before*
  the push, which is the only ordering that helps.
- **T-01-41 (attribution trailer published)** — audited before the push and re-audited after; the
  evidence commit itself carries no trailer.
- **T-01-42 (wrong account or visibility)** — name and visibility came from the user; `gh auth
  status` was checked first; `isEmpty` was re-asserted read-only.
- **T-01-43 (CI green because a step no-opped)** — the job log shows all six gates as separately
  named steps with real output (`3 kept, 0 broken`, `8 passed`, the coverage table).
- **T-01-44 (phase declared complete on gates never green at once)** — Task 1 is a single
  uninterrupted capture, and the evidence says so explicitly.

One standing note for the public repository: `ci.yml` commits an obviously-fake
`JWT_SECRET: ci-only-secret-not-a-real-credential` and a fake `DATABASE_URL`. Both are CI-only and
intentional; no repository secret is referenced anywhere in the workflow. Phase 3 and Phase 5 must
not turn either into a real credential.

## User Setup Required

None remaining. The one item this phase needed — a public GitHub repository — was supplied by the
user and is live at <https://github.com/Xch4rt/crehana-backend-test>.

## Next Phase Readiness

Phase 1 is complete. FND-09, FND-10 and DOCK-04 are satisfied by observation. What Phase 2 and
beyond must know:

- **Every push now runs CI, on every branch, with no filter.** A red gate is immediately visible
  and public. Phase 2's domain work inherits black, isort, flake8, mypy strict, import-linter and
  the 75% coverage floor as a hard precondition for merging anything.
- **The coverage floor is currently 100%, not 75%.** Every statement added from here is covered
  or the total drops. The gate only fails below 75%, but landing at, say, 80% would be a visible
  regression in a public repo. Phase 2 should keep the ratchet.
- **The image and the runner agree at 19 statements; the host venv counts 18.** When a coverage
  number is quoted in documentation, say which interpreter produced it. The image is the
  authoritative one for an evaluator.
- **`01-RESEARCH.md` assumption A2 and `DECISION_LOG.md` ADR-019 are stale.** Both state the
  workflow has never executed on a real runner. It has, once, successfully, on
  `6d7328163ebc70a926f68201a8b580c22f92ee75`. Phase 7 owns the refresh (it already owns AIW-05,
  the README badge, which will point at this same workflow). This plan deliberately did not edit
  the append-only ADR log.
- **`AI_WORKFLOW.md` gains a Phase 1 closing entry from Phase 7 or from whoever closes the phase.**
  The standing rule in `STATE.md` is that the incident log is appended to at the end of every
  phase. Phase 1's honest raw material is already captured across the 01-03 → 01-08 SUMMARYs and
  `evidence/`: RESEARCH Pitfall 2 failing to reproduce, the pre-commit bare-`entry:` failure, the
  Docker `test` stage missing `.env.example`, the 368 MB vs 285 MB image size, and now A2's
  fix-up budget going unused.
- **The README badge (AIW-05) has a live target.** `https://github.com/Xch4rt/crehana-backend-test/actions/workflows/ci.yml/badge.svg`
  will render green from now on.
