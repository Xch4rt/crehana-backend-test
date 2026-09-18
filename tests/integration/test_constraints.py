"""DB-04 and DB-05, proven the only way they can be: by statements PostgreSQL refused.

`alembic check` is blind here. Autogenerate does not compare `CHECK` constraints
at all - SQLAlchemy does not reflect them into a comparable form - so a revision
that dropped `ck_tasks_status` tomorrow would be reported as no drift whatsoever,
and `test_migrations.py` would stay green while the database quietly accepted any
string at all. The same is true of the `ON DELETE` actions: they are visible to
reflection, which `test_schema.py` asserts, but "the catalogue says CASCADE" and
"deleting a list really removes its tasks" are different claims, and only the
second one is what DB-05 promises.

So every test below writes something. Half of them write something the database
must refuse, and assert on the *name* it refused under - read with
`violated_constraint()`, the same function D-13 will use to turn these failures
into domain errors, so a rename that breaks the translation breaks this suite
first. Asserting merely that `IntegrityError` was raised would pass for a
violation of any other constraint in the schema, including one the test did not
intend to touch.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection

from taskmanager.infrastructure.db.constraints import (
    CK_TASKS_COMPLETED_AT_MATCHES_STATUS,
    CK_TASKS_PRIORITY,
    CK_TASKS_STATUS,
    FK_TASKS_TASK_LIST_ID_TASK_LISTS,
    UQ_TASK_LISTS_OWNER_ID_NAME,
    UQ_USERS_EMAIL_LOWER,
)
from taskmanager.infrastructure.db.errors import violated_constraint

pytestmark = pytest.mark.integration

# Fixed identifiers, never generated ones: a UUID produced at run time would make
# an assertion about "the list that was deleted" true of whatever row happened to
# be there, and the cascade tests below are exactly the place that matters.
OWNER_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")
OTHER_OWNER_ID = uuid.UUID("00000000-0000-4000-8000-000000000002")
ASSIGNEE_ID = uuid.UUID("00000000-0000-4000-8000-000000000003")
LIST_ID = uuid.UUID("00000000-0000-4000-8000-000000000011")
OTHER_LIST_ID = uuid.UUID("00000000-0000-4000-8000-000000000012")
MISSING_LIST_ID = uuid.UUID("00000000-0000-4000-8000-0000000000ff")
TASK_ID = uuid.UUID("00000000-0000-4000-8000-000000000021")
OTHER_TASK_ID = uuid.UUID("00000000-0000-4000-8000-000000000022")

NOW = datetime(2026, 3, 14, 15, 9, 26, tzinfo=UTC)
PASSWORD_HASH = "argon2-placeholder-hash-value"
OWNER_EMAIL = "owner@example.test"

INSERT_USER = (
    "INSERT INTO users (id, email, password_hash, created_at, updated_at) "
    "VALUES (:id, :email, :password_hash, :created_at, :updated_at)"
)
INSERT_TASK_LIST = (
    "INSERT INTO task_lists (id, owner_id, name, created_at, updated_at) "
    "VALUES (:id, :owner_id, :name, :created_at, :updated_at)"
)
INSERT_TASK = (
    "INSERT INTO tasks "
    "(id, task_list_id, title, status, priority, assignee_id, "
    "created_at, updated_at, completed_at) "
    "VALUES (:id, :task_list_id, :title, :status, :priority, :assignee_id, "
    ":created_at, :updated_at, :completed_at)"
)


def user_values(
    *, user_id: uuid.UUID = OWNER_ID, email: str = OWNER_EMAIL
) -> dict[str, Any]:
    """Bound parameters for one valid `users` row."""
    return {
        "id": user_id,
        "email": email,
        "password_hash": PASSWORD_HASH,
        "created_at": NOW,
        "updated_at": NOW,
    }


def task_list_values(
    *,
    list_id: uuid.UUID = LIST_ID,
    owner_id: uuid.UUID = OWNER_ID,
    name: str = "Groceries",
) -> dict[str, Any]:
    """Bound parameters for one valid `task_lists` row."""
    return {
        "id": list_id,
        "owner_id": owner_id,
        "name": name,
        "created_at": NOW,
        "updated_at": NOW,
    }


def task_values(
    *,
    task_id: uuid.UUID = TASK_ID,
    task_list_id: uuid.UUID = LIST_ID,
    title: str = "Buy milk",
    status: str = "pending",
    priority: str = "medium",
    assignee_id: uuid.UUID | None = None,
    completed_at: datetime | None = None,
) -> dict[str, Any]:
    """Bound parameters for one `tasks` row, valid unless an argument says otherwise."""
    return {
        "id": task_id,
        "task_list_id": task_list_id,
        "title": title,
        "status": status,
        "priority": priority,
        "assignee_id": assignee_id,
        "created_at": NOW,
        "updated_at": NOW,
        "completed_at": completed_at,
    }


async def given_a_list_with_an_owner(connection: AsyncConnection) -> None:
    """The minimum valid world: one user, owning one list named `Groceries`.

    The identifiers are the module constants above rather than a return value.
    Handing them back would read as if a test could be given different ones,
    which is precisely what the fixed literals are there to prevent.
    """
    await connection.execute(text(INSERT_USER), user_values())
    await connection.execute(text(INSERT_TASK_LIST), task_list_values())


async def refused(
    connection: AsyncConnection, statement: str, parameters: dict[str, Any]
) -> IntegrityError:
    """Run a statement PostgreSQL must reject, and hand back the rejection.

    The savepoint is the load-bearing part, and the reason this helper exists at
    all. A statement PostgreSQL refuses aborts the whole transaction: every later
    statement on the same connection answers `current transaction is aborted`
    until it is unwound. The transaction here belongs to the `connection` fixture
    and has to survive to the end of the test, so each expected failure gets its
    own savepoint, which is rolled back to on the way out. That is what lets a
    test build its rows, watch one statement be refused, and still read the table
    afterwards.

    Every statement is `text()` with bound parameters - never an interpolated
    string. These tests author their own SQL, so nothing here is attacker
    controlled, but the discipline is the same one the Phase 4 filter endpoints
    will need, and a test file is a poor place to demonstrate the other habit.
    """
    with pytest.raises(IntegrityError) as raised:
        async with connection.begin_nested():
            await connection.execute(text(statement), parameters)
    return raised.value


async def test_a_task_status_outside_the_enumeration_is_refused(
    connection: AsyncConnection,
) -> None:
    """DB-04: `status` is a VARCHAR, and `ck_tasks_status` is what makes it an enum."""
    await given_a_list_with_an_owner(connection)

    error = await refused(connection, INSERT_TASK, task_values(status="archived"))

    assert violated_constraint(error) == CK_TASKS_STATUS


async def test_a_task_priority_outside_the_enumeration_is_refused(
    connection: AsyncConnection,
) -> None:
    """DB-04: the same argument for the second enumerated column."""
    await given_a_list_with_an_owner(connection)

    error = await refused(connection, INSERT_TASK, task_values(priority="urgent"))

    assert violated_constraint(error) == CK_TASKS_PRIORITY


async def test_a_completed_task_without_a_completion_timestamp_is_refused(
    connection: AsyncConnection,
) -> None:
    """The database copy of the entity invariant at `task.py` L83-87.

    `Task.__post_init__` already refuses this, so the constraint is not what
    protects a request that came through a use case. It protects the rows: a
    direct `UPDATE`, a future bulk operation or a repository that skipped the
    entity would otherwise be able to write a state the domain says cannot exist.
    """
    await given_a_list_with_an_owner(connection)

    error = await refused(
        connection, INSERT_TASK, task_values(status="completed", completed_at=None)
    )

    assert violated_constraint(error) == CK_TASKS_COMPLETED_AT_MATCHES_STATUS


async def test_a_pending_task_with_a_completion_timestamp_is_refused(
    connection: AsyncConnection,
) -> None:
    """The other direction of the same equivalence.

    The constraint is written with `=` between two boolean expressions rather
    than as an implication, so it refuses both halves: a completed task with no
    timestamp, and a timestamp on a task that is not completed.
    """
    await given_a_list_with_an_owner(connection)

    error = await refused(
        connection, INSERT_TASK, task_values(status="pending", completed_at=NOW)
    )

    assert violated_constraint(error) == CK_TASKS_COMPLETED_AT_MATCHES_STATUS


async def test_two_lists_with_the_same_name_for_one_owner_are_refused(
    connection: AsyncConnection,
) -> None:
    """The race-proof backstop behind LIST-06's 409 (D-12).

    A use-case pre-check cannot provide this on its own: two concurrent requests
    both read "no such name" and both proceed. The unique constraint is what makes
    the second one fail, and D-13 is what turns that failure back into the same
    409 the pre-check would have produced.
    """
    await given_a_list_with_an_owner(connection)

    error = await refused(
        connection,
        INSERT_TASK_LIST,
        task_list_values(list_id=OTHER_LIST_ID, name="Groceries"),
    )

    assert violated_constraint(error) == UQ_TASK_LISTS_OWNER_ID_NAME


async def test_the_same_name_in_a_different_case_is_allowed_for_one_owner(
    connection: AsyncConnection,
) -> None:
    """List-name uniqueness is case-SENSITIVE, and that is a decision, not an oversight.

    `TaskList` folds no case, so `Groceries` and `groceries` are two distinct
    names to the domain; an index over `lower(name)` would refuse a value the
    entity considers perfectly new. The deliberate contrast is `users.email`,
    where `User` lowercases the address on construction and the index below
    defends a rule the entity already enforces.
    """
    await given_a_list_with_an_owner(connection)

    await connection.execute(
        text(INSERT_TASK_LIST),
        task_list_values(list_id=OTHER_LIST_ID, name="groceries"),
    )

    names = (
        await connection.execute(
            text(
                "SELECT name FROM task_lists WHERE owner_id = :owner_id ORDER BY name"
            ),
            {"owner_id": OWNER_ID},
        )
    ).scalars()
    assert list(names) == ["Groceries", "groceries"]


async def test_the_same_name_is_allowed_for_a_different_owner(
    connection: AsyncConnection,
) -> None:
    """Uniqueness is per owner: two people may both keep a list called `Groceries`."""
    await given_a_list_with_an_owner(connection)
    await connection.execute(
        text(INSERT_USER),
        user_values(user_id=OTHER_OWNER_ID, email="other@example.test"),
    )

    await connection.execute(
        text(INSERT_TASK_LIST),
        task_list_values(list_id=OTHER_LIST_ID, owner_id=OTHER_OWNER_ID),
    )

    count = await connection.scalar(
        text("SELECT count(*) FROM task_lists WHERE name = :name"),
        {"name": "Groceries"},
    )
    assert count == 2


async def test_two_users_whose_emails_differ_only_in_case_are_refused(
    connection: AsyncConnection,
) -> None:
    """D-12: `uq_users_email_lower` is an expression index over `lower(email)`."""
    await connection.execute(text(INSERT_USER), user_values())

    error = await refused(
        connection,
        INSERT_USER,
        user_values(user_id=OTHER_OWNER_ID, email=OWNER_EMAIL.upper()),
    )

    assert violated_constraint(error) == UQ_USERS_EMAIL_LOWER


async def test_deleting_a_task_list_cascades_to_its_tasks(
    connection: AsyncConnection,
) -> None:
    """DB-05, the requirement stated as a behaviour rather than as DDL."""
    await given_a_list_with_an_owner(connection)
    await connection.execute(text(INSERT_TASK), task_values())
    await connection.execute(
        text(INSERT_TASK), task_values(task_id=OTHER_TASK_ID, title="Buy bread")
    )

    await connection.execute(
        text("DELETE FROM task_lists WHERE id = :id"), {"id": LIST_ID}
    )

    orphans = await connection.scalar(
        text("SELECT count(*) FROM tasks WHERE task_list_id = :id"), {"id": LIST_ID}
    )
    assert orphans == 0


async def test_deleting_a_user_cascades_to_their_task_lists(
    connection: AsyncConnection,
) -> None:
    """`task_lists.owner_id` cascades, so a list cannot outlive its owner."""
    await given_a_list_with_an_owner(connection)
    await connection.execute(text(INSERT_TASK), task_values())

    await connection.execute(text("DELETE FROM users WHERE id = :id"), {"id": OWNER_ID})

    remaining_lists = await connection.scalar(
        text("SELECT count(*) FROM task_lists WHERE owner_id = :id"), {"id": OWNER_ID}
    )
    remaining_tasks = await connection.scalar(
        text("SELECT count(*) FROM tasks WHERE task_list_id = :id"), {"id": LIST_ID}
    )
    # The second cascade follows the first: the list goes with the user, and the
    # tasks go with the list. Two hops, one DELETE.
    assert remaining_lists == 0
    assert remaining_tasks == 0


async def test_deleting_an_assignee_leaves_the_task_with_a_null_assignee(
    connection: AsyncConnection,
) -> None:
    """`tasks.assignee_id` is ON DELETE SET NULL, and the difference matters.

    Deleting a user must not delete the work they were assigned - that work
    belongs to a list, which belongs to somebody else. It only stops being
    assigned.
    """
    await given_a_list_with_an_owner(connection)
    await connection.execute(
        text(INSERT_USER),
        user_values(user_id=ASSIGNEE_ID, email="assignee@example.test"),
    )
    await connection.execute(text(INSERT_TASK), task_values(assignee_id=ASSIGNEE_ID))

    await connection.execute(
        text("DELETE FROM users WHERE id = :id"), {"id": ASSIGNEE_ID}
    )

    row = (
        await connection.execute(
            text("SELECT title, assignee_id FROM tasks WHERE id = :id"),
            {"id": TASK_ID},
        )
    ).one_or_none()
    assert row is not None
    assert row.title == "Buy milk"
    assert row.assignee_id is None


async def test_a_task_in_a_missing_list_is_refused(
    connection: AsyncConnection,
) -> None:
    """The failure D-13 will translate into the list-not-found error.

    It also settles RESEARCH assumption A2 empirically: psycopg populates
    `diag.constraint_name` for foreign-key violations too, not only for unique
    and check ones. `violated_constraint()` is unit-tested only on its `None`
    paths - a populated `Diagnostic` has no public constructor - so this is the
    first place in the project where its positive branch actually runs.
    """
    await given_a_list_with_an_owner(connection)

    error = await refused(
        connection, INSERT_TASK, task_values(task_list_id=MISSING_LIST_ID)
    )

    assert violated_constraint(error) == FK_TASKS_TASK_LIST_ID_TASK_LISTS
