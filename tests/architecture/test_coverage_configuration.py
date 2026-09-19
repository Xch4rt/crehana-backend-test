r"""TEST-03 and D-11: the coverage number's configuration, asserted as a gate.

`CLAUDE.md` already states the rule in prose — the threshold is never lowered,
and it is never reached with an exclusion pragma or an `omit` entry. Prose is
not a gate. A single character in `pytest.ini` turns 75 into 70, and a single
line in `pyproject.toml` removes a package from the denominator; both leave
every test green and the reported percentage higher than before. This module
reads the two files the number depends on and asserts each fact the number
rests on, so tampering with the measurement fails a build instead of producing
a better-looking build.

The `exclude_also` list is compared **exactly**, and that has a cost worth
stating the way `test_layer_boundaries.py` states its own: a legitimate fourth
entry fails this test until it is added to `EXPECTED_EXCLUDE_ALSO` here too.
That is the guard working, and it is the reason the comparison is not by
length. A fourth entry is precisely how a real exclusion would be smuggled in —
`if not TYPE_CHECKING:`, a bare `return`, a decorator name — and every weaker
comparison waves it through.

Pinning the list by value is necessary and it is not sufficient, which this
module learned the expensive way: the list *was* pinned, with four entries, and
one of them (`\.\.\.`) was an `omit` in disguise. `exclude_also` entries are
unanchored regexes, and when the matching line is the header of a block
coverage.py drops the **whole block** — so that entry matched
`-> tuple[UserResult, ...]:` and silently removed the entire `execute` body of
`ListUsers`, `ListTaskLists` and `ListAssignedTasks`, plus
`DomainError.__reduce__`, from the denominator, while this file asserted in a
docstring that none of the four excluded executable behaviour. The value pin
made *removing* it red. `test_no_exclusion_removes_a_real_statement` is the
answer: it asks coverage.py itself, through `analysis2`, which lines it is
excluding from every module under the package, and fails on any excluded line
that carries a statement outside a stub body or a `TYPE_CHECKING` block. That
check does not care how the exclusion was spelled, which is the only property
worth having here — a future entry nobody predicted is caught by what it does
rather than by how it looks (ADR-092).

One more thing a value pin cannot say: *that this is the file being read*.
coverage.py searches `.coveragerc`, `setup.cfg`, `tox.ini` and `pyproject.toml`
in that order and uses the first that carries coverage settings, so a three-line
`.coveragerc` replaces every table pinned here and leaves this whole module green
about a file nothing opens. `test_pyproject_is_the_only_coverage_configuration`
refuses the three alternatives, and refuses `--no-cov` and `--cov-config` in the
addopts for the same reason from the other side (ADR-095).

Deliberately NOT used: asserting the coverage *number*. The suite has measured
100 % since plan 03-05, but D-12 keeps the requirement at 75; 100 % is a norm
this project holds itself to, not a contract. A test that pinned 100 would go
red on an honest refactor that added a defensive branch nobody can reach yet,
and the only way to make it green again would be to write a test for something
the code does not do — which is the opposite of what a coverage number is for.
The threshold is asserted as a floor (`>= 75`, parsed as a number) so a raise
is allowed and a drop is not.

Deliberately NOT used: string-matching the literal `--cov-fail-under=75`. That
form is red on `--cov-fail-under=80`, which is a strictly better configuration,
so it would punish the one change nobody needs to prevent.

This gate adds no hook to `.pre-commit-config.yaml` and no step to
`.github/workflows/ci.yml`. CLAUDE.md's two-places rule applies to a gate that
needs its own invocation; this one rides inside `pytest`, which the hook set,
the Docker test stage and CI all already run. Same argument, same outcome, as
plan 02-06's stdlib check and plan 03-06's commit scan.
"""

import ast
import configparser
import re
import tomllib
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any, Final

import pytest
from coverage import Coverage

pytestmark = pytest.mark.unit

# tests/architecture/test_coverage_configuration.py -> tests/architecture ->
# tests -> repository root.
ROOT: Final[Path] = Path(__file__).resolve().parents[2]
PYTEST_INI: Final[Path] = ROOT / "pytest.ini"
PYPROJECT: Final[Path] = ROOT / "pyproject.toml"
PACKAGE: Final[Path] = ROOT / "src" / "taskmanager"

