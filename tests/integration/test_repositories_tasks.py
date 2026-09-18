"""The task adapter against a real server: SC-2, D-13, and what is not translated.

The properties proven here are the ones no in-memory fake can reach. An entity
handed back is readable after the session that produced it is gone (roadmap
SC-2). A dangling reference becomes the `NotFoundError` it means, and names the
right aggregate: a task pointing at a list that is not there is a different
answer from a task pointing at an assignee who is not there, and only a real
foreign key can tell the two apart (D-13).

The third property is the one specific to this aggregate: a `CHECK` violation is
asserted to escape *un*translated. `tasks` is the only table with `CHECK`
constraints, and they duplicate invariants `Task.__post_init__` already enforces,
so a refusal from one of them means the entity was bypassed. That is a defect in
the process rather than a decision a caller made, and the test below pins it as
such by asserting on the constraint PostgreSQL named.

Every write goes through the repository, and nothing here commits. The
`connection` fixture's outer transaction is rolled back at teardown, so a stray
transaction boundary inside the adapter would leave rows the next test would
see - which is the isolation contract D-01 buys, and the reason nothing here
cleans up after itself.
"""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, AsyncSessionTransaction

from taskmanager.domain.entities.task import Task
from taskmanager.domain.entities.task_list import TaskList
from taskmanager.domain.entities.user import User
from taskmanager.domain.exceptions import (
    TaskListNotFoundError,
    TaskNotFoundError,
    UserNotFoundError,
)
from taskmanager.domain.value_objects.task_priority import TaskPriority
from taskmanager.domain.value_objects.task_status import TaskStatus
from taskmanager.infrastructure.db.constraints import CK_TASKS_STATUS
from taskmanager.infrastructure.db.errors import violated_constraint
from taskmanager.infrastructure.db.mappers import task_list_to_row, user_to_row
from taskmanager.infrastructure.db.models import TaskRow
from taskmanager.infrastructure.db.repositories.tasks import SqlAlchemyTaskRepository

pytestmark = pytest.mark.integration

# Fixed identifiers and fixed instants, never generated ones: a value produced at
# run time would make an assertion about "the task that was completed" true of
# whatever row happened to be there, and the ordering and aggregate tests are
# exactly where that would stop being noticed.
OWNER_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")
ASSIGNEE_ID = uuid.UUID("00000000-0000-4000-8000-000000000003")
MISSING_USER_ID = uuid.UUID("00000000-0000-4000-8000-0000000000fe")
LIST_ID = uuid.UUID("00000000-0000-4000-8000-000000000011")
OTHER_LIST_ID = uuid.UUID("00000000-0000-4000-8000-000000000012")
MISSING_LIST_ID = uuid.UUID("00000000-0000-4000-8000-0000000000ff")
TASK_ID = uuid.UUID("00000000-0000-4000-8000-000000000021")
OTHER_TASK_ID = uuid.UUID("00000000-0000-4000-8000-000000000022")
MISSING_TASK_ID = uuid.UUID("00000000-0000-4000-8000-0000000000fd")

NOW = datetime(2026, 3, 14, 15, 9, 26, 535897, tzinfo=UTC)
EARLIER = datetime(2026, 3, 13, 9, 0, 0, tzinfo=UTC)
LATER = datetime(2026, 3, 15, 9, 0, 0, tzinfo=UTC)

PASSWORD_HASH = "argon2-placeholder-hash-value"
OWNER_EMAIL = "owner@example.test"
ASSIGNEE_EMAIL = "assignee@example.test"


def refused(session: AsyncSession) -> AsyncSessionTransaction:
    """A savepoint around work PostgreSQL is expected to reject.

    A refused statement aborts the transaction it ran in: every later statement
    answers `current transaction is aborted` until it is unwound, and the
    transaction here belongs to the `connection` fixture, which has to keep it
    until teardown. Running the expected failure inside a savepoint means the
    rollback stops at that savepoint, so a test can watch a statement be refused
    and then keep reading the table. Same helper, same argument, as
    `test_repositories_task_lists.py` and `test_constraints.py`.
    """
    return session.begin_nested()


