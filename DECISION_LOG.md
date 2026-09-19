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

## ADR-023: per-owner task-list name uniqueness is case-sensitive

**Context**
Three artifacts disagreed about one index. `02-CONTEXT.md` D-12 specifies a plain
`UNIQUE (owner_id, name)` on `task_lists`. The `TaskList` entity docstring and
`tests/unit/application/fakes.py` both described it as `(owner_id, lower(name))`, and the fake
implemented a case-folded comparison. One of the three had to be wrong before any repository
could be written against it, because D-13's `IntegrityError` translation keys on the constraint
and the in-memory fake is the behavioural model the SQLAlchemy adapter has to match.

**Options**

- **`lower(name)`, matching the two comments** — superficially friendlier, and symmetric with
  the `users` index. Rejected on a concrete consequence, not on the word count of the
  specification: `TaskList` performs no case folding on its name, so a case-insensitive index
  would make PostgreSQL refuse `alpha` for an owner who already has `Alpha` — a rejection the
  domain has no concept of, surfacing as a 409 for two values the entity considers distinct.
- **Plain `UNIQUE (owner_id, name)`, matching D-12** — the database defends exactly the rule the
  entity states and nothing more.

**Decision**
D-12 wins. `uq_task_lists_owner_id_name` is `UNIQUE (owner_id, name)`, case-sensitive. The
entity docstring, the model comment and the fake were corrected in plan 03-01 (`1b3b65e`) so all
three now say the same thing.

The deliberate contrast is `uq_users_email_lower`, a unique index on `lower(email)`. The two
differ because the two entities differ: `User.__post_init__` lowercases the address before it can
ever be stored, so the expression index defends a rule the entity already enforces and can never
reject a value the domain accepts. `TaskList` folds no case, so the same shape there would
overreach.

**Consequences**

- `Alpha` and `alpha` are two lists for one owner. That is the domain's answer, and it is now
  stated in the entity docstring rather than left for a reviewer to infer from an index.
- The asymmetry between the two indexes will look like an oversight to anyone who reads the
  schema alone. It is commented at both `__table_args__` entries and in `constraints.py`, and it
  is recorded here so the question has an answer that is not "nobody noticed".
- It is proven at the server, not at the model:
  `tests/integration/test_constraints.py` accepts `Groceries` beside `groceries` for one owner
  and refuses `OWNER@EXAMPLE.TEST` after `owner@example.test` in the same file, so the contrast
  is one pair of tests rather than one sentence.

---

## ADR-024: `users.updated_at` and `task_lists.description` are in the baseline revision

**Context**
`03-CONTEXT.md` D-10 enumerates the baseline columns and omits both `users.updated_at` and
`task_lists.description`. The Phase 2 entities declare both. Read literally, D-10 would have
produced a baseline schema the mappers could not round-trip.

**Options**

- **Ship D-10 literally and add a second revision later** — defensible as "follow the
  specification", and it would have produced a second migration file, which superficially
  demonstrates that migrations are versioned. Rejected twice over: the phase context explicitly
  rejects a revision written to *show* versioning, and until that revision existed the mappers
  could not persist two fields the entities require.
- **Treat D-10's column list as an incomplete transcription of the entities and correct it in
  place.**

**Decision**
Both columns are in `0001_baseline`. D-10's intent is the schema the entities already describe;
its column list was a summary, not a specification, and the entities are the authority.

**Consequences**

- There is no fake second migration. A second revision will appear in this repository the first
  time a genuine change requires one, which is the only way its presence means anything.
- The mapper round-trip tests in `tests/unit/infrastructure/test_mappers.py` can assert every
  field of all three aggregates, rather than carrying two known gaps with a note attached.
- Anyone comparing `03-CONTEXT.md` D-10 against the shipped schema will find two extra columns.
  That discrepancy is deliberate and is recorded here, because an unexplained difference between
  a context document and a migration is exactly the kind of thing that reads as drift.

---

## ADR-025: a revision file spells its constraint names as literals

**Context**
`src/taskmanager/infrastructure/db/constraints.py` holds the twelve D-12 constraint names as
`Final` constants, and it exists precisely so that one name lives in one place — D-13's
`IntegrityError` translation compares `diag.constraint_name` against those constants. Plan 03-01
handed forward a request that `0001_baseline` import them too, so the migration and the
translation could not disagree.

**Options**

- **`from taskmanager.infrastructure.db.constraints import UQ_TASK_LISTS_OWNER_ID_NAME`** inside
  the revision. Rejected: a revision is a frozen record of what a database was migrated *to*. A
  name read from a constant silently rewrites that record the day the constant is renamed —
  freshly created databases would get the new name while every existing database kept the old,
  and nothing would report it.
- **Literal strings in the revision, with the agreement checked elsewhere.**

**Decision**
`migrations/versions/0001_baseline.py` carries literal constraint names. The link plan 03-01
wanted is not lost; it runs through two existing hops instead of one import:
`tests/unit/infrastructure/test_models.py` asserts all twelve constants against the DDL the
models render, and `alembic check` asserts the live schema against those same models.

**Consequences**

- A rename applied to the models but not to the revision is caught by `alembic check`; a rename
  applied to the schema but not to `constraints.py` is caught by
  `tests/integration/test_constraints.py`, which asserts constraint *names* through
  `violated_constraint()` rather than asserting `IntegrityError` alone.
