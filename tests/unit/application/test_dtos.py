"""Specification for the Phase 4 DTO layer: the commands in, the results out.

Three properties are pinned here, and each of them is a rule the rest of the
phase reads off these types rather than re-deciding per use case.

*Immutability*: every command and every result is a frozen, slotted dataclass,
so nothing downstream can edit an input halfway through a use case or a response
after the transaction closed (ADR-020). The negative-attribute tests assert the
portable claim - refused, and no `__dict__` to keep it in - because a frozen
slotted dataclass raises `FrozenInstanceError` for an undeclared name on CPython
3.13 and `TypeError` on 3.14.3, and this project runs on both (plan 02-01).

*The `actor_id` convention*: `commands.py` states that every command names the
actor first. A test reads that back off `dataclasses.fields`, so the convention
is a gate rather than a paragraph. Phase 5 adds the first three commands that
cannot honour it - the two unauthenticated ones and the one whose whole job is
to *produce* an actor - so the gate now runs over every command except a named
exemption set, and a second test derives that set from the table and compares
it to the declaration. Adding a fourth actor-less command is therefore a
deliberate edit in two places rather than a test that quietly stops covering it.

*The sentinel*: the two update commands must be able to say "omitted" and "set
to null" and be believed differently (D-05). mypy proves the narrowing; these
tests prove the runtime counterpart, which is what a use case's `is not UNSET`
guard actually reads.
"""

from dataclasses import FrozenInstanceError, fields
from datetime import UTC, datetime
from typing import Any, Final
from uuid import UUID

import pytest

from taskmanager.application.dto.commands import (
    AssignTaskCommand,
    AuthenticateActorCommand,
    CreateTaskCommand,
    CreateTaskListCommand,
    DeleteTaskCommand,
    DeleteTaskListCommand,
    GetProfileCommand,
    GetTaskCommand,
    GetTaskListCommand,
    ListAssignedTasksCommand,
    ListTaskListsCommand,
    ListTasksCommand,
    ListUsersCommand,
    LoginCommand,
    RegisterUserCommand,
    UnassignTaskCommand,
    UpdateTaskCommand,
    UpdateTaskListCommand,
)
from taskmanager.application.dto.results import (
    AccessTokenResult,
    TaskCollectionResult,
    TaskListResult,
    TaskResult,
    UserResult,
)
from taskmanager.application.dto.unset import UNSET
from taskmanager.domain.entities.task import Task
from taskmanager.domain.entities.task_list import TaskList
from taskmanager.domain.entities.user import User
from taskmanager.domain.value_objects.completion import CompletionStats
from taskmanager.domain.value_objects.task_priority import TaskPriority
from taskmanager.domain.value_objects.task_status import TaskStatus

pytestmark = pytest.mark.unit

# Fixed identifiers and fixed moments, for the reason the sibling suites give:
# a generated value would leave the assertions unable to say what they expect.
NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
LATER = datetime(2026, 6, 1, 9, 30, tzinfo=UTC)
ACTOR_ID = UUID("11111111-1111-4111-8111-111111111111")
TASK_ID = UUID("22222222-2222-4222-8222-222222222222")
TASK_LIST_ID = UUID("33333333-3333-4333-8333-333333333333")
# The user an assignment names, distinct from the actor: `AssignTaskCommand` is
# the only command in the project carrying a second person's identifier, so a
# fixture that reused `ACTOR_ID` would make the field indistinguishable from the
# actor it must never be confused with (T-5-10).
ASSIGNEE_ID = UUID("55555555-5555-4555-8555-555555555555")

# The auth vocabulary's fixtures. `PASSWORD` is a literal in a test table and
# nowhere else: no command stores it, no result carries it, and the only thing
# asserted about it is that the frozen dataclass refuses to have it rewritten.
EMAIL = "ana@example.com"
FULL_NAME = "Ana Torres"
PASSWORD = "a-long-enough-password"
TOKEN = "header.payload.signature"
HASH = "argon2-encoded-hash"

# Attribute names live in constants so mypy does not reject the very assignment
# the immutability tests exist to observe failing at runtime - and so
# flake8-bugbear's B010 does not reject the `setattr` call for having a
# constant name, which it would if the string were written inline.
UNDECLARED_FIELD = "actor"
DECLARED_RESULT_FIELD = "name"
DECLARED_COLLECTION_FIELD = "total_tasks"
DECLARED_USER_FIELD = "email"
DECLARED_TOKEN_FIELD = "access_token"

