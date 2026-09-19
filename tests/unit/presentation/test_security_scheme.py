"""The Authorize button's contract, read out of the document it is built from.

AUTH-02's acceptance is a human clicking **Authorize** in `/docs`, typing an
email and a password, and finding every other route callable. Three things have
to be true of the published document for that to work, and none of them is
visible in any handler's signature:

* the document must declare an OAuth2 password-flow scheme, which is what makes
  the button exist at all;
* that scheme's `tokenUrl` must name a route that accepts a form - a `tokenUrl`
  pointing nowhere leaves the button visible and posting into a 404, which is
  the single most expensive failure available here because it looks like
  working software right up until somebody tries it;
* every operation that needs a token must *say* it needs one, and the three
  that do not must say nothing - a document that misdescribes either direction
  misleads every client generated from it.

**Everything below reads `app.openapi()` and nothing below reads the route
table** (ADR-057). On the pinned stack an included router is left in the
application's route collection as a single opaque object with neither a path
nor a method, so an inventory taken from it would find the documentation
endpoints and none of the real ones. The document is also the artifact a client
actually consumes, which makes it the honest place to assert a published
contract.

**The shape of the main assertion is a partition, and that is the point.** A
loop over a hand-written list of secured routes would be exactly as long and
would say nothing about a route nobody remembered to add to the list: a new
endpoint shipped without a caller parameter would simply not be mentioned. Here
every operation in the document must fall on one side or the other, so the
route that was forgotten is the one that fails. Plan 05-12 adds three more
routes and this module must keep passing untouched; that is the property being
bought.

Falsified rather than assumed: a throwaway route with no caller parameter was
added to the auth router and the partition test named it - the capture is
`.planning/phases/05-auth-assignment-notifications/evidence/05-11-open-route-falsification.txt`.
"""

from typing import Any, Final

from taskmanager.infrastructure.config.settings import Settings
from taskmanager.main import create_app

DATABASE_URL = "postgresql+psycopg://user:pass@localhost:5432/taskmanager"
JWT_SECRET = "b" * 32

# The name FastAPI derives from the security class the actor seam constructs.
# Spelled here because it is the key a client looks up, and the button breaks
# if it changes.
SCHEME_NAME: Final[str] = "OAuth2PasswordBearer"

LOGIN_PATH: Final[str] = "/api/v1/auth/login"

# Everything an OpenAPI path item can hold that is not an operation. Filtering
# by an allow-list of verbs instead would silently drop a verb this API grows
# later; this way a new one is included and has to satisfy the partition.
NON_OPERATION_KEYS: Final[frozenset[str]] = frozenset(
    {"summary", "description", "servers", "parameters", "$ref"}
)

# The three operations that carry no security requirement, each with the reason
# it is open. This is the whole exemption list: anything not named here must
# demand a token.
#
#   `/health`                   - the compose healthcheck reads it on an
#                                 interval with no credential to offer, so a
#                                 token requirement here would make the
#                                 container permanently unhealthy.
#   `POST /auth/register`       - open by definition: it is the operation that
#                                 creates the identity a token would name.
#   `POST /auth/login`          - open by definition: it is the operation that
#                                 issues the token.
OPEN_OPERATIONS: Final[frozenset[tuple[str, str]]] = frozenset(
    {
        ("get", "/health"),
        ("post", "/api/v1/auth/register"),
        ("post", LOGIN_PATH),
    }
)


def _document() -> dict[str, Any]:
    """The published OpenAPI document of the real application.

    Settings are injected rather than read from the environment, so this module
    needs no `.env`, no database and no network - the same promise every other
    unit test in this suite rests on.
    """
    application = create_app(
        Settings(
            _env_file=None,
            database_url=DATABASE_URL,
            jwt_secret=JWT_SECRET,
        )
    )
    return application.openapi()


def _operations() -> dict[tuple[str, str], dict[str, Any]]:
    """Every operation in the document, keyed by (method, path)."""
    return {
        (method, path): operation
        for path, item in _document()["paths"].items()
        for method, operation in item.items()
        if method not in NON_OPERATION_KEYS
    }


def test_the_document_declares_the_oauth2_password_scheme() -> None:
    """Without this entry there is no Authorize button in `/docs` at all.

    The scheme reaches the document through the bearer object the actor seam
    depends on, never by being written into the application by hand - so this
    also pins that the seam is still wired the way it was built.
    """
    components = _document()["components"]

    assert SCHEME_NAME in components["securitySchemes"], sorted(
        components["securitySchemes"]
    )
    scheme = components["securitySchemes"][SCHEME_NAME]
    assert scheme["type"] == "oauth2"
    assert "password" in scheme["flows"]


def test_the_token_url_resolves_to_the_login_route() -> None:
    """The button posts here, so here has to exist and accept a form.

    This is the one automated check standing behind AUTH-02's manual
    verification. A `tokenUrl` naming a path this application does not serve
    produces a button that appears, accepts a password and answers 404 - a
    failure invisible to every other test in the project, because nothing else
    reads the two facts together. Asserted as a pair deliberately: the value
    the scheme publishes, *and* the operation it names being published too.
    """
    document = _document()
    token_url = document["components"]["securitySchemes"][SCHEME_NAME]["flows"][
        "password"
    ]["tokenUrl"]

    assert token_url.endswith(LOGIN_PATH), token_url
    assert ("post", LOGIN_PATH) in _operations()


def test_every_operation_either_requires_the_scheme_or_is_a_named_open_one() -> None:
    """The partition. A route shipped without a token requirement fails here.

    Both directions are asserted in one pass, which is what makes the test
    survive plan 05-12's three new routes without being edited: a secured route
    added later is covered because it is not in the exemption set, and an open
    one added later fails because it is not in the exemption set either. A
    per-route loop over a list of expected secured routes would have said
    nothing about either.
    """
    operations = _operations()
    assert operations

    secured = {
        endpoint: operation.get("security")
        for endpoint, operation in operations.items()
        if endpoint not in OPEN_OPERATIONS
    }

    assert all(requirement for requirement in secured.values()), [
        endpoint for endpoint, requirement in secured.items() if not requirement
    ]
    assert all(
        SCHEME_NAME in scheme
        for requirement in secured.values()
        if requirement is not None
        for scheme in requirement
    ), secured


def test_the_three_open_operations_carry_no_security_requirement() -> None:
    """Openness asserted, never skipped over.

    The exemption list is a hole in the gate above, so it has to keep earning
    itself: each of the three must exist in the document and must genuinely
    carry no requirement. A route quietly dropped from the application, or one
    that grew a token requirement it must not have - `/health` is the dangerous
    one, since the container healthcheck has no credential - fails here rather
    than passing as an entry nobody checks.
    """
    operations = _operations()

    for endpoint in sorted(OPEN_OPERATIONS):
        assert endpoint in operations, endpoint
        assert "security" not in operations[endpoint], endpoint


def test_the_secured_operations_are_every_operation_but_those_three() -> None:
    """The count, as the arithmetic statement of the same property.

    Written as a subtraction rather than as a literal number so the phase's
    remaining routes do not have to edit it. What it adds to the partition
    above is a guard against the exemption set drifting out of the document
    entirely: if a named open operation were renamed, the partition would
    still pass - the renamed route would simply be secured - while this fails,
    because three exemptions would no longer be three.
    """
    operations = _operations()

    secured = [
        endpoint
        for endpoint, operation in operations.items()
        if operation.get("security")
    ]

    assert len(secured) == len(operations) - len(OPEN_OPERATIONS)
    assert set(secured).isdisjoint(OPEN_OPERATIONS)
