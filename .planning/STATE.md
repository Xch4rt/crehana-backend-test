---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
stopped_at: Completed 03-08-PLAN.md
last_updated: "2026-09-19T00:18:37.901Z"
last_activity: 2026-09-19
progress:
  total_phases: 7
  completed_phases: 2
  total_plans: 26
  completed_plans: 23
  percent: 88
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-09-17)

**Core value:** Every requirement in the challenge PDF is met to the letter and is provable in
under five minutes by an evaluator: `docker compose up`, run the tests, read the docs.
**Current focus:** Phase 03 — persistence-runnable-stack

## Current Position

Phase: 03 (persistence-runnable-stack) — EXECUTING
Plan: 9 of 11
Status: Ready to execute
Last activity: 2026-09-19

Progress: [█████████░] 88%

## Performance Metrics

**Velocity:**

- Total plans completed: 16
- Average duration: —
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 8 | - | - |
| 02 | 7 | - | - |
| 03 | 1 | - | - |

**Recent Trend:**

- Last 5 plans: —
- Trend: —

*Updated after each plan completion*
| Phase 01 P01 | 13min | 3 tasks | 15 files |
| Phase 01 P02 | 5min | 3 tasks | 7 files |
| Phase 01 P03 | 8min | 3 tasks | 3 files |
| Phase 01 P04 | 14min | 2 tasks | 3 files |
| Phase 01 P05 | 17min | 2 tasks | 3 files |
| Phase 01 P06 | 10min | 2 tasks | 2 files |
| Phase 01 P07 | 11min | 2 tasks | 1 files |
| Phase 01 P08 | 14min | 2 tasks | 2 files |
| Phase 02 P01 | 10min | 2 tasks | 10 files |
| Phase 02 P02 | 14min | 2 tasks | 4 files |
| Phase 02 P03 | 12min | 3 tasks | 11 files |
| Phase 02 P04 | 18min | 3 tasks | 12 files |
| Phase 02 P05 | 22min | 3 tasks | 17 files |
| Phase 02 P06 | 10min | 2 tasks | 3 files |
| Phase 02 P07 | 19min | 2 tasks | 6 files |
| Phase 03 P01 | 16min | 3 tasks | 9 files |
| Phase 03 P02 | 24min | 3 tasks | 8 files |
| Phase 03 P03 | 6min | 2 tasks | 6 files |
| Phase 03 P04 | 16min | 2 tasks | 4 files |
| Phase 03 P05 | 11min | 3 tasks | 5 files |
| Phase 03 P06 | 15min | 3 tasks | 7 files |
| Phase 03 P07 | 10min | 2 tasks | 3 files |
| Phase 03 P08 | 13min | 3 tasks | 7 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: Python 3.13, `src/taskmanager/` layout, psycopg 3 + SQLAlchemy 2.0 async, Alembic
- [Roadmap]: Domain entities as stdlib dataclasses; Pydantic at schema/DTO/settings boundaries
- [Roadmap]: RFC 9457 problem+json from a single exception handler, built before any router
- [Roadmap]: 404 for invisible resources, 403 for visible-but-forbidden
- [Roadmap]: Completion % over the whole list via one SQL aggregate; pytest-asyncio loop scope
  `function` by default; `postgres:18-alpine`

- [Phase 01-01]: requires-python >=3.13 with mypy/black analysis target py313 — host venv runs CPython 3.14.3
- [Phase 01-01]: requirements*.txt is the single version source; pyproject.toml has no [project.dependencies]
- [Phase 01-01]: Coverage measured as --cov=taskmanager (package name) with the 75% gate in pytest.ini addopts
- [Phase 01-01]: Host venv at `.venv/` (CPython 3.14.3); invoke tools as `.venv/bin/<tool>`; a bare
  `pytest` fails the 75% gate until plan 01-02 adds real modules and tests

