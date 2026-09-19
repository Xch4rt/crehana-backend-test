"""The task-list adapter against a real server: SC-2, D-13 and the ordering.

Three properties are proven here that no unit test with an in-memory fake could
reach.

Roadmap SC-2: an entity handed back by this adapter is readable after the
session that produced it is gone. The fake satisfies that trivially; only a
session bound to PostgreSQL can fail it, and it would fail as a `MissingGreenlet`
raised from wherever the use case read the attribute, which is the failure mode
DB-03 exists to remove.

D-13: a refusal from the database becomes the business error it means. The two
constraints this adapter knows about are asserted through the errors they
produce, not through the exception the driver raised, and the third case - a
violation the adapter does not recognise - is asserted to escape untranslated.
That last one is the branch `tests/unit/infrastructure/test_errors.py` could not
reach without a server, and the reason it matters is that an unrecognised
failure must become the fixed 500 rather than a guess.

Every write below goes through the repository, and no test commits anything. The
`connection` fixture's outer transaction is rolled back at teardown, so a stray
transaction boundary inside the adapter would leave rows behind that the next
test would see - which is the isolation contract D-01 buys, and the reason
nothing here cleans up after itself.
"""

import uuid
from datetime import UTC, datetime
from typing import Final

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import Dialect
from sqlalchemy.exc import IntegrityError, InvalidRequestError
from sqlalchemy.ext.asyncio import AsyncSession, AsyncSessionTransaction

from taskmanager.domain.entities.task import Task
from taskmanager.domain.entities.task_list import TaskList
from taskmanager.domain.entities.user import User
from taskmanager.domain.exceptions import (
    DuplicateTaskListNameError,
    TaskListNotFoundError,
    UserNotFoundError,
)
from taskmanager.domain.value_objects.task_status import TaskStatus
from taskmanager.infrastructure.db.constraints import UQ_TASK_LISTS_OWNER_ID_NAME
from taskmanager.infrastructure.db.mappers import task_to_row, user_to_row
from taskmanager.infrastructure.db.models import TaskListRow
from taskmanager.infrastructure.db.repositories.task_lists import (
    SqlAlchemyTaskListRepository,
    lists_with_stats_statement,
    task_list_for_update_statement,
)

pytestmark = pytest.mark.integration

# Fixed identifiers and fixed instants, never generated ones: a value produced at
# run time would make an assertion about "the list that was renamed" true of
# whatever row happened to be there, and the ordering test below is exactly the
# place where that would stop being noticed.
OWNER_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")
OTHER_OWNER_ID = uuid.UUID("00000000-0000-4000-8000-000000000002")
MISSING_OWNER_ID = uuid.UUID("00000000-0000-4000-8000-0000000000fe")
LIST_ID = uuid.UUID("00000000-0000-4000-8000-000000000011")
OTHER_LIST_ID = uuid.UUID("00000000-0000-4000-8000-000000000012")
THIRD_LIST_ID = uuid.UUID("00000000-0000-4000-8000-000000000013")
MISSING_LIST_ID = uuid.UUID("00000000-0000-4000-8000-0000000000ff")

NOW = datetime(2026, 3, 14, 15, 9, 26, 535897, tzinfo=UTC)
EARLIER = datetime(2026, 3, 13, 9, 0, 0, tzinfo=UTC)
LATER = datetime(2026, 3, 15, 9, 0, 0, tzinfo=UTC)

PASSWORD_HASH = "argon2-placeholder-hash-value"
OWNER_EMAIL = "owner@example.test"
OTHER_OWNER_EMAIL = "other@example.test"

# Resolved through a typed `create_engine`, never `postgresql.dialect()`: mypy
# strict reports the latter as `no-untyped-call`. The engine connects lazily, so
# nothing below it opens a socket - the same idiom `test_repositories_tasks.py`
# and `test_schema.py` use, and the reason the compiled-SQL test needs no server.
DIALECT: Final[Dialect] = create_engine("postgresql+psycopg://").dialect


def refused(session: AsyncSession) -> AsyncSessionTransaction:
    """A savepoint around work PostgreSQL is expected to reject.

    A refused statement aborts the transaction it ran in: every later statement
    answers `current transaction is aborted` until it is unwound, and the
    transaction here belongs to the `connection` fixture, which has to keep it
    until teardown. Running the expected failure inside a savepoint means the
    rollback stops at that savepoint, so a test can watch a statement be refused
    and then keep reading the table. Written once here rather than as a comment
    repeated at every call site - the same argument `test_constraints.py` makes
    for its own helper of this name.
    """
    return session.begin_nested()


