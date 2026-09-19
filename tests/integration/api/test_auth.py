"""The three auth routes, over real HTTP, through the real actor dependency.

Every test here uses `authenticated_client` rather than `api_client`, and the
choice is the whole point of the module. `api_client` overrides
`get_current_actor`, so a request through it never reaches a decode and no
assertion made through it says anything about a credential; this suite is where
the dependency runs for real, which is the only arrangement in which the 401
legs exist at all (D-20). The harness's own docstring argues the split.

The two standards `test_task_lists.py` sets out apply unchanged. Each test
asserts on the **response body**, never on the status code alone - a 401 that
answered with a different `code`, or with an `errors` member naming the failed
claim, would be a leak a status assertion cannot see. And each mutating test
**re-reads through the API**: registering is proven by logging in with the new
credential and reading the profile back, not by trusting the 201 body.

Three things are specific to this module.

**The comparative assertions are the load-bearing ones.** D-11 and D-12 are
both claims that two different failures are *the same answer*, and a test that
checked only the status of each would pass against an implementation that
leaked the difference in `code`, in `detail` or in the presence of `errors`.
So the seven token failures are compared body to body against each other, and
the two login failures are compared body to body against each other, with
`anonymised` applied for the reason `test_task_lists.py` gives.

**Member lists are asserted in declaration order, never as a per-key absence
check.** `assert "password_hash" not in body` passes happily against a field
that was renamed; `assert list(body) == PROFILE_MEMBERS` does not (T-5-08).

**Nothing here spells the refusal message.** `AuthenticationError.REFUSAL` is
the single home of the generic 401 wording (D-11), and a literal copy here
would be the thing that quietly disagreed the first time it moved.
"""

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from taskmanager.domain.exceptions import AuthenticationError
from taskmanager.infrastructure.config.settings import Settings
from taskmanager.infrastructure.security.resources import create_security_resources
from tests.integration.api.test_task_lists import (
    DEMO_EMAIL,
    DEMO_FULL_NAME,
    SessionFactory,
    a_user,
    anonymised,
)
from tests.integration.conftest import OWNER_ID, bearer_header, seed

# Imported rather than re-declared, the convention `test_task_lists.py` states
# in full: the media type and the six-member error body are Phase 2's contract
# and `tests/problem_details.py` is where they live.
from tests.problem_details import MEMBERS, PROBLEM_JSON

pytestmark = pytest.mark.integration

AUTH = "/api/v1/auth"
REGISTER = f"{AUTH}/register"
LOGIN = f"{AUTH}/login"
ME = f"{AUTH}/me"
# The one published route that lists accounts, and therefore the only place a
# registration can be read back from. See `directory` below.
USERS = "/api/v1/users"

# `UserResponse`'s four members, in declaration order - which is serialisation
# order, and therefore contract. The fifth member this list does not have is
# the whole of T-5-08.
PROFILE_MEMBERS = ["id", "email", "full_name", "created_at"]
# `TokenResponse`'s three, likewise.
TOKEN_MEMBERS = ["access_token", "token_type", "expires_in"]

# A registration that succeeds, and the credential it succeeds with. The
# password is distinctive rather than realistic on purpose: every assertion
# that it did not reach a response body is a substring search, and a common
# word would match something in a message by accident and pass for the wrong
# reason.
NEW_EMAIL = "newcomer@example.com"
NEW_FULL_NAME = "New Comer"
PASSWORD = "correct-horse-battery-staple"
# Seven characters, one short of `require_password`'s floor, and equally
# distinctive for the same reason.
SHORT_PASSWORD = "7chars!"

# Phase 5 review WR-01: an address no text column can hold, written as an
# escape so this file stays free of the character. It is what the form field
# `a%00b@example.com` decodes to.
UNSTORABLE_EMAIL = "a\x00b@example.com"

# The same address in two letter cases. `EmailStr` lower-cases the domain half
# only, and `User.__post_init__` lower-cases the whole address, so these two
# collide at `uq_users_email_lower` however they were typed (D-10, AUTH-01).
MIXED_CASE_EMAIL = "Ana@X.com"
LOWER_CASE_EMAIL = "ana@x.com"

