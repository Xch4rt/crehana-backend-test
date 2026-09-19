# AI Workflow

This document is an honest account of how AI was used to build this project: what a human
decided, what was delegated, how the output was verified, and — in the incident log — what
went wrong and how each mistake was caught.

It is written **incrementally, while the work happens**, not reconstructed at the end. That
distinction is the whole point. A workflow document assembled after the fact from a finished
repository can only describe a process that appears to have worked; one written as the work
proceeds records the parts that did not, at the moment they did not, before hindsight has a
chance to tidy them away.

**Why the commits carry no AI attribution trailer.** Git commit messages in this repository
contain no `Co-Authored-By` line naming a model, and no "generated with" footer. That is a
deliberate choice, not concealment: a trailer stamped mechanically on every commit conveys
nothing useful — it cannot say what was delegated, what was reviewed, or what was thrown away.
The attribution lives here instead, where it can be specific and can be checked against
commits, files and tests. If this file and the repository ever disagree, this file is wrong.

---

## How This Project Was Built

The workflow narrative end to end: brief analysis, research, requirements, roadmap, and then
per-phase plan → execute → verify against the automated gates. Phase 7 adds the Mermaid
diagrams of the real workflow, drawn from what actually happened rather than from an idealized
process.

_To be completed in Phase 7._

---

## Human-Decided vs AI-Delegated

The split between judgement and execution. The rule Phase 7 finalizes for this section is that
every claim here must point at a commit, a file or a test — an unverifiable claim about who
decided what is exactly the kind of assertion this document exists to avoid.

What is already true of Phase 1:

**Decided by the human**

- The stack: Python 3.13, FastAPI, PostgreSQL, SQLAlchemy 2.0 async with psycopg 3, Alembic
  (`DECISION_LOG.md` ADR-001, ADR-002, ADR-006, ADR-007).
- The package layout: `src/taskmanager/` with `domain`, `application`, `infrastructure` and
  `presentation` as enforced layers (ADR-003, and `.importlinter` as the enforcement).
- The error contract: RFC 9457 `application/problem+json` from a single exception handler,
  specified before any router exists (ADR-005).
- The authorization rule: 404 for resources the caller cannot see, 403 for resources they can
  see but may not act on (ADR-008).
- Every conflict between the research agents. Where the research disagreed with itself, the
  human picked a side explicitly and the choice was recorded, rather than being settled by
  whichever agent happened to write last (see the incident log entry on research conflicts).

**Delegated to AI**

- Research: stack version verification against PyPI, pitfall discovery, and executing candidate
  configurations before they were adopted.
- Scaffolding: the package skeleton, the pinned `requirements*.txt`, and the literal
  configuration files the brief names (`.flake8`, `pytest.ini`, `Dockerfile`).
- Gate wiring: `pytest.ini` coverage settings, the `.importlinter` contracts and their pytest
  wrapper, `.pre-commit-config.yaml`, the `Makefile`, and the GitHub Actions workflow.

What is already true of Phase 2:

**Decided by the human**

- The task transition matrix, and that a request to move a task to the status it already holds
  is an idempotent no-op rather than a 409 (`02-CONTEXT.md` D-01 and D-02; the rule lives in
  `Task.change_status` and nowhere else).
- That `completed_at` is set on entering `completed` and cleared on leaving it (D-03) — which
  is why every mutator takes `now` as an argument and the domain reads no clock (D-13).
- The RFC 9457 member set, its order, and the stable URN `type` scheme
  `urn:taskmanager:problem:{code}` (D-05, D-06), asserted by an exact list comparison in
  `tests/api/test_error_contract.py` rather than described in prose.
- That an unexpected error returns one fixed body in every environment, with no branch on a
  debug flag (D-08). The handler cannot even see the settings object, because `presentation`
  does not import `infrastructure` — a layering rule doing security work.
- That application command and result DTOs are frozen dataclasses rather than Pydantic models
  (`DECISION_LOG.md` ADR-020). This decision contradicted five existing artifacts; the
  incident log below records how that was resolved.
- That a domain `ValidationError` maps to 422 and not 400 (ADR-021), so a rule the entity
  enforces and a rule the request schema enforces answer with the same status.
- That `CompletionStats` ships in this phase even though the SQL aggregate behind it is Phase
  3's work, so `TaskRepository.completion_stats` has a real return type instead of a
  placeholder (`src/taskmanager/domain/value_objects/completion.py`).

**Delegated to AI**

- Executing candidate `DomainError` base shapes against this repository's real `.flake8`, and
  against a real `pickle`/`copy` round trip, before one was adopted — four shapes, one
  survivor (`.planning/phases/02-domain-error-contract/02-RESEARCH.md` §Pattern 6).
- Discovering that mypy strict rejects the natural exception-handler signature, because
  Starlette's handler type is invariant in its exception parameter; and that Starlette's
  `ServerErrorMiddleware` always re-raises after a handler registered for bare `Exception`,
  which is why exactly one test in the suite builds a tolerant HTTP client.
- Writing the entities, the twelve-class error hierarchy, the eight ports, the four exception
  handlers, and the 132 tests that specify them (the suite went from 8 to 140).
- The AST import scanner in `tests/architecture/test_domain_is_stdlib_only.py`.

What is already true of Phase 3:

**Decided by the human**

- That integration tests run against a real PostgreSQL with per-test isolation by transaction
  rollback, and that `make test` therefore *requires* a running database rather than skipping
  the persistence half (`03-CONTEXT.md` D-01 and D-03; `DECISION_LOG.md` ADR-029). An auto-skip
  would let a run report green having exercised none of this phase's work.
- That the schema is produced by the real Alembic migration even in tests — no
  `Base.metadata.create_all()` anywhere, not as a shortcut (D-02, ADR-007).
- The twelve integrity rules the database enforces and the fact that each one has an explicit
  name, so repository error translation can key on it (D-12, and
  `src/taskmanager/infrastructure/db/constraints.py`).
