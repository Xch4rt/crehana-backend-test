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


# Phase 4 review WR-02: both ends of the range `datetime` can represent, each with
# the offset that pushes its UTC form over the edge. Built from ISO strings
# because that is how they arrive - these are the reviewer's two request bodies.
BEYOND_THE_LAST_YEAR = datetime.fromisoformat("9999-12-31T23:59:59-12:00")
BEFORE_THE_FIRST_YEAR = datetime.fromisoformat("0001-01-01T00:00:00+14:00")


@pytest.mark.parametrize("value", [BEYOND_THE_LAST_YEAR, BEFORE_THE_FIRST_YEAR])
def test_require_utc_refuses_a_value_whose_utc_form_is_out_of_range(
    value: datetime,
) -> None:
    """An aware datetime with no UTC form is a validation error, never a crash.

    `astimezone` raises `OverflowError` here, which is not a `DomainError`, so it
    used to reach the catch-all and answer 500 to a well-formed JSON body.
    """
    with pytest.raises(ValidationError) as excinfo:
        require_utc(value, field="due_date")

    assert excinfo.value.details == {"field": "due_date"}
    assert "outside the supported date range" in str(excinfo.value)
    # The driver-level cause is chained for whoever reads the traceback, and
    # never reaches the message a client is shown.
    assert isinstance(excinfo.value.__cause__, OverflowError)


def test_require_utc_accepts_the_last_representable_instant() -> None:
    """The guard refuses what overflows, not everything near the edge."""
    last = datetime.fromisoformat("9999-12-31T23:59:59+00:00")

    assert require_utc(last, field="due_date") == last


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


# Phase 4 review WR-03. Spelled as an escape so the file itself stays free of the
# character under test: this is what the JSON body `"a\u0000b"` parses to.
WITH_A_NUL = "a\x00b"


def test_require_text_refuses_a_nul_character() -> None:
    """PostgreSQL's text types cannot hold NUL, so the domain says so first."""
    with pytest.raises(ValidationError) as excinfo:
        require_text(WITH_A_NUL, field="title", max_length=200)

    assert excinfo.value.details == {"field": "title"}
    assert "NUL" in str(excinfo.value)
    # The message names the rule and never echoes the offending value back.
    assert "\x00" not in str(excinfo.value)


def test_optional_text_refuses_a_nul_character() -> None:
    """The second helper, because a description reaches the same column type."""
    with pytest.raises(ValidationError) as excinfo:
        optional_text(WITH_A_NUL, field="description", max_length=2000)

    assert excinfo.value.details == {"field": "description"}


def test_a_nul_is_reported_before_the_length() -> None:
    """One refusal per request: the character rule wins over the length rule."""
    with pytest.raises(ValidationError) as excinfo:
        require_text(WITH_A_NUL * 100, field="title", max_length=10)

    assert "NUL" in str(excinfo.value)