- [Phase 01-02]: Executed plan 01-02 as a real TDD cycle: tests written and observed failing (3d48d02) before settings.py and main.py existed (58a0497)
- [Phase 01-02]: Settings secrets (database_url, jwt_secret) carry no default at all; jwt_secret enforces min_length=16, extra=forbid and frozen=True
- [Phase 01-02]: create_app(settings=None) is a factory with no module-level app instance, so taskmanager.main imports with zero environment configuration
- [Phase 01-02]: Coverage is 100% over 18 real statements with no pragma, no omit and no threshold change; the gate was observed firing at 40.91% and the output committed as evidence
- [Phase 01-03]: Root-level .importlinter (not [tool.importlinter] in pyproject.toml): equivalent, but an evaluator finds a file named after the tool in five seconds
- [Phase 01-03]: The architecture contract runs inside pytest via importlinter.application.use_cases.lint_imports; python -m importlinter.cli is forbidden - it exits 0 with a real violation in place
- [Phase 01-03]: RESEARCH Pitfall 2 corrected by execution: the [importlinter:contracts:] plural typo is harmless on 2.15; the real zero-contract trap is the hyphenated [import-linter:] prefix, and the guard test was observed catching it
- [Phase 01-04]: pre-commit repo-local hooks use .venv/bin-qualified entries; RESEARCH's bare entries were executed and both whole-program gates died with 'Executable not found' under a minimal PATH (evidence/pre-commit-venv-entry.txt)
- [Phase 01-04]: consequence accepted - .pre-commit-config.yaml is developer-host-only, so CI and the Docker image must never call pre-commit run; CI runs black/isort/flake8/mypy/lint-imports/pytest as named steps
- [Phase 01-04]: Makefile comments describe forbidden forms (ONESHELL, a version-suffixed python3, the python -m import-linter module) without spelling them, so the plan's grep gates stay strict - same convention as 01-03's docstring
- [Phase 01-05]: The research Dockerfile's test stage was observed red before shipping: it never copied .env.example, so 01-02's parity test failed while the run still printed 'Total coverage: 100.00%'; fix and both captures in evidence/docker-test-stage.txt
- [Phase 01-05]: Image size recorded as observed (368MB on linux/arm64 with a BuildKit attestation manifest), not RESEARCH's 285MB; both far under the 500MB ceiling
- [Phase 01-05]: ci.yml runs six gates as named direct steps with permissions contents:read and lint-imports --no-logo; the local hook framework is never invoked, since a runner has no .venv
- [Phase 01-06]: CLAUDE.md gains a hand-maintained ## Project Rules section placed outside every GSD delimiter block, transcribing the layer order from .importlinter rather than from CONTEXT so documentation cannot drift from enforcement
- [Phase 01-06]: DECISION_LOG.md opens with 19 ADRs (17 required): the two extra are 01-05's Dockerfile test stage and major-tag action pinning, both handed over as owed
- [Phase 01-06]: the duplicated gate list is documented twice on purpose - as a rule in CLAUDE.md and as a consequence in ADR-015 - because silent divergence between pre-commit and ci.yml is threat T-01-47
- [Phase 01-07]: AI_WORKFLOW.md opens with the five-section skeleton plus four dated incidents; Phase 7 sections carry explicit to-be-completed markers instead of filler
- [Phase 01-07]: The incident log quotes the coverage and import-linter captures verbatim (9 and 51 exact lines matched by script) rather than paraphrasing any number
- [Phase 01-07]: Four further real Phase 1 incidents (RESEARCH Pitfall 2 non-reproduction, pre-commit bare entry, Docker .env.example, 368MB image) were deliberately left out - the plan enumerates exactly four entries
- [Phase 01-08]: The whole Phase 1 gate was captured green in one uninterrupted run (format first, proven a no-op) rather than stitched from per-plan runs
- [Phase 01-08]: FND-10 satisfied by observation, not the fallback: CI run 35301518310 on Xch4rt/crehana-backend-test concluded success on the FIRST attempt, so RESEARCH A2's budgeted fix-up commit went unused
- [Phase 01-08]: 01-RESEARCH.md assumption A2 and DECISION_LOG.md ADR-019 ('the workflow has never run on a real runner') are now stale; Phase 7 owns the refresh since DECISION_LOG.md is append-only
- [Phase 01-08]: The user supplied an already-created empty public repo, so gh repo create was never run and GitHub's quick-setup README/first-commit snippet was ignored: the real eight-commit main was pushed unchanged, no force
- [Phase 01-08]: The attribution audit publishes both counts (raw=1, refined=0); the single raw match is the filename CLAUDE.md in commit 0456070's subject, not a trailer
- [Phase 02-01]: TDD RED is observed and captured as evidence/02-01-tdd-red.txt, never as a separate test() commit - the mypy (strict) pre-commit hook rejects a test importing a module that does not exist yet, and --no-verify is forbidden
- [Phase 02-01]: frozen+slots dataclass setattr on a NON-field raises FrozenInstanceError on CPython 3.13 (Docker/CI) but TypeError on 3.14.3 (host); negative attribute tests assert the portable claim (refused, no __dict__, exact __slots__) - evidence/02-01-frozen-slots-setattr.txt
- [Phase 02-01]: No can_transition() helper beside ALLOWED_TRANSITIONS - the state machine is a Task invariant owned by the entity (02-03); CompletionStats carries no __post_init__ guard because Phase 3's COUNT(*) FILTER aggregate owns that invariant
- [Phase 02-02]: DomainError.details is typed dict[str, str | int | float | bool | None], not dict[str, Any] - an unserialisable value is now a mypy error at the raise site instead of a server fault raised inside the error handler
- [Phase 02-02]: flake8-bugbear B042 counts POSITIONAL arguments against declared parameters, so every single-argument exception leaf forwards details as a keyword; 02-RESEARCH.md Pattern 6 only verified the two-parameter case - evidence/02-02-b042-leaf-arity.txt
- [Phase 02-02]: One __reduce__ on DomainError delegating to a module-level _restore covers pickle and copy for every subclass; no leaf defines a pickle dunder, and the explicit __str__ keeps the details dict out of log lines
- [Phase 02-03]: Entities are mutable @dataclass(slots=True) and their negative attribute tests assert AttributeError directly - a non-frozen slotted class installs no __setattr__, so 02-01's frozen 3.13-vs-3.14.3 divergence does not apply (evidence/02-03-mutable-slots-setattr.txt)
- [Phase 02-03]: domain/validation.py owns require_utc/require_text/optional_text and every entity delegates to them, so each limit exists exactly once - in the entity ClassVar passed as max_length, never as a literal in a guard, a message or a test
- [Phase 02-03]: change_status checks ALLOWED_TRANSITIONS before normalising now, so a rejected move leaves the entity byte-identical; the same-state no-op returns before either check (D-02)
- [Phase 02-03]: User.PASSWORD_HASH_MAX_LENGTH = 512 is a sanity bound, not a policy - the minimum-password-length rule applies to the plaintext, which never reaches the domain; the entity validates no email format either, because EmailStr owns that at the boundary (D-04)
- [Phase 02-04]: ARC-07 is satisfied: register_exception_handlers(app), called by create_app(), is the only place an error body is produced - four handlers, one problem() builder, one class-keyed status table resolved by MRO walk
- [Phase 02-04]: Exception handlers annotate the base Exception type and narrow with an isinstance assertion: mypy strict rejects the narrower annotation (callable parameters are contravariant) and the if/raise form adds partial branches the 100% gate cannot cover
- [Phase 02-04]: STATUS_BY_EXCEPTION holds eight entries and no leaf class: TaskNotFoundError and its four siblings resolve through their parent by MRO, and the table uses int literals because 422's HTTPStatus member name changed across Python versions
- [Phase 02-04]: coverage report --include A --include B keeps only B, so the plan's presentation coverage command measured main.py alone; the comma-separated single-flag form is the honest one and is captured in evidence/02-04-tdd-red.txt
- [Phase 02-05]: ARC-04 satisfied: the eight ports are typing.Protocol classes with ... bodies only, and each has a conforming in-memory fake under tests/ named in eight test_fake_*_satisfies_the_*_port tests
- [Phase 02-05]: mypy checks a MUTABLE protocol member invariantly, so FakeUnitOfWork.tasks must be annotated TaskRepository exactly; the fake exposes the same object twice (tasks + task_repository) and Phase 3's SqlAlchemyUnitOfWork will need the same annotation
- [Phase 02-05]: The invisible-task test catches the base DomainError and then asserts the leaf is TaskNotFoundError and not AuthorizationError - catching the leaf directly would pass against an implementation that never considered the 403 question (ADR-008)
- [Phase 02-05]: ChangeTaskStatus has no same-state branch and no AuthorizationError branch, both deliberate: idempotence is a change_status invariant (D-02) and ASGN-02 leaves no visible-but-forbidden case for this verb
- [Phase 02-06]: ARC-06 is ticked here: 02-06 is its LAST claimant across the 02-0* plans (02-02, 02-03, 02-06); 02-07 claims only ARC-04 and ARC-02, so ARC-02 stays untouched
- [Phase 02-06]: Roadmap SC-1 is now mechanically true - tests/architecture/test_domain_is_stdlib_only.py walks the domain with ast and checks every import root against sys.stdlib_module_names, which the enumerated import-linter contract cannot do
- [Phase 02-06]: The gap is demonstrated, not asserted: a planted 'import greenlet' turns the new test red while lint-imports exits 0 reporting 'Domain is framework-free' KEPT - the graph even grew from 48 to 50 files, so grimp saw the import and the contract had nothing to say about it
- [Phase 02-06]: The new check adds no gate to .pre-commit-config.yaml or ci.yml on purpose - it rides inside pytest, which both already invoke, so ADR-015's two-places rule never applies
- [Phase 02-06]: ADR-020 refines ADR-004 rather than overturning it: DTOs are frozen slotted dataclasses, and pydantic is deliberately NOT added to application-framework-free's forbidden_modules
- [Phase 02-07]: ROADMAP Phase 2 SC-1 amended beyond the plan's four artifacts: it credited the import-linter contract with proving the domain is stdlib-only, which 02-06 demonstrated it cannot; it now names tests/architecture/test_domain_is_stdlib_only.py and ADR-022
- [Phase 02-07]: pydantic stays absent from application-framework-free's forbidden_modules and the .importlinter comment now records that as a decision - the previous comment claimed the opposite of the code, which is worse than either option
- [Phase 02-07]: AI_WORKFLOW.md gained nine Phase 2 incident entries rather than the three the plan owes; each is traceable to a summary, an evidence file or a commit hash, and the uncommittable TDD RED step is recorded as a compromise with its cost
- [Phase 02-07]: ARC-02 and ARC-04 were re-verified against the code before being ticked (three slotted entity dataclasses plus two StrEnums plus the AST proof; eight Protocol ports and a use case depending only on UnitOfWork and Clock), not inherited from a plan header

