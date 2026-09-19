# Phase 6: Test Hardening & Coverage - Pattern Map

**Mapped:** 2026-09-19
**Files analyzed:** 18 (7 new, 11 modified/swept)
**Analogs found:** 17 / 18

Every new artifact in this phase has a sibling already in the tree. This phase writes no
production code, so every analog is a test, a test-support module, a shell script or a
Makefile target. The three house styles that matter are: **the AST gate**
(`tests/architecture/test_routers_raise_no_http_exception.py`), **the OpenAPI partition**
(`tests/unit/presentation/test_security_scheme.py`) and **the script + its driver test**
(`scripts/init-env.sh` + `tests/unit/test_env_bootstrap.py`).

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `tests/architecture/test_use_case_totality.py` (new) | architecture gate (test) | AST scan / batch | `tests/architecture/test_routers_raise_no_http_exception.py` | exact |
| `tests/architecture/test_assertion_quality.py` (new) | architecture gate (test) | AST scan / batch | `tests/architecture/test_routers_raise_no_http_exception.py` | exact |
| `tests/architecture/test_coverage_configuration.py` (new) | architecture gate (test) | file-I/O (INI + TOML parse) | `tests/architecture/test_layer_boundaries.py` + `test_no_commit_in_repositories.py` | role-match |
| `tests/integration/test_endpoint_totality.py` (new) | integration gate (test) | event-driven (run-wide observation) | `tests/unit/presentation/test_security_scheme.py` | role-match |
| `tests/integration/conftest.py` (modified: ASGI recorder + ordering hook) | harness / fixture | event-driven recorder | `statements` fixture (`conftest.py:495-534`) + `api_client` (`:306-381`) | role-match |
| `tests/problem_details.py` (new) | test-support utility (never collected) | constants | `tests/probe.py` | exact |
| `scripts/break-check.sh` (new) | script (POSIX sh) | file mutate → subprocess → restore | `scripts/init-env.sh` | exact |
| `tests/unit/test_break_check.py` (new) | test (drives a script as a program) | subprocess + file-I/O | `tests/unit/test_env_bootstrap.py` | exact |
| `Makefile` (new `test-unit`, `break-check`) | config | n/a | `Makefile` `test` / `env` targets | exact |
| `tests/conftest.py` (new unmarked-item guard) | collection hook | collection-time | no in-repo hook precedent; idiom from the non-vacuity guards | partial |
| 41 unmarked test modules (`pytestmark = pytest.mark.unit`) | test (modified) | n/a | `tests/integration/api/test_task_lists.py:53` | exact |
| `tests/unit/presentation/test_error_contract.py` (moved from `tests/api/`) | test (moved) | request-response | its own body; siblings in `tests/unit/presentation/` | exact |
| ~29 sweep edits under `tests/integration/api/` (D-05b / D-06) | test (modified) | request-response | `test_task_lists.py:412-431` | exact |
| `tests/integration/api/test_tasks.py` transition complement | test (modified) | request-response | `test_tasks.py:909-936` + `tests/unit/domain/test_task_status.py:44-71` | exact |
| `tests/integration/api/test_auth.py` caller-seeding fix (D-14) | test (modified) | request-response | `seed(...)` usage at `test_task_lists.py:417` | exact |
| `tests/integration/test_concurrent_writes.py` list-deletion case (optional) | test (new case) | transactional / concurrent | `test_concurrent_writes.py:337-368` | exact |
| `AI_WORKFLOW.md` incident entry | docs | n/a | `AI_WORKFLOW.md:299-330` | exact |
| `DECISION_LOG.md` ADR-085.. + `CLAUDE.md` rule bullets | docs | n/a | `DECISION_LOG.md:3563` (ADR-084) | exact |

## Pattern Assignments

### `tests/architecture/test_use_case_totality.py` and `test_assertion_quality.py` (architecture gate, AST scan)

**Analog:** `tests/architecture/test_routers_raise_no_http_exception.py`
(secondary: `tests/architecture/test_no_commit_in_repositories.py` for the simpler shape)

**Module header / path constant** (`test_routers_raise_no_http_exception.py:87-104`) — note the
`parents[2]` comment spelling out the hop count, and `Final` on every constant:

