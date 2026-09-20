"""The error body, published. One component, one media type, 69 legs.

Every other module in this package describes a body the server *parses* or a
body it *builds*. This one describes neither: `errors/problem.py` builds the
real document as a dict literal and hands it to `JSONResponse`, and nothing
ever validates an incoming request against `ProblemResponse`. It exists to be
**published** - so that `/docs` shows a reader the shape of the 409 a route
answers with, instead of a sentence saying that it answers one.

That split is the reason the model is bound to the builder by a test rather
than by an import. `tests/unit/presentation/test_problem_schema.py` calls
`problem(...)` for real, reads the bytes back, and asserts that every member
the server sends is a declared field here and arrives in the declared order.
A model that drifts from the builder is then a red test, not a lie in the
document.

**Member order is load-bearing** (D-06). Pydantic writes `properties` in
declaration order, so the six members are declared in the order
`tests/problem_details.py::MEMBERS` states the contract, with `errors` last
because the server appends it last and only when it is truthy.

**How the legs are declared - measured, because three of the four obvious
spellings publish a lie.** Executed against the pinned FastAPI 0.141.1
(07-RESEARCH.md Gap 3):

- `{"model": ProblemResponse}` publishes `application/json` with the schema.
  Wrong media type: this API never emits `application/json` for an error.
- `{"model": ..., "content": {PROBLEM_JSON: {}}}` publishes both media types,
  and the one it really serves gets an empty object - the worst of the four.
- `{"model": ..., "content": {PROBLEM_JSON: {...$ref...}}}` publishes both
  with the schema, so `application/json` becomes a documented response the
  API cannot produce.
- The no-`model` form below publishes exactly one media type, correctly.

The no-`model` form costs one thing: FastAPI registers a component only for a
`model=` key, so the `$ref` would dangle. `ProblemAwareFastAPI` in
`taskmanager.main` registers it once, which is the other half of this module.
"""

from copy import deepcopy
from typing import Any, Final

from pydantic import BaseModel, ConfigDict, Field

from taskmanager.presentation.api.errors.problem import PROBLEM_JSON

# The component name, spelled once. `PROBLEM_REF` below builds the pointer from
# it, and `main.ProblemAwareFastAPI` registers the schema under it, so the two
# cannot drift apart into a `$ref` that resolves to nothing.
PROBLEM_SCHEMA_NAME: Final[str] = "Problem"

# The `content` value every error leg carries. Never handed out directly -
# `problem_response` deep-copies it - so a consumer that mutates one leg's
# schema block cannot reach through into the other sixty-eight.
PROBLEM_REF: Final[dict[str, Any]] = {
    "schema": {"$ref": f"#/components/schemas/{PROBLEM_SCHEMA_NAME}"}
}

# What `/docs` shows beside the schema. A real 409 from `POST /task-lists`,
# copied from what the handlers actually emit rather than invented: the `type`
# URN is `urn:taskmanager:problem:{code}` (D-05), and `errors` carries the
# domain's `details` dict. No credential, no identifier and no internal path
# appears in it, because none appears in a real one either.
PROBLEM_EXAMPLE: Final[dict[str, Any]] = {
    "type": "urn:taskmanager:problem:duplicate_task_list_name",
    "title": "Task list name already used",
    "status": 409,
    "detail": "You already have a task list named 'Groceries'.",
    "instance": "/api/v1/task-lists",
    "code": "duplicate_task_list_name",
    "errors": {"name": "Groceries"},
}


class ProblemResponse(BaseModel):
    """The RFC 9457 document this API answers every refusal with.

    Published, never validated against: no route takes this as a request body
    and no handler constructs it. `errors/problem.py` is the one builder, and
    this is the one description of what that builder sends.

    Declaration order is the published order (D-06), and the published order is
    the served order - a test asserts the two against a real response rather
    than trusting the coincidence.
    """

    model_config = ConfigDict(json_schema_extra={"example": PROBLEM_EXAMPLE})

    type: str = Field(
        description=(
            "A stable URN identifying the problem kind: "
            "`urn:taskmanager:problem:{code}`. Not dereferenceable, and not "
            "meant to be - RFC 9457 requires a URI, not a URL."
        )
    )
    title: str = Field(
        description="A short, human-readable summary of the problem kind."
    )
    status: int = Field(
        description="The HTTP status code, repeated inside the body per RFC 9457."
    )
    detail: str = Field(
        description="A human-readable explanation specific to this occurrence."
    )
    instance: str = Field(
        description="The path of the request that produced this problem."
    )
    code: str = Field(
        description=(
            "The machine-readable failure identifier. This is the member a "
            "client branches on; `title` and `detail` are prose and may change."
        )
    )
    errors: dict[str, str | int | float | bool | None] | list[dict[str, str]] | None = (
        Field(
            default=None,
            description=(
                "Present only when the failure carries structured context. Two "
                "shapes occur: a flat object of domain details (for example "
                '`{"from": "completed", "to": "pending"}`), and - on a '
                "422 - a list of `{field, message, type}` entries, one per "
                "rejected field."
            ),
        )
    )


def problem_response(description: str) -> dict[str, Any]:
    """One `responses=` entry: this description, on the one media type served.

    Deliberately no `model=` key. See the module docstring: on the pinned stack
    a `model` publishes `application/json`, a media type this API never emits
    for an error, and adding a `content` block beside it publishes both. The
    component the `$ref` points at is registered by `ProblemAwareFastAPI`.

    The block is deep-copied rather than shared, so the sixty-nine legs are
    sixty-nine independent objects: FastAPI stores what it is given, and one
    mutable dict reachable from every operation is a defect waiting for the
    first piece of code that edits a schema in place.
    """
    return {
        "description": description,
        "content": {PROBLEM_JSON: deepcopy(PROBLEM_REF)},
    }
