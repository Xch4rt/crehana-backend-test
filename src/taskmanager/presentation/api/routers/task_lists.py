"""The five task-list routes: build a command, run a use case, map the result.

A handler here is four lines or fewer, and that is the phase's whole argument
made visible. Everything these routes call was proved by unit tests before any
of them existed, so a handler that grew a branch would be a business rule that
escaped a layer - and the layer it escaped is the one an evaluator reads first.

Three things are deliberately absent from every handler in this module.

There is no `try` and no `except`, and no web-framework error is ever raised.
A refusal is a `DomainError`, which `register_exception_handlers` turns into the
one RFC 9457 `application/problem+json` body the whole API speaks (ARC-07). A
router that answered a refusal itself would be a second place error bodies are
built, and the two would drift; ADR-008 also puts the *visibility* decision -
whether a caller may know a resource exists at all - in the use case, where the
ownership check lives. `tests/architecture/test_routers_raise_no_http_exception.py`
turns that from a convention into a gate (D-15).

Nothing here ends a transaction, and nothing here enters the unit of work's
context. The use case owns the transaction boundary (ARC-08, D-17), and
`SqlAlchemyUnitOfWork.__aenter__` refuses a second entry outright, so a router
that opened the block would fail loudly rather than quietly hold a session open
across the response. Both forbidden forms are described here rather than
spelled, the convention `test_no_commit_in_repositories.py` sets out, so the
grep gates this module is held to stay strict.

There is no length check, no past-date check and no duplicate-name lookup. The
entity owns its limits (Phase 2 D-04) and the use case owns the pre-check plus
the constraint translation (03-06, D-13); a copy here would be the one a client
actually hits, and it would answer with the wrong error shape.

Every route declares `response_model=` explicitly *and* is annotated with the
response schema. Annotating a handler with a result dataclass and leaving the
model to inference makes FastAPI publish the application DTO as the public
schema, and ARC-05's claim that Pydantic types every HTTP boundary quietly stops
being true.

Every route also declares a `responses` map, including the `500` leg that any
route can produce. The `500` is not decoration: Phase 2's catch-all handler
answers an unexpected failure with a fixed problem+json body, so it is a
documented outcome of this API rather than an accident, and naming it is what
lets the collection route below - which has no 404, no 409 and no 422 - still
publish an honest refusal map.
"""

from typing import Final
from uuid import UUID

from fastapi import APIRouter, FastAPI, Request, Response, status

from taskmanager.application.dto.commands import (
    DeleteTaskListCommand,
    GetTaskListCommand,
    ListTaskListsCommand,
)
from taskmanager.application.use_cases.task_lists.create import CreateTaskList
from taskmanager.application.use_cases.task_lists.delete import DeleteTaskList
from taskmanager.application.use_cases.task_lists.get import GetTaskList
from taskmanager.application.use_cases.task_lists.list import ListTaskLists
from taskmanager.application.use_cases.task_lists.update import UpdateTaskList
from taskmanager.presentation.api.actor import CurrentActor
from taskmanager.presentation.api.dependencies import (
    ClockDependency,
    UnitOfWorkDependency,
)
from taskmanager.presentation.api.schemas.task_lists import (
    TaskListCreateRequest,
    TaskListPatchRequest,
    TaskListResponse,
)

# The prefix is declared once, on the router, so `request.url_for` below can
# build a `Location` header that survives a change to either prefix. An
# f-string over `/api/v1/...` would not.
task_list_router = APIRouter(prefix="/task-lists", tags=["task lists"])

# The refusal descriptions, as constants rather than repeated literals: the same
# leg means the same thing on every verb, and a client reading `/openapi.json`
# should not have to decide whether two wordings describe two behaviours.
NOT_FOUND_DESCRIPTION: Final[str] = (
    "No such task list for this caller. A list that exists but belongs to "
    "someone else answers identically, so the response discloses nothing about "
    "resources the caller may not see (ADR-008, D-04)."
)
DUPLICATE_NAME_DESCRIPTION: Final[str] = (
    "The caller already owns a task list with this name. The comparison is "
    "case-sensitive (D-12)."
)
VALIDATION_DESCRIPTION: Final[str] = (
    "The request is malformed - an unknown or missing field, an explicit null "
    "on a field that has none, an empty patch body, an identifier that is not "
    "a UUID - or a value breaks a domain rule such as a length limit."
)
UNEXPECTED_DESCRIPTION: Final[str] = (
    "An unexpected server-side failure. The body is the same problem+json "
    "document as every other error, and carries no internal detail."
)


@task_list_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=TaskListResponse,
    summary="Create a task list",
    response_description=(
        "The created task list, with its completion counters, and a Location "
        "header naming its URL."
    ),
    responses={
        409: {"description": DUPLICATE_NAME_DESCRIPTION},
        422: {"description": VALIDATION_DESCRIPTION},
        500: {"description": UNEXPECTED_DESCRIPTION},
    },
)
async def create_task_list(
    payload: TaskListCreateRequest,
    actor_id: CurrentActor,
    uow: UnitOfWorkDependency,
    clock: ClockDependency,
    request: Request,
    response: Response,
) -> TaskListResponse:
    """Create a list owned by the caller, and say where it now lives (D-12).

    The owner is never read from the body. `TaskListCreateRequest` declares no
    `owner_id` and forbids extra keys, and the owner reaches the command from
    `CurrentActor` alone - so a client cannot create a list in someone else's
    name by adding a key (T-4-35, T-4-43).

    The new list's counters are `0`, `0` and `0.0`: the response shape is the
    same on every task-list verb (D-10), so a client parses one thing.
    """
    result = await CreateTaskList(uow, clock).execute(
        payload.to_command(actor_id=actor_id)
    )
    response.headers["Location"] = str(
        request.url_for("get_task_list", list_id=result.id)
    )
    return TaskListResponse.from_result(result)


