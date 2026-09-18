"""`SystemClock` is the runtime implementation of the `Clock` port (D-14).

The conformance proof below is static, exactly as in
`tests/unit/application/test_ports.py`: binding the adapter to a local annotated
with the Protocol type is accepted by mypy strict only if the structure matches,
so `make typecheck` is the real gate and the test is what makes the claim visible
in the pytest report.
"""

from datetime import timedelta

from taskmanager.application.ports.clock import Clock
from taskmanager.infrastructure.clock import SystemClock


def test_system_clock_satisfies_the_clock_port() -> None:
    clock: Clock = SystemClock()
    assert clock is not None


def test_now_returns_an_aware_utc_datetime() -> None:
    """Aware and at zero offset - a naive value fails every entity guard."""
    now = SystemClock().now()

    assert now.tzinfo is not None
    assert now.utcoffset() == timedelta(0)


def test_now_advances() -> None:
    """Consecutive readings are non-decreasing: falsifiable without flaking."""
    clock = SystemClock()

    first = clock.now()
    second = clock.now()

    assert second >= first
