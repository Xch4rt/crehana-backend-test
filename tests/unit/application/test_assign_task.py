"""Where four decisions meet: the door, the no-op, the ordering, and the email.

`AssignTask` is the only use case in the project that does something after its
transaction has ended, and three of the tests here exist because a call count
cannot see the difference between right and wrong:

* **Ordering (NOTF-01).** One commit and one send is equally true of a send that
  happened first, which is the thing D-16 forbids - a notification for a write
  that then failed. So the fake unit of work and the notifier append to one
  shared list and the assertion is on the sequence.
* **Failure (NOTF-03).** "No exception escaped" is equally true of an
  implementation that swallowed the error *and* rolled the assignment back, so
  the test re-reads the task out of the repository afterwards.
* **Guard ordering (T-5-12, Pitfall 13).** A stranger naming a user id that does
  not exist must get the answer a stranger naming a real one gets. Asserted as a
  pair, produced from two fixtures and compared, because a single-error
  assertion passes just as happily against a use case that looked the user up
  first and happened to answer 404 either way with a different code.

Every failure test asserts `commits == 0` and `rollbacks == 1` as well as the
exception, and that nothing was sent - the suite convention `test_delete_task.py`
describes, plus the outbound half this use case adds.
"""

import logging
from datetime import UTC, datetime, timedelta
from types import TracebackType
from typing import Self
from uuid import UUID

import pytest

from taskmanager.application.dto.commands import AssignTaskCommand
from taskmanager.application.ports.repositories import UserRepository
from taskmanager.application.use_cases.tasks.assign import AssignTask
from taskmanager.domain.entities.task import Task
from taskmanager.domain.entities.task_list import TaskList
from taskmanager.domain.entities.user import User
from taskmanager.domain.exceptions import (
    AuthorizationError,
    DomainError,
    TaskNotFoundError,
    UserNotFoundError,
)
from taskmanager.domain.value_objects.task_priority import TaskPriority
from tests.unit.application.fakes import (
    FakeEmailNotifier,
    FakeUnitOfWork,
    FrozenClock,
)

pytestmark = pytest.mark.unit

# Fixed on purpose. A generated identifier or a real clock reading would make
# every assertion below unfalsifiable: the test could no longer state which
# moment, or which actor, it expects.
NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
LATER = NOW + timedelta(hours=3)
ACTOR_ID = UUID("11111111-1111-4111-8111-111111111111")
TASK_ID = UUID("22222222-2222-4222-8222-222222222222")
TASK_LIST_ID = UUID("33333333-3333-4333-8333-333333333333")
OTHER_LIST_ID = UUID("44444444-4444-4444-8444-444444444444")
ASSIGNEE_ID = UUID("55555555-5555-4555-8555-555555555555")
SECOND_ASSIGNEE_ID = UUID("66666666-6666-4666-8666-666666666666")
# The caller who is neither the owner nor the assignee, and the id of a user
# who has no row at all - the two halves of the Pitfall 13 pair.
STRANGER_ID = UUID("77777777-7777-4777-8777-777777777777")
OTHER_USER_ID = UUID("99999999-9999-4999-8999-999999999999")
MISSING_USER_ID = UUID("00000000-0000-4000-8000-000000000000")

OWNER_EMAIL = "ana@example.com"
ASSIGNEE_EMAIL = "bruno@example.com"
SECOND_ASSIGNEE_EMAIL = "carla@example.com"
TITLE = "Write the assignment use case"

# The logger `assign.py` names itself after, spelled here so an assertion about
# a WARNING cannot be satisfied by a record some other module emitted.
LOGGER_NAME = "taskmanager.application.use_cases.tasks.assign"


class _NotifierDown(RuntimeError):
    """What an outbound dependency having a bad day looks like from in here."""


class _FailingEmailNotifier(FakeEmailNotifier):
    """Records the attempt, then raises - so "it was tried" stays assertable."""

    async def send_task_assigned(
        self,
        *,
        recipient_email: str,
        task_title: str,
        task_id: UUID,
    ) -> None:
        await super().send_task_assigned(
            recipient_email=recipient_email, task_title=task_title, task_id=task_id
        )
        raise _NotifierDown("the mail service is unreachable")