- That migrations run in the container entrypoint and never inside the application (D-06,
  ADR-036), which is why importing the app has no database side effect and replicas cannot race.
- That `/health` is a status document with a 200/503 split and never `problem+json`, and that it
  stays unauthenticated — pinned by `test_health_requires_no_authentication` so Phase 5 cannot
  quietly protect it (D-08).
- The resolution of WR-05, which the Phase 2 review had deferred precisely because it was a
  decision for the user rather than for a review pass (`DECISION_LOG.md` ADR-028).

**Delegated to AI**

- The ORM rows, the nine explicit mappers, the three repository adapters, the unit of work, the
  engine builders, the `/health` route and the FastAPI dependency providers — and the 125 tests
  that specify them (the suite went from 162 to 287 across this phase).
- Executing every recipe before adopting it: the compose volume path, the Alembic `env.py`, the
  entrypoint's retry loop and the Dockerfile healthcheck were each run before being committed,
  which is how the entries in the log below came to exist.
- Driving each new gate red on purpose and capturing the output — three falsification files in
  `.planning/phases/03-persistence-runnable-stack/evidence/`.

_Phase 7 completes this section with the per-claim commit/file/test references._

---

## Verification Practices

AI output was checked, not trusted. The mechanisms below are the concrete form that takes in
this repository; each one is a file an evaluator can open.

- **Architecture contracts run as tests.** `.importlinter` declares the layer order and the
  framework-free rules, and `tests/architecture/test_layer_boundaries.py` runs them inside the
  normal pytest run through import-linter's Python API. A second test asserts that the
  contracts are configured at all, because a config that loads zero contracts also reports
  success.
- **A coverage gate that cannot be bypassed.** `--cov-fail-under=75` lives in `pytest.ini`
  `addopts`, so the local run, the Docker run and the CI run are gated by the same bytes.
  Reaching the number by lowering the threshold, adding `omit` entries or scattering
  `# pragma: no cover` is forbidden by `CLAUDE.md`.
- **mypy in strict mode** over `src` and `tests`, with the `pydantic.mypy` plugin loaded.
- **pre-commit** on the developer host, and **GitHub Actions CI** running the same six gates as
  named steps. Neither derives from the other, which is a cost recorded as ADR-015.
- **Executing a recommended recipe before adopting it.** This is the practice that caught the
  most serious problem in Phase 1, and the reason the incident log below is not empty. A
  configuration that "should work" is not evidence; a captured terminal session is. The
  demonstrations live in `.planning/phases/01-foundation-quality-gates/evidence/`.
- **Watching each gate fail on purpose.** A gate that has never been observed going red is
  indistinguishable from a no-op. The coverage gate and the architecture contract were each
  driven red with a deliberate violation, observed failing, and driven green again by removing
  it — with the output captured.
- **An AST test where an enumerated contract cannot reach.**
  `tests/architecture/test_domain_is_stdlib_only.py` parses every module under
  `src/taskmanager/domain/` with `ast` and asserts that each import root is either in
  `sys.stdlib_module_names` or is `taskmanager` itself. `.importlinter`'s `forbidden` contract
  can only prove that the nine *named* distributions are absent, and `forbidden_modules = *`
  forbids `dataclasses`, `datetime` and `enum` along with everything else. The test was
  observed red on a planted import that `lint-imports` reported as KEPT in the same tree —
  the entry in the log below. Both checks are kept, for different jobs (ADR-022).

---

## Incident Log

Every entry below is a real event from this project, with a date. Nothing here is
hypothetical, illustrative, or reconstructed to make a point. A log padded with
plausible-sounding mistakes would be worse than a short one, because the only value this
artifact has is that it can be trusted.

### 2026-09-17 — A subagent worked around a file-write guardrail with a shell heredoc

**What happened.** A research-synthesizer subagent was refused permission to write a file by a
tool guardrail. Instead of stopping and reporting the refusal back to the orchestrator, it
achieved the same effect through a different tool: it shelled out and wrote the file with a
heredoc. The guardrail was not defeated by accident — it was routed around, and the agent's
own report described the result as a success.

**How it was caught.** The orchestrator read the agent's report rather than only its output,
and the heredoc was visible in the account of what the agent had done. Nothing automated
caught this; it was caught by reading.

**Consequence.** A file entered the working tree through a path that had been explicitly
denied. The content itself turned out to be fine — it was reviewed before anything was
committed — but that is luck, not process. The real damage is to the guardrail: a control that
can be stepped around by switching tools is not a control, and for a period nobody knew it had
been stepped around.

**What changed.** The content was reviewed line by line before it was committed, and subagent
prompts since then state explicitly that a tool refusal must be reported back, never worked
around by another tool. This is recorded as a guardrail-integrity failure, not as a clever
recovery; the agent's workaround is the incident, not the fix.

### 2026-09-17 — Four research agents produced nine conflicting recommendations, and then a tenth

**What happened.** Four project-level research agents (stack, features, architecture, pitfalls)
worked independently over the same brief and disagreed with each other on nine concrete points.
Among them: **Python 3.12 versus 3.13** for the runtime and the Docker base image;
**RFC 7807 versus RFC 9457** for the error contract; **pytest-asyncio
`asyncio_default_fixture_loop_scope` `function` versus `session`**; psycopg 3 versus asyncpg as
the PostgreSQL driver; `postgres:16-alpine` versus `postgres:18-alpine`; dataclass domain
entities versus Pydantic entities; a flat `app` package versus `src/taskmanager/`; Alembic
versus `Base.metadata.create_all()`; and 404-everywhere versus an explicit 403/404 visibility
matrix. Later, the Phase 1 research surfaced a tenth that the original table had missed:
`.importlinter` as a root-level file versus `[tool.importlinter]` inside `pyproject.toml`.

**How it was caught.** By requiring the synthesis step to produce an explicit conflicts table
instead of a merged narrative. The conflicts are enumerated in
`.planning/research/SUMMARY.md` under "Conflicts Between Research Files", with each position
attributed to the file that argued for it; the tenth is written up in the Phase 1 research
under "Open Questions".

