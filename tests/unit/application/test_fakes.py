"""Behaviours of the in-memory doubles, each pinned to a rule the database keeps.

A fake is only worth testing where it can *disagree* with the adapter it stands
in for, and two places in `FakeTaskListRepository` can - plus, since Phase 5,
`FakeTaskRepository.list_for_assignee`, which is D-02's discovery query and is
the only listing in the project whose answer crosses a list boundary.

`exists_with_name` is what every Phase 4 use-case test will run LIST-06's
duplicate-name pre-check against, and the only thing that makes those tests
meaningful is that the fake refuses exactly what `uq_task_lists_owner_id_name`
refuses. It drifted once already: the fake folded case while D-12 specifies a
plain `UNIQUE (owner_id, name)`, so a use case could have been proven correct
against a constraint PostgreSQL will never enforce.

`list_for_owner_with_stats` is LIST-03's whole collection with its counters, and
the fake has two ways to be wrong about it. It can count something other than
what the task repository stores - then a use case that computed the percentage
itself would pass - and it can return the lists in insertion order, which is the
divergence 04-PATTERNS §11 names: `list_for_owner` had no ordering at all while
the adapter has always sorted by `(created_at, id)`, so a D-13 assertion about
the first element would pass in a unit test and fail over HTTP.

`FakeUserRepository.list_all` was the same defect, still open: the adapter has
ordered by `(created_at, id)` since Phase 3, the fake answered in insertion
order, and the two sibling fakes were fixed in 04-02 and 04-06 while this one
was missed. D-25 asks for it to be falsified rather than asserted, so the
divergence was observed red first - the capture is in
`.planning/phases/05-auth-assignment-notifications/evidence/
05-02-fake-user-ordering.txt` - and the test below is what keeps it closed.

The rejected alternative in every case is trusting the integration tests to
catch it. They would - eventually, in a later phase, as a confusing 500 from a
duplicate insert, or as a flaky ordering assertion. This file fails instead, in
milliseconds, at the line that would have to change.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from taskmanager.domain.entities.task import Task
from taskmanager.domain.entities.task_list import TaskList
from taskmanager.domain.entities.user import User
from taskmanager.domain.value_objects.task_status import TaskStatus
from tests.unit.application.fakes import (
    FakeTaskListRepository,
    FakeTaskRepository,
    FakeUserRepository,
)

pytestmark = pytest.mark.unit

# Fixed literals, never uuid4()/now(): an assertion about a lookup key must be
# reproducible from the source alone.
NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
EARLIER = NOW - timedelta(days=1)
OWNER_ID = UUID("11111111-1111-4111-8111-111111111111")
OTHER_OWNER_ID = UUID("33333333-3333-4333-8333-333333333333")
TASK_LIST_ID = UUID("22222222-2222-4222-8222-222222222222")
OTHER_LIST_ID = UUID("44444444-4444-4444-8444-444444444444")
THIRD_LIST_ID = UUID("55555555-5555-4555-8555-555555555555")
ASSIGNEE_ID = UUID("77777777-7777-4777-8777-777777777777")
STRANGER_ID = UUID("88888888-8888-4888-8888-888888888888")
# Two of the three share an instant, and the lower id is deliberately the one
# seeded second, so the `id` tie-break has something to do.
TIED_LOWER_TASK_ID = UUID("99999999-0000-4000-8000-000000000001")
TIED_HIGHER_TASK_ID = UUID("99999999-0000-4000-8000-000000000002")
OLDEST_TASK_ID = UUID("99999999-0000-4000-8000-000000000003")
UNASSIGNED_TASK_ID = UUID("99999999-0000-4000-8000-000000000004")
# The user fake's ordering, same shape: two accounts share an instant and the
# lower id is registered second.
TIED_LOWER_USER_ID = UUID("aaaaaaaa-0000-4000-8000-000000000001")
TIED_HIGHER_USER_ID = UUID("aaaaaaaa-0000-4000-8000-000000000002")
OLDEST_USER_ID = UUID("aaaaaaaa-0000-4000-8000-000000000003")
PASSWORD_HASH = "fake-hash:irrelevant"


def _stored_list(
    *,
    owner_id: UUID,
    name: str,
    task_list_id: UUID = TASK_LIST_ID,
    created_at: datetime = NOW,
) -> TaskList:
    """A list as the repository would hold it, built through the entity."""
    return TaskList.create(
        task_list_id=task_list_id,
        owner_id=owner_id,
        name=name,
        now=created_at,
    )


async def _given_tasks(
    tasks: FakeTaskRepository,
    *,
    task_list_id: UUID,
    total: int,
    completed: int,
) -> None:
    """`total` tasks in one list, `completed` of them marked done."""
    for index in range(total):
        task = Task.create(
            task_id=UUID(f"{task_list_id.hex[:8]}-6666-4666-8666-{index:012d}"),
            task_list_id=task_list_id,
            title=f"Task {index}",
            now=NOW,
        )
        if index < completed:
            task.change_status(TaskStatus.COMPLETED, now=NOW)
        await tasks.add(task)


async def _given_assignments(tasks: FakeTaskRepository) -> None:
    """Three tasks for one assignee across two lists, plus two that are not theirs.

    The insertion order is not the answer on either axis. `TIED_HIGHER_TASK_ID`
    goes in before `TIED_LOWER_TASK_ID` although they share an instant, so only
    the `id` tie-break can separate them, and the oldest task goes in last. The
    two decoys - a task assigned to someone else and a task assigned to nobody -
    are both older than everything else, so a query that dropped its filter
    would put one of them first.
    """
    await tasks.add(
        Task.create(
            task_id=TIED_HIGHER_TASK_ID,
            task_list_id=TASK_LIST_ID,
            title="Tied, higher id",
            assignee_id=ASSIGNEE_ID,
            now=NOW,
        )
    )
    await tasks.add(
        Task.create(
            task_id=TIED_LOWER_TASK_ID,
            task_list_id=OTHER_LIST_ID,
            title="Tied, lower id",
            assignee_id=ASSIGNEE_ID,
            now=NOW,
        )
    )
    await tasks.add(
        Task.create(
            task_id=OLDEST_TASK_ID,
            task_list_id=TASK_LIST_ID,
            title="Oldest",
            assignee_id=ASSIGNEE_ID,
            now=EARLIER,
        )
    )
    await tasks.add(
        Task.create(
            task_id=UNASSIGNED_TASK_ID,
            task_list_id=TASK_LIST_ID,
            title="Nobody's",
            now=EARLIER,
        )
    )
    await tasks.add(
        Task.create(
            task_id=UUID("99999999-0000-4000-8000-000000000005"),
            task_list_id=TASK_LIST_ID,
            title="Somebody else's",
            assignee_id=STRANGER_ID,
            now=EARLIER,
        )
    )


async def test_list_for_assignee_spans_every_list_the_user_appears_in() -> None:
    """D-02's discovery query crosses list boundaries, which no other listing does.

    A fake that reused `list_for_task_list`'s scoping - or that answered from one
    list at a time - would return two of these three tasks, so the assertion is
    on the set of parent lists as well as on the titles.
    """
    tasks = FakeTaskRepository()
    await _given_assignments(tasks)

    assigned = await tasks.list_for_assignee(ASSIGNEE_ID)

    assert sorted(task.title for task in assigned) == [
        "Oldest",
        "Tied, higher id",
        "Tied, lower id",
    ]
    assert {task.task_list_id for task in assigned} == {TASK_LIST_ID, OTHER_LIST_ID}
    assert all(task.assignee_id == ASSIGNEE_ID for task in assigned)


async def test_list_for_assignee_is_empty_for_a_user_with_nothing_assigned() -> None:
    """Nothing assigned is an empty answer, never everything and never a raise.

    `STRANGER_ID` does have a task in the store, so this asks about a third user
    entirely: an implementation that ignored its argument would answer five here,
    and one that treated an unknown user as "no filter" would answer the same.
    """
    tasks = FakeTaskRepository()
    await _given_assignments(tasks)

    assert list(await tasks.list_for_assignee(OTHER_OWNER_ID)) == []
    assert list(await FakeTaskRepository().list_for_assignee(ASSIGNEE_ID)) == []


async def test_list_for_assignee_is_ordered_by_created_at_then_id() -> None:
    """The same total order the adapter's `ORDER BY created_at, id` produces.

    Two of the three share an instant to the microsecond, which is not contrived:
    the clock is read once per request. The insertion order in `_given_assignments`
    disagrees with the expected order on both axes, so neither `dict` ordering nor
    a sort on `created_at` alone can produce it.
    """
    tasks = FakeTaskRepository()
    await _given_assignments(tasks)

    assigned = await tasks.list_for_assignee(ASSIGNEE_ID)

    assert [task.id for task in assigned] == [
        OLDEST_TASK_ID,
        TIED_LOWER_TASK_ID,
        TIED_HIGHER_TASK_ID,
    ]


async def test_exists_with_name_matches_the_case_sensitive_unique_constraint() -> None:
    """The fake refuses exactly what `UNIQUE (owner_id, name)` refuses (D-12).

    `Groceries` collides with itself and with a padded spelling of itself - the
    entity strips on construction, so the argument is stripped too - but not
    with `groceries`, which the database would store as a second row.
    """
    repository = FakeTaskListRepository()
    await repository.add(_stored_list(owner_id=OWNER_ID, name="Groceries"))

    assert await repository.exists_with_name(OWNER_ID, "Groceries") is True
    assert await repository.exists_with_name(OWNER_ID, "  Groceries  ") is True
    assert await repository.exists_with_name(OWNER_ID, "groceries") is False


async def test_exists_with_name_is_scoped_to_one_owner() -> None:
    """The unique key leads with `owner_id`, so namespaces cannot collide.

    Two owners may each keep a list called `Groceries`; a check that ignored the
    owner would let one user's names block another's.
    """
    repository = FakeTaskListRepository()
    await repository.add(_stored_list(owner_id=OWNER_ID, name="Groceries"))

    assert await repository.exists_with_name(OTHER_OWNER_ID, "Groceries") is False


async def test_listing_with_stats_returns_one_entry_per_list_of_the_owner() -> None:
    """LIST-03's shape: the whole collection, each entry carrying its counters.

    The two lists get different mixes on purpose. A fake that returned the same
    `CompletionStats` for every entry - or one built from the first list it
    found - would satisfy an assertion about the length and about the entities,
    and only the differing counters catch it.
    """
    tasks = FakeTaskRepository()
    repository = FakeTaskListRepository(tasks)
    await repository.add(_stored_list(owner_id=OWNER_ID, name="Groceries"))
    await repository.add(
        _stored_list(owner_id=OWNER_ID, name="Chores", task_list_id=OTHER_LIST_ID)
    )
    await _given_tasks(tasks, task_list_id=TASK_LIST_ID, total=4, completed=1)
    await _given_tasks(tasks, task_list_id=OTHER_LIST_ID, total=2, completed=2)

    entries = await repository.list_for_owner_with_stats(OWNER_ID)

    assert [
        (entry[0].name, entry[1].total, entry[1].completed) for entry in entries
    ] == [
        ("Groceries", 4, 1),
        ("Chores", 2, 2),
    ]
    assert [entry[1].percentage for entry in entries] == [25.0, 100.0]


async def test_listing_with_stats_reports_zero_for_a_list_with_no_tasks() -> None:
    """An empty list is an ordinary list, and reports 0.0 rather than raising.

    This is the in-memory half of the `count(*)`-versus-`count(tasks.id)` trap
    the adapter's LEFT OUTER JOIN carries: there, a list with no tasks would
    otherwise report one phantom task. A fake that counted the same way - or
    that skipped a list with no tasks entirely - disagrees here.
    """
    tasks = FakeTaskRepository()
    repository = FakeTaskListRepository(tasks)
    await repository.add(_stored_list(owner_id=OWNER_ID, name="Empty"))

    entries = await repository.list_for_owner_with_stats(OWNER_ID)

    assert len(entries) == 1
    _, stats = entries[0]
    assert stats.total == 0
    assert stats.completed == 0
    assert stats.percentage == 0.0


async def test_listing_with_stats_never_returns_another_owners_list() -> None:
    """The owner is the only scope, exactly as the adapter's `WHERE` is (T-4-06).

    The other owner's list is given tasks too, so an implementation that counted
    across the whole task store rather than per list would also be caught here.
    """
    tasks = FakeTaskRepository()
    repository = FakeTaskListRepository(tasks)
    await repository.add(_stored_list(owner_id=OWNER_ID, name="Mine"))
    await repository.add(
        _stored_list(owner_id=OTHER_OWNER_ID, name="Theirs", task_list_id=OTHER_LIST_ID)
    )
    await _given_tasks(tasks, task_list_id=TASK_LIST_ID, total=1, completed=0)
    await _given_tasks(tasks, task_list_id=OTHER_LIST_ID, total=3, completed=3)

    entries = await repository.list_for_owner_with_stats(OWNER_ID)

    assert [entry[0].name for entry in entries] == ["Mine"]
    assert entries[0][1].total == 1


async def test_listing_with_stats_is_ordered_by_created_at_then_id() -> None:
    """D-13's total order, in the fake as in the adapter (04-PATTERNS §11).

    Two of the three lists share an instant to the microsecond, which is not
    contrived: the clock is read once per request, so a call that creates more
    than one list stamps them all identically. The insertion order below
    disagrees with the expected order on both axes, so neither `dict` ordering
    nor a sort on `created_at` alone can produce it - only the `id` tie-break.
    """
    repository = FakeTaskListRepository()
    await repository.add(
        _stored_list(
            owner_id=OWNER_ID,
            name="Tied, higher id",
            task_list_id=THIRD_LIST_ID,
            created_at=NOW,
        )
    )
    await repository.add(
        _stored_list(
            owner_id=OWNER_ID,
            name="Oldest",
            task_list_id=OTHER_LIST_ID,
            created_at=EARLIER,
        )
    )
    await repository.add(
        _stored_list(
            owner_id=OWNER_ID,
            name="Tied, lower id",
            task_list_id=TASK_LIST_ID,
            created_at=NOW,
        )
    )

    with_stats = await repository.list_for_owner_with_stats(OWNER_ID)
    plain = await repository.list_for_owner(OWNER_ID)

    expected = [OTHER_LIST_ID, TASK_LIST_ID, THIRD_LIST_ID]
    assert [entry[0].id for entry in with_stats] == expected
    # Asserted of both methods in one test, because the point is that they
    # agree: the endpoint reads one of them and a Phase 4 use case the other.
    assert [task_list.id for task_list in plain] == expected


async def test_list_all_is_ordered_by_created_at_then_id() -> None:
    """ASGN-03's directory order, in the fake as in the adapter (D-25).

    This fake was the last one still answering in insertion order, and the
    divergence was observed rather than anticipated: the failing run is in
    `.planning/phases/05-auth-assignment-notifications/evidence/
    05-02-fake-user-ordering.txt`.

    Two of the three accounts share an instant to the microsecond, which a seed
    script or a fixture produces routinely, and the registration order below
    disagrees with the expected order on both axes - so neither `dict` ordering
    nor a sort on `created_at` alone can produce it.
    """
    repository = FakeUserRepository()
    await repository.add(
        User.create(
            user_id=TIED_HIGHER_USER_ID,
            email="tied-higher@example.test",
            full_name="Tied Higher",
            password_hash=PASSWORD_HASH,
            now=NOW,
        )
    )
    await repository.add(
        User.create(
            user_id=OLDEST_USER_ID,
            email="oldest@example.test",
            full_name="Oldest Account",
            password_hash=PASSWORD_HASH,
            now=EARLIER,
        )
    )
    await repository.add(
        User.create(
            user_id=TIED_LOWER_USER_ID,
            email="tied-lower@example.test",
            full_name="Tied Lower",
            password_hash=PASSWORD_HASH,
            now=NOW,
        )
    )

    listed = await repository.list_all()

    assert [user.id for user in listed] == [
        OLDEST_USER_ID,
        TIED_LOWER_USER_ID,
        TIED_HIGHER_USER_ID,
    ]