class _RecordingEmailNotifier(FakeEmailNotifier):
    """The outbound half of the ordering record (NOTF-01)."""

    def __init__(self, events: list[str]) -> None:
        super().__init__()
        self.events = events

    async def send_task_assigned(
        self,
        *,
        recipient_email: str,
        task_title: str,
        task_id: UUID,
    ) -> None:
        self.events.append("send")
        await super().send_task_assigned(
            recipient_email=recipient_email, task_title=task_title, task_id=task_id
        )


class _RecordingUnitOfWork(FakeUnitOfWork):
    """The transactional half of the same record, writing to the same list."""

    def __init__(self, events: list[str]) -> None:
        super().__init__()
        self.events = events

    async def commit(self) -> None:
        self.events.append("commit")
        await super().commit()


class _ClosedUserRepository:
    """A user repository that refuses everything, standing in for a spent one.

    `SqlAlchemyUnitOfWork.__aexit__` unbinds its repositories and the port
    documents any use after the block as a `RuntimeError`, which a dictionary
    cannot model on its own. This class is what the unit of work below swaps in
    on the way out, so a use case that reached back for the assignee's address
    after the transaction ended fails here rather than in production.
    """

    async def get(self, user_id: UUID) -> User | None:
        raise RuntimeError("the unit of work has already been closed")

    async def get_by_email(self, email: str) -> User | None:
        raise RuntimeError("the unit of work has already been closed")

    async def add(self, user: User) -> None:
        raise RuntimeError("the unit of work has already been closed")

    async def list_all(self) -> list[User]:
        raise RuntimeError("the unit of work has already been closed")


class _ClosingUnitOfWork(FakeUnitOfWork):
    """The shared fake, which actually becomes unusable when its block ends."""

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await super().__aexit__(exc_type, exc, tb)
        closed: UserRepository = _ClosedUserRepository()
        self.users = closed

    async def __aenter__(self) -> Self:
        # Re-bound on entry, so the object is reusable within a test even
        # though a single `execute` only ever enters it once.
        self.users = self.user_repository
        return await super().__aenter__()


def _uow(
    *,
    owner_id: UUID = ACTOR_ID,
    assignee_id: UUID | None = None,
    unit_of_work: FakeUnitOfWork | None = None,
) -> FakeUnitOfWork:
    """Two lists, one task and three accounts, written straight into `stored`.

    `owner_id` is the ownership lever and `assignee_id` the other role's, and
    both lists belong to the same owner so nothing but the intended condition
    can refuse a request. The absent-task and wrong-parent legs are not levers
    here: they belong to `access.py` and are pinned in `test_access.py`, where
    they are proved once for every use case that enters the guard.

    Entities go in directly rather than through `add()`, so `added` and
    `updated` stay empty and every entry a test finds in them was written by
    the use case. `unit_of_work` lets a test bring its own instrumented one.
    """
    unit_of_work = unit_of_work if unit_of_work is not None else FakeUnitOfWork()
    for task_list_id in (TASK_LIST_ID, OTHER_LIST_ID):
        unit_of_work.task_list_repository.stored[task_list_id] = TaskList.create(
            task_list_id=task_list_id,
            owner_id=owner_id,
            name=f"List {task_list_id}",
            now=NOW,
        )
    task = Task.create(
        task_id=TASK_ID,
        task_list_id=TASK_LIST_ID,
        title=TITLE,
        priority=TaskPriority.HIGH,
        assignee_id=assignee_id,
        now=NOW,
    )
    unit_of_work.task_repository.stored[task.id] = task
    for user_id, email in (
        (ACTOR_ID, OWNER_EMAIL),
        (ASSIGNEE_ID, ASSIGNEE_EMAIL),
        (SECOND_ASSIGNEE_ID, SECOND_ASSIGNEE_EMAIL),
    ):
        unit_of_work.user_repository.stored[user_id] = User.create(
            user_id=user_id,
            email=email,
            full_name="A registered person",
            password_hash="argon2-encoded-hash",
            now=NOW,
        )
    return unit_of_work


