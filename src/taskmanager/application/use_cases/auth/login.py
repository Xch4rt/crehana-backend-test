"""Exchange a credential for an access token, or refuse without saying why.

**One refusal, constructed in one place.** The two failing legs - no account
with that address, and an account whose stored hash does not match - raise the
same class with the same message, and the message is the module constant below
rather than a string typed twice. That constant *is* the mechanism D-12 rests
on. Two `raise` statements carrying two hand-written strings agree right up
until somebody edits one of them, and the comparative test in
`test_login.py` would then be the only thing standing between this project and
an account-enumeration oracle. With one constant there is nothing to drift.

**The unknown-address leg does work it throws away.** Identical bodies are not
enough. An account that exists costs Argon2id - measured at 23.6 ms in
`05-RESEARCH.md` - while a lookup that found nothing has no stored hash to
compare against and would return in microseconds, so the two answers would be
distinguishable on a stopwatch even while being identical on the wire. The
`PasswordHasher` port therefore offers a throwaway-hash comparison (D-21,
measured at 23.4 ms), and this use case asks for it on the leg that has
nothing of its own to check. The application layer cannot produce that hash
itself: making one needs `pwdlib`, which `.importlinter` forbids here, which is
the same reason hashing is a port at all. The port's docstring argues the three
rejected alternatives in full.

**Nothing is committed and nothing is held.** The lookup is a read, so there is
nothing to make durable and `__aexit__` closing the transaction is the port's
documented obligation - the argument `use_cases/task_lists/list.py` makes. The
block is also *left* before any hashing happens: a connection held across 23 ms
of arithmetic is a pool slot spent for nothing, on the one unauthenticated
endpoint an attacker can call as often as they like.

**An address the database cannot hold is an address no account has.** The form
behind this use case has no schema - OAuth2 fixes its shape - so a `username`
containing a NUL or an unpaired surrogate used to reach psycopg, which refused
the statement: an unauthenticated 500 any fuzzer finds in seconds, with the
submitted address echoed into the log through the driver's message (Phase 5
review WR-01). It is refused here instead, on the same terms and at the same
cost as an address that merely does not exist - the same throwaway hashing, the
same one refusal - and before the transaction, so no connection is taken out
for a lookup that cannot succeed. The question is the domain's
`is_storable_text`, the same predicate the entity guards ask, rather than a
character test written a second time here.

**On the field name.** OAuth2 fixes the login form's field to `username`, and
this API's usernames are email addresses. The rename happens once, in the
schema that reads the form (plan 05-11); everything from `LoginCommand` inward
says `email`, so nobody reading this file has to hold the translation in their
head. The route description says the same thing to a human reading the docs.

**What this endpoint does not do.** There is no rate limiting and no lockout;
T-5-08 is accepted rather than mitigated, and Argon2's ~25 ms floor is an
incidental throttle, not a control. It belongs in the README's future-work
list, which Phase 7 owns.
"""

from typing import Final

from taskmanager.application.dto.commands import LoginCommand
from taskmanager.application.dto.results import AccessTokenResult
from taskmanager.application.ports.security import PasswordHasher, TokenService
from taskmanager.application.ports.unit_of_work import UnitOfWork
from taskmanager.domain.exceptions import AuthenticationError
from taskmanager.domain.validation import is_storable_text

# The one message both refusals carry. See the module docstring: this being a
# single object, referenced twice, is what makes the two legs identical by
# construction rather than by two people typing carefully.
_REFUSAL: Final[str] = "Incorrect email or password."

# Lowercase, because Swagger's Authorize button and a good many clients build
# the Authorization header by concatenating this value with the token.
_TOKEN_TYPE: Final[str] = "bearer"

# `expires_in` is published in seconds while the setting is in minutes.
_SECONDS_PER_MINUTE: Final[int] = 60


class Login:
    """Authenticates a credential and issues an access token (AUTH-02)."""

    def __init__(
        self,
        uow: UnitOfWork,
        hasher: PasswordHasher,
        tokens: TokenService,
        expire_minutes: int,
    ) -> None:
        # The unit of work first, then the non-transactional ports (D-17). The
        # lifetime arrives as a plain integer rather than as a settings object:
        # this layer reads no configuration, and the composition root already
        # holds the one `jwt_expire_minutes` value the token service is built
        # with, so both sides of the answer come from the same number.
        self._uow = uow
        self._hasher = hasher
        self._tokens = tokens
        self._expire_minutes = expire_minutes

    async def execute(self, command: LoginCommand) -> AccessTokenResult:
        """Return a token, or raise the one refusal that covers both failures."""
        if not is_storable_text(command.email):
            # No row can hold this address, so no row can match it: the same
            # answer the unknown-address leg gives, paid for with the same
            # throwaway work and built from the same constant. Before the
            # block, so the driver never sees the value (WR-01).
            await self._hasher.dummy_verify(command.password)
            raise AuthenticationError(_REFUSAL)
        async with self._uow:
            # The adapter folds case on both sides, so the address is found
            # however it was typed (D-10) - the same question registration's
            # pre-check asks.
            user = await self._uow.users.get_by_email(command.email)
        if user is None:
            # No stored hash to compare against, so the equivalent work is
            # requested from the port instead. Its result is not read because
            # there is none: the method returns nothing on purpose, so this
            # line cannot be mistaken for a check that passed.
            await self._hasher.dummy_verify(command.password)
            raise AuthenticationError(_REFUSAL)
        if not await self._hasher.verify(command.password, user.password_hash):
            raise AuthenticationError(_REFUSAL)
        return AccessTokenResult(
            access_token=await self._tokens.issue_access_token(user.id),
            token_type=_TOKEN_TYPE,
            expires_in=self._expire_minutes * _SECONDS_PER_MINUTE,
        )