# Each case is one command instance and the name of a field the immutability
# test tries to overwrite. The tuple is annotated `Any` because the commands
# share no base class on purpose - there is no `Command` supertype to inherit a
# field from, which is what keeps `actor_id` a per-class declaration the field
# order test can check.
COMMAND_CASES: Final[tuple[tuple[Any, str], ...]] = (
    (
        CreateTaskListCommand(actor_id=ACTOR_ID, name="Phase 4", description=None),
        "name",
    ),
    (GetTaskListCommand(actor_id=ACTOR_ID, task_list_id=TASK_LIST_ID), "task_list_id"),
    (ListTaskListsCommand(actor_id=ACTOR_ID), "actor_id"),
    (
        UpdateTaskListCommand(
            actor_id=ACTOR_ID, task_list_id=TASK_LIST_ID, name="Renamed"
        ),
        "name",
    ),
    (
        DeleteTaskListCommand(actor_id=ACTOR_ID, task_list_id=TASK_LIST_ID),
        "task_list_id",
    ),
    (
        CreateTaskCommand(
            actor_id=ACTOR_ID,
            task_list_id=TASK_LIST_ID,
            title="Write the DTOs",
            description=None,
            priority=TaskPriority.MEDIUM,
            due_date=None,
        ),
        "title",
    ),
    (
        GetTaskCommand(actor_id=ACTOR_ID, task_list_id=TASK_LIST_ID, task_id=TASK_ID),
        "task_id",
    ),
    (
        ListTasksCommand(
            actor_id=ACTOR_ID,
            task_list_id=TASK_LIST_ID,
            status=TaskStatus.PENDING,
            priority=TaskPriority.HIGH,
        ),
        "status",
    ),
    (
        UpdateTaskCommand(
            actor_id=ACTOR_ID,
            task_list_id=TASK_LIST_ID,
            task_id=TASK_ID,
            title="Renamed",
        ),
        "title",
    ),
    (
        DeleteTaskCommand(
            actor_id=ACTOR_ID, task_list_id=TASK_LIST_ID, task_id=TASK_ID
        ),
        "task_id",
    ),
    (
        AssignTaskCommand(
            actor_id=ACTOR_ID,
            task_list_id=TASK_LIST_ID,
            task_id=TASK_ID,
            assignee_id=ASSIGNEE_ID,
        ),
        "assignee_id",
    ),
    (
        UnassignTaskCommand(
            actor_id=ACTOR_ID, task_list_id=TASK_LIST_ID, task_id=TASK_ID
        ),
        "task_id",
    ),
    (ListAssignedTasksCommand(actor_id=ACTOR_ID), "actor_id"),
    (ListUsersCommand(actor_id=ACTOR_ID), "actor_id"),
    (
        RegisterUserCommand(email=EMAIL, full_name=FULL_NAME, password=PASSWORD),
        "email",
    ),
    (LoginCommand(email=EMAIL, password=PASSWORD), "password"),
    (AuthenticateActorCommand(token=TOKEN), "token"),
    (GetProfileCommand(actor_id=ACTOR_ID), "actor_id"),
)

COMMAND_IDS: Final[list[str]] = [type(case[0]).__name__ for case in COMMAND_CASES]

# The three commands `commands.py` exempts from the actor-first rule, declared
# here as types rather than inferred, so the exemption is something a reader can
# find and a fourth one cannot arrive by accident: the test below derives the
# same set from the table and fails if the two disagree.
ACTORLESS_COMMANDS: Final[frozenset[type]] = frozenset(
    {RegisterUserCommand, LoginCommand, AuthenticateActorCommand}
)

ACTOR_FIRST_CASES: Final[tuple[tuple[Any, str], ...]] = tuple(
    case for case in COMMAND_CASES if type(case[0]) not in ACTORLESS_COMMANDS
)
ACTOR_FIRST_IDS: Final[list[str]] = [
    type(case[0]).__name__ for case in ACTOR_FIRST_CASES
]


