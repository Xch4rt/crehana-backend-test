---
phase: 07-documentation-delivery
plan: 03
subsystem: documentation-ai-workflow
tags: [aiw-01, aiw-02, mermaid, human-ai-split, commit-references, honest-limits]

# Dependency graph
requires:
  - phase: 07-documentation-delivery
    provides: "07-01 — the 69 published error legs and the DOC-04 gate the Phase 7 block records"
  - phase: 07-documentation-delivery
    provides: "07-02 — ADR-097..101, the ids the Phase 7 block cites"
  - phase: 05-auth-assignment-notifications
    provides: "05-VERIFICATION.md — the forged-token round trip the sequence diagram draws"
  - phase: 06-test-hardening-coverage
    provides: "06-REVIEW.md — the two criticals and the seven warnings left open"
provides:
  - "AI_WORKFLOW.md §How This Project Was Built — three Mermaid diagrams of the real workflow"
  - "AI_WORKFLOW.md §Human-Decided vs AI-Delegated — Phases 5, 6 and 7 blocks, 35 resolving commit hashes"
  - "AI_WORKFLOW.md §What I Did Not Do — four groups, every item carrying a resolving id"
affects: [07-04-readme, 07-05-rehearsal]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A measured number gets an anchor in the sentence that states it, so it stays true as the suite grows"
    - "A commit hash is attached to the claim hardest to believe without one, inline, never in a table"

key-files:
  created: []
  modified:
    - AI_WORKFLOW.md
    - .planning/REQUIREMENTS.md
    - .planning/ROADMAP.md
    - .planning/STATE.md

key-decisions:
  - "The pipeline diagram is drawn uneven because the process was uneven — no discussion log for Phases 1 and 7, verification returning gaps_found for Phases 5 and 6, a code review that found two criticals. An idealised loop would have been easier to draw and would have been the one thing this document exists not to do"
  - "The gate diagram says pre-commit runs no tests. CLAUDE.md's prose reads as if the hook set enforced all four gates; the config was read, and its hooks are the formatters, flake8, mypy and lint-imports. make test being green before a commit is a rule enforced by hand, by the Docker test stage and by CI"
  - "Nine architecture gates, not the research's eight: 07-01 added tests/architecture/test_openapi_completeness.py after 07-RESEARCH was written. Counted from the directory, not copied from the document"
  - "The suite number is stated with an anchor — 'at the close of this plan, 1,115 tests at 100.00% over 1,690 statements' — because 07-04 adds tests and an unanchored count would be false within the same phase"
  - "The commit total is deliberately absent. It changes with every commit including this plan's, and a documentation-claims gate that pinned it would be red on its own commit; the checkable claims kept instead are 'no attribution trailer in any commit' and the per-claim hashes"
  - "Thirty-five hashes rather than the seven the plan asked for. Every phase-1-to-4 claim that already named an ADR got the commit beside it, since finding them cost one git log per scope and the alternative is a reader taking the ADR's word for what shipped"

metrics:
  duration: ~40 min
  completed: 2026-09-19
  tasks: 3
  commits: 3
  tests-added: 0
  suite: 1115 passed, 100% coverage over 1690 statements
---

# Phase 7 Plan 03: The AI Workflow Document Is Finished Summary

`AI_WORKFLOW.md` now draws the real workflow in three diagrams, says who decided what across all
seven phases with a commit beside the claims hardest to believe, and publishes its own gate
weaknesses — with the 51 incident entries byte-identical.

## What Was Built

**Three Mermaid diagrams** under `## How This Project Was Built`, replacing a placeholder.

1. `flowchart TD` — the brief to four parallel research agents, their disagreement settled by the
   human on the record (ADR-053), 69 requirements, seven phases, and the per-phase loop drawn with
   its real edges: verification returning `gaps_found` for Phases 5 and 6, and the code review's
   two criticals after Phase 6, both looping back to another plan.
