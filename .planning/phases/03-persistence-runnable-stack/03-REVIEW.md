---
phase: 03-persistence-runnable-stack
reviewed: 2026-09-19T02:08:15Z
depth: standard
files_reviewed: 57
files_reviewed_list:
  - .env.example
  - Dockerfile
  - Makefile
  - alembic.ini
  - docker-compose.yml
  - docker/entrypoint.sh
  - docker/initdb/01-create-test-database.sql
  - migrations/env.py
  - migrations/script.py.mako
  - migrations/versions/0001_baseline.py
  - src/taskmanager/__init__.py
  - src/taskmanager/domain/entities/task_list.py
  - src/taskmanager/infrastructure/clock.py
  - src/taskmanager/infrastructure/config/database_url.py
  - src/taskmanager/infrastructure/config/settings.py
  - src/taskmanager/infrastructure/db/__init__.py
  - src/taskmanager/infrastructure/db/base.py
  - src/taskmanager/infrastructure/db/constraints.py
  - src/taskmanager/infrastructure/db/engine.py
  - src/taskmanager/infrastructure/db/errors.py
  - src/taskmanager/infrastructure/db/mappers.py
  - src/taskmanager/infrastructure/db/models.py
  - src/taskmanager/infrastructure/db/repositories/__init__.py
  - src/taskmanager/infrastructure/db/repositories/task_lists.py
  - src/taskmanager/infrastructure/db/repositories/tasks.py
  - src/taskmanager/infrastructure/db/repositories/users.py
  - src/taskmanager/infrastructure/db/unit_of_work.py
  - src/taskmanager/main.py
  - src/taskmanager/presentation/api/dependencies.py
  - src/taskmanager/presentation/api/health.py
  - tests/architecture/test_no_commit_in_repositories.py
  - tests/integration/__init__.py
  - tests/integration/conftest.py
  - tests/integration/test_constraints.py
  - tests/integration/test_dependencies.py
  - tests/integration/test_health.py
  - tests/integration/test_migrations.py
  - tests/integration/test_repositories_task_lists.py
  - tests/integration/test_repositories_tasks.py
  - tests/integration/test_repositories_users.py
  - tests/integration/test_schema.py
  - tests/integration/test_unit_of_work.py
  - tests/unit/application/fakes.py
  - tests/unit/application/test_fakes.py
  - tests/unit/infrastructure/__init__.py
  - tests/unit/infrastructure/test_adapter_ports.py
  - tests/unit/infrastructure/test_clock.py
  - tests/unit/infrastructure/test_database_url.py
  - tests/unit/infrastructure/test_engine.py
  - tests/unit/infrastructure/test_errors.py
  - tests/unit/infrastructure/test_mappers.py
  - tests/unit/infrastructure/test_models.py
  - tests/unit/presentation/__init__.py
  - tests/unit/presentation/test_health.py
  - tests/unit/test_app_factory.py
  - tests/unit/test_settings.py
  - tests/unit/test_version.py
findings:
  critical: 1
  warning: 7
  info: 8
  total: 16
fixed: 6
fixed_at: 2026-09-19T02:50:29Z
fixed_findings:
  - CR-01
  - WR-01
  - WR-03
  - WR-04
  - WR-06
  - WR-07
open_findings:
  - WR-02
  - WR-05
  - IN-01
  - IN-02
  - IN-03
  - IN-04
  - IN-05
  - IN-06
  - IN-07
  - IN-08
status: issues_found
---

# Phase 3: Code Review Report

**Reviewed:** 2026-09-19T02:08:15Z
**Depth:** standard
**Files Reviewed:** 57
**Status:** issues_found -- 6 of 16 fixed on 2026-09-19

## Fix Round 1 (2026-09-19)

CR-01 and five Warnings were fixed, one atomic commit each, with
`make lint && make typecheck && make arch && make test` green before every
commit. The suite went from 287 to 293 tests and coverage stayed at 100.00%
over `src/taskmanager`.