# D-12 carries Phase 1's threshold forward unchanged. This is a floor, not the
# value: `--cov-fail-under=80` passes, `--cov-fail-under=70` does not.
MINIMUM_THRESHOLD: Final[int] = 75

COVERAGE_TARGET: Final[str] = "--cov=taskmanager"
COVERAGE_TARGET_FLAG: Final[str] = "--cov="
THRESHOLD_FLAG: Final[str] = "--cov-fail-under="

# Two addopts that would make the threshold three lines below a decoration:
# `--no-cov` disables the measurement entirely, and `--cov-config` points
# coverage.py at a file nothing in this module reads.
FORBIDDEN_ADDOPTS: Final[tuple[str, ...]] = ("--no-cov", "--cov-config")

EXPECTED_SOURCE: Final[list[str]] = ["taskmanager"]

# Both are required, and the reason is in `pyproject.toml`: dropping `greenlet`
# hid 18 executed lines behind SQLAlchemy's async bridge, and a coverage error
# that makes the number too LOW is the one nobody investigates.
EXPECTED_CONCURRENCY: Final[list[str]] = ["thread", "greenlet"]

# Exactly the three entries `pyproject.toml` carries today, compared as a list:
# see the module docstring for why this is pinned by value and not by length,
# and for what the fourth entry that used to sit here was actually doing.
EXPECTED_EXCLUDE_ALSO: Final[list[str]] = [
    "if TYPE_CHECKING:",
    "raise NotImplementedError",
    "@abstractmethod",
]

# The only names a body may `raise` and still count as a stub rather than as
# behaviour somebody wrote and nobody measures.
STUB_EXCEPTIONS: Final[frozenset[str]] = frozenset({"NotImplementedError"})

# The exclusion comment coverage.py honours by default. Zero occurrences under
# `src/` today, so the assertion below is a hard literal and not a ceiling.
FORBIDDEN_PRAGMA: Final[str] = "# pragma: no cover"


def _addopts() -> list[str]:
    """The `pytest.ini` addopts, as the tokens pytest itself would see."""
    # `interpolation=None`: a percent sign in a value is a syntax error to the
    # default interpolation, and a configuration file is read here to be
    # reported on, never expanded. Same reasoning as `migrations/env.py`.
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(PYTEST_INI, encoding="utf-8")

    return parser.get("pytest", "addopts").split()


def _pyproject() -> dict[str, Any]:
    """`pyproject.toml`, parsed."""
    with PYPROJECT.open("rb") as handle:
        data: dict[str, Any] = tomllib.load(handle)

    return data


def _coverage_table(name: str) -> dict[str, Any]:
    """One `[tool.coverage.<name>]` table, or an empty one if it is absent."""
    table: dict[str, Any] = _pyproject()["tool"]["coverage"].get(name, {})

    return table


def _package_modules() -> list[Path]:
    """Every `.py` file under the measured package, in a stable order."""
    return sorted(PACKAGE.rglob("*.py"))


def _is_stub_body(body: Sequence[ast.stmt]) -> bool:
    """True when nothing in `body` is behaviour: `...`, docstring, or a stub raise.

    This is the whole definition of a body it is legitimate to exclude from the
    measurement - a Protocol method, an `@overload` signature, an abstract
    method whose only job is to be overridden. Anything else in the body, one
    assignment included, makes the function real.
    """
    for statement in body:
        if isinstance(statement, ast.Pass):
            continue
        if isinstance(statement, ast.Expr) and isinstance(
            statement.value, ast.Constant
        ):
            # `...` (a Protocol/overload body) or a docstring.
            if statement.value.value is Ellipsis or isinstance(
                statement.value.value, str
            ):
                continue
            return False
        if isinstance(statement, ast.Raise):
            raised = statement.exc
            called = raised.func if isinstance(raised, ast.Call) else raised
            if isinstance(called, ast.Name) and called.id in STUB_EXCEPTIONS:
                continue
            return False
        return False

    return True


def _is_type_checking_test(test: ast.expr) -> bool:
    """True for `if TYPE_CHECKING:` however the name was imported or dotted."""
    if isinstance(test, ast.Name):
        return test.id == "TYPE_CHECKING"
    if isinstance(test, ast.Attribute):
        return test.attr == "TYPE_CHECKING"

    return False


