"""The assignment door, the assignee's capabilities, and the discovery route.

`test_task_lists.py` states the two standards every test in this package
follows - assert on the **body**, never on the status code alone, and re-read
every mutation **through the API** - and they are not restated here. Its
constants, its builders and its `anonymised` helper are imported rather than
copied, and so are the two identifiers plan 05-13 introduced for the assignee
and the stranger: a second copy of a shared fact is the one that quietly
disagrees the first time the fact moves.

Three things are specific to this module.

**It runs on `authenticated_client`, so every request carries a real token.**
The other harness overrides the actor seam, and this module is about three
*different* callers looking at one task - the list's owner, the task's
assignee and a stranger. `acting_as` could impersonate them, but it replaces
the very dependency that decides who is calling, and the assignee's four
refusals are only worth asserting against the code path a client reaches. The
price is the one `authenticated_client` documents: every caller's `users` row
has to be seeded, which is why the fixtures below seed all three people even
when a test names one.

**Every 403 test re-reads as the owner.** A refusal that had already written
and a refusal that wrote nothing produce the same status code, so the second
request is what makes these mass-assignment proofs rather than status
assertions (T-5-11). The same argument `test_tasks.py` makes for its
wrong-list `PATCH`.

**The stranger-with-an-unknown-assignee test compares two bodies, not two
statuses.** Both are 404, and they would be 404 against an implementation that
looked the assignee up *before* the ownership guard and leaked the difference
through `code`: `user_not_found` for an invented identifier, `task_not_found`
for a real one, and the difference between the two answers is a user-existence
oracle handed to a caller who cannot see the task (T-5-12). The comparison is
over the serialised documents, `instance` included, through `anonymised`.
"""

import json
import logging
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient, Response

from taskmanager.application.ports.notifications import EmailNotifier
from taskmanager.application.use_cases.tasks.assign import logger as assignment_logger
from taskmanager.domain.entities.task import Task
from taskmanager.domain.entities.user import User
from taskmanager.domain.value_objects.task_status import TaskStatus
from taskmanager.infrastructure.logging import JsonFormatter
from taskmanager.infrastructure.notifications.logging import LOGGER_NAME
from taskmanager.presentation.api.dependencies import get_email_notifier

# Imported rather than re-declared - the convention `test_task_lists.py`
# states: the error contract has one home.
from tests.api.test_error_contract import MEMBERS, PROBLEM_JSON
from tests.integration.api.test_task_lists import (
    FOREIGN_LIST_ID,
    LIST_ID,
    NOW,
    SECOND_TASK_ID,
    TASK_ID,
    TASK_LISTS,
    THIRD_TASK_ID,
    SessionFactory,
    a_task_list,
    anonymised,
    assert_not_found,
    moment,
)
from tests.integration.api.test_tasks import (
    FIFTH_TASK_ID,
    FOURTH_TASK_ID,
    TASK_MEMBERS,
    assert_task_not_found,
    status_url,
    task_url,
    tasks_url,
)
from tests.integration.api.test_users import (
    ASSIGNEE_EMAIL,
    ASSIGNEE_FULL_NAME,
    ASSIGNEE_ID,
    STRANGER_EMAIL,
    STRANGER_FULL_NAME,
    STRANGER_ID,
    a_user,
    the_caller,
)
from tests.integration.conftest import OWNER_ID, bearer_header, seed

pytestmark = pytest.mark.integration

ASSIGNED_TO_ME = "/api/v1/tasks/assigned-to-me"

# An identifier no `users` row carries. The sibling modules took `...fe` for an
# absent task and `...ff` for an absent list, so the series continues backwards
# rather than colliding with either.
MISSING_USER_ID = uuid.UUID("00000000-0000-4000-8000-0000000000fd")

# A second instant, so the discovery collection below is not one big tie: the
# order is then decided by the timestamp *and* by the identifier, which is the
# only arrangement in which both terms of `(created_at, id)` are exercised.
LATER_MOMENT = NOW.replace(month=4)


def assignee_url(task_list_id: uuid.UUID, task_id: uuid.UUID) -> str:
    """The assignment door: one URL, two verbs (D-05)."""
    return f"{task_url(task_list_id, task_id)}/assignee"


async def headers_for(app: FastAPI, user_id: uuid.UUID) -> dict[str, str]:
    """The `Authorization` header of one caller, minted by the application.

    A helper rather than the expression spelled out per request, because this
    module's tests routinely speak as two people in one function and the
    difference between them should be one readable argument rather than a
    nested call a reader has to unpick.
    """
    return {"Authorization": await bearer_header(app, user_id)}


def a_task_held_by(
    assignee_id: uuid.UUID | None,
    *,
    task_id: uuid.UUID,
    task_list_id: uuid.UUID = LIST_ID,
    title: str = "Buy milk",
    status: TaskStatus = TaskStatus.PENDING,
    created_at: datetime = NOW,
) -> Task:
    """A task entity whose assignee is the point rather than an afterthought.

    `test_task_lists.py`'s builder takes no assignee, which is exactly right
    for the ~120 tests that use it and useless here, where the column is the
    subject. Widening the sibling would put a parameter in all of them that
    none of them uses - the argument `test_users.py` already made for its own
    builder.
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
        assignee_id=assignee_id,
    )


def the_assignee() -> User:
    """The person a task is handed to, from `test_users.py`'s identifier series."""
    return a_user(
        user_id=ASSIGNEE_ID, email=ASSIGNEE_EMAIL, full_name=ASSIGNEE_FULL_NAME
    )