@pytest.mark.parametrize(("command", "declared_field"), COMMAND_CASES, ids=COMMAND_IDS)
def test_a_command_cannot_be_edited_after_presentation_built_it(
    command: Any, declared_field: str
) -> None:
    """frozen=True: a use case cannot rewrite its own input halfway through."""
    with pytest.raises(FrozenInstanceError) as excinfo:
        setattr(command, declared_field, None)

    assert declared_field in str(excinfo.value)


@pytest.mark.parametrize(("command", "declared_field"), COMMAND_CASES, ids=COMMAND_IDS)
def test_a_command_rejects_an_undeclared_attribute(
    command: Any, declared_field: str
) -> None:
    """slots=True leaves no __dict__, so a typo'd field cannot be created.

    The exception type differs between this project's two runtimes - CPython
    3.13 raises `FrozenInstanceError`, 3.14.3 raises `TypeError` - so the
    assertion is the portable claim: refused, and nowhere to keep it either way.
    """
    with pytest.raises((AttributeError, TypeError)):
        setattr(command, UNDECLARED_FIELD, ACTOR_ID)

    assert not hasattr(command, UNDECLARED_FIELD)
    assert not hasattr(command, "__dict__")


@pytest.mark.parametrize(
    ("command", "declared_field"), ACTOR_FIRST_CASES, ids=ACTOR_FIRST_IDS
)
def test_a_command_names_the_actor_first(command: Any, declared_field: str) -> None:
    """The `commands.py` convention, read back off the dataclass rather than
    off the docstring that states it.

    It comes first because everything a use case may see or change derives from
    it: a command that acquired the actor later, or from a body, would be a
    command that could authorize itself (T-4-18).

    The three commands of `ACTORLESS_COMMANDS` are excluded, and the test below
    is what keeps that exclusion honest.
    """
    field_names = [field.name for field in fields(type(command))]

    assert field_names[0] == "actor_id"


def test_only_the_three_unauthenticated_commands_omit_the_actor() -> None:
    """The exemption set, derived from the table and compared to the declaration.

    Without this, a later command that simply forgot `actor_id` could be added
    to `ACTORLESS_COMMANDS` - or the filter could silently start skipping it -
    and the convention would decay one command at a time. Here the two have to
    agree, so an exemption is a decision someone wrote down.
    """
    without_actor = {
        type(command)
        for command, _ in COMMAND_CASES
        if "actor_id" not in {field.name for field in fields(type(command))}
    }

    assert without_actor == ACTORLESS_COMMANDS
    # And the one that carries a credential-adjacent value carries nothing else:
    # `AuthenticateActorCommand` exists to *produce* an actor, so a second field
    # would be something the caller got to assert about themselves.
    assert [field.name for field in fields(AuthenticateActorCommand)] == ["token"]


def test_no_auth_command_can_nominate_an_identity_it_was_not_given() -> None:
    """T-5-09: registration's surface is exactly three caller-supplied fields.

    No `id`, no `created_at`, no role and no `password_hash`: the identifier
    comes from `uuid4()` in the use case and the timestamps from the `Clock`
    port, so a body cannot choose either. Asserted as a whole field list rather
    than one absent name at a time, because a mass-assignment surface is a set.
    """
    assert [field.name for field in fields(RegisterUserCommand)] == [
        "email",
        "full_name",
        "password",
    ]
    assert [field.name for field in fields(LoginCommand)] == ["email", "password"]


def test_the_task_patch_command_cannot_express_a_status_change() -> None:
    """D-08 / TASK-03, proven by absence at the application boundary too.

    The PATCH schema forbids the key, but a command field would let a later
    router wire it anyway; with no field there is nothing to wire, and this test
    fails the moment someone adds one back.
    """
    field_names = {field.name for field in fields(UpdateTaskCommand)}

    assert "status" not in field_names
    # The neighbouring mass-assignment risks, refused the same way (T-4-17).
    assert "owner_id" not in field_names
    assert "assignee_id" not in field_names
    assert "completed_at" not in field_names


def test_assignment_is_the_only_command_that_can_name_an_assignee() -> None:
    """T-5-10, counted across the whole table rather than per command.

    D-05 gives assignment its own door, and the reason that holds is that no
    other command has a field an `assignee_id` could arrive in - so a router
    wiring the value onto the generic PATCH would have nothing to wire it to.
    The neighbouring test asserts the absence on `UpdateTaskCommand` alone;
    this one makes the same claim about every command there is, so a *new*
    command that quietly grew the field fails here rather than at review.
    """
    carrying_an_assignee = {
        type(command)
        for command, _ in COMMAND_CASES
        if "assignee_id" in {field.name for field in fields(type(command))}
    }

    assert carrying_an_assignee == {AssignTaskCommand}
    assert [field.name for field in fields(AssignTaskCommand)] == [
        "actor_id",
        "task_list_id",
        "task_id",
        "assignee_id",
    ]


