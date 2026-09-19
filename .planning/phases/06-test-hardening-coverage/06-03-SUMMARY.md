---
phase: 06-test-hardening-coverage
plan: 03
subsystem: test-gates
tags: [mutation-spot-check, break-check, sc-4, d-08, d-09, d-10, d-14, shell-script, trap-safety, ai-workflow]

# Dependency graph
requires:
  - phase: 06-test-hardening-coverage
    provides: "06-RESEARCH.md — the five breaks measured end to end against tree cfa6f8d, and the six required behaviours of the script"
  - phase: 06-test-hardening-coverage
    provides: "06-01 — the two D-14 fixes (the auth caller seeded, the list-deletion concurrency case), which are what makes breaks 4 and 5 reach behaviour"
  - phase: 01-foundation-quality-gates
    provides: "scripts/init-env.sh and tests/unit/test_env_bootstrap.py — the POSIX-sh / no-`sed -i` precedent and the script-as-a-program test shape"
provides:
  - "scripts/break-check.sh — five mutations applied, run, asserted red and restored, exiting non-zero on any survivor"
  - "make break-check — roadmap SC-4 behind one command, in no gate path"
  - "tests/unit/test_break_check.py — the script's three safety properties, each falsified once"
  - "AI_WORKFLOW.md — the dated incident entry for the whole episode, with both survivals and their fixes"
affects: [06-04, 07-documentation-delivery]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A mutating diagnostic that owns its own safety: refuses a dirty tree, restores through a trap installed before the first mutation, and restores only the files it touched"
    - "A mutation guarded by `assert old in s`, so a drifted source line fails loudly instead of reporting a green break"
    - "A per-break named test selection rather than the whole suite, so the report shows which kind of test caught the defect"
    - "One documented environment-variable seam (`BREAK_CHECK_PYTEST`) so the script can be driven as a program in a throwaway repository"

key-files:
  created:
    - scripts/break-check.sh
    - tests/unit/test_break_check.py
  modified:
    - Makefile
    - AI_WORKFLOW.md

key-decisions:
  - "The trap restores exactly the files the script has mutated so far (a `MUTATED` accumulator), not the `git checkout -- src/` the plan and 06-RESEARCH specify: a blanket checkout can destroy uncommitted work the script never touched, and 06-02 produced a live example of precisely that. The dirty-tree refusal makes the blanket form *usually* harmless, which is not the same as safe"
  - "`BREAK_CHECK_PYTEST` is the one seam, and it exists for the unit test: in a throwaway repository there is no `.venv`, and running the real suite there would defeat the point of a unit test. The header says so rather than leaving a knob unexplained"
  - "The trap test's stub interrupts its own caller (`kill -TERM \"$PPID\"`) instead of the test polling for the mutation window and racing to signal it: a poll that misses the window passes for the wrong reason, since the script exits non-zero and clean on the next break's precondition anyway"
  - "The mutated path the unit test plants is read out of the script with a regex rather than restated, so a reordered or repointed break table cannot leave the tests exercising a path the script no longer touches"
  - "Break 3's literal occurs twice (the assignee clause of `visible_task` and of `owned_task`) and both are mutated on purpose: one literal, two guards, and a suite that only ever asked from the owner's side would not notice either"
  - "Only `AI_WORKFLOW.md` records the episode — no evidence file, no transcript (D-15). The entry quotes the `make break-check` output verbatim with its exit code, which is what SC-4 asks for"

patterns-established:
  - "Falsify the safety, not only the finding: each of the script's three safety properties was driven red by removing the single line that provides it"
  - "Report counts in both directions against the by-hand baseline, and say why each direction moved"

requirements-completed: []

# Metrics
duration: 22min
completed: 2026-09-19
---

# Phase 6 Plan 03: The Deliberate-Break Spot Check Summary

**`make break-check` breaks `src/` on purpose five times in thirteen seconds, proves each defect
turns the suite red, restores every file and exits non-zero if any break survives — and
`AI_WORKFLOW.md` now records the two breaks that originally did not turn it red, including the one
that had been reporting token expiry as enforced while nothing in the API checked it.**

## Performance

