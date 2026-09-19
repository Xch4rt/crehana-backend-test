"""Unit tests for the Task entity and its status state machine."""

from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID

import pytest

from taskmanager.domain.entities.task import Task
from taskmanager.domain.exceptions import InvalidStatusTransitionError, ValidationError
from taskmanager.domain.value_objects.task_priority import TaskPriority
from taskmanager.domain.value_objects.task_status import TaskStatus

# Every instant and identifier below is a literal. A freshly generated identifier
# or a clock reading would make the assertions on `updated_at` and `completed_at`
# unfalsifiable: the test could no longer state which moment it expects.
NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
LATER = NOW + timedelta(hours=1)
EVEN_LATER = NOW + timedelta(hours=2)
NAIVE_NOW = datetime(2026, 1, 1, 12, 0)
BOGOTA = timezone(timedelta(hours=-5))
AWARE_NON_UTC_DUE = datetime(2026, 1, 2, 7, 0, tzinfo=BOGOTA)
TASK_ID = UUID("11111111-1111-4111-8111-111111111111")
TASK_LIST_ID = UUID("22222222-2222-4222-8222-222222222222")

# A name that is not a field, held in a constant so mypy does not reject the very
# assignment this test exists to observe failing at runtime.
UNDECLARED_FIELD = "statsu"


def _task(status: TaskStatus = TaskStatus.PENDING) -> Task:
    """Build a task in the requested status with at most one transition."""
    task = Task.create(
        task_id=TASK_ID,
        task_list_id=TASK_LIST_ID,
        title="Write the specification",
        now=NOW,
    )
    if status is not TaskStatus.PENDING:
        task.change_status(status, now=NOW)
    return task


def test_task_create_starts_pending_and_unfinished() -> None:
    """A new task is pending, unfinished, medium priority and freshly stamped."""
    task = _task()

    assert task.status is TaskStatus.PENDING
    assert task.priority is TaskPriority.MEDIUM
    assert task.completed_at is None
    assert task.created_at == task.updated_at == NOW


def test_task_create_strips_the_title_and_normalises_the_description() -> None:
    """Surrounding whitespace is noise; a blank description is an absent one."""
    task = Task.create(
        task_id=TASK_ID,
        task_list_id=TASK_LIST_ID,
        title="  Write the specification  ",
        description="   ",
        now=NOW,
    )

    assert task.title == "Write the specification"
    assert task.description is None


def test_task_create_accepts_a_due_date_at_or_after_the_creation_moment() -> None:
    """A future deadline is stored as given, in UTC."""
    task = Task.create(
        task_id=TASK_ID,
        task_list_id=TASK_LIST_ID,
        title="Write the specification",
        due_date=LATER,
        priority=TaskPriority.HIGH,
        assignee_id=TASK_LIST_ID,
        now=NOW,
    )

    assert task.due_date == LATER
    assert task.priority is TaskPriority.HIGH
    assert task.assignee_id == TASK_LIST_ID


def test_task_allows_the_transition_from_pending_to_in_progress() -> None:
    """Starting work moves the status and the timestamp, nothing else."""
    task = _task()

    task.change_status(TaskStatus.IN_PROGRESS, now=LATER)

    assert task.status is TaskStatus.IN_PROGRESS
    assert task.updated_at == LATER
    assert task.completed_at is None


def test_task_allows_the_transition_from_pending_to_completed() -> None:
    """A task may be finished without ever being started."""
    task = _task()

    task.change_status(TaskStatus.COMPLETED, now=LATER)

    assert task.status is TaskStatus.COMPLETED
    assert task.updated_at == LATER


def test_task_allows_the_transition_from_in_progress_to_pending() -> None:
    """Work can be put back on the shelf."""
    task = _task(TaskStatus.IN_PROGRESS)

    task.change_status(TaskStatus.PENDING, now=LATER)

    assert task.status is TaskStatus.PENDING
    assert task.updated_at == LATER


def test_task_allows_the_transition_from_in_progress_to_completed() -> None:
    """The ordinary happy path of the lifecycle."""
    task = _task(TaskStatus.IN_PROGRESS)

    task.change_status(TaskStatus.COMPLETED, now=LATER)

    assert task.status is TaskStatus.COMPLETED
    assert task.updated_at == LATER