def a_task_list(
    *,
    task_list_id: uuid.UUID = LIST_ID,
    owner_id: uuid.UUID = OWNER_ID,
    name: str = "Groceries",
    description: str | None = "Everything for the week",
    created_at: datetime = NOW,
) -> TaskList:
    """A valid list entity, differing from the default only where asked."""
    return TaskList(
        id=task_list_id,
        owner_id=owner_id,
        name=name,
        description=description,
        created_at=created_at,
        updated_at=created_at,
    )


async def given_an_owner(
    session: AsyncSession,
    *,
    user_id: uuid.UUID = OWNER_ID,
    email: str = OWNER_EMAIL,
) -> None:
    """One user row, because `task_lists.owner_id` is a foreign key.

    Written through the mapper and the session rather than through the user
    adapter: this module tests one adapter, and a failure in the other one should
    not be able to make these tests red.
    """
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


async def test_a_stored_list_comes_back_as_a_domain_entity(
    session: AsyncSession,
) -> None:
    """What goes in as an entity comes back as one, never as a row (DB-03)."""
    await given_an_owner(session)
    repository = SqlAlchemyTaskListRepository(session)

    await repository.add(a_task_list())
    fetched = await repository.get(LIST_ID)

    assert isinstance(fetched, TaskList)
    assert not isinstance(fetched, TaskListRow)
    assert fetched.name == "Groceries"
    assert fetched.description == "Everything for the week"
    assert fetched.owner_id == OWNER_ID
    assert await repository.get(MISSING_LIST_ID) is None


