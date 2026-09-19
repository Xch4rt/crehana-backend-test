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
not touched. (ADR-084 later made step one `make env`; the argument
above is unchanged, only the command that writes the file.)

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
  (ADR-084 replaces the first of the four with `make env`.)

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
## ADR-044: `get_current_actor` is a seam, and it is not authentication

**Context**
Phase 4 ships the brief's mandatory use case 1.a — task lists and tasks over HTTP — before any
credential exists. Every command in the layer takes `actor_id: UUID` as its first field, and
`task_lists.owner_id` is a foreign key. Something has to answer "who is calling?" two phases
before the thing that can really answer it.

**Options**

- **Bring JWT forward into Phase 4.** Rejected: it drags registration, password hashing, the
  OAuth2 password flow and the 401 leg of the error contract into a phase whose success criteria
  say nothing about any of them, and it would make the CRUD slice untestable until all of it
  worked.
- **Take the identity from a request header** (`X-Actor-Id: <uuid>`). Rejected for being worse
  than the honest placeholder in the way that matters: it *looks* like a mechanism. A reviewer
  who sees a header being trusted has to work out whether it is a stub or a vulnerability, and
  every integration test would have been written against a wire format that Phase 5 deletes.
- **Get-or-create the user inside the dependency.** Rejected: a dependency that writes to the
  database on a read request owns a transaction it has no business owning (ARC-08), and it makes
  `GET /health` and `GET /api/v1/task-lists` differ in their side effects for no stated reason.
- **One dependency returning a fixed demo id**, in a module of its own.

**Decision**
`src/taskmanager/presentation/api/actor.py` holds `DEMO_USER_ID: Final[UUID]` and
`get_current_actor() -> UUID`, exposed as `CurrentActor = Annotated[UUID, Depends(...)]`
(ADR-034). Every router takes the caller from there and from nowhere else. Phase 5 replaces the
**body** of that one function with a token decode; no router signature, no schema, no command and
no use case changes. The module's own docstring opens by saying, in those words, that this is
**not authentication** — and `test_the_seam_says_it_is_not_authentication` asserts the phrase
against `inspect.getsource`, so moving the sentence into a comment still satisfies it while
deleting it fails the suite.

It is a separate module rather than a third provider in `dependencies.py` for two concrete
reasons: the entrypoint's seed (ADR-045) imports `DEMO_USER_ID`, and importing it from
`dependencies.py` would drag the whole database stack into a five-line script; and in Phase 5 the
seam is deleted as a *file* rather than edited out of one.

**Consequences**

- **The API has no access control against a stranger in Phase 4, and that is stated rather than
  implied.** Ownership *is* enforced — every use case compares `task_list.owner_id` with
  `actor_id` and answers 404 for anything else (D-04, ADR-008) — but with one fixed actor there is
  no second caller to enforce it against over HTTP. The rule is proven in the unit suite with two
  fake actors, and `acting_as(app, other_id)` in the integration harness exercises the same
  refusals through the real routes.
- The seeded row's `password_hash` is `!`, which is not a valid Argon2 encoded hash, so a pwdlib
  verification against it can never succeed. This identity cannot become a live account by
  accident when the login endpoint arrives.
- The identifier is a `Final` constant and not a setting (D-03). It is not configuration: nothing
  deploys differently because of it, and `.env.example` therefore gains no key an evaluator would
  have to be told to ignore.
- Phase 5's diff is small and readable: one function body, one deleted file, one deleted
  entrypoint block.

---

## ADR-045: the demo user is seeded by the container entrypoint, not by a migration

**Context**
ADR-044's fixed actor needs a `users` row to exist, because `task_lists.owner_id` references it.
On a fresh volume it does not, so an evaluator's very first `POST /api/v1/task-lists` after
`docker compose up` would be a foreign-key violation — which would defeat the entire point of the
seam.

**Options**

- **An Alembic data migration.** Rejected: a data row is not a schema change. It would make this
  identity part of the schema's recorded history, and Phase 5 could then only remove it by writing
  a second revision whose only job is to delete it.
- **Get-or-create inside `get_current_actor`.** Rejected with ADR-044, for the same reason.
- **A seed module under `src/taskmanager/`.** Rejected on the argument **ADR-037** already settled
  for the readiness probe: that package's coverage carries no `omit` entry and allows no
  `# pragma: no cover`, so a seed module would owe a unit test of a five-line `INSERT`, and it
  would add a node to import-linter's graph that has to import `presentation`.
- **An inline `python` heredoc in `docker/entrypoint.sh`**, after `alembic upgrade head`.

**Decision**
Step `2b` of `docker/entrypoint.sh`, between migrate and serve. It imports `DEMO_USER_ID` from
`actor.py` rather than pasting the literal, so the identifier still exists in exactly one place
(D-03), and it writes the row with `INSERT ... ON CONFLICT DO NOTHING` — **untargeted**.

The step is numbered `2b` rather than `3` because it is temporary: Phase 5 deletes it with the
seam, and `exec uvicorn` has been step 3 since Phase 3. Renumbering a permanent step for the sake
of a temporary one is a rename a future diff would have to undo.

**Consequences**

- **The untargeted conflict clause is load-bearing, not laziness.** The seed runs on every
  container start, so it must absorb every way the row can already be there. Run three times
  against the live database it produced rowcounts `1, 0, 0`. A clause naming the primary-key
  column as its target absorbs the second run and **not** the third: with a different id and the
  same address it raises `duplicate key value violates unique constraint "uq_users_email_lower"`,
  and under `set -eu` that aborts the container on a restart. Both forms were executed and both
  transcripts are in
  `.planning/phases/04-task-lists-tasks/evidence/04-11-seed-idempotence.txt`; executions 1 and 2
  are byte-identical between them, which is exactly why a proof that only restarted with the same
  id would have passed against the form that breaks.
- No coverage exemption is bought. The heredoc is not a module under `src/`, so it adds no node to
  import-linter's graph and cannot break a contract — confirmed by running `make arch`, not
  assumed.
- The behaviour is proven end to end rather than by unit test, in
  `.planning/phases/04-task-lists-tasks/evidence/04-11-cold-start.txt`: an empty volume reaching
  `api healthy`, and `POST /api/v1/task-lists` answering `201` on the fresh stack with no setup.
- The seed proof deliberately ran against `taskmanager_test`, never `taskmanager`: its third
  execution attempts a second row and its cleanup deletes by email, and pointing a destructive
  statement at the database `docker compose up` serves would have bought nothing.
- Phase 5 deletes this block and `actor.py` together.

---

## ADR-046: "field not provided" is a single-member enum in the application layer, refining ADR-020

**Context**
D-05 gives PATCH JSON Merge Patch semantics: an omitted key leaves a field unchanged, an explicit
`null` clears a nullable one. A command DTO therefore has to carry three states per field —
absent, null, value — and it has to do so under `mypy --strict` in a layer that ADR-020 keeps free
of Pydantic.

**Options**

- **`None` as the marker.** Rejected outright: `None` is a legal *value* for every nullable PATCH
  field, so the command could not tell "leave this alone" from "empty this", and the two produce
  different rows.
- **A bare `_UNSET = object()`.** Distinguishes them at runtime and gives mypy nothing: `str |
  object` collapses to `object`, so a use case that forgot its guard and passed the sentinel into
  `Task.rename` would type-check and fail in production.
- **`fields_set: frozenset[str]` beside the values.** Rejected: it moves the question from the
  type system to a runtime string comparison, and a typo in the set is invisible to every gate.
- **A per-field `Patch[T]` wrapper** (`provided: bool`, `value: T`). Narrows correctly, and was
  rejected for cost rather than correctness: every read becomes `command.field.value` behind
  `command.field.provided`, and it adds a second DTO vocabulary beside ADR-020's frozen dataclasses
  for no behaviour the enum does not already give.
- **A single-member enum**, `class Unset(Enum): TOKEN = "unset"`, with `UNSET: Final = Unset.TOKEN`.

**Decision**
The enum, in `src/taskmanager/application/dto/unset.py`. mypy treats `value is not UNSET` as a
literal narrowing, so inside the guard `str | Unset` is `str`, and omitting the guard is an
`arg-type` error at the call site rather than a runtime surprise. The narrowing was verified by
deleting a guard and observing mypy report it.

**The sentinel stops at the application boundary, and that is the measured half of this decision.**
Declaring it in the Pydantic request schemas was executed (04-RESEARCH Pattern 2) and produced two
observable defects: a `_Unset` component published into `/openapi.json` as part of the field's
`anyOf`, and the explicit-null refusal split across two error entries, at `body.title.str` and
`body.title.enum[_Unset]`, neither of which a client can act on. The schemas therefore declare
plain `X | None = None` and the mapper converts on the way in.

**Consequences**

- The application layer stays Pydantic-free without special pleading, which keeps ADR-020 intact
  rather than carving an exception into it.
- **The asymmetry with filters is deliberate.** `ListTasksCommand.status` and `.priority` are plain
  `X | None = None`, not sentinels: for a filter, "absent" and "null" are the same request, so
  there is only one meaning to express and a second marker would be ceremony every use case has to
  unwrap. The command's docstring argues this rather than leaving a reader to notice it.
- A live `None` leg follows from it: `if command.description is not UNSET:
  task_list.describe(command.description, now=now)` correctly passes `None` through to clear the
  field, and adding `and command.description is not None` would silently drop D-05's clear case.
- The mapper that produces the sentinel has its own cost, recorded in ADR-052.

---

## ADR-047: `updated_at` moves whenever a field is provided — and therefore not at all when none is

**Context**
Discretion item 2 of the phase context, and Assumption **A1** of `04-RESEARCH.md`: does a PATCH
whose values equal the current ones move `updated_at`? The update use cases are written as one
guard per patchable field, each calling one entity mutator, and every entity mutator stamps
`updated_at` unconditionally (Phase 2 D-04: the entity owns the rule, and it takes `now` as an
argument rather than reading a clock).

**Options**

- **Compare values first, and stamp only on a real change.** Rejected: it puts a second "did this
  actually change?" rule beside mutators that already stamp unconditionally, in a layer that is
  not supposed to be re-deciding entity behaviour. Phase 2 D-04 exists to stop exactly that
  duplication, and the comparison would have to be written once per field, per use case.
- **Stamp unconditionally at the top of `execute`.** This is what two Phase 4 plans' task text
  asked for in the all-omitted case. Rejected: it contradicts `04-PATTERNS` Pitfall 10 and the
  verified `UpdateTaskList` body in `04-RESEARCH`, and it would make a request that changed
  nothing indistinguishable, in the database, from one that did.
- **Keep the guarded shape**, and accept the corollary.

**Decision**
The guarded shape, unchanged. `updated_at` moves whenever a field is *provided* — even to the
value it already holds — and a command carrying no field at all reaches no mutator and therefore
stamps nothing.

**Consequences**

- **No genuine no-op request exists over HTTP.** D-06 answers an empty body `{}` with a 422 at the
  schema, and `extra="forbid"` answers a body of only unknown keys the same way, so a command with
  every field `UNSET` can never be built from a real request. The corollary is nonetheless pinned
  by a test in both update suites (`updated_at == NOW`, `commits == 1`), because nothing upstream
  would reveal a change in it.
- Two plans (04-05 and 04-06) asked in their task text for the opposite assertion, and both
  executors recorded the contradiction rather than quietly implementing the plan or quietly
  implementing the research. The reasoning is in each use case's test docstring.
- A client that PATCHes the same name twice sees `updated_at` advance twice. That is the honest
  reading of "this resource was written to", and it is cheaper than a correctness rule duplicated
  in ten places.

---

## ADR-048: one door into the state machine — a dedicated status endpoint

**Context**
The brief lists "change a task's status" as a use case of its own, separately from "update a
task". The status field is the one field in this API governed by a transition matrix
(`pending → in_progress → completed`, Phase 2 D-01), with an observable side effect on
`completed_at`.

**Options**

- **A writable `status` in the generic `PATCH /tasks/{id}`.** Rejected: it gives the state machine
  a second entrance, and the generic PATCH's other fields have no transition rules at all, so one
  request body would carry two different validation regimes.
- **Action verbs**, `POST /tasks/{id}/complete` and a reopen counterpart — the shape **Todoist**
  actually ships (`/close`, `/reopen`), so the alternative is genuinely defensible rather than a
  strawman. Rejected here because the transition has no side effect beyond the field and a
  timestamp, and one endpoint covers all transitions instead of three verb routes.
- **`PATCH /api/v1/task-lists/{list_id}/tasks/{task_id}/status`** with body `{"status": "..."}`.

**Decision**
The sub-resource PATCH (D-11), returning `200` with the full `TaskResponse`. `status` is **not a
field of `TaskPatchRequest` at all** (D-08) — not a declared-and-refused field, simply absent —
so `extra="forbid"` turns a `status` key in the generic PATCH into exactly one `extra_forbidden`
error at `(status,)`. The test asserts `len(errors) == 1`, so a model that declared the field and
then refused it would still fail.

**Consequences**

- TASK-03's "`status` is not writable here" is proven **by absence** rather than by a guard
  somebody could delete: `test_status_is_not_writable_through_the_generic_patch` over HTTP, and a
  unit assertion that `UpdateTaskCommand` has no `status` field — together with `owner_id`,
  `assignee_id` and `completed_at`, so the mass-assignment surface is refused as a set rather than
  one field at a time.
- An invalid transition is a 409 whose problem body names `from` and `to`, produced by the domain
  and translated by the single handler — no router builds it.
- A same-state request is a 200 no-op with an unchanged body (Phase 2 D-02), which is an
  `Task.change_status` invariant rather than a use-case branch.
- The Todoist alternative is named here on purpose, so that a reviewer who prefers action verbs
  reads a decision rather than an oversight.

---

## ADR-049: the two response envelopes, refining ADR-009

**Context**
ADR-009 fixes *what* the completion percentage means — the whole list, one SQL aggregate, `0.0`
when empty. It does not fix what the HTTP responses carrying it look like.
`.planning/research/FEATURES.md` proposes a richer envelope than the phase context does.

**Options for the task collection**

- **The research envelope**: `list_id`, `completion_percentage`, `total_tasks`, `completed_tasks`,
  `returned_count`, an echoed `filters` block, and `items`.
- **The four-member envelope** of D-09: `items`, `total_tasks`, `completed_tasks`,
  `completion_percentage`.

**Decision**
Four members. `list_id` is the path segment the client just sent. `returned_count` is
`len(items)`. An echoed `filters` block restates the query string. Each is a second copy of
something already in the request, and a second copy is something that can disagree — which is
precisely the ambiguity the counters exist to remove.

For task lists, **one `TaskListResponse` shape everywhere** (D-10): the collection, the single
`GET`, the `POST` answer and the `PATCH` answer all carry `total_tasks`, `completed_tasks` and
`completion_percentage`. A list created one millisecond ago reports `0, 0, 0.0` rather than
omitting the block.

The sentence the research asked to be written down is worth writing down: **the percentage is a
property of the list, the filter is a property of the view.** That is the whole argument for the
statistics not moving when a filter is applied.

**Consequences**

- `TaskCollectionResult` carries the three statistics **flat**, not as a nested `CompletionStats`
  value object as the research example did. Flat keeps the response schema mapping one-to-one with
  the DTO and stops presentation reaching through a domain value object for a number;
  `from_parts(tasks, stats)` is where the unpacking happens, exactly once.
- `test_the_filter_never_moves_the_statistics` asserts that the **item counts differ** as well as
  that the three counters match, so it cannot pass vacuously against a filter that was silently
  dropped.
- One shape everywhere means the collection needs the statistics for every list in one query.
  That is the new port capability `list_for_owner_with_stats` and the grouped statement behind it
  (LIST-03), not an N+1 — see ADR-054.
- `returned_count` is recoverable by any client in one expression, so nothing was actually
  withheld.

---

## ADR-050: `ChangeTaskStatusCommand` gained `task_list_id`, so every task route honours its parent segment

**Context**
`ChangeTaskStatus` shipped in Phase 2 as the reference use case, with `actor_id` and `task_id` and
no parent. Phase 4's URL for it is nested — `/task-lists/{list_id}/tasks/{task_id}/status` — and
D-14 requires that a task addressed under a list it does not belong to answer `404`, identically
to an absent task. The Phase 2 command could not express that question. This was
`04-RESEARCH.md` Open Question 1.

**Options**

- **Ignore the parent segment on that one route.** Rejected: a nested path whose parent is not
  checked is a real defect, an evaluator finds it in one `curl`, and the inconsistency would be
  between two routes of the same resource.
- **Check the parent in the router**, before calling the use case. Rejected: it puts a visibility
  decision in the layer that cannot make one (ADR-008), and the unit suite would no longer prove
  the rule.
- **Add `task_list_id` to the command** and check it in the use case, like every other task verb.

**Decision**
The field was added (plan 04-03) and the shared guard `visible_task` compares the task's parent
**before** loading the addressed list — so a wrong-list request cannot reveal whether that list
exists either. Cost: one DTO field, one comparison, seven test call sites.