def test_task_allows_the_reopening_transition_from_completed_to_in_progress() -> None:
    """Reopening lands in in_progress: work resumes before it is un-started."""
    task = _task(TaskStatus.COMPLETED)

    task.change_status(TaskStatus.IN_PROGRESS, now=LATER)

    assert task.status is TaskStatus.IN_PROGRESS


def test_task_rejects_the_forbidden_transition_from_completed_to_pending() -> None:
    """The single forbidden move raises its own error and changes nothing."""
    task = _task(TaskStatus.COMPLETED)
    before = (task.status, task.updated_at, task.completed_at)

    with pytest.raises(InvalidStatusTransitionError) as excinfo:
        task.change_status(TaskStatus.PENDING, now=LATER)

    assert excinfo.value.details == {"from": "completed", "to": "pending"}
    assert (task.status, task.updated_at, task.completed_at) == before


def test_task_same_state_change_is_an_idempotent_no_op_while_pending() -> None:
    """Pending to pending moves no field and no timestamp (D-02)."""
    task = _task()
    before = (task.status, task.updated_at, task.completed_at)

    task.change_status(TaskStatus.PENDING, now=EVEN_LATER)

    assert (task.status, task.updated_at, task.completed_at) == before


def test_task_same_state_change_is_an_idempotent_no_op_while_in_progress() -> None:
    """In progress to in progress is a no-op, not a conflict."""
    task = _task(TaskStatus.IN_PROGRESS)
    before = (task.status, task.updated_at, task.completed_at)

    task.change_status(TaskStatus.IN_PROGRESS, now=EVEN_LATER)

    assert (task.status, task.updated_at, task.completed_at) == before


def test_task_same_state_change_is_an_idempotent_no_op_while_completed() -> None:
    """Completing a completed task does not restamp when it was finished."""
    task = _task(TaskStatus.COMPLETED)
    before = (task.status, task.updated_at, task.completed_at)

    task.change_status(TaskStatus.COMPLETED, now=EVEN_LATER)

    assert (task.status, task.updated_at, task.completed_at) == before


def test_task_entering_completed_sets_completed_at() -> None:
    """The finish stamp is exactly the moment the caller supplied (D-03)."""
    task = _task()

    task.change_status(TaskStatus.COMPLETED, now=LATER)

    assert task.completed_at == LATER


def test_task_leaving_completed_clears_completed_at() -> None:
    """Reopening a task un-finishes it: the stamp goes back to None (D-03)."""
    task = _task(TaskStatus.COMPLETED)

    task.change_status(TaskStatus.IN_PROGRESS, now=LATER)

    assert task.completed_at is None


def test_task_validation_rejects_a_blank_title() -> None:
    """An empty title is refused at construction, naming the field."""
    with pytest.raises(ValidationError) as excinfo:
        Task.create(
            task_id=TASK_ID,
            task_list_id=TASK_LIST_ID,
            title="",
            now=NOW,
        )

    assert excinfo.value.details == {"field": "title"}


def test_task_validation_rejects_a_whitespace_only_title() -> None:
    """Spaces are stripped before the blank check, so they cannot smuggle a title."""
    with pytest.raises(ValidationError) as excinfo:
        Task.create(
            task_id=TASK_ID,
            task_list_id=TASK_LIST_ID,
            title="   ",
            now=NOW,
        )

    assert excinfo.value.details == {"field": "title"}


def test_task_validation_rejects_an_over_length_title() -> None:
    """The cap is the entity ClassVar, so the test cannot drift from the rule."""
    with pytest.raises(ValidationError) as excinfo:
        Task.create(
            task_id=TASK_ID,
            task_list_id=TASK_LIST_ID,
            title="a" * (Task.TITLE_MAX_LENGTH + 1),
            now=NOW,
        )

    assert excinfo.value.details == {"field": "title"}


def test_task_validation_rejects_an_over_length_description() -> None:
    """The optional field is bounded too, by its own ClassVar."""
    with pytest.raises(ValidationError) as excinfo:
        Task.create(
            task_id=TASK_ID,
            task_list_id=TASK_LIST_ID,
            title="Write the specification",
            description="a" * (Task.DESCRIPTION_MAX_LENGTH + 1),
            now=NOW,
        )

    assert excinfo.value.details == {"field": "description"}


