"""D-04, TEST-04: every failure this code can raise has its `code` asserted.

The API speaks one error language - RFC 9457 `application/problem+json`, built in
one place - and the `code` member is the part a client branches on. Nine of the
thirteen classes in `domain/exceptions.py` are actually raised, and every one of
their codes is asserted by some test today. Nothing said so, which is the whole
problem: the tenth leaf would have shipped with a code no test had ever seen, and
the first reader of an unasserted `code` is a client that has already integrated
against it.

**The rule is "raised under `src/`", not "declared".** Four of the thirteen
classes - the root, and the three that group the not-found, conflict and
business-rule families - are abstract parents. They are never raised, they exist
so `presentation/api/errors/mapping.py` can resolve a status by MRO walk, and
their `code` is therefore a value no response can ever carry. Requiring a test to
assert `not_found` would be requiring a test of something that cannot happen; the
gate would be satisfied by a test that asserted a fiction. So the raised set is
measured, by walking every `raise` statement under `src/` with `ast` - the same
walk `test_routers_raise_no_http_exception.py` uses - and the rule applies to
exactly those classes.

**A code is covered when it appears as a string literal under `tests/`, and a
docstring does not count.** The literal is what an assertion compares a response
body against, so the presence of the literal is a good proxy for "some test
compares the body's code to this". Docstrings are excluded deliberately: this
project's tests explain themselves at length, and a code *named in prose* is the
exact thing this gate must not accept as coverage. Every module, class and
function docstring under `tests/` is skipped before the literals are collected.

**This module excludes itself from the `tests/` scan, and that exclusion is the
difference between a gate and a formality.** `REQUIRED_RAISED_CODES` below names
all nine codes as string literals, in a file under `tests/` - so a scan that
included this one would find every code "asserted" by the gate's own non-vacuity
guard and pass no matter what the rest of the suite did. It was written that way
first, and it passed while proving nothing; the exclusion, and
`test_the_self_exclusion_is_load_bearing` beside it, are what make the green
meaningful.

**The two non-vacuity guards.** `REQUIRED_RAISED_CODES` names the nine codes as a
subset of the discovered raised set, so a moved package or a renamed `code`
ClassVar fails here rather than leaving the real check comparing two empty sets.
And both scans have to have matched files at all - a `src/` glob that found
nothing would report perfect coverage of nothing.

**The hole that is closed rather than accepted.** The classes are discovered by
importing the exceptions module and walking `__subclasses__()` recursively, which
sees only the subclasses whose defining module has been imported. A leaf declared
somewhere else - a convenience subclass in an adapter - would therefore be
invisible to the discovery while being perfectly raisable. So a second test
asserts that every `DomainError` subclass declared anywhere under `src/` is
declared in the one module, which is a rule worth having on its own: an error
contract with two homes has no single place to read it from.

Deliberately NOT used: a hand-written list of codes to check. That is the
registry D-04 exists to avoid, and the `ClassVar` on each class is already the
source of truth - a list beside it would disagree with it the first time either
moved.

Deliberately NOT used: asserting each code is reachable over HTTP. That is a much
stronger property and the right one to want, but it cannot be derived: some leaves
are raised on paths no request can construct on purpose (an `IntegrityError`
translation that only fires on a race). The honest gate is the one that says every
raisable code is asserted *somewhere*, and the permission matrix plus the
endpoint-totality gate are what cover the HTTP surface.

This gate adds no hook to `.pre-commit-config.yaml` and no step to
`.github/workflows/ci.yml`. CLAUDE.md's two-places rule applies to a gate that
needs its own invocation; this one rides inside `pytest`, which the Docker test
stage and CI all already run.
"""

import ast
from pathlib import Path
from typing import Final

import pytest

from taskmanager.domain.exceptions import DomainError

pytestmark = pytest.mark.unit

# tests/architecture/test_error_contract_totality.py -> tests/architecture ->
# tests -> repository root.
ROOT: Final[Path] = Path(__file__).resolve().parents[2]

SRC: Final[Path] = ROOT / "src" / "taskmanager"
TESTS: Final[Path] = ROOT / "tests"

# The one module the whole error contract is allowed to live in.
EXCEPTIONS_MODULE: Final[Path] = SRC / "domain" / "exceptions.py"

# This file, excluded from the `tests/` scan for the reason the docstring gives:
# its own guard names every code, so counting it would make the gate self-
# satisfying.
SELF: Final[Path] = Path(__file__).resolve()

# The nine codes that can actually come out of this application today, named
# rather than counted. A subset check, so a tenth raisable leaf does not have to
# be added here - it is caught by the coverage test, which is the one that
# matters. The four abstract parents are deliberately absent: see the docstring.
REQUIRED_RAISED_CODES: Final[frozenset[str]] = frozenset(
    {
        "validation_error",
        "invalid_status_transition",
        "task_not_found",
        "task_list_not_found",
        "user_not_found",
        "duplicate_task_list_name",
        "email_already_registered",
        "authentication_failed",
        "authorization_failed",
    }
)


