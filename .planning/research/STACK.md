# Stack Research

**Domain:** Layered (domain / application / infrastructure) FastAPI + PostgreSQL REST API with JWT auth — technical-challenge deliverable
**Researched:** 2026-09-17
**Confidence:** HIGH (all versions read live from the PyPI JSON API, GitHub Releases API and official docs on 2026-09-17; no version stated from training data)

---

## Executive Decision Summary

Nine decisions drive everything else. Each is expanded below.

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

---

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

> Installing `fastapi[standard]` would drag in `fastapi-cli`, `fastapi-cloud-cli`, `jinja2`, `httpx` and `pydantic-extra-types` into the **production** image. Install the bare `fastapi` package plus only what you need. Smaller image, fewer CVE surfaces, and it reads as deliberate.

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

Use `services: postgres: image: postgres:18-alpine` with a `pg_isready` health check rather than spinning up compose inside CI.

---

## Decision Detail

### 1. Python 3.13, not 3.12

Verified from python.org devguide (2026-09-17):

| Version | Status | EOL |
|---------|--------|-----|
| 3.12 | **security** (bugfixes stopped) | 2028-10 |
| 3.13 | bugfix | 2029-10 |
| 3.14 | bugfix | 2030-10 |

The only argument PROJECT.md gives for 3.12 is "wheel stability". That is now false: PyPI shows `cp313` **and** `cp314` manylinux wheels (x86_64 + aarch64) for `psycopg-binary` 3.3.5, `asyncpg` 0.31.0, `greenlet` 3.5.6, `cryptography` 50.0.1, `bcrypt` 5.0.0, `mypy` 2.3.1, `black` 26.5.1. Nothing in this stack compiles from source on 3.13.

Why not 3.14: it is only ~11 months old; a few second-tier plugins still lack `3.14` classifiers (e.g. `flake8-simplify`, `factory-boy`). 3.13 is the maximum-compatibility, non-stale choice. Use `python:3.13-slim-trixie` (Debian 13 — `3.13-slim` currently resolves to trixie).

### 2. SQLAlchemy 2.0 **async**, not sync

FastAPI is ASGI. A sync `Session` inside `async def` endpoints blocks the event loop; the only correct sync alternative is declaring every endpoint `def` so Starlette runs it in a threadpool — which reads as a workaround in a review. Use `create_async_engine` + `async_sessionmaker(engine, expire_on_commit=False)` + an `async def get_session()` FastAPI dependency. `expire_on_commit=False` matters: without it, accessing an attribute after `commit()` triggers a lazy refresh that raises `MissingGreenlet` in async code.

### 3. psycopg 3, not asyncpg — the single-driver argument

Both work. The decision hinges on **Alembic**, and it is the single highest-leverage simplification in this stack.

SQLAlchemy's own "What's New in 2.0" states psycopg 3 is *"the first DBAPI supported by SQLAlchemy that provides both a PEP-249 synchronous API and an asyncio driver. The same psycopg database URL can be used with both `create_engine()` and `create_async_engine()`, automatically selecting the corresponding sync or asyncio dialect version."*

Consequences for this project:

| | psycopg 3 | asyncpg |
|---|---|---|
| App runtime | `create_async_engine("postgresql+psycopg://…")` | `create_async_engine("postgresql+asyncpg://…")` |
| Alembic `env.py` | **stock sync template, same URL** | needs an async `env.py` (`asyncio.run` + `run_sync`) **or** a second driver (`psycopg2-binary`) |
| Dependencies | 1 | 2, or ~40 extra lines of `env.py` |
| `DATABASE_URL` in `.env` | one value everywhere | one value for app, another (or string surgery) for Alembic |
| `?sslmode=…` in the URL | handled (libpq semantics) | rejected by the dialect; needs `connect_args` translation |
| Raw speed | slightly slower | fastest |

For a CRUD task manager, the throughput difference is noise; the configuration surface saved is not. **Use `psycopg[binary]==3.3.5`.**

