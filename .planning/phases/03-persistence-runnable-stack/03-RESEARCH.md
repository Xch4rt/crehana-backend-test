# Phase 3: Persistence & Runnable Stack - Research

**Researched:** 2026-09-18
**Domain:** Async SQLAlchemy 2.0 persistence on PostgreSQL, Alembic migrations, Docker Compose runnable stack, integration-test isolation
**Confidence:** HIGH (every API shape below was executed against the repository's own pinned `.venv`, not recalled)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Integration test strategy**

- **D-01:** Per-test isolation is a transaction rollback: each integration test gets a session
  bound to a connection whose outer transaction is opened by the fixture and rolled back at
  teardown. The `UnitOfWork` under test must still be able to call `commit()`, so the session
  is configured with the SAVEPOINT pattern (`join_transaction_mode="create_savepoint"`); the
  use case's commit releases a savepoint, the fixture's rollback discards everything. A test
  reads a row after `commit()` from a *second* connection to prove nothing leaked past the
  outer transaction. No `TRUNCATE`, no per-test database.
- **D-02:** The test schema is produced by the real migration: a session-scoped fixture runs
  `alembic upgrade head` against the test database once (and `downgrade base` first when the
  schema already exists, so a stale test DB never masks a migration change). One test runs
  `alembic check` and asserts no drift between the ORM models and the migration history.
  `Base.metadata.create_all()` is never used, not even in tests (ADR-007; research
  Anti-Pattern 9).
- **D-03:** `make test` runs the *whole* suite (unit + integration) and requires a reachable
  PostgreSQL. When `DATABASE_URL` is unreachable, a session-scoped fixture fails once, fast,
  with a message naming the URL and the remedy (`make up` or `make docker-test`) — never
  dozens of connection tracebacks, never an auto-skip. The 75% coverage gate is computed over
  the full suite, exactly as in CI. `make docker-test` remains the zero-host-setup path.
- **D-04:** Integration tests use a separate database, `taskmanager_test`, in the same
  PostgreSQL instance as the application database `taskmanager`. The compose `db` service
  creates both through an init script in `docker-entrypoint-initdb.d`. Tests read
  `TEST_DATABASE_URL` when set and otherwise derive it from `DATABASE_URL` by replacing the
  database name with `taskmanager_test`; the derivation is unit-tested. CI keeps its existing
  `taskmanager_test` service database.
- **D-05:** Integration tests carry the `integration` marker already declared in `pytest.ini`;
  the marker is informational (selectable with `-m`), not a switch that changes what
  `make test` runs.

**Startup sequence and `/health`**

- **D-06:** `alembic upgrade head` runs in a container entrypoint script
  (`docker/entrypoint.sh` or equivalent, copied into the runtime image): wait for the
  database → migrate → `exec uvicorn --factory taskmanager.main:create_app`. Migrations never
  run inside the FastAPI lifespan or inside `create_app()`, so importing and building the app
  stays free of database side effects for tests, and multiple replicas cannot race on
  startup. The `test` image stage does not run the entrypoint's migration step; the pytest
  fixture from D-02 owns the test schema.
- **D-07:** Database readiness is enforced twice, and both are documented: (a) compose
  `api` declares `depends_on: db: condition: service_healthy` and `db` has a healthcheck
  running `pg_isready -h 127.0.0.1 -U <user> -d <db>` (the `-h 127.0.0.1` is load-bearing —
  the image's init-time server listens only on a Unix socket; same reasoning as the CI
  workflow); (b) the entrypoint runs a bounded retry loop (e.g. 30 attempts, 1 s apart) that
  opens a real psycopg connection and executes `SELECT 1` before migrating, so the image is
  also correct under plain `docker run` or after a database restart. Exhausting the retries
  exits non-zero with a clear message.
- **D-08:** `GET /health` returns a small status document, never problem+json:
  `{"status": "ok" | "degraded", "checks": {"database": "ok" | "unavailable"}, "version": "<app version>"}`.
  The database check executes `SELECT 1` through the application's engine with a short
  timeout (about 2 s). All checks ok → HTTP 200; database unavailable → HTTP 503 with the same
  body shape. The 503 is what makes the container healthcheck fail, which is the intent. The
  endpoint is unauthenticated (Phase 5 must not protect it) and lives in `presentation`.
- **D-09:** The container healthcheck is declared in the `Dockerfile` (`HEALTHCHECK`) using a
  Python one-liner (`urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=3)`, exit
  0 only on status 200) so the slim runtime image needs no `curl`/`wget`. Compose inherits it;
  `docker compose ps` shows `healthy` only once the API answers 200.

**Baseline migration scope and integrity rules**

- **D-10:** A single baseline revision (`0001_baseline`) creates the complete schema the
  domain entities already describe: `users` (id, email, password_hash, created_at),
  `task_lists` (id, owner_id → users, name, created_at, updated_at) and `tasks` (id,
  task_list_id → task_lists, title, description, status, priority, due_date, assignee_id →
  users nullable, created_at, updated_at, completed_at). Phase 5 adds behaviour, not columns;
  a second revision only appears when a genuine change requires it (never a fake one to
  "show" versioning). The migration has a working `downgrade()`.
- **D-11:** Column types: primary and foreign keys are native `uuid` (ids are generated by
  the application, D-11 of Phase 2 — the database never generates them); every timestamp is
  `TIMESTAMP WITH TIME ZONE` and the application always supplies UTC-aware values (no
  `server_default=now()` for `created_at`/`updated_at`, so the `Clock` port stays the only
  source of time — Phase 2 D-13/D-14); `status` and `priority` are `VARCHAR` with named
  `CHECK` constraints listing the enum values (DB-04), not PostgreSQL `ENUM` types.
- **D-12:** Integrity rules enforced by the database, each with an explicit constraint name
  so it can be recognised in code:
  - `uq_task_lists_owner_id_name`: `UNIQUE (owner_id, name)` on `task_lists` — the
    race-proof backstop for LIST-06's 409.
  - `uq_users_email_lower`: unique index on `lower(email)` on `users` — case-insensitive
    email uniqueness.
  - `ck_tasks_completed_at_matches_status`: `CHECK ((status = 'completed') = (completed_at IS
    NOT NULL))` — the same invariant `Task.__post_init__` enforces (Phase 2 review fix WR-07).
  - `ck_tasks_status`, `ck_tasks_priority`: the DB-04 value lists.
  - Foreign keys: `task_lists.owner_id → users.id ON DELETE CASCADE`,
    `tasks.task_list_id → task_lists.id ON DELETE CASCADE` (DB-05),
    `tasks.assignee_id → users.id ON DELETE SET NULL`.
  - Indexes on `tasks.task_list_id` (plus `status`, `priority` as a composite or separate
    indexes — planner's call) to serve the Phase 4 filtered listing and completion aggregate.
- **D-13:** Repositories translate database rejections into domain errors: each repository
  catches `sqlalchemy.exc.IntegrityError`, inspects the violated constraint name (psycopg 3
  exposes it via `diag.constraint_name`) and raises the same `DomainError` subclass the use
  case's pre-check would have raised (`uq_task_lists_owner_id_name` → the list-name conflict
  error, `uq_users_email_lower` → the email conflict error, FK violations → the matching
  not-found error). An unrecognised constraint re-raises the original exception so it
  surfaces as a 500. No SQLAlchemy exception ever crosses into `application`.

**Compose and local development layout**

- **D-14:** `docker-compose.yml` defines exactly two long-running services: `db`
  (`postgres:18-alpine`, named volume for data, init script creating `taskmanager` and
  `taskmanager_test`, the D-07 healthcheck) and `api` (built from the repository
  `Dockerfile` runtime stage, `depends_on` healthy `db`, entrypoint from D-06). A third
  service, `test`, is built from the Dockerfile `test` stage, points at `taskmanager_test`
  and is meant to be invoked, not started: `make docker-test` becomes
  `docker compose run --rm --build test`. `make up` → `docker compose up --build`,
  `make down` → `docker compose down` (with `-v` documented as the reset). ADR-017 and
  ADR-018 get a follow-up ADR recording that the placeholders were replaced as promised and
  the `test` stage now runs through compose.
- **D-15:** Configuration enters compose through `env_file: .env`; the evaluator's setup is
  `cp .env.example .env` once, and compose fails with a clear error when `.env` is missing
  (it must not silently start with defaults — no secret has a default, Phase 1 D-16). Inside
  compose the database host is `db`, on the host it is `localhost`; `.env.example` documents
  both values for `DATABASE_URL` with a comment saying which one to use where. The `api`
  service overrides `DATABASE_URL` for the compose network in the compose file itself, so a
  developer's `.env` can stay on `localhost` for `make test` / `make run`. Ports published on
  the host: API `8000:8000`, PostgreSQL `5432:5432`, so host-side `make test` reaches the
  same `db` container.
- **D-16:** `docker compose up` runs the production-like image: no bind mount of `src/`, no
  `--reload`, non-root user, the real entrypoint and healthcheck. Developers who want a fast
  edit-run loop use the host virtualenv against the compose database via a new `make run`
  target (`uvicorn --factory taskmanager.main:create_app --reload`). No
  `docker-compose.override.yml` is shipped.

### Claude's Discretion

- **Engine and session lifetime.** `.planning/research/STACK.md` sketches a module-level
  `create_async_engine` while `.planning/research/ARCHITECTURE.md` Anti-Pattern 10 forbids a
  module-level global engine; resolve this in favour of building the engine from `Settings`
  inside the composition root (`create_app()` or a factory it calls) and disposing it in the
  lifespan. Hard constraints either way: `create_app()` must still be constructible in unit
  tests with a fake `DATABASE_URL` and no database (creating an engine does not connect;
  connecting must happen lazily), `async_sessionmaker(expire_on_commit=False)` is mandatory
  (PITFALLS Pitfall 2), and `pool_pre_ping=True`.
- **ORM model / mapper layout.** Declarative models with `Mapped[...]`/`mapped_column()`
  under `infrastructure/db/models.py` (or one module per table) and explicit mapper
  functions `to_entity()` / `to_row()` per aggregate (research Pattern 5, DB-03). Any
  relationship declared on the models uses `lazy="raise"`; repositories return domain
  entities only, and a test proves reading a returned entity outside the session never raises
  `MissingGreenlet` (roadmap SC-2). Imperative mapping of the dataclasses themselves is *not*
  acceptable — it would fuse the entity and the persistence model that DB-03 keeps apart.
- **`UnitOfWork` adapter details.** One `AsyncSession` per `UnitOfWork` instance, opened in
  `__aenter__`, committed only by an explicit `commit()`, rolled back in `__aexit__` when
  nothing was committed or an exception is in flight (the normative rule from the Phase 2
  review fix WR-06). Repository attributes must be annotated with the port types
  (`self.tasks: TaskRepository`) — mypy checks mutable Protocol members invariantly (Phase 2
  finding). No `.commit()` call may exist anywhere under `infrastructure/repositories/`
  (roadmap SC-4); a grep-based test or the code review enforces it.
- **How routers obtain a `UnitOfWork`.** A FastAPI dependency that *constructs* a UoW from
  the app's session factory and yields it, never committing in its teardown (ARC-08;
  research Anti-Pattern 1). Phase 3 needs it only for `/health` wiring and tests; Phase 4 is
  the first real consumer — leave a documented, tested factory.
- **`SystemClock` adapter** for the `Clock` port (returns `datetime.now(UTC)`), plus the
  decision the Phase 2 review deferred (WR-05): now that the only adapters that can produce a
  naive datetime exist (clock and mappers), decide whether a naive value read from the
  database stays a domain `ValidationError` (Phase 2 D-14) or becomes an infrastructure fault
  raised by the mapper before the entity is built. Record the outcome as an ADR that
  explicitly refines D-14; do not leave it implicit.
- **Alembic wiring**: `alembic.ini` at the root, a *synchronous* `env.py` reusing the same
  `postgresql+psycopg://` URL from `Settings` (the single-driver argument of ADR-006),
  autogenerate compared against the models' `metadata` so `alembic check` is meaningful.
- Exact entrypoint script language (POSIX `sh` vs a small Python module invoked by the
  image), exact retry counts, compose project name, restart policies, and whether the
  `test` service is hidden behind a compose profile.

