---
phase: 05-auth-assignment-notifications
plan: 16
subsystem: documentation-phase-close
tags: [adr, decision-log, ai-workflow, claude-md, requirements, traceability, phase-gate, coverage, pep-649, t-5-06, t-5-08]

# Dependency graph
requires:
  - phase: 05-auth-assignment-notifications
    provides: "fifteen plan summaries handing forward the decisions the plans did not anticipate (05-01 .. 05-15)"
  - phase: 05-auth-assignment-notifications
    provides: "evidence/05-15-cold-start.txt, the compose leg already discharged on an empty volume"
  - phase: 04-task-lists-tasks
    provides: "ADR-058's locking read and the widened HTTPException AST gate, both shipped as Phase 4 review debt (D-18) and both undocumented in CLAUDE.md until now"
  - phase: 04-task-lists-tasks
    provides: "the 04-12 precedent: a re-verification table, a one-run gate capture written to a scratch path, and phase completion left to the orchestrator"
provides:
  - "DECISION_LOG.md ADR-059 .. ADR-083: twenty-five Phase 5 decisions, appended, nothing edited away"
  - "AI_WORKFLOW.md: thirteen dated Phase 5 incident entries, each pointing at a commit, a file or a test"
  - "CLAUDE.md § Project Rules: the HTTPException gate at its real scope, and the write-path locking rule"
  - ".planning/REQUIREMENTS.md: AUTH-01..06, ASGN-01..03, NOTF-01..03 ticked against a re-verification table; 56/69"
  - "evidence/05-16-phase-gate.txt: six gates green in one uninterrupted clean-tree run, plus the twelve re-verifications"
  - "A re-measured host/container coverage divergence handed to Phase 6 as TEST-03"
affects: [06-test-hardening, 07-documentation-delivery]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A phase-closing ADR set written from the plan summaries rather than from the plan's own enumeration, because the summaries carry the decisions execution forced"
    - "A requirement tick that is earned by running its command inside the same transcript the tick cites"
    - "A CLAUDE.md rule transcribed from the gate file it names, never from the plan that intended the gate"

key-files:
  created:
    - .planning/phases/05-auth-assignment-notifications/evidence/05-16-phase-gate.txt
  modified:
    - DECISION_LOG.md
    - AI_WORKFLOW.md
    - CLAUDE.md
    - .planning/REQUIREMENTS.md
    - .planning/ROADMAP.md
    - .planning/STATE.md

key-decisions:
  - "Twenty-five ADRs (059-083) rather than the fifteen the plan enumerates: the fifteen Phase 5 summaries handed forward ten more decisions, and writing only the enumerated set would have satisfied the acceptance criterion while pushing the debt into Phase 7 - the same call 03-11 (21 for 12) and 04-12 (14 for 9) made"
  - "ADR-066 and ADR-067 are written as concessions in those words: the register 409 is an enumeration oracle AUTH-01 requires, bounded but not removed, and login has no rate limiting at all with Argon2's floor named as an incidental throttle rather than a control. Neither is described as mitigated"
  - "ROADMAP Phase 5 SC-1 amended: it credited using Swagger's Authorize button successfully, which nobody in this project does - no human ran the browser flow and no test drives one. It now names the contract the button reads and the gate that asserts it. The other four criteria were re-read against what shipped and are accurate as written"
  - "The Phase 4 review's 'Still open' note - CLAUDE.md describing the AST gate as routers/ only - is discharged here and recorded as an AI_WORKFLOW entry of its own, because the rule text was wrong for eleven plans while the gate was right"
  - "The gate capture is one execution of one shell script covering all nine steps. An earlier pass covering steps 1-7 only was green and is NOT in the file; the header says so rather than letting ATTEMPTS: ONE imply something narrower than the truth"
  - "The host/container coverage divergence was re-measured rather than inherited: 998 tests give host 100.00% over 1619 statements and container 99.06% over 1772. It widened from 11 missed lines to 18, is still PEP 649, and is handed to Phase 6 with no pragma and no omit"
  - "STATE.md and ROADMAP.md were updated by hand in their existing conventions rather than through the SDK state handlers, the same call every plan in this phase made, for the reasons now recorded in AI_WORKFLOW.md"
  - "The phase is NOT marked complete: the ROADMAP phase checkbox, the Progress table's status cell and its completion date are the orchestrator's after verification. Only the sixteenth plan box and the 16/16 count were taken here"