- [Phase 03-01]: Constraint names are GENERATED by the MetaData naming convention, never typed per table; constraints.py holds the twelve names as Final constants and is the single source D-13's IntegrityError translation keys on
- [Phase 03-01]: Per-owner task-list name uniqueness is case-SENSITIVE (D-12 wins over two stale comments) - TaskList folds no case on its name while User lowercases its email, so uq_task_lists_owner_id_name and uq_users_email_lower differ on purpose; the fake, the entity docstring and the model now say so identically
- [Phase 03-01]: D-10 corrected in place rather than patched later - users.updated_at and task_lists.description exist on the entities, so both are in the baseline schema instead of arriving as a fake second revision
- [Phase 03-01]: The schema is proven by compiling CreateTable + CreateIndex against the psycopg dialect and asserting on the rendered SQL, with no database; plan 03-05 owns the live-server counterpart, and the two test modules say so to each other
- [Phase 03-01]: mypy strict rejects postgresql.dialect() as no-untyped-call (PGDialect() too), so the typed create_engine('postgresql+psycopg://').dialect is used - it resolves the dialect eagerly and connects lazily, so no test needs PostgreSQL
- [Phase 03-01]: Requirement ticks DB-01/03/04/05 deliberately NOT taken - 03-11 is the last claimant of all four under the project's last-claimant convention
- [Phase 03-02]: alembic.ini carries no database URL key at all - env.py reads config.attributes['sqlalchemy_url'] then DATABASE_URL, so ConfigParser interpolation never sees a percent character and no live credential sits in a printable config object
- [Phase 03-02]: PostgreSQL 18 images mount the data volume at /var/lib/postgresql, not /var/lib/postgresql/data - RESEARCH Pattern 6's path is pre-18 and postgres:18-alpine exits 1 on it, which would have broken docker compose up for the evaluator
- [Phase 03-02]: The baseline revision keeps literal constraint names instead of importing constraints.py - a revision is a frozen record, and the agreement is already checked in two hops (test_models.py, then alembic check)
- [Phase 03-02]: Autogenerate DID render the three CHECK constraints: Pitfall 8's blindness applies to comparing an existing table, not to adding one - but alembic check still cannot prove they survive, so DB-04 rests on 03-05's insert-and-refuse tests
- [Phase 03-02]: sa.literal_column('lower(email)') in the migration against text('lower(email)') in the model is drift-free, because alembic check compares the reflected database to the model and never to the revision file
- [Phase 03-03]: TEST_DATABASE_URL is a declared optional Settings field AND a .env.example key - RESEARCH Pitfall 6 option (a); documenting it in only one of the two would make cp .env.example .env fail at boot under extra=forbid
- [Phase 03-03]: The test DSN is derived with make_url(url).set(database=...).render_as_string(hide_password=False), never a substring substitution - the compose credential pair taskmanager:taskmanager puts the word in the user and the password too
- [Phase 03-03]: .env.example documents the compose host as a COMMENTED DATABASE_URL line - a second live assignment would survive the parity test (it collects key names) while silently changing which host pydantic reads (D-15)
- [Phase 03-03]: SystemClock is the runtime Clock adapter in infrastructure, returning datetime.now(UTC); conformance is structural under mypy strict, with no base class and no ABC

