"""LIST-01, and the create leg of LIST-06, proved against the in-memory fakes.

Two properties are asserted by every test here rather than by whichever one
remembered: a success adds exactly one entity and leaves `commits == 1` with
`rollbacks == 0`, and a refusal adds nothing and leaves the mirror image. The
rollback half only measures anything because `FakeUnitOfWork.__aexit__` honours
the obligation the port states - see `test_ports.py` for that behaviour alone.

The clock is stopped at `LATER` while every pre-existing list in the fixtures is
stamped `NOW`. The two instants differ on purpose: a single-instant test cannot
tell a use case that reads the clock from one that copied a timestamp off
something it found in the repository.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from taskmanager.application.dto.commands import CreateTaskListCommand
from taskmanager.application.use_cases.task_lists.create import CreateTaskList
from taskmanager.domain.entities.task_list import TaskList
from taskmanager.domain.exceptions import DuplicateTaskListNameError
from tests.unit.application.fakes import FakeUnitOfWork, FrozenClock

# Fixed on purpose. A generated identifier or a real clock reading would make
# every assertion below unfalsifiable: the test could no longer state which
# moment, or which actor, it expects.
NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
LATER = NOW + timedelta(hours=3)
ACTOR_ID = UUID("11111111-1111-4111-8111-111111111111")
OTHER_USER_ID = UUID("99999999-9999-4999-8999-999999999999")
LIST_ID = UUID("33333333-3333-4333-8333-333333333333")

NAME = "Phase 4"
DESCRIPTION = "The five list use cases."


def _uow(
    *,
    existing_name: str | None = None,
    existing_owner: UUID = ACTOR_ID,
) -> FakeUnitOfWork:
    """Assemble a unit of work, optionally already holding one named list.

    The entity is placed in `stored` directly rather than through `add()`, so
    the `added` record stays empty and every entry a test finds in it was
    written by the use case.
    """
    unit_of_work = FakeUnitOfWork()
    if existing_name is not None:
        task_list = TaskList.create(
            task_list_id=LIST_ID,
            owner_id=existing_owner,
            name=existing_name,
            now=NOW,
        )
        unit_of_work.task_list_repository.stored[task_list.id] = task_list
    return unit_of_work


def _command(
    *,
    name: str = NAME,
    description: str | None = DESCRIPTION,
    actor_id: UUID = ACTOR_ID,
) -> CreateTaskListCommand:
    """The single construction site every test below goes through."""
    return CreateTaskListCommand(
        actor_id=actor_id,
        name=name,
        description=description,
    )


async def test_create_task_list_returns_the_owner_the_instant_and_zero_statistics() -> (
    None
):
    """The happy path: the actor owns it, the clock stamped it, nothing is done.

    `owner_id` is asserted against the *actor*, which is the whole of T-4-27:
    the command carries no owner field, so the only thing the use case could
    put there is the authenticated caller.
    """
    unit_of_work = _uow()
    use_case = CreateTaskList(unit_of_work, FrozenClock(LATER))

    result = await use_case.execute(_command())

    assert result.owner_id == ACTOR_ID
    assert result.name == NAME
    assert result.description == DESCRIPTION
    assert result.created_at == LATER
    assert result.updated_at == LATER
    assert result.total_tasks == 0
    assert result.completed_tasks == 0
    assert result.completion_percentage == 0.0


async def test_create_task_list_adds_the_entity_once_and_commits() -> None:
    """The write reached the repository exactly once, and was made durable.

    `added` rather than `stored`: a use case that saved twice would leave the
    same final state behind and is caught only by the count.
    """
    unit_of_work = _uow()
    use_case = CreateTaskList(unit_of_work, FrozenClock(LATER))

    result = await use_case.execute(_command())

    assert len(unit_of_work.task_list_repository.added) == 1
    stored = unit_of_work.task_list_repository.added[0]
    assert stored.id == result.id
    assert stored.owner_id == ACTOR_ID
    assert unit_of_work.commits == 1
    assert unit_of_work.rollbacks == 0


async def test_create_task_list_refuses_a_name_the_owner_already_uses() -> None:
    """LIST-06: the conflict is raised before anything is written."""
    unit_of_work = _uow(existing_name=NAME)
    use_case = CreateTaskList(unit_of_work, FrozenClock(LATER))

    with pytest.raises(DuplicateTaskListNameError) as excinfo:
        await use_case.execute(_command())

    assert excinfo.value.details == {"field": "name", "name": NAME}
    assert unit_of_work.task_list_repository.added == []
    assert unit_of_work.commits == 0
    assert unit_of_work.rollbacks == 1


async def test_a_refused_create_reports_the_normalised_name() -> None:
    """Review fix WR-01: the 409 echoes the name as it would have been stored.

    The adapter's constraint path reports the trimmed `task_list.name`; the
    pre-check used to echo the client's untrimmed string, so one error had two
    spellings depending on which road caught it.
    """
    unit_of_work = _uow(existing_name=NAME)
    use_case = CreateTaskList(unit_of_work, FrozenClock(LATER))

    with pytest.raises(DuplicateTaskListNameError) as excinfo:
        await use_case.execute(_command(name=f"  {NAME} "))

    assert excinfo.value.details == {"field": "name", "name": NAME}
    assert unit_of_work.task_list_repository.added == []
    assert unit_of_work.commits == 0


async def test_a_name_differing_only_in_case_is_not_a_duplicate() -> None:
    """D-12: uniqueness is case-sensitive, because the entity folds no case.

    A use case that compared case-insensitively would refuse a list
    `uq_task_lists_owner_id_name` accepts - an endpoint stricter than the
    database, which is the direction nobody notices until a user complains.
    """
    unit_of_work = _uow(existing_name=NAME.lower())
    use_case = CreateTaskList(unit_of_work, FrozenClock(LATER))

    result = await use_case.execute(_command())

    assert result.name == NAME
    assert len(unit_of_work.task_list_repository.added) == 1
    assert unit_of_work.commits == 1


async def test_another_owners_identical_name_is_not_a_duplicate() -> None:
    """LIST-06 is scoped per owner, so the check is passed the actor's id."""
    unit_of_work = _uow(existing_name=NAME, existing_owner=OTHER_USER_ID)
    use_case = CreateTaskList(unit_of_work, FrozenClock(LATER))

    result = await use_case.execute(_command())

    assert result.name == NAME
    assert result.owner_id == ACTOR_ID
    assert unit_of_work.commits == 1
    assert unit_of_work.rollbacks == 0


@pytest.mark.parametrize("description", [None, ""], ids=["null", "empty"])
async def test_an_absent_description_is_stored_as_none(description: str | None) -> None:
    """`optional_text` folds "" to None, so the field has one absent form.

    Asserted through the use case rather than only on the entity because this
    is the shape that reaches a response body: two ways to say "no description"
    would be two different JSON payloads for the same request.
    """
    unit_of_work = _uow()
    use_case = CreateTaskList(unit_of_work, FrozenClock(LATER))

    result = await use_case.execute(_command(description=description))

    assert result.description is None
    assert unit_of_work.task_list_repository.added[0].description is None
