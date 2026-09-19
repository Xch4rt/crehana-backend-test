"""The authentication seam, and the `Clock` provider beside it.

Two of the assertions below look unusual and are deliberate.

One inspects the `Annotated` alias rather than calling through FastAPI.
`CurrentActor` is what every router spells, so the thing worth pinning is that
the alias still points at *this* provider: a refactor that repointed it at a
different function would leave every router compiling, every test of
`get_current_actor` green, and the application quietly reading someone else's
answer. That test survives this module's Phase 5 rewrite verbatim, which is the
clearest evidence there is that ADR-044 held - nothing downstream moved when
the seam became real.

The other reads the module's own source. Until Phase 5 it asserted the phrase
"not authentication" was still in `actor.py`, because D-03's honesty
requirement lived in prose and prose is the one thing no type checker
protects. **That test is deleted here, as a deliberate act rather than a
dropped guarantee**: the phrase is now false, and a gate that pins a false
statement is worse than no gate. It is replaced by a positive one - the module
names no algorithm and no cryptography library anywhere, because the decode is
reachable only through the `TokenService` port. That is the property the old
assertion was really defending, stated the right way round.

The refusal legs are driven over HTTP rather than by calling the provider,
even though this is a unit test and nothing here touches a database. The
`Authorization` header is parsed by FastAPI's own bearer scheme, and three of
the four shapes below differ only in that parse: "no header" and
"`Basic zzz`" both arrive as `None`, while "`Bearer `" arrives as the empty
string. Calling the function with `None` would test this module's guard
against a value invented by the test rather than produced by the code that
actually produces it - and the lowercase-scheme leg could not be expressed at
all.
"""

import inspect
from datetime import UTC, datetime
from typing import Annotated, get_args, get_origin, get_type_hints
from uuid import UUID

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response

from taskmanager.application.ports.clock import Clock
from taskmanager.application.ports.security import TokenService
from taskmanager.domain.entities.user import User
from taskmanager.domain.exceptions import AuthenticationError
from taskmanager.presentation.api import actor as actor_module
from taskmanager.presentation.api.actor import CurrentActor, get_current_actor
from taskmanager.presentation.api.dependencies import (
    TokenServiceDependency,
    UnitOfWorkDependency,
    get_clock,
    get_token_service,
    get_uow,
)
from taskmanager.presentation.api.errors.handlers import register_exception_handlers
from tests.unit.application.fakes import (
    FakeTokenService,
    FakeUnitOfWork,
    FakeUserRepository,
)

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)

ACTOR_ID = UUID("11111111-1111-4111-8111-111111111111")
DELETED_USER_ID = UUID("99999999-9999-4999-8999-999999999999")

EMAIL = "ana@example.com"
FULL_NAME = "Ana Torres"
PASSWORD_HASH = "fake-hash:a-long-enough-password"

PROBLEM_JSON = "application/problem+json"
WHO = "/who"

# Every name that would betray the token being decoded in this module rather
# than behind the port: the two credential libraries, the token format they
# implement, and the signing schemes a hand-rolled decode would have to name.
# The tuple is the assertion, so a library added to the project joins it here.
LEAKED_IMPLEMENTATION_NAMES = (
    "jwt",
    "pwdlib",
    "argon2",
    "hs256",
    "rs256",
)


class _RefusingTokenService(FakeTokenService):
    """Refuses every token, exactly as the real adapter does.

    `JwtTokenService.decode` answers a malformed, expired, wrongly signed or
    unsigned token with one `AuthenticationError` and no details; the stock
    fake would raise `ValueError` out of `UUID(...)`, which is the fake's
    accident rather than the port's stated behaviour. Same double, same
    argument, as `tests/unit/application/test_authenticate_actor.py`.
    """

    async def decode(self, token: str) -> UUID:
        raise AuthenticationError()