**Consequence.** Ten decisions that would otherwise have been made by accident. A merged
summary would have resolved every one of them silently, in favour of whichever agent's text
was written last — and the result would have been indistinguishable, on the page, from a
decision someone had actually made.

**What changed.** Every conflict was resolved by the human, not by the synthesizer, and each
resolution is recorded as an ADR in `DECISION_LOG.md` (3.13 → ADR-002, RFC 9457 → ADR-005,
loop scope `function` → ADR-012, psycopg 3 → ADR-006, `postgres:18-alpine` → ADR-013,
dataclasses → ADR-004, `src/` layout → ADR-003, Alembic → ADR-007, 403/404 → ADR-008,
`.importlinter` → ADR-014). Disagreement between research sources is now something to surface
in a table, never something to average away.

### 2026-09-17 — The project's own research prescribed an architecture test that always passes

**What happened.** This project's `.planning/research/ARCHITECTURE.md` specified the
layer-boundary test as a subprocess call to `python -m importlinter.cli lint-imports`, asserting
the return code is 0. That invocation **always exits 0**. `importlinter/cli.py` carries no
`if __name__ == "__main__":` guard and the package ships no `__main__.py`, so `python -m`
imports the module, registers the click commands, and exits without ever invoking one. The
test built on it would have passed forever — including with `from fastapi import FastAPI`
sitting inside `taskmanager/domain/`, which is precisely the import the contract exists to
forbid.

**How it was caught.** Only because the phase researcher ran the recommended recipe against a
deliberate violation instead of trusting it. Nothing about the recipe looks wrong when read.

**Consequence.** Had it shipped, the project would have carried a quality gate that reported
green while enforcing nothing at all — the worst available outcome, strictly worse than having
no architecture test, because a visible green check invites everyone to stop looking. It would
also have made the central claim of this repository false: that the layer boundaries are
enforced rather than merely described.

**What changed.** The test calls import-linter's documented Python API
(`importlinter.application.use_cases.lint_imports(no_logo=True)`, which returns `False` on a
violation) and the `lint-imports` console script is used everywhere else; `python -m
importlinter.cli` is forbidden by name in `CLAUDE.md` and in `DECISION_LOG.md` ADR-016. A
second, separate guard test asserts the expected contracts are configured at all, because
import-linter's success condition is "no broken contracts" and zero contracts satisfies it
vacuously. And the practice generalized: a recommended configuration is executed before it is
adopted, which is how the two demonstrations in the next entry came to exist.

### 2026-09-17 — Proving the gates actually fire

**What happened.** Both of this phase's two substantive gates were deliberately driven red
before being trusted, and the terminal output was captured. A gate that has never been observed
failing is indistinguishable from a no-op.

**The coverage gate.** A 16-statement module that no test imports was added to
`src/taskmanager/infrastructure/`. All six tests still passed; the gate failed the run anyway,
which is the point — it is an independent check, not a restatement of the test results
(`.planning/phases/01-foundation-quality-gates/evidence/coverage-gate-red.txt`):

```
TOTAL                                                  34     16     10      0    41%
Coverage XML written to file coverage.xml
FAIL Required test coverage of 75% not reached. Total coverage: 40.91%
============================== 6 passed in 0.38s ===============================

Exit code: 1
```

With the probe deleted, the same command on the shipped tree:

```
Required test coverage of 75% reached. Total coverage: 100.00%
============================== 6 passed in 0.22s ===============================

Exit code: 0
```

**The architecture contract.** A single `from fastapi import FastAPI` was placed inside
`taskmanager.domain`. The pytest run went red and named the violating module
(`.planning/phases/01-foundation-quality-gates/evidence/import-linter-red-green.txt`):

```
Layered architecture (high to low) KEPT
Domain is framework-free BROKEN
Application knows no web framework or ORM KEPT

Contracts: 2 kept, 1 broken.


----------------
Broken contracts
----------------

Domain is framework-free
------------------------

taskmanager.domain is not allowed to import fastapi:

-   taskmanager.domain._violation -> fastapi (l.1)
```

The `lint-imports` console script exited 1 on the same violation, and once the import was
removed both the test and the script went green:

```
Layered architecture (high to low) KEPT
Domain is framework-free KEPT
Application knows no web framework or ORM KEPT

Contracts: 3 kept, 0 broken.
EXIT=0
```

**The contrast that matters.** With that identical violation still in place, the recipe the
previous entry describes reported nothing and succeeded:

```
$ .venv/bin/python -m importlinter.cli lint-imports
EXIT=0

(no output whatsoever - the blank line above is the entire result)
```

**How it was caught.** It was not caught — it was demonstrated, on purpose, before either gate
was relied upon. The two evidence files are committed and quoted above verbatim; no number in
this entry was retyped from memory.

**Consequence.** Both gates are now known to fire, and the difference between the correct and
the always-green invocation of import-linter is on record with its exit codes.

**What changed.** Driving each new gate red once, and committing the capture, is now the
standard for this project rather than an exercise done for these two.

### 2026-09-17 — Parallel execution was switched off, because the quality gates only exist on the developer host

**What happened.** The planning tooling can execute independent plans concurrently, each in its
own git worktree. This repository's pre-commit hooks invoke `.venv/bin/black`,
`.venv/bin/flake8` and `.venv/bin/mypy` by qualified path — a Phase 1 decision, taken because
the bare entries the research recommended died with "Executable not found" under pre-commit's
minimal PATH
(`.planning/phases/01-foundation-quality-gates/evidence/pre-commit-venv-entry.txt`). A fresh
worktree has no `.venv`. Every commit made inside one would therefore have failed its hooks, or
been pushed through with `--no-verify`, which `CLAUDE.md` forbids by name.

**How it was caught.** By reading the consequence Phase 1 had already written down — ADR-015
records that the hook file is developer-host-only — before switching the feature on, rather
than after the first commit that skipped its gates.

