"""Two writers, two connections: the one thing the rest of this suite cannot say.

The Phase 4 review's CR-01, reproduced by the reviewer with two real units of
work: a task `in_progress`; A loads it, B loads it; A completes and commits; B,
still holding `in_progress`, moves it to `pending` - legal against B's copy - and
commits. The row went `completed -> pending`, which `ALLOWED_TRANSITIONS`
forbids, A's completion and its `completed_at` were erased, and neither caller
was told. 599 tests and 100.00% coverage were green over that defect, because
every one of them runs on the *single* connection the `connection` fixture owns,
where a second writer cannot exist. ADR-058 is the fix; this module is what makes
it falsifiable.

**Why this module leaves the harness.** `tests/integration/conftest.py` binds
every session to one connection and rolls it back, and a row lock held by a
connection never blocks that same connection - so inside the harness the locking
read and the plain read are indistinguishable, which is exactly how the defect
stayed invisible. These tests open their own engine, commit for real, and remove
what they committed from a separate connection afterwards. That cleanup is not
housekeeping the module docstring over there forbids: it is the
`_remove_the_committed_user` argument from `test_dependencies.py` - a test whose
subject *is* a durable write has to take it back, or
`test_the_users_table_is_left_empty` would report it as a leak.

**How the interleaving is forced, and why it cannot hang the suite.** Writer A is
driven by hand so it can be paused between its locking read and its commit;
writer B is the real use case, started as a task while A is paused. An observer
connection polls `pg_stat_activity` until a backend is waiting on a lock (or B
has already finished, which is what happens when nothing makes it wait). Three
independent bounds keep a broken lock from becoming a stuck run: the poll gives
up after `OBSERVE_FOR` seconds, every connection carries PostgreSQL's
`lock_timeout`, and B is awaited under `asyncio.wait_for`.

**What goes red without the lock.** With `.with_for_update()` removed from the
adapter, B does not wait: it reads `in_progress`, commits `pending` and is told
it succeeded, and A then commits `completed` over it. The first test fails on
"the second writer must be refused" - a writer was told its change was durable
and it is gone. The captured run is in
`.planning/phases/04-task-lists-tasks/evidence/04-review-fix-CR-01-red.txt`.
"""

import asyncio
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from taskmanager.application.dto.commands import (
    ChangeTaskStatusCommand,
    GetTaskCommand,
    UpdateTaskListCommand,
)
from taskmanager.application.dto.results import TaskListResult, TaskResult
from taskmanager.application.use_cases.access import visible_task, visible_task_list
from taskmanager.application.use_cases.task_lists.update import UpdateTaskList
from taskmanager.application.use_cases.tasks.change_task_status import (
    ChangeTaskStatus,
)
from taskmanager.application.use_cases.tasks.get import GetTask
from taskmanager.domain.entities.task import Task
from taskmanager.domain.entities.task_list import TaskList
from taskmanager.domain.entities.user import User
from taskmanager.domain.exceptions import InvalidStatusTransitionError
from taskmanager.domain.value_objects.task_status import TaskStatus
from taskmanager.infrastructure.db.mappers import (
    task_list_to_row,
    task_to_row,
    user_to_row,
)
from taskmanager.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork

pytestmark = pytest.mark.integration

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
LATER = NOW + timedelta(hours=1)
OWNER_ID = UUID("c0c0c0c0-0001-4000-8000-000000000001")
LIST_ID = UUID("c0c0c0c0-0002-4000-8000-000000000002")
TASK_ID = UUID("c0c0c0c0-0003-4000-8000-000000000003")

# The three bounds the module docstring names. Generous beside the milliseconds
# a healthy run takes, and small beside a CI job's patience.
LOCK_TIMEOUT_MS = 8_000
OBSERVE_FOR = 5.0
AWAIT_WRITER_FOR = 15.0

WAITING_ON_A_LOCK = text(
    "SELECT count(*) FROM pg_stat_activity "
    "WHERE datname = current_database() AND wait_event_type = 'Lock'"
)