def _a_user(user_id: UUID = ACTOR_ID) -> User:
    """The account a valid token points at."""
    return User.create(
        user_id=user_id,
        email=EMAIL,
        full_name=FULL_NAME,
        password_hash=PASSWORD_HASH,
        now=NOW,
    )


def _app(uow: FakeUnitOfWork, tokens: TokenService) -> FastAPI:
    """One route behind `CurrentActor`, on the project's real handler stack.

    Built here rather than through `create_app` because the point is the
    dependency and not the routing table: this application registers the same
    exception handlers, so a refusal is rendered by the code that renders every
    other refusal, and nothing else about it can influence the answer.

    Both collaborators arrive through `dependency_overrides`, which is also the
    assertion Pitfall 4 asks for. The seam takes its unit of work as a
    parameter; had it called the provider directly instead, the override below
    would be bypassed, the call would reach for application state this
    application never set, and every test in this module would fail with an
    attribute error rather than an assertion.
    """
    app = FastAPI()
    register_exception_handlers(app)

    @app.get(WHO)
    async def who(actor: CurrentActor) -> dict[str, str]:
        return {"actor": str(actor)}

    app.dependency_overrides[get_uow] = lambda: uow
    app.dependency_overrides[get_token_service] = lambda: tokens
    return app


def _uow_holding(*users: User) -> FakeUnitOfWork:
    """A unit of work whose `users` table contains exactly these rows."""
    repository = FakeUserRepository()
    for user in users:
        repository.stored[user.id] = user
    return FakeUnitOfWork(users=repository)


