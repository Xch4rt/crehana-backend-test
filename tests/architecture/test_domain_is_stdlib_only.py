"""The domain package's stdlib-only rule, executed as part of the normal test suite.

`taskmanager.domain` may import the standard library and itself, and nothing else. The
rule is checked here, inside pytest, by parsing every module under
`src/taskmanager/domain/` and testing each import root against the interpreter's own
list of standard-library module names. A third-party import entering the domain is
therefore a failing test on the host, in the Docker test stage and in CI, with no extra
gate to keep in sync.

Deliberately NOT relied on: the `domain-framework-free` contract in `.importlinter`.
That is a `forbidden` contract with an *enumerated* module list, so it proves those nine
distributions are absent and says nothing whatsoever about the tenth. The
`forbidden_modules = *` wildcard was executed during research and reported
`dataclasses`, `datetime` and `enum` as violations, because the grimp graph built with
`include_external_packages = True` carries stdlib modules as first-class nodes; there is
no contract type meaning "everything except the standard library". The enumerated
contract is kept for its targeted, readable failures, and this test is what makes
roadmap success criterion 1 mechanically true.

Deliberately NOT used: `grimp.build_graph`. grimp reaches this environment only as a
transitive dependency of import-linter, and `requirements-dev.txt` states that it is
intentionally absent from the declared set, so depending on it here would let a future
import-linter bump break the suite with a confusing `ModuleNotFoundError`.
`sys.stdlib_module_names` is maintained by CPython for the running interpreter, which
keeps the check honest on 3.13 in CI and on 3.14 on the host. This gate was observed red
on a planted `import greenlet` that `lint-imports` reported as KEPT - see
evidence/domain-stdlib-red-green.txt.
"""

import ast
import sys
from pathlib import Path

DOMAIN_ROOT = Path(__file__).resolve().parents[2] / "src" / "taskmanager" / "domain"

MINIMUM_DOMAIN_MODULES = 10

REQUIRED_SCANNED_MODULES = frozenset(
    {
        "exceptions.py",
        "validation.py",
        "value_objects/task_status.py",
        "entities/task.py",
    }
)


def _domain_modules() -> list[Path]:
    """Every `.py` file under the domain package, in a stable order."""
    return sorted(DOMAIN_ROOT.rglob("*.py"))


def _imported_roots(path: Path) -> set[str]:
    """The root package name of every absolute import made by one module."""
    roots: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            # node.level > 0 means a relative intra-package import such as
            # `from .task_status import TaskStatus`. It cannot reach outside the
            # domain, so it is skipped rather than resolved - reporting it as a
            # violation is the obvious bug in a test shaped like this one.
            if node.level == 0 and node.module is not None:
                roots.add(node.module.split(".")[0])
    return roots


def test_the_domain_package_is_actually_scanned() -> None:
    """A glob that matches nothing passes vacuously; assert it matched the real tree.

    Without this guard a renamed directory, a moved `src/` layout or a typo in
    `DOMAIN_ROOT` would leave `test_domain_imports_only_stdlib` asserting that an empty
    list is empty - green forever, checking nothing, which is worse than no test at all.
    """
    scanned = {path.relative_to(DOMAIN_ROOT).as_posix() for path in _domain_modules()}

    assert len(scanned) >= MINIMUM_DOMAIN_MODULES
    assert REQUIRED_SCANNED_MODULES <= scanned


def test_domain_imports_only_stdlib() -> None:
    """Every import root under `taskmanager.domain` is stdlib or `taskmanager`."""
    violations = [
        (path.relative_to(DOMAIN_ROOT).as_posix(), root)
        for path in _domain_modules()
        for root in sorted(_imported_roots(path))
        if root != "taskmanager" and root not in sys.stdlib_module_names
    ]

    assert violations == []