def _command(
    *,
    actor_id: UUID = ACTOR_ID,
    assignee_id: UUID = ASSIGNEE_ID,
    task_list_id: UUID = TASK_LIST_ID,
) -> AssignTaskCommand:
    """The single construction site every test below goes through."""
    return AssignTaskCommand(
        actor_id=actor_id,
        task_list_id=task_list_id,
        task_id=TASK_ID,
        assignee_id=assignee_id,
    )


async def test_the_owner_assigns_an_existing_user_and_notifies_them() -> None:
    """The happy path: the field moves, the write is durable, one email goes out.

    The hold is asserted here too, in passing: ADR-058 says a write path takes
    the locking road and holds only the addressed row, and
    `test_write_paths_hold_what_they_change.py` is where that claim is kept for
    the set of them.
    """
    unit_of_work = _uow()
    notifier = FakeEmailNotifier()

    result = await AssignTask(unit_of_work, FrozenClock(LATER), notifier).execute(
        _command()
    )

    assert result.assignee_id == ASSIGNEE_ID
    assert result.updated_at == LATER
    assert unit_of_work.task_repository.stored[TASK_ID].assignee_id == ASSIGNEE_ID
    assert unit_of_work.task_repository.updated == [
        unit_of_work.task_repository.stored[TASK_ID]
    ]
    assert unit_of_work.commits == 1
    assert unit_of_work.rollbacks == 0
    assert notifier.sent == [(ASSIGNEE_EMAIL, TITLE, TASK_ID)]
    assert unit_of_work.task_repository.held_for_update == [TASK_ID]
    assert unit_of_work.task_list_repository.held_for_update == []


async def test_reassignment_notifies_only_the_new_assignee() -> None:
    """D-07's other half: handing the task on is one email, to the new person.

    The previous assignee is deliberately not told. Nothing in ASGN-01 or
    NOTF-01 asks for it, and inventing a second message here would be a product
    decision made in a use case.
    """
    unit_of_work = _uow(assignee_id=ASSIGNEE_ID)
    notifier = FakeEmailNotifier()

    result = await AssignTask(unit_of_work, FrozenClock(LATER), notifier).execute(
        _command(assignee_id=SECOND_ASSIGNEE_ID)
    )

    assert result.assignee_id == SECOND_ASSIGNEE_ID
    assert notifier.sent == [(SECOND_ASSIGNEE_EMAIL, TITLE, TASK_ID)]
    assert unit_of_work.commits == 1


async def test_assigning_the_same_user_again_is_a_no_op_that_sends_nothing() -> None:
    """D-07: a repeated `PUT` is a 200 that writes nothing and mails nobody.

    It mirrors `Task.change_status`'s same-state no-op, and it cannot live in
    `Task.assign` - the entity has no way to skip a commit or an email, which is
    why the entity deliberately carries no such guard (plan 05-01).

    `updated_at` is asserted unchanged as well as the counters: an
    implementation that returned early *after* stamping the entity would leave
    the timestamp moved in memory and satisfy every count here.
    """
    unit_of_work = _uow(assignee_id=ASSIGNEE_ID)
    notifier = FakeEmailNotifier()

    result = await AssignTask(unit_of_work, FrozenClock(LATER), notifier).execute(
        _command()
    )

    assert result.assignee_id == ASSIGNEE_ID
    assert result.updated_at == NOW
    assert unit_of_work.task_repository.updated == []
    assert unit_of_work.commits == 0
    assert unit_of_work.rollbacks == 1
    assert notifier.sent == []


