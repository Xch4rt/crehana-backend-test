"""`PwdlibPasswordHasher`, the Argon2id half of the credential ports.

Exactly one test below pays the real `PasswordHash.recommended()` cost - a
measured 37.2 ms to hash and 25.7 ms to verify - and it pays it on purpose,
because it is the only test that proves the configuration this application
actually ships. Every other test injects a deliberately cheap `Argon2Hasher`
through the constructor, which is the reason that constructor argument exists.
The alternative - lowering the real adapter's cost parameters when a test is
running - would leave the shipped hasher untested and, worse, would make the
cheap configuration a property of the production object.

Two claims here are worth more than they look. The first is the argument
*order*: pwdlib's own `PasswordHash.recommended()` docstring still shows
`verify(hash, password)`, stale since 0.2, and a transposed call raises
`UnknownHashError` - which this adapter catches and turns into `False`. The two
mistakes cancel into an application where every login silently fails, so the
off-loop test below records the arguments `run_sync` received and asserts their
order, rather than trusting that a green round-trip means the call is right.

The second is that the hashing really does leave the event loop. That is
asserted by recording the offload call, never by timing anything: a timing
assertion on a 25 ms operation is a flake waiting for a loaded CI runner, and
it would still pass against an implementation that blocked the loop for exactly
as long.
"""

from collections.abc import Callable
from typing import Any

import pytest
from anyio import to_thread
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

from taskmanager.domain.entities.user import User
from taskmanager.infrastructure.security.passwords import PwdlibPasswordHasher

PASSWORD = "correct horse battery staple"

# The value the Phase 4 demo seed wrote into `users.password_hash` (see
# `docker/entrypoint.sh` step 2b). A developer database still holding that row
# is the concrete reason `verify` refuses an unrecognised stored value instead
# of letting `UnknownHashError` become a 500.
DEMO_SEED_PLACEHOLDER = "!"


def a_cheap_hasher() -> PwdlibPasswordHasher:
    """The adapter over an Argon2 configuration tuned for speed, not secrecy.

    `memory_cost=8` is the floor argon2-cffi accepts at `parallelism=1`, and the
    whole point is that it is far too weak to store a real password behind. It
    never leaves this module: the adapter's default is `recommended()`, and this
    object arrives through the injection point rather than replacing it.
    """
    return PwdlibPasswordHasher(
        PasswordHash((Argon2Hasher(time_cost=1, memory_cost=8, parallelism=1),))
    )


async def test_the_shipped_configuration_round_trips_a_password() -> None:
    """The one test that pays the real Argon2id cost, and the only one that can.

    `PwdlibPasswordHasher()` with no argument is exactly what the composition
    root builds, so this is the only place the shipped parameters are exercised.
    The length assertion is not decoration either: the encoded hash measured 97
    characters, and `users.password_hash` is a `VARCHAR(512)` bound to the
    entity's own limit, so a future parameter change that overflowed the column
    would fail here rather than at the first registration.
    """
    hasher = PwdlibPasswordHasher()

    digest = await hasher.hash(PASSWORD)

    assert digest.startswith("$argon2")
    assert len(digest) <= User.PASSWORD_HASH_MAX_LENGTH
    assert await hasher.verify(PASSWORD, digest) is True
    assert await hasher.verify("wrong", digest) is False


async def test_a_hash_is_an_argon2id_encoded_string() -> None:
    """The variant marker is read off the encoding, not assumed from the name."""
    digest = await a_cheap_hasher().hash(PASSWORD)

    assert digest.startswith("$argon2id$")


async def test_hashing_the_same_password_twice_gives_two_different_hashes() -> None:
    """A per-hash salt, asserted rather than assumed.

    Without one, two accounts sharing a password would be visibly identical in
    the table - a property nobody would notice until the table leaked.
    """
    hasher = a_cheap_hasher()

    assert await hasher.hash(PASSWORD) != await hasher.hash(PASSWORD)


async def test_verify_accepts_the_password_that_produced_the_hash() -> None:
    hasher = a_cheap_hasher()

    digest = await hasher.hash(PASSWORD)

    assert await hasher.verify(PASSWORD, digest) is True


async def test_verify_rejects_a_wrong_password() -> None:
    hasher = a_cheap_hasher()

    digest = await hasher.hash(PASSWORD)

    assert await hasher.verify("not the password", digest) is False


async def test_verify_refuses_the_demo_seed_placeholder_instead_of_raising() -> None:
    """A stored value this application did not write is a refusal, not a fault.

    `PasswordHash.verify` walks its hashers, finds none that identifies `"!"`,
    and raises `UnknownHashError`. Uncaught, that is a 500 on a login attempt
    against `demo@taskmanager.local` in any developer database seeded before
    Phase 5 - a server fault reported for a credential that is simply wrong.
    """
    assert await a_cheap_hasher().verify(PASSWORD, DEMO_SEED_PLACEHOLDER) is False


async def test_verify_refuses_an_empty_stored_value() -> None:
    """The degenerate case of the same rule, and the one a NULL column becomes."""
    assert await a_cheap_hasher().verify(PASSWORD, "") is False


async def test_dummy_verify_performs_real_argon2_work() -> None:
    """D-21: the work is the whole product, so the hash it burns must be real.

    Nothing is returned - there is no answer, only cost - so the observable is
    the throwaway hash the adapter built, which must be a genuine Argon2
    encoding rather than a placeholder that would make the call instantaneous
    and the timing equalisation a fiction.
    """
    hasher = a_cheap_hasher()

    await hasher.dummy_verify(PASSWORD)

    assert hasher._dummy_hash is not None
    assert hasher._dummy_hash.startswith("$argon2id$")


async def test_the_dummy_hash_is_computed_once_per_instance() -> None:
    """Twice would double the cost of the unknown-email leg for no benefit.

    Identity, not equality: a second `hash()` call would produce a different
    encoding anyway (the salt test above), so `==` would be the weaker claim and
    `is` is the one that says the cached value was reused.
    """
    hasher = a_cheap_hasher()

    await hasher.dummy_verify(PASSWORD)
    first = hasher._dummy_hash
    await hasher.dummy_verify("a different password")

    assert first is not None
    assert hasher._dummy_hash is first


async def test_hashing_and_verifying_leave_the_event_loop_in_that_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AUTH-04, plus the transposed-argument guard, in one recording.

    The recorder delegates to the real `run_sync`, so this is the adapter's
    genuine behaviour with a tap on it rather than a stub standing in for it -
    the round trip still has to work. What the recording adds is the pair
    `(password, hashed)`, in that order: pwdlib's stale docstring shows the
    reverse, and a transposed call would raise `UnknownHashError`, which this
    adapter catches. The green round trip alone therefore cannot distinguish a
    correct call from a transposed one that always answers `False`.
    """
    offloaded: list[tuple[object, tuple[object, ...]]] = []
    run_sync = to_thread.run_sync

    async def recording(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        offloaded.append((func, args))
        return await run_sync(func, *args, **kwargs)

    monkeypatch.setattr(to_thread, "run_sync", recording)
    hasher = a_cheap_hasher()

    digest = await hasher.hash(PASSWORD)
    verified = await hasher.verify(PASSWORD, digest)

    assert verified is True
    assert [args for _, args in offloaded] == [(PASSWORD,), (PASSWORD, digest)]
