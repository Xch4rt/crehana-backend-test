"""Assignment: one door with two verbs, and the flat route for finding it.

`task_lists.py`'s module docstring states the rules every handler in this
package follows - no error answered here, no transaction entered or ended here,
no domain bound re-checked here, an explicit `response_model` on every route,
and a `responses` map naming every leg - and they are not restated.

Three things are specific to this module.

**It declares two routers, and it is still one registration function.** The
assignee verbs are nested under `/task-lists`, because a task is always
addressed through the list that owns it; the discovery collection sits on the
flat `/tasks` prefix, because D-02 makes it a view across every list there is
and a nested path would have to name a list it deliberately does not have. Two
prefixes therefore mean two router objects. `register_task_routes` states the
convention that a module exposes exactly one registration function, so the two
are included by one - a reader looking for "what does this module add to the
application?" finds a single answer.

**The three operations share a tag of their own.** `/docs` groups them
together rather than scattering the two verbs among the six task routes and
leaving the discovery route alone at the bottom - assignment is one feature and
reads as one.

**The two verbs are asymmetric in what they take, on purpose.** Assigning
notifies and unassigning does not (D-07), so only one of the two handlers is
handed the notification port. Accepting a dependency a handler never uses would
be a claim about the operation that the operation cannot back up, which is the
same argument `UnassignTask`'s constructor makes one layer down.
"""

from typing import Final
from uuid import UUID

from fastapi import APIRouter, FastAPI, status

from taskmanager.application.dto.commands import (
    ListAssignedTasksCommand,
    UnassignTaskCommand,
)
from taskmanager.application.use_cases.tasks.assign import AssignTask, UnassignTask
from taskmanager.application.use_cases.tasks.list_assigned import ListAssignedTasks
from taskmanager.presentation.api.actor import CurrentActor
from taskmanager.presentation.api.dependencies import (
    ClockDependency,
    EmailNotifierDependency,
    UnitOfWorkDependency,
)
from taskmanager.presentation.api.schemas.problem import problem_response
from taskmanager.presentation.api.schemas.tasks import TaskAssigneeRequest, TaskResponse

# The two verbs of the door, nested under the list that owns the task - the
# same prefix `routers/tasks.py` declares, for the same reason.
assignee_router = APIRouter(prefix="/task-lists", tags=["assignments"])

# The discovery collection, on the flat prefix D-02 gives it. A second object
# rather than a second path on the first one: the prefix is a property of the
# router, and writing `/../tasks/assigned-to-me` into a path to escape a prefix
# would be a URL that outlives neither prefix.
discovery_router = APIRouter(prefix="/tasks", tags=["assignments"])

NOT_FOUND_DESCRIPTION: Final[str] = (
    "No such task for this caller. A task that exists but sits in another "
    "list, and a task in a list the caller does not own, both answer "
    "identically to an absent one (D-14, ADR-008)."
)
USER_NOT_FOUND_DESCRIPTION: Final[str] = (
    "No user has the requested `assignee_id`. This leg is reachable only by a "
    "caller who has already been established as the list's owner - the "
    "ownership guard runs first, deliberately - and it discloses nothing that "
    "caller could not learn anyway, because `GET /api/v1/users` lists every "
    "account to anyone who is logged in (D-08, D-13)."
)
FORBIDDEN_DESCRIPTION: Final[str] = (
    "The caller is the task's assignee, not the list's owner. An assignee may "
    "read the task and change its status, and may neither assign it, unassign "
    "it nor take it back off themselves: ASGN-01 gives assignment to the list "
    "owner. They can already see the task, so hiding it behind a 404 would "
    "contradict an answer this API has already given them (D-03, ADR-008)."
)
UNAUTHENTICATED_DESCRIPTION: Final[str] = (
    "No usable credential. A missing, malformed, badly signed or expired "
    "token, and a token naming an account that no longer exists, all produce "
    "this same body with the same message, so it discloses nothing about "
    "which half of the credential was wrong (D-11)."
)
VALIDATION_DESCRIPTION: Final[str] = (
    "The request is malformed - an unknown or missing field, an explicit null, "
    "or an identifier in the path or the body that is not a UUID."
)
UNEXPECTED_DESCRIPTION: Final[str] = (
    "An unexpected server-side failure. The body is the same problem+json "
    "document as every other error, and carries no internal detail."
)


