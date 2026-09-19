"""D-05: every HTTP test asserts something beyond the status code.

`tests/integration/api/test_task_lists.py` opens by stating two standards that
apply to every test in this suite: each asserts on the **response body**, never
on the status code alone, and each mutating test **re-reads through the API**. A
201 whose body is missing a counter is a broken contract a status assertion
cannot see, and a handler that answers 200 while persisting nothing is invisible
to one too. Both standards were written down in Phase 4 and neither was enforced,
so this module makes them properties of the tree rather than habits of whoever
last edited it.

Half (a) lives here. A test that drives the API through a client fixture must
contain at least one assertion that is not about the status code, where
"something beyond the status code" is any of four AST-decidable shapes:

* an assertion naming `.json()`, `.headers`, `.text` or `.content`;
* an assertion on a name tainted from a response - `body = response.json()`
  followed by `assert body[...]`, which is the dominant shape in this suite and
  the reason a literal scan is useless here;
* a call to one of the named `Response`-taking helpers this suite already uses
  (`anonymised`, `assert_not_found`, `assert_forbidden`, ...), resolved both
  same-file **and across modules** - `anonymised` is defined in
  `test_task_lists.py` and imported by `test_auth.py`, so without the
  cross-module hop the gate reports a false positive on a good test;
* an assertion naming a recorded side-effect fixture the test declares
  (`caplog`, `statements`) - the notification tests assert on a log record and
  the statement recorder asserts on emitted SQL, and in both cases the response
  body is genuinely not the behaviour under test.

There is no per-test opt-out for this half, which is D-07's rule and is only
affordable because the rule above is stated correctly. Half (b), the re-read
rule, has one - a registered marker, gated three ways - because a handful of
tests provably have nothing to read back.

Deliberately NOT used: the naive scan - "a test mentioning `.status_code` with no
literal `.json()` inside an `assert`". It was prototyped in 06-RESEARCH.md and
reports **29** offenders, of which **one** is real. A gate with a 28-to-1 false
positive rate does not get fixed; it gets an `# noqa`, a blanket skip, or
deleted, and the property it was defending goes with it. The taint-tracking and
the helper resolution are not refinements of that scan - they are what makes the
difference between a rule and a nuisance.

Deliberately NOT used: a global set of every `Response`-taking helper name found
anywhere under `tests/`. It would resolve the cross-module case for free and
would also accept a module that calls a helper it never imported, which is a
`NameError` at run time and a green gate here. The resolution is per-module -
same-file definitions plus what an `ImportFrom` actually binds - so removing the
import hop turns the gate red on a real test rather than leaving it silently
weaker.

Deliberately NOT used: a runtime check, a `pytest` hook that inspects assertions
as they run, or a coverage-based proxy. All three report on the tests that ran;
the property is about the tests that exist, including the one someone adds next
week and runs once.

The gate's own detection logic is proved against planted source on every run, at
the end of this module. Plan 06-01 shipped a gate that passed while proving
nothing - its non-vacuity guard satisfied its own scan - and the lesson taken
from it is that a gate's rules have to be tested like any other code, not merely
driven red once by hand on the day they were written.

This gate adds no hook to `.pre-commit-config.yaml` and no step to
`.github/workflows/ci.yml`. CLAUDE.md's two-places rule applies to a gate that
needs its own invocation; this one rides inside `pytest`, which the Docker test
stage and CI all already run. Same argument, same outcome, as plans 02-06, 03-06
and 06-01.
"""

import ast
from pathlib import Path
from typing import Final

import pytest

# tests/architecture/test_assertion_quality.py -> tests/architecture -> tests.
TESTS: Final[Path] = Path(__file__).resolve().parents[1]

# The suite this gate governs: the modules that drive the published API. Other
# modules under `tests/` build throwaway applications - a probe router that only
# raises, a health endpoint with a stubbed driver - and their "resources" are
# fixtures rather than rows, so the two standards this module enforces do not
# translate. Those applications are covered by the modules that own them.
HTTP_TESTS: Final[Path] = TESTS / "integration" / "api"