def _legitimately_excludable(tree: ast.Module) -> set[int]:
    """Every line a coverage exclusion may remove without hiding behaviour.

    Two shapes, and no third: a function (or `@overload` signature) whose body
    is a stub, decorators included, and the body of an `if TYPE_CHECKING:`
    block. The `orelse` of such an `if` is deliberately NOT included - code
    under the runtime branch is code that runs.
    """
    excludable: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and _is_stub_body(
            node.body
        ):
            first = min(
                [node.lineno, *(decorator.lineno for decorator in node.decorator_list)]
            )
            excludable.update(range(first, (node.end_lineno or node.lineno) + 1))
        elif isinstance(node, ast.If) and _is_type_checking_test(node.test):
            last = max(
                statement.end_lineno or statement.lineno for statement in node.body
            )
            excludable.update(range(node.lineno, last + 1))

    return excludable


def _statement_lines(tree: ast.Module) -> set[int]:
    """The first line of every statement in the module.

    Only the first line, on purpose: a statement spread over several lines is
    reported by coverage against its first one, and counting the continuation
    lines here would turn a legitimately excluded multi-line signature into an
    offender below.
    """
    return {node.lineno for node in ast.walk(tree) if isinstance(node, ast.stmt)}


def _exclusions_that_remove_a_statement(
    path: Path, excluded: Iterable[int]
) -> list[str]:
    """The excluded lines of `path` that carry a statement, as `file:line: src`.

    `excluded` is coverage.py's own answer, so this function is indifferent to
    how the exclusion was configured: a regex in `exclude_also`, a pragma
    comment, or a default pattern all arrive here the same way.
    """
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    lines = source.splitlines()
    offending = (set(excluded) & _statement_lines(tree)) - _legitimately_excludable(
        tree
    )

    return [
        f"{path.name}:{number}: {lines[number - 1].strip()}"
        for number in sorted(offending)
    ]


def test_both_configuration_files_are_actually_read() -> None:
    """A parse of a missing file yields an empty config and passes vacuously.

    `configparser.read` does not raise on a path that does not exist: it
    returns the list of files it managed to read. So a renamed `pytest.ini`, a
    moved repository root or an off-by-one in `parents[2]` would leave every
    assertion below reading an empty mapping - and `configparser` would raise
    `NoSectionError` rather than pass, but the `pyproject.toml` half would
    happily report "no `omit` key" about a file it never opened. Both are
    required by name here instead.
    """
    assert PYTEST_INI.is_file()
    assert PYPROJECT.is_file()
    assert _addopts()
    assert "coverage" in _pyproject()["tool"]


def test_the_measured_package_is_actually_scanned() -> None:
    """A glob that matches nothing passes vacuously; assert it matched the tree.

    Without this, the pragma scan below would assert that an empty list is
    empty - green forever, checking nothing, which is worse than no gate at
    all. The package's own name is required, not a count, so the tree can grow
    without editing this file.
    """
    scanned = {path.relative_to(PACKAGE).as_posix() for path in _package_modules()}

    assert PACKAGE.is_dir()
    assert scanned
    assert "__init__.py" in scanned
    assert "main.py" in scanned


def test_coverage_is_measured_over_the_package() -> None:
    """`--cov=taskmanager` measures the installed package, never the repository.

    Measuring a directory (`--cov=src`) would put `tests/` one careless flag
    away from the denominator, and roadmap SC-5 requires the tests to stay out
    of it.
    """
    addopts = _addopts()
    targets = [token for token in addopts if token.startswith(COVERAGE_TARGET_FLAG)]

    assert COVERAGE_TARGET in addopts
    # A second `--cov=` does not replace the first, it adds to it: `--cov=src`
    # beside this one would measure the tests as well and move the percentage
    # without a single test being written.
    assert targets == [COVERAGE_TARGET], f"Exactly one --cov= belongs here: {targets}"


