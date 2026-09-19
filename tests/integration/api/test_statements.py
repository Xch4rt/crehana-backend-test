"""No N+1, as a counter rather than a claim (D-17, LIST-03, TASK-07).

This module asserts the **number** of statements a request issues, and never
their text. The text already has a home: `test_repositories_task_lists.py` and
`test_repositories_tasks.py` compile the grouped statement and the aggregate
against the psycopg dialect with no server running, and assert on the rendered
SQL - that `count(*) FILTER (WHERE ...)` is there, that there is one `FROM
tasks`, that the `GROUP BY` is where it should be. What a compiled statement
cannot say is how many times the application runs it. A repository that emits a
perfect single aggregate and a use case that calls it once per row would pass
every assertion over there and would still be the N+1 that ADR-009 exists to
prevent.

So the two halves are complementary and neither is redundant: the repository
suites prove the shape, and this module proves the execution. Together they make
"one grouped statement" true in both senses.

Three properties are asserted per endpoint, because each alone is weak.

The **exact count** - a test that only compared one row against many would be
perfectly happy with a request that issued five statements in both cases.

The **invariance** between one row and several - an exact count alone would go
on passing if the extra statements arrived only once the list held more than one
task, which is precisely how an N+1 presents.

And **non-vacuity**, in a test of its own. The recorder is an event listener
attached to a connection; a listener that silently failed to attach would make
every assertion above pass by recording nothing at all, and the run would be
green for the worst possible reason.

The listener is the `statements` fixture from `tests/integration/conftest.py`,
which is attached to the *test* connection. That is the right one and not a
compromise: `get_uow` is overridden, so the request runs on that connection and
the application's own engine is never dialled. Attaching a second listener to
the application's engine here would record nothing and prove nothing.
"""

import uuid

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from taskmanager.domain.value_objects.task_status import TaskStatus
from tests.integration.api.test_task_lists import (
    LIST_ID,
    NOW,
    OTHER_LIST_ID,
    SECOND_TASK_ID,
    TASK_ID,
    TASK_LISTS,
    THIRD_TASK_ID,
    SessionFactory,
    a_task,
    a_task_list,
    a_user,
)
from tests.integration.api.test_tasks import FIFTH_TASK_ID, FOURTH_TASK_ID, tasks_url
from tests.integration.conftest import seed

pytestmark = pytest.mark.integration

# The sibling modules name two lists and five tasks; the invariance test below
# needs five lists, so the series continues here rather than restarting.
THIRD_LIST_ID = uuid.UUID("00000000-0000-4000-8000-000000000014")
FOURTH_LIST_ID = uuid.UUID("00000000-0000-4000-8000-000000000015")
FIFTH_LIST_ID = uuid.UUID("00000000-0000-4000-8000-000000000016")

# A second instant, so the rows added in the second half of a test are not all
# tied on `created_at` - the order is then decided by the timestamp as well as
# by the id, which is the ordinary case a count should be measured against.
LATER_MOMENT = NOW.replace(month=4)

# `GET /api/v1/task-lists` is one grouped statement: the lists and every list's
# counters arrive together (D-10, LIST-03).
TASK_LISTS_STATEMENTS = ["SELECT"]

# `GET /api/v1/task-lists/{id}/tasks` is **three**, and each one is there for a
# reason a reader should be able to name:
#
#   1. the visibility guard - `visible_task_list` loads the parent and discards
#      it, so a list this caller cannot see is refused before a single task is
#      read (D-04, ADR-008). 04-10-PLAN.md predicted two statements and did not
#      count this one; the guard is a decision of the same phase, so the number
#      is corrected here rather than the guard being removed to meet it.
#   2. the page of tasks, narrowed by whatever filter the caller sent.
#   3. the completion aggregate over the *whole* list, which is why it cannot
#      share the statement above (ADR-009, D-09, roadmap SC-4).
#
# None of the three is issued once per row, and that is the whole claim: the
# count is three for an empty list and three for a thousand tasks. A reader
# tempted to "optimise" this to one would be asking the filter and the
# statistics to share a query, which is the bug TASK-07 is about.
TASK_COLLECTION_STATEMENTS = ["SELECT", "SELECT", "SELECT"]


async def test_the_recorder_sees_statements_at_all(
    api_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
    statements: list[str],
) -> None:
    """The non-vacuity guard every other test in this module depends on.

    Without it, a listener that failed to attach - a renamed event, a facade
    that stopped exposing the sync connection underneath, a fixture reordering
    that put the recorder on a different connection from the request - would
    make every count below compare an empty list with an empty list and pass.
    """
    await seed(session_factory, users=[a_user()], task_lists=[a_task_list()])
    client, _ = api_client
    statements.clear()

    response = await client.get(TASK_LISTS)

    assert response.status_code == 200
    assert statements != []
    assert set(statements) <= {"SELECT", "INSERT", "UPDATE", "DELETE"}


