"""AUTH-01 against the fakes: an account is created, or the 409 that refuses it.

Four properties are pinned here, and each is a decision the rest of the phase
reads off this use case rather than re-deciding at the route.

*The transaction*: a success adds exactly one entity and leaves `commits == 1`
with `rollbacks == 0`; every refusal adds nothing and leaves the mirror image.
The rollback half only measures anything because `FakeUnitOfWork.__aexit__`
honours the obligation the port states.

*The policy runs before the work*: a password outside D-10's 8..128 bounds is
refused with the hasher untouched, asserted on `FakePasswordHasher.hashed`
rather than on a stopwatch (T-5-07).

*Both duplicate roads*: the pre-check the use case makes, and the refusal the
repository itself raises when the pre-check saw nothing. CLAUDE.md requires the
adapter to translate an `IntegrityError` into the error the pre-check would
have raised, so the race backstop is a road a test has to drive down - here by
a repository whose lookup answers `None` however many rows it holds.

*The address never travels*: the raised error carries no email in its message
and none in its details (T-5-06 is accepted as an oracle only as far as the
status code, D-23).
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from taskmanager.application.dto.commands import RegisterUserCommand
from taskmanager.application.use_cases.auth.register import RegisterUser
from taskmanager.domain.entities.user import User
from taskmanager.domain.exceptions import EmailAlreadyRegisteredError, ValidationError
from taskmanager.domain.validation import PASSWORD_MAX_LENGTH, PASSWORD_MIN_LENGTH
from tests.unit.application.fakes import (
    FakePasswordHasher,
    FakeUnitOfWork,
    FakeUserRepository,
    FrozenClock,
)

# Fixed on purpose, for the reason `test_create_task_list.py` gives: a generated
# identifier or a real clock reading would leave the assertions unable to say
# what they expect.
NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
LATER = NOW + timedelta(hours=3)
EXISTING_USER_ID = UUID("11111111-1111-4111-8111-111111111111")

EMAIL = "ana@example.com"
FULL_NAME = "Ana Torres"
PASSWORD = "a-long-enough-password"


class _BlindUserRepository(FakeUserRepository):
    """A repository whose lookup never finds anything, so `add` has to refuse.

    This is the race CLAUDE.md's persistence rule describes: two requests both
    pass the pre-check and only one passes `uq_users_email_lower`, so the
    adapter's `IntegrityError` translation is the second half of the refusal
    and not a belt-and-braces duplicate of the first. A test cannot produce two
    concurrent transactions against a dictionary; it can produce the state they
    produce, which is a lookup that saw nothing and an insert that collides.
    """

    async def get_by_email(self, email: str) -> User | None:
        return None


def _existing_user(email: str = EMAIL) -> User:
    """One account already registered, stamped at the earlier instant."""
    return User.create(
        user_id=EXISTING_USER_ID,
        email=email,
        full_name="Ana Somebody Else",
        password_hash="fake-hash:whatever-they-chose",
        now=NOW,
    )


def _uow(
    *,
    registered: str | None = None,
    blind: bool = False,
) -> FakeUnitOfWork:
    """Assemble a unit of work, optionally already holding one account.

    The entity is placed in `stored` directly rather than through `add()`, so
    the `added` record stays empty and every entry a test finds in it was
    written by the use case.
    """
    users = _BlindUserRepository() if blind else FakeUserRepository()
    if registered is not None:
        user = _existing_user(registered)
        users.stored[user.id] = user
    return FakeUnitOfWork(users=users)


def _command(
    *,
    email: str = EMAIL,
    full_name: str = FULL_NAME,
    password: str = PASSWORD,
) -> RegisterUserCommand:
    """The single construction site every test below goes through."""
    return RegisterUserCommand(email=email, full_name=full_name, password=password)


async def test_register_returns_the_canonical_profile_and_the_clock_instant() -> None:
    """The happy path: trimmed, lower-cased, stamped, and identified here.

    The address arrives with capitals and surrounding space and comes back
    canonical, because `User.__post_init__` owns that rule (D-10) and the
    result is built from the entity rather than from the command.
    """
    unit_of_work = _uow()
    use_case = RegisterUser(unit_of_work, FakePasswordHasher(), FrozenClock(LATER))

    result = await use_case.execute(
        _command(email="  Ana@Example.COM ", full_name="  Ana Torres ")
    )

    assert result.email == EMAIL
    assert result.full_name == FULL_NAME
    assert result.created_at == LATER
    assert result.id != EXISTING_USER_ID
    assert unit_of_work.commits == 1
    assert unit_of_work.rollbacks == 0


async def test_register_adds_the_account_once_and_stores_only_the_hash() -> None:
    """AUTH-01 and T-5-04: what is stored is the hasher's output, never the word.

    `added` rather than `stored`, for the reason `test_create_task_list.py`
    gives: a use case that saved twice leaves the same final state behind and
    is caught only by the count.
    """
    unit_of_work = _uow()
    hasher = FakePasswordHasher()
    use_case = RegisterUser(unit_of_work, hasher, FrozenClock(LATER))

    result = await use_case.execute(_command())

    assert len(unit_of_work.user_repository.added) == 1
    stored = unit_of_work.user_repository.added[0]
    assert stored.id == result.id
    # The port was asked exactly once, and what was stored is what it answered.
    # The fake's hash is a reversible prefix, so "the plaintext is absent from
    # the stored string" is not a claim this suite can make - what it can say
    # is that the stored value came from the port and never from the command's
    # own field, which is the property the port exists to enforce.
    assert hasher.hashed == [PASSWORD]
    assert stored.password_hash == f"{hasher.PREFIX}{PASSWORD}"
    assert stored.password_hash != PASSWORD


async def test_register_generates_the_identifier_rather_than_accepting_one() -> None:
    """T-5-09: the id comes from `uuid4()` here, so two accounts differ.

    The command has no `id` field at all, so this is belt and braces - but it
    is the assertion that would fail first if a later edit let one in.
    """
    unit_of_work = _uow()
    use_case = RegisterUser(unit_of_work, FakePasswordHasher(), FrozenClock(LATER))

    first = await use_case.execute(_command())
    second = await use_case.execute(_command(email="other@example.com"))

    assert first.id != second.id
    assert unit_of_work.commits == 2


async def test_register_refuses_a_duplicate_address_in_any_letter_case() -> None:
    """D-10: `Ana@X.com` and `ana@x.com` are one account, so the second is a 409."""
    unit_of_work = _uow(registered=EMAIL)
    use_case = RegisterUser(unit_of_work, FakePasswordHasher(), FrozenClock(LATER))

    with pytest.raises(EmailAlreadyRegisteredError):
        await use_case.execute(_command(email="ANA@Example.com"))

    assert unit_of_work.user_repository.added == []
    assert unit_of_work.commits == 0
    assert unit_of_work.rollbacks == 1


async def test_a_duplicate_the_pre_check_missed_is_refused_by_the_index() -> None:
    """The race backstop: the same class, raised by the adapter instead.

    Both roads are required and both are tested, because they answer different
    questions - the pre-check is what makes the ordinary 409 clean and
    testable, and the constraint is what actually holds when two registrations
    interleave. An implementation that dropped either one passes one of these
    two tests and fails the other.
    """
    unit_of_work = _uow(registered=EMAIL, blind=True)
    use_case = RegisterUser(unit_of_work, FakePasswordHasher(), FrozenClock(LATER))

    with pytest.raises(EmailAlreadyRegisteredError):
        await use_case.execute(_command())

    assert unit_of_work.commits == 0
    assert unit_of_work.rollbacks == 1


async def test_the_duplicate_refusal_never_repeats_the_address() -> None:
    """D-23: the 409 is an accepted oracle, and it is bounded to the status.

    Nothing about the submitted address is echoed - not in the message, not in
    `details` - so the response and every log line built from it disclose only
    what the caller already typed.
    """
    unit_of_work = _uow(registered=EMAIL)
    use_case = RegisterUser(unit_of_work, FakePasswordHasher(), FrozenClock(LATER))

    with pytest.raises(EmailAlreadyRegisteredError) as excinfo:
        await use_case.execute(_command())

    assert EMAIL not in str(excinfo.value)
    assert excinfo.value.details == {"field": "email"}
    assert EMAIL not in str(excinfo.value.details)


@pytest.mark.parametrize(
    "length",
    [PASSWORD_MIN_LENGTH - 1, PASSWORD_MAX_LENGTH + 1],
    ids=["one-short", "one-long"],
)
async def test_a_password_outside_the_policy_never_reaches_the_hasher(
    length: int,
) -> None:
    """T-5-07: D-10's bound is what stops an unbounded Argon2 request.

    The assertion is on the hasher's recorder rather than on elapsed time: a
    timing assertion in a unit suite is a flake, and "was the work requested?"
    is the property. The lengths are derived from the domain constants, so a
    policy change moves this test with it rather than leaving it asserting an
    old number.
    """
    unit_of_work = _uow()
    hasher = FakePasswordHasher()
    use_case = RegisterUser(unit_of_work, hasher, FrozenClock(LATER))

    with pytest.raises(ValidationError) as excinfo:
        await use_case.execute(_command(password="p" * length))

    assert excinfo.value.details == {"field": "password"}
    assert hasher.hashed == []
    assert unit_of_work.user_repository.added == []
    assert unit_of_work.commits == 0
    # Nothing was refused *inside* a transaction either: the policy check runs
    # before the block is entered, so there is no transaction to roll back.
    assert unit_of_work.rollbacks == 0
