"""The RFC 9457 error contract, asserted end to end against the probe router.

This suite is the proof required by roadmap success criterion 4: the single
exception-handling point behaves correctly *before* the first real router
exists. Every request below hits a throwaway route defined in `tests/probe.py`,
so nothing here depends on a feature that has not been built yet.
"""

import logging

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from taskmanager.domain.exceptions import BusinessRuleViolationError, DomainError
from tests.probe import PROBE_TASK_ID

PROBLEM_JSON = "application/problem+json"
# The full D-06 member list, in the order the contract promises.
MEMBERS = ["type", "title", "status", "detail", "instance", "code"]


async def test_domain_error_subclass_becomes_problem_json_409(
    client: AsyncClient,
) -> None:
    """A refused status transition answers 409 with the complete D-06 body."""
    response = await client.get("/_probe/domain")

    assert response.status_code == 409
    # Exactly, not `startswith`: the point is that there is no charset suffix.
    assert response.headers["content-type"] == PROBLEM_JSON

    body = response.json()

    assert list(body) == [*MEMBERS, "errors"]
    assert body["type"] == "urn:taskmanager:problem:invalid_status_transition"
    assert body["title"] == "Invalid status transition"
    assert body["status"] == 409
    assert body["instance"] == "/_probe/domain"
    assert body["code"] == "invalid_status_transition"
    assert body["errors"] == {"from": "completed", "to": "pending"}


async def test_domain_error_handler_catches_a_grandchild_through_the_mro(
    app: FastAPI, client: AsyncClient
) -> None:
    """One registration on the base class serves every descendant (D-10)."""
    from taskmanager.domain.exceptions import InvalidStatusTransitionError

    assert InvalidStatusTransitionError.__mro__[1] is BusinessRuleViolationError
    assert InvalidStatusTransitionError.__mro__[2] is DomainError
    # Only the base is registered; Starlette walks the MRO to find the handler.
    assert DomainError in app.exception_handlers
    assert InvalidStatusTransitionError not in app.exception_handlers
    assert BusinessRuleViolationError not in app.exception_handlers

    response = await client.get("/_probe/domain")

    assert response.status_code == 409
    assert response.json()["code"] == "invalid_status_transition"


async def test_not_found_error_resolves_its_status_through_its_parent(
    client: AsyncClient,
) -> None:
    """A leaf with no table entry of its own still answers 404, via NotFoundError."""
    response = await client.get("/_probe/not-found")

    assert response.status_code == 404
    assert response.headers["content-type"] == PROBLEM_JSON

    body = response.json()

    assert body["code"] == "task_not_found"
    assert body["type"] == "urn:taskmanager:problem:task_not_found"
    assert body["errors"] == {"task_id": str(PROBE_TASK_ID)}


async def test_forbidden_route_returns_authorization_error_as_problem_json_403(
    client: AsyncClient,
) -> None:
    """An authorization failure answers 403 in the same shape as every other error."""
    response = await client.get("/_probe/forbidden")

    assert response.status_code == 403
    assert response.headers["content-type"] == PROBLEM_JSON

    body = response.json()

    assert list(body) == MEMBERS
    assert body["code"] == "authorization_failed"
    assert body["title"] == "Authorization failed"


async def test_authentication_error_answers_401_with_the_mandatory_challenge(
    client: AsyncClient,
) -> None:
    """RFC 9110 15.5.2: the 401 this handler builds must carry a challenge.

    The header cannot come from the exception, the way it does for a Starlette
    `HTTPException`: a domain `AuthenticationError` has no headers. So it has to
    be added here, or every bad-token response Phase 5 produces would violate
    the spec.
    """
    response = await client.get("/_probe/unauthenticated")

    assert response.status_code == 401
    assert response.headers["content-type"] == PROBLEM_JSON
    assert response.headers["www-authenticate"] == "Bearer"

    body = response.json()

    assert list(body) == MEMBERS
    assert body["code"] == "authentication_failed"
    assert body["title"] == "Authentication failed"


async def test_request_validation_failure_is_translated_to_422(
    client: AsyncClient,
) -> None:
    """A bad query value and a bad body become one 422 with {field, message, type}."""
    response = await client.post("/_probe/validation?q=nope", json={"count": "abc"})

    assert response.status_code == 422
    assert response.headers["content-type"] == PROBLEM_JSON

    body = response.json()

    assert body["code"] == "validation_error"
    assert body["title"] == "Request validation failed"
    assert body["detail"] == "The request payload failed validation."
    assert all(set(entry) == {"field", "message", "type"} for entry in body["errors"])
    fields = {entry["field"] for entry in body["errors"]}
    assert fields == {"query.q", "body.title", "body.count"}


async def test_validation_problem_never_echoes_the_client_input(
    client: AsyncClient,
) -> None:
    """Pydantic's raw entries carry the submitted value; the response never does."""
    response = await client.post("/_probe/validation?q=nope", json={"count": "abc"})

    assert "nope" not in response.text
    assert "abc" not in response.text
    assert "input" not in response.text
    assert "ctx" not in response.text
    assert "url" not in response.text


