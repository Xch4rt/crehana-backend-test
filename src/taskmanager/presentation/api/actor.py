"""Who is calling. One dependency, one answer, and one refusal for everything.

This module **is** authentication. Until Phase 5 it was a placeholder that
answered with a fixed identifier and said so in these words; what replaced it
is the body of `get_current_actor` and nothing else. `CurrentActor` keeps its
name, its `UUID` type and its target function, which is why no router, request
schema, command or use case moved when authentication arrived (ADR-044) - the
whole point of having had a seam.

**It touches the database on every request, and that is the decision rather
than an oversight.** The earlier version of this file argued the opposite as a
load-bearing property; D-11 reverses it. A signature proves the token was
issued here and has not expired, and proves nothing about whether the account
still exists - so the subject is looked up, every time, and a missing row is
refused exactly like a forged token (T-5-15). `AuthenticateActor`'s docstring
argues the price; plan 05-13 measures it.

**No token format, no library and no signing scheme is named anywhere below.**
The decode is reachable only through the `TokenService` port, so the choice of
algorithm lives in one adapter, beside the settings that configure it, and
this layer cannot pin it by accident. A test asserts the absence rather than
trusting it.

The refusal is a `DomainError`, never the web framework's own exception class.
That is CLAUDE.md's rule for every layer below the single handling point, and
here it is also why the bearer scheme is configured not to refuse anything by
itself - see the comment on it below.
"""

from typing import Annotated
from uuid import UUID

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from taskmanager.application.dto.commands import AuthenticateActorCommand
from taskmanager.application.use_cases.auth.authenticate import AuthenticateActor
from taskmanager.domain.exceptions import AuthenticationError
from taskmanager.presentation.api.dependencies import (
    TokenServiceDependency,
    UnitOfWorkDependency,
)

# Switching the scheme's automatic error off is not a preference, and it is the
# single most consequential argument in this file. (It is named once, on the
# call below, and described rather than spelled here - the 01-03 convention
# that keeps a grep for it a real gate.)
#
# The default makes the scheme raise the web framework's own
# exception class when the header is missing or is not a bearer one. That is
# refused anywhere under `presentation/api` by
# `tests/architecture/test_routers_raise_no_http_exception.py` (ADR-051, review
# fix WR-05) - and rightly: it would produce a second error body shape beside
# the RFC 9457 one every other refusal in this API speaks. Returning `None` and
# raising the domain error below keeps one shape and one handler.
#
# The rejected alternative is reading the header by hand. It would satisfy the
# gate just as well and would lose the other half of what this object is for:
# `tokenUrl` is what puts `OAuth2PasswordBearer` into the OpenAPI document's
# security schemes, which is what makes Swagger's Authorize button exist
# (AUTH-02). The path is absolute so it stays correct if the document ever
# moves off the root.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

BearerToken = Annotated[str | None, Depends(oauth2_scheme)]


async def get_current_actor(
    token: BearerToken,
    uow: UnitOfWorkDependency,
    tokens: TokenServiceDependency,
) -> UUID:
    """The caller's identity, or the one refusal every failure mode shares.

    The unit of work and the token service arrive as **parameters**, never by
    calling their providers here. `dependencies.py::get_uow` is an ordinary
    callable and is therefore tempting to call, and the consequence is
    measured: the test harness overrides the *dependency*, so a direct call
    would walk past the override and dial the syntactically valid, entirely
    fictional DSN the harness sets - turning around 120 integration tests from
    assertions into sockets that hang.

    Taking it as a parameter also costs nothing. Sub-dependencies are cached
    per request, so this dependency and the route handler below it receive the
    very same unit of work, constructed once. This function enters the block
    and leaves it again before the handler runs, so the use case's later
    `async with` is a *re-open* rather than a re-entry - a distinction
    `SqlAlchemyUnitOfWork.__aenter__` makes explicitly and
    `test_a_unit_of_work_can_be_reopened_after_its_block_ended` pins.
    """
    if not token:
        # Both shapes the scheme can hand over for "no usable credential":
        # `None` when there is no `Authorization` header at all or when its
        # scheme is not a bearer one, and `""` when the scheme matched but the
        # parameter after it is empty. The emptiness check covers the pair;
        # an identity check against the first would let the second through to
        # the adapter.
        raise AuthenticationError()
    command = AuthenticateActorCommand(token)
    actor = await AuthenticateActor(uow, tokens).execute(command)
    return actor.id


# Declared as an annotation, never as an argument default - the B008 argument
# `health.py` L47-L54 makes in full, which this module deliberately does not
# re-litigate.
CurrentActor = Annotated[UUID, Depends(get_current_actor)]
