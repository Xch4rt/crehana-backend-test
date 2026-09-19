---
phase: 03-persistence-runnable-stack
plan: 08
subsystem: infrastructure
tags: [unit-of-work, transactions, engine, session-factory, arc-08, wr-06, d-01, sc-4, sc-5, port-conformance]

# Dependency graph
requires:
  - phase: 02-domain-error-contract
    provides: the UnitOfWork Protocol with its normative __aexit__ docstring, FakeUnitOfWork as the behavioural model, and the WR-06 rollback rule
  - phase: 03-persistence-runnable-stack
    plan: 03
    provides: Settings and the resolved DSN the engine builder reads
  - phase: 03-persistence-runnable-stack
    plan: 05
    provides: the connection/session_factory fixtures and join_transaction_mode="create_savepoint", without which a commit inside a test is a silent no-op
  - phase: 03-persistence-runnable-stack
    plan: 07
    provides: the third and last repository adapter, so all three can be constructed behind one unit of work
provides:
  - src/taskmanager/infrastructure/db/engine.py - create_engine / create_session_factory / create_database_resources, and DatabaseResources as the one typed object 03-09 puts on app.state
  - src/taskmanager/infrastructure/db/unit_of_work.py - SqlAlchemyUnitOfWork, the transaction boundary ARC-08 names
  - tests/integration/conftest.py::uow - the fixture every Phase 4 integration test will take
  - tests/unit/infrastructure/test_adapter_ports.py - the infrastructure half of the ARC-04 conformance proof
  - The empirical settlement of two claims: building an engine opens no connection, and a commit inside the test transaction really commits
affects: [03-09, 03-10, 03-11, 04-crud-endpoints, 05-auth]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A module that the composition root calls exports builders, never an instance: an instance would read Settings at import time and break mypy, import-linter and `docker build` alike"
    - "A transaction proof asserts a read, not a counter: `commits == 1` says the method was called, while reading the row back after `__aexit__` says the rollback correctly did not fire"
    - "A test suite whose reads all share one connection needs exactly one test that reads from a second one, or the whole suite can pass with the commit silently disabled"
    - "A constructor parameter typed as the widest callable it needs (`Callable[[], AsyncSession]`) is what removes a `cast` from the one fixture the isolation proof lives in"

key-files:
  created:
    - src/taskmanager/infrastructure/db/engine.py
    - src/taskmanager/infrastructure/db/unit_of_work.py
    - tests/unit/infrastructure/test_engine.py
    - tests/unit/infrastructure/test_adapter_ports.py
    - tests/integration/test_unit_of_work.py
    - .planning/phases/03-persistence-runnable-stack/evidence/03-08-commit-falsification.txt
  modified:
    - tests/integration/conftest.py

key-decisions:
  - "SqlAlchemyUnitOfWork keeps `_session: AsyncSession | None` and reads it through an `_open_session` property that raises a sentence. RESEARCH Pattern 3 creates the attribute in `__aenter__` only, which makes a commit outside the block an AttributeError naming a private field. Added beyond the plan's letter, with its own unit test so the branch is covered"
  - "The pre-ping assertion reads the pool's private `_pre_ping`, because SQLAlchemy 2.0.54 exposes no public reader. Confirmed by introspecting a built engine rather than guessed, as the plan required"
  - "`engine.pool` is narrowed to QueuePool before `checkedout()`: `AsyncEngine.pool` is annotated with the `Pool` base, which has no such method, and the isinstance also asserts that an async engine really gets a queue pool"
  - "The immutability test uses `setattr` with a field name held in a constant, following the frozen-dataclass convention of tests/unit/application/: a direct assignment needs a `type: ignore`, and this project has none"
  - "The Clock port's adapter conformance stays in tests/unit/infrastructure/test_clock.py and is NOT repeated in test_adapter_ports.py; the new module says so in its docstring"
  - "No requirement tick taken: 03-11 is the last claimant of DB-01 and ARC-08. Eighth consecutive plan in this phase to make the same call"

patterns-established:
  - "tests/integration/conftest.py now owns the whole stack a Phase 4 test needs: migrated schema, outer transaction, savepoint-joining session factory, and the unit of work over it. Plan 03-09 adds a FastAPI dependency and no fixture"

