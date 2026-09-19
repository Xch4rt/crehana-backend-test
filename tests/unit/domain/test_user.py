"""Unit tests for the User entity."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from taskmanager.domain.entities.user import User
from taskmanager.domain.exceptions import ValidationError

# Fixed literals, never a clock reading or a generated identifier, for the same
# reason as in the sibling entity tests: the expected values stay readable.
NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
NAIVE_NOW = datetime(2026, 1, 1, 12, 0)
USER_ID = UUID("44444444-4444-4444-8444-444444444444")
PASSWORD_HASH = "$argon2id$v=19$m=65536,t=3,p=4$c29tZXNhbHQ$aGFzaA"
FULL_NAME = "Ada Lovelace"

# A name that is not a field, held in a constant so mypy does not reject the
# assignment this test exists to observe failing at runtime.
UNDECLARED_FIELD = "password"


def _user(email: str = "person@example.com", full_name: str = FULL_NAME) -> User:
    """Build the reference user every positive test starts from."""
    return User.create(
        user_id=USER_ID,
        email=email,
        full_name=full_name,
        password_hash=PASSWORD_HASH,
        now=NOW,
    )


def test_user_create_strips_and_lowercases_the_email() -> None:
    """Addresses are stored in one canonical form so lookups cannot miss."""
    assert _user("  MiXeD@Example.COM ").email == "mixed@example.com"


def test_user_create_stamps_both_timestamps_with_the_supplied_moment() -> None:
    """A new user is created and updated at the same instant."""
    user = _user()

    assert user.created_at == user.updated_at == NOW
    assert user.password_hash == PASSWORD_HASH


def test_user_validation_rejects_a_blank_email() -> None:
    """An empty address is refused at construction, naming the field."""
    with pytest.raises(ValidationError) as excinfo:
        _user("   ")

    assert excinfo.value.details == {"field": "email"}


def test_user_validation_rejects_an_over_length_email() -> None:
    """The cap is the entity ClassVar, so the test cannot drift from the rule."""
    with pytest.raises(ValidationError) as excinfo:
        _user("a" * (User.EMAIL_MAX_LENGTH + 1))

    assert excinfo.value.details == {"field": "email"}


def test_user_create_trims_the_full_name_without_folding_its_case() -> None:
    """A display name is trimmed and otherwise stored exactly as typed.

    The contrast with `email` directly above is the decision (AUTH-01, ASGN-03).
    An address is an identity key - `uq_users_email_lower` defends the rule that
    two spellings are one account - so the entity canonicalises it. A full name
    keys nothing, is never looked up by, and belongs to the person who typed it,
    so lower-casing it would corrupt every name whose capitals are not English
    convention and buy nothing in return.
    """
    user = _user(full_name="  Ada  LOVELACE  ")

    assert user.full_name == "Ada  LOVELACE"


def test_user_validation_rejects_a_blank_full_name() -> None:
    """An empty display name is refused at construction, naming the field."""
    with pytest.raises(ValidationError) as excinfo:
        _user(full_name="   ")

    assert excinfo.value.details == {"field": "full_name"}


def test_user_validation_rejects_an_over_length_full_name() -> None:
    """The cap is the entity ClassVar, so the test cannot drift from the rule."""
    with pytest.raises(ValidationError) as excinfo:
        _user(full_name="x" * (User.FULL_NAME_MAX_LENGTH + 1))

    assert excinfo.value.details == {"field": "full_name"}


def test_user_accepts_a_full_name_exactly_at_the_cap() -> None:
    """The boundary is inclusive, so `VARCHAR(100)` never has to refuse a row.

    Paired with the test above on purpose: an off-by-one in either direction
    fails one of the two, and only the pair pins which side of the cap is legal.
    """
    at_the_cap = "x" * User.FULL_NAME_MAX_LENGTH

    assert _user(full_name=at_the_cap).full_name == at_the_cap


def test_user_validation_rejects_a_blank_password_hash() -> None:
    """A user without a credential is not a user."""
    with pytest.raises(ValidationError) as excinfo:
        User.create(
            user_id=USER_ID,
            email="person@example.com",
            full_name=FULL_NAME,
            password_hash="   ",
            now=NOW,
        )

    assert excinfo.value.details == {"field": "password_hash"}


def test_user_does_not_validate_the_email_format() -> None:
    """A deliberate non-validation: format is the Pydantic boundary's job (D-04).

    Duplicating EmailStr here would put the same limit in two layers, which is
    the defect D-04 exists to prevent - so the entity accepts a string that is
    plainly not an address and lets the schema refuse it first.
    """
    assert _user("not-an-email").email == "not-an-email"


def test_user_rejects_a_naive_created_at() -> None:
    """A datetime with no timezone cannot become a stored timestamp (D-14)."""
    with pytest.raises(ValidationError) as excinfo:
        User.create(
            user_id=USER_ID,
            email="person@example.com",
            full_name=FULL_NAME,
            password_hash=PASSWORD_HASH,
            now=NAIVE_NOW,
        )

    assert excinfo.value.details == {"field": "created_at"}


def test_user_declares_no_plaintext_password_field() -> None:
    """The plaintext credential never enters the domain at all."""
    assert UNDECLARED_FIELD not in User.__slots__
    assert "password_hash" in User.__slots__


def test_user_rejects_an_undeclared_attribute() -> None:
    """slots=True leaves no __dict__, so a plaintext password cannot be bolted on."""
    user = _user()

    with pytest.raises(AttributeError):
        setattr(user, UNDECLARED_FIELD, "hunter2")

    assert not hasattr(user, UNDECLARED_FIELD)
    assert not hasattr(user, "__dict__")
