"""AUTH-06 as one table: nineteen routes, four callers, seventy-six cells (D-04).

The sibling modules in this package each prove one route thoroughly. That is
the right shape for a route and the wrong shape for an authorization *claim*:
"every route refuses every caller who should not reach it" is a cross-product,
and a cross-product asserted one file at a time has no place where a missing
cell is visible. A route nobody wrote a stranger test for simply has no failing
test - the gap and the pass look identical from the outside.

So this module is the table itself. `MATRIX` below carries one entry per route,
each naming the method, the published path template and the four statuses the
four callers are owed, and the parametrized test drives all of them. A cell
that was never thought about is a number missing from a row a reader can see,
which is the whole of D-04.

Four things are specific to this module.

**The route set is derived from the published document, not maintained by
hand.** `test_the_table_covers_every_operation_the_document_publishes` reads
`app.openapi()["paths"]` and asserts it equals the set of `(method, path)`
pairs the table covers. Without it the table is a list someone remembers to
update; with it, a route shipped later without a row here is a failing test
(ADR-057). The document is read rather than the router table for the reason
`tests/unit/test_app_factory.py` gives in full: on the pinned stack
`include_router` leaves an opaque object behind, and the document is also the
thing a client reads.

**The three open routes are asserted open rather than skipped.** `/health`,
register and login answer an anonymous caller, and "which routes need no
token" is then a fact this table *states* instead of a gap a reader has to
infer from three absent rows. Their success legs additionally assert that no
`WWW-Authenticate` challenge came back, so "open" means openness rather than a
refusal that happened to carry a 2xx.

**The paths are spelled out here rather than imported.** Every other module in
this package imports its URLs from the one that owns them, and that convention
is deliberately set aside for the table's own column: a table assembled from
fragments defined in five files is no longer a table, and the same table is
reused as documentation in Phase 7 (D-04). Nothing is lost by it - the coverage
test binds every one of these strings to the published document, which is a
stronger check than agreeing with a helper in a sibling test.

**Every cell asserts a body, never a bare status.** A 401 asserts the RFC 9110
challenge header and the shared refusal document; a 403 asserts
`authorization_failed`; a 404 asserts the `code` and the `errors` member of
whichever shape that row is owed, through the same helpers the per-route
modules use. A status-only matrix would pass against an implementation that
answered 404 while naming the resource in the body. A 2xx asserts the document
the status promises - the fields the request sent come back, a 204 carries no
body at all, and a submitted credential never appears in the answer - and a
2xx that *wrote* something then reads it back through the API and asserts the
end state, so a DELETE that answered 204 and deleted nothing is a red cell
rather than a green one (ADR-096).

What this module deliberately does **not** do is re-litigate the per-route
behaviour. The assignee's refusals are asserted in `test_assignment.py` with an
owner-side re-read proving nothing was written, the collections' *contents* are
pinned in `test_task_lists.py`, `test_tasks.py` and `test_users.py`, and the
statement counts in `test_statements.py`. This table's contribution is
completeness across the cross-product and the anonymous column, not a second
copy of those proofs.
"""

import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Final, cast

import pytest
from fastapi import FastAPI
from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncConnection

from taskmanager.domain.entities.user import User
from taskmanager.domain.exceptions import AuthenticationError
from taskmanager.domain.value_objects.task_status import TaskStatus
from taskmanager.infrastructure.security.resources import SecurityResources
from taskmanager.presentation.api.dependencies import get_engine
from tests.integration.api.test_assignment import (
    a_task_held_by,
    assert_forbidden,
    the_assignee,
    the_stranger,
)
from tests.integration.api.test_task_lists import (
    LIST_ID,
    TASK_ID,
    SessionFactory,
    a_task_list,
    assert_not_found,
)
from tests.integration.api.test_tasks import assert_task_not_found
from tests.integration.api.test_users import (
    ASSIGNEE_ID,
    CALLER_EMAIL,
    CALLER_FULL_NAME,
    EARLIER,
    STRANGER_ID,
)
from tests.integration.conftest import OWNER_ID, bearer_header, seed

# Imported rather than re-declared - the convention `test_task_lists.py`
# states: the error contract has one home, `tests/problem_details.py`.
from tests.problem_details import MEMBERS, PROBLEM_JSON

