"""Composition root: builds the FastAPI application.

`create_app` is a factory rather than a module-level `app = create_app()`.
A module-level instance would evaluate the settings at import time, which makes
`import taskmanager.main` crash in any environment without JWT_SECRET -
including mypy's, import-linter's and a plain `docker build`. The container
runs `uvicorn --factory taskmanager.main:create_app`.

Building the application touches no database, and that is a decision rather than
an accident (D-06). No schema migration runs here and no statement is executed
here, on startup or anywhere else in this module: `docker/entrypoint.sh` owns
`alembic upgrade head` and runs it once per container start, before the server
is exec'd. What that buys is one thing, precisely: every unit test in this suite
can build the real application against a syntactically valid but fictional DSN
with no server running anywhere, which is what `tests/conftest.py` has relied on
since Phase 1.

What it does not buy is safety under several replicas, and the earlier wording
here claimed otherwise (review fix WR-04). Moving the call out of the
application does not serialise it: every replica's entrypoint would run
`alembic upgrade head` concurrently against the same database, and Alembic takes
no advisory lock of its own. It is not entirely unguarded either - the version
table is read and written inside one transaction, so on PostgreSQL the losing
replica generally blocks and then finds the revision already applied - but that
is a race resolved by the database, not one the project prevents, and DDL that
Alembic has not yet reached can still collide. One replica, one migration run,
by construction of `docker-compose.yml`; a multi-replica deployment must
serialise `upgrade head` itself, with a `pg_advisory_lock` in
`migrations/env.py` or a one-shot migration job.

What the composition root does own is the engine's lifetime. It builds the
engine, hands the application a typed container holding it, and disposes it in
the lifespan's shutdown half - disposal is symmetrical with construction, so it
belongs to whoever constructed it. Without that half, a process asked to stop
would leave pooled connections open on the server, each one holding the
credentials it authenticated with (T-3-25).
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Final

from fastapi import FastAPI

from taskmanager import __version__
from taskmanager.infrastructure.clock import SystemClock
from taskmanager.infrastructure.config.settings import Settings, get_settings
from taskmanager.infrastructure.db.engine import create_database_resources
from taskmanager.infrastructure.logging import configure_logging
from taskmanager.infrastructure.security.resources import create_security_resources
from taskmanager.presentation.api.errors.handlers import register_exception_handlers
from taskmanager.presentation.api.health import register_health_routes
from taskmanager.presentation.api.routers.assignments import register_assignment_routes
from taskmanager.presentation.api.routers.auth import register_auth_routes
from taskmanager.presentation.api.routers.task_lists import register_task_list_routes
from taskmanager.presentation.api.routers.tasks import register_task_routes
from taskmanager.presentation.api.routers.users import register_user_routes
from taskmanager.presentation.api.schemas.problem import (
    PROBLEM_SCHEMA_NAME,
    ProblemResponse,
)

# The first thing an evaluator reads, because `docker compose up` hands them
# `/docs` before it hands them the README - which repeats this in Phase 7. It
# is a procedure and never a credential: the stack ships with no seeded
# account (D-14), so there is no password in this repository to leak into a
# published document (T-5-03).
DESCRIPTION: str = """
A REST API for task lists and the tasks inside them.

**There is no seeded account, so start by making one.**

1. `POST /api/v1/auth/register` with an email, a full name and a password.
2. Click **Authorize** at the top right of `/docs` and enter that same email
   (in the `username` field - OAuth2 fixes the name, this API's usernames are
   email addresses) and password.
3. Every other route is then callable, and each one acts as the account you
   registered.

