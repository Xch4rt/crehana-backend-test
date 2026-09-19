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

from taskmanager.application.dto.results import (
    AccessTokenResult,
    TaskCollectionResult,
    TaskListResult,
    TaskResult,
    UserResult,
)
from taskmanager.application.dto.unset import UNSET
from taskmanager.domain.entities.task import Task
from taskmanager.domain.value_objects.task_priority import TaskPriority
from taskmanager.domain.value_objects.task_status import TaskStatus
from taskmanager.presentation.api.schemas.auth import (
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from taskmanager.presentation.api.schemas.task_lists import (
    TaskListCreateRequest,
    TaskListPatchRequest,
    TaskListResponse,
)
from taskmanager.presentation.api.schemas.tasks import (
    TaskAssigneeRequest,
    TaskCollectionResponse,
    TaskCreateRequest,
    TaskPatchRequest,
    TaskResponse,
    TaskStatusChangeRequest,
)
from taskmanager.presentation.api.schemas.users import UserSummaryResponse

# Fixed identifiers and instants: a generated value makes an assertion
# unfalsifiable, and the project uses literals everywhere for that reason.
ACTOR_ID = UUID("00000000-0000-4000-8000-0000000000a1")
LIST_ID = UUID("00000000-0000-4000-8000-0000000000b1")
TASK_ID = UUID("00000000-0000-4000-8000-0000000000c1")
OTHER_TASK_ID = UUID("00000000-0000-4000-8000-0000000000c2")
ASSIGNEE_ID = UUID("00000000-0000-4000-8000-0000000000d1")
CREATED_AT = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
UPDATED_AT = datetime(2026, 1, 2, 12, 0, tzinfo=UTC)
DUE_AT = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
COMPLETED_AT = datetime(2026, 1, 3, 12, 0, tzinfo=UTC)

USER_ID = UUID("00000000-0000-4000-8000-0000000000e1")

NAME = "Groceries"
DESCRIPTION = "Everything for the week"
TITLE = "Buy oat milk"

EMAIL = "ada@example.com"
FULL_NAME = "Ada Lovelace"
PASSWORD = "a-perfectly-ordinary-passphrase"
# Seven characters: one short of the domain's minimum, which is exactly why the
# boundary must still accept it (CONTEXT D-10, Phase 2 D-04).
SHORT_PASSWORD = "sevench"
ACCESS_TOKEN = "header.payload.signature"

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

# `TaskResult`'s eleven members, in the order the result DTO declares them.
TASK_RESPONSE_MEMBERS = [
    "id",
    "task_list_id",
    "title",
    "description",
    "status",
    "priority",
    "created_at",
    "updated_at",
    "due_date",
    "completed_at",
    "assignee_id",
]

# D-09's envelope: exactly these four, in this order, and nothing else.
TASK_COLLECTION_MEMBERS = [
    "items",
    "total_tasks",
    "completed_tasks",
    "completion_percentage",
]

# AUTH-01 and AUTH-05's profile, in `UserResult`'s order. The list is the whole
# assertion: a fifth member - the stored hash above all - fails it, and so does
# a rename, which a per-key absence check would let through (T-5-08).
USER_RESPONSE_MEMBERS = ["id", "email", "full_name", "created_at"]

# AUTH-02's answer to a login, in `AccessTokenResult`'s order.
TOKEN_RESPONSE_MEMBERS = ["access_token", "token_type", "expires_in"]

# ASGN-03's literal wording - "id, name, email" - and therefore its order,
# which is deliberately not the profile's above.
USER_SUMMARY_MEMBERS = ["id", "full_name", "email"]


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


# ---------------------------------------------------------------------------
# TaskCreateRequest
# ---------------------------------------------------------------------------


def _task_patch(**body: object) -> TaskPatchRequest:
    """Validate a task patch body the way FastAPI will (see `_patch` above)."""
    return TaskPatchRequest.model_validate(body)


def _task_result(task_id: UUID = TASK_ID) -> TaskResult:
    """A fully populated task result: no field left at its type's zero value."""
    return TaskResult(
        id=task_id,
        task_list_id=LIST_ID,
        title=TITLE,
        description=DESCRIPTION,
        status=TaskStatus.IN_PROGRESS,
        priority=TaskPriority.HIGH,
        created_at=CREATED_AT,
        updated_at=UPDATED_AT,
        due_date=DUE_AT,
        completed_at=COMPLETED_AT,
        assignee_id=ASSIGNEE_ID,
    )


def test_a_task_can_be_created_with_a_title_alone() -> None:
    """The other three fields are optional, and their absence is not an error."""
    request = TaskCreateRequest.model_validate({"title": TITLE})

    assert request.title == TITLE
    assert request.description is None
    assert request.due_date is None


def test_a_created_task_takes_the_entity_s_default_priority() -> None:
    """TASK-01's `medium` is read from the entity, so the two cannot drift.

    Asserted by identity against the ClassVar rather than against the literal:
    a test that spelled the value would become a third copy of the rule it is
    meant to protect.
    """
    command = TaskCreateRequest.model_validate({"title": TITLE}).to_command(
        actor_id=ACTOR_ID, task_list_id=LIST_ID
    )

    assert command.priority is Task.DEFAULT_PRIORITY


def test_the_create_command_carries_every_field_it_was_given() -> None:
    request = TaskCreateRequest.model_validate(
        {
            "title": TITLE,
            "description": DESCRIPTION,
            "priority": "high",
            "due_date": DUE_AT.isoformat(),
        }
    )

    command = request.to_command(actor_id=ACTOR_ID, task_list_id=LIST_ID)

    assert command.actor_id == ACTOR_ID
    assert command.task_list_id == LIST_ID
    assert command.title == TITLE
    assert command.description == DESCRIPTION
    assert command.priority is TaskPriority.HIGH
    assert command.due_date == DUE_AT


def test_the_task_create_request_refuses_an_unknown_key() -> None:
    """Including `status`: a new task's state is the entity's to decide."""
    with pytest.raises(ValidationError) as caught:
        TaskCreateRequest.model_validate({"title": TITLE, "status": "completed"})

    error = caught.value.errors()[0]

    assert error["type"] == "extra_forbidden"
    assert error["loc"] == ("status",)


def test_an_unknown_priority_is_refused_by_the_enum() -> None:
    """TASK-06 at the body level: the enum is the check, so none is written.

    An invalid value is a 422 before any use case runs, which is also what
    stops a filter or a priority ever reaching SQL as free text (T-4-39).
    """
    with pytest.raises(ValidationError) as caught:
        TaskCreateRequest.model_validate({"title": TITLE, "priority": "urgent"})

    assert caught.value.errors()[0]["loc"] == ("priority",)


# ---------------------------------------------------------------------------
# TaskPatchRequest
# ---------------------------------------------------------------------------


def test_the_task_patch_schema_declares_exactly_the_four_patchable_fields() -> None:
    """The mapper's strings are only ever as right as this assertion."""
    assert set(TaskPatchRequest.model_fields) == {
        "title",
        "description",
        "priority",
        "due_date",
    }


def test_status_is_not_a_field_of_the_task_patch_schema() -> None:
    """D-08 and TASK-03, asserted by name as well as by the set above.

    Named separately because the set assertion would still pass if both it and
    the model gained `status` in the same edit; this one fails on the model
    change alone.
    """
    assert "status" not in TaskPatchRequest.model_fields


def test_sending_a_status_to_the_generic_patch_is_refused_at_that_key() -> None:
    """The proof D-08 asks for: one request, one 422, naming `status`."""
    with pytest.raises(ValidationError) as caught:
        _task_patch(status="completed")

    errors = caught.value.errors()

    assert len(errors) == 1
    assert errors[0]["type"] == "extra_forbidden"
    assert errors[0]["loc"] == ("status",)


def test_an_omitted_task_title_leaves_the_title_alone() -> None:
    command = _task_patch(description=DESCRIPTION).to_command(
        actor_id=ACTOR_ID, task_list_id=LIST_ID, task_id=TASK_ID
    )

    assert command.title is UNSET


def test_a_provided_task_title_reaches_the_command() -> None:
    command = _task_patch(title=TITLE).to_command(
        actor_id=ACTOR_ID, task_list_id=LIST_ID, task_id=TASK_ID
    )

    assert command.title == TITLE


def test_an_explicitly_null_task_title_is_refused() -> None:
    with pytest.raises(ValidationError) as caught:
        _task_patch(title=None)

    error = caught.value.errors()[0]

    assert error["type"] == "value_error"
    assert error["loc"] == ("title",)


def test_an_omitted_task_description_leaves_the_description_alone() -> None:
    command = _task_patch(title=TITLE).to_command(
        actor_id=ACTOR_ID, task_list_id=LIST_ID, task_id=TASK_ID
    )

    assert command.description is UNSET


def test_a_provided_task_description_reaches_the_command() -> None:
    command = _task_patch(description=DESCRIPTION).to_command(
        actor_id=ACTOR_ID, task_list_id=LIST_ID, task_id=TASK_ID
    )

    assert command.description == DESCRIPTION


def test_an_explicitly_null_task_description_clears_it() -> None:
    command = _task_patch(description=None).to_command(
        actor_id=ACTOR_ID, task_list_id=LIST_ID, task_id=TASK_ID
    )

    assert command.description is None


def test_an_omitted_priority_leaves_the_priority_alone() -> None:
    command = _task_patch(title=TITLE).to_command(
        actor_id=ACTOR_ID, task_list_id=LIST_ID, task_id=TASK_ID
    )

    assert command.priority is UNSET


def test_a_provided_priority_reaches_the_command() -> None:
    command = _task_patch(priority="low").to_command(
        actor_id=ACTOR_ID, task_list_id=LIST_ID, task_id=TASK_ID
    )

    assert command.priority is TaskPriority.LOW


def test_an_explicitly_null_priority_is_refused() -> None:
    """A task always has a priority, so there is no null to clear it to."""
    with pytest.raises(ValidationError) as caught:
        _task_patch(priority=None)

    error = caught.value.errors()[0]

    assert error["type"] == "value_error"
    assert error["loc"] == ("priority",)


def test_an_omitted_due_date_leaves_the_due_date_alone() -> None:
    """D-07: a patch that does not mention the deadline never re-checks it."""
    command = _task_patch(title=TITLE).to_command(
        actor_id=ACTOR_ID, task_list_id=LIST_ID, task_id=TASK_ID
    )

    assert command.due_date is UNSET


def test_a_provided_due_date_reaches_the_command() -> None:
    command = _task_patch(due_date=DUE_AT.isoformat()).to_command(
        actor_id=ACTOR_ID, task_list_id=LIST_ID, task_id=TASK_ID
    )

    assert command.due_date == DUE_AT


def test_an_explicitly_null_due_date_clears_it() -> None:
    """A deadline can be removed, which is why this leg is not the title's."""
    command = _task_patch(due_date=None).to_command(
        actor_id=ACTOR_ID, task_list_id=LIST_ID, task_id=TASK_ID
    )

    assert command.due_date is None


def test_an_empty_task_patch_body_is_refused() -> None:
    with pytest.raises(ValidationError) as caught:
        _task_patch()

    assert caught.value.errors()[0]["type"] == "value_error"
    assert "at least one field" in str(caught.value)


def test_the_task_patch_request_refuses_an_unknown_key() -> None:
    with pytest.raises(ValidationError) as caught:
        _task_patch(titel=TITLE)

    error = caught.value.errors()[0]

    assert error["type"] == "extra_forbidden"
    assert error["loc"] == ("titel",)


def test_the_task_patch_command_carries_the_identifiers_it_was_handed() -> None:
    command = _task_patch(title=TITLE).to_command(
        actor_id=ACTOR_ID, task_list_id=LIST_ID, task_id=TASK_ID
    )

    assert command.actor_id == ACTOR_ID
    assert command.task_list_id == LIST_ID
    assert command.task_id == TASK_ID


def test_no_task_request_repeats_a_business_limit() -> None:
    """Phase 2 D-04 again, for the three task request models."""
    assert _declares_no_length_limit(TaskCreateRequest)
    assert _declares_no_length_limit(TaskPatchRequest)
    assert _declares_no_length_limit(TaskStatusChangeRequest)


# ---------------------------------------------------------------------------
# TaskStatusChangeRequest
# ---------------------------------------------------------------------------


def test_the_status_request_builds_the_change_command() -> None:
    """D-11: the addressed list travels with the request the use case checks."""
    request = TaskStatusChangeRequest.model_validate({"status": "completed"})

    command = request.to_command(
        actor_id=ACTOR_ID, task_list_id=LIST_ID, task_id=TASK_ID
    )

    assert command.actor_id == ACTOR_ID
    assert command.task_list_id == LIST_ID
    assert command.task_id == TASK_ID
    assert command.new_status is TaskStatus.COMPLETED


def test_the_status_request_refuses_an_empty_body() -> None:
    """The field is required, so absence is a `missing` at that key."""
    with pytest.raises(ValidationError) as caught:
        TaskStatusChangeRequest.model_validate({})

    error = caught.value.errors()[0]

    assert error["type"] == "missing"
    assert error["loc"] == ("status",)


def test_the_status_request_refuses_an_unknown_key() -> None:
    with pytest.raises(ValidationError) as caught:
        TaskStatusChangeRequest.model_validate({"status": "completed", "title": TITLE})

    error = caught.value.errors()[0]

    assert error["type"] == "extra_forbidden"
    assert error["loc"] == ("title",)


def test_an_unknown_status_is_refused_by_the_enum() -> None:
    """`cancelled` is out of scope by requirement, and this is where it stops."""
    with pytest.raises(ValidationError) as caught:
        TaskStatusChangeRequest.model_validate({"status": "cancelled"})

    assert caught.value.errors()[0]["loc"] == ("status",)


# ---------------------------------------------------------------------------
# TaskResponse and TaskCollectionResponse
# ---------------------------------------------------------------------------


def test_the_task_response_copies_every_field_of_its_result() -> None:
    result = _task_result()

    response = TaskResponse.from_result(result)

    assert response.id == result.id
    assert response.task_list_id == result.task_list_id
    assert response.title == result.title
    assert response.description == result.description
    assert response.status == result.status
    assert response.priority == result.priority
    assert response.created_at == result.created_at
    assert response.updated_at == result.updated_at
    assert response.due_date == result.due_date
    assert response.completed_at == result.completed_at
    assert response.assignee_id == result.assignee_id


def test_the_task_response_declares_its_eleven_members_in_order() -> None:
    assert list(TaskResponse.model_fields) == TASK_RESPONSE_MEMBERS


def test_the_collection_preserves_item_order_and_copies_the_statistics() -> None:
    """D-09: the counters are the list's, the items are the caller's view.

    The two items are given distinguishable identifiers, and the counters are
    given values that do not match the number of items - a collection of two
    reporting four - so a mapper that derived the statistics from `items`
    rather than copying them fails here.
    """
    result = TaskCollectionResult(
        items=(_task_result(), _task_result(OTHER_TASK_ID)),
        total_tasks=4,
        completed_tasks=3,
        completion_percentage=75.0,
    )

    response = TaskCollectionResponse.from_result(result)

    assert [item.id for item in response.items] == [TASK_ID, OTHER_TASK_ID]
    assert response.total_tasks == 4
    assert response.completed_tasks == 3
    assert response.completion_percentage == 75.0


def test_an_empty_collection_serialises_an_empty_array_and_zero_percent() -> None:
    """The empty list is an answer, never a division and never a null."""
    result = TaskCollectionResult(
        items=(), total_tasks=0, completed_tasks=0, completion_percentage=0.0
    )

    body = TaskCollectionResponse.from_result(result).model_dump()

    assert body["items"] == []
    assert body["completion_percentage"] == 0.0


def test_the_collection_declares_d_09_s_four_members_in_order() -> None:
    """Exactly four, and no echoed identifier, page count or filter."""
    assert list(TaskCollectionResponse.model_fields) == TASK_COLLECTION_MEMBERS


# ---------------------------------------------------------------------------
# RegisterRequest
# ---------------------------------------------------------------------------


def _register(**body: object) -> RegisterRequest:
    """Validate a register body the way FastAPI will (see `_patch` above)."""
    return RegisterRequest.model_validate(body)


def _user_result() -> UserResult:
    """One profile, with every field distinct from every other."""
    return UserResult(
        id=USER_ID,
        email=EMAIL,
        full_name=FULL_NAME,
        created_at=CREATED_AT,
    )


def test_the_register_request_hands_the_application_layer_a_plain_string() -> None:
    """Pitfall 7: the secret wrapper stops at the boundary, by one call.

    `RegisterUserCommand.password` is typed `str`, and the type checker cannot
    see the difference at runtime - so the assertion is about the object, not
    about the annotation: a schema that forwarded `self.password` would hand
    the application layer a Pydantic type and nothing would fail but this.
    """
    command = _register(
        email=EMAIL, full_name=FULL_NAME, password=PASSWORD
    ).to_command()

    assert command.email == EMAIL
    assert command.full_name == FULL_NAME
    assert command.password == PASSWORD
    assert type(command.password) is str


def test_the_register_request_refuses_an_unknown_key() -> None:
    """T-5-09: the register body is the whole surface an attacker can reach.

    Exactly one error, at the offending key: a model that declared a role and
    then refused it would fail this assertion too, which a bare "it raised"
    check would not.
    """
    with pytest.raises(ValidationError) as caught:
        _register(email=EMAIL, full_name=FULL_NAME, password=PASSWORD, is_admin=True)

    errors = caught.value.errors()

    assert len(errors) == 1
    assert errors[0]["type"] == "extra_forbidden"
    assert errors[0]["loc"] == ("is_admin",)


def test_a_malformed_email_is_refused_at_the_email_key() -> None:
    """Format is the boundary's rule, and the entity deliberately re-checks none."""
    with pytest.raises(ValidationError) as caught:
        _register(email="not-an-address", full_name=FULL_NAME, password=PASSWORD)

    error = caught.value.errors()[0]

    assert error["type"] == "value_error"
    assert error["loc"] == ("email",)


def test_a_seven_character_password_is_accepted_by_the_boundary() -> None:
    """D-10 lives in the domain, so the schema declares no minimum at all.

    The password is short enough that `require_password` refuses it, and the
    point of the test is that it gets that far: a `min_length` here would be
    the second copy of the rule, answering with the request-validation error
    shape instead of the domain's (Phase 2 D-04).
    """
    request = _register(email=EMAIL, full_name=FULL_NAME, password=SHORT_PASSWORD)

    assert request.to_command().password == SHORT_PASSWORD


def test_the_register_request_masks_the_password_wherever_pydantic_prints_it() -> None:
    """T-5-04: `repr` and a serialised body are two separate ways out.

    A router that logged the model, or a traceback that rendered it, is the
    accident this type exists for - the value is only ever unwrapped by the one
    call in `to_command`.
    """
    request = _register(email=EMAIL, full_name=FULL_NAME, password=PASSWORD)

    assert PASSWORD not in repr(request)
    assert PASSWORD not in str(request)
    assert PASSWORD not in request.model_dump_json()
    assert PASSWORD not in str(request.model_dump())


def test_no_auth_request_repeats_a_business_limit() -> None:
    """Phase 2 D-04 once more, for the one request model this module adds."""
    assert _declares_no_length_limit(RegisterRequest)


# ---------------------------------------------------------------------------
# UserResponse and TokenResponse
# ---------------------------------------------------------------------------


def test_the_user_response_copies_every_field_of_its_result() -> None:
    """Field by field, so a forgotten member fails here rather than on the wire."""
    result = _user_result()

    response = UserResponse.from_result(result)

    assert response.id == result.id
    assert response.email == result.email
    assert response.full_name == result.full_name
    assert response.created_at == result.created_at


def test_the_user_response_publishes_the_profile_s_four_members_in_order() -> None:
    """The serialised body is the contract, and the hash is not in it (T-5-08)."""
    body = UserResponse.from_result(_user_result()).model_dump()

    assert list(body) == USER_RESPONSE_MEMBERS
    assert list(UserResponse.model_fields) == USER_RESPONSE_MEMBERS


def test_the_token_response_copies_the_three_members_of_its_result() -> None:
    """AUTH-02: the token, the lowercase scheme and the lifetime in seconds."""
    result = AccessTokenResult(
        access_token=ACCESS_TOKEN, token_type="bearer", expires_in=1800
    )

    response = TokenResponse.from_result(result)

    assert response.access_token == ACCESS_TOKEN
    assert response.token_type == "bearer"
    assert response.expires_in == 1800
    assert list(response.model_dump()) == TOKEN_RESPONSE_MEMBERS


# ---------------------------------------------------------------------------
# TaskAssigneeRequest
# ---------------------------------------------------------------------------


def test_the_assignee_request_builds_the_assign_command() -> None:
    """D-05's door: the body names the assignee, the path names everything else.

    All four identifiers are asserted, because `actor_id` and `assignee_id`
    are the two that must never be confused - one is the authenticated caller
    and the other is attacker-controlled input (T-5-12).
    """
    request = TaskAssigneeRequest.model_validate({"assignee_id": str(ASSIGNEE_ID)})

    command = request.to_command(
        actor_id=ACTOR_ID, task_list_id=LIST_ID, task_id=TASK_ID
    )

    assert command.actor_id == ACTOR_ID
    assert command.task_list_id == LIST_ID
    assert command.task_id == TASK_ID
    assert command.assignee_id == ASSIGNEE_ID


def test_the_assignee_request_refuses_an_empty_body() -> None:
    """The field is required, so absence is a `missing` at that key."""
    with pytest.raises(ValidationError) as caught:
        TaskAssigneeRequest.model_validate({})

    error = caught.value.errors()[0]

    assert error["type"] == "missing"
    assert error["loc"] == ("assignee_id",)


def test_an_assignee_that_is_not_an_identifier_is_refused_by_the_type() -> None:
    """The annotation is the check, so no parsing is written anywhere.

    A value that is not an identifier is a 422 before any use case runs, which
    is also what stops it reaching SQL as free text.
    """
    with pytest.raises(ValidationError) as caught:
        TaskAssigneeRequest.model_validate({"assignee_id": "somebody"})

    error = caught.value.errors()[0]

    assert error["type"] == "uuid_parsing"
    assert error["loc"] == ("assignee_id",)


def test_the_assignee_request_refuses_an_unknown_key() -> None:
    """One key and one only: the door decides nothing else about the request."""
    with pytest.raises(ValidationError) as caught:
        TaskAssigneeRequest.model_validate(
            {"assignee_id": str(ASSIGNEE_ID), "notify": True}
        )

    errors = caught.value.errors()

    assert len(errors) == 1
    assert errors[0]["type"] == "extra_forbidden"
    assert errors[0]["loc"] == ("notify",)


# ---------------------------------------------------------------------------
# UserSummaryResponse
# ---------------------------------------------------------------------------


def test_the_user_summary_publishes_asgn_03_s_three_members_in_its_order() -> None:
    """ASGN-03 says "id, name, email", and the order is the contract.

    Deliberately not the profile's order, and deliberately not the profile's
    model: the directory and the profile answer different questions, and a
    shared model would make one contract move whenever the other's did.
    """
    result = _user_result()

    body = UserSummaryResponse.from_result(result).model_dump()

    assert list(body) == USER_SUMMARY_MEMBERS
    assert body["id"] == result.id
    assert body["full_name"] == result.full_name
    assert body["email"] == result.email


def test_the_user_summary_publishes_nothing_the_directory_was_not_asked_for() -> None:
    """The member list is the assertion; these two names make it legible.

    `created_at` is absent because ASGN-03 does not ask for it and a field
    published once has to keep being published; the stored hash is absent for
    the reason `UserResult` exists at all (T-5-08).
    """
    assert list(UserSummaryResponse.model_fields) == USER_SUMMARY_MEMBERS


# ---------------------------------------------------------------------------
# What the two existing task doors refuse by having no field for it
# ---------------------------------------------------------------------------

# Each row is a key an existing task body must never accept, and each is proven
# by **absence**: the model does not declare the field, and `extra="forbid"`
# turns sending it into one 422 naming it. `assignee_id` on create is D-06 (a
# task cannot be created already assigned, and one use case notifies, not two);
# `assignee_id` on the generic patch is T-5-10 (the patch stays free of side
# effects, and D-05 gives assignment its own door); `status` on the generic
# patch is D-08, re-asserted here because this phase touched the module that
# declares both patch models.
FORBIDDEN_TASK_BODY_KEYS = [
    pytest.param(TaskCreateRequest, "assignee_id", id="create-assignee_id"),
    pytest.param(TaskPatchRequest, "assignee_id", id="patch-assignee_id"),
    pytest.param(TaskPatchRequest, "status", id="patch-status"),
]

FORBIDDEN_KEY_VALUES: dict[str, object] = {
    "assignee_id": str(ASSIGNEE_ID),
    "status": "completed",
}


@pytest.mark.parametrize(("model", "key"), FORBIDDEN_TASK_BODY_KEYS)
def test_an_existing_task_door_refuses_a_key_it_declares_no_field_for(
    model: type[BaseModel], key: str
) -> None:
    """Exactly one error, at the key - and the count is the load-bearing part.

    A model that declared the field and then refused it in a validator would
    fail this assertion, because the refusal would arrive as a `value_error`
    at a field that exists; a bare "it raised" check would pass against that
    model and against a model that had quietly started accepting the key and
    tripped over something else in the body.
    """
    with pytest.raises(ValidationError) as caught:
        model.model_validate({"title": TITLE, key: FORBIDDEN_KEY_VALUES[key]})

    errors = caught.value.errors()

    assert len(errors) == 1
    assert errors[0]["type"] == "extra_forbidden"
    assert errors[0]["loc"] == (key,)