def a_task(
    *,
    task_id: uuid.UUID = TASK_ID,
    task_list_id: uuid.UUID = LIST_ID,
    title: str = "Buy milk",
    description: str | None = "Semi-skimmed, two litres",
    status: TaskStatus = TaskStatus.PENDING,
    priority: TaskPriority = TaskPriority.MEDIUM,
    due_date: datetime | None = LATER,
    assignee_id: uuid.UUID | None = ASSIGNEE_ID,
    completed_at: datetime | None = None,
    created_at: datetime = NOW,
) -> Task:
    """A valid task entity, differing from the default only where asked."""
    return Task(
        id=task_id,
        task_list_id=task_list_id,
        title=title,
        status=status,
        priority=priority,
        created_at=created_at,
        updated_at=created_at,
        description=description,
        due_date=due_date,
        completed_at=completed_at,
        assignee_id=assignee_id,
    )


async def given_a_list_with_an_owner(session: AsyncSession) -> None:
    """The minimum valid world: two users, and two lists owned by the first.

    Written through the mappers and the session rather than through the sibling
    adapters, following `test_repositories_task_lists.py`: this module tests one
    adapter, and a fault in `task_lists.py` or `users.py` should not be able to
    make these tests red while pointing at the wrong file.

    Both users exist because `tasks.assignee_id` is a foreign key too, and both
    lists exist because the scoping tests need a second one to keep rows out of.

    The users are flushed before the lists are even added. SQLAlchemy orders a
    flush by the dependencies it knows about, and it knows about a `relationship`
    - there is none between `UserRow` and `TaskListRow`, only a plain foreign
    key, so with both pending in one flush it emitted the lists first and
    PostgreSQL refused them. Two flushes, in the order the references point.
    """
    for user_id, email in ((OWNER_ID, OWNER_EMAIL), (ASSIGNEE_ID, ASSIGNEE_EMAIL)):
        session.add(
            user_to_row(
                User(
                    id=user_id,
                    email=email,
                    password_hash=PASSWORD_HASH,
                    created_at=NOW,
                    updated_at=NOW,
                )
            )
        )
    await session.flush()
    for list_id, name in ((LIST_ID, "Groceries"), (OTHER_LIST_ID, "Chores")):
        session.add(
            task_list_to_row(
                TaskList(
                    id=list_id,
                    owner_id=OWNER_ID,
                    name=name,
                    description=None,
                    created_at=NOW,
                    updated_at=NOW,
                )
            )
        )
    await session.flush()


async def test_a_stored_task_comes_back_as_a_domain_entity(
    session: AsyncSession,
) -> None:
    """What goes in as an entity comes back as one, never as a row (DB-03).

    Every optional column is populated, because a mapper that dropped one of
    them would still satisfy a round trip of the required fields. The two enums
    are asserted with `is`: `TaskStatus` is a `StrEnum`, so the plain string
    `"completed"` would satisfy `==` while being exactly the value
    `task_to_entity` exists to reject.
    """
    await given_a_list_with_an_owner(session)
    repository = SqlAlchemyTaskRepository(session)

    await repository.add(
        a_task(
            status=TaskStatus.COMPLETED, priority=TaskPriority.HIGH, completed_at=NOW
        )
    )
    fetched = await repository.get(TASK_ID)

    # `type(...) is Task` rather than the `not isinstance(..., TaskRow)` the
    # task-list suite uses: mypy with `warn_unreachable` proves that comparison
    # can never be true here (`Task` and `TaskRow` have incompatible method
    # signatures, so no object can be both) and rejects it as dead code. The
    # exact-type check makes the same claim and is one mypy cannot resolve away.
    assert type(fetched) is Task
    assert fetched.title == "Buy milk"
    assert fetched.description == "Semi-skimmed, two litres"
    assert fetched.task_list_id == LIST_ID
    assert fetched.assignee_id == ASSIGNEE_ID
    assert fetched.due_date == LATER
    assert fetched.completed_at == NOW
    assert fetched.status is TaskStatus.COMPLETED
    assert fetched.priority is TaskPriority.HIGH
    assert await repository.get(MISSING_TASK_ID) is None