| Finding | Commit | Kind |
|---------|--------|------|
| CR-01 | `f3747a5` | behaviour + tests |
| WR-01 | `94ccc43` | behaviour + test |
| WR-07 | `3aee2e5` | rename, no behaviour change |
| WR-03 | `c2ebc84` | query + tests |
| WR-04 | `c4594ed` | docstring only |
| WR-06 | `1e36557` | test only |

Still open, and deliberately so: **WR-02** (needs a schema change and a new
migration), **WR-05** (compose port binding, locked decision D-15) and every
Info finding.

## Summary

Phase 3 delivers the persistence layer (SQLAlchemy 2.0 async models, mappers, three
repositories, a unit of work), the Alembic baseline, the FastAPI wiring (`app.state`
container, `Depends` providers, `/health`) and the runnable Docker stack. The
architecture rules in CLAUDE.md hold across every reviewed file: the domain stays
stdlib-only, the application layer imports no ORM or web framework, no
`HTTPException` appears outside `presentation`, no repository ends a transaction, no
secret has a default in code, every SQL statement uses bound parameters, and neither
`/health` nor the entrypoint's readiness probe leaks a DSN or a driver message.

One Critical defect was found and reproduced: `get_uow` enters the unit-of-work block
before yielding it, while the port's contract and the one existing use case
(`ChangeTaskStatus.execute`) enter the block themselves. `SqlAlchemyUnitOfWork` is
not re-entrant, so the first routed use case will orphan a session and raise
`RuntimeError` in the dependency's teardown on every request. Nothing in this phase's
tests exercises that combination, which is why the suite is green.

The Warnings are about robustness and evaluator-visible accuracy: repositories that
stay bound to a closed session after the block ends, entity invariants the schema does
not back (a blank `title` in the database becomes a 422 on a GET), non-total
`ORDER BY` in two list queries, a `main.py` docstring that claims a migration race is
impossible when the entrypoint has no lock, PostgreSQL published on every host
interface with fixed credentials, and a production-guard test that checks the wrong
route prefix.

## Critical Issues

### CR-01: `get_uow` enters the unit of work, and so does the use case - the adapter is not re-entrant

**File:** `src/taskmanager/presentation/api/dependencies.py:68-69`, `src/taskmanager/infrastructure/db/unit_of_work.py:66-79`, `src/taskmanager/infrastructure/db/unit_of_work.py:101`
**Severity:** BLOCKER
**Issue:** The provider does `async with SqlAlchemyUnitOfWork(...) as unit: yield unit`, so the object a router injects is already open. The port docstring (`application/ports/unit_of_work.py`) and the only use case in the tree (`ChangeTaskStatus.execute`, line 71: `async with self._uow:`) put the `async with` in the use case. With the SQLAlchemy adapter that double entry is not harmless:

1. `__aenter__` in the dependency creates session #1 and binds the three repositories to it.
2. The use case's `async with` calls `__aenter__` again, which overwrites `self._session` with session #2 and rebinds the repositories. Session #1 is never closed.
3. The use case commits on #2 and its `__aexit__` closes #2 and sets `self._session = None`.
4. The dependency's `__aexit__` runs after the response and calls `self._open_session`, which now raises `RuntimeError("This unit of work is not open...")`. Under uvicorn that is an "Exception in ASGI application" log line per request; under `ASGITransport` (the default `raise_app_exceptions=True`) it fails every API test that routes through a use case.

Reproduced without a database (sessions never touch a connection until first use):

```
$ python reentry.py
teardown raised: This unit of work is not open. Every repository call and every commit happens inside `async with unit_of_work:` (ARC-08).
```

`test_dependencies.py` does not catch this because its probe handlers call `unit.users.get(...)` directly, never through `async with unit:` - the shape no use case will ever have. `FakeUnitOfWork.__aenter__` tolerates re-entry (it only resets a flag), so the Phase 2 unit tests hide the difference as well.

