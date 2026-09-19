---
phase: 03-persistence-runnable-stack
plan: 11
subsystem: documentation
tags: [adr, decision-log, ai-workflow, claude-md, phase-gate, requirements, wr-05, roadmap]

# Dependency graph
requires:
  - phase: 01-foundation-quality-gates
    provides: the DECISION_LOG.md ADR form and its append-only rule, the AI_WORKFLOW.md skeleton and incident-log format, the hand-maintained CLAUDE.md Project Rules section outside every GSD block, and ADR-017/ADR-018 with their promises attached
  - phase: 02-domain-error-contract
    provides: ADR-021 (the DomainError shape and the 422 classification this phase's WR-05 ADR refines) and 02-REVIEW-FIX.md, which deferred WR-05 to this phase by name
  - phase: 03-persistence-runnable-stack
    plan: 10
    provides: the last of the ten plans whose decisions this one records, and the cold-start rehearsal the phase gate repeats from scratch
provides:
  - DECISION_LOG.md ADR-023 through ADR-043 - every non-obvious Phase 3 choice with its options and its consequences
  - ADR-028 - WR-05 settled in writing, refining ADR-021 by scope rather than by error type
  - ADR-041 - the ADR-017 / ADR-018 follow-up, recording that both Phase 1 promises were kept and naming plan 03-10
  - AI_WORKFLOW.md - nine dated Phase 3 incidents plus the Phase 3 human/AI split, every claim tied to a commit, an evidence capture, a test module or a test name
  - CLAUDE.md - a Persistence and transactions section and one quality-gate rule, each transcribed from the gate that enforces it
  - evidence/03-11-phase-gate.txt - the whole gate in one uninterrupted run, cold volume included
affects: [04-crud-endpoints, 05-auth, 06-test-hardening, 07-documentation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A phase closes by recording its decisions before its evidence goes stale: ten plans handed forward an ADR debt list in their summaries, and this plan is where it is paid"
    - "An ADR that refines an earlier one names it by id and leaves it unedited - the log is append-only, and a refinement by id is the mechanism its own header describes"
    - "A CLAUDE.md rule is transcribed from the artifact that enforces it, never from the plan that asked for it, so documentation cannot drift from enforcement"
    - "The phase gate runs `make format` first and proves it a no-op, so the lint run that follows is a check rather than a rewrite"
    - "A roadmap success criterion is re-verified against a named test before it is ticked, never inherited from a plan header"

key-files:
  created:
    - .planning/phases/03-persistence-runnable-stack/evidence/03-11-phase-gate.txt
  modified:
    - DECISION_LOG.md
    - AI_WORKFLOW.md
    - CLAUDE.md
    - .planning/ROADMAP.md

key-decisions:
  - "Twenty-one ADRs were written rather than the plan's twelve: the plan enumerates twelve decisions, and ten plan summaries handed forward nine more (the PostgreSQL 18 volume path, literal constraint names in revisions, the untranslated CHECK constraints, the one-helper-per-adapter translation and its savepoint rule, the unit of work's open-session property and port annotations, the Annotated[...] injection form, the test compose profile, and ENTRYPOINT/CMD). Leaving the nine unrecorded would have left the debt list unpaid while satisfying the letter of the criterion"
  - "ADR-028 names ADR-021 as the Phase 2 ADR it refines. D-14 is a locked CONTEXT decision rather than an ADR; ADR-021 is where its HTTP consequence (a domain ValidationError is 422) was decided, so that is the entry a refinement by scope has to name"
  - "The CLAUDE.md additions include one rule the plan did not list - the Annotated[T, Depends(...)] injection form - because it is gate-enforced by flake8-bugbear B008 and a Phase 4 router written the other way fails make lint for a reason that reads as a linter misconfiguration"
  - "The AI_WORKFLOW entry records two cases where a plan or a research pattern was wrong and names them: 03-10-PLAN.md forbidding the compose profile, and 03-RESEARCH.md Pattern 7 reintroducing Pitfall 2 from a second direction"
  - "All eight requirement ticks (DB-01..DB-05, ARC-08, DOCK-02, DOCK-03) are taken here, each re-verified against a named test or a line of the gate capture rather than against a plan header - ten consecutive plans deferred them under the last-claimant convention"

patterns-established:
  - "DECISION_LOG.md now carries 43 ADRs across three phases, and every Phase 3 entry cites the D-NN, WR-NN or review item it settles, so a reviewer can walk from a context decision to the code through the log"

requirements-completed: [DB-01, DB-02, DB-03, DB-04, DB-05, ARC-08, DOCK-02, DOCK-03]

# Metrics
duration: 22min
completed: 2026-09-19
---

# Phase 3 Plan 11: Phase Close — the ADRs, the Incident Log and the Full Gate Summary

**Every choice this phase made that a reviewer could otherwise read as an accident is now a numbered ADR with its options and its consequences — twenty-one of them, including the WR-05 refinement Phase 2's review explicitly deferred and the follow-up recording that ADR-017 and ADR-018 both kept their promises — `AI_WORKFLOW.md` has nine dated Phase 3 incidents whose every claim points at a commit, an evidence capture or a test name, and the whole gate was run in one uninterrupted sequence: `make format` a proven no-op, four gates green, `make test` twice with identical counts, a cold stack from an empty volume reaching `api healthy` in three polls, `/health` answering `"database":"ok"`, and `make docker-test` green inside the image.**

## Performance

- **Duration:** 22 min
- **Started:** 2026-09-19T01:28Z
- **Completed:** 2026-09-19T01:50Z
- **Tasks:** 3
- **Files modified:** 1 created, 4 modified (plus this summary, `STATE.md` and `REQUIREMENTS.md` in the metadata commit)

## Accomplishments

- **`DECISION_LOG.md` goes from 22 ADRs to 43, and loses no line.** `git diff DECISION_LOG.md | grep -c '^-'` prints `1` — the diff header alone — so the append-only rule the log's own preamble states is kept mechanically rather than by intention. `grep -c -i "consequences"` went from 23 to 44, one per new entry, and every new ADR carries all four established headings.
- **WR-05 is settled in writing, and it names what it refines.** ADR-028 records the resolution the Phase 2 review skipped *because* it contradicted a locked decision: D-14 is refined by **scope**, not by error type. A naive datetime reaching the domain is still a `ValidationError`; one read from a database row raises `NaiveDatetimeFromDatabaseError`, a `RuntimeError` deliberately outside the `DomainError` hierarchy, so a schema regression becomes the fixed 500 rather than a 422 naming a column no request contains. The ADR names **ADR-021** as the entry it refines, because D-14 is a locked `02-CONTEXT.md` decision rather than an ADR and ADR-021 is where its HTTP consequence was decided.
- **ADR-017 and ADR-018 get their promised follow-up, with the plan that discharged it named.** ADR-041 records that `make up` / `make down` are real commands (`grep -c` for the placeholder string prints `0`) and that `make docker-test` is now `docker compose run --rm --build test` against the compose database — so the integration suite runs there too, where the previous body would have failed every integration test this phase added. Both in plan 03-10, commits `bb1274e`, `15423a9`, `083fd11`.
- **Nine of the twenty-one ADRs exist only because ten plan summaries asked for them.** The accumulated debt — the PostgreSQL 18 volume path, literal constraint names in revisions, the untranslated CHECK constraints, the one-`_refused()`-per-adapter translation with its savepoint rule, the unit of work's open-session property and port-annotated attributes, the `Annotated[...]` injection form, the `test` compose profile and the `ENTRYPOINT`/`CMD` split — is paid rather than carried into Phase 4.
- **The two assumptions RESEARCH could only guess at are recorded with the observed outcome.** A1 is written down as *half wrong*: autogenerate **did** emit the three CHECK constraints, because the blindness applies to comparing an existing table rather than to adding one, while `alembic check` still cannot notice one disappearing — and on the `lower(email)` expression index the observed output was `No new upgrade operations detected.` with no warning at all (ADR-025). A2 is written down as true and as the thing that closed the project's last uncovered line (ADR-030).
- **`AI_WORKFLOW.md` gains nine dated Phase 3 incidents, and none of them is flattering.** A green integration test that had never executed the method it was testing, caught by reading a per-test coverage row rather than an exit status. The one falsification that can tell a working savepoint from a silently disabled commit. Two gates driven red on purpose, one of which left a real row in `taskmanager_test` that had to be deleted by hand. A plan that forbade the one change the evaluator's first command needed. A research recipe that would have failed `docker compose up` outright. A planning document that cleared a linter rule which then fired, beside a research pattern that reintroduced the pitfall it was written to avoid. The five assumptions, settled. Two verification runs that looked green and were not. And the cold stack, proved by stopping the database rather than by reading the compose file.
- **`CLAUDE.md` gains a `Persistence and transactions` section, entirely inside the hand-maintained block.** Five rules, each transcribed from the artifact that enforces it: the no-commit gate (`tests/architecture/test_no_commit_in_repositories.py`), the entities-only repository rule (the `application-framework-free` contract plus the port bindings under `mypy --strict` plus the read-after-close test), migrations only in the entrypoint (`test_creating_the_app_opens_no_connection`), constraint names in one module (`test_models.py` and `test_constraints.py`), and the `Annotated[T, Depends(...)]` injection form (flake8-bugbear B008). The `make test` database requirement joins the Quality gates section as D-03 rather than as a setup problem. `grep -c "GSD:"` is unchanged at 15 and `git diff` removes no line.
- **The whole gate ran in one uninterrupted sequence, and the transcript is on disk.** `evidence/03-11-phase-gate.txt`, 693 lines: `make format` then an empty `git status --porcelain`; `make lint`, `make typecheck`, `make arch` (3 contracts KEPT) and `make test` each `EXIT=0`; `make test` a second time with the same 287 passed and the same 100.00%, with `SELECT count(*) FROM users` on `taskmanager_test` printing `0` afterwards; `docker compose down -v` and `up --build -d` reaching `api healthy` after **3 polls** on a volume created from scratch; the Alembic revision line *before* the first uvicorn line in `docker compose logs api`; `curl` returning `200` and `{"status":"ok","checks":{"database":"ok"},"version":"0.1.0"}`; and `make docker-test` green with `Required test coverage of 75% reached. Total coverage: 100.00%`.
- **The eight requirement ticks are taken, and each was re-verified rather than inherited.** Ten consecutive plans deferred DB-01, DB-02, DB-03, DB-04, DB-05, ARC-08, DOCK-02 and DOCK-03 under the last-claimant convention. Each is checked below against a named test or a named line of the gate capture.

## Task Commits

Each task was committed atomically:

1. **Task 1: the Phase 3 ADRs** — `c703cfd` (docs)
2. **Task 2: the Phase 3 AI_WORKFLOW entry and the CLAUDE.md rule refresh** — `2b7305e` (docs)
3. **Task 3: the full phase gate, captured** — `67f2b2d` (docs)

**Plan metadata:** see the `docs(03-11)` commit that carries this SUMMARY.

## Files Created/Modified

- `DECISION_LOG.md` (+852 lines) — ADR-023 through ADR-043, appended; no existing line touched
- `AI_WORKFLOW.md` (+~250 lines) — nine incidents appended to the log, plus a Phase 3 block in the human-decided/AI-delegated section
- `CLAUDE.md` (+39 lines) — one new `### Persistence and transactions` subsection and one bullet under `### Quality gates`, both inside `## Project Rules`
- `.planning/ROADMAP.md` (+3/−3) — the Phase 3 checkbox, the 03-11 plan checkbox and the progress-table row
- `.planning/phases/03-persistence-runnable-stack/evidence/03-11-phase-gate.txt` (693 lines) — the gate, with a header stating what each of the seven steps proves

## Roadmap Phase 3 success criteria, re-verified

Each criterion was checked against the code and the run rather than ticked from a plan header, following the precedent plan 02-07 set for ARC-02 and ARC-04.

**SC-1 — `docker compose up` on an empty volume starts PostgreSQL and the API, the API waits for a genuinely ready database, applies migrations automatically, and `GET /health` reports liveness plus database readiness and backs the container healthcheck.**
True. `evidence/03-11-phase-gate.txt` STEP 5: `docker compose down -v` discards the volume, `docker compose up --build -d` starts `db` and `api` (and *not* `test`, per ADR-039), and `docker compose ps` reports `api healthy` after 3 polls — which under D-09 means the image's own curl-free `HEALTHCHECK` got HTTP 200 from `/health`, which under D-08 means the database probe passed. The migration ordering is read off the log, not claimed: `docker compose logs api` opens with `INFO [alembic.runtime.migration] Running upgrade  -> 0001, baseline` and only then `INFO: Started server process [1]`. STEP 6: `curl -s -o /dev/null -w '%{http_code}'` prints `200` and the body is `{"status":"ok","checks":{"database":"ok"},"version":"0.1.0"}`. The *failing* half of the healthcheck was falsified in plan 03-10 (`evidence/03-10-cold-start.txt`): `docker compose stop db` turns the container `unhealthy` and `/health` answers 503 with the same three members; `start db` returns both to healthy.

**SC-2 — SQLAlchemy 2.0 async ORM models are separate from the domain entities, relationships use `lazy="raise"`, and repositories return domain objects only; a test that reads an entity outside the session never raises `MissingGreenlet`.**
True, and each clause has its own test rather than resting on one. Separation: `tests/unit/infrastructure/test_models.py::test_the_three_row_classes_are_not_the_three_entities` — every other test in that file would pass unchanged against imperatively mapped entities, so the claim needed its own assertion. `lazy="raise"`: `test_every_relationship_raises_on_lazy_load` at the model level and `tests/integration/test_repositories_task_lists.py::test_touching_the_tasks_relationship_raises_instead_of_lazy_loading` against a real session. Entities only, read after close: `test_a_returned_entity_is_readable_after_the_session_is_gone`, which closes the session and then reads five fields. All eight of the tests named in this section were re-run together and reported `14 passed`.

**SC-3 — the Alembic baseline creates the schema with `task_lists.owner_id`, VARCHAR + CHECK constraints for status and priority, timezone-aware UTC timestamps, and deleting a list removes its tasks.**
True, asserted against the live catalogue rather than against `Base.metadata`. `tests/integration/test_schema.py::test_task_lists_has_an_owner_id_foreign_key` (reflected FK, `ondelete=CASCADE`, `owner_id NOT NULL`); `::test_status_and_priority_are_varchar_not_postgres_enums` (reflected `VARCHAR(16)`, and `pg_type` holds no user-defined enum in `public`); `::test_every_timestamp_column_is_timestamptz` with a vacuity guard, plus `::test_timestamps_round_trip_as_aware_utc`, which settles RESEARCH assumption A4 by round trip; `tests/integration/test_constraints.py::test_deleting_a_task_list_cascades_to_its_tasks`. The CHECK constraints are proven by refusal rather than by reflection — `alembic check` is structurally incapable of noticing one disappearing (ADR-025) — in `test_constraints.py`, which asserts the constraint *name* through `violated_constraint()`.

**SC-4 — the use case owns the transaction: a UnitOfWork commits exactly once on success and rolls back on a raised `DomainError`, and no `.commit()` call exists anywhere under `infrastructure/repositories/`.**
True. `tests/integration/test_unit_of_work.py` — six proofs, every one of which asserts a **row** rather than a counter, because `commits == 1` is equally true of a unit of work whose `__aexit__` rolled the commit straight back. The no-commit claim: `grep -rn "\.commit()" src/taskmanager/infrastructure/db/repositories/` returns `0` lines, and the gate that keeps it true is `tests/architecture/test_no_commit_in_repositories.py`, observed red on a planted line naming `users.py:73` (`evidence/03-06-no-commit-gate-red.txt`). **One wording note, recorded rather than glossed:** the criterion says `infrastructure/repositories/`; the shipped path is `infrastructure/db/repositories/`, which is where the gate scans and where the three adapters live. The claim is true of the real path.

**SC-5 — integration tests run against real PostgreSQL with per-test isolation, and the full gate (lint, typecheck, architecture, tests) is green.**
True. `evidence/03-11-phase-gate.txt` STEP 3 and STEP 4: all four gates `EXIT=0`, and `make test` twice in a row reporting **287 passed, 100.00% total coverage** with the gate at 75. Per-test isolation is not merely asserted: `SELECT count(*) FROM users` on `taskmanager_test` prints `0` after both runs, and the D-01 claim that a committed write never escapes the fixture's outer transaction is proven from a *second, independent* connection in `test_a_committed_write_is_invisible_outside_the_test_transaction` — falsified in `evidence/03-08-commit-falsification.txt`, which is the only check that distinguishes a working `create_savepoint` from a silently degraded `rollback_only`.

**Coverage observed in the final `make test` run: 100.00%** over 730 statements and 74 branches on the host (CPython 3.14.3), and 100.00% over 772 statements inside the `test` image (CPython 3.13) — the difference is statement attribution between the two interpreters, recorded by plan 03-10 and unchanged here.

## Requirement ticks, each re-verified

| ID | Verified against |
|----|------------------|
| DB-01 | `src/taskmanager/infrastructure/db/engine.py` builds an async engine on `postgresql+psycopg://` with `pool_pre_ping=True`; `tests/unit/infrastructure/test_adapter_ports.py` binds all three SQLAlchemy adapters and the unit of work to their ports under `mypy --strict`; the whole integration suite runs against a real PostgreSQL 18 in the gate capture |
| DB-02 | `migrations/versions/0001_baseline.py` applied by `docker/entrypoint.sh`; the gate capture shows `Running upgrade  -> 0001, baseline` before uvicorn starts, and `tests/integration/test_migrations.py` covers upgrade, `alembic check` and `downgrade base` |
| DB-03 | `test_the_three_row_classes_are_not_the_three_entities`, the nine explicit mappers in `src/taskmanager/infrastructure/db/mappers.py` with their round-trip tests, and the two `lazy="raise"` tests named under SC-2 |
| DB-04 | `test_status_and_priority_are_varchar_not_postgres_enums` and `test_every_timestamp_column_is_timestamptz` against the live catalogue, plus the insert-and-refuse tests in `tests/integration/test_constraints.py`, each asserting the constraint name |
| DB-05 | `test_task_lists_has_an_owner_id_foreign_key` (present since `0001_baseline`) and `test_deleting_a_task_list_cascades_to_its_tasks` |
| ARC-08 | `tests/integration/test_unit_of_work.py` (six proofs), `tests/architecture/test_no_commit_in_repositories.py` (observed red), and `test_the_dependency_does_not_commit_on_teardown` with its falsification capture |
| DOCK-02 | The STEP 5 cold start in `evidence/03-11-phase-gate.txt`: one command, both services, `pg_isready -h 127.0.0.1` healthcheck, the entrypoint's bounded retry loop, migrations applied automatically |
| DOCK-03 | STEP 6 — `200` and `"database":"ok"` — plus `tests/integration/test_health.py` and `tests/unit/presentation/test_health.py`, including the 503 leg and the leak test |

## Decisions Made

- **Twenty-one ADRs, not twelve.** The plan enumerates twelve decisions; the ten plan summaries of this phase each handed forward an ADR debt, and nine of those are not in the plan's list. Writing only the twelve would have satisfied the acceptance criterion (`at least 12 more`) while leaving the debt list unpaid and pushing it into Phase 7, where reconstructing it from a finished repository is exactly what this project's own thesis argues against. The nine extra are ADR-025, ADR-026, ADR-030, ADR-031, ADR-032, ADR-034, ADR-038, ADR-039 and part of ADR-037.
- **ADR-028 names ADR-021.** The plan asks the WR-05 ADR to "name the Phase 2 D-14 ADR it refines". There is no ADR for D-14 — D-14 is a locked decision in `02-CONTEXT.md`, and `DECISION_LOG.md` never numbered it. ADR-021 is where D-14's HTTP consequence was decided (a domain `ValidationError` is 422, on the well-formed-but-semantically-invalid reading), so that is the entry a refinement by scope has to name, and ADR-028 says so explicitly rather than inventing a reference.
- **One CLAUDE.md rule beyond the plan's five.** The `Annotated[T, Depends(...)]` injection form is added because it meets the section's own bar — it is enforced by a gate that fails a build (flake8-bugbear B008 in `make lint`) — and because a Phase 4 router written with the default-argument form fails that gate for a reason that reads as a linter misconfiguration rather than as a rule. The four other new rules and the `make test` database requirement are the plan's, transcribed from their enforcing artifacts.
- **The AI_WORKFLOW entry names two artifacts that were wrong.** `03-10-PLAN.md` instructed the executor not to add a compose profile, and both halves of its reasoning were falsified live. `03-RESEARCH.md` Pattern 7 builds the readiness probe's engine inside the retry loop, which reintroduces the same document's Pitfall 2 from a second direction. The plan's own instruction — "where a plan told the executor something that turned out to be wrong, say so plainly and name the plan" — is followed literally, including for the plan that wrote that instruction's sibling.
- **The SC-4 wording discrepancy is recorded, not silently reinterpreted.** The roadmap criterion says `infrastructure/repositories/`; the code lives at `infrastructure/db/repositories/`. The claim is true of the real path and the gate scans the real path, and saying so is cheaper than a reviewer wondering whether a directory was missed.
- **`make format` ran first and was proven a no-op.** `git status --porcelain` printed nothing after it, which is what makes the `make lint` run three steps later a check rather than a rewrite that would have hidden whatever it fixed.

## Deviations from Plan

### Deviations from the plan's letter

**1. Twenty-one ADRs where the plan lists twelve decisions**

- **Found during:** Task 1
- **Reason:** recorded in full under "Decisions Made". Nine further decisions were owed by the ten plan summaries of this phase and are not in the plan's enumeration; all twelve of the plan's are present.
- **Files modified:** `DECISION_LOG.md`
- **Commit:** `c703cfd`

**2. A sixth CLAUDE.md rule**

- **Found during:** Task 2
- **Reason:** the `Annotated[T, Depends(...)]` form is gate-enforced and is the shape Phase 4 must copy; the plan's list of five does not include it. It satisfies the section's stated bar ("every rule below is enforced by a gate that fails a build") and adds no advisory text.
- **Files modified:** `CLAUDE.md`
- **Commit:** `2b7305e`

**3. `make up` was not used for the gate's database step**

- **Found during:** Task 3
- **Reason:** the plan's sequence says `docker compose up -d db`, and `make up` is `docker compose up --build` in the **foreground** (deliberately, so a failed migration is visible — see the Makefile comment). The plan's own command was used verbatim; this note exists only so the difference between the plan's step 2 and `make up` is not read as a substitution.
- **Files modified:** none
- **Commit:** `67f2b2d`

**4. One pre-commit abort on the evidence file, expected and re-staged**

- **Found during:** Task 3
- **Reason:** the `trailing-whitespace` hook rewrites captured terminal output (compose and pytest lines end in spaces). The commit aborted, the fixed file was re-staged, and the second attempt passed. This is the third plan in this phase to meet it; 03-08's summary predicted it ("stage, expect one abort, re-stage").
- **Files modified:** `.planning/phases/03-persistence-runnable-stack/evidence/03-11-phase-gate.txt`
- **Commit:** `67f2b2d`

Everything else executed as written. Every acceptance criterion of all three tasks passed: `grep -c "^## ADR-"` went 22 → 43 (the criterion asks for at least 12 more) and `grep -c -i "consequences"` went 23 → 44; `grep -c "WR-05"` prints `4` and the surrounding ADR names ADR-021; `grep -c "ADR-017\|ADR-018"` prints `8`; `git diff DECISION_LOG.md | grep -c '^-'` prints `1`; no attribution line or co-author trailer appears in any of the three documents or in any commit; `AI_WORKFLOW.md` carries a dated heading naming Phase 3 and nine incident entries, with `grep -c "evidence/\|tests/"` at 27; `CLAUDE.md` mentions `test_no_commit_in_repositories.py`, the entities-only rule and the `make test` database requirement, `grep -c "GSD:"` is unchanged at 15 and `git diff CLAUDE.md | grep -c '^-'` prints `1`, so no GSD-managed block was touched; the capture contains an empty `git status --porcelain` after `make format`, four green gates, a second green `make test` with identical counts, an `api healthy` line, a `/health` body containing `"database":"ok"` and a green `make docker-test`; and `Required test coverage of 75% reached` appears three times in it.

## Issues Encountered

- **The one pre-commit abort above.** Nothing else in the run required a fix-up.
- **`make test` was run with `DATABASE_URL`, `TEST_DATABASE_URL` and `JWT_SECRET` exported from `.env` in the shell** rather than relying on the process environment, because `make` does not source `.env` and the settings object has no defaults for two of the three. `.env` itself is git-ignored and was not modified.
- **The gate capture was written to a scratch path and copied into the repository afterwards**, on purpose: writing it into `.planning/` first would have made STEP 1's `git status --porcelain` non-empty, which is the one line in the whole transcript that has to be blank.
- Nothing else. `filterwarnings = error` raised nothing across either `make test` run or the containerised one.

## Known Stubs

None. This plan writes documentation and runs a gate; every artifact it produces is complete. Three sections of `AI_WORKFLOW.md` — "How This Project Was Built", the per-claim reference pass over "Human-Decided vs AI-Delegated", and "What I Did Not Do" — still carry their explicit *"To be completed in Phase 7"* markers, which are Phase 1's deliberate placeholders for Phase 7's scope and not gaps this plan left.

## Threat Flags

None new. This plan opens no endpoint, adds no auth path, installs nothing (`requirements.txt` untouched, so **T-3-SC** stays `accept` with no package legitimacy question raised) and reads no user input. The register's four `mitigate` rows are implemented:

- **T-3-35** (an environment value leaking into an evidence capture) — *mitigated by scan, not by assumption*: every `KEY=value` pair in `.env` was grepped against `evidence/03-11-phase-gate.txt` as a literal. `DATABASE_URL`, `TEST_DATABASE_URL`, `JWT_SECRET` and `APP_NAME` all return **0 hits**. The only non-zero results are `ENVIRONMENT=local` (4) and `JWT_EXPIRE_MINUTES=30` (8), whose values are the ordinary English word "local" and the number 30 appearing in unrelated output — neither is a credential and neither is disclosed by the match. No password, DSN or secret appears anywhere in the capture.
- **T-3-36** (a reader left guessing whether a real secret was ever involved) — *mitigated*: ADR-042 states the published 5432/8000 bindings, names the credential pair as the obviously-fake `taskmanager:taskmanager` already public in `docker-compose.yml`, `.env.example` and CI, and names the loopback-only alternative as a one-token change — the sentence plan 03-02 handed forward.
- **T-3-37** (an `AI_WORKFLOW.md` claim resting on assertion alone) — *mitigated*: every one of the nine incident entries points at a commit hash, a path under `evidence/`, a `tests/` path or a test function name; `grep -c "evidence/\|tests/"` prints 27 against a required increase of 3.
- **T-3-38** (a decision quietly rewritten after the fact) — *mitigated*: `git diff DECISION_LOG.md | grep -c '^-'` prints `1`, the diff header alone, so the append-only rule is asserted rather than trusted. ADR-028 and ADR-041 refine earlier entries **by id**, leaving ADR-021, ADR-017 and ADR-018 untouched.

## User Setup Required

**None, and one thing to know.** The stack was left running: `db` and `api` are up, `api` is `healthy`, and `http://localhost:8000/health` answers 200 on a volume created fresh during this plan's gate. `make down` stops it; `docker compose down -v` also discards the volume, which is what a fresh rehearsal needs — and which the initdb script requires in order to run at all.

`.env` exists on this machine, git-ignored, copied from `.env.example` during plan 03-10. Nothing in it needs editing for local evaluation.

## Next Phase Readiness

- **Phase 3 is closed.** All five roadmap success criteria are re-verified above against named tests and named lines of the gate capture, all eight requirements are ticked, `ROADMAP.md` marks the phase complete at 11/11, and the whole gate is green on disk.
- **Phase 4 inherits three rules it must follow rather than rediscover,** all now in `CLAUDE.md`: routers take `Annotated[UnitOfWork, Depends(get_uow)]` (the default-argument form fails `make lint`); a use case owns its transaction and nothing under the repositories package may end one; and any test that expects a database refusal must create the *cause* of that refusal inside `session.begin_nested()`, or the savepoint's own flush produces a green test that never reached the code under test (ADR-030).
- **Phase 4 also inherits two query shapes and a fixture chain.** The TASK-06 filters are already keyword-only and already in SQL; the completion percentage is already one `COUNT(*) FILTER (WHERE ...)` statement returning a `CompletionStats`; and `tests/integration/conftest.py` already hands out a migrated schema, an outer transaction that rolls back, a savepoint-joining session factory and a `uow` fixture.
- **Two items are explicitly Phase 7's, not forgotten here.** `AI_WORKFLOW.md`'s three skeleton sections carry their own markers. And `DECISION_LOG.md` ADR-019's claim that "the workflow has never run on a real runner" has been stale since plan 01-08; the log is append-only, so Phase 7 owns the superseding entry — flagged in 01-08's summary and repeated here so it does not fall off the list.
- **One standing obligation is unchanged:** `AI_WORKFLOW.md` is appended to at the end of every phase. Reconstructing it in Phase 7 would undermine its own thesis, and Phase 3's entry was written from evidence captured while the work happened.
- No blockers.

## Self-Check: PASSED

The created file exists on disk
(`.planning/phases/03-persistence-runnable-stack/evidence/03-11-phase-gate.txt`, 693 lines) and
all four modified files carry their intended diffs (`DECISION_LOG.md`, `AI_WORKFLOW.md`,
`CLAUDE.md`, `.planning/ROADMAP.md`). All three task commits (`c703cfd`, `2b7305e`, `67f2b2d`)
are present in `git log`. No commit deleted a tracked file
(`git diff --diff-filter=D --name-only HEAD~3 HEAD` is empty) and `git status --short` was clean
after each. `make lint && make typecheck && make arch && make test` was run green before every
commit, and the full gate — four gates, `make test` twice, a cold stack reaching `api healthy`,
`/health` answering `"database":"ok"`, and `make docker-test` — ran green in one uninterrupted
sequence: 287 passed, 100.00% coverage over `src/taskmanager` with the gate at 75, three
contracts KEPT.

---
*Phase: 03-persistence-runnable-stack*
*Completed: 2026-09-19*