> Pick asyncpg instead only if raw driver benchmarks are an explicit evaluation criterion — then also add `psycopg2-binary` for Alembic (or convert `env.py` to async) and document the reason in `DECISION_LOG.md`.

Use `psycopg[binary]` (prebuilt libpq) rather than `psycopg[c]`/plain `psycopg` — no `libpq-dev`/`gcc` in the Docker builder stage.

### 4. JWT: PyJWT — python-jose is disqualified

The **official FastAPI security tutorial now installs `pyjwt` and imports `jwt` / `jwt.exceptions.InvalidTokenError`.** It no longer mentions `python-jose`. Reasons python-jose is out:

- CVE-2024-33663 — algorithm confusion, signing a JWT with a public key was accepted.
- CVE-2024-33664 — "JWT bomb" DoS via a highly-compressed JWE payload.
- Both fixed in 3.4.0, but the project is effectively dormant: last release `3.5.0` on **2025-05-28**, ~16 months of silence at time of writing.
- It drags in `ecdsa` (which has its own long-standing side-channel advisories), `rsa` and `pyasn1`.

PyJWT: `2.14.0`, released **2026-09-11**, maintained, ~zero dependencies on Python 3.11+.

### 5. Password hashing: pwdlib[argon2] — passlib is disqualified

The official FastAPI tutorial installs `pwdlib[argon2]` and imports `from pwdlib import PasswordHash`. passlib is dead for hard, verifiable reasons:

- Last release **1.7.4, 2020-10-08**. Six years, no `requires_python`, no modern classifiers.
- It imports the stdlib `crypt` module, **removed in Python 3.13** (PEP 594) — the exact interpreter we are targeting. passlib will not import.
- `bcrypt` 5.0.0 removed `bcrypt.__about__`, which passlib's backend detection reads → `AttributeError: module 'bcrypt' has no attribute '__about__'` (pyca/bcrypt issue #1079). This has been breaking apps since bcrypt 4.1.1.

`pwdlib` is Beta (0.3.1) and is a thin wrapper — that is deliberate: the cryptography lives in the battle-tested `argon2-cffi` (25.1.0) it wraps. If the Beta version number is a concern for the deliverable, depend on **`argon2-cffi` directly** (`PasswordHasher().hash()` / `.verify()`), which is Production/Stable — but then you write the rehash-on-login logic yourself. **Recommendation: `pwdlib[argon2]`**, because matching the official FastAPI docs is the easiest thing to defend in `DECISION_LOG.md`.

### 6. pytest-asyncio, not anyio (with one caveat)

FastAPI's docs use `@pytest.mark.anyio`. Choose **pytest-asyncio 1.4.0 with `asyncio_mode = auto`** anyway:

- `auto` mode means zero markers on ~100 async tests.
- You need a **session-scoped async engine fixture** for integration tests. pytest-asyncio exposes `asyncio_default_fixture_loop_scope = session` as one config line. With anyio, the `anyio_backend` fixture is function-scoped by default and you must redefine it at session scope in `conftest.py` — more code, less obvious.
- anyio arrives transitively regardless (Starlette + httpx), so nothing is saved by "using what's already there".

Required `pytest.ini` (which the brief requires as a literal file):

```ini
[pytest]
asyncio_mode = auto
asyncio_default_fixture_loop_scope = session
```

Omitting `asyncio_default_fixture_loop_scope` emits a deprecation warning — and pytest 9 escalates `PytestRemovedIn9Warning` to an error, so this is not cosmetic.

### 7. Test database: compose/CI service container, not testcontainers

`testcontainers` 4.15.0 is excellent, but for this deliverable it costs more than it returns:

- The evaluator must have a working Docker socket **while running pytest on the host**. `docker compose up` is already required by the brief; reusing it is one less thing that can fail in five minutes.
- Cold-start per test session adds seconds and a `docker` + `wrapt` + `urllib3` dependency tree to dev requirements.
- GitHub Actions `services:` already gives you a first-class Postgres with a health check.

