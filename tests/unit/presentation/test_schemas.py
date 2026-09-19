"""The Pydantic boundary: every PATCH leg, and every promise about field lists.

Two kinds of assertion here look like ceremony and are not.

The first reads `set(Model.model_fields)` off the **class** and compares it to a
literal. The schema-to-command mappers ask "did the client send this field?"
with a string, and mypy cannot check a string against a model's field list: a
mapper that asked for `nmae` would compile, type-check, lint, and silently never
update the field (04-RESEARCH Pitfall 7). A field-set assertion plus the three
legs per field is the only thing that catches that class of bug, so it is owed
per model rather than written once.

The second asserts declaration **order** on the response models. Pydantic
serialises in declaration order, so the order is the wire contract D-09 and D-10
describe; a reordering is a silent API change that no other gate would see.

The field list is read off the class throughout. The instance attribute of the
same name was deprecated in Pydantic 2.11, and `filterwarnings = error` turns
reading it into a failure rather than a warning.
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import BaseModel, ValidationError

from taskmanager.application.dto.results import TaskListResult
from taskmanager.application.dto.unset import UNSET
from taskmanager.presentation.api.schemas.task_lists import (
    TaskListCreateRequest,
    TaskListPatchRequest,
    TaskListResponse,
)

# Fixed identifiers and instants: a generated value makes an assertion
# unfalsifiable, and the project uses literals everywhere for that reason.
ACTOR_ID = UUID("00000000-0000-4000-8000-0000000000a1")
LIST_ID = UUID("00000000-0000-4000-8000-0000000000b1")
CREATED_AT = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
UPDATED_AT = datetime(2026, 1, 2, 12, 0, tzinfo=UTC)

NAME = "Groceries"
DESCRIPTION = "Everything for the week"

# D-10's nine members, in the order the wire contract promises.
TASK_LIST_RESPONSE_MEMBERS = [
    "id",
    "owner_id",
    "name",
    "description",
    "created_at",
    "updated_at",
    "total_tasks",
    "completed_tasks",
    "completion_percentage",
]


def _patch(**body: object) -> TaskListPatchRequest:
    """Validate a body the way FastAPI will, so omission means omission.

    Built through `model_validate` rather than by keyword, because a keyword
    call with an explicit `None` and an omitted argument are distinguishable
    only if every case goes through the same door - and it is the JSON body
    that this model exists to interpret.
    """
    return TaskListPatchRequest.model_validate(body)


def _declares_no_length_limit(model: type[BaseModel]) -> bool:
    """True when no field of the model carries a length constraint.

    Phase 2 D-04 says a business limit lives in the entity and nowhere else.
    This inspects the constraint metadata Pydantic attaches to a field rather
    than scanning the source, so an equivalent constraint spelled a different
    way is caught too.
    """
    return all(
        getattr(constraint, "max_length", None) is None
        and getattr(constraint, "min_length", None) is None
        for field in model.model_fields.values()
        for constraint in field.metadata
    )


# ---------------------------------------------------------------------------
# TaskListCreateRequest
# ---------------------------------------------------------------------------


def test_a_list_can_be_created_with_a_name_alone() -> None:
    """The description is optional, and its absence is not an error."""
    request = TaskListCreateRequest.model_validate({"name": NAME})

    assert request.name == NAME
    assert request.description is None


def test_the_create_request_refuses_an_unknown_key() -> None:
    """`extra="forbid"`: a typo is refused, never silently dropped (D-06)."""
    with pytest.raises(ValidationError) as caught:
        TaskListCreateRequest.model_validate({"name": NAME, "owner_id": str(ACTOR_ID)})

    error = caught.value.errors()[0]

    assert error["type"] == "extra_forbidden"
    assert error["loc"] == ("owner_id",)


def test_the_create_command_binds_the_body_to_the_caller() -> None:
    """The actor arrives as a keyword from the router, never from the body."""
    request = TaskListCreateRequest.model_validate(
        {"name": NAME, "description": DESCRIPTION}
    )

    command = request.to_command(actor_id=ACTOR_ID)

    assert command.actor_id == ACTOR_ID
    assert command.name == NAME
    assert command.description == DESCRIPTION


# ---------------------------------------------------------------------------
# TaskListPatchRequest
# ---------------------------------------------------------------------------


def test_the_patch_schema_declares_exactly_the_two_patchable_fields() -> None:
    """The mapper's strings are only ever as right as this assertion."""
    assert set(TaskListPatchRequest.model_fields) == {"name", "description"}