### Deferred Ideas (OUT OF SCOPE)

- Kubernetes-style split `/health/live` + `/health/ready` — considered; a single `/health`
  with 200/503 was chosen. Revisit only if a deployment story appears (out of scope).
- `docker-compose.override.yml` with bind mount + `--reload` for developers — not shipped;
  `make run` on the host covers the fast loop. Could be added as an undocumented convenience
  later.
- A second Alembic revision purely to demonstrate versioning — rejected as a fake artifact;
  a real one will appear if and when Phase 4/5 needs an index or column.
- Ephemeral per-session databases (`CREATE DATABASE taskmanager_test_<random>`) — not needed
  with transaction rollback; note for Phase 6 if test parallelism (`pytest-xdist`) is
  considered.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DB-01 | Data is stored in PostgreSQL via SQLAlchemy 2.0 async with psycopg 3 | §Pattern 1 (engine/session lifetime), §Pattern 3 (UoW adapter), verified `create_async_engine` + `async_sessionmaker(expire_on_commit=False)` shapes |
| DB-02 | Schema is created and versioned by Alembic migrations; the container applies them on startup | §Pattern 5 (sync `env.py`), §Pitfall 3/4/5 (interpolation, `fileConfig`, connection sharing), §Pattern 7 (entrypoint) |
| DB-03 | ORM models are separate from domain entities with explicit mappers; relationships use `lazy="raise"` | §Pattern 2 (models + mappers), §Pitfall 1 (`MissingGreenlet`), verified `lazy="raise_on_sql"` → `InvalidRequestError` |
| DB-04 | Status and priority persist as VARCHAR + CHECK constraints; all timestamps are timezone-aware UTC | §Pattern 4 (naming convention + rendered DDL, verified), §Pitfall 8 (`alembic check` cannot see CHECKs) |
| DB-05 | `task_lists.owner_id` exists from the first migration; deleting a list deletes its tasks | §Pattern 4 — verified `ON DELETE CASCADE` DDL render with the exact constraint names of D-12 |
| ARC-08 | Transactions are owned by a UnitOfWork committed explicitly by the use case | §Pattern 3, §Validation Architecture (commit-once / rollback-on-DomainError tests, `.commit()` grep gate) |
| DOCK-02 | `docker-compose.yml` starts API + PostgreSQL with one command; API waits for a healthy DB and applies migrations | §Pattern 6 (compose), §Pattern 7 (entrypoint), verified `environment` > `env_file` precedence and initdb-on-empty-volume semantics |
| DOCK-03 | `/health` reports liveness and database readiness and backs the container healthcheck | §Pattern 8 (`/health` + Dockerfile `HEALTHCHECK`), verified Compose inherits the image healthcheck |
</phase_requirements>

## Summary

This phase adds no new dependencies. Everything it needs — `SQLAlchemy[asyncio]==2.0.54`,
`psycopg[binary]==3.3.5`, `alembic==1.20.0` — is already exact-pinned in `requirements.txt` and
already installed in `.venv`. That made it possible to verify every API shape below by
*executing* it against the project's own interpreter rather than recalling it, which is the
right posture given how much of this phase is "the idiom that changed between versions".

The research found **seven concrete traps that would each cost a red build**, all verified by
execution: (1) `join_transaction_mode` defaults to `conditional_savepoint`, which silently
degrades to `rollback_only` for the exact fixture shape D-01 describes — it must be passed
explicitly; (2) `psycopg.connect()` **rejects** the `postgresql+psycopg://` URL the project
uses everywhere, so the D-07 entrypoint probe cannot naively reuse `DATABASE_URL`;
(3) `alembic.config.Config.set_main_option()` raises `ValueError` on any `%` in the URL, so
the sync `env.py` must build its engine directly instead of writing the URL back into the ini;
(4) Alembic's stock `env.py` calls `logging.config.fileConfig()`, which **disables every
existing logger** — demonstrated live, and it would break the two `caplog` assertions already
in `tests/api/test_error_contract.py`; (5) the current `Dockerfile` copies only
`requirements*.txt`, `pyproject.toml`, `src` and `tests`, so `alembic.ini`, the migrations
directory and `docker/entrypoint.sh` are invisible to both the `runtime` and `test` stages
until new `COPY` lines are added; (6) `tests/unit/test_settings.py` asserts **exact equality**
between `.env.example` keys and `Settings.model_fields`, so `TEST_DATABASE_URL` cannot be
documented in `.env.example` without also becoming a `Settings` field — and with
`extra="forbid"`, an undeclared key in a developer's `.env` makes the app fail at boot;
(7) Alembic autogenerate cannot see `CHECK` constraints at all, so `alembic check` will never
prove DB-04 — only an integration test that tries to insert a forbidden value will.

Everything else lines up cleanly. A `MetaData(naming_convention=...)` produces *exactly* the
constraint names D-12 specifies (verified by compiling the DDL); `sa.Uuid()` renders native
PostgreSQL `UUID` and `sa.DateTime(timezone=True)` renders `TIMESTAMP WITH TIME ZONE`;
Alembic 1.20's `generic` template already ships `path_separator = os` so no deprecation
warning fires under `filterwarnings = error`; `command.check()` raises a typed
`AutogenerateDiffsDetected` that a test can assert on; and Alembic 1.20 genuinely compares
PostgreSQL expression indexes, so the `lower(email)` unique index will not show up as
permanent drift.

