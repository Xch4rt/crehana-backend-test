# Phase 2: Domain & Error Contract - Pattern Map

**Mapped:** 2026-09-17
**Files analyzed:** 42 (38 created, 4 modified) + 5 doc/config edits
**Analogs found:** 34 / 42 with a same-role or role-match analog; 8 are first-of-kind

> Phase 1 shipped only **four** source modules (`main.py`, `infrastructure/config/settings.py`,
> and three empty `__init__.py`) and **three** test modules. The analog pool is therefore small
> but it is *complete* — every convention this project has, it has in those seven files. Where no
> role analog exists (entities, Protocol ports, exception hierarchy, the handlers), the **style
> analog** is still binding: docstring voice, import layout, comment discipline and test rhythm
> are copied from Phase 1 regardless of role.

---

## Codebase-Wide Conventions (verified by inspection, apply to every new file)

These were confirmed mechanically, not inferred:

| Convention | Evidence | Rule for Phase 2 |
|---|---|---|
| **No `from __future__ import annotations`** | `grep -rn "from __future__" src tests` returns **nothing** | Do **not** add it. Python 3.13 + PEP 604 (`Task \| None`) works natively at runtime; adding it now would be a gratuitous divergence. |
| **ASCII-only source** | `LC_ALL=C grep -rn '[^ -~]' src tests --include="*.py"` returns **nothing** | No em dashes, no curly quotes, no arrows in `.py` files. Use ` - ` and `->` in prose inside docstrings. (`.planning/*.md` and `DECISION_LOG.md` *do* use em dashes — different rule per file type.) |
| **Every package dir has an empty `__init__.py`** | All six existing `__init__.py` are 0 bytes | New packages (`domain/entities`, `domain/value_objects`, `application/ports`, `application/dto`, `application/use_cases`, `application/use_cases/tasks`, `presentation/api`, `presentation/api/errors`, `tests/unit/domain`, `tests/unit/application`, `tests/api`) each get an **empty** `__init__.py`. No re-export barrels, no docstrings in `__init__.py`. |
| **Module docstrings explain *why*, never *what*** | `settings.py:1-7`, `main.py:1-8`, `test_layer_boundaries.py:1-14` | First line is a short noun phrase ending in a period; blank line; then one or more prose paragraphs justifying a non-obvious choice. Identifiers in backticks. |
| **Inline `#` comments justify a decision, never narrate code** | `settings.py:21`, `.importlinter` header, `test_settings.py:10-11,17,61-62` | Same rule for all new modules. A comment that restates the line below it is the "AI tell" PITFALLS §18 flags. |
| **isort profile = black, `known_first_party = ["taskmanager"]`** | `pyproject.toml [tool.isort]` | Import order: stdlib / third-party / `taskmanager.*`, blank line between groups. Verified in `test_app_factory.py:3-7` (`pytest`, `fastapi` then `taskmanager.*`). |
| **Coverage excludes `...` bodies** | `pyproject.toml [tool.coverage.report] exclude_also` contains `"\\.\\.\\."` | All eight `Protocol` port modules are **free coverage** (the `def` line executes at import; the `...` body is excluded). Do not add `# pragma: no cover` anywhere - CLAUDE.md forbids it. |
| **`branch = true` coverage** | `pyproject.toml [tool.coverage.run]` | Drives the `next(...)`-over-`for/return` and `assert`-over-`if-raise` shapes (RESEARCH Pitfalls 7 and Alternatives table). |

---

## File Classification

