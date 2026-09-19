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
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from taskmanager.domain.entities.user import User
from taskmanager.presentation.api.actor import DEMO_USER_ID
from tests.integration.conftest import seed

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

NOW = datetime(2026, 3, 14, 15, 9, 26, 535897, tzinfo=UTC)

PASSWORD_HASH = "argon2-placeholder-hash-value"
DEMO_EMAIL = "demo@example.test"
OTHER_EMAIL = "other@example.test"

TASK_LISTS = "/api/v1/task-lists"


def a_user(
    *,
    user_id: uuid.UUID = DEMO_USER_ID,
    email: str = DEMO_EMAIL,
) -> User:
    """A valid user entity, differing from the demo actor only where asked.

    `task_lists.owner_id` is a foreign key, so every test that creates a list
    needs the row behind the actor the seam hands out. Tests never rely on the
    container's demo seed (D-02): the `test` stage carries no entrypoint, and a
    suite that depended on one would pass or fail according to how the database
    was started.
    """
    return User.create(
        user_id=user_id,
        email=email,
        password_hash=PASSWORD_HASH,
        now=NOW,
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