pytestmark = pytest.mark.integration

# The credential the login row is driven with. Invented here and used nowhere
# else in the repository: D-14 removed the seeded account precisely so the
# project ships no known password, and a value borrowed from `test_auth.py`
# would make the two modules fail together the day one of them changed it.
PASSWORD = "matrix-rehearsal-passphrase"
NEWCOMER_EMAIL = "matrix-newcomer@example.com"
WRONG_PASSWORD = "matrix-rehearsal-passphrase-but-wrong"

# The fields a request may send that must never come back in the answer. A
# register echoes the address and the name it was given and must not echo the
# credential, and the same rule covers every value of a `form` body - login is
# handed a password and answers a token (T-06-54).
SECRET_FIELDS: Final[frozenset[str]] = frozenset({"password"})

# The four values the mutating rows write, each spelled once and read by both
# the row that sends it and the confirmation that looks for it. The plan asked
# for these to be read back out of `MATRIX` so the two cannot drift; a shared
# constant is the same guarantee without a subscript into the table, and it
# reads as the sentence the confirmation asserts.
LIST_NAME = "A matrix list"
RENAMED_LIST_NAME = "Renamed by the matrix"
TASK_TITLE = "A matrix task"
RETITLED_TASK_TITLE = "Retitled by the matrix"

# The two refusal shapes a 404 in this API can have. Rows 8-12 address a list,
# so they answer the list-shaped error even when the caller asked about tasks
# inside it (D-01); rows 13-18 address a task and answer the task-shaped one.
LIST_NOT_FOUND = "task_list_not_found"
TASK_NOT_FOUND = "task_not_found"

# The nineteen published paths, exactly as `/openapi.json` spells them - the
# placeholders included, because the coverage test compares these strings with
# the document's own keys.
HEALTH = "/health"
REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"
ME = "/api/v1/auth/me"
USERS = "/api/v1/users"
TASK_LISTS = "/api/v1/task-lists"
ONE_LIST = "/api/v1/task-lists/{list_id}"
LIST_TASKS = "/api/v1/task-lists/{list_id}/tasks"
ONE_TASK = "/api/v1/task-lists/{list_id}/tasks/{task_id}"
TASK_STATUS = "/api/v1/task-lists/{list_id}/tasks/{task_id}/status"
TASK_ASSIGNEE = "/api/v1/task-lists/{list_id}/tasks/{task_id}/assignee"
ASSIGNED_TO_ME = "/api/v1/tasks/assigned-to-me"


@dataclass(frozen=True, slots=True)
class Confirmation:
    """The `GET` that proves a mutating row's change reached the database.

    `path` is a published template addressed through `url()`, so a confirmation
    can only ever read a route this table already covers - the coverage test
    binds every one of those strings to `/openapi.json`. `shows` is the end
    state the mutation promised, written as a named function rather than a
    lambda: a lambda cannot contain an `assert`, and a named one reads as the
    sentence it is asserting.
    """

    path: str
    shows: Callable[[Response], None]


@dataclass(frozen=True, slots=True)
class Row:
    """One route of the table, with the four statuses its four callers get.

    The statuses are positional and in the table's own column order - owner,
    assignee, stranger, anonymous - so a row reads across the way the markdown
    table in `05-RESEARCH.md` does. Naming each of the four would make every
    entry three lines long and the table unreadable, which is the property
    D-04 asks for above all others.
    """

    number: int
    method: str
    path: str
    owner: int
    assignee: int
    stranger: int
    anonymous: int
    # The request body, for the verbs that need one. A `Mapping` rather than a
    # `dict` because these live at module scope for the whole session and are
    # handed to httpx per cell; nothing may edit one in place.
    body: Mapping[str, Any] | None = None
    # The form body, which exactly one row has: OAuth2 fixes `POST
    # /auth/login` as a form, and `username` carries the address.
    form: Mapping[str, str] | None = None
    # The `code` a 404 in this row carries. It does not vary by caller: an
    # invisible resource answers the same way to everyone who cannot see it,
    # which is the whole of ADR-008.
    not_found_code: str | None = None
    # The read that proves this row's mutation happened. `None` for a row that
    # writes nothing - every `GET`, and login. A mutating row that leaves it
    # `None` fails
    # `test_every_mutating_row_confirms_its_change_or_says_it_changes_nothing`.
    confirmation: Confirmation | None = None