### Domain layer (new package content)

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/taskmanager/domain/exceptions.py` | model (error taxonomy) | transform | `src/taskmanager/infrastructure/config/settings.py` (style only) | style-match |
| `src/taskmanager/domain/value_objects/task_status.py` | model (enum + table) | transform | `settings.py` (style only) | style-match |
| `src/taskmanager/domain/value_objects/task_priority.py` | model (enum) | transform | sibling `task_status.py` (written first) | exact (intra-phase) |
| `src/taskmanager/domain/value_objects/completion.py` | value object | transform | sibling `task_status.py` | style-match |
| `src/taskmanager/domain/entities/task.py` | model (aggregate + state machine) | event-driven (state transition) | `settings.py` (declarative class + validation, style only) | partial |
| `src/taskmanager/domain/entities/task_list.py` | model | transform | sibling `task.py` (written first) | exact (intra-phase) |
| `src/taskmanager/domain/entities/user.py` | model | transform | sibling `task.py` | exact (intra-phase) |
| `src/taskmanager/domain/{entities,value_objects}/__init__.py` | config | - | any existing `__init__.py` (empty) | exact |

### Application layer (new package content)

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/taskmanager/application/ports/repositories.py` | interface (Protocol) | CRUD | none in repo - RESEARCH §Ports | no analog |
| `src/taskmanager/application/ports/unit_of_work.py` | interface (Protocol, async CM) | transactional | sibling `repositories.py` | role-match |
| `src/taskmanager/application/ports/security.py` | interface (Protocol) | request-response | sibling `repositories.py` | role-match |
| `src/taskmanager/application/ports/notifications.py` | interface (Protocol) | event-driven | sibling `repositories.py` | role-match |
| `src/taskmanager/application/ports/clock.py` | interface (Protocol, sync) | request-response | sibling `repositories.py` | role-match |
| `src/taskmanager/application/dto/commands.py` | DTO | request-response | `domain/value_objects/completion.py` (frozen dataclass) | role-match |
| `src/taskmanager/application/dto/results.py` | DTO | transform | sibling `commands.py` | exact (intra-phase) |
| `src/taskmanager/application/use_cases/tasks/change_task_status.py` | service (use case) | request-response | `src/taskmanager/main.py` (DI-by-constructor-arg style only) | partial |

### Presentation layer (new package content) + composition root

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/taskmanager/presentation/api/errors/problem.py` | utility (response builder) | transform | none - RESEARCH §Code Examples | no analog |
| `src/taskmanager/presentation/api/errors/mapping.py` | config (lookup table) | transform | `test_layer_boundaries.py:19-23` (module-level `Final` expected-set constant) | partial |
| `src/taskmanager/presentation/api/errors/handlers.py` | middleware (exception handlers) | request-response | none - RESEARCH §Pattern 7 | no analog |
| `src/taskmanager/main.py` **(MODIFIED)** | config (composition root) | - | **itself**, `main.py:15-22` | exact |

### Tests

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `tests/conftest.py` | test fixture module | - | `tests/unit/test_app_factory.py:13-18` (app construction) + RESEARCH §conftest | partial |
| `tests/probe.py` | test double (router) | request-response | none - RESEARCH D-10 / Pitfall 10 | no analog |
| `tests/unit/domain/test_task_status.py` | test | - | `tests/unit/test_settings.py` | exact |
| `tests/unit/domain/test_task.py` | test | - | `tests/unit/test_settings.py` | exact |
| `tests/unit/domain/test_task_list.py` | test | - | `tests/unit/test_settings.py` | exact |
| `tests/unit/domain/test_user.py` | test | - | `tests/unit/test_settings.py` | exact |
| `tests/unit/domain/test_exceptions.py` | test | - | `tests/unit/test_settings.py` | exact |
| `tests/unit/domain/test_completion.py` | test | - | `tests/unit/test_settings.py` | exact |
| `tests/unit/application/fakes.py` | test double (in-memory adapters) | CRUD | none - RESEARCH §Pattern 5 | no analog |
| `tests/unit/application/test_ports.py` | test (conformance) | - | `tests/unit/test_settings.py` | role-match |
| `tests/unit/application/test_change_task_status.py` | test (async) | - | `tests/unit/test_settings.py` (style) + RESEARCH §Use case | partial |
| `tests/api/test_error_contract.py` | test (HTTP integration) | request-response | `tests/unit/test_app_factory.py` (style) | partial |
| `tests/architecture/test_domain_is_stdlib_only.py` | test (architecture) | file-I/O (AST walk) | `tests/architecture/test_layer_boundaries.py` | exact |
| `tests/unit/test_app_factory.py` **(MODIFIED)** | test | - | **itself** | exact |
| `tests/{unit/domain,unit/application,api}/__init__.py` | config | - | `tests/unit/__init__.py` (empty) | exact |

### Docs & config (modified)

| Modified File | Role | Change | Analog |
|---|---|---|---|
| `DECISION_LOG.md` | doc | **Append** ADR-020 (+ optionally ADR-021); never edit ADR-004/005 | `DECISION_LOG.md:19-46` (ADR-001) |
| `.planning/REQUIREMENTS.md` line 32 | doc | Amend ARC-05 wording (Conflict C-02) | in-file surrounding requirement lines |
| `.planning/ROADMAP.md` line 127 | doc | Amend Phase 4 SC-5 to match ARC-05 | in-file |
| `.importlinter` (comment on line ~43) | config | Fix stale "DTOs are pydantic models" comment | `.importlinter` existing comment voice |
| `CLAUDE.md` §Conventions / §Architecture | doc | Optional: populate now that patterns exist | existing §Project Rules voice |
| `.planning/phases/02-domain-error-contract/evidence/domain-stdlib-red-green.txt` | evidence | New red/green capture | `.planning/phases/01-foundation-quality-gates/evidence/import-linter-red-green.txt` |

---

## Pattern Assignments

### `src/taskmanager/domain/exceptions.py` (model, transform)

**Analog:** `src/taskmanager/infrastructure/config/settings.py` — the only existing declarative
"pure class" module; copy its docstring voice and comment discipline, not its content.

**Module docstring pattern** (`settings.py:1-7`):
```python
"""Application settings loaded from the process environment.

`database_url` and `jwt_secret` deliberately carry no default: a misconfigured
process must fail at boot with a single readable ValidationError listing every
missing variable, rather than starting up on a placeholder secret and failing
at the first authenticated request.
"""
```
Note the shape to copy: **summary line ending in a period**, blank line, then a paragraph that
answers *"why is this not the obvious thing?"*. For `exceptions.py` the "why" is `__reduce__`
(RESEARCH §Code Examples supplies the exact wording, already ASCII-clean).

**Import pattern** (`settings.py:9-12`) — stdlib group, blank line, third-party group:
```python
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
```
`exceptions.py` has **only** the stdlib group: `from typing import Any, ClassVar`.

**Class docstring pattern** (`settings.py:16`): one line, sentence case, ends with a period —
`"""Every configurable value of the application, validated at startup."""`

**Inline-comment pattern** (`settings.py:21-24`) — comment states the rationale, then the line:
```python
        # An unknown key in .env is a typo, not a no-op: fail loudly.
        extra="forbid",
        # Settings are read-only once loaded.
        frozen=True,
