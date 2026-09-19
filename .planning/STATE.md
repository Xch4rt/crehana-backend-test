---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: ready_to_plan
stopped_at: Phase 6 context gathered — ready to plan Phase 6
last_updated: 2026-09-19T20:06:05.426Z
last_activity: 2026-09-19 -- Phase 06 context gathered (06-CONTEXT.md, 15 decisions); suite baseline 1019 passed, 100% coverage
progress:
  total_phases: 7
  completed_phases: 5
  total_plans: 55
  completed_plans: 55
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-09-17)

**Core value:** Every requirement in the challenge PDF is met to the letter and is provable in
under five minutes by an evaluator: `docker compose up`, run the tests, read the docs.
**Current focus:** Phase 6 — test hardening & coverage

## Current Position

Phase: 6
Plan: Not started
Status: Ready to plan
Last activity: 2026-09-19 -- Phase 06 context gathered; Phase 05 complete (17/17) after gap closure 05-17 and a passing re-verification (6/6)

Progress: [██████████] 100%

The ROADMAP phase checkbox for Phase 5, its Progress-table status cell and its completion
date are deliberately untouched: they belong to the orchestrator after verification.
`total_plans` counts planned plans only - phases 6 and 7 are not yet planned, so 55/55
means "every plan written so far has been executed", not "the milestone is finished".

## Performance Metrics

**Velocity:**

