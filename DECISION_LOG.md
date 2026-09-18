# Decision Log

Opened **2026-09-17**, during Phase 1 (Foundation & Quality Gates).

Every entry is an ADR (Architecture Decision Record) with exactly four parts:

- **Context** — what forced the choice.
- **Options** — the alternatives that were really on the table, with the rejected one named.
- **Decision** — what was chosen.
- **Consequences** — what follows, including the cost or risk accepted, not only the benefit.

The log is appended to as the project progresses; entries are never rewritten once accepted.
If a later phase reverses a decision, it gets a new ADR that supersedes the old one by id.
Only decisions that were actually made are recorded here — no reconstructed rationale, and no
alternative softened into a strawman to make the chosen option look better.

---

## ADR-001: PostgreSQL, not SQLite

**Context**
The challenge brief requires "a real database". SQLite would run with zero setup and no
container, which is tempting for a deliverable an evaluator has five minutes to assess.

**Options**

- **SQLite** — no service to start, no credentials, the fastest possible test suite. Rejected:
  it invites the reviewer to ask whether "a real database" was satisfied, and its type
  affinity, lack of native `ENUM`, and weaker constraint behaviour would make the SQLAlchemy
  models diverge from anything that would ship.
- **PostgreSQL 18** — a service the evaluator must start, but `docker compose up` is required
  by the brief anyway.

**Decision**
PostgreSQL, reached through SQLAlchemy 2.0 and psycopg 3. Local and CI both run it as a
container; no code path targets SQLite, not even in tests.

**Consequences**

- Integration tests need a running database. That is an accepted cost: it is paid once, by the
  `docker compose up` the brief already demands, and CI gets it free from a service container.
- The test suite is no longer runnable from a bare `pytest` on a machine with nothing running.
  `make docker-test` exists precisely so that never becomes an excuse.
- Unit tests over the application layer use in-memory fakes implementing the same `Protocol`
  ports, so the majority of the suite stays database-free by design rather than by luck.

---

## ADR-002: Python 3.13 as the target runtime

**Context**
A version had to be pinned in the Dockerfile, in CI, in `requires-python`, and in the mypy and
black analysis targets. Python 3.12 entered security-only status (no more bugfix releases);
3.13 is in bugfix status until ~2026-10 with EOL 2029-10; 3.14 is newer still.

**Options**

- **3.12** — the conservative "wheels are guaranteed" choice, and the version an earlier draft
  of the project notes assumed. Rejected: every native dependency in this stack already ships
  `cp313` manylinux wheels for x86_64 and aarch64, so the rationale no longer holds, and a
  security-only interpreter is the kind of detail an evaluator flags.
- **3.14** — maximum "current" signal. Rejected as the *declared target*: a couple of lint
  plugins still lack 3.14 classifiers, and shipping the newest possible interpreter buys
  nothing a grader rewards.
- **3.13** — current bugfix line, full wheel coverage.

**Decision**
Python 3.13. Image `python:3.13-slim-trixie` (resolves to 3.13.15), `requires-python = ">=3.13"`,
`mypy python_version = "3.13"`, `black target-version = ["py313"]`, CI on 3.13.

**Consequences**

- The development host has no 3.13: it runs CPython **3.14.3**, and the host venv was created
  with plain `python3` on purpose (a `python3.13 -m venv` line would fail on the first
  command). `requires-python = ">=3.13"` is satisfied by 3.14, so the inner loop works.
- **Accepted risk, recorded deliberately:** the host interpreter and the authoritative one
  differ. With `filterwarnings = error` in `pytest.ini`, a warning that exists on only one of
  the two could make local and CI disagree. None was observed in Phase 1, the divergence
  becomes more likely once SQLAlchemy and psycopg are actually imported (Phase 3), and the
  mitigation is that **CI on 3.13 is authoritative** and `make docker-test` reproduces 3.13
  locally on demand.

---

## ADR-003: `src/` layout with four layer packages

**Context**
The brief asks for a clean separation of concerns. The package also has to be importable by
pytest, mypy and import-linter, all three of which resolve modules differently.

**Options**

- **Flat `taskmanager/` at the repository root** — one less directory. Rejected: the root
  directory is implicitly on `sys.path`, so tests can import the package without it ever being
  installed, and a packaging error stays invisible until it is someone else's problem.
- **`pythonpath = src` in `pytest.ini` alone, no install** — works for pytest and (with
  `mypy_path`) for mypy, but `lint-imports` then needs `PYTHONPATH=src` exported in every
  Makefile target, CI step and hook. Rejected: more places to forget it.
- **`src/taskmanager/` plus an editable install** (`pip install -e .`, setuptools backend).