# A secret this application has never signed anything with. Forty characters,
# so it clears the `min_length` floor a `Settings` object would impose - not
# that one is built from it, but a shorter value would invite the reader to
# wonder whether the refusal came from the length rather than the signature.
FOREIGN_SECRET = "wrong" * 8

GARBAGE_TOKEN = "not-a-token-at-all"


def a_registration(
    *,
    email: str = NEW_EMAIL,
    full_name: str = NEW_FULL_NAME,
    password: str = PASSWORD,
) -> dict[str, str]:
    """A valid register body, differing from the default only where asked."""
    return {"email": email, "full_name": full_name, "password": password}


def a_login_form(
    *, username: str = NEW_EMAIL, password: str = PASSWORD
) -> dict[str, str]:
    """A valid login form. `username` carries the address - OAuth2 fixes the name."""
    return {"username": username, "password": password}


async def as_the_caller(app: FastAPI) -> dict[str, str]:
    """A bearer header for the seeded caller, for reading `USERS` back.

    Registering has no resource of its own to read back. `GET /auth/me` answers
    about the *caller*, and a freshly created account has no token yet, so the
    account's existence is read out of the user directory instead - the one
    published route that lists accounts (ASGN-03).

    That route is closed (D-11), so the re-read costs a seeded caller and a
    token minted for it. This is why every register test below takes
    `session_factory` and seeds `a_user()`: the caller exists so that the
    directory can be read, and it is never the account under test.

    Only the header is built here. The `GET` itself stays written out in each
    test, because a re-read hidden inside a helper is a re-read a reader has to
    go looking for - and the D-05 gate reads the test, not the helper.
    """
    return {"Authorization": await bearer_header(app, OWNER_ID)}


def configured_settings() -> Settings:
    """The settings the harness's application was built from.

    `authenticated_client` monkeypatches `DATABASE_URL` and `JWT_SECRET` and
    then constructs `Settings(_env_file=None)`, so an identical construction
    inside a test yields the identical object - including the signing secret,
    the algorithm and the lifetime. That is what lets the forged tokens below
    match the application on everything except the one property under test.
    """
    return Settings(_env_file=None)


@dataclass(frozen=True, slots=True)
class StoppedClock:
    """A `Clock` frozen at one instant, for minting a token in the past.

    Declared here rather than imported from `tests/unit/application/fakes.py`.
    That module is the application layer's fake *world* - a unit of work, three
    repositories, a hasher that records - and pulling all of it into an HTTP
    suite to borrow three lines would couple this file to every change made
    over there. Conformance is structural, so there is nothing to inherit.

    This is also why the expired-token case needs no sleeping and no library
    that rewrites the clock: PyJWT validates `exp` against the real
    `time.time()`, so the only controllable side is the issuing one, and
    issuing two hours ago with a thirty-minute lifetime produces a token that
    expired ninety minutes before the request is made.
    """

    instant: datetime

    def now(self) -> datetime:
        return self.instant


