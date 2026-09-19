"""The five task-list routes, over HTTP, against the real database (D-16).

Every test here drives the application a client would reach: an httpx request
through `ASGITransport`, the real routers, the real use cases, the real
adapters, and PostgreSQL underneath. Nothing is faked and nothing is stubbed,
which is what makes this module the first place LIST-01..LIST-06 are provable
rather than merely implemented.

Two standards apply to every test below, and both cost nothing now and a great
deal later. Each asserts on the **response body**, never on the status code
alone - a 201 whose body is missing a counter is a broken contract that a status
assertion cannot see. And each mutating test **re-reads through the API**, so
"it was written" is a fact about the database rather than about the return value
of the handler that claimed to write it.

The smoke pair at the top is deliberately the dullest thing in the file, and it
is the one that would fail first if the harness were wrong: it proves that the
`get_uow` override, the savepoint the seeding helper releases, and the use
case's own `commit()` all line up on one connection.
"""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from taskmanager.domain.entities.task import Task
from taskmanager.domain.entities.task_list import TaskList
from taskmanager.domain.entities.user import User
from taskmanager.domain.value_objects.task_status import TaskStatus
from taskmanager.infrastructure.db.repositories.tasks import SqlAlchemyTaskRepository

# `OWNER_ID` comes from the harness for the same reason: `api_client` installs
# it as the caller, so the identifier and the override have to be one value.
from tests.integration.conftest import OWNER_ID, acting_as, seed

# Imported rather than re-declared. The media type and the six-member list
# are the error contract Phase 2 fixed, and `tests/problem_details.py` is where
# they are stated; a second copy here would be the one that quietly disagreed
# the first time the contract moved. A rename over there breaks this import
# loudly, which is the failure mode to prefer.
from tests.problem_details import MEMBERS, PROBLEM_JSON

# The `session_factory` fixture's type, spelled once: every seeding call below
# takes it, and repeating the two-part annotation per test would add noise
# without adding a check.
SessionFactory = Callable[[], AsyncSession]

pytestmark = pytest.mark.integration

# Fixed identifiers and fixed instants, in the readable series the sibling
# integration modules use. A value generated at run time would make an assertion
# about "the list that was renamed" true of whichever row happened to be there,
# and the ordering tests below are exactly where that stops being noticed.
OTHER_USER_ID = uuid.UUID("00000000-0000-4000-8000-000000000002")
LIST_ID = uuid.UUID("00000000-0000-4000-8000-000000000011")
OTHER_LIST_ID = uuid.UUID("00000000-0000-4000-8000-000000000012")
FOREIGN_LIST_ID = uuid.UUID("00000000-0000-4000-8000-000000000013")
TASK_ID = uuid.UUID("00000000-0000-4000-8000-000000000021")
SECOND_TASK_ID = uuid.UUID("00000000-0000-4000-8000-000000000022")
THIRD_TASK_ID = uuid.UUID("00000000-0000-4000-8000-000000000023")
MISSING_LIST_ID = uuid.UUID("00000000-0000-4000-8000-0000000000ff")

NOW = datetime(2026, 3, 14, 15, 9, 26, 535897, tzinfo=UTC)

PASSWORD_HASH = "argon2-placeholder-hash-value"
DEMO_EMAIL = "demo@example.test"
OTHER_EMAIL = "other@example.test"
DEMO_FULL_NAME = "Demo Person"

TASK_LISTS = "/api/v1/task-lists"

# D-10's nine members, in the order `TaskListResponse` declares them. Pydantic
# serialises in declaration order, so the *order* is contract too: a client that
# reads the body as an ordered document should not have it rearranged under
# them, and a member silently added or dropped is what `list(body)` catches and
# a per-key lookup does not.
TASK_LIST_MEMBERS = [
    "id",
    "owner_id",
    "name",
    "description",
    "created_at",
    "updated_at",
    "total_tasks",
    "completed_tasks",
    "completion_percentage",
]


def a_user(
    *,
    user_id: uuid.UUID = OWNER_ID,
    email: str = DEMO_EMAIL,
    full_name: str = DEMO_FULL_NAME,
) -> User:
    """A valid user entity, differing from the harness's caller only where asked.

    `task_lists.owner_id` is a foreign key, so every test that creates a list
    needs the row behind the actor `api_client` overrides the seam with. The
    default is that actor, which is why almost every call below takes no
    argument at all.

    Nothing here depends on a row the container wrote. Plan 05-10 deleted the
    entrypoint's demo seed outright, and even before that the `test` stage
    carried no entrypoint - a suite that relied on one would pass or fail
    according to how the database happened to be started.
    """
    return User.create(
        user_id=user_id,
        email=email,
        full_name=full_name,
        password_hash=PASSWORD_HASH,
        now=NOW,
    )