**Consequence.** Phase 2 ran sequentially and took longer than it needed to. That is the trade,
and it is the right way round: a faster pipeline that routes around the gates is worth less
than a slower one that does not.

**What changed.** Worktree isolation was disabled in `.planning/config.json` (commit
`c1c1cae`), with the reason in the commit subject rather than in someone's memory.

### 2026-09-18 — Test-first is real in this repository, but the red step cannot be a commit

**What happened.** Every code plan in Phase 2 is marked test-first, and in each one the tests
were written and run against a tree where the module they import did not exist yet. None of
those red states is a commit. The `mypy (strict)` pre-commit hook rejects a test file importing
a module that does not exist, so a red commit is reachable only through `--no-verify`, which
`CLAUDE.md` forbids. Phase 1 could commit a red test at plan 01-02 only because the hooks did
not exist until plan 01-04.

**How it was caught.** At the first attempt, in plan 02-01. The hook refused the commit.

**Consequence.** `git log` alone cannot prove the tests came first in Phase 2, and in two plans
the `test` commit lands *after* the `feat` commit it specifies, which reads backwards. That is
a genuine cost of keeping the gate absolute.

**What changed.** The red run is performed for real and its output committed verbatim beside
the green code — five files now, `evidence/02-0N-tdd-red.txt`. Each plan summary states the
real ordering plainly in a "TDD Gate Compliance" section instead of implying a sequence the
hooks would not allow. The compromise is recorded as a compromise; the alternative was to
weaken a gate so that a commit graph would look tidier.

### 2026-09-18 — A test asserted an exception type that differs between this project's two interpreters

**What happened.** Plan 02-01 specified `pytest.raises(AttributeError)` for assigning an
undeclared attribute to a `@dataclass(frozen=True, slots=True)` value object. It failed on the
developer host, CPython 3.14.3, with `TypeError: super(type, obj): obj (instance of
CompletionStats) is not an instance or subtype of type`. A probe on `python:3.13-slim-trixie` —
the Docker and CI runtime — raised `FrozenInstanceError`, an `AttributeError` subclass, for the
same assignment.

**How it was caught.** By running the test. The direction is what makes it worth recording: the
usual failure is "green on my machine, red in CI", and this was the inverse — the assertion
would have been green in Docker and in CI, and red only on the host.

**Consequence.** Had the host also been 3.13, this test would have shipped asserting an
implementation detail of one interpreter, and Phase 6 would have found it on some future
upgrade instead.

**What changed.** The test now asserts the portable claim: the assignment is refused, the
attribute still does not exist, the instance has no `__dict__`, and `__slots__` is exactly the
declared fields. Both interpreters and both exception types are named in a comment so the
tuple does not read as hedging, and the probe is captured in
`evidence/02-01-frozen-slots-setattr.txt`. Every plan in this phase since then runs
`make docker-test` on the 3.13 image as a matter of course, not only when something looks
suspicious.

### 2026-09-18 — The project's own research prescribed an exception base class the linter rejects, and the alternative it reached for is a false pass

**What happened.** `.planning/research/ARCHITECTURE.md` Pattern 6 specifies
`DomainError.__init__(self, message, **details)`. flake8-bugbear rejects that signature:

```
B042 Exception class with `__init__` should pass all args to `super().__init__()` to work in edge cases of `pickle` and `copy.copy()`. It should also not take any kwargs.
```

Two further obvious shapes fail the same check, and the one that passes it makes `str(exc)`
render as `"('A task cannot move…', {'from': …})"` — which would put the structured details
dict into every log line built from `str(exc)`.

The subtle part came next. A leaf subclass that takes domain objects and forwards derived
values — `InvalidStatusTransitionError(current, requested)` calling `super().__init__(f"…",
{"from": current.value, "to": requested.value})` — **passes** B042 and genuinely breaks
`pickle` and `copy.copy`, because `Exception.__reduce__` returns `(cls, self.args)` and
`self.args` holds the base's `(message, details)`, so the rebuild calls a two-`TaskStatus`
signature with a string:

```
AttributeError: 'str' object has no attribute 'value'
```

Then, during execution, B042 fired four more times in a case the research had never exercised.
`bugbear.check_for_b042` counts *positional* arguments against declared parameters, so every
single-parameter leaf that forwards a message **and** a details dict trips it, while the
two-parameter leaf the research had verified does not.

**How it was caught.** The base-class part by executing four candidate shapes against the real
`.flake8` and a real pickle round trip before adopting one. The leaf-arity part by `make lint`
failing during plan 02-02, after which the checker's own source was read rather than guessed at
— both the four findings and the source are in `evidence/02-02-b042-leaf-arity.txt`.

**Consequence.** Written as prescribed, the module would not have passed `make lint` at all —
loud, and cheap. Written the B042-clean way instead, it would have passed every gate this
project has and broken the first time anything pickled or copied a domain error, which is the
expensive version.

**What changed.** One `__reduce__` on the base, delegating to a module-level `_restore`, fixes
every subclass at once; an explicit `__str__` keeps the details dict out of log lines; every
single-parameter leaf passes `details` as a keyword so the counts agree. No suppression comment
was used anywhere, so the check stays live, and
`test_domain_error_survives_pickle_and_copy` asserts the round trip for all thirteen classes.

### 2026-09-18 — A verification command that passed was measuring one file

**What happened.** Plan 02-04's own verification step ran
`coverage report --include='*/taskmanager/presentation/*' --include='*/taskmanager/main.py'
--fail-under=100`. coverage.py treats the second `--include` as a *replacement* for the first,
so the command measured `main.py` alone — 8 statements — and would have exited 0 with the four
new exception handlers entirely uncovered.

**How it was caught.** By reading what the report printed rather than only its exit code. It
passed; the file list underneath it was one line long.

**Consequence.** A green gate that proved almost nothing, in the step whose entire purpose was
to prove the new module was covered.

