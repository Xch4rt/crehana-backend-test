"""Fixtures shared by the API-level tests: the app and its two HTTP clients.

Three shapes that a reader may expect here are deliberately absent: the
asyncio-specific fixture decorator, the per-test asyncio marker, and a
hand-rolled replacement for pytest-asyncio's own loop fixture. `pytest.ini`
sets `asyncio_mode = auto` and `asyncio_default_fixture_loop_scope = function`,
which already covers both async tests and async-generator fixtures, and the
loop override in particular has been removed from pytest-asyncio itself.
"""

from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from taskmanager.infrastructure.config.settings import Settings
from taskmanager.main import create_app
from tests.probe import probe_router

# The same syntactically valid DSN and obviously fake secret
# `tests/unit/test_app_factory.py` uses. Both are injected through monkeypatch,
# so no test depends on the developer's shell.
DATABASE_URL = "postgresql+psycopg://user:pass@localhost:5432/taskmanager"
JWT_SECRET = "b" * 32


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    """The production app plus the probe router, which only tests ever see."""
    # `database_url` and `jwt_secret` have no default at all, so `Settings`
    # raises without these two - the env injection is not optional ceremony.
    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
    monkeypatch.setenv("JWT_SECRET", JWT_SECRET)

    application = create_app(Settings(_env_file=None))
    application.include_router(probe_router)  # tests only - never production

    return application


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """The default client: an exception escaping the app fails the test."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client


@pytest.fixture
async def tolerant_client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """For the unexpected-error case only: the 500 is re-raised by design.

    Starlette's ServerErrorMiddleware sends the installed 500 handler's
    response and then re-raises the exception, so that servers can log it and
    test clients can choose to assert on it. Suppressing that here is what lets
    the D-08 body be inspected. Never fold this into the shared `client`
    fixture: a tolerant default would silently absorb a genuine 500 in every
    other test in the suite.
    """
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client