def moment(value: str) -> datetime:
    """A timestamp off the wire, as an instant rather than as text.

    Comparing the two ISO-8601 strings directly would work for the pairs below
    and would stop working the first time one of them landed on a whole second:
    Pydantic omits the microseconds it has none of, and `"...:00Z"` sorts after
    `"...:00.5Z"`. Parsing removes a trap that would surface as a flake months
    from now rather than as a failure today.
    """
    return datetime.fromisoformat(value)


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


def a_task(
    *,
    task_id: uuid.UUID,
    task_list_id: uuid.UUID = LIST_ID,
    title: str = "Buy milk",
    status: TaskStatus = TaskStatus.PENDING,
    created_at: datetime = NOW,
) -> Task:
    """A valid task entity, completed ones carrying the stamp the entity demands.

    `Task.__post_init__` refuses a completed task with no `completed_at` and an
    unfinished one that carries it, so the pair is derived here rather than
    passed separately - a fixture cannot construct the incoherent combination
    even by accident.
    """
    return Task(
        id=task_id,
        task_list_id=task_list_id,
        title=title,
        status=status,
        priority=Task.DEFAULT_PRIORITY,
        created_at=created_at,
        updated_at=created_at,
        completed_at=created_at if status is TaskStatus.COMPLETED else None,
    )


async def test_the_collection_is_empty_for_an_actor_who_owns_nothing(
    api_client: tuple[AsyncClient, FastAPI],
) -> None:
    """200 with an empty array: the collection exists whether or not it has members."""
    client, _ = api_client

    response = await client.get(TASK_LISTS)

    assert response.status_code == 200
    assert response.json() == []


