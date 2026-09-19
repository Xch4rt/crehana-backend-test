"""Round-trip proof for all three aggregates, with no database involved.

That is the point of keeping the mappers pure functions: DB-03 is a claim about
translation, not about storage, so it can be falsified in milliseconds here
rather than behind a container that has to start first. Plans 03-06 and 03-07
then prove the *other* half - that PostgreSQL gives the rows back - against a
real server.

Every literal below is fixed. A generated identifier or a clock reading would
make an equality assertion pass for the wrong reason: the value would travel
through the mapper in a variable that both sides read, and a mapper that dropped
the field entirely would still compare equal to itself.
"""

from datetime import UTC, datetime, timedelta
from typing import Final
from uuid import UUID

import pytest

from taskmanager.domain.entities.task import Task
from taskmanager.domain.entities.task_list import TaskList
from taskmanager.domain.entities.user import User
from taskmanager.domain.exceptions import DomainError
from taskmanager.domain.value_objects.task_priority import TaskPriority
from taskmanager.domain.value_objects.task_status import TaskStatus
from taskmanager.infrastructure.db.errors import NaiveDatetimeFromDatabaseError
from taskmanager.infrastructure.db.mappers import (
    apply_task_list_to_row,
    apply_task_to_row,
    apply_user_to_row,
    task_list_to_entity,
    task_list_to_row,
    task_to_entity,
    task_to_row,
    user_to_entity,
    user_to_row,
)

pytestmark = pytest.mark.unit

USER_ID: Final[UUID] = UUID("11111111-1111-4111-8111-111111111111")
TASK_LIST_ID: Final[UUID] = UUID("22222222-2222-4222-8222-222222222222")
TASK_ID: Final[UUID] = UUID("33333333-3333-4333-8333-333333333333")
ASSIGNEE_ID: Final[UUID] = UUID("44444444-4444-4444-8444-444444444444")

CREATED_AT: Final[datetime] = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
UPDATED_AT: Final[datetime] = datetime(2026, 1, 2, 9, 30, tzinfo=UTC)
DUE_DATE: Final[datetime] = datetime(2026, 3, 1, 8, 0, tzinfo=UTC)
COMPLETED_AT: Final[datetime] = datetime(2026, 2, 1, 17, 45, tzinfo=UTC)

# The value the whole WR-05 guard exists to refuse: the same instant with the
# timezone stripped off, which is what a column that regressed to `TIMESTAMP
# WITHOUT TIME ZONE` would hand back.
NAIVE: Final[datetime] = datetime(2026, 1, 1, 12, 0)


def _user() -> User:
    return User(
        id=USER_ID,
        email="owner@example.com",
        full_name="Ada Lovelace",
        password_hash="$argon2id$v=19$m=65536,t=3,p=4$fake",
        created_at=CREATED_AT,
        updated_at=UPDATED_AT,
    )


def _task_list() -> TaskList:
    return TaskList(
        id=TASK_LIST_ID,
        owner_id=USER_ID,
        name="Groceries",
        description="Everything the fridge is missing",
        created_at=CREATED_AT,
        updated_at=UPDATED_AT,
    )


def _task() -> Task:
    return Task(
        id=TASK_ID,
        task_list_id=TASK_LIST_ID,
        title="Buy milk",
        status=TaskStatus.PENDING,
        priority=TaskPriority.MEDIUM,
        created_at=CREATED_AT,
        updated_at=UPDATED_AT,
    )


def _assert_tasks_match(actual: Task, expected: Task) -> None:
    """Compare field by field so a failure names the field that was lost."""
    assert actual.id == expected.id
    assert actual.task_list_id == expected.task_list_id
    assert actual.title == expected.title
    assert actual.status == expected.status
    assert actual.priority == expected.priority
    assert actual.created_at == expected.created_at
    assert actual.updated_at == expected.updated_at
    assert actual.description == expected.description
    assert actual.due_date == expected.due_date
    assert actual.completed_at == expected.completed_at
    assert actual.assignee_id == expected.assignee_id


def test_a_user_round_trips_through_its_row() -> None:
    """Entity to row to entity loses nothing a `User` carries."""
    user = _user()

    restored = user_to_entity(user_to_row(user))

    assert restored == user


def test_a_task_list_round_trips_through_its_row() -> None:
    """Entity to row to entity loses nothing a `TaskList` carries."""
    task_list = _task_list()

    restored = task_list_to_entity(task_list_to_row(task_list))

    assert restored == task_list


def test_a_task_list_with_no_description_round_trips() -> None:
    """The nullable column comes back as `None`, not as an empty string."""
    task_list = TaskList(
        id=TASK_LIST_ID,
        owner_id=USER_ID,
        name="Groceries",
        created_at=CREATED_AT,
        updated_at=UPDATED_AT,
    )

    restored = task_list_to_entity(task_list_to_row(task_list))

    assert restored.description is None
    assert restored == task_list


def test_a_task_round_trips_through_its_row() -> None:
    """Entity to row to entity loses nothing a minimal `Task` carries."""
    task = _task()

    restored = task_to_entity(task_to_row(task))

    _assert_tasks_match(restored, task)


def test_a_task_with_every_optional_field_set_round_trips() -> None:
    """The four optional fields survive together, not just one at a time."""
    task = Task(
        id=TASK_ID,
        task_list_id=TASK_LIST_ID,
        title="Buy milk",
        status=TaskStatus.COMPLETED,
        priority=TaskPriority.HIGH,
        created_at=CREATED_AT,
        updated_at=UPDATED_AT,
        description="Semi-skimmed, two litres",
        due_date=DUE_DATE,
        completed_at=COMPLETED_AT,
        assignee_id=ASSIGNEE_ID,
    )

    restored = task_to_entity(task_to_row(task))

    _assert_tasks_match(restored, task)
    assert restored.description == "Semi-skimmed, two litres"
    assert restored.due_date == DUE_DATE
    assert restored.completed_at == COMPLETED_AT
    assert restored.assignee_id == ASSIGNEE_ID