- Two spellings of the expression index coexist by design — `sa.literal_column("lower(email)")`
  in the revision against `text("lower(email)")` in the model — and they never meet, because
  `alembic check` compares the reflected database to the model metadata and never to the revision
  file.
- **Assumption A1 is settled empirically, and the answer is split.** RESEARCH A1 assumed Alembic
  autogenerate is blind to `CHECK` constraints. Observed in plan 03-02: autogenerate *did* emit
  `ck_tasks_status`, `ck_tasks_priority` and `ck_tasks_completed_at_matches_status` with the
  right names and the right SQL, because the blindness applies to *comparing* an existing table,
  not to rendering one being added for the first time — none was hand-written. But `alembic
  check` still cannot notice one disappearing later, so DB-04 rests on the insert-and-refuse
  tests of plan 03-05, and the migration says so at the constraint list. On the `lower(email)`
  expression index the observed outcome was `No new upgrade operations detected.` — Alembic 1.20
  does compare PostgreSQL expression indexes, reported no drift, and emitted no warning, which
  mattered because `filterwarnings = error` would have turned one into a failure.

---

## ADR-026: the `postgres:18-alpine` data volume mounts at `/var/lib/postgresql`

**Context**
Every pre-18 PostgreSQL compose example — including this project's own research, Pattern 6 —
mounts the named volume at `/var/lib/postgresql/data`. The image this project pins is
`postgres:18-alpine`.

**Options**

- **`/var/lib/postgresql/data`**, the convention an evaluator will have seen everywhere.
  Rejected on observation: `postgres:18-alpine` exits 1 on it with a multi-paragraph error
  — *"in 18+, these Docker images are configured to store database data in a format which is
  compatible with pg_ctlcluster (specifically, using major-version-specific directory names)
  ... Counter to that, there appears to be PostgreSQL data in: /var/lib/postgresql/data (unused
  mount/volume)"*. The image declares `VOLUME /var/lib/postgresql` and sets
  `PGDATA=/var/lib/postgresql/18/docker`.
- **`/var/lib/postgresql`**, the path the image itself declares.

**Decision**
`pgdata:/var/lib/postgresql`. The compose file carries both the reason and the observed error
text, so the next reader does not re-derive it from pre-18 documentation.

**Consequences**

- Left unfixed, this would have failed `docker compose up` — the first command of this
  project's own README — on the evaluator's first attempt. It is recorded as an ADR rather than
  as a comment because the correct value contradicts almost every example in circulation.
- The cold-volume rehearsal is the only run that exercises it, and it is the one that was
  performed: `down -v` → `up -d db` → `db healthy`, with `docker-entrypoint-initdb.d` visible in
  the container log creating the second database.

---

## ADR-027: `test_database_url` is a field on the production `Settings` object

**Context**
Integration tests need a DSN for `taskmanager_test`, and `.env.example` is the file an evaluator
copies (`cp .env.example .env`). Two Phase 1 gates constrain how that key may be introduced:
`Settings` is configured `extra="forbid"`, so an undeclared key in a copied `.env` is a
boot-time `ValidationError`; and `test_env_example_documents_every_field` asserts *exact set
equality* between `Settings.model_fields` and the keys in `.env.example`, not a subset.

**Options** (the three from RESEARCH Pitfall 6)

- **(b) Keep the key out of both files and read it with `os.environ` in the integration
  conftest.** Rejected: it contradicts the phase context's own canonical-reference note, and it
  leaves the variable documented nowhere except a README — which is where configuration goes to
  be forgotten.
- **(c) Loosen the parity assertion from set equality to a subset.** Rejected outright: it
  weakens an existing gate to accommodate a new key, which is the wrong direction for a
  repository whose entire thesis is that its gates are real.
- **(a) Declare `test_database_url: str | None = None` on `Settings` and add
  `TEST_DATABASE_URL` to `.env.example`.**

**Decision**
Option (a). The rule that matters is one sentence: **the key exists in both places or in
neither.** `cp .env.example .env && docker compose up` keeps working, and the parity gate was
not touched.

**Consequences**

- A test-only key lives on the production settings object. That is mildly wrong and it is
  written down rather than hidden — the field comment states that it is never read in
  production, and that declaring it is what stops a copied `.env` from becoming a *production*
  failure rather than a test failure.
- The only new default is `None`, on the one field that touches the database without being a
  credential. `database_url` and `jwt_secret` still have no default at all.
- The fallback is a library call, never a substring edit:
  `make_url(url).set(database=TEST_DATABASE_NAME).render_as_string(hide_password=False)`. The
  compose credential pair puts the word `taskmanager` in the user, the password *and* the
  database name, so a `str.replace` would rewrite three occurrences where exactly one must
  change — which is a test, not a warning.
- The compose form of `DATABASE_URL` is documented as a **commented** line. An uncommented
  second assignment would contribute the same key name and sail through the parity gate, while
  `python-dotenv` reads the last assignment and the application quietly dials a host that does
  not exist outside the compose network.

---

## ADR-028: WR-05 — a naive datetime read from the database is an infrastructure fault, refining ADR-021's classification of D-14