@assignee_router.put(
    "/{list_id}/tasks/{task_id}/assignee",
    response_model=TaskResponse,
    summary="Assign a task to a user",
    response_description=(
        "The task in full, after the assignment, exactly as the status "
        "endpoint answers (D-05, ADR-048).\n\n"
        "**Sending the user who is already the assignee is a 200 no-op, not a "
        "409.** Nothing is written and no second email is sent (D-07): "
        "repeating a request that already succeeded is not a conflict, which "
        "is the same argument the status endpoint makes for a move to the "
        "state a task is already in.\n\n"
        "**Assigning a task to yourself is allowed** and notifies exactly like "
        "any other assignment - the owner gets no special case (D-08).\n\n"
        "The notification is attempted after the assignment is durable and "
        "cannot undo it: a notifier having a bad day does not turn a completed "
        "assignment into an error (NOTF-01, NOTF-03)."
    ),
    responses={
        401: problem_response(UNAUTHENTICATED_DESCRIPTION),
        403: problem_response(FORBIDDEN_DESCRIPTION),
        404: problem_response(f"{NOT_FOUND_DESCRIPTION} {USER_NOT_FOUND_DESCRIPTION}"),
        422: problem_response(VALIDATION_DESCRIPTION),
        500: problem_response(UNEXPECTED_DESCRIPTION),
    },
)
async def assign_task(
    list_id: UUID,
    task_id: UUID,
    payload: TaskAssigneeRequest,
    actor_id: CurrentActor,
    uow: UnitOfWorkDependency,
    clock: ClockDependency,
    notifier: EmailNotifierDependency,
) -> TaskResponse:
    """Hand the task to a user, on behalf of the list's owner (ASGN-01).

    The one handler in this project that takes four collaborators, and the
    fourth is the notification port. It is injected rather than constructed
    here for the reason every other port is: a test that wants to observe the
    message overrides a provider instead of patching a module.

    The path's parent segment travels into the command, so a task addressed
    under a list that does not own it is refused exactly as it is on every
    other task route (D-14). Whether the requested assignee is a real person is
    the use case's question, asked *after* the ownership guard has run - the
    order is what keeps this route from being a user-existence oracle (T-5-12).
    """
    result = await AssignTask(uow, clock, notifier).execute(
        payload.to_command(actor_id=actor_id, task_list_id=list_id, task_id=task_id)
    )
    return TaskResponse.from_result(result)


