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
`presentation/api/routers`, in two passes, and the pair is not redundant.

The first pass walks each `raise` statement and resolves the name being raised.
That catches the direct form, the dotted form and an aliased import. It does
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
earns its place rather than restating the first.

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
ROUTERS: Final[Path] = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "taskmanager"
    / "presentation"
    / "api"
    / "routers"
)

# The one literal the scan needs. Every other forbidden form in this module is
# described in prose, following the convention `test_no_commit_in_repositories.py`
# sets out - and this file is not itself under the scanned package, so naming the
# class here cannot make the gate flag itself.
FORBIDDEN_EXCEPTION: Final[str] = "HTTPException"

# Both routers, named rather than counted. Requiring them by name is what makes
# the scan non-vacuous - a renamed or emptied package, or a newest router that
# quietly stopped being scanned, fails the guard below instead of leaving the
# real tests asserting that nothing is nothing. A third router adds its name here
# in the same commit that creates it.
REQUIRED_SCANNED_MODULES: Final[frozenset[str]] = frozenset(
    {"task_lists.py", "tasks.py"}
)


def _router_modules() -> list[Path]:
    """Every `.py` file under the routers package, in a stable order."""
    return sorted(ROUTERS.rglob("*.py"))


def _parsed(path: Path) -> ast.Module:
    """The module's syntax tree, with the filename kept for the error text."""
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


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


def _location(path: Path, node: ast.stmt | ast.expr) -> str:
    """`file:line`, so a failure names the line rather than the rule alone."""
    return f"{path.relative_to(ROUTERS).as_posix()}:{node.lineno}"


def test_the_routers_package_is_actually_scanned() -> None:
    """A glob that matches nothing passes vacuously; assert it matched the tree.

    Without this guard a moved package, a renamed directory or a typo in
    `ROUTERS` would leave both tests below asserting that an empty list is empty
    - green forever, checking nothing, which is worse than no gate at all.
    """
    scanned = {path.relative_to(ROUTERS).as_posix() for path in _router_modules()}

    assert scanned
    assert REQUIRED_SCANNED_MODULES <= scanned


def test_no_router_raises_an_http_exception() -> None:
    """No `raise` under the routers package names the framework's exception."""
    offenders = [
        _location(path, node)
        for path in _router_modules()
        for node in ast.walk(_parsed(path))
        if isinstance(node, ast.Raise) and _raised_name(node) == FORBIDDEN_EXCEPTION
    ]

    assert offenders == [], (
        "A router must never answer a business failure itself: it raises a "
        "DomainError, and the single exception handler turns that into the one "
        "problem+json body the API speaks. Whether the caller may know the "
        "resource exists is the use case's decision, not the router's "
        "(ADR-008, D-15). Offending raise statements: "
        f"{offenders}"
    )


def test_no_router_imports_an_http_exception() -> None:
    """No router binds or reaches the framework's exception class at all.

    Strictly stronger than the raise check, and the reason the pair exists: a
    module that never names the class cannot raise it under any spelling,
    including the bind-then-raise form the syntax of a `raise` statement cannot
    see.
    """
    offenders = []
    for path in _router_modules():
        for node in ast.walk(_parsed(path)):
            if isinstance(node, ast.ImportFrom) and any(
                alias.name == FORBIDDEN_EXCEPTION for alias in node.names
            ):
                offenders.append(_location(path, node))
            elif isinstance(node, ast.Attribute) and node.attr == FORBIDDEN_EXCEPTION:
                offenders.append(_location(path, node))

    assert offenders == [], (
        "A router must not so much as name the framework's exception class - "
        "importing it is the one step that makes the indirect raise the check "
        "above cannot see possible at all (D-15). Offending references: "
        f"{offenders}"
    )
