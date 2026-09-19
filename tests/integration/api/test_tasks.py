"""The six task routes, over HTTP, against the real database (D-16).

The sibling module `test_task_lists.py` states the two standards every test in
this package follows - assert on the **body**, never on the status code alone,
and re-read every mutation **through the API** - and they are not restated here.
Its constants, its builders and its `anonymised` helper are imported rather than
copied, for the reason it gives about the error contract: a second copy of a
shared fact is the one that quietly disagrees the first time the fact moves.

Two things are specific to this module, and both are about the nested path.

A task is only ever addressed as `/task-lists/{list_id}/tasks/{task_id}`, so
every refusal has two doors: the task may not exist, and the list segment may
not be the one that owns it. D-14 closes the second door with the same answer as
the first, and the wrong-list tests below assert it on **four verbs** rather than
on the one an evaluator happens to try - a parent segment honoured on GET and
ignored on DELETE is an ownership check that passes while checking nothing.

The create route is the single deliberate exception: it refuses with the
*list*-shaped error, because the caller addressed a list and no task exists yet
for the answer to be about. `use_cases/tasks/create.py` argues it at length; the
test that pins it says so in its docstring so a later reader does not "fix" it.
"""

import uuid
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from httpx import AsyncClient, Response

from taskmanager.domain.entities.task import Task
from taskmanager.domain.value_objects.task_priority import TaskPriority
from taskmanager.domain.value_objects.task_status import TaskStatus
from tests.api.test_error_contract import MEMBERS, PROBLEM_JSON
from tests.integration.api.test_task_lists import (
    LIST_ID,
    MISSING_LIST_ID,
    NOW,
    OTHER_EMAIL,
    OTHER_LIST_ID,
    OTHER_USER_ID,
    SECOND_TASK_ID,
    TASK_ID,
    TASK_LISTS,
    SessionFactory,
    a_task,
    a_task_list,
    a_user,
    anonymised,
    moment,
)
from tests.integration.conftest import acting_as, seed

pytestmark = pytest.mark.integration

# The same fixed series the sibling module uses, continued rather than restarted.
MISSING_TASK_ID = uuid.UUID("00000000-0000-4000-8000-0000000000fe")

# Two instants on either side of any moment this suite can run at. `Task.create`
# and `Task.reschedule` compare a due date against the *clock*, not against
# `NOW`, so a date that merely sits after the seeded `created_at` would start
# failing the day the suite is run after it - the exact flake a literal is worst
# at. These two are decades apart from each other and from today.
FUTURE_DUE_DATE = datetime(2030, 6, 1, 12, 0, tzinfo=UTC)
PAST_DUE_DATE = datetime(2020, 1, 1, 12, 0, tzinfo=UTC)

# The eleven members of `TaskResponse`, in the order it declares them. Pydantic
# serialises in declaration order, so the order is contract: `list(body)` sees a
# member added, dropped or moved, and a per-key lookup sees none of the three.
TASK_MEMBERS = [
    "id",
    "task_list_id",
    "title",
    "description",
    "status",
    "priority",
    "created_at",
    "updated_at",
    "due_date",
    "completed_at",
    "assignee_id",
]


def tasks_url(task_list_id: uuid.UUID) -> str:
    """The task collection of one list."""
    return f"{TASK_LISTS}/{task_list_id}/tasks"


def task_url(task_list_id: uuid.UUID, task_id: uuid.UUID) -> str:
    """One task, addressed through the list segment that has to be honoured."""
    return f"{TASK_LISTS}/{task_list_id}/tasks/{task_id}"


def status_url(task_list_id: uuid.UUID, task_id: uuid.UUID) -> str:
    """The status endpoint, the one door onto the state machine (D-11)."""
    return f"{task_url(task_list_id, task_id)}/status"


