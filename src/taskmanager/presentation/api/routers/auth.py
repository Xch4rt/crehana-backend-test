"""The three auth routes: create an account, exchange it for a token, read it.

`task_lists.py`'s module docstring states the rules every handler in this
package follows - no error answered here, no transaction entered or ended here,
no business limit re-checked here, an explicit `response_model` on every route,
and a `responses` map naming every leg - and they are not restated.

Four things are specific to this module.

**Two of these handlers take no caller, and they are the only two in the
project that do not.** The absence is the openness of the route, and an absence
is invisible: nothing in a signature says "this one is deliberately
unauthenticated", so each of the two says it in its own docstring, and rows 2
and 3 of plan 05-15's permission matrix are what prove it over HTTP. Everything
else in this API - including `read_current_user` below - takes the caller as a
parameter and is refused without a token.

**Login reads a form, not a JSON body.** That is what Swagger's Authorize
button drives (AUTH-02), and it is why `schemas/auth.py` declares no request
model for it: the fields arrive through the web framework's own OAuth2 form
object. Consequently `login` is the one handler in this project that builds its
command itself rather than calling `to_command(...)` on a schema - there is no
schema to call it on. A malformed form is still the project's own 422, from the
single validation handler, which keeps only the field, the message and the type
and therefore cannot echo the submitted credential back (T-5-04).

**Nothing here spells a URL and nothing here reads configuration.** The
`Location` header on register is resolved from the handler's name, for the
reason `task_lists.py` gives about a change of prefix, and the token lifetime
arrives through an injected dependency rather than by reaching for the settings
accessor in a router - `dependencies.py` states that rule (RC-3) and the
provider it added for this route explains why the number lives in the security
container.

**The refusal descriptions are declared here, not imported from a sibling
router.** `schemas/tasks.py` states that rule and its reason: a shared constant
makes one endpoint's wording change another's. The 401 wording is new in this
module and the phase's other routers will declare their own.
"""

from typing import Annotated, Final

from fastapi import APIRouter, Depends, FastAPI, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm

from taskmanager.application.dto.commands import GetProfileCommand, LoginCommand
from taskmanager.application.use_cases.auth.login import Login
from taskmanager.application.use_cases.auth.profile import GetProfile
from taskmanager.application.use_cases.auth.register import RegisterUser
from taskmanager.presentation.api.actor import CurrentActor
from taskmanager.presentation.api.dependencies import (
    AccessTokenExpiryDependency,
    ClockDependency,
    PasswordHasherDependency,
    TokenServiceDependency,
    UnitOfWorkDependency,
)
from taskmanager.presentation.api.schemas.auth import (
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from taskmanager.presentation.api.schemas.problem import problem_response

# The prefix is declared once, on the router, exactly as its two siblings do -
# which is what lets the `Location` header below survive a change to either
# this prefix or the version one.
auth_router = APIRouter(prefix="/auth", tags=["auth"])

DUPLICATE_EMAIL_DESCRIPTION: Final[str] = (
    "An account with this address already exists. Answering at all tells an "
    "unauthenticated caller that an address is registered, which is an "
    "account-enumeration oracle: AUTH-01 requires the conflict, so it is "
    "accepted and bounded rather than claimed to be mitigated (D-23). The "
    "body repeats no address, and logging in concedes nothing of the kind - "
    "a wrong password and an unknown address answer identically (D-12)."
)
UNAUTHENTICATED_DESCRIPTION: Final[str] = (
    "No usable credential. A missing, malformed, badly signed or expired "
    "token, and a token naming an account that no longer exists, all produce "
    "this same body with the same message, so it discloses nothing about "
    "which half of the credential was wrong (D-11)."
)
CREDENTIALS_DESCRIPTION: Final[str] = (
    "The credential was refused. An unknown address and a wrong password "
    "produce byte-identical answers, and the unknown-address path performs "
    "the same hashing work, so the two are indistinguishable in content and "
    "in time alike (D-12, AUTH-04)."
)
PROFILE_GONE_DESCRIPTION: Final[str] = (
    "The account named by the token no longer exists. Reachable only by a "
    "deletion landing between the token check and this read, which is why it "
    "is an ordinary not-found rather than the generic 401: the token was "
    "sound and the caller already knows their own identifier."
)
VALIDATION_DESCRIPTION: Final[str] = (
    "The request is malformed - an unknown or missing field, an address that "
    "is not one - or a value breaks a domain rule such as the 8-to-128 "
    "character password policy. The submitted value is never echoed back."
)
UNEXPECTED_DESCRIPTION: Final[str] = (
    "An unexpected server-side failure. The body is the same problem+json "
    "document as every other error, and carries no internal detail."
)


@auth_router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=UserResponse,
    summary="Register an account",
    response_description=(
        "The new account's profile - and no token: logging in is a separate "
        "step through the login route below (D-09). The Location header names "
        "the profile route."
    ),
    responses={
        409: problem_response(DUPLICATE_EMAIL_DESCRIPTION),
        422: problem_response(VALIDATION_DESCRIPTION),
        500: problem_response(UNEXPECTED_DESCRIPTION),
    },
)
async def register_user(
    payload: RegisterRequest,
    uow: UnitOfWorkDependency,
    hasher: PasswordHasherDependency,
    clock: ClockDependency,
    request: Request,
    response: Response,
) -> UserResponse:
    """Create an account from an unauthenticated request (AUTH-01, D-09).

    **This handler takes no caller, and that is the point.** It and the login
    route below are the only two in this project with no actor parameter,
    because this is the operation that creates an identity - there is nobody to
    authenticate yet. Every other route in the API refuses a request with no
    token; these two must not, and nothing in a signature says so out loud,
    which is why it is said here. Rows 2 and 3 of plan 05-15's permission
    matrix drive both routes anonymously and prove it.

    **The Location header names the profile route, not the account created.**
    That is a real divergence from every other `Location` in this project,
    which names the resource just made. D-19 chose it: a user-by-id route would
    be the resource to name, there is none in this phase, and adding one was
    considered and left outside the phase boundary. So the header points at
    `/api/v1/auth/me` - a representation of the very account just created,
    which the caller can read only once they have logged in. The header is
    resolved from the handler's name rather than spelled as a path, for the
    reason `routers/task_lists.py` states: a spelled path outlives neither
    prefix.
    """
    result = await RegisterUser(uow, hasher, clock).execute(payload.to_command())
    response.headers["Location"] = str(request.url_for("read_current_user"))
    return UserResponse.from_result(result)