```python
import ast
from pathlib import Path
from typing import Final

# tests/architecture/test_routers_raise_no_http_exception.py ->
# tests/architecture -> tests -> repository root.
PRESENTATION_API: Final[Path] = (
    Path(__file__).resolve().parents[2] / "src" / "taskmanager" / "presentation" / "api"
)
```

**Non-vacuity guard** (`:116-131` and `:230-242`) — this is the `REQUIRED_SCANNED_MODULES`
shape D-02 and D-05 must copy. `REQUIRED_USE_CASE_SYMBOLS` (20 names) and
`REQUIRED_SCANNED_TEST_MODULES` are the Phase 6 instances:

```python
# Named rather than counted. Requiring these by name is what makes the scan
# non-vacuous - a renamed or emptied package, or a module that quietly stopped
# being scanned, fails the guard below instead of leaving the real tests
# asserting that nothing is nothing. [...] A new router or
# provider adds its name here in the same commit that creates it.
REQUIRED_SCANNED_MODULES: Final[frozenset[str]] = frozenset(
    {
        "actor.py",
        "dependencies.py",
        ...
    }
)


def test_the_presentation_api_package_is_actually_scanned() -> None:
    """A glob that matches nothing passes vacuously; assert it matched the tree."""
    scanned = {_relative(path) for path in _scanned_modules()}

    assert scanned
    assert REQUIRED_SCANNED_MODULES <= scanned
    assert scanned.isdisjoint(EXEMPT_MODULES)
```

**`file:line` offender reporting** (`:210-227`) — the exact helper pair to copy; every gate in
this repo reports locations, never a bare boolean:

```python
def _location(path: Path, node: ast.AST) -> str:
    """`file:line`, so a failure names the line rather than the rule alone."""
    return f"{_relative(path)}:{getattr(node, 'lineno', '?')}"


def raise_offenders(path: Path, tree: ast.Module) -> list[str]:
    """`file:line` for every `raise` of the class, under any name it is bound to."""
    forbidden = _local_names_of_the_class(tree)
    return [
        _location(path, node)
        for node in ast.walk(tree)
        if isinstance(node, ast.Raise) and _raised_name(node) in forbidden
    ]
```

**Assertion message shape** (`:271-278`) — `assert offenders == []` with a prose message naming
the rule, the decision id, and the offender list:

```python
    assert offenders == [], (
        "The presentation layer must never answer a failure itself: it raises a "
        "DomainError, and the single exception handler turns that into the one "
        "problem+json body the API speaks. [...] (ADR-008, D-15). Offending raise statements: "
        f"{offenders}"
    )
```

**Parsing helper** (`:147-149`) — filename kept for error text:

```python
def _parsed(path: Path) -> ast.Module:
    """The module's syntax tree, with the filename kept for the error text."""
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
```

**Snippet self-tests** (`:304-353`) — the gate's own detection logic is proved against planted
source on every run, not only on the day it was driven red by hand. `test_assertion_quality.py`
should copy this verbatim for its taint-tracking and helper-resolution rules (RESEARCH Pitfall 2
is exactly the failure this catches):

```python
def _offenders_in(source: str) -> tuple[list[str], list[str]]:
    """Both passes over a snippet, as (raise offenders, reference offenders)."""
    path = PRESENTATION_API / "planted.py"
    tree = ast.parse(source)
    return raise_offenders(path, tree), reference_offenders(path, tree)


def test_the_raise_pass_catches_an_aliased_import() -> None:
    raised, referenced = _offenders_in(
        "from fastapi import HTTPException as HE\n"
        "def handler():\n"
        "    raise HE(status_code=401)\n"
    )

    assert raised == ["planted.py:3"]
    assert referenced == ["planted.py:1"]
```

**Exemption + companion test** (`:107-108`, `:245-260`) — this is the shape D-07's
`REQUIRED_NO_REREAD` frozenset must follow: an exemption has to keep justifying itself:

```python
# The single exception-handling point. See the module docstring: a module, not
# the `errors/` package, and guarded by a test of its own.
EXEMPT_MODULES: Final[frozenset[str]] = frozenset({"errors/handlers.py"})


def test_the_exempt_module_still_needs_its_exemption() -> None:
    """An exemption is a hole, so it has to keep justifying itself."""
    for relative in EXEMPT_MODULES:
        path = PRESENTATION_API / relative
        assert path.is_file(), f"{relative} is exempt from the scan and does not exist"
        tree = _parsed(path)
        assert reference_offenders(
            path, tree
        ), f"{relative} no longer names the class; remove it from EXEMPT_MODULES"
```

For `no_reread`, the equivalent three assertions are: the frozenset is non-empty, every node id
in it still exists, and every one still carries the marker with a non-empty reason.

---

### `tests/architecture/test_coverage_configuration.py` (architecture gate, config file-I/O)

**Analog:** `tests/architecture/test_layer_boundaries.py` (reads a config file and pins its
contents by exact set) + `test_no_commit_in_repositories.py` (root-relative path constant).

**Exact-set pin with its own cost stated** (`test_layer_boundaries.py:19-45`) — this is the
pattern for pinning `exclude_also` by exact list (RESEARCH: "pin by exact list, not by length"):

```python
EXPECTED_CONTRACT_NAMES = {
    "Layered architecture (high to low)",
    "Domain is framework-free",
    "Application knows no web framework or ORM",
    "No web framework below presentation",
}


def test_every_contract_is_configured() -> None:
    """A config that configures nothing passes vacuously; assert what it configures.

    The set is compared exactly rather than by length or by containment, which has a
    cost worth stating: adding a contract to `.importlinter` fails this test until the
    name is added here too. That is the guard working. A contract *removed* from the
    config is the case it exists for, and no weaker comparison catches it.
    """
    config = api.read_configuration()

    assert config["session_options"]["root_packages"] == ["taskmanager"]
    assert {
        contract["name"] for contract in config["contracts_options"]
    } == EXPECTED_CONTRACT_NAMES
```

**Root-relative path constant** (`test_no_commit_in_repositories.py:43-52`) — the same
`parents[2]` hop, with the comment:

```python
# tests/architecture/test_no_commit_in_repositories.py -> tests/architecture ->
# tests -> repository root.
REPOSITORIES: Final[Path] = (
    Path(__file__).resolve().parents[2] / "src" / "taskmanager" / ...
)
```

**Text-scan offender list** (`test_no_commit_in_repositories.py:86-99`) — the shape for the
"no `# pragma: no cover` under `src/`" half, which is a text property, not a syntax one:

```python
def test_no_repository_commits_its_own_transaction() -> None:
    offenders = [
        f"{path.relative_to(REPOSITORIES).as_posix()}:{number}"
        for path in _repository_modules()
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if FORBIDDEN_CALL in line
    ]

    assert offenders == [], (...)
```

**Values under audit** (read, do not re-derive) — `pytest.ini` currently carries
`--cov=taskmanager`, `--cov-report=term-missing`, `--cov-report=xml`, `--cov-fail-under=75`,
`--strict-markers`, `--strict-config`, `filterwarnings = error`, and `markers = unit, integration`.

---

### `tests/integration/test_endpoint_totality.py` (integration gate, observed run)

**Analog:** `tests/unit/presentation/test_security_scheme.py` — the only module in the repo that
enumerates `app.openapi()` operation by operation.

**Operation enumeration** (`test_security_scheme.py:56-107`) — copy `NON_OPERATION_KEYS` and
`_operations()`; do **not** read `app.routes` (ADR-057, and RESEARCH Pitfall 1):

```python
# Everything an OpenAPI path item can hold that is not an operation. Filtering
# by an allow-list of verbs instead would silently drop a verb this API grows
# later; this way a new one is included and has to satisfy the partition.
NON_OPERATION_KEYS: Final[frozenset[str]] = frozenset(
    {"summary", "description", "servers", "parameters", "$ref"}
)


def _operations() -> dict[tuple[str, str], dict[str, Any]]:
    """Every operation in the document, keyed by (method, path)."""
    return {
        (method, path): operation
        for path, item in _document()["paths"].items()
        for method, operation in item.items()
        if method not in NON_OPERATION_KEYS
    }
```

