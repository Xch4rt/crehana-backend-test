# Pitfalls Research

**Domain:** FastAPI + async SQLAlchemy + PostgreSQL REST API delivered as a hiring take-home, built with AI assistance and an explicit AI-workflow narrative
**Researched:** 2026-09-17
**Confidence:** HIGH for library/tooling pitfalls (verified against Context7 + official docs), MEDIUM for evaluator-behaviour and AI-disclosure pitfalls (web sources, multiple credible sources agree)

> Phase names below map to the expected roadmap shape:
> **P1 Foundation & Tooling** · **P2 Domain & Architecture** · **P3 Persistence** ·
> **P4 Core API (lists/tasks/filters/completion %)** · **P5 Auth & Bonus** ·
> **P6 Test Hardening & Coverage** · **P7 Docs & Delivery**.
> If the roadmap renames phases, keep the topic mapping.

---

## The Meta-Pitfall (read this first)

This deliverable is judged in roughly this order by a human with limited time:

1. Does `docker compose up` work on a clean machine? (a startup failure ends the review)
2. Do the tests run and pass, and is coverage really ≥ 75%?
3. Is the layering real or cosmetic?
4. Does the code read like a person owned it, or like a model produced it?
5. Is `AI_WORKFLOW.md` credible, or does it read like marketing?

Every pitfall below is ranked by how much damage it does in that ordering. **A broken first run costs more points than any amount of architectural elegance.**

---

## Critical Pitfalls

### Pitfall 1: `MissingGreenlet` — implicit IO from async SQLAlchemy

**What goes wrong:**
`sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called; can't call await_only() here`. It fires when a lazy-loaded relationship (`task.assignee`, `task_list.tasks`), a deferred column, or an expired attribute is touched outside the async driver's greenlet context — most often inside a Pydantic `model_validate(orm_obj)` call in the router, after the use case already returned.

**Why it happens:**
SQLAlchemy's default relationship loading strategy is `lazy="select"`, which performs implicit IO on attribute access. Under `asyncio` that IO cannot be awaited implicitly. AI-generated code reproduces sync-ORM habits (`return db_obj` and let Pydantic walk the graph) that work fine under `Session` and explode under `AsyncSession`.

**How to avoid:**
- Set `lazy="raise"` (or `lazy="raise_on_sql"`) on every `relationship()` in the ORM models. This converts a runtime async crash into a loud, deterministic `InvalidRequestError` at development time, and forces every query to declare its loading strategy.
- Load explicitly: `select(TaskList).options(selectinload(TaskList.tasks))`. Prefer `selectinload` over `joinedload` for collections (no row multiplication).
- Map ORM rows → domain objects / DTOs **inside the repository**, while the session is still open. Never hand an ORM instance to a router or a Pydantic response model.
- Verified: SQLAlchemy 2.0 asyncio docs explicitly recommend eager loading up front and `AsyncSession.refresh()` (with attribute names) rather than implicit lazy load.

**Warning signs:**
- Any `from_attributes=True` Pydantic schema being fed a SQLAlchemy object in the presentation layer.
- A repository whose return type annotation is an ORM class.
- Tests pass individually but fail when the same object is used after `await session.commit()`.

**Phase to address:** P3 Persistence (set `lazy="raise"` the moment models are written; mapping boundary decided before the first repository ships).

---

### Pitfall 2: `expire_on_commit=True` — the default that breaks async

**What goes wrong:**
After `await session.commit()`, every loaded attribute is expired. The next attribute read (e.g. building the `201 Created` response body from the just-created entity) triggers a refresh SELECT → `MissingGreenlet`, or a silent extra round-trip.

**Why it happens:**
`expire_on_commit=True` is SQLAlchemy's default and is correct for sync code. The async docs explicitly recommend `False`, but the default is what a model reproduces from memory.

**How to avoid:**
Create the factory once: `async_sessionmaker(engine, expire_on_commit=False, autoflush=False)`. If a genuine refresh is needed, call `await session.refresh(obj, ["field"])` explicitly. Document the choice in `DECISION_LOG.md` — it is exactly the kind of small, justified decision evaluators reward.

**Warning signs:** A create/update endpoint that works in a unit test with a mocked repo but 500s in the integration test.

**Phase to address:** P3 Persistence.

---

### Pitfall 3: Session lifecycle — one session per request, commit at one place

**What goes wrong:**
Three variants, all common in AI-scaffolded projects:
- A module-level global `AsyncSession` shared across requests → concurrent-use errors (`This session is provisioning a new connection; concurrent operations are not permitted`) and cross-request data bleed.
- Every repository method opening and closing its own session → no transactional boundary, half-applied use cases, and objects detached between calls.
- `await session.commit()` sprinkled inside repository methods → the use case can no longer be atomic, and "create list + create default tasks" cannot be rolled back.

**Why it happens:**
Each layer "just wants to work", so each grabs a session. There is no explicit owner of the transaction.

**How to avoid:**
- Session is created per request by a FastAPI dependency (`async with session_factory() as session: yield session`), injected down into the repository.
- Repositories `add()` / `flush()` but **never** `commit()`. The unit of work (the dependency wrapper or an explicit `UnitOfWork` port) commits once on success and rolls back on exception.
- Use `session.flush()` when the use case needs a generated PK before commit.

**Warning signs:** `grep -rn "\.commit()" src/infrastructure/repositories/` returning hits. A `SessionLocal` created at import time and used directly.

**Phase to address:** P3 Persistence, decided before P4 builds use cases on top of it.

---

### Pitfall 4: pytest-asyncio event-loop / fixture-scope mismatch

**What goes wrong:**
`RuntimeError: Task ... attached to a different loop`, `Event loop is closed`, or `asyncpg.InterfaceError: cannot perform operation: another operation is in progress`. Tests pass one at a time and fail as a suite, or fail only in CI. A session-scoped engine/connection fixture is bound to loop A; each function-scoped test runs in a fresh loop B.

**Why it happens:**
In pytest-asyncio ≥ 0.23 the old `event_loop` fixture override is deprecated/removed and **fixture loop scope is independent from fixture caching scope**. Training data is full of the pre-0.23 `@pytest.fixture(scope="session") def event_loop(): ...` recipe, which an AI will confidently reproduce. Verified against current pytest-asyncio docs.

**How to avoid:**
- In `pytest.ini` (the file is a hard requirement anyway):
  ```ini
  [pytest]
  asyncio_mode = auto
  asyncio_default_fixture_loop_scope = function
  ```
  Setting `asyncio_default_fixture_loop_scope` explicitly also silences the deprecation warning pytest-asyncio emits when it is unset.
- Do **not** override `event_loop`. If a shared engine is wanted, use `@pytest_asyncio.fixture(loop_scope="session", scope="session")` — both parameters, matched. Otherwise keep everything function-scoped; with ~60-100 tests the cost is negligible and the reliability is worth more than the seconds saved.
- Pin `pytest-asyncio` to a specific minor version in requirements. Its config surface has changed three times across 0.21 → 0.23 → 0.24+.

**Warning signs:** An `event_loop` fixture anywhere in `conftest.py`. Any `@pytest.fixture(scope="session")` (not `pytest_asyncio.fixture`) wrapping an `async def`. Suite green locally, red in CI, or order-dependent failures (confirm with `pytest -p no:randomly` vs. shuffled runs).

**Phase to address:** P1 Foundation & Tooling (write `conftest.py` skeleton + `pytest.ini` before any test exists), re-verified in P6.

---

### Pitfall 5: Test database isolation — tests that pass only on an empty DB

**What goes wrong:**
Test 12 asserts `len(response.json()) == 3` and passes; after test 30 also creates lists, test 12 fails. Or the suite passes locally and fails in CI because CI starts from an empty volume and local does not. Or tests run against the *development* database and wipe the data the evaluator just created by hand.