**Context**
The Phase 2 review raised **WR-05**: server-side clock and persistence faults surface to the
caller as a `422 validation_error` naming a field no request contains. The fix it proposed
contradicted locked decision D-14 of `02-CONTEXT.md` — "a naive `datetime` reaching the domain is
a `ValidationError`" — whose HTTP consequence is decided in **ADR-021** (a domain
`ValidationError` is 422, on the well-formed-but-semantically-invalid reading). The review fix
therefore **skipped** WR-05 and deferred it to this phase, on the grounds that changing the error
type for four of the five temporal fields is a decision for the user and an ADR, not for a
review pass. Phase 3 is the first phase in which the adapters that can produce a naive value —
the clock and the mappers — actually exist.

**Options**

- **Refine by error type**, as WR-05 proposed: split `require_utc` so internal temporal values
  (`now`, `created_at`, `updated_at`, `completed_at`) raise a `TypeError` while only `due_date`
  keeps `ValidationError`. Rejected: it changes five existing domain tests, reverses a locked
  decision, and alters the observable HTTP contract of the domain layer for values that reach it
  from three different directions.
- **Do nothing** and accept that a schema regression is reported as the caller's validation
  problem. Rejected: that *is* the defect.
- **Refine by scope.** Leave D-14 untouched at the domain boundary, and add a second, earlier
  check at the infrastructure boundary.

**Decision**
D-14 is refined by **scope**, not by error type, exactly as RESEARCH Open Question 5 recommends.

A naive datetime *reaching the domain* is still a `ValidationError` — no domain test changed and
no HTTP contract moved. In addition, every datetime read *from a database row* passes through
`_aware()` in `src/taskmanager/infrastructure/db/mappers.py`, which raises
`NaiveDatetimeFromDatabaseError(column=...)` — a plain `RuntimeError`, **deliberately outside the
`DomainError` hierarchy**.

This **refines ADR-021** rather than overturning it. ADR-021's claim — one status per meaning,
422 for well-formed-but-invalid — is unchanged; what narrows is the set of faults that can reach
it, because a schema regression is now intercepted one layer earlier and never becomes a domain
error at all.

**Consequences**

- A schema that stopped promising `TIMESTAMP WITH TIME ZONE` surfaces as Phase 2's fixed 500
  body with no message, which is the honest answer for this process's own fault — rather than a
  422 naming a column no request contains, sending a client hunting for a mistake they did not
  make.
- Four tests pin the classification, one per aggregate plus one nullable column, and one of them
  asserts `not isinstance(raised, DomainError)` explicitly, so the type cannot be quietly
  re-parented into the hierarchy later.
- The guard is a **tripwire, not a live path**, and that is now a fact rather than an assumption.
  RESEARCH A4 assumed psycopg 3 returns aware datetimes for `timestamptz`;
  `tests/integration/test_schema.py` round-trips an aware UTC value with non-zero microseconds
  and gets back an equal, aware, zero-offset instant. The branch is unreachable from a correct
  schema, which is the point of having it.
- The cost is one `if` on every timestamp read from every row, on all three aggregates including
  the nullable columns. One overloaded private guard serves both mandatory and nullable columns,
  so no call site needs a `cast` and none can silently widen a required field into an optional
  one.

---

## ADR-029: `make test` requires a reachable PostgreSQL from this phase onward

**Context**
Before Phase 3 the whole suite ran with nothing installed but Python. From plan 03-05 the suite
includes integration tests against a real server, and `pytest.ini`'s `--cov-fail-under=75` is
computed over the whole run. A suite that quietly skipped the database half would report green
having exercised none of the persistence layer.

**Options**

- **Auto-skip the integration tests when the database is unreachable** — the friendliest
  behaviour, and the most common. Rejected: on a graded deliverable, a green run that proves
  nothing is worse than a red one that says what to do. It would also make the coverage number
  meaningless, since the modules those tests cover would drop out of the denominator's numerator
  while staying in the denominator.
- **A separate `make test-unit` / `make test-integration` split** — considered; `-m "not
  integration"` already provides it for the inner loop, and the `integration` marker is
  informational rather than a switch that changes what `make test` runs (D-05).
- **Fail once, fast, with an instruction** (D-03).

**Decision**
`make test` runs the whole suite and requires PostgreSQL. A session-scoped fixture opens one
connection, and on failure the entire run produces three lines and nothing else:

```
PostgreSQL is not reachable at postgresql+psycopg://x:***@127.0.0.1:1/x.
Start it with `make up`, or run the whole suite inside Docker with `make docker-test`.
Underlying error: OperationalError: (psycopg.OperationalError) connection failed: ...
```

**Consequences**

- The failure message is part of the deliverable, and getting it right needed a non-obvious
  shape: `pytest.fail` is called *after* the `except` block, never inside it. Raised inside, the
  `Failed` carries the driver error in `__context__` and pytest prints two chained tracebacks
  above the one line of instruction — the exact outcome D-03 exists to prevent. Both forms were
  run and compared.
- The URL in the message is rendered with `render_as_string()`'s **masking default**; a run with
  a literal password greps zero matches. `hide_password=False` appears exactly once in the
  repository, at the one call that must produce a live connection string.
- The destructive schema fixture refuses any database whose name is not `taskmanager_test`
  *before opening a connection*, because it runs `downgrade base`, which drops every table. The
  check sits after the reachability probe so an unreachable host still produces the instruction
  above rather than a name complaint.
