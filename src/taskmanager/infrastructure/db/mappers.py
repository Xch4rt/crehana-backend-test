"""The only module that knows both the entity shape and the row shape (DB-03).

The rejected alternative is `registry.map_imperatively` applied to the domain
dataclasses themselves. It writes fewer lines and it fuses exactly the two
things DB-03 keeps apart: every entity would carry SQLAlchemy instrumentation,
an expired attribute could emit SQL from inside a use case, and
`tests/architecture/test_domain_is_stdlib_only.py` would go red the moment the
mapping was registered. Nine small functions are the price of keeping the domain
a set of plain dataclasses that need no database to exist.

Nine, not six, because a repository's `update()` loads the row that is already
in the session and writes the entity's current values onto it. Replacing that
row with a freshly constructed one would either detach the original or insert a
duplicate, so the `apply_*` functions exist as the in-place half of each pair.

The enums make one round trip through a plain string and back. `to_row` writes
`status.value` and `priority.value` because D-11 stores them in `VARCHAR`
columns guarded by `CHECK` constraints rather than PostgreSQL `ENUM` types;
`to_entity` rebuilds them with `TaskStatus(...)` and `TaskPriority(...)`, so a
value that somehow got past `ck_tasks_status` raises at this boundary instead of
becoming a live entity in an invalid state.

**WR-05, decided here.** Every datetime read out of a row passes through
`_aware()` before an entity is constructed, and a naive one raises
`NaiveDatetimeFromDatabaseError`. That refines D-14 by scope rather than by
error type: a naive datetime arriving from *outside* the process is still a
domain `ValidationError`, because it is a caller's malformed input. A naive
datetime arriving *from the database* is something else entirely - the schema
promises `TIMESTAMP WITH TIME ZONE` (D-11), so a naive value means the schema
regressed, and reporting that to a client as a validation problem with their
input would send them hunting for a mistake they did not make. The mapper simply
never lets one get as far as the domain.

Nothing above `infrastructure` is imported here. The mapper speaks entities and
rows, and knows about neither use cases nor HTTP.
"""

from datetime import datetime
from typing import overload

from taskmanager.domain.entities.task import Task
from taskmanager.domain.entities.task_list import TaskList
from taskmanager.domain.entities.user import User
from taskmanager.domain.value_objects.task_priority import TaskPriority
from taskmanager.domain.value_objects.task_status import TaskStatus
from taskmanager.infrastructure.db.errors import NaiveDatetimeFromDatabaseError
from taskmanager.infrastructure.db.models import TaskListRow, TaskRow, UserRow


@overload
def _aware(value: datetime, *, column: str) -> datetime: ...


@overload
def _aware(value: None, *, column: str) -> None: ...


def _aware(value: datetime | None, *, column: str) -> datetime | None:
    """Return a timestamp read from a row, refusing a naive one (WR-05).

    The two overloads above are what keep the nullable columns honest: passing
    `due_date` through returns `datetime | None` and passing `created_at`
    through returns `datetime`, so neither call site needs a cast and neither
    can silently widen a required field into an optional one.

    The awareness test is `utcoffset()` rather than `tzinfo is not None`,
    matching `domain.validation.require_utc`: a `tzinfo` object is allowed to
    return `None` for a given instant, and such a value is naive in every way
    that matters while looking aware to a shallower check.
    """
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise NaiveDatetimeFromDatabaseError(column=column)
    return value


