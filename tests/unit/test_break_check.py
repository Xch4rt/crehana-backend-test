"""`scripts/break-check.sh`, driven as a program in a throwaway repository.

The five real breaks live behind `make break-check` (D-09): that run takes a
couple of minutes, needs PostgreSQL, and deliberately writes to `src/` — none of
which belongs in a unit test. So each test below builds a git repository in
`tmp_path`, plants a copy of every file the script mutates at the path the
script expects, and stands a shell stub in for pytest through the one
environment variable the script reads. Nothing here can touch this repository's
own `src/`, because the script resolves every path against its working directory
and that directory is always the temporary one.

Two properties are under test, and for a while only the first one was — which is
how the verdict defect in ADR-093 shipped.

*Safety.* This is the only tool in the repository that writes to `src/` on
purpose, so it must never be able to leave a mutation behind, and it must never
be able to destroy work it did not make.

*Correctness of the verdict.* The script's whole output is one line, and that
line is the evidence offered for roadmap SC-4, so every way of reaching it is
exercised here: a survivor, five real reddenings, a pytest exit that is not a
test failure at all, and a selection that was not green before the mutation. The
stub is what makes that affordable — it decides the verdict by exit code, which
is precisely the input the script reads. `src/` is asserted clean on every one
of those paths, including the ones that abort.
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
SUCCESS_LINE: Final[str] = "turned the suite red"

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


def break_targets() -> tuple[str, ...]:
    """Every repository-relative path the script mutates, in break order.

    Read out of the script rather than restated here: the tests plant a copy of
    those exact files, so a break table which is reordered, extended or
    repointed at another module cannot leave these tests silently exercising a
    path the script no longer touches. The tests that run all five breaks to
    completion need all five planted, because the `assert old in s` precondition
    stops the run at the first file it cannot find.
    """
    found = re.findall(
        r"^\s*(src/\S+\.py) \\$", SCRIPT.read_text(encoding="utf-8"), re.MULTILINE
    )
    assert found, "no `src/...py` mutation target found in the script"
    return tuple(found)


BREAK_TARGETS: Final[tuple[str, ...]] = break_targets()
BREAKS: Final[int] = len(BREAK_TARGETS)
BREAK_TARGET: Final[str] = BREAK_TARGETS[0]
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
    """A committed git repository holding every mutated path, first one planted.

    The first target carries `planted` — the content a test wants to drive the
    script with — and every other target carries this repository's real content,
    so the mutations of breaks 2..5 find the literals they expect and a run can
    reach the end.
    """
    directory.mkdir()
    git(directory, "init", "--quiet")
    for number, relative in enumerate(BREAK_TARGETS):
        target = directory / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        content = planted if number == 0 else (ROOT / relative).read_text("utf-8")
        target.write_text(content, encoding="utf-8")
        git(directory, "add", relative)
    git(directory, "commit", "--quiet", "-m", "planted")
    return directory / BREAK_TARGET


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


def a_stub_green_on_the_baseline(mutated: str, directory: Path) -> tuple[str, Path]:
    """A stub that passes every baseline run and does `mutated` after each one.

    The script now runs each selection twice: once unmutated, which must be
    green, and once with the defect in place. A stub with a single exit code can
    therefore only ever reach the baseline refusal, so this one counts its own
    invocations in a file and answers by parity — odd is a baseline (exit 0),
    even is the mutated run (`mutated`, which is shell, not a number). The count
    file is returned so a test can assert *how many* runs happened, which is how
    "it refused before mutating anything" is proven rather than assumed.
    """
    counted = directory / "invocations"
    body = (
        f"count_file={shlex.quote(str(counted))}\n"
        'count=$(cat "$count_file" 2>/dev/null || echo 0)\n'
        "count=$((count + 1))\n"
        'printf "%s" "$count" > "$count_file"\n'
        "if [ $((count % 2)) -eq 1 ]; then exit 0; fi\n"
        f"{mutated}\n"
    )
    return a_stub_for_pytest(body, directory), counted


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
    mutated nothing would pass this test. The signal has to land on the *mutated*
    run rather than the baseline one, which is what the parity stub is for.
    """
    repository = tmp_path / "repo"
    target = a_repository_in(repository, ORIGINAL)
    observed = tmp_path / "what-the-tests-saw"
    stub, _ = a_stub_green_on_the_baseline(
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

    The stub is green on the baseline so the run *reaches* the mutation: the
    invocation count then proves where it stopped - one run, the baseline, and no
    mutated run at all.
    """
    repository = tmp_path / "repo"
    drifted = '"""Nothing in this file is anything the script knows how to break."""\n'
    target = a_repository_in(repository, drifted)
    stub, counted = a_stub_green_on_the_baseline("exit 0\n", tmp_path)

    result = run_script(repository, stub)

    assert result.returncode != 0
    assert counted.read_text(encoding="utf-8") == "1"
    assert BREAK_TARGET in result.stderr
    assert SUCCESS_LINE not in result.stdout
    assert target.read_text(encoding="utf-8") == drifted


def test_a_selection_that_is_not_green_before_the_break_is_refused(
    tmp_path: Path,
) -> None:
    """No baseline, no verdict: a red selection stops the run before it mutates.

    The defect this closes (ADR-093) was silent and total. With PostgreSQL down,
    every integration test errors, pytest exits non-zero, and the old script read
    that as "the suite noticed" - for all five breaks, printing `red: 0 test(s)
    failed` beside each one and then its success line. An evaluator who ran
    `make break-check` before `make up` was shown proof of a property nothing had
    measured. Three things are asserted: the refusal, that exactly one pytest run
    happened (so the mutation never followed), and that what that run saw on disk
    was the unmutated file.
    """
    repository = tmp_path / "repo"
    target = a_repository_in(repository, ORIGINAL)
    observed = tmp_path / "what-the-tests-saw"
    counted = tmp_path / "invocations"
    stub = a_stub_for_pytest(
        f"cat {shlex.quote(str(target))} >> {shlex.quote(str(observed))}\n"
        f'printf "x" >> {shlex.quote(str(counted))}\n'
        'echo "1 failed, 2 passed"\n'
        "exit 1\n",
        tmp_path,
    )

    result = run_script(repository, stub)

    assert result.returncode != 0
    assert "not green BEFORE the break" in result.stderr
    assert SUCCESS_LINE not in result.stdout
    assert counted.read_text(encoding="utf-8") == "x"
    assert observed.read_text(encoding="utf-8") == ORIGINAL
    assert git(repository, "status", "--porcelain") == ""


def test_a_survivor_is_named_and_the_run_fails(tmp_path: Path) -> None:
    """Every break surviving is the finding this script exists to report.

    The one path that runs all five mutate/restore cycles to completion with a
    verdict on each, which is also what makes it the test of the restore
    *sequencing*: break 2 only starts because break 1's file was put back and the
    clean-tree check re-run, so a clean tree at the end plus five verdicts is a
    statement about all ten steps. The stub's mutated runs pass, so the defect is
    invisible to them - and a tool that cannot say so is worse than no tool.
    """
    repository = tmp_path / "repo"
    a_repository_in(repository, ORIGINAL)
    stub, counted = a_stub_green_on_the_baseline("exit 0\n", tmp_path)

    result = run_script(repository, stub)

    assert result.returncode == 1
    assert f"{BREAKS} of {BREAKS} breaks SURVIVED" in result.stderr
    assert SUCCESS_LINE not in result.stdout
    assert result.stdout.count("SURVIVED: every test passed") == BREAKS
    # A baseline and a mutated run for each break, and nothing skipped.
    assert counted.read_text(encoding="utf-8") == str(2 * BREAKS)
    assert git(repository, "status", "--porcelain") == ""


def test_a_failed_test_per_break_is_the_success_line_and_a_clean_tree(
    tmp_path: Path,
) -> None:
    """The green path, asserted for what it prints and for what it leaves behind.

    RED is exit 1 *and* a `FAILED` line, so the stub prints one - in pytest's own
    short-summary format, because that is what the script parses to name the
    tests that caught each break. This is the only test here that reaches the
    script's final line, and the reason it can be trusted is the test above: the
    same line used to be printed for runs that executed no test at all.
    """
    repository = tmp_path / "repo"
    a_repository_in(repository, ORIGINAL)
    stub, counted = a_stub_green_on_the_baseline(
        'echo "FAILED tests/unit/test_planted.py::test_it - AssertionError: no"\n'
        "exit 1\n",
        tmp_path,
    )

    result = run_script(repository, stub)

    assert result.returncode == 0
    assert f"All {BREAKS} breaks {SUCCESS_LINE}" in result.stdout
    assert result.stdout.count("red: 1 test(s) failed") == BREAKS
    assert result.stdout.count("tests/unit/test_planted.py::test_it") == BREAKS
    assert counted.read_text(encoding="utf-8") == str(2 * BREAKS)
    assert git(repository, "status", "--porcelain") == ""


@pytest.mark.parametrize(
    "what_pytest_did",
    [
        pytest.param(
            'echo "ERROR: file or directory not found: tests/gone.py"\nexit 4\n',
            id="4-usage-error",
        ),
        pytest.param(
            'echo "!!!! Interrupted: 1 error during collection !!!!"\nexit 2\n',
            id="2-collection-error",
        ),
        pytest.param('echo "INTERNALERROR> Traceback"\nexit 3\n', id="3-internal"),
        pytest.param(
            'echo "no tests ran in 0.01s"\nexit 5\n', id="5-nothing-collected"
        ),
        pytest.param(
            'echo "ERROR tests/unit/test_x.py::test_y - Boom"\nexit 1\n',
            id="1-without-a-FAILED-line",
        ),
    ],
)
def test_an_exit_that_is_not_a_test_failure_is_an_error_not_a_verdict(
    tmp_path: Path, what_pytest_did: str
) -> None:
    """Only exit 1 with a `FAILED` line is RED; everything else stops the run.

    Each row is a way for pytest to exit non-zero having judged nothing: a
    renamed test path (4), a collection error or interrupt (2), an internal
    error (3), an empty selection (5), and an exit 1 whose failures are ERRORs
    rather than FAILEDs - which is what a missing database or a broken fixture
    actually produces, and what `grep -c '^FAILED '` counts as zero. All five
    used to print `red: 0 test(s) failed` and reach the success line. Each row
    carries the exit code in its id, so a failure names the shape that broke.
    """
    repository = tmp_path / "repo"
    a_repository_in(repository, ORIGINAL)
    stub, counted = a_stub_green_on_the_baseline(what_pytest_did, tmp_path)

    result = run_script(repository, stub)

    assert result.returncode != 0
    assert "ERROR" in result.stderr
    assert SUCCESS_LINE not in result.stdout
    assert "red:" not in result.stdout
    # Stopped at the first break rather than carrying on to the next four.
    assert counted.read_text(encoding="utf-8") == "2"
    assert git(repository, "status", "--porcelain") == ""