- Total plans completed: 55
- Average duration: —
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 8 | - | - |
| 02 | 7 | - | - |
| 03 | 11 | - | - |
| 04 | 12 | - | - |
| 05 | 17 | - | - |
| 5 | 17 | - | - |

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
| Phase 04 P04 | 14min | 2 tasks | 3 files |
| Phase 04 P05 | 12min | 3 tasks | 11 files |
| Phase 04 P06 | 11min | 3 tasks | 12 files |
| Phase 04 P07 | 10min | 3 tasks | 7 files |
| Phase 04 P08 | 11min | 3 tasks | 7 files |
| Phase 04 P09 | 10min | 3 tasks | 3 files |
| Phase 04 P11 | 14min | 2 tasks | 3 files |
| Phase 04 P10 | 12min | 3 tasks | 2 files |
| Phase 04 P12 | 18min | 3 tasks | 7 files |
| Phase 05 P01 | 6min | 3 tasks | 8 files |
| Phase 05 P02 | 10min | 3 tasks | 9 files |
| Phase 05 P04 | 12min | 3 tasks | 9 files |
| Phase 05 P03 | 12min | 3 tasks | 21 files |
| Phase 05 P05 | 14min | 3 tasks | 10 files |
| Phase 05 P06 | 5min | 2 tasks | 7 files |
| Phase 05 P07 | 16min | 3 tasks | 16 files |
| Phase 05 P08 | 13min | 3 tasks | 13 files |
| Phase 05 P10 | 14min | 3 tasks | 10 files |
| Phase 05 P09 | 21min | 3 tasks | 7 files |
| Phase 05 P11 | 24min | 3 tasks | 10 files |
| Phase 05 P12 | 7min | 3 tasks | 8 files |
| Phase 05 P13 | 11min | 3 tasks | 4 files |
| Phase 05 P14 | 34min | 3 tasks | 4 files |
| Phase 05 P15 | 20min | 2 tasks | 2 files |
| Phase 05 P16 | 30min | 3 tasks | 6 files |
| Phase 05 P17 | 25min | 5 tasks | 18 files |

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
- [Phase 04-04]: TaskCollectionResult carries the three statistics FLAT rather than 04-RESEARCH's nested stats: CompletionStats - the plan's interfaces block and its acceptance criteria both read result.completion_percentage, and a nested value object would make the presentation schema reach through a domain type for a number; from_parts(tasks, stats) is where the unpacking happens exactly once
- [Phase 04-04]: ListTasksCommand's status/priority filters are plain X | None = None and NOT the Unset sentinel - for a filter, absent and null are the same request, so a second marker would be ceremony every use case has to unwrap; the asymmetry with the two update commands is argued in the command docstring rather than left implicit
- [Phase 04-04]: the thirty per-command convention tests are THREE parametrized tests over a COMMAND_CASES table with per-class ids, not thirty hand-written functions - same granularity in the report, and a command added later joins all three gates by joining one table
- [Phase 04-04]: UpdateTaskCommand's absence test asserts four names - status (D-08) plus owner_id, assignee_id and completed_at - so T-4-17's mass-assignment surface is refused as a set rather than one field at a time
- [Phase 04-04]: ChangeTaskStatusCommand moved to the end of the tasks banner with its body byte-identical, so the file reads task-lists-then-tasks and the status verb sits after the CRUD five it is deliberately not part of (D-08); nothing 04-03 decided was reverted
- [Phase 04-04]: requirement tick ARC-05 deliberately NOT taken - 04-12 is the last claimant, and this plan ships only the frozen-dataclass half; the Pydantic-at-every-HTTP-boundary half does not exist until the schemas and routers do
- [Phase 04-05]: updated_at moves whenever a field is PROVIDED, and therefore does not move at all when a command carries neither - the plan's task text expected an unconditional stamp, which contradicts both 04-PATTERNS Pitfall 10 and the verified 04-RESEARCH body; D-06 refuses an empty body at the schema, so the case never reaches the API
- [Phase 04-05]: list.py spells list_for_owner_with_stats exactly once, on the call, and names the capability in prose in the docstring - the plan's grep -c criterion is met literally rather than 'in substance', applying the project's prose-not-literal convention to a counter the plan itself wrote
- [Phase 04-05]: the N+1 proof is a counting subclass declared in the test module, and the list repository is handed a SECOND uncounted task repository sharing the same stored dict - counting the fake's own bookkeeping would have made the zero-calls assertion measure nothing
- [Phase 04-05]: GetTaskList, ListTaskLists and DeleteTaskList take no Clock and make nothing durable; their SUCCESS path asserts commits == 0 AND rollbacks == 1, because commits == 0 is equally true of a transaction nobody ever closed
- [Phase 04-05]: DeleteTaskList loads through visible_task_list and discards the entity - without the load a foreign list answers 204, the loudest possible way to tell a stranger their delete worked; the tasks go with it through ON DELETE CASCADE rather than a second cascade written in Python
- [Phase 04-05]: requirement ticks LIST-01..LIST-06 deliberately NOT taken - 04-12 is the last claimant, and this plan ships orchestration with no endpoint above it
- [Phase 04-06]: CreateTask refuses with the LIST-shaped error while its four siblings refuse with the task-shaped one - the caller addressed the list, no task exists yet, so there is no task identifier to answer with and nothing the list-shaped error can disclose that the request did not already contain; the module docstring argues the exception at length so a reader does not read it as an inconsistency with access.py
- [Phase 04-06]: updated_at moves whenever a field is PROVIDED and therefore not at all when a command carries none - the plan's task text asks for a stamp in the all-omitted case, which is unreachable from the guarded shape the same plan specifies; the identical call 04-05 made, and D-06 refuses an empty body at the schema so the case never reaches the API
- [Phase 04-06]: FakeTaskRepository.list_for_task_list gained the (created_at, id) sort the adapter has had since 03-07 - 04-PATTERNS section 11 scheduled it for both list methods and 04-02 applied it to the task-list side only; two ordering assertions were observed RED against the unsorted fake, capture in evidence/04-06-fake-ordering.txt, and the list fixture is now seeded in an order that is not the expected answer
- [Phase 04-06]: the TASK-06 conjunction is pinned by TWO pairs - completed+high matching no row and completed+low matching exactly one - because the empty case alone passes against an implementation that narrows to nothing whenever two filters arrive, and the one-row case alone passes against an OR
- [Phase 04-06]: test_the_filter_never_moves_the_statistics asserts the item counts DIFFER as well as the three counters matching, so it cannot pass vacuously against a filter that was silently dropped; D-08 is asserted from the command's dataclass fields AND from a source scan of update.py for the status mutator name, so status is unwritable by shape rather than by convention
- [Phase 04-06]: grep -c visible_task_list on create.py prints 2, not the plan's 1 - the import line plus the call line is the floor for import-by-name, and collapsing them by importing the access module would satisfy a counter by abandoning a convention; the same call 04-03 made for the same criterion on access.py itself
- [Phase 04-06]: requirement ticks TASK-01..TASK-08 deliberately NOT taken - 04-12 is the last claimant, and this plan ships orchestration with no endpoint above it
- [Phase 04-07]: the non-nullable PATCH mapper uses `value is not None`, NOT the plan's and 04-RESEARCH's membership test on model_fields_set - the membership form leaves the value `str | None` and mypy strict refuses to pass it to a `str | Unset` command field; the two questions are identical for those fields because the field validator has already refused an explicit null, while the nullable fields keep the membership form, where absence genuinely cannot be read off the value
- [Phase 04-07]: grep -c "Unset" prints 0 per schema module, not the plan's 1 - importing the sentinel by name gives the uppercase spelling the mixed-case pattern does not match, and 0 is the stronger reading since the sentinel TYPE is then never named at all; grep -c "UNSET" prints 3 and 5, every match the import line or a to_command argument (the 04-03/04-06 precedent for a counter met in substance)
- [Phase 04-07]: D-08 is proven by ABSENCE - status is not a field of TaskPatchRequest at all, so extra=forbid makes sending it exactly one extra_forbidden error at (status,), asserted with len(errors) == 1 so a model that both declared the field and refused it would still fail
- [Phase 04-07]: get_clock takes no Request and stores nothing on app.state - SystemClock is stateless, so the narrowing _resources exists for does not apply, and a test asserts two calls return different objects; CurrentActor is pinned through typing.get_args, so a refactor that repointed the alias at another provider fails there rather than in production
- [Phase 04-07]: the 'not authentication' phrase is asserted against inspect.getsource rather than __doc__, so moving the sentence into a comment still satisfies D-03's honesty requirement; the requirement is that a reader of the file is told, not that a particular string object exists at runtime
- [Phase 04-07]: requirement ticks ARC-05/TASK-01/TASK-03/TASK-06 deliberately NOT taken - 04-12 is the last claimant, the seventh consecutive plan in this phase to make the same call, and this plan ships the typed boundary with no route above it
- [Phase 04-08]: the plan's route-counting one-liners walk app.routes for .path/.methods, but FastAPI 0.141.1 with Starlette 1.6.0 leaves ONE opaque _IncludedRouter there with neither attribute - every route assertion, acceptance checks and the new inventory test alike, reads app.openapi()['paths'] instead, which is both the working form and the document a client actually reads
- [Phase 04-08]: every route declares a 500 leg beside its 404/409/422, because GET /api/v1/task-lists can produce none of the three and would otherwise have carried an EMPTY responses map - the 500 is Phase 2's fixed problem+json body, a real documented outcome rather than padding
- [Phase 04-08]: declaring 422 explicitly REPLACES FastAPI's generated HTTPValidationError entry, and that is a correction - this API answers 422 as RFC 9457 problem+json, so the generated entry documented a shape no endpoint has ever returned; publishing the real component is DOC-04's Phase 7 budget
- [Phase 04-08]: the tasks router takes the plan's conditional branch - the parameter is status_filter with Query(alias="status") because the plain name shadows the status module imported for the status-code constants; the public contract was MEASURED rather than assumed (422 with field "query.status")
- [Phase 04-08]: the D-15 import check flags the forbidden name bound from ANY module, not only fastapi and starlette.exceptions as 04-RESEARCH recommends - naming the two would tie the gate to a dependency's layout rather than to the property, and a local re-export would walk straight through it
- [Phase 04-08]: the red capture's plant 1 adds the import AS WELL AS the raise (the plan names only the raise) - a raise of an unbound name is not a state the codebase could reach, and plant 2, the import alone, is the run that proves the two assertions are not redundant: raise check green, import check red
- [Phase 04-08]: two grep criteria were met by rewording docstring prose rather than by changing code - "commit()" printed 1 and "response_class=Response" printed 2 from passages that spelled the forms they explained; the prose-not-literal convention since 01-03 exists precisely so these counters stay strict
- [Phase 04-08]: requirement ticks ARC-05/LIST-01..06/TASK-01..08 deliberately NOT taken - 04-12 is the last claimant, the eighth consecutive plan in this phase to make the same call; these routes have no HTTP test above them until 04-09 and 04-10, and a tick taken from a route's existence rather than its behaviour proves nothing
- [Phase 04-09]: the not-owned body is compared to the absent body with each response's own identifier tokenised out - STRONGER than the plan's 'identical apart from instance', which would leave the request path uncompared, since instance IS the path and therefore necessarily differs between the two requests
- [Phase 04-09]: PROBLEM_JSON and MEMBERS are imported from tests/api/test_error_contract.py rather than re-declared, so grep -c 'application/problem+json' prints 0 while grep -c 'PROBLEM_JSON' prints 10 - a tenth copy of a constant that already has a single home would satisfy a counter by abandoning the reason the counter exists (the 04-03/04-06/04-07 call)
- [Phase 04-09]: the two 409 tests are named ..._is_a_duplicate_409 rather than the plan's ..._is_409, because pytest -k matches the test id and the plan's own prescribed names contain no 'duplicate' - its own '-k duplicate collects at least 2' criterion would have collected 0
- [Phase 04-09]: seed() commits - under join_transaction_mode=create_savepoint a session closed without committing rolls its savepoint back, so seeded rows vanish and the first request 404s; the commit releases the savepoint into the outer transaction the connection fixture still rolls back, so isolation is unchanged and only visibility is bought
- [Phase 04-09]: api_client deliberately does NOT enter the lifespan - get_uow is overridden so the engine built against the fictional DSN is never dialled, and tests/integration/test_health.py stays the one place the engine's own lifecycle is proven
- [Phase 04-09]: acting_as is a restoring context manager rather than a one-way as_actor(app, id) setter, because a test that proved a 404 as a stranger and then asserted the owner's view would otherwise still be the stranger and pass for the wrong reason
- [Phase 04-09]: requirement ticks LIST-01..LIST-06 deliberately NOT taken - 04-12 is the last claimant, the ninth consecutive plan in this phase to make the same call, though the behaviour those ticks rest on is now proved over HTTP
- [Phase 04-11]: the seed step is numbered 2b and the entrypoint header was rewritten from 'Three steps' to name it - renumbering exec uvicorn to 4 would rename a step that has been step 3 since Phase 3 for the sake of a block Phase 5 deletes, so the letter carries the information instead
- [Phase 04-11]: the comment banner DESCRIBES the rejected targeted conflict form rather than spelling it - the plan's own acceptance criteria require grep -c of that form to print 0, and a comment quoting it would have failed the gate while explaining itself perfectly (the 01-03 prose-not-literal convention)
- [Phase 04-11]: the idempotence evidence carries a SECOND run the plan did not ask for - the same three executions against a targeted clause, where the third raises IntegrityError on uq_users_email_lower; executions 1 and 2 are byte-identical between the two forms, so a proof that only restarted with the same id would have passed against the form that aborts the container
- [Phase 04-11]: the seed proof ran against taskmanager_test, never taskmanager - its third execution deliberately attempts a second row and its cleanup deletes by email, so pointing it at the database docker compose up serves would have put a destructive statement beside an evaluator's data for no gain
- [Phase 04-11]: requirement tick LIST-01 deliberately NOT taken despite this plan's own frontmatter naming it - 04-12 is the last claimant of LIST-01..06 and TASK-01..08, the tenth consecutive plan in this phase to make the same call
- [Phase 04-10]: GET /api/v1/task-lists/{id}/tasks issues THREE statements, not the two 04-10-PLAN's interfaces block predicted - the third is 04-03's visible_task_list guard, which the plan forgot to count; the measured number shipped with all three named in TASK_COLLECTION_STATEMENTS, because removing the guard would trade a security property of this same phase for a number in a plan, and D-17 is about invariance rather than a magic number
- [Phase 04-10]: two status tests are named ..._rejects_an_unknown_value/_key rather than the plan's ..._is_422 - pytest exits 5, not 0, when -k matches nothing, so the plan's own prescribed names would have failed its own '-k rejects exits 0' clause; both halves of the either/or criterion are now literally true (the 04-09 precedent for renaming to contain the matched word)
- [Phase 04-10]: requirement ticks TASK-01..TASK-08 deliberately NOT taken despite this plan's own frontmatter naming all eight - 04-12 is the last claimant, the eleventh consecutive plan in this phase to make the same call, though the behaviour those ticks rest on is now proved over HTTP
- [Phase 04-12]: DECISION_LOG.md gains FOURTEEN ADRs (044-057), not the plan's enumerated nine - the eleven summaries handed forward five more (access.py and the dropped assignee clause, CreateTask's list-shaped refusal, the app.routes opacity, the HTTP harness design, the grouped LIST-03 statement with its three-statement D-17 finding); the 03-11 precedent of writing one too many rather than leaving one owed
- [Phase 04-12]: the log stayed append-only mechanically - git diff DECISION_LOG.md | grep -c '^-' prints 1, the diff header alone - and every refining entry names its predecessor by id (ADR-046 refines ADR-020, ADR-049 refines ADR-009, ADR-045 names ADR-037, ADR-051 names ADR-015)
- [Phase 04-12]: Roadmap Phase 4 SC-5 AMENDED, not reinterpreted: its 'no router imports SQLAlchemy' clause is true of both routers by inspection but is gated by nothing, and presentation as a whole deliberately imports SQLAlchemy in health.py and dependencies.py; the replacement names the two gates that exist and is stronger about HTTPException, since the AST gate refuses the import as well as the raise (the Phase 2 SC-1 and Phase 3 SC-4 precedent)
- [Phase 04-12]: all fifteen requirement ticks taken (ARC-05, LIST-01..06, TASK-01..08), each against a command that was run and exited 0 with at least one test collected, each naming a test in a new re-verification table in REQUIREMENTS.md - eleven consecutive Phase 4 plans deferred them to the last claimant and this is where that convention pays out
- [Phase 04-12]: the host and container gate runs disagree on coverage - 100.00% over 1155 statements vs 99.20% over 1267, same 599 tests - and the difference was explained rather than reported: the statement count is PEP 649 (visible in Phase 3 too at 730 vs 772), and the eleven missed lines are shown to be a measurement artifact by a labelled one-test probe in which test_create_returns_201_with_a_location_header_and_the_full_representation PASSES while coverage calls missed the only lines that set the header it asserts
- [Phase 04-12]: nothing was suppressed in response to that discrepancy - a pragma is forbidden by CLAUDE.md and would turn an artifact into a permanent exemption; the finding is handed to Phase 6, which owns TEST-03 and therefore the honesty of the coverage number
- [Phase 04-12]: the phase itself is deliberately NOT marked complete here - roadmap.update-plan-progress set the Phase 4 checkbox, its Progress-table status and its date, and all three were reverted by hand; plan-level progress (12/12) and the fifteen requirement ticks are this plan's, phase completion belongs to the orchestrator after verification
- [Phase ?]: [Phase 05-01]: PASSWORD_MIN_LENGTH/PASSWORD_MAX_LENGTH are module Final constants in domain/validation.py, not User ClassVars - the entity never sees plaintext, only the Argon2 hash, so no entity can own D-10's rule; Phase 2 D-04 still holds and this module is the only place in the domain that can hold it
- [Phase ?]: [Phase 05-01]: require_password's two departures from require_text (no strip, no _refuse_nul) are proven by BEHAVIOUR - eight spaces returned byte-identical and a NUL password returned unchanged - because a length-only test suite passes just as happily against an implementation that quietly trims
- [Phase ?]: [Phase 05-01]: Task.assign/unassign copy reprioritise exactly and carry no value guard; the entity deliberately has NO same-assignee no-op, and a test asserting unassign still stamps an already-unassigned task is what stops a later reader 'fixing' the asymmetry D-07 owns in AssignTask (05-08)
- [Phase ?]: [Phase 05-01]: jwt_secret's floor moved 16 to 32 as an isolated commit, justified by RFC 7518 section 3.2 and by the pytest.ini filterwarnings interaction rather than by taste; all three existing secrets were COUNTED first (conftest 32, .env.example 34, ci.yml 36), which is the finding that made D-26 a one-line change
- [Phase ?]: [Phase 05-01]: requirement ticks AUTH-04 and ASGN-02 deliberately NOT taken despite this plan's frontmatter naming both - 05-16 is the last claimant, and this plan ships a validator and two mutators with no use case and no route above them
- [Phase ?]: [Phase 05-01]: the TDD RED step is captured in evidence/05-01-tdd-red.txt rather than committed - pre-commit's mypy (strict) hook rejects a test importing a name no module exports and --no-verify is forbidden (the 02-01 and 04-02 precedent)
- [Phase 05-04]: the assignee short-circuit in visible_task sits AFTER the parent-list comparison
  and before uow.task_lists.get - ADR-050 outranks D-01, so an assignee addressing their task under
  the wrong list gets 404 and never learns where it really lives; a test pins that ordering on each
  guard, the owned_task one also asserting the list was never read
