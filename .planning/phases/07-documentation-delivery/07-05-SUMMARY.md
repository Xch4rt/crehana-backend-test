---
phase: 07-documentation-delivery
plan: 05
subsystem: rehearsal-and-delivery
tags: [dock-05, aiw-05, rehearsal, push, ci, delivery]

requires:
  - phase: 07-documentation-delivery
    provides: "07-04 — README.md with its rehearsal:begin/end region and the documentation gate"
  - phase: 08-web-ui
    provides: "Phase 8 ran while this plan was paused at task 4, so the UI is part of the delivered commit"
provides:
  - "scripts/clean-clone-rehearsal.sh + `make rehearse` — a fresh clone, a --no-cache build, and the README's own fenced blocks executed in the clone"
  - "tests/unit/test_clean_clone_rehearsal.py — the script's guards, each driven red first"
  - "ADR-103 (the rehearsal) and ADR-104 (four sentences that credited the brief with words it does not contain)"
  - "The public repository at https://github.com/Xch4rt/crehana-backend-test, CI green on the delivered commit 7b7d970"
affects: []

key-files:
  created:
    - scripts/clean-clone-rehearsal.sh
    - tests/unit/test_clean_clone_rehearsal.py
  modified:
    - Makefile
    - README.md
    - DECISION_LOG.md
    - AI_WORKFLOW.md
    - CLAUDE.md
    - .planning/REQUIREMENTS.md
---

# 07-05 — prove the documents are true, then deliver

**Result:** delivered. The repository is public, both CI jobs are green on `7b7d970`, the developer
verified the rendered pages, and the developer sent the delivery email.

## Tasks

| Task | Commit(s) | Result |
|------|-----------|--------|
| 1 — `make rehearse` | `126b5c8` | POSIX sh, `trap cleanup EXIT` plus `HUP INT QUIT TERM`, its own compose project (`crehana-rehearsal`), 7 unit tests, three guards driven red first |
| 2 — gaps the rehearsal found | `6c73ca5`, `8bb7bd8` | four package-relative paths in the README's evidence map; one false line in the script's own report |
| 3 — ADR-103, incident entry, DOCK-05 | `a110bba` | the 52nd dated incident entry, with one marked CI-coverage placeholder |
| 4 — approve the push (human) | — | approved on 2026-09-20 after the figures were re-measured: 335 commits, 248 `.planning/` files, 0 attribution trailers, fast-forward |
| 5 — push, CI, AIW-05 | `7b7d970` | `f879894..30435c9` then `30435c9..7b7d970`, both fast-forward; runs 35490072118 and 35490320069, both jobs `success` on the first attempt |
| 6 — badge, diagrams, trail (human) | — | developer: badge green, all three Mermaid diagrams render, `.planning/` browsable |
| 7 — delivery email (human) | — | developer: sent |

## What happened between task 3 and task 4

The plan was paused at its push checkpoint for longer than it was written to be, and three things
landed in the gap, all before anything was published:

- **An audit against the real PDF** (`da125c9`). Every brief use case was exercised against the live
  API (30/30) and every sentence that attributes something to the brief was read against it. Four
  overstated it (ADR-010, ADR-018, ADR-066, ADR-097); ADR-104 corrects them by id and the README's
  409 sentence was fixed in the same commit.
- **Phase 8, the web UI**, by user decision and against the AI's recommendation (ADR-105..108).
- **Three code-review fixes** to the frontend (`d48e20b`, `20b6b44`, `0f3e364`).

The plan file's "289+ commits" was therefore stale; the figure shown to the developer at approval was
the measured 335, and the plan file was not edited.

## The CI leg of D-11

Read from run 35490072118's log, not predicted: **1140 passed, 100.00% over 1844 statements** — the
container's number to the statement (both CPython 3.13). The host's 1690 is the outlier (3.14).
06-04's predicted 1796 matched none of the three. No fix-up commit was needed; ADR-019's budgeted
one was never spent.

## Deviations

1. Static document checks run before the `--no-cache` build in the rehearsal, not after (ADR-103).
2. Five malformed-region cases tested, not four.
3. `.planning/ROADMAP.md` was left to the orchestrator during tasks 1-3.
4. The plan said the executor must not draft the delivery email; the developer later asked for help
   wording it and wrote and sent it themselves. Nothing was sent by tooling.
5. `gsd-sdk` state handlers were never called in this phase — they regress `STATE.md`; every state
   edit was made by hand and diffed.

## Self-Check: PASSED

`HEAD` == `origin/main` at delivery (`7b7d970`); CI badge `passing`; REQUIREMENTS 69/69 plus UI-01..08.