**Partition assertion, both directions in one pass** (`:146-173`) — this is the argument for
D-03's two-sided check, already written out:

```python
def test_every_operation_either_requires_the_scheme_or_is_a_named_open_one() -> None:
    """The partition. A route shipped without a token requirement fails here.

    Both directions are asserted in one pass, which is what makes the test
    survive plan 05-12's three new routes without being edited [...] A
    per-route loop over a list of expected secured routes would have said
    nothing about either.
    """
    operations = _operations()
    assert operations
    ...
```

Note `assert operations` on line 157 — the same non-vacuity reflex as the AST gates, applied to
a document instead of a glob.

**The document is built from injected settings** (`:83-97`) — no `.env`, no database, no network:

```python
def _document() -> dict[str, Any]:
    application = create_app(
        Settings(_env_file=None, database_url=DATABASE_URL, jwt_secret=JWT_SECRET)
    )
    return application.openapi()
```

The Phase 6 gate needs the *harness's* app rather than a fresh one (the recorder sees the app the
tests drove), so take it from the `(client, app)` two-tuple the fixtures already yield.

---

### `tests/integration/conftest.py` (modified: ASGI recorder + collection ordering hook)

**Analog:** the `statements` fixture (`tests/integration/conftest.py:495-534`) — the existing
recorder precedent (an event listener that appends to a list and is removed in a `finally`), and
`api_client` (`:306-381`) for where the wrapper attaches.

**Where the recorder attaches** (`:371-380` — `authenticated_client` at `:421-429` is the same
four lines minus the actor override). The recorder wraps at the transport so the application
under test stays byte-for-byte the production one:

```python
    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
    monkeypatch.setenv("JWT_SECRET", JWT_SECRET)

    app = create_app(Settings(_env_file=None))
    app.dependency_overrides[get_uow] = lambda: SqlAlchemyUnitOfWork(session_factory)
    app.dependency_overrides[get_current_actor] = lambda: OWNER_ID

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, app
```

Both fixtures must be changed together, and the one-line difference between them
(`get_current_actor`) is documented at `:388-394` as deliberate — keep it.

**Fixture docstring convention** — every fixture in this file names the shapes a reader would
expect and why they are absent ("Three shapes a reader may expect here are deliberately absent",
`:321`). The recorder's docstring owes the same: why a wrapper rather than `app.add_middleware`,
why a module-level session-lived set is sound (single-process, no xdist), and the property
RESEARCH names — "a route requested by a test that only proved a 401 still counts as requested".

**Module-level constants with the reason they live here** (`:77-83`):

```python
# The caller `api_client` runs as, in the readable identifier series every
# integration module already uses. It lives here rather than in one of them
# because the fixture below is what makes it the caller [...]
OWNER_ID = UUID("00000000-0000-4000-8000-000000000001")
```

**Stale-prose warning:** `alembic_config`'s docstring (`:99`) names
`tests/api/test_error_contract.py` by path. The D-13 move must update it in the same commit.

---

### `tests/problem_details.py` (test-support utility, never collected)

**Analog:** `tests/probe.py` — the existing "lives under `tests/`, importable, never collected"
module, with the docstring that justifies the location:

```python
"""A throwaway router that raises one of each error family on demand.

It lives under `tests/` rather than under `src/` for three reasons. [...]
Keeping it outside `src/` also keeps it out of the coverage source, so routes
that exist purely to fail cannot flatter the numbers. And it stays out of
import-linter's graph - whose `root_package` is `taskmanager` [...]
"""
```

**What moves** (`tests/api/test_error_contract.py:18-20`):

```python
PROBLEM_JSON = "application/problem+json"

MEMBERS = ["type", "title", "status", "detail", "instance", "code"]
```

**The import convention the move must preserve** (`test_task_lists.py:36-41` — six sites import
these, and every one carries this comment; `test_auth.py:51-53` repeats it by reference):

```python
# Imported rather than re-declared. The media type and the six-member list
# are the error contract Phase 2 fixed, and `tests/api/test_error_contract.py`
# is where they are stated; a second copy here would be the one that quietly
# disagreed the first time the contract moved. A rename over there breaks this
# import loudly, which is the failure mode to prefer.
from tests.api.test_error_contract import MEMBERS, PROBLEM_JSON
```