**Why it happens:**
No rollback strategy. `create_all()` once at session start and then hope. Assertions written against absolute global state instead of against what the test itself created.

**How to avoid:**
Pick **one** strategy and apply it everywhere:
- **Preferred (fast, strict):** per-test outer transaction — open a connection, `begin()`, bind the `AsyncSession` to that connection, run the test, `rollback()`. Nothing ever commits to disk.
- **Acceptable (simpler, more obvious to a reader):** `TRUNCATE ... RESTART IDENTITY CASCADE` on all tables in a function-scoped autouse fixture.
- A **separate database name** (`taskmanager_test`), driven by an env var, created by the compose test profile. Never the dev DB.
- Override the FastAPI session dependency with `app.dependency_overrides[get_session]` so the app and the test share the same transaction.
- Assertions must be relative to fixtures the test created (assert the created id is in the response), not to global counts.

**Warning signs:** Assertions on absolute counts or on `id == 1`. A test that fails when run twice in a row. `create_all()` without a matching teardown.

**Phase to address:** P1 (harness design) and P6 (verification: run the suite twice in a row, and in random order).

---

### Pitfall 6: Coverage that looks like ≥ 75% but isn't

**What goes wrong:**
The brief mandates ≥ 75%. Three ways to report a number that an evaluator can disprove in thirty seconds:
- **Test files counted as source.** `pytest --cov=.` measures the `tests/` package too. Test files are ~100% executed by construction, so a 500-line test suite drags a 55% app to 80%.
- **Unimported modules invisible.** Without a `source` setting, coverage.py only reports files that were actually imported. A whole `infrastructure/notifications/` package that no test touches simply does not appear in the denominator. Verified: coverage.py docs state that *only* the `source` option lets coverage discover and report un-executed files.
- **No enforcement.** The number is quoted in the README from a run that no longer reflects `main`.

**How to avoid:**
- Configure explicitly (in `pyproject.toml` or `.coveragerc`):
  ```ini
  [coverage:run]
  source = app          # or src/ — makes unimported files show as 0%
  branch = True
  omit = */tests/*, */__init__.py, app/main.py  # only if justified in DECISION_LOG
  ```
- Run `pytest --cov=app --cov-report=term-missing --cov-fail-under=75` in the Makefile **and** in CI. The gate, not the claim, is the evidence.
- Sanity-check the denominator: `coverage report` total statement count should be within a few percent of `find app -name '*.py' | xargs wc -l` order of magnitude. A suspiciously small denominator means files are missing.
- Do not `omit` anything you wouldn't defend out loud. An evaluator reading `omit = app/infrastructure/*` will read it as gaming the number, and that costs more than the missing 5%.

**Warning signs:** `--cov=.` or bare `--cov` in `pytest.ini`. Coverage percentage that jumps when tests are added without app code being tested. A `omit` list longer than three entries.

**Phase to address:** P1 (configure the gate before writing tests, so it never has to be retrofitted), enforced continuously, audited in P6.

---

### Pitfall 7: Docker image that starts before Postgres is ready

**What goes wrong:**
`docker compose up` → API container exits with `asyncpg.exceptions.CannotConnectNowError` or `ConnectionRefusedError`. Evaluator sees a crash loop on first run. Two distinct causes:
- `depends_on: [db]` **without** a condition — Compose only waits for the container to *start*, not for Postgres to accept connections.
- A `pg_isready` healthcheck that returns healthy too early. **Verified gotcha:** the official `postgres` image's entrypoint runs a *temporary* server with `listen_addresses=''` (Unix socket only) while `initdb` and `/docker-entrypoint-initdb.d` scripts execute. `pg_isready` without `-h` talks to that socket and reports "accepting connections" while no TCP listener exists. It only bites on a **fresh volume**, which is exactly the evaluator's situation and never the developer's.

**How to avoid:**
```yaml
db:
  image: postgres:16-alpine
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -h 127.0.0.1 -U $$POSTGRES_USER -d $$POSTGRES_DB"]
    interval: 5s
    timeout: 5s
    retries: 10
    start_period: 10s
api:
  depends_on:
    db:
      condition: service_healthy
```
The `-h 127.0.0.1` forces a TCP probe, which fails until the real server is up. Additionally, make the app's startup retry connecting with a short backoff — belt and braces, and it is cheap.

**Warning signs:** The bug is invisible with a warm volume. **Always test with `docker compose down -v && docker compose up`** — that is the only run that matches the evaluator's.

**Phase to address:** P1 Foundation (compose skeleton), re-verified in P7 with a clean-machine rehearsal.

---

### Pitfall 8: Migration race / no migration story at all

**What goes wrong:**
Either (a) schema is created by `Base.metadata.create_all()` in the app's lifespan — which an evaluator reads as "no migration discipline"; or (b) Alembic is wired but `alembic upgrade head` runs inside the app's startup, so with multiple workers or a restart loop two processes race on the same migration and one dies on a duplicate-object error or an advisory-lock timeout; or (c) Alembic exists but the migration files were never generated, so a clean start has no tables.

**Why it happens:**
"It has to work with one command" pushes migration into app startup. AI scaffolds `create_all` because it is the shortest path to a running demo.

**How to avoid:**
- Run migrations as a **separate step**, not inside the app process: a dedicated one-shot compose service or a container `command` that does `alembic upgrade head && uvicorn app.main:app ...` with `--workers 1` for the challenge. State the choice explicitly in `DECISION_LOG.md`.
- Commit the generated migration files and verify them on a clean volume. An empty `versions/` directory is a hard fail.
- If Alembic is judged out of budget for a 4-6h challenge, that is defensible — but then say so in `DECISION_LOG.md` under pending work, and keep `create_all` in **one** obvious place, not scattered.
- Async Alembic needs `run_async_migrations` / `connection.run_sync(context.run_migrations)` in `env.py`; the sync template will not work with an `asyncpg` URL.

