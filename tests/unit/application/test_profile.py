"""AUTH-05 against the fakes: the caller's own profile, and nothing else's.

`GetProfile` exists beside `AuthenticateActor` rather than inside it, and the
two tests here are what that decision costs and buys. ADR-044 fixes the actor
seam's type as a `UUID`, so a route that wants the profile asks for it in one
more call - which is why `GET /auth/me` issues two `SELECT`s rather than one.
Folding the profile into the actor dependency would save the second read and
change the type every router signature in the project is written against.

The command carries one field and it is the actor, so there is no identifier a
request could substitute: the not-found leg below is reachable only by an
account deleted between the actor lookup and this one.
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from taskmanager.application.dto.commands import GetProfileCommand
from taskmanager.application.dto.results import UserResult
from taskmanager.application.use_cases.auth.profile import GetProfile
from taskmanager.domain.entities.user import User
from taskmanager.domain.exceptions import UserNotFoundError
from tests.unit.application.fakes import FakeUnitOfWork, FakeUserRepository

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
ACTOR_ID = UUID("11111111-1111-4111-8111-111111111111")
UNKNOWN_USER_ID = UUID("99999999-9999-4999-8999-999999999999")

EMAIL = "ana@example.com"
FULL_NAME = "Ana Torres"
PASSWORD_HASH = "fake-hash:a-long-enough-password"


def _uow(*, registered: bool = True) -> FakeUnitOfWork:
    """A unit of work holding the actor's account, or holding nothing."""
    users = FakeUserRepository()
    if registered:
        user = User.create(
            user_id=ACTOR_ID,
            email=EMAIL,
            full_name=FULL_NAME,
            password_hash=PASSWORD_HASH,
            now=NOW,
        )
        users.stored[user.id] = user
    return FakeUnitOfWork(users=users)


async def test_the_profile_is_the_four_public_fields_and_no_transaction() -> None:
    """D-09's profile shape, read without writing anything.

    `commits == 0` alone would be equally true of a transaction nobody closed,
    so the rollback is asserted beside it - the inverse of the write-path
    convention, exactly as `use_cases/task_lists/get.py`'s suite does it.
    """
    unit_of_work = _uow()
    use_case = GetProfile(unit_of_work)

    result = await use_case.execute(GetProfileCommand(actor_id=ACTOR_ID))

    assert result.id == ACTOR_ID
    assert result.email == EMAIL
    assert result.full_name == FULL_NAME
    assert result.created_at == NOW
    assert unit_of_work.commits == 0
    assert unit_of_work.rollbacks == 1


async def test_an_actor_whose_account_is_gone_is_a_not_found() -> None:
    """A 404, not a 401: the token was fine, the row is what is missing.

    Reachable only in the window between the actor lookup and this one, since
    the command has no identifier a caller could supply - which is why the
    error names the id it was given rather than concealing it.
    """
    unit_of_work = _uow(registered=False)
    use_case = GetProfile(unit_of_work)

    with pytest.raises(UserNotFoundError) as excinfo:
        await use_case.execute(GetProfileCommand(actor_id=UNKNOWN_USER_ID))

    assert excinfo.value.details == {"user_id": str(UNKNOWN_USER_ID)}
    assert unit_of_work.commits == 0
    assert unit_of_work.rollbacks == 1


async def test_the_profile_carries_no_field_a_hash_could_travel_in() -> None:
    """T-5-04 at the use-case boundary, not only at the DTO's.

    `test_dtos.py` proves `UserResult` has no such field; this proves the use
    case answers with that type rather than with the entity it just read, so a
    later "just return the user" simplification fails here.

    The type is asserted with `type(...) is`, never `not isinstance(..., User)`:
    mypy's `warn_unreachable` proves the two classes can share no subclass, so
    the negative form is dead code and fails `make typecheck` (the 03-07 call).
    """
    unit_of_work = _uow()
    use_case = GetProfile(unit_of_work)

    result = await use_case.execute(GetProfileCommand(actor_id=ACTOR_ID))

    assert not hasattr(result, "password_hash")
    assert type(result) is UserResult
