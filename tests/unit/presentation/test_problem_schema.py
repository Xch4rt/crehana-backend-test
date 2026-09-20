"""The published error shape, bound to the one the server actually sends.

`ProblemResponse` is a description of somebody else's output: `errors/problem.py`
builds the real body as a dict literal, and nothing ever validates a request
against the model. Two descriptions of one thing drift, and the drift is silent -
a document that promises a member the server stopped sending is worse than no
document, because a client wrote a branch against it.

So the binding is made mechanically here, in three directions. The declared
member order is compared against `tests/problem_details.py::MEMBERS`, which is
where the D-06 contract is stated once. A real response is built by calling the
builder and read back out of its bytes, so the *served* order and the declared
order are compared against each other rather than both against a wish. And the
served body is validated against the model, which is what catches a type
drifting rather than a name.

The fourth test is about the leg helper and the fifth about the component it
points at: a `$ref` that resolves to nothing is the specific failure the
no-`model` spelling risks, and `ProblemAwareFastAPI` exists only to prevent it.

Deliberately NOT used: a golden copy of the JSON schema. It would pin Pydantic's
rendering of a union and the wording of every `description`, so the next
docstring improvement would be a failing test, and the thing it claims to
protect - the member set and their order - is asserted directly above.
"""

import json
from typing import Any, Final

import pytest

from taskmanager.infrastructure.config.settings import Settings
from taskmanager.main import create_app
from taskmanager.presentation.api.errors.problem import PROBLEM_JSON, problem
from taskmanager.presentation.api.schemas.problem import (
    PROBLEM_SCHEMA_NAME,
    ProblemResponse,
    problem_response,
)
from tests.conftest import DATABASE_URL, JWT_SECRET
from tests.problem_details import MEMBERS

pytestmark = pytest.mark.unit

# The extension member, last and optional. Named here rather than added to
# `MEMBERS` because `MEMBERS` is the list six integration modules assert with
# `list(body) == MEMBERS` against responses that carry no details at all.
EXTENSION_MEMBER: Final[str] = "errors"


def _built_body(errors: Any) -> dict[str, Any]:
    """A real problem document, read back out of the bytes the client gets."""
    response = problem(
        code="task_status_transition_not_allowed",
        title="Status transition not allowed",
        status=409,
        detail="A completed task cannot return to pending.",
        instance="/api/v1/task-lists/1/tasks/2/status",
        errors=errors,
    )
    assert response.media_type == PROBLEM_JSON
    # `bytes(...)` because `Response.body` is typed `bytes | memoryview[int]`
    # on the pinned stack, and only the first of those is what `loads` takes.
    decoded: dict[str, Any] = json.loads(bytes(response.body))
    return decoded


def test_the_declared_members_are_the_contract_s_members_in_order() -> None:
    """D-06's six, in order, then `errors`, and nothing else."""
    declared = list(ProblemResponse.model_fields)

    assert declared[:6] == MEMBERS
    assert declared[6:] == [EXTENSION_MEMBER]


@pytest.mark.parametrize(
    "errors",
    [
        None,
        {"from": "completed", "to": "pending"},
        [{"field": "body.name", "message": "Field required", "type": "missing"}],
    ],
    ids=["no-details", "domain-details", "validation-entries"],
)
def test_the_model_accepts_and_orders_what_the_builder_emits(errors: Any) -> None:
    """The published shape against a real body, for all three `errors` shapes.

    The order assertion is the load-bearing half: both sides are read from
    running code, so it fails when either one moves - which is the failure a
    hand-written expectation would not produce.
    """
    body = _built_body(errors)

    declared = list(ProblemResponse.model_fields)
    assert set(body) <= set(declared), set(body) - set(declared)
    assert list(body) == [name for name in declared if name in body]
    # An empty `errors` is dropped by the builder (truthiness, not `is None`),
    # so the member is present exactly when there was something to say.
    assert (EXTENSION_MEMBER in body) is bool(errors)
    # Validating the served body is what catches a *type* drifting rather than
    # a name: a `detail` published as an int would survive the two above.
    assert ProblemResponse.model_validate(body).model_dump() is not None


def test_a_leg_publishes_one_media_type_and_a_resolving_pointer() -> None:
    """`problem_response` declares problem+json and nothing else."""
    leg = problem_response("A description the route already wrote.")

    assert leg["description"] == "A description the route already wrote."
    assert list(leg["content"]) == [PROBLEM_JSON]
    assert leg["content"][PROBLEM_JSON]["schema"] == {
        "$ref": f"#/components/schemas/{PROBLEM_SCHEMA_NAME}"
    }


def test_two_legs_share_no_mutable_object() -> None:
    """Sixty-nine legs, sixty-nine objects. FastAPI stores what it is given."""
    first = problem_response("one")
    second = problem_response("two")

    first["content"][PROBLEM_JSON]["schema"]["$ref"] = "#/components/schemas/Other"

    assert second["content"][PROBLEM_JSON]["schema"] == {
        "$ref": f"#/components/schemas/{PROBLEM_SCHEMA_NAME}"
    }


def test_the_component_is_registered_once_and_stays_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The `$ref` resolves, and a second `openapi()` call does not double it.

    `super().openapi()` caches into `self.openapi_schema` and hands back the
    same object every time, so a registration that appended rather than
    `setdefault`-ing would grow the document on every call - and every test in
    this suite that reads `app.openapi()` twice would be reading something
    different the second time.
    """
    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
    monkeypatch.setenv("JWT_SECRET", JWT_SECRET)

    app = create_app(Settings(_env_file=None))

    first = app.openapi()
    assert PROBLEM_SCHEMA_NAME in first["components"]["schemas"]
    published = first["components"]["schemas"][PROBLEM_SCHEMA_NAME]
    assert list(published["properties"]) == list(ProblemResponse.model_fields)

    second = app.openapi()
    assert second["components"]["schemas"][PROBLEM_SCHEMA_NAME] == published