**Warning signs:** `create_all` inside `lifespan`. `alembic/versions/` empty or gitignored. Autogenerate producing an empty migration (usually means models were never imported into `env.py`'s `target_metadata`).

**Phase to address:** P3 Persistence.

---

### Pitfall 9: Layers that are folders, not boundaries

**What goes wrong:**
`domain/`, `application/`, `infrastructure/` exist, but `domain/entities/task.py` starts with `from sqlalchemy.orm import Mapped` and `from fastapi import HTTPException`. The use case imports `SessionLocal` directly. The "layering" is decorative, and an evaluator who opens two files sees through it immediately — which is worse than having no layers at all, because it reads as cargo-culting.

**Why it happens:**
It is genuinely more work to define a `TaskRepository` Protocol and map between ORM rows and domain objects. AI will happily create the folders and then put the ORM model in `domain/` because that is the shortest path from the prompt "clean architecture FastAPI".

**How to avoid:**
- One domain entity type (dataclass or plain Pydantic model with no ORM base), one separate ORM model in `infrastructure/persistence/models.py`, and an explicit mapper. Accept the duplication; it *is* the boundary.
- Ports as `typing.Protocol` in `domain/ports/` (or `application/ports/`). The use case depends on the Protocol; FastAPI's DI supplies the concrete SQLAlchemy implementation.
- **Enforce it with a test** — this is already in the project's "next level" list and it is the single highest-leverage differentiator here:
  ```python
  # tests/architecture/test_layer_boundaries.py
  FORBIDDEN_IN_DOMAIN = {"fastapi", "sqlalchemy", "starlette", "asyncpg", "alembic"}
  # walk app/domain/**/*.py, ast.parse, collect Import/ImportFrom roots, assert disjoint
  ```
  Using `ast` (not string grep) makes the test honest and non-trivial. Add `application` → must not import `fastapi` or `sqlalchemy` as a second assertion.

**Warning signs:** `grep -rn "^from \(fastapi\|sqlalchemy\)" app/domain/` returning anything. A domain entity with `__tablename__`. The architecture test existing but only checking that directories exist.

**Phase to address:** P2 Domain & Architecture — the boundary test must be written **in the same phase as the domain**, not bolted on later, or the violations accumulate faster than they can be fixed.

---

### Pitfall 10: `HTTPException` raised inside use cases

**What goes wrong:**
`application/use_cases/update_task.py` raises `HTTPException(404, "Task not found")`. The application layer now depends on FastAPI, unit-testing it requires importing a web framework, and Pitfall 9's boundary test fails. It also makes the error contract inconsistent, because some errors come from raw `HTTPException` (`{"detail": "..."}`) and some from custom handlers.

**Why it happens:**
It is the single most-repeated pattern in FastAPI tutorials and therefore the strongest attractor in any model's output.

**How to avoid:**
- Domain exception hierarchy: `DomainError` → `NotFoundError`, `ConflictError`, `ValidationError`, `PermissionDeniedError`. Pure Python, no HTTP status codes inside.
- **One** translation point: `app.add_exception_handler(DomainError, domain_error_handler)` in the composition root, mapping exception type → HTTP status + RFC 7807 `application/problem+json` body (`type`, `title`, `status`, `detail`, `instance`).
- Also register a handler for `RequestValidationError` so Pydantic's 422 is emitted in the *same* Problem Details shape. A project with two different error formats — one for 422 and one for everything else — undercuts the whole "consistent error contract" claim, and 422 is the response an evaluator will trigger first.
- Document the mapping table in the README.

**Warning signs:** `grep -rn "HTTPException" app/domain app/application` returning hits. Two different error JSON shapes in the OpenAPI examples.

**Phase to address:** P2 (exception hierarchy + handler skeleton), enforced by the P2 boundary test, exercised in P4/P5.

---

### Pitfall 11: Computing completion percentage in Python (N+1 in disguise)

**What goes wrong:**
`GET /lists` loads every list, then for each list loads all its tasks, then counts completed ones in a Python loop. That is 1 + N queries plus full row transfer, to produce two integers per list. It is the one place in this challenge where an evaluator can see whether the candidate actually thinks in SQL.

**Why it happens:**
The naive implementation is the obvious one and it "works" against the five rows in the demo data. It is also exactly what an AI produces from "add a completion percentage field".

**How to avoid:**
- Compute it in the database:
  ```sql
  SELECT l.id,
         COUNT(t.id) AS total,
         COUNT(*) FILTER (WHERE t.status = 'DONE') AS done
  FROM task_lists l LEFT JOIN tasks t ON t.list_id = l.id
  GROUP BY l.id
  ```
  (`func.count().filter(...)` in SQLAlchemy Core; PostgreSQL-specific `FILTER` is fine and worth a `DECISION_LOG` line.)
- **Resolve the ambiguity explicitly** (the PROJECT.md already flags it): is completion % over the whole list or over the filtered subset? Pick "always over the whole list, independent of filters" — it is the only definition where the number is stable and meaningful — return the filter-independent value, and write one sentence in `DECISION_LOG.md` plus a test named after the decision (`test_completion_percentage_ignores_status_filter`). Evaluators grade ambiguity-handling, not just code.
- Define the empty-list case: 0 tasks → `0.0`, not a `ZeroDivisionError` and not `null`. Test it.
- Decide and document the rounding/type: `float` rounded to 2 decimals, or integer percent. Pick one and keep it consistent across endpoints.

**Warning signs:** A `for` loop over `task_list.tasks` in a use case. `selectinload(TaskList.tasks)` on a list endpoint that only needs counts. Echo SQL on (`echo=True` temporarily) and count queries on `GET /lists`.

**Phase to address:** P4 Core API.

---

### Pitfall 12: JWT implemented from stale training data

**What goes wrong:** A cluster of issues, each individually enough to lose security points:

| Sub-pitfall | Why it's bad |
|---|---|
| `SECRET_KEY = "secret"` hard-coded in `config.py` and committed | Instant, visible security failure; also in the Docker image forever |
| No `exp` claim, or `exp` set but never verified | Tokens valid forever |
| `jwt.decode(token, key, algorithms=["HS256", "RS256", "none"])` or omitting `algorithms=` | Algorithm-confusion / `alg: none` acceptance |
| Login returns 404 "user not found" vs 401 "wrong password" | User/email enumeration oracle |
| Timing difference between "user missing" and "wrong password" | Enumeration oracle via response time |
| `UserResponse` schema includes `hashed_password` | Hash disclosure — offline cracking |
| `sub` claim set to an `int` user id | PyJWT ≥ 2.10 rejects non-string `sub`; will 401 everything |
| `python-jose` + `passlib[bcrypt]` | **Both are the stale-training-data tell** (see below) |

**Why it happens:**
The most-replicated FastAPI auth snippet on the internet uses `python-jose` and `passlib`. **Verified: FastAPI's current official OAuth2-JWT tutorial uses `PyJWT` and `pwdlib` (Argon2), not `python-jose`/`passlib`.** `python-jose` has had long maintenance gaps, and `passlib` 1.7.4 (last release 2020, effectively unmaintained) famously breaks against `bcrypt` ≥ 4.1 with `(trapped) error reading bcrypt version: AttributeError: module 'bcrypt' has no attribute '__about__'` — a warning an evaluator will see in the test output and read as "unpinned, unverified dependencies".

**How to avoid:**
- Use **PyJWT**. Use **pwdlib[argon2]** (or `bcrypt` directly); if `passlib` is used anyway, pin `bcrypt==4.0.1` and say why — but just don't.
- `SECRET_KEY` from env via `pydantic-settings`, **no default value** in the settings class so the app refuses to boot without it. `.env.example` holds a dummy; `.env` is gitignored; `docker-compose.yml` reads `${JWT_SECRET_KEY:?JWT_SECRET_KEY is required}` so a missing secret fails loudly rather than silently defaulting.
- Always `jwt.decode(token, key, algorithms=[ALGORITHM])` with a single-element list. Catch `jwt.InvalidTokenError` (the base class), not just `ExpiredSignatureError`.
- `sub` must be `str(user.id)`.
- Login: **one** response for both "no such user" and "bad password" — `401` with an identical generic body. Mitigate the timing oracle by verifying against a module-level dummy hash when the user is not found (this is exactly what the current FastAPI tutorial does — copy the pattern and cite it in `DECISION_LOG.md`).
- Separate `UserCreate` / `UserPublic` schemas. Never reuse the ORM-facing model as a response model. Add a test: `assert "hashed_password" not in response.json()` and `assert "password" not in response.json()`.
- `datetime.now(timezone.utc) + timedelta(minutes=...)` for `exp`.

**Warning signs:** Any literal string assigned to a secret. `algorithms=` missing. A response model that inherits from a model containing the hash field. `python-jose` or `passlib` in `requirements.txt`.

**Phase to address:** P5 Auth & Bonus, with the secret-from-env decision made in P1.

---

### Pitfall 13: 404 vs 403 — ownership information leakage

**What goes wrong:**
`GET /lists/{id}` on a list owned by another user returns `403 Forbidden`. That confirms the resource exists, letting an attacker enumerate the id space and learn how many lists exist and which ids are taken. Alternatively — and more commonly in take-homes — the ownership check is simply **missing**, and any authenticated user can read and delete anyone's lists. That is an IDOR/BOLA, the #1 item on the OWASP API Security Top 10, and the fastest way for a security-minded evaluator to fail the submission.

**Why it happens:**
The repository method is `get_by_id(id)`, and adding `owner_id` to the query feels like duplicating the auth check. So the check gets deferred, then forgotten. Nested routes make it worse: `PATCH /lists/{list_id}/tasks/{task_id}` needs the ownership check on the **parent**, and it is easy to validate only the task.

**How to avoid:**
- **Return `404` for "exists but not yours"** on read/update/delete of a resource the user has no visibility into. `403` is correct only when the user can legitimately see the resource but lacks permission for *this* action. Write one sentence in `DECISION_LOG.md` explaining the choice — this is a genuine engineering-judgement signal.
- Scope at the query level, not with a post-fetch `if`: `select(TaskList).where(TaskList.id == id, TaskList.owner_id == current_user.id)`. One query, impossible to forget the second predicate, no TOCTOU gap.
- For nested task routes, always resolve the parent list under the ownership predicate first; a task is reachable only through a list the caller owns.
- **Write the negative tests.** `test_cannot_read_other_users_list_returns_404`, `..._cannot_update_...`, `..._cannot_delete_...`, `..._cannot_add_task_to_...`. A suite that only tests the happy path is the clearest signal that the tests were generated rather than reasoned about.
- Decide and document what "assign a responsible user" means across ownership: can you assign a task to a user who does not own the list? (Recommended: yes — that is what the fake invitation email is for — and it is the answer that makes the bonus features cohere.)

**Warning signs:** A repository `get_by_id(self, id)` with no owner/tenant parameter. Zero tests with two different users. A `403` anywhere in the ownership path.

**Phase to address:** P5 Auth (rule + tests), but the repository signatures must be designed for it in P3, otherwise every method needs changing later.

---

### Pitfall 14: README that doesn't work on a clean machine

**What goes wrong:**
The evaluator follows the README and hits: a missing `.env` (gitignored, never templated), `docker compose up` failing because the image expects a network or volume created by an earlier manual step, `pytest` failing because it needs a running Postgres that the README never mentions starting, a port 5432 collision with the evaluator's own local Postgres, or an `arm64`/`amd64` build failure. **Verified as the #1 reviewer complaint: a large share of take-home submissions fail on first execution, and reviewers reject rather than debug.**

**Why it happens:**
The author's machine has accumulated state: an `.env`, a warm Docker volume, an installed virtualenv, an already-created database. None of it is in the repo, and none of it is visible from inside the working directory.

**How to avoid:**
- **Rehearse the clean-machine run as an explicit task**, not as a final glance:
  ```bash
  git clone <url> /tmp/clean && cd /tmp/clean
  docker compose down -v --remove-orphans     # in the original checkout first
  docker compose up --build                   # in /tmp/clean
  ```
  Anything you have to type that is not in the README is a README bug.
- Commit `.env.example` and make the compose file work with **zero** manual setup (sensible non-secret defaults inline, `env_file: .env` optional). If `cp .env.example .env` is required, it must be literally step 1 of the README.
- Do not publish port 5432 on the host, or publish it as `5433:5432`. Evaluators frequently already run Postgres.
- Provide **one** documented command for tests that does not assume an existing DB: `make test` → `docker compose run --rm api pytest`. Also document the local-venv path, but make the Docker path the primary one.
- Pin the base image (`python:3.12-slim-bookworm`) and pin every dependency with `==` in `requirements.txt`. An unpinned `fastapi` that resolves to a new major during the evaluator's build is a preventable failure. (A `requirements.lock` / `pip-compile` output earns extra credit and costs ten minutes.)
- README structure that matches what the brief asks for, in this order: what it is → prerequisites → run with Docker (one command) → run tests → run locally without Docker → API docs link (`/docs`) → project structure → error contract → what's not done.

**Warning signs:** `.env` in `.gitignore` with no `.env.example` beside it. A README step that says "make sure Postgres is running". Build succeeding only because of Docker layer cache — test with `--no-cache` at least once.

**Phase to address:** P7 Docs & Delivery, with a mandatory clean-clone rehearsal as an explicit acceptance criterion.

---

### Pitfall 15: Deprecated idioms that broadcast "generated from stale training data"

**What goes wrong:**
The code runs, but the test output is full of `DeprecationWarning`s and the patterns are visibly one or two major versions behind. For a submission whose entire thesis is *"I direct AI to produce impeccable work"*, stale idioms are the most damaging possible detail — they prove the opposite of the claim.

**Verified deprecations relevant to this stack:**

| Stale idiom | Current form | Status |
|---|---|---|
| `@app.on_event("startup")` / `("shutdown")` | `lifespan=asynccontextmanager` passed to `FastAPI()` | Deprecated in FastAPI; docs label the event handlers "Alternative Events (deprecated)" |
| `datetime.utcnow()` | `datetime.now(timezone.utc)` | Deprecated since Python 3.12 |
| `datetime.utcfromtimestamp(x)` | `datetime.fromtimestamp(x, tz=timezone.utc)` | Deprecated since Python 3.12 |
| `class Config:` inside a model | `model_config = ConfigDict(...)` | Pydantic v2; defining both raises `PydanticUserError(code='config-both')` |
| `orm_mode = True` | `from_attributes=True` | Pydantic v2 |
| `.dict()` / `.json()` | `.model_dump()` / `.model_dump_json()` | Pydantic v2 deprecated |
| `parse_obj` / `from_orm` | `model_validate()` | Pydantic v2 deprecated |
| `@validator` / `@root_validator` | `@field_validator` / `@model_validator` | Pydantic v2 |
| `from pydantic import BaseSettings` | `from pydantic_settings import BaseSettings` | Moved to a separate package in v2 |
| `declarative_base()` + `Column(...)` | `DeclarativeBase` + `Mapped[...]` / `mapped_column(...)` | SQLAlchemy 2.0 style |
| `session.query(Model)` | `select(Model)` + `session.execute()` / `.scalars()` | SQLAlchemy 2.0 style; `Query` is legacy and has no async form |
| `python-jose`, `passlib` | `PyJWT`, `pwdlib`/`bcrypt` | Current FastAPI tutorial |
| `TestClient` for async tests | `httpx.AsyncClient(transport=ASGITransport(app=app))` | Current FastAPI async-testing docs |
| naive `DateTime` columns | `DateTime(timezone=True)` → `timestamptz` | Postgres correctness |

**How to avoid:**
- `filterwarnings = error::DeprecationWarning` in `pytest.ini` (with a short, commented allowlist for third-party noise you cannot fix). This turns the entire table above into an automatic, enforced gate — and it is a genuinely impressive line for an evaluator to find in `pytest.ini`.
- Add `mypy --strict` (already planned) and consider `ruff` alongside flake8 for the deprecation-adjacent rules — but `flake8` must remain the declared linter per the brief.
- Make timezone-awareness a rule: all columns `DateTime(timezone=True)`, all Python datetimes aware UTC, all API output ISO-8601 with offset. A naive `created_at` compared against an aware `datetime.now(timezone.utc)` raises `TypeError: can't compare offset-naive and offset-aware datetimes` — usually discovered in a due-date validation, at the worst moment.

**Warning signs:** Any warning in the pytest summary line. `grep -rn "utcnow\|orm_mode\|class Config\|\.dict()\|session.query\|on_event" app/`.

**Phase to address:** P1 (`filterwarnings = error` in `pytest.ini` from commit one — retrofitting it later means fixing dozens of call sites at once).

---

### Pitfall 16: flake8 / black / isort fighting each other

**What goes wrong:**
`make lint` fails on code that `black` just formatted: `E203 whitespace before ':'` on slices, `W503 line break before binary operator` on black's operator placement, `E501 line too long` because flake8 defaults to 79 and black to 88. Or pre-commit loops: black reformats, isort un-formats, black reformats. A submission where the declared linter fails on the declared formatter's output is a direct hit on "modern Python tooling", which is an explicit grading criterion.

**Why it happens:**
flake8 (pycodestyle) predates black and has different opinions. The configs are in three different files.

**How to avoid:**
`.flake8` (the file is a hard requirement of the brief):
```ini
[flake8]
max-line-length = 88
extend-ignore = E203, E701
extend-exclude = .venv,migrations,alembic
max-complexity = 10
```
- **Use `extend-ignore`, not `ignore`.** Verified: flake8's default ignore list is `E121, E123, E126, E226, E24, E704, W503, W504`. Writing `ignore = E203, W503` **replaces** that list, silently re-enabling `E121/E123/E126/E226/E704` — which then conflict with black. This is a subtle, real trap and the reason W503 no longer needs to be listed at all (it is already a default). Verified against current black docs, which recommend exactly `extend-ignore = E203, E701`.
- isort in `pyproject.toml`: `[tool.isort]` → `profile = "black"` (plus `line_length = 88`). Nothing else.
- black in `pyproject.toml`: `[tool.black]` → `line-length = 88`, `target-version = ["py312"]`.
- Order the pre-commit hooks **isort → black → flake8**. Any other order oscillates.
- CI must run `black --check .`, `isort --check-only .`, `flake8 .` — check mode, not write mode, so CI fails instead of silently "fixing".
- Exclude Alembic's auto-generated `versions/` from flake8 or the generated files will fail line-length checks.

**Warning signs:** `make lint` and `make format` disagreeing. pre-commit modifying files on a second consecutive run. `ignore =` (without `extend-`) in `.flake8`.

**Phase to address:** P1 Foundation & Tooling — before the first line of app code, so the whole history is clean.

---

### Pitfall 17: Docker image that fails a basic review

**What goes wrong:** Multiple independent deductions, each cheap to prevent:

| Issue | Why it costs points | Fix |
|---|---|---|
| Container runs as `root` | Default, but a known bad practice reviewers look for | `RUN adduser --system --no-create-home app` + `USER app` |
| No `.dockerignore` | `.git`, `.venv`, `__pycache__`, `.env`, `.pytest_cache` copied into the image — slow build, and **`.env` with the real secret is baked into a layer** | `.dockerignore` with `.git`, `.venv`, `__pycache__`, `*.pyc`, `.env`, `.pytest_cache`, `htmlcov`, `.mypy_cache`, `.planning` (decide) |
| Secrets via `ENV JWT_SECRET=...` or `ARG` | Persist in image layers, recoverable with `docker history` | Inject at runtime via compose `environment:` / `env_file:` |
| "Multistage" that is one stage with a label | The brief asks for multistage explicitly | Real builder stage (compile wheels / `pip install --prefix`) → slim runtime stage that copies only site-packages + app |
| `COPY . .` before `pip install` | Every code edit invalidates the dependency layer; rebuilds are slow for the evaluator | `COPY requirements.txt` → `pip install` → `COPY . .` |
| No `HEALTHCHECK` on the API | Compose can't tell running from working | `HEALTHCHECK CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').status==200 else 1)"` + a real `/health` endpoint that pings the DB |
| `python:3.12` (full) base | ~1GB image | `python:3.12-slim-bookworm`, pinned |
| `--reload` in the production command | Dev flag shipped as prod | `--reload` only via a compose override / dev target |
| `PYTHONDONTWRITEBYTECODE` / `PYTHONUNBUFFERED` unset | Logs buffered → evaluator sees no output | Set both |

