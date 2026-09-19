"""`JwtTokenService`: the behaviour table of PyJWT, turned into assertions.

The shape is `tests/unit/infrastructure/test_errors.py`': a table of inputs and
the single outcome they must all produce, rather than a hand-written test per
library exception. What the table buys here is the property the adapter exists
for - `InvalidAlgorithmError`, `InvalidSignatureError`, `ExpiredSignatureError`,
`MissingRequiredClaimError`, `DecodeError` and a `ValueError` from `UUID` are
six different library failures and exactly one answer to a caller. A test per
exception would still pass if one of them leaked a distinguishing message; the
table plus `test_every_refusal_carries_the_same_message` cannot.

The expired case is minted from a clock two hours in the past and decoded
against the real system clock. That is not a trick, it is the reason the
adapter takes a `Clock` at all: PyJWT validates `exp` against `time.time()`
with no hook, so the *issuing* side is the only side an injected clock can
reach. It is also why this project needs no `freezegun` and no `sleep` - a
suite that slept for a token to expire would be either slow or flaky, and this
one is neither.

One construction is worth naming because the obvious spelling does not work.
An `alg=none` token cannot be produced by passing `headers={"alg": "none"}`
alongside a real key: PyJWT 2.14.0 prepares the key for the *header's*
algorithm and raises `InvalidKeyError` at encode time. The real forgery - which
is what an attacker would send - is an unsigned token, and that is what
`unsigned()` below builds.
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import jwt
import pytest

from taskmanager.application.ports.clock import Clock
from taskmanager.domain.exceptions import AuthenticationError
from taskmanager.infrastructure.clock import SystemClock
from taskmanager.infrastructure.security.tokens import JwtTokenService
from tests.unit.application.fakes import FrozenClock

pytestmark = pytest.mark.unit

SECRET = "a" * 32
# A second key of the same length: the difference under test is whose secret
# signed the token, never how long it was. Both clear the 32-byte floor D-26
# raised `Settings.jwt_secret` to, so nothing here can trip PyJWT's
# short-key warning, which `pytest.ini`'s `filterwarnings = error` would turn
# into a failure with no assertion in the traceback.
OTHER_SECRET = "b" * 32
ALGORITHM = "HS256"
EXPIRE_MINUTES = 30

SUBJECT = UUID("3f2a1b4c-5d6e-4f70-8192-a3b4c5d6e7f8")
EPOCH = 0
FAR_FUTURE = 9_999_999_999
VALID_CLAIMS: dict[str, Any] = {"sub": str(SUBJECT), "iat": EPOCH, "exp": FAR_FUTURE}


def a_service(clock: Clock | None = None) -> JwtTokenService:
    return JwtTokenService(
        secret=SECRET,
        algorithm=ALGORITHM,
        expire_minutes=EXPIRE_MINUTES,
        clock=clock if clock is not None else SystemClock(),
    )


def signed(claims: dict[str, Any], secret: str = SECRET) -> str:
    """A well-formed token, signed with whichever key is named."""
    return jwt.encode(claims, secret, algorithm=ALGORITHM)


def unsigned(claims: dict[str, Any]) -> str:
    """The forgery RFC 8725 §2.1 exists to refuse: a token with no signature.

    Its header advertises the absence, and a verifier that believed the header
    would accept anything at all.
    """
    return jwt.encode(claims, None, algorithm="none")


def an_expired_token() -> str:
    """Exactly what this adapter issued two hours ago, still correctly signed.

    Built here rather than through `issue_access_token` only because the table
    below is a module-level constant and there is no event loop yet;
    `test_a_token_minted_two_hours_ago_has_already_expired` is where the
    adapter itself produces one, from a clock in the past.
    """
    past = datetime.now(UTC) - timedelta(hours=2)
    return signed(
        {
            "sub": str(SUBJECT),
            "iat": past,
            "exp": past + timedelta(minutes=EXPIRE_MINUTES),
        }
    )


# Everything this adapter must refuse, keyed by what is wrong with it. The keys
# become the parametrised test ids, so a failure names the forgery rather than
# an index.
REFUSED: dict[str, str] = {
    "alg_none": unsigned(dict(VALID_CLAIMS)),
    "another_secret": signed(dict(VALID_CLAIMS), OTHER_SECRET),
    "missing_iat": signed({"sub": str(SUBJECT), "exp": FAR_FUTURE}),
    "missing_sub": signed({"iat": EPOCH, "exp": FAR_FUTURE}),
    "missing_exp": signed({"sub": str(SUBJECT), "iat": EPOCH}),
    "subject_not_a_uuid": signed({**VALID_CLAIMS, "sub": "not-a-uuid"}),
    "empty_string": "",
    "garbage": "garbage",
    "expired": an_expired_token(),
}


async def test_a_freshly_issued_token_decodes_back_to_its_subject() -> None:
    """The round trip, and the only path that is meant to succeed."""
    service = a_service()
    subject = uuid4()

    token = await service.decode(await service.issue_access_token(subject))

    assert token == subject


async def test_the_subject_is_carried_as_a_string() -> None:
    """Not cosmetic: PyJWT >= 2.10 refuses a non-string `sub` on decode.

    Read off the encoded token rather than off the adapter, because the claim
    is about what a verifier receives. Writing the `UUID` object straight into
    the payload would round-trip through this adapter's own JSON encoder and
    then fail at the next verifier - or at this one, after an upgrade.
    """
    service = a_service()

    claims = jwt.decode(
        await service.issue_access_token(SUBJECT), SECRET, algorithms=[ALGORITHM]
    )

    assert claims["sub"] == str(SUBJECT)
    assert isinstance(claims["iat"], int)
    assert claims["exp"] - claims["iat"] == EXPIRE_MINUTES * 60


@pytest.mark.parametrize("token", list(REFUSED.values()), ids=list(REFUSED))
async def test_a_token_that_cannot_be_trusted_is_refused(token: str) -> None:
    """Six library exceptions, one answer (T-5-01, T-5-04)."""
    with pytest.raises(AuthenticationError):
        await a_service().decode(token)


async def test_a_token_minted_two_hours_ago_has_already_expired() -> None:
    """The mechanism behind the table's `expired` row, stated once.

    `expire_minutes` is 30, so a token issued at `now - 2h` carries an `exp`
    ninety minutes behind the real clock PyJWT compares against. No sleep, no
    `freezegun`, and no tolerance to tune - which is the point of a leeway of
    zero.
    """
    past = datetime.now(UTC) - timedelta(hours=2)
    service = a_service(FrozenClock(past))

    token = await service.issue_access_token(SUBJECT)

    with pytest.raises(AuthenticationError):
        await service.decode(token)


async def test_every_refusal_carries_the_same_message() -> None:
    """D-11's single generic 401 starts here, in the adapter that refuses.

    A shared status code is not enough: if the messages differed, the body the
    presentation layer builds from this error would tell a caller whether their
    token expired, was signed by the wrong key, or was never signed at all -
    three different pieces of information about a key they should learn nothing
    about. The details dict is asserted empty for the same reason, and because
    it is the other place a token fragment could be echoed back.
    """
    service = a_service()
    messages = set()

    for token in REFUSED.values():
        with pytest.raises(AuthenticationError) as excinfo:
            await service.decode(token)
        messages.add(str(excinfo.value))
        assert excinfo.value.details == {}

    assert len(messages) == 1
    message = messages.pop()
    assert not any(token and token in message for token in REFUSED.values())