**Primary recommendation:** Build the engine in the composition root from `Settings`, pass
`join_transaction_mode="create_savepoint"` explicitly in the integration fixture, make the
Alembic `env.py` self-sufficient (own engine, guarded `fileConfig`, `config.attributes`
connection sharing), and add the five missing `COPY` lines to the Dockerfile before anything
else — that last one is the difference between `docker compose up` working and the entrypoint
dying on a missing `alembic.ini`.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| ORM table definitions, column types, constraints | Infrastructure (`infrastructure/db/models.py`) | — | SQLAlchemy is forbidden in `domain`/`application` by `.importlinter`; the ORM model is a persistence detail (DB-03) |
| ORM ↔ domain entity translation | Infrastructure (`infrastructure/db/mappers.py`) | — | The mapper is the only module that legally knows both shapes (Pattern 5) |
| Repository adapters (the three ports) | Infrastructure (`infrastructure/db/repositories/`) | — | Adapters implement application-declared Protocols; the Protocol lives above, the adapter below |
| Transaction boundary (commit/rollback) | Application (use case calls `uow.commit()`) | Infrastructure (adapter performs it) | ARC-08: the *decision* to commit is a use-case decision; the *mechanism* is an adapter |
| `IntegrityError` → `DomainError` translation | Infrastructure (repository) | — | D-13: no SQLAlchemy exception may cross into `application` |
| Engine + session factory construction | Composition root (`main.create_app`) | Infrastructure (`infrastructure/db/engine.py` factory fn) | Anti-Pattern 10 forbids a module-level global engine; `main` is the only layer allowed to depend on everything |
| Engine disposal | Composition root (FastAPI lifespan) | — | Symmetrical with construction; the lifespan is the app's own lifecycle hook |
| UoW dependency wiring | Presentation (`presentation/api/dependencies.py`) | — | Pattern 7: `Depends` is the composition wiring for request-scoped objects |
| `/health` route + status document | Presentation (`presentation/api/health.py`) | Infrastructure (engine `SELECT 1`) | D-08: an HTTP contract, unauthenticated, owned by presentation |
| Schema versioning (Alembic) | Repository root (`alembic.ini`, `migrations/`) | Infrastructure (models' `metadata` as `target_metadata`) | Migrations are a deployment artifact, not importable application code; keeping them outside `src/` keeps them out of coverage and out of import-linter's graph |
| Database readiness wait + migrate + exec | Container entrypoint (`docker/entrypoint.sh`) | Compose (`depends_on: service_healthy`) | D-06/D-07: must work under plain `docker run` too, so it cannot live only in compose |
| Container liveness reporting | Dockerfile `HEALTHCHECK` | Compose (inherits it) | D-09: verified that Compose inherits the image's `HEALTHCHECK` unless overridden |
| Test schema provisioning | Test fixture (`tests/integration/conftest.py`) | Alembic programmatic API | D-02: the migration under test provides the schema; never `create_all()` |
| `SystemClock` | Infrastructure (`infrastructure/clock.py`) | — | The `Clock` port is an application Protocol; the system clock is an adapter |

## Project Constraints (from CLAUDE.md)

These are as binding as the locked decisions above. Each is a gate that fails a build.

| # | Directive | Consequence for this phase |
|---|-----------|----------------------------|
| C-1 | Import direction `main > presentation > infrastructure > application > domain`; never upward | The `/health` router may import `infrastructure.db`; `infrastructure.db` may **not** import `presentation` |
| C-2 | `taskmanager.domain` imports **no third-party library at all** | No `Mapped`, no `mapped_column`, no `sa.` anywhere under `domain/` |
| C-3 | `taskmanager.application` imports no web framework and no ORM (`fastapi`, `starlette`, `sqlalchemy`, `alembic` forbidden in `.importlinter`) | Repository adapters must return domain entities; an `IntegrityError` may never escape `infrastructure` (D-13) |
| C-4 | `fastapi.HTTPException` may never be raised outside `presentation` | `/health`'s 503 must come from a `Response`/`JSONResponse` with an explicit status, or an `HTTPException` raised *inside* the presentation module — never from an infrastructure probe |
| C-5 | `make lint && make typecheck && make arch && make test` green before every commit; pre-commit runs the same set | New infra code must pass mypy **strict** with no `type: ignore` |
| C-6 | Coverage gated at 75% over `src/taskmanager`, never reached with `pragma: no cover` or a coverage `omit` | Every new branch under `src/taskmanager/infrastructure/db/` needs a test. Migrations under `migrations/` are outside the `taskmanager` package, so they carry **no** coverage burden |
| C-7 | A new gate must be added in **both** `.pre-commit-config.yaml` and `.github/workflows/ci.yml` — neither derives from the other | If the `.commit()` grep gate or a new lint path is added, it goes in both files (plus the Makefile) |
| C-8 | No secret ever gets a default value in code; every setting read through `infrastructure.config.settings` and documented in `.env.example`; `.env` never committed | `TEST_DATABASE_URL` must be a `Settings` field *and* a `.env.example` key, or neither — see Pitfall 6 |
| C-9 | Everything in English; git commits carry no AI attribution trailer | Applies to migration docstrings and ADR text |

## Standard Stack

### Core — already pinned, no installation step in this phase

| Library | Pinned version | Purpose | Verification |
|---------|---------------|---------|--------------|
| `SQLAlchemy[asyncio]` | `2.0.54` | Async ORM + Core | `[VERIFIED: .venv import]` `sqlalchemy.__version__ == '2.0.54'` |
| `psycopg[binary]` | `3.3.5` | PostgreSQL driver, sync **and** async behind one URL | `[VERIFIED: .venv import]` `psycopg.__version__ == '3.3.5'` |
| `alembic` | `1.20.0` | Schema migrations | `[VERIFIED: .venv import]` `alembic.__version__ == '1.20.0'` |
| `pytest-asyncio` | `1.4.0` | Async fixtures/tests, `auto` mode | `[VERIFIED: .venv import]`; `pytest_asyncio.fixture(loop_scope=...)` parameter confirmed present |
| `postgres` image | `18-alpine` | Database (ADR-013) | `[CITED: .github/workflows/ci.yml]` already in use in CI |
| `python` image | `3.13-slim-trixie` | Runtime/builder/test stages | `[CITED: Dockerfile]` already in use |

**Installation:** none. `requirements.txt` is unchanged by this phase.
If the planner believes a new package is needed, that is a signal to re-read this document —
every capability below is achievable with what is already pinned.

### Alternatives Considered (and already rejected by locked ADRs — do not reopen)

| Instead of | Could Use | Why it is closed |
|------------|-----------|------------------|
| `psycopg` 3 | `asyncpg` | ADR-006: forces an async Alembic `env.py` or a second driver, and a second URL |
| Alembic | `Base.metadata.create_all()` | ADR-007 + D-02 + Anti-Pattern 9 |
| Separate ORM models + mappers | `registry.map_imperatively` on the dataclasses | CONTEXT: "not acceptable — it would fuse the entity and the persistence model that DB-03 keeps apart" |
| compose/CI Postgres | `testcontainers` | STACK decision #8; adds a Docker-socket prerequisite to `pytest` |
| Transaction rollback per test | `TRUNCATE ... CASCADE` | D-01; truncation hides a misplaced `.commit()` |

## Package Legitimacy Audit

This phase installs **no new packages**. The three packages it activates were already vetted
and pinned in Phase 1. They were re-checked anyway:

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| `sqlalchemy` | PyPI | ~19 yrs | very high | github.com/sqlalchemy/sqlalchemy | `[OK]` | Approved (already pinned `2.0.54`) |
| `psycopg` | PyPI | ~4 yrs (v3 line) | very high | github.com/psycopg/psycopg | `[OK]` | Approved (already pinned `3.3.5`) |
| `alembic` | PyPI | ~15 yrs | very high | github.com/sqlalchemy/alembic | `[OK]` | Approved (already pinned `1.20.0`) |

`[VERIFIED: slopcheck install sqlalchemy psycopg alembic]` — output `3 OK`, 0 SUS, 0 SLOP.
(The tool then attempted a `pip install` into the system interpreter and was blocked by the
sandbox; the legitimacy verdicts had already been emitted and are what matter here. No
installation was performed and `requirements.txt` was not modified.)

**Packages removed due to slopcheck `[SLOP]` verdict:** none
**Packages flagged as suspicious `[SUS]`:** none

## Architecture Patterns

### System Architecture Diagram

```
                      ┌──────────────────────────────────────────────────┐
  docker compose up   │            compose network                       │
  ───────────────────▶│                                                  │
                      │  ┌────────────┐  pg_isready -h 127.0.0.1         │
                      │  │  db        │◀────── healthcheck ──────┐       │
                      │  │ pg 18      │                          │       │
                      │  │ volume     │  initdb.d/*.sql          │       │
                      │  │            │  → taskmanager           │       │
                      │  │            │  → taskmanager_test      │       │
                      │  └─────▲──────┘                          │       │
                      │        │                    depends_on:  │       │
                      │        │              condition: service_healthy │
                      │        │                                 │       │
                      │  ┌─────┴──────────────────────────────────┴────┐ │
                      │  │  api  (runtime stage, non-root)             │ │
                      │  │                                             │ │
                      │  │   docker/entrypoint.sh                      │ │
                      │  │     1. wait: SELECT 1, bounded retry  ──────┼─┼─▶ db
                      │  │     2. alembic upgrade head  ───────────────┼─┼─▶ db
                      │  │     3. exec uvicorn --factory create_app    │ │
                      │  │                                             │ │
                      │  │   HEALTHCHECK: python urllib → /health      │ │
                      │  └─────────────────────────────────────────────┘ │
                      └──────────────────────────────────────────────────┘

  HTTP request                      in-process flow
  ────────────▶ presentation/api/health.py
                      │
                      │ Depends(get_engine)        ← app.state, built in create_app()
                      ▼
                 engine.connect() ── SELECT 1 (asyncio.timeout ≈2s)
                      │                    │
                 ok → 200               fail → 503   (same body shape, D-08)


  Phase-4 write path (wired, not yet exercised)
  ────────────▶ router ──▶ Depends(get_uow) ──▶ SqlAlchemyUnitOfWork(session_factory)
                                   │
                      use case ── async with uow:  ──▶ uow.tasks.add(entity)
                                     ...                    │
                                   await uow.commit()       │ mapper: entity → row
                                     │                      ▼
                                     │             AsyncSession (expire_on_commit=False)
                                     ▼                      │
                            __aexit__ rollback-if-           ▼
                            not-committed, close       psycopg 3 ──▶ PostgreSQL
                                     ▲                      │
                                     │              IntegrityError
                                     │                      │
                          DomainError ◀── diag.constraint_name lookup (D-13)


  Integration test isolation (D-01)
  ────────────▶ engine.connect() ──▶ conn.begin()  (outer transaction, never committed)
                      │
                      ├─ AsyncSession(bind=conn, join_transaction_mode="create_savepoint")
                      │      └─ UoW.commit() → RELEASE SAVEPOINT   (visible inside conn)
                      │
                      └─ second, independent connection ── SELECT ──▶ sees nothing
                                     │
                        teardown: await transaction.rollback()  → everything discarded
```

### Recommended Project Structure

```
alembic.ini                          # root; script_location = %(here)s/migrations
migrations/                          # NOT "alembic/" — see Pitfall 9
├── env.py                           # synchronous; own engine; guarded fileConfig
├── script.py.mako                   # customised to PEP 604 unions (py3.13 project)
└── versions/
    └── 0001_baseline.py             # the complete schema, with a real downgrade()

docker/
├── entrypoint.sh                    # wait → alembic upgrade head → exec uvicorn
└── initdb/
    └── 01-create-test-database.sql  # CREATE DATABASE taskmanager_test;

docker-compose.yml                   # db + api (+ test, invoked not started)

src/taskmanager/
├── infrastructure/
│   ├── clock.py                     # SystemClock adapter
│   └── db/
│       ├── engine.py                # create_engine_and_session_factory(settings)
│       ├── base.py                  # DeclarativeBase + MetaData(naming_convention)
│       ├── models.py                # UserRow / TaskListRow / TaskRow
│       ├── constraints.py           # the D-12 constraint-name constants (single source)
│       ├── mappers.py               # to_entity() / apply_to_row() per aggregate
│       ├── errors.py                # IntegrityError → DomainError translation (D-13)
│       ├── unit_of_work.py          # SqlAlchemyUnitOfWork
│       └── repositories/
│           ├── tasks.py
│           ├── task_lists.py
│           └── users.py
└── presentation/api/
    ├── dependencies.py              # get_engine / get_session_factory / get_uow
    └── health.py                    # GET /health

tests/
├── integration/
│   ├── conftest.py                  # schema fixture, engine, connection/session, uow
│   ├── test_migrations.py           # alembic check; upgrade/downgrade round trip
│   ├── test_repositories_*.py
│   ├── test_unit_of_work.py         # commit-once / rollback-on-DomainError / isolation
│   └── test_constraints.py          # CHECK + UNIQUE + CASCADE proofs
├── unit/infrastructure/
│   ├── test_mappers.py              # round trip, no DB
│   ├── test_clock.py
│   └── test_database_url.py         # TEST_DATABASE_URL derivation (D-04)
└── architecture/
    └── test_no_commit_in_repositories.py   # SC-4 grep gate
```

> **Naming note.** The structure above says `migrations/`, not `alembic/`. CONTEXT sketched
> `alembic/`, but `.flake8` already carries `extend-exclude = .venv,build,dist,migrations`,
> and `alembic init` defaults to whatever directory name it is given. `migrations/` costs
> nothing and matches an exclusion that already exists. If the planner keeps `alembic/`, the
> `.flake8` exclude must be updated in the same task — otherwise the exclusion is dead
> configuration that reads as an oversight. Either way the choice must be made once and
> applied consistently to `alembic.ini`, `.flake8` and the Dockerfile `COPY` lines.

---

### Pattern 1: Engine built in the composition root, disposed in the lifespan

**What:** `create_app()` builds the async engine and the session factory from `Settings`,
stores them on `app.state`, and disposes the engine in the lifespan shutdown.
**Resolves:** the STACK.md-vs-ARCHITECTURE.md contradiction the CONTEXT flagged.
**Why it satisfies both hard constraints:** `create_async_engine()` does **not** open a
connection — the pool is lazy — so `create_app(Settings(...))` with a fake DSN and no database
running still works, which is exactly what `tests/conftest.py::app` already does today.

```python
# src/taskmanager/infrastructure/db/engine.py
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from taskmanager.infrastructure.config.settings import Settings


def create_engine(settings: Settings) -> AsyncEngine:
    """Build the engine. This opens no connection; the pool is lazy."""
    return create_async_engine(settings.database_url, pool_pre_ping=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    # expire_on_commit=False is mandatory: the default triggers a refresh SELECT on the
    # first attribute read after commit(), which under asyncio is MissingGreenlet.
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
```

```python
# src/taskmanager/main.py (shape)
@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield
    await app.state.engine.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()
    engine = create_engine(resolved)
    app = FastAPI(title=resolved.app_name, version=__version__, lifespan=_lifespan)
    app.state.engine = engine
    app.state.session_factory = create_session_factory(engine)
    register_exception_handlers(app)
    app.include_router(health_router)
    return app
```

> `app.state` is untyped (`starlette.datastructures.State.__getattr__ -> Any`). Under mypy
> strict that is an implicit-`Any` source. Read it back through an explicitly annotated
> dependency (`def get_engine(request: Request) -> AsyncEngine: return cast(AsyncEngine, request.app.state.engine)`)
> or keep a typed module-level `dataclass` container on `app.state`. Decide once, in
> `dependencies.py`, rather than sprinkling casts.

**Anti-pattern avoided:** module-level `engine = create_async_engine(...)` (Anti-Pattern 10) —
it would make `import taskmanager.infrastructure.db.engine` read `Settings` at import time and
crash mypy, import-linter and `docker build`, exactly as `main.py`'s docstring already explains
for the app object.

---

### Pattern 2: ORM models with a naming convention that *produces* the D-12 names

**What:** a `DeclarativeBase` whose `MetaData` carries a naming convention chosen so that the
constraint names in D-12 fall out automatically instead of being hand-typed in two places.

`[VERIFIED: compiled DDL, .venv SQLAlchemy 2.0.54]` — the convention below renders exactly:

```sql
CREATE TABLE task_lists (
	id UUID NOT NULL,
	owner_id UUID NOT NULL,
	name VARCHAR(120) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	status VARCHAR(16) NOT NULL,
	CONSTRAINT pk_task_lists PRIMARY KEY (id),
	CONSTRAINT uq_task_lists_owner_id_name UNIQUE (owner_id, name),
	CONSTRAINT ck_task_lists_status CHECK (status IN ('pending','in_progress','completed')),
	CONSTRAINT fk_task_lists_owner_id_users FOREIGN KEY(owner_id) REFERENCES users (id) ON DELETE CASCADE
)

CREATE UNIQUE INDEX uq_users_email_lower ON users (lower(email))
```

`uq_task_lists_owner_id_name` and `ck_tasks_status` are D-12's names, unedited.

```python
# src/taskmanager/infrastructure/db/base.py
from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
```

```python
# src/taskmanager/infrastructure/db/models.py (excerpt)
import datetime
import uuid

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from taskmanager.infrastructure.db.base import Base


class TaskRow(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        # name= supplies %(constraint_name)s -> ck_tasks_status
        CheckConstraint("status IN ('pending','in_progress','completed')", name="status"),
        CheckConstraint("priority IN ('low','medium','high')", name="priority"),
        CheckConstraint(
            "(status = 'completed') = (completed_at IS NOT NULL)",
            name="completed_at_matches_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True)
    task_list_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("task_lists.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(String(2000))
    status: Mapped[str] = mapped_column(String(16))
    priority: Mapped[str] = mapped_column(String(16))
    due_date: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
```

**Type mapping, verified:** `sa.Uuid()` has `native_uuid=True` by default and renders `UUID`
on PostgreSQL; `sa.DateTime(timezone=True)` renders `TIMESTAMP WITH TIME ZONE`. Neither needs
the `postgresql`-dialect-specific types, so the models stay backend-neutral in their imports.

**`lazy="raise"` (DB-03, SC-2):** every `relationship()` declared on these models must carry
`lazy="raise"`. `[VERIFIED: SQLAlchemy 2.0 docs]` accessing an unloaded relationship then
raises `sqlalchemy.exc.InvalidRequestError: '<X>' is not available due to lazy='raise_on_sql'`
at development time instead of `MissingGreenlet` at runtime. Given that repositories return
**domain entities only**, the honest answer may be that **no relationship is needed at all** —
foreign-key columns plus explicit `select()` statements cover every query in this phase and
Phase 4. That is the simplest correct design; if a relationship is added for convenience, it
carries `lazy="raise"` and every query that needs it uses `selectinload()` (never
`joinedload()` for collections — row multiplication).

---

### Pattern 3: `SqlAlchemyUnitOfWork` — one session, one explicit commit

```python
# src/taskmanager/infrastructure/db/unit_of_work.py
from collections.abc import Callable
from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession

from taskmanager.application.ports.repositories import (
    TaskListRepository, TaskRepository, UserRepository,
)


class SqlAlchemyUnitOfWork:
    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self._session_factory = session_factory
        self._committed = False

    async def __aenter__(self) -> Self:
        self._session = self._session_factory()
        self._committed = False
        # Annotated with the PORT types, not the concrete classes: mypy checks a mutable
        # Protocol member invariantly, so `self.tasks: SqlAlchemyTaskRepository` would stop
        # this class from satisfying UnitOfWork. Same finding as FakeUnitOfWork's docstring.
        self.tasks: TaskRepository = SqlAlchemyTaskRepository(self._session)
        self.task_lists: TaskListRepository = SqlAlchemyTaskListRepository(self._session)
        self.users: UserRepository = SqlAlchemyUserRepository(self._session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        # WR-06, normative: roll back whatever commit() did not make durable, on EVERY exit
        # path. Returning None (never True) keeps the exception travelling.
        try:
            if not self._committed:
                await self._session.rollback()
        finally:
            await self._session.close()

    async def commit(self) -> None:
        await self._session.commit()
        self._committed = True

    async def rollback(self) -> None:
        await self._session.rollback()
        self._committed = True   # nothing left to undo; mirrors FakeUnitOfWork._finished
```

**Why `Callable[[], AsyncSession]` and not `async_sessionmaker[AsyncSession]`:** the
integration fixture (D-01) must hand the UoW a factory that returns a session **bound to the
test connection**, which is a plain lambda, not an `async_sessionmaker`. `async_sessionmaker`
satisfies `Callable[[], AsyncSession]` (its `__call__(**local_kw: Any) -> AsyncSession`
accepts zero arguments), so production wiring is unaffected while the test override becomes
type-clean. This choice is what makes the whole D-01 fixture possible without a `cast`.

**Closing a session bound to an external `Connection` does not close that connection** — the
fixture keeps ownership of the outer transaction. That is the property D-01 relies on.

---

### Pattern 4: Repositories that never commit, and translate `IntegrityError` (D-13)

`[VERIFIED: psycopg 3.3.5]` `psycopg.errors.Diagnostic` exposes `constraint_name`,
`table_name`, `column_name` and `sqlstate`. `sqlalchemy.exc.IntegrityError.orig` is typed
`BaseException | None`, so mypy strict **requires** an `isinstance` narrowing before `.diag`
is reachable — there is no `type: ignore`-free shortcut.

```python
# src/taskmanager/infrastructure/db/constraints.py
# The single source of the D-12 names. The migration, the models and the translator below
# all read from here, so a rename can never leave the error mapping silently dead.
from typing import Final

UQ_TASK_LISTS_OWNER_ID_NAME: Final = "uq_task_lists_owner_id_name"
UQ_USERS_EMAIL_LOWER: Final = "uq_users_email_lower"
FK_TASKS_TASK_LIST_ID_TASK_LISTS: Final = "fk_tasks_task_list_id_task_lists"
CK_TASKS_STATUS: Final = "ck_tasks_status"
```

```python
# src/taskmanager/infrastructure/db/errors.py
import psycopg
from sqlalchemy.exc import IntegrityError


def violated_constraint(error: IntegrityError) -> str | None:
    """The name of the constraint PostgreSQL refused on, or None if unknowable."""
    original = error.orig
    # mypy strict: .orig is BaseException | None, so the narrowing is mandatory.
    if isinstance(original, psycopg.Error) and original.diag.constraint_name:
        return original.diag.constraint_name
    return None
```

```python
# src/taskmanager/infrastructure/db/repositories/task_lists.py (excerpt)
    async def add(self, task_list: TaskList) -> None:
        self._session.add(to_row(task_list))
        try:
            # flush(), never commit(): the use case owns the boundary (ARC-08, SC-4).
            # flush is what surfaces the constraint violation HERE, where the constraint
            # name is still meaningful, instead of at the use case's commit().
            await self._session.flush()
        except IntegrityError as error:
            if violated_constraint(error) == UQ_TASK_LISTS_OWNER_ID_NAME:
                raise DuplicateTaskListNameError(task_list.name) from error
            raise            # unrecognised: let it become a 500, per D-13
```

> **The `flush()` decision is load-bearing.** If a repository only calls `session.add()` and
> never flushes, the `IntegrityError` is raised by `uow.commit()` instead — at which point
> the UoW, not the repository, is holding the exception, and D-13's "translate in the
> repository" becomes impossible without the grab-bag mapping table the discussion log
> explicitly rejected. Every write path must flush.
>
> `autoflush=False` on the session factory (Pattern 1) is what makes this explicit rather
> than accidental: with autoflush on, a later `select()` could trigger the flush at an
> unpredictable point outside the `try`.

**Completion aggregate (ADR-009).** `[VERIFIED: compiled SQL]`:

```python
stmt = select(
    func.count().label("total"),
    func.count().filter(TaskRow.status == TaskStatus.COMPLETED.value).label("completed"),
).where(TaskRow.task_list_id == task_list_id)
# -> SELECT count(*) AS total, count(*) FILTER (WHERE tasks.status = %(status_1)s) AS completed
#    FROM tasks WHERE tasks.task_list_id = %(task_list_id_1)s
```

One row, two integers, straight into `CompletionStats(total=..., completed=...)`.

---

### Pattern 5: A synchronous, self-sufficient Alembic `env.py`

Four deviations from the stock template, each fixing a verified defect:

```python
# migrations/env.py
import os
from logging.config import fileConfig

from sqlalchemy import create_engine, pool

from alembic import context
from taskmanager.infrastructure.db.base import Base
from taskmanager.infrastructure.db import models  # noqa: F401 - registers every table

config = context.config

# (1) Guarded, and never disabling loggers that already exist. fileConfig() defaults to
#     disable_existing_loggers=True, which silences taskmanager's own loggers for the rest
#     of the process - verified to break the caplog assertions in
#     tests/api/test_error_contract.py when a session fixture runs a migration first.
if config.config_file_name is not None and config.attributes.get("configure_logging", True):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _database_url() -> str:
    # (2) Never config.set_main_option(): ConfigParser interpolation raises ValueError on
    #     any '%' in the URL (a percent-encoded password is enough). Read the value
    #     directly instead. attributes wins so a test can point at taskmanager_test
    #     without touching the process environment.
    url = config.attributes.get("sqlalchemy_url")
    if isinstance(url, str):
        return url
    return os.environ["DATABASE_URL"]


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _run(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # (3) The documented connection-sharing hook, so a pytest fixture can pass its own
    #     Connection and keep one transaction across upgrade+downgrade.
    connection = config.attributes.get("connection")
    if connection is not None:
        _run(connection)
        return
    # (4) Own engine, built from the URL above - not engine_from_config(), which would read
    #     sqlalchemy.url back out of the ini and re-introduce the interpolation problem.
    engine = create_engine(_database_url(), poolclass=pool.NullPool)
    with engine.connect() as conn:
        _run(conn)
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

`prepend_sys_path = .` in `alembic.ini` is not sufficient to import `taskmanager` on a fresh
clone — the package lives under `src/`. Either set `prepend_sys_path = src` or rely on the
editable install (`make install` already does `pip install -e .`, and the Docker builder does
a non-editable install). Recommend `prepend_sys_path = src` so `alembic upgrade head` works
from a bare checkout too.

`[VERIFIED: alembic 1.20.0 scaffold generated in this session]` the `generic` template's
`alembic.ini` already contains `path_separator = os` and
`script_location = %(here)s/migrations`, so no deprecation warning fires — which matters
because `pytest.ini` sets `filterwarnings = error`.

**Customise `script.py.mako`.** The stock template emits
`from typing import Sequence, Union` and `Union[str, Sequence[str], None]`. On a Python 3.13
project that also runs isort/black, rewrite it to `str | Sequence[str] | None` with
`from collections.abc import Sequence`. It is three edited lines and it removes an obvious
"generated, never read" tell.

---

### Pattern 6: `docker-compose.yml`

```yaml
services:
  db:
    image: postgres:18-alpine
    environment:
      POSTGRES_USER: taskmanager
      POSTGRES_PASSWORD: taskmanager
      POSTGRES_DB: taskmanager
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./docker/initdb:/docker-entrypoint-initdb.d:ro
    ports:
      - "5432:5432"
    healthcheck:
      # -h 127.0.0.1 is load-bearing: the image's init-time server listens on a Unix
      # socket only, so a socket probe reports ready before any TCP listener exists.
      # Identical reasoning to .github/workflows/ci.yml.
      test: ["CMD-SHELL", "pg_isready -h 127.0.0.1 -U $$POSTGRES_USER -d $$POSTGRES_DB"]
      interval: 5s
      timeout: 5s
      retries: 10
      start_period: 10s

  api:
    build:
      context: .
      target: runtime
    env_file: .env
    environment:
      # `environment` beats `env_file` (verified), so a developer's .env can keep
      # localhost for `make test` / `make run` while the container talks to `db`.
      DATABASE_URL: postgresql+psycopg://taskmanager:taskmanager@db:5432/taskmanager
    depends_on:
      db:
        condition: service_healthy
    ports:
      - "8000:8000"

  test:
    build:
      context: .
      target: test
    env_file: .env
    environment:
      DATABASE_URL: postgresql+psycopg://taskmanager:taskmanager@db:5432/taskmanager_test
      TEST_DATABASE_URL: postgresql+psycopg://taskmanager:taskmanager@db:5432/taskmanager_test
    depends_on:
      db:
        condition: service_healthy

volumes:
  pgdata:
```

`[VERIFIED: docs.docker.com]` precedence is
`run -e` > interpolated > `environment` > `env_file` > image `ENV`.
`[VERIFIED: docs.docker.com]` `env_file` entries are `required: true` by default, so a missing
`.env` is a clear compose error — exactly the D-15 behaviour.
`[VERIFIED: docs.docker.com]` Compose inherits the image's `HEALTHCHECK` unless the service
overrides it, so D-09's Dockerfile declaration is enough for `docker compose ps` to show
`healthy`.

---

### Pattern 7: Entrypoint — wait, migrate, exec

```sh
#!/bin/sh
# docker/entrypoint.sh
set -eu

python - <<'PY'
import os, sys, time
from sqlalchemy import create_engine, text

# DATABASE_URL is a SQLAlchemy URL (postgresql+psycopg://...). psycopg.connect() REJECTS
# that scheme - verified - so the probe goes through SQLAlchemy's sync engine, which
# understands the +psycopg driver token and uses the very same driver.
url = os.environ["DATABASE_URL"]
for attempt in range(1, 31):
    try:
        with create_engine(url, pool_pre_ping=True).connect() as conn:
            conn.execute(text("SELECT 1"))
        sys.exit(0)
    except Exception as exc:  # noqa: BLE001 - any failure means "not ready yet"
        print(f"waiting for database ({attempt}/30): {exc.__class__.__name__}", flush=True)
        time.sleep(1)
print("database did not become reachable after 30 attempts", file=sys.stderr)
sys.exit(1)
PY

alembic upgrade head
exec uvicorn --factory taskmanager.main:create_app --host 0.0.0.0 --port 8000
```

**Alternative worth considering:** put the probe in a small Python module *inside*
`src/taskmanager/infrastructure/db/wait.py` and call it as `python -m taskmanager...`. That
buys unit-testability of the retry/bound logic — but it lands the module in the coverage
denominator (C-6), so it must then be tested. The heredoc form above keeps it out of
`src/taskmanager` entirely and therefore out of coverage. This is a genuine trade the planner
must make explicitly, not drift into.

---

### Pattern 8: `/health` and the Dockerfile `HEALTHCHECK`

```python
# src/taskmanager/presentation/api/health.py
import asyncio

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

router = APIRouter(tags=["health"])
DATABASE_PROBE_TIMEOUT_SECONDS = 2.0


async def _database_is_reachable(engine: AsyncEngine) -> bool:
    try:
        async with asyncio.timeout(DATABASE_PROBE_TIMEOUT_SECONDS):
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
    except (TimeoutError, SQLAlchemyError):
        return False
    return True


@router.get("/health", response_model=HealthResponse, responses={503: {"model": HealthResponse}})
async def health(response: Response, engine: AsyncEngine = Depends(get_engine)) -> HealthResponse:
    database_ok = await _database_is_reachable(engine)
    if not database_ok:
        # No HTTPException: C-4 permits it here (presentation), but a plain status
        # assignment keeps the D-08 body identical on both paths, which is the point.
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse(
        status="ok" if database_ok else "degraded",
        checks={"database": "ok" if database_ok else "unavailable"},
        version=__version__,
    )
```

```dockerfile
# Dockerfile, runtime stage
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=3 \
  CMD ["python", "-c", "import sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).status == 200 else 1)"]
```

`urlopen` raises `HTTPError` on a 503, which exits non-zero via the traceback — that is the
intended behaviour, but wrapping it in an explicit `try/except SystemExit` is clearer. Note
`--start-period=30s`: the API is not listening until migrations finish, and without a start
period the container flaps to `unhealthy` before it ever had a chance.

**Note on `response_model` + `Response`:** injecting `Response` to mutate `status_code` while
still returning a Pydantic model is the documented FastAPI pattern. Do not return a raw
`JSONResponse` — it would bypass `response_model` and drop the schema from `/openapi.json`,
which DOC-04 will later need.

### Anti-Patterns to Avoid

- **A module-level `engine` or `Settings()`** — Anti-Pattern 10; breaks `create_app()`'s
  no-database guarantee that `tests/conftest.py` already depends on.
- **Returning ORM rows from repositories** — Anti-Pattern 2; the ports are typed in domain
  entities and mypy will catch it, but the temptation appears at `completion_stats`.
- **`.commit()` inside a repository** — SC-4; the entire phase turns on this.
- **Committing in the `get_uow` dependency's teardown** — Anti-Pattern 1; FastAPI runs
  `yield`-dependency exit code after the response is sent.
- **`Base.metadata.create_all()` in the test fixture** — Anti-Pattern 9 + D-02; it would make
  the migration the only untested artifact in a phase that is about migrations.
- **`server_default=func.now()` on `created_at`/`updated_at`** — contradicts Phase 2 D-13/D-14
  (the `Clock` port is the only source of time) and would make `alembic check` compare a
  server default the models do not declare.
- **PostgreSQL `ENUM` types for status/priority** — D-11 mandates `VARCHAR` + `CHECK`; a PG
  enum also makes every future value addition a migration with `ALTER TYPE`.

## Don't Hand-Roll

| Problem | Don't build | Use instead | Why |
|---------|-------------|-------------|-----|
| Waiting for a ready DB in compose | A `sleep 10` in the entrypoint | `depends_on: condition: service_healthy` + `pg_isready -h 127.0.0.1` + bounded retry | `sleep` is a race that passes on a warm volume and fails on the evaluator's cold one |
| Deriving `TEST_DATABASE_URL` | `DATABASE_URL.replace("taskmanager", "taskmanager_test")` | `sqlalchemy.engine.make_url(url).set(database="taskmanager_test").render_as_string(hide_password=False)` | String replace corrupts a URL whose *user* or *password* contains `taskmanager`. `[VERIFIED]` `make_url(...).set(database=...)` is exact |
| Converting a SQLAlchemy URL to libpq form | Regex-stripping `+psycopg` | `make_url(url).set(drivername="postgresql").render_as_string(hide_password=False)` | `[VERIFIED]` produces `postgresql://u:p@localhost:5432/db`; handles percent-encoding |
| Per-test DB cleanup | `TRUNCATE ... CASCADE` autouse fixture | Connection-bound session + `join_transaction_mode="create_savepoint"` | D-01; truncation lets a stray repository `.commit()` pass unnoticed |
| Detecting model/migration drift | Hand-comparing `\d+` output | `alembic.command.check()` → `AutogenerateDiffsDetected` | `[VERIFIED]` typed exception, assertable in a test |
| Constraint names | Typing the string in migration + repository | One `constraints.py` of `Final` constants + a `MetaData(naming_convention=...)` | D-13 keys error translation on the name; two copies drift silently |
| Running migrations programmatically | `subprocess.run(["alembic", "upgrade", "head"])` | `alembic.command.upgrade(Config, "head")` with `cfg.attributes["connection"]` | Shares the fixture's connection, returns real exceptions, no PATH dependency |
| Completion percentage | Loading rows and counting in Python | `func.count().filter(...)` → one `COUNT(*) FILTER` row | Anti-Pattern 8 / ADR-009 |
| Enforcing "no commit in repositories" | A code-review habit | A pytest test that greps `src/taskmanager/infrastructure/db/repositories/` | SC-4 says it must be *provable* |

**Key insight:** every hand-rolled shortcut in this table fails in exactly one situation — a
cold volume, a password with a special character, a stray commit — and none of them fail on
the developer's machine. This phase's whole risk profile is "works here, breaks for the
evaluator", so the library routine is always the cheaper choice.

## Common Pitfalls

### Pitfall 1: `join_transaction_mode` silently degrades to `rollback_only`

**What goes wrong:** the D-01 fixture opens `conn.begin()` and binds an `AsyncSession` without
passing `join_transaction_mode`. The `UnitOfWork` under test calls `commit()`. Instead of
releasing a savepoint, the session issues a *no-op* — and every subsequent read in the same
test sees the data (because it is the same connection), so the test passes. The claim "the use
case really committed" is then untested, and so is the rollback path.

**Why it happens:** `[VERIFIED: SQLAlchemy 2.0.54 source]` the default is
`join_transaction_mode="conditional_savepoint"`, documented as: *"if the given Connection is
begun within a transaction but does not have a SAVEPOINT, then `rollback_only` is used"*. A
fixture that calls `connection.begin()` (not `begin_nested()`) hits exactly that branch.

**How to avoid:** pass it explicitly. `AsyncSession.__init__` is
`(bind, *, binds, sync_session_class, **kw)` `[VERIFIED: introspected]`, and `**kw` forwards to
`Session`, so `AsyncSession(bind=connection, join_transaction_mode="create_savepoint")` works.
The SQLAlchemy docs themselves say: *"It is recommended that one of the explicit settings be
used."*

**Warning signs:** an integration test asserting on data it wrote through a committing UoW
that passes even when `commit()` is commented out.

---

### Pitfall 2: `psycopg.connect()` rejects the project's own `DATABASE_URL`

**What goes wrong:** the D-07 entrypoint probe does `psycopg.connect(os.environ["DATABASE_URL"])`
and dies immediately — not after a timeout, but on the first attempt, with a message about
connection-string syntax. The bounded retry loop then burns all 30 attempts on a permanent
error and the container exits 1 on a perfectly healthy database.

**Why it happens:** `[VERIFIED: psycopg 3.3.5]`
`psycopg.conninfo.conninfo_to_dict("postgresql+psycopg://u:p@localhost:5432/db")` raises
`ProgrammingError: missing "=" after "postgresql+psycopg://..."`. libpq understands
`postgresql://`, not SQLAlchemy's `+driver` token.

**How to avoid:** either probe through `sqlalchemy.create_engine(url)` (Pattern 7 — same
driver, no conversion) or convert first with
`make_url(url).set(drivername="postgresql").render_as_string(hide_password=False)`
`[VERIFIED]`. Never regex.

---

### Pitfall 3: `Config.set_main_option()` explodes on a `%` in the URL

**What goes wrong:** the test fixture does
`cfg.set_main_option("sqlalchemy.url", test_database_url)` to point Alembic at
`taskmanager_test`. It works for everyone until a password containing a percent-encoded
character appears, at which point the whole suite dies in a fixture with
`ValueError: invalid interpolation syntax`.

**Why it happens:** `[VERIFIED: alembic 1.20.0 + Python 3.14 configparser]`
`set_main_option` → `ConfigParser.set` → `BasicInterpolation.before_set`, which rejects any
`%` not followed by `%` or `(`.

**How to avoid:** do not write the URL into the ini at all. Pass it through
`Config(..., attributes={"sqlalchemy_url": url})` and read it in `env.py` (Pattern 5). If the
ini route is unavoidable, escape with `url.replace("%", "%%")` — but the attributes route is
strictly better because it also keeps a live credential out of a config object that might be
printed.

---

### Pitfall 4: Alembic's `fileConfig()` disables the application's loggers

**What goes wrong:** `tests/api/test_error_contract.py` has two `caplog` assertions
(lines ~178 and ~227) that pin the single `ERROR` record `handle_unexpected_error` emits. Once
a session-scoped fixture runs `alembic upgrade head`, those tests see **zero** records and
fail — with a message about an empty `caplog.records` that points nowhere near Alembic.

**Why it happens:** `[VERIFIED: demonstrated live in this session]` the stock `env.py` calls
`fileConfig(config.config_file_name)`, and `logging.config.fileConfig` defaults to
`disable_existing_loggers=True`. A logger created by importing
`taskmanager.presentation.api.errors.handlers` goes from `disabled=False` to `disabled=True`
the moment `fileConfig` runs.

**How to avoid:** both belts. In `env.py`, guard on
`config.attributes.get("configure_logging", True)` **and** pass
`disable_existing_loggers=False` (Pattern 5). In the test fixture, build the `Config` with
`attributes={"configure_logging": False, ...}`.

**Warning signs:** a `caplog` test that passes in isolation (`pytest tests/api/...`) and fails
in the full suite. This is precisely the ordering-dependent failure mode Pitfall 4 of
`.planning/research/PITFALLS.md` warns about, arriving from an unexpected direction.

---

### Pitfall 5: the Dockerfile cannot see `alembic.ini`, the migrations, or the entrypoint

**What goes wrong:** `docker compose up` builds fine, then the container exits with
`FAILED: No config file 'alembic.ini' found` — or with `exec: ./docker/entrypoint.sh: not
found`.

**Why it happens:** `[VERIFIED: Dockerfile read]` the current builder stage copies only
`requirements.txt`, `pyproject.toml` and `src`; the test stage adds `requirements-dev.txt`,
`pytest.ini .flake8 .importlinter .env.example` and `tests`. Nothing copies `alembic.ini`,
`migrations/` or `docker/`. `.dockerignore` does not exclude them — they simply are never
copied.

**How to avoid:** add to the **runtime** stage (which currently copies *no* application files
at all, only `/opt/venv`):

```dockerfile
COPY --chown=app:app alembic.ini ./
COPY --chown=app:app migrations ./migrations
COPY --chown=app:app docker/entrypoint.sh ./docker/entrypoint.sh
ENTRYPOINT ["./docker/entrypoint.sh"]
```

and to the **test** stage (which needs the schema fixture to find them):

```dockerfile
COPY alembic.ini ./
COPY migrations ./migrations
```

Two second-order details: the runtime stage sets `USER app` **before** these copies would land,
so either move the `COPY` lines above `USER app` or use `--chown=app:app`; and
`entrypoint.sh` needs the executable bit — set it with `RUN chmod +x` rather than relying on
the host's file mode surviving the build context on every platform.

---

### Pitfall 6: `.env.example` ↔ `Settings` parity is an **exact-equality** assertion

**What goes wrong:** `TEST_DATABASE_URL` is added to `.env.example` per D-04. `make test` goes
red in `tests/unit/test_settings.py::test_env_example_documents_every_field`, which asserts
`documented == {name.upper() for name in Settings.model_fields}` `[VERIFIED: file read]` — a
set equality, not a subset.

**And worse:** `Settings` is configured `extra="forbid"` with `env_file=".env"`
`[VERIFIED: file read]`. A developer who copies `.env.example` to `.env` now has a
`TEST_DATABASE_URL` key that `Settings` does not declare, and **the application fails at
boot** with a pydantic validation error — in production, not just in tests. D-15's entire
premise (`cp .env.example .env` then `docker compose up`) breaks.

**How to avoid:** pick one and state it in the plan.
- **(a) Recommended.** Add `test_database_url: str | None = None` to `Settings` and
  `TEST_DATABASE_URL=...` to `.env.example`. Parity holds, `extra="forbid"` is satisfied, and
  the field being `None` by default means nothing in production depends on it. The mild
  smell — a test-only key on the production settings object — is worth one sentence in the
  ADR.
- **(b)** Keep `TEST_DATABASE_URL` out of both `Settings` and `.env.example`; read it with
  `os.environ.get` in `tests/integration/conftest.py` and document it in the README and
  Makefile only. Parity test untouched, but it contradicts the CONTEXT canonical-refs note
  that `.env.example` "gains ... `TEST_DATABASE_URL`".
- **(c)** Loosen the parity assertion to a subset. Not recommended — it weakens an existing
  gate to accommodate a new key, which is the wrong direction.

---

### Pitfall 7: `docker-entrypoint-initdb.d` never runs on a warm volume

**What goes wrong:** a developer who already ran `docker compose up` before the init script
existed adds `01-create-test-database.sql`, re-runs `docker compose up`, and
`taskmanager_test` is still missing. Every integration test fails with
`FATAL: database "taskmanager_test" does not exist`.

**Why it happens:** `[VERIFIED: hub.docker.com/_/postgres]` *"scripts in
`/docker-entrypoint-initdb.d` are only run if you start the container with a data directory
that is empty"*; a pre-existing database is left untouched.

**How to avoid:** document `docker compose down -v` as the reset (D-14 already says to), and —
more importantly — make the `taskmanager_test` creation **idempotent and independent of the
volume state** where it is cheap to do so. A `CREATE DATABASE IF NOT EXISTS` does not exist in
PostgreSQL, but the init script can use the standard guard:

```sql
SELECT 'CREATE DATABASE taskmanager_test'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'taskmanager_test') \gexec
```

That still only runs on a fresh volume, so the real mitigation is the clean-volume rehearsal:
**always verify with `docker compose down -v && docker compose up`** — that is the evaluator's
run, and it is the only one that exercises this path. DOCK-05 makes this a requirement anyway.

---

### Pitfall 8: `alembic check` cannot prove DB-04

**What goes wrong:** the plan leans on `alembic check` (D-02) as the proof that the schema
matches the models, and concludes the `CHECK` constraints are therefore verified. They are not.

**Why it happens:** Alembic autogenerate has a documented set of things it cannot detect, and
`CHECK` constraints are on it — SQLAlchemy does not reflect them into a comparable form. The
practical consequence cuts both ways: `alembic check` will not report a **missing** CHECK as
drift (so it cannot prove DB-04), and it will not report a CHECK declared in `__table_args__`
as spurious drift either (so it will not produce false positives). `[ASSUMED — documented
Alembic limitation; not executed against a live database in this session]`

**How to avoid:** prove the CHECKs the only way that is real — an integration test that
attempts the forbidden insert and asserts the specific `IntegrityError` / translated
`DomainError`. One test per constraint in D-12. The same applies to the `ON DELETE CASCADE`
of DB-05: insert a list with tasks, delete the list, assert the tasks are gone.

**Related, verified:** Alembic 1.20 **does** compare PostgreSQL *expression* indexes
(`_compare_index_expressions` in `alembic/ddl/postgresql.py` `[VERIFIED: source read]`), so
the `lower(email)` unique index will not show up as permanent drift. It emits a `util.warn`
only when an expression contains an operator-class clause (`..._ops`), which this schema does
not use — worth knowing because under `filterwarnings = error` such a warning would fail the
`alembic check` test outright.

**Also verified:** `compare_type` defaults to `True` since Alembic 1.12
`[VERIFIED: EnvironmentContext.configure signature]`, so a `String(200)` in the model against a
`VARCHAR(120)` in the migration *will* be caught.

---

### Pitfall 9: `filterwarnings = error` turns every ORM/migration deprecation into a failure

**What goes wrong:** a legacy idiom — `Query`, `declarative_base()`, `session.execute()` with a
raw string instead of `text()` — emits a SQLAlchemy 2.0 deprecation warning, and `pytest.ini`'s
`filterwarnings = error` converts it into a test failure with a confusing traceback.

**How to avoid:** 2.0 idioms only: `DeclarativeBase`, `Mapped[...]`, `mapped_column()`,
`select()`, `text()` for raw SQL, `session.get()`/`session.scalars()`. Never `Query`, never
`declarative_base()`, never `sqlalchemy2-stubs`.

`[VERIFIED]` the Alembic 1.20 `generic` scaffold itself is warning-clean under this setting —
its `alembic.ini` already carries `path_separator = os`, the option whose absence produces a
deprecation warning in 1.16+.

---

### Pitfall 10: a session-scoped async fixture crosses event loops

**What goes wrong:** `RuntimeError: Task ... attached to a different loop`, or
`Event loop is closed`, in the second integration test.

**Why it happens:** `pytest.ini` sets `asyncio_default_fixture_loop_scope = function`
(ADR-012). A `@pytest.fixture(scope="session")` wrapping an `async def` gets a loop that dies
with the first test.

**How to avoid:** keep everything that must be session-scoped **synchronous**. This works out
naturally here: Alembic is synchronous, so the D-02 schema fixture and the D-03 fail-fast
reachability probe are both sync session-scoped fixtures using `sqlalchemy.create_engine`.
The *async* engine and the connection/session are function-scoped. If a session-scoped async
fixture is genuinely wanted later, `pytest_asyncio.fixture(loop_scope="session", scope="session")`
is the form — both parameters, matched `[VERIFIED: pytest_asyncio 1.4.0 signature has
loop_scope]` — and it is a deliberate, separately-committed change per ADR-012.

---

### Pitfall 11: `expire_on_commit=True` after commit

**What goes wrong:** `MissingGreenlet` on the first attribute read after `uow.commit()`.
**How to avoid:** `async_sessionmaker(engine, expire_on_commit=False)` — mandatory, per ADR-006
and `[VERIFIED: SQLAlchemy asyncio docs]`. In this architecture the risk is lower than usual
because repositories return **domain entities** (plain dataclasses, already detached from the
ORM), but the ORM rows the mappers read from are still live in the session and the flag still
matters.

## Code Examples

### Integration-test fixtures (D-01 + D-02 + D-03)

```python
# tests/integration/conftest.py
from collections.abc import AsyncIterator, Callable, Iterator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession, create_async_engine

from taskmanager.infrastructure.config.settings import get_settings

ROOT = Path(__file__).resolve().parents[2]


def test_database_url() -> str:
    """TEST_DATABASE_URL when set, otherwise DATABASE_URL with the database swapped.

    make_url().set() rather than str.replace(): a password or username containing
    "taskmanager" would silently corrupt a replace-based derivation. Unit-tested in
    tests/unit/infrastructure/test_database_url.py (D-04).
    """
    settings = get_settings()
    if settings.test_database_url:
        return settings.test_database_url
    return make_url(settings.database_url).set(database="taskmanager_test").render_as_string(
        hide_password=False
    )


@pytest.fixture(scope="session")
def database_url() -> str:
    return test_database_url()


@pytest.fixture(scope="session")
def _require_database(database_url: str) -> None:
    """D-03: fail ONCE, fast, with an instruction - never dozens of tracebacks."""
    try:
        with create_engine(database_url).connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as error:  # noqa: BLE001
        pytest.fail(
            f"PostgreSQL is not reachable at {make_url(database_url).render_as_string()}.\n"
            f"Start it with `make up`, or run the whole suite in Docker with "
            f"`make docker-test`.\n"
            f"Underlying error: {error.__class__.__name__}: {error}",
            pytrace=False,
        )


@pytest.fixture(scope="session")
def migrated_database(_require_database: None, database_url: str) -> Iterator[None]:
    """D-02: the real migration builds the schema. Never create_all().

    downgrade base first so a stale test database from a previous revision cannot mask
    a migration change. configure_logging=False keeps Alembic's fileConfig() from
    disabling taskmanager's loggers and breaking the caplog tests in tests/api/.
    """
    config = Config(
        str(ROOT / "alembic.ini"),
        attributes={"sqlalchemy_url": database_url, "configure_logging": False},
    )
    engine = create_engine(database_url, poolclass=NullPool)
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "base")
        command.upgrade(config, "head")
    engine.dispose()
    yield


@pytest.fixture
async def connection(migrated_database: None, database_url: str) -> AsyncIterator[AsyncConnection]:
    """The outer transaction. Nothing inside a test ever reaches disk."""
    engine = create_async_engine(database_url, poolclass=NullPool)
    async with engine.connect() as conn:
        transaction = await conn.begin()
        try:
            yield conn
        finally:
            await transaction.rollback()
    await engine.dispose()


@pytest.fixture
def session_factory(connection: AsyncConnection) -> Callable[[], AsyncSession]:
    """join_transaction_mode is explicit on purpose: the default 'conditional_savepoint'
    degrades to 'rollback_only' for a connection whose transaction is not itself a
    SAVEPOINT - which is exactly this fixture - and the UoW's commit() would silently
    become a no-op that no assertion could catch."""
    def factory() -> AsyncSession:
        return AsyncSession(
            bind=connection,
            expire_on_commit=False,
            autoflush=False,
            join_transaction_mode="create_savepoint",
        )

    return factory


@pytest.fixture
def uow(session_factory: Callable[[], AsyncSession]) -> SqlAlchemyUnitOfWork:
    return SqlAlchemyUnitOfWork(session_factory)
```

### The D-01 isolation proof (the test the CONTEXT explicitly asks for)

```python
# tests/integration/test_unit_of_work.py
pytestmark = pytest.mark.integration


async def test_a_committed_write_is_invisible_outside_the_test_transaction(
    uow: SqlAlchemyUnitOfWork, database_url: str
) -> None:
    """The savepoint pattern is real: the UoW commits, and nothing escapes."""
    user = User.create(user_id=uuid4(), email="a@b.test", password_hash="h" * 20, now=NOW)

    async with uow:
        await uow.users.add(user)
        await uow.commit()

    # Same transaction: the write is there.
    async with uow:
        assert await uow.users.get(user.id) is not None

    # A SECOND, independent connection: the write is not there.
    outside = create_async_engine(database_url, poolclass=NullPool)
    async with outside.connect() as connection:
        count = await connection.scalar(
            text("SELECT count(*) FROM users WHERE id = :id"), {"id": user.id}
        )
    await outside.dispose()
    assert count == 0
```

### The `MissingGreenlet` regression test (SC-2)

```python
async def test_a_returned_entity_is_readable_after_the_session_is_gone(
    uow: SqlAlchemyUnitOfWork,
) -> None:
    """The repository returns a domain entity, not an ORM row - so every field is
    already materialised and nothing lazy-loads outside the greenlet context."""
    async with uow:
        await uow.task_lists.add(a_task_list())
        await uow.commit()
        fetched = await uow.task_lists.get(TASK_LIST_ID)

    assert fetched is not None
    # Outside the `async with`: the session is closed. Reading every field must not raise.
    assert fetched.name and fetched.owner_id and fetched.created_at
    assert isinstance(fetched, TaskList)          # never a *Row
```

### The SC-4 "no commit in repositories" gate

```python
# tests/architecture/test_no_commit_in_repositories.py
from pathlib import Path

REPOSITORIES = Path(__file__).resolve().parents[2] / "src/taskmanager/infrastructure/db/repositories"


def test_no_repository_commits_its_own_transaction() -> None:
    """ARC-08 / roadmap SC-4: the use case owns the boundary, so a repository that
    committed would make `async with uow:` a lie that no unit test could detect."""
    offenders = [
        f"{path.relative_to(REPOSITORIES)}:{number}"
        for path in sorted(REPOSITORIES.rglob("*.py"))
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if ".commit()" in line
    ]
    assert offenders == [], (
        "Repositories must never commit; the UnitOfWork does, once, when the use case "
        f"says so. Found: {offenders}"
    )
```

> A source-text scan is the right tool here and not a lazy one: the property being asserted
> is *"this call does not appear in this directory"*, which is a property of the text. An AST
> walk would be more precise about comments and strings, and is a fine upgrade — but it must
> still not be weakened into "no commit is *reached* at runtime", which is untestable.
> If the planner prefers AST, `ast.walk` looking for `Attribute(attr="commit")` is ~10 lines.

### The `alembic check` drift test (D-02)

```python
def test_the_models_and_the_migrations_do_not_disagree(migrated_database: None, database_url: str) -> None:
    """If this fails, someone changed a model without writing a revision."""
    config = Config(
        str(ROOT / "alembic.ini"),
        attributes={"sqlalchemy_url": database_url, "configure_logging": False},
    )
    try:
        command.check(config)
    except AutogenerateDiffsDetected as drift:
        pytest.fail(f"ORM models drifted from the migrations: {drift}", pytrace=False)
```

`[VERIFIED: alembic 1.20.0 source]` `command.check()` raises
`alembic.util.exc.AutogenerateDiffsDetected` (importable as
`from alembic.util.exc import AutogenerateDiffsDetected`) and returns `None` on success.

## State of the Art

| Old approach | Current approach | When changed | Impact here |
|--------------|------------------|--------------|-------------|
| `declarative_base()` + `Column()` | `DeclarativeBase` + `Mapped[...]` / `mapped_column()` | SQLAlchemy 2.0 | Mandatory — `filterwarnings = error` |
| `session.query(Model)` | `select(Model)` + `session.scalars()` | SQLAlchemy 2.0 | Mandatory |
| `sqlalchemy2-stubs` | Inline types shipped with 2.0 | SQLAlchemy 2.0 | Never install stubs; they conflict |
| `postgresql.UUID(as_uuid=True)` | `sa.Uuid()` (backend-neutral, native on PG) | SQLAlchemy 2.0 | Recommended; `[VERIFIED]` `native_uuid=True` by default |
| `event.listen(session, "after_transaction_end", restart_savepoint)` recipe | `join_transaction_mode="create_savepoint"` | SQLAlchemy 2.0 | The old recipe is what training data contains; do not reproduce it |
| `compare_type=False` default | `compare_type=True` default | Alembic 1.12 | Type drift is caught for free `[VERIFIED]` |
| `version_path_separator` | `path_separator` | Alembic ~1.16 | The 1.20 scaffold already emits the new key `[VERIFIED]` |
| `@pytest.fixture def event_loop()` override | `asyncio_default_fixture_loop_scope` in `pytest.ini`; `pytest_asyncio.fixture(loop_scope=...)` | pytest-asyncio 0.23+ | Already correct in `pytest.ini`; never add an `event_loop` fixture |
| `AsyncClient(app=app)` | `AsyncClient(transport=ASGITransport(app=app))` | httpx 0.28 | Already correct in `tests/conftest.py` |
| `depends_on: [db]` | `depends_on: {db: {condition: service_healthy}}` | Compose v2 | Mandatory (DOCK-02) |

**Deprecated / do not use:**
- `Base.metadata.create_all()` for the test schema — ADR-007, D-02, Anti-Pattern 9
- PostgreSQL `ENUM` for status/priority — D-11 mandates VARCHAR + CHECK
- `asyncpg` — ADR-006
- A module-level `engine` — Anti-Pattern 10

## Assumptions Log

| # | Claim | Section | Risk if wrong |
|---|-------|---------|---------------|
| A1 | Alembic autogenerate cannot detect `CHECK` constraints, so `alembic check` neither proves nor false-positives on them | Pitfall 8 | If it *does* compare them, `alembic check` may report permanent drift and the D-02 test fails. Mitigation: the first `alembic check` run in Wave 1 settles it empirically — cheap to verify, so do not carry this assumption past the first migration |
| A2 | `psycopg`'s `IntegrityError` for a FK violation populates `diag.constraint_name` | Pattern 4 / D-13 | If the field is empty for some violation classes, the FK→`NotFoundError` branch of D-13 silently falls through to the re-raise. Mitigation: one integration test per constraint asserting the *translated* `DomainError`, not the raw exception |
| A3 | `urlopen` raising `HTTPError` on 503 is sufficient for the Dockerfile `HEALTHCHECK` to report unhealthy | Pattern 8 | If the traceback exit code is not 1 on some Python builds, an unhealthy API could report healthy. Mitigation: wrap explicitly in `try/except` and `sys.exit(1)`; verify with `docker compose ps` while the DB is stopped |
| A4 | psycopg 3 returns timezone-aware `datetime` for `timestamptz`, so the mapper never sees a naive value | WR-05 / D-11 | If a naive value can arrive, `require_utc` raises a domain `ValidationError` for an infrastructure fault — the exact defect WR-05 flagged. Mitigation: the WR-05 ADR must state the chosen behaviour, and one integration test must round-trip a timestamp and assert `tzinfo is not None` |
| A5 | The two `caplog` tests in `tests/api/test_error_contract.py` will run *after* the migration fixture in a default (file-order) run | Pitfall 4 | If they run first they pass today and break on a `-p randomly` or `--lf` run — a latent, order-dependent failure. Mitigation: apply the `disable_existing_loggers=False` fix regardless of observed ordering; it costs one keyword argument |

## Open Questions (RESOLVED — each recommendation below was adopted by the plans: Q1 → 03-10, Q2 → 03-03, Q3 → 03-02, Q4 → 03-01/03-06, Q5 → 03-04/03-11)

1. **Where does the entrypoint's retry logic live — shell heredoc or `src/taskmanager`?**
   - What we know: a module under `src/taskmanager/` is unit-testable but enters the coverage
     denominator (C-6, no `omit` allowed); a heredoc in `entrypoint.sh` is untestable but
     costs no coverage.
   - What's unclear: whether the planner values the unit test of the bound/backoff logic more
     than the extra integration tests needed to cover it.
   - Recommendation: heredoc (Pattern 7) for Phase 3. The behaviour it encodes is proven
     end-to-end by the `docker compose down -v && docker compose up` rehearsal, which is a
     stronger proof than a unit test of a `range(30)` loop.

2. **Does `TEST_DATABASE_URL` become a `Settings` field?**
   - What we know: the `.env.example` parity test is an exact-equality assertion, and
     `extra="forbid"` makes an undeclared `.env` key a boot failure `[VERIFIED]`.
   - What's unclear: whether a test-only key on the production settings object is acceptable
     to the user.
   - Recommendation: option (a) from Pitfall 6 — add the field as `str | None = None`. It is
     the only option that keeps both `cp .env.example .env && docker compose up` and the
     existing parity gate working unchanged. Record it in the ADR with one sentence of
     justification.

3. **`migrations/` or `alembic/`?**
   - What we know: `.flake8` already excludes `migrations`; CONTEXT sketched `alembic/`.
   - Recommendation: `migrations/`. If `alembic/` is chosen, updating `.flake8` is a
     mandatory task, not an optional tidy-up.

4. **Are any `relationship()` declarations needed at all in Phase 3?**
   - What we know: repositories return domain entities; every Phase 3 and Phase 4 query is
     expressible with FK columns and explicit `select()`. `lazy="raise"` is required on any
     relationship that *does* exist (DB-03, SC-2).
   - What's unclear: whether SC-2's wording ("relationships use `lazy='raise'`") requires at
     least one relationship to exist in order to be demonstrable.
   - Recommendation: declare the `TaskListRow.tasks` relationship with `lazy="raise"` even if
     no query uses it, plus one test asserting that touching it raises `InvalidRequestError`.
     That makes SC-2 provable rather than vacuously true, at the cost of four lines.

5. **How does the WR-05 naive-datetime question resolve?**
   - What we know: `require_utc` currently raises a domain `ValidationError` and normalises
     with `astimezone(UTC)` `[VERIFIED: file read]`. D-11 mandates `timestamptz`, which
     psycopg returns as aware — so in practice the naive branch is unreachable from the
     database.
   - Recommendation: an ADR that refines D-14 by *scope* rather than by error type — "a naive
     datetime reaching the domain remains a `ValidationError`; the mapper additionally asserts
     awareness at the infrastructure boundary so a schema regression surfaces as an
     infrastructure fault before an entity is constructed." That satisfies the reviewer's
     concern without changing five existing domain tests or the observable HTTP contract.

## Environment Availability

| Dependency | Required by | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Docker Engine | `make up`, `make docker-test`, compose stack | ✓ | 29.2.0 (server reachable) | — |
| Docker Compose | DOCK-02, `make up` / `make docker-test` | ✓ | v5.0.2 | — |
| `postgres:18-alpine` image | `db` service | ✓ (pullable; already used by CI) | 18-alpine | `postgres:17-alpine` per ADR-013 |
| `python:3.13-slim-trixie` image | builder/runtime/test stages | ✓ (already built as `taskmanager-test:latest`) | 3.13 | — |
| SQLAlchemy / psycopg / Alembic | everything in this phase | ✓ | 2.0.54 / 3.3.5 / 1.20.0 | — |
| pytest-asyncio | async integration fixtures | ✓ | 1.4.0 | — |
| `psql` CLI on the host | nothing — no task requires it | ✗ | — | Use `docker compose exec db psql` for manual inspection |
| `pg_isready` on the host | nothing — it runs **inside** the `db` container | ✗ | — | None needed; the compose healthcheck uses the image's own binary |
| Host `.venv` interpreter | `make test` / `make lint` / `make typecheck` | ✓ | CPython 3.14.3 (project targets 3.13; Docker + CI are authoritative) | Docker `test` stage |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** `psql` and `pg_isready` are absent from the host. This
is harmless — no planned task invokes them from the host. A plan step that says "run
`pg_isready` locally" would be broken on this machine; use `docker compose exec db pg_isready`
instead.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 + pytest-asyncio 1.4.0 (`asyncio_mode = auto`) |
| Config file | `pytest.ini` (brief-mandated; `[tool.pytest.ini_options]` is ignored when it exists) |
| Quick run command | `.venv/bin/pytest -m "not integration" -q` |
| Full suite command | `make test` (→ `.venv/bin/pytest`, with `--cov-fail-under=75` from addopts) |
| Containerised run | `make docker-test` (→ `docker compose run --rm --build test`) |
| CI equivalent | `.github/workflows/ci.yml` step "Tests with coverage gate", against the existing `postgres:18-alpine` service on `taskmanager_test` |

### Success Criteria → Test Map

| SC | Behaviour | Test type | Automated command | File exists? |
|----|-----------|-----------|-------------------|--------------|
| SC-1 | `docker compose up` on an empty volume reaches a healthy API | manual/rehearsal + smoke | `docker compose down -v && docker compose up -d && docker compose ps --format '{{.Service}} {{.Health}}'` → `api healthy` | ❌ Wave 0 (compose file) |
| SC-1 | `/health` returns 200 with `database: ok` | integration (API) | `pytest tests/integration/test_health.py::test_health_reports_ok_against_a_reachable_database -x` | ❌ Wave 0 |
| SC-1 | `/health` returns 503 with the same body shape when the DB is unreachable | unit (API) | `pytest tests/unit/presentation/test_health.py::test_health_reports_503_when_the_database_probe_fails -x` | ❌ Wave 0 |
| SC-1 | Migrations are applied by the entrypoint, not the app | integration | `pytest tests/integration/test_migrations.py::test_alembic_upgrade_creates_every_table -x` | ❌ Wave 0 |
| SC-2 | ORM models are separate from domain entities | unit | `pytest tests/unit/infrastructure/test_mappers.py -x` (round trip, no DB) | ❌ Wave 0 |
| SC-2 | Every relationship uses `lazy="raise"` | unit (introspection) | `pytest tests/unit/infrastructure/test_models.py::test_every_relationship_raises_on_lazy_load -x` | ❌ Wave 0 |
| SC-2 | Reading a returned entity outside the session never raises `MissingGreenlet` | integration | `pytest tests/integration/test_repositories_task_lists.py::test_a_returned_entity_is_readable_after_the_session_is_gone -x` | ❌ Wave 0 |
| SC-3 | Baseline creates `task_lists.owner_id` | integration | `pytest tests/integration/test_schema.py::test_task_lists_has_an_owner_id_foreign_key -x` | ❌ Wave 0 |
| SC-3 | VARCHAR + CHECK for status and priority (DB-04) | integration | `pytest tests/integration/test_constraints.py -k "check" -x` — one test per CHECK, asserting the insert is refused | ❌ Wave 0 |
| SC-3 | Timestamps are timezone-aware UTC | integration | `pytest tests/integration/test_schema.py::test_timestamps_round_trip_as_aware_utc -x` | ❌ Wave 0 |
| SC-3 | Deleting a list removes its tasks (DB-05) | integration | `pytest tests/integration/test_constraints.py::test_deleting_a_task_list_cascades_to_its_tasks -x` | ❌ Wave 0 |
| SC-3 | Migration history matches the models | integration | `pytest tests/integration/test_migrations.py::test_the_models_and_the_migrations_do_not_disagree -x` (`alembic check`) | ❌ Wave 0 |
| SC-3 | `downgrade()` actually works | integration | `pytest tests/integration/test_migrations.py::test_downgrade_base_removes_every_table -x` | ❌ Wave 0 |
| SC-4 | UoW commits exactly once on success | integration | `pytest tests/integration/test_unit_of_work.py::test_a_successful_block_commits_once -x` | ❌ Wave 0 |
| SC-4 | UoW rolls back on a raised `DomainError` | integration | `pytest tests/integration/test_unit_of_work.py::test_a_domain_error_leaves_nothing_written -x` | ❌ Wave 0 |
| SC-4 | UoW rolls back a block that never committed (WR-06) | integration | `pytest tests/integration/test_unit_of_work.py::test_an_uncommitted_block_is_rolled_back -x` | ❌ Wave 0 |
| SC-4 | No `.commit()` under `infrastructure/.../repositories/` | architecture | `pytest tests/architecture/test_no_commit_in_repositories.py -x` | ❌ Wave 0 |
| SC-4 | The adapter satisfies the `UnitOfWork` port | typecheck + unit | `make typecheck` and `pytest tests/unit/infrastructure/test_adapter_ports.py -x` (the `uow: UnitOfWork = SqlAlchemyUnitOfWork(...)` binding pattern from `test_ports.py`) | ❌ Wave 0 |
| SC-5 | Per-test isolation: a committed write does not escape the fixture's transaction | integration | `pytest tests/integration/test_unit_of_work.py::test_a_committed_write_is_invisible_outside_the_test_transaction -x` | ❌ Wave 0 |
| SC-5 | Suite is order-independent and repeatable | integration | `make test && make test` (twice in a row, same result) | ✅ (command exists) |
| SC-5 | Full gate green | all | `make lint && make typecheck && make arch && make test` | ✅ |
| D-03 | Unreachable DB fails once with an instruction | integration (negative) | `TEST_DATABASE_URL=postgresql+psycopg://x:x@127.0.0.1:1/x .venv/bin/pytest tests/integration -x` → exactly one failure naming `make up` | ❌ Wave 0 |
| D-04 | `TEST_DATABASE_URL` derivation | unit | `pytest tests/unit/infrastructure/test_database_url.py -x` (including a URL whose password contains `taskmanager`) | ❌ Wave 0 |
| D-13 | Constraint violation → the matching `DomainError` | integration | `pytest tests/integration/test_repositories_*.py -k "conflict or duplicate" -x` | ❌ Wave 0 |
| D-13 | An unrecognised constraint re-raises | unit | `pytest tests/unit/infrastructure/test_errors.py::test_an_unknown_constraint_is_not_swallowed -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `.venv/bin/pytest -m "not integration" -q` (sub-second; no DB needed)
  followed by the four-gate set required by C-5 before the commit itself.
- **Per wave merge:** `make lint && make typecheck && make arch && make test` (full suite,
  coverage gate included).
- **Phase gate:** `make test` green **twice in a row**, then
  `docker compose down -v && docker compose up` reaching `api healthy`, then
  `make docker-test` green — before `/gsd:verify-work`.

### Wave 0 Gaps

- [ ] `tests/integration/__init__.py` + `tests/integration/conftest.py` — the five fixtures
      above (`database_url`, `_require_database`, `migrated_database`, `connection`,
      `session_factory`, `uow`); covers D-01/D-02/D-03/D-04
- [ ] `tests/unit/infrastructure/__init__.py` — new package for mapper/clock/URL/error tests
- [ ] `tests/unit/presentation/__init__.py` — new package for the `/health` 503 unit test
- [ ] `tests/architecture/test_no_commit_in_repositories.py` — SC-4 gate
- [ ] `docker/initdb/01-create-test-database.sql` — without it there is no `taskmanager_test`
      and every integration test fails at collection
- [ ] `alembic.ini` + `migrations/env.py` — the `migrated_database` fixture cannot run without
      them, so these precede every integration test
- [ ] Framework install: none — pytest, pytest-asyncio and pytest-cov are already pinned and
      installed

> **Ordering note for the planner.** Wave 0 is unusually load-bearing in this phase: nothing in
> `tests/integration/` can even be collected before `alembic.ini`, `migrations/env.py`,
> `0001_baseline.py` and the initdb script exist. A plan that writes a repository test before
> the migration will produce a RED that is a collection error rather than an assertion
> failure, which is not a useful TDD RED. The first plan should establish
> models → baseline migration → fixtures, and only then start the repository TDD cycles.

## Security Domain

`security_enforcement` is not set to `false`, so this section applies.

### Applicable ASVS categories

| ASVS category | Applies | Standard control in this phase |
|---------------|---------|-------------------------------|
| V2 Authentication | no | Phase 5. `/health` is deliberately unauthenticated (D-08) |
| V3 Session management | no | Phase 5 |
| V4 Access control | partially | The repositories must expose owner-scoped queries (`list_for_owner`, and ADR-008's "visible to this user?" split) so Phase 4's use cases cannot accidentally do an unscoped read. No enforcement happens in this phase, but the query shapes are decided here |
| V5 Input validation | yes | Two layers, both present: domain `require_text`/`require_utc` on entity construction, and the D-12 database `CHECK`/`UNIQUE` constraints as the race-proof backstop. SQL is built exclusively with SQLAlchemy `select()`/`text()` + bound parameters — never f-strings |
| V6 Cryptography | no | Phase 5 (`pwdlib`, PyJWT) |
| V7 Error handling & logging | yes | D-13: a raw `IntegrityError` must never reach the client. The Phase 2 catch-all already emits a fixed body with no message for any 500, so an unrecognised constraint leaks nothing — but the repository must not put the constraint name or SQL into a `DomainError.details` that the problem body echoes |
| V9 Communications | partially | `DATABASE_URL` may carry `?sslmode=require`; psycopg 3 accepts libpq parameters in the URL natively (an asyncpg-specific problem this project does not have). No change needed, worth one line in the ADR |
| V14 Configuration | yes | C-8: no secret has a default; `.env` is git-ignored and `.dockerignore`d `[VERIFIED: file read]`. Compose credentials are the obviously-fake `taskmanager/taskmanager` pair, consistent with CI |

### Known threat patterns for this stack

| Pattern | STRIDE | Standard mitigation |
|---------|--------|---------------------|
| SQL injection via string-built queries | Tampering | SQLAlchemy `select()` / `text()` with bound parameters only. Never f-string a filter value into SQL — TASK-06's `status`/`priority` filters are the tempting spot |
| Credential disclosure in a connection error | Information disclosure | The D-03 fail-fast message must print `make_url(url).render_as_string()` (password masked by default) — **not** `render_as_string(hide_password=False)`. Same for the entrypoint's retry log line |
| Credential disclosure via a committed `.env` | Information disclosure | `.env` is in `.gitignore` and `.dockerignore`; pre-commit runs `detect-private-key` `[VERIFIED: file read]` |
| Raw DBAPI error reaching the client | Information disclosure | D-13 + the Phase 2 catch-all's fixed 500 body |
| IDOR / BOLA on task lists | Elevation of privilege | Owner-scoped repository queries (ADR-008); enforced in Phase 4, shaped here |
| Unbounded text reaching the database | DoS | Domain `max_length` guards + `String(n)` column limits, both present |
| Container running as root | Elevation of privilege | `USER app` already in the runtime stage `[VERIFIED: Dockerfile]`; the new `COPY` lines must not undo it (use `--chown=app:app`) |
| Published Postgres port 5432 on the host | Information disclosure | D-15 requires it for host-side `make test`. Acceptable for a local evaluation stack with throwaway credentials; worth one honest sentence in the ADR rather than silence |

## Sources

### Primary (HIGH confidence)

- **Executed against the project's own `.venv`** (SQLAlchemy 2.0.54, psycopg 3.3.5,
  Alembic 1.20.0, pytest-asyncio 1.4.0) — `join_transaction_mode` default and docstring,
  `AsyncSession.__init__` signature, `psycopg.errors.Diagnostic` attributes,
  `pytest_asyncio.fixture(loop_scope=...)`, `alembic.command.{check,upgrade,downgrade}`
  signatures, `AutogenerateDiffsDetected`, `Config.set_main_option` `%` failure,
  `fileConfig` logger disabling, `Uuid`/`DateTime(timezone=True)` DDL rendering, naming
  convention output, `COUNT(*) FILTER` rendering, `make_url(...).set(...)` behaviour,
  `conninfo_to_dict` rejection of `postgresql+psycopg://`, `alembic init -t generic` scaffold
  contents, `compare_type=True` default, `_compare_index_expressions` source
- Context7 `/websites/sqlalchemy_en_20` — asyncio extension, `expire_on_commit=False`,
  `async_sessionmaker`, joining a Session into an external transaction, `lazy="raise_on_sql"`,
  `selectinload`
- Context7 `/websites/alembic_sqlalchemy` — `alembic check`, `target_metadata`,
  `Config.attributes["connection"]` connection sharing
- Context7 `/docker/docs` — `depends_on: condition: service_healthy`, `healthcheck`,
  `env_file` `required` default, `HEALTHCHECK` option defaults, Compose inheriting the image
  healthcheck
- https://docs.docker.com/compose/how-tos/environment-variables/envvars-precedence/ —
  `environment` > `env_file`
- https://hub.docker.com/_/postgres — `docker-entrypoint-initdb.d` runs only on an empty data
  directory; `POSTGRES_DB`
- Repository files read directly — `Dockerfile`, `docker-compose` absence, `.dockerignore`,
  `.flake8`, `pytest.ini`, `.importlinter`, `Makefile`, `.pre-commit-config.yaml`,
  `.github/workflows/ci.yml`, `.env.example`, `requirements*.txt`, `pyproject.toml`,
  `src/taskmanager/**`, `tests/**`, `DECISION_LOG.md` (ADR-006/007/008/009/012/013/014),
  `.planning/{REQUIREMENTS,ROADMAP,STATE,config.json}`,
  `.planning/research/{ARCHITECTURE,PITFALLS,STACK}.md`,
  `.planning/phases/02-domain-error-contract/02-REVIEW-FIX.md` (WR-05/WR-06/WR-07)

### Secondary (MEDIUM confidence)

- `slopcheck install sqlalchemy psycopg alembic` — 3 OK, 0 SUS, 0 SLOP
- Alembic `alembic/ddl/postgresql.py` source reading for expression-index comparison — the
  code path was read, not executed against a live PostgreSQL

### Tertiary (LOW confidence — flagged in the Assumptions Log)

- Alembic's inability to detect `CHECK` constraints (A1) — a widely documented limitation,
  but not executed in this session
- psycopg populating `diag.constraint_name` for every violation class (A2)

## Metadata

**Confidence breakdown:**

- Standard stack: **HIGH** — no new packages; every pinned version confirmed by import
- Architecture patterns: **HIGH** — every API shape executed against the project's own venv
- Pitfalls: **HIGH** for 1–7 and 9–11 (all reproduced or introspected); **MEDIUM** for
  Pitfall 8 (source read + documented limitation, not executed against PostgreSQL)
- Docker/Compose behaviour: **HIGH** — official docs, plus Docker 29.2.0 / Compose v5.0.2
  confirmed present and the daemon reachable
- Existing-code integration points: **HIGH** — every claim traced to a file read in this
  session

**Research date:** 2026-09-18
**Valid until:** 2026-10-18 (30 days — the stack is exact-pinned, so the only decay risk is
the `postgres:18-alpine` and `python:3.13-slim-trixie` tags moving under the project)