Six import sites to rewrite: `tests/integration/api/{test_task_lists,test_assignment,test_auth,
test_permission_matrix,test_tasks,test_users}.py` — plus the moved module itself. The comment
text must be updated to name the new home, not just the import line.

---

### `scripts/break-check.sh` (script, POSIX sh)

**Analog:** `scripts/init-env.sh` — same shell, same constraints, same documentation weight.

**Header + constraints** (`init-env.sh:1-31`):

```sh
#!/bin/sh
# Write a .env with a real JWT_SECRET, and never destroy one that already works.
#
# Three behaviours, in the order they are decided below:
#   * no .env            -> copy .env.example and generate a secret into it;
#   ...
# POSIX sh only, and no `sed -i`: its argument differs between GNU and BSD, and
# an evaluator on macOS would get the GNU form silently creating a backup file
# named after the expression. Paths are resolved against the working directory,
# so `make` runs it at the repository root and a test can run it in a temporary
# one. The generated value is never printed.
set -eu

EXAMPLE=.env.example
TARGET=.env

if [ ! -f "$EXAMPLE" ]; then
	echo "$EXAMPLE not found - run this from the repository root." >&2
	exit 1
fi
```

Copy: `set -eu`, the tab-indented bodies, the precondition check with a remedy on stderr and
`exit 1`, and the "no `sed -i`" rule (the break script applies its mutations with a here-doc
Python `str.replace` carrying an `assert old in s` precondition — RESEARCH D-09 table).

**Trap-based restore** (`init-env.sh:68-69`) — the precedent for D-09's
`trap 'git checkout -- src/' EXIT INT TERM`, installed before the first mutation:

```sh
tmp="$TARGET.tmp.$$"
trap 'rm -f "$tmp"' EXIT
```

**Terminal message shape** (`:77-81`) — a plain sentence naming what changed, never the secret
itself. The break script's equivalent is "which tests failed" per break.

---

### `tests/unit/test_break_check.py` (test that drives a script as a program)

**Analog:** `tests/unit/test_env_bootstrap.py` — runs the real `.sh` through `sh` in `tmp_path`
rather than reimplementing its decisions in Python.

**Module docstring + root/script constants + runner** (`:1-44`):

```python
"""The `make env` bootstrap script, driven as a real program.

`scripts/init-env.sh` is the evaluator's first command, so these tests run the
file itself through `sh` in a temporary directory rather than reimplementing its
decisions in Python. Nothing here asserts on the wording it prints: the
behaviour under test is the file it leaves behind.
"""

# tests/unit/test_env_bootstrap.py -> tests/unit -> tests -> repository root.
ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "init-env.sh"


def run_in(directory: Path) -> subprocess.CompletedProcess[str]:
    """Run the script with `directory` as its working directory."""
    return subprocess.run(
        ["sh", str(SCRIPT)],
        cwd=directory,
        check=True,
        capture_output=True,
        text=True,
    )
```

**The "assert the behaviour, not the wording" rule** (`:57-62`) — for the break script this means
asserting the tree is restored and the exit status inverts, never the printed banner:

```python
    """With no `.env`, the script writes one the application can start from.

    Booting the generated file is the honest assertion. A length check alone
    would also pass on the published placeholder [...]
    """
```

Note the break script's own tests cannot run it against the real `src/` (it mutates and
restores); follow `test_env_bootstrap.py`'s `tmp_path` discipline — build a throwaway git
repository in `tmp_path` for the dirty-tree refusal and the restore-on-interrupt legs, and keep
the full five-break run behind `make break-check` rather than inside pytest (D-09).

---

### `Makefile` (new `test-unit` and `break-check` targets)

**Analog:** the `test` and `env` targets.

```makefile
.PHONY: install env lint format typecheck arch test docker-test up down run

VENV := .venv

# The 75% coverage gate rides along via the addopts in pytest.ini, so `make test`
# and a bare `pytest` are gated by the same bytes.
test:
	$(VENV)/bin/pytest

env:
	sh scripts/init-env.sh
```