patterns-established:
  - "A concession is recorded with the word 'conceded' and the bound on the damage, never with a compensating control presented as a fix"
  - "A success criterion that credits an observation nobody made is amended with the amendment recorded inline, not quietly reinterpreted"

requirements-completed: [AUTH-01, AUTH-02, AUTH-03, AUTH-04, AUTH-05, AUTH-06, ASGN-01, ASGN-02, ASGN-03, NOTF-01, NOTF-02, NOTF-03]

# Metrics
duration: 30min
completed: 2026-09-19
---

# Phase 5 Plan 16: The Phase Close Summary

**Every Phase 5 decision that outlives the phase is now an ADR with its rejected alternatives,
the two security properties this phase conceded are written down as concessions, the twelve
requirement ticks were each earned by running their command inside the transcript that cites
them, and all six gates are green in one recorded run from a clean tree.**

## Performance

- **Duration:** ~30 min
- **Tasks:** 3 of 3
- **Files modified:** 7 (1 created, 6 modified)

## Task Commits

| Task | Name | Commit |
|------|------|--------|
| 1 | The Phase 5 ADRs | `a3390c0` (docs) |
| 2 | The incident log, the two changed rules, and the twelve ticks | `0bb9601` (docs) |
| 3 | The full phase gate in one uninterrupted run | `7fda036` (docs) |

## Accomplishments

### Task 1 — twenty-five ADRs, appended, nothing edited away

`DECISION_LOG.md` went from 58 entries to **83** (ADR-059 … ADR-083). The plan enumerates
fifteen decisions; the fifteen Phase 5 summaries handed forward ten more, and writing only the
enumerated set would have met the acceptance criterion while pushing the rest into Phase 7 —
which is the thing this project's own workflow thesis argues against. 03-11 wrote twenty-one
where its plan named twelve and 04-12 wrote fourteen where its plan named nine; both are the
precedent.

The log is append-only **mechanically**: `git diff DECISION_LOG.md | grep -c '^-'` prints `1`,
the diff header alone. Three entries refine earlier ones by id without editing them — ADR-059
refines ADR-055, ADR-075 refines ADR-045, ADR-076 refines ADR-054.

| ADR | One line |
|-----|----------|
| 059 | the third outcome — `owned_task` beside `visible_task`, refining ADR-055 |
| 060 | a grep-checkable documentation claim is retired in the commit that falsifies it (D-22) |
| 061 | the HS256 signing-key floor rises from 16 characters to 32 (D-26) |
| 062 | the PyJWT decode policy, and the one failure deliberately left outside the catch |
| 063 | Argon2 runs off the event loop through `anyio.to_thread`, which is imported unpinned |
| 064 | `PasswordHasher.dummy_verify` — the one port extension this phase took (D-21) |
| 065 | the 401 message lives on `AuthenticationError`, and this API has two 401 wordings |
| 066 | register's 409 is an account-enumeration oracle — **conceded, not mitigated** (D-23, T-5-06) |
| 067 | there is **no rate limiting** on login, and Argon2 is not a substitute for one (T-5-08) |
| 068 | `GET /api/v1/users` is an email directory readable by every authenticated caller (D-13) |
| 069 | the assignment door — one URL, two verbs, two no-ops, self-assignment allowed (D-05, D-07, D-08) |
| 070 | the invitation is attempted after the commit, and its failure is swallowed (D-16) |
| 071 | nothing in this repository's flake8 configuration objects to a bare `except Exception` |
| 072 | the JSON log handler is attached to the whole `taskmanager` package (D-15, D-24) |
| 073 | the formatter renders `exc_info`, and the notifier names its logger literally |
| 074 | `OAuth2PasswordBearer(auto_error=False)` is how ADR-051 and AUTH-02 hold together |
| 075 | the demo account is deleted and nothing replaces it, refining ADR-045 (D-14) |
| 076 | the HTTP harness splits in two, and the statement counts become 2 and 4 (D-20) |
| 077 | `GetProfile` is a second use case, so ADR-044's seam type never had to change |
| 078 | `SecurityResources` carries the token lifetime as well as the two adapters (RC-3) |
| 079 | register answers 201 with a `Location` of `/api/v1/auth/me` (D-09, D-19) |
| 080 | revision `0002` — a transient `server_default`, and one index argued against two refusals (D-25) |
| 081 | `GET /api/v1/tasks/assigned-to-me` is a flat route returning a bare array (D-02) |
| 082 | an address that crosses an `EmailStr` boundary must use a real top-level domain |
| 083 | the permission model is one table, bound to the published document (D-04) |