# ---------------------------------------------------------------------------
# The ten confirmations: one per mutating row, each the end state that row's
# 2xx promised. They are what turns "the handler answered 201" into "the row is
# in the database" (D-06, T-06-52), and the two destructive rows confirm the
# only thing a deleted resource can say - its own 404 problem body, through the
# per-route modules' own helpers so the shape cannot drift from theirs.
# ---------------------------------------------------------------------------


def _the_newcomer_is_in_the_directory(response: Response) -> None:
    """Row 2: the address that registered is now one of the accounts."""
    assert NEWCOMER_EMAIL in {user["email"] for user in response.json()}


def _the_new_list_is_in_the_collection(response: Response) -> None:
    """Row 6: the created list is among the caller's own lists."""
    assert LIST_NAME in {item["name"] for item in response.json()}


def _the_list_carries_its_new_name(response: Response) -> None:
    """Row 9: the rename is what a reader of the list now sees."""
    assert response.json()["name"] == RENAMED_LIST_NAME


def _the_list_is_gone(response: Response) -> None:
    """Row 10: the deleted list answers its own 404 document (D-06)."""
    assert_not_found(response, LIST_ID)


def _the_new_task_is_in_the_collection(response: Response) -> None:
    """Row 11: the created task is among the list's tasks."""
    assert TASK_TITLE in {item["title"] for item in response.json()["items"]}


def _the_task_carries_its_new_title(response: Response) -> None:
    """Row 14: the retitle is what a reader of the task now sees."""
    assert response.json()["title"] == RETITLED_TASK_TITLE


def _the_task_is_gone(response: Response) -> None:
    """Row 15: the deleted task answers its own 404 document (D-06)."""
    assert_task_not_found(response, TASK_ID)


def _the_task_is_in_progress(response: Response) -> None:
    """Row 16: the status the request asked for is the status it holds."""
    assert response.json()["status"] == TaskStatus.IN_PROGRESS.value


def _the_assignee_holds_the_task(response: Response) -> None:
    """Row 17: the assignment is held by the person it named."""
    assert response.json()["assignee_id"] == str(ASSIGNEE_ID)


def _nobody_holds_the_task(response: Response) -> None:
    """Row 18: the unassignment left the task in nobody's hands."""
    assert response.json()["assignee_id"] is None


# ---------------------------------------------------------------------------
# The table (D-04), lifted from `05-RESEARCH.md` § "The full permission matrix".
#
#   Row(#, method, path, owner, assignee, stranger, anonymous, ...)
#
# `owner` owns the list; `assignee` holds the addressed task and owns nothing;
# `stranger` is an authenticated caller with no relationship to either; and
# `anonymous` sends no `Authorization` header at all.
#
# Rows 1-3 are the open routes. Rows 8-12 are D-01 - the list stays invisible,
# so its tasks do too. Rows 13-18 are D-03's split: an assignee may read their
# task and move its status, and may not edit it, delete it or decide who holds
# it. Row 19 is D-02, the only route through which an assignee can discover a
# task at all.
#
# Row 3's anonymous cell is the one answer in the table that depends on the
# *body* rather than on the caller: login is open, so good credentials are 200
# and bad ones are 401. The 200 is the cell below; the 401 is a test of its
# own, immediately after the parametrized walk, rather than a value this
# column had to pick between.
# ---------------------------------------------------------------------------