**Consequences**

- `PATCH .../status` answers the wrong-list 404 exactly as `GET`, `PATCH` and `DELETE` do; four
  HTTP tests, one per verb, assert it.
- All four refusal legs raise the **task-shaped** error carrying only the identifier the caller
  already supplied, and indistinguishability is asserted comparatively — both refusals produced
  and compared on type, code and details — because a single-error assertion passes just as happily
  against an implementation that leaks existence through a different code.
- A router that filled `task_list_id` from the task it had just loaded, rather than from the path,
  would restore the defect while keeping every unit test green. The use case's docstring says so.

---

## ADR-051: D-15 is two gates, and the import check is the load-bearing half

**Context**
Phase 2 deferred a gate: `fastapi.HTTPException` must never be raised below — or, as it turns out,
inside — the layer that answers business failures. A router that raises it has built an error body
by hand, bypassing the single RFC 9457 handler ARC-07 puts in charge, *and* has taken an
access-control decision in the one layer that does not know who owns what.

**Options**

- **An import-linter `forbidden` contract alone.** It works on *modules*, so it can say
  "`infrastructure` must not import `fastapi`" — but it cannot be pointed at `presentation`, which
  is supposed to import FastAPI. It cannot express "this symbol in particular".
- **An AST test alone**, walking `raise` statements under the routers package. It catches the
  direct, dotted and aliased spellings — and misses a construction bound to a local name and
  raised on the next line, which the research prototype demonstrated by being run against exactly
  that shape.
- **Both**, each answering the question the other cannot.

**Decision**
Both. `.importlinter` gains `no-http-below-presentation` (`domain`, `application`,
`infrastructure`; `fastapi`, `starlette`), and
`tests/architecture/test_routers_raise_no_http_exception.py` makes two passes over every module
under `presentation/api/routers`: one over `raise` statements, and one over imports and attribute
access. The second is the load-bearing one — a module that never binds the name cannot raise it by
any spelling — and the first is kept because it fails with the offending `file:line` rather than
with an import at the top of the file.

The import pass refuses the name **wherever it is bound**, not only from `fastapi` and
`starlette.exceptions` as the research recommends. Naming the two would tie the gate to a fact
about a dependency's layout rather than to the property, and a local re-export would walk straight
through it.

A third test asserts the scan is non-vacuous: a glob that matches nothing passes, so the suite
fails if the routers package is renamed or emptied.

**Consequences**

- **Neither gate adds a pre-commit hook or a CI step**, and that is the ADR-015 argument applied a
  third time (after plans 02-06 and 03-06): the contract rides inside `lint-imports`, which the
  hook and the CI step already run, and the AST test rides inside pytest, which the hook set, the
  Docker `test` stage and CI already run. ADR-015's "a new gate goes in two places" rule is about
  gates that introduce a *new command*, and neither of these does.
- Both were driven red before being trusted. The import-linter contract was planted twice, because
  the first planting — inside `application` — also broke the pre-existing
  `application-framework-free` contract and therefore proved only that the build goes red, not
  that the new contract earns its place. The second planting, in `infrastructure/db/engine.py`,
  reports **exactly one** contract BROKEN and it is the new one
  (`evidence/04-02-importlinter-red.txt`).
- The AST gate's first plant adds the import **as well as** the raise, because a raise of a name
  the module never bound is not a state this codebase could reach; the second plant is the import
  alone, and it is the run that proves the two assertions are not redundant — raise check green,
  import check red (`evidence/04-08-ast-gate-red.txt`).
- `EXPECTED_CONTRACT_NAMES` in `tests/architecture/test_layer_boundaries.py` now holds four names,
  so a contract added later must edit both files in one change or fail.

---

## ADR-052: the OpenAPI polish level in Phase 4, and the two corrections it forced

**Context**
`04-RESEARCH.md` Open Question 3, and discretion item 6: how much OpenAPI work belongs in a phase
whose requirement set does not include DOC-04?

**Options**

- **Nothing now; DOC-04 does it all in Phase 7.** Rejected: documenting a route months after
  writing it is how a summary ends up describing what the author remembers rather than what the
  route does.
- **Everything now, including a `ProblemDetail` Pydantic model** so the error bodies are typed in
  the schema. Rejected here: that model would exist *only* for documentation — nothing constructs
  it, nothing validates against it — and Phase 7 owns that budget.
- **Tags, `summary`, `response_description` and a status-keyed `responses` map per route now;
  the documented error model in Phase 7.**

**Decision**
The middle option, on all eleven routes. `test_every_api_route_is_documented` asserts all four
members on every `/api/v1` operation, so the twelfth route cannot arrive bare — a documented
contract with no gate is the one that drifts first.

**Two corrections followed from writing it:**

- **Every route also declares a `500` leg.** `GET /api/v1/task-lists` can produce no 404, no 409
  and no 422 — no path parameter, no body, no query parameter, and a caller who owns nothing gets
  `200` with `[]` — so taken literally it would have carried an *empty* `responses` map. The 500
  is Phase 2's fixed problem+json body: a real, documented outcome of every route in this API
  rather than padding.
- **Declaring `422` explicitly replaces FastAPI's generated `HTTPValidationError` entry, and that
  is the point.** This API answers 422 as RFC 9457 `application/problem+json`; the generated entry
  documented a shape no endpoint has ever returned. Superseding it with a description and no
  misleading `content` is more accurate than leaving it, and publishing the real component is
  DOC-04's work.

**Consequences**

- `/docs` is already close to DOC-04's bar, so Phase 7 adds one model rather than eleven routes'
  worth of prose.
- The `status` query parameter is spelled `status_filter` in Python with `Query(alias="status")`,
  because `tasks.py` imports `status` from FastAPI for the status-code constants. The public
  contract is unchanged and was *measured*: `?status=bogus` answers 422 with
  `errors[0].field == "query.status"`.
- The mapper that fills the ADR-046 sentinel uses `value is not None` for the **non-nullable**
  fields (`name`; `title`, `priority`) and the `model_fields_set` membership test for the nullable
  ones (`description`, `due_date`). The research and the plan wrote membership everywhere, and it
  does not type-check: the expression stays `str | None | Unset` where the command field is `str |
  Unset`. The equivalence for the non-nullable fields is exact rather than convenient — a field
  validator has already refused an explicit null for precisely those fields, so a `None` at
  mapping time can only mean the key was absent, and three tests assert that refusal. A `cast`
  would have stopped the type checker from checking, and an `assert` would have added a branch the
  no-`pragma` coverage rule needs an unreachable test for.

---

## ADR-053: where the research and the phase context disagreed, the context won

**Context**
`.planning/research/FEATURES.md` was written before the phase context was gathered, and it is the
document a reader most likely to "fix" the code back toward. It contradicts `04-CONTEXT.md` in
three places, and the code follows the context in all three.

**Options**
Leave the disagreement for a reader to discover and resolve on their own, or record it once so
that the older document is read as history.

**Decision**
Recorded, all three:

1. **An empty PATCH body `{}`.** FEATURES §3 says `200` with the resource unchanged, "an
   idempotent no-op". D-06 says `422 validation_error`. The context wins because a client that
   sends `{}` has almost certainly sent the wrong thing — a typo like `titel` is refused rather
   than silently ignored under `extra="forbid"`, and an empty body is the same mistake with
   nothing left in it. A 200 would report success for a request that did nothing. This also makes
   ADR-047's corollary unreachable over HTTP, which is why the two decisions are consistent rather
   than merely compatible.
2. **Multi-value filters** (`?status=pending&status=in_progress`). FEATURES lists them as a cheap
   "next level" feature. The context restricts each filter to a single value, combined with AND;
   multi-value is requirement **API-02**, explicitly v2. The brief names exactly two filters and
   says nothing about repeating them, and OR-within-field / AND-across-fields is a semantic that
   has to be documented, tested and explained.
3. **The richer task-collection envelope.** Covered by ADR-049.

**Consequences**

- A future reader of `FEATURES.md` sees three claims that the code does not implement, and this
  entry is where they find out that was a decision.
- `API-02` stays in the v2 list in `REQUIREMENTS.md` and is documented as pending in the README
  (DOC-02), so the omission is visible to an evaluator too.

---

## ADR-054: the whole-list statistics come from one grouped statement, and "no N+1" is measured

**Context**
ADR-049 puts `total_tasks`, `completed_tasks` and `completion_percentage` on **every**
`TaskListResponse`, including each element of `GET /api/v1/task-lists`. Computing that per list in
Python is the textbook N+1, and it is the pitfall the phase research flags by name.

**Options**

- **`completion_stats(list_id)` per list**, reusing the existing single-list aggregate. Rejected:
  correct and linear in the number of lists.
- **A new port capability returning lists and stats together**, satisfied by one grouped
  `LEFT JOIN ... GROUP BY` with `count(*) FILTER (WHERE status = 'completed')`.

**Decision**
`TaskListRepository.list_for_owner_with_stats(owner_id) -> Sequence[tuple[TaskList,
CompletionStats]]`. The port speaks domain types; the pair is a bare `tuple` rather than a new
`TaskListWithStats` value object, because that would introduce a domain concept only one query
needs and the naming belongs on the application result DTO (`04-RESEARCH` Open Question 2).

**Consequences**

- The compiled-SQL test asserts `count(tasks.id)` **present** and `count(*)` **absent**: the two
  render almost identically and differ exactly on the null-extended row an empty list produces,
  which is the difference between `0` and `1` total tasks for a list with none.
- The fake sorts its own pairs rather than delegating to `list_for_owner`, mirroring the adapter's
  two separate `ORDER BY` clauses — a delegation would keep the test green if the grouped
  statement lost its ordering.
- **D-17 is discharged by measurement, and the measurement corrected a plan.** A
  `before_cursor_execute` recorder asserts that the responses for one list and for many issue
  *byte-identical* statement recordings. For the task collection the count is **three**, not the
  two the plan predicted: the plan forgot `visible_task_list`, the ADR-008 guard that loads the
  parent list and discards it so an invisible list is refused before a single task is read. The
  measured number shipped, with all three named in `TASK_COLLECTION_STATEMENTS`. Removing the
  guard would have traded a security property of this same phase for a number in a planning
  document, and folding it into the page query would have dissolved the indistinguishability
  ADR-050 depends on. D-17 is about invariance, not about a magic number: none of the three is
  issued once per row, and the recording does not change with a filter either.

---

## ADR-055: the ADR-008 visibility rule lives in one module, `application/use_cases/access.py`

**Context**
Eleven use cases begin the same way: load the addressed resource, decide whether this actor may
see it, and refuse identically to an absent one if not (D-04, ADR-008). Before this phase the
block existed once, privately, inside `change_task_status.py`.

**Options**

- **A private function per use-case module**, which is what the reference use case did and is
  arguably more consistent with it. Rejected at ten copies: the rule is a security property, and
  ten copies age separately.
- **A `GuardedUseCase` base class or mixin.** Rejected, and for a specific reason: an inherited
  guard is invisible at the call site, so a subclass that overrode it, or a use case that simply
  did not inherit, looks exactly like one that did. A missing `await visible_task_list(...)` is an
  absent line in a diff.
- **A module of two functions**, called explicitly as the first statement inside the use case's
  `async with self._uow:` block.

**Decision**
`visible_task_list(uow, task_list_id, actor_id)` and `visible_task(uow, task_id, task_list_id,
actor_id)`, taking an **already-entered** unit of work. They neither open the block nor commit, so
the transaction boundary stays with the use case (D-17 of Phase 2, ARC-08) — asserted by a test
that both guards leave `commits` and `rollbacks` at zero. `grep -rn "visible_task" src/` is an
audit an evaluator can run in one command.

**Consequences**

- **The assignee clause was dropped, and the ASGN-02 test inverted.** `_may_change_status`
  previously allowed `task.assignee_id == actor_id`. No Phase 4 endpoint sets `assignee_id`, so
  keeping the clause would ship a branch no request can reach — which the no-`pragma` coverage
  rule cannot excuse. `test_change_task_status_allows_the_assignee_who_does_not_own_the_list`
  became `test_change_task_status_hides_the_task_from_its_assignee_for_now`, with a docstring
  saying what it used to assert and that Phase 5 turns it back. Two places name Phase 5 by number:
  that test, and `access.py`'s own docstring.
- `access.py` discusses the 403 question at length **without naming `AuthorizationError`**, and
  says in its docstring that it is doing so deliberately: nothing in Phase 4 can produce a
  visible-but-forbidden case, so the class does not appear.
- `CreateTask` is the deliberate exception to the task-shaped refusal: it refuses with the
  **list-shaped** error, because the caller addressed a list and no task exists yet — there is no
  task identifier to answer with. Its module docstring argues the exception at length so that a
  reader does not file it as an inconsistency.
- Phase 5 restores the assignee capability inside `access.py` and adds the project's first 403
  branch there, rather than inside any single use case.

---

## ADR-056: the HTTP harness overrides the unit-of-work dependency and never enters the lifespan

**Context**
D-16 requires every Phase 4 route to be tested over HTTP against the real `taskmanager_test`
database, under Phase 3's per-test rollback isolation. The application builds its engine in
`create_app` and disposes it in the lifespan (ADR-035), and the integration fixtures already own a
connection whose transaction is rolled back after each test.

**Options**

- **Enter the app's lifespan and let it build its own engine**, then somehow make the test's
  transaction and the app's sessions agree. Rejected: two engines, two pools, and an isolation
  story that depends on them cooperating.
- **Build the app against a fictional DSN, override `get_uow`**, and never enter the lifespan.

**Decision**
The second. `api_client` deliberately does **not** enter the lifespan: `get_uow` is overridden, so
the engine built against the fictional DSN is never dialled, and
`tests/integration/test_health.py` remains the one place the engine's own lifecycle is proven.

**Consequences**

- **`seed()` commits, and it has to.** Under `join_transaction_mode="create_savepoint"` a session
  closed without committing rolls its savepoint back, so seeded rows would vanish and the first
  request would 404. The commit releases the savepoint into the outer transaction the connection
  fixture still rolls back — isolation is unchanged, only visibility is bought.
- `acting_as(app, actor_id)` is a **restoring** context manager rather than a one-way setter,
  because a test that proved a 404 as a stranger and then asserted the owner's view would
  otherwise still be the stranger and pass for the wrong reason.
- The not-owned refusal is compared to the absent refusal **whole**, with each response's own
  identifier tokenised out by `anonymised(response, *ids)`. The plan asked for "identical apart
  from `instance`", but `instance` *is* the request path and therefore necessarily differs — so
  excusing it would have left the path entirely uncompared.
- 48 HTTP tests for the task routes and 31 for the task lists found **no** defect under `src/`.
  That is the payoff of the same behaviours having been proven against the in-memory fakes first,
  and it is recorded because a phase whose integration suite finds nothing is either well-built or
  badly written, and the distinction matters.

---

## ADR-057: route assertions read `app.openapi()["paths"]`, never `app.routes`

**Context**
Three Phase 4 acceptance checks and one new test needed to enumerate the application's routes. The
obvious form walks `app.routes`, filters on `hasattr(r, "methods")` and reads `r.path`.

**Options**

- **Walk `app.routes`.** On the pinned stack — FastAPI 0.141.1 with Starlette 1.6.0 —
  `include_router` leaves a single opaque `fastapi.routing._IncludedRouter` object there, with no
  `path` and no `methods` at all. Run verbatim against a correctly wired application, the first
  check asserted `0 == 5` and failed. This is the second time this repository has hit the same
  opacity: 03-09's probe-route guard reached the same conclusion in its own words.
- **Read the generated OpenAPI document.**

**Decision**
Every route assertion derives its operations from `app.openapi()["paths"]`, through
`_api_operations()` in `tests/unit/test_app_factory.py`, which carries the reason in its docstring.

**Consequences**

- The assertions are made against **the document a client actually reads**, which is the published
  contract rather than an internal representation that has already changed once under us.
- `test_create_app_publishes_exactly_the_phase_four_routes` is an inventory test: a twelfth route
  cannot appear unnoticed, and neither can one disappear.
- A future FastAPI upgrade that restores a walkable `app.routes` does not invalidate anything here;
  the weaker form simply stays unused.

---

## ADR-058: write paths load through a locking read, `get_for_update`, and read paths never do

**Context**
The Phase 4 code review (CR-01) found that every mutating use case is read-validate-write with
nothing serialising two writers: it loads a detached entity with a plain `SELECT`, asks the entity
whether the change is legal, and writes the entity back. The reviewer reproduced the consequence
with two real units of work on PostgreSQL: a task `in_progress`; A and B both load it; A completes
it and commits; B, validating against its stale `in_progress` copy, moves it to `pending` and
commits. The row went `completed -> pending`, which `ALLOWED_TRANSITIONS` forbids, A's completion
and its `completed_at` were erased, and neither caller was told. The claim in three module
docstrings that the entity is "the only copy of the state machine" was false under concurrency.
599 green tests and 100.00% coverage did not see it, because the whole integration harness runs on
one connection, where a second writer cannot exist.

