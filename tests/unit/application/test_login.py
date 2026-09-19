"""AUTH-02 and D-12: a login that tells an attacker exactly one thing.

The test that matters here is the comparative one. Every other assertion in
this module could pass against an implementation that answers "no account with
that address" to one caller and "wrong password" to another - both raise
`AuthenticationError`, both refuse the request, and a suite that caught the
class twice would call that correct. So the two refusals are produced from one
fixture and compared on every field a client can observe: class, `code`,
message and `details`. That comparison is the gate D-12 rests on, and the
single module-level constant in `login.py` is the mechanism it is checking.

The second property is cost. Equal bodies are not enough when the two paths
differ by 23 ms: the wrong-password leg pays Argon2id (measured at 23.6 ms in
`05-RESEARCH.md`) while a leg with no stored hash to compare against would
return in microseconds, and the difference is readable off a stopwatch. The
assertions are on the fake's recorders rather than on elapsed time - a timing
assertion in a unit suite is a flake, and "was the work requested?" is the
property, while the real cost is measured exactly once, in
`tests/unit/infrastructure/test_passwords.py`.

Nothing here commits. The lookup is a read, so `commits == 0` and
`rollbacks == 1` even on the successful path, for the reason
`use_cases/task_lists/list.py` states.
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from taskmanager.application.dto.commands import LoginCommand
from taskmanager.application.use_cases.auth.login import Login
from taskmanager.domain.entities.user import User
from taskmanager.domain.exceptions import AuthenticationError, DomainError
from tests.unit.application.fakes import (
    FakePasswordHasher,
    FakeTokenService,
    FakeUnitOfWork,
    FakeUserRepository,
)

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
USER_ID = UUID("11111111-1111-4111-8111-111111111111")

EMAIL = "ana@example.com"
FULL_NAME = "Ana Torres"
PASSWORD = "a-long-enough-password"
WRONG_PASSWORD = "not-the-right-password"
UNKNOWN_EMAIL = "nobody@example.com"

# The same value `create_app` will pass from `jwt_expire_minutes`; fixed here so
# the seconds assertion can name a number rather than restate the arithmetic.
EXPIRE_MINUTES = 30


def _uow(*, registered: bool = True) -> FakeUnitOfWork:
    """A unit of work holding one registered account, or holding none.

    The entity goes into `stored` directly rather than through `add()`: what is
    under test is the lookup, and nothing in this module should depend on the
    repository's write path.
    """
    users = FakeUserRepository()
    if registered:
        user = User.create(
            user_id=USER_ID,
            email=EMAIL,
            full_name=FULL_NAME,
            password_hash=f"{FakePasswordHasher.PREFIX}{PASSWORD}",
            now=NOW,
        )
        users.stored[user.id] = user
    return FakeUnitOfWork(users=users)


def _login(
    unit_of_work: FakeUnitOfWork, hasher: FakePasswordHasher | None = None
) -> Login:
    """The single construction site, so every test injects the same four things."""
    return Login(
        unit_of_work,
        hasher if hasher is not None else FakePasswordHasher(),
        FakeTokenService(),
        EXPIRE_MINUTES,
    )


async def test_the_right_credentials_return_a_bearer_token() -> None:
    """The happy path, including both wire-format fields of the answer.

    `token_type` is the lowercase literal Swagger's Authorize button
    concatenates, and `expires_in` is seconds - the setting is in minutes, so
    the multiplication is asserted rather than assumed.
    """
    unit_of_work = _uow()

    result = await _login(unit_of_work).execute(
        LoginCommand(email=EMAIL, password=PASSWORD)
    )

    assert result.access_token == str(USER_ID)
    assert result.token_type == "bearer"
    assert result.expires_in == EXPIRE_MINUTES * 60
    assert result.expires_in > 0


async def test_a_successful_login_makes_nothing_durable() -> None:
    """A read is a read: `commits == 0`, and the transaction was still closed.

    `commits == 0` on its own is equally true of a transaction nobody ever
    closed, which is why the rollback is asserted beside it.
    """
    unit_of_work = _uow()

    await _login(unit_of_work).execute(LoginCommand(email=EMAIL, password=PASSWORD))

    assert unit_of_work.commits == 0
    assert unit_of_work.rollbacks == 1


async def test_an_address_typed_in_another_case_still_logs_in() -> None:
    """D-10: `Ana@X.com` and `ana@x.com` are one account on the way in too.

    Registration canonicalises through the entity; this is the other half -
    a lookup that folded no case would leave an account unreachable by the
    spelling its owner actually types.
    """
    unit_of_work = _uow()

    result = await _login(unit_of_work).execute(
        LoginCommand(email="  Ana@Example.COM ", password=PASSWORD)
    )

    assert result.access_token == str(USER_ID)


async def test_an_unknown_address_is_refused() -> None:
    """No account, no token - and no hint that the account is what is missing."""
    unit_of_work = _uow(registered=False)

    with pytest.raises(AuthenticationError):
        await _login(unit_of_work).execute(
            LoginCommand(email=UNKNOWN_EMAIL, password=PASSWORD)
        )

    assert unit_of_work.commits == 0
    assert unit_of_work.rollbacks == 1


async def test_a_wrong_password_on_a_real_account_is_refused() -> None:
    """The other leg, with the account present and the credential wrong.

    Caught as the base `DomainError` and then narrowed, the 04-03 pattern: the
    leaf assertion alone would pass against an implementation that never
    considered which error class this case deserves.
    """
    unit_of_work = _uow()

    with pytest.raises(DomainError) as excinfo:
        await _login(unit_of_work).execute(
            LoginCommand(email=EMAIL, password=WRONG_PASSWORD)
        )

    assert type(excinfo.value) is AuthenticationError
    assert unit_of_work.commits == 0


async def test_the_two_refusals_are_indistinguishable() -> None:
    """D-12, the gate: one refusal, compared field by field across both legs.

    An implementation with two `raise` statements and two hand-written strings
    is one typo away from an enumeration oracle, and this is the test that
    would be the only thing between the project and that bug - so it compares
    everything a client can see rather than only the class.
    """
    with pytest.raises(AuthenticationError) as unknown_address:
        await _login(_uow(registered=False)).execute(
            LoginCommand(email=UNKNOWN_EMAIL, password=PASSWORD)
        )
    with pytest.raises(AuthenticationError) as wrong_password:
        await _login(_uow()).execute(LoginCommand(email=EMAIL, password=WRONG_PASSWORD))

    assert type(unknown_address.value) is type(wrong_password.value)
    assert unknown_address.value.code == wrong_password.value.code
    assert str(unknown_address.value) == str(wrong_password.value)
    assert unknown_address.value.details == wrong_password.value.details
    # And neither of them names the address that was submitted (T-5-04).
    assert UNKNOWN_EMAIL not in str(unknown_address.value)
    assert EMAIL not in str(wrong_password.value)


async def test_the_unknown_address_leg_pays_the_hashing_work_anyway() -> None:
    """D-21: the equalisation, asserted as a port call rather than as a clock.

    Equal bodies are not enough if the two paths differ by 23 ms. There is no
    stored hash to compare against here, so the work is requested through the
    port's throwaway-hash method instead - and the assertion is that it was
    requested exactly once, with the submitted password, since a call that
    passed something else would be doing different work.
    """
    hasher = FakePasswordHasher()

    with pytest.raises(AuthenticationError):
        await _login(_uow(registered=False), hasher).execute(
            LoginCommand(email=UNKNOWN_EMAIL, password=PASSWORD)
        )

    assert hasher.dummy_verifications == [PASSWORD]
    assert hasher.verifications == []


async def test_the_wrong_password_leg_pays_it_through_the_real_comparison() -> None:
    """The mirror image: one real verification, and no throwaway work beside it.

    Asserted as well as its twin because "both legs call something" is not the
    property - "each leg calls exactly one of the two, exactly once" is, and an
    implementation that called both on one path would be doing twice the work
    and would still pass a laxer test.
    """
    hasher = FakePasswordHasher()

    with pytest.raises(AuthenticationError):
        await _login(_uow(), hasher).execute(
            LoginCommand(email=EMAIL, password=WRONG_PASSWORD)
        )

    assert hasher.verifications == [
        (WRONG_PASSWORD, f"{FakePasswordHasher.PREFIX}{PASSWORD}")
    ]
    assert hasher.dummy_verifications == []


async def test_a_successful_login_pays_the_work_exactly_once() -> None:
    """The third leg of the same property: success verifies once and no more.

    Without this, an implementation that verified twice - or that verified and
    then also burned the throwaway work - would satisfy both refusal tests.
    """
    hasher = FakePasswordHasher()

    await _login(_uow(), hasher).execute(LoginCommand(email=EMAIL, password=PASSWORD))

    assert hasher.verifications == [
        (PASSWORD, f"{FakePasswordHasher.PREFIX}{PASSWORD}")
    ]
    assert hasher.dummy_verifications == []
