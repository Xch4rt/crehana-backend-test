"""`scripts/clean-clone-rehearsal.sh`, driven as a program without a daemon.

The rehearsal itself lives behind `make rehearse` (D-09, the `make break-check`
precedent): it stops the developer's stack, clones the repository, builds an
image with `--no-cache` and runs the whole containerised suite inside the clone.
That is minutes of Docker, and none of it belongs in a unit test.

What does belong here is the part of the script that decides **what the
rehearsal will run** — and it is the part most worth testing, because it is the
only part that can fail silently. A build that breaks is loud. An extractor that
matches nothing produces a rehearsal which executes zero commands, reports every
step green, and proves that the README is true when it has not read a line of
it. So `--extract-only` is exercised against a planted README in both
directions: what it takes, and what it refuses.

The other half is the refusal. The script clones the **committed** tree, so a
dirty working tree makes a green run a claim about a tree nobody will deliver.
That check runs before the first `mktemp -d` and before the first `docker`
invocation, which is what makes it testable here: a stub for `docker` on `PATH`
and a `TMPDIR` of its own are enough to prove not just that the run refused, but
that it refused before doing anything at all. No flag or environment override
was needed to stop the script after step 0 — the ordering is the mechanism.
"""

import os
import subprocess
from pathlib import Path
from typing import Final

import pytest

pytestmark = pytest.mark.unit

# tests/unit/test_clean_clone_rehearsal.py -> tests/unit -> tests -> root.
ROOT: Final[Path] = Path(__file__).resolve().parents[2]
SCRIPT: Final[Path] = ROOT / "scripts" / "clean-clone-rehearsal.sh"

BEGIN: Final[str] = "<!-- rehearsal:begin -->"
END: Final[str] = "<!-- rehearsal:end -->"

# Git is invoked with an explicit identity and no signing, so the temporary
# repository neither depends on nor picks up the developer's global config.
GIT_ISOLATION: Final[tuple[str, ...]] = (
    "-c",
    "user.name=rehearsal test",
    "-c",
    "user.email=rehearsal@example.invalid",
    "-c",
    "commit.gpgsign=false",
    "-c",
    "init.defaultBranch=main",
)

# A README whose region holds two fenced blocks, a comment line, a blank line,
# an inline code span and a third block *outside* the markers. Every one of
# those is a thing the extractor has to treat differently, and the expected list
# below is the whole contract.
A_GOOD_README: Final[str] = f"""# Planted

{BEGIN}

## Run it

```bash
make env
make up
```

Prose naming `make install` in an inline span, which is host-path and must never
be executed by the rehearsal.

```bash
# a comment, which is expected output rather than a command

make docker-test
echo "the third command"
```

{END}

## After the region

```bash
echo "this block is outside the markers"
```
"""

EXPECTED: Final[tuple[str, ...]] = (
    "make env",
    "make up",
    "make docker-test",
    'echo "the third command"',
)

A_BLOCK: Final[str] = "```bash\nmake env\nmake up\nmake docker-test\n```"


def git(directory: Path, *arguments: str) -> None:
    """Run git in `directory`, failing the test on a non-zero exit."""
    subprocess.run(
        ["git", *GIT_ISOLATION, *arguments],
        cwd=directory,
        check=True,
        capture_output=True,
        text=True,
    )


def run(
    directory: Path, *arguments: str, extra_path: Path | None = None, tmpdir: Path
) -> subprocess.CompletedProcess[str]:
    """Run the real script in `directory` with a controlled environment.

    `PWD` is set explicitly because the script compares `pwd` with
    `git rev-parse --show-toplevel`, and an inherited `PWD` from the pytest
    process would make that comparison about the wrong directory.
    """
    environment = dict(os.environ)
    environment["PWD"] = str(directory)
    environment["TMPDIR"] = str(tmpdir)
    if extra_path is not None:
        environment["PATH"] = f"{extra_path}{os.pathsep}{environment['PATH']}"
    return subprocess.run(
        ["sh", str(SCRIPT), *arguments],
        cwd=directory,
        env=environment,
        capture_output=True,
        text=True,
    )


def a_tree_with(readme: str, tmp_path: Path) -> tuple[Path, Path]:
    """A directory holding `readme`, plus an empty directory to serve as TMPDIR."""
    tree = (tmp_path / "tree").resolve()
    tree.mkdir()
    (tree / "README.md").write_text(readme, encoding="utf-8")
    tmpdir = (tmp_path / "tmp").resolve()
    tmpdir.mkdir()
    return tree, tmpdir