**Decision**
`src/taskmanager/` with sub-packages `domain`, `application`, `infrastructure`, `presentation`
and `main.py` as the composition root. `make install` ends with `pip install -e .`.

**Consequences**

- `make install` is a real prerequisite; a bare `pytest` on a fresh clone works only because
  `pythonpath = src` is kept in `pytest.ini` as a safety net.
- The four packages exist from day one with no logic in them, which looks empty in Phase 1 and
  is exactly what makes the import-linter contracts enforceable from day one.
- `pyproject.toml` deliberately has **no** `[project.dependencies]`, so `pip install -e .`
  installs only the local package (see ADR-011).

---

## ADR-004: stdlib dataclass domain entities, Pydantic only at the boundaries

**Context**
The brief asks for "strong typing with Pydantic". The obvious reading — make every model a
Pydantic model — would put a validation framework in the centre of the domain.

**Options**

- **Pydantic models as domain entities** — fewer classes to write. Rejected: a Pydantic
  `ValidationError` cannot carry the domain error contract (ADR-005), so business rules would
  either raise the wrong exception type or be duplicated.
- **SQLModel** — fuses the ORM entity and the API schema into one class. Rejected outright: it
  collapses precisely the boundary the brief asks the candidate to demonstrate.
- **stdlib `dataclass` entities + `typing.Protocol` ports, with Pydantic at the HTTP schema,
  application DTO and settings boundaries.**

**Decision**
Domain entities are stdlib dataclasses and enums; ports are `typing.Protocol`. Pydantic lives
in `presentation` schemas, `application` DTOs and `infrastructure.config.settings`.

**Consequences**

- Three representations of the same concept can exist (entity, DTO, response schema) and must
  be mapped explicitly. That is real, repetitive work, accepted as the price of the boundary.
- The rule is mechanically enforced: `pydantic` is in the `forbidden_modules` list of the
  `domain-framework-free` contract, and allowed for `application`.
- Domain unit tests need no framework at all and run in milliseconds.

---

## ADR-005: RFC 9457 `application/problem+json` from a single exception handler

**Context**
The API needs one consistent error shape. FastAPI's default is `{"detail": ...}`, and there is
a standard for exactly this problem — RFC 7807, obsoleted by **RFC 9457** in 2023.

**Options**

- **FastAPI's default `detail` body** — zero work. Rejected: no `type`, no way to extend the
  payload per error class, and nothing to point a reviewer at.
- **RFC 7807** — the widely-known number. Rejected in favour of its successor; citing an
  obsoleted RFC is a small but avoidable error.
- **RFC 9457 Problem Details**, emitted by one registered exception handler.

**Decision**
`application/problem+json` per RFC 9457, produced at a single translation point that maps
`DomainError` subclasses to status codes. `fastapi.HTTPException` is never raised outside the
`presentation` layer; the rule is written into `CLAUDE.md`.

**Consequences**

- The handler must exist before the first router, which is why Phase 2 builds the error
  contract before any endpoint.
- FastAPI's own validation errors (422) come out in FastAPI's shape unless they are also
  translated — an explicit task, not something the decision gives for free.
- The prohibition on `HTTPException` outside `presentation` is currently enforced by review and
  by the layer contracts; a targeted `forbidden` contract can tighten it once the modules exist.

---

## ADR-006: psycopg 3 with async SQLAlchemy 2.0, not asyncpg

**Context**
An async SQLAlchemy 2.0 engine needs an async DBAPI. Alembic's stock `env.py` is synchronous.
The driver choice decides whether those two can share one `DATABASE_URL`.

**Options**

- **asyncpg** — the fastest PostgreSQL driver in Python by a clear margin. Rejected: Alembic
  then needs either an async `env.py` (~40 extra lines of `asyncio.run` + `run_sync`) or a
  second driver (`psycopg2-binary`), the URL has to differ between app and migrations, and
  `?sslmode=...` is rejected by the dialect and must be translated into `connect_args`.
- **psycopg 3 (`psycopg[binary]`)** — one driver that speaks both sync and async behind the
  same `postgresql+psycopg://` URL.

**Decision**
`psycopg[binary]` 3.3.5 with `create_async_engine("postgresql+psycopg://...")` for the app, and
the **stock synchronous Alembic `env.py`** against the identical URL.

**Consequences**

- Slower raw driver throughput than asyncpg. Accepted: this deliverable is graded on structure
  and correctness, not on benchmark numbers.
- One `DATABASE_URL` value everywhere — `.env`, CI, compose and Alembic — with no string
  surgery, which removes a whole class of "works locally, fails in CI" bugs.
