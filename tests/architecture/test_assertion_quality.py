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
affordable because the rule above is stated correctly.

Half (b) is the second standard: a test that issues POST, PUT, PATCH or DELETE
through a client must read the resource back with a `client.get(...)` **after**
its last mutation. The "after" carries the rule - the rejected-mutation leg
captures `before` with a read above the mutation and asserts `after == before`
below it, and a check that accepted any read anywhere would count the `before`
and let the half that actually says "unchanged" go missing.

A mutation is recognised by the verb, not by the attribute name. `client.post`
says it outright; the generic `client.request(...)` carries its verb as the first
positional argument or as a `method=` keyword, and it is resolved from there when
that argument is a string literal, so `request("GET", ...)` is a read and
`request("DELETE", ...)` is a mutation. A verb the gate **cannot** read - an
expression, a name, an unrecognised spelling - is treated as a mutation. That
asymmetry is the lesson of WR-02: half (b) matched the attribute name alone, so
`test_permission_matrix.py`, which issues every one of a seventy-six-cell
table's mutations through `client.request(cell.row.method, ...)`, sat entirely
outside the rule while this gate reported zero offenders. A non-literal verb
must never be a way *out* of the gate (ADR-096).

Half (b) has an escape hatch, because ten tests provably have nothing a `GET`
can observe: `POST /auth/login` mutates no resource, and the five notification
tests assert on a log record no route publishes. It is `@pytest.mark.no_reread`
and it is gated three ways so it cannot become a blanket skip: the reason must
be a non-empty string literal; the test's node id must appear in
`REQUIRED_NO_REREAD` below, so granting an exemption means editing this file in
the same commit; and a companion test fails if a listed id disappears, loses its
marker, loses its reason, *or stops needing the exemption at all* - if someone
adds a re-read to an exempted test, the entry becomes a hole with no reason left
and the gate says so.

Deliberately NOT used: a blanket `skip`, a file-level opt-out, or a
`# type: ignore`-style inline comment. All three are exemptions that never have
to justify themselves again, and an exemption nobody has to re-earn is a hole
rather than a rule (D-07). The precedent is `EXEMPT_MODULES` in
`test_routers_raise_no_http_exception.py`, whose companion test fails when its
one exemption outlives its reason; this marker copies that shape and adds the
fourth assertion, that the exemption is still *needed*.

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
import copy
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

# The marker that exempts a test from half (b), registered in `pytest.ini`
# because `--strict-markers` is on. Half (a) has no marker and never will.
MARKER_NAME: Final[str] = "no_reread"

# The whole of half (b)'s escape hatch, named. A marker on a test absent from
# this set fails the gate, so granting an exemption means editing this file in
# the same commit - exactly as `EXPECTED_CONTRACT_NAMES` and
# `REQUIRED_SCANNED_MODULES` already work. Each entry carries the reason no
# `GET` can observe it, and `test_every_registered_exemption_still_needs_it`
# fails the moment one of them stops being true.
REQUIRED_NO_REREAD: Final[frozenset[str]] = frozenset(
    {
        # POST /auth/login mutates nothing at all: there is no resource a GET
        # could read back. Three of the five register an account first, and that
        # register is setup rather than the subject - its persistence is proved
        # by `test_register_then_login_then_get_me_reads_back_the_same_profile`,
        # and in two of the three the successful login *is* the read, which this
        # gate cannot see because a login is spelled as a POST.
        "tests/integration/api/test_auth.py"
        "::test_login_answers_a_bearer_token_and_the_configured_lifetime",
        "tests/integration/api/test_auth.py"
        "::test_login_without_a_password_is_422_and_does_not_echo_the_username",
        "tests/integration/api/test_auth.py"
        "::test_login_with_an_unknown_address_and_with_a_wrong_password_"
        "are_indistinguishable",
        "tests/integration/api/test_auth.py"
        "::test_login_with_an_unstorable_username_is_the_same_401",
        "tests/integration/api/test_permission_matrix.py"
        "::test_login_refuses_a_bad_credential_from_an_anonymous_caller",
        # The five notification tests. Their subject is the log record the
        # adapter emits, which no route publishes; the assignment's persistence
        # is proved next door by
        # `test_a_notifier_failure_leaves_the_assignment_committed` and by the
        # four assign/unassign tests that do re-read.
        "tests/integration/api/test_assignment.py"
        "::test_assigning_notifies_the_new_assignee_with_one_structured_record",
        "tests/integration/api/test_assignment.py"
        "::test_the_notification_renders_as_one_parseable_json_line",
        "tests/integration/api/test_assignment.py"
        "::test_a_title_carrying_a_newline_still_notifies_on_a_single_line",
        "tests/integration/api/test_assignment.py"
        "::test_assigning_the_same_user_again_notifies_nobody",
        "tests/integration/api/test_assignment.py::test_unassigning_notifies_nobody",
    }
)