Pattern: `TEST_DATABASE_URL` env var, a **session-scoped** fixture that runs `Base.metadata.create_all` (or `alembic upgrade head`) once, and a **function-scoped** fixture that opens a connection, `begin()`s a transaction, binds the `AsyncSession` to it, yields, then **rolls back**. Per-test isolation with no truncation and no re-migration.

> Choose testcontainers instead if you want the exact same throwaway Postgres on host and CI with zero env-var coordination, and you accept the Docker-socket prerequisite.

### 8. Architecture enforcement: import-linter

PROJECT.md asks for boundaries enforced by an automated check. `import-linter` 2.15 does this declaratively. Config file (`.importlinter`, INI):

```ini
[importlinter]
root_package = app

[importlinter:contract:layers]
name = Layered architecture
type = layers
layers =
    app.api
    app.infrastructure
    app.application
    app.domain

[importlinter:contract:domain-is-framework-free]
name = Domain must not import frameworks or the ORM
type = forbidden
source_modules =
    app.domain
    app.application
forbidden_modules =
    fastapi
    starlette
    sqlalchemy
```

In a `layers` contract the **first listed layer is the highest**; higher layers may import lower ones, never the reverse. Run `lint-imports` in CI, and additionally wrap it in a pytest test (`subprocess.run(["lint-imports"]).returncode == 0`) so it also shows up in the test report — PROJECT.md explicitly frames this as "an automated test".

Note the second contract forbids `sqlalchemy` in `app.application` too — that is what forces repository **ports as `typing.Protocol`** in the domain with SQLAlchemy adapters in infrastructure. Pydantic is deliberately *not* forbidden, since the brief mandates "strong typing with Pydantic"; keep Pydantic models in `api`/`application` DTOs and plain dataclasses in `domain` if you want an even cleaner story.

### 9. Dependency management: pip + exact pins

The host has no uv or poetry, and the evaluator's machine is unknown.

**Use three files, exact `==` pins:**

```
requirements.txt        # runtime only — what goes in the Docker runtime stage
requirements-dev.txt    # -r requirements.txt + test/lint/type tooling
```

Why not uv/Poetry as the source of truth:
- `pip install -r requirements.txt` works on every evaluator machine with zero prerequisites. A `uv.lock` requires them to install and trust another tool, and it is not human-readable in a diff.
- Exact `==` pins make the build reproducible six months from now, which is the whole point of a submitted artifact.
- `pyproject.toml` still holds tool config (black/isort/mypy/coverage) — you are not avoiding it, just not using it for resolution.

**Optional accelerator (best of both):** keep `requirements*.txt` as the source of truth and use uv *only inside the Docker builder stage*:

```dockerfile
COPY --from=ghcr.io/astral-sh/uv:0.12.15 /uv /bin/uv
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system --no-cache -r requirements.txt
```

Fast builds, nothing extra required on the host, and uv never reaches the runtime stage. If that feels like an unexplained dependency for the reviewer, plain `pip install --no-cache-dir -r requirements.txt` into a venv copied between stages is completely fine — the brief does not grade build speed.

---

## Installation

```bash
# Host (macOS, Python 3.14 present — venv is fine for editor/tooling; Docker is the source of truth)
python3 -m venv .venv && source .venv/bin/activate
python -m pip install -U pip
pip install -r requirements-dev.txt
pre-commit install
```

**`requirements.txt`** (runtime — exact pins verified on PyPI 2026-09-17):

```
fastapi==0.141.1
uvicorn[standard]==0.53.0
pydantic==2.13.5
pydantic-settings==2.15.0
SQLAlchemy[asyncio]==2.0.54
psycopg[binary]==3.3.5
alembic==1.20.0
PyJWT==2.14.0
pwdlib[argon2]==0.3.1
python-multipart==0.0.32
email-validator==2.3.0
```