def test_an_omitted_list_patch_field_is_the_sentinel_and_not_none() -> None:
    """Constructing with no optional argument leaves every field UNSET."""
    command = UpdateTaskListCommand(actor_id=ACTOR_ID, task_list_id=TASK_LIST_ID)

    assert command.name is UNSET
    assert command.description is UNSET


def test_an_explicit_null_on_a_list_patch_is_distinguishable_from_omission() -> None:
    """D-05's whole distinction, as a use case's guard will read it.

    `description=None` means "clear it" and must not be mistaken for "leave it
    alone"; `name` stays UNSET in the same command, so one object carries both
    meanings at once and an implementation that collapsed them fails here.
    """
    command = UpdateTaskListCommand(
        actor_id=ACTOR_ID, task_list_id=TASK_LIST_ID, description=None
    )

    assert command.description is None
    assert command.description is not UNSET
    assert command.name is UNSET


def test_an_omitted_task_patch_field_is_the_sentinel_and_not_none() -> None:
    """All four patchable fields of the task command default to UNSET."""
    command = UpdateTaskCommand(
        actor_id=ACTOR_ID, task_list_id=TASK_LIST_ID, task_id=TASK_ID
    )

    assert command.title is UNSET
    assert command.description is UNSET
    assert command.priority is UNSET
    assert command.due_date is UNSET


def test_an_explicit_null_on_a_task_patch_is_distinguishable_from_omission() -> None:
    """Both nullable task fields carry the same D-05 distinction.

    `due_date` matters twice over: D-07 re-checks the past-moment rule only when
    the field was sent, so "omitted" and "set to null" reaching the use case as
    the same value would make an overdue task impossible to rename.
    """
    command = UpdateTaskCommand(
        actor_id=ACTOR_ID,
        task_list_id=TASK_LIST_ID,
        task_id=TASK_ID,
        description=None,
        due_date=None,
    )

    assert command.description is None
    assert command.due_date is None
    assert command.title is UNSET
    assert command.priority is UNSET


def test_a_task_patch_carries_the_values_it_was_given() -> None:
    """The third leg: a field that was sent with a value arrives as that value."""
    command = UpdateTaskCommand(
        actor_id=ACTOR_ID,
        task_list_id=TASK_LIST_ID,
        task_id=TASK_ID,
        title="Renamed",
        priority=TaskPriority.HIGH,
        due_date=LATER,
    )

    assert command.title == "Renamed"
    assert command.priority is TaskPriority.HIGH
    assert command.due_date == LATER
    assert command.description is UNSET


def test_the_task_listing_filters_default_to_no_filter() -> None:
    """TASK-06's two filters are plain optionals, and both are absent by default."""
    command = ListTasksCommand(actor_id=ACTOR_ID, task_list_id=TASK_LIST_ID)

    assert command.status is None
    assert command.priority is None


def _task_list() -> TaskList:
    """A fully populated list - description included, and two distinct moments.

    `created_at` and `updated_at` differ on purpose: equal values would let a
    mapping that copied one of them into both fields pass the field-by-field
    test below.
    """
    return TaskList(
        id=TASK_LIST_ID,
        owner_id=ACTOR_ID,
        name="Phase 4",
        description="Task lists and tasks",
        created_at=NOW,
        updated_at=LATER,
    )


def _task(title: str, *, status: TaskStatus = TaskStatus.PENDING) -> Task:
    """One task, identified by its title so ordering assertions can name it."""
    return Task(
        id=TASK_ID,
        task_list_id=TASK_LIST_ID,
        title=title,
        status=status,
        priority=TaskPriority.MEDIUM,
        created_at=NOW,
        updated_at=NOW,
    )


