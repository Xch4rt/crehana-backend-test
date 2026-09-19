"""Who is calling. One dependency, one answer, and one place Phase 5 rewrites.

This is **not authentication**, and saying so plainly is the whole point of the
module. Phase 4 ships the task-list and task slice before any credential exists,
so every request runs as a single fixed demo user (D-01). Phase 5 replaces the
*body* of `get_current_actor` with JWT decoding and nothing else in the project
moves: no router signature, no request schema, no command and no use case, since
all of them already take the caller's identity from here and from nowhere else.

It is a module of its own rather than a third provider in `dependencies.py`, for
two reasons. The container entrypoint's demo-user seed (D-02) imports
`DEMO_USER_ID` to write the row, and importing it from `dependencies.py` would
drag the whole database stack into a five-line seed script. And when Phase 5
arrives the seam is deleted as a file rather than edited out of one, which is a
diff a reviewer can read in a second.

The identifier is a `Final` constant rather than a setting (D-03). It is not
configuration: nothing deploys differently because of it, no environment ever
wants a different value, and the constant disappears entirely in Phase 5. Adding
it to `Settings` would put a key in `.env.example` that an evaluator has to be
told to ignore, and `.env.example` therefore gains none.

The security consequence is deliberate too. The seeded row's `password_hash` is
an unverifiable placeholder - it is not an Argon2 encoded hash, so a verify call
against it can never succeed - which means this identity cannot become a live
account by accident when the login endpoint appears. The row and the seam are
deleted together.

Nothing here touches the database, and that is load-bearing rather than
incidental: it is what keeps the seed's import cheap and keeps this file
deletable on its own.
"""

from typing import Annotated, Final
from uuid import UUID

from fastapi import Depends

# A version-4 UUID with a readable tail, so a row in `psql` or an id in a log
# line is recognisable as the demo identity at a glance rather than looked up.
# The version matters: a genuine v4 cannot be mistaken for a hand-made value by
# a reader who checks, and it sorts and indexes like every other user id.
DEMO_USER_ID: Final[UUID] = UUID("00000000-0000-4000-8000-00000000de00")


def get_current_actor() -> UUID:
    """The caller's identity, which in Phase 4 is always the demo user.

    A plain `def` with no parameters: it reads no request, no header and no
    application state, because there is nothing yet to read. Phase 5 gives it
    the token dependency and the decode, and every call site stays as written.
    """
    return DEMO_USER_ID


# Declared as an annotation, never as an argument default - the B008 argument
# `health.py` L47-L54 makes in full, which this module deliberately does not
# re-litigate.
CurrentActor = Annotated[UUID, Depends(get_current_actor)]