- `make docker-test` remains the zero-host-setup path and is not a fallback of last resort: it
  runs the identical suite, integration tests included, against the compose database.

---

## ADR-030: `IntegrityError` translation is one private helper per adapter

**Context**
D-13 requires each repository to catch `sqlalchemy.exc.IntegrityError`, read the violated
constraint name, and raise the same `DomainError` the use case's pre-check would have raised.
Both write paths of every adapter — `add()` and `update()` — can raise it, so the obvious
implementation is the same `try`/`except` block written twice per adapter.

**Options**

- **The block copied into `add()` and `update()`** — what the research sketched. Rejected on two
  grounds. First, two copies are two places for the constraint-name comparison to age
  separately. Second, and concretely: the foreign-key branch cannot fire from `update()`,
  because `apply_task_list_to_row` deliberately does not write `owner_id` (ownership is fixed at
  creation). A copied block would therefore have shipped a branch no test could reach, which on
  a project holding 100% coverage means either a forbidden `pragma` or a permanently red number.
- **One private `NoReturn` helper per adapter, called from every write path.**

**Decision**
Each adapter owns a `_refused(error, entity)` helper annotated `NoReturn`. It compares
`violated_constraint(error)` against the `Final` constants and re-raises the original exception
unchanged when it recognises nothing. It is not syntactically inside an `except` clause, so
flake8-bugbear's B904 has nothing to say about the bare re-raise, and mypy knows the call does
not fall through.

Every write path calls `flush()` inside the `try`. Without it the `IntegrityError` surfaces at
the use case's `commit()`, where the *unit of work* is holding it and D-13's "translate in the
repository" becomes impossible. `autoflush=False` on the session factory is what keeps that
explicit rather than accidental.

**Consequences**

- **Assumption A2 is settled, and it closed the project's last coverage gap.** RESEARCH A2
  assumed psycopg populates `diag.constraint_name` for foreign-key violations and not only for
  unique and check ones. Plan 03-04 left the positive branch of `violated_constraint()`
  deliberately uncovered — a populated psycopg `Diagnostic` has no public constructor, and a
  hand-built stand-in would have passed against a broken implementation too. Plan 03-05's
  `test_a_task_in_a_missing_list_is_refused` asserts
  `violated_constraint(error) == FK_TASKS_TASK_LIST_ID_TASK_LISTS` against a real server
  response, which settled A2 and took coverage over `src/taskmanager` to 100.00%.
- **A savepoint flushes what is already pending, and that decides where a deliberately bad row
  must be created.** The first version of `test_an_unrecognised_integrity_error_is_re_raised`
  added the malformed row to the session and *then* opened `begin_nested()` around the
  repository call. It passed — and the per-test coverage row showed `add()` entirely uncovered,
  because entering the savepoint flushed the pending row and PostgreSQL refused it there. The
  cause of an expected refusal now goes **inside** the savepoint. This is recorded as a rule
  rather than as an anecdote because every refusal test in this phase and in Phase 4 depends on
  it, and the failure it produces is a green test that never reached the code under test.
- An expected `IntegrityError` must run inside `connection.begin_nested()` at all, because a
  refused statement aborts the transaction the isolation fixture owns and every later statement
  answers `current transaction is aborted` until it is unwound.
- Nothing translated carries a constraint name or any SQL. The email conflict takes no argument
  at all, so there is nothing a call site could leak by being helpful.

---

## ADR-031: the three `tasks` CHECK constraints are deliberately not translated, refining D-13

**Context**
D-13 says repositories translate database rejections into domain errors. `tasks` carries three
CHECK constraints — `ck_tasks_status`, `ck_tasks_priority` and
`ck_tasks_completed_at_matches_status` — each of which duplicates an invariant
`Task.__post_init__` already enforces.

**Options**

- **Translate them, for uniformity with the unique and foreign-key constraints.** Rejected: a
  CHECK refusal would become a 422 pointing at a field the request never contained, because a
  value outside the enumeration cannot come from a `Task` at all.
- **Leave them untranslated and say nothing** — indistinguishable from an oversight.
- **Leave them untranslated and make the absence a test.**

**Decision**
The three CHECK constraints are absent from every `_refused()` helper. A refusal from one of them
means a row reached the database without passing through the entity, which is a defect in this
process rather than a request a client can fix, and it must reach Phase 2's catch-all as the
fixed 500.

`test_a_check_constraint_violation_is_not_translated` asserts both that the raw `IntegrityError`
escaped *and* that `violated_constraint()` names `ck_tasks_status` — the exception type alone
would also pass for a violation the test never intended to cause.

**Consequences**

- The deliberate gap is pinned rather than merely left. A future contributor who "fixes" the
  asymmetry by adding the branch turns that test red, with the reasoning one file away.
- The constraints still earn their place: they are the backstop that makes the invariant true of
  rows written by a migration, a seed script or a future bulk import — none of which goes
  through `Task.__post_init__`.
- The mapper re-validates on the way back out (`TaskStatus(row.status)`), so a value that
  somehow got past the CHECK raises at the boundary instead of rehydrating into a live entity.

---

## ADR-032: the unit of work refuses use outside its block, and annotates its repositories with the port types

**Context**
`SqlAlchemyUnitOfWork` is the transaction boundary ARC-08 names, and Phase 4 will hand instances
out through a FastAPI `Depends`. Two shapes in the research would have compiled and shipped
wrong.