def test_a_task_list_result_cannot_be_edited_on_its_way_out() -> None:
    """frozen=True: a response cannot be rewritten after the transaction closed."""
    result = TaskListResult.from_entity(
        _task_list(), CompletionStats(total=0, completed=0)
    )

    with pytest.raises(FrozenInstanceError) as excinfo:
        setattr(result, DECLARED_RESULT_FIELD, "edited")

    assert DECLARED_RESULT_FIELD in str(excinfo.value)
    assert not hasattr(result, "__dict__")


def test_a_task_list_result_rejects_an_undeclared_attribute() -> None:
    """slots=True: a field nobody declared has nowhere to live (T-4-20)."""
    result = TaskListResult.from_entity(
        _task_list(), CompletionStats(total=0, completed=0)
    )

    with pytest.raises((AttributeError, TypeError)):
        setattr(result, UNDECLARED_FIELD, ACTOR_ID)

    assert not hasattr(result, UNDECLARED_FIELD)


def test_a_task_list_result_copies_every_field_and_the_three_statistics() -> None:
    """All nine fields cross, so a forgotten one fails here and not at the HTTP
    boundary where the symptom is a missing key in someone else's client.

    This is the test that catches drift between the entity and the result when
    `TaskList` gains a field (T-4-19).
    """
    task_list = _task_list()

    result = TaskListResult.from_entity(
        task_list, CompletionStats(total=4, completed=1)
    )

    assert result.id == task_list.id
    assert result.owner_id == task_list.owner_id
    assert result.name == task_list.name
    assert result.description == task_list.description
    assert result.created_at == task_list.created_at
    assert result.updated_at == task_list.updated_at
    assert result.total_tasks == 4
    assert result.completed_tasks == 1
    assert result.completion_percentage == 25.0
    assert {field.name for field in fields(TaskListResult)} == {
        "id",
        "owner_id",
        "name",
        "description",
        "created_at",
        "updated_at",
        "total_tasks",
        "completed_tasks",
        "completion_percentage",
    }


def test_an_empty_task_list_reports_zero_percent_rather_than_failing() -> None:
    """D-10's empty case: 0.0, never a ZeroDivisionError and never null.

    The guard lives in `CompletionStats.percentage`, so this test also pins that
    the result reads it rather than dividing the two counters itself.
    """
    result = TaskListResult.from_entity(
        _task_list(), CompletionStats(total=0, completed=0)
    )

    assert result.completion_percentage == 0.0
    assert result.total_tasks == 0
    assert result.completed_tasks == 0


def test_a_task_list_percentage_is_rounded_to_two_decimals() -> None:
    """2 of 3 is 66.666..., and D-09 fixes it at 66.67 for lists and tasks alike.

    Pinned here rather than only in the domain suite because this is the number
    that reaches a client: a later "improvement" to the rounding would change a
    published response, and it fails this test first.
    """
    result = TaskListResult.from_entity(
        _task_list(), CompletionStats(total=3, completed=2)
    )

    assert result.completion_percentage == 66.67


def test_a_task_collection_result_cannot_be_edited_on_its_way_out() -> None:
    """The tasks envelope is frozen and slotted exactly like every other DTO."""
    result = TaskCollectionResult.from_parts([], CompletionStats(total=0, completed=0))

    with pytest.raises(FrozenInstanceError) as excinfo:
        setattr(result, DECLARED_COLLECTION_FIELD, 99)

    assert DECLARED_COLLECTION_FIELD in str(excinfo.value)
    assert not hasattr(result, "__dict__")


def test_a_task_collection_result_rejects_an_undeclared_attribute() -> None:
    """slots=True on the envelope too, for the same T-4-20 reason."""
    result = TaskCollectionResult.from_parts([], CompletionStats(total=0, completed=0))

    with pytest.raises((AttributeError, TypeError)):
        setattr(result, UNDECLARED_FIELD, ACTOR_ID)

    assert not hasattr(result, UNDECLARED_FIELD)


def test_a_task_collection_keeps_its_items_in_a_tuple_in_input_order() -> None:
    """A tuple, not a list - a list would stay editable through the frozen
    wrapper - and D-13's order is preserved rather than re-sorted here.

    Ordering belongs to the repository's `created_at, id` clause; a result DTO
    that sorted would be a second, competing answer to the same question.
    """
    tasks = [_task("first"), _task("second"), _task("third")]

    result = TaskCollectionResult.from_parts(
        tasks, CompletionStats(total=3, completed=0)
    )

    assert isinstance(result.items, tuple)
    assert [item.title for item in result.items] == ["first", "second", "third"]
    assert all(isinstance(item, TaskResult) for item in result.items)


