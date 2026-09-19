"""Unit tests for the PATCH sentinel that marks a field the client omitted."""

from taskmanager.application.dto.unset import UNSET, Unset


def _title_or_default(value: str | Unset) -> str:
    """Return the supplied title, or a stand-in when none was provided.

    The annotation is the point of this helper. `value` is `str | Unset`, and
    the return type is `str`, so the `return value` below type-checks only
    because mypy narrows the union on the `is not UNSET` test. Deleting the
    guard makes `make typecheck` fail with an `arg-type`/`return-value` error
    rather than shipping a sentinel into a field that expects a string - which
    is the whole reason the marker is an enum and not `object()`.
    """
    if value is not UNSET:
        return value
    return "unchanged"


def test_unset_is_the_single_member_of_its_enum() -> None:
    """The module constant is the member itself, not a copy or an alias."""
    assert UNSET is Unset.TOKEN


def test_unset_enum_has_exactly_one_member() -> None:
    """A second member would give "not provided" two values to compare against."""
    assert len(list(Unset)) == 1


def test_unset_is_distinguishable_from_none() -> None:
    """The marker exists to differ from the value it must not be confused with.

    `None` is a legal value for every nullable PATCH field (D-05), so both the
    identity and the equality comparison are asserted: an implementation whose
    sentinel merely compared equal to None would make "leave unchanged" and
    "clear this field" the same request.
    """
    assert UNSET is not None
    assert UNSET != None  # noqa: E711 - the comparison itself is under test


def test_the_guard_narrows_the_union_at_runtime_too() -> None:
    """The branch mypy proves statically is exercised on both legs."""
    assert _title_or_default("Ship the thing") == "Ship the thing"
    assert _title_or_default(UNSET) == "unchanged"
