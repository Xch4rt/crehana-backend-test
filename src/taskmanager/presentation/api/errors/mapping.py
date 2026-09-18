"""The one place a business failure becomes an HTTP status.

The table is keyed by *class* and resolved by walking the MRO, not by the
error's `code` string. A `code -> status` dict looks equivalent and is not: a
new leaf added in Phase 4 or 5 whose code nobody remembered to register would
silently answer 500, while a class-keyed table lets that leaf inherit its
parent's status for free and keeps the default path unreachable in practice.
The MRO walk also mirrors exactly how Starlette resolves the handler that
calls this function, so the two lookups cannot disagree.

Nothing in `taskmanager.domain` knows this file exists; that is the point of
ARC-06, and it is why the table lives in `presentation` instead of hanging a
`status` attribute off each exception class.
"""

from typing import Final

from taskmanager.domain.exceptions import (
    AuthenticationError,
    AuthorizationError,
    BusinessRuleViolationError,
    ConflictError,
    DomainError,
    InvalidStatusTransitionError,
    NotFoundError,
    ValidationError,
)

# The ONLY place in the codebase that maps a business failure to an HTTP
# status. Plain integer literals rather than `HTTPStatus` members: 422's member
# name differs across Python versions (the entity/content spelling changed),
# and an int sidesteps the question while staying perfectly readable.
#
# The eight entries are the seven families plus the base. The base entry is not
# a business answer: 500 is the signal `handle_domain_error` reads to hand the
# exception to the catch-all handler instead, so an unmapped domain error gets
# the fixed D-08 body and a logged traceback rather than a bespoke 500 built
# from its own message. The five leaf classes
# - TaskNotFoundError, TaskListNotFoundError, UserNotFoundError,
# DuplicateTaskListNameError and EmailAlreadyRegisteredError - are deliberately
# absent: each resolves through its parent by the MRO walk below, so listing
# them would be four opportunities to disagree with NotFoundError and
# ConflictError. The omission is a decision, not an oversight.
#
# A domain ValidationError is 422, not 400: the request was well-formed and
# semantically invalid, which is what 422 means. An invalid status transition
# stays 409 per D-01 and TASK-05, because it is a conflict with the current
# state of the resource rather than a defect in the payload.
STATUS_BY_EXCEPTION: Final[dict[type[DomainError], int]] = {
    DomainError: 500,
    ValidationError: 422,
    BusinessRuleViolationError: 422,
    InvalidStatusTransitionError: 409,
    NotFoundError: 404,
    ConflictError: 409,
    AuthenticationError: 401,
    AuthorizationError: 403,
}


def status_for(exc: DomainError) -> int:
    """Resolve the HTTP status by walking the MRO, as Starlette resolves handlers.

    The generator form is deliberate. The equivalent `for` loop with a trailing
    `return` leaves one statement no test can reach - every `DomainError`
    subclass's MRO contains `DomainError`, which is mapped - plus a loop-exit
    branch that never happens, and the only way to make the 100% gate pass over
    it would be a coverage suppression comment, which CLAUDE.md forbids. The
    500 default below is therefore belt and braces, not a code path.
    """
    return next(
        (
            STATUS_BY_EXCEPTION[klass]
            for klass in type(exc).__mro__
            if klass in STATUS_BY_EXCEPTION
        ),
        500,
    )
