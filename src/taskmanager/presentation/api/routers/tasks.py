"""The six task routes, nested under the list that owns them.

`task_lists.py`'s module docstring states the rules every handler in this
package follows - no error answered here, no transaction ended or entered here,
no business limit re-checked here, an explicit `response_model` on every route -
and they are not restated.

Two things are specific to this module.

The router declares the same `/task-lists` prefix as its sibling, so the URLs
stay nested and a task is always addressed through the list it belongs to. The
tag differs, so `/docs` groups the six task operations separately from the five
task-list ones rather than presenting eleven flat entries.

Every route passes the path's parent segment into the command it builds, and
that is a security property rather than a convenience (D-14, T-4-46). The use
case compares `task.task_list_id` against it and refuses a mismatch with the
same not-found answer an absent task produces, so a task id addressed under a
list that does not own it discloses nothing. A nested path whose parent segment
never reached the use case would be an ownership check that passes while
checking nothing.
"""

from typing import Annotated, Final
from uuid import UUID

from fastapi import APIRouter, FastAPI, Query, Request, Response, status

from taskmanager.application.dto.commands import (
    DeleteTaskCommand,
    GetTaskCommand,
    ListTasksCommand,
)
from taskmanager.application.use_cases.tasks.change_task_status import ChangeTaskStatus
from taskmanager.application.use_cases.tasks.create import CreateTask
from taskmanager.application.use_cases.tasks.delete import DeleteTask
from taskmanager.application.use_cases.tasks.get import GetTask
from taskmanager.application.use_cases.tasks.list import ListTasks
from taskmanager.application.use_cases.tasks.update import UpdateTask
from taskmanager.domain.value_objects.task_priority import TaskPriority
from taskmanager.domain.value_objects.task_status import TaskStatus
from taskmanager.presentation.api.actor import CurrentActor
from taskmanager.presentation.api.dependencies import (
    ClockDependency,
    UnitOfWorkDependency,
)
from taskmanager.presentation.api.schemas.tasks import (
    TaskCollectionResponse,
    TaskCreateRequest,
    TaskPatchRequest,
    TaskResponse,
    TaskStatusChangeRequest,
)

task_router = APIRouter(prefix="/task-lists", tags=["tasks"])

NOT_FOUND_DESCRIPTION: Final[str] = (
    "No such task for this caller. A task that exists but sits in another "
    "list, and a task in a list the caller does not own, both answer "
    "identically to an absent one (D-14, ADR-008)."
)
LIST_NOT_FOUND_DESCRIPTION: Final[str] = (
    "No such task list for this caller. A list owned by someone else answers "
    "identically to an absent one (ADR-008, D-04)."
)
TRANSITION_DESCRIPTION: Final[str] = (
    "The requested move is not one the state machine allows. The problem+json "
    "body carries the refused move as `from` and `to` inside `errors`."
)
VALIDATION_DESCRIPTION: Final[str] = (
    "The request is malformed - an unknown or missing field, an explicit null "
    "on a field that has none, an empty patch body, an identifier that is not "
    "a UUID, a filter value outside the enumeration - or a value breaks a "
    "domain rule such as a length limit or a due date in the past."
)
UNEXPECTED_DESCRIPTION: Final[str] = (
    "An unexpected server-side failure. The body is the same problem+json "
    "document as every other error, and carries no internal detail."
)

# The two filters, typed by the domain's own enumerations (TASK-06). An unknown
# value is a 422 at `query.status` or `query.priority` before any use case runs,
# the value reaches SQL as a bound parameter, and `/docs` enumerates the
# accepted values - none of which a hand-written membership check would give.
#
# The status parameter is spelled with an alias because the Python name would
# otherwise shadow the `status` module this file imports for its status-code
# constants. The public contract is unchanged: the query parameter is `status`,
# and so is the `loc` of its 422.
StatusFilter = Annotated[TaskStatus | None, Query(alias="status")]
PriorityFilter = Annotated[TaskPriority | None, Query()]