async def test_a_returned_entity_is_readable_after_the_session_is_gone(
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
    await given_an_owner(session)
    repository = SqlAlchemyTaskListRepository(session)
    await repository.add(a_task_list())
    fetched = await repository.get(LIST_ID)
    assert fetched is not None

    await session.close()

    assert fetched.name == "Groceries"
    assert fetched.description == "Everything for the week"
    assert fetched.owner_id == OWNER_ID
    assert fetched.created_at == NOW
    assert fetched.updated_at == NOW


async def test_touching_the_tasks_relationship_raises_instead_of_lazy_loading(
    session: AsyncSession,
) -> None:
    """DB-03's `lazy="raise"`, stated as a refusal rather than as a setting.

    Without this test the option is merely present in `models.py`. With it, the
    guarantee is the one DB-03 actually promises: a developer who reaches for the
    children of a list gets an `InvalidRequestError` the moment they write it,
    instead of a `MissingGreenlet` raised at runtime in front of a user. Nothing
    in this package reads the collection - `task_list_to_entity` deliberately
    does not - and a query that genuinely needs the tasks asks for them.
    """
    await given_an_owner(session)
    await SqlAlchemyTaskListRepository(session).add(a_task_list())

    row = await session.get(TaskListRow, LIST_ID)
    assert row is not None

    with pytest.raises(InvalidRequestError):
        row.tasks  # noqa: B018 - the attribute read IS the assertion


async def test_a_duplicate_name_for_one_owner_raises_the_conflict_error(
    session: AsyncSession,
) -> None:
    """D-13: `uq_task_lists_owner_id_name` becomes LIST-06's 409, not a 500.

    The error body is asserted as well as the error type. A translation that
    forwarded what the driver said would put the constraint name - and the SQL
    that produced it - into a response, which is the disclosure T-3-13 is about.
    """
    await given_an_owner(session)
    repository = SqlAlchemyTaskListRepository(session)
    await repository.add(a_task_list())

    with pytest.raises(DuplicateTaskListNameError) as raised:
        async with refused(session):
            await repository.add(a_task_list(task_list_id=OTHER_LIST_ID))

    assert raised.value.details == {"field": "name", "name": "Groceries"}
    reported = f"{raised.value} {raised.value.details}"
    assert UQ_TASK_LISTS_OWNER_ID_NAME not in reported
    assert "INSERT" not in reported


async def test_the_same_name_in_a_different_case_is_accepted(
    session: AsyncSession,
) -> None:
    """D-12: the per-owner index is case-sensitive, unlike the users one.

    `TaskList` folds no case on its name, so `Groceries` and `groceries` are two
    lists the domain considers distinct and the database agrees. The same pair is
    asserted at the raw SQL level in `test_constraints.py`; here it is asserted
    through the adapter, because a repository that lowercased on the way in would
    satisfy that test and fail this one.
    """
    await given_an_owner(session)
    repository = SqlAlchemyTaskListRepository(session)

    await repository.add(a_task_list(name="Groceries"))
    await repository.add(a_task_list(task_list_id=OTHER_LIST_ID, name="groceries"))

    stored = await repository.list_for_owner(OWNER_ID)
    assert sorted(task_list.name for task_list in stored) == ["Groceries", "groceries"]


async def test_a_list_for_an_unknown_owner_raises_user_not_found(
    session: AsyncSession,
) -> None:
    """D-13: the foreign key becomes a `NotFoundError` about the owner.

    A 500 would be the wrong answer and so would a conflict: nothing is in
    conflict, the owner simply is not there. Settled empirically by 03-05 -
    psycopg populates `diag.constraint_name` for foreign-key violations too, so
    this branch has a name to key on.
    """
    repository = SqlAlchemyTaskListRepository(session)

    with pytest.raises(UserNotFoundError) as raised:
        async with refused(session):
            await repository.add(a_task_list(owner_id=MISSING_OWNER_ID))

    assert raised.value.details == {"user_id": str(MISSING_OWNER_ID)}


async def test_an_unrecognised_integrity_error_is_re_raised(
    session: AsyncSession,
) -> None:
    """D-13's other half: what the adapter does not recognise, it does not touch.

    A row with no `name` is put into the session directly - the entity would
    refuse to build one - so the flush inside `add()` carries a violation this
    adapter has no translation for. It must escape as it arrived, which is what
    lets Phase 2's catch-all answer the fixed 500 with no message rather than
    letting this module invent a business meaning for a failure it does not
    understand (T-3-14).
    """
    await given_an_owner(session)
    repository = SqlAlchemyTaskListRepository(session)

    with pytest.raises(IntegrityError):
        async with refused(session):
            # Inside the savepoint, never before it: opening a SAVEPOINT flushes
            # whatever is already pending, so a bad row added beforehand would be
            # refused by the savepoint itself and this test would pass without
            # the repository having run at all. Observed - the first version of
            # this test was green with `add()` fully uncovered.
            session.add(
                TaskListRow(
                    id=OTHER_LIST_ID,
                    owner_id=OWNER_ID,
                    created_at=NOW,
                    updated_at=NOW,
                )
            )
            await repository.add(a_task_list())


async def test_update_renames_and_rejects_a_colliding_rename(
    session: AsyncSession,
) -> None:
    """An update writes onto the stored row, and collides like an insert does."""
    await given_an_owner(session)
    repository = SqlAlchemyTaskListRepository(session)
    await repository.add(a_task_list(name="Groceries"))
    await repository.add(a_task_list(task_list_id=OTHER_LIST_ID, name="Chores"))

    chores = await repository.get(OTHER_LIST_ID)
    assert chores is not None
    chores.rename("Weekly chores", now=LATER)
    await repository.update(chores)

    renamed = await repository.get(OTHER_LIST_ID)
    assert renamed is not None
    assert renamed.name == "Weekly chores"
    assert renamed.updated_at == LATER

    renamed.rename("Groceries", now=LATER)
    with pytest.raises(DuplicateTaskListNameError):
        async with refused(session):
            await repository.update(renamed)


async def test_updating_a_list_that_is_gone_raises_not_found(
    session: AsyncSession,
) -> None:
    """There is no row to write onto, and inserting one would be a lie.

    `update()` is the one write path that can fail before it reaches the
    database. Treating a missing row as an insert would turn a use case's
    "modify what I fetched" into "create whatever I was handed", which is how a
    deleted resource comes back to life.
    """
    repository = SqlAlchemyTaskListRepository(session)

    with pytest.raises(TaskListNotFoundError) as raised:
        await repository.update(a_task_list(task_list_id=MISSING_LIST_ID))

    assert raised.value.details == {"task_list_id": str(MISSING_LIST_ID)}


async def test_delete_removes_the_row_and_is_a_no_op_for_an_unknown_id(
    session: AsyncSession,
) -> None:
    """Deleting what is not there raises nothing: the use case owns the 404."""
    await given_an_owner(session)
    repository = SqlAlchemyTaskListRepository(session)
    await repository.add(a_task_list())

    await repository.delete(LIST_ID)
    assert await repository.get(LIST_ID) is None

    await repository.delete(MISSING_LIST_ID)


async def test_list_for_owner_returns_only_that_owners_lists_in_creation_order(
    session: AsyncSession,
) -> None:
    """Owner-scoped in SQL, and ordered, because both are load-bearing.

    The two lists are written newest first, so a missing `ORDER BY` would have to
    be lucky to produce the asserted order. The third list belongs to somebody
    else: scoping applied in Python rather than in the query is how a Phase 4 use
    case ends up reading every owner's rows before filtering them (T-3-20).
    """
    await given_an_owner(session)
    await given_an_owner(session, user_id=OTHER_OWNER_ID, email=OTHER_OWNER_EMAIL)
    repository = SqlAlchemyTaskListRepository(session)

    await repository.add(a_task_list(name="Newer", created_at=LATER))
    await repository.add(
        a_task_list(task_list_id=OTHER_LIST_ID, name="Older", created_at=EARLIER)
    )
    await repository.add(
        a_task_list(
            task_list_id=THIRD_LIST_ID, owner_id=OTHER_OWNER_ID, name="Somebody else's"
        )
    )

    stored = await repository.list_for_owner(OWNER_ID)

    assert [task_list.name for task_list in stored] == ["Older", "Newer"]
    assert await repository.list_for_owner(MISSING_OWNER_ID) == []


async def test_list_for_owner_breaks_a_tie_on_created_at_with_the_id(
    session: AsyncSession,
) -> None:
    """WR-03: the ordering has to be total, not merely present.

    Three lists share one instant to the microsecond, which is not a contrived
    fixture: D-13 has the use case read the clock once per request, so a Phase 4
    operation that creates more than one list writes them all under the same
    `created_at`. With `ORDER BY created_at` alone PostgreSQL may return those
    rows in any order it finds convenient, and it is free to choose a different
    one on the next run - so an assertion about the first element would be
    flaky rather than wrong, which is the harder kind to notice.

    The names and the insertion order are both chosen to disagree with the
    asserted order, and that took a second attempt: with names that sorted the
    same way the identifiers do, PostgreSQL answered from the
    `uq_task_lists_owner_id_name` index and the test passed against the very
    query it was written to reject. Here neither alphabetical order
    (Alpha, Mike, Zulu) nor insertion order (Alpha, Mike, Zulu) matches the
    expected one, so only an explicit tie-break on `id` can produce it.
    """
    await given_an_owner(session)
    repository = SqlAlchemyTaskListRepository(session)

    await repository.add(
        a_task_list(task_list_id=OTHER_LIST_ID, name="Alpha", created_at=NOW)
    )
    await repository.add(
        a_task_list(task_list_id=THIRD_LIST_ID, name="Mike", created_at=NOW)
    )
    await repository.add(a_task_list(task_list_id=LIST_ID, name="Zulu", created_at=NOW))

    stored = await repository.list_for_owner(OWNER_ID)

    assert [task_list.id for task_list in stored] == [
        LIST_ID,
        OTHER_LIST_ID,
        THIRD_LIST_ID,
    ]


async def test_exists_with_name_is_case_sensitive_and_owner_scoped(
    session: AsyncSession,
) -> None:
    """LIST-06's pre-check agrees with the index it stands in front of.

    A case-insensitive answer here would refuse a name the database would have
    accepted, and an unscoped one would report somebody else's list as this
    owner's collision - reading, in effect, a row the caller may not see.
    """
    await given_an_owner(session)
    await given_an_owner(session, user_id=OTHER_OWNER_ID, email=OTHER_OWNER_EMAIL)
    repository = SqlAlchemyTaskListRepository(session)
    await repository.add(a_task_list(name="Groceries"))

    assert await repository.exists_with_name(OWNER_ID, "Groceries") is True
    # Trimmed, because `require_text` trimmed the stored side before writing it.
    assert await repository.exists_with_name(OWNER_ID, "  Groceries  ") is True
    assert await repository.exists_with_name(OWNER_ID, "groceries") is False
    assert await repository.exists_with_name(OWNER_ID, "Chores") is False
    assert await repository.exists_with_name(OTHER_OWNER_ID, "Groceries") is False


async def given_tasks_in(
    session: AsyncSession,
    *,
    task_list_id: uuid.UUID,
    total: int,
    completed: int,
) -> None:
    """`total` tasks in one list, `completed` of them already done.

    Written through the mapper and the session rather than through the task
    adapter, for the reason `given_an_owner` gives: this module tests one
    adapter, and a failure in the other one should not be able to make these
    tests red. The tasks exist only so the grouped statement has something to
    count.
    """
    for index in range(total):
        # Built through the entity rather than by filling the dataclass in:
        # `change_status` is what stamps `completed_at`, and the three CHECK
        # constraints on `tasks` refuse a row whose status and stamp disagree.
        # Derived from the list's own last four hex digits, never from its first
        # eight: every identifier in this module shares the prefix
        # `00000000-0000-4000-8000-`, so a prefix-based derivation gives two
        # different lists the same task ids and `pk_tasks` refuses the second.
        task = Task.create(
            task_id=uuid.UUID(
                f"00000000-0000-4000-9000-{task_list_id.hex[-4:]}{index:08d}"
            ),
            task_list_id=task_list_id,
            title=f"Task {index}",
            now=NOW,
        )
        if index < completed:
            task.change_status(TaskStatus.COMPLETED, now=NOW)
        session.add(task_to_row(task))
    await session.flush()


async def test_listing_with_stats_returns_one_entry_per_list_of_the_owner(
    session: AsyncSession,
) -> None:
    """LIST-03: the whole collection, each entry carrying its own counters.

    The two lists get different mixes on purpose. A join that leaked rows across
    groups - or a `GROUP BY` that lost one - would still produce two entries with
    plausible entities, and only counters that differ from each other catch it.
    The entities are asserted to be domain objects as well, because a grouped
    `SELECT` returns a `Row` and it is `task_list_to_entity` that must unpack it.
    """
    await given_an_owner(session)
    repository = SqlAlchemyTaskListRepository(session)
    await repository.add(a_task_list(name="Groceries", created_at=EARLIER))
    await repository.add(
        a_task_list(task_list_id=OTHER_LIST_ID, name="Chores", created_at=LATER)
    )
    await given_tasks_in(session, task_list_id=LIST_ID, total=4, completed=1)
    await given_tasks_in(session, task_list_id=OTHER_LIST_ID, total=2, completed=2)

    entries = await repository.list_for_owner_with_stats(OWNER_ID)

    assert [
        (task_list.name, stats.total, stats.completed) for task_list, stats in entries
    ] == [("Groceries", 4, 1), ("Chores", 2, 2)]
    assert all(isinstance(task_list, TaskList) for task_list, _ in entries)
    assert not any(isinstance(task_list, TaskListRow) for task_list, _ in entries)
    assert [stats.percentage for _, stats in entries] == [25.0, 100.0]


async def test_listing_with_stats_reports_zero_for_a_list_with_no_tasks(
    session: AsyncSession,
) -> None:
    """The `count(*)` trap, made into a test rather than left as a comment.

    A LEFT OUTER JOIN produces one null-extended row for a list with no tasks.
    `count(*)` counts it, so the list would report a total of 1 and a percentage
    over a task that does not exist; `count(tasks.id)` skips the NULL. This is
    also the only assertion that distinguishes the outer join from an inner one -
    an inner join would drop the empty list from the response entirely, which is
    the other way LIST-03 can be got wrong.
    """
    await given_an_owner(session)
    repository = SqlAlchemyTaskListRepository(session)
    await repository.add(a_task_list(name="Empty"))

    entries = await repository.list_for_owner_with_stats(OWNER_ID)

    assert len(entries) == 1
    _, stats = entries[0]
    assert stats.total == 0
    assert stats.completed == 0
    assert stats.percentage == 0.0


async def test_listing_with_stats_never_returns_another_owners_list(
    session: AsyncSession,
) -> None:
    """The owner filter is the only scope, and it is in SQL (T-4-06, ADR-008).

    The other owner's list is given tasks too, so a join that counted across the
    whole `tasks` table rather than per group would be caught here as well as by
    the counters above.
    """
    await given_an_owner(session)
    await given_an_owner(session, user_id=OTHER_OWNER_ID, email=OTHER_OWNER_EMAIL)
    repository = SqlAlchemyTaskListRepository(session)
    await repository.add(a_task_list(name="Mine"))
    await repository.add(
        a_task_list(
            task_list_id=OTHER_LIST_ID, owner_id=OTHER_OWNER_ID, name="Somebody else's"
        )
    )
    await given_tasks_in(session, task_list_id=LIST_ID, total=1, completed=0)
    await given_tasks_in(session, task_list_id=OTHER_LIST_ID, total=3, completed=3)

    entries = await repository.list_for_owner_with_stats(OWNER_ID)

    assert [task_list.name for task_list, _ in entries] == ["Mine"]
    assert entries[0][1].total == 1
    assert await repository.list_for_owner_with_stats(MISSING_OWNER_ID) == []


async def test_listing_with_stats_orders_by_created_at_then_id(
    session: AsyncSession,
) -> None:
    """D-13 again, and it has to be asserted of *this* statement separately.

    `list_for_owner`'s ordering test proves nothing about the grouped query: the
    two are different statements with different `ORDER BY` clauses, and a
    `GROUP BY` is exactly the kind of change that invites an implementation to
    trust the grouping order. Two of the three lists share an instant to the
    microsecond - the clock is read once per request, so that is the ordinary
    case rather than a contrived one - and neither alphabetical nor insertion
    order matches the expected result, so only the `id` tie-break produces it.
    """
    await given_an_owner(session)
    repository = SqlAlchemyTaskListRepository(session)
    await repository.add(
        a_task_list(task_list_id=THIRD_LIST_ID, name="Alpha", created_at=NOW)
    )
    await repository.add(
        a_task_list(task_list_id=OTHER_LIST_ID, name="Mike", created_at=EARLIER)
    )
    await repository.add(a_task_list(task_list_id=LIST_ID, name="Zulu", created_at=NOW))

    entries = await repository.list_for_owner_with_stats(OWNER_ID)

    assert [task_list.id for task_list, _ in entries] == [
        OTHER_LIST_ID,
        LIST_ID,
        THIRD_LIST_ID,
    ]


async def test_listing_with_stats_returns_counters_as_python_ints(
    session: AsyncSession,
) -> None:
    """psycopg decodes `bigint` as `int`, asserted rather than assumed.

    `CompletionStats` takes whatever the row carried, and the adapter converts
    nothing - deliberately, for the reason `completion_stats` records. So the day
    a driver or a dialect change hands back a `Decimal` instead, the percentage
    would still look right and the response body would carry `"total": 4.0`. This
    test is what notices.
    """
    await given_an_owner(session)
    repository = SqlAlchemyTaskListRepository(session)
    await repository.add(a_task_list())
    await given_tasks_in(session, task_list_id=LIST_ID, total=2, completed=1)

    _, stats = (await repository.list_for_owner_with_stats(OWNER_ID))[0]

    assert type(stats.total) is int
    assert type(stats.completed) is int


def test_listing_with_stats_is_a_single_statement() -> None:
    """LIST-03's "no N+1" as a property of the SQL, not of a round-trip count.

    Compiled rather than observed, exactly as `test_the_aggregate_is_a_single_
    statement` in the sibling module is: counting queries on the wire needs an
    event listener and still only describes the one call path the test happened
    to take. The rendered statement is the claim - one `FROM task_lists`, a
    `LEFT OUTER JOIN` onto `tasks`, and a `FILTER` doing the conditional half -
    so a refactor into `list_for_owner` plus a `completion_stats` per row fails
    here regardless of how it is invoked. Plan 04-10 adds the runtime statement
    counter on top of this, over the endpoint.

    `count(tasks.id)` is asserted and `count(*)` is asserted *absent*, because
    the two render almost identically and differ only on the null-extended row an
    empty list produces.
    """
    compiled = str(lists_with_stats_statement(OWNER_ID).compile(dialect=DIALECT))

    assert "FILTER (WHERE" in compiled
    assert "LEFT OUTER JOIN" in compiled
    assert compiled.count("count(tasks.id)") == 2
    assert "count(*)" not in compiled
    assert compiled.count("FROM task_lists") == 1
    # The filter value travels as a bound parameter, never as an inlined literal
    # (T-3-17): the same discipline every statement in this package follows. The
    # label is elided first, exactly as the sibling assertion does - `completed`
    # is both the status this query filters on and the name it gives the counter.
    assert TaskStatus.COMPLETED.value not in compiled.replace("AS completed", "")


def test_the_write_path_read_locks_the_list_row() -> None:
    """ADR-058 as a property of the SQL; see the sibling test in the task suite."""
    compiled = str(task_list_for_update_statement(LIST_ID).compile(dialect=DIALECT))

    assert compiled.rstrip().endswith("FOR UPDATE")
    assert compiled.count("FROM task_lists") == 1
    assert str(LIST_ID) not in compiled


async def test_get_for_update_returns_the_list_or_none(session: AsyncSession) -> None:
    """The write-path read answers exactly as `get` does: an entity, or `None`."""
    await given_an_owner(session)
    repository = SqlAlchemyTaskListRepository(session)
    await repository.add(a_task_list())

    fetched = await repository.get_for_update(LIST_ID)

    assert type(fetched) is TaskList
    assert fetched.name == "Groceries"
    assert await repository.get_for_update(MISSING_LIST_ID) is None
