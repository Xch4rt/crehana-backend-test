"""Unit tests for the shared domain validation guards."""

from datetime import UTC, datetime, timedelta, timezone

import pytest

from taskmanager.domain.exceptions import ValidationError
from taskmanager.domain.validation import optional_text, require_text, require_utc

# Fixed literals rather than a clock reading or a generated identifier: a guard
# that normalises time must be asserted against an instant the reader can see.
AWARE_UTC = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
NAIVE = datetime(2026, 1, 1, 12, 0)
BOGOTA = timezone(timedelta(hours=-5))
AWARE_NON_UTC = datetime(2026, 1, 1, 7, 0, tzinfo=BOGOTA)


def test_require_utc_rejects_a_naive_datetime() -> None:
    """A datetime with no timezone never reaches an entity field (D-14)."""
    with pytest.raises(ValidationError) as excinfo:
        require_utc(NAIVE, field="due_date")

    assert excinfo.value.details == {"field": "due_date"}


def test_require_utc_normalises_an_aware_non_utc_datetime() -> None:
    """An offset-carrying instant is kept, its representation moved to UTC."""
    normalised = require_utc(AWARE_NON_UTC, field="due_date")

    assert normalised.tzinfo is UTC
    assert normalised == AWARE_NON_UTC
    assert normalised == AWARE_UTC


def test_require_utc_returns_an_already_utc_datetime_unchanged() -> None:
    """The common case costs nothing: an aware UTC value passes straight through."""
    assert require_utc(AWARE_UTC, field="created_at") == AWARE_UTC


def test_require_text_strips_surrounding_whitespace() -> None:
    """Leading and trailing spaces are noise, not content."""
    assert require_text("  hello  ", field="title", max_length=200) == "hello"


def test_require_text_rejects_a_blank_value() -> None:
    """An empty string is not a title, and the field is named in the details."""
    with pytest.raises(ValidationError) as excinfo:
        require_text("", field="title", max_length=200)

    assert excinfo.value.details == {"field": "title"}


def test_require_text_rejects_a_whitespace_only_value() -> None:
    """Whitespace collapses to nothing, so it is refused like an empty string."""
    with pytest.raises(ValidationError) as excinfo:
        require_text("   ", field="title", max_length=200)

    assert excinfo.value.details == {"field": "title"}


def test_require_text_rejects_an_over_length_value() -> None:
    """One character past the supplied limit is already too long."""
    with pytest.raises(ValidationError) as excinfo:
        require_text("a" * 201, field="title", max_length=200)

    assert excinfo.value.details == {"field": "title"}


def test_require_text_accepts_a_value_exactly_at_the_limit() -> None:
    """The limit is inclusive: 200 characters is a valid title."""
    assert require_text("a" * 200, field="title", max_length=200) == "a" * 200


def test_require_text_message_states_the_limit_it_was_given() -> None:
    """The number in the message comes from the argument, never from a literal."""
    with pytest.raises(ValidationError) as excinfo:
        require_text("a" * 8, field="name", max_length=7)

    assert "7" in str(excinfo.value)


def test_optional_text_passes_none_through() -> None:
    """An omitted optional field stays omitted."""
    assert optional_text(None, field="description", max_length=2000) is None


def test_optional_text_turns_a_whitespace_only_value_into_none() -> None:
    """An explicitly blank string clears the field rather than storing spaces."""
    assert optional_text("   ", field="description", max_length=2000) is None


def test_optional_text_strips_surrounding_whitespace() -> None:
    """A present value is trimmed exactly like a required one."""
    assert optional_text("  note  ", field="description", max_length=2000) == "note"


def test_optional_text_rejects_an_over_length_value() -> None:
    """Optional does not mean unbounded: the cap still applies."""
    with pytest.raises(ValidationError) as excinfo:
        optional_text("a" * 2001, field="description", max_length=2000)

    assert excinfo.value.details == {"field": "description"}
