---
phase: 04-task-lists-tasks
plan: 11
subsystem: infrastructure
tags: [docker, entrypoint, seed, idempotence, d-01, d-02, d-03, adr-037, cold-start, list-01]

# Dependency graph
requires:
  - phase: 04-task-lists-tasks
    provides: "04-07's actor seam — DEMO_USER_ID, the Final constant this seed imports rather than copies"
  - phase: 04-task-lists-tasks
    provides: "04-08's eleven routes, which is what makes a cold-start transcript able to show anything beyond `healthy`"
  - phase: 03-persistence-runnable-stack
    provides: "docker/entrypoint.sh's three-step sequence, the compose stack, the image healthcheck and ADR-037's heredoc-not-module precedent"
  - phase: 03-persistence-runnable-stack
    provides: "migrations/versions/0001_baseline.py — the users table's columns and the uq_users_email_lower unique index this seed has to survive"
provides:
  - "docker/entrypoint.sh step 2b — the idempotent demo-user seed, so a fresh `docker compose up` serves the mandatory use case with zero setup"
  - "evidence/04-11-seed-idempotence.txt — rowcounts 1/0/0 plus the counterfactual in which a targeted conflict clause raises"
  - "evidence/04-11-cold-start.txt — the empty-volume rehearsal 04-12's phase gate and the README's five-minute claim both rest on"
affects: [04-12, 05, 07]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A conflict clause with NO target, so every unique constraint on the table absorbs a re-run — not just the primary key; a seed that must survive `set -eu` cannot pick which collision it tolerates"
    - "The entrypoint imports DEMO_USER_ID from presentation/api/actor.py, so the identifier has exactly one home and the literal does not appear in docker/entrypoint.sh at all"
    - "An idempotence claim is proven by executing the statement three times AND by running the rejected alternative through the same three, so the two forms are distinguished by observation rather than by argument"
    - "A cold-start transcript records elapsed time and poll counts rather than asserting `it came up`"

key-files:
  created:
    - .planning/phases/04-task-lists-tasks/evidence/04-11-seed-idempotence.txt
    - .planning/phases/04-task-lists-tasks/evidence/04-11-cold-start.txt
  modified:
    - docker/entrypoint.sh

key-decisions:
  - "The step is numbered 2b, not 3, and the entrypoint's header paragraph was rewritten from 'Three steps' to name it. Renumbering `exec uvicorn` to 4 would have renamed a step that has been step 3 since Phase 3 for the sake of a block Phase 5 deletes; the header now says in one clause why the letter is there (it is temporary), which is the information a reader of the renumbering would have had to reconstruct"
  - "The comment banner DESCRIBES the targeted conflict form rather than spelling it — 'a clause that named the primary-key column as its target'. The plan's own acceptance criteria are `grep -c \"ON CONFLICT DO NOTHING\"` prints 1 and `grep -c \"ON CONFLICT (id)\"` prints 0, and a comment that quoted the rejected form would have failed both while explaining itself perfectly. This is the prose-not-literal convention running since 01-03, and the banner says so in a parenthesis so the next editor does not undo it"
  - "The idempotence evidence carries a SECOND run the plan did not ask for: the same three executions against a targeted conflict clause, where the third raises `IntegrityError` on `uq_users_email_lower`. Executions 1 and 2 are byte-identical between the two runs — so a proof that only restarted with the same id would have passed against the form that aborts the container, and the difference would have surfaced the day someone edited the constant"
  - "The proof ran against `taskmanager_test`, not `taskmanager`. Its third execution deliberately attempts to write a second row and its cleanup deletes by email, so pointing it at the database `docker compose up` serves would have put a destructive statement next to an evaluator's data for no gain. Both runs deleted what they created; the database was left as found"
  - "Requirement tick LIST-01 deliberately NOT taken, despite this plan's own frontmatter naming it — 04-12 is the last claimant of LIST-01..06 and TASK-01..08, the tenth consecutive plan in this phase to make the same call. What this plan adds to LIST-01 is real (the route now answers 201 on a stack with no setup, captured in evidence) and it is exactly the kind of proof 04-12 will tick from"

patterns-established:
  - "Every decision in the banner is written as a question a future reader could answer the other way — why here and not a migration, why a heredoc and not a module, why no conflict target, why this hash is not a credential — so the block defends itself without the plan beside it"
  - "The cold-start capture elides only the image build, marks where it was cut, and says what was cut; every timing, poll count and byte of API output is verbatim"