MATRIX: Final[tuple[Row, ...]] = (
    Row(1, "GET", HEALTH, 200, 200, 200, 200),
    Row(
        2,
        "POST",
        REGISTER,
        201,
        201,
        201,
        201,
        body={
            "email": NEWCOMER_EMAIL,
            "full_name": "Matrix Newcomer",
            "password": PASSWORD,
        },
        confirmation=Confirmation(USERS, _the_newcomer_is_in_the_directory),
    ),
    Row(
        3,
        "POST",
        LOGIN,
        200,
        200,
        200,
        200,
        form={"username": CALLER_EMAIL, "password": PASSWORD},
    ),
    Row(4, "GET", ME, 200, 200, 200, 401),
    Row(5, "GET", USERS, 200, 200, 200, 401),
    Row(
        6,
        "POST",
        TASK_LISTS,
        201,
        201,
        201,
        401,
        body={"name": LIST_NAME},
        confirmation=Confirmation(TASK_LISTS, _the_new_list_is_in_the_collection),
    ),
    Row(7, "GET", TASK_LISTS, 200, 200, 200, 401),
    Row(8, "GET", ONE_LIST, 200, 404, 404, 401, not_found_code=LIST_NOT_FOUND),
    Row(
        9,
        "PATCH",
        ONE_LIST,
        200,
        404,
        404,
        401,
        body={"name": RENAMED_LIST_NAME},
        not_found_code=LIST_NOT_FOUND,
        confirmation=Confirmation(ONE_LIST, _the_list_carries_its_new_name),
    ),
    Row(
        10,
        "DELETE",
        ONE_LIST,
        204,
        404,
        404,
        401,
        not_found_code=LIST_NOT_FOUND,
        confirmation=Confirmation(ONE_LIST, _the_list_is_gone),
    ),
    Row(
        11,
        "POST",
        LIST_TASKS,
        201,
        404,
        404,
        401,
        body={"title": TASK_TITLE},
        not_found_code=LIST_NOT_FOUND,
        confirmation=Confirmation(LIST_TASKS, _the_new_task_is_in_the_collection),
    ),
    Row(12, "GET", LIST_TASKS, 200, 404, 404, 401, not_found_code=LIST_NOT_FOUND),
    Row(13, "GET", ONE_TASK, 200, 200, 404, 401, not_found_code=TASK_NOT_FOUND),
    Row(
        14,
        "PATCH",
        ONE_TASK,
        200,
        403,
        404,
        401,
        body={"title": RETITLED_TASK_TITLE},
        not_found_code=TASK_NOT_FOUND,
        confirmation=Confirmation(ONE_TASK, _the_task_carries_its_new_title),
    ),
    Row(
        15,
        "DELETE",
        ONE_TASK,
        204,
        403,
        404,
        401,
        not_found_code=TASK_NOT_FOUND,
        confirmation=Confirmation(ONE_TASK, _the_task_is_gone),
    ),
    Row(
        16,
        "PATCH",
        TASK_STATUS,
        200,
        200,
        404,
        401,
        body={"status": TaskStatus.IN_PROGRESS.value},
        not_found_code=TASK_NOT_FOUND,
        confirmation=Confirmation(ONE_TASK, _the_task_is_in_progress),
    ),
    Row(
        17,
        "PUT",
        TASK_ASSIGNEE,
        200,
        403,
        404,
        401,
        body={"assignee_id": str(ASSIGNEE_ID)},
        not_found_code=TASK_NOT_FOUND,
        confirmation=Confirmation(ONE_TASK, _the_assignee_holds_the_task),
    ),
    Row(
        18,
        "DELETE",
        TASK_ASSIGNEE,
        200,
        403,
        404,
        401,
        not_found_code=TASK_NOT_FOUND,
        confirmation=Confirmation(ONE_TASK, _nobody_holds_the_task),
    ),
    Row(19, "GET", ASSIGNED_TO_ME, 200, 200, 200, 401),
)

# The three rows with no credential requirement, named by number so the test
# that asserts their openness cannot drift from the table above.
OPEN_ROWS: Final[frozenset[int]] = frozenset({1, 2, 3})

# Every row that writes something and therefore owes a read proving it. Named
# by number rather than derived from the `confirmation` field, because a set
# derived from the table would agree with the table by construction: a
# confirmation dropped in an edit would drop out of both sides at once and the
# guard below would still pass.
ROWS_THAT_CONFIRM: Final[frozenset[int]] = frozenset(
    {2, 6, 9, 10, 11, 14, 15, 16, 17, 18}
)