def test_task_validation_rejects_a_past_due_date_at_creation() -> None:
    """A deadline behind the creation moment is refused on input (rule 5)."""
    with pytest.raises(ValidationError) as excinfo:
        Task.create(
            task_id=TASK_ID,
            task_list_id=TASK_LIST_ID,
            title="Write the specification",
            due_date=NOW - timedelta(hours=1),
            now=NOW,
        )

    assert excinfo.value.details == {"field": "due_date"}


def test_task_rejects_a_naive_created_at() -> None:
    """A datetime with no timezone cannot become a stored timestamp (D-14)."""
    with pytest.raises(ValidationError) as excinfo:
        Task.create(
            task_id=TASK_ID,
            task_list_id=TASK_LIST_ID,
            title="Write the specification",
            now=NAIVE_NOW,
        )

    assert excinfo.value.details == {"field": "created_at"}


def test_task_rejects_a_naive_due_date() -> None:
    """The optional temporal field is held to the same rule as the mandatory ones."""
    with pytest.raises(ValidationError) as excinfo:
        Task.create(
            task_id=TASK_ID,
            task_list_id=TASK_LIST_ID,
            title="Write the specification",
            due_date=NAIVE_NOW + timedelta(days=1),
            now=NOW,
        )

    assert excinfo.value.details == {"field": "due_date"}


def test_task_rejects_a_naive_completed_at() -> None:
    """Rehydrating a finished task with a naive stamp fails at construction."""
    with pytest.raises(ValidationError) as excinfo:
        Task(
            id=TASK_ID,
            task_list_id=TASK_LIST_ID,
            title="Write the specification",
            status=TaskStatus.COMPLETED,
            priority=TaskPriority.MEDIUM,
            created_at=NOW,
            updated_at=NOW,
            completed_at=NAIVE_NOW,
        )

    assert excinfo.value.details == {"field": "completed_at"}


def test_task_rejects_a_completed_status_with_no_completion_stamp() -> None:
    """D-03 is an invariant of the type, not a habit of one mutator.

    Only `change_status` ever maintained the pair. This constructs the state a
    migration, a fixture or a Phase 3 mapper bug can produce directly.
    """
    with pytest.raises(ValidationError) as excinfo:
        Task(
            id=TASK_ID,
            task_list_id=TASK_LIST_ID,
            title="Write the specification",
            status=TaskStatus.COMPLETED,
            priority=TaskPriority.MEDIUM,
            created_at=NOW,
            updated_at=NOW,
            completed_at=None,
        )

    assert excinfo.value.details == {"field": "completed_at"}


def test_task_rejects_a_completion_stamp_on_an_unfinished_task() -> None:
    """The other half of the same invariant: an unfinished task has no stamp."""
    with pytest.raises(ValidationError) as excinfo:
        Task(
            id=TASK_ID,
            task_list_id=TASK_LIST_ID,
            title="Write the specification",
            status=TaskStatus.PENDING,
            priority=TaskPriority.MEDIUM,
            created_at=NOW,
            updated_at=NOW,
            completed_at=NOW,
        )

    assert excinfo.value.details == {"field": "completed_at"}


def test_task_accepts_a_completed_task_carrying_its_stamp() -> None:
    """The coherent pair rehydrates without complaint, as Phase 3 needs it to."""
    task = Task(
        id=TASK_ID,
        task_list_id=TASK_LIST_ID,
        title="Write the specification",
        status=TaskStatus.COMPLETED,
        priority=TaskPriority.MEDIUM,
        created_at=NOW,
        updated_at=LATER,
        completed_at=LATER,
    )

    assert task.status is TaskStatus.COMPLETED
    assert task.completed_at == LATER


def test_task_rejects_a_naive_now_argument() -> None:
    """The clock reading the caller passes in is validated like any other input."""
    task = _task()

    with pytest.raises(ValidationError) as excinfo:
        task.change_status(TaskStatus.IN_PROGRESS, now=NAIVE_NOW)

    assert excinfo.value.details == {"field": "now"}