requirements-completed: []

# Metrics
duration: 14min
completed: 2026-09-19
---

# Phase 4 Plan 11: the demo-user seed and the cold-start rehearsal Summary

**The stack is now usable on the first command: the entrypoint writes the one row the actor seam's fixed id points at, between `alembic upgrade head` and `exec uvicorn`, with a conflict clause that names no target so neither the primary key nor `uq_users_email_lower` can abort a restart — and the rehearsal that proves it goes from an empty volume to `api healthy` in six seconds and then walks the brief's mandatory use case to `completion_percentage: 100.0` without a line of setup.**

## Performance

- **Duration:** ~14 min (06:33 → 06:47 UTC)
- **Tasks:** 2 of 2, one commit each
- **Files:** 2 created, 1 modified

## What Was Built

### Task 1 — the seed (`2c2acab`)

`docker/entrypoint.sh` gains step `2b`, a Python heredoc between the migration and the server:

```
INSERT INTO users (id, email, password_hash, created_at, updated_at)
VALUES (:id, :email, :password_hash, :now, :now)
ON CONFLICT DO NOTHING
```

bound with `DEMO_USER_ID` **imported** from `taskmanager.presentation.api.actor`,
`demo@taskmanager.local`, `!` as the password hash, and `datetime.now(UTC)` for both timestamps.
A successful run prints nothing, exactly like the readiness probe above it.

Why the step exists at all: D-01 gives every Phase 4 request a fixed actor id and
`task_lists.owner_id` is a foreign key to `users.id`. On a fresh volume that row does not exist,
so an evaluator's very first `POST /api/v1/task-lists` would be a foreign-key violation — which
would make the seam's whole premise (the mandatory use case works with zero setup) false on the
first command.

The comment banner answers four questions, each one a decision a reader could otherwise undo:

| Question | Answer in the banner |
|----------|----------------------|
| Why here, not an Alembic data migration? | A data row is not a schema change. A migration would put this identity in the schema's recorded history, and Phase 5 could then only remove it by writing a second revision; here it disappears with the block. After `upgrade head` because the table must exist. |
| Why a heredoc, not a module under `src/`? | ADR-037, already won for the readiness probe: that package has no coverage `omit` and allows no `pragma`, so a seed module would owe a unit test of a five-line INSERT and add a graph node importing `presentation`. |
| Why no conflict target? | Three executions gave 1, 0, 0. The second run collides on the primary key, a run with a different id and the same email collides on `uq_users_email_lower`, and the untargeted form absorbs both. A targeted clause would raise on the second of those, and under `set -eu` that is an aborted container. |
| Why is the hash not a credential? | `!` is not a valid Argon2 encoded hash, so a pwdlib verification can never succeed against it. This identity cannot become a live account when login arrives; the row is deleted with the seam. |

### Task 2 — the rehearsal (`59f7411`)

`docker compose down -v` → `up -d --build` → poll → the full use case → `restart api` → `/health`,
captured verbatim. What it shows:

- `api healthy` **6 s** after `up` returned (3 polls, 2 s apart); the log has the Alembic revision
  line before the first uvicorn line, and nothing from the seed between them.
- `POST /api/v1/task-lists` → **201** with a `Location` header, `owner_id` reading
  `00000000-0000-4000-8000-00000000de00`. This is the line the plan exists for.
- Task created `pending`/`medium`, moved `pending → in_progress → completed`, envelope statistics
  `(1, 0, 0.0)` → `(1, 1, **100.0**)`, and the collection endpoint's per-list statistics moving
  with them.
- `docker compose restart api` → healthy again in **7 s**. The seed's second run is where Task 1's
  claim is observed in the real container under `set -eu`:
  `docker compose logs api | grep -c -E 'IntegrityError|Traceback'` prints **0**, the data survives,
  and `SELECT id, email, password_hash FROM users` returns exactly **one** row
  (`… de00 | demo@taskmanager.local | !`).
- `/health` still 200 with `"database":"ok"`.

One detail worth having in the record: on the second boot the log prints the two Alembic context
lines but **no** `Running upgrade` line. The schema was already at head, so the migration did
nothing — the same shape the seed takes one line below it.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical documentation] The entrypoint header still said "Three steps"**

