# Phase 3: Persistence & Runnable Stack - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-09-18
**Phase:** 03-persistence-runnable-stack
**Areas discussed:** Integration test strategy, Startup sequence & /health, Baseline migration scope, Compose & local dev layout

---

## Integration test strategy

### Per-test isolation

| Option | Description | Selected |
|--------|-------------|----------|
| Transaction rollback per test | Connection-bound session, outer transaction rolled back at teardown; SAVEPOINT pattern so the use case's `commit()` does not escape | ✓ |
| Truncate all tables after each test | Tests commit for real; `TRUNCATE ... CASCADE` at teardown; slower, hides a misplaced commit | |
| Fresh schema per session, rollback per test | `downgrade base` + `upgrade head` once per session, then rollback per test | |

**User's choice:** Transaction rollback per test (recommended).

### Test schema

| Option | Description | Selected |
|--------|-------------|----------|
| `alembic upgrade head` once per session | The migration itself is under test every run; `alembic check` asserts no drift | ✓ |
| `Base.metadata.create_all` in tests only | Faster, but the migration is only exercised by `docker compose up` | |
| Both, with a dedicated migration test | `create_all` for speed plus one explicit `upgrade head` + `alembic check` test | |

**User's choice:** `alembic upgrade head` once per session (recommended).

### `make test` without a reachable PostgreSQL

| Option | Description | Selected |
|--------|-------------|----------|
| Fail fast with a clear message | Whole suite needs a DB; one session fixture fails with the URL and the remedy | ✓ |
| Skip integration tests when no DB | Auto-skip; risk of green without DB tests and coverage dipping | |
| Split targets: test-unit / test-integration | `make test` = unit only; "one command runs the tests" then points at a subset | |

**User's choice:** Fail fast with a clear message (recommended).

### Test database

| Option | Description | Selected |
|--------|-------------|----------|
| Separate DB in the same Postgres | `taskmanager` + `taskmanager_test` created by an init script; `TEST_DATABASE_URL` or derived | ✓ |
| Same database as the app | Fewer moving parts; a slip hits dev data | |
| Ephemeral DB per pytest session | `CREATE DATABASE ..._<random>`; needs elevated role, adds seconds | |

**User's choice:** Separate DB in the same Postgres (recommended).

---

## Startup sequence & /health

### Where migrations run

| Option | Description | Selected |
|--------|-------------|----------|
| Container entrypoint script | wait → `alembic upgrade head` → `exec uvicorn`; works outside compose; app import side-effect free | ✓ |
| One-shot compose `migrate` service | `service_completed_successfully`; only compose knows the ordering | |
| In the FastAPI lifespan | Fewest files; every test app would migrate; replicas race | |

**User's choice:** Container entrypoint script (recommended).

### Database readiness

| Option | Description | Selected |
|--------|-------------|----------|
| Both: compose healthcheck + entrypoint retry | `depends_on: service_healthy` with `pg_isready -h 127.0.0.1` and a bounded psycopg retry loop | ✓ |
| Compose healthcheck only | Minimal; `docker run` or a restarted DB races | |
| Entrypoint retry loop only | Works everywhere; compose cannot express the dependency | |

**User's choice:** Both (recommended).

### `/health` contract

| Option | Description | Selected |
|--------|-------------|----------|
| 200/503 with a small status body | `{status, checks.database, version}`; `SELECT 1` with ~2 s timeout; plain JSON, not problem+json | ✓ |
| Always 200, status in the body | Container healthcheck would have to parse JSON | |
| Two endpoints `/health/live` + `/health/ready` | Kubernetes-style split; roadmap names a single `/health` | |

**User's choice:** 200/503 with a small status body (recommended).

### Container healthcheck

| Option | Description | Selected |
|--------|-------------|----------|
| `python -c` urllib probe in the Dockerfile `HEALTHCHECK` | No curl in the slim image; applies with or without compose | ✓ |
| Install curl in the runtime image | +~5 MB; familiar | |
| Healthcheck only in docker-compose.yml | `docker run` alone reports no health | |

**User's choice:** `python -c` urllib probe in the Dockerfile (recommended).

---

## Baseline migration scope