**How to avoid:** Treat the Dockerfile as a reviewed artifact, and add a one-line justification per stage in `DECISION_LOG.md`. Verify with `docker history <image>` (no secrets), `docker run --rm <image> whoami` (not root), and `docker images` (size).

**Warning signs:** Image > 500MB. `whoami` → `root`. `.env` present inside `docker run --rm -it <image> ls -a`.

**Phase to address:** P1 (skeleton) and P7 (hardening pass + verification commands).

---

### Pitfall 18: The AI-generated-code tells

**What goes wrong:**
The code is *correct* but unmistakably machine-authored, which directly undermines the submission's central claim of *directed*, *verified* AI use. Reviewers in 2026 explicitly name "polished but unowned" as the loud red flag. The tells:

- **Over-commenting.** `# Create the task` above `task = Task(...)`. `"""Get a task by id.\n\nArgs:\n    id: The id.\nReturns:\n    The task."""` on a two-line function. Docstrings that restate the signature carry zero information and are the single most recognisable tell.
- **Dead code.** Unused imports, a `utils.py` with helpers nobody calls, an abstract method with no second implementation, a `# TODO: implement caching` in a 4-hour challenge, commented-out alternatives left in place.
- **Inconsistent naming across files.** `task_list` / `tasklist` / `list_` / `todo_list` for the same concept. `get_by_id` in one repository and `find_one` in another. `id` vs `uuid` vs `pk`.
- **Hallucinated or half-real APIs.** A `selectinload` import that is never used; a call to a SQLAlchemy/Pydantic method that does not exist on the installed version; `pytest.mark.asyncio` used while `asyncio_mode = auto` is set.
- **Tests that assert nothing.** `assert response.status_code == 200` and nothing else. `assert result is not None`. `assert True`. Mocks that are configured and never asserted against. Tests named `test_create_task_success` that never verify the task was persisted. These inflate coverage while proving nothing — the exact combination an evaluator is trained to spot.
- **Mirror tests.** A test that reimplements the production logic and asserts they agree, so both are wrong together.
- **Shape uniformity.** Every function the same length, every module with an identical header, perfectly regular — real code has irregular density.

