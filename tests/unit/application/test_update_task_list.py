"""LIST-04 and the rename leg of LIST-06, including what "omitted" has to mean.

Three legs of D-05 are pinned separately - a field omitted, a field carrying a
value, and a field carrying an explicit null - because they are three different
outcomes and only the sentinel can express the difference. A use case that read
`None` as "not provided" would pass the first two tests here and quietly refuse
to let anybody clear a description.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from taskmanager.application.dto.commands import UpdateTaskListCommand
from taskmanager.application.dto.unset import UNSET, Unset
from taskmanager.application.use_cases.task_lists.update import UpdateTaskList
from taskmanager.domain.entities.task_list import TaskList
from taskmanager.domain.exceptions import (
    AuthorizationError,
    DomainError,
    DuplicateTaskListNameError,
    TaskListNotFoundError,
)
from tests.unit.application.fakes import FakeUnitOfWork, FrozenClock

pytestmark = pytest.mark.unit

# Fixed on purpose. A generated identifier or a real clock reading would make
# every assertion below unfalsifiable: the test could no longer state which
# moment, or which actor, it expects.
NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
LATER = NOW + timedelta(hours=3)
ACTOR_ID = UUID("11111111-1111-4111-8111-111111111111")
OTHER_USER_ID = UUID("99999999-9999-4999-8999-999999999999")
LIST_ID = UUID("33333333-3333-4333-8333-333333333333")
OTHER_LIST_ID = UUID("44444444-4444-4444-8444-444444444444")

NAME = "Phase 4"
NEW_NAME = "Phase 4 - task lists"
TAKEN_NAME = "Phase 5"
DESCRIPTION = "Everything the list endpoints owe."
NEW_DESCRIPTION = "Rewritten in one PATCH."


def _uow(
    *,
    owner_id: UUID = ACTOR_ID,
    with_list: bool = True,
    also_named: str | None = None,
) -> FakeUnitOfWork:
    """Assemble a unit of work holding the list, and optionally a rival name.

    Entities go into `stored` directly rather than through `add()`, so the
    `updated` record stays empty and every entry a test finds in it was written
    by the use case.
    """
    unit_of_work = FakeUnitOfWork()
    if with_list:
        task_list = TaskList.create(
            task_list_id=LIST_ID,
            owner_id=owner_id,
            name=NAME,
            description=DESCRIPTION,
            now=NOW,
        )
        unit_of_work.task_list_repository.stored[task_list.id] = task_list
    if also_named is not None:
        rival = TaskList.create(
            task_list_id=OTHER_LIST_ID,
            owner_id=owner_id,
            name=also_named,
            now=NOW,
        )
        unit_of_work.task_list_repository.stored[rival.id] = rival
    return unit_of_work


def _command(
    *,
    name: str | Unset = UNSET,
    description: str | None | Unset = UNSET,
    actor_id: UUID = ACTOR_ID,
) -> UpdateTaskListCommand:
    """The single construction site every test below goes through."""
    return UpdateTaskListCommand(
        actor_id=actor_id,
        task_list_id=LIST_ID,
        name=name,
        description=description,
    )


async def test_update_task_list_renames_without_touching_the_description() -> None:
    """The omitted leg of D-05: a field nobody mentioned is left exactly alone."""
    unit_of_work = _uow()
    use_case = UpdateTaskList(unit_of_work, FrozenClock(LATER))

    result = await use_case.execute(_command(name=NEW_NAME))

    assert result.name == NEW_NAME
    assert result.description == DESCRIPTION
    assert result.created_at == NOW
    assert result.updated_at == LATER
    assert len(unit_of_work.task_list_repository.updated) == 1
    assert unit_of_work.commits == 1
    assert unit_of_work.rollbacks == 0


async def test_update_task_list_re_describes_without_touching_the_name() -> None:
    """The same rule from the other side, so neither mutator can be the default."""
    unit_of_work = _uow()
    use_case = UpdateTaskList(unit_of_work, FrozenClock(LATER))

    result = await use_case.execute(_command(description=NEW_DESCRIPTION))

    assert result.name == NAME
    assert result.description == NEW_DESCRIPTION
    assert result.updated_at == LATER
    assert unit_of_work.commits == 1
    assert unit_of_work.rollbacks == 0


async def test_an_explicit_null_description_clears_it() -> None:
    """D-05's third leg, and the reason `None` cannot also mean "omitted".

    This is the request the sentinel exists for: it and the test above send the
    same field, and a use case with one marker for both meanings has to get one
    of them wrong.
    """
    unit_of_work = _uow()
    use_case = UpdateTaskList(unit_of_work, FrozenClock(LATER))

    result = await use_case.execute(_command(description=None))

    assert result.description is None
    assert result.name == NAME
    assert unit_of_work.task_list_repository.stored[LIST_ID].description is None
    assert unit_of_work.commits == 1


async def test_a_command_with_neither_field_changes_nothing_and_still_commits() -> None:
    """The request D-06 never lets through, pinned anyway.

    `updated_at` does **not** move here, and that is the decision stated exactly:
    the stamp follows a field being *provided*, and no field was. The schema
    answers an empty body with a 422 before a command is built, so this is the
    use case's behaviour for a request the API does not deliver - worth a test
    precisely because nothing upstream would reveal a change in it.
    """
    unit_of_work = _uow()
    use_case = UpdateTaskList(unit_of_work, FrozenClock(LATER))

    result = await use_case.execute(_command())

    assert result.name == NAME
    assert result.description == DESCRIPTION
    assert result.updated_at == NOW
    assert len(unit_of_work.task_list_repository.updated) == 1
    assert unit_of_work.commits == 1
    assert unit_of_work.rollbacks == 0


async def test_updated_at_moves_even_when_the_value_is_unchanged() -> None:
    """04-PATTERNS Pitfall 10, named after the decision it records.

    Sending `name` with the value it already holds still stamps the list. The
    rejected alternative - comparing old and new before stamping - would put a
    second "did this change?" rule beside mutators that already stamp
    unconditionally.
    """
    unit_of_work = _uow()
    use_case = UpdateTaskList(unit_of_work, FrozenClock(LATER))

    result = await use_case.execute(_command(name=NAME))

    assert result.name == NAME
    assert result.updated_at == LATER
    assert unit_of_work.commits == 1


async def test_resending_the_lists_own_name_is_not_a_conflict() -> None:
    """LIST-06 must not refuse a list on the strength of its own row.

    The rival list here carries the *same* name as the one being patched, which
    is what the stored state looks like from an unconditional pre-check's point
    of view - so an implementation without the comparison answers 409 to a PATCH
    that changes nothing about the name at all.
    """
    unit_of_work = _uow(also_named=NAME)
    use_case = UpdateTaskList(unit_of_work, FrozenClock(LATER))

    result = await use_case.execute(_command(name=NAME, description=NEW_DESCRIPTION))

    assert result.name == NAME
    assert result.description == NEW_DESCRIPTION
    assert unit_of_work.commits == 1
    assert unit_of_work.rollbacks == 0


async def test_resending_the_lists_own_name_padded_is_not_a_conflict() -> None:
    """Review fix WR-01: a re-send with surrounding whitespace is still a re-send.

    Unlike the test above there is no rival list here, and that is the point. The
    only row that can match `" Phase 4 "` once it is trimmed is this list's own -
    so a comparison made on the raw string sees a "new" name, asks the
    repository, finds the list itself and answers 409. The exact-spelling test
    passed over that defect by coincidence of its input.
    """
    unit_of_work = _uow()
    use_case = UpdateTaskList(unit_of_work, FrozenClock(LATER))

    result = await use_case.execute(_command(name=f"  {NAME}\t"))

    assert result.name == NAME
    assert unit_of_work.commits == 1
    assert unit_of_work.rollbacks == 0


async def test_a_refused_rename_reports_the_normalised_name() -> None:
    """One spelling of one error: the 409 echoes the name as it would be stored.

    The adapter's constraint path has always reported the trimmed
    `task_list.name`; the pre-check used to echo the client's untrimmed string.
    """
    unit_of_work = _uow(also_named=TAKEN_NAME)
    use_case = UpdateTaskList(unit_of_work, FrozenClock(LATER))

    with pytest.raises(DuplicateTaskListNameError) as excinfo:
        await use_case.execute(_command(name=f" {TAKEN_NAME} "))

    assert excinfo.value.details == {"field": "name", "name": TAKEN_NAME}
    assert unit_of_work.task_list_repository.stored[LIST_ID].name == NAME
    assert unit_of_work.task_list_repository.stored[LIST_ID].updated_at == NOW


async def test_update_task_list_refuses_a_rename_onto_a_name_the_owner_uses() -> None:
    """LIST-06's rename leg: the conflict is raised before anything is written."""
    unit_of_work = _uow(also_named=TAKEN_NAME)
    use_case = UpdateTaskList(unit_of_work, FrozenClock(LATER))

    with pytest.raises(DuplicateTaskListNameError) as excinfo:
        await use_case.execute(_command(name=TAKEN_NAME))

    assert excinfo.value.details == {"field": "name", "name": TAKEN_NAME}
    assert unit_of_work.task_list_repository.updated == []
    assert unit_of_work.task_list_repository.stored[LIST_ID].name == NAME
    assert unit_of_work.task_list_repository.stored[LIST_ID].updated_at == NOW
    assert unit_of_work.commits == 0
    assert unit_of_work.rollbacks == 1


