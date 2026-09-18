<!-- GSD:project-start source:PROJECT.md -->
## Project

**Task Manager API — Crehana Backend Technical Challenge**

A REST API for managing task lists and their tasks, built with Python and FastAPI as the
deliverable for Crehana's Backend Technical Challenge. It is aimed at the Crehana evaluators:
it must satisfy every line of the challenge brief literally, and on top of that demonstrate
a disciplined, transparent AI-assisted engineering workflow (human direction, automated
quality gates, verified output) rather than "AI wrote it".

**Core Value:** Every requirement in the challenge PDF is met to the letter and is provable in under five
minutes by an evaluator: `docker compose up`, run the tests, read the docs.

### Constraints

- **Tech stack**: Python, FastAPI, pytest, flake8, black, Docker — mandated by the brief
- **Database**: PostgreSQL — brief requires "a real database"; removes any doubt SQLite might raise
- **Language**: Everything in English (code, docs, commits, planning artifacts) — user decision
- **Files**: `pytest.ini`, `.flake8`, `Dockerfile`, `docker-compose.yml`, `README.md`,
  `DECISION_LOG.md` must exist literally — brief lists them by name
- **Coverage**: >= 75%, enforced automatically — brief requirement
- **Git**: No Claude/AI co-author attribution lines in commits — user preference; AI usage is
  documented transparently in `AI_WORKFLOW.md` instead
- **Delivery**: Public GitHub repo owned by the candidate; link sent to talento@crehana.com
- **Reviewability**: One-command startup (`docker compose up`) and one-command test run
<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->
## Technology Stack