- [Phase 05-04]: the assignee leg is proven by an ABSENT statement - CountingTaskListRepository,
  declared in the test module, wraps get and get_for_update and the assertion is reads == []; the
  returned task alone would pass against an implementation that read the list and ignored it, which
  is the statement the leg exists to save (the 04-05 counting-subclass precedent)
- [Phase 05-04]: owned_task is a second function, never visible_task(require_owner=True) and never a
  (task, is_owner) tuple - the two differ by which failure SET they can produce, and a tuple would
  push the ADR-008 decision back into eleven use cases (ADR-055); both rejections are argued in the
  function's own docstring rather than left to the plan
- [Phase 05-04]: the comparative test is INVERTED for AUTH-06 - every other comparison in this suite
  produces two refusals and asserts they match, and these three produce two from ONE fixture and
  assert the class and the code DIFFER, because a single-error assertion passes just as happily
  against an implementation that answered the assignee 404 too
- [Phase 05-04]: the plan's access.py coverage criterion was already false before the plan - this
  module's own suite never passed for_update=True to either guard, so both locking roads were
  covered only by test_write_paths_hold_what_they_change.py; closed by writing the missing test
  rather than by reinterpreting the criterion
- [Phase 05-04]: update.py's docstring names the status ENDPOINT in prose because
  test_update_task_cannot_change_a_status asserts TaskStatus.__name__ is absent from the module
  source and the use case's name contains it as a substring - observed by probe and reverted
  (evidence/05-04-tdd-red.txt appendix); the 01-03 prose-not-literal convention protecting a D-08
  source scan rather than a grep criterion