**Status:** FIXED
**fixed_in:** `f3747a5`
**Resolution:** Taken as written. `get_uow` is a plain `def` returning a closed `SqlAlchemyUnitOfWork` typed as the port, and `__aenter__` raises `RuntimeError("This unit of work is already open...")` when `_session` is not `None`. Sequential blocks on the same object stay allowed, which `tests/integration/conftest.py`'s `uow` fixture relies on. The `/_uow/*` probe handlers now open the block themselves, a third probe (`/_uow/write-and-commit`) proves the committing half of ARC-08 from a second connection, and two unit tests in `tests/unit/infrastructure/test_adapter_ports.py` pin the refusal and the reuse. Falsified: restoring the `yield` provider turns four of the five tests in `test_dependencies.py` red with the new message.

**Fix:** Pick one owner of the block and make the other side incapable of entering it. The port already says the owner is the use case, so the provider must hand over a *closed* unit of work and the adapter must refuse a second entry:

```python
# presentation/api/dependencies.py
def get_uow(request: Request) -> UnitOfWork:
    """A closed unit of work; the use case opens, commits and closes it (ARC-08)."""
    return SqlAlchemyUnitOfWork(get_session_factory(request))
```

```python
# infrastructure/db/unit_of_work.py
async def __aenter__(self) -> Self:
    if self._session is not None:
        raise RuntimeError(
            "This unit of work is already open; a block cannot be entered twice."
        )
    self._session = self._session_factory()
    ...
```

Then change the two probe handlers in `tests/integration/test_dependencies.py` to `async with unit:` around their repository calls (which is also what makes `test_the_dependency_does_not_commit_on_teardown` prove the property for the real call shape), and add a unit test that asserts re-entry raises. If the dependency is instead kept as the owner, `ChangeTaskStatus` and every Phase 4 use case must drop their `async with`, and the port docstring must be rewritten - but that moves the boundary into the web framework, which the port docstring explicitly rejects.

## Warnings

### WR-01: Repositories stay bound to a closed session after `__aexit__`, and are unset before `__aenter__`

**File:** `src/taskmanager/infrastructure/db/unit_of_work.py:74-78`, `src/taskmanager/infrastructure/db/unit_of_work.py:101-108`
**Issue:** `tasks`, `task_lists` and `users` are created in `__aenter__` and never cleared. After `__aexit__`, `self._session` is `None` (so `commit()` gets the friendly guard) but `uow.tasks._session` still points at the closed `AsyncSession`. SQLAlchemy sessions are reusable after `close()`, so `await uow.tasks.get(...)` outside the block silently autobegins a fresh transaction on a new pooled connection that nothing will ever roll back or close - the exact "dirty session handed back to the pool" the port docstring forbids. Before `__aenter__`, the same attributes do not exist at all, so `uow.tasks` is an `AttributeError` about a missing attribute instead of the sentence `_open_session` was written to provide.
**Status:** FIXED
**fixed_in:** `94ccc43`
**Resolution:** Fixed by the second of the two suggested shapes rather than the first. The three names are now bare class-level annotations, assigned in `__aenter__` and deleted in `__aexit__`'s `finally`, so a repository call outside the block raises `AttributeError` immediately instead of autobeginning a transaction on a pooled connection nobody will close. The read-only `property` was rejected because `UnitOfWork` declares the three as *mutable* members and mypy checks those invariantly - a property would stop `SqlAlchemyUnitOfWork` from satisfying the port and break `tests/unit/infrastructure/test_adapter_ports.py`. A `__getattr__` carrying the friendlier `_open_session` sentence was rejected too: mypy resolves every unknown attribute through `__getattr__` once it exists, which would turn a typo on the object every use case holds into a runtime error instead of a type error. `tests/integration/test_unit_of_work.py::test_the_repositories_are_unreachable_outside_the_block` asserts both sides of the block.