- **Found during:** Task 1
- **Issue:** The plan asked only for a new `# --- 2b. ...` banner. Adding it would have left the
  file's own header paragraph (L4) asserting a three-step sequence that the file no longer had —
  documentation contradicting the code four lines above it, in the one file an evaluator reads to
  understand what `docker compose up` does.
- **Fix:** The header now reads "The steps run in this order and no other (D-06)" and lists `2b`
  between 2 and 3, with the one clause that explains the letter: the step is temporary, Phase 5
  deletes it with the seam, and `exec uvicorn` has been step 3 since Phase 3.
- **Files modified:** `docker/entrypoint.sh`
- **Commit:** `2c2acab`

**2. [Rule 2 - Weak proof] The idempotence capture gained a counterfactual run**

- **Found during:** Task 1
- **Issue:** The plan's three executions (1, 0, 0) are consistent with the *targeted* conflict
  clause too for the first two of them. A capture showing only the shipped form would have proved
  the seed is idempotent without proving the untargeted clause is why.
- **Fix:** The same three executions were run a second time against a clause naming the
  primary-key column, and the third raised
  `IntegrityError: … duplicate key value violates unique constraint "uq_users_email_lower"`. Both
  runs are in the evidence file, with the reading spelled out.
- **Files modified:** `.planning/phases/04-task-lists-tasks/evidence/04-11-seed-idempotence.txt`
- **Commit:** `2c2acab`

### Plan criteria met in substance

The plan's banner instructions said to name `ON CONFLICT (id) DO NOTHING` as the rejected form,
while its own acceptance criteria require `grep -c "ON CONFLICT (id)"` to print `0` and
`grep -c "ON CONFLICT DO NOTHING"` to print `1`. The banner therefore describes both forms rather
than quoting them, which is the convention running since 01-03 (and the call 04-03, 04-06, 04-07
and 04-09 each made for their own counters). Every grep criterion passes literally.

### Authentication gates

None.

## Verification

| Check | Result |
|-------|--------|
| `bash -n docker/entrypoint.sh` | exit 0 |
| `grep -c "ON CONFLICT DO NOTHING" docker/entrypoint.sh` | `1` |
| `grep -c "ON CONFLICT (id)" docker/entrypoint.sh` | `0` |
| `grep -c "DEMO_USER_ID" docker/entrypoint.sh` | `3` (import, bound parameter, banner) — criterion is "at least 2" |
| `grep -c "00000000-0000-4000-8000-00000000de00" docker/entrypoint.sh` | `0` — the literal lives only in `actor.py` |
| seed between `upgrade head` and `exec uvicorn` | asserted by index, exit 0 |
| `make lint` | pass |
| `make typecheck` | `Success: no issues found in 137 source files` |
| `make arch` | `Contracts: 4 kept, 0 broken.` |
| `make test` | `551 passed`, `Total coverage: 99.36%` |
| `docker compose ps` after cold start | `api healthy`, `db healthy` |
| `POST /api/v1/task-lists` on the fresh stack | `HTTP/1.1 201 Created` + `location: …/api/v1/task-lists/f73371f5-…` |
| `curl … /health` | `200`, `{"status":"ok","checks":{"database":"ok"},"version":"0.1.0"}` |
| `docker compose logs api \| grep -c -E 'IntegrityError\|Traceback'` | `0` |
| `git status --porcelain -- docker-compose.yml Dockerfile Makefile` | empty |

The gates were run twice — once before each commit — and the second run came *after* the
`docker compose down -v`, so the `551 passed / 99.36%` above is against a test database that was
recreated by the initdb script and migrated by the `migrated_database` fixture, not one that had
been sitting warm since Phase 3.

## Known Stubs

None. The seeded row is not a stub: it is the deliberate, documented subject of T-4-64 and it is
removed in Phase 5 together with `actor.py`.

## Self-Check: PASSED

- `docker/entrypoint.sh` — FOUND
- `.planning/phases/04-task-lists-tasks/evidence/04-11-seed-idempotence.txt` — FOUND
- `.planning/phases/04-task-lists-tasks/evidence/04-11-cold-start.txt` — FOUND
- commit `2c2acab` — FOUND
- commit `59f7411` — FOUND