**The two concessions are written as concessions.** ADR-066 says AUTH-01 requires the 409, that
the requirement was chosen over the property, and states the bound: the error carries no
address (asserted by a test that registers `Ana@X.com` then `ana@x.com` and checks the 409
document for neither spelling), and `GET /users` already discloses every address to
authenticated callers, so the residual leak is to unauthenticated ones — who face no rate limit,
which ADR-067 says in its own words rather than leaving implied.

### Task 2 — the incidents, the two rules, and the twelve ticks

**`AI_WORKFLOW.md`** gained **thirteen** dated entries. The ones the plan names, plus the ones
the summaries turned up:

- the INFO line uvicorn was dropping entirely, found by executing rather than reading — plus the
  two further defects the same decision exposed (a formatter that discards every traceback, a
  logger name that resolves to a branch nothing listens on);
- RC-1 and RC-2: the research asked for four fakes that already existed and named two of them
  wrongly, which followed literally would have shipped two in-memory doubles for one port;
- D-20's consequence stated in the indicative mood while being conditional on a harness change
  nobody had planned;
- `FakeUserRepository.list_all`, the last fake still answering in insertion order, missed when
  its two siblings were fixed in 04-02 and 04-06, observed red in
  `evidence/05-02-fake-user-ordering.txt`;
- the migration that broke `docker compose up`, and the plan that under-counted its own blast
  radius (fourteen construction sites planned, eighteen real, fifteen tests red);
- **the evidence file drafted with the results of two runs that had not happened**, discarded
  before commit and rewritten from observed output only — named here as the AI failure mode it
  is, in the one file whose purpose is to be evidence;
- the prohibited `git stash --include-untracked`, popped immediately, tree verified clean;
- six plans that were wrong about what a tool does — 05-05's un-buildable `alg=none` snippet,
  05-06's logger name, 05-08's `noqa` for a Ruff code flake8 cannot emit, 05-11's missing
  provider, 05-12's self-contradictory 422, 05-02's `is None` assertion that fails mypy — plus
  the six grep counters met by rewording prose;
- the RED step that still cannot be a commit, and the falsifications that replaced it, with
  05-14's removed `commit()` as the instructive one: the 200 and the response body still passed,
  and only the owner-side re-read caught it;
- the two 401 wordings, found by the permission matrix asserting the wrong one;
- the SDK state handlers regressing STATE.md and ROADMAP.md in all sixteen plans, including the
  twelve `[Phase ?]:` decision lines still in the file;
- the two coverage dips (99.59%, 99.15%) closed with no exemption, the orchestrator re-running
  every gate itself after every wave, and the one executor suggestion rejected for proposing an
  upward import the `.importlinter` contracts forbid;
- the rule text catching up with its gate, eleven plans late.

**`CLAUDE.md` § Project Rules**, both changes transcribed from the gate file and outside every
GSD delimiter block (`git diff CLAUDE.md | grep -c "GSD:"` prints `0`):

1. The `HTTPException` rule now states the real scope — **all of `presentation/api`**, not
   `routers/` — names the one exemption (`errors/handlers.py`) and the test that fails if that
   exemption outlives its reason, describes both AST passes including the aliased-import and
   star-import spellings, and names `REQUIRED_SCANNED_MODULES` as the non-vacuity guard with the
   rule that a new module joins it in its creating commit. A second bullet records the
   consequence this phase met: `OAuth2PasswordBearer(auto_error=True)` is not an option.
2. A new **write-path locking** rule: a use case about to change or delete a resource loads
   through `visible_task_list(..., for_update=True)` / `visible_task(..., for_update=True)` /
   `owned_task(..., for_update=True)`; read paths never lock; only the addressed resource is
   held. It names both gates —
   `tests/unit/application/test_write_paths_hold_what_they_change.py` (both directions, against
   the fakes) and `tests/integration/test_concurrent_writes.py` (two units of work on two real
   connections).

Nothing was added that no gate enforces, which is that section's own bar.