def test_pyproject_is_the_only_coverage_configuration() -> None:
    """The gate pins the file coverage.py would actually read, and no other.

    coverage.py searches `.coveragerc`, then `setup.cfg`, then `tox.ini`, then
    `pyproject.toml`, and uses **the first one that carries coverage settings**.
    Everything else in this module reads `pyproject.toml`, so a three-line
    `.coveragerc` holding `omit = */use_cases/*` would replace the entire pinned
    configuration - source, branch, concurrency, exclusions and all - and leave
    every assertion here green about a file coverage.py no longer opens. The
    addopts are the same argument from the other side: `--cov-config=other.rc`
    redirects the search, and `--no-cov` turns the measurement off outright while
    `--cov-fail-under=75` sits three lines below, still looking like a gate.

    An empty `setup.cfg` or `tox.ini` is allowed, since coverage.py ignores a
    file with no coverage section; what is refused is the section.
    """
    offenders: list[str] = []
    if (ROOT / ".coveragerc").exists():
        # It has no other purpose, so its existence is the offence.
        offenders.append(".coveragerc")
    for name in ("setup.cfg", "tox.ini"):
        path = ROOT / name
        if not path.is_file():
            continue
        parser = configparser.ConfigParser(interpolation=None)
        parser.read(path, encoding="utf-8")
        offenders += [
            f"{name} [{section}]"
            for section in parser.sections()
            if section == "coverage" or section.startswith("coverage:")
        ]

    forbidden = [
        token
        for token in _addopts()
        for flag in FORBIDDEN_ADDOPTS
        if token == flag or token.startswith(f"{flag}=")
    ]

    assert offenders == [], (
        "coverage.py reads the FIRST of .coveragerc, setup.cfg, tox.ini, "
        "pyproject.toml that carries coverage settings, so this file would "
        "outrank the pinned [tool.coverage.*] tables and every assertion in "
        f"this module would pass about a file nothing reads: {offenders}"
    )
    assert forbidden == [], (
        "These addopts would redirect or disable the measurement the threshold "
        f"beside them claims to gate: {forbidden}"
    )


def test_the_threshold_is_at_least_the_required_minimum() -> None:
    """The gate's floor, parsed as a number so a raise stays legal (D-12)."""
    thresholds = [
        int(token.removeprefix(THRESHOLD_FLAG))
        for token in _addopts()
        if token.startswith(THRESHOLD_FLAG)
    ]

    assert (
        len(thresholds) == 1
    ), f"Exactly one coverage threshold belongs in the addopts; found {thresholds}"
    assert thresholds[0] >= MINIMUM_THRESHOLD, (
        f"The coverage gate must never drop below {MINIMUM_THRESHOLD}% "
        f"(the brief's requirement, carried forward unchanged by D-12); found "
        f"{thresholds[0]}%"
    )


def test_the_threshold_has_exactly_one_home() -> None:
    """A second `fail_under` in `pyproject.toml` would silently win.

    `[tool.coverage.report] fail_under` and the `--cov-fail-under` addopt are
    two knobs for one rule, and coverage.py resolves the conflict without
    complaining. Keeping the threshold in the addopts alone is what makes `make
    test`, `make docker-test`, CI and a bare `pytest` gated by identical bytes
    (D-11's three-way agreement).
    """
    assert "fail_under" not in _coverage_table("report")


def test_the_measurement_covers_the_whole_package() -> None:
    """The source is the package alone, branch coverage is on, nothing omitted.

    An `omit` entry is the cheapest way to raise the number without writing a
    test: the excluded file leaves the denominator entirely. Branch coverage
    matters for the same reason - with it off, a half-taken `if` counts as
    fully covered. `concurrency` is the one entry here that defends against the
    number being too *low*: see `pyproject.toml` and ADR-089.
    """
    run = _coverage_table("run")

    assert run["source"] == EXPECTED_SOURCE
    assert run["branch"] is True
    assert run["concurrency"] == EXPECTED_CONCURRENCY
    assert "omit" not in run, (
        "Nothing is omitted from the coverage measurement: an omit entry "
        f"raises the number by shrinking the denominator. Found: {run['omit']}"
    )


def test_the_exclusion_list_is_exactly_the_three_known_entries() -> None:
    """`exclude_also` is pinned by value, with the cost stated in the docstring.

    A typing-only import block and two bodies that exist to be overridden. A
    fourth entry is how a real exclusion would arrive, so adding one fails here
    until it is argued for in this list - and being argued for in this list is
    not enough on its own, which is what the next test is for.
    """
    assert _coverage_table("report")["exclude_also"] == EXPECTED_EXCLUDE_ALSO


