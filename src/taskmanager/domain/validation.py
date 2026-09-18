"""The guards every entity delegates its field validation to.

The rejected alternative is expressing these same rules as Pydantic field
constraints on the request schemas at the HTTP boundary. A limit that exists in
two layers is a defect rather than redundancy (D-04): the two copies drift, and
the one a reviewer reads is not necessarily the one the database is protected
by. Pydantic therefore checks shape and type only, and every policy limit is
enforced here, once, on the way into an entity.

The functions take the field name as a keyword argument rather than inferring
it, because the name is what travels into `ValidationError.details` and from
there into the `errors` member of the problem body a client actually reads.
"""

from datetime import UTC, datetime

from taskmanager.domain.exceptions import ValidationError


def require_utc(value: datetime, *, field: str) -> datetime:
    """Return the value as an aware UTC datetime, refusing a naive one."""
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ValidationError(
            f"{field} must be a timezone-aware datetime in UTC.",
            details={"field": field},
        )
    # Aware does not imply UTC: reading a local clock and applying astimezone()
    # with no argument yields an offset-carrying value. Storing those unchanged
    # would leave `completed_at` comparisons and Phase 3's timestamptz round
    # trip dependent on whichever offset the caller happened to be in.
    return value.astimezone(UTC)


def require_text(value: str, *, field: str, max_length: int) -> str:
    """Return the trimmed value, refusing a blank or over-long one."""
    text = value.strip()
    if not text:
        raise ValidationError(
            f"{field} must not be blank.",
            details={"field": field},
        )
    if len(text) > max_length:
        # The number comes from the argument, never from a literal repeated
        # here, so the entity ClassVar stays the single source of the limit.
        raise ValidationError(
            f"{field} must be at most {max_length} characters long.",
            details={"field": field},
        )
    return text


def optional_text(value: str | None, *, field: str, max_length: int) -> str | None:
    """Return the trimmed value, None for an absent or blank one."""
    if value is None:
        return None
    text = value.strip()
    if not text:
        # An explicitly empty string clears the field. Storing "" alongside NULL
        # would give the same absence two representations to test for.
        return None
    if len(text) > max_length:
        raise ValidationError(
            f"{field} must be at most {max_length} characters long.",
            details={"field": field},
        )
    return text
