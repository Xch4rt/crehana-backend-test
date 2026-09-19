"""Unit tests for the FastAPI composition root."""

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from httpx import ASGITransport, AsyncClient
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
from tests.integration.test_dependencies import uow_probe_router
from tests.probe import probe_router

DATABASE_URL = "postgresql+psycopg://user:pass@localhost:5432/taskmanager"
JWT_SECRET = "b" * 32


def _declared_endpoints(router: APIRouter) -> list[tuple[str, str]]:
    """Every (method, path) a probe router declares, read off the router itself.

    Derived rather than written down. A literal list of prefixes is only as
    wide as the prefixes whoever wrote it happened to know about, which is how
    the guard below came to ignore `/_uow/*` entirely; asking the routers what
    they declare means a new probe route is covered the moment it exists.
    """
    return [
        (sorted(route.methods)[0], route.path)
        for route in router.routes
        if isinstance(route, APIRoute) and route.methods
    ]


# Both test-only routers in the project. A third one would have to be added
# here, and that is the remaining manual step - but it is one line in a file
# named for the guarantee, rather than a prefix buried inside an assertion.
PROBE_ENDPOINTS = _declared_endpoints(probe_router) + _declared_endpoints(
    uow_probe_router
)


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


async def test_production_app_answers_no_probe_route(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No test-only route is reachable on the app `create_app()` returns.

    Two things were wrong with the previous version of this guard, and the
    second one is why it is now a request rather than an inspection (review fix
    WR-06). It asserted that no path in `app.routes` started with `/_probe`,
    which missed the `/_uow/*` router this phase added - and it would have
    missed `/_probe` too: FastAPI wraps an included router in a single opaque
    object with no `path` attribute at all, so `getattr(route, "path", "")`
    answered `""` for exactly the routes the test existed to find. Including
    either probe router in `create_app` would have left it green.

    Asking the application to route the request is the assertion that cannot
    drift. It goes through the same stack a client uses, so it does not depend
    on how FastAPI happens to represent an included router this release, and a
    404 from the production app is the property itself rather than a proxy for
    it.
    """
    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
    monkeypatch.setenv("JWT_SECRET", JWT_SECRET)

    app = create_app(Settings(_env_file=None))

    # An empty list would make every assertion below vacuously true, which is
    # the failure mode this whole test is being rewritten to escape.
    assert PROBE_ENDPOINTS

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for method, path in PROBE_ENDPOINTS:
            response = await client.request(method, path)

            # The declared method, so a 405 can never stand in for a 404 and
            # make an actually-registered route look absent.
            assert response.status_code == 404, f"{method} {path} is reachable"
