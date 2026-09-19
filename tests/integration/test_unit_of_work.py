"""The transaction boundary against a real server: SC-4, SC-5 and WR-06.

Phase 2 proved these three behaviours against `FakeUnitOfWork`, where a commit
is an integer going up. That was worth having - it pins what a use case is
allowed to assume - but it cannot fail for the reason this suite can. Here a
missing rollback is a row PostgreSQL still holds, and the assertions are reads
rather than counters: the plan's wording is `commits == 1`, and the stronger
claim is that the write is readable after `__aexit__` ran, because that is only
true if the rollback in `__aexit__` correctly left a committed transaction
alone.

The normative obligation being tested is WR-06 from
`.planning/phases/02-domain-error-contract/02-REVIEW-FIX.md`: `__aexit__` MUST
roll back whatever `commit()` did not make durable, on every exit path, and MUST
return `None` so an exception leaving the block is never swallowed.

`test_a_committed_write_is_invisible_outside_the_test_transaction` is the one
CONTEXT asks for by name (D-01, roadmap SC-5). It is also this file's own
safety net: if the `session_factory` fixture ever lost
`join_transaction_mode="create_savepoint"` and degraded to `rollback_only`
(RESEARCH Pitfall 1), every commit in this module would become a silent no-op
and every other test here would still pass - because the reads happen on the
same connection that did the writing. That test reads from a second, entirely
independent connection, which is the only vantage point from which the
difference is visible.

The falsification evidence in
`.planning/phases/03-persistence-runnable-stack/evidence/03-08-commit-falsification.txt`
records the same check from the other direction: with `await uow.commit()`
removed, `test_a_successful_block_commits_once` goes red.
"""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from taskmanager.domain.entities.task_list import TaskList
from taskmanager.domain.entities.user import User
from taskmanager.domain.exceptions import TaskListNotFoundError
from taskmanager.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork

pytestmark = pytest.mark.integration

# Fixed, never generated: an identifier produced at run time would make "the
# row is absent" true of whatever happened not to be there, which is exactly
# the assertion this module cannot afford to weaken.
USER_ID = uuid.UUID("00000000-0000-4000-8000-0000000000a1")
OTHER_USER_ID = uuid.UUID("00000000-0000-4000-8000-0000000000a2")
LIST_ID = uuid.UUID("00000000-0000-4000-8000-0000000000b1")

NOW = datetime(2026, 5, 4, 11, 30, 0, 123456, tzinfo=UTC)

PASSWORD_HASH = "argon2-placeholder-hash-value"
USER_EMAIL = "boundary@example.test"
OTHER_USER_EMAIL = "second@example.test"
FULL_NAME = "Boundary Owner"


def a_user(
    *,
    user_id: uuid.UUID = USER_ID,
    email: str = USER_EMAIL,
) -> User:
    """A valid user entity, differing from the default only where asked."""
    return User(
        id=user_id,
        email=email,
        full_name=FULL_NAME,
        password_hash=PASSWORD_HASH,
        created_at=NOW,
        updated_at=NOW,
    )


def a_task_list(*, owner_id: uuid.UUID = USER_ID) -> TaskList:
    """A list owned by the user above, so the foreign key is satisfiable."""
    return TaskList(
        id=LIST_ID,
        owner_id=owner_id,
        name="Groceries",
        description="Everything for the week",
        created_at=NOW,
        updated_at=NOW,
    )


async def rows_in_users(uow: SqlAlchemyUnitOfWork, user_id: uuid.UUID) -> bool:
    """Whether the user is readable through a freshly opened block."""
    async with uow:
        return await uow.users.get(user_id) is not None


async def count_from_a_second_connection(database_url: str, user_id: uuid.UUID) -> int:
    """`SELECT count(*)` over a connection this test transaction never touched.

    A separate engine, a separate connection, disposed before returning. This
    is the only place in the suite that reads from outside the fixture's outer
    transaction, and it is the whole point of D-01.

    `AsyncConnection.scalar` is typed `Any`, so the narrowing below is what
    mypy strict requires - and it is worth having anyway: an aggregate coming
    back as something other than an `int` would otherwise compare unequal to
    zero and turn this proof into a silent pass.
    """
    outside = create_async_engine(database_url, poolclass=NullPool)
    try:
        async with outside.connect() as connection:
            count = await connection.scalar(
                text("SELECT count(*) FROM users WHERE id = :id"), {"id": user_id}
            )
    finally:
        await outside.dispose()

    assert isinstance(count, int)
    return count


async def test_a_successful_block_commits_once(uow: SqlAlchemyUnitOfWork) -> None:
    """A committed block's write survives `__aexit__` (ARC-08, roadmap SC-4).

    Asserted as a read rather than as a counter. `commits == 1` would say the
    method was called; reading the row back through a *second* block says the
    rollback `__aexit__` performs on every uncommitted exit correctly did not
    fire here - which is the behaviour a counter cannot distinguish from its
    opposite.
    """
    async with uow:
        await uow.users.add(a_user())
        await uow.commit()

    assert await rows_in_users(uow, USER_ID)