async def test_a_created_list_is_visible_to_the_next_request(
    api_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """The end-to-end proof that the harness works at all.

    A `POST` runs the real use case, which opens its own session on the shared
    connection and commits; the `GET` that follows opens another and reads the
    row back. If the `get_uow` override were pointed at the application's own
    engine, or if the seeded user's savepoint had been rolled back instead of
    released, this pair is what would notice.
    """
    await seed(session_factory, users=[a_user()])
    client, _ = api_client

    created = await client.post(TASK_LISTS, json={"name": "Groceries"})
    assert created.status_code == 201

    listed = await client.get(TASK_LISTS)

    assert listed.status_code == 200
    body = listed.json()
    assert len(body) == 1
    assert body[0]["name"] == "Groceries"
    assert body[0]["id"] == created.json()["id"]


async def test_create_returns_201_with_a_location_header_and_the_full_representation(
    api_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """D-12's create contract: 201, a Location header, and the whole resource.

    The `Location` is checked as a suffix of the URL the header actually
    carries, so a change to either the `/api/v1` prefix or the router's own
    `/task-lists` still produces a header a client can follow - which is what
    `request.url_for` buys over an f-string, and what this assertion is here to
    keep honest.

    Following the header and comparing the two bodies is the part that makes
    this a contract test rather than a header test: a Location naming a URL that
    answers something else would satisfy the suffix assertion on its own.
    """
    await seed(session_factory, users=[a_user()])
    client, _ = api_client

    response = await client.post(
        TASK_LISTS,
        json={"name": "Groceries", "description": "Everything for the week"},
    )

    assert response.status_code == 201
    body = response.json()

    assert list(body) == TASK_LIST_MEMBERS
    assert body["owner_id"] == str(OWNER_ID)
    assert body["name"] == "Groceries"
    assert body["description"] == "Everything for the week"
    assert body["created_at"] == body["updated_at"]
    assert body["total_tasks"] == 0
    assert body["completed_tasks"] == 0
    assert body["completion_percentage"] == 0.0

    location = response.headers["Location"]
    assert location.endswith(f"{TASK_LISTS}/{body['id']}")

    followed = await client.get(location)

    assert followed.status_code == 200
    assert followed.json() == body


async def test_create_accepts_a_list_with_no_description(
    api_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """`description` is optional, and its absence is a null rather than an omission."""
    await seed(session_factory, users=[a_user()])
    client, _ = api_client

    response = await client.post(TASK_LISTS, json={"name": "Groceries"})

    assert response.status_code == 201
    body = response.json()

    assert list(body) == TASK_LIST_MEMBERS
    assert body["description"] is None

    stored = await client.get(f"{TASK_LISTS}/{body['id']}")

    assert stored.status_code == 200
    assert stored.json() == body


async def test_get_returns_the_list_with_its_statistics(
    api_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """D-10: two of three tasks done is 66.67, rounded to two decimals."""
    await seed(
        session_factory,
        users=[a_user()],
        task_lists=[a_task_list()],
        tasks=[
            a_task(task_id=TASK_ID, status=TaskStatus.COMPLETED),
            a_task(task_id=SECOND_TASK_ID, status=TaskStatus.COMPLETED),
            a_task(task_id=THIRD_TASK_ID),
        ],
    )
    client, _ = api_client

    response = await client.get(f"{TASK_LISTS}/{LIST_ID}")

    assert response.status_code == 200
    body = response.json()

    assert list(body) == TASK_LIST_MEMBERS
    assert body["id"] == str(LIST_ID)
    assert body["total_tasks"] == 3
    assert body["completed_tasks"] == 2
    assert body["completion_percentage"] == 66.67


async def test_the_collection_returns_every_list_of_the_actor_with_statistics(
    api_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """LIST-03: every list the caller owns, each carrying its own counters.

    The two lists carry *different* mixes on purpose. Equal counters would pass
    against a grouped query that computed one list's statistics and repeated
    them, which is the failure mode a single-list fixture cannot see.
    """
    await seed(
        session_factory,
        users=[a_user()],
        task_lists=[
            a_task_list(),
            a_task_list(
                task_list_id=OTHER_LIST_ID,
                name="Chores",
                created_at=NOW.replace(year=2026, month=4),
            ),
        ],
        tasks=[
            a_task(task_id=TASK_ID, status=TaskStatus.COMPLETED),
            a_task(task_id=SECOND_TASK_ID),
            a_task(task_id=THIRD_TASK_ID, task_list_id=OTHER_LIST_ID),
        ],
    )
    client, _ = api_client

    response = await client.get(TASK_LISTS)

    assert response.status_code == 200
    body = response.json()

    assert [entry["name"] for entry in body] == ["Groceries", "Chores"]
    assert all(list(entry) == TASK_LIST_MEMBERS for entry in body)
    assert (body[0]["total_tasks"], body[0]["completed_tasks"]) == (2, 1)
    assert body[0]["completion_percentage"] == 50.0
    assert (body[1]["total_tasks"], body[1]["completed_tasks"]) == (1, 0)
    assert body[1]["completion_percentage"] == 0.0


async def test_the_collection_is_ordered_by_created_at_then_id(
    api_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """D-13: a timestamp alone is not a total order, so the id decides ties.

    Both lists are stamped with the same instant and seeded in the *reverse* of
    the expected answer, so a query that ordered by `created_at` alone would
    return them in insertion order and fail here rather than flake later.
    """
    await seed(
        session_factory,
        users=[a_user()],
        task_lists=[
            a_task_list(task_list_id=OTHER_LIST_ID, name="Chores"),
            a_task_list(task_list_id=LIST_ID, name="Groceries"),
        ],
    )
    client, _ = api_client

    response = await client.get(TASK_LISTS)

    assert response.status_code == 200
    body = response.json()

    # Asserted rather than assumed: if the two instants ever drifted apart the
    # ordering below would be decided by the timestamp, and the id tie-break
    # this test exists for would go unexercised while the test still passed.
    assert len({entry["created_at"] for entry in body}) == 1
    assert [entry["id"] for entry in body] == [str(LIST_ID), str(OTHER_LIST_ID)]


async def test_the_collection_never_contains_another_actors_list(
    api_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """D-04 on the collection: ownership filters, it does not merely authorise."""
    await seed(
        session_factory,
        users=[a_user(), a_user(user_id=OTHER_USER_ID, email=OTHER_EMAIL)],
        task_lists=[
            a_task_list(),
            a_task_list(
                task_list_id=FOREIGN_LIST_ID,
                owner_id=OTHER_USER_ID,
                name="Someone else's list",
            ),
        ],
    )
    client, _ = api_client

    response = await client.get(TASK_LISTS)

    assert response.status_code == 200
    body = response.json()

    assert [entry["id"] for entry in body] == [str(LIST_ID)]
    assert str(FOREIGN_LIST_ID) not in response.text


async def test_patch_with_a_name_only_leaves_the_description_alone(
    api_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """D-05's omitted leg: an absent field is not a cleared field."""
    await seed(session_factory, users=[a_user()], task_lists=[a_task_list()])
    client, _ = api_client
    before = (await client.get(f"{TASK_LISTS}/{LIST_ID}")).json()

    response = await client.patch(f"{TASK_LISTS}/{LIST_ID}", json={"name": "Weekly"})

    assert response.status_code == 200
    assert response.json()["name"] == "Weekly"

    after = (await client.get(f"{TASK_LISTS}/{LIST_ID}")).json()

    assert after["name"] == "Weekly"
    assert after["description"] == before["description"]
    assert after["created_at"] == before["created_at"]
    assert moment(after["updated_at"]) > moment(before["updated_at"])


async def test_patch_with_a_description_only_leaves_the_name_alone(
    api_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """The mirror leg, which a single-field test would leave unproved."""
    await seed(session_factory, users=[a_user()], task_lists=[a_task_list()])
    client, _ = api_client
    before = (await client.get(f"{TASK_LISTS}/{LIST_ID}")).json()

    response = await client.patch(
        f"{TASK_LISTS}/{LIST_ID}", json={"description": "Only the essentials"}
    )

    assert response.status_code == 200
    assert response.json()["description"] == "Only the essentials"

    after = (await client.get(f"{TASK_LISTS}/{LIST_ID}")).json()

    assert after["description"] == "Only the essentials"
    assert after["name"] == before["name"]
    assert after["created_at"] == before["created_at"]
    assert moment(after["updated_at"]) > moment(before["updated_at"])


async def test_patch_with_an_explicit_null_description_clears_the_field(
    api_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """D-05's null leg: the one field that has a null to be cleared to.

    This is the test that distinguishes merge-patch semantics from "ignore the
    nulls": an implementation reading the value instead of `model_fields_set`
    would leave the description standing and still answer 200.
    """
    await seed(session_factory, users=[a_user()], task_lists=[a_task_list()])
    client, _ = api_client
    before = (await client.get(f"{TASK_LISTS}/{LIST_ID}")).json()

    response = await client.patch(f"{TASK_LISTS}/{LIST_ID}", json={"description": None})

    assert response.status_code == 200
    assert response.json()["description"] is None

    after = (await client.get(f"{TASK_LISTS}/{LIST_ID}")).json()

    assert after["description"] is None
    assert after["name"] == before["name"]
    assert moment(after["updated_at"]) > moment(before["updated_at"])


async def test_delete_returns_204_with_an_empty_body(
    api_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """LIST-05: no content, and no header describing content that is not there.

    The absent `content-type` is the measured difference `response_class=Response`
    makes on this stack. Without it a 204 returning `None` still advertises
    `application/json` over an empty body, which is a small lie a client's
    parser is entitled to trip over.
    """
    await seed(session_factory, users=[a_user()], task_lists=[a_task_list()])
    client, _ = api_client

    response = await client.delete(f"{TASK_LISTS}/{LIST_ID}")

    assert response.status_code == 204
    assert response.content == b""
    assert "content-type" not in response.headers

    gone = await client.get(f"{TASK_LISTS}/{LIST_ID}")

    assert gone.status_code == 404
    assert gone.json()["code"] == "task_list_not_found"


async def test_deleting_a_list_removes_its_tasks(
    api_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
    session: AsyncSession,
) -> None:
    """D-12's cascade, asserted twice: through the API, and against the rows.

    The API half proves what a client sees; it cannot prove the tasks are gone,
    because a 404 on the collection is equally the answer for a list that was
    deleted while its tasks were orphaned. The repository read on the shared
    session is the half that looks at the table, and the two ids it asks for
    were created through the API rather than seeded, so the cascade is being
    tested against rows the application itself wrote.
    """
    await seed(session_factory, users=[a_user()])
    client, _ = api_client

    created = await client.post(TASK_LISTS, json={"name": "Groceries"})
    list_id = created.json()["id"]
    first = await client.post(f"{TASK_LISTS}/{list_id}/tasks", json={"title": "Milk"})
    second = await client.post(f"{TASK_LISTS}/{list_id}/tasks", json={"title": "Eggs"})
    assert [first.status_code, second.status_code] == [201, 201]

    deleted = await client.delete(f"{TASK_LISTS}/{list_id}")

    assert deleted.status_code == 204

    orphans = await client.get(f"{TASK_LISTS}/{list_id}/tasks")

    assert orphans.status_code == 404
    assert orphans.json()["code"] == "task_list_not_found"

    tasks = SqlAlchemyTaskRepository(session)
    assert await tasks.get(uuid.UUID(first.json()["id"])) is None
    assert await tasks.get(uuid.UUID(second.json()["id"])) is None


def anonymised(response: Response, *identifiers: uuid.UUID) -> str:
    """The serialised body with every named identifier replaced by one token.

    This is what makes "a list you do not own answers exactly like an absent
    one" a test rather than a claim (D-04, T-4-51, T-4-52). The two bodies being
    compared necessarily *mention* two different identifiers - in `detail`, in
    `errors` and in `instance`, which is the request path - so comparing them
    raw proves nothing and comparing only their status codes proves almost
    nothing: a difference in `code`, in `title` or in the presence of an
    `errors` member would sail straight through.

    Replacing each response's own identifier with a fixed token leaves exactly
    the part that should be identical, `instance` included. That is strictly
    stronger than "identical apart from `instance`": the paths are compared too,
    modulo the id they each carry.
    """
    text = response.text
    for identifier in identifiers:
        text = text.replace(str(identifier), "<identifier>")
    return text


def assert_not_found(response: Response, task_list_id: uuid.UUID) -> None:
    """The one shape every task-list 404 in this module has to have."""
    assert response.status_code == 404
    assert response.headers["content-type"] == PROBLEM_JSON

    body = response.json()

    assert list(body) == [*MEMBERS, "errors"]
    assert body["code"] == "task_list_not_found"
    assert body["title"] == "Task list not found"
    assert body["errors"] == {"task_list_id": str(task_list_id)}


async def test_get_a_list_the_actor_does_not_own_is_404_exactly_like_an_absent_one(
    api_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """D-04 on GET: a stranger learns nothing, not even that the list exists."""
    await seed(
        session_factory,
        users=[a_user(), a_user(user_id=OTHER_USER_ID, email=OTHER_EMAIL)],
        task_lists=[a_task_list()],
    )
    client, app = api_client

    with acting_as(app, OTHER_USER_ID):
        not_owned = await client.get(f"{TASK_LISTS}/{LIST_ID}")
        absent = await client.get(f"{TASK_LISTS}/{MISSING_LIST_ID}")

    assert_not_found(not_owned, LIST_ID)
    assert_not_found(absent, MISSING_LIST_ID)
    assert anonymised(not_owned, LIST_ID) == anonymised(absent, MISSING_LIST_ID)


async def test_patch_a_list_the_actor_does_not_own_is_404_exactly_like_an_absent_one(
    api_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """D-04 on PATCH, and the write is refused before it is attempted."""
    await seed(
        session_factory,
        users=[a_user(), a_user(user_id=OTHER_USER_ID, email=OTHER_EMAIL)],
        task_lists=[a_task_list()],
    )
    client, app = api_client
    payload = {"name": "Hijacked"}

    with acting_as(app, OTHER_USER_ID):
        not_owned = await client.patch(f"{TASK_LISTS}/{LIST_ID}", json=payload)
        absent = await client.patch(f"{TASK_LISTS}/{MISSING_LIST_ID}", json=payload)

    assert_not_found(not_owned, LIST_ID)
    assert_not_found(absent, MISSING_LIST_ID)
    assert anonymised(not_owned, LIST_ID) == anonymised(absent, MISSING_LIST_ID)

    # The owner's list is untouched: a refused PATCH must not be a half-applied
    # one, and only a read as the owner can say so.
    survivor = await client.get(f"{TASK_LISTS}/{LIST_ID}")

    assert survivor.json()["name"] == "Groceries"


async def test_delete_a_list_the_actor_does_not_own_is_404_exactly_like_an_absent_one(
    api_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """D-04 on DELETE, the verb where a 204 would be the loudest possible leak."""
    await seed(
        session_factory,
        users=[a_user(), a_user(user_id=OTHER_USER_ID, email=OTHER_EMAIL)],
        task_lists=[a_task_list()],
    )
    client, app = api_client

    with acting_as(app, OTHER_USER_ID):
        not_owned = await client.delete(f"{TASK_LISTS}/{LIST_ID}")
        absent = await client.delete(f"{TASK_LISTS}/{MISSING_LIST_ID}")

    assert_not_found(not_owned, LIST_ID)
    assert_not_found(absent, MISSING_LIST_ID)
    assert anonymised(not_owned, LIST_ID) == anonymised(absent, MISSING_LIST_ID)

    survivor = await client.get(f"{TASK_LISTS}/{LIST_ID}")

    assert survivor.status_code == 200


async def test_get_an_absent_list_is_404(
    api_client: tuple[AsyncClient, FastAPI],
) -> None:
    """The counterpart the three tests above are measured against."""
    client, _ = api_client

    response = await client.get(f"{TASK_LISTS}/{MISSING_LIST_ID}")

    assert_not_found(response, MISSING_LIST_ID)
    assert response.json()["instance"] == f"{TASK_LISTS}/{MISSING_LIST_ID}"


async def test_patch_an_absent_list_is_404(
    api_client: tuple[AsyncClient, FastAPI],
) -> None:
    """A well-formed body against nothing is still a 404, never a 422."""
    client, _ = api_client

    response = await client.patch(
        f"{TASK_LISTS}/{MISSING_LIST_ID}", json={"name": "Anything"}
    )

    assert_not_found(response, MISSING_LIST_ID)

    # D-06 on a refused write: a PATCH that refuses must not have brought the
    # list into existence on its way to refusing it, which an upsert would.
    after = await client.get(f"{TASK_LISTS}/{MISSING_LIST_ID}")

    assert_not_found(after, MISSING_LIST_ID)


async def test_delete_an_absent_list_is_404(
    api_client: tuple[AsyncClient, FastAPI],
) -> None:
    """Delete is not idempotent-by-silence here: nothing deleted is nothing found."""
    client, _ = api_client

    response = await client.delete(f"{TASK_LISTS}/{MISSING_LIST_ID}")

    assert_not_found(response, MISSING_LIST_ID)

    after = await client.get(f"{TASK_LISTS}/{MISSING_LIST_ID}")

    assert_not_found(after, MISSING_LIST_ID)


async def test_creating_a_list_with_a_name_the_actor_already_uses_is_a_duplicate_409(
    api_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """LIST-06 on create: the conflict names the field and the offending name."""
    await seed(session_factory, users=[a_user()], task_lists=[a_task_list()])
    client, _ = api_client
    before = (await client.get(TASK_LISTS)).json()

    response = await client.post(TASK_LISTS, json={"name": "Groceries"})

    assert response.status_code == 409
    assert response.headers["content-type"] == PROBLEM_JSON

    body = response.json()

    assert list(body) == [*MEMBERS, "errors"]
    assert body["code"] == "duplicate_task_list_name"
    assert body["title"] == "Duplicate task list name"
    assert body["errors"] == {"field": "name", "name": "Groceries"}

    # D-06: the collection is what a duplicate would show up in, and a 409
    # reported by a handler that inserted the row anyway is exactly the failure
    # a status-and-body assertion cannot see.
    after = (await client.get(TASK_LISTS)).json()

    assert after == before
    assert len(after) == 1


async def test_renaming_a_list_to_a_name_the_actor_already_uses_is_a_duplicate_409(
    api_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """LIST-06 on rename - the leg a create-only test would miss entirely."""
    await seed(
        session_factory,
        users=[a_user()],
        task_lists=[
            a_task_list(),
            a_task_list(task_list_id=OTHER_LIST_ID, name="Chores"),
        ],
    )
    client, _ = api_client

    response = await client.patch(
        f"{TASK_LISTS}/{OTHER_LIST_ID}", json={"name": "Groceries"}
    )

    assert response.status_code == 409
    assert response.headers["content-type"] == PROBLEM_JSON

    body = response.json()

    assert body["code"] == "duplicate_task_list_name"
    assert body["errors"] == {"field": "name", "name": "Groceries"}

    unchanged = await client.get(f"{TASK_LISTS}/{OTHER_LIST_ID}")

    assert unchanged.json()["name"] == "Chores"


async def test_a_name_another_actor_uses_is_not_a_conflict(
    api_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """Uniqueness is per owner: two people may each have a list called Groceries."""
    await seed(
        session_factory,
        users=[a_user(), a_user(user_id=OTHER_USER_ID, email=OTHER_EMAIL)],
        task_lists=[
            a_task_list(
                task_list_id=FOREIGN_LIST_ID,
                owner_id=OTHER_USER_ID,
                name="Groceries",
            )
        ],
    )
    client, _ = api_client

    response = await client.post(TASK_LISTS, json={"name": "Groceries"})

    assert response.status_code == 201
    assert response.json()["owner_id"] == str(OWNER_ID)

    mine = await client.get(TASK_LISTS)

    assert mine.json() == [response.json()]
    assert str(FOREIGN_LIST_ID) not in mine.text


async def test_a_name_differing_only_in_case_is_not_a_conflict(
    api_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """D-12 over HTTP: the list name folds no case, and the index agrees."""
    await seed(session_factory, users=[a_user()], task_lists=[a_task_list()])
    client, _ = api_client

    response = await client.post(TASK_LISTS, json={"name": "groceries"})

    assert response.status_code == 201
    assert response.json()["name"] == "groceries"

    both = await client.get(TASK_LISTS)

    assert sorted(entry["name"] for entry in both.json()) == ["Groceries", "groceries"]


async def test_renaming_a_list_to_its_own_current_name_succeeds(
    api_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """The guard that stops a row conflicting with itself.

    An unconditional pre-check would refuse this request on the strength of the
    very row it is about to write, which is the one 409 that would be a bug
    rather than a rule.
    """
    await seed(session_factory, users=[a_user()], task_lists=[a_task_list()])
    client, _ = api_client
    before = (await client.get(f"{TASK_LISTS}/{LIST_ID}")).json()

    response = await client.patch(f"{TASK_LISTS}/{LIST_ID}", json={"name": "Groceries"})

    assert response.status_code == 200
    assert response.json()["name"] == "Groceries"

    after = (await client.get(f"{TASK_LISTS}/{LIST_ID}")).json()

    assert after["name"] == "Groceries"
    assert after["description"] == before["description"]
    assert moment(after["updated_at"]) > moment(before["updated_at"])


async def test_renaming_a_list_to_its_own_name_padded_with_whitespace_succeeds(
    api_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """Review fix WR-01, over HTTP and against the real `exists_with_name`.

    `PATCH {"name": " Groceries "}` on the list named `Groceries` used to answer
    409 `duplicate_task_list_name`: the raw string differed from the stored one,
    so the pre-check ran, trimmed its argument, and found the list's own row.
    """
    await seed(session_factory, users=[a_user()], task_lists=[a_task_list()])
    client, _ = api_client
    before = (await client.get(f"{TASK_LISTS}/{LIST_ID}")).json()

    response = await client.patch(
        f"{TASK_LISTS}/{LIST_ID}", json={"name": "  Groceries "}
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Groceries"

    # The stored name is the trimmed one, so the padding never reached the row.
    after = (await client.get(f"{TASK_LISTS}/{LIST_ID}")).json()

    assert after["name"] == "Groceries"
    assert after["description"] == before["description"]


async def test_a_duplicate_409_reports_the_trimmed_name_on_both_verbs(
    api_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """One error, one spelling: `detail` and `errors.name` carry the stored form."""
    await seed(
        session_factory,
        users=[a_user()],
        task_lists=[
            a_task_list(),
            a_task_list(task_list_id=OTHER_LIST_ID, name="Chores"),
        ],
    )
    client, _ = api_client
    before = (await client.get(TASK_LISTS)).json()

    created = await client.post(TASK_LISTS, json={"name": " Groceries  "})
    renamed = await client.patch(
        f"{TASK_LISTS}/{OTHER_LIST_ID}", json={"name": " Groceries  "}
    )

    for response in (created, renamed):
        assert response.status_code == 409
        body = response.json()
        assert body["errors"] == {"field": "name", "name": "Groceries"}
        assert "'Groceries'" in body["detail"]

    # Both refusals left the two lists exactly as they were: neither a third row
    # nor a renamed second one.
    after = (await client.get(TASK_LISTS)).json()

    assert after == before
    assert [entry["name"] for entry in after] == ["Groceries", "Chores"]


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({"name": "a\x00b"}, "name"),
        ({"name": "ok", "description": "x\x00y"}, "description"),
    ],
)
async def test_a_nul_character_in_a_list_field_is_a_domain_validation_error(
    api_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
    body: dict[str, str],
    field: str,
) -> None:
    """Phase 4 review WR-03: `"\\u0000"` is valid JSON and must never be a 500.

    PostgreSQL refuses NUL in a text value, and for `name` it used to do so from
    inside the duplicate-name SELECT, before anything was written. Both verbs
    are driven, because create and PATCH reach the rule by different roads.
    """
    await seed(session_factory, users=[a_user()], task_lists=[a_task_list()])
    client, _ = api_client
    before = (await client.get(TASK_LISTS)).json()

    created = await client.post(TASK_LISTS, json=body)
    patched = await client.patch(f"{TASK_LISTS}/{LIST_ID}", json=body)

    for response in (created, patched):
        assert response.status_code == 422
        assert response.headers["content-type"] == PROBLEM_JSON
        problem = response.json()
        assert problem["code"] == "validation_error"
        assert problem["title"] == "Validation error"
        assert problem["errors"] == {"field": field}

    # The NUL reached PostgreSQL on the `name` road, so "refused" has to mean
    # the row is untouched as well as the answer being a 422.
    after = (await client.get(TASK_LISTS)).json()

    assert after == before
    assert "\x00" not in (await client.get(TASK_LISTS)).text


async def test_an_empty_patch_body_is_a_request_validation_error(
    api_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """D-06: a body that asks for nothing is refused, not treated as a no-op.

    This is the **list** `errors` shape - the request-validation producer - and
    the title is what tells the two apart at a glance (04-RESEARCH Pitfall 5).
    """
    await seed(session_factory, users=[a_user()], task_lists=[a_task_list()])
    client, _ = api_client
    before = (await client.get(f"{TASK_LISTS}/{LIST_ID}")).json()

    response = await client.patch(f"{TASK_LISTS}/{LIST_ID}", json={})

    assert response.status_code == 422
    assert response.headers["content-type"] == PROBLEM_JSON

    body = response.json()

    assert list(body) == [*MEMBERS, "errors"]
    assert body["code"] == "validation_error"
    assert body["title"] == "Request validation failed"
    assert isinstance(body["errors"], list)
    assert len(body["errors"]) == 1
    assert body["errors"][0]["field"] == "body"
    assert body["errors"][0]["type"] == "value_error"

    # D-06: refused, so nothing moved - `updated_at` included. A handler that
    # stamped the row before validating the body would answer this same 422.
    after = (await client.get(f"{TASK_LISTS}/{LIST_ID}")).json()

    assert after == before


async def test_an_unknown_key_in_a_patch_is_a_request_validation_error(
    api_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """D-06: a typo is refused at the named field, never silently ignored.

    This is also the mass-assignment proof (T-4-54): `extra="forbid"` reaching
    the client as `extra_forbidden` at `body.nmae` is the difference between a
    key that was rejected and a key that was quietly dropped.
    """
    await seed(session_factory, users=[a_user()], task_lists=[a_task_list()])
    client, _ = api_client
    before = (await client.get(f"{TASK_LISTS}/{LIST_ID}")).json()

    response = await client.patch(f"{TASK_LISTS}/{LIST_ID}", json={"nmae": "Weekly"})

    assert response.status_code == 422
    assert response.headers["content-type"] == PROBLEM_JSON

    body = response.json()

    assert body["title"] == "Request validation failed"
    assert isinstance(body["errors"], list)
    assert len(body["errors"]) == 1
    assert body["errors"][0]["field"] == "body.nmae"
    assert body["errors"][0]["type"] == "extra_forbidden"

    after = (await client.get(f"{TASK_LISTS}/{LIST_ID}")).json()

    assert after == before
    assert "Weekly" not in (await client.get(f"{TASK_LISTS}/{LIST_ID}")).text


async def test_an_explicit_null_name_is_a_request_validation_error(
    api_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """D-05: `name` has no null to be cleared to, so sending one is a 422."""
    await seed(session_factory, users=[a_user()], task_lists=[a_task_list()])
    client, _ = api_client
    before = (await client.get(f"{TASK_LISTS}/{LIST_ID}")).json()

    response = await client.patch(f"{TASK_LISTS}/{LIST_ID}", json={"name": None})

    assert response.status_code == 422
    assert response.headers["content-type"] == PROBLEM_JSON

    body = response.json()

    assert body["title"] == "Request validation failed"
    assert isinstance(body["errors"], list)
    assert [entry["field"] for entry in body["errors"]] == ["body.name"]

    # The name survives. A schema that accepted the null and let the entity
    # refuse it later would be a different bug with the same status code.
    after = (await client.get(f"{TASK_LISTS}/{LIST_ID}")).json()

    assert after == before
    assert after["name"] == "Groceries"


async def test_a_blank_name_is_a_domain_validation_error(
    api_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """The **object** `errors` shape: a domain rule, not a schema one.

    Pydantic declares no length and no blankness constraint on `name` (Phase 2
    D-04 keeps every business limit in the entity), so this request is
    well-formed all the way to `TaskList.create`, and the refusal comes back
    with the other 422's code and a different title and `errors` shape.
    """
    await seed(session_factory, users=[a_user()])
    client, _ = api_client

    response = await client.post(TASK_LISTS, json={"name": "   "})

    assert response.status_code == 422
    assert response.headers["content-type"] == PROBLEM_JSON

    body = response.json()

    assert list(body) == [*MEMBERS, "errors"]
    assert body["code"] == "validation_error"
    assert body["title"] == "Validation error"
    assert body["errors"] == {"field": "name"}

    # D-06 on a refused create: the collection is where a row that was written
    # anyway would appear, and it is still empty.
    assert (await client.get(TASK_LISTS)).json() == []


async def test_an_over_length_name_is_a_domain_validation_error(
    api_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """The same object shape, from the limit the entity owns.

    The string is built from `TaskList.NAME_MAX_LENGTH` rather than from a
    literal, so raising the entity's limit cannot leave this test asserting a
    refusal that no longer happens.
    """
    await seed(session_factory, users=[a_user()])
    client, _ = api_client

    response = await client.post(
        TASK_LISTS, json={"name": "x" * (TaskList.NAME_MAX_LENGTH + 1)}
    )

    assert response.status_code == 422
    assert response.headers["content-type"] == PROBLEM_JSON

    body = response.json()

    assert body["code"] == "validation_error"
    assert body["title"] == "Validation error"
    assert body["errors"] == {"field": "name"}

    assert (await client.get(TASK_LISTS)).json() == []


async def test_a_malformed_list_id_is_a_request_validation_error(
    api_client: tuple[AsyncClient, FastAPI],
) -> None:
    """A path segment that is not a UUID is refused before any use case runs."""
    client, _ = api_client

    response = await client.get(f"{TASK_LISTS}/not-a-uuid")

    assert response.status_code == 422
    assert response.headers["content-type"] == PROBLEM_JSON

    body = response.json()

    assert body["title"] == "Request validation failed"
    assert [entry["field"] for entry in body["errors"]] == ["path.list_id"]


async def test_a_refusal_never_echoes_the_clients_input(
    api_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """T-4-53, at the HTTP level: what a refusal reveals is attack surface.

    The HTTP counterpart of `test_validation_problem_never_echoes_the_client_input`.
    A marker string goes in as an over-length name and must not come back in any
    member of the body - not in `detail`, which names the field and the limit but
    never the value, and not in `errors`, which is the field name alone.
    """
    marker = "canary-4d09"
    await seed(session_factory, users=[a_user()])
    client, _ = api_client

    over_length = marker * (TaskList.NAME_MAX_LENGTH // len(marker) + 1)
    response = await client.post(TASK_LISTS, json={"name": over_length})

    assert response.status_code == 422
    assert len(over_length) > TaskList.NAME_MAX_LENGTH
    assert marker not in response.text
    assert "input" not in response.text
    assert "ctx" not in response.text

    # The marker must not be readable back out of the collection either: a
    # refusal that leaked nothing into its own body and everything into the
    # database would satisfy every assertion above.
    nothing = await client.get(TASK_LISTS)

    assert nothing.json() == []
    assert marker not in nothing.text
