"""The D-01 caller-identity seam, and the `Clock` provider beside it.

Two of the assertions below look unusual and are deliberate.

One reads the module's own source and asserts a phrase is still in it. The
honesty requirement of D-03 lives in prose - a reader must be told that this is
a placeholder and not a security mechanism - and prose is the one thing no type
checker or linter protects. The project already treats documentation as a
contract this way in `tests/architecture/test_no_commit_in_repositories.py` and
in `test_update_task.py`, so the form is established rather than invented here.

The other inspects the `Annotated` alias rather than calling through FastAPI.
`CurrentActor` is what every router will spell, so the thing worth pinning is
that the alias still points at *this* provider: a refactor that repointed it at
a different function would leave every router compiling, every test of
`get_current_actor` green, and the application quietly reading someone else's
answer.
"""

import inspect
from typing import Annotated, get_args, get_origin
from uuid import UUID

from taskmanager.application.ports.clock import Clock
from taskmanager.presentation.api import actor as actor_module
from taskmanager.presentation.api.actor import (
    DEMO_USER_ID,
    CurrentActor,
    get_current_actor,
)
from taskmanager.presentation.api.dependencies import get_clock

# The phrase D-03 requires the module to say about itself, in those words.
HONESTY_PHRASE = "not authentication"


def test_get_current_actor_returns_the_demo_user() -> None:
    """The one answer Phase 4 has, taken from the one constant that holds it."""
    assert get_current_actor() == DEMO_USER_ID


def test_get_current_actor_is_stable_across_calls() -> None:
    """Two requests in one process see the same actor.

    A provider that minted an identity per call would make every ownership
    check in the phase fail on the second request, and would do it in a way no
    single-call test could see.
    """
    assert get_current_actor() == get_current_actor()


def test_the_demo_user_id_is_a_version_4_uuid() -> None:
    """A real v4, not a hand-shaped string that merely looks like one.

    The seed writes this value into `users.id`, a `uuid` column shared with
    every genuinely generated user, so it has to be a well-formed member of the
    same space rather than a recognisable outlier.
    """
    assert isinstance(DEMO_USER_ID, UUID)
    assert DEMO_USER_ID.version == 4


def test_current_actor_depends_on_this_module_s_provider() -> None:
    """The alias routers will use resolves to `get_current_actor`, still.

    `get_args` on an `Annotated` alias yields the underlying type first and the
    metadata after it; the metadata here is FastAPI's `Depends` marker, whose
    `.dependency` is the callable the framework will run.
    """
    assert get_origin(CurrentActor) is Annotated

    annotated_type, marker = get_args(CurrentActor)

    assert annotated_type is UUID
    assert marker.dependency is get_current_actor


def test_the_module_says_it_is_not_authentication() -> None:
    """D-03's honesty requirement, asserted as text so an edit cannot drop it.

    Read from the source rather than from `__doc__` so that moving the sentence
    into a comment beside the function still satisfies it - the requirement is
    that a reader of the file is told, not that a particular string object
    exists at runtime.
    """
    source = inspect.getsource(actor_module)

    assert HONESTY_PHRASE in source.lower()


def test_get_clock_returns_the_clock_port() -> None:
    """Structural conformance, with mypy strict as the real gate (03-03)."""
    clock: Clock = get_clock()

    assert clock.now().tzinfo is not None


def test_get_clock_builds_a_fresh_instance_per_call() -> None:
    """Nothing is cached, so no request can be handed another's clock.

    The provider deliberately keeps no module-level instance and stores nothing
    on `app.state`; this is the assertion that says so.
    """
    assert get_clock() is not get_clock()