# The one mutating row that confirms nothing, named with its reason rather than
# left silently absent: `POST /auth/login` writes no resource, so there is no
# `GET` that could observe it. The round trip is
# `test_auth.py::test_register_then_login_then_get_me_reads_back_the_same_profile`'s
# to prove, and this row's own `no_reread` exemption in
# `tests/architecture/test_assertion_quality.py` says the same thing.
ROWS_THAT_MUTATE_NOTHING: Final[frozenset[int]] = frozenset({3})


@dataclass(frozen=True, slots=True)
class Cell:
    """One (row, caller) pair: the unit this module actually drives.

    `caller` is `None` for the anonymous column, which is the difference
    between sending a token that fails and sending no header at all - and it
    is the only column that measures the dependency a browser hits first.
    """

    row: Row
    role: str
    caller: uuid.UUID | None
    expected: int


def every_cell() -> tuple[Cell, ...]:
    """The cross-product, written out rather than generated from a role table.

    Four explicit lines per row, because each one pairs a column of `Row` with
    the identifier that column belongs to, and a loop over a `(name, id,
    attribute)` table would move that pairing behind a `getattr` no type
    checker can see through.
    """
    cells: list[Cell] = []
    for row in MATRIX:
        cells.append(Cell(row, "owner", OWNER_ID, row.owner))
        cells.append(Cell(row, "assignee", ASSIGNEE_ID, row.assignee))
        cells.append(Cell(row, "stranger", STRANGER_ID, row.stranger))
        cells.append(Cell(row, "anonymous", None, row.anonymous))
    return tuple(cells)


CELLS: Final[tuple[Cell, ...]] = every_cell()

# `NN-role-METHOD-path`, so a failure names the row of the table it came from
# and `-k anonymous` selects exactly the anonymous column.
CELL_IDS: Final[list[str]] = [
    f"{cell.row.number:02d}-{cell.role}-{cell.row.method}-{cell.row.path}"
    for cell in CELLS
]


def url(path: str) -> str:
    """A published path template, addressed at the fixture's list and task."""
    return path.replace("{list_id}", str(LIST_ID)).replace("{task_id}", str(TASK_ID))


def sending(row: Row) -> dict[str, Any]:
    """The httpx keyword arguments this row's body needs, and no others.

    Passing `json=None` is not the same as passing nothing: httpx would send
    the four bytes `null` with a JSON content type, and a `GET` carrying a body
    is not the request a client makes.
    """
    arguments: dict[str, Any] = {}
    if row.body is not None:
        arguments["json"] = dict(row.body)
    if row.form is not None:
        arguments["data"] = dict(row.form)
    return arguments


# The Argon2 hash of `PASSWORD`, computed once for the whole session.
#
# The login row needs a caller whose stored hash is real - the placeholder the
# sibling modules seed is not an Argon2 encoded hash, and the adapter answers
# `False` for it rather than raising, so a login against it would be a 401 and
# the row would assert the opposite of what it says. Hashing is deliberately
# expensive (a measured 37 ms), and this module seeds a caller for each of its
# seventy-seven tests, so the cost is paid once and reused: the parameters are
# the adapter's own and a hash does not belong to the application that produced
# it. A dict rather than a module-level `global`, which mypy and the reader
# both prefer.
_HASHES: dict[str, str] = {}


async def hashed(app: FastAPI, password: str) -> str:
    """This password's stored form, produced by the application's own hasher."""
    if password not in _HASHES:
        security = cast(SecurityResources, app.state.security)
        _HASHES[password] = await security.password_hasher.hash(password)
    return _HASHES[password]


def the_owner(password_hash: str) -> User:
    """The caller who owns the list, with a credential that really works.

    `test_users.py`'s builder takes no hash, which is exactly right for the
    modules that only need the row to exist behind a foreign key and useless
    here, where row 3 logs in as this person. Widening the sibling would put a
    parameter in every one of its callers that none of them uses - the argument
    that module already makes for its own builder.
    """
    return User.create(
        user_id=OWNER_ID,
        email=CALLER_EMAIL,
        full_name=CALLER_FULL_NAME,
        password_hash=password_hash,
        now=EARLIER,
    )