class _Clock:
    """The `Clock` port, stopped at `LATER`, local so this module imports no fake."""

    def now(self) -> datetime:
        return LATER


@dataclass(frozen=True, slots=True)
class _Database:
    """The module's own engine, and units of work that really commit."""

    engine: AsyncEngine
    session_factory: Callable[[], AsyncSession]

    def unit_of_work(self) -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(self.session_factory)

    async def someone_is_waiting_on_a_lock(self) -> bool:
        async with self.engine.connect() as observer:
            count = await observer.scalar(WAITING_ON_A_LOCK)
        return bool(count)

    async def task_columns(self) -> tuple[str, datetime | None, str]:
        async with self.engine.connect() as outside:
            row = await outside.execute(
                text("SELECT status, completed_at, title FROM tasks WHERE id = :id"),
                {"id": TASK_ID},
            )
            status, completed_at, title = row.one()
        return status, completed_at, title

    async def list_columns(self) -> tuple[str, str | None]:
        async with self.engine.connect() as outside:
            row = await outside.execute(
                text("SELECT name, description FROM task_lists WHERE id = :id"),
                {"id": LIST_ID},
            )
            name, description = row.one()
        return name, description


async def _remove_what_was_committed(engine: AsyncEngine) -> None:
    """Both foreign keys cascade from `users`, so one row takes the rest along."""
    async with engine.begin() as connection:
        await connection.execute(
            text("DELETE FROM users WHERE id = :id"), {"id": OWNER_ID}
        )


@pytest.fixture
async def database(
    migrated_database: None, database_url: str
) -> AsyncIterator[_Database]:
    """An owner, a list and an `in_progress` task, durable for one test."""
    engine = create_async_engine(
        database_url,
        poolclass=NullPool,
        # psycopg hands `options` to libpq: every connection this module opens,
        # the cleanup's included, gives up on a lock instead of waiting for ever.
        connect_args={"options": f"-c lock_timeout={LOCK_TIMEOUT_MS}"},
    )
    session_factory = async_sessionmaker(
        engine, expire_on_commit=False, autoflush=False
    )
    task = Task.create(
        task_id=TASK_ID, task_list_id=LIST_ID, title="Contended", now=NOW
    )
    task.change_status(TaskStatus.IN_PROGRESS, now=NOW)
    try:
        # A run that died between its commit and its cleanup must not turn every
        # later run red on a duplicate key.
        await _remove_what_was_committed(engine)
        async with session_factory() as session:
            session.add(
                user_to_row(
                    User.create(
                        user_id=OWNER_ID,
                        email="contended@example.com",
                        full_name="Contended Owner",
                        password_hash="not-a-real-hash",
                        now=NOW,
                    )
                )
            )
            await session.flush()
            session.add(
                task_list_to_row(
                    TaskList.create(
                        task_list_id=LIST_ID, owner_id=OWNER_ID, name="Alpha", now=NOW
                    )
                )
            )
            await session.flush()
            session.add(task_to_row(task))
            await session.commit()
        yield _Database(engine, session_factory)
    finally:
        try:
            await _remove_what_was_committed(engine)
        finally:
            await engine.dispose()


async def _until_it_waits_or_finishes[T](
    database: _Database, writer: asyncio.Task[T]
) -> bool:
    """Whether the second writer was seen waiting on a lock before it finished.

    Returns rather than asserts. The caller lets the first writer commit either
    way and asserts on the *outcome* first, so a run without the lock fails on
    what actually went wrong - a lost write - and not merely on "nobody waited".
    """
    loop = asyncio.get_running_loop()
    deadline = loop.time() + OBSERVE_FOR
    while loop.time() < deadline and not writer.done():
        if await database.someone_is_waiting_on_a_lock():
            return True
        await asyncio.sleep(0.02)
    return False


async def _settle[T](writer: asyncio.Task[T]) -> T | BaseException:
    """The second writer's result or its exception, within `AWAIT_WRITER_FOR`."""
    try:
        return await asyncio.wait_for(writer, AWAIT_WRITER_FOR)
    except Exception as error:
        return error
    finally:
        if not writer.done():
            writer.cancel()
            await asyncio.gather(writer, return_exceptions=True)