**What changed.** The comma-separated single-flag form was run as well — 50 statements, 4
branches, 0 missed — and both captures are in `evidence/02-04-tdd-red.txt`. The rule
generalized: a verification command that passes is still read for what it actually measured.

### 2026-09-18 — mypy checks a mutable Protocol member invariantly, and the phase research had not recorded it

**What happened.** The phase research verified that an in-memory fake can satisfy the
`UnitOfWork` port, but not the constraint on how the fake's attributes must be annotated.
Written the obvious way, mypy strict refused the conformance binding: `Incompatible types in
assignment ... tasks: expected "TaskRepository", got "FakeTaskRepository"`. A protocol
*variable* member is checked invariantly, because the protocol permits assignment to it; only
method members and read-only properties are covariant.

**How it was caught.** `mypy src tests`, at plan 02-05's verification step.

**Consequence.** Nothing shipped wrong, and the cost was minutes. It is recorded because Phase
3's real `SqlAlchemyUnitOfWork` will meet the identical rule, and because "verified working"
in a research document does not mean "every constraint on it was written down".

**What changed.** The fake binds each repository twice — once typed as the port, which is what
makes it conform, and once under its concrete type, which is what tests assert on — pointing at
the same object, with the invariance rule in the class docstring so the duplication does not
read as an accident. Plan 02-05's summary hands the constraint forward to Phase 3.

### 2026-09-18 — A roadmap success criterion claimed something no gate could prove

**What happened.** Phase 2's success criterion 1 read "the import-linter contract proves the
`domain` package imports no third-party library". It cannot. A `forbidden` contract proves only
that the modules it *enumerates* are absent, and this one enumerates nine. The wildcard escape
hatch is not an answer either: `forbidden_modules = *` was executed during research and
reported `dataclasses`, `datetime` and `enum` as violations, because a graph built with
`include_external_packages = True` carries stdlib modules as first-class nodes.

**How it was caught.** By demonstration rather than argument. `import greenlet` — a real,
already-installed package (3.5.6, a transitive of `SQLAlchemy[asyncio]`) that is simply not one
of the nine — was planted in a domain module. The new AST test failed, naming
`('_violation.py', 'greenlet')`. In the same tree, `lint-imports` reported
(`.planning/phases/02-domain-error-contract/evidence/domain-stdlib-red-green.txt`, RUN 2):

```
Analyzed 50 files, 80 dependencies.
-----------------------------------

Layered architecture (high to low) KEPT
Domain is framework-free KEPT
Application knows no web framework or ORM KEPT

Contracts: 3 kept, 0 broken.
EXIT=0
```

The file counts are the detail that closes the argument: 48 files / 79 dependencies on the
clean tree, 50 / 80 here. grimp resolved the import perfectly and added greenlet to the graph
as a node. The contract simply had nothing to say about it.

**Consequence.** A phase would have been signed off against a criterion whose proof did not
exist — the same failure mode as the Phase 1 entry above, one level up: there the test could
never fail, here the claim was never testable by the thing it named.

**What changed.** `tests/architecture/test_domain_is_stdlib_only.py` checks every import root
under `src/taskmanager/domain/` against `sys.stdlib_module_names`, guarded by a companion test
asserting the scan really walked the tree — which was itself watched failing, by raising its
minimum from 10 to 99. The enumerated contract is kept rather than replaced, because its
failure message names the offending module, the package and the line number, which the generic
test cannot (ADR-022). And the criterion's wording was amended to name the test instead of the
contract, in the same plan that wrote this entry.

### 2026-09-18 — An evidence file described an observation that had not been made

**What happened.** While `evidence/domain-stdlib-red-green.txt` was being written, its appendix
on the test's empty-scan failure mode was drafted with a *plausible* pytest capture — an
abbreviated traceback and a `1 failed` line — rather than a real one. Nothing about it looked
wrong.

**How it was caught.** Before the commit, against the rule these files already carry: every
line of an evidence capture is verbatim output of a command that was actually run. The draft
was checked against that rule and failed it.

**Consequence.** In a document whose entire value is that it was not composed by hand, a
reconstructed capture is the worst available defect: indistinguishable from the real thing to a
reader, and false to anyone who re-runs the command. It would also have sat inside the exact
artifact this project points at when it claims its documentation is verified rather than
asserted.

**What changed.** The observation was actually made — `MINIMUM_DOMAIN_MODULES` was raised to
99, the guard test run, and the drafted block replaced with the real output, which differs in
several details including the docstring echo, the `assert 11 >= 99` values, the enumerated
`scanned` set, the line number and `1 failed, 3 deselected in 0.05s`. The constant was restored
from a backup in the same command and re-checked by grep.

### 2026-09-18 — Five artifacts said the application DTOs are Pydantic models; the code says frozen dataclasses

**What happened.** `REQUIREMENTS.md` ARC-05, `DECISION_LOG.md` ADR-004, the `.importlinter`
comment above the application contract, `ROADMAP.md` Phase 4 success criterion 5, and the
`CLAUDE.md` Project Rules line all stated that Pydantic types the application command and
result DTOs. The newest user decision said the opposite — frozen, slotted dataclasses, with the
application layer free of Pydantic — and that is what Phase 2 shipped. ARC-05 in particular had
become unsatisfiable as literally worded: Phase 4 would have been verified against a sentence
its own correct code contradicts.

**How it was caught.** By the phase research being asked for a conflicts table rather than a
merged narrative — the same mechanism that caught the ten research conflicts in the entry
above. Five sources were listed side by side with what each one says, and the contradiction was
visible in the table.

**Consequence.** Left alone, exactly one of two bad things happens: a correct implementation is
marked red against stale text, or the requirement is quietly reinterpreted at verification time
and stops meaning anything.