```

**Core pattern to copy:** RESEARCH `02-RESEARCH.md:1011-1072` verbatim (the `_restore` +
`__reduce__` + `__str__` base). It is the **only** shape that passes B042 + mypy strict + pickle.
Do not substitute ARCHITECTURE.md Pattern 6 (`**details`) — it fails `make lint` (Conflict C-03).

---

### `src/taskmanager/domain/value_objects/task_status.py` (model, transform)

**Analog:** `settings.py` for style; `test_layer_boundaries.py:19-23` for the module-level
constant idiom.

**Module-level `Final` constant pattern** (`test_layer_boundaries.py:19-23`) — a module-level
UPPER_SNAKE constant defined right after imports, used as the single source of truth:
```python
EXPECTED_CONTRACT_NAMES = {
    "Layered architecture (high to low)",
    "Domain is framework-free",
    "Application knows no web framework or ORM",
}
```
`ALLOWED_TRANSITIONS: Final[Mapping[TaskStatus, frozenset[TaskStatus]]]` follows the same
placement; annotate with `Final[...]` because mypy strict is on (Phase 1's constant is untyped
only because it lives in a test, where strictness still applies but the literal infers cleanly —
in `src/` prefer the explicit `Final`).

**Content:** RESEARCH `02-RESEARCH.md:523-528` (three-key exhaustive table; the only forbidden
move is `completed -> pending`). Use `enum.StrEnum`, never `class X(str, Enum)`.

---

### `src/taskmanager/domain/entities/task.py` (model, event-driven)

**Analog:** `settings.py` — the closest existing "class whose whole job is enforcing its own
validity at construction". Copy: the docstring voice, the no-default-means-fail-loudly
commenting, and the habit of putting the *reason* for a constraint next to it.

**Style excerpt to mirror** (`settings.py:15-32`) — class docstring, `model_config` block with
justification comments, then declared fields with constraints:
```python
class Settings(BaseSettings):
    """Every configurable value of the application, validated at startup."""

    model_config = SettingsConfigDict(
        ...
    )

    app_name: str = "Task Manager API"
    environment: str = "local"
    database_url: str
    jwt_secret: str = Field(min_length=16)