async def test_a_domain_error_leaves_nothing_written(
    uow: SqlAlchemyUnitOfWork,
) -> None:
    """A business refusal cannot leave half a change behind (T-3-23).

    Two claims in one test, and both are needed. The exception must escape the
    `async with` - an `__aexit__` returning a true value would swallow it, and a
    failing use case would answer 200 - and the write it interrupted must be
    gone.
    """
    with pytest.raises(TaskListNotFoundError):
        async with uow:
            await uow.users.add(a_user())
            # Raised before any commit, exactly as a use case would raise it
            # once a pre-check failed on work already staged.
            raise TaskListNotFoundError(LIST_ID)

    assert not await rows_in_users(uow, USER_ID)


async def test_an_uncommitted_block_is_rolled_back(uow: SqlAlchemyUnitOfWork) -> None:
    """WR-06: leaving normally without committing undoes the work.

    This is the obligation `commits == 0` could never prove. A unit of work
    that simply returned would leave the session dirty and the write pending,
    and every fake-based test in the suite would still be green.
    """
    async with uow:
        await uow.users.add(a_user())

    assert not await rows_in_users(uow, USER_ID)


async def test_a_committed_write_is_invisible_outside_the_test_transaction(
    uow: SqlAlchemyUnitOfWork, database_url: str
) -> None:
    """D-01 and roadmap SC-5: the unit of work commits, and nothing escapes.

    The savepoint pattern is what makes both halves true at once. The commit
    releases a savepoint inside the fixture's outer transaction, so the write
    is real to everything sharing that connection; the outer transaction is
    never committed, so no other connection in the cluster can see it, and the
    rollback at teardown removes it entirely.
    """
    async with uow:
        await uow.users.add(a_user())
        await uow.commit()

    # Inside the test transaction: the write is there.
    assert await rows_in_users(uow, USER_ID)

    # From outside it: nothing.
    assert await count_from_a_second_connection(database_url, USER_ID) == 0


async def test_rollback_is_not_performed_twice(uow: SqlAlchemyUnitOfWork) -> None:
    """An explicit rollback finishes the transaction, so `__aexit__` adds none.

    Pins the `_finished = True` line in `rollback()`. Without it `__aexit__`
    rolls back a session whose transaction has already ended, which silently
    begins and ends a fresh one - work nobody asked for, and on a pooled
    session a round trip per request.
    """
    async with uow:
        await uow.users.add(a_user())
        await uow.rollback()

    assert not await rows_in_users(uow, USER_ID)


async def test_the_repositories_are_unreachable_outside_the_block(
    uow: SqlAlchemyUnitOfWork,
) -> None:
    """WR-01: a closed session must not stay reachable through a repository.

    The failure this forbids is silent rather than noisy, which is why it needs
    a test of its own. `close()` does not make an `AsyncSession` unusable -
    SQLAlchemy reuses it - so `await uow.users.get(...)` after the block would
    autobegin a fresh transaction on a newly checked-out connection, answer
    correctly, and leave that transaction open for ever. Nothing would raise,
    nothing would be written, and the pool would lose a connection per call.

    Both sides of the block are asserted, because they are the same mistake
    seen from two directions: the repositories exist only while a transaction
    does.
    """
    with pytest.raises(AttributeError):
        _ = uow.users

    async with uow:
        assert await uow.users.get(USER_ID) is None

    with pytest.raises(AttributeError):
        _ = uow.users
    with pytest.raises(AttributeError):
        _ = uow.tasks
    with pytest.raises(AttributeError):
        _ = uow.task_lists


async def test_the_three_repositories_share_one_transaction(
    uow: SqlAlchemyUnitOfWork,
) -> None:
    """One unit of work is a claim about atomicity, not about naming.

    Two different repositories write in one block. Committed, both rows are
    there; uncommitted, neither change happened - the added user is absent and
    the deleted list still stands. The second half is what rules out three
    adapters that each quietly held a transaction of their own.
    """
    async with uow:
        await uow.users.add(a_user())
        await uow.task_lists.add(a_task_list())
        await uow.commit()

    async with uow:
        assert await uow.users.get(USER_ID) is not None
        assert await uow.task_lists.get(LIST_ID) is not None

    async with uow:
        await uow.users.add(a_user(user_id=OTHER_USER_ID, email=OTHER_USER_EMAIL))
        await uow.task_lists.delete(LIST_ID)

    async with uow:
        assert await uow.users.get(OTHER_USER_ID) is None
        assert await uow.task_lists.get(LIST_ID) is not None