async def test_a_returned_task_is_readable_after_the_session_is_gone(
    session: AsyncSession,
) -> None:
    """Roadmap SC-2: every field is readable once the session has closed.

    It cannot raise, and the reason is structural rather than lucky: the
    repository returns a plain dataclass whose every field was copied out of the
    row while the session was open. There is no instrumented attribute left to
    load, so there is no SQL to emit from outside the greenlet context and no
    `MissingGreenlet` to raise. An adapter that returned the row instead would
    fail this test at the first attribute read below.
    """
    await given_a_list_with_an_owner(session)
    repository = SqlAlchemyTaskRepository(session)
    await repository.add(a_task())
    fetched = await repository.get(TASK_ID)
    assert fetched is not None

    await session.close()

    assert fetched.title == "Buy milk"
    assert fetched.description == "Semi-skimmed, two litres"
    assert fetched.task_list_id == LIST_ID
    assert fetched.assignee_id == ASSIGNEE_ID
    assert fetched.status is TaskStatus.PENDING
    assert fetched.priority is TaskPriority.MEDIUM
    assert fetched.due_date == LATER
    assert fetched.completed_at is None
    assert fetched.created_at == NOW
    assert fetched.updated_at == NOW


async def test_a_task_in_a_missing_list_raises_task_list_not_found(
    session: AsyncSession,
) -> None:
    """D-13: `fk_tasks_task_list_id_task_lists` names the list, not the task.

    The two foreign keys of this table have to be told apart, and the error is
    the only place that distinction survives: a caller who posted to a list that
    does not exist must not be told their assignee is missing.
    """
    await given_a_list_with_an_owner(session)
    repository = SqlAlchemyTaskRepository(session)

    with pytest.raises(TaskListNotFoundError) as raised:
        async with refused(session):
            await repository.add(a_task(task_list_id=MISSING_LIST_ID))

    assert raised.value.details == {"task_list_id": str(MISSING_LIST_ID)}


async def test_a_task_for_a_missing_assignee_raises_user_not_found(
    session: AsyncSession,
) -> None:
    """D-13: the other foreign key, and the other aggregate it names."""
    await given_a_list_with_an_owner(session)
    repository = SqlAlchemyTaskRepository(session)

    with pytest.raises(UserNotFoundError) as raised:
        async with refused(session):
            await repository.add(a_task(assignee_id=MISSING_USER_ID))

    assert raised.value.details == {"user_id": str(MISSING_USER_ID)}


async def test_a_check_constraint_violation_is_not_translated(
    session: AsyncSession,
) -> None:
    """The deliberate gap in the translation, asserted rather than assumed.

    A status outside the enumeration cannot come from an entity - `TaskStatus`
    has three members and `Task` accepts nothing else - so the row is built
    directly, which is the only way this refusal can happen at all. It means
    something bypassed the entity, which is a defect in this process rather than
    a decision a caller made: it must reach Phase 2's catch-all and become the
    fixed 500, not a business error naming a field no request contained.

    The constraint name is asserted as well as the exception type, for
    `test_constraints.py`'s reason: `IntegrityError` alone would also pass for a
    violation this test never intended to cause.
    """
    await given_a_list_with_an_owner(session)
    repository = SqlAlchemyTaskRepository(session)

    with pytest.raises(IntegrityError) as raised:
        async with refused(session):
            # Inside the savepoint, never before it: opening a SAVEPOINT flushes
            # whatever is already pending, so a bad row added beforehand would be
            # refused by the savepoint itself and this test would pass without
            # the repository having run at all (observed in plan 03-06).
            session.add(
                TaskRow(
                    id=OTHER_TASK_ID,
                    task_list_id=LIST_ID,
                    title="Archive the milk",
                    description=None,
                    status="archived",
                    priority="medium",
                    due_date=None,
                    assignee_id=None,
                    created_at=NOW,
                    updated_at=NOW,
                    completed_at=None,
                )
            )
            await repository.add(a_task())

    assert violated_constraint(raised.value) == CK_TASKS_STATUS