# Named rather than counted, the convention every gate in this repo follows.
# A renamed, moved or emptied module fails the guard below instead of leaving
# the real test asserting that nothing is nothing. A new HTTP module adds its
# name here in the same commit that creates it.
REQUIRED_SCANNED_TEST_MODULES: Final[frozenset[str]] = frozenset(
    {
        "test_assignment.py",
        "test_auth.py",
        "test_permission_matrix.py",
        "test_statements.py",
        "test_task_lists.py",
        "test_tasks.py",
        "test_users.py",
    }
)

# The client fixtures this suite hands out, named for non-vacuity only: the scan
# below identifies a client parameter by its *annotation*, so a fixture renamed
# tomorrow is still found. This set exists so that a change which stopped the
# discovery working altogether - a moved conftest, a rewritten annotation - fails
# here rather than quietly reducing the scan to nothing.
REQUIRED_CLIENT_FIXTURES: Final[frozenset[str]] = frozenset(
    {"api_client", "authenticated_client", "matrix_client"}
)

# The type whose presence in an annotation makes a parameter a client.
CLIENT_TYPE: Final[str] = "AsyncClient"

# The type a helper takes when it carries the body assertions for its callers.
RESPONSE_TYPE: Final[str] = "Response"

# What a response object can be asked for that is not its status code. These are
# the members an assertion has to reach for the test to be asserting on the
# answer rather than on the envelope.
BODY_MEMBERS: Final[frozenset[str]] = frozenset({"json", "headers", "text", "content"})

# Fixtures that record a side effect the API produced without returning it. A
# test whose subject is the log record or the SQL statement asserts on these
# instead of on a body, and that is the behaviour under test rather than a hole:
# `test_assignment.py`'s notification tests and `test_statements.py`'s recorder.
# Named, and each name earns its place by being a real fixture some test takes.
RECORDER_FIXTURES: Final[frozenset[str]] = frozenset({"caplog", "statements"})

# The HTTP verbs a client is asked for. `get` is separated out because half (b)
# needs it by itself: it is the only one that proves an end state.
READ_VERB: Final[str] = "get"
MUTATING_VERBS: Final[frozenset[str]] = frozenset({"post", "put", "patch", "delete"})
REQUEST_VERBS: Final[frozenset[str]] = MUTATING_VERBS | {
    READ_VERB,
    "head",
    "options",
    "request",
}

pytestmark = pytest.mark.unit


def _relative(path: Path) -> str:
    return path.relative_to(TESTS.parent).as_posix()


def _parsed(path: Path) -> ast.Module:
    """The module's syntax tree, with the filename kept for the error text."""
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _test_modules() -> list[Path]:
    """Every module under the scanned package, in a stable order."""
    return sorted(HTTP_TESTS.rglob("test_*.py"))


def _functions(tree: ast.AST) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    ]


def _annotation(node: ast.arg) -> str:
    """The parameter's annotation as source text, or the empty string."""
    return "" if node.annotation is None else ast.unparse(node.annotation)


