"""A throwaway router that raises one of each error family on demand.

It lives under `tests/` rather than under `src/` for three reasons. D-10
requires that the production app never register it, and a module the
application package cannot even import is a stronger guarantee than a
convention. Keeping it outside `src/` also keeps it out of the coverage source,
so routes that exist purely to fail cannot flatter the numbers. And it stays
out of import-linter's graph - whose `root_package` is `taskmanager` - so a
test double can never break a layer contract.

Every route is declared `include_in_schema=False` as a second line of defence:
even if some future fixture included this router somewhere it should not, the
probe would still be absent from `/openapi.json`.
"""

from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from taskmanager.domain.exceptions import (
    AuthorizationError,
    InvalidStatusTransitionError,
    TaskNotFoundError,
)
from taskmanager.domain.value_objects.task_status import TaskStatus

# Fixed literals, never a freshly generated identifier: the contract tests
# assert on the exact value that comes back in the problem body.
PROBE_TASK_ID = UUID("3f1d4c9a-0000-4000-8000-000000000001")

probe_router = APIRouter()


class ProbeBody(BaseModel):
    """The smallest body that can fail in two different ways at once."""

    title: str
    count: int


@probe_router.get("/_probe/domain", include_in_schema=False)
async def probe_domain() -> dict[str, str]:
    """Raise a grandchild of `DomainError`, to prove the MRO walk reaches it."""
    raise InvalidStatusTransitionError(TaskStatus.COMPLETED, TaskStatus.PENDING)


@probe_router.get("/_probe/not-found", include_in_schema=False)
async def probe_not_found() -> dict[str, str]:
    """Raise a leaf that the status table maps only through its parent."""
    raise TaskNotFoundError(PROBE_TASK_ID)


@probe_router.get("/_probe/forbidden", include_in_schema=False)
async def probe_forbidden() -> dict[str, str]:
    """Raise the error Phase 5 will raise for a visible-but-forbidden resource."""
    raise AuthorizationError("This probe is not yours to read.")


@probe_router.post("/_probe/validation", include_in_schema=False)
async def probe_validation(body: ProbeBody, q: int) -> dict[str, str]:
    """Never reached with an invalid payload: FastAPI fails before the handler."""
    return {"title": body.title, "q": str(q)}


@probe_router.get("/_probe/unexpected", include_in_schema=False)
async def probe_unexpected() -> dict[str, str]:
    """Raise something nobody planned for, carrying a canary the leak test greps."""
    raise RuntimeError("secret internals: hunter2")


@probe_router.get("/_probe/http-error", include_in_schema=False)
async def probe_http_error() -> dict[str, str]:
    """Raise the 401 Phase 5's auth dependency will raise, headers included.

    Raising this here is legal: CLAUDE.md forbids the framework's HTTP
    exception outside the `presentation` layer of `src/`, and this module is a
    test double under `tests/` whose entire purpose is to exercise the handler
    that translates it. Nobody should "fix" it by moving it into the app.
    """
    raise StarletteHTTPException(
        status_code=401,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )
