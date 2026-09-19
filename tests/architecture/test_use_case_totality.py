"""D-01/D-02, TEST-01: no use case reaches the tree without a fakes-based test.

The brief asks for unit tests that cover every use case against in-memory
fakes. For five phases that was a claim a reader had to take on trust: the
suite did cover all of them, but nothing said so, and the twenty-third use case
would have shipped untested with every gate still green. This gate turns the
claim into a build failure.

The rule, in one sentence: every public symbol declared at module level under
`application/use_cases/` must be imported, alongside the in-memory fakes, by
some module under `tests/unit/application/` that also *constructs or calls* it.

**Discovery is a parse, not an import.** The package is walked with `ast`, the
way the two sibling gates walk theirs, so the gate has no opinion about import
order and cannot be defeated by a module that only exports a symbol
conditionally. A module-level `class`, `async def` or `def` whose name does not
begin with an underscore is a use-case symbol; today that is twenty-two of them
across nine modules, and a plain `def` is included so that a synchronous helper
promoted to a use case cannot slip outside the rule. (There is none today - all
twenty-two are a class or an `async def`.)

**The coverage rule needs all three of its conditions.** Importing a symbol
proves nothing on its own: a test module that imports `DeleteTaskList` only to
annotate a variable would satisfy a weaker gate. Importing the fakes matters
because TEST-01 is specifically about the in-memory suite - a symbol reachable
only from the integration harness is not what the requirement asks for. And the
construction is what separates a mention from a use. An aliased import counts
under the name it binds, so `from ... import Login as L` followed by `L(...)`
covers `Login`; the self-tests below hold the gate to that.

**The known limit, stated rather than hidden.** An import plus a construction
proves *reachability from the fakes-based suite*, not an exercise.
`test_write_paths_hold_what_they_change.py` alone imports and constructs
thirteen of the twenty-two, so in principle it could carry the whole gate.
Requiring two distinct modules would be an arbitrary number; requiring an
`await instance.execute(...)` is brittle across the three call shapes the suite
uses (a constructed use case awaited immediately, one bound to a local first,
and the three bare `await` calls of `access.py`). The honest division of labour
is that this gate proves reachability and the 75 % coverage gate proves
execution - and coverage is at 100 %, so a use case reached but never run would
fail there instead.

Deliberately NOT used: a hand-written `{use-case module: test module}` map. That
registry is the thing D-02 exists to avoid, and the real mapping is not a
function of the module name: `tasks/assign.py` is covered by two test modules
(`test_assign_task.py` and `test_unassign_task.py`, one per class),
`auth/register.py` by `test_register_user.py`, `task_lists/create.py` by
`test_create_task_list.py` and `tasks/create.py` by `test_create_task.py`. Any
name convention strong enough to resolve those is a map maintained by hand,
which is a second place for the truth to live.

Deliberately NOT used: a runtime scan of `sys.modules` or a `pytest` plugin that
watches which symbols were called during the run. That measures one invocation
of the suite and calls it a rule, and it would make a focused run either
meaningless or falsely red. The property here is about the text of the tests.

This gate adds no hook to `.pre-commit-config.yaml` and no step to
`.github/workflows/ci.yml`. CLAUDE.md's two-places rule applies to a gate that
needs its own invocation; this one rides inside `pytest`, which the Docker test
stage and CI all already run. Same argument, same outcome, as plans 02-06,
03-06 and 04-08.
"""

import ast
from pathlib import Path
from typing import Final

import pytest

pytestmark = pytest.mark.unit

# tests/architecture/test_use_case_totality.py -> tests/architecture -> tests ->
# repository root.
ROOT: Final[Path] = Path(__file__).resolve().parents[2]

USE_CASES: Final[Path] = ROOT / "src" / "taskmanager" / "application" / "use_cases"
APPLICATION_TESTS: Final[Path] = ROOT / "tests" / "unit" / "application"

# The dotted root every use-case import starts with, and the module the
# in-memory doubles live in. Both are matched structurally: the import root by
# prefix, so a deeper package is included, and the fakes by the last component of
# the dotted path, so moving them does not silently empty the gate.
USE_CASES_IMPORT_ROOT: Final[str] = "taskmanager.application.use_cases"
FAKES_MODULE: Final[str] = "fakes"

