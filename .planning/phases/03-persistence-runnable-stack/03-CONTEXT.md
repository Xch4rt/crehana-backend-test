# Phase 3: Persistence & Runnable Stack - Context

**Gathered:** 2026-09-18
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase makes the application talk to a real PostgreSQL and makes the whole stack start
with one command:

- `infrastructure/db/`: async SQLAlchemy 2.0 engine/session factory, ORM models kept
  separate from the domain entities, explicit ORM ↔ entity mappers, repository adapters for
  the three repository ports, and the `UnitOfWork` adapter that owns the transaction.
- Alembic at the repository root with one baseline migration that creates the complete
  schema (users, task_lists, tasks) with the constraints decided below.
- `presentation/`: the first real router — `GET /health` — reporting liveness and database
  readiness, backing the container healthcheck.
- `docker-compose.yml` (db + api), a container entrypoint that waits for the database and
  applies migrations, a Dockerfile `HEALTHCHECK`, and `make up` / `make down` /
  `make docker-test` becoming real.
- Integration tests against real PostgreSQL with per-test isolation, run by the same
  `make test` / `make docker-test` commands and by CI.

Not in this phase: task-list/task endpoints and their use cases (Phase 4), JWT/auth adapters
and user registration/login (Phase 5), the email adapter (Phase 5), README/DECISION_LOG
completion beyond the ADRs this phase adds (Phase 7). The `users` table and
`tasks.assignee_id` column exist from the baseline migration, but no behaviour touches them
before Phases 4–5.

</domain>

<decisions>
## Implementation Decisions

### Integration test strategy
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

### Startup sequence and `/health`
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

### Baseline migration scope and integrity rules
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

### Compose and local development layout
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

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project
- `.planning/PROJECT.md` — scope, constraints, key decisions (PostgreSQL over SQLite, one-command startup)
- `.planning/REQUIREMENTS.md` — DB-01..DB-05, ARC-08, DOCK-02, DOCK-03 (this phase); LIST-06,
  TASK-05, TASK-06, ASGN-01/02 (rules the schema must support without a later migration)
- `.planning/ROADMAP.md` §"Phase 3" — goal and the five success criteria; §"Phase 4" SC-4
  (single SQL aggregate for completion) and SC-5 shape what the repositories must expose

### Decisions already locked (do not reopen)
- `DECISION_LOG.md` — ADR-001 (PostgreSQL), ADR-006 (psycopg 3 + async SQLAlchemy, one URL
  for app and Alembic), ADR-007 (Alembic, never `create_all`), ADR-009 (completion % via
  one SQL aggregate — `TaskRepository.completion_stats`), ADR-012 (pytest-asyncio `auto`,
  loop scope `function` — constrains fixture scopes), ADR-013 (`postgres:18-alpine`),
  ADR-017 (`make up`/`make down` placeholders this phase replaces), ADR-018 (Dockerfile
  `test` stage this phase routes through compose), ADR-020 (frozen-dataclass DTOs),
  ADR-021 (`DomainError` shape — what repositories may raise)
- `.planning/phases/02-domain-error-contract/02-CONTEXT.md` — D-11/D-12 (UUIDs from the
  application), D-13/D-14 (time only via `Clock`, everything UTC-aware), D-17 (UoW shape),
  D-19 (async ports)
- `.planning/phases/01-foundation-quality-gates/01-CONTEXT.md` — D-08/D-09 (pytest config
  and coverage rules), D-13 (CI Postgres service container), D-15/D-16 (dockerized tests,
  settings without defaults)
- `.planning/phases/02-domain-error-contract/02-REVIEW-FIX.md` — WR-05 (deferred naive-
  datetime classification, to be settled by an ADR in this phase) and WR-06 (normative
  rollback contract the adapter must satisfy)
- `CLAUDE.md` §"Project Rules" — layer rules, error-handling rule, quality-gate rule,
  configuration rule (no secret defaults; every setting documented in `.env.example`)
- `.importlinter` — `sqlalchemy`/`alembic` remain forbidden in `domain` and `application`

### Code contracts to implement against
- `src/taskmanager/application/ports/repositories.py` — the three repository Protocols
  (note `TaskRepository.completion_stats`, `list_for_task_list` filters,
  `TaskListRepository.exists_with_name`, `UserRepository.get_by_email`)
- `src/taskmanager/application/ports/unit_of_work.py` — the `UnitOfWork` Protocol and its
  normative `__aexit__` rollback obligation
- `src/taskmanager/application/ports/clock.py` — `Clock.now()`
- `tests/unit/application/fakes.py` — the in-memory fakes: the SQLAlchemy adapters must pass
  the same conformance shape (`mypy` binding to the port type)
- `src/taskmanager/domain/entities/*.py` — the exact field set the ORM models and mappers
  must round-trip
- `src/taskmanager/infrastructure/config/settings.py` — `Settings` (`database_url`, no
  default) and `get_settings()`; extend here for any new variable (`TEST_DATABASE_URL`)

### Research
- `.planning/research/ARCHITECTURE.md` §"Pattern 4" (Unit of Work), §"Pattern 5" (explicit
  mappers), §"Pattern 7" (`Depends` as composition root), §"Pattern 9" (settings), §"Pattern
  10" (Alembic at root, migrations at container start), §"Test Architecture", Anti-Patterns
  1, 2, 9 and 10
- `.planning/research/PITFALLS.md` — Pitfalls 1 (`MissingGreenlet`), 2 (`expire_on_commit`),
  3 (session lifecycle), 4 (loop/fixture scope), 5 (test DB isolation), 7 (starting before
  Postgres is ready), 8 (migration race), 17 (Docker image review)