**Fix:** Make the repositories go through the same guard as `commit()`:

```python
@property
def tasks(self) -> TaskRepository:
    return SqlAlchemyTaskRepository(self._open_session)
```

(or keep them as attributes but set them in `__init__` to a sentinel that raises, and reset them in `__aexit__`'s `finally`). Note the port declares the three as attributes; a read-only property still satisfies the Protocol for reads, which is the only access a use case performs. Add an integration test that calls a repository after the block and expects `RuntimeError`.

### WR-02: Entity invariants the schema does not enforce turn a corrupt row into a 422 on a GET

**File:** `src/taskmanager/infrastructure/db/mappers.py:89-97`, `src/taskmanager/infrastructure/db/mappers.py:130-137`, `src/taskmanager/infrastructure/db/mappers.py:170-185`, `migrations/versions/0001_baseline.py:48-137`
**Issue:** The mapper docstring states the WR-05 principle - a value that violates the schema's promise is an infrastructure fault and must become the fixed 500, never a validation error naming a field the caller did not send - but implements it for datetimes only. `to_entity` calls the entity constructor, and `__post_init__` runs `require_text` on `title`, `name`, `email` and `password_hash`. `VARCHAR` accepts `''` and whitespace-only strings, and the baseline has no `CHECK (btrim(title) <> '')`. A row written by a seed script, a raw `UPDATE`, or a future bulk operation with a blank title makes `SqlAlchemyTaskRepository.get()` raise `ValidationError("title must not be blank.", details={"field": "title"})`, which Phase 2's handler renders as a 422 telling the client their request had a bad `title`. The completed/`completed_at` pair is protected (CK), the enums are protected (CK), the timestamps are protected (`_aware`); the text columns are not.
**Status:** OPEN -- deferred. The stronger of the two fixes needs three `CHECK` constraints, matching `CheckConstraint`s in `models.py`, new names in `constraints.py` and a new Alembic revision, which is a schema change rather than a code fix and belongs to a planned migration rather than to a review-fix pass.
**Fix:** Either back the invariants in the schema so the mapper cannot see the bad row -

```python
sa.CheckConstraint("btrim(title) <> ''", name=op.f("ck_tasks_title_not_blank")),
sa.CheckConstraint("btrim(name) <> ''", name=op.f("ck_task_lists_name_not_blank")),
sa.CheckConstraint("btrim(email) <> ''", name=op.f("ck_users_email_not_blank")),
```

(and the matching `CheckConstraint`s in `models.py` plus constants in `constraints.py` so `test_the_naming_convention_produces_every_d12_constraint_name` stays honest) - or wrap the entity construction in each `*_to_entity` with `except ValidationError as error: raise CorruptRowError(...) from error` where `CorruptRowError` is a `RuntimeError` sibling of `NaiveDatetimeFromDatabaseError`. The first is stronger; the second is smaller.

### WR-03: `list_for_owner` and `list_all` order by `created_at` alone, which is not a total order

**File:** `src/taskmanager/infrastructure/db/repositories/task_lists.py:128-132`, `src/taskmanager/infrastructure/db/repositories/users.py:84`
**Issue:** `SqlAlchemyTaskRepository.list_for_task_list` orders by `(created_at, id)` and its docstring explains why `created_at` alone makes a first-element assertion flaky. The two sibling list queries do not apply the same rule. A use case that creates two lists in one request reads the clock once (D-13), so both rows share an instant and PostgreSQL may return them either way round on different runs. `test_list_for_owner_returns_only_that_owners_lists_in_creation_order` passes only because its two rows are one day apart.
**Status:** FIXED
**fixed_in:** `c2ebc84`
**Resolution:** Taken as written: both queries now order by `(created_at, id)`, matching `list_for_task_list`. Each gained a test that seeds a same-instant group. The task-list one needed a second attempt and the detail is worth keeping: with names that sorted the same way the identifiers do, PostgreSQL answered from `uq_task_lists_owner_id_name` and the test passed against the *unfixed* query. It now uses names whose alphabetical order matches neither the insertion order nor the expected order, and both tests are confirmed red with the tie-break removed.
**Fix:**

```python
.order_by(TaskListRow.created_at, TaskListRow.id)
...
select(UserRow).order_by(UserRow.created_at, UserRow.id)
```

and give each integration test a same-instant pair, as `given_a_mixed_list` already does for tasks.

### WR-04: `main.py` claims replicas cannot race the migration; the entrypoint takes no lock

**File:** `src/taskmanager/main.py:15-16`, `docker/entrypoint.sh:91`
**Issue:** The docstring says moving `alembic upgrade head` out of the application means "several replicas started at the same moment cannot race each other through the same migration". Moving the call to the entrypoint does not remove the race - every replica's entrypoint runs `alembic upgrade head` concurrently against the same database, and Alembic takes no advisory lock by default. Two concurrent `CREATE TABLE users` on an empty database is a real failure (`duplicate key value violates unique constraint "pg_type_typname_nsp_index"` or a plain "relation already exists"). The compose file runs one replica, so nothing breaks today, but the sentence is the kind an evaluator reads and checks.
**Status:** FIXED
**fixed_in:** `c4594ed`
**Resolution:** The first of the two options: the docstring now states what is true. It says the entrypoint runs `alembic upgrade head` once per container start, that this buys the no-database-at-import property and nothing more, that Alembic's version-table transaction is the only thing between two concurrent replicas and is the database resolving a race rather than the project preventing one, and that a multi-replica deployment must serialise the upgrade itself. The advisory lock in `migrations/env.py` was not added: migrations are out of scope for this pass, and one replica is the deployment the compose file describes.
**Fix:** Either correct the docstring to "one replica, one migration run, by construction of the compose file; a multi-replica deployment must serialise `upgrade head` (advisory lock or a one-shot migration job)", or make the claim true by wrapping the upgrade in `pg_advisory_lock` inside `migrations/env.py`'s `run_migrations_online`:

```python
with engine.connect() as open_connection:
    open_connection.execute(text("SELECT pg_advisory_lock(:key)"), {"key": 0x7A5B_0001})
    _run_migrations(open_connection)
```

### WR-05: PostgreSQL is published on every host interface with fixed credentials

**File:** `docker-compose.yml:42`
**Issue:** `"5432:5432"` binds to `0.0.0.0` on the host. The database authenticates as `taskmanager:taskmanager` and `postgres:18-alpine` defaults `POSTGRES_HOST_AUTH_METHOD` to password auth for all addresses, so on a laptop attached to a shared network (or a CI runner with a public interface) the evaluator's `docker compose up` exposes a writable database with a guessable password to the LAN. The reason for publishing (host-side `make test` against the same container) only needs loopback.
**Status:** OPEN -- not accepted. The compose port binding is locked by decision D-15 and was left untouched deliberately; changing it is a decision to revisit, not a defect to patch in a fix pass.
**Fix:**

```yaml
ports:
  - "127.0.0.1:5432:5432"
```

`.env.example` already dials `localhost`, so nothing else changes.

### WR-06: The production-app guard checks a prefix the new probe router does not use

**File:** `tests/unit/test_app_factory.py:66-68`, `tests/integration/test_dependencies.py:59-98`
**Issue:** `test_production_app_has_no_probe_routes` asserts that no route path starts with `/_probe`. The router this phase adds for `get_uow` mounts `/_uow/report` and `/_uow/write-without-finishing`. If someone moved `app.include_router(uow_probe_router)` into `create_app` by mistake - the exact regression the test exists to catch - it would stay green. The guard is only as wide as the prefixes it knows.
**Status:** FIXED
**fixed_in:** `1e36557`
**Resolution:** Fixed, and the finding understated the problem. The guard was not merely too narrow: FastAPI wraps an included router in a single opaque object carrying no `path` attribute, so `getattr(route, "path", "")` answered `""` for precisely the routes the test existed to find - including `/_probe/*`. Including *either* probe router in `create_app` would have left it green, so the prefix tuple suggested here would not have worked either. The test now asks the production application to route every endpoint both probe routers declare (derived from the routers, under the declared method so a 405 cannot stand in for a 404) and expects 404, plus an assertion that the derived list is non-empty. Confirmed red by including `uow_probe_router` in `create_app`. The `include_in_schema=True` variant was rejected: FastAPI's own `/docs`, `/redoc` and `/openapi.json` routes are declared `include_in_schema=False`.
**Fix:** Assert on the intent rather than one literal:

```python
PROBE_PREFIXES = ("/_probe", "/_uow")
assert not any(
    getattr(route, "path", "").startswith(PROBE_PREFIXES) for route in app.routes
)
```

and better, assert that every route in the production app has `include_in_schema=True`, since both probe routers are declared `include_in_schema=False`.

### WR-07: `rollback()` records itself as `_committed`

**File:** `src/taskmanager/infrastructure/db/unit_of_work.py:47`, `src/taskmanager/infrastructure/db/unit_of_work.py:115-122`
**Issue:** The flag `_committed` is set to `True` by both `commit()` and `rollback()`. The behaviour is correct (both finish the transaction, so `__aexit__` must not roll back again), but the name states something false after a rollback, and the next person adding a feature that genuinely needs "was this block committed" (an outbox flush, an audit line, a metric) will read the flag and get a wrong answer. `FakeUnitOfWork` already uses the accurate name, `_finished`.
**Status:** FIXED
**fixed_in:** `3aee2e5`
**Resolution:** Taken as written. The flag is `_finished`, the comment in `rollback()` now says it is named for the transaction being finished rather than for how it ended, and `__init__` carries the reasoning. Behaviour is unchanged and the 293-test suite confirms it.

**Fix:** Rename to `_finished`, mirroring the fake, and update the comment at line 118-122 which already describes it as "the transaction is finished".

## Info

### IN-01: `docker run <image> --port 9000` does not "still work" as the Dockerfile and entrypoint claim

**File:** `Dockerfile:84-90`, `Dockerfile:102-103`, `docker/entrypoint.sh:98-103`
**Issue:** Replacing `CMD` replaces the whole argument list, so `--port 9000` also drops `--host 0.0.0.0`; uvicorn then binds `127.0.0.1` and is unreachable from outside the container. The `HEALTHCHECK` also hardcodes `127.0.0.1:8000`, so the container would go `unhealthy` on any other port. Both comments overstate what the override buys.
**Fix:** Either fix `--host 0.0.0.0` in the `exec uvicorn` line and keep only `--port 8000` in `CMD`, or soften the comment to "extra uvicorn flags can be appended".

### IN-02: The readiness loop retries permanent failures for 30 s and then blames the database service

**File:** `docker/entrypoint.sh:60-83`
**Issue:** `except Exception` treats a wrong password, a wrong database name (`FATAL: database "x" does not exist`) and a refused TCP connection identically. The final message says "check that the database service is running", which is wrong for the first two, and the per-attempt line prints only `OperationalError` for all three. An evaluator with a typo in `.env` waits 30 s and is pointed at the wrong thing.
**Fix:** Distinguish `psycopg.OperationalError` whose `sqlstate` starts with `28` (auth) or `3D` (invalid catalog name) and exit immediately with "the database refused the credentials/name in DATABASE_URL" - still without echoing the URL.

### IN-03: The `.env.example` JWT placeholder passes validation, so the evaluator's stack signs tokens with a public secret

**File:** `.env.example:39-42`, `src/taskmanager/infrastructure/config/settings.py:41`
**Issue:** `replace-me-with-a-generated-secret` is 34 characters, so `cp .env.example .env && docker compose up` - the documented first step - boots with a secret that is committed to the repository. The CLAUDE.md rule is about code defaults and is respected; this is the same outcome reached through the example file. It is acceptable for a take-home if the README says so explicitly.
**Fix:** Either have the README's step one generate the value (`sed`/`python -c` one-liner), or add a `field_validator` on `jwt_secret` that rejects the literal placeholder string so the first boot fails with a sentence.

### IN-04: `jwt_algorithm` is an unconstrained `str`

**File:** `src/taskmanager/infrastructure/config/settings.py:42`
**Issue:** Nothing stops `JWT_ALGORITHM=none` or an RS256 value with an HS256 secret from reaching PyJWT in Phase 5. PyJWT refuses `none` unless asked, but the setting should not be able to express it at all.
**Fix:** `jwt_algorithm: Literal["HS256", "HS384", "HS512"] = "HS256"`.

### IN-05: Bulk `delete()` leaves cascaded child rows stale in the identity map

**File:** `src/taskmanager/infrastructure/db/repositories/task_lists.py:113-116`
**Issue:** `delete(TaskListRow).where(...)` with `synchronize_session="auto"` evicts the list row, but any `TaskRow` objects already loaded in the same session (from an earlier `tasks.get()` in the same use case) are not evicted even though PostgreSQL's `ON DELETE CASCADE` has removed them. A later `session.get(TaskRow, id)` in the same block returns the stale object from the identity map without a query, so the repository would hand back an entity for a row that no longer exists. No current use case does this in one block; a Phase 4 "delete list" that first lists its tasks would.
**Fix:** After the delete, `self._session.expire_all()` is the blunt instrument; the targeted one is `await self._session.execute(delete(TaskRow).where(TaskRow.task_list_id == task_list_id))` before deleting the list, letting synchronize_session evict the children too.

### IN-06: `apply_task_list_to_row` silently ignores a changed `owner_id`

**File:** `src/taskmanager/infrastructure/db/mappers.py:140-148`
**Issue:** The comment says no use case transfers a list, so `owner_id` is not written. That makes `update()` a silent partial write if a future use case ever does set it: the entity says one owner, the row keeps another, and no error is raised. A silent drop is worse than either writing it or refusing it.
**Fix:** Raise if `row.owner_id != task_list.owner_id` (`RuntimeError("task_lists.owner_id is immutable")`), so the day a transfer is attempted it fails at the mapper rather than persisting nothing.

### IN-07: `get_by_email` folds case in Python on one side and in PostgreSQL on the other

**File:** `src/taskmanager/infrastructure/db/repositories/users.py:60-62`, `src/taskmanager/domain/entities/user.py:46-48`
**Issue:** `User` canonicalises with Python `str.lower()`; the index and the lookup use PostgreSQL `lower()` under the cluster's collation. For ASCII the two agree. For a handful of Unicode code points (dotted capital I, final sigma, characters whose lowercase is longer than one code unit) they can differ, so an address that Python folds to X and PostgreSQL folds to Y could register twice or fail to be found. `EmailStr` at the HTTP boundary narrows this considerably but does not forbid non-ASCII local parts.
**Fix:** Acceptable to leave as-is for this scope; document the assumption next to the index, or use `lower(email COLLATE "C")` in the index and the query so both sides fold only ASCII.

### IN-08: Docstring typo in `TaskList.rename`

**File:** `src/taskmanager/domain/entities/task_list.py:90`
**Issue:** "Replace the name, applying the same guard construction applied." reads as a half-edited sentence in a codebase whose docstrings are otherwise carefully written and will be read by the evaluator.
**Fix:** "Replace the name, applying the same guard that construction applies."

## Info findings: all open

None of IN-01 through IN-08 was touched. This pass was scoped to CR-01 and five
of the seven Warnings.

---

_Reviewed: 2026-09-19T02:08:15Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
_Fix round 1: 2026-09-19T02:50:29Z, 6 of 16 findings fixed_
