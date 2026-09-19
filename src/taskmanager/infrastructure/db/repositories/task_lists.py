"""The `TaskListRepository` adapter: rows in, entities out, no transaction.

Two shapes are rejected here, and the reasons are the whole substance of this
module.

The first is a repository that makes its own writes durable. It would turn
`async with uow:` into a claim the use case cannot check - a failure later in
the block would undo the part of the work that was still pending and leave the
rest standing, and no test above this layer could tell the difference. The
transaction boundary belongs to the use case (ARC-08, roadmap SC-4), so every
method below writes, flushes, and stops.
`tests/architecture/test_no_commit_in_repositories.py` fails if any line under
this package ever says otherwise.

The second is a repository that hands back ORM rows. A row is attached to a
session, so reading one of its attributes after that session is gone emits SQL
from wherever the use case happens to be standing - under asyncio, a
`MissingGreenlet` raised in front of a user. Every method here returns the plain
dataclasses `mappers.py` builds, whose fields are all materialised before the
value leaves, which is what makes roadmap SC-2 a property a test can assert
rather than a habit.

`flush()` appears in every write path on purpose, and it is load-bearing rather
than tidy. It is what makes PostgreSQL refuse the statement *here*, while the
constraint name still says which aggregate and which rule were violated, instead
of at the unit of work's transaction boundary, where the failure has lost its
author and D-13's per-repository translation would have to be guessed from a
name alone.
"""

from collections.abc import Sequence
from typing import NoReturn
from uuid import UUID

from sqlalchemy import Select, delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from taskmanager.domain.entities.task_list import TaskList
from taskmanager.domain.exceptions import (
    DuplicateTaskListNameError,
    TaskListNotFoundError,
    UserNotFoundError,
)
from taskmanager.domain.value_objects.completion import CompletionStats
from taskmanager.domain.value_objects.task_status import TaskStatus
from taskmanager.infrastructure.db.constraints import (
    FK_TASK_LISTS_OWNER_ID_USERS,
    UQ_TASK_LISTS_OWNER_ID_NAME,
)
from taskmanager.infrastructure.db.errors import violated_constraint
from taskmanager.infrastructure.db.mappers import (
    apply_task_list_to_row,
    task_list_to_entity,
    task_list_to_row,
)
from taskmanager.infrastructure.db.models import TaskListRow, TaskRow


def lists_with_stats_statement(owner_id: UUID) -> Select[tuple[TaskListRow, int, int]]:
    """LIST-03 in one statement: every list of one owner, with its two counters.

    A module-level function for the reason `completion_statement` in `tasks.py`
    is one, and the argument is the whole point of the shape: the SQL it produces
    can be compiled and asserted on with no server at all, so a later refactor
    back into `list_for_owner` plus a `completion_stats` per row fails a test
    rather than a code review. LIST-03 forbids that N+1 explicitly, and an
    intention nothing checks is not a guarantee.

    `count(tasks.id)`, never `count(*)`. A LEFT OUTER JOIN produces one
    null-extended row for a list with no tasks, and `count(*)` counts that row:
    the list would report a total of 1 over a task that does not exist, and a
    percentage computed against it. `count(tasks.id)` skips the NULL and returns
    0, which is what makes an empty list report 0.0.

    `GROUP BY task_lists.id` alone is sufficient, and deliberately not the full
    column list a reader may expect: `id` is the primary key, so PostgreSQL's
    functional-dependency rule makes every other column of that table legal in
    the select list without being grouped by.

    The filter value is `TaskStatus.COMPLETED.value` and travels as a bound
    parameter, like every other value in this package, and the ordering is
    `list_for_owner`'s `(created_at, id)` - D-13's total order, for the reason
    that method's docstring gives.
    """
    return (
        select(
            TaskListRow,
            func.count(TaskRow.id).label("total"),
            func.count(TaskRow.id)
            .filter(TaskRow.status == TaskStatus.COMPLETED.value)
            .label("completed"),
        )
        .outerjoin(TaskRow, TaskRow.task_list_id == TaskListRow.id)
        .where(TaskListRow.owner_id == owner_id)
        .group_by(TaskListRow.id)
        .order_by(TaskListRow.created_at, TaskListRow.id)
    )


