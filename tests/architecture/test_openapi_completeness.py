"""DOC-04: every refusal the document enumerates also publishes its body.

Before this gate the document was complete in five of six ways. All nineteen
operations carried a tag, a summary, a description and a success model, and all
seventy non-2xx legs were enumerated - and sixty-nine of those seventy published
nothing a client could parse against. `"409": {"description": "..."}` tells a
reader that the route refuses; it does not tell them what arrives when it does.
A client then either guesses the shape or treats every refusal as opaque, which
is the failure mode DOC-04 exists to prevent.

**The artifact under audit is `app.openapi()`, never `app.routes`.** That is
ADR-057 and ADR-086, and it is not a preference: on the pinned stack
`include_router` leaves a single opaque object in `app.routes` with no path and
no methods, so a walk over the routes finds the documentation endpoints and none
of the real ones. It is also the honest place to assert a published contract -
the document is the thing a client generates code from.

**What this gate cannot see.** It reads the document, not the bytes on the wire.
A route could publish `application/problem+json` here and serve something else,
and nothing below would notice. The other half of that pair is the integration
suite: six modules under `tests/integration/api/` assert `PROBLEM_JSON` and the
D-06 member list against real responses, and `tests/unit/presentation/
test_problem_schema.py` binds the published model to the builder that produces
those bytes. This gate is the claim; those are the observation.

**The one exemption is a leg, not a route.** `GET /health` 503 publishes
`HealthResponse` on `application/json` by design (D-08): `/health` is a status
document saying which check failed, and it is never `problem+json`. A gate
demanding problem+json there would be wrong rather than strict. `EXEMPT_LEGS`
names exactly that triple, and `test_the_health_exemption_still_earns_itself`
fails if the leg is renamed, removed or quietly turned into something else -
otherwise the hole would silently widen to cover whatever took its place.

Deliberately NOT used: pinning the leg count as an exact number. The census
moves with every route anyone adds, so an equality would be a test of the
census rather than of the property, and it would be "fixed" by editing the
number. A floor plus a per-leg property is the honest pair: the floor proves
the scan found the surface it claims to audit, and the property is what
actually has to hold.

Deliberately NOT used: `pytest.skip` in the non-vacuity guard. 06-REVIEW's
WR-06 recorded that a *skipped* totality half is worse than a failing one -
it reports green having checked nothing, and nobody reads the skip reason.
It fails.

This gate adds no hook to `.pre-commit-config.yaml` and no step to
`.github/workflows/ci.yml`. CLAUDE.md's two-places rule applies to a gate that
needs its own invocation; this one rides inside `pytest`, which the hook set,
the Docker test stage and CI all already run - the same argument
`test_coverage_configuration.py` and `test_error_contract_totality.py` make.
"""

from typing import Any, Final

import pytest

from taskmanager.infrastructure.config.settings import Settings
from taskmanager.main import create_app
from taskmanager.presentation.api.schemas.problem import (
    PROBLEM_SCHEMA_NAME,
    ProblemResponse,
)
from tests.conftest import DATABASE_URL, JWT_SECRET
from tests.problem_details import PROBLEM_JSON

pytestmark = pytest.mark.unit

# D-08: `/health` answers a status document, not a problem document. Its 503
# carries `HealthResponse` on `application/json` so that a container healthcheck
# and a human both learn *which* check failed. This is the only leg in the API
# that is allowed to publish anything but problem+json, and the test below keeps
# the exemption tied to the thing it was granted for.
EXEMPT_LEGS: Final[frozenset[tuple[str, str, str]]] = frozenset(
    {("get", "/health", "503")}
)

# The published pointer, spelled here from the component name rather than
# copied, so renaming the component cannot leave this file asserting the old
# name against a document that no longer uses it.
PROBLEM_POINTER: Final[dict[str, str]] = {
    "$ref": f"#/components/schemas/{PROBLEM_SCHEMA_NAME}"
}

# Floors, not counts. The census on the day this gate was written was 19
# operations and 70 non-2xx legs, 69 of them non-exempt; these are what the
# scan must at least have found before any of its "no offenders" results mean
# anything. A route removed below the floor is a failure worth looking at.
MINIMUM_OPERATIONS: Final[int] = 19
MINIMUM_ERROR_LEGS: Final[int] = 69

PLAIN_JSON: Final[str] = "application/json"


