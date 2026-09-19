"""The `TaskRepository` adapter: the heaviest of the three, same five moves.

The two shapes `task_lists.py` rejects are rejected here for the same reasons. A
repository that made its own writes durable would take the transaction boundary
away from the use case that owns it (ARC-08, roadmap SC-4), and one that handed
back ORM rows would put a session-bound object in the application layer, where
reading an attribute after the session has gone raises from wherever the use
case happens to be standing. `flush()` in every write path is what keeps a
refusal inside the method that caused it, while the constraint name still says
which rule was broken.

One thing is specific to this aggregate: what the translation deliberately
leaves alone. `tasks` carries three `CHECK` constraints as well as its two
foreign keys, and only the foreign keys become domain errors. A `CHECK` refusal
means a row reached the database in a state `Task.__post_init__` already
refuses - a status or a priority outside the enumeration, or a completion stamp
that disagrees with the status - so it can only have been written by something
that bypassed the entity. That is a defect in this process, not a decision a
caller made, and reporting it as a business error would tell a client to fix a
field their request never contained. Untranslated, it reaches Phase 2's
catch-all and becomes the fixed 500 with no message at all (T-3-14).
"""

from collections.abc import Sequence
from typing import NoReturn
from uuid import UUID

from sqlalchemy import Select, delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from taskmanager.domain.entities.task import Task
from taskmanager.domain.exceptions import (
    TaskListNotFoundError,
    TaskNotFoundError,
    UserNotFoundError,
)
from taskmanager.domain.value_objects.completion import CompletionStats
from taskmanager.domain.value_objects.task_priority import TaskPriority
from taskmanager.domain.value_objects.task_status import TaskStatus
from taskmanager.infrastructure.db.constraints import (
    FK_TASKS_ASSIGNEE_ID_USERS,
    FK_TASKS_TASK_LIST_ID_TASK_LISTS,
)
from taskmanager.infrastructure.db.errors import violated_constraint
from taskmanager.infrastructure.db.mappers import (
    apply_task_to_row,
    task_to_entity,
    task_to_row,
)
from taskmanager.infrastructure.db.models import TaskRow


def completion_statement(task_list_id: UUID) -> Select[tuple[int, int]]:
    """The one statement behind the completion percentage (ADR-009).

    Two counters over one pass of the list's rows: how many tasks there are, and
    how many of them are completed. `count(*) FILTER (WHERE ...)` is what makes
    the second one free - the alternative shapes are two queries, which can
    disagree with each other because they see the table at two different moments,
    or a full read counted in Python, which is Anti-Pattern 8 and turns a number
    into a table scan the moment a list gets long.

    It is a module-level function rather than a few lines inside the method so
    the SQL it produces can be compiled and asserted on with no server at all:
    `test_the_aggregate_is_a_single_statement` fails if a later refactor turns
    this back into two queries. The filter value is `TaskStatus.COMPLETED.value`
    and travels as a bound parameter, like every other value in this package.
    """
    return select(
        func.count().label("total"),
        func.count()
        .filter(TaskRow.status == TaskStatus.COMPLETED.value)
        .label("completed"),
    ).where(TaskRow.task_list_id == task_list_id)


