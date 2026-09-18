"""Unit tests for the TaskList entity."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from taskmanager.domain.entities.task_list import TaskList
from taskmanager.domain.exceptions import ValidationError

# Fixed literals, never a clock reading or a generated identifier: a test that
# asserts on `updated_at` has to be able to name the moment it expects.
NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
LATER = NOW + timedelta(hours=1)
NAIVE_NOW = datetime(2026, 1, 1, 12, 0)
TASK_LIST_ID = UUID("22222222-2222-4222-8222-222222222222")
OWNER_ID = UUID("33333333-3333-4333-8333-333333333333")

# A name that is not a field, held in a constant so mypy does not reject the
# assignment this test exists to observe failing at runtime.
UNDECLARED_FIELD = "naem"


def _task_list() -> TaskList:
    """Build the reference list every positive test starts from."""
    return TaskList.create(
        task_list_id=TASK_LIST_ID,
        owner_id=OWNER_ID,
        name="  Work  ",
        now=NOW,
    )


def test_task_list_create_strips_the_name_and_stamps_both_timestamps() -> None:
    """A new list is trimmed, owned, and created and updated at the same moment."""
    task_list = _task_list()

    assert task_list.name == "Work"
    assert task_list.owner_id == OWNER_ID
    assert task_list.created_at == task_list.updated_at == NOW


def test_task_list_create_leaves_an_omitted_description_as_none() -> None:
    """The optional field stays absent rather than becoming an empty string."""
    assert _task_list().description is None


def test_task_list_create_keeps_a_supplied_description() -> None:
    """A present description is trimmed and stored."""
    task_list = TaskList.create(
        task_list_id=TASK_LIST_ID,
        owner_id=OWNER_ID,
        name="Work",
        description="  Everything for the quarter  ",
        now=NOW,
    )

    assert task_list.description == "Everything for the quarter"


def test_task_list_validation_rejects_a_blank_name() -> None:
    """An empty name is refused at construction, naming the field."""
    with pytest.raises(ValidationError) as excinfo:
        TaskList.create(
            task_list_id=TASK_LIST_ID,
            owner_id=OWNER_ID,
            name="",
            now=NOW,
        )

    assert excinfo.value.details == {"field": "name"}


def test_task_list_validation_rejects_a_whitespace_only_name() -> None:
    """Trimming happens before the blank check, so spaces are not a name."""
    with pytest.raises(ValidationError) as excinfo:
        TaskList.create(
            task_list_id=TASK_LIST_ID,
            owner_id=OWNER_ID,
            name="   ",
            now=NOW,
        )

    assert excinfo.value.details == {"field": "name"}


def test_task_list_validation_rejects_an_over_length_name() -> None:
    """The cap is the entity ClassVar, so the test cannot drift from the rule."""
    with pytest.raises(ValidationError) as excinfo:
        TaskList.create(
            task_list_id=TASK_LIST_ID,
            owner_id=OWNER_ID,
            name="a" * (TaskList.NAME_MAX_LENGTH + 1),
            now=NOW,
        )

    assert excinfo.value.details == {"field": "name"}


def test_task_list_validation_rejects_an_over_length_description() -> None:
    """Optional does not mean unbounded."""
    with pytest.raises(ValidationError) as excinfo:
        TaskList.create(
            task_list_id=TASK_LIST_ID,
            owner_id=OWNER_ID,
            name="Work",
            description="a" * (TaskList.DESCRIPTION_MAX_LENGTH + 1),
            now=NOW,
        )

    assert excinfo.value.details == {"field": "description"}


def test_task_list_rename_strips_and_revalidates_the_name() -> None:
    """Renaming runs the same guard as creating, and moves updated_at."""
    task_list = _task_list()

    task_list.rename("  Personal  ", now=LATER)

    assert task_list.name == "Personal"
    assert task_list.updated_at == LATER


def test_task_list_rename_rejects_a_blank_name() -> None:
    """A mutator cannot be used to slip past a constructor invariant."""
    task_list = _task_list()

    with pytest.raises(ValidationError) as excinfo:
        task_list.rename("   ", now=LATER)

    assert excinfo.value.details == {"field": "name"}


def test_task_list_rejects_a_naive_created_at() -> None:
    """A datetime with no timezone cannot become a stored timestamp (D-14)."""
    with pytest.raises(ValidationError) as excinfo:
        TaskList.create(
            task_list_id=TASK_LIST_ID,
            owner_id=OWNER_ID,
            name="Work",
            now=NAIVE_NOW,
        )

    assert excinfo.value.details == {"field": "created_at"}


def test_task_list_rejects_an_undeclared_attribute() -> None:
    """slots=True leaves no __dict__, so a typo cannot create a shadow field."""
    task_list = _task_list()

    with pytest.raises(AttributeError):
        setattr(task_list, UNDECLARED_FIELD, "Work")

    assert not hasattr(task_list, UNDECLARED_FIELD)
    assert not hasattr(task_list, "__dict__")