**How to avoid:**
- **Comment policy, stated in the README/`AI_WORKFLOW.md`:** comments explain *why*, never *what*. Docstrings only on public use cases and non-obvious domain rules. Delete every comment that a reader could infer from the line below it. This single pass changes the texture of the whole repo.
- **Assertion policy:** every test asserts on the response **body**, not only the status code. Every mutating test re-reads through the API (or repository) to confirm persistence. Every error test asserts the RFC 7807 `type`/`title`, not just the status.
- **Vulture / flake8 F401** in CI to kill dead code and unused imports automatically. `mypy --strict` catches most hallucinated attributes at CI time.
- **Naming glossary** decided in P2 (`TaskList`, `Task`, `status`, `priority`, `assignee_id`, `owner_id`) and used verbatim everywhere — code, DB columns, JSON fields, tests, docs.
- **Read every file once, out loud, before the final commit.** If you cannot explain a line, delete or rewrite it. The interview follow-up will ask.
- **Mutation-testing spot check** (optional, 15 min): run `mutmut` or manually break one domain rule and confirm a test goes red. A suite that stays green when the completion-% formula is inverted is a suite that asserts nothing.

**Warning signs:** Coverage high but the suite stays green after you deliberately break a business rule. Any docstring longer than the function. More than ~1 comment per 15 lines. Two names for one concept.

**Phase to address:** P6 Test Hardening (assertion audit + deliberate-break check) and P7 (a dedicated "read-through and de-AI" pass). Naming glossary in P2.

---

### Pitfall 19: `AI_WORKFLOW.md` that reads as marketing

**What goes wrong:**
The differentiator becomes the liability. A document full of "leveraged cutting-edge AI to deliver a production-grade, enterprise-ready solution", five beautiful Mermaid diagrams, and zero specifics reads as self-promotion and invites the reviewer to hunt for the gap between the claim and the code. Worse: a fabricated narrative ("AI suggested X, I rejected it") that does not match the git history is straightforwardly dishonest and detectable — the commits are right there. PROJECT.md already sets the constraint: *"must reflect what genuinely happened — no fabricated narrative."*

**Why it happens:**
The document is written last, from memory, with the goal of impressing. Both of those are the wrong inputs.