**`requirements-dev.txt`**:

```
-r requirements.txt
pytest==9.1.1
pytest-asyncio==1.4.0
pytest-cov==7.1.0
httpx==0.28.1
black==26.5.1
isort==9.0.1
flake8==7.3.0
flake8-bugbear==26.9.9
flake8-comprehensions==3.17.0
pep8-naming==0.15.1
mypy==2.3.1
import-linter==2.15
pre-commit==4.6.2
```

Optional, only if fixtures get repetitive: `faker==40.39.0` or `polyfactory==3.3.0`. Neither is needed for a task manager with ~6 entities; hand-written factory functions are clearer to a reviewer.

---

## Configuration Files (exact, compatible)

### `.flake8` (brief-mandated literal file)

```ini
[flake8]
max-line-length = 88
extend-ignore = E203,E701
extend-select = B950
extend-immutable-calls = fastapi.Depends,fastapi.Query,fastapi.Path,fastapi.Body,fastapi.Header
exclude = .git,__pycache__,.venv,build,dist,migrations/versions
per-file-ignores =
    tests/*:S101
max-complexity = 10
```

**Why `extend-ignore` and not `ignore` — verified in pycodestyle source:**

```python
DEFAULT_IGNORE = 'E121,E123,E126,E226,E24,E704,W503,W504'
```

`W503` (line break before binary operator) and `E704` are **already in pycodestyle's defaults**. Using `extend-ignore` preserves them. Writing `ignore = E203,W503` would *replace* the default set and silently re-enable `E121`, `E123`, `E126`, `E226`, `E704`, `W504` — all of which Black's output triggers. This is the single most common broken Black+flake8 config on the internet.

Black's official compatibility guide currently prescribes exactly `max-line-length = 88` + `extend-ignore = E203,E701` (E203 = whitespace before `:` in slices; E701 = multiple statements on one line, which Black emits for `class X: ...` stubs). W503 needs no explicit mention.

`extend-select = B950` is bugbear's 10%-tolerance line-length check, which matches Black's own line-length philosophy. If you add it, Black's guide pairs it with `max-line-length = 80` + ignoring `E501`; **simpler and equally defensible: drop `extend-select = B950` and keep `max-line-length = 88`.** Pick one, do not mix.

### `pytest.ini` (brief-mandated literal file)

```ini
[pytest]
testpaths = tests
asyncio_mode = auto
asyncio_default_fixture_loop_scope = session
addopts =
    -ra
    --strict-markers
    --cov=app
    --cov-report=term-missing
    --cov-report=xml
    --cov-fail-under=75
markers =
    unit: pure domain/application tests, no I/O
    integration: tests that hit PostgreSQL
filterwarnings =
    error
```

**Gotcha:** when `pytest.ini` exists it wins outright — pytest **ignores** `[tool.pytest.ini_options]` in `pyproject.toml`. Since the brief mandates `pytest.ini`, put *all* pytest config there and none in `pyproject.toml`, or you will chase phantom settings.

`filterwarnings = error` is aggressive but is exactly the kind of rigour this deliverable is being graded on; relax to per-warning `ignore::` entries if a transitive dependency misbehaves.

### `pyproject.toml` (tool config only)

```toml
[tool.black]
line-length = 88
target-version = ["py313"]

[tool.isort]
profile = "black"
line_length = 88
known_first_party = ["app"]

[tool.mypy]
python_version = "3.13"
strict = true
plugins = ["pydantic.mypy"]
warn_unreachable = true

[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false

[tool.coverage.run]
source = ["app"]
omit = ["*/migrations/*", "*/__main__.py"]

[tool.coverage.report]
exclude_also = ["if TYPE_CHECKING:", "raise NotImplementedError", "@abstractmethod", "\\.\\.\\."]
```