**Options**

- **A row lock on the write path (`SELECT ... FOR UPDATE`).** The second writer waits at its read;
  under READ COMMITTED a statement that waited on a row lock re-reads the row when the lock is
  released, so it validates against what the first writer committed. No schema change, no new
  error a client has to handle, and the refusal B gets is the 409 the API already documents. Cost:
  writers to the *same row* queue behind one another for the length of a transaction, which here is
  a handful of statements with no I/O in between.
- **A `version` column with optimistic concurrency** (`version_id_col`, `StaleDataError`
  translated in the adapter). Never blocks, and it is the better tool when a client edits a copy
  for minutes. But it needs a migration on both tables, a new domain error and problem type for
  "somebody else changed this", and a retry story for every client - and it answers B with
  "conflict, try again" where the lock answers with the *real* reason, an invalid transition.
  It also leaves the entity out of the decision: the state machine is still validated against a
  stale copy, and only the write is refused.
- **A conditional `UPDATE ... WHERE status = :expected`.** The smallest SQL, but it moves the
  transition rule's enforcement into a hand-written statement per mutator, beside the entity that
  is supposed to own it (Phase 2 D-04), and a zero-row result then has to be reverse-engineered
  into "not found" or "changed underneath you". It covers the status and nothing else; the list
  PATCH and Phase 5's assignment would each need their own predicate.

**Decision**
A row lock, expressed on the ports in domain terms. `TaskRepository` and `TaskListRepository` each
gain `get_for_update(id) -> Entity | None`, whose contract is stated without naming a database: the
entity returned is the latest committed state, and until the unit of work ends no other unit of
work can obtain the same entity through `get_for_update`. The SQLAlchemy adapters keep it with
`.with_for_update()` plus `populate_existing`, in two module-level statement functions.
`access.visible_task` and `access.visible_task_list` take a keyword-only `for_update: bool = False`,
and the five write paths - `ChangeTaskStatus`, `UpdateTask`, `DeleteTask`, `UpdateTaskList`,
`DeleteTaskList` - pass `for_update=True`. Every read path keeps the default and never waits.

**Consequences**

- B now waits for A, re-reads `completed`, and `change_status(PENDING)` raises
  `InvalidStatusTransitionError` - the documented 409. The entity is the only copy of the state
  machine again, and it is so under concurrency because it is always handed the committed state.
- **Lock ordering is a rule, not an accident:** only the *addressed* resource is held. A task's
  writer holds the task and reads its parent list plainly, so a list deletion - which reaches its
  tasks through `ON DELETE CASCADE` - can never wait on a writer that is waiting on it.
- **Phase 5 inherits this rather than re-deciding it.** The assignee who may change a task's status
  concurrently with the owner, and the assignment use case, are further writers of the same row.
  They enter through `uow.tasks.get_for_update(...)` - via `visible_task(..., for_update=True)` or
  whatever guard replaces it for the assignee - and must not introduce a plain `get` on a write path.
- A flag on the existing guard rather than a second pair of functions, because a second pair would
  be a second copy of ADR-055's visibility rule. Keyword-only, so a write path names it at the call
  site, and defaulted to `False`, so a read cannot start waiting by accident.
- The write path costs no extra statement: `update` finds the locked row in the session's identity
  map. `tests/integration/api/test_statements.py` covers GET routes only and its expected counts
  were not touched.
- Plain `FOR UPDATE`, not `FOR NO KEY UPDATE`. The weaker mode would let a concurrent `CreateTask`
  foreign-key check proceed beside a list PATCH; that contention is a few milliseconds on an
  operation pair nobody runs in a loop, and the stronger mode is the one a `DELETE` takes anyway,
  so the two list write paths behave identically. Revisit if list PATCHes ever become hot.
- Proof, in three layers. `tests/integration/test_concurrent_writes.py` leaves the single-connection
  harness on purpose: two units of work on two connections, the interleaving forced by pausing A
  and observing B in `pg_stat_activity`, bounded three ways (`lock_timeout`, a polling deadline,
  `asyncio.wait_for`) so a broken lock is a red test and never a hung run, with the rows it commits
  removed from a separate connection. It was driven red by deleting `.with_for_update()` and the
  capture is `evidence/04-review-fix-CR-01-red.txt`. `test_the_write_path_read_locks_the_row` pins
  the compiled SQL with no server, and
  `tests/unit/application/test_write_paths_hold_what_they_change.py` pins which road each of the
  eight use cases takes against the fakes - both directions, so a GET that starts locking fails too.
- What this does not cover: two `CreateTaskList` requests racing on a name (already converged on
  one 409 by `uq_task_lists_owner_id_name`), and anything that spans more than one row. Neither
  exists as a requirement today.

---

## ADR-059: the third outcome — `owned_task` beside `visible_task`, refining ADR-055

**Context**
ADR-008 fixed two answers: a resource the caller cannot see is a 404, a resource they can see
but may not act on is a 403. Until this phase the project had never produced the second one —
Phase 4 had exactly one role, the owner, so plan 04-03 deliberately dropped the assignee clause
from the status guard and inverted the test that asserted it. Phase 5 adds the assignee, and
with them the first request in the project's history that is visible-but-forbidden: an assignee
may read their task and advance its status (ASGN-02), and may not rename it, delete it, or
change who it is assigned to (CONTEXT D-03). The rule lives in one module,
`application/use_cases/access.py` (ADR-055), and that module had two functions.

**Options**

- **A `require_owner=True` keyword on `visible_task`.** The smallest diff. Rejected: at the call
  site a boolean reads as something being *tuned*, when what is being selected is which **set of
  failures** the request can produce — `visible_task` can raise one error class, the owner-only
  door can raise two. The existing `for_update` keyword is a genuine tuning flag (it changes how
  the row is read, not what may be refused), and putting a second keyword of a different kind
  beside it would blur both.
- **A `(task, is_owner)` tuple return.** Rejected for a specific, countable cost: eleven use
  cases would each grow an `if not is_owner: raise ...` branch — eleven copies of the ADR-008
  decision, eleven chances to choose the wrong status code. That is precisely the duplication
  ADR-055 exists to prevent.
- **A second function, `owned_task`, copying `visible_task`'s shape and differing on one
  branch.**

**Decision**
`owned_task(uow, task_id, task_list_id, actor_id, *, for_update=False)` sits beside
`visible_task`. It raises `AuthorizationError` on exactly one leg — the caller is the task's
assignee — and `TaskNotFoundError(task_id)` on the other four (a stranger, an absent task, a
wrong parent, an orphan). `grep -c "raise AuthorizationError"` over the file prints `1`, so *how
many ways this project can produce a 403* is a question one command settles. `UpdateTask`,
`DeleteTask`, `AssignTask` and `UnassignTask` load through it; `GetTask`, `ListTasks` and
`ChangeTaskStatus` keep the wider `visible_task`.

`visible_task` gained the matching capability: it answers a task's assignee. The **placement of
that short-circuit is itself the decision** — it sits *after* the
`task.task_list_id != task_list_id` comparison and *before* `uow.task_lists.get`. ADR-050
outranks CONTEXT D-01: an assignee who addresses their task under the wrong parent list gets the
same 404 a stranger gets, and never learns where the task really lives.

**Consequences**

- **The assignee's read never touches the parent list.** That is first a privacy property — the
  list is invisible to them (D-01), so nothing about it is read on their behalf — and second a
  saved statement. Measured on the real authenticated path: the owner's `GET` of one task issues
  three `SELECT`s, the assignee's two; the owner's `PATCH .../status` issues four and one
  `UPDATE`, the assignee's three and one `UPDATE`. See ADR-076 for the rule that follows.
- **The saving is proven by an absence, not by an answer.** `CountingTaskListRepository`, a
  subclass declared in `tests/unit/application/test_access.py`, wraps `get` and `get_for_update`,
  and the assignee tests assert `reads == []`. Asserting only the returned task would pass
  against an implementation that read the list, found a different owner and returned the task on
  a later branch anyway.
- **The 403 carries no identifier.** Its message names the rule — "Only the list owner may change
  this task." — and two tests assert the foreign owner's id appears in neither `str(error)` nor
  `error.details`.
- **A new test shape entered the suite: the comparative *difference* test.** Everywhere else in
  this project two refusals are produced from one fixture and asserted **indistinguishable**.
  AUTH-06 needs the opposite, so `test_update_task.py`, `test_delete_task.py` and
  `test_access.py` each produce the assignee's refusal and the stranger's refusal from one
  fixture and assert the class and the `code` **differ**. A single-error assertion would pass
  against an implementation that answered the assignee 404 too — which is exactly what this
  project did for the whole of Phase 4.
- Between the commit that made the assignee visible and the commit that narrowed the two
  mutating verbs, an assignee could rename and delete a task on a list they cannot see. That
  window is inherent in the task order, lasts two commits on one branch, and the second commit's
  red capture (`evidence/05-04-tdd-red.txt`) is that window reproduced: four tests failing with
  `DID NOT RAISE`, not with a wrong error class.

---

## ADR-060: a grep-checkable documentation claim is retired in the commit that falsifies it

**Context**
`access.py`'s module docstring carried a claim of a shape this project uses deliberately: not
prose, but a property a command can check. It said `AuthorizationError` was "deliberately not
named anywhere in this file", and explained why — nothing in Phase 4 could produce a
visible-but-forbidden case, so the class did not appear. `grep -c AuthorizationError
access.py` printing `0` was the check. CONTEXT D-22 anticipated that Phase 5 would falsify it.

**Options**

- **Delete the paragraph.** Rejected: a reader of the Phase 4 history would find a claim that
  simply evaporated, with nothing saying whether it had been wrong or merely outlived.
- **Leave it and add a caveat.** Rejected: the file would then contain a sentence that is false
  on its face, one paragraph away from the code that falsifies it.
- **Replace it, in the same commit, with a paragraph that states the old claim, why it had been
  true, and the counted property that replaces it.**

**Decision**
The third. The paragraph headed "Why nothing here can answer 403" is gone;
`grep -c "deliberately not named anywhere in this file"` prints `0`. What replaces it records
that the claim held for the whole of Phase 4, that Phase 5's assignee falsified it, and that the
new checkable property is `grep -c "raise AuthorizationError"` printing exactly `1`. The project
keeps making claims of this shape because a counted property is the only kind of documentation
that can go red.

**Consequences**

- **Four further sentences in the same docstring were falsified by the same change and were
  rewritten with it**, not left as collateral: "the rule lives here, once, as **two**
  functions"; "**Both functions** take an already-entered `UnitOfWork`"; the `for_update`
  paragraph's argument that a keyword beats "a second pair of them" (there is now a third
  function, added for a different reason); and "`visible_task(..., for_update=True)` holds the
  task **and reads its parent list plainly**", which is no longer true on the assignee's leg.
  Fixing the one paragraph D-22 named and leaving the other four would have been the exact
  failure D-22 exists to name.
- The replacement is weaker in one respect and stronger in another: it no longer asserts that a
  concept is absent, it asserts how many times a specific outcome can be produced. The second is
  the property a reviewer actually cares about.
- The same convention bit from a new direction in `update.py`. Its docstring cannot name the
  status use case, because `test_update_task_cannot_change_a_status` asserts
  `TaskStatus.__name__` is absent from the module source and the class name is a substring of
  the use case's name. The docstring names the endpoint in prose instead. That constraint was
  **observed rather than assumed**: the forbidden spelling was written, the test run, and the
  failure captured in the evidence file's appendix before the probe was reverted.

---

## ADR-061: the HS256 signing-key floor rises from 16 characters to 32

**Context**
`Settings.jwt_secret` has carried `min_length=16` since Phase 1, when no code signed anything.
PyJWT 2.14.0 emits `InsecureKeyLengthWarning` when an HS256 key is shorter than 32 bytes, and
`pytest.ini` sets `filterwarnings = error`. RFC 7518 §3.2 requires a key of at least the hash
output size — 256 bits, 32 bytes — for HMAC-SHA256.

**Options**

- **Leave the floor at 16 and suppress the warning.** Rejected twice over: it would put a
  `filterwarnings` exemption in `pytest.ini` for a warning that is *correct*, and it would leave
  a deployable configuration whose tokens are brute-forceable offline (threat T-5-02).
- **Leave the floor at 16 and rely on operators reading `.env.example`.** Rejected: the whole
  point of validating settings at boot is that a misconfigured container fails fast.
- **Raise the floor to 32.**

**Decision**
`jwt_secret: str = Field(min_length=32)`. `.env.example`'s comment states the minimum and why,
and keeps its `secrets.token_urlsafe(32)` generation command. The boundary is pinned at 31/32
rather than at an obviously tiny value, so the floor cannot be lowered back towards PyJWT's
threshold without a red test.

**Consequences**

- **Nothing had to be lengthened, and that was established before the field changed.** Every
  secret in the repository was counted first: `.env.example` 34 characters, `.github/workflows/ci.yml`
  36, `tests/conftest.py` `"b" * 32`. That finding is what made D-26 a one-line change rather
  than a repository-wide one.
- **A developer whose local, uncommitted `.env` carries a 16-to-31 character `JWT_SECRET` now
  fails at boot** with a `ValidationError` naming the field. That is the intended behaviour and
  is recorded here because it is the only way this change can be felt.
- The warning is now unreachable rather than suppressed, which is the difference between a
  configuration that is safe and one that is quiet.

---

## ADR-062: the PyJWT decode policy, and the one failure deliberately left outside the catch

**Context**
`JwtTokenService.decode` is the single place an attacker-supplied string becomes an identity.
python-jose is disqualified project-wide (CLAUDE.md § What NOT to Use, CVE-2024-33663 and
CVE-2024-33664), so the adapter is PyJWT 2.14.0 and every policy choice is ours to make
explicitly.

**Options**

- **Read the algorithm from the token's own header** — the default shape of many tutorials.
  Rejected outright: that is RFC 8725 §2.1's algorithm-confusion attack. Verified against the
  pinned library, a token whose header says `alg: none` is refused with `InvalidAlgorithmError`
  once the accepted list is pinned.
- **Accept a token missing `exp`.** Rejected: a token with no expiry is a permanent credential.
- **Allow a few seconds of clock leeway.** Rejected: the expiry proof in the test suite is a
  boundary, and a tolerance would make that test measure the tolerance instead. Nothing in this
  deployment has two clocks to reconcile.
- **Catch the library's own base exception class.** Rejected — see the decision.

**Decision**
`algorithms=[self._algorithm]`, taken from `Settings.jwt_algorithm` and never from the token;
`require=["sub", "exp", "iat"]`; no leeway; and a catch narrow enough to exclude
`InvalidKeyError`. `grep -c 'algorithms='` over the adapter prints exactly `1`.

**Consequences**

- **A misconfigured server is a 500, not a 401.** `InvalidKeyError` means *this deployment's key
  is unusable* — the caller did nothing wrong, and answering them "your credentials are invalid"
  would send an operator hunting for a client bug. It escapes the adapter and becomes Phase 2's
  fixed problem+json 500 (T-5-02).
- **Nine forgeries are one parametrised table** — unsigned, foreign-signed, expired, missing
  `iat`, missing `sub`, missing `exp`, a non-UUID subject, `""` and `"garbage"` — and a tenth
  test asserts every refusal carries an identical message, empty details and no fragment of any
  token (D-11, T-5-04).
- **The expired case needs no `sleep` and no clock-rewriting library.** PyJWT compares `exp`
  against the real `time.time()`, so only the *issuing* side is controllable: a `FrozenClock` two
  hours in the past mints a token that expired ninety minutes ago. That asymmetry is the reason
  the adapter takes a `Clock` at all.
- **The plan's own `alg=none` construction could not be built, and the corrected one is
  stronger.** `jwt.encode(claims, secret, algorithm="HS256", headers={"alg": "none"})` raises
  `InvalidKeyError` at *encode* time in PyJWT 2.14.0 — the library prepares the key for the
  header's algorithm, and `alg=none` requires a `None` key. The token an attacker actually sends
  is `jwt.encode(claims, None, algorithm="none")`, and that is what the table uses.
- Three literals are argued in prose rather than spelled, because the plan's own grep criteria
  required `InvalidKeyError` once, `PyJWTError` zero times and `leeway=` zero times. The
  01-03 prose-not-literal convention.

---

## ADR-063: Argon2 runs off the event loop through `anyio.to_thread`, which is imported unpinned

**Context**
Argon2's cost is the point of Argon2 — measured here at 37 ms to hash and 26 ms to verify. Under
asyncio, a 37 ms synchronous call in a coroutine is not a slow request, it is a **stalled
server**: nothing else on that event loop runs for its duration. AUTH-04 requires the hashing to
run off the loop (threat T-5-07).

**Options**

- **`asyncio.to_thread`.** Works, and opens a *second*, invisible thread pool alongside
  Starlette's, with its own unbounded concurrency. Rejected.
