"""The runtime adapter for `PasswordHasher`, over pwdlib's Argon2id.

`application/ports/security.py` states the contract and argues why hashing
belongs behind a port at all; this module is its production implementation and
does not repeat either. It follows the four conventions `infrastructure/clock.py`
sets out for an adapter: no base class and no ABC - conformance is structural
and mypy strict is the gate - the port is referenced rather than restated,
configuration arrives as a constructor argument, and `Settings` is never read
here.

Two library behaviours shape the code below, and both are the kind that produce
a *quiet* wrong application rather than a loud one.

The first is the argument order. pwdlib 0.3.1's signature is
`verify(password, hash)`, but the docstring of `PasswordHash.recommended()` in
the installed source still shows the reverse - stale since 0.2. A transposed
call raises `UnknownHashError`, which is survivable exactly until someone wraps
it, at which point every login in the system fails and nothing anywhere reports
an error. This module does wrap it, so the order is written to match the port
verbatim and `tests/unit/infrastructure/test_passwords.py` asserts the pair the
thread actually received rather than trusting a green round trip.

The second is that Argon2id is deliberately slow - measured 37.2 ms to hash and
25.7 ms to verify on this machine. Under asyncio that is not a slow request, it
is a stalled *server*: the event loop cannot run any other task for the
duration. Every call below therefore goes through `anyio.to_thread.run_sync`,
which hands the work to the same threadpool and the same `CapacityLimiter`
Starlette uses for its own synchronous endpoints, so the bound on concurrent
hashing is the application's existing one rather than a second, invisible pool
(AUTH-04).
"""

import secrets

from anyio import to_thread
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

# Bytes of entropy behind the throwaway password `dummy_verify` hashes. It is
# generated rather than written down; see that method's docstring.
_DUMMY_SECRET_BYTES = 32


class PwdlibPasswordHasher:
    """`PasswordHasher` (D-19) over pwdlib's recommended Argon2id settings."""

    def __init__(self, password_hash: PasswordHash | None = None) -> None:
        """Take a configured `PasswordHash`, or build the recommended one.

        The argument is an injection point, not a tuning knob: a test that
        cannot afford 37 ms per call substitutes a cheap hasher here, and the
        object this application ships keeps `recommended()` untouched. Lowering
        the real adapter's cost parameters "for tests" would do the opposite -
        it would leave the shipped configuration unexercised and make the weak
        one a property of production.
        """
        self._hash = password_hash or PasswordHash.recommended()
        # mypy 2.x has `--local-partial-types` on by default, so the annotation
        # is required rather than inferred from a later assignment.
        self._dummy_hash: str | None = None

    async def hash(self, password: str) -> str:
        """The encoded Argon2id hash of this password, computed off the loop."""
        return await to_thread.run_sync(self._hash.hash, password)

    async def verify(self, password: str, hashed: str) -> bool:
        """Whether this password produced this stored hash.

        The arguments are forwarded in the order the port declares them, which
        is also pwdlib's real order and *not* the one its own `recommended()`
        docstring shows.

        `UnknownHashError` is caught narrowly, and nothing wider. A stored value
        that is not an Argon2 encoded hash is not a credential that failed to
        match - it is a row this application did not write, and the honest
        answer to "is this the password" is no. The case is concrete rather than
        defensive: the Phase 4 demo seed wrote `password_hash = "!"` (see
        `docker/entrypoint.sh` step 2b), so any developer database still holding
        that row would answer a login attempt with a 500 instead of a 401.
        """
        try:
            return await to_thread.run_sync(self._hash.verify, password, hashed)
        except UnknownHashError:
            return False

    async def dummy_verify(self, password: str) -> None:
        """Burn the work a `verify` would have cost, with nothing to verify.

        D-12 requires a login with an unknown email to be indistinguishable from
        one with a wrong password, and D-21 authorised this method because
        identical bodies are not enough: the wrong-password leg pays 23.6 ms of
        Argon2 and the unknown-email leg has no stored hash to compare against,
        so the difference is readable off a stopwatch. This equalises the two.

        The throwaway hash is built once per instance, lazily, and cached. Two
        alternatives were rejected:

        * hashing at import time - every process that imports this module pays
          37 ms, including every test run, for work most of them never use;
        * hard-coding the encoded Argon2 string as a literal - it would read as
          a credential to anyone grepping the repository, and nothing about its
          surroundings would say otherwise (threat T-5-03).

        The password behind it is generated from `secrets` rather than written
        here for the same reason the second alternative was rejected: there is
        then no string in this file that looks like one.

        Nothing is returned, deliberately. There is no answer to report, only
        work to perform, so no caller can read a falsy result as "the password
        was wrong".
        """
        if self._dummy_hash is None:
            self._dummy_hash = await self.hash(
                secrets.token_urlsafe(_DUMMY_SECRET_BYTES)
            )
        await self.verify(password, self._dummy_hash)