async def _get(app: FastAPI, headers: dict[str, str] | None = None) -> Response:
    """One request through the whole ASGI stack, headers exactly as given."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(WHO, headers=headers)


async def test_a_request_with_no_authorization_header_is_refused() -> None:
    """The bearer scheme returns `None`; the seam turns that into one 401.

    The status, the media type and the challenge header all matter. A client
    that receives a bare 401 with no `WWW-Authenticate` has not been told how
    to authenticate, and the body is the project's single problem+json shape
    rather than a second one invented for authentication.
    """
    app = _app(_uow_holding(_a_user()), FakeTokenService())

    response = await _get(app)

    assert response.status_code == 401
    assert response.headers["content-type"].startswith(PROBLEM_JSON)
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert response.json()["detail"] == AuthenticationError.REFUSAL


async def test_a_non_bearer_scheme_is_refused() -> None:
    """`Basic` credentials also arrive as `None`, and are also one 401."""
    app = _app(_uow_holding(_a_user()), FakeTokenService())

    response = await _get(app, {"Authorization": "Basic zzz"})

    assert response.status_code == 401
    assert response.json()["detail"] == AuthenticationError.REFUSAL


async def test_a_bearer_scheme_with_an_empty_parameter_is_refused() -> None:
    """This is the leg a `token is None` guard would let through.

    FastAPI's scheme returns the empty string here, not `None`, because the
    scheme *did* match - so the guard has to be falsiness rather than identity.
    A token service that was reached with `""` would answer whatever it answers
    for junk, which is the same 401 today and is not a property to rely on.
    """
    app = _app(_uow_holding(_a_user()), FakeTokenService())

    response = await _get(app, {"Authorization": "Bearer "})

    assert response.status_code == 401
    assert response.json()["detail"] == AuthenticationError.REFUSAL


async def test_a_lowercase_bearer_scheme_is_accepted() -> None:
    """Scheme matching is case-insensitive, and the actor comes back.

    The one positive leg, and it is written in the awkward spelling on purpose:
    `bearer` lowercase is what several HTTP clients send, and a hand-rolled
    header parse comparing the scheme literally would refuse it.
    """
    user = _a_user()
    app = _app(_uow_holding(user), FakeTokenService())

    response = await _get(app, {"Authorization": f"bearer {user.id}"})

    assert response.status_code == 200
    assert response.json() == {"actor": str(user.id)}


async def test_a_token_whose_subject_has_no_row_is_the_same_refusal() -> None:
    """D-11's second read, and T-5-04's indistinguishability, in one test.

    Both refusals are produced and compared member by member. Asserting a 401
    for the deleted user alone would pass just as happily against an
    implementation whose two bodies differ - and a caller who can tell "this
    token is junk" from "this token's owner is gone" has an oracle for account
    deletion over every token they ever held.

    Only `instance` is allowed to differ, and here it cannot: both requests
    address the same path.
    """
    junk = await _get(
        _app(_uow_holding(), _RefusingTokenService()),
        {"Authorization": "Bearer not-a-token"},
    )
    deleted = await _get(
        _app(_uow_holding(), FakeTokenService()),
        {"Authorization": f"Bearer {DELETED_USER_ID}"},
    )

    assert deleted.status_code == junk.status_code == 401
    assert deleted.json() == junk.json()
    assert str(DELETED_USER_ID) not in deleted.text


async def test_the_route_is_published_with_the_bearer_scheme() -> None:
    """AUTH-02's other half: Swagger's Authorize button needs this entry.

    It is emitted *through* the nested dependency - the route declares nothing
    about security itself - which is the whole reason the scheme is a
    `Depends` rather than a hand-rolled header read. Losing it would leave
    authentication working and undiscoverable.
    """
    schema = _app(_uow_holding(), FakeTokenService()).openapi()

    assert "OAuth2PasswordBearer" in schema["components"]["securitySchemes"]
    assert schema["paths"][WHO]["get"]["security"] == [{"OAuth2PasswordBearer": []}]


def test_the_seam_takes_its_collaborators_as_parameters() -> None:
    """Pitfall 4, pinned by signature rather than by the failure it causes.

    Both are `Depends` aliases, so FastAPI resolves them - and a test, or the
    integration harness, can override them. The alternative shape, calling the
    providers inside the body, is invisible at a glance and would dial the
    fictional DSN `tests/conftest.py` sets the moment a harness overrode the
    dependency instead of the function.
    """
    hints = get_type_hints(get_current_actor, include_extras=True)

    assert hints["uow"] is UnitOfWorkDependency
    assert hints["tokens"] is TokenServiceDependency
    assert hints["return"] is UUID


def test_current_actor_depends_on_this_module_s_provider() -> None:
    """The alias routers use resolves to `get_current_actor`, still.

    `get_args` on an `Annotated` alias yields the underlying type first and the
    metadata after it; the metadata here is FastAPI's `Depends` marker, whose
    `.dependency` is the callable the framework will run.
    """
    assert get_origin(CurrentActor) is Annotated

    annotated_type, marker = get_args(CurrentActor)

    assert annotated_type is UUID
    assert marker.dependency is get_current_actor


def test_the_module_names_no_algorithm_and_no_library() -> None:
    """The positive replacement for the deleted honesty assertion.

    A seam that decoded a token itself would have to name a library and an
    algorithm somewhere in this file; reaching the decode only through the
    `TokenService` port means it names neither, and that is what keeps the
    choice of algorithm in one adapter where `.importlinter` and the settings
    can both reach it. Read from the source rather than from `__doc__`, the
    same way the assertion it replaces was.
    """
    source = inspect.getsource(actor_module).lower()

    for name in LEAKED_IMPLEMENTATION_NAMES:
        assert name.lower() not in source, name


def test_get_clock_returns_the_clock_port() -> None:
    """Structural conformance, with mypy strict as the real gate (03-03)."""
    clock: Clock = get_clock()

    assert clock.now().tzinfo is not None


def test_get_clock_builds_a_fresh_instance_per_call() -> None:
    """Nothing is cached, so no request can be handed another's clock.

    The provider deliberately keeps no module-level instance and stores nothing
    on `app.state`; this is the assertion that says so.
    """
    assert get_clock() is not get_clock()