- [Phase 03-04]: WR-05 resolved as RESEARCH Open Question 5 recommends - D-14 is refined by SCOPE, not by error type: a naive datetime reaching the domain is still a ValidationError, while one read FROM the database raises NaiveDatetimeFromDatabaseError, a RuntimeError deliberately outside the DomainError hierarchy, so a schema regression becomes the fixed 500 and never a 422 naming a column no request contains. This is the ADR 03-11 owes
- [Phase 03-04]: NaiveDatetimeFromDatabaseError forwards its COLUMN to super().__init__() and renders the message in __str__ - flake8-bugbear B042 rejects a keyword-only exception parameter outright, and forwarding the rendered message would rebuild the error with its own message as the column name under copy.copy()
- [Phase 03-04]: violated_constraint() narrows error.orig with a real `if isinstance(...)`, not the assertion idiom handlers.py uses, because the None result is a reachable documented outcome; three tests cover both None paths (non-psycopg original, orig=None, psycopg.Error with an empty Diagnostic)
- [Phase 03-04]: The positive branch of violated_constraint() is the ONE uncovered line in src/taskmanager, left to 03-06/03-07 on purpose - a psycopg Diagnostic is populated by libpq and a hand-built stand-in would pass against a broken implementation too
- [Phase 03-04]: One _aware() guard serves mandatory and nullable timestamp columns through two @overload stubs, so no mapper call site needs a cast and none can silently widen a required field into an optional one
- [Phase 03-04]: Requirement ticks DB-03/DB-04 deliberately NOT taken - 03-11 is the last claimant, the fourth consecutive plan in this phase to make the same call