@task_router.post(
    "/{list_id}/tasks",
    status_code=status.HTTP_201_CREATED,
    response_model=TaskResponse,
    summary="Create a task in a list",
    response_description=(
        "The created task, and a Location header naming its URL. It starts "
        "`pending`, which the entity decides rather than the request (TASK-01)."
    ),
    responses={
        404: {"description": LIST_NOT_FOUND_DESCRIPTION},
        422: {"description": VALIDATION_DESCRIPTION},
        500: {"description": UNEXPECTED_DESCRIPTION},
    },
)
async def create_task(
    list_id: UUID,
    payload: TaskCreateRequest,
    actor_id: CurrentActor,
    uow: UnitOfWorkDependency,
    clock: ClockDependency,
    request: Request,
    response: Response,
) -> TaskResponse:
    """Create a task inside the caller's list, and say where it now lives.

    The refusal here is shaped like a *list* that cannot be found, not like a
    task: the caller addressed a list, no task exists yet, and there is no task
    identifier the answer could be about. Its four siblings below refuse with
    the task-shaped error for the mirror-image reason.

    Neither `status` nor `assignee_id` is a field of the request body, so
    neither is a mass-assignment surface (T-4-35): the initial state belongs to
    the entity, and Phase 4 declares no assignment endpoint at all.
    """
    result = await CreateTask(uow, clock).execute(
        payload.to_command(actor_id=actor_id, task_list_id=list_id)
    )
    response.headers["Location"] = str(
        request.url_for("get_task", list_id=list_id, task_id=result.id)
    )
    return TaskResponse.from_result(result)


@task_router.get(
    "/{list_id}/tasks",
    response_model=TaskCollectionResponse,
    summary="List the tasks in a list, optionally filtered",
    response_description=(
        "The tasks, ordered by created_at and then by id - a total order, so "
        "the sequence is stable even when two tasks were created in the same "
        "instant (D-13). There are no sort and no pagination parameters in v1 "
        "(ADR-043). Each filter takes a single value and the two combine with "
        "AND; multi-value filters are deferred to v2. The three statistics in "
        "the envelope describe the whole list and do not move with the filter "
        "(D-09, TASK-07), so `items` is what the caller asked to see while the "
        "counters are what the list is."
    ),
    responses={
        404: {"description": LIST_NOT_FOUND_DESCRIPTION},
        422: {"description": VALIDATION_DESCRIPTION},
        500: {"description": UNEXPECTED_DESCRIPTION},
    },
)
async def list_tasks(
    list_id: UUID,
    actor_id: CurrentActor,
    uow: UnitOfWorkDependency,
    status_filter: StatusFilter = None,
    priority: PriorityFilter = None,
) -> TaskCollectionResponse:
    """The list's tasks, and the list's own completion counters beside them.

    A percentage that moved when a client changed a filter would be a different
    number wearing the same name, so the counters come from one aggregate over
    the whole list (ADR-009) and the filter is applied only to `items`.
    """
    result = await ListTasks(uow).execute(
        ListTasksCommand(
            actor_id=actor_id,
            task_list_id=list_id,
            status=status_filter,
            priority=priority,
        )
    )
    return TaskCollectionResponse.from_result(result)


@task_router.get(
    "/{list_id}/tasks/{task_id}",
    response_model=TaskResponse,
    summary="Read one task",
    response_description="The task, in full.",
    responses={
        404: {"description": NOT_FOUND_DESCRIPTION},
        422: {"description": VALIDATION_DESCRIPTION},
        500: {"description": UNEXPECTED_DESCRIPTION},
    },
)
async def get_task(
    list_id: UUID,
    task_id: UUID,
    actor_id: CurrentActor,
    uow: UnitOfWorkDependency,
) -> TaskResponse:
    """Read one task, addressed through the list that owns it.

    A task id requested under a list it does not belong to answers 404,
    identically to an absent task (D-14, TASK-02) - the parent segment is
    compared, never ignored.

    The function name is load-bearing rather than descriptive: the create route
    passes it to `request.url_for` to build its `Location` header.
    """
    result = await GetTask(uow).execute(
        GetTaskCommand(actor_id=actor_id, task_list_id=list_id, task_id=task_id)
    )
    return TaskResponse.from_result(result)


