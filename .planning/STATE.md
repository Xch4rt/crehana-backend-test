---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
stopped_at: Completed 04-03-PLAN.md
last_updated: "2026-09-19T05:21:16.854Z"
last_activity: 2026-09-19
progress:
  total_phases: 7
  completed_phases: 3
  total_plans: 38
  completed_plans: 29
  percent: 43
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-09-17)

**Core value:** Every requirement in the challenge PDF is met to the letter and is provable in
under five minutes by an evaluator: `docker compose up`, run the tests, read the docs.
**Current focus:** Phase 04 — task-lists-tasks

## Current Position

Phase: 04 (task-lists-tasks) — EXECUTING
Plan: 4 of 12
Status: Ready to execute
Last activity: 2026-09-19

Progress: [████████░░] 76%

## Performance Metrics

**Velocity:**

- Total plans completed: 37
- Average duration: —
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 8 | - | - |
| 02 | 7 | - | - |
| 03 | 11 | - | - |

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
| Phase 03 P09 | 16min | 3 tasks | 11 files |
| Phase 03 P10 | 19min | 3 tasks | 5 files |
| Phase 03 P11 | 22min | 3 tasks | 5 files |
| Phase 04 P01 | 10min | 3 tasks | 8 files |
| Phase 04 P02 | 18min | 3 tasks | 10 files |
| Phase 04 P03 | 12min | 2 tasks | 6 files |

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

- [Phase 03-09]: taskmanager.__version__ is the ONE runtime version string and src/taskmanager/__init__.py is now the project's only non-empty package init, with the exception justified in its docstring; importlib.metadata was rejected because it raises PackageNotFoundError in exactly the environment pytest.ini's pythonpath=src creates, and tests/unit/test_version.py binds the constant to pyproject.toml
- [Phase 03-09]: Dependencies are injected as Annotated[T, Depends(f)], never as an argument default - flake8-bugbear's B008 matches the call name AS WRITTEN and .flake8 whitelists the dotted `fastapi.Depends` this project never uses; PATTERNS.md predicted B008 could not fire and make lint proved otherwise
- [Phase 03-09]: The lifespan closes over the DatabaseResources create_app just built instead of reading app.state.database - the plan's form type-checks only because the attribute arrives as Any, and dependencies.py stays the single place application state is narrowed (grep -c "cast(" prints 1)
- [Phase 03-09]: /health is a status document and never problem+json: the 503 is a status assignment on the injected Response, so both legs keep the declared response model and both appear in /openapi.json; the probe returns a bool so the driver's message is discarded rather than reported (T-3-26)
- [Phase 03-09]: get_uow is proven by a throwaway router that TAKES the provider, not by an override - an override replaces the code under test; the no-durable-teardown claim was falsified (one line added, assert 1 == 0) and the red/green pair is in evidence/03-09-teardown-falsification.txt
- [Phase 03-09]: Engine disposal is asserted by pool object identity before and after the lifespan, because dispose() recreates the pool - a connection-count assertion would pass vacuously against an engine that never connected
- [Phase 03-09]: The falsification run left a real row in taskmanager_test and had to be deleted by hand: test_dependencies.py deliberately runs OUTSIDE the D-01 rollback, which is the only arrangement in which an escaping write is visible
- [Phase 03-09]: Requirement ticks DOCK-03/ARC-08/DB-01 deliberately NOT taken - 03-11 is the last claimant, the ninth consecutive plan in this phase to make the same call

