r"""UI-07 and D-04: the frontend's pins and its strictness, asserted as a gate.

`CLAUDE.md` and `DECISION_LOG.md` both say the frontend follows the same
dependency policy as `requirements.txt` — exact pins, a committed lockfile,
`npm ci` everywhere. Prose is not a gate. A single `^` in
`frontend/package.json` turns a reproducible build into a build that resolves
whatever the registry published this morning, and it leaves every test green
while doing it: `npm ci` is perfectly happy to install a range, and neither
eslint nor tsc nor vitest has an opinion about version specifiers. This module
reads the three configuration files the reproducibility rests on and fails a
build instead of letting the property quietly stop being true.

What this gate CANNOT see, stated in the house style because the boundary is
the interesting part: it reads three files. It cannot tell whether the frontend
lints, whether it type-checks, or whether its tests pass — that is
`make ui-lint`, `make ui-typecheck`, `make ui-test` and the CI `frontend` job,
and it never will be, because the Docker `test` stage has no Node in it. A
check that skipped in the container would be the 06-REVIEW WR-06 shape: a green
run that checked nothing, reported as a green run. Putting Node into the test
image to close that would change what `make docker-test` means — one of this
project's two headline commands — for a check CI already performs (ADR-108).

The three files are reachable here only because the `test` stage copies them
(`COPY frontend/package.json frontend/package-lock.json frontend/tsconfig.json
./frontend/`). That `COPY` line and this module landed in the same commit and
that commit's verification was `make docker-test`, not `make test`, because a
test that reads a repository file is green on the developer host and a
collection error in the container until the line exists (ADR-102).

Deliberately NOT asserted: the specific version any package is pinned TO. A
test that pinned `react` to `19.3.0` would go red on an honest upgrade, and the
only way to make it green again would be to edit the test in the same commit —
which is a ceremony, not a gate. What matters is the SHAPE of the specifier and
that the lockfile agrees with it.
"""

import json
import re
from pathlib import Path
from typing import Any, Final

import pytest

pytestmark = pytest.mark.unit

ROOT: Final[Path] = Path(__file__).resolve().parents[2]

FRONTEND: Final[Path] = ROOT / "frontend"
PACKAGE_JSON: Final[Path] = FRONTEND / "package.json"
LOCKFILE: Final[Path] = FRONTEND / "package-lock.json"
TSCONFIG: Final[Path] = FRONTEND / "tsconfig.json"

SCANNED: Final[tuple[Path, ...]] = (PACKAGE_JSON, LOCKFILE, TSCONFIG)

# Three numeric components and nothing else. One expression rejects `^`, `~`,
# `>=`, `*`, `x`, `1.2`, a `git+https://` URL, a `file:../somewhere` path, an
# `npm:alias@` redirect and every pre-release suffix — each of which is a way to
# make `npm ci` install something the reviewer did not read.
EXACT_PIN: Final[re.Pattern[str]] = re.compile(r"^\d+\.\d+\.\d+$")

# The floor, not the value: lockfileVersion 3 is what `npm ci` needs to resolve
# from `packages` alone. A future 4 is fine and must not be red.
MINIMUM_LOCKFILE_VERSION: Final[int] = 3

# Low enough that a real trim stays legal, high enough that an emptied or
# truncated manifest cannot pass. The set is 18 today.
MINIMUM_PINNED_DEPENDENCIES: Final[int] = 15


def _json(path: Path) -> dict[str, Any]:
    loaded: Any = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict), f"{path.name} is not a JSON object"
    return loaded


def _direct_dependencies() -> dict[str, str]:
    """Every `dependencies` and `devDependencies` entry, as name -> specifier.

    `engines`, `overrides`, `resolutions` and `peerDependencies` are
    deliberately NOT included: `engines.node` is legitimately a range (`>=24`),
    and a blanket scan of the file would report it as a violation forever.
    """
    manifest = _json(PACKAGE_JSON)
    declared: dict[str, str] = {}
    for block in ("dependencies", "devDependencies"):
        entries: Any = manifest.get(block, {})
        assert isinstance(entries, dict), f"package.json `{block}` is not an object"
        for name, specifier in entries.items():
            assert isinstance(specifier, str)
            declared[name] = specifier
    return declared


