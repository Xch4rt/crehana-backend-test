"""The task lifecycle: its three statuses and the moves allowed between them.

`TaskStatus` derives from `enum.StrEnum` and not from `class TaskStatus(str, Enum)`.
Since Python 3.11 the latter formats as `TaskStatus.PENDING`, so the member name
rather than the value is what reaches a log line, a cache key or a SQL literal - a
defect that only surfaces where it is most expensive to find. `StrEnum` renders and
serializes as the plain value everywhere, with no custom JSON encoder.

`ALLOWED_TRANSITIONS` is exhaustive over every member on purpose. A fourth status
added without its own entry raises `KeyError` at the lookup that guards a status
change, instead of falling through to a permissive default that would silently
allow every move.
"""

from collections.abc import Mapping
from enum import StrEnum
from typing import Final


class TaskStatus(StrEnum):
    """The three states a task can be in, in lifecycle order."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


# Work resumes before it is un-started, so reopening a completed task lands in
# `in_progress`: that makes `completed -> pending` the single forbidden move.
ALLOWED_TRANSITIONS: Final[Mapping[TaskStatus, frozenset[TaskStatus]]] = {
    TaskStatus.PENDING: frozenset({TaskStatus.IN_PROGRESS, TaskStatus.COMPLETED}),
    TaskStatus.IN_PROGRESS: frozenset({TaskStatus.PENDING, TaskStatus.COMPLETED}),
    TaskStatus.COMPLETED: frozenset({TaskStatus.IN_PROGRESS}),
}
