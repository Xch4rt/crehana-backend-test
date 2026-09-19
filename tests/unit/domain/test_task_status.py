"""Unit tests for the task status enum and its transition table."""

import json

import pytest

from taskmanager.domain.value_objects.task_status import ALLOWED_TRANSITIONS, TaskStatus

pytestmark = pytest.mark.unit


def test_task_status_serializes_to_its_lowercase_value() -> None:
    """json.dumps emits the bare string value, with no custom encoder."""
    payload = json.dumps({"status": TaskStatus.PENDING})

    assert payload == '{"status": "pending"}'


def test_task_status_formats_as_its_value() -> None:
    """An f-string renders the value, never the `TaskStatus.X` member name."""
    assert f"{TaskStatus.IN_PROGRESS}" == "in_progress"


def test_task_status_is_rebuilt_from_its_wire_value() -> None:
    """A known wire value resolves back to the singleton member."""
    assert TaskStatus("completed") is TaskStatus.COMPLETED


def test_task_status_rejects_an_unknown_value() -> None:
    """An undeclared status is a ValueError naming the rejected input."""
    with pytest.raises(ValueError) as excinfo:
        TaskStatus("done")

    assert "done" in str(excinfo.value)


def test_task_status_declares_exactly_three_members() -> None:
    """Exactly three statuses; cancelled, archived and blocked stay out of scope."""
    assert [member.value for member in TaskStatus] == [
        "pending",
        "in_progress",
        "completed",
    ]


def test_transition_table_covers_every_status() -> None:
    """The table is exhaustive, so a fourth status fails loudly at the lookup."""
    assert set(ALLOWED_TRANSITIONS) == set(TaskStatus)


def test_transition_table_matches_the_documented_matrix() -> None:
    """Each status allows exactly the moves recorded in the decision log."""
    assert ALLOWED_TRANSITIONS[TaskStatus.PENDING] == frozenset(
        {TaskStatus.IN_PROGRESS, TaskStatus.COMPLETED}
    )
    assert ALLOWED_TRANSITIONS[TaskStatus.IN_PROGRESS] == frozenset(
        {TaskStatus.PENDING, TaskStatus.COMPLETED}
    )
    assert ALLOWED_TRANSITIONS[TaskStatus.COMPLETED] == frozenset(
        {TaskStatus.IN_PROGRESS}
    )


def test_completed_to_pending_is_not_an_allowed_transition() -> None:
    """The single forbidden move: a completed task reopens into in_progress."""
    assert TaskStatus.PENDING not in ALLOWED_TRANSITIONS[TaskStatus.COMPLETED]


def test_no_status_allows_a_transition_to_itself() -> None:
    """A same-state request is an idempotent no-op on the entity, not a table entry."""
    for status, allowed in ALLOWED_TRANSITIONS.items():
        assert status not in allowed