## Executive Decision Summary
| # | Decision | Verdict | Confidence |
|---|----------|---------|------------|
| 1 | Python version in Docker | **3.13** (`python:3.13-slim-trixie`), **not 3.12** | HIGH |
| 2 | Web stack | FastAPI 0.141.x + Pydantic 2.13.x + pydantic-settings 2.15.x | HIGH |
| 3 | ORM style | SQLAlchemy **2.0.x async** (`create_async_engine`) | HIGH |
| 4 | Postgres driver | **`psycopg[binary]` 3.3.x** (one driver, sync + async), **not asyncpg** | MEDIUM-HIGH |
| 5 | Migrations | Alembic 1.20.x with a **sync** `env.py` (works because of #4) | HIGH |
| 6 | JWT | **PyJWT 2.14.x**, **never python-jose** | HIGH |
| 7 | Password hashing | **`pwdlib[argon2]` 0.3.x**, **never passlib** | HIGH |
| 8 | Test DB | **Postgres from docker-compose / GHA service container**, not testcontainers | MEDIUM |
| 9 | Dependency management | **pip + exact-pinned `requirements*.txt`**, uv only as a build-stage accelerator | MEDIUM |
## Recommended Stack
### Core Technologies
| Technology | Version (verified 2026-09-17) | Purpose | Why Recommended |
|------------|------------------------------|---------|-----------------|
| **Python** | `3.13` (image `python:3.13-slim-trixie`) | Runtime | 3.12 entered **security-only** status (no more bugfix releases, per python.org devguide); 3.13 is in active *bugfix* status until ~Oct 2026 and EOL 2029-10. Every native dependency in this stack ships `cp313` manylinux wheels for **both** x86_64 and aarch64 (verified on PyPI: `psycopg-binary`, `greenlet`, `bcrypt`, `cryptography`, `mypy`, `black`, `orjson`). **This overrides the "target 3.12 for wheel stability" note in PROJECT.md** — that rationale no longer holds, and 3.12 is now the less-current choice an evaluator may flag. |
| **FastAPI** | `0.141.1` (2026-07-29) | HTTP framework, OpenAPI, DI | Mandated by the brief. Current release depends on `starlette>=0.46.0` (upper pin removed) and `pydantic>=2.9.0`; it is verified working against Starlette 1.6.0. |
| **Pydantic** | `2.13.5` (2026-08-28) | Request/response schemas, validation | Satisfies the brief's "strong typing with Pydantic". `2.14.0b2` exists — **do not use the beta**. |
| **pydantic-settings** | `2.15.0` (2026-08-07) | 12-factor config from env / `.env` | Keeps `DATABASE_URL`, `JWT_SECRET`, `JWT_EXPIRE_MINUTES` out of code; `BaseSettings` validates them at boot, so a misconfigured container fails fast instead of at first request. |
| **SQLAlchemy** | `2.0.54` (2026-09-15), pin `>=2.0.54,<2.1` | ORM + Core, async engine | 2.0 is the stable line. `2.1.0rc2` is **release-candidate only** — do not ship an RC in a graded deliverable. 2.0's typed `Mapped[...]` / `mapped_column()` declarative style is what "modern SQLAlchemy" means to a reviewer. |
| **psycopg (psycopg 3)** | `3.3.5` (2026-08-31), install `psycopg[binary]` | PostgreSQL driver | See decision #4 below. |
| **Alembic** | `1.20.0` (2026-09-11) | Schema migrations | The only credible migration tool for SQLAlchemy (same maintainers). Requires `SQLAlchemy>=2.0`. Proves you did not rely on `Base.metadata.create_all()`. |
| **PostgreSQL** | `18-alpine` (PG 18 GA 2025-09-25, EOL 2030-11) | Database | "A real database" per the brief. PG 18 has ~1 year in the field; PG 17 is the conservative fallback. Pin the major version in `docker-compose.yml` — never use `postgres:latest`. |
| **Uvicorn** | `0.53.0` (2026-09-14), install `uvicorn[standard]` | ASGI server | `[standard]` adds `uvloop` + `httptools` for real throughput. Single-process uvicorn is correct for this deliverable; gunicorn workers are unnecessary ceremony. |
### Supporting Libraries (runtime)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **PyJWT** | `2.14.0` (2026-09-11) | Encode/decode JWT access tokens | Always, for the bonus JWT use case. `import jwt`; catch `jwt.exceptions.InvalidTokenError`. HS256 with a secret from settings is sufficient here — no need for `pyjwt[crypto]` unless you sign with RS256/ES256. |
| **pwdlib[argon2]** | `0.3.1` (2026-08-12) | Password hashing | Always. `PasswordHash.recommended()` → Argon2id via `argon2-cffi`. Pulls `argon2-cffi>=23.1.0` (`25.1.0` current). |
| **python-multipart** | `0.0.32` (2026-06-04) | Form parsing | **Required** the moment you use `OAuth2PasswordRequestForm` on `POST /auth/login`. FastAPI raises a runtime error without it — an easy way to ship a broken login endpoint. |
| **email-validator** | `2.3.0` (2025-08-26) | Backs Pydantic `EmailStr` | Required for the user registration schema and the fake-invitation use case. Pydantic raises an import error on `EmailStr` without it. |
| **greenlet** | `3.5.6` (2026-09-14) | SQLAlchemy async bridge | Installed automatically by `SQLAlchemy[asyncio]`; list it explicitly only if you fully pin transitives. |
### Testing Stack
| Library | Version | Purpose | Notes |
|---------|---------|---------|-------|
| **pytest** | `9.1.1` (2026-06-19) | Test runner | pytest 9 turns `PytestRemovedIn9Warning` deprecations into **errors**, and requires Python >= 3.10. `pytest-asyncio` requires `pytest<10,>=8.4` — compatible. |
| **pytest-asyncio** | `1.4.0` (2026-05-26) | Async test + fixture support | Use `asyncio_mode = auto` so `async def` tests need no marker, and set `asyncio_default_fixture_loop_scope` explicitly (otherwise you get deprecation noise, and with pytest 9 that noise is an error). |
| **httpx** | `0.28.1` | Async API client for integration tests | `1.0.dev6` is a **pre-release** — pin `>=0.28.1,<1.0`. FastAPI itself pins `httpx<1.0.0,>=0.23.0`. **The `AsyncClient(app=app)` shortcut is gone**; use `AsyncClient(transport=ASGITransport(app=app), base_url="http://test")`. |
| **pytest-cov** | `7.1.0` (2026-03-21) | Coverage + `--cov-fail-under=75` | Requires `coverage[toml]>=7.10.6` (current `7.16.1`). This is what mechanically enforces the brief's 75% gate. |
| **anyio** | `4.15.1` | Transitive (Starlette/httpx) | Already present. See "pytest-asyncio vs anyio" below — you do not need to add it explicitly. |
| **asgi-lifespan** | `2.1.0` (2023) | Run startup/shutdown events under `AsyncClient` | **Only if** you put real work in the lifespan handler. Prefer designing the app so tests don't need it (create the engine at import time from settings). Stale package — avoid if avoidable. |
### Development Tools
| Tool | Version | Purpose | Configuration notes |
|------|---------|---------|---------------------|
| **black** | `26.5.1` (2026-05-18) | Formatter (brief-mandated) | Configure in `[tool.black]` of `pyproject.toml`: `line-length = 88`, `target-version = ["py313"]`. |
| **isort** | `9.0.1` (2026-08-27) | Import sorting (brief-mandated) | `profile = "black"` still exists in isort 9 (verified in `isort/profiles.py`: sets `multi_line_output=3`, `include_trailing_comma`, `line_length=88`). isort 9.0 removed deprecated options only. |
| **flake8** | `7.3.0` (2025-06-20) | Linter (brief-mandated) | Config **must** live in `.flake8` / `setup.cfg` / `tox.ini` — flake8 still does not read `pyproject.toml`. The brief requires a literal `.flake8` file anyway, so this is free. |
| **flake8-bugbear** | `26.9.9` (2026-09-09) | Real-bug checks (B006 mutable defaults, B008 function-call-in-default, B904 `raise ... from`) | Highest-value plugin. Caveat: **B008 fires on FastAPI's `Depends()`** — add `extend-immutable-calls = fastapi.Depends, fastapi.Query, fastapi.Path, fastapi.Body, fastapi.Header` to `.flake8`. |
| **flake8-comprehensions** | `3.17.0` | Comprehension simplifications (C4xx) | Cheap, zero false positives in practice. |
| **pep8-naming** | `0.15.1` | Naming conventions (N8xx) | Cheap. Signals discipline in a graded repo. |
| **mypy** | `2.3.1` (2026-08-15) | Static typing in CI | See "mypy 2.x migration" below — 2.0 changed defaults. |
| **import-linter** | `2.15` (2026-09-04) | **Automated architecture-boundary enforcement** | This is the tool for the PROJECT.md requirement "layer boundaries enforced by an automated test". Config in a `.importlinter` INI file; run via `lint-imports`. |
| **pre-commit** | `4.6.2` (2026-08-10) | Local quality gate | Mirror repos verified live: `psf/black-pre-commit-mirror@26.5.1`, `PyCQA/isort@9.0.1`, `PyCQA/flake8@7.3.0`, `pre-commit/mirrors-mypy@v2.3.1`, `pre-commit/pre-commit-hooks@v6.0.0`. |
### GitHub Actions (verified tags, 2026-09-17)
| Action | Current tag |
|--------|-------------|
| `actions/checkout` | `v7.0.1` (2026-07-20) |
| `actions/setup-python` | `v7.0.0` (2026-07-20) |
| `actions/cache` | `v6.1.0` (2026-06-26) |
## Decision Detail
### 1. Python 3.13, not 3.12
| Version | Status | EOL |
|---------|--------|-----|
| 3.12 | **security** (bugfixes stopped) | 2028-10 |
| 3.13 | bugfix | 2029-10 |
| 3.14 | bugfix | 2030-10 |
### 2. SQLAlchemy 2.0 **async**, not sync
### 3. psycopg 3, not asyncpg — the single-driver argument
| | psycopg 3 | asyncpg |
|---|---|---|
| App runtime | `create_async_engine("postgresql+psycopg://…")` | `create_async_engine("postgresql+asyncpg://…")` |
| Alembic `env.py` | **stock sync template, same URL** | needs an async `env.py` (`asyncio.run` + `run_sync`) **or** a second driver (`psycopg2-binary`) |
| Dependencies | 1 | 2, or ~40 extra lines of `env.py` |
| `DATABASE_URL` in `.env` | one value everywhere | one value for app, another (or string surgery) for Alembic |
| `?sslmode=…` in the URL | handled (libpq semantics) | rejected by the dialect; needs `connect_args` translation |
| Raw speed | slightly slower | fastest |
### 4. JWT: PyJWT — python-jose is disqualified
- CVE-2024-33663 — algorithm confusion, signing a JWT with a public key was accepted.
- CVE-2024-33664 — "JWT bomb" DoS via a highly-compressed JWE payload.
- Both fixed in 3.4.0, but the project is effectively dormant: last release `3.5.0` on **2025-05-28**, ~16 months of silence at time of writing.
- It drags in `ecdsa` (which has its own long-standing side-channel advisories), `rsa` and `pyasn1`.
### 5. Password hashing: pwdlib[argon2] — passlib is disqualified
- Last release **1.7.4, 2020-10-08**. Six years, no `requires_python`, no modern classifiers.
- It imports the stdlib `crypt` module, **removed in Python 3.13** (PEP 594) — the exact interpreter we are targeting. passlib will not import.
- `bcrypt` 5.0.0 removed `bcrypt.__about__`, which passlib's backend detection reads → `AttributeError: module 'bcrypt' has no attribute '__about__'` (pyca/bcrypt issue #1079). This has been breaking apps since bcrypt 4.1.1.
### 6. pytest-asyncio, not anyio (with one caveat)
- `auto` mode means zero markers on ~100 async tests.
- You need a **session-scoped async engine fixture** for integration tests. pytest-asyncio exposes `asyncio_default_fixture_loop_scope = session` as one config line. With anyio, the `anyio_backend` fixture is function-scoped by default and you must redefine it at session scope in `conftest.py` — more code, less obvious.
- anyio arrives transitively regardless (Starlette + httpx), so nothing is saved by "using what's already there".
### 7. Test database: compose/CI service container, not testcontainers
- The evaluator must have a working Docker socket **while running pytest on the host**. `docker compose up` is already required by the brief; reusing it is one less thing that can fail in five minutes.
- Cold-start per test session adds seconds and a `docker` + `wrapt` + `urllib3` dependency tree to dev requirements.
- GitHub Actions `services:` already gives you a first-class Postgres with a health check.
### 8. Architecture enforcement: import-linter
### 9. Dependency management: pip + exact pins
- `pip install -r requirements.txt` works on every evaluator machine with zero prerequisites. A `uv.lock` requires them to install and trust another tool, and it is not human-readable in a diff.
- Exact `==` pins make the build reproducible six months from now, which is the whole point of a submitted artifact.
- `pyproject.toml` still holds tool config (black/isort/mypy/coverage) — you are not avoiding it, just not using it for resolution.
## Installation
# Host (macOS, Python 3.14 present — venv is fine for editor/tooling; Docker is the source of truth)
## Configuration Files (exact, compatible)
### `.flake8` (brief-mandated literal file)
### `pytest.ini` (brief-mandated literal file)
### `pyproject.toml` (tool config only)
### `.pre-commit-config.yaml` (revs verified live via GitHub tags API)
## mypy 2.x Migration Notes
| Change | Impact here |
|--------|-------------|
| `--local-partial-types` on by default | Module-level `x = None` later assigned a real type now errors. Annotate explicitly: `x: Session | None = None`. |
| `--strict-bytes` on by default (PEP 688) | `bytearray`/`memoryview` no longer assignable to `bytes`. Affects JWT/hash helpers if you were sloppy — annotate `bytes` precisely. |
| `--allow-redefinition` now means the old `--allow-redefinition-new` | Only if you were using the flag. Don't. |
| Dropped **running on** Python 3.9 | Irrelevant (we're on 3.13). |
| Bundled legacy stub special-casing removed | `--ignore-missing-imports` now applies uniformly. |
## Alternatives Considered
| Recommended | Alternative | When the alternative is better |
|-------------|-------------|--------------------------------|
| Python 3.13 | Python 3.14 | If you want maximum "current" signal and accept that a couple of lint plugins lack 3.14 classifiers. Wheels all exist. |
| psycopg 3 | asyncpg 0.31.0 | Raw driver throughput is an explicit criterion. Costs: async Alembic `env.py` or a second driver, and `connect_args` juggling for SSL params. |
| SQLAlchemy 2.0 async | SQLAlchemy 2.0 sync + `def` endpoints | You want the simplest possible test fixtures and are willing to explain the threadpool tradeoff. Genuinely defensible for a 4-6h scope. |
| SQLAlchemy 2.0.54 | SQLAlchemy 2.1.0rc2 | Never for a graded deliverable. Shipping an RC is an unforced error. |
| SQLAlchemy | SQLModel | Fewer models to write, but it fuses persistence and validation into one class — which directly contradicts the brief's domain/infrastructure separation. Actively harmful here. |
| pwdlib[argon2] | argon2-cffi 25.1.0 directly | You want a Production/Stable dependency instead of a Beta wrapper, and are happy writing `needs_rehash` logic yourself. |
| pytest-asyncio | anyio pytest plugin | You want to mirror the official FastAPI docs exactly. Then redefine `anyio_backend` at session scope in `conftest.py`. |
| compose Postgres | testcontainers 4.15.0 | You want identical throwaway DBs on host and CI and accept the Docker-socket prerequisite for `pytest`. |
| pip + requirements | uv + `pyproject.toml` + `uv.lock` | The evaluator is known to use uv, or build speed matters. Not the case here. |
| flake8 (+ plugins) | ruff 0.16.8 | Ruff is genuinely the modern standard and 10-100× faster — but **the brief mandates flake8 as the linter**. Do not substitute. Mentioning ruff in `DECISION_LOG.md` as "what I'd use absent the constraint" is a good move. |
| uvicorn single process | gunicorn 26.2.0 + uvicorn workers | Real production deployment. Out of scope per PROJECT.md. |
## What NOT to Use
| Avoid | Why (verified) | Use instead |
|-------|----------------|-------------|
| **python-jose** | CVE-2024-33663 (algorithm confusion / public-key signing accepted), CVE-2024-33664 (JWT-bomb DoS). Last release 2025-05-28, effectively dormant. Drags in `ecdsa`. Removed from the official FastAPI docs. | **PyJWT 2.14.0** |
| **passlib** | Last release 2020-10-08. Imports stdlib `crypt`, **removed in Python 3.13**. Breaks on `bcrypt>=4.1.1` (`AttributeError: module 'bcrypt' has no attribute '__about__'`). Removed from the official FastAPI docs. | **pwdlib[argon2] 0.3.1** |
| `AsyncClient(app=app)` | Removed in httpx 0.28. | `AsyncClient(transport=ASGITransport(app=app), base_url="http://test")` |
| `ignore = ...` in `.flake8` | Overwrites pycodestyle's `DEFAULT_IGNORE`, silently re-enabling E121/E123/E126/E226/E704/W503/W504 — all of which Black's output violates. | `extend-ignore = E203,E701` |
| `[tool.pytest.ini_options]` in `pyproject.toml` | Silently ignored whenever `pytest.ini` exists — and the brief mandates `pytest.ini`. | All pytest config in `pytest.ini` |
| `sqlalchemy-stubs` / `sqlalchemy2-stubs` | Obsolete. SQLAlchemy 2.0 ships inline types; the stubs actively conflict with them. | `Mapped[...]` + `mapped_column()` |
| **SQLModel** | Merges the ORM entity and the API schema into one class — collapses exactly the domain/infrastructure boundary the brief asks you to demonstrate. | SQLAlchemy models + separate Pydantic schemas |
| `flake8-docstrings` | Wraps `pydocstyle`, which is unmaintained/archived; the plugin itself last released 2023-01. | `pep8-naming` for naming; skip docstring linting |
| `flake8-annotations` | Fully redundant with `mypy --strict`, and produces duplicate noise. | mypy 2.3.1 with `strict = true` |
| `Base.metadata.create_all()` as the production schema path | Reads as "no migration strategy". Fine as a *test-only* shortcut. | Alembic `upgrade head` on startup/entrypoint |
| `postgres:latest`, `python:3.13` (non-slim), `:alpine` for Python | `latest` is unreproducible; non-slim is ~4× larger; Python-on-Alpine uses musl → no manylinux wheels → source builds for `psycopg`/`greenlet`/`argon2-cffi`. | `postgres:18-alpine` (Postgres on Alpine is fine), `python:3.13-slim-trixie` |
| `fastapi[standard]` in the runtime image | Pulls `fastapi-cli`, `fastapi-cloud-cli`, `jinja2`, `httpx`, `pydantic-extra-types` into production. | bare `fastapi` + explicit deps |
| `pydantic` 2.14.0b2, `httpx` 1.0.dev6, `SQLAlchemy` 2.1.0rc2 | All pre-releases as of 2026-09-17. | The stable pins listed above |
## Version Compatibility Matrix
| Package | Constraint (verified from package metadata) | Note |
|---------|---------------------------------------------|------|
| `fastapi 0.141.1` | `starlette>=0.46.0`, `pydantic>=2.9.0`, `typing-extensions>=4.8.0` | Starlette upper pin **removed**; verified compatible with Starlette 1.6.0. |
| `pydantic 2.13.5` | `pydantic-core==2.46.5` (exact) | Never pin `pydantic-core` yourself. |
| `pydantic-settings 2.15.0` | `pydantic>=2.7.0`, `python-dotenv>=0.21.0` | OK with 2.13.5. |
| `alembic 1.20.0` | `SQLAlchemy>=2.0`, `typing-extensions>=4.12` | Python `>=3.10`. |
| `SQLAlchemy 2.0.54` | `greenlet>=1` on x86_64/aarch64; `psycopg>=3.0.7` for the `postgresql+psycopg` dialect | Install as `SQLAlchemy[asyncio]` to make the greenlet dependency explicit. |
| `pytest-asyncio 1.4.0` | `pytest>=8.4,<10` | Compatible with pytest 9.1.1. |
| `pytest-cov 7.1.0` | `coverage[toml]>=7.10.6`, `pytest>=7`, `pluggy>=1.2` | Compatible. |
| `pwdlib 0.3.1` | `argon2-cffi>=23.1.0` (extra `argon2`); `bcrypt>=4.1.2` (extra `bcrypt`) | Top-pins removed in 0.3.1 — no cap conflicts. |
| `flake8 7.3.0` | `pycodestyle>=2.14,<2.15`, `pyflakes>=3.4,<3.5`, `mccabe>=0.7,<0.8` | Plugins must be flake8 7-compatible; the three recommended ones are. |
| `import-linter 2.15` | `grimp>=3.17`, `rich>=14.2.0` | Do **not** install the `[ui]` extra — it pulls fastapi+uvicorn into dev deps. |
| `mypy 2.3.1` | `librt>=0.13.0`, `ast-serialize>=0.6.0`, `pathspec>=1.0.0` | New transitive deps in mypy 2.x; all ship wheels. |
| `black 26.5.1` | `pytokens~=0.4.0`, `click>=8.0.0`, `pathspec>=1.0.0` | — |
| `psycopg[binary] 3.3.5` | Python `>=3.10`; manylinux wheels for cp310–cp314, x86_64 + aarch64 | No `libpq-dev` needed. |
## Stack Patterns by Variant
- `create_async_engine(settings.database_url, pool_pre_ping=True)` at module scope in `app/infrastructure/db/engine.py`.
- `async_sessionmaker(engine, expire_on_commit=False)` — `expire_on_commit=False` is mandatory; the default triggers a lazy refresh after `commit()` that raises `MissingGreenlet` in async context.
- Tests: session-scoped engine + function-scoped connection-bound transaction that always rolls back.
- Alembic stays fully synchronous thanks to psycopg 3.
- Declare route handlers as `def` (not `async def`) so Starlette runs them in the threadpool.
- Drop `pytest-asyncio`; use `fastapi.testclient.TestClient` instead of `httpx.AsyncClient`.
- Keep `psycopg[binary]` — same URL, `create_engine("postgresql+psycopg://…")`.
- Document the tradeoff explicitly in `DECISION_LOG.md`, or a reviewer will read it as ignorance rather than a choice.
- Coverage is dominated by the application layer (use cases), which is pure logic and trivially unit-testable with in-memory fake repositories implementing the same `Protocol` ports. Ten fast unit tests there move the number more than twenty integration tests. This is a direct payoff of the layered architecture the brief mandates — say so in the README.
## Sources
- **PyPI JSON API** (`https://pypi.org/pypi/<pkg>/json`), queried 2026-09-17 — every version, release date, `requires_python`, `requires_dist` and wheel platform tag in this document. **HIGH**
- **GitHub Releases/Tags API**, queried 2026-09-17 — `actions/checkout` v7.0.1, `actions/setup-python` v7.0.0, `actions/cache` v6.1.0, `psf/black-pre-commit-mirror` 26.5.1, `pre-commit/mirrors-mypy` v2.3.1, `PyCQA/flake8` 7.3.0, `PyCQA/isort` 9.0.1, `pre-commit/pre-commit-hooks` v6.0.0, `frankie567/pwdlib` v0.3.1 changelog. **HIGH**
- https://devguide.python.org/versions/ — Python 3.12 = security-only, 3.13/3.14 = bugfix, EOL dates. **HIGH**
- https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/ — official recommendation of `pyjwt` and `pwdlib[argon2]`; explicit removal of passlib/python-jose. **HIGH**
- https://fastapi.tiangolo.com/release-notes/ — 0.141.1 latest; Starlette bumped to 1.6.0. **HIGH**
- https://fastapi.tiangolo.com/advanced/async-tests/ — `ASGITransport` pattern; lifespan caveat. **HIGH**
- https://docs.sqlalchemy.org/en/20/changelog/whatsnew_20.html + `/dialects/postgresql.html` (via Context7 `/websites/sqlalchemy_en_20`) — psycopg 3 as the only dual sync/async DBAPI with a shared URL; asyncpg prepared-statement cache behaviour. **HIGH**
- https://black.readthedocs.io/en/stable/guides/using_black_with_other_tools.html + raw `docs/guides/using_black_with_other_tools.md` — exact `max-line-length = 88` / `extend-ignore = E203,E701` and the Bugbear/B950 variant. **HIGH**
- `PyCQA/pycodestyle` raw source, `DEFAULT_IGNORE = 'E121,E123,E126,E226,E24,E704,W503,W504'` — basis for the `extend-ignore` vs `ignore` warning. **HIGH**
- `PyCQA/isort` raw `isort/profiles.py` — the `black` profile still exists in isort 9. **HIGH**
- https://pytest-asyncio.readthedocs.io (via Context7) — `asyncio_mode = auto`, `asyncio_default_fixture_loop_scope`. **HIGH**
- https://docs.pytest.org/en/stable/changelog.html — pytest 9 breaking changes (removal warnings are errors, Python >= 3.10). **HIGH**
- https://mypy.readthedocs.io/en/stable/changelog.html — mypy 2.0 default changes (local partial types, strict bytes). **HIGH**
- https://import-linter.readthedocs.io/en/stable/ — `.importlinter` INI syntax, layers/forbidden contract types, layer ordering semantics. **HIGH**
- https://github.com/pyca/bcrypt/issues/1079 and https://github.com/pyca/bcrypt/issues/684 — passlib + bcrypt `__about__` breakage. **MEDIUM** (issue threads, corroborated by the passlib 2020 release date and the Python 3.13 `crypt` removal)
- https://github.com/frankie567/pwdlib README — passlib "won't work anymore starting Python 3.13". **MEDIUM-HIGH**
- CVE-2024-33663 / CVE-2024-33664 advisories (Ubuntu, Snyk, OSV) — python-jose vulnerabilities, fixed in 3.4.0. **MEDIUM-HIGH**
- https://endoflife.date/postgresql — PostgreSQL 18 current, EOL 2030-11. **MEDIUM**
- Docker Hub `_/python` tags — `3.13-slim` currently resolves to the Trixie base. **MEDIUM**
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->

## Project Rules

> Hand-maintained section. It sits outside every `<!-- GSD:*-start -->` / `<!-- GSD:*-end -->`
> block on purpose, so regenerating the blocks above cannot delete it. Every rule below is
> enforced by a gate that fails a build — none of it is advisory.

### Layers

- Import direction, high to low:
  `taskmanager.main` > `taskmanager.presentation` > `taskmanager.infrastructure` >
  `taskmanager.application` > `taskmanager.domain`. Imports only ever point downward;
  a lower layer never imports a higher one.
- `taskmanager.domain` imports **no third-party library at all** — stdlib only
  (`dataclasses`, `enum`, `datetime`, `typing.Protocol`). Not even Pydantic: a Pydantic
  `ValidationError` cannot carry the domain error contract, so validation lives at the
  boundaries.
- `taskmanager.application` imports **no web framework and no ORM** (no `fastapi`,
  `starlette`, `sqlalchemy`, `alembic`). Pydantic *is* permitted there and the contract is
  deliberately not tightened — but application command and result DTOs are frozen dataclasses
  (`@dataclass(frozen=True, slots=True)`) per ADR-020, so nothing in the layer imports it
  today.
- This is enforced automatically by the contracts in `.importlinter`, executed by
  `tests/architecture/test_layer_boundaries.py`, by `make arch` and by CI. A violating
  import fails a test, not a review.

### Error handling

- `fastapi.HTTPException` may **never** be raised outside the `presentation` layer.
- Business failures raise a `DomainError` subclass (Phase 2) and are translated once, at a
  single exception-handling point, into an RFC 9457 `application/problem+json` response.
  No handler builds an error body by hand.

### Quality gates

- `make lint`, `make typecheck`, `make arch` and `make test` must all be green before any
  commit. pre-commit enforces the same set locally on every `git commit`.
- Coverage is gated at **75%** over `src/taskmanager` (`--cov-fail-under=75` in
  `pytest.ini`). The threshold is never lowered, and it is never reached with
  `# pragma: no cover` or a coverage `omit` entry. If the number is short, write the test.
- Where each gate runs: pre-commit is the **developer-host** gate and depends on `.venv`
  existing (its whole-program hook entries are `.venv/bin/`-qualified). CI and the Docker
  `test` stage have no `.venv`, so they run the same tools **directly** as named steps.
  A new gate must therefore be added in **both** `.pre-commit-config.yaml` and
  `.github/workflows/ci.yml` — neither derives from the other.

### Configuration

- No secret ever gets a default value in code.
- Every setting is read through `taskmanager.infrastructure.config.settings`, documented in
  `.env.example`, and `.env` is never committed.

### Language and attribution

- Everything is written in English: code, comments, docs, commit messages and planning
  artifacts.
- Git commit messages carry **no Claude/AI co-author or attribution trailer of any kind**.
  AI involvement is documented transparently in `AI_WORKFLOW.md` instead — that is this
  project's chosen form of honesty about it, not a way of hiding it.
