"""Roadmap SC-4 and ARC-08: no repository ends its own transaction.

The use case owns the transaction boundary. A repository that made its own
writes permanent would turn `async with uow:` into a claim nothing can check -
the block would look atomic while half of its work was already durable, and a
failure after that point would leave the database holding a state no code path
describes. Worse, nothing would fail: the integration harness rolls its outer
transaction back at teardown, so the escaped rows would simply vanish and every
test would stay green while the property quietly stopped being true.

So the property is asserted about the *source text* of
`infrastructure/db/repositories/`, which is the only place it can be asserted at
all.

Deliberately NOT used: a code-review habit. It enforces nothing, and SC-4 asks
for a property that is provable rather than agreed.

Deliberately NOT used: a runtime assertion that no transaction is ended during
some particular call. That would test one execution path and call it a rule -
and the paths that matter are the ones nobody thought to exercise. "This call
does not appear in this directory" is a claim about the text, and the text is
what is read here.

Deliberately NOT used: an `ast` walk for an attribute access named after the
call. It is a fine upgrade and it is more precise about comments and string
literals, but the precision buys nothing here: this project already describes
forbidden forms in prose rather than spelling them (the convention `Makefile`,
`migrations/env.py` and `errors.py` follow), so a mention inside a docstring
under that package is a violation of the convention too. If it is ever adopted,
it must assert the same property - an attribute named for the call, anywhere in
the module - and never be weakened into the runtime check above.

This gate adds no hook to `.pre-commit-config.yaml` and no step to
`.github/workflows/ci.yml`. CLAUDE.md's two-places rule applies to a gate that
needs its own invocation; this one rides inside `pytest`, which the hook set, the
Docker test stage and CI all already run. Same argument, same outcome, as plan
02-06's stdlib check.
"""

from pathlib import Path
from typing import Final

import pytest

pytestmark = pytest.mark.unit

# tests/architecture/test_no_commit_in_repositories.py -> tests/architecture ->
# tests -> repository root.
REPOSITORIES: Final[Path] = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "taskmanager"
    / "infrastructure"
    / "db"
    / "repositories"
)

FORBIDDEN_CALL: Final[str] = ".commit()"

# All three adapters, named rather than counted. Requiring them by name is what
# makes the scan non-vacuous - a renamed or emptied package, or a newest adapter
# that quietly stopped being scanned, fails the guard below instead of leaving
# the real test asserting that nothing is nothing. A fourth adapter adds its name
# here in the same commit that creates it.
REQUIRED_SCANNED_MODULES: Final[frozenset[str]] = frozenset(
    {"task_lists.py", "tasks.py", "users.py"}
)


def _repository_modules() -> list[Path]:
    """Every `.py` file under the repositories package, in a stable order."""
    return sorted(REPOSITORIES.rglob("*.py"))


def test_the_repositories_package_is_actually_scanned() -> None:
    """A glob that matches nothing passes vacuously; assert it matched the tree.

    Without this guard a moved package, a renamed directory or a typo in
    `REPOSITORIES` would leave the test below asserting that an empty list is
    empty - green forever, checking nothing, which is worse than no gate at all.
    """
    scanned = {
        path.relative_to(REPOSITORIES).as_posix() for path in _repository_modules()
    }

    assert scanned
    assert REQUIRED_SCANNED_MODULES <= scanned


def test_no_repository_commits_its_own_transaction() -> None:
    """No line under the repositories package ends a transaction."""
    offenders = [
        f"{path.relative_to(REPOSITORIES).as_posix()}:{number}"
        for path in _repository_modules()
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if FORBIDDEN_CALL in line
    ]

    assert offenders == [], (
        "A repository must never end its own transaction: the unit of work does "
        "that once, when the use case says so (ARC-08, roadmap SC-4). Found "
        f"{FORBIDDEN_CALL} at: {offenders}"
    )
