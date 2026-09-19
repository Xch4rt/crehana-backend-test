"""The marker partition's guard, plus the app and its two HTTP clients.

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

# The two buckets D-13 offers, and the only two `pytest.ini` registers. Every
# collected test is in exactly one of them; see the guard below.
REQUIRED_MARKERS = ("unit", "integration")


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Fail the run if any collected test carries neither marker (D-13).

    `--strict-markers` refuses an *unregistered* marker; nothing in pytest
    refuses a *missing* one. So without this, a new test module joins the suite
    outside both `-m unit` and `-m integration`: `make test-unit` would not run
    it, a `-m integration` selection would not run it, and the only invocation
    that would is the full `pytest` nobody uses while writing code. It would be
    green, collected, and absent from every selection anyone actually types -
    the quietest way for a test to stop being run.

    `tryfirst=True` pins an ordering rather than fixing a bug, and the
    difference was measured rather than assumed. pytest's own mark plugin
    implements this same hook to apply `-m`, and it *removes* the deselected
    items from the list - so running after it, an unmarked item would already be
    gone and a `-m unit` run would report nothing wrong about the very file the
    rule exists for. On pytest 9 a conftest implementation is in fact called
    before the builtin plugin's, so the guard fires under `-m unit` with the
    decorator removed too (observed, plan 06-04). It stays because relying on
    registration order for that is relying on something no version promises, and
    the failure it would produce is a silent hole rather than an error.

    The offending node ids are reported rather than counted, because a count is
    a puzzle: the fix is to put one line in a named module, and the message
    should say which.

    This guard is itself the gate. It adds no hook to `.pre-commit-config.yaml`
    and no step to `.github/workflows/ci.yml` - it rides inside `pytest`, which
    the hook set, the Docker test stage and CI all already run. CLAUDE.md's
    two-places rule applies to a gate that needs its own invocation.
    """
    unmarked = [
        item.nodeid
        for item in items
        if all(item.get_closest_marker(name) is None for name in REQUIRED_MARKERS)
    ]

    if unmarked:
        raise pytest.UsageError(
            "Every collected test must carry exactly one of the markers "
            f"{REQUIRED_MARKERS}, as a module-level `pytestmark` (D-13). "
            "Add `pytestmark = pytest.mark.unit` to a test that needs neither "
            "PostgreSQL nor HTTP through a live engine, and "
            "`pytest.mark.integration` to one that does. Unmarked: "
            f"{unmarked}"
        )


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