Three file-level rules stated in the Makefile header (`:1-12`) and binding on the new targets:
GNU Make 3.81 — every recipe line runs in its own shell, no recipe relies on a previous line's
`cd`; no target assumes an activated virtualenv (always `$(VENV)/bin/`); every target carries a
comment block explaining why it exists. Both new names go in `.PHONY`.

RESEARCH supplies the `test-unit` body and its comment verbatim (§D-13):

```makefile
test-unit:
	$(VENV)/bin/pytest -m unit --no-cov
```

---

### Sweep edits under `tests/integration/api/` (D-05b / D-06, ~29 tests)

**Analog:** `tests/integration/api/test_task_lists.py:412-431` — the canonical
before / mutate / after shape the sweep replicates:

```python
async def test_patch_with_a_name_only_leaves_the_description_alone(
    api_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """D-05's omitted leg: an absent field is not a cleared field."""
    await seed(session_factory, users=[a_user()], task_lists=[a_task_list()])
    client, _ = api_client
    before = (await client.get(f"{TASK_LISTS}/{LIST_ID}")).json()

    response = await client.patch(f"{TASK_LISTS}/{LIST_ID}", json={"name": "Weekly"})

    assert response.status_code == 200
    assert response.json()["name"] == "Weekly"

    after = (await client.get(f"{TASK_LISTS}/{LIST_ID}")).json()

    assert after["name"] == "Weekly"
    assert after["description"] == before["description"]
    assert after["created_at"] == before["created_at"]
    assert moment(after["updated_at"]) > moment(before["updated_at"])
```

**The rejected-mutation leg is what the sweep adds.** A typical offender today
(`test_task_lists.py:888-913`) ends at the problem body with no re-read:

```python
    response = await client.patch(f"{TASK_LISTS}/{LIST_ID}", json={})

    assert response.status_code == 422
    assert response.headers["content-type"] == PROBLEM_JSON

    body = response.json()

    assert list(body) == [*MEMBERS, "errors"]
    assert body["code"] == "validation_error"
    ...
```

D-06's fix is the mechanical two-line addition: capture `before = (await client.get(...)).json()`
above the mutation and assert `after == before` below it — the same two lines the analog above
already uses for its success leg.

**Named-helper convention** (`test_task_lists.py:547-579`) — the sweep must *use* these rather
than inlining body assertions, and the D-05a gate must *resolve* them (RESEARCH Pitfall 2, and
`anonymised` is imported across modules by `test_auth.py:57`):

```python
def anonymised(response: Response, *identifiers: uuid.UUID) -> str:
    """The serialised body with every named identifier replaced by one token."""
    ...


def assert_not_found(response: Response, task_list_id: uuid.UUID) -> None:
    """The one shape every task-list 404 in this module has to have."""
    assert response.status_code == 404
    assert response.headers["content-type"] == PROBLEM_JSON

    body = response.json()

    assert list(body) == [*MEMBERS, "errors"]
    assert body["code"] == "task_list_not_found"
    assert body["title"] == "Task list not found"
    assert body["errors"] == {"task_list_id": str(task_list_id)}
```

Helper inventory the gate must resolve: `anonymised`, `assert_not_found`
(`test_task_lists.py:547/569`), `assert_forbidden`, `assert_user_not_found`
(`test_assignment.py:258/276`), `assert_task_not_found` (`test_tasks.py:135`),
`assert_unauthenticated`, `assert_the_body_the_status_promises`
(`test_permission_matrix.py:450/479`).

**Module-level standard statement** (`test_task_lists.py:9-14`) — the rule the sweep is enforcing
is already written down; the phase is making it true everywhere:

```python
"""Two standards apply to every test below [...] Each asserts on the **response body**, never on
the status code alone - a 201 whose body is missing a counter is a broken contract that a status
assertion cannot see. And each mutating test **re-reads through the API**, so "it was written" is
a fact about the database rather than about the return value of the handler that claimed to write
it."""
```

---

### D-04 negative-path work (transition complement + auth seeding fix)

**Transition analog** (`tests/unit/domain/test_task_status.py:44-71`) — the table is read from
the source of truth, never restated, and the self-transition leg is already a separate test:

```python
def test_transition_table_covers_every_status() -> None:
    """The table is exhaustive, so a fourth status fails loudly at the lookup."""
    assert set(ALLOWED_TRANSITIONS) == set(TaskStatus)


def test_no_status_allows_a_transition_to_itself() -> None:
    """A same-state request is an idempotent no-op on the entity, not a table entry."""
    for status, allowed in ALLOWED_TRANSITIONS.items():
        assert status not in allowed
```

**HTTP-level derivation analog** (`tests/integration/api/test_tasks.py:913-927`) — the existing
precedent for asserting a move is in the table before driving it:

```python
    """TASK-05 over HTTP: the whole lifecycle, one request per move.

    The moves are taken from `ALLOWED_TRANSITIONS` rather than from memory, so
    a change to the table turns this test red instead of leaving it asserting a
    walk the machine no longer permits.
    """
    await given_a_task(session_factory)
    client, _ = api_client
    assert TaskStatus.IN_PROGRESS in ALLOWED_TRANSITIONS[TaskStatus.PENDING]
```

`ALLOWED_TRANSITIONS` is already imported at `test_tasks.py:34` — the complement parametrization
adds no import.

**Auth parametrization to extend** (`test_auth.py:564-594`) — the closed case list and its
driver, which the D-14 fix must seed a caller into:

```python
UNAUTHENTICATED_CASES: tuple[tuple[str, HeaderBuilder], ...] = (
    ("no_header", no_header),
    ("a_basic_scheme", a_basic_scheme),
    ...
    ("a_token_for_an_unknown_subject", a_token_for_an_unknown_subject),
)


@pytest.mark.parametrize(
    "build_header",
    [build for _, build in UNAUTHENTICATED_CASES],
    ids=[name for name, _ in UNAUTHENTICATED_CASES],
)
async def test_unauthenticated_requests_are_refused_with_the_one_shared_body(
    authenticated_client: tuple[AsyncClient, FastAPI],
    build_header: HeaderBuilder,
) -> None:
```

**The seeding call to add** (`test_task_lists.py:417`, helper at `conftest.py:536-576`) — the
fix is one `session_factory` parameter plus one line. Note the `a_token_for_an_unknown_subject`
docstring (`test_auth.py:552-561`) currently *relies* on nothing being seeded, so it must keep
using a fresh `uuid.uuid4()` subject while the other six get a seeded `OWNER_ID`:

```python
    await seed(session_factory, users=[a_user()], task_lists=[a_task_list()])
```

**Optional list-deletion concurrency case** (`test_concurrent_writes.py:337-368`) — the shape to
copy if the planner takes RESEARCH's open question 2:

```python
async def test_two_list_patches_are_serialised_and_neither_edit_is_lost(
    database: _Database,
) -> None:
    first = database.unit_of_work()
    async with first:
        task_list = await visible_task_list(first, LIST_ID, OWNER_ID, for_update=True)
        second: asyncio.Task[TaskListResult] = asyncio.create_task(...)
        try:
            waited = await _until_it_waits_or_finishes(database, second)
            ...
            await first.commit()
        finally:
            outcome = await _settle(second)

    assert waited, "the second PATCH never waited for the first one"
```

The `assert waited, "<message>"` line is load-bearing: without it the outcome could be luck
(`:334` makes the same point for the task path).

---

## Shared Patterns

### The gate docstring (applies to all four new gates)

**Source:** `tests/architecture/test_no_commit_in_repositories.py:1-38`, repeated in
`test_routers_raise_no_http_exception.py:1-85`

Three fixed sections, in order: what property is being defended and why it cannot be defended
elsewhere; one or more `Deliberately NOT used:` paragraphs naming the weaker alternative and the
exact way it fails; and the no-extra-gate paragraph:

```python
"""Deliberately NOT used: a code-review habit. It enforces nothing, and SC-4 asks
for a property that is provable rather than agreed.

Deliberately NOT used: a runtime assertion that no transaction is ended during
some particular call. That would test one execution path and call it a rule -
and the paths that matter are the ones nobody thought to exercise.

This gate adds no hook to `.pre-commit-config.yaml` and no step to
`.github/workflows/ci.yml`. CLAUDE.md's two-places rule applies to a gate that
needs its own invocation; this one rides inside `pytest`, which the hook set, the
Docker test stage and CI all already run. Same argument, same outcome, as plan
02-06's stdlib check.
"""
```