async def test_register_answers_201_with_the_profile_and_a_location_header(
    authenticated_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """AUTH-01, D-09: the account, the four members, and no token (D-19)."""
    await seed(session_factory, users=[a_user()])
    client, app = authenticated_client

    response = await client.post(REGISTER, json=a_registration())

    assert response.status_code == 201

    body = response.json()

    assert list(body) == PROFILE_MEMBERS
    assert body["email"] == NEW_EMAIL
    assert body["full_name"] == NEW_FULL_NAME
    assert uuid.UUID(body["id"])
    # D-19's divergence: the header names the profile route rather than the
    # account, because this phase publishes no user-by-id route to name.
    assert response.headers["Location"].endswith(ME)
    # No token, and no credential: registering and logging in are two steps.
    assert "access_token" not in response.text
    assert PASSWORD not in response.text

    listed = await client.get(USERS, headers=await as_the_caller(app))

    assert listed.status_code == 200
    assert body["id"] in [entry["id"] for entry in listed.json()]
    assert NEW_EMAIL in listed.text
    assert PASSWORD not in listed.text


async def test_register_then_login_then_get_me_reads_back_the_same_profile(
    authenticated_client: tuple[AsyncClient, FastAPI],
) -> None:
    """The re-read: the account is a fact about the database, not about a 201.

    Three real requests rather than an assertion on the register body alone. A
    handler that answered a perfect 201 and rolled its transaction back would
    pass every assertion in the test above, and would fail on the login here -
    which is precisely the failure the standard exists to catch.
    """
    client, _ = authenticated_client

    created = await client.post(REGISTER, json=a_registration())
    assert created.status_code == 201

    logged_in = await client.post(LOGIN, data=a_login_form())
    assert logged_in.status_code == 200

    token = logged_in.json()["access_token"]
    profile = await client.get(ME, headers={"Authorization": f"Bearer {token}"})

    assert profile.status_code == 200
    assert list(profile.json()) == PROFILE_MEMBERS
    assert profile.json() == created.json()


async def test_register_with_the_same_address_in_another_case_is_a_duplicate_409(
    authenticated_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """AUTH-01's conflict, and D-23's bound on what it is allowed to say.

    The 409 is an account-enumeration oracle and is accepted as one, because
    the requirement asks for it. What is *not* accepted is a body that repeats
    the address: the caller already knows what they submitted, and a body
    carrying it would put the value into logs and error trackers as well.
    """
    await seed(session_factory, users=[a_user()])
    client, app = authenticated_client

    first = await client.post(REGISTER, json=a_registration(email=MIXED_CASE_EMAIL))
    assert first.status_code == 201

    second = await client.post(REGISTER, json=a_registration(email=LOWER_CASE_EMAIL))

    assert second.status_code == 409
    assert second.headers["content-type"] == PROBLEM_JSON

    body = second.json()

    assert list(body) == [*MEMBERS, "errors"]
    assert body["code"] == "email_already_registered"
    assert body["errors"] == {"field": "email"}
    # Neither spelling of the address, in any member of the document.
    assert MIXED_CASE_EMAIL not in second.text
    assert LOWER_CASE_EMAIL not in second.text

    # The refusal left one account, not two. `User.__post_init__` lower-cases
    # the whole address, so the stored spelling is the lower-case one whichever
    # way it was typed - which is what makes counting it the right assertion.
    after = await client.get(USERS, headers=await as_the_caller(app))

    assert [entry["email"] for entry in after.json()].count(LOWER_CASE_EMAIL) == 1
    assert MIXED_CASE_EMAIL not in after.text


async def test_register_with_a_seven_character_password_is_422_and_never_echoes_it(
    authenticated_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """The domain's 8-to-128 policy over HTTP, naming the field and not the value.

    The refusal comes from `require_password` rather than from the schema - the
    bound lives in the domain and the boundary declares none - so this is the
    project's domain-validation 422 rather than the request-validation one, and
    its `errors` member is an object naming the field.
    """
    await seed(session_factory, users=[a_user()])
    client, app = authenticated_client

    response = await client.post(REGISTER, json=a_registration(password=SHORT_PASSWORD))

    assert response.status_code == 422
    assert response.headers["content-type"] == PROBLEM_JSON

    body = response.json()

    assert list(body) == [*MEMBERS, "errors"]
    assert body["code"] == "validation_error"
    assert body["errors"] == {"field": "password"}
    assert SHORT_PASSWORD not in response.text

    # D-06: no account, and therefore no Argon2 hash of a password the policy
    # refused. The directory holds the seeded caller alone.
    after = await client.get(USERS, headers=await as_the_caller(app))

    assert [entry["email"] for entry in after.json()] == [DEMO_EMAIL]
    assert NEW_EMAIL not in after.text


async def test_register_with_an_unknown_key_is_one_extra_forbidden_error(
    authenticated_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """T-5-09: a privilege cannot be smuggled in as an extra member.

    `RegisterRequest` forbids extras, so `id`, `created_at` and anything else a
    client invents is one named 422 rather than a value quietly accepted and
    ignored - or, worse, quietly used.
    """
    await seed(session_factory, users=[a_user()])
    client, app = authenticated_client
    payload = {**a_registration(), "is_admin": "true"}

    response = await client.post(REGISTER, json=payload)

    assert response.status_code == 422
    assert response.headers["content-type"] == PROBLEM_JSON

    body = response.json()

    assert list(body) == [*MEMBERS, "errors"]
    assert body["code"] == "validation_error"
    assert len(body["errors"]) == 1
    assert body["errors"][0]["type"] == "extra_forbidden"
    assert body["errors"][0]["field"] == "body.is_admin"
    assert PASSWORD not in response.text

    # Refused as a whole, not accepted with the extra member dropped.
    after = await client.get(USERS, headers=await as_the_caller(app))

    assert [entry["email"] for entry in after.json()] == [DEMO_EMAIL]
    assert NEW_EMAIL not in after.text


@pytest.mark.no_reread(
    "POST /auth/login mutates no resource, so there is nothing to read back. The\n"
    "register above is setup; its persistence is proved by\n"
    "test_register_then_login_then_get_me_reads_back_the_same_profile, and the\n"
    "successful login below is itself that re-read - spelled as a POST, which is\n"
    "why the gate cannot see it."
)
async def test_login_answers_a_bearer_token_and_the_configured_lifetime(
    authenticated_client: tuple[AsyncClient, FastAPI],
) -> None:
    """AUTH-02: the three members, and `expires_in` bound to the configuration.

    The lifetime is compared against the setting rather than against a literal
    number of seconds. A literal would be asserting that somebody typed 1800
    here and 30 there; deriving it asserts the property that actually matters,
    which is that the number the client is told and the number the token was
    signed with come from one place (see `SecurityResources`).
    """
    client, _ = authenticated_client

    created = await client.post(REGISTER, json=a_registration())
    assert created.status_code == 201

    response = await client.post(LOGIN, data=a_login_form())

    assert response.status_code == 200

    body = response.json()

    assert list(body) == TOKEN_MEMBERS
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == configured_settings().jwt_expire_minutes * 60
    assert body["expires_in"] > 0
    assert body["access_token"]
    assert PASSWORD not in response.text


@pytest.mark.no_reread(
    "POST /auth/login mutates no resource, and this leg never reaches the use\n"
    "case at all: the form is refused at the boundary, so there is no state for a\n"
    "GET to be about."
)
async def test_login_without_a_password_is_422_and_does_not_echo_the_username(
    authenticated_client: tuple[AsyncClient, FastAPI],
) -> None:
    """A malformed form is the project's own 422, keeping loc/msg/type only.

    The submitted `username` is an address, so a validation handler that passed
    Pydantic's raw entries through - each of which carries the client's own
    input - would turn every malformed login into an echo of whatever was
    typed into it (T-5-04, D-07).
    """
    client, _ = authenticated_client
    ghost = "ghost@example.com"

    response = await client.post(LOGIN, data={"username": ghost})

    assert response.status_code == 422
    assert response.headers["content-type"] == PROBLEM_JSON

    body = response.json()

    assert list(body) == [*MEMBERS, "errors"]
    assert body["code"] == "validation_error"
    assert [error["field"] for error in body["errors"]] == ["body.password"]
    assert ghost not in response.text


@pytest.mark.no_reread(
    "POST /auth/login mutates no resource. The register above is setup, proved by\n"
    "test_register_then_login_then_get_me_reads_back_the_same_profile; what this\n"
    "test asserts is that two refusals are one document, which no GET can show."
)
async def test_login_with_an_unknown_address_and_with_a_wrong_password_are_indistinguishable(  # noqa: E501
    authenticated_client: tuple[AsyncClient, FastAPI],
) -> None:
    """D-12, AUTH-04: the two failures are one answer, compared body to body.

    Comparing statuses would prove almost nothing - both legs were always going
    to be 401 - so the comparison is over the serialised documents. A
    difference in `code`, in `detail`, in `title` or in the presence of an
    `errors` member would fail here and would sail straight through a status
    assertion, and any one of them is an account-enumeration oracle.
    """
    client, _ = authenticated_client

    created = await client.post(REGISTER, json=a_registration())
    assert created.status_code == 201

    unknown_address = await client.post(
        LOGIN, data=a_login_form(username="nobody@example.com")
    )
    wrong_password = await client.post(
        LOGIN, data=a_login_form(password="not-the-password-that-was-registered")
    )

    assert unknown_address.status_code == 401
    assert wrong_password.status_code == 401
    assert unknown_address.headers["content-type"] == PROBLEM_JSON
    assert unknown_address.headers["WWW-Authenticate"] == "Bearer"
    assert wrong_password.headers["WWW-Authenticate"] == "Bearer"

    body = unknown_address.json()

    assert list(body) == MEMBERS
    assert body["code"] == "authentication_failed"
    # No identifier appears in either document, so nothing needs tokenising -
    # `anonymised` is still the comparison used, because "identical modulo the
    # identifiers each one carries" is the claim every indistinguishability
    # test in this project makes, and spelling it the same way keeps them
    # comparable.
    assert anonymised(unknown_address) == anonymised(wrong_password)
    assert "nobody@example.com" not in unknown_address.text
    assert PASSWORD not in wrong_password.text


@pytest.mark.no_reread(
    "POST /auth/login mutates no resource, and the point of this test is that the\n"
    "NUL never reached a statement. The register above is setup, proved by\n"
    "test_register_then_login_then_get_me_reads_back_the_same_profile."
)
async def test_login_with_an_unstorable_username_is_the_same_401(
    authenticated_client: tuple[AsyncClient, FastAPI],
) -> None:
    """WR-01: a NUL in `username` answers the ordinary refusal, not a 500.

    The login form has no schema by design, so nothing above the use case
    refused this value: it reached psycopg, the statement failed, and the
    fixed 500 came back with the submitted address in the log. The body is
    compared against the unknown-address refusal built beside it, because "it
    is a 401 now" would also be true of a 401 that said something different.
    """
    client, _ = authenticated_client

    created = await client.post(REGISTER, json=a_registration())
    assert created.status_code == 201

    unstorable = await client.post(LOGIN, data=a_login_form(username=UNSTORABLE_EMAIL))
    unknown_address = await client.post(
        LOGIN, data=a_login_form(username="nobody@example.com")
    )

    assert unstorable.status_code == 401
    assert unstorable.headers["content-type"] == PROBLEM_JSON
    assert unstorable.headers["WWW-Authenticate"] == "Bearer"
    assert list(unstorable.json()) == MEMBERS
    assert anonymised(unstorable) == anonymised(unknown_address)


async def test_register_with_an_unstorable_name_is_the_domains_422(
    authenticated_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """WR-04: an unpaired surrogate in `full_name` is refused by the domain.

    The body is sent as a raw string rather than as a dict, because the value
    only exists as the JSON escape `\\ud800`: it passes Pydantic's `str`, and
    before this fix it passed every domain guard too and became a 500 while
    psycopg bound the INSERT - after a full Argon2 hash had been paid for by an
    unauthenticated request.
    """
    await seed(session_factory, users=[a_user()])
    client, app = authenticated_client

    response = await client.post(
        REGISTER,
        content=(
            '{"email": "surrogate@example.com", '
            '"full_name": "A\\ud800B", '
            f'"password": "{PASSWORD}"}}'
        ),
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 422
    assert response.headers["content-type"] == PROBLEM_JSON

    body = response.json()

    assert list(body) == [*MEMBERS, "errors"]
    assert body["code"] == "validation_error"
    assert body["errors"] == {"field": "full_name"}

    # Refused before the INSERT rather than after it: the directory holds the
    # seeded caller alone, and nothing addressed `surrogate@example.com`.
    after = await client.get(USERS, headers=await as_the_caller(app))

    assert [entry["email"] for entry in after.json()] == [DEMO_EMAIL]
    assert "surrogate@example.com" not in after.text
    assert "ud800" not in response.text


async def test_get_me_answers_the_callers_own_profile_and_no_stored_hash(
    authenticated_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """AUTH-05: the caller's own account, read through a real minted token.

    The row is seeded rather than registered, because this test is about the
    read and not about the write: seeding costs one `INSERT` where registering
    costs an Argon2 hash, and the round trip through registration already has a
    test of its own above.
    """
    await seed(session_factory, users=[a_user()])
    client, app = authenticated_client

    response = await client.get(
        ME, headers={"Authorization": await bearer_header(app, OWNER_ID)}
    )

    assert response.status_code == 200

    body = response.json()

    assert list(body) == PROFILE_MEMBERS
    assert body["id"] == str(OWNER_ID)
    assert body["email"] == DEMO_EMAIL
    assert body["full_name"] == DEMO_FULL_NAME


# ---------------------------------------------------------------------------
# The seven ways a caller can fail to authenticate.
#
# One parametrized test rather than seven functions, so a case that was never
# written is *visible* as a missing row in the table below rather than absent
# from the file. Each builder returns the `Authorization` value to send, or
# `None` for "send no header at all".
# ---------------------------------------------------------------------------

HeaderBuilder = Callable[[FastAPI], Awaitable[str | None]]


async def no_header(app: FastAPI) -> str | None:
    """The anonymous caller: no credential offered at all."""
    return None


async def a_basic_scheme(app: FastAPI) -> str | None:
    """A credential of the wrong kind. The bearer scheme hands over `None`."""
    return "Basic zzz"


async def an_empty_bearer_parameter(app: FastAPI) -> str | None:
    """The right scheme with nothing after it - the scheme hands over `""`.

    This is the second of the two shapes `get_current_actor`'s emptiness check
    covers, and the reason it is a truthiness test rather than an identity test
    against `None`.
    """
    return "Bearer "


async def garbage(app: FastAPI) -> str | None:
    """Not a token in any format: the decode fails before any claim is read."""
    return f"Bearer {GARBAGE_TOKEN}"


async def a_foreign_secret_token(app: FastAPI) -> str | None:
    """A perfectly well-formed token this application never signed (T-5-01).

    Built here rather than through any adapter of ours, and signed with the
    algorithm the application is configured for, so the only thing wrong with
    it is the key. That is what makes it a test of signature verification
    rather than of anything else.
    """
    issued_at = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": str(OWNER_ID),
            "iat": issued_at,
            "exp": issued_at + timedelta(minutes=30),
        },
        FOREIGN_SECRET,
        algorithm=configured_settings().jwt_algorithm,
    )
    return f"Bearer {token}"


async def an_expired_token(app: FastAPI) -> str | None:
    """A token this application really issued, two hours before the request.

    Minted through a real security container built from the real settings and
    a clock stopped in the past, so the secret, the algorithm and the lifetime
    are all the application's own and only the issuing instant differs.
    """
    two_hours_ago = StoppedClock(datetime.now(UTC) - timedelta(hours=2))
    security = create_security_resources(configured_settings(), two_hours_ago)
    return f"Bearer {await security.token_service.issue_access_token(OWNER_ID)}"


async def a_token_for_an_unknown_subject(app: FastAPI) -> str | None:
    """A flawless token naming an account that was never created (T-5-15).

    This is the one case that a signature check alone cannot refuse, and the
    only case that exercises what D-11 bought: the extra confirmation read
    `AuthenticateActor` performs on every request. The subject is therefore a
    freshly generated identifier, and it has to stay one: the test below now
    seeds the *caller's* row precisely so the other six cases stop collapsing
    into this one, and a token minted for `OWNER_ID` here would turn this case
    into a test of nothing at all. A generated identifier cannot collide with a
    row a sibling test left behind, because the harness leaves none.
    """
    return await bearer_header(app, uuid.uuid4())


UNAUTHENTICATED_CASES: tuple[tuple[str, HeaderBuilder], ...] = (
    ("no_header", no_header),
    ("a_basic_scheme", a_basic_scheme),
    ("an_empty_bearer_parameter", an_empty_bearer_parameter),
    ("garbage", garbage),
    ("a_foreign_secret_token", a_foreign_secret_token),
    ("an_expired_token", an_expired_token),
    ("a_token_for_an_unknown_subject", a_token_for_an_unknown_subject),
)


@pytest.mark.parametrize(
    "build_header",
    [build for _, build in UNAUTHENTICATED_CASES],
    ids=[name for name, _ in UNAUTHENTICATED_CASES],
)
async def test_unauthenticated_requests_are_refused_with_the_one_shared_body(
    authenticated_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
    build_header: HeaderBuilder,
) -> None:
    """AUTH-03, T-5-01, T-5-04, T-5-15: one shape for every failure mode.

    The route driven is `GET /auth/me`, so `instance` is the same path in all
    seven answers and the documents are comparable without tokenising anything
    - which the companion test below relies on.

    **The caller's row is seeded, and that line is the whole of Phase 6's D-14
    finding here.** `AuthenticateActor` confirms the subject on *every* request
    (D-11), so with no `users` row for `OWNER_ID` six of these seven cases were
    refused for the unknown-subject reason no matter what credential they
    carried - the expired token, the foreign signature and the garbage were all
    decided by a read that came after the mechanism each case names. Measured,
    not inferred: with `verify_exp: False` planted in
    `infrastructure/security/tokens.py` every test in this selection stayed
    green, which is a suite reporting that token expiry is enforced while
    nothing checked it. Seeding the caller sends each case down its own branch,
    and the same plant now turns `an_expired_token` red.

    `a_token_for_an_unknown_subject` is the one case that must *not* be reached
    by a seeded subject, and it signs for a fresh identifier so it still is not;
    its docstring says so.
    """
    await seed(session_factory, users=[a_user()])
    client, app = authenticated_client
    header = await build_header(app)
    headers = {} if header is None else {"Authorization": header}

    response = await client.get(ME, headers=headers)

    assert response.status_code == 401
    assert response.headers["content-type"] == PROBLEM_JSON
    # RFC 9110 15.5.2: a 401 must carry a challenge, and this is the only place
    # the whole phase proves the handler attaches one to a domain refusal.
    assert response.headers["WWW-Authenticate"] == "Bearer"

    body = response.json()

    # No `errors` member: the generic refusal carries no details, so there is
    # nothing in the document that could differ between two of these cases.
    assert list(body) == MEMBERS
    assert body["code"] == "authentication_failed"
    assert body["detail"] == AuthenticationError.REFUSAL
    assert body["instance"] == ME

    # T-5-04: whatever was offered is not read back. The two cases that offer
    # no credential material are skipped rather than asserted, because the
    # empty string is a substring of every document and the assertion would
    # pass without checking anything.
    credential = header.partition(" ")[2] if header is not None else ""
    if credential:
        assert credential not in response.text


async def test_every_unauthenticated_refusal_carries_the_same_body_as_the_others(
    authenticated_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """D-11: seven failures, one answer - asserted across the cases, not within.

    The parametrized test above pins the *shape* of each refusal, which is
    already strong; what it structurally cannot do is compare one case with
    another, because each parameter runs in its own test. A leak that made, say,
    the unknown-subject case differ from the expired one would satisfy every
    assertion up there if it happened to be in a member neither of them names.

    So this drives all seven in one test and asserts the set of serialised
    bodies has exactly one member. The failure message names the cases, so a
    regression says which two answers diverged rather than that a set was too
    large.

    The caller is seeded here for the reason given above: unseeded, this test
    compared six answers that were all the unknown-subject answer, so "they are
    identical" was true by construction rather than by design. Seeded, the six
    reach their own branches and the bodies still have to come out byte-identical
    - which is now a claim about the handler instead of about the fixture.
    """
    await seed(session_factory, users=[a_user()])
    client, app = authenticated_client
    bodies: dict[str, str] = {}

    for name, build_header in UNAUTHENTICATED_CASES:
        header = await build_header(app)
        headers = {} if header is None else {"Authorization": header}
        response = await client.get(ME, headers=headers)
        assert response.status_code == 401
        bodies[name] = anonymised(response)

    assert len(set(bodies.values())) == 1, bodies