### `.pre-commit-config.yaml` (revs verified live via GitHub tags API)

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v6.0.0
    hooks: [{id: trailing-whitespace}, {id: end-of-file-fixer}, {id: check-yaml}, {id: check-added-large-files}, {id: check-merge-conflict}]
  - repo: https://github.com/PyCQA/isort
    rev: 9.0.1
    hooks: [{id: isort}]
  - repo: https://github.com/psf/black-pre-commit-mirror
    rev: 26.5.1
    hooks: [{id: black}]
  - repo: https://github.com/PyCQA/flake8
    rev: 7.3.0
    hooks:
      - id: flake8
        additional_dependencies: [flake8-bugbear==26.9.9, flake8-comprehensions==3.17.0, pep8-naming==0.15.1]
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v2.3.1
    hooks:
      - id: mypy
        additional_dependencies: [pydantic==2.13.5, sqlalchemy[mypy]==2.0.54, types-python-dateutil]
```

Order matters: **isort before black**. Both are formatters that rewrite files; running black last guarantees the final byte layout is black's. flake8 must run after both, or it lints pre-format code.

`psf/black-pre-commit-mirror` (not `psf/black`) is the correct repo — the mirror is lightweight and exists precisely for pre-commit.

---

## mypy 2.x Migration Notes

mypy 2.0 changed defaults. Relevant to this project (verified from the official changelog):

| Change | Impact here |
|--------|-------------|
| `--local-partial-types` on by default | Module-level `x = None` later assigned a real type now errors. Annotate explicitly: `x: Session | None = None`. |
| `--strict-bytes` on by default (PEP 688) | `bytearray`/`memoryview` no longer assignable to `bytes`. Affects JWT/hash helpers if you were sloppy — annotate `bytes` precisely. |
| `--allow-redefinition` now means the old `--allow-redefinition-new` | Only if you were using the flag. Don't. |
| Dropped **running on** Python 3.9 | Irrelevant (we're on 3.13). |
| Bundled legacy stub special-casing removed | `--ignore-missing-imports` now applies uniformly. |

With `strict = true` plus the `pydantic.mypy` plugin, expect real friction in the SQLAlchemy layer. Use SQLAlchemy 2.0's `Mapped[int]` / `mapped_column()` declarative style — it is natively typed and needs no plugin (the legacy `sqlalchemy-stubs`/`sqlalchemy2-stubs` packages are obsolete and must not be installed).

---

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

---

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

---

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

---

## Stack Patterns by Variant

**If you keep the async decision (recommended):**
- `create_async_engine(settings.database_url, pool_pre_ping=True)` at module scope in `app/infrastructure/db/engine.py`.
- `async_sessionmaker(engine, expire_on_commit=False)` — `expire_on_commit=False` is mandatory; the default triggers a lazy refresh after `commit()` that raises `MissingGreenlet` in async context.
- Tests: session-scoped engine + function-scoped connection-bound transaction that always rolls back.
- Alembic stays fully synchronous thanks to psycopg 3.

**If you drop to sync SQLAlchemy (acceptable fallback if the async test harness eats your time budget):**
- Declare route handlers as `def` (not `async def`) so Starlette runs them in the threadpool.
- Drop `pytest-asyncio`; use `fastapi.testclient.TestClient` instead of `httpx.AsyncClient`.
- Keep `psycopg[binary]` — same URL, `create_engine("postgresql+psycopg://…")`.
- Document the tradeoff explicitly in `DECISION_LOG.md`, or a reviewer will read it as ignorance rather than a choice.

**If the 75% coverage gate is at risk near the end:**
- Coverage is dominated by the application layer (use cases), which is pure logic and trivially unit-testable with in-memory fake repositories implementing the same `Protocol` ports. Ten fast unit tests there move the number more than twenty integration tests. This is a direct payoff of the layered architecture the brief mandates — say so in the README.

---

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

---
*Stack research for: layered FastAPI + PostgreSQL REST API (Crehana backend technical challenge)*
*Researched: 2026-09-17*