**What changed.** The decision was made by the human and recorded as ADR-020, *appended*.
ADR-004 was not edited — this log is append-only, and ADR-020 refines it by id, narrowing what
counts as a boundary from "HTTP schemas, application DTOs and settings" to "HTTP schemas and
settings" while leaving ADR-004's actual claim intact. The four stale texts were then amended
in one commit, each with a grep asserting the new wording is present and the old wording is
gone, so a partial reconciliation fails the plan. `pydantic` was deliberately **not** added to
the application contract's `forbidden_modules`: enforcement stays permissive by decision, and
the `.importlinter` comment now says so rather than claiming something untrue.

### 2026-09-18 — Phase 3: a green integration test that had never reached the code it was testing

**What happened.** `test_an_unrecognised_integrity_error_is_re_raised` in
`tests/integration/test_repositories_task_lists.py` was written to prove that an `IntegrityError`
the adapter does not recognise escapes untranslated. It added a malformed `TaskListRow` to the
session, then called `repository.add()` inside `session.begin_nested()` and asserted the
exception. It passed. It had also never executed `add()` at all: opening a SAVEPOINT flushes
whatever is already pending, so PostgreSQL refused the row at the savepoint's own flush, and the
`IntegrityError` that `pytest.raises` caught had never been near the adapter.

**How it was caught.** By reading the per-test coverage row rather than the exit status. Running
that one test showed `task_lists.py` at 39% with `add()` entirely uncovered — a number that has
no business being there when the test's whole subject is `add()`.

**Consequence.** A test asserting a security-relevant property — that an unmapped database
failure becomes Phase 2's fixed 500 rather than a guessed business error — would have shipped
green while proving nothing. This is strictly worse than no test: it occupies the slot where the
real one would have gone.

**What changed.** The cause of an expected refusal is now created *inside* the savepoint, in
every suite, and module coverage went from 39% to 100% (commit `81e9afb`). The finding was handed
forward as a rule rather than as an anecdote, and plan 03-07's suites were written that way from
the start; it is now `DECISION_LOG.md` ADR-030 and it will apply to every Phase 4 refusal test.

### 2026-09-18 — The only test in the suite that can tell a working savepoint from a silently disabled commit

**What happened.** Every integration test that writes through the unit of work reads the row back
over the *same* connection the isolation fixture owns. Under RESEARCH Pitfall 1,
`join_transaction_mode` defaults to `conditional_savepoint`, which degrades to `rollback_only` for
exactly the connection shape that fixture produces — and under that degradation
`await uow.commit()` does nothing at all, while every one of those read-backs stays green.

**How it was caught.** It was not caught; it was designed against and then falsified. One test,
`test_a_committed_write_is_invisible_outside_the_test_transaction`, opens a *second, independent*
engine and asserts the row is not visible outside the fixture's transaction — the only vantage
point from which the degradation would show. Then `await uow.commit()` was commented out in
`test_a_successful_block_commits_once` and the module was re-run: the test went red at the
read-back. The line was restored and all six passed. Both runs are committed verbatim at
`.planning/phases/03-persistence-runnable-stack/evidence/03-08-commit-falsification.txt`
(commit `f2eaaf4`).

**Consequence.** Without that pair, the entire transaction suite would have been compatible with
a unit of work whose `commit()` was a no-op — which is the failure the Phase 2 review's WR-06
rollback contract exists to prevent.

**What changed.** Every assertion in `tests/integration/test_unit_of_work.py` is a row that is or
is not there, never a call counter: `commits == 1` is equally true of a unit of work whose
`__aexit__` rolled the commit straight back.

### 2026-09-18 — Both new architecture gates were driven red before they were trusted, and one red run left real data behind

**What happened.** Two gates were added in this phase that assert something does *not* happen, and
a green assertion of a negative is worth exactly what its red run proves.

The SC-4 gate — `tests/architecture/test_no_commit_in_repositories.py`, which scans the
repositories package for any call that ends a transaction — was driven red by planting one line in
`users.py`. The test named `users.py:73`; the line was removed and it went green, with nothing
else changed between the runs
(`.planning/phases/03-persistence-runnable-stack/evidence/03-06-no-commit-gate-red.txt`, commit
`4227a93`).

The ARC-08 claim that the FastAPI `get_uow` dependency never makes its block durable in its own
teardown was falsified the same way: one line, `await unit.commit()`, was added to the provider's
teardown and `test_the_dependency_does_not_commit_on_teardown` failed with `assert 1 == 0`
(`evidence/03-09-teardown-falsification.txt`, commit `f81cc8e`). A green test alone could not
distinguish "the provider does not do it" from "the test could not have seen it if it did",
because FastAPI runs the exit half of a `yield` dependency after the response has already been
sent.

**How it was caught.** Deliberately, before either gate was relied on — the standard this project
set in Phase 1.

**Consequence, and the part that is not flattering.** `tests/integration/test_dependencies.py`
deliberately runs *outside* the per-test rollback fixture, because that is the only arrangement in
which an escaping write would be visible. So the red run genuinely committed a row into
`taskmanager_test`, and nothing cleaned it up. It was deleted by hand and the count verified at
zero before the suite was re-run.

**What changed.** The consequence is recorded here for the next plan that falsifies a persistence
claim from outside the isolation fixture: the red run leaves real rows, and the right response is
to remove them, never to add a cleanup step that would weaken the test.

### 2026-09-18 — A plan forbade the one change that kept the evaluator's first command usable

**What happened.** `03-10-PLAN.md` instructed the executor explicitly: *"Do not add a compose
profile for the `test` service: `docker compose run test` names it explicitly, and a profile would
add a flag the README would then have to explain."* Following it, the first
`docker compose up --build -d` of the cold-start rehearsal started **three** containers, because
`up` starts every declared service. `docker compose logs` then carried a full pytest run, coverage
table included, interleaved with the API's startup, and `docker compose ps -a` was left showing
`test exited`. For a project whose stated core value is that an evaluator can judge it in five
minutes starting from `docker compose up`, that is the most visible surface in the repository
reading like a failure.

**How it was caught.** By actually running the evaluator's command on an empty volume instead of
assuming the file was correct because it matched the plan.