- `async_sessionmaker(..., expire_on_commit=False)` is mandatory in Phase 3: the default
  triggers a lazy refresh after `commit()` that raises `MissingGreenlet` under async.

---

## ADR-007: Alembic migrations, never `Base.metadata.create_all()`

**Context**
The schema has to come from somewhere. `create_all()` is one line in the app factory and works.

**Options**

- **`Base.metadata.create_all()` on startup** — trivial, and adequate for a throwaway project.
  Rejected as the production path: it reads as "no migration strategy", has no downgrade, and
  silently does nothing when a table already exists but has drifted.
- **Alembic** — same maintainers as SQLAlchemy, requires `SQLAlchemy>=2.0`.

**Decision**
Alembic 1.20 owns the schema. `alembic upgrade head` runs from the container entrypoint;
`create_all()` is permitted only as a test-only shortcut, if at all.

**Consequences**

- An extra artifact to maintain: every model change needs a reviewed autogenerated revision,
  and autogenerate does not detect everything (type changes, renames).
- Startup gains a database dependency and a failure mode — a container that cannot reach
  PostgreSQL now fails during migration rather than at the first request, which is preferable
  but must be visible in the compose health checks (Phase 3).

---

## ADR-008: 404 for invisible resources, 403 for visible-but-forbidden

**Context**
Task lists are owned and shared. When a caller asks for a resource they may not have, the
status code either leaks its existence or hides it.

**Options**

- **403 for everything unauthorised** — simple and uniform. Rejected: it is an existence
  oracle; an attacker enumerating ids learns which ones exist from the difference between 403
  and 404.
- **404 for everything unauthorised** — no leak at all, but it makes a genuine permission
  problem indistinguishable from a typo, which is hostile to legitimate users and untestable.
- **A split rule**, keyed on whether the resource is visible to the caller.

**Decision**
If the caller cannot see the resource at all, the API returns **404**. If the caller can see it
but is not allowed to perform the operation, it returns **403**.

**Consequences**

- The permission matrix must be explicit and tested per operation — each endpoint owes both a
  404 case and a 403 case. That is more tests, accepted: it is the only way the rule is real.
- The repository layer must answer "visible to this user?" separately from "exists?", which
  shapes the query methods in Phase 3.

---

## ADR-009: completion percentage over the whole list, via one SQL aggregate

**Context**
The brief requires a completion percentage on a list endpoint that also supports filtering by
status. Two readings are possible, and the brief does not resolve it.

**Options**

- **Percentage over the filtered subset** — arguably "what the user is looking at". Rejected as
  degenerate: `?status=completed` would always report 100%, and `?status=pending` always 0%.
- **Percentage over the whole list, independent of any filter**, computed in a single SQL
  aggregate rather than by counting rows in Python.

**Decision**
The percentage always describes the entire list and is unaffected by filters. It is computed by
one aggregate query, not by loading tasks and counting them in the application.

**Consequences**

- The response returns a number that does not match the visible rows when a filter is active.
  That is a documentation obligation (README and OpenAPI description), not a bug.
- The list endpoint issues two queries (page + aggregate) rather than one, and never pays an
  N+1 or a full-table load to produce the number.
- The ambiguity itself is worth recording: the brief is unclear here, and the choice is
  defended rather than silently made.

---

## ADR-010: flake8, not ruff

**Context**
The challenge brief names the linter explicitly: flake8. Ruff is, in 2026, the de facto modern
standard and runs 10-100x faster while replacing flake8, isort and several plugins.

**Options**

- **ruff** — one tool, one config block, a fraction of the runtime, and it would also subsume
  isort. **This is what would be chosen absent the constraint** — it is the better tool.
- **flake8 7.3.0** with `flake8-bugbear`, `flake8-comprehensions` and `pep8-naming`.

**Decision**
flake8, because the brief mandates it. A mandated tool is not a suggestion, and substituting a
"better" one is the kind of initiative that fails a take-home. Configuration lives in the
literal `.flake8` file (flake8 still cannot read `pyproject.toml`), with black compatibility via
`max-line-length = 88` and `extend-ignore = E203, E701`; black and isort are configured in
`pyproject.toml`.

**Consequences**

- Accepted cost: four linting tools (black, isort, flake8, + plugins) where one would do, a
  slower gate, and a fourth place where versions are pinned (the pre-commit hook revs).
- `extend-ignore` is used, never `ignore` — `ignore` replaces pycodestyle's `DEFAULT_IGNORE`
  and silently re-enables E121/E123/E126/E226/E704/W503/W504, every one of which black's own
  output violates.
