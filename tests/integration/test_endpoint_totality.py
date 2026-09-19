"""D-01/D-03, TEST-02: every published operation is driven through HTTP.

The brief asks for integration tests that exercise every endpoint against a real
database. Phase 5's permission matrix does drive all nineteen, but nothing said
so: a twentieth route could have shipped with no test at all and every gate would
still have been green. This module is the gate, and it is *observed* rather than
declared - there is no list of routes here to keep in step with the routers.

**The recorder.** `conftest.recording` wraps the application at the transport in
both HTTP fixtures and notes `(method, route.path_format)` for every request the
router managed to dispatch. `REQUESTED` is a module-level set, so it lives for
the whole session; that is sound because this suite runs in one process and under
no parallel plugin, and the module docstring of the conftest says what to
re-think if that ever changes.

**Why the resolver exists.** On the pinned stack (FastAPI 0.141.1 / Starlette
1.6.0) `include_router` leaves an opaque router object in `app.routes` (ADR-057),
and the consequence reaches into `scope`: `route.path_format` is the *router-
local* template (`/task-lists/{list_id}`) and `scope["root_path"]` is `""`, so
the `/api/v1` prefix is in neither. The recorded template is therefore matched
against the published one by unique suffix, and the resolver fails loudly if a
suffix matches two published paths rather than picking one - a future router
whose tail overlaps another's must be a red test, not a silent miscount.

**Why the check is two-sided, and only half of it is total.** Every *recorded*
operation must be published: that is meaningful on any selection, and it catches a
route that answers over HTTP but is absent from the document a client reads.
Every *published* operation must have been recorded: that can only be asserted
when the whole suite ran, so a partial selection (`-k`, `-m`, a single file, a
`--lf` rerun) skips that half. Otherwise every focused run in the project would
be red, and a gate that cries wolf on every invocation is one people learn to
pass with `-k`. A bare `pytest` is what CI and the Docker `test` stage both run,
so the total half is exercised on every verdict that counts.

**The honest property.** A route "requested" by a test that only proved a 401
still counts as requested: the router matched before the dependency refused. That
is the faithful reading of D-03 - an operation no integration test requested is a
failure - and it is exactly why plan 02's assertion-quality gate is the one that
makes each request *mean* something. This gate proves the surface was reached;
it does not, and cannot, judge what was asserted once it was.

Deliberately NOT used: an `httpx` response event hook. It sees the concrete path
(`/api/v1/task-lists/<uuid>`), never the template, so every request would record
a distinct operation and the comparison would have nothing to compare.

Deliberately NOT used: a registry of expected operations beside `MATRIX`. That is
the second home for the truth D-03 exists to avoid; the document the application
publishes is the source, and it cannot drift from itself.

One consequence, stated rather than discovered: a request to a documentation
route (`/docs`, `/openapi.json`) through either integration fixture would be
recorded and would then fail the first check, because `app.openapi()["paths"]`
does not publish those. No integration test makes one - the tests that read the
document read it from the object - and a test that wants to fetch it over HTTP
belongs in `tests/api/`, whose client is not wrapped.

This gate adds no hook to `.pre-commit-config.yaml` and no step to
`.github/workflows/ci.yml`. CLAUDE.md's two-places rule applies to a gate that
needs its own invocation; this one rides inside `pytest`, which the Docker test
stage and CI all already run.
"""

from collections.abc import Collection
from typing import Any, Final

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from tests.integration.conftest import REQUESTED

pytestmark = pytest.mark.integration

# Everything an OpenAPI path item can hold that is not an operation. The same
# filter `tests/unit/presentation/test_security_scheme.py` uses, and for the same
# reason: an allow-list of verbs would silently drop a verb this API grows later.
NON_OPERATION_KEYS: Final[frozenset[str]] = frozenset(
    {"summary", "description", "servers", "parameters", "$ref"}
)

# The pytest options that mean "not the whole suite". `keyword` is `-k`,
# `markexpr` is `-m`, `deselect` is `--deselect`, and the last three are the
# cache plugin's reruns. Read from `config.option` rather than counted from the
# collected items: a count cannot tell a focused run from a suite that shrank.
PARTIAL_SELECTION_OPTIONS: Final[tuple[str, ...]] = (
    "keyword",
    "markexpr",
    "deselect",
    "last_failed",
    "failed_first",
    "stepwise",
)