**How to avoid:**
- **Write it incrementally, during the work.** Keep a running log of specific incidents as they happen. Retroactive reconstruction is where fabrication creeps in.
- **Be concrete and falsifiable.** Not "AI made mistakes that I caught" but: *"The first repository implementation returned SQLAlchemy objects directly to the router; the integration test failed with `MissingGreenlet`. I introduced an explicit ORM→domain mapper and set `lazy='raise'` so the failure mode becomes deterministic. Commit `a1b2c3d`."* Every claim should point at a commit, a test name, or a file.
- **Include at least three real AI mistakes**, including one you did not catch immediately. A log with zero mistakes is not credible. The most valuable entries are the ones that are slightly unflattering.
- **State the division of labour bluntly.** A table: *Decision* | *Made by* | *Why*. Human: stack choices, layering, 404-vs-403, completion-% semantics, scope cuts. AI: boilerplate, test scaffolding, first drafts, docstrings. Mixed: naming, error taxonomy.
- **Name the verification, not the intention.** "Quality gates" means nothing; "CI runs `black --check`, `isort --check-only`, `flake8`, `mypy --strict`, `pytest --cov-fail-under=75`, and the layer-boundary test on every push — badge above" means everything. The gates are the argument; the prose is just an index to them.
- **Keep it short.** One page of specifics plus two diagrams beats five pages. Adjectives ("robust", "seamless", "enterprise-grade", "world-class", "leveraged") are the marketing tell — cut every one.
- **Include a "what I did not do" section.** Scope cuts with reasons are the strongest credibility signal in the whole document, and the brief explicitly asks for uncovered items to be documented.
- **Be ready to defend it live.** Assume every line becomes an interview question. Verified reviewer consensus: honest, specific disclosure is rewarded; polished work the candidate cannot defend is the failure mode.
- Committing `.planning/` is a genuine differentiator **only if** the artifacts match the code that shipped. Stale planning docs that contradict the implementation are worse than no planning docs. Reconcile before the final commit.

**Warning signs:** No commit hashes / file paths / test names in the document. An "AI mistakes" section where every mistake was caught instantly. Superlatives. Diagrams that describe an idealised process rather than the one in the git log.

**Phase to address:** Started in P1 (log as you go, one entry per phase), finalised and reconciled against git history in P7.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|---|---|---|---|
| ORM model used as the domain entity | Saves the mapper; half the code | Kills the layering claim — the project's stated differentiator; Pitfall 1 becomes unavoidable | **Never here.** The brief grades structure explicitly |
| `Base.metadata.create_all()` instead of Alembic | Working demo in 10 minutes | No schema evolution story; reads as inexperience | Acceptable **only** if declared in `DECISION_LOG.md` as a scoped-out item with the reason |
| `dict` / `Any` instead of Pydantic schemas on internal boundaries | Less typing | Brief mandates "strong typing with Pydantic"; `mypy --strict` will fail anyway | Never |
| Sync `psycopg2` + sync SQLAlchemy | Removes every async gotcha in this document | `async def` endpoints blocking the event loop; inconsistent with FastAPI's selling point | Acceptable **if fully consistent** — sync engine **and** `def` (not `async def`) endpoints so Starlette uses the threadpool. A coherent sync stack is far better than a broken async one. Decide in P3, never mix |
| Integration tests only, no unit tests | Fewer tests, same coverage number | Brief asks for "unit **and** integration"; slow suite; failures don't localise | Never — the brief names both |
| SQLite for tests, Postgres for prod | Fast, no container needed for tests | Divergent SQL (`FILTER`, `timestamptz`, `ARRAY`, identity semantics); tests can pass on code that fails in prod | Never here — the brief's "real database" is the point, and the completion-% query uses PostgreSQL syntax |
| Skipping the fake-notification bonus | ~30 min saved | One of three bonus items unclaimed | Acceptable if documented, but it is the cheapest bonus of the three — an in-memory/logging `NotificationPort` is ~20 lines and demonstrates ports-and-adapters better than anything else in the project |
| `# type: ignore` to get mypy green | Unblocks CI | Each one is a visible admission; reviewers grep for them | ≤ 2, each with a trailing comment explaining why |
| Reusing one Pydantic schema for request and response | Fewer classes | Leaks `hashed_password`; lets clients set `id`/`owner_id`/`created_at` (mass assignment) | Never for anything touching users or ownership |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|---|---|---|
| PostgreSQL ↔ SQLAlchemy async | `DATABASE_URL=postgresql://...` with an async engine → `InvalidRequestError: The asyncio extension requires an async driver` | `postgresql+asyncpg://...`. Keep a separate sync URL for Alembic (`postgresql+psycopg://`) or use Alembic's async template |
| PostgreSQL ↔ Docker networking | `localhost:5432` inside the API container | Service name: `db:5432`. Host tooling uses `localhost:5433`. Two different URLs — document both in `.env.example` |
| PostgreSQL ↔ Compose startup | `depends_on: [db]` (no condition), or `pg_isready` over the Unix socket | `condition: service_healthy` + `pg_isready -h 127.0.0.1 -U ... -d ...` (see Pitfall 7) + app-side retry |
| asyncpg ↔ pgbouncer / prepared statements | Not relevant at this scale, but AI will add `statement_cache_size=0` cargo-cult | Omit. Don't add configuration you can't justify |
| asyncpg ↔ enum columns | Python `enum.Enum` mapped to a PG `ENUM` type needs the type created by the migration; `create_all` handles it, Alembic autogenerate often doesn't | Prefer `String` + a domain-level `StrEnum` validated by Pydantic. Simpler, migration-friendly, and keeps the enum in the domain layer |
| FastAPI ↔ Pydantic v2 | `response_model` returning an ORM object without `from_attributes=True` | Map to the schema explicitly in the router or repository; `from_attributes` only where deliberate |
| FastAPI ↔ httpx test client | `AsyncClient(app=app)` — removed in httpx 0.28 | `AsyncClient(transport=ASGITransport(app=app), base_url="http://test")` (current FastAPI docs) |
| FastAPI ↔ lifespan in tests | Lifespan never runs with a bare `TestClient(app)` call, so startup wiring is skipped | Use `with TestClient(app) as client:` (context manager), or `LifespanManager` for async clients — or, better, don't put essential wiring in lifespan at all |
| FastAPI ↔ dependency overrides | Overriding a dependency but forgetting to clear it → leaks into later tests | Set in a fixture, `app.dependency_overrides.clear()` in teardown |
| Fake notification adapter | Calling it "fake" but actually importing `smtplib` / adding an SMTP config that's never used | A `NotificationPort` Protocol + an `InMemoryNotificationAdapter` that appends to a list and logs. Assert on the captured list in tests — that assertion is what makes the port meaningful |
| GitHub Actions ↔ Postgres | Trying to `docker compose up` inside the runner | `services: postgres:` in the job, `ports: 5432:5432`, plus the `options: --health-cmd pg_isready` health options |
| pre-commit ↔ CI | pre-commit hooks locally, different versions in CI → CI fails on committed code | CI runs `pre-commit run --all-files`, single source of truth for tool versions |

---

## Performance Traps

Scale here is a demo, so the only trap that *matters* is the one an evaluator can see by reading. Ranked accordingly.