def test_task_normalises_an_aware_non_utc_due_date_to_utc() -> None:
    """An offset-carrying deadline keeps its instant and loses its offset."""
    task = Task.create(
        task_id=TASK_ID,
        task_list_id=TASK_LIST_ID,
        title="Write the specification",
        due_date=AWARE_NON_UTC_DUE,
        now=NOW,
    )

    assert task.due_date is not None
    assert task.due_date.tzinfo is UTC
    assert task.due_date == AWARE_NON_UTC_DUE


def test_task_rename_strips_and_revalidates_the_title() -> None:
    """Renaming runs the same guard as creating, and moves updated_at."""
    task = _task()

    task.rename("  Ship the thing  ", now=LATER)

    assert task.title == "Ship the thing"
    assert task.updated_at == LATER


def test_task_rename_rejects_a_blank_title() -> None:
    """A mutator cannot be used to slip past a constructor invariant."""
    task = _task()

    with pytest.raises(ValidationError) as excinfo:
        task.rename("   ", now=LATER)

    assert excinfo.value.details == {"field": "title"}


def test_task_rename_with_a_naive_now_changes_nothing() -> None:
    """A refused rename leaves the aggregate exactly as it found it.

    The title argument is valid here, so the only thing that can fail is the
    `now` guard - which is the point: an implementation that assigned the title
    first would leave the entity renamed with an unmoved `updated_at`.
    """
    task = _task()
    before = (task.title, task.updated_at)

    with pytest.raises(ValidationError) as excinfo:
        task.rename("Ship the thing", now=NAIVE_NOW)

    assert excinfo.value.details == {"field": "now"}
    assert (task.title, task.updated_at) == before


def test_task_reschedule_clears_the_due_date() -> None:
    """Passing None removes the deadline and stamps the change."""
    task = Task.create(
        task_id=TASK_ID,
        task_list_id=TASK_LIST_ID,
        title="Write the specification",
        due_date=EVEN_LATER,
        now=NOW,
    )

    task.reschedule(None, now=LATER)

    assert task.due_date is None
    assert task.updated_at == LATER


def test_task_reschedule_accepts_a_future_due_date() -> None:
    """A deadline after the supplied moment is stored."""
    task = _task()

    task.reschedule(EVEN_LATER, now=LATER)

    assert task.due_date == EVEN_LATER
    assert task.updated_at == LATER


def test_task_reschedule_rejects_a_due_date_in_the_past() -> None:
    """A deadline before the supplied moment is refused, as it is at creation."""
    task = _task()

    with pytest.raises(ValidationError) as excinfo:
        task.reschedule(NOW - timedelta(hours=1), now=LATER)

    assert excinfo.value.details == {"field": "due_date"}


# Phase 4 review WR-02: the reviewer's two request bodies, as the schema parses them.
UNREPRESENTABLE_DUE_DATES = [
    datetime.fromisoformat("9999-12-31T23:59:59-12:00"),
    datetime.fromisoformat("0001-01-01T00:00:00+14:00"),
]


@pytest.mark.parametrize("due_date", UNREPRESENTABLE_DUE_DATES)
def test_task_create_refuses_a_due_date_with_no_utc_form(due_date: datetime) -> None:
    """TASK-08's neighbour: a deadline that overflows on conversion is a 422."""
    with pytest.raises(ValidationError) as excinfo:
        Task.create(
            task_id=TASK_ID,
            task_list_id=TASK_LIST_ID,
            title="Out of range",
            due_date=due_date,
            now=NOW,
        )

    assert excinfo.value.details == {"field": "due_date"}


@pytest.mark.parametrize("due_date", UNREPRESENTABLE_DUE_DATES)
def test_task_reschedule_refuses_a_due_date_with_no_utc_form(
    due_date: datetime,
) -> None:
    """The PATCH leg, and a refused call leaves the aggregate as it found it."""
    task = _task()

    with pytest.raises(ValidationError) as excinfo:
        task.reschedule(due_date, now=LATER)

    assert excinfo.value.details == {"field": "due_date"}
    assert task.due_date is None
    assert task.updated_at == NOW


