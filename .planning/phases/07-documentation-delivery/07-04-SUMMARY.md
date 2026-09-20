---
phase: 07-documentation-delivery
plan: 04
subsystem: documentation-readme
tags: [doc-01, doc-02, readme, documentation-gate, dockerfile-copy, rehearsal-markers]

# Dependency graph
requires:
  - phase: 07-documentation-delivery
    provides: "07-01 — OPENAPI_TAGS and the 19 published operations the endpoint table is gated against"
  - phase: 07-documentation-delivery
    provides: "07-02 — ADR-097/098 and the §Start here ambiguity map the README's §Decisions mirrors"
  - phase: 07-documentation-delivery
    provides: "07-03 — AI_WORKFLOW.md's diagrams, human/AI section and §What I Did Not Do"
provides:
  - "README.md — the evaluator's entry point, ten sections, with one rehearsal:begin/end pair"
  - "tests/architecture/test_documentation_claims.py — 13 tests over README, DECISION_LOG, AI_WORKFLOW, Makefile"
  - "Dockerfile test stage — the COPY line for the four root documents"
  - "ADR-102 — the documentation-honesty gate and the root-file COPY rule"
  - "CLAUDE.md §Quality gates — the COPY rule, the gated-README rule, and the corrected pre-commit sentence"
affects: [07-05-rehearsal-and-delivery]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A README claim is kept true by set equality against the published artifact, never by generation"
    - "A gate that reads a repository-root file adds its Dockerfile COPY line in the same commit; its verification is make docker-test"
    - "Read root documents inside the tests, not at import time, so a missing file is a named failure rather than a collection error"
    - "Scan Markdown code spans and fenced blocks for commands, never prose"

key-files:
  created:
    - README.md
    - tests/architecture/test_documentation_claims.py
  modified:
    - Dockerfile
    - DECISION_LOG.md
    - CLAUDE.md

key-decisions:
  - "The endpoint table is written by hand and gated, never generated. A generated table agrees with app.openapi() by construction, so the one failure worth catching - a human wrote a row that is not true - becomes inexpressible"
  - "The quickstart uses curl, grep and cut and nothing else, so the stated prerequisites stay true. 07-RESEARCH's python3 one-liner for the token would have added an undeclared prerequisite to the one file that must not have any"
  - "The make-target scan is restricted to code spans and fenced blocks, with the cost named in the docstring and in ADR-102: `make rehearse` written in prose would escape. The alternative fires on 'make sure' and is how a gate gets disabled"
  - "The AI_WORKFLOW commit hashes are deliberately not re-resolved. The test stage installs git but receives no .git, so the check would skip in the container - the WR-06 shape"
  - "Two numeric claims the README makes (102 ADRs, 4 contracts) are re-derived from the files on every run instead of being avoided or frozen. The pin went red on this plan's own third commit, which is the behaviour that makes a count in prose safe to write"
  - "The marker guard asserts exactly one pair, closing the WR-05 shape rather than repeating it"

metrics:
  duration: ~45 min
  completed: 2026-09-20
  tasks: 3
  commits: 3
  tests-added: 13
  suite: 1128 passed, 100% coverage (1690 statements on the host, 1844 in the container)
---

# Phase 7 Plan 04: The README, and the Gate That Keeps It True Summary

`README.md` now answers "can I run this?", "do the tests pass?" and "did they do what the brief
asked?" in its first three screens — with every command in it executed against a stack rebuilt from
an empty volume, and every checkable claim held true by a pytest gate that is green in the
container as well as on the host.

## What Was Built

**`README.md`** (commit `f5a9ffa`) — ten sections, in the order a reader with five minutes needs
them. Title, one paragraph and the CI badge; **Run it** (`make env`, `make up`, `/docs`, with
Docker and `make` as the honest prerequisite list and the foreground warning); **Run the tests**
(`make docker-test` as the zero-host-setup path, the host path named with its ADR-029 caveat);
a **2-minute quickstart** ending on the filtered listing that returns one item while reporting
`total_tasks: 2`, `completed_tasks: 1`, `completion_percentage: 50.0`, plus the two error bodies
and the simulated invitation; the **19-operation endpoint table**; a **requirement-to-evidence
map** over all 23 `[PDF x.y]` keys cited in `REQUIREMENTS.md`, every proof cell a command or a test
path, with the sentence that the brief itself is not redistributed here; **Local development**;
**Architecture in one screen**; **Decisions and AI workflow**; and a **pending** section naming the
v2 scope, the three conceded security properties (ADR-066, ADR-067, ADR-068) and the seven open
gate-robustness warnings.

