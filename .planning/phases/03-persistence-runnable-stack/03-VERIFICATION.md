---
phase: 03-persistence-runnable-stack
verified: 2026-09-19T03:11:57Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
overrides:
  - must_have: "docker-compose.yml binds PostgreSQL to loopback only (WR-05)"
    reason: "Locked decision D-15: host-side make test and docker compose up must reach the same db container over 5432:5432; the review flagged the LAN-exposure risk but the user explicitly kept the binding as-is rather than accepting the review's fix. Recorded as OPEN — not accepted in 03-REVIEW.md, not a phase-goal blocker (no roadmap success criterion requires a loopback-only bind)."
    accepted_by: "pablo.gutierrez (project owner, via 03-REVIEW.md WR-05 resolution)"
    accepted_at: "2026-09-19T02:50:29Z"
---

# Phase 3: Persistence & Runnable Stack Verification Report

**Phase Goal:** The application talks to a real PostgreSQL through mapped repositories and an
explicit transaction boundary, and an evaluator can start the whole stack with one command.
**Verified:** 2026-09-19T03:11:57Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Phase 3 Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `docker compose up` on an empty volume starts PostgreSQL and the API, the API waits for a genuinely ready database, applies Alembic migrations automatically, and `GET /health` returns liveness plus database readiness and backs the container healthcheck | ✓ VERIFIED | Live stack observed: `docker compose ps` shows `test-db-1` and `test-api-1` both `healthy`. `curl localhost:8000/health` → `200 {"status":"ok","checks":{"database":"ok"},"version":"0.1.0"}`. Cold-start rehearsal with stop/start of `db` recorded in `evidence/03-10-cold-start.txt` (container goes `unhealthy` and `/health` answers 503 with the same body shape when the DB is stopped, proving the healthcheck is wired to the DB, not just process liveness). Entrypoint (`docker/entrypoint.sh`) runs a bounded SQLAlchemy readiness probe then `alembic upgrade head` then `exec uvicorn`, confirmed by reading the file. |
| 2 | SQLAlchemy 2.0 async ORM models are separate from the domain entities, relationships use `lazy="raise"`, and repositories return domain objects only — a test that reads an entity outside the session never raises `MissingGreenlet` | ✓ VERIFIED | `src/taskmanager/infrastructure/db/models.py` defines `UserRow`/`TaskListRow`/`TaskRow`, structurally separate from `domain/entities/*`; `TaskListRow.tasks` relationship declared `lazy="raise", passive_deletes=True`. `tests/integration/test_repositories_task_lists.py::test_a_returned_entity_is_readable_after_the_session_is_gone` reads every field of a returned entity after `session.close()` with no exception, and `test_touching_the_tasks_relationship_raises_instead_of_lazy_loading` proves the `lazy="raise"` refusal. Both pass under `make test` against real Postgres. |
| 3 | The Alembic baseline migration creates the schema with `task_lists.owner_id`, VARCHAR + CHECK constraints for status and priority, timezone-aware UTC timestamps, and deleting a list removes its tasks | ✓ VERIFIED | `migrations/versions/0001_baseline.py` creates `task_lists.owner_id` (FK `ON DELETE CASCADE` to `users.id`), `tasks.status`/`tasks.priority` as `String` columns with `CheckConstraint` value lists (`ck_tasks_status`, `ck_tasks_priority`), every timestamp column as `DateTime(timezone=True)`. `tasks.task_list_id` FK is `ON DELETE CASCADE` — deleting a list cascades to its tasks. `tests/integration/test_constraints.py` and `test_migrations.py` (per 03-05-PLAN scope) exercise the constraint set and the migrate/downgrade cycle; the full suite (which includes them) is green. |
| 4 | The use case owns the transaction: a UnitOfWork commits exactly once on success and rolls back on a raised `DomainError`, and no `.commit()` call exists anywhere under `infrastructure/repositories/` (shipped path: `infrastructure/db/repositories/`) | ✓ VERIFIED | `src/taskmanager/infrastructure/db/unit_of_work.py::SqlAlchemyUnitOfWork` — `commit()` sets `_finished`, `__aexit__` rolls back only `if not self._finished`, returns `None` (never swallows). Proven by `tests/integration/test_unit_of_work.py::test_a_successful_block_commits_once`, `test_a_domain_error_leaves_nothing_written`, `test_an_uncommitted_block_is_rolled_back`, `test_a_committed_write_is_invisible_outside_the_test_transaction` (D-01 isolation), `test_rollback_is_not_performed_twice`. The no-commit rule is enforced by `tests/architecture/test_no_commit_in_repositories.py`, a source-text scan requiring `task_lists.py`, `tasks.py`, `users.py` to be present and forbidding `.commit()` in any of them — passing today. Path discrepancy (`infrastructure/db/repositories/` vs. roadmap's literal `infrastructure/repositories/`) is cosmetic; the architectural property (no repository ends its own transaction) holds regardless of directory name, and CR-01 (the one defect that broke this boundary — a `get_uow` that entered the block itself) was found by code review and fixed in commit `f3747a5`, confirmed present in the current `dependencies.py` (`get_uow` is a plain `def` returning a closed UoW; `__aenter__` now refuses re-entry). |
| 5 | Integration tests run against real PostgreSQL with per-test isolation, and the full gate (lint, typecheck, architecture, tests) is green | ✓ VERIFIED | Ran all four gates myself against the live `test-db-1`/`test-api-1` stack: `make lint` → black/isort/flake8 clean; `make typecheck` → mypy "Success: no issues found in 99 source files"; `make arch` → import-linter "Contracts: 3 kept, 0 broken"; `make test` → **293 passed**, coverage **100.00%** over `src/taskmanager` (`Required test coverage of 75% reached`). Per-test isolation (D-01 savepoint/rollback pattern) confirmed by reading `tests/integration/conftest.py`-driven fixtures and the isolation-proving test above. |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/taskmanager/infrastructure/db/models.py` | ORM row classes, separate from entities, `lazy="raise"` | ✓ VERIFIED | Present, substantive, correctly separates persistence shape from domain (DB-03). |
| `src/taskmanager/infrastructure/db/mappers.py` | Explicit `to_entity()`/`to_row()`/`apply_*` per aggregate | ✓ VERIFIED | 9 functions, all substantive; `_aware()` guard implements WR-05 (naive datetime → infrastructure fault, not domain ValidationError). |
| `src/taskmanager/infrastructure/db/repositories/{task_lists,tasks,users}.py` | Three repository adapters, no `.commit()` | ✓ VERIFIED | Exist, scanned and enforced by `tests/architecture/test_no_commit_in_repositories.py`; wired into `SqlAlchemyUnitOfWork.__aenter__`. |
| `src/taskmanager/infrastructure/db/unit_of_work.py` | `SqlAlchemyUnitOfWork` adapter, ARC-08 | ✓ VERIFIED | Correct commit/rollback/re-entry-refusal semantics; CR-01 fix confirmed present in current code, not just in SUMMARY narrative. |
| `migrations/versions/0001_baseline.py` | Complete baseline schema | ✓ VERIFIED | All three tables, all D-12 constraint names, working `downgrade()`. |
| `src/taskmanager/presentation/api/health.py` | `GET /health` liveness + DB readiness | ✓ VERIFIED | Live-tested: 200/`"database":"ok"` while stack is up; body shape matches D-08. |
| `docker-compose.yml`, `Dockerfile`, `docker/entrypoint.sh` | One-command runnable stack | ✓ VERIFIED | Live-tested: `docker compose ps` shows both services `healthy`; entrypoint waits, migrates, execs uvicorn. |
| `Makefile` (`up`, `down`, `run`, `docker-test`) | One-command dev/test workflow | ✓ VERIFIED | `make lint/typecheck/arch/test` all run and pass against the live stack. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `presentation/api/dependencies.py::get_uow` | `SqlAlchemyUnitOfWork` | plain `def`, returns closed UoW | ✓ WIRED | Confirmed current code matches the CR-01 fix; SUMMARY's older `async with ... yield` description is stale and correctly superseded per post-execution context. |
| `presentation/api/health.py::health` | `infrastructure/db/engine.py` (`AsyncEngine`) | `Depends(get_engine)` → `SELECT 1` | ✓ WIRED | Live 200/503 behavior confirmed via cold-start evidence and current curl check. |
| `docker-compose.yml api` service | `db` service | `depends_on: condition: service_healthy` + entrypoint retry loop | ✓ WIRED | `docker compose ps` shows both healthy; evidence file shows API correctly reflects DB down/up cycles. |
| `infrastructure/db/repositories/*` | `SqlAlchemyUnitOfWork.__aenter__` | attribute assignment, PORT-typed | ✓ WIRED | Repositories bound in `__aenter__`, deleted in `__aexit__`'s `finally` (WR-01 fix), proven by `test_the_repositories_are_unreachable_outside_the_block`. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Stack is up and both services healthy | `docker compose ps` | `test-db-1 healthy`, `test-api-1 healthy` | ✓ PASS |
| `/health` reports DB readiness | `curl -s -w HTTP_STATUS localhost:8000/health` | `200 {"status":"ok","checks":{"database":"ok"},"version":"0.1.0"}` | ✓ PASS |
| Lint gate | `make lint` | black/isort/flake8 clean | ✓ PASS |
| Typecheck gate | `make typecheck` | mypy: no issues in 99 files | ✓ PASS |
| Architecture gate | `make arch` | import-linter: 3 kept, 0 broken | ✓ PASS |
| Full test + coverage gate | `make test` | 293 passed, 100.00% coverage (≥75% required) | ✓ PASS |

### Probe Execution

No `scripts/*/tests/probe-*.sh` convention used by this project; phase verification is via `make` gate targets and live stack checks (above), all executed directly by the verifier, not sourced from SUMMARY.md claims.

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|-----------------|--------------|--------|----------|
| DB-01 | 03-01, 03-03, 03-07, 03-08, 03-09, 03-11 | Data stored in PostgreSQL via SQLAlchemy 2.0 async + psycopg 3 | ✓ SATISFIED | `requirements.txt`: `SQLAlchemy[asyncio]==2.0.54`, `psycopg[binary]==3.3.5`; `infrastructure/db/engine.py` builds `create_async_engine("postgresql+psycopg://...")`. |
| DB-02 | 03-02, 03-05, 03-10, 03-11 | Schema created/versioned by Alembic; container applies on startup | ✓ SATISFIED | `migrations/versions/0001_baseline.py`; entrypoint runs `alembic upgrade head`; live cold-start evidence. |
| DB-03 | 03-01, 03-04, 03-06, 03-07, 03-11 | ORM models separate from entities, explicit mappers, `lazy="raise"` | ✓ SATISFIED | `models.py`, `mappers.py`, `lazy="raise"` on `TaskListRow.tasks`, proven by `MissingGreenlet`-avoidance test. |
| DB-04 | 03-01, 03-02, 03-04, 03-05, 03-07, 03-11 | VARCHAR + CHECK for status/priority; TZ-aware UTC timestamps | ✓ SATISFIED | `0001_baseline.py` CheckConstraints; all `DateTime(timezone=True)`. |
| DB-05 | 03-01, 03-02, 03-05, 03-11 | `task_lists.owner_id` from first migration; cascading delete | ✓ SATISFIED | FK `owner_id → users.id ON DELETE CASCADE`; `tasks.task_list_id → task_lists.id ON DELETE CASCADE`. |
| ARC-08 | 03-06, 03-07, 03-08, 03-09, 03-11 | Transactions owned by UnitOfWork, committed explicitly by the use case, never in `yield` dependency teardown | ✓ SATISFIED | `get_uow` is a plain `def` (not `yield`); commit/rollback semantics proven by `test_unit_of_work.py`; CR-01 fix verified present in current code. |
| DOCK-02 | 03-02, 03-10 | `docker-compose.yml` starts API + PostgreSQL with one command; API waits for healthy DB, applies migrations | ✓ SATISFIED | Live `docker compose ps` both healthy; entrypoint waits + migrates. |
| DOCK-03 | 03-09, 03-10 | `/health` reports liveness and DB readiness and backs the container healthcheck | ✓ SATISFIED | Live `curl` 200 with `"database":"ok"`; `Dockerfile HEALTHCHECK` targets `/health`; cold-start evidence shows the healthcheck flips with DB stop/start. |

No orphaned requirements: `REQUIREMENTS.md` maps exactly these eight IDs to Phase 3, and all eight appear in at least one plan's `requirements:` frontmatter field.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | No `TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/`PLACEHOLDER` markers found in any file touched by Phase 3 commits (`15423a9^..3f911fe`) | — | None — clean scan |
| `docker-compose.yml:42` | `ports: "5432:5432"` | PostgreSQL published on `0.0.0.0` with fixed dev credentials (WR-05) | ⚠️ WARNING (open by deliberate user decision, D-15) | Not a phase-goal blocker: no roadmap success criterion requires loopback-only binding; documented as OPEN — not accepted in `03-REVIEW.md`. Recorded as an accepted override above rather than a gap. |
| `src/taskmanager/infrastructure/db/mappers.py` | multiple `require_text` call sites | Blank/whitespace text columns not backed by a CHECK constraint (WR-02) | ⚠️ WARNING (deferred by review — needs a new migration, tracked as follow-up work, not this phase's scope) | Would surface as a 422 on a corrupt row rather than a 500; does not block any Phase 3 roadmap SC. |

Both open review findings above are pre-existing, explicitly-tracked deviations from the reviewer's suggested fix, not undiscovered gaps — the 03-REVIEW.md frontmatter records them as `open_findings` with a stated reason each.

### Human Verification Required

None. Every roadmap success criterion for this phase is either directly observable in the live running stack (health endpoint, `docker compose ps`) or provable by an automated test that was actually executed during this verification pass (not merely cited from SUMMARY.md).

### Gaps Summary

No gaps. All 5 roadmap success criteria for Phase 3 are verified against live, currently running code — not SUMMARY.md narrative. The one Critical review finding (CR-01, the unit-of-work double-entry defect that would have broken ARC-08 on the first routed request) was confirmed fixed in the current `dependencies.py`/`unit_of_work.py`, not merely claimed fixed. All four quality gates (`lint`, `typecheck`, `arch`, `test`) were re-run by the verifier and are green, with the full 293-test suite passing at 100.00% coverage against real PostgreSQL. The two still-open review findings (WR-02, WR-05) are deliberate, explicitly-tracked deviations that do not block any roadmap success criterion, and are recorded as an accepted override / warning rather than silently ignored.

---

_Verified: 2026-09-19T03:11:57Z_
_Verifier: Claude (gsd-verifier)_
