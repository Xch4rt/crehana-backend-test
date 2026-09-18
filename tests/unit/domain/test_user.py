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

# A name that is not a field, held in a constant so mypy does not reject the
# assignment this test exists to observe failing at runtime.
UNDECLARED_FIELD = "password"


def _user(email: str = "person@example.com") -> User:
    """Build the reference user every positive test starts from."""
    return User.create(
        user_id=USER_ID,
        email=email,
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


def test_user_validation_rejects_a_blank_password_hash() -> None:
    """A user without a credential is not a user."""
    with pytest.raises(ValidationError) as excinfo:
        User.create(
            user_id=USER_ID,
            email="person@example.com",
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