- **Duration:** ~22 min
- **Tasks:** 4 of 4
- **Files modified:** 4 (2 created, 2 modified)
- **Suite:** 1066 → **1069 passed**, coverage **100.00 %** (gate 75 %)
- **`make break-check`:** 5 breaks, 5 red, exit 0, ~13 s

## Task Commits

| Task | Name                                          | Commit    | Files                              |
| ---- | --------------------------------------------- | --------- | ---------------------------------- |
| 1    | The script and the `make break-check` target  | `03fce00` | scripts/break-check.sh, Makefile   |
| 2    | The script driven as a program                | `0741613` | tests/unit/test_break_check.py     |
| 3    | The incident entry (D-10, D-14)               | `e6ac2d0` | AI_WORKFLOW.md                     |
| 4    | Close the plan                                | (this)    | 06-03-SUMMARY.md, STATE.md, ROADMAP.md |

## The five breaks: measured, against the baseline

Baseline is the by-hand measurement against tree `cfa6f8d`, which ran the **whole suite** per
break. The script runs a **named selection** per break, which is why the first three are lower —
and breaks 4 and 5 are higher, which is plan 06-01's two fixes showing up.

| # | Break | Baseline | Now | Reaches behaviour? |
|---|-------|----------|-----|--------------------|
| 1 | completion percentage inverted | 17 | **7** | yes — 4 HTTP tests in `test_task_lists.py` / `test_tasks.py` |
| 2 | `completed -> pending` made legal | 6 | **5** | yes — the 409 HTTP case and the stale-writer concurrency case |
| 3 | assignee comparison inverted (both guards) | 33 | **30** | yes — 12 permission-matrix rows and 9 assignment tests |
| 4 | `"verify_exp": False` in the decode options | 3, **none over HTTP** | **5** | yes, now — `test_auth.py::[an_expired_token]` and the shared-body test |
| 5 | list-deletion lock dropped | 1, a road pin | **2** | yes, now — `test_concurrent_writes.py`'s deletion case |

Every break reddens at least one test that is not a fakes-based mirror of the implementation, which
is the property D-08 actually cares about. The two "yes, now" rows are the two D-14 findings: before
06-01 they were a unit-only catch and a road-pin-only catch respectively.

## The script's safety, and the three falsifications

This is the only tool in the repository that writes to `src/` on purpose, so the safety is the part
that was tested rather than assumed. `tests/unit/test_break_check.py` builds a git repository in
`tmp_path`, plants a copy of the first file the script mutates at the path the script expects, and
stands a shell stub in for pytest. All three legs run in 0.4 s and cannot reach the real `src/`.

| Property | Falsified by | Observed red |
| --- | --- | --- |
| A dirty `src/` is refused before anything runs, and the uncommitted edit survives | deleting the `assert_src_is_clean` call | the stub's marker file existed — it had run the tests on a dirty tree |
| A run terminated mid-mutation restores the file | deleting `trap on_signal INT TERM` | `assert -15 == 143` — the shell was killed and the mutation stayed on disk |
| A vanished literal is loud, not a green break | deleting the `assert old in source` precondition | the stub ran, so the script would have reported a passing selection as a survived break |