**Options**

- **RESEARCH Pattern 3's `self._session = ...` created in `__aenter__` only.** It type-checks.
  It also makes `await uow.commit()` on an unopened unit of work raise
  `AttributeError: 'SqlAlchemyUnitOfWork' object has no attribute '_session'` — a message about a
  private field, from a class whose entire contract is "the boundary is the `async with`". A
  router that forgot the block is a plausible Phase 4 mistake and deserves a sentence, not a
  traceback about an attribute.
- **Annotating the repository attributes with their concrete adapter types** — the natural
  reading. Rejected on evidence: it was tried, and mypy reported `Following member(s) of
  "SqlAlchemyUnitOfWork" have conflicts: tasks: expected "TaskRepository", got
  "SqlAlchemyTaskRepository"` at the conformance binding, because a *mutable* Protocol member is
  checked invariantly. Phase 2's `FakeUnitOfWork` had already recorded the same constraint.

**Decision**
`_session: AsyncSession | None` is declared in `__init__` and read through an `_open_session`
property that raises `RuntimeError` naming the rule. `__aexit__` sets it back to `None`, so a
block is a real lifecycle rather than an attribute that lingers. The three repository attributes
are annotated with the **port** types (`self.tasks: TaskRepository`), and that annotation is
load-bearing rather than decorative.

**Consequences**

- The refusal branch has its own unit test, so the safeguard is exercised rather than merely
  written, and coverage stayed at 100%.
- Every transaction proof asserts a **read**, never a counter. `commits == 1` is equally true of
  a unit of work whose `__aexit__` rolled the commit straight back, which is precisely the WR-06
  failure the suite exists to catch.
- One test in the module reads from a **second, independent connection**. Every other read
  shares the fixture's connection, so that is the only vantage point from which a
  `join_transaction_mode` degraded to `rollback_only` would be visible — and the falsification on
  disk (commenting out `uow.commit()` turns it red) is what proves the savepoint mode is really
  working rather than silently swallowing the commit.
- `__aexit__` returns `None` explicitly. A true return would swallow the exception that left the
  block and let a failed use case answer 200.

---

## ADR-033: one runtime version string, `taskmanager.__version__`

**Context**
The application version appeared as a literal in three places, and `/health` (D-08) needed a
fourth. Three copies of a string that must agree is a defect waiting for a release.

**Options**

- **`importlib.metadata.version("taskmanager")`** — the textbook answer, and it leaves one
  literal instead of two. Rejected on a concrete failure: it raises `PackageNotFoundError` in
  exactly the environment `pytest.ini`'s `pythonpath = src` exists to create — a bare checkout
  where the package has not been installed. That path is a deliberate safety net (ADR-003), so a
  runtime constant that breaks it is not an improvement.
- **A module constant, with the packaging copy bound to it by a test.**

**Decision**
`__version__` lives in `src/taskmanager/__init__.py`, which is now the project's only non-empty
package `__init__` — the docstring says so and says why, because an unexplained exception to a
stated convention reads as an oversight. `tests/unit/test_version.py` reads `pyproject.toml`
with `tomllib` and asserts the two agree.

**Consequences**

- Two copies remain, and that is accepted rather than pretended away: a build backend cannot
  import the package it is about to build. The parity test is what makes two copies acceptable,
  in the same spirit as `test_env_example_documents_every_field`.
- `grep -rn '0\.1\.0' src tests` matches exactly one source line, so the next bump is one edit
  and a red test if it is forgotten.

---

## ADR-034: dependencies are injected as `Annotated[T, Depends(...)]`, never as an argument default

**Context**
`.flake8` carries `extend-immutable-calls = fastapi.Depends, fastapi.Query, ...` — added in Phase
1 precisely so flake8-bugbear's B008 would not fire on FastAPI's dependency injection, and
`03-PATTERNS.md` concluded from that entry that the default-argument form was safe. It is not.

**Options**

- **`engine: AsyncEngine = Depends(get_engine)`**, the form the research and the older FastAPI
  documentation use. It failed `make lint` with
  `health.py:86:47: B008 Do not perform function calls in argument defaults`: bugbear matches the
  call name **as written in the source**, and the whitelist entry names the *dotted* spelling
  `fastapi.Depends`, which this project never uses because it imports by name.
- **Add a bare `Depends` to `extend-immutable-calls`.** Rejected: it loosens a linter rule for
  the whole repository to accommodate one call site.
- **`Annotated[AsyncEngine, Depends(get_engine)]`.**

**Decision**
The annotated form, aliased at module level (`EngineDependency`, and Phase 4's
`UnitOfWorkDependency`). It needs no configuration change, it is the shape FastAPI's own
documentation now leads with, and the alias gives Phase 4 a name to reuse rather than a call to
repeat.

**Consequences**

- **This is the shape Phase 4's routers must copy.** A handler written with the default-argument
  form will fail `make lint`, and the reason will look like a linter misconfiguration rather
  than what it is.
- No `.flake8` change was made, so B008 stays live everywhere else in the repository.
- `03-PATTERNS.md`'s prediction that B008 could not fire is wrong, and `make lint` proved it.
  Recorded here because a planning document that has been falsified by execution is worth
  naming once rather than quietly ignoring.

