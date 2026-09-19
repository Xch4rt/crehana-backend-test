"""The `/health` failure leg, proved with no database anywhere.

This module is a *unit* test of a route that talks to PostgreSQL, and the
apparent contradiction is the point. Every application below is built on a DSN
whose port nothing listens on, so the probe fails for real rather than through a
patched function - which is what lets these tests assert the two properties that
only exist on the failing path: the 503, and the fact that a driver's refusal
leaves no trace in the body (D-08, T-3-26). Mocking the engine would assert the
handler's `if`, not the translation of an actual database failure.

The 200 leg lives in `tests/integration/test_health.py`, where a real server can
answer, and one test there compares the two bodies member for member.

Nothing here needs a marker or a running container, so a developer with no
Docker still runs this file - deliberately, because it carries the leak
assertion, and a security property that only runs under a full stack is one that
gets skipped exactly when it matters.
"""

from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from taskmanager import __version__
from taskmanager.infrastructure.config.settings import Settings
from taskmanager.main import create_app

pytestmark = pytest.mark.unit

# Port 1 is reserved and unassignable, so a connection attempt is refused
# immediately rather than hanging: the failure this module needs, arriving fast.
UNREACHABLE_DATABASE_URL = "postgresql+psycopg://user:pass@127.0.0.1:1/nothing"
JWT_SECRET = "b" * 32

# The D-08 member list, in the order the contract promises.
MEMBERS = ["status", "checks", "version"]


def _app_with_no_database() -> FastAPI:
    """The production application, pointed at a database that cannot answer."""
    return create_app(
        Settings(
            _env_file=None,
            database_url=UNREACHABLE_DATABASE_URL,
            jwt_secret=JWT_SECRET,
        )
    )


@pytest.fixture
def unhealthy_app() -> FastAPI:
    """One application per test: the engine each builds is never disposed here."""
    return _app_with_no_database()


@pytest.fixture
async def unhealthy_client(unhealthy_app: FastAPI) -> AsyncIterator[AsyncClient]:
    """A client over the app above, in the project's transport-explicit form."""
    transport = ASGITransport(app=unhealthy_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def test_health_reports_503_when_the_database_probe_fails(
    unhealthy_client: AsyncClient,
) -> None:
    """An unreachable database is a 503 carrying the complete D-08 document."""
    response = await unhealthy_client.get("/health")

    assert response.status_code == 503

    body = response.json()

    assert list(body) == MEMBERS
    assert body["status"] == "degraded"
    assert body["checks"] == {"database": "unavailable"}
    assert body["version"] == __version__


async def test_the_unavailable_body_leaks_no_driver_detail(
    unhealthy_client: AsyncClient,
) -> None:
    """The refusal is classified, never reported: nothing of the DSN survives.

    Each needle is a distinct disclosure the naive implementation makes. The
    driver name and a traceback would come from re-raising; the password, the
    host and the whole connection string would come from formatting the
    exception, which is what a driver's own message does (T-3-26).
    """
    response = await unhealthy_client.get("/health")

    leaked = [
        needle
        for needle in ("psycopg", "Traceback", "pass", "127.0.0.1", "nothing")
        if needle in response.text
    ]

    assert leaked == []


async def test_health_is_not_problem_json(unhealthy_client: AsyncClient) -> None:
    """Even failing, `/health` is a status document and not an error (D-08)."""
    response = await unhealthy_client.get("/health")

    content_type = response.headers["content-type"]

    assert content_type.startswith("application/json")
    assert "problem" not in content_type


def test_health_appears_in_the_openapi_document(unhealthy_app: FastAPI) -> None:
    """Both legs are published, so a client can be generated against either.

    The 503 being *documented* is the part that matters. A schema listing only
    the 200 would describe an endpoint that cannot fail, and the failure is the
    half the container healthcheck actually reads.
    """
    paths = unhealthy_app.openapi()["paths"]

    assert "/health" in paths
    assert set(paths["/health"]["get"]["responses"]) == {"200", "503"}


def test_creating_the_app_opens_no_connection() -> None:
    """Building the application against a dead DSN raises nothing at all.

    This is the property `tests/conftest.py` and `tests/unit/test_app_factory.py`
    have depended on silently since Phase 1, and the one that a migration or a
    `SELECT` moved into the composition root would destroy - so it is asserted
    here now that `create_app` really does build an engine (D-06).
    """
    app = _app_with_no_database()

    assert app.state.database.engine.pool.checkedout() == 0


async def test_the_lifespan_disposes_the_engine(unhealthy_app: FastAPI) -> None:
    """Shutdown releases the pool; startup does nothing (D-06, T-3-25).

    Disposal is observable without a server: `dispose()` replaces the engine's
    pool with a fresh one, so the object identity before and after is the
    evidence. Asserting on a connection count instead would pass vacuously here,
    where the count was zero to begin with.
    """
    resources = unhealthy_app.state.database
    pool_before = resources.engine.pool

    async with unhealthy_app.router.lifespan_context(unhealthy_app):
        # The startup half is empty by design; reaching here is the assertion.
        assert resources.engine.pool is pool_before

    assert resources.engine.pool is not pool_before