- [Phase 03-05]: migrated_database refuses any database whose name is not taskmanager_test BEFORE opening a connection - the fixture runs downgrade base, which drops every table, and 03-03 exported TEST_DATABASE_NAME for exactly this check; it sits after _require_database so an unreachable host still produces the D-03 instruction first (T-3-18)
- [Phase 03-05]: The D-03 fail-fast raises pytest.fail AFTER the except block, never inside it - raised inside, the Failed carries the driver error in __context__ and pytest prints two chained tracebacks above the one line of instruction, which is the exact outcome D-03 exists to prevent; both forms were run and compared
- [Phase 03-05]: alembic_config() lives in tests/integration/conftest.py and test_migrations.py imports it, so the Pitfall 4 argument for configure_logging=False is written once; both tests/ and tests/integration/ are packages, so pytest and the test import the same module object
- [Phase 03-05]: An expected IntegrityError runs inside connection.begin_nested() - a refused statement aborts the PostgreSQL transaction the isolation fixture owns, so the savepoint is what lets the next assertion in the same test still run; written once in a refused() helper rather than as a comment repeated seven times
- [Phase 03-05]: Constraint tests assert the constraint NAME through violated_constraint(), not the exception type - IntegrityError alone would pass for a violation the test never intended, and this makes the suite a live test of the function D-13's translation calls
- [Phase 03-05]: RESEARCH assumptions A2 and A4 are settled empirically here: psycopg populates diag.constraint_name for FOREIGN-KEY violations too (closing the last uncovered line in src/taskmanager, so coverage is now 100.00%), and a timestamptz column round-trips an aware UTC value unchanged
- [Phase 03-05]: .github/workflows/ci.yml needs NO change, confirmed by reading it - DATABASE_URL already names taskmanager_test and TEST_DATABASE_URL is unset, so resolve_test_database_url derives the identical URL and the name guard passes
- [Phase 03-05]: Requirement ticks DB-02/DB-04/DB-05 deliberately NOT taken - 03-11 is the last claimant, the fifth consecutive plan in this phase to make the same call