```
The dataclass equivalent: class docstring, then `ClassVar` limit constants (the length caps from
TASK-08), then fields, then `__post_init__`, then the named mutators (`rename`, `reschedule`,
`change_status`).

**Decorator:** `@dataclass(slots=True)` — mutable, per RESEARCH §Alternatives (D-01/D-03 need
in-place mutation; `slots=True` turns a typo'd attribute into an `AttributeError`).
DTOs get `@dataclass(frozen=True, slots=True)`; entities do **not**.

**State-machine method shape** (RESEARCH `02-RESEARCH.md:1340` + D-01/D-02/D-03):
`def change_status(self, new_status: TaskStatus, *, now: datetime) -> None` —
`now` arrives as an explicit keyword argument; the domain never calls `datetime.now()` and never
imports the `Clock` Protocol (that would be an upward import and fails the `layers` contract).

**Timezone guard** (RESEARCH `02-RESEARCH.md:552-559`): the aware check is
`dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None`; naive -> `ValidationError`; aware-non-UTC
-> normalise with `value.astimezone(UTC)`.

---

### `src/taskmanager/application/ports/*.py` (interface, Protocol)

**Analog:** none in the repo. Source: RESEARCH `02-RESEARCH.md:1273-1307` (all eight shapes,
verified mypy-strict-clean).

**Formatting rule that is a lint trap, not a preference** (RESEARCH Pitfall 3,
`02-RESEARCH.md:860-875`):
- Protocols where **every** method is a one-liner (`TaskRepository`, `Clock`) -> **no** blank
  lines between methods; black keeps them packed and pycodestyle tolerates it.
- Protocols where **at least one** signature wraps (`UnitOfWork.__aexit__`) -> **one blank line
  between every method**, or flake8 fires `E301 expected 1 blank line, found 0` on black's own
  output.

**Do not** use `@runtime_checkable`: `issubclass()` raises `TypeError` on `UnitOfWork` because it
has non-method members (`tasks`, `task_lists`, `users`).

---

### `src/taskmanager/presentation/api/errors/mapping.py` (config, transform)

**Analog:** `tests/architecture/test_layer_boundaries.py:19-23` for the module-level
single-source-of-truth constant; `settings.py:21` for the justifying comment above it.

**Excerpt to copy in spirit** — RESEARCH `02-RESEARCH.md:1102-1129`, notably the comment that
names the module's exclusive responsibility:
```python
# The ONLY place in the codebase that maps a business failure to an HTTP status.
STATUS_BY_EXCEPTION: Final[dict[type[DomainError], int]] = {...}
```
and the `next((...), default)` MRO walk — **not** the `for`/`return` form, which leaves an
uncoverable `return` plus a partial branch (RESEARCH Pitfall 7) and `# pragma: no cover` is
forbidden by CLAUDE.md.

---

### `src/taskmanager/presentation/api/errors/handlers.py` (middleware, request-response)

**Analog:** none. Source: RESEARCH `02-RESEARCH.md:1138-1244` verbatim.

Four load-bearing details, each already burned in by a verified pitfall:
1. Handlers annotate `exc: Exception` and narrow with `assert isinstance(...)` on the first line.
   `exc: DomainError` is rejected by mypy strict (Pitfall 5); `if not isinstance(...): raise` adds
   an uncoverable partial branch.
2. Register on `starlette.exceptions.HTTPException`, not `fastapi.HTTPException`.
3. `handle_http_exception` must re-copy `exc.headers` onto the response or 401 loses
   `WWW-Authenticate` and 405 loses `Allow` (Pitfall 6).
4. `handle_unexpected_error` never branches on `settings.environment` (D-08) - one shape
   everywhere, which also keeps `presentation` from importing `infrastructure`.

---

### `src/taskmanager/main.py` (config, composition root) — **MODIFIED**

**Analog:** itself. The entire existing file is the pattern; the change is minimal and additive.

**Current code** (`main.py:15-22`):
```python
def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the application, optionally with explicitly injected settings."""
    resolved = settings or get_settings()
    return FastAPI(
        title=resolved.app_name,
        version="0.1.0",
        openapi_url="/openapi.json",
    )
```

**Required shape after the change** — the `return FastAPI(...)` becomes a local binding so the
handlers can be registered before returning:
```python
def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the application, optionally with explicitly injected settings."""
    resolved = settings or get_settings()
    app = FastAPI(
        title=resolved.app_name,
        version="0.1.0",
        openapi_url="/openapi.json",
    )
    register_exception_handlers(app)
    return app
```

**Constraint carried by the existing docstring** (`main.py:1-8`): no module-level `app`. This is
why the imperative `app.add_exception_handler(...)` form is mandatory and the
`@app.exception_handler` decorator is an anti-pattern here, even though it type-checks.

---

### `tests/unit/domain/test_*.py` and `tests/unit/application/test_*.py` (test)

**Analog:** `tests/unit/test_settings.py` — the richest existing test module. Copy all four of
its structural habits.

**Module docstring + module-level fixture constants** (`test_settings.py:1-18`):
```python
"""Unit tests for the environment-backed application settings."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from taskmanager.infrastructure.config.settings import Settings, get_settings

# A syntactically valid DSN and an obviously fake 32-character secret. Both are
# injected through monkeypatch so no test ever depends on the developer's shell.
ENV = {
    "DATABASE_URL": "postgresql+psycopg://user:pass@localhost:5432/taskmanager",
    "JWT_SECRET": "a" * 32,
}
```
For domain tests the equivalent constants are the fixed instants and ids, e.g.
`NOW = datetime(2026, 1, 1, tzinfo=UTC)` / `ACTOR_ID = UUID("...")` — deterministic literals with
a comment saying why they are fixed, never `datetime.now()` in a test body.

**Test-function pattern** (`test_settings.py:21-31`) — `-> None` return annotation, a **one-line
docstring written as a behaviour claim** (not "test that..."), then arrange / act / assert
separated by single blank lines:
```python
def test_settings_read_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Declared fields are read from the process environment, defaults apply."""
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)

    settings = Settings(_env_file=None)

    assert settings.database_url == ENV["DATABASE_URL"]
    assert settings.jwt_secret == ENV["JWT_SECRET"]
```

**Expected-failure pattern** (`test_settings.py:34-42`) — `pytest.raises` with `excinfo`, then an
assertion on the message. Domain tests reuse this for `InvalidStatusTransitionError` /
`ValidationError`, but should additionally assert `excinfo.value.details`, since D-04/D-01 make
`details` (not the string) the contract:
```python
def test_missing_secret_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """A process without JWT_SECRET refuses to start instead of defaulting."""
    ...
    with pytest.raises(ValidationError) as excinfo:
        Settings(_env_file=None)

    assert "jwt_secret" in str(excinfo.value).lower()
```

**Cleanup pattern** (`test_settings.py:61-72`) — a `try/finally` with a comment explaining the
leak being prevented. Relevant if any Phase 2 test mutates shared state (it should not need to).

**Naming:** `test_<subject>_<claim>` in the indicative mood —
`test_settings_read_from_environment`, `test_short_secret_is_rejected`. RESEARCH's §Test Map uses
`-k` selectors `transition`, `same_state`, `completed_at`, `validation`, `naive`, `domain`,
`validation`, `unexpected`, `http`, `probe`, `handlers` — **the test names must contain those
substrings** or the documented commands in `02-RESEARCH.md:1463-1484` select nothing.

**Async tests:** no `@pytest.mark.asyncio`, no `@pytest_asyncio.fixture`, no `event_loop`
override. `pytest.ini` sets `asyncio_mode = auto` and
`asyncio_default_fixture_loop_scope = function`; a bare `async def test_...` and a plain
`@pytest.fixture` on an async generator both work.

---

### `tests/architecture/test_domain_is_stdlib_only.py` (test, architecture)

**Analog:** `tests/architecture/test_layer_boundaries.py` — same directory, same role, same
purpose (turn an architectural claim into a failing test). This is the strongest analog in the
phase; copy its structure closely.

**Module docstring pattern** (`test_layer_boundaries.py:1-14`) — states what the file enforces,
where else the same check runs, and then a **"Deliberately NOT used:"** paragraph naming the
plausible-but-broken alternative and why it was rejected:
```python
"""The architecture contract, executed as part of the normal test suite.

The layer boundaries declared in `.importlinter` are checked here, inside pytest,
so that an upward import or a framework leaking into the domain is a failing test
rather than a folder-naming convention nobody enforces. ...

Deliberately NOT used: running import-linter's command-line module through `python -m`.
That module has no `__main__` guard and the package ships no `__main__.py`, so the form
merely imports it and exits 0 without checking anything - an architecture test that can
never fail. The supported Python API below returns False on a violation, which was
observed before this file was committed (see evidence/import-linter-red-green.txt).
"""
```
The new file's "Deliberately NOT used" paragraph writes itself from Conflict C-01: *the
`forbidden` contract cannot prove this - `forbidden_modules = *` also forbids `dataclasses`,
`datetime` and `enum`*. And, per Pitfall 8, why `ast` + `sys.stdlib_module_names` (Option B) was
chosen over `grimp` (a transitive dependency `requirements-dev.txt` deliberately does not name).

**Anti-vacuity pattern** (`test_layer_boundaries.py:26-39`) — Phase 1's precedent that an
architecture test must first prove it is actually checking something:
```python
def test_every_contract_is_configured() -> None:
    """A config that configures nothing passes vacuously; assert it configures three.
    ...
    """
    config = api.read_configuration()

    assert config["session_options"]["root_packages"] == ["taskmanager"]
    assert {
        contract["name"] for contract in config["contracts_options"]
    } == EXPECTED_CONTRACT_NAMES
```
The stdlib-only test needs the same guard: assert the AST walk actually found N domain modules
(`assert len(scanned) >= 7`) before asserting `violations == []`, or an empty glob passes
vacuously.

**Assertion pattern** (`test_layer_boundaries.py:42-44`): one short function, docstring is the
claim, body is a single assert.

**Note for the planner:** `EXPECTED_CONTRACT_NAMES` (`test_layer_boundaries.py:19-23`) only needs
updating if `.importlinter` gains or renames a contract. Phase 2's `.importlinter` change is a
**comment fix only** (Conflict C-02), so this set stays as-is — but the plan must say so
explicitly, because a plan that "helpfully" adds a fourth contract breaks this test.

---

### `tests/conftest.py` (test fixture module)

**Analog:** `tests/unit/test_app_factory.py:9-18` for app construction under test.

**App-construction excerpt to reuse** (`test_app_factory.py:9-18`) — note that `Settings` is
built with `_env_file=None` **and** the two required env vars are injected via `monkeypatch`,
because `database_url` and `jwt_secret` have no defaults:
```python
DATABASE_URL = "postgresql+psycopg://user:pass@localhost:5432/taskmanager"
JWT_SECRET = "b" * 32


def test_create_app_uses_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """create_app() builds a FastAPI instance from the settings it is given."""
    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
    monkeypatch.setenv("JWT_SECRET", JWT_SECRET)

    app = create_app(Settings(_env_file=None))
```
The `app` fixture must do the same env injection (via `monkeypatch`, which is function-scoped —
consistent with `asyncio_default_fixture_loop_scope = function`) before `Settings(_env_file=None)`
or it raises `ValidationError`. RESEARCH `02-RESEARCH.md:1348-1369` shows the three fixtures but
elides this; the planner must carry it over from `test_app_factory.py`.

**Fixture shapes:** RESEARCH `02-RESEARCH.md:1348-1369` (`app`, `client`, `tolerant_client`).
`tolerant_client` exists **only** for the 500 test (Pitfall 4: `ServerErrorMiddleware` always
re-raises). Never make the shared `client` tolerant.

---

### `tests/unit/test_app_factory.py` (test) — **MODIFIED**

**Analog:** itself. Two tests are appended in the existing style
(`test_app_factory.py:13-22` is the template):

- `test_create_app_registers_exception_handlers` — asserts the four keys are present in
  `app.exception_handlers` (keeping in mind `Exception`/`500` is lifted out onto
  `ServerErrorMiddleware` by `build_middleware_stack`).
- `test_production_app_has_no_probe_routes` — RESEARCH Pitfall 10,
  `02-RESEARCH.md:991-994`.

Both names must contain `handlers` and `probe` respectively to match the `-k` selectors in the
RESEARCH test map.

---

### `DECISION_LOG.md` (doc) — **MODIFIED, append-only**

**Analog:** `DECISION_LOG.md:19-46` (ADR-001). The header at `DECISION_LOG.md:5-16` states the
contract explicitly: **four parts, never rewritten, superseded by id only**.

**Exact heading and section format to copy:**
```markdown
## ADR-001: PostgreSQL, not SQLite

**Context**
The challenge brief requires "a real database". SQLite would run with zero setup and no
container, which is tempting for a deliverable an evaluator has five minutes to assess.

**Options**

- **SQLite** - no service to start, ... Rejected:
  it invites the reviewer to ask whether "a real database" was satisfied, ...
- **PostgreSQL 18** - a service the evaluator must start, but `docker compose up` is required
  by the brief anyway.

**Decision**
PostgreSQL, reached through SQLAlchemy 2.0 and psycopg 3. ...

**Consequences**

- Integration tests need a running database. That is an accepted cost: ...

---
```
Observed rules: title is `## ADR-0NN: <lowercase-ish decisive phrase>`; `**Context**` and
`**Decision**` have **no** blank line before their prose; `**Options**` and `**Consequences**`
**do** have a blank line before their bullet list; every rejected option is named with the word
"Rejected:"; the entry closes with a `---` separator. Next free id: **ADR-020**
(ADR-019 is the last, at `DECISION_LOG.md:587`).

**Content required by RESEARCH:**
- ADR-020 — application command/result DTOs are frozen dataclasses, *refining* ADR-004
  (Conflict C-02). Must also record the `ResponseValidationError` -> 500 consequence
  (`02-RESEARCH.md:726-731`) and which stdlib-only proof (Option A vs B) was chosen and why
  (`02-RESEARCH.md:774-776`).
- Optionally a second ADR for the `DomainError.__reduce__` shape if the plan wants B042's false
  pass documented separately.

---

### `evidence/domain-stdlib-red-green.txt` (evidence)

**Analog:** `.planning/phases/01-foundation-quality-gates/evidence/import-linter-red-green.txt`.

**Format to copy** (lines 1-25 of that file):
```
Architecture-contract demonstration - Phase 1, plan 01-03
Date: 2026-09-17
Host: macOS arm64, CPython 3.14.3 in .venv, import-linter 2.15, pytest 9.1.1

Commands, in the order they were run:
  printf 'from fastapi import FastAPI\n\n__all__ = ["FastAPI"]\n' \
      > src/taskmanager/domain/_violation.py
  .venv/bin/pytest tests/architecture -q --no-cov ;  echo $?
  ...
  rm src/taskmanager/domain/_violation.py
  .venv/bin/pytest tests/architecture -q --no-cov ;  echo $?

What this proves: the layer boundaries in .importlinter are enforced, not decorative -
a single forbidden import placed inside taskmanager.domain turns the pytest suite red
and only the removal of that import turns it green again.

The violation module was deleted immediately after the red runs and exists neither on
disk nor in git history as a tracked file; the green runs below are the shipped tree.
```
Structure: title line with phase + plan id, `Date:`, `Host:`, the literal command list, a *"What
this proves"* paragraph, a disclosure paragraph about the planted file, a note on any elision,
then verbatim captures with exit codes. Phase 2's version plants `import pydantic` in a domain
module instead.

---

## Shared Patterns

### Docstring voice (apply to every new `.py` file under `src/` and `tests/`)
**Source:** `src/taskmanager/main.py:1-8`, `src/taskmanager/infrastructure/config/settings.py:1-7`
**Apply to:** all 38 new source and test modules (empty `__init__.py` excepted)
```python
"""Composition root: builds the FastAPI application.

`create_app` is a factory rather than a module-level `app = create_app()`.
A module-level instance would evaluate the settings at import time, which makes
`import taskmanager.main` crash in any environment without JWT_SECRET -
including mypy's, import-linter's and a plain `docker build`. The container
runs `uvicorn --factory taskmanager.main:create_app`.
"""
```
The tell: it names the alternative that was *not* chosen and the concrete failure that
alternative causes. Every Phase 2 module has such a paragraph available (why not `frozen=True`,
why not `**details`, why not `exc: DomainError`, why not `runtime_checkable`, why not
`for`/`return`) — use it. Note ` - ` used as a dash, ASCII only.

### Type-annotation conventions
**Source:** `main.py:15`, `settings.py:36`, `test_settings.py:21`
**Apply to:** every function, including tests
- Every function and method carries a full annotation **including `-> None`** on tests and
  procedures (`def test_... (monkeypatch: pytest.MonkeyPatch) -> None:`). mypy strict runs over
  `tests` as well as `src` (`pyproject.toml [tool.mypy] packages = ["taskmanager"]`, with the
  pre-commit/CI invocation covering tests).
- PEP 604 unions inline (`Settings | None`, `Task | None`) — no `Optional`, no
  `from __future__ import annotations`.
- `ClassVar[str]` for `code`/`title` on exception classes and `Final[...]` for module constants —
  both are mypy-strict requirements, not decoration.
- No `# type: ignore` anywhere. If mypy objects to
  `add_exception_handler(DomainError, handler)`, the fix is the `exc: Exception` + `assert`
  shape, never a suppression.

### Error handling
**Source:** `DECISION_LOG.md:146-173` (ADR-005), `CLAUDE.md` §Project Rules
**Apply to:** every module in `domain/`, `application/`, `presentation/`
- Business failures raise a `DomainError` subclass. `fastapi.HTTPException` never appears outside
  `presentation` (and in Phase 2, not even there — only the *handler* for it does).
- Exactly one `problem(...)` builder constructs error bodies; no handler assembles a dict inline.
- `detail` comes from `exc.message`, never `str(exc)` (Pitfall 2) — though the explicit `__str__`
  on `DomainError` makes them equal, relying on that couples the wire format to `__str__`.

### Validation placement
**Source:** CONTEXT D-04, `.importlinter` domain contract
**Apply to:** entities vs. presentation schemas
- Policy limits (blank title, length caps, past `due_date`) live **only** in the entity
  (`__post_init__` / mutators). Pydantic at the HTTP boundary checks shape and type only.
  A limit duplicated in two layers is a defect, not redundancy.

### Test layout and gating
**Source:** `pytest.ini`, `tests/unit/test_settings.py`
**Apply to:** all new test files
- `filterwarnings = error` — any `DeprecationWarning` from new code fails the suite.
  No `datetime.utcnow()`, ever.
- Markers `unit` and `integration` are declared with `--strict-markers`; Phase 2 adds **no** new
  marker (all of it is `unit`/`api`-without-I/O). Do not invent one without adding it to
  `pytest.ini`.
- Every new package under `tests/` gets an empty `__init__.py` (both existing test packages have
  one).
- Quick loop: `.venv/bin/pytest tests/unit -q --no-cov`. Gate: `make lint && make typecheck &&
  make arch && make test`.

### Config-file comment style
**Source:** `.importlinter` header (lines 1-10), `pytest.ini:3`, `pyproject.toml` NOTE blocks
**Apply to:** the `.importlinter` comment fix
```
# `include_external_packages = True` is required for the two `forbidden` contracts:
# without it import-linter never builds nodes for third-party distributions and the
# contracts silently have nothing to check.
```
Comments state the failure mode being prevented. The stale comment to fix
(`.importlinter`, "The application layer ... may use pydantic (DTOs are pydantic models)") should
be rewritten to say pydantic *remains permitted* there while ADR-020 chooses frozen dataclasses —
not deleted, because the permissiveness of the contract is itself deliberate
(`02-RESEARCH.md:333-336`: do **not** add `pydantic` to `application-framework-free`).

---

## No Analog Found

Files with no role match in the Phase 1 codebase. The planner should take the shape from
`02-RESEARCH.md` §Code Examples (every block there was executed against this repo's own venv and
passed black + flake8 + mypy strict + pytest) and apply the style patterns above.

| File | Role | Data Flow | Reason | Use instead |
|---|---|---|---|---|
| `application/ports/repositories.py` | interface | CRUD | No `Protocol` exists in the repo yet | `02-RESEARCH.md:1273-1307` + Pitfall 3 blank-line rule |
| `application/use_cases/tasks/change_task_status.py` | service | request-response | No use case exists yet | `02-RESEARCH.md:1326-1343` |
| `application/dto/commands.py` / `results.py` | DTO | request-response | No frozen dataclass exists yet | `02-RESEARCH.md:1312-1323` |
| `presentation/api/errors/problem.py` | utility | transform | Presentation package is empty | `02-RESEARCH.md:1149-1172` |
| `presentation/api/errors/handlers.py` | middleware | request-response | No handler / router exists yet | `02-RESEARCH.md:1175-1243` + Pitfalls 4, 5, 6 |
| `tests/probe.py` | test double (router) | request-response | No router of any kind exists yet | CONTEXT D-10 + Pitfall 10 (`02-RESEARCH.md:982-999`) |
| `tests/unit/application/fakes.py` | test double | CRUD | No fake/in-memory adapter exists yet | `02-RESEARCH.md:613-624` (F841-safe conformance idiom) |
| `tests/api/test_error_contract.py` | test (HTTP) | request-response | No HTTP-level test exists (`test_app_factory.py` never issues a request) | `02-RESEARCH.md:1348-1369` fixtures + §Test Map rows |

---

## Planner Notes (ordering implied by the analogs)

1. `domain/exceptions.py` and `domain/value_objects/task_status.py` are the two *originating*
   files — every later domain and application module copies from them rather than from Phase 1.
   Write them first and get them through `make lint && make typecheck` before fanning out.
2. `tests/architecture/test_domain_is_stdlib_only.py` has an exact analog and no dependency on
   the domain content beyond "the package exists"; it can be written early and will pass
   vacuously until the anti-vacuity guard is added — add the guard in the same commit.
3. `main.py`'s change is three lines and depends on `handlers.py` existing; it is the last
   source edit of the phase.
4. The doc edits (ADR-020, ARC-05, ROADMAP SC-5, `.importlinter` comment) resolve Conflict C-02
   and are independent of the code; they can land in any plan but must all land, or Phase 4
   verification fails against its own text.

---

## Metadata

**Analog search scope:** `src/taskmanager/**` (4 non-empty modules), `tests/**` (3 modules),
`.importlinter`, `pytest.ini`, `pyproject.toml`, `.flake8`, `Makefile`, `DECISION_LOG.md`,
`.planning/phases/01-foundation-quality-gates/evidence/`
**Files scanned:** 14 Python files + 8 config/doc files
**Mechanical checks run:** `grep -rn "from __future__"` (0 hits),
`LC_ALL=C grep -rn '[^ -~]'` over `src`/`tests` (0 hits), `__init__.py` byte-size check (all 0)
**Pattern extraction date:** 2026-09-17