requirements-completed: []

# Metrics
duration: 13min
completed: 2026-09-18
---

# Phase 3 Plan 08: The Transaction Boundary Summary

**ARC-08 stopped being an intention: `SqlAlchemyUnitOfWork` opens one session per block, commits only when the use case says so, and rolls back on every exit path that did not — proven against real PostgreSQL by six tests that assert rows rather than counters, including the D-01 proof that a write committed inside a test is invisible to a second, independent connection. The engine and session factory it runs on are built by functions, never instantiated at import, and a unit test shows that building them touches no network at all.**

## Performance

- **Duration:** 13 min
- **Started:** 2026-09-18T23:59Z
- **Completed:** 2026-09-19T00:12Z
- **Tasks:** 3
- **Files modified:** 6 created, 1 modified

## Accomplishments

- **The STACK-versus-ARCHITECTURE contradiction is resolved in code and in prose.** `engine.py` exports `create_engine`, `create_session_factory` and `create_database_resources` and instantiates nothing; an AST assertion in the acceptance criteria proves there is not a single module-level assignment in the file. The docstring states the reason concretely rather than citing Anti-Pattern 10: a module-level engine would read `Settings` at import, so `import taskmanager.infrastructure.db.engine` would raise everywhere `DATABASE_URL` is absent — mypy's environment, import-linter's, and a plain `docker build` — which is the same argument `main.py` already makes for the app object.
- **The three mandatory options are each in exactly one place, and each is asserted.** `pool_pre_ping=True` on the engine, `expire_on_commit=False` and `autoflush=False` on the factory, all three appearing once in the module and named in prose everywhere else so the plan's grep gate stays a real gate. `test_the_session_factory_does_not_expire_on_commit` reads them off `async_sessionmaker.kw` — the values `AsyncSession` will actually be constructed with, not the source text.
- **"Building an engine opens no connection" is now a test, not an assumption.** Every unit test in `test_engine.py` builds from `postgresql+psycopg://user:pass@127.0.0.1:1/nothing`, where nothing listens, and asserts the pool has zero connections checked out and zero checked in. That is the exact property `tests/conftest.py` and `tests/unit/test_app_factory.py` have been depending on silently since Phase 1; both still pass with no database running.
- **`DatabaseResources` exists to buy 03-09 one cast instead of many.** `starlette.datastructures.State.__getattr__` returns `Any`, which mypy strict treats as an implicit-`Any` source, so each read of `app.state.engine` would otherwise need its own `cast`. One frozen, slotted container means the dependency module casts once and everything downstream is typed by the dataclass.
- **`SqlAlchemyUnitOfWork` implements WR-06 literally, and the docstrings say which sentence of the port each line answers.** `__aexit__` rolls back when nothing committed, closes the session in a `finally`, and returns `None` explicitly — with the comment that a true return would swallow the exception that left the block and let a failed use case answer 200. `rollback()` sets `_committed = True` for `FakeUnitOfWork._finished`'s reason: a second rollback on a finished transaction is not harmless, it begins and ends a fresh one.
- **The port annotations are load-bearing, and that was verified by breaking them.** Changing `self.tasks: TaskRepository` to `self.tasks: SqlAlchemyTaskRepository` makes mypy report `Following member(s) of "SqlAlchemyUnitOfWork" have conflicts: tasks: expected "TaskRepository", got "SqlAlchemyTaskRepository"` at the conformance test's binding — observed, then reverted. mypy checks a mutable Protocol member invariantly, exactly as Phase 2's `FakeUnitOfWork` docstring recorded, and the test docstring now carries the observed error text.
- **Four conformance tests make the static proof countable.** `test_adapter_ports.py` binds each of the three adapters and the unit of work to a local annotated with its port, copying the docstring and binding pattern of `tests/unit/application/test_ports.py`. The adapters are constructed from a session over the unreachable engine, so no connection is opened and these stay unit tests.
- **Six transaction proofs against PostgreSQL, and every one of them asserts a row.** A committed block's write survives `__aexit__`; a `DomainError` both escapes the `async with` *and* leaves nothing behind; a block that never committed is undone; an explicit `rollback()` inside the block is not repeated on exit; two different repositories in one block commit together and are undone together. The plan's wording was `commits == 1`; reading the row back through a second block is the stronger claim, because a counter cannot distinguish a correct `__aexit__` from one that rolled back what had just been committed.
- **The D-01 isolation proof is real, and it is also this suite's own safety net.** `test_a_committed_write_is_invisible_outside_the_test_transaction` commits through the unit of work, reads the row back inside the fixture's transaction, then opens a separate engine and connection to the same DSN and asserts `SELECT count(*) FROM users WHERE id = :id` returns 0, disposing that engine afterwards. Every other read in the module shares the fixture's connection, so this is the only vantage point from which a `join_transaction_mode` degraded to `rollback_only` (RESEARCH Pitfall 1) would be visible.
- **The falsification is on disk.** With `await uow.commit()` commented out, `test_a_successful_block_commits_once` fails on `assert False` at the read-back; with the line restored and nothing else changed, all six pass. Both runs are captured in `evidence/03-08-commit-falsification.txt` with a header explaining what a green run would have meant had the test stayed green.
- **All four gates green before all three commits.** `make lint && make typecheck && make arch && make test`: 92 files black/isort clean, flake8 clean, mypy strict clean over 92 source files with no `type: ignore` anywhere in the project, three import-linter contracts KEPT, **272 passed** under `filterwarnings = error`. **Coverage over `src/taskmanager` is back to 100.00%** — 671 statements, 0 missed, 72 branches, 0 partial — gate still at 75, no `pragma`, no `omit`. `make test` twice in a row reports 272 both times and `SELECT count(*) FROM users` on the test database prints `0` afterwards.