@pytest.fixture
async def matrix_client(
    authenticated_client: tuple[AsyncClient, FastAPI],
    connection: AsyncConnection,
    session_factory: SessionFactory,
) -> tuple[AsyncClient, FastAPI]:
    """Three people, one list and one assigned task - fresh for **every** cell.

    Function-scoped on purpose, and that is what makes the destructive rows
    safe. Rows 10 and 15 delete the very subject rows 8-18 address, and row 9
    renames it; ordered into one shared fixture they would decide each other's
    answers, and a matrix whose later rows depend on its earlier ones passes
    for the wrong reason. The outer transaction is rolled back per test
    anyway, so a fresh list and task cost one seeding statement each rather
    than a database.

    It is `authenticated_client` underneath, so the actor dependency is the
    real one: the three authenticated columns carry tokens this application
    minted and confirms on every request, and the anonymous column measures the
    dependency itself rather than an override standing in for it (D-20). That
    is also why all three people are seeded even for a cell that names one -
    the confirmation read (D-11) means an unseeded caller answers 401 instead
    of the refusal the cell was written to assert.

    One provider is overridden beyond the harness's own, and only one:
    `get_engine` is pointed at the connection this test already owns. The
    shared harness aims its application at a syntactically valid fiction so no
    unit test needs a server, and `/health` is the single route in the table
    that asks the database a question of its own rather than through the unit
    of work - against that DSN it would answer 503 and row 1 would be
    measuring the fiction instead of the route's openness. Nothing about
    authentication is replaced by it.
    """
    client, app = authenticated_client
    app.dependency_overrides[get_engine] = lambda: connection.engine

    await seed(
        session_factory,
        users=[the_owner(await hashed(app, PASSWORD)), the_assignee(), the_stranger()],
        task_lists=[a_task_list()],
        tasks=[a_task_held_by(ASSIGNEE_ID, task_id=TASK_ID)],
    )
    return client, app


def assert_a_bearer_challenge(response: Response) -> None:
    """What every 401 this API can answer with has in common.

    RFC 9110 15.5.2 requires a 401 to carry `WWW-Authenticate`, and the body
    is the six-member error document with no `errors` member: the generic
    refusal carries no details, so there is nothing in it that could differ
    between two refusals and become an oracle.
    """
    assert response.headers["content-type"] == PROBLEM_JSON
    assert response.headers["WWW-Authenticate"] == "Bearer"

    body = response.json()

    assert list(body) == MEMBERS
    assert body["code"] == "authentication_failed"


def assert_unauthenticated(response: Response) -> None:
    """The anonymous column's answer: the challenge above, and D-11's wording.

    The wording is read from `AuthenticationError.REFUSAL` rather than copied,
    because that constant is the mechanism D-11 rests on: the token adapter
    and the actor use case both raise with the default so the two cannot be
    told apart, and a literal here would be the copy that disagreed the first
    time it moved.
    """
    assert_a_bearer_challenge(response)
    assert response.json()["detail"] == AuthenticationError.REFUSAL


def assert_no_challenge_was_issued(response: Response) -> None:
    """A success is a success: no challenge header, no problem document.

    Applied to every 2xx cell, which is what turns rows 1-3 from "not asserted
    to need a token" into "asserted to answer without one".
    """
    assert "WWW-Authenticate" not in response.headers
    assert response.headers.get("content-type") != PROBLEM_JSON


def assert_the_success_document_says_what_was_asked_for(
    row: Row, response: Response
) -> None:
    """A 2xx owes the document its status promises, not merely a quiet header.

    Until this plan the success branch asserted only that no challenge came
    back, which a handler that answered and persisted nothing satisfies exactly
    as well as one that worked: `assert_no_challenge_was_issued` is a statement
    about what is *absent*. The cheapest honest oracle a table has is that the
    answer echoes the fields the request sent - the table already carries them,
    so nothing new has to be maintained to assert it - and the per-route
    modules keep their fuller claims about the members no request names.

    Three rules. A 204 is asserted to carry no body at all, because a 204 with
    one is a protocol violation and there is nothing else to read. Otherwise
    the body is parsed, which is itself the shape check - `.json()` raises on
    an answer that is not JSON - and every field the request sent is asserted
    present and equal, except a secret, which is asserted *absent* from the
    whole response text. Every value of a `form` body is asserted absent too:
    login is handed a password and answers a token, never the credential
    (T-06-54).
    """
    if response.status_code == 204:
        assert response.content == b"", response.text
        return

    body = response.json()

    for field, value in (row.body or {}).items():
        if field in SECRET_FIELDS:
            assert value not in response.text
        else:
            assert body[field] == value, body

    for value in (row.form or {}).values():
        assert value not in response.text

    assert isinstance(body, dict | list), body