def test_task_rejects_an_undeclared_attribute() -> None:
    """slots=True leaves no __dict__, so a typo cannot create a shadow field."""
    task = _task()

    # Unlike the frozen value objects, this assertion is portable across both
    # runtimes of the project. A frozen dataclass installs its own __setattr__
    # whose behaviour for a non-field name differs between CPython 3.13 and
    # 3.14.3 (see evidence/02-01-frozen-slots-setattr.txt); a mutable slotted
    # class installs none, so the refusal comes from the type itself.
    with pytest.raises(AttributeError):
        setattr(task, UNDECLARED_FIELD, TaskStatus.PENDING)

    assert not hasattr(task, UNDECLARED_FIELD)
    assert not hasattr(task, "__dict__")
    assert UNDECLARED_FIELD not in Task.__slots__
    assert "status" in Task.__slots__


def test_task_describe_sets_the_description_and_stamps_the_change() -> None:
    """The mutator trims like the constructor and moves updated_at."""
    task = _task()

    task.describe("  Draft the whole thing  ", now=LATER)

    assert task.description == "Draft the whole thing"
    assert task.updated_at == LATER


def test_task_describe_with_none_clears_the_description() -> None:
    """An explicit null empties the field (Phase 4 D-05)."""
    task = _task()
    task.describe("Draft the whole thing", now=NOW)

    task.describe(None, now=LATER)

    assert task.description is None
    assert task.updated_at == LATER


def test_task_describe_with_an_empty_string_clears_the_description() -> None:
    """A blank string and a null are the same request: one absence, one form."""
    task = _task()
    task.describe("Draft the whole thing", now=NOW)

    task.describe("   ", now=LATER)

    assert task.description is None


def test_task_describe_rejects_an_over_length_description() -> None:
    """A refused description leaves the aggregate exactly as it found it."""
    task = _task()
    task.describe("Draft the whole thing", now=NOW)
    before = (task.description, task.updated_at)

    with pytest.raises(ValidationError) as excinfo:
        task.describe("a" * (Task.DESCRIPTION_MAX_LENGTH + 1), now=LATER)

    assert excinfo.value.details == {"field": "description"}
    assert (task.description, task.updated_at) == before


def test_task_describe_with_a_naive_now_changes_nothing() -> None:
    """The description argument is valid, so only the `now` guard can fail.

    That is what lets this test observe an implementation which assigned the
    description before finishing its validation.
    """
    task = _task()
    task.describe("Draft the whole thing", now=NOW)
    before = (task.description, task.updated_at)

    with pytest.raises(ValidationError) as excinfo:
        task.describe("Something else", now=NAIVE_NOW)

    assert excinfo.value.details == {"field": "now"}
    assert (task.description, task.updated_at) == before


def test_task_reprioritise_moves_the_priority_and_stamps_the_change() -> None:
    """The one field the PATCH endpoint changes, and the timestamp with it."""
    task = _task()

    task.reprioritise(TaskPriority.HIGH, now=LATER)

    assert task.priority is TaskPriority.HIGH
    assert task.updated_at == LATER


def test_task_reprioritise_with_a_naive_now_changes_nothing() -> None:
    """The priority is a valid member, so only the `now` guard can fail."""
    task = _task()
    before = (task.priority, task.updated_at)

    with pytest.raises(ValidationError) as excinfo:
        task.reprioritise(TaskPriority.HIGH, now=NAIVE_NOW)

    assert excinfo.value.details == {"field": "now"}
    assert (task.priority, task.updated_at) == before


def test_task_default_priority_is_the_one_the_constructor_applies() -> None:
    """TASK-01's default exists once, and `create` is proven to read it.

    Asserting only `Task.DEFAULT_PRIORITY is TaskPriority.MEDIUM` would leave a
    `create` that spelled `medium` a second time perfectly green, which is the
    drift the ClassVar was introduced to make impossible.
    """
    assert Task.DEFAULT_PRIORITY is TaskPriority.MEDIUM

    task = Task.create(
        task_id=TASK_ID,
        task_list_id=TASK_LIST_ID,
        title="Write the specification",
        now=NOW,
    )

    assert task.priority is Task.DEFAULT_PRIORITY