2. `flowchart LR` — the gate set, with the two annotations that make it honest: pre-commit is
   host-only and its hooks are `.venv/bin/`-qualified, so CI and the Docker `test` stage run the
   six tools as named steps instead (ADR-015); and `make break-check` sits outside every gate path
   by D-09, drawn as a dashed edge.
3. `sequenceDiagram` — the Phase 5 round trip end to end: a token forged offline with the
   placeholder from `.env.example` returning another account's profile with 200, plan 05-17
   closing it (commits `64b2e6d`, `4d94514`, ADR-084), and the same forgery answering 401 on
   re-verification.

All three are restricted to the three permitted diagram types with every label double-quoted, pure
ASCII, no icons, no styling. Rendering is owed to 07-05's human checkpoint — the file says so.

**Phase 5, 6 and 7 human/AI blocks**, in the shape the first four already had, replacing the
promissory note that closed the section. Phase 5 records the visibility matrix, the assignment
door, the post-commit invitation, the two conceded properties and the placeholder refusal; Phase 6
records totality-by-gate, the re-read rule, `break-check` as a script and not a gate, the coverage
pin, and the two criticals its own review found; Phase 7 records the four decisions the research
resolved at planning time, and states plainly that the dated Phase 7 incident entry is appended at
the end of the phase, per the standing rule.

**Thirty-five commit hashes**, every one resolved with `git cat-file -e` rather than eyeballed,
attached inline to the claims a reader would most want to check: the placeholder refusal
(`64b2e6d`, `4d94514`), the coverage configuration pin (`03e8c3a`), the two criticals (`8a0439f`,
`142d64c`), the marker partition (`52ed708`), the 69 error legs (`4963218`).

**`## What I Did Not Do`**, in four groups: the v1 scope left out (API-01, API-02, API-03,
AUTH-07, AUTH-08, integer priorities), the three security properties conceded on purpose with the
production answer for each (ADR-066, ADR-067, ADR-068), the seven gate-robustness warnings the
Phase 6 review left open (WR-03, WR-05, WR-06, WR-07, WR-08, WR-10, WR-11), and the shortcuts
rejected — `# pragma: no cover`, `create_all()`, SQLModel, ruff, a compose override, testcontainers
and `--no-verify`. It closes on a property rather than a promise: the only signing key this
repository publishes is the placeholder, and the application refuses to boot with it.

## Verification

| Check | Result |
|---|---|
| `make lint`, `make typecheck`, `make arch`, `make test` | green — 1115 passed, 100.00% over 1690 statements, 4 contracts kept |
| `grep -c '^```mermaid'` | 3, fences balanced |
| `To be completed in Phase 7` | 0 occurrences anywhere in the file |
| Phases 1..7 | each has `**Decided by the human**` and `**Delegated to AI**` — 7 and 7 |
| 35 short hashes | all resolve (`git cat-file -e <hash>^{commit}`) |
| 72 `ADR-NNN` ids cited in the file | all resolve to a `## ADR-NNN:` heading in `DECISION_LOG.md` |
| `## Incident Log` | byte-identical to its pre-plan state, 114,727 bytes both sides |
| `## Verification Practices` | byte-identical |
| Diagrams | pure ASCII; no `fa:`, `click`, `style` or `classDef` |
| Commit messages | no `Co-Authored-By`, no "Generated with" |

## Deviations from Plan

**1. [Rule 2 — accuracy] The gate diagram contradicts a sentence in `CLAUDE.md`, on purpose.**
`CLAUDE.md` reads "pre-commit enforces the same set locally on every `git commit`", which a reader
takes to include `make test`. `.pre-commit-config.yaml` was read: its hooks are the hygiene set,
isort, black, flake8, mypy and `lint-imports` — no pytest. The diagram and its caveat say so. The
`CLAUDE.md` sentence is not wrong about the *rule* (all four gates green before any commit); it is
imprecise about *who enforces it*. Not edited here — `CLAUDE.md` is 07-04's file this phase.

**2. [Rule 1 — stale number] Nine architecture gates, not eight.** 07-RESEARCH says eight;
07-01 added a ninth (`tests/architecture/test_openapi_completeness.py`) after the research was
written. Counted from the directory.