### Scope of revision 0001

| Option | Description | Selected |
|--------|-------------|----------|
| Complete schema in one baseline | users, task_lists (owner_id FK), tasks (nullable assignee_id FK); Phase 5 adds behaviour, not columns | ✓ |
| Phase 3/4 schema now, Phase 5 migration later | Omit `assignee_id`; Phase 5 ships `0002`; ORM diverges from the entity until then | |
| Complete schema plus a deliberate second migration | Baseline has everything; an honest follow-up revision when a query needs it | |

**User's choice:** Complete schema in one baseline (recommended).

### Database-level integrity rules (multi-select)

| Option | Description | Selected |
|--------|-------------|----------|
| `UNIQUE (owner_id, name)` on task_lists | Race-proof backstop for LIST-06's 409 | ✓ |
| `UNIQUE users.email` (case-insensitive) | Unique index on `lower(email)` | ✓ |
| `CHECK completed_at` consistency | `(status = 'completed') = (completed_at IS NOT NULL)`, mirrors `Task.__post_init__` | ✓ |
| assignee FK `ON DELETE SET NULL` | Deleting a user clears assignments; owner → CASCADE | ✓ |

**User's choice:** All four.

### Repository behaviour on `IntegrityError`

| Option | Description | Selected |
|--------|-------------|----------|
| Translate to the matching `DomainError` | Inspect the named constraint, raise the same error the pre-check would have raised | ✓ |
| Let `IntegrityError` propagate as a 500 | Pre-check is the only friendly path; races hit the catch-all | |
| Translate in `UnitOfWork.commit()` | One place, far from the operation; grab-bag mapping table | |

**User's choice:** Translate to the matching `DomainError` (recommended).

---

## Compose & local dev layout

### Services and `make docker-test`

| Option | Description | Selected |
|--------|-------------|----------|
| api + db; tests via compose `run` on the test stage | Init script creates both DBs; `docker compose run --rm --build test`; `make up`/`down` become real | ✓ |
| api + db + separate db-test service | Two Postgres containers unless profiles hide it | |
| api + db only; docker-test keeps the standalone image | Makefile starts a throwaway Postgres | |

**User's choice:** api + db; tests via compose `run` on the test stage (recommended).

### Configuration and ports

| Option | Description | Selected |
|--------|-------------|----------|
| `.env` via `env_file`, both ports published | `cp .env.example .env`; `.env.example` documents compose vs localhost URL; 8000 and 5432 published | ✓ |
| Values inline in compose, no `.env` | Zero setup; a fake secret lives in a committed file | |
| `.env` via `env_file`, only API port published | Postgres internal; host `make test` needs its own DB | |

**User's choice:** `.env` via `env_file`, both ports published (recommended).

### Development loop inside compose

| Option | Description | Selected |
|--------|-------------|----------|
| No bind mount, production-like image | Host `.venv` + `make run` (`uvicorn --reload`) against the compose Postgres | ✓ |
| Bind mount + `--reload` by default | Running container differs from the built image | |
| Optional override file | `docker-compose.override.yml` adds mount + reload for those who want it | |

**User's choice:** No bind mount, production-like image (recommended).

---

## Claude's Discretion

- Engine/session lifetime (built in the composition root, disposed in lifespan; must not
  connect at import time; `expire_on_commit=False`, `pool_pre_ping=True`).
- ORM model and mapper module layout; `lazy="raise"` on every relationship; the
  `MissingGreenlet` proof test.
- `UnitOfWork` adapter internals and the `Depends` factory Phase 4 will consume.
- `SystemClock` adapter and the ADR settling the deferred WR-05 naive-datetime question.
- Alembic wiring details (sync `env.py`, autogenerate metadata), entrypoint script language,
  retry counts, compose project name, restart policies, optional compose profile for `test`.

## Deferred Ideas

- `/health/live` + `/health/ready` split — not needed for this deliverable.
- `docker-compose.override.yml` with bind mount + reload — not shipped; `make run` covers it.
- A second Alembic revision purely to demonstrate versioning — rejected as a fake artifact.
- Ephemeral per-session databases — revisit only if Phase 6 adds `pytest-xdist`.