NOT_FOUND_ASSERTIONS: Final[Mapping[str, Callable[[Response], None]]] = {
    LIST_NOT_FOUND: lambda response: assert_not_found(response, LIST_ID),
    TASK_NOT_FOUND: lambda response: assert_task_not_found(response, TASK_ID),
}


def assert_the_body_the_status_promises(cell: Cell, response: Response) -> None:
    """Every cell asserts a document, never only a number.

    A 404 whose `code` named the wrong resource, a 403 carrying an `errors`
    member naming the list's owner, or a 401 with no challenge would each
    satisfy a status-only matrix. The helpers are the per-route modules' own,
    so the shapes asserted here and there cannot drift apart.
    """
    if cell.expected == 401:
        assert_unauthenticated(response)
    elif cell.expected == 403:
        assert_forbidden(response)
    elif cell.expected == 404:
        assert cell.row.not_found_code is not None, cell.row
        NOT_FOUND_ASSERTIONS[cell.row.not_found_code](response)
    else:
        assert_no_challenge_was_issued(response)
        assert_the_success_document_says_what_was_asked_for(cell.row, response)


@pytest.mark.parametrize("cell", CELLS, ids=CELL_IDS)
async def test_the_permission_matrix_answers_what_the_table_promises(
    cell: Cell,
    matrix_client: tuple[AsyncClient, FastAPI],
) -> None:
    """One cell of D-04, driven end to end through the real dependency.

    The token is minted for a seeded row by the application's own service, and
    the anonymous column sends no header at all - not an empty one, not an
    invalid one. `test_auth.py` owns the seven ways a credential can be wrong;
    this column owns the one case where none was offered.

    A successful mutating cell then reads its change back, so what the cell
    proves is that the write reached the database rather than that the handler
    said it had (D-06). The reader is the caller that just mutated - a
    stranger's own list is read with the stranger's token, which is also the
    only way the read is a legal request - and the fallback to the owner exists
    for row 2 alone, whose caller may be anonymous while `GET /api/v1/users`
    needs a credential. A refused mutation reads nothing back: there is no
    change to confirm, and the "the resource is unchanged" leg of D-06 stays
    the per-route modules' to assert, where the before-and-after pair already
    lives.
    """
    client, app = matrix_client
    headers = (
        {}
        if cell.caller is None
        else {"Authorization": await bearer_header(app, cell.caller)}
    )

    response = await client.request(
        cell.row.method, url(cell.row.path), headers=headers, **sending(cell.row)
    )

    assert response.status_code == cell.expected, response.text
    assert_the_body_the_status_promises(cell, response)

    confirmation = cell.row.confirmation
    if confirmation is None or cell.expected >= 300:
        return

    reader = OWNER_ID if cell.caller is None else cell.caller
    read_back = await client.get(
        url(confirmation.path),
        headers={"Authorization": await bearer_header(app, reader)},
    )
    confirmation.shows(read_back)


@pytest.mark.no_reread(
    "POST /auth/login mutates no resource, so there is no resource to read back -\n"
    "and this caller is anonymous, so it could not read one if there were."
)
async def test_login_refuses_a_bad_credential_from_an_anonymous_caller(
    matrix_client: tuple[AsyncClient, FastAPI],
) -> None:
    """Row 3's second anonymous outcome, given a cell rather than a footnote.

    Login is the one row whose answer to an anonymous caller depends on the
    body: the route is open, so a good credential is 200 - the cell in the
    table above - and a bad one is 401. Asserting only the first would leave
    the table saying "login always answers 200", and asserting only the second
    would leave it saying the route needs a token.

    The refusal carries the same challenge, the same six members and the same
    `code` as every other 401 in the table. Its `detail` is deliberately *not*
    asserted to be D-11's wording, and the difference is real rather than an
    oversight: `AuthenticationError`'s docstring argues that login asks a
    different question at a different endpoint, so it passes a message of its
    own with a single home in `use_cases/auth/login.py`, and D-12's
    indistinguishability is between login's two legs - which is
    `test_auth.py`'s to assert, and it does, body to body. What is asserted
    here is the property that matters at this door: neither the address nor
    the password comes back in the document.
    """
    client, _ = matrix_client

    response = await client.post(
        url(LOGIN), data={"username": CALLER_EMAIL, "password": WRONG_PASSWORD}
    )

    assert response.status_code == 401
    assert_a_bearer_challenge(response)
    assert WRONG_PASSWORD not in response.text
    assert CALLER_EMAIL not in response.text


