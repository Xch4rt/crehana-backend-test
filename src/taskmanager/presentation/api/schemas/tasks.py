"""The task HTTP boundary: creation, the generic patch, the status door, answers.

`task_lists.py` states the three rules this package follows - no business limit
at the boundary, the application's not-provided marker never in a field
annotation, and no instance read of the deprecated field-list attribute - and
they are not restated here.

One rule is specific to this module. `due_date` carries no past-date check.
`Task.create` and `Task.reschedule` own that rule (Phase 2 D-04, D-07), and a
second copy here would do two wrong things at once: it would drift from the
entity's the first time either changed, and it would answer with the
request-validation error shape instead of the domain's - so the same rejected
request would produce two different bodies depending on which layer noticed
first.
"""

from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from taskmanager.application.dto.commands import (
    ChangeTaskStatusCommand,
    CreateTaskCommand,
    UpdateTaskCommand,
)
from taskmanager.application.dto.results import TaskCollectionResult, TaskResult
from taskmanager.application.dto.unset import UNSET
from taskmanager.domain.entities.task import Task
from taskmanager.domain.value_objects.task_priority import TaskPriority
from taskmanager.domain.value_objects.task_status import TaskStatus

# The same two refusal messages `task_lists.py` uses, re-declared rather than
# imported: they are part of this module's contract with its own tests, and a
# shared constant would make a change to one endpoint's wording silently change
# the other's.
NULL_REJECTED_MESSAGE = "this field may not be null"
EMPTY_PATCH_MESSAGE = "at least one field must be provided"


class TaskCreateRequest(BaseModel):
    """`POST /task-lists/{id}/tasks`: a title, and three optional refinements.

    There is no `status` field. A new task starts `pending` and the entity
    decides that (TASK-01), so offering the choice here would be a second place
    the initial state is written.

    `assignee_id` is absent too. Phase 4 declares no assignment endpoint, and a
    field that quietly accepted one would be a mass-assignment surface for a
    capability the API does not otherwise have (T-4-35).
    """

    model_config = ConfigDict(extra="forbid")

    title: str
    description: str | None = None
    # TASK-01's `medium`, read from the entity rather than spelled again. The
    # ClassVar is the single copy of the rule, so `/openapi.json` documents the
    # default the entity will actually apply, and the two cannot drift.
    priority: TaskPriority = Task.DEFAULT_PRIORITY
    due_date: datetime | None = None

    def to_command(self, *, actor_id: UUID, task_list_id: UUID) -> CreateTaskCommand:
        """Bind the body to the caller and the list named in the path."""
        return CreateTaskCommand(
            actor_id=actor_id,
            task_list_id=task_list_id,
            title=self.title,
            description=self.description,
            priority=self.priority,
            due_date=self.due_date,
        )


class TaskPatchRequest(BaseModel):
    """`PATCH /task-lists/{id}/tasks/{id}`: merge-patch, minus the state machine.

    `status` is deliberately not a field. D-08 makes the dedicated status
    endpoint the only door onto the transitions, and with `extra="forbid"` a
    client that sends the key here gets a 422 naming it - which is how TASK-03's
    "the status cannot be changed through the generic patch" is proven to an
    evaluator with one request rather than promised in a document.

    The same three legs as the task-list patch apply per field: omitting leaves
    the field alone, an explicit null clears the two fields that have a null to
    be cleared to, and a null on `title` or `priority` is a field-level 422.
    """

    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    description: str | None = None
    priority: TaskPriority | None = None
    due_date: datetime | None = None

    @field_validator("title", "priority")
    @classmethod
    def _reject_explicit_null(
        cls, value: str | TaskPriority | None
    ) -> str | TaskPriority | None:
        """D-05's explicit-null leg for the two fields that have no null.

        It runs only against a value the client actually sent, because Pydantic
        does not validate a default unless a field asks it to - which is what
        keeps "absent" and "null" two outcomes rather than one.
        """
        if value is None:
            raise ValueError(NULL_REJECTED_MESSAGE)
        return value

    @model_validator(mode="after")
    def _require_at_least_one_field(self) -> Self:
        """D-06: a body that asks for nothing is a 422, not a silent success."""
        if not self.model_fields_set:
            raise ValueError(EMPTY_PATCH_MESSAGE)
        return self

    def to_command(
        self, *, actor_id: UUID, task_list_id: UUID, task_id: UUID
    ) -> UpdateTaskCommand:
        """Turn "the client sent this field" into the application's marker.

        The nullable fields are read through the set of keys the client sent,
        because for them a `None` is a value and absence has to be asked about
        separately. The two non-nullable fields are read with an identity test
        against `None`, which is the same question here - the validator above
        has already refused an explicit null, so a `None` can only mean the key
        was absent - and it is the form the type checker can narrow to the
        command's non-optional field.
        """
        sent = self.model_fields_set
        return UpdateTaskCommand(
            actor_id=actor_id,
            task_list_id=task_list_id,
            task_id=task_id,
            title=self.title if self.title is not None else UNSET,
            description=self.description if "description" in sent else UNSET,
            priority=self.priority if self.priority is not None else UNSET,
            due_date=self.due_date if "due_date" in sent else UNSET,
        )