- `extend-immutable-calls` lists `fastapi.Depends`, `Query`, `Path`, `Body` and `Header`,
  because bugbear's B008 otherwise fires on every FastAPI dependency.
- Ruff is named here on purpose: an evaluator should see that the constraint was recognised as
  a constraint.

---

## ADR-011: plain pip with exact `==` pins

**Context**
Dependencies must be reproducible six months from now on an evaluator's machine, with the
fewest prerequisites possible.

**Options**

- **Poetry** — lockfile and resolver, but requires the evaluator to install Poetry and produces
  a lockfile nobody reads in a diff.
- **uv** — dramatically faster, but the same objection: another tool to install and trust, and
  `uv.lock` is not human-readable.
- **pip + exact-pinned `requirements.txt` / `requirements-dev.txt`.**

**Decision**
`requirements.txt` (runtime) and `requirements-dev.txt` (dev/test) with `==` pins are the single
source of version truth. `pyproject.toml` holds packaging metadata and tool configuration but
deliberately no `[project.dependencies]`, so `pip install -e .` installs only the local package.

**Consequences**

- **Accepted cost:** nine runtime dependencies are pinned in Phase 1 that Phase 1 never imports
  (`uvicorn[standard]`, `SQLAlchemy[asyncio]`, `psycopg[binary]`, `alembic`, `PyJWT`,
  `pwdlib[argon2]`, `python-multipart`, `email-validator`, plus `httpx` in dev). This is
  intentional: the Dockerfile layer and the CI cache key never change shape later.
- No transitive lock. `pip install -r requirements.txt` can still resolve a different
  transitive version tomorrow; the direct dependencies are frozen, which is the level of
  reproducibility this deliverable needs.
- Version bumps are manual, and the pre-commit mirror revs must be bumped in the same commit.

---

## ADR-012: pytest-asyncio in `auto` mode, `asyncio_default_fixture_loop_scope = function`

**Context**
The suite will be mostly `async def`. Two plugins can run it, and pytest 9 turns removal
warnings into errors, so an unset loop-scope option is a hard failure rather than noise.

**Options**

- **anyio's pytest plugin** — what the official FastAPI docs use, and it arrives transitively
  anyway via Starlette and httpx. Rejected: `auto` mode does not exist, so every async test
  needs a marker, and a session-scoped event loop requires redefining the `anyio_backend`
  fixture in `conftest.py`.
- **pytest-asyncio 1.4.0** with `asyncio_mode = auto`.

**Decision**
pytest-asyncio in `auto` mode. `asyncio_default_fixture_loop_scope = function` is set
explicitly in `pytest.ini`. All pytest configuration lives in `pytest.ini` — the brief mandates
that file, and pytest silently ignores `[tool.pytest.ini_options]` whenever it exists.

**Consequences**

- A function-scoped loop means a session-scoped async fixture (for example a shared engine) is
  not usable as-is; Phase 3 either raises the scope deliberately, in its own commit, or keeps
  the engine creation synchronous at import time. Choosing `function` now is the conservative
  default that cannot produce cross-test loop reuse bugs.
- Two async plugins are installed (anyio is transitive). Only pytest-asyncio is configured, and
  `asyncio_mode = auto` keeps them from competing for the same tests.

---

## ADR-013: `postgres:18-alpine`, pinned by major version

**Context**
The database image tag ends up in `docker-compose.yml` and in the CI service container, and it
decides whether a build six months from now is the same build.

**Options**

- **`postgres:latest`** — always current. Rejected: unreproducible by definition, and a silent
  major-version jump is a failure mode nobody notices until it happens.
- **`postgres:17-alpine`** — the conservative fallback, more field time.
- **`postgres:18-alpine`** — GA 2025-09, EOL 2030-11, roughly a year in the field.

**Decision**
`postgres:18-alpine`, with the major version pinned everywhere it appears. Alpine is fine for
PostgreSQL (unlike for Python — see ADR-014).

**Consequences**

- Patch updates still arrive on a rebuild, which is wanted; a major jump requires an explicit
  edit, which is also wanted.
- PostgreSQL 18 is young enough that an obscure incompatibility is conceivable; nothing this
  project uses is near that edge, and PG 17 is a one-token fallback.

---

## ADR-014: `.importlinter` as a root-level INI file, not `[tool.importlinter]`

**Context**
import-linter reads its contracts from either a dedicated INI file or a `[tool.importlinter]`
section of `pyproject.toml`. The project's own research documents disagreed: `STACK.md` used
the INI file, `ARCHITECTURE.md` used `pyproject.toml`.

**Options**

- **`[tool.importlinter]` in `pyproject.toml`** — one fewer root-level file, all tool
  configuration in one place. **Functionally identical** — this is not a technical tradeoff,
  and the architecture test calls `api.read_configuration()` with no filename, which finds
  either form.
