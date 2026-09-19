"""D-11 against the fakes: a token becomes an actor, or it becomes one 401.

The decision this module exists to pin is the *second* lookup. A token that
decodes carries a subject, and an implementation could stop there - the
signature is valid, so the caller is who they say they are. D-11 says no: the
row is confirmed on every request, which is what makes a deleted user's still
valid token a 401 from the very next call rather than a live session nobody can
revoke (T-5-15). The cost is one indexed `SELECT` per authenticated request,
and plan 05-13 re-measures it; the test below asserts the read happened at all,
because a value assertion alone passes against an implementation that trusted
the claim.

The two refusals are produced from one fixture and compared field by field.
Asserting `pytest.raises(AuthenticationError)` twice would pass just as happily
against an implementation whose two messages differ - and a caller who can tell
"this token is junk" from "this token's owner is gone" can enumerate deleted
accounts, which is the same leak in a different coat.

Nothing here is made durable: the transaction read one row, so `commits == 0`
and `rollbacks == 1` on the success path, for the reason
`use_cases/task_lists/list.py` states.
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from taskmanager.application.dto.commands import AuthenticateActorCommand
from taskmanager.application.use_cases.auth.authenticate import AuthenticateActor
from taskmanager.domain.entities.user import User
from taskmanager.domain.exceptions import AuthenticationError
from tests.unit.application.fakes import (
    FakeTokenService,
    FakeUnitOfWork,
    FakeUserRepository,
)

pytestmark = pytest.mark.unit

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
ACTOR_ID = UUID("11111111-1111-4111-8111-111111111111")
DELETED_USER_ID = UUID("99999999-9999-4999-8999-999999999999")

EMAIL = "ana@example.com"
FULL_NAME = "Ana Torres"
PASSWORD_HASH = "fake-hash:a-long-enough-password"


class _RefusingTokenService(FakeTokenService):
    """A token service that refuses everything, exactly as the adapter does.

    `JwtTokenService.decode` answers a malformed, expired, wrongly signed or
    unsigned token with one `AuthenticationError` and no details
    (`tests/unit/infrastructure/test_tokens.py`), so that is the contract this
    double honours. `FakeTokenService` itself would raise `ValueError` from
    `UUID(...)`, which is the fake's own accident rather than the port's stated
    behaviour, and a use case built against it would be built against the wrong
    contract.
    """

    async def decode(self, token: str) -> UUID:
        raise AuthenticationError()


class _CountingUserRepository(FakeUserRepository):
    """Records every identifier looked up, so D-11's extra read is observable."""

    def __init__(self) -> None:
        super().__init__()
        self.reads: list[UUID] = []

    async def get(self, user_id: UUID) -> User | None:
        self.reads.append(user_id)
        return await super().get(user_id)


def _user(user_id: UUID = ACTOR_ID) -> User:
    """The account a valid token points at."""
    return User.create(
        user_id=user_id,
        email=EMAIL,
        full_name=FULL_NAME,
        password_hash=PASSWORD_HASH,
        now=NOW,
    )


def _uow(*, registered: bool = True) -> FakeUnitOfWork:
    """A unit of work over a counting user repository, optionally populated."""
    users = _CountingUserRepository()
    if registered:
        user = _user()
        users.stored[user.id] = user
    return FakeUnitOfWork(users=users)


async def test_a_valid_token_resolves_to_the_profile_of_a_live_account() -> None:
    """The happy path, and the transaction it deliberately does not commit."""
    unit_of_work = _uow()
    use_case = AuthenticateActor(unit_of_work, FakeTokenService())

    result = await use_case.execute(AuthenticateActorCommand(token=str(ACTOR_ID)))

    assert result.id == ACTOR_ID
    assert result.email == EMAIL
    assert result.full_name == FULL_NAME
    assert result.created_at == NOW
    assert unit_of_work.commits == 0
    assert unit_of_work.rollbacks == 1


async def test_the_user_row_is_confirmed_on_every_call() -> None:
    """D-11, asserted as a read rather than as a returned value.

    Two calls, two lookups: an implementation that cached the subject, or that
    trusted the signature and built the result from the claim, would answer
    correctly and leave this list short.
    """
    unit_of_work = _uow()
    users = unit_of_work.user_repository
    assert isinstance(users, _CountingUserRepository)
    use_case = AuthenticateActor(unit_of_work, FakeTokenService())

    await use_case.execute(AuthenticateActorCommand(token=str(ACTOR_ID)))
    await use_case.execute(AuthenticateActorCommand(token=str(ACTOR_ID)))

    assert users.reads == [ACTOR_ID, ACTOR_ID]


async def test_a_token_the_port_refuses_is_an_authentication_failure() -> None:
    """The adapter's refusal travels out unchanged; nothing is re-wrapped."""
    unit_of_work = _uow()
    use_case = AuthenticateActor(unit_of_work, _RefusingTokenService())

    with pytest.raises(AuthenticationError):
        await use_case.execute(AuthenticateActorCommand(token="not.a.token"))

    assert unit_of_work.commits == 0


async def test_a_token_whose_subject_has_no_row_is_refused() -> None:
    """T-5-15: the deleted account's live token stops working immediately."""
    unit_of_work = _uow(registered=False)
    use_case = AuthenticateActor(unit_of_work, FakeTokenService())

    with pytest.raises(AuthenticationError):
        await use_case.execute(AuthenticateActorCommand(token=str(DELETED_USER_ID)))

    assert unit_of_work.commits == 0
    assert unit_of_work.rollbacks == 1


async def test_the_two_refusals_are_indistinguishable() -> None:
    """D-11's single generic 401: same class, same code, same message, same body.

    Produced here from two fixtures that differ only in *why* they fail, and
    compared on every field a client can see. A caller able to tell the two
    apart could ask "does this subject still exist?" about any token they ever
    held.
    """
    with pytest.raises(AuthenticationError) as bad_token:
        await AuthenticateActor(_uow(), _RefusingTokenService()).execute(
            AuthenticateActorCommand(token="not.a.token")
        )
    with pytest.raises(AuthenticationError) as gone_subject:
        await AuthenticateActor(_uow(registered=False), FakeTokenService()).execute(
            AuthenticateActorCommand(token=str(DELETED_USER_ID))
        )

    assert type(bad_token.value) is type(gone_subject.value)
    assert bad_token.value.code == gone_subject.value.code
    assert str(bad_token.value) == str(gone_subject.value)
    assert bad_token.value.details == gone_subject.value.details
    # And neither of them repeats the token or the identifier back.
    assert str(DELETED_USER_ID) not in str(gone_subject.value)
    assert gone_subject.value.details == {}
