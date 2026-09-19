"""The user adapter against a real server: the index, and the silent conflict.

Two things here are worth more than the CRUD coverage.

The lookup is asserted against a row this application did not write. `User`
lowercases every address it constructs, so a repository that compared the raw
argument would pass a test whose fixtures all went through the entity - and miss
the row a migration, a seed script or an operator inserted. Folding both sides is
also what lets PostgreSQL use the `uq_users_email_lower` expression index rather
than scanning.

The conflict is asserted to say nothing. `EmailAlreadyRegisteredError` takes no
argument by design, and `test_the_conflict_error_does_not_echo_the_address`
checks the consequence rather than the intent: neither the address nor the
constraint name appears in the message or the details, so AUTH-01's 409 concedes
that an account exists and not one character more (T-3-13).
"""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, AsyncSessionTransaction

from taskmanager.domain.entities.user import User
from taskmanager.domain.exceptions import EmailAlreadyRegisteredError
from taskmanager.infrastructure.db.constraints import UQ_USERS_EMAIL_LOWER
from taskmanager.infrastructure.db.models import UserRow
from taskmanager.infrastructure.db.repositories.users import SqlAlchemyUserRepository

pytestmark = pytest.mark.integration

# Fixed identifiers and instants, for the reason given in the task-list suite.
USER_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")
OTHER_USER_ID = uuid.UUID("00000000-0000-4000-8000-000000000002")
MISSING_USER_ID = uuid.UUID("00000000-0000-4000-8000-0000000000ff")

NOW = datetime(2026, 3, 14, 15, 9, 26, 535897, tzinfo=UTC)
EARLIER = datetime(2026, 3, 13, 9, 0, 0, tzinfo=UTC)

PASSWORD_HASH = "argon2-placeholder-hash-value"
EMAIL = "owner@example.test"
OTHER_EMAIL = "other@example.test"


def refused(session: AsyncSession) -> AsyncSessionTransaction:
    """A savepoint around work PostgreSQL is expected to reject.

    Same helper, same reason as in `test_repositories_task_lists.py`: a refused
    statement aborts the transaction the `connection` fixture owns, and the
    savepoint is what lets the rollback stop short of it.
    """
    return session.begin_nested()


def a_user(
    *,
    user_id: uuid.UUID = USER_ID,
    email: str = EMAIL,
    created_at: datetime = NOW,
) -> User:
    """A valid user entity, differing from the default only where asked."""
    return User(
        id=user_id,
        email=email,
        password_hash=PASSWORD_HASH,
        created_at=created_at,
        updated_at=created_at,
    )


async def test_a_stored_user_comes_back_as_a_domain_entity(
    session: AsyncSession,
) -> None:
    """What goes in as an entity comes back as one, never as a row (DB-03)."""
    repository = SqlAlchemyUserRepository(session)

    await repository.add(a_user())
    fetched = await repository.get(USER_ID)

    assert isinstance(fetched, User)
    assert not isinstance(fetched, UserRow)
    assert fetched.email == EMAIL
    assert fetched.password_hash == PASSWORD_HASH
    assert await repository.get(MISSING_USER_ID) is None


async def test_get_by_email_ignores_case_and_surrounding_whitespace(
    session: AsyncSession,
) -> None:
    """The lookup folds both sides, so a row the entity did not write is found.

    The row below is put in with its capitals intact, bypassing `User` exactly
    the way a seed script or a migration would. An adapter that compared the
    stored value directly would answer `None` here and let a second account be
    created for an address that already has one.
    """
    session.add(
        UserRow(
            id=USER_ID,
            email="Owner@Example.Test",
            password_hash=PASSWORD_HASH,
            created_at=NOW,
            updated_at=NOW,
        )
    )
    await session.flush()
    repository = SqlAlchemyUserRepository(session)

    found = await repository.get_by_email("  OWNER@EXAMPLE.TEST  ")

    assert found is not None
    assert found.id == USER_ID
    # The entity canonicalises on the way out, whatever the column held.
    assert found.email == EMAIL


async def test_get_by_email_returns_none_for_an_unknown_address(
    session: AsyncSession,
) -> None:
    """An address nobody registered is `None`, not an empty-ish user."""
    repository = SqlAlchemyUserRepository(session)
    await repository.add(a_user())

    assert await repository.get_by_email("nobody@example.test") is None


async def test_a_duplicate_email_raises_the_registration_conflict(
    session: AsyncSession,
) -> None:
    """D-13: `uq_users_email_lower` becomes AUTH-01's 409, not a 500."""
    repository = SqlAlchemyUserRepository(session)
    await repository.add(a_user())

    with pytest.raises(EmailAlreadyRegisteredError):
        async with refused(session):
            await repository.add(a_user(user_id=OTHER_USER_ID))