async def test_the_owner_may_assign_themselves_and_is_notified_like_anyone() -> None:
    """D-08: self-assignment is an ordinary assignment, with no special case.

    A branch exempting the owner from the email would be a rule nobody asked
    for, and it would make the one path an evaluator is most likely to try by
    hand the one path that emits no log line.
    """
    unit_of_work = _uow()
    notifier = FakeEmailNotifier()

    result = await AssignTask(unit_of_work, FrozenClock(LATER), notifier).execute(
        _command(assignee_id=ACTOR_ID)
    )

    assert result.assignee_id == ACTOR_ID
    assert notifier.sent == [(OWNER_EMAIL, TITLE, TASK_ID)]
    assert unit_of_work.commits == 1


async def test_assign_refuses_the_assignee_with_a_403() -> None:
    """D-03: an assignee may advance their task, never hand it to somebody else.

    The task is still unassigned-to-nobody-else afterwards, because an
    implementation that refused *after* writing would be a 403 that changed
    something.
    """
    unit_of_work = _uow(owner_id=OTHER_USER_ID, assignee_id=ACTOR_ID)
    notifier = FakeEmailNotifier()

    with pytest.raises(DomainError) as excinfo:
        await AssignTask(unit_of_work, FrozenClock(LATER), notifier).execute(
            _command(assignee_id=SECOND_ASSIGNEE_ID)
        )

    error = excinfo.value
    assert isinstance(error, AuthorizationError)
    assert not isinstance(error, TaskNotFoundError)
    assert str(OTHER_USER_ID) not in str(error)
    assert unit_of_work.task_repository.stored[TASK_ID].assignee_id == ACTOR_ID
    assert unit_of_work.commits == 0
    assert unit_of_work.rollbacks == 1
    assert notifier.sent == []


async def test_assign_hides_the_task_from_a_stranger() -> None:
    """The 404 leg: a caller with no relationship is told the task is not there."""
    unit_of_work = _uow(owner_id=OTHER_USER_ID, assignee_id=ASSIGNEE_ID)
    notifier = FakeEmailNotifier()

    with pytest.raises(DomainError) as excinfo:
        await AssignTask(unit_of_work, FrozenClock(LATER), notifier).execute(
            _command(actor_id=STRANGER_ID, assignee_id=SECOND_ASSIGNEE_ID)
        )

    error = excinfo.value
    assert isinstance(error, TaskNotFoundError)
    assert not isinstance(error, AuthorizationError)
    assert error.details == {"task_id": str(TASK_ID)}
    assert unit_of_work.commits == 0
    assert unit_of_work.rollbacks == 1
    assert notifier.sent == []


async def test_a_stranger_naming_an_unknown_user_learns_nothing_about_them() -> None:
    """T-5-12 / Pitfall 13: the ownership guard runs before the user lookup.

    Reversed, this route is a user-existence oracle for somebody who cannot see
    the task at all: `user_not_found` for an invented id and `task_not_found`
    for a real one tells them which ids are real. So both refusals are produced
    and compared - class, code, details and message - rather than one of them
    asserted alone, which would pass against an implementation that leaked the
    difference through a code the single assertion never looked at.
    """
    invented_uow = _uow(owner_id=OTHER_USER_ID, assignee_id=ASSIGNEE_ID)
    with pytest.raises(DomainError) as invented_info:
        await AssignTask(invented_uow, FrozenClock(LATER), FakeEmailNotifier()).execute(
            _command(actor_id=STRANGER_ID, assignee_id=MISSING_USER_ID)
        )

    real_uow = _uow(owner_id=OTHER_USER_ID, assignee_id=ASSIGNEE_ID)
    with pytest.raises(DomainError) as real_info:
        await AssignTask(real_uow, FrozenClock(LATER), FakeEmailNotifier()).execute(
            _command(actor_id=STRANGER_ID, assignee_id=SECOND_ASSIGNEE_ID)
        )

    invented, real = invented_info.value, real_info.value
    assert isinstance(invented, TaskNotFoundError)
    assert not isinstance(invented, UserNotFoundError)
    assert type(invented) is type(real)
    assert invented.code == real.code
    assert invented.details == real.details
    assert str(invented) == str(real)


