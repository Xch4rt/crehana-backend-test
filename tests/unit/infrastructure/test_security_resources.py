"""`SecurityResources`, proven the way `test_engine.py` proves its sibling.

The two containers make the same promise and are therefore tested the same way:
building one performs no I/O, so the composition root can assemble the whole
application in a unit test with no database, no network and no `.env` on disk.
For `DatabaseResources` that claim is asserted against a pool that has checked
nothing out; there is no pool here, so it is asserted directly - `socket` and
`open` are replaced with objects that refuse, and the builder is called between
them.

The annotation test is the one that would be easy to leave out and expensive to
lose. Nothing at runtime distinguishes a field annotated with a Protocol from
one annotated with the concrete adapter, and mypy would not complain either -
the adapter satisfies the port, so the narrower annotation type-checks. What it
would break is the reason the container exists: `dependencies.py` hands a
provider's caller the contract, and a test overrides it. Reading the annotations
back is the only place that decision can be pinned.
"""

import dataclasses
import socket
from dataclasses import FrozenInstanceError
from typing import Any, get_type_hints

import pytest

from taskmanager.application.ports.security import PasswordHasher, TokenService
from taskmanager.infrastructure.clock import SystemClock
from taskmanager.infrastructure.config.settings import Settings
from taskmanager.infrastructure.security.passwords import PwdlibPasswordHasher
from taskmanager.infrastructure.security.resources import (
    SecurityResources,
    create_security_resources,
)
from taskmanager.infrastructure.security.tokens import JwtTokenService

# The same unreachable DSN the sibling suites use: this container touches no
# database at all, and a DSN that could connect would hide it if it ever did.
UNREACHABLE_DATABASE_URL = "postgresql+psycopg://user:pass@127.0.0.1:1/nothing"
JWT_SECRET = "b" * 32

# A real field, named once so the immutability test cannot quietly start
# asserting about an attribute that does not exist.
DECLARED_FIELD = "token_service"


def a_settings() -> Settings:
    """Settings built without reading any `.env`, as `test_engine.py` does."""
    return Settings(
        _env_file=None,
        database_url=UNREACHABLE_DATABASE_URL,
        jwt_secret=JWT_SECRET,
    )


def test_the_fields_are_the_two_ports_in_order() -> None:
    """Annotated with the contracts, never with the adapters that satisfy them."""
    assert dataclasses.is_dataclass(SecurityResources)
    assert [f.name for f in dataclasses.fields(SecurityResources)] == [
        "password_hasher",
        "token_service",
    ]
    assert get_type_hints(SecurityResources) == {
        "password_hasher": PasswordHasher,
        "token_service": TokenService,
    }


def test_security_resources_is_frozen_and_slotted() -> None:
    """Neither half may be swapped after the application is built.

    Written through `setattr` with the name held in a constant, the convention
    every frozen-dataclass test in this project uses: a direct assignment is a
    mypy error that would have to be silenced with a `type: ignore`, and this
    project has none.
    """
    resources = create_security_resources(a_settings(), SystemClock())

    with pytest.raises(FrozenInstanceError) as excinfo:
        setattr(resources, DECLARED_FIELD, None)

    assert DECLARED_FIELD in str(excinfo.value)
    assert not hasattr(resources, "__dict__")


def test_the_builder_populates_both_halves_from_settings() -> None:
    """One call, one container, and the JWT configuration read exactly once."""
    settings = a_settings()

    resources = create_security_resources(settings, SystemClock())

    assert isinstance(resources, SecurityResources)
    assert isinstance(resources.password_hasher, PwdlibPasswordHasher)
    assert isinstance(resources.token_service, JwtTokenService)
    assert resources.token_service._secret == settings.jwt_secret
    assert resources.token_service._algorithm == settings.jwt_algorithm


def test_building_the_container_opens_no_socket_and_reads_no_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The property that keeps the composition root constructible offline.

    Falsifiable rather than decorative: both refusals below raise, so an
    adapter that grew a key fetch, a config read or a warm-up connection would
    fail here instead of turning every unit test that builds the application
    into one that needs a network.
    """

    def no_socket(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("building the security container opened a socket")

    def no_open(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("building the security container read a file")

    settings = a_settings()
    clock = SystemClock()
    monkeypatch.setattr(socket, "socket", no_socket)
    monkeypatch.setattr("builtins.open", no_open)

    resources = create_security_resources(settings, clock)

    assert isinstance(resources, SecurityResources)


def test_the_container_holds_one_hasher_per_application() -> None:
    """D-27 and RC-3: why the hasher lives here and the clock does not.

    `SystemClock` is rebuilt per request because it holds no state and costs an
    allocation. `PwdlibPasswordHasher` caches a throwaway hash that costs a
    measured 37 ms to produce, so a fresh instance per request would pay that
    on every login - the exact cost D-21 added `dummy_verify` to control.

    Two claims, not one. The reads return the same object, so the cache
    survives; and two builds return *different* objects, so nothing here is a
    module-level singleton built at import time - which is the shape
    `db/engine.py` refuses for the engine, and for the same reason.
    """
    resources = create_security_resources(a_settings(), SystemClock())

    assert resources.password_hasher is resources.password_hasher
    other = create_security_resources(a_settings(), SystemClock())
    assert other.password_hasher is not resources.password_hasher