async def test_a_duplicate_email_differing_only_in_case_raises_the_same_error(
    session: AsyncSession,
) -> None:
    """The expression index is what catches this one, and it must.

    `User` lowercases on construction, so this pair would collide even under a
    plain unique constraint - which is why the row below is written without the
    entity. It is the deliberate opposite of `uq_task_lists_owner_id_name`, where
    two names differing in case are two distinct lists (D-12).
    """
    session.add(
        UserRow(
            id=USER_ID,
            email="OWNER@EXAMPLE.TEST",
            password_hash=PASSWORD_HASH,
            created_at=NOW,
            updated_at=NOW,
        )
    )
    await session.flush()
    repository = SqlAlchemyUserRepository(session)

    with pytest.raises(EmailAlreadyRegisteredError):
        async with refused(session):
            await repository.add(a_user(user_id=OTHER_USER_ID))


async def test_the_conflict_error_does_not_echo_the_address(
    session: AsyncSession,
) -> None:
    """The account-enumeration property, asserted rather than assumed.

    A registration endpoint that repeats the submitted address in its 409 is a
    slightly better oracle than one that does not: the body can then be quoted
    verbatim into a log, a bug report or an error-tracking service. The caller
    already knows what they sent, so there is nothing to gain by saying it again.
    The constraint name is excluded for the separate reason that it is internal
    schema detail no client has any use for.
    """
    repository = SqlAlchemyUserRepository(session)
    await repository.add(a_user())

    with pytest.raises(EmailAlreadyRegisteredError) as raised:
        async with refused(session):
            await repository.add(a_user(user_id=OTHER_USER_ID))

    reported = f"{raised.value} {raised.value.details}"
    assert EMAIL not in reported
    assert "example.test" not in reported
    assert UQ_USERS_EMAIL_LOWER not in reported
    assert raised.value.details == {"field": "email"}


async def test_an_unrecognised_integrity_error_is_re_raised(
    session: AsyncSession,
) -> None:
    """What this adapter does not recognise, it does not translate.

    The row added inside the savepoint has no address at all, so the flush inside
    `add()` carries a violation with no branch here - and it must escape exactly
    as it arrived, to become the fixed 500 that says nothing (T-3-14). The bad row
    goes in *after* the savepoint opens, because opening one flushes whatever is
    already pending and the refusal would then happen before the repository ran.
    """
    repository = SqlAlchemyUserRepository(session)

    with pytest.raises(IntegrityError):
        async with refused(session):
            session.add(
                UserRow(
                    id=OTHER_USER_ID,
                    password_hash=PASSWORD_HASH,
                    created_at=NOW,
                    updated_at=NOW,
                )
            )
            await repository.add(a_user())


async def test_a_returned_user_is_readable_after_the_session_is_gone(
    session: AsyncSession,
) -> None:
    """Roadmap SC-2 for this aggregate: a dataclass outlives its session.

    Every field was copied out of the row while the session was open, so there is
    no instrumented attribute left to load and no SQL to emit from outside the
    greenlet context.
    """
    repository = SqlAlchemyUserRepository(session)
    await repository.add(a_user())
    fetched = await repository.get_by_email(EMAIL)
    assert fetched is not None

    await session.close()

    assert fetched.id == USER_ID
    assert fetched.email == EMAIL
    assert fetched.password_hash == PASSWORD_HASH
    assert fetched.created_at == NOW
    assert fetched.updated_at == NOW


async def test_list_all_returns_every_user_in_creation_order(
    session: AsyncSession,
) -> None:
    """Written newest first, so an absent ORDER BY would have to be lucky."""
    repository = SqlAlchemyUserRepository(session)
    await repository.add(a_user(email=EMAIL, created_at=NOW))
    await repository.add(
        a_user(user_id=OTHER_USER_ID, email=OTHER_EMAIL, created_at=EARLIER)
    )

    stored = await repository.list_all()

    assert [user.email for user in stored] == [OTHER_EMAIL, EMAIL]


async def test_list_all_breaks_a_tie_on_created_at_with_the_id(
    session: AsyncSession,
) -> None:
    """WR-03: `created_at` alone is not a total order, so `id` follows it.

    Two accounts written under one clock reading - a seed script, a fixture, a
    future bulk import - would otherwise be free to swap places between runs,
    and a first-element assertion above this repository would be flaky rather
    than wrong. They are inserted in descending id order, so returning them in
    insertion order fails here.
    """
    repository = SqlAlchemyUserRepository(session)
    await repository.add(
        a_user(user_id=OTHER_USER_ID, email=OTHER_EMAIL, created_at=NOW)
    )
    await repository.add(a_user(user_id=USER_ID, email=EMAIL, created_at=NOW))

    stored = await repository.list_all()

    assert [user.id for user in stored] == [USER_ID, OTHER_USER_ID]