def task_for_update_statement(task_id: UUID) -> Select[tuple[TaskRow]]:
    """The write-path read: one task row, locked until the transaction ends.

    ADR-058, from the Phase 4 review's CR-01. Every mutating use case loads a
    task, asks the entity whether the change is legal and writes the whole entity
    back, so two overlapping requests used to validate against the same stale
    copy - and the second one persisted `completed -> pending`, which the state
    machine forbids, while erasing the first one's completion. `FOR UPDATE` makes
    the second writer wait here, and under READ COMMITTED a statement that waited
    on a row lock re-reads the row once the lock is released, so what it gets back
    is what the first writer committed.

    `populate_existing` is the other half of "latest committed state". A session
    that already held this row in its identity map would otherwise be handed that
    cached object back with its old attribute values, lock or no lock, which is
    the defect again by a quieter road.

    A module-level function for the reason `completion_statement` is one: the SQL
    can be compiled and asserted on with no server, so a refactor that drops the
    lock fails a unit test as well as the two-connection integration test.
    """
    return (
        select(TaskRow)
        .where(TaskRow.id == task_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


class SqlAlchemyTaskRepository:
    """`TaskRepository` (D-19) over an `AsyncSession` it does not own.

    No base class: conformance to the port is structural, checked by mypy where
    the unit of work assigns this object to a `TaskRepository`-annotated
    attribute, exactly as the in-memory fakes are checked in Phase 2's tests.
    """

    def __init__(self, session: AsyncSession) -> None:
        # Borrowed, as in both sibling adapters: the unit of work decides when
        # this session's work becomes permanent, and this class never does.
        self._session = session

    async def get(self, task_id: UUID) -> Task | None:
        """The task with this identifier as an entity, or `None`."""
        row = await self._session.get(TaskRow, task_id)
        return None if row is None else task_to_entity(row)

    async def get_for_update(self, task_id: UUID) -> Task | None:
        """The task's latest committed state, held against other writers.

        The port states the contract; `task_for_update_statement` is how it is
        kept. The lock is released by whatever ends the transaction, which is the
        unit of work's decision and never this method's. `update` below then finds
        the row in the identity map, so the write path costs no extra statement.
        """
        row = await self._session.scalar(task_for_update_statement(task_id))
        return None if row is None else task_to_entity(row)

    async def add(self, task: Task) -> None:
        """Insert the task, translating the two references it can dangle."""
        self._session.add(task_to_row(task))
        try:
            # The flush is what surfaces the violation here, where the
            # constraint name still identifies which reference was missing; see
            # `task_lists.py` for the full argument.
            await self._session.flush()
        except IntegrityError as error:
            self._refused(error, task)

    async def update(self, task: Task) -> None:
        """Write the entity's current values onto the row already stored.

        The row is loaded rather than replaced, because the session is tracking
        it; `apply_task_to_row` is the in-place half of the mapper pair that
        exists for exactly this call.
        """
        row = await self._session.get(TaskRow, task.id)
        if row is None:
            raise TaskNotFoundError(task.id)
        apply_task_to_row(task, row)
        try:
            # Both foreign keys are writable through `apply_task_to_row` -
            # moving a task between lists and reassigning it are ordinary
            # updates - so an update can dangle either reference just as an
            # insert can, and the same translation applies.
            await self._session.flush()
        except IntegrityError as error:
            self._refused(error, task)

    async def delete(self, task_id: UUID) -> None:
        """Remove the task, and say nothing if there was none to remove.

        Deleting an identifier that is not there is a no-op, matching
        `FakeTaskRepository.delete`. Whether a missing task is a 404 is the use
        case's decision (ADR-008): it is the only layer that knows whether the
        caller was allowed to see the task in the first place, and an adapter
        that raised here would take that decision away from it.
        """
        await self._session.execute(delete(TaskRow).where(TaskRow.id == task_id))
        await self._session.flush()

    async def list_for_task_list(
        self,
        task_list_id: UUID,
        *,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
    ) -> Sequence[Task]:
        """The tasks of one list, oldest first, filtered where asked.

        Both filters are appended to the statement, never applied to the result.
        TASK-06 makes them a requirement of the listing endpoint, so a Phase 4
        request for the high-priority tasks of a list must ask PostgreSQL for
        exactly those rows; a comprehension over a full read would answer the
        same thing today and become the slow path the first time a list holds a
        thousand tasks - while also reading rows the caller never asked for
        (T-3-17, T-3-20). The values reach SQL as bound parameters, and they are
        always an enum member's `.value`, so nothing a query string carries can
        arrive as text.

        The keyword-only signature is the port's and must not be widened: a
        caller that could pass these positionally would be relying on an order
        the Protocol does not promise.

        The order is `created_at` and then `id`, because `created_at` alone is
        not a total order - two tasks created in the same request share an
        instant, and PostgreSQL may then return them either way round, which is
        how a Phase 4 assertion about the first element passes on one run and
        fails on the next.
        """
        statement = select(TaskRow).where(TaskRow.task_list_id == task_list_id)
        if status is not None:
            statement = statement.where(TaskRow.status == status.value)
        if priority is not None:
            statement = statement.where(TaskRow.priority == priority.value)
        rows = await self._session.scalars(
            statement.order_by(TaskRow.created_at, TaskRow.id)
        )
        return [task_to_entity(row) for row in rows]

    async def completion_stats(self, task_list_id: UUID) -> CompletionStats:
        """The list's two counters, from the one statement above (ADR-009).

        No filter argument, and that is the contract rather than an omission:
        roadmap Phase 4 SC-4 makes the percentage a property of the whole list,
        so it must not move when a caller narrows the listing beside it.

        The two values are handed to `CompletionStats` as they arrive. psycopg
        decodes PostgreSQL's `bigint` as a Python `int`, which
        `test_completion_stats_counts_the_whole_list` asserts rather than
        assumes; converting here anyway would hide the day that stops being true
        behind a silent `int(...)`, and converting inside `CompletionStats` would
        put a persistence concern in a domain value object.
        """
        row = await self._session.execute(completion_statement(task_list_id))
        total, completed = row.one()
        return CompletionStats(total=total, completed=completed)

    def _refused(self, error: IntegrityError, task: Task) -> NoReturn:
        """Re-raise a refusal as the error it means, or exactly as it arrived.

        Written once and called from both write paths, for the reason
        `task_lists.py` records: a second copy is a second place for the
        constraint-name comparison to fall out of date.

        Only the two foreign keys are translated. The three `CHECK` constraints
        are deliberately absent - see the module docstring - as is any attempt
        to guess at a name this module does not recognise, because
        `violated_constraint` returning `None` means *unknowable* rather than
        *no conflict* (D-13, T-3-14).
        """
        refused_by = violated_constraint(error)
        if refused_by == FK_TASKS_TASK_LIST_ID_TASK_LISTS:
            raise TaskListNotFoundError(task.task_list_id) from error
        # The assignee check is narrow on purpose. An unassigned task writes
        # `NULL`, which no foreign key can refuse, so the pairing cannot happen
        # in practice - and stating it keeps `assignee_id` a `UUID` rather than
        # an optional one at the raise below, with no cast and no assertion.
        if refused_by == FK_TASKS_ASSIGNEE_ID_USERS and task.assignee_id is not None:
            raise UserNotFoundError(task.assignee_id) from error
        raise error