- [Phase 05-04]: four docstring sentences beyond D-22's paragraph were falsified by this change
  ('two functions', 'Both functions', the for_update twin argument, 'reads its parent list plainly')
  and all four were rewritten in the commits that falsified them - a partial retirement one
  paragraph from the fix would have been the exact failure D-22 names
- [Phase 05-04]: requirement ticks AUTH-06/ASGN-01/ASGN-02 deliberately NOT taken - 05-16 is the
  last claimant, and this plan ships an application-layer rule with no route above it: nothing can
  set an assignee_id until 05-08, so no HTTP request yet produces this 403
- [Phase 05-03]: full_name is trimmed but NOT lower-cased, the deliberate opposite of email - an
  address is an identity key uq_users_email_lower defends, while a display name keys nothing, is
  never looked up by, and its capitals belong to the person who typed them; no CHECK constraint on
  the length either, because this schema enforces a text limit with VARCHAR(n) bound to the entity
  ClassVar and its three CHECKs guard invariants a width cannot express
- [Phase 05-03]: the construction blast radius was EIGHTEEN files, not the plan's fourteen - three
  User.create sites in test_fakes.py written after the plan's grep was taken, and a second class the
  plan did not consider at all: code that builds a users row WITHOUT the entity (three UserRow
  literals plus raw INSERT INTO users in test_constraints.py and test_schema.py), which bypasses
  User on purpose and is therefore obliged to name the new NOT NULL column itself
- [Phase 05-03]: the populated-table claim CANNOT be proven by the suite - migrated_database runs
  downgrade base first, so taskmanager_test is always empty when 0002 runs and the transient
  server_default is never exercised; proven instead by upgrading the live compose database
  0001 -> 0002 through the container's own entrypoint, with alembic check reporting no drift after
  (evidence/05-03-live-upgrade.txt)
- [Phase 05-03]: that live run found a real bug - docker/entrypoint.sh step 2b names its columns by
  hand and omitted full_name, so the seed INSERT became a NotNullViolation and the container aborted
  under set -eu, breaking docker compose up; ON CONFLICT DO NOTHING could not absorb it because
  PostgreSQL checks NOT NULL while building the candidate row, before the arbiter index is
  consulted. No test could have caught it: the entrypoint is a heredoc rather than a module
  (ADR-037), so nothing imports that INSERT - which is ADR-037's own cold-start argument paying out
- [Phase 05-03]: test_the_migration_directory_holds_exactly_one_revision is retired OUT LOUD, named
  in the docstring of the chain test replacing it - a count says nothing about whether the revisions
  can be walked, and a second head or a wrong down_revision would satisfy it while breaking upgrade
  head; the replacement reads Alembic's own ScriptDirectory against a deliberately unusable DSN
- [Phase 05-03]: splitting one revision file across two commits left taskmanager_test stamped 0002
  by an upgrade() that never created the index, so Task 2's downgrade() could not run; repaired with
  one CREATE INDEX IF NOT EXISTS against the test database only. A development artifact of the
  commit split, not a defect in the shipped chain - a deployment only ever walks 0001 -> 0002 forward
- [Phase 05-03]: the plan's grep for op.create_index(op.f("ix_tasks_assignee_id") on one line prints
  0, not 1 - the call is 89 characters and black wraps it, exactly as it already wraps the identical
  ix_tasks_task_list_id call in 0001; met in substance with grep -c on op.f("ix_tasks_assignee_id")
  printing 2 (the 01-03 prose-not-literal precedent applied to a counter the plan itself wrote)
- [Phase 05-03]: requirement ticks AUTH-01/ASGN-02/ASGN-03 deliberately NOT taken - 05-16 is the
  last claimant, the sixth consecutive plan in this phase to make the same call, and this plan ships
  a column and an index with no use case and no route above them
- [Phase 05-05]: the plan's own alg=none construction cannot be built - jwt.encode(claims, secret,
  algorithm='HS256', headers={'alg':'none'}) raises InvalidKeyError at ENCODE time in PyJWT 2.14.0,
  because the library prepares the key for the header's algorithm; the forgery an attacker actually
  sends is jwt.encode(claims, None, algorithm='none'), which is what the refusal table and the
  corrected acceptance run use. The plan's behaviour table row was right; only its construction was
- [Phase 05-05]: the off-loop proof records the callable and the ARGUMENT TUPLE anyio's run_sync
  received and then delegates to the real one, so it is simultaneously the transposed-argument
  guard - pwdlib's recommended() docstring still shows verify(hash, password), a transposed call
  raises UnknownHashError, and this adapter catches that into False, so a green round trip alone
  cannot tell a correct call from one that always answers no
- [Phase 05-05]: the throwaway password behind the dummy hash is generated with
  secrets.token_urlsafe(32), one step beyond the plan, which forbids only a hard-coded ENCODED
  Argon2 literal; generating the plaintext seed too means no string in the file reads as a
  credential to anyone grepping the repository (T-5-03), at no cost since it is never compared
- [Phase 05-05]: InvalidKeyError, PyJWTError and leeway=0 are argued in prose without being spelled
  - the plan's own grep criteria require those literals to appear 1, 0 and 0 times - so tokens.py
  says 'the library's own base exception class' and 'a leeway of zero'; the 01-03 prose-not-literal
  convention applied to counters the plan itself wrote
- [Phase 05-05]: SecurityResources' port annotations are pinned with typing.get_type_hints, because
  annotating the fields with the concrete adapters would type-check and run identically - mypy
  accepts them, they satisfy the ports - and the only thing it would break is the reason the
  container exists; the no-I/O promise is likewise falsifiable, with socket and open replaced by
  objects that raise and the builder called between them
- [Phase 05-05]: both port bindings went to test_adapter_ports.py even though Task 1's <behavior>
  lists the PasswordHasher one - that module's docstring already argues, about Clock, that asserting
  a binding twice makes one port change look like two problems, and Task 3's <action> owns the file
- [Phase 05-05]: requirement ticks AUTH-02/AUTH-04 deliberately NOT taken - 05-16 is the last
  claimant, the seventh consecutive plan in this phase to make the same call, and this plan ships
  two adapters and a container with no use case and no route above them
- [Phase 05-06]: JsonFormatter renders exc_info into an `exception` field, which neither the plan
  nor 05-RESEARCH Pattern 8 does - handlers.py logs the fixed 500 with exc_info=exc and its
  docstring promises the traceback reaches the log, exc_info is a RESERVED LogRecord attribute so
  the extras merge skips it, and the two existing caplog assertions read record.exc_info rather
  than formatted output: the suite would have stayed green while every traceback vanished
