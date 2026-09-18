"""The `UserRepository` adapter, shaped exactly like its task-list sibling.

The same two alternatives are rejected here for the same two reasons: a
repository that made its own writes durable would take the transaction boundary
away from the use case that owns it (ARC-08, roadmap SC-4), and one that handed
back ORM rows would put a session-bound object in the application layer, where
reading an attribute after the session has gone raises from wherever the use
case happens to be standing.

One thing is specific to this aggregate. The conflict raised on a duplicate
address carries no address. That is a security property rather than an
oversight: registration already concedes *some* enumeration surface by answering
409 at all, and echoing the value back - into a response body, and from there
into whatever logs it - widens the surface for nothing. `User` canonicalises the
address on construction and `uq_users_email_lower` defends that rule at the
database, so the two agree on what "the same address" means; the error simply
does not repeat it.
"""

from collections.abc import Sequence
from typing import NoReturn
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from taskmanager.domain.entities.user import User
from taskmanager.domain.exceptions import EmailAlreadyRegisteredError
from taskmanager.infrastructure.db.constraints import UQ_USERS_EMAIL_LOWER
from taskmanager.infrastructure.db.errors import violated_constraint
from taskmanager.infrastructure.db.mappers import user_to_entity, user_to_row
from taskmanager.infrastructure.db.models import UserRow


class SqlAlchemyUserRepository:
    """`UserRepository` (D-19) over an `AsyncSession` it does not own."""

    def __init__(self, session: AsyncSession) -> None:
        # Borrowed, exactly as in `task_lists.py`: the unit of work decides when
        # this session's work becomes permanent, and this class never does.
        self._session = session

    async def get(self, user_id: UUID) -> User | None:
        """The user with this identifier as an entity, or `None`."""
        row = await self._session.get(UserRow, user_id)
        return None if row is None else user_to_entity(row)

    async def get_by_email(self, email: str) -> User | None:
        """The account registered under this address, however it was typed.

        The comparison folds case on *both* sides. Folding only the argument
        would be enough for every row this application wrote, because `User`
        lowercases on construction - and it would silently miss a row written by
        a fixture, a migration or an operator, which is precisely when a missed
        row turns into a duplicate account. `func.lower` is also what lets
        PostgreSQL answer from the `uq_users_email_lower` expression index
        instead of scanning the table.
        """
        statement = select(UserRow).where(
            func.lower(UserRow.email) == email.strip().lower()
        )
        row = await self._session.scalar(statement)
        return None if row is None else user_to_entity(row)

    async def add(self, user: User) -> None:
        """Insert the account, translating the one collision it can cause."""
        self._session.add(user_to_row(user))
        try:
            # The flush is what surfaces the violation here rather than at the
            # unit of work's boundary; see `task_lists.py` for the full argument.
            await self._session.flush()
        except IntegrityError as error:
            self._refused(error)

    async def list_all(self) -> Sequence[User]:
        """Every registered account, oldest first.

        The ordering is the same determinism argument `list_for_owner` makes: an
        unordered `SELECT` may come back in any order the server finds
        convenient, and an assertion about the first element of a response would
        then pass on one run and fail on the next.
        """
        rows = await self._session.scalars(select(UserRow).order_by(UserRow.created_at))
        return [user_to_entity(row) for row in rows]

    def _refused(self, error: IntegrityError) -> NoReturn:
        """Re-raise a refusal as the error it means, or exactly as it arrived.

        `EmailAlreadyRegisteredError` takes no argument, which is the whole point
        of it: there is nothing to pass, so no call site can leak the address by
        being helpful. An unrecognised constraint is re-raised untouched and
        becomes Phase 2's fixed 500, because `violated_constraint` returning
        `None` means *unknowable* rather than *no conflict* (T-3-14).
        """
        if violated_constraint(error) == UQ_USERS_EMAIL_LOWER:
            raise EmailAlreadyRegisteredError() from error
        raise error
