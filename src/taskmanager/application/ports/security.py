"""The two credential ports: hashing a password and issuing an access token.

The rejected alternative is calling the hashing and token libraries directly
from the use cases that need them. Those two calls are the entire reason the
`application-framework-free` contract in `.importlinter` lists `jwt` and
`pwdlib` as forbidden: a `register_user` use case that imports a hashing backend
cannot be unit-tested without paying Argon2id's deliberate cost on every run,
and a `login` use case that signs its own token pins the application layer to
one algorithm. Behind these ports, Phase 5 chooses the libraries - and can
change them - without a use case being reopened.

`TokenService` is `async` even though signing an HS256 token does no I/O. D-19
makes every port async except `Clock`, and a uniform surface costs nothing here
while leaving room for an adapter that fetches a rotating key or asks an
introspection endpoint. `PasswordHasher` has the better claim to it anyway:
Argon2id is intentionally slow, so a real adapter will want to run it off the
event loop rather than block every other request for the duration.

No plaintext ever reaches the domain. `User` stores `password_hash` only, and
`verify` compares here, so nothing below this line can echo a credential.

`dummy_verify` is the one method this phase added to either port, and 05-CONTEXT
says the ports "keep their shape unless research proves a need" - so the need is
argued here rather than left to be inferred. D-12 requires a login with an
unknown email to be indistinguishable from a login with a wrong password.
Identical status codes and identical bodies are not enough: the wrong-password
leg pays Argon2id's deliberate cost (measured at 23.6 ms) while the unknown-email
leg has no stored hash to compare against and returns in well under a
millisecond, so the difference is readable off a stopwatch and the endpoint
becomes an account-enumeration oracle in time instead of in text. The
equalisation is a verify against a throwaway hash, and every way of producing
that hash *above* this line is worse than the port method:

* the application layer cannot compute it, because producing an Argon2 hash
  needs `pwdlib`, which `.importlinter`'s `application-framework-free` contract
  forbids in this layer - the same contract that put `hash` and `verify` here;
* a hard-coded encoded Argon2 string in source reads as a credential to anyone
  grepping the repository, and nothing about its file would say otherwise;
* a hash the `Login` use case derives from the injected hasher at construction
  time re-hashes on every request, because construction is per request.

So the adapter owns the throwaway hash - it is the only component allowed to make
one - and the application asks for the work through this method. D-21 is the
decision that authorised the extension.
"""

from typing import Protocol
from uuid import UUID


class PasswordHasher(Protocol):
    """Turns a plaintext password into a stored hash, and checks one against it."""

    async def hash(self, password: str) -> str: ...
    async def verify(self, password: str, hashed: str) -> bool: ...

    # D-21, for D-12: perform the same hashing work `verify` would have cost,
    # against a hash the adapter supplies, when there is no stored hash to
    # compare against. It returns `None` on purpose - there is no answer to
    # report, only work to perform - so a caller has nothing to branch on and
    # must not read a falsy return as "the password was wrong".
    async def dummy_verify(self, password: str) -> None: ...


class TokenService(Protocol):
    """Issues an access token for a user id, and resolves one back to that id."""

    async def issue_access_token(self, subject: UUID) -> str: ...

    # Returns the subject or raises: a token that cannot be trusted is an
    # `AuthenticationError` from the adapter, never a `None` the caller might
    # forget to check.
    async def decode(self, token: str) -> UUID: ...