def published_operations(app: FastAPI) -> frozenset[tuple[str, str]]:
    """Every `(method, path)` the application publishes, from its own document."""
    return frozenset(
        (method, path)
        for path, item in app.openapi()["paths"].items()
        for method in item
        if method not in NON_OPERATION_KEYS
    )


def resolve_published_path(recorded: str, published: Collection[str]) -> str | None:
    """The one published path the router-local template belongs to.

    `None` when nothing matches, which the caller reports as an offender. A
    *collision* is not reported the same way: two published paths ending in the
    same template means the resolver can no longer say which operation was
    requested, so it raises rather than guessing, and the failure names both.
    """
    matches = sorted(path for path in published if path.endswith(recorded))
    if not matches:
        return None
    if len(matches) > 1:
        raise AssertionError(
            f"The router-local template {recorded!r} is a suffix of more than one "
            "published path, so a recorded request can no longer be attributed to "
            "one operation. Give one of these routes a distinct tail, or match on "
            f"a compiled path regex instead: {matches}"
        )
    return matches[0]


def _is_a_partial_selection(config: pytest.Config) -> bool:
    """Whether this invocation asked for less than the whole suite.

    The last clause is the one that catches `pytest tests/integration`: with no
    arguments pytest fills `config.args` from `testpaths`, so the two agree on a
    full run and differ on any narrower one.
    """
    if any(getattr(config.option, name, None) for name in PARTIAL_SELECTION_OPTIONS):
        return True
    testpaths: Any = config.getini("testpaths")
    return list(config.args) != list(testpaths)


def test_the_application_publishes_a_surface_to_compare_against(
    api_client: tuple[AsyncClient, FastAPI],
) -> None:
    """A document with no operations would make both checks below vacuous.

    The application is taken from the harness fixture rather than built here, so
    the document compared is the one the tests actually drove - a freshly
    constructed application could in principle publish a different surface and
    nobody would know which of the two the suite had exercised.
    """
    _, app = api_client

    assert published_operations(app)


def test_every_requested_operation_is_published(
    api_client: tuple[AsyncClient, FastAPI],
) -> None:
    """Nothing the suite reached over HTTP is missing from the document.

    Asserted on every invocation, including a focused one: this half needs only
    the requests that were made, not all of them. An operation that answers a
    request while being absent from `/openapi.json` is a client-facing defect -
    the document is the contract - and this is the only check in the project that
    would see it.
    """
    _, app = api_client
    published = published_operations(app)
    published_paths = {path for _, path in published}

    offenders = sorted(
        f"{method.upper()} {path}"
        for method, path in REQUESTED
        if (resolved := resolve_published_path(path, published_paths)) is None
        or (method, resolved) not in published
    )

    assert offenders == [], (
        "A request reached a route that the OpenAPI document does not publish "
        "(D-03). The document is the contract a client reads, so an operation "
        "that answers but is not published is a defect in the document, not in "
        f"the test. Unpublished operations: {offenders}"
    )


def test_every_published_operation_was_requested(
    api_client: tuple[AsyncClient, FastAPI],
    pytestconfig: pytest.Config,
) -> None:
    """TEST-02: every published operation was driven through HTTP in this run.

    Skipped on a partial selection, for the reason the module docstring gives.
    The `REQUESTED` non-vacuity assertion is inside the full-run branch on
    purpose: on a full run an empty recorder means the wrapper came unwired, which
    must fail here rather than leave the comparison below trivially satisfied.
    """
    if _is_a_partial_selection(pytestconfig):
        pytest.skip("partial selection - totality is asserted on a full run")

    _, app = api_client
    published = published_operations(app)
    published_paths = {path for _, path in published}

    assert REQUESTED, (
        "No request was recorded at all, so the ASGI wrapper in "
        "tests/integration/conftest.py is no longer wired into the HTTP "
        "fixtures - the check below would pass vacuously."
    )

    requested = {
        (method, resolved)
        for method, path in REQUESTED
        if (resolved := resolve_published_path(path, published_paths)) is not None
    }
    offenders = sorted(
        f"{method.upper()} {path}" for method, path in published - requested
    )

    assert offenders == [], (
        "Every endpoint must be exercised through HTTP against real PostgreSQL "
        "(TEST-02, D-03), and these published operations were never requested "
        "during this run. Add an integration test - a row in the permission "
        f"matrix counts - or stop publishing the route: {offenders}"
    )
