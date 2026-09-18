"""Unit tests for the task priority enum."""

import json

import pytest

from taskmanager.domain.value_objects.task_priority import TaskPriority


def test_task_priority_is_ordered_from_low_to_high() -> None:
    """Declaration order is the ascending urgency order clients read as a list."""
    assert list(TaskPriority) == [
        TaskPriority.LOW,
        TaskPriority.MEDIUM,
        TaskPriority.HIGH,
    ]


def test_task_priority_serializes_to_its_lowercase_value() -> None:
    """json.dumps emits the bare string value, with no custom encoder."""
    payload = json.dumps(list(TaskPriority))

    assert payload == '["low", "medium", "high"]'


def test_task_priority_formats_as_its_value() -> None:
    """An f-string renders the value, never the `TaskPriority.X` member name."""
    assert f"{TaskPriority.HIGH}" == "high"


def test_task_priority_is_rebuilt_from_its_wire_value() -> None:
    """A known wire value resolves back to the singleton member."""
    assert TaskPriority("medium") is TaskPriority.MEDIUM


def test_task_priority_rejects_an_unknown_value() -> None:
    """An undeclared priority is a ValueError naming the rejected input."""
    with pytest.raises(ValueError) as excinfo:
        TaskPriority("urgent")

    assert "urgent" in str(excinfo.value)
