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
"""

from typing import Protocol
from uuid import UUID


class PasswordHasher(Protocol):
    """Turns a plaintext password into a stored hash, and checks one against it."""

    async def hash(self, password: str) -> str: ...
    async def verify(self, password: str, hashed: str) -> bool: ...


class TokenService(Protocol):
    """Issues an access token for a user id, and resolves one back to that id."""

    async def issue_access_token(self, subject: UUID) -> str: ...

    # Returns the subject or raises: a token that cannot be trusted is an
    # `AuthenticationError` from the adapter, never a `None` the caller might
    # forget to check.
    async def decode(self, token: str) -> UUID: ...
