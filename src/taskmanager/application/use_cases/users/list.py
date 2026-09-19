"""Every account in the system, for any authenticated caller (ASGN-03, D-13).

**This is an email directory, and that is a deliberate trade-off rather than an
oversight.** Any authenticated user may call `GET /api/v1/users` and receive
every other user's address along with their name and identifier. There is no
scoping, and the honest reason is that there is nothing to scope by: a real
product would restrict this to a team, an organisation or a project membership,
and this brief declares no tenancy concept of any kind. ASGN-03 asks literally
for a list of users so that an assignment can name one, and the endpoint that
answers it is this one.

So the risk is accepted with its eyes open (threat T-5-06), and plan 05-16 owes
it an ADR. What the acceptance buys elsewhere is worth recording here too,
because it is the reason a *second* decision is safe: since every address is
already discoverable by any authenticated caller, the `user_not_found` 404 that
`PUT .../tasks/{id}/assignee` answers to a list owner naming a nonexistent user
discloses nothing that a single call to this endpoint would not have disclosed
anyway (D-08). Remove the directory and that 404 becomes a user-existence
oracle; keep it, and the oracle already exists by design.

The actor is carried in the command and is not used as a filter. That is the
whole of D-13: the field says the caller was authenticated, and every
authenticated caller gets the same answer. An implementation that quietly
scoped the result - to the caller's collaborators, say - would be inventing a
tenancy rule nobody decided, and would break the only route from which a client
can learn an `assignee_id`.

Nothing here is made durable, for the reason `task_lists/list.py` states: the
transaction wrote nothing, and `__aexit__` closing it is the port's documented
obligation. Nothing is held for update either - this is a read, and a read that
waited on a writer would be a regression
(`tests/unit/application/test_write_paths_hold_what_they_change.py`).

The answer is a plain `tuple` of `UserResult`, never a wrapper class and never
the entity: `UserResult` is the four-field public profile, so the stored Argon2
hash has no field to travel in (T-5-04). `tuple` and not `list`, because a
caller must not be able to edit an answer the transaction has already finished
producing.
"""

from taskmanager.application.dto.commands import ListUsersCommand
from taskmanager.application.dto.results import UserResult
from taskmanager.application.ports.unit_of_work import UnitOfWork


class ListUsers:
    """Reads the whole user directory for an authenticated actor (ASGN-03)."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, command: ListUsersCommand) -> tuple[UserResult, ...]:
        """Return every account in `(created_at, id)` order.

        `command` names the actor, and nothing is read off it: see the module
        docstring for why the directory is the same answer for everybody.
        """
        async with self._uow:
            # The ordering is the repository's (D-25): a total order belongs in
            # the statement's ORDER BY, where PostgreSQL can serve it, rather
            # than in a sort applied to rows already fetched.
            users = await self._uow.users.list_all()
        # Mapped outside the block, like every sibling in this package.
        return tuple(UserResult.from_entity(user) for user in users)
