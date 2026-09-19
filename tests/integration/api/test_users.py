"""The user directory over HTTP: three members, in the database's own order.

This module uses `authenticated_client` rather than `api_client`, for the
reason `test_auth.py`'s docstring gives in full: the anonymous leg below does
not exist through a harness that overrides the actor. The two standards
`test_task_lists.py` sets out apply unchanged - assert the body, never the
status alone.

**The ordering test is the third of three, and the three are deliberate.**
`GET /api/v1/users` promises `(created_at, id)`, a total order, and that one
promise is now pinned at three levels that can each fail independently:

- `tests/unit/application/test_list_users.py`, in
  `test_list_users_orders_by_created_at_then_id`, pins it against the in-memory
  fake, which is where a use case that re-sorted its own results would be
  caught;
- `tests/integration/test_repositories_users.py`, in
  `test_list_all_breaks_a_tie_on_created_at_with_the_id`, pins it against real
  PostgreSQL through the adapter, which is where a missing second `ORDER BY`
  term would be caught;
- and the test below pins it through the whole stack, which is the only level
  at which a router or a serialiser that rearranged the collection on its way
  out would be caught.

None of the three is redundant, because each has a layer above it that could
undo what it proved. Saying so here is cheaper than a reader discovering the
other two and deleting one of them as a duplicate.

**Every member assertion is a list in declaration order.** ASGN-03 asks for
"id, name, email" and `UserSummaryResponse` publishes exactly those three in
that sequence, so the order is contract and not presentation. A per-key check
that the stored hash is absent would pass against a hash field that had merely
been renamed (T-5-08); the list would not.
"""

import uuid
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from taskmanager.domain.entities.user import User

# Imported rather than re-declared - the convention `test_task_lists.py`
# states: the error contract has one home.
from tests.api.test_error_contract import MEMBERS, PROBLEM_JSON
from tests.integration.api.test_task_lists import SessionFactory
from tests.integration.conftest import OWNER_ID, bearer_header, seed

pytestmark = pytest.mark.integration

USERS = "/api/v1/users"

# ASGN-03's three members, in `UserSummaryResponse`'s declaration order, which
# is its serialisation order. The two members this list does not have are the
# stored hash - which has no field to travel in anywhere - and `created_at`,
# which the profile publishes and the directory was never asked for.
USER_MEMBERS = ["id", "full_name", "email"]

# The readable identifier series continues rather than restarting: Phase 4 used
# ...0001 for the caller and ...0002 for the second user, so Phase 5's two new
# people take the next two slots and no Phase 4 number is reused.
ASSIGNEE_ID = uuid.UUID("00000000-0000-4000-8000-000000000003")
STRANGER_ID = uuid.UUID("00000000-0000-4000-8000-000000000004")

# Two instants, because one would make every row tie and the ordering test
# would only ever exercise the tie-break.
EARLIER = datetime(2026, 3, 14, 15, 9, 26, 535897, tzinfo=UTC)
LATER = datetime(2026, 5, 1, 8, 0, 0, tzinfo=UTC)

CALLER_EMAIL = "caller@example.com"
ASSIGNEE_EMAIL = "assignee@example.com"
STRANGER_EMAIL = "stranger@example.com"

CALLER_FULL_NAME = "The Caller"
ASSIGNEE_FULL_NAME = "An Assignee"
STRANGER_FULL_NAME = "A Stranger"

PASSWORD_HASH = "argon2-placeholder-hash-value"


def a_user(
    *,
    user_id: uuid.UUID,
    email: str,
    full_name: str,
    created_at: datetime = EARLIER,
) -> User:
    """A valid user entity, with the creation instant as a knob.

    Local rather than `test_task_lists.py`'s builder, which takes no
    `created_at`: over there every user is a foreign key that has to exist and
    nothing reads its timestamp, while here the timestamp *is* the property
    under test. Widening the sibling's signature for one caller would put a
    parameter in ~120 tests that none of them uses.
    """
    return User.create(
        user_id=user_id,
        email=email,
        full_name=full_name,
        password_hash=PASSWORD_HASH,
        now=created_at,
    )


def the_caller(*, created_at: datetime = EARLIER) -> User:
    """The row behind the token, which every request here needs to exist.

    The price `authenticated_client` charges: the real dependency confirms the
    subject's row on every request (D-11), so a directory test that forgot to
    seed its own caller would fail with a 401 rather than with an empty array.
    """
    return a_user(
        user_id=OWNER_ID,
        email=CALLER_EMAIL,
        full_name=CALLER_FULL_NAME,
        created_at=created_at,
    )


