"""Read the caller's own profile (AUTH-05).

**Why this exists beside `AuthenticateActor` rather than inside it.** That use
case already loads the row, so a route needing the profile could have it for
free if the actor seam handed back a `User` instead of a `UUID`. ADR-044 fixes
the seam's type as a `UUID`, and changing it would change the signature of
every router function in the project - eleven routes that want an identifier
and nothing else would start receiving an entity, and the temptation to read
one more field off it would arrive with them. So the type stays, and a route
that wants the profile asks for it.

The cost is named rather than hidden: `GET /api/v1/auth/me` issues **two**
`SELECT`s against the users table, the actor lookup D-11 requires and this one.
That is one avoidable statement on one endpoint, traded for an unchanged seam
type across the whole presentation layer.

There is no clock and nothing is made durable, for the reasons
`use_cases/task_lists/get.py` gives: this operation stamps nothing, and a
transaction that wrote nothing has nothing to commit.

The command carries one field and it is the actor, so there is no identifier a
request could substitute - `/auth/me` cannot be aimed at somebody else's
account. The not-found leg is therefore reachable only by an account deleted
between the actor lookup and this read, which is why it answers with the
ordinary `UserNotFoundError` rather than with the generic 401: the token was
fine, and the caller already knows their own id.
"""

from taskmanager.application.dto.commands import GetProfileCommand
from taskmanager.application.dto.results import UserResult
from taskmanager.application.ports.unit_of_work import UnitOfWork
from taskmanager.domain.exceptions import UserNotFoundError


class GetProfile:
    """Reads the authenticated caller's own account (AUTH-05)."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, command: GetProfileCommand) -> UserResult:
        """Return the caller's profile, or raise the not-found that explains."""
        async with self._uow:
            user = await self._uow.users.get(command.actor_id)
            if user is None:
                raise UserNotFoundError(command.actor_id)
        # Mapped outside the block, like every sibling in this package.
        return UserResult.from_entity(user)
