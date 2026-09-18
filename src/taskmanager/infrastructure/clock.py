"""The runtime adapter for `Clock`, the one port that performs no I/O.

`application/ports/clock.py` explains why that port is not `async`; this is its
production implementation, and it lives in `infrastructure` for the same reason
every other adapter does - the application layer names the capability, the outer
layer supplies it.

It returns `datetime.now(UTC)`, an aware instant. The naive stdlib alternative is
deliberately not used: `domain/validation.py::require_utc` rejects a naive value
outright, so an entity stamped by a naive clock would fail at the first
`created_at` guard rather than quietly storing a wrong offset. The failure would
be loud, but it would also be impossible to express - which is why the choice is
recorded here instead of being left to look accidental.

There is no base class and no ABC: `Clock` is a `typing.Protocol`, so
conformance is structural and mypy strict is the gate that checks it.
"""

from datetime import UTC, datetime


class SystemClock:
    """Reads the real system clock, as an aware UTC `datetime` (D-14)."""

    def now(self) -> datetime:
        return datetime.now(UTC)