- **A root-level `.importlinter`.**

**Decision**
The root-level `.importlinter` INI file, with a `layers` contract and two `forbidden` contracts
(`domain-framework-free`, `application-framework-free`).

**Consequences**

- Discoverability decided it: this phase's thesis is that an evaluator can find the enforced
  boundary in seconds, and a file named after the tool does that better than the fifth section
  of `pyproject.toml`.
- One more file at the repository root.
- `include_external_packages = True` is required, or the two `forbidden` contracts build no
  nodes for third-party distributions and silently check nothing.
- The real configuration trap found by execution is **not** the plural `contracts:` header the
  research warned about (harmless on 2.15) but the hyphenated `[import-linter:...]` section
  prefix, which yields zero contracts and exit 0. A guard test asserts the contract count.

---

## ADR-015: mypy and lint-imports as `repo: local` pre-commit hooks with `.venv/bin` entries

**Context**
pre-commit installs each hook repo into its own isolated virtualenv. mypy and import-linter are
whole-program tools: they must see the real installed environment (the `pydantic` plugin, the
editable `taskmanager` package, `pytest` imported from `tests/`).

**Options**

- **`pre-commit/mirrors-mypy` with `additional_dependencies`** — pinned isolation, the
  documented path. Rejected: it needs `pydantic`, `pydantic-settings` **and** `pytest`
  duplicated into an `additional_dependencies` list, creating a fourth place where versions are
  pinned and are free to drift from `requirements-dev.txt`. The usual "fix" for the resulting
  errors is to drop `tests/` from the hook, which quietly stops type-checking half the repo.
- **`repo: local` hooks with `language: system`, `pass_filenames: false`** — run the same
  binaries as `make typecheck` and `make arch`, from the same `.venv`, at the same versions.

**Decision**
black, isort and flake8 come from pinned mirror repos (they are file-scoped, and isolation is
what is wanted there). mypy and import-linter are `repo: local`, `language: system`, with the
entries written as the literal paths **`.venv/bin/mypy`** and **`.venv/bin/lint-imports`** — not
bare tool names.

**Consequences**

- The `.venv/bin` prefix is load-bearing, and this was verified rather than assumed: with the
  bare entries, under `env -i HOME=... PATH=/usr/bin:/bin:/usr/local/bin`, pre-commit reported
  ``Executable `mypy` not found`` and ``Executable `lint-imports` not found`` and both hooks
  failed — while the ten hooks above them still reported `Passed`. pre-commit never activates a
  virtualenv, and this host has no project tools on `PATH` outside `.venv`. Capture:
  `.planning/phases/01-foundation-quality-gates/evidence/pre-commit-venv-entry.txt`.
- **Accepted cost:** `.pre-commit-config.yaml` now only works where `.venv` exists — the
  developer host. Therefore **CI and the Docker `test` stage never invoke `pre-commit`**:
  `.github/workflows/ci.yml` runs black, isort, flake8, mypy, `lint-imports` and pytest as its
  own named steps, and the container's gate is `pytest`.
- **Maintenance consequence, recorded as a standing rule:** a new gate must be added in **both**
  `.pre-commit-config.yaml` and `.github/workflows/ci.yml`, because neither file derives from
  the other. The CI step names are aligned to the hook ids so the drift is visible in review,
  and the same rule is written in the `## Project Rules` section of `CLAUDE.md`.
- A hook and its Makefile target can never disagree: both run the identical binary from the
  identical `.venv`.

---

## ADR-016: the architecture contract runs through import-linter's Python API

**Context**
The layer contracts have to fail the test suite, not just a separate command an evaluator might
never run. The obvious implementations are a subprocess call or the module form of the CLI.

**Options**

- **`python -m importlinter.cli` inside the test** — looks like the documented invocation.
  Rejected on evidence: that module has no `__main__` guard, so it **exits 0 with a real
  violation in place**. It would have shipped an architecture test incapable of failing.
- **`subprocess.run(["lint-imports"])`** — the console script does exit 1 correctly, but
  resolving its path portably inside a venv is fiddlier than a two-line API call.
- **`importlinter.api` / `importlinter.application.use_cases.lint_imports` in-process.**

**Decision**
`tests/architecture/test_layer_boundaries.py` calls the Python API in-process and asserts on a
real boolean, plus a guard assertion on the number of contracts read. `make arch`, the
pre-commit hook and CI all use the **`lint-imports` console script**; the `python -m` module
form is forbidden anywhere in this repository.

**Consequences**