## Task Commits

Each task was committed atomically:

1. **Task 1: the engine and session-factory builders** — `ea902c7` (feat)
2. **Task 2: SqlAlchemyUnitOfWork and the adapter port-conformance suite** — `90e43d2` (feat)
3. **Task 3: the uow fixture and the six transaction proofs** — `f2eaaf4` (test)

**Plan metadata:** see the `docs(03-08)` commit that carries this SUMMARY.

## Files Created/Modified

- `src/taskmanager/infrastructure/db/engine.py` (97 lines) — three builders and `DatabaseResources`. The module docstring resolves the STACK/ARCHITECTURE contradiction once, with the concrete consequence rather than the rule number
- `src/taskmanager/infrastructure/db/unit_of_work.py` (122 lines) — the adapter. The docstring records why the constructor takes the widest callable, and every method says which obligation of the port it discharges
- `tests/unit/infrastructure/test_engine.py` (119 lines) — 5 tests, all against an unreachable DSN
- `tests/unit/infrastructure/test_adapter_ports.py` (105 lines) — 5 tests: four conformance bindings plus the use-outside-a-block refusal
- `tests/integration/test_unit_of_work.py` (231 lines) — 6 proofs, two entity builders, a `rows_in_users` read-back helper and the second-connection reader
- `tests/integration/conftest.py` (+21/−3) — the `uow` fixture, and the `session` fixture's docstring no longer promises a fixture that now exists
- `.planning/phases/03-persistence-runnable-stack/evidence/03-08-commit-falsification.txt` (52 lines) — the red/green pair

## Decisions Made