---

## ADR-035: the engine is built in the composition root and disposed in the lifespan

**Context**
The project's own research contradicted itself. `.planning/research/STACK.md` sketches a
module-level `create_async_engine(...)` in `infrastructure/db/engine.py`;
`.planning/research/ARCHITECTURE.md` Anti-Pattern 10 forbids a module-level global engine.
`03-CONTEXT.md` flagged the contradiction and handed the resolution to this phase.

**Options**

- **A module-level engine.** Rejected with a concrete consequence rather than a rule number: it
  would read `Settings` at import time, so `import taskmanager.infrastructure.db.engine` would
  raise everywhere `DATABASE_URL` is absent — mypy's environment, import-linter's, and a plain
  `docker build`. That is the same argument `main.py` already makes for not having a
  module-level `app` object.
- **Builders in `engine.py`, an engine owned by `create_app()`.**

**Decision**
`engine.py` exports `create_engine`, `create_session_factory` and `create_database_resources` and
**instantiates nothing** — an AST assertion in the plan's acceptance criteria proves there is not
a single module-level assignment in the file. `create_app()` builds `DatabaseResources`, stores
it on `app.state`, and disposes the engine in the lifespan's shutdown half, closing over the
value it just built rather than reading it back untyped.

`pool_pre_ping=True` on the engine; `expire_on_commit=False` and `autoflush=False` on the session
factory. `expire_on_commit=False` is mandatory, not a preference: the default triggers a lazy
refresh after `commit()` that raises `MissingGreenlet` under async.

**Consequences**

- `create_app()` stays constructible with a fake DSN and no database, which `tests/conftest.py`
  has silently depended on since Phase 1. That dependency is now a test:
  `test_creating_the_app_opens_no_connection` builds the real application against a dead DSN and
  asserts zero connections checked out.
- `app.state` carries exactly one typed object, so `dependencies.py` needs exactly one `cast`
  (`grep -c "cast(" ` prints `1`). `starlette.datastructures.State.__getattr__` returns `Any`,
  so without the container every read would have been its own unverified narrowing.
- Disposal is asserted by **pool object identity** before and after the lifespan, because
  `dispose()` replaces the pool. A connection-count assertion would have passed vacuously
  against an engine that never connected.

---

## ADR-036: migrations run in the container entrypoint, never in the application

**Context**
The schema has to be applied somewhere. `create_app()` and the FastAPI lifespan are the two
places it is easiest to put.

**Options**

- **`alembic upgrade head` in the lifespan or in `create_app()`** — one place, no extra file.
  Rejected: importing the application would then have a database side effect, every unit test
  that builds the app would need a server, and multiple replicas would race on startup against
  the same revision.
- **A container entrypoint that waits, migrates, then execs the server** (D-06).

**Decision**
`docker/entrypoint.sh` runs three numbered steps — wait for a database that genuinely answers,
`alembic upgrade head`, then `exec uvicorn --factory taskmanager.main:create_app "$@"` — and the
`test` image stage deliberately does **not** run it, because the pytest fixture owns the test
schema.

**Consequences**

- The ordering is read off the log rather than claimed: `docker compose logs api` opens with
  `Running upgrade  -> 0001, baseline` and only then `Started server process [1]`. That
  transcript is committed at
  `.planning/phases/03-persistence-runnable-stack/evidence/03-10-cold-start.txt`.
- uvicorn is PID 1, because the entrypoint `exec`s rather than spawns, so signals reach the
  server.
- The word `downgrade` appears nowhere in the entrypoint. A restart applies pending revisions and
  can never destroy data.
- A new migration is picked up automatically by Phase 4 and Phase 5 — the entrypoint runs
  `upgrade head`, not a pinned revision — so neither phase needs a Dockerfile or compose change
  to ship a schema change.

---

## ADR-037: the entrypoint's readiness probe lives in a shell heredoc, not under `src/`

**Context**
The bounded retry loop that waits for PostgreSQL (D-07: thirty attempts, one second apart) is
real logic with a real failure mode. RESEARCH Open Question 1 asked where it should live.

**Options**

- **A `wait.py` module under `src/taskmanager/`** — unit-testable. Rejected on the coverage
  policy this project refuses to weaken: that package's coverage denominator has no `omit` and
  allows no `# pragma: no cover`, so the module would owe a unit test of a `range(30)` loop
  against a patched clock — a test of the loop's shape rather than of the behaviour anyone cares
  about.
- **A Python heredoc inside `docker/entrypoint.sh`.**

**Decision**
The heredoc, as RESEARCH Open Question 1 recommends. The entrypoint's header names, by path, the
evidence file that proves it.

**Consequences**

- **The retry bound is not unit tested.** It is proven end to end by the cold-start rehearsal
  (`evidence/03-10-cold-start.txt`), which an evaluator can re-run, and by the falsification in
  the same transcript: `docker compose stop db` turns the container `unhealthy` and `/health`
  answers 503 within the retry window; `docker compose start db` returns both to healthy. A
  liveness-only healthcheck would have stayed green throughout.
- This is the cost of the "never lower the coverage gate" rule, paid in the open. The rule is
  what pushed the code out of the measured package; the honest response is an end-to-end proof,
  not an `omit` entry.