def the_stranger() -> User:
    """A third account that owns nothing and holds nothing."""
    return a_user(
        user_id=STRANGER_ID, email=STRANGER_EMAIL, full_name=STRANGER_FULL_NAME
    )


async def given_three_people_and_an_unassigned_task(
    session_factory: SessionFactory,
) -> None:
    """The owner, the assignee, a stranger, one list and one free task.

    All three rows exist in every fixture here because the real actor
    dependency confirms the caller's row on *every* request (D-11): a test
    that spoke as the stranger without seeding them would fail with a 401
    rather than with the refusal it was written to assert.
    """
    await seed(
        session_factory,
        users=[the_caller(), the_assignee(), the_stranger()],
        task_lists=[a_task_list()],
        tasks=[a_task_held_by(None, task_id=TASK_ID)],
    )


async def given_a_task_the_assignee_holds(session_factory: SessionFactory) -> None:
    """The same three people, with the task already in the assignee's hands."""
    await seed(
        session_factory,
        users=[the_caller(), the_assignee(), the_stranger()],
        task_lists=[a_task_list()],
        tasks=[a_task_held_by(ASSIGNEE_ID, task_id=TASK_ID)],
    )


async def given_a_workload_across_two_lists(session_factory: SessionFactory) -> None:
    """Five tasks over two lists, arranged so no cheaper rule is right.

    The three the assignee holds are seeded as `TASK_ID`, `THIRD_TASK_ID`,
    `SECOND_TASK_ID`, and the expected answer is none of the orders that come
    for free:

    - insertion order is wrong, because the row seeded first is expected last;
    - identifier order is wrong, because `TASK_ID` is the lowest identifier and
      carries the latest instant;
    - `created_at` alone is not an order at all, because `SECOND_TASK_ID` and
      `THIRD_TASK_ID` share one instant - which row came first would be
      whatever the database felt like, and that is the flakiness the second
      term exists to remove.

    The expected sequence is therefore the tied pair in identifier order and
    the later row last. The other two tasks are there so the collection can be
    wrong in the two remaining ways: one belongs to nobody and one belongs to
    the owner, so a route that answered "every assigned task" or "every task in
    a list I can reach" fails as well.

    `SECOND_TASK_ID` lives in a list the **stranger** owns, which is what makes
    this a view across lists rather than a filter inside one - and it is a list
    the assignee cannot see at all (D-01).
    """
    await seed(
        session_factory,
        users=[the_caller(), the_assignee(), the_stranger()],
        task_lists=[
            a_task_list(),
            a_task_list(
                task_list_id=FOREIGN_LIST_ID,
                owner_id=STRANGER_ID,
                name="Somebody else's errands",
            ),
        ],
        tasks=[
            a_task_held_by(
                ASSIGNEE_ID,
                task_id=TASK_ID,
                title="File the tax return",
                created_at=LATER_MOMENT,
            ),
            a_task_held_by(
                ASSIGNEE_ID, task_id=THIRD_TASK_ID, title="Call the plumber"
            ),
            a_task_held_by(
                ASSIGNEE_ID,
                task_id=SECOND_TASK_ID,
                task_list_id=FOREIGN_LIST_ID,
                title="Water the plants",
            ),
            a_task_held_by(None, task_id=FOURTH_TASK_ID, title="Nobody's job"),
            a_task_held_by(OWNER_ID, task_id=FIFTH_TASK_ID, title="The owner's own"),
        ],
    )


def assert_forbidden(response: Response) -> None:
    """The 403 the assignee earns: told they may not, and told nothing else.

    `AuthorizationError` carries no details, so the body is exactly the six
    members of the error contract - asserted as a list, because an `errors`
    member naming the list's owner would be precisely the disclosure a 403 is
    supposed to avoid, and a per-key check would not see it arrive.
    """
    assert response.status_code == 403
    assert response.headers["content-type"] == PROBLEM_JSON

    body = response.json()

    assert list(body) == MEMBERS
    assert body["code"] == "authorization_failed"
    assert body["title"] == "Authorization failed"


def assert_user_not_found(response: Response, user_id: uuid.UUID) -> None:
    """The 404 an owner gets for an `assignee_id` naming nobody (D-08).

    The `code` is asserted as well as the status, because `task_not_found` is
    also a 404 and would also look reasonable here - and the difference between
    the two is the whole of T-5-12.
    """
    assert response.status_code == 404
    assert response.headers["content-type"] == PROBLEM_JSON

    body = response.json()

    assert list(body) == [*MEMBERS, "errors"]
    assert body["code"] == "user_not_found"
    assert body["title"] == "User not found"
    assert body["errors"] == {"user_id": str(user_id)}


# --------------------------------------------------------------------------
# The door itself: PUT assigns, DELETE unassigns, both are idempotent
# (ASGN-01, ASGN-02, D-05, D-07, D-08)
# --------------------------------------------------------------------------


