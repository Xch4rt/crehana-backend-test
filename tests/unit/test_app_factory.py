"""Unit tests for the FastAPI composition root."""

import pytest
from fastapi import FastAPI

from taskmanager.infrastructure.config.settings import Settings
from taskmanager.main import create_app

DATABASE_URL = "postgresql+psycopg://user:pass@localhost:5432/taskmanager"
JWT_SECRET = "b" * 32


def test_create_app_uses_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """create_app() builds a FastAPI instance from the settings it is given."""
    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
    monkeypatch.setenv("JWT_SECRET", JWT_SECRET)

    app = create_app(Settings(_env_file=None))

    assert isinstance(app, FastAPI)
    assert app.title == "Task Manager API"
    assert app.openapi()["info"]["version"] == "0.1.0"