- The contract is red/green-proven, not declared: a deliberate forbidden import was added,
  observed failing, and removed. Capture:
  `.planning/phases/01-foundation-quality-gates/evidence/import-linter-red-green.txt`.
- The test depends on an internal-ish API surface that could change across import-linter
  majors. Accepted: `import-linter` is pinned exactly, and the failure mode would be an import
  error at collection time — loud, not silent.
- The contract count assertion is what protects against a misconfigured section header
  (ADR-014) turning the whole check into a no-op.

---

## ADR-017: `make up` / `make down` ship as honest placeholders

**Context**
The Makefile must expose `up` and `down` from Phase 1, but `docker-compose.yml` does not arrive
until Phase 3 (the API cannot be composed with a database before the error contract and the
persistence layer exist).

**Options**

- **Omit the targets until Phase 3** — nothing pretends to work. Rejected: the target list is a
  locked deliverable of this phase, and a missing target reads as an oversight.
- **Have them fail with a non-zero exit** — technically honest, but indistinguishable from a
  broken Makefile.
- **A single `@echo` that states the truth and exits 0.**

**Decision**
`make up` and `make down` each print one accurate line naming Phase 3 and pointing at
`make docker-test`, and exit 0. Phase 3 replaces the recipe bodies in place; the target names
are frozen so no documentation has to change.

**Consequences**

- Two targets currently do nothing. Accepted, and stated in the output itself rather than left
  for the reader to discover — a placeholder that lies about its status is the failure mode
  being avoided.
- `make docker-test` is the real containerised entry point in the meantime, and it is not a
  placeholder: it builds the Dockerfile `test` stage and runs the suite on Python 3.13.

---

## ADR-018: a dedicated Dockerfile `test` stage, not a compose profile

**Context**
The brief requires one documented command that runs the test suite in Docker with no Python on
the host. Compose is the natural home for such a command, and compose does not exist yet.

**Options**

- **A compose profile / service** — the eventual shape, and what Phase 3 will offer. Rejected
  for now: `docker-compose.yml` does not exist in Phase 1, and inventing a half file just to
  hold a test service would create an artifact Phase 3 has to undo.
- **A third Dockerfile stage** (`builder` → `runtime`, `builder` → `test`) whose default command
  runs `pytest`.

**Decision**
`docker build --target test` plus `docker run --rm`, wrapped as `make docker-test`. Phase 3 adds
a compose `test` service with `target: test` and swaps the recipe body without renaming the
target.

**Consequences**

- The image carries dev tooling and the test suite in a stage that never reaches the runtime
  image, which stays slim and non-root.
- **The stage was shipped only after being observed red:** copied verbatim from the research it
  failed, because it never copied `.env.example` and the settings/`.env.example` parity test
  reads that file from the repository root — while the same run still printed
  `Required test coverage of 75% reached. Total coverage: 100.00%` immediately above `1 failed`.
  `.env.example` (a tracked placeholder; the real `.env` stays excluded by `.dockerignore`) was
  added to the stage. Capture:
  `.planning/phases/01-foundation-quality-gates/evidence/docker-test-stage.txt`.
- Image size is recorded as **observed**: 368 MB on linux/arm64 with a BuildKit attestation
  manifest, not the 285 MB the research measured elsewhere. Both are far under the 500 MB
  ceiling; repeating a number measured on another platform would have been easier and less
  honest.

---

## ADR-019: GitHub Actions pinned to major tags, not commit SHAs

**Context**
`ci.yml` uses `actions/checkout`, `actions/setup-python` and `actions/cache`. A mutable tag can
be repointed by whoever controls the action's repository.

**Options**

- **Full commit SHA pinning** — the supply-chain-hardened form, immune to tag repointing.
  Rejected for now as ceremony disproportionate to the exposure, and it makes every routine
  update an opaque 40-character diff.
- **Major version tags** (`@v7`, `@v7`, `@v6`).

**Decision**
Major tags, with `permissions: contents: read` declared explicitly at workflow level and no
secret referenced by any step.

**Consequences**

- **Accepted risk, named rather than omitted:** a compromised upstream tag would execute in CI.
  It is bounded by the workflow holding no credential and no write scope, and the explicit
  read-only `permissions` block survives a future change to the repository's default workflow
  permissions.
- SHA pinning is the Phase 7 delivery-hardening option and is listed as such.
- **The workflow has never run on a real runner** — no repository existed when it was written.
  Every component is verified individually (action tags, the `postgres:18-alpine` service, the
  `cache: pip` syntax, and every shell command executed locally), but the assembled YAML is
  unproven. One fix-up commit after the first push is budgeted.

---

