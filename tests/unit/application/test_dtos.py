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
is a gate rather than a paragraph.

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
    CreateTaskCommand,
    CreateTaskListCommand,
    DeleteTaskCommand,
    DeleteTaskListCommand,
    GetTaskCommand,
    GetTaskListCommand,
    ListTaskListsCommand,
    ListTasksCommand,
    UpdateTaskCommand,
    UpdateTaskListCommand,
)
from taskmanager.application.dto.results import (
    TaskCollectionResult,
    TaskListResult,
    TaskResult,
)
from taskmanager.application.dto.unset import UNSET
from taskmanager.domain.entities.task import Task
from taskmanager.domain.entities.task_list import TaskList
from taskmanager.domain.value_objects.completion import CompletionStats
from taskmanager.domain.value_objects.task_priority import TaskPriority
from taskmanager.domain.value_objects.task_status import TaskStatus

# Fixed identifiers and fixed moments, for the reason the sibling suites give:
# a generated value would leave the assertions unable to say what they expect.
NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
LATER = datetime(2026, 6, 1, 9, 30, tzinfo=UTC)
ACTOR_ID = UUID("11111111-1111-4111-8111-111111111111")
TASK_ID = UUID("22222222-2222-4222-8222-222222222222")
TASK_LIST_ID = UUID("33333333-3333-4333-8333-333333333333")

# Attribute names live in constants so mypy does not reject the very assignment
# the immutability tests exist to observe failing at runtime.
UNDECLARED_FIELD = "actor"
DECLARED_RESULT_FIELD = "name"
DECLARED_COLLECTION_FIELD = "total_tasks"

# Each case is one command instance and the name of a field the immutability
# test tries to overwrite. The tuple is annotated `Any` because the ten commands
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
)

COMMAND_IDS: Final[list[str]] = [type(case[0]).__name__ for case in COMMAND_CASES]


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


@pytest.mark.parametrize(("command", "declared_field"), COMMAND_CASES, ids=COMMAND_IDS)
def test_a_command_names_the_actor_first(command: Any, declared_field: str) -> None:
    """The `commands.py` convention, read back off the dataclass rather than
    off the docstring that states it.

    It comes first because everything a use case may see or change derives from
    it: a command that acquired the actor later, or from a body, would be a
    command that could authorize itself (T-4-18).
    """
    field_names = [field.name for field in fields(type(command))]

    assert field_names[0] == "actor_id"


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
