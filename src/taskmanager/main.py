"""Composition root: builds the FastAPI application.

`create_app` is a factory rather than a module-level `app = create_app()`.
A module-level instance would evaluate the settings at import time, which makes
`import taskmanager.main` crash in any environment without JWT_SECRET -
including mypy's, import-linter's and a plain `docker build`. The container
runs `uvicorn --factory taskmanager.main:create_app`.

Building the application touches no database, and that is a decision rather than
an accident (D-06). No schema migration runs here and no statement is executed
here, on startup or anywhere else in this module: `docker/entrypoint.sh` owns
`alembic upgrade head` and runs it once, before the server is exec'd. Two things
follow. Every unit test in this suite can build the real application against a
syntactically valid but fictional DSN with no server running anywhere, which is
what `tests/conftest.py` has relied on since Phase 1; and several replicas
started at the same moment cannot race each other through the same migration.

What the composition root does own is the engine's lifetime. It builds the
engine, hands the application a typed container holding it, and disposes it in
the lifespan's shutdown half - disposal is symmetrical with construction, so it
belongs to whoever constructed it. Without that half, a process asked to stop
would leave pooled connections open on the server, each one holding the
credentials it authenticated with (T-3-25).
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from taskmanager import __version__
from taskmanager.infrastructure.config.settings import Settings, get_settings
from taskmanager.infrastructure.db.engine import create_database_resources
from taskmanager.presentation.api.errors.handlers import register_exception_handlers
from taskmanager.presentation.api.health import register_health_routes


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the application, optionally with explicitly injected settings."""
    resolved = settings or get_settings()
    resources = create_database_resources(resolved)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        """Nothing on the way up; the engine is released on the way down.

        The startup half is empty and must stay empty - that is D-06 again.
        Shutdown closes the pool through the container this closure captured
        rather than through `app.state`, because a value read back off the
        application's state arrives untyped, and there is no reason to give up
        the type of an object this same function just built.
        """
        yield
        await resources.engine.dispose()

    app = FastAPI(
        title=resolved.app_name,
        version=__version__,
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )
    app.state.database = resources
    register_exception_handlers(app)
    register_health_routes(app)
    return app