- **A `concurrent.futures.ThreadPoolExecutor` owned by the adapter.** Same objection plus a
  lifecycle to manage.
- **`anyio.to_thread.run_sync`.** Shares Starlette's own threadpool and its `CapacityLimiter`,
  which is the pool the framework already sizes and already blocks on.

**Decision**
`anyio.to_thread.run_sync` for both `hash` and `verify`. **No package was added**: `anyio` is a
hard transitive of the pinned Starlette, which `fastapi==0.141.1` in turn pins.
`requirements.txt` records it as a comment in the convention `requirements-dev.txt` already uses
for `coverage` and `grimp`: `grep -c anyio` prints 1, `grep -cE '^anyio=='` prints 0.

**Consequences**

- **Residual risk, recorded rather than dismissed:** this project imports a library it does not
  pin. If a future FastAPI release dropped Starlette, or Starlette dropped anyio, the import
  would break at build time rather than at runtime — loudly, in CI, before a deployment. The
  alternative, pinning `anyio==` ourselves, risks a resolver conflict with whatever Starlette
  requires, which is a quieter and worse failure. The comment in `requirements.txt` is what makes
  the choice visible to whoever hits it.
- **The off-loop claim is asserted by recording the offload, never by timing.** A recorder
  appends `(callable, args)` and then awaits the real `run_sync`, so the round trip still has to
  work. A stopwatch assertion in a unit suite is a flake.
- **That same recorder is the guard against a transposed call.** pwdlib's `recommended()`
  docstring has shown `verify(hash, password)` since 0.2; the correct order is
  `verify(password, hash)`. A transposed call raises `UnknownHashError`, which this adapter
  catches and turns into `False` — so the two mistakes cancel into an application where every
  login silently fails and nothing reports an error. A green round trip is not evidence; the
  recorded argument tuple is.
- `verify` catches `UnknownHashError` narrowly and answers `False`.
  `grep -cE 'except (Exception|BaseException)'` over the adapter prints `0`. The case is
  concrete: the Phase 4 demo seed wrote `password_hash = "!"`, so a developer database still
  holding that row would otherwise have answered a login attempt with a 500.

---

## ADR-064: `PasswordHasher.dummy_verify` — the one port extension this phase took (D-21)

**Context**
D-12 and roadmap SC-2 require a login with a wrong password to be indistinguishable from a login
with an unknown email. Same status and same body is the easy half; **equal work** is the other
half, because a request that returns in 0.2 ms when the address is unknown and 26 ms when it is
known is an account-enumeration oracle with a stopwatch instead of a diff. 05-CONTEXT's
carried-forward note said the ports keep their shape "unless research proves a need".

**Options**

- **Compute a throwaway hash in the `Login` use case.** Rejected: `application` would have to
  import `pwdlib`, which the `application-framework-free` contract in `.importlinter` forbids —
  and rightly, because a hashing library is infrastructure.
- **A hard-coded encoded Argon2 string as a module constant.** Rejected: it reads as a
  credential to anyone grepping the repository, and it pins the cost parameters of a library
  that is allowed to change its recommendations.
- **Re-hash a constant per request inside the use case.** Rejected: that is the 26 ms paid twice
  on every unknown-address login, for no property.
- **One method on the port.**

**Decision**
`PasswordHasher.dummy_verify(password) -> None`, implemented by the adapter as a verify against
one throwaway hash built lazily, **once per instance**, from `secrets.token_urlsafe(32)`. The
measured cost of the two login legs is 23.4 ms and 23.6 ms.

**Consequences**

- **The plaintext behind the dummy hash is generated, not written.** The plan only forbade a
  hard-coded *encoded* hash; generating the seed too means no string in the file looks like a
  credential at all (T-5-03), at zero cost, because the value is never compared to anything.
- **The `-> None` return is enforced by the type checker, not by a runtime assertion.** The
  obvious test — `assert await hasher.dummy_verify("pw") is None` — fails `mypy --strict` with
  `Function does not return a value (it only ever returns None) [func-returns-value]`. That
  failure *is* the property the port's comment asks for: no caller anywhere can read this return
  and branch on it, which a passing runtime assertion could never establish. The assertion was
  dropped and the reason written into the test's docstring.
- **The equalisation is asserted as a port call count, never as elapsed time.**
  `FakePasswordHasher` records `dummy_verifications`, `hashed` and `verifications`, and three
  tests pin the per-leg pattern: unknown address calls `dummy_verify` and not `verify`, wrong
  password the other way round, success calls `verify` exactly once and nothing else.
- The cached hash costs ~37 ms **once per application**. A `PwdlibPasswordHasher()` constructed
  per request would pay it per login, which is the exact cost this decision exists to control —
  which is why the adapter travels in the composition root's container (ADR-078) and not in a
  provider.

---

## ADR-065: the 401 message lives on `AuthenticationError`, and this API has two 401 wordings

**Context**
D-11 requires that a missing token, a malformed token, a badly-signed token, an expired token
and a perfectly valid token whose subject has no user row all produce the **same** generic 401
body. Two components raise that refusal: the token adapter in `infrastructure/security/tokens.py`
and the `AuthenticateActor` use case in `application/`. The adapter held the message in a private
module constant, `_REFUSAL`, which the application layer cannot import — the layer contract
forbids it.

**Options**

- **Retype the string in `authenticate.py`.** Two constants in two layers that agree only until
  somebody edits one — and nothing would have failed at that moment: `test_tokens.py` asserts the
  adapter's refusals share *one* message without asserting what it is, and no test compared the
  two components. Rejected.
- **Move the constant into a shared module.** There is no layer both may import that is not the
  domain, which brings us to the third option anyway.
- **Put the message on the exception class.**

**Decision**
`AuthenticationError.REFUSAL: ClassVar[str]`, defaulted into `__init__`. Both components now
write `raise AuthenticationError()` and **neither spells the message**. `tokens.py` lost its
private constant and gained a comment recording where the message went and why. Two files
outside the owning plan's declared file list were changed to do it, which is recorded in that
plan's summary as a deviation.

**Consequences**

- **D-11 became structural rather than careful.** A deleted user's live token and a junk token
  produce byte-identical bodies because there is exactly one string, in one place, and that place
  is the class both raisers name.
- **This API nevertheless has two distinct 401 wordings, and that is deliberate.**
  `AuthenticationError.REFUSAL` — "Could not validate credentials." — answers anything to do with
  a token. `use_cases/auth/login.py`'s own constant — "Incorrect email or password." — answers a
  rejected credential at the login door. The two endpoints answer different questions, and D-12's
  requirement is that *login's two legs* match each other, which one constant in one module
  guarantees. Sharing the token wording would tie two unrelated messages together for no
  property.
- **The cost is a rule for every future assertion:** both carry `code: authentication_failed` and
  both carry the `WWW-Authenticate: Bearer` challenge, so a test asserting on a 401 `detail` must
  say which door it is at. Plan 05-15 found this the hard way — its first draft asserted
  `AuthenticationError.REFUSAL` on every 401 in the permission matrix, and login's bad-credential
  cell failed with `'Incorrect email or password.' != 'Could not validate credentials.'`. The
  matrix now asserts the shared half (status, media type, challenge, six members, `code`) for
  every cell and the wording only where it applies.

---

## ADR-066: register's 409 is an account-enumeration oracle — conceded, not mitigated

**Context**
AUTH-01 requires: "duplicate email returns 409". A 409 that is reachable by an unauthenticated
caller and that distinguishes a registered address from an unregistered one *is* an
account-enumeration oracle, by construction. There is no way to satisfy the requirement and
remove the property. Threat T-5-06 is dispositioned **accept, documented**.

**Options**

- **Answer 201 for a duplicate and send a "somebody tried to register your address" email
  instead** — the shape a consumer product uses. Rejected: it contradicts the brief's literal
  wording, which this project's core value says is met to the letter, and this project transmits
  no real email.
- **Answer 202 Accepted for every registration and resolve asynchronously.** Rejected for the
  same reason plus a state machine nobody asked for.
- **Ship the 409 and write down what it costs.**

**Decision**
The 409 ships. The requirement was chosen over the property, deliberately, and this entry says so
in those words rather than presenting a compensating control as a fix. What is done **instead**,
and what bounds the damage:

- `EmailAlreadyRegisteredError.__init__` takes no argument at all, by design, so the address
  never reaches a body or a log line. `test_auth.py` registers `Ana@X.com`, then `ana@x.com`, and
  asserts the 409 document contains **neither spelling** — it carries `code:
  email_already_registered` and `{"field": "email"}` and nothing else.
- `GET /api/v1/users` already discloses every address to every authenticated caller (ADR-068), so
  the residual disclosure is to *unauthenticated* callers only.
- The login door, which is the one an attacker would actually use at scale, stays
  indistinguishable (D-12, ADR-064).

**Consequences**

- **An unauthenticated attacker can test whether an address has an account here, one request at a
  time, with no rate limit in front of them (ADR-067).** That is the honest statement of the
  residual risk and it is not reduced by anything above.
- Phase 7's README security note owes the same sentence. A reader who finds this concession in
  the decision log and not in the documentation would be right to distrust both.
- The bound is a test rather than an intention, which is the only part of this that a reviewer
  can check.

---

## ADR-067: there is no rate limiting on login, and Argon2 is not a substitute for one

**Context**
Threat T-5-08 is login brute force. 05-CONTEXT lists "login throttling / lockout" under Deferred
Ideas, alongside refresh tokens and password reset, as v2 work.

**Options**

- **A per-address or per-IP counter in the database.** A migration, a cleanup story, and a new
  failure mode (a shared NAT locking out a whole office) for a deliverable with no deployment.
- **`slowapi` or an equivalent middleware.** A new dependency and a second source of truth about
  what a 429 body looks like, which this project's single RFC 9457 handler would have to be
  taught.
- **Nothing, recorded as nothing.**

**Decision**
Nothing, recorded as nothing. There is no rate limiting, no lockout and no CAPTCHA on
`POST /api/v1/auth/login`.

**Consequences**

- **Argon2's ~25 ms floor is an incidental throttle, not a control.** It bounds an attacker to
  roughly forty attempts per second per core — which is a meaningful cost for one attacker on one
  connection and no cost at all for a distributed one. Calling it a mitigation would be the same
  category error as calling the 409's silence a fix for enumeration (ADR-066).
- **The same 25 ms is also the denial-of-service surface in the other direction:** an
  unauthenticated caller can make this server do Argon2 work. What is bounded is the *size* of
  that work — D-10's 128-character cap runs before the hasher is reached, and
  `test_register_user.py` asserts `hasher.hashed == []` on the over-long path (T-5-07). The
  *rate* is not bounded.
- Owed to Phase 7's README future-work list, beside refresh tokens (AUTH-07) and password reset
  (AUTH-08).

---

## ADR-068: `GET /api/v1/users` is an email directory readable by every authenticated caller

**Context**
ASGN-03 asks, literally, for a way to "list users (id, name, email) so an assignee id is
discoverable". `PUT .../assignee` takes a `UUID`, and a `UUID` is not something a human can guess
or be told over a chat window, so without a directory the assignment feature is unusable through
Swagger — which is the only client this deliverable has.

**Options**

- **Scope the directory to a team, organisation or tenancy.** The correct answer in a real
  product. Rejected because this brief has no such concept: there is no membership model, no
  invitation that grants anything, and inventing one would be a schema and a set of rules nobody
  asked for (05-CONTEXT lists it under Deferred Ideas).
- **A lookup-by-email endpoint — `GET /users?email=...` — returning one id or a 404.** Rejected:
  it discloses strictly less in bulk and strictly more precisely (it is a *confirmation* oracle
  for any address an attacker already suspects), it needs the pagination-free contract anyway,
  and it does not let a Swagger user discover the teammate they just registered.
- **The full directory.**

**Decision**
`GET /api/v1/users` returns `id`, `full_name` and `email` for every user, ordered by
`created_at`, `id`, with no pagination (ADR-043) and no query parameters at all
(`grep -cE "Query\(|limit|offset|page"` over the router prints `0`). Any authenticated caller may
read it.

**Consequences**

- **Every authenticated user can read every registered address.** Stated plainly, because that is
  the one deliberate disclosure in this API and a reader should meet it here rather than discover
  it in the code.
- **It is also the bound that makes another decision safe.** D-08's `user_not_found` 404 on
  `PUT .../assignee` — reachable only by a list owner, who is authenticated by definition —
  discloses nothing the same caller could not learn from one `GET /api/v1/users`. That
  consequence is what allowed the ownership guard to be the only thing standing between a
  stranger and the user-existence oracle (T-5-12, ADR-069).
- **The trade-off is written where a client reads it, not only where a maintainer does.** The
  route's `response_description` says it is an email directory readable by anyone logged in, that
  a product with a tenancy concept would scope it, and that **no client should treat it as
  restricted**. Describing it as restricted was the one available wording that would actively
  mislead.
- Phase 7's README owes it in the documented trade-offs.

---

## ADR-069: the assignment door — one URL, two verbs, two no-ops, and self-assignment allowed

**Context**
ASGN-01 requires a list owner to assign and unassign a task. ADR-048 already settled the shape
for a side-effecting verb on an existing resource: a dedicated sub-resource route, not a field in
the generic `PATCH`. Assignment additionally sends an email (NOTF-01), which makes keeping it out
of the generic patch a correctness question and not only a tidiness one.

**Options**

- **`assignee_id` as a field of `PATCH /tasks/{id}`.** Rejected: a partial update would acquire a
  side effect, the notification would fire from a use case whose job is field copying, and
  T-5-10 (mass assignment) would be a live surface rather than a refused key.
- **`POST /tasks/{id}/assignments` creating an assignment resource, `DELETE .../assignments/{id}`
  removing it.** A defensible REST reading, rejected because there is no assignment *entity* —
  `tasks.assignee_id` is a nullable column, a task has at most one assignee, and inventing an
  identifier for a field would leak into the schema, the response and the URL space.
- **One URL, two verbs.**

**Decision**
`PUT /api/v1/task-lists/{list_id}/tasks/{task_id}/assignee` with body `{"assignee_id": "<uuid>"}`
(`extra="forbid"`) assigns; `DELETE` on the same URL unassigns. Both answer **200 with the full
`TaskResponse`** — not 204 — because what is deleted is a *field of a resource*, not the
resource. Both are owner-only, reached through `owned_task(..., for_update=True)` (ADR-059,
ADR-058).

**Consequences**

- **A repeat of either verb is a 200 no-op, not a 409** — the same reading Phase 2 D-02 gave the
  same-state status request. `PUT` naming the current assignee changes nothing, commits nothing
  and **sends no second email**; `DELETE` on an unassigned task likewise; unassigning notifies
  nobody.
- **That idempotence lives in the use case, not in the entity, and the asymmetry is deliberate.**
  `Task.assign` and `Task.unassign` stamp `updated_at` unconditionally, by design (there is a
  test asserting an unassign on an unassigned task still moves the timestamp, precisely so a
  later reader cannot "fix" the asymmetry). Only the use case can skip three things at once: the
  mutation, the commit and the email. The no-op tests assert `updated_at` **unchanged** as well as
  `commits == 0`, because an implementation that returned early *after* calling `Task.assign`
  satisfies every counter while moving the timestamp.
- **Self-assignment is allowed and is emailed like any other assignment (D-08).** No special case
  for the owner — a special case would be a rule nobody asked for and a branch no requirement
  covers.
- **A non-existent `assignee_id` is a 404 `user_not_found`, and the ordering of the two checks is
  a security property.** Ownership is verified *before* the assignee is looked up, so a stranger
  naming an invented id and a stranger naming a real one receive byte-identical documents. That
  is asserted by producing both refusals and comparing them, and it was observed failing —
  `assert 'user_not_found' == 'task_not_found'` — against a deliberately reordered implementation
  (T-5-12, `evidence/05-14-falsification.txt`).
- **`UnassignTask` takes no notifier, and its constructor is the proof.** A port accepted and
  never called would contradict the very rule its sibling cites to justify taking one; the test
  asserts `"notifier" not in signature(...)` and says plainly that the zero-message count beside
  it is the weaker half of the claim.
- **The body-less `DELETE` still declares a 422.** Its two path segments are `UUID`-annotated, so
  `DELETE /api/v1/task-lists/not-a-uuid/tasks/x/assignee` is a validation 422 before any use case
  runs. The owning plan's behaviour block excluded the leg and contradicted itself doing so; the
  sibling body-less `DELETE` in `routers/tasks.py` has declared it since 04-08 for the identical
  reason. An omitted reachable leg and a declared unreachable one are the same defect in two
  directions.
- **Exactly four operations in this API declare a 403**, and it is asserted by set *equality*
  rather than containment: the generic task `PATCH`, the task `DELETE`, and the two assignee
  verbs. A documented refusal a route cannot produce misleads a client as much as a missing one.

---

## ADR-070: the invitation is attempted after the commit, and its failure is swallowed