- [Phase 03-10]: The container readiness probe goes through SQLAlchemy's SYNC engine, never through libpq directly - DATABASE_URL carries a +psycopg driver token libpq reads as a connection-string syntax error, so the naive probe fails permanently on attempt 1 and the bounded loop then burns all thirty against a healthy database (Pitfall 2)
- [Phase 03-10]: The probe's engine is built ONCE before the retry loop, against RESEARCH Pattern 7 - building it parses the URL, so inside the try a malformed DATABASE_URL is treated as transient and retried thirty times, which is Pitfall 2's own failure arriving from a second direction
- [Phase 03-10]: ENTRYPOINT owns the program and CMD became the argument list (--host/--port): kept verbatim, the old full-command CMD would have been passed to the entrypoint and silently discarded, so `docker run <image> --port 9000` would have started on 8000 with no error
- [Phase 03-10]: The `test` compose service carries profiles: ["test"], AGAINST the plan's explicit instruction - the plan's reason (a profile adds a flag the README must explain) was falsified live, since `docker compose run` enables the profiles of the service it names, while the cost of omitting it was observed: `docker compose up` started the whole pytest suite as a side effect of the evaluator's first command
- [Phase 03-10]: The wait-for-database loop stays in the shell heredoc rather than becoming a module under src/taskmanager/ - that package's coverage has no omit and no pragma, so it would owe a unit test of a range(30) loop; the behaviour is proven instead by the cold-start rehearsal in evidence/03-10-cold-start.txt, which the entrypoint names by path
- [Phase 03-10]: The healthcheck's wiring to the database was falsified, not asserted: `docker compose stop db` turns the container unhealthy and /health 503 within the retry window, and `start db` returns both to healthy - a liveness-only check would have stayed green throughout (T-3-33)
- [Phase 03-10]: `docker compose down -v` does NOT remove containers of disabled profiles, so a `docker compose run test` without --rm survives a full reset; make down was left as plain `docker compose down` to match D-14
- [Phase 03-10]: Requirement ticks DOCK-02/DOCK-03/DB-02 deliberately NOT taken - 03-11 is the last claimant, the tenth consecutive plan in this phase to make the same call

