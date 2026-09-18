"""How much of a task list is done, as a value object.

There is deliberately no `__post_init__` guard rejecting negative counts or a
`completed` greater than `total`. Such a guard would make this value object depend
on the error hierarchy to describe a state only a broken SQL aggregate could
produce, and it is that single `COUNT(*) FILTER (...)` query (ADR-009, Phase 3)
which guarantees the invariant at its source. The absence of validation here is a
decision, not an omission.

`frozen=True, slots=True` rather than the plain `slots=True` of the entities: this
is a value object with no identity and no lifecycle, so nothing may edit it after
the aggregate produced it.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CompletionStats:
    """The completion counters of one task list, and the percentage they imply."""

    total: int
    completed: int

    @property
    def percentage(self) -> float:
        """Share of the list that is completed, rounded to two decimals."""
        # An empty list reports 0.0 rather than raising ZeroDivisionError: ADR-009
        # makes the percentage a property of the list, and a list with no tasks is
        # a perfectly ordinary list.
        if self.total == 0:
            return 0.0
        return round(self.completed / self.total * 100, 2)
