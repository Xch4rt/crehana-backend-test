"""Unit tests for the FastAPI composition root."""

import inspect
from typing import Annotated, Any, Final, get_args, get_origin, get_type_hints

import pytest
from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from taskmanager import __version__
from taskmanager.application.ports.notifications import EmailNotifier
from taskmanager.application.ports.security import PasswordHasher, TokenService
from taskmanager.domain.exceptions import DomainError
from taskmanager.infrastructure.config.settings import Settings
from taskmanager.infrastructure.notifications.logging import LoggingEmailNotifier
from taskmanager.infrastructure.security.resources import SecurityResources
from taskmanager.main import create_app
from taskmanager.presentation.api import dependencies as dependencies_module
from taskmanager.presentation.api.dependencies import (
    EmailNotifierDependency,
    PasswordHasherDependency,
    TokenServiceDependency,
    get_email_notifier,
    get_password_hasher,
    get_token_service,
)
from taskmanager.presentation.api.errors.handlers import (
    handle_domain_error,
    handle_http_exception,
    handle_unexpected_error,
    handle_validation_error,
)
from taskmanager.presentation.api.schemas import task_lists as task_list_schemas
from taskmanager.presentation.api.schemas import tasks as task_schemas
from tests.integration.test_dependencies import uow_probe_router
from tests.probe import probe_router

DATABASE_URL = "postgresql+psycopg://user:pass@localhost:5432/taskmanager"
JWT_SECRET = "b" * 32

API_PREFIX = "/api/v1"

# The eleven routes Phase 4 owes, written down rather than derived. A derived
# expectation would agree with whatever the application happens to expose, which
# is the one thing an inventory must not do: a route silently added, removed or
# re-pathed has to fail here, and a typo in a path is exactly the defect a
# generated list would reproduce faithfully on both sides.
EXPECTED_API_ENDPOINTS: Final[frozenset[tuple[str, str]]] = frozenset(
    {
        ("POST", "/api/v1/task-lists"),
        ("GET", "/api/v1/task-lists"),
        ("GET", "/api/v1/task-lists/{list_id}"),
        ("PATCH", "/api/v1/task-lists/{list_id}"),
        ("DELETE", "/api/v1/task-lists/{list_id}"),
        ("POST", "/api/v1/task-lists/{list_id}/tasks"),
        ("GET", "/api/v1/task-lists/{list_id}/tasks"),
        ("GET", "/api/v1/task-lists/{list_id}/tasks/{task_id}"),
        ("PATCH", "/api/v1/task-lists/{list_id}/tasks/{task_id}"),
        ("DELETE", "/api/v1/task-lists/{list_id}/tasks/{task_id}"),
        ("PATCH", "/api/v1/task-lists/{list_id}/tasks/{task_id}/status"),
    }
)


def _api_operations(app: FastAPI) -> dict[tuple[str, str], dict[str, Any]]:
    """Every published `/api/v1` operation, keyed by (method, path).

    Read out of `app.openapi()` rather than off `app.routes`, and that is not a
    convenience. On the pinned stack `include_router` leaves a single opaque
    `_IncludedRouter` object in `app.routes` with no `path` and no `methods` at
    all - the same representation change this module's probe guard already ran
    into - so walking `app.routes` would find the four documentation endpoints
    and none of the eleven. The schema is also the thing a client reads, which
    makes it the honest place to assert a published contract.
    """
    schema = app.openapi()
    return {
        (method.upper(), path): operation
        for path, item in schema["paths"].items()
        for method, operation in item.items()
        if path.startswith(API_PREFIX)
    }


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