- [Phase 03-06]: The IntegrityError translation is ONE private NoReturn helper per adapter called from both write paths, not the block copied into add() and update() - a second copy ages separately, and the foreign-key branch cannot fire from update() (apply_task_list_to_row deliberately does not write owner_id), so a copy would ship a branch no test could reach
- [Phase 03-06]: Opening a SAVEPOINT flushes whatever is already pending, so anything a test needs PostgreSQL to refuse must be added INSIDE begin_nested() - the first unrecognised-IntegrityError test was green with add() entirely uncovered, caught by reading the per-test coverage row rather than the exit status
- [Phase 03-06]: exists_with_name returns `count is not None and count > 0` as one expression: AsyncSession.scalar is typed int | None so the plan's bare comparison fails mypy strict, and the expression form adds no branch coverage would want a second test for
- [Phase 03-06]: The SC-4 gate is a source-TEXT scan, not an AST walk and never a runtime check - the property is about the text, and the project's prose-not-literal convention makes a docstring mention under that package a violation too; the AST upgrade is recorded as legitimate, the runtime check as not
- [Phase 03-06]: The SC-4 gate adds no pre-commit hook and no CI step - it rides inside pytest, which the hook set, the Docker test stage and CI already run, so ADR-015's two-places rule does not apply (same argument as 02-06)
- [Phase 03-06]: Requirement ticks DB-01/DB-03/ARC-08 deliberately NOT taken - 03-11 is the last claimant, the sixth consecutive plan in this phase to make the same call