# Named rather than counted, the `REQUIRED_SCANNED_MODULES` idiom applied to
# symbols. Requiring these by name is what makes the discovery non-vacuous: a
# renamed or emptied package, or a typo in `USE_CASES`, fails this guard instead
# of leaving the real test asserting that nothing is nothing. It is a subset
# check, so a twenty-third use case does not have to be added here - it is caught
# by the coverage test, which is the one that matters. 06-RESEARCH.md calls this
# set "the 20 symbols"; the measured count is twenty-two, and the enumeration
# there is the one that was right.
REQUIRED_USE_CASE_SYMBOLS: Final[frozenset[str]] = frozenset(
    {
        # access.py - the shared visibility rule, three functions and no class.
        "visible_task_list",
        "visible_task",
        "owned_task",
        # auth/
        "AuthenticateActor",
        "Login",
        "GetProfile",
        "RegisterUser",
        # task_lists/
        "CreateTaskList",
        "DeleteTaskList",
        "GetTaskList",
        "ListTaskLists",
        "UpdateTaskList",
        # tasks/
        "AssignTask",
        "UnassignTask",
        "ChangeTaskStatus",
        "CreateTask",
        "DeleteTask",
        "GetTask",
        "ListTasks",
        "ListAssignedTasks",
        "UpdateTask",
        # users/
        "ListUsers",
    }
)

# The same guard from the other side: the test-side glob has to have matched the
# modules the coverage rule reads. Without this, a moved `tests/unit/application`
# would make every symbol an offender for a reason that reads as twenty-two
# missing tests rather than as one wrong path - and a `*.py` glob that matched
# nothing would be the more dangerous variant of the same mistake.
REQUIRED_SCANNED_TEST_MODULES: Final[frozenset[str]] = frozenset(
    {
        "test_access.py",
        "test_create_task_list.py",
        "test_list_users.py",
        "test_login.py",
        "test_write_paths_hold_what_they_change.py",
    }
)


def _relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _parsed(path: Path) -> ast.Module:
    """The module's syntax tree, with the filename kept for the error text."""
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _location(path: Path, node: ast.AST) -> str:
    """`file:line`, so a failure names the declaration rather than the rule."""
    return f"{_relative(path)}:{getattr(node, 'lineno', '?')}"


def _use_case_modules() -> list[Path]:
    """Every `.py` file under the use-case package, in a stable order."""
    return sorted(USE_CASES.rglob("*.py"))


def _test_modules() -> list[Path]:
    """Every `test_*.py` under the fakes-based application suite, in order."""
    return sorted(APPLICATION_TESTS.rglob("test_*.py"))


def declared_symbols() -> dict[str, str]:
    """Every public module-level symbol under the package, as `name -> file:line`.

    A nested class or a method is not a module-level declaration and is not a
    use case; only `tree.body` is read, never `ast.walk`.
    """
    declared: dict[str, str] = {}
    for path in _use_case_modules():
        for node in _parsed(path).body:
            if not isinstance(
                node, (ast.ClassDef, ast.AsyncFunctionDef, ast.FunctionDef)
            ):
                continue
            if node.name.startswith("_"):
                continue
            declared[node.name] = _location(path, node)
    return declared