**Context**
NOTF-01 requires the simulated invitation to be sent *after the transaction commits*; NOTF-03
requires a notifier failure never to fail the assignment request. The two together fix the
ordering and the error handling, and leave open only where the call lives.

**Options**

- **Inside the `async with self._uow:` block.** Rejected by NOTF-01 directly: an email announcing
  an assignment that a later failure rolls back is a message about something that never happened.
- **FastAPI's `BackgroundTasks`.** Rejected on two counts. It moves ownership of an
  application-layer side effect into the presentation layer, which the whole architecture exists
  to prevent; and it makes the send happen *after* the response, so every test asserting the
  email would need a sleep or a polling loop. With the call inline, by the time the response
  returns the email has been attempted.
- **A queue or a task runner.** Over-engineering for a simulated message; explicitly out of scope
  in REQUIREMENTS.md.
- **Inline in the use case, after the commit, outside the block, in a `try/except` that logs at
  WARNING and swallows.**

**Decision**
The last. `AssignTask` commits, leaves the block, and then attempts
`notifier.send_task_assigned(...)` inside a broad `except Exception` that logs a WARNING naming
the task id and continues. The recipient's address is read **inside** the block, while the unit
of work is still open.

**Consequences**

- **The ordering is proved as a sequence, not as two counts.** `_RecordingUnitOfWork` and
  `_RecordingEmailNotifier` append to one shared list and the assertion is
  `events == ["commit", "send"]`. "One commit and one send" is equally true of a send that ran
  first, which is exactly the thing this decision exists to prevent.
- **"The address is captured inside the block" is a failing test rather than a comment.**
  `_ClosingUnitOfWork` swaps in a user repository that raises on every method as its block ends —
  which is what `SqlAlchemyUnitOfWork.__aexit__` does in domain terms and what a dictionary-backed
  fake cannot model. An implementation reaching back for `uow.users.get(...)` to build the email
  fails in the unit suite instead of in production.
- **NOTF-03 is proved by a re-read, not by a status code.** With the notifier overridden by one
  that raises, the request is still 200, **and a fresh `GET` still shows the assignment**. "No
  exception escaped" is equally true of an implementation that swallowed the error and rolled the
  write back. Removing `AssignTask`'s `commit()` was observed turning exactly that second request
  red while the 200 and the response body still passed — which is the whole argument for making
  it a second request.
- **The WARNING carries the task id and the traceback and *not* the task title.** Caller-supplied
  text does not go into a log line (T-5-13), and a test asserts the title is absent from it.
- **The cost, stated: a notification can be lost silently.** If the notifier fails, the
  assignment stands and the assignee is never told. For a simulated email that logs to stdout
  that is the right trade; for a real delivery path it would need an outbox table, and this entry
  is where that future reader should start.

---

## ADR-071: nothing in this repository's flake8 configuration objects to a bare `except Exception`

**Context**
ADR-070's swallow requires a broad `except Exception`. Two artifacts in this repository implied
that such a line would trip the linter and need a suppression: `docker/entrypoint.sh` carries a
`# noqa: BLE001` on one, and `05-RESEARCH.md` §Pattern 7 instructs the executor to run
`make lint` and add whichever code fires.

**Options**

- **Write `# noqa: BLE001` because the convention appears to exist.** Rejected once it was
  measured.
- **Guess a different flake8 code.** Rejected for the same reason.
- **Run the line with no suppression and record what actually happens.**

**Decision**
No `noqa`. The line was committed with no suppression and `flake8` exited `0`. The installed
plugin set is flake8-bugbear 26.9.9, flake8-comprehensions 3.17.0 and pep8-naming 0.15.1, and
none of the three has a check for this shape. **`BLE001` is a Ruff code** — and ruff is excluded
from this project because the brief mandates flake8. The `# noqa: BLE001` in
`docker/entrypoint.sh` that established the apparent convention sits inside a **shell heredoc
flake8 never reads**, so it has never suppressed anything either. The capture is
`evidence/05-08-broad-except-lint.txt`.

**Consequences**

- A suppression naming a code that cannot fire is worse than no suppression: it tells the next
  reader that a gate objected when no gate did. The explanatory comment stays on the `except` and
  now records the measurement and points at the capture.
- **The broad catch is therefore ungated, and that is a real gap**, not a clean result. Nothing
  in this repository would stop a future `except Exception` that swallows something it should
  not. If that becomes a concern, the honest fix is a small AST gate of the kind
  `tests/architecture/` already contains — not a `noqa` restating a belief.
- Recorded as an ADR because the next person to write a broad catch here should not have to
  re-measure it, and because two project artifacts still imply the opposite.

---

## ADR-072: the JSON log handler is attached to the whole `taskmanager` package

**Context**
D-15 requires the runtime notifier to emit one structured JSON line at INFO, findable with one
`grep` in `docker compose logs api`. Research established by **execution** that no such line was
being written at all: uvicorn's `LOGGING_CONFIG` configures only the `uvicorn*` loggers, attaches
nothing to root and leaves the root level at `WARNING`, so
`logging.getLogger("taskmanager.notifications").info(...)` is filtered out entirely. Without a
decision here, NOTF-02 would have shipped with nothing to grep.

**Options**

- **A `--log-config` YAML file passed to uvicorn.** Rejected: it is untested by anything in this
  suite, invisible to coverage, does nothing for `caplog` assertions, and adds a second
  configuration format to a project that reads all of its configuration through
  pydantic-settings.
- **A handler on `taskmanager.notifications` alone.** The narrowest change, and the one whose
  blast radius is zero. Rejected on 05-RESEARCH's recommendation: the application would then have
  one machine-readable log line and everything else unformatted, which is worse than either
  consistent choice.
- **A handler on the `taskmanager` package logger.**

**Decision**
`configure_logging()` attaches exactly one `StreamHandler(sys.stdout)` carrying `JsonFormatter`
to the `taskmanager` logger at INFO, and `create_app()` calls it as its **first statement** —
before the settings are even resolved, so a failure during container construction is logged, and
not in the lifespan, because the HTTP harness never enters the lifespan (ADR-056) and D-06 keeps
the startup half empty. The call is idempotent: a second invocation returns early because the
handler carries a private marker attribute, which matters because `create_app()` runs hundreds of
times across this suite.

**Consequences**

- **Named blast radius (T-5-03, accepted): the fixed-500 record is JSON from now on.**
  `presentation/api/errors/handlers.py` already logged the unexpected-error case, and its output
  format changes as a direct result of this decision. The content is unchanged. This is recorded
  in the module docstring rather than left for someone to discover in a log aggregator.
- **`propagate` is left `True`, and both halves are asserted** — the flag itself *and* a record
  reaching `caplog`, which attaches to the **root** logger. The flag alone would pass against a
  handler that swallowed the record some other way. Two pre-existing assertions in
  `tests/api/test_error_contract.py` depend on this; setting `propagate = False` would break them.
- **Log injection is mitigated by construction rather than by sanitising.** Every value goes
  through `json.dumps`, so a newline inside a task title is escaped. The formatter test builds a
  message containing `\n` and a complete `{"level": "ERROR", ...}` object and asserts **one**
  parseable line with the injected text as the `message` *value*; the notifier test does the same
  end to end through a task title (T-5-13).
- `stack_info` is deliberately not rendered: nothing in this project passes it, so the branch
  would be unreachable, and the no-`pragma` coverage rule has no way to excuse an unreachable
  line. Stated in the docstring so the absence reads as a choice.
- `json.dumps` is called with no `default=` fallback. The one caller stringifies its `UUID` at the
  call site; a silent coercion here would hide a call-site bug and pick a wire shape nobody chose.

---

## ADR-073: the formatter renders `exc_info`, and the notifier names its logger literally

**Context**
Two decisions taken **against** the written instructions this phase was executing, both caught by
reading what the code would actually do rather than what the documents said it would.

**Options and decisions**

**1. `exc_info` is rendered.** The formatter specified by the plan and by 05-RESEARCH §Pattern 8
serialises three base fields plus every *non-reserved* record attribute — exactly the set a caller
passed through `extra=`. `exc_info` **is** a reserved `LogRecord` attribute, so it is excluded
from that merge and never rendered. `handlers.py` logs the fixed 500 with `exc_info=exc` and its
docstring promises "the traceback goes to the log and nowhere else". Attaching this handler to
the package logger (ADR-072) would therefore have made every traceback in the application go
**nowhere at all** — and nothing would have failed: the two existing assertions read
`record.exc_info`, an attribute of the record object, not the handler's output. The formatter now
writes `payload["exception"] = self.formatException(...)`, escaped onto one line by `json.dumps`
like everything else, with a test for each leg.

**2. The notifier's logger is named with the literal `taskmanager.notifications`.** The plan
specified `logging.getLogger(__name__)`. In
`src/taskmanager/infrastructure/notifications/logging.py`, `__name__` is
`taskmanager.infrastructure.notifications.logging`. Records on that logger propagate to
`taskmanager.infrastructure.notifications`, `taskmanager.infrastructure`, `taskmanager` and root
— **never** to `taskmanager.notifications`, which is a sibling branch. D-15 names that logger,
the plan's own behaviour block asserted "exactly one record on `taskmanager.notifications`", and
its acceptance snippet attached a handler there and expected one record: all three would have
been false. The name is exported as `LOGGER_NAME` so the tests, the assignment use case's warning
and the cold-start grep read one constant. A second reason is recorded in the comment: a
path-derived name changes the day the file moves, and an operator's log filter breaks with it.

**Consequences**

- Both are recorded here rather than in a plan summary because the append-only log is where a
  decision made *against* the instructions belongs. The first would have been a silent regression
  in an area no test could see; the second would have been a feature that was documented, tested
  against the wrong logger, and invisible in production.
- The rule these two share: a logging change is verified by reading the record that comes out, not
  by reading the call that goes in.

---

## ADR-074: `OAuth2PasswordBearer(auto_error=False)` is how ADR-051 and AUTH-02 hold together

**Context**
Two requirements meet in one object. AUTH-02 requires Swagger's **Authorize** button to work,
which means the OpenAPI document must publish a `securitySchemes` entry and a per-route `security`
array — and the supported way to get both is FastAPI's `OAuth2PasswordBearer`. ADR-051, widened by
the Phase 4 review's WR-05, forbids any module under `presentation/api` from raising **or
importing** `HTTPException`. FastAPI's default `OAuth2PasswordBearer(auto_error=True)` raises
`HTTPException` itself on a missing or non-bearer header — from inside the library, but the
project's own 401 body would then never be produced, and the error contract would have two shapes.

**Options**

- **Hand-roll the header parse.** Read `Authorization` off the request, split the scheme, raise
  `AuthenticationError`. Satisfies the AST gate perfectly and **loses the Authorize button**:
  nothing would appear in `securitySchemes`, and every route would look open in `/docs`.
- **Keep `auto_error=True` and translate.** Would require catching and re-raising the framework's
  exception class somewhere under `presentation/api`, which is what the gate forbids.
- **`auto_error=False`.**

**Decision**
`OAuth2PasswordBearer(tokenUrl=..., auto_error=False)`. The dependency returns `None` for a
missing header *and* for a non-bearer scheme; `get_current_actor` treats a falsy token — covering
both `None` and `""` — as `AuthenticationError`, which the single RFC 9457 handler turns into the
project's own 401 with `WWW-Authenticate: Bearer`.

**Consequences**

- **Both properties hold at once, and both are asserted.** `presentation/api` neither raises nor
  imports the framework's exception class — the widened AST gate covers the whole package and
  names `actor.py` in `REQUIRED_SCANNED_MODULES`. And because the scheme is still a `Depends`,
  `components.securitySchemes.OAuth2PasswordBearer` and a per-route
  `security: [{"OAuth2PasswordBearer": []}]` are emitted **through the nested dependency**, with
  nothing repeated per route.
- **The published contract is asserted as a partition, from the document.**
  `tests/unit/presentation/test_security_scheme.py` reads `app.openapi()` (ADR-057) and asserts
  that every operation is either one of the three named open ones — `/health`, register, login —
  or carries a `security` array naming the scheme, and that the three open ones carry no
  `security` key at all. A route shipped with no token requirement fails by name.
- **That test was falsified rather than trusted.** Its subject already existed when it was
  written, so a throwaway `GET /api/v1/auth/_falsification` with no caller parameter was planted;
  the partition failed naming it by path and the count test failed with `assert 12 == (16 - 3)`.
  The route was removed; both runs are in `evidence/05-11-open-route-falsification.txt`.
- The four routes added after this decision — the directory, the two assignee verbs and the
  discovery collection — joined the secured set with **no edit** to the partition test, which is
  the property this shape buys.

---

## ADR-075: the demo account is deleted and nothing replaces it, refining ADR-045

**Context**
ADR-045 put an idempotent demo-user seed in the container entrypoint, because Phase 4's actor seam
answered with one fixed `DEMO_USER_ID` and `docker compose up` had to produce a database in which
that identifier resolved. Phase 5 replaces the seam with real authentication, so the seed's reason
is gone — and a shipped account with a known identity in a public repository is a liability rather
than a convenience.

**Options**

- **Keep the seed and give it a real password.** Rejected: the password would have to live
  somewhere readable — the repository, the compose file or the README — and would then be a real
  credential on every machine that runs this stack (T-5-03).
- **Keep the seed with an unusable `password_hash` as a discoverable "example row".** Rejected:
  it is a row nobody can log in as, whose only effect is to make `GET /users` non-empty and
  confuse the first person who reads it.
- **Delete it.**

**Decision**
Step 2b of `docker/entrypoint.sh` is deleted in full — 94 lines — and the header's step list is
back to 1 / 2 / 3: wait, migrate, serve. `DEMO_USER_ID` is gone from `src/`, `tests/` and
`docker/`; `grep -rn DEMO_USER_ID src/ tests/ docker/` exits 1. **A fresh volume ships zero
users**, and no account and no password exists anywhere in the repository. The documented path is
register → click **Authorize** in Swagger → call anything, stated in the OpenAPI description
itself (D-14).

**Consequences**

- **The claim is rehearsed, not asserted.** `evidence/05-15-cold-start.txt` runs
  `docker compose down -v`, records what the wipe destroyed, brings the stack up on an empty
  volume, observes three startup steps and no fourth, `SELECT count(*) FROM users` returning `0`,
  and then walks the documented path end to end: register, register a teammate, log in, read the
  profile, create a list, create a task, `GET /users`, assign — followed by one
  `docker compose logs api | grep task_assigned_email` returning exactly one line. One attempt.
- **A gate was retired as a deliberate act, and replaced rather than deleted.**
  `test_the_module_says_it_is_not_authentication` asserted that `actor.py` told the reader it was
  a seam and not authentication (ADR-044). Phase 5 made that sentence false in the most direct
  way possible: the module *is* authentication now. It is replaced by a **positive** assertion of
  the property that still matters — that `actor.py` names no credential library and no signing
  scheme, scanning for `jwt`, `pwdlib`, `argon2`, `hs256` and `rs256`, because a decode
  hand-rolled in the presentation layer would have to spell one of them. A first draft of that
  list forbade the English words "algorithm" and "secret" and immediately collided with the
  docstring the same change required; the shipped tuple is implementation names only, and
  `actor.py` says "bearer token" throughout rather than naming the format.
- **One demo row survives on developer machines and cannot become an account.** Its stored
  `password_hash` is `"!"`, which is not an encoded Argon2 hash, and the adapter answers `False`
  for it (ADR-063). `docker compose down -v` removes it; a fresh volume never has it. The
  05-15 cold start did exactly that and recorded the row it destroyed.
- `ADR-045` is refined, not contradicted: the seed was the right answer for a phase with a fixed
  actor and the wrong one for a phase with real accounts.

---

## ADR-076: the HTTP harness splits in two, and the statement counts become 2 and 4

**Context**
ADR-054 recorded measured statement counts — 1 for the task-list collection, 3 for the task
collection — and the property they defend: *invariance*, that one list and many lists cost the
same number of statements, which is what "no N+1" means. D-11 adds a per-request `SELECT` on
`users` to confirm the token's subject still exists. 05-CONTEXT stated that consequence as
unconditional. Research found it was not: `api_client` did not override `get_current_actor`, so
if Phase 5's harness *started* overriding it, the counts would stay at 1 and 3 and D-11's cost
would never be observed. A statement-count test still reading 1 and 3 because the dependency was
overridden would hide the very thing it was measuring.

**Options**

- **Issue real tokens everywhere.** Every one of ~120 Phase 4 HTTP tests would have to seed its
  own caller row and mint a header, for a property none of them is about.
- **Override everywhere.** Cheap, and D-11 becomes unmeasurable.
- **Two harnesses, with the choice between them written down.**

**Decision**
`api_client` installs a default `get_current_actor` override, so the Phase 4 suites keep testing
task lists rather than tokens. `authenticated_client` is the same fixture **minus that one line**
— it overrides `get_uow` and nothing else, so the real dependency runs, the real token is decoded
and the confirmation read happens. The 401 legs, the permission matrix's anonymous column and
`test_statements.py` all use it. Each fixture's docstring states what the other cannot measure.

