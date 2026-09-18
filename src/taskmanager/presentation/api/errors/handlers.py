"""The single exception-handling point required by ARC-07.

Four handlers, one body builder, registered imperatively by `create_app()`.
Three shapes here look wrong until you know what each of them prevents.

Every handler annotates its exception parameter with the bare `Exception` type
and narrows on its first line with an `isinstance` assertion. The narrower
`exc: DomainError` annotation is the obvious form and mypy strict rejects it:
Starlette's handler type is
`Callable[[Request, Exception], Response | Awaitable[Response]]`, callable
parameters are contravariant, and a function that only accepts `DomainError` is
therefore not one of those. The rejected fixes were a type-ignore comment,
which would hide a real variance rule, and `if not isinstance(...): raise`,
which adds four partial branches no test can reach while the 100% presentation
coverage gate forbids a suppression comment. `assert` narrows for mypy and
coverage.py does not count it as a branch. That makes these asserts
load-bearing, so nothing may run this application with assertions disabled:
no `-O` flag and no `PYTHONOPTIMIZE` appears in the `Dockerfile`, the
`Makefile` or `ci.yml` today, and none should be added.

Registration is imperative: `register_exception_handlers` below calls
`add_exception_handler` on the application object it is given. The decorator
form FastAPI also offers is deliberately absent, because it can only be applied
to a module-level application instance, which `main.py`'s own docstring
forbids: evaluating the settings at import time makes `import taskmanager.main`
crash wherever JWT_SECRET is unset, including under mypy, import-linter and
`docker build`.

Registration is on `starlette.exceptions.HTTPException`, not on
`fastapi.HTTPException`. The FastAPI class is a subclass of the Starlette one,
so the Starlette registration catches both through the same MRO walk, *plus*
the 404 for an unknown route and the 405 for a wrong verb, which Starlette
raises internally and which never pass through FastAPI's class at all. D-09
wants those two translated as well.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from taskmanager.domain.exceptions import DomainError
from taskmanager.presentation.api.errors.mapping import status_for
from taskmanager.presentation.api.errors.problem import problem

logger = logging.getLogger(__name__)


async def handle_domain_error(request: Request, exc: Exception) -> JSONResponse:
    """Translate any `DomainError` - base or grandchild - into problem+json."""
    assert isinstance(exc, DomainError)
    status = status_for(exc)
    response = problem(
        code=exc.code,
        title=exc.title,
        status=status,
        # `exc.message`, never `str(exc)`: the base keeps a 2-tuple `args`, so
        # the stringified form of a sloppier hierarchy would drag the details
        # dict into the response body.
        detail=exc.message,
        instance=request.url.path,
        errors=exc.details or None,
    )
    # RFC 9110 section 15.5.2: a server generating a 401 MUST send a challenge.
    # `handle_http_exception` gets this for free by forwarding `exc.headers`,
    # but a domain `AuthenticationError` carries no headers of its own, and
    # `ports/security.py` already specifies that Phase 5's `TokenService.decode`
    # raises exactly that. The challenge therefore belongs here, at the one
    # place a business failure becomes an HTTP response, rather than in the
    # adapter that has not been written yet.
    if status == 401:
        response.headers["WWW-Authenticate"] = "Bearer"
    return response


async def handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    """Translate a request-validation failure into 422 problem+json (D-07)."""
    assert isinstance(exc, RequestValidationError)
    return problem(
        code="validation_error",
        title="Request validation failed",
        status=422,
        detail="The request payload failed validation.",
        instance=request.url.path,
        # Only `loc`, `msg` and `type` survive. Pydantic's raw entries also
        # carry the client's own submitted value, and some error kinds add a
        # context dict and a documentation link; D-07 forbids exposing any of
        # them, which is exactly what makes this a translation rather than a
        # pass-through of the framework's internal shape.
        errors=[
            {
                "field": ".".join(str(part) for part in error["loc"]),
                "message": error["msg"],
                "type": error["type"],
            }
            for error in exc.errors()
        ],
    )


async def handle_http_exception(request: Request, exc: Exception) -> JSONResponse:
    """Translate a Starlette `HTTPException`, headers and all, into problem+json."""
    assert isinstance(exc, StarletteHTTPException)
    response = problem(
        code="http_error",
        title="HTTP error",
        status=exc.status_code,
        detail=str(exc.detail),
        instance=request.url.path,
    )
    # Starlette's own handler forwards these; a replacement must too, or a 401
    # loses WWW-Authenticate and a 405 loses Allow - both of which are part of
    # the HTTP contract rather than decoration.
    for key, value in (exc.headers or {}).items():
        response.headers[key] = value
    return response


async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    """Answer any unhandled exception with the one fixed 500 body (D-08)."""
    # The traceback goes to the log and nowhere else. `exc_info=exc` rather
    # than `logger.exception(...)` so the record does not depend on there being
    # an ambient exception context when the handler runs.
    logger.error(
        "Unhandled exception while handling %s %s",
        request.method,
        request.url.path,
        exc_info=exc,
    )
    # Identical in every environment: no traceback, no exception message, no
    # `errors` member and no branch on the configured environment. That last
    # point is also why this module imports nothing from `infrastructure`.
    return problem(
        code="internal_error",
        title="Internal server error",
        status=500,
        detail="An unexpected error occurred",
        instance=request.url.path,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Install the single exception-handling point of ARC-07, from create_app().

    The `HTTPException` and `RequestValidationError` registrations replace the
    defaults FastAPI installs at construction time - handlers live in a dict
    keyed by exception class, so re-registering the same key overrides it - and
    the `Exception` registration is what Starlette lifts onto
    `ServerErrorMiddleware` as the outermost catch-all.
    """
    app.add_exception_handler(DomainError, handle_domain_error)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, handle_http_exception)
    app.add_exception_handler(Exception, handle_unexpected_error)
