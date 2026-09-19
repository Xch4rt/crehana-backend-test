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
from typing import Final

from taskmanager.domain.exceptions import ValidationError

# D-10's password policy, length only, spelled here and nowhere else. These are
# module constants rather than `ClassVar`s on `User`, unlike `Task.TITLE_MAX_LENGTH`
# and every other limit in this project, and the asymmetry is deliberate: the
# entity never sees a plaintext password at all - only the Argon2 encoded hash
# reaches it - so there is no entity that could own the rule. Phase 2 D-04 still
# applies, and this module is the only place in the domain that can hold it.
PASSWORD_MIN_LENGTH: Final[int] = 8
PASSWORD_MAX_LENGTH: Final[int] = 128


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
    try:
        return value.astimezone(UTC)
    except (OverflowError, ValueError) as error:
        # Phase 4 review WR-02. `datetime` stops at year 1 and at year 9999, and
        # a value within a day of either end carrying a non-zero offset has no
        # UTC form inside that range: `9999-12-31T23:59:59-12:00` is noon on a
        # day this type cannot name. CPython raises `OverflowError` for it (and
        # documents `ValueError` for the same family), neither of which is a
        # `DomainError` - so a well-formed ISO-8601 string in a JSON body
        # reached the catch-all and answered 500. It is a rule about the value,
        # so it is refused here, as every other rule about a value is, with the
        # `field` a client needs in order to find it.
        raise ValidationError(
            f"{field} is outside the supported date range.",
            details={"field": field},
        ) from error


def _refuse_nul(text: str, *, field: str) -> None:
    """Refuse the one character no text column can hold (Phase 4 review WR-03).

    `"\u0000"` is valid JSON and a valid Python `str`; it survives `strip()` and
    counts as one character, so it passed every rule below - and PostgreSQL then
    refused the statement, because its text types cannot contain NUL. That
    arrived as a driver error no adapter translates, so a well-formed body
    answered 500, and for a list name it did so from inside the duplicate-name
    SELECT before anything was written at all.

    The rule lives here rather than as a caught driver error, because it is a
    rule about the value: the domain says what a title may contain, and an
    adapter that turned a `DataError` back into "your title is wrong" would be
    guessing which field a statement-level failure was about. Called from both
    helpers, so there is one copy and no text field can be added without it.
    Only NUL is refused - other control characters are storable, and whether
    they are *welcome* is a product question nobody has asked.
    """
    if "\x00" in text:
        raise ValidationError(
            f"{field} must not contain NUL characters.",
            details={"field": field},
        )


def require_text(value: str, *, field: str, max_length: int) -> str:
    """Return the trimmed value, refusing a blank or over-long one."""
    text = value.strip()
    if not text:
        raise ValidationError(
            f"{field} must not be blank.",
            details={"field": field},
        )
    _refuse_nul(text, field=field)
    if len(text) > max_length:
        # The number comes from the argument, never from a literal repeated
        # here, so the entity ClassVar stays the single source of the limit.
        raise ValidationError(
            f"{field} must be at most {max_length} characters long.",
            details={"field": field},
        )
    return text


def require_password(value: str, *, field: str) -> str:
    """Return the password unchanged, refusing one outside D-10's length policy.

    The policy is length only - no composition rule, no character class, no
    dictionary - following NIST 800-63B, and the upper bound doubles as the
    bound on the Argon2 work a single unauthenticated request can demand.

    It reads like `require_text` and deliberately differs from it in three ways,
    each of which is a decision rather than an omission:

    - It does **not** `.strip()`. Leading and trailing whitespace is part of a
      password, not noise around it; trimming would silently change a credential
      between registration and login, so a password chosen with a trailing space
      would be unusable and its owner would have no way to find out why.
    - It does **not** call `_refuse_nul`. That guard exists because PostgreSQL's
      text types cannot hold NUL and `title`, `name` and `full_name` are stored
      verbatim. A password never becomes a text column - only its Argon2 encoded
      hash is stored, and Argon2 hashes arbitrary bytes - so the guard would have
      nothing to protect here, and refusing a character would be exactly the kind
      of composition rule D-10 rules out.
    - Its bounds are the module constants above rather than an argument or an
      entity `ClassVar`, because there is no entity to put them on: `User` holds
      a hash and never sees plaintext. The rule about the number is unchanged -
      it is spelled once - only its home differs from `Task.TITLE_MAX_LENGTH`.

    The two bounds are refused separately, with distinct messages, so the 422
    body tells the caller which one they crossed rather than restating the range.
    """
    if len(value) < PASSWORD_MIN_LENGTH:
        raise ValidationError(
            f"{field} must be at least {PASSWORD_MIN_LENGTH} characters long.",
            details={"field": field},
        )
    if len(value) > PASSWORD_MAX_LENGTH:
        raise ValidationError(
            f"{field} must be at most {PASSWORD_MAX_LENGTH} characters long.",
            details={"field": field},
        )
    return value


def optional_text(value: str | None, *, field: str, max_length: int) -> str | None:
    """Return the trimmed value, None for an absent or blank one."""
    if value is None:
        return None
    text = value.strip()
    if not text:
        # An explicitly empty string clears the field. Storing "" alongside NULL
        # would give the same absence two representations to test for.
        return None
    _refuse_nul(text, field=field)
    if len(text) > max_length:
        raise ValidationError(
            f"{field} must be at most {max_length} characters long.",
            details={"field": field},
        )
    return text
