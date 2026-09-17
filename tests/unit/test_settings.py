"""Unit tests for the environment-backed application settings."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from taskmanager.infrastructure.config.settings import Settings, get_settings

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
    """A JWT_SECRET below the 16-character floor is a boot-time failure."""
    monkeypatch.setenv("DATABASE_URL", ENV["DATABASE_URL"])
    monkeypatch.setenv("JWT_SECRET", "short")

    with pytest.raises(ValidationError) as excinfo:
        Settings(_env_file=None)

    assert "at least 16 characters" in str(excinfo.value)


def test_get_settings_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_settings() hands back one identical instance per process."""
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)

    # Clear before, so no earlier test's environment is still cached, and clear
    # after, so this test's Settings object does not leak into a later one.
    get_settings.cache_clear()
    first = get_settings()
    second = get_settings()
    try:
        assert first is second
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
