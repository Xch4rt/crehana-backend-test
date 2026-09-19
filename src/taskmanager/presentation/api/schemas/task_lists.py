"""The task-list HTTP boundary: what a client may send, and what it gets back.

Three rules shape every model in this package, and each is a thing that is
deliberately **absent** rather than a thing that is present.

No length constraint is declared here. `TaskList` owns its two limits as
ClassVars and `domain/validation.py` applies them, which is Phase 2 D-04: a
business limit exists in exactly one place. A second copy in Pydantic would be
the one a client hits, it would drift the first time the entity's changed, and
it would answer with the request-validation error shape instead of the domain's.

The application layer's "field not provided" marker never appears in a field
annotation or a field default. Declaring it was executed and measured
(04-RESEARCH Pattern 2): it publishes an extra component into `/openapi.json` as
part of the field's `anyOf`, and it splits the explicit-null refusal into two
error entries that no client can act on. The boundary therefore speaks plain
`X | None = None`, and `to_command` is the single place the marker is produced.

The instance attribute that lists a model's fields is never read. Pydantic
deprecated it in 2.11, and `pytest.ini` sets `filterwarnings = error`, so
reading it off an instance raises rather than warns. `model_fields_set` - a
different attribute with a different meaning - is the one this module uses, and
it is read off the instance exactly as intended.

The response model copies its result field by field in a classmethod rather than
calling `model_validate` on the DTO. Validation from attributes works on the
pinned stack; it was rejected for the reason `TaskResult.from_entity` gives
about `asdict`. It would silently publish a result field the moment someone
declared one, and silently ignore one this model forgot - which re-opens exactly
the automatic-leak hole the result DTOs exist to close.
"""

from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from taskmanager.application.dto.commands import (
    CreateTaskListCommand,
    UpdateTaskListCommand,
)
from taskmanager.application.dto.results import TaskListResult
from taskmanager.application.dto.unset import UNSET

# D-05's refusal message for an explicit null on a field that has no null, and
# D-06's for a body that asks for nothing. Constants so the tests assert the
# string the client actually receives rather than a copy of it.
NULL_REJECTED_MESSAGE = "this field may not be null"
EMPTY_PATCH_MESSAGE = "at least one field must be provided"


class TaskListCreateRequest(BaseModel):
    """`POST /task-lists`: a name, and optionally a description.

    `owner_id` is not a field and never will be. The owner is the caller, which
    the router takes from `CurrentActor` and passes to `to_command` as a keyword
    - so a client cannot create a list in someone else's name by adding a key to
    the body, and `extra="forbid"` turns the attempt into a 422 (T-4-35/T-4-36).
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str | None = None

    def to_command(self, *, actor_id: UUID) -> CreateTaskListCommand:
        """Bind the body to the caller the router resolved."""
        return CreateTaskListCommand(
            actor_id=actor_id,
            name=self.name,
            description=self.description,
        )


class TaskListPatchRequest(BaseModel):
    """`PATCH /task-lists/{id}`: RFC 7396 merge-patch semantics (D-05, D-06).

    Omitting a field leaves it alone; sending an explicit null clears the one
    field that has a null to be cleared to. `name` has none, so a null there is
    a field-level 422 rather than a silently ignored key.
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    description: str | None = None

    @field_validator("name")
    @classmethod
    def _reject_explicit_null(cls, value: str | None) -> str | None:
        """D-05's explicit-null leg, and nothing else.

        Pydantic skips a field validator for a field the client did not send,
        because defaults are not validated unless a model asks for it. So this
        runs only against a value that was actually in the JSON body, which is
        what makes "absent" and "null" two different outcomes here rather than
        one.
        """
        if value is None:
            raise ValueError(NULL_REJECTED_MESSAGE)
        return value

    @model_validator(mode="after")
    def _require_at_least_one_field(self) -> Self:
        """D-06: an empty body, or one holding only defaults, asks for nothing.

        Refusing it here rather than in the use case is what keeps `updated_at`
        honest: with no empty request possible, "a field was provided" and "a
        write was asked for" are the same statement (04-RESEARCH Pitfall 10).
        """
        if not self.model_fields_set:
            raise ValueError(EMPTY_PATCH_MESSAGE)
        return self

    def to_command(
        self, *, actor_id: UUID, task_list_id: UUID
    ) -> UpdateTaskListCommand:
        """Turn "the client sent this field" into the application's marker.

        The two fields are read differently on purpose. `description` accepts a
        null as a *value*, so absence can only be told from emptiness by asking
        whether the client sent the key at all. `name` does not: the validator
        above has already refused an explicit null, so at this point a `None`
        can only mean the field was omitted, and the two tests are the same
        question. Asking it as `is not None` is also the form the type checker
        can narrow - a membership test leaves the value optional, and the
        command's field is not.
        """
        sent = self.model_fields_set
        return UpdateTaskListCommand(
            actor_id=actor_id,
            task_list_id=task_list_id,
            name=self.name if self.name is not None else UNSET,
            description=self.description if "description" in sent else UNSET,
        )


class TaskListResponse(BaseModel):
    """The one task-list shape, on every verb that returns a list (D-10).

    Member order is contract, not decoration: Pydantic serialises in declaration
    order, so the nine names below are declared in the order D-10 writes them -
    the identity of the list, then its text, then its timestamps, then the three
    completion counters that every task-list answer carries.

    The counters always describe the **whole** list. Nothing here is ever
    computed over a filtered view (ADR-009).
    """

    id: UUID
    owner_id: UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime
    total_tasks: int
    completed_tasks: int
    completion_percentage: float

    @classmethod
    def from_result(cls, result: TaskListResult) -> "TaskListResponse":
        """Copy every field of the result, naming each one explicitly."""
        return cls(
            id=result.id,
            owner_id=result.owner_id,
            name=result.name,
            description=result.description,
            created_at=result.created_at,
            updated_at=result.updated_at,
            total_tasks=result.total_tasks,
            completed_tasks=result.completed_tasks,
            completion_percentage=result.completion_percentage,
        )
