"""The two credential adapters as one typed value, built once at composition.

This is `db/engine.py::DatabaseResources` applied to the security half, and it
exists for the same reason. `starlette.datastructures.State.__getattr__` is
annotated to return `Any`, so every attribute read off the application's state
object is an implicit-`Any` source that mypy strict has nothing left to check
downstream of. One container means the dependency module narrows once, in one
private helper, and every provider below it is typed by this dataclass instead
of by a second cast.

It is frozen for the same reason its sibling is: neither half may be swapped
after the application is built. A token service replaced mid-flight would
invalidate every token already issued, and a password hasher replaced after the
first login would throw away the cached work described below.

The fields are annotated with the **ports**, never with the adapters. Nothing
at runtime depends on that and mypy accepts either, because both adapters
satisfy their ports - but the narrower annotation would hand a provider's
caller the implementation instead of the contract, and it is the contract a
test overrides. This is also why no provider needs to reach for the settings
object per request (RC-3): the composition root reads `Settings` once, here,
and the dependency module keeps its property of narrowing application state in
exactly one place.

One divergence is worth stating, because it looks inconsistent beside
`get_clock`. `SystemClock` is rebuilt for every caller: it holds no state and
costs a single allocation, so a shared instance would buy nothing and add a
second place a test could forget to override. `PwdlibPasswordHasher` is the
opposite - it caches a throwaway Argon2 hash that costs a measured 37 ms to
produce, so a fresh instance per request would pay that on every login, which
is precisely the cost D-21 added `dummy_verify` to control. It therefore lives
here, beside the token service, and is built once per application (D-27).

Nothing below opens a connection, reads a file or performs any other I/O, which
is what keeps the whole application constructible in a unit test with no
network - the same promise `create_database_resources` makes, asserted in
`tests/unit/infrastructure/test_security_resources.py`. Wiring this container
into the application belongs to plan 05-10, not here.
"""

from dataclasses import dataclass

from taskmanager.application.ports.clock import Clock
from taskmanager.application.ports.security import PasswordHasher, TokenService
from taskmanager.infrastructure.config.settings import Settings
from taskmanager.infrastructure.security.passwords import PwdlibPasswordHasher
from taskmanager.infrastructure.security.tokens import JwtTokenService


@dataclass(frozen=True, slots=True)
class SecurityResources:
    """The password hasher and the token service, as one typed value."""

    password_hasher: PasswordHasher
    token_service: TokenService


def create_security_resources(settings: Settings, clock: Clock) -> SecurityResources:
    """Both adapters at once, for the composition root to hold onto.

    The clock arrives as an argument rather than being constructed here, so
    this builder stays the single place the JWT configuration is read and the
    single place it can be substituted - a test that needs a token minted in
    the past passes a frozen clock and changes nothing else.
    """
    return SecurityResources(
        password_hasher=PwdlibPasswordHasher(),
        token_service=JwtTokenService(
            secret=settings.jwt_secret,
            algorithm=settings.jwt_algorithm,
            expire_minutes=settings.jwt_expire_minutes,
            clock=clock,
        ),
    )