The measured counts, on the real authenticated path, **as the owner**: `GET /api/v1/task-lists`
issues **2**, the task collection issues **4**. Each entry is named in the constant's comment,
with the actor lookup first.

**Consequences**

- **The property under test did not change; a measurement did.** The module docstring says so
  explicitly, so a later reader does not mistake a number for a target and "fix" it. The
  `for_one == for_many` assertions are untouched.
- **Counts now differ by role, and that difference was measured rather than derived.** Owner
  `GET` of one task: three `SELECT`s. Assignee: two. Owner `PATCH .../status`: four `SELECT`s and
  one `UPDATE`. Assignee: three and one `UPDATE`. The saving is ADR-059's assignee short-circuit,
  and the *reason* for it is the disclosure, not the statement. **The rule that follows: any
  statement-count assertion must name the role it measures**, or it will read as a regression to
  the next person.
- `bearer_header(app, user_id)` mints through the application's **own** token service, narrowed
  once off `app.state.security`. `grep -c "JwtTokenService" tests/integration/conftest.py` prints
  `0`, so no test can restate a secret, an algorithm or a lifetime and drift from the application.
- `acting_as` impersonates and does not authenticate; its docstring now says so, and says that
  combining it with `authenticated_client` is a contradiction rather than a convenience.

---

## ADR-077: `GetProfile` is a second use case, so ADR-044's seam type never had to change

**Context**
AUTH-05 needs `GET /api/v1/auth/me` to return the caller's own profile. The dependency that
authenticates the caller has already loaded that user's row — D-11 confirms it on every request —
so the profile is, in one sense, already in hand.

**Options**

- **Widen `CurrentActor` from a `UUID` to a `User` (or to a small actor object).** Free at
  `/auth/me` and expensive everywhere else: `CurrentActor` is a parameter of every router handler
  in the project, and every command in the application layer starts with `actor_id: UUID`.
  Changing the seam's type would rewrite eleven router signatures and reach into the DTOs, to
  serve one route.
- **Return the profile from the actor dependency as a second value.** The same coupling with a
  worse shape.
- **A second use case that loads the user by id.**

**Decision**
`GetProfile`. `CurrentActor` keeps its name, its `UUID` type and its target function, and not one
router, request schema, command or use-case signature moved because authentication arrived. The
clearest evidence is that `test_current_actor_depends_on_this_module_s_provider` survived the
rewrite of `actor.py` verbatim.

**Consequences**

- **Named cost: `GET /auth/me` issues two `SELECT`s against `users`** — one in the actor
  dependency, one in the use case. It is written in `profile.py`'s docstring rather than left for
  a reader to discover in a query log. For the one route in the API where the caller *is* the
  resource, paying one redundant indexed lookup is the cheaper side of the trade.
- **ADR-044 is what paid out here.** That entry called the Phase 4 actor a seam and predicted that
  only its body would be replaced. It was, in one file.
- `GET /auth/me` also declares a **404** that the plan enumerating its legs (200/401/500) omitted:
  `GetProfile` raises `UserNotFoundError` when the account is deleted between the token check and
  the profile read, and `profile.py` documents that race. This module's rule is that every route
  declares its full refusal set, and an undeclared but reachable refusal is exactly the
  dishonesty the rule exists to prevent.

---

## ADR-078: `SecurityResources` carries the token lifetime as well as the two adapters

**Context**
Phase 3 established the composition-root shape: `create_app` builds a frozen, typed container
from `Settings` and stores it on `app.state`; `dependencies.py` narrows it **once**, privately;
every provider reads a field off it. `dependencies.py` reads no configuration at all
(`grep -c "get_settings"` over it prints `0`), which the research flagged as a property a naive
Phase 5 would break by calling `get_settings()` inside each new security provider (correction
RC-3). Then `POST /auth/login` needed `expires_in`, which must describe the lifetime the token
was *actually* signed with — and the `TokenService` port exposes no lifetime, while `Login` needs
the number as a plain `int`.

**Options**

- **`get_settings()` in the login router.** The exact shape RC-3 forbids, and it would make
  `dependencies.py`'s "one narrowing, no per-request configuration" claim false.
- **A second read of `settings.jwt_expire_minutes` in a provider.** Two reads of one setting,
  which agree until one of them is changed.
- **A third member on the container both answers are built from.**

**Decision**
`SecurityResources` is a frozen slotted dataclass with three members: the `PasswordHasher`, the
`TokenService`, and `access_token_expire_minutes: int`. `create_security_resources(settings,
clock)` populates all three from one call, so `expires_in` and the `exp` the token was signed
with come from a single expression two lines apart. `dependencies.py` narrows it in one private
helper, `_security`, beside the database narrowing, and hands out port-annotated providers.

**Consequences**

- **The container is no longer "the two adapters", and the inconsistency is argued at the field
  rather than in a changelog.** A reader comparing the third member to its two neighbours would
  otherwise read it as an accident.
- **The field annotations are the ports, and that is pinned with `get_type_hints`.** Both adapters
  satisfy their ports, so annotating the fields with the concrete classes would type-check and run
  identically — the only thing it would break is the reason the container exists, which is a claim
  no other test could make.
- **Two narrowings, not one per module.** `dependencies.py`'s docstring argues the count: fusing
  the database and security containers would couple every unit test of one half to the other.
- **Building the container performs no I/O, falsifiably**: `socket` and `open` are replaced with
  objects that raise and the builder is called between them. That is what keeps
  `test_creating_the_app_opens_no_connection` true.
- The hasher's ~37 ms cached dummy hash (ADR-064) is therefore paid once per application rather
  than once per login, which is the practical payoff of the container over a per-request provider.

---

## ADR-079: register answers 201 with a `Location` of `/api/v1/auth/me`