@auth_router.post(
    "/login",
    response_model=TokenResponse,
    summary="Log in and get an access token",
    response_description=(
        "The access token, the token type to put in front of it, and how many "
        "seconds it is good for."
    ),
    responses={
        401: problem_response(CREDENTIALS_DESCRIPTION),
        422: problem_response(VALIDATION_DESCRIPTION),
        500: problem_response(UNEXPECTED_DESCRIPTION),
    },
)
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    uow: UnitOfWorkDependency,
    hasher: PasswordHasherDependency,
    tokens: TokenServiceDependency,
    expire_minutes: AccessTokenExpiryDependency,
) -> TokenResponse:
    """Exchange an email and a password for a bearer token (AUTH-02).

    **Send `username`, and put your email address in it.** The field name is
    not this API's choice: the OAuth2 password flow fixes the form to
    `username` and `password`, and Swagger's Authorize button posts exactly
    that. This API's usernames *are* email addresses, so the value belongs in
    the `username` field and the rename happens here, on the way in - nothing
    from the command inward says anything but `email`. The request is a form
    (`application/x-www-form-urlencoded`), not JSON, for the same reason.

    **This handler takes no caller either**, and for the reason the register
    route above sets out at length: it is the operation that identifies
    somebody, so there is nobody to identify it with. These two are the only
    such handlers in the project.

    `expires_in` is derived from the same configured lifetime the token service
    signed the token with, because both reach this request from the one
    container the composition root built - see the provider's docstring.
    """
    result = await Login(uow, hasher, tokens, expire_minutes).execute(
        # The one command in this project built by a handler rather than by a
        # schema's `to_command`: the form is read by the web framework's own
        # object, so there is no schema of ours to put the method on.
        LoginCommand(email=form.username, password=form.password)
    )
    return TokenResponse.from_result(result)


@auth_router.get(
    "/me",
    response_model=UserResponse,
    summary="Read the caller's own profile",
    response_description=(
        "The caller's profile, in the same four members register answered "
        "with - and never the stored password hash (AUTH-05)."
    ),
    responses={
        401: problem_response(UNAUTHENTICATED_DESCRIPTION),
        404: problem_response(PROFILE_GONE_DESCRIPTION),
        500: problem_response(UNEXPECTED_DESCRIPTION),
    },
)
async def read_current_user(
    actor_id: CurrentActor,
    uow: UnitOfWorkDependency,
) -> UserResponse:
    """The authenticated caller's own account, and nobody else's (AUTH-05).

    There is no identifier in the path and none in a query, so this route
    cannot be aimed at another account: the only input is the caller, and the
    command carries one field for exactly that reason.

    The function name is load-bearing rather than descriptive - the register
    route resolves its `Location` header from it, so renaming it here without
    renaming it there breaks the header rather than the import.
    """
    result = await GetProfile(uow).execute(GetProfileCommand(actor_id=actor_id))
    return UserResponse.from_result(result)


def register_auth_routes(app: FastAPI) -> None:
    """Install the auth router under `/api/v1`, from create_app().

    Imperative and called from the composition root, exactly as its two
    siblings are: the router attaches to the application the factory built,
    never to a module-level instance, so importing this module creates nothing
    and connects to nothing.

    The version prefix is applied here rather than written into the router, for
    the reason `register_task_list_routes` gives - and the login path this
    produces is the one the bearer scheme in `actor.py` was constructed with.
    A mismatch between the two would leave Swagger's Authorize button visible
    and posting into a 404, which is why plan 05-11's security-scheme test
    compares them through the published document.
    """
    app.include_router(auth_router, prefix="/api/v1")
