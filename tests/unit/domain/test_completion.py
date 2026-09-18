"""Unit tests for the completion statistics value object."""

from dataclasses import FrozenInstanceError

import pytest

from taskmanager.domain.value_objects.completion import CompletionStats

# Attribute names are held in constants rather than written as literals inside
# `setattr`, which keeps both negative tests readable and keeps mypy from
# rejecting an assignment the test exists precisely to observe at runtime.
DECLARED_FIELD = "total"
UNDECLARED_FIELD = "ratio"


def test_completion_percentage_of_an_empty_list_is_zero() -> None:
    """An empty list reports 0.0, never a ZeroDivisionError (ADR-009)."""
    assert CompletionStats(total=0, completed=0).percentage == 0.0


def test_completion_percentage_is_rounded_to_two_decimals() -> None:
    """One of three completed is reported as 33.33, not 33.333333333333336."""
    assert CompletionStats(total=3, completed=1).percentage == 33.33


def test_completion_percentage_of_a_finished_list_is_one_hundred() -> None:
    """Every task completed reports the full hundred."""
    assert CompletionStats(total=4, completed=4).percentage == 100.0


def test_completion_percentage_of_an_untouched_list_is_zero() -> None:
    """A list with tasks but none completed reports 0.0, like the empty one."""
    assert CompletionStats(total=2, completed=0).percentage == 0.0


def test_completion_percentage_is_a_float() -> None:
    """The wire type is float: not Decimal, and not an int on the round numbers."""
    assert isinstance(CompletionStats(total=4, completed=4).percentage, float)
    assert isinstance(CompletionStats(total=0, completed=0).percentage, float)


def test_completion_stats_is_immutable() -> None:
    """A declared field cannot be edited after the aggregate produced it."""
    stats = CompletionStats(total=3, completed=1)

    with pytest.raises(FrozenInstanceError) as excinfo:
        setattr(stats, DECLARED_FIELD, 99)

    assert DECLARED_FIELD in str(excinfo.value)


def test_completion_stats_rejects_an_undeclared_attribute() -> None:
    """slots=True leaves no __dict__, so a typo'd attribute cannot be created."""
    stats = CompletionStats(total=3, completed=1)

    # The exception type for a name that is not a field is interpreter-specific
    # on a frozen+slots dataclass, and both runtimes of this project disagree:
    # CPython 3.13 (Docker, CI) raises FrozenInstanceError, which is an
    # AttributeError, while 3.14.3 (this host) reaches `super(cls, self)` with
    # the pre-slots class and raises TypeError. Asserting one of them would make
    # the suite pass on one runtime and fail on the other, so the assertion is
    # the portable claim instead: the attribute is refused, and the object has
    # nowhere to keep it either way.
    with pytest.raises((AttributeError, TypeError)):
        setattr(stats, UNDECLARED_FIELD, 0.5)

    assert not hasattr(stats, UNDECLARED_FIELD)
    assert not hasattr(stats, "__dict__")
    assert CompletionStats.__slots__ == ("total", "completed")
