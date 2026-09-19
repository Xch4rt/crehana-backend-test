"""The RFC 9457 error contract, stated once, for every test that asserts it.

Seven test modules assert the media type and the six-member body D-06 fixed:
`tests/unit/presentation/test_error_contract.py`, which proves the contract
against the probe router, and the six under `tests/integration/api/`, which
assert that every real endpoint's refusals arrive in the same shape. A second
copy of either value is the one that quietly disagrees the first time the
contract changes, so there is one.

It lives here, beside `tests/probe.py`, rather than inside the module that
proves the contract, for the reason that module's own move made plain: a
constant imported *out of a test module* ties six integration modules to a test
file's location, and a tidy of the suite then breaks six imports that have
nothing to do with the tidy. A plain module under `tests/` has no tests, is
never collected, carries no marker, and can be moved only by a change that says
it is moving it.

It stays outside `src/` for the same three reasons `probe.py` does: the
application package cannot import it, it is outside the coverage source, and it
is outside import-linter's graph, whose `root_package` is `taskmanager`.
"""

from typing import Final

PROBLEM_JSON: Final[str] = "application/problem+json"

# The full D-06 member list, in the order the contract promises. Asserted with
# `list(body) == MEMBERS` rather than by membership, because the order is part
# of the promise and a set comparison would not notice it changing.
MEMBERS: Final[list[str]] = ["type", "title", "status", "detail", "instance", "code"]
