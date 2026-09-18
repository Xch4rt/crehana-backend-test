"""The closed domain-error hierarchy. Nothing here knows that HTTP exists.

`__reduce__` is not ceremony. `Exception.__reduce__` rebuilds an instance by
calling `cls(*self.args)`, so a subclass with its own signature -
`InvalidStatusTransitionError(current, requested)` - would be rebuilt with the
*base* arguments and raise `AttributeError` during `pickle.loads` or
`copy.copy`. Delegating to `_restore` rebuilds every subclass without ever
calling a subclass `__init__`.

The rejected alternative is `__init__(self, message, **details)`, the shape
sketched in `.planning/research/ARCHITECTURE.md` Pattern 6. flake8-bugbear
refuses it with B042, and an inline suppression comment on that line - the
obvious way out, deliberately absent from this file - would silence a check
that points at the real pickling defect above, not at a style opinion.

B042 also explains why two call shapes appear below. The check compares the
number of *positional* arguments handed to `super().__init__()` with the number
of parameters the signature declares, so a leaf taking a single domain object
and forwarding a message plus a details dict is reported as a two-for-one
mismatch. Every such leaf names `details` as a keyword: the stored state is
identical, and the check keeps running instead of being suppressed.
`InvalidStatusTransitionError` is the one leaf whose two parameters already
match the two forwarded values, so it reads positionally.
"""

from typing import Any, ClassVar
from uuid import UUID

from taskmanager.domain.value_objects.task_status import TaskStatus

# Narrower than `dict[str, Any]` on purpose. A `UUID` or a `TaskStatus` object
# left in `details` would raise while the presentation layer serialises the
# problem body, so the error handler would fail on its own input and replace a
# precise business answer with an unexplained server fault - the worst failure
# mode available here. Leaf classes below therefore store `str(task_id)` and
# `current.value`, and this alias makes anything else a mypy error at the raise
# site instead of a runtime surprise.
DetailValue = str | int | float | bool | None
Details = dict[str, DetailValue]


def _restore(cls: type["DomainError"], message: str, details: Details) -> "DomainError":
    """Rebuild a DomainError without calling a subclass-specific ``__init__``."""
    error = cls.__new__(cls)
    Exception.__init__(error, message, details)
    error.message = message
    error.details = details
    return error


class DomainError(Exception):
    """Base of the closed domain-error hierarchy.

    `super().__init__(message, details)` forwards *every* parameter, which is
    what flake8-bugbear's B042 requires; the consequence is that `self.args` is
    a 2-tuple, so the inherited `__str__` would render the whole details dict
    into any log line built from `str(exc)`. Hence the explicit `__str__`.
    """

    # ClassVar is not decoration: without it `code` and `title` would be
    # instance fields, and every subclass override below a mypy error.
    code: ClassVar[str] = "domain_error"
    title: ClassVar[str] = "Domain error"

    def __init__(self, message: str, details: Details | None = None) -> None:
        super().__init__(message, details)
        self.message = message
        self.details: Details = details if details is not None else {}

    def __reduce__(self) -> tuple[Any, ...]:
        return (_restore, (type(self), self.message, self.details))

    def __str__(self) -> str:
        return self.message


class ValidationError(DomainError):
    """Raised when a supplied value breaks an invariant of the entity."""

    code: ClassVar[str] = "validation_error"
    title: ClassVar[str] = "Validation error"


class BusinessRuleViolationError(DomainError):
    """Raised when a well-formed operation is refused by a rule of the domain."""

    code: ClassVar[str] = "business_rule_violation"
    title: ClassVar[str] = "Business rule violated"


class InvalidStatusTransitionError(BusinessRuleViolationError):
    """Raised when a task is asked to move between two statuses D-01 forbids."""

    code: ClassVar[str] = "invalid_status_transition"
    title: ClassVar[str] = "Invalid status transition"

    def __init__(self, current: TaskStatus, requested: TaskStatus) -> None:
        super().__init__(
            f"A task cannot move from {current.value} to {requested.value}.",
            {"from": current.value, "to": requested.value},
        )


class NotFoundError(DomainError):
    """Raised when the addressed resource does not exist for this caller."""

    code: ClassVar[str] = "not_found"
    title: ClassVar[str] = "Resource not found"


class TaskNotFoundError(NotFoundError):
    """Raised when no task carries the requested identifier."""

    code: ClassVar[str] = "task_not_found"
    title: ClassVar[str] = "Task not found"

    def __init__(self, task_id: UUID) -> None:
        super().__init__(
            f"No task exists with identifier {task_id}.",
            details={"task_id": str(task_id)},
        )


class TaskListNotFoundError(NotFoundError):
    """Raised when no task list carries the requested identifier."""

    code: ClassVar[str] = "task_list_not_found"
    title: ClassVar[str] = "Task list not found"

    def __init__(self, task_list_id: UUID) -> None:
        super().__init__(
            f"No task list exists with identifier {task_list_id}.",
            details={"task_list_id": str(task_list_id)},
        )


class UserNotFoundError(NotFoundError):
    """Raised when no user carries the requested identifier."""

    code: ClassVar[str] = "user_not_found"
    title: ClassVar[str] = "User not found"

    def __init__(self, user_id: UUID) -> None:
        super().__init__(
            f"No user exists with identifier {user_id}.",
            details={"user_id": str(user_id)},
        )


class ConflictError(DomainError):
    """Raised when a request collides with the current state of a resource."""

    code: ClassVar[str] = "conflict"
    title: ClassVar[str] = "Conflict"


class DuplicateTaskListNameError(ConflictError):
    """Raised when an owner already has a task list under the same name."""

    code: ClassVar[str] = "duplicate_task_list_name"
    title: ClassVar[str] = "Duplicate task list name"

    def __init__(self, name: str) -> None:
        super().__init__(
            f"A task list named '{name}' already exists for this owner.",
            details={"field": "name", "name": name},
        )


class EmailAlreadyRegisteredError(ConflictError):
    """Raised when a registration reuses an address that already has an account.

    The address itself is deliberately absent from `details`: the caller already
    knows what they submitted, and keeping the value out of the response body
    and out of the logs limits the account-enumeration surface that AUTH-01's
    conflict answer already concedes.
    """

    code: ClassVar[str] = "email_already_registered"
    title: ClassVar[str] = "Email already registered"

    def __init__(self) -> None:
        super().__init__(
            "That email address is already registered.",
            details={"field": "email"},
        )


class AuthenticationError(DomainError):
    """Raised when a caller cannot be identified from the credentials given."""

    code: ClassVar[str] = "authentication_failed"
    title: ClassVar[str] = "Authentication failed"


class AuthorizationError(DomainError):
    """Raised when an identified caller may not perform this operation."""

    code: ClassVar[str] = "authorization_failed"
    title: ClassVar[str] = "Authorization failed"