def test_no_exclusion_removes_a_real_statement() -> None:
    """Whatever is excluded under `src/`, it is a stub - asked of coverage.py.

    The gate the `\\.\\.\\.` entry needed and did not have. It reads the
    exclusions back out of `analysis2` for every module in the package, so it
    measures the *effect* of the configuration rather than its spelling: an
    unanchored regex, a pragma comment and a default pattern are all the same
    input here. An excluded line that carries a statement is an offender unless
    it sits in a stub body or under `if TYPE_CHECKING:`, and the failure names
    `file:line` plus the source, because "coverage is excluding something" is
    unactionable without it.
    """
    coverage = Coverage(config_file=str(PYPROJECT))

    excluded_total = 0
    offenders: list[str] = []
    for path in _package_modules():
        _, _, excluded, _, _ = coverage.analysis2(str(path))
        excluded_total += len(excluded)
        offenders += _exclusions_that_remove_a_statement(path, excluded)

    # Non-vacuity, and it cannot satisfy what is asserted below: the package
    # really does have exclusions (the Protocol and `@overload` stub bodies), so
    # an `analysis2` that had silently stopped applying the configuration - or a
    # module list that had gone empty - fails here rather than passing green.
    assert excluded_total > 0, (
        "coverage.py reports no excluded line anywhere under the package; the "
        "Protocol stubs under application/ports/ should be excluded, so this "
        "scan is not measuring what it thinks it is"
    )
    assert offenders == [], (
        "A coverage exclusion is removing a line that carries a statement. "
        "Entries in `exclude_also` are UNANCHORED regexes, and one that matches "
        "a block header removes the whole block - which is an `omit` by another "
        "name, and CLAUDE.md forbids reaching the number that way. Offenders: "
        f"{offenders}"
    )


def test_the_exclusion_scan_catches_an_unanchored_pattern(tmp_path: Path) -> None:
    """The scan above, driven red on the exact defect it was written for.

    A gate is not trusted until it has been driven red, and by a test rather
    than by hand. The planted module is the shape that got past the value pin -
    a signature mentioning `tuple[int, ...]` over a body that does real work -
    and the planted configuration is the entry that used to be in
    `pyproject.toml`. Both directions are asserted: red under that entry, and
    clean under the repository's own configuration, so the test cannot pass
    because the helper flags everything.
    """
    module = tmp_path / "planted.py"
    module.write_text(
        "def widths() -> tuple[int, ...]:\n"
        '    """A real body under a signature that mentions an ellipsis."""\n'
        "    total = 1\n"
        "    return (total,)\n",
        encoding="utf-8",
    )
    planted = tmp_path / "planted.rc"
    planted.write_text("[report]\nexclude_also =\n    \\.\\.\\.\n", encoding="utf-8")

    _, _, excluded_under_the_pattern, _, _ = Coverage(
        config_file=str(planted)
    ).analysis2(str(module))
    _, statements, excluded_here, _, _ = Coverage(config_file=str(PYPROJECT)).analysis2(
        str(module)
    )

    assert excluded_under_the_pattern, "coverage.py excluded nothing; bad fixture"
    assert _exclusions_that_remove_a_statement(module, excluded_under_the_pattern) != []
    assert statements, "the body must be measurable to begin with"
    assert _exclusions_that_remove_a_statement(module, excluded_here) == []


def test_no_line_under_the_package_is_excluded_by_a_pragma() -> None:
    """Zero exclusion pragmas under `src/`, reported by `file:line`.

    The no-pragma rule is CLAUDE.md's, and it is the one that keeps the
    percentage meaningful: a pragma removes a line from the denominator without
    removing the line from the program, so the number goes up while the untested
    code stays exactly as untested as it was.
    """
    offenders = [
        f"{path.relative_to(PACKAGE).as_posix()}:{number}"
        for path in _package_modules()
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if FORBIDDEN_PRAGMA in line
    ]

    assert offenders == [], (
        "The coverage threshold is never reached by excluding a line: if the "
        f"number is short, write the test. Found {FORBIDDEN_PRAGMA} at: "
        f"{offenders}"
    )


def test_the_threshold_flag_is_spelled_as_pytest_cov_expects() -> None:
    """A misspelled flag is an error, not a silently ungated run - proven here.

    `--strict-config` is on, but it governs `pytest.ini` keys, not addopt
    spellings; an unknown `--cov-*` flag fails argument parsing instead. This
    test exists so the parse above cannot succeed against a flag pytest-cov
    would reject, which would make `thresholds` empty and the previous test red
    for a reason nobody could read off its message.
    """
    threshold_tokens = [
        token for token in _addopts() if re.fullmatch(r"--cov-fail-under=\d+", token)
    ]

    assert len(threshold_tokens) == 1