- [Phase 05-06]: the notifier names its logger with the literal taskmanager.notifications, not the
  plan's getLogger(__name__) - __name__ here is taskmanager.infrastructure.notifications.logging,
  a sibling branch that never propagates to taskmanager.notifications, so D-15, the plan's own
  <behavior> line and its own acceptance snippet would all have been false
- [Phase 05-06]: stack_info is deliberately NOT rendered and json.dumps gets no default= fallback -
  the first would be a branch no test could reach under the no-pragma coverage rule, the second
  would hide the call-site bug that stringifying task_id at the call site exists to make impossible
- [Phase 05-06]: the handler is attached to the PACKAGE logger, so the fixed 500's ERROR record is
  JSON from now on; the blast radius is named in the module docstring rather than left to a
  changelog, and 05-16 owes an ADR for it and a second one for the exception rendering above
- [Phase 05-06]: requirement tick NOTF-02 deliberately NOT taken - 05-16 is the last claimant, the
  eighth consecutive plan in this phase to make the same call: nothing calls configure_logging()
  and nothing constructs LoggingEmailNotifier in production until 05-10 and 05-11
- [Phase 05-07]: the 401 message moved onto AuthenticationError itself, as a ClassVar REFUSAL
  defaulted into __init__, and infrastructure/security/tokens.py lost its private _REFUSAL copy -
  D-11 requires a junk token and a token whose subject has no row to produce the same body, and
  two constants in two layers agree only until one is edited, with no test able to notice
  (test_tokens.py asserts the adapter's refusals share ONE message without asserting which)
- [Phase 05-07]: Login keeps a refusal constant of its own rather than reusing that default - the
  two endpoints answer different questions, D-12 requires only that LOGIN's two legs match, and
  one object referenced by two raise statements is what makes them match by construction
- [Phase 05-07]: FakeUserRepository.add compares against `stored` directly, never through its own
  get_by_email - the race-backstop test blinds the lookup, which is what an interleaved
  transaction sees, and the delegating form disabled the refusal too; observed DID NOT RAISE
  before the fix. PostgreSQL does not consult a repository method before enforcing a constraint
- [Phase 05-07]: COMMAND_CASES now holds all fourteen commands while the actor-first gate runs
  over a filtered subset, with ACTORLESS_COMMANDS declared AND re-derived from the table - three
  of this plan's four commands break the rule that gate asserts, and dropping them from the table
  would have taken them out of the immutability and slots gates too
- [Phase 05-07]: FakePasswordHasher gained `hashed` and `verifications` beside 05-02's
  dummy_verifications - T-5-07's 'the hasher was never called' and D-12's per-leg counts are
  unassertable without them, and the only alternative is a stopwatch, which the plan itself bans
- [Phase 05-07]: the plan's 'the id comes from uuid4() inside User.create' is imprecise - the
  entity takes user_id as a keyword argument (Phase 2 D-11/D-12 put id generation in the
  application layer), so RegisterUser calls uuid4() at the call site exactly as CreateTaskList
  does; the property the plan wanted holds and a test asserts two registrations differ
- [Phase 05-07]: two grep criteria met by rewording prose rather than code - SecretStr prints 0
  and require_password prints 2 - and the plan's per-module coverage command cannot run as
  written, because pytest.ini's addopts already carry --cov=taskmanager --cov-fail-under=75, so
  measuring one module while running a subset exits at ~71% (the 02-04 --include artifact again)
- [Phase 05-07]: requirement ticks AUTH-01/AUTH-02/AUTH-04/AUTH-05 deliberately NOT taken - 05-16
  is the last claimant, the ninth consecutive plan in this phase to make the same call, and these
  four use cases have no route above them until 05-11

- [Phase 05-08]: NO noqa on the broad except in assign.py, against the plan and 05-RESEARCH - the
  line was run with no suppression and flake8 exited 0, because the installed set (bugbear 26.9.9
  + comprehensions + pep8-naming) has no check for the shape; BLE001 is a Ruff code and the one in
  docker/entrypoint.sh sits in a heredoc flake8 never reads (evidence/05-08-broad-except-lint.txt)
- [Phase 05-08]: the NOTF-01 ordering is proven from a shared event list, never from two counts of
  one - a fake unit of work and a notifier that both append, asserting ['commit', 'send'], because
  one commit and one send is equally true of a send that ran first, which is the outcome D-16 puts
  the send outside the block to prevent
- [Phase 05-08]: _ClosingUnitOfWork swaps in a user repository that raises on every method as its
  block ends, so 'the address is captured INSIDE the block' is a failing test rather than a comment
  - the dictionary fakes cannot otherwise model the port's documented RuntimeError after exit
- [Phase 05-08]: the T-5-12 guard-ordering test produces BOTH stranger refusals and compares them
  on class, code, details and message; a single assertion that an invented assignee id yields
  TaskNotFoundError passes against an implementation that leaked the difference through a code the
  assertion never read (the 04-09 / 05-04 comparative shape)
- [Phase 05-08]: both no-op tests assert updated_at UNCHANGED as well as commits == 0 - Task.assign
  and Task.unassign stamp unconditionally by design (05-01), so an implementation that returned
  early after calling the mutator satisfies every counter while moving the timestamp
- [Phase 05-08]: test_dtos.py gained a gate the plan did not ask for - the set of commands carrying
  an assignee_id is derived from the whole table and must equal {AssignTaskCommand}; T-5-10's
  mitigation rests on that uniqueness and the existing test asserted it of UpdateTaskCommand alone,
  so a NEW command growing the field would have passed
- [Phase 05-08]: for_update=True is spelled exactly twice in assign.py, one per write path, and the
  two prose mentions that made the plan's counter print 4 were reworded rather than the counter
  reinterpreted (the 04-05 precedent); list_for_assignee prints 1 and commit prints 0 in both reads
- [Phase 05-08]: requirement ticks ASGN-01/ASGN-02/ASGN-03/NOTF-01/NOTF-03 deliberately NOT taken -
  05-16 is the last claimant, the tenth consecutive plan in this phase to make the same call, and
  these four use cases have no route above them until 05-11 and 05-12

- [Phase 05-10]: OWNER_ID lives in tests/integration/conftest.py and test_task_lists.py imports it,
  against the plan's 'module-local' wording - the fixture that installs the override and the users
  row the tests seed have to be ONE value, and two copies agree only until one is edited with
  nothing able to notice (the 04-09 PROBLEM_JSON precedent applied to an identifier the harness
  owns); the plan's own 'grep -c OWNER_ID >= 5' prints 6 either way
- [Phase 05-10]: the deleted 'not authentication' test is replaced by a source scan of
  IMPLEMENTATION names, not English words - a first draft forbade 'algorithm' and 'secret' and
  immediately collided with the docstring the same plan requires; the shipped tuple is jwt, pwdlib,
  argon2, hs256, rs256, so actor.py says 'bearer token' throughout and never names the format,
  which is also the truer statement: the format is the adapter's business
- [Phase 05-10]: Task 2's 'grep DEMO_USER_ID in tests/ prints 0' criterion cannot hold at Task 2 -
  tests/unit/presentation/test_actor.py is the module whose subject IS the constant, and Task 2
  changes no production code by design; the identical Task 3 criterion over src/ tests/ docker/
  prints 0, and the harness-first ordering is what keeps each commit green
- [Phase 05-10]: three grep counters were met by rewording prose rather than code - auto_error=False
  printed 3 and the deleted step's old label printed 1, both from passages explaining the forms they
  named (the 01-03 prose-not-literal convention, now in its fourth phase)
- [Phase 05-10]: the four header shapes are driven over HTTP in a UNIT test rather than by calling
  the provider with None - 'no header' and 'Basic zzz' both arrive as None and 'Bearer ' arrives as
  '', so the distinction lives in FastAPI's parse and a hand-passed value would prove nothing; the
  lowercase-scheme leg cannot be expressed at all without a real request
- [Phase 05-10]: nothing went into the lifespan - the security container owns no pool, no file and
  no socket, the startup half stays empty (D-06), and the HTTP harness never enters the lifespan
  (ADR-056), so anything placed there would be untested by every test that drives the app over HTTP
- [Phase 05-10]: the already-seeded demo row on the compose database was deliberately left in place
  rather than deleted - password_hash is '!', which is not an Argon2 encoded hash, so 05-05's
  adapter turns any verification against it into False; a fresh volume never gets the row, and
  docker compose down -v is the developer's one-line removal
- [Phase 05-10]: requirement ticks AUTH-03/AUTH-05/AUTH-06 deliberately NOT taken - 05-16 is the
  last claimant, the eleventh consecutive plan in this phase to make the same call: AUTH-05 has no
  route until 05-11 and AUTH-06's 403 cannot be produced over HTTP until 05-12

- [Phase 05-09]: each new schema module joins REQUIRED_SCANNED_MODULES in the commit that CREATES
  it, not in the plan's later gate task - RESEARCH Pitfall 14 states the rule that way, the plan's
  own must_haves repeat it, and every acceptance criterion of the gate task still passes; the only
  thing the split would have bought is two commits in which a presentation module was scanned by
  luck rather than by assertion
- [Phase 05-09]: SecretStr is unwrapped exactly once, in RegisterRequest.to_command, and the test
  asserts `type(command.password) is str` rather than the annotation - the command is a frozen
  dataclass with no runtime check, so forwarding the wrapper would break no contract, no type check
  and no import-linter contract (pydantic is deliberately off the application layer's forbidden
  list); that one assertion is the whole enforcement of Pitfall 7
- [Phase 05-09]: UserSummaryResponse is a SECOND model rather than a reuse of UserResponse, and the
  two member lists differing is the point - ASGN-03 asks for id, name, email in that order, the
  directory publishes no created_at, and a shared model would move the directory's contract
  whenever the profile's moved
- [Phase 05-09]: the three proven-by-absence refusals are one parametrized table, and they were
  FALSIFIED rather than assumed: both task request models were given an assignee_id field by hand
  and the two new rows went red (evidence/05-09-absence-falsification.txt) - an absence assertion
  that has never been driven red is indistinguishable from one asserting nothing
- [Phase 05-09]: requirement ticks AUTH-01/AUTH-02/AUTH-05/ASGN-01/ASGN-02/ASGN-03 deliberately NOT
  taken - 05-16 is the last claimant, the twelfth consecutive plan in this phase to make the same
  call: a schema with no route above it proves no requirement

- [Phase 05-11]: the access token's lifetime joined SecurityResources as a third member, because the
  plan required a provider and none existed - expires_in must describe the lifetime the token was
  actually signed with, and both now come from one builder call rather than from two reads of the
  same setting; dependencies.py still reads no configuration per request (grep -c get_settings
  prints 0), which is the RC-3 property the container exists to keep
- [Phase 05-11]: GET /auth/me publishes a 404 the plan's enumeration (200/401/500) omitted -
  profile.py documents that leg as reachable by a deletion landing between the token check and the
  read, and this package's own rule is that every route declares its full refusal set; an
  undeclared but reachable refusal is the dishonesty the rule exists to prevent
- [Phase 05-11]: login is the one handler in the project that builds its own command - 05-09
  deliberately declared no login schema because the fields arrive through the OAuth2 form object,
  so the rename from the form's username to the command's email happens at that single call site
  and is commented as the exception it is
- [Phase 05-11]: Task 3's red step is a FALSIFICATION rather than a failing-first test - the task's
  only artifact is a test and everything it asserts was built by tasks 1 and 2, so a throwaway
  route with no caller parameter was planted, the partition named it by path and the count test
  read 12 == 16 - 3 (evidence/05-11-open-route-falsification.txt carries both runs)
- [Phase 05-11]: configure_logging() is create_app's FIRST statement, before the settings are
  resolved, and the lifespan was rejected in a comment naming both reasons - the HTTP harness never
  enters the lifespan (ADR-056), so the call would be untested by every test that speaks HTTP, and
  D-06 keeps the startup half empty
- [Phase 05-11]: coverage fell from 100.00% to 99.59% and was left there - the seven uncovered
  statements are the three handler bodies, nothing drives them over HTTP until 05-13, and no pragma
  and no omit entry was added; 05-13 owes the return to 100%
- [Phase 05-11]: requirement ticks AUTH-01/AUTH-02/AUTH-05 deliberately NOT taken - 05-16 is the
  last claimant, the thirteenth consecutive plan in this phase to make the same call: the routes
  exist here, but their behaviour is asserted over HTTP by 05-13

- [Phase 05-12]: DELETE .../assignee declares a 422 the plan's behaviour block excluded - the block
  contradicts itself ('the two assignee operations declare ... 422; the delete declares the same
  minus 422') and the exclusion is wrong on the facts: the verb has no body but two UUID-typed path
  segments, so a malformed identifier is a 422 before any use case runs, exactly as on
  routers/tasks.py's bodiless DELETE
- [Phase 05-12]: the 403 set is asserted by EQUALITY, not containment - a missing 403 is a refusal a
  client was not told about, and a surplus one is a dead branch plus a false claim about what this
  API discloses; the failure message separates 'missing' from 'unexpected', and the four routes in
  routers/tasks.py that must NOT take the leg are named in a comment on the constant itself
- [Phase 05-12]: the nineteen-operation inventory reads the WHOLE document while the eighteen-entry
  versioned one keeps the /api/v1 filter - _api_operations cannot see /health at all, so an
  inventory taken through it would stay green if the health route disappeared; _all_operations was
  added beside it rather than loosening a helper two other tests depend on
- [Phase 05-12]: assignments.py declares TWO APIRouter objects and one register_assignment_routes -
  the assignee verbs are nested under /task-lists and D-02 puts discovery on a flat /tasks, so the
  prefixes differ, and a module still contributes exactly one line to the composition root
- [Phase 05-12]: create_task's docstring said 'Phase 4 declares no assignment endpoint at all',
  which this plan made false; rewritten in place to state D-06 and T-5-10 instead, rather than left
  as a sentence a reader would take for the current design
- [Phase 05-12]: coverage fell from 99.59% to 99.15% and was left there - eight of the fifteen
  uncovered statements are the four new handler bodies, nothing drives them over HTTP until 05-13
  and 05-14, and no pragma and no omit entry was added
- [Phase 05-12]: requirement ticks ASGN-01/ASGN-02/ASGN-03/AUTH-03/AUTH-06/NOTF-01 deliberately NOT
  taken - 05-16 is the last claimant, the fourteenth consecutive plan in this phase to make the same
  call: the routes exist here, but none of the six is asserted over HTTP until 05-13 and 05-15

- [Phase 05-13]: authenticated_client is api_client verbatim minus ONE line, the actor override, and
  its docstring states what the other fixture therefore cannot measure - the 401 legs, the anonymous
  column of the D-04 matrix and the statement counts; its price is that every test using it seeds
  its own caller, because the real dependency confirms the row on every request, which is the
  property under test rather than a setup tax (D-20)
- [Phase 05-13]: the forged tokens are built from Settings(_env_file=None) constructed INSIDE the
  test, never from restated literals - the fixture monkeypatches the same two variables the
  application was built from, so an identical construction yields the identical secret, algorithm
  and lifetime, and each forgery therefore differs from a valid token in exactly one property
- [Phase 05-13]: the expired token needed no freezegun and no sleeping (both greps print 0) - PyJWT
  compares exp against the real time.time(), so only the ISSUING side is controllable, and a real
  SecurityResources built on a clock stopped two hours ago mints a token that expired ninety
  minutes before the request
- [Phase 05-13]: the seven-case table is asserted TWICE - once per case for shape, and once across
  all seven in a single test asserting the set of serialised bodies has exactly one member; each
  parameter runs in its own test, so a leak living in a member no per-case assertion names would
  satisfy every one of them
- [Phase 05-13]: `example.test` is refused by email-validator as a reserved name, so six tests
  failed at the EmailStr boundary before reaching a handler - the registering addresses moved to
  example.com; the suite's existing demo@example.test constants are safe only because they are
  seeded as entities and never cross that boundary
- [Phase 05-13]: expires_in is asserted against configured_settings().jwt_expire_minutes * 60 rather
  than against 1800 - a literal would assert that somebody typed the same number twice, while the
  derivation asserts the property SecurityResources exists for
- [Phase 05-13]: the plan's falsified-sentence rewrite was already done by 05-10 (the grep printed 0
  on arrival); the half genuinely still missing was written instead - acting_as impersonates rather
  than authenticates, so combining it with authenticated_client is a contradiction
- [Phase 05-13]: routers/auth.py and routers/users.py are back at 100%; coverage is 99.66% with SIX
  uncovered statements, all in routers/assignments.py (144-147, 201-204, 249-252), which 05-14 owns
  - no pragma and no omit entry was added
- [Phase 05-13]: requirement ticks AUTH-01..AUTH-05/ASGN-03 deliberately NOT taken - 05-16 is the
  last claimant, the fifteenth consecutive plan in this phase to make the same call
- [Phase 05-14]: no TDD RED was available - 05-08 and 05-12 shipped the behaviour, so every test
  here was green when written; four falsifications were recorded instead (the guard reordered after
  the user lookup, the D-07 early return deleted, AssignTask's commit removed, the owner's write
  path not holding the row), each reverted with git checkout and the suite re-run green
- [Phase 05-14]: a notification's extra= fields are read with vars(record), never with attribute
  access - record.event is a mypy-strict attr-defined error and getattr(record, "event") is four
  flake8-bugbear B009 violations, both observed; __dict__ is also what JsonFormatter itself iterates
- [Phase 05-14]: NOTF-03 is proven by a RE-READ through the API, not by the 200 - removing
  AssignTask's commit() was observed leaving the status code and the response body green while the
  re-read went red, which is exactly the implementation the requirement forbids
- [Phase 05-14]: the statement counts measured on the real authenticated path are 2 and 4 for the
  OWNER (D-11's actor lookup is the new first entry, named in the constant's comment); the
  invariance property is unchanged and the module now says the absolute number is a measurement
- [Phase 05-14]: counts differ by ROLE and it was measured, not inferred - owner GET task 3 SELECTs
  vs assignee 2, owner PATCH .../status 4 SELECTs + 1 UPDATE vs assignee 3 + 1; any future count
  assertion must say whose it is
- [Phase 05-14]: _remove_what_was_committed names both users explicitly - tasks.assignee_id is ON
  DELETE SET NULL, so deleting the owner clears the column and leaves the assignee's users row for
  test_dependencies.py to report as a leak
- [Phase 05-14]: the new concurrency case asserts `waited` LAST, the ordering the module's own
  _until_it_waits_or_finishes docstring asks for - with the lock removed it now fails on the lost
  rename rather than on "nobody waited"
- [Phase 05-14]: routers/assignments.py is back at 100% and the suite's total coverage is 100.00%
  with no pragma and no omit entry - the six statements 05-13 handed over are closed
- [Phase 05-14]: requirement ticks ASGN-01/ASGN-02/NOTF-01/NOTF-02/NOTF-03 deliberately NOT taken -
  05-16 is the last claimant, the sixteenth consecutive plan in this phase to make the same call

- [Phase 05-15]: the matrix's nineteen paths are spelled out in the module instead of imported from
  the five sibling files that own them - this package's strongest convention, set aside on purpose
  because a table assembled from fragments is no longer a table and D-04 reuses this one as Phase 7
  documentation; the coverage test binds every string to app.openapi()["paths"], which is a stronger
  check than agreeing with a helper
- [Phase 05-15]: the four expected statuses are POSITIONAL fields of Row, in the research table's
  own column order, so a row reads across like the markdown it was lifted from; naming each would
  make every entry three lines long and destroy the readability D-04 asks for above all else
- [Phase 05-15]: all 76 cells were right on the FIRST run - the table lifted from 05-RESEARCH.md
  matched the running application exactly, no cell surprised and no production bug was exposed
- [Phase 05-15]: this API has TWO 401 wordings, discovered by the matrix: AuthenticationError.REFUSAL
  for anything to do with a token, and use_cases/auth/login.py's own constant for a rejected
  credential. Both carry code=authentication_failed and the WWW-Authenticate challenge, and the
  difference is deliberate (the exception's own docstring argues it), so the assertion helper was
  split rather than the application changed - any future assertion on a 401 detail must say which
  door it is at
- [Phase 05-15]: the matrix overrides get_engine and nothing else beyond the harness's own - the
  shared client aims at a deliberately fictional DSN and /health is the one row that dials the
  database itself, so row 1 would otherwise have measured 503 against the fixture rather than 200
  against the route
- [Phase 05-15]: the owner is seeded with a REAL Argon2 hash so the login row can log in, computed
  once per session into a module-level dict - the sibling modules' placeholder is not an encoded
  hash and the adapter answers False for it, which would have made the row assert the opposite of
  what it says
- [Phase 05-15]: the cold start ran `up -d --build`, not the plan's bare `up -d` - `down -v` removes
  containers, network and volume but NOT images, and this machine's test-api image predated 05-11
  and 05-12; an evaluator cloning the repository has no image and their plain `up` builds one
- [Phase 05-15]: the capture records the PRE-WIPE state including the old demo row, against the
  plan's "no reference to a demo account" criterion - the criterion's intent is met and observed
  (zero users, no seed line, no INSERT INTO users), and recording what `down -v` destroyed is what
  turns "the volume was empty afterwards" into a change rather than a claim
- [Phase 05-15]: the only redaction in the capture is the two access tokens, each a live thirty-
  minute bearer credential signed with the un-committed .env secret - the T-3-31 argument the
  entrypoint already makes about container logs, applied to a transcript in the repository
- [Phase 05-15]: requirement ticks AUTH-03/AUTH-06/ASGN-02/NOTF-02 deliberately NOT taken - 05-16 is
  the last claimant, the seventeenth consecutive plan in this phase to make the same call
- [Phase 05-16]: DECISION_LOG.md gains TWENTY-FIVE ADRs (059-083), not the plan's enumerated
  fifteen - the fifteen Phase 5 summaries handed forward ten more, and writing only the enumerated
  set would have satisfied the acceptance criterion while pushing the debt into Phase 7; the same
  call 03-11 (21 for 12) and 04-12 (14 for 9) made
- [Phase 05-16]: the log stays append-only mechanically rather than by intention - `git diff
  DECISION_LOG.md | grep -c '^-'` prints 1, the diff header alone - and the three refining entries
  name their predecessors by id: ADR-059 refines ADR-055, ADR-075 refines ADR-045, ADR-076 refines
  ADR-054
- [Phase 05-16]: ADR-066 and ADR-067 are written as concessions in those words. ADR-066 says the
  register 409 is an enumeration oracle AUTH-01 requires and states the bound (the error carries no
  address, GET /users already discloses every address to authenticated callers, so the residual
  leak is to unauthenticated ones); ADR-067 says Argon2's ~25 ms floor is an incidental throttle
  and not a control. Neither is described as mitigated
- [Phase 05-16]: CLAUDE.md § Project Rules records the widened HTTPException AST gate scope (all of
  presentation/api, exempting errors/handlers.py, with REQUIRED_SCANNED_MODULES as the non-vacuity
  guard) and the ADR-058 write-path locking rule, each transcribed from the gate file and naming
  it; the auto_error=True consequence is written beside the first, because that is the shape a
  future agent would otherwise reach for
- [Phase 05-16]: ROADMAP Phase 5 SC-1 amended - it credited "use Swagger's Authorize button
  successfully", which nobody in this project does: no human ran the browser flow and no test
  drives one. It now names the published contract and test_security_scheme.py, the gate that reads
  it. The Phase 2 SC-1 / Phase 3 SC-4 / Phase 4 SC-5 precedent; the other four criteria were
  re-read and are accurate as written
- [Phase 05-16]: all twelve requirement ticks taken (AUTH-01..06, ASGN-01..03, NOTF-01..03), each
  re-verified by running its command inside the gate capture rather than inherited from a plan
  header, after fifteen consecutive plans deferred them
- [Phase 05-16]: the phase is deliberately NOT marked complete - the ROADMAP phase checkbox, the
  Progress table's status cell and its completion date are the orchestrator's after verification;
  only the sixteenth plan box and the 16/16 count were taken here
- [Phase 05-16]: STATE.md and ROADMAP.md were updated by hand in their existing conventions rather
  than through the SDK state handlers, as every plan in this phase did, because those handlers
  regressed both files in all sixteen plans (a phase-based percent, a reset Status line, injected
  blank lines, a blanked progress row, a bogus `[Phase ?]:` decision prefix)

- [Phase 05-17]: the local `.env` was repaired with `make env` and the container rebuilt onto a
  generated secret BEFORE the refusal landed - `tests/integration/conftest.py`'s `database_url`
  fixture is the one place in the suite that builds `Settings()` from the real on-disk file, so
  the reverse order would have left the whole suite, and the pre-commit hook that runs it, red
  between two commits with `--no-verify` forbidden
- [Phase 05-17]: the refusal is a PREFIX rule (`replace-me`) and ADR-084 says what it does not
  do: an operator's own weak 32-character secret is not protected, and no code default was
  introduced - the generated value exists only in an untracked `.env`
- [Phase 05-17]: `make env` generates on the HOST rather than in the entrypoint; an entrypoint
  generator would mint a new secret on every container start and invalidate every live token,
  which is a different defect rather than a fix
- [Phase 05-17]: `is_storable_text` is a public domain predicate and the single home of the rule;
  `_refuse_unstorable` (renamed from `_refuse_nul`) returns early when it answers yes and only
  then picks between two messages, so the guard and the predicate cannot drift, and `Login` asks
  the same question about a submitted address without importing an exception
- [Phase 05-17]: the login guard runs BEFORE the unit of work, and the test asserts
  `rollbacks == 0` to prove it - the unknown-address leg leaves it at 1, so the assertion
  distinguishes a guard in front of the block from one inside it
- [Phase 05-17]: the engine test reads `hide_parameters` off the real engine and passes that flag
  into the `DBAPIError` it renders, rather than hardcoding `True`, so removing the option from
  `create_engine` fails the test instead of leaving it asserting about a literal
- [Phase 05-17]: STATE.md and ROADMAP.md were again updated by hand for the reason 05-16 records;
  the ROADMAP Phase 5 checkbox, its status cell and its completion date are still untouched -
  only the seventeenth plan box and the 17/17 count were taken here

### Pending Todos

[From .planning/todos/pending/ — ideas captured during sessions]

None yet.

### Blockers/Concerns

[Issues that affect future work]

- Both research flags are now discharged. Phase 5 (JWT/hashing libraries, the 403-vs-404
  matrix) was planned with `/gsd:plan-phase --research-phase`; `05-RESEARCH.md` resolved it,
  and three of its findings changed the shape of the plan (the bearer scheme that raises no
  `HTTPException`, the INFO line uvicorn was dropping entirely, and D-11's statement-count
  consequence being conditional on the harness). The same flag on Phase 3 (async session
  lifecycle, transactional test fixtures, Alembic `env.py`) was discharged in that phase.

- `DECISION_LOG.md` ADR-019 still claims "the workflow has never run on a real runner", which
  has been false since plan 01-08 (CI run 35301518310 concluded success on the first attempt).
  The log is append-only, so Phase 7 owns the superseding entry.

- `AI_WORKFLOW.md` must be appended to at the end of every phase; reconstructing it in Phase 7
  would undermine the project's own thesis.

- Phase 6 (TEST-03): `make test` and `make docker-test` report different coverage for the same suite. **Re-measured by plan 05-16 on the closing gate: the same 998 tests give host 100.00% over 1619 statements and container 99.06% over 1772, with 18 missed.** The Phase 4 figures were host 100.00% over 1155 vs container 99.20% over 1267 with 11 missed, and Phase 3's were 730 vs 772 - so the divergence is pre-existing and has widened with the number of route handlers. The statement-count gap is PEP 649 (Python 3.14 host vs 3.13 image), and the 18 missed lines are again the trailing statements of route handlers - `routers/assignments.py` 147/204/252, `routers/auth.py` 152-153/234, `routers/task_lists.py` 161-164/197/226/260, `routers/tasks.py` 170-173/218/251/292/366, `routers/users.py` 99 - every one of which the integration suite drives over HTTP and the host run reports covered. Both runs are in `.planning/phases/05-auth-assignment-notifications/evidence/05-16-phase-gate.txt`. Phase 6 owns TEST-03 and should pin both runs to one measurement rather than argue the number down; no pragma and no omit.

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| *(none)* | | | |

## Session Continuity

Last session: 2026-09-19T20:06:05.418Z
Stopped at: Phase 6 context gathered
Resume file: .planning/phases/06-test-hardening-coverage/06-CONTEXT.md