async def test_the_table_covers_every_operation_the_document_publishes(
    authenticated_client: tuple[AsyncClient, FastAPI],
) -> None:
    """ADR-057: a route added later without a row here is a failing test.

    Read out of the published document rather than off the application's route
    collection, for the reason `tests/unit/test_app_factory.py` gives at
    length: on the pinned stack an included router is a single opaque object
    with no path and no methods, so walking it would find the documentation
    endpoints and none of the nineteen. The document is also what a client
    reads, which makes it the honest place to take an inventory.

    The comparison is an equality rather than a subset in either direction. A
    subset one way would let a route ship unmeasured; the other way would let
    this table keep a row for a route that no longer exists, and a cell
    asserting the behaviour of nothing is worse than no cell at all.
    """
    _, app = authenticated_client

    published: set[tuple[str, str]] = {
        (method.upper(), path)
        for path, item in app.openapi()["paths"].items()
        for method in item
    }
    covered = {(row.method, row.path) for row in MATRIX}

    assert covered == published, {
        "unmeasured": sorted(published - covered),
        "stale": sorted(covered - published),
    }
    # Non-vacuity: an empty document would satisfy the equality above against
    # an empty table, and both halves would have to be wrong in the same way
    # for this to pass.
    assert len(published) == 19


def test_the_table_numbers_its_rows_once_each_from_one_to_nineteen() -> None:
    """The row numbers are the reader's index into D-04, so they are checked.

    A duplicated number would make a failure name the wrong row of the
    research document, and a duplicated `(method, path)` would be a cell
    asserted twice while another went unwritten - which the coverage test
    above cannot see, because a set swallows the repeat.
    """
    assert [row.number for row in MATRIX] == list(range(1, 20))
    assert len({(row.method, row.path) for row in MATRIX}) == len(MATRIX)
    assert len(CELLS) == 4 * len(MATRIX)
    assert len(set(CELL_IDS)) == len(CELLS)


def test_every_mutating_row_confirms_its_change_or_says_it_changes_nothing() -> None:
    """A mutating row added here without a re-read is a failing test (T-06-53).

    The assertion-quality gate makes "a mutating test re-reads" a build failure
    per *test*, and this module is one test parametrized seventy-six times - so
    a row added to the table with no confirmation would hide behind the
    confirmations of the rows beside it and the gate could not tell. This is
    that rule at the granularity the table actually has.

    Compared as an equality in both directions, twice over: a confirmation
    dropped from a row and a number listed that no row confirms both fail, and
    the set of mutating rows minus the confirmed ones has to be exactly the one
    row named as writing nothing. The last two assertions are about the
    confirmations themselves: a re-read may only address a path this table
    covers, which the coverage test binds to the published document, and every
    confirmation must have at least one cell that reaches it - a confirmation
    whose row succeeds for nobody is dead code that would pass for ever.
    """
    confirmed = {row.number for row in MATRIX if row.confirmation is not None}
    mutating = {row.number for row in MATRIX if row.method != "GET"}

    assert confirmed == ROWS_THAT_CONFIRM
    assert mutating - ROWS_THAT_CONFIRM == ROWS_THAT_MUTATE_NOTHING

    published = {row.path for row in MATRIX}
    for row in MATRIX:
        if row.confirmation is not None:
            assert row.confirmation.path in published, row

    for number in ROWS_THAT_CONFIRM:
        assert any(
            cell.expected < 300 for cell in CELLS if cell.row.number == number
        ), f"row {number} confirms a change no cell of it ever makes"