| Trap | Symptoms | Prevention | When It Breaks |
|---|---|---|---|
| N+1 on `GET /lists` (completion % in Python) | 1 + N queries visible with `echo=True`; obvious on code read | Aggregate in SQL (Pitfall 11) | Visible to a reviewer at **any** scale — this is a code-review failure, not a runtime one |
| N+1 on `GET /lists/{id}/tasks` loading `task.assignee` per row | Lazy load per task | `selectinload(Task.assignee)` | Same — read-visible immediately |
| Blocking call inside `async def` | Whole event loop stalls | No `requests`, no `time.sleep`, no sync file IO, no sync password hashing in an `async def` handler. Argon2/bcrypt hashing is CPU-heavy (~100-300ms): run it via `run_in_threadpool` or make the login handler a `def` | Login under any concurrency |
| No index on `tasks.list_id` / `task_lists.owner_id` | Seq scans | Index every FK used in a `WHERE`; `ForeignKey` does **not** create an index in PostgreSQL | ~10k rows — but the missing index is read-visible in the model, which is the real cost |
| `SELECT *` + Python filtering for status/priority filters | Filters implemented as list comprehensions after fetching | Push filters into the `WHERE` clause; build the statement conditionally | Read-visible; also makes pagination impossible later |
| Unbounded list endpoints (no limit) | Fine with 10 rows | Out of scope per PROJECT.md — but mention pagination in the README's "pending work" so the reviewer knows you saw it | 10k+ tasks |
| Default `pool_size=5` with no `pool_pre_ping` | Stale connections after DB restart → first request fails | `create_async_engine(url, pool_pre_ping=True)` | Any container restart during the evaluator's session |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---|---|---|
| Hard-coded / defaulted `SECRET_KEY` | Anyone can forge tokens; visible in the repo | Env var via `pydantic-settings` with **no default**; app refuses to boot without it |
| `.env` committed or baked into the image | Credential leak, permanent in git history and image layers | `.gitignore` + `.dockerignore` + `.env.example`; verify with `git log --all -- .env` and `docker history` |
| Missing ownership predicate (IDOR/BOLA) | Any user reads/deletes any list — OWASP API #1 | Scope every query by `owner_id`; explicit cross-user negative tests (Pitfall 13) |
| `403` instead of `404` for others' resources | Resource-existence enumeration | `404` for invisible resources; document the choice |
| Distinguishable login failures (message, status, or timing) | User/email enumeration | Identical `401` body for both cases; dummy-hash verification when the user is missing |
| `hashed_password` in a response model | Offline cracking of every user's password | Separate `UserPublic` schema + an explicit test asserting absence |
| `algorithms=` omitted or multi-valued in `jwt.decode` | Algorithm confusion, `alg: none` acceptance | Single-element allowlist, always |
| No `exp`, or `exp` present but verification disabled | Tokens valid forever | Always set `exp`; never pass `options={"verify_exp": False}` |
| Password policy absent (`"a"` accepted) | Trivial credentials; also a missed "business validations" point | Pydantic `Field(min_length=8)` + a domain rule; test the rejection |
| Mass assignment via a shared schema | Client sets `owner_id`, `id`, `is_admin`, `created_at` | Distinct `Create` / `Update` / `Public` schemas; `model_config = ConfigDict(extra="forbid")` on inputs |
| Stack traces / SQL errors returned to the client | Schema and path disclosure | Catch-all handler returning a generic RFC 7807 `500`; log the detail server-side with a correlation id |
| `allow_origins=["*"]` with credentials | CORS misconfiguration | Only add CORS if needed; if added, an explicit origin list |
| Container runs as root | Container-escape blast radius; a standard review checklist item | `USER app` in the final stage |
| `POSTGRES_PASSWORD: postgres` in a committed compose file | Fine for local dev, bad if unexplained | Acceptable for the challenge **with** a comment saying it is dev-only and a README line about production secret management |
| Unpinned dependencies | Supply-chain exposure; non-reproducible builds | `==` pins; optionally `pip-audit` in CI (cheap, and a visible signal) |

---

## UX Pitfalls

"User" here means **the evaluator** and **the API consumer**.

| Pitfall | User Impact | Better Approach |
|---|---|---|
| README buried under a wall of architecture prose | Reviewer can't find the run command in 30s | Quickstart (3 commands) in the first screen; architecture below |
| No seed data | `/docs` shows an empty API; reviewer must create everything by hand to see the completion % work | A `make seed` command or an optional seed on first boot: 2 users, 3 lists, mixed-status tasks. Makes the feature self-demonstrating |
| No `/health` endpoint | Reviewer can't tell "up" from "working"; no compose healthcheck target | `GET /health` returning `{"status": "ok", "database": "ok"}` after a `SELECT 1` |
| Undocumented enum values | Reviewer guesses `status: "completed"`, gets 422, assumes it's broken | Enums in the OpenAPI schema (Pydantic `StrEnum` does this automatically) + a table in the README + `examples=` on the fields |
| Generic 422 with no field context | API consumer can't fix their request | Map `RequestValidationError` into the same Problem Details shape with a per-field `errors` array |
| Inconsistent response envelope | Some endpoints return a bare list, some `{"data": [...]}`, some `{"items": [...]}` | Pick one and apply it everywhere. For the list-with-completion endpoint, `{"completion_percentage": 62.5, "items": [...]}` is self-documenting |
| No OpenAPI metadata | `/docs` looks like a default scaffold | `FastAPI(title=..., description=..., version=...)`, `tags_metadata`, `summary=`/`description=` and `responses={404: ...}` on each route. Cheap, and `/docs` is the first thing a reviewer opens |
| `DELETE` returning `200` with a body, or `PUT` used where `PATCH` is meant | Reads as sloppy REST design — an explicit grading criterion | `204 No Content` for delete; `PATCH` for partial updates with all-optional fields; `POST` → `201` + `Location` header |
| Status-change endpoint design left vague | Reviewer wonders whether the requirement was actually met | A dedicated `PATCH /lists/{lid}/tasks/{tid}/status` makes "change the status of a task" unmistakably present as its own use case — the brief lists it separately, so surface it separately |

---

## "Looks Done But Isn't" Checklist

