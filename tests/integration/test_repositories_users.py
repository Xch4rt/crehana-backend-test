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
from taskmanager.domain.exceptions import EmailAlreadyRegisteredError, ValidationError
from taskmanager.infrastructure.db.constraints import UQ_USERS_EMAIL_LOWER
from taskmanager.infrastructure.db.models import UserRow
from taskmanager.infrastructure.db.repositories.users import SqlAlchemyUserRepository

pytestmark = pytest.mark.integration

# Fixed identifiers and instants, for the reason given in the task-list suite.
USER_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")
OTHER_USER_ID = uuid.UUID("00000000-0000-4000-8000-000000000002")
MISSING_USER_ID = uuid.UUID("00000000-0000-4000-8000-0000000000ff")
# Three accounts for the ordering test, named for their expected places rather
# than for the order they are written in: the two tied ids differ only in their
# last digit, which is what the `id` tie-break has to notice.
OLDEST_USER_ID = uuid.UUID("00000000-0000-4000-8000-00000000000a")
TIED_LOWER_USER_ID = uuid.UUID("00000000-0000-4000-8000-00000000000b")
TIED_HIGHER_USER_ID = uuid.UUID("00000000-0000-4000-8000-00000000000c")

NOW = datetime(2026, 3, 14, 15, 9, 26, 535897, tzinfo=UTC)
EARLIER = datetime(2026, 3, 13, 9, 0, 0, tzinfo=UTC)

PASSWORD_HASH = "argon2-placeholder-hash-value"
EMAIL = "owner@example.test"
OTHER_EMAIL = "other@example.test"
THIRD_EMAIL = "third@example.test"
FULL_NAME = "Ada Lovelace"


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
    full_name: str = FULL_NAME,
    created_at: datetime = NOW,
) -> User:
    """A valid user entity, differing from the default only where asked."""
    return User(
        id=user_id,
        email=email,
        full_name=full_name,
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
            full_name=FULL_NAME,
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
            full_name=FULL_NAME,
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
                    full_name=FULL_NAME,
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


async def test_a_full_name_round_trips_through_both_read_paths(
    session: AsyncSession,
) -> None:
    """AUTH-01: the stored name is the trimmed one, read back from the server.

    Asserted through `get` and through `get_by_email` rather than off the
    entity `add()` was handed: the entity trims in `__post_init__`, so checking
    the object that went in would pass against a column that was never written
    and against a mapper that silently dropped the field. Both read paths are
    exercised because each builds its own entity out of its own row.
    """
    repository = SqlAlchemyUserRepository(session)

    await repository.add(a_user(full_name="  Ada  Lovelace  "))

    by_id = await repository.get(USER_ID)
    by_email = await repository.get_by_email(EMAIL)

    assert by_id is not None
    assert by_email is not None
    assert by_id.full_name == "Ada  Lovelace"
    assert by_email.full_name == "Ada  Lovelace"


async def test_an_over_length_full_name_never_reaches_the_database(
    session: AsyncSession,
) -> None:
    """The entity is the gate and `VARCHAR(100)` is only the backstop (T-5-13).

    A 101-character name raises before a repository is even asked, so no
    statement is issued and no savepoint is needed - which is the whole
    difference between a value refused by this application and a value refused
    by PostgreSQL. The database would truncate nothing and raise a
    `StringDataRightTruncation` that reaches a client as the fixed 500; the
    entity answers a 422 naming the field instead.
    """
    with pytest.raises(ValidationError) as raised:
        a_user(full_name="x" * (User.FULL_NAME_MAX_LENGTH + 1))

    assert raised.value.details == {"field": "full_name"}


async def test_list_all_orders_three_users_by_created_at_then_id(
    session: AsyncSession,
) -> None:
    """The adapter-side counterpart of 05-02's fake fix (D-25, ASGN-03).

    Three accounts, two of them sharing an instant to the microsecond, written
    in an order that disagrees with the expected answer on both axes - so
    neither insertion order nor a sort on `created_at` alone can produce it.
    The two-row tests above and below each pin one axis; only three rows with a
    tie in the middle pin the composite, and the user directory ASGN-03 serves
    is paged off exactly this order.
    """
    repository = SqlAlchemyUserRepository(session)
    await repository.add(a_user(user_id=TIED_HIGHER_USER_ID, email=EMAIL))
    await repository.add(
        a_user(user_id=OLDEST_USER_ID, email=OTHER_EMAIL, created_at=EARLIER)
    )
    await repository.add(a_user(user_id=TIED_LOWER_USER_ID, email=THIRD_EMAIL))

    stored = await repository.list_all()

    assert [user.id for user in stored] == [
        OLDEST_USER_ID,
        TIED_LOWER_USER_ID,
        TIED_HIGHER_USER_ID,
    ]


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