class TaskStatusChangeRequest(BaseModel):
    """`PATCH .../tasks/{id}/status`: the one door onto the state machine (D-11).

    One required field, so an empty body is a 422 without needing the patch
    models' at-least-one-field rule. The value is enum-typed, so an unknown
    state is refused before any use case runs and can never reach SQL as free
    text (T-4-39); no membership check is written anywhere.
    """

    model_config = ConfigDict(extra="forbid")

    status: TaskStatus

    def to_command(
        self, *, actor_id: UUID, task_list_id: UUID, task_id: UUID
    ) -> ChangeTaskStatusCommand:
        """Bind the requested state to the task the path addressed.

        `task_list_id` travels with it because the use case compares it against
        the task's own parent and refuses a mismatch (D-14); a nested path whose
        parent segment never reached the use case would be an ownership check
        that passes while checking nothing.
        """
        return ChangeTaskStatusCommand(
            actor_id=actor_id,
            task_list_id=task_list_id,
            task_id=task_id,
            new_status=self.status,
        )


class TaskResponse(BaseModel):
    """One task on the wire: the eleven members of `TaskResult`, in its order.

    Declaration order is serialisation order, so this list is the contract. It
    mirrors the result DTO exactly, which is what lets `from_result` below be a
    field-for-field copy that a reviewer can check by reading down two columns.
    """

    id: UUID
    task_list_id: UUID
    title: str
    description: str | None
    status: TaskStatus
    priority: TaskPriority
    created_at: datetime
    updated_at: datetime
    due_date: datetime | None
    completed_at: datetime | None
    assignee_id: UUID | None

    @classmethod
    def from_result(cls, result: TaskResult) -> "TaskResponse":
        """Copy every field of the result, naming each one explicitly."""
        return cls(
            id=result.id,
            task_list_id=result.task_list_id,
            title=result.title,
            description=result.description,
            status=result.status,
            priority=result.priority,
            created_at=result.created_at,
            updated_at=result.updated_at,
            due_date=result.due_date,
            completed_at=result.completed_at,
            assignee_id=result.assignee_id,
        )


class TaskCollectionResponse(BaseModel):
    """`GET /task-lists/{id}/tasks`: exactly these four members, in this order.

    D-09 fixes the envelope, and the fixing is the point. `.planning/research`
    proposes an echoed `list_id`, a `returned_count` beside the total, and the
    filters played back to the caller; CONTEXT overrules all three, so a client
    reads the list's identity from the URL it asked for and the size of the page
    from the array it received.

    The three statistics describe the **whole list**, whatever the filter says.
    `items` is what the caller asked to see; the counters are what the list is.
    A percentage that moved when a client changed a filter would be a different
    number wearing the same name (ADR-009), and an empty list answers `0.0`
    rather than dividing by nothing.
    """

    items: list[TaskResponse]
    total_tasks: int
    completed_tasks: int
    completion_percentage: float

    @classmethod
    def from_result(cls, result: TaskCollectionResult) -> "TaskCollectionResponse":
        """Copy the envelope member for member, items in the order given.

        The order is D-13's: the repository sorts by `created_at` then `id`, a
        total order, and nothing between there and here re-sorts.
        """
        return cls(
            items=[TaskResponse.from_result(item) for item in result.items],
            total_tasks=result.total_tasks,
            completed_tasks=result.completed_tasks,
            completion_percentage=result.completion_percentage,
        )