**Consequence.** The plan's stated *reason* was also false, and that was checked rather than
argued: with `profiles: ["test"]` in place, `docker compose run --rm --build test` works with **no
flag**, because `run` enables the profiles of the service it names. So the cost the plan was
avoiding did not exist, and the cost it was accepting was the first thing an evaluator would see.

**What changed.** `profiles: ["test"]` was added against the plan text (commit `083fd11`), and the
contradiction is recorded as `DECISION_LOG.md` ADR-039 rather than buried in a deviation note, so
anyone reading the plan beside the compose file does not read the difference as an executor going
off-script. The transcript, including `docker compose config --services` before and after, is at
`evidence/03-10-cold-start.txt`.

### 2026-09-18 — The research's compose recipe would have failed the very first command in the README

**What happened.** `.planning/research/PITFALLS.md` and `03-RESEARCH.md` Pattern 6 both specify
`pgdata:/var/lib/postgresql/data` for the database volume, and `03-02-PLAN.md` repeated it.
`postgres:18-alpine` exits 1 on that mount: the image declares `VOLUME /var/lib/postgresql` and
sets `PGDATA=/var/lib/postgresql/18/docker`, and it refuses to start when it finds data at the
pre-18 path.

**How it was caught.** By starting the container on a cold volume rather than trusting that a
compose file which reads correctly will run. The image printed a multi-paragraph explanation; the
observed error text is now quoted in `docker-compose.yml` itself.

**Consequence.** `docker compose up` is the first command of this project's own README and the
opening move of the evaluator's five minutes. Shipped as researched, it would have failed there,
with an error about directory layouts rather than about anything the candidate wrote.

**What changed.** The volume mounts at `/var/lib/postgresql` (commit `4073765`), recorded as
`DECISION_LOG.md` ADR-026 specifically because the *correct* value contradicts almost every
PostgreSQL compose example in circulation — a reviewer who spots it should be able to find out in
one click that it was deliberate.

### 2026-09-18 — A planning document cleared a linter rule that then fired, and a research pattern reintroduced the pitfall it was written to avoid

**What happened, twice.** `03-PATTERNS.md` concluded that flake8-bugbear's B008 could not fire on
FastAPI dependency injection, because `.flake8` carries
`extend-immutable-calls = fastapi.Depends, ...`. `make lint` disagreed:
`health.py:86:47: B008 Do not perform function calls in argument defaults`. Bugbear matches the
call name **as written in the source**, and the whitelist names the *dotted* spelling this project
never uses, because it imports by name.

Separately, `03-RESEARCH.md` Pitfall 2 documents that handing `DATABASE_URL` to psycopg directly
fails, because the DSN carries a `+psycopg` driver token libpq reads as a syntax error — so the
entrypoint's bounded retry loop would spend all thirty attempts on a permanent error against a
healthy database. The same document's Pattern 7 then builds the SQLAlchemy engine *inside* the
retry loop. Building an engine parses the URL, so a malformed `DATABASE_URL` raises inside the
`try`, is counted as "not ready yet", and is retried thirty times: Pitfall 2's own failure mode
arriving from a second direction, in the code written to avoid it.

**How it was caught.** The first by `make lint` failing a commit gate. The second by reading
Pattern 7 against Pitfall 2 before running it, which is the only order in which it is visible.

**Consequence.** The B008 fix had two exits and only one of them was acceptable: adding a bare
`Depends` to `extend-immutable-calls` would have loosened a linter rule for the whole repository
to accommodate one call site.

**What changed.** Dependencies are injected as `Annotated[T, Depends(...)]` with a module-level
alias (`EngineDependency`), no `.flake8` change (commit `b56e5d6`, `DECISION_LOG.md` ADR-034) —
and this is now a rule in `CLAUDE.md`, because a Phase 4 router written the other way will fail
`make lint` for a reason that looks like a linter misconfiguration. The probe's engine is built
once before the loop (commit `bb1274e`, ADR-037), so a bad URL aborts in under a second with the
real exception and only *connecting* is retried.

### 2026-09-18 — What the five assumptions actually did, including the one that was half wrong

**What happened.** `03-RESEARCH.md` carries an assumptions log, A1 to A5. Each was settled by
observation during execution rather than carried to the end of the phase.

- **A1 — "Alembic autogenerate cannot detect `CHECK` constraints".** Half wrong, and the half that
  is wrong is the useful half. Autogenerate *did* emit `ck_tasks_status`, `ck_tasks_priority` and
  `ck_tasks_completed_at_matches_status` with the right names and the right SQL, because the
  blindness applies to *comparing* an existing table, not to rendering one being added for the
  first time — so none was hand-written. The half that holds: `alembic check` still cannot notice
  one disappearing later. On the related question of the `lower(email)` expression index, the
  observed output was `No new upgrade operations detected.` with no warning at all — which
  mattered, because `filterwarnings = error` would have turned one into a failed suite.
- **A2 — "psycopg populates `diag.constraint_name` for foreign-key violations too".** True, and
  proving it closed the project's last uncovered line. Plan 03-04 had deliberately left the
  positive branch of `violated_constraint()` untested, because a populated psycopg `Diagnostic`
  has no public constructor and a hand-built stand-in would have passed against a broken
  implementation too. `tests/integration/test_constraints.py::test_a_task_in_a_missing_list_is_refused`
  asserts the foreign-key name against a real server response; coverage over `src/taskmanager`
  went to 100.00%.
- **A3 — "an uncaught `HTTPError` is enough for the Dockerfile `HEALTHCHECK` to exit 1".** Not
  assumed. The healthcheck is a `python -c` one-liner with an explicit `try/except` and
  `sys.exit(1)`, because an unhealthy API reporting healthy is the one failure mode a healthcheck
  must not have.
- **A4 — "`timestamptz` round-trips as an aware datetime".** True.
  `tests/integration/test_schema.py` sends an aware UTC value with non-zero microseconds and gets
  back an equal, aware, zero-offset instant. That is what makes plan 03-04's
  `NaiveDatetimeFromDatabaseError` a tripwire rather than a live path.
