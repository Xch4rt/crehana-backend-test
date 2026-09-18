"""The priority a task carries, from low to high.

`TaskPriority` derives from `enum.StrEnum` for the reason spelled out in
`task_status.py`: the `class TaskPriority(str, Enum)` form formats as
`TaskPriority.LOW` on Python 3.11+, leaking the member name instead of the value
into logs and query strings.

`medium` is the priority a task gets when the caller supplies none (TASK-01), but
that default is applied by the `Task` entity, not here. An enum that knew which of
its members was "the default" would bury a policy decision in the vocabulary every
layer shares, and the same limit would then exist in two places.
"""

from enum import StrEnum


class TaskPriority(StrEnum):
    """The three priorities a task can carry, in ascending urgency."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