async def test_the_owner_naming_an_unknown_user_gets_user_not_found() -> None:
    """D-08: for the owner the disclosure is harmless, so the 404 is honest.

    `GET /api/v1/users` already lists every account to every authenticated
    caller (D-13), so telling a list owner that an id they invented is not a
    user hands them nothing a second request would not have handed them - and
    a `task_not_found` here would be a lie about a task they can plainly see.
    """
    unit_of_work = _uow()
    notifier = FakeEmailNotifier()

    with pytest.raises(UserNotFoundError) as excinfo:
        await AssignTask(unit_of_work, FrozenClock(LATER), notifier).execute(
            _command(assignee_id=MISSING_USER_ID)
        )

    assert excinfo.value.details == {"user_id": str(MISSING_USER_ID)}
    assert unit_of_work.task_repository.stored[TASK_ID].assignee_id is None
    assert unit_of_work.task_repository.updated == []
    assert unit_of_work.commits == 0
    assert unit_of_work.rollbacks == 1
    assert notifier.sent == []


async def test_the_task_is_made_durable_before_the_notification_is_attempted() -> None:
    """NOTF-01 as a sequence, because two counts of one prove nothing.

    A send that ran first, inside the block, would record exactly the same
    numbers as a correct implementation - and would email an assignment that a
    later failure then rolled back. The unit of work and the notifier append to
    one shared list, so the order is the assertion.
    """
    events: list[str] = []
    unit_of_work = _uow(unit_of_work=_RecordingUnitOfWork(events))
    notifier = _RecordingEmailNotifier(events)

    await AssignTask(unit_of_work, FrozenClock(LATER), notifier).execute(_command())

    assert events == ["commit", "send"]


async def test_a_notifier_failure_leaves_the_assignment_durable(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """NOTF-03: the email is best effort, the assignment is not.

    The task is re-read out of the repository rather than off the returned
    result, and that is the whole point: asserting only that no exception
    escaped would pass just as well against an implementation that swallowed
    the error *and* rolled the write back, which is precisely the outcome
    D-16 puts the send outside the block to prevent.

    The WARNING names the task id and carries the traceback. It deliberately
    does **not** carry the task title (T-5-13): a title is caller-supplied text
    and a log line is not the place to find out what it does to a parser.
    """
    unit_of_work = _uow()
    notifier = _FailingEmailNotifier()

    result = await AssignTask(unit_of_work, FrozenClock(LATER), notifier).execute(
        _command()
    )

    assert result.assignee_id == ASSIGNEE_ID
    assert unit_of_work.task_repository.stored[TASK_ID].assignee_id == ASSIGNEE_ID
    assert unit_of_work.commits == 1
    assert notifier.sent == [(ASSIGNEE_EMAIL, TITLE, TASK_ID)]

    warnings = [
        record
        for record in caplog.records
        if record.name == LOGGER_NAME and record.levelno == logging.WARNING
    ]
    assert len(warnings) == 1
    assert str(TASK_ID) in warnings[0].getMessage()
    assert TITLE not in warnings[0].getMessage()
    assert warnings[0].exc_info is not None
    assert isinstance(warnings[0].exc_info[1], _NotifierDown)


async def test_the_use_case_never_reaches_into_the_closed_unit_of_work() -> None:
    """The address leaves the block as a plain `str`, captured inside it.

    `SqlAlchemyUnitOfWork.__aexit__` unbinds its repositories, and the port
    documents any use afterwards as a `RuntimeError` - which the dictionary
    fakes cannot model, so this test's unit of work swaps in a repository that
    refuses everything on the way out. An implementation that read
    `uow.users.get(...)` again to build the email would raise here, and the
    failure would otherwise wait for production.
    """
    unit_of_work = _uow(unit_of_work=_ClosingUnitOfWork())
    notifier = FakeEmailNotifier()

    result = await AssignTask(unit_of_work, FrozenClock(LATER), notifier).execute(
        _command()
    )

    assert result.assignee_id == ASSIGNEE_ID
    assert notifier.sent == [(ASSIGNEE_EMAIL, TITLE, TASK_ID)]