def assert_task_not_found(response: Response, task_id: uuid.UUID) -> None:
    """The one shape every task 404 in this module has to have.

    The `code` is asserted as well as the status, because `task_list_not_found`
    is also a 404 and would also be a plausible-looking answer - and it would
    carry an identifier the caller never named (D-04, D-14).
    """
    assert response.status_code == 404
    assert response.headers["content-type"] == PROBLEM_JSON

    body = response.json()

    assert list(body) == [*MEMBERS, "errors"]
    assert body["code"] == "task_not_found"
    assert body["title"] == "Task not found"
    assert body["errors"] == {"task_id": str(task_id)}


async def given_a_list(session_factory: SessionFactory) -> None:
    """The owner and one empty list: the starting point of most tests here.

    A task's row needs a list, and a list's row needs a user, so the two arrive
    together in every test that is not specifically about their absence. The
    seeding helper commits (see its docstring); without that the savepoint would
    roll back and the first request would answer 404 about a list the test
    plainly created.
    """
    await seed(session_factory, users=[a_user()], task_lists=[a_task_list()])


async def given_a_task(session_factory: SessionFactory) -> None:
    """One owner, one list, one pending task in it."""
    await seed(
        session_factory,
        users=[a_user()],
        task_lists=[a_task_list()],
        tasks=[a_task(task_id=TASK_ID)],
    )


async def given_a_stranger_and_a_task(session_factory: SessionFactory) -> None:
    """The same task, plus a second user who owns nothing (D-04)."""
    await seed(
        session_factory,
        users=[a_user(), a_user(user_id=OTHER_USER_ID, email=OTHER_EMAIL)],
        task_lists=[a_task_list()],
        tasks=[a_task(task_id=TASK_ID)],
    )