def test_an_omitted_name_leaves_the_name_alone() -> None:
    command = _patch(description=DESCRIPTION).to_command(
        actor_id=ACTOR_ID, task_list_id=LIST_ID
    )

    assert command.name is UNSET


def test_a_provided_name_reaches_the_command() -> None:
    command = _patch(name=NAME).to_command(actor_id=ACTOR_ID, task_list_id=LIST_ID)

    assert command.name == NAME


def test_an_explicitly_null_name_is_refused() -> None:
    """D-05: `name` has no null to be cleared to, so this is a 422."""
    with pytest.raises(ValidationError) as caught:
        _patch(name=None)

    error = caught.value.errors()[0]

    assert error["type"] == "value_error"
    assert error["loc"] == ("name",)
    assert "may not be null" in str(caught.value)


def test_an_omitted_description_leaves_the_description_alone() -> None:
    command = _patch(name=NAME).to_command(actor_id=ACTOR_ID, task_list_id=LIST_ID)

    assert command.description is UNSET


def test_a_provided_description_reaches_the_command() -> None:
    command = _patch(description=DESCRIPTION).to_command(
        actor_id=ACTOR_ID, task_list_id=LIST_ID
    )

    assert command.description == DESCRIPTION


def test_an_explicitly_null_description_clears_it() -> None:
    """D-05's other leg: a null on a nullable field is how a client empties it.

    The distinction from the test above is the whole reason the application
    layer has a marker at all: both requests carry `None` on this field, and
    they mean different things.
    """
    command = _patch(description=None).to_command(
        actor_id=ACTOR_ID, task_list_id=LIST_ID
    )

    assert command.description is None
    assert command.name is UNSET


def test_an_empty_patch_body_is_refused() -> None:
    """D-06: a body that asks for nothing is a 422, not a successful no-op."""
    with pytest.raises(ValidationError) as caught:
        _patch()

    error = caught.value.errors()[0]

    assert error["type"] == "value_error"
    assert "at least one field" in str(caught.value)


def test_the_patch_request_refuses_an_unknown_key() -> None:
    """A misspelt field is refused at the key, naming the key (D-06)."""
    with pytest.raises(ValidationError) as caught:
        _patch(nmae=NAME)

    error = caught.value.errors()[0]

    assert error["type"] == "extra_forbidden"
    assert error["loc"] == ("nmae",)


def test_the_patch_command_carries_the_identifiers_it_was_handed() -> None:
    """Neither identifier is a body field; both arrive from the router."""
    command = _patch(name=NAME).to_command(actor_id=ACTOR_ID, task_list_id=LIST_ID)

    assert command.actor_id == ACTOR_ID
    assert command.task_list_id == LIST_ID


# ---------------------------------------------------------------------------
# TaskListResponse
# ---------------------------------------------------------------------------


def test_the_list_response_copies_every_field_of_its_result() -> None:
    """Field by field, so a forgotten member fails here rather than on the wire."""
    result = _task_list_result()

    response = TaskListResponse.from_result(result)

    assert response.id == result.id
    assert response.owner_id == result.owner_id
    assert response.name == result.name
    assert response.description == result.description
    assert response.created_at == result.created_at
    assert response.updated_at == result.updated_at
    assert response.total_tasks == result.total_tasks
    assert response.completed_tasks == result.completed_tasks
    assert response.completion_percentage == result.completion_percentage


def test_the_list_response_declares_d_10_s_members_in_order() -> None:
    """Declaration order is serialisation order, and therefore the contract."""
    assert list(TaskListResponse.model_fields) == TASK_LIST_RESPONSE_MEMBERS


def test_no_task_list_request_repeats_a_business_limit() -> None:
    """Phase 2 D-04, enforced rather than remembered."""
    assert _declares_no_length_limit(TaskListCreateRequest)
    assert _declares_no_length_limit(TaskListPatchRequest)


def _task_list_result() -> TaskListResult:
    """A fully populated result, with no field left at its type's zero value.

    Every number differs from every other, so a mapper that crossed two fields
    is caught by the copy test above instead of passing on equal values.
    """
    return TaskListResult(
        id=LIST_ID,
        owner_id=ACTOR_ID,
        name=NAME,
        description=DESCRIPTION,
        created_at=CREATED_AT,
        updated_at=UPDATED_AT,
        total_tasks=4,
        completed_tasks=3,
        completion_percentage=75.0,
    )
