"""The architecture contract, executed as part of the normal test suite.

The layer boundaries declared in `.importlinter` are checked here, inside pytest,
so that an upward import or a framework leaking into the domain is a failing test
rather than a folder-naming convention nobody enforces. The `lint-imports` console
script runs the very same file from `make arch`, pre-commit and CI; this module is
what makes `pytest` alone sufficient to catch a violation.

Deliberately NOT used: running import-linter's command-line module through `python -m`.
That module has no `__main__` guard and the package ships no `__main__.py`, so the form
merely imports it and exits 0 without checking anything - an architecture test that can
never fail. The supported Python API below returns False on a violation, which was
observed before this file was committed (see evidence/import-linter-red-green.txt).
"""

from importlinter import api
from importlinter.application import use_cases

EXPECTED_CONTRACT_NAMES = {
    "Layered architecture (high to low)",
    "Domain is framework-free",
    "Application knows no web framework or ORM",
}


def test_every_contract_is_configured() -> None:
    """A config that configures nothing passes vacuously; assert it configures three.

    `lint-imports` reports "Contracts: 0 kept, 0 broken" and exits 0 when the section
    headers are mistyped (`[importlinter:contracts:...]` instead of the singular
    `[importlinter:contract:...]`), so without this guard a one-character typo would
    silently disable every boundary check while the build stayed green.
    """
    config = api.read_configuration()

    assert config["session_options"]["root_packages"] == ["taskmanager"]
    assert {
        contract["name"] for contract in config["contracts_options"]
    } == EXPECTED_CONTRACT_NAMES


def test_import_contracts_hold() -> None:
    """Every contract in `.importlinter` is kept by the current import graph."""
    assert use_cases.lint_imports(no_logo=True) is True