def test_create_app_publishes_exactly_the_phase_four_routes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The eleven routes, at these paths, on these verbs - no more, no fewer.

    An inventory rather than a count. `len(...) == 11` would stay green if a
    route were re-pathed, if a verb changed, or if one route were deleted while
    another was added; comparing the whole set means the failure message names
    which route moved.
    """
    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
    monkeypatch.setenv("JWT_SECRET", JWT_SECRET)

    app = create_app(Settings(_env_file=None))

    assert set(_api_operations(app)) == EXPECTED_API_ENDPOINTS


# Which named component each route's success body must be, or `None` for a 204
# with no body. Written out by hand for the reason `EXPECTED_API_ENDPOINTS` is:
# a table derived from the application would agree with whatever the application
# says, including when it is wrong.
EXPECTED_RESPONSE_MODELS: Final[dict[tuple[str, str], str | None]] = {
    ("POST", "/api/v1/task-lists"): "TaskListResponse",
    ("GET", "/api/v1/task-lists"): "TaskListResponse",
    ("GET", "/api/v1/task-lists/{list_id}"): "TaskListResponse",
    ("PATCH", "/api/v1/task-lists/{list_id}"): "TaskListResponse",
    ("DELETE", "/api/v1/task-lists/{list_id}"): None,
    ("POST", "/api/v1/task-lists/{list_id}/tasks"): "TaskResponse",
    ("GET", "/api/v1/task-lists/{list_id}/tasks"): "TaskCollectionResponse",
    ("GET", "/api/v1/task-lists/{list_id}/tasks/{task_id}"): "TaskResponse",
    ("PATCH", "/api/v1/task-lists/{list_id}/tasks/{task_id}"): "TaskResponse",
    ("DELETE", "/api/v1/task-lists/{list_id}/tasks/{task_id}"): None,
    ("PATCH", "/api/v1/task-lists/{list_id}/tasks/{task_id}/status"): "TaskResponse",
}


def _presentation_models() -> dict[str, type[BaseModel]]:
    """Every Pydantic model the two presentation schema modules define, by name."""
    return {
        name: member
        for module in (task_list_schemas, task_schemas)
        for name, member in vars(module).items()
        if isinstance(member, type)
        and issubclass(member, BaseModel)
        and member.__module__ == module.__name__
    }


def _published_success_models(operation: dict[str, Any]) -> list[str | None]:
    """The component each 2xx response points at; `None` where it has no body.

    A `$ref`, or an array of one, is what a declared model looks like in the
    document. Anything else - the `{}` FastAPI publishes for an unannotated
    handler, or an inline object - has no name and is reported as `"<inline>"`,
    which no entry of the table above can equal.
    """
    published: list[str | None] = []
    for code, response in operation["responses"].items():
        if not code.startswith("2"):
            continue
        if "content" not in response:
            published.append(None)
            continue
        schema = response["content"]["application/json"]["schema"]
        reference = schema.get("items", schema).get("$ref")
        published.append(
            "<inline>" if reference is None else reference.rsplit("/", 1)[-1]
        )
    return published


def test_every_api_route_declares_a_response_model_or_returns_no_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ARC-05's mechanical half: a *presentation* Pydantic schema, or a bodiless 204.

    A handler annotated with an application result dataclass and no explicit
    model makes FastAPI infer the published schema from that dataclass. The
    endpoint would answer a `curl` perfectly, the response would even look
    right, and ARC-05's claim that Pydantic types every HTTP boundary would
    have quietly stopped being true. Here it fails instead.

    **This test could not fail until the Phase 4 review's WR-04.** It asserted
    only that a 2xx response had a `content` member, and FastAPI publishes one
    for the dataclass case (a `$ref` to a component named after the dataclass)
    and for a handler with no annotation at all (`"schema": {}`). Both were
    "modelled", so the gate was green by construction. It now asserts *which*
    component each route publishes, against a hand-written table, and that every
    name in that table is a `BaseModel` defined under
    `presentation/api/schemas/` - so an application DTO cannot be written into
    the table to make a wrong route pass. Driven red by pointing `get_task` at
    `TaskResult`; the capture is
    `.planning/phases/04-task-lists-tasks/evidence/04-review-fix-WR-04-red.txt`.
    """
    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
    monkeypatch.setenv("JWT_SECRET", JWT_SECRET)

    app = create_app(Settings(_env_file=None))
    presentation_models = _presentation_models()

    # The table is only a gate if it names presentation models and nothing else.
    named = {name for name in EXPECTED_RESPONSE_MODELS.values() if name is not None}
    assert named <= set(presentation_models), named - set(presentation_models)
    # And it has to cover the inventory exactly, or a twelfth route is unchecked.
    assert set(EXPECTED_RESPONSE_MODELS) == EXPECTED_API_ENDPOINTS

    published = {
        endpoint: _published_success_models(operation)
        for endpoint, operation in _api_operations(app).items()
    }
    expected = {
        endpoint: [model] for endpoint, model in EXPECTED_RESPONSE_MODELS.items()
    }

    assert published == expected, (
        "Every route must publish its presentation response model, or answer "
        "204 with no body (ARC-05)."
    )


def test_every_api_route_is_documented(monkeypatch: pytest.MonkeyPatch) -> None:
    """A tag, a summary, a description of the success, and the refusal legs.

    DOC-04 is Phase 7's budget, but a route documented in a plan and nowhere
    else is documented nowhere. Asserting the four members here is what stops
    the twelfth route from arriving bare, which is how an OpenAPI document
    becomes half-useful and then ignored.
    """
    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
    monkeypatch.setenv("JWT_SECRET", JWT_SECRET)

    app = create_app(Settings(_env_file=None))

    undocumented = [
        endpoint
        for endpoint, operation in _api_operations(app).items()
        if not (
            operation.get("tags")
            and operation.get("summary")
            and any(
                code.startswith("2") and operation["responses"][code].get("description")
                for code in operation["responses"]
            )
            and any(not code.startswith("2") for code in operation["responses"])
        )
    ]

    assert undocumented == [], (
        "Every route needs a tag, a summary, a description of its success and "
        f"a responses map naming its refusal legs. Bare: {undocumented}"
    )