The run/test/quickstart command blocks sit inside a single `<!-- rehearsal:begin -->` …
`<!-- rehearsal:end -->` pair, so plan 07-05's script executes the README rather than a transcript
of it. `make rehearse` appears nowhere — 07-05 adds the target and the rows that name it together.

**`tests/architecture/test_documentation_claims.py`** (commit `dda7476`) — 13 tests,
`pytestmark = pytest.mark.unit`. Endpoint set equality against `create_app(...).openapi()` as two
separate tests so the two failures name themselves; every `ADR-NNN` cited in `README.md` or
`AI_WORKFLOW.md` resolved against the log's headings; `AMBIGUITY_ADRS`, the brief's five
ambiguities pinned as a hand-written table; every `make <target>` in a code context checked against
`.PHONY`; a check that the rehearsal region names only Docker-path targets; the two counts the
README quotes re-derived from the files; the marker pair asserted as **exactly** one; three
`AI_WORKFLOW` completeness checks (mermaid floor, no `To be completed in Phase 7`, every phase 1..7
named inside the located section); and a non-vacuity test that fails rather than skips.

**`Dockerfile`** (same commit) — `COPY README.md DECISION_LOG.md AI_WORKFLOW.md Makefile ./` in the
`test` stage, with the comment that records why the line and the gate belong in the same commit.
The `runtime` stage is untouched.

**`DECISION_LOG.md` / `CLAUDE.md`** (commit `fcd8579`) — ADR-102, and two new `## Project Rules`
bullets under §Quality gates: the root-file `COPY` rule with the four documents named, and the
gated-README rule. Plus the correction 07-03 handed over.

## Verification

- `make lint`, `make typecheck`, `make arch`, `make test` — all green. **1128 passed, 100.00%
  coverage over 1690 statements** on the host.
- **`make docker-test` — green: 1128 passed, 100.00% over 1844 statements.** Run four times across
  this plan, including once with the `COPY` line removed on purpose.
- The README's own blocks were extracted from the file and executed as one shell script against a
  stack rebuilt with `docker compose down -v`. Every documented response matched, including the
  money shot and both error bodies.

**Every new check was driven red first**, each reverted by undoing exactly that edit (no
`git checkout --`, no `git stash`, no `git reset --hard`); `git diff --quiet README.md` was
asserted after each revert:

| Planted | Test that went red | Message |
|---------|--------------------|---------|
| A row deleted from the endpoint table | `test_the_endpoint_table_omits_no_route_that_does_exist` | `[('DELETE', '/api/v1/task-lists/{list_id}')]` |
| A row for a route that does not exist | `test_the_endpoint_table_publishes_no_route_that_does_not_exist` | `[('GET', '/api/v1/teams')]` |
| `make docker-tests` | `test_every_make_target_the_readme_names_exists` | `['docker-tests']`, with the `.PHONY` list |
| A second `<!-- rehearsal:begin -->` | `test_the_rehearsal_markers_are_one_well_formed_pair` | `assert (2, 1) == (1, 1)` |
| `ADR-999` cited | `test_every_cited_adr_resolves_to_an_entry` | `{'README.md': ['ADR-999']}` |
| `README.md` emptied | `test_the_scan_is_not_vacuous` | **failed**, did not skip |
| The Dockerfile `COPY` line removed | all 13, in the container | `make docker-test`: 13 failed / 1115 passed |

That last row is the one the plan called for. `make test` stayed green throughout it — the host has
the whole tree — which is precisely why the verification command for a gate like this is
`make docker-test`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] The README's ADR count had to change in task 3's commit**

- **Found during:** Task 3
- **Issue:** Task 1 wrote "101 ADRs" and gated it against `DECISION_LOG.md`'s headings. Appending
  ADR-102 made that test red — correctly.
- **Fix:** `README.md` bumped to "102 ADRs" inside the same commit as the ADR. `README.md` was not
  in task 3's declared file list.
- **Files modified:** `README.md`
- **Commit:** `fcd8579`

**2. [Rule 2 - Missing check] Two numeric claims gated beyond the plan's list**

- **Found during:** Task 2
- **Issue:** The plan's gate list did not cover the two counts the README states (the ADRs, the
  import-linter contracts). A count in prose is a number that was true once, and the project
  overrides forbid hard-coding one that can go stale.
- **Fix:** Two extra tests re-derive both from `DECISION_LOG.md` and `.importlinter`. Deviation #1
  is that check working.
- **Commit:** `dda7476`

**3. [Rule 2 - Missing check] A guard that the rehearsal region needs no virtualenv**

