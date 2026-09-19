"""D-15: no router answers a business failure itself.

A refusal in this API is a `DomainError`. `register_exception_handlers` turns it
into the one RFC 9457 `application/problem+json` body the whole surface speaks,
and ADR-008 puts the *visibility* decision - whether a caller may learn a
resource exists at all - inside the use case, beside the ownership check that
can actually answer it. A router that raised the web framework's own error class
would break both properties at once: a second error-body shape a client has to
parse, and an access-control decision taken in the one layer that does not know
who owns what.

So the property is asserted about the *syntax* of every module under
`presentation/api` - routers, schemas, the actor seam, the dependency providers
and the health endpoint - with exactly one exemption, in two passes, and the pair
is not redundant.

**The scope, and what the Phase 4 review's WR-05 changed.** This gate used to
scan `presentation/api/routers` only, while `.importlinter` and CLAUDE.md both
described it as covering the presentation layer. The gap was not academic:
`actor.py` is the file Phase 5 rewrites with JWT decoding, which is the single
most likely place for a hand-raised 401 to appear, and it was outside the scan.
The file keeps its name because other documents point at it; what it walks is
now the whole package.

**The one exemption is a module, not a package:** `errors/handlers.py`. It is the
single exception-handling point CLAUDE.md describes, and it has to name
Starlette's class in order to *register a handler for it* - that is translating
the exception into problem+json, the opposite of raising it. `errors/mapping.py`
and `errors/problem.py` need no such thing and are scanned like everything else.
`test_the_exempt_module_still_needs_its_exemption` fails if the exemption outlives
its reason.

The first pass walks each `raise` statement and resolves the name being raised.
That catches the direct form, the dotted form and an aliased import - the last
one because the pass first collects every local name the module binds the class
to (`from fastapi import HTTPException as HE` makes `HE` a forbidden name), which
is what the review found this docstring claiming and the code not doing. It does
**not** catch a construction bound to a local name and raised on the next line -
the research prototype that became this code said so explicitly, having been run
against exactly that shape.

The second pass is what closes the hole, and it is the load-bearing one: a
module that never *imports* the class, and never reaches it through an
attribute, cannot raise it by any spelling at all. The first pass is kept
anyway, because it fails with the offending line rather than with an import at
the top of the file, and because it also catches a class reached through some
future re-export the import pass names by a different route. The red capture in
`.planning/phases/04-task-lists-tasks/evidence/04-08-ast-gate-red.txt` shows the
two failing together on a planted raise, and then the import pass failing alone
on a plant that only imports - which is the evidence that the second assertion
earns its place rather than restating the first. The widened gate was re-proved
the same way with plants in `actor.py`, which the old scan never reached:
`.planning/phases/04-task-lists-tasks/evidence/04-review-fix-WR-05-red.txt`.

The second pass refuses four spellings: a `from ... import` of the name (aliased
or not), an attribute access ending in it, a bare use of the name, and a
star-import from the web framework, which binds the name without ever spelling
it - the hole the review pointed at. Known gap, stated rather than hidden: a
hand-built `JSONResponse(status_code=404, ...)` breaks the same rule by another
road and is not detected here; `health.py` legitimately sets a status code on a
response, so a syntactic rule for it needs more thought than this fix had.

The import pass deliberately does not restrict itself to the two modules the
class is importable from today. Naming them would make the gate depend on a
fact about a dependency rather than on the property being defended, and a local
re-export - a `presentation/api/_compat.py` that forwarded the name - would walk
straight through it. The name is refused wherever it is bound.

Deliberately NOT used: a runtime assertion that some particular request did not
produce that exception. That tests one execution path and calls it a rule, and
the paths that matter are the ones nobody thought to exercise.

Deliberately NOT used: a source-text scan for the name. It would flag this
project's own prose - a docstring under that package explaining why the class is
absent is a mention, not a use - and the `ast` walk is precise about exactly
that difference. Where 03-06's gate reads text because the property *is* about
the text, this one reads syntax because the property is about what the code
does.

This gate adds no hook to `.pre-commit-config.yaml` and no step to
`.github/workflows/ci.yml`. CLAUDE.md's two-places rule applies to a gate that
needs its own invocation; this one rides inside `pytest`, which the hook set,
the Docker test stage and CI all already run. Same argument, same outcome, as
plans 02-06 and 03-06.
"""

import ast
from pathlib import Path
from typing import Final