**Context**
D-09 fixes register's answer: **201 with the profile and no token** — `{id, email, full_name,
created_at}`, never the hash — because logging in is a separate step through the OAuth2 form,
which is what Swagger's Authorize button drives (AUTH-02). This project's convention, from
Phase 4, is that a 201 carries a `Location` header pointing at the created resource. There is no
`GET /users/{id}` route in this phase.

**Options**

- **Add `GET /api/v1/users/{id}`** so the header can point at the canonical resource. Rejected:
  it is a route no requirement asks for, it would need its own permission answer in the matrix,
  and it would widen the directory disclosure of ADR-068 from a list to a probe.
- **Omit the `Location` header.** Rejected: the convention exists so a client is told where the
  thing it created lives, and a 201 without one is the weaker answer.
- **Point at `/api/v1/auth/me`.**

**Decision**
`Location: /api/v1/auth/me`, resolved from the profile handler's *name* rather than written as a
literal. It is a divergence from the Phase 4 convention — the URL is not the created resource's
canonical address, it is "the place the caller will read this profile from once they have a
token" — and the argument is written in `register_user`'s docstring, which is the copy this entry
points at.

**Consequences**

- A client following the header without authenticating first gets a 401, which is correct and
  slightly surprising. The docstring says so.
- **Register also returns a token to nobody, on purpose.** An account is created and then
  exchanged for a token in a second call. That keeps exactly one code path that issues tokens, and
  it is the path Swagger drives.
- Register and login are the only two handlers in the project with **no caller parameter**, and an
  absent parameter is invisible. Each docstring states the absence, why it exists, and that the
  permission matrix's anonymous column is what proves it over HTTP.

---

## ADR-080: revision `0002` — a transient `server_default`, and one index argued against two refusals

**Context**
`User` had no `full_name`, which AUTH-01 and ASGN-03 both require, so the column had to be added
`NOT NULL` to a table that may already hold rows. Separately, D-25 asks for an index on
`tasks.assignee_id`.

**Options for the column**

- **Add it nullable and leave it nullable.** Rejected: the entity requires it, so the schema
  would be weaker than the domain for no reason.
- **Add it `NOT NULL` with a permanent `server_default`.** Rejected: a default in the schema is a
  second place the value can come from, and the application always supplies one.
- **Add it `NOT NULL` with a `server_default` dropped in the same `upgrade()`.**

**Decision**
The third. `alembic check` is the gate that proves the default did not survive — it compares the
reflected database to the models, and a leftover default is drift.

**Options for the index**

`models.py` already refuses two other speculative indexes with written-out reasons, so a third
index needs its argument written in the same voice or it reads as inconsistency.

**Decision**
`ix_tasks_assignee_id` is created, and the argument is: PostgreSQL does not index a foreign key
automatically; no unique constraint covers `assignee_id` (unlike `task_lists.owner_id`); it is the
**entire** `WHERE` clause of `GET /api/v1/tasks/assigned-to-me` (D-02); and it is the scan
performed for every `ON DELETE SET NULL` when a user is removed. The name joins
`constraints.py` as its thirteenth entry, spelled as a literal in the revision per ADR-025, and
`test_the_naming_convention_produces_every_d12_constraint_name` asserts thirteen names against
the compiled DDL as an exact count.

**Consequences**

- **The populated-table claim cannot be proved by this test suite, and that gap is the reason a
  live rehearsal was scheduled.** `migrated_database` runs `downgrade base` first, so
  `taskmanager_test` is always empty when `0002` runs and the transient default is never
  exercised. The compose `taskmanager` database was at `0001` with a row in it — the exact case —
  so the image was rebuilt and the container restarted, which runs `alembic upgrade head` through
  its own entrypoint. Capture: `evidence/05-03-live-upgrade.txt`. Afterwards: `version_num =
  0002`, the existing row carrying the default's filler, `\d users` showing `full_name | character
  varying(100) | not null` with an **empty Default column**, and `alembic check` reporting no new
  operations.
- **That rehearsal found a defect no test in this repository could have found.** The Phase 4 demo
  seed wrote its row with a hand-written column list that did not include `full_name`. The
  `INSERT` became a `NotNullViolation`, and `ON CONFLICT DO NOTHING` did not absorb it and could
  not have — PostgreSQL checks `NOT NULL` while building the candidate row, before the arbiter
  index is consulted. Under `set -eu` the container aborted before serving: `docker compose up`,
  this project's core value, broken by one column. The seed is a shell heredoc (ADR-037), so
  nothing imports that `INSERT`; ADR-037 argues that the cold-start rehearsal is the stronger
  proof in exchange, and this is that argument paying out. (The seed itself was deleted three
  plans later by ADR-075.)
- **The rule that follows:** if a migration's claim is about rows that already exist, the suite
  cannot prove it — schedule a run against a populated database.
- `test_the_migration_directory_holds_exactly_one_revision` was retired out loud, named in the
  docstring of `test_the_revisions_form_one_unbroken_chain_ending_at_the_head` that replaces it.
  A file count says nothing about whether the revisions can be *walked*; a second head or a wrong
  `down_revision` would satisfy the count and break `upgrade head`. The chain test reads through
  Alembic's own `ScriptDirectory` against a deliberately unusable DSN, so an edit that made it
  touch a database would fail loudly rather than quietly connect to whatever the environment
  points at.
- Splitting one revision file across two commits left the *developer's* test database at a version
  whose newer `downgrade()` could not run. Repaired with one `CREATE INDEX IF NOT EXISTS` against
  `taskmanager_test` only. It is an artifact of the commit split, not of the shipped chain: a real
  deployment only ever walks `0001 -> 0002` forward.

---

## ADR-081: `GET /api/v1/tasks/assigned-to-me` is a flat route returning a bare array

**Context**
D-01 makes an assignee's parent list invisible: `GET /task-lists/{id}` and
`GET /task-lists/{id}/tasks` answer them 404, and `GET /task-lists` stays strictly "lists I own".
An assignee can therefore reach their task only through the nested URL — and has no way to find
out what that URL is.

**Options**

- **Let assignees see the lists their tasks live in.** Rejected: it discloses the list's name, its
  owner and its other tasks, which is the whole property D-01 buys.
- **A query parameter on the existing collection — `GET /task-lists/{id}/tasks?assignee=me`.**
  Rejected: it still requires knowing the list id, which is the thing the assignee does not have.
- **One new flat, read-only route.**

**Decision**
`GET /api/v1/tasks/assigned-to-me`, filtered on the **token's subject** and never on a
client-supplied identifier, ordered by `created_at`, `id`, with no pagination (ADR-043). It
returns a **bare array** of `TaskResponse` rather than the per-list envelope, because that
envelope carries completion statistics and a percentage has no meaning spread across lists.

**Consequences**

- **Each entry's `task_list_id` is the point of the route**, not incidental: it is how a caller
  who cannot see the list builds the nested URL the task is actually worked on through. The HTTP
  test does not assert the field is present — it **builds the nested URL from it and follows it**,
  for a task in a list the caller cannot see.
- **The safety property is the argument, not the query.** `list_for_assignee` takes exactly one
  parameter and filters in SQL; what makes that safe is that the *argument* comes from the token.
  The use case's docstring names the condition under which a future change would need a guard
  (T-5-11).
- The discovery fixture puts one of the assignee's tasks in a list a third party owns, so the
  three plausible wrong answers — every assigned task, every task in a reachable list, insertion
  order — each fail.
- `list_for_assignee` takes no `status` or `priority` keyword, and the port comment records that
  as a decision rather than an oversight: filtering `assigned-to-me` is a Deferred Idea, and
  widening a signature later is additive while a caller depending on filters nobody asked for is
  not.

---

## ADR-082: an address that crosses an `EmailStr` boundary must use a real top-level domain

**Context**
The integration suite's address convention is `demo@example.test`, which works everywhere it is
used because those addresses are seeded straight onto the `User` entity, and the entity validates
no format (Phase 2 D-04 puts that at the boundary). `RegisterRequest.email` is an `EmailStr`,
backed by `email-validator`, which refuses reserved and special-use names outright: *"The part
after the @-sign is a special-use or reserved name that cannot be used with email."* `.test` and
`.local` are both refused; this was verified directly against the validator.

**Options**

- **Loosen the schema** — `str` with a regex, or `EmailStr` with the deliverability check
  relaxed. Rejected: the point of `EmailStr` is that we do not hand-write address validation.
- **Change the whole suite's convention to a real TLD.** Rejected as unnecessary churn: the
  seeded addresses never cross the boundary.
- **Use a real TLD for the addresses that cross it, and record the rule.**

**Decision**
Addresses posted through an HTTP boundary use `example.com`. Addresses seeded as entities keep
`example.test`. This entry is the record, because the failure mode is not obvious.

**Consequences**

- **The insidious half is worth naming.** Six tests failed loudly with a 422 where a 201 was
  expected. One failed *green-looking*: a short-password test asserting a domain 422 received a
  **request-validation** 422 instead — same status, differing only in the shape of `errors`. A
  weaker assertion would have passed while testing nothing.
- Phase 7's README and any `curl` example it carries must use a real TLD for the same reason, or
  the documented quickstart fails on its first command.

---

## ADR-083: the permission model is one table, bound to the published document

**Context**
AUTH-06 is a cross-product, not a list: nineteen operations by four kinds of caller — owner,
assignee, stranger, anonymous. D-04 requires it to be proven by one parametrized test over the
real HTTP harness, with a missing cell **visible in the table**, and the same table reused as
documentation in Phase 7.

**Options**

- **Per-route test modules asserting each role separately.** That is what the rest of the suite
  already does, and it cannot answer "is every cell covered?" — an unwritten test is an absence in
  a file, which nobody sees.
- **A table assembled from constants imported from the five sibling modules that own those
  paths.** This package's strongest convention, and set aside here on purpose: a table assembled
  from fragments defined elsewhere is no longer a table a human can read, and D-04 says this one
  is read as documentation.
- **One module-level table, spelled out, with the paths bound to the document by a test.**

**Decision**
`MATRIX` holds nineteen `Row` entries, each naming the method, the published path template and the
four expected statuses in the research document's own column order, positionally — naming each
field would make every entry three lines long and destroy the one property D-04 asks for above all
others. 76 cells are driven by one parametrized test whose ids read
`08-assignee-GET-/api/v1/task-lists/{list_id}`, so `-k anonymous` selects exactly that column and
a failure names the row it came from.

**Consequences**

- **Nothing is lost by spelling the paths out, because the table is bound to the published
  contract.** `test_the_table_covers_every_operation_the_document_publishes` reads
  `app.openapi()["paths"]` (ADR-057) and asserts set equality in **both** directions — an
  unmeasured route and a stale row both fail — with `len(published) == 19` as the non-vacuity
  guard. A fourth test pins the row numbers to 1..19, the `(method, path)` pairs to unique, and
  the cell count to `4 x 19`, because a set swallows a duplicate the coverage test would not see.
  **This is a stronger check than agreeing with a helper in a sibling test.**
- **Every cell asserts a document, not a number.** 401 cells assert the challenge header, the
  six-member body and the `code`; 403 cells go through `assert_forbidden`; 404 cells go through
  `assert_not_found` or `assert_task_not_found` according to which shape the row is owed. Every
  2xx cell additionally asserts that **no** challenge header came back, so "open" means open
  rather than a refusal that happened to carry a 2xx.
- **The matrix deliberately does not re-litigate per-route behaviour.** The assignee's legs are
  already proven in `test_assignment.py` with owner-side re-reads. The matrix's contribution is
  completeness and the anonymous column.
- **Every destructive cell is isolated rather than ordered.** The fixture is function-scoped:
  two rows delete the subject the middle rows address and one renames it. A matrix whose later
  rows depend on its earlier ones passes for the wrong reason.
- **One provider is overridden beyond the harness's own, and it is argued:** `get_engine`, pointed
  at the connection the test already owns. `/health` is the single route in the table that asks
  the database a question outside the unit of work, and against the harness's deliberately
  fictional DSN it answers 503 — row 1 would then be measuring the fixture rather than the route's
  openness. Nothing about authentication is replaced.
- **All 76 cells were right on the first run.** The table lifted from `05-RESEARCH.md` matched the
  running application exactly; no cell surprised and no production defect was exposed. That is
  recorded because it is the first time this cross-product had been driven as a cross-product,
  and because a suite that finds nothing is either well-built or badly written — the distinction
  matters (the same note ADR-056 makes about Phase 4's 79 HTTP tests).
- Adding a twentieth operation without a row is now a failing test that names the unmeasured
  `(method, path)`. The same table is what Phase 7's README should reproduce.

---

## ADR-084: the published placeholder is refused at boot, and `make env` writes a real secret

**Context**
ADR-061 raised the `JWT_SECRET` floor to 32 characters, sized against RFC 7518 §3.2 and PyJWT's
HS256 warning. It was never checked against the one value this repository publishes:
`.env.example` ships a 34-character placeholder, which clears the floor, and the documented setup
was to copy that file verbatim (D-15). Phase 5 verification forged a token offline with the
published string and read another account's profile from `GET /api/v1/auth/me` with 200 — against
the container running on this machine, started from exactly the documented path. `GET /users`
makes the subject identifier trivially obtainable, so the two decisions compound into full
impersonation by any reader of the public repository.

**Options**

- **Refuse the placeholder and keep the copy step.** One line of validation, and it breaks the
  brief's one-command review path: the evaluator's first command would produce a configuration
  that cannot boot, with no documented way to fix it but to invent a secret.
- **Generate the secret in the container entrypoint when it is absent.** Zero-edit startup, but
  the value would change on every container start: every token issued before a restart would be
  refused afterwards, and `make docker-test` and `docker compose up` would disagree about who is
  logged in. A generated secret that nobody can keep is a different defect.
- **Generate on the host, in a `make` target, and refuse the placeholder at boot.**

**Decision**
The third. `make env` runs `scripts/init-env.sh`, which writes a freshly generated 64-character
secret into an untracked `.env` — creating the file from `.env.example` when it is absent,
replacing only the placeholder line when it is present, and changing nothing at all when the
secret is already real. `Settings` then refuses any `JWT_SECRET` beginning `replace-me`, with a
message naming `make env` as the remedy, and `jwt_algorithm` becomes `Literal["HS256"]`. This
amends D-15: step one of the evaluator's path is now `make env` rather than a copy.

**Consequences**

- **The rule is a prefix check, and it protects against exactly one thing.** It stops the value
  published here and half-edited copies of it. An operator who types their own weak
  32-character secret is not protected, and this ADR does not claim otherwise; a strength
  estimator would be a different decision, with false refusals of its own.
- **No code default was introduced.** CLAUDE.md's configuration rule still holds in full: the
  generated value exists only in an untracked `.env`, never in a tracked file and never as a
  fallback in `Settings`.
- **`make env` is the one target that needs neither Python nor Docker** — a POSIX shell, `awk`,
  `cp`, `mv` and either `openssl` or `/dev/urandom` — because it runs before either is set up.
  It never overwrites a secret that is already real, so it is safe to re-run, and
  `tests/unit/test_env_bootstrap.py` drives the real script through `sh` to prove all three
  behaviours.
- **`HS512` is now refused rather than accepted against a floor sized for HS256.** Supporting it
  properly would mean a 64-byte floor and a model validator pairing the two; the adapter signs
  with one algorithm, so the closed set has one member and a mismatch fails at boot instead of
  at the first login (WR-03).
- **Tokens minted under the placeholder stop working.** On this machine that was the point: the
  running container was rebuilt onto a generated secret as the first step of the fix.

---

## ADR-085: every use case must be reachable from the fakes-based unit suite, checked by an AST walk

**Context**
TEST-01 says "every use case" has a unit test against in-memory fakes. Nothing enforced the
"every". A use case added in a later plan could ship with an integration test and no unit test at
all, and the suite would stay green: the coverage gate would be satisfied by the HTTP path
exercising the same lines, and nobody reading a diff notices a file that was *not* added. The
failure is silent by construction, which is the only kind worth building a gate for.

**Options**

- **Trust the plan checklist.** Free, and it is what had been happening; the audit that produced
  this phase found the gap by hand, which is the argument against relying on finding it by hand.
- **Require a per-use-case test file by name.** A naming convention is cheap to check and cheap to
  satisfy without writing an assertion: an empty module with the right name passes.
- **Walk the AST of `tests/unit/application/` and require each public use-case symbol to be
  imported and then named in a call or a construction.**

**Decision**
The third. `tests/architecture/test_use_case_totality.py` discovers the expected set from
`application/use_cases/` — every public module-level symbol, by AST, never a hand-kept list — and
requires each one to be imported and used under `tests/unit/application/`. A use case with no
fakes-based test fails a build.

**Consequences**

- **The claim is reachability, not correctness, and the gate says so.** It proves a unit test
  constructs or calls the use case; the coverage gate proves the lines ran; only a human reading
  the test knows whether it asserts anything worth asserting. Stating the limit is what stops the
  gate being read as more than it is.
- **The expected set is derived, so it cannot drift.** A new use case joins the requirement by
  existing. There is no registry to forget to update, which is the defect the naming-convention
  option shares with the checklist.
- **A use case that is genuinely presentation-only has nowhere to hide.** It would have to be
  moved out of `application/use_cases/`, which is a visible change to the layer it lives in
  rather than an omission in a test directory.

---

## ADR-086: endpoint totality is observed at run time from `app.openapi()`, not asserted from a list

**Context**
TEST-02 says "every endpoint" has an integration test. The published document
(`app.openapi()["paths"]`) is the only authority on what "every endpoint" means, and a test cannot
know what the suite *requested* by reading source: a request travels through fixtures, helpers and
parametrized tables, and the path that reaches the app is a template the test never spells.

**Options**

- **A registry of expected operations beside the permission matrix.** A second home for a truth the
  application already publishes; it drifts the first time a route is added, and it drifts silently.
- **An `httpx` event hook recording the requested URL.** It sees the concrete path
  (`/api/v1/task-lists/<uuid>`), never the template, so every request would record a distinct
  operation and the comparison would have nothing to compare.
- **Wrap the ASGI application in the integration fixtures and record the matched route.**

**Decision**
The third. The integration harness wraps the app, records the matched operation into a run-wide
`REQUESTED` set, and `tests/integration/test_endpoint_totality.py` compares that set with
`app.openapi()["paths"]`. The total half skips on a partial selection — it cannot be true of a
single-module run — while the recorded-subset half, which catches a recorded operation the document
does not publish, is always on.

**Consequences**

- **A published operation no test requests fails a full run.** That is the property TEST-02 asks
  for, and it is checked against the document rather than against anyone's memory of it.
- **The total half is conditional, and that is a real hole with a stated shape.** A developer who
  only ever runs a focused selection never sees it. CI and `make test` run the full suite, so the
  hole closes before a merge, not before a commit.
- **It records what was requested, never what was asserted.** An operation reached by a test that
  checks only its status code counts as covered here; ADR-088 is the gate for that question, and
  the two are deliberately separate.
- **ADR-057's `_IncludedRouter` fact is why the resolver matches by suffix.** FastAPI's include
  machinery means the recorded path and the published path do not always compare as equal strings.

---

## ADR-087: every raisable domain error leaf must have its RFC 9457 code asserted somewhere

**Context**
D-06 fixed the error body and ADR-021 mapped the hierarchy to statuses. What nothing checked was
whether each *leaf* had ever been produced through the API and had its `code` asserted. A new
`DomainError` subclass raised in a use case answers with whatever the MRO walk finds, which is
frequently the right status and the wrong `code` — and a negative-path test that asserts only the
status passes.

**Options**

- **Assert the status table is total.** Cheap, and it proves nothing about the wire: the table maps
  classes to integers, and the `code` is derived elsewhere.
- **A registry of expected codes.** The second-home problem again, and here the registry would be
  the very thing the test is supposed to discover.
- **Walk `src/` for leaves actually raised, then require each one's `code` as a non-docstring
  string literal somewhere under `tests/`.**

**Decision**
The third. `tests/architecture/test_error_contract_totality.py` collects every `DomainError` leaf
that some module under `src/` actually raises, requires every leaf to be declared in
`domain/exceptions.py`, and requires each raisable leaf's `code` to appear as a real string literal
in a test. It excludes itself from its own scan, or it would satisfy its own requirement.

**Consequences**

- **A leaf nobody ever asserted on fails a build.** Adding an exception now costs one assertion,
  which is the cost of the exception being part of a published contract.
- **"Raised somewhere under `src/`" is the scope, deliberately.** A leaf that exists but is never
  raised is not on the wire and owes nothing; the declaration check is what keeps it from being
  defined in a corner instead.
- **A string literal is a weak proof and a strong signal.** The gate cannot tell an assertion from
  a comment-shaped constant, but it can tell the difference between a code that appears in the test
  suite and one that does not, and the second is the failure that was actually happening.
- **Self-exclusion is load-bearing and was found the hard way.** Plan 06-01 produced a live example
  of a gate that its own non-vacuity guard satisfied; see ADR-090's consequences.

---

## ADR-088: an HTTP test must assert on something the API said, and a mutating one must re-read it

**Context**
Roadmap SC-3 is two claims: every test asserts on a response body rather than a status code alone,
and every mutating test re-reads through the API. Both were house style, written into module
docstrings from plan 04-09 onward, and both were partly untrue — a sweep found 29 tests asserting
status codes only and a set of mutations nothing read back. A status-only test passes against a
handler that returns an empty body; a mutation nobody re-reads passes against a handler that
never committed.

**Options**

- **Keep it as a docstring standard.** It is what produced the 29, so it is not a candidate.
- **Require a literal body member in every test.** Measured against the real suite, this reported
  29 false positives out of 30 findings: the suite reaches response members through helpers, named
  fixtures and intermediate locals, and a rule that demands a literal punishes exactly the tests
  that factored their assertions well. A noisy gate gets deleted.
- **An AST gate with taint tracking to a fixed point, scoped to tests that issue a request.**

**Decision**
The third. `tests/architecture/test_assertion_quality.py` accepts four shapes — a response member,
a name tainted from one, a named `Response`-taking helper, or a recorded side-effect fixture the
test declares — and propagates taint to a fixed point, which reduced the 30 findings to 1 real
offender. Half (a) has no opt-out, because the rule stated correctly needs none. Half (b), the
re-read, has exactly one: `@pytest.mark.no_reread("<reason>")`, whose node id must appear in
`REQUIRED_NO_REREAD` in the gate module.

**Consequences**

- **The exemption has to keep earning itself.** Beyond being listed, every exempted test is
  re-parsed with its marker stripped and must still be an offender. An exemption that stops being
  necessary — because someone added a re-read — fails the build until it is deleted. No other
  exemption list in this repository has that fourth check, and it is the one that stops the list
  becoming a graveyard.
- **`REQUIRED_NO_REREAD` is compared as an equality in both directions.** A marker on an unlisted
  test is an exemption granted without editing the gate; a listed id whose test lost its marker is
  a stale entry. A subset check catches neither.
- **The rule is per test, not per response, and that is a stated hole.** A test that asserts one
  body and only a status code on a second response satisfies it. The per-response rule is a much
  larger change with an unmeasured false-positive rate, and the whole argument above is that a
  noisy gate does not survive.
- **A gate's detection rules are code and get their own tests.** 20 of that module's 28 tests are
  planted snippets. Two of the rules were wrong in ways only the tree could reveal, and both were
  caught in minutes because they were executable rather than prose.

---

## ADR-089: the coverage configuration is pinned by a test, and greenlet is declared to it

**Context**
CLAUDE.md states the coverage rule in prose: the 75 % threshold is never lowered, it is never
reached with `# pragma: no cover` or an `omit` entry, and the tests stay out of the denominator.
Prose is not a gate. One character in `pytest.ini` turns 75 into 70; one line in `pyproject.toml`
removes a package from the denominator. Both leave every test green and the reported percentage
higher than before, which is the direction nobody audits.

**Options**

- **String-match `--cov-fail-under=75` in the addopts.** Red on `--cov-fail-under=80`, which is a
  strictly better configuration — it punishes the one change nobody needs to prevent.
- **Assert the coverage number itself.** 100 % is a norm this project holds to, not a requirement
  (D-12). A test pinning it would go red on an honest refactor that added a defensive branch, and
  the only way back to green would be to write a test for something the code does not do.
- **Parse both configuration files and assert every fact the number rests on, with the threshold as
  a floor.**

**Decision**
The third. `tests/architecture/test_coverage_configuration.py` reads `pytest.ini` with
`configparser` and `pyproject.toml` with `tomllib` and asserts: `--cov=taskmanager`;
`--cov-fail-under=N` with `N >= 75`, parsed as a number; `source == ["taskmanager"]`; `branch`;
`concurrency == ["thread", "greenlet"]`; no `omit` key; no second `fail_under` home; `exclude_also`
exactly four entries; and zero `# pragma: no cover` under `src/`, reported by `file:line`. Each of
those was planted and observed red before the gate was trusted.

**Consequences**

- **`concurrency = ["thread", "greenlet"]` was added here, and it fixed a false negative nobody
  would have investigated.** Running `make docker-test` for the first time against a suite with
  routers in it reported 99.08 % on Python 3.13: 18 lines missing, every one of them a
  `return XResponse.from_result(...)` or a `Location` header — the lines that run *after* a
  handler's first `await` into SQLAlchemy's greenlet bridge, in a frame coverage stops following
  unless greenlet is declared. The tests asserting those very response bodies were passing. With
  the line added, Python 3.13 reports 100 % and Python 3.14 is unchanged. A coverage error that
  makes the number too low is the one kind that never gets reported.
- **The host and the container agree on the percentage and disagree on the denominator, for a
  reason that is not a defect.** 1643 statements on CPython 3.14 against 1796 on 3.13, both at
  100 % with zero partial branches: Python 3.14 evaluates annotations lazily (PEP 649/749), so the
  annotation lines in the schemas and router signatures are not executable statements there.
  D-11's agreement is about the percentage and the pass count, and both match exactly.
- **`exclude_also` is compared by exact value, which costs something.** A legitimate fifth entry
  fails the gate until it is argued for in `EXPECTED_EXCLUDE_ALSO`. That is the point: a fifth
  entry is how a real exclusion would be smuggled in, and every weaker comparison waves it through.
- **The threshold keeps exactly one home.** `[tool.coverage.report] fail_under` and the
  `--cov-fail-under` addopt are two knobs for one rule, and coverage.py resolves the conflict
  without complaining. Keeping it in the addopts alone is what makes `make test`, `make
  docker-test`, CI and a bare `pytest` gated by identical bytes.

---

## ADR-090: every collected test carries `unit` or `integration`, and a collection hook enforces it

**Context**
`pytest.ini` has registered both markers since Phase 1, and `--strict-markers` refuses an
*unregistered* one. Nothing in pytest refuses a *missing* one. Measured at the start of this phase:
zero tests carried `unit`, 315 carried `integration`, and 704 carried neither — including a third
top-level directory, `tests/api/`, that the two-bucket vocabulary has no name for. A test outside
both markers is run by the full `pytest` nobody types while writing code, and by no selection
anyone does.

**Options**

- **Leave the markers unused and select by path.** `pytest tests/unit` works until a no-database
  test lands somewhere else, and it is how `tests/api/` came to exist in the first place.
- **Add the markers and rely on review to keep them.** The same argument as ADR-085: the omission
  is invisible in a diff, because what is missing is a line nobody wrote.
- **Make the partition total and add a collection-time guard that fails on an unmarked item.**

**Decision**
The third. `pytestmark` is a module-level line in all 81 collected modules, placed where the
integration modules already placed theirs; `tests/api/` was folded into
`tests/unit/presentation/` with `git mv`, and its two shared constants moved to a never-collected
`tests/problem_details.py`. `pytest_collection_modifyitems` in `tests/conftest.py` raises
`pytest.UsageError` naming the offending node ids when any collected item carries neither marker.
`make test-unit` runs the 755-test no-database slice with `--no-cov`.

**Consequences**

- **A new test cannot join the suite unmarked.** The guard was driven red by deleting one
  `pytestmark` line, under both a full run and a `-m unit` run, before it was trusted.
