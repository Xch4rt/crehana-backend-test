"""The `make env` bootstrap script, driven as a real program.

`scripts/init-env.sh` is the evaluator's first command, so these tests run the
file itself through `sh` in a temporary directory rather than reimplementing its
decisions in Python. Nothing here asserts on the wording it prints: the
behaviour under test is the file it leaves behind.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

from taskmanager.infrastructure.config.settings import Settings

# tests/unit/test_env_bootstrap.py -> tests/unit -> tests -> repository root.
ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "init-env.sh"
ENV_EXAMPLE = ROOT / ".env.example"

# The floor `Settings` enforces, restated here only as the weaker of the two
# assertions the first test makes - the load-bearing one is that the generated
# file boots.
MINIMUM_SECRET_LENGTH = 32


def jwt_secret_of(text: str) -> str:
    """The value of the single JWT_SECRET assignment in an env file's text."""
    for line in text.splitlines():
        if line.startswith("JWT_SECRET="):
            return line.split("=", 1)[1]
    raise AssertionError("no JWT_SECRET line found")


def run_in(directory: Path) -> subprocess.CompletedProcess[str]:
    """Run the script with `directory` as its working directory."""
    return subprocess.run(
        ["sh", str(SCRIPT)],
        cwd=directory,
        check=True,
        capture_output=True,
        text=True,
    )


def an_example_in(directory: Path) -> Path:
    """Copy the shipped `.env.example` into `directory` and return the copy."""
    example = directory / ".env.example"
    shutil.copy(ENV_EXAMPLE, example)
    return example


def test_a_missing_env_is_created_with_a_secret_that_boots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no `.env`, the script writes one the application can start from.

    Booting the generated file is the honest assertion. A length check alone
    would also pass on the published placeholder, which is 34 characters and is
    exactly the value this script exists to stop installing.
    """
    an_example_in(tmp_path)

    run_in(tmp_path)

    written = tmp_path / ".env"
    secret = jwt_secret_of(written.read_text(encoding="utf-8"))
    assert secret != jwt_secret_of(ENV_EXAMPLE.read_text(encoding="utf-8"))
    assert len(secret) >= MINIMUM_SECRET_LENGTH

    # The process environment must not be able to stand in for the file, or the
    # developer's own exported secret would make this pass against a script that
    # wrote nothing.
    for key in ("JWT_SECRET", "DATABASE_URL", "TEST_DATABASE_URL"):
        monkeypatch.delenv(key, raising=False)
    assert Settings(_env_file=written).jwt_secret == secret


def test_the_placeholder_is_replaced_and_no_other_line_moves(tmp_path: Path) -> None:
    """A `.env` on the published placeholder changes in exactly one line.

    The developer's `.env` is their untracked file: a `DATABASE_URL` pointing at
    something other than the compose default must survive `make env`.
    """
    an_example_in(tmp_path)
    written = tmp_path / ".env"
    shutil.copy(ENV_EXAMPLE, written)
    before = written.read_text(encoding="utf-8").splitlines()

    run_in(tmp_path)

    after = written.read_text(encoding="utf-8").splitlines()
    assert len(after) == len(before)
    differing = [
        index
        for index, (old, new) in enumerate(zip(before, after, strict=True))
        if old != new
    ]
    assert len(differing) == 1
    assert after[differing[0]].startswith("JWT_SECRET=")
    assert jwt_secret_of("\n".join(after)) != jwt_secret_of("\n".join(before))
    assert [line for line in after if line.startswith("DATABASE_URL=")] == [
        line for line in before if line.startswith("DATABASE_URL=")
    ]


def test_an_existing_secret_is_never_overwritten(tmp_path: Path) -> None:
    """A real secret already in place is kept, so the target is safe to re-run."""
    an_example_in(tmp_path)
    written = tmp_path / ".env"
    mine = ENV_EXAMPLE.read_text(encoding="utf-8").replace(
        jwt_secret_of(ENV_EXAMPLE.read_text(encoding="utf-8")), "b" * 64
    )
    written.write_text(mine, encoding="utf-8")

    result = run_in(tmp_path)

    assert result.returncode == 0
    assert written.read_text(encoding="utf-8") == mine
