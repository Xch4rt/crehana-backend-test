"""Unit tests for the closed domain-error hierarchy."""

import copy
import json
import pickle
import re
from collections.abc import Iterator
from uuid import UUID

from taskmanager.domain.exceptions import (
    AuthenticationError,
    AuthorizationError,
    BusinessRuleViolationError,
    ConflictError,
    DomainError,
    DuplicateTaskListNameError,
    EmailAlreadyRegisteredError,
    InvalidStatusTransitionError,
    NotFoundError,
    TaskListNotFoundError,
    TaskNotFoundError,
    UserNotFoundError,
    ValidationError,
)
from taskmanager.domain.value_objects.task_status import TaskStatus

# The living documentation of the taxonomy. A new error class added without a
# line here - and therefore without a status in presentation/api/errors/
# mapping.py - fails this test, instead of reaching the client as an unmapped
# 500 that nobody notices until an evaluator clicks the endpoint.
EXPECTED_SUBCLASS_NAMES = frozenset(
    {
        "ValidationError",
        "BusinessRuleViolationError",
        "InvalidStatusTransitionError",
        "NotFoundError",
        "TaskNotFoundError",
        "TaskListNotFoundError",
        "UserNotFoundError",
        "ConflictError",
        "DuplicateTaskListNameError",
        "EmailAlreadyRegisteredError",
        "AuthenticationError",
        "AuthorizationError",
    }
)

# Fixed literals rather than a freshly generated identifier or a clock reading:
# a failing assertion has to be reproducible from this file alone, and a value
# that differs on every run cannot be quoted in a bug report.
SAMPLE_TASK_ID = UUID("11111111-1111-1111-1111-111111111111")
SAMPLE_TASK_LIST_ID = UUID("22222222-2222-2222-2222-222222222222")
SAMPLE_USER_ID = UUID("33333333-3333-3333-3333-333333333333")
SAMPLE_LIST_NAME = "Groceries"

# One instance of every class in the hierarchy, base included: the code, title
# and JSON-safety claims below are made about the taxonomy as a whole, not about
# whichever class a reader happened to think of.
SAMPLE_ERRORS: tuple[DomainError, ...] = (
    DomainError("A domain rule was broken."),
    ValidationError("The title cannot be blank."),
    BusinessRuleViolationError("A task list cannot be shared with its owner."),
    InvalidStatusTransitionError(TaskStatus.COMPLETED, TaskStatus.PENDING),
    NotFoundError("The requested resource does not exist."),
    TaskNotFoundError(SAMPLE_TASK_ID),
    TaskListNotFoundError(SAMPLE_TASK_LIST_ID),
    UserNotFoundError(SAMPLE_USER_ID),
    ConflictError("The resource is in a conflicting state."),
    DuplicateTaskListNameError(SAMPLE_LIST_NAME),
    EmailAlreadyRegisteredError(),
    AuthenticationError("The supplied credentials are invalid."),
    AuthorizationError("The task list belongs to another user."),
)

CODE_PATTERN = re.compile(r"^[a-z][a-z_]*$")

JSON_SAFE_TYPES = (str, int, float, bool, type(None))


def _walk_subclasses(cls: type[DomainError]) -> Iterator[type[DomainError]]:
    """Yield every descendant of `cls`, depth first."""
    for subclass in cls.__subclasses__():
        yield subclass
        yield from _walk_subclasses(subclass)


def test_hierarchy_is_closed() -> None:
    """The recursive walk finds exactly the twelve documented subclasses."""
    found = {subclass.__name__ for subclass in _walk_subclasses(DomainError)}

    # Asserted before the set comparison: an empty walk would otherwise have to
    # be caught by an expected set that is itself empty, and this test exists to
    # make that impossible.
    assert len(found) == 12
    assert found == EXPECTED_SUBCLASS_NAMES


def test_domain_error_survives_pickle_and_copy() -> None:
    """__str__, __reduce__ and _restore keep a leaf error whole through both."""
    error = InvalidStatusTransitionError(TaskStatus.COMPLETED, TaskStatus.PENDING)

    restored = pickle.loads(pickle.dumps(error))

    assert str(error) == error.message
    assert isinstance(restored, InvalidStatusTransitionError)
    assert restored.details == error.details
    assert copy.copy(error).details == error.details
    assert copy.deepcopy(error).details == error.details


def test_every_error_carries_a_stable_code_and_title() -> None:
    """Every class names itself with a distinct lower_snake_case code."""
    codes = [error.code for error in SAMPLE_ERRORS]

    assert len(codes) == 13
    assert len(set(codes)) == 13
    for error in SAMPLE_ERRORS:
        assert CODE_PATTERN.match(error.code), error.code
        assert error.title


def test_every_error_details_payload_is_json_serialisable() -> None:
    """No details value can make the error handler itself raise a 500."""
    for error in SAMPLE_ERRORS:
        assert json.dumps(error.details)
        for key, value in error.details.items():
            assert isinstance(key, str)
            assert isinstance(value, JSON_SAFE_TYPES), error.code


def test_invalid_status_transition_details_name_the_transition() -> None:
    """D-01 travels as structured from/to, not as a sentence to be parsed."""
    error = InvalidStatusTransitionError(TaskStatus.COMPLETED, TaskStatus.PENDING)

    assert isinstance(error, BusinessRuleViolationError)
    assert isinstance(error, DomainError)
    assert error.details == {"from": "completed", "to": "pending"}


def test_not_found_errors_carry_a_stringified_identifier() -> None:
    """Each not-found leaf reports its own key, holding a str and not a UUID."""
    assert TaskNotFoundError(SAMPLE_TASK_ID).details == {"task_id": str(SAMPLE_TASK_ID)}
    assert TaskListNotFoundError(SAMPLE_TASK_LIST_ID).details == {
        "task_list_id": str(SAMPLE_TASK_LIST_ID)
    }
    assert UserNotFoundError(SAMPLE_USER_ID).details == {"user_id": str(SAMPLE_USER_ID)}


def test_email_already_registered_error_does_not_echo_the_address() -> None:
    """The conflict names the field; the submitted address never leaves."""
    error = EmailAlreadyRegisteredError()

    assert error.details == {"field": "email"}
    assert "@" not in json.dumps(error.details)


def test_domain_error_defaults_to_an_empty_details_dict() -> None:
    """details is a dict even when the caller passes none, never None."""
    assert DomainError("boom").details == {}
    assert DomainError("boom", {"field": "title"}).details == {"field": "title"}