**3. Thirty-five hashes rather than seven.** The plan asks for "at least one claim per phase";
every existing claim that already carried an ADR id got its commit too, because the cost was one
`git log --oneline --grep` per scope.

**4. Two claims softened after checking them.** "Every list route orders by `created_at, id`" was
written, then reduced to "in a fixed total order" because only three of the routes were verified.
"`--no-verify`: never used" became "forbidden by `CLAUDE.md`", with the compromise that was paid
instead (the RED step captured to an evidence file) named and dated — an absolute about what never
happened is not checkable, and this document's own rule is that an unverifiable sentence costs more
than a missing one.

**5. No commit-total figure.** 07-RESEARCH's "332 commits" is already stale and any replacement
goes stale on the next commit, including this plan's own. The stable claims were kept instead.

## For the Next Plans

**07-04 (README, `test_documentation_claims.py`, `Dockerfile` COPY):**

- Claims in `AI_WORKFLOW.md` a gate can pin cheaply and safely: at least three ```` ```mermaid ````
  blocks with balanced fences; zero occurrences of `To be completed in Phase 7`; the seven strings
  `What is already true of Phase N:` for N in 1..7, each followed by both bold headings; every
  `ADR-NNN` in the file resolving to a `^## ADR-NNN:` heading; every seven-hex-character token
  matching `\b[0-9a-f]{7}\b` in the human/AI section resolving via `git cat-file -e`. The last one
  needs a real `git` in the container — the `Dockerfile` `test` stage already installs it for
  `tests/unit/test_break_check.py`.
- **Do not pin the suite count or the statement count from this file.** The one occurrence, "at the
  close of this plan the suite is 1,115 tests at 100.00% over 1,690 statements", is deliberately
  anchored to this plan and will be false of the live suite the moment 07-04 adds a test. Pin the
  README's numbers against the run instead.
- `## Incident Log` must stay byte-identical: the totality of dated entries is 51 until 07-05
  appends the Phase 7 one. A gate that counts `^### 20` headings under that section would be a
  cheap tamper check.
- The README's security-note section owes the same three sentences as this file's second group —
  ADR-066, ADR-067 and ADR-068 each say in their Consequences that Phase 7's README owes them.

**07-05 (clean-clone rehearsal, the dated Phase 7 entry):**

- The Mermaid rendering checkpoint is owed and the file says so in its own text. Three diagrams,
  at `## How This Project Was Built`.
- The dated Phase 7 incident entry is still unwritten and is 07-05's, per the standing rule. It
  owes the two entries 06-04 handed forward — `make docker-test` broken for two phases unnoticed,
  and the CI leg of D-11's three-way coverage agreement, whose number can only be read from a real
  run — plus, if they are judged worth keeping, this phase's own two: 07-01's shallow-copy
  `$ref` (the plan prescribed `dict(PROBLEM_REF)`, which would have left one mutable object shared
  across 69 legs) and 07-02's discovery that a tag description shipped by 07-01 claimed the API
  publishes no email while ADR-068 says it does.
- Everything this plan states about Phase 7's decisions is in the present tense and stays true
  after the push except one sentence: the file says rendering "is checked by a human on GitHub
  after the push". If 07-05's checkpoint finds a diagram that does not render, that sentence is
  the one to amend, along with the diagram.

## Self-Check: PASSED

- `AI_WORKFLOW.md` — FOUND, 2,238 lines, 51 dated incident entries (`grep -c '^### 20'`)
- `.planning/phases/07-documentation-delivery/07-03-SUMMARY.md` — FOUND
- Commit `1d3e9eb` — FOUND (`docs(07-03): draw the real workflow in three diagrams`)
- Commit `cbd577a` — FOUND (`docs(07-03): the human/AI split for Phases 5, 6 and 7, with commit references`)
- Commit `b074183` — FOUND (`docs(07-03): what was left out, and where this project's own gates are weak`)