Every Phase 6 gate owes that last paragraph verbatim-in-spirit (ADR-015, D-01). RESEARCH flags
that the sentence "which the hook set … already run" is inaccurate about pre-commit — the new
gates should say "the Docker test stage and CI all already run".

### Markers

**Source:** `tests/integration/api/test_task_lists.py:53` (and 16 sibling modules)
**Apply to:** the 41 unmarked modules under `tests/unit/`, `tests/architecture/`, and the moved
error-contract module

```python
pytestmark = pytest.mark.integration
```

One module-level line, placed after the module constants and before the first helper. The `unit`
side is the identical one-liner with `pytest.mark.unit`. `tests/probe.py` and
`tests/problem_details.py` are never collected and take no marker.

### Non-vacuity, everywhere

**Source:** `test_no_commit_in_repositories.py:71-83`, `test_layer_boundaries.py:27-45`,
`test_security_scheme.py:157`
**Apply to:** every new gate, including the OpenAPI one and the coverage-config one

Every scan, glob, document read and config parse is preceded by an assertion that it found
something, and — where a name list exists — that the required names are a subset of what was
found. The comment that accompanies it is itself conventional: *"A glob that matches nothing
passes vacuously; assert it matched the tree … green forever, checking nothing, which is worse
than no gate at all."*

### Type annotations and lint scope

**Source:** `Makefile:typecheck` → `$(VENV)/bin/mypy src tests`; `.flake8` carries bugbear
**Apply to:** every new module, conftest hook and helper

`mypy --strict` covers `tests/` too. Annotate hooks explicitly (`config: pytest.Config`,
`items: list[pytest.Item]`) and the ASGI wrapper with `Scope`, `Receive`, `Send` from
`starlette.types`. Existing signatures to copy: `def _location(path: Path, node: ast.AST) -> str`,
`async def api_client(...) -> AsyncIterator[tuple[AsyncClient, FastAPI]]`,
`def run_in(directory: Path) -> subprocess.CompletedProcess[str]`.

### Documentation artifacts

**Source:** `AI_WORKFLOW.md:299-326` (incident entry) and `DECISION_LOG.md:3563-3600` (ADR-084)
**Apply to:** the break-check episode (D-10) and any new gate's ADR (D-15, discretion item)

Incident-log entry: `### YYYY-MM-DD — <one-sentence finding in the past tense>`, then
`**What happened.**`, then a named sub-heading per sub-episode, with fenced terminal output
captured verbatim including the exit code:

```markdown
### 2026-09-17 — Proving the gates actually fire

**What happened.** Both of this phase's two substantive gates were deliberately driven red
before being trusted, and the terminal output was captured. A gate that has never been observed
failing is indistinguishable from a no-op.
```

ADR: `## ADR-0NN: <lowercase statement of the decision>` then `**Context**`, `**Options**`
(bulleted, each with the reason it was rejected inline), `**Decision**`, `**Consequences**`
(bulleted, each starting with a bold clause). Next free number is **ADR-085**.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `tests/conftest.py` unmarked-item guard (`pytest_collection_modifyitems`) | collection hook | collection-time | No `pytest_collection_modifyitems` hook exists anywhere in the repo today — this phase introduces the first two (the guard here and the ordering hook in `tests/integration/conftest.py`). Use RESEARCH §D-13/§D-03 for the mechanism, and the non-vacuity/offender-reporting idioms above for the failure message: report the offending node ids, not a count. |

## Metadata

**Analog search scope:** `tests/architecture/`, `tests/unit/`, `tests/integration/`,
`tests/integration/api/`, `tests/api/`, `tests/probe.py`, `tests/conftest.py`, `scripts/`,
`Makefile`, `pytest.ini`, `AI_WORKFLOW.md`, `DECISION_LOG.md`
**Files read in this pass:** 16 (4 fully, 12 targeted ranges)
**Pattern extraction date:** 2026-09-19
