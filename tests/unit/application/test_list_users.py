"""ASGN-03: the directory that makes an assignee id something a client can name.

There is no per-owner view to assert here and no refusal to provoke, which is
itself the specification: `ListUsers` answers every authenticated caller with
every account, so the only things worth pinning are the order, the empty case,
and the fact that a read closes its transaction without writing to it.

The interesting assertion is the negative one. `test_the_directory_is_not_a_
per_caller_view` passes an actor who has no row at all and requires the same
full answer, because an implementation that quietly filtered - or that refused
an unknown subject - would satisfy every other test in this module while
breaking the one thing D-13 decided.
"""

import inspect
from datetime import UTC, datetime, timedelta
from uuid import UUID

from taskmanager.application.dto.commands import ListUsersCommand
from taskmanager.application.dto.results import UserResult
from taskmanager.application.use_cases.users.list import ListUsers
from taskmanager.domain.entities.user import User
from tests.unit.application.fakes import FakeUnitOfWork

# Fixed on purpose. A generated identifier or a real clock reading would make
# every assertion below unfalsifiable: the test could no longer state which
# moment, or which actor, it expects.
NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
LATER = NOW + timedelta(hours=3)
ACTOR_ID = UUID("11111111-1111-4111-8111-111111111111")
STRANGER_ID = UUID("99999999-9999-4999-8999-999999999999")
# Ordered by their hex so the `(created_at, id)` tie-break has a known answer.
A_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
B_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
C_ID = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")


def _add_user(
    unit_of_work: FakeUnitOfWork,
    user_id: UUID,
    *,
    email: str,
    created_at: datetime = NOW,
    full_name: str = "Ana Torres",
) -> None:
    """Place one account in `stored` directly, so `added` stays the use case's."""
    user = User.create(
        user_id=user_id,
        email=email,
        full_name=full_name,
        password_hash="argon2-encoded-hash",
        now=created_at,
    )
    unit_of_work.user_repository.stored[user.id] = user


def _command(*, actor_id: UUID = ACTOR_ID) -> ListUsersCommand:
    """The single construction site every test below goes through."""
    return ListUsersCommand(actor_id=actor_id)


async def test_list_users_orders_by_created_at_then_id() -> None:
    """D-25: `created_at` decides, and `id` breaks the tie it leaves.

    `C` is seeded last and created first, so insertion order is not the answer;
    `A` and `B` share an instant, which is the case a timestamp alone cannot
    order - a seed script or a fixture really does write several accounts under
    one clock reading.
    """
    unit_of_work = FakeUnitOfWork()
    _add_user(unit_of_work, A_ID, email="a@example.com", created_at=LATER)
    _add_user(unit_of_work, B_ID, email="b@example.com", created_at=LATER)
    _add_user(unit_of_work, C_ID, email="c@example.com", created_at=NOW)

    results = await ListUsers(unit_of_work).execute(_command())

    assert [result.id for result in results] == [C_ID, A_ID, B_ID]
    assert [result.email for result in results] == [
        "c@example.com",
        "a@example.com",
        "b@example.com",
    ]


async def test_the_directory_is_not_a_per_caller_view() -> None:
    """D-13 / ASGN-03: every authenticated caller sees every account.

    The actor here owns nothing and has no row of their own, and still gets the
    whole directory - which is the trade-off written down in the use case's
    docstring rather than an oversight. An implementation that scoped the answer
    to the caller, or refused an unknown subject, would break the only endpoint
    from which a client can learn an `assignee_id` at all.
    """
    unit_of_work = FakeUnitOfWork()
    _add_user(unit_of_work, A_ID, email="a@example.com")
    _add_user(unit_of_work, B_ID, email="b@example.com")

    results = await ListUsers(unit_of_work).execute(_command(actor_id=STRANGER_ID))

    assert [result.id for result in results] == [A_ID, B_ID]


async def test_an_empty_directory_is_an_empty_tuple() -> None:
    """The empty collection is an empty answer, never `None`.

    A use case returning `None` here would push an `if results is None` branch
    into every caller, and the first one to forget it would answer 500 against
    a freshly migrated database.
    """
    results = await ListUsers(FakeUnitOfWork()).execute(_command())

    assert results == ()
    assert isinstance(results, tuple)


async def test_list_users_answers_with_the_public_profile_shape() -> None:
    """`UserResult`, so the stored Argon2 hash has no field to travel in (T-5-04)."""
    unit_of_work = FakeUnitOfWork()
    _add_user(unit_of_work, A_ID, email="a@example.com", full_name="Ana Torres")

    results = await ListUsers(unit_of_work).execute(_command())

    assert len(results) == 1
    assert isinstance(results[0], UserResult)
    assert results[0].full_name == "Ana Torres"
    assert not hasattr(results[0], "password_hash")


async def test_list_users_answers_with_a_tuple_and_commits_nothing() -> None:
    """The answer is immutable, and the read transaction was closed unwritten.

    `commits == 0` alone is equally true of a transaction nobody ever closed,
    so the rollback is asserted beside it - the sibling suites' convention.
    """
    unit_of_work = FakeUnitOfWork()
    _add_user(unit_of_work, A_ID, email="a@example.com")

    results = await ListUsers(unit_of_work).execute(_command())

    assert isinstance(results, tuple)
    assert unit_of_work.commits == 0
    assert unit_of_work.rollbacks == 1


def test_list_users_asks_for_no_clock_and_no_notifier() -> None:
    """ARC-04 read back off the constructor: a read touches one port.

    A dependency accepted and never used would be a dependency this use case
    does not have, and the whole point of one class per operation is that its
    constructor states exactly what the operation touches.
    """
    parameters = list(inspect.signature(ListUsers.__init__).parameters)

    assert parameters[1:] == ["uow"]