def _imports_the_fakes(tree: ast.Module) -> bool:
    """Whether the module binds anything from the in-memory doubles module."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[-1] == FAKES_MODULE:
                return True
        elif isinstance(node, ast.Import):
            if any(alias.name.split(".")[-1] == FAKES_MODULE for alias in node.names):
                return True
    return False


def _use_case_names_bound(tree: ast.Module) -> dict[str, str]:
    """`local name -> declared name` for every use-case symbol this module binds.

    The local name is what a construction can spell, and for an aliased import it
    is the alias - which is why the mapping is kept rather than the declared set
    alone.
    """
    bound: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        module = node.module or ""
        if module != USE_CASES_IMPORT_ROOT and not module.startswith(
            f"{USE_CASES_IMPORT_ROOT}."
        ):
            continue
        for alias in node.names:
            bound[alias.asname or alias.name] = alias.name
    return bound


def _called_names(tree: ast.Module) -> frozenset[str]:
    """Every name this module constructs or calls, however it is reached."""
    called: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name):
            called.add(func.id)
        elif isinstance(func, ast.Attribute):
            called.add(func.attr)
    return frozenset(called)


def covered_symbols(tree: ast.Module) -> frozenset[str]:
    """The declared symbols this one module covers, all three conditions met."""
    if not _imports_the_fakes(tree):
        return frozenset()
    bound = _use_case_names_bound(tree)
    called = _called_names(tree)
    return frozenset(declared for local, declared in bound.items() if local in called)


def test_the_use_case_package_is_actually_scanned() -> None:
    """A glob that matches nothing passes vacuously; assert it matched the tree.

    Both sides of the rule are guarded here. Without this, a moved package or a
    typo in either path constant would leave the coverage test below asserting
    that an empty list is empty - green forever, checking nothing, which is worse
    than no gate at all.
    """
    declared = declared_symbols()
    scanned_tests = {path.name for path in _test_modules()}

    assert declared
    assert REQUIRED_USE_CASE_SYMBOLS <= set(declared), (
        "A use-case symbol named in REQUIRED_USE_CASE_SYMBOLS was not found by "
        "the scan, so either the package moved or the symbol was renamed "
        "without this list being updated. Missing: "
        f"{sorted(REQUIRED_USE_CASE_SYMBOLS - set(declared))}"
    )
    assert scanned_tests
    assert REQUIRED_SCANNED_TEST_MODULES <= scanned_tests


def test_every_use_case_is_reachable_from_the_fakes_based_suite() -> None:
    """Every public use-case symbol is imported, with the fakes, and constructed."""
    declared = declared_symbols()
    covered: set[str] = set()
    for path in _test_modules():
        covered |= covered_symbols(_parsed(path))

    offenders = sorted(
        f"{symbol} -> {location}"
        for symbol, location in declared.items()
        if symbol not in covered
    )

    assert offenders == [], (
        "Every use case must have a unit test that runs it against the "
        "in-memory fakes (TEST-01, D-02): some module under "
        "tests/unit/application/ has to import the symbol, import the fakes, "
        "and construct or call it. Uncovered symbols: "
        f"{offenders}"
    )


def _covered_in(source: str) -> frozenset[str]:
    """The coverage rule applied to a snippet, for the self-tests below."""
    return covered_symbols(ast.parse(source))


def test_an_import_without_a_construction_is_not_coverage() -> None:
    """The condition that separates a mention from a use.

    A module that imports a use case to annotate a variable, or to assert it
    exists, has not tested it - and a gate that accepted the import alone would
    be satisfied by the import line this snippet contains.
    """
    covered = _covered_in(
        "from taskmanager.application.use_cases.auth.login import Login\n"
        "from tests.unit.application.fakes import FakeUnitOfWork\n"
        "def test_it() -> None:\n"
        "    assert Login is not None\n"
    )

    assert covered == frozenset()


def test_a_construction_without_the_fakes_is_not_coverage() -> None:
    """TEST-01 asks for the in-memory suite specifically.

    A use case constructed against real adapters is tested somewhere else, by
    something else; this gate is the one that says the fakes-based suite reaches
    it.
    """
    covered = _covered_in(
        "from taskmanager.application.use_cases.auth.login import Login\n"
        "def test_it() -> None:\n"
        "    Login(unit_of_work, hasher, tokens)\n"
    )

    assert covered == frozenset()


def test_an_aliased_import_plus_a_construction_is_coverage() -> None:
    """The alias is the only name the construction can spell.

    Resolved to the *declared* name, which is what the offender list is keyed
    on - otherwise an aliased import would report the real symbol as uncovered
    while a test for it sat in the file.
    """
    covered = _covered_in(
        "from taskmanager.application.use_cases.auth.login import Login as L\n"
        "from tests.unit.application.fakes import FakeUnitOfWork\n"
        "def test_it() -> None:\n"
        "    L(FakeUnitOfWork(), hasher, tokens)\n"
    )

    assert covered == frozenset({"Login"})


def test_a_bare_await_of_a_module_function_is_coverage() -> None:
    """`access.py`'s three functions are called, never constructed.

    The same `ast.Call` node covers both shapes, which is why the rule is worded
    "constructs or calls" - a shape-specific rule would have needed a second
    branch for the one module that has no class in it.
    """
    covered = _covered_in(
        "from taskmanager.application.use_cases.access import visible_task_list\n"
        "from tests.unit.application.fakes import FakeUnitOfWork\n"
        "async def test_it() -> None:\n"
        "    await visible_task_list(FakeUnitOfWork(), list_id, actor_id)\n"
    )

    assert covered == frozenset({"visible_task_list"})


def test_an_unrelated_import_is_not_mistaken_for_a_use_case() -> None:
    """The import root is matched by prefix, and a neighbouring package is not it."""
    covered = _covered_in(
        "from taskmanager.application.dto.commands import LoginCommand\n"
        "from tests.unit.application.fakes import FakeUnitOfWork\n"
        "def test_it() -> None:\n"
        "    LoginCommand(email='a@b.c', password='x')\n"
    )

    assert covered == frozenset()