# tests/architecture/test_routers_raise_no_http_exception.py ->
# tests/architecture -> tests -> repository root.
PRESENTATION_API: Final[Path] = (
    Path(__file__).resolve().parents[2] / "src" / "taskmanager" / "presentation" / "api"
)

# The one literal the scan needs. Every other forbidden form in this module is
# described in prose, following the convention `test_no_commit_in_repositories.py`
# sets out - and this file is not itself under the scanned package, so naming the
# class here cannot make the gate flag itself.
FORBIDDEN_EXCEPTION: Final[str] = "HTTPException"

# The packages a star-import would silently bind the class from.
WEB_FRAMEWORK_PACKAGES: Final[frozenset[str]] = frozenset({"fastapi", "starlette"})

# The single exception-handling point. See the module docstring: a module, not
# the `errors/` package, and guarded by a test of its own.
EXEMPT_MODULES: Final[frozenset[str]] = frozenset({"errors/handlers.py"})

# Named rather than counted. Requiring these by name is what makes the scan
# non-vacuous - a renamed or emptied package, or a module that quietly stopped
# being scanned, fails the guard below instead of leaving the real tests
# asserting that nothing is nothing. `actor.py` and `dependencies.py` are here on
# purpose: they are where Phase 5's authentication lands. A new router or
# provider adds its name here in the same commit that creates it.
REQUIRED_SCANNED_MODULES: Final[frozenset[str]] = frozenset(
    {
        "actor.py",
        "dependencies.py",
        "health.py",
        "routers/task_lists.py",
        "routers/tasks.py",
        "schemas/task_lists.py",
        "schemas/tasks.py",
    }
)


def _relative(path: Path) -> str:
    return path.relative_to(PRESENTATION_API).as_posix()


def _scanned_modules() -> list[Path]:
    """Every `.py` file under `presentation/api` but the exempt one, in order."""
    return sorted(
        path
        for path in PRESENTATION_API.rglob("*.py")
        if _relative(path) not in EXEMPT_MODULES
    )


def _parsed(path: Path) -> ast.Module:
    """The module's syntax tree, with the filename kept for the error text."""
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _local_names_of_the_class(tree: ast.Module) -> frozenset[str]:
    """Every name this module could raise the class under.

    The class's own name always, plus whatever an aliased import binds it to:
    `from fastapi import HTTPException as HE` makes `HE` one of them. This is
    what lets the raise pass keep the promise its docstring makes about aliases.
    """
    aliases = {
        alias.asname
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
        if alias.name == FORBIDDEN_EXCEPTION and alias.asname is not None
    }
    return frozenset({FORBIDDEN_EXCEPTION, *aliases})


def _raised_name(node: ast.Raise) -> str | None:
    """The name a `raise` statement raises, however it is spelled.

    Resolves the bare form, the called form and the dotted form to the same
    string. A bare re-raise inside an `except` block has nothing to resolve and
    answers `None`, as does anything raised through a subscript or a call on a
    call - which is the documented gap the import pass exists to cover.
    """
    exc = node.exc
    if exc is None:
        return None
    if isinstance(exc, ast.Call):
        exc = exc.func
    if isinstance(exc, ast.Name):
        return exc.id
    if isinstance(exc, ast.Attribute):
        return exc.attr
    return None


def _is_a_star_import_from_the_web_framework(node: ast.ImportFrom) -> bool:
    """`from fastapi import *` binds the class without ever spelling its name."""
    package = (node.module or "").split(".")[0]
    return package in WEB_FRAMEWORK_PACKAGES and any(
        alias.name == "*" for alias in node.names
    )


def _names_the_class(node: ast.AST) -> bool:
    """Whether this node binds, reaches or uses the forbidden class."""
    if isinstance(node, ast.ImportFrom):
        return _is_a_star_import_from_the_web_framework(node) or any(
            alias.name == FORBIDDEN_EXCEPTION for alias in node.names
        )
    if isinstance(node, ast.Attribute):
        return node.attr == FORBIDDEN_EXCEPTION
    if isinstance(node, ast.Name):
        return node.id == FORBIDDEN_EXCEPTION
    return False


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


def reference_offenders(path: Path, tree: ast.Module) -> list[str]:
    """`file:line` for every node that binds, reaches or uses the class."""
    return [_location(path, node) for node in ast.walk(tree) if _names_the_class(node)]


def test_the_presentation_api_package_is_actually_scanned() -> None:
    """A glob that matches nothing passes vacuously; assert it matched the tree.

    Without this guard a moved package, a renamed directory or a typo in
    `PRESENTATION_API` would leave both tests below asserting that an empty list
    is empty - green forever, checking nothing, which is worse than no gate at
    all.
    """
    scanned = {_relative(path) for path in _scanned_modules()}

    assert scanned
    assert REQUIRED_SCANNED_MODULES <= scanned
    assert scanned.isdisjoint(EXEMPT_MODULES)