- **The unit of work holds `_session: AsyncSession | None` and reads it through a property that raises a sentence.** RESEARCH Pattern 3 assigns `self._session` in `__aenter__` and nowhere else, which type-checks but makes `await uow.commit()` outside a block an `AttributeError` naming a private attribute — a message that says nothing about the rule the caller broke. `_open_session` raises `RuntimeError("This unit of work is not open. Every repository call and every commit happens inside `async with unit_of_work:` (ARC-08).")` instead. The branch is covered by its own unit test, so the addition costs no coverage and the error path is exercised rather than merely written. `__aexit__` also sets `_session = None` afterwards, so a block is a real lifecycle rather than an attribute that lingers.
- **The pre-ping assertion reads a private attribute, deliberately.** SQLAlchemy 2.0.54's `Pool` records the setting as `_pre_ping` and exposes no public reader — confirmed by introspecting a built engine, which is what the plan asked for instead of guessing an attribute name. Asserting on a private name is worth more than the alternative, which is a constructor argument no test would notice the removal of. If SQLAlchemy renames it, this test fails loudly in a place that explains itself.
- **`engine.pool` is narrowed to `QueuePool` before `checkedout()` is called.** `AsyncEngine.pool` is annotated with the `Pool` base class, which has no such method, so mypy strict rejects the plan's literal assertion. The `isinstance` that fixes it is not ceremony: it also asserts that an async engine really gets a queue pool, which is what makes "zero connections checked out" a meaningful statement rather than a property of a pool type that could never hold one.
- **The frozen-resources test uses `setattr` with the field name in a constant.** A direct `resources.engine = ...` is a mypy error that must be silenced with `type: ignore[misc]`, and this repository has none — the frozen-dataclass tests in `tests/unit/application/` and `tests/unit/domain/` established the `setattr` convention for exactly this reason. Following it kept the project's `type: ignore` count at zero.
- **`test_the_sqlalchemy_task_list_repository_satisfies_its_port` is shortened from the plan's suggested name.** The literal name in the plan is 79 characters, which makes the `def` line 94 — nine over the limit black cannot rewrap and flake8 rejects. The other three conformance names are used verbatim, as are all four names VALIDATION.md records for the integration suite, which are the ones the traceability table matches on.
- **The `Clock` conformance test is not duplicated.** `tests/unit/infrastructure/test_clock.py::test_system_clock_satisfies_the_clock_port` already owns it (plan 03-03). The plan permitted either; asserting it twice would mean a future change to the port produces two identical failures in two files, which reads as two problems. `test_adapter_ports.py`'s docstring names the owning file.
- **The commit tests assert reads, not counters.** The plan's own wording notes the distinction and this summary records why it matters: `commits == 1` is true of a unit of work whose `__aexit__` rolled back immediately afterwards, and that is precisely the failure WR-06 exists to prevent. Every assertion in `test_unit_of_work.py` is therefore a row that is or is not there.
- **No requirement tick taken.** The plan's frontmatter lists `DB-01` and `ARC-08`; `03-11-PLAN.md` claims both again. Under the last-claimant convention, 03-11 owns the tick. Eighth consecutive plan in this phase to make the same call.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 — Missing safeguard] using the unit of work outside a block was an `AttributeError`**

- **Found during:** Task 2
- **Issue:** RESEARCH Pattern 3 creates `self._session` in `__aenter__` only. `await uow.commit()` on an unopened unit of work therefore raises `AttributeError: 'SqlAlchemyUnitOfWork' object has no attribute '_session'` — a message about a private field, in a class whose entire contract is "the boundary is the `async with`". Phase 4 will have a `Depends` handing these out, and a router that forgot the block is a plausible mistake worth naming.
- **Fix:** `_session` is declared `AsyncSession | None` in `__init__` and read through an `_open_session` property that raises `RuntimeError` with the rule stated. Covered by `test_using_a_unit_of_work_outside_a_block_says_so`, so the new branch is exercised and coverage stayed at 100%.
- **Files modified:** `src/taskmanager/infrastructure/db/unit_of_work.py`, `tests/unit/infrastructure/test_adapter_ports.py`
- **Commit:** `90e43d2`

**2. [Rule 3 — Blocking] `Pool` has no `checkedout()` under mypy strict**

- **Found during:** Task 1
- **Issue:** The plan's assertion `resources.engine.pool.checkedout() == 0` fails `make typecheck` with `"Pool" has no attribute "checkedout"`: `AsyncEngine.pool` is annotated with the base class, and the method lives on `QueuePool`.
- **Fix:** Narrow with `isinstance(pool, QueuePool)` first, then assert both `checkedout()` and `checkedin()` are zero. The comment records that the narrowing doubles as a claim about which pool an async engine gets.
- **Files modified:** `tests/unit/infrastructure/test_engine.py`
- **Commit:** `ea902c7`

**3. [Rule 3 — Blocking] `AsyncConnection.scalar` returns `Any`**

- **Found during:** Task 3
- **Issue:** The second-connection helper returned the result of `connection.scalar(...)` directly, and mypy strict rejects it as `Returning Any from function declared to return "int | None"`.
- **Fix:** The value is assigned, narrowed with `assert isinstance(count, int)` and returned as `int`. The docstring notes the narrowing is worth having anyway — an aggregate arriving as something other than an `int` would compare unequal to zero and turn the D-01 proof into a silent pass.
- **Files modified:** `tests/integration/test_unit_of_work.py`
- **Commit:** `f2eaaf4`