async def test_a_created_task_is_visible_to_the_next_request(
    api_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """The dullest test in the file, and the first one that would fail.

    A `POST` runs the real use case, which commits on the shared connection; the
    `GET` that follows opens another session and reads the row back. Everything
    below assumes this pair works.
    """
    await given_a_list(session_factory)
    client, _ = api_client

    created = await client.post(tasks_url(LIST_ID), json={"title": "Buy milk"})
    assert created.status_code == 201

    listed = await client.get(tasks_url(LIST_ID))

    assert listed.status_code == 200
    body = listed.json()
    assert [item["id"] for item in body["items"]] == [created.json()["id"]]


async def test_create_returns_201_with_a_location_header(
    api_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """TASK-01 and D-12: the defaults belong to the entity, and so does the URL.

    `pending` and `medium` are asserted against the entity's own constants
    rather than against literals, so raising either rule in one place cannot
    leave this test asserting a default the application no longer applies.

    Following the `Location` and comparing the two bodies is what makes this a
    contract test rather than a header test: a header naming a URL that answers
    something else would satisfy a suffix assertion on its own.
    """
    await given_a_list(session_factory)
    client, _ = api_client

    response = await client.post(tasks_url(LIST_ID), json={"title": "Buy milk"})

    assert response.status_code == 201
    body = response.json()

    assert list(body) == TASK_MEMBERS
    assert body["task_list_id"] == str(LIST_ID)
    assert body["title"] == "Buy milk"
    assert body["status"] == TaskStatus.PENDING.value
    assert body["priority"] == Task.DEFAULT_PRIORITY.value
    assert body["description"] is None
    assert body["due_date"] is None
    assert body["completed_at"] is None
    assert body["assignee_id"] is None
    assert body["created_at"] == body["updated_at"]

    location = response.headers["Location"]
    assert location.endswith(task_url(LIST_ID, uuid.UUID(body["id"])))

    followed = await client.get(location)

    assert followed.status_code == 200
    assert followed.json() == body


async def test_create_accepts_every_optional_field(
    api_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """All four fields round-trip, the due date as an ISO-8601 UTC instant.

    The deadline is compared as an *instant* rather than as text: Pydantic omits
    microseconds it does not have, so a value that landed on a whole second
    would serialise into a string a literal comparison would miss while the
    moment itself was right (the sibling module's `moment` helper).
    """
    await given_a_list(session_factory)
    client, _ = api_client

    response = await client.post(
        tasks_url(LIST_ID),
        json={
            "title": "Buy milk",
            "description": "Semi-skimmed",
            "priority": TaskPriority.HIGH.value,
            "due_date": FUTURE_DUE_DATE.isoformat(),
        },
    )

    assert response.status_code == 201
    body = response.json()

    assert list(body) == TASK_MEMBERS
    assert body["description"] == "Semi-skimmed"
    assert body["priority"] == TaskPriority.HIGH.value
    assert moment(body["due_date"]) == FUTURE_DUE_DATE
    assert moment(body["due_date"]).tzinfo is not None

    followed = await client.get(response.headers["Location"])

    assert followed.json() == body


async def test_get_returns_the_task(
    api_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """All eleven members, in declaration order, for a task written by the API."""
    await given_a_task(session_factory)
    client, _ = api_client

    response = await client.get(task_url(LIST_ID, TASK_ID))

    assert response.status_code == 200
    body = response.json()

    assert list(body) == TASK_MEMBERS
    assert body["id"] == str(TASK_ID)
    assert body["task_list_id"] == str(LIST_ID)
    assert body["title"] == "Buy milk"
    assert body["status"] == TaskStatus.PENDING.value
    assert moment(body["created_at"]) == NOW


async def test_patch_changes_only_the_title(
    api_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """D-05's omitted leg on `title`: the other three fields stand."""
    await seed(
        session_factory,
        users=[a_user()],
        task_lists=[a_task_list()],
        tasks=[
            Task(
                id=TASK_ID,
                task_list_id=LIST_ID,
                title="Buy milk",
                status=TaskStatus.PENDING,
                priority=TaskPriority.HIGH,
                created_at=NOW,
                updated_at=NOW,
                description="Semi-skimmed",
                due_date=FUTURE_DUE_DATE,
            )
        ],
    )
    client, _ = api_client
    before = (await client.get(task_url(LIST_ID, TASK_ID))).json()

    response = await client.patch(
        task_url(LIST_ID, TASK_ID), json={"title": "Buy oats"}
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Buy oats"

    after = (await client.get(task_url(LIST_ID, TASK_ID))).json()

    assert after["title"] == "Buy oats"
    assert after["description"] == before["description"]
    assert after["priority"] == before["priority"]
    assert after["due_date"] == before["due_date"]
    assert moment(after["updated_at"]) > moment(before["updated_at"])


async def test_patch_changes_only_the_description(
    api_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """The mirror leg on `description`."""
    await given_a_task(session_factory)
    client, _ = api_client
    before = (await client.get(task_url(LIST_ID, TASK_ID))).json()

    response = await client.patch(
        task_url(LIST_ID, TASK_ID), json={"description": "Semi-skimmed"}
    )

    assert response.status_code == 200
    assert response.json()["description"] == "Semi-skimmed"

    after = (await client.get(task_url(LIST_ID, TASK_ID))).json()

    assert after["description"] == "Semi-skimmed"
    assert after["title"] == before["title"]
    assert after["priority"] == before["priority"]
    assert after["due_date"] == before["due_date"]
    assert moment(after["updated_at"]) > moment(before["updated_at"])


async def test_patch_changes_only_the_priority(
    api_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """The mirror leg on `priority`, the field with no null of its own."""
    await given_a_task(session_factory)
    client, _ = api_client
    before = (await client.get(task_url(LIST_ID, TASK_ID))).json()

    response = await client.patch(
        task_url(LIST_ID, TASK_ID), json={"priority": TaskPriority.HIGH.value}
    )

    assert response.status_code == 200
    assert response.json()["priority"] == TaskPriority.HIGH.value

    after = (await client.get(task_url(LIST_ID, TASK_ID))).json()

    assert after["priority"] == TaskPriority.HIGH.value
    assert after["title"] == before["title"]
    assert after["description"] == before["description"]
    assert after["due_date"] == before["due_date"]
    assert moment(after["updated_at"]) > moment(before["updated_at"])


async def test_patch_changes_only_the_due_date(
    api_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """The mirror leg on `due_date`, and the status is untouched throughout."""
    await given_a_task(session_factory)
    client, _ = api_client
    before = (await client.get(task_url(LIST_ID, TASK_ID))).json()

    response = await client.patch(
        task_url(LIST_ID, TASK_ID), json={"due_date": FUTURE_DUE_DATE.isoformat()}
    )

    assert response.status_code == 200
    assert moment(response.json()["due_date"]) == FUTURE_DUE_DATE

    after = (await client.get(task_url(LIST_ID, TASK_ID))).json()

    assert moment(after["due_date"]) == FUTURE_DUE_DATE
    assert after["title"] == before["title"]
    assert after["description"] == before["description"]
    assert after["priority"] == before["priority"]
    assert after["status"] == before["status"]
    assert moment(after["updated_at"]) > moment(before["updated_at"])


async def test_patch_with_an_explicit_null_clears_the_description(
    api_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """D-05's null leg: an implementation reading the value instead of the set
    of keys the client sent would leave the description standing and still
    answer 200."""
    await seed(
        session_factory,
        users=[a_user()],
        task_lists=[a_task_list()],
        tasks=[
            Task(
                id=TASK_ID,
                task_list_id=LIST_ID,
                title="Buy milk",
                status=TaskStatus.PENDING,
                priority=Task.DEFAULT_PRIORITY,
                created_at=NOW,
                updated_at=NOW,
                description="Semi-skimmed",
            )
        ],
    )
    client, _ = api_client

    response = await client.patch(
        task_url(LIST_ID, TASK_ID), json={"description": None}
    )

    assert response.status_code == 200
    assert response.json()["description"] is None

    after = (await client.get(task_url(LIST_ID, TASK_ID))).json()

    assert after["description"] is None
    assert after["title"] == "Buy milk"


async def test_patch_with_an_explicit_null_clears_the_due_date(
    api_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """The second of the two fields that have a null to be cleared to (D-05)."""
    await seed(
        session_factory,
        users=[a_user()],
        task_lists=[a_task_list()],
        tasks=[
            Task(
                id=TASK_ID,
                task_list_id=LIST_ID,
                title="Buy milk",
                status=TaskStatus.PENDING,
                priority=Task.DEFAULT_PRIORITY,
                created_at=NOW,
                updated_at=NOW,
                due_date=FUTURE_DUE_DATE,
            )
        ],
    )
    client, _ = api_client

    response = await client.patch(task_url(LIST_ID, TASK_ID), json={"due_date": None})

    assert response.status_code == 200
    assert response.json()["due_date"] is None

    after = (await client.get(task_url(LIST_ID, TASK_ID))).json()

    assert after["due_date"] is None


async def test_a_patch_without_due_date_leaves_an_overdue_task_patchable(
    api_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """D-07: the deadline rule validates input, it does not retro-invalidate a row.

    The overdue task is written through the mapper rather than through the API,
    because `Task.create` refuses a deadline behind the creation moment - the
    state this test needs is reachable by the passage of time and by nothing
    else. A `reschedule` called on every patch, rather than only on a patch that
    names `due_date`, would answer 422 here and lock the task forever.
    """
    await seed(
        session_factory,
        users=[a_user()],
        task_lists=[a_task_list()],
        tasks=[
            Task(
                id=TASK_ID,
                task_list_id=LIST_ID,
                title="Buy milk",
                status=TaskStatus.PENDING,
                priority=Task.DEFAULT_PRIORITY,
                created_at=NOW,
                updated_at=NOW,
                due_date=PAST_DUE_DATE,
            )
        ],
    )
    client, _ = api_client

    response = await client.patch(
        task_url(LIST_ID, TASK_ID), json={"title": "Buy oats"}
    )

    assert response.status_code == 200
    body = response.json()

    assert body["title"] == "Buy oats"
    assert moment(body["due_date"]) == PAST_DUE_DATE


async def test_delete_returns_204_with_an_empty_body(
    api_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """TASK-04: no content, and no header describing content that is not there.

    The absent `content-type` is the measured difference the bare response class
    on the route makes; without it a 204 returning `None` still advertises
    `application/json` over an empty body.
    """
    await given_a_task(session_factory)
    client, _ = api_client

    response = await client.delete(task_url(LIST_ID, TASK_ID))

    assert response.status_code == 204
    assert response.content == b""
    assert "content-type" not in response.headers

    gone = await client.get(task_url(LIST_ID, TASK_ID))

    assert_task_not_found(gone, TASK_ID)


async def test_get_an_absent_task_is_404(
    api_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """The answer every refusal below is measured against."""
    await given_a_list(session_factory)
    client, _ = api_client

    response = await client.get(task_url(LIST_ID, MISSING_TASK_ID))

    assert_task_not_found(response, MISSING_TASK_ID)
    assert response.json()["instance"] == task_url(LIST_ID, MISSING_TASK_ID)


async def test_a_get_under_the_wrong_list_is_404_exactly_like_an_absent_task(
    api_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """D-14 and TASK-02 on GET: the parent segment is compared, never ignored.

    Both lists belong to the caller, so ownership cannot be what refuses this -
    only the mismatch between the task's own parent and the list named in the
    path. The two bodies are compared with each response's own identifier
    tokenised out, which leaves `instance` - the request path - compared too.
    """
    await seed(
        session_factory,
        users=[a_user()],
        task_lists=[
            a_task_list(),
            a_task_list(task_list_id=OTHER_LIST_ID, name="Chores"),
        ],
        tasks=[a_task(task_id=TASK_ID)],
    )
    client, _ = api_client

    wrong_list = await client.get(task_url(OTHER_LIST_ID, TASK_ID))
    absent = await client.get(task_url(OTHER_LIST_ID, MISSING_TASK_ID))

    assert_task_not_found(wrong_list, TASK_ID)
    assert_task_not_found(absent, MISSING_TASK_ID)
    assert anonymised(wrong_list, TASK_ID) == anonymised(absent, MISSING_TASK_ID)

    # And the task is still perfectly readable under the list that does own it,
    # so the refusal above is about the path rather than about the task.
    assert (await client.get(task_url(LIST_ID, TASK_ID))).status_code == 200


async def test_a_patch_under_the_wrong_list_is_404(
    api_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """D-14 on PATCH, and the refused write is not a half-applied one."""
    await seed(
        session_factory,
        users=[a_user()],
        task_lists=[
            a_task_list(),
            a_task_list(task_list_id=OTHER_LIST_ID, name="Chores"),
        ],
        tasks=[a_task(task_id=TASK_ID)],
    )
    client, _ = api_client

    response = await client.patch(
        task_url(OTHER_LIST_ID, TASK_ID), json={"title": "Hijacked"}
    )

    assert_task_not_found(response, TASK_ID)

    survivor = await client.get(task_url(LIST_ID, TASK_ID))

    assert survivor.json()["title"] == "Buy milk"


async def test_a_delete_under_the_wrong_list_is_404(
    api_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """D-14 on DELETE, the verb where a 204 would destroy what it leaked."""
    await seed(
        session_factory,
        users=[a_user()],
        task_lists=[
            a_task_list(),
            a_task_list(task_list_id=OTHER_LIST_ID, name="Chores"),
        ],
        tasks=[a_task(task_id=TASK_ID)],
    )
    client, _ = api_client

    response = await client.delete(task_url(OTHER_LIST_ID, TASK_ID))

    assert_task_not_found(response, TASK_ID)

    survivor = await client.get(task_url(LIST_ID, TASK_ID))

    assert survivor.status_code == 200


async def test_a_status_change_under_the_wrong_list_is_404(
    api_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """D-14 on the status endpoint - the fourth verb, and the one most easily
    forgotten, because it is the only route whose path carries a segment after
    the task identifier."""
    await seed(
        session_factory,
        users=[a_user()],
        task_lists=[
            a_task_list(),
            a_task_list(task_list_id=OTHER_LIST_ID, name="Chores"),
        ],
        tasks=[a_task(task_id=TASK_ID)],
    )
    client, _ = api_client

    response = await client.patch(
        status_url(OTHER_LIST_ID, TASK_ID),
        json={"status": TaskStatus.COMPLETED.value},
    )

    assert_task_not_found(response, TASK_ID)

    survivor = await client.get(task_url(LIST_ID, TASK_ID))

    assert survivor.json()["status"] == TaskStatus.PENDING.value


async def test_getting_a_task_in_a_list_the_actor_does_not_own_is_404(
    api_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """D-04 on GET: a stranger gets the *task*-shaped answer, deliberately.

    `task_list_not_found` would also be a 404, and would also look reasonable -
    and it would differ in `code` and carry the identifier of a list the caller
    only guessed at. The guard compares the task's parent before it loads the
    addressed list precisely so that cannot happen.
    """
    await given_a_stranger_and_a_task(session_factory)
    client, app = api_client

    with acting_as(app, OTHER_USER_ID):
        not_owned = await client.get(task_url(LIST_ID, TASK_ID))
        absent = await client.get(task_url(LIST_ID, MISSING_TASK_ID))

    assert_task_not_found(not_owned, TASK_ID)
    assert not_owned.json()["code"] != "task_list_not_found"
    assert anonymised(not_owned, TASK_ID) == anonymised(absent, MISSING_TASK_ID)


async def test_patching_a_task_in_a_list_the_actor_does_not_own_is_404(
    api_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """D-04 on PATCH, with the owner's task read back to prove nothing moved."""
    await given_a_stranger_and_a_task(session_factory)
    client, app = api_client

    with acting_as(app, OTHER_USER_ID):
        response = await client.patch(
            task_url(LIST_ID, TASK_ID), json={"title": "Hijacked"}
        )

    assert_task_not_found(response, TASK_ID)
    assert response.json()["code"] != "task_list_not_found"

    survivor = await client.get(task_url(LIST_ID, TASK_ID))

    assert survivor.json()["title"] == "Buy milk"


async def test_deleting_a_task_in_a_list_the_actor_does_not_own_is_404(
    api_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """D-04 on DELETE: the stranger's 404 and the owner's task, in one test."""
    await given_a_stranger_and_a_task(session_factory)
    client, app = api_client

    with acting_as(app, OTHER_USER_ID):
        response = await client.delete(task_url(LIST_ID, TASK_ID))

    assert_task_not_found(response, TASK_ID)
    assert response.json()["code"] != "task_list_not_found"

    survivor = await client.get(task_url(LIST_ID, TASK_ID))

    assert survivor.status_code == 200


async def test_changing_the_status_of_a_task_the_actor_does_not_own_is_404(
    api_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """D-04 on the status endpoint.

    In Phase 4 there is no assignee capability at all: the only caller who may
    move a task through its lifecycle is the owner of the list it sits in. Phase
    5 adds the assignee's view and the 403 leg (ASGN-02); until then this 404 is
    the whole rule.
    """
    await given_a_stranger_and_a_task(session_factory)
    client, app = api_client

    with acting_as(app, OTHER_USER_ID):
        response = await client.patch(
            status_url(LIST_ID, TASK_ID),
            json={"status": TaskStatus.COMPLETED.value},
        )

    assert_task_not_found(response, TASK_ID)
    assert response.json()["code"] != "task_list_not_found"

    survivor = await client.get(task_url(LIST_ID, TASK_ID))

    assert survivor.json()["status"] == TaskStatus.PENDING.value


async def test_creating_a_task_in_a_list_the_actor_does_not_own_is_404(
    api_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """The one leg that answers `task_list_not_found`, and it is deliberate.

    Every other refusal in this module is task-shaped. Create is different
    because the caller addressed a *list* and no task exists yet, so there is no
    task identifier the answer could be about and nothing the list-shaped error
    discloses that the request did not already carry. This is not an
    inconsistency to be tidied away: `use_cases/tasks/create.py` argues it in
    full, and a later reader who "fixes" it would be inventing an identifier to
    report.
    """
    await seed(
        session_factory,
        users=[a_user(), a_user(user_id=OTHER_USER_ID, email=OTHER_EMAIL)],
        task_lists=[a_task_list()],
    )
    client, app = api_client

    with acting_as(app, OTHER_USER_ID):
        not_owned = await client.post(tasks_url(LIST_ID), json={"title": "Intruder"})
        absent = await client.post(
            tasks_url(MISSING_LIST_ID), json={"title": "Intruder"}
        )

    assert not_owned.status_code == 404
    assert not_owned.json()["code"] == "task_list_not_found"
    assert not_owned.json()["errors"] == {"task_list_id": str(LIST_ID)}
    assert anonymised(not_owned, LIST_ID) == anonymised(absent, MISSING_LIST_ID)

    # Nothing was written into the list the stranger addressed.
    owner_view = await client.get(tasks_url(LIST_ID))

    assert owner_view.json()["items"] == []


async def test_a_malformed_task_id_is_a_request_validation_error(
    api_client: tuple[AsyncClient, FastAPI],
) -> None:
    """A path segment that is not a UUID is refused before any use case runs."""
    client, _ = api_client

    response = await client.get(f"{tasks_url(LIST_ID)}/not-a-uuid")

    assert response.status_code == 422
    assert response.headers["content-type"] == PROBLEM_JSON

    body = response.json()

    assert body["title"] == "Request validation failed"
    assert [entry["field"] for entry in body["errors"]] == ["path.task_id"]


async def test_an_over_length_title_is_a_domain_validation_error(
    api_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """The **object** `errors` shape, from the limit the entity owns.

    The string is built from `Task.TITLE_MAX_LENGTH` rather than from a literal,
    so raising the entity's limit cannot leave this test asserting a refusal
    that no longer happens. Pydantic declares no length constraint on `title`
    (Phase 2 D-04 keeps every business limit in the entity), so the request is
    well-formed all the way to `Task.create` and comes back with the domain
    producer's title and shape (04-RESEARCH Pitfall 5).
    """
    await given_a_list(session_factory)
    client, _ = api_client

    response = await client.post(
        tasks_url(LIST_ID), json={"title": "x" * (Task.TITLE_MAX_LENGTH + 1)}
    )

    assert response.status_code == 422
    assert response.headers["content-type"] == PROBLEM_JSON

    body = response.json()

    assert list(body) == [*MEMBERS, "errors"]
    assert body["code"] == "validation_error"
    assert body["title"] == "Validation error"
    assert body["errors"] == {"field": "title"}


async def test_the_collection_of_a_list_the_actor_does_not_own_is_404(
    api_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """`GET .../tasks` is addressed at a list, so it answers list-shaped too.

    Measured rather than assumed: the collection route names no task, so the
    only identifier its refusal could carry is the one in the path.
    """
    await seed(
        session_factory,
        users=[a_user(), a_user(user_id=OTHER_USER_ID, email=OTHER_EMAIL)],
        task_lists=[a_task_list()],
        tasks=[
            a_task(task_id=TASK_ID),
            a_task(task_id=SECOND_TASK_ID, title="Buy eggs"),
        ],
    )
    client, app = api_client

    with acting_as(app, OTHER_USER_ID):
        not_owned = await client.get(tasks_url(LIST_ID))
        absent = await client.get(tasks_url(MISSING_LIST_ID))

    assert not_owned.status_code == 404
    assert not_owned.json()["code"] == "task_list_not_found"
    assert str(TASK_ID) not in not_owned.text
    assert str(SECOND_TASK_ID) not in not_owned.text
    assert anonymised(not_owned, LIST_ID) == anonymised(absent, MISSING_LIST_ID)