# The HTTP verbs a client is asked for. `get` is separated out because half (b)
# needs it by itself: it is the only one that proves an end state.
READ_VERB: Final[str] = "get"
MUTATING_VERBS: Final[frozenset[str]] = frozenset({"post", "put", "patch", "delete"})

# `client.request(<verb>, ...)` - the generic call, whose verb is an argument
# rather than the attribute name. It is resolved when the argument is a literal
# this module recognises, and otherwise stands for "could be any verb", which
# half (b) treats as **mutating**. An unreadable verb must never be a way *out*
# of the gate: that is exactly how a seventy-six-cell table driven entirely
# through `client.request(cell.row.method, ...)` sat outside the re-read rule
# while this gate reported zero offenders (WR-02, ADR-096).
UNRESOLVED_VERB: Final[str] = "request"

REQUEST_VERBS: Final[frozenset[str]] = MUTATING_VERBS | {
    READ_VERB,
    "head",
    "options",
    UNRESOLVED_VERB,
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


def _verb_of(call: ast.Call, attribute: str) -> str:
    """The verb this call issues, which is not always the attribute name.

    `client.post(...)` says it in the attribute and returns unchanged. The
    generic `client.request(...)` carries its verb as the first positional
    argument, or as a `method=` keyword, and is resolved when that argument is a
    string literal this module recognises - so `request("GET", ...)` really is a
    read and `request("DELETE", ...)` really is a mutation.

    Anything else - an expression, an f-string, a name, a spelling that is not
    one of `REQUEST_VERBS` - is unreadable, and an unreadable verb stays
    `UNRESOLVED_VERB`, which half (b) treats as mutating. The asymmetry is
    deliberate: a wrongly-mutating classification costs a re-read that was
    already the standard, and a wrongly-reading one is a hole (WR-02).
    """
    if attribute != UNRESOLVED_VERB:
        return attribute
    method: ast.expr | None = call.args[0] if call.args else None
    if method is None:
        method = next(
            (keyword.value for keyword in call.keywords if keyword.arg == "method"),
            None,
        )
    if isinstance(method, ast.Constant) and isinstance(method.value, str):
        spelled = method.value.lower()
        if spelled in REQUEST_VERBS:
            return spelled
    return UNRESOLVED_VERB


def _mutates(verb: str) -> bool:
    """Whether a request with this verb may have changed something.

    The four named verbs, plus the unresolved one: a `request(...)` whose method
    the gate cannot read could be any of them.
    """
    return verb in MUTATING_VERBS or verb == UNRESOLVED_VERB


def requests_made(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[tuple[str, int]]:
    """Every request this test issues, as `(verb, line)` in source order.

    The verb is resolved through `_verb_of`, so a `client.request(...)` is
    classified by the method it was given rather than by the attribute name.
    Membership in `REQUEST_VERBS` is still tested on the attribute, so a call to
    an unrelated method of a client is still not a request.
    """
    clients = client_names(node)
    return sorted(
        (_verb_of(child, child.func.attr), child.func.value.lineno)
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


def _node_id(path: Path, node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """`file::test`, the address a reader can paste straight into `pytest`.

    The parametrized form (`...[case]`) is deliberately not used: this gate reads
    source rather than collected items, and an exemption is about the test
    function, never about one of its cases. A marker on a parametrized test
    exempts every case, which is the honest reading of the marker anyway.
    """
    return f"{_relative(path)}::{node.name}"


def _no_reread_decorators(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[ast.expr]:
    """Every decorator on this test that is the exemption marker.

    Matched on the last dotted segment, so `@pytest.mark.no_reread` and a
    `from pytest import mark` spelling both resolve, and a bare
    `@pytest.mark.no_reread` with no call is *found* rather than ignored - which
    is what lets the reason check below report it instead of a marker with no
    reason quietly passing as no marker at all.
    """
    return [
        decorator
        for decorator in node.decorator_list
        if ast.unparse(decorator).split("(")[0].split(".")[-1] == MARKER_NAME
    ]


def _reason(decorator: ast.expr) -> str | None:
    """The marker's reason, if it is a non-empty string literal."""
    if not isinstance(decorator, ast.Call) or not decorator.args:
        return None
    first = decorator.args[0]
    if not isinstance(first, ast.Constant) or not isinstance(first.value, str):
        return None
    return first.value or None


def marked_tests(
    path: Path, tree: ast.Module
) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    """Every test in this tree carrying the exemption marker, by node id."""
    return {
        _node_id(path, node): node
        for node in _functions(tree)
        if node.name.startswith("test_") and _no_reread_decorators(node)
    }


def reason_offenders(path: Path, tree: ast.Module) -> list[str]:
    """`file:line` for every marker whose reason is missing or empty.

    The first of the three gates on the escape hatch. A marker applied bare, or
    with `""`, or with a name instead of a literal, is a blanket skip wearing a
    justification's clothes.
    """
    return [
        _location(path, node)
        for node in _functions(tree)
        for decorator in _no_reread_decorators(node)
        if _reason(decorator) is None
    ]


def no_reread_offenders(path: Path, tree: ast.Module) -> list[str]:
    """`file:line` for every mutating test that never reads its change back.

    A test is an offender when it issues POST, PUT, PATCH or DELETE through a
    client and no `client.get(...)` appears *after* its last mutation. The
    "after" is the whole point: the rejected-mutation leg captures `before` with
    a read above the mutation, and a gate that accepted any read anywhere would
    count that one and let the `after == before` half go missing - which is the
    only half that says the resource is unchanged.

    A mutation issued through the generic `client.request(...)` counts too: the
    verb is resolved from the call's first argument or its `method=` keyword, and
    a verb the gate cannot read is treated as mutating rather than as nothing
    (ADR-096).
    """
    offenders = []
    for node in http_tests(tree):
        if _no_reread_decorators(node):
            continue
        requests = requests_made(node)
        mutations = [line for verb, line in requests if _mutates(verb)]
        if not mutations:
            continue
        reads = [line for verb, line in requests if verb == READ_VERB]
        if reads and max(reads) > max(mutations):
            continue
        offenders.append(_location(path, node))
    return offenders


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


def test_no_mutating_test_leaves_its_change_unread() -> None:
    """Half (b) of D-06: "it was written" is a fact about the database."""
    offenders = [
        offender
        for path in _test_modules()
        for offender in no_reread_offenders(path, _parsed(path))
    ]

    assert offenders == [], (
        "Every test that mutates through the API must read the resource back "
        "with a GET after its last mutation, so that the change is a fact about "
        "the database rather than about the return value of the handler that "
        "claimed to make it. A rejected mutation proves the resource is "
        "unchanged; a successful one proves the end state; a DELETE proves the "
        "404. If no GET can observe it, mark the test "
        f"@pytest.mark.{MARKER_NAME}(...) and register it in "
        f"REQUIRED_NO_REREAD (D-06, D-07). Offending tests: {offenders}"
    )


def test_every_exemption_marker_carries_a_non_empty_reason() -> None:
    """Gate one of three on the escape hatch: a reason, in English, per test."""
    offenders = [
        offender
        for path in _test_modules()
        for offender in reason_offenders(path, _parsed(path))
    ]

    assert offenders == [], (
        f"@pytest.mark.{MARKER_NAME} takes one argument: a non-empty string "
        "literal saying why no GET can observe this test's mutation. A bare "
        "marker, an empty string or a name instead of a literal is a blanket "
        f"skip wearing a justification's clothes (D-07). Offenders: {offenders}"
    )


def test_every_exemption_marker_is_registered_in_this_module() -> None:
    """Gate two of three: the marker and the frozenset move in one commit.

    Compared as an equality in both directions. A marker added to a test that is
    not listed here is an exemption granted without anyone editing the gate; an
    id listed here whose test no longer carries the marker is a stale entry, and
    no weaker comparison catches the second.
    """
    marked = {
        node_id
        for path in _test_modules()
        for node_id in marked_tests(path, _parsed(path))
    }

    assert marked == REQUIRED_NO_REREAD


def test_every_registered_exemption_still_needs_it() -> None:
    """Gate three of three: an exemption cannot outlive its reason.

    Four things are asserted about every entry, and the fourth is the one the
    analog in `test_routers_raise_no_http_exception.py` does not have: the test
    must still be an offender *without* its marker. If a re-read is ever added to
    an exempted test - which would be an improvement - the entry becomes a hole
    with no reason left, and this fails until it is removed.
    """
    assert REQUIRED_NO_REREAD

    found: dict[str, str] = {}
    for path in _test_modules():
        tree = _parsed(path)
        unmarked = no_reread_offenders(path, _strip_markers(tree))
        for node_id, node in marked_tests(path, tree).items():
            reasons = [_reason(one) for one in _no_reread_decorators(node)]
            assert reasons and all(reasons), f"{node_id} has no usable reason"
            assert _location(path, node) in unmarked, (
                f"{node_id} reads its mutation back and no longer needs its "
                f"{MARKER_NAME} marker; remove both"
            )
            found[node_id] = node_id

    assert REQUIRED_NO_REREAD <= set(found), (
        "these node ids are registered as exempt and no longer exist: "
        f"{sorted(REQUIRED_NO_REREAD - set(found))}"
    )


def test_the_marker_is_registered_with_pytest() -> None:
    """`--strict-markers` is on, so an unregistered marker errors at collection.

    Read out of `pytest.ini` rather than trusted, because the failure it
    prevents is not a red test but a whole module that cannot be collected.
    """
    registered = {
        line.strip().split("(")[0].split(":")[0]
        for line in (TESTS.parent / "pytest.ini")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.startswith("    ") and ":" in line
    }

    assert MARKER_NAME in registered, f"registered markers found: {sorted(registered)}"


_TASK_LISTS = HTTP_TESTS / "test_task_lists.py"


def _strip_markers(tree: ast.Module) -> ast.Module:
    """The same tree with every exemption marker removed.

    Used by the companion test above to ask what the gate would say about an
    exempted test if it were not exempt - which is the only way to check that the
    exemption is still needed rather than merely still present.

    A deep copy rather than a re-parse of `ast.unparse(tree)`: unparsing
    renumbers every line, and the answer is compared against `file:line` taken
    from the original tree.
    """
    stripped = copy.deepcopy(tree)
    for node in _functions(stripped):
        node.decorator_list = [
            decorator
            for decorator in node.decorator_list
            if ast.unparse(decorator).split("(")[0].split(".")[-1] != MARKER_NAME
        ]
    return stripped


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


def _no_reread_in(source: str) -> list[str]:
    """The half (b) offenders in a planted snippet, as `file:line`."""
    return no_reread_offenders(HTTP_TESTS / "planted.py", ast.parse(source))


def _reasons_in(source: str) -> list[str]:
    """The reason offenders in a planted snippet, as `file:line`."""
    return reason_offenders(HTTP_TESTS / "planted.py", ast.parse(source))


_A_MUTATION = (
    "async def test_planted(api_client: tuple[AsyncClient, FastAPI]) -> None:\n"
    "    client, _ = api_client\n"
    "    response = await client.patch('/x', json={'name': 'Weekly'})\n"
    "    assert response.json()['name'] == 'Weekly'\n"
)


def test_a_mutation_with_no_read_is_an_offender() -> None:
    """The shape the sweep removed twenty-nine of."""
    assert _no_reread_in(_A_MUTATION) == ["tests/integration/api/planted.py:1"]


def test_a_mutation_followed_by_a_read_is_not_an_offender() -> None:
    """The shape the sweep left behind."""
    assert (
        _no_reread_in(
            _A_MUTATION + "    after = (await client.get('/x')).json()\n"
            "    assert after['name'] == 'Weekly'\n"
        )
        == []
    )


def test_a_read_before_the_mutation_and_none_after_is_still_an_offender() -> None:
    """The `before` half of the rejected-mutation leg is not the re-read.

    This is the assertion that makes the gate worth having on the rejected leg: a
    check that accepted any `client.get` anywhere would count the `before` and
    let the `after == before` that actually says "unchanged" go missing.
    """
    assert _no_reread_in(
        "async def test_planted(api_client: tuple[AsyncClient, FastAPI]) -> None:\n"
        "    client, _ = api_client\n"
        "    before = (await client.get('/x')).json()\n"
        "    response = await client.patch('/x', json={})\n"
        "    assert response.json()['code'] == 'validation_error'\n"
    ) == ["tests/integration/api/planted.py:1"]


def test_a_read_only_test_is_not_an_offender() -> None:
    """Half (b) is about mutations; a GET has nothing to read back."""
    assert (
        _no_reread_in(
            "async def test_planted(api_client: tuple[AsyncClient, FastAPI]) -> None:\n"
            "    client, _ = api_client\n"
            "    response = await client.get('/x')\n"
            "    assert response.json() == []\n"
        )
        == []
    )


_A_LITERAL_DELETE = (
    "async def test_planted(api_client: tuple[AsyncClient, FastAPI]) -> None:\n"
    "    client, _ = api_client\n"
    "    response = await client.request('DELETE', '/x')\n"
    "    assert response.json()['code'] == 'gone'\n"
)


def test_a_literal_mutating_verb_through_request_is_an_offender() -> None:
    """The generic call is a mutation when its verb says so."""
    assert _no_reread_in(_A_LITERAL_DELETE) == ["tests/integration/api/planted.py:1"]


def test_a_literal_get_through_request_is_not_an_offender() -> None:
    """And it is a read when its verb says *that*, which is the load-bearing half.

    Without this the resolution could be nothing more than "treat `request` as
    mutating", and a re-read spelled generically would be invisible - so the
    second assertion reads the change back through `request('GET', ...)` after a
    `patch` and expects no offender.
    """
    assert (
        _no_reread_in(
            "async def test_planted("
            "api_client: tuple[AsyncClient, FastAPI]) -> None:\n"
            "    client, _ = api_client\n"
            "    response = await client.request('GET', '/x')\n"
            "    assert response.json() == []\n"
        )
        == []
    )
    assert (
        _no_reread_in(
            _A_MUTATION + "    after = (await client.request('GET', '/x')).json()\n"
            "    assert after['name'] == 'Weekly'\n"
        )
        == []
    )


def test_a_non_literal_verb_is_treated_as_mutating() -> None:
    """The permission matrix's own shape, reduced to four lines.

    `cell.row.method` is any of POST, PATCH, PUT, DELETE and GET depending on the
    parameter, so the gate cannot know - and the rule is that it assumes the
    worst. With a `get` after it the test complies, which is what plan 06-05's
    first commit made true of the matrix itself.
    """
    unread = (
        "async def test_planted(api_client: tuple[AsyncClient, FastAPI]) -> None:\n"
        "    client, _ = api_client\n"
        "    response = await client.request(cell.row.method, '/x')\n"
        "    assert response.json()['code'] == 'whatever'\n"
    )

    assert _no_reread_in(unread) == ["tests/integration/api/planted.py:1"]
    assert (
        _no_reread_in(
            unread + "    after = (await client.get('/x')).json()\n"
            "    assert after['name'] == 'Weekly'\n"
        )
        == []
    )


def test_a_verb_the_gate_cannot_read_is_never_a_way_out() -> None:
    """The fallback, not the happy path: both of these are mutations.

    A spelling `REQUEST_VERBS` does not contain, passed as the `method=` keyword,
    and a verb bound to a local name. Neither can be resolved, so neither is
    allowed to be a read.
    """
    assert _no_reread_in(
        "async def test_planted(api_client: tuple[AsyncClient, FastAPI]) -> None:\n"
        "    client, _ = api_client\n"
        "    response = await client.request(method='TRACE', url='/x')\n"
        "    assert response.json()['code'] == 'nope'\n"
    ) == ["tests/integration/api/planted.py:1"]
    assert _no_reread_in(
        "async def test_planted(api_client: tuple[AsyncClient, FastAPI]) -> None:\n"
        "    client, _ = api_client\n"
        "    verb = 'GET'\n"
        "    response = await client.request(verb, '/x')\n"
        "    assert response.json() == []\n"
    ) == ["tests/integration/api/planted.py:1"]


def test_a_marked_test_is_not_an_offender() -> None:
    """The escape hatch works - and the next three tests are why it is not a hole."""
    marked = f'@pytest.mark.{MARKER_NAME}("login mutates nothing")\n' + _A_MUTATION

    assert _no_reread_in(marked) == []
    assert _reasons_in(marked) == []


def test_a_marker_with_an_empty_reason_is_a_reason_offender() -> None:
    """Gate one, on a snippet: `""` is not a justification."""
    assert _reasons_in(f'@pytest.mark.{MARKER_NAME}("")\n' + _A_MUTATION) == [
        "tests/integration/api/planted.py:2"
    ]


def test_a_bare_marker_with_no_reason_is_a_reason_offender() -> None:
    """A marker applied without a call is found and reported, never ignored."""
    assert _reasons_in(f"@pytest.mark.{MARKER_NAME}\n" + _A_MUTATION) == [
        "tests/integration/api/planted.py:2"
    ]


def test_a_reason_that_is_a_name_rather_than_a_literal_is_a_reason_offender() -> None:
    """A literal, so that the reason is readable in the file it exempts."""
    assert _reasons_in(f"@pytest.mark.{MARKER_NAME}(REASON)\n" + _A_MUTATION) == [
        "tests/integration/api/planted.py:2"
    ]


def test_the_marker_is_matched_through_an_aliased_mark_import() -> None:
    """`from pytest import mark` binds the same marker under a shorter name."""
    assert (
        _no_reread_in(f"@mark.{MARKER_NAME}('login mutates nothing')\n" + _A_MUTATION)
        == []
    )