def user_to_row(user: User) -> UserRow:
    """Build the row that persists this user, field by explicit field."""
    return UserRow(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        password_hash=user.password_hash,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


def user_to_entity(row: UserRow) -> User:
    """Rehydrate the user this row stores."""
    return User(
        id=row.id,
        email=row.email,
        full_name=row.full_name,
        password_hash=row.password_hash,
        created_at=_aware(row.created_at, column="users.created_at"),
        updated_at=_aware(row.updated_at, column="users.updated_at"),
    )


def apply_user_to_row(user: User, row: UserRow) -> None:
    """Write the user's current values onto the row already in the session."""
    # `row.id` is deliberately not reassigned. It is the primary key of a row
    # the session is tracking; writing to it would make SQLAlchemy emit an
    # UPDATE of the identity itself rather than of the record it names.
    row.email = user.email
    row.full_name = user.full_name
    row.password_hash = user.password_hash
    row.created_at = user.created_at
    row.updated_at = user.updated_at


def task_list_to_row(task_list: TaskList) -> TaskListRow:
    """Build the row that persists this list, field by explicit field."""
    return TaskListRow(
        id=task_list.id,
        owner_id=task_list.owner_id,
        name=task_list.name,
        description=task_list.description,
        created_at=task_list.created_at,
        updated_at=task_list.updated_at,
    )


def task_list_to_entity(row: TaskListRow) -> TaskList:
    """Rehydrate the list this row stores, without touching its tasks.

    `TaskListRow.tasks` is declared `lazy="raise"`, and nothing below reads it:
    the aggregate this project persists is the list itself, and the tasks are
    loaded by their own repository when a use case asks for them.
    """
    return TaskList(
        id=row.id,
        owner_id=row.owner_id,
        name=row.name,
        description=row.description,
        created_at=_aware(row.created_at, column="task_lists.created_at"),
        updated_at=_aware(row.updated_at, column="task_lists.updated_at"),
    )


def apply_task_list_to_row(task_list: TaskList, row: TaskListRow) -> None:
    """Write the list's current values onto the row already in the session."""
    # `row.id` is deliberately not reassigned, for the reason given in
    # `apply_user_to_row`. Neither is `owner_id`: ownership is fixed at
    # creation, and no use case in the roadmap transfers a list.
    row.name = task_list.name
    row.description = task_list.description
    row.created_at = task_list.created_at
    row.updated_at = task_list.updated_at


def task_to_row(task: Task) -> TaskRow:
    """Build the row that persists this task, with both enums as strings."""
    return TaskRow(
        id=task.id,
        task_list_id=task.task_list_id,
        title=task.title,
        description=task.description,
        status=task.status.value,
        priority=task.priority.value,
        due_date=task.due_date,
        assignee_id=task.assignee_id,
        created_at=task.created_at,
        updated_at=task.updated_at,
        completed_at=task.completed_at,
    )


def task_to_entity(row: TaskRow) -> Task:
    """Rehydrate the task this row stores, rebuilding both enums."""
    return Task(
        id=row.id,
        task_list_id=row.task_list_id,
        title=row.title,
        # Re-validated rather than trusted: `TaskStatus("nonsense")` raises
        # here, where the row is still identifiable, instead of producing an
        # entity whose state machine has a member nothing can transition out of.
        status=TaskStatus(row.status),
        priority=TaskPriority(row.priority),
        created_at=_aware(row.created_at, column="tasks.created_at"),
        updated_at=_aware(row.updated_at, column="tasks.updated_at"),
        description=row.description,
        due_date=_aware(row.due_date, column="tasks.due_date"),
        completed_at=_aware(row.completed_at, column="tasks.completed_at"),
        assignee_id=row.assignee_id,
    )


def apply_task_to_row(task: Task, row: TaskRow) -> None:
    """Write the task's current values onto the row already in the session."""
    # `row.id` is deliberately not reassigned, for the reason given in
    # `apply_user_to_row`. `task_list_id` is written, because moving a task
    # between lists is an ordinary update rather than a change of identity.
    row.task_list_id = task.task_list_id
    row.title = task.title
    row.description = task.description
    row.status = task.status.value
    row.priority = task.priority.value
    row.due_date = task.due_date
    row.assignee_id = task.assignee_id
    row.created_at = task.created_at
    row.updated_at = task.updated_at
    row.completed_at = task.completed_at