class SqlAlchemyTaskListRepository:
    """`TaskListRepository` (D-19) over an `AsyncSession` it does not own.

    No base class: conformance to the port is structural, checked by mypy where
    the unit of work assigns this object to a `TaskListRepository`-annotated
    attribute, exactly as the in-memory fakes are checked in Phase 2's tests.
    """

    def __init__(self, session: AsyncSession) -> None:
        # The session is borrowed. Its lifetime, and the decision to make its
        # work permanent, belong to the unit of work that handed it over.
        self._session = session

    async def get(self, task_list_id: UUID) -> TaskList | None:
        """The list with this identifier as an entity, or `None`."""
        row = await self._session.get(TaskListRow, task_list_id)
        return None if row is None else task_list_to_entity(row)

    async def add(self, task_list: TaskList) -> None:
        """Insert the list, translating the two collisions it can cause."""
        self._session.add(task_list_to_row(task_list))
        try:
            # See the module docstring: the flush is what surfaces the violation
            # in this method, where the constraint name is still meaningful.
            await self._session.flush()
        except IntegrityError as error:
            self._refused(error, task_list)

    async def update(self, task_list: TaskList) -> None:
        """Write the entity's current values onto the row already stored.

        The row is loaded rather than replaced, because the session is tracking
        it; `apply_task_list_to_row` is the in-place half of the mapper pair that
        exists for exactly this call.
        """
        row = await self._session.get(TaskListRow, task_list.id)
        if row is None:
            raise TaskListNotFoundError(task_list.id)
        apply_task_list_to_row(task_list, row)
        try:
            # A rename can collide with a sibling just as an insert can, so the
            # same translation applies here rather than a narrower one.
            await self._session.flush()
        except IntegrityError as error:
            self._refused(error, task_list)

    async def delete(self, task_list_id: UUID) -> None:
        """Remove the list, and say nothing if there was none to remove.

        Deleting an identifier that is not there is a no-op, matching
        `FakeTaskListRepository.delete`. Whether a missing list is a 404 is the
        use case's decision (ADR-008): it is the only layer that knows whether
        the caller was allowed to see the list in the first place, and an adapter
        that raised here would take that decision away from it.
        """
        await self._session.execute(
            delete(TaskListRow).where(TaskListRow.id == task_list_id)
        )
        await self._session.flush()

    async def list_for_owner(self, owner_id: UUID) -> Sequence[TaskList]:
        """Every list this owner has, oldest first.

        The ordering is not decoration. An unordered `SELECT` may come back in
        any order PostgreSQL finds convenient, which would make a Phase 4
        assertion about the first element of a list response pass on one run and
        fail on the next. The owner filter is in SQL rather than in a
        comprehension over a full read, so no caller can accidentally perform an
        unscoped one (ADR-008).

        `id` is the tie-break, and it is what makes the ordering *total*
        (review fix WR-03). `created_at` alone is not: D-13 has the use case
        read the clock once per request, so two lists created in one call carry
        the same instant to the microsecond, and PostgreSQL is then free to
        return them either way round - by index order, by physical order, by
        whatever the plan happened to be - and to choose differently on the next
        run. The same pair appears in
        `SqlAlchemyTaskRepository.list_for_task_list` for the same reason.
        """
        statement = (
            select(TaskListRow)
            .where(TaskListRow.owner_id == owner_id)
            .order_by(TaskListRow.created_at, TaskListRow.id)
        )
        rows = await self._session.scalars(statement)
        return [task_list_to_entity(row) for row in rows]

    async def list_for_owner_with_stats(
        self, owner_id: UUID
    ) -> Sequence[tuple[TaskList, CompletionStats]]:
        """Every list this owner has and how far through it they are (LIST-03).

        One round trip, from the grouped statement above. The shape this replaces
        is `list_for_owner` followed by a `completion_stats` call per row, which
        answers the same thing and issues one query per list - the N+1 LIST-03
        names, and a read amplification a caller with many lists can trigger at
        will (T-4-08).

        The relationship is never touched: `TaskListRow.tasks` is `lazy="raise"`,
        and the counters come from the join rather than from loading children the
        caller did not ask for. Nothing is flushed and nothing is committed - this
        is a read, and the transaction belongs to the unit of work.

        The two counters are handed to `CompletionStats` as they arrive, for the
        reason `SqlAlchemyTaskRepository.completion_stats` records: psycopg
        decodes `bigint` as a Python `int`, a test asserts that rather than
        assuming it, and a silent `int(...)` here would hide the day it stops
        being true.
        """
        rows = await self._session.execute(lists_with_stats_statement(owner_id))
        return [
            (
                task_list_to_entity(row),
                CompletionStats(total=total, completed=completed),
            )
            for row, total, completed in rows
        ]

    async def exists_with_name(self, owner_id: UUID, name: str) -> bool:
        """Whether this owner already has a list under exactly this name.

        Case-SENSITIVE, because `uq_task_lists_owner_id_name` is the plain
        `UNIQUE (owner_id, name)` of D-12 and `TaskList` folds no case on its
        name - the deliberate contrast with `uq_users_email_lower`, where the
        entity does canonicalise and the index defends that rule. A
        case-insensitive check here would refuse a list the database would have
        accepted. Only the argument is stripped: the stored value was trimmed by
        `require_text` before it was ever written.
        """
        statement = (
            select(func.count())
            .select_from(TaskListRow)
            .where(
                TaskListRow.owner_id == owner_id,
                TaskListRow.name == name.strip(),
            )
        )
        count = await self._session.scalar(statement)
        return count is not None and count > 0

    def _refused(self, error: IntegrityError, task_list: TaskList) -> NoReturn:
        """Re-raise a refusal as the error it means, or exactly as it arrived.

        Written once and called from both write paths, rather than copied into
        each: a second copy would be a second place for the constraint-name
        comparison to fall out of date, and it would also leave one of the two
        branches unreachable in whichever method cannot cause that collision.

        An unrecognised constraint is re-raised untouched, which is D-13's
        instruction and not a gap. `violated_constraint` returning `None` means
        *unknowable*, never *no conflict*, and inventing a business meaning for a
        failure nothing here recognises is how a driver message ends up in a
        response body. Untranslated, it reaches Phase 2's catch-all and becomes
        the fixed 500 with no detail at all (T-3-14).
        """
        refused_by = violated_constraint(error)
        if refused_by == UQ_TASK_LISTS_OWNER_ID_NAME:
            raise DuplicateTaskListNameError(task_list.name) from error
        if refused_by == FK_TASK_LISTS_OWNER_ID_USERS:
            raise UserNotFoundError(task_list.owner_id) from error
        raise error
