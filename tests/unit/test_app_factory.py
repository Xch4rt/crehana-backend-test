"""Unit tests for the FastAPI composition root."""

import inspect
import logging
from collections.abc import Iterator
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
from taskmanager.infrastructure.logging import PACKAGE_LOGGER
from taskmanager.infrastructure.notifications.logging import LoggingEmailNotifier
from taskmanager.infrastructure.security.resources import SecurityResources
from taskmanager.main import create_app
from taskmanager.presentation.api import dependencies as dependencies_module
from taskmanager.presentation.api.dependencies import (
    AccessTokenExpiryDependency,
    EmailNotifierDependency,
    PasswordHasherDependency,
    TokenServiceDependency,
    get_access_token_expire_minutes,
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
from taskmanager.presentation.api.schemas import auth as auth_schemas
from taskmanager.presentation.api.schemas import task_lists as task_list_schemas
from taskmanager.presentation.api.schemas import tasks as task_schemas
from taskmanager.presentation.api.schemas import users as user_schemas
from tests.integration.test_dependencies import uow_probe_router
from tests.probe import probe_router

DATABASE_URL = "postgresql+psycopg://user:pass@localhost:5432/taskmanager"
JWT_SECRET = "b" * 32

API_PREFIX = "/api/v1"

# Every published route, written down rather than derived. A derived
# expectation would agree with whatever the application happens to expose, which
# is the one thing an inventory must not do: a route silently added, removed or
# re-pathed has to fail here, and a typo in a path is exactly the defect a
# generated list would reproduce faithfully on both sides.
#
# Phase 4's eleven, the three auth routes plan 05-11 registers, and the four
# plan 05-12 adds. The login path in particular is not decoration in this list:
# `actor.py` constructs the bearer scheme with that exact path, and a mismatch
# would leave Swagger's Authorize button visible and posting into a 404. This
# inventory pins the route's existence; `test_security_scheme.py` pins the
# agreement.
EXPECTED_API_ENDPOINTS: Final[frozenset[tuple[str, str]]] = frozenset(
    {
        ("POST", "/api/v1/auth/register"),
        ("POST", "/api/v1/auth/login"),
        ("GET", "/api/v1/auth/me"),
        ("GET", "/api/v1/users"),
        ("GET", "/api/v1/tasks/assigned-to-me"),
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
        ("PUT", "/api/v1/task-lists/{list_id}/tasks/{task_id}/assignee"),
        ("DELETE", "/api/v1/task-lists/{list_id}/tasks/{task_id}/assignee"),
    }
)

# The one published operation outside the versioned prefix. Named rather than
# added to the set above, because `_api_operations` filters on that prefix and
# an entry it can never return would make the inventory unfalsifiable.
HEALTH_ENDPOINT: Final[tuple[str, str]] = ("GET", "/health")

# Every operation the application publishes, versioned or not. Nineteen after
# plan 05-12, which is the number `05-RESEARCH.md`'s permission matrix has rows
# for and the number plan 05-15's parametrized HTTP walk drives.
EXPECTED_OPERATIONS: Final[frozenset[tuple[str, str]]] = EXPECTED_API_ENDPOINTS | {
    HEALTH_ENDPOINT
}

# The three operations that answer without a token, and therefore the three
# with no 401 leg to declare. Duplicated from `test_security_scheme.py` on
# purpose rather than imported: that module partitions the `security` arrays a
# client's generated code reads, this one partitions the `responses` maps a
# human reads, and fusing the two would make one property's exemption silently
# grant the other's. `POST /auth/login` is in this set and still declares a 401,
# which is the asymmetry the partition below is careful to allow: the exemption
# says an open route need not document a missing-credential refusal, never that
# it may not document a rejected one.
OPEN_OPERATIONS: Final[frozenset[tuple[str, str]]] = frozenset(
    {
        HEALTH_ENDPOINT,
        ("POST", "/api/v1/auth/register"),
        ("POST", "/api/v1/auth/login"),
    }
)

# Exactly the operations that can answer 403, and there are four (D-03). An
# assignee may read their task and change its status; they may not edit it,
# delete it, or decide who holds it. Every other refusal in this API is a 404,
# because the caller cannot see the resource at all - so a 403 declared
# anywhere else would be a documented leg the route cannot produce, which
# misleads a client exactly as much as a missing one does.
FORBIDDEN_OPERATIONS: Final[frozenset[tuple[str, str]]] = frozenset(
    {
        ("PATCH", "/api/v1/task-lists/{list_id}/tasks/{task_id}"),
        ("DELETE", "/api/v1/task-lists/{list_id}/tasks/{task_id}"),
        ("PUT", "/api/v1/task-lists/{list_id}/tasks/{task_id}/assignee"),
        ("DELETE", "/api/v1/task-lists/{list_id}/tasks/{task_id}/assignee"),
    }
)


def _all_operations(app: FastAPI) -> dict[tuple[str, str], dict[str, Any]]:
    """Every operation in the published document, versioned prefix or not.

    `_api_operations` below is the same read narrowed to `/api/v1`, and the
    narrow one cannot be used for the inventory: `/health` is published outside
    the prefix, so an inventory taken through the filter would be unable to
    notice the health route disappearing.
    """
    return {
        (method.upper(), path): operation
        for path, item in app.openapi()["paths"].items()
        for method, operation in item.items()
    }


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


def test_create_app_publishes_exactly_the_expected_routes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """These routes, at these paths, on these verbs - no more, no fewer.

    An inventory rather than a count. A length comparison would stay green if a
    route were re-pathed, if a verb changed, or if one route were deleted while
    another was added; comparing the whole set means the failure message names
    which route moved.

    The name lost its "phase four" qualifier when plan 05-11 added the three
    auth routes, because the set is no longer one phase's.
    """
    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
    monkeypatch.setenv("JWT_SECRET", JWT_SECRET)

    app = create_app(Settings(_env_file=None))

    assert set(_api_operations(app)) == EXPECTED_API_ENDPOINTS


def test_the_document_publishes_exactly_nineteen_operations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The whole surface, `/health` included, counted and named (ADR-057).

    The sibling above asserts the versioned inventory, and it cannot see the
    health route at all: `_api_operations` filters on the `/api/v1` prefix, so
    `/health` disappearing - or a second unversioned route appearing beside it -
    would leave it perfectly green. This one reads the document whole.

    Both the set and the number are asserted. The set is what names the route
    that moved; the number is the one plan 05-15's permission matrix has rows
    for, so a route added without a row in that table fails here first, while
    the matrix is still being written rather than after it has been shipped
    incomplete.
    """
    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
    monkeypatch.setenv("JWT_SECRET", JWT_SECRET)

    app = create_app(Settings(_env_file=None))

    published = set(_all_operations(app))
    assert published == EXPECTED_OPERATIONS
    assert len(published) == 19


def test_every_authenticated_operation_declares_a_401(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AUTH-03 in the document, not only in the tests.

    A partition rather than a list, which is the shape plan 05-11 used for the
    `security` arrays and the reason this survives a route added later: an
    operation is either one of the three named open ones or it must document
    the refusal it now produces without a token. A hand-written list of secured
    routes would say nothing about the route nobody remembered to add to it.

    Why this is worth a gate at all: `security` and `responses` are read by
    different halves of a client. A generated client uses the first to decide
    whether to attach a token, and a human - or a typed error union - uses the
    second to decide which failures to handle. A route that demands a token and
    never documents the 401 is a client that treats it as an unexpected server
    fault.
    """
    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
    monkeypatch.setenv("JWT_SECRET", JWT_SECRET)

    app = create_app(Settings(_env_file=None))

    operations = _all_operations(app)
    assert operations
    # The exemption list is a hole in the partition, so it has to keep earning
    # itself: a renamed open route would otherwise simply become a secured one
    # and the partition would still pass.
    assert OPEN_OPERATIONS <= set(operations), OPEN_OPERATIONS - set(operations)

    undeclared = [
        endpoint
        for endpoint, operation in operations.items()
        if endpoint not in OPEN_OPERATIONS and "401" not in operation["responses"]
    ]

    assert undeclared == [], (
        "Every operation that requires a token must declare the 401 it answers "
        f"without one (AUTH-03). Missing the leg: {undeclared}"
    )


def test_exactly_four_operations_declare_a_403(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D-03's four, and an equality so a fifth is a failure either way.

    Asserted as set equality rather than as containment, because the two
    directions fail differently and both matter. A missing 403 is a refusal an
    assignee will meet and no client was told about. A *surplus* one is worse
    in its own way: the task-list routes and `POST .../tasks` cannot produce a
    403 at all - an assignee cannot see the list, so every refusal there is the
    404 D-01 specifies - and documenting a leg a route can never answer with
    invites a client to write a branch that is dead on arrival, and invites a
    reader to believe this API discloses more than it does.
    """
    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
    monkeypatch.setenv("JWT_SECRET", JWT_SECRET)

    app = create_app(Settings(_env_file=None))

    declared = {
        endpoint
        for endpoint, operation in _all_operations(app).items()
        if "403" in operation["responses"]
    }

    assert declared == FORBIDDEN_OPERATIONS, {
        "missing": sorted(FORBIDDEN_OPERATIONS - declared),
        "unexpected": sorted(declared - FORBIDDEN_OPERATIONS),
    }


# Which named component each route's success body must be, or `None` for a 204
# with no body. Written out by hand for the reason `EXPECTED_API_ENDPOINTS` is:
# a table derived from the application would agree with whatever the application
# says, including when it is wrong.
EXPECTED_RESPONSE_MODELS: Final[dict[tuple[str, str], str | None]] = {
    ("POST", "/api/v1/auth/register"): "UserResponse",
    ("POST", "/api/v1/auth/login"): "TokenResponse",
    ("GET", "/api/v1/auth/me"): "UserResponse",
    ("GET", "/api/v1/users"): "UserSummaryResponse",
    ("GET", "/api/v1/tasks/assigned-to-me"): "TaskResponse",
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
    ("PUT", "/api/v1/task-lists/{list_id}/tasks/{task_id}/assignee"): "TaskResponse",
    ("DELETE", "/api/v1/task-lists/{list_id}/tasks/{task_id}/assignee"): "TaskResponse",
}


def _presentation_models() -> dict[str, type[BaseModel]]:
    """Every Pydantic model the presentation schema modules define, by name."""
    return {
        name: member
        for module in (
            auth_schemas,
            task_list_schemas,
            task_schemas,
            user_schemas,
        )
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


def test_the_access_token_lifetime_provider_reads_the_container() -> None:
    """`expires_in` and the signed token come from one number (05-11).

    The provider that hands out an integer rather than a port. The login route
    publishes how many seconds its token is good for, and that claim is only
    true if the value it publishes is the value the token service signed with;
    both now come from the container the composition root built, so the two
    cannot drift apart. Asserted against the settings object the application
    was built from, not against the literal default, so a changed default does
    not turn into a changed assertion.
    """
    settings = Settings(
        _env_file=None, database_url=DATABASE_URL, jwt_secret=JWT_SECRET
    )
    app = create_app(settings)
    request = _request_for(app)

    assert get_access_token_expire_minutes(request) == settings.jwt_expire_minutes
    assert (
        get_access_token_expire_minutes(request)
        == app.state.security.access_token_expire_minutes
    )
    assert get_type_hints(get_access_token_expire_minutes)["return"] is int
    assert get_origin(AccessTokenExpiryDependency) is Annotated
    annotated_type, marker = get_args(AccessTokenExpiryDependency)
    assert annotated_type is int
    assert marker.dependency is get_access_token_expire_minutes


# --- Logging, and the description an evaluator reads first (05-11) -----------


@pytest.fixture
def a_package_logger_with_no_handlers() -> Iterator[logging.Logger]:
    """The `taskmanager` logger, emptied for the test and restored after it.

    `configure_logging` is idempotent by design, so by the time any of these
    tests runs the handler is almost certainly already attached by some earlier
    `create_app()` - and a test that merely counted handlers would then pass
    whether or not the factory ever called it. Emptying the logger first is
    what makes the count below evidence of this call rather than of a previous
    one. The state is global, so it is put back.
    """
    logger = logging.getLogger(PACKAGE_LOGGER)
    saved_handlers = list(logger.handlers)
    saved_level = logger.level
    logger.handlers.clear()
    yield logger
    logger.handlers[:] = saved_handlers
    logger.setLevel(saved_level)


def test_create_app_configures_logging_once_however_often_it_runs(
    a_package_logger_with_no_handlers: logging.Logger,
) -> None:
    """One handler after three factories, and records still reach the root.

    Without this call nothing under `taskmanager` is written at all: uvicorn
    configures its own loggers and leaves the root one at WARNING, so D-15's
    INFO notification line would be dropped and NOTF-02 would have nothing an
    evaluator can grep for (D-24). The factory runs hundreds of times across
    this suite, so the second half of the property is the one that matters -
    each run must not attach another handler and multiply every line.

    `propagate` is asserted deliberately: the assertions in
    `tests/api/test_error_contract.py` read records off `caplog`, whose handler
    sits on the root logger, so a record that stopped here would never reach
    them.
    """
    logger = a_package_logger_with_no_handlers
    assert logger.handlers == []

    for _ in range(3):
        _app_with_a_security_container()

    assert len(logger.handlers) == 1
    assert logger.propagate
    assert logger.level == logging.INFO


async def test_logging_is_configured_by_the_factory_and_not_by_the_lifespan(
    a_package_logger_with_no_handlers: logging.Logger,
) -> None:
    """The handler exists before any lifespan is entered, and adds nothing on
    the way in.

    ADR-056: the HTTP harness drives the application without ever entering the
    lifespan, so anything put in its startup half would be untested by every
    test in this project that speaks HTTP - and the notification line would be
    missing in exactly the runs that assert on it. The startup half stays
    empty (D-06), which is also what keeps
    `test_creating_the_app_opens_no_connection` and
    `test_the_lifespan_disposes_the_engine` in `tests/unit/presentation/
    test_health.py` true of a factory that now does one more thing.
    """
    logger = a_package_logger_with_no_handlers

    app = _app_with_a_security_container()

    # Before the lifespan: the assertion is the ordering, not the count.
    assert len(logger.handlers) == 1
    async with app.router.lifespan_context(app):
        assert len(logger.handlers) == 1
    assert len(logger.handlers) == 1


def test_the_description_names_the_evaluator_s_path() -> None:
    """There is no seeded account, so `/docs` has to say where to start (D-14).

    This is the copy an evaluator reads first - before the README, because
    `/docs` is what `docker compose up` hands them - and the stack ships with
    zero users, so an evaluator who clicks Authorize before registering has no
    credential to type. The three things the description must name are
    therefore the three steps of that path, and it names a procedure rather
    than a credential: there is no password anywhere in this repository
    (T-5-03).
    """
    description = _app_with_a_security_container().openapi()["info"]["description"]

    assert "/api/v1/auth/register" in description
    assert "Authorize" in description
    assert "/docs" in description