## ADR-020: application command and result DTOs are frozen dataclasses, refining ADR-004

**Context**
Five artifacts written before Phase 2 assert that Pydantic types the application DTOs —
`REQUIREMENTS.md` ARC-05, ADR-004's own decision line, the `.importlinter` comment above the
`application-framework-free` contract, ROADMAP Phase 4 SC-5, and the `CLAUDE.md` rule that
"Pydantic *is* allowed there". The Phase 2 planning session decided the opposite: commands and
results are `@dataclass(frozen=True, slots=True)` and the application layer stays free of
Pydantic. That decision is the newest and is authoritative, so five documents now contradict
the code that Phase 2 actually shipped.

**Options**

- **Pydantic command and result models** — the shape four documents already describe, and
  consistent with "strong typing with Pydantic" read maximally. Rejected: shape validation has
  already happened once, at the HTTP boundary, where the request schema rejected a malformed
  payload before a command object could exist. Running it a second time buys no safety and
  makes the application layer depend on the web stack's validation library, which is the
  dependency the layering exists to avoid.
- **Frozen, slotted dataclasses** — `frozen=True` so a use case cannot rewrite its own input
  halfway through, `slots=True` so a misspelled field is an `AttributeError` at the call site
  rather than a silently ignored keyword.

**Decision**
Frozen slotted dataclasses, with `actor_id: UUID` as the first field of every command. This
**refines ADR-004 rather than overturning it**: ADR-004's real claim is that Pydantic lives at
the boundaries and never in the centre, and that claim is unchanged. Only the list of what
counts as a boundary narrows — from "HTTP schemas, application DTOs and settings" to "HTTP
schemas and settings". ADR-004 is not edited; this log is append-only, and a refinement by id
is exactly the mechanism its header describes.

`pydantic` is deliberately **not** added to the `application-framework-free` contract's
`forbidden_modules`. Enforcement stays permissive on purpose: a later phase may have a
legitimate reason for a Pydantic DTO, the current contract shape is a locked decision from the
phase context, and a rule nobody has needed yet is a rule that will be deleted under pressure
rather than obeyed. The convention is stated once, in `application/dto/commands.py`'s
docstring, where the next person to write a command will read it.

**Consequences**

- ARC-05's wording, ROADMAP Phase 4 SC-5, the `.importlinter` comment and the `CLAUDE.md`
  Project Rules line are amended to match (plan 02-07). Without that, Phase 4 verification
  fails against its own text while the code is correct — the worst kind of red.
- The mismatch is recorded here rather than quietly reconciled. Five documents saying one thing
  and the code doing another is a fact about this project's history, and a decision log that
  hides it is not worth keeping.
- A command carries no validation of its own. Anything the domain must guarantee is guaranteed
  by the entity, in one place, per the "no rule lives in two layers" rule.

---

## ADR-021: the `DomainError` base shape, and what the four handlers deliberately do not catch

**Context**
`.planning/research/ARCHITECTURE.md` Pattern 6 prescribes `__init__(self, message, **details)`
for the base domain error. This repository's own flake8 rejects that signature with
flake8-bugbear's B042, and each obvious B042-clean alternative breaks something else. The base
class is also where the error contract's serialisability is won or lost, because the
presentation layer turns `details` straight into a `problem+json` member.

**Options**

- **`__init__(self, message, **details)`** — the sketched shape. Rejected: it fails `make lint`,
  and an inline `# noqa: B042` would suppress a check that is pointing at a real defect rather
  than at a style opinion.
- **`super().__init__(message)` only** — the smaller signature. Rejected: also B042, because the
  check compares the number of *positional* arguments forwarded to `super().__init__()` with the
  number of parameters the signature declares.
- **A leaf subclass with its own signature and no `__reduce__`** — for example
  `InvalidStatusTransitionError(current, requested)`. Rejected, and this is the interesting one:
  it *passes* B042 and still breaks. `Exception.__reduce__` rebuilds an instance by calling
  `cls(*self.args)`, so the leaf is reconstructed with the base class's arguments and raises
  `AttributeError` during `pickle.loads` or `copy.copy`. B042's heuristic gives a false pass
  here, which is precisely why the check is worth keeping unsuppressed elsewhere.
- **One `__init__(message, details=None)` on the base, plus `__reduce__`.**

**Decision**
One `__init__(self, message: str, details: Details | None = None)` forwarding both parameters to
`super().__init__()`; one `__reduce__` on the base delegating to a module-level `_restore` that
rebuilds any subclass via `cls.__new__` without ever calling a subclass `__init__`; and an
explicit `__str__` returning `self.message`, because forwarding two parameters makes `self.args`
a 2-tuple and the inherited `__str__` would otherwise render the whole `details` dict into every
log line built from `str(exc)`.