@task_router.patch(
    "/{list_id}/tasks/{task_id}",
    response_model=TaskResponse,
    summary="Update a task",
    response_description=(
        "The updated task, in full. `status` is not accepted here: the "
        "dedicated status endpoint is the only door onto the state machine "
        "(D-08, TASK-03), and sending the key in this body is a 422 naming it."
    ),
    responses={
        404: {"description": NOT_FOUND_DESCRIPTION},
        422: {"description": VALIDATION_DESCRIPTION},
        500: {"description": UNEXPECTED_DESCRIPTION},
    },
)
async def update_task(
    list_id: UUID,
    task_id: UUID,
    payload: TaskPatchRequest,
    actor_id: CurrentActor,
    uow: UnitOfWorkDependency,
    clock: ClockDependency,
) -> TaskResponse:
    """Merge-patch semantics (RFC 7396), minus the state machine.

    Omitting a field leaves it alone; an explicit null clears `description` or
    `due_date`, the two fields that have a null to be cleared to; a null on
    `title` or `priority` is a 422 naming the field, and a body that asks for
    nothing is a 422 too (D-05, D-06).

    A patch that does not mention `due_date` never re-checks it, so an overdue
    task can still be renamed or re-prioritised (D-07).
    """
    result = await UpdateTask(uow, clock).execute(
        payload.to_command(actor_id=actor_id, task_list_id=list_id, task_id=task_id)
    )
    return TaskResponse.from_result(result)


@task_router.delete(
    "/{list_id}/tasks/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Delete a task",
    response_description="No content. The task is gone (TASK-04).",
    responses={
        404: {"description": NOT_FOUND_DESCRIPTION},
        422: {"description": VALIDATION_DESCRIPTION},
        500: {"description": UNEXPECTED_DESCRIPTION},
    },
)
async def delete_task(
    list_id: UUID,
    task_id: UUID,
    actor_id: CurrentActor,
    uow: UnitOfWorkDependency,
) -> None:
    """Delete one task, addressed through the list that owns it.

    The bare response class declared above is what keeps the empty body free of
    a content-type header describing a document that is not there; the
    `task_lists.py` sibling explains the measurement.
    """
    await DeleteTask(uow).execute(
        DeleteTaskCommand(actor_id=actor_id, task_list_id=list_id, task_id=task_id)
    )


@task_router.patch(
    "/{list_id}/tasks/{task_id}/status",
    response_model=TaskResponse,
    summary="Change a task's status",
    response_description=(
        "The task in full, after the move. Only the transitions the state "
        "machine allows are accepted; a request for the state the task is "
        "already in is a 200 no-op that changes nothing, not an error "
        "(D-11, TASK-05)."
    ),
    responses={
        404: {"description": NOT_FOUND_DESCRIPTION},
        409: {"description": TRANSITION_DESCRIPTION},
        422: {"description": VALIDATION_DESCRIPTION},
        500: {"description": UNEXPECTED_DESCRIPTION},
    },
)
async def change_task_status(
    list_id: UUID,
    task_id: UUID,
    payload: TaskStatusChangeRequest,
    actor_id: CurrentActor,
    uow: UnitOfWorkDependency,
    clock: ClockDependency,
) -> TaskResponse:
    """The one door onto the state machine (D-11).

    A move the machine does not allow is a 409 carrying the refused `from` and
    `to` inside `errors` - a conflict with the resource's current state, not a
    defect in a well-formed payload. An unknown state never gets that far: the
    body's field is enum-typed, so it is a 422 before any use case runs.

    The path's parent segment travels into the command, so a task addressed
    under the wrong list is refused here exactly as it is on every other task
    route (D-14).
    """
    result = await ChangeTaskStatus(uow, clock).execute(
        payload.to_command(actor_id=actor_id, task_list_id=list_id, task_id=task_id)
    )
    return TaskResponse.from_result(result)


def register_task_routes(app: FastAPI) -> None:
    """Install the task router under `/api/v1`, from create_app().

    A separate registration from the task-list router's, and a separate router,
    even though the two share a URL prefix: the split is what gives `/docs` two
    groups, and it keeps each module readable in one screen.
    """
    app.include_router(task_router, prefix="/api/v1")