- **`tryfirst=True` pins an ordering that happens to hold anyway.** pytest's own mark plugin
  implements the same hook and *removes* deselected items, so running after it would mean an
  unmarked item was already gone. On pytest 9 a conftest implementation is called first regardless
  — observed with the decorator removed — but relying on registration order for that is relying on
  something no version promises, and the failure would be a silent hole rather than an error.
- **`make test-unit` uses `--no-cov`, not a threshold override.** `pytest.ini` also writes
  `coverage.xml`, and that file is the artifact D-11's agreement is read off; a partial run must
  not overwrite it. The slice does clear 75 % on its own today, which is precisely why it is not
  gated on a number nobody is defending.
- **It is a convenience subset, not a new gate.** It runs a strict subset of `make test`, so
  ADR-015's "a new gate goes in two places" does not apply and neither `.pre-commit-config.yaml`
  nor `ci.yml` learns about it.
- **The two-marker vocabulary is now closed.** A future test that is neither — a contract test
  against a running container, say — has to argue for a third marker in `pytest.ini`, in the guard
  and in this ADR, rather than arriving as an unmarked file.

---

## ADR-091: the deliberate-break spot check is a script, and it is the one tool allowed to write to `src/`

**Context**
Roadmap SC-4 asks for a deliberate break that turns the suite red, recorded in `AI_WORKFLOW.md`.
Done by hand it is a one-off anecdote, and the hand-run version of it in this phase produced two
breaks the suite did *not* catch — including token expiry, which was enforced by nothing. So the
check has to be repeatable. But it is also the only tool here that edits `src/` on purpose, which
makes its safety a bigger question than its findings.

**Options**

- **Keep it manual and documented.** An anecdote does not survive a refactor, and the two
  survivals prove the exercise is worth repeating rather than remembering.
- **Adopt a mutation-testing tool.** The honest choice for a larger budget; it is a dependency, a
  configuration and a multi-minute run for a deliverable whose whole review path is five minutes
  (D-08).
- **A POSIX shell script applying five named mutations, each with the tests that should care.**

**Decision**
The third. `scripts/break-check.sh` behind `make break-check` applies five mutations, runs a named
selection per break, asserts each turns red, restores the file and exits non-zero if any break
survives. It is held to three rules no other tool here needs: it refuses to start unless
`git status --porcelain -- src/` is empty; it restores through a trap installed before the first
mutation, and restores **only the files it touched**; and every mutation carries an
`assert old in s` precondition, so a drifted source line fails loudly instead of reporting a defect
nobody introduced.

**Consequences**

- **"Restore only what you touched" is a rule, not a preference.** A blanket
  `git checkout -- src/`, `git stash` or `git reset --hard` would destroy uncommitted work the
  script never touched, and plan 06-02 produced a live example of exactly that. The dirty-tree
  refusal makes the blanket form *usually* harmless, which is not the same as safe.
- **It is deliberately in no gate path** — not `make test`, not `.pre-commit-config.yaml`, not
  `ci.yml` (D-09). It runs a large selection five times over, and the value of a ten-second commit
  loop is that nobody is tempted to skip it. ADR-015's two-places rule does not apply, because
  this is a spot check and not a gate.
- **`BREAK_CHECK_PYTEST` is the one seam, and it exists for the unit test.**
  `tests/unit/test_break_check.py` drives the script as a program in a throwaway repository, where
  there is no `.venv` and running the real suite would defeat the point. Its three safety legs were
  each driven red by deleting the single line that provides the property.
- **A gate is not trusted until it has been driven red, and a gate must never be satisfiable by its
  own non-vacuity guard.** Both rules were paid for in this phase: ADR-087's gate was briefly
  green because the guard that proved it had scanned something also satisfied what it scanned for.
  Every gate this phase added was falsified at least once before being committed.

---

## ADR-092: an `exclude_also` entry is judged by what it removes, not by being on the pinned list (2026-09-19, amending ADR-089)

**Context**
ADR-089 pinned `exclude_also` by exact value and recorded four entries, and this log stated that
each was harmless. One was not. `\.\.\.` is an **unanchored** regex, and when the line it matches
is the header of a block, coverage.py excludes the **whole block**. Asked directly —
`Coverage(config_file="pyproject.toml").analysis2(...)` — it was removing:
`ListUsers.execute` (users/list.py:52-64), `ListTaskLists.execute` (task_lists/list.py:48-63),
`ListAssignedTasks.execute` (tasks/list_assigned.py:52-63) and `DomainError.__reduce__`
(domain/exceptions.py:70-71). Every one of those signatures returns a
`tuple[XResult, ...]`, which is all it took. That is an `omit` written as a regex, and CLAUDE.md
forbids reaching the number that way. Worse, the gate certified it: the pin made *removing* the
entry a red test, and the docstring of `test_the_exclusion_list_is_exactly_the_four_known_entries`
asserted in prose that none of the four excluded executable behaviour.

**Options**

- **Anchor the pattern** (`^\s*\.\.\.\s*$`). Fixes this instance and leaves the class of defect
  intact: the next unanchored entry — a decorator name, `if not TYPE_CHECKING:` — arrives with the
  same argument and the same gate waving it through, because a value pin can only ever say "this is
  the list somebody approved".
- **Drop the entry and keep pinning by value.** Necessary, and it is what makes the three
  remaining entries auditable, but on its own it is the configuration that just failed.
- **Drop the entry and add a gate that measures the effect.**

**Decision**
The third. `\.\.\.` is gone from `pyproject.toml` — coverage's own `DEFAULT_EXCLUDE` already
carries an *anchored* pattern for an ellipsis body, so every Protocol method and `@overload`
signature under `application/ports/` and `infrastructure/db/mappers.py` stays excluded without it.
`tests/architecture/test_coverage_configuration.py::test_no_exclusion_removes_a_real_statement`
then reads the exclusions back out of `analysis2` for every module under `src/taskmanager` and
fails on any excluded line that carries a statement, unless that line sits inside a stub body
(`...`, `pass`, a docstring, `raise NotImplementedError`) or inside an `if TYPE_CHECKING:` block —
the `orelse` of such an `if` deliberately not included, since code under the runtime branch runs.

**Consequences**

- **The gate is indifferent to spelling, which is the only property worth having.** A pragma
  comment, a default pattern and a hand-written regex all reach it as the same input: a line
  number coverage.py says it is not measuring. The literal pragma scan beside it keeps its own
  value as a faster, more readable message, not as the last line of defence.
- **The denominator grew and the percentage did not move.** Host CPython 3.14: 1643 → **1659**
  statements, 0 missing, 100 %. Container CPython 3.13: 1796 → **1813**, 0 missing, 100 %. 1080
  tests pass in both. So the three `execute` bodies were being exercised all along — the number
  was true and unmeasured, which is the good case and was in no way guaranteed. Had a line come
  back missing, the rule is CLAUDE.md's: write the test.
- **It was driven red twice, deliberately.** Once by re-planting the entry in `pyproject.toml`
  (the failure names `users/list.py:58: async with self._uow:` and its siblings, `file:line` plus
  source), and once as a test of its own —
  `test_the_exclusion_scan_catches_an_unanchored_pattern` plants a module whose signature mentions
  `tuple[int, ...]` over a real body, asks coverage.py for its verdict under a planted
  `[report] exclude_also` and under this repository's configuration, and asserts red for the first
  and clean for the second. A gate that only ever ran green on the tree that satisfies it is not a
  tested gate.
- **ADR-089's list is now three entries, and its statement counts are superseded by the two
  figures above.** That ADR is otherwise unchanged and still describes the gate correctly.
- **The lesson generalises past coverage.** Two of this phase's gates pin a configuration *value*
  (`EXPECTED_EXCLUDE_ALSO`, `EXPECTED_CONTRACT_NAMES`). A value pin proves that a human approved
  the list; it proves nothing about what the list does. Where the effect is askable — and here it
  was, through one public API — the gate should ask.

---

## ADR-093: RED is exit 1 with a FAILED line, measured against a baseline (2026-09-19, amending ADR-091)

**Context**
`scripts/break-check.sh` prints one line, and that line is the evidence offered for roadmap SC-4.
Its verdict was `if [ "$status" -eq 0 ]` survived, else red — so *any* non-zero pytest exit counted
as "the suite noticed". pytest exits 2 on a collection error or interrupt, 3 on an internal error,
4 on a usage error (a renamed test path), 5 when it collected nothing, and 1 with only `ERROR`
entries when a fixture fails — `grep -c '^FAILED '` counts that last one as zero. Reproduced with a
stub that prints pytest's "file or directory not found" and exits 4:

```
    red: 0 test(s) failed

All 5 breaks turned the suite red. src/ is back as it was.
exit=0
```

The same output appears with PostgreSQL down, when every integration test errors in
`_require_database`. There was also no baseline: a selection already failing for an unrelated
reason "caught" all five breaks. An evaluator who runs `make break-check` before `make up` was
shown proof of a property nothing had measured — the failure mode the script's own header says it
fears, reached from the other side.

**Options**

- **Require `FAILED` lines and treat everything else as red anyway.** Half the fix. A run that
  collected nothing would still be a "catch", and the more likely accident by far — no database —
  would still read as five caught breaks.
- **Run the whole suite once at the start and require it green.** One baseline for five different
  selections: cheaper than five, and it stops answering the question the moment a break's selection
  is narrower than the suite (all of them are), because a selection can be red while the suite is
  green only if... it cannot, but the reverse — a suite red in a file no break selects — would
  refuse a run that was perfectly valid.
- **A baseline per break, and a three-way verdict.**

**Decision**
The third. `check_break` now runs its own selection **unmutated** first and refuses, non-zero, with
the last line of pytest's output, unless that run exits 0. Then, after the mutated run, exactly
three outcomes: exit 0 is SURVIVED, exit 1 **with at least one `FAILED` line** is RED, and anything
else — including exit 1 with none — is an ERROR that stops the script non-zero with the tail of the
log. `src/` is restored before the verdict is read in every branch, so an abort cannot leave a
mutation behind.

**Consequences**

- **The run costs about twice what it did**, ten selections rather than five, a couple of minutes
  in total. That is the entire price, it is paid by a spot check nothing gates on (D-09), and the
  alternative is a success line that can be printed by a run which executed no test.
- **The unit test now covers the verdict, not only the safety.** ADR-091 recorded three tests, all
  of which ended before a single `check_break` completed; the defect above shipped underneath them.
  `tests/unit/test_break_check.py` plants all five mutation targets (parsed out of the script, never
  restated) and drives: a survivor on every break (exit 1, `5 of 5 breaks SURVIVED`, clean tree), a
  `FAILED` line on every break (exit 0, the success line, five `red: 1 test(s) failed`, clean tree),
  the four non-failure exit codes and the FAILED-less exit 1 (non-zero, no success line, stopped at
  the first break, clean tree), and a red baseline (refused, exactly one pytest invocation, and the
  file that invocation saw was unmutated).
- **The stub grew a parity seam.** A stand-in for pytest with one exit code can no longer reach the
  mutated run at all, so `a_stub_green_on_the_baseline` counts its invocations in a file and answers
  green on odd ones, the test's script on even ones. The count file is what turns "it refused before
  mutating" and "it stopped at the first break" into assertions rather than inferences.
- **Both new rules were driven red before being trusted**, by planting the old behaviour: the
  baseline refusal disabled (`if false`) reddens the baseline test alone, and the `*)` ERROR branch
  made unreachable reddens exactly the four exit-code rows and nothing else. Each edit was reverted
  by its own inverse replacement, never a blanket checkout.

---

## ADR-094: the break script traps HUP and QUIT too, and its signal test runs under dash (2026-09-19, amending ADR-091)

**Context**
ADR-091 records that the restore happens "through a trap installed before the first mutation".
The trap was `trap cleanup EXIT` plus `trap on_signal INT TERM`. POSIX does not run the EXIT trap
when the shell dies from an **untrapped** signal; bash happens to, dash does not, and dash is
`/bin/sh` on Debian — the base of the `test` image and of any Linux evaluator's host. HUP is what a
closed terminal tab or a dropped SSH session sends, QUIT is Ctrl-\, and this script spends about a
minute with a defect on disk. Reproduced with a stub that sends `kill -s HUP "$PPID"` mid-run:

```
dash  exit=129   M src/taskmanager/domain/value_objects/completion.py   <- left behind
sh    exit=129   (restored: macOS /bin/sh is bash)
```

The unit test passed on both platforms because it only ever sent TERM, which *was* trapped.

**Options**

- **Leave it: `make break-check` is run by hand and interrupted with Ctrl-C.** Ctrl-C is INT and
  was covered; the uncovered cases are the ones nobody chooses, on the one tool in this repository
  that writes to `src/`. The cost of the fix is one word per signal.
- **Rely on the EXIT trap and document the shell requirement.** It would mean this script's safety
  depends on which `sh` the evaluator's machine has, which is exactly the class of defect the
  POSIX-only rule in its header exists to avoid.
- **Name every signal, and test under the strict shell.**

**Decision**
`trap on_signal HUP INT QUIT TERM`, and
`test_the_trap_restores_the_file_when_the_script_is_terminated` is parametrized over all four
signals *and* over the shells — `sh` always, plus `dash` whenever `shutil.which("dash")` finds it,
which it does on this macOS host and in the container. Eight runs, about two seconds.

**Consequences**

- **A macOS developer now exercises the shell the image uses.** Without the `dash` axis the whole
  class of defect is invisible locally: bash's leniency is not a property the deliverable can rely
  on, and `/bin/sh` being bash is a macOS accident.
- **Driven red, both axes.** Narrowing the trap back to `INT TERM` reddens exactly four of the eight
  rows — `[sh-HUP]`, `[sh-QUIT]`, `[dash-HUP]`, `[dash-QUIT]` — and under dash the failure is the
  mutation still sitting in `src/`, while under bash-as-sh it is the exit status being the signal
  (129) rather than the handler's own 143. Two different symptoms, one missing word.
- **`on_signal` still exits 143 for every signal.** Convention would be 130 for INT, and a caller
  such as `make` reports the two differently; that is a separate, cosmetic finding (IN-03) and is
  deliberately not folded in here, because the exit code is not what makes the tree clean.

---

## ADR-095: the coverage gate also pins *which file* coverage.py reads (2026-09-19, extending ADR-089)

**Context**
ADR-089's gate parses `pytest.ini` and `pyproject.toml` and asserts every fact the percentage
rests on. It does not assert that `pyproject.toml` is the file coverage.py *reads*. coverage.py
searches `.coveragerc`, `setup.cfg`, `tox.ini`, `pyproject.toml` in that order and uses the first
one carrying coverage settings, so a three-line `.coveragerc` holding
`[run] omit = */use_cases/*` replaces the whole pinned configuration — source, branch, concurrency,
exclusions — and every assertion in that module stays green about a file nothing opens. The addopts
are the same hole from the other side: `--cov-config=` redirects the search, `--no-cov` disables the
measurement while `--cov-fail-under=75` sits three lines below still looking like a gate, and a
second `--cov=src` adds to the first rather than replacing it, putting `tests/` in the denominator.

**Options**

- **Trust review.** The whole reason this module exists is that a one-line configuration change is
  invisible in a diff and moves the number in the direction nobody audits. A *new file* is if
  anything easier to miss than a changed line.
- **Assert `.coveragerc`, `setup.cfg` and `tox.ini` simply do not exist.** Strongest and slightly
  wrong: coverage.py ignores a `setup.cfg` or `tox.ini` with no coverage section, and either may
  arrive later for an unrelated tool.
- **Refuse the coverage *section*, and the three addopts.**

**Decision**
The third. `test_pyproject_is_the_only_coverage_configuration` fails if `.coveragerc` exists at all
(it has no other purpose), if `setup.cfg` or `tox.ini` carries a `[coverage]` or `[coverage:*]`
section, or if the addopts contain `--no-cov` or `--cov-config`; and
`test_coverage_is_measured_over_the_package` now also requires **exactly one** `--cov=` token.

**Consequences**

- **Driven red three ways**, each reverted by deleting exactly what was planted: a `.coveragerc`
  with an `omit`, a `tox.ini` with `[coverage:run]`, and an addopts block carrying `--cov=src`
  plus `--cov-config=other.rc` (which reddens the `--cov=` count test as well, by design).
- **Out of scope here, and still open:** WR-04's other half. `FORBIDDEN_PRAGMA` is matched as the
  literal `# pragma: no cover`, while coverage honours
  `#\s*(pragma|PRAGMA)[:\s]?\s*(no|NO)\s*(cover|COVER)` — so `#pragma: no cover`,
  `# pragma:no cover`, `# PRAGMA: NO COVER` and `# pragma no cover` are all invisible to it, and
  `# pragma: no branch` is not scanned for at all despite `branch = true` being pinned. That is
  one `re.compile` away and is deliberately left to its own change; note that
  `test_no_exclusion_removes_a_real_statement` (ADR-092) already catches every one of those
  spellings by effect, which is why this is a message-quality gap rather than a hole.

---