async def test_update_task_list_hides_a_list_not_owned_by_the_actor() -> None:
    """D-04 and ADR-008 on the write verb: a 404, never a 403.

    The broad `DomainError` is caught on purpose - catching the leaf directly
    would pass against an implementation that never considered the 403 question
    (T-4-22).
    """
    unit_of_work = _uow(owner_id=OTHER_USER_ID)
    use_case = UpdateTaskList(unit_of_work, FrozenClock(LATER))

    with pytest.raises(DomainError) as excinfo:
        await use_case.execute(_command(name=NEW_NAME))

    error = excinfo.value
    assert isinstance(error, TaskListNotFoundError)
    assert not isinstance(error, AuthorizationError)
    assert error.details == {"task_list_id": str(LIST_ID)}
    assert unit_of_work.task_list_repository.updated == []
    assert unit_of_work.task_list_repository.stored[LIST_ID].name == NAME
    assert unit_of_work.commits == 0
    assert unit_of_work.rollbacks == 1


async def test_the_not_owned_update_answers_exactly_like_an_absent_list() -> None:
    """Both refusals are produced and compared, because D-04 is about a pair."""
    absent_uow = _uow(with_list=False)
    with pytest.raises(DomainError) as absent_info:
        await UpdateTaskList(absent_uow, FrozenClock(LATER)).execute(
            _command(name=NEW_NAME)
        )

    foreign_uow = _uow(owner_id=OTHER_USER_ID)
    with pytest.raises(DomainError) as foreign_info:
        await UpdateTaskList(foreign_uow, FrozenClock(LATER)).execute(
            _command(name=NEW_NAME)
        )

    absent, foreign = absent_info.value, foreign_info.value
    assert type(foreign) is type(absent)
    assert foreign.code == absent.code
    assert foreign.details == absent.details
    assert str(OTHER_USER_ID) not in str(foreign.details)
    assert absent_uow.commits == 0
    assert foreign_uow.commits == 0