def test_a_task_collection_reports_the_whole_list_never_the_filtered_view() -> None:
    """D-09: the filter describes the view, the counters describe the list.

    One item is handed in - a filtered page - beside statistics covering four
    tasks, and the envelope must carry both without reconciling them. An
    implementation that recomputed the counters from `items` would answer 1 and
    0 here.
    """
    result = TaskCollectionResult.from_parts(
        [_task("only the pending one")], CompletionStats(total=4, completed=3)
    )

    assert len(result.items) == 1
    assert result.total_tasks == 4
    assert result.completed_tasks == 3
    assert result.completion_percentage == 75.0


def test_an_empty_task_collection_reports_zero_percent() -> None:
    """An empty list is an ordinary list: an empty tuple and 0.0, not an error."""
    result = TaskCollectionResult.from_parts([], CompletionStats(total=0, completed=0))

    assert result.items == ()
    assert result.completion_percentage == 0.0


def _user() -> User:
    """One registered account, with a hash that must not reach a result."""
    return User(
        id=ACTOR_ID,
        email=EMAIL,
        full_name=FULL_NAME,
        password_hash=HASH,
        created_at=NOW,
        updated_at=LATER,
    )


def test_a_user_result_copies_the_four_public_fields() -> None:
    """D-09's profile shape: id, email, full_name, created_at, and nothing else."""
    user = _user()

    result = UserResult.from_entity(user)

    assert result.id == user.id
    assert result.email == user.email
    assert result.full_name == user.full_name
    assert result.created_at == user.created_at
    assert [field.name for field in fields(UserResult)] == [
        "id",
        "email",
        "full_name",
        "created_at",
    ]


def test_a_user_result_has_no_field_a_password_hash_could_travel_in() -> None:
    """T-5-04, asserted against `dataclasses.fields` rather than `hasattr`.

    `hasattr` would pass against a result that kept the hash under any other
    name, and against a slotted class carrying it as a non-field attribute. The
    field list is the thing a response schema maps from, so the field list is
    what has to be free of it - and `updated_at` is absent too, because the
    profile answer never had a reason to publish it.
    """
    field_names = {field.name for field in fields(UserResult)}

    assert "password_hash" not in field_names
    assert "password" not in field_names
    assert "updated_at" not in field_names


def test_a_user_result_cannot_be_edited_on_its_way_out() -> None:
    """frozen and slotted, exactly like every other result (ADR-020)."""
    result = UserResult.from_entity(_user())

    with pytest.raises(FrozenInstanceError) as excinfo:
        setattr(result, DECLARED_USER_FIELD, "someone.else@example.com")

    assert DECLARED_USER_FIELD in str(excinfo.value)
    assert not hasattr(result, "__dict__")

    with pytest.raises((AttributeError, TypeError)):
        setattr(result, UNDECLARED_FIELD, ACTOR_ID)


def test_an_access_token_result_carries_the_three_wire_fields() -> None:
    """The login answer, in the shape OAuth2 clients and Swagger expect.

    `token_type` is the lowercase literal `bearer`; `expires_in` is a number of
    seconds. Both are wire-format obligations, so both are asserted here rather
    than left to the route that builds the response.
    """
    result = AccessTokenResult(access_token=TOKEN, token_type="bearer", expires_in=1800)

    assert result.access_token == TOKEN
    assert result.token_type == "bearer"
    assert result.expires_in == 1800
    assert [field.name for field in fields(AccessTokenResult)] == [
        "access_token",
        "token_type",
        "expires_in",
    ]


def test_an_access_token_result_cannot_be_edited_on_its_way_out() -> None:
    """Frozen and slotted: a token cannot be swapped after the use case built it."""
    result = AccessTokenResult(access_token=TOKEN, token_type="bearer", expires_in=1800)

    with pytest.raises(FrozenInstanceError) as excinfo:
        setattr(result, DECLARED_TOKEN_FIELD, "another.token.entirely")

    assert DECLARED_TOKEN_FIELD in str(excinfo.value)
    assert not hasattr(result, "__dict__")

    with pytest.raises((AttributeError, TypeError)):
        setattr(result, UNDECLARED_FIELD, ACTOR_ID)