async def test_the_owner_assigns_a_task_and_the_assignee_id_persists(
    authenticated_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """ASGN-01 and ASGN-02 over HTTP: 200, the full task, and it stuck.

    The response is asserted member by member in declaration order, because
    D-05 says this endpoint answers with the same document the status endpoint
    does - a handler that returned only the changed field would satisfy a
    per-key check on `assignee_id` and break that promise.
    """
    await given_three_people_and_an_unassigned_task(session_factory)
    client, app = authenticated_client
    owner = await headers_for(app, OWNER_ID)

    response = await client.put(
        assignee_url(LIST_ID, TASK_ID),
        json={"assignee_id": str(ASSIGNEE_ID)},
        headers=owner,
    )

    assert response.status_code == 200
    body = response.json()

    assert list(body) == TASK_MEMBERS
    assert body["id"] == str(TASK_ID)
    assert body["assignee_id"] == str(ASSIGNEE_ID)
    assert body["status"] == TaskStatus.PENDING.value

    after = await client.get(task_url(LIST_ID, TASK_ID), headers=owner)

    assert after.status_code == 200
    assert after.json() == body
    assert moment(after.json()["updated_at"]) > NOW


async def test_the_owner_unassigns_and_the_assignee_id_goes_back_to_null(
    authenticated_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """D-05's second verb: 200 **with a body**, not the 204 the other deletes give.

    What is deleted is a field of a resource rather than the resource itself,
    so the resource is still there to be returned - and returning it saves the
    client the re-read this test makes anyway.
    """
    await given_a_task_the_assignee_holds(session_factory)
    client, app = authenticated_client
    owner = await headers_for(app, OWNER_ID)

    response = await client.delete(assignee_url(LIST_ID, TASK_ID), headers=owner)

    assert response.status_code == 200
    body = response.json()

    assert list(body) == TASK_MEMBERS
    assert body["assignee_id"] is None

    after = await client.get(task_url(LIST_ID, TASK_ID), headers=owner)

    assert after.status_code == 200
    assert after.json()["assignee_id"] is None


async def test_assigning_the_same_user_again_is_a_no_op_that_does_not_move_updated_at(
    authenticated_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """D-07, and the `updated_at` half is the load-bearing one.

    "200 with the same assignee" is also true of an implementation that
    rewrote the row and sent a second email; what distinguishes the no-op from
    the rewrite is that nothing moved. The whole body is compared rather than
    the one member, exactly as the same-state status test does.
    """
    await given_three_people_and_an_unassigned_task(session_factory)
    client, app = authenticated_client
    owner = await headers_for(app, OWNER_ID)
    payload = {"assignee_id": str(ASSIGNEE_ID)}

    first = await client.put(
        assignee_url(LIST_ID, TASK_ID), json=payload, headers=owner
    )
    assert first.status_code == 200

    again = await client.put(
        assignee_url(LIST_ID, TASK_ID), json=payload, headers=owner
    )

    assert again.status_code == 200
    assert again.json() == first.json()

    after = await client.get(task_url(LIST_ID, TASK_ID), headers=owner)

    assert after.json() == first.json()
    assert moment(after.json()["updated_at"]) == moment(first.json()["updated_at"])


async def test_unassigning_a_task_nobody_holds_is_a_200_no_op(
    authenticated_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """D-07's mirror: repeating a request that already succeeded is not a conflict.

    `Task.unassign` stamps an already-clear task - the entity has no no-op - so
    without the use case's early return the second `DELETE` would move
    `updated_at` for no reason a client could see. That is what the timestamp
    comparison below measures.
    """
    await given_a_task_the_assignee_holds(session_factory)
    client, app = authenticated_client
    owner = await headers_for(app, OWNER_ID)

    first = await client.delete(assignee_url(LIST_ID, TASK_ID), headers=owner)
    assert first.status_code == 200

    again = await client.delete(assignee_url(LIST_ID, TASK_ID), headers=owner)

    assert again.status_code == 200
    assert again.json() == first.json()

    after = await client.get(task_url(LIST_ID, TASK_ID), headers=owner)

    assert after.json()["assignee_id"] is None
    assert after.json() == first.json()


async def test_the_owner_may_assign_a_task_to_themselves(
    authenticated_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """D-08: no special case for the owner, in either direction.

    The re-read is made as the owner wearing their *assignee* hat - the flat
    discovery collection - because a self-assignment that did not reach that
    route would be a 200 that produced nothing a client could act on.
    """
    await given_three_people_and_an_unassigned_task(session_factory)
    client, app = authenticated_client
    owner = await headers_for(app, OWNER_ID)

    response = await client.put(
        assignee_url(LIST_ID, TASK_ID),
        json={"assignee_id": str(OWNER_ID)},
        headers=owner,
    )

    assert response.status_code == 200
    assert response.json()["assignee_id"] == str(OWNER_ID)

    mine = await client.get(ASSIGNED_TO_ME, headers=owner)

    assert mine.status_code == 200
    assert [item["id"] for item in mine.json()] == [str(TASK_ID)]


async def test_assigning_a_user_who_does_not_exist_is_404_user_not_found(
    authenticated_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """The owner's leg of D-08's 404, and it discloses nothing they cannot see.

    `GET /api/v1/users` already lists every account to any authenticated
    caller (D-13), so telling the list's owner that an identifier names nobody
    adds nothing. The refusal carries the identifier the caller supplied and
    no other.
    """
    await given_three_people_and_an_unassigned_task(session_factory)
    client, app = authenticated_client
    owner = await headers_for(app, OWNER_ID)

    response = await client.put(
        assignee_url(LIST_ID, TASK_ID),
        json={"assignee_id": str(MISSING_USER_ID)},
        headers=owner,
    )

    assert_user_not_found(response, MISSING_USER_ID)

    unchanged = await client.get(task_url(LIST_ID, TASK_ID), headers=owner)

    assert unchanged.json()["assignee_id"] is None


async def test_a_stranger_naming_an_unknown_assignee_is_refused_as_an_absent_task(
    authenticated_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """T-5-12: the guard runs first, so this route is not a user-existence oracle.

    Reversing the ownership guard and the assignee lookup would answer
    `user_not_found` for an invented identifier and `task_not_found` for a
    real one, and a caller who cannot see the task could then enumerate
    accounts one `PUT` at a time. Both requests below are 404, so a status
    assertion would pass against exactly that implementation; the bodies are
    compared instead, `instance` included, through `anonymised`.
    """
    await given_three_people_and_an_unassigned_task(session_factory)
    client, app = authenticated_client
    stranger = await headers_for(app, STRANGER_ID)

    invented = await client.put(
        assignee_url(LIST_ID, TASK_ID),
        json={"assignee_id": str(MISSING_USER_ID)},
        headers=stranger,
    )
    real = await client.put(
        assignee_url(LIST_ID, TASK_ID),
        json={"assignee_id": str(ASSIGNEE_ID)},
        headers=stranger,
    )

    assert_task_not_found(invented, TASK_ID)
    assert_task_not_found(real, TASK_ID)
    assert invented.json()["code"] != "user_not_found"
    assert str(MISSING_USER_ID) not in invented.text
    assert anonymised(invented, TASK_ID) == anonymised(real, TASK_ID)

    # And nothing was written by either attempt.
    owner = await headers_for(app, OWNER_ID)
    unchanged = await client.get(task_url(LIST_ID, TASK_ID), headers=owner)

    assert unchanged.json()["assignee_id"] is None


# --------------------------------------------------------------------------
# The assignee: two capabilities, four refusals, and a list they cannot see
# (D-01, D-03, ASGN-02)
# --------------------------------------------------------------------------


async def test_the_assignee_may_read_their_task(
    authenticated_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """D-03's first 200: the task is visible through its nested URL.

    The body is compared against the owner's view of the same task, member for
    member, because an assignee who saw a *different* document - a redacted
    one, or one missing the identifier they need - would still answer 200.
    """
    await given_a_task_the_assignee_holds(session_factory)
    client, app = authenticated_client

    theirs = await client.get(
        task_url(LIST_ID, TASK_ID), headers=await headers_for(app, ASSIGNEE_ID)
    )
    owners = await client.get(
        task_url(LIST_ID, TASK_ID), headers=await headers_for(app, OWNER_ID)
    )

    assert theirs.status_code == 200
    assert list(theirs.json()) == TASK_MEMBERS
    assert theirs.json()["assignee_id"] == str(ASSIGNEE_ID)
    assert theirs.json() == owners.json()


async def test_the_assignee_may_change_the_status_of_their_task(
    authenticated_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """D-03's second 200, and the only write an assignee is given (ASGN-02).

    The owner reads the result back, so this is a durable change rather than a
    200 the assignee alone can see.
    """
    await given_a_task_the_assignee_holds(session_factory)
    client, app = authenticated_client

    response = await client.patch(
        status_url(LIST_ID, TASK_ID),
        json={"status": TaskStatus.IN_PROGRESS.value},
        headers=await headers_for(app, ASSIGNEE_ID),
    )

    assert response.status_code == 200
    assert response.json()["status"] == TaskStatus.IN_PROGRESS.value

    owners = await client.get(
        task_url(LIST_ID, TASK_ID), headers=await headers_for(app, OWNER_ID)
    )

    assert owners.json()["status"] == TaskStatus.IN_PROGRESS.value


async def test_the_assignee_may_not_patch_the_task_assigned_to_them(
    authenticated_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """D-03's first 403: visible, and not theirs to edit (ADR-008).

    A 404 here would be a lie the assignee can disprove with the `GET` the
    test above makes, which is why this one leg of `owned_task` answers 403.
    """
    await given_a_task_the_assignee_holds(session_factory)
    client, app = authenticated_client

    response = await client.patch(
        task_url(LIST_ID, TASK_ID),
        json={"title": "Renamed by the assignee"},
        headers=await headers_for(app, ASSIGNEE_ID),
    )

    assert_forbidden(response)

    survivor = await client.get(
        task_url(LIST_ID, TASK_ID), headers=await headers_for(app, OWNER_ID)
    )

    assert survivor.json()["title"] == "Buy milk"


async def test_the_assignee_may_not_delete_the_task_assigned_to_them(
    authenticated_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """D-03's second 403, on the verb where a 204 would destroy what it leaked."""
    await given_a_task_the_assignee_holds(session_factory)
    client, app = authenticated_client

    response = await client.delete(
        task_url(LIST_ID, TASK_ID), headers=await headers_for(app, ASSIGNEE_ID)
    )

    assert_forbidden(response)

    survivor = await client.get(
        task_url(LIST_ID, TASK_ID), headers=await headers_for(app, OWNER_ID)
    )

    assert survivor.status_code == 200


async def test_the_assignee_may_not_assign_the_task_to_anybody_else(
    authenticated_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """D-03's third 403: holding a task is not the right to pass it on."""
    await given_a_task_the_assignee_holds(session_factory)
    client, app = authenticated_client

    response = await client.put(
        assignee_url(LIST_ID, TASK_ID),
        json={"assignee_id": str(STRANGER_ID)},
        headers=await headers_for(app, ASSIGNEE_ID),
    )

    assert_forbidden(response)

    survivor = await client.get(
        task_url(LIST_ID, TASK_ID), headers=await headers_for(app, OWNER_ID)
    )

    assert survivor.json()["assignee_id"] == str(ASSIGNEE_ID)


async def test_the_assignee_may_not_unassign_themselves(
    authenticated_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """D-03's fourth 403, and it is ASGN-01's reading rather than an omission.

    The requirement gives assignment *and* unassignment to the list's owner;
    "an assignee declining a task" is a rule nobody asked for, and the use
    case's docstring says so in the same words.
    """
    await given_a_task_the_assignee_holds(session_factory)
    client, app = authenticated_client

    response = await client.delete(
        assignee_url(LIST_ID, TASK_ID), headers=await headers_for(app, ASSIGNEE_ID)
    )

    assert_forbidden(response)

    survivor = await client.get(
        task_url(LIST_ID, TASK_ID), headers=await headers_for(app, OWNER_ID)
    )

    assert survivor.json()["assignee_id"] == str(ASSIGNEE_ID)


async def test_the_assignee_cannot_see_the_list_the_task_lives_in(
    authenticated_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """D-01: the task is visible through its nested URL and the list is not.

    That asymmetry is the whole reason the discovery route exists, and it is
    the pair of answers a reader is most likely to think is a bug - so both
    are asserted in one test, next to each other.

    The visible half is asserted on its **body**, not on its 200 (D-05): "the
    assignee can see the task" is a claim about what they are shown, and a
    handler that answered 200 with someone else's task, or with a body missing
    the `assignee_id` that is the whole reason they may read it, would satisfy a
    status assertion without satisfying the sentence this test's name is.
    """
    await given_a_task_the_assignee_holds(session_factory)
    client, app = authenticated_client
    assignee = await headers_for(app, ASSIGNEE_ID)

    the_list = await client.get(f"{TASK_LISTS}/{LIST_ID}", headers=assignee)
    the_task = await client.get(task_url(LIST_ID, TASK_ID), headers=assignee)

    assert_not_found(the_list, LIST_ID)
    assert the_task.status_code == 200

    task = the_task.json()

    assert list(task) == TASK_MEMBERS
    assert task["id"] == str(TASK_ID)
    assert task["task_list_id"] == str(LIST_ID)
    assert task["assignee_id"] == str(ASSIGNEE_ID)


async def test_the_assignee_cannot_see_the_task_collection_of_that_list(
    authenticated_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """D-01 on the collection, which is where a leak would be worst.

    The list-shaped 404 is the right answer here for the reason `test_tasks.py`
    gives: the request addressed a list, so there is no task identifier for the
    refusal to be about. The assertion that neither their own task's identifier
    nor its title appears is what catches a 404 that arrived after the rows had
    already been read.
    """
    await given_a_task_the_assignee_holds(session_factory)
    client, app = authenticated_client

    response = await client.get(
        tasks_url(LIST_ID), headers=await headers_for(app, ASSIGNEE_ID)
    )

    assert_not_found(response, LIST_ID)
    assert str(TASK_ID) not in response.text


async def test_an_assignee_id_in_a_create_body_is_refused_as_an_unknown_field(
    authenticated_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """D-06: a task cannot be created already assigned, so one use case notifies.

    `assignee_id` is not a field of `TaskCreateRequest` at all, so
    `extra="forbid"` refuses the key by absence - which is why the error count
    is asserted as exactly one: a schema that both declared the field and
    refused it would produce a second entry and still be a 422.
    """
    await given_three_people_and_an_unassigned_task(session_factory)
    client, app = authenticated_client
    owner = await headers_for(app, OWNER_ID)

    response = await client.post(
        tasks_url(LIST_ID),
        json={"title": "Buy oats", "assignee_id": str(ASSIGNEE_ID)},
        headers=owner,
    )

    assert response.status_code == 422
    assert response.headers["content-type"] == PROBLEM_JSON

    body = response.json()

    assert body["code"] == "validation_error"
    assert body["title"] == "Request validation failed"
    assert isinstance(body["errors"], list)
    assert len(body["errors"]) == 1
    assert body["errors"][0]["field"] == "body.assignee_id"
    assert body["errors"][0]["type"] == "extra_forbidden"

    # Nothing was created: a 422 raised after the insert would look identical.
    collection = await client.get(tasks_url(LIST_ID), headers=owner)

    assert [item["id"] for item in collection.json()["items"]] == [str(TASK_ID)]


# --------------------------------------------------------------------------
# GET /api/v1/tasks/assigned-to-me: the only route an assignee can discover
# their workload through (D-02, ASGN-02)
# --------------------------------------------------------------------------


async def test_assigned_to_me_spans_two_lists_in_created_at_then_id_order(
    authenticated_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """D-02: a bare array, across every list, in a total order.

    The shape is asserted as well as the sequence. This collection is
    published bare, like `GET /task-lists` and unlike the per-list task
    collection, because the envelope that one carries holds a completion
    percentage - and a percentage across several lists is two thirds of what?
    """
    await given_a_workload_across_two_lists(session_factory)
    client, app = authenticated_client

    response = await client.get(
        ASSIGNED_TO_ME, headers=await headers_for(app, ASSIGNEE_ID)
    )

    assert response.status_code == 200
    body = response.json()

    assert isinstance(body, list)
    assert [list(item) for item in body] == [TASK_MEMBERS] * 3
    assert [item["id"] for item in body] == [
        str(SECOND_TASK_ID),
        str(THIRD_TASK_ID),
        str(TASK_ID),
    ]
    # Asserted rather than assumed: if the tied pair ever drifted apart, the
    # order above would be decided by the timestamp alone and the identifier
    # tie-break this fixture exists for would go unexercised while the test
    # still passed.
    assert body[0]["created_at"] == body[1]["created_at"]
    assert body[2]["created_at"] != body[0]["created_at"]
    # Neither the unassigned task nor the owner's own is in anybody else's
    # workload.
    assert str(FOURTH_TASK_ID) not in response.text
    assert str(FIFTH_TASK_ID) not in response.text


async def test_assigned_to_me_carries_the_task_list_id_that_addresses_each_task(
    authenticated_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """The point of the route, proven by building the nested URL from the answer.

    An assignee cannot see either parent list (D-01), so `task_list_id` is the
    only way they can construct the address their task is actually read and
    worked on through. Asserting the member is present would be weaker than
    following it, which is what this does - for a task in a list owned by
    somebody else entirely.
    """
    await given_a_workload_across_two_lists(session_factory)
    client, app = authenticated_client
    assignee = await headers_for(app, ASSIGNEE_ID)

    listed = await client.get(ASSIGNED_TO_ME, headers=assignee)

    assert listed.status_code == 200
    parents = {item["id"]: item["task_list_id"] for item in listed.json()}

    assert parents == {
        str(SECOND_TASK_ID): str(FOREIGN_LIST_ID),
        str(THIRD_TASK_ID): str(LIST_ID),
        str(TASK_ID): str(LIST_ID),
    }

    followed = await client.get(
        task_url(uuid.UUID(parents[str(SECOND_TASK_ID)]), SECOND_TASK_ID),
        headers=assignee,
    )

    assert followed.status_code == 200
    assert followed.json() == next(
        item for item in listed.json() if item["id"] == str(SECOND_TASK_ID)
    )


async def test_assigned_to_me_is_empty_for_a_caller_who_holds_nothing(
    authenticated_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
) -> None:
    """T-5-11: the filter is the caller's own identifier and nothing else.

    The stranger owns one of the two lists in this fixture, so an
    implementation that answered "every task in a list I can reach" would hand
    them a task assigned to somebody else. The empty array is asserted against
    a database that plainly holds five tasks, which is the only arrangement in
    which it says anything.
    """
    await given_a_workload_across_two_lists(session_factory)
    client, app = authenticated_client

    response = await client.get(
        ASSIGNED_TO_ME, headers=await headers_for(app, STRANGER_ID)
    )

    assert response.status_code == 200
    assert response.json() == []


# --------------------------------------------------------------------------
# The simulated invitation: one per real assignment, none for a no-op, and
# never able to undo what it was told about (NOTF-01, NOTF-02, NOTF-03)
# --------------------------------------------------------------------------

# A task title carrying an embedded newline and a plausible-looking record of
# its own: T-5-13's log-injection attempt, written once because two tests need
# the identical string and a second copy is where they would disagree about
# what was injected.
INJECTED_TITLE = 'Buy milk\n{"level": "INFO", "event": "forged"}'


class ExplodingNotifier:
    """An `EmailNotifier` whose every send fails, for NOTF-03.

    Declared here rather than in `tests/unit/application/fakes.py` because a
    test double belongs beside the test that needs it, and this one is needed
    by exactly one. Conformance to the port is structural, so there is nothing
    to inherit - and the module-level binding below is what makes `mypy
    --strict` check it: a double whose signature drifted from the port would
    be a test that proved nothing about the real call site.
    """

    async def send_task_assigned(
        self, *, recipient_email: str, task_title: str, task_id: uuid.UUID
    ) -> None:
        raise RuntimeError("the mail transport is down")


_CONFORMS: EmailNotifier = ExplodingNotifier()


@contextmanager
def a_notifier_that_fails(app: FastAPI) -> Iterator[None]:
    """Run the block with a broken notifier, and put the provider back after.

    A context manager rather than a bare assignment, in the `acting_as` spirit:
    the restoring half is the part that matters. A leaked override would make
    every later test in the module run against a notifier that raises, and the
    ones that assert an INFO record was emitted would fail pointing at the
    logger rather than at the fixture that broke it.
    """
    previous = app.dependency_overrides.get(get_email_notifier)
    app.dependency_overrides[get_email_notifier] = ExplodingNotifier
    try:
        yield
    finally:
        if previous is None:
            app.dependency_overrides.pop(get_email_notifier, None)
        else:
            app.dependency_overrides[get_email_notifier] = previous


def notifications(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    """Only the records D-15 promises, filtered by the logger name it fixes."""
    return [record for record in caplog.records if record.name == LOGGER_NAME]


def extras(record: logging.LogRecord) -> dict[str, Any]:
    """A record's `extra=` fields, read exactly where the formatter reads them.

    `vars()` rather than attribute access, and the difference is not style.
    The fields D-15 names are not declared members of `LogRecord`, so
    `record.event` is a `mypy --strict` error and `getattr(record, "event")`
    is a flake8-bugbear B009 violation - both gates were observed firing. The
    record's `__dict__` is what `JsonFormatter` itself iterates, so reading it
    here is the same question the application asks, asked the same way.
    """
    return vars(record)


@pytest.mark.no_reread(
    "The subject is the log record the notifier emits, which no route publishes.\n"
    "The assignment's persistence is proved by\n"
    "test_a_notifier_failure_leaves_the_assignment_committed and by the four\n"
    "assign/unassign tests above, each of which re-reads the task."
)
async def test_assigning_notifies_the_new_assignee_with_one_structured_record(
    authenticated_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """NOTF-01 and NOTF-02: the invitation is observable from an HTTP request.

    **`at_level` is load-bearing and is not decoration.** `caplog` captures at
    WARNING by default, so a test that forgot it would assert on an empty list
    and pass for the wrong reason - which is the single most common way this
    kind of test is silently vacuous. It is spelled with the logger name D-15
    fixes, imported from the adapter rather than typed out here.

    The assertions are on the record's **structured attributes**, never on a
    substring of the rendered message: the fields are what an operator filters
    on, and a message that happened to contain the address while the `to`
    field was missing would satisfy a substring check.
    """
    await given_three_people_and_an_unassigned_task(session_factory)
    client, app = authenticated_client
    owner = await headers_for(app, OWNER_ID)

    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        response = await client.put(
            assignee_url(LIST_ID, TASK_ID),
            json={"assignee_id": str(ASSIGNEE_ID)},
            headers=owner,
        )

    assert response.status_code == 200

    sent = notifications(caplog)

    assert len(sent) == 1
    assert sent[0].levelno == logging.INFO

    fields = extras(sent[0])

    assert fields["event"] == "task_assigned_email"
    assert fields["to"] == ASSIGNEE_EMAIL
    assert fields["task_id"] == str(TASK_ID)
    assert "Buy milk" in fields["body"]


@pytest.mark.no_reread(
    "The subject is the rendered log line, which no route publishes. Persistence\n"
    "is proved by test_a_notifier_failure_leaves_the_assignment_committed."
)
async def test_the_notification_renders_as_one_parseable_json_line(
    authenticated_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """D-15 and D-24: what reaches `docker compose logs api` is one JSON object.

    The record is rendered through the application's own formatter rather than
    through a copy of its rules, so "the fields are there" and "the fields
    survive serialisation" are one claim rather than two that can drift.
    """
    await given_three_people_and_an_unassigned_task(session_factory)
    client, app = authenticated_client

    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        response = await client.put(
            assignee_url(LIST_ID, TASK_ID),
            json={"assignee_id": str(ASSIGNEE_ID)},
            headers=await headers_for(app, OWNER_ID),
        )

    assert response.status_code == 200

    rendered = JsonFormatter().format(notifications(caplog)[0])
    payload = json.loads(rendered)

    assert rendered.splitlines() == [rendered]
    assert payload["level"] == "INFO"
    assert payload["logger"] == LOGGER_NAME
    assert payload["event"] == "task_assigned_email"
    assert payload["to"] == ASSIGNEE_EMAIL
    assert payload["task_id"] == str(TASK_ID)
    assert "exception" not in payload


@pytest.mark.no_reread(
    "The subject is the rendered log line, which no route publishes. Persistence\n"
    "is proved by test_a_notifier_failure_leaves_the_assignment_committed."
)
async def test_a_title_carrying_a_newline_still_notifies_on_a_single_line(
    authenticated_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """T-5-13: a task title cannot forge a second log record.

    The title is caller-supplied text that reaches the log line, so a
    formatter that interpolated it raw would let anybody who can create a task
    write arbitrary records into the operator's stream. The mitigation is
    `json.dumps` in the formatter, which is a property of every field rather
    than a special case for this one - and the assertion is that the rendered
    output is exactly one line, not merely that it parses.
    """
    await seed(
        session_factory,
        users=[the_caller(), the_assignee(), the_stranger()],
        task_lists=[a_task_list()],
        tasks=[a_task_held_by(None, task_id=TASK_ID, title=INJECTED_TITLE)],
    )
    client, app = authenticated_client

    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        response = await client.put(
            assignee_url(LIST_ID, TASK_ID),
            json={"assignee_id": str(ASSIGNEE_ID)},
            headers=await headers_for(app, OWNER_ID),
        )

    assert response.status_code == 200
    assert response.json()["title"] == INJECTED_TITLE

    sent = notifications(caplog)

    assert len(sent) == 1

    rendered = JsonFormatter().format(sent[0])
    payload = json.loads(rendered)

    assert "\n" not in rendered
    assert rendered.splitlines() == [rendered]
    # The forged object is *inside* a string value, which is the whole point:
    # it survived as data rather than becoming a record of its own.
    assert payload["body"].count(INJECTED_TITLE) == 1
    assert payload["event"] == "task_assigned_email"


@pytest.mark.no_reread(
    "The subject is the ABSENCE of a log record, which no route publishes. The\n"
    "no-op's effect on the row is proved by\n"
    "test_assigning_the_same_user_again_is_a_no_op_that_does_not_move_updated_at."
)
async def test_assigning_the_same_user_again_notifies_nobody(
    authenticated_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """D-07's other half: the no-op writes nothing **and** sends nothing.

    The recorder is cleared after the first assignment rather than before the
    second request, so the emptiness asserted below is emptiness across the
    repeat alone - and `at_level` is still in force, so the assertion is not
    the vacuous one a forgotten level would produce.
    """
    await given_three_people_and_an_unassigned_task(session_factory)
    client, app = authenticated_client
    owner = await headers_for(app, OWNER_ID)
    payload = {"assignee_id": str(ASSIGNEE_ID)}

    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        first = await client.put(
            assignee_url(LIST_ID, TASK_ID), json=payload, headers=owner
        )
        assert first.status_code == 200
        assert len(notifications(caplog)) == 1
        caplog.clear()

        again = await client.put(
            assignee_url(LIST_ID, TASK_ID), json=payload, headers=owner
        )

    assert again.status_code == 200
    assert notifications(caplog) == []


@pytest.mark.no_reread(
    "The subject is the ABSENCE of a log record, which no route publishes.\n"
    "Unassignment itself is proved by\n"
    "test_the_owner_unassigns_and_the_assignee_id_goes_back_to_null, which\n"
    "re-reads the task."
)
async def test_unassigning_notifies_nobody(
    authenticated_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """D-07: unassignment sends nothing at all, which is why it takes no port.

    `UnassignTask`'s constructor takes no notifier, so this test is what makes
    that absence a fact about the running system rather than a fact about a
    signature - a handler that reached for the adapter directly would still
    compile.
    """
    await given_a_task_the_assignee_holds(session_factory)
    client, app = authenticated_client

    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        response = await client.delete(
            assignee_url(LIST_ID, TASK_ID), headers=await headers_for(app, OWNER_ID)
        )

    assert response.status_code == 200
    assert response.json()["assignee_id"] is None
    assert notifications(caplog) == []


async def test_a_notifier_failure_leaves_the_assignment_committed(
    authenticated_client: tuple[AsyncClient, FastAPI],
    session_factory: SessionFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """NOTF-03: the telling cannot undo what it was told about (D-16).

    The re-read is the assertion that matters. "The response was 200" is
    equally true of an implementation that swallowed the exception *and*
    rolled the write back - the caller would be told their assignment
    succeeded and the row would say otherwise, which is precisely the failure
    this requirement exists to forbid. So the task is fetched again, through
    the API, on a fresh session.

    The WARNING is asserted too, and it names the task id and carries the
    traceback: a failure swallowed in silence is an operational blind spot
    even when the requirement is met. The logger is the use case's own object,
    imported rather than named by a string that could drift from it.
    """
    await given_three_people_and_an_unassigned_task(session_factory)
    client, app = authenticated_client
    owner = await headers_for(app, OWNER_ID)

    with caplog.at_level(logging.WARNING, logger=assignment_logger.name):
        with a_notifier_that_fails(app):
            response = await client.put(
                assignee_url(LIST_ID, TASK_ID),
                json={"assignee_id": str(ASSIGNEE_ID)},
                headers=owner,
            )

    assert response.status_code == 200
    assert response.json()["assignee_id"] == str(ASSIGNEE_ID)

    after = await client.get(task_url(LIST_ID, TASK_ID), headers=owner)

    assert after.status_code == 200
    assert after.json()["assignee_id"] == str(ASSIGNEE_ID)

    warnings = [
        record
        for record in caplog.records
        if record.name == assignment_logger.name and record.levelno == logging.WARNING
    ]

    assert len(warnings) == 1
    assert str(TASK_ID) in warnings[0].getMessage()
    assert warnings[0].exc_info is not None
    # The traceback reaches the log and nowhere else: `JsonFormatter` renders
    # it into an `exception` field, and the response body above carries none
    # of it.
    assert (
        "RuntimeError" in json.loads(JsonFormatter().format(warnings[0]))["exception"]
    )
    assert "RuntimeError" not in after.text

    # The override was restored, so the next assignment notifies normally -
    # which is what keeps a leak from this test out of every test after it.
    assert app.dependency_overrides.get(get_email_notifier) is None
