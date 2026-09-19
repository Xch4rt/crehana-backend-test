"""Unit tests for the FastAPI composition root."""

import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from taskmanager import __version__
from taskmanager.domain.exceptions import DomainError
from taskmanager.infrastructure.config.settings import Settings
from taskmanager.main import create_app
from taskmanager.presentation.api.errors.handlers import (
    handle_domain_error,
    handle_http_exception,
    handle_unexpected_error,
    handle_validation_error,
)

DATABASE_URL = "postgresql+psycopg://user:pass@localhost:5432/taskmanager"
JWT_SECRET = "b" * 32


def test_create_app_uses_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """create_app() builds a FastAPI instance from the settings it is given."""
    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
    monkeypatch.setenv("JWT_SECRET", JWT_SECRET)

    app = create_app(Settings(_env_file=None))

    assert isinstance(app, FastAPI)
    assert app.title == "Task Manager API"
    assert app.openapi()["info"]["version"] == __version__


def test_create_app_registers_exception_handlers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """create_app() installs all four handlers, and ours win over FastAPI's."""
    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
    monkeypatch.setenv("JWT_SECRET", JWT_SECRET)

    app = create_app(Settings(_env_file=None))

    registered = app.exception_handlers
    assert {
        DomainError,
        RequestValidationError,
        StarletteHTTPException,
        Exception,
    } <= set(registered)
    assert registered[DomainError] is handle_domain_error
    assert registered[Exception] is handle_unexpected_error
    # FastAPI installs defaults for these two keys at construction time, so
    # identity - not mere presence - is what proves the override took effect.
    assert registered[StarletteHTTPException] is handle_http_exception
    assert registered[RequestValidationError] is handle_validation_error


def test_production_app_has_no_probe_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    """The test-only probe router is never part of the app create_app() returns."""
    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
    monkeypatch.setenv("JWT_SECRET", JWT_SECRET)

    app = create_app(Settings(_env_file=None))

    assert not any(
        getattr(route, "path", "").startswith("/_probe") for route in app.routes
    )