- [Phase 03-07]: completion_statement() is a MODULE-LEVEL function rather than four lines inside completion_stats() - it is the only way a test can compile the aggregate and assert FILTER (WHERE, one FROM tasks and two count(*) with no server and no event listener, which turns ADR-009 from an intention into a gate
- [Phase 03-07]: The three CHECK constraints are deliberately NOT translated and the absence is a test: a ck_tasks_* refusal means a row bypassed Task.__post_init__, which is a process defect that must become Phase 2's fixed 500, never a 422 naming a field the request never contained
- [Phase 03-07]: TASK-06's status and priority filters are appended to the statement under `if ... is not None` and never applied to the result; the conjunction test asks for pending+high (no rows) as well as pending+low (one row), so an OR or last-argument-wins implementation fails while both single-filter tests still pass
- [Phase 03-07]: Listing orders by created_at THEN id and two seeded tasks share an instant - a timestamp alone is not a total order, and the bug it produces in Phase 4 is flakiness rather than wrongness
- [Phase 03-07]: SQLAlchemy orders a flush by relationship() declarations, not by raw ForeignKey columns - users and task_lists added in one flush emitted the lists first and PostgreSQL refused them; two flushes in reference order, and 03-08 will meet the same thing
- [Phase 03-07]: `type(x) is Task` replaces the sibling suite's `not isinstance(x, TaskRow)` - mypy warn_unreachable proves Task and TaskRow can have no common subclass, so the isinstance form is dead code and fails make typecheck
- [Phase 03-07]: Requirement ticks DB-01/DB-03/DB-04/ARC-08 deliberately NOT taken - 03-11 is the last claimant, the seventh consecutive plan in this phase to make the same call
- [Phase 03-08]: infrastructure/db/engine.py exports BUILDERS and instantiates nothing - a module-level engine would read Settings at import, so importing the module would crash mypy, import-linter and a plain `docker build`, exactly as main.py's docstring already argues for the app object; this resolves the STACK-vs-ARCHITECTURE contradiction CONTEXT flagged
- [Phase 03-08]: DatabaseResources is a frozen dataclass carrying the engine and the session factory together, because starlette's State.__getattr__ returns Any - one container means 03-09 casts once in dependencies.py instead of once per read
- [Phase 03-08]: SqlAlchemyUnitOfWork holds `_session: AsyncSession | None` behind an `_open_session` property that raises a RuntimeError naming the rule; RESEARCH Pattern 3's attribute-in-__aenter__ shape makes a commit outside the block an AttributeError about a private field, and Phase 4 will hand these out through Depends
- [Phase 03-08]: The unit of work's three repository attributes are annotated with the PORT types, and that was verified by breaking it - the concrete annotation makes mypy report `tasks: expected "TaskRepository", got "SqlAlchemyTaskRepository"`, because a mutable Protocol member is checked invariantly
- [Phase 03-08]: Transaction proofs assert a READ, never a counter - `commits == 1` is equally true of a unit of work whose __aexit__ rolled the commit straight back, which is precisely the WR-06 failure the suite exists to catch
- [Phase 03-08]: The commit falsification is on disk (evidence/03-08-commit-falsification.txt): every read in the integration suite shares the fixture's connection, so only the second-connection test and the red/green pair can distinguish a working `create_savepoint` from a silently degraded `rollback_only` (Pitfall 1)
- [Phase 03-08]: Requirement ticks DB-01/ARC-08 deliberately NOT taken - 03-11 is the last claimant, the eighth consecutive plan in this phase to make the same call

### Pending Todos

[From .planning/todos/pending/ — ideas captured during sessions]

None yet.

### Blockers/Concerns

[Issues that affect future work]

- Phase 3 (async session lifecycle, transactional test fixtures, Alembic `env.py`) and Phase 5
  (JWT/hashing libraries, 403-vs-404 matrix) are flagged by research as needing
  `/gsd:plan-phase --research-phase`.

- `AI_WORKFLOW.md` must be appended to at the end of every phase; reconstructing it in Phase 7
  would undermine the project's own thesis.

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| *(none)* | | | |

## Session Continuity

Last session: 2026-09-18T23:52:05.626Z
Stopped at: Completed 03-07-PLAN.md
Resume file: None
