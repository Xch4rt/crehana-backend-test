"""The one port that is not I/O: where the current instant enters the system.

Two alternatives were rejected. The first is a bare `Callable[[], datetime]`
dependency. D-13 already fixes the call site as `clock.now()`, and a named
method reads better at the injection site - `ChangeTaskStatus(uow, clock)` says
what arrives, `ChangeTaskStatus(uow, now_fn)` does not - while leaving room for
a test double that carries extra affordances. The second is putting this port in
`taskmanager.domain`, next to the entities that consume the instant. That would
be an upward import from the domain into the application layer, which the
`layers` contract in `.importlinter` fails; the domain therefore reads no clock
at all and takes `now` as a keyword argument on every method that needs it.

This is the single port D-19 exempts from `async`, because it is the single port
that performs no I/O: returning an in-memory reading of the system clock through
a coroutine would make every call site `await` something that can never yield.
"""

from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    """Reads the current moment, as an aware UTC `datetime` (D-14)."""

    def now(self) -> datetime: ...