def _is_a_fixture(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Whether the definition carries a `fixture` decorator, however spelled."""
    return any(
        ast.unparse(decorator).split("(")[0].split(".")[-1] == "fixture"
        for decorator in node.decorator_list
    )


def client_fixture_names() -> frozenset[str]:
    """Every fixture under `tests/` that yields or returns a client.

    Discovered from the return annotation rather than listed, so
    `AsyncIterator[AsyncClient]` and `AsyncIterator[tuple[AsyncClient, FastAPI]]`
    are both found and a fixture added later joins the scan without editing it.
    """
    return frozenset(
        node.name
        for path in sorted(TESTS.rglob("*.py"))
        for node in _functions(_parsed(path))
        if _is_a_fixture(node)
        and node.returns is not None
        and CLIENT_TYPE in ast.unparse(node.returns)
    )


def response_helpers(tree: ast.Module) -> frozenset[str]:
    """The names of functions in this tree that take a `Response` parameter.

    These are the suite's named helpers - `assert_not_found`, `anonymised`,
    `assert_the_body_the_status_promises` - each of which carries the body
    assertions its callers would otherwise inline.
    """
    return frozenset(
        node.name
        for node in _functions(tree)
        for argument in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
        if RESPONSE_TYPE in _annotation(argument)
    )


def _imported_module_path(node: ast.ImportFrom) -> Path | None:
    """The file a `from tests.x.y import ...` names, if it is one of ours."""
    module = node.module or ""
    if node.level or not module.startswith("tests."):
        return None
    candidate = TESTS.parent / Path(*module.split(".")).with_suffix(".py")
    return candidate if candidate.is_file() else None


def resolvable_helpers(
    tree: ast.Module, *, cross_module: bool = True
) -> frozenset[str]:
    """Every `Response`-taking helper name this module can actually call.

    Same-file definitions, plus whatever an `ImportFrom` binds from another
    module under `tests/` - under the local name, so an alias resolves too. The
    `cross_module` switch exists for the self-test that proves the second half is
    load-bearing: with it off, a good test in `test_auth.py` becomes an offender.
    """
    names = set(response_helpers(tree))
    if not cross_module:
        return frozenset(names)
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        path = _imported_module_path(node)
        if path is None:
            continue
        exported = response_helpers(_parsed(path))
        names.update(
            alias.asname or alias.name for alias in node.names if alias.name in exported
        )
    return frozenset(names)


def _client_parameters(node: ast.FunctionDef | ast.AsyncFunctionDef) -> frozenset[str]:
    """The parameters through which this function reaches the API."""
    return frozenset(
        argument.arg
        for argument in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
        if CLIENT_TYPE in _annotation(argument)
    )


def client_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> frozenset[str]:
    """Every local name in this test that is a client.

    The parameters themselves, plus the first element of any tuple unpacking of
    one: `api_client` and `authenticated_client` yield a `(client, app)` pair, so
    `client, _ = api_client` is what binds the object the requests go through,
    and a scan that only knew the parameter name would see no requests at all.
    """
    names = set(_client_parameters(node))
    for statement in ast.walk(node):
        if not isinstance(statement, ast.Assign):
            continue
        if not isinstance(statement.value, ast.Name) or statement.value.id not in names:
            continue
        for target in statement.targets:
            if isinstance(target, ast.Tuple) and target.elts:
                first = target.elts[0]
                if isinstance(first, ast.Name):
                    names.add(first.id)
    return frozenset(names)


def requests_made(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[tuple[str, int]]:
    """Every request this test issues, as `(verb, line)` in source order."""
    clients = client_names(node)
    return sorted(
        (child.func.attr, child.func.value.lineno)
        for child in ast.walk(node)
        if isinstance(child, ast.Call)
        and isinstance(child.func, ast.Attribute)
        and child.func.attr in REQUEST_VERBS
        and isinstance(child.func.value, ast.Name)
        and child.func.value.id in clients
    )


def http_tests(
    tree: ast.AST,
) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    """Every test function in this tree that issues a request through a client.

    Declaring a client fixture is not enough, and the difference is not
    pedantic: `test_permission_matrix.py` has a test that takes
    `authenticated_client` only to reach the `app` half of the two-tuple and
    then compares the published document against the table. It drives no
    request, has no response to assert on, and belongs in neither half of this
    gate.
    """
    return [
        node
        for node in _functions(tree)
        if node.name.startswith("test_") and requests_made(node)
    ]


def _reaches_into_a_response(node: ast.AST) -> bool:
    """Whether this expression asks a response for anything but its status."""
    return any(
        isinstance(child, ast.Attribute) and child.attr in BODY_MEMBERS
        for child in ast.walk(node)
    )


def _names_in(node: ast.AST) -> frozenset[str]:
    return frozenset(
        child.id for child in ast.walk(node) if isinstance(child, ast.Name)
    )


def _calls_in(node: ast.AST) -> frozenset[str]:
    """The local name of every function called in this subtree."""
    return frozenset(
        child.func.id
        for child in ast.walk(node)
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Name)
    )


def _assigned_names(target: ast.expr) -> frozenset[str]:
    """The names an assignment target binds.

    A subscript contributes its *base* - `bodies[name] = ...` binds `bodies` and
    says nothing about `name` - which keeps the taint below from spreading
    through whatever happened to be used as a key.
    """
    if isinstance(target, ast.Name):
        return frozenset({target.id})
    if isinstance(target, ast.Tuple | ast.List):
        return frozenset().union(*(_assigned_names(item) for item in target.elts))
    if isinstance(target, ast.Starred):
        return _assigned_names(target.value)
    if isinstance(target, ast.Subscript):
        return _assigned_names(target.value)
    return frozenset()


def _declared_recorders(node: ast.FunctionDef | ast.AsyncFunctionDef) -> frozenset[str]:
    """The recorder fixtures this test actually takes as parameters."""
    return RECORDER_FIXTURES & {
        argument.arg
        for argument in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
    }


def _assignments(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[tuple[frozenset[str], ast.expr]]:
    pairs: list[tuple[frozenset[str], ast.expr]] = []
    for statement in ast.walk(node):
        if isinstance(statement, ast.Assign):
            bound = frozenset().union(
                *(_assigned_names(target) for target in statement.targets)
            )
            pairs.append((bound, statement.value))
        if isinstance(statement, ast.AnnAssign) and statement.value is not None:
            pairs.append((_assigned_names(statement.target), statement.value))
        if isinstance(statement, ast.NamedExpr):
            pairs.append((_assigned_names(statement.target), statement.value))
    return pairs


def tainted_names(
    node: ast.FunctionDef | ast.AsyncFunctionDef, helpers: frozenset[str]
) -> frozenset[str]:
    """Every local name that carries something the API said.

    Three sources: a response member (`body = response.json()`), a recorder
    fixture the test declares (`sent = notifications(caplog)`), and a call to
    one of the suite's `Response`-taking helpers (`bodies[n] = anonymised(r)`).
    Propagated to a fixed point, because the suite chains them:
    `sent = notifications(caplog)` then `fields = extras(sent[0])` then
    `assert fields["event"] == ...` - three statements, and only the first names
    anything this scan recognises on its own.
    """
    tainted = set(_declared_recorders(node))
    assignments = _assignments(node)
    while True:
        grown = False
        for bound, value in assignments:
            if bound <= tainted:
                continue
            if (
                _reaches_into_a_response(value)
                or _calls_in(value) & helpers
                or _names_in(value) & tainted
            ):
                tainted |= bound
                grown = True
        if not grown:
            return frozenset(tainted)


def _location(path: Path, node: ast.AST) -> str:
    """`file:line`, so a failure names the test rather than the rule alone."""
    return f"{_relative(path)}:{getattr(node, 'lineno', '?')}"


def _asserts_more_than_a_status(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    helpers: frozenset[str],
) -> bool:
    """The rule: one of the four shapes the module docstring enumerates."""
    if _calls_in(node) & helpers:
        return True
    tainted = tainted_names(node, helpers)
    return any(
        _reaches_into_a_response(statement.test) or _names_in(statement.test) & tainted
        for statement in ast.walk(node)
        if isinstance(statement, ast.Assert)
    )


def status_only_offenders(
    path: Path, tree: ast.Module, *, cross_module: bool = True
) -> list[str]:
    """`file:line` for every HTTP test that asserts nothing but a status code."""
    helpers = resolvable_helpers(tree, cross_module=cross_module)
    return [
        _location(path, node)
        for node in http_tests(tree)
        if not _asserts_more_than_a_status(node, helpers)
    ]


def test_the_http_suite_is_actually_scanned() -> None:
    """A glob that matches nothing passes vacuously; assert it matched the tree.

    Without this guard a moved package or a typo in `HTTP_TESTS` would leave the
    gate below asserting that an empty list is empty - green forever, checking
    nothing, which is worse than no gate at all. The module set is a subset
    check, so adding an HTTP module does not require editing this file; removing
    one does, which is the case the guard exists for.
    """
    scanned = {path.name for path in _test_modules()}

    assert scanned
    assert REQUIRED_SCANNED_TEST_MODULES <= scanned


def test_the_client_fixtures_are_still_discoverable() -> None:
    """The discovery, not a list, is what the scan depends on - so prove it works.

    `REQUIRED_CLIENT_FIXTURES` is a subset check on the *discovered* set. If the
    annotation-based discovery ever stopped working, every test below would find
    no client parameters and report no offenders.
    """
    discovered = client_fixture_names()

    assert REQUIRED_CLIENT_FIXTURES <= discovered


def test_the_scan_finds_the_http_tests_it_governs() -> None:
    """The second half of non-vacuity: the tests themselves, not just the files."""
    found = {
        node.name for path in _test_modules() for node in http_tests(_parsed(path))
    }

    assert len(found) > 100, f"only {len(found)} HTTP tests discovered"


def test_no_http_test_asserts_only_a_status_code() -> None:
    """Half (a) of D-05: a status code is an envelope, not an answer."""
    offenders = [
        offender
        for path in _test_modules()
        for offender in status_only_offenders(path, _parsed(path))
    ]

    assert offenders == [], (
        "Every test that drives the API must assert on something the API "
        "actually said: a body member, a name tainted from one, a named "
        "Response-taking helper, or a recorded side effect it declares. A 201 "
        "whose body is missing a counter, or a 200 that persisted nothing, is a "
        "broken contract no status assertion can see (D-05, TEST-05). Offending "
        f"tests: {offenders}"
    )


_TASK_LISTS = HTTP_TESTS / "test_task_lists.py"


def _status_only_in(source: str, *, cross_module: bool = True) -> list[str]:
    """The half (a) offenders in a planted snippet, as `file:line`."""
    return status_only_offenders(
        HTTP_TESTS / "planted.py", ast.parse(source), cross_module=cross_module
    )


_A_STATUS_ONLY_TEST = (
    "async def test_planted(api_client: tuple[AsyncClient, FastAPI]) -> None:\n"
    "    client, _ = api_client\n"
    "    response = await client.get('/x')\n"
    "    assert response.status_code == 200\n"
)


def test_the_rule_catches_a_status_only_test() -> None:
    """The one shape the gate exists to refuse."""
    assert _status_only_in(_A_STATUS_ONLY_TEST) == [
        "tests/integration/api/planted.py:1"
    ]


def test_a_test_with_no_client_is_not_in_scope() -> None:
    """The scan governs tests that drive the API, and nothing else."""
    assert (
        _status_only_in(
            "def test_planted(session_factory: SessionFactory) -> None:\n"
            "    assert True\n"
        )
        == []
    )


def test_a_tainted_body_name_satisfies_the_rule() -> None:
    """The dominant shape in this suite, and the reason a literal scan is useless."""
    assert (
        _status_only_in(
            "async def test_planted(api_client: tuple[AsyncClient, FastAPI]) -> None:\n"
            "    client, _ = api_client\n"
            "    response = await client.get('/x')\n"
            "    assert response.status_code == 200\n"
            "    body = response.json()\n"
            "    assert body['name'] == 'Groceries'\n"
        )
        == []
    )


def test_an_unrelated_local_name_does_not_satisfy_the_rule() -> None:
    """Taint is tracked, not assumed: a name assigned from nothing proves nothing."""
    assert _status_only_in(
        "async def test_planted(api_client: tuple[AsyncClient, FastAPI]) -> None:\n"
        "    client, _ = api_client\n"
        "    response = await client.get('/x')\n"
        "    assert response.status_code == 200\n"
        "    expected = 'Groceries'\n"
        "    assert expected == 'Groceries'\n"
    ) == ["tests/integration/api/planted.py:1"]


def test_a_same_file_response_helper_satisfies_the_rule() -> None:
    """The named-helper convention, resolved where it is defined."""
    assert (
        _status_only_in(
            "def assert_not_found(response: Response, list_id: uuid.UUID) -> None:\n"
            "    assert response.json()['code'] == 'task_list_not_found'\n"
            "async def test_planted(api_client: tuple[AsyncClient, FastAPI]) -> None:\n"
            "    client, _ = api_client\n"
            "    response = await client.get('/x')\n"
            "    assert_not_found(response, LIST_ID)\n"
        )
        == []
    )


def test_a_helper_imported_from_another_test_module_satisfies_the_rule() -> None:
    """The cross-module hop, and the proof that it is load-bearing.

    `anonymised` is defined in `test_task_lists.py` and imported by
    `test_auth.py`. With the import resolution off, the identical snippet is an
    offender - which is exactly the false positive 06-RESEARCH.md measured and
    the reason the resolution is not decorative.
    """
    source = (
        "from tests.integration.api.test_task_lists import anonymised\n"
        "async def test_planted(api_client: tuple[AsyncClient, FastAPI]) -> None:\n"
        "    client, _ = api_client\n"
        "    response = await client.get('/x')\n"
        "    assert anonymised(response, LIST_ID) == anonymised(response, LIST_ID)\n"
    )

    assert _status_only_in(source) == []
    assert _status_only_in(source, cross_module=False) == [
        "tests/integration/api/planted.py:2"
    ]


def test_an_import_of_a_name_that_is_not_a_helper_resolves_to_nothing() -> None:
    """The cross-module hop binds helpers, not every name a module exports."""
    assert _status_only_in(
        "from tests.integration.api.test_task_lists import a_user\n"
        "async def test_planted(api_client: tuple[AsyncClient, FastAPI]) -> None:\n"
        "    client, _ = api_client\n"
        "    response = await client.get('/x')\n"
        "    assert a_user(response) is not None\n"
    ) == ["tests/integration/api/planted.py:2"]


def test_a_recorded_side_effect_satisfies_the_rule() -> None:
    """A log record is an observation of the API, and is what those tests assert."""
    assert (
        _status_only_in(
            "async def test_planted(\n"
            "    api_client: tuple[AsyncClient, FastAPI],\n"
            "    caplog: pytest.LogCaptureFixture,\n"
            ") -> None:\n"
            "    client, _ = api_client\n"
            "    response = await client.put('/x')\n"
            "    assert response.status_code == 200\n"
            "    assert caplog.records[0].event == 'assigned'\n"
        )
        == []
    )


def test_a_recorder_the_test_does_not_declare_satisfies_nothing() -> None:
    """The fixture has to be the test's own, or the name is just a name."""
    assert _status_only_in(
        "async def test_planted(api_client: tuple[AsyncClient, FastAPI]) -> None:\n"
        "    client, _ = api_client\n"
        "    response = await client.put('/x')\n"
        "    assert response.status_code == 200\n"
        "    assert caplog.records == []\n"
    ) == ["tests/integration/api/planted.py:1"]


def test_the_real_helpers_are_found_where_the_suite_defines_them() -> None:
    """The helper inventory, pinned against the tree rather than against a list.

    If `anonymised` or `assert_not_found` were renamed, or lost their `Response`
    annotation, the resolution above would silently stop accepting their callers
    and the gate would start reporting false positives - which is how a gate
    gets weakened. This fails first instead.
    """
    helpers = response_helpers(_parsed(_TASK_LISTS))

    assert {"anonymised", "assert_not_found"} <= helpers