**4. [Rule 3 — Blocking] `pool_pre_ping=True` appeared twice, failing its own acceptance criterion**

- **Found during:** Task 1
- **Issue:** The first docstring named the option literally as well as passing it, so `grep -c` printed `2` against a required `1`.
- **Fix:** The docstring now describes the option in prose and says it is named once in the call — the project's prose-not-literal convention, applied for the eighth or ninth time in this phase.
- **Files modified:** `src/taskmanager/infrastructure/db/engine.py`
- **Commit:** `ea902c7`

### Deviations from the plan's letter

**5. One conformance test name is shortened; the four VALIDATION.md names are verbatim**

- **Found during:** Task 2
- **Reason:** `test_the_sqlalchemy_task_list_repository_satisfies_the_task_list_repository_port` produces a 94-character `def` line. Black cannot rewrap a function name and flake8 rejects it, so the name became `test_the_sqlalchemy_task_list_repository_satisfies_its_port`. No traceability entry references it; the four integration test names VALIDATION.md does record are used exactly as written, and `grep -c` for them prints `4`.
- **Files modified:** `tests/unit/infrastructure/test_adapter_ports.py`
- **Commit:** `90e43d2`

**6. A sixth integration test, and a fifth unit test in each new unit module**

- **Found during:** Tasks 1–3
- **Reason:** The plan's own action text lists six integration tests while its acceptance criterion floors at six — both are met. Beyond the plan: `test_create_database_resources_binds_the_factory_to_the_same_engine` pins that the composer builds one engine and one factory over it rather than two independent pools, which is the failure `DatabaseResources` exists to make impossible; and `test_using_a_unit_of_work_outside_a_block_says_so` covers the safeguard added under deviation 1.
- **Files modified:** `tests/unit/infrastructure/test_engine.py`, `tests/unit/infrastructure/test_adapter_ports.py`
- **Commit:** `ea902c7`, `90e43d2`

Everything else executed as written. Every acceptance criterion passed: the engine suite reports 5 tests against a floor of 4 and the conformance suite 5 against 4; `grep -c` prints `1` for each of `expire_on_commit=False`, `autoflush=False` and `pool_pre_ping=True`, and `1` for each of the three port annotations; the AST check for module-level assignments exits 0; `tests/unit/test_app_factory.py` and `tests/api/` pass with no database; `Callable[[], AsyncSession]` appears twice against a floor of 1; `grep -rn "type: ignore\|cast("` prints nothing for the unit of work; the four VALIDATION.md test names grep to `4`; the integration suite reports 6 against a floor of 6; the evidence file shows the red and the green run; `SELECT count(*) FROM users` prints `0` after the suite; and `make test` twice in a row reports 272 both times with `Required test coverage of 75% reached. Total coverage: 100.00%`.

## Issues Encountered

- **The trailing-whitespace pre-commit hook rewrote the evidence file on the first attempt at the Task 3 commit**, because captured pytest output carries trailing spaces on its blank source-context lines. The hook fixed it, the commit aborted, and re-staging the fixed file committed cleanly. Worth knowing for any future plan that commits captured terminal output: stage, expect one abort, re-stage.
- **No `.env` exists in this repository by design**, so `DATABASE_URL`, `TEST_DATABASE_URL` and `JWT_SECRET` were exported in the shell for every test run, exactly as in 03-05 through 03-07. `pre-commit` runs no pytest, so the commits themselves needed no database.
- Nothing else. `filterwarnings = error` raised nothing new: constructing an `AsyncSession` in a synchronous unit test over an engine that never connects produces no `SAWarning`, and neither does disposing the second engine in the isolation proof.

## Known Stubs

None. Both new source modules are complete and every public function and method in them is driven by at least one test. `DatabaseResources` is constructed but not yet *stored* anywhere — that is plan 03-09's task, and it is a finished typed value rather than a placeholder, which is why its own unit test asserts what 03-09 will rely on (one engine, one factory bound to it, neither swappable).

## Threat Flags

None new. This plan opens no endpoint, adds no auth path, installs nothing (`requirements.txt` untouched, so T-3-SC stays `accept`) and reads no user input. The register's five `mitigate` rows are implemented:

- **T-3-21** (a write escaping the use case's decision, or a failure answering 200) — *mitigated*: `test_an_uncommitted_block_is_rolled_back` proves the rollback on a normal uncommitted exit, and `test_a_domain_error_leaves_nothing_written` asserts the exception escapes the `async with`, which is only possible because `__aexit__` returns `None`.
- **T-3-23** (a partial write surviving a business refusal) — *mitigated*: `test_the_three_repositories_share_one_transaction` writes through two repositories in one block and asserts both halves are undone together, so atomicity is asserted across repositories rather than within one.
- **T-3-24** (a dirty pooled session inherited by the next request) — *mitigated*: `__aexit__` closes the session in a `finally` and drops the reference, so the close happens even if the rollback raises. `expire_on_commit=False` is paired with that close rather than standing alone.
- **T-3-19** (test residue, and a savepoint mode that quietly stopped working) — *mitigated*: the falsification evidence shows the commit test goes red without its commit, which is the only check that can distinguish a working `create_savepoint` from a degraded `rollback_only`; `make test` back to back reports 272 both times and the `users` table is empty afterwards.
- **T-3-25** (a credential reaching stdout through SQLAlchemy's logger) — *mitigated*: `create_engine` passes no `echo` argument, so it stays at its default of off, and nothing in `engine.py` logs or formats the DSN. `grep -c "echo" src/taskmanager/infrastructure/db/engine.py` prints `0`.

## User Setup Required

None new. `docker compose up -d db` (or `make up`) must be running before `make test`, and until `.env` exists on a given machine `DATABASE_URL`, `TEST_DATABASE_URL` and `JWT_SECRET` must be in the shell — `cp .env.example .env` covers all three.

## Next Phase Readiness

- **03-09 has exactly what it needs and nothing to invent.** `create_database_resources(settings)` returns the one object to put on `app.state`; the single `cast` belongs in `dependencies.py` and nowhere else; `SqlAlchemyUnitOfWork(resources.session_factory)` is the whole body of `get_uow`, and that dependency must not commit in its teardown (ARC-08, Anti-Pattern 1) — the boundary is already owned here.
- **The engine is built but never disposed yet.** `create_app()` does not hold it, so there is no lifespan to dispose it in; 03-09 adds both in the same commit. Disposal is symmetrical with construction and belongs to the composition root, per the responsibility map.
- **Phase 4 inherits the `uow` fixture and six worked examples of asserting on a transaction.** A use-case integration test is now `async with uow: ... await uow.commit()` plus a read-back; the fixture chain above it needs no further work.
- **The flush-ordering hand-off from 03-07 is confirmed rather than hit.** `test_the_three_repositories_share_one_transaction` writes a user and then a list in one block and does not trip `fk_task_lists_owner_id_users`, because both adapters flush explicitly inside `add()` and the calls are in reference order. A Phase 4 use case that stages both and relies on one flush at commit time will meet 03-07's finding.
- **Coverage is at 100% with the gate at 75%**, unchanged since 03-05 across 197 further statements.
- **ADR debt for 03-11 grows by one small entry**: the resolution of the CONTEXT "engine lifetime" discretion — builders in `infrastructure/db/engine.py`, an engine owned by the composition root, `DatabaseResources` as the typed carrier, and the reason a module-level engine is not an option. It joins the existing debt (the PostgreSQL 18 volume path, literal constraint names in revisions, the case-sensitivity contrast, the test-only key on `Settings`, the WR-05 resolution, `make test` requiring PostgreSQL, and the deliberate non-translation of the three CHECK constraints).
- No blockers.

## Self-Check: PASSED

All six created files exist on disk and `tests/integration/conftest.py` carries the `uow` fixture; all three task commits (`ea902c7`, `90e43d2`, `f2eaaf4`) are present in `git log`. No commit deleted a tracked file (`git diff --diff-filter=D --name-only HEAD~3 HEAD` is empty) and `git status --short` was clean after each. `make lint && make typecheck && make arch && make test` was run green before every commit: 272 passed, 100.00% coverage over `src/taskmanager` with the gate at 75%, three contracts KEPT.

---
*Phase: 03-persistence-runnable-stack*
*Completed: 2026-09-18*
