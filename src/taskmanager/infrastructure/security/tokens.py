"""The runtime adapter for `TokenService`, over PyJWT.

`application/ports/security.py` states the contract - including why a token
that cannot be trusted leaves here as an exception rather than as a `None` a
caller might forget to check - and this module implements it under the four
conventions `infrastructure/clock.py` sets out: no base class and no ABC, the
port is referenced rather than restated, configuration arrives as constructor
arguments, and `Settings` is never read here. The composition root reads the
three JWT values once and passes them in.

Two decisions in `decode` are the security of the whole phase, and both are
about *not* trusting the token to describe how it should be checked.

The first is that the accepted signing algorithm is pinned from configuration
and never derived from the token's own header. RFC 8725 §2.1 requires exactly
this, and it is what turns two classic forgeries into refusals rather than
accepted tokens: an unsigned token whose header advertises `none`, and a token
signed with a public key that a verifier reading the header would happily check
symmetrically (T-5-01).

The second is the required-claims option. A token carrying nothing but a
subject would otherwise verify and never expire, so `sub`, `exp` and `iat` are
all demanded; requiring `iat` in particular is what makes a hand-forged minimal
token fail even when the forger has somehow obtained the key.

The `except` clause is deliberately narrow, in the voice of
`db/repositories/users.py::_refused`: translate the one failure this component
recognises, and let anything else through untouched so it becomes Phase 2's
fixed 500. `InvalidKeyError` is the failure that must stay outside. It is not a
subclass of the token-failure base this clause catches, and that is not an
accident of the library's hierarchy - it means the *server* is misconfigured,
not that the caller's token is bad. Reported as a 401 it would blame a caller
who did nothing wrong, and hide the one fault an operator has to see. Widening
the catch to the library's own base exception class would swallow it, so the
catch is not widened.
"""

from datetime import timedelta
from uuid import UUID

import jwt
from jwt.exceptions import InvalidTokenError

from taskmanager.application.ports.clock import Clock
from taskmanager.domain.exceptions import AuthenticationError

# Demanded of every token, before any of them is read.
_REQUIRED_CLAIMS = ["sub", "exp", "iat"]

# The refusal message used to be a private constant here. It moved onto
# `AuthenticationError` itself when plan 05-07 added the second component that
# refuses a token - `AuthenticateActor`, for a subject whose row is gone - and
# had to answer with a body indistinguishable from this one (D-11). Two
# constants in two layers agree only until somebody edits one; now neither
# spells the message at all.


class JwtTokenService:
    """`TokenService` (D-19) over PyJWT, signing with the configured algorithm.

    No tolerance is allowed on the expiry comparison, and the omission is
    deliberate rather than forgotten: this deliverable runs on one machine
    against one clock, so there is no skew to absorb, and a non-zero leeway
    would make the expired-token test depend on a tolerance instead of on a
    boundary. A deployment spanning hosts with drifting clocks is where that
    trade changes, and it is not this one.
    """

    def __init__(
        self, *, secret: str, algorithm: str, expire_minutes: int, clock: Clock
    ) -> None:
        self._secret = secret
        self._algorithm = algorithm
        self._lifetime = timedelta(minutes=expire_minutes)
        # The port, never `SystemClock`: `dependencies.py::get_clock` already
        # hands out the contract rather than the implementation, and a test
        # that needs an instant in the past passes a frozen one here.
        self._clock = clock

    async def issue_access_token(self, subject: UUID) -> str:
        """An access token naming this user, valid for the configured window."""
        issued_at = self._clock.now()
        return jwt.encode(
            {
                # `str(...)` is not cosmetic. PyJWT >= 2.10 raises on decode
                # when `sub` is not a string, so a `UUID` written straight into
                # the payload would produce a token this very adapter refuses.
                "sub": str(subject),
                "iat": issued_at,
                "exp": issued_at + self._lifetime,
            },
            self._secret,
            algorithm=self._algorithm,
        )

    async def decode(self, token: str) -> UUID:
        """The user this token names, or one indistinguishable refusal.

        Every rejected token - unsigned, foreign-signed, expired, missing a
        required claim, syntactically broken, or carrying a subject that is not
        a identifier this system could have issued - leaves here as the same
        exception with the same message and no details (D-11, T-5-04). The
        caller therefore has nothing to compare, so the endpoint above cannot
        become an oracle for which half of a credential was wrong.

        `UUID(...)` is called inside the `try` rather than guarded by an
        `isinstance` check. `jwt.decode` is typed as returning `dict[str, Any]`,
        so a defensive branch would be one no test could reach - and the
        exception it would avoid, a `ValueError` or a `TypeError`, is already
        part of the net below and is exactly how a well-formed token carrying a
        non-identifier subject is refused.
        """
        try:
            payload = jwt.decode(
                token,
                self._secret,
                algorithms=[self._algorithm],
                options={"require": _REQUIRED_CLAIMS},
            )
            return UUID(payload["sub"])
        except (InvalidTokenError, ValueError, TypeError) as error:
            raise AuthenticationError() from error
