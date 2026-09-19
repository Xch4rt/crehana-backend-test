"""`scripts/break-check.sh`, driven as a program in a throwaway repository.

What these tests are about is the script's *safety*, never its findings. The
five real breaks live behind `make break-check` (D-09): that run takes about a
quarter of a minute, needs PostgreSQL, and deliberately writes to `src/` —
none of which belongs in a unit test. So each test below builds a git
repository in `tmp_path`, plants a copy of the first file the script mutates at
the path the script expects, and stands a shell stub in for pytest through the
one environment variable the script reads. Nothing here can touch this
repository's own `src/`, because the script resolves every path against its
working directory and that directory is always the temporary one.

The property under test in all three cases is the same: this is the only tool
in the repository that writes to `src/` on purpose, so it must never be able to
leave a mutation behind, and it must never be able to destroy work it did not
make.
"""

import os
import re
import shlex
import subprocess
from pathlib import Path
from typing import Final

import pytest

pytestmark = pytest.mark.unit

# tests/unit/test_break_check.py -> tests/unit -> tests -> repository root.
ROOT: Final[Path] = Path(__file__).resolve().parents[2]
SCRIPT: Final[Path] = ROOT / "scripts" / "break-check.sh"

# Git is invoked with an explicit identity and no signing, so the temporary
# repository does not depend on - or pick up - the developer's global config.
GIT_ISOLATION: Final[tuple[str, ...]] = (
    "-c",
    "user.name=break-check test",
    "-c",
    "user.email=break-check@example.invalid",
    "-c",
    "commit.gpgsign=false",
    "-c",
    "init.defaultBranch=main",
)


def first_break_target() -> str:
    """The repository-relative path of the first file the script mutates.

    Read out of the script rather than restated here: the tests plant a copy of
    that exact file, so a break table which is reordered or repointed at another
    module cannot leave these tests silently exercising a path the script no
    longer touches.
    """
    match = re.search(
        r"^\s*(src/\S+\.py) \\$", SCRIPT.read_text(encoding="utf-8"), re.MULTILINE
    )
    assert match is not None, "no `src/...py` mutation target found in the script"
    return match.group(1)


BREAK_TARGET: Final[str] = first_break_target()
ORIGINAL: Final[str] = (ROOT / BREAK_TARGET).read_text(encoding="utf-8")


def git(directory: Path, *arguments: str) -> str:
    """Run git in `directory` and return its stdout."""
    completed = subprocess.run(
        ["git", *GIT_ISOLATION, *arguments],
        cwd=directory,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout


def a_repository_in(directory: Path, planted: str) -> Path:
    """A committed git repository holding `planted` at the mutated path."""
    directory.mkdir()
    git(directory, "init", "--quiet")
    target = directory / BREAK_TARGET
    target.parent.mkdir(parents=True)
    target.write_text(planted, encoding="utf-8")
    git(directory, "add", BREAK_TARGET)
    git(directory, "commit", "--quiet", "-m", "planted")
    return target


def a_stub_for_pytest(body: str, directory: Path) -> str:
    """Write a stand-in for pytest and return the value the script reads."""
    stub = directory / "stub.sh"
    stub.write_text(f"#!/bin/sh\n{body}", encoding="utf-8")
    return f"sh {stub}"


def a_stub_that_only_records_it_ran(directory: Path) -> tuple[str, Path]:
    """A stub which leaves a marker behind, so "it never ran" is assertable."""
    marker = directory / "the-tests-ran"
    body = f"touch {shlex.quote(str(marker))}\nexit 1\n"
    return a_stub_for_pytest(body, directory), marker


def run_script(repository: Path, pytest_stub: str) -> subprocess.CompletedProcess[str]:
    """Run the real script in `repository`, with `pytest_stub` for pytest."""
    return subprocess.run(
        ["sh", str(SCRIPT)],
        cwd=repository,
        env={**os.environ, "BREAK_CHECK_PYTEST": pytest_stub},
        capture_output=True,
        text=True,
    )


def test_a_dirty_src_is_refused_before_anything_is_mutated(tmp_path: Path) -> None:
    """Uncommitted work under `src/` stops the run, and survives it.

    Both halves matter. The script restores with git, so it needs a tree it can
    restore *to* - but the reason the refusal comes first is the other half: a
    tool that writes to `src/` must never be the thing that discards an edit
    somebody had not committed yet.
    """
    repository = tmp_path / "repo"
    target = a_repository_in(repository, ORIGINAL)
    dirtied = ORIGINAL + "# work in progress, not committed\n"
    target.write_text(dirtied, encoding="utf-8")
    stub, marker = a_stub_that_only_records_it_ran(tmp_path)

    result = run_script(repository, stub)

    assert result.returncode != 0
    assert not marker.exists()
    assert target.read_text(encoding="utf-8") == dirtied


def test_the_trap_restores_the_file_when_the_script_is_terminated(
    tmp_path: Path,
) -> None:
    """A run killed with the mutation in place still leaves the tree clean.

    The stub interrupts its own caller, which is the one deterministic way to
    reach the trap while a file is mutated - polling for the window and racing
    to signal it would pass just as happily by missing the window entirely. It
    records what it found on disk first, so "the mutation had really been
    applied" is asserted rather than assumed: without that, a script which
    mutated nothing would pass this test.
    """
    repository = tmp_path / "repo"
    target = a_repository_in(repository, ORIGINAL)
    observed = tmp_path / "what-the-tests-saw"
    stub = a_stub_for_pytest(
        f"cat {shlex.quote(str(target))} > {shlex.quote(str(observed))}\n"
        'kill -TERM "$PPID"\n'
        "exit 1\n",
        tmp_path,
    )

    result = run_script(repository, stub)

    # 143 is the script's own `exit 143` from the signal handler, not the shell
    # being killed - a terminated shell would report a negative status here and
    # leave the mutation on disk.
    assert result.returncode == 143
    assert observed.read_text(encoding="utf-8") != ORIGINAL
    assert target.read_text(encoding="utf-8") == ORIGINAL
    assert git(repository, "status", "--porcelain") == ""


def test_a_vanished_literal_is_loud_rather_than_a_green_break(tmp_path: Path) -> None:
    """A source line that has drifted fails the run and names the file.

    This is the failure mode a mutation script has to be most afraid of. A
    `str.replace` whose needle is gone rewrites the file with the same bytes, the
    tests then pass because nothing was broken, and the script reports that the
    suite cannot see a defect which was never introduced - the exact inversion of
    what it exists to say. The `assert old in s` precondition is what stops it.
    """
    repository = tmp_path / "repo"
    drifted = '"""Nothing in this file is anything the script knows how to break."""\n'
    target = a_repository_in(repository, drifted)
    stub, marker = a_stub_that_only_records_it_ran(tmp_path)

    result = run_script(repository, stub)

    assert result.returncode != 0
    assert not marker.exists()
    assert BREAK_TARGET in result.stderr
    assert target.read_text(encoding="utf-8") == drifted