- [Phase 03-11]: DECISION_LOG.md gains TWENTY-ONE ADRs (023-043), not the plan's twelve: the plan enumerates twelve decisions and the ten plan summaries handed forward nine more, and writing only twelve would have satisfied the acceptance criterion while pushing the debt into Phase 7 - which is exactly what this project's own AI_WORKFLOW thesis argues against
- [Phase 03-11]: ADR-028 settles WR-05 and names ADR-021 as the entry it refines: D-14 is a locked 02-CONTEXT decision that was never numbered, and ADR-021 is where its HTTP consequence (a domain ValidationError is 422) was decided, so that is the ADR a refinement by scope has to name rather than inventing a reference
- [Phase 03-11]: The log stays append-only mechanically, not by intention - `git diff DECISION_LOG.md | grep -c '^-'` prints 1, the diff header alone, and ADR-028/ADR-041 refine ADR-021/ADR-017/ADR-018 by id without editing them
- [Phase 03-11]: CLAUDE.md gains a sixth rule beyond the plan's five - the Annotated[T, Depends(...)] injection form - because it meets the section's own bar (enforced by flake8-bugbear B008 in make lint) and a Phase 4 router written the other way fails that gate for a reason that reads as a linter misconfiguration
- [Phase 03-11]: The AI_WORKFLOW entry names the two artifacts that were wrong: 03-10-PLAN.md forbidding the compose profile (both halves of its reasoning falsified live) and 03-RESEARCH.md Pattern 7 building the readiness engine inside the retry loop, which reintroduces the same document's Pitfall 2 from a second direction
- [Phase 03-11]: The gate capture was written to a scratch path and copied in afterwards, because writing it into .planning/ first would have made STEP 1's `git status --porcelain` non-empty - the one line in the transcript that has to be blank
- [Phase 03-11]: All eight requirement ticks taken (DB-01..DB-05, ARC-08, DOCK-02, DOCK-03), each re-verified against a named test or a named line of the gate capture rather than against a plan header - the 02-07 precedent, after ten consecutive plans deferred them
- [Phase 03-11]: Roadmap SC-4's wording says `infrastructure/repositories/` while the shipped path is `infrastructure/db/repositories/`; the claim is true of the real path and the gate scans the real path, and the discrepancy is recorded rather than silently reinterpreted
- [Phase 04-01]: test_get_settings_is_cached had been red on the developer host since 03-03 added TEST_DATABASE_URL to .env; fixed by monkeypatch.chdir(tmp_path) - the test's ISOLATION, never its assertion, since _env_file=None on the get_settings() path stops testing the function as production calls it
- [Phase 04-01]: Task.reprioritise carries no value guard - TaskPriority is a StrEnum and the enum-typed boundary field refuses non-members, so a defensive check would be an unreachable branch the no-pragma coverage rule could not excuse
- [Phase 04-01]: Task.DEFAULT_PRIORITY is the single copy of TASK-01's medium and Task.create reads it; a test binds inspect.signature(Task.create) to the ClassVar so 04-07's schema default cannot drift from the entity's
- [Phase 04-01]: the Unset sentinel is a single-member enum confined to application/dto/ - the docstring records the measured cost of the rejected Pydantic variant (a _Unset component in /openapi.json, the explicit-null error split across body.title.str and body.title.enum[_Unset]), and the narrowing was proven by deleting the guard and observing mypy report return-value
- [Phase 04-01]: requirement ticks LIST-04/TASK-01/TASK-03/TASK-08 deliberately NOT taken - 04-12 is the last claimant of all four and this plan ships only their domain-side preconditions, no endpoint
- [Phase ?]: [Phase 04-02]: Tasks 1 and 2 shipped as ONE commit - adding a method to a Protocol breaks every implementation at once, so the tree between them fails mypy strict, and CLAUDE.md forbids committing red with --no-verify; the red step is captured in evidence/04-02-port-change-red.txt, the same compromise 02-01 recorded
- [Phase ?]: [Phase 04-02]: The D-15 violation is planted TWICE - in application the import also breaks the pre-existing application-framework-free contract, so only the infrastructure planting (exactly ONE contract BROKEN) proves the new contract earns its place
- [Phase ?]: [Phase 04-02]: list_for_owner_with_stats sorts its own pairs rather than delegating to list_for_owner, mirroring the adapter's two separate ORDER BY clauses - a delegation would keep the test green if the grouped statement lost its ORDER BY
- [Phase ?]: [Phase 04-02]: FakeTaskListRepository takes the sibling FakeTaskRepository through its constructor and FakeUnitOfWork hands over the one it already builds, so the fake counts what a use case stored and can disagree with a wrong implementation
- [Phase ?]: [Phase 04-02]: The compiled-SQL test asserts count(*) ABSENT as well as count(tasks.id) present - the two render almost identically and differ only on the null-extended row an empty list produces
- [Phase ?]: [Phase 04-02]: Requirement tick LIST-03 deliberately NOT taken - 04-12 is the last claimant and this plan ships the repository capability with no endpoint above it
- [Phase 04-03]: the assignee clause of _may_change_status is DROPPED and the ASGN-02 test inverted to assert the Phase 4 scope - no Phase 4 endpoint sets assignee_id, so keeping it would ship a branch no request can reach and the no-pragma coverage rule could not excuse it; the test and the use-case docstring both name Phase 5 as the phase that restores it, in access.py
- [Phase 04-03]: the plan's 'grep -c TaskListNotFoundError access.py prints 1' is met in substance, not literally - the import line plus the one raise line are 2, and grep -c 'raise TaskListNotFoundError' is 1; collapsing them by importing the exceptions module would game a counter by abandoning the project's import-by-name convention. 'grep -c AuthorizationError prints 0' IS met literally, prose included, and the module docstring says it avoids the name deliberately
- [Phase 04-03]: visible_task compares the task's parent BEFORE loading the addressed list, so a wrong-list request (D-14) cannot reveal whether that list exists; all four refusal legs raise the task-shaped not-found error carrying only the identifier the caller already supplied
- [Phase 04-03]: indistinguishability is tested by producing BOTH refusals and comparing type, code and details - three comparative tests across the two modules - because a single-error assertion passes just as happily against an implementation that leaks existence through a different code
- [Phase 04-03]: the shared guard is a module of functions, never a GuardedUseCase mixin: an override is invisible at the call site while a missing 'await visible_task(...)' is an absent line in a diff; a ninth test asserts both guards leave commits and rollbacks at zero, so the transaction boundary stays with the use case (D-17, ARC-08)
- [Phase 04-03]: requirement ticks TASK-02/TASK-05 deliberately NOT taken - 04-12 is the last claimant and this plan ships the application-layer rule with no endpoint above it

### Pending Todos

[From .planning/todos/pending/ — ideas captured during sessions]

None yet.

### Blockers/Concerns

[Issues that affect future work]

- Phase 5 (JWT/hashing libraries, 403-vs-404 matrix) is flagged by research as needing
  `/gsd:plan-phase --research-phase`. The same flag on Phase 3 (async session lifecycle,
  transactional test fixtures, Alembic `env.py`) is discharged: the phase was planned with
  `--research-phase` and all five of its open questions are resolved in `03-RESEARCH.md`.

- `DECISION_LOG.md` ADR-019 still claims "the workflow has never run on a real runner", which
  has been false since plan 01-08 (CI run 35301518310 concluded success on the first attempt).
  The log is append-only, so Phase 7 owns the superseding entry.

- `AI_WORKFLOW.md` must be appended to at the end of every phase; reconstructing it in Phase 7
  would undermine the project's own thesis.

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| *(none)* | | | |

## Session Continuity

Last session: 2026-09-19T05:21:16.848Z
Stopped at: Completed 04-03-PLAN.md
Resume file: None
