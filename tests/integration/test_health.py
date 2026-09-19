"""`GET /health` against the real container: roadmap SC-1 and DOCK-03.

The 503 leg is pinned in `tests/unit/presentation/test_health.py`, where no
database exists. This module is the other half, and it is the half the evaluator
performs by hand: `docker compose up`, then open `/health` and read `"database":
"ok"`. The compose dependency gate and the Dockerfile healthcheck both read this
same 200, so an endpoint that answered 200 without asking the database would
make every readiness guarantee in the phase decorative.

The application under test is built here rather than taken from the unit `app`
fixture, and that is not duplication: the shared fixture's DSN is a syntactically
valid fiction pointed at nothing, chosen so unit tests need no server. A probe
against it can only fail. These tests need an engine aimed at the same database
the rest of the integration suite migrated.

Each application is entered through its own lifespan, so the engine it built is
disposed when the test ends - the production shutdown path, exercised rather
than assumed.
"""

from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from taskmanager import __version__
from taskmanager.infrastructure.config.settings import Settings
from taskmanager.main import create_app

pytestmark = pytest.mark.integration

JWT_SECRET = "b" * 32

# Port 1 is unassignable, so the comparison case below fails fast and for real.
UNREACHABLE_DATABASE_URL = "postgresql+psycopg://user:pass@127.0.0.1:1/nothing"

# The D-08 member list, in the order the contract promises.
MEMBERS = ["status", "checks", "version"]


def _app_for(database_url: str) -> FastAPI:
    """The production application, aimed at whichever database is named."""
    return create_app(
        Settings(_env_file=None, database_url=database_url, jwt_secret=JWT_SECRET)
    )


async def _body_of_health(app: FastAPI) -> tuple[int, dict[str, Any]]:
    """The status and body `/health` answers with, engine disposed afterwards.

    The body is annotated `dict[str, Any]` rather than something narrower for
    the same reason every other API test in this project reads a decoded
    payload loosely: the point of the assertions below is what the *wire*
    carries, and narrowing it here would describe the contract in the test
    instead of checking it.
    """
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")
    body: dict[str, Any] = response.json()
    return response.status_code, body


@pytest.fixture
async def healthy_client(
    _require_database: None, database_url: str
) -> AsyncIterator[AsyncClient]:
    """A client over an application pointed at the running test database."""
    app = _app_for(database_url)
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


async def test_health_reports_ok_against_a_reachable_database(
    healthy_client: AsyncClient,
) -> None:
    """A database that answers `SELECT 1` makes the whole document `ok`."""
    response = await healthy_client.get("/health")

    assert response.status_code == 200

    body = response.json()

    assert list(body) == MEMBERS
    assert body["status"] == "ok"
    assert body["checks"]["database"] == "ok"
    assert body["version"] == __version__


async def test_the_healthy_and_unhealthy_bodies_have_the_same_shape(
    _require_database: None, database_url: str
) -> None:
    """D-08's "the same body shape" becomes an assertion instead of a claim.

    Both documents are produced in this one test, from two applications that
    differ in nothing but their DSN, so the comparison cannot drift with a
    literal copied from somewhere else. A future change that gave the failing
    leg an extra member - a reason, a retry hint, an error - fails here, which
    is the only place it would be noticed before a client broke on it.
    """
    healthy_status, healthy_body = await _body_of_health(_app_for(database_url))
    degraded_status, degraded_body = await _body_of_health(
        _app_for(UNREACHABLE_DATABASE_URL)
    )

    assert (healthy_status, degraded_status) == (200, 503)
    assert list(healthy_body) == list(degraded_body) == MEMBERS
    assert set(healthy_body["checks"]) == set(degraded_body["checks"])


async def test_health_requires_no_authentication(
    healthy_client: AsyncClient,
) -> None:
    """No credential of any kind, and still 200 (D-08).

    Recorded here because Phase 5 is the phase that could break it: an
    authentication dependency applied to the whole application, rather than to
    the routers that need it, would turn every container healthcheck into a 401
    and the compose readiness gate would never open.
    """
    response = await healthy_client.get("/health")

    assert "authorization" not in response.request.headers
    assert response.status_code == 200