async def test_the_task_lists_collection_issues_the_same_statements_for_one_list_and_for_many(  # noqa: E501
    api_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
    statements: list[str],
) -> None:
    """LIST-03: the collection's cost does not follow the number of lists.

    The naive implementation - list the lists, then ask each one for its
    completion statistics - answers exactly the same JSON and issues one
    statement per list. That is the failure this test exists to catch, and no
    amount of reading the response body would catch it.

    The recorder is cleared after each seeding, because the seeding helper's own
    `INSERT`s run on the same connection and would otherwise be counted as work
    the request did.
    """
    await seed(session_factory, users=[a_user()], task_lists=[a_task_list()])
    client, _ = api_client
    statements.clear()

    one = await client.get(TASK_LISTS)
    for_one_list = list(statements)

    assert one.status_code == 200
    assert len(one.json()) == 1
    assert for_one_list == TASK_LISTS_STATEMENTS

    await seed(
        session_factory,
        task_lists=[
            a_task_list(task_list_id=OTHER_LIST_ID, name="Chores"),
            a_task_list(task_list_id=THIRD_LIST_ID, name="Reading"),
            a_task_list(task_list_id=FOURTH_LIST_ID, name="Errands"),
            a_task_list(task_list_id=FIFTH_LIST_ID, name="Garden"),
        ],
        tasks=[
            a_task(task_id=TASK_ID),
            a_task(task_id=SECOND_TASK_ID, task_list_id=OTHER_LIST_ID),
            a_task(
                task_id=THIRD_TASK_ID,
                task_list_id=THIRD_LIST_ID,
                status=TaskStatus.COMPLETED,
            ),
        ],
    )
    statements.clear()

    many = await client.get(TASK_LISTS)
    for_many_lists = list(statements)

    assert many.status_code == 200
    assert len(many.json()) == 5
    assert for_many_lists == for_one_list


async def test_the_task_collection_issues_the_same_statements_for_one_task_and_for_many(
    api_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
    statements: list[str],
) -> None:
    """TASK-07: three statements, and three whatever the list holds.

    Three on purpose, and the constant above names each one. The guard is not
    overhead to be optimised away - it is D-04 - and the page and the aggregate
    are separate because collapsing them would make the statistics follow the
    filter, which is exactly what D-09 and roadmap SC-4 forbid. The claim being
    enforced here is not "one statement" but "a fixed number": the count is the
    same for one task and for five.
    """
    await seed(
        session_factory,
        users=[a_user()],
        task_lists=[a_task_list()],
        tasks=[a_task(task_id=TASK_ID)],
    )
    client, _ = api_client
    statements.clear()

    one = await client.get(tasks_url(LIST_ID))
    for_one_task = list(statements)

    assert one.status_code == 200
    assert len(one.json()["items"]) == 1
    assert for_one_task == TASK_COLLECTION_STATEMENTS

    await seed(
        session_factory,
        tasks=[
            a_task(task_id=SECOND_TASK_ID, title="Buy eggs"),
            a_task(task_id=THIRD_TASK_ID, title="Call the plumber"),
            a_task(
                task_id=FOURTH_TASK_ID, title="File the return", created_at=LATER_MOMENT
            ),
            a_task(
                task_id=FIFTH_TASK_ID,
                title="Water the plants",
                status=TaskStatus.COMPLETED,
                created_at=LATER_MOMENT,
            ),
        ],
    )
    statements.clear()

    many = await client.get(tasks_url(LIST_ID))
    for_many_tasks = list(statements)

    assert many.status_code == 200
    assert len(many.json()["items"]) == 5
    assert many.json()["completion_percentage"] == 20.0
    assert for_many_tasks == for_one_task


async def test_the_task_collection_statement_count_does_not_change_with_a_filter(
    api_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
    statements: list[str],
) -> None:
    """The filter reaches SQL; it is not a narrowing done afterwards.

    A filter applied in Python would read the whole list and then narrow it -
    the same three statements, and this test would not see it - but a filter
    applied by asking the database an *extra* time, once for the rows and once
    again for the filtered rows, is a real and easy mistake, and that is what
    the equality below refuses.
    """
    await seed(
        session_factory,
        users=[a_user()],
        task_lists=[a_task_list()],
        tasks=[
            a_task(task_id=TASK_ID),
            a_task(task_id=SECOND_TASK_ID, title="Buy eggs"),
            a_task(
                task_id=THIRD_TASK_ID,
                title="File the return",
                status=TaskStatus.COMPLETED,
            ),
        ],
    )
    client, _ = api_client
    statements.clear()

    unfiltered = await client.get(tasks_url(LIST_ID))
    without_a_filter = list(statements)
    statements.clear()

    filtered = await client.get(
        tasks_url(LIST_ID), params={"status": TaskStatus.PENDING.value}
    )
    with_a_filter = list(statements)

    assert unfiltered.status_code == 200
    assert filtered.status_code == 200
    assert len(filtered.json()["items"]) < len(unfiltered.json()["items"])
    assert without_a_filter == TASK_COLLECTION_STATEMENTS
    assert with_a_filter == without_a_filter