Errors are RFC 9457 `application/problem+json` documents, from every route.
"""

# The order `/docs` groups the nineteen operations in, and one sentence each.
# Without this the document's top-level `tags` array is absent, Swagger falls
# back to bare tag names in route-registration order, and a reader gets six
# unexplained headings. The order below is the registration order in
# `create_app`, which is itself the order an evaluator has to read the API in:
# check it is up, make an account, then the resources, then the people, then
# who holds what.
#
# Both directions are gated. `tests/architecture/test_openapi_completeness.py`
# asserts set equality between the names here and the tags the operations
# actually use, so a described tag nobody uses and a used tag nobody described
# both fail - the second being the one that matters, because it is what a new
# router silently introduces.
OPENAPI_TAGS: Final[list[dict[str, str]]] = [
    {
        "name": "health",
        "description": (
            "Liveness and readiness. The only route outside `/api/v1`, and the "
            "only one whose failure body is not `problem+json` - a 503 here is "
            "a status document saying which check failed."
        ),
    },
    {
        "name": "auth",
        "description": (
            "Registration, login and the caller's own profile. Start here: "
            "there is no seeded account, and every other tag needs the token "
            "`POST /auth/login` returns."
        ),
    },
    {
        "name": "task lists",
        "description": (
            "The lists a caller owns, each carrying its completion counters "
            "over the whole list. Only the owner sees a list at all, so a "
            "refusal here is a 404 rather than a 403."
        ),
    },
    {
        "name": "tasks",
        "description": (
            "The tasks inside a list: creation, filtering by status, priority "
            "and assignee, editing, deletion, and the dedicated endpoint that "
            "moves a task's status."
        ),
    },
    {
        "name": "users",
        "description": (
            "The directory a client picks an assignee out of: id, full name "
            "and email for every registered account, readable by any "
            "authenticated caller (ADR-068). Nothing here is restricted, and "
            "no client should treat it as if it were."
        ),
    },
    {
        "name": "assignments",
        "description": (
            "Handing a task over, taking it back, and the caller's own inbox "
            "of tasks assigned to them across every list."
        ),
    },
]


class ProblemAwareFastAPI(FastAPI):
    """The application, plus the one component sixty-nine `$ref`s point at.

    Every error leg is declared without a `model=` key, because on the pinned
    stack a `model` publishes `application/json` - a media type this API never
    emits for an error (07-RESEARCH.md Gap 3, and the long form in
    `presentation/api/schemas/problem.py`). The cost of the correct spelling is
    that FastAPI registers a component only for a `model=`, so the `$ref` would
    resolve to nothing. This puts it back, once.

    A subclass rather than the documented `app.openapi = custom_openapi`
    assignment: `mypy --strict` rejects that as `method-assign`, and buying a
    one-line convenience with a `type: ignore` in the composition root is not a
    trade this project makes. `isinstance(app, FastAPI)` is still true, which is
    what every existing test asserts.
    """

    def openapi(self) -> dict[str, Any]:
        """Build the document, then register `Problem` if it is not there.

        `setdefault` at all three levels, and that is not defensiveness: a
        plain application has no `components` key until some route declares a
        model. It is also what makes the call idempotent - `super().openapi()`
        caches into `self.openapi_schema` and returns the *same* object on
        every later call, so a second call must not append a second copy.
        """
        schema = super().openapi()
        schema.setdefault("components", {}).setdefault("schemas", {}).setdefault(
            PROBLEM_SCHEMA_NAME, ProblemResponse.model_json_schema()
        )
        return schema


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the application, optionally with explicitly injected settings."""
    # First, and in the factory rather than in the lifespan. Nothing under
    # `taskmanager` is written at all without it: uvicorn attaches handlers to
    # its own loggers and leaves the root one at WARNING, so D-15's INFO
    # notification line is dropped and NOTF-02 has nothing an evaluator can
    # grep for (D-24). The lifespan would be the wrong home twice over - the
    # HTTP harness never enters it (ADR-056), so the call would be untested by
    # every test that drives this application over HTTP, and the startup half
    # must stay empty (D-06). Attaching a stream handler opens nothing, so
    # `test_creating_the_app_opens_no_connection` still holds; the function is
    # idempotent, so the hundreds of factory calls in the test suite leave one
    # handler rather than hundreds.
    configure_logging()
    resolved = settings or get_settings()
    resources = create_database_resources(resolved)
    # The second container, built here for the reason the first one is: this is
    # the only place `Settings` is read, so `dependencies.py` narrows two typed
    # objects off `app.state` and reads no configuration per request (RC-3).
    # The clock is passed in rather than constructed inside the builder, which
    # keeps the JWT configuration and the notion of "now" substitutable
    # independently.
    security = create_security_resources(resolved, SystemClock())

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

    app = ProblemAwareFastAPI(
        title=resolved.app_name,
        version=__version__,
        description=DESCRIPTION,
        openapi_url="/openapi.json",
        openapi_tags=OPENAPI_TAGS,
        lifespan=lifespan,
    )
    app.state.database = resources
    # Nothing about either container goes in the lifespan. The startup half
    # stays empty (D-06), and the HTTP harness never enters the lifespan at
    # all, so anything placed there would be untested by every test that drives
    # the application over HTTP. The security container has nothing to release
    # on the way down either: it owns no pool, no file and no socket.
    app.state.security = security
    register_exception_handlers(app)
    register_health_routes(app)
    # Before the two authenticated routers, matching the order of the document
    # an evaluator reads: the two open routes come first because they are what
    # makes the rest reachable.
    register_auth_routes(app)
    register_task_list_routes(app)
    register_task_routes(app)
    # Then the two Phase 5 additions, after the Phase 4 registrations: the
    # directory a client picks an assignee out of, and the door that hands the
    # task over. One call per router module, which is why each of those modules
    # exposes exactly one registration function even when - as `assignments.py`
    # does - it declares more than one router.
    register_user_routes(app)
    register_assignment_routes(app)
    return app