async def test_unmapped_domain_error_answers_the_fixed_internal_error_body(
    client: AsyncClient,
) -> None:
    """A `DomainError` with no status of its own is a server fault, not a 4xx.

    `STATUS_BY_EXCEPTION[DomainError]` is 500, so the base class - and any
    future subclass registered under it without a table entry - reaches
    `handle_domain_error`. D-08 says what a 500 looks like, and that shape has
    no room for the error's own message or details.
    """
    response = await client.get("/_probe/unmapped-domain")

    assert response.status_code == 500
    assert response.headers["content-type"] == PROBLEM_JSON

    body = response.json()

    assert list(body) == MEMBERS
    assert body["code"] == "internal_error"
    assert body["title"] == "Internal server error"
    assert body["detail"] == "An unexpected error occurred"
    # Neither the message nor the details member survives the translation.
    assert "hunter3" not in response.text
    assert "should_never_be_exposed" not in response.text
    assert "domain_error" not in response.text


async def test_unmapped_domain_error_is_logged_like_any_other_server_fault(
    client: AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    """The old behaviour answered 500 and logged nothing, which is worse (D-08)."""
    with caplog.at_level(logging.ERROR):
        await client.get("/_probe/unmapped-domain")

    records = [
        record
        for record in caplog.records
        if record.name == "taskmanager.presentation.api.errors.handlers"
    ]

    assert len(records) == 1
    assert records[0].levelno == logging.ERROR
    assert records[0].exc_info is not None
    assert "hunter3" in str(records[0].exc_info[1])


async def test_unexpected_error_returns_the_fixed_internal_error_body(
    tolerant_client: AsyncClient,
) -> None:
    """Any unhandled exception answers one fixed 500 body, in every environment."""
    response = await tolerant_client.get("/_probe/unexpected")

    assert response.status_code == 500
    assert response.headers["content-type"] == PROBLEM_JSON

    body = response.json()

    assert list(body) == MEMBERS
    assert body["code"] == "internal_error"
    assert body["title"] == "Internal server error"
    assert body["detail"] == "An unexpected error occurred"
    assert body["type"] == "urn:taskmanager:problem:internal_error"


async def test_unexpected_error_leaks_no_message_or_traceback(
    tolerant_client: AsyncClient,
) -> None:
    """The probe's canary string, its class and its traceback stay server-side."""
    response = await tolerant_client.get("/_probe/unexpected")

    assert "hunter2" not in response.text
    assert "secret internals" not in response.text
    assert "Traceback" not in response.text
    assert "RuntimeError" not in response.text


async def test_unexpected_error_is_logged_with_its_traceback(
    tolerant_client: AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    """A blank 500 that logs nothing would be worse than no handler at all (D-08)."""
    with caplog.at_level(logging.ERROR):
        await tolerant_client.get("/_probe/unexpected")

    records = [
        record
        for record in caplog.records
        if record.name == "taskmanager.presentation.api.errors.handlers"
    ]

    assert len(records) == 1
    assert records[0].levelno == logging.ERROR
    assert records[0].exc_info is not None
    assert "hunter2" in str(records[0].exc_info[1])


async def test_unexpected_error_still_reaches_an_intolerant_client(
    client: AsyncClient,
) -> None:
    """Documents why `tolerant_client` exists: the 500 is re-raised by design.

    Starlette's ServerErrorMiddleware sends the handler's response and then
    re-raises, so that servers can log it and test clients can assert on it.
    The shared `client` fixture keeps that behaviour on purpose - making it
    tolerant would hide a genuine 500 in every other test in the suite.
    """
    with pytest.raises(RuntimeError):
        await client.get("/_probe/unexpected")


async def test_http_unknown_route_becomes_problem_json_404(
    client: AsyncClient,
) -> None:
    """Starlette's own 404 is translated too, so it is never a bare detail body."""
    response = await client.get("/_probe/nonexistent")

    assert response.status_code == 404
    assert response.headers["content-type"] == PROBLEM_JSON

    body = response.json()

    assert list(body) == MEMBERS
    assert body["code"] == "http_error"
    assert body["detail"] == "Not Found"
    assert body["instance"] == "/_probe/nonexistent"


async def test_http_wrong_verb_preserves_the_allow_header(client: AsyncClient) -> None:
    """A 405 keeps the Allow header the HTTP spec requires of it."""
    response = await client.post("/_probe/domain")

    assert response.status_code == 405
    assert response.headers["content-type"] == PROBLEM_JSON
    assert "GET" in response.headers["allow"]
    assert response.json()["code"] == "http_error"


async def test_http_exception_preserves_the_www_authenticate_header(
    client: AsyncClient,
) -> None:
    """A 401 keeps its challenge header, which Phase 5's auth depends on."""
    response = await client.get("/_probe/http-error")

    assert response.status_code == 401
    assert response.headers["content-type"] == PROBLEM_JSON
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["detail"] == "Not authenticated"


async def test_every_error_response_uses_the_problem_json_media_type(
    client: AsyncClient,
) -> None:
    """No error this app can produce answers with a bare {"detail": ...} body."""
    cases = [
        ("GET", "/_probe/domain"),
        ("GET", "/_probe/not-found"),
        ("GET", "/_probe/forbidden"),
        ("GET", "/_probe/unauthenticated"),
        ("GET", "/_probe/unmapped-domain"),
        ("POST", "/_probe/validation?q=nope"),
        ("GET", "/_probe/http-error"),
        ("GET", "/_probe/nonexistent"),
        ("POST", "/_probe/domain"),
    ]

    for method, path in cases:
        response = await client.request(method, path)

        assert response.status_code >= 400, path
        assert response.headers["content-type"] == PROBLEM_JSON, path

        body = response.json()

        assert list(body)[: len(MEMBERS)] == MEMBERS, path
        assert list(body) != ["detail"], path