def test_every_frontend_dependency_is_an_exact_pin() -> None:
    loose = sorted(
        f"{name}: {specifier}"
        for name, specifier in _direct_dependencies().items()
        if not EXACT_PIN.fullmatch(specifier)
    )

    assert not loose, (
        "frontend/package.json declares specifiers that are not exact pins, so "
        "`npm ci` could resolve a version nobody reviewed: "
        f"{loose}. The policy is requirements.txt's - `==`, never a range "
        "(D-04, ADR-108)"
    )


def test_the_lockfile_is_committed_and_describes_this_package() -> None:
    lock = _json(LOCKFILE)
    manifest = _json(PACKAGE_JSON)

    version: Any = lock.get("lockfileVersion")
    assert isinstance(version, int) and version >= MINIMUM_LOCKFILE_VERSION, (
        f"frontend/package-lock.json declares lockfileVersion {version!r}; "
        f"`npm ci` needs at least {MINIMUM_LOCKFILE_VERSION}"
    )
    assert lock.get("name") == manifest.get("name"), (
        "frontend/package-lock.json names "
        f"{lock.get('name')!r} while package.json names "
        f"{manifest.get('name')!r} - the lock belongs to a different package"
    )


def test_the_lockfile_agrees_with_the_manifest() -> None:
    """Every direct dependency resolves in the lock to the version declared.

    This is the half that makes `npm ci` reproducible rather than merely
    present. A lockfile can be committed, parse, carry the right name and still
    pin `react` to a version `package.json` does not ask for - and `npm ci`
    would then fail in CI and in the image build while the host, whose
    `node_modules` predates the drift, stays green.
    """
    lock = _json(LOCKFILE)
    packages: Any = lock.get("packages", {})
    assert isinstance(packages, dict), "package-lock.json has no `packages` map"

    disagreements: list[str] = []
    for name, declared in sorted(_direct_dependencies().items()):
        entry: Any = packages.get(f"node_modules/{name}")
        if not isinstance(entry, dict):
            disagreements.append(f"{name}: declared {declared}, absent from the lock")
            continue
        resolved: Any = entry.get("version")
        if resolved != declared:
            disagreements.append(f"{name}: declared {declared}, locked {resolved}")

    assert not disagreements, (
        "frontend/package-lock.json disagrees with frontend/package.json: "
        f"{disagreements}. Re-run `npm install` in frontend/ and commit the lock"
    )


def test_typescript_is_strict_and_emits_nothing() -> None:
    options: Any = _json(TSCONFIG).get("compilerOptions", {})
    assert isinstance(options, dict), "tsconfig.json has no compilerOptions object"

    assert options.get("strict") is True, (
        "frontend/tsconfig.json does not set compilerOptions.strict to true. "
        "Strict is the axis D-04 names; without it `any` flows silently through "
        "the API client and the type annotations become decoration"
    )
    assert options.get("noEmit") is True, (
        "frontend/tsconfig.json does not set compilerOptions.noEmit to true, so "
        "`make ui-typecheck` would write build output into the working tree"
    )


def test_the_scan_is_not_vacuous() -> None:
    """Every parser above found something, and fails rather than skips if not.

    The reason this is its own test: deleting `frontend/package.json` would
    otherwise make three of the four checks pass. An empty dependency map has no
    loose specifier in it, an absent lock has no disagreement with it, and the
    gate would report a perfectly pinned frontend about files that are not
    there.
    """
    missing = [path.name for path in SCANNED if not path.is_file()]
    assert not missing, (
        f"these frontend files are missing: {missing}. In the container this "
        "means the Dockerfile `test` stage is not copying them into ./frontend/ "
        "(ADR-102)"
    )

    empty = [
        path.name for path in SCANNED if not path.read_text(encoding="utf-8").strip()
    ]
    assert not empty, f"these frontend files are empty: {empty}"

    pinned = len(_direct_dependencies())
    assert pinned >= MINIMUM_PINNED_DEPENDENCIES, (
        f"only {pinned} pinned frontend dependencies were found; at least "
        f"{MINIMUM_PINNED_DEPENDENCIES} are expected, so the pin scan above is "
        "reading a manifest that has been emptied rather than a real one"
    )