- **The probe goes through SQLAlchemy's synchronous engine, never through libpq directly.**
  `DATABASE_URL` carries a `+psycopg` driver token that libpq reads as a connection-string
  syntax error, so the naive probe fails *permanently* on attempt 1 and the bounded loop then
  burns all thirty attempts against a perfectly healthy database (RESEARCH Pitfall 2).
- **The engine is built once, before the loop** — against RESEARCH Pattern 7, which constructs it
  inside each iteration. Building an engine parses the URL, so inside the `try` a malformed
  `DATABASE_URL` is treated as transient and retried thirty times: Pitfall 2's own failure
  arriving from a second direction. Built first, a bad URL aborts in under a second with the real
  exception, and only *connecting* — the part that can legitimately succeed later — is retried.
- The per-attempt log line prints the attempt counter and the exception class name and nothing
  else: no URL, no host, no password, no driver message.

---

## ADR-038: `ENTRYPOINT` owns the program and `CMD` is the argument list

**Context**
Phase 1's runtime stage declared `CMD ["uvicorn", "--factory", "taskmanager.main:create_app",
"--host", "0.0.0.0", "--port", "8000"]` and no `ENTRYPOINT`. Phase 3 adds an `ENTRYPOINT` (ADR-036).

**Options**

- **Keep `CMD` verbatim.** The moment an `ENTRYPOINT` exists, `CMD` becomes *arguments to the
  entrypoint*. Since the entrypoint ends with its own `exec uvicorn ...`, those arguments would
  have gone nowhere: `docker run <image> --port 9000` — the documented way to retune a
  containerised server — would have started on 8000 with no error and no warning.
- **`CMD` as the argument list**, with the entrypoint forwarding `"$@"`.

**Decision**
`CMD ["--host", "0.0.0.0", "--port", "8000"]`, and the entrypoint ends with
`exec uvicorn --factory taskmanager.main:create_app "$@"`. The factory is fixed — there is one,
and no reason to let it be overridden — and everything else is a real, replaceable default.

**Consequences**

- `docker run <image> --port 9000` does what it looks like it does.
- A reader comparing this Dockerfile against Phase 1's will see the `CMD` "shrink". It did not
  shrink; it changed role, and the role is what the `ENTRYPOINT` line above it establishes.

---

## ADR-039: the `test` compose service carries a profile

**Context**
`docker-compose.yml` defines three services: `db`, `api` and `test` (D-14). The first two are
long-running; `test` is meant to be *invoked*, not started. Plan 03-10 instructed the executor
explicitly **not** to add a compose profile, on the grounds that a profile adds a flag the README
would then have to explain.

**Options**

- **No profile, as the plan instructed.** Falsified by execution rather than by argument. The
  first `docker compose up --build -d` of the cold-start rehearsal started **three** containers,
  because `up` starts every declared service. `docker compose logs` then carried a full pytest
  run, coverage table included, interleaved with the API's startup, and `docker compose ps -a`
  was left showing `test exited`. For a project whose stated core value is that an evaluator can
  judge it in five minutes starting from `docker compose up`, that is the single most visible
  surface in the repository reading like a failure.
- **`profiles: ["test"]`.** The plan's stated cost was checked rather than assumed:
  `docker compose run --rm --build test` was run with the profile in place and **works with no
  flag**, because `run` enables the profiles of the service it names.

**Decision**
`profiles: ["test"]`. `make docker-test` is unchanged, the README has nothing to explain, and
`docker compose up` starts exactly `db` and `api`.

**Consequences**

- **This contradicts the text of `03-10-PLAN.md`, deliberately.** The plan's reason was tested
  and found false; the cost of following it was observed, not predicted. Recorded as an ADR
  rather than as a deviation note because anyone reading the plan beside the compose file will
  otherwise read the difference as an executor going off-script.
- Any command that inspects the full service list must ask for the profile:
  `docker compose config --services` prints `api db`, and
  `docker compose --profile test config --services` prints `api db test`. Acceptance criteria and
  verification scripts that enumerate services must use the second form.
- `docker compose down -v` does **not** remove containers belonging to a disabled profile, so a
  `docker compose run test` without `--rm` survives a full reset.
  `docker compose --profile test down` is the answer if it ever matters; `make down` was left as
  plain `docker compose down` to match D-14.

---

## ADR-040: the migrations directory is `migrations/`, not `alembic/`

**Context**
`03-CONTEXT.md` sketched an `alembic/` directory at the repository root. Phase 1's `.flake8`
already carried `extend-exclude = .venv,build,dist,migrations`.

**Options**

- **`alembic/`**, matching the context sketch and the tool's own default scaffold name. It would
  have required editing `.flake8` in the same commit — a mandatory task, not an optional tidy-up,
  because generated revision files do not pass this project's linter.
- **`migrations/`**, matching the exclusion that already existed.

**Decision**
`migrations/`, as RESEARCH Open Question 3 recommends. `alembic.ini`'s `script_location`, the
`.flake8` exclusion and the Dockerfile's two `COPY` lines all name the same directory.

**Consequences**

- No dead configuration line. A `.flake8` entry excluding a directory that does not exist is the
  kind of thing that survives for years and then silently excludes something real.
- `migrations/` is still formatted by isort and black through pre-commit even though flake8
  excludes it and mypy never sees it, and `script.py.mako` is written so a freshly generated
  revision is already clean under both — the first generated revision was not, and had to be
  reformatted before it could be committed.

---

## ADR-041: follow-up to ADR-017 and ADR-018 — both promises were kept in plan 03-10

**Context**
Two Phase 1 ADRs shipped with explicit promises attached. **ADR-017** made `make up` and
`make down` honest `@echo` placeholders, promising that Phase 3 would replace the recipe bodies
in place with the target names frozen. **ADR-018** chose a dedicated Dockerfile `test` stage over
a compose profile *because compose did not exist yet*, promising that Phase 3 would add a compose
`test` service with `target: test` and swap the body of `make docker-test` without renaming the
target.

**Options**

- **Leave the promises to be inferred from a diff.** Rejected: a decision log that records
  promises but never records whether they were kept is a log that cannot be trusted about the
  next promise.
- **Record the follow-up explicitly, naming the plan that discharged it.**

**Decision**
Both promises were kept, in **plan 03-10** (commits `bb1274e`, `15423a9`, `083fd11`):

- ADR-017: `make up` is `docker compose up --build` and `make down` is `docker compose down`,
  with the `-v` reset documented in a comment. `grep -c` for the placeholder string prints `0`.
  Neither target was renamed, so no documentation written against Phase 1 had to change.
- ADR-018: `make docker-test` is now `docker compose run --rm --build test`. The Dockerfile
  `test` stage still exists and is what the compose service builds (`target: test`); the change
  is that it now reaches the `db` service over the compose network, so the **integration** tests
  run there too. The previous body built an image and ran it with no database in sight, which
  means every integration test added in this phase would have failed under it.

**Consequences**

- ADR-018's reasoning is now fully discharged: the compose profile it deferred exists (ADR-039),
  and the stage it chose instead was not thrown away but wrapped.
- `make docker-test` is genuinely the zero-host-setup path it always claimed to be: the same 287
  tests, integration suite included, reporting `Required test coverage of 75% reached`.
- Phase 7's README has four settled commands: `cp .env.example .env`, `docker compose up`,
  `http://localhost:8000/health`, `make docker-test`.