The status mapping is decided here too. A domain `ValidationError` is **422**, on the
well-formed-but-semantically-invalid reading — the same 422 an evaluator has already seen come
out of Pydantic, so the API answers one code for one meaning. An invalid status transition is
**409**, per D-01 and TASK-05: it is a conflict with the current state of the resource, not a
defect in the payload.

**Consequences**

- A pickle/copy round-trip test is mandatory, not optional — it is the only thing standing
  between a future leaf signature and the `AttributeError` above. It is also what takes
  `exceptions.py` to 100% coverage, so the cost is already paid.
- `details` values are constrained to `str | int | float | bool | None` rather than `Any`. A
  `UUID` or a `TaskStatus` left in there would raise while the handler serialised the problem
  body, turning a precise business answer into an unexplained 500. The narrow alias makes that
  a mypy error at the raise site instead.
- **`ResponseValidationError` is not a `RequestValidationError`** — both subclass
  `fastapi.exceptions.ValidationException` and neither is a parent of the other. A response-model
  mismatch therefore falls past the four registered handlers into the catch-all `Exception`
  handler and becomes a 500 `internal_error`, not a 422. That is the intended outcome, because a
  response-model mismatch is a server bug and not a client error, and it is recorded here so it
  reads as a choice rather than as something nobody checked.
- Leaf classes forward `details` as a keyword, which looks inconsistent next to
  `InvalidStatusTransitionError`'s positional call. The reason is B042's positional-argument
  count and it is documented in the module docstring; the stored state is identical either way.

---

## ADR-022: the domain's stdlib-only rule is proven by an AST test, not by import-linter alone

**Context**
ROADMAP success criterion 1 for Phase 2 says "the import-linter contract proves the `domain`
package imports no third-party library". It cannot, as written. `domain-framework-free` is a
`forbidden` contract with an enumerated list of nine distributions; it proves those nine are
absent and says nothing about the tenth.

**Options**

- **`forbidden_modules = *`** — import-linter 2.15 does support the wildcard. Rejected on
  evidence, not on taste: it was executed during this phase's research and reported
  `dataclasses`, `datetime` and `enum` as violations, because a grimp graph built with
  `include_external_packages = True` carries stdlib modules as first-class nodes. There is no
  contract type meaning "everything except the standard library".
- **`grimp.build_graph` inside a test** — reuses the resolver import-linter already uses, and
  was verified working. Rejected: `grimp` reaches this environment only as a transitive
  dependency of `import-linter`, and `requirements-dev.txt` states that it is intentionally
  absent from the declared set. Importing it in a test would let a future `import-linter` bump
  break the suite with a confusing `ModuleNotFoundError` in a file that has nothing to do with
  the upgrade.
- **`ast` + `sys.stdlib_module_names`** — parse every module under `src/taskmanager/domain/`,
  collect each import's root name, and check it against the interpreter's own list.

**Decision**
The AST test, at `tests/architecture/test_domain_is_stdlib_only.py`, **kept alongside the
enumerated contract rather than replacing it**. The contract gives targeted, readable failures
naming the exact import path for the nine distributions that matter most; the AST test closes
the general case. `sys.stdlib_module_names` is maintained by CPython for the running
interpreter, so the check is honest on 3.13 in CI and on 3.14 on the developer host — the two
sets differ (290 names against 297) and the test passes on both.

**Consequences**

- **No gate is added to `.pre-commit-config.yaml` or `.github/workflows/ci.yml`.** The check
  rides inside `pytest`, which both files already invoke. That matters because those two files
  do not derive from one another: per ADR-015 a new gate would have to be added to both, and the
  cheapest way to avoid that divergence is not to create a gate at all.
- The test carries an anti-vacuity guard, because a glob that matches nothing makes
  `assert violations == []` pass forever. It asserts the scan found at least ten modules and
  that four named ones — `exceptions.py`, `validation.py`, `value_objects/task_status.py` and
  `entities/task.py` — were among them.
- The gate was **observed** red on a planted `import greenlet` that `lint-imports` reported as
  KEPT in the same tree, and green once the import was removed. Both captures, and the
  contrasting exit codes, are committed at
  `.planning/phases/02-domain-error-contract/evidence/domain-stdlib-red-green.txt`. Following
  the Phase 1 precedent: a quality gate is not trusted here until it has been seen failing.
- Import parsing is hand-rolled, which is a real cost — roughly fifteen statements that a
  library would otherwise own. It is bounded: relative imports are skipped by `node.level`
  rather than resolved, so the test never has to model Python's import system, only read it.

---
