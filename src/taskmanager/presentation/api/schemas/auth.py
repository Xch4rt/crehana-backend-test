"""The auth HTTP boundary: registering, the token answer, and the profile.

`task_lists.py` states the three rules this package follows - no business limit
at the boundary, the application's not-provided marker never in a field
annotation, and no instance read of the deprecated field-list attribute - and
they are not restated here.

Two things are specific to this module, and both are about the password.

It is the first value in this project that must be typed at the boundary and
then deliberately *stripped of its type* before crossing into the application
layer. `SecretStr` masks in `repr`, `str()`, `model_dump()` and
`model_dump_json()` (measured, 05-RESEARCH Pitfall 7), so a router that logged
the model, or a traceback that rendered it, prints the mask rather than the
credential - and `to_command` unwraps it exactly once, on the way in.

It is also the first field whose *policy* is nowhere near it. The 8-to-128 rule
is `domain/validation.py`'s `require_password`, and the entity owns the display
name's bound; see the comments on the two fields below.

The login request has no model here at all. `POST /auth/login` reads an OAuth2
form (`OAuth2PasswordRequestForm`, plan 05-11), which is what Swagger's
Authorize button drives, so there is no JSON body to type. A malformed form is
a 422 from the project's existing validation handler, which keeps only `loc`,
`msg` and `type` - so the submitted credential cannot reach a response body by
that route either (T-5-04).
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, SecretStr

from taskmanager.application.dto.commands import RegisterUserCommand
from taskmanager.application.dto.results import AccessTokenResult, UserResult


class RegisterRequest(BaseModel):
    """`POST /auth/register`: an address, a display name, a credential (AUTH-01).

    These three are the whole surface a request gets to influence. There is no
    `id`, no `created_at` and no role: the identifier comes from `uuid4()` in
    the use case and the timestamps from the `Clock` port, so with
    `extra="forbid"` an attempt to send any of them is one 422 naming the key
    rather than a privilege quietly granted (T-5-09).
    """

    model_config = ConfigDict(extra="forbid")

    # Format only. `EmailStr` validates the address, trims it and normalises
    # the **domain half** alone - measured: `Ana@Example.COM` arrives here as
    # `Ana@example.com`. `User.__post_init__` then lower-cases the whole
    # address, which is the form `uq_users_email_lower` and `get_by_email` both
    # rely on. The two are complementary, not duplicated, and `user.py`'s
    # module docstring already argues that split rather than it being restated
    # here.
    email: EmailStr
    # No bound on either string below, and that is the project's limits
    # convention rather than an oversight. The display name's cap is a ClassVar
    # on the `User` entity and the credential's 8-to-128 policy is
    # `domain/validation.py`'s, per Phase 2 D-04 and CONTEXT D-10. A second
    # copy here would be the one a client actually hits, it would drift the
    # first time the entity's changed, and it would answer with the
    # request-validation error shape instead of the domain's - while the 422
    # the domain raises already names the field.
    full_name: str
    password: SecretStr

    def to_command(self) -> RegisterUserCommand:
        """Hand the application layer a command carrying a plain string.

        This is the one place the credential is unwrapped, and the unwrapping
        is the point: `RegisterUserCommand` is an ADR-020 frozen dataclass, and
        `.importlinter` deliberately leaves Pydantic off the application
        layer's forbidden list *as a convention rather than a gate*. Forwarding
        the wrapper would therefore break nothing - no contract, no type check,
        no test but the one that watches this - it would just silently put a
        validation library's type in a layer that names none.

        There is no `actor_id` to bind: this is the operation that creates an
        identity, so there is no authenticated caller and the route takes none.
        """
        return RegisterUserCommand(
            email=self.email,
            full_name=self.full_name,
            password=self.password.get_secret_value(),
        )


class UserResponse(BaseModel):
    """The profile, on register and on `GET /auth/me` alike (D-09, AUTH-05).

    Four members, and the interesting one is the fifth this class does not
    have: `User` stores a `password_hash`, `UserResult` already refuses to
    carry it, and the field-by-field copy below is what guarantees a later
    result field cannot arrive here by default. Declaration order is
    serialisation order, so the list is the contract - which is why the test
    asserts the whole member list rather than the absence of one name: a
    renamed hash field would pass a per-key check and fail this one (T-5-08).
    """

    id: UUID
    email: str
    full_name: str
    created_at: datetime

    @classmethod
    def from_result(cls, result: UserResult) -> "UserResponse":
        """Copy every field of the result, naming each one explicitly."""
        return cls(
            id=result.id,
            email=result.email,
            full_name=result.full_name,
            created_at=result.created_at,
        )


class TokenResponse(BaseModel):
    """`POST /auth/login`'s answer: the token and how to use it (AUTH-02).

    The three members are `AccessTokenResult`'s, in its order, and the two
    beside the token are wire-format obligations the result DTO argues in full:
    `token_type` carries the lowercase `bearer` that Swagger's Authorize button
    concatenates, and `expires_in` is a number of **seconds**.
    """

    access_token: str
    token_type: str
    expires_in: int

    @classmethod
    def from_result(cls, result: AccessTokenResult) -> "TokenResponse":
        """Copy every field of the result, naming each one explicitly."""
        return cls(
            access_token=result.access_token,
            token_type=result.token_type,
            expires_in=result.expires_in,
        )
