"""Unit tests for the environment-backed application settings."""

import secrets
from pathlib import Path

import pytest
from pydantic import ValidationError

from taskmanager.infrastructure.config.settings import Settings, get_settings

pytestmark = pytest.mark.unit

# A syntactically valid DSN and an obviously fake 32-character secret. Both are
# injected through monkeypatch so no test ever depends on the developer's shell.
ENV = {
    "DATABASE_URL": "postgresql+psycopg://user:pass@localhost:5432/taskmanager",
    "JWT_SECRET": "a" * 32,
}

# tests/unit/test_settings.py -> tests/unit -> tests -> repository root.
ENV_EXAMPLE = Path(__file__).resolve().parents[2] / ".env.example"


def test_settings_read_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Declared fields are read from the process environment, defaults apply."""
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)

    settings = Settings(_env_file=None)

    assert settings.database_url == ENV["DATABASE_URL"]
    assert settings.jwt_secret == ENV["JWT_SECRET"]
    assert settings.jwt_algorithm == "HS256"
    assert settings.jwt_expire_minutes == 30


def test_missing_secret_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """A process without JWT_SECRET refuses to start instead of defaulting."""
    monkeypatch.setenv("DATABASE_URL", ENV["DATABASE_URL"])
    monkeypatch.delenv("JWT_SECRET", raising=False)

    with pytest.raises(ValidationError) as excinfo:
        Settings(_env_file=None)

    assert "jwt_secret" in str(excinfo.value).lower()


def test_short_secret_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """A JWT_SECRET below the 32-character floor is a boot-time failure.

    The boundary is asserted at 31 rather than at an obviously tiny value, so
    the test still fails if the floor is quietly lowered back towards PyJWT's
    32-byte HS256 threshold (D-26, T-5-02). There is deliberately no
    `pytest.warns` block here: the point of the floor is that
    `InsecureKeyLengthWarning` becomes unreachable, not that it is caught.
    """
    monkeypatch.setenv("DATABASE_URL", ENV["DATABASE_URL"])
    monkeypatch.setenv("JWT_SECRET", "a" * 31)

    with pytest.raises(ValidationError) as excinfo:
        Settings(_env_file=None)

    assert "jwt_secret" in str(excinfo.value).lower()
    assert "at least 32 characters" in str(excinfo.value)


def test_a_secret_exactly_at_the_floor_is_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The floor is inclusive: 32 characters boots, which is what CI relies on."""
    monkeypatch.setenv("DATABASE_URL", ENV["DATABASE_URL"])
    monkeypatch.setenv("JWT_SECRET", "a" * 32)

    assert Settings(_env_file=None).jwt_secret == "a" * 32


def shipped_placeholder() -> str:
    """The JWT_SECRET value `.env.example` actually ships.

    Read from the file rather than restated here, so the tests below track
    whatever the repository publishes instead of a copy that can go stale.
    """
    for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        if line.startswith("JWT_SECRET="):
            return line.split("=", 1)[1]
    raise AssertionError("no JWT_SECRET line in .env.example")


def test_the_shipped_placeholder_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """The value published in this repository cannot boot the application.

    It is 34 characters, so `min_length=32` accepted it and the documented
    setup signed every token with a string any reader of the public repository
    already has (ADR-084). The refusal names the remedy, so the message is the
    whole fix rather than half of it.
    """
    monkeypatch.setenv("DATABASE_URL", ENV["DATABASE_URL"])
    monkeypatch.setenv("JWT_SECRET", shipped_placeholder())

    with pytest.raises(ValidationError) as excinfo:
        Settings(_env_file=None)

    assert "jwt_secret" in str(excinfo.value).lower()
    assert "make env" in str(excinfo.value)


def test_a_half_edited_placeholder_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Clearing the length floor is not enough: the prefix is the rule."""
    monkeypatch.setenv("DATABASE_URL", ENV["DATABASE_URL"])
    monkeypatch.setenv("JWT_SECRET", "replace-me-later-i-promise-this-is-long-enough")

    with pytest.raises(ValidationError) as excinfo:
        Settings(_env_file=None)

    assert "jwt_secret" in str(excinfo.value).lower()


def test_a_generated_secret_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    """What `make env` writes boots, which is the other half of the decision."""
    generated = secrets.token_urlsafe(32)
    monkeypatch.setenv("DATABASE_URL", ENV["DATABASE_URL"])
    monkeypatch.setenv("JWT_SECRET", generated)

    assert Settings(_env_file=None).jwt_secret == generated


@pytest.mark.parametrize("algorithm", ["none", "HS256 ", "RS256", "HS512"])
def test_the_algorithm_is_a_closed_set(
    monkeypatch: pytest.MonkeyPatch, algorithm: str
) -> None:
    """Anything but HS256 fails at boot instead of at the first login (WR-03).

    `none` and `RS256` made every login a 500, a trailing space is an ordinary
    `.env` typo, and HS512 booted against a floor sized for a 32-byte key.
    """
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("JWT_ALGORITHM", algorithm)

    with pytest.raises(ValidationError) as excinfo:
        Settings(_env_file=None)

    assert "jwt_algorithm" in str(excinfo.value).lower()


def test_test_database_url_defaults_to_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """The test-only DSN is optional: nothing in production depends on it."""
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)

    assert Settings(_env_file=None).test_database_url is None


def test_test_database_url_is_read_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When TEST_DATABASE_URL is exported it is read back verbatim (D-04)."""
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)
    explicit = "postgresql+psycopg://user:pass@localhost:5432/somewhere_else"
    monkeypatch.setenv("TEST_DATABASE_URL", explicit)

    assert Settings(_env_file=None).test_database_url == explicit


def test_get_settings_is_cached(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """get_settings() hands back one identical instance per process."""
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)

    # Clear before, so no earlier test's environment is still cached, and clear
    # after, so this test's Settings object does not leak into a later one.
    # The working directory moves to an empty one first, because Settings
    # declares `env_file=".env"` as a *relative* name: a developer host with a
    # real `.env` beside the repository root would otherwise have get_settings()
    # read that untracked file while the comparison object below does not, which
    # makes this test's outcome depend on a file no gate can see.
    monkeypatch.chdir(tmp_path)
    get_settings.cache_clear()
    first = get_settings()
    second = get_settings()
    try:
        assert first is second
        # The cached instance carries the current environment, not a stale one.
        assert first == Settings(_env_file=None)
        assert first.database_url == ENV["DATABASE_URL"]
    finally:
        get_settings.cache_clear()


def test_env_example_documents_every_field() -> None:
    """.env.example documents every declared field and nothing else."""
    documented = {
        line.split("=", 1)[0].strip()
        for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines()
        if "=" in line and not line.strip().startswith("#")
    }

    assert documented == {name.upper() for name in Settings.model_fields}