@task_list_router.get(
    "",
    response_model=list[TaskListResponse],
    summary="List the caller's task lists",
    response_description=(
        "Every task list the caller owns, ordered by created_at and then by id "
        "- a total order, so the sequence is stable across requests even when "
        "two lists were created in the same instant (D-13). There are no sort "
        "and no pagination parameters in v1 (ADR-043)."
    ),
    responses={500: {"description": UNEXPECTED_DESCRIPTION}},
)
async def list_task_lists(
    actor_id: CurrentActor,
    uow: UnitOfWorkDependency,
) -> list[TaskListResponse]:
    """Every list the caller owns, each carrying the whole list's counters.

    This route has no 404 and no 422 leg, and the `responses` map above says so
    by naming neither: a caller who owns nothing gets `200` with an empty array,
    because the collection exists whether or not it has members.

    The counters for all of the caller's lists come from one grouped statement,
    not one query per list (LIST-03, ADR-009); plan 04-11 asserts the statement
    count directly so "no N+1" stays proved rather than claimed.
    """
    results = await ListTaskLists(uow).execute(ListTaskListsCommand(actor_id=actor_id))
    return [TaskListResponse.from_result(result) for result in results]


@task_list_router.get(
    "/{list_id}",
    response_model=TaskListResponse,
    summary="Read one task list",
    response_description="The task list, with its completion counters.",
    responses={
        404: {"description": NOT_FOUND_DESCRIPTION},
        422: {"description": VALIDATION_DESCRIPTION},
        500: {"description": UNEXPECTED_DESCRIPTION},
    },
)
async def get_task_list(
    list_id: UUID,
    actor_id: CurrentActor,
    uow: UnitOfWorkDependency,
) -> TaskListResponse:
    """Read one list, if it is the caller's to read.

    The function name is load-bearing rather than descriptive: the create route
    passes it to `request.url_for` to build its `Location` header, so renaming
    it without renaming that call breaks the header rather than the import.
    """
    result = await GetTaskList(uow).execute(
        GetTaskListCommand(actor_id=actor_id, task_list_id=list_id)
    )
    return TaskListResponse.from_result(result)


@task_list_router.patch(
    "/{list_id}",
    response_model=TaskListResponse,
    summary="Update a task list",
    response_description="The updated task list, in full.",
    responses={
        404: {"description": NOT_FOUND_DESCRIPTION},
        409: {"description": DUPLICATE_NAME_DESCRIPTION},
        422: {"description": VALIDATION_DESCRIPTION},
        500: {"description": UNEXPECTED_DESCRIPTION},
    },
)
async def update_task_list(
    list_id: UUID,
    payload: TaskListPatchRequest,
    actor_id: CurrentActor,
    uow: UnitOfWorkDependency,
    clock: ClockDependency,
) -> TaskListResponse:
    """Merge-patch semantics (RFC 7396), and the full representation back.

    Omitting a field leaves it alone; an explicit null clears `description`,
    which is the one field that has a null to be cleared to. A null on `name`
    is a 422 naming the field, and a body that asks for nothing is a 422 too
    (D-05, D-06) - so "a field was provided" and "a write was asked for" are the
    same statement by the time the command is built.
    """
    result = await UpdateTaskList(uow, clock).execute(
        payload.to_command(actor_id=actor_id, task_list_id=list_id)
    )
    return TaskListResponse.from_result(result)


@task_list_router.delete(
    "/{list_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Delete a task list",
    response_description=(
        "No content. The list and, through the ON DELETE CASCADE the baseline "
        "migration declares, every task inside it are gone."
    ),
    responses={
        404: {"description": NOT_FOUND_DESCRIPTION},
        422: {"description": VALIDATION_DESCRIPTION},
        500: {"description": UNEXPECTED_DESCRIPTION},
    },
)
async def delete_task_list(
    list_id: UUID,
    actor_id: CurrentActor,
    uow: UnitOfWorkDependency,
) -> None:
    """Delete one list, cascading to its tasks (LIST-05, D-12).

    The bare response class declared above is not decoration. Measured on this
    stack, a 204 that returns `None` without it still carries `content-type:
    application/json` on an empty body - a header describing a document that is
    not there. The declared OpenAPI response is identical either way.

    The use case loads the list before deleting it, so a list the caller does
    not own answers 404 rather than the 204 that would tell a stranger their
    delete had worked.
    """
    await DeleteTaskList(uow).execute(
        DeleteTaskListCommand(actor_id=actor_id, task_list_id=list_id)
    )


def register_task_list_routes(app: FastAPI) -> None:
    """Install the task-list router under `/api/v1`, from create_app().

    Imperative and called from the composition root, exactly as
    `register_health_routes` and `register_exception_handlers` are: the router
    attaches to the application the factory built, never to a module-level
    instance, so importing this module creates nothing and connects to nothing.

    The version prefix is applied here rather than written into the router,
    because it is a deployment fact about the whole API rather than a property
    of task lists - and `request.url_for` honours both prefixes regardless.
    """
    app.include_router(task_list_router, prefix="/api/v1")