# --- The security container and the three providers it feeds (05-10) ---------
#
# These live here rather than beside `get_clock` in `test_actor.py` because the
# property they defend is a property of the composition root: the container is
# built once, in `create_app`, and the providers exist to hand pieces of it out
# without reading application state a second time.


def _app_with_a_security_container() -> FastAPI:
    """The real application, settings injected, no environment consulted."""
    return create_app(
        Settings(
            _env_file=None,
            database_url=DATABASE_URL,
            jwt_secret=JWT_SECRET,
        )
    )


def _request_for(app: FastAPI) -> Request:
    """The minimum scope a provider that narrows `app.state` needs.

    The providers take a `Request` and read one attribute off the application
    behind it, so a hand-built scope is enough and a running server would add
    nothing - the same shape `tests/integration/test_dependencies.py` uses to
    prove `get_engine`.
    """
    return Request({"type": "http", "app": app, "headers": []})


def test_create_app_stores_the_security_container_on_state() -> None:
    """The second typed container, beside the database one (RC-3)."""
    app = _app_with_a_security_container()

    assert isinstance(app.state.security, SecurityResources)


def test_the_two_stateful_providers_hand_back_the_container_s_objects() -> None:
    """One hasher and one token service per application, not per request.

    Identity, not equivalence, and asserted twice per provider. `dummy_verify`
    is answered from a throwaway Argon2 hash the hasher computes once and
    caches, at a measured ~37 ms; a provider that built a fresh adapter per
    call would pay that on every login, which is the cost D-21 added the method
    to control and D-27 put the object in the container to avoid.
    """
    app = _app_with_a_security_container()
    request = _request_for(app)

    assert get_password_hasher(request) is app.state.security.password_hasher
    assert get_password_hasher(request) is get_password_hasher(request)
    assert get_token_service(request) is app.state.security.token_service
    assert get_token_service(request) is get_token_service(request)


def test_get_email_notifier_builds_a_fresh_notifier_per_call() -> None:
    """The `get_clock` shape, for the same reason and with the same assertion.

    `LoggingEmailNotifier` holds nothing but a module-level logger, so there is
    no cached work to preserve and nothing for the narrowing to be worth: the
    provider takes no `Request` and stores nothing on the application. Two
    calls returning two objects is what says so.
    """
    notifier = get_email_notifier()

    assert isinstance(notifier, LoggingEmailNotifier)
    assert get_email_notifier() is not get_email_notifier()


def test_the_three_providers_are_typed_by_the_ports() -> None:
    """Contracts at the boundary, never the adapters that satisfy them.

    Nothing at runtime tells the two apart and mypy accepts either, because
    every adapter satisfies its port - so the annotation is the only place the
    decision lives, and reading it back is the only way to pin it. The aliases
    are checked in the same breath: they are what a router actually spells, so
    an alias pointing at the right port through the wrong provider would leave
    every signature compiling and every request answered by someone else.
    """
    assert get_type_hints(get_password_hasher)["return"] is PasswordHasher
    assert get_type_hints(get_token_service)["return"] is TokenService
    assert get_type_hints(get_email_notifier)["return"] is EmailNotifier

    for alias, port, provider in (
        (PasswordHasherDependency, PasswordHasher, get_password_hasher),
        (TokenServiceDependency, TokenService, get_token_service),
        (EmailNotifierDependency, EmailNotifier, get_email_notifier),
    ):
        assert get_origin(alias) is Annotated
        annotated_type, marker = get_args(alias)
        assert annotated_type is port
        assert marker.dependency is provider


def test_creating_the_app_still_opens_no_connection() -> None:
    """D-06 survives the second container (`test_health.py` asserts the first).

    Re-asserted here rather than left to the sibling because this plan adds a
    builder to `create_app`, and the whole unit suite - every test above
    included - rests on the application being constructible against a DSN that
    points nowhere. The security container performs no I/O of its own
    (`test_security_resources.py` proves that directly); what this asserts is
    that adding it moved nothing in the half that owns a pool.
    """
    app = _app_with_a_security_container()

    assert app.state.database.engine.pool.checkedout() == 0


def test_the_dependency_module_reads_no_settings_per_request() -> None:
    """RC-3 as a gate: configuration is read once, in the composition root.

    A provider that reached for the settings object per request would work
    perfectly and would quietly undo the reason both containers exist - the
    application's state is narrowed in one private helper per container, and
    everything downstream is typed by a dataclass instead of by a fresh cast.
    A source scan is the honest form here: the accessor is cached, so a call
    would not even be slow enough to notice.
    """
    source = inspect.getsource(dependencies_module)

    assert "get_settings" not in source
