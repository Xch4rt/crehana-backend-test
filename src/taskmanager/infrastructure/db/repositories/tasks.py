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

from typing import NoReturn
from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from taskmanager.domain.entities.task import Task
from taskmanager.domain.exceptions import (
    TaskListNotFoundError,
    TaskNotFoundError,
    UserNotFoundError,
)
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