async def test_update_persists_every_mutable_field_and_rejects_an_unknown_id(
    session: AsyncSession,
) -> None:
    """Every field `apply_task_to_row` writes is written, and a missing row is not.

    The task is moved between lists and unassigned as well as renamed, because
    both foreign keys are writable on update - that is what makes the same
    translation apply there - and a mapper that quietly skipped one of them would
    pass a rename-only assertion.

    `update()` is the one write path that can fail before it reaches the
    database. Treating a missing row as an insert would turn a use case's
    "modify what I fetched" into "create whatever I was handed", which is how a
    deleted resource comes back to life.
    """
    await given_a_list_with_an_owner(session)
    repository = SqlAlchemyTaskRepository(session)
    await repository.add(
        a_task(status=TaskStatus.COMPLETED, completed_at=NOW, due_date=None)
    )

    stored = await repository.get(TASK_ID)
    assert stored is not None
    stored.rename("Buy oat milk", now=LATER)
    stored.change_status(TaskStatus.IN_PROGRESS, now=LATER)
    stored.reschedule(LATER, now=LATER)
    stored.task_list_id = OTHER_LIST_ID
    stored.assignee_id = None
    stored.priority = TaskPriority.LOW
    stored.description = None
    await repository.update(stored)

    updated = await repository.get(TASK_ID)
    assert updated is not None
    assert updated.title == "Buy oat milk"
    assert updated.description is None
    assert updated.status is TaskStatus.IN_PROGRESS
    assert updated.priority is TaskPriority.LOW
    assert updated.due_date == LATER
    assert updated.task_list_id == OTHER_LIST_ID
    assert updated.assignee_id is None
    assert updated.updated_at == LATER
    # D-03, as stored rather than as computed: leaving `completed` cleared the
    # stamp, and a row that kept it would fail `ck_tasks_completed_at_matches_status`
    # on the way in - so this assertion also proves the flush really happened.
    assert updated.completed_at is None

    with pytest.raises(TaskNotFoundError) as raised:
        await repository.update(a_task(task_id=MISSING_TASK_ID))

    assert raised.value.details == {"task_id": str(MISSING_TASK_ID)}


async def test_moving_a_task_into_a_missing_list_is_refused_the_same_way(
    session: AsyncSession,
) -> None:
    """The update path translates too, and it is not the same code as the insert.

    `add()` and `update()` both hand their `IntegrityError` to one translator, so
    this could look redundant with the insert test above - it is not. The two
    methods reach it through different `try` blocks, and a rewrite that dropped
    the one in `update()` would leave a raw `IntegrityError` travelling up from
    every PATCH in Phase 4 while every test that only exercised `add()` stayed
    green.
    """
    await given_a_list_with_an_owner(session)
    repository = SqlAlchemyTaskRepository(session)
    await repository.add(a_task())

    stored = await repository.get(TASK_ID)
    assert stored is not None
    stored.task_list_id = MISSING_LIST_ID

    with pytest.raises(TaskListNotFoundError):
        async with refused(session):
            await repository.update(stored)


async def test_delete_removes_the_row_and_is_a_no_op_for_an_unknown_id(
    session: AsyncSession,
) -> None:
    """Deleting what is not there raises nothing: the use case owns the 404."""
    await given_a_list_with_an_owner(session)
    repository = SqlAlchemyTaskRepository(session)
    await repository.add(a_task())

    await repository.delete(TASK_ID)
    assert await repository.get(TASK_ID) is None

    await repository.delete(MISSING_TASK_ID)
