"""The Task aggregate: its invariants and the only copy of the state machine.

The entity is a mutable `@dataclass(slots=True)` and deliberately not
`frozen=True`. D-01 and D-03 change `status`, `updated_at` and `completed_at` in
place, and freezing would force an `object.__setattr__` call in every mutator -
the escape hatch written out once per line, which is worse than not freezing at
all. `slots=True` is kept for the half of the benefit that costs nothing: the
class has no `__dict__`, so a mistyped attribute raises `AttributeError` instead
of silently creating a field nothing ever reads.

`now` arrives as a keyword argument on every method that needs it. The domain
never reads a clock and never imports the `Clock` protocol: `Clock` lives in the
application layer, so depending on it would be an upward import that fails the
`layers` contract in `.importlinter` (D-13). The use case reads the clock once
and hands the instant down.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar
from uuid import UUID

from taskmanager.domain.exceptions import InvalidStatusTransitionError, ValidationError
from taskmanager.domain.validation import optional_text, require_text, require_utc
from taskmanager.domain.value_objects.task_priority import TaskPriority
from taskmanager.domain.value_objects.task_status import ALLOWED_TRANSITIONS, TaskStatus


@dataclass(slots=True)
class Task:
    """A unit of work inside a task list, and the rules it enforces on itself.

    There is one mutator per field a caller may change - `rename`, `describe`,
    `reprioritise`, `reschedule`, `assign`, `unassign` and `change_status` -
    each following the same `now` keyword convention. `status` deliberately has
    no setter beyond
    `change_status`: the state machine is the reason this entity exists, and a
    plain assignment would route around it (TASK-03).
    """

    # TASK-08 / FEATURES section 8 rule 3: a title is 1-200 characters trimmed.
    TITLE_MAX_LENGTH: ClassVar[int] = 200
    # FEATURES section 8 rule 4: the description is optional and capped.
    DESCRIPTION_MAX_LENGTH: ClassVar[int] = 2000
    # TASK-01: a task created without a priority is medium. The default lives
    # here rather than in the request schema because it is a business rule, and
    # Phase 2 D-04 puts every business rule in the entity exactly once - the
    # schema and `create` both read this ClassVar, so `medium` cannot be spelled
    # in two places that drift apart.
    DEFAULT_PRIORITY: ClassVar[TaskPriority] = TaskPriority.MEDIUM

    id: UUID
    task_list_id: UUID
    title: str
    status: TaskStatus
    priority: TaskPriority
    created_at: datetime
    updated_at: datetime
    description: str | None = None
    due_date: datetime | None = None
    completed_at: datetime | None = None
    # Declared in Phase 2 so no later phase had to reopen the entity; written
    # by `assign` and `unassign` since Phase 5 (ASGN-02). It stays optional
    # because an unassigned task is the ordinary case, not a defect.
    assignee_id: UUID | None = None

    def __post_init__(self) -> None:
        """Normalise and validate every field, and the invariant spanning two."""
        self.title = require_text(
            self.title, field="title", max_length=self.TITLE_MAX_LENGTH
        )
        self.description = optional_text(
            self.description,
            field="description",
            max_length=self.DESCRIPTION_MAX_LENGTH,
        )
        self.created_at = require_utc(self.created_at, field="created_at")
        self.updated_at = require_utc(self.updated_at, field="updated_at")
        if self.due_date is not None:
            self.due_date = require_utc(self.due_date, field="due_date")
        if self.completed_at is not None:
            self.completed_at = require_utc(self.completed_at, field="completed_at")
        # D-03 - `completed_at` is set exactly when the status is completed, so
        # a reopened task is never reported as finished - held only as long as
        # every task in existence had been mutated through `change_status`. A
        # row written by a migration, a hand-edited fixture or a Phase 3 mapper
        # bug rehydrates straight through this constructor and would otherwise
        # serialise into a `TaskResult` claiming to be finished with no finish
        # stamp, or unfinished while carrying one. The entity is the single copy
        # of the state machine, so it refuses the incoherent pair here for the
        # same reason it refuses a naive timestamp.
        if (self.status is TaskStatus.COMPLETED) != (self.completed_at is not None):
            raise ValidationError(
                "completed_at must be set exactly when status is completed.",
                details={"field": "completed_at"},
            )

    @classmethod
    def create(
        cls,
        *,
        task_id: UUID,
        task_list_id: UUID,
        title: str,
        description: str | None = None,
        priority: TaskPriority = DEFAULT_PRIORITY,
        due_date: datetime | None = None,
        assignee_id: UUID | None = None,
        now: datetime,
    ) -> "Task":
        """Build a pending task stamped with the supplied moment.

        The identifier is an argument because ids are generated by the
        application layer with uuid4() before persistence, never by the entity
        and never by the database (D-11/D-12): a task is complete from
        construction, so domain tests need no database to exist.
        """
        task = cls(
            id=task_id,
            task_list_id=task_list_id,
            title=title,
            status=TaskStatus.PENDING,
            priority=priority,
            created_at=now,
            updated_at=now,
            description=description,
            due_date=due_date,
            completed_at=None,
            assignee_id=assignee_id,
        )
        # Checked on creation and on reschedule only, never as a standing
        # invariant: the rule validates input and must not retro-invalidate a
        # stored row whose deadline has simply passed (FEATURES section 8
        # rule 6).
        if task.due_date is not None and task.due_date < task.created_at:
            raise ValidationError(
                "due_date must not be earlier than the creation moment.",
                details={"field": "due_date"},
            )
        return task

    def rename(self, title: str, *, now: datetime) -> None:
        """Replace the title, applying the same guard construction applied."""
        # Every guard runs before the first assignment, as in `reschedule` and
        # `change_status`. Assigning the title first and validating `now`
        # afterwards left a refused call with the new title and the old
        # `updated_at`: a half-applied mutation the unit of work cannot undo,
        # because the corrupted copy is the in-memory aggregate, not the row.
        moment = require_utc(now, field="now")
        self.title = require_text(
            title, field="title", max_length=self.TITLE_MAX_LENGTH
        )
        self.updated_at = moment

    def describe(self, description: str | None, *, now: datetime) -> None:
        """Replace or clear the description, under the constructor's own guard."""
        # `optional_text` folds "" to None, so an explicit empty string clears
        # the field exactly as an explicit JSON null does and the absence keeps
        # the single representation `__post_init__` guarantees (Phase 4 D-05).
        moment = require_utc(now, field="now")
        self.description = optional_text(
            description,
            field="description",
            max_length=self.DESCRIPTION_MAX_LENGTH,
        )
        self.updated_at = moment

    def reprioritise(self, priority: TaskPriority, *, now: datetime) -> None:
        """Replace the priority and stamp the change."""
        # There is no value guard here, unlike every sibling mutator, and the
        # absence is deliberate: `TaskPriority` is a StrEnum, so the parameter's
        # own type is the constraint and the enum-typed field at the HTTP
        # boundary refuses anything that is not a member before a command is
        # built. A defensive check would be a branch no test could reach, which
        # this project's coverage norm would then have to excuse with a pragma.
        moment = require_utc(now, field="now")
        self.priority = priority
        self.updated_at = moment

    def assign(self, assignee_id: UUID, *, now: datetime) -> None:
        """Hand the task to a user and stamp the change (ASGN-02).

        There is no value guard here, for the same reason `reprioritise` has
        none: a `UUID` parameter is already the constraint the enum is there,
        and whether that user *exists* is a different question entirely - one
        that needs a repository, which the entity has no access to and must not
        acquire. A defensive check would be a branch no test could reach, which
        this project's no-pragma coverage norm could not excuse.

        The entity deliberately has **no** same-assignee no-op, unlike
        `change_status`: D-07's idempotence has to skip a commit and an
        assignment email as well as a field, so it lives in the `AssignTask` use
        case, which is the layer that owns all three. The asymmetry is named
        here so a later reader does not "fix" it by adding a guard that would
        make the use case's own no-op untestable.
        """
        # The guard runs before the first assignment, as in `rename`: a refused
        # call must leave the in-memory aggregate byte-identical.
        moment = require_utc(now, field="now")
        self.assignee_id = assignee_id
        self.updated_at = moment

    def unassign(self, *, now: datetime) -> None:
        """Take the task back off its assignee and stamp the change.

        Clearing an already-clear assignee still moves `updated_at`; see
        `assign` for why the entity carries no no-op of its own.
        """
        moment = require_utc(now, field="now")
        self.assignee_id = None
        self.updated_at = moment

    def reschedule(self, due_date: datetime | None, *, now: datetime) -> None:
        """Move or clear the deadline, refusing one behind the supplied moment."""
        moment = require_utc(now, field="now")
        if due_date is None:
            self.due_date = None
        else:
            scheduled = require_utc(due_date, field="due_date")
            if scheduled < moment:
                raise ValidationError(
                    "due_date must not be earlier than the current moment.",
                    details={"field": "due_date"},
                )
            self.due_date = scheduled
        self.updated_at = moment

    def change_status(self, new_status: TaskStatus, *, now: datetime) -> None:
        """Move the task through the lifecycle, or refuse a forbidden move."""
        # D-02: asking for the status the task already has is an idempotent
        # no-op. No field moves, no timestamp moves, and Phase 4 answers 200
        # with the unchanged task rather than 409 - repeating a request that
        # already succeeded is not a conflict.
        if new_status is self.status:
            return
        if new_status not in ALLOWED_TRANSITIONS[self.status]:
            raise InvalidStatusTransitionError(self.status, new_status)
        moment = require_utc(now, field="now")
        self.status = new_status
        self.updated_at = moment
        # D-03: entering completed stamps the finish; leaving it clears the
        # stamp, so a reopened task is never reported as finished.
        self.completed_at = moment if new_status is TaskStatus.COMPLETED else None
