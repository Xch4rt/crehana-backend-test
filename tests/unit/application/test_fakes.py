"""One behaviour of the in-memory double, pinned to a database rule.

`FakeTaskListRepository.exists_with_name` is what every Phase 4 use-case test
will run LIST-06's duplicate-name pre-check against, and the only thing that
makes those tests meaningful is that the fake refuses exactly what
`uq_task_lists_owner_id_name` refuses. It drifted once already: the fake folded
case while D-12 specifies a plain `UNIQUE (owner_id, name)`, so a use case could
have been proven correct against a constraint PostgreSQL will never enforce.

The rejected alternative is trusting the integration tests to catch it. They
would - eventually, in a later phase, as a confusing 500 from a duplicate insert
the use case believed it had already excluded. This file fails instead, in
milliseconds, at the line that would have to change.
"""

from datetime import UTC, datetime
from uuid import UUID

from taskmanager.domain.entities.task_list import TaskList
from tests.unit.application.fakes import FakeTaskListRepository

# Fixed literals, never uuid4()/now(): an assertion about a lookup key must be
# reproducible from the source alone.
NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
OWNER_ID = UUID("11111111-1111-4111-8111-111111111111")
OTHER_OWNER_ID = UUID("33333333-3333-4333-8333-333333333333")
TASK_LIST_ID = UUID("22222222-2222-4222-8222-222222222222")


def _stored_list(*, owner_id: UUID, name: str) -> TaskList:
    """A list as the repository would hold it, built through the entity."""
    return TaskList.create(
        task_list_id=TASK_LIST_ID,
        owner_id=owner_id,
        name=name,
        now=NOW,
    )


async def test_exists_with_name_matches_the_case_sensitive_unique_constraint() -> None:
    """The fake refuses exactly what `UNIQUE (owner_id, name)` refuses (D-12).

    `Groceries` collides with itself and with a padded spelling of itself - the
    entity strips on construction, so the argument is stripped too - but not
    with `groceries`, which the database would store as a second row.
    """
    repository = FakeTaskListRepository()
    await repository.add(_stored_list(owner_id=OWNER_ID, name="Groceries"))

    assert await repository.exists_with_name(OWNER_ID, "Groceries") is True
    assert await repository.exists_with_name(OWNER_ID, "  Groceries  ") is True
    assert await repository.exists_with_name(OWNER_ID, "groceries") is False


async def test_exists_with_name_is_scoped_to_one_owner() -> None:
    """The unique key leads with `owner_id`, so namespaces cannot collide.

    Two owners may each keep a list called `Groceries`; a check that ignored the
    owner would let one user's names block another's.
    """
    repository = FakeTaskListRepository()
    await repository.add(_stored_list(owner_id=OWNER_ID, name="Groceries"))

    assert await repository.exists_with_name(OTHER_OWNER_ID, "Groceries") is False