def test_status_and_priority_are_stored_as_their_string_values() -> None:
    """The columns are plain `VARCHAR` (D-11), so the row holds plain strings."""
    task = Task(
        id=TASK_ID,
        task_list_id=TASK_LIST_ID,
        title="Buy milk",
        status=TaskStatus.IN_PROGRESS,
        priority=TaskPriority.HIGH,
        created_at=CREATED_AT,
        updated_at=UPDATED_AT,
    )

    row = task_to_row(task)

    assert row.status == "in_progress"
    assert row.priority == "high"
    # `StrEnum` members compare equal to their value, so the assertions above
    # would also hold for a row that stored the enum object itself - which the
    # `VARCHAR` column would then have to coerce. Pin the type as well.
    assert type(row.status) is str
    assert type(row.priority) is str


def test_status_and_priority_come_back_as_enum_members() -> None:
    """DB-04: the application layer never sees a bare status string."""
    row = task_to_row(_task())
    row.status = "completed"
    row.priority = "low"
    row.completed_at = COMPLETED_AT

    restored = task_to_entity(row)

    assert isinstance(restored.status, TaskStatus)
    assert isinstance(restored.priority, TaskPriority)
    assert restored.status is TaskStatus.COMPLETED
    assert restored.priority is TaskPriority.LOW


def test_a_status_the_check_constraint_would_refuse_fails_at_the_boundary() -> None:
    """Rebuilding through the enum re-validates what the database handed back."""
    row = task_to_row(_task())
    row.status = "almost_done"

    with pytest.raises(ValueError):
        task_to_entity(row)


def test_apply_writes_every_mutable_field_onto_an_existing_task_row() -> None:
    """`update()` mutates the tracked row; the primary key is left alone."""
    row = task_to_row(_task())
    changed = Task(
        id=TASK_ID,
        task_list_id=TASK_LIST_ID,
        title="Buy oat milk",
        status=TaskStatus.COMPLETED,
        priority=TaskPriority.HIGH,
        created_at=CREATED_AT,
        updated_at=UPDATED_AT + timedelta(hours=1),
        description="Barista edition",
        due_date=DUE_DATE,
        completed_at=COMPLETED_AT,
        assignee_id=ASSIGNEE_ID,
    )

    apply_task_to_row(changed, row)

    assert row.id == TASK_ID
    _assert_tasks_match(task_to_entity(row), changed)


def test_apply_writes_every_mutable_field_onto_an_existing_task_list_row() -> None:
    """The same contract for a list: everything but the identity moves."""
    row = task_list_to_row(_task_list())
    changed = TaskList(
        id=TASK_LIST_ID,
        owner_id=USER_ID,
        name="Weekly groceries",
        description=None,
        created_at=CREATED_AT,
        updated_at=UPDATED_AT + timedelta(hours=1),
    )

    apply_task_list_to_row(changed, row)

    assert row.id == TASK_LIST_ID
    assert task_list_to_entity(row) == changed


def test_apply_writes_every_mutable_field_onto_an_existing_user_row() -> None:
    """The same contract for a user: everything but the identity moves."""
    row = user_to_row(_user())
    changed = User(
        id=USER_ID,
        email="new.owner@example.com",
        full_name="Ada Byron",
        password_hash="$argon2id$v=19$m=65536,t=3,p=4$rotated",
        created_at=CREATED_AT,
        updated_at=UPDATED_AT + timedelta(hours=1),
    )

    apply_user_to_row(changed, row)

    assert row.id == USER_ID
    assert user_to_entity(row) == changed


def test_a_naive_timestamp_from_the_database_is_an_infrastructure_fault() -> None:
    """WR-05: the mapper refuses it before an entity is built, and it is not 4xx.

    The classification is the whole point. A `DomainError` here would answer the
    caller with a 422 naming a field their request never contained, when what
    actually happened is that this application's own schema stopped promising
    `TIMESTAMP WITH TIME ZONE`.
    """
    row = task_to_row(_task())
    row.created_at = NAIVE

    with pytest.raises(NaiveDatetimeFromDatabaseError) as raised:
        task_to_entity(row)

    assert "tasks.created_at" in str(raised.value)
    assert not isinstance(raised.value, DomainError)


def test_a_naive_nullable_timestamp_is_refused_too() -> None:
    """The guard covers the optional columns, not only the mandatory pair."""
    row = task_to_row(_task())
    row.due_date = NAIVE

    with pytest.raises(NaiveDatetimeFromDatabaseError) as raised:
        task_to_entity(row)

    assert "tasks.due_date" in str(raised.value)


def test_a_naive_timestamp_on_a_user_row_is_refused() -> None:
    """Every aggregate is guarded, so the proof is not `tasks`-shaped."""
    row = user_to_row(_user())
    row.updated_at = NAIVE

    with pytest.raises(NaiveDatetimeFromDatabaseError) as raised:
        user_to_entity(row)

    assert "users.updated_at" in str(raised.value)


def test_a_naive_timestamp_on_a_task_list_row_is_refused() -> None:
    """The third aggregate, for the same reason."""
    row = task_list_to_row(_task_list())
    row.created_at = NAIVE

    with pytest.raises(NaiveDatetimeFromDatabaseError) as raised:
        task_list_to_entity(row)

    assert "task_lists.created_at" in str(raised.value)