- [ ] **`docker compose up`** — verified after `docker compose down -v` **and** from a fresh `git clone` into a different directory, with `--no-cache`
- [ ] **Tests** — pass twice in a row without a DB reset; pass in random order; pass in CI on a clean runner
- [ ] **Coverage ≥ 75%** — with `source = app`, `tests/` omitted, `--cov-fail-under=75` wired into CI (not just quoted in the README)
- [ ] **`pytest.ini` and `.flake8` exist as literal files** — the brief names them; a `pyproject.toml`-only setup technically fails a literal reading
- [ ] **Linters** — `black --check`, `isort --check-only`, `flake8`, `mypy` all green on the committed tree, and green in CI
- [ ] **Completion percentage** — defined for the empty list (0, not a crash); semantics vs. filters decided, documented, and covered by a named test
- [ ] **Filters** — `status` alone, `priority` alone, both together, and neither; invalid enum value → 422 in the Problem Details shape
- [ ] **Ownership** — a second user cannot GET / PATCH / DELETE the first user's list, nor add a task to it (four separate tests)
- [ ] **Auth** — expired token → 401; malformed token → 401; missing header → 401; valid token on another user's resource → 404
- [ ] **No secrets in the repo or image** — `git log --all --full-history -- .env` empty; `docker history` clean; `whoami` in the container is not `root`
- [ ] **Migrations** — `alembic/versions/` is non-empty and committed; a clean volume reaches `head` without manual steps
- [ ] **Every response model** — checked for leaked fields (`hashed_password`, internal ids, `owner_id` where it shouldn't be)
- [ ] **Zero warnings** in the pytest output (enforced by `filterwarnings = error`)
- [ ] **Architecture test** exists, uses `ast` (not grep), and actually fails when you add `import fastapi` to a domain file — **verify by temporarily adding it**
- [ ] **README** — every command copy-pasted and run verbatim, in order, on a clean checkout
- [ ] **`DECISION_LOG.md`** — every brief ambiguity listed with a resolution (completion-% scope, status values and transitions, priority values, who can be assigned, what triggers the fake invitation)
- [ ] **`AI_WORKFLOW.md`** — every claim traceable to a commit, test, or file; at least three real mistakes logged; `.planning/` reconciled with what shipped
- [ ] **Pending work** section — everything not done is listed with a reason (the brief explicitly requires this)
- [ ] **CI badge** green on the public repo's `main`, and the repo is actually public (open it in a logged-out browser)

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---|---|---|
| `MissingGreenlet` everywhere | MEDIUM | Add `lazy="raise"` to all relationships, fix each surfaced site with `selectinload`, move ORM→domain mapping into repositories. Painful but mechanical; cost grows superlinearly with how late it's done |
| ORM model doubles as domain entity | HIGH | Requires introducing entities, mappers, and port signatures across every layer. **Do not defer this decision past P2/P3** |
| pytest event-loop chaos | LOW | Delete the `event_loop` override, set `asyncio_mode = auto` + `asyncio_default_fixture_loop_scope = function`, make everything function-scoped. Usually a 20-minute fix |
| Coverage below 75% near the deadline | LOW–MEDIUM | `--cov-report=term-missing`, target the largest uncovered use cases first. **Do not** add `omit` entries — that's the visible, unrecoverable version of the mistake |
| Postgres readiness race discovered late | LOW | Healthcheck + `condition: service_healthy` + `-h 127.0.0.1` + app-side retry. 15 minutes |
| flake8/black war | LOW | `extend-ignore = E203, E701`, `max-line-length = 88`, isort `profile = "black"`, hook order isort→black→flake8 |
| `HTTPException` scattered through use cases | LOW–MEDIUM | Mechanical: define the domain exception hierarchy, find/replace, register one handler. Cheap early, annoying late |
| Ownership checks missing | MEDIUM | Change repository signatures to take `owner_id`, update every call site, add negative tests. Cheaper if the signatures were designed for it in P3 |
| Tests that assert nothing | MEDIUM | Break one business rule deliberately, see which tests stay green, rewrite those. Faster than re-reading the whole suite |
| `AI_WORKFLOW.md` reads as marketing | LOW | Delete every adjective, attach a commit hash or test name to every claim, add the "what I didn't do" section. 30 minutes, high payoff |
| Discovered post-submission that `docker compose up` fails | HIGH | There is no recovery — this is why the clean-clone rehearsal is a blocking acceptance criterion, not a nicety |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---|---|---|
| 16 · flake8/black/isort conflicts | P1 Foundation | `make lint` green on a black-formatted file; pre-commit stable on a second run |
| 4 · pytest-asyncio loop scope | P1 Foundation | Suite green with `-p no:randomly` and shuffled; no `event_loop` fixture in the tree |
| 6 · Coverage measured wrong | P1 Foundation | `source = app` set; CI fails when `--cov-fail-under=75` is not met (test by lowering a test) |
| 15 · Deprecated idioms | P1 Foundation | `filterwarnings = error::DeprecationWarning` in `pytest.ini`; zero-warning test output |
| 7 · Postgres readiness race | P1 Foundation | `docker compose down -v && docker compose up` succeeds on the first try, three times |
| 17 · Docker review failures | P1 + P7 | `whoami` ≠ root; `docker history` has no secrets; image < 500MB; `/health` returns 200 |
| 9 · Layers that are folders | P2 Domain | `ast`-based boundary test **fails** when `import fastapi` is added to a domain file |
| 10 · `HTTPException` in use cases | P2 Domain | `grep -rn HTTPException app/domain app/application` empty; 404, 409, 422 all return `application/problem+json` |
| 18 · AI-code tells (naming half) | P2 Domain | Glossary in `DECISION_LOG.md`; one name per concept across code, DB, JSON, tests |
| 1 · `MissingGreenlet` / lazy loading | P3 Persistence | All relationships `lazy="raise"`; no ORM type in any repository return annotation |
| 2 · `expire_on_commit` | P3 Persistence | `async_sessionmaker(..., expire_on_commit=False)`; a create→read-attribute test passes |
| 3 · Session lifecycle | P3 Persistence | No `.commit()` in any repository; a use case raising mid-way leaves the DB unchanged (explicit rollback test) |
| 8 · Migration race / absence | P3 Persistence | `alembic/versions/` committed and non-empty; clean volume reaches `head` |
| 5 · Test DB isolation | P1 design, P6 proof | Suite passes twice consecutively with no manual reset; dev DB untouched after a test run |
| 11 · Completion % in Python / N+1 | P4 Core API | Query count on `GET /lists` is O(1) — assert it with a SQLAlchemy `before_cursor_execute` counting fixture |
| 12 · JWT pitfalls | P5 Auth | No literal secret in the tree; `algorithms=[...]` present; expired-token test; `hashed_password` absent from every response |
| 13 · 404 vs 403 / IDOR | P5 Auth | Four cross-user negative tests, all asserting 404 |
| 18 · AI-code tells (assertions half) | P6 Test Hardening | Deliberately invert the completion-% formula → at least one test goes red |
| 14 · README fails on a clean machine | P7 Delivery | Fresh `git clone` into a new directory; every README command run verbatim, in order |
| 19 · `AI_WORKFLOW.md` as marketing | P1 log → P7 finalise | Every claim carries a commit hash / test name / file path; ≥ 3 real mistakes logged; zero superlatives |

---

## Sources

**HIGH confidence (Context7 / official docs):**
- SQLAlchemy 2.0 asyncio extension — `expire_on_commit=False`, `selectinload`, preventing implicit IO: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
- pytest-asyncio stable docs — `asyncio_mode`, `asyncio_default_fixture_loop_scope`, `loop_scope` on fixtures, migration guides from 0.21/0.23: https://pytest-asyncio.readthedocs.io/en/stable/
- FastAPI — lifespan vs. deprecated `on_event`: https://fastapi.tiangolo.com/advanced/events
- FastAPI — async tests with `httpx.AsyncClient` + `ASGITransport`: https://fastapi.tiangolo.com/advanced/async-tests
- FastAPI — OAuth2 with JWT, current tutorial using **PyJWT** and **pwdlib**, `datetime.now(timezone.utc)`, dummy-hash timing mitigation: https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt
- Pydantic v2 migration guide — `model_config`/`ConfigDict`, `from_attributes`, `model_validate`, `model_dump`, `config-both` error: https://pydantic.dev/docs/validation/latest/get-started/migration
- Black — using Black with other tools; `extend-ignore = E203, E701`, `max-line-length = 88`, isort `profile = "black"`: https://black.readthedocs.io/en/stable/guides/using_black_with_other_tools.html
- flake8 options — default ignore list `E121,E123,E126,E226,E24,E704,W503,W504`; `--ignore` replaces vs. `--extend-ignore` adds: https://flake8.pycqa.org/en/latest/user/options.html
- Python `datetime` — `utcnow()` / `utcfromtimestamp()` deprecated since 3.12: https://docs.python.org/3/library/datetime.html
- coverage.py — only `source` enables reporting un-executed files: https://coverage.readthedocs.io/en/latest/source.html
- Docker Compose — `depends_on` + `condition: service_healthy`, `healthcheck` syntax: https://docs.docker.com/reference/compose-file/services/

**MEDIUM confidence (multiple credible sources agree):**
- Postgres image `pg_isready` init-race / temporary Unix-socket server; fix with `-h 127.0.0.1`: https://github.com/docker-library/postgres/issues/1237 and corroborating fix PRs (keploy/samples-python#106, keploy/samples-go#241)
- passlib 1.7.4 (unmaintained since 2020) × bcrypt ≥ 4.1 `__about__` AttributeError: https://github.com/pyca/bcrypt/issues/684, https://github.com/pyca/bcrypt/issues/792
- Take-home reviewer behaviour — first-run failures are the dominant rejection cause; README/manifests read first: https://medium.com/bigpanda-engineering/secrets-from-the-interview-room-what-reviewers-look-for-in-a-take-home-coding-assignment-1aaec70dabe0
- Don't omit tests from coverage (counter-argument, considered and rejected for this project's ≥75% gate): https://nedbatchelder.com/blog/201908/dont_omit_tests_from_coverage
- AI disclosure in hiring — specific honest disclosure rewarded; "polished but unowned" is the 2026 red flag: https://kittygiraudel.com/2026/05/08/on-take-home-coding-assignments/, https://interviewaibox.co/en/blog/ai-take-home-assignment-guide-2026

**LOW confidence (judgement / experience, flagged as such):**
- Specific ordering of evaluator attention (the "Meta-Pitfall" section) — inferred from reviewer write-ups, not measured
- The AI-code tells catalogue in Pitfall 18 — pattern recognition, not a cited taxonomy; the prevention strategies are nonetheless directly actionable

---
*Pitfalls research for: FastAPI + async SQLAlchemy + PostgreSQL take-home deliverable with documented AI-assisted workflow*
*Researched: 2026-09-17*
