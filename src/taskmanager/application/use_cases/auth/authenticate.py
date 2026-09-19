"""Turn a bearer token into the caller it names, or into one 401 (D-11).

This runs on **every** authenticated request, so both of its decisions are
about what a request costs and what it discloses.

**The row is confirmed every time.** Decoding proves the token was issued by
this server and has not expired; it does not prove the account still exists. An
implementation that stopped at the signature would leave a deleted user's
unexpired token working until it aged out, with no way to revoke it short of
rotating the signing key for everybody (T-5-15). So the subject is looked up,
and a missing row is refused. The price is one extra indexed `SELECT` per
authenticated request - `GET /api/v1/task-lists` moves from one statement to
two - which plan 05-13 re-measures in `test_statements.py` rather than leaves
as an estimate. Invariance is the property that test holds; the number moving
is this decision being paid for in the open.

**The two refusals are one refusal.** A token the port will not decode and a
token whose subject has no row produce the same class, code, message and empty
details - because a caller who could tell them apart would have an oracle for
"has this account been deleted?" over any token they ever held. The message is
not written here and not written in the adapter either: it lives on
`AuthenticationError` itself, so there is no second string to drift (see that
class's docstring).

**Nothing is committed.** The transaction read one row and wrote nothing, and
`__aexit__` closing it is the obligation the `UnitOfWork` port states in
writing - the same argument `use_cases/task_lists/list.py` makes. The unit
tests assert `commits == 0` **and** `rollbacks == 1`, because the first alone
is equally true of a transaction nobody ever closed.

The decode happens before the block rather than inside it, for the reason
`register.py` keeps hashing outside one: a refused token must not have opened
a transaction at all, and verifying a signature needs nothing from the
database.
"""

from taskmanager.application.dto.commands import AuthenticateActorCommand
from taskmanager.application.dto.results import UserResult
from taskmanager.application.ports.security import TokenService
from taskmanager.application.ports.unit_of_work import UnitOfWork
from taskmanager.domain.exceptions import AuthenticationError


class AuthenticateActor:
    """Resolves a bearer token to the profile of a live account (D-11)."""

    def __init__(self, uow: UnitOfWork, tokens: TokenService) -> None:
        # No clock: nothing here is stamped, and expiry is the token service's
        # to judge, against its own reading. A `Clock` accepted and never read
        # would be a dependency this operation does not have (the argument
        # `use_cases/task_lists/get.py` makes about read use cases).
        self._uow = uow
        self._tokens = tokens

    async def execute(self, command: AuthenticateActorCommand) -> UserResult:
        """Return the caller's profile, or raise the one refusal."""
        # The port answers with the subject or raises; there is no `None` leg
        # to forget to check, which is why the port is declared that way.
        subject = await self._tokens.decode(command.token)
        async with self._uow:
            user = await self._uow.users.get(subject)
            if user is None:
                # Constructed with no argument, exactly as the token adapter
                # constructs it, so the two bodies cannot differ by a word.
                raise AuthenticationError()
        # Mapped outside the block, like every sibling: the profile is built
        # from a value already read, never from an entity a closed session
        # might try to refresh.
        return UserResult.from_entity(user)