**`.planning/REQUIREMENTS.md`** — all twelve boxes ticked, all twelve Traceability rows moved to
`Complete`, and a Phase 5 re-verification table added in the shape 04-12 introduced: twenty-three
rows, each with its command, its collected count and a named test. **56/69 complete.** NOTF-02's
second half is the one row whose evidence is not a test, and the table says so: it rests on
`evidence/05-15-cold-start.txt`, where one `grep` over `docker compose logs api` finds exactly
one `task_assigned_email` record on a wiped volume.

**`.planning/ROADMAP.md`** — the sixteenth plan box ticked, the Progress row at 16/16, no `TBD`
in the Phase 5 section, and **SC-1 amended**. It read "use Swagger's 'Authorize' button
successfully"; nobody in this project clicks that button and no test drives one, so the criterion
credited an observation that was never made. It now names the published contract and
`tests/unit/presentation/test_security_scheme.py`, the gate that reads it, with the amendment
recorded inline — the Phase 2 SC-1 / Phase 3 SC-4 / Phase 4 SC-5 precedent. The other four
criteria were re-read against what shipped and are accurate as written.

### Task 3 — the gate

One execution of one shell script, `18:36:16Z` to `18:37:16Z`, from a blank
`git status --porcelain` to a blank one, written to a scratch path and copied in afterwards so
that line could be blank at all.

| Step | Command | Result |
|------|---------|--------|
| 2 | `make format` (first, to prove it is a no-op) | `180 files left unchanged`, tree still clean |
| 3 | `make lint` | `180 files would be left unchanged`; isort clean; flake8 silent |
| 4 | `make typecheck` | `Success: no issues found in 180 source files` |
| 5 | `make arch` | `Contracts: 4 kept, 0 broken.` (115 files, 385 dependencies) |
| 6 | `make test` (with `db` up) | **998 passed in 10.16s**, `Required test coverage of 75% reached. Total coverage: 100.00%` — 1619 statements, 0 missed, 146 branches, 0 partial |
| 7 | `make docker-test` | **998 passed in 17.24s**, `Total coverage: 99.06%` — 1772 statements, 18 missed |
| 8 | the twelve requirement re-verifications | 22 commands, every one exit `0`, every one collecting at least one test |
| 9 | the compose leg | named by path: `evidence/05-15-cold-start.txt` |

`grep -rn "pragma: no cover" src/taskmanager/` matches nothing and `grep -c "omit" pytest.ini`
prints `0`. The 75% threshold was not touched.

## Deviations from Plan

**1. Twenty-five ADRs where the plan enumerates fifteen.** Not a deviation in kind — the plan
says "prefer writing one ADR too many over leaving one owed" and names the 03-11 and 04-12
precedents — but recorded because the count is ten over. The additions come from the summaries:
ADR-071 (the `BLE001` finding), ADR-073 (the two decisions taken against the plan in 05-06),
ADR-077 (`GetProfile`), ADR-078 (`SecurityResources`' third member), ADR-081 (the discovery
route), ADR-082 (the `EmailStr` TLD finding), ADR-083 (the matrix), plus the wrong-parent
ordering folded into ADR-059 and the two no-ops folded into ADR-069.

**2. The gate script was run twice, and the header says so.** The first execution covered
steps 1–7 only and was green throughout with identical results; the script was then extended
with step 8 (the twelve re-verifications) and step 9, and the **whole** sequence was re-run so
that no part of the capture comes from a different shell. `ATTEMPTS: ONE` describes the recorded
sequence, in which nothing was red and nothing was fixed between steps, and the header states
the earlier partial pass immediately underneath rather than letting the count imply something
narrower than the truth.

**3. `roadmap.update-plan-progress` and the `state.*` handlers were not used.** Every plan in
this phase reported the same regressions (a phase-based `percent`, a reset `Status:` line,
injected blank lines, a blanked progress row, a `[Phase ?]:` decision prefix), and every plan
repaired them by hand. This plan edited `STATE.md` and `ROADMAP.md` directly in their existing
conventions instead, which means the three fields the plan warns about — the phase checkbox, the
Progress table's status cell and its completion date — were never touched rather than set and
reverted. The regressions themselves are now an `AI_WORKFLOW.md` entry, which is where a
recurring tooling defect belongs.