async def test_the_directory_answers_a_bare_array_to_an_authenticated_caller(
    authenticated_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """ASGN-03: 200 and a JSON array, not an envelope around one.

    The collection is published bare, exactly as `GET /task-lists` is and
    unlike `GET /task-lists/{id}/tasks`, which carries the completion counters
    it was asked for. A client reading this route needs no unwrapping.
    """
    await seed(session_factory, users=[the_caller()])
    client, app = authenticated_client

    response = await client.get(
        USERS, headers={"Authorization": await bearer_header(app, OWNER_ID)}
    )

    assert response.status_code == 200

    body = response.json()

    assert isinstance(body, list)
    assert len(body) == 1
    assert body[0]["id"] == str(OWNER_ID)
    assert body[0]["email"] == CALLER_EMAIL


async def test_every_entry_publishes_exactly_the_three_members_in_declaration_order(
    authenticated_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """ASGN-03's shape, asserted as a list so a rename cannot pass it (T-5-08)."""
    await seed(
        session_factory,
        users=[
            the_caller(),
            a_user(
                user_id=ASSIGNEE_ID,
                email=ASSIGNEE_EMAIL,
                full_name=ASSIGNEE_FULL_NAME,
            ),
        ],
    )
    client, app = authenticated_client

    response = await client.get(
        USERS, headers={"Authorization": await bearer_header(app, OWNER_ID)}
    )

    assert response.status_code == 200

    body = response.json()

    assert len(body) == 2
    assert [list(entry) for entry in body] == [USER_MEMBERS, USER_MEMBERS]


async def test_neither_the_stored_hash_nor_the_creation_instant_reaches_the_wire(
    authenticated_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """The same claim as the test above, made over the whole document.

    Not a duplicate of the member-list assertion, and not a weaker restatement
    of it either: this searches the *serialised response*, so a hash arriving
    anywhere a per-entry key check cannot see - inside a nested object, in an
    envelope, in a member added above the array - fails here. The member list
    is what catches a rename; this is what catches a leak that is not a member
    of an entry at all.
    """
    await seed(session_factory, users=[the_caller()])
    client, app = authenticated_client

    response = await client.get(
        USERS, headers={"Authorization": await bearer_header(app, OWNER_ID)}
    )

    assert response.status_code == 200
    assert "password_hash" not in response.text
    assert PASSWORD_HASH not in response.text
    assert "created_at" not in response.text


async def test_the_directory_is_returned_in_created_at_then_id_order(
    authenticated_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """The total order, measured against real PostgreSQL through the full stack.

    The three rows are arranged so that no cheaper rule produces the expected
    answer, which is the only arrangement worth writing:

    - they are **seeded** as caller, stranger, assignee, so insertion order is
      wrong;
    - the caller has the *lowest* identifier and the *latest* instant, so an
      order by id alone is wrong;
    - the assignee and the stranger share one instant, so an order by
      `created_at` alone is not an order at all - which row came first would be
      whatever the database felt like, and that is the flakiness a second term
      exists to remove.

    The expected sequence is therefore assignee, stranger, caller: the tied
    pair first in identifier order, and the later row last.
    """
    await seed(
        session_factory,
        users=[
            the_caller(created_at=LATER),
            a_user(
                user_id=STRANGER_ID,
                email=STRANGER_EMAIL,
                full_name=STRANGER_FULL_NAME,
                created_at=EARLIER,
            ),
            a_user(
                user_id=ASSIGNEE_ID,
                email=ASSIGNEE_EMAIL,
                full_name=ASSIGNEE_FULL_NAME,
                created_at=EARLIER,
            ),
        ],
    )
    client, app = authenticated_client

    response = await client.get(
        USERS, headers={"Authorization": await bearer_header(app, OWNER_ID)}
    )

    assert response.status_code == 200
    assert [entry["id"] for entry in response.json()] == [
        str(ASSIGNEE_ID),
        str(STRANGER_ID),
        str(OWNER_ID),
    ]


async def test_the_caller_sees_accounts_other_than_their_own(
    authenticated_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """D-13: a directory, not a self-view - and that is the accepted trade.

    An implementation that quietly narrowed this collection to the caller would
    answer 200 with a perfectly well-shaped array and would break the only
    route from which an `assignee_id` can be learnt, which is the whole reason
    ASGN-03 asks for the route. So the assertion is that the *other* two
    addresses are there, not merely that the array has three entries.
    """
    await seed(
        session_factory,
        users=[
            the_caller(),
            a_user(
                user_id=ASSIGNEE_ID,
                email=ASSIGNEE_EMAIL,
                full_name=ASSIGNEE_FULL_NAME,
            ),
            a_user(
                user_id=STRANGER_ID,
                email=STRANGER_EMAIL,
                full_name=STRANGER_FULL_NAME,
            ),
        ],
    )
    client, app = authenticated_client

    response = await client.get(
        USERS, headers={"Authorization": await bearer_header(app, OWNER_ID)}
    )

    assert response.status_code == 200
    assert {entry["email"] for entry in response.json()} == {
        CALLER_EMAIL,
        ASSIGNEE_EMAIL,
        STRANGER_EMAIL,
    }


async def test_an_anonymous_caller_is_refused_with_the_shared_401(
    authenticated_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """AUTH-03 on this route: no token, no directory - and no hint of one.

    The rows are seeded first on purpose. A refusal against an empty database
    would be true of an implementation that only refused because there was
    nothing to answer with; refusing while three readable accounts exist is the
    claim worth making.
    """
    await seed(
        session_factory,
        users=[
            the_caller(),
            a_user(
                user_id=ASSIGNEE_ID,
                email=ASSIGNEE_EMAIL,
                full_name=ASSIGNEE_FULL_NAME,
            ),
        ],
    )
    client, _ = authenticated_client

    response = await client.get(USERS)

    assert response.status_code == 401
    assert response.headers["content-type"] == PROBLEM_JSON
    assert response.headers["WWW-Authenticate"] == "Bearer"

    body = response.json()

    assert list(body) == MEMBERS
    assert body["code"] == "authentication_failed"
    assert body["instance"] == USERS
    # Nothing about the collection it declined to publish.
    assert ASSIGNEE_EMAIL not in response.text
    assert CALLER_EMAIL not in response.text
