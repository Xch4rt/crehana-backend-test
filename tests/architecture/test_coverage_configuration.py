"""TEST-03 and D-11: the coverage number's configuration, asserted as a gate.

`CLAUDE.md` already states the rule in prose — the threshold is never lowered,
and it is never reached with an exclusion pragma or an `omit` entry. Prose is
not a gate. A single character in `pytest.ini` turns 75 into 70, and a single
line in `pyproject.toml` removes a package from the denominator; both leave
every test green and the reported percentage higher than before. This module
reads the two files the number depends on and asserts each fact the number
rests on, so tampering with the measurement fails a build instead of producing
a better-looking build.

The `exclude_also` list is compared **exactly**, and that has a cost worth
stating the way `test_layer_boundaries.py` states its own: a legitimate fifth
entry fails this test until it is added to `EXPECTED_EXCLUDE_ALSO` here too.
That is the guard working, and it is the reason the comparison is not by
length. A fifth entry is precisely how a real exclusion would be smuggled in —
`if not TYPE_CHECKING:`, a bare `return`, a decorator name — and every weaker
comparison waves it through.

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

import configparser
import re
import tomllib
from pathlib import Path
from typing import Any, Final

import pytest

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
THRESHOLD_FLAG: Final[str] = "--cov-fail-under="

EXPECTED_SOURCE: Final[list[str]] = ["taskmanager"]

# Both are required, and the reason is in `pyproject.toml`: dropping `greenlet`
# hid 18 executed lines behind SQLAlchemy's async bridge, and a coverage error
# that makes the number too LOW is the one nobody investigates.
EXPECTED_CONCURRENCY: Final[list[str]] = ["thread", "greenlet"]

# Exactly the four entries `pyproject.toml` carries today, compared as a list:
# see the module docstring for why this is pinned by value and not by length.
EXPECTED_EXCLUDE_ALSO: Final[list[str]] = [
    "if TYPE_CHECKING:",
    "raise NotImplementedError",
    "@abstractmethod",
    r"\.\.\.",
]

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
    assert COVERAGE_TARGET in _addopts()


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


def test_the_exclusion_list_is_exactly_the_four_known_entries() -> None:
    """`exclude_also` is pinned by value, with the cost stated in the docstring.

    None of the four excludes executable behaviour: a typing-only import block,
    two bodies that exist to be overridden, and the Protocol ellipsis. A fifth
    entry is how a real exclusion would arrive, so adding one fails here until
    it is argued for in this list.
    """
    assert _coverage_table("report")["exclude_also"] == EXPECTED_EXCLUDE_ALSO


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