def _parsed(path: Path) -> ast.Module:
    """The module's syntax tree, with the filename kept for the error text."""
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _source_modules() -> list[Path]:
    """Every `.py` file under the application package, in a stable order."""
    return sorted(SRC.rglob("*.py"))


def _test_modules() -> list[Path]:
    """Every `.py` file under the test suite but this one, in a stable order."""
    return sorted(path for path in TESTS.rglob("*.py") if path.resolve() != SELF)


def domain_error_classes() -> dict[str, str]:
    """Every `DomainError` and descendant, as `class name -> code`.

    Walked recursively rather than read off a list, so a class added to the
    hierarchy joins this gate by existing.
    """
    found: dict[str, str] = {}

    def descend(cls: type[DomainError]) -> None:
        found[cls.__name__] = cls.code
        for subclass in cls.__subclasses__():
            descend(subclass)

    descend(DomainError)
    return found


def _raised_name(node: ast.Raise) -> str | None:
    """The name a `raise` statement raises, however it is spelled.

    A bare re-raise inside an `except` block has nothing to resolve and answers
    `None`; the called, bare and dotted forms all resolve to the same string.
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


def raised_names() -> frozenset[str]:
    """Every name raised anywhere under the application package."""
    return frozenset(
        name
        for path in _source_modules()
        for node in ast.walk(_parsed(path))
        if isinstance(node, ast.Raise) and (name := _raised_name(node)) is not None
    )


def _docstring_node_ids(tree: ast.Module) -> frozenset[int]:
    """The `Constant` nodes that are documentation rather than data."""
    docstrings: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            continue
        if not node.body:
            continue
        first = node.body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
            if isinstance(first.value.value, str):
                docstrings.add(id(first.value))
    return frozenset(docstrings)


def string_literals(tree: ast.Module) -> frozenset[str]:
    """Every string literal in the module that is not a docstring."""
    documentation = _docstring_node_ids(tree)
    return frozenset(
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in documentation
    )


def test_the_error_hierarchy_and_both_scans_are_not_empty() -> None:
    """A glob that matches nothing passes vacuously; assert all three matched.

    Without this guard a moved package, a renamed `code` ClassVar or a typo in
    either path constant would leave the coverage test below asserting that an
    empty set is covered - green forever, checking nothing, which is worse than no
    gate at all.
    """
    classes = domain_error_classes()
    raised = {code for name, code in classes.items() if name in raised_names()}

    assert _source_modules()
    assert _test_modules()
    assert classes
    assert REQUIRED_RAISED_CODES <= raised, (
        "A code named in REQUIRED_RAISED_CODES is no longer raised anywhere under "
        "src/, so either the failure it names became unreachable or the class was "
        "renamed without this list being updated. Missing: "
        f"{sorted(REQUIRED_RAISED_CODES - raised)}"
    )


def test_the_self_exclusion_is_load_bearing() -> None:
    """This module names every code, so the scan below has to skip it.

    The `EXEMPT_MODULES` idiom of `test_routers_raise_no_http_exception.py`,
    applied to a self-reference: the exemption keeps justifying itself. If
    `REQUIRED_RAISED_CODES` were ever moved out of this file the exclusion would
    become a hole with no reason left, and this fails until it is removed - and if
    the exclusion were dropped while the guard stayed, the coverage test would go
    green forever on its own literals.
    """
    own_literals = string_literals(_parsed(SELF))

    assert SELF not in _test_modules()
    assert REQUIRED_RAISED_CODES <= own_literals


def test_the_whole_error_contract_lives_in_one_module() -> None:
    """No `DomainError` subclass is declared outside `domain/exceptions.py`.

    This is what makes the discovery above honest: `__subclasses__()` only sees
    classes whose module has been imported, so a leaf declared in an adapter would
    be raisable and invisible at once. It is also a rule worth having for its own
    sake - a contract with two homes has no single place to read it from.
    """
    known = set(domain_error_classes())
    offenders = [
        f"{path.relative_to(ROOT).as_posix()}:{node.lineno} {node.name}"
        for path in _source_modules()
        if path != EXCEPTIONS_MODULE
        for node in ast.walk(_parsed(path))
        if isinstance(node, ast.ClassDef)
        and any(isinstance(base, ast.Name) and base.id in known for base in node.bases)
    ]

    assert offenders == [], (
        "Every DomainError subclass belongs in domain/exceptions.py, which is "
        "where the RFC 9457 contract is read from and where the totality gate "
        f"below can see it. Declared elsewhere: {offenders}"
    )


def test_every_raisable_error_code_is_asserted_by_a_test() -> None:
    """Each code a `raise` under `src/` can produce appears in a test's literals."""
    classes = domain_error_classes()
    raised = raised_names()
    asserted: set[str] = set()
    for path in _test_modules():
        asserted |= string_literals(_parsed(path))

    offenders = sorted(
        f"{code} -> {name}"
        for name, code in classes.items()
        if name in raised and code not in asserted
    )

    assert offenders == [], (
        "Every failure this code can raise must have its RFC 9457 code asserted "
        "by some test (TEST-04, D-04) - a code no test names is one whose first "
        "reader is a client that has already integrated against it. Unasserted "
        f"codes: {offenders}"
    )