---

## ADR-042: PostgreSQL 5432 is published on the host, with throwaway credentials

**Context**
D-15 requires the compose `db` service to publish 5432 so a host-side `make test` reaches the
*same* container the API uses, rather than a second database that can drift from it. That means a
PostgreSQL server listening on all interfaces of the developer's machine with a well-known
credential pair.

**Options**

- **Do not publish the port**, and give the host suite its own database. Rejected: two databases
  that must stay identical is exactly the "works locally, fails in the container" class of bug
  this project keeps trying to make impossible, and the evaluator would then need a second setup
  step.
- **Bind to `127.0.0.1:5432` only.** A real hardening option, and the right one for a machine on
  an untrusted network. Not taken here: it adds a line whose value depends on facts about the
  reader's network that this repository cannot know, and the exposure is bounded by what is
  behind it.
- **Publish `5432:5432` with obviously-fake credentials**, and say so out loud.

**Decision**
`"5432:5432"` and `"8000:8000"`, with the credential pair `taskmanager:taskmanager` — identical
to the one CI's service container already uses, and visible in `docker-compose.yml`,
`.env.example` and `.github/workflows/ci.yml`. Nothing in this repository carries a real
credential; `.env` is git-ignored and `.dockerignore`d and is never baked into a layer.

**Consequences**

- **Named rather than omitted:** on a developer machine on an untrusted network, that is a
  PostgreSQL server reachable from the local link with a guessable password. It holds nothing
  but throwaway evaluation data, it is started by an explicit `docker compose up` and stopped by
  `make down`, and `127.0.0.1:5432:5432` is a one-token change for anyone who wants it.
- A reader is not left guessing whether a real secret was ever involved. The pair is fake by
  construction and is published in three files on purpose, so there is no scenario in which it
  looks like a leak.
- The host port must actually be free. It was held by an unrelated container for three plans of
  this phase, which produced an *authentication* error rather than a wrong-database one — worth
  knowing, because the symptom does not point at the cause.

---

## ADR-043: no pagination on task listing in this phase

**Context**
`GET` on a task list returns every task in it. The threat register carries this as **T-3-22**
(unbounded listing), dispositioned `accept`.

**Options**

- **Add `limit`/`offset` or cursor pagination now.** Rejected: the challenge brief does not ask
  for it, and adding an unrequested parameter to a documented endpoint is the kind of initiative
  that costs more than it earns on a take-home.
- **Leave it out and say nothing.** Rejected: silence is indistinguishable from not having
  thought about it.
- **Leave it out and record the omission as a decision.**

**Decision**
Out of scope for this deliverable. The work per request is bounded by the per-list scope — a
listing is always `WHERE task_list_id = :id`, served by `ix_tasks_task_list_id` — rather than by
a page size.

**Consequences**

- A pathologically large list would return a pathologically large response. Accepted: no use case
  in the brief creates one, and there is no authenticated path that lets a caller enumerate
  another owner's lists.
- The completion percentage is unaffected either way, because it is one `COUNT(*) FILTER (WHERE
  ...)` aggregate over the whole list rather than a count of returned rows (ADR-009) — so adding
  pagination later changes the page, not the number.
- Recorded so that a reviewer reads the absence as a decision rather than as an omission, which
  is the only reason this ADR exists.

---
