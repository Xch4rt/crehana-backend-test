"""Composition root: builds the FastAPI application.

`create_app` is a factory rather than a module-level `app = create_app()`.
A module-level instance would evaluate the settings at import time, which makes
`import taskmanager.main` crash in any environment without JWT_SECRET -
including mypy's, import-linter's and a plain `docker build`. The container
runs `uvicorn --factory taskmanager.main:create_app`.
"""

from fastapi import FastAPI

from taskmanager.infrastructure.config.settings import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the application, optionally with explicitly injected settings."""
    resolved = settings or get_settings()
    return FastAPI(
        title=resolved.app_name,
        version="0.1.0",
        openapi_url="/openapi.json",
    )