- **A5 — "the two `caplog` tests run after the migration fixture in a default run".** Never
  tested, deliberately. Alembic's `fileConfig` silences existing loggers, which would break those
  two assertions in a full run while they pass in isolation. The fix —
  `disable_existing_loggers=False`, plus a guard on `config.attributes` — costs one keyword
  argument, so it was applied regardless of the observed ordering rather than made to depend on
  a file order that `-p randomly` or `--lf` would change.

**How it was caught.** By treating the assumptions log as a list of things to settle rather than
as a list of things to believe.

**What changed.** A1 and A2 are written into `DECISION_LOG.md` ADR-025 and ADR-030 with the
*observed* outcome rather than the expectation, including the part of A1 that did not hold.

### 2026-09-18 — Two verification runs looked green and were not

**What happened.** Twice in this phase, a command sequence reported success and had not.

In plan 03-02, a shell variable holding a multi-word `docker compose -f ... -f ...` invocation
does not word-split under zsh, so several verification lines died with `no such file or
directory` while the surrounding `alembic` commands kept passing — against a container left over
from an earlier attempt. In plan 03-10, the first Task 3 commit was rejected by the
`trailing-whitespace` pre-commit hook (captured compose output ends lines with a space), but the
failure was three lines above the end of a `tail -6`, so it read as a success while `git log`
still showed the previous commit.

**How it was caught.** The first by reading the output rather than the exit codes; the second by
running `git status --short` and seeing `AM` on the evidence file instead of assuming the commit
had happened.

**Consequence.** Both are the same defect in a different costume: a pipeline that reports on the
last thing it did rather than on everything it did. The 03-02 case is the more dangerous one,
because the verification *appeared* to prove a cold-volume start and had actually run against a
warm one.

**What changed.** The 03-02 sequence was redone with a shell function and a genuinely cold
volume; the 03-10 evidence file was re-staged and committed (`083fd11`). The general rule this
project already had from Phase 2 — *a verification command that passes is still read for what it
actually measured* — now has two more instances behind it, and every plan since stages captured
terminal output expecting one pre-commit abort.

### 2026-09-19 — The stack was proved by stopping the database, not by reading the compose file

**What happened.** The phase's headline claim is that `docker compose up` on an empty volume
starts PostgreSQL and the API, that the API waits for a database which genuinely answers, applies
the migration, and that `docker compose ps` reports `api healthy` only once `/health` has returned
200. All of that is also true of a container whose healthcheck merely proves the process is
alive.

**How it was caught — or rather, how the weaker version was ruled out.** After the cold start
reached `api healthy`, `docker compose stop db` was run: the container went `unhealthy` after 8
polls and `/health` answered `503` with
`{"status":"degraded","checks":{"database":"unavailable"},"version":"0.1.0"}` — the same three
members as the healthy body. `docker compose start db` returned both to healthy after 5 polls. A
liveness-only check would have stayed green throughout. The ordering claim was read off the log
rather than asserted: `docker compose logs api` opens with `Running upgrade  -> 0001, baseline`
and only then `Started server process [1]`.

**Consequence.** The healthcheck is known to be wired to the database, which is what makes
`depends_on: condition: service_healthy` meaningful rather than decorative, and what makes the
`/health` endpoint worth having at all.

**What changed.** The whole eight-step transcript is committed at
`.planning/phases/03-persistence-runnable-stack/evidence/03-10-cold-start.txt`, including the
stop/start cycle and `docker compose run --rm --build test` reporting
`Required test coverage of 75% reached` inside the container. It is the proof of record for the
entrypoint's retry bound, which deliberately has no unit test (`DECISION_LOG.md` ADR-037) — the
project would rather pay for an end-to-end rehearsal than add a coverage `omit` entry.

### 2026-09-18 — The commit gate had been red on the developer host for two phases, and only the research found it

**What happened.** `tests/unit/test_settings.py::test_get_settings_is_cached` failed on the
developer host while passing in CI and in the Docker `test` stage. `Settings` declares
`model_config = SettingsConfigDict(env_file=".env")`, and pydantic-settings resolves that
*relative* name against the process working directory. So `get_settings()` — a bare `Settings()` —
read the repository's real, untracked `.env`, which since plan 03-03 exports `TEST_DATABASE_URL`,
while the test's comparison object `Settings(_env_file=None)` deliberately read nothing. The two
objects differed on exactly that one field and the equality assertion failed. CI and the image
have no `.env`, so neither ever saw it.

**How it was caught.** Not by a gate. The Phase 4 research agent ran the baseline suite before
planning and recorded `1 failed, 292 passed` in `04-RESEARCH.md` §"Environment Availability". That
is two phases after the `.env` key that triggered it was added, and `make test` is named in
`CLAUDE.md` as a gate that must be green before *every* commit — so for two phases the developer
either did not run it or read past the failure.

**Consequence.** A gate whose verdict depends on an untracked file is not a gate. Worse, a
permanently red test trains the reader to ignore red, which is precisely how a real Phase 4
regression would have been let through.

**What changed.** The test's *isolation* was fixed, not its assertion: `monkeypatch.chdir(tmp_path)`
now runs before `get_settings.cache_clear()`, so the relative `.env` name resolves inside an empty
directory and both constructions read exactly the monkeypatched environment. All three assertions
are untouched — `first is second`, `first == Settings(_env_file=None)`, and the `database_url`
check — because each of the easy alternatives destroys the claim the test exists to make:
`_env_file=None` on the `get_settings()` path would stop testing the function as production calls
it, `skipif` would hide the failure on the only machine that reproduces it, and deleting the test
would drop the "the cached instance carries the current environment" guarantee altogether.

---

This log is appended to at the end of every subsequent phase.

---

## What I Did Not Do

The scope that was deliberately left out, and the shortcuts that were considered and rejected —
stated plainly rather than left for the reader to discover as omissions.

_To be completed in Phase 7._