@assignee_router.delete(
    "/{list_id}/tasks/{task_id}/assignee",
    status_code=status.HTTP_200_OK,
    response_model=TaskResponse,
    summary="Take a task back off its assignee",
    response_description=(
        "The task in full, after the assignee is cleared - **200 and a body, "
        "not the 204 the other two deletes in this API answer with.** What is "
        "deleted here is a field of a resource rather than the resource "
        "itself, so the resource is still there to be returned, and returning "
        "it saves the client the re-read it would otherwise have to make "
        "(D-05).\n\n"
        "**Unassigning a task nobody holds is a 200 no-op**: nothing is "
        "written, `updated_at` does not move, and nothing is sent. "
        "Unassignment notifies no one at all (D-07)."
    ),
    responses={
        401: problem_response(UNAUTHENTICATED_DESCRIPTION),
        403: problem_response(FORBIDDEN_DESCRIPTION),
        404: problem_response(NOT_FOUND_DESCRIPTION),
        # This verb takes no body, and it still declares a 422: two path
        # segments are UUID-typed, so a malformed identifier is refused before
        # any use case runs. `routers/tasks.py`'s bodiless DELETE declares the
        # leg for exactly the same reason, and a leg the route can produce is
        # as wrong to omit as an unreachable one is to declare.
        422: problem_response(VALIDATION_DESCRIPTION),
        500: problem_response(UNEXPECTED_DESCRIPTION),
    },
)
async def unassign_task(
    list_id: UUID,
    task_id: UUID,
    actor_id: CurrentActor,
    uow: UnitOfWorkDependency,
    clock: ClockDependency,
) -> TaskResponse:
    """Clear the assignee, on behalf of the list's owner only (ASGN-01).

    No request body, and therefore no schema: there is nothing for a client to
    say beyond the path, since whoever is holding the task is who gets cleared.

    **No notification port either, and the absence is the decision.**
    Unassigning sends nothing (D-07), so a port accepted and never called would
    be a claim this route cannot back up - the asymmetry with its sibling above
    is kept visible rather than smoothed over.

    **An assignee may not unassign themselves.** They are refused with the 403
    above, which is ASGN-01's reading rather than an omission: the requirement
    gives assignment and unassignment to the list's owner, and "an assignee
    declining a task" is a rule nobody asked for.
    """
    result = await UnassignTask(uow, clock).execute(
        UnassignTaskCommand(actor_id=actor_id, task_list_id=list_id, task_id=task_id)
    )
    return TaskResponse.from_result(result)


@discovery_router.get(
    "/assigned-to-me",
    response_model=list[TaskResponse],
    summary="List the tasks assigned to the caller, across every list",
    response_description=(
        "Every task assigned to the caller, ordered by created_at and then by "
        "id - a total order, so the sequence is stable across requests. There "
        "are no filters and no pagination in v1 (ADR-043).\n\n"
        "**Each entry carries its `task_list_id`, and that is the point of the "
        "route.** An assignee who does not own the list cannot see the list at "
        "all - `GET /api/v1/task-lists/{list_id}` answers 404 for them (D-01) "
        "- so this is the only place they can learn which tasks they have "
        "been given. The `task_list_id` is what lets a client build the nested "
        "`/api/v1/task-lists/{list_id}/tasks/{task_id}` address the task is "
        "actually read and worked on through.\n\n"
        "**The answer is a bare array, not the envelope the per-list "
        "collection returns.** That envelope carries a list's completion "
        "statistics, and a completion percentage has no meaning spread across "
        "several lists: two thirds of what? The shape here matches "
        "`GET /api/v1/task-lists` instead."
    ),
    responses={
        401: problem_response(UNAUTHENTICATED_DESCRIPTION),
        500: problem_response(UNEXPECTED_DESCRIPTION),
    },
)
async def list_assigned_tasks(
    actor_id: CurrentActor,
    uow: UnitOfWorkDependency,
) -> list[TaskResponse]:
    """The caller's own workload, and nobody else's (D-02, ASGN-02).

    This route has no 404 and no 422 leg, and the `responses` map above says so
    by naming neither: there is no identifier in the path and none in a query,
    so there is nothing a client can address wrongly and nothing to refuse.

    **That absence is also the security property.** The only identifier the
    query filters on is the caller, read off the token; the command carries no
    assignee field and this signature offers no way to supply one, so the route
    cannot be pointed at another person's workload by editing a path or a query
    string (T-5-11).
    """
    results = await ListAssignedTasks(uow).execute(
        ListAssignedTasksCommand(actor_id=actor_id)
    )
    return [TaskResponse.from_result(result) for result in results]


def register_assignment_routes(app: FastAPI) -> None:
    """Install both assignment routers under `/api/v1`, from create_app().

    One function for two routers, which is the convention
    `register_task_routes` states from the other direction: a module exposes
    exactly one registration function, so the composition root's block has one
    line per module and a reader can count the modules by reading it.

    The version prefix is applied here rather than written into either router,
    for the reason `register_task_list_routes` gives.
    """
    app.include_router(assignee_router, prefix="/api/v1")
    app.include_router(discovery_router, prefix="/api/v1")