- `.planning/research/STACK.md` — pinned versions and the psycopg-3 single-driver argument;
  its module-scope engine sketch is superseded by the discretion note above

### Existing infrastructure this phase extends
- `Dockerfile` — `builder` / `runtime` / `test` stages; gains the entrypoint and `HEALTHCHECK`
- `.github/workflows/ci.yml` — Postgres 18 service with the `pg_isready -h 127.0.0.1`
  healthcheck and `DATABASE_URL` pointing at `taskmanager_test`; integration tests must run
  there unchanged
- `Makefile` — `up`, `down`, `docker-test` bodies change; `test` gains the fail-fast
  behaviour; `run` is new
- `.env.example` — gains the compose-vs-localhost `DATABASE_URL` guidance and
  `TEST_DATABASE_URL`

### Standards
- PostgreSQL 18 documentation — `pg_isready`, `TIMESTAMP WITH TIME ZONE`, `ON DELETE`
  actions, expression indexes (`lower(email)`)
- SQLAlchemy 2.0 docs — asyncio extension, `join_transaction_mode="create_savepoint"`,
  `lazy="raise"`; Alembic docs — `check` command, autogenerate

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/taskmanager/main.py::create_app(settings=None)` — composition root; already registers
  the exception handlers. The engine/session factory, `/health` router and lifespan attach
  here. It must remain constructible without a database.
- `src/taskmanager/infrastructure/config/settings.py` — `Settings` is frozen, `extra="forbid"`,
  reads `.env`; `tests/unit/test_app_factory.py` and `tests/conftest.py` already set
  `DATABASE_URL`/`JWT_SECRET` through `monkeypatch`, and a unit test enforces `.env.example`
  ↔ `Settings` parity (any new variable must be added to both).
- `tests/unit/application/fakes.py` — `FakeUnitOfWork` models the exact commit/rollback
  protocol the SQLAlchemy adapter must honour; the port conformance tests in
  `tests/unit/application/test_ports.py` show the mypy-binding pattern to copy.
- `src/taskmanager/domain/value_objects/completion.py::CompletionStats` — the return type of
  `completion_stats()`; the SQL aggregate maps straight into it.
- `tests/probe.py` + `tests/conftest.py` (`app` / `client` fixtures with
  `httpx.ASGITransport`) — the pattern for `/health` API tests.
- CI's Postgres service container and healthcheck — copy its `pg_isready -h 127.0.0.1`
  reasoning into compose verbatim.

### Established Patterns
- Coverage source is `taskmanager` with no `omit`; the project is at 100% and the review/fix
  cycle treats every new branch as needing a test. Infrastructure code (mappers, repositories,
  entrypoint helpers written in Python) is measured too — integration tests are what cover it.
- `filterwarnings = error`: SQLAlchemy/Alembic deprecation warnings fail the suite; use the
  2.0 idioms only (`Mapped`, `mapped_column`, `select()`, no legacy `Query`).
- mypy strict over `src` and `tests`; SQLAlchemy 2.0 ships inline types — no stubs, no
  `type: ignore`.
- pytest-asyncio loop scope is `function` (ADR-012): a session-scoped *async* fixture would
  cross loops. Either keep engine/schema setup synchronous (Alembic is sync; a sync psycopg
  probe for the fail-fast check) or create the async engine per test — the planner decides,
  the constraint is fixed.
- TDD RED output is committed as `evidence/*-tdd-red.txt` (the strict-mypy hook prevents
  standalone RED commits); every plan has followed this since 02-01.
- Twelve pre-commit hooks run on every commit; `make lint && make typecheck && make arch &&
  make test` must be green before each commit; CI repeats them.

### Integration Points
- `create_app()` gains: engine + session factory from `Settings`, lifespan disposal, the
  `/health` router, and the `UnitOfWork` dependency factory Phase 4 will consume.
- `infrastructure/` gains `db/` (engine, models, mappers, repositories, unit of work) and a
  `clock.py` (`SystemClock`); `presentation/` gains `api/health.py` (or similar).
- Root gains `alembic.ini`, `alembic/` (sync `env.py`, `versions/0001_baseline.py`),
  `docker-compose.yml`, `docker/entrypoint.sh`, `docker/initdb/*.sql`.
- `.importlinter` contracts are unchanged; `tests/architecture/test_layer_boundaries.py`
  automatically covers the new `infrastructure` modules.
- Phase 4 routers will call use cases through the UoW dependency; Phase 5's
  `UserRepository` usage and `assignee_id` already have their columns.

</code_context>

<specifics>
## Specific Ideas

- The evaluator's path must be exactly: `cp .env.example .env`, `docker compose up`, open
  `http://localhost:8000/health` → 200 with `"database": "ok"`; then `make docker-test` → green
  with the coverage gate. Nothing else to install, no manual migration step.
- The fail-fast message when `make test` cannot reach PostgreSQL should read like an
  instruction, not a traceback: name the URL, say `make up` or `make docker-test`.
- Constraint names are part of the contract: the repository error translation keys on them,
  so the migration and the repositories must share one source of those names (a constants
  module under `infrastructure/db/`).
- A test should demonstrate the D-01 isolation claim directly: commit through the UoW, then
  read from a second connection and see nothing.

</specifics>

<deferred>
## Deferred Ideas

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

</deferred>

---

*Phase: 03-persistence-runnable-stack*
*Context gathered: 2026-09-18*