Two further checks were run by hand against the real tree and are not automated (they are the
script's own subject matter): editing one file under `src/` makes `make break-check` exit 1 on the
refusal before mutating anything, and sending `TERM` to a real run mid-break-1 exited 143 with
`git status --porcelain -- src/` empty and break 2 never started.

## Deviations from Plan

**1. [Rule 2 — the plan's restore mechanism is unsafe in the one case that matters] the trap restores only what it touched**
- **Found during:** Task 1
- **Issue:** the plan and `06-RESEARCH.md` both specify `trap 'git checkout -- src/' EXIT INT TERM`.
  A blanket checkout of `src/` can destroy uncommitted work the script never touched; 06-02 produced
  a live instance of exactly that failure. The dirty-tree refusal makes it *usually* harmless — but
  "usually" is not the property a tool that writes to your source tree should have.
- **Fix:** a `MUTATED` accumulator, appended to before each write and checked out file by file. The
  trap is still one line, still installed before the first mutation, and the restore-on-interrupt
  test is red without it.
- **Commit:** `03fce00`

**2. [Rule 3 — the script could not otherwise be unit-tested] one documented seam, `BREAK_CHECK_PYTEST`**
- **Found during:** Task 1
- **Issue:** the plan asks for the script to be driven as a program in a throwaway repository, where
  `.venv/bin/pytest` does not exist and where running the real suite would make a unit test take a
  quarter of a minute and need PostgreSQL.
- **Fix:** `PYTEST=${BREAK_CHECK_PYTEST:-.venv/bin/pytest}`, named in the header as existing for
  `tests/unit/test_break_check.py` and for nothing else. The default path is still checked for
  executability with `make install` as the remedy.
- **Commit:** `03fce00`

**3. [Rule 1 — a test that can pass by missing its own window] the stub interrupts its caller**
- **Found during:** Task 2
- **Issue:** the obvious way to test the trap is to poll for the mutation and then signal the
  process. If the poll misses the window the script proceeds to the next break, fails its
  precondition, restores and exits non-zero — so the test passes without ever having reached the
  trap.
- **Fix:** the stub records what the mutation left on disk and then `kill -TERM "$PPID"`. The test
  asserts the recorded content differs from the original (the mutation really happened), that the
  exit status is the handler's own `143` rather than a negative signal status, and that the file is
  byte-identical afterwards.
- **Commit:** `0741613`

## For plan 04: the ADR and `CLAUDE.md` bullet this plan owes

One rule, worth an ADR of its own (next free number was 085 as of 06-01; 06-02 added none):

**The deliberate-break spot check.** `make break-check` mutates `src/` and is therefore held to
three rules that no other tool here needs: it refuses to start unless `git status --porcelain --
src/` is empty; it restores through a trap installed before the first mutation, and restores only
the files it touched — never a blanket `git checkout -- src/`, `git stash` or `git reset --hard`;
and every mutation carries an `assert old in s` precondition, so a drifted source line fails loudly
instead of reporting a defect nobody introduced. It is deliberately in neither `make test`,
`.pre-commit-config.yaml` nor `.github/workflows/ci.yml` (D-09), so ADR-015's "a new gate goes in
two places" rule does not apply — this is not a gate. Enforced by
`tests/unit/test_break_check.py`, which drives the script in a throwaway repository and whose three
legs were each driven red by deleting the single line that provides the property.

Carried forward from 06-01, still owed by 06-04: **a gate is not trusted until it has been driven
red**, and **a gate must never be satisfiable by its own non-vacuity guard**.

## Verification Results

```
make lint       -> black 186 files unchanged, isort clean, flake8 clean
make typecheck  -> Success: no issues found in 186 source files
make arch       -> Contracts: 4 kept, 0 broken.
make test       -> 1069 passed, TOTAL 1643 stmts / 154 branches, 100%
make break-check-> All 5 breaks turned the suite red. src/ is back as it was. (exit 0, ~13s)
```

- `git status --porcelain -- src/` empty after every run, including the two hand-run safety checks
  and the three falsifications.
- `git status --porcelain` shows no `coverage.xml` change caused by a break-check run
  (`--no-cov -p no:cacheprovider`).
- `grep -c "break-check\|break_check" .pre-commit-config.yaml .github/workflows/ci.yml` → 0 and 0.
- No commit in this plan carries a `Co-Authored-By` or `Generated with` line.

## Ceremony

Minimal, per D-15: one SUMMARY, no evidence file, no transcript. The `AI_WORKFLOW.md` entry *is*
the evidence SC-4 asks for, and it quotes the run verbatim with its exit code. Nothing was written
to `DECISION_LOG.md` or `CLAUDE.md` — plan 04 owns those.

## Self-Check: PASSED

- `scripts/break-check.sh` — FOUND
- `tests/unit/test_break_check.py` — FOUND
- `Makefile` `break-check` target and `.PHONY` entry — FOUND
- `AI_WORKFLOW.md` entry, `grep -c verify_exp` → 1 — FOUND
- commits `03fce00`, `0741613`, `e6ac2d0` — all FOUND in `git log`