**4. One acceptance criterion is met in substance.** ADR-066's heading reads "conceded, **not**
mitigated", so the word "mitigated" does appear in the entry the criterion names. The criterion's
intent — that the register 409 is never *described as* mitigated — is met literally: the only
occurrence negates it, and it is the plan's own `must_haves` phrasing ("neither described as
mitigated"). The 01-03 prose-not-literal convention applied to a counter the plan wrote.

**5. No `roadmap` phase-completion field was set, deliberately.** `- [ ] **Phase 5** …` is still
unticked, the Progress table still reads `In Progress` with `-` for the date, and
`grep -c "^- \[x\] \*\*Phase 5" .planning/ROADMAP.md` prints `0`.

## Issues Encountered

- **The `trailing-whitespace` hook rewrote the gate capture on the first commit attempt**, as it
  has for every evidence file in this phase: pytest echoes source lines with trailing spaces and
  import-linter's ASCII diagram carries them too. The file was re-added and committed; the text
  is otherwise verbatim and the commit message records the edit.
- **The host/container coverage gap has widened, and is not being closed here.** 18 missed
  statements against Phase 4's 11, same PEP 649 cause, all of them the trailing statements of
  route handlers that the integration suite demonstrably drives. Closing it with a `pragma` or an
  `omit` is forbidden by CLAUDE.md and would be the wrong fix anyway; Phase 6 owns TEST-03 and
  the `STATE.md` blocker now carries the new numbers and the exact line list.
- **A dangling note in `AI_WORKFLOW.md` was discharged rather than left.** The Phase 4 review
  entry ends with "Still open … CLAUDE.md's description of the AST gate still says `routers/`".
  That is now false, and a thirteenth entry says so and records why the fix waited eleven plans.

## Known Stubs

None.

## Threat Flags

None. This plan ships no code: it touches five documentation files, two planning files and one
evidence capture. `requirements*.txt` is unchanged, no package was installed, and T-5-SC holds
trivially.

Two threats are **closed as accepted-and-documented** rather than mitigated, which is the outcome
the plan's own register specifies: **T-5-06** (register's 409 as an enumeration oracle) in
ADR-066, and **T-5-08** (no login rate limiting) in ADR-067. Both are owed again to Phase 7's
README security note; a reader who found the concession in the decision log and not in the
documentation would be right to distrust both.

## What the Next Phases Need

- **Phase 6 (TEST-03)** owns the host/container coverage divergence, re-measured here and
  recorded with its eighteen line numbers in `STATE.md` and in
  `evidence/05-16-phase-gate.txt`. Pin both runs to one measurement; do not argue the number
  down, and do not reach for a `pragma` or an `omit`.
- **Phase 7's README** owes three things this phase conceded or disclosed: the register 409
  (ADR-066), the absence of login rate limiting beside refresh tokens and password reset
  (ADR-067), and `GET /api/v1/users` as an email directory (ADR-068). It also owes the
  permission matrix reproduced as documentation (D-04, ADR-083), the `curl` examples using a
  real TLD (ADR-082), and the superseding entry for ADR-019, which is still claimed as a blocker.
- **The phase checkbox is the orchestrator's.** `.planning/ROADMAP.md` Phase 5 is unticked, its
  Progress row reads `16/16 | In Progress | -`, and `STATE.md` says
  `AWAITING VERIFICATION` in as many words.
- **The compose stack is up and healthy** with the current code, and `taskmanager_test` is
  reachable. Nothing was pruned, no volume was removed and no other container on this machine was
  touched.

## Self-Check

- `DECISION_LOG.md` — FOUND, 83 `## ADR-` headings (was 58), `git diff | grep -c '^-'` = 1
- `AI_WORKFLOW.md` — FOUND, 13 new `### 2026-09-19 —` entries
- `CLAUDE.md` — FOUND, `presentation/api` and `for_update` and
  `test_write_paths_hold_what_they_change` all present, `GSD:` absent from the diff
- `.planning/REQUIREMENTS.md` — FOUND, 0 unticked Phase 5 boxes, 0 `| Phase 5 | Pending |`
- `.planning/ROADMAP.md` — FOUND, 16 ticked plan lines, 0 `TBD`, phase checkbox unticked
- `.planning/phases/05-auth-assignment-notifications/evidence/05-16-phase-gate.txt` — FOUND
- commits `a3390c0`, `0bb9601`, `7fda036` — all FOUND in `git log`

## Self-Check: PASSED

---
*Phase: 05-auth-assignment-notifications*
*Completed: 2026-09-19*