def test_the_exempt_module_still_needs_its_exemption() -> None:
    """An exemption is a hole, so it has to keep justifying itself.

    `errors/handlers.py` is outside the scan because registering a handler *for*
    the class requires naming it. If that module is moved, or stops referring to
    the class, the entry in `EXEMPT_MODULES` is a hole with no reason left, and
    this fails until it is removed. It must also never *raise* what it handles.
    """
    for relative in EXEMPT_MODULES:
        path = PRESENTATION_API / relative
        assert path.is_file(), f"{relative} is exempt from the scan and does not exist"
        tree = _parsed(path)
        assert reference_offenders(
            path, tree
        ), f"{relative} no longer names the class; remove it from EXEMPT_MODULES"
        assert raise_offenders(path, tree) == []


def test_no_presentation_module_raises_an_http_exception() -> None:
    """No `raise` under `presentation/api` names the framework's exception."""
    offenders = [
        offender
        for path in _scanned_modules()
        for offender in raise_offenders(path, _parsed(path))
    ]

    assert offenders == [], (
        "The presentation layer must never answer a failure itself: it raises a "
        "DomainError, and the single exception handler turns that into the one "
        "problem+json body the API speaks. Whether the caller may know the "
        "resource exists is the use case's decision, not the router's "
        "(ADR-008, D-15). Offending raise statements: "
        f"{offenders}"
    )


def test_no_presentation_module_imports_an_http_exception() -> None:
    """No scanned module binds, reaches or uses the framework's exception class.

    Strictly stronger than the raise check, and the reason the pair exists: a
    module that never names the class cannot raise it under any spelling,
    including the bind-then-raise form the syntax of a `raise` statement cannot
    see.
    """
    offenders = [
        offender
        for path in _scanned_modules()
        for offender in reference_offenders(path, _parsed(path))
    ]

    assert offenders == [], (
        "No module under presentation/api but the exception handlers may so much "
        "as name the framework's exception class - importing it is the one step "
        "that makes the indirect raise the check above cannot see possible at "
        "all (D-15). Offending references: "
        f"{offenders}"
    )


def _offenders_in(source: str) -> tuple[list[str], list[str]]:
    """Both passes over a snippet, as (raise offenders, reference offenders)."""
    path = PRESENTATION_API / "planted.py"
    tree = ast.parse(source)
    return raise_offenders(path, tree), reference_offenders(path, tree)


def test_the_raise_pass_catches_an_aliased_import() -> None:
    """The promise the module docstring makes, held to (review fix WR-05).

    `_raised_name` answers the *local* name, which for an aliased import is the
    alias and never the class's own name - so the raise pass used to be blind to
    this spelling while its docstring claimed the opposite. Asserted on a
    snippet, so the claim is tested on every run and not only on the day a plant
    is driven red by hand.
    """
    raised, referenced = _offenders_in(
        "from fastapi import HTTPException as HE\n"
        "def handler():\n"
        "    raise HE(status_code=401)\n"
    )

    assert raised == ["planted.py:3"]
    assert referenced == ["planted.py:1"]


def test_the_import_pass_catches_a_star_import_and_a_bare_name() -> None:
    """The two spellings neither pass used to see (review fix WR-05)."""
    _, star = _offenders_in("from fastapi import *\n")
    _, nested = _offenders_in("from starlette.exceptions import *\n")
    _, bare = _offenders_in("error = HTTPException(status_code=404)\n")
    _, unrelated = _offenders_in("from os.path import *\nfrom fastapi import Depends\n")

    assert star == ["planted.py:1"]
    assert nested == ["planted.py:1"]
    assert bare == ["planted.py:1"]
    assert unrelated == []


def test_the_passes_still_see_the_direct_and_the_dotted_raise() -> None:
    """The two spellings the gate has always caught, kept honest the same way."""
    direct, _ = _offenders_in(
        "from fastapi import HTTPException\nraise HTTPException(status_code=404)\n"
    )
    dotted, _ = _offenders_in("import fastapi\nraise fastapi.HTTPException(404)\n")
    rethrow, _ = _offenders_in("try:\n    pass\nexcept Exception:\n    raise\n")

    assert direct == ["planted.py:2"]
    assert dotted == ["planted.py:2"]
    assert rethrow == []
