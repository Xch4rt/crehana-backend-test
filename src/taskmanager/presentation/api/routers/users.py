"""The one user route: the directory an assignment is chosen from (ASGN-03).

`task_lists.py`'s module docstring states the rules every handler in this
package follows - no error answered here, no transaction entered or ended here,
no domain bound re-checked here, an explicit `response_model` on every route,
and a `responses` map naming every leg - and they are not restated.

Two things are specific to this module.

**The route is deliberately unscoped, and the description says so to the
client.** Any authenticated caller reads every account's address. D-13 accepted
that with its eyes open, because the brief declares no tenancy concept to scope
by and ASGN-03 asks literally for a list of users so that an assignment can name
one. `ListUsers`' docstring argues the trade-off in full and plan 05-16 owes it
an ADR; what belongs *here* is the half a client can see, which is why the
sentence is in `response_description` rather than only in a comment. Describing
this as restricted would be the one wording that is actually dangerous - it
would invite a reader to assume a bound the code does not enforce.

**One route, one handler, and no query parameters at all.** There is no
pagination and no filtering (ADR-043): a parameter with no requirement behind it
is surface that has to be documented, validated and then kept working forever.
The ordering is the repository's, and the description names it, so a client
knows the collection is stable rather than having to discover it.

The refusal descriptions are declared in this module rather than imported from
a sibling router, the rule `schemas/tasks.py` states: a shared constant makes
one endpoint's wording change another's.
"""

from typing import Final

from fastapi import APIRouter, FastAPI

from taskmanager.application.dto.commands import ListUsersCommand
from taskmanager.application.use_cases.users.list import ListUsers
from taskmanager.presentation.api.actor import CurrentActor
from taskmanager.presentation.api.dependencies import UnitOfWorkDependency
from taskmanager.presentation.api.schemas.problem import problem_response
from taskmanager.presentation.api.schemas.users import UserSummaryResponse

# The prefix is declared once, on the router, exactly as every sibling does.
user_router = APIRouter(prefix="/users", tags=["users"])

UNAUTHENTICATED_DESCRIPTION: Final[str] = (
    "No usable credential. A missing, malformed, badly signed or expired "
    "token, and a token naming an account that no longer exists, all produce "
    "this same body with the same message, so it discloses nothing about "
    "which half of the credential was wrong (D-11)."
)
UNEXPECTED_DESCRIPTION: Final[str] = (
    "An unexpected server-side failure. The body is the same problem+json "
    "document as every other error, and carries no internal detail."
)


@user_router.get(
    "",
    response_model=list[UserSummaryResponse],
    summary="List every user, so an assignee can be named",
    response_description=(
        "Every account in the system - id, full name and email address - "
        "ordered by created_at and then by id, a total order, so the sequence "
        "is stable across requests. There is no pagination and there are no "
        "filters in v1 (ADR-043).\n\n"
        "**This is an email directory readable by any authenticated caller, "
        "and that is a deliberate trade-off rather than an oversight.** It "
        "exists because ASGN-03 requires that an `assignee_id` be discoverable "
        "at all, and there is nothing here to scope it by: this brief declares "
        "no team, organisation or project membership. A product that had one "
        "would restrict this collection to it. Nothing is hidden from a caller "
        "who is logged in, so no client should treat this route as restricted."
    ),
    responses={
        401: problem_response(UNAUTHENTICATED_DESCRIPTION),
        500: problem_response(UNEXPECTED_DESCRIPTION),
    },
)
async def list_users(
    actor_id: CurrentActor,
    uow: UnitOfWorkDependency,
) -> list[UserSummaryResponse]:
    """Every account there is, for any caller who is logged in (ASGN-03, D-13).

    This route has no 404 and no 422 leg, and the `responses` map above says so
    by naming neither: there is no identifier in the path and none in a query,
    so there is nothing a client can address wrongly.

    The caller travels into the command and is not used as a filter. That is
    the whole of D-13: the field says the request was authenticated, and every
    authenticated caller gets the same answer. An implementation that quietly
    narrowed the result would be inventing a tenancy rule nobody decided, and
    would break the only route from which an `assignee_id` can be learnt.

    The published shape is three members, never the four `GET /auth/me`
    answers with: `UserSummaryResponse` is a second model for exactly that
    reason, and the stored password hash has no field to travel in anywhere.
    """
    results = await ListUsers(uow).execute(ListUsersCommand(actor_id=actor_id))
    return [UserSummaryResponse.from_result(result) for result in results]


def register_user_routes(app: FastAPI) -> None:
    """Install the user router under `/api/v1`, from create_app().

    Imperative and called from the composition root, exactly as its siblings
    are: the router attaches to the application the factory built, never to a
    module-level instance, so importing this module creates nothing and
    connects to nothing.

    The version prefix is applied here rather than written into the router, for
    the reason `register_task_list_routes` gives - it is a deployment fact about
    the whole API rather than a property of users.
    """
    app.include_router(user_router, prefix="/api/v1")