def test_extract_only_prints_the_regions_commands_in_order(tmp_path: Path) -> None:
    """The dry run is the rehearsal's plan, printed.

    `--extract-only` and the real run share one extraction function, so this is
    also the assertion that the real run executes these four lines and nothing
    else: the inline `make install` span stays prose, the comment and the blank
    line are dropped, and the block after the end marker is outside the region.
    """
    tree, tmpdir = a_tree_with(A_GOOD_README, tmp_path)

    result = run(tree, "--extract-only", tmpdir=tmpdir)

    assert result.returncode == 0, result.stderr
    assert tuple(result.stdout.splitlines()) == EXPECTED


@pytest.mark.parametrize(
    ("readme", "expected_in_stderr"),
    [
        pytest.param(f"# No markers at all\n\n{A_BLOCK}\n", "0 begin", id="none"),
        pytest.param(f"# Half a pair\n\n{BEGIN}\n\n{A_BLOCK}\n", "0 end", id="no-end"),
        pytest.param(
            f"# Two begins\n\n{BEGIN}\n\n{A_BLOCK}\n\n{BEGIN}\n\n{END}\n",
            "2 begin",
            id="two-begins",
        ),
        pytest.param(
            f"# Reversed\n\n{END}\n\n{A_BLOCK}\n\n{BEGIN}\n",
            "end marker before the begin marker",
            id="reversed",
        ),
        pytest.param(
            f"# Empty region\n\n{BEGIN}\n\n```bash\n# only a comment\n```\n\n{END}\n",
            "at least 3 are required",
            id="empty-block",
        ),
    ],
)
def test_a_region_that_is_not_one_well_formed_pair_is_refused(
    tmp_path: Path, readme: str, expected_in_stderr: str
) -> None:
    """Five ways for the region to be unusable, and none of them may be silent.

    This is the guard that stops a rehearsal from running almost nothing and
    reporting that the README is true. The two-begins row is the one with
    history: 06-REVIEW WR-05 recorded a marker guard in this repository that
    documented "exactly one" while enforcing "at least one", and a second
    `begin` moves the region without changing a visible thing. The empty-block
    row is the floor — markers can be well formed around nothing.
    """
    tree, tmpdir = a_tree_with(readme, tmp_path)

    result = run(tree, "--extract-only", tmpdir=tmpdir)

    assert result.returncode != 0
    assert expected_in_stderr in result.stderr
    assert result.stdout == ""


def test_a_dirty_tree_is_refused_before_anything_is_created_or_stopped(
    tmp_path: Path,
) -> None:
    """The refusal comes first, so the test needs no Docker and no override.

    Three things are asserted, and the last two are the point. A rehearsal that
    refused *after* stopping the developer's stack, or after creating a clone,
    would be a tool that costs something every time it declines to run — so
    `docker` is stubbed with a recorder and `TMPDIR` is a directory of this
    test's own, and both are asserted untouched. The stub can only prove this
    because the script resolves `docker` through `PATH`, which is also how an
    evaluator's machine resolves it.
    """
    tree, tmpdir = a_tree_with(A_GOOD_README, tmp_path)
    git(tree, "init", "--quiet")
    git(tree, "add", "README.md")
    git(tree, "commit", "--quiet", "-m", "planted")

    dirtied = A_GOOD_README + "\nAn edit nobody committed.\n"
    (tree / "README.md").write_text(dirtied, encoding="utf-8")

    stubs = (tmp_path / "bin").resolve()
    stubs.mkdir()
    ran = tmp_path / "docker-was-invoked"
    (stubs / "docker").write_text(f"#!/bin/sh\ntouch {ran}\nexit 0\n", encoding="utf-8")
    (stubs / "docker").chmod(0o755)

    result = run(tree, extra_path=stubs, tmpdir=tmpdir)

    assert result.returncode != 0
    assert "uncommitted changes" in result.stderr
    assert not ran.exists(), "the developer's stack was touched by a refused run"
    assert list(tmpdir.iterdir()) == [], "a temporary directory was left behind"
    assert (tree / "README.md").read_text(encoding="utf-8") == dirtied