- **Found during:** Task 2
- **Issue:** The plan states as a mechanic that the region must name no `make` target requiring
  `.venv`, but listed no test for it — so the constraint would have been a comment.
- **Fix:** `test_the_rehearsal_region_needs_no_virtualenv`, whitelisting `env`, `up`, `down`,
  `docker-test`.
- **Commit:** `dda7476`

### Judgement calls, recorded rather than silently taken

- **The host test path's commands live in §Local development, not §Run the tests.** The plan asks
  for both paths in section 3 *and* for the host path's commands outside the markers, and the
  markers must wrap sections 2–4. Section 3 names the host path in prose with its ADR-029 caveat
  and points at section 7, where the fenced block sits — outside the markers. Both instructions are
  satisfied; neither is satisfied by putting a `.venv` command inside the region.
- **The quickstart extracts ids with `grep -o … | cut`, not `python3 -c`.** 07-RESEARCH's captured
  session used a Python one-liner for the bearer token. That would add an undeclared prerequisite
  to the one file whose prerequisite list must be exactly true. Verified live.
- **`GET /api/v1/users` returns a bare JSON array**, not an envelope — worth knowing for 07-05.
- **The plan's "current true numbers" were stale** (1101 tests / 1659 statements; the baseline was
  1115 / 1690, and this plan closes at 1128). The README quotes no suite count at all; it quotes
  the 75% gate and points at the run, per 07-RESEARCH Pitfall 7 and the project overrides.

### Not a deviation, but worth naming

The dev stack's data volume was destroyed twice (`docker compose down -v`) to verify the quickstart
on a genuinely fresh database. That is the only way the register step's 201 is real rather than an
artifact of a database that happened to be empty of that one address.

## Known Stubs

None.

## Threat Flags

None. No new network surface, auth path, file access pattern or schema change. T-07-11 is honoured:
the quickstart never prints, pastes or invents a `JWT_SECRET`, both example accounts use
`@example.com` addresses with an obviously fake password, and no bearer token from a real run
appears in the file — the one token fragment shown is the JWT header `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9`,
which is the base64 of `{"alg":"HS256","typ":"JWT"}` and carries no signature and no claims.

## What 07-05 Needs to Know

1. **The rehearsal extractor must take fenced ` ```bash ` blocks only, never inline code spans.**
   Section 3 mentions `make install` and `make test` in prose backticks inside the region; those
   are host-path commands and must not be executed. The gate's own
   `_rehearsal_commands()` shows the shape.
2. **The region's blocks share shell state** (`$API`, `$TOKEN`, `$AUTH`, `$LIST`, `$TASK`), so they
   must be concatenated into **one** script, in order, not run block by block.
3. **The region's blocks in order are:** `make env` + `make up` (background it and poll for
   `healthy`); `make docker-test`; the quickstart; the two error calls; the assignment plus
   `docker compose logs api | grep task_assigned_email`.
4. **The quickstart needs a database with no `ada@example.com` and no `grace@example.com`**, so the
   rehearsal's `docker compose down -v` before `up` is load-bearing, not hygiene.
5. **Adding `make rehearse` to the README is free now**: the `.PHONY` check will accept it the
   moment the target exists, and `test_the_rehearsal_region_needs_no_virtualenv` will reject it
   *inside* the markers (correctly — the script must not invoke itself).
6. **`README.md` is now a gated file.** Any edit to its endpoint table, its `make` targets, its ADR
   citations, the two counts it quotes or its markers must keep
   `tests/architecture/test_documentation_claims.py` green.
7. **Any new test that reads a repository-root file needs its Dockerfile `COPY` line in the same
   commit**, and that commit is verified with `make docker-test`. ADR-102 and CLAUDE.md now say so.
8. **`.planning/` and `.github/` are still absent from the test image** — path-existence checks over
   the whole tree belong to the rehearsal script, as ADR-102 records.
9. **The Phase 7 incident-log entry is still owed** (standing rule). Do not pin "51 incident
   entries" as an equality anywhere; 07-05 appends one.
10. **The CI badge is red-or-stale until the push.** Expected, and a human checkpoint afterwards —
    along with the Mermaid rendering, which has no local renderer by design.

## Self-Check: PASSED

- `README.md` — FOUND
- `tests/architecture/test_documentation_claims.py` — FOUND
- `Dockerfile` (COPY line present) — FOUND
- `DECISION_LOG.md` ADR-102 heading — FOUND (102 `^## ADR-` headings, `git diff | grep -c '^-'` = 1)
- `CLAUDE.md` new bullets, no `<!-- GSD:` line deleted — FOUND
- Commits `f5a9ffa`, `dda7476`, `fcd8579` — FOUND