@pytest.fixture
def spec(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """The published document, built from the real factory and no database."""
    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
    monkeypatch.setenv("JWT_SECRET", JWT_SECRET)
    return create_app(Settings(_env_file=None)).openapi()


def _operations(spec: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    """Every operation in the document, keyed by (lowercase method, path)."""
    return {
        (method, path): operation
        for path, item in spec["paths"].items()
        for method, operation in item.items()
    }


def _error_legs(spec: dict[str, Any]) -> dict[tuple[str, str, str], dict[str, Any]]:
    """Every non-2xx response leg, keyed by (method, path, status code)."""
    return {
        (method, path, code): leg
        for (method, path), operation in _operations(spec).items()
        for code, leg in operation["responses"].items()
        if not code.startswith("2")
    }


def test_the_health_exemption_still_earns_itself(spec: dict[str, Any]) -> None:
    """The exempt leg exists, and is still the thing the exemption is for.

    An exemption is a hole in a totality rule, so it has to keep justifying
    itself. Without this, renaming `/health` would move the hole onto whatever
    triple happened to match next - or onto nothing, leaving the gate passing
    over an exemption for a route that no longer exists.
    """
    legs = _error_legs(spec)

    for exempt in EXEMPT_LEGS:
        assert exempt in legs, f"{exempt} is exempt from DOC-04 and does not exist"
        content = legs[exempt]["content"]
        assert list(content) == [PLAIN_JSON], content
        assert content[PLAIN_JSON]["schema"] == {
            "$ref": "#/components/schemas/HealthResponse"
        }


def test_every_error_leg_publishes_the_problem_document(spec: dict[str, Any]) -> None:
    """DOC-04: one media type per error leg, and it is problem+json."""
    offenders = [
        f"{method} {path} {code}"
        for (method, path, code), leg in _error_legs(spec).items()
        if (method, path, code) not in EXEMPT_LEGS
        and (
            list(leg.get("content", {})) != [PROBLEM_JSON]
            or leg["content"][PROBLEM_JSON].get("schema") != PROBLEM_POINTER
        )
    ]

    assert offenders == [], (
        "Every documented refusal must publish the body a client has to parse, "
        f"as {PROBLEM_JSON} with a $ref to {PROBLEM_SCHEMA_NAME}. Declare it "
        "with `problem_response(DESCRIPTION)` from "
        f"`presentation/api/schemas/problem.py`. Bare legs: {offenders}"
    )


def test_no_error_leg_advertises_plain_json(spec: dict[str, Any]) -> None:
    """The warning sign of a `model=` key, asserted directly.

    Three of the four obvious spellings of an error leg publish
    `application/json` - two of them *alongside* problem+json, which is why the
    test above would not always catch them on its own and why this one exists
    separately. A documented media type the API never emits is a response every
    generated client is prepared for and will never receive.
    """
    offenders = [
        f"{method} {path} {code}"
        for (method, path, code), leg in _error_legs(spec).items()
        if (method, path, code) not in EXEMPT_LEGS
        and PLAIN_JSON in leg.get("content", {})
    ]

    assert offenders == [], (
        f"No error leg may advertise {PLAIN_JSON}: this API serves "
        f"{PROBLEM_JSON} for every refusal. A `model=` key publishes the wrong "
        f"media type on the pinned stack - drop it. Offenders: {offenders}"
    )


def test_the_problem_reference_resolves(spec: dict[str, Any]) -> None:
    """Sixty-nine `$ref`s, and the component they point at.

    The no-`model` spelling is the only correct one and it is also the one
    FastAPI registers no component for, so the pointer would dangle without
    `ProblemAwareFastAPI`. A dangling `$ref` breaks every code generator while
    leaving the document looking complete to a human reading `/docs`.
    """
    schemas = spec["components"]["schemas"]

    assert PROBLEM_SCHEMA_NAME in schemas, sorted(schemas)
    assert list(schemas[PROBLEM_SCHEMA_NAME]["properties"]) == list(
        ProblemResponse.model_fields
    )


def test_every_operation_is_tagged_and_summarised(spec: dict[str, Any]) -> None:
    """A route with no tag lands in an unnamed group; one with no summary is a path."""
    offenders = [
        f"{method} {path}"
        for (method, path), operation in _operations(spec).items()
        if not operation.get("tags") or not operation.get("summary")
    ]

    assert offenders == [], (
        "Every operation needs a tag and a summary so `/docs` can group it and "
        f"name it. Missing one or both: {offenders}"
    )


def test_the_described_tags_are_exactly_the_tags_in_use(spec: dict[str, Any]) -> None:
    """Set equality both ways, because the two directions fail differently.

    A tag an operation uses and the table does not describe is a heading in
    `/docs` with no explanation - and it is what a new router introduces
    silently. A described tag no operation uses is an empty section promising a
    feature that is not there. Neither is caught by containment in one
    direction.
    """
    described = {entry["name"]: entry for entry in spec["tags"]}
    in_use = {
        tag
        for operation in _operations(spec).values()
        for tag in operation.get("tags", [])
    }

    assert set(described) == in_use, {
        "described but unused": sorted(set(described) - in_use),
        "used but undescribed": sorted(in_use - set(described)),
    }
    blank = [name for name, entry in described.items() if not entry.get("description")]
    assert blank == [], f"Every tag needs a one-sentence description. Blank: {blank}"


def test_the_scan_is_not_vacuous(spec: dict[str, Any]) -> None:
    """Fails - never skips - if the scan found less than it claims to audit.

    Every assertion above is of the form "no offenders", and every one of them
    is trivially true over an empty document. This is what stands between a
    green run and a gate that read nothing: the operations were found, the
    error legs were found, and the exemption matched something real.
    """
    operations = _operations(spec)
    legs = _error_legs(spec)
    matched = {leg for leg in legs if leg in EXEMPT_LEGS}

    assert len(operations) >= MINIMUM_OPERATIONS, sorted(operations)
    assert len(legs) - len(matched) >= MINIMUM_ERROR_LEGS, len(legs)
    assert matched == EXEMPT_LEGS, EXEMPT_LEGS - matched
