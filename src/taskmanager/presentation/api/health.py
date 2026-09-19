"""`GET /health`: liveness and database readiness, as a status document (D-08).

Two shapes a reader may expect here are deliberately absent, and both would
break the same property.

This route never answers with the RFC 9457 body the rest of the API uses. A
database that is down is not the caller's error and not a business refusal - it
is the answer to the question the endpoint was asked - so D-08 specifies one
document with the same three members on both legs, and only the status line
changes. Routing the failing leg through the error translation would give the
two outcomes different shapes, and the container healthcheck, the compose
readiness gate and any future uptime probe would each have to parse both.

It also never returns a hand-built JSON response object. That would bypass the
declared response model, and with it the schema in `/openapi.json` that DOC-04
depends on. The documented way to change the status line while still returning
a model is the injected `Response` below, and that is what makes the 200 and the
503 provably one shape rather than two that happen to match today.

The endpoint is unauthenticated on purpose (D-08). Phase 5 must not protect it:
a healthcheck that needs a token cannot run from a `HEALTHCHECK` instruction,
and the document deliberately carries nothing an anonymous caller could not
already read from the OpenAPI schema.
"""

import asyncio
from typing import Annotated, Final, Literal

from fastapi import APIRouter, Depends, FastAPI, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

from taskmanager import __version__
from taskmanager.presentation.api.dependencies import get_engine

health_router = APIRouter(tags=["health"])

# D-08 asks for "a short timeout, about 2 s". It is bounded rather than left to
# the driver because an unreachable host and a *hung* one fail very differently:
# the first refuses in milliseconds, the second holds the request open until
# something upstream gives up, and a healthcheck that hangs reports nothing at
# all while consuming a connection slot per attempt.
DATABASE_PROBE_TIMEOUT_SECONDS: Final[float] = 2.0

# The injection is expressed as an annotation rather than as a default value,
# and that is not a style preference. flake8-bugbear's B008 rejects a call in an
# argument default, and `.flake8` whitelists the dotted spelling
# `fastapi.Depends` - which this module does not use, because every other import
# in the project is by name. The annotated form has no default to object to, it
# is the shape FastAPI's own documentation now leads with, and it gives the
# dependency a name Phase 4's routers can reuse instead of repeating the call.
EngineDependency = Annotated[AsyncEngine, Depends(get_engine)]


class HealthResponse(BaseModel):
    """The D-08 document: three members, always these three, in this order.

    Member order is not decoration. Pydantic serialises fields in declaration
    order, so declaring them here in the order D-08 writes them is what makes
    the contract mechanically true rather than aspirational - the same argument
    `errors/problem.py` makes for building its body as a literal.
    """

    status: Literal["ok", "degraded"]
    checks: dict[str, str]
    version: str


async def _database_is_reachable(engine: AsyncEngine) -> bool:
    """Ask the database one question, and report only whether it answered.

    The return type is the whole security property of this module (T-3-26). The
    driver's exception carries the host, the port, the user and sometimes the
    server's own diagnostics, and every one of those would reach an anonymous
    caller if the failure were reported rather than classified. It is caught,
    discarded, and turned into a `False` that says nothing about why.
    """
    try:
        async with asyncio.timeout(DATABASE_PROBE_TIMEOUT_SECONDS):
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
    except (TimeoutError, SQLAlchemyError):
        return False
    return True


@health_router.get(
    "/health",
    response_model=HealthResponse,
    responses={503: {"model": HealthResponse}},
)
async def health(response: Response, engine: EngineDependency) -> HealthResponse:
    """Liveness is answering at all; readiness is the database answering too.

    The 503 is the point rather than a formality: it is what the container
    healthcheck reads, so an API whose database has gone leaves the compose
    dependency gate closed instead of accepting traffic it cannot serve.
    """
    database_ok = await _database_is_reachable(engine)
    if not database_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse(
        status="ok" if database_ok else "degraded",
        checks={"database": "ok" if database_ok else "unavailable"},
        version=__version__,
    )


def register_health_routes(app: FastAPI) -> None:
    """Install the health router, from create_app().

    Imperative and called from the composition root, mirroring
    `register_exception_handlers`: the router is attached to the application the
    factory built, never to a module-level instance, so importing this module
    creates nothing.
    """
    app.include_router(health_router)