async def test_a_stale_writer_cannot_persist_a_forbidden_transition(
    database: _Database,
) -> None:
    """CR-01 itself: `completed -> pending` must not reach the row, by any timing.

    A holds the task and completes it; B asks for `pending` while A is still in
    flight. B has to wait, see `completed`, and be refused with the documented
    409 - and A's completion and its `completed_at` have to survive.
    """
    first = database.unit_of_work()
    async with first:
        task = await visible_task(first, LIST_ID, TASK_ID, OWNER_ID, for_update=True)
        second: asyncio.Task[TaskResult] = asyncio.create_task(
            ChangeTaskStatus(database.unit_of_work(), _Clock()).execute(
                ChangeTaskStatusCommand(
                    actor_id=OWNER_ID,
                    task_list_id=LIST_ID,
                    task_id=TASK_ID,
                    new_status=TaskStatus.PENDING,
                )
            )
        )
        try:
            waited = await _until_it_waits_or_finishes(database, second)
            task.change_status(TaskStatus.COMPLETED, now=LATER)
            await first.tasks.update(task)
            await first.commit()
        finally:
            outcome = await _settle(second)

    assert isinstance(outcome, InvalidStatusTransitionError), (
        "the second writer must be refused: it asked for `pending` on a task the "
        f"first writer had completed, and was answered with {outcome!r}"
    )
    assert outcome.details == {"from": "completed", "to": "pending"}
    status, completed_at, _ = await database.task_columns()
    assert status == "completed"
    assert completed_at == LATER
    assert waited, "the second writer never waited, so the outcome above was luck"


async def test_two_list_patches_are_serialised_and_neither_edit_is_lost(
    database: _Database,
) -> None:
    """The same guarantee on the other aggregate a request can change.

    A renames the list; B re-describes it while A is in flight. B waits, so the
    representation it answers with carries A's new name rather than the one B
    would have read a moment earlier - and both edits are in the row.
    """
    first = database.unit_of_work()
    async with first:
        task_list = await visible_task_list(first, LIST_ID, OWNER_ID, for_update=True)
        second: asyncio.Task[TaskListResult] = asyncio.create_task(
            UpdateTaskList(database.unit_of_work(), _Clock()).execute(
                UpdateTaskListCommand(
                    actor_id=OWNER_ID, task_list_id=LIST_ID, description="From B."
                )
            )
        )
        try:
            waited = await _until_it_waits_or_finishes(database, second)
            task_list.rename("Renamed by A", now=LATER)
            await first.task_lists.update(task_list)
            await first.commit()
        finally:
            outcome = await _settle(second)

    assert isinstance(outcome, TaskListResult), outcome
    assert waited, "the second PATCH never waited for the first one"
    assert outcome.name == "Renamed by A"
    assert outcome.description == "From B."
    assert await database.list_columns() == ("Renamed by A", "From B.")


async def test_a_read_never_waits_on_a_writer(database: _Database) -> None:
    """The other half of ADR-058: only write paths hold, so a GET is never queued.

    A holds the task and has not committed. A plain read from a second connection
    answers at once, with the last committed state - `in_progress` - rather than
    waiting for A or seeing A's unfinished work.
    """
    first = database.unit_of_work()
    async with first:
        task = await visible_task(first, LIST_ID, TASK_ID, OWNER_ID, for_update=True)
        task.change_status(TaskStatus.COMPLETED, now=LATER)
        await first.tasks.update(task)

        reader: asyncio.Task[TaskResult] = asyncio.create_task(
            GetTask(database.unit_of_work()).execute(
                GetTaskCommand(actor_id=OWNER_ID, task_list_id=LIST_ID, task_id=TASK_ID)
            )
        )
        outcome = await _settle(reader)

    assert isinstance(outcome, TaskResult), outcome
    assert outcome.status is TaskStatus.IN_PROGRESS
    # A never committed, so its block rolled back and the row is untouched.
    status, completed_at, _ = await database.task_columns()
    assert (status, completed_at) == ("in_progress", None)
